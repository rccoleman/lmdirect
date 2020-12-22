"""Local API commands for La Marzocco espresso machines"""
import logging, asyncio
from functools import partial
from datetime import datetime

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
# 40 1C 00 04: Preamble
# 03 BC: Coffee Temp (95.6C)
# 04 D8: Steam Temp (124.0C)
# B6: Check byte

TEMP_REPORT_MAP = {Elem(0, 2): "TEMP_COFFEE", Elem(2, 2): "TEMP_STEAM"}

# R
# 40 00 00 20: Preamble
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
    Elem(1, 1): "FIRMWARE",
    Elem(3, 12, type=Elem.STRING): "MODULE_SER_NUM",
    Elem(23, 1): "MACHINE_STATUS",
    # Elem(32, 2): "TEMP_COFFEE",
    # Elem(34, 2): "TEMP_STEAM",
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
    Elem(7, 2): "TSET_COFFEE",
    Elem(9, 2): "TSET_STEAM",
    Elem(11): "ENABLE_PREBREWING",
    Elem(12): "TON_PREBREWING_K1",
    Elem(13): "TON_PREBREWING_K2",
    Elem(14): "TON_PREBREWING_K3",
    Elem(15): "TON_PREBREWING_K4",
    Elem(16): "TOFF_PREBREWING_K1",
    Elem(17): "TOFF_PREBREWING_K2",
    Elem(18): "TOFF_PREBREWING_K3",
    Elem(19): "TOFF_PREBREWING_K4",
    Elem(20, 2): "DOSE_K1",
    Elem(22, 2): "DOSE_K2",
    Elem(24, 2): "DOSE_K3",
    Elem(26, 2): "DOSE_K4",
    Elem(28, 2): "DOSE_K5",
    Elem(30): "DOSE_TEA",
}

# Response to R 03 10 00 1D EB

# R
# 03 10 00 1D: Preamble
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
    Elem(0): "AUTO_BITFIELD",
    Elem(1): "SUN_ON",
    Elem(2): "SUN_OFF",
    Elem(3): "MON_ON",
    Elem(4): "MON_OFF",
    Elem(5): "TUE_ON",
    Elem(6): "TUE_OFF",
    Elem(7): "WED_ON",
    Elem(8): "WED_OFF",
    Elem(9): "THU_ON",
    Elem(10): "THU_OFF",
    Elem(11): "FRI_ON",
    Elem(12): "FRI_OFF",
    Elem(13): "SAT_ON",
    Elem(14): "SAT_OFF",
}

AUTO_BITFIELD_MAP = {
    0: "GLOBAL_AUTO",
    1: "SUN_AUTO",
    2: "MON_AUTO",
    3: "TUE_AUTO",
    4: "WED_AUTO",
    5: "THU_AUTO",
    6: "FRI_AUTO",
    7: "SAT_AUTO",
}

# W: Write
# 00 00 00 01 : Message
# OK: Result
# 72: Check byte

POWER_MAP = {
    Elem(0, 1, type=Elem.STRING): "POWER_RESULT",
}

# App: R 01 00 00 11 D5
# Machine:
# R
# 01 00 00 11: Read machine serial number
# 5A: Z (?)
# XX XX XX XX XX XX XX XX 00 00 00 00 00 00 00 00: Machine serial number
# 7D: Check byte

SER_NUM_MAP = {
    Elem(1, 16, type=Elem.STRING): "MACHINE_SER_NUM",
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
    Elem(0, 1): "SECOND",
    Elem(1, 1): "MINUTE",
    Elem(2, 1): "HOUR",
    Elem(3, 1): "DAYOFWEEK",
    Elem(4, 1): "DAY",
    Elem(5, 1): "MONTH",
    Elem(6, 1): "YEAR",
}


class Msg:
    STATUS = 0
    CONFIG = 1
    AUTO_SCHED = 2
    POWER = 3
    TEMP_REPORT = 4
    SET_AUTO_ON = 4
    SET_AUTO_OFF = 5
    SER_NUM = 6
    DATETIME = 7

    POWER_ON_DATA = "01"
    POWER_OFF_DATA = "00"

    READ = "R"
    WRITE = "W"

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
    Msg.STATUS: Msg(Msg.READ, "40000020", STATUS_MAP),
    Msg.CONFIG: Msg(Msg.READ, "0000001F", CONFIG_MAP),
    Msg.AUTO_SCHED: Msg(Msg.READ, "0310001D", AUTO_SCHED_MAP),
    Msg.POWER: Msg(Msg.WRITE, "00000001", POWER_MAP),
    Msg.TEMP_REPORT: Msg(Msg.READ, "401C0004", TEMP_REPORT_MAP),
    Msg.SER_NUM: Msg(Msg.READ, "01000011", SER_NUM_MAP),
    Msg.DATETIME: Msg(Msg.READ, "03000007", DATETIME_MAP),
}
