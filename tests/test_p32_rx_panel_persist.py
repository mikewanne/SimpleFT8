"""P32 RX-Panel-Spalten-Sichtbarkeit persistieren (v0.97.14, Mai 2026).

Vorher (Bug): Spalten-Auswahl via Rechtsklick verloren bei App-Restart.
Jetzt: hidden_cols-Param im Konstruktor + hidden_cols_changed-Signal.
"""
from __future__ import annotations

import sys

import pytest
from PySide6.QtWidgets import QApplication

from ui.rx_panel import (
    COL_COUNT,
    COL_DT,
    COL_LAND,
    COL_MSG,
    RXPanel,
)


@pytest.fixture(scope="module")
def qapp():
    """QApplication fuer das ganze Modul."""
    app = QApplication.instance() or QApplication(sys.argv)
    yield app


def test_hidden_cols_loaded_from_settings(qapp):
    """T1: hidden_cols=[COL_DT, COL_LAND] -> beide Spalten versteckt."""
    panel = RXPanel(hidden_cols=[COL_DT, COL_LAND])
    assert panel.table.isColumnHidden(COL_DT) is True
    assert panel.table.isColumnHidden(COL_LAND) is True
    # andere Spalten bleiben sichtbar
    assert panel.table.isColumnHidden(0) is False  # COL_UTC
    assert panel.table.isColumnHidden(COL_MSG) is False
    panel.deleteLater()


def test_invalid_hidden_cols_filtered_out(qapp):
    """T2: Ungueltige Werte werden defensive verworfen (Range, Typ, COL_MSG)."""
    panel = RXPanel(hidden_cols=[COL_MSG, 99, -1, "foo", COL_DT, None])
    # Nur COL_DT durch — alle anderen rausgefiltert
    assert panel._hidden_cols == {COL_DT}
    # COL_MSG NIE versteckt (Pflicht-sichtbar)
    assert panel.table.isColumnHidden(COL_MSG) is False
    panel.deleteLater()


def test_toggle_emits_hidden_cols_signal(qapp):
    """T3: _toggle_column emittet hidden_cols_changed mit sortierter Liste."""
    panel = RXPanel()
    received = []
    panel.hidden_cols_changed.connect(lambda cols: received.append(list(cols)))
    panel._toggle_column(COL_DT, True)
    panel._toggle_column(COL_LAND, True)
    panel._toggle_column(COL_DT, False)  # COL_DT wieder anzeigen
    assert received == [[COL_DT], sorted([COL_DT, COL_LAND]), [COL_LAND]]
    panel.deleteLater()


def test_default_no_settings_all_visible(qapp):
    """T5: Default hidden_cols=None -> 9 Spalten alle sichtbar."""
    panel = RXPanel()
    for col in range(COL_COUNT):
        assert panel.table.isColumnHidden(col) is False
    assert panel._hidden_cols == set()
    panel.deleteLater()


def test_col_msg_cannot_be_hidden_via_settings(qapp):
    """T4: Bug-Schutz — COL_MSG=6 ist nicht toggelbar (kein Crash, kein Effekt)."""
    panel = RXPanel(hidden_cols=[COL_MSG])
    assert COL_MSG not in panel._hidden_cols
    assert panel.table.isColumnHidden(COL_MSG) is False
    panel.deleteLater()


def test_signal_emits_after_unhide(qapp):
    """T6: Sichtbar-machen emittet leere Liste."""
    panel = RXPanel(hidden_cols=[COL_DT])
    received = []
    panel.hidden_cols_changed.connect(lambda cols: received.append(list(cols)))
    panel._toggle_column(COL_DT, False)
    assert received == [[]]
    panel.deleteLater()
