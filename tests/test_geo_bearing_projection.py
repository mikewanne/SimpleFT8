#!/usr/bin/env python3
"""Tests fuer core/geo.py: Bearing, Azimuthal-Equidistant-Projektion, safe_locator_to_latlon.

Ausfuehren:
    cd SimpleFT8
    ./venv/bin/python3 -m pytest tests/test_geo_bearing_projection.py -v
"""

import sys
import os
import math

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.geo import (
    safe_locator_to_latlon,
    great_circle_bearing,
    azimuthal_equidistant_project,
    distance_km,
)


# ── safe_locator_to_latlon ────────────────────────────────

def test_safe_locator_none_returns_none():
    assert safe_locator_to_latlon(None) is None


def test_safe_locator_empty_string_returns_none():
    assert safe_locator_to_latlon("") is None


def test_safe_locator_whitespace_returns_none():
    assert safe_locator_to_latlon("   ") is None


def test_safe_locator_too_short_returns_none():
    assert safe_locator_to_latlon("JO") is None


def test_safe_locator_invalid_chars_returns_none():
    # "XX99" — XX ueberschreitet den Maidenhead-Bereich nicht (A–R erlaubt sind 0..17),
    # X ist 23 → ungueltige Lon. grid_to_latlon liefert hier eine Lat/Lon-Pair,
    # aber bereits "12" als erste 2 Zeichen gibt sicher None (alpha-Check).
    assert safe_locator_to_latlon("12cd") is None


def test_safe_locator_non_string_returns_none():
    assert safe_locator_to_latlon(12345) is None
    assert safe_locator_to_latlon(["JO31"]) is None


def test_safe_locator_4char_jo31():
    pos = safe_locator_to_latlon("JO31")
    assert pos is not None
    lat, lon = pos
    # JO31 = ca. (51.5°N, 7.0°E)
    assert 51.0 < lat < 52.0
    assert 6.0 < lon < 8.0


def test_safe_locator_6char_jo31qf():
    pos = safe_locator_to_latlon("JO31qf")
    assert pos is not None
    lat, lon = pos
    # JO31qf liegt im selben Feld, genauer
    assert 51.0 < lat < 52.0
    assert 6.5 < lon < 7.5


def test_safe_locator_lowercase_input():
    a = safe_locator_to_latlon("jo31")
    b = safe_locator_to_latlon("JO31")
    assert a == b


# ── great_circle_bearing ──────────────────────────────────

def test_bearing_north_is_zero():
    # Center (0,0), Punkt direkt noerdlich (10°,0°) → 0°
    b = great_circle_bearing(0.0, 0.0, 10.0, 0.0)
    assert abs(b - 0.0) < 0.5


def test_bearing_east_at_equator_is_90():
    # Center (0,0), Punkt direkt oestlich (0°,30°) → 90°
    b = great_circle_bearing(0.0, 0.0, 0.0, 30.0)
    assert abs(b - 90.0) < 0.5


def test_bearing_south_is_180():
    b = great_circle_bearing(0.0, 0.0, -10.0, 0.0)
    assert abs(b - 180.0) < 0.5


def test_bearing_west_at_equator_is_270():
    # Center (0,0), Punkt direkt westlich → 270°
    b = great_circle_bearing(0.0, 0.0, 0.0, -30.0)
    assert abs(b - 270.0) < 0.5


def test_bearing_jo31_to_ko82_is_easterly():
    # JO31 (DE) → KO82 (Russland Sued, ca. 50.5°N 36.5°E)
    # Bearing sollte deutlich oestlich sein, ungefaehr 70–100°
    pos1 = safe_locator_to_latlon("JO31")
    pos2 = safe_locator_to_latlon("KO82")
    assert pos1 and pos2
    b = great_circle_bearing(pos1[0], pos1[1], pos2[0], pos2[1])
    assert 60.0 < b < 110.0, f"Bearing JO31→KO82 = {b}, erwartet ~70–100°"


def test_bearing_always_in_range():
    # Egal welche Konstellation, Bearing muss [0, 360) sein
    for lat1, lon1, lat2, lon2 in [
        (90.0, 0.0, -90.0, 0.0),  # Pol → Pol
        (51.5, 7.0, 51.5, -170.0),  # ueber Antimeridian
        (-30.0, 150.0, 30.0, -150.0),
        (0.0, 0.0, 0.0, 180.0),  # Antipode
    ]:
        b = great_circle_bearing(lat1, lon1, lat2, lon2)
        assert 0.0 <= b < 360.0, f"Bearing {b} out of range fuer ({lat1},{lon1})→({lat2},{lon2})"


