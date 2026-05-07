"""Tests fuer P1.COLLAPSE-RADIO-MODEBAND (v0.95.17).

Modus+Band-Card und Radio-Card sind einklappbar analog zur Antennen-
Kachel (v0.95.11). Beide unabhaengig, Settings-persistiert. Mike-
Anweisung 2026-05-07: „radio und mouds haette ich gerne auch zum
einklappen der kachel wie die Antennen kachel".

Spiegelt `tests/test_antenne_card.py` per pytest-parametrize fuer
beide Cards.
"""
from __future__ import annotations

import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from ui.control_panel import _ModeBandCard, _RadioCard


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture(params=[
    pytest.param(_ModeBandCard, id="modeband"),
    pytest.param(_RadioCard, id="radio"),
])
def card(app, request):
    """Frische Card pro Test (parametrisiert auf beide Klassen)."""
    c = request.param()
    c.show()
    return c


# ── Per-Card-Tests (parametrisiert) ─────────────────────────────────────


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
    assert card.maximumHeight() > 1000  # _QWIDGETSIZE_MAX = 16777215


def test_tooltip_set_on_toggle_button(card):
    """Toggle-Button hat Tooltip mit 'ein-/ausklappen'-Hint."""
    assert "ein-/ausklappen" in card.toggle_btn.toolTip().lower()


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


# ── Integration-Tests (kein Parametrize) ────────────────────────────────


def test_modeband_and_radio_independent(app):
    """Beide Karten getrennt togglen — keine gegenseitige Beeinflussung."""
    mb = _ModeBandCard()
    rd = _RadioCard()
    mb.show()
    rd.show()
    mb.set_collapsed(True)
    assert mb.is_collapsed() is True
    assert rd.is_collapsed() is False
    rd.set_collapsed(True)
    assert mb.is_collapsed() is True
    assert rd.is_collapsed() is True
    mb.set_collapsed(False)
    assert mb.is_collapsed() is False
    assert rd.is_collapsed() is True


def test_modeband_card_preserves_button_refs(app):
    """Refactor darf existierende Member-Refs nicht zerstoeren."""
    mb = _ModeBandCard()
    # Diese Refs werden von ControlPanel weiterverwendet (Z.1080-1084):
    assert mb.btn_ft8 is not None
    assert mb.btn_ft4 is not None
    assert mb.btn_ft2 is not None
    assert mb.freq_label is not None
    assert "20m" in mb.band_buttons
    assert "10m" in mb.band_buttons
    assert "20m" in mb.prop_bars


def test_radio_card_preserves_button_refs(app):
    """Refactor darf existierende Member-Refs nicht zerstoeren."""
    rd = _RadioCard()
    assert rd.psk_label is not None
    assert rd.btn_psk_map is not None
    assert rd.btn_tune is not None
    assert rd.watt_label is not None
    assert rd.swr_label is not None
    assert 10 in rd.power_buttons
    assert 100 in rd.power_buttons
