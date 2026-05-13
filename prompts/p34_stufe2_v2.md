# P34-Stufe2 — V2 (Self-Review)

**Du bist Senior Python-Entwickler spezialisiert auf Amateurfunk-Software
und PySide6 (Signal statt pyqtSignal, Slot statt pyqtSlot). Das Projekt
ist ein Hobby-Funker-Tool für einen einzelnen Operator — NICHT Multi-Tenant.**

**Deine einzige Aufgabe:** diesen Prompt kritisieren — NICHT das Problem
lösen. Strukturierte Liste: Lücken, Unklarheiten, Widersprüche, Verbesserungen.

**KRITISCHE REGELN:**
1. SCOPE-RESPEKT: Explizit als out-of-scope markiertes NICHT als Finding melden.
2. KISS VOR DEFENSIV: Komplexität nur wenn Wahrscheinlichkeit > 50%.
3. PROJEKT-BEZUG: Jedes Finding am konkreten Use-Case messen.
4. FORMAT: Tabelle Schwere | Finding | Datei:Zeile | Empfehlung.
   Severity: Bug (rot) / Risiko (orange) / Verbesserung (gelb) / Hinweis (grau).

Overengineering ist selbst ein Fehler den du benennen sollst.

---

## 0. Compact-Recovery (verbindlich)

Falls diese Session via Compact unterbrochen wird:
- Diese V2-Datei ist Grundlage für R1-Review (`prompts/p34_stufe2_v2.md`).
- V1 ist `prompts/p34_stufe2_v1.md` (historisch, V2 ersetzt sie).
- R1-Output landet in `prompts/p34_stufe2_r1.md`.
- V3 (final) landet in `prompts/p34_stufe2_v3.md`.
- Final-R1 nach Code: `prompts/p34_stufe2_final_r1.md`.
- Backup-Pfad: `Appsicherungen/2026-05-13_v0.97.18_vor_p34_stufe2/`.
- Aktuelle Test-Bilanz: **1239 grün** (v0.97.18).
- APP_VERSION-Bump: **0.97.18 → 0.97.19** (Patch-Bump für reines Refactor
  ohne Feature-Add; v0.98.0 wäre für ein Bandpilot-Major-Update reserviert).

---

## 1. Ziel

P34-Stufe1 (v0.97.0) hat Dynamic-Pipeline (`DynamicDiversityController`)
parallel zur Statik gebaut, gesteuert durch Settings-Toggle "Antennen-
Verhaeltnis dynamisch anpassen (Testphase)". Field-Test 11.-13.05.2026:
Dynamic funktioniert verlaesslich, Mike sagt "dynamisch laeuft ja top",
will Toggle weg.

**P34-Stufe2:** Statik-Ratio-Pipeline (Phase 3 Mess, 90 s UI-Sperre,
6-Slot-Mess-Pattern, 1 h-Re-Mess-Frist, MessStatusDialog, Settings-
Toggle, Cache-Reuse für Ratio) komplett raus. Dynamic ist Default und
einziger Pfad.

**Bonus:** 80m-Abbruch-Bug (Mike-Beobachtung 13.05.) wird obsolet — keine
Phase 3 mehr, keine "0/6-Mess-Haenger"-Symptome.

**Out-of-Scope:** Gain-Kalibrierung (DXTuneDialog Phase 2),
CQ-Frequenz-Such, Bandpilot, Bänder-Deaktivierung (separate Folgeprojekte).

---

## 2. Akzeptanzkriterien (verbindlich, 18 ACs)

### Kern-Refactor

1. **AK1 — Statik-Mess-Phase komplett raus:**
   - `_phase == "measure"`-Branch existiert nicht mehr im Code
   - `record_measurement()`, `_check_phase3_early_stop()`, `_evaluate()`,
     `start_measure()`, `on_band_change()`, `can_measure()`,
     `on_operate_cycle()` Methoden raus
   - Konstanten raus: `MEASURE_CYCLES`, `EARLY_STOP_FRACTION`,
     `EARLY_STOP_THRESHOLD`, `REMEASURE_INTERVAL_SECONDS`
   - Felder raus: `_measure_step`, `_measurements`, `_operate_cycles`,
     `_last_measured_at`, `_was_early_stopped`
   - Properties raus: `phase`, `measure_step`, `operate_cycles`,
     `seconds_until_remeasure`, `_early_stop_at`
   - `_handle_diversity_measure()` in `mw_cycle.py` raus

