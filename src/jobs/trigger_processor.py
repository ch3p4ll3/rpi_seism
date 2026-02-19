from threading import Thread, Event
from queue import Empty, Queue

from src.settings import Settings
from src.utils.sta_lta import STALTAProperty


class TriggerProcessor(Thread):
    def __init__(self, settings: Settings, data_queue: Queue, shutdown_event: Event):
        super().__init__()
        self.data_queue = data_queue
        self.shutdown_event = shutdown_event
        self.detector = STALTAProperty(sampling_rate=settings.sampling_rate)

    def run(self):
        while not self.shutdown_event.is_set():
            try:
                # We don't want to block forever so we can check shutdown_event
                channel, value, timestamp = self.data_queue.get(timeout=0.5)
                
                ratio, triggered = self.detector.process_sample(value)

                if triggered:
                    # Logic: If newly triggered, send a special WS message
                    # or tell MSeedWriter to "mark" the current file.
                    self.broadcast_event(channel.name, ratio, timestamp)
                
                self.data_queue.task_done()
            except Empty:
                continue

    def broadcast_event(self, channel, ratio, ts):
        event_msg = {
            "type": "SEISMIC_EVENT",
            "channel": channel,
            "ratio": round(ratio, 2),
            "timestamp": ts
        }

        print(event_msg)
