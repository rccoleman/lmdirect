"""Local API commands for La Marzocco espresso machines."""

# Tags

from lmdirect.const import (
    CONTINUOUS_OFFSET,
    DRINKS_K1_OFFSET,
    DRINKS_K2_OFFSET,
    DRINKS_K3_OFFSET,
    DRINKS_K4_OFFSET,
    HOT_WATER_OFFSET,
)

DATE_RECEIVED = "date_received"
POWER = "power"
TEMP_COFFEE = "coffee_temp"
TEMP_STEAM = "steam_temp"
TSET_STEAM = "steam_set_temp"
TSET_COFFEE = "coffee_set_temp"
DOSE_K1 = "dose_k1"
DOSE_K2 = "dose_k2"
DOSE_K3 = "dose_k3"
DOSE_K4 = "dose_k4"
DOSE_K5 = "dose_k5"
DOSE_TEA = "dose_tea"
ENABLE_PREBREWING = "enable_prebrewing"
PREBREWING_TON_K1 = "prebrewing_ton_k1"
PREBREWING_TON_K2 = "prebrewing_ton_k2"
PREBREWING_TON_K3 = "prebrewing_ton_k3"
PREBREWING_TON_K4 = "prebrewing_ton_k4"
PREBREWING_TOFF_K1 = "prebrewing_toff_k1"
PREBREWING_TOFF_K2 = "prebrewing_toff_k2"
PREBREWING_TOFF_K3 = "prebrewing_toff_k3"
PREBREWING_TOFF_K4 = "prebrewing_toff_k4"
DRINKS_K1 = "drinks_k1"
DRINKS_K2 = "drinks_k2"
DRINKS_K3 = "drinks_k3"
DRINKS_K4 = "drinks_k4"
CONTINUOUS = "continuous"
TOTAL_COFFEE = "total_coffee"
HOT_WATER = "hot_water"
DRINK_MYSTERY = "drink_mystery"
TOTAL_DRINKS = "total_drinks"
HOT_WATER_2 = "hot_water_2"
DRINKS_TEA = "drinks_tea"

FIRMWARE_VER = "firmware_ver"
MODULE_SER_NUM = "module_ser_num"

UPDATE_AVAILABLE = "update_available"

SUN_ON = "sun_on"
SUN_OFF = "sun_off"
MON_ON = "mon_on"
MON_OFF = "mon_off"
TUE_ON = "tue_on"
TUE_OFF = "tue_off"
WED_ON = "wed_on"
WED_OFF = "wed_off"
THU_ON = "thu_on"
THU_OFF = "thu_off"
FRI_ON = "fri_on"
FRI_OFF = "fri_off"
SAT_ON = "sat_on"
SAT_OFF = "sat_off"

AUTO_BITFIELD = "auto_bitfield"
GLOBAL_AUTO = "global_auto"
SUN_AUTO = "sun"
MON_AUTO = "mon"
TUE_AUTO = "tue"
WED_AUTO = "wed"
THU_AUTO = "thu"
FRI_AUTO = "fri"
SAT_AUTO = "sat"

SECOND = "second"
MINUTE = "minute"
HOUR = "hour"
DAYOFWEEK = "dayofweek"
DAY = "day"
MONTH = "month"
YEAR = "month"

FLOW_MYSTERY = "flow_mystery"
FLOW_PULSES = "flow_pulses"
FLOW_SECONDS = "flow_seconds"

WRITE_RESULT = "write_result"
MACHINE_SER_NUM = "machine_ser_num"

"""Data Types"""
TYPE_MAIN = 1
TYPE_PREBREW = 2
TYPE_AUTO_ON_OFF = 3
TYPE_COFFEE_TEMP = 4
TYPE_STEAM_TEMP = 5
TYPE_DRINK_STATS = 6

DIVIDE_KEYS = ["tset", "temp", "prebrewing_k"]
SERIAL_NUMBERS = [MACHINE_SER_NUM, MODULE_SER_NUM]

