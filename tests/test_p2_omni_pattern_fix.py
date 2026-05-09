"""Tests fuer P2.OMNI-PATTERN-FIX (v0.95.24).

Bug: OMNI-CQ-Pattern in v0.95.23 verschoben um +30s. Mike-Field-Test
09.05. 08:34-08:37 UTC zeigt: TX nur in Pos 0 jedes Blocks, RX-Slots
kollabiert. Wurzel: _send_cq lief am Slot-START via on_cycle_end →
Encoder overshoot=0.8s > 0.3s → v0.80 Fix B schiebt TX um 2 Slots.

Loesung (R1-bestaetigt):
1. Encoder-Queue (Commit 1, tests/test_encoder_queue.py)
2. Mid-Cycle-Pretrigger (Commit 2)
   - omni_tx.peek_next() fuer naechsten-Slot-Vorschau
   - mw_cycle._omni_pretrigger_check() bei cycle_pos > dur-1.3s
   - qso_state._was_pretriggered Flag verhindert on_cycle_end
     Doppel-_send_cq

Tests:
- T1-T6: peek_next() Methode (RX/TX, Block-Rollover, Paritaet)
- T7-T11: _was_pretriggered Flag (Init, on_cycle_end-Schutz)
- T12-T16: Pretrigger-Verhalten (Schwellen, Reentrancy, Pause-Skip,
  Edge-Cases)
"""
from __future__ import annotations

import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication

from core.omni_tx import OmniTX
from core.qso_state import QSOStateMachine, QSOState


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def omni_fresh():
    """Frische OmniTX-Instanz pro Test."""
    from core import omni_tx as _omni
    _omni._instance = None
    yield
    _omni._instance = None


# ─────────────────────────────────────────────────────────────────────
# T1-T6 — peek_next() (AC: Block 1+2 Pattern, Rollover)
# ─────────────────────────────────────────────────────────────────────


def test_peek_next_block1_pos0_returns_tx_odd(app, omni_fresh):
    """T1: Block 1 Pos 0 → naechster Slot Pos 1 ist TX Odd."""
    omni = OmniTX()
    omni.start_with_parity_for_next_slot(next_is_even=True)  # Block 1, Pos 0
    next_idx, next_block, target_even, is_tx = omni.peek_next()
    assert next_idx == 1
    assert next_block == 1
    assert is_tx is True
    assert target_even is False  # Pos 1 in Block 1 = Odd


def test_peek_next_block1_pos1_returns_rx(app, omni_fresh):
    """T2: Block 1 Pos 1 → naechster Slot Pos 2 ist RX."""
    omni = OmniTX()
    omni.start_with_parity_for_next_slot(next_is_even=True)
    omni.advance()  # Pos 0 → Pos 1
    next_idx, next_block, target_even, is_tx = omni.peek_next()
    assert next_idx == 2
    assert is_tx is False
    assert target_even is None
    assert next_block == 1


def test_peek_next_rollover_switches_block(app, omni_fresh):
    """T3: Pos 4 → naechster Slot ist Pos 0 mit Block-Wechsel."""
    omni = OmniTX()
    omni.start_with_parity_for_next_slot(next_is_even=True)  # Block 1
    for _ in range(4):  # Pos 0 → 1 → 2 → 3 → 4
        omni.advance()
    assert omni._slot_index == 4
    next_idx, next_block, target_even, is_tx = omni.peek_next()
    # Rollover: Block 1 → Block 2
    assert next_idx == 0
    assert next_block == 2
    assert is_tx is True
    assert target_even is False  # Block 2 Pos 0 = Odd


def test_peek_next_block2_pos0_returns_tx_even(app, omni_fresh):
    """T4: Block 2 Pos 0 → naechster Slot Pos 1 ist TX Even."""
    omni = OmniTX()
    omni.start_with_parity_for_next_slot(next_is_even=False)  # Block 2, Pos 0
    next_idx, next_block, target_even, is_tx = omni.peek_next()
    assert next_idx == 1
    assert next_block == 2
    assert is_tx is True
    assert target_even is True  # Block 2 Pos 1 = Even


