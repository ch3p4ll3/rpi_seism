import time
from threading import Thread, Event
from queue import Queue

from src.settings import Settings
from src.settings.channel import Channel
from src.driver.ads1256 import ADS1256
from src.driver.enums import ScanMode


class Reader(Thread):
    def __init__(self, settings: Settings, queues: list[Queue], shutdown_event: Event):
        self.settings = settings
        self.shutdown_event = shutdown_event
        self._running = True

        self.queues = queues
        super().__init__()

    def run(self):
        interval_per_channel = 1.0 / self.settings.sampling_rate  # seconds per channel
        next_sample_time = time.perf_counter()  # start now

        try:
            with ADS1256(self.settings) as adc:
                while not self.shutdown_event.is_set():
                    timestamp = time.time()

                    for channel in self.settings.channels:
                        # Wait until the scheduled sample time
                        now = time.perf_counter()
                        sleep_time = next_sample_time - now
                        if sleep_time > 0:
                            time.sleep(sleep_time)

                        # Read ADC and convert to voltage
                        adc.set_mode(ScanMode.DifferentialInput if channel.use_differential_channel else ScanMode.SingleEndedInput)
                        adc_value = adc.get_channel_value(channel.adc_channel)

                        self.__update_queues(channel, adc_value, timestamp)

                        # Schedule next sample for this channel
                        next_sample_time += interval_per_channel

        except Exception as e:
            print(f"Reader thread exception: {e}")

    def __update_queues(self, channel: Channel, value: float, timestamp: int):
        for queue in self.queues:
            queue.put((channel, value, timestamp))
