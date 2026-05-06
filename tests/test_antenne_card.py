"""Tests fuer P1.ANTENNE-COLLAPSE — _AntenneCard einklappbar.

Prueft Toggle-API, Persistence-Hook (collapse_changed-Signal) und
Initial-State-Verhalten. Mike-Designentscheidung 2026-05-06: Antennen-
Kachel WIRD einklappbar (DeepSeek's Konvention „alles immer sichtbar"
explizit ueberschrieben — SimpleFT8 ist Hobby-Tool, kein Contest).
"""
from __future__ import annotations

import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from ui.control_panel import _AntenneCard


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def card(app):
    """Frische Card pro Test — show() damit isVisible() True liefert."""
    c = _AntenneCard()
    c.show()
    return c


def test_default_expanded(card):
    """Default: Body sichtbar, Toggle-Icon ▼."""
    assert card._body_widget.isVisible() is True
    assert card.toggle_btn.text() == "▼"
    assert card.is_collapsed() is False


def test_set_collapsed_hides_body(card):
    """set_collapsed(True) → Body unsichtbar, Toggle ▶."""
    card.set_collapsed(True)
    assert card._body_widget.isVisible() is False
    assert card.toggle_btn.text() == "▶"
    assert card.is_collapsed() is True


def test_set_collapsed_false_shows_body(card):
    """set_collapsed(False) nach True → Body wieder sichtbar."""
    card.set_collapsed(True)
    card.set_collapsed(False)
    assert card._body_widget.isVisible() is True
    assert card.toggle_btn.text() == "▼"
    assert card.is_collapsed() is False


def test_toggle_button_click_collapses(card):
    """Klick auf Toggle-Button → wechselt zwischen sichtbar/unsichtbar."""
    QTest.mouseClick(card.toggle_btn, Qt.LeftButton)
    assert card.is_collapsed() is True
    QTest.mouseClick(card.toggle_btn, Qt.LeftButton)
    assert card.is_collapsed() is False


def test_toggle_emits_collapse_changed(card):
    """_toggle_collapsed (User-Klick-Pfad) emitiert collapse_changed."""
    received = []
    card.collapse_changed.connect(lambda c: received.append(c))
    card._toggle_collapsed()
    assert received == [True]
    card._toggle_collapsed()
    assert received == [True, False]


def test_max_height_set_when_collapsed(card):
    """Bei Collapse: setMaximumHeight=36, bei Expand: zurueck auf MAX."""
    card.set_collapsed(True)
    assert card.maximumHeight() == 36
    card.set_collapsed(False)
    # QWIDGETSIZE_MAX = 16777215
    assert card.maximumHeight() > 1000


def test_diversity_widget_visibility_preserved_through_toggle(card):
    """Mode-State (_div_widget.setVisible) bleibt durch Collapse erhalten."""
    card._div_widget.setVisible(True)
    card.set_collapsed(True)
    card.set_collapsed(False)
    assert card._div_widget.isVisible() is True


def test_tooltip_set_on_toggle_button(card):
    """Toggle-Button hat Tooltip mit 'ein-/ausklappen'-Hint."""
    assert "ein-/ausklappen" in card.toggle_btn.toolTip().lower()


def test_collapse_with_existing_body_state(card):
    """Body-Children behalten ihre eigene Visibility nach Toggle.

    Wichtig: _freq_hist + _tx_freq_row sind initial unsichtbar (nur in
    bestimmten Modi sichtbar). Wenn man sie aufschaltet, dann Card
    collapsed + expanded → Visibility bleibt.
    """
    card._freq_hist.setVisible(True)
    card._tx_freq_row.setVisible(True)
    card.set_collapsed(True)
    card.set_collapsed(False)
    assert card._freq_hist.isVisible() is True
    assert card._tx_freq_row.isVisible() is True


def test_signal_not_emitted_by_set_collapsed_api(card):
    """set_collapsed() (Programm-API) emitiert KEIN Signal.

    Init-Loop-Schutz: MainWindow ruft set_collapsed beim App-Start mit
    Settings-Wert auf — wuerde es ein Signal emittieren, kaeme es zu
    unnoetigem set+save-Roundtrip in Settings.
    Nur _toggle_collapsed (User-Klick) emitiert collapse_changed.
    """
    received = []
    card.collapse_changed.connect(lambda c: received.append(c))
    card.set_collapsed(True)
    card.set_collapsed(False)
    assert received == []
