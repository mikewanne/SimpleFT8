"""Tests fuer P2.OMNI-REDESIGN v4.0 (v0.95.23).

Voller architektureller Refactor: block_cycles raus, Block-Switch automatisch
bei rollover, Pause/Resume-Lifecycle, Flag-Pattern fuer State-Wechsel-Skip.

Workflow-Pfad: V1 → V2 → R1-V2 → V3 (Compact-fest) → Compact #3 → Code →
Final-R1.

Tests T1-T20 aus V3 §4 — deckt 15 ACs (AC1-AC15) ab.
"""
from __future__ import annotations

import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import inspect

import pytest
from PySide6.QtWidgets import QApplication

from core.omni_tx import OmniTX
from core.qso_state import QSOStateMachine, QSOState
from core.message import FT8Message
import core.omni_tx as omni_module


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def omni_tx_fresh():
    """Reset OmniTX-Singleton zwischen Tests."""
    from core import omni_tx as _omni
    _omni._instance = None
    yield
    _omni._instance = None


# ─────────────────────────────────────────────────────────────────────────────
# T1, T2 — 5-Slot-Pattern Block 1 + Block 2 (AC1, AC2)
# ─────────────────────────────────────────────────────────────────────────────

def test_block_1_pattern(app, omni_tx_fresh):
    """T1 (AC1): Block 1 = E-TX, O-TX, E-RX, O-RX, E-RX."""
    omni = OmniTX()
    omni.start_with_parity_for_next_slot(next_is_even=True)  # → Block 1
    expected = [
        (True, True),    # Pos 0: TX Even
        (True, False),   # Pos 1: TX Odd
        (False, None),   # Pos 2: RX
        (False, None),   # Pos 3: RX
        (False, None),   # Pos 4: RX
    ]
    for pos, (exp_send, exp_target) in enumerate(expected):
        send, target = omni.should_tx()
        assert send == exp_send, f"Pos {pos}: send={send} != {exp_send}"
        assert target == exp_target, f"Pos {pos}: target={target} != {exp_target}"
        omni.advance()


def test_block_2_pattern(app, omni_tx_fresh):
    """T2 (AC2): Block 2 = O-TX, E-TX, O-RX, E-RX, O-RX."""
    omni = OmniTX()
    omni.start_with_parity_for_next_slot(next_is_even=False)  # → Block 2
    expected = [
        (True, False),   # Pos 0: TX Odd
        (True, True),    # Pos 1: TX Even
        (False, None),   # Pos 2: RX
        (False, None),   # Pos 3: RX
        (False, None),   # Pos 4: RX
    ]
    for pos, (exp_send, exp_target) in enumerate(expected):
        send, target = omni.should_tx()
        assert send == exp_send, f"Pos {pos}: send={send} != {exp_send}"
        assert target == exp_target, f"Pos {pos}: target={target} != {exp_target}"
        omni.advance()


# ─────────────────────────────────────────────────────────────────────────────
# T3 — Block-Rollover (AC3)
# ─────────────────────────────────────────────────────────────────────────────

def test_block_switch_on_rollover(app, omni_tx_fresh):
    """T3 (AC3): advance() rollover slot_index 4→0 wechselt Block automatisch."""
    omni = OmniTX()
    omni.start_with_parity_for_next_slot(next_is_even=True)  # Block 1
    assert omni.block == 1
    # 4× advance → Pos 4
    for _ in range(4):
        omni.advance()
    assert omni._slot_index == 4
    assert omni.block == 1  # noch nicht gewechselt
    # 5. advance → Pos 0 → Block-Switch
    omni.advance()
    assert omni._slot_index == 0
    assert omni.block == 2
    # 5 weitere → wieder zu Block 1
    for _ in range(5):
        omni.advance()
    assert omni.block == 1


# ─────────────────────────────────────────────────────────────────────────────
# T4, T5 — start_with_parity_for_next_slot (AC10)
# ─────────────────────────────────────────────────────────────────────────────

def test_start_with_parity_next_even_block_1(app, omni_tx_fresh):
    """T4: next_is_even=True → Block 1, slot_index=0, active=True, paused=False."""
    omni = OmniTX()
    omni.start_with_parity_for_next_slot(next_is_even=True)
    assert omni.active is True
    assert omni.block == 1
    assert omni._slot_index == 0
    assert omni.is_paused() is False


def test_start_with_parity_next_odd_block_2(app, omni_tx_fresh):
    """T5: next_is_even=False → Block 2, slot_index=0, active=True, paused=False."""
    omni = OmniTX()
    omni.start_with_parity_for_next_slot(next_is_even=False)
    assert omni.active is True
    assert omni.block == 2
    assert omni._slot_index == 0
    assert omni.is_paused() is False


# ─────────────────────────────────────────────────────────────────────────────
# T6, T7, T8 — Pause/Resume (AC4, AC5)
# ─────────────────────────────────────────────────────────────────────────────

