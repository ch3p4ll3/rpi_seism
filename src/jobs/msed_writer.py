from threading import Thread, Event
import time
from queue import Queue, Empty
from pathlib import Path
from logging import getLogger

from obspy import Stream, Trace, UTCDateTime
import numpy as np

from src.settings import Settings

logger = getLogger(__name__)


class MSeedWriter(Thread):
    def __init__(self, settings: Settings, data_queue: Queue, output_dir: str, shutdown_event: Event, write_interval_sec: int = 1800):
        """
        Args:
            data_queue (Queue): Queue from which to get (Channel, value) tuples
            output_dir (str): Directory to save mseed files
            write_interval_sec (int): How often to write files (default 30 min)
        """
        super().__init__()
        self.settings = settings
        self.data_queue = data_queue
        self.output_dir = output_dir
        self.write_interval_sec = write_interval_sec
        self.shutdown_event = shutdown_event

        # Temporary storage: dict of channel_name -> list of (timestamp, value)
        self._buffer = {}

    def run(self):
        next_write_time = time.time() + self.write_interval_sec

        while not self.shutdown_event.is_set():
            now = time.time()

            # Collect data from the queue
            try:
                while True:  # drain the queue
                    channel, value, timestamp = self.data_queue.get_nowait()

                    if channel.name not in self._buffer:
                        self._buffer[channel.name] = []
                    self._buffer[channel.name].append((timestamp, value))

                    self.data_queue.task_done()
            except Empty:
                pass

            # Check if it's time to write a file
            if now >= next_write_time:
                self._write_mseed()
                next_write_time = now + self.write_interval_sec

            # Sleep a short while to avoid busy-waiting
            time.sleep(0.02)

        # Write any remaining data when stopping
        self._write_mseed()

    def _write_mseed(self):
        if not self._buffer:
            return

        output_dir = Path(self.output_dir)

        logger.debug(f"Writing {len(self._buffer)} channels to MiniSEED...")
        output_dir.mkdir(parents=True, exist_ok=True)
        stream = Stream()

        for channel_name, data_list in self._buffer.items():
            if not data_list:
                continue
            # Sort by timestamp just in case
            data_list.sort(key=lambda x: x[0])
            times, values = zip(*data_list)
            start_time = times[0]
            # Convert values to numpy array
            trace = Trace(data=np.array(values, dtype=np.float32))
            trace.stats.starttime = UTCDateTime(start_time)
            trace.stats.channel = channel_name
            trace.stats.sampling_rate = self.settings.sampling_rate
            trace.stats.station = self.settings.station
            trace.stats.network = self.settings.network
            stream.append(trace)

        if stream:
            filename = output_dir / f"data_{UTCDateTime().strftime('%Y%m%dT%H%M%S')}.mseed"
            stream.write(filename, format='MSEED')
            logger.debug(f"Written {filename}")

        # Clear buffer after writing
        self._buffer.clear()
