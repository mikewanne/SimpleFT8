"""Unit-Tests fuer P4.OMNI-NEUBAU V5 — core/omni_cq.py (signal-basiert).

Deckt V3 §6 T1-T22 ab. Tests rufen on_cycle_start direkt auf — KEIN
Worker-Mock, KEIN Sleep-Mock, KEIN Boundary-Mock.

Lesson aus v0.96.0 (feedback_test_critical_path_not_mock.md): wenn ein
Mock genau die Logik ueberschreibt die der Test pruefen sollte, validiert
er die Mock-Implementierung statt des echten Codes. Vor jedem Mock
fragen: "Ersetzt dieser Mock den Pfad den der Test pruefen sollte?".
"""
from __future__ import annotations

import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from PySide6.QtWidgets import QApplication

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from core.omni_cq import OmniCQ  # noqa: E402


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def _make_omni(*, free_cq_freq: int | None = 1500):
    """Test-Setup: OmniCQ mit Mock-Encoder/Diversity/Timer.

    Returns: (omni, encoder, diversity, timer) fuer Test-Asserts.
    KEIN Worker-Mock, KEIN Sleep-Mock, KEIN Boundary-Mock.
    """
    encoder = MagicMock()
    encoder.transmit = MagicMock(return_value=True)
    diversity = MagicMock()
    diversity.get_free_cq_freq = MagicMock(return_value=free_cq_freq)
    timer = MagicMock()
    timer.cycle_duration = 15.0
    timer.is_even_cycle = MagicMock(return_value=False)
    omni = OmniCQ(
        encoder=encoder,
        diversity_ctrl=diversity,
        timer=timer,
        my_call="DA1MHH",
        my_grid="JN58",
    )
    return omni, encoder, diversity, timer


# ===========================================================================
# T1 — initial state
# ===========================================================================
def test_initial_state_inactive(app):
    omni, *_ = _make_omni()
    assert omni.is_active() is False
    assert omni.is_paused() is False
    assert omni.cq_even_count == 0
    assert omni.cq_odd_count == 0
    assert omni.cq_audio_hz is None
    assert omni._slot_index == 0
    assert omni._block == 1


# ===========================================================================
# T2 — start initialisiert Block 1 ab Pos 0 (AC1, AC5)
# ===========================================================================
def test_start_initializes_block1_pos0(app):
    omni, *_ = _make_omni()
    captured: list[None] = []
    omni.omni_started.connect(lambda: captured.append(None))
    omni.start()
    assert omni.is_active() is True
    assert omni.is_paused() is False
    assert omni._block == 1            # AC5: IMMER Block 1
    assert omni._slot_index == 0
    assert omni._cq_audio_hz is None
    assert omni._cq_even_count == 0
    assert omni._cq_odd_count == 0
    assert len(captured) == 1          # AC22: omni_started emittet 1x


# ===========================================================================
# T3 — start idempotent bei bereits aktivem OMNI (AC1)
# ===========================================================================
def test_start_idempotent_on_already_active(app):
    omni, *_ = _make_omni()
    omni.start()
    omni._slot_index = 3              # Pattern-State manipulieren
    omni._block = 2
    captured: list[None] = []
    omni.omni_started.connect(lambda: captured.append(None))
    omni.start()                       # zweiter Aufruf — no-op
    assert omni._slot_index == 3      # nicht zurueckgesetzt
    assert omni._block == 2
    assert captured == []              # kein zweites omni_started


# ===========================================================================
# T4 — Block 1 Pos 0: encoder.transmit mit tx_even=True (AC2, AC8)
# ===========================================================================
def test_block1_pos0_calls_encoder_transmit_tx_even(app):
    omni, encoder, *_ = _make_omni()
    omni.start()
    omni.on_cycle_start(cycle_num=100, is_even=True)
    encoder.transmit.assert_called_once_with(
        "CQ DA1MHH JN58", tx_even=True, audio_freq_hz=1500,
    )
    assert omni._slot_index == 1


# ===========================================================================
# T5 — Block 1 Pos 1: encoder.transmit mit tx_even=False (AC2, AC8)
# ===========================================================================
def test_block1_pos1_calls_encoder_transmit_tx_odd(app):
    omni, encoder, *_ = _make_omni()
    omni.start()
    omni._slot_index = 1               # Pos 1 = TX-O in Block 1
    omni.on_cycle_start(cycle_num=101, is_even=False)
    encoder.transmit.assert_called_once_with(
        "CQ DA1MHH JN58", tx_even=False, audio_freq_hz=1500,
    )
    assert omni._slot_index == 2


