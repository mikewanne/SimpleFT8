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
                     gain_age_offset_sec=600):
    """Erstellt Mock-Store mit konfiguriertem Verhalten fuer is_valid_gain+get."""
    store = MagicMock()
    store.is_valid_gain = MagicMock(return_value=gain_valid)
    store.get_gain_age_minutes = MagicMock(
        return_value=int(gain_age_offset_sec / 60))
    entry = {}
    if has_gain_timestamp:
        entry["gain_timestamp"] = time.time() - gain_age_offset_sec
    store.get = MagicMock(return_value=(entry or None))
    return store


def _make_mw_self(*, store=None, scoring="normal", radio_ip="192.168.1.10",
                  rx_mode="diversity"):
    """Erstellt Mock-self fuer RadioMixin-Methoden."""
    from ui.mw_radio import RadioMixin

    fake_self = MagicMock()
    fake_self.radio = MagicMock()
    fake_self.radio.ip = radio_ip
    fake_self.settings = MagicMock()
    fake_self.settings.band = "40m"
    fake_self.settings.mode = "FT8"
    fake_self._rx_mode = rx_mode

    # Stores setzen
    if scoring == "dx":
        fake_self._dx_store = store
        fake_self._standard_store = None
    else:
        fake_self._standard_store = store
        fake_self._dx_store = None

    # Echte Helper-Methoden
    fake_self._get_diversity_store = lambda s: (
        fake_self._dx_store if s == "dx" else fake_self._standard_store
    )
    fake_self._assess_gain = lambda b, m, s: RadioMixin._assess_gain(fake_self, b, m, s)

    # Diversity-Controller
    fake_self._diversity_ctrl = MagicMock()
    fake_self._diversity_ctrl.scoring_mode = scoring

    # Encoder + Pending-Flags
    fake_self.encoder = MagicMock()
    fake_self.encoder.is_transmitting = False
    fake_self._pending_dx_diversity = False
    fake_self._pending_diversity_scoring = None
    return fake_self


# ── _assess_gain Tests ────────────────────────────────────────────────


def test_assess_gain_fresh_stale_missing():
    from ui.mw_radio import RadioMixin

    fresh = _make_mw_self(store=_make_store_mock(gain_valid=True))
    assert RadioMixin._assess_gain(fresh, "40m", "FT8", "normal") == "fresh"

    stale = _make_mw_self(store=_make_store_mock(
        gain_valid=False, has_gain_timestamp=True))
    assert RadioMixin._assess_gain(stale, "40m", "FT8", "normal") == "stale"

    no_store = _make_mw_self(store=None)
    assert RadioMixin._assess_gain(no_store, "40m", "FT8", "normal") == "missing"

    empty = _make_mw_self(store=_make_store_mock(
        gain_valid=False, has_gain_timestamp=False))
    assert RadioMixin._assess_gain(empty, "40m", "FT8", "normal") == "missing"


# ── _check_diversity_preset Dispatch Tests (P34-Stufe2: 2 Branches) ─────


def test_check_preset_dispatch_gain_fresh_calls_enable_diversity():
    """P34-Stufe2: Gain fresh → _enable_diversity direkt, kein DXTuneDialog."""
    from ui.mw_radio import RadioMixin

    fake_self = _make_mw_self(store=_make_store_mock(gain_valid=True))
    fake_self._enable_diversity = MagicMock()
    fake_self._start_dx_tuning = MagicMock()
    fake_self._update_statusbar = MagicMock()

    RadioMixin._check_diversity_preset(fake_self, "40m", "FT8", "normal")

    fake_self._enable_diversity.assert_called_once_with(scoring_mode="normal")
    fake_self._start_dx_tuning.assert_not_called()


def test_check_preset_dispatch_gain_stale_opens_dialog(monkeypatch):
    """P34-Stufe2: Gain stale → DXTuneDialog (kein _enable_diversity sofort).

    P62 (v0.97.35): _start_dx_tuning ist jetzt deferred via QTimer.singleShot
    (1s Pause). Test mocked singleShot und führt den Callback aus.
    """
    from ui.mw_radio import RadioMixin

    fake_self = _make_mw_self(store=_make_store_mock(
        gain_valid=False, has_gain_timestamp=True))
    fake_self._enable_diversity = MagicMock()
    fake_self._start_dx_tuning = MagicMock()
    fake_self._update_statusbar = MagicMock()
    fake_self._set_gain_measure_lock = MagicMock()

    # P62: QTimer.singleShot mocken, Callback sofort ausführen
    def fake_singleshot(msec, callback):
        callback()
    monkeypatch.setattr("PySide6.QtCore.QTimer.singleShot", fake_singleshot)

    RadioMixin._check_diversity_preset(fake_self, "40m", "FT8", "normal")

    fake_self._start_dx_tuning.assert_called_once()
    fake_self._enable_diversity.assert_not_called()
    assert fake_self._pending_dx_diversity is True
    # P62: Lock vor Tune
    fake_self._set_gain_measure_lock.assert_called_with(True)


def test_check_preset_dispatch_gain_missing_opens_dialog(monkeypatch):
    """P34-Stufe2: Gain missing → DXTuneDialog (P62 deferred via QTimer)."""
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

    RadioMixin._check_diversity_preset(fake_self, "40m", "FT8", "normal")

    fake_self._start_dx_tuning.assert_called_once()
    fake_self._enable_diversity.assert_not_called()


def test_check_preset_skip_when_no_radio():
    """Ohne Radio kein Dispatch — Methode returnt sofort."""
    from ui.mw_radio import RadioMixin

    fake_self = _make_mw_self(store=_make_store_mock(), radio_ip=None)
    fake_self._enable_diversity = MagicMock()
    fake_self._start_dx_tuning = MagicMock()

    RadioMixin._check_diversity_preset(fake_self, "40m", "FT8", "normal")

    fake_self._enable_diversity.assert_not_called()
    fake_self._start_dx_tuning.assert_not_called()


def test_check_preset_dispatch_dx_scoring():
    """DX-Scoring: Store-Auswahl korrekt + Gain-Branch greift."""
    from ui.mw_radio import RadioMixin

    fake_self = _make_mw_self(
        store=_make_store_mock(gain_valid=True), scoring="dx")
    fake_self._enable_diversity = MagicMock()
    fake_self._start_dx_tuning = MagicMock()
    fake_self._update_statusbar = MagicMock()

    RadioMixin._check_diversity_preset(fake_self, "40m", "FT8", "dx")

    fake_self._enable_diversity.assert_called_once_with(scoring_mode="dx")
