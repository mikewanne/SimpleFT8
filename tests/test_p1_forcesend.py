"""Tests fuer P1.FORCESEND — btn_advance state-aware + WAIT_73-Branch.

Mike-Use-Case 2026-05-06: bei stuck-Gegenstation manuell RR73 oder 73
senden statt 3-Min-Timeout abwarten. Bestehender btn_advance bekommt
2 Bug-Fixes (Label dynamisch, WAIT_73 in advance() + Enabled).

V1→V2→R1→V3 Workflow durch. R1-KP-1 (qso_complete-Bug) als Halluzination
verworfen — qso_complete laeuft bereits in TX_RR73 (Z.444), WAIT_73 =
"QSO schon geloggt".
"""
from __future__ import annotations

import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication

from core.qso_state import QSOState, QSOStateMachine, QSOData
from ui.control_panel import ControlPanel


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def panel(app):
    return ControlPanel(callsign="DA1MHH")


# ── advance() WAIT_73-Branch (qso_state.py) ──────────────────────────


def test_advance_wait_73_sends_73():
    """advance() in WAIT_73 → emittet '<their> <me> 73'."""
    sm = QSOStateMachine(my_call="DA1MHH", my_grid="JO31")
    sm.qso = QSOData(their_call="DK5ON", start_time=0.0)
    sm._set_state(QSOState.WAIT_73)
    received = []
    sm.send_message.connect(lambda m: received.append(m))

    sm.advance()

    assert received == ["DK5ON DA1MHH 73"]
    assert sm.state == QSOState.TX_73_COURTESY


def test_advance_wait_73_sets_courtesy_flag():
    """advance() in WAIT_73 → setzt courtesy_73_sent=True (Doppel-Send-Schutz P1.10)."""
    sm = QSOStateMachine(my_call="DA1MHH", my_grid="JO31")
    sm.qso = QSOData(their_call="DK5ON", start_time=0.0)
    sm._set_state(QSOState.WAIT_73)

    sm.advance()

    assert sm.qso.courtesy_73_sent is True


def test_advance_wait_73_flag_set_before_send():
    """R1 KP-3: Flag muss VOR send_message gesetzt werden (asynchron-Schutz)."""
    sm = QSOStateMachine(my_call="DA1MHH", my_grid="JO31")
    sm.qso = QSOData(their_call="DK5ON", start_time=0.0)
    sm._set_state(QSOState.WAIT_73)
    flag_at_emit = []
    sm.send_message.connect(lambda m: flag_at_emit.append(sm.qso.courtesy_73_sent))

    sm.advance()

    assert flag_at_emit == [True]


def test_advance_wait_73_idempotent_when_flag_set():
    """Final-R1 Race-Schutz: Auto-Pfad hat courtesy_73_sent gesetzt →
    Mike-Klick verpufft ohne zweiten Send (Doppel-73-Schutz)."""
    sm = QSOStateMachine(my_call="DA1MHH", my_grid="JO31")
    sm.qso = QSOData(their_call="DK5ON", start_time=0.0)
    sm.qso.courtesy_73_sent = True  # Auto-Pfad war schneller
    sm._set_state(QSOState.WAIT_73)
    received = []
    sm.send_message.connect(lambda m: received.append(m))

    sm.advance()

    assert received == [], "Doppel-73 muss verhindert sein"


def test_advance_other_states_no_emit():
    """advance() in IDLE/TIMEOUT/CQ_CALLING → keine Aenderung (Default-Pfad)."""
    sm = QSOStateMachine(my_call="DA1MHH", my_grid="JO31")
    sm.qso = QSOData(their_call="DK5ON", start_time=0.0)
    received = []
    sm.send_message.connect(lambda m: received.append(m))

    for state in [QSOState.IDLE, QSOState.TIMEOUT, QSOState.CQ_CALLING]:
        sm._set_state(state)
        sm.advance()

    assert received == []


# ── set_advance_label (control_panel.py) ─────────────────────────────


def test_advance_label_default(panel):
    """state IDLE → Default-Label 'Weiter →'."""
    panel.set_advance_label(QSOState.IDLE)
    assert panel.btn_advance.text() == "Weiter →"


def test_advance_label_wait_report(panel):
    """state WAIT_REPORT → 'R+Report'."""
    panel.set_advance_label(QSOState.WAIT_REPORT)
    assert panel.btn_advance.text() == "R+Report"


def test_advance_label_wait_rr73(panel):
    """state WAIT_RR73 → 'RR73'."""
    panel.set_advance_label(QSOState.WAIT_RR73)
    assert panel.btn_advance.text() == "RR73"


def test_advance_label_wait_73(panel):
    """state WAIT_73 → '73'."""
    panel.set_advance_label(QSOState.WAIT_73)
    assert panel.btn_advance.text() == "73"


def test_advance_label_unknown_state_default(panel):
    """state TX_RR73 (nicht in mapping) → Default 'Weiter →'."""
    panel.set_advance_label(QSOState.TX_RR73)
    assert panel.btn_advance.text() == "Weiter →"


def test_advance_label_returns_to_default(panel):
    """Nach WAIT_73 → IDLE → Label zurueck auf Default."""
    panel.set_advance_label(QSOState.WAIT_73)
    panel.set_advance_label(QSOState.IDLE)
    assert panel.btn_advance.text() == "Weiter →"
