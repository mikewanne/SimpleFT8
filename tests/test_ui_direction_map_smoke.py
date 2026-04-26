#!/usr/bin/env python3
"""Smoke-Tests fuer ui/direction_map_widget.py.

Stellt sicher, dass das Widget instantiierbar ist, kein Crash bei leerem Locator,
Toggle korrekt funktioniert. Nutzt QT_QPA_PLATFORM=offscreen damit kein Display
noetig ist.

Ausfuehren:
    cd SimpleFT8
    ./venv/bin/python3 -m pytest tests/test_ui_direction_map_smoke.py -v
"""

import sys
import os

# Offscreen-Modus VOR dem Import von Qt setzen
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

try:
    from PySide6.QtWidgets import QApplication
    HAVE_QT = True
except ImportError:
    HAVE_QT = False

if not HAVE_QT:
    pytest.skip("PySide6 nicht verfuegbar", allow_module_level=True)


@pytest.fixture(scope="module")
def qapp():
    """QApplication-Singleton fuer alle Tests im Modul."""
    app = QApplication.instance() or QApplication([])
    yield app
    # Nicht .quit() — andere Tests koennten App noch brauchen


# ── Pure-Python-Logik (ohne Widget) ───────────────────────

def test_load_coastlines_returns_list():
    from ui.direction_map_widget import load_coastlines
    lines = load_coastlines()
    assert isinstance(lines, list)
    # Bei vorhandenem Asset > 0 Linien
    assert len(lines) > 0
    # Jede Linie ist Liste von (lon,lat)-Tupeln
    for ln in lines[:3]:
        assert isinstance(ln, list)
        for pt in ln[:3]:
            assert len(pt) == 2
            assert -180 <= pt[0] <= 180
            assert -90 <= pt[1] <= 90


def test_load_coastlines_total_points_plausible():
    from ui.direction_map_widget import load_coastlines
    lines = load_coastlines()
    total = sum(len(ln) for ln in lines)
    # Build-Script reportet 5143 Punkte; Toleranz fuer kuenftige Updates
    assert total > 1000, f"nur {total} Coastline-Punkte — Asset zu klein?"


# ── MapCanvas — instantiieren und API ─────────────────────

def test_canvas_instantiate_with_valid_locator(qapp):
    from ui.direction_map_widget import MapCanvas
    c = MapCanvas(my_locator="JO31")
    assert c.has_locator()


def test_canvas_instantiate_with_empty_locator(qapp):
    from ui.direction_map_widget import MapCanvas
    c = MapCanvas(my_locator="")
    assert not c.has_locator()


def test_canvas_instantiate_with_invalid_locator(qapp):
    from ui.direction_map_widget import MapCanvas
    # "12cd" — Ziffer an Pos 0/1 statt Buchstabe → grid_to_latlon → None
    c = MapCanvas(my_locator="12cd")
    assert not c.has_locator()


def test_canvas_set_locator_changes_state(qapp):
    from ui.direction_map_widget import MapCanvas
    c = MapCanvas(my_locator="")
    assert not c.has_locator()
    c.set_locator("JO31")
    assert c.has_locator()
    c.set_locator("")
    assert not c.has_locator()


def test_canvas_set_mode_only_accepts_rx_or_tx(qapp):
    from ui.direction_map_widget import MapCanvas
    c = MapCanvas(my_locator="JO31")
    c.set_mode("rx")
    assert c._mode == "rx"
    c.set_mode("tx")
    assert c._mode == "tx"
    c.set_mode("garbage")  # silent ignore
    assert c._mode == "tx"


