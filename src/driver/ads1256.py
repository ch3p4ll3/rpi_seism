from logging import getLogger

from src.driver.enums import ScanMode, Gain, Reg, Commands, DataRate
from src.settings import Settings
from src.driver.spi import SPI

logger = getLogger(__name__)


class ADS1256:
    """
    A class for interacting with ADS1256
    """
    def __init__(self, settings: Settings, gain: Gain=Gain.ADS1256_GAIN_1, data_rate: DataRate = DataRate.ADS1256_30000SPS):
        """
        Instantiate an ADS1256 class
        
        :param settings: The settings
        :type settings: Settings
        :param gain: The gain at which the PGA will be set. Default = 1
        :type gain: Gain
        :param data_rate: The data rate at which the ADS1256 will sample data. Default = 30000SPS
        :type data_rate: DataRate
        """
        self.pwdn_pin = settings.spi.pwdn_pin
        self.cs_pin = settings.spi.cs_pin
        self.drdy_pin = settings.spi.drdy_pin

        self.spi = SPI(settings)

        self.scan_mode = ScanMode.SINGLE_ENDED_INPUT
        self.gain = gain
        self.data_rate = data_rate

    def __enter__(self):
        self.ADS1256_init()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.spi.module_exit()

    # Hardware reset
    def __reset(self):
        logger.debug("Resetting ADS1256")
        self.spi.digital_write(self.pwdn_pin, 0)
        self.spi.delay_ms(200)
        self.spi.digital_write(self.pwdn_pin, 1)
        self.__write_cmd(Commands.RESET)

    def __write_cmd(self, cmd: Commands):
        self.spi.digital_write(self.cs_pin, 0)  #cs  0
        self.spi.spi_writebyte([cmd.value])
        self.spi.digital_write(self.cs_pin, 1)  #cs 1

    def __write_reg(self, reg: Reg, data):
        self.spi.digital_write(self.cs_pin, 0)  #cs  0
        self.spi.spi_writebyte([Commands.WREG.value | reg.value, 0x00, data])
        self.spi.digital_write(self.cs_pin, 1)  #cs 1

    def __read_data(self, reg: Reg):
        self.spi.digital_write(self.cs_pin, 0)#cs  0
        self.spi.spi_writebyte([Commands.RREG.value | reg.value, 0x00])
        data = self.spi.spi_readbytes(1)
        self.spi.digital_write(self.cs_pin, 1)  #cs 1

        return data

    def __wait_drdy(self):
        for i in range(0,400000,1):
            if self.spi.digital_read(self.drdy_pin) == 0:
                break

        if i >= 400000:
            logger.warninging("DRDY timed out")
    
    def __set_channel(self, channel):
        """
        Docstring for set_channel
        
        :param channel: Description
        """
        if channel > 7:
            return 0
        self.__write_reg(Reg.MUX, (channel<<4) | (1<<3))

    def __set_diff_channel(self, channel: int):
        match channel:
            case 0:
                self.__write_reg(Reg.MUX, (0 << 4) | 1) # differential channel AIN0-AIN1
            case 1:
                self.__write_reg(Reg.MUX, (2 << 4) | 3) # differential channel AIN2-AIN3
            case 2:
                self.__write_reg(Reg.MUX, (4 << 4) | 5) # differential channel AIN4-AIN5
            case 3:
                self.__write_reg(Reg.MUX, (6 << 4) | 7) # differential channel AIN6-AIN7

    def __read_adc_data(self):
        self.__wait_drdy()
        self.spi.digital_write(self.cs_pin, 0)  #cs  0
        self.spi.spi_writebyte([Commands.RDATA.value])
        # self.spi.delay_ms(10)

        buf = self.spi.spi_readbytes(3)
        self.spi.digital_write(self.cs_pin, 1)  #cs 1
        read = (buf[0]<<16) & 0xff0000
        read |= (buf[1]<<8) & 0xff00
        read |= (buf[2]) & 0xff
        if read & 0x800000:
            read &= 0xF000000
        return read

    def read_chip_id(self):
        """
        Reads chip ID
        """
        self.__wait_drdy()
        chip_id = self.__read_data(Reg.STATUS)
        chip_id = chip_id[0] >> 4
        # print 'ID',id
        return chip_id

    #The configuration parameters of ADC, gain and data rate
    def config_adc(self, gain: Gain, drate: DataRate):
        """
        Configure the ADC settings before starting sampling
        
        :param gain: The gain to set the internal PGA
        :type gain: Gain
        :param drate: The datarate at which the ADS1256 will read a sample
        :type drate: DataRate
        """
        self.__wait_drdy()
        buf = [0,0,0,0,0,0,0,0]
        buf[0] = (0<<3) | (1<<2) | (0<<1)
        buf[1] = 0x08
        buf[2] = (0<<5) | (0<<3) | (gain.value<<0)
        buf[3] = drate.value

        self.spi.digital_write(self.cs_pin, 0)  #cs  0
        self.spi.spi_writebyte([Commands.WREG.value | 0, 0x03])
        self.spi.spi_writebyte(buf)

        self.spi.digital_write(self.cs_pin, 1)  #cs 1
        self.spi.delay_ms(1)

    def set_mode(self, mode: ScanMode):
        """
        Set sampling mode
        
        :param mode: Single-ended or differential mode
        :type mode: ScanMode
        """
        self.scan_mode = mode

    def ADS1256_init(self):
        """
        Initialize the module and check chip ID
        """
        if (self.spi.module_init() != 0):
            return -1
        self.__reset()
        chip_id = self.read_chip_id()
        if chip_id == 3 :
            logger.debug("ID read success")
        else:
            logger.warning("ID read failed. Chip ID: %d", chip_id)
            return -1
        self.config_adc(self.gain, self.data_rate)
        return 0

    def get_channel_value(self, channel: int):
        """
        Read a single channel
        
        :param channel: Description
        :type channel: int
        """
        if self.scan_mode == ScanMode.SINGLE_ENDED_INPUT: # SINGLE_ENDED_INPUT = 8 channels. DIFFERENTIAL_INPUT = 4 channels
            if channel >= 8:
                return 0

            self.__set_channel(channel)
            self.__write_cmd(Commands.SYNC)
            # self.spi.delay_ms(10)
            self.__write_cmd(Commands.WAKEUP)
            # self.spi.delay_ms(200)
            value = self.__read_adc_data()

        else:
            if channel >= 4:
                return 0
            self.__set_diff_channel(channel)
            self.__write_cmd(Commands.SYNC)
            # self.spi.delay_ms(10)
            self.__write_cmd(Commands.WAKEUP)
            # self.spi.delay_ms(10)
            value = self.__read_adc_data()

        return value

    def get_all_channels(self):
        """
        read all channels
        """
        value = [0,0,0,0,0,0,0,0]
        for i in range(0,8,1):
            value[i] = self.get_channel_value(i)
        return value
