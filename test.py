import asyncio
from lmdirect import LMDirect
import json
import sys
import logging
from lmdirect.cmds import ON, OFF

logging.basicConfig(level=logging.DEBUG)
_LOGGER = logging.getLogger(__name__)
_LOGGER.setLevel(logging.DEBUG)


def read_config():
    """Read key and machine IP from config file"""
    try:
        with open("config.json") as config_file:
            data = json.load(config_file)

            key = data["key"]
            ip_addr = data["ip_addr"]
    except Exception as err:
        print(err)
        exit(1)

    return key, ip_addr


async def main():
    """Main execution loop"""
    loop = asyncio.get_event_loop()
    key, ip_addr = await loop.run_in_executor(None, read_config)

    lmdirect = LMDirect(key)
    await lmdirect.connect(ip_addr)

    while True:
        try:
            print("\n1 = ON, 2 = OFF, 3 = Status, Other = quit: ")
            response = (await loop.run_in_executor(None, sys.stdin.readline)).rstrip()

            if response == "1":
                await lmdirect.send_cmd(ON)
            elif response == "2":
                await lmdirect.send_cmd(OFF)
            elif response == "3":
                print(lmdirect.current_status)
            else:
                break
        except KeyboardInterrupt:
            break

    await lmdirect.close()

asyncio.run(main())