# ===========================================================================
# T6 — Block 1 Pos 2/3/4: kein transmit, slot_action emittet "Horche" (AC2, AC9)
# ===========================================================================
@pytest.mark.parametrize(
    "slot_index, signal_is_even",
    [(2, True), (3, False), (4, True)],
)
def test_block1_pos_2_3_4_no_transmit_emits_horche(app, slot_index,
                                                   signal_is_even):
    omni, encoder, *_ = _make_omni()
    omni.start()
    omni._slot_index = slot_index
    captured: list[tuple[str, bool, bool]] = []
    omni.slot_action.connect(
        lambda lbl, tx, tev: captured.append((lbl, tx, tev))
    )
    omni.on_cycle_start(cycle_num=200, is_even=signal_is_even)
    encoder.transmit.assert_not_called()
    assert len(captured) == 1
    label, is_tx, target_even = captured[0]
    assert is_tx is False
    assert target_even is signal_is_even   # AC9: echte UTC-Paritaet


# ===========================================================================
# T7 — Rollover Block 1 -> Block 2: erster TX nach Rollover ist tx_odd (AC3, AC4, AC10)
# ===========================================================================
def test_rollover_block1_to_block2_first_tx_is_odd(app):
    omni, encoder, *_ = _make_omni()
    omni.start()
    omni._slot_index = 4               # Pos 4 = letzte RX-Slot in Block 1
    # RX-Slot triggert advance, Pos 4 -> 0 = Block-Rollover
    omni.on_cycle_start(cycle_num=300, is_even=True)
    assert omni._slot_index == 0
    assert omni._block == 2            # AC4: Rollover automatisch
    encoder.transmit.assert_not_called()  # Pos 4 war RX

    # Naechster Slot in Block 2 Pos 0 = TX-O (AC3)
    omni.on_cycle_start(cycle_num=301, is_even=False)
    encoder.transmit.assert_called_once_with(
        "CQ DA1MHH JN58", tx_even=False, audio_freq_hz=1500,
    )


# ===========================================================================
# T8 — Block 2 Pos 1: encoder.transmit mit tx_even=True (AC3)
# ===========================================================================
def test_block2_pos1_tx_even(app):
    omni, encoder, *_ = _make_omni()
    omni.start()
    omni._block = 2
    omni._slot_index = 1               # Pos 1 = TX-E in Block 2
    omni.on_cycle_start(cycle_num=400, is_even=True)
    encoder.transmit.assert_called_once_with(
        "CQ DA1MHH JN58", tx_even=True, audio_freq_hz=1500,
    )
    assert omni._slot_index == 2


# ===========================================================================
# T9 — Block 2 -> Block 1 Rollover (AC4)
# ===========================================================================
def test_block2_rollover_back_to_block1(app):
    omni, *_ = _make_omni()
    omni.start()
    omni._block = 2
    omni._slot_index = 4
    omni.on_cycle_start(cycle_num=500, is_even=False)
    assert omni._slot_index == 0
    assert omni._block == 1            # zurueck zu Block 1


# ===========================================================================
# T10 — Block-Alternation permanent ueber 15 Slots (AC4)
# ===========================================================================
def test_block_alternation_permanent_15_slots(app):
    omni, *_ = _make_omni()
    omni.start()
    blocks_seen = []
    for i in range(15):
        blocks_seen.append(omni._block)
        omni.on_cycle_start(cycle_num=600 + i, is_even=(i % 2 == 0))
    # Slots 0-4 = Block 1, 5-9 = Block 2, 10-14 = Block 1
    assert blocks_seen[0:5] == [1, 1, 1, 1, 1]
    assert blocks_seen[5:10] == [2, 2, 2, 2, 2]
    assert blocks_seen[10:15] == [1, 1, 1, 1, 1]
    # Nach 15 Slots: slot_index zurueck auf 0, Block 2 (16. Slot waere Block 2)
    assert omni._slot_index == 0
    assert omni._block == 2


# ===========================================================================
# T11 — pause friert _slot_index, _active bleibt True (AC17)
# ===========================================================================
def test_pause_freezes_slot_index_active_stays_true(app):
    omni, *_ = _make_omni()
    omni.start()
    omni._slot_index = 3
    omni._block = 2
    omni.pause()
    assert omni.is_active() is True   # AC17: bleibt True
    assert omni.is_paused() is True
    assert omni._slot_index == 3      # eingefroren
    assert omni._block == 2
    # idempotent: zweiter pause-Aufruf no-op
    omni.pause()
    assert omni.is_paused() is True


