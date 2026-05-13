# P34-Stufe2 — V1 (Initial-Entwurf)

**Aufgabe:** Statik-Ratio-Pipeline komplett entfernen. Dynamic
(`DynamicDiversityController`) wird der einzige Pfad.

**Status:** V1 — wird Self-Reviewed zu V2.
**Datum:** 2026-05-13 nachmittags.

---

## 1. Ziel

P34-Stufe1 (v0.97.0) hat Dynamic-Pipeline parallel zur Statik gebaut, mit
Settings-Toggle als ENTWEDER-ODER-Schalter. Field-Test 11.-13.05.2026
zeigte: Dynamic funktioniert, Mike will keinen Toggle mehr.

**Stufe 2:** Statik-Pipeline (Phase 3 Ratio-Messung, 90 s UI-Sperre,
6-Slot-Mess, 1 h-Re-Mess-Frist, MessStatusDialog, Settings-Toggle) komplett
raus. Dynamic ist Default und einziger Pfad. Phase 2 (Gain-Kalibrierung
via DXTuneDialog) bleibt komplett unangetastet.

**Bonus:** Macht den 80m-Abbruch-Bug obsolet (kein Phase 3 → keine
"0/6-Mess-Hänger"-Symptome mehr).

---

## 2. Akzeptanzkriterien (verbindlich)

1. **AK1 — Keine Statik-Ratio-Mess-Phase mehr:**
   - `_phase == "measure"` Branch existiert nicht mehr
   - `DiversityController._measurements` / `_measure_step` /
     `_operate_cycles` / `MEASURE_CYCLES` / `EARLY_STOP_FRACTION` /
     `EARLY_STOP_THRESHOLD` raus
   - `record_measurement()`, `_check_phase3_early_stop()`, `_evaluate()`,
     `start_measure()`, `on_band_change()`, `can_measure()`,
     `on_operate_cycle()` Methoden raus
   - `_handle_diversity_measure()` in `mw_cycle.py` raus

2. **AK2 — Keine 1 h-Re-Mess-Frist mehr:**
   - `_last_measured_at`, `REMEASURE_INTERVAL_SECONDS`,
     `should_remeasure()`, `seconds_until_remeasure` raus
   - `_dynamic_active` Property + Setter raus (gibt's keinen Statik-Pfad
     mehr, der unterdrückt werden muss)

3. **AK3 — Settings-Toggle weg:**
   - `Settings.dynamic_diversity_enabled` Property + Setter raus
   - `settings_dialog.py`: QCheckBox + Tooltip + Apply-Logic raus
   - `_apply_dynamic_toggle()` in `main_window.py` raus
   - Auto-Reactivate-Block in `mw_radio.py:683-688` raus

4. **AK4 — Dynamic ist immer aktiv (bei Diversity-Mode):**
   - `DynamicDiversityController.activate()` wird IMPLIZIT aus
     `_enable_diversity()` aufgerufen (kein User-Toggle mehr)
   - `deactivate()` wird IMPLIZIT aus `_disable_diversity()` aufgerufen
   - `is_active()` bleibt als API — wenn Diversity aus, Dynamic aus

5. **AK5 — MessStatusDialog raus:**
   - `ui/mess_status_dialog.py` Datei löschen
   - `_open_mess_status_dialog()`, `_close_mess_status_dialog()`,
     `_on_mess_status_cancelled()` raus
   - Aufruf-Stellen in `mw_radio.py`, `mw_cycle.py`, `main_window.closeEvent`
     raus
   - `_mess_status_dialog`-Attribut raus

6. **AK6 — `_enable_diversity` vereinfacht:**
   - Drei aktuelle Pfade (dynamic_active / cached_ratio / Phase=measure)
     reduziert auf einen Pfad: Phase=operate sofort, 50:50, Dynamic startet
   - `cached_ratio`/`cached_dominant`/`cached_age_seconds`-Parameter raus
     (wird nicht mehr aufgerufen)
   - Statik-spezifische Init-Logik raus (Lock setzen, Modal öffnen,
     MEASURE_CYCLES setzen, scoring_mode_listeners)
   - Deferred-Init bei `radio.ip=None` bleibt (P35 Bug A — Pending-Resume
     über `_check_diversity_preset` Pfad)

