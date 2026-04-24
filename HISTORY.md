# SimpleFT8 — Änderungshistorie

Diese Datei wird nur ergänzt, niemals gelöscht oder überschrieben.
Format: `## YYYY-MM-DD — Kurztitel` → Änderungen darunter.

---

## 2026-04-23 (Abend) — DT-Timing vollständig korrigiert

**Betroffene Dateien:** `core/decoder.py`, `core/encoder.py`, `core/ntp_time.py`, `ui/mw_radio.py`

### Architektur-Änderung
- DT-Gesamtfehler (~0,77 s) in zwei Schichten aufgeteilt:
  - **Festwert** `DT_BUFFER_OFFSET` (FT8=2,0 / FT4=1,0 / FT2=0,8) — bekannte FlexRadio-Konstante, hardcodiert
  - **Adaptiv** `ntp_time.py` — konvergiert auf ~0,27 s Restfehler
- Vorteil: Kaltstart beginnt nahe am Zielwert, kleinerer Regelbereich → schnellere Konvergenz

### Bugfixes
- FT2 Even/Odd: `_slot_from_utc()` auf 3,8 s-Arithmetik korrigiert (war 7,5 s)
- Tune-Anzeige: `_tune_active` vor `set_frequency()` gesetzt
- PSK bei Bandwechsel: gelöscht + Timer-Reset + Interval 300 s (5 min Rate-Limit)
- Stats-Guard: pausiert bei CQ-Modus und laufendem QSO
- 15m Diversity: Preset laden oder Warnung "bitte KALIBRIEREN"
- 3 veraltete Tests auf neues Key-Format "FT8_20m" angepasst

### TX-Timing
- `TARGET_TX_OFFSET = -0,8 s` — kompensiert FlexRadio TX-Buffer 1,3 s
- Validiert: 8 Zyklen 0,0 s DT am Icom, 20m + 40m getestet

### Neue Docs
- `dt.md` erstellt (Theorie, Änderungen, Messergebnisse)

**Tests:** 167 passed

---

## 2026-04-23 (Nacht) — 3 kleine Features

**Betroffene Dateien:** `core/propagation.py`, `ui/mw_radio.py`, `core/station_accumulator.py`, `tests/test_modules.py`

### Features
1. **60m Propagation** — Interpolation 40m/80m war bereits implementiert, nur Docs angepasst
2. **RX-Liste leeren bei Antennen/Diversity-Wechsel** — `_on_rx_panel_toggled`, `_enable_diversity`, `_disable_diversity`
3. **Alte CQ-Rufe auto-löschen (>5 Min)** — neues Aging-Limit 300 s für CQ-Rufer in `station_accumulator.py`

### Tests
- `test_accumulator_aging` auf nicht-CQ-Message geändert
- Neuer Test `test_accumulator_cq_longer_aging`

**Tests:** 168 passed

---

## 2026-04-23 (Nacht II) — Stats-Guard Bug gefixt

**Betroffene Dateien:** `ui/mw_qso.py`, `core/qso_state.py`, `ui/mw_cycle.py`

### Root Cause (durch DeepSeek-Analyse gefunden)
In `_on_station_clicked` (manueller Klick auf Station während CQ):
1. `stop_cq()` setzte `cq_mode=False`
2. `start_qso()` speicherte `_was_cq = self.cq_mode = False` (schon False!)
3. Nach QSO-Ende: `_resume_cq_if_needed()` sah beide False → CQ wurde nicht resumed + Stats geloggt fälschlicherweise

### Fixes
- `mw_qso.py::_on_station_clicked` — `_cq_was_active` VOR `stop_cq()` sichern, nach `start_qso()` als `_was_cq=True` setzen
- `qso_state.py::_process_cq_reply` — `self._was_cq = True` explizit setzen
- `mw_cycle.py::_log_stats` — Guard um `btn_cq.isChecked()` erweitert (3-fach robust: Button + cq_mode + State)

**Tests:** 168 passed

---

## 2026-04-23 (Nachmittag) — Histogramm-Umbau + Bugfixes + Docs

**Betroffene Dateien:** `core/diversity.py`, `ui/mw_cycle.py`, `tests/test_modules.py`, `docs/`

### Architektur-Änderung: Histogramm 1:1 mit RX-Fenster

**Problem vorher:** Das Frequenz-Histogramm akkumulierte Daten über viele Zyklen und vergaß nie. Nutzer sah 5 Stationen im RX-Fenster, Histogramm zeigte 26 (historische Daten). Freie Frequenz wurde auf Basis veralteter Daten berechnet.

**Lösung:** Histogramm wird nach jedem Dekodierzyklus aus dem `station_accumulator` neu aufgebaut — exakt dieselbe Datenbasis wie das RX-Fenster. Der Accumulator hält Stationen 75–300 s (je nach Typ) und deckt damit automatisch mehrere Zyklen inkl. Even+Odd ab.

