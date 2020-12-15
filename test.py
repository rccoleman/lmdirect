import asyncio
from lmdirect import LMDirect
from lmdirect.cmds import ON, OFF
import json, sys, logging

logging.basicConfig(level=logging.DEBUG)
_LOGGER = logging.getLogger(__name__)
_LOGGER.setLevel(logging.DEBUG)


async def main():
    try:
        with open("config.json") as config_file:
            data = json.load(config_file)

            key = data["key"]
            ip_addr = data["ip_addr"]
    except Exception as err:
        print(err)
        exit(1)

    lmdirect = LMDirect(key)
    await lmdirect.connect(ip_addr)

    loop = asyncio.get_running_loop()
    reader = asyncio.StreamReader(loop=loop)
    reader_protocol = asyncio.StreamReaderProtocol(reader)
    await loop.connect_read_pipe(lambda: reader_protocol, sys.stdin)

    while True:
        try:
            print("\n1 = ON, 2 = OFF, 3 = Status, Other = quit: ")
            response = (await reader.readline())[:-1].decode("utf-8")

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
    exit(0)


asyncio.run(main())
