# Final-R1 — P54 Auto-Tune bei Bandwechsel + RFPreset-Stützpunkt

Du bist Senior-Reviewer. Sprache: Deutsch. Prüfe die **bereits umgesetzte**
P54-Implementation streng auf Bugs, Race-Conditions, Hardware-Sicherheits-
Verletzungen, vergessene Pfade.

## Was wurde umgesetzt (V3-Spec)

Variante C aus Mike-Diskussion: nach Bandwechsel automatisch 10 W TUNE
über AutoTuneDialog (modal, exec-blocking). Während TUNE wird FWDPWR
gemessen; bei SWR-Good wird `rf_preset_store.save(radio, band, 10, 10)`
aufgerufen (R1-F1: nominal watt=10, NICHT round(avg)).

### Code-Änderungen
1. `config/settings.py`: Default `auto_tune_on_band_change=True`.
2. `ui/settings_dialog.py`: Toggle in Tab „FT8 & Diversity" + Load/Save/
   Reset.
3. `ui/auto_tune_dialog.py` NEU: WindowModal, Spinner, Status-Label,
   Cancel-Button, Backup-Timeout (`tune_duration_s + 5 s`),
   `auto_tune_done(bool, float, float)`-Signal.
4. `ui/main_window.py` `__init__`: State-Vars `_auto_tune_running=False`,
   `_auto_tune_dialog=None`.
5. `ui/mw_tx.py`:
   - `_on_meter_update` sampled FWDPWR auch wenn `_tune_active=True`
     (nicht nur bei `encoder.is_transmitting`).
   - `_tune_post_swr_check`:
     - Snapshot `_fwdpwr_samples` → avg.
     - Plausibilität `2.0 < avg < 80.0` → `rf_preset_store.save(radio,
       band, 10, 10)` + `_apply_rf_preset()` neu.
     - R1-F2: Bei `_auto_tune_running` Signal emit statt QMessageBox.
     - R1-F3: Diversity-Resume nur im manuellen Pfad.
   - Helper `_start_auto_tune_for_band_change(band)`:
     - `set_tx_antenna("ANT1")` VOR `tune_on()` (Hardware-Pflicht).
     - `set_rfpower_direct(10)` + `tune_on()`.
     - `dialog.exec()` blockt bis Signal/Cancel/Timeout.
     - Returns True bei DialogCode.Accepted.
6. `ui/mw_radio.py`:
   - `_on_band_changed` Re-Entry-Schutz wenn `_tune_active=True`.
   - Hook nach `_apply_rf_preset()` (Z.481) ruft Helper wenn Setting +
     `radio.ip` + Band nicht SWR-blockiert + `tuner_present`.
7. `main.py`: APP_VERSION 0.97.43 → 0.97.44.

### Tests
26 Tests in `tests/test_p54_auto_tune.py` — Gate-Logik (T3-T7),
Save-Schlüssel (T8/T8b R1-F1), Plausibilität (T9/T10/T18/T19),
Manueller Pfad (T12), Sampling (T13/T13b), Signal-Routing R1-F2 (T14/T15),
Diversity-Schutz R1-F3 (T16), `_apply_rf_preset` Re-Call (T17/T17b),
Verbindungsverlust (T20), Hardware ANT1 (T21), Cleanup (T22), Token-Race
(T23). 1393 Tests gesamt grün.

## Prüfpunkte

1. **R1-F1 (`watt=10` statt round(avg)):** Wird in `_tune_post_swr_check`
   korrekt mit `10, 10` aufgerufen?
2. **R1-F2 (Signal vs. QMessageBox):** Bei `_auto_tune_running=True` wird
   nur das Signal emittiert, KEINE QMessageBox.
3. **R1-F3 (Diversity-Resume-Schutz):** `_check_diversity_preset` wird im
   Auto-Tune-Pfad NICHT vom Post-Check aufgerufen.
4. **V2-F1 (`_apply_rf_preset` Re-Call):** Wird nach Save erneut
   aufgerufen damit aktuelle Convergenz davon profitiert.
5. **V2-F3 (Re-Entry-Schutz):** `_on_band_changed` ignoriert Wechsel
   wenn `_tune_active=True`.
6. **Hardware-Pflicht:** `set_tx_antenna("ANT1")` explizit VOR
   `tune_on()` im Helper.
7. **Cleanup-Pfade:** Cancel, Timeout-Backup, Verbindungsverlust —
   `_tune_in_progress` und `_auto_tune_running` werden zuverlässig
   zurückgesetzt.
8. **Bandwechsel-Flow nach Auto-Tune:** `_on_band_changed` läuft nach
   `_start_auto_tune_for_band_change` weiter (Bandpilot,
   `_check_diversity_preset`) — keine Doppel-Aufrufe?
9. **Test-Coverage:** Reichen 26 Tests?
10. **Sind irgendwo set_tx_antenna-Aufrufe versehentlich auf ANT2 möglich?**

## Antwortformat

- F-Findings ROT/ORANGE/GELB
- Push-Status: FREIGEGEBEN / FIX / BLOCKIERT
- KP

Max 1000 Wörter.