**Änderungen `core/diversity.py`:**
- `record_freq()` entfernt (akkumulierend, falsch)
- `_freq_histogram`, `_hist_lock` (threading.Lock) entfernt
- `_recalc_interval = 20` entfernt (tote Variable, nie gelesen)
- `import threading` entfernt
- `sync_from_stations(stations: dict)` neu — baut Histogramm 1:1 aus aktuellem Stationsstand
- `get_free_cq_freq()`: Search-Window auf vollen Bereich [150–2800 Hz] erweitert (vorher nur belegter Bereich)
- `get_free_cq_freq()`: Fallback-Bug gefixt — `None` statt Median-Frequenz wenn keine Lücke (Median lag mitten im belegten Bereich → Kollision → Oszillation)
- `update_proposed_freq()`: Lock in Kollisionserkennung entfernt
- `get_histogram_data()`: Lock entfernt
- `start_measure()`: `_freq_histogram = {}` entfernt (übernimmt sync_from_stations)

**Änderungen `ui/mw_cycle.py`:**
- Alle `record_freq()` Calls entfernt (3 Stellen: Messphase, Betriebsphase, Normal-Modus)
- Diversity-Betriebsphase: `accumulate_stations` kommt jetzt VOR Histogram-Update (war danach → Histogramm war einen Zyklus veraltet)
- `sync_from_stations(self._diversity_stations)` nach `accumulate_stations`
- Normal-Modus `_update_histogram()`: `sync_from_stations(self._normal_stations)`, `if messages:` Guard entfernt

**Änderungen `tests/test_modules.py`:**
- Hilfsfunktion `_make_stations(*freqs)` hinzugefügt
- 6 Tests von `record_freq()` auf `sync_from_stations()` umgestellt
- Assertions angepasst an neues Verhalten (Search-Window [150–2800]):
  - `test_cq_freq_high_activity`: prüft nun `freq < 1000 or freq > 2000` (Gap außerhalb des belegten Bereichs)
  - `test_cq_freq_stays_inside_occupied` → umbenannt in `test_cq_freq_finds_gap_outside_occupied`
  - `test_cq_freq_fallback_no_gap`: füllt jetzt alle Bins [150–2850 Hz], prüft `freq is None`

### Neue Docs (4 Dateien)
- `docs/FREQUENCY_HISTOGRAM.md` (EN) — Visualisierung, Algorithmus, Timing
- `docs/FREQUENCY_HISTOGRAM_DE.md` (DE)
- `docs/DT_CORRECTION.md` (EN) — Festwert + Adaptiv, Parameter, TX-Timing
- `docs/DT_CORRECTION_DE.md` (DE)

### CLAUDE.md + feierabend.md
- CLAUDE.md: Abschnitt "Änderungshistorie" + Verweis auf HISTORY.md ergänzt
- feierabend.md: Schritt 3 "HISTORY.md ergänzen" als Pflicht eingefügt

**Tests:** 168 passed

---

## 2026-04-24 — Workflow-Optimierung: opusplan als Standard

**Betroffene Dateien:** `~/.claude/settings.json`

### Änderung
- `"model": "opusplan"` dauerhaft in globaler Claude Code settings.json gesetzt
- **Verhalten:** Opus (claude-opus-4-7) übernimmt die Planungsphase, Sonnet (claude-sonnet-4-6) die Implementierung — automatisch, kein manueller Wechsel nötig
- **Grund:** Komplexere Aufgaben profitieren von Opus-Reasoning beim Planen, Sonnet ist für Code-Ausführung vollkommen ausreichend und schneller

---

## 2026-04-24 — Antennen-Label in TX-Zeilen des QSO-Panels

**Betroffene Dateien:** `ui/qso_panel.py`, `ui/mw_radio.py`, `ui/mw_qso.py`

### Feature
- TX-Zeilen im QSO-Panel zeigen jetzt Empfangsantenne + SNR-Delta:
  `11:47:00 [E] →  Sende   OE7RJV DA1MHH -23   ANT1 Δ7.0dB`
- Orange (Nachricht) + Grau (Label) auf einer Zeile — via `QTextCharFormat`
- Nur im Diversity-Modus, nur wenn `delta_db` bekannt
- CQ-Zeilen unverändert

### Technische Umsetzung
- `qso_panel.py::add_tx(message, ant_label="")` — rückwärtskompatible Erweiterung
- `qso_panel.py::_append_two_color()` — neue Hilfsmethode für zweifarbige Zeilen
- `mw_radio.py` — Lambda durch `self._on_tx_started` ersetzt (direkter Slot, sauberer)
- `mw_qso.py::_on_tx_started()` — liest `qso_sm.qso.their_call` + `_antenna_prefs.get_pref()`

**Tests:** 168 passed
