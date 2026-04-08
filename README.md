# SimpleFT8 — FT8/FT4 Client for FlexRadio

[English](#english) | [Deutsch](#deutsch)

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![Platform: macOS](https://img.shields.io/badge/platform-macOS-lightgrey.svg)](https://www.apple.com/macos/)

---

<a name="english"></a>
## English

**Direct SmartSDR control | Temporal Polarization Diversity | Adaptive Antenna Selection | Auto TX Power Regulation**

SimpleFT8 is a standalone FT8/FT4 client that controls your FlexRadio directly via the SmartSDR TCP API — no SmartSDR GUI needed. It features temporal antenna diversity with UCB1 adaptive selection.

### What Makes This Different

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

### Screenshots

| Main Interface | Diversity Mode |
|:-:|:-:|
| ![Main](docs/screenshots/normal_27stations_40m.png) | ![Diversity](docs/screenshots/diversity_37stations_40m.png) |

### Core Innovations

- **[Temporal Polarization Diversity](docs/DIVERSITY.md)** — How antenna cycling works, UCB1 algorithm, test results
- **[DX Tuning / Gain Measurement](docs/DX_TUNING.md)** — Automated antenna optimization, per-band presets
- **[Auto TX Power Regulation](docs/POWER_REGULATION.md)** — Closed-loop feedback, clipping protection, per-band calibration

### Features

- **Temporal Polarization Diversity** with UCB1 adaptive antenna ratio (70:30, 50:50, 30:70)
- **DX Tuning**: Automated 18-cycle gain measurement, per-band presets
- **Auto TX Power Regulation**: PI-controller with FWDPWR feedback, peak monitoring, per-band calibration
- **Signal Processing**: 5-pass signal subtraction, spectral whitening, sinc resampling
- **QSO Management**: Hunt mode + CQ mode, full state machine, ADIF 3.1.7 logging
- **Integrated Logbook**: Sortable table, search, DXCC counter, QSO detail overlay
- **QRZ.com**: Callsign lookup + logbook upload
- **PSKReporter** integration with spot statistics and distance display

### Installation

```bash
git clone https://github.com/mikewanne/SimpleFT8.git
cd SimpleFT8
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python3 main.py
```

**Requirements:** macOS, Python 3.12+, FlexRadio with SmartSDR TCP API (FLEX-6000/8000 series). Two antenna ports for Diversity mode (optional).

### Configuration

Settings in `~/.simpleft8/config.json`: callsign, locator, radio IP, band, power preset, QRZ API key.

### Architecture

```
SimpleFT8/
├── main.py               # Entry point
├── config/settings.py    # Settings, band frequencies
├── core/                 # Decoder, encoder, QSO state machine, diversity, timing
├── radio/flexradio.py    # SmartSDR TCP + VITA-49 RX/TX audio
├── log/                  # ADIF writer, QRZ.com API
└── ui/                   # PySide6 GUI (3-panel layout)
```

### Radio Compatibility

**Tested:** FLEX-8400M. **Expected compatible:** FLEX-6400/6600/6700/8400/8600 series.

### License

MIT License (c) 2026 DA1MHH (Mike Hammerer)

---

<a name="deutsch"></a>
## Deutsch

**Direkte SmartSDR-Steuerung | Temporale Polarisations-Diversity | Adaptive Antennenwahl | Automatische TX-Leistungsregelung**

SimpleFT8 ist ein eigenstaendiger FT8/FT4 Client, der dein FlexRadio direkt ueber die SmartSDR TCP API steuert — kein SmartSDR GUI noetig. Mit temporaler Antennen-Diversity und UCB1-adaptiver Auswahl.

### Was macht SimpleFT8 anders?

Anders als WSJT-X oder aehnliche Clients kommuniziert SimpleFT8 **direkt** mit deinem FlexRadio ueber TCP (Port 4992) und streamt VITA-49 Audio ueber UDP (Port 4991). Das ermoeglicht:

- **Temporale Polarisations-Diversity**: Wechsel zwischen zwei Antennen pro FT8-Zyklus, Stationen beider Antennen werden akkumuliert
- **Automatische TX-Leistungsregelung**: Geschlossener Regelkreis haelt die tatsaechliche Ausgangsleistung auf dem eingestellten Wert
- **Komplett eigenstaendiger Betrieb**: Kein SmartSDR, keine virtuellen Audiokabel, kein DAX-Panel

### Praxis-Ergebnisse

Kontrollierter Test auf 40m, gleiche Hardware (FLEX-8400M), 2 Minuten Abstand:

| Messwert | SimpleFT8 Normal | SimpleFT8 Diversity |
|----------|:---:|:---:|
| 40m, gute Bedingungen | 27 | **37** (+37%) |
| 40m, schlechte Bedingungen (4 min) | 9 | **13** (+44%) |
| PSKReporter Spots (TX, 15m) | -- | **190** |
| Weitester RX | -- | Kiribati ~13.000 km |
| Weitester TX | -- | Indonesien 11.996 km |

Siehe [Test-Screenshots und Methodik](docs/DIVERSITY_DE.md) fuer Details.

### Screenshots

| Hauptoberflaeche | Diversity-Modus |
|:-:|:-:|
| ![Main](docs/screenshots/normal_27stations_40m.png) | ![Diversity](docs/screenshots/diversity_37stations_40m.png) |

### Kern-Innovationen

- **[Temporale Polarisations-Diversity](docs/DIVERSITY_DE.md)** — Antennenwechsel, UCB1 Algorithmus, Testergebnisse
- **[DX Tuning / Gain-Messung](docs/DX_TUNING_DE.md)** — Automatisierte Antennenoptimierung, Presets pro Band
- **[Automatische TX-Leistungsregelung](docs/POWER_REGULATION_DE.md)** — Regelkreis, Clipping-Schutz, Kalibrierung pro Band

### Funktionen

- **Temporale Polarisations-Diversity** mit UCB1 adaptivem Antennenverhaeltnis (70:30, 50:50, 30:70)
- **DX Tuning**: Automatisierte 18-Zyklen Gain-Messung, Presets pro Band
- **Automatische TX-Leistungsregelung**: PI-Regler mit FWDPWR-Feedback, Peak-Monitor, Kalibrierung pro Band
- **Signalverarbeitung**: 5-Pass Signal Subtraction, Spectral Whitening, Sinc-Resampling
- **QSO-Management**: Hunt-Modus + CQ-Modus, Zustandsmaschine, ADIF 3.1.7 Logging
- **Integriertes Logbuch**: Sortierbare Tabelle, Suche, DXCC-Zaehler, QSO-Detail-Overlay
- **QRZ.com**: Rufzeichen-Lookup + Logbuch-Upload
- **PSKReporter**-Integration mit Spot-Statistik und Entfernungsanzeige

### Installation

```bash
git clone https://github.com/mikewanne/SimpleFT8.git
cd SimpleFT8
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python3 main.py
```

**Voraussetzungen:** macOS, Python 3.12+, FlexRadio mit SmartSDR TCP API (FLEX-6000/8000 Serie). Zwei Antennenanschluesse fuer Diversity-Modus (optional).

### Konfiguration

Einstellungen in `~/.simpleft8/config.json`: Rufzeichen, Locator, Radio-IP, Band, Leistungs-Preset, QRZ API Key.

### Architektur

```
SimpleFT8/
├── main.py               # Einstiegspunkt
├── config/settings.py    # Einstellungen, Band-Frequenzen
├── core/                 # Decoder, Encoder, QSO-Zustandsmaschine, Diversity, Timing
├── radio/flexradio.py    # SmartSDR TCP + VITA-49 RX/TX Audio
├── log/                  # ADIF Writer, QRZ.com API
└── ui/                   # PySide6 GUI (3-Panel Layout)
```

### Radio-Kompatibilitaet

**Getestet:** FLEX-8400M. **Voraussichtlich kompatibel:** FLEX-6400/6600/6700/8400/8600 Serie.

### Lizenz

MIT License (c) 2026 DA1MHH (Mike Hammerer)

---

## Acknowledgments / Danksagungen

- [PyFT8](https://github.com/kgoba/ft8_lib) — FT8/FT4 encode/decode library
- [FlexRadio Systems](https://www.flexradio.com/) — SmartSDR TCP API
- [WSJT-X](https://wsjt.sourceforge.io/) — Pioneering digital weak-signal modes

---

*SimpleFT8: Because weak signals deserve a fighting chance. / Weil schwache Signale eine faire Chance verdienen.*
