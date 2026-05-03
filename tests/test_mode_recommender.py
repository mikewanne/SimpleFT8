"""Tests fuer core/mode_recommender.py — Bandpilot v0.88 Stunden-Logik.

Deckt ab:
- _parse_stats_file: Normal/Diversity/kaputte Zeilen
- _aggregate_mode_by_hour: pro UTC-Stunde gruppieren, Spotlight-Duplikate ignorieren
- aggregate_stats_by_hour: alle drei Modi
- recommend_for_hour: Toleranz-Regel, Schwellen, Edge-Cases
- HourlyBandpilotCache: TTL, invalidate, atomare Persistenz, JSON-Round-Trip
- HourlyBandpilot End-to-End

Alte Kandidat-A-Tests (V0.87 Aggregat (S+D)/2) wurden komplett entfernt —
das Konzept ist mit V0.88 obsolet (R1-Urteil 2026-05-04: Std und DX sind
keine IID-Population, Aggregat erzeugt Bias).
"""

import json
import time
from pathlib import Path

import pytest

from core.mode_recommender import (
    HourlyBandpilot,
    HourlyBandpilotCache,
    MIN_CYCLES_HOUR,
    MIN_DAYS_HOUR,
    _aggregate_mode_by_hour,
    _parse_stats_file,
    aggregate_stats_by_hour,
    recommend_for_hour,
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
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [NORMAL_HEADER]
    for i, c in enumerate(counts):
        lines.append(f"| 12:{i:02d}:00 | {c} | -20 |\n")
    path.write_text("".join(lines), encoding="utf-8")


def _write_div_file(path: Path, counts: list[int]):
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [DIV_HEADER]
    for i, c in enumerate(counts):
        lines.append(f"| 12:{i:02d}:00 | {c} | -20 | 2 | -1.5 |\n")
    path.write_text("".join(lines), encoding="utf-8")


def _build_band_hour_stats(
    base: Path,
    band: str,
    hour: int,
    *,
    normal_days: dict[str, list[int]] | None = None,
    div_normal_days: dict[str, list[int]] | None = None,
    div_dx_days: dict[str, list[int]] | None = None,
):
    """Stats-Verzeichnis bauen fuer EINE Stunde + alle 3 Modi.

    Filename-Format: ``YYYY-MM-DD_HH.md``.
    """
    for mode_dir, days_data, writer in (
        ("Normal", normal_days, _write_normal_file),
        ("Diversity_Normal", div_normal_days, _write_div_file),
        ("Diversity_Dx", div_dx_days, _write_div_file),
    ):
        if not days_data:
            continue
        target = base / mode_dir / band / "FT8"
        for day, counts in days_data.items():
            writer(target / f"{day}_{hour:02d}.md", counts)


def _summary_uniform(
    *, normal_mean: float, std_mean: float, dx_mean: float,
    days: int = MIN_DAYS_HOUR, cycles: int = MIN_CYCLES_HOUR,
) -> dict[int, dict[str, dict]]:
    """Synthetisches Summary fuer Stunde 12 mit gegebenen Means + Schwellen."""
    return {
        12: {
            "normal":           {"days": days, "cycles": cycles, "mean": normal_mean},
            "diversity_normal": {"days": days, "cycles": cycles, "mean": std_mean},
            "diversity_dx":     {"days": days, "cycles": cycles, "mean": dx_mean},
        }
    }


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
        + "| ohne_zeit | 99 | -20 |\n"
        + "| 12:01:00 | x | -20 |\n"
        + "| 12:02:00 | 3 | -20 |\n",
        encoding="utf-8",
    )
    s, c = _parse_stats_file(path)
    assert c == 2
    assert s == 10


def test_parse_missing_file_returns_zero(tmp_path):
    s, c = _parse_stats_file(tmp_path / "nope.md")
    assert (s, c) == (0, 0)


# ── _aggregate_mode_by_hour ───────────────────────────────────────────────────

def test_aggregate_mode_by_hour_empty(tmp_path):
    res = _aggregate_mode_by_hour(tmp_path)
    assert res == {}


def test_aggregate_mode_by_hour_one_hour_two_days(tmp_path):
    _write_normal_file(tmp_path / "2026-04-21_12.md", [4, 6])     # day 1
    _write_normal_file(tmp_path / "2026-04-22_12.md", [10, 10, 10])  # day 2
    res = _aggregate_mode_by_hour(tmp_path)
    assert 12 in res
    assert res[12]["days"] == 2
    assert res[12]["cycles"] == 5
    assert res[12]["mean"] == pytest.approx(40 / 5)


