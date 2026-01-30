import time
from threading import Thread
from queue import Queue

from src.settings import Settings
from src.settings.channel import Channel
from src.driver.ad1256 import ADS1256


class Reader(Thread):
    def __init__(self, settings: Settings, queues: list[Queue]):
        self.adc = ADS1256(settings)
        self.settings = settings
        self._running = True

        self.queues = queues
        super().__init__()

    def run(self):
        interval_per_channel = 1.0 / self.settings.sampling_rate  # seconds per channel
        next_sample_time = time.perf_counter()  # start now

        self.__set_channels()

        try:
            while self._running:
                timestamp = time.time()

                for channel in self.settings.channels:
                    # Wait until the scheduled sample time
                    now = time.perf_counter()
                    sleep_time = next_sample_time - now
                    if sleep_time > 0:
                        time.sleep(sleep_time)

                    # Read ADC and convert to voltage
                    adc_value = self.adc.get_channel_value(channel.adc_channel)
                    voltage = adc_value * 5.0 / 0x7FFFFF  # scale to volts

                    self.__update_queues(channel, voltage, timestamp)

                    # Schedule next sample for this channel
                    next_sample_time += interval_per_channel

        except Exception as e:
            print(f"Reader thread exception: {e}")
    
    def __set_channels(self):
        for channel in self.settings.channels:
            if channel.use_differential_channel:
                self.adc.set_differential_channel(channel.adc_channel)

    def __update_queues(self, channel: Channel, value: float, timestamp: int):
        for queue in self.queues:
            queue.put((channel, value, timestamp))

    def stop(self):
        self._running = False
