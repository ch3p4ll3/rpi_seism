from src.driver.enums import ScanMode, Gain, Reg, Commands, DataRate
from src.settings import Settings
from src.driver.spi import SPI


class ADS1256:
    def __init__(self, settings: Settings):
        self.rst_pin = settings.spi.rst_pin
        self.cs_pin = settings.spi.cs_pin
        self.drdy_pin = settings.spi.drdy_pin

        self.spi = SPI(settings)

        self.scan_mode = ScanMode.SingleEndedInput
    
    def __enter__(self):
        self.ADS1256_init()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.spi.module_exit()

    # Hardware reset
    def __reset(self):
        self.spi.digital_write(self.rst_pin, 1)
        self.spi.delay_ms(200)
        self.spi.digital_write(self.rst_pin, 0)
        self.spi.delay_ms(200)
        self.spi.digital_write(self.rst_pin, 1)

    def __write_cmd(self, reg: Reg):
        self.spi.digital_write(self.cs_pin, 0)#cs  0
        self.spi.spi_writebyte([reg.value])
        self.spi.digital_write(self.cs_pin, 1)#cs 1

    def __write_reg(self, reg: Reg, data):
        self.spi.digital_write(self.cs_pin, 0)#cs  0
        self.spi.spi_writebyte([Commands.CMD_WREG.value | reg.value, 0x00, data])
        self.spi.digital_write(self.cs_pin, 1)#cs 1

    def __read_data(self, reg: Reg):
        self.spi.digital_write(self.cs_pin, 0)#cs  0
        self.spi.spi_writebyte([Commands.CMD_RREG.value | reg.value, 0x00])
        data = self.spi.spi_readbytes(1)
        self.spi.digital_write(self.cs_pin, 1)#cs 1

        return data

    def __wait_drdy(self):
        for i in range(0,400000,1):
            if self.spi.digital_read(self.drdy_pin) == 0:
                
                break
        if i >= 400000:
            print ("Time Out ...\r\n")

    def read_chip_id(self):
        self.__wait_drdy()
        id = self.__read_data(Reg.REG_STATUS)
        id = id[0] >> 4
        # print 'ID',id
        return id
        
    #The configuration parameters of ADC, gain and data rate
    def config_adc(self, gain: Gain, drate: DataRate):
        self.__wait_drdy()
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

    def set_channel(self, Channal):
        if Channal > 7:
            return 0
        self.__write_reg(Reg.REG_MUX, (Channal<<4) | (1<<3))

    def set_diff_channel(self, channel: int):
        match channel:
            case 0:
                self.__write_reg(Reg.REG_MUX, (0 << 4) | 1) 	#DiffChannal  AIN0-AIN1
            case 1:
                self.__write_reg(Reg.REG_MUX, (2 << 4) | 3) 	#DiffChannal   AIN2-AIN3
            case 2:
                self.__write_reg(Reg.REG_MUX, (4 << 4) | 5) 	#DiffChannal    AIN4-AIN5
            case 3:
                self.__write_reg(Reg.REG_MUX, (6 << 4) | 7) 	#DiffChannal   AIN6-AIN7

    def set_mode(self, mode: ScanMode):
        self.scan_mode = mode

    def ADS1256_init(self):
        if (self.spi.module_init() != 0):
            return -1
        self.__reset()
        id = self.read_chip_id()
        if id == 3 :
            print("ID Read success  ")
        else:
            print("ID Read failed   ")
            return -1
        self.config_adc(Gain.ADS1256_GAIN_1, DataRate.ADS1256_30000SPS)
        return 0
        
    def read_adc_data(self):
        self.__wait_drdy()
        self.spi.digital_write(self.cs_pin, 0)#cs  0
        self.spi.spi_writebyte([Commands.CMD_RDATA.value])
        # self.spi.delay_ms(10)

        buf = self.spi.spi_readbytes(3)
        self.spi.digital_write(self.cs_pin, 1)#cs 1
        read = (buf[0]<<16) & 0xff0000
        read |= (buf[1]<<8) & 0xff00
        read |= (buf[2]) & 0xff
        if (read & 0x800000):
            read &= 0xF000000
        return read
 
    def get_channel_value(self, channel: int):
        if self.scan_mode == ScanMode.SingleEndedInput:# 0  Single-ended input  8 channel1 Differential input  4 channe
            if channel >= 8:
                return 0

            self.set_channel(channel)
            self.__write_cmd(Commands.CMD_SYNC)
            # self.spi.delay_ms(10)
            self.__write_cmd(Commands.CMD_WAKEUP)
            # self.spi.delay_ms(200)
            value = self.read_adc_data()

        else:
            if channel >= 4:
                return 0
            self.set_diff_channel(channel)
            self.__write_cmd(Commands.CMD_SYNC)
            # self.spi.delay_ms(10) 
            self.__write_cmd(Commands.CMD_WAKEUP)
            # self.spi.delay_ms(10) 
            value = self.read_adc_data()
        return value

    def get_all_channels(self):
        value = [0,0,0,0,0,0,0,0]
        for i in range(0,8,1):
            value[i] = self.get_channel_value(i)
        return value
