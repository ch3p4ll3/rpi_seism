import asyncio
import json
from threading import Thread, Event
from queue import Queue
from collections import deque

import websockets
import numpy as np
from obspy import Trace, UTCDateTime


class WebSocketSender(Thread):
    def __init__(self, data_queue: Queue, shutdown_event: Event, host: str = "localhost", port: int = 8765, downsample_rate: int = 10):
        """
        Args:
            data_queue (Queue): Queue from which data will be read (channel, value, timestamp)
            host (str): WebSocket server host
            port (int): WebSocket server port
            downsample_rate (int): Number of samples to accumulate before decimating (default: 10)
        """
        super().__init__()
        self.data_queue = data_queue
        self.host = host
        self.port = port
        self.downsample_rate = downsample_rate
        self.shutdown_event = shutdown_event
        self._buffers = {}  # {channel_name: deque of (timestamp, value)}

    def run(self):
        asyncio.run(self._start_server())

    async def _start_server(self):
        async with websockets.serve(self._handle_connection, self.host, self.port):
            print(f"WebSocket server started on ws://{self.host}:{self.port}")
            await asyncio.Future()  # Keep the server running

    async def _handle_connection(self, websocket):
        try:
            while not self.shutdown_event.is_set():
                # Get data from the queue
                try:
                    channel, value, timestamp = self.data_queue.get(timeout=1)  # 1-second timeout
                except Exception:
                    continue  # No data, continue to the next iteration

                # Buffer the data per channel
                if channel.name not in self._buffers:
                    self._buffers[channel.name] = deque(maxlen=self.downsample_rate)

                # Add current sample to the buffer
                self._buffers[channel.name].append((timestamp, value))

                # If buffer is full, decimate (reduce the sampling rate) and send
                if len(self._buffers[channel.name]) == self.downsample_rate:
                    # Create an obspy Trace for the data
                    times, values = zip(*self._buffers[channel.name])
                    trace = Trace()
                    trace.data = np.array(values, dtype=np.float32)
                    trace.stats.network = "XX"  # You can set your network code here
                    trace.stats.station = channel.name
                    trace.stats.starttime = UTCDateTime(times[0])

                    # Decimate the trace (downsample it)
                    trace.decimate(factor=self.downsample_rate)

                    # Send the decimated data
                    self._send_data(websocket, trace)

                    # Clear the buffer after sending
                    self._buffers[channel.name].clear()

                await asyncio.sleep(0.01)  # Small sleep to avoid CPU overuse
        except websockets.exceptions.ConnectionClosed:
            print("Client disconnected.")

    async def _send_data(self, websocket, trace):
        # Prepare the message
        message = {
            "channel": trace.stats.station,
            "timestamp": trace.stats.starttime.isoformat(),
            "data": trace.data.tolist()  # Convert the numpy array to a list for sending
        }

        # Send message via WebSocket
        await websocket.send(json.dumps(message))
        print(f"Sent data: {message}")
