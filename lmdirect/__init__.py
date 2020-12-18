from .aescipher import AESCipher
from . import cmds as CMD
from .const import *

import asyncio
from functools import partial
import logging

_LOGGER = logging.getLogger(__name__)
_LOGGER.setLevel(logging.INFO)


class LMDirect:
    def __init__(self, key, ip_addr):
        """Init LMDirect"""
        self._run = False
        self._cipher = AESCipher(key)
        self._read_response_task = None
        self._current_status = {}
        self._callback = None
        self._responses_waiting = []
        self._ip_addr = ip_addr
        self._reader = self._writer = None

    def register_callback(self, callback):
        """Register callback for updates"""
        if callable(callback):
            self._callback = callback

    async def connect(self):
        """Conmnect to espresso machine"""
        TCP_PORT = 1774

        """Connect to the machine"""
        self._reader, self._writer = await asyncio.open_connection(
            self._ip_addr, TCP_PORT
        )

        self._run = True

        """Start listening for responses & sending status requests"""
        loop = asyncio.get_event_loop()
        self._read_response_task = loop.create_task(
            self.read_response_task(), name="Response Task"
        )

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

        while self._run:
            encoded_data = await self._reader.read(BUFFER_SIZE)
            if encoded_data is not None:
                loop = asyncio.get_event_loop()
                fn = partial(self._cipher.decrypt, encoded_data[1:-1])
                plaintext = await loop.run_in_executor(None, fn)
                finished_queue = await self.process_data(plaintext)

                if self._callback is not None:
                    self._callback(self._current_status, finished_queue)
                    if finished_queue:
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
                """No effect on response queue"""
                return False

        await self.populate_items(data, CMD.RESP_MAP[preamble])
        _LOGGER.debug(self._current_status)

        if preamble in self._responses_waiting:
            self._responses_waiting.remove(preamble)
            if not len(self._responses_waiting):
                _LOGGER.debug("Recevied all responses")
                return True

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

    async def request_status(self):
        """Request all status elements"""
        await self.send_cmd(CMD.CMD_D8_STATUS)
        await self.send_cmd(CMD.CMD_E9_CONFIG)
        await self.send_cmd(CMD.CMD_EB_AUTO_SCHED)

    async def send_cmd(self, cmd):
        """Send command to espresso machine"""

        """Connect if we don't have an active connection"""
        if self._writer is None:
            await self.connect()

        loop = asyncio.get_event_loop()
        fn = partial(self._cipher.encrypt, cmd)
        ciphertext = "@" + (await loop.run_in_executor(None, fn)).decode("utf-8") + "%"
        _LOGGER.debug(ciphertext)

        _LOGGER.debug("Before sending: {}".format(ciphertext))
        self._writer.write(bytes(ciphertext, "utf-8"))
        await self._writer.drain()

        """Remember that we're waiting for a response"""
        self._responses_waiting.append(CMD.CMD_RESP_MAP[cmd])
