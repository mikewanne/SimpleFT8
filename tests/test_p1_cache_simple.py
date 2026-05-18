"""Tests fuer P1.CACHE-SIMPLE — Gain-Cache-Branching.

P34-Stufe2 (v0.97.19): Ratio-Cache-Logik entfernt (Dynamic ist live).
Nur noch Gain-Cache-Branching in `_check_diversity_preset`.

Logik in `_check_diversity_preset` Dispatch:
- Gain fresh  → `_enable_diversity(scoring)` direkt (Dynamic startet)
- Gain stale/missing → DXTuneDialog (Gain-Mess), nach OK `_enable_diversity`

Whitebox-Tests via Mock-Self.
"""

import os
import sys
import time
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


# ── Mock-Helper ───────────────────────────────────────────────────────────


def _make_store_mock(*, gain_valid=True, has_gain_timestamp=True,
                     gain_age_offset_sec=600, ant2_calibrated=True):
    """P80: unified store mock — band-only API, ant2_calibrated-Feld."""
    store = MagicMock()
    store.is_valid_gain = MagicMock(return_value=gain_valid)
    store.get_gain_age_minutes = MagicMock(
        return_value=int(gain_age_offset_sec / 60))
    entry = {}
    if has_gain_timestamp:
        entry["gain_timestamp"] = time.time() - gain_age_offset_sec
        entry["ant2_calibrated"] = ant2_calibrated
    store.get = MagicMock(return_value=(entry or None))
    return store


def _make_mw_self(*, store=None, scoring="normal", radio_ip="192.168.1.10",
                  rx_mode="diversity"):
    """P80: 1 Store (_gain_store) statt 2."""
    from ui.mw_radio import RadioMixin

    fake_self = MagicMock()
    fake_self.radio = MagicMock()
    fake_self.radio.ip = radio_ip
    fake_self.settings = MagicMock()
    fake_self.settings.band = "40m"
    fake_self.settings.mode = "FT8"
    fake_self._rx_mode = rx_mode
    fake_self._swr_blocked_bands = set()

    # P80: 1 unified Store
    fake_self._gain_store = store if store else MagicMock()
    if store is None:
        fake_self._gain_store.is_valid_gain = MagicMock(return_value=False)
        fake_self._gain_store.get = MagicMock(return_value=None)

    fake_self._assess_gain = lambda b: RadioMixin._assess_gain(fake_self, b)

    fake_self._diversity_ctrl = MagicMock()
    fake_self._diversity_ctrl.scoring_mode = scoring
    fake_self.encoder = MagicMock()
    fake_self.encoder.is_transmitting = False
    fake_self._pending_dx_diversity = False
    fake_self._pending_diversity_scoring = None
    fake_self.qso_panel = MagicMock()
    return fake_self


# ── _assess_gain Tests (P80: nur band) ───────────────────────────────


def test_assess_gain_fresh_stale_missing():
    from ui.mw_radio import RadioMixin

    fresh = _make_mw_self(store=_make_store_mock(gain_valid=True))
    assert RadioMixin._assess_gain(fresh, "40m") == "fresh"

    stale = _make_mw_self(store=_make_store_mock(
        gain_valid=False, has_gain_timestamp=True))
    assert RadioMixin._assess_gain(stale, "40m") == "stale"

    no_store = _make_mw_self(store=_make_store_mock(
        gain_valid=False, has_gain_timestamp=False))
    assert RadioMixin._assess_gain(no_store, "40m") == "missing"


# ── _check_diversity_preset Dispatch (P80: band + scoring) ───────────


def test_check_preset_dispatch_gain_fresh_calls_enable_diversity():
    """P80: Gain fresh + ant2_calibrated=True → _enable_diversity direkt."""
    from ui.mw_radio import RadioMixin

    fake_self = _make_mw_self(store=_make_store_mock(
        gain_valid=True, ant2_calibrated=True))
    fake_self._enable_diversity = MagicMock()
    fake_self._start_dx_tuning = MagicMock()
    fake_self._update_statusbar = MagicMock()

    RadioMixin._check_diversity_preset(fake_self, "40m", "normal")

    fake_self._enable_diversity.assert_called_once_with(scoring_mode="normal")
    fake_self._start_dx_tuning.assert_not_called()


def test_check_preset_dispatch_gain_stale_opens_dialog(monkeypatch):
    """P80: Gain stale → DXTuneDialog (P62 deferred via QTimer)."""
    from ui.mw_radio import RadioMixin

    fake_self = _make_mw_self(store=_make_store_mock(
        gain_valid=False, has_gain_timestamp=True))
    fake_self._enable_diversity = MagicMock()
    fake_self._start_dx_tuning = MagicMock()
    fake_self._update_statusbar = MagicMock()
    fake_self._set_gain_measure_lock = MagicMock()

    def fake_singleshot(msec, callback):
        callback()
    monkeypatch.setattr("PySide6.QtCore.QTimer.singleShot", fake_singleshot)

    RadioMixin._check_diversity_preset(fake_self, "40m", "normal")

    fake_self._start_dx_tuning.assert_called_once()
    fake_self._enable_diversity.assert_not_called()
    assert fake_self._pending_dx_diversity is True
    fake_self._set_gain_measure_lock.assert_called_with(True)


def test_check_preset_dispatch_gain_missing_opens_dialog(monkeypatch):
    """P80: Gain missing → DXTuneDialog."""
    from ui.mw_radio import RadioMixin

    fake_self = _make_mw_self(store=_make_store_mock(
        gain_valid=False, has_gain_timestamp=False))
    fake_self._enable_diversity = MagicMock()
    fake_self._start_dx_tuning = MagicMock()
    fake_self._update_statusbar = MagicMock()
    fake_self._set_gain_measure_lock = MagicMock()

    def fake_singleshot(msec, callback):
        callback()
    monkeypatch.setattr("PySide6.QtCore.QTimer.singleShot", fake_singleshot)

    RadioMixin._check_diversity_preset(fake_self, "40m", "normal")

    fake_self._start_dx_tuning.assert_called_once()
    fake_self._enable_diversity.assert_not_called()


def test_check_preset_skip_when_no_radio():
    from ui.mw_radio import RadioMixin

    fake_self = _make_mw_self(store=_make_store_mock(), radio_ip=None)
    fake_self._enable_diversity = MagicMock()
    fake_self._start_dx_tuning = MagicMock()

    RadioMixin._check_diversity_preset(fake_self, "40m", "normal")

    fake_self._enable_diversity.assert_not_called()
    fake_self._start_dx_tuning.assert_not_called()


def test_check_preset_dispatch_dx_scoring():
    from ui.mw_radio import RadioMixin

    fake_self = _make_mw_self(
        store=_make_store_mock(gain_valid=True), scoring="dx")
    fake_self._enable_diversity = MagicMock()
    fake_self._start_dx_tuning = MagicMock()
    fake_self._update_statusbar = MagicMock()

    RadioMixin._check_diversity_preset(fake_self, "40m", "dx")

    fake_self._enable_diversity.assert_called_once_with(scoring_mode="dx")
