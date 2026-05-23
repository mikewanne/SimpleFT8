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


# ── P97-Update v0.97.71: Status-Label NUR bei collapsed sichtbar ─


def test_t11_antenna_status_visible_only_when_collapsed(panel):
    """Mike-Spec 20.05.: bei aufgeklappter Kachel sieht man Mode-Buttons
    im Body — Status-Suffix wäre doppelt. Daher nur bei collapsed zeigen.

    Offscreen-Test nutzt `isHidden()` statt `isVisible()` (Widget ist
    nicht in einem geshow'ten Parent → isVisible() wäre immer False).
    """
    panel._ant_card.set_collapsed(False)
    assert panel._antenne_card_status_label.isHidden(), (
        "Aufgeklappte Kachel: Status-Label muss versteckt (hidden) sein")
    panel._ant_card.set_collapsed(True)
    assert not panel._antenne_card_status_label.isHidden(), (
        "Eingeklappte Kachel: Status-Label darf NICHT hidden sein")


def test_t12_radio_status_visible_only_when_collapsed(panel):
    """Analog Radio-Kachel: Power-Buttons zeigen Wattzahl im Body."""
    panel._radio_card.set_collapsed(False)
    assert panel._radio_card_status_label.isHidden(), (
        "Aufgeklappte Kachel: Radio-Status muss versteckt (hidden) sein")
    panel._radio_card.set_collapsed(True)
    assert not panel._radio_card_status_label.isHidden(), (
        "Eingeklappte Kachel: Radio-Status darf NICHT hidden sein")


# ── P102 (23.05.2026, v0.97.97): User-Klick-Pfad-Sync ───────────────
#
# Mike-Field-Bug 23.05.2026: NORMAL aktiv, Kachel eingeklappt zeigt
# faelschlich „— Diversity Standard". Ursache: `_on_rx_mode_clicked`
# (User-Klick-Pfad) hat im Gegensatz zu `set_rx_mode` (programmatischer
# Pfad, Z. 1725) keinen `_refresh_antenna_status_label()`-Aufruf — Label
# blieb stale auf letztem `update_diversity_ratio`-Wert.


def test_t0_click_normal_when_already_normal_no_crash(panel):
    """P102: Early-Return-Pfad — Klick NORMAL bei _current_rx_mode='normal'
    darf nicht crashen, Label bleibt 'Normal'."""
    assert panel._current_rx_mode == "normal"
    panel._on_rx_mode_clicked("normal")
    assert panel._antenne_card_status_label.text() == "— Normal"


def test_t13_click_diversity_updates_label_immediately(panel):
    """P102: User-Klick DIVERSITY aktualisiert Label sofort
    (vorher nur via naechsten Cycle ueber update_diversity_ratio)."""
    panel._on_rx_mode_clicked("diversity")
    assert panel._antenne_card_status_label.text() == "— Diversity Standard"


def test_t14_click_back_to_normal_updates_label(panel):
    """P102: Reproduktion Mike-Bug 23.05.2026 — Klick Diversity, dann
    Klick Normal: Label muss 'Normal' zeigen (vorher blieb stale)."""
    panel._on_rx_mode_clicked("diversity")
    panel._on_rx_mode_clicked("normal")
    assert panel._antenne_card_status_label.text() == "— Normal"


def test_t15_click_back_to_normal_after_dx_scoring(panel):
    """P102 Edge: nach Diversity DX scoring → Klick Normal muss Label
    auf 'Normal' setzen (auch wenn _current_scoring_mode noch 'dx' ist).
    Der Refresh-Helper liest bei rx_mode='normal' den scoring gar nicht."""
    panel._on_rx_mode_clicked("diversity")
    panel.update_diversity_ratio("70:30", scoring_mode="dx")
    assert panel._antenne_card_status_label.text() == "— Diversity DX"
    panel._on_rx_mode_clicked("normal")
    assert panel._antenne_card_status_label.text() == "— Normal"
