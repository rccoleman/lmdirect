import base64
import logging
from math import ceil

from Crypto.Cipher import AES

_LOGGER = logging.getLogger(__name__)


class AESCipher:
    def __init__(self, key):
        self.key = key.encode("latin-1")

    def encrypt(self, plaintext):
        cipher = AES.new(self.key, AES.MODE_CBC, iv=bytearray(16))
        plaintext = bytes(plaintext, "utf-8") + bytearray(
            ceil(len(plaintext) / 16) * 16 - len(plaintext)
        )
        ciphertext = cipher.encrypt(plaintext)
        return base64.b64encode(ciphertext)

    def decrypt(self, b64text):
        ciphertext = base64.b64decode(b64text)
        cipher = AES.new(self.key, AES.MODE_CBC, iv=bytearray(16))
        return cipher.decrypt(ciphertext).decode().partition("\0")[0]