# Response Maps
class Elem:

    INT = 0
    STRING = 1

    def __init__(self, index, size=1, type=INT):
        self._index = index
        self._size = size
        self._type = type

    @property
    def index(self):
        return self._index

    @property
    def size(self):
        return self._size

    @property
    def type(self):
        return self._type


# R
# 40 1C 00 04: Message
# 03 BC: Coffee Temp (95.6C)
# 04 D8: Steam Temp (124.0C)
# B6: Check byte

TEMP_REPORT_MAP = {Elem(0, 2): TEMP_COFFEE, Elem(2, 2): TEMP_STEAM}

# R
# 40 00 00 20: Message
# 01
# 78: Version (1.20)
# 02
# 53 6E XX XX XX XX XX XX XX XX XX XX: Module serial number (SnXXXXXXXXXX)
# 00: ?? sometimes 01
# 00 00 00 00 00 00 00
# 27: 01: Power (ON)
# 01 00 00 00
# 32: 02 96: Coffee Temp (66.2C)
# 34: 03 2A: Steam Temp (81.0C)
# 70: Check byte

STATUS_MAP = {
    Elem(1, 1): FIRMWARE_VER,
    Elem(3, 12, type=Elem.STRING): MODULE_SER_NUM,
    Elem(23, 1): POWER,
    # Elem(32, 2): TEMP_COFFEE,
    # Elem(34, 2): TEMP_STEAM,
}

# R
# 00 00 00 1F: Preamble
# 01 00 00 02 6E 31 39
# 11: 03 C7: Coffee Temp Set (96.7C)
# 13: 04 D9: Steam Temp Set (124.1C)
# 15: 00: Prebrewing ON (off)
# 16: 00: B1 Prebrewing ON
# 17: 00: B2 Prebrewing ON
# 18: 00: B3 Prebrewing ON
# 19: 0A: B4 Prebrewing ON (1.0s)
# 20: 00: B1 Prebrewing Off
# 21: 00: B2 Prebrewing Off
# 22: 00: B3 Prebrewing Off
# 23: 00: B4 Prebrewing Off
# 24: 0078: Dose B1
# 26: 0076: Dost B2
# 28: 0078: Dose B3
# 30: 0085: Dose B4
# 32: 03E8: Dose B5
# 34: 08: Seconds hot water for Tea
# 35: Check byte

CONFIG_MAP = {
    Elem(7, 2): TSET_COFFEE,
    Elem(9, 2): TSET_STEAM,
    Elem(11): ENABLE_PREBREWING,
    Elem(12): PREBREWING_TON_K1,
    Elem(13): PREBREWING_TON_K2,
    Elem(14): PREBREWING_TON_K3,
    Elem(15): PREBREWING_TON_K4,
    Elem(16): PREBREWING_TOFF_K1,
    Elem(17): PREBREWING_TOFF_K2,
    Elem(18): PREBREWING_TOFF_K3,
    Elem(19): PREBREWING_TOFF_K4,
    Elem(20, 2): DOSE_K1,
    Elem(22, 2): DOSE_K2,
    Elem(24, 2): DOSE_K3,
    Elem(26, 2): DOSE_K4,
    Elem(28, 2): DOSE_K5,
    Elem(30): DOSE_TEA,
}

# Response to R 03 10 00 1D EB

# R
# 03 10 00 1D: Message
# 4: FE: Bitfield for auto on/off, where upper bits are the days bit 0 is auto on/off (disabled)
# 5: 06: Sunday on hour
# 6: 11: Sunday off hour (5pm)
# 7: 06: Monday on hour
# 8: 11: Monday off hour (5pm)
# 9: 06: Tuesday on hour
# 10: 11: Tuesday off hour (5pm)
# 11: 06: Wednesday on hour
# 12: 11: Wednesday off hour (5pm)
# 13: 06: Thursday on hour
# 14: 11: Thursday off hour (5pm)
# 15: 06: Friday on hour
# 16: 11: Friday off hour (5pm)
# 17: 06: Saturday on hour
# 18: 11: Saturday off hour (5pm)
# 00 00 00 00 00 00 00 00 00 00 00 00 00 00
# 2E: Check byte