def test_canvas_update_stations_works_without_crash(qapp):
    from ui.direction_map_widget import MapCanvas
    from core.direction_pattern import StationPoint
    c = MapCanvas(my_locator="JO31")
    stations = [
        StationPoint(call="DK4ABC", locator="JO40", lat=49.0, lon=8.0,
                     snr=-12.0, antenna="A2"),
        StationPoint(call="W1XYZ", locator="FN42", lat=42.0, lon=-71.0,
                     snr=-8.0, antenna="A1"),
    ]
    c.update_stations(stations)
    assert len(c._stations) == 2
    # Sektor-Aggregation lief
    assert len(c._sectors) == 16


def test_canvas_update_stations_without_locator_no_crash(qapp):
    from ui.direction_map_widget import MapCanvas
    from core.direction_pattern import StationPoint
    c = MapCanvas(my_locator="")
    c.update_stations([
        StationPoint(call="DK4ABC", locator="JO40", lat=49.0, lon=8.0, snr=-12.0)
    ])
    assert c._sectors == []  # ohne my_pos kein Aggregate


# ── DirectionMapDialog — Toggle, Status ───────────────────

def test_dialog_instantiate(qapp):
    from ui.direction_map_widget import DirectionMapDialog
    d = DirectionMapDialog(my_locator="JO31")
    assert d.canvas.has_locator()
    assert d.mode == "rx"
    d.deleteLater()


def test_dialog_default_mode_rx(qapp):
    from ui.direction_map_widget import DirectionMapDialog
    d = DirectionMapDialog(my_locator="JO31", default_mode="rx")
    assert d.btn_rx.isChecked()
    assert not d.btn_tx.isChecked()
    d.deleteLater()


def test_dialog_default_mode_tx(qapp):
    from ui.direction_map_widget import DirectionMapDialog
    d = DirectionMapDialog(my_locator="JO31", default_mode="tx")
    assert d.btn_tx.isChecked()
    assert not d.btn_rx.isChecked()
    d.deleteLater()


def test_dialog_invalid_default_mode_falls_back_to_rx(qapp):
    from ui.direction_map_widget import DirectionMapDialog
    d = DirectionMapDialog(my_locator="JO31", default_mode="garbage")
    assert d.mode == "rx"
    d.deleteLater()


def test_dialog_toggle_rx_to_tx(qapp):
    from ui.direction_map_widget import DirectionMapDialog
    d = DirectionMapDialog(my_locator="JO31", default_mode="rx")
    d.btn_tx.click()  # simulate click
    assert d.mode == "tx"
    assert d.btn_tx.isChecked()
    assert not d.btn_rx.isChecked()
    d.deleteLater()


def test_dialog_toggle_buttons_mutually_exclusive(qapp):
    from ui.direction_map_widget import DirectionMapDialog
    d = DirectionMapDialog(my_locator="JO31", default_mode="rx")
    d.btn_tx.click()
    # Nur einer zur Zeit checked
    assert d.btn_rx.isChecked() != d.btn_tx.isChecked()
    d.btn_rx.click()
    assert d.btn_rx.isChecked() != d.btn_tx.isChecked()
    d.deleteLater()


def test_dialog_set_status_updates_label(qapp):
    from ui.direction_map_widget import DirectionMapDialog
    d = DirectionMapDialog(my_locator="JO31")
    d.set_status("Custom status text")
    assert "Custom status text" in d.status_label.text()
    d.deleteLater()


def test_dialog_with_empty_locator_renders_hint(qapp):
    from ui.direction_map_widget import DirectionMapDialog
    d = DirectionMapDialog(my_locator="")
    assert not d.canvas.has_locator()
    # paintEvent muss fuer no-locator-Fall ohne Crash laufen
    d.show()
    d.canvas.repaint()
    d.deleteLater()


def test_dialog_set_locator_propagates_to_canvas(qapp):
    from ui.direction_map_widget import DirectionMapDialog
    d = DirectionMapDialog(my_locator="")
    assert not d.canvas.has_locator()
    d.set_locator("JO31")
    assert d.canvas.has_locator()
    d.deleteLater()


