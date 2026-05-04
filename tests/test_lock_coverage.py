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


# ───── Reihenfolge: Lock VOR Reset (test 6) ────────────────────────────


def test_enable_diversity_locks_before_reset():
    """_enable_diversity ruft _set_gain_measure_lock(True) VOR _diversity_ctrl.reset().

    Schuetzt gegen Race-Window in dem laufende Slots ins frische
    _measurements-Bucket schreiben koennten (R1-Audit Befund 3).

    Verifikation via call-tracking auf einem gemeinsamen Manager-Mock.
    """
    s = MagicMock()
    s._radio = MagicMock()
    s._radio.ip = None  # Pfad ohne Radio-Setup
    s.settings.mode = "FT8"
    s.settings.band = "40m"
    s._dx_store = MagicMock()
    s._dx_store.get.return_value = None  # Kein Preset → einfacher Pfad
    s._standard_store = MagicMock()
    s._standard_store.get.return_value = None
    s._diversity_in_operate = False
    s._tune_token = None

    # Manager-Mock fuer call-Reihenfolge
    manager = MagicMock()
    s._diversity_ctrl = manager.diversity_ctrl
    s._set_cq_locked = manager.cq_lock
    s._set_gain_measure_lock = manager.gain_lock

    # _enable_diversity ruft viele weitere Methoden — die ignorieren wir
    try:
        RadioMixin._enable_diversity(s, "normal")
    except (AttributeError, TypeError):
        # Methode bricht eventuell auf Mock-Limit ab, aber die ersten
        # 3 Aufrufe (cq_lock, gain_lock, reset) sollten geloggt sein.
        pass

    # Reihenfolge der manager-Aufrufe extrahieren
    call_names = [c[0] for c in manager.mock_calls if c[0]]

    # Erwartet: cq_lock(True), gain_lock(True), diversity_ctrl.reset() —
    # in dieser Reihenfolge irgendwo am Anfang
    cq_idx = next((i for i, n in enumerate(call_names) if n == "cq_lock"), None)
    gain_idx = next((i for i, n in enumerate(call_names) if n == "gain_lock"), None)
    reset_idx = next((i for i, n in enumerate(call_names)
                      if n == "diversity_ctrl.reset"), None)

    assert cq_idx is not None, f"cq_lock nicht aufgerufen: {call_names}"
    assert gain_idx is not None, f"gain_lock nicht aufgerufen: {call_names}"
    assert reset_idx is not None, f"reset nicht aufgerufen: {call_names}"

    # KRITISCH: Lock vor Reset
    assert gain_idx < reset_idx, (
        f"gain_lock (idx {gain_idx}) muss VOR reset (idx {reset_idx}) sein. "
        f"Call-Reihenfolge: {call_names}"
    )
