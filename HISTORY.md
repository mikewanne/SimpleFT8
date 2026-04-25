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

---

## 2026-04-24 v0.48 — CQ-Freq nur noch im belegten Bandbereich

**Betroffene Dateien:** `core/diversity.py`, `tests/test_modules.py`

### Bugfix
- `get_free_cq_freq()` suchte bisher im vollen [150–2800 Hz] Fenster
- Resultat: TX landete bei 2125 Hz obwohl alle Stationen bei 400–1100 Hz clusterten
- **Fix:** Search-Window = `[min(belegte Bins) – 2, max(belegte Bins) + 2]`, geclippt auf absolute Grenzen
- 2-Bin Rand (100 Hz) damit auch die allererste/letzte Lücke knapp außerhalb noch gefunden wird
- Test `test_proposed_freq_updates` auf Stationen mit echter innerer Lücke umgestellt

**Tests:** 168 passed

---

## 2026-04-24 v0.53 — Diversity-Panel UI-Politur

**Betroffene Dateien:** `ui/control_panel.py`

### Fixes & Verbesserungen
- **Label:** "Diversity Neuberechnung in X Zyklen" (fehlende "in" ergänzt)
- **Zentrierung:** 36px Spacer links in phase_row balanciert NEU-Button → Text exakt mittig
- **Nähe:** `phase_row` ohne oberen Margin — Label näher an Ratio-Zeile
- **DX-Counts:** `35 DX  01 DX` Format (2-stellig, Leerzeichen vor "DX", `--` wenn kein Wert noch)
- **Balkenfarbe:** Dunkelrot `#882222` → Mittelrot `#CC3333` → Hellrot `#FF5555` (heller = dringender)
- **Hintergrund Balken:** `#1a1010` (passt zu Rotton statt Grün-Dunkel)

**Tests:** 168 passed

---

## 2026-04-24 v0.52 — CQ-Freq zeitbasiert + Platz-Suche-Balken + Antennenwahl-Label

**Betroffene Dateien:** `core/diversity.py`, `ui/control_panel.py`, `ui/mw_cycle.py`

### Features
- **Label-Umbenennung:** "Neucheck in X" → "Antennenwahl in X" — verständlich für Funker
- **Neuer Countdown-Balken:** "Platz-Suche in Xs" — zeigt wann die freie TX-Frequenz neu berechnet wird (Sekunden, schrumpfend 120→0)
- **CQ-Freq Timing zeitbasiert:** Statt zyklus-basiert (FT2: 10×3.8s=38s!) jetzt:
  - Zeit-Fallback: 120s (für alle Modi gleich — FT8/FT4/FT2)
  - Minimum Dwell: 15s (kein Bounce-Back bei Kollision)
  - Kollisionserkennung: jedes Zyklus prüfen, bei ≥3 Nachbarn + 15s Dwell reagieren

### Technische Details
- `diversity.py`: `import time` + `RECALC_INTERVAL_S=120`, `MIN_DWELL_S=15`
- `diversity.py`: `_cycles_since_recalc` → `_last_recalc_time` + `_last_change_time` (float Unix-Zeit)
- `diversity.py`: neues Property `seconds_until_recalc` → int 0–120
- `control_panel.py`: `_cq_freq_lbl` + `_cq_freq_bar` im AntCard, Proxy in ControlPanel
- `control_panel.py`: neue Methode `update_cq_freq_countdown(remaining_s)`
- `mw_cycle.py`: 3 Aufrufstellen ergänzt (measure, operate, normal)

**Tests:** 168 passed

---

## 2026-04-24 v0.51 — Diversity Countdown-Balken + besseres Label

**Betroffene Dateien:** `ui/control_panel.py`

### Feature
- OPERATE-Phase: Label `"Neu in X Zyklen"` → `"Neucheck in X"` (verständlich für den Funker)
- Neuer schmaler Countdown-Balken (6 px) unter dem Label — schrumpft von 60→0
- Farbwechsel synchron mit Text: grün (>15), gelb (≤15), orange (≤5)
- Balken verschwindet automatisch in MESSEN- und NEUEINMESSUNG-Phase
- `QProgressBar` mit dynamischem Stylesheet, kein Custom-Widget nötig
- Proxy-Anbindung über `ant_card._operate_bar` in `ControlPanel.__init__()`

**Tests:** 168 passed

---

## 2026-04-24 v0.50 — freq_label Farbwechsel Grün ↔ Gelb (Tune-Feedback)

**Betroffene Dateien:** `ui/control_panel.py`, `ui/mw_radio.py`, `ui/mw_tx.py`

