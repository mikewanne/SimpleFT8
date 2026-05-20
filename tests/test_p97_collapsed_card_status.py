"""P97 (20.05.2026, v0.97.69) — Collapsed Card Status-Suffix.

Mike-Wunsch 20.05.2026: bei eingeklappter Antennen-/Radio-Kachel
soll im Header neben „ANTENNE"/„RADIO" der aktuelle Modus bzw. die
aktuelle Sendeleistung als Suffix sichtbar bleiben.

Test-Coverage:
- T1: ANTENNE-Status default „— Normal" (initial RX-Modus normal)
- T2: nach set_rx_mode('diversity') → „— Diversity Standard"
- T3: update_diversity_ratio(scoring='dx') → „— Diversity DX"
- T4: zurück zu normal → „— Normal"
- T5: RADIO-Status default „— 10 W" (initial-Power 10W)
- T6: set_power_preset(70) → „— 70 W"
- T7: _on_power_preset_clicked(50) → „— 50 W"
- T8: Schriftfarbe Antenne-Status = #55BBAA (gleich wie ANTENNE)
- T9: Schriftfarbe Radio-Status = #00aacc (gleich wie RADIO)
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def panel(app):
    from ui.control_panel import ControlPanel
    return ControlPanel()


# ── Antenne-Card Status ────────────────────────────────────────────


def test_t1_antenna_status_default_normal(panel):
    assert panel._antenne_card_status_label.text() == "— Normal"


def test_t2_antenna_status_diversity_standard(panel):
    panel.set_rx_mode("diversity")
    assert panel._antenne_card_status_label.text() == "— Diversity Standard"


def test_t3_antenna_status_diversity_dx(panel):
    panel.set_rx_mode("diversity")
    panel.update_diversity_ratio("30:70", scoring_mode="dx")
    assert panel._antenne_card_status_label.text() == "— Diversity DX"


def test_t4_antenna_status_back_to_normal(panel):
    panel.set_rx_mode("diversity")
    panel.update_diversity_ratio("30:70", scoring_mode="dx")
    panel.set_rx_mode("normal")
    assert panel._antenne_card_status_label.text() == "— Normal"


# ── Radio-Card Status ──────────────────────────────────────────────


def test_t5_radio_status_default_10w(panel):
    assert panel._radio_card_status_label.text() == "— 10 W"


def test_t6_radio_status_after_set_preset(panel):
    panel.set_power_preset(70)
    assert panel._radio_card_status_label.text() == "— 70 W"


def test_t7_radio_status_after_click(panel):
    panel._on_power_preset_clicked(50)
    assert panel._radio_card_status_label.text() == "— 50 W"


# ── Schriftfarben (dezent, gleich wie Header-Label) ──────────────


def test_t8_antenna_status_color_matches_header(panel):
    ss = panel._antenne_card_status_label.styleSheet()
    assert "#55BBAA" in ss, "P97: Antenne-Status muss #55BBAA sein"


def test_t9_radio_status_color_matches_header(panel):
    ss = panel._radio_card_status_label.styleSheet()
    assert "#00aacc" in ss, "P97: Radio-Status muss #00aacc sein"


# ── Diversity-Sub-Toggle Std↔DX im Live-Betrieb ──────────────────


def test_t10_scoring_toggle_updates_status(panel):
    panel.set_rx_mode("diversity")
    panel.update_diversity_ratio("50:50", scoring_mode="normal")
    assert panel._antenne_card_status_label.text() == "— Diversity Standard"
    panel.update_diversity_ratio("70:30", scoring_mode="dx")
    assert panel._antenne_card_status_label.text() == "— Diversity DX"
    panel.update_diversity_ratio("50:50", scoring_mode="normal")
    assert panel._antenne_card_status_label.text() == "— Diversity Standard"
