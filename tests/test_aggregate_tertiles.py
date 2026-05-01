"""Tests fuer scripts.generate_plots._aggregate Tertile-Analyse (Feature H v0.84).

Pure-Logic-Tests — kein Plot-Rendering, kein File-IO.
"""
import sys
from pathlib import Path

PROJ = Path(__file__).parent.parent
sys.path.insert(0, str(PROJ))


def test_aggregate_tertiles_basic():
    """12 Cycles [1..12] → t33=4.667, t67=8.333, pooled_mean=6.5.

    Verifiziert dass _aggregate die statistics.quantiles(n=3, inclusive)
    korrekt fuer min/max-Schluessel verwendet.
    """
    from scripts.generate_plots import _aggregate
    hour_stats = {
        12: {
            "cycles": list(range(1, 13)),
            "daily": {"2026-05-01": list(range(1, 13))},
            "minutes": set(range(60)),
        }
    }
    result = _aggregate(hour_stats)
    assert 12 in result
    h12 = result[12]
    assert h12["mean"] == 6.5
    # Tertile inclusive: t33=4.667, t67=8.333
    assert abs(h12["min"] - 4.6666666) < 0.01, (
        f"t33 erwartet ~4.667, war {h12['min']}"
    )
    assert abs(h12["max"] - 8.3333333) < 0.01, (
        f"t67 erwartet ~8.333, war {h12['max']}"
    )
    assert h12["n_cycles"] == 12
    assert h12["n_days"] == 1


def test_aggregate_tertiles_fallback_under_3():
    """< 3 Cycles → t33 = t67 = pooled_mean (Fallback gegen StatisticsError)."""
    from scripts.generate_plots import _aggregate
    hour_stats = {
        12: {
            "cycles": [10, 20],
            "daily": {"2026-05-01": [10, 20]},
            "minutes": {0, 30},
        }
    }
    result = _aggregate(hour_stats)
    h12 = result[12]
    assert h12["mean"] == 15.0
    assert h12["min"] == 15.0
    assert h12["max"] == 15.0


def test_aggregate_tertiles_zero_cycles_skipped():
    """0 Cycles → Stunde wird im Output uebersprungen."""
    from scripts.generate_plots import _aggregate
    hour_stats = {
        12: {"cycles": [], "daily": {}, "minutes": set()},
        13: {
            "cycles": [5, 5, 5],
            "daily": {"2026-05-01": [5, 5, 5]},
            "minutes": {0},
        },
    }
    result = _aggregate(hour_stats)
    assert 12 not in result, "leere Stunde muss uebersprungen werden"
    assert 13 in result
    h13 = result[13]
    assert h13["mean"] == 5.0
    # Alle Werte gleich → Tertile sind auch alle gleich 5
    assert h13["min"] == 5.0
    assert h13["max"] == 5.0


def test_aggregate_tertiles_multiday():
    """Mehrere Tage → n_days korrekt aus daily-Dict."""
    from scripts.generate_plots import _aggregate
    hour_stats = {
        10: {
            "cycles": [10, 20, 30, 40, 50, 60],
            "daily": {
                "2026-04-30": [10, 20, 30],
                "2026-05-01": [40, 50, 60],
            },
            "minutes": set(range(60)),
        }
    }
    result = _aggregate(hour_stats)
    h10 = result[10]
    assert h10["n_days"] == 2
    assert h10["mean"] == 35.0
    # Tertile [10..60] inclusive: t33=26.67, t67=43.33
    assert 25.0 < h10["min"] < 28.0, f"t33 war {h10['min']}"
    assert 42.0 < h10["max"] < 45.0, f"t67 war {h10['max']}"
