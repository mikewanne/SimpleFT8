# SimpleFT8 — Temporal Polarization Diversity for FT8

🇬🇧 **English** | [🇩🇪 Deutsch](#deutsch)

---

**WORK IN PROGRESS / BAUSTELLE** — This is an early proof-of-concept, far from a finished program. But the core idea works and RX is functional.

**A proof-of-concept FT8 client that introduces Temporal Polarization Diversity — a novel technique to dramatically increase weak signal decoding on any dual-antenna radio.**

> **3.4x more stations decoded** compared to single-antenna operation under poor conditions.
> Tested on FlexRadio 8400M with a multiband dipole + rain gutter as second antenna.

**Status:** RX works. TX works (30+ PSKReporter spots). Full QSO cycle not yet tested end-to-end. Many rough edges. Published to timestamp the concept, not to ship a product.

---

## The Concept: Temporal Polarization Diversity

### The Problem

FT8 stations are decoded from 15-second audio windows. A single antenna has one polarization pattern and radiation characteristic. Stations whose polarization or arrival angle doesn't match your antenna are weak or invisible.

Most SDR radios with two antenna ports (like the FlexRadio 8400M) have only **one receiver (SCU)** — so you can't listen on both antennas simultaneously. True simultaneous diversity requires expensive dual-receiver models.

### The Solution

**Switch antennas every FT8 cycle (15 seconds) and accumulate stations across cycles.**

```
Cycle 1 (ANT1): Decode → 12 stations found
Cycle 2 (ANT2): Decode → 14 stations found (some overlap, some new)
Cycle 3 (ANT1): Decode → 11 stations found
Cycle 4 (ANT2): Decode → 13 stations found
                          ─────────────────
Accumulated unique:       48 stations (vs 14 with single antenna)
```

Key rules:
- **Accumulate, don't replace**: New cycle results merge with existing stations
- **Keep best SNR**: When a station is heard on both antennas, keep the stronger reading
- **Age out stale entries**: Stations not heard for >2 minutes are removed
- **Mark antenna source**: `[A1]`, `[A2]`, `[A1>2]` (ANT1 stronger), `[A2>1]` (ANT2 stronger)
- **TX always on ANT1**: Never switch antenna during transmit
- **Non-blocking antenna commands**: Sent in a separate thread so keepalive and audio stream are never interrupted
- **No second slice needed**: Uses the same single slice/receiver — just switches the antenna input
- **Single decoder**: One decoder instance, one audio stream — ~20 lines of additional code

### Why This Works

FT8 signals are persistent — a station calling CQ will repeat for many cycles. By alternating antennas, you capture stations that are only strong on one polarization/pattern. The 15-second FT8 cycle is the natural switching interval — no audio is lost, no decode is interrupted.

This works on **any radio with two antenna ports**, even single-receiver models. No hardware modification needed. ~20 lines of code.

### Measured Results (2026-04-02, 20m band, POOR conditions)

| Mode | Stations | Setup |
|------|----------|-------|
| **Single Antenna (ANT1)** | 14 | Multiband dipole (vertical, 10cm from wall) |
| **Temporal Diversity (ANT1+ANT2)** | **48** | + Rain gutter (horizontal) as ANT2 |
| IC-7300 + WSJT-X (reference) | 22 | Same location, same time |

**3.4x improvement.** Farthest station: New Zealand, 18,000 km — received on the rain gutter.

---

## DX Tuning (Automatic Antenna Measurement)

SimpleFT8 includes an automated measurement dialog that optimizes antenna + gain per band:

**Phase 1 — Antenna comparison:**
1. Listen on ANT1 for 3 FT8 cycles, record Top-5 strongest stations (average SNR)
2. Switch to ANT2, repeat 3 cycles
3. Winner = antenna with higher Top-5 average

**Phase 2 — Gain optimization:**
4. On the winning antenna, test RF gain 0, 10, 20 dB (3 cycles each)
5. Save optimal antenna + gain as preset for this band

**Automatic loading:**
6. On band change: preset is loaded automatically — no manual tuning needed
7. When conditions change (rain/sun): re-measure takes ~3-5 minutes

---

## What SimpleFT8 Is (and Isn't)

**This is a proof-of-concept.** It demonstrates that Temporal Polarization Diversity works and delivers massive gains with minimal code.

It is **not** a polished product. It's a working FT8 client built in one week by one ham (DA1MHH) with AI assistance (Claude). It has rough edges, incomplete features, and no unit tests.

**What works:**
- Full FT8 RX/TX via VITA-49 (no SmartSDR needed)
- 3 RX modes: Normal / Diversity / DX Tuning
- Signal Subtraction (5 passes), Spectral Whitening, Anti-Alias Resampling
- CQ mode with auto-reply, QSO state machine
- Country detection, distance calculation, ADIF export
- PSKReporter integration, 30+ confirmed spots with 10W

**What's incomplete:**
- Full QSO cycle not yet live-tested end-to-end
- FT4 mode not implemented
- AP decoding (a-priori) only stubbed
- OSD decoder incomplete
- No unit tests

---

## Technical Details

| Component | Technology |
|-----------|-----------|
| Language | Python 3.12 |
| GUI | PySide6 (Qt6) |
| FT8 Codec | PyFT8 2.6.1 |
| Audio RX/TX | VITA-49 UDP, int16 mono 24kHz |
| Rig Control | SmartSDR TCP API (Port 4992) |
| Config | ~/.simpleft8/config.json |

### Decoder Pipeline

```
VITA-49 Audio (24kHz)
  → Anti-Alias Lowpass (Sinc/Hamming, fc=6kHz, 63 taps)
  → Resample to 12kHz
  → DC Remove
  → Spectral Whitening (Overlap-Add FFT, Median Noise Floor)
  → Normalization (-12 dBFS)
  → Window Sliding (0, +0.3s, -0.3s offset)
  → FT8 Decode (Costas Sync → Demap → LDPC 50 iter → CRC → Unpack)
  → Signal Subtraction (up to 5 passes)
  → Result Fusion + Deduplication
```

### Diversity Implementation (core logic)

```python
# At each FT8 cycle start:
if diversity_cycle % 2 == 0:
    radio.set_antenna("ANT1")
    radio.set_rf_gain(preset.gain_ant1)
else:
    radio.set_antenna("ANT2")
    radio.set_rf_gain(preset.gain_ant2)

# After decode: accumulate (don't replace)
for station in new_stations:
    if station.call in accumulated:
        if station.snr > accumulated[station.call].snr:
            accumulated[station.call] = station  # Keep stronger
    else:
        accumulated[station.call] = station

# Age out stations not heard for >2 minutes
cutoff = time.time() - 120
accumulated = {k: v for k, v in accumulated.items() if v.last_heard > cutoff}
```

---

## Tested On

- **Mac Mini M2** + FlexRadio 8400M
- **iMac Pro** + FlexRadio 8400M
- macOS, Python 3.12, PySide6
- Antennas: Multiband dipole (vertical) + rain gutter (horizontal)

## Installation

```bash
git clone https://github.com/DA1MHH/SimpleFT8.git
cd SimpleFT8
python3.12 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python main.py
```

**Requires:** A FlexRadio with SmartSDR TCP API (tested on 8400M, should work on 6xxx/8600M).

## License

MIT License — free for everyone. Use it, modify it, build on it, integrate it into your software.

---

---

<a name="deutsch"></a>
# 🇩🇪 SimpleFT8 — Temporal Polarization Diversity fuer FT8

**BAUSTELLE / WORK IN PROGRESS** — Das ist eine fruehe Machbarkeitsstudie, weit entfernt von einem fertigen Programm. Aber die Kernidee funktioniert und der Empfang laeuft.

**Eine Machbarkeitsstudie: FT8-Client mit Temporal Polarization Diversity — eine neue Technik die das Dekodieren schwacher Signale auf jedem Dual-Antennen-Radio drastisch verbessert.**

> **3,4x mehr Stationen dekodiert** im Vergleich zu Single-Antenna bei schlechten Bedingungen.
> Getestet am FlexRadio 8400M mit Multiband-Dipol + Regenrinne als zweite Antenne.

**Status:** RX funktioniert. TX funktioniert (30+ PSKReporter-Spots). Vollstaendiger QSO-Zyklus noch nicht End-to-End getestet. Viele raue Kanten. Veroeffentlicht um das Konzept mit Zeitstempel zu dokumentieren, nicht um ein Produkt zu liefern.

---

## Das Konzept: Temporal Polarization Diversity

### Das Problem

FT8-Stationen werden aus 15-Sekunden-Audiofenstern dekodiert. Eine einzelne Antenne hat ein festes Polarisationsmuster und eine feste Abstrahlcharakteristik. Stationen deren Polarisation oder Eintreffwinkel nicht zur Antenne passt, sind schwach oder unsichtbar.

Die meisten SDR-Radios mit zwei Antennenanschluessen (wie das FlexRadio 8400M) haben nur **einen Empfaenger (SCU)** — man kann also nicht gleichzeitig auf beiden Antennen hoeren. Echtes Simultandiversity braucht teure Dual-Receiver-Modelle.

### Die Loesung

**Antenne bei jedem FT8-Zyklus (15 Sekunden) wechseln und Stationen ueber mehrere Zyklen akkumulieren.**

```
Zyklus 1 (ANT1): Dekodierung → 12 Stationen gefunden
Zyklus 2 (ANT2): Dekodierung → 14 Stationen gefunden (Ueberlappung + neue)
Zyklus 3 (ANT1): Dekodierung → 11 Stationen gefunden
Zyklus 4 (ANT2): Dekodierung → 13 Stationen gefunden
                                ─────────────────
Akkumuliert einzigartig:        48 Stationen (vs 14 mit einer Antenne)
```

Regeln:
- **Akkumulieren, nicht ersetzen**: Neue Zyklusergebnisse werden mit bestehenden Stationen zusammengefuehrt
- **Besten SNR behalten**: Wird eine Station auf beiden Antennen gehoert, wird der staerkere Wert behalten
- **Veraltete Eintraege entfernen**: Stationen die >2 Minuten nicht mehr gehoert werden, werden entfernt
- **Antennenquelle markieren**: `[A1]`, `[A2]`, `[A1>2]` (ANT1 staerker), `[A2>1]` (ANT2 staerker)
- **TX immer auf ANT1**: Antenne wird beim Senden nie gewechselt
- **Non-blocking Antennenbefehle**: In eigenem Thread gesendet, damit Keepalive und Audio-Stream nicht blockiert werden
- **Kein zweiter Slice noetig**: Nutzt denselben einzelnen Slice/Receiver — wechselt nur den Antenneneingang
- **Ein Decoder**: Eine Decoder-Instanz, ein Audio-Stream — ~20 Zeilen zusaetzlicher Code

### Warum das funktioniert

FT8-Signale sind persistent — eine Station die CQ ruft, wiederholt das ueber viele Zyklen. Durch den Antennenwechsel fangen wir Stationen ein, die nur auf einer Polarisation/einem Muster stark sind. Der 15-Sekunden-FT8-Zyklus ist das natuerliche Umschaltintervall — kein Audio geht verloren, keine Dekodierung wird unterbrochen.

Das funktioniert auf **jedem Radio mit zwei Antennenanschluessen**, auch mit nur einem Empfaenger. Keine Hardware-Modifikation noetig. ~20 Zeilen Code.

### Gemessene Ergebnisse (02.04.2026, 20m-Band, SCHLECHTE Bedingungen)

| Modus | Stationen | Setup |
|-------|-----------|-------|
| **Single Antenna (ANT1)** | 14 | Multiband-Dipol (vertikal, 10cm Wandabstand) |
| **Temporal Diversity (ANT1+ANT2)** | **48** | + Regenrinne (horizontal) als ANT2 |
| IC-7300 + WSJT-X (Referenz) | 22 | Gleicher Standort, gleiche Zeit |

**3,4x Verbesserung.** Weiteste Station: Neuseeland, 18.000 km — empfangen ueber die Regenrinne.

---

## DX Tuning (Automatische Antennenmessung)

SimpleFT8 enthaelt einen automatischen Messdialog der Antenne + Gain pro Band optimiert:

**Phase 1 — Antennenvergleich:**
1. 3 FT8-Zyklen auf ANT1, Top-5 staerkste Stationen erfassen (Durchschnitts-SNR)
2. Auf ANT2 wechseln, 3 Zyklen wiederholen
3. Gewinner = Antenne mit hoeherem Top-5 Durchschnitt

**Phase 2 — Gain-Optimierung:**
4. Auf der Gewinner-Antenne RF-Gain 0, 10, 20 dB testen (je 3 Zyklen)
5. Optimale Antenne + Gain als Preset fuer dieses Band speichern

**Automatisches Laden:**
6. Bei Bandwechsel: Preset wird automatisch geladen — kein manuelles Tuning noetig
7. Bei wechselnden Bedingungen (Regen/Sonne): Neumessung dauert ca. 3-5 Minuten

---

## Was SimpleFT8 ist (und was nicht)

**Das ist eine Machbarkeitsstudie.** Es zeigt dass Temporal Polarization Diversity funktioniert und mit minimalem Code massive Gewinne liefert.

Es ist **kein** fertiges Produkt. Es ist ein funktionierender FT8-Client, gebaut in einer Woche von einem Funkamateur (DA1MHH) mit KI-Unterstuetzung (Claude). Es hat raue Kanten, unfertige Features und keine Unit-Tests.

**Was funktioniert:**
- Voller FT8 RX/TX ueber VITA-49 (kein SmartSDR noetig)
- 3 RX-Modi: Normal / Diversity / DX Tuning
- Signal Subtraction (5 Passes), Spectral Whitening, Anti-Alias Resampling
- CQ-Modus mit Auto-Antwort, QSO State Machine
- Laendererkennung, Entfernungsberechnung, ADIF-Export
- PSKReporter-Integration, 30+ bestaetigte Spots mit 10W

**Was noch fehlt:**
- Vollstaendiger QSO-Zyklus noch nicht live End-to-End getestet
- FT4-Modus nicht implementiert
- AP-Dekodierung (A-Priori) nur als Stub
- OSD-Decoder unvollstaendig
- Keine Unit-Tests

---

## Technische Details

| Komponente | Technologie |
|-----------|-----------|
| Sprache | Python 3.12 |
| GUI | PySide6 (Qt6) |
| FT8 Codec | PyFT8 2.6.1 |
| Audio RX/TX | VITA-49 UDP, int16 mono 24kHz |
| Rig Control | SmartSDR TCP API (Port 4992) |
| Config | ~/.simpleft8/config.json |

---

## Getestet auf

- **Mac Mini M2** + FlexRadio 8400M
- **iMac Pro** + FlexRadio 8400M
- macOS, Python 3.12, PySide6
- Antennen: Multiband-Dipol (vertikal) + Regenrinne (horizontal)

## Installation

```bash
git clone https://github.com/DA1MHH/SimpleFT8.git
cd SimpleFT8
python3.12 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python main.py
```

**Voraussetzung:** Ein FlexRadio mit SmartSDR TCP API (getestet am 8400M, sollte auf 6xxx/8600M funktionieren).

## Lizenz

MIT-Lizenz — frei fuer alle. Nutzen, aendern, erweitern, in eigene Software einbauen. Keine Einschraenkungen.

---

## Ueber dieses Projekt

**Konzept & Implementierung:** Mike Hammerer, DA1MHH (JO31, Herne, Deutschland)
**KI-Unterstuetzung:** Claude (Anthropic)
**Datum:** Maerz/April 2026

Das ist ein Amateurfunk-Projekt. Das Temporal Polarization Diversity Konzept wird hier als Prior Art veroeffentlicht — frei fuer jeden zum Nutzen, Bewerten, Verwerfen oder Einbauen in eigene Software.

73 de DA1MHH
