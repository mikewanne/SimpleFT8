# v0.93 Cache-Reuse + Mess-Refactor — V3 (Final-Plan an R1)

## Auftrag an R1

Dies ist der **finale V3-Plan** der aus V1 (Mike-Vision) + V2 (Self-Review,
7 Findings) + R1 (4 Mods Refactor) + Dichte-R1 (Score-Killer + MIN_STATIONS weg)
synthetisiert wurde. **Kritisch reviewen**, keine neuen Punkte aufmachen die
nicht in V1/V2/R1/Dichte-R1 standen — wir sind im Endgame.

**Auftrag:**
1. Implementierungs-Plan auf Vollstaendigkeit pruefen.
2. Reihenfolge der atomaren Commits sinnvoll? Atomar-Brueche identifizieren.
3. Migration-Strategie fuer alte Caches (1 → 2 Timestamps) tragfaehig?
4. Test-Strategie ausreichend? Welche Tests fehlen?
5. Edge-Cases die V1/V2/R1 uebersehen haben?
6. KISS-Check: Eintrag entdeckt der weggelassen werden kann?

**KEINE neuen Features einfuehren.** KEINE Architektur-Aenderungen vorschlagen.
Nur Plan kritisch reviewen.

---

## Kontext (aktueller Stand v0.92)

- Pipeline-Lock bulletproof (v0.92, gestern erledigt)
- Tests: 681 gruen
- Working Tree clean
- Memory: `project_diversity_cache_reuse.md` hat alle Detail-Discussions
- Diskussions-Trail: V1, V2, R1, Dichte-V1, Dichte-R1 in `prompts/`

---

## Mike's Vision (final)

1. **1 h Auto-Refresh atmosphaerisch** (modus-unabhaengig, atmosphaerisch korrekt)
2. **Pro-Band+Modus-Cache** mit 5-s-Toast (kein Klick)
3. **Normal-Modus raus** aus Cache-System (kein Auto-Refresh, kein Cache)
4. **OPERATE_CYCLES weg**, Settings-Option weg, _MULT fuer OPERATE_CYCLES weg
5. **MEASURE_CYCLES-_MULT BLEIBT** (FT8=6, FT4=12, FT2=24) — R1-Mod 1
6. **Pattern fair 3:3 BLEIBT** (v0.90, nicht aendern)

---

## R1's 4 Mods + Dichte-Mods (alle integriert)

### Mod 1: MEASURE_CYCLES-_MULT BEHALTEN
- Nur OPERATE_CYCLES-_MULT raus, MEASURE_CYCLES-_MULT bleibt
- Begruendung R1: FT2 in 23 s (= 6 × 3.8 s) zu kurz fuer statistische Basis

### Mod 2: PresetStore zwei Timestamps
- Aktuell ein `timestamp` fuer Gain UND Ratio
- Neu: `gain_timestamp` (6 h) + `ratio_timestamp` (1 h)
- `is_valid_gain(band, mode)` + `is_valid_ratio(band, mode)`
- `save_gain()` setzt `gain_timestamp`, `save_ratio()` setzt `ratio_timestamp`
- Migration: alte Eintraege mit `timestamp` → beide Felder = alter Wert

### Mod 3: CQ-Lock zusaetzlich zu QSO-Lock
- Aktuell `should_remeasure(qso_active)` blockt nur QSO
- Neu: `should_remeasure(qso_active, cq_active)`
- Aufruf in `mw_cycle.py` muss `cq_active` mitgeben

### Mod 4 (KILLER): Score statt station_count
- Aktuell `record_measurement` nutzt `dx_weak_count` (DX) oder `station_count` (Standard)
- Beide diskret bei FT2/FT4 → Median-Aufloesung schwach
- Neu: `score` (sum(snr+30)) wird schon uebergeben aber ignoriert
- 2-Zeilen-Aenderung: beide `append`-Calls auf `score` umstellen
- Konsequenz: `peak <= 1.0`-Schwelle in `_evaluate` + `_check_phase3_early_stop`
  auf `peak <= 5.0` anpassen (SNR-Skala statt Stueckzahl)

### Mod 5 (Bonus): MIN_MEASURE_STATIONS entfernen
- Aktuell blockt `can_measure(station_count)` Phase 3 wenn < 5 Stationen
- Bei FT2 oft Block-Trigger
- R1: `can_measure()` immer True, Auswertung in `_evaluate` faellt auf 50:50
  zurueck wenn peak <= 5.0

