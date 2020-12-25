"""lmdierct"""
from lmdirect.const import DISABLED, ENABLED
from .connection import Connection
from .msgs import (
    DOSE_TEA,
    GLOBAL_AUTO,
    TYPE_AUTO_ON_OFF,
    TYPE_COFFEE_TEMP,
    TYPE_MAIN,
    TYPE_PREBREW,
    TYPE_STEAM_TEMP,
    Msg,
    MSGS,
    AUTO_SCHED_MAP,
    AUTO_BITFIELD_MAP,
    DOSE_K1,
    TEMP_COFFEE,
    TEMP_STEAM,
    TON_PREBREWING_K1,
    TOFF_PREBREWING_K1,
)
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
            self._callback_list.append(callback)

    def register_raw_callback(self, msg, callback, **kwargs):
        """Register a callback for the raw response to a command"""
        if callable(callback):
            self._raw_callback_list.append((msg, callback))

    def deregister_raw_callback(self, key):
        """Register a callback for the raw response to a command"""

        """The key is a tuple comprised of (msg, callback)"""
        if key in self._raw_callback_list:
            self._raw_callback_list.remove(key)

    async def request_status(self):
        """Request all status elements"""

        _LOGGER.debug("Requesting status")
        await self._send_msg(Msg.GET_STATUS)
        await self._send_msg(Msg.GET_CONFIG)
        await self._send_msg(Msg.GET_AUTO_SCHED)
        # await self._send_msg(Msg.GET_SER_NUM)
        await self._send_msg(Msg.GET_DATETIME)

        """Also wait for current temp"""
        self._responses_waiting.append(MSGS[Msg.GET_TEMP_REPORT].msg)

    async def send_msg(self, msg_id, key=None, data=None):
        """Send a message"""
        await self._send_msg(msg_id, key=key, data=data)

    async def close(self):
        """Wait for the read task to exit"""
        await asyncio.gather(*[self._reaper_task])
        await self._close()

    def call_callbacks(self, **kwargs):
        """Call all callbacks to refresh data"""
        self._call_callbacks(**kwargs)

    """Utils"""

    def convert_to_ascii(self, value, size):
        """Convert an integer value to ASCII-encoded hex"""
        return ("%0" + str(size * 2) + "X") % value

    def findkey(self, find_value, dict):
        """Find a key from the value in a dict"""
        return next(
            (key for key, value in dict.items() if value == find_value),
            None,
        )

    """Services"""

    async def set_power(self, power):
        """Send power on or power off commands"""
        value = self.convert_to_ascii(0x01 if power else 0x00, size=1)
        await self._send_msg(Msg.SET_POWER, value)
        await self._send_msg(Msg.GET_CONFIG)
        self._call_callbacks(entity_type=TYPE_MAIN)

    async def set_auto_on_off(self, field_name, value):
        """Configure auto on/off"""

        async def auto_on_off_callback(key, data):
            """Callback for the raw sequence"""

            """We don't need to continue looking for it"""
            self.deregister_raw_callback(key)
            _LOGGER.debug(f"Received raw callback: {data}")

            try:
                """Find the bit"""
                elem = self.findkey("AUTO_BITFIELD", AUTO_SCHED_MAP)

                """The strings are ASCII-encoded hex, so each value takes 2 bytes"""
                index = elem.index * 2
                size = elem.size * 2

                """Extract value for this field"""
                orig_value = int(data[index : index + size], 16)
                bitmask = 0x01 << self.findkey(field_name, AUTO_BITFIELD_MAP)
                new_value = self.convert_to_ascii(
                    orig_value | bitmask if value else orig_value & ~bitmask, 1
                )

                buf_to_send = data[:index] + new_value + data[index + size :]

                self._current_status[field_name] = ENABLED if value else DISABLED

                await self._send_msg(Msg.SET_AUTO_SCHED, buf_to_send)
                await self._send_msg(Msg.GET_AUTO_SCHED)
                self._call_callbacks(entity_type=TYPE_AUTO_ON_OFF)
            except Exception as err:
                _LOGGER.debug(f"Caught exception: {err}")

        self.register_raw_callback(Msg.GET_AUTO_SCHED, auto_on_off_callback)
        await self._send_msg(Msg.GET_AUTO_SCHED)

    async def set_auto_on_off_global(self, value):
        """Set global auto on/off"""
        await self.set_auto_on_off(GLOBAL_AUTO, value)

    async def set_auto_on_off_hours(self, field_name, hour_on, hour_off):
        """Configure auto on/off"""

        async def auto_on_off_callback(key, data):
            """Callback for the raw sequence"""

            """We don't need to continue looking for it"""
            self.deregister_raw_callback(key)
            _LOGGER.debug(f"Received raw callback: {data}")

            try:
                """Find the "on" element"""
                elem = self.findkey(field_name.replace("AUTO", "ON"), AUTO_SCHED_MAP)

                """The strings are ASCII-encoded hex, so each value takes 2 bytes and there 2 of them"""
                index = elem.index * 2
                size = elem.size * 4

                """Construct the new "on" and "off" values"""
                buf_to_send = (
                    data[:index]
                    + self.convert_to_ascii(hour_on, 1)
                    + self.convert_to_ascii(hour_off, 1)
                    + data[index + size :]
                )

                self._current_status[field_name.replace("AUTO", "ON")] = hour_on
                self._current_status[field_name.replace("AUTO", "OFF")] = hour_off

                _LOGGER.info(f"Orig data: {data}")
                _LOGGER.info(f"New data:  {buf_to_send}")
                await self._send_msg(Msg.SET_AUTO_SCHED, buf_to_send)
                await self._send_msg(Msg.GET_AUTO_SCHED)
                self._call_callbacks(entity_type=TYPE_AUTO_ON_OFF)
            except Exception as err:
                _LOGGER.debug(f"Caught exception: {err}")

        self.register_raw_callback(Msg.GET_AUTO_SCHED, auto_on_off_callback)
        await self._send_msg(Msg.GET_AUTO_SCHED)

    async def set_dose(self, key, pulses):
        """Set the coffee boiler temp in Celcius"""

        if isinstance(pulses, str):
            pulses = int(pulses)

        if isinstance(key, str):
            key = int(key)

        """Validate input"""
        if not (1 <= pulses <= 1000 and 1 <= key <= 5):
            _LOGGER.error(f"Invalid values pulses:{pulses} key:{key}")
            return False

        self._current_status[DOSE_K1.replace("1", str(key))] = pulses

        data = self.convert_to_ascii(pulses, size=2)
        key = self.convert_to_ascii(Msg.DOSE_KEY_BASE + (key - 1) * 2, size=1)
        await self._send_msg(Msg.SET_DOSE, key=key, data=data)
        await self._send_msg(Msg.GET_CONFIG)
        self._call_callbacks(entity_type=TYPE_MAIN)

    async def set_dose_tea(self, seconds):
        """Set the coffee boiler temp in Celcius"""

        if isinstance(seconds, str):
            seconds = int(seconds)

        """Validate input"""
        if not (1 <= seconds <= 30):
            _LOGGER.error(f"Invalid values seconds:{seconds}")
            return False

        self._current_status[DOSE_TEA] = seconds

        data = self.convert_to_ascii(seconds, size=1)
        await self._send_msg(Msg.SET_DOSE_TEA, data=data)
        await self._send_msg(Msg.GET_CONFIG)
        self._call_callbacks(entity_type=TYPE_MAIN)

    async def set_prebrew_times(self, key, time_on, time_off):
        """Set the coffee boiler temp in Celcius"""

        if isinstance(time_on, str):
            time_on = float(time_on)

        if isinstance(time_off, str):
            off_time = float(time_off)

        if isinstance(key, str):
            key = int(key)

        """Validate input"""
        if not (0 <= time_on <= 5.9 and 0 <= time_off <= 5.9 and 1 <= key <= 4):
            _LOGGER.error(
                f"Invalid values time_on:{time_on} off_time:{time_off} key:{key}"
            )
            return False

        self._current_status[TON_PREBREWING_K1.replace("1", str(key))] = time_on
        self._current_status[TOFF_PREBREWING_K1.replace("1", str(key))] = time_off

        """set "on" time"""
        key_on = self.convert_to_ascii(Msg.PREBREW_ON_BASE + (key - 1), size=1)
        data = self.convert_to_ascii(int(time_on * 10), size=1)
        await self._send_msg(Msg.SET_PB_ON, key=key_on, data=data)

        """set "off" time"""
        key_off = self.convert_to_ascii(Msg.PREBREW_OFF_BASE + (key - 1), size=1)
        data = self.convert_to_ascii(int(time_off * 10), size=1)
        await self._send_msg(Msg.SET_PB_OFF, key=key_off, data=data)
        await self._send_msg(Msg.GET_CONFIG)
        self._call_callbacks(entity_type=TYPE_PREBREW)

    async def set_coffee_temp(self, temp):
        """Set the coffee boiler temp in Celcius"""

        if isinstance(temp, str):
            temp = float(temp)

        temp = round(temp, 1)

        self._current_status[TEMP_COFFEE] = temp

        data = self.convert_to_ascii(int(temp * 10), size=2)
        await self._send_msg(Msg.SET_COFFEE_TEMP, data=data)
        await self._send_msg(Msg.GET_TEMP_REPORT, data=data)
        self._call_callbacks(entity_type=TYPE_COFFEE_TEMP)

    async def set_steam_temp(self, temp):
        """Set the steam boiler temp in Celcius"""

        if isinstance(temp, str):
            temp = float(temp)

        temp = round(temp, 1)

        self._current_status[TEMP_STEAM] = temp

        data = self.convert_to_ascii(int(temp * 10), size=2)
        await self._send_msg(Msg.SET_STEAM_TEMP, data=data)
        await self._send_msg(Msg.GET_TEMP_REPORT, data=data)
        self._call_callbacks(entity_type=TYPE_STEAM_TEMP)

    async def set_prebrewing_enable(self, enable):
        """Turn prebrewing on or off"""
        data = self.convert_to_ascii(0x01 if enable else 0x00, size=1)
        await self._send_msg(Msg.SET_PREBREWING_ENABLE, data=data)
        await self._send_msg(Msg.GET_CONFIG)
        self._call_callbacks(entity_type=TYPE_PREBREW)