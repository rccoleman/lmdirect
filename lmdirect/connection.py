"""lmdirect connection class."""
import asyncio
import logging
from datetime import datetime, timedelta
from functools import partial

from authlib.integrations.base_client.errors import OAuthError
from authlib.integrations.httpx_client import AsyncOAuth2Client

from .aescipher import AESCipher
from .const import *
from .msgs import (
    AUTO_BITFIELD,
    AUTO_BITFIELD_MAP,
    AUTO_SCHED_MAP,
    CURRENT_PULSE_COUNT,
    DAYS_SINCE_BUILT,
    DIVIDE_KEYS,
    DRINK_OFFSET_MAP,
    ENABLE_PREBREWING,
    ENABLE_PREINFUSION,
    FIRMWARE_VER,
    FRONT_PANEL_DISPLAY,
    GATEWAY_DRINK_MAP,
    HEATING_STATE,
    HEATING_VALUES,
    HOUR,
    KEY_ACTIVE,
    MIN,
    MSGS,
    OFF,
    ON,
    PREBREW_FLAG,
    SERIAL_NUMBERS,
    STEAM_BOILER_ENABLE,
    TEMP_COFFEE,
    TIME,
    TOTAL_COFFEE,
    TOTAL_COFFEE_ACTIVATIONS,
    TOTAL_FLUSHING,
    UPDATE_AVAILABLE,
    BREW_GROUP_OFFSET,
    T_UNIT,
    Elem,
    Msg,
)

_LOGGER = logging.getLogger(__name__)


