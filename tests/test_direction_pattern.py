#!/usr/bin/env python3
"""Tests fuer core/direction_pattern.py — Sektor-Aggregation.

Ausfuehren:
    cd SimpleFT8
    ./venv/bin/python3 -m pytest tests/test_direction_pattern.py -v
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.direction_pattern import (
    StationPoint,
    SectorBucket,
    is_mobile,
    sector_index,
    aggregate_sectors,
    SECTOR_COUNT,
    SECTOR_WIDTH_DEG,
)


# ── is_mobile ─────────────────────────────────────────────

def test_is_mobile_portable():
    assert is_mobile("DA1MHH/P")


def test_is_mobile_maritime():
    assert is_mobile("DA1MHH/MM")


def test_is_mobile_aeronautical():
    assert is_mobile("DA1MHH/AM")


def test_is_mobile_qrp():
    assert is_mobile("DA1MHH/QRP")


def test_is_mobile_short_suffix():
    assert is_mobile("DA1MHH/M")


def test_is_mobile_plain_call_false():
    assert not is_mobile("DA1MHH")


def test_is_mobile_empty_false():
    assert not is_mobile("")


def test_is_mobile_lowercase_normalized():
    assert is_mobile("da1mhh/p")


def test_is_mobile_long_suffix_not_matched():
    # Region-Indikatoren wie /XYZ12 sind > 4 Zeichen → nicht als mobile gewertet
    assert not is_mobile("K1ABC/XYZ12")


# ── sector_index ──────────────────────────────────────────

def test_sector_index_north_is_zero():
    assert sector_index(0.0) == 0
    assert sector_index(360.0) == 0
    # Knapp unter Norden (rechts vom Pol)
    assert sector_index(11.0) == 0
    # Knapp ueber Norden auf der West-Seite
    assert sector_index(355.0) == 0


def test_sector_index_east_is_4():
    # 4 * 22.5 = 90°
    assert sector_index(90.0) == 4


def test_sector_index_south_is_8():
    assert sector_index(180.0) == 8


def test_sector_index_west_is_12():
    assert sector_index(270.0) == 12


def test_sector_index_360_wraps_to_0():
    assert sector_index(359.99) == 0
    assert sector_index(360.0) == 0


def test_sector_index_boundary_at_11_25():
    # 11.25 ist Grenze zwischen Sektor 0 (-11.25..11.25) und 1 (11.25..33.75)
    assert sector_index(11.24) == 0
    assert sector_index(11.26) == 1


def test_sector_index_negative_normalizes():
    # -10° entspricht 350° → Sektor 0
    assert sector_index(-10.0) == 0


def test_sector_index_all_16_buckets():
    # Mitte jedes Sektors ergibt genau dessen Index
    for i in range(SECTOR_COUNT):
        center = i * SECTOR_WIDTH_DEG
        assert sector_index(center) == i, f"Sektor-Mitte {center}° → erwartet {i}"


# ── aggregate_sectors ─────────────────────────────────────

def _sp(call: str, lat: float, lon: float, snr: float = -10.0,
        antenna: str = "", ts: float = 0.0) -> StationPoint:
    return StationPoint(call=call, locator="", lat=lat, lon=lon, snr=snr,
                        antenna=antenna, timestamp=ts)


def test_aggregate_empty_returns_16_empty_buckets():
    buckets = aggregate_sectors([], 51.5, 7.0)
    assert len(buckets) == SECTOR_COUNT
    for b in buckets:
        assert b.count == 0
        assert b.avg_snr == 0.0


def test_aggregate_single_north_station():
    # Punkt direkt noerdlich von JO31
    stations = [_sp("DK4ABC", 60.0, 7.0, snr=-12.0)]
    buckets = aggregate_sectors(stations, 51.5, 7.0)
    assert buckets[0].count == 1
    assert buckets[0].avg_snr == -12.0
    for b in buckets[1:]:
        assert b.count == 0


def test_aggregate_call_dedup_same_sector():
    # Gleiche Station mehrfach gehoert → 1× im Sektor gezaehlt
    stations = [
        _sp("DK4ABC", 60.0, 7.0, snr=-12.0),
        _sp("DK4ABC", 60.0, 7.0, snr=-15.0),
        _sp("DK4ABC", 60.0, 7.0, snr=-10.0),
    ]
    buckets = aggregate_sectors(stations, 51.5, 7.0)
    assert buckets[0].count == 1
    # avg_snr = nur erste Sichtung gezaehlt
    assert buckets[0].avg_snr == -12.0


def test_aggregate_different_calls_same_sector_both_counted():
    stations = [
        _sp("DK4ABC", 60.0, 7.0, snr=-12.0),
        _sp("DL1XYZ", 61.0, 7.5, snr=-8.0),
    ]
    buckets = aggregate_sectors(stations, 51.5, 7.0)
    assert buckets[0].count == 2
    assert buckets[0].avg_snr == -10.0  # Mittelwert


def test_aggregate_antenna_counters():
    stations = [
        _sp("DK4ABC", 60.0, 7.0, antenna="A1"),
        _sp("DL1XYZ", 60.5, 7.0, antenna="A2"),
        _sp("DM2ABC", 61.0, 7.0, antenna="A2"),
        _sp("DN3XYZ", 60.2, 7.0, antenna="rescue"),
    ]
    buckets = aggregate_sectors(stations, 51.5, 7.0)
    b = buckets[0]
    assert b.count == 4
    assert b.ant1_count == 1
    assert b.ant2_count == 2
    assert b.rescue_count == 1


def test_aggregate_360_wrap_north_sector():
    # Stationen knapp links und rechts vom Norden landen beide in Sektor 0
    stations = [
        # Bearing ~5°
        _sp("EAST_OF_NORTH", 60.0, 7.5, snr=-12.0),
        # Bearing ~355° (durch Lon-Spiegelung)
        _sp("WEST_OF_NORTH", 60.0, 6.5, snr=-12.0),
    ]
    buckets = aggregate_sectors(stations, 51.5, 7.0)
    assert buckets[0].count == 2


def test_aggregate_last_update_is_max():
    stations = [
        _sp("DK4ABC", 60.0, 7.0, ts=100.0),
        _sp("DK4ABC", 60.0, 7.0, ts=50.0),  # Dedup-Skip
        _sp("DL1XYZ", 60.0, 7.0, ts=200.0),
    ]
    buckets = aggregate_sectors(stations, 51.5, 7.0)
    # last_update = max ueber alle Stationen die im Sektor gezaehlt wurden
    assert buckets[0].last_update == 200.0


def test_aggregate_all_16_sectors_distributed():
    """Stationen in jeder Himmelsrichtung → genau 1 pro Sektor."""
    import math
    stations = []
    for i in range(SECTOR_COUNT):
        bearing_rad = math.radians(i * SECTOR_WIDTH_DEG)
        # Punkt in 1000km Distanz von (0,0), klein genug fuer flache Naeherung
        # 1° Lat ≈ 111 km, 1° Lon am Aequator ≈ 111 km
        d_deg = 9.0
        lat = d_deg * math.cos(bearing_rad)
        lon = d_deg * math.sin(bearing_rad)
        stations.append(_sp(f"CALL{i}", lat, lon))
    buckets = aggregate_sectors(stations, 0.0, 0.0)
    counts = [b.count for b in buckets]
    assert counts == [1] * SECTOR_COUNT, f"Verteilung nicht gleichmaessig: {counts}"


def test_aggregate_returns_bucket_with_index():
    buckets = aggregate_sectors([], 51.5, 7.0)
    for i, b in enumerate(buckets):
        assert b.index == i


def test_aggregate_skips_nan_or_inf_coords():
    # Defense-in-Depth: korrupte lat/lon duerfen NICHT alle in Sektor 0 landen.
    nan_lat = _sp("NAN_LAT", float("nan"), 7.0)
    inf_lon = _sp("INF_LON", 60.0, float("inf"))
    valid = _sp("VALID", 60.0, 7.0)
    buckets = aggregate_sectors([nan_lat, inf_lon, valid], 51.5, 7.0)
    # Nur VALID gezaehlt
    total = sum(b.count for b in buckets)
    assert total == 1
    assert buckets[0].count == 1
    assert "VALID" in buckets[0]._calls
