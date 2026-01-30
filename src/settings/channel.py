from .enums import ChannelOrientation

from pydantic import BaseModel


class Channel(BaseModel):
    name: str
    adc_channel: int
    use_differential_channel: bool
    orientation: ChannelOrientation
    gain: int
    sensitivity: float  # V/(m/s)
