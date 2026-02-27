from enum import StrEnum, IntEnum


class ChannelOrientation(StrEnum):
    """Enumeration for channel orientations. This enum defines the possible orientations
    for seismic data channels, which can be vertical, north, or east.
    It is used in the Channel model to specify the orientation of each channel
    """
    VERTICAL = 'vertical'
    NORTH = 'north'
    EAST = 'east'


class PGA(IntEnum):
    PGA_1 = 0   # ± 5 V
    PGA_2 = 1   # ± 2.5 V
    PGA_4 = 2   # ± 1.25 V
    PGA_8 = 3   # ± 625 mV
    PGA_16 = 4  # ± 312.5 mV
    PGA_32 = 5  # ± 156.25 mV
    PGA_64 = 6  # ± 78.125 mV


class DataRate(IntEnum):
    DRATE_2SPS = 0      # 3
    DRATE_5SPS = 1      # 19
    DRATE_10SPS = 2     # 35
    DRATE_15SPS = 3     # 51
    DRATE_25SPS = 4     # 67
    DRATE_30SPS = 5     # 83
    DRATE_50SPS = 6     # 99
    DRATE_60SPS = 7     # 114
    DRATE_100SPS = 8    # 130
    DRATE_500SPS = 9    # 146
    DRATE_1000SPS = 10  # 161
    DRATE_2000SPS = 11  # 176
    DRATE_3750SPS = 12  # 192
    DRATE_7500SPS = 13  # 208
    DRATE_15000SPS = 14 # 224
    DRATE_30000SPS = 15 # 240
