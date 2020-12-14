import json, codecs, re, logging, sys
from lmdirect.aescipher import AESCipher

_LOGGER = logging.getLogger(__name__)
_LOGGER.setLevel(logging.DEBUG)

if len(sys.argv) == 2:
    key = sys.argv[1]
else:
    print(f"{sys.argv[0]}: <32-byte> Key>")
    exit(1)

cipher = AESCipher(key)

SOURCE_MAP = {"192.168.1.150": "\nApp", "192.168.1.215": "Machine"}

# Opening JSON file
with open("version.json") as json_file:
    data = json.load(json_file)

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
                print(
                    codecs.decode(chars, "hex").decode("utf-8")
                    if chars.isdigit() and 30 <= int(chars) <= 39
                    else chars,
                    end=" ",
                )

            print("")

        except KeyError:
            pass