2. **AK2 — 1 h-Re-Mess weg:**
   - `should_remeasure()` Methode raus
   - `_dynamic_active` Property + Setter raus (keine Statik-Pipeline mehr
     die unterdrueckt werden muss)

3. **AK3 — Settings-Toggle weg:**
   - `Settings.dynamic_diversity_enabled` Property + Setter raus
   - `settings_dialog.py`: QCheckBox + Tooltip + Apply-Logic raus
   - `_apply_dynamic_toggle()` in `main_window.py` raus
   - Auto-Reactivate-Block in `mw_radio.py:683-688` raus
   - **Anti-Pattern-Check:** Grep nach `dynamic_diversity_enabled` über alle
     Files und alle Aufrufer sauber entfernen (Memory-Lesson
     `feedback_partial_fix_check_other_paths.md`)

4. **AK4 — Dynamic ist Default bei Diversity-Mode:**
   - `_enable_diversity()` ruft IMPLIZIT `_dynamic_ctrl.activate()` auf
   - `_disable_diversity()` ruft IMPLIZIT `_dynamic_ctrl.deactivate()` auf
   - `is_active()`-API bleibt fuer Defensive-Checks (record_slot-No-Op
     bei Diversity-AUS)

5. **AK5 — `_scoring_mode_listeners`-Liste raus:**
   - DiversityController hat keine Listener-Liste mehr
   - `DynamicDiversityController.__init__` registriert KEINEN Listener mehr
   - Stattdessen: `mw_radio._activate_diversity_with_scoring` ruft nach
     `_diversity_ctrl.scoring_mode = scoring` explizit
     `_dynamic_ctrl.reset()` auf (KISS, explicit ist besser als magisch)

6. **AK6 — MessStatusDialog komplett weg:**
   - `ui/mess_status_dialog.py` Datei löschen
   - `_open_mess_status_dialog()`, `_close_mess_status_dialog()`,
     `_on_mess_status_cancelled()` in `mw_radio.py` raus
   - `_mess_status_dialog`-Attribut in `MainWindow` raus
   - Aufruf in `MainWindow.closeEvent` raus
   - Aufruf in `mw_cycle._handle_diversity_measure` faellt mit der Methode
     weg

### Pipeline-Vereinfachung

7. **AK7 — `_enable_diversity` vereinfacht (3 Pfade → 1 Pfad):**
   - `cached_ratio`, `cached_dominant`, `cached_age_seconds`-Parameter aus
     Signatur raus (kein Cache-Reuse-Aufrufer mehr)
   - `dynamic_active`-Pfad und `Phase=measure`-Pfad zusammengelegt
   - Einziger Pfad: Phase=operate sofort, Ratio=50:50 (oder bei
     pending_resume aus Cache-Ratio falls noch gesetzt — siehe AK7a),
     `_dynamic_ctrl.activate()`, Lock aufheben
   - Deferred-Init bei `radio.ip=None` (P35 Bug A) bleibt
   - `MEASURE_CYCLES`-Setter (Z.982) + `_MULT`-Dict raus

   **AK7a — Cache-Ratio bei `_enable_diversity` (Mike-Use-Case):**
   - Heute: Cache-Reuse-Pfad laed `cached_ratio` aus Preset
   - Stufe2: Cache wird NICHT mehr fuer Ratio gelesen (Ratio ist live).
     ABER: bei pending_resume direkt nach Radio-Connect koennte das alte
     Ratio aus Preset noch sinnvoll sein als Start-Ratio. R1 entscheidet
     ob das overengineering ist.
   - **V2-Default:** kein Cache-Ratio-Init. Start IMMER 50:50, Dynamic
     übernimmt nach 5+5 Slots. KISS.

