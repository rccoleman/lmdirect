"""lmdirect package for connecting to the local La Marzocco API."""
import asyncio
import logging

from lmdirect.const import (
    DISABLED,
    ENABLED,
    MACHINE_NAME,
    MODEL_NAME,
    SERIAL_NUMBER,
)

from .connection import Connection
from .msgs import (
    AUTO_BITFIELD,
    AUTO_BITFIELD_MAP,
    AUTO_SCHED_MAP,
    DOSE_K1,
    DOSE_HOT_WATER,
    FIRMWARE_VER,
    GLOBAL_AUTO,
    MODEL_GS3_AV,
    MODEL_LM,
    MON_OFF,
    MON_ON,
    MSGS,
    PREBREWING_TOFF_K1,
    PREBREWING_TON_K1,
    TSET_COFFEE,
    TSET_STEAM,
    TYPE_AUTO_ON_OFF,
    TYPE_COFFEE_TEMP,
    TYPE_MAIN,
    TYPE_PREBREW,
    TYPE_STEAM_TEMP,
    Msg,
)

_LOGGER = logging.getLogger(__name__)


class LMDirect(Connection):
    """Represents and provides an interface to the local API to a La Marzocco espresso machine"""

    def __init__(self, machine_info):
        super().__init__(machine_info)

    @property
    def current_status(self):
        """Return a dict of all the properties that have been received."""
        return self._current_status

    @property
    def machine_name(self):
        """Return the name of the machine."""
        return self._machine_info[MACHINE_NAME]

    @property
    def serial_number(self):
        """Return serial number."""
        return self._machine_info[SERIAL_NUMBER]

    @property
    def model_name(self):
        """Return model name."""
        return self._machine_info[MODEL_NAME]

    @property
    def firmware_version(self):
        """Return firmware version."""
        return self._current_status.get(FIRMWARE_VER, "Unknown")

    def register_callback(self, callback):
        """Register callback for updates."""
        if callable(callback):
            self._callback_list.append(callback)

    def register_raw_callback(self, msg, callback, **kwargs):
        """Register a callback for the raw response to a command."""
        if callable(callback):
            self._raw_callback_list.append((msg, callback))

    def deregister_raw_callback(self, key):
        """Register a callback for the raw response to a command."""

        """The key is a tuple comprised of (msg, callback)."""
        if key in self._raw_callback_list:
            self._raw_callback_list.remove(key)

    async def connect(self):
        """Connect to the machine."""
        return await self._connect()

    async def request_status(self):
        """Request new data."""
        msgs = [
            Msg.GET_STATUS,
            Msg.GET_CONFIG,
            Msg.GET_AUTO_SCHED,
            Msg.GET_DATETIME,
            Msg.GET_DRINK_STATS,
            Msg.GET_USAGE_STATS,
        ]

        _LOGGER.debug("Requesting status")
        await asyncio.gather(*[self._send_msg(msg) for msg in msgs])

        """Also wait for current temp"""
        self._responses_waiting.append(MSGS[Msg.GET_TEMP_REPORT].msg)

    async def send_msg(self, msg_id, key=None, data=None):
        """Send a message to the machine."""
        await self._send_msg(msg_id, key=key, data=data)

    async def close(self):
        """Close the connection to the machine."""

        """Wait for the read task to exit"""
        if self._read_reaper_task:
            await asyncio.gather(self._read_reaper_task)
        await self._close()

    def call_callbacks(self, **kwargs):
        """Call all callbacks to refresh data for listeners."""
        self._call_callbacks(**kwargs)

    """Utils"""

    def _convert_to_ascii(self, value, size):
        """Convert an integer value to ASCII-encoded hex."""
        return ("%0" + str(size * 2) + "X") % value

    def _findkey(self, find_value, dict):
        """Find a key from the value in a dict."""
        return next(
            (key for key, value in dict.items() if value == find_value),
            None,
        )

    """Services"""

    async def set_power(self, power):
        """Send power on or power off commands."""
        value = self._convert_to_ascii(0x01 if power else 0x00, size=1)
        await self._send_msg(Msg.SET_POWER, data=value)
        await self._send_msg(Msg.GET_CONFIG)
        self._call_callbacks(entity_type=TYPE_MAIN)

    async def set_auto_on_off(self, day_of_week=None, enable=None):
        """Configure auto on/off."""

        async def auto_on_off_callback(key, data):
            """Callback for the raw sequence."""

            """Deregister because we don't need to continue looking for it."""
            self.deregister_raw_callback(key)
            _LOGGER.debug(f"Received raw callback: {data}")

            try:
                """Find the bit to modify."""
                elem = self._findkey(AUTO_BITFIELD, AUTO_SCHED_MAP)

                """The strings are ASCII-encoded hex, so each value takes 2 bytes."""
                index = elem.index * 2
                size = elem.size * 2

                """Extract value for this field."""
                orig_value = int(data[index : index + size], 16)
                bitmask = 0x01 << self._findkey(day_of_week, AUTO_BITFIELD_MAP)
                new_value = self._convert_to_ascii(
                    orig_value | bitmask if enable else orig_value & ~bitmask, 1
                )

                buf_to_send = data[:index] + new_value + data[index + size :]

                self._current_status[day_of_week] = ENABLED if enable else DISABLED

                await self._send_msg(Msg.SET_AUTO_SCHED, data=buf_to_send)
                await self._send_msg(Msg.GET_AUTO_SCHED)

                self._call_callbacks(entity_type=TYPE_AUTO_ON_OFF)
            except Exception as err:
                _LOGGER.debug(f"Caught exception: {err}")

        if None in [day_of_week, enable]:
            msg = f"Some parameters invalid {day_of_week} {enable}"
            raise InvalidInput(msg)

        self.register_raw_callback(Msg.GET_AUTO_SCHED, auto_on_off_callback)
        await self._send_msg(Msg.GET_AUTO_SCHED)

    async def set_auto_on_off_global(self, value):
        """Set global auto on/off."""
        await self.set_auto_on_off(GLOBAL_AUTO, value)

    async def set_auto_on_off_hours(
        self, day_of_week=None, hour_on=None, hour_off=None
    ):
        """Configure auto on/off hours."""

        async def auto_on_off_callback(key, data):
            """Callback for the raw sequence."""

            """Deregister because we don't need to continue looking for it."""
            self.deregister_raw_callback(key)
            _LOGGER.debug(f"Received raw callback: {data}")

            try:
                """Find the "on" element."""
                elem = self._findkey(day_of_week + MON_ON[3:], AUTO_SCHED_MAP)

                """The strings are ASCII-encoded hex, so each value takes 2 bytes and there 2 of them."""
                index = elem.index * 2
                size = elem.size * 4

                """Construct the new "on" and "off" values."""
                buf_to_send = (
                    data[:index]
                    + self._convert_to_ascii(hour_on, 1)
                    + self._convert_to_ascii(hour_off, 1)
                    + data[index + size :]
                )

                self._current_status[day_of_week + MON_ON[3:]] = hour_on
                self._current_status[day_of_week + MON_OFF[3:]] = hour_off

                await self._send_msg(Msg.SET_AUTO_SCHED, data=buf_to_send)
                await self._send_msg(Msg.GET_AUTO_SCHED)
                self._call_callbacks(entity_type=TYPE_AUTO_ON_OFF)
            except Exception as err:
                _LOGGER.debug(f"Caught exception: {err}")
                raise

        if None in [day_of_week, hour_on, hour_off]:
            msg = f"Some parameters invalid {day_of_week} {hour_on} {hour_off}"
            raise InvalidInput(msg)

        self.register_raw_callback(Msg.GET_AUTO_SCHED, auto_on_off_callback)
        await self._send_msg(Msg.GET_AUTO_SCHED)

    async def set_dose(self, key=None, pulses=None):
        """Set the coffee dose in pulses (~0.5ml)."""

        if None in [key, pulses]:
            msg = f"set_dose: Some parameters not specified {key} {pulses}"
            raise InvalidInput(msg)

        if isinstance(pulses, str):
            pulses = int(pulses)

        if isinstance(key, str):
            key = int(key)

        """Validate input."""
        if not (1 <= pulses <= 1000 and 1 <= key <= 5):
            msg = f"set_dose: Invalid values pulses:{pulses} key:{key}"
            raise InvalidInput(msg)

        self._current_status[DOSE_K1.replace("1", str(key))] = pulses

        data = self._convert_to_ascii(pulses, size=2)
        key = self._convert_to_ascii(Msg.DOSE_KEY_BASE + (key - 1) * 2, size=1)
        await self._send_msg(Msg.SET_DOSE, key=key, data=data)
        await self._send_msg(Msg.GET_CONFIG)
        self._call_callbacks(entity_type=TYPE_MAIN)

    async def set_dose_hot_water(self, seconds=None):
        """Set the hot water dose in seconds."""

        if seconds is None:
            raise InvalidInput("set_dose_hot_water: Seconds not specified")

        if isinstance(seconds, str):
            seconds = int(seconds)

        """Validate input."""
        if not (1 <= seconds <= 30):
            msg = f"Invalid values seconds:{seconds}"
            raise InvalidInput(msg)

        self._current_status[DOSE_HOT_WATER] = seconds

        data = self._convert_to_ascii(seconds, size=1)
        await self._send_msg(Msg.SET_DOSE_HOT_WATER, data=data)
        await self._send_msg(Msg.GET_CONFIG)
        self._call_callbacks(entity_type=TYPE_MAIN)

    async def set_prebrew_times(self, key=None, time_on=None, time_off=None):
        """Set prebrew on/off times in seconds."""

        if None in [key, time_on, time_off]:
            raise InvalidInput(
                "set_prebrew_times: Some parameters invalid {key} {time_on} {time_off}"
            )

        if isinstance(time_on, str):
            time_on = float(time_on)

        if isinstance(time_off, str):
            time_off = float(time_off)

        if isinstance(key, str):
            key = int(key)

        """Validate input."""
        if not (0 <= time_on <= 5.9 and 0 <= time_off <= 5.9 and 1 <= key <= 4):
            msg = f"Invalid values time_on:{time_on} off_time:{time_off}"
            raise InvalidInput(msg)

        if not (
            (self.model_name == MODEL_GS3_AV and 1 <= key <= 4)
            or (self.model_name == MODEL_LM and key == 1)
        ):
            msg = f"Invalid values key:{key}"
            raise InvalidInput(msg)

        self._current_status[PREBREWING_TON_K1.replace("1", str(key))] = time_on
        self._current_status[PREBREWING_TOFF_K1.replace("1", str(key))] = time_off

        """Set "on" time."""
        key_on = self._convert_to_ascii(Msg.PREBREW_ON_BASE + (key - 1), size=1)
        data = self._convert_to_ascii(int(time_on * 10), size=1)
        await self._send_msg(Msg.SET_PREBREW_TIMES, key=key_on, data=data)

        """Set "off" time."""
        key_off = self._convert_to_ascii(Msg.PREBREW_OFF_BASE + (key - 1), size=1)
        data = self._convert_to_ascii(int(time_off * 10), size=1)
        await self._send_msg(Msg.SET_PREBREW_TIMES, key=key_off, data=data)
        await self._send_msg(Msg.GET_CONFIG)
        self._call_callbacks(entity_type=TYPE_PREBREW)

    async def set_coffee_temp(self, temp=None):
        """Set the coffee boiler temp in Celcius."""

        if temp is None:
            raise InvalidInput("set_coffee__temp: Temperature not specified")

        if isinstance(temp, str):
            temp = float(temp)

        temp = round(temp, 1)

        self._current_status[TSET_COFFEE] = temp

        data = self._convert_to_ascii(int(temp * 10), size=2)
        await self._send_msg(Msg.SET_COFFEE_TEMP, data=data)
        await self._send_msg(Msg.GET_TEMP_REPORT, data=data)
        self._call_callbacks(entity_type=TYPE_COFFEE_TEMP)

    async def set_steam_temp(self, temp=None):
        """Set the steam boiler temp in Celcius."""

        if temp is None:
            raise InvalidInput("set_steam_temp: Temperature not specified")

        if isinstance(temp, str):
            temp = float(temp)

        temp = round(temp, 1)

        self._current_status[TSET_STEAM] = temp

        data = self._convert_to_ascii(int(temp * 10), size=2)
        await self._send_msg(Msg.SET_STEAM_TEMP, data=data)
        await self._send_msg(Msg.GET_TEMP_REPORT, data=data)
        self._call_callbacks(entity_type=TYPE_STEAM_TEMP)

    async def set_prebrewing_enable(self, enable):
        """Turn prebrewing on or off."""
        data = self._convert_to_ascii(0x01 if enable else 0x00, size=1)
        await self._send_msg(Msg.SET_PREBREWING_ENABLE, data=data)
        await self._send_msg(Msg.GET_CONFIG)
        self._call_callbacks(entity_type=TYPE_PREBREW)


class InvalidInput(Exception):
    """Error to indicate that invalid parameters were provided."""

    def __init__(self, msg):
        _LOGGER.exception(msg)
        super().__init__(msg)