### Mod 6 (R1 optional, Mike-Entscheidung): scoring_mode bleibt
- DX-Modus zaehlt `dx_weak_count` (SNR<-10), Normal `station_count`
- Mit Score-Umstellung wird DX obsolet (SNR ist eh feiner)
- ABER: scoring_mode wird in vielen Stellen gelesen (UI-Texte, Cache-Keys)
- **Entscheidung:** scoring_mode-API bleibt, intern beide Modi nutzen `score`
- Begruendung: KISS, kein API-Bruch, Cache-Keys bleiben kompatibel
- Spaeterer separater Refactor moeglich

---

## Implementierungs-Plan (atomare Commits)

### Commit 1: PresetStore zwei Timestamps + Migration
**Files:**
- `core/preset_store.py`
  - `VALIDITY_SECONDS = 6*3600` → `GAIN_VALIDITY_SECONDS = 6*3600` + neu `RATIO_VALIDITY_SECONDS = 3600`
  - `is_valid()` → `is_valid_gain()` + neu `is_valid_ratio()`
  - `save_gain()` setzt `gain_timestamp` (statt `timestamp`)
  - `save_ratio()` setzt `ratio_timestamp` (vorher kein Timestamp!)
  - `_load()` Migration: alte `timestamp` → beide Felder = alter Wert
  - `get_age_minutes()` → `get_gain_age_minutes()` + neu `get_ratio_age_minutes()`

**Tests:**
- `tests/test_preset_store.py` (existiert?) erweitern oder neu:
  - `test_save_gain_sets_gain_timestamp_only`
  - `test_save_ratio_sets_ratio_timestamp_only`
  - `test_is_valid_gain_6h_window`
  - `test_is_valid_ratio_1h_window`
  - `test_migration_old_timestamp_to_both_fields`

**Migration-Strategie:**
- Beim ersten Load nach Update: wenn Eintrag nur `timestamp` hat (alt) →
  `gain_timestamp = ratio_timestamp = timestamp`
- Wenn Eintrag schon `gain_timestamp` hat (neu) → unangetastet
- Alter `timestamp`-Key bleibt drin fuer Backwards-Read, wird aber nicht mehr geschrieben

**Akzeptanz:**
- Alte Caches (`presets_standard.json` mit `timestamp`) lesbar
- Neue Caches haben `gain_timestamp` + `ratio_timestamp`
- `save_ratio()` aktualisiert NUR `ratio_timestamp`, nicht `gain_timestamp`

### Commit 2: DiversityController Score + MIN_MEASURE_STATIONS weg
**Files:**
- `core/diversity.py`
  - Z.29 `MIN_MEASURE_STATIONS = 5` → ENTFERNEN
  - Z.78-80 `can_measure(station_count)` → `can_measure()` immer True (oder ganz entfernen wenn unbenutzt)
  - Z.402-407 `record_measurement`: beide `append`-Calls auf `score` statt `dx_weak_count`/`station_count`
  - Z.436 `_check_phase3_early_stop`: `peak <= 1.0` → `peak <= 5.0`
  - Z.503 `_evaluate`: `peak <= 1.0` → `peak <= 5.0`
  - Docstring oben anpassen: scoring_mode beschreibt jetzt Sammlungsstrategie
    (Standard sammelt alle Stationen, DX nur SNR<-10), Score basiert auf SNR

**Tests:**
- `tests/test_diversity.py` Tests fuer record_measurement anpassen (score statt count)
- `tests/test_diversity_density.py` NEU: 6 Slots à 1-2 Stationen fuer FT2 →
  Score-basierter Median liefert Ratio-Entscheidung statt 50:50-Default
- `test_diversity_min_stations_removed` NEU: `can_measure()` immer True

**Akzeptanz:**
- Bei FT2 mit 1-2 Stationen pro Slot wird Phase 3 nicht mehr geblockt
- Score-basierter Median liefert kontinuierliche Werte → 70:30/30:70 moeglich
- `peak <= 5.0`-Schwelle haelt Default 50:50 bei sehr schwachem Empfang

### Commit 3: should_remeasure CQ-Lock + zeit-basiertes Re-Measure
**Files:**
- `core/diversity.py`
  - `should_remeasure(qso_active)` → `should_remeasure(qso_active, cq_active)`
  - Logik: `not qso_active and not cq_active`
  - **OPERATE_CYCLES-Logik raus**, dafuer `_last_measured_at` Property + Vergleich
    gegen `time.time() - 3600`
  - `_evaluate()` setzt `self._last_measured_at = time.time()`
  - `OPERATE_CYCLES = 60` Konstante BLEIBT noch (UI-Anzeige), aber `should_remeasure`
    nutzt sie nicht mehr → in Commit 5 vollstaendig raus
