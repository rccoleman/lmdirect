from .aescipher import AESCipher
from . import cmds as CMD
from .const import *

import asyncio
from functools import partial
import logging

_LOGGER = logging.getLogger(__name__)
_LOGGER.setLevel(logging.INFO)


class LMDirect:
    def __init__(self, key):
        """Init LMDirect"""
        self._run = True
        self._cipher = AESCipher(key)
        self._read_response_task = None
        self._poll_status_task = None
        self._current_status = {}

    async def connect(self, addr):
        """Conmnect to espresso machine"""
        TCP_PORT = 1774

        """Connect to the machine"""
        self.reader, self.writer = await asyncio.open_connection(addr, TCP_PORT)

        loop = asyncio.get_event_loop()

        """Start listening for responses & sending status requests"""
        self._read_response_task = loop.create_task(
            self.read_response_task(), name="Response Task"
        )

    async def close(self):
        """Stop listening for responses and close the socket"""
        self._run = False
        tasks = [self._read_response_task]

        if self._poll_status_task:
            tasks.append(self._poll_status_task)

        await asyncio.gather(*tasks)

        """Close the connection"""
        self.writer.close()

    async def read_response_task(self):
        """Start thread to receive responses"""
        BUFFER_SIZE = 1000

        while self._run:
            encoded_data = await self.reader.read(BUFFER_SIZE)

            _LOGGER.debug(encoded_data)
            if encoded_data is not None:
                loop = asyncio.get_event_loop()
                fn = partial(self._cipher.decrypt, encoded_data[1:-1])
                plaintext = await loop.run_in_executor(None, fn)
                await self.process_data(plaintext)

    async def process_data(self, plaintext):
        """Process incoming packet"""

        """Separate the preamble from the data"""
        data = plaintext[1:]
        preamble = data[:8]

        _LOGGER.debug("Preamble={}, data={}".format(preamble, data))

        """If it's just a confirmation, skip it"""
        if preamble == CMD.WRITE_ON_OFF_PREAMBLE:
            _LOGGER.info(
                "Short status: {}".format(
                    "Good" if CMD.RESPONSE_GOOD in data else "Bad"
                )
            )
            return

        if any(preamble in x for x in CMD.PREAMBLES):
            await self.populate_items(data, CMD.RESP_MAP[preamble])
            _LOGGER.debug(self._current_status)

    async def populate_items(self, data, map):
        for elem in map:
            index = elem.index * 2
            size = elem.size * 2

            value = int(data[index : index + size], 16)
            if any(x in map[elem] for x in ["TEMP", "PREBREWING_K"]):
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

    async def create_polling_task(self):
        """Start a polling task"""
        self._poll_status_task = asyncio.get_event_loop().create_task(
            self.poll_status_task(), name="Request Status Task"
        )

    async def poll_status_task(self):
        """Send periodic status requests"""
        while self._run:
            await self.request_status()
            await asyncio.sleep(5)

    async def request_status(self):
        await self.send_cmd(CMD.STATUS)
        await self.send_cmd(CMD.CONFIG)
        await self.send_cmd(CMD.AUTO_SCHED)

    async def send_cmd(self, cmd):
        """Send command to espresso machine"""
        loop = asyncio.get_event_loop()
        fn = partial(self._cipher.encrypt, cmd)
        ciphertext = "@" + (await loop.run_in_executor(None, fn)).decode("utf-8") + "%"
        _LOGGER.debug(ciphertext)

        _LOGGER.debug("Before sending: {}".format(ciphertext))
        self.writer.write(bytes(ciphertext, "utf-8"))
        await self.writer.drain()
