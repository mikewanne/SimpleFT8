# P63 R1 DeepSeek-V4-pro Review Request

**Aufgabe:** SWR-Block-System per Band-Marker bauen für SimpleFT8 v0.97.35 → v0.97.36.

## Lies zuerst V1 + V2:

- `prompts/p63_swr_block_marker_v1.md` — Spec, Architektur, AC1-AC10, 11 Commits, 15 Tests
- `prompts/p63_swr_block_marker_v2.md` — Self-Review, 12 Findings F1-F12, Plan-Korrekturen für V3

## Kern-Problem (kurz)

Mike-Field-Test 17m-Band: SWR-Watchdog (P53) feuert → Stop-Block läuft korrekt → ABER:
- `_gain_measure_locked` bleibt `True` (Bug — `_on_swr_alarm` resetet nicht)
- TUNE-Button GESPERRT (genau das was Mike zur Antennen-Diagnostik braucht)
- OMNI/Hunt KLICKBAR (würden sofort wieder SWR-Alarm geben)

Mike-Spec: Band-Marker pro Band in-memory, blockiert Auto-Pfade, manueller TUNE bleibt
klickbar zur Freischaltung. Settings: `tuner_present` (bool) + `tune_duration_s` (15/30s).
LDG AT-200 Pro Standard: 10W TUNE-Power fest.

## Was ich brauche von dir

**Beurteile V1+V2 auf:**

1. **Halluzinationen** — sind alle API-Calls, Zeilennummern, Property-Namen korrekt?
   (Ich habe in V2 bereits F1 gefunden: `control_panel.last_swr()` war Halluzination,
   korrekt ist `radio.last_swr`.)

2. **Bug-Risiken** — übersehen wir Edge-Cases?
   - SWR-Wert direkt nach `tune_off` stale? (V2-F2)
   - `_swr_blocked_bands` Concurrency-Race zwischen GUI-Slots?
   - `_handle_dx_tuning` (KALIBRIEREN) ohne Pre-Check?
   - Auto-TUNE im `_start_dx_tuning` Z.1366 Post-Check soll auch Marker setzen? (V2-F11)

3. **Architektur-Trade-offs:**
   - V2-F7 schlägt KISS-Lösung statt Injection: AutoHunt-Pre-Check in
     `mw_cycle._run_auto_hunt` VOR `select_next`-Call. Korrekt?
   - V2-F8 schlägt Pre-Check in Toggle-Handlern (`_on_btn_omni_cq_toggled` Z.764 +
     `_on_btn_auto_hunt_toggled` Z.854) statt in `on_cycle_start`. Korrekt?
   - V2-F9 schlägt KISS-Else-Branch in `_start_dx_tuning` Z.1379-1381 für `tuner_present=False`.
     Korrekt?

4. **Open Points aus V2 §10:**
   - F2 Post-Tune-Delay: 200ms genug? Oder auf `meter_update`-Signal warten?
   - F11 Auto-TUNE-Post-Check (Z.1366): soll auch Marker setzen?
   - F12 `_tune_in_progress` nur für manuellen TUNE OK?

5. **KISS-Check:** ist irgendwo Overengineering oder unnötige Abstraktion?
   (Mike-Mantra: „brauchen wir das wirklich, oder verliebt in unsere Idee?")

6. **Hardware-Sicherheit:** ANT1-Pflicht eingehalten?
   `_on_tune_clicked` ruft `set_tx_antenna("ANT1")` — verifiziert.
   `_start_dx_tuning` ruft kein `set_tx_antenna` — Risiko?
   `_on_swr_alarm` stoppt antennen-neutral — gut.

## Antwort-Format (bitte halten)

```
## Findings

### F1 — [Bug/Risiko/Verbesserung/Hinweis]
**Was:** ...
**Wo:** Datei:Zeile
**Wirkung:** ...
**Empfehlung:** ...

### F2 — ...
```

## Push-Empfehlung

Am Ende: „Push freigegeben (V3-Phase OK)" oder „Nachbessern + Re-Review".

## Wichtige Kontext-Files (folgen als Argumente)

1. `ui/mw_tx.py` — `_on_swr_alarm` + `_on_tune_clicked` (zu ändern)
2. `ui/mw_radio.py` — `_check_diversity_preset` + `_start_dx_tuning` + `_set_gain_measure_lock`
3. `ui/main_window.py` — Init + `_on_btn_omni_cq_toggled` + `_on_btn_auto_hunt_toggled`
4. `ui/settings_dialog.py` — `_build_tab_ft8` + `_save_and_close`
5. `ui/mw_qso.py` — `_on_station_clicked` + `_on_cq_clicked`
6. `core/auto_hunt.py` — `select_next` + `mark_pick` (P61-Pattern)
7. `core/omni_cq.py` — `on_cycle_start`
8. `ui/control_panel.py` — `btn_tune` + `update_swr` + `_update_button_visibility`
9. `config/settings.py` — DEFAULTS

## Mike-Spec-Mantra (verbindlich)

- Hobby-Funker-Tool, kein Contest-Tool
- KISS schlägt Eleganz
- Drei ähnliche Zeilen besser als verfrühte Abstraktion
- ANT1 = TX. IMMER. ANT2 = nur RX.
- Modal-Pattern + In-Memory-Marker (kein Persist)

Push-Status: KEIN Push bis Final-R1 + Field-Test F1-F10 ✓.
