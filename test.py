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
            HOST: data["host"],
            PORT: data["port"],
            CLIENT_ID: data["client_id"],
            CLIENT_SECRET: data["client_secret"],
            USERNAME: data["username"],
            PASSWORD: data["password"],
            KEY: data.get("key", None),
        }

        return creds

    def update(self, **kwargs):
        _LOGGER.debug("Updated: {}".format(self.lmdirect.current_status))

    async def raw_callback(self, key, data):
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
                    "\n1=Power <on/off>, 2=Status, 3=Coffee Temp <temp>, 4=Steam Temp <temp>, 5=PB <on/off>, 6=Auto on/off <0=global or day> <on/off>, 7=Dose <key> <sec>, 8=Tea Dose <sec>, 8=PB times <key> <on off>: "
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
                    if check_args(2):
                        await self.lmdirect.set_power(args[1] == "on")
                elif args[0] == "2":
                    print(self.lmdirect.current_status)
                elif args[0] == "3":
                    if check_args(2):
                        await self.lmdirect.set_coffee_temp(args[1])
                elif args[0] == "4":
                    if check_args(2):
                        await self.lmdirect.set_steam_temp(args[1])
                elif args[0] == "5":
                    if check_args(2):
                        await self.lmdirect.set_prebrewing_enable(args[1] == "on")
                elif args[0] == "6":
                    if check_args(2):
                        await self.lmdirect.set_auto_on_off(
                            AUTO_BITFIELD_MAP[int(args[1])], args[2] == "on"
                        )
                elif args[0] == "7":
                    if check_args(2):
                        await self.lmdirect.set_dose(args[1], args[2])
                elif args[0] == "8":
                    if check_args(2):
                        await self.lmdirect.set_dose_tea(args[1])
                elif args[0] == "9":
                    if check_args(3):
                        await self.lmdirect.set_prebrew_times(args[1], args[2], args[3])
            except KeyboardInterrupt:
                break

        self._run = False

        self._poll_status_task.cancel()

        try:
            await asyncio.gather(self._poll_status_task)
        except asyncio.CancelledError:
            pass

        await self.lmdirect.close()


lm = lmtest()
asyncio.run(lm.main())