7. **AK7 — `_check_diversity_preset` vereinfacht:**
   - `_assess_ratio()` raus, nur noch `_assess_gain()`
   - Zwei Branches statt fünf:
     - `gain fresh` → Cache-Reuse (Gain-Werte laden + `_enable_diversity`)
     - `gain stale/missing` → DXTuneDialog (Gain-Mess) + nach OK
       `_enable_diversity`
   - `_pending_ratio_status` raus, `_pending_dx_diversity` bleibt
     (Gain-Pipeline)
   - `_try_diversity_cache_reuse` umbenannt zu `_load_gain_cache` (nur
     Gain laden, kein Ratio mehr)

8. **AK8 — PresetStore Ratio-Felder werden nicht mehr geschrieben:**
   - `commit_with_ratio()` Aufruf in `mw_cycle._handle_diversity_measure`
     fällt mit der Methode weg
   - `settings.save_diversity_preset()` Aufruf fällt mit weg
   - PresetStore-Datei behält Ratio-Felder im Format (Backward-Compat fuer
     alte JSON-Dateien) — aber Lese-Pfad ignoriert sie
   - `is_valid_ratio()` Methode + `get_ratio_age_minutes()` können bleiben
     (kein Aufrufer mehr) oder raus — Vorschlag: raus (Dead-Code-Vermeidung)

9. **AK9 — `choose()` in DiversityController:**
   - `_phase == "measure"`-Branch raus
   - Nur noch Operate-Pattern (70:30, 30:70, 50:50)
   - Pattern-Konstanten `_PAT_70_A1` / `_PAT_70_A2` bleiben

10. **AK10 — CQ-Frequenz-Such bleibt unangetastet:**
    - `tick_slot()`, `update_proposed_freq()`, `get_free_cq_freq()`,
      `_score_gap()`, `_measure_gap_around()`, `reset_search_counter()`,
      `set_mode()`, `_SEARCH_INTERVAL_SLOTS`, `_freq_histogram`,
      `_cq_freq_hz`, `_current_gap_width_hz`, `_search_slots_remaining`,
      `_recalc_count` — alle bleiben
    - `_diversity_in_operate`-Flag in `mw_cycle.py` bleibt (Transition-
      Guard für once-only Code, läuft nach erstem operate-Eintritt)

11. **AK11 — Hardware-Schutz:**
    - `radio.set_tx_antenna("ANT1")` unangetastet
    - Diversity-Pattern (70:30 / 50:50 / 30:70) nutzt nur RX-Antennen

12. **AK12 — Tests:**
    - `test_should_remeasure.py` → komplett löschen (1 h-Frist gibt's nicht
      mehr)
    - `test_p35_startup_bugs.py` → komplett löschen (testet Toggle +
      Mess-Phase, beides weg)
    - `test_diversity_cache_reuse.py` → Ratio-Cache-Tests löschen, Gain-
      Cache-Tests behalten oder umbauen
    - `test_diversity_bandwechsel.py` → Mess-Phase-Tests löschen,
      Histogramm-Reset-Tests behalten
    - `test_p1_cache_simple.py` → fünf Branches → zwei Branches anpassen
    - `test_p22_preset_atomic.py` → `commit_with_ratio`-Tests löschen,
      `stage_gain` + `discard_staged` + `is_valid_gain` behalten
    - `test_dx_tune_adaptive_stop.py` → bleibt unangetastet (Gain-Phase)
    - `test_diversity_dynamic.py` + `test_diversity_dynamic_integration.py`
      → Toggle-Tests entfernen, Activate-via-`_enable_diversity`-Tests
      neu
    - **Neue Tests P34-Stufe2:**
      - `test_p34_stufe2_no_measure_phase.py` — verifiziert dass kein
        `_phase=="measure"` mehr auftritt, kein `record_measurement` mehr
      - `test_p34_stufe2_dynamic_default.py` — verifiziert dass Dynamic
        bei `_enable_diversity` automatisch aktiviert wird
      - `test_p34_stufe2_check_preset_two_branches.py` — verifiziert
        Gain-only Logic

