# P45 Stats-Guard für OMNI-CQ — V1

## Auftrag

`ui/mw_cycle.py:_log_stats` (Z.840-905) blockiert Statistik-Logging
korrekt bei manuellem CQ, aktivem QSO, Antennen-Tuning, Warmup. ABER:
**OMNI-CQ wird nicht erkannt** — es ist eine separate State-Machine in
`core/omni_cq.py` und setzt nie `qso_sm.cq_mode=True`.

→ Bug: Wenn OMNI-CQ aktiv ist und kein QSO läuft, schreibt die App
weiter Stats. Das verfälscht die Statistik (OMNI-RX-Slots haben anderes
Antennen-Pattern als regulärer RX, TX-Slots fehlen → Pattern-Bias).

## Code-Verifikation (Stand v0.97.8 + DIAG-Code)

**`ui/mw_cycle.py` Z.876-883:**
```python
# CQ oder aktives QSO → pausieren (nur 1 Slot RX, Statistik wäre verzerrt)
# Robuster Check: State-Machine UND UI-Button — falls cq_mode durch Bug False ist
_qsm = getattr(self, 'qso_sm', None)
_cp = getattr(self, 'control_panel', None)
_cq_btn = getattr(_cp, 'btn_cq', None) if _cp else None
_cq_ui = _cq_btn is not None and _cq_btn.isChecked()
if _qsm and (_cq_ui or _qsm.cq_mode or _qsm.state not in (QSOState.IDLE, QSOState.TIMEOUT)):
    return False
```

`_omni_cq.is_active()` wird hier **nicht abgefragt**.

**`core/omni_cq.py` confirmed:** kein `cq_mode` oder `start_cq` Aufruf
in der ganzen Datei (grep ergab 0 Treffer).

## Akzeptanzkriterien

**AC1 — OMNI-CQ blockiert Stats-Logging:**
Wenn `self._omni_cq.is_active() == True`, dann `_log_stats` returnt
False. Indikator wird grau (kein "geloggt"-Status).

**AC2 — Existierende Checks bleiben unverändert:**
`_cq_ui`, `qso_sm.cq_mode`, `qso_sm.state not in (IDLE, TIMEOUT)`
funktionieren wie bisher.

**AC3 — Robuster Check (analog Original):**
`getattr(self, '_omni_cq', None)` damit Tests/Mocks ohne `_omni_cq`-
Attribut nicht crashen.

**AC4 — OMNI-CQ pausiert:**
Wenn OMNI gerade pausiert ist (`_omni_cq.is_paused() == True`), greift
das **vorhandene** QSO-Logik (Mike führt gerade QSO mit OMNI-Anrufer).
Der QSO-State-Check fängt das schon ab — kein zusätzlicher Code nötig.

**AC5 — 2 neue Tests:**
- T1: OMNI aktiv → Stats blockiert
- T2: OMNI inaktiv → Stats laufen (sofern andere Checks passen)

**AC6 — Bestehende Tests grün:**
1156 → 1158 (+2 P45-Tests).

## Implementierung (1 Zeile Diff)

`ui/mw_cycle.py:882`:
```python
_omni_active = (
    getattr(self, '_omni_cq', None) is not None
    and self._omni_cq.is_active()
)
if _qsm and (_cq_ui or _qsm.cq_mode or _omni_active
             or _qsm.state not in (QSOState.IDLE, QSOState.TIMEOUT)):
    return False
```

## Files

- **Modified:** `ui/mw_cycle.py` (1 Zeile + Helper-Variable)
- **New:** `tests/test_p45_omni_stats_guard.py` (2 Tests)

## Tests-Strategie

Mock `_omni_cq` mit Stub-`is_active()`. Mock `qso_sm` mit IDLE state.
Erwarte `_log_stats(...)` returnt False wenn OMNI aktiv, True wenn nicht
(unter sonst gleichen Bedingungen).

## Compact-Festigkeit

Alle Zeilen-Refs gegen `core/decoder.py` v0.97.8 (HEAD `211d887`)
verifiziert. Plan ist allein-lauffähig auch nach Compact.

## Risiko-Bewertung

| Risiko | Wahrsch | Mitigation |
|---|---|---|
| `_omni_cq.is_active()` wirft Exception | LOW | `getattr` + None-Check |
| Bestehende Tests rot | LOW | Test mit fehlendem `_omni_cq` muss nach wie vor funktionieren |
| Stats-Logging blockiert komplett (false-positive) | LOW | `is_active()` returnt False wenn OMNI nicht aktiv (default) |

## Was V2/R1 prüfen sollen

1. Reicht 1 Zeile-Erweiterung oder fehlt was Konzeptionelles?
2. Test-Mock-Pattern korrekt?
3. Wann `is_active() vs is_paused()` Edge-Cases — übersehen wir was?
4. Existieren weitere Statistik-Pfade die OMNI auch blockieren müssen?
   (z.B. `log_antenna_qso`, `log_station_comparison`)
