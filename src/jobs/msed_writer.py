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
    """
    Thread that buffers incoming seismic data packets and writes them to MiniSEED files at
    regular intervals. It also handles earthquake events by ensuring that a file is saved
    immediately when an event is detected, and then continues with the regular saving schedule.
    """
    def __init__(
        self,
        settings: Settings,
        data_queue: Queue,
        output_dir: Path,
        shutdown_event: Event,
        earthquake_event: Event,
        write_interval_sec: int = 1800
    ):
        super().__init__()
        self.settings = settings
        self.data_queue = data_queue
        self.output_dir = output_dir
        self.write_interval_sec = write_interval_sec
        self.shutdown_event = shutdown_event
        self.earthquake_event = earthquake_event

        # Buffer structure: { channel_name: [value1, value2, ...] }
        self._buffer = {}
        # Track the start time of the current batch
        self._start_time = None
        self._recording_until = None
        self.is_processing_event = False

    def run(self):
        next_write_time = time.time() + self.write_interval_sec

        while not self.shutdown_event.is_set():
            now = time.time()

            # collect data from the queue
            try:
                while True:
                    # Expecting: {"timestamp": float, "measurements": [{"channel": obj, "value": int}, ...]}
                    packet = self.data_queue.get_nowait()

                    ts = packet["timestamp"]

                    # Set the start time for this file if it's a new buffer
                    if not self._buffer:
                        self._start_time = ts

                    for item in packet["measurements"]:
                        ch_name = item["channel"].name
                        val = item["value"]

                        if ch_name not in self._buffer:
                            self._buffer[ch_name] = []

                        self._buffer[ch_name].append(val)

                    self.data_queue.task_done()
            except Empty:
                pass

            # We only trigger this if we aren't already in an EQ countdown
            if self.earthquake_event.is_set():
                # Force the next write to happen in exactly 300 seconds
                next_write_time = now + 300

                if not self.is_processing_event:
                    self.is_processing_event = True
                    logger.warning("Earthquake detected! Saving file in 5 minutes.")
                else:
                    logger.warning("New earthquake detected during countdown! Resetting timer to 5 minutes.")

            # Check if it's time to write (Scheduled OR Earthquake deadline)
            if now >= next_write_time:
                self._write_mseed()

                # Reset for next interval
                next_write_time = now + self.write_interval_sec
                self.is_processing_event = False

            time.sleep(0.01)

        # final write on shutdown
        self._write_mseed()

    def _write_mseed(self):
        if not self._buffer or self._start_time is None:
            return

        logger.info("Writing batch to MiniSEED (%d channels)...", len(self._buffer))
        self.output_dir.mkdir(parents=True, exist_ok=True)

        stream = Stream()

        for ch_name, values in self._buffer.items():
            if not values:
                continue

            # Create Trace
            # Using int32 or float32 depending on your ADC precision
            trace = Trace(data=np.array(values, dtype=np.float32))

            # Header Info
            trace.stats.starttime = UTCDateTime(self._start_time)
            trace.stats.sampling_rate = self.settings.sampling_rate
            trace.stats.channel = ch_name
            trace.stats.station = self.settings.station
            trace.stats.network = self.settings.network

            stream.append(trace)

        if stream:
            # Generate filename based on actual data start time
            triggered = "EQ_" if self.is_processing_event else "" 
            timestamp_str = UTCDateTime(self._start_time).strftime('%Y%m%dT%H%M%S')
            filename = self.output_dir / f"data_{triggered}_{timestamp_str}.mseed"

            # Write to disk
            stream.write(str(filename), format='MSEED')
            logger.info("File saved: %s", filename)

        # Reset state for next interval
        self._buffer.clear()
        self._start_time = None