13. **AK13 — APP_VERSION-Bump:**
    - 0.97.18 → 0.98.0 (Major-Bump weil Statik-Pipeline-Entfernung ist
      eine grundlegende Architektur-Vereinfachung)

14. **AK14 — Doku:**
    - HISTORY.md, HANDOFF.md, CLAUDE.md, TODO.md updaten
    - CLAUDE.md "Architektur & Module" → DiversityController-Beschreibung
      vereinfachen
    - `docs/explained/` falls Statik-Diagramme drin → updaten

---

## 3. Betroffene Module + Dateien (Datei:Zeile)

### Files mit signifikanten Änderungen

| Datei | Was geändert | Geschätzter Aufwand |
|---|---|---|
| `core/diversity.py` | ~250 LOC raus (Mess-Phase, _phase, _measurements, should_remeasure, _evaluate, etc.) | groß |
| `core/dynamic_diversity.py` | Minimal: ggf. scoring_mode_listeners-Coupling vereinfachen | klein |
| `core/preset_store.py` | Ratio-spezifische Methoden raus oder als deprecated markiert | mittel |
| `config/settings.py` | dynamic_diversity_enabled-Property raus + save_diversity_preset-Aufrufer | klein |
| `ui/mw_radio.py` | _enable_diversity vereinfacht, _check_diversity_preset vereinfacht, _try_diversity_cache_reuse umgebaut, Mess-Modal-Trio raus, _apply_dynamic_toggle entkoppelt | groß |
| `ui/mw_cycle.py` | _handle_diversity_measure raus, _on_cycle_decoded vereinfacht (kein was_phase=="measure" mehr) | mittel |
| `ui/main_window.py` | _apply_dynamic_toggle raus, closeEvent-MessDialog-Aufruf raus | klein |
| `ui/control_panel.py` | update_diversity_ratio: measure_step + measure_total + is_dynamic-Parameter raus (alles immer dynamic+operate) | klein |
| `ui/settings_dialog.py` | QCheckBox Toggle + Tooltip + Apply-Logic raus | klein |

### Files die gelöscht werden

- `ui/mess_status_dialog.py` (komplettes File)

### Files unangetastet

- `core/diversity_merger.py`, `core/diversity_cache.py` (anderer Use-Case)
- `ui/dx_tune_dialog.py` (Gain-Phase, bleibt)
- `core/dynamic_diversity.py` (Kern-Pipeline, bleibt — nur Coupling-Hooks
  ggf. vereinfacht)

---

## 4. Randbedingungen

### Hardware-Schutz (PFLICHT)

- ANT1 = TX immer. ANT2 = nur RX. `radio.set_tx_antenna("ANT1")` vor jedem
  TX-Trigger. NICHT angefasst durch P34-Stufe2.

### Threading

- `_diversity_lock` in MainWindow bleibt — Queue + current_ant unter Lock.
- `DynamicDiversityController._lock` (threading.Lock) bleibt.
- `_dynamic_ctrl.is_active()`-Check in mw_cycle._on_cycle_decoded bleibt
  (Defensive — bei Diversity-AUS sollte record_slot No-Op sein).

### Persistence

- Gain-Werte (presets_standard.json, presets_dx.json) bleiben.
- Ratio-Werte werden NICHT mehr geschrieben (Dynamic ist Live-Mess).
- Alte JSON-Dateien mit Ratio-Feldern werden silent ignoriert (kein
  Migrations-Lauf nötig).

### Backward-Compat

- `Settings.save_diversity_preset()` Methode kann bleiben aber wird nicht
  mehr aufgerufen → bessere Lösung: Aufrufer entfernen, Methode kann
  bleiben (Dead-Code in API ist OK fuer eine Version, später ausräumen).
- Alte `settings.json` mit `dynamic_diversity_enabled`-Schlüssel:
  `Settings.load()` ignoriert unbekannte Schlüssel ohnehin. Property
  weg → kein Aufrufer → silent OK.

### UI

- Antennen-Panel zeigt jetzt IMMER: aktuelles Ratio + RX-Antennen-Suffix
  (P37/P40) + "(live)"-Indikator. KEINE "Messung X/6"-Anzeige mehr.
