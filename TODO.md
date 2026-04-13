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

#### RMS Auto-Gain Control ✓ CODE FERTIG (v0.27)
**Status:** Integriert in decoder.py, aktiv. Unit Tests bestanden.
- [x] RMS-Messung nach Resample, vor Spectral Whitening
- [x] Gain-Faktor automatisch (Ziel: -12 dBFS = 8225 int16 RMS)
- [x] EMA α=0.02, ±3 dB Hysterese, Gain [0.1x..4.0x], Clipping-Schutz

**Im Feldtest prüfen (NUR MIT RADIO TESTBAR):**
- [ ] AGC-Gain konvergiert nahe 1.0 bei normalem Bandverkehr?
- [ ] Dreifache Normalisierung: Noise-Floor (raw) + AGC (12k) + Whitening (preprocess) — kollidieren die? Gain-Wert im Log beobachten: `[AGC] Gain=X.XXx`
- [ ] 40m abends: verhindert AGC Decoder-Übersteuerung?
- [ ] Stille → Gain rampt auf 4.0x Max. Kein Problem wenn danach Signale kommen?

#### Frequenz-Drift-Kompensation ⛔ ENTFERNT (13.04.2026)
Feldtest: 0 Nutzen, 400ms Overhead → entfernt. Code in Git-History (v0.30).
- [x] 6 Unit Tests (Shape, Clipping, Varianten, Analytic Signal, Audio-Change)
- [ ] **Feldtest:** Bringt es tatsaechlich neue Decodes? Log: `[Drift] +N Stationen`
- [ ] Performance-Impact akzeptabel? (~400ms extra pro Zyklus)

---

### PRIO 4 — Langfristig / Refactoring

#### main_window.py aufteilen ✓ ERLEDIGT (v0.29)
- [x] 1755→473 Zeilen via Mixin-Pattern (4 Mixins: Cycle, QSO, Radio, TX)
- [x] `ui/mw_cycle.py` (360Z) — Zyklusverarbeitung, Diversity Akkumulation
- [x] `ui/mw_qso.py` (304Z) — QSO-Callbacks, CQ, QRZ
- [x] `ui/mw_radio.py` (554Z) — Radio, Band, Diversity, DX-Tuning
- [x] `ui/mw_tx.py` (139Z) — TX-Regelung, Meter, SWR
- [x] 29 permanente Unit Tests in `tests/test_modules.py`

---

## VORBEREITET — Noch deaktiviert (Secrets intern)

### OMNI-TX v3.2 (`core/omni_tx.py`) — ⛔ GEHEIM ✓ HOOKS KOMPLETT (v0.26)
**Status:** Vollständig integriert — Easter Egg aktivierbar (Klick Versionsnummer)
- [x] Hook: `should_tx()` in `_on_send_message` (nur CQ, QSO-Schutz!)
- [x] `advance(qso_active)` pro Zyklus in `_on_cycle_start`
- [x] `on_qso_started()` bei TX_CALL in `_on_state_changed`
- [ ] Feldtest: 5-Slot-Muster verifizieren, Block-Wechsel beobachten

### Propagation-Balken (`core/propagation.py`) ✓ GETESTET (13.04.2026)
**Status:** Funktioniert! HamQSL Band-Gruppen-Fix angewendet.
- [x] Balken erscheinen nach ~3s App-Start
- [x] Farben plausibel: 20m/30m=grün, 15m/17m=gelb, 80m/40m/10m/12m=rot
- [x] Stimmt mit HAM-Toolbox überein (Screenshot-Vergleich)

---

## NUR MIT RADIO TESTBAR — Feldtest-Checkliste

**Diese Punkte können NICHT offline getestet werden. Beim nächsten Einschalten prüfen:**

### AGC (decoder.py) ⛔ DEAKTIVIERT (13.04.2026)
**Ergebnis:** AGC kollidiert mit Noise-Floor-Norm → 4x Gain → Clipping → 0-2 Stationen.
DeepSeek-Analyse: Dreifach-Normalisierung (Noise-Floor + Whitening + RMS) reicht aus.
AGC ist NICHT noetig und bleibt deaktiviert.

### DT-Zeitkorrektur (ntp_time.py) ✓ GETESTET (13.04.2026)
**Ergebnis:** Funktioniert! Kumulative Korrektur, 4-Zyklen-Messung, 20-Zyklen-Betrieb.
- [x] DT-Werte nach Korrektur bei ±0.2 (vorher +0.7)
- [x] TX-Timing auf ICOM: stabil +0.2 (perfekt)
- [x] Kumulative Korrektur verhindert Oszillation
- [x] Startup Audio-Purge (2s) verhindert Müll-DT beim Start
- [x] Anzeige in Statusbar: `DT: +0.XXs`

### AP-Lite (ap_lite.py)
- [ ] Erst nach Feldtest `AP_LITE_ENABLED = True` setzen!
- [ ] Threshold 0.75 kalibrieren: zu viele False Positives? Zu wenige Rescues?
- [ ] Costas-Alignment findet korrekte Verschiebung?
- [ ] `generate_reference_wave()` erzeugt identisches Signal wie Gegenstation?

### OMNI-TX (omni_tx.py)
- [ ] Easter-Egg-Aktivierung funktioniert (Klick Versionsnummer)?
- [ ] 5-Slot-Muster TX-TX-RX-RX-RX sichtbar im Log?
- [ ] Block-Wechsel alle N Zyklen beobachtbar?
- [ ] QSO wird NICHT durch OMNI-TX unterbrochen?

