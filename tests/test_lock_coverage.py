"""Tests fuer v0.92 Lock-Coverage-Audit.

Pruefen:
- _gain_measure_locked Flag wird in _set_gain_measure_lock gesetzt/zurueckgesetzt
- _on_band_changed: Frueh-Return wenn Lock aktiv (UI-Button zurueck-gesynct)
- _on_mode_changed: gleiches
- _on_rx_mode_changed: gleiches (R1-Audit-Finding)
- _enable_diversity: Reihenfolge — Lock VOR _diversity_ctrl.reset()

Whitebox-Tests via unbound-method-Aufruf mit MagicMock-self
(Pattern aus test_mw_radio_bandpilot.py).
"""
from unittest.mock import MagicMock, patch

import pytest

from ui.mw_radio import RadioMixin


@pytest.fixture(scope="module")
def qapp():
    """Qt Application Instance — module-scoped (1× pro Test-Modul)."""
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app


def _make_mock_self(*, gain_locked: bool = False, band: str = "40m",
                    mode: str = "FT8", rx_mode: str = "diversity"):
    """Mock-Objekt mit den fuer Lock-Tests noetigen Attributen."""
    self_mock = MagicMock()
    self_mock._gain_measure_locked = gain_locked
    self_mock.settings.band = band
    self_mock.settings.mode = mode
    self_mock._rx_mode = rx_mode
    return self_mock


# ───── Flag-Setter (test 1+2) ──────────────────────────────────────────


def test_lock_flag_set_when_locked():
    """_set_gain_measure_lock(True) → _gain_measure_locked == True."""
    s = MagicMock()
    s.control_panel.band_buttons = {}
    # Stub statusBar() für showMessage-Aufruf
    s.statusBar = MagicMock()

    RadioMixin._set_gain_measure_lock(s, True)

    assert s._gain_measure_locked is True


def test_lock_flag_cleared_when_unlocked():
    """_set_gain_measure_lock(False) → _gain_measure_locked == False."""
    s = MagicMock()
    s.control_panel.band_buttons = {}
    s.statusBar = MagicMock()

    RadioMixin._set_gain_measure_lock(s, False)

    assert s._gain_measure_locked is False


# ───── Band/Mode/RX-Mode Frueh-Return (test 3+4+5) ────────────────────


def test_band_change_blocked_during_lock():
    """_on_band_changed mit Lock=True → Frueh-Return, settings.set NICHT aufgerufen."""
    s = _make_mock_self(gain_locked=True, band="40m")

    RadioMixin._on_band_changed(s, "20m")

    # Frueh-Return: settings.set("band", ...) darf NICHT aufgerufen werden
    s.settings.set.assert_not_called()
    # UI-Sync: control_panel._set_band("40m") MUSS aufgerufen werden
    s.control_panel._set_band.assert_called_once_with("40m")


def test_mode_change_blocked_during_lock():
    """_on_mode_changed mit Lock=True → Frueh-Return, kein settings/decoder Setup."""
    s = _make_mock_self(gain_locked=True, mode="FT8")

    RadioMixin._on_mode_changed(s, "FT4")

    s.settings.set.assert_not_called()
    s.control_panel._set_mode.assert_called_once_with("FT8")


def test_rx_mode_change_blocked_during_lock():
    """_on_rx_mode_changed mit Lock=True → Frueh-Return, kein _disable_diversity."""
    s = _make_mock_self(gain_locked=True, rx_mode="diversity")

    RadioMixin._on_rx_mode_changed(s, "normal")

    # _disable_diversity darf NICHT aufgerufen werden bei Lock-Block
    s._disable_diversity.assert_not_called()
    # UI-Sync: control_panel.set_rx_mode("diversity") MUSS aufgerufen werden
    s.control_panel.set_rx_mode.assert_called_once_with("diversity")


# P34-Stufe2: test_enable_diversity_locks_before_reset entfernt — keine
# Statik-Mess-Phase mehr, daher kein Lock-vor-Reset-Race-Window. Locks
# werden in _enable_diversity nur noch auf False gesetzt (Aufhebung).
