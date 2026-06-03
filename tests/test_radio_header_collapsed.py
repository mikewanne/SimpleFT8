"""v0.99.0 — Eingeklappter RADIO-Header zeigt beim Senden Netto-Watt + farbiges SWR.

Mike-Wunsch: bei eingeklappter RADIO-Kachel auch sehen, was rausgeht. Format:
  Senden:  „— 70 → 58 W · SWR 1.2"  (SWR farbig per Ampel)
  Empfang: „— 70 W"                  (kein TX → nur eingestellt)

Der Zusatz haengt am selben `_last_watt > 0`-Guard wie die Body-Netto-Anzeige
(`_refresh_netto`); im RX faellt FWDPWR ueber den Meter auf ~0 → Zusatz weg.
"""
from __future__ import annotations

import pytest
from PySide6.QtWidgets import QApplication

from ui.control_panel import swr_color, compute_net_power


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


# ── Ampel-Helper (pure) ───────────────────────────────────────────────────
def test_swr_color_green():
    assert swr_color(1.0) == "#44FF44"
    assert swr_color(1.49) == "#44FF44"


def test_swr_color_yellow():
    assert swr_color(1.5) == "#FFD700"
    assert swr_color(2.49) == "#FFD700"


def test_swr_color_red():
    assert swr_color(2.5) == "#FF4444"
    assert swr_color(10.0) == "#FF4444"


# ── Header-Logik ──────────────────────────────────────────────────────────
def test_rx_shows_only_setting(qapp):
    """Empfang (last_watt=0) → nur eingestellte Leistung, kein SWR/Netto."""
    from ui.control_panel import ControlPanel
    cp = ControlPanel()
    cp._current_power_watts = 80
    cp.update_watt(0)                      # RX → _last_watt=0
    txt = cp._radio_card_status_label.text()
    assert txt == "— 80 W"
    assert "SWR" not in txt


def test_tx_shows_netto_and_colored_swr(qapp):
    """Senden (last_watt>0) → „— {set} → {netto} W · SWR x.x" mit Ampel-Farbe."""
    from ui.control_panel import ControlPanel
    cp = ControlPanel()
    cp._current_power_watts = 80
    cp.update_swr(1.2)                      # gruen
    cp.update_watt(70)                      # TX
    txt = cp._radio_card_status_label.text()
    netto = compute_net_power(70, 1.2)
    assert "→" in txt
    assert f"{netto} W" in txt
    assert "SWR 1.2" in txt
    assert "#44FF44" in txt                 # gruen (SWR<1.5)
    assert "80" in txt                      # eingestellte Leistung


def test_tx_high_swr_red(qapp):
    """Hohes SWR → roter SWR-Teil im Header."""
    from ui.control_panel import ControlPanel
    cp = ControlPanel()
    cp._current_power_watts = 70
    cp.update_swr(2.6)
    cp.update_watt(70)
    txt = cp._radio_card_status_label.text()
    assert "#FF4444" in txt
    assert "SWR 2.6" in txt


def test_tx_without_preset_no_arrow(qapp):
    """Power None aber TX aktiv → Netto+SWR ohne „→"-Praefix."""
    from ui.control_panel import ControlPanel
    cp = ControlPanel()
    cp._current_power_watts = None
    cp.update_swr(1.2)
    cp.update_watt(70)
    txt = cp._radio_card_status_label.text()
    assert "→" not in txt
    assert "SWR 1.2" in txt
    assert f"{compute_net_power(70, 1.2)} W" in txt


def test_tx_end_reverts_to_setting(qapp):
    """TX endet (Meter FWDPWR→0) → Header zurueck auf „— {set} W"."""
    from ui.control_panel import ControlPanel
    cp = ControlPanel()
    cp._current_power_watts = 80
    cp.update_swr(1.2)
    cp.update_watt(70)
    assert "SWR" in cp._radio_card_status_label.text()
    cp.update_watt(0)                      # TX-Ende
    assert cp._radio_card_status_label.text() == "— 80 W"


def test_reset_swr_reverts_header(qapp):
    """reset_swr_display (Bandwechsel) → Header zurueck auf „— {set} W"."""
    from ui.control_panel import ControlPanel
    cp = ControlPanel()
    cp._current_power_watts = 80
    cp.update_swr(2.6)
    cp.update_watt(70)
    assert "SWR" in cp._radio_card_status_label.text()
    cp.reset_swr_display()
    assert cp._radio_card_status_label.text() == "— 80 W"


def test_power_none_rx_empty(qapp):
    """Power None + RX → leerer Header."""
    from ui.control_panel import ControlPanel
    cp = ControlPanel()
    cp._current_power_watts = None
    cp.update_watt(0)
    assert cp._radio_card_status_label.text() == ""