### Propagation (propagation.py) ✓ GETESTET (13.04.2026)
- [x] HamQSL-Abruf funktioniert
- [x] Farben stimmen (verglichen mit HAM-Toolbox)
- [x] Band-Gruppen-Fix: "80m-40m" → einzelne Bänder aufgelöst

### Radio-Abstraktionsschicht ✓ GETESTET (13.04.2026)
- [x] `create_radio(settings)` → FlexRadio Instanz funktioniert
- [x] PREAMP_PRESETS werden korrekt geladen
- [x] Bandwechsel, Diversity, DX Tuning: keine Regression

---

## ERLEDIGTE FEATURES

### 12.04.2026 (Session 3 — Opus+DeepSeek Full Review + Refactoring)
- [x] RMS Auto-Gain Control: `_apply_agc()` in decoder.py (v0.27)
- [x] README.md + README_DE.md: ungetestete Features mit ⚠️ markiert
- [x] BUG FIX: `main_window.py:1421` — undefinierte Variable `msg` in QRZ-Upload (→ NameError)
- [x] BUG FIX: `ntp_time.py:reset()` — Lock hinzugefügt (Race Condition)
- [x] DeepSeek Full Code Review: 11 Dateien, 1675 Zeilen — 2 echte Bugs gefunden + gefixt
- [x] 8 Unit Tests geschrieben + bestanden (AGC, NTP, OMNI-TX, AP-Lite, Diversity, Factory, Propagation, Syntax)
- [x] **REFACTORING: Radio-Abstraktion komplett (v0.28)** — 22→0 private FlexRadio-Zugriffe in main_window.py
  - 10 neue public API Methoden + 3 Properties in FlexRadio
  - base_radio.py (ABC) mit 3 abstract + 6 default methods erweitert
  - IC-7300 Fork: nur noch `radio/ic7300.py` mit den 10 Methoden implementieren
- [x] **main_window.py Split (v0.29)** — 1755→473 Zeilen, 4 Mixins, 29→35 Unit Tests
- [x] Frequenz-Drift-Kompensation implementiert, nach Feldtest wieder ENTFERNT (0 Nutzen, 400ms Overhead)

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

## IC-7300 FORK — Detaillierte Planung

**Status:** Radio-Abstraktions-Layer FERTIG (v0.25): `base_radio.py` + `radio_factory.py` + `presets.py`
**Nächster Schritt:** FlexRadio-spezifische Aufrufe aus main_window.py abstrahieren!

### Problem: 22 direkte FlexRadio-Zugriffe in main_window.py

main_window.py greift 22× direkt auf FlexRadio-Interna zu:

| Zugriff | Vorkommen | Abstraktion nötig |
|---------|-----------|-------------------|
| `self.radio._send_cmd(...)` | 12× | → `set_antenna()`, `set_rfgain()`, `set_txant()` |
| `self.radio._slice_idx` | 6× | → Flex-spezifisch (IC-7300 hat keine Slices) |
| `self.radio._slice_idx_b` | 1× | → Nur Flex-Diversity mit 2 Slices |
| `self.radio._tx_audio_level` | 2× | → `get_tx_level()` / `set_tx_level()` |
| `self.radio._last_swr` | 1× | → `get_last_swr()` |
| `self.radio._last_tx_raw_peak` | 1× | → `get_tx_peak()` (via Meter) |

### Refactoring-Plan (NÄCHSTE SESSION)

**Phase 1: Abstraktionsmethoden in FlexRadio ✓ ERLEDIGT (v0.28)**
- [x] `set_rx_antenna(ant)`, `set_tx_antenna(ant)`, `set_rfgain(gain)`
- [x] `set_rfgain_secondary(gain)`, `has_secondary_slice()`
- [x] `set_rfpower_direct(value)`
- [x] Properties: `last_swr`, `tx_raw_peak`, `tx_audio_level` (r/w)
- [x] `set_frequency()` + `apply_ft8_preset()` nutzen internen `_slice_idx`
- [x] `base_radio.py` (ABC) erweitert: 3 abstract + 6 default methods

**Phase 2: main_window.py entkoppelt ✓ ERLEDIGT (v0.28)**
- [x] Alle 22 `_send_cmd` / `_slice_idx` Zugriffe eliminiert
- [x] `_slice_idx_b` durch `has_secondary_slice()` + `set_rfgain_secondary()` ersetzt
- [x] Kein `self.radio._xxx` mehr in main_window.py — verifiziert via grep

**Phase 3: IC-7300 implementieren**
- [ ] `radio/ic7300.py` — `IC7300Interface` (CI-V + sounddevice)
- [ ] Audio: USB Audio über `sounddevice` (kein VITA-49!)
- [ ] Steuerung: CI-V Serial (`iu2frl-civ` Library, `/dev/ttyUSB0`)
- [ ] PTT: CI-V 0x1C oder RTS
- [ ] Meter: CI-V Poll (SWR: 0x15, Power: 0x16)

**Was GLEICH bleibt (radio-agnostisch):**
- Decoder/Encoder Pipeline (PCM Audio)
- QSO State Machine
- GUI komplett
- Diversity-Logik (wenn 2 Antennen vorhanden)
- Alle FT8-Optimierungen (AGC, Whitening, Subtraction)