- `ui/mw_cycle.py`
  - `should_remeasure(qso_active)` Aufruf in Z.564 → `should_remeasure(qso_active, cq_active)`
  - `cq_active` aus `qso_sm.cq_mode` ableiten

**Tests:**
- `test_should_remeasure_cq_blocks` NEU
- `test_should_remeasure_qso_blocks`
- `test_should_remeasure_after_1h_triggers`
- `test_should_remeasure_under_1h_no_trigger`

**Akzeptanz:**
- Auto-Refresh nach 1 h, aber nicht waehrend QSO/CQ
- `_last_measured_at` wird in `_evaluate` gesetzt
- Tests `tests/test_modules.py:931` (OPERATE_CYCLES Modus-Faktor) muss umgeschrieben:
  alter Test prueft Zyklen-Counter, neuer Test prueft 1h-Frist

### Commit 4: Cache-Reuse bei Bandwechsel (5-s-Toast)
**Files:**
- `ui/mw_radio.py`
  - Im `_on_band_changed` Pfad VOR `_diversity_ctrl.on_band_change()`:
    Cache-Check fuer `_standard_store`/`_dx_store` mit `is_valid_ratio(band, mode)`
  - Bei valid Cache: Phase=operate setzen, ratio + dominant aus Cache laden,
    `_last_measured_at = time.time() - age_seconds` setzen, 5-s-Toast
  - Bei NICHT valid: aktueller Pfad (Phase 3 messen)
- `ui/bandpilot_dialogs.py` ODER neu `ui/diversity_cache_toast.py`
  - 5-s-Toast non-modal (vergleichbar mit Bandpilot-Toast)
  - Text: „Diversity aus Cache — A1 70:30, vor 23 Min gemessen"
  - QTimer-Auto-Close 5000 ms

**Tests:**
- `tests/test_diversity_cache_reuse.py` NEU:
  - `test_band_change_with_valid_cache_skips_phase3`
  - `test_band_change_with_expired_cache_runs_phase3`
  - `test_cache_reuse_loads_ratio_and_dominant`
  - `test_cache_reuse_sets_last_measured_at_correctly`

**Akzeptanz:**
- Bandwechsel mit Cache < 1 h alt: Phase 3 ueberspringen, Toast erscheint
- Bandwechsel mit Cache > 1 h alt: Phase 3 laeuft normal
- `_was_early_stopped`-Schutz in `mw_cycle.py:223` BLEIBT — Cache-Reuse-Eintraege
  stammen aus voll-gemessener Pipeline (Cache-Schutz schreibt sie nicht)

### Commit 5: OPERATE_CYCLES + Settings-Option entfernen
**Files:**
- `core/diversity.py` Z.27 `OPERATE_CYCLES = 60` → ENTFERNEN
- `core/diversity.py` Z.487-489 `operate_cycles` property → ENTFERNEN
- `core/diversity.py` `_operate_cycles` Counter → ENTFERNEN
- `core/diversity.py` `on_operate_cycle()` → ENTFERNEN (oder leer lassen mit
  Deprecation-Kommentar fuer Aufrufer-Kompatibilitaet, Mike-Entscheidung)
- `ui/mw_radio.py:821-824` `_MULT` fuer OPERATE_CYCLES + `base = ...` weg,
  `MEASURE_CYCLES`-Skalierung BLEIBT (R1 Mod 1)
- `ui/main_window.py:230` und :232 `block_cycles = ...` aus `diversity_operate_cycles`
  → fester Default 80 oder via OMNI-TX-Konstante (separater Mike-Check noetig)
- `ui/main_window.py:822` `OPERATE_CYCLES = ...` → ENTFERNEN
- `ui/mw_cycle.py:206` und :606 `operate_total = self._diversity_ctrl.OPERATE_CYCLES`
  → durch UI-Anzeige „Restzeit bis Re-Measure" via `(3600 - age) / cycle_s` ersetzen
  (Anzeige bleibt erhalten, Zaehler-Logik weg)
- `ui/settings_dialog.py:444` und :575 Settings-UI fuer
  `diversity_operate_cycles` ENTFERNEN
- `config/settings.py` (wenn vorhanden) `diversity_operate_cycles` Default raus
- `core/omni_tx.py:61` Kommentar bezieht sich auf Default — separater Mike-Check
  ob OMNI-TX-Konstante eigenstaendig wird (vermutlich ja)
- `tests/test_modules.py:931` Modus-Faktor-Test: Test umschreiben auf
  MEASURE_CYCLES-Skalierung
- `tests/test_settings_dialog_smoke.py:34` `diversity_operate_cycles` aus
  Test-Settings entfernen

