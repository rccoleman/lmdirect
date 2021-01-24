"""lmdirect package for connecting to the local La Marzocco API."""
import asyncio
import logging

from lmdirect.const import (
    DISABLED,
    ENABLED,
    MACHINE_NAME,
    MODEL_NAME,
    SERIAL_NUMBER,
    SET_POWER,
    SET_AUTO_ON_OFF,
    SET_AUTO_ON_OFF_TIMES,
    SET_DOSE,
    SET_DOSE_HOT_WATER,
    SET_PREBREW_TIMES,
    SET_COFFEE_TEMP,
    SET_STEAM_TEMP,
    SET_PREBREWING_ENABLE,
)

from .connection import Connection
from .msgs import (
    AUTO,
    AUTO_BITFIELD,
    AUTO_BITFIELD_MAP,
    DAYS,
    DOSE,
    DOSE_HOT_WATER,
    ENABLE_PREBREWING,
    FIRMWARE_VER,
    GLOBAL,
    HOUR,
    MIN,
    MODEL_GS3_AV,
    MODEL_LM,
    MSGS,
    OFF,
    ON,
    POWER,
    PREBREWING,
    TOFF,
    TON,
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

        """Create locks to ensure correct previous status is retrieved for each service call"""
        self._locks = {
            x: asyncio.Lock()
            for x in [
                SET_POWER,
                SET_AUTO_ON_OFF,
                SET_AUTO_ON_OFF_TIMES,
                SET_DOSE,
                SET_DOSE_HOT_WATER,
                SET_PREBREW_TIMES,
                SET_COFFEE_TEMP,
                SET_STEAM_TEMP,
                SET_PREBREWING_ENABLE,
            ]
        }

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
            Msg.GET_DRINK_STATS,
            Msg.GET_USAGE_STATS,
            Msg.GET_FRONT_DISPLAY,
        ]

        _LOGGER.debug("Requesting status")
        await asyncio.gather(*[self._send_msg(msg) for msg in msgs])

        """Also wait for current temp"""
        self._responses_waiting.append(MSGS[Msg.GET_TEMP_REPORT].msg)

    async def send_msg(self, msg_id, **kwargs):
        """Send a message to the machine."""
        await self._send_msg(msg_id, **kwargs)

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
        async with self._locks[SET_POWER]:
            power_value = 1 if power else 0
            value = self._convert_to_ascii(power_value, size=1)
            await self._send_msg(Msg.SET_POWER, data=value)

            """Update the stored values to immediately reflect the change"""
            for state in [self._temp_state, self._current_status]:
                state[POWER] = power_value

            self._call_callbacks(entity_type=TYPE_MAIN)

    async def set_auto_on_off(self, day_of_week=None, enable=None):
        """Configure auto on/off."""

        async with self._locks[SET_AUTO_ON_OFF]:
            if None in [day_of_week, enable]:
                raise InvalidInput(f"Some parameters invalid {day_of_week=} {enable=}")

            """We need the existing register value, so fail if we don't have it yet."""
            if AUTO_BITFIELD not in self._current_status:
                """Kick off a query so that we'll have the data later."""
                await self._send_msg(Msg.GET_AUTO_SCHED)
                raise NotReady(f"Query not completed yet")

            """Extract value for this field."""
            bitfield = self._current_status[AUTO_BITFIELD]
            bitmask = 0x01 << self._findkey((day_of_week, AUTO), AUTO_BITFIELD_MAP)
            bitfield = bitfield | bitmask if enable else bitfield & ~bitmask
            buf_to_send = self._convert_to_ascii(bitfield, 1)

            _LOGGER.debug(
                f"set_on_off_enable: {buf_to_send=}, {MSGS[Msg.SET_AUTO_ENABLE].msg=}"
            )
            await self._send_msg(Msg.SET_AUTO_ENABLE, data=buf_to_send)

            """Update the stored values to immediately reflect the change"""
            for state in [self._temp_state, self._current_status]:
                state[day_of_week] = ENABLED if enable else DISABLED
                state[AUTO_BITFIELD] = bitfield

            self._call_callbacks(entity_type=TYPE_AUTO_ON_OFF)

    async def set_auto_on_off_global(self, value):
        """Set global auto on/off."""
        await self.set_auto_on_off(GLOBAL, value)

    async def set_auto_on_off_times(
        self,
        day_of_week=None,
        hour_on=None,
        minute_on=None,
        hour_off=None,
        minute_off=None,
    ):
        """Configure auto on/off hours."""
        async with self._locks[SET_AUTO_ON_OFF_TIMES]:
            if None in [day_of_week, hour_on, minute_on, hour_off, minute_off]:
                raise InvalidInput(
                    f"Some parameters invalid {day_of_week=} {hour_on=} {minute_on=} {hour_off=} {minute_off=}"
                )

            isinstance(hour_on, str) and (hour_on := int(hour_on))
            isinstance(minute_on, str) and (minute_on := int(minute_on))

            isinstance(hour_off, str) and (hour_off := int(hour_off))
            isinstance(minute_off, str) and (minute_off := int(minute_off))

            """Validate input."""
            if not (
                0 <= hour_on <= 23
                and 0 <= minute_on <= 59
                and 0 <= hour_off <= 23
                and 0 <= minute_off <= 59
                and day_of_week in DAYS
            ):
                raise InvalidInput(
                    f"set_auto_on_off_times: Invalid values {day_of_week=} {hour_on=} {minute_on=} {hour_off=} {minute_off=}"
                )

            """Update hours."""
            data = self._convert_to_ascii(hour_on, size=1) + self._convert_to_ascii(
                hour_off, size=1
            )
            address_base = self._convert_to_ascii(
                Msg.AUTO_ON_OFF_HOUR_BASE + (DAYS.index(day_of_week) * 2), size=1
            )
            _LOGGER.debug(
                f"set_on_off_times: {data=}, {address_base=}, {MSGS[Msg.SET_AUTO_SCHED].msg=}"
            )
            await self._send_msg(Msg.SET_AUTO_SCHED, base=address_base, data=data)

            """Update minutes."""
            data = self._convert_to_ascii(minute_on, size=1) + self._convert_to_ascii(
                minute_off, size=1
            )
            address_base = self._convert_to_ascii(
                Msg.AUTO_ON_OFF_MIN_BASE + (DAYS.index(day_of_week) * 2), size=1
            )
            _LOGGER.debug(
                f"set_on_off_times: {data=}, {address_base=}, {MSGS[Msg.SET_AUTO_SCHED].msg=}"
            )
            await self._send_msg(Msg.SET_AUTO_SCHED, base=address_base, data=data)

        """Update the stored values to immediately reflect the change"""
        for state in [self._temp_state, self._current_status]:
            state[self._get_key((day_of_week, ON, HOUR))] = hour_on
            state[self._get_key((day_of_week, ON, MIN))] = minute_on
            state[self._get_key((day_of_week, OFF, HOUR))] = hour_off
            state[self._get_key((day_of_week, OFF, MIN))] = minute_off

        self.calculate_auto_sched_times(day_of_week)

        self._call_callbacks(entity_type=TYPE_MAIN)

    async def set_dose(self, key=None, pulses=None):
        """Set the coffee dose in pulses (~0.5ml)."""

        async with self._locks[SET_DOSE]:
            if None in [key, pulses]:
                raise InvalidInput(
                    f"set_dose: Some parameters not specified {key=} {pulses=}"
                )

            isinstance(pulses, str) and (pulses := int(pulses))
            isinstance(key, str) and (key := int(key))

            """Validate input."""
            if not (1 <= pulses <= 1000 and 1 <= key <= 5):
                raise InvalidInput(f"set_dose: Invalid values {pulses=} {key=}")

            data = self._convert_to_ascii(pulses, size=2)
            key = self._convert_to_ascii(Msg.DOSE_KEY_BASE + (key - 1) * 2, size=1)
            await self._send_msg(Msg.SET_DOSE, base=key, data=data)

            """Update the stored values to immediately reflect the change"""
            for state in [self._temp_state, self._current_status]:
                state[self._get_key((DOSE, f"k{key}"))] = pulses

            self._call_callbacks(entity_type=TYPE_MAIN)

    async def set_dose_hot_water(self, seconds=None):
        """Set the hot water dose in seconds."""

        async with self._locks[SET_DOSE_HOT_WATER]:
            if seconds is None:
                raise InvalidInput("set_dose_hot_water: Seconds not specified")

            isinstance(seconds, str) and (seconds := int(seconds))

            """Validate input."""
            if not (1 <= seconds <= 30):
                raise InvalidInput(f"Invalid values {seconds=}")

            data = self._convert_to_ascii(seconds, size=1)
            await self._send_msg(Msg.SET_DOSE_HOT_WATER, data=data)

            """Update the stored values to immediately reflect the change"""
            for state in [self._temp_state, self._current_status]:
                state[DOSE_HOT_WATER] = seconds

            self._call_callbacks(entity_type=TYPE_MAIN)

    async def set_prebrew_times(self, key=None, seconds_on=None, seconds_off=None):
        """Set prebrew on/off times in seconds."""

        async with self._locks[SET_PREBREW_TIMES]:
            if None in [key, seconds_on, seconds_off]:
                raise InvalidInput(
                    "set_prebrew_times: Some parameters invalid {key=} {seconds_on=} {seconds_off=}"
                )

            seconds_on, seconds_off = [float(x) for x in [seconds_on, seconds_off]]
            isinstance(key, str) and (key := int(key))

            """Validate input."""
            if not (
                0 <= seconds_on <= 5.9 and 0 <= seconds_off <= 5.9 and 1 <= key <= 4
            ):
                raise InvalidInput(f"Invalid values {seconds_on=} {seconds_off=}")

            if not (
                (self.model_name == MODEL_GS3_AV and 1 <= key <= 4)
                or (self.model_name == MODEL_LM and key == 1)
            ):
                raise InvalidInput(f"Invalid values {key=}")

            """Set "on" time."""
            key_on = self._convert_to_ascii(Msg.PREBREW_ON_BASE + (key - 1), size=1)
            data = self._convert_to_ascii(int(seconds_on * 10), size=1)
            await self._send_msg(Msg.SET_PREBREW_TIMES, base=key_on, data=data)

            """Set "off" time."""
            key_off = self._convert_to_ascii(Msg.PREBREW_OFF_BASE + (key - 1), size=1)
            data = self._convert_to_ascii(int(seconds_off * 10), size=1)
            await self._send_msg(Msg.SET_PREBREW_TIMES, base=key_off, data=data)

            """Update the stored values to immediately reflect the change"""
            for state in [self._temp_state, self._current_status]:
                state[self._get_key((PREBREWING, TON, f"k{key}"))] = seconds_on
                state[self._get_key((PREBREWING, TOFF, f"k{key}"))] = seconds_off

            self._call_callbacks(entity_type=TYPE_PREBREW)

    async def set_coffee_temp(self, temp=None):
        """Set the coffee boiler temp in Celcius."""

        async with self._locks[SET_COFFEE_TEMP]:
            if temp is None:
                raise InvalidInput("set_coffee__temp: Temperature not specified")

            isinstance(temp, str) and (temp := float(temp))
            temp = round(temp, 1)

            data = self._convert_to_ascii(int(temp * 10), size=2)
            await self._send_msg(Msg.SET_COFFEE_TEMP, data=data)

            """Update the stored values to immediately reflect the change"""
            for state in [self._temp_state, self._current_status]:
                state[TSET_COFFEE] = temp

            self._call_callbacks(entity_type=TYPE_COFFEE_TEMP)

    async def set_steam_temp(self, temp=None):
        """Set the steam boiler temp in Celcius."""

        async with self._locks[SET_STEAM_TEMP]:
            if temp is None:
                raise InvalidInput("set_steam_temp: Temperature not specified")

            isinstance(temp, str) and (temp := float(temp))
            temp = round(temp, 1)

            data = self._convert_to_ascii(int(temp * 10), size=2)
            await self._send_msg(Msg.SET_STEAM_TEMP, data=data)

            """Update the stored values to immediately reflect the change"""
            for state in [self._temp_state, self._current_status]:
                state[TSET_STEAM] = temp

            self._call_callbacks(entity_type=TYPE_STEAM_TEMP)

    async def set_prebrewing_enable(self, enable):
        """Turn prebrewing on or off."""

        async with self._locks[SET_PREBREWING_ENABLE]:
            prebrew_value = 1 if enable else 0
            data = self._convert_to_ascii(prebrew_value, size=1)

            await self._send_msg(Msg.SET_PREBREWING_ENABLE, data=data)

            """Update the stored values to immediately reflect the change"""
            for state in [self._temp_state, self._current_status]:
                state[ENABLE_PREBREWING] = prebrew_value

            self._call_callbacks(entity_type=TYPE_PREBREW)


class InvalidInput(Exception):
    """Error to indicate that invalid parameters were provided."""

    def __init__(self, msg):
        _LOGGER.exception(msg)
        super().__init__(msg)


class NotReady(Exception):
    """Error to indicate that data hasn't been read yet that the service call relies on."""

    def __init__(self, msg):
        _LOGGER.exception(msg)
        super().__init__(msg)
