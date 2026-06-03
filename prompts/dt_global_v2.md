Du bist Senior Python-Entwickler für Amateurfunk-Timing/DSP (PySide6: Signal
statt pyqtSignal). Hobby-FT8-Tool, ein Operator, FlexRadio.

Deine einzige Aufgabe: diesen Umbau-Prompt KRITISIEREN — NICHT umsetzen.
Strukturierte Liste: Lücken, Unklarheiten, Widersprüche, Risiken, Verbesserungen.
Severity 🔴 Bug | 🟠 Risiko | 🟡 Verbesserung | ⚪ Hinweis. SCOPE-RESPEKT, KISS vor
Defensiv. Overengineering ist selbst ein Fehler.

================================================================================
DT-Korrektur: von per-(Modus,Band) auf EINEN GLOBALEN Wert
================================================================================

## Vorgeschichte (bereits mit Mike + DeepSeek geklärt — NICHT neu aufrollen)
Die gelernte DT-Korrektur (~0.26s) ist die KONSTANTE FlexRadio-RX-Hardware-/
Transport-Latenz (VITA-49). Sie ist **modus- UND band-unabhängig** (die
protokoll-/slot-abhängige Fensterlage wird SEPARAT über `_DT_OFFSETS` im Decoder
behandelt; das ist NICHT Teil dieses Umbaus). Empirisch bestätigt: in Mikes
`dt_corrections.json` matchen fast alle FT4/FT2-Werte die FT8-Werte; einziger
Ausreißer FT4_20m=0.0451 (statt ~0.27) ist ein 1-Stationen-Messartefakt
(`_MIN={FT8:3,FT4:1,FT2:1}`). **Mikes Entscheidung (explizit): EIN globaler Wert,
gelernt NUR aus FT8, genutzt von allen Modi/Bändern. FT4/FT2 schreiben nie.**
→ Vorschläge Richtung „doch per-Band" oder „Cross-Band-Median-Fallback" sind
out-of-scope (Mike will bewusst einen einzigen Wert).

## Ziel
`core/ntp_time.py` von per-(Modus,Band)-Speicherung + Cross-Modus-Fallback
(P48-B) auf EINEN persistenten globalen Korrekturwert umbauen. Macht das Modul
übersichtlicher und KISS.

## Ist-Zustand (core/ntp_time.py, verifiziert)
- `_saved: dict` = {"FT8_20m":0.27, "FT4_20m":0.045, ...}, Key `_mode_key()` =
  f"{_mode}_{_band}".
- `update_from_decoded(dt_values)` misst in ALLEN Modi (`_MIN={FT8:3,FT4:1,
  FT2:1}`), Median + MAD-Filter (`_filter_outliers_mad`), measure/operate-Phasen
  (`INITIAL_MEASURE_CYCLES=2`, `STEADY_MEASURE_CYCLES=2`, `OPERATE_CYCLES=10`),
  gedämpfte Korrektur (`DAMPING=0.7`), Totband (`DEADBAND=0.02`), Clamp
  `_MAX_CORR={FT8:1.0,FT4:0.5,FT2:0.3}`, Schnell-Konvergenz (P48-D), Sprung-Reset
  (operate, |median|>1.0 → corr=0), Speicherung via `_save_current()`.
- `set_mode(mode, band=None)` / `set_band(band)`: speichern alten Wert, laden
  neuen via `_load_for_current_key()` (eigener Wert → Legacy-Migration → P48-B
  Cross-Modus-Fallback → Hardware-Default), reset measure-Phase, setzen
  `_is_initial = _saved.get(_mode_key()) is None`.
- `set_hardware_default(value)` (main_window:185, FlexRadio 0.26) → setzt
  `_hardware_default_offset`, der heute nur im `_load_for_current_key`-Fallback
  greift.
- `get_correction()` (decoder:361 wendet sie als Audio-Buffer-Shift an;
  control_panel zeigt sie), `get_time()` (mw_cycle), `get_status_text()`,
  `reset(keep_correction)`.

