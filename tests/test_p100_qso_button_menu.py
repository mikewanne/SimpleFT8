"""P100 (21.05.2026, v0.97.72) — QSO-Button Kontextmenü + Padding-Fix.

Mike-Spec 21.05.: Rechtsklick auf QSO-Tab-Button soll dasselbe Spalten-
Toggle-Menü öffnen wie der Log-Bereich. Copy/SelectAll raus. QMenu
Padding rechts 20→32px (Häkchen saßen optisch am Rand) — auch im
RX-Panel-Spaltenauswahl- und Länder-Filter-Menü.

Tests:
- T1: QSO-Button hat ContextMenuPolicy.CustomContextMenu
- T2: Signal-Connect auf QSO-Button (customContextMenuRequested)
- T3: _build_columns_menu liefert Menü mit 2 Actions, beide checkable
- T4: Actions im Builder = Even/Odd-Tag + Antennen-Anzeige (Reihenfolge)
- T5: Toggle aus Builder-Menü wirkt + emit Signal (Hook-Test)
- T6: _on_log_context_menu nutzt _build_columns_menu (kein Copy/SelectAll)
- T7: _on_qso_button_context_menu nutzt _build_columns_menu
- T8: qso_panel-Stylesheet padding rechts = 32px
- T9: rx_panel Spaltenmenü-Stylesheet padding rechts = 32px (Source-Check)
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def panel(app):
    from ui.qso_panel import QSOPanel
    return QSOPanel()


# ── QSO-Button Kontextmenü ──────────────────────────────────────────


def test_t1_qso_button_has_custom_context_menu_policy(panel):
    assert panel._btn_tab_qso.contextMenuPolicy() == (
        Qt.ContextMenuPolicy.CustomContextMenu)


def test_t2_qso_button_signal_emits_calls_handler(panel, monkeypatch):
    """Signal emittieren → _on_qso_button_context_menu muss gerufen werden."""
    from PySide6.QtCore import QPoint
    called = []
    monkeypatch.setattr(
        panel, "_on_qso_button_context_menu",
        lambda pos: called.append(pos))
    # Re-connect auf gepatchte Methode (Original-Connect zeigt noch auf Bound-Method)
    panel._btn_tab_qso.customContextMenuRequested.disconnect()
    panel._btn_tab_qso.customContextMenuRequested.connect(
        panel._on_qso_button_context_menu)
    panel._btn_tab_qso.customContextMenuRequested.emit(QPoint(10, 5))
    assert len(called) == 1


# ── _build_columns_menu Builder ─────────────────────────────────────


def test_t3_builder_returns_two_actions_not_checkable(panel):
    """P102: Actions nicht checkable (Häkchen manuell im Text)."""
    menu = panel._build_columns_menu()
    actions = menu.actions()
    assert len(actions) == 2
    assert all(not a.isCheckable() for a in actions), (
        "P102: setCheckable(False) — kein Qt-Default-Indikator")


def test_t4_builder_action_labels_contain_text(panel):
    """P102: Labels mit Häkchen-Prefix oder Whitespace-Padding."""
    menu = panel._build_columns_menu()
    labels = [a.text() for a in menu.actions()]
    assert "Even/Odd-Tag" in labels[0]
    assert "Antennen-Anzeige" in labels[1]


def test_t5_builder_action_trigger_toggles_state(panel):
    """P102: trigger() ruft _toggle_eo_tag(not current_state)."""
    received = []
    panel.eo_tag_visibility_changed.connect(received.append)
    panel._show_eo_tag = True  # Ausgangslage
    menu = panel._build_columns_menu()
    a_eo = menu.actions()[0]
    a_eo.trigger()
    assert received == [False]  # flippt von True auf False
    assert panel._show_eo_tag is False
    assert panel._show_eo_tag is False


# ── Kein Copy/SelectAll mehr ─────────────────────────────────────────


def test_t6_log_context_menu_no_standard_actions():
    """_on_log_context_menu darf createStandardContextMenu NICHT mehr nutzen."""
    src = Path(__file__).resolve().parent.parent / "ui" / "qso_panel.py"
    text = src.read_text(encoding="utf-8")
    # Methode _on_log_context_menu isolieren
    m = re.search(r"def _on_log_context_menu\(self, pos\):.*?(?=\n    def )",
                  text, re.DOTALL)
    assert m, "_on_log_context_menu nicht gefunden"
    body = m.group(0)
    assert "createStandardContextMenu" not in body, (
        "P100: Copy/SelectAll muss raus aus _on_log_context_menu")
    assert "_build_columns_menu" in body, (
        "P100: _on_log_context_menu muss _build_columns_menu nutzen")


def test_t7_qso_button_context_menu_uses_builder():
    src = Path(__file__).resolve().parent.parent / "ui" / "qso_panel.py"
    text = src.read_text(encoding="utf-8")
    m = re.search(r"def _on_qso_button_context_menu\(self, pos\):.*?(?=\n    def )",
                  text, re.DOTALL)
    assert m, "_on_qso_button_context_menu nicht gefunden"
    body = m.group(0)
    assert "_build_columns_menu" in body
    assert "createStandardContextMenu" not in body


# ── Padding-Fix ──────────────────────────────────────────────────────


def test_t8_qso_panel_menu_indicator_hidden_text_checkmark():
    """P102 (v0.97.78 nach Mike-Field-Test): Indicator versteckt
    (width:0), Häkchen über Action-Text-Prefix. Pixelgenaue Kontrolle."""
    src = Path(__file__).resolve().parent.parent / "ui" / "qso_panel.py"
    text = src.read_text(encoding="utf-8")
    m = re.search(r"def _build_columns_menu\(self\):.*?(?=\n    def )",
                  text, re.DOTALL)
    assert m
    body = m.group(0)
    assert "padding: 4px 20px 4px 8px" in body, "P102: padding-left 8px"
    assert "QMenu::indicator { width: 0px" in body, (
        "P102: Indicator versteckt")
    assert '✓' in body, "P102: Häkchen-Symbol manuell im Action-Text"
    assert "setCheckable(False)" in body, (
        "P102: kein Qt-Default-Indikator (Text trägt Häkchen)")


def test_t9_rx_panel_menu_indicator_hidden_text_checkmark():
    """P102: RX-Panel beide Menüs analog mit verstecktem Indicator."""
    src = Path(__file__).resolve().parent.parent / "ui" / "rx_panel.py"
    text = src.read_text(encoding="utf-8")
    new_pad = text.count("padding: 4px 20px 4px 8px")
    hidden = text.count("QMenu::indicator { width: 0px")
    old_pad = text.count("padding: 4px 20px 4px 32px")
    old_margin = text.count("margin-left: 8px")
    assert new_pad >= 2, (
        f"P102: RX-Panel 2× `4px 20px 4px 8px`, gefunden: {new_pad}")
    assert hidden >= 2, (
        f"P102: RX-Panel 2× versteckter Indicator, gefunden: {hidden}")
    assert old_pad == 0, "P102: alte 32-Variante muss raus"
    assert old_margin == 0, "P102: alte margin-left:8 muss raus"