8. **AK8 — `_check_diversity_preset` vereinfacht (5 Branches → 2 Branches):**
   - `_assess_ratio()` Methode raus (keine Ratio-Cache-Bewertung mehr)
   - `_pending_ratio_status`-Attribut raus
   - `_try_diversity_cache_reuse` Methode raus (kein Cache-Ratio-Reuse
     mehr); falls Gain-Cache-Reuse separat noetig → neuer Helper
     `_apply_diversity_with_cached_gain` (KISS-Variante)
   - Branches:
     - **Gain fresh:** sofort `_enable_diversity(scoring)` (Dynamic
       startet live)
     - **Gain stale/missing:** DXTuneDialog → nach OK
       `_enable_diversity(scoring)`

9. **AK9 — PresetStore Ratio-API raus:**
   - `is_valid_ratio()`, `get_ratio_age_minutes()` Methoden raus
   - `commit_with_ratio()`, `save_ratio()` Methoden raus
   - Ratio-Format-Validierung in `_validate_entry`/`is_valid_gain` nur
     noch Gain-Felder
   - Alte JSON-Dateien mit `ratio`/`dominant`/`ratio_timestamp`-Feldern
     werden silent ignoriert (kein Migrations-Lauf)

10. **AK10 — `Settings.save_diversity_preset` raus:**
    - Methode + Aufruf in `mw_cycle._handle_diversity_measure` faellt
      mit der Methode weg
    - Settings-JSON-Key `diversity_preset` in alten Configs wird silent
      ignoriert

11. **AK11 — `choose()` in DiversityController nur noch Operate:**
    - `_phase == "measure"`-Branch raus
    - Operate-Pattern (70:30, 30:70, 50:50) bleibt mit `_PAT_70_A1`,
      `_PAT_70_A2`, Standard-50:50-Pattern
    - `_operate_cycles`-Counter raus → Pattern wird via Slot-Index (modulo
      Pattern-Laenge) gewaehlt. Slot-Index kommt vom Caller (mw_cycle
      hat slot_index/cycle_id). **R1-Klarstellung erforderlich:** wie wird
      Slot-Index gezaehlt wenn _operate_cycles weg ist?

### `_handle_diversity_measure`-Folgewirkungen (kritisch!)

12. **AK12 — Folgewirkungen aus `_handle_diversity_measure`-Entfernung:**
    Heute macht die Methode beim Phase-Uebergang measure→operate folgende
    Setup-Operationen die bei Stufe2 woanders passieren muessen:
    - `_diversity_in_operate = True` → muss bei erstem operate-Eintritt
      gesetzt werden (passiert: `_handle_diversity_operate` checkt das?
      → V2: ja, in mw_cycle.py:435ff). Aber: heute wird Flag NICHT in
      `_handle_diversity_operate` gesetzt. Daher: in
      `_enable_diversity` direkt `_diversity_in_operate = True` setzen,
      weil Phase ab sofort operate ist.
    - `_stats_warmup_cycles = 6` → in `_enable_diversity` setzen
    - `_set_cq_locked(False)` → in `_enable_diversity` schon enthalten
    - `commit_with_ratio` + `save_diversity_preset` → entfaellt (AK9, AK10)
    - `get_free_cq_freq + audio_freq_hz` → wird im naechsten operate-Slot
      vom `_refresh_diversity_freq_view`-Pfad sowieso initialisiert (mw_cycle
      laeuft pro Slot). KEIN Setup noetig.
    - `update_freq_histogram` → naechster Slot macht's eh
    - `_close_mess_status_dialog` → Modal existiert nicht mehr
    - `omni.reset_counter_after_measure` → nur sinnvoll wenn Mess-Phase
      vorbei war. Bei Stufe2: keine Mess-Phase mehr → kein Counter-
      Reset-Trigger nach Mess. OMNI-Counter laeuft eigenstaendig.
      Aufruf raus.

13. **AK13 — `_diversity_in_operate`-Flag-Semantik:**
    - Heute: False bis Phase=operate erreicht (nach Mess), dann True
    - Stufe2: True ab `_enable_diversity()` (Phase=operate sofort)
    - Code-Stellen die das Flag pruefen sollen weiter funktionieren

### Sekundäre Refactors

14. **AK14 — `control_panel.update_diversity_ratio()` Signatur:**
    - `measure_step`, `measure_total`, `is_dynamic`-Parameter aus
      Signatur raus
    - `operate_seconds_remaining` raus (keine Re-Mess-Frist mehr)
    - Neue Signatur: `update_diversity_ratio(ratio, phase, *, scoring_mode,
      current_ant=None)`
    - **Alle ~6 Aufrufer (mw_cycle, mw_radio, main_window) anpassen**
      (Memory-Lesson `feedback_partial_fix_check_other_paths.md`!)

