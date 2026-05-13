# P34-Stufe2 — V3 (Final, Compact-fest)

**Status:** V3 nach V1 → V2 → R1-Review. Verbindliche Spezifikation.
**Datum:** 2026-05-13 nachmittags.
**Workflow:** V3 → Plan-Mode → Backup → Code → Final-R1 → HISTORY/HANDOFF/CLAUDE/TODO.

---

## 0. Einstieg für neue KI (Compact-Recovery)

Falls Compact diese Session unterbrochen hat: lies **NUR diese V3-Datei**.
V1 (`p34_stufe2_v1.md`) und V2 (`p34_stufe2_v2.md`) sind im Archiv,
nicht aktuell. R1-Output (`p34_stufe2_r1.md`) ist eingearbeitet — alle
Findings adressiert.

### 0.1 Mike's Anweisung (13.05.2026 nachmittags)

> *"Statik-Pipeline raus, dynmisch läuft ja top. Workflow autonom, kein
> Rueckfragen, beide KIs arbeiten Hand in Hand bis zum Ende."*

### 0.2 Architektur-Kern

**Vor Stufe2 (Status quo v0.97.18):** ENTWEDER-ODER mit Settings-Toggle
"Antennen-Verhältnis dynamisch anpassen (Testphase)".
- Toggle AUS → Statik-Pipeline (Phase 3 Mess, 90 s Sperre, 1 h Re-Mess)
- Toggle AN  → Dynamic-Pipeline (Live 5er-Buffer, Slot-für-Slot)

**Nach Stufe2:** Nur noch Dynamic. Toggle weg, Statik komplett raus.
Gain-Kalibrierung (DXTuneDialog Phase 2) bleibt unangetastet.

### 0.3 Compact-Recovery-Hinweise

- **Backup-Pfad:** `Appsicherungen/2026-05-13_v0.97.18_vor_p34_stufe2/`
- **Aktuelle Test-Bilanz vor Code:** 1239 grün
- **Geplante APP_VERSION:** 0.97.18 → **0.97.19** (Patch-Bump für reines Refactor)
- **Final-R1-File:** `prompts/p34_stufe2_final_r1.md`
- **R1-Findings die in V3 eingearbeitet sind:** s. Abschnitt 9 (V2→V3 Diff)

---

## 1. Ziel

Statik-Ratio-Pipeline (Phase 3 Mess, 1 h-Frist, Settings-Toggle, MessStatusDialog,
PresetStore-Ratio-API) komplett raus. Dynamic ist Default und einziger Pfad bei
aktivem Diversity-Mode.

**Bonus:** 80m-Abbruch-Bug (Mike-Beobachtung 13.05.) wird obsolet — keine Mess-
Phase mehr, keine "0/6 Hänger"-Symptome.

**Out-of-Scope:** Gain-Kalibrierung (DXTuneDialog), CQ-Frequenz-Such, Bandpilot,
Bänder-Deaktivierung.

---

## 2. Akzeptanzkriterien (verbindlich, 20 ACs)

### Kern-Refactor

1. **AK1 — Statik-Mess-Phase komplett raus** (`core/diversity.py`):
   - `_phase == "measure"`-Branch existiert nicht mehr
   - Methoden weg: `record_measurement`, `_check_phase3_early_stop`,
     `_evaluate`, `start_measure`, `on_band_change`, `can_measure`,
     `on_operate_cycle`, `should_remeasure`
   - Konstanten weg: `MEASURE_CYCLES`, `EARLY_STOP_FRACTION`,
     `EARLY_STOP_THRESHOLD`, `REMEASURE_INTERVAL_SECONDS`
   - Felder weg: `_phase`, `_measure_step`, `_measurements`,
     `_operate_cycles`, `_last_measured_at`, `_was_early_stopped`,
     `_dynamic_active`
   - Properties weg: `phase`, `measure_step`, `operate_cycles`,
     `seconds_until_remeasure`, `_early_stop_at`, `dynamic_active`
   - `_scoring_mode_listeners`-Liste weg (siehe AK6)

2. **AK2 — `_handle_diversity_measure` in `mw_cycle.py` raus**:
   - Methode + Aufruf-Stelle (Aufruf-Condition `was_phase == "measure"`)
     löschen
   - Folgewirkungen siehe AK14 (Setup-Operationen in `_enable_diversity`
     migrieren)