AUTO_SCHED_MAP = {
    Elem(0): AUTO_BITFIELD,
    Elem(1): SUN_ON,
    Elem(2): SUN_OFF,
    Elem(3): MON_ON,
    Elem(4): MON_OFF,
    Elem(5): TUE_ON,
    Elem(6): TUE_OFF,
    Elem(7): WED_ON,
    Elem(8): WED_OFF,
    Elem(9): THU_ON,
    Elem(10): THU_OFF,
    Elem(11): FRI_ON,
    Elem(12): FRI_OFF,
    Elem(13): SAT_ON,
    Elem(14): SAT_OFF,
}

AUTO_BITFIELD_MAP = {
    0: GLOBAL_AUTO,
    1: MON_AUTO,
    2: TUE_AUTO,
    3: WED_AUTO,
    4: THU_AUTO,
    5: FRI_AUTO,
    6: SAT_AUTO,
    7: SUN_AUTO,
}

# W: Write
# 00 00 00 01 : Message
# OK: Result
# 72: Check byte

WRITE_RESULT_MAP = {
    Elem(0, 1, type=Elem.STRING): WRITE_RESULT,
}

# App: R 01 00 00 11 D5
# Machine:
# R
# 01 00 00 11: Read machine serial number
# 5A: Z (?)
# XX XX XX XX XX XX XX XX 00 00 00 00 00 00 00 00: Machine serial number
# 7D: Check byte

SER_NUM_MAP = {
    Elem(1, 16, type=Elem.STRING): MACHINE_SER_NUM,
}

# R
# 03000007
# 00: Second (00)
# 05: Minute (5)
# 0A: Hour (10)
# 02: Day of week (2)
# 16: Day (22)
# 0C: Month (12)
# 14: Year (20)
# B3: Check byte

DATETIME_MAP = {
    Elem(0, 1): SECOND,
    Elem(1, 1): MINUTE,
    Elem(2, 1): HOUR,
    Elem(3, 1): DAYOFWEEK,
    Elem(4, 1): DAY,
    Elem(5, 1): MONTH,
    Elem(6, 1): YEAR,
}

# R
# 0020002C
# 0000014A: Key 1 (1 espresso)
# 00000096: Key 2 (2 espressos) * 2 = 0x12C
# 000001B0: Key 3 (1 coffee)
# 00000021: Key 4 (2 coffees) * 2 = 0x42
# 00000563: Flushing
# 00000914: From Coffee boiler (total of above)
# 00000010: Tea
# 0000000A: ?? Doesn't seem to change
# 00000ADE: ?? Increments every button press
# 00000010: Also Tea?
# 00000032: # Tea, if you let it finish

DRINK_STATS_MAP = {
    Elem(0, 4): DRINKS_K1,
    Elem(4, 4): DRINKS_K2,
    Elem(8, 4): DRINKS_K3,
    Elem(12, 4): DRINKS_K4,
    Elem(16, 4): CONTINUOUS,
    Elem(20, 4): TOTAL_COFFEE,
    Elem(24, 4): HOT_WATER,
    Elem(28, 4): DRINK_MYSTERY,
    Elem(32, 4): TOTAL_DRINKS,
    Elem(36, 4): HOT_WATER_2,
    Elem(40, 4): DRINKS_TEA,
}

GATEWAY_DRINK_MAP = {
    -1: HOT_WATER_OFFSET,
    0: DRINKS_K1_OFFSET,
    1: DRINKS_K2_OFFSET,
    2: DRINKS_K3_OFFSET,
    3: DRINKS_K4_OFFSET,
    4: CONTINUOUS_OFFSET,
}

DRINK_OFFSET_MAP = {
    HOT_WATER: HOT_WATER_OFFSET,
    DRINKS_K1: DRINKS_K1_OFFSET,
    DRINKS_K2: DRINKS_K2_OFFSET,
    DRINKS_K3: DRINKS_K3_OFFSET,
    DRINKS_K4: DRINKS_K4_OFFSET,
    CONTINUOUS: CONTINUOUS_OFFSET,
}