15. **AK15 — `_on_dynamic_ratio_changed`-Slot bleibt aber vereinfacht:**
    - Signal-Pfad: Dynamic emittet `ratio_changed_dynamic` → MainWindow-
      Slot ruft `update_diversity_ratio` mit aktuellem Ratio
    - `is_dynamic=True`-Argument fliegt raus (AK14)

16. **AK16 — `DiversityController.set_band()` / `set_mode()`:**
    - `set_band` existiert NICHT (nur `on_band_change` heute, ruft `reset()`).
      Stufe2: `on_band_change` raus. Bandwechsel-Reset wird stattdessen aus
      `mw_radio._on_band_changed` direkt aufgerufen: `_diversity_ctrl.reset()`
      (was nur noch Histogramm + Search-Counter reset) PLUS
      `_dynamic_ctrl.reset()` (Buffer leer).
    - `set_mode(mode)`-Methode bleibt — setzt `_mode` +
      `_search_slots_remaining` (CQ-Such-Counter). Wird weiter genutzt.

17. **AK17 — `DiversityController.reset()` vereinfacht:**
    - Heute resetet: `_phase`, `_measure_step`, `_measurements`,
      `_operate_cycles`, `ratio`, `dominant`, `_freq_histogram`,
      `_cq_freq_hz`, `_current_gap_width_hz`, `_search_slots_remaining`,
      `_recalc_count`, `_was_early_stopped`, `_last_measured_at`
    - Stufe2 reset: `_freq_histogram`, `_cq_freq_hz`,
      `_current_gap_width_hz`, `_search_slots_remaining`, `_recalc_count`,
      `ratio` (50:50), `dominant` (None)

### Tests

18. **AK18 — Test-Strategie:**

    **Komplett gelöschte Tests:**
    - `test_should_remeasure.py` (1 h-Frist gibt's nicht)
    - `test_p35_startup_bugs.py` (Toggle + Mess-Phase, beides weg) —
      wenn Bug-A-Test (radio.ip=None defer) noch sinnvoll, einzelne Tests
      in `test_p34_stufe2_*.py` migriert

    **Umgebaute Tests:**
    - `test_diversity_cache_reuse.py` → Ratio-Cache-Tests raus, Gain-
      Cache-Tests bleiben (Gain-Pfad)
    - `test_diversity_bandwechsel.py` → `on_band_change`+Mess-Tests raus,
      Histogramm-Reset-Tests bleiben/anpassen
    - `test_p1_cache_simple.py` → 5 Branches → 2 Branches reduzieren
    - `test_p22_preset_atomic.py` → `commit_with_ratio`-Tests raus,
      `stage_gain`/`discard_staged`/`is_valid_gain` bleiben
    - `test_diversity_dynamic.py` → `dynamic_diversity_enabled`-Tests
      raus, Active-via-`_enable_diversity`-Tests neu
    - `test_diversity_dynamic_integration.py` → analog
    - `test_diversity_density.py` → Mess-Phase-spezifische Tests raus
    - `test_preset_store.py` → Ratio-API-Tests raus

    **Neue Tests (`tests/test_p34_stufe2.py`):**
    | # | Name | Was prueft |
    |---|---|---|
    | T1 | `test_no_measure_phase_constants` | DiversityController hat kein `MEASURE_CYCLES`, kein `_measurements`-Dict |
    | T2 | `test_no_should_remeasure` | `should_remeasure` Attribut existiert nicht |
    | T3 | `test_no_record_measurement` | `record_measurement` Methode existiert nicht |
    | T4 | `test_no_evaluate` | `_evaluate` Methode existiert nicht |
    | T5 | `test_enable_diversity_activates_dynamic` | Nach `_enable_diversity()` ist `_dynamic_ctrl.is_active()` True |
    | T6 | `test_disable_diversity_deactivates_dynamic` | Nach `_disable_diversity()` ist `_dynamic_ctrl.is_active()` False |
    | T7 | `test_check_preset_gain_fresh_calls_enable` | Gain fresh → `_enable_diversity` direkt aufgerufen, kein DXTuneDialog |
    | T8 | `test_check_preset_gain_stale_opens_dx_dialog` | Gain stale → DXTuneDialog öffnet |
    | T9 | `test_no_mess_status_dialog_module` | `import ui.mess_status_dialog` schlaegt fehl (Modul geloescht) |
    | T10 | `test_no_dynamic_diversity_enabled` | `Settings.dynamic_diversity_enabled` Attribut existiert nicht |
    | T11 | `test_no_handle_diversity_measure` | `MainWindow._handle_diversity_measure` Attribut existiert nicht |
    | T12 | `test_no_apply_dynamic_toggle` | `MainWindow._apply_dynamic_toggle` Attribut existiert nicht |
    | T13 | `test_scoring_mode_change_resets_dynamic` | Wenn `_activate_diversity_with_scoring("dx")` nach Standard aufgerufen, ist `_dynamic_ctrl.buffer_a1` leer (Reset triggered) |
    | T14 | `test_pending_init_after_radio_connect` | P35 Bug A: radio.ip=None → pending, nach Connect → `_enable_diversity` triggert + Dynamic aktiv |
    | T15 | `test_band_change_resets_dynamic_buffer` | Bandwechsel mit Diversity aktiv → `_dynamic_ctrl.buffer_a1` leer |
    | T16 | `test_no_preset_ratio_methods` | PresetStore hat kein `commit_with_ratio`, `save_ratio`, `is_valid_ratio` |

    **Test-Bilanz:** 1239 → erwartet **~1180 grün** (–~80 Statik-spezifische,
    +~16 P34-Stufe2). R1-Klarstellung der genauen Diff: nach Code-Schreiben
    Final-R1 zaehlt.

---

## 3. Implementierungs-Plan (15 atomare Commits)

| # | Commit | Datei(en) | Inhalt |
|---|---|---|---|
| **C1** | Tests: Statik-Tests löschen | `tests/test_should_remeasure.py`, `tests/test_p35_startup_bugs.py` | reine Loeschungen, vor Code-Refactor |
| **C2** | `core/diversity.py` Mess-Phase raus | core/diversity.py | record_measurement + _evaluate + _check_phase3_early_stop + start_measure + on_band_change + can_measure + on_operate_cycle + should_remeasure + Konstanten (MEASURE_CYCLES, EARLY_STOP_*) + Felder + Properties — alles raus. `choose()` reduziert auf Operate. `reset()` vereinfacht. |
| **C3** | `core/dynamic_diversity.py` Listener-Coupling raus | core/dynamic_diversity.py | `_scoring_mode_listeners.append(...)` in __init__ raus |
| **C4** | `core/preset_store.py` Ratio-API raus | core/preset_store.py | is_valid_ratio, get_ratio_age_minutes, commit_with_ratio, save_ratio, Ratio-Felder-Validierung |
| **C5** | `config/settings.py` dynamic_diversity_enabled + save_diversity_preset raus | config/settings.py | Property + Setter + Methode |
| **C6** | `ui/mess_status_dialog.py` löschen | (Datei-Löschung) | komplettes File raus |
| **C7** | `ui/mw_radio.py` Statik-Pipeline raus | ui/mw_radio.py | _open/close/cancelled_mess_status_dialog, _try_diversity_cache_reuse, _assess_ratio, _pending_ratio_status, Auto-Reactivate-Block (Z.683-688), _enable_diversity cached_ratio + measure-Pfade, _check_diversity_preset gain-only (5→2 Branches), _on_dx_tune_accepted pending_ratio_status-Logik |
| **C8** | `ui/mw_cycle.py` _handle_diversity_measure raus | ui/mw_cycle.py | Z.93-94 Aufruf + Z.236-372 Methode + Z.288-289 `_is_dyn`-Check (immer True bei Diversity → wegmoeglich, defensive-Check beibehalten als is_active-Guard) |
| **C9** | `ui/main_window.py` Toggle-Handler + closeEvent raus | ui/main_window.py | _apply_dynamic_toggle Methode + closeEvent Mess-Dialog-Block + _mess_status_dialog-Attribut |
| **C10** | `ui/control_panel.py` measure-Params raus | ui/control_panel.py | update_diversity_ratio: measure_step/measure_total/is_dynamic/operate_seconds_remaining raus + alle Aufrufer anpassen |
| **C11** | `ui/settings_dialog.py` Toggle-UI raus | ui/settings_dialog.py | QCheckBox + Tooltip + Apply-Block |
| **C12** | Bestehende Tests anpassen | diverse tests/ | s.o. AK18 |
| **C13** | Neue P34-Stufe2 Tests | tests/test_p34_stufe2.py NEU | T1-T16 |
| **C14** | `_diversity_in_operate` Semantik + AK12 Folgewirkungen | ui/mw_radio.py, ui/mw_cycle.py | `_diversity_in_operate=True` direkt im `_enable_diversity`, `_stats_warmup_cycles=6` ditto, OMNI-Counter-Reset-Aufruf raus |
| **C15** | APP_VERSION + Doku | main.py, HISTORY.md, HANDOFF.md, CLAUDE.md, TODO.md | 0.97.18 → 0.97.19, alle 4 Pflicht-Dateien |

**Reihenfolge:** C1 zuerst (Tests raus die nach Code-Refactor eh sterben).
C2-C5 (Core+Settings) — Tests fuer diese Module brechen bewusst, werden in
C12 gefixt. C6 (File-Loeschung). C7-C9 (UI). C10-C11 (UI-Detail). C12+C13
(Test-Pflege). C14 (Folgewirkungen-Aufraumen). C15 (Doku/Version).

**Geschätzter Aufwand:** 4-5 h.

---

## 4. Edge-Cases (12, V1 + V2-Ergaenzung)

### EC1: User auf Normal → wechselt zu Diversity DX (frischer Gain-Cache)

- Stufe2: `_check_diversity_preset` → gain fresh → `_enable_diversity("dx")`
  → Phase=operate, 50:50, Dynamic aktiv, in ~3 Min Verhältnis-Wechsel.

### EC2: User auf Normal → Diversity Standard mit stale Gain

- `_check_diversity_preset` → gain stale → DXTuneDialog (Gain-Mess) →
  user accept → `_on_dx_tune_accepted` → `_enable_diversity("normal")` →
  wie EC1.

### EC3: User auf 80m, SWR zu hoch, Gain-Mess bricht ab

- DXTuneDialog Cancel → kein `_enable_diversity` → Diversity nicht
  aktiviert → bleibt Normal-Modus.

### EC4: Bandwechsel mit aktiver Diversity

- `_on_band_changed` → `_check_diversity_preset(new_band, mode, scoring)`
- Falls Gain fresh: `_enable_diversity` → reset + Dynamic.activate +
  buffer leer
- Falls Gain stale: DXTuneDialog
- Während Bandwechsel: Dynamic.deactivate (über `_disable_diversity` im
  Bandwechsel-Flow)?
- **Frage R1:** wer triggert Dynamic.reset() bei Bandwechsel? Heute über
  `_enable_diversity` dynamic_active-Pfad implizit. Stufe2: bleibt
  implizit via `_enable_diversity` (immer triggert activate+reset).

### EC5: 1 h ohne QSO mit aktiver Diversity

- Stufe2: nichts passiert. Dynamic läuft live weiter. **Keine Re-Mess.**

### EC6: App-Quit waehrend laufender Gain-Mess (DXTuneDialog offen)

- `closeEvent` → MessStatusDialog-Block raus (existiert nicht mehr).
- DXTuneDialog: Cancel-Flow existiert eigenstaendig (Test-Plan EC6:
  closeEvent muss `_dx_tune_dialog`-Attribut ggf. clean schliessen falls
  vorhanden — bereits implementiert? → V2 verifiziert in Code).

### EC7: scoring_mode-Wechsel (Standard ↔ DX) bei aktivem Diversity

- Heute: scoring_mode-Setter triggert Listener → `_dynamic_ctrl.reset()`.
- Stufe2: Listener weg. Wer triggert reset? → `_activate_diversity_with_scoring`
  ruft `_diversity_ctrl.scoring_mode = new` UND `_dynamic_ctrl.reset()`
  explizit. AK5.

### EC8: Mode-Wechsel (FT8 ↔ FT4 ↔ FT2)

- `_on_mode_changed` → `_check_diversity_preset(band, new_mode, scoring)`
- Gain ist pro Modus separat im Preset → ggf. DXTuneDialog → wie EC4.

### EC9: Pending-Resume nach Radio-Connect (P35 Bug A)

- Heute: `_pending_diversity_init` triggert `_check_diversity_preset`
- Stufe2: bleibt unverändert. Funktioniert weiter.

### EC10: Dynamic record_slot bei Diversity-AUS

- record_slot prueft is_active()-Flag. is_active=False → No-Op.
- mw_cycle._on_cycle_decoded Z.111-112 Defensive-Check bleibt. **Wichtig:**
  bei Stufe2 ist is_active synchron mit Diversity-Mode (activate/deactivate
  in _enable/disable_diversity). Sollte nie inkonsistent sein. Defensive-
  Check trotzdem behalten — Race-Schutz zwischen Diversity-AUS und
  laufendem Decoder-Hook.

### EC11: Alter PresetStore-JSON mit ratio-Feldern

- Stufe2 ignoriert die Felder still (kein Migrations-Lauf, kein
  Aufrueum-Script). Beim naechsten Gain-Mess wird `commit_with_ratio`
  nicht mehr aufgerufen → ggf. werden Felder mit `None` oder gar nicht
  ueberschrieben. PresetStore.save schreibt das ganze Dict raus. Ratio-
  Felder bleiben dann verrottend drin. Akzeptabel.

### EC12: Alte settings.json mit dynamic_diversity_enabled

- Settings ignoriert unbekannte Keys (lt. PROBLEME.md fuer Python-load-
  Pattern). Property existiert nicht mehr → kein Lese-Aufruf →
  Stoerungsfrei.

---

## 5. Randbedingungen

### Hardware-Schutz (PFLICHT)

- **ANT1 = TX immer. ANT2 = nur RX.** `radio.set_tx_antenna("ANT1")` vor
  jedem TX-Trigger. NICHT angefasst durch P34-Stufe2.
- Diversity-Pattern (70:30 / 50:50 / 30:70) nutzt nur RX-Antennen.

### Threading

- `_diversity_lock` (RLock, MainWindow) bleibt — Queue + current_ant
  unter Lock.
- `DynamicDiversityController._lock` (threading.Lock) bleibt — Buffer +
  Active-Flag.
- `Qt.QueuedConnection` fuer Dynamic-Signal-Slot bleibt.

### UI

- Antennen-Panel zeigt jetzt IMMER: aktuelles Ratio + RX-Antennen-Suffix
  (P37/P40) + "● DYNAMISCH (live)"-Phase-Label.
- "Messung X/6"-Anzeige entfaellt.
- "Diversity Neuberechnung in X Min."-Anzeige entfaellt.
- Cache-Reuse-Toast war eh bereits entfernt (v0.95.13).

### Tests

- Vor jedem Commit: `QT_QPA_PLATFORM=offscreen ./venv/bin/python3 -m pytest tests/ -q`
- Erwartung: 1239 → ~1180 grün (Refactor reduziert Test-Count netto).

---

## 6. Nicht im Scope

- **Gain-Kalibrierung** (DXTuneDialog Phase 2)
- **CQ-Frequenz-Such** (Histogramm, Sticky-Gap)
- **Diversity-Operate-Betrieb** (Antennen-Pattern, Stations-Akkumulation,
  Stats-Logging)
- **PSKReporter-Integration**
- **Bandpilot** (3-Wege-Empfehlung)
- **Bänder-Deaktivierung Feature** (separates Folgeprojekt)
- **Migrations-Script fuer alte PresetStore-Dateien** (silent ignore reicht)

---

## 7. V1 → V2 Diff (was hat sich geandert)

| Änderung V1 → V2 | Grund |
|---|---|
| **AK5 hinzu:** `_scoring_mode_listeners` raus, scoring_mode-Wechsel-Reset explizit aus mw_radio | KISS, explicit > magic |
| **AK7a hinzu:** Cache-Ratio bei `_enable_diversity` Frage — V2-Default: kein Cache-Init, Start IMMER 50:50 | Vereinfachung, Dynamic übernimmt eh in 3 Min |
| **AK11 hinzu:** `_operate_cycles`-Counter raus → wie wird Slot-Pattern gewählt? Klarstellung fuer R1 | War in V1 unklar |
| **AK12 hinzu:** Folgewirkungen aus `_handle_diversity_measure`-Entfernung detailliert | War in V1 oberflaechlich |
| **AK13 hinzu:** `_diversity_in_operate` Semantik geklaert | War in V1 nicht eindeutig |
| **AK14 erweitert:** auch `operate_seconds_remaining` raus aus update_diversity_ratio | War in V1 unklar |
| **AK16 hinzu:** `set_band` existiert nicht, `on_band_change` raus, `set_mode` bleibt | Praezision |
| **AK17 hinzu:** `reset()` vereinfacht (nur CQ-Such-relevantes) | Praezision |
| **Edge-Cases EC7-EC12 hinzu** | Vollstaendigkeit |
| **Commit C14 hinzu:** Folgewirkungen-Aufraumen separat | Atomarer Commit |
| **APP_VERSION-Bump 0.97.18 → 0.97.19** statt 0.98.0 | reines Refactor, kein Feature |
| **Tests-Strategie:** 16 P34-Stufe2 Tests statt 10 | Vollstaendigkeit (T11-T16 Defensive-Tests fuer geloeschte API) |

---

## 8. Offene Fragen an R1

1. **Q1 — Cache-Ratio bei `_enable_diversity` resume:** AK7a — sollte
   bei pending-Resume (P35 Bug A) das alte Ratio aus PresetStore als
   Start-Ratio benutzt werden, oder reicht 50:50 + Dynamic übernimmt? V2
   sagt "50:50, KISS". R1 prueft ob es Use-Cases gibt wo 5+5 Slots
   (~75 s) als Startup-Hicker problematisch sind.

2. **Q2 — `_operate_cycles`-Ersatz:** AK11 — `choose()` brauchte heute
   `_operate_cycles` als Modulo-Index fuers Pattern. Stufe2:
   `_operate_cycles` raus. Wie zaehlt der Pattern-Index? Optionen:
   - A) Slot-Index vom Caller mit reingegeben (mw_cycle hat slot_index
     ohnehin)
   - B) Eigene Property `_pattern_index` die `set_band`/`set_mode` reset
     und `choose()` selbst inkrementiert
   - C) `choose(slot_index)` als Argument
   V2 tendiert zu C — KISS, kein internes State.