3. **AK3 — Settings-Toggle weg:**
   - `Settings.dynamic_diversity_enabled` Property + Setter raus
   - `settings_dialog.py`: QCheckBox + Tooltip + Apply-Block raus
   - `MainWindow._apply_dynamic_toggle` Methode raus
   - Auto-Reactivate-Block in `mw_radio._activate_diversity_with_scoring`
     (heute Z.683-688) raus
   - **Anti-Pattern-Check:** Grep nach `dynamic_diversity_enabled` über
     alle Files; alle Aufrufer entfernen (Memory-Lesson
     `feedback_partial_fix_check_other_paths.md`)

4. **AK4 — Dynamic ist Default bei Diversity-Mode (mit Radio-Connect-Guard):**
   - `_enable_diversity()` ruft `_dynamic_ctrl.activate()` auf
     **NUR WENN** Radio verbunden ist (`radio.ip` gesetzt)
   - Bei `radio.ip=None`: deferred-Init wie heute (P35 Bug A), KEIN
     `activate()`-Aufruf. Stattdessen `_pending_diversity_init = scoring`
   - Resume-Pfad via `_check_diversity_preset` nach Radio-Connect
     triggert dann `_enable_diversity` erneut → diesmal mit `radio.ip`
     gesetzt → `activate()`
   - `_disable_diversity()` ruft `_dynamic_ctrl.deactivate()` auf
     (unconditional, ist sicher auch bei radio=None)

   **R1-F1 KRITISCH (eingearbeitet):** activate() darf NICHT bei
   deferred-Init aufgerufen werden.

5. **AK5 — Buffer-Reset Strategie bei `_enable_diversity`:**
   - Beim Aktivieren mit verbundenem Radio: `_dynamic_ctrl.reset()` →
     `activate()` (Reihenfolge: erst Buffer leeren, dann aktivieren)
   - `activate()` setzt selbst `_active=True`, ändert Ratio nur wenn
     aktuell 50:50/None (AK5 von Stufe1 — Cache-Reuse-Respekt bleibt für
     den Fall dass kein Cache, sondern aktuelle Live-Werte)
   - **R1-F3 entschieden:** Start IMMER 50:50 (kein Preset-Ratio-Reuse).
     Begründung: Dynamic übernimmt in 5+5 Slots (~75 s bei FT8). Saubere
     Trennung Statik(persisted) vs Dynamic(live). KISS.

6. **AK6 — `_scoring_mode_listeners`-Liste raus, explicit Reset:**
   - DiversityController hat keine Listener-Liste mehr
   - `DynamicDiversityController.__init__` registriert KEINEN Listener
   - `mw_radio._activate_diversity_with_scoring` ruft nach
     `_diversity_ctrl.scoring_mode = scoring` explizit
     `_dynamic_ctrl.reset()` auf

7. **AK7 — MessStatusDialog komplett weg:**
   - `ui/mess_status_dialog.py` Datei löschen
   - `MainWindow._open_mess_status_dialog`, `_close_mess_status_dialog`,
     `_on_mess_status_cancelled` raus
   - `_mess_status_dialog`-Attribut in `MainWindow` raus
   - Aufruf in `MainWindow.closeEvent` raus
   - Aufruf-Stellen in `mw_radio._enable_diversity` (Modal öffnen) und
     `mw_cycle._handle_diversity_measure` (Modal schließen) fallen mit
     dem Refactor weg

### Pipeline-Vereinfachung

8. **AK8 — `_enable_diversity` vereinfacht** (`ui/mw_radio.py`):

   Neue Signatur (kein cached_ratio mehr):
   ```python
   def _enable_diversity(self, scoring_mode: str = "normal") -> None:
   ```

   Neuer Ablauf (linear, kein If/Else über 3 Pfade mehr):
   1. RX-Liste + QSO-Panel + Stations leeren (wie heute)
   2. Queue + current_ant unter `_diversity_lock` neu (wie heute)
   3. `_diversity_ctrl.scoring_mode = scoring_mode`
   4. `_diversity_ctrl.reset()` (Histogramm, Search-Counter — siehe AK17)
   5. **Deferred-Branch:** falls `radio.ip is None`:
      - `_pending_diversity_init = scoring_mode`
      - `_diversity_ctrl.ratio = "50:50"`, `dominant = None`
      - `_set_cq_locked(False)`, `_set_gain_measure_lock(False)`
      - Print "Radio nicht verbunden — Init aufgeschoben"
      - `return` (KEIN activate)
   6. **Normal-Branch:** Radio verbunden:
      - `_diversity_ctrl.ratio = "50:50"`, `dominant = None`
      - `_dynamic_ctrl.reset()` (Buffer leer für fresh Start)
      - `_dynamic_ctrl.activate()` (siehe AK4)
      - `_set_cq_locked(False)`, `_set_gain_measure_lock(False)`
      - `_diversity_in_operate = True` (AK14)
      - `_stats_warmup_cycles = 6` (AK14)
      - `update_diversity_ratio("50:50", scoring_mode=…, current_ant=…)`

