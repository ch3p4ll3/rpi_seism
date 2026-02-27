from threading import Thread, Event
from queue import Empty, Queue
from logging import getLogger

from src.settings import Settings
from src.utils.sta_lta import STALTAProperty

logger = getLogger(__name__)

class TriggerProcessor(Thread):
    """
    Thread that processes incoming seismic data packets, applies a STA/LTA algorithm
    to detect earthquakes, and sets an earthquake event flag when a trigger condition is met.
    """
    def __init__(
        self,
        settings: Settings,
        data_queue: Queue,
        shutdown_event: Event,
        earthquake_event: Event
    ):
        super().__init__()
        self.data_queue = data_queue
        self.earthquake_event = earthquake_event
        self.shutdown_event = shutdown_event

        # Initialize the detector with your specific sampling rate
        self.detector = STALTAProperty(sampling_rate=settings.sampling_rate)

        # We usually trigger on the vertical component
        self.trigger_channel = "EHZ"
        self.last_trigger = False

    def run(self):
        logger.info("Trigger Processor (STA/LTA) started.")

        while not self.shutdown_event.is_set():
            try:
                # Expecting: {"timestamp": float, "measurements": [{"channel": obj, "value": int}, ...]}
                packet = self.data_queue.get(timeout=0.5)

                # extract the value for the trigger channel (e.g., EHZ)
                trigger_value = None
                for item in packet["measurements"]:
                    if item["channel"].name == self.trigger_channel:
                        trigger_value = item["value"]
                        break

                # If the packet doesn't contain our trigger channel, skip
                if trigger_value is None:
                    self.data_queue.task_done()
                    continue

                # feed the sample into the STA/LTA algorithm
                # detector.process_sample likely returns (ratio, is_triggered)
                _, triggered = self.detector.process_sample(trigger_value)

                # handle State Changes (Edge Detection)
                if triggered and not self.last_trigger:
                    logger.warning("EARTHQUAKE DETECTED: STA/LTA threshold exceeded!")
                    self.earthquake_event.set()
                    self.last_trigger = True

                elif not triggered and self.last_trigger:
                    logger.info("Trigger cleared: Signal returned to background levels.")
                    self.earthquake_event.clear()
                    self.last_trigger = False

                self.data_queue.task_done()

            except Empty:
                continue
            except Exception:
                logger.exception("Error in Trigger Processor loop")

        logger.info("Trigger Processor stopped.")
