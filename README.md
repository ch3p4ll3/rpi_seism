# RPI-SEISM

A 3‑axis geophone seismometer project for Raspberry Pi.  
Reads data from an Arduino‑based digitizer over RS485, processes it in real‑time, and provides:

- **MiniSEED archiving** (via ObsPy)  
- **Live waveform streaming** via WebSocket to a web frontend  
- **Earthquake detection** using a STA/LTA algorithm with immediate file marking and notifications

The system is built around four concurrently running threads, making it efficient and responsive even on a Raspberry Pi.

---

## Table of contents

- [RPI-SEISM](#rpi-seism)
  - [Table of contents](#table-of-contents)
  - [Features](#features)
  - [Hardware Requirements](#hardware-requirements)
  - [Software Stack](#software-stack)
  - [Installation with UV](#installation-with-uv)
  - [Configuration via YAML](#configuration-via-yaml)
    - [Default configuration](#default-configuration)
  - [Usage](#usage)
    - [Frontend](#frontend)
  - [In‑Depth Explanation of Each Thread](#indepth-explanation-of-each-thread)
    - [1. Reader Thread](#1-reader-thread)
    - [2. MSeedWriter Thread](#2-mseedwriter-thread)
    - [3. TriggerProcessor Thread](#3-triggerprocessor-thread)
    - [4. WebSocketSender Thread](#4-websocketsender-thread)
  - [Data Flow Diagram](#data-flow-diagram)
  - [File Layout](#file-layout)
  - [Customising the STA/LTA Detector](#customising-the-stalta-detector)
  - [Troubleshooting](#troubleshooting)
  - [Contributing](#contributing)
  - [License](#license)
  - [Acknowledgements](#acknowledgements)
  - [Links](#links)


---

## Features

- **Continuous data acquisition** from a 3‑channel (EHZ, EHN, EHE) geophone at 100 Hz
- **Robust RS485 communication** with automatic heartbeat to keep the Arduino streaming
- **MiniSEED file writer** – creates 30‑minute files by default, but saves immediately (with `EQ_` prefix) when an event is detected
- **STA/LTA trigger** – detects earthquakes on the vertical channel and notifies the writer and frontend
- **WebSocket live feed** – serves decimated waveform data (1 second updates) to connected clients
- **Modular design** – each component runs in its own thread, communicating via thread‑safe queues
- **Configurable via YAML** – station name, channel mapping, sampling rate, decimation factor, etc.

---

## Hardware Requirements

- **Raspberry Pi** (any model with GPIO, tested on RPi 3/4)
- **Arduino‑based digitizer** (code provided in separate repository)  
  - Sampling at 100 Hz, 3 channels  
  - Communicates over RS485  
  - Expects a heartbeat pulse every 500 ms to continue streaming
- **MAX485** or equivalent RS485 transceiver connected to the Pi’s UART and a GPIO pin (e.g., GPIO5) for direction control
- **Geophone** (3‑component, e.g., 4.5 Hz) with appropriate pre‑amplifier/shielded cables

> 📌 **Arduino firmware**: [rpi-seism-reader](https://github.com/ch3p4ll3/rpi-seism-reader) – handles ADC reading, packet framing, and RS485 transmission.

---

## Software Stack

- Python 3.7+ (managed with [UV](https://docs.astral.sh/uv/))
- [ObsPy](https://github.com/obspy/obspy) – for MiniSEED I/O and decimation
- [pyserial](https://github.com/pyserial/pyserial) – serial communication
- [websockets](https://github.com/aaugustin/websockets) – WebSocket server
- [numpy](https://numpy.org/) – data handling
- [gpiozero](https://gpiozero.readthedocs.io/) – GPIO control (with mock fallback for development)
- [PyYAML](https://pyyaml.org/) – YAML configuration loading

---

## Installation with UV

[UV](https://docs.astral.sh/uv/) is a fast Python package installer and resolver.  
If you don’t have it yet, install it:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Then clone this repository and install dependencies:

```bash
git clone https://github.com/ch3p4ll3/rpi-seism.git
cd rpi-seism
uv sync                # install dependencies
```

---

## Configuration via YAML

All system settings are defined in a YAML file. If the file is not present, one will be created with the default configuration

### Default configuration

```yaml
station: RPI3
network: XX
sampling_rate: 100
decimation_factor: 4
channels:
- adc_channel: 0
  name: EHZ
  orientation: vertical
- adc_channel: 1
  name: EHN
  orientation: north
- adc_channel: 2
  name: EHE
  orientation: east

```

- **network / station** – SEED identifiers.
- **sampling_rate** – must match the Arduino’s output rate (100 Hz).
- **decimation_factor** – factor used by the WebSocket sender (e.g., 4 → 25 Hz output).
- **channels** – list with names, ADC indices, and orientations.

---

## Usage

Start the application with:

```bash
uv run python -m src.main
```

All threads start automatically:

- **Reader** – reads from the serial port and pushes raw packets into a shared queue.
- **MSeedWriter** – buffers samples and writes MiniSEED files at regular intervals (or immediately on trigger).
- **TriggerProcessor** – runs STA/LTA on the vertical channel; sets an `earthquake_event` when threshold is crossed.
- **WebSocketSender** – serves a WebSocket, sending decimated traces every second.

Stop with `Ctrl+C`. On shutdown, any buffered data is written to disk.

### Frontend

A companion web interface is available to display live waveforms and event notifications:

📁 **[rpi-seism-frontend](https://github.com/ch3p4ll3/rpi-seism-web)** – Angular‑based dashboard that connects to the WebSocket endpoint.

---

## In‑Depth Explanation of Each Thread

### 1. Reader Thread
- **Responsibility**: Sole owner of the serial port and the RS485 direction control GPIO.
- **Operation**:
  - Sends a heartbeat byte (`0x01`) every `heartbeat_interval` (default 0.5 s) to keep the Arduino streaming. Before sending, it sets the MAX485 to transmit mode, then immediately back to receive.
  - Reads incoming bytes into a buffer, searches for the packet header (`0xAA 0xBB`), and validates the checksum (XOR of all bytes except the last).
  - Upon a valid packet, unpacks three 32‑bit signed integers (the channel samples).
  - The packet then is formatted as a dict:  
    `{"timestamp": time.time(), "measurements": [{"channel": ch_obj, "value": val}, ...]}`
  - This packet is placed into every downstream queue (MSeed, Trigger, WebSocket).
- **Why a thread?** It must continuously poll the serial port without blocking other tasks, and the heartbeat timing must be precise.

### 2. MSeedWriter Thread
- **Responsibility**: Buffer incoming samples and write them to MiniSEED files.
- **Operation**:
  - Maintains a per‑channel list of values and the start time of the current batch.
  - Consumes packets from its queue, appending values to the buffers.
  - Normally, writes a file every `write_interval_sec` (e.g., 1800 s = 30 min).
  - When the `earthquake_event` is set by the trigger, it schedules the *next* write to happen in `event_write_delay_sec` (e.g., 5 min) – this ensures that the triggered event data is saved promptly without waiting for the normal interval.
  - If multiple triggers occur during the countdown, the timer resets.
  - The written file is named `data_YYYYMMDDTHHMMSS.mseed` normally, or `data_EQ_YYYYMMDDTHHMMSS.mseed` when triggered.
- **Why a thread?** Writing to disk can be I/O‑bound; buffering allows the writer to operate independently from the high‑rate data stream.

### 3. TriggerProcessor Thread
- **Responsibility**: Detect seismic events using a STA/LTA algorithm on the vertical channel.
- **Operation**:
  - Listens for packets and extracts the value for the designated trigger channel (e.g., `EHZ`).
  - Feeds each sample into a `STALTAProperty` instance (implemented in `utils/sta_lta.py`).
  - The algorithm computes short‑term and long‑term averages and returns the ratio plus a boolean trigger state (ratio > threshold_on).
  - On a rising edge (from false to true), it sets the `earthquake_event` (a `threading.Event`) and logs the detection.
  - On a falling edge (true to false), it clears the event.
- **Why a thread?** STA/LTA processing is lightweight but needs to run for every sample. Running it in its own thread prevents it from being blocked by I/O operations.

### 4. WebSocketSender Thread
- **Responsibility**: Provide a live data feed to web clients with decimated waveforms.
- **Operation**:
  - Runs an asyncio event loop that hosts a WebSocket server.
  - Maintains a sliding‑window buffer (size = `window_seconds * sampling_rate`) per channel.
  - Every `step_seconds` (e.g., 1 s), it takes the current window for each channel, creates an ObsPy Trace, and applies decimation (with anti‑alias filtering) using `trace.decimate(decimation_factor)`.
  - Extracts only the newly added decimated samples (the last `step_seconds / decimation_factor` samples) and broadcasts them in a JSON message:
    ```json
    {
      "channel": "EHZ",
      "timestamp": "2025-03-23T12:34:56.789Z",
      "fs": 25,
      "data": [123, 125, ...]
    }
    ```
  - Manages client connections, sending updates only to active clients.
- **Why a thread?** It uses asyncio, which runs in its own thread to avoid interfering with the other synchronous threads. The thread’s `run()` method starts the asyncio event loop.

---

## Data Flow Diagram

```
                +-------------+
                |   Arduino   |
                |   (100 Hz)  |
                +------+------+
                       | RS485
                       v
+-------------------------------------------------+
|                                                 |
|  Reader Thread                                   |
|  - Reads serial, verifies checksum               |
|  - Sends heartbeat every 500ms                   |
|  - Distributes packets to all queues             |
|                                                 |
+--------+----------------+------------+-----------+
         |                |            |
         v                v            v
   +----------+    +-------------+  +-----------------+
   | data_q   |    | data_q      |  | data_q          |
   +----------+    +-------------+  +-----------------+
         |                |            |
         v                v            v
+----------------+  +----------------+  +-------------------+
| MSeedWriter    |  | TriggerProcessor|  | WebSocketSender   |
| - Buffers data |  | - STA/LTA       |  | - Sliding window  |
| - Writes .mseed|  | - Sets event    |  | - Decimates       |
| - Handles event|  |   on trigger    |  | - Broadcasts via  |
|   file marking |  +----------------+  |   WebSocket       |
+----------------+                       +-------------------+
         |                                        |
         | earthquake_event                       |
         +----------------------------------------+
```

---

## File Layout

```
rpi_seism/
├── data/
│   └── config.yml          # example configuration
├── src/
│   ├── jobs/
│   │   ├── reader.py            # RS‑485 reader + heartbeat
│   │   ├── mseed_writer.py      # ObsPy file writer
│   │   ├── websocket_sender.py  # real‑time websocket server
│   │   └── trigger_processor.py # STA/LTA detector
│   ├── utils/
│   │   ├── sta_lta.py           # short‑term/long‑term average detector
│   │   └── serial_helpers.py    # packet encode/decode
│   ├── settings/
│   │   └── settings.py          # pydantic model for config
│   └── main.py                  # thread orchestration & CLI
├── tests/                    # pytest unit tests
├── LICENSE
└── pyproject.toml            # dependencies & packaging
```

---

## Customising the STA/LTA Detector

The `STALTAProperty` class (in `utils/sta_lta.py`) implements a recursive STA/LTA. You can adjust:

- `sta_window` (seconds)
- `lta_window` (seconds)
- `trigger_threshold` (on ratio)
- `detrigger_threshold` (off ratio)

These values are taken from the `trigger` section of the YAML config.

---

## Troubleshooting

- **No data in MiniSEED files**: Check the serial connection, baud rate, and that the Arduino is sending packets with headers `0xAA 0xBB` and correct checksum. Enable debug logging in the Reader.
- **GPIO errors**: If running on a non‑Raspberry Pi (or without GPIO), the code falls back to a mock pin factory. For real deployment, ensure you have `gpiozero` and the correct pin number in the config.
- **WebSocket not connecting**: Verify the port (default 8765) is not blocked and that the frontend points to the correct IP.
- **Earthquake not detected**: Tune the STA/LTA thresholds. The current implementation may need adjustment for your site’s noise level.
- **UV not found**: Follow the [UV installation guide](https://docs.astral.sh/uv/getting-started/installation/).

---

## Contributing

Contributions are welcome! Please open an issue or pull request for any improvements, bug fixes, or documentation updates.

---

## License

[GNU General Public License v3.0](LICENSE)

---

## Acknowledgements

- Inspired by the [Raspberry Shake](https://raspberryshake.org/) project
- STA/LTA algorithm based on common seismic processing practices
- Built with [ObsPy](https://obspy.org/) – a great toolkit for seismology

---

## Links

- [Arduino digitizer firmware](https://github.com/ch3p4ll3/rpi-seism-reader)
- [Web frontend](https://github.com/ch3p4ll3/rpi-seism-web)