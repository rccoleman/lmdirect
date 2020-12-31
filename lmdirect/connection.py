"""lmdirect connection class"""
from .const import *
from .aescipher import AESCipher
from .msgs import Msg, MSGS, AUTO_BITFIELD_MAP, Elem

from authlib.integrations.base_client.errors import OAuthError
from authlib.integrations.httpx_client import AsyncOAuth2Client
import asyncio
from datetime import timedelta, datetime
from functools import partial

import logging

_LOGGER = logging.getLogger(__name__)


class Connection:
    def __init__(self, creds):
        """Init LMDirect"""
        self._reader = None
        self._writer = None
        self._read_response_task = None
        self._reaper_task = None
        self._current_status = {}
        self._responses_waiting = []
        self._run = True
        self._callback_list = []
        self._raw_callback_list = []
        self._cipher = None
        self._creds = creds
        self._start_time = None
        self._connected = False
        self._lock = asyncio.Lock()
        self._first_time = True

    async def retrieve_key(self, creds):
        """Machine data inialization"""
        _LOGGER.debug("Retrieving key")

        client = AsyncOAuth2Client(
            client_id=creds[CLIENT_ID],
            client_secret=creds[CLIENT_SECRET],
            token_endpoint=TOKEN_URL,
        )

        headers = {
            "client_id": creds[CLIENT_ID],
            "client_secret": creds[CLIENT_SECRET],
        }

        try:
            await client.fetch_token(
                url=TOKEN_URL,
                username=creds[USERNAME],
                password=creds[PASSWORD],
                headers=headers,
            )
        except OAuthError:
            await client.aclose()
            raise AuthFail("Authorization failure")

        except Exception as err:
            await self.close()
            raise AuthFail(f"Caught: {type(err)}, {err}")

        cust_info = await client.get(CUSTOMER_URL)
        if cust_info is not None:
            fleet = cust_info.json()["data"]["fleet"][0]
            creds[KEY] = fleet["communicationKey"]
            creds[SERIAL_NUMBER] = fleet["machine"]["serialNumber"]
            creds[MACHINE_NAME] = fleet["name"]
            creds[MODEL_NAME] = fleet["machine"]["model"]["name"]

        """Done with the cloud API"""
        await client.aclose()

        _LOGGER.debug(f"Finished retrieving key")
        return creds

    async def _connect(self):
        """Conmnect to espresso machine"""
        if self._connected:
            return self._creds

        _LOGGER.debug("Connecting")

        if not self._creds.get(KEY):
            try:
                self._creds.update(await self.retrieve_key(self._creds))
            except Exception as err:
                raise ConnectionFail(f"Exception retrieving key: {err}")

        if not self._cipher:
            self._cipher = AESCipher(self._creds[KEY])

        """Connect to the machine"""
        try:
            self._reader, self._writer = await asyncio.wait_for(
                asyncio.open_connection(self._creds[HOST], self._creds[PORT]), timeout=3
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

        return self._creds

    async def start_read_task(self):
        """Start listening for responses & sending status requests"""
        loop = asyncio.get_event_loop()
        self._read_response_task = loop.create_task(
            self.read_response_task(), name="Response Task"
        )

        """Reap the results and any any exceptions"""
        self._reaper_task = loop.create_task(self.reaper(), name="Reaper")

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

    async def reaper(self):
        _LOGGER.debug("Starting reaper")
        try:
            await asyncio.gather(self._read_response_task)
        except Exception as err:
            _LOGGER.error(f"Exception in read_response_task: {err}")

        await self._close()
        self._read_response_task = None
        self._first_time = False

        _LOGGER.debug("Finished reaping")

    def _call_callbacks(self, **kwargs):
        """Call the callbacks"""
        if self._callback_list is not None:
            [
                elem(current_status=self._current_status, **kwargs)
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

                await self._process_data(plaintext)

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
                    _LOGGER.debug("Exiting loop: {}".format(self._responses_waiting))

                    """Flush the wait list"""
                    self._responses_waiting = []
                    break

    async def _process_data(self, plaintext):
        """Process incoming packet"""

        """Separate the mesg from the data"""
        msg_type = plaintext[0]
        raw_data = plaintext[1:]
        msg = raw_data[:8]

        """chop off the message and check byte"""
        data = raw_data[8:-2]
        finished = not len(self._responses_waiting)

        _LOGGER.debug("Message={}, Data={}".format(msg, data))

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
            _LOGGER.error("Unexpected response: {}".format(plaintext))
            return finished
        else:
            cur_msg = MSGS[msg_id]

        if cur_msg.map is not None:
            await self._populate_items(data, cur_msg)

        if cur_msg.msg in self._responses_waiting:
            self._responses_waiting.remove(cur_msg.msg)
            finished = not len(self._responses_waiting)
            _LOGGER.debug("Received all responses") if finished else _LOGGER.debug(
                "Waiting for {}".format(self._responses_waiting)
            )

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
                value = int(value, 16)

            if "RESULT" in map[elem]:
                if Msg.RESPONSE_GOOD not in value:
                    _LOGGER.error(f"Command Failed: {map[elem]}: {data}")
                else:
                    _LOGGER.debug(f"Command Succeeded: {map[elem]}: {data}")
            elif any(x in map[elem] for x in ["TSET", "TEMP", "PREBREWING_K"]):
                value = value / 10
            elif "FIRMWARE" in map[elem]:
                value = "%0.2f" % (value / 100)
            elif "SER_NUM" in map[elem]:
                value = "".join(
                    [chr(int(value[i : i + 2], 16)) for i in range(0, len(value), 2)]
                )
                value = value.partition("\0")[0]

            elif "AUTO_BITFIELD" in map[elem]:
                for item in AUTO_BITFIELD_MAP:
                    setting = ENABLED if value & 0x01 else DISABLED
                    self._current_status[AUTO_BITFIELD_MAP[item]] = setting
                    value = value >> 1
                continue
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
            _LOGGER.debug("got in here somehow")
            _LOGGER.debug("Sending {} with {}".format(msg.msg, data))

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
            _LOGGER.debug("Now waiting for {}".format(self._responses_waiting))

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