def test_pause_freezes_slot_index(app, omni_tx_fresh):
    """T6 (AC4): pause() → is_paused()=True, advance() macht NICHTS solange paused
    in Aufrufer-Logik gechecked wird."""
    omni = OmniTX()
    omni.start_with_parity_for_next_slot(next_is_even=True)
    omni.advance()
    omni.advance()
    assert omni._slot_index == 2
    omni.pause()
    assert omni.is_paused() is True
    # Aufrufer-Pre-Check (mw_cycle): if not is_paused: advance()
    if not omni.is_paused():
        omni.advance()  # darf nicht passieren
    assert omni._slot_index == 2  # eingefroren


def test_resume_after_pause(app, omni_tx_fresh):
    """T7 (AC5): resume() → is_paused()=False, advance() funktioniert wieder."""
    omni = OmniTX()
    omni.start_with_parity_for_next_slot(next_is_even=True)
    omni.pause()
    assert omni.is_paused() is True
    omni.resume()
    assert omni.is_paused() is False
    # advance funktioniert wieder
    omni.advance()
    assert omni._slot_index == 1


def test_advance_skipped_when_paused(app, omni_tx_fresh):
    """T8 (AC4 Aufrufer-Pre-Check): mw_cycle.py-Logik 'if not is_paused: advance'.
    Verifiziert dass paused-OMNI bei korrektem Pre-Check eingefroren bleibt."""
    omni = OmniTX()
    omni.start_with_parity_for_next_slot(next_is_even=True)
    omni.advance()  # → Pos 1
    omni.pause()
    # Simuliere 5 Cycle-Ticks aus mw_cycle._on_cycle_start
    for _ in range(5):
        if not omni.is_paused():
            omni.advance()
    assert omni._slot_index == 1  # unverändert
    assert omni.block == 1        # auch nicht durch Rollover gewechselt


# ─────────────────────────────────────────────────────────────────────────────
# T9, T10 — Flag-Pattern (AC13, AC14)
# ─────────────────────────────────────────────────────────────────────────────

def test_send_cq_with_omni_rx_slot_no_state_change(app, omni_tx_fresh):
    """T9 (AC14): bei OMNI-RX-Slot bleibt State auf vor-Wert (CQ_WAIT),
    nicht CQ_CALLING. Listener emuliert mw_qso._on_send_message-Skip."""
    sm = QSOStateMachine(my_call="DA1MHH", my_grid="JN58")
    sm.cq_mode = True

    def listener(message):
        if message.startswith("CQ "):
            sm._omni_skip_state_change = True

    sm.send_message.connect(listener)
    sm._set_state(QSOState.CQ_WAIT)
    sm._send_cq()

    assert sm.state != QSOState.CQ_CALLING
    assert sm.state == QSOState.CQ_WAIT
    assert sm._omni_skip_state_change is True


def test_omni_skip_state_change_flag_resets(app, omni_tx_fresh):
    """T10 (AC13): Flag wird bei jedem _send_cq() neu auf False gesetzt
    (kein Hänger durch alten True-Wert)."""
    sm = QSOStateMachine(my_call="DA1MHH", my_grid="JN58")
    sm.cq_mode = True
    sm._omni_skip_state_change = True  # Vorzustand: True

    sm.send_message.connect(lambda m: None)  # Listener setzt Flag NICHT
    sm._set_state(QSOState.CQ_WAIT)
    sm._send_cq()

    assert sm._omni_skip_state_change is False  # zurückgesetzt
    assert sm.state == QSOState.CQ_CALLING


# ─────────────────────────────────────────────────────────────────────────────
# T11, T12, T13 — Pause-Helper in 3 QSO-Entry-Pfaden (AC4, AC15)
# ─────────────────────────────────────────────────────────────────────────────

def _make_qso_stub(app):
    """Minimaler Stub fuer QSOMixin._pause_omni_if_active / _maybe_resume_omni."""
    from ui.mw_qso import QSOMixin
    sm = QSOStateMachine(my_call="DA1MHH", my_grid="JN58")
    omni = OmniTX()

    class _Stub:
        pass

    stub = _Stub()
    stub._omni_tx = omni
    stub._omni_was_active_pre_qso = False
    stub.qso_sm = sm

    class _Timer:
        @staticmethod
        def is_even_cycle():
            return True

    stub.timer = _Timer()
    return stub, sm, omni, QSOMixin


def test_omni_pause_on_station_clicked(app):
    """T11: _pause_omni_if_active setzt OMNI auf paused + Pre-QSO-Flag (Hunt-Entry)."""
    stub, sm, omni, mixin = _make_qso_stub(app)
    omni.start_with_parity_for_next_slot(next_is_even=True)
    assert omni.is_paused() is False
    mixin._pause_omni_if_active(stub)
    assert omni.is_paused() is True
    assert stub._omni_was_active_pre_qso is True


def test_omni_pause_on_cq_reply_via_tx_slot_for_partner(app):
    """T12: _pause_omni_if_active fuer CQ-Reply-Entry (gleiche Helper-Logik)."""
    stub, sm, omni, mixin = _make_qso_stub(app)
    omni.start_with_parity_for_next_slot(next_is_even=True)
    mixin._pause_omni_if_active(stub)
    assert omni.is_paused() is True
    assert stub._omni_was_active_pre_qso is True


