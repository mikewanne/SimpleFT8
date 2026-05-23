# Final-R1 — P74-A Modal-Konsolidierung — committeter Code-Review

Du hast schon V3 reviewt und 4 Findings beigesteuert (F1 ORANGE Token-
Invalidierung, F2 ORANGE Stop-Token, F3 GELB Lock try/finally, F4 GELB
Backup-Race). Alle 4 wurden eingebaut. Jetzt: schau dir das tatsächlich
committet Code-Ergebnis an und sage mir ob's wirklich sauber sitzt.

## Was committet wurde (6 atomare Commits)

- **C1** DXTuneDialog State-Machine `TUNE → GAIN_CYCLES → FINISHED`:
  neues Klassen-Signal `auto_tune_done`, Constructor-Param
  `with_tune_phase`/`tune_duration_s`/`mode`, `_apply_state_ui`,
  `_start_tune_phase`, `_on_tune_tick`/`_on_tune_backup_timeout`,
  `_on_auto_tune_done` mit `_tune_phase_finished`-Flag (R1-F4),
  `_on_cancel` state-aware mit Token-Rotation (R1-F1), `feed_cycle`-
  State-Guard.

- **C2** mw_radio neue Helper:
  - `_start_pipeline_for_band_change(band, scoring)`: try/except
    Lock-Release (R1-F3) — bei Konstruktor-Fehler Lock + Pending-Flags
    aufgeräumt. Setzt `_pending_dx_diversity=True` +
    `_pending_diversity_scoring=scoring` vorab. Modal exec(), gibt
    True bei Accept zurück.
  - `_start_dialog_tune_sequence(dialog, band, mode, duration_s)`:
    expliziter `_tune_auto_stop_token = object()` (R1-F2), Hardware-
    TUNE-Sequenz, `set_tx_antenna("ANT1")` Pflicht. Setzt Dialog als
    `_auto_tune_dialog` (Duck-Typing-Pfad).

- **C3** `_on_band_changed` Fall-B-Check VOR bestehender TUNE-Branch:
  `is_case_b` mit 8 Bedingungen, bei True → Pipeline-Helper +
  `_case_b_handled=True`. Bestehender Auto-TUNE-Block jetzt elif. Bei
  Fail → `_on_rx_mode_changed("normal")`. Diversity-Preset-Check am
  Methoden-Ende skipt bei `_case_b_handled`.

- **C4** Parameter-Propagation:
  - `_start_dx_tuning(scoring_mode, with_tune_phase=False)`: bei True
    skipt Hardware-TUNE-Block + ruft direkt `_open_dx_tune_dialog
    (with_tune_phase=True)`. RX-Cleanup (Stations-Tabellen) bleibt.
  - `_open_dx_tune_dialog(with_tune_phase=False)`: Param durchgereicht
    an DXTuneDialog-Constructor.
  - `_handle_dx_tuning` (KALIBRIEREN) + `_check_diversity_preset`
    auto_remess-Branch nutzen `with_tune_phase=tuner_present`.

- **C5** 12 Tests (T1-T10 DXTuneDialog, T11-T12 Fall-B-Branch).
  Tests 1744 → 1756. 4 bestehende Tests angepasst (neuer
  `with_tune_phase`-Arg).

- **C6** APP_VERSION 0.97.94, HISTORY/HANDOFF/CLAUDE/TODO.

## Was du prüfen sollst

Sanity-Check des **tatsächlichen committeten Codes**:

1. **R1-F1 Cancel-Token-Rotation:** Sitzt das in `dx_tune_dialog.py
   _on_cancel` korrekt? Reihenfolge `token rotieren → convergence-Flag
   → _tune_stop` richtig? Was wenn parent None ist (Test T8-Pfad)?

2. **R1-F2 Stop-Token in `_start_dialog_tune_sequence`:** Token wird
   gesetzt + an Lambda übergeben. Wird der Token bei einem User-Cancel
   (`parent._tune_stop(None)`) wirklich von `_tune_stop` verglichen
   und der old token-Stop dann ignoriert? Sind die Pfade konsistent
   mit `_start_auto_tune_for_band_change`?

3. **R1-F3 Lock-Release bei Exception:** try/except in
   `_start_pipeline_for_band_change` umfasst Konstruktor + exec().
   Wenn `dialog.exec()` selbst eine Exception wirft (selten), wird
   Lock weiterhin released? Edge-Cases?

4. **R1-F4 Backup-vs-Echtsignal-Race:** `_tune_phase_finished` als
   Idempotenz-Flag in `_on_auto_tune_done` + `_on_tune_backup_timeout`
   sichert das. Aber `_tune_phase_finished` wird auch im Cancel-Pfad
   gesetzt — kann ein spätes echtes Signal nach Cancel den Dialog
   trotzdem versuchen umzuschalten?

5. **`_on_band_changed` Fall-B-Branch:** is_case_b-Bedingungen alle
   konsistent (Negation richtig?). `_case_b_handled` skipt korrekt den
   nachfolgenden Diversity-Preset-Check (Z.~683). Bei Pipeline-Fail
   wird `_on_rx_mode_changed("normal")` gerufen — aber was wenn
   `_rx_mode` schon „normal" war oder das `_pending_diversity_scoring`
   noch nicht reset ist?

6. **`_check_diversity_preset` auto_remess + tuner_present=False:**
   In dem Pfad wird `with_tune_phase=False` übergeben → alter
   Hardware-TUNE-Pfad in `_start_dx_tuning` läuft. Stimmt das mit
   AC18 überein? Kein toter Code? SWR-bad-Modal im alten Pfad ist
   bewusst dringeblieben (Out-of-Scope-Hygiene).

7. **Duck-Typing für `_auto_tune_dialog`:** mw_tx.py:343/438/454
   emittiert weiter via `dlg.auto_tune_done.emit(...)`. DXTuneDialog
   und AutoTuneDialog haben jetzt beide das Signal identisch deklariert.
   Stimmt das wirklich für alle Emit-Pfade? `_tune_post_swr_check`
   Disconnect-Pfad mw_tx.py:343 (radio.ip leer) zählt auch?

8. **Test-Coverage:** T1-T12 decken Happy-Path + Fail-Pfade ab. Reicht
   das oder fehlt z.B. ein Test für Pipeline-Helper-Konstruktor-
   Exception (R1-F3 Pfad)?

9. **Sonstige übersehene Risiken:** Setting-Migration nötig? Backwards-
   Compat für altes settings.json? Race zwischen Bandwechsel und
   Pipeline-Helper-Dialog-Erstellung?

## Format

Sei knapp. Severity (🔴 ROT / 🟠 ORANGE / 🟡 GELB / 🟢 OK), Datei:
Zeile (sofern möglich), Was, Vorschlag. Wenn alles passt: „PUSH
FREIGEGEBEN". Wenn Nachbessern: konkret was.

## Code-Files

`ui/dx_tune_dialog.py` und `ui/mw_radio.py` (geänderte Stellen — gesamte
Files anbei) und `ui/mw_tx.py` (Duck-Typing-Stellen).