3. **Q3 — `_evaluate` als Modul-Funktion-Wrapper:** Heute ruft `_evaluate`
   den Modul-Helper `evaluate_ratio`. Wenn `_evaluate` raus, wird
   `evaluate_ratio` nur noch von `DynamicDiversityController._evaluate_locked`
   genutzt. Public-API bleibt (kein Konflikt). OK.

4. **Q4 — `DiversityController` als abstrakte Klasse refaktorieren?**
   Nach Stufe2 enthaelt sie nur noch: CQ-Frequenz-Such (Histogramm-
   basiert) + Pattern-Auswahl + ratio/dominant-Felder. Frage: ist der
   Name `DiversityController` noch sinnvoll, oder besser `DiversityState`
   / `CQFrequencyController` + `AntennaPattern`?
   V2-Default: Name bleibt (KISS, Renamings fuehren zu vielen Folgefixes).

5. **Q5 — `ratio` + `dominant`-Felder auf DiversityController:** Diese
   bleiben als Zustand fuer "aktuelles Verhaeltnis". Setter von Dynamic
   geschrieben. Lese-API: control_panel + choose(). OK, bleibt.

6. **Q6 — `_dynamic_ctrl` als reine Implementierungs-Detail vs Public-API:**
   Heute: MainWindow hat `_dynamic_ctrl` als Attribut, mw_cycle nutzt
   `getattr(self, "_dynamic_ctrl", None)`. Mit Stufe2 ist Dynamic
   Default — sollte `_dynamic_ctrl` Pflicht-Attribut werden statt
   getattr-defensive?
   V2-Default: getattr-defensive bleibt (Test-Setup ohne MainWindow soll
   weiter laufen).

---

**V2 fertig. Naechster Schritt: R1-Review.**
