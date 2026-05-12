# P45 Stats-Guard für OMNI-CQ — V2 (Self-Review)

## Lücken die V1 hatte

### L1 — Andere Stats-Pfade müssen NICHT separat gefixt werden ✓
V1-Frage 4 geklärt: Code-Analyse `ui/mw_cycle.py:511`:
```python
_stats_logged = self._log_stats(...)
if _stats_logged and comparisons:
    self._stats_logger.log_station_comparisons(...)
```
→ `log_station_comparisons` hängt explizit am Erfolg von `_log_stats`.
   Unser Fix dort blockt automatisch auch dieses Logging.

→ `log_antenna_qso` (mw_qso.py:474): läuft NACH QSO-Ende.
   OMNI ist während QSO pausiert (`_pause_omni_if_active`). Sauber.

**Bestätigt: 1 Fix-Stelle in `_log_stats` reicht.**

### L2 — Klärung Logik `is_active()` vs `is_paused()`
- `is_active()`: OMNI ist eingeschaltet (User hat Knopf gedrückt)
- `is_paused()`: OMNI ist eingeschaltet ABER gerade pausiert wegen QSO

Wenn OMNI paused: läuft QSO → QSO-State-Check greift bereits.
Wenn OMNI active nicht paused: rufende CQ-Slots → unser neuer Check
greift → Stats blockiert.
→ **Nur `is_active()` prüfen reicht.** Selbst während paused-QSO würde
unser Check feuern, aber QSO-Check greift VOR uns → kein Schaden.

### L3 — Test-Mock-Strategie konkretisiert
```python
class _OmniStub:
    def __init__(self, active=False): self._active = active
    def is_active(self): return self._active
```
+ Mock `qso_sm` mit state=IDLE, cq_mode=False.
+ Mock `control_panel.btn_cq` mit isChecked=False (existing pattern in
  tests).

### L4 — `_stats_indicator` Update bei OMNI-Block
V1 hat das nicht spezifiziert. Bei OMNI-aktiv-Block soll der Indikator
ebenfalls grau werden (wie bei den anderen Stats-Pausen-Pfaden).
**V2-Patch:** Nach `if _qsm and (...)` wenn return False, vorher den
Indikator grau setzen (analog Z.866-868 Warmup-Pfad).

Tatsächlich: aktuell setzt das `_qsm`-Check-Pfad den Indikator NICHT
grau. Das ist ein bestehender Inkonsistenz-Bug. **V2-Entscheidung:**
beim P45-Fix konsistent mit anderen Pfaden machen — Indikator grau.

### L5 — Edge-Case: `_omni_cq` Attribut fehlt
V1 hatte `getattr(self, '_omni_cq', None) is not None and ...` —
ausreichend. Bei Tests ohne `_omni_cq`: returnt False (kein Block).
Bestätigt korrekt.

### L6 — APP_VERSION + Doku
V1 vergessen. V2: APP_VERSION 0.97.8 → **0.97.9** (Bugfix-only bump).

## Final-Diff (V2)

`ui/mw_cycle.py:876-883`:
```python
# CQ oder aktives QSO → pausieren (nur 1 Slot RX, Statistik wäre verzerrt)
# Robuster Check: State-Machine UND UI-Button — falls cq_mode durch Bug False ist
# P45 (v0.97.9): OMNI-CQ läuft als separate State-Machine (core/omni_cq.py)
# und setzt qso_sm.cq_mode NIE → eigener Check über _omni_cq.is_active()
_qsm = getattr(self, 'qso_sm', None)
_cp = getattr(self, 'control_panel', None)
_cq_btn = getattr(_cp, 'btn_cq', None) if _cp else None
_cq_ui = _cq_btn is not None and _cq_btn.isChecked()
_omni = getattr(self, '_omni_cq', None)
_omni_active = _omni is not None and _omni.is_active()
if _qsm and (_cq_ui or _qsm.cq_mode or _omni_active
             or _qsm.state not in (QSOState.IDLE, QSOState.TIMEOUT)):
    _lbl = getattr(self, '_stats_indicator', None)
    if _lbl:
        _lbl.setStyleSheet("color: #555; font-family: Menlo; font-size: 11px; padding: 0 6px;")
    return False
```

## Tests (3 statt 2)

**T1 — OMNI aktiv blockt Stats:**
Mock-Setup mit `_omni_active=True`, qso_sm IDLE. Erwartet: `_log_stats`
returnt False. Stats-Logger wird nie aufgerufen.

**T2 — OMNI inaktiv läßt Stats durch:**
Mock-Setup mit `_omni_active=False`, qso_sm IDLE, cq_mode=False, btn_cq
nicht checked, Band in LOGGED_BANDS, kein Tuning, Warmup=0. Erwartet:
`_log_stats` returnt True. Stats-Logger wird genau einmal aufgerufen.

**T3 — `_omni_cq` Attribut fehlt (rückwärts-Kompatibilität):**
Mw_cycle-Instance ohne `_omni_cq`-Attribut → kein AttributeError →
returnt entsprechend (False wenn andere Checks blockieren, True sonst).
Sichert dass alte/Test-Instances ohne OMNI weiter funktionieren.

## Tests-Count

1156 → 1159 (+3 P45-Tests).

## Atomare Commits

**C1:** `ui/mw_cycle.py` (1 Zeile Diff + Indikator-Grau)
**C2:** `tests/test_p45_omni_stats_guard.py` NEU (3 Tests)
**C3:** APP_VERSION 0.97.8 → 0.97.9 + HISTORY + HANDOFF + CLAUDE-Header

## Compact-Festigkeit

Alle Zeilen-Refs gegen v0.97.8 HEAD `211d887` verifiziert. V2 ist
allein-lauffähig.

## Backup vor Code

`Appsicherungen/2026-05-12_v0.97.8_vor_p45_omni_stats_guard/` (vor C1).

## Was V3/Code-Schritt klären sollte

1. R1 sollte prüfen: ist die Indikator-Grau-Erweiterung in V2 (L4)
   konsistent mit anderen Stats-Pause-Pfaden oder über-engineered?
2. R1 sollte prüfen: gibt's andere Stats-Pfade (z.B. in andere Datei)
   die OMNI auch missen?
