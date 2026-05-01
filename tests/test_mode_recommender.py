"""Tests fuer core/mode_recommender.py — Bandpilot RX-Modus-Empfehlung.

Deckt ab:
- _parse_stats_file: Normal- und Diversity-Format, kaputte Zeilen
- _aggregate_mode: Tagesanzahl, Pooled Mean, Spotlight-Duplikate ignorieren
- aggregate_stats: alle drei Modi parallel
- recommend: MIN_DAYS / MIN_CYCLES Guards
- recommend: Normal gewinnt
- recommend: Diversity gewinnt mit diversity_pref auto/standard/dx
- BandpilotSummaryCache: TTL, invalidate, atomare Persistenz
- Bandpilot.recommend_for_band: End-to-End
"""

import json
import time
from pathlib import Path

import pytest

from core import mode_recommender as mr
from core.mode_recommender import (
    Bandpilot,
    BandpilotSummaryCache,
    MIN_CYCLES,
    MIN_DAYS,
    _aggregate_mode,
    _parse_stats_file,
    aggregate_stats,
    recommend,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

NORMAL_HEADER = (
    "# Statistik 2026-04-21 12:00-12:59 UTC | FT8 | 40m | Normal\n\n"
    "| Zeit | Stationen | Ø SNR |\n"
    "|------|-----------|-------|\n"
)
DIV_HEADER = (
    "# Statistik 2026-04-21 12:00-12:59 UTC | FT8 | 40m | Diversity_Normal\n\n"
    "| Zeit | Stationen | Ø SNR | Ant2 Wins | Ø ΔSNR |\n"
    "|------|-----------|-------|-----------|--------|\n"
)


def _write_normal_file(path: Path, counts: list[int]):
    """Erzeuge Normal-Stats-Datei mit gegebenen Stations-Counts."""
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [NORMAL_HEADER]
    for i, c in enumerate(counts):
        lines.append(f"| 12:{i:02d}:00 | {c} | -20 |\n")
    path.write_text("".join(lines), encoding="utf-8")


def _write_div_file(path: Path, counts: list[int]):
    """Erzeuge Diversity-Stats-Datei mit gegebenen Stations-Counts."""
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [DIV_HEADER]
    for i, c in enumerate(counts):
        lines.append(f"| 12:{i:02d}:00 | {c} | -20 | 2 | -1.5 |\n")
    path.write_text("".join(lines), encoding="utf-8")


def _build_band_stats(
    base: Path,
    band: str,
    *,
    normal_days: dict[str, list[int]] | None = None,
    div_normal_days: dict[str, list[int]] | None = None,
    div_dx_days: dict[str, list[int]] | None = None,
):
    """Baue Stats-Verzeichnis mit Tag→Counts-Mapping pro Modus."""
    for mode, days_data, writer in (
        ("Normal", normal_days, _write_normal_file),
        ("Diversity_Normal", div_normal_days, _write_div_file),
        ("Diversity_Dx", div_dx_days, _write_div_file),
    ):
        if not days_data:
            continue
        mode_dir = base / mode / band / "FT8"
        for day, counts in days_data.items():
            writer(mode_dir / f"{day}_12.md", counts)


# ── _parse_stats_file ─────────────────────────────────────────────────────────

def test_parse_normal_file(tmp_path):
    path = tmp_path / "test.md"
    _write_normal_file(path, [5, 7, 10, 8])
    s, c = _parse_stats_file(path)
    assert c == 4
    assert s == 30


def test_parse_diversity_file(tmp_path):
    path = tmp_path / "test.md"
    _write_div_file(path, [12, 15, 20])
    s, c = _parse_stats_file(path)
    assert c == 3
    assert s == 47


def test_parse_skips_broken_lines(tmp_path):
    path = tmp_path / "broken.md"
    path.write_text(
        NORMAL_HEADER
        + "| 12:00:00 | 7 | -20 |\n"
        + "| ohne_zeit | 99 | -20 |\n"   # parts[0] keine Uhrzeit
        + "| 12:01:00 | x | -20 |\n"     # parts[1] keine Zahl
        + "| 12:02:00 | 3 | -20 |\n",
        encoding="utf-8",
    )
    s, c = _parse_stats_file(path)
    assert c == 2
    assert s == 10


def test_parse_missing_file_returns_zero(tmp_path):
    s, c = _parse_stats_file(tmp_path / "nope.md")
    assert (s, c) == (0, 0)


# ── _aggregate_mode ───────────────────────────────────────────────────────────

def test_aggregate_mode_empty(tmp_path):
    res = _aggregate_mode(tmp_path)
    assert res == {"days": 0, "cycles": 0, "mean": None}


def test_aggregate_mode_two_days(tmp_path):
    _write_normal_file(tmp_path / "2026-04-21_12.md", [4, 6])      # day 1: 10 / 2
    _write_normal_file(tmp_path / "2026-04-22_12.md", [10, 10, 10]) # day 2: 30 / 3
    res = _aggregate_mode(tmp_path)
    assert res["days"] == 2
    assert res["cycles"] == 5
    assert res["mean"] == pytest.approx(40 / 5)


def test_aggregate_mode_ignores_spotlight_duplicates(tmp_path):
    _write_normal_file(tmp_path / "2026-04-21_12.md", [10])
    _write_normal_file(tmp_path / "2026-04-21_12 2.md", [99])  # macOS-Artefakt
    _write_normal_file(tmp_path / "random_other.md", [99])     # nicht-matching
    res = _aggregate_mode(tmp_path)
    assert res["days"] == 1
    assert res["cycles"] == 1
    assert res["mean"] == 10.0


# ── aggregate_stats ───────────────────────────────────────────────────────────

def test_aggregate_stats_three_modes(tmp_path):
    _build_band_stats(
        tmp_path,
        "40m",
        normal_days={"2026-04-21": [10, 10], "2026-04-22": [10, 10, 10]},
        div_normal_days={"2026-04-21": [15, 15], "2026-04-22": [15, 15, 15]},
        div_dx_days={"2026-04-21": [12, 12], "2026-04-22": [12, 12, 12]},
    )
    res = aggregate_stats(tmp_path, "40m")
    assert res["Normal"]["days"] == 2
    assert res["Normal"]["mean"] == pytest.approx(10.0)
    assert res["Diversity_Normal"]["mean"] == pytest.approx(15.0)
    assert res["Diversity_Dx"]["mean"] == pytest.approx(12.0)


def test_aggregate_stats_missing_band(tmp_path):
    res = aggregate_stats(tmp_path, "20m")
    for mode in ("Normal", "Diversity_Normal", "Diversity_Dx"):
        assert res[mode] == {"days": 0, "cycles": 0, "mean": None}


# ── recommend: Guards ─────────────────────────────────────────────────────────

def _summary(n_days, n_cycles, n_mean,
             s_days, s_cycles, s_mean,
             d_days, d_cycles, d_mean):
    return {
        "Normal":           {"days": n_days, "cycles": n_cycles, "mean": n_mean},
        "Diversity_Normal": {"days": s_days, "cycles": s_cycles, "mean": s_mean},
        "Diversity_Dx":     {"days": d_days, "cycles": d_cycles, "mean": d_mean},
    }


def test_recommend_insufficient_days_returns_none():
    s = _summary(1, 999, 10.0, 5, 999, 15.0, 5, 999, 12.0)  # Normal hat nur 1 Tag
    assert recommend(s) is None


def test_recommend_insufficient_cycles_returns_none():
    s = _summary(5, MIN_CYCLES - 1, 10.0, 5, 999, 15.0, 5, 999, 12.0)
    assert recommend(s) is None


def test_recommend_none_mean_returns_none():
    s = _summary(5, 999, None, 5, 999, 15.0, 5, 999, 12.0)
    assert recommend(s) is None


# ── recommend: Entscheidungslogik ─────────────────────────────────────────────

def test_recommend_normal_wins():
    # Normal=20, (Div_S+Div_D)/2 = (15+12)/2 = 13.5 → Normal
    s = _summary(MIN_DAYS, MIN_CYCLES, 20.0,
                 MIN_DAYS, MIN_CYCLES, 15.0,
                 MIN_DAYS, MIN_CYCLES, 12.0)
    assert recommend(s) == "normal"


def test_recommend_diversity_auto_picks_standard():
    # Normal=10, (15+12)/2=13.5 → Diversity, auto: max(15,12)=15 → standard
    s = _summary(MIN_DAYS, MIN_CYCLES, 10.0,
                 MIN_DAYS, MIN_CYCLES, 15.0,
                 MIN_DAYS, MIN_CYCLES, 12.0)
    assert recommend(s, diversity_pref="auto") == "diversity_normal"


def test_recommend_diversity_auto_picks_dx():
    # Normal=10, (12+18)/2=15 → Diversity, auto: max(12,18)=18 → dx
    s = _summary(MIN_DAYS, MIN_CYCLES, 10.0,
                 MIN_DAYS, MIN_CYCLES, 12.0,
                 MIN_DAYS, MIN_CYCLES, 18.0)
    assert recommend(s, diversity_pref="auto") == "diversity_dx"


def test_recommend_diversity_pref_standard_forces_standard():
    # Auto wuerde dx waehlen (18>12), aber pref=standard zwingt diversity_normal
    s = _summary(MIN_DAYS, MIN_CYCLES, 10.0,
                 MIN_DAYS, MIN_CYCLES, 12.0,
                 MIN_DAYS, MIN_CYCLES, 18.0)
    assert recommend(s, diversity_pref="standard") == "diversity_normal"


def test_recommend_diversity_pref_dx_forces_dx():
    # Auto wuerde standard waehlen (18>12), aber pref=dx zwingt diversity_dx
    s = _summary(MIN_DAYS, MIN_CYCLES, 10.0,
                 MIN_DAYS, MIN_CYCLES, 18.0,
                 MIN_DAYS, MIN_CYCLES, 12.0)
    assert recommend(s, diversity_pref="dx") == "diversity_dx"


def test_recommend_normal_pref_ignored_when_normal_wins():
    # Normal gewinnt unabhaengig von diversity_pref
    s = _summary(MIN_DAYS, MIN_CYCLES, 100.0,
                 MIN_DAYS, MIN_CYCLES, 5.0,
                 MIN_DAYS, MIN_CYCLES, 5.0)
    assert recommend(s, diversity_pref="dx") == "normal"


# ── BandpilotSummaryCache ─────────────────────────────────────────────────────

def test_cache_set_and_get(tmp_path):
    cache = BandpilotSummaryCache(tmp_path / "cache.json")
    summary = {"Normal": {"days": 2, "cycles": 100, "mean": 10.0}}
    cache.set("40m", summary)
    assert cache.get("40m") == summary


def test_cache_ttl_expires(tmp_path):
    cache_path = tmp_path / "cache.json"
    cache = BandpilotSummaryCache(cache_path)
    cache.set("40m", {"x": 1})
    # Datei manipulieren: Timestamp 25h alt
    raw = json.loads(cache_path.read_text())
    raw["40m"]["ts"] = time.time() - 25 * 3600
    cache_path.write_text(json.dumps(raw))
    cache2 = BandpilotSummaryCache(cache_path)  # neu laden
    assert cache2.get("40m") is None


def test_cache_invalidate(tmp_path):
    cache = BandpilotSummaryCache(tmp_path / "cache.json")
    cache.set("40m", {"x": 1})
    cache.invalidate("40m")
    assert cache.get("40m") is None


def test_cache_corrupted_json_returns_empty(tmp_path):
    cache_path = tmp_path / "cache.json"
    cache_path.write_text("{ not valid json")
    cache = BandpilotSummaryCache(cache_path)
    assert cache.get("40m") is None


def test_cache_persists_across_instances(tmp_path):
    cache1 = BandpilotSummaryCache(tmp_path / "cache.json")
    cache1.set("40m", {"hello": "world"})
    cache2 = BandpilotSummaryCache(tmp_path / "cache.json")
    assert cache2.get("40m") == {"hello": "world"}


# ── Bandpilot End-to-End ──────────────────────────────────────────────────────

def test_bandpilot_recommend_for_band(tmp_path):
    stats = tmp_path / "stats"
    cache_path = tmp_path / "cache.json"
    _build_band_stats(
        stats,
        "40m",
        normal_days={
            "2026-04-21": [10] * 30, "2026-04-22": [10] * 30,
        },
        div_normal_days={
            "2026-04-21": [20] * 30, "2026-04-22": [20] * 30,
        },
        div_dx_days={
            "2026-04-21": [15] * 30, "2026-04-22": [15] * 30,
        },
    )
    bp = Bandpilot(stats_dir=stats, cache=BandpilotSummaryCache(cache_path))
    result = bp.recommend_for_band("40m")
    # Normal=10, (20+15)/2=17.5 → Diversity, auto: max(20,15)=20 → standard
    assert result == "diversity_normal"


def test_bandpilot_uses_cache_on_second_call(tmp_path):
    """Zweiter Call muss Cache verwenden — kein erneutes Aggregieren."""
    stats = tmp_path / "stats"
    cache_path = tmp_path / "cache.json"
    _build_band_stats(
        stats, "40m",
        normal_days={"2026-04-21": [5] * MIN_CYCLES, "2026-04-22": [5] * MIN_CYCLES},
        div_normal_days={"2026-04-21": [10] * MIN_CYCLES, "2026-04-22": [10] * MIN_CYCLES},
        div_dx_days={"2026-04-21": [10] * MIN_CYCLES, "2026-04-22": [10] * MIN_CYCLES},
    )
    cache = BandpilotSummaryCache(cache_path)
    bp = Bandpilot(stats_dir=stats, cache=cache)
    bp.recommend_for_band("40m")
    # Nun Stats wegloeschen → wenn Cache verwendet wird, klappt 2. Call trotzdem
    import shutil
    shutil.rmtree(stats)
    result = bp.recommend_for_band("40m")
    assert result is not None  # Cache hat noch Daten


def test_bandpilot_insufficient_data_returns_none(tmp_path):
    stats = tmp_path / "stats"
    # nur 1 Tag → unter MIN_DAYS → None
    _build_band_stats(
        stats, "40m",
        normal_days={"2026-04-21": [10] * 100},
        div_normal_days={"2026-04-21": [15] * 100},
        div_dx_days={"2026-04-21": [12] * 100},
    )
    bp = Bandpilot(stats_dir=stats, cache=BandpilotSummaryCache(tmp_path / "c.json"))
    assert bp.recommend_for_band("40m") is None


def test_bandpilot_invalidate_forces_reaggregate(tmp_path):
    stats = tmp_path / "stats"
    cache_path = tmp_path / "cache.json"
    _build_band_stats(
        stats, "40m",
        normal_days={"2026-04-21": [5] * MIN_CYCLES, "2026-04-22": [5] * MIN_CYCLES},
        div_normal_days={"2026-04-21": [10] * MIN_CYCLES, "2026-04-22": [10] * MIN_CYCLES},
        div_dx_days={"2026-04-21": [10] * MIN_CYCLES, "2026-04-22": [10] * MIN_CYCLES},
    )
    bp = Bandpilot(stats_dir=stats, cache=BandpilotSummaryCache(cache_path))
    bp.recommend_for_band("40m")  # populated cache
    bp.invalidate("40m")
    # Nach invalidate ist der Cache fuer 40m leer → recommend_for_band re-aggregiert
    raw = json.loads(cache_path.read_text())
    assert "40m" not in raw


def test_bandpilot_diversity_pref_propagates(tmp_path):
    stats = tmp_path / "stats"
    _build_band_stats(
        stats, "40m",
        normal_days={"2026-04-21": [5] * MIN_CYCLES, "2026-04-22": [5] * MIN_CYCLES},
        div_normal_days={"2026-04-21": [10] * MIN_CYCLES, "2026-04-22": [10] * MIN_CYCLES},
        div_dx_days={"2026-04-21": [20] * MIN_CYCLES, "2026-04-22": [20] * MIN_CYCLES},
    )
    cache = BandpilotSummaryCache(tmp_path / "c.json")
    # diversity_pref="standard" muss auch wenn dx-Mean groesser ist Standard waehlen
    bp_std = Bandpilot(stats_dir=stats, cache=cache, diversity_pref="standard")
    assert bp_std.recommend_for_band("40m") == "diversity_normal"
