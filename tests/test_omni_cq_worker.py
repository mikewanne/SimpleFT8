"""Unit-Tests fuer P4.OMNI-NEUBAU C2 — core/omni_cq.py.

Deckt V3 §5 Test-Plan T1-T20 ab. Hardware-frei, Qt-offscreen via env.
Encoder/Diversity/Timer als MagicMock — der echte Worker-Thread wird
fuer Lifecycle-Tests nur kurz gestartet und sofort gestoppt.
"""
from __future__ import annotations

import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import sys
import time
import threading
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


def _make_omni(
    *,
    cycle_duration: float = 15.0,
    is_even_cycle: bool = False,
    free_cq_freq: int | None = 1500,
) -> tuple[OmniCQ, MagicMock, MagicMock, MagicMock]:
    """Hilfsfunktion: OmniCQ + Mocks erzeugen, Defaults gesetzt."""
    encoder = MagicMock()
    encoder.transmit = MagicMock(return_value=True)
    encoder.tx_even = None
    encoder.audio_freq_hz = 1500

    diversity = MagicMock()
    diversity.get_free_cq_freq = MagicMock(return_value=free_cq_freq)

    timer = MagicMock()
    timer.cycle_duration = cycle_duration
    timer.is_even_cycle = MagicMock(return_value=is_even_cycle)

    omni = OmniCQ(
        encoder=encoder,
        diversity_ctrl=diversity,
        timer=timer,
        my_call="DA1MHH",
        my_grid="JN58",
    )
    return omni, encoder, diversity, timer


# ---------------------------------------------------------------------------
# T1 — initial state
# ---------------------------------------------------------------------------
def test_initial_state_inactive(app):
    omni, *_ = _make_omni()
    assert omni.is_active() is False
    assert omni.is_paused() is False
    assert omni.cq_even_count == 0
    assert omni.cq_odd_count == 0
    assert omni.cq_audio_hz is None
    assert omni._slot_index == 0
    assert omni._block == 1


# ---------------------------------------------------------------------------
# T2 / T3 — start mit Paritaet -> Block-Wahl
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "next_is_even, expected_block",
    [(True, 1), (False, 2)],
    ids=["even_first_block1", "odd_first_block2"],
)
def test_start_paritaet_waehlt_block(app, next_is_even, expected_block):
    omni, *_ = _make_omni()
    # Worker-Loop sofort blockieren via stop_event-Trick: wir blockieren NICHT
    # hier — start() spawnt den Thread, wir warten kurz und stoppen sauber.
    omni.start(next_is_even=next_is_even)
    try:
        assert omni._block == expected_block
        assert omni._slot_index == 0
        assert omni.is_active() is True
        assert omni.is_paused() is False
    finally:
        omni.stop("test_cleanup")
    assert omni.is_active() is False


# ---------------------------------------------------------------------------
# T4 — Block 1 Pattern (parametrize 0..4)
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "slot_index, expected",
    [
        (0, (True, True)),    # TX-E
        (1, (True, False)),   # TX-O
        (2, (False, False)),  # RX
        (3, (False, False)),  # RX
        (4, (False, False)),  # RX
    ],
)
def test_next_slot_action_block1_pattern(app, slot_index, expected):
    omni, *_ = _make_omni()
    omni._block = 1
    omni._slot_index = slot_index
    assert omni._next_slot_action() == expected


# ---------------------------------------------------------------------------
# T5 — Block 2 Pattern (parametrize 0..4)
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "slot_index, expected",
    [
        (0, (True, False)),   # TX-O
        (1, (True, True)),    # TX-E
        (2, (False, False)),  # RX
        (3, (False, False)),  # RX
        (4, (False, False)),  # RX
    ],
)
def test_next_slot_action_block2_pattern(app, slot_index, expected):
    omni, *_ = _make_omni()
    omni._block = 2
    omni._slot_index = slot_index
    assert omni._next_slot_action() == expected


# ---------------------------------------------------------------------------
# T6 — Block-Rollover nach 5 Slots
# ---------------------------------------------------------------------------
def test_block_rollover_after_5_slots(app):
    omni, *_ = _make_omni()
    omni._block = 1
    omni._slot_index = 0
    omni._block_count = 0

    # 5x advance = ein Block durchgespielt -> Block 2, slot 0
    for _ in range(5):
        omni._advance_state()
    assert omni._slot_index == 0
    assert omni._block == 2
    assert omni._block_count == 1

    # weitere 5 -> zurueck zu Block 1
    for _ in range(5):
        omni._advance_state()
    assert omni._block == 1
    assert omni._block_count == 2