**OFFENE FRAGE FUER R1:**
Sollte `OPERATE_CYCLES`-Konstante in einem **separaten** Commit weg
(=Commit 6), damit Commit 4 atomar nur die Cache-Reuse-Logik enthaelt?
Oder zusammen mit Cache-Reuse als logische Einheit?

**Akzeptanz:**
- `OPERATE_CYCLES`-Konstante existiert nicht mehr
- Settings-Dialog hat keine `diversity_operate_cycles`-Option
- UI-Anzeige fuer „Restzeit bis Re-Measure" funktioniert (zeit-basiert)
- OMNI-TX bleibt funktional (block_cycles via fester Default)

### Commit 6: Tests-Migration + Doku-Sync
**Files:**
- `tests/test_diversity_bandwechsel.py` `test_load_preset_removed` umschreiben:
  „band-spezifischer Cache-Reuse erlaubt, kein globaler Cache" (V2 Finding 7)
- `HISTORY.md` v0.93-Eintrag
- `HANDOFF.md` (beide Pfade) v0.93-Update
- `CLAUDE.md` (beide Pfade) Aktueller Stand v0.93
- Memory `project_diversity_cache_reuse.md` als ERLEDIGT
- `main.py` `APP_VERSION = "0.93"`

---

## Migrations-Strategie (Detail)

### PresetStore JSON-Migration

**Alt (v0.92):**
```json
{
  "40m_FT8": {
    "rxant": "ANT1",
    "ant1_gain": 10, "ant2_gain": 20,
    "ant1_avg": -8.5, "ant2_avg": -10.2,
    "ratio": "70:30", "dominant": "A1",
    "timestamp": 1714567890,
    "measured": "2026-05-04 13:45"
  }
}
```

**Neu (v0.93):**
```json
{
  "40m_FT8": {
    "rxant": "ANT1",
    "ant1_gain": 10, "ant2_gain": 20,
    "ant1_avg": -8.5, "ant2_avg": -10.2,
    "ratio": "70:30", "dominant": "A1",
    "gain_timestamp": 1714567890,
    "ratio_timestamp": 1714567890,
    "measured": "2026-05-04 13:45"
  }
}
```

**Migration in `_load()`:**
```python
for key, entry in self._data.items():
    if "timestamp" in entry and "gain_timestamp" not in entry:
        # Alt-Format: timestamp → beide Felder
        ts = entry["timestamp"]
        entry["gain_timestamp"] = ts
        entry["ratio_timestamp"] = ts
```

`save_gain` schreibt nur `gain_timestamp`. `save_ratio` schreibt nur `ratio_timestamp`.
Beim Re-Save wird das alte `timestamp`-Feld nicht mehr beruehrt — bleibt drin oder
wird beim naechsten Voll-Save (z.B. neue Migration) gepurged.

### `_last_measured_at` in DiversityController

- Aktuell: Counter `_operate_cycles` zaehlt hoch
- Neu: `_last_measured_at` wird in `_evaluate()` und `start_measure()` gesetzt
- Bei App-Start: aus PresetStore.get_ratio_age_minutes() rekonstruieren?
  ODER: erst beim ersten `_evaluate` setzen (= Pipeline laeuft beim Start einmal durch)
- **Entscheidung KISS:** Erst beim ersten `_evaluate` setzen. App-Start-Cache-Reuse
  setzt es ueber den Cache-Check-Pfad.

---

## Test-Strategie (gesamt)

**Neue Tests (~15-20):**
- `test_preset_store.py` 5x (Migration + 2 Timestamps)
- `test_diversity_density.py` 3x (Score-basiert, FT2 dünn)
- `test_diversity_min_stations_removed.py` 1x (oder in test_diversity.py)
- `test_should_remeasure_cq.py` 4x (CQ-Lock + 1h-Frist)
- `test_diversity_cache_reuse.py` 4x (Bandwechsel + Toast + Edge-Cases)

**Anzupassende Tests:**
- `test_modules.py:931` (Modus-Faktor → MEASURE_CYCLES only)
- `test_settings_dialog_smoke.py:34` (Settings-Option weg)
- `test_diversity_bandwechsel.py` `test_load_preset_removed` (band-spezifisch erlaubt)
- evt. weitere `test_diversity*.py` mit `record_measurement(score=...)` API

**Erwartung:** 681 → ~700 Tests gruen.

---

## Reihenfolge der Commits — Begruendung Atomar

1. **Commit 1 (PresetStore):** Foundation — keine Verhaltensaenderung, nur API-
   Erweiterung. Tests grun. Sicheres Fundament fuer Rest.
