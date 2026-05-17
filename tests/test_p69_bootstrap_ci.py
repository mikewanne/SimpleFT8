"""Tests fuer P69 Block-Bootstrap-CI (scripts/bootstrap_ci.py).

12 Tests T1-T12 nach V3-Plan.
"""

import math
import sys
import time
from pathlib import Path

import pytest

# scripts/-Verzeichnis ins sys.path damit bootstrap_ci importierbar ist
_SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from bootstrap_ci import (  # noqa: E402
    blocks_from_hourly_stats,
    compute_bootstrap_ci_diff_pct,
    compute_mode_comparison_ci,
    format_ci_full,
    format_ci_short,
)


# ── Helper: Mock-Blöcke konstruieren ──────────────────────────────────────


def _const_blocks(n_blocks: int, cycles_per_block: int, value: float) -> list[list[float]]:
    """n_blocks Bloecke, jeder mit cycles_per_block identischen value-Cycles."""
    return [[value] * cycles_per_block for _ in range(n_blocks)]


def _uniform_blocks(
    n_blocks: int, cycles_per_block: int, center: float, spread: float, seed: int
) -> list[list[float]]:
    """n_blocks Bloecke mit gleichverteiltem Inhalt center±spread."""
    import random

    rng = random.Random(seed)
    return [
        [rng.uniform(center - spread, center + spread) for _ in range(cycles_per_block)]
        for _ in range(n_blocks)
    ]


# ── T1: Identische Bloecke -> CI eng um 0 ────────────────────────────────


def test_t1_identical_blocks_ci_around_zero():
    blocks = _uniform_blocks(30, 10, center=20.0, spread=5.0, seed=1)
    pt, lo, hi, flag = compute_bootstrap_ci_diff_pct(
        blocks, blocks, n_iter=1000, seed=42
    )
    assert flag == "ok"
    assert abs(pt) < 0.01, f"Punktschaetzer sollte exakt 0 sein, ist {pt}"
    # CI sollte 0 enthalten und nicht extrem breit sein
    assert lo <= 0 <= hi
    assert hi - lo < 50, f"CI-Breite {hi - lo} zu gross fuer identische Daten"


# ── T2: Konstante Werte -> deterministisches CI ─────────────────────────────


def test_t2_constant_values_deterministic_ci():
    blocks_n = _const_blocks(30, 5, value=10.0)
    blocks_c = _const_blocks(30, 5, value=20.0)
    pt, lo, hi, flag = compute_bootstrap_ci_diff_pct(
        blocks_n, blocks_c, n_iter=500, seed=42
    )
    assert flag == "ok"
    assert pt == pytest.approx(100.0, abs=0.001)
    # Jeder Resample gibt Mean 10 bzw. 20 -> CI degeneriert auf 100 %
    assert lo == pytest.approx(100.0, abs=0.001)
    assert hi == pytest.approx(100.0, abs=0.001)


# ── T3: Seed-Reproduzierbarkeit ─────────────────────────────────────────────


def test_t3_seed_reproducibility():
    blocks_n = _uniform_blocks(25, 5, center=10.0, spread=2.0, seed=10)
    blocks_c = _uniform_blocks(25, 5, center=15.0, spread=3.0, seed=20)
    r1 = compute_bootstrap_ci_diff_pct(blocks_n, blocks_c, n_iter=1000, seed=42)
    r2 = compute_bootstrap_ci_diff_pct(blocks_n, blocks_c, n_iter=1000, seed=42)
    assert r1 == r2, "Gleicher Seed muss identisches Ergebnis liefern"


# ── T4: Unterschiedlicher Seed -> leicht andere CI ─────────────────────────


def test_t4_different_seed_different_ci():
    blocks_n = _uniform_blocks(25, 5, center=10.0, spread=3.0, seed=10)
    blocks_c = _uniform_blocks(25, 5, center=15.0, spread=4.0, seed=20)
    r1 = compute_bootstrap_ci_diff_pct(blocks_n, blocks_c, n_iter=1000, seed=42)
    r2 = compute_bootstrap_ci_diff_pct(blocks_n, blocks_c, n_iter=1000, seed=99)
    # Punktschaetzer aus Originaldaten ist identisch
    assert r1[0] == r2[0]
    # CIs sollten unterscheidbar sein (sonst Bug)
    assert r1[1] != r2[1] or r1[2] != r2[2]


# ── T5: Fixture-Daten -> Punktschaetzer im CI ──────────────────────────────