9. **AK9 — `_check_diversity_preset` vereinfacht** (5 Branches → 2):
   - `_assess_ratio()` Methode raus
   - `_pending_ratio_status`-Attribut raus
   - `_try_diversity_cache_reuse` Methode raus (kein Cache-Ratio-Reuse)
   - Branches:
     - **`gain == "fresh"`** → `_enable_diversity(scoring)` direkt
     - **`gain in ("stale", "missing")`** → DXTuneDialog → bei Accept
       `_enable_diversity(scoring)`
   - `_on_dx_tune_accepted` vereinfacht: kein `_pending_ratio_status`-
     Branching mehr, nach Gain-Mess immer `_enable_diversity`

10. **AK10 — PresetStore Ratio-API raus** (`core/preset_store.py`):
    - Methoden weg: `is_valid_ratio`, `get_ratio_age_minutes`,
      `commit_with_ratio`, `save_ratio`
    - Ratio-Format-Validierung in `_validate_entry`/`is_valid_gain` nur
      noch Gain-Felder
    - **R1-F5 (eingearbeitet):** Beim Laden eines alten Presets mit
      ratio-Feldern wird **einmalig** loggen:
      `[PresetStore] Ratio-Felder in {Key} ignoriert (Dynamic-Pipeline)`.
      In `PresetStore.__init__` nach `load()` — pro Key der ratio
      enthält 1× pro Session.

11. **AK11 — `Settings.save_diversity_preset` raus:**
    - Methode raus
    - Aufruf in `mw_cycle._handle_diversity_measure` faellt mit der
      Methode weg
    - Alte settings.json-Keys werden silent ignoriert

12. **AK12 — `choose(slot_index)` mit Argument** (`core/diversity.py`):

    **R1-F2 entschieden (Option C):** `choose()` bekommt Slot-Index als
    Argument vom Caller (mw_cycle hat slot_index ohnehin). Kein internes
    `_operate_cycles`-Counter mehr.

    Neue Signatur:
    ```python
    def choose(self, slot_index: int) -> str:
    ```
    - `slot_index` ist int (FIFO-Slot-Zähler vom Caller)
    - Pattern-Index = `slot_index % len(pattern)` (Pattern hat Länge 6)
    - Pattern-Auswahl:
      - `ratio == "70:30"` → `_PAT_70_A1[idx]`
      - `ratio == "30:70"` → `_PAT_70_A2[idx]`
      - sonst → `("A1", "A1", "A2", "A2")[slot_index % 4]` (50:50, 4-Slot-Pattern)

    Caller in `mw_radio._switch_antenna_for_next_slot` oder wo
    `choose()` aufgerufen wird: `slot_index` von der bestehenden Queue-
    Zähler-Logik übergeben (heute heißt das nicht slot_index, aber es gibt
    `_diversity_ant_queue` und einen impliziten Counter — siehe Code-
    Verifikation V3-Erstellung).

    **WICHTIG:** Mw_cycle/mw_radio ruft `choose()` heute NICHT direkt auf.
    Die Pattern-Auswahl läuft über `_diversity_ant_queue` in mw_radio.py.
    `choose()` ist Public-API von DiversityController, wird heute via
    `_diversity_ctrl.choose()` aus mw_radio.py:`_get_next_antenna` (oder
    ähnlich) gerufen. **Code-Verifikation in Schritt 5:** wenn `choose()`
    nirgends mehr im Code als Public-API genutzt wird, kann es komplett
    raus statt umgebaut.

