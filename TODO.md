# SimpleFT8 TODO — Stand 12.04.2026

---

## OFFENE AUFGABEN — Priorisiert

### PRIO 1 — Architektur (JETZT, bevor Code zu groß wird!)

#### Radio-Abstraktions-Layer für IC-7300 Fork
**Warum JETZT:** Jede weitere Woche macht den Fork schwieriger. FlexRadio-Code
wächst mit jedem Feature — je länger wir warten, desto mehr muss entkoppelt werden.

**Was zu tun ist:**
- [x] `radio/base_radio.py` — Abstract Base Class `RadioInterface` erstellt (15 Methoden)
- [x] `radio/presets.py` — PREAMP_PRESETS ausgelagert (radio-agnostisch)
- [x] `radio/radio_factory.py` — `create_radio(settings)` → FlexRadio (v0.25)
- [x] `radio/flexradio.py` — PREAMP_PRESETS jetzt aus presets.py importiert
- [x] `main_window.py`: FlexRadio-Import → `create_radio()` + `PREAMP_PRESETS` aus presets
- [x] `config/settings.py`: `radio_type: "flex"` als neue Setting
- [ ] Künftig: `radio/ic7300.py` — `IC7300Interface(RadioInterface)` (CI-V + sounddevice)

**IC-7300 Steuerung (für spätere Referenz):**
- Protokoll: CI-V über USB Serial (`/dev/ttyUSB0`, Adresse 0x94)
- Audio RX/TX: USB Audio über `sounddevice` (kein VITA-49!)
- PTT: CI-V Befehl 0x1C oder RTS
- Python Library: `iu2frl/iu2frl-civ` (GitHub, MIT)
- Frequenz: `device.read_operating_frequency()`, `device.set_operating_frequency()`

**Aufwand:** 2-4 Stunden Refactoring, null neue Features nötig, kein Risiko für Betrieb.

---

#### Settings Dialog — 2-Spalten Layout
**Problem:** 6 GroupBoxen vertikal gestapelt → zu hoch, unübersichtlich

**Neue Struktur (3 Gruppen, 2-Spalten):**
```
┌──────────────────────┬─────────────────────┐
│  Station & Hardware  │  TX & Schutz        │
│  Rufzeichen          │  Sendeleistung W    │
│  Locator             │  TX Audio-Pegel %   │
│  Radio IP            │  Anrufversuche      │
│                      │  SWR-Limit          │
│                      │  Tune-Leistung      │
├──────────────────────┴─────────────────────┤
│  FT8 & Antennen                            │
│  TX Audio-Frequenz Hz                      │
│  Max. Decode-Frequenz Hz                   │
│  Diversity-Zyklen                          │
└────────────────────────────────────────────┘
```
- [x] `ui/settings_dialog.py` auf 2-Spalten QHBoxLayout umgebaut (v0.24.x)
- [x] 3 Gruppen: Station & Hardware | TX & Schutz | FT8 & Antennen
- [x] ~40% weniger Höhe erreicht

---

### PRIO 2 — Features fertigstellen

#### AP-Lite v2.2 (`core/ap_lite.py`) ✓ CODE FERTIG (v0.26)
**Warum besser als OSD:** +4-5 dB (vs. OSD +1.2 dB), kein LDPC-Internals nötig.
**Status:** Vollständig integriert, `AP_LITE_ENABLED = False` bis Feldtest

- [x] `encoder.generate_reference_wave()` — int16→float32, normalisiert
- [x] `correlate_candidate()` — Cosinus-Ähnlichkeit + Costas-Gewichtung (DeepSeek)
- [x] `decoder.last_pcm_12k` — PCM-Buffer für AP-Lite zugänglich
- [x] Hook: `on_decode_failed()` bei erstem Fehler in WAIT_REPORT/WAIT_RR73
- [x] Hook: `try_rescue()` beim zweiten Fehler
- [ ] Threshold 0.75 im Feldtest kalibrieren → dann `AP_LITE_ENABLED = True`

#### DT-Zeitkorrektur (`core/ntp_time.py`) — Feldtest
**Status:** Code fertig + thread-sicher, UNGETESTET

**Im Feldtest prüfen:**
- [ ] Vorzeichen korrekt? (positiver Median → Uhr geht nach → positive Korrektur)
- [ ] Smoothing-Faktor 0.3 sinnvoll?
- [ ] 5 Stationen Minimum ausreichend?
- [ ] 50ms Deadband sinnvoll?
- [ ] Log prüfen: `[DT-Korr] Median=+0.XXXs → Korrektur=+0.XXXs (n=XX)`

#### Diversity-Messung FIX ✓ ERLEDIGT (v0.24.2)
- [x] `diversity.py`: OPERATE_CYCLES 80 → 60 (15 Min)
- [x] `main_window.py`: CQ_CALLING + CQ_WAIT aus Remeasure-Bedingung entfernt

---

### PRIO 3 — Neue Features (nach Feldtest)

#### RMS Auto-Gain Control (Audio-Eingang)
**Was:** Misst laufend RMS-Pegel des Audio-Eingangs, reguliert Gain automatisch.
**Warum:** 40m abends → viele starke Signale → Summe übersteuert → Decoder versagt.
Wir haben Spectral Whitening (Rauschboden), aber kein Eingangs-AGC.
- [ ] RMS-Messung vor Decoder-Pipeline einbauen
- [ ] Gain-Faktor automatisch anpassen (Ziel: -12 dBFS RMS)
- [ ] Hysterese damit es nicht pumpt

