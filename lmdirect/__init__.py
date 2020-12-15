from .aescipher import AESCipher
from . import cmds as CMD
from .const import *

import asyncio
from threading import Thread
from time import sleep

import logging


_LOGGER = logging.getLogger(__name__)
_LOGGER.setLevel(logging.INFO)


class LMDirect:
    def __init__(self, key):
        """Init LMDirect"""
        self.run = True
        self.cipher = AESCipher(key)
        self.response_task = None
        self.status_task = None
        self.current_status = {}

    async def connect(self, addr):
        """Conmnect to espresso machine"""
        TCP_PORT = 1774

        self.reader, self.writer = await asyncio.open_connection(addr, TCP_PORT)

        """Start listening for responses"""
        self.response_task = asyncio.create_task(self.response())

        """Start sending status requests"""
        self.status_task = asyncio.create_task(self.status())

    async def close(self):
        """Stop listening for responses and close the socket"""
        self.run = False

        await asyncio.gather(*[self.response_task, self.status_task])

        """Close the connection"""
        self.writer.close()

    async def response(self):
        """Start thread to receive responses"""
        BUFFER_SIZE = 1000

        while self.run:
            encoded_data = await self.reader.read(BUFFER_SIZE)
            _LOGGER.debug(encoded_data)
            if encoded_data is not None:
                plaintext = self.cipher.decrypt(encoded_data[1:-1])
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
            _LOGGER.debug(self.current_status)

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
                    self.current_status[CMD.AUTO_BITFIELD_MAP[i]] = setting
                    value = value >> 1
                continue
            self.current_status[map[elem]] = value

    async def status(self):
        """Send periodic status requests"""
        while self.run:
            await self.send_cmd(CMD.STATUS)
            await self.send_cmd(CMD.CONFIG)
            await self.send_cmd(CMD.AUTO_SCHED)
            await asyncio.sleep(5)

    async def send_cmd(self, cmd):
        """Send command to espresso machine"""
        ciphertext = "@" + self.cipher.encrypt(cmd).decode("utf-8") + "%"
        _LOGGER.debug(ciphertext)

        _LOGGER.debug("Before sending: {}".format(ciphertext))
        self.writer.write(bytes(ciphertext, "utf-8"))
        await self.writer.drain()
