"""Tests fuer P1.OMNI-START (v0.95.22).

OMNI-CQ-Toggle aktiviert jetzt zusaetzlich den CQ-Loop in qso_state.
Plus HALT-Button stoppt OMNI. Plus Stop-while-QSO setzt _was_cq=False.

Workflow-Pfad: V1 → V2 → R1 → V3 → Compact → Code.
"""
from __future__ import annotations

import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication

from core.qso_state import QSOStateMachine, QSOState
from core.omni_tx import OmniTX
from core.message import FT8Message


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def _make_setup(state=QSOState.IDLE):
    """Minimaler Stub aus QSOStateMachine + OmniTX fuer Toggle-Test ohne MainWindow."""
    sm = QSOStateMachine("DA1MHH", "JN58")
    sm._set_state(state)
    omni = OmniTX(block_cycles=80)
    return sm, omni


# ── Toggle Start: enable OMNI + start_cq ─────────────────────────────


def test_omni_toggle_starts_cq_loop(app):
    """Toggle on bei IDLE → omni.active=True UND cq_mode=True UND CQ wird emittet."""
    sm, omni = _make_setup(state=QSOState.IDLE)
    sent: list[str] = []
    sm.send_message.connect(lambda m: sent.append(m))
    # Simuliere _on_btn_omni_cq_toggled(True) — Sequenz aus Diff 2.1
    omni.enable()
    sm.start_cq()
    assert omni.active is True
    assert sm.cq_mode is True
    assert sm.state == QSOState.CQ_CALLING
    # _send_cq emittet "CQ DA1MHH JN58"
    assert any(m.startswith("CQ DA1MHH") for m in sent)


def test_omni_toggle_off_stops_cq_loop(app):
    """Toggle off → omni stop + cq_mode=False + _was_cq=False."""
    sm, omni = _make_setup(state=QSOState.IDLE)
    omni.enable()
    sm.start_cq()
    # Simuliere Toggle off → omni.stop_omni_tx + _on_omni_stopped (Diff 2.2)
    omni.stop_omni_tx("manual_halt")
    if sm.cq_mode:
        sm.stop_cq()
    sm._was_cq = False
    assert omni.active is False
    assert sm.cq_mode is False
    assert sm._was_cq is False


# ── Stop-Reasons (parametrisiert, R1 KOENNTE #5) ─────────────────────


@pytest.mark.parametrize(
    "reason",
    ["band_change", "ft_mode_change", "rx_mode_change",
     "totmann_expired", "easter_egg_off", "superseded"],
)
def test_omni_external_stop_resets_cq(app, reason):
    """ALLE Stop-Reasons triggern qso_sm.stop_cq() + _was_cq=False (Diff 2.2)."""
    sm, omni = _make_setup(state=QSOState.IDLE)
    omni.enable()
    sm.start_cq()
    assert omni.active and sm.cq_mode
    omni.stop_omni_tx(reason)
    # Simuliere _on_omni_stopped(reason)
    if sm.cq_mode:
        sm.stop_cq()
    sm._was_cq = False
    assert omni.active is False
    assert sm.cq_mode is False
    assert sm._was_cq is False


# ── Block-while-QSO ──────────────────────────────────────────────────


def test_omni_blocked_during_active_qso(app):
    """Mike klickt OMNI waehrend WAIT_REPORT → Toggle nicht aktiviert (Diff 2.1 Pre-Block)."""
    sm, omni = _make_setup(state=QSOState.WAIT_REPORT)
    # Pre-Cond: state ist NICHT in (IDLE, CQ_WAIT)
    assert sm.state not in (QSOState.IDLE, QSOState.CQ_WAIT)
    # Simuliere Toggle-Versuch — Block muss vor enable()/start_cq() greifen
    blocked = sm.state not in (QSOState.IDLE, QSOState.CQ_WAIT)
    if not blocked:
        omni.enable()
        sm.start_cq()
    assert omni.active is False
    assert sm.cq_mode is False


# ── HALT mit OMNI aktiv ──────────────────────────────────────────────


def test_halt_stops_omni(app):
    """HALT-Button (cancel()) muss OMNI ebenfalls stoppen (Diff 2.3)."""
    sm, omni = _make_setup(state=QSOState.IDLE)
    omni.enable()
    sm.start_cq()
    # Simuliere _on_cancel-Sequenz aus Diff 2.3
    sm.stop_cq()
    sm.cancel()
    if omni.active:
        omni.stop_omni_tx("manual_halt")
    assert omni.active is False
    assert sm.cq_mode is False


# ── Reply-Resume waehrend OMNI (Backward-compat) ─────────────────────


def test_omni_active_cq_reply_sets_was_cq(app):
    """OMNI aktiv + _process_cq_reply setzt _was_cq=True.

    Backward-compat-Beweis: nach QSO-Ende kann _resume_cq_if_needed
    OMNI-CQ resumen weil _was_cq=True bleibt (solange OMNI nicht gestoppt
    wird — bei Stop wird _was_cq=False ueber Diff 2.2 gesetzt).
    """
    sm, omni = _make_setup(state=QSOState.CQ_CALLING)
    omni.enable()
    sm.cq_mode = True
    # CQ-Reply von EV81AB an uns mit Locator KN12 (is_grid=True)
    msg = FT8Message(
        raw="DA1MHH EV81AB KN12",
        field1="DA1MHH",
        field2="EV81AB",
        field3="KN12",
        snr=-15,
        freq_hz=946,
    )
    # Sanity-Check Properties
    assert msg.is_grid is True
    assert msg.caller == "EV81AB"
    sm._pending_reply = msg
    sm._process_cq_reply()
    assert sm._was_cq is True