def test_peek_next_no_state_mutation(app, omni_fresh):
    """T5: peek_next() veraendert _slot_index/block NICHT."""
    omni = OmniTX()
    omni.start_with_parity_for_next_slot(next_is_even=True)
    omni.advance()  # Pos 1
    before_idx = omni._slot_index
    before_block = omni.block
    omni.peek_next()
    omni.peek_next()
    omni.peek_next()
    assert omni._slot_index == before_idx
    assert omni.block == before_block


def test_peek_next_returns_4_tuple_for_rx_slot(app, omni_fresh):
    """T6: RX-Slot returnt (idx, block, None, False)."""
    omni = OmniTX()
    omni.start_with_parity_for_next_slot(next_is_even=True)
    omni.advance()  # Pos 1 (TX Odd)
    omni.advance()  # Pos 2 (RX)
    next_idx, next_block, target_even, is_tx = omni.peek_next()
    # Pos 3 = RX
    assert next_idx == 3
    assert is_tx is False
    assert target_even is None


# ─────────────────────────────────────────────────────────────────────
# T7-T11 — _was_pretriggered Flag in qso_state
# ─────────────────────────────────────────────────────────────────────


def test_was_pretriggered_flag_init_false(app):
    """T7: _was_pretriggered ist nach __init__ False."""
    sm = QSOStateMachine("DA1MHH", "JO31")
    assert sm._was_pretriggered is False


def test_on_cycle_end_with_pretriggered_skips_send_cq(app):
    """T8: on_cycle_end CQ_WAIT mit _was_pretriggered=True → KEIN _send_cq.

    Pretrigger lief mid-cycle, der TX ist schon eingereiht. Slot-Start
    on_cycle_end darf NICHT noch ein zweites _send_cq triggern (sonst
    Doppel-TX im selben Slot).
    """
    sm = QSOStateMachine("DA1MHH", "JO31")
    sm.cq_mode = True
    sm._set_state(QSOState.CQ_WAIT)
    sm.qso.timeout_cycles = 0
    sm._was_pretriggered = True
    captured = []
    sm.send_message.connect(captured.append)
    sm.on_cycle_end()
    # KEIN _send_cq → kein Emit
    assert len(captured) == 0


def test_on_cycle_end_with_pretriggered_resets_flag(app):
    """T9: on_cycle_end resettet _was_pretriggered nach Skip."""
    sm = QSOStateMachine("DA1MHH", "JO31")
    sm.cq_mode = True
    sm._set_state(QSOState.CQ_WAIT)
    sm.qso.timeout_cycles = 0
    sm._was_pretriggered = True
    sm.on_cycle_end()
    assert sm._was_pretriggered is False


def test_on_cycle_end_without_pretriggered_runs_send_cq(app):
    """T10: on_cycle_end CQ_WAIT mit _was_pretriggered=False → _send_cq laeuft.

    Klassischer Pfad bleibt erhalten (Initial-Toggle, Resume).
    """
    sm = QSOStateMachine("DA1MHH", "JO31")
    sm.cq_mode = True
    sm._set_state(QSOState.CQ_WAIT)
    sm.qso.timeout_cycles = 0
    sm._was_pretriggered = False
    captured = []
    sm.send_message.connect(captured.append)
    sm.on_cycle_end()
    # _send_cq → Emit "CQ ..."
    assert len(captured) == 1
    assert captured[0].startswith("CQ ")


def test_on_cycle_end_pretriggered_only_affects_cq_wait(app):
    """T11: _was_pretriggered greift NUR im CQ_WAIT-Branch.

    In WAIT_REPORT/WAIT_RR73 gibt es keinen on_cycle_end-_send_cq —
    daher hat das Flag dort keinen Effekt (Test prueft Konsistenz).
    """
    sm = QSOStateMachine("DA1MHH", "JO31")
    sm.cq_mode = False  # Hunt-QSO
    sm.qso.start_time = 0.0  # Kein Timeout
    sm._set_state(QSOState.WAIT_REPORT)
    sm.qso.timeout_cycles = 0
    sm._was_pretriggered = True
    captured = []
    sm.send_message.connect(captured.append)
    sm.on_cycle_end()
    # WAIT_REPORT ruft _send_cq nicht — daher kein Emit, Flag bleibt
    assert len(captured) == 0
    # Flag bleibt True (kein Reset im WAIT_REPORT-Branch)
    assert sm._was_pretriggered is True


# ─────────────────────────────────────────────────────────────────────
# T12-T16 — Pretrigger-Verhalten / Edge-Cases
# ─────────────────────────────────────────────────────────────────────