## Aufrufer (Interface, NICHT brechen)
- `ui/mw_radio.py:486` `ntp_time.set_mode(mode, band)`
- `ui/mw_radio.py:724` `_ntp.set_band(band)`
- `ui/mw_cycle.py:279` `ntp_time.update_from_decoded(dt_values)`
- `ui/mw_cycle.py:265` `get_time()`, `core/decoder.py:361` `get_correction()`
- `ui/main_window.py:185` `set_hardware_default(rx_offset)`
- `get_status_text()` (control_panel), `reset()` (tests + app-start)

================================================================================
## NEUES MODELL (Akzeptanzkriterien)
================================================================================

1. **Ein globaler `_correction`** für alle Modi/Bänder. `set_mode`/`set_band`
   ändern `_correction` NICHT mehr (kein Laden/Speichern beim Wechsel) — sie
   aktualisieren nur `_mode`/`_band` (für Mess-Gating + Logging) und resetten die
   Mess-Phase (`_phase="measure"`, `_cycle_count=0`, `_measure_buffer=[]`). Das
   ist der Kern: Umschalten auf FT4/FT2 behält den FT8-Wert.
2. **Nur FT8 misst/schreibt.** In `update_from_decoded`: nach Median-Berechnung
   die DT-ANZEIGE (`_last_median_dt`, `_last_sample_count`) für ALLE Modi
   aktualisieren (Mike will die DT auch auf FT4/FT2 SEHEN), dann
   `if _mode != "FT8": return False` — keine Korrektur-/Phasen-/Save-Logik.
   Phasen-Maschine (measure/operate/Sprung-Reset/Schnell-Konvergenz/Save) läuft
   NUR für FT8. `_MIN` einheitlich = `MIN_STATIONS` (3); per-Modus-`_MIN` entfällt.
   Clamp `MAX_CORR_FT8 = 1.0` (per-Modus-Dict entfällt).
3. **Persistenz: neues Format** `{"dt_correction_s": <float>}` in derselben Datei
   `~/.simpleft8/dt_corrections.json`. `_save_current()` schreibt dieses Format.
4. **Migration (in-memory, KEIN Schreiben beim Import!):** `_load_saved()` liest
   die Datei. Hat sie `dt_correction_s` → benutze ihn (`_is_initial=False`). Hat
   sie alte Keys → globaler Wert = Median der `FT8_*`-Werte (Fallback Median
   ALLER numerischen Werte; sonst 0.0). NICHT zurückschreiben (Tests importieren
   das Modul; Mikes echte Datei nicht beim Import anfassen) — die Datei wird beim
   nächsten `_save_current()` (erste FT8-Messung) ins neue Format überführt.
5. **Seed:** `set_hardware_default(value)` setzt `_correction = value` NUR wenn
   noch kein gemessener/migrierter Wert existiert (`_is_initial` True und
   `_correction == 0.0`). So startet ein frisches System bei 0.26 statt 0.
   `_is_initial` bleibt nach Seed True (Hardware-Default ist kein eigener
   Messwert → erste FT8-Messung macht die gedämpfte Erstkorrektur).
6. **Entfernt:** `_mode_key()`, `_load_for_current_key()` (Cross-Modus-Fallback
   + Legacy-Per-Modus-Migration), per-Modus `_MIN`/`_MAX_CORR`-Dicts. Logs nutzen
   `_mode` statt `_mode_key()`.
7. **Unverändert:** MAD-Filter, Damping, Deadband, Schnell-Konvergenz, Sprung-
   Reset (jetzt nur FT8), `get_correction`/`get_time`/`get_status_text`,
   `reset(keep_correction)`-Semantik, decoder-Audio-Shift, Lock.
8. Tests grün.