#### Frequenz-Drift-Kompensation
**Was:** FT8 hat 3× Costas-Arrays. Drift über 15s messbar → kompensieren.
**Warum:** Billige QRP-Gegenstationen driften 0.5-5 Hz → wir dekodieren sie schlechter.
Unser FlexRadio driftet nicht (GNSS), aber ihre Geräte schon.
- [ ] Drift aus Costas-Array Anfang/Mitte/Ende berechnen
- [ ] Signal vor LDPC linearisieren
- [ ] Gewinn: +5-10% mehr Decodes bei driftenden Gegenstationen

---

### PRIO 4 — Langfristig / Refactoring

#### main_window.py aufteilen (~1700 Zeilen)
- [ ] `ui/main_window_base.py` — Widget-Setup + Layout
- [ ] `ui/cycle_handler.py` — `_on_cycle_decoded()` und Timer-Logik
- [ ] `ui/qso_controller.py` — QSO-State-Machine Callbacks
- [ ] Macht auch Radio-Abstraktions-Layer einfacher

---

## VORBEREITET — Noch deaktiviert (Secrets intern)

### OMNI-TX v3.2 (`core/omni_tx.py`) — ⛔ GEHEIM ✓ HOOKS KOMPLETT (v0.26)
**Status:** Vollständig integriert — Easter Egg aktivierbar (Klick Versionsnummer)
- [x] Hook: `should_tx()` in `_on_send_message` (nur CQ, QSO-Schutz!)
- [x] `advance(qso_active)` pro Zyklus in `_on_cycle_start`
- [x] `on_qso_started()` bei TX_CALL in `_on_state_changed`
- [ ] Feldtest: 5-Slot-Muster verifizieren, Block-Wechsel beobachten

### Propagation-Balken (`core/propagation.py`)
**Status:** Aktiv — Feldtest ausstehend
- [ ] Balken erscheinen nach ~3s App-Start?
- [ ] Farben plausibel? 80m mittags = rot?

---

## ERLEDIGTE FEATURES

### 12.04.2026 (Session 2 — komplette Offline-Implementierung)
- [x] Radio-Abstraktions-Layer: base_radio.py + presets.py + radio_factory.py (v0.25)
- [x] Settings Dialog → 2-Spalten Layout, 40% kompakter
- [x] Diversity FIX: OPERATE_CYCLES 80→60, Remeasure-Sperre bei CQ/QSO
- [x] OMNI-TX Hooks komplett (3 Hooks, QSO-Schutz, Easter Egg voll funktionsfähig)
- [x] AP-Lite v2.2 Encoder-Integration: generate_reference_wave(), correlate_candidate() aktiviert, 2 Hooks
- [x] 50:50 Diversity Bug gefixt: A1-A2-A1-A2 → A1-A1-A2-A2 (Even+Odd je auf beide Antennen)
- [x] DeepSeek Review: 3 Bugfixes (omni_tx Block-Switch, propagation dead code, ntp_time Lock)
- [x] OSD von Roadmap gestrichen → AP-Lite ist der bessere Ansatz (+4-5dB vs +1.2dB)

### 09.04.2026
- [x] CQ 60s-Bug → jetzt 30s
- [x] Diversity UX: Dialog, CQ-Sperre, NEUEINMESSUNG, Zyklen einstellbar
- [x] RX-OFF Warnung in Titelleiste
- [x] TX-Status als Text (Clipschutz/Pegel/SWR)
- [x] Messung pausiert bei CQ/QSO

### 08.04.2026
- [x] TX-Timing Jitter-Fix (war -2.8..+1.2s, jetzt stabil)
- [x] TARGET_TX_OFFSET=-0.65
- [x] Kaltstart-Guard
- [x] UTC Slot-Start im QSO-Panel
- [x] "Beendet ist beendet" (5 Min Cooldown)

---

## IDEEN / SPÄTER
- [ ] Turbo FT8: Listen-Slot (einen TX-Slot überspringen um zweiten Caller zu erfassen)
- [ ] FT4 Modus
- [ ] QSO-Resume bei App-Neustart
- [ ] Band Map (visuelle Frequenz-Belegung)

---

## IC-7300 FORK — Zukünftige Planung
**Voraussetzung:** Radio-Abstraktions-Layer (PRIO 1 oben) muss zuerst rein!

**Was beim Fork getauscht wird:**
- `radio/flexradio.py` → `radio/ic7300.py`
- Audio: VITA-49 UDP → USB Audio (`sounddevice`)
- Steuerung: SmartSDR TCP → CI-V Serial (`iu2frl-civ` Library)
- PTT: TCP-Befehl → CI-V 0x1C oder RTS
- Antennen: ANT1/ANT2 TCP → CI-V Antenna Select (falls vorhanden)
- Meter: VITA-49 Meter → CI-V Poll (SWR: 0x15, Power: 0x16)

**Was GLEICH bleibt:**
- Gesamte Decoder/Encoder Pipeline (PCM Audio ist radio-agnostisch)
- QSO State Machine
- GUI komplett
- Diversity-Logik (wenn IC-7300 2 Antennen hat)
- Alle FT8-Optimierungen
