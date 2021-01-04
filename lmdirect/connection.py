"""lmdirect connection class"""
import asyncio
import logging
from datetime import datetime, timedelta
from functools import partial

from authlib.integrations.base_client.errors import OAuthError
from authlib.integrations.httpx_client import AsyncOAuth2Client

from .aescipher import AESCipher
from .const import *
from .msgs import (
    AUTO_BITFIELD,
    AUTO_BITFIELD_MAP,
    DIVIDE_KEYS,
    DRINK_OFFSET_MAP,
    FIRMWARE_VER,
    GATEWAY_DRINK_MAP,
    MSGS,
    SERIAL_NUMBERS,
    UPDATE_AVAILABLE,
    Elem,
    Msg,
)

_LOGGER = logging.getLogger(__name__)


class Connection:
    def __init__(self, machine_info):
        """Init LMDirect"""
        self._reader = None
        self._writer = None
        self._read_response_task = None
        self._read_reaper_task = None
        self._current_status = {}
        self._responses_waiting = []
        self._run = True
        self._callback_list = []
        self._raw_callback_list = []
        self._cipher = None
        self._machine_info = machine_info
        self._start_time = None
        self._connected = False
        self._lock = asyncio.Lock()
        self._first_time = True
        self._update_available = None

    async def retrieve_machine_info(self, machine_info):
        """Machine data inialization"""
        _LOGGER.debug(f"Retrieving machine info")

        client = AsyncOAuth2Client(
            client_id=machine_info[CLIENT_ID],
            client_secret=machine_info[CLIENT_SECRET],
            token_endpoint=TOKEN_URL,
        )

        headers = {
            "client_id": machine_info[CLIENT_ID],
            "client_secret": machine_info[CLIENT_SECRET],
        }

        try:
            await client.fetch_token(
                url=TOKEN_URL,
                username=machine_info[USERNAME],
                password=machine_info[PASSWORD],
                headers=headers,
            )
        except OAuthError:
            await client.aclose()
            raise AuthFail("Authorization failure")

        except Exception as err:
            await self.close()
            raise AuthFail(f"Caught: {type(err)}, {err}")

        """Only retrieve this the first time"""
        if any(
            x not in machine_info
            for x in [KEY, SERIAL_NUMBER, MACHINE_NAME, MODEL_NAME]
        ):
            cust_info = await client.get(CUSTOMER_URL)
            if cust_info:
                fleet = cust_info.json()["data"]["fleet"][0]
                machine_info[KEY] = fleet["communicationKey"]
                machine_info[SERIAL_NUMBER] = fleet["machine"]["serialNumber"]
                machine_info[MACHINE_NAME] = fleet["name"]
                machine_info[MODEL_NAME] = fleet["machine"]["model"]["name"]

        if any(x not in self._current_status for x in DRINK_OFFSET_MAP.values()):
            drink_info = await client.get(
                DRINK_COUNTER_URL.format(serial_number=machine_info[SERIAL_NUMBER])
            )
            if drink_info:
                data = drink_info.json()["data"]
                self._current_status.update(
                    {GATEWAY_DRINK_MAP[x["coffeeType"]]: x["count"] for x in data}
                )

        if UPDATE_AVAILABLE not in self._current_status:
            update_info = await client.get(UPDATE_URL)
            if update_info:
                data = update_info.json()["data"]
                self._update_available = "Yes" if data else "No"

        """Done with the cloud API"""
        await client.aclose()

        _LOGGER.debug(f"Finished machine info")
        return machine_info

    async def _connect(self):
        """Conmnect to espresso machine"""
        if self._connected:
            return self._machine_info

        _LOGGER.debug(f"Connecting")

        try:
            self._machine_info = await self.retrieve_machine_info(self._machine_info)
        except Exception as err:
            raise ConnectionFail(f"Exception retrieving machine info: {err}")

        if not self._cipher:
            self._cipher = AESCipher(self._machine_info[KEY])

        """Connect to the machine"""
        try:
            self._reader, self._writer = await asyncio.wait_for(
                asyncio.open_connection(
                    self._machine_info[HOST], self._machine_info[PORT]
                ),
                timeout=3,
            )
        except asyncio.TimeoutError:
            _LOGGER.warning("Connection Timeout, skipping")
            return None

        except Exception as err:
            raise ConnectionFail(f"Cannot connect to machine: {err}")

        """Start listening for responses & sending status requests"""
        await self.start_read_task()

        self._connected = True
        _LOGGER.debug("Finished Connecting")

        return self._machine_info

    async def start_read_task(self):
        """Start listening for responses & sending status requests"""
        loop = asyncio.get_event_loop()
        self._read_response_task = loop.create_task(
            self.read_response_task(), name="Response Task"
        )

        """Reap the results and any any exceptions"""
        self._read_reaper_task = loop.create_task(
            self.read_reaper(), name="Read Reaper"
        )

    async def _close(self):
        """Close the connection"""
        if not self._connected:
            return

        if self._writer is not None:
            self._writer.close()

        if self._read_response_task:
            self._read_response_task.cancel()

        self._reader = self._writer = None
        self._connected = False
        _LOGGER.debug("Finished closing")

    async def read_reaper(self):
        _LOGGER.debug("Starting read reaper")
        try:
            await asyncio.gather(self._read_response_task)
        except Exception as err:
            _LOGGER.error(f"Exception in read_response_task: {err}")

        await self._close()
        self._read_response_task = None
        self._first_time = False

        _LOGGER.debug("Finished reaping read task")

    def _call_callbacks(self, **kwargs):
        """Call the callbacks"""
        if self._callback_list is not None:
            [
                elem(
                    current_status=self._current_status,
                    **kwargs,
                )
                for elem in self._callback_list
            ]

    async def read_response_task(self):
        """Start thread to receive responses"""
        BUFFER_SIZE = 1000
        handle = None

        _LOGGER.debug("Starting read task")

        if self._start_time is None:
            self._start_time = datetime.now()

        while self._run:
            encoded_data = await self._reader.read(BUFFER_SIZE)
            if encoded_data is not None:
                loop = asyncio.get_event_loop()
                fn = partial(self._cipher.decrypt, encoded_data[1:-1])
                plaintext = await loop.run_in_executor(None, fn)
                if not plaintext:
                    continue

                await self.process_data(plaintext)

                if not self._first_time:
                    if handle:
                        handle.cancel()
                        handle = None

                    """Throttle callbacks"""
                    handle = loop.call_later(5, self._call_callbacks)
                else:
                    self._call_callbacks()

                """Exit if we've been reading longer than 5s"""
                if datetime.now() > self._start_time + timedelta(seconds=5):
                    _LOGGER.debug(f"Exiting loop: {self._responses_waiting}")

                    """Flush the wait list"""
                    self._responses_waiting = []
                    break

    async def process_data(self, plaintext):
        """Process incoming packet"""

        """Separate the mesg from the data"""
        msg_type = plaintext[0]
        raw_data = plaintext[1:]
        msg = raw_data[:8]

        """chop off the message and check byte"""
        data = raw_data[8:-2]
        finished = not len(self._responses_waiting)

        _LOGGER.debug(f"Message={msg}, Data={data}")

        """Find the matching item or returns None"""
        msg_id = next(
            (x for x in MSGS if MSGS[x].msg == msg and MSGS[x].msg_type == msg_type),
            None,
        )

        """notify any listeners for this message"""
        [
            await x[1]((msg_id, x[1]), data)
            for x in self._raw_callback_list
            if MSGS[x[0]].msg == msg
        ]

        if msg_id is None:
            _LOGGER.error(f"Unexpected response: {plaintext}")
            return finished
        else:
            cur_msg = MSGS[msg_id]

        if msg_id == Msg.GET_WATER_FLOW:
            _LOGGER.debug(plaintext)

        if cur_msg.map is not None:
            await self._populate_items(data, cur_msg)

        if cur_msg.msg in self._responses_waiting:
            self._responses_waiting.remove(cur_msg.msg)
            finished = not len(self._responses_waiting)
            if finished:
                _LOGGER.debug("Received all responses")

        return finished

    async def _populate_items(self, data, cur_msg):
        """process all the fields"""
        map = cur_msg.map
        for elem in map:
            """The strings are ASCII-encoded hex, so each value takes 2 bytes"""
            index = elem.index * 2
            size = elem.size * 2

            """Extract value for this field"""
            value = data[index : index + size]

            if elem.type == Elem.INT:
                """Convert from ascii-encoded hex"""
                value = int(value, 16)

            if "RESULT" in map[elem]:
                if Msg.RESPONSE_GOOD not in value:
                    _LOGGER.error(f"Command Failed: {map[elem]}: {data}")
                else:
                    _LOGGER.debug(f"Command Succeeded: {map[elem]}: {data}")
            elif any(x in map[elem] for x in DIVIDE_KEYS if x in map[elem]):
                value = value / 10
            elif map[elem] == FIRMWARE_VER:
                value = "%0.2f" % (value / 100)
            elif map[elem] in SERIAL_NUMBERS:
                value = "".join(
                    [chr(int(value[i : i + 2], 16)) for i in range(0, len(value), 2)]
                )
                value = value.partition("\0")[0]

            elif map[elem] == AUTO_BITFIELD:
                for item in AUTO_BITFIELD_MAP:
                    setting = ENABLED if value & 0x01 else DISABLED
                    self._current_status[AUTO_BITFIELD_MAP[item]] = setting
                    value = value >> 1
                continue
            elif map[elem] in DRINK_OFFSET_MAP:
                offset_index = DRINK_OFFSET_MAP[map[elem]]
                if map[elem] not in self._current_status:
                    """If we haven't seen the value before, calculate the offset"""
                    self._current_status.update(
                        {offset_index: value - self._current_status[offset_index]}
                    )
                """Offset the value"""
                value -= self._current_status[offset_index]

            self._current_status[map[elem]] = value

    async def _send_msg(self, msg_id, data=None, key=None):
        """Send command to espresso machine"""

        def checksum(buffer):
            """Compute check byte"""
            buffer = bytes(buffer, "utf-8")
            return "%0.2X" % (sum(buffer) % 256)

        """Prevent race conditions - can be called from different tasks"""
        async with self._lock:
            msg = MSGS[msg_id]
            _LOGGER.debug(f"Sending {msg.msg} with {data}")

            """Connect if we don't have an active connection"""
            result = await self._connect()

            if not result:
                raise ConnectionFail("Connection failed")

            if not self._writer:
                raise ConnectionFail(f"self._writer={self._writer}")

            """Add read/write and check bytes"""
            plaintext = msg.msg_type + msg.msg

            """If a key was provided, replace the second byte of the message"""
            if key:
                plaintext = plaintext[:3] + key + plaintext[5:]

            if data is not None:
                plaintext += data

            """Add the check byte"""
            plaintext += checksum(plaintext)

            loop = asyncio.get_event_loop()
            fn = partial(self._cipher.encrypt, plaintext)
            ciphertext = (
                "@" + (await loop.run_in_executor(None, fn)).decode("utf-8") + "%"
            )

            self._writer.write(bytes(ciphertext, "utf-8"))
            await self._writer.drain()

            """Remember that we're waiting for a response"""
            self._responses_waiting.append(msg.msg)

            """Note when the command was sent"""
            self._start_time = datetime.now()

            _LOGGER.debug("Finished sending")


class AuthFail(BaseException):
    """Error to indicate there is invalid auth"""

    def __init__(msg):
        _LOGGER.error(msg)


class ConnectionFail(BaseException):
    """Error to indicate there is no Connection"""

    def __init__(msg):
        _LOGGER.error(msg)
