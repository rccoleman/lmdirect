"""lmdirect connection class"""
from .const import *
from .aescipher import AESCipher

from authlib.integrations.base_client.errors import OAuthError
from authlib.integrations.httpx_client import AsyncOAuth2Client
import asyncio, logging
from datetime import timedelta, datetime
from functools import partial

_LOGGER = logging.getLogger(__name__)

from .msgs import Msg, MSGS, AUTO_BITFIELD_MAP, Elem
from .const import *
import logging


class Connection:
    def __init__(self, creds):
        """Init LMDirect"""
        self._reader = self._writer = None
        self._read_response_task = None
        self._reaper_task = None
        self._current_status = {}
        self._responses_waiting = []
        self._run = False
        self._callback = None
        self._cipher = None
        self._creds = creds
        self._key = None
        self._start_time = None

    async def retrieve_key(self):
        """Machine data inialization"""
        client = AsyncOAuth2Client(
            client_id=self._creds[CLIENT_ID],
            client_secret=self._creds[CLIENT_SECRET],
            token_endpoint=TOKEN_URL,
        )

        headers = {
            "client_id": self._creds[CLIENT_ID],
            "client_secret": self._creds[CLIENT_SECRET],
        }

        try:
            await client.fetch_token(
                url=TOKEN_URL,
                username=self._creds[USERNAME],
                password=self._creds[PASSWORD],
                headers=headers,
            )
        except OAuthError:
            await client.aclose()
            raise AuthFail

        except Exception as err:
            print("Caught: {}, {}".format(type(err), err))
            await self.close()
            raise AuthFail

        cust_info = await client.get(CUSTOMER_URL)
        if cust_info is not None:
            fleet = cust_info.json()["data"]["fleet"][0]
            self._key = fleet["communicationKey"]
            self._serial_number = fleet["machine"]["serialNumber"]
            self._machine_name = fleet["name"]
            self._model_name = fleet["machine"]["model"]["name"]
            self._cipher = AESCipher(self._key)

        """Done with the cloud API"""
        await client.aclose()

    async def connect(self):
        """Conmnect to espresso machine"""

        if not self._key:
            try:
                await self.retrieve_key()
            except Exception as err:
                _LOGGER.debug("Exception retrieving key: {}".format(err))
                raise

        TCP_PORT = 1774

        """Connect to the machine"""
        try:
            self._reader, self._writer = await asyncio.wait_for(
                asyncio.open_connection(self._creds[IP_ADDR], TCP_PORT), timeout=3
            )
        except asyncio.TimeoutError:
            _LOGGER.warning("Connection Timeout, skipping")
            return False

        except Exception as err:
            _LOGGER.error("Cannot connect to machine: {}".format(err))
            return False

        """Start listening for responses & sending status requests"""
        self._run = True
        loop = asyncio.get_event_loop()
        self._read_response_task = loop.create_task(
            self.read_response_task(), name="Response Task"
        )

        """Reap the results and any any exceptions"""
        self._reaper_task = loop.create_task(self.reaper(), name="Reaper")

        _LOGGER.debug("Finished Connecting")
        return True

    async def start_read_task(self):
        self._run = True

        """Start listening for responses & sending status requests"""
        loop = asyncio.get_event_loop()
        self._read_response_task = loop.create_task(
            self.read_response_task(), name="Response Task"
        )

        """Reap the results and any any exceptions"""
        loop.create_task(self.reaper(), name="Reaper")

    async def _close(self):
        """Close the connection"""
        if self._writer is not None:
            self._writer.close()
        self._reader = self._writer = None
        _LOGGER.debug("Finished closing")

    async def reaper(self):
        _LOGGER.debug("Starting reaper")
        try:
            await asyncio.gather(*[self._read_response_task])
        except Exception as err:
            _LOGGER.error(f"Exception in read_response_task: {err}")

        await self._close()

        self._read_response_task = None

        _LOGGER.debug("Finished reaping")

    async def read_response_task(self):
        """Start thread to receive responses"""
        BUFFER_SIZE = 1000

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

                finished_queue = await self.process_data(plaintext)

                """Call the callback"""
                if self._callback is not None:
                    self._callback(self._current_status, finished_queue)

                """Exit if we've been reading longer than 5s"""
                if datetime.now() > self._start_time + timedelta(seconds=5):
                    _LOGGER.debug("Exiting loop: {}".format(self._responses_waiting))

                    """Flush the wait list"""
                    self._responses_waiting = []
                    break

    async def process_data(self, plaintext):
        """Process incoming packet"""

        """Separate the mesg from the data"""
        raw_data = plaintext[1:]
        msg = raw_data[:8]
        data = raw_data[8:]
        finished = not len(self._responses_waiting)

        _LOGGER.debug("Message={}, Data={}".format(msg, data))

        msg_id = next((x for x in MSGS if MSGS[x].msg == msg), None)

        if msg_id is None:
            _LOGGER.error("Unexpected response: {}".format(plaintext))
            return finished
        else:
            cur_msg = MSGS[msg_id]

        if cur_msg.map is not None:
            await self.populate_items(data, cur_msg)

        if cur_msg.msg in self._responses_waiting:
            self._responses_waiting.remove(cur_msg.msg)
            finished = not len(self._responses_waiting)
            if finished:
                _LOGGER.debug("Received all responses")
            else:
                _LOGGER.debug("Waiting for {}".format(self._responses_waiting))

        return finished

    async def populate_items(self, data, cur_msg):
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
                for i in range(0, 7):
                    setting = ENABLED if value & 0x01 else DISABLED
                    self._current_status[AUTO_BITFIELD_MAP[i]] = setting
                    value = value >> 1
                continue
            self._current_status[map[elem]] = value

    def checksum(self, buffer):
        """Compute check byte"""
        buffer = bytes(buffer, "utf-8")
        return "%0.2X" % (sum(buffer) % 256)

    async def _send_msg(self, msg, data=None):
        """Send command to espresso machine"""

        _LOGGER.debug("Sending {} with {}".format(msg.msg, data))

        """Connect if we don't have an active connection"""
        if self._writer is None:
            if not await self.connect():
                _LOGGER.debug("Connectin failed, not sending {}".format(msg))
                return

        """Add read/write and check bytes"""
        plaintext = msg.msg_type + msg.msg

        if data is not None:
            plaintext += data

        plaintext += self.checksum(plaintext)

        loop = asyncio.get_event_loop()
        fn = partial(self._cipher.encrypt, plaintext)
        ciphertext = "@" + (await loop.run_in_executor(None, fn)).decode("utf-8") + "%"

        self._writer.write(bytes(ciphertext, "utf-8"))
        await self._writer.drain()

        """Remember that we're waiting for a response"""
        self._responses_waiting.append(msg.msg)
        _LOGGER.debug("Now waiting for {}".format(self._responses_waiting))

        """Note when the command was sent"""
        self._start_time = datetime.now()


class AuthFail(BaseException):
    """Error to indicate there is invalid auth."""