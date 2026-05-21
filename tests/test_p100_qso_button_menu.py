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


def test_t3_builder_returns_two_checkable_actions(panel):
    menu = panel._build_columns_menu()
    actions = menu.actions()
    assert len(actions) == 2
    assert all(a.isCheckable() for a in actions)


def test_t4_builder_action_labels_and_order(panel):
    menu = panel._build_columns_menu()
    labels = [a.text() for a in menu.actions()]
    assert labels == ["Even/Odd-Tag", "Antennen-Anzeige"]


def test_t5_builder_action_toggle_emits_signal(panel):
    """Toggle aus Builder-Menü muss eo_tag_visibility_changed feuern.

    QAction.trigger() flippt bei checkable=True automatisch — Action wird
    initial mit setChecked(self._show_eo_tag=True) gebaut, trigger() macht
    daraus False und emittet triggered(False).
    """
    received = []
    panel.eo_tag_visibility_changed.connect(received.append)
    panel._show_eo_tag = True  # Ausgangslage
    menu = panel._build_columns_menu()
    a_eo = menu.actions()[0]
    assert a_eo.isChecked() is True
    a_eo.trigger()  # flippt auf False + emit triggered(False)
    assert received == [False]
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


def test_t8_qso_panel_menu_padding_right_32():
    """Builder-Stylesheet muss `padding: 4px 32px 4px 28px` enthalten."""
    src = Path(__file__).resolve().parent.parent / "ui" / "qso_panel.py"
    text = src.read_text(encoding="utf-8")
    m = re.search(r"def _build_columns_menu\(self\):.*?(?=\n    def )",
                  text, re.DOTALL)
    assert m
    assert "padding: 4px 32px 4px 28px" in m.group(0), (
        "P100: padding rechts muss 32px sein (war 20px)")


def test_t9_rx_panel_menu_padding_right_32():
    """RX-Panel beide QMenu-Stylesheets müssen 32px rechts haben."""
    src = Path(__file__).resolve().parent.parent / "ui" / "rx_panel.py"
    text = src.read_text(encoding="utf-8")
    count_new = text.count("padding: 4px 32px 4px 28px")
    count_old = text.count("padding: 4px 20px 4px 28px")
    assert count_new >= 2, (
        f"P100: RX-Panel muss 2× `4px 32px 4px 28px` haben (Spalten + Länder), "
        f"gefunden: {count_new}")
    assert count_old == 0, (
        f"P100: alte 20px-Variante darf nicht mehr existieren, gefunden: {count_old}")
