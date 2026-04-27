"""Tests fuer get_conditions_at(minutes_ahead) — Trend-Lookahead.

Plus Tests fuer _ModeBandCard Pulsier-Logik (active_band, _pulse-State).
"""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from datetime import datetime, timezone

import pytest

from core import propagation


def test_get_conditions_at_zero_equals_now():
    """get_conditions_at(0) und get_conditions() liefern identisches Ergebnis."""
    a = propagation.get_conditions_at(0)
    b = propagation.get_conditions()
    assert a == b  # beide None oder beide gleiches Dict


def test_get_conditions_at_returns_none_without_cache(monkeypatch):
    """Leerer _raw_data Cache → None."""
    monkeypatch.setattr(propagation, "_raw_data", None)
    assert propagation.get_conditions_at(0) is None
    assert propagation.get_conditions_at(60) is None


class _FakeDatetime:
    """Fake datetime.now() ohne real-time Drift im Test."""
    _now: datetime = datetime(2026, 1, 15, 13, 30, tzinfo=timezone.utc)

    @classmethod
    def now(cls, tz=None):
        return cls._now


def test_get_conditions_at_60min_band_opens(monkeypatch):
    """40m Winter open_h=14: bei now=13:30 UTC ist Band zu, in 60 min auf."""
    raw = {b: {"day": "good", "night": "good"} for b in propagation.ALL_BANDS}
    monkeypatch.setattr(propagation, "_raw_data", raw)
    monkeypatch.setattr(propagation, "datetime", _FakeDatetime)

    cond_now = propagation.get_conditions_at(0)
    cond_60  = propagation.get_conditions_at(60)
    assert cond_now is not None and cond_60 is not None
    # 13:30 UTC, January, 40m: open_h=14 → noch zu → poor
    assert cond_now["40m"] == "poor"
    # +60 min = 14:30 UTC → 40m offen → HamQSL-Wert "good"
    assert cond_60["40m"] == "good"


# ─────────────────────────────────────────────────────────────────────────
# Pulsier-Logik in _ModeBandCard
# ─────────────────────────────────────────────────────────────────────────

@pytest.fixture
def qapp():
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app


def test_pulse_started_only_for_active_band(qapp, monkeypatch):
    """Nur das aktive Band bekommt eine laufende Animation."""
    from PySide6.QtCore import QAbstractAnimation
    from ui.control_panel import _ModeBandCard

    # 40m: cond_now=good, cond_30=poor, cond_60=poor → Trend → animieren
    # 20m: cond_now=poor, cond_30=good, cond_60=good → Trend → wuerde
    #      animiert, ist aber nicht active_band
    def fake_at(minutes):
        if minutes == 0:
            return {"40m": "good", "20m": "poor"}
        return {"40m": "poor", "20m": "good"}  # 30 und 60 zeigen Trend

    monkeypatch.setattr(propagation, "get_conditions_at", fake_at)

    card = _ModeBandCard()
    card.update_propagation({"40m": "good", "20m": "poor"}, active_band="40m")

    assert "40m" in card._pulse, "active band sollte pulsieren"
    assert card._pulse["40m"]["anim"].state() == QAbstractAnimation.State.Running
    assert "20m" not in card._pulse, "non-active band darf nicht pulsieren"


def test_no_pulse_when_trend_equals_now(qapp, monkeypatch):
    """Aktives Band ohne Trend (cond_now == cond_60) → keine Animation."""
    from ui.control_panel import _ModeBandCard

    def fake_at(minutes):
        return {"40m": "good"}  # alle Zeitpunkte gleich → kein Trend

    monkeypatch.setattr(propagation, "get_conditions_at", fake_at)

    card = _ModeBandCard()
    card.update_propagation({"40m": "good"}, active_band="40m")

    assert "40m" not in card._pulse, "kein Trend → keine Animation"