13. **AK13 — Hardware-Schutz (PFLICHT):**
    - `radio.set_tx_antenna("ANT1")` unangetastet
    - Diversity-Pattern (70:30 / 50:50 / 30:70) nutzt nur RX-Antennen
    - Vor jedem TX-Trigger ANT1 verifiziert (bestehender Code)

### Folgewirkungen (kritisch!)

14. **AK14 — Setup-Operationen aus `_handle_diversity_measure` migrieren:**

    Heute macht `_handle_diversity_measure` beim Phase-Übergang
    measure→operate (Z.300-369):
    - `_diversity_in_operate = True` → **→ `_enable_diversity` AK8.6**
    - `_stats_warmup_cycles = 6` → **→ `_enable_diversity` AK8.6**
    - `_set_cq_locked(False)` → **→ `_enable_diversity` AK8.6 schon drin**
    - `commit_with_ratio` + `save_diversity_preset` → **entfällt (AK10, AK11)**
    - `get_free_cq_freq` + `audio_freq_hz` setzen → **→ entfällt** (im
      nächsten operate-Slot triggert `_refresh_diversity_freq_view` das
      sowieso pro-Slot)
    - `update_freq_histogram` → **→ entfällt** (nächster Slot eh)
    - `_close_mess_status_dialog` → **→ entfällt (AK7)**
    - `omni.reset_counter_after_measure` → **→ entfällt** (keine Mess-
      Phase mehr → kein Trigger; OMNI-Counter läuft eigenständig)

15. **AK15 — `_diversity_in_operate`-Flag-Semantik:**
    - Heute: False bis erstes operate, dann True
    - Stufe2: True ab `_enable_diversity()` (Phase=operate sofort)
    - Code-Stellen die `_diversity_in_operate` prüfen funktionieren weiter

### Sekundäre Refactors

