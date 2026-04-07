# SimpleFT8 — Minimal FT8/FT4 Client for FlexRadio on macOS

**English** | [Deutsch](README_DE.md)

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![Platform: macOS](https://img.shields.io/badge/platform-macOS-lightgrey.svg)](https://www.apple.com/macos/)

**Direct SmartSDR control | Temporal Polarization Diversity | Adaptive Antenna Selection | Auto TX Power Regulation**

SimpleFT8 is a standalone FT8/FT4 client that controls your FlexRadio directly via the SmartSDR TCP API — no SmartSDR GUI needed. It features temporal antenna diversity with UCB1 adaptive selection, achieving up to 8x more decoded stations than conventional setups.

---

## What Makes This Different

Unlike WSJT-X or similar clients that need SmartSDR running, SimpleFT8 communicates **directly** with your FlexRadio via TCP (port 4992) and streams VITA-49 audio over UDP (port 4991). This enables:

- **Temporal Polarization Diversity**: Cycle between two antennas every FT8 cycle, accumulate stations from both
- **Automatic TX power regulation**: Closed-loop feedback keeps your actual output matching the selected wattage
- **Fully standalone operation**: No SmartSDR, no virtual audio cables, no DAX panel

### Real-World Performance

Controlled test on 40m, same hardware (FLEX-8400M), 2 minutes apart:

| Metric | SimpleFT8 Normal | SimpleFT8 Diversity |
|--------|:---:|:---:|
| 40m, good conditions | 27 | **37** (+37%) |
| 40m, poor conditions (4 min) | 9 | **13** (+44%) |
| PSKReporter Spots (TX, 15m) | -- | **190** |
| Farthest RX | -- | Kiribati ~13,000 km |
| Farthest TX | -- | Indonesia 11,996 km |

See [test screenshots and methodology](docs/DIVERSITY.md) for details.

---

## Screenshots

| Main Interface | Diversity Mode |
|:-:|:-:|
| ![Main](screenshots/main.png) | ![Diversity](screenshots/diversity.png) |

*(Add your own screenshots to the `screenshots/` directory)*

---

## Core Innovations

Each of the three core features has its own detailed documentation with screenshots and technical explanation:

- **[Temporal Polarization Diversity](docs/DIVERSITY.md)** — How antenna cycling works, UCB1 algorithm, test results
- **[DX Tuning / Gain Measurement](docs/DX_TUNING.md)** — Automated antenna optimization, per-band presets
- **[Auto TX Power Regulation](docs/POWER_REGULATION.md)** — Closed-loop feedback, clipping protection, per-band calibration

---

## Features

### Temporal Polarization Diversity
- Cycles between ANT1 and ANT2 every 15-second FT8 cycle
- Accumulates decoded stations from both antennas without duplicates
- Visual indicators show which stations are exclusive to each antenna (A1, A2, A1>2, A2>1)
- Works on any FlexRadio with two antenna ports (even single-SCU models)

### UCB1 Adaptive Antenna Selection
- In AUTO mode, uses Upper Confidence Bound (UCB1) multi-armed bandit algorithm
- Dynamically finds the optimal antenna ratio: 70:30, 50:50, or 30:70
- Continuously adapts to changing propagation — no manual tuning needed
- Exploration bonus prevents under-sampled antenna from being abandoned

### DX Tuning
- Automated 18-cycle interleaved measurement of both antennas
- Per-antenna preamp gain optimization per band
- Presets saved and automatically loaded on band change

### Auto TX Power Regulation
- P-controller feedback loop using the radio's FWDPWR meter
- Automatically adjusts TX audio drive (mic_level + software gain) so actual watts match selected power
- Per-band calibration saved — instant convergence on band change
- Clipping protection: monitors audio peak level, stops increasing if signal would distort
- Compensates for antenna/SWR changes and weather conditions in real-time

### Signal Processing
- 5-pass iterative signal subtraction for weak signal recovery
- FFT-based spectral whitening with median noise floor normalization
- Anti-alias sinc resampling (63 taps, Hamming window) from 24 kHz to 12 kHz
- LDPC decoder with 50 iterations, 200 candidates, multi-sync LLR sweep

### QSO Management
- **Hunt mode**: Click any station in the RX panel to initiate a QSO
- **CQ mode**: Automatic CQ calling with TX queue for incoming callers
- Full state machine: CQ -> Report -> RR73 -> ADIF log
- Configurable max call attempts (3/5/7/99)
- Even/Odd slot auto-detection and correction

### Logging and Reporting
- ADIF 3.1.7 export (append mode)
- PSKReporter integration with spot statistics and distance display
- Country detection from callsign prefix with distance in km

---

## Installation

### Prerequisites
- macOS (tested on macOS 15 Sequoia)
- Python 3.12 or newer
- FlexRadio with SmartSDR TCP API (FLEX-6000 / 8000 series)
- Two antenna ports for Diversity mode (optional)

### Setup

```bash
git clone https://github.com/mikewanne/SimpleFT8.git
cd SimpleFT8

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

python3 main.py
```

### Dependencies
- PySide6 (Qt6 GUI framework)
- PyFT8 2.6.1 (FT8/FT4 encode/decode)
- NumPy (signal processing)
- sounddevice (audio fallback)
- ntplib (time synchronization)

---

## Configuration

SimpleFT8 stores settings in `~/.simpleft8/config.json`:

```json
{
  "callsign": "YOURCALL",
  "locator": "JO31",
  "flexradio_ip": "192.168.1.68",
  "flexradio_port": 4992,
  "band": "20m",
  "mode": "FT8",
  "power_preset": 70,
  "max_calls": 3,
  "swr_limit": 3.0
}
```

On first run, the file is created with default values. Set your callsign, locator, and radio IP, then restart.

---

## Architecture

```
SimpleFT8/
├── main.py               # Entry point + instance cleanup
├── config/
│   └── settings.py       # Settings, band frequencies, FlexRadio IP
├── core/
│   ├── decoder.py        # FT8 decode (PyFT8 + subtraction + whitening)
│   ├── encoder.py        # FT8 encode (PyFT8 -> VITA-49 TX)
│   ├── message.py        # FT8 message parser (CQ, Report, Grid, RR73)
│   ├── qso_state.py      # QSO state machine (Hunt + CQ)
│   ├── diversity.py      # Diversity controller (measure/operate phases)
│   └── timing.py         # UTC clock, 15s/7.5s cycle timing
├── radio/
│   └── flexradio.py      # SmartSDR TCP + VITA-49 RX/TX audio
├── log/
│   └── adif.py           # ADIF 3.1.7 writer
├── ui/
│   ├── main_window.py    # 3-panel QSplitter layout
│   ├── rx_panel.py       # RX station list (color-coded)
│   ├── qso_panel.py      # QSO history (TX/RX chronological)
│   └── control_panel.py  # Mode, Band, Antenna, Radio, QSO controls
└── requirements.txt
```

### Connection Flow

```
1. TCP connect to radio:4992
2. Disconnect SmartSDR-M (free receiver resources)
3. Create own panadapter + slice
4. Configure: DIGU mode, DAX, TX stream
5. Set max_power_level=100, rfpower, mic_level
6. Stream VITA-49 audio: RX decode + TX encode
7. Keepalive every 5 seconds
```

### Audio Pipeline

```
VITA-49 RX (24kHz int16 mono)
  -> Anti-alias lowpass (sinc/Hamming, fc=6kHz)
  -> Resample to 12kHz
  -> DC removal
  -> Spectral whitening (overlap-add FFT)
  -> Normalize (-12 dBFS)
  -> Window sliding (0, +0.3s, -0.3s offsets)
  -> FT8 decode (Costas sync -> LDPC -> CRC -> Unpack)
  -> Signal subtraction (up to 5 passes)
  -> Result fusion + deduplication
```

---

## Radio Compatibility

**Tested:**
- FLEX-8400M (primary development platform)

**Expected compatible:**
- FLEX-6400 / 6400M / 6600 / 6600M / 6700
- FLEX-8400 / 8600 / 8600M

Any FlexRadio with SmartSDR TCP API should work. Diversity requires two antenna ports.

---

## Usage

### Basic Workflow
1. Start SimpleFT8 — it auto-discovers and connects to your FlexRadio
2. Select band (20m, 40m, etc.) — radio tunes automatically
3. Watch stations appear in the RX panel
4. **Hunt mode**: Click a station to call them
5. **CQ mode**: Press CQ button for automatic calling

### Antenna Modes
- **NORMAL**: Single antenna (ANT1), standard FT8 operation
- **DIVERSITY**: Temporal switching ANT1/ANT2, station accumulation
- **EINMESSEN (DX Tuning)**: Automated antenna + preamp measurement

### Power Control
Select power with the 10W-100W buttons. The auto-regulation adjusts TX drive so the radio's actual output matches your selection. The TX bar shows current drive level, Peak shows audio headroom.

---

## Contributing

Contributions welcome! Please:
1. Open an issue to discuss changes before submitting a PR
2. Follow existing code style
3. Test with an actual FlexRadio if possible

---

## License

MIT License (c) 2026 DA1MHH (Mike Hammerer)

See [LICENSE](LICENSE) for details.

---

## Acknowledgments

- [PyFT8](https://github.com/kgoba/ft8_lib) — FT8/FT4 encode/decode library
- [FlexRadio Systems](https://www.flexradio.com/) — SmartSDR TCP API
- [WSJT-X](https://wsjt.sourceforge.io/) — Pioneering digital weak-signal modes

---

*SimpleFT8: Because weak signals deserve a fighting chance.*