def test_aggregate_mode_by_hour_groups_by_hour(tmp_path):
    _write_normal_file(tmp_path / "2026-04-21_07.md", [10])
    _write_normal_file(tmp_path / "2026-04-21_08.md", [20])
    _write_normal_file(tmp_path / "2026-04-22_07.md", [12])
    res = _aggregate_mode_by_hour(tmp_path)
    assert set(res.keys()) == {7, 8}
    assert res[7]["days"] == 2
    assert res[7]["mean"] == pytest.approx(11.0)
    assert res[8]["days"] == 1
    assert res[8]["mean"] == pytest.approx(20.0)


def test_aggregate_mode_by_hour_ignores_spotlight_duplicates(tmp_path):
    _write_normal_file(tmp_path / "2026-04-21_12.md", [10])
    _write_normal_file(tmp_path / "2026-04-21_12 2.md", [99])  # macOS-Artefakt
    _write_normal_file(tmp_path / "random_other.md", [99])     # nicht-matching
    res = _aggregate_mode_by_hour(tmp_path)
    assert 12 in res
    assert res[12]["days"] == 1
    assert res[12]["mean"] == pytest.approx(10.0)


# ── aggregate_stats_by_hour ───────────────────────────────────────────────────

def test_aggregate_stats_by_hour_three_days_three_modes(tmp_path):
    """V3-AK 32 #1: Drei Tage in einer Stunde, alle drei Modi."""
    _build_band_hour_stats(
        tmp_path, "40m", hour=12,
        normal_days={
            "2026-04-21": [10, 10, 10, 10, 10],
            "2026-04-22": [10, 10, 10, 10, 10],
            "2026-04-23": [10, 10, 10, 10, 10],
        },
        div_normal_days={
            "2026-04-21": [15, 15, 15, 15, 15],
            "2026-04-22": [15, 15, 15, 15, 15],
            "2026-04-23": [15, 15, 15, 15, 15],
        },
        div_dx_days={
            "2026-04-21": [12, 12, 12, 12, 12],
            "2026-04-22": [12, 12, 12, 12, 12],
            "2026-04-23": [12, 12, 12, 12, 12],
        },
    )
    res = aggregate_stats_by_hour(tmp_path, "40m")
    assert 12 in res
    assert res[12]["normal"]["days"] == 3
    assert res[12]["normal"]["mean"] == pytest.approx(10.0)
    assert res[12]["diversity_normal"]["mean"] == pytest.approx(15.0)
    assert res[12]["diversity_dx"]["mean"] == pytest.approx(12.0)


def test_aggregate_stats_by_hour_missing_band(tmp_path):
    res = aggregate_stats_by_hour(tmp_path, "20m")
    assert res == {}


# ── recommend_for_hour: Edge-Cases (None, leere Stunde) ────────────────────────

def test_recommend_for_hour_current_mode_none_returns_none():
    summary = _summary_uniform(normal_mean=10.0, std_mean=15.0, dx_mean=12.0)
    assert recommend_for_hour(summary, 12, None) is None


def test_recommend_for_hour_empty_hour_returns_none():
    """V3-AK 32 #6: Stunde ohne Daten → None."""
    summary = _summary_uniform(normal_mean=10.0, std_mean=15.0, dx_mean=12.0)
    # Stunde 13 ist nicht im summary
    assert recommend_for_hour(summary, 13, "normal") is None


def test_recommend_for_hour_insufficient_one_mode_returns_none():
    """V3-AK 32 #6: Wenn ein Modus unter MIN_DAYS_HOUR → None."""
    summary = {
        12: {
            "normal":           {"days": MIN_DAYS_HOUR - 1,
                                  "cycles": MIN_CYCLES_HOUR, "mean": 10.0},
            "diversity_normal": {"days": MIN_DAYS_HOUR,
                                  "cycles": MIN_CYCLES_HOUR, "mean": 15.0},
            "diversity_dx":     {"days": MIN_DAYS_HOUR,
                                  "cycles": MIN_CYCLES_HOUR, "mean": 12.0},
        }
    }
    assert recommend_for_hour(summary, 12, "normal") is None


def test_recommend_for_hour_insufficient_cycles_returns_none():
    summary = {
        12: {
            "normal":           {"days": MIN_DAYS_HOUR,
                                  "cycles": MIN_CYCLES_HOUR - 1, "mean": 10.0},
            "diversity_normal": {"days": MIN_DAYS_HOUR,
                                  "cycles": MIN_CYCLES_HOUR, "mean": 15.0},
            "diversity_dx":     {"days": MIN_DAYS_HOUR,
                                  "cycles": MIN_CYCLES_HOUR, "mean": 12.0},
        }
    }
    assert recommend_for_hour(summary, 12, "normal") is None


