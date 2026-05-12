# P45 Stats-Guard für OMNI-CQ — V3 (Compact-fest, freigegeben)

## Auftrag

`_log_stats` in `ui/mw_cycle.py` blockiert nicht wenn OMNI-CQ aktiv.
P45 fügt einen Guard für `_omni_cq.is_active()` ein. Im selben Block
wird der Stats-Indikator konsistent grau gesetzt (war bisher in
QSO/CQ-Pfad nicht angefasst).

## R1-Klarstellungen ggü V2

**K1 — Unabhängiger OMNI-Guard (R1-Empfehlung KRITISCH):**
V2 hatte OMNI als Teil der `if _qsm and (...)`-Bedingung. Wenn `_qsm`
fehlt aber `_omni_cq` aktiv → OMNI würde ignoriert (sehr selten, aber
möglich z.B. in frühen Init-Phasen). R1: OMNI als eigener Block.

**V3-Pattern:**
```python
_omni = getattr(self, '_omni_cq', None)
_omni_block = _omni is not None and _omni.is_active()
_qsm_block = (
    _qsm is not None
    and (_cq_ui or _qsm.cq_mode
         or _qsm.state not in (QSOState.IDLE, QSOState.TIMEOUT))
)
if _omni_block or _qsm_block:
    _lbl = getattr(self, '_stats_indicator', None)
    if _lbl:
        _lbl.setStyleSheet("color: #555; font-family: Menlo; font-size: 11px; padding: 0 6px;")
    return False
```

**K2 — Edge-Test OMNI+QSO gleichzeitig (R1-nice-to-have):**
T4 zusätzlich für Fall „OMNI aktiv UND QSO läuft" → False. Macht der
Pattern aktuell automatisch durch OR, aber expliziter Test schärft.

## Final-Diff `ui/mw_cycle.py:876-883`

Ersetze Block:
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

Durch:
```python
# CQ oder aktives QSO → pausieren (nur 1 Slot RX, Statistik wäre verzerrt)
# Robuster Check: State-Machine UND UI-Button — falls cq_mode durch Bug False ist.
# P45 (v0.97.9): OMNI-CQ läuft als separate State-Machine (core/omni_cq.py)
# und setzt qso_sm.cq_mode NIE → eigener Block, unabhängig von _qsm.
_qsm = getattr(self, 'qso_sm', None)
_cp = getattr(self, 'control_panel', None)
_cq_btn = getattr(_cp, 'btn_cq', None) if _cp else None
_cq_ui = _cq_btn is not None and _cq_btn.isChecked()
_omni = getattr(self, '_omni_cq', None)
_omni_block = _omni is not None and _omni.is_active()
_qsm_block = (
    _qsm is not None
    and (_cq_ui or _qsm.cq_mode
         or _qsm.state not in (QSOState.IDLE, QSOState.TIMEOUT))
)
if _omni_block or _qsm_block:
    _lbl = getattr(self, '_stats_indicator', None)
    if _lbl:
        _lbl.setStyleSheet("color: #555; font-family: Menlo; font-size: 11px; padding: 0 6px;")
    return False
```

## Tests (4 statt 3) — `tests/test_p45_omni_stats_guard.py` NEU

