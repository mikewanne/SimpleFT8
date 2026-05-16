"""P45 Stats-Guard für OMNI-CQ (v0.97.9, Mai 2026).

Testet dass _log_stats blockiert wenn OMNI-CQ aktiv ist.
Vorher: OMNI war nicht im Guard → Stats wurden während OMNI-RX-Slots
weiter geloggt, was die Statistik verfälschte (anderes Antennen-Pattern,
TX-Slots fehlen).

R1-bestätigt: OMNI-Guard MUSS unabhängig von _qsm sein (sehr seltener
Fall: _qsm fehlt, _omni_cq aktiv → ohne unabhängigen Block würde der
Guard übersprungen).
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
    from ui.mw_cycle import CycleMixin
    from core.qso_state import QSOState

    obj = CycleMixin.__new__(CycleMixin)

    # Stats-Logger Mock
    obj._stats_logger = MagicMock()

    # qso_sm Mock — default IDLE + nicht cq
    obj.qso_sm = MagicMock()
    obj.qso_sm.state = QSOState.IDLE
    obj.qso_sm.cq_mode = False

    # control_panel + btn_cq Mock — Default nicht checked
    obj.control_panel = MagicMock()
    obj.control_panel.btn_cq.isChecked.return_value = False

    # settings Mock — Band+Mode in LOGGED_BANDS/MODES
    obj.settings = MagicMock()
    obj.settings.band = "20m"
    obj.settings.mode = "FT8"
    obj.settings.get = MagicMock(return_value=True)  # generic settings.get returns True (stats_enabled-Guard wurde in P52 v0.97.41 entfernt)

    # _stats_warmup_cycles = 0 → kein Warmup-Block
    obj._stats_warmup_cycles = 0

    # _rx_mode + radio.ip + _dx_tune_dialog + _diversity_ctrl
    obj._rx_mode = "normal"
    obj.radio = MagicMock()
    obj.radio.ip = "192.168.1.68"
    obj._dx_tune_dialog = None
    obj._diversity_ctrl = MagicMock()
    obj._diversity_ctrl.scoring_mode = "normal"

    # _stats_indicator (None → kein UI-Update nötig)
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
    """Mw-Cycle ohne _omni_cq-Attribut → kein AttributeError, normal weiter."""
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