================================================================================
## RANDBEDINGUNGEN
================================================================================
- **Decode-Unabhängigkeit (bereits geklärt):** die Korrektur ist KEINE
  Voraussetzung fürs Dekodieren (Decoder sucht Sync über Sekunden; DT wird AUS
  dekodierten Stationen gelernt; Kaltstart = Hardware-Default 0.26). Der Umbau
  darf daran nichts ändern.
- **Thread-Safety:** bestehender `_lock` bleibt; Schreib-/Phasen-State unter Lock.
- **Persistenz-Breaking-Change** am json-Format: explizit gewollt + migriert.
  Datei wird beim Import NICHT geschrieben (Test-/Daten-Sicherheit).
- Reine Timing-Logik, kein TX-Eingriff, ANT1/ANT2 unberührt.

================================================================================
## NICHT IM SCOPE
================================================================================
- `_DT_OFFSETS`/Decoder-Fensterlogik (separate, modus-abhängige Größe — bleibt).
- Per-Band- oder Cross-Band-Median-Varianten (Mike will EINEN Wert).
- TX-Timing (`TARGET_TX_OFFSET`, Encoder) — unberührt.
- FT4/FT2-DT-Readout über die Status-Median-Anzeige hinaus ausbauen.

================================================================================
## TEST-IMPACT (anzupassen)
================================================================================
- `tests/test_p48_dt_optimization.py`: die 5 `test_cross_mode_*` + 
  `test_load_for_current_key_returns_hardware_default` + die 3 `test_is_initial_*`
  kodieren das alte Per-Modus+Cross-Modus-Design → Cross-Modus-Tests entfernen
  (Konzept weg), is_initial/Hardware-Default auf das globale Modell umschreiben;
  `test_fast_convergence_*` bleiben (FT8). Encoder-/Settings-Tests unberührt.
- `tests/test_modules.py:562-570`: testet `set_mode("FT4")` lädt FT4-Wert →
  umschreiben: `set_mode("FT4")` lässt `_correction` UNVERÄNDERT (global).
- `tests/test_p_bundle_qol.py:201-208`: `_saved["FT4_40m"]` + Log
  `"[DT-Korr] FT4_40m: ..."` → auf neues Format/Logging umstellen.
- `tests/conftest.py` `_protect_dt_corrections_file` + `fresh_ntp`-Fixture
  (test_p48) bleiben nutzbar (setzen Modul-State direkt).

================================================================================
## TESTBARKEIT (unverzichtbar)
================================================================================
- set_mode/set_band ändern `_correction` nicht (Globalwert bleibt über
  Mode-/Band-Wechsel).
- FT4/FT2: `update_from_decoded` schreibt NICHT (kein `_save_current`, keine
  Korrektur-Änderung), aktualisiert aber `_last_median_dt` (Anzeige).
- FT8: misst + speichert wie bisher (Erstkorrektur, Feinkorrektur, Totband,
  Sprung-Reset, Schnell-Konvergenz).
- Migration: alte json {FT8_20m:.27, FT8_40m:.30, FT4_20m:.045} → globaler Wert =
  Median(FT8-Werte); FT4_20m-Müll verworfen. Import schreibt die Datei nicht.
- Seed: set_hardware_default(0.26) bei leerem State → `_correction==0.26`,
  `_is_initial==True`.

================================================================================
## OFFENE FRAGEN AN DICH
================================================================================
A) Migration: Median der FT8-Werte als Startwert — sinnvoll, oder lieber den
   FT8-Wert des AKTUELLEN Bandes bevorzugen (falls vorhanden)? Pro/Contra KISS.
B) DT-Anzeige für FT4/FT2 aktualisieren (aber nicht messen) — sinnvoll für die
   Beobachtbarkeit, oder unnötige Komplexität (dann FT4/FT2 ganz früh raus)?
C) Sprung-Reset nur auf FT8: Problem, wenn die Hardware-Latenz sich mal ändert
   während man lange auf FT4 hängt? (Realistisch bei Hobby-Betrieb?)
D) Übersehene Aufrufer/State-Abhängigkeiten beim Entfernen von `_mode_key`/
   `_load_for_current_key`?
