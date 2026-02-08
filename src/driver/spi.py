import spidev
import lgpio
import time
from src.settings import Settings


class SPI():
    def __init__(self, settings: Settings):
        self.settings = settings
        # SPI device, bus = 0, device = 0
        self.spi = spidev.SpiDev(0, 0)
        # lgpio handle
        self.h = None

    def digital_write(self, pin, value):
        lgpio.gpio_write(self.h, pin, value)

    def digital_read(self, pin):
        return lgpio.gpio_read(self.h, pin)

    def delay_ms(self, delaytime):
        time.sleep(delaytime // 1000.0)

    def spi_writebyte(self, data):
        self.spi.writebytes(data)
        
    def spi_readbytes(self, reg):
        return self.spi.readbytes(reg)

    def module_init(self):
        self.h = lgpio.gpiochip_open(0)

        lgpio.gpio_claim_output(self.h, self.settings.spi.rst_pin)
        lgpio.gpio_claim_output(self.h, self.settings.spi.cs_dac_pin)
        lgpio.gpio_claim_output(self.h, self.settings.spi.cs_pin)
        lgpio.gpio_claim_input(self.h, self.settings.spi.drdy_pin)
        self.spi.max_speed_hz = 20000
        self.spi.mode = 0b01
        return 0

    def module_exit(self):
        """Clean up SPI and lgpio resources opened by module_init()."""
        try:
            if SPI:
                try:
                    self.spi.close()
                except Exception:
                    pass
            if self.h is not None:
                try:
                    lgpio.gpiochip_close(self.h)
                except Exception:
                    pass
                self.h = None
        except Exception:
            pass
