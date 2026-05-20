"""P96 (20.05.2026, v0.97.68) — Power-Button-Farbe permanent bei Hover.

Mike-Beobachtung 20.05.: ausgewählter Watt-Button (z.B. 70W) verlor
beim Mouse-Over die Farbe (wurde schwarz) → wirkte wie Toggle-Aus.

Ursache: Qt-CSS-Spezifität. `:hover` und `:checked` haben dieselbe
Spezifität; bei gleichgewichtigen Selektoren gewinnt der zuletzt
definierte. Im alten Stylesheet kam `:hover` NACH `:checked` →
hat das Auswahl-Styling überschrieben.

Fix: expliziter `:checked:hover` Selektor (höhere Spezifität durch
Kombination) hält die Auswahl-Farbe auch beim Hover.
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


def test_power_btn_has_checked_hover_selector(app):
    """P96: jedes power_button-Stylesheet enthält :checked:hover Selektor."""
    from ui.control_panel import ControlPanel
    panel = ControlPanel()
    for watts, btn in panel.power_buttons.items():
        ss = btn.styleSheet()
        assert "QPushButton:checked:hover" in ss, (
            f"P96: power_buttons[{watts}] hat keinen :checked:hover-Selektor")


def test_power_btn_checked_hover_keeps_active_bg(app):
    """P96: :checked:hover hat dieselbe background-Farbe wie :checked."""
    import re
    from ui.control_panel import ControlPanel
    panel = ControlPanel()
    btn = panel.power_buttons[70]
    ss = btn.styleSheet()
    # Extrahiere :checked und :checked:hover Blocks
    checked_match = re.search(
        r"QPushButton:checked\s*\{[^}]*background:\s*([^;]+);", ss)
    checked_hover_match = re.search(
        r"QPushButton:checked:hover\s*\{[^}]*background:\s*([^;]+);", ss)
    assert checked_match and checked_hover_match
    assert checked_match.group(1).strip() == checked_hover_match.group(1).strip(), (
        "P96: :checked:hover background muss identisch mit :checked sein")


def test_power_btn_hover_selector_before_checked(app):
    """P96: :hover-Selektor steht VOR :checked damit :checked nicht
    übermalt wird (Qt last-defined-wins-Regel)."""
    from ui.control_panel import ControlPanel
    panel = ControlPanel()
    ss = panel.power_buttons[50].styleSheet()
    hover_pos = ss.find("QPushButton:hover ")
    checked_pos = ss.find("QPushButton:checked ")
    assert hover_pos != -1 and checked_pos != -1
    assert hover_pos < checked_pos, (
        "P96: :hover muss VOR :checked stehen — last-defined-wins")
