"""Tests fuer get_conditions_at(minutes_ahead) — Trend-Lookahead."""
from datetime import datetime, timezone

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
