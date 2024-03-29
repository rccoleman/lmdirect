import json, codecs, re, logging
from lmdirect.aescipher import AESCipher

_LOGGER = logging.getLogger(__name__)
_LOGGER.setLevel(logging.DEBUG)

PHONE_IP = "192.168.1.150"
LM_IP = "192.168.1.215"
CONFIG_FILE = "config.json"

try:
    with open(CONFIG_FILE) as config_file:
        data = json.load(config_file)

        key = data["key"]
        filename = data["filename"]
except Exception as err:
    print(err)
    exit(1)

cipher = AESCipher(key)

SOURCE_MAP = {PHONE_IP: "\nApp", LM_IP: "Machine"}


def checksum(buffer):
    """Compute check byte"""
    buffer = bytes(buffer, "utf-8")
    return "%0.2X" % (sum(buffer) % 256)


# Opening JSON file
with open(filename) as json_file:
    data = json.load(json_file)

    print(f"Parsing {filename}")

    for item in data:
        layers = item["_source"]["layers"]
        ip_src = layers["ip"]["ip.src"]

        try:
            packet_data = layers["data"]["data.data"].replace(":", "")
            decoded_data = codecs.decode(packet_data, "hex").decode("utf-8")
            _LOGGER.debug("Parsed: {}".format(decoded_data))
            ciphertext = re.sub("[@%]", "", decoded_data)

            plaintext = cipher.decrypt(ciphertext)
            _LOGGER.debug(plaintext)
            # plaintest = plaintext.partition(b'\0')[0].decode('utf-8')

            print("{}: {} ".format(SOURCE_MAP[ip_src], plaintext[0]), end="")

            for i in range(1, len(plaintext), 2):
                chars = plaintext[i : i + 2]
                print(chars, end=" ")

            print("")

        except KeyError:
            pass
