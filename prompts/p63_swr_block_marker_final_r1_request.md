# P63 Final-R1 Review Request — Push-Freigabe für SimpleFT8 v0.97.36

**Status:** Code implementiert (11 Commits C1-C10 atomar), Tests 1306 → **1327 grün** (+21).

## Was wurde gebaut

Bezugsdokumente in diesem Repo:
- `prompts/p63_swr_block_marker_v1.md` — Initial-Spec
- `prompts/p63_swr_block_marker_v2.md` — Self-Review mit 12 Findings F1-F12
- `prompts/p63_swr_block_marker_r1.md` — Erste R1-Review mit 6 Findings
- `prompts/p63_swr_block_marker_v3.md` — Finaler Plan mit AC1-AC13

## V3-Findings alle eingearbeitet

| # | Finding | Status |
|---|---|---|
| AC1 | Lock-Release `_set_gain_measure_lock(False)` in `_on_swr_alarm` | ✓ implementiert in ui/mw_tx.py |
| AC2/AC3 | Marker-Set / Modal-Text-Branching nach `tuner_present` | ✓ in `_on_swr_alarm` |
| AC4 | `_tune_in_progress`-Bypass | ✓ erste Zeile in `_on_swr_alarm` |
| AC5 | 10W fest + Dauer 15/30 + Token-Pattern | ✓ neuer `_on_tune_clicked` |
| AC6/AC7 | 2s Post-Tune SWR-Check via `_tune_post_swr_check` | ✓ R1-F1 umgesetzt |
| AC8 | 6 Pre-Checks (Diversity-Preset, Start-DX, CQ-Click, Station-Click, OMNI-Toggle, Hunt-Toggle) | ✓ |
| AC9 | Tuner=False skipt Auto-TUNE + Power-Reset | ✓ R1-F3 umgesetzt |
| AC11 | Auto-TUNE-Fehler Lock-Release + Marker | ✓ R1-F2 umgesetzt in `_start_dx_tuning` |
| AC12 | Pending-Click-Schutz in `_on_station_clicked` UND `_on_tx_finished` | ✓ R1-F5 umgesetzt |
| AC13 | Explizites `set_tx_antenna("ANT1")` vor Auto-TUNE | ✓ in `_start_dx_tuning` Z.1338+x |

## Tests (18 + 3 Bonus = 21 neue)

| # | Test |
|---|---|
| T1 | SWR-Alarm Lock-Release |
| T2 | Marker-Set bei tuner_present=True |
| T3 | Kein Marker bei tuner_present=False |
| T4 | OMNI-Toggle Pre-Check + Button-State-Reset |
| T5 | Auto-Hunt-Toggle Pre-Check + Button-State-Reset |
| T6 | Normal-CQ Pre-Check + Button-State-Reset |
| T7 | `_check_diversity_preset` Pre-Check VOR `_assess_gain` |
| T8 | Manueller TUNE auf rotem Band ERLAUBT (kein Pre-Check) |
| T9 | 10W FEST (`set_rfpower_direct(TUNE_POWER_W)`), `tune_power`-Setting NICHT gelesen |
| T10 | Dauer aus `tune_duration_s` mit Whitelist {15, 30} |
| T11 | `_tune_in_progress`-Bypass VOR is_transmitting-Check |
| T12 | Post-Tune SWR≤Limit: discard + Diversity-Resume |
| T13 | Post-Tune SWR>Limit: Modal „Tuner konnte nicht matchen" |
| T14 | `tuner_present=False`: Auto-TUNE-Guard `radio.ip AND tuner_present` |
| T15 | `set_tuner_present(False)` blendet btn_tune aus |
| T18 | 2s QTimer in `_tune_stop` |
| T19 | Auto-TUNE-Fehler Marker + Lock-Release |
| T20 | Power-Reset im Skip-Branch |
| Bonus | Defaults haben P63-Keys |
| Bonus | Pending-Click geschützt in tx_finished |
| Bonus | Marker-Check FIRST in station_clicked |

## Was ich von dir brauche

1. **Code-Review der tatsächlichen Implementation** in den 8 Touch-Files:
   - `ui/mw_tx.py:_on_swr_alarm` + `_on_tune_clicked` + `_tune_stop` + `_tune_post_swr_check`
   - `ui/mw_radio.py:_check_diversity_preset` + `_start_dx_tuning`
   - `ui/main_window.py` Init + `_on_btn_omni_cq_toggled` + `_on_btn_auto_hunt_toggled` + `_on_settings_clicked`
   - `ui/settings_dialog.py:_build_tab_ft8` + `_save_and_close` + `_load_values` + `_reset_defaults`
   - `ui/mw_qso.py:_on_station_clicked` + `_on_cq_clicked` + `_on_tx_finished`
   - `ui/control_panel.py:set_tuner_present`
   - `config/settings.py` DEFAULTS

2. **Sicherheits-Check:** sind alle V3-AC erfüllt? Gibt es noch Edge-Cases?
   - Lock-Release in allen 3 Fehlerpfaden (`_on_swr_alarm`, `_start_dx_tuning`-Fehler, `_check_diversity_preset`-Pre-Check) korrekt?
   - Concurrency `_swr_blocked_bands`-Set (alle Modifier im GUI-Thread)?
   - Token-Pattern `_tune_auto_stop_token` + `_tune_post_check_token` race-frei?
   - Pending-Click-Schutz in `_on_tx_finished` korrekt geordnet?
   - ANT1-Pflicht verifiziert?

3. **KISS-Check:** Overengineering?

4. **Push-Empfehlung** am Ende: „Push freigegeben" oder „Nachbessern".

## Mike-Spec-Mantra (Reminder)

- Hobby-Funker-Tool, kein Contest-Tool
- KISS schlägt Eleganz
- ANT1 = TX. ANT2 = nur RX.

## Field-Test-Plan F1-F10 (für Mike nach Push)

| # | Was |
|---|---|
| F1 | 17m-Band: SWR-Alarm → Modal „Band gesperrt — bitte TUNE" |
| F2 | Nach Modal: TUNE klickbar, OMNI/Hunt/CQ blockiert mit `add_info` |
| F3 | Manueller TUNE 15s 10W läuft durch, Auto-Stop, „TUNE beendet — prüfe SWR (2s)..." |
| F4 | TUNE-Erfolg → Marker grün, Gain-Mess startet automatisch (P62-Pause) |
| F5 | TUNE-Misserfolg → Modal „Tuner konnte nicht matchen" |
| F6 | Settings „Tuner=NEIN": TUNE-Button hidden, Gain-Mess ohne Auto-TUNE |
| F7 | Settings „Tuner=NEIN": SWR-Alarm = Modal + Stop, KEIN Marker |
| F8 | Settings „TUNE-Dauer 30s": manueller TUNE läuft 30s |
| F9 | Marker pro Band: 17m rot, 20m wechseln → läuft normal |
| F10 | App-Restart: alle Marker weg |
