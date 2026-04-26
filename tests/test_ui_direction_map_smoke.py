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