- "Diversity Neuberechnung in X Min." entfällt komplett.
- Cache-Reuse-Toast war eh schon entfernt (v0.95.13).

### Tests

- Tests müssen vor jedem Commit grün sein.
- `QT_QPA_PLATFORM=offscreen ./venv/bin/python3 -m pytest tests/ -q`
- Erwartung: 1239 → ~1190 grün (–~80 Statik-spezifische Tests gelöscht,
  +~30 P34-Stufe2-Tests neu, Netto-Reduktion).

---

## 5. Nicht im Scope

- **Gain-Kalibrierung (DXTuneDialog, Phase 2)** — bleibt komplett, ist eine
  separate Pipeline für Audio-Pegel-Optimierung. Hat nichts mit Ratio-Mess
  zu tun.
- **CQ-Frequenz-Such (Histogramm, Sticky-Gap, Suche pro Slot)** — bleibt
  unangetastet. Lebt unabhängig in `DiversityController` (Modul-Funktion-
  Ebene).
- **Diversity-Operate-Betrieb** (Antennen-Pattern, Stations-Akkumulation,
  Stats-Logging) — bleibt.
- **PSKReporter-Integration** — bleibt (orthogonal).
- **Bandpilot** — bleibt (3-Wege-Empfehlung Normal/Std/DX).
- **Bänder-Deaktivierung Feature** — separates Folgeprojekt nach P34-Stufe2.

---

## 6. Test-Strategie (Erstentwurf)

### Bestehende Tests die gelöscht werden

1. `test_should_remeasure.py` — 1h-Frist, raus
2. `test_p35_startup_bugs.py` — Toggle-Tests, raus
3. `test_diversity_density.py` — falls Mess-Phase-spezifisch (zu prüfen
   in V2-Schritt)

### Bestehende Tests die umgebaut werden

1. `test_diversity_cache_reuse.py` — Ratio-Branch raus, Gain-Branch bleibt
2. `test_diversity_bandwechsel.py` — `on_band_change`-Tests raus, Reset-
   bei-Bandwechsel-Tests umbauen auf Histogramm-Reset
3. `test_p1_cache_simple.py` — Mess-Branches raus
4. `test_p22_preset_atomic.py` — `commit_with_ratio`-Tests raus,
   `stage_gain`-Tests bleiben
5. `test_diversity_dynamic.py` + `test_diversity_dynamic_integration.py`
   — `dynamic_diversity_enabled`-Tests raus, Activate-via-`_enable_diversity`
   neu

### Neue Tests P34-Stufe2

| Test | Was prüft |
|---|---|
| T1 `test_no_measure_phase_constants` | DiversityController hat kein `MEASURE_CYCLES`, kein `_measurements`-Dict |
| T2 `test_diversity_controller_no_should_remeasure` | `should_remeasure` Methode existiert nicht (oder gibt immer False zurück, falls bewusst behalten als API-Stub) |
| T3 `test_enable_diversity_activates_dynamic` | Nach `_enable_diversity()` ist `_dynamic_ctrl.is_active()` True |
| T4 `test_disable_diversity_deactivates_dynamic` | Nach `_disable_diversity()` ist `_dynamic_ctrl.is_active()` False |
| T5 `test_check_preset_gain_fresh_skips_mess` | Gain frisch → kein DXTuneDialog, `_enable_diversity` direkt |
| T6 `test_check_preset_gain_stale_opens_dx_dialog` | Gain stale → DXTuneDialog öffnet |
| T7 `test_no_mess_status_dialog_class` | `ui.mess_status_dialog` nicht mehr importierbar (Modul gelöscht) |
| T8 `test_settings_no_dynamic_diversity_enabled` | `Settings.dynamic_diversity_enabled` Property existiert nicht |
| T9 `test_handle_diversity_measure_method_gone` | `MainWindow._handle_diversity_measure` Attribut existiert nicht |
| T10 `test_phase_always_operate` | Nach `_enable_diversity`, `_diversity_ctrl.phase` ist "operate" (defensive falls phase als API erhalten bleibt) |

---

## 7. Implementierungs-Reihenfolge (Atomare Commits)

