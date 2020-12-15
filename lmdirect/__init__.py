from .aescipher import AESCipher
from . import cmds as CMD
from .const import *

import socket, select
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
        self.response_thread = None
        self.status_thread = None
        self.current_status = {}
        self.is_on = None

    def connect(self, addr):
        """Conmnect to espresso machine"""
        TCP_PORT = 1774

        self.s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.s.connect((addr, TCP_PORT))

        """Start listening for responses"""
        self.response_thread = Thread(target=self.response, name="Response")
        self.response_thread.start()

        """Start sending status requests"""
        self.status_thread = Thread(target=self.status, name="Status")
        self.status_thread.start()

    def close(self):
        """Stop listening for responses and close the socket"""
        self.run = False
        threads = [self.response_thread, self.status_thread]

        [t.join() for t in threads if t is not None]

        self.s.shutdown(socket.SHUT_WR)
        self.s.close()

    def response(self):
        """Start thread to receive responses"""
        BUFFER_SIZE = 1000

        while self.run:
            reading = [self.s]
            writing = []
            exceptions = []
            select.select(reading, writing, exceptions, 1)
            if self.s in reading:
                encoded_data = self.s.recv(BUFFER_SIZE)
                _LOGGER.debug(encoded_data)
                if encoded_data is not None:
                    plaintext = self.cipher.decrypt(encoded_data[1:-1])
                    self.process_data(plaintext)

    def process_data(self, plaintext):
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

        if preamble == CMD.D8_PREAMBLE:
            _LOGGER.debug("D8 status")
            self.populate_items(data, CMD.D8_MAP)

            new_state = self.current_status["POWER"] == 1
            if new_state is not self.is_on:
                self.is_on = new_state

                _LOGGER.info("Device is {}".format("ON" if self.is_on else "OFF"))
        elif preamble == CMD.E9_PREAMBLE:
            _LOGGER.debug("E9 status")
            self.populate_items(data, CMD.E9_MAP)
        elif preamble == CMD.SHORT_PREAMBLE:
            _LOGGER.debug("Short status")
            self.populate_items(data, CMD.SHORT_MAP)
        elif preamble == CMD.EB_PREAMBLE:
            _LOGGER.debug("EB auto schedule")
            self.populate_items(data, CMD.EB_MAP)

        _LOGGER.debug(self.current_status)

    def populate_items(self, data, map):
        for elem in map:
            index = elem.index * 2
            size = elem.size * 2

            value = int(data[index : index + size], 16)
            if any(x in map[elem] for x in ["TEMP", "PREBREWING_K"]):
                value = value / 10
            elif "UNITS" in map[elem]:
                print(data)
                print("{}, {}".format(value, chr(value)))
                value = u"\xb0F" if chr(value) == "f" else u"\xb0C"
            elif "AUTO_BITFIELD" in map[elem]:
                for i in range(0, 7):
                    setting = ENABLED if value & 0x01 else DISABLED
                    self.current_status[CMD.AUTO_BITFIELD_MAP[i]] = setting
                    value = value >> 1
                continue
            self.current_status[map[elem]] = value

    def status(self):
        """Send periodic status requests"""
        while self.run:
            self.send_cmd(CMD.STATUS)
            self.send_cmd(CMD.CONFIG)
            self.send_cmd(CMD.AUTO_SCHED)
            sleep(5)

    def send_cmd(self, cmd):
        """Send command to espresso machine"""
        ciphertext = "@" + self.cipher.encrypt(cmd).decode("utf-8") + "%"
        _LOGGER.debug(ciphertext)

        _LOGGER.debug("Before sending: {}".format(ciphertext))
        self.s.send(bytes(ciphertext, "utf-8"))
        _LOGGER.debug("After sending")
