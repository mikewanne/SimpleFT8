# Final-R1 — P67 Code-Review (post-Implementation)

Du bist Senior-Reviewer. Sprache: Deutsch. Pruefe die **bereits umgesetzte**
P67-Implementation streng auf Bugs, Race-Conditions, Hardware-Sicherheits-
Verletzungen, vergessene Pfade, Test-Luecken.

## Was wurde umgesetzt (V3-Spec)

Variante C: Auto-Hunt-Session beendet sich automatisch wenn 5 Min keine
Mausbewegung erkannt wird. 10-Min-Hard-Cap bleibt unveraendert, parallel.

Aenderungen:
1. `ui/main_window.py`:
   - Klassen-Konstante `_AUTO_HUNT_MOUSE_INACTIVITY_TIMEOUT_S = 300`.
   - Neuer State `self._auto_hunt_last_mouse_t: float = 0.0` in
     `_init_presence_watchdog`.
   - `_poll_mouse_activity` setzt bei Mausbewegung zusaetzlich
     `_auto_hunt_last_mouse_t = time.monotonic()`.
   - `_on_btn_auto_hunt_toggled(True)` setzt Anker VOR `start_auto_hunt(600)`.
   - `_on_auto_hunt_polling_tick` (1s-Tick) prueft Inaktivitaet VOR
     Text-Update; bei delta > 300 → `add_info(...) + print(...) +
     stop_auto_hunt("mouse_inactive_5min")`.
   - KEIN `_abort_active_tx` — laufendes QSO darf zu Ende.
2. `core/auto_hunt.py`:
   - `stop_auto_hunt` Docstring um Reason `mouse_inactive_5min` erweitert.
   - Cleanup-Logik: DEFAULT-Branch (clear cooldowns + last_tx_even=None).
3. `tests/test_p67_mouse_inactivity.py`: 15 Tests, alle grün.
4. `main.py`: APP_VERSION 0.97.42 → 0.97.43.

## Pruefpunkte
1. Wird der Anker zuverlaessig gesetzt VOR dem ersten Polling-Tick?
   (Race-Schutz gegen Default 0.0 → Sofort-Stop.)
2. Stimmt der Stop-Pfad mit der Hardware-Pflicht „nie set_tx_antenna im
   Stop-Pfad" ueberein?
3. Reihenfolge im Polling-Tick: `if not active` → return; sonst
   inactivity-Check → stop. Korrekt?
4. Reason `mouse_inactive_5min` in der DEFAULT-Cleanup-Branch — wird
   `_cooldown.clear()` und `_last_tx_even = None` auch tatsaechlich
   ausgeloest? (Negativ-Test: `totmann_expired` darf NICHT gleich
   behandelt werden.)
5. Tests `tests/test_p67_mouse_inactivity.py` (15 Stueck): decken sie
   alle Code-Pfade ab? Welche Pfade fehlen?
6. Konsistenz `_PRESENCE_TIMEOUT` (15 Min CQ/QSO) vs.
   `_AUTO_HUNT_MOUSE_INACTIVITY_TIMEOUT_S` (5 Min Auto-Hunt) — kein
   semantischer Konflikt?
7. UI-Text klar?
8. Werden andere Stop-Pfade (manual_halt, band_change, etc.) durch P67
   gestoert?

## Antwortformat
- KP (kritische Punkte): ...
- F-Findings: ROT / ORANGE / GELB
- Push-Status: FREIGEGEBEN / FREIGEGEBEN MIT FIX / BLOCKIERT

Max 1000 Woerter.