| # | Commit | Datei(en) | Beschreibung |
|---|---|---|---|
| C1 | Tests: Statik-Tests löschen | `tests/test_should_remeasure.py`, `tests/test_p35_startup_bugs.py`, ggf. test_diversity_density.py | Löschungen — sonst nach Code-Refactor kaputte Tests im Repo |
| C2 | `core/diversity.py` Mess-Phase raus | core/diversity.py | record_measurement, _evaluate, _check_phase3_early_stop, start_measure, on_band_change, can_measure, on_operate_cycle, should_remeasure, _phase, _measure_step, _measurements, _operate_cycles, _last_measured_at, _was_early_stopped, _dynamic_active, _scoring_mode_listeners, MEASURE_CYCLES, EARLY_STOP_*, REMEASURE_INTERVAL_SECONDS, properties (phase, measure_step, operate_cycles, seconds_until_remeasure, dynamic_active), choose() Mess-Branch — alles raus |
| C3 | `core/dynamic_diversity.py` Coupling vereinfachen | core/dynamic_diversity.py | scoring_mode_listeners-Coupling auf direkten Setter-Hook in DiversityController.scoring_mode-Setter? oder bleibt. Re-evaluieren in V2. |
| C4 | `core/preset_store.py` Ratio-API raus | core/preset_store.py | is_valid_ratio, get_ratio_age_minutes, commit_with_ratio, save_ratio, ratio/dominant-Felder in Format-Validierung |
| C5 | `config/settings.py` dynamic_diversity_enabled raus | config/settings.py | Property + Setter + save_diversity_preset (falls nirgendwo mehr genutzt) |
| C6 | `ui/mess_status_dialog.py` löschen | (Datei-Löschung) | Komplettes File raus |
| C7 | `ui/mw_radio.py` Mess-Pipeline raus | ui/mw_radio.py | _open/close/cancelled_mess_status_dialog, _try_diversity_cache_reuse, _assess_ratio, _pending_ratio_status, _apply_dynamic_toggle-Auto-Reactivate, _enable_diversity cached_ratio + Phase=measure-Pfade, _check_diversity_preset gain-only |
| C8 | `ui/mw_cycle.py` _handle_diversity_measure raus | ui/mw_cycle.py | Z.93-94 (Aufruf) + Z.236-372 (Methode) + Z.288-289 `_is_dyn`-Check redundant (immer True bei Diversity) |
| C9 | `ui/main_window.py` Toggle-Handler raus | ui/main_window.py | _apply_dynamic_toggle Methode + closeEvent Mess-Dialog-Block |
| C10 | `ui/control_panel.py` measure-Params raus | ui/control_panel.py | update_diversity_ratio: measure_step/measure_total/is_dynamic Parameter aus Signatur raus |
| C11 | `ui/settings_dialog.py` Toggle-UI raus | ui/settings_dialog.py | QCheckBox + Apply-Block |
| C12 | Bestehende Tests anpassen | diverse tests/ | s.o. test-strategy |
| C13 | Neue P34-Stufe2 Tests | tests/test_p34_stufe2_*.py | T1-T10 oben |
| C14 | APP_VERSION + Doku | main.py, HISTORY.md, HANDOFF.md, CLAUDE.md, TODO.md | 0.97.18 → 0.98.0, alle 4 Pflicht-Dateien |

**Geschätzter Zeitaufwand:** 4-5 h.

---

## 8. Edge-Cases

### EC1: User startet Normal, wechselt auf Diversity DX

- Heute: _check_diversity_preset gain-Check → ggf. DXTuneDialog → nach OK
  Phase 3 (gain stale) oder Cache-Reuse (gain fresh).
- Stufe 2: _check_diversity_preset gain-Check → ggf. DXTuneDialog → nach
  OK `_enable_diversity()` → Phase=operate, 50:50, Dynamic startet, in
  ~3 Min Verhältnis-Wechsel.

### EC2: User auf 80m, SWR zu hoch, Gain-Mess bricht ab

- Heute: Cancel → `_disable_diversity()` → zurück zu Normal-Modus.
- Stufe 2: Gleiches Verhalten. Cancel = Diversity-Aus = Dynamic-Aus.