def test_pretrigger_offset_constant(app):
    """T12: _OMNI_PRETRIGGER_OFFSET_S = 1.3s (FlexRadio TX-Buffer-Latenz).

    FT8 Slot 15s: Pretrigger ab cycle_pos > 13.7s.
    FT4 Slot 7.5s: ab cycle_pos > 6.2s.
    FT2 Slot 3.8s: ab cycle_pos > 2.5s.
    Encoder hat dann sleep_dur > 0 → kein v0.80 Fix B Drift-Schutz.
    """
    from ui.mw_cycle import _OMNI_PRETRIGGER_OFFSET_S
    assert _OMNI_PRETRIGGER_OFFSET_S == 1.3
    # Aequivalent zur Encoder-TX-Buffer-Konstante
    from core.encoder import TARGET_TX_OFFSET
    assert _OMNI_PRETRIGGER_OFFSET_S == abs(TARGET_TX_OFFSET) + 0.5  # 0.8 + 0.5


def test_peek_next_called_multiple_times_idempotent(app, omni_fresh):
    """T13: peek_next() mehrfach hintereinander = idempotent (Reentrancy).

    Pretrigger-Flag verhindert Re-Trigger im selben Cycle, aber peek_next
    selbst muss bei wiederholtem Aufruf gleiches Ergebnis liefern.
    """
    omni = OmniTX()
    omni.start_with_parity_for_next_slot(next_is_even=True)
    omni.advance()  # Pos 1
    result_1 = omni.peek_next()
    result_2 = omni.peek_next()
    result_3 = omni.peek_next()
    assert result_1 == result_2 == result_3


def test_peek_next_inactive_omni(app, omni_fresh):
    """T14: peek_next() bei inactive OMNI rechnet trotzdem korrekt.

    Pre-Cond-Check liegt im Aufrufer (mw_cycle._omni_pretrigger_check
    prueft active+is_paused). peek_next selbst macht reine Berechnung.
    """
    omni = OmniTX()
    # active=False, kein start_with_parity
    next_idx, next_block, target_even, is_tx = omni.peek_next()
    # _slot_index=0 default → Pos 1, Block 1 (default), TX
    assert next_idx == 1
    assert is_tx is True
    # Block 1 Pos 1 → Odd
    assert target_even is False


def test_peek_next_during_pause(app, omni_fresh):
    """T15: peek_next() arbeitet auch waehrend Pause-State.

    Pretrigger-Aufrufer skipt zwar bei pause(), aber Methode selbst
    bleibt funktional (z.B. fuer Tests/Diagnose).
    """
    omni = OmniTX()
    omni.start_with_parity_for_next_slot(next_is_even=True)
    omni.pause()
    assert omni.is_paused() is True
    next_idx, next_block, target_even, is_tx = omni.peek_next()
    # Pos 0 → Pos 1 (TX Odd) — keine Pause-Special-Logik in peek_next
    assert next_idx == 1
    assert is_tx is True
    assert target_even is False


def test_peek_next_5_slot_cycle_block_consistency(app, omni_fresh):
    """T16: Vollstaendige 5-Slot-Sequenz: peek_next() zeigt jeweils
    den naechsten Slot korrekt voraus, auch ueber Block-Grenze.

    Block 1 Pattern: E-TX, O-TX, E-RX, O-RX, E-RX
    Block 2 Pattern: O-TX, E-TX, O-RX, E-RX, O-RX
    """
    omni = OmniTX()
    omni.start_with_parity_for_next_slot(next_is_even=True)  # Block 1
    expected_block1 = [
        # (pos, peek_next-Erwartung)
        (0, (1, 1, False, True)),    # peek: Pos 1 = TX Odd, Block 1
        (1, (2, 1, None, False)),    # peek: Pos 2 = RX
        (2, (3, 1, None, False)),    # peek: Pos 3 = RX
        (3, (4, 1, None, False)),    # peek: Pos 4 = RX
        (4, (0, 2, False, True)),    # peek: Rollover → Block 2 Pos 0 = TX Odd
    ]
    for cur_pos, expected in expected_block1:
        assert omni._slot_index == cur_pos
        assert omni.peek_next() == expected
        omni.advance()
    # Nach 5x advance: bei Block 2 Pos 0
    assert omni._slot_index == 0
    assert omni.block == 2