# ===========================================================================
# T12 — on_cycle_start waehrend Pause = no-op (AC7, AC17)
# ===========================================================================
def test_on_cycle_start_during_pause_no_op(app):
    omni, encoder, *_ = _make_omni()
    omni.start()
    omni._slot_index = 0
    omni.pause()
    omni.on_cycle_start(cycle_num=700, is_even=True)
    encoder.transmit.assert_not_called()
    assert omni._slot_index == 0      # nicht advanced


# ===========================================================================
# T13 — resume_after_qso(even=True) -> Block 2 ab Pos 0 (AC18)
# ===========================================================================
def test_resume_after_qso_even_chooses_block2_pos0(app):
    omni, *_ = _make_omni()
    omni.start()
    omni._slot_index = 3              # mid-Block einfrieren
    omni.pause()
    omni.resume_after_qso(last_was_even=True)
    assert omni._block == 2            # AC18: even -> Block 2
    assert omni._slot_index == 0
    assert omni.is_paused() is False
    assert omni.is_active() is True


# ===========================================================================
# T14 — resume_after_qso(even=False) -> Block 1 ab Pos 0 (AC18)
# ===========================================================================
def test_resume_after_qso_odd_chooses_block1_pos0(app):
    omni, *_ = _make_omni()
    omni.start()
    omni._block = 2
    omni._slot_index = 3
    omni.pause()
    omni.resume_after_qso(last_was_even=False)
    assert omni._block == 1            # AC18: odd -> Block 1
    assert omni._slot_index == 0
    assert omni.is_paused() is False


# ===========================================================================
# T15 — resume_after_qso no-op wenn nicht pausiert (AC18 Pre-Check, R1)
# ===========================================================================
def test_resume_after_qso_no_op_when_not_paused(app):
    omni, *_ = _make_omni()
    omni.start()
    omni._slot_index = 2
    omni._block = 2
    # NICHT pause() rufen — resume_after_qso muss no-op sein
    omni.resume_after_qso(last_was_even=True)
    assert omni._block == 2            # unveraendert
    assert omni._slot_index == 2


# ===========================================================================
# T16 — stop reset full state (AC20, AC21, parametrize 8 reasons)
# ===========================================================================
@pytest.mark.parametrize(
    "reason",
    ["manual_halt", "band_change", "mode_change", "rx_mode_change",
     "totmann_expired", "superseded", "easter_egg_off", "test_cleanup"],
)
def test_stop_resets_full_state(app, reason):
    omni, *_ = _make_omni()
    captured: list[str] = []
    omni.omni_stopped.connect(lambda r: captured.append(r))
    omni.start()
    omni._slot_index = 3
    omni._block = 2
    omni._cq_even_count = 5
    omni._cq_odd_count = 4
    omni._cq_audio_hz = 1700
    omni.stop(reason)
    assert omni.is_active() is False
    assert omni.is_paused() is False
    assert omni._slot_index == 0
    assert omni._block == 1
    assert omni._cq_audio_hz is None
    assert omni._cq_even_count == 0
    assert omni._cq_odd_count == 0
    assert captured == [reason]
    # idempotent: zweiter stop-Aufruf no-op
    omni.stop(reason)
    assert captured == [reason]        # kein zweites Emit


# ===========================================================================
# T17 — Frequenz-Init aus diversity beim ersten TX (AC12)
# ===========================================================================
def test_freq_init_from_diversity_first_tx(app):
    omni, encoder, diversity, _ = _make_omni(free_cq_freq=2300)
    captured: list[int] = []
    omni.cq_freq_changed.connect(lambda f: captured.append(f))
    omni.start()
    assert omni._cq_audio_hz is None
    omni.on_cycle_start(cycle_num=800, is_even=True)
    diversity.get_free_cq_freq.assert_called_once()
    assert omni._cq_audio_hz == 2300
    assert captured == [2300]
    # encoder bekommt die Sticky-Freq
    args, kwargs = encoder.transmit.call_args
    assert kwargs["audio_freq_hz"] == 2300


# ===========================================================================
# T18 — Fallback 1500 wenn diversity None returnt (AC12)
# ===========================================================================
def test_freq_fallback_1500_when_diversity_none(app):
    omni, encoder, *_ = _make_omni(free_cq_freq=None)
    captured: list[int] = []
    omni.cq_freq_changed.connect(lambda f: captured.append(f))
    omni.start()
    omni.on_cycle_start(cycle_num=900, is_even=True)
    assert omni._cq_audio_hz == 1500
    assert captured == [1500]