# ---------------------------------------------------------------------------
# T7 / T8 — resume_after_qso Block-Wahl
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "last_qso_was_even, expected_block",
    [(True, 2), (False, 1)],
    ids=["even_qso_choses_block2", "odd_qso_choses_block1"],
)
def test_resume_after_qso_chooses_block(app, last_qso_was_even, expected_block):
    omni, *_ = _make_omni()
    omni.start(next_is_even=True)  # erst hochfahren
    omni.pause()
    try:
        omni.resume_after_qso(last_qso_was_even=last_qso_was_even)
        assert omni._block == expected_block
        assert omni._slot_index == 0
    finally:
        omni.stop("test_cleanup")


# ---------------------------------------------------------------------------
# T9 — resume IMMER ab Pos 0
# ---------------------------------------------------------------------------
def test_resume_starts_from_pos_0_always(app):
    omni, *_ = _make_omni()
    omni.start(next_is_even=False)  # Block 2
    omni._slot_index = 3  # mid-Block einfrieren
    omni.pause()
    try:
        assert omni._slot_index == 3  # pause friert
        omni.resume_after_qso(last_qso_was_even=False)  # → Block 1
        assert omni._slot_index == 0
    finally:
        omni.stop("test_cleanup")


# ---------------------------------------------------------------------------
# T10 — pause freezes state
# ---------------------------------------------------------------------------
def test_pause_freezes_state(app):
    omni, *_ = _make_omni()
    omni.start(next_is_even=True)
    omni._slot_index = 2
    omni._block_count = 7
    omni.pause()
    try:
        # is_active bleibt True (Worker pausiert, Lifecycle laeuft logisch),
        # is_paused True. Slot-Index/Block-Count eingefroren.
        assert omni.is_active() is True
        assert omni.is_paused() is True
        assert omni._slot_index == 2
        assert omni._block_count == 7
    finally:
        omni.stop("test_cleanup")


# ---------------------------------------------------------------------------
# T11 — stop_cleans_state (parametrize alle 5 reasons)
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "reason",
    ["manual_halt", "band_change", "mode_change", "rx_mode_change",
     "totmann_expired"],
)
def test_stop_cleans_state(app, reason):
    omni, *_ = _make_omni()
    captured: list[str] = []
    omni.omni_stopped.connect(lambda r: captured.append(r))
    omni.start(next_is_even=True)
    omni.stop(reason)
    assert omni.is_active() is False
    assert omni.is_paused() is False
    assert captured == [reason]


# ---------------------------------------------------------------------------
# T12 — _maybe_recheck_freq nur alle 4 Bloecke
# ---------------------------------------------------------------------------
def test_freq_recheck_every_4_blocks(app):
    omni, _enc, diversity, _t = _make_omni(free_cq_freq=1700)
    omni._cq_audio_hz = 1500  # initial gesetzt

    # Block_count 1, 2, 3 -> kein recheck
    for bc in (1, 2, 3):
        omni._block_count = bc
        omni._maybe_recheck_freq()
    assert diversity.get_free_cq_freq.call_count == 0
    assert omni._cq_audio_hz == 1500

    # Block_count 4 -> recheck triggert
    omni._block_count = 4
    omni._maybe_recheck_freq()
    assert diversity.get_free_cq_freq.call_count == 1
    assert omni._cq_audio_hz == 1700

    # Block_count 5..7 wieder kein recheck
    for bc in (5, 6, 7):
        omni._block_count = bc
        omni._maybe_recheck_freq()
    assert diversity.get_free_cq_freq.call_count == 1


# ---------------------------------------------------------------------------
# T13 — sticky wenn diversity gleichen Wert returnt
# ---------------------------------------------------------------------------
def test_freq_sticky_when_unchanged(app):
    omni, _enc, _div, _t = _make_omni(free_cq_freq=1500)
    omni._cq_audio_hz = 1500
    omni._block_count = 4
    captured: list[int] = []
    omni.cq_freq_changed.connect(lambda f: captured.append(f))
    omni._maybe_recheck_freq()
    assert omni._cq_audio_hz == 1500
    assert captured == []   # kein emit weil unchanged


# ---------------------------------------------------------------------------
# T14 — emit wenn diversity neue Frequenz returnt
# ---------------------------------------------------------------------------
def test_freq_changes_when_diversity_returns_new(app):
    omni, _enc, _div, _t = _make_omni(free_cq_freq=2000)
    omni._cq_audio_hz = 1500
    omni._block_count = 4
    captured: list[int] = []
    omni.cq_freq_changed.connect(lambda f: captured.append(f))
    omni._maybe_recheck_freq()
    assert omni._cq_audio_hz == 2000
    assert captured == [2000]


# ---------------------------------------------------------------------------
# T15 — Fallback 1500 wenn diversity None returnt
# ---------------------------------------------------------------------------
def test_freq_fallback_when_diversity_returns_none(app):
    omni, *_ = _make_omni(free_cq_freq=None)
    captured: list[int] = []
    omni.cq_freq_changed.connect(lambda f: captured.append(f))
    freq = omni._ensure_audio_freq()
    assert freq == 1500
    assert omni._cq_audio_hz == 1500
    assert captured == [1500]


