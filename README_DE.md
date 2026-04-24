# SimpleFT8 — Minimaler FT8/FT4 Client fuer FlexRadio auf macOS

[English](README.md) | **Deutsch**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![Platform: macOS](https://img.shields.io/badge/platform-macOS-lightgrey.svg)](https://www.apple.com/macos/)

**Direkte SmartSDR-Steuerung | Temporale Polarisations-Diversity | Adaptive Antennenwahl | Automatische TX-Leistungsregelung**

SimpleFT8 ist ein eigenstaendiger FT8/FT4 Client, der dein FlexRadio direkt ueber die SmartSDR TCP API steuert — kein SmartSDR GUI noetig. Mit temporaler Antennen-Diversity und UCB1-adaptiver Auswahl werden bis zu 8x mehr Stationen dekodiert als mit konventionellen Setups.

> **Jedes Feature ausfuehrlich erklaert:** Wie funktioniert es? Warum? Vor-/Nachteile? Physik + Formeln.
> Deutsch + Englisch → **[docs/explained/](docs/explained/)** (5 Features × 2 Sprachen = 10 Dokumente)

> **Optimieren ja — Automatisieren nein.** SimpleFT8 ist ein Operator-in-the-Loop-Tool. Es optimiert den Workflow, aber ersetzt nicht den menschlichen Entscheider. Alle automatisierten Funktionen — Totmannschalter (15 Min), semi-automatischer CQ-Modus, manueller Hunt-Modus — stellen sicher, dass der Operator stets die finale Kontrolle behaelt und eingreifen kann. Dies entspricht unserem Verstaendnis verantwortungsvoller Amateurfunk-Software und den regulatorischen Anforderungen (AFuV §16).

---

## Was macht SimpleFT8 anders?

Anders als WSJT-X oder aehnliche Clients, die SmartSDR benoetigen, kommuniziert SimpleFT8 **direkt** mit deinem FlexRadio ueber TCP (Port 4992) und streamt VITA-49 Audio ueber UDP (Port 4991). Das ermoeglicht:

- **Temporale Polarisations-Diversity**: Wechsel zwischen zwei Antennen pro FT8-Zyklus, Stationen beider Antennen werden akkumuliert
- **Automatische TX-Leistungsregelung**: Geschlossener Regelkreis haelt die tatsaechliche Ausgangsleistung auf dem eingestellten Wert
- **Komplett eigenstaendiger Betrieb**: Kein SmartSDR, keine virtuellen Audiokabel, kein DAX-Panel

### Die drei Empfangsmodi — kurz erklärt

SimpleFT8 kann mit einer oder zwei Antennen empfangen. Du hast drei Modi zur Auswahl:

- **Normal** — arbeitet wie jede andere FT8-Software mit einer Antenne. Perfekt, um zu sehen wie gut dein eigener Aufbau im Vergleich läuft.
- **Diversity Standard (für die Masse)** — mit zwei Antennen sucht das System in jeder Runde automatisch die bessere aus. Das Ergebnis: du hörst deutlich mehr Stationen auf einmal.
- **Diversity DX (für die Leisen)** — auch mit zwei Antennen, aber hier sucht die Software gezielt nach der Antenne, die ganz schwache Signale besser einfängt. So findest du weit entfernte Stationen, die sonst unter dem Rauschen verschwinden.

| Modus | Antennen | Was er tut | Wofür |
|-------|----------|-----------|-------|
| **Normal** | 1 | Empfängt wie gewohnt | Vergleich mit anderer Software |
| **Diversity Standard** | 2 | Wählt die Antenne mit den meisten Stationen | Die Masse — möglichst viele hören |
| **Diversity DX** | 2 | Wählt die Antenne die schwache Signale besser hört | Die Leisen — weit entfernte Stationen |

→ Mehr Details: **[docs/explained/diversity-modes_de.md](docs/explained/diversity-modes_de.md)**

---

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

---

## Screenshots

**CQ-Modus mit DT-Korrektur, Propagation-Balken, Totmannschalter, PSKReporter 21 Spots (Max 6111km):**

![SimpleFT8 Komplett](docs/screenshots/simpleft8_v031_complete.png)

| Diversity 20m (DT-korrigiert, A1/A2) | Vergleichstest 40m (+37%) |
|:-:|:-:|
| ![Diversity 20m](docs/screenshots/diversity_20m_dt_corrected.png) | ![Vergleich](docs/screenshots/diversity_37stations_40m.png) |

**Warteliste in Aktion** — F1IQH ruft während laufendem QSO mit DL3AQJ → automatisch eingereiht → danach automatisch beantwortet. Echtes QSO, 40m FT8. *(Screenshot mit freundlicher Genehmigung von DL3AQJ — Danke!)*

![Warteliste QSO](docs/screenshots/warteliste_qso.png)

---

## Kern-Innovationen

Jede der drei Kernfunktionen hat eine eigene ausfuehrliche Dokumentation mit Screenshots und technischer Erklaerung:

- **[Temporale Polarisations-Diversity](docs/DIVERSITY_DE.md)** — Wie der Antennenwechsel funktioniert, UCB1 Algorithmus, Testergebnisse
- **[DX Tuning / Gain-Messung](docs/DX_TUNING_DE.md)** — Automatisierte Antennenoptimierung, Presets pro Band
- **[Automatische TX-Leistungsregelung](docs/POWER_REGULATION_DE.md)** — Geschlossener Regelkreis, Clipping-Schutz, Kalibrierung pro Band

---

## Funktionen

### Temporale Polarisations-Diversity
- Wechselt zwischen ANT1 und ANT2 in jedem 15-Sekunden FT8-Zyklus
- Sammelt dekodierte Stationen beider Antennen ohne Duplikate
- Visuelle Markierung zeigt, welche Stationen exklusiv pro Antenne sind (A1, A2, A1>2, A2>1)
- Funktioniert auf jedem FlexRadio mit zwei Antennenanschluessen (auch Single-SCU Modelle)

### UCB1 Adaptive Antennenwahl
- Im AUTO-Modus wird der Upper Confidence Bound (UCB1) Multi-Armed-Bandit-Algorithmus eingesetzt
- Findet dynamisch das optimale Antennenverhaeltnis: 70:30, 50:50 oder 30:70
- Passt sich laufend an wechselnde Ausbreitungsbedingungen an — kein manuelles Tuning noetig
- Explorationsbonus verhindert, dass eine unterabgetastete Antenne aufgegeben wird

### DX Tuning
- Automatisierte 18-Zyklen Wechselmessung beider Antennen
- Preamp-Gain-Optimierung pro Antenne und Band
- Presets werden gespeichert und bei Bandwechsel automatisch geladen

### Automatische TX-Leistungsregelung
- P-Regler Regelkreis ueber das FWDPWR-Meter des Radios
- Passt TX-Audiopegel (mic_level + Software-Gain) automatisch an, damit die tatsaechliche Wattleistung dem eingestellten Wert entspricht
- Kalibrierung pro Band gespeichert — sofortige Konvergenz bei Bandwechsel
- Clipping-Schutz: Ueberwacht den Audio-Spitzenpegel, stoppt Erhoehung bei drohender Verzerrung
- Kompensiert Antennen-/SWR-Aenderungen und Wetterbedingungen in Echtzeit

### Signalverarbeitung
- 5-Pass iterative Signal Subtraction fuer Schwachsignal-Erholung
- FFT-basiertes Spectral Whitening mit Median-Rauschboden-Normalisierung
- Anti-Alias Sinc-Resampling (63 Taps, Hamming-Fenster) von 24 kHz auf 12 kHz
- LDPC-Decoder mit 50 Iterationen, 200 Kandidaten, Multi-Sync LLR-Sweep

### QSO-Management
- **Hunt-Modus**: Klicke eine Station im RX-Panel an, um ein QSO zu starten
- **CQ-Modus**: Automatischer CQ-Ruf mit TX-Warteschlange fuer eingehende Anrufer
- Vollstaendige Zustandsmaschine: CQ -> Report -> RR73 -> ADIF-Log
- Einstellbare maximale Anrufversuche (3/5/7/99)
- Automatische Even/Odd Slot-Erkennung und -Korrektur

### Logging und Reporting
- ADIF 3.1.7 Export (Append-Modus)
- PSKReporter-Integration mit Spot-Statistik und Entfernungsanzeige
- Laendererkennung aus Rufzeichen-Prefix mit Entfernung in km

### Getestet und bestaetigt (Feldtest 13.04.2026)

- ✅ **DT-Zeitkorrektur**: Kumulative Korrektur aus Band-Konsens. 4-Zyklen-Messung, 20-Zyklen-Betrieb. DT-Werte ±0.2 (vorher +0.7). TX und RX gleichzeitig korrigiert. Bandwechsel behaelt Korrekturwert.
- ✅ **Propagation-Balken**: HamQSL-Solardaten mit Tageszeit-Korrektur fuer Mitteleuropa. Farben stimmen mit HAM-Toolbox ueberein. Band-Gruppen-Fix angewendet.
- ✅ **Operator Presence (Totmannschalter)**: 15 Min Timeout, Maus-Reset funktioniert.

### Implementiert — Feldtest laeuft

- ⚠️ **AP-Lite v2.2** *(aktiviert seit 13.04.2026)*: Schwache QSOs retten via kohaerenter Addition. Threshold 0.75, Feldtest-Kalibrierung laeuft.
### Operator Presence (Totmannschalter)
- **Gesetzliche Pflicht (DE)**: Operator muss am Funkgeraet anwesend sein — kein Bot-Betrieb
- Fest 15 Minuten Timeout, nicht konfigurierbar, nicht umgehbar
- 4px Countdown-Balken unter CQ-Button (gruen → gelb → rot)
- Reset durch Maus-/Tastaturaktivitaet im SimpleFT8-Fenster
- Bei Ablauf: CQ wird gestoppt, kein neuer TX — laufende QSOs werden zu Ende gefuehrt

---

## Installation

### Voraussetzungen
- macOS (getestet unter macOS 15 Sequoia)
- Python 3.12 oder neuer
- FlexRadio mit SmartSDR TCP API (FLEX-6000 / 8000 Serie)
- Zwei Antennenanschluesse fuer Diversity-Modus (optional)

### Einrichtung

```bash
git clone https://github.com/mikewanne/SimpleFT8.git
cd SimpleFT8

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

python3 main.py
```

### Abhaengigkeiten
- PySide6 (Qt6 GUI-Framework)
- PyFT8 2.6.1 (FT8/FT4 Encode/Decode)
- NumPy (Signalverarbeitung)
- sounddevice (Audio-Fallback)
- ntplib (Zeitsynchronisation)

---

## Konfiguration

SimpleFT8 speichert Einstellungen in `~/.simpleft8/config.json`:

```json
{
  "callsign": "DEINCALL",
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

Beim ersten Start wird die Datei mit Standardwerten angelegt. Trage dein Rufzeichen, deinen Locator und die Radio-IP ein, dann starte neu.

---

## Architektur

```
SimpleFT8/
├── main.py               # Einstiegspunkt + Instanz-Cleanup
├── config/
│   └── settings.py       # Einstellungen, Band-Frequenzen, FlexRadio IP
├── core/
│   ├── decoder.py        # FT8 Decode (PyFT8 + Subtraction + Whitening + AGC ⚠️)
│   ├── encoder.py        # FT8 Encode (PyFT8 -> VITA-49 TX)
│   ├── message.py        # FT8 Message Parser (CQ, Report, Grid, RR73)
│   ├── qso_state.py      # QSO-Zustandsmaschine (Hunt + CQ)
│   ├── diversity.py      # Diversity-Controller (Mess-/Betriebsphasen)
│   ├── timing.py         # UTC-Takt, 15s/7.5s Zyklus-Timing
│   ├── ap_lite.py        # ⚠️ UNGETESTET: AP-Lite v2.2 (kohärente Addition)
│   ├── ntp_time.py       # ⚠️ UNGETESTET: DT-Zeitkorrektur (Median-DT)
│   └── propagation.py    # ⚠️ UNGETESTET: Propagation-Balken (HamQSL)
├── radio/
│   ├── base_radio.py     # RadioInterface ABC (Kontrakt für alle Radios)
│   ├── presets.py        # PREAMP_PRESETS (radio-agnostisch)
│   ├── radio_factory.py  # create_radio(settings) → FlexRadio | IC7300 (zukünftig)
│   └── flexradio.py      # SmartSDR TCP + VITA-49 RX/TX Audio
├── log/
│   └── adif.py           # ADIF 3.1.7 Writer
├── ui/
│   ├── main_window.py    # 3-Panel QSplitter Layout
│   ├── rx_panel.py       # RX-Stationsliste (farbcodiert)
│   ├── qso_panel.py      # QSO-Verlauf (TX/RX chronologisch)
│   └── control_panel.py  # Modus, Band, Antenne, Radio, QSO-Steuerung
└── requirements.txt
```

### Verbindungsablauf

```
1. TCP-Verbindung zu radio:4992
2. SmartSDR-M trennen (Receiver-Ressourcen freigeben)
3. Eigenen Panadapter + Slice erstellen
4. Konfiguration: DIGU-Modus, DAX, TX-Stream
5. max_power_level=100, rfpower, mic_level setzen
6. VITA-49 Audio streamen: RX Decode + TX Encode
7. Keepalive alle 5 Sekunden
```

### Audio-Pipeline

```
VITA-49 RX (24kHz int16 mono)
  -> Anti-Alias Tiefpass (Sinc/Hamming, fc=6kHz)
  -> Resampling auf 12kHz
  -> DC-Entfernung
  -> Spectral Whitening (Overlap-Add FFT)
  -> Normalisierung (-12 dBFS)
  -> Fenster-Sliding (0, +0.3s, -0.3s Offsets)
  -> FT8 Decode (Costas Sync -> LDPC -> CRC -> Unpack)
  -> Signal Subtraction (bis zu 5 Passes)
  -> Ergebnis-Fusion + Deduplizierung
```

---

## Radio-Kompatibilitaet

**Getestet:**
- FLEX-8400M (primaere Entwicklungsplattform)

**Voraussichtlich kompatibel:**
- FLEX-6400 / 6400M / 6600 / 6600M / 6700
- FLEX-8400 / 8600 / 8600M

Jedes FlexRadio mit SmartSDR TCP API sollte funktionieren. Diversity erfordert zwei Antennenanschluesse.

**Radio-agnostische Architektur (ab v0.28):**
Die gesamte UI- und Decoder-Schicht ist vollstaendig vom Radio-Treiber entkoppelt. Neue Radios koennen durch Implementierung einer einzigen Datei (`radio/ic7300.py` etc.) angebunden werden — ohne Aenderungen am Rest der Software. Aktuell vorbereitet: **ICOM IC-7300** (CI-V + USB Audio).

---

## Bedienung

### Grundlegender Ablauf
1. SimpleFT8 starten — das Radio wird automatisch erkannt und verbunden
2. Band waehlen (20m, 40m usw.) — das Radio stimmt automatisch ab
3. Stationen erscheinen im RX-Panel
4. **Hunt-Modus**: Station anklicken, um sie zu rufen
5. **CQ-Modus**: CQ-Button druecken fuer automatisches Rufen

### Antennenmodi
- **NORMAL**: Einzelantenne (ANT1), Standard-FT8-Betrieb
- **DIVERSITY**: Temporaler Wechsel ANT1/ANT2, Stationen-Akkumulation
- **EINMESSEN (DX Tuning)**: Automatisierte Antennen- + Preamp-Messung

### Leistungssteuerung
Waehle die Leistung mit den 10W-100W Buttons. Die automatische Regelung passt den TX-Pegel an, damit die tatsaechliche Ausgangsleistung des Radios deiner Auswahl entspricht. Der TX-Balken zeigt den aktuellen Pegel, Peak zeigt die Audio-Reserve.

---

## Ausfuehrliche Feature-Dokumentation

Fuer jedes Feature gibt es eine eigene Erklaerung in Deutsch und Englisch — mit Physik, Formeln, Vor-/Nachteilen:

| Feature | Deutsch | English |
|---------|---------|---------|
| Signalverarbeitung | [signal-processing_de.md](docs/explained/signal-processing_de.md) | [signal-processing.md](docs/explained/signal-processing.md) |
| AP-Lite (QSO Rescue) | [ap-lite_de.md](docs/explained/ap-lite_de.md) | [ap-lite.md](docs/explained/ap-lite.md) |
| DT-Zeitkorrektur | [dt-correction_de.md](docs/explained/dt-correction_de.md) | [dt-correction.md](docs/explained/dt-correction.md) |
| Propagation-Anzeige | [propagation-indicators_de.md](docs/explained/propagation-indicators_de.md) | [propagation-indicators.md](docs/explained/propagation-indicators.md) |
| Operator Presence | [operator-presence_de.md](docs/explained/operator-presence_de.md) | [operator-presence.md](docs/explained/operator-presence.md) |

---

## Mitmachen

Beitraege sind willkommen! Bitte:
1. Oeffne ein Issue, um Aenderungen zu besprechen, bevor du einen PR einreichst
2. Halte dich an den bestehenden Code-Stil
3. Teste wenn moeglich mit einem echten FlexRadio

---

## Lizenz

MIT License (c) 2026 DA1MHH (Mike Hammerer)

Siehe [LICENSE](LICENSE) fuer Details.

---

## Danksagungen

- [PyFT8](https://github.com/kgoba/ft8_lib) — FT8/FT4 Encode/Decode Bibliothek
- [FlexRadio Systems](https://www.flexradio.com/) — SmartSDR TCP API
- [WSJT-X](https://wsjt.sourceforge.io/) — Wegbereiter digitaler Schwachsignal-Modi

---

*SimpleFT8: Weil schwache Signale eine faire Chance verdienen.*