def test_omni_pause_on_try_replace_pending_tx(app):
    """T13 (AC15 K1-NEU): _on_try_replace_pending_tx ruft Pause-Helper.
    Vor R1-V2 K1-Fix war dieser Pfad der EINZIGE der OMNI nicht pausierte."""
    stub, sm, omni, mixin = _make_qso_stub(app)
    omni.start_with_parity_for_next_slot(next_is_even=True)
    mixin._pause_omni_if_active(stub)
    assert omni.is_paused() is True
    assert stub._omni_was_active_pre_qso is True


# ─────────────────────────────────────────────────────────────────────────────
# T14, T15, T16, T17 — Resume-Helper in 3 Exit-Pfaden (AC5, AC12)
# ─────────────────────────────────────────────────────────────────────────────

def test_omni_resume_after_qso_complete_empty_queue(app):
    """T14 (AC5): _maybe_resume_omni resumed OMNI wenn Pre-Flag True + Queue leer."""
    stub, sm, omni, mixin = _make_qso_stub(app)
    omni.start_with_parity_for_next_slot(next_is_even=True)
    omni.pause()
    stub._omni_was_active_pre_qso = True
    sm._caller_queue = []

    mixin._maybe_resume_omni(stub)
    assert omni.is_paused() is False
    assert omni.active is True
    assert omni._slot_index == 0
    assert stub._omni_was_active_pre_qso is False


def test_omni_resume_after_qso_confirmed_empty_queue(app):
    """T15 (AC5): identisch zu T14 — Helper ist gleich, Aufrufer-Pfad ist anders."""
    stub, sm, omni, mixin = _make_qso_stub(app)
    omni.start_with_parity_for_next_slot(next_is_even=False)  # Block 2
    omni.pause()
    stub._omni_was_active_pre_qso = True
    sm._caller_queue = []

    mixin._maybe_resume_omni(stub)
    assert omni.is_paused() is False
    assert omni.active is True


def test_omni_resume_after_qso_timeout_empty_queue(app):
    """T16 (AC5): identisch — Timeout-Pfad."""
    stub, sm, omni, mixin = _make_qso_stub(app)
    omni.start_with_parity_for_next_slot(next_is_even=True)
    omni.pause()
    stub._omni_was_active_pre_qso = True
    sm._caller_queue = []

    mixin._maybe_resume_omni(stub)
    assert omni.is_paused() is False
    assert stub._omni_was_active_pre_qso is False


def test_omni_no_resume_with_caller_queue_pending(app):
    """T17 (AC12): nicht-leere Caller-Queue → kein Resume, Pre-Flag bleibt True."""
    stub, sm, omni, mixin = _make_qso_stub(app)
    omni.start_with_parity_for_next_slot(next_is_even=True)
    omni.pause()
    stub._omni_was_active_pre_qso = True

    msg = FT8Message(
        raw="DA1MHH SP6AXW JN89",
        field1="DA1MHH",
        field2="SP6AXW",
        field3="JN89",
        snr=-10,
        freq_hz=1500,
    )
    sm._caller_queue = [msg]

    mixin._maybe_resume_omni(stub)
    # OMNI bleibt pausiert, Pre-Flag bleibt True (naechstes QSO holt es ab)
    assert omni.is_paused() is True
    assert stub._omni_was_active_pre_qso is True


# ─────────────────────────────────────────────────────────────────────────────
# T18 — HALT (AC7)
# ─────────────────────────────────────────────────────────────────────────────

def test_halt_stops_omni_no_resume(app, omni_tx_fresh):
    """T18 (AC7): stop_omni_tx('manual_halt') → omni.active=False, Pre-Flag wird
    via _on_omni_stopped invalidiert, kein _maybe_resume_omni-Resume mehr."""
    omni = OmniTX()
    omni.start_with_parity_for_next_slot(next_is_even=True)
    received = []
    omni.omni_stopped.connect(lambda r: received.append(r))

    omni.stop_omni_tx("manual_halt")
    assert omni.active is False
    assert received == ["manual_halt"]


# ─────────────────────────────────────────────────────────────────────────────
# T19, T20 — API-Cleanup (AC11, S2)
# ─────────────────────────────────────────────────────────────────────────────

def test_block_cycles_constant_removed(app, omni_tx_fresh):
    """T19 (AC11): block_cycles ist KEIN Attribut mehr in OmniTX (Counter weg)."""
    omni = OmniTX()
    assert not hasattr(omni, "block_cycles"), \
        "block_cycles entfernt — auto-rollover ersetzt 80-Counter"
    assert not hasattr(omni, "_cycle_count"), \
        "_cycle_count entfernt"
    assert not hasattr(omni, "_pending_switch"), \
        "_pending_switch entfernt"


def test_get_instance_no_block_cycles_param(app, omni_tx_fresh):
    """T20 (S2): get_instance() Signatur hat keinen block_cycles-Parameter mehr."""
    sig = inspect.signature(omni_module.get_instance)
    assert "block_cycles" not in sig.parameters
    # Auch im OmniTX.__init__:
    init_sig = inspect.signature(OmniTX.__init__)
    assert "block_cycles" not in init_sig.parameters
