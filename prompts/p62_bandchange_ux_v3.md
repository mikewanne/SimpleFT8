# P62 V3 (final) — keine Plan-Änderungen, Code direkt

R1 V4-pro „Push freigegeben (V3-Phase OK)" mit 0 KP. V3 = V2 unverändert
übernommen.

## Code-Plan umgesetzt

| Commit | Datei | Was |
|---|---|---|
| C1 | `ui/mw_radio.py:_check_diversity_preset` | Lock + Statusbar + QTimer.singleShot(1000, lambda) im stale/missing-Branch |
| C2 | `main.py` APP_VERSION 0.97.34 → 0.97.35 |
| C3 | `tests/test_p62_bandchange_ux.py` NEU 6 Tests T1-T6 |
| C4 | `tests/test_p1_cache_simple.py` 2 alte Tests angepasst (QTimer.singleShot gemockt) |
| C5 | Backup + Doku |

## Tests

6 neue P62 + 2 angepasste alte. **1306 grün** (1300 → 1306, +6 P62
netto: 6 neu, 2 angepasst).

## Final-R1 V4-pro „Push freigegeben." 0 KP

Alle 5 Pruefpunkte (Race/Lock-Release/Style/Coverage/ANT1) abgehakt.
Lock-Release via `_on_dx_tune_accepted`/`_on_dx_tune_rejected` ist
lueckenlos.
