# P44 Statusbar DT-Label V3 — Freigegeben (Compact-fest)

**Stand:** 13.05.2026, R1-Review von V2 ohne Kritik („Alle Änderungen
atomar und können mit den drei Diffs eingespielt werden").
**Tests aktuell:** 1160 grün
**Backup:** `Appsicherungen/2026-05-13_v0.97.9_vor_p44_dt_indicator/`

## Auftrag

Bug Z.1088-1094 in `ui/main_window.py`: `statusBar().setStyleSheet()`
färbt **gesamten** Statusbar-Text grün während DT-Korrektur statt nur
das DT-Stück. Fix: DT als eigenes Permanent-Widget rechts neben
`_stats_indicator`.

## Diffs (alle gegen v0.97.9 HEAD `0f5d23b` verifiziert)

### Diff 1 — `ui/main_window.py` `__init__` nach Z.461

Nach `self.statusBar().addPermanentWidget(self._stats_indicator)`:
```python
# DT-Korrektur-Indikator (permanentes Widget, rechts in Statusbar
# direkt neben _stats_indicator). Default grau, grün bei aktiver
# Mess-Phase. Konsistent zum Stats-Indikator-Pattern.
self._dt_indicator = _QLabel("DT: —")
self._dt_indicator.setStyleSheet(
    "color: #555; font-family: Menlo; font-size: 11px; padding: 0 6px;"
)
self.statusBar().addPermanentWidget(self._dt_indicator)
```

### Diff 2 — `_update_statusbar()` Z.1088-1094 ersetzen

Alter Block (`if dt_color != "#888": ...self.statusBar().setStyleSheet(...)
else: ...`) ersetzen durch:
```python
if hasattr(self, '_dt_indicator'):
    self._dt_indicator.setText(dt_text)
    self._dt_indicator.setStyleSheet(
        f"color: {dt_color}; font-family: Menlo; "
        f"font-size: 11px; padding: 0 6px;"
    )
```

### Diff 3 — Z.1134 `msg`-Aufbau

`{dt_text}` raus aus dem msg-String:
```python
# vorher: f"{mode_str}  |  {dt_text}{omni_str}{freq_str}{ap_str}"
# nachher:
f"{mode_str}{omni_str}{freq_str}{ap_str}"
```

## Tests `tests/test_p44_dt_indicator.py` NEU

QLabel-Pattern-Smoke-Tests (kein MainWindow-Init):
- `test_dt_indicator_pattern_initial_grey`
- `test_dt_indicator_correction_phase_green`

Tests-Count: 1160 → **1162**.

## Atomare Commits

C1 `ui/main_window.py` (3 Diffs)
C2 `tests/test_p44_dt_indicator.py` NEU
C3 APP_VERSION 0.97.9 → 0.97.10 + HISTORY + HANDOFF + CLAUDE + Plan-Files

## Rollback

```bash
cp "Appsicherungen/2026-05-13_v0.97.9_vor_p44_dt_indicator/main_window.py" ui/main_window.py
rm tests/test_p44_dt_indicator.py
```

V3 ist **lauffähig auch nach Compact**.