# Z
# 60000016
# Snxxxxxxxxxx
# 0401: Mystery
# 0009: Pulses
# 000C: Seconds (upper 12 bits are whole seconds, lower 4 bits are fractional)
# 03B6: Coffee boiler temp
# 04D4: Steam boiler temp
# DC: Check byte

WATER_FLOW_MAP = {
    Elem(12, 2): FLOW_MYSTERY,
    Elem(14, 2): FLOW_PULSES,
    Elem(16, 2): FLOW_SECONDS,
    # Elem(18, 2): TEMP_COFFEE,
    # Elem(20, 2): TEMP_STEAM,
}


class Msg:
    GET_STATUS = 0
    GET_CONFIG = 1
    GET_AUTO_SCHED = 2
    SET_POWER = 3
    GET_TEMP_REPORT = 4
    SET_AUTO_ON = 4
    SET_AUTO_OFF = 5
    GET_SER_NUM = 6
    GET_DATETIME = 7
    SET_COFFEE_TEMP = 8
    SET_STEAM_TEMP = 9
    SET_PREBREWING_ENABLE = 10
    SET_AUTO_SCHED = 11
    SET_DOSE = 12
    SET_DOSE_TEA = 13
    SET_PREBREW_TIMES = 14
    GET_DRINK_STATS = 15
    GET_WATER_FLOW = 16

    """Dose command starts at 0x14 for the first key and increments by 2 thereafter"""
    DOSE_KEY_BASE = 0x14

    """Prebrew on base"""
    PREBREW_ON_BASE = 0x0C

    """Prebrew off base"""
    PREBREW_OFF_BASE = 0x10

    READ = "R"
    WRITE = "W"
    STREAM = "Z"

    RESPONSE_GOOD = "OK"

    def __init__(self, msg_type, msg, map):
        """Init command"""
        self._msg_type = msg_type
        self._msg = msg
        self._map = map

    @property
    def msg_type(self):
        """Command type"""
        return self._msg_type

    @property
    def msg(self):
        """Command type"""
        return self._msg

    @property
    def map(self):
        """Return map if we should decode, None if not"""
        return self._map


MSGS = {
    # Reads
    Msg.GET_STATUS: Msg(Msg.READ, "40000020", STATUS_MAP),
    Msg.GET_CONFIG: Msg(Msg.READ, "0000001F", CONFIG_MAP),
    Msg.GET_AUTO_SCHED: Msg(Msg.READ, "0310001D", AUTO_SCHED_MAP),
    Msg.GET_TEMP_REPORT: Msg(Msg.READ, "401C0004", TEMP_REPORT_MAP),
    Msg.GET_SER_NUM: Msg(Msg.READ, "01000011", SER_NUM_MAP),
    Msg.GET_DATETIME: Msg(Msg.READ, "03000007", DATETIME_MAP),
    Msg.GET_DRINK_STATS: Msg(Msg.READ, "0020002C", DRINK_STATS_MAP),
    Msg.GET_WATER_FLOW: Msg(Msg.STREAM, "60000016", WATER_FLOW_MAP),
    # Writes
    Msg.SET_POWER: Msg(Msg.WRITE, "00000001", WRITE_RESULT_MAP),
    Msg.SET_COFFEE_TEMP: Msg(Msg.WRITE, "00070002", WRITE_RESULT_MAP),
    Msg.SET_STEAM_TEMP: Msg(Msg.WRITE, "00090002", WRITE_RESULT_MAP),
    Msg.SET_PREBREWING_ENABLE: Msg(Msg.WRITE, "000B0001", WRITE_RESULT_MAP),
    Msg.SET_AUTO_SCHED: Msg(Msg.WRITE, "0310001D", WRITE_RESULT_MAP),
    # Write config for keys (second byte is base + the key number and will be replaced)
    Msg.SET_DOSE: Msg(Msg.WRITE, "00140002", WRITE_RESULT_MAP),
    Msg.SET_DOSE_TEA: Msg(Msg.WRITE, "001E0001", WRITE_RESULT_MAP),
    Msg.SET_PREBREW_TIMES: Msg(Msg.WRITE, "000C0001", WRITE_RESULT_MAP),
}