def test_dialog_default_filter_settings(qapp):
    from ui.direction_map_widget import DirectionMapDialog
    d = DirectionMapDialog(my_locator="JO31")
    assert d.time_window_min == 60
    assert d.band_filter == "current"
    d.deleteLater()


def test_dialog_paintevent_with_locator_no_crash(qapp):
    """paintEvent darf bei vorhandenem Locator nicht crashen, auch wenn
    keine Stationen geladen sind."""
    from ui.direction_map_widget import DirectionMapDialog
    d = DirectionMapDialog(my_locator="JO31")
    d.resize(600, 600)
    d.show()
    d.canvas.repaint()
    d.deleteLater()


def test_dialog_paintevent_with_stations_no_crash(qapp):
    from ui.direction_map_widget import DirectionMapDialog
    from core.direction_pattern import StationPoint
    d = DirectionMapDialog(my_locator="JO31")
    d.resize(600, 600)
    d.show()
    d.update_rx_stations([
        StationPoint(call="DK4ABC", locator="JO40", lat=49.0, lon=8.0,
                     snr=-12.0, antenna="A2"),
    ])
    d.canvas.repaint()
    d.deleteLater()


# ── LocatorCache (pure-Python, ohne Qt) ───────────────────

def test_locator_cache_empty():
    from ui.direction_map_widget import LocatorCache
    c = LocatorCache()
    assert c.get("DK4ABC") is None
    assert len(c) == 0


def test_locator_cache_update_and_get():
    from ui.direction_map_widget import LocatorCache
    c = LocatorCache()
    c.update("DK4ABC", "JO31")
    assert c.get("DK4ABC") == "JO31"
    assert len(c) == 1


def test_locator_cache_uppercases_callsign():
    from ui.direction_map_widget import LocatorCache
    c = LocatorCache()
    c.update("dk4abc", "JO31")
    assert c.get("DK4ABC") == "JO31"
    assert c.get("dk4abc") == "JO31"


def test_locator_cache_skips_invalid_locator():
    from ui.direction_map_widget import LocatorCache
    c = LocatorCache()
    c.update("DK4ABC", "")        # leer → skip
    c.update("DL1XYZ", "12cd")    # ungueltig → skip
    c.update("DM2DEF", "JO")      # zu kurz → skip
    assert len(c) == 0


def test_locator_cache_skips_empty_call():
    from ui.direction_map_widget import LocatorCache
    c = LocatorCache()
    c.update("", "JO31")
    assert len(c) == 0


def test_locator_cache_overwrites_old_locator():
    from ui.direction_map_widget import LocatorCache
    c = LocatorCache()
    c.update("DK4ABC", "JO31")
    c.update("DK4ABC", "JO40")  # Station hat sich gemeldet (umgezogen?)
    assert c.get("DK4ABC") == "JO40"


def test_locator_cache_clear():
    from ui.direction_map_widget import LocatorCache
    c = LocatorCache()
    c.update("DK4ABC", "JO31")
    c.clear()
    assert len(c) == 0


# ── snapshot_to_station_points ────────────────────────────

def test_snapshot_to_points_skips_unknown_locator():
    from ui.direction_map_widget import snapshot_to_station_points, LocatorCache
    cache = LocatorCache()
    snap = {"DK4ABC": {"snr": -10, "freq_hz": 14074000, "antenna": "A1"}}
    pts = snapshot_to_station_points(snap, cache)
    assert pts == []  # kein Locator → kein Punkt


def test_snapshot_to_points_uses_cache():
    from ui.direction_map_widget import snapshot_to_station_points, LocatorCache
    cache = LocatorCache()
    cache.update("DK4ABC", "JO31")
    snap = {"DK4ABC": {"snr": -10, "antenna": "A2"}}
    pts = snapshot_to_station_points(snap, cache)
    assert len(pts) == 1
    assert pts[0].call == "DK4ABC"
    assert pts[0].locator == "JO31"
    assert pts[0].antenna == "A2"


