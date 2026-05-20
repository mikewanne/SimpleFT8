# P98 — Final-R1 Codereview (v0.97.70 vor Push)

Push-Freigabe ja/nein?

## Was P98 macht

Mike-Field-Test 20.05.: 3 Retries waren in 2 Fällen knapp/zu wenig.
DeepSeek-R1-Brainstorm bestätigt: beide auf 5 hochsetzen, Risiko gering.

**Konkret:**
- `core/qso_state.py:107` `MAX_RR73_RETRIES = 3 → 5`
- `core/qso_state.py:124` `QSOData.max_calls: int = 3 → 5`
- `core/qso_state.py:166` `QSOStateMachine.max_calls = 3 → 5`
- `ui/main_window.py:1216` `get("max_calls", 3) → 5`
- `ui/mw_qso.py:251` `get("max_calls", 3) → 5`
- `ui/mw_cycle.py:515` **Bugfix R1-F2:** war hartcodiert `= 3`, jetzt
  `settings.get("max_calls", 5)`
- `ui/settings_dialog.py:51` Hint-Text aktualisiert
- `ui/settings_dialog.py:621` Load-Fallback `3 → 5`, Default-Combo-Index 0→1
- `ui/settings_dialog.py:833` Reset-Default Combo-Index 3 (99) → 1 (5)
- `config/settings.py:60` `"max_calls": 99 → 5`

## R1-Findings (alle eingebaut)

- **R1-F1:** DG8DBW-Pfad geht über `on_message_received`-Branch (nicht
  `on_decoder_finished`-Retry-Pfad). `MAX_RR73_RETRIES`-Erhöhung wirkt
  nur bei leerem RX-Slot. Mike-Etikette: trotzdem nützlich für andere
  Fälle. ✓ akzeptiert.
- **R1-F2:** `mw_cycle.py:515` Hartcodierung **war Bug** — Auto-Hunt
  ignorierte User-Setting. Jetzt aus Settings. ✓
- **R1-F3:** Tests importieren `MAX_RR73_RETRIES` statt 5 hartcodieren. ✓

## Tests

10 neue Tests `tests/test_p98_retry_limits.py` (T1-T10):
- Konstanten-Werte (MAX_RR73_RETRIES, max_calls defaults)
- Retry-Verhalten WAIT_REPORT + WAIT_RR73 via Signal-Tracking
- Settings-Fallbacks
- mw_cycle Bugfix-Verifikation (kein hartcodiertes 3)
- Zeit-Budget (5 Retries × Slots < MAX_QSO_DURATION)
- Settings-Dialog Reset-Default

Alte Tests:
- `test_p1_bundle2.py:41` rr73_retries=3 → MAX_RR73_RETRIES import

**Suite: 1671 → 1681 (+10 P98, alle grün).**

## Bewertungs-Fragen

1. Coverage der 10 Tests vollständig?
2. R1-F1 (DG8DBW-Pfad) — sollte separat noch gefixt werden, oder ist
   das ein eigener P99-Kandidat? Aktueller P98-Patch verbessert Sache
   nur teilweise im DG8DBW-Fall.
3. `config/settings.py` Default 99 → 5: könnte Bestandsuser
   überraschen wenn sie die alte 99 erwarteten. Migration nötig oder
   reicht der Code-Fallback?
4. Hardware-Sicherheit: TX-relevante Pfade unbetroffen?
5. Final-Check: missing edge cases?

Kurze Antwort genügt.
