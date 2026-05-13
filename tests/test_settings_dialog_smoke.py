"""Smoke-Tests fuer SettingsDialog (Tab-basiert seit v0.76).

Prueft:
- Dialog hat 4 Tabs.
- Alle Widget-Attribute sind erreichbar (auch wenn sie in versch. Tabs leben).
- Dialog-Hoehe bleibt unter 750 px (Mike's 1440x900-Limit).
- Save-Round-Trip schreibt Werte korrekt in Settings.
"""

import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from PySide6.QtWidgets import QApplication, QTabWidget
from ui.settings_dialog import SettingsDialog


class _FakeSettings:
    """Minimaler Settings-Mock — dict-basiert mit Property-Aliasen."""

    def __init__(self):
        self._d = {
            "callsign": "TEST",
            "locator": "JN58XB",
            "flexradio_ip": "",
            "power_watts": 50,
            "tx_level": 100,
            "max_calls": 3,
            "swr_limit": 3.0,
            "tune_power": 10,
            "language": "de",
            "stats_enabled": True,
            "debug_console_visible": False,
        }

    def get(self, key, default=None):
        return self._d.get(key, default)

    def set(self, key, val):
        self._d[key] = val

    def save(self):
        pass

    @property
    def callsign(self):
        return self._d["callsign"]

    @property
    def locator(self):
        return self._d["locator"]

    @property
    def power_watts(self):
        return self._d["power_watts"]


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def dlg(qapp):
    settings = _FakeSettings()
    dialog = SettingsDialog(settings, parent=None)
    yield dialog
    dialog.close()
    dialog.deleteLater()


def test_dialog_has_tabs_attribute(dlg):
    """`self.tabs` existiert und hat 4 Tabs."""
    assert hasattr(dlg, "tabs")
    assert isinstance(dlg.tabs, QTabWidget)
    assert dlg.tabs.count() == 4
    # Tab-Header-Texte
    assert dlg.tabs.tabText(0) == "Station"
    assert dlg.tabs.tabText(1) == "TX & Schutz"
    assert dlg.tabs.tabText(2) == "FT8 & Diversity"
    assert dlg.tabs.tabText(3) == "Daten & Tools"


def test_widget_attributes_accessible(dlg):
    """Alle Widget-Attribute sind erreichbar (egal in welchem Tab)."""
    expected_attrs = [
        "callsign", "locator", "radio_ip",
        "power", "tx_level", "max_calls_combo", "swr_limit",
        "language_combo", "stats_cb", "debug_console_cb",
        "_tune_btns", "_current_tune_power",
        "rf_table", "_rf_band_combo",
        "btn_rf_clear_band", "btn_rf_clear_all", "_rf_info_label",
        "_tx_status_timer", "_export_csv_btn", "_map_open_btn",
        "tabs",
        # v0.88 Bandpilot Stunden-Logik
        "bandpilot_mode_combo",
    ]
    for attr in expected_attrs:
        assert hasattr(dlg, attr), f"Fehlt: {attr}"


def test_bandpilot_save_round_trip(dlg):
    """Bandpilot-Mode-Combo ueberlebt _save_and_close → Settings."""
    dlg.bandpilot_mode_combo.setCurrentIndex(2)  # Manuell
    dlg.accept = lambda: None
    dlg._save_and_close()
    assert dlg.settings.get("bandpilot_mode") == "manual"


def test_bandpilot_load_values_from_settings(qapp):
    """Bandpilot-Mode aus Settings wird korrekt im Dialog initialisiert."""
    settings = _FakeSettings()
    settings.set("bandpilot_mode", "auto")
    dlg = SettingsDialog(settings, parent=None)
    try:
        assert dlg.bandpilot_mode_combo.currentIndex() == 1  # auto
    finally:
        dlg.close()
        dlg.deleteLater()


def test_dialog_height_within_limit(dlg, qapp):
    """Dialog-Hoehe ≤ 750 px (1440x900-Display-Limit)."""
    dlg.show()
    qapp.processEvents()
    assert dlg.height() <= 750, f"Dialog zu hoch: {dlg.height()} px"
    dlg.hide()


def test_save_round_trip(dlg):
    """Werte aendern → _save_and_close() → in Settings persistiert."""
    dlg.callsign.setText("DA1MHH")
    dlg.power.setValue(75)
    dlg.language_combo.setCurrentIndex(1)  # English

    # accept() per Monkey-Patch entschaerfen (sonst schliesst Dialog)
    dlg.accept = lambda: None
    dlg._save_and_close()

    assert dlg.settings.get("callsign") == "DA1MHH"
    assert dlg.settings.get("power_watts") == 75
    assert dlg.settings.get("language") == "en"


def test_initial_tab_is_station(dlg):
    """Beim Oeffnen ist Tab 0 (Station) aktiv."""
    assert dlg.tabs.currentIndex() == 0
