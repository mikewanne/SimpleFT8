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