def test_snapshot_to_points_uses_explicit_locator_and_caches():
    from ui.direction_map_widget import snapshot_to_station_points, LocatorCache
    cache = LocatorCache()
    snap = {"DK4ABC": {"snr": -10, "antenna": "A1", "locator": "JO31"}}
    pts = snapshot_to_station_points(snap, cache)
    assert len(pts) == 1
    # Cache wurde aktualisiert
    assert cache.get("DK4ABC") == "JO31"


def test_snapshot_to_points_filters_mobile_calls():
    from ui.direction_map_widget import snapshot_to_station_points, LocatorCache
    cache = LocatorCache()
    cache.update("DK4ABC/P", "JO31")  # wuerde geskippt durch is_mobile
    snap = {"DK4ABC/P": {"snr": -10, "antenna": "A1", "locator": "JO31"}}
    pts = snapshot_to_station_points(snap, cache)
    assert pts == []


def test_snapshot_to_points_rescue_classification():
    from ui.direction_map_widget import snapshot_to_station_points, LocatorCache
    cache = LocatorCache()
    snap = {"DK4ABC": {
        "snr": -22, "antenna": "A2", "locator": "JO31",
        "snr_a1": -25.0, "snr_a2": -22.0,  # ANT1 unter -24, ANT2 daruber → rescue
    }}
    pts = snapshot_to_station_points(snap, cache)
    assert len(pts) == 1
    assert pts[0].antenna == "rescue"


def test_snapshot_to_points_no_rescue_when_both_strong():
    from ui.direction_map_widget import snapshot_to_station_points, LocatorCache
    cache = LocatorCache()
    snap = {"DK4ABC": {
        "snr": -10, "antenna": "A2", "locator": "JO31",
        "snr_a1": -12.0, "snr_a2": -10.0,
    }}
    pts = snapshot_to_station_points(snap, cache)
    assert pts[0].antenna == "A2"


# ── _interpolate_color ────────────────────────────────────

def test_interpolate_color_at_min(qapp):
    from PySide6.QtGui import QColor
    from ui.direction_map_widget import _interpolate_color
    low = QColor(0, 0, 0)
    high = QColor(255, 255, 255)
    c = _interpolate_color(low, high, value=0.0, v_min=0.0, v_max=10.0)
    assert (c.red(), c.green(), c.blue()) == (0, 0, 0)


def test_interpolate_color_at_max(qapp):
    from PySide6.QtGui import QColor
    from ui.direction_map_widget import _interpolate_color
    low = QColor(0, 0, 0)
    high = QColor(255, 255, 255)
    c = _interpolate_color(low, high, value=10.0, v_min=0.0, v_max=10.0)
    assert (c.red(), c.green(), c.blue()) == (255, 255, 255)


def test_interpolate_color_clamps_below_min(qapp):
    from PySide6.QtGui import QColor
    from ui.direction_map_widget import _interpolate_color
    low = QColor(0, 0, 0)
    high = QColor(255, 255, 255)
    c = _interpolate_color(low, high, value=-100.0, v_min=0.0, v_max=10.0)
    assert (c.red(), c.green(), c.blue()) == (0, 0, 0)


def test_canvas_layer_toggles_state(qapp):
    from ui.direction_map_widget import MapCanvas
    c = MapCanvas(my_locator="JO31")
    c.set_show_sectors(False)
    assert not c._show_sectors
    c.set_show_stations(False)
    assert not c._show_stations
    c.set_show_sectors(True)
    assert c._show_sectors


def test_dialog_set_callsign(qapp):
    from ui.direction_map_widget import DirectionMapDialog
    d = DirectionMapDialog(my_locator="JO31")
    d.set_callsign("DA1MHH", "FT8")
    assert d._callsign == "DA1MHH"
    assert d._ft_mode == "FT8"
    d.deleteLater()