2. **Commit 2 (Score + MIN_STATIONS):** Quick-Win. Verbessert FT2-Statistik
   sofort, unabhaengig vom Rest. Auch ohne Cache-Reuse nuetzlich.
3. **Commit 3 (CQ-Lock + 1h-Frist):** Logik-Aenderung in `should_remeasure`.
   `OPERATE_CYCLES`-Konstante BLEIBT noch fuer UI-Kompat — Commit 5 raeumt auf.
4. **Commit 4 (Cache-Reuse + Toast):** Hauptfeature. Baut auf Commit 1+3.
5. **Commit 5 (OPERATE_CYCLES weg):** Cleanup. Letzter Schritt damit zwischen-
   durch keine kaputten States entstehen.
6. **Commit 6 (Tests + Doku):** Doku-Sync.

**Frage R1:** Ist diese Reihenfolge sinnvoll? Sollte Commit 5 vor Commit 4
(Cleanup vor Feature)? Oder zusammen?

---

## Edge-Cases (V2 + R1)

1. **App-Start mit valid Cache:** Cache-Check beim ersten Diversity-Aktivieren
   im Init-Pfad → Phase 3 ueberspringen. (R1: ja, Suspend/Resume meist > 1h
   alt → frische Messung sowieso.)

2. **Cache 55 Min alt + Tag/Nacht-Wechsel 18 UTC:** Bedingungen koennen
   gekippt sein. R1: akzeptabel, max 5 Min suboptimal bei 1h-Frist.

3. **Bandpilot-Wechsel + Cache-Reuse:** 5-s-Toast erscheint, Mike sieht
   Antennen-Empfehlung sofort. R1: transparent genug, Mehrfach-Toasts bei
   schnellen Bandwechseln okay (informativ, nicht stoerend).

4. **Auto-Hunt mit Cache-Reuse:** Auto-Hunt 1 Min frueher aktiv. Positiv.

5. **Cache aus Adaptiv-Stop:** `_was_early_stopped`-Flag in `mw_cycle.py:220`
   schuetzt — diese Ratios landen nicht im Cache. Cache enthaelt nur voll-
   gemessene Werte.

6. **NaN/Inf in Score:** Der `score`-Parameter wird vom Aufrufer als
   `sum(snr+30)` berechnet. Wenn alle SNR > -30 → score >= 0. Bei leerem
   Slot → score = 0. Kein NaN-Risiko (R1-bestaetigt im Dichte-Review).

---

## Risiken (V2 + Mike-Bekannt)

1. **1h-Frist beim Tag/Nacht-Wechsel knapp** (R1: akzeptabel, 5 Min max).
2. **PresetStore-Migration** muss alte Caches lesbar halten (Ja, siehe oben).
3. **Score-Schwelle 5.0** ist Schaetzung — Field-Test-Tuning moeglich.
   Conservative-Fallback: bei `peak <= 5.0` immer 50:50. Bei `peak > 5.0`
   THRESHOLD-Vergleich (8 % rel-diff).
4. **OMNI-TX block_cycles** Default 80 → fester Wert ohne Settings.
   Mike-Check ob OMNI-TX-eigene Konstante sinnvoll (bisher gekoppelt an
   `diversity_operate_cycles`).

---

## Was BLEIBT unveraendert

- Phase 2 Gain-Messung (separate 6 h Validity)
- Phase 3 fair 3:3 Pattern (v0.90)
- v0.91 Adaptiv-Stops (Phase 2 + Phase 3)
- v0.91 Cache-Schutz (`_was_early_stopped`)
- v0.92 Pipeline-Lock (Bandwechsel-Race-Fix)
- Manueller „NEU"-Button fuer Re-Measure
- Auto-Hunt, OMNI-TX, Bandpilot bestehende Logik

---

## R1-Auftrag (final)

1. Plan-Vollstaendigkeit: Code-Stellen alle erfasst?
2. Atomar-Reihenfolge: Commits sinnvoll, sicher, ohne Zwischen-Brueche?
3. Migration robust: alte JSON-Caches lesbar, neue korrekt geschrieben?
4. Test-Strategie: ausreichend, oder fehlt was?
5. Edge-Cases: was haben V1/V2/R1/Dichte-R1 uebersehen?
6. KISS-Check: kann was weggelassen werden?
7. **Eine Empfehlung:** Plan ready fuer Plan-Mode + Code? Oder noch ein V4-Iteration?

**KEINE neuen Features einfuehren.** **KEINE Architektur-Aenderungen vorschlagen.**
Nur Plan kritisch reviewen.
