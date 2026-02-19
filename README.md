# 🛰️ rpi-seism: High-Precision Seismic Data Acquisition

**rpi-seism** is a robust, professional-grade data acquisition (DAQ) system designed to transform a Raspberry Pi into a continuous seismic station. By interfacing with the **ADS1256 24-bit ADC**, it captures high-resolution analog signals from geophones or accelerometers, archives them in industry-standard **MiniSEED** format, and provides real-time telemetry via **WebSockets**.

The system is engineered for **unattended, long-term operation**, featuring deterministic timing control, schema-validated configuration, and graceful error handling.

---

## 🏗️ System Architecture

The core of `rpi-seism` is a **multithreaded producer-consumer pipeline**. This design ensures that high-priority hardware sampling is never interrupted by slower disk I/O or network fluctuations.

### Thread Model

| Thread | Priority | Responsibility |
| --- | --- | --- |
| **Reader** | **Critical** | Interfaces with SPI; implements drift-free sampling loops. |
| **MSeedWriter** | Medium | Buffers samples in RAM; flushes to MiniSEED files every 30 min. |
| **WebSocketSender** | Low | Downsamples data and broadcasts JSON to connected clients. |

All threads share a global **shutdown event**, ensuring that when the system receives a `SIGTERM` (from systemd) or `SIGINT` (Ctrl+C), all buffers are flushed to disk before the process exits.

---

## ✨ Key Features

* **24-bit Resolution:** Leverages the ADS1256 for ultra-low noise floor sensing, capturing the subtle nuances of seismic waves.
* **Drift-Free Timing:** Uses a monotonic clock (`time.perf_counter`) and absolute scheduling to maintain sample alignment over months of operation.
* **Seismology Standards:** Produces **MiniSEED** files (via ObsPy) compatible with IRIS, SeisComP, and Swarm.
* **Live Telemetry:** Built-in WebSocket server with on-the-fly decimation (anti-aliasing) for remote dashboard monitoring.
* **Deployment Ready:** Full **systemd** compatibility for automatic boot-start and headless operation.
* **Configuration Validation:** Uses **Pydantic** to ensure `config.yml` is logically sound before hardware initialization.

---

## 🔌 Hardware Setup

### Requirement List

* **Computer:** Raspberry Pi 3, 4, or 5.
* **ADC:** ADS1256 High-Precision ADC Board (WaveShare or similar).
* **Sensors:** Geophones (passive) or MEMS accelerometers (analog).
* **OS:** Raspberry Pi OS (64-bit recommended).

### Wiring Diagram (Default GPIO)

| ADS1256 Pin | RPi Pin (GPIO) | Function |
| --- | --- | --- |
| **PWDN** | 27 | Hardware Reset / Power Down |
| **CS** | 22 | SPI Chip Select |
| **DRDY** | 17 | Data Ready Interrupt |
| **SCLK/DIN/DOUT** | 11 / 10 / 9 | Standard SPI Bus (SPI0) |

---

## 📈 Technical Deep-Dive

### Timing & Jitter Mitigation

In seismic monitoring, "timing is the signal." `rpi-seism` calculates the **absolute next tick** rather than sleeping for a relative duration.

$$Next\_Tick = Start\_Time + (Total\_Samples \times Interval)$$

This ensures that even if the OS introduces a 1ms delay in one sample, the subsequent sample compensates to bring the stream back into alignment. Typical jitter on a Pi 4 is **<200µs**.

### ADS1256 Conversion Logic

The ADS1256 is a Delta-Sigma ADC. When switching channels (multiplexing), the system issues `SYNC` and `WAKEUP` commands to ensure the digital filter has settled before reading the 24-bit result.

### 24-Bit Data Processing

The ADC returns data as 3 bytes. The software converts this two's complement value into a signed integer:

1. Concatenate: $Value = (Byte1 \ll 16) | (Byte2 \ll 8) | Byte3$
2. If the 23rd bit is set: $Value = Value - 2^{24}$

---

## 📦 Installation & Deployment

### 1. Enable Hardware SPI

```bash
sudo raspi-config
# Interfacing Options -> SPI -> Enable

```

### 2. Install using `uv` (Recommended)

This project utilizes `uv` for lightning-fast, reproducible dependency management.

```bash
# Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# Setup environment
git clone https://github.com/your-org/rpi-seism.git
cd rpi-seism
uv venv && source .venv/bin/activate
uv pip install .

```

### 3. Execution

```bash
python -m src.main

```

---

## 🌐 Real-Time Streaming

The WebSocket server (default: `ws://0.0.0.0:8765`) emits JSON packets.
**Data Packet Example:**

```json
{
  "channel": "EHZ",
  "timestamp": "2026-02-10T16:05:00.123456",
  "data": [0.002, 0.005, -0.001]
}

```

*Built-in decimation reduces the 100Hz hardware stream to a lighter rate suitable for web-based dashboards.*

---

## 📜 License & Usage

This project is licensed under the **GNU General Public License v3.0 (GPL-3.0)**.

---

## 🚧 Known Limitations

* **Time Sync:** For research-grade data, a GPS-PPS HAT is recommended to discipline the system clock.
* **Gain:** The PGA gain is currently applied globally across all multiplexed channels.
* **Calibration:** No built-in sensor response deconvolution; users should apply instrument correction in post-processing.