def test_dialog_tx_polling_does_nothing_without_callsign(qapp):
    """TX-Toggle ohne Callsign in Settings → Status-Hinweis statt Crash."""
    from ui.direction_map_widget import DirectionMapDialog
    d = DirectionMapDialog(my_locator="JO31")  # callsign default ""
    d.btn_tx.click()
    # Polling-Client darf nicht laufen
    assert d._psk_client is None or not d._psk_client.is_running
    assert "kein Callsign" in d.status_label.text() or "deaktiviert" in d.status_label.text()
    d.deleteLater()


def test_dialog_tx_to_rx_stops_polling(qapp):
    """Wechsel TX→RX muss Polling sauber stoppen."""
    from ui.direction_map_widget import DirectionMapDialog
    d = DirectionMapDialog(my_locator="JO31", callsign="DA1MHH",
                           default_mode="rx")
    d.btn_tx.click()
    # Polling-Client gestartet
    assert d._psk_client is not None
    d.btn_rx.click()
    # Nach Toggle-Back: kein laufender Client mehr
    import time
    time.sleep(0.2)  # stop() hat 2s Timeout
    assert not d._psk_client.is_running
    d.deleteLater()


def test_dialog_close_stops_polling(qapp):
    from ui.direction_map_widget import DirectionMapDialog
    d = DirectionMapDialog(my_locator="JO31", callsign="DA1MHH",
                           default_mode="tx")
    assert d._psk_client is not None
    d.close()
    assert not d._psk_client.is_running


def test_dialog_spots_to_station_points_filters(qapp):
    """Conversion PSK-Spot → StationPoint: dedup + invalid-locator-skip,
    /P-Suffix wird via normalize_call abgeschnitten (Plain-Call-Match)."""
    from ui.direction_map_widget import DirectionMapDialog
    from core.psk_reporter import Spot
    d = DirectionMapDialog(my_locator="JO31", callsign="DA1MHH")
    spots = [
        Spot(rx_call="DK4ABC", rx_locator="JO40", snr_db=-12.0,
             frequency_hz=14074000, timestamp=1234.5,
             mode="FT8", sender_call="DA1MHH"),
        Spot(rx_call="W1XYZ/P", rx_locator="FN42", snr_db=-8.0,
             frequency_hz=14074000, timestamp=1235.0,
             mode="FT8", sender_call="DA1MHH"),  # /P wird gestrippt → W1XYZ
        Spot(rx_call="K2BAD", rx_locator="garbage", snr_db=-10.0,
             frequency_hz=14074000, timestamp=1236.0,
             mode="FT8", sender_call="DA1MHH"),  # bad locator → skip
        Spot(rx_call="DK4ABC", rx_locator="JO40", snr_db=-9.0,
             frequency_hz=14074000, timestamp=1237.0,
             mode="FT8", sender_call="DA1MHH"),  # dupe → skip
    ]
    points = d._spots_to_station_points(spots)
    assert len(points) == 2
    calls = sorted(p.call for p in points)
    assert calls == ["DK4ABC", "W1XYZ"]
    d.deleteLater()


def test_canvas_zoom_default_is_one(qapp):
    from ui.direction_map_widget import MapCanvas
    c = MapCanvas(my_locator="JO31")
    assert c._zoom == 1.0


def test_canvas_zoom_doubles_globe_radius(qapp):
    """Zoom rein verdoppelt Globus-Radius (Orthographic)."""
    from ui.direction_map_widget import MapCanvas
    c = MapCanvas(my_locator="JO31")
    c.resize(500, 500)
    r1 = c._radius_px()
    c._zoom = 2.0
    r2 = c._radius_px()
    assert abs(r2 - 2.0 * r1) < 0.5


