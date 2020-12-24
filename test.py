from lmdirect import LMDirect
import asyncio, json, sys, logging
from lmdirect.msgs import AUTO_BITFIELD_MAP

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

    def update(self, data, finished, **kwargs):
        _LOGGER.debug(
            "Updated: {}, {}".format(
                self.lmdirect.current_status, "Finished" if finished else "Waiting"
            )
        )

    async def raw_callback(self, key, data, **kwargs):
        self.lmdirect.deregister_raw_callback(key)
        print(f"Raw callback: {data}")

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
        # self.lmdirect.register_raw_callback(Msg.GET_AUTO_SCHED, self.raw_callback)

        self._run = True

        self._poll_status_task = asyncio.get_event_loop().create_task(
            self.poll_status_task(), name="Request Status Task"
        )

        while True:
            try:
                print(
                    "\n1 = Power, 2 = Status, 3 = Set Coffee Temp, 4 = Set Steam Temp, 5 = Set Prebrewing Enable, 6 = Set auto on/off enable, Other = quit: "
                )
                response = (
                    await loop.run_in_executor(None, sys.stdin.readline)
                ).rstrip()

                args = response.split()

                def check_args(num_args):
                    if len(args) >= num_args:
                        return True
                    else:
                        if len(args) > 0:
                            _LOGGER.error("Not enough arguments")
                        return False

                if not check_args(1):
                    break

                if args[0] == "1":
                    if check_args(1):
                        await self.lmdirect.set_power(args[1] == "on")
                elif args[0] == "2":
                    print(self.lmdirect.current_status)
                elif args[0] == "3":
                    if check_args(1):
                        await self.lmdirect.set_coffee_temp(args[1])
                elif args[0] == "4":
                    if check_args(1):
                        await self.lmdirect.set_steam_temp(args[1])
                elif args[0] == "5":
                    if check_args(1):
                        await self.lmdirect.send_prebrewing_enable(args[1] == "on")
                elif args[0] == "6":
                    if check_args(2):
                        await self.lmdirect.set_auto_on_off(
                            AUTO_BITFIELD_MAP[int(args[1])], args[2] == "on"
                        )
                else:
                    break
            except KeyboardInterrupt:
                break

        self._run = False
        await asyncio.gather(*[self._poll_status_task])

        await self.lmdirect.close()


lm = lmtest()
asyncio.run(lm.main())
