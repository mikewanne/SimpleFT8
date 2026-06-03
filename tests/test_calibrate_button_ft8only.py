"""v0.99.2 — DT-Kalibrier-Knopf (⏱) nur auf FT8 sichtbar.

Mike-Wunsch: auf FT4 (und spaeter FT2) den ⏱-Knopf ausblenden, damit man nicht
versehentlich draufklickt — DT wird ausschliesslich aus FT8 gemessen.

`isHidden()` statt `isVisible()`: spiegelt das explizite Sichtbarkeits-Flag
unabhaengig davon ob das Widget je `.show()` gesehen hat (offscreen).
"""
from __future__ import annotations

import inspect

import pytest
from PySide6.QtWidgets import QApplication


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def test_calibrate_button_visible_by_default(qapp):
    """RXPanel startet mit sichtbarem ⏱-Knopf (App-Start = FT8)."""
    from ui.rx_panel import RXPanel
    panel = RXPanel()
    assert panel.btn_calibrate.isHidden() is False


def test_set_calibrate_visible_hides_and_shows(qapp):
    from ui.rx_panel import RXPanel
    panel = RXPanel()
    panel.set_calibrate_visible(False)
    assert panel.btn_calibrate.isHidden() is True
    panel.set_calibrate_visible(True)
    assert panel.btn_calibrate.isHidden() is False


def test_mode_change_wires_calibrate_visibility():
    """mw_radio._on_mode_changed schaltet den Knopf mode-abhaengig (FT8) —
    Source-Check, damit ein Refactor die Verdrahtung nicht still verliert."""
    from ui.mw_radio import RadioMixin
    src = inspect.getsource(RadioMixin._on_mode_changed)
    assert "set_calibrate_visible" in src
    assert 'mode == "FT8"' in src


def test_main_window_sets_initial_calibrate_visibility():
    """main_window setzt die Initial-Sichtbarkeit mode-abhaengig (Source-Check)."""
    import ui.main_window as mw
    src = inspect.getsource(mw)
    assert "set_calibrate_visible" in src
