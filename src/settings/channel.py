from .enums import ChannelOrientation

from pydantic import BaseModel


class Channel(BaseModel):
    name: str
    adc_channel: int
    orientation: ChannelOrientation
    gain: int
    sensitivity: float  # V/(m/s)