def test_recommend_for_hour_current_mode_no_data_returns_none():
    """V3-AK 32 #7: current_mode hat keine Daten in der Stunde → None.

    Edge-Case R1-3: Stunde existiert, aber EIN Modus fehlt komplett —
    insufficient-data-Path greift, weil der fehlende Modus ist == None.
    """
    summary = {
        12: {
            "normal":           {"days": MIN_DAYS_HOUR,
                                  "cycles": MIN_CYCLES_HOUR, "mean": 10.0},
            "diversity_normal": {"days": MIN_DAYS_HOUR,
                                  "cycles": MIN_CYCLES_HOUR, "mean": 15.0},
            # diversity_dx fehlt komplett
        }
    }
    assert recommend_for_hour(summary, 12, "diversity_dx") is None


# ── recommend_for_hour: Hauptlogik ────────────────────────────────────────────

def test_recommend_for_hour_normal_top1_no_change():
    """V3-AK 32 #2: Top-1 == aktueller Modus → no_change."""
    summary = _summary_uniform(normal_mean=20.0, std_mean=10.0, dx_mean=5.0)
    res = recommend_for_hour(summary, 12, "normal")
    assert res is not None
    assert res["top1"] == "normal"
    assert res["top1_mean"] == pytest.approx(20.0)
    assert res["decision"] == "no_change"
    assert res["decision_mode"] == "normal"
    # Ranking: 3-elementig, sortiert
    assert [r[0] for r in res["ranking"]] == ["normal", "diversity_normal", "diversity_dx"]


def test_recommend_for_hour_diversity_dx_top1_switch():
    """V3-AK 32 #3: Top-1 != aktueller Modus + grosse Differenz → switch."""
    # Normal=10, Std=15, DX=40 (current=normal). 40-10=30 > Toleranz max(2,1)=2.
    summary = _summary_uniform(normal_mean=10.0, std_mean=15.0, dx_mean=40.0)
    res = recommend_for_hour(summary, 12, "normal")
    assert res is not None
    assert res["top1"] == "diversity_dx"
    assert res["decision"] == "switch"
    assert res["decision_mode"] == "diversity_dx"


def test_recommend_for_hour_tolerance_5pct_keeps_current():
    """V3-AK 32 #4: 5%-Toleranz greift, kein Wechsel."""
    # Top-1 = 40, current = 39. 5% von 40 = 2. 40-39 = 1 < 2 → no_change.
    summary = _summary_uniform(normal_mean=39.0, std_mean=10.0, dx_mean=40.0)
    res = recommend_for_hour(summary, 12, "normal")
    assert res is not None
    assert res["top1"] == "diversity_dx"
    assert res["decision"] == "no_change"
    assert res["decision_mode"] == "normal"


def test_recommend_for_hour_tolerance_1station_keeps_current():
    """V3-AK 32 #5: 1-Station-Toleranz bei kleinen Means."""
    # Top-1 = 5, current = 4.5. 5% von 5 = 0.25, max(0.25, 1) = 1.
    # 5-4.5 = 0.5 < 1 → no_change.
    summary = _summary_uniform(normal_mean=4.5, std_mean=3.0, dx_mean=5.0)
    res = recommend_for_hour(summary, 12, "normal")
    assert res is not None
    assert res["decision"] == "no_change"
    assert res["decision_mode"] == "normal"


def test_recommend_for_hour_tolerance_5pct_switches():
    """5%-Toleranz NICHT erfuellt → switch."""
    # Top-1 = 40, current = 30. 40-30 = 10 > max(2, 1) = 2 → switch.
    summary = _summary_uniform(normal_mean=30.0, std_mean=10.0, dx_mean=40.0)
    res = recommend_for_hour(summary, 12, "normal")
    assert res is not None
    assert res["decision"] == "switch"
    assert res["decision_mode"] == "diversity_dx"


def test_recommend_for_hour_hourly_thresholds_constants():
    """V3-AK 32 #8: MIN_DAYS_HOUR=3, MIN_CYCLES_HOUR=20."""
    assert MIN_DAYS_HOUR == 3
    assert MIN_CYCLES_HOUR == 20


def test_recommend_for_hour_ranking_descending():
    """Ranking immer absteigend nach mean sortiert."""
    summary = _summary_uniform(normal_mean=10.0, std_mean=30.0, dx_mean=20.0)
    res = recommend_for_hour(summary, 12, "normal")
    assert res is not None
    means_in_order = [r[1] for r in res["ranking"]]
    assert means_in_order == sorted(means_in_order, reverse=True)
    assert res["ranking"][0][0] == "diversity_normal"


# ── HourlyBandpilotCache ──────────────────────────────────────────────────────

def test_cache_set_and_get(tmp_path):
    cache = HourlyBandpilotCache(tmp_path / "cache.json")
    summary = {12: {"normal": {"days": 3, "cycles": 50, "mean": 10.0}}}
    cache.set("40m", summary)
    got = cache.get("40m")
    assert got is not None
    assert got[12]["normal"]["mean"] == pytest.approx(10.0)