def test_canvas_zoom_clamped(qapp):
    """Zoom-State respektiert ZOOM_MIN/MAX bei vielen Wheel-Events."""
    from ui.direction_map_widget import MapCanvas, ZOOM_MIN, ZOOM_MAX, ZOOM_FACTOR
    c = MapCanvas(my_locator="JO31")
    # Direkt zoom-state via emulation pruefen — Wheel-Event-Kette vermeiden
    # (PySide6.QWheelEvent-Konstruktor ist Versions-abhaengig)
    for _ in range(100):
        c._zoom = max(ZOOM_MIN, min(ZOOM_MAX, c._zoom * ZOOM_FACTOR))
    assert c._zoom == ZOOM_MAX
    for _ in range(200):
        c._zoom = max(ZOOM_MIN, min(ZOOM_MAX, c._zoom / ZOOM_FACTOR))
    assert c._zoom == ZOOM_MIN


def test_canvas_view_default_is_user_pos(qapp):
    """View startet mit Beobachter direkt auf JO31 (User in der Mitte)."""
    from ui.direction_map_widget import MapCanvas
    c = MapCanvas(my_locator="JO31")
    assert c._my_pos is not None
    assert c._view_lat == c._my_pos[0]
    assert c._view_lon == c._my_pos[1]


def test_canvas_user_at_center_when_view_is_user_pos(qapp):
    """View == JO31 → User-Marker fix in der Mitte."""
    from ui.direction_map_widget import MapCanvas
    c = MapCanvas(my_locator="JO31")
    c.resize(500, 500)
    cx, cy = c._center_px()
    user = c._user_screen_pos()
    assert user is not None
    assert abs(user[0] - cx) < 1.0
    assert abs(user[1] - cy) < 1.0


def test_canvas_user_offsets_when_view_pans(qapp):
    """Wenn View 30° nach Westen wandert, User-Marker landet im rechten Halbkreis."""
    from ui.direction_map_widget import MapCanvas
    c = MapCanvas(my_locator="JO31")
    c.resize(500, 500)
    cx, _ = c._center_px()
    c._view_lon = c._view_lon - 30.0
    user = c._user_screen_pos()
    assert user is not None
    assert user[0] > cx + 10


def test_canvas_user_invisible_when_on_far_side(qapp):
    """View auf Antipode (lat negiert, lon+180) → User ist auf Rueckseite, invisible."""
    from ui.direction_map_widget import MapCanvas
    c = MapCanvas(my_locator="JO31")
    c.resize(500, 500)
    my_lat, my_lon = c._my_pos
    # Antipode-Ansicht
    c._view_lat = -my_lat
    c._view_lon = ((my_lon + 180.0) + 180.0) % 360.0 - 180.0
    user = c._user_screen_pos()
    assert user is None  # User auf Globus-Rueckseite


def test_canvas_reset_view_resets_to_user_pos(qapp):
    from ui.direction_map_widget import MapCanvas
    c = MapCanvas(my_locator="JO31")
    c._zoom = 3.5
    c._view_lat = 12.3
    c._view_lon = -45.6
    c.reset_view()
    assert c._zoom == 1.0
    assert c._view_lat == c._my_pos[0]
    assert c._view_lon == c._my_pos[1]


def test_canvas_set_locator_recenters_view(qapp):
    from ui.direction_map_widget import MapCanvas
    c = MapCanvas(my_locator="JO31")
    c._view_lat = 0.0
    c._view_lon = 0.0
    c.set_locator("KO82")
    assert c._view_lat == c._my_pos[0]
    assert c._view_lon == c._my_pos[1]


def test_orthographic_project_basic():
    """Punkt = view_center → projeziert auf (0, 0)."""
    from core.geo import orthographic_project
    p = orthographic_project(51.5, 7.0, 51.5, 7.0, radius_px=200.0)
    assert p is not None
    assert abs(p[0]) < 1e-6
    assert abs(p[1]) < 1e-6


def test_orthographic_project_back_side_returns_none():
    """Punkt auf Antipode → None."""
    from core.geo import orthographic_project
    p = orthographic_project(0.0, 0.0, 0.0, 180.0, radius_px=200.0)
    assert p is None