```python
"""P45 Stats-Guard für OMNI-CQ (v0.97.9).

Testet dass _log_stats blockiert wenn OMNI-CQ aktiv ist.
Vorher: OMNI war nicht im Guard → Stats wurden verfälscht.
"""
from __future__ import annotations

from unittest.mock import MagicMock
import pytest


class _OmniStub:
    """Minimaler Stub für _omni_cq mit is_active()-Methode."""
    def __init__(self, active: bool = False):
        self._active = active

    def is_active(self) -> bool:
        return self._active


@pytest.fixture
def cycle_mixin():
    """Liefert Mock-MwCycleMixin-Instanz mit allen für _log_stats nötigen Attributen."""
    from ui.mw_cycle import MwCycleMixin
    from core.qso_state import QSOState

    obj = MwCycleMixin.__new__(MwCycleMixin)

    # Stats-Logger Mock
    obj._stats_logger = MagicMock()

    # qso_sm Mock — default IDLE + nicht cq
    obj.qso_sm = MagicMock()
    obj.qso_sm.state = QSOState.IDLE
    obj.qso_sm.cq_mode = False

    # control_panel + btn_cq Mock
    obj.control_panel = MagicMock()
    obj.control_panel.btn_cq.isChecked.return_value = False

    # settings Mock — Band+Mode in LOGGED_BANDS/MODES
    obj.settings = MagicMock()
    obj.settings.band = "20m"
    obj.settings.mode = "FT8"
    obj.settings.get = MagicMock(return_value=True)  # stats_enabled

    # _stats_warmup_cycles = 0 → kein Warmup-Block
    obj._stats_warmup_cycles = 0

    # _rx_mode + radio.ip + _dx_tune_dialog + _diversity_ctrl
    obj._rx_mode = "normal"
    obj.radio = MagicMock()
    obj.radio.ip = "192.168.1.68"
    obj._dx_tune_dialog = None
    obj._diversity_ctrl = MagicMock()
    obj._diversity_ctrl.phase = "operate"
    obj._diversity_ctrl.scoring_mode = "normal"

    # _stats_indicator (None → kein UI-Update)
    obj._stats_indicator = None

    return obj


def test_omni_active_blocks_stats(cycle_mixin):
    """OMNI aktiv → _log_stats returnt False, log_cycle nie gerufen."""
    cycle_mixin._omni_cq = _OmniStub(active=True)
    result = cycle_mixin._log_stats(station_count=5, messages=[])
    assert result is False
    cycle_mixin._stats_logger.log_cycle.assert_not_called()


def test_omni_inactive_lets_stats_through(cycle_mixin):
    """OMNI inaktiv + alle anderen Guards passieren → Stats durch."""
    cycle_mixin._omni_cq = _OmniStub(active=False)
    result = cycle_mixin._log_stats(station_count=5, messages=[])
    assert result is True
    cycle_mixin._stats_logger.log_cycle.assert_called_once()


def test_no_omni_attribute_compat(cycle_mixin):
    """Mw-Cycle ohne _omni_cq-Attribut → kein AttributeError."""
    # Bewusst kein cycle_mixin._omni_cq setzen
    if hasattr(cycle_mixin, '_omni_cq'):
        delattr(cycle_mixin, '_omni_cq')
    result = cycle_mixin._log_stats(station_count=5, messages=[])
    # Sollte True sein (alle anderen Guards ok)
    assert result is True


def test_omni_and_qso_both_block(cycle_mixin):
    """OMNI aktiv UND QSO aktiv → Stats blockiert (R1-Edge-Case)."""
    from core.qso_state import QSOState
    cycle_mixin._omni_cq = _OmniStub(active=True)
    cycle_mixin.qso_sm.state = QSOState.WAIT_REPORT  # nicht IDLE/TIMEOUT
    result = cycle_mixin._log_stats(station_count=5, messages=[])
    assert result is False
    cycle_mixin._stats_logger.log_cycle.assert_not_called()
```

**Tests-Count:** 1156 → 1160 (+4 P45).

## Atomare Commits

**C1:** `ui/mw_cycle.py` (Guard-Erweiterung + Indikator-Grau)
**C2:** `tests/test_p45_omni_stats_guard.py` NEU
**C3:** APP_VERSION 0.97.8 → 0.97.9 + HISTORY + HANDOFF + CLAUDE-Header

## Backup vor Code

`Appsicherungen/2026-05-12_v0.97.8_vor_p45_omni_stats_guard/` (vor C1).

## Risiko

| Risiko | Wahrsch | Mitigation |
|---|---|---|
| Bestehende Tests rot | LOW | nur 1 Stelle verändert, Default-Pfad unverändert |
| `_omni_cq.is_active()` Exception | LOW | None-Check + try-implizit |
| Indikator-Grau-Erweiterung bricht UI | LOW | gleiches Pattern wie Warmup/Tuning |
| Race mit gerade pausierender OMNI | LOW | `is_active()` ist thread-safe Property-Read |

## Rollback

```bash
cp "Appsicherungen/2026-05-12_v0.97.8_vor_p45_omni_stats_guard/ui/mw_cycle.py" ui/mw_cycle.py
rm tests/test_p45_omni_stats_guard.py
```

## Compact-Festigkeit

Alle Zeilen-Refs gegen v0.97.8 HEAD `211d887`. V3 ist allein-lauffähig.
