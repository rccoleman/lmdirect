from .aescipher import AESCipher
from . import cmds as CMD
from .const import *

from authlib.integrations.base_client.errors import OAuthError
from authlib.integrations.httpx_client import AsyncOAuth2Client
import asyncio, logging, time
from functools import partial
from datetime import timedelta, datetime


_LOGGER = logging.getLogger(__name__)
_LOGGER.setLevel(logging.DEBUG)


class LMDirect:
    def __init__(self, creds):
        """Init LMDirect"""
        self._cipher = None
        self._run = False
        self._read_response_task = None
        self._current_status = {}
        self._callback = None
        self._responses_waiting = []
        self._reader = self._writer = None
        self._keepalive = False

        self._creds = creds
        self._key = None

    def register_callback(self, callback):
        """Register callback for updates"""
        if callable(callback):
            self._callback = callback

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
            self._key = cust_info.json()["data"]["fleet"][0]["communicationKey"]
            self._serial_number = cust_info.json()["data"]["fleet"][0]["machine"][
                "serialNumber"
            ]
            self._machine_name = cust_info.json()["data"]["fleet"][0]["name"]
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

        self._run = True

        """Start listening for responses & sending status requests"""
        loop = asyncio.get_event_loop()
        self._read_response_task = loop.create_task(
            self.read_response_task(), name="Response Task"
        )

        _LOGGER.debug("Finished Connecting")
        return True

    async def close(self):
        """Stop listening for responses and close the socket"""
        self._run = False

        """Close the connection"""
        if self._writer is not None:
            self._writer.close()
        self._reader = self._writer = None

    async def read_response_task(self):
        """Start thread to receive responses"""
        BUFFER_SIZE = 1000

        _LOGGER.debug("Starting read task")

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

        await self.close()

    async def process_data(self, plaintext):
        """Process incoming packet"""

        """Separate the preamble from the data"""
        data = plaintext[1:]
        preamble = data[:8]

        _LOGGER.debug("Preamble={}, data={}".format(preamble, data))

        """If it's just a confirmation, skip it"""
        if preamble == CMD.RESP_WRITE_ON_OFF_PREAMBLE:
            if CMD.RESPONSE_GOOD not in data:
                cmd = list(CMD.CMD_RESP_MAP.keys())[
                    list(CMD.CMD_RESP_MAP.values()).index(preamble)
                ]
                _LOGGER.error("Command Failed: {} {}".format(cmd, data))
        else:
            await self.populate_items(data, CMD.RESP_MAP[preamble])

        if preamble in self._responses_waiting:
            self._responses_waiting.remove(preamble)
            if not len(self._responses_waiting):
                _LOGGER.debug("Recevied all responses")
                return True
            else:
                _LOGGER.debug("Waiting for {}".format(self._responses_waiting))

    async def populate_items(self, data, map):
        for elem in map:
            index = elem.index * 2
            size = elem.size * 2

            value = int(data[index : index + size], 16)
            if any(x in map[elem] for x in ["TSET", "TEMP", "PREBREWING_K"]):
                value = value / 10
            elif "AUTO_BITFIELD" in map[elem]:
                for i in range(0, 7):
                    setting = ENABLED if value & 0x01 else DISABLED
                    self._current_status[CMD.AUTO_BITFIELD_MAP[i]] = setting
                    value = value >> 1
                continue
            self._current_status[map[elem]] = value

    @property
    def current_status(self):
        """Return a dict of all the properties that have been received"""
        return self._current_status

    @property
    def machine_name(self):
        """Return the name of the machine"""
        return self._machine_name

    @property
    def serial_number(self):
        """Return serial number"""
        return self._serial_number

    async def request_status(self):
        """Request all status elements"""
        await self.send_cmd(CMD.CMD_D8_STATUS)
        await self.send_cmd(CMD.CMD_E9_CONFIG)
        await self.send_cmd(CMD.CMD_EB_AUTO_SCHED)

        """Also wait for current temp"""
        self._responses_waiting.append(CMD.RESP_SHORT_PREAMBLE)

    async def send_cmd(self, cmd):
        """Send command to espresso machine"""

        """Connect if we don't have an active connection"""
        if self._writer is None:
            if not await self.connect():
                _LOGGER.debug("Connectin failed, not sending {}".format(cmd))
                return

        _LOGGER.debug("Sending command: {}".format(cmd))

        loop = asyncio.get_event_loop()
        fn = partial(self._cipher.encrypt, cmd)
        ciphertext = "@" + (await loop.run_in_executor(None, fn)).decode("utf-8") + "%"

        self._writer.write(bytes(ciphertext, "utf-8"))
        await self._writer.drain()

        """Remember that we're waiting for a response"""
        self._responses_waiting.append(CMD.CMD_RESP_MAP[cmd])

        """Note when the command was sent"""
        self._start_time = datetime.now()


class AuthFail(BaseException):
    """Error to indicate there is invalid auth."""