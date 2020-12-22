"""Local API commands for La Marzocco espresso machines"""
import logging, asyncio
from functools import partial
from datetime import datetime

RESPONSE_GOOD = "OK"

# Response Maps
class Element:
    def __init__(self, index, size=1):
        self._index = index
        self._size = size

    @property
    def index(self):
        return self._index

    @property
    def size(self):
        return self._size


# R
# 40 1C 00 04: Preamble
# 03 BC: Coffee Temp (95.6C)
# 04 D8: Steam Temp (124.0C)
# B6: Check byte

TEMP_REPORT_MAP = {Element(4, 2): "TEMP_COFFEE", Element(6, 2): "TEMP_STEAM"}

# R
# 40 00 00 20: Preamble
# 01 78 02
# 53 6E 31 39 31 32 30 30 30 34 39 32 00 00 00 00 00 00 00 00
# 27: 01: Power (ON)
# 01 00 00 00
# 32: 02 96: Coffee Temp (66.2C)
# 34: 03 2A: Steam Temp (81.0C)
# 70: Check byte

STATUS_MAP = {
    Element(27, 1): "MACHINE_STATUS",
    # Element(32, 2): "TEMP_COFFEE",
    # Element(34, 2): "TEMP_STEAM",
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
    Element(11, 2): "TSET_COFFEE",
    Element(13, 2): "TSET_STEAM",
    Element(15): "ENABLE_PREBREWING",
    Element(16): "TON_PREBREWING_K1",
    Element(17): "TON_PREBREWING_K2",
    Element(18): "TON_PREBREWING_K3",
    Element(19): "TON_PREBREWING_K4",
    Element(20): "TOFF_PREBREWING_K1",
    Element(21): "TOFF_PREBREWING_K2",
    Element(22): "TOFF_PREBREWING_K3",
    Element(23): "TOFF_PREBREWING_K4",
    Element(24, 2): "DOSE_K1",
    Element(26, 2): "DOSE_K2",
    Element(28, 2): "DOSE_K3",
    Element(30, 2): "DOSE_K4",
    Element(32, 2): "DOSE_K5",
    Element(34): "DOSE_TEA",
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
    Element(4): "AUTO_BITFIELD",
    Element(5): "SUN_ON",
    Element(6): "SUN_OFF",
    Element(7): "MON_ON",
    Element(8): "MON_OFF",
    Element(9): "TUE_ON",
    Element(10): "TUE_OFF",
    Element(11): "WED_ON",
    Element(12): "WED_OFF",
    Element(13): "THU_ON",
    Element(14): "THU_OFF",
    Element(15): "FRI_ON",
    Element(16): "FRI_OFF",
    Element(17): "SAT_ON",
    Element(18): "SAT_OFF",
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


class Msg:
    STATUS = 0
    CONFIG = 1
    AUTO_SCHED = 2
    POWER = 3
    TEMP_REPORT = 4
    SET_AUTO_ON = 4
    SET_AUTO_OFF = 5

    POWER_ON_DATA = "01"
    POWER_OFF_DATA = "00"

    READ = "R"
    WRITE = "W"

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
    Msg.POWER: Msg(Msg.WRITE, "00000001", None),
    Msg.TEMP_REPORT: Msg(Msg.READ, "401C0004", TEMP_REPORT_MAP),
}