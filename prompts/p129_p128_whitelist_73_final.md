# Final-R1 — P129 P128-Whitelist 73/RR73 (committeter Code)

## Implementation

`ui/mw_cycle.py:_p128_recently_completed_block`:
- +Optional-Param `msg: FT8Message | None = None`
- Whitelist `if msg is not None and (msg.is_73 or msg.is_rr73): return False` als ERSTE Zeile
- Sonstiger Code unverändert

Call-Site `on_message_decoded` Z. 797:
- `if not self._p128_recently_completed_block(msg.caller, msg):` (+msg)

`tests/test_p129_whitelist_73.py` — 12 Tests:
- T1-T2: 73 + RR73 durchgelassen
- T3-T4b: R-Report, Plain Report, Grid weiter geblockt
- T5: msg=None Default backward-compat
- T6-T6b: Andere Stationen (nicht im Cooldown) — Bypass
- T7: Aging-Pfad unverändert
- T7b: Whitelist short-circuit
- T8: Source-Inspektion Call-Site
- T9: Funktion-Signatur Optional-Param

`tests/test_p128_recently_completed_block.py:t7` — 1 String-Match angepasst (P128-Test prüfte `(msg.caller)` strikt, jetzt `(msg.caller` ohne Klammer-Ende).

Tests 1894 → 1906 (+12 P129 + 0 netto P128-Anpassung). Full-Regression grün.

R1-Pre-Code: GO direkt, „exzellent KISS, keine Findings".

## Verifikation

1. ACs AC1-AC7 alle abgedeckt?
2. KISS — Optional-Param mit Default, 1 Zeile Whitelist?
3. Backward-Compat — msg=None Default, alte P128-Tests grün (1 String-Match angepasst).
4. Race-Conditions — alles GUI-Thread, kein Problem.
5. P128-Funktion erhalten — R-Reports/Grids weiter geblockt (T3-T4b).
6. Mike-Field-Bug behoben — 73 von Gegenstation kommt jetzt durch.

## Verdict erwartet

PUSH FREIGEGEBEN / NACHBESSERN