# ---------------------------------------------------------------------------
# T16 — _compute_next_boundary mit Paritaet (parametrize)
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "now, target_even, expected",
    [
        # SLOT=15s. now=10s -> cycle_num=0 -> next=15.
        # cycle 1 ist odd -> bei target_even=True muss +15 (cycle 2 = even).
        (10.0, True, 30.0),
        (10.0, False, 15.0),
        # now=20s -> cycle_num=1 -> next=30 (cycle 2 = even).
        (20.0, True, 30.0),
        (20.0, False, 45.0),
    ],
)
def test_compute_next_boundary_target_even(app, monkeypatch, now,
                                           target_even, expected):
    omni, *_ = _make_omni()
    monkeypatch.setattr("core.omni_cq.time.time", lambda: now)
    assert omni._compute_next_boundary(target_even) == pytest.approx(expected)


# ---------------------------------------------------------------------------
# T17 — RX-Boundary ohne Paritaets-Filter
# ---------------------------------------------------------------------------
def test_compute_next_boundary_rx_no_filter(app, monkeypatch):
    omni, *_ = _make_omni(cycle_duration=15.0)
    monkeypatch.setattr("core.omni_cq.time.time", lambda: 12.0)
    # cycle_num=0 -> next boundary 15
    assert omni._compute_next_boundary(None) == pytest.approx(15.0)
    monkeypatch.setattr("core.omni_cq.time.time", lambda: 17.0)
    # cycle_num=1 -> next boundary 30
    assert omni._compute_next_boundary(None) == pytest.approx(30.0)


# ---------------------------------------------------------------------------
# T18 — atomic transmit API: tx_even kwarg
# ---------------------------------------------------------------------------
def test_atomic_transmit_api_tx_even_kwarg(app):
    omni, encoder, *_ = _make_omni()
    omni._cq_audio_hz = 1500  # vermeidet diversity-call im _ensure_audio_freq
    omni._do_tx_slot(target_even=True)
    encoder.transmit.assert_called_once()
    args, kwargs = encoder.transmit.call_args
    assert kwargs.get("tx_even") is True
    assert kwargs.get("audio_freq_hz") == 1500


# ---------------------------------------------------------------------------
# T19 — atomic transmit API: audio_freq_hz kwarg
# ---------------------------------------------------------------------------
def test_atomic_transmit_api_audio_freq_kwarg(app):
    omni, encoder, *_ = _make_omni(free_cq_freq=2300)
    omni._do_tx_slot(target_even=False)
    args, kwargs = encoder.transmit.call_args
    assert kwargs.get("audio_freq_hz") == 2300
    # CQ-Message Format: "CQ <call> <grid>"
    msg = args[0] if args else kwargs.get("message")
    assert msg == "CQ DA1MHH JN58"


# ---------------------------------------------------------------------------
# T20 — resume joint alten Worker (R1 R3 Defense-in-Depth)
# ---------------------------------------------------------------------------
def test_resume_joins_old_worker(app):
    omni, *_ = _make_omni()
    omni.start(next_is_even=True)
    omni.pause()
    # Faked alten Worker injizieren (lebt noch) — resume_after_qso muss joinen.
    fake_old = MagicMock()
    fake_old.is_alive = MagicMock(return_value=True)
    fake_old.join = MagicMock()
    omni._thread = fake_old
    try:
        omni.resume_after_qso(last_qso_was_even=False)
    finally:
        omni.stop("test_cleanup")
    fake_old.join.assert_called_once()


# ---------------------------------------------------------------------------
# Bonus — Counter inkrementieren bei TX-Erfolg
# ---------------------------------------------------------------------------
def test_counters_increment_on_successful_tx(app):
    omni, encoder, *_ = _make_omni()
    omni._cq_audio_hz = 1500
    captured: list[tuple[int, int]] = []
    omni.counter_changed.connect(lambda e, o: captured.append((e, o)))
    omni._do_tx_slot(target_even=True)
    omni._do_tx_slot(target_even=False)
    omni._do_tx_slot(target_even=True)
    assert omni.cq_even_count == 2
    assert omni.cq_odd_count == 1
    assert captured == [(1, 0), (1, 1), (2, 1)]


# ---------------------------------------------------------------------------
# Bonus — encoder.transmit returnt False -> kein Counter-Increment
# ---------------------------------------------------------------------------
def test_busy_encoder_does_not_increment_counter(app):
    omni, encoder, *_ = _make_omni()
    encoder.transmit.return_value = False
    omni._cq_audio_hz = 1500
    omni._do_tx_slot(target_even=True)
    assert omni.cq_even_count == 0
    assert omni.cq_odd_count == 0