### EC3: Bandwechsel mit aktiver Diversity

- Heute: `on_band_change` → reset → Phase=measure → 6 Slots Mess →
  ratio.
- Stufe 2: Bandwechsel triggert `_check_diversity_preset` → ggf.
  DXTuneDialog (Gain-stale) oder Cache-Reuse-Pfad → `_enable_diversity()`
  → Phase=operate sofort, 50:50, Dynamic startet bei null (Buffer leer,
  `_dynamic_ctrl.reset()` im `_enable_diversity`).

### EC4: 1h ohne QSO

- Heute: should_remeasure True → 90s Mess-Phase erneut.
- Stufe 2: Nichts passiert. Dynamic läuft live weiter. KEINE Re-Mess.

### EC5: App-Quit während laufender Gain-Mess

- Heute: closeEvent schliesst mess_status_dialog (falls offen) +
  discard_all_staged.
- Stufe 2: closeEvent muss DXTuneDialog schliessen (nicht
  mess_status_dialog mehr). DXTuneDialog hat eigenes Cancel-Flow.
  Wahrscheinlich bereits implementiert — V2 prüft.

---

## 9. Risiken (V1-Spec, in V2 zu schärfen)

1. **R1 — `_handle_diversity_measure` dependencies:** Funktion wird nur an
   einer Stelle aufgerufen (mw_cycle Z.94). Aber: setzt `_set_cq_locked`,
   `_set_gain_measure_lock`, ruft `commit_with_ratio`, `settings.save_diversity_preset`,
   `_close_mess_status_dialog`, `omni.reset_counter_after_measure`. Alle
   Folgewirkungen müssen anderswo abgefangen werden (oder als nicht mehr
   nötig deklariert).
2. **R2 — `_dynamic_ctrl.is_active()`-Check in mw_cycle Z.111-112:** Wird
   redundant da Dynamic bei Diversity immer aktiv. Aber: Defensive lassen
   für den Fall dass Diversity-Aus zwischen Slot und Decoder-Hook gerade
   geschaltet wurde (Race-Schutz). Bewusst behalten.
3. **R3 — `phase`-Property bleibt:** `seconds_until_remeasure` raus, aber
   `phase` Property selbst wird noch von `mw_cycle` an control_panel
   durchgereicht. V2 entscheidet ob `phase` als API-Stub bleibt (immer
   "operate") oder ganz raus + Aufrufer angepasst.
4. **R4 — `set_band()` in DiversityController:** Wird heute aufgerufen
   und löst `on_band_change` aus, das ein `reset()` macht. `reset()`
   setzt `_phase = "measure"` + initialisiert Mess-State. Stufe 2:
   `set_band` macht nur noch CQ-Such-Counter-Reset, `on_band_change` raus.
   `reset` muss vereinfacht werden (nur Histogramm + Search-Counter
   reset, kein Phase + Measurements mehr).
5. **R5 — DynamicDiversityController.reset() bei Bandwechsel:** Heute
   wird `_dynamic_ctrl.reset()` in `_enable_diversity` (dynamic_active-
   Pfad) aufgerufen. Mit Stufe 2: ist das automatisch der Standardpfad.
   `set_band`/`set_mode` müssen ebenfalls `_dynamic_ctrl.reset()`
   triggern damit Buffer bei Bandwechsel leer ist. Heute ist das via
   `_check_diversity_preset` → `_enable_diversity` indirekt der Fall;
   muss in V2 sauber dokumentiert werden.

---

## 10. Compact-Recovery-Hinweis

Falls die Session Compact-getrennt wird zwischen V1 und Code:
- Diese V1-Datei ist Start für V2-Self-Review.
- V2 wird `prompts/p34_stufe2_v2.md`.
- V3 (final) wird `prompts/p34_stufe2_v3.md`.
- R1-Output: `prompts/p34_stufe2_r1.md`.
- Final-R1: `prompts/p34_stufe2_final_r1.md`.
- Backup-Pfad: `Appsicherungen/2026-05-13_v0.97.18_vor_p34_stufe2/`.
- Aktuelle Test-Bilanz: 1239 grün.

---

**V1 fertig. Nächster Schritt: V2 Self-Review.**
