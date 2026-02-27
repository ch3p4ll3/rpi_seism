from enum import StrEnum


class ChannelOrientation(StrEnum):
    """Enumeration for channel orientations. This enum defines the possible orientations
    for seismic data channels, which can be vertical, north, or east.
    It is used in the Channel model to specify the orientation of each channel
    """
    VERTICAL = 'vertical'
    NORTH = 'north'
    EAST = 'east'