### Feature
- `freq_label` (oben links) zeigt Frequenz jetzt farbcodiert:
  - **Normal:** Grün (#00CC66) + Arbeitsfrequenz
  - **Tune aktiv:** Gelb (#FFD700) + Tune-Frequenz (z.B. -2 kHz Offset)
- Neue Methode `control_panel.set_freq_display(freq_mhz, tune_active=False)` — zentrales Farb-Update
- `_update_frequency()` delegiert an `set_freq_display()` (Band/Mode-Wechsel → automatisch Grün)
- `_on_mode_changed()` in mw_radio.py → `set_freq_display(..., False)`
- `_on_tune_clicked()` in mw_tx.py → `set_freq_display(..., True/False)` je nach Tune-State
- Tune-Sonderfall `tune_freq=None` (60m ohne Offset) → Gelb + Arbeitsfreq (korrekt)

**Tests:** 168 passed

---

## 2026-04-24 v0.49 — Versionsanzeige UI automatisch synchron

**Betroffene Dateien:** `ui/control_panel.py`, `main.py`

### Fix
- Versionsanzeige unten rechts zeigte hardcodiert "v0.26"
- `control_panel.py` importiert jetzt `APP_VERSION` aus `main.py`
- Label: `f"SimpleFT8 v{APP_VERSION}"` — ab jetzt automatisch korrekt
- `main.py` APP_VERSION auf 0.49 erhöht

**Tests:** 168 passed

---

## 2026-04-24 v0.54 — CQ-Freq Countdown sekündlich + glatt

**Betroffene Dateien:** `core/diversity.py`, `ui/control_panel.py`, `ui/mw_cycle.py`, `ui/main_window.py`

### Problem vorher
Countdown sprang z.B. 119→108→119 weil per-Zyklus-Updates die 120s-Range unregelmäßig aktualisierten (FT8=15s, FT4=7.5s, FT2=3.8s). Kein gleichmäßiges Runterzählen.

### Lösung
- **Neues Property `seconds_until_next_check`** in `diversity.py` — zählt 15→0 ab `_last_check_time`
- **`_last_check_time`** in `reset()` ergänzt; in `update_proposed_freq()` gesetzt:
  - Bei Erstberechnung
  - Jedes Mal wenn MIN_DWELL_S abgelaufen ist (ob Kollision oder nicht) → Display immer zurück auf 15
- **1-Sekunden QTimer** (`_cq_countdown_timer`) in `main_window.__init__()` → `_tick_cq_countdown()`
  - Aktiv nur wenn `_rx_mode == "diversity"` und `cq_freq_hz is not None`
  - Sonst: Widget ausgeblendet via `set_cq_countdown_visible(False)`
- **3 per-Zyklus-Calls** `update_cq_freq_countdown()` aus `mw_cycle.py` entfernt
- **Range** 0-120 → 0-15, Label: `"Prüfe nächste freie TX Frequenz in: X Sek."`
- **Neue Methode** `control_panel.set_cq_countdown_visible(bool)`
- **Farb-Schwellen** angepasst: ≤5s → #FF5555, ≤10s → #CC3333, sonst #882222
- **Hintergrund** korrigiert: `#1a1010` (war fälschlich `#1a2a1a`)

**Tests:** 168 passed

---

## 2026-04-24 v0.54 — README Antennenfotos + Transparenz-Caveat + PDF-Update

**Betroffene Dateien:** `README.md`, `scripts/generate_plots.py`, `docs/fotos/`

### README
- Neue Sektion "Antenna Setup" / "Antennensetup" (DE+EN) mit 2 Fotos:
  - `docs/fotos/Gesamt.png` — Gesamtansicht Haus, beide Antennen sichtbar
  - `docs/fotos/Gesamt_Farbe.png` — Annotiert: Gelb=ANT1, Rot=ANT2
- ANT1: Kelemen DP-201510, vertikal gespannter Mehrband-Halbwellendipol (20m/15m/10m),
  Einspeisepunkt an Dachgaube, 1:1-Balun, ein Arm hoch zur Dachspitze, einer runter
- ANT2: Regenrinne ~15m L-Form (5m waagerecht + 8m senkrecht + 2m waagerecht),
  zwischen λ/4 und λ/2 für 40m, nie als Antenne installiert — einfach angeklemmt
- Rohdaten-Link: `statistics/` Ordner (214 Dateien, jeder Zyklus geloggt)
- Messtage aktualisiert: 11.896 → 18.425 Zyklen, 3-4 → 4-5 Messtage

### Transparenz-Caveat (DE+EN, README + PDF)
- ANT1 auf 40m außerhalb Auslegungsband (20m/15m/10m) → suboptimal
- ANT2 (Regenrinne) auf 40m günstiger durch Länge/Form → erklärt großen Gewinn
- Ergebnisse als Obergrenze deklariert — nicht übertragbar auf andere Setups
- 20m-Folgetests angekündigt (ANT1 dort resonant, 20m generell besser)

### generate_plots.py PDF-Texte
- `p1_caveat`: Antennencaveat auf Titelseite (DE+EN)
- `p2_setup_body`: "mornings only" entfernt, aktueller Tagesbereich 05-23 UTC
- `p3_note2`: Obergrenze-Hinweis bei Ergebnistabelle (DE+EN)
- `p7_cannot_body`: Übertragbarkeit explizit verneint (DE+EN)
- `p7_next_body`: 20m-Folgetests angekündigt (DE+EN)
- "über beide Messtage" → "über alle Messtage" (DE+EN)

### Strategie für weitere Datensammlung
- Abfrage alle 2-3h welcher Modus die dünnste Abdeckung hat
- Ziel: Lücken bei 15-23 UTC für alle drei Modi schließen
- Diversity Standard als nächstes (14-16 UTC, 15h+16h = je 1 Tag)

**Tests:** 168 passed

---

## 2026-04-25 v0.54 — 20m Messungen gestartet + Nachtdaten Diversity DX

**Keine Code-Änderungen — nur Datensammlung**

### Datenlage Stand 25.04.2026 Vormittag
- **Diversity DX 40m**: Nachtlücke geschlossen — 15 neue Stunden (18–09 UTC)
- **20m gestartet**: Normal + Diversity parallel zu 40m
- **40m gesamt**: 22.251 Zyklen (Normal 6.793 / Div.Standard 6.542 / Div.DX 8.916)

### Strategie
- Alle 2-3h Modus prüfen, Lücken in Berliner Zeit (CEST=UTC+2) schließen
- 40m Restlücken: 08 CEST (Div.Standard), 12-13 CEST (Div.Standard), 21-23 CEST (Normal+Div.Standard)
- 20m: Tagsüber Normal sammeln, dann Diversity

**Tests:** 168 passed
