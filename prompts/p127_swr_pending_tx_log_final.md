# Final-R1 — P127 Sende-Log bei SWR-Abbruch verwerfen (committeter Code)

## Was ich will

Final-Review. Severity (🔴/🟠/🟡/🟢). PUSH FREIGEGEBEN ja/nein. Knapp.

## Implementierung

In `ui/mw_tx.py:_on_swr_alarm` nach P60-F3-Block (Z. 740 alt):

```python
if hasattr(self, "_pending_station_click"):
    self._pending_station_click = None
# P127 (25.05.2026): pending deferred TX-Log-Eintrag verwerfen.
# [10-Zeilen-Kommentar...]
if hasattr(self, "_pending_tx_log"):
    self._pending_tx_log = None
```

8 Tests in `tests/test_p127_swr_pending_tx_log.py`:
- T1: Source-Inspektion fix ist drin
- T2: Position nach P60-F3 (Symmetrie)
- T3: hasattr-Guard
- T4: Hardware-Sicherheit (abort + ptt_off bleibt + Reihenfolge)
- T5: HALT-Pfad (_abort_active_tx) unberührt
- T6: Early-Return-Pfade unberührt
- T7: _on_tx_finished handhabt pending=None bereits
- T8: Doku-Marker P127 + 25.05.2026

Tests 1881 → 1889 (+8). Full-Regression grün (1889 total).

R1-Pre-Code Verdict: GO direkt, alle 7 Findings 🟢.

## Verifikation

1. ACs AC1-AC7 alle abgedeckt?
2. Race-Conditions? GUI-Thread sequenziell, kein Race.
3. Hardware-Sicherheit unverändert? Verifiziert per T4.
4. Backward-Compat? 1881 → 1889 grün.
5. Pattern-Familie: 5. Iteration P81/P122/P124/P128/**P127**.

## Verdict erwartet

PUSH FREIGEGEBEN / NACHBESSERN / BLOCK
