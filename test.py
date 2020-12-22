from lmdirect import LMDirect
import asyncio, json, sys, logging
from lmdirect.msgs import Msg, MSGS

from lmdirect.const import *

_LOGGER = logging.getLogger(__name__)
logging.basicConfig(
    format="%(asctime)s %(levelname)-8s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
_LOGGER.setLevel(logging.INFO)


class lmtest:
    def __init__(self):
        self._run = True

    def read_config(self):
        """Read key and machine IP from config file"""
        try:
            with open("config.json") as config_file:
                data = json.load(config_file)

        except Exception as err:
            print(err)
            exit(1)

        creds = {
            IP_ADDR: data["ip_addr"],
            CLIENT_ID: data["client_id"],
            CLIENT_SECRET: data["client_secret"],
            USERNAME: data["username"],
            PASSWORD: data["password"],
        }

        return creds

    def update(self, data, finished):
        _LOGGER.debug(
            "Updated: {}, {}".format(
                self.lmdirect.current_status, "Finished" if finished else "Waiting"
            )
        )

    async def poll_status_task(self):
        """Send periodic status requests"""
        _LOGGER.debug("Starting polling task")
        while self._run:
            await self.lmdirect.request_status()
            await asyncio.sleep(20)

    async def close(self):
        await self.lmdirect.close()

    async def connect(self):
        await self.lmdirect.connect()

    async def main(self):
        """Main execution loop"""
        loop = asyncio.get_event_loop()
        creds = await loop.run_in_executor(None, self.read_config)

        self.lmdirect = LMDirect(creds)
        self.lmdirect.register_callback(self.update)

        self._run = True

        self._poll_status_task = asyncio.get_event_loop().create_task(
            self.poll_status_task(), name="Request Status Task"
        )

        while True:
            try:
                print("\n1 = ON, 2 = OFF, 3 = Status, Other = quit: ")
                response = (
                    await loop.run_in_executor(None, sys.stdin.readline)
                ).rstrip()

                if response == "1":
                    await self.lmdirect.send_msg(MSGS[Msg.POWER], Msg.POWER_ON_DATA)
                elif response == "2":
                    await self.lmdirect.send_msg(MSGS[Msg.POWER], Msg.POWER_OFF_DATA)
                elif response == "3":
                    print(self.lmdirect.current_status)
                else:
                    break
            except KeyboardInterrupt:
                break

        self._run = False
        await asyncio.gather(*[self._poll_status_task])

        await self.lmdirect.close()


lm = lmtest()
asyncio.run(lm.main())
