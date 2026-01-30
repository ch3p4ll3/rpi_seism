from logging import getLogger

from src.settings import Settings

from .spi_driver import SPIDriver
from .enums import ScanMode, ADCGain, DataRate, Registry, Commands


logger = getLogger(__name__)


class ADS1256:
    def __init__(self, settings: Settings):
        self.rst_pin = settings.spi.rst_pin
        self.cs_pin = settings.spi.cs_pin
        self.drdy_pin = settings.spi.drdy_pin

        self.scan_mode = ScanMode.SingleMode
        self.spi = SPIDriver(settings)

        self.__init_adc()

    def __init_adc(self):
        if self.spi.module_init() != 0:
            logger.error("Module init failed")
            raise Exception("Module init failed")

        self.reset()
        chip_id = self.read_chip_id()
        if chip_id == 3 :
            logger.debug("ID read success")
        else:
            logger.error("ID read failed")
            raise Exception("ID read failed")
        self.config_adc(ADCGain.GAIN_1, DataRate.DR_30000SPS)

    # Hardware reset
    def reset(self):
        self.spi.digital_write(self.rst_pin, 1)
        self.spi.delay_ms(200)
        self.spi.digital_write(self.rst_pin, 0)
        self.spi.delay_ms(200)
        self.spi.digital_write(self.rst_pin, 1)

    def write_cmd(self, reg):
        self.spi.digital_write(self.cs_pin, 0)#cs  0
        self.spi.spi_writebyte([reg])
        self.spi.digital_write(self.cs_pin, 1)#cs 1

    def write_reg(self, reg: Registry, data):
        self.spi.digital_write(self.cs_pin, 0)#cs  0
        self.spi.spi_writebyte([Commands.CMD_WREG.value | reg.value, 0x00, data])
        self.spi.digital_write(self.cs_pin, 1)#cs 1

    def read_data(self, reg):
        self.spi.digital_write(self.cs_pin, 0)#cs  0
        self.spi.spi_writebyte([Commands.CMD_RREG.value | reg, 0x00])
        data = self.spi.spi_readbytes(1)
        self.spi.digital_write(self.cs_pin, 1)#cs 1

        return data

    def wait_drdy(self):
        for i in range(0,400000,1):
            if self.spi.digital_read(self.drdy_pin) == 0:

                break
        if i >= 400000:
            logger.warning("Timed out")
            print ("Time Out ...\r\n")

    def read_chip_id(self):
        self.wait_drdy()
        id = self.read_data(Registry.REG_STATUS)
        id = id[0] >> 4
        # print 'ID',id
        return id

    #The configuration parameters of ADC, gain and data rate
    def config_adc(self, gain: ADCGain, drate: DataRate):
        self.wait_drdy()
        buf = [0,0,0,0,0,0,0,0]
        buf[0] = (0<<3) | (1<<2) | (0<<1)
        buf[1] = 0x08
        buf[2] = (0<<5) | (0<<3) | (gain.value<<0)
        buf[3] = drate.value

        self.spi.digital_write(self.cs_pin, 0)#cs  0
        self.spi.spi_writebyte([Commands.CMD_WREG.value | 0, 0x03])
        self.spi.spi_writebyte(buf)

        self.spi.digital_write(self.cs_pin, 1)#cs 1
        self.spi.delay_ms(1)

    def set_channel(self, channel):
        if channel > 7:
            return 0
        self.write_reg(Registry.REG_MUX, (channel<<4) | (1<<3))

    def set_differential_channel(self, channel):
        if channel == 0:
            self.write_reg(Registry.REG_MUX, (0 << 4) | 1) 	#Diffchannel  AIN0-AIN1
        elif channel == 1:
            self.write_reg(Registry.REG_MUX, (2 << 4) | 3) 	#Diffchannel   AIN2-AIN3
        elif channel == 2:
            self.write_reg(Registry.REG_MUX, (4 << 4) | 5) 	#Diffchannel    AIN4-AIN5
        elif channel == 3:
            self.write_reg(Registry.REG_MUX, (6 << 4) | 7) 	#Diffchannel   AIN6-AIN7

    def set_mode(self, mode: ScanMode):
        self.scan_mode = mode

    def read_ADC_data(self):
        self.wait_drdy()
        self.spi.digital_write(self.cs_pin, 0)#cs  0
        self.spi.spi_writebyte([Commands.CMD_RDATA.value])
        # config.delay_ms(10)

        buf = self.spi.spi_readbytes(3)
        self.spi.digital_write(self.cs_pin, 1)#cs 1
        read = (buf[0]<<16) & 0xff0000
        read |= (buf[1]<<8) & 0xff00
        read |= (buf[2]) & 0xff
        if read & 0x800000:
            read &= 0xF000000
        return read

    def get_channel_value(self, channel):
        if self.scan_mode == ScanMode.SingleMode:
            if channel >= 8:
                return 0
            self.set_channel(channel)
            self.write_cmd(Commands.CMD_SYNC.value)
            # config.delay_ms(10)
            self.write_cmd(Commands.CMD_WAKEUP.value)
            # config.delay_ms(200)
            value = self.read_ADC_data()
        else:
            if channel>=4:
                return 0
            self.set_differential_channel(channel)
            self.write_cmd(Commands.CMD_SYNC.value)
            # config.delay_ms(10) 
            self.write_cmd(Commands.CMD_WAKEUP.value)
            # config.delay_ms(10) 
            value = self.read_ADC_data()
        return value * 5.0 / 0x7fffff

    def get_all(self):
        for i in range(0,8,1):
            yield self.get_channel_value(i)

    def get_specific_channels(self, channels: list[int]):
        for i in channels:
            yield self.get_channel_value(i)