16. **AK16 — `control_panel.update_diversity_ratio()` Signatur:**

    Heute (mit allen optionalen Parametern):
    ```python
    def update_diversity_ratio(self, ratio, phase, *,
                               measure_step=None, measure_total=None,
                               operate_seconds_remaining=None,
                               scoring_mode="normal",
                               is_dynamic=False,
                               current_ant=None):
    ```

    Stufe2:
    ```python
    def update_diversity_ratio(self, ratio, *,
                               scoring_mode="normal",
                               current_ant=None):
    ```

    - `phase` raus (immer "operate")
    - `measure_step`, `measure_total`, `operate_seconds_remaining` raus
    - `is_dynamic` raus (immer True bei Diversity)

    **Anti-Pattern-Check:** Alle ~6 Aufrufer (`mw_cycle`, `mw_radio`,
    `main_window`) anpassen. Memory-Lesson:
    `feedback_partial_fix_check_other_paths.md`!

    **Im control_panel Renderer:** "● DYNAMISCH (live) — RX Ant1/Ant2"-
    Label IMMER zeigen (war heute nur bei `is_dynamic=True`). Statik-
    spezifische Phase-Labels ("● MESSUNG (X/6)", "Diversity Neuberechnung
    in X Min.") werden nie wieder gezeigt → können aus dem Renderer raus.

17. **AK17 — `DiversityController.reset()` vereinfacht:**

    Heute resetet 13 Felder. Stufe2 reset:
    - `_freq_histogram = {}` (Histogramm leer)
    - `_cq_freq_hz = None`
    - `_current_gap_width_hz = 0`
    - `_search_slots_remaining = self._SEARCH_INTERVAL_SLOTS.get(mode, 4)`
    - `_recalc_count = 0`
    - `ratio = "50:50"`
    - `dominant = None`

### Tests

18. **AK18 — Test-Strategie:**

    **Komplett gelöschte Tests** (im Commit "Tests: Statik-Tests löschen"):
    - `tests/test_should_remeasure.py` (1 h-Frist)
    - `tests/test_p35_startup_bugs.py` (Toggle + Mess-Phase Bugs A/B/B5).
      Bug-A-Test (radio.ip=None defer) wird in `test_p34_stufe2.py` T17
      migriert.

    **Umgebaute Tests** (im Commit "Tests anpassen"):
    - `tests/test_diversity_cache_reuse.py` → Ratio-Cache-Tests raus,
      Gain-Cache-Tests bleiben oder umgebaut
    - `tests/test_diversity_bandwechsel.py` → `on_band_change`+Mess-
      Tests raus, Histogramm-Reset-Tests bleiben/anpassen
    - `tests/test_p1_cache_simple.py` → 5 Branches → 2 Branches
    - `tests/test_p22_preset_atomic.py` → `commit_with_ratio`-Tests
      raus, `stage_gain`/`discard_staged`/`is_valid_gain` bleiben
    - `tests/test_diversity_dynamic.py` → `dynamic_diversity_enabled`-
      Tests raus, Activate-via-`_enable_diversity` neu
    - `tests/test_diversity_dynamic_integration.py` → analog
    - `tests/test_diversity_density.py` → Mess-Phase-spezifische Tests raus
    - `tests/test_preset_store.py` → Ratio-API-Tests raus

    **Neue Tests** in `tests/test_p34_stufe2.py`:

    | # | Name | Was prueft |
    |---|---|---|
    | T1 | `test_no_measure_phase_constants` | Kein `MEASURE_CYCLES`, kein `_measurements`-Dict |
    | T2 | `test_no_should_remeasure` | `should_remeasure` Attribut existiert nicht |
    | T3 | `test_no_record_measurement` | `record_measurement` Methode existiert nicht |
    | T4 | `test_no_evaluate` | `_evaluate` Methode existiert nicht |
    | T5 | `test_enable_diversity_activates_dynamic` | Nach `_enable_diversity()` mit Radio: `_dynamic_ctrl.is_active() == True` |
    | T6 | `test_disable_diversity_deactivates_dynamic` | Nach `_disable_diversity()`: `is_active() == False` |
    | T7 | `test_check_preset_gain_fresh_calls_enable` | Gain fresh → `_enable_diversity` direkt, kein DXTuneDialog |
    | T8 | `test_check_preset_gain_stale_opens_dx_dialog` | Gain stale → DXTuneDialog öffnet |
    | T9 | `test_no_mess_status_dialog_module` | `import ui.mess_status_dialog` `ImportError` |
    | T10 | `test_no_dynamic_diversity_enabled` | `Settings.dynamic_diversity_enabled` nicht da |
    | T11 | `test_no_handle_diversity_measure` | `MainWindow._handle_diversity_measure` nicht da |
    | T12 | `test_no_apply_dynamic_toggle` | `MainWindow._apply_dynamic_toggle` nicht da |
    | T13 | `test_scoring_mode_change_resets_dynamic` | `_activate_diversity_with_scoring("dx")` nach Standard → Buffer leer |
    | T14 | `test_band_change_resets_dynamic_buffer` | Bandwechsel mit Diversity aktiv → Buffer leer |
    | T15 | `test_no_preset_ratio_methods` | PresetStore hat kein `commit_with_ratio`, `save_ratio`, `is_valid_ratio` |
    | T16 | `test_choose_slot_index_argument` | `DiversityController.choose(slot_index)` returnt korrektes Pattern (50:50, 70:30, 30:70) |
    | **T17 (R1-F8)** | `test_enable_diversity_deferred_no_radio` | radio.ip=None → kein `activate()`, `_pending_diversity_init` gesetzt, `is_active() == False` |

    **Erwartete Test-Bilanz** (R1-F6 korrigiert): **1239 → ~1175 grün**
    (–~80 Statik-spezifische, +~17 P34-Stufe2).

19. **AK19 — APP_VERSION-Bump:**
    - 0.97.18 → **0.97.19** (Patch-Bump, reines Refactor ohne Feature)

20. **AK20 — Doku-Updates (in dieser Reihenfolge nach Code-Fertig):**
    - `HISTORY.md` anhängen: `## 2026-05-13 v0.97.19 — P34-Stufe2 Statik-Pipeline raus`
    - `HANDOFF.md` updaten: Stand + Field-Test-Checkliste
    - `CLAUDE.md` Header: aktueller Stand + Test-Count
    - `TODO.md`: P34-Stufe2 als erledigt markieren
    - `Memory: project_p34_stufe2.md` neu, MEMORY.md-Index ergänzen
    - `docs/deepseek_lessons.md`: ggf. neue R1-Erkenntnis ergänzen

---

## 3. Implementierungs-Plan (10 atomare Commits)

**R1-F4 eingearbeitet:** Granularität reduziert von 15 auf 10 Commits.
Test-Löschungen/Anpassungen/Neue bleiben atomar (Tests müssen mit Code-
Refactor zusammen passen, atomare Trennung verhindert "broken commits").

| # | Commit | Datei(en) | Inhalt |
|---|---|---|---|
| **C1** | Statik-Tests löschen | `tests/test_should_remeasure.py`, `tests/test_p35_startup_bugs.py` | Reine File-Löschungen |
| **C2** | `core/diversity.py` Mess-Phase raus | `core/diversity.py` | record_measurement + _evaluate + _check_phase3_early_stop + start_measure + on_band_change + can_measure + on_operate_cycle + should_remeasure + Konstanten + Felder + Properties + dynamic_active + _scoring_mode_listeners — alles raus. choose() umgebaut auf `choose(slot_index)`. reset() vereinfacht (AK17). |
| **C3** | `core/dynamic_diversity.py` Listener-Coupling raus | `core/dynamic_diversity.py` | `_scoring_mode_listeners.append(...)` in __init__ raus |
| **C4** | `core/preset_store.py` Ratio-API raus + Info-Log alte Felder | `core/preset_store.py` | is_valid_ratio, get_ratio_age_minutes, commit_with_ratio, save_ratio raus. Bei Load alter ratio-Felder: 1× pro Key loggen (R1-F5) |
| **C5** | `config/settings.py` dynamic_diversity_enabled + save_diversity_preset raus | `config/settings.py` | Property + Setter + Methode |
| **C6** | UI Statik-Pipeline raus (R1-F4 Sammelcommit) | `ui/mw_radio.py`, `ui/mw_cycle.py`, `ui/main_window.py`, `ui/control_panel.py`, `ui/settings_dialog.py`, `ui/mess_status_dialog.py` | mess_status_dialog.py löschen. mw_radio: _enable_diversity vereinfacht (AK8 + Deferred-Guard AK4!), _check_diversity_preset 5→2 Branches (AK9), _try_diversity_cache_reuse + _assess_ratio + _pending_ratio_status raus, _open/_close/_cancelled_mess_status_dialog raus, _on_dx_tune_accepted vereinfacht, Auto-Reactivate-Block raus. mw_cycle: _handle_diversity_measure raus, _on_cycle_decoded `was_phase=="measure"`-Branch raus. main_window: _apply_dynamic_toggle Methode + closeEvent Mess-Dialog-Block + _mess_status_dialog-Attribut raus. control_panel: update_diversity_ratio Signatur vereinfacht (AK16), alle Aufrufer angepasst, Statik-Phase-Labels aus Renderer. settings_dialog: QCheckBox + Apply-Block raus. |
| **C7** | Tests anpassen | diverse `tests/` | Bestehende Tests umgebaut (AK18) |
| **C8** | Neue P34-Stufe2 Tests | `tests/test_p34_stufe2.py` NEU | T1-T17 |
| **C9** | scoring_mode-Wechsel-Reset explicit | `ui/mw_radio.py` (`_activate_diversity_with_scoring`) | Nach `_diversity_ctrl.scoring_mode = scoring` explizit `_dynamic_ctrl.reset()` (AK6) |
| **C10** | APP_VERSION + Doku | `main.py`, `HISTORY.md`, `HANDOFF.md`, `CLAUDE.md`, `TODO.md` | 0.97.18 → 0.97.19, alle Pflicht-Dateien |

**Reihenfolge wichtig:** C1 zuerst (kein "broken main"). C2-C5 (Core/Settings)
brechen UI-Tests bewusst. C6 (UI Sammelcommit) fixt sie strukturell. C7
passt verbleibende Tests an. C8 fügt neue Tests hinzu. C9 ist Logik-Detail.
C10 zuletzt (Doku).

**Geschätzter Aufwand:** 4-5 h.

---

## 4. Field-Test-Checkliste (Mike nach Code-fertig)

Nach App-Start mit v0.97.19:

| # | Test | Erwartung |
|---|---|---|
| **F1** | App-Start | Wie heute — 20m FT8 Normal (P35-Bug-F unangetastet) |
| **F2** | Normal → Diversity DX (Gain frisch) | Kein DXTuneDialog. Antennen-Panel zeigt sofort "● DYNAMISCH (live) — RX Ant1", Ratio 50:50. In ~75 s erste Dynamic-Auswertung. |
| **F3** | Normal → Diversity DX (Gain stale auf 80m) | DXTuneDialog öffnet. Cancel → kein Diversity. Bei Erfolg → wie F2. |
| **F4** | Bandwechsel mit aktiver Diversity | Sofort wieder Phase=operate, 50:50, Buffer leer. **Keine 90-Sek-Sperre mehr**. |
| **F5** | Modus-Wechsel (FT8→FT4) mit Diversity | Wie F4. |
| **F6** | scoring_mode (Standard→DX) mit Diversity | Buffer leer, Ratio 50:50, neu sammeln. |
| **F7** | 1 h ohne QSO mit Diversity AN | **Keine automatische Re-Mess.** Dynamic läuft weiter. |
| **F8** | Toggle in Einstellungen | Settings-Dialog hat **KEINEN** Toggle "Antennen-Verhältnis dynamisch anpassen" mehr. |
| **F9** | Antennen-Panel-Label | Immer "● DYNAMISCH (live) — RX Ant1/Ant2". **Niemals** "Messung X/6" oder "Diversity Neuberechnung in X Min." |
| **F10** | App-Quit mit Diversity aktiv | Saubere Abschaltung. Kein Mess-Modal-Phantom. |

**Bestanden wenn:** F1-F8 sauber. F9-F10 als visuelle Bestätigung.

---

## 5. Randbedingungen

### Hardware-Schutz (PFLICHT)
- ANT1 = TX immer. `radio.set_tx_antenna("ANT1")` vor jedem TX-Trigger.
- ANT2 nur RX, niemals TX.

### Threading
- `_diversity_lock` (RLock) bleibt
- `DynamicDiversityController._lock` (threading.Lock) bleibt
- `Qt.QueuedConnection` für Dynamic-Signal-Slot bleibt

### Persistence
- Gain-Werte (presets_standard.json, presets_dx.json) bleiben
- Ratio-Werte werden NICHT mehr geschrieben
- Alte JSON-Dateien mit Ratio-Feldern: silent ignore + 1×-Log (R1-F5)

### Tests
- Vor jedem Commit: `QT_QPA_PLATFORM=offscreen ./venv/bin/python3 -m pytest tests/ -q`
- Erwartung: **1175 grün** nach C8

---

## 6. Nicht im Scope

- Gain-Kalibrierung (DXTuneDialog Phase 2)
- CQ-Frequenz-Such-System
- Bandpilot
- Bänder-Deaktivierung Feature
- Migrations-Script für alte PresetStore-Dateien

---

## 7. Edge-Cases (12)

| # | Szenario | Stufe2-Verhalten |
|---|---|---|
| EC1 | Normal → Diversity DX (gain fresh) | `_check_diversity_preset` → `_enable_diversity("dx")` → 50:50, Dynamic aktiv |
| EC2 | Normal → Diversity Standard (gain stale) | DXTuneDialog → bei OK `_enable_diversity` |
| EC3 | 80m SWR zu hoch, Gain-Mess bricht | DXTuneDialog Cancel → bleibt Normal |
| EC4 | Bandwechsel mit Diversity aktiv | `_enable_diversity` triggert reset+activate+Buffer-leer |
| EC5 | 1 h ohne QSO mit Diversity | nichts passiert — Dynamic live weiter |
| EC6 | App-Quit während Gain-Mess | DXTuneDialog Cancel-Flow (existiert). Kein Mess-Modal mehr. |
| EC7 | scoring_mode-Wechsel (Std↔DX) | `_activate_diversity_with_scoring` ruft explizit `_dynamic_ctrl.reset()` (AK6) |
| EC8 | Mode-Wechsel (FT8↔FT4↔FT2) | `_check_diversity_preset` → ggf. DXTuneDialog → wie EC4 |
| EC9 | Pending-Resume nach Radio-Connect (P35 Bug A) | `_pending_diversity_init` triggert `_check_diversity_preset` → mit Radio diesmal Normal-Branch → activate() (AK4) |
| EC10 | record_slot bei Diversity-AUS | `is_active()=False` → No-Op |
| EC11 | Alter PresetStore-JSON mit ratio-Feldern | Silent ignore + 1× Info-Log (R1-F5) |
| EC12 | Alte settings.json mit dynamic_diversity_enabled | Silent ignore (Property gibt's nicht mehr) |

---

## 8. Erwartete Risiken nach Final-R1 (Pre-Empts)

1. **`choose()`-Aufrufer:** V3 Schritt 5 Code-Verifikation prüft ob
   `choose()` als Public-API tatsächlich noch genutzt wird oder die
   Antennen-Pattern-Auswahl ohnehin nur über `_diversity_ant_queue` läuft.
   Falls `choose()` nicht aufgerufen wird → komplett raus statt umbauen.

2. **`MEASURE_CYCLES`-Setter (heute Z.982):** Mit Konstante weg muss
   `_MULT`-Dict + Setter raus. In `_enable_diversity` Z.977-982.

3. **`_handle_diversity_measure`-Folgewirkungen für OMNI:**
   `omni.reset_counter_after_measure` (heute Z.367-369) wird nicht mehr
   getriggert. Test ob OMNI-Counter dadurch nicht mehr "neuer Slot, neuer
   Anfang"-Reset bekommt. Vermutlich akzeptabel — OMNI-Counter läuft
   eigenständig, Mess-Trigger war "nice to have".

4. **`update_diversity_counts(0, 0)`-Aufrufe:** Werden in
   `_enable_diversity` + `_disable_diversity` aufgerufen. Bleiben
   unverändert — kein Bezug zur Statik.

---

## 9. V2 → V3 Diff (R1-Findings eingearbeitet)

| R1-Finding | V3-Änderung |
|---|---|
| **🔴 F1 Bug — Radio.ip=None + activate() Race** | AK4 + AK8: activate() explizit hinter Radio-Connect-Guard. AK8 macht Deferred-Branch first |
| **🟠 F2 Risiko — `_operate_cycles`-Ersatz unklar** | AK12: Option C verbindlich — `choose(slot_index)` mit Argument. Klare Signatur |
| **🟠 F3 Risiko — Cache-Ratio-Start bei Pending-Resume** | AK5: Start IMMER 50:50, KISS, kein Preset-Ratio-Reuse. Verbindlich, keine Frage an R1 |
| **🟡 F4 Verbesserung — Commit-Granularität** | Reduziert von 15 → 10 Commits. C6 als UI-Sammelcommit |
| **🟡 F5 Verbesserung — Silent ignore alter Ratio-Felder** | AK10: 1×-Info-Log pro Key beim PresetStore-Load |
| **🔵 F6 Hinweis — Testanzahl-Inkonsistenz** | Korrigiert auf 1175 (1239 – 80 + 16 (T1-T16) + 1 (T17) = 1176, ≈ 1175 ± Test-Anpassungs-Effekte). AK18 |
| **🔵 F7 Hinweis — Zeilenangaben obsolet** | AK16 + AK14 nutzen jetzt Funktionsnamen + Block-Beschreibungen statt fixe Zeilen |
| **🟡 F8 Verbesserung — Test deferred-Init** | T17 hinzugefügt in AK18 |

---

## 10. Offene Fragen (KEINE — alle entschieden)

V2 hatte 6 offene Fragen — alle in V3 entschieden:
- **Q1 Cache-Ratio-Start:** 50:50 (AK5)
- **Q2 `_operate_cycles`-Ersatz:** `choose(slot_index)` (AK12)
- **Q3 `evaluate_ratio`-Modul-Funktion:** bleibt (kein Konflikt)
- **Q4 `DiversityController` rename:** nein (KISS, Folgefixes)
- **Q5 `ratio`/`dominant`-Felder:** bleiben als Zustand
- **Q6 `_dynamic_ctrl` getattr vs. Pflicht-Attribut:** getattr bleibt (Test-Setup-Robustheit)

---

## 11. Lessons-Learned-Vorab

Für Memory nach Code:
1. **Architektur-Migration vs Major-Bump:** Trotz "Pipeline raus" ist 0.97.19
   richtig — keine User-sichtbaren Feature-Adds, nur internes Refactor +
   Wegfall eines Toggle.
2. **R1-F1 (Radio.ip=None + activate Race):** R1 fand kritisches Race in
   V2-Pseudocode. Bestätigt: R1-Threading-Stärke (siehe deepseek_lessons.md).
3. **R1-F2 (offene Optionen):** R1 erzwang verbindliche Entscheidung für
   Pattern-Auswahl. Lesson: V2 darf keine "R1 entscheidet"-Branches mehr
   haben; alle Architektur-Trade-offs in V2 entschieden + R1 fact-checkt.

---

**V3 fertig. Nächster Schritt: Backup + Code (atomare Commits C1-C10) + Final-R1.**