def test_cache_int_keys_round_trip(tmp_path):
    """JSON serialisiert int-keys als str — beim Lesen zurueck konvertieren."""
    cache_path = tmp_path / "cache.json"
    cache = HourlyBandpilotCache(cache_path)
    summary = {7: {"normal": {"days": 3, "cycles": 50, "mean": 5.0}},
               13: {"normal": {"days": 3, "cycles": 50, "mean": 10.0}}}
    cache.set("40m", summary)
    cache2 = HourlyBandpilotCache(cache_path)  # neu laden
    got = cache2.get("40m")
    assert got is not None
    assert set(got.keys()) == {7, 13}
    assert all(isinstance(k, int) for k in got.keys())


def test_cache_ttl_expires(tmp_path):
    cache_path = tmp_path / "cache.json"
    cache = HourlyBandpilotCache(cache_path)
    cache.set("40m", {12: {"normal": {"days": 3, "cycles": 50, "mean": 1.0}}})
    raw = json.loads(cache_path.read_text())
    raw["40m"]["ts"] = time.time() - 25 * 3600  # 25h alt
    cache_path.write_text(json.dumps(raw))
    cache2 = HourlyBandpilotCache(cache_path)
    assert cache2.get("40m") is None


def test_cache_invalidate(tmp_path):
    cache = HourlyBandpilotCache(tmp_path / "cache.json")
    cache.set("40m", {12: {"normal": {"days": 3, "cycles": 50, "mean": 1.0}}})
    cache.invalidate("40m")
    assert cache.get("40m") is None


def test_cache_corrupted_json_returns_empty(tmp_path):
    cache_path = tmp_path / "cache.json"
    cache_path.write_text("{ not valid json")
    cache = HourlyBandpilotCache(cache_path)
    assert cache.get("40m") is None


def test_cache_atomic_write_no_partial_file(tmp_path):
    """Cache-Save schreibt erst tmp, dann replace — keine half-written
    config.json moeglich."""
    cache_path = tmp_path / "cache.json"
    cache = HourlyBandpilotCache(cache_path)
    cache.set("40m", {12: {"normal": {"days": 3, "cycles": 50, "mean": 5.0}}})
    # Nach Save: Datei existiert + keine .tmp-Reste
    assert cache_path.exists()
    assert not (tmp_path / "cache.tmp").exists()


# ── HourlyBandpilot End-to-End ────────────────────────────────────────────────

def test_hourly_bandpilot_recommend_uses_cache(tmp_path):
    """Zweiter Aufruf nutzt Cache (Stats geloescht → Cache haelt Wert)."""
    stats = tmp_path / "stats"
    cache_path = tmp_path / "cache.json"
    _build_band_hour_stats(
        stats, "40m", hour=12,
        normal_days={f"2026-04-{d:02d}": [10] * 10 for d in range(21, 24)},
        div_normal_days={f"2026-04-{d:02d}": [20] * 10 for d in range(21, 24)},
        div_dx_days={f"2026-04-{d:02d}": [15] * 10 for d in range(21, 24)},
    )
    bp = HourlyBandpilot(stats_dir=stats, cache=HourlyBandpilotCache(cache_path))
    first = bp.recommend("40m", 12, "normal")
    assert first is not None
    # Stats wegloeschen → Cache haelt
    import shutil
    shutil.rmtree(stats)
    second = bp.recommend("40m", 12, "normal")
    assert second is not None
    assert second["top1"] == first["top1"]


def test_hourly_bandpilot_insufficient_data_returns_none(tmp_path):
    stats = tmp_path / "stats"
    _build_band_hour_stats(
        stats, "40m", hour=12,
        normal_days={"2026-04-21": [10] * 100},  # nur 1 Tag
        div_normal_days={"2026-04-21": [15] * 100},
        div_dx_days={"2026-04-21": [12] * 100},
    )
    bp = HourlyBandpilot(stats_dir=stats,
                         cache=HourlyBandpilotCache(tmp_path / "c.json"))
    assert bp.recommend("40m", 12, "normal") is None


def test_hourly_bandpilot_invalidate(tmp_path):
    stats = tmp_path / "stats"
    cache_path = tmp_path / "cache.json"
    _build_band_hour_stats(
        stats, "40m", hour=12,
        normal_days={f"2026-04-{d:02d}": [10] * 10 for d in range(21, 24)},
        div_normal_days={f"2026-04-{d:02d}": [20] * 10 for d in range(21, 24)},
        div_dx_days={f"2026-04-{d:02d}": [15] * 10 for d in range(21, 24)},
    )
    bp = HourlyBandpilot(stats_dir=stats, cache=HourlyBandpilotCache(cache_path))
    bp.recommend("40m", 12, "normal")
    bp.invalidate("40m")
    raw = json.loads(cache_path.read_text())
    assert "40m" not in raw
