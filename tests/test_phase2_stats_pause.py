#!/usr/bin/env python3
"""Tests fuer v0.94 Stats-Pause waehrend Phase 2 (DXTuneDialog).

Bug-Fix: ``_is_antenna_tuning_active`` muss True returnen wenn
``_dx_tune_dialog`` gesetzt ist — bis v0.93 wurde das nicht geprueft,
Stats wurden waehrend Gain-Messung mit verzerrten Antennen-Werten
geloggt.
"""

import os
import sys
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _make_self(*, dx_tune_dialog=None, rx_mode="diversity",
               div_phase="operate"):
    """Mock-self fuer Whitebox-Test von _is_antenna_tuning_active."""
    fake_self = MagicMock()
    fake_self.radio = MagicMock()
    fake_self.radio.ip = "192.168.1.68"  # Radio verbunden
    fake_self._rx_mode = rx_mode
    fake_self._dx_tune_dialog = dx_tune_dialog
    fake_self._diversity_ctrl = MagicMock()
    fake_self._diversity_ctrl.phase = div_phase
    return fake_self


def test_dx_tune_dialog_active_blocks_stats():
    """v0.94: Phase 2 laeuft → Stats blockiert."""
    from ui.mw_cycle import CycleMixin
    fake_self = _make_self(dx_tune_dialog=MagicMock())
    assert CycleMixin._is_antenna_tuning_active(fake_self) is True


def test_dx_tune_dialog_none_does_not_block():
    """Kein Dialog → Stats NICHT durch Dialog-Check blockiert."""
    from ui.mw_cycle import CycleMixin
    fake_self = _make_self(dx_tune_dialog=None)
    assert CycleMixin._is_antenna_tuning_active(fake_self) is False


def test_phase3_measure_still_blocks_stats():
    """Bestehender Schutz: Diversity Phase 3 measure blockt weiter."""
    from ui.mw_cycle import CycleMixin
    fake_self = _make_self(dx_tune_dialog=None, div_phase="measure")
    assert CycleMixin._is_antenna_tuning_active(fake_self) is True


def test_no_radio_blocks_stats():
    """Bestehender Schutz: kein Radio → Stats blockiert."""
    from ui.mw_cycle import CycleMixin
    fake_self = _make_self(dx_tune_dialog=None)
    fake_self.radio.ip = None
    assert CycleMixin._is_antenna_tuning_active(fake_self) is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