# ===========================================================================
# T19 — Frequenz-Sticky: 1x init, dann fest ueber 5 Cycles (AC13)
# ===========================================================================
def test_freq_sticky_during_omni_5_cycles(app):
    omni, encoder, diversity, _ = _make_omni(free_cq_freq=1700)
    omni.start()
    # 5 Slots durchlaufen — diversity nur 1x rufen
    for i in range(5):
        omni.on_cycle_start(cycle_num=1000 + i, is_even=(i % 2 == 0))
    # diversity nur 1x gerufen (beim 1. TX-Slot Pos 0)
    assert diversity.get_free_cq_freq.call_count == 1
    assert omni._cq_audio_hz == 1700
    # Beide TX-Calls (Pos 0 + Pos 1) bekamen 1700 Hz
    tx_calls = [c for c in encoder.transmit.call_args_list]
    assert len(tx_calls) == 2
    for call in tx_calls:
        _, kwargs = call
        assert kwargs["audio_freq_hz"] == 1700


# ===========================================================================
# T20 — Frequenz behaelt Wert ueber pause/resume (AC14)
# ===========================================================================
def test_freq_kept_during_pause_resume(app):
    omni, _enc, diversity, _ = _make_omni(free_cq_freq=1800)
    omni.start()
    omni.on_cycle_start(cycle_num=1100, is_even=True)   # init freq
    assert omni._cq_audio_hz == 1800
    omni.pause()
    assert omni._cq_audio_hz == 1800   # bleibt
    omni.resume_after_qso(last_was_even=True)
    assert omni._cq_audio_hz == 1800   # bleibt
    # diversity wurde NICHT erneut gerufen
    assert diversity.get_free_cq_freq.call_count == 1


# ===========================================================================
# T21 — encoder busy: kein Counter, kein slot_action, aber advance (AC11, R1)
# ===========================================================================
def test_encoder_busy_no_counter_no_slot_action_but_advance(app):
    omni, encoder, *_ = _make_omni()
    encoder.transmit.return_value = False    # busy
    omni.start()
    captured_counter: list[tuple[int, int]] = []
    captured_slot: list[tuple[str, bool, bool]] = []
    omni.counter_changed.connect(
        lambda e, o: captured_counter.append((e, o))
    )
    omni.slot_action.connect(
        lambda lbl, tx, tev: captured_slot.append((lbl, tx, tev))
    )
    omni.on_cycle_start(cycle_num=1200, is_even=True)
    # encoder.transmit gerufen, aber Counter unveraendert
    encoder.transmit.assert_called_once()
    assert omni._cq_even_count == 0
    assert omni._cq_odd_count == 0
    assert captured_counter == []
    assert captured_slot == []                 # kein slot_action bei busy
    # AC10: _slot_index advanced trotzdem (Pattern-Sync)
    assert omni._slot_index == 1


# ===========================================================================
# T22 — Alle 5 Signale werden korrekt emittet (AC22-26)
# ===========================================================================
def test_signals_emitted_correctly(app):
    omni, _enc, _div, _ = _make_omni(free_cq_freq=1600)
    started: list[None] = []
    stopped: list[str] = []
    slot_actions: list[tuple[str, bool, bool]] = []
    freq_changes: list[int] = []
    counter_changes: list[tuple[int, int]] = []
    omni.omni_started.connect(lambda: started.append(None))
    omni.omni_stopped.connect(lambda r: stopped.append(r))
    omni.slot_action.connect(
        lambda lbl, tx, tev: slot_actions.append((lbl, tx, tev))
    )
    omni.cq_freq_changed.connect(lambda f: freq_changes.append(f))
    omni.counter_changed.connect(
        lambda e, o: counter_changes.append((e, o))
    )

    omni.start()                               # AC22: omni_started
    omni.on_cycle_start(cycle_num=1300, is_even=True)   # Pos 0 TX-E
    omni.on_cycle_start(cycle_num=1301, is_even=False)  # Pos 1 TX-O
    omni.on_cycle_start(cycle_num=1302, is_even=True)   # Pos 2 RX-E
    omni.stop("manual_halt")                   # AC23

    assert len(started) == 1                   # omni_started 1x (AC22)
    assert stopped == ["manual_halt"]          # omni_stopped (AC23)
    assert freq_changes == [1600]              # cq_freq_changed 1x (AC25)
    assert counter_changes == [(1, 0), (1, 1)]  # 2x TX-Erfolg (AC26)
    # slot_action: 2x TX (AC24) + 1x RX = 3
    assert len(slot_actions) == 3
    assert slot_actions[0][1] is True          # TX
    assert slot_actions[1][1] is True          # TX
    assert slot_actions[2][1] is False         # RX
