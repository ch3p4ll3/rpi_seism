import time
from threading import Thread, Event
from queue import Queue
from logging import getLogger

from src.settings import Settings
from src.settings.channel import Channel
from src.driver.ads1256 import ADS1256
from src.driver.enums import ScanMode

logger = getLogger(__name__)


class Reader(Thread):
    def __init__(self, settings: Settings, queues: list[Queue], shutdown_event: Event):
        self.settings = settings
        self.shutdown_event = shutdown_event
        self.queues = queues

        super().__init__()

    def run(self):
        # We divide the interval by the number of channels to keep the cycle consistent
        num_channels = len(self.settings.channels)
        interval = 1.0 / self.settings.sampling_rate / num_channels

        start_time = time.perf_counter()

        try:
            with ADS1256(self.settings) as adc:
                # Optimized: Set mode once if all channels are same type
                # (Assuming differential for geophones)
                adc.set_mode(ScanMode.DIFFERENTIAL_INPUT if self.settings.use_differential_channel else ScanMode.SINGLE_ENDED_INPUT)

                samples_collected = 0

                while not self.shutdown_event.is_set():
                    timestamp = time.time()

                    for channel in self.settings.channels:
                        # Direct read - minimizing MUX switching overhead
                        adc_value = adc.get_channel_value(channel.adc_channel)
                        self.__update_queues(channel, adc_value, timestamp)

                    samples_collected += 1

                    # Precise Timing: Calculate sleep until the next 100Hz tick
                    next_tick = start_time + (samples_collected * interval)
                    sleep_time = next_tick - time.perf_counter()

                    if sleep_time > 0:
                        time.sleep(sleep_time)
                    else:
                        # If we are here, the RPi is falling behind!
                        logger.warning("RPi is falling behind!")

        except Exception as e:
            logger.exception(f"Reader thread exception: {e}", exc_info=True)
        finally:
            logger.debug(f"Recording finished. Total cycles: {samples_collected}")

    def __update_queues(self, channel: Channel, value: float, timestamp: float):
        for queue in self.queues:
            # Tip: Ensure your consumer queue handles data quickly 
            # so this thread doesn't block.
            queue.put((channel, value, timestamp))
