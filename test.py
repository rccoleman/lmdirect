from lmdirect import LMDirect
from lmdirect.cmds import ON, OFF
import json
import logging

logging.basicConfig(level=logging.DEBUG)
_LOGGER = logging.getLogger(__name__)
_LOGGER.setLevel(logging.DEBUG)

try:
    with open("config.json") as config_file:
        data = json.load(config_file)

        key = data["key"]
        ip_addr = data["ip_addr"]
except Exception as err:
    print(err)
    exit(1)

lmdirect = LMDirect(key)
lmdirect.connect(ip_addr)

while True:
    try:
        response = input("1 = ON, 2 = OFF, 3 = Status, Other = quit: ")
        if response == "1":
            lmdirect.send_cmd(ON)
        elif response == "2":
            lmdirect.send_cmd(OFF)
        elif response == "3":
            print(lmdirect.current_status)
        else:
            break
    except KeyboardInterrupt:
        break

lmdirect.close()
exit(0)