class Connection:
    def __init__(self, machine_info):
        """Init LMDirect."""
        self._reader = None
        self._writer = None
        self._read_response_task = None
        self._read_reaper_task = None
        self._current_status = {}
        self._responses_waiting = []
        self._run = True
        self._callback_list = []
        self._raw_callback_list = []
        self._cipher = None
        self._machine_info = machine_info
        self._start_time = None
        self._connected = False
        self._lock = asyncio.Lock()
        self._first_time = True
        self._update_available = None
        self._initialized_machine_info = False

        """Maintain temporary states for device states that take a while to update"""
        self._temp_state = {}

    def _get_key(self, k):
        """Construct tag name if needed."""
        if isinstance(k, tuple):
            k = "_".join(k)
        return k

    async def retrieve_machine_info(self, machine_info):
        """Retrieve the machine info from the cloud APIs."""
        _LOGGER.debug(f"Retrieving machine info")

        async with AsyncOAuth2Client(
            client_id=machine_info[CLIENT_ID],
            client_secret=machine_info[CLIENT_SECRET],
            token_endpoint=TOKEN_URL,
        ) as client:

            headers = {
                "client_id": machine_info[CLIENT_ID],
                "client_secret": machine_info[CLIENT_SECRET],
            }

            try:
                await client.fetch_token(
                    url=TOKEN_URL,
                    username=machine_info[USERNAME],
                    password=machine_info[PASSWORD],
                    headers=headers,
                )
            except OAuthError as err:
                raise AuthFail("Authorization failure") from err

            """Only retrieve info if we're missing something."""
            if any(
                x not in machine_info
                for x in [KEY, SERIAL_NUMBER, MACHINE_NAME, MODEL_NAME]
            ):
                cust_info = await client.get(CUSTOMER_URL)
                if cust_info:
                    fleet = cust_info.json()["data"]["fleet"][0]
                    machine_info[KEY] = fleet["communicationKey"]
                    machine_info[SERIAL_NUMBER] = fleet["machine"]["serialNumber"]
                    machine_info[MACHINE_NAME] = fleet["name"]
                    machine_info[MODEL_NAME] = fleet["machine"]["model"]["name"]

            """Add the machine and model names to the dict so that they're avaialble for attributes"""
            self._current_status.update({MACHINE_NAME: machine_info[MACHINE_NAME]})
            self._current_status.update({MODEL_NAME: machine_info[MODEL_NAME]})

            if any(
                self._get_key(x) not in self._current_status
                for x in DRINK_OFFSET_MAP.values()
            ):
                drink_info = await client.get(
                    DRINK_COUNTER_URL.format(serial_number=machine_info[SERIAL_NUMBER])
                )
                if drink_info:
                    data = drink_info.json().get("data")
                    if data:
                        self._current_status.update(
                            {
                                self._get_key(GATEWAY_DRINK_MAP[x["coffeeType"]]): x["count"]
                                for x in data
                            }
                        )

            if UPDATE_AVAILABLE not in self._current_status:
                update_info = await client.get(UPDATE_URL)
                if update_info:
                    data = update_info.json().get("data")
                    self._update_available = "Yes" if data else "No"

        self._initialized_machine_info = True

        _LOGGER.debug(f"Finished machine info")
        return machine_info

    async def _connect(self):
        """Conmnect to espresso machine."""
        if self._connected:
            return self._machine_info

        _LOGGER.debug(f"Connecting")

        if not self._initialized_machine_info:
            try:
                self._machine_info = await self.retrieve_machine_info(
                    self._machine_info
                )
            except AuthFail as err:
                raise err
            except Exception as err:
                raise ConnectionFail(
                    f"Exception retrieving machine info: {err}"
                ) from err

        if not self._cipher:
            self._cipher = AESCipher(self._machine_info[KEY])

        """Connect to the machine."""
        try:
            self._reader, self._writer = await asyncio.wait_for(
                asyncio.open_connection(
                    self._machine_info[HOST], self._machine_info[PORT]
                ),
                timeout=3,
            )
        except asyncio.TimeoutError:
            _LOGGER.warning("Connection Timeout, skipping")
            return None

        except Exception as err:
            raise ConnectionFail(f"Cannot connect to machine: {err}") from err

        """Start listening for responses."""
        await self.start_read_task()

        self._connected = True
        _LOGGER.debug("Finished Connecting")

        return self._machine_info

    async def start_read_task(self):
        """Start listening for responses."""
        loop = asyncio.get_event_loop()
        self._read_response_task = loop.create_task(
            self.read_response_task(), name="Response Task"
        )

        """Reap the results and any any exceptions"""
        self._read_reaper_task = loop.create_task(
            self.read_reaper(), name="Read Reaper"
        )

    async def _close(self):
        """Close the connection to the machine."""
        if not self._connected:
            return

        if self._writer is not None:
            self._writer.close()

        if self._read_response_task:
            self._read_response_task.cancel()

        self._reader = self._writer = None
        self._connected = False
        _LOGGER.debug("Finished closing")

    async def read_reaper(self):
        _LOGGER.debug("Starting read reaper")
        try:
            await asyncio.gather(self._read_response_task)
        except Exception as err:
            _LOGGER.error(f"Exception in read_response_task: {err}")

        await self._close()
        self._read_response_task = None
        self._first_time = False

        _LOGGER.debug("Finished reaping read task")

    def _call_callbacks(self, **kwargs):
        """Call the callbacks."""
        if self._callback_list is not None:
            [
                elem(
                    current_status=self._current_status,
                    **kwargs,
                )
                for elem in self._callback_list
            ]

    async def read_response_task(self):
        """Start thread to receive responses."""
        BUFFER_SIZE = 1000
        handle = None

        _LOGGER.debug("Starting read task")

        if self._start_time is None:
            self._start_time = datetime.now()

        while self._run:
            encoded_data = await self._reader.readuntil(separator=b"%")

            if encoded_data is not None:
                loop = asyncio.get_event_loop()
                fn = partial(self._cipher.decrypt, encoded_data[1:-1])
                plaintext = await loop.run_in_executor(None, fn)
                if not plaintext:
                    continue

                await self.process_data(plaintext)

                if not self._first_time:
                    if handle:
                        handle.cancel()
                        handle = None

                    """Coalesce callbacks within a 5s window."""
                    handle = loop.call_later(5, self._call_callbacks)
                else:
                    self._call_callbacks()

                """Exit if we've been reading longer than 10s since the last command."""
                if datetime.now() > self._start_time + timedelta(seconds=10):
                    _LOGGER.debug(f"Exiting loop: {self._responses_waiting}")

                    """Flush the wait list."""
                    self._responses_waiting = []
                    break

    async def process_data(self, plaintext):
        """Process incoming packet."""

        """Separate the mesg from the data."""
        msg_type = plaintext[0]
        raw_data = plaintext[1:]
        msg = raw_data[:8]
        retval = True

        """Chop off the message and check byte."""
        data = raw_data[8:-2]
        finished = not len(self._responses_waiting)

        _LOGGER.debug(f"Message={msg}, Data={data}")

        msg_id = None

        if msg_type == Msg.WRITE:
            if Msg.RESPONSE_GOOD not in data:
                _LOGGER.error(f"Command Failed: {msg}: {data}")
                retval = False
            else:
                _LOGGER.debug(f"Command Succeeded: {msg}: {data}")
        else:
            """Find the matching item or returns None."""
            msg_id = next(
                (
                    x
                    for x in MSGS
                    if MSGS[x].msg == msg and MSGS[x].msg_type == msg_type
                ),
                None,
            )

            if msg_id is not None:
                cur_msg = MSGS[msg_id]

                """Notify any listeners for this message."""
                [
                    await x[1]((msg_id, x[1]), data)
                    for x in self._raw_callback_list
                    if MSGS[x[0]].msg == msg
                ]

                if cur_msg.map is not None:
                    await self._populate_items(data, cur_msg)
            else:
                _LOGGER.error(f"Unexpected response: {plaintext}")
                retval = False

        if msg in self._responses_waiting:
            self._responses_waiting.remove(msg)
            finished = not len(self._responses_waiting)
            if finished:
                _LOGGER.debug("Received all responses")

        return retval

    def calculate_auto_sched_times(self, key):
        time_on_key = self._get_key((key, ON, TIME))
        hour_on_key = self._get_key((key, ON, HOUR))
        min_on_key = self._get_key((key, ON, MIN))
        time_off_key = self._get_key((key, OFF, TIME))
        hour_off_key = self._get_key((key, OFF, HOUR))
        min_off_key = self._get_key((key, OFF, MIN))

        """Set human-readable "on" time"""
        self._current_status[
            time_on_key
        ] = f"{'%02d' % self._current_status[hour_on_key]}:{'%02d' % self._current_status[min_on_key]}"

        """Set human-readable "off" time"""
        self._current_status[
            time_off_key
        ] = f"{'%02d' % self._current_status[hour_off_key]}:{'%02d' % self._current_status[min_off_key]}"

    async def _populate_items(self, data, cur_msg):
        def handle_cached_value(element, value):
            """See if we've stored a temporary value that may take a while to update on the machine"""
            if element in self._temp_state:
                if value == self._temp_state[element]:
                    """Value has updated, so remove the temp value"""
                    _LOGGER.debug(
                        f"Element {element} has updated to {value}, pop the cached value"
                    )
                    self._temp_state.pop(element, None)
                else:
                    """Value hasn't updated yet, so use the cached value"""
                    _LOGGER.debug(
                        f"Element {element} hasn't updated yet, so use the cached value {value}"
                    )
                    value = self._temp_state[element]

            return value

        """Process all the fields and populate shared dict."""
        map = cur_msg.map
        for elem in map:
            value = None

            """Don't decode a value if we just plan to calculate it"""
            if elem.index != CALCULATED_VALUE:
                """The strings are ASCII-encoded hex, so each value takes 2 bytes."""
                index = elem.index * 2
                size = elem.size * 2

                """Extract value for this field."""
                value = data[index : index + size]

                if elem.type == Elem.INT:
                    """Convert from ascii-encoded hex."""
                    value = int(value, 16)

            raw_key = map[elem]

            """Construct key name if needed."""
            key = self._get_key(raw_key)

            if any(x in key for x in DIVIDE_KEYS):
                value = value / 10
            elif key == FIRMWARE_VER:
                value = "%0.2f" % (value / 100)
            elif key in SERIAL_NUMBERS:
                value = "".join(
                    [chr(int(value[i : i + 2], 16)) for i in range(0, len(value), 2)]
                )
                """Chop off any trailing nulls."""
                value = value.partition("\0")[0]

            elif key == AUTO_BITFIELD:
                bitfield = value
                for item in AUTO_BITFIELD_MAP:
                    setting = ENABLED if bitfield & 0x01 else DISABLED
                    processed_key = self._get_key(AUTO_BITFIELD_MAP[item])
                    self._current_status[processed_key] = handle_cached_value(
                        processed_key, setting
                    )
                    bitfield = bitfield >> 1
            elif raw_key in DRINK_OFFSET_MAP:
                if key == TOTAL_FLUSHING:
                    value = (
                        self._current_status[TOTAL_COFFEE_ACTIVATIONS]
                        - self._current_status[TOTAL_COFFEE]
                    )
                offset_key = self._get_key(DRINK_OFFSET_MAP[raw_key])
                if key not in self._current_status:
                    """If we haven't seen the value before, calculate the offset."""
                    self._current_status.update(
                        {offset_key: value - self._current_status.get(offset_key, 0)}
                    )
                """Apply the offset to the value."""
                value = value - self._current_status.get(offset_key, 0)
            elif key == DAYS_SINCE_BUILT:
                """Convert hours to days."""
                value = round(value / 24)
            elif key == HEATING_STATE:
                value = [x for x in HEATING_VALUES if HEATING_VALUES[x] & value]
                """Don't add attribute and remove it if machine isn't currently running."""
                if not value:
                    self._current_status.pop(key, None)
                    continue
            elif key == BREW_GROUP_OFFSET:
                value = (value & 0xFF00) >> 8 | (value & 0x00FF) << 8
                units = self._current_status.get(T_UNIT, 0x99)
                # The Linea Mini has no offset
                if units == 0x00:
                    value = 0
                # check if the factory default is in Fahrenheit
                else:
                    if units == 0x99:
                        # convert to Celcius
                        value *= 200/360

                    value = round((value - 100) / 10, 1)
            elif key in [KEY_ACTIVE, CURRENT_PULSE_COUNT]:
                """Don't add attributes and remove them if machine isn't currently running."""
                if not value:
                    self._current_status.pop(key, None)
                    continue
            elif key == FRONT_PANEL_DISPLAY:
                value = (
                    bytes.fromhex(value)
                    .decode("latin-1")
                    .replace("\xdf", "\u00b0")  # Degree symbol
                    .replace(
                        "\xdb", "\u25A1"
                    )  # turn a block into an outline block (heating element off)
                    .replace(
                        "\xff", "\u25A0"
                    )  # turn \xff into a solid block (heating element on)
                )
            elif elem.index == CALCULATED_VALUE and key in AUTO_SCHED_MAP.values():
                self.calculate_auto_sched_times(key)
                continue
            elif key == STEAM_BOILER_ENABLE:
                value = (value & 0x01) == 1
            elif elem.index == CALCULATED_VALUE and key in [ENABLE_PREBREWING, ENABLE_PREINFUSION]:
                state = self._current_status.get(PREBREW_FLAG)
                value = state == (1 if key == ENABLE_PREBREWING else 2)

            if key == TEMP_COFFEE:
                # The offset is used to set the boiler temp to achieve the
                # user-set temp at the grouphead, so subtract to get the
                # group temp
                value = round(value - self._current_status.get(BREW_GROUP_OFFSET, 0), 1)

            self._current_status[key] = handle_cached_value(key, value)

    async def _send_msg(self, msg_id, data=None, base=None):
        """Send command to the espresso machine."""
        msg = MSGS[msg_id]

        _LOGGER.debug(f"Sending {msg.msg} with {data} {base}")
        await self._send_raw_msg(msg.msg, msg.msg_type, data, base)

    async def _send_raw_msg(self, msg, msg_type, data=None, base=None):
        def checksum(buffer):
            """Compute check byte."""
            buffer = bytes(buffer, "utf-8")
            return "%0.2X" % (sum(buffer) % 256)

        """Prevent race conditions - can be called from different tasks."""
        async with self._lock:
            """Connect if we don't have an active connection."""
            result = await self._connect()

            if not result:
                raise ConnectionFail("Connection failed.")

            if not self._writer:
                raise ConnectionFail(f"self._writer={self._writer}")

            """If a key was provided, replace the second byte of the message."""
            msg_to_send = msg if not base else msg[:2] + base + msg[4:]

            plaintext = msg_type + msg_to_send

            if data is not None:
                plaintext += data

            """Add the check byte."""
            plaintext += checksum(plaintext)

            loop = asyncio.get_event_loop()
            fn = partial(self._cipher.encrypt, plaintext)
            ciphertext = (
                "@" + (await loop.run_in_executor(None, fn)).decode("utf-8") + "%"
            )

            self._writer.write(bytes(ciphertext, "utf-8"))
            await self._writer.drain()

            """Remember that we're waiting for a response."""
            self._responses_waiting.append(msg_to_send)

            """Note when the command was sent."""
            self._start_time = datetime.now()


class AuthFail(Exception):
    """Error to indicate there is invalid auth info."""

    def __init__(self, msg):
        super().__init__(msg)


class ConnectionFail(Exception):
    """Error to indicate there is no connection."""

    def __init__(self, msg):
        super().__init__(msg)