def test_t5_fixture_data_pt_inside_ci():
    # Realistische Verteilung: normal ~20 ± 5, compare ~45 ± 8
    blocks_n = _uniform_blocks(30, 50, center=20.0, spread=5.0, seed=100)
    blocks_c = _uniform_blocks(30, 50, center=45.0, spread=8.0, seed=200)
    pt, lo, hi, flag = compute_bootstrap_ci_diff_pct(
        blocks_n, blocks_c, n_iter=2000, seed=42
    )
    assert flag == "ok"
    assert lo <= pt <= hi, f"Punktschaetzer {pt} nicht in CI [{lo}, {hi}]"
    # Erwartung: Punktschaetzer ungefaehr +125 % (45/20-1)*100
    assert 100.0 < pt < 150.0, f"Punktschaetzer {pt} unerwartet"


# ── T6: Leere Bloecke werden ignoriert ─────────────────────────────────────


def test_t6_empty_blocks_filtered():
    # 5 groups × 10 = 50 blocks, 3 non-empty per group → 30 non-empty
    blocks_n = [[10, 10, 10], [], [10, 10, 10], [], [10, 10]] * 10
    blocks_c = [[20, 20], [20, 20, 20], []] * 17  # 51 raw, 34 non-empty
    pt, lo, hi, flag = compute_bootstrap_ci_diff_pct(
        blocks_n, blocks_c, n_iter=500, seed=42
    )
    # 30 non-empty Normal blocks, 34 non-empty Compare blocks → min 30, "ok"
    assert flag == "ok"
    assert pt == pytest.approx(100.0, abs=0.1)


# ── T7: n_min < 15 -> "insufficient" ───────────────────────────────────────


def test_t7_insufficient_data():
    blocks_n = _const_blocks(10, 5, value=10.0)
    blocks_c = _const_blocks(10, 5, value=20.0)
    pt, lo, hi, flag = compute_bootstrap_ci_diff_pct(
        blocks_n, blocks_c, n_iter=500, seed=42
    )
    assert flag == "insufficient"
    assert math.isnan(pt)
    assert math.isnan(lo)
    assert math.isnan(hi)


# ── T8: 15 <= n_min < 25 -> "limited" ──────────────────────────────────────


def test_t8_limited_data():
    blocks_n = _const_blocks(20, 5, value=10.0)
    blocks_c = _const_blocks(20, 5, value=20.0)
    pt, lo, hi, flag = compute_bootstrap_ci_diff_pct(
        blocks_n, blocks_c, n_iter=500, seed=42
    )
    assert flag == "limited"
    assert pt == pytest.approx(100.0)


# ── T9: n_min >= 25 -> "ok" ────────────────────────────────────────────────


def test_t9_ok_data():
    blocks_n = _const_blocks(30, 5, value=10.0)
    blocks_c = _const_blocks(30, 5, value=20.0)
    pt, lo, hi, flag = compute_bootstrap_ci_diff_pct(
        blocks_n, blocks_c, n_iter=500, seed=42
    )
    assert flag == "ok"
    assert pt == pytest.approx(100.0)


# ── T10: F-DIV0 — Normal-Werte mit 0 ──────────────────────────────────────


def test_t10_div0_handled_gracefully():
    # Alle Normal-Werte sind 0, alle Compare > 0
    blocks_n = _const_blocks(30, 5, value=0.0)
    blocks_c = _const_blocks(30, 5, value=20.0)
    # Originaldaten: normal_mean == 0 -> sofort nan zurueck
    pt, lo, hi, flag = compute_bootstrap_ci_diff_pct(
        blocks_n, blocks_c, n_iter=500, seed=42
    )
    assert flag == "ok"  # Block-Count ist OK
    assert math.isnan(pt)
    assert math.isnan(lo)
    assert math.isnan(hi)


def test_t10b_div0_in_resample_recovered():
    # Mix: einige Normal-Blöcke 0, andere positiv
    blocks_n = (
        _const_blocks(15, 5, value=0.0)
        + _const_blocks(15, 5, value=10.0)
    )
    blocks_c = _const_blocks(30, 5, value=20.0)
    # Originaldaten: normal_mean = 5 -> kein DIV0 in Original
    pt, lo, hi, flag = compute_bootstrap_ci_diff_pct(
        blocks_n, blocks_c, n_iter=500, seed=42
    )
    # Punktschaetzer = (20-5)/5*100 = 300%
    assert flag == "ok"
    assert pt == pytest.approx(300.0, abs=0.1)


# ── T11: Performance < 2 s ─────────────────────────────────────────────────


