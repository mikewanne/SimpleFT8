#!/usr/bin/env python3
"""Tests fuer v0.94 _resolve_hardware_antenna — RX-Panel zeigt waehrend
Phase 2 (DXTuneDialog) die echte Hardware-Antenne statt Diversity-Pattern.
"""

import os
import sys
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _make_self(*, dx_tune_dialog=None):
    fake_self = MagicMock()
    fake_self._dx_tune_dialog = dx_tune_dialog
    return fake_self


def _make_dialog(schedule, step):
    dlg = MagicMock()
    dlg._schedule = schedule
    dlg._step = step
    return dlg


def test_no_dialog_returns_default():
    """Kein Dialog → Default-Antenne aus Diversity-Pattern bleibt."""
    from ui.mw_cycle import CycleMixin
    fake_self = _make_self(dx_tune_dialog=None)
    assert CycleMixin._resolve_hardware_antenna(fake_self, "A1") == "A1"
    assert CycleMixin._resolve_hardware_antenna(fake_self, "A2") == "A2"


def test_dialog_ant1_returns_a1():
    """Dialog-Step ANT1 → 'A1' (kurze Form)."""
    from ui.mw_cycle import CycleMixin
    schedule = [("ANT1", 10), ("ANT2", 10), ("ANT1", 20), ("ANT2", 20)]
    dlg = _make_dialog(schedule, step=0)
    fake_self = _make_self(dx_tune_dialog=dlg)
    # Default A2 wird ueberschrieben durch Hardware-Antenne ANT1 → A1
    assert CycleMixin._resolve_hardware_antenna(fake_self, "A2") == "A1"


def test_dialog_ant2_returns_a2():
    """Dialog-Step ANT2 → 'A2'."""
    from ui.mw_cycle import CycleMixin
    schedule = [("ANT1", 10), ("ANT2", 10), ("ANT1", 20), ("ANT2", 20)]
    dlg = _make_dialog(schedule, step=1)
    fake_self = _make_self(dx_tune_dialog=dlg)
    assert CycleMixin._resolve_hardware_antenna(fake_self, "A1") == "A2"


def test_dialog_step_overflow_returns_default():
    """Step >= len(_schedule) → IndexError → Default-Fallback."""
    from ui.mw_cycle import CycleMixin
    schedule = [("ANT1", 10), ("ANT2", 10)]
    dlg = _make_dialog(schedule, step=10)  # ueberlaeuft
    fake_self = _make_self(dx_tune_dialog=dlg)
    assert CycleMixin._resolve_hardware_antenna(fake_self, "A1") == "A1"


def test_dialog_no_schedule_attr_returns_default():
    """Dialog ohne _schedule-Attribut → AttributeError → Default."""
    from ui.mw_cycle import CycleMixin
    dlg = MagicMock()
    del dlg._schedule  # Attribut entfernen
    fake_self = _make_self(dx_tune_dialog=dlg)
    assert CycleMixin._resolve_hardware_antenna(fake_self, "A1") == "A1"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
