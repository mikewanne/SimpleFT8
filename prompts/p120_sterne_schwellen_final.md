# Final-R1 — P120 Sterne-Schwellen FT8-realistisch (committeter Code)

## Implementierung

`ui/mw_cycle.py:compute_local_conditions` Z. 33-77 (P120-Schwellen + Docstring).
R1-Option-B Schwellen: 5★ > -13, 4★ > -18, 3★ > -21, 2★ > -22.

Mike-Spec war 5★ > -13, 4★ > -16, 3★ > -19. R1 fand Inkonsistenz:
Mike behauptet "-17 → 4★" aber mit > -16 wäre -17 noch 3★. R1-
Option-B löst das: 4★-Schwelle auf > -18 → Mike's Outcome erfüllt.

13 Tests in test_local_conditions.py:
- 9 alte (2 mit neuen SNR-Werten: 4★ jetzt -14 statt -12, 3★ jetzt -19 statt -16, 2★ jetzt -21.5 statt -20)
- 4 neue P120-Tests: Mike-Field -17 → 4★, 4 Grenzfall-Tests (5/4, 4/3, 3/2, 2/1)

Tests 1889 → 1894 (+5 netto). Full-Regression grün.

## Verifikation

1. ACs aus R1-Option-B alle abgedeckt?
2. Mike's Field-Befund -17 → 4★ erfüllt? (T `test_p120_mike_field_test_minus17_is_4_stars` ✓)
3. Grenzfall-Tests vollständig? Alle 4 Schwellen-Übergänge.
4. Backward-Compat: Code-Pfade unverändert (nur Konstanten).
5. Hardware: kein Bezug.
6. Pattern: alle Schwellen `>` (homogener Code-Style).

## Verdict erwartet

PUSH FREIGEGEBEN / NACHBESSERN
