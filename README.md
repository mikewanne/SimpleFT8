# SimpleFT8 — The Autonomous FT8/FT4 Client for FlexRadio

[English](#english) | [Deutsch](#deutsch)

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![Platform: macOS](https://img.shields.io/badge/platform-macOS-lightgrey.svg)](https://www.apple.com/macos/)
[![Ham Radio](https://img.shields.io/badge/ham--radio-FT8%2FFT4-orange.svg)](https://www.physics.princeton.edu/pulsar/k1jt/wsjtx.html)

> **No more manual ALC babysitting, no missed replies, no guessing the best antenna or frequency.**
> SimpleFT8 automates your entire FT8/FT4 workflow with closed-loop power control, reinforcement learning antenna selection, automatic CQ frequency optimization, and intelligent caller queuing.

---

<a name="english"></a>
## English

### Why SimpleFT8 vs. WSJT-X?

| Feature | WSJT-X / JS8Call | SimpleFT8 |
|---------|:---:|:---:|
| TX Power Control | Manual ALC monitoring | **Automatic closed-loop (FWDPWR feedback)** |
| Antenna Selection | Manual | **Automatic via UCB1 reinforcement learning** |
| CQ Frequency Selection | Manual waterfall scan | **Automatic via spectrum histogram** |
| Simultaneous Callers | Second station ignored | **Queued, answered automatically after first QSO** |
| SmartSDR required | Yes (most clients) | **No — direct VITA-49 + TCP** |
| Band change power re-calibration | Manual | **Automatic per-band calibration** |

### Key Innovations

- **Auto TX Power Regulation** — Set your target wattage (e.g. 50W), SimpleFT8 reads the actual FWDPWR from the radio and adjusts rfpower proportionally until the target is hit. No more overdrive, no more weak signal on band changes. Works automatically every QSO cycle.

- **Temporal Polarization Diversity** — Cycles between two antennas every FT8 cycle and uses the UCB1 multi-armed bandit algorithm to learn which antenna/polarization performs better. After 80 cycles it re-evaluates and adjusts the ratio (70:30, 50:50, 30:70). Accumulates decoded stations from both antennas.

- **Automatic CQ Frequency Selection** — After diversity calibration, a 50 Hz bin histogram of all occupied frequencies is built. The widest clear gap (>150 Hz) is automatically chosen as the CQ frequency. No more manually hunting for a free slot.

- **Caller Waitlist** — When two stations reply to your CQ simultaneously, the second is placed in a queue. After the first QSO completes, SimpleFT8 automatically responds to the queued station without sending another CQ. More QSOs per hour.

- **Fully Standalone** — No SmartSDR GUI, no virtual audio cables, no DAX panel needed. Direct VITA-49 UDP audio streaming + SmartSDR TCP API.

### Real-World Performance

Controlled test on 40m, same hardware (FLEX-8400M), 2 minutes apart:

| Metric | SimpleFT8 Normal | SimpleFT8 Diversity |
|--------|:---:|:---:|
| Stations decoded (good conditions) | 27 | **37 (+37%)** |
| Stations decoded (poor conditions, 4 min) | 9 | **13 (+44%)** |
| PSKReporter Spots (TX, 15 min) | — | **190** |
| Farthest RX | — | Kiribati ~13,000 km |
| Farthest TX | — | Indonesia 11,996 km |

See [test screenshots and methodology](docs/DIVERSITY.md) for details.

### Screenshots

| Main Interface | Diversity Mode |
|:-:|:-:|
| ![Main](docs/screenshots/normal_27stations_40m.png) | ![Diversity](docs/screenshots/diversity_37stations_40m.png) |

### All Features

- **Auto TX Power Regulation**: Proportional closed-loop FWDPWR feedback, clipping protection (audio level capped at 0.75), per-band calibration, fast proportional step-up and step-down
- **Temporal Polarization Diversity** with UCB1 adaptive antenna ratio (70:30, 50:50, 30:70), auto re-measurement every 80 cycles
- **Automatic CQ Frequency** via spectrum histogram after diversity calibration
- **Caller Waitlist**: Queue simultaneous callers, respond automatically after current QSO
- **DX Tuning**: Automated 18-cycle gain measurement, per-band presets saved
- **Signal Processing**: 5-pass signal subtraction, spectral whitening, sinc anti-alias resampling, 50 LDPC iterations
- **QSO State Machine**: Hunt mode + CQ mode, even/odd slot management, retry logic, ADIF 3.1.7 logging
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

**Requirements:** macOS, Python 3.12+, FlexRadio SDR (FLEX-6000/8000 series) with SmartSDR TCP API. Two antenna ports for Diversity mode (optional — single antenna works fine in normal mode).

### Configuration

Settings via GUI or directly in `~/.simpleft8/config.json`: callsign, locator, radio IP, band, power preset, QRZ API key.

### Architecture

```
SimpleFT8/
├── main.py               # Entry point
├── config/settings.py    # Settings, band frequencies
├── core/                 # Decoder, encoder, QSO state machine, diversity, timing
├── radio/flexradio.py    # SmartSDR TCP + VITA-49 RX/TX audio streaming
├── log/                  # ADIF writer, QRZ.com API
└── ui/                   # PySide6 GUI (3-panel dark theme)
```

### Radio Compatibility

**Tested:** FLEX-8400M. **Expected compatible:** FLEX-6300/6400/6500/6600/6700/8400/8600 series.

### License

MIT License (c) 2026 DA1MHH (Mike Hammerer)

---

<a name="deutsch"></a>
## Deutsch

### Warum SimpleFT8 statt WSJT-X?

| Funktion | WSJT-X / JS8Call | SimpleFT8 |
|---------|:---:|:---:|
| TX-Leistungsregelung | Manuelles ALC-Monitoring | **Automatischer Regelkreis (FWDPWR-Feedback)** |
| Antennenwahl | Manuell | **Automatisch via UCB1 Reinforcement Learning** |
| CQ-Frequenzwahl | Manueller Wasserfall | **Automatisch via Frequenz-Histogramm** |
| Gleichzeitige Anrufer | Zweite Station ignoriert | **Warteliste — automatisch nach erstem QSO beantwortet** |
| SmartSDR erforderlich | Ja (die meisten Clients) | **Nein — direkt via VITA-49 + TCP** |
| Leistungs-Rekalibrierung nach Bandwechsel | Manuell | **Automatisch pro Band** |

### Die wichtigsten Innovationen

- **Automatische TX-Leistungsregelung** — Zielwatt einstellen (z.B. 50W), SimpleFT8 liest den tatsächlichen FWDPWR-Wert vom Radio und regelt den rfpower-Wert proportional nach — aufwärts und abwärts. Kein manuelles ALC, keine Übersteuerung, keine zu schwachen Signale nach dem Bandwechsel.

- **Temporale Polarisations-Diversity** — Wechselt pro FT8-Zyklus zwischen zwei Antennen und nutzt den UCB1 Multi-Armed-Bandit-Algorithmus um zu lernen, welche Antenne/Polarisation besser ist. Nach 80 Zyklen wird neu eingemessen und das Verhältnis angepasst (70:30, 50:50, 30:70).

- **Automatische CQ-Frequenzwahl** — Nach dem Einmessen wird aus einem 50-Hz-Bin-Histogramm aller belegten Frequenzen die breiteste freie Lücke (>150 Hz) automatisch als CQ-Frequenz gewählt. Kein manuelles Suchen nach freiem Platz im Wasserfall.

- **Warteliste für gleichzeitige Anrufer** — Wenn zwei Stationen gleichzeitig auf dein CQ antworten, kommt die zweite in eine Warteschlange. Nach dem ersten QSO antwortet SimpleFT8 automatisch der wartenden Station — ohne neues CQ.

- **Komplett eigenständig** — Kein SmartSDR GUI, keine virtuellen Audiokabel, kein DAX-Panel. Direktes VITA-49 UDP Audio-Streaming + SmartSDR TCP API.

### Praxis-Ergebnisse

Kontrollierter Test auf 40m, gleiche Hardware (FLEX-8400M), 2 Minuten Abstand:

| Messwert | SimpleFT8 Normal | SimpleFT8 Diversity |
|----------|:---:|:---:|
| Dekodierte Stationen (gute Bedingungen) | 27 | **37 (+37%)** |
| Dekodierte Stationen (schlechte Bedingungen, 4 min) | 9 | **13 (+44%)** |
| PSKReporter Spots (TX, 15 min) | — | **190** |
| Weitester RX | — | Kiribati ~13.000 km |
| Weitester TX | — | Indonesien 11.996 km |

Siehe [Test-Screenshots und Methodik](docs/DIVERSITY_DE.md) für Details.

### Alle Funktionen

- **Automatische TX-Leistungsregelung**: Proportionaler Regelkreis mit FWDPWR-Feedback, Clipping-Schutz (Audio-Level max. 0,75), Kalibrierung pro Band
- **Temporale Polarisations-Diversity** mit UCB1 adaptivem Verhältnis (70:30, 50:50, 30:70), automatische Neueinmessung alle 80 Zyklen
- **Automatische CQ-Frequenz** via Frequenz-Histogramm nach dem Einmessen
- **Warteliste**: Gleichzeitige Anrufer werden gequeued, nach aktuellem QSO automatisch beantwortet
- **DX Tuning**: Automatisierte 18-Zyklen Gain-Messung, Presets pro Band
- **Signalverarbeitung**: 5-Pass Signal Subtraction, Spectral Whitening, Sinc-Resampling, 50 LDPC-Iterationen
- **QSO-Zustandsmaschine**: Hunt-Modus + CQ-Modus, Even/Odd-Slot-Verwaltung, Retry-Logik, ADIF 3.1.7 Logging
- **Integriertes Logbuch**: Sortierbare Tabelle, Suche, DXCC-Zähler, QSO-Detail-Overlay
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

**Voraussetzungen:** macOS, Python 3.12+, FlexRadio SDR (FLEX-6000/8000 Serie) mit SmartSDR TCP API. Zwei Antennenanschlüsse für Diversity-Modus (optional — Einzelantenne läuft im Normal-Modus problemlos).

### Konfiguration

Einstellungen über die GUI oder direkt in `~/.simpleft8/config.json`: Rufzeichen, Locator, Radio-IP, Band, Leistungs-Preset, QRZ API-Key.

### Architektur

```
SimpleFT8/
├── main.py               # Einstiegspunkt
├── config/settings.py    # Einstellungen, Band-Frequenzen
├── core/                 # Decoder, Encoder, QSO-Zustandsmaschine, Diversity, Timing
├── radio/flexradio.py    # SmartSDR TCP + VITA-49 RX/TX Audio-Streaming
├── log/                  # ADIF Writer, QRZ.com API
└── ui/                   # PySide6 GUI (3-Panel Dark Theme)
```

### Radio-Kompatibilität

**Getestet:** FLEX-8400M. **Voraussichtlich kompatibel:** FLEX-6300/6400/6500/6600/6700/8400/8600 Serie.

### Lizenz

MIT License (c) 2026 DA1MHH (Mike Hammerer)

---

## Acknowledgments / Danksagungen

- [ft8_lib](https://github.com/kgoba/ft8_lib) — FT8/FT4 encode/decode C library (MIT)
- [FlexRadio Systems](https://www.flexradio.com/) — SmartSDR TCP API
- [WSJT-X](https://wsjt.sourceforge.io/) — Pioneering digital weak-signal modes

---

*SimpleFT8: Because weak signals deserve a fighting chance. / Weil schwache Signale eine faire Chance verdienen.*