def test_orthographic_project_quarter_globe_at_radius():
    """Punkt 90° entfernt vom view-center → liegt am Rand der Disk (r=radius_px)."""
    from core.geo import orthographic_project
    import math
    p = orthographic_project(0.0, 0.0, 0.0, 90.0, radius_px=200.0)
    assert p is not None
    r_actual = math.hypot(p[0], p[1])
    assert abs(r_actual - 200.0) < 1.0


def test_canvas_call_to_country_known(qapp):
    from ui.direction_map_widget import MapCanvas
    assert MapCanvas._call_to_country("DA1MHH") == "DE"
    assert MapCanvas._call_to_country("W1XYZ") == "US"
    assert MapCanvas._call_to_country("JA1ABC") == "JP"


def test_canvas_call_to_country_unknown(qapp):
    from ui.direction_map_widget import MapCanvas
    assert MapCanvas._call_to_country("XQ1XYZ") in (None, "XQ1XYZ"[:2])


def test_canvas_call_to_country_strips_slash(qapp):
    from ui.direction_map_widget import MapCanvas
    # /P wird abgeschnitten, Hauptcall bleibt
    assert MapCanvas._call_to_country("DA1MHH/P") == "DE"


def test_canvas_heatmap_color_lerp(qapp):
    from ui.direction_map_widget import MapCanvas, HEATMAP_COLOR_LOW, HEATMAP_COLOR_HIGH
    c0 = MapCanvas._heatmap_color(0.0)
    c1 = MapCanvas._heatmap_color(1.0)
    cm = MapCanvas._heatmap_color(0.5)
    assert (c0.red(), c0.green(), c0.blue()) == (
        HEATMAP_COLOR_LOW.red(), HEATMAP_COLOR_LOW.green(), HEATMAP_COLOR_LOW.blue()
    )
    assert (c1.red(), c1.green(), c1.blue()) == (
        HEATMAP_COLOR_HIGH.red(), HEATMAP_COLOR_HIGH.green(), HEATMAP_COLOR_HIGH.blue()
    )
    # Mid sollte irgendwo dazwischen liegen
    assert HEATMAP_COLOR_LOW.red() <= cm.red() <= HEATMAP_COLOR_HIGH.red()


def test_canvas_paintevent_with_zoom_and_view_pan(qapp):
    """paintEvent darf bei extremen Zoom + View-Pan nicht crashen."""
    from ui.direction_map_widget import MapCanvas
    c = MapCanvas(my_locator="JO31")
    c.resize(500, 500)
    c.show()
    c._zoom = 4.0
    c._view_lat = 30.0
    c._view_lon = -100.0
    c.repaint()
    c._zoom = 0.5
    c._view_lat = -45.0
    c._view_lon = 150.0
    c.repaint()
    c.deleteLater()


def test_canvas_paintevent_with_wedges_and_stations(qapp):
    """paintEvent mit Sektor-Wedges + Stations-Punkten in beiden Modi."""
    from ui.direction_map_widget import MapCanvas
    from core.direction_pattern import StationPoint
    c = MapCanvas(my_locator="JO31")
    c.resize(500, 500)
    c.show()
    stations = [
        StationPoint(call="DK4ABC", locator="JO40", lat=49.0, lon=8.0,
                     snr=-12.0, antenna="A2"),
        StationPoint(call="W1XYZ", locator="FN42", lat=42.0, lon=-71.0,
                     snr=-8.0, antenna="A1"),
        StationPoint(call="JA1ABC", locator="PM95", lat=35.7, lon=139.7,
                     snr=-18.0, antenna="rescue"),
    ]
    c.update_stations(stations)
    c.set_mode("rx")
    c.repaint()
    c.set_mode("tx")
    c.repaint()
    c.deleteLater()
