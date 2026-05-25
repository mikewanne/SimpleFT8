# Final-R1 — P128 Empf.-Eintrag 60s blocken nach ✓ QSO (committeter Code)

## Was ich will

Final-Review. Severity (🔴/🟠/🟡/🟢). PUSH FREIGEGEBEN ja/nein.

## Kontext

Mike-Field-Bug 25.05.: nach „✓ QSO komplett" sendet Gegenstation noch
R-23 → erscheint im QSO-Log. Mike: „beendet ist beendet".
Mike-Spec Variante A — 60s harter Block, RX-Tabelle unberührt.

## V3-ACs (alle MÜSSEN nach Review erfüllt sein)

- AC1: Cooldown in `_on_qso_complete` gesetzt
- AC2: blocked-call → kein add_rx im QSO-Log
- AC3: RX-Tabelle/Wasserfall unberührt
- AC4: Lazy-Aging nach 60s
- AC5 (R1-F5 🔴 ROT-Catch): State-Machine läuft trotzdem (NICHT return)
- AC6/AC7: Reset bei Band/Mode-Wechsel
- AC8: Manueller Re-Klick hebt Cooldown auf
- AC9: andere Stationen nicht betroffen
- AC10: Timeout setzt KEINEN Cooldown

## R1-Findings die in V3 eingearbeitet wurden

| # | Severity | Status |
|---|---|---|
| F1 (Frage 1) | 🟡 Timeout NICHT blocken | Mike-Spec war ✓ |
| F2 (Frage 2) | 🟢 Quick73-Interaktion akzeptabel | unverändert |
| F3 (Frage 3) | 🟢 P124-Reihenfolge OK | T12 verifiziert |
| F4 (Frage 4) | 🟢 Reset-Vollständigkeit OK | unverändert |
| **F5 (Frage 5)** | **🔴 ROT — return → if/else** | **V3 + T7 verifiziert per Source-Inspektion** |
| F6 (Frage 6) | 🟢 Edge-Cases OK | dokumentiert |
| F7 (Frage 7) | 🟢 KISS-Konstante OK | unverändert |
| F8 (Frage 8) | 🟡 6 weitere Tests | T7/T11/T12 priorisiert eingebaut |

## Implementierung (Diff)

- **`ui/mw_cycle.py`** Modul-Top: Konstante `_RECENTLY_COMPLETED_BLOCK_S = 60.0`
- **`ui/mw_cycle.py:on_message_decoded`** Z. 776 — `if not self._p128_recently_completed_block(...)`-Branch um add_rx
- **`ui/mw_cycle.py`** neue Methode `_p128_recently_completed_block` nach `_p124_resolve_hash_if_active_qso`
- **`ui/main_window.py`** Z. 287 — `_recently_completed_qsos: dict[str, float] = {}`
- **`ui/mw_qso.py:_on_qso_complete`** — Set-Pfad nach `_active_qso_targets.discard`
- **`ui/mw_qso.py:_on_station_clicked`** Z. 239 — `.pop(msg.caller, None)` für Re-Klick-Reset
- **`ui/mw_radio.py:_on_band_changed`** + **`_on_mode_changed`** — `.clear()` bei Wechsel
- **`tests/test_p128_recently_completed_block.py`** — 14 Tests (T1-T12)

Tests: 1867 → 1881 (+14), alle grün.

## Was du prüfen sollst

1. **ACs AC1-AC10 abgedeckt?**
2. **Race-Conditions?** `_recently_completed_qsos` wird vom GUI-Thread
   gesetzt (in `_on_qso_complete`) und gelesen (in `on_message_decoded`).
   Beide laufen im GUI-Thread (Qt-Slots) → keine Thread-Safety nötig.
3. **Memory-Leak?** Lazy-Aging im Filter — wenn Station NIE wieder
   gehört, bleibt Eintrag bis Bandwechsel. Akzeptabel?
4. **P124-Interaktion korrekt?** T12 verifiziert per Source-Inspektion
   dass `_p124_resolve_hash_if_active_qso` VOR `_p128_recently_completed_block`
   läuft. Reicht das oder echter Mock-Test nötig?
5. **Hardware-Sicherheit unverändert?** Kein TX-Pfad berührt.
6. **Backward-Compat?** 1867 → 1881 grün, 0 Regression.
7. **R1-F5 ROT-Fix korrekt umgesetzt?** Code-Inspektion ja, aber
   double-check: `if not self._p128_recently_completed_block(msg.caller):`
   umschließt NUR den add_rx-Block, alles danach (Quick73, OMNI,
   on_message_received) läuft unverändert.

## Verdict erwartet

PUSH FREIGEGEBEN / NACHBESSERN / BLOCK
