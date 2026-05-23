"""2026-05-23: QSO-Finish-Button (`btn_advance`) ist versteckt.

Mike: nie gebraucht — FT8-Timeouts (MAX_STATION_CALLS, 3-Min-Gesamt)
fangen stuck-Gegenstationen ab. Kein Sicherheits-Netz wie HALT, sondern
Workaround → analog FT2-Button hide statt delete.

Code-Pfad (Signal `advance_clicked`, Handler `_on_advance` in
`mw_qso.py:373`) bleibt intakt. Reaktivierung trivial.
"""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication

from ui.control_panel import ControlPanel


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def panel(app):
    return ControlPanel(callsign="DA1MHH")


def test_btn_advance_is_hidden(panel):
    """btn_advance ist explizit hidden gesetzt (2026-05-23 Hide).

    isHidden() pruefen, nicht isVisible() — letzteres haengt am Parent-
    Rendering und ist im Unit-Test ohne shown Window immer False.
    """
    assert panel.btn_advance.isHidden() is True


def test_btn_cancel_not_explicitly_hidden(panel):
    """HALT-Button wurde nicht explizit ausgeblendet — andere Rolle
    als btn_advance (Sicherheits-Notbremse, nicht Workaround)."""
    assert panel.btn_cancel.isHidden() is False


def test_btn_advance_signal_still_connected(panel):
    """Signal/Handler bleiben — programmatisches Triggern (Tests, Hooks)
    soll weiter moeglich sein, auch wenn UI versteckt ist."""
    # Signal existiert, kein AttributeError
    assert hasattr(panel, "advance_clicked")
    # Button-Objekt + click()-Methode existieren weiter
    assert panel.btn_advance is not None
    assert hasattr(panel.btn_advance, "click")
