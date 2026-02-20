from threading import Thread, Event
from queue import Queue, Empty
from collections import deque
from logging import getLogger
import json
import asyncio

import numpy as np
import websockets
from obspy import UTCDateTime, Trace

from src.settings import Settings


logger = getLogger(__name__)


class WebSocketSender(Thread):
    def __init__(
        self,
        settings: Settings,
        data_queue: Queue,
        shutdown_event: Event,
        earthquake_event: Event,
        host: str = "0.0.0.0",
        port: int = 8765
    ):
        super().__init__(daemon=True)
        self.data_queue = data_queue
        self.shutdown_event = shutdown_event
        self.earthquake_event = earthquake_event
        self.host = host
        self.port = port
        self._clients = set()

        self.settings = settings

        # Sliding Window Config
        self.window_size = self.settings.sampling_rate * 5  # 2.5s lookback for filter stability
        self.step_size = self.settings.sampling_rate    # Update every 0.5s

        # Buffers
        self.data_buffer = deque(maxlen=self.window_size)
        self.time_buffer = deque(maxlen=self.window_size)
        self.sample_counter = 0

    def run(self):
        asyncio.run(self._main_loop())

    async def _main_loop(self):
        async with websockets.serve(self._handle_connection, self.host, self.port):
            logger.debug("Downsampled Data Server started on ws://%s:%d", self.host, self.port)
            await self._producer_loop()

    async def _handle_connection(self, websocket):
        self._clients.add(websocket)
        try:
            await websocket.wait_closed()
        finally:
            self._clients.discard(websocket)

    async def _producer_loop(self):
        loop = asyncio.get_running_loop()
        
        while not self.shutdown_event.is_set():
            try:
                # Get raw point from queue
                item = await loop.run_in_executor(None, self.data_queue.get, True, 0.5)
                channel, value, timestamp = item
                
                # Add to sliding window
                self.data_buffer.append(float(value))
                self.time_buffer.append(timestamp)
                self.sample_counter += 1

                # Process every STEP_SIZE samples once window is primed
                if len(self.data_buffer) == self.window_size and (self.sample_counter % self.step_size == 0):
                    await self._process_and_broadcast(channel.name)
                
            except Empty:
                continue
            except Exception as e:
                logger.exception("Error in producer.", exc_info=True)

    async def _process_and_broadcast(self, channel_name):
        """Perform downsampling on the current window and send results."""
        # Convert deque to array for ObsPy
        data_array = np.array(self.data_buffer)
        
        # Create Trace
        tr = Trace(data=data_array)
        tr.stats.sampling_rate = self.settings.sampling_rate
        tr.stats.starttime = UTCDateTime(self.time_buffer[0])

        # Decimate (Apply Anti-Alias filter automatically)
        # We work on a copy to keep the raw buffer pristine
        tr_decimated = tr.copy()
        tr_decimated.decimate(self.settings.decimation_factor, no_filter=False)

        # Extract only the "new" samples since the last step
        # For Factor 4 and Step 100, we take the last 25 samples
        new_samples_count = int(self.step_size / self.settings.decimation_factor)
        downsampled_values = tr_decimated.data[-new_samples_count:]
        
        # We send the latest point or the whole new batch
        # Sending the whole batch is better for high-performance graphing
        message = json.dumps({
            "channel": channel_name,
            "timestamp": tr_decimated.stats.endtime.isoformat(),
            "fs": tr_decimated.stats.sampling_rate,
            "data": downsampled_values.tolist() 
        })

        await self._broadcast(message)

    async def _broadcast(self, message):
        if not self._clients:
            return
        dead_clients = set()
        send_tasks = [self._safe_send(ws, message, dead_clients) for ws in self._clients]
        if send_tasks:
            await asyncio.gather(*send_tasks)
        if dead_clients:
            self._clients.difference_update(dead_clients)

    async def _safe_send(self, websocket, message, dead_clients):
        try:
            await websocket.send(message)
        except Exception:
            dead_clients.add(websocket)