def test_bearing_identical_points_returns_zero():
    # Bei (0,0)→(0,0): atan2(0,0) = 0
    b = great_circle_bearing(51.5, 7.0, 51.5, 7.0)
    assert b == 0.0


def test_bearing_pole_input_does_not_crash():
    # Vom Nordpol aus ist Bearing semantisch nicht definiert; Funktion darf nicht crashen.
    # Docstring dokumentiert: Wert ist semantisch willkuerlich, aber [0, 360).
    b = great_circle_bearing(90.0, 0.0, 51.5, 7.0)
    assert 0.0 <= b < 360.0
    b = great_circle_bearing(-90.0, 0.0, 51.5, 7.0)
    assert 0.0 <= b < 360.0


# ── azimuthal_equidistant_project ─────────────────────────

def test_projection_center_is_origin():
    # Identischer Punkt → (0, 0)
    p = azimuthal_equidistant_project(51.5, 7.0, 51.5, 7.0, radius_px=300.0)
    assert p is not None
    x, y = p
    assert abs(x) < 1e-6
    assert abs(y) < 1e-6


def test_projection_north_has_negative_y():
    # Punkt direkt noerdlich → x≈0, y<0 (Norden ist oben in Qt)
    p = azimuthal_equidistant_project(0.0, 0.0, 30.0, 0.0, radius_px=300.0)
    assert p is not None
    x, y = p
    assert abs(x) < 1.0  # nahe 0
    assert y < 0.0       # negativ → oben


def test_projection_east_has_positive_x():
    # Punkt direkt oestlich am Aequator → x>0, y≈0
    p = azimuthal_equidistant_project(0.0, 0.0, 0.0, 30.0, radius_px=300.0)
    assert p is not None
    x, y = p
    assert x > 0.0
    assert abs(y) < 1.0


def test_projection_south_has_positive_y():
    p = azimuthal_equidistant_project(0.0, 0.0, -30.0, 0.0, radius_px=300.0)
    assert p is not None
    x, y = p
    assert abs(x) < 1.0
    assert y > 0.0


def test_projection_radius_scales_linearly():
    # Doppeltes radius_px → doppelte Pixel-Koordinaten
    p1 = azimuthal_equidistant_project(0.0, 0.0, 0.0, 30.0, radius_px=100.0)
    p2 = azimuthal_equidistant_project(0.0, 0.0, 0.0, 30.0, radius_px=200.0)
    assert p1 and p2
    assert abs(p2[0] - 2.0 * p1[0]) < 1e-6


def test_projection_distance_proportional():
    # r = (d / max_distance_km) * radius_px — exakten Haversine-Wert nutzen,
    # nicht eine 111.32-km/°-Schaetzung
    d = distance_km(0.0, 0.0, 0.0, 30.0)
    p = azimuthal_equidistant_project(0.0, 0.0, 0.0, 30.0, radius_px=180.0, max_distance_km=18000.0)
    assert p is not None
    expected_r = (d / 18000.0) * 180.0
    actual_r = math.hypot(p[0], p[1])
    assert abs(actual_r - expected_r) < 0.5, f"r={actual_r}, expected={expected_r}"


def test_projection_antipode_returns_none():
    # JO31 (51.5°N 7.0°E), Antipode bei (-51.5°S, -173.0°W), Distanz ~20015 km
    p = azimuthal_equidistant_project(51.5, 7.0, -51.5, -173.0, radius_px=300.0,
                                       max_distance_km=18000.0)
    assert p is None


def test_projection_just_within_max_distance():
    # 150° Lon am Aequator ≈ 16696 km (Haversine) < 18000 km → muss projizieren
    p = azimuthal_equidistant_project(0.0, 0.0, 0.0, 150.0, radius_px=300.0)
    assert p is not None
    # nahe am Rand, aber innerhalb (r > 250 von max 300)
    assert math.hypot(p[0], p[1]) > 250.0


def test_projection_custom_max_distance_km():
    # Mit max_distance_km=5000 wird ein 6000-km-Punkt geclipped
    p = azimuthal_equidistant_project(0.0, 0.0, 0.0, 60.0, radius_px=300.0,
                                       max_distance_km=5000.0)
    # 60° Lon = ~6680 km am Aequator → > 5000 → None
    assert p is None


def test_projection_invalid_max_distance_returns_none():
    # max_distance_km <= 0 darf keinen DivByZero werfen, sondern None liefern
    assert azimuthal_equidistant_project(0.0, 0.0, 0.0, 0.0, radius_px=300.0,
                                          max_distance_km=0.0) is None
    assert azimuthal_equidistant_project(0.0, 0.0, 10.0, 10.0, radius_px=300.0,
                                          max_distance_km=-1.0) is None