def test_t11_performance_under_2s():
    blocks_n = _uniform_blocks(40, 200, center=20.0, spread=5.0, seed=1)
    blocks_c = _uniform_blocks(40, 200, center=45.0, spread=8.0, seed=2)
    t0 = time.perf_counter()
    compute_bootstrap_ci_diff_pct(blocks_n, blocks_c, n_iter=5000, seed=42)
    dur = time.perf_counter() - t0
    assert dur < 2.0, f"Bootstrap dauerte {dur:.2f} s, Ziel < 2.0 s"


# ── T12: compute_mode_comparison_ci mit Fake-loader ─────────────────────────


def test_t12_mode_comparison_ci_returns_dict():
    """Test mit injiziertem load_hourly_stats_fn (kein Filesystem-Zugriff)."""
    fake_data = {
        "Normal": {
            10: {"cycles": [10] * 50, "daily": {"2026-05-01": [10] * 25, "2026-05-02": [10] * 25}, "minutes": set()},
            11: {"cycles": [10] * 50, "daily": {"2026-05-01": [10] * 25, "2026-05-02": [10] * 25}, "minutes": set()},
        },
        "Diversity_Normal": {
            10: {"cycles": [20] * 50, "daily": {"2026-05-01": [20] * 25, "2026-05-02": [20] * 25}, "minutes": set()},
            11: {"cycles": [20] * 50, "daily": {"2026-05-01": [20] * 25, "2026-05-02": [20] * 25}, "minutes": set()},
        },
        "Diversity_Dx": {
            10: {"cycles": [15] * 50, "daily": {"2026-05-01": [15] * 25, "2026-05-02": [15] * 25}, "minutes": set()},
        },
    }

    # Diese Datensaetze haben pro Modus nur wenige (date, hour)-Bloecke ->
    # insufficient. Wir extrahieren mit blocks_from_hourly_stats und packen
    # eine ausreichende Menge hinzu.
    # Erweitere auf 30 Bloecke pro Modus:
    for mode in ("Normal", "Diversity_Normal", "Diversity_Dx"):
        value = {"Normal": 10, "Diversity_Normal": 20, "Diversity_Dx": 15}[mode]
        fake_data[mode] = {
            h: {
                "cycles": [value] * 10,
                "daily": {f"2026-05-{d:02d}": [value] * 10 for d in range(1, 11)},
                "minutes": set(),
            }
            for h in range(10, 13)
        }

    def fake_load(stats_dir, mode, band, protocol):
        return fake_data.get(mode, {})

    result = compute_mode_comparison_ci(
        Path("/dummy"), "40m", n_iter=500, load_hourly_stats_fn=fake_load
    )
    assert "Diversity_Normal" in result
    assert "Diversity_Dx" in result
    # Std: (20-10)/10*100 = +100%
    pt_std, _, _, flag_std = result["Diversity_Normal"]
    assert pt_std == pytest.approx(100.0)
    assert flag_std == "ok"
    # DX: (15-10)/10*100 = +50%
    pt_dx, _, _, flag_dx = result["Diversity_Dx"]
    assert pt_dx == pytest.approx(50.0)


# ── Format-Helpers ──────────────────────────────────────────────────────────


def test_format_ci_short_ok():
    # 141.4 statt 141.5 um Banker's-Rounding (round-half-to-even) zu vermeiden
    assert format_ci_short(126.3, 112.1, 141.4, "ok") == "+112\u2013+141%"


def test_format_ci_short_limited():
    assert format_ci_short(126.3, 112.1, 141.4, "limited") == "+112\u2013+141% (limited)"


def test_format_ci_short_insufficient():
    assert format_ci_short(math.nan, math.nan, math.nan, "insufficient") == "n/a"


def test_format_ci_short_negative():
    assert format_ci_short(-5.0, -8.0, -2.0, "ok") == "-8\u2013-2%"


def test_format_ci_full_ok():
    assert format_ci_full(126.3, 112.1, 141.4, "ok") == "+126% (95%-CI: +112% to +141%)"


def test_format_ci_full_insufficient():
    assert format_ci_full(math.nan, math.nan, math.nan, "insufficient") == "n/a (insufficient data)"


def test_blocks_from_hourly_stats():
    """Konvertierung von load_hourly_stats-Output zu Block-Liste."""
    hour_stats = {
        10: {"daily": {"2026-05-01": [1, 2, 3], "2026-05-02": [4, 5]}, "cycles": [], "minutes": set()},
        11: {"daily": {"2026-05-01": [6, 7]}, "cycles": [], "minutes": set()},
        12: {"daily": {}, "cycles": [], "minutes": set()},  # Leerer Tag -> ignoriert
    }
    blocks = blocks_from_hourly_stats(hour_stats)
    assert len(blocks) == 3
    # Blocks sollten alle Float-Listen sein
    all_vals = sorted([v for b in blocks for v in b])
    assert all_vals == [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0]
