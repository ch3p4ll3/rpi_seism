from threading import Thread, Event
from queue import Queue
from logging import getLogger

import time
import struct

import serial
from gpiozero.pins.mock import MockFactory
from gpiozero.exc import BadPinFactory
from gpiozero import OutputDevice, Device

from src.settings import Settings

logger = getLogger(__name__)


# < = little endian, B = uint8, i = int32
PACKET_FORMAT = "<BBiiiB"
PACKET_SIZE = struct.calcsize(PACKET_FORMAT)

class Reader(Thread):
    def __init__(self, port: str, settings: Settings, queues: list[Queue], shutdown_event: Event):
        """
        Thread that continuously reads from the RS-485 serial port,
        processes incoming packets, and distributes data to queues.
        """
        super().__init__()
        self.port = port
        self.settings = settings
        self.queues = queues
        self.shutdown_event = shutdown_event
        self.baudrate = 250000
        self.heartbeat_interval = 0.5  # Send pulse every 500ms
        self.last_heartbeat = 0

        # Initialize the DE/RE control pin
        # Set active_high=True (Standard for MAX485 DE pin)
        # initial_value=False (Start in Listen mode)
        try:
            self.max485_control = OutputDevice(5, active_high=True, initial_value=False)
        except BadPinFactory:
            Device.pin_factory = MockFactory()
            self.max485_control = OutputDevice(5, active_high=True, initial_value=False)
        
        self.channels = self.__map_channels()

    def run(self):
        try:
            with serial.Serial(self.port, self.baudrate, timeout=0.1) as ser:
                logger.info("Connected to RS-485 on %s at %d", self.port, self.baudrate)

                # Buffer to store incoming bytes
                buffer = bytearray()

                while not self.shutdown_event.is_set():
                    # send Heartbeat to keep Arduino streaming
                    if time.time() - self.last_heartbeat > self.heartbeat_interval:
                        self.max485_control.on()   # Switch MAX485 to Transmit
                        ser.write(b'\x01')         # Send pulse
                        ser.flush()                # Wait for bits to leave the UART
                        self.max485_control.off()  # Switch back to Listen immediately
                        self.last_heartbeat = time.time()

                    # read available data
                    if ser.in_waiting > 0:
                        buffer.extend(ser.read(ser.in_waiting))

                    # process buffer for packets
                    while len(buffer) >= PACKET_SIZE:
                        # Look for headers 0xAA 0xBB
                        if buffer[0] == 0xAA and buffer[1] == 0xBB:
                            packet_data = buffer[:PACKET_SIZE]
                            if self._verify_checksum(packet_data):
                                self._process_packet(packet_data)
                                del buffer[:PACKET_SIZE] # Remove processed packet
                            else:
                                logger.warning("Checksum failed, shifting buffer")
                                del buffer[0] # Slide window to find next header
                        else:
                            # Not a header, discard byte and keep looking
                            del buffer[0]

        except Exception:
            logger.exception("RS485 Reader exception")
        finally:
            logger.info("RS485 Reader stopped.")

    def _verify_checksum(self, data):
        # XOR all bytes except the last one (the checksum byte)
        calculated = 0
        for b in data[:-1]:
            calculated ^= b
        return calculated == data[-1]

    def _process_packet(self, data):
        # Unpack binary data
        # _, _ are the headers, ch0-ch2 are the values, _ is checksum
        _, _, ch0, ch1, ch2, _ = struct.unpack(PACKET_FORMAT, data)

        timestamp = time.time()

        packet = {
            "timestamp": timestamp,
            "measurements": [
                {"channel": self.channels.get(0), "value": ch0},
                {"channel": self.channels.get(1), "value": ch1},
                {"channel": self.channels.get(2), "value": ch2}
            ]
        }

        for q in self.queues:
            # Replicating your original tuple format
            q.put(packet)

    def __map_channels(self):
        return {
            i.adc_channel: i
            for i in self.settings.channels
        }
