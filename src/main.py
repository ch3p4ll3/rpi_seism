import signal
from queue import Queue
from pathlib import Path
from threading import Event

from src.settings import Settings
from src.jobs import Reader, MSeedWriter, WebSocketSender


def main():
    # Define paths and load settings
    data_base_folder = Path(__file__).parent.parent / "data"
    settings = Settings.load_settings()

    # Create a global shutdown event
    shutdown_event = Event()

    # Define a signal handler for systemd (SIGTERM)
    def handle_exit(sig, frame):
        print(f"Exit signal {sig} received. Shutting down...")
        shutdown_event.set()

    signal.signal(signal.SIGTERM, handle_exit)
    signal.signal(signal.SIGINT, handle_exit)

    # Create queues for communication between jobs
    msed_writer_queue = Queue()
    websocket_queue = Queue()

    # Create and start the Reader job thread (reads from ADC, puts data in the queues)
    reader_job = Reader(settings, [msed_writer_queue, websocket_queue], shutdown_event)
    reader_job.start()

    # Create and start the MSeedWriter job thread (writes data to MiniSEED file)
    m_seed_writer_job = MSeedWriter(settings, msed_writer_queue, data_base_folder, shutdown_event, 1800)
    m_seed_writer_job.start()

    # Create and start the WebSocketSender job thread (sends data over WebSocket)
    websocket_job = WebSocketSender(websocket_queue, shutdown_event)
    websocket_job.start()

    # Gracefully stop all threads
    reader_job.join()

    # Wait for all threads to finish
    m_seed_writer_job.join()
    websocket_job.join()

    print("All threads stopped and the main script has finished.")


if __name__ == "__main__":
    main()
