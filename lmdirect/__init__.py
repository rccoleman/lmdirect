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
        await self.send_msg(MSGS[Msg.STATUS])
        await self.send_msg(MSGS[Msg.CONFIG])
        await self.send_msg(MSGS[Msg.AUTO_SCHED])

        """Also wait for current temp"""
        self._responses_waiting.append(MSGS[Msg.TEMP_REPORT].msg)

    async def send_msg(self, msg, data=None):
        await self._send_msg(msg, data)

    async def close(self):
        """Wait for the read task to exit"""
        await asyncio.gather(*[self._reaper_task])
        await self._close()