"""lmdierct"""
from .connection import Connection
from .msgs import Msg, MSGS
import asyncio

import logging

_LOGGER = logging.getLogger(__name__)


class LMDirect(Connection):
    def __init__(self, creds):
        super().__init__(creds)

    @property
    def current_status(self):
        """Return a dict of all the properties that have been received"""
        return self._current_status

    @property
    def machine_name(self):
        """Return the name of the machine"""
        return self._machine_name

    @property
    def serial_number(self):
        """Return serial number"""
        return self._serial_number

    @property
    def model_name(self):
        """Return model name"""
        return self._model_name

    def register_callback(self, callback):
        """Register callback for updates"""
        if callable(callback):
            self._callback = callback

    async def request_status(self):
        """Request all status elements"""

        _LOGGER.debug("Requesting status")
        await self.send_msg(MSGS[Msg.GET_STATUS])
        await self.send_msg(MSGS[Msg.GET_CONFIG])
        await self.send_msg(MSGS[Msg.GET_AUTO_SCHED])
        # await self.send_msg(MSGS[Msg.GET_SER_NUM])
        await self.send_msg(MSGS[Msg.GET_DATETIME])

        """Also wait for current temp"""
        self._responses_waiting.append(MSGS[Msg.GET_TEMP_REPORT].msg)

    async def set_power(self, power):
        """Send power on or power off commands"""
        await self._send_msg(MSGS[Msg.SET_POWER], value=0x01 if power else 0x00, size=1)

    async def set_coffee_temp(self, temp):
        """Set the coffee boiler temp in Celcius"""
        await self._send_msg(MSGS[Msg.SET_COFFEE_TEMP], value=int(temp * 10), size=2)

    async def set_steam_temp(self, temp):
        """Set the steam boiler temp in Celcius"""
        await self._send_msg(MSGS[Msg.SET_STEAM_TEMP], value=int(temp * 10), size=2)

    async def set_prebrewing_enable(self, enable):
        """Turn prebrewing on or off"""
        await self._send_msg(
            MSGS[Msg.SET_PREBREWING_ENABLE], value=0x01 if enable else 0x00, size=1
        )

    async def send_msg(self, msg, data=None, size=0):
        """Send a message"""
        await self._send_msg(msg, data, size)

    async def close(self):
        """Wait for the read task to exit"""
        await asyncio.gather(*[self._reaper_task])
        await self._close()
