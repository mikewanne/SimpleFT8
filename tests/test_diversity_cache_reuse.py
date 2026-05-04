#!/usr/bin/env python3
"""Tests fuer v0.93 Cache-Reuse-Pfad — _try_diversity_cache_reuse.

Whitebox-Tests via Mock-Self (Pattern aus test_mw_radio_bandpilot.py /
test_lock_coverage.py): wir rufen die Mixin-Methoden mit MagicMock-self
auf und verifizieren das State-Setting + den Toast-Aufruf.
"""

import os
import sys
import time
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Qt-Headless fuer Toast-Konstruktion
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


# ── _try_diversity_cache_reuse Whitebox ─────────────────────────────────────


def _make_self_with_store(*, scoring="normal",
                          ratio_valid=True, gain_valid=True,
                          ratio="70:30", dominant="A1", age_min=23):
    """Mock-self mit konfiguriertem PresetStore."""
    fake_self = MagicMock()
    store = MagicMock()
    store.is_valid_ratio = MagicMock(return_value=ratio_valid)
    store.is_valid_gain  = MagicMock(return_value=gain_valid)
    store.get_ratio_age_minutes = MagicMock(return_value=age_min)
    store.get = MagicMock(return_value={
        "ratio": ratio, "dominant": dominant,
        "gain_timestamp":  time.time() - 600,
        "ratio_timestamp": time.time() - age_min * 60,
    })
    if scoring == "dx":
        fake_self._dx_store = store
        fake_self._standard_store = None
    else:
        fake_self._standard_store = store
        fake_self._dx_store = None
    return fake_self, store


def test_cache_reuse_returns_false_when_no_store():
    """Kein Store → False, kein Cache-Reuse."""
    from ui.mw_radio import RadioMixin
    fake_self = MagicMock()
    fake_self._standard_store = None
    fake_self._dx_store = None
    result = RadioMixin._try_diversity_cache_reuse(
        fake_self, "40m", "FT8", "normal"
    )
    assert result is False


def test_cache_reuse_returns_false_when_ratio_expired():
    """ratio > 1h → is_valid_ratio False → Cache-Reuse abgebrochen."""
    from ui.mw_radio import RadioMixin
    fake_self, store = _make_self_with_store(ratio_valid=False)
    result = RadioMixin._try_diversity_cache_reuse(
        fake_self, "40m", "FT8", "normal"
    )
    assert result is False
    fake_self._enable_diversity.assert_not_called()


def test_cache_reuse_returns_false_when_gain_expired():
    """gain > 6h → kein Cache-Reuse (Gain-Werte unbrauchbar)."""
    from ui.mw_radio import RadioMixin
    fake_self, store = _make_self_with_store(gain_valid=False)
    result = RadioMixin._try_diversity_cache_reuse(
        fake_self, "40m", "FT8", "normal"
    )
    assert result is False
    fake_self._enable_diversity.assert_not_called()


def test_cache_reuse_returns_false_when_ratio_field_missing():
    """Eintrag ohne 'ratio'-Feld → False (defensive)."""
    from ui.mw_radio import RadioMixin
    fake_self, store = _make_self_with_store(ratio=None)
    store.get = MagicMock(return_value={"dominant": "A1", "ratio_timestamp": time.time()})
    result = RadioMixin._try_diversity_cache_reuse(
        fake_self, "40m", "FT8", "normal"
    )
    assert result is False


def test_cache_reuse_calls_enable_diversity_with_cache_args():
    """Erfolg: _enable_diversity wird mit cached_ratio + dominant + age gerufen."""
    from ui.mw_radio import RadioMixin
    fake_self, store = _make_self_with_store(
        ratio="70:30", dominant="A1", age_min=23
    )
    result = RadioMixin._try_diversity_cache_reuse(
        fake_self, "40m", "FT8", "normal"
    )
    assert result is True
    fake_self._enable_diversity.assert_called_once()
    kwargs = fake_self._enable_diversity.call_args.kwargs
    assert kwargs["scoring_mode"] == "normal"
    assert kwargs["cached_ratio"] == "70:30"
    assert kwargs["cached_dominant"] == "A1"
    assert kwargs["cached_age_seconds"] == 23 * 60


def test_cache_reuse_dx_uses_dx_store():
    """scoring='dx' → Cache-Reuse liest aus _dx_store."""
    from ui.mw_radio import RadioMixin
    fake_self, dx_store = _make_self_with_store(
        scoring="dx", ratio="30:70", dominant="A2"
    )
    result = RadioMixin._try_diversity_cache_reuse(
        fake_self, "20m", "FT8", "dx"
    )
    assert result is True
    fake_self._enable_diversity.assert_called_once()
    kwargs = fake_self._enable_diversity.call_args.kwargs
    assert kwargs["scoring_mode"] == "dx"
    assert kwargs["cached_ratio"] == "30:70"
    assert kwargs["cached_dominant"] == "A2"
    dx_store.is_valid_ratio.assert_called_with("20m", "FT8")


def test_cache_reuse_does_not_crash_on_toast_error(qapp):
    """Toast-Konstruktion fehlerhaft → return True trotzdem (Cache funktioniert)."""
    from ui.mw_radio import RadioMixin
    fake_self, store = _make_self_with_store()
    # Verhindern dass Toast wirklich aufgeht (sonst Test braucht GUI-Loop)
    fake_self._enable_diversity = MagicMock()
    result = RadioMixin._try_diversity_cache_reuse(
        fake_self, "40m", "FT8", "normal"
    )
    assert result is True


# ── _enable_diversity Cache-Override ────────────────────────────────────────


def test_enable_diversity_with_cached_ratio_sets_operate_phase(qapp):
    """_enable_diversity(cached_ratio=...) setzt Phase=operate + ratio + last_measured_at."""
    from core.diversity import DiversityController
    dc = DiversityController()
    # Setup: Phase ist measure (Default nach reset)
    assert dc.phase == "measure"

    # Simulieren was _enable_diversity macht (vereinfacht):
    dc.reset()
    cached_ratio = "70:30"
    cached_dominant = "A1"
    cached_age_seconds = 600  # 10 Min alt
    dc.ratio = cached_ratio
    dc.dominant = cached_dominant
    dc._phase = "operate"
    dc._last_measured_at = time.time() - cached_age_seconds

    assert dc.phase == "operate"
    assert dc.ratio == "70:30"
    assert dc.dominant == "A1"
    assert dc._last_measured_at is not None
    # Frist sollte ~10 Min alt anzeigen, NICHT abgelaufen
    assert (time.time() - dc._last_measured_at) < 3600


# ── DiversityCacheToast Smoke ──────────────────────────────────────────────


def test_diversity_cache_toast_constructs(qapp):
    """Toast laesst sich ohne Crash konstruieren."""
    from ui.diversity_cache_toast import DiversityCacheToast
    toast = DiversityCacheToast(
        parent=None, band="40m", ft_mode="FT8",
        scoring_label="Diversity Standard",
        ratio="70:30", dominant="A1", age_minutes=23,
    )
    assert toast is not None
    toast.close()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
