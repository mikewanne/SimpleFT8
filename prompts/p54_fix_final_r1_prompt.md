# Final-R1 — P54-FIX (post-Implementation)

Du bist Senior-Reviewer. Sprache: Deutsch. Pruefe **bereits umgesetzte**
P54-FIX-Implementation streng auf Bugs, Race-Conditions, Hardware-
Sicherheits-Verletzungen, vergessene Pfade. Tests: 1395 → 1414 grün.

## Was umgesetzt wurde (V3-Spec)

Variante: bei jedem TUNE läuft jetzt eine echte Closed-Loop-Convergenz
in Phase B nach der Tuner-Match-Phase A. Speichert den echten Slider-
Wert für 10W (`rf_preset_store.save(band, 10, <konvergiert>)`), nicht
mehr hart rf=10.

### Code-Änderungen
1. `ui/main_window.py`: State-Vars `_tune_converged_rf` + `_tune_convergence_cancelled`.
2. `ui/mw_tx.py`:
   - `_wait_with_event_loop(ms)` Helper mit QEventLoop+QTimer.
   - `_tune_converge_to_target(target_w, max_iterations, iter_ms)` Helper.
     Iteriert proportional bis FWDPWR≈target. Cancel-Flag-Check, MIN_SAMPLES=2,
     Clamp 1..100, max-iter best-effort.
   - `_kruecken_skalierung(band, target_w)` Helper. Linear vom 1-Stützpunkt
     × 0.9 Sicherheit. None bei 0 oder ≥2 Stützpunkten.
   - `_apply_rf_preset` erweitert: nutzt Krücke wenn `load()` None gibt.
   - `_tune_stop` mit Phase-B-Block: SWR-Check vor Convergenz, Convergenz-
     Aufruf, Result in `_tune_converged_rf`.
   - `_tune_post_swr_check` Save mit `_tune_converged_rf` (Fallback 10),
     Plausibilitäts-Check rf∈[3..50], `_apply_rf_preset`+`set_power` nach Save.
   - `_on_tune_clicked` + `_start_auto_tune_for_band_change`: Cancel-Flag
     Reset vor Phase A.
3. `ui/auto_tune_dialog.py`: Cancel-Pfad setzt `_tune_convergence_cancelled = True`.
4. `tests/test_p54_fix.py` NEU: 19 Tests.
5. `tests/test_p54_auto_tune.py` aktualisiert: 4 Tests an neue Plausibilitäts-
   Logik angepasst.
6. `main.py`: APP_VERSION 0.97.44 → 0.97.45.

## Prüfpunkte

1. **R1-F1 ROT (set_power nach _apply_rf_preset):** im Save-Branch von
   `_tune_post_swr_check` vorhanden?
2. **R1-F2 ROT (Cancel-Race):** Cancel-Flag wird im AutoTuneDialog gesetzt,
   in Convergenz-Schleife geprüft, Reset vor Phase A im Caller?
3. **R1-F3 ROT (State-Var Init):** `_tune_converged_rf` + `_tune_convergence_cancelled`
   in `MainWindow.__init__` deklariert?
4. **R1-F4 ROT (Konvergierter Save):** `rf_preset_store.save` nutzt
   `_tune_converged_rf` statt hart 10?
5. **R1-F5 ORANGE (Plausibilität):** `if 3 <= rf_to_save <= 50` Check vor Save?
6. **R1-F6 ORANGE (SWR vor Phase B):** `_tune_stop` prüft SWR nach Phase A
   und skippt Phase B bei SWR > Limit?
7. **Hardware-Pflicht ANT1:** kein `set_tx_antenna`-Aufruf in Phase B / Krücke?
8. **Phase B Timer:** Convergenz innerhalb der TUNE-Dauer, kein Race mit Auto-Stop?
9. **Krücken-Faktor:** Formel `anchor_rf × (target_w / anchor_watt) × 0.9` korrekt?
10. **Manuelle TUNE Pfad:** identische Phase B + Save-Logik wie Auto-Tune?

## Antwortformat
- F-Findings ROT/ORANGE/GELB mit Pfad/Wurzel/Fix
- Push-Status: FREIGEGEBEN / FIX / BLOCKIERT
- KP

Max 800 Wörter.
