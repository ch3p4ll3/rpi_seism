from enum import Enum


class ScanMode(Enum):
    """
    Scan mode for the ADS1256. Can be single-ended or differential
    """
    SINGLE_ENDED_INPUT = 0
    DIFFERENTIAL_INPUT = 1


class Gain(Enum):
    """
    The gain at which the ADS1256 will set it's PGA
    """
    ADS1256_GAIN_1 = 0  # GAIN   1
    ADS1256_GAIN_2 = 1	# GAIN   2
    ADS1256_GAIN_4 = 2	# GAIN   4
    ADS1256_GAIN_8 = 3	# GAIN   8
    ADS1256_GAIN_16 = 4 # GAIN  16
    ADS1256_GAIN_32 = 5 # GAIN  32
    ADS1256_GAIN_64 = 6 # GAIN  64


class DataRate(Enum):
    """
    The data rate at which the ADS1256 will sample
    """
    ADS1256_30000SPS = 0xF0 # reset the default values
    ADS1256_15000SPS = 0xE0
    ADS1256_7500SPS = 0xD0
    ADS1256_3750SPS = 0xC0
    ADS1256_2000SPS = 0xB0
    ADS1256_1000SPS = 0xA1
    ADS1256_500SPS = 0x92
    ADS1256_100SPS = 0x82
    ADS1256_60SPS = 0x72
    ADS1256_50SPS = 0x63
    ADS1256_30SPS = 0x53
    ADS1256_25SPS = 0x43
    ADS1256_15SPS = 0x33
    ADS1256_10SPS = 0x20
    ADS1256_5SPS = 0x13
    ADS1256_2D5SPS = 0x03

class Reg(Enum):
    """
    ADS1256 registry addresses
    """
    STATUS = 0  # x1H
    MUX = 1     # 01H
    ADCON = 2   # 20H
    DRATE = 3   # F0H
    IO = 4      # E0H
    OFC0 = 5    # xxH
    OFC1 = 6    # xxH
    OFC2 = 7    # xxH
    FSC0 = 8    # xxH
    FSC1 = 9    # xxH
    FSC2 = 10   # xxH

class Commands(Enum):
    """
    ADS1256 commands
    """
    WAKEUP = 0x00     # Completes SYNC and Exits Standby Mode 0000  0000 (00h)
    RDATA = 0x01      # Read Data 0000  0001 (01h)
    RDATAC = 0x03     # Read Data Continuously 0000   0011 (03h)
    SDATAC = 0x0F     # Stop Read Data Continuously 0000   1111 (0Fh)
    RREG = 0x10       # Read from REG rrr 0001 rrrr (1xh)
    WREG = 0x50       # Write to REG rrr 0101 rrrr (5xh)
    SELFCAL = 0xF0    # Offset and Gain Self-Calibration 1111    0000 (F0h)
    SELFOCAL = 0xF1   # Offset Self-Calibration 1111    0001 (F1h)
    SELFGCAL = 0xF2   # Gain Self-Calibration 1111    0010 (F2h)
    SYSOCAL = 0xF3    # System Offset Calibration 1111   0011 (F3h)
    SYSGCAL = 0xF4    # System Gain Calibration 1111    0100 (F4h)
    SYNC = 0xFC       # Synchronize the A/D Conversion 1111   1100 (FCh)
    STANDBY = 0xFD    # Begin Standby Mode 1111   1101 (FDh)
    RESET = 0xFE      # Reset to Power-Up Values 1111   1110 (FEh)
