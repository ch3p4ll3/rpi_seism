from pydantic import BaseModel


class Spi(BaseModel):
    pwdn_pin: int
    cs_pin: int
    drdy_pin: int
