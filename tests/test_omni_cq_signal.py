"""Unit-Tests fuer P7.OMNI-SIMPLIFY — core/omni_cq.py (single-slot v0.96.4).

Mike-Spec 10.05.2026: OMNI = Single-Slot-CQ in EINER Paritaet, Wechsel
ueber Diversity-Such-Counter alle ~10 Min.

Deckt V3 §5 AC1-AC13 + R1-SF-1 ab. Tests rufen on_cycle_start direkt mit
synthetischen Werten — KEIN Worker/Sleep-Mock (Lesson
feedback_test_critical_path_not_mock.md).
"""
from __future__ import annotations

import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import sys
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtWidgets import QApplication

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from core.omni_cq import OmniCQ, _OMNI_FLIP_AFTER_SEARCHES  # noqa: E402


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def _make_omni(*, free_cq_freq: int | None = 1500,
               diversity_phase: str = "operate"):
    """Test-Setup: OmniCQ mit Mock-Encoder/Diversity/Timer."""
    encoder = MagicMock()
    encoder.transmit = MagicMock(return_value=True)
    diversity = MagicMock()
    diversity.get_free_cq_freq = MagicMock(return_value=free_cq_freq)
    # phase als gewoehnliche Property (str) — testbar via direct set
    diversity.phase = diversity_phase
    timer = MagicMock()
    timer.cycle_duration = 15.0
    omni = OmniCQ(
        encoder=encoder,
        diversity_ctrl=diversity,
        timer=timer,
        my_call="DA1MHH",
        my_grid="JN58",
    )
    return omni, encoder, diversity, timer


# ── T1: AC1 Initial-State ──────────────────────────────────────────


def test_start_initial_state(app):
    """T1 (AC1): start setzt _active=True, alles andere Default."""
    omni, *_ = _make_omni()
    omni.start()
    assert omni.is_active() is True
    assert omni.is_paused() is False
    assert omni.cq_count == 0
    assert omni.cq_tx_even is None
    assert omni.cq_audio_hz is None
    assert omni._search_trigger_count == 0


# ── T2: AC2 Erster Cycle setzt _cq_tx_even aus fresh time ──────────


@pytest.mark.parametrize("fake_time, expected_tx_even", [
    (16005.0, True),    # 16005/15 = 1067 -> Even
    (16020.0, False),   # 16020/15 = 1068 -> Even? 1068%2==0 -> True. Korrektur:
    # cycle 1067 = odd? 1067%2=1 -> odd. 1068=even.
    # Lass das pytest selbst berechnen
])
def test_first_cycle_sets_tx_even_from_fresh_time(app, fake_time, expected_tx_even):
    """T2 (AC2): _cq_tx_even = fresh_is_even beim ersten on_cycle_start."""
    omni, encoder, *_ = _make_omni()
    # parametrize-Werte sind nur Anker — echte Erwartung dynamisch berechnen
    expected = (int(fake_time / 15.0) % 2 == 0)
    omni.start()
    with patch("core.omni_cq.time.time", return_value=fake_time):
        omni.on_cycle_start(cycle_num=999, is_even=False)  # signal-is_even ignoriert
    assert omni.cq_tx_even is expected


# ── T3: AC3 Matching Slot -> encoder.transmit + emits ──────────────


def test_matching_cycle_calls_encoder_transmit_and_emits(app):
    """T3 (AC3): Slot mit passender Paritaet -> encoder.transmit + counter + emits."""
    omni, encoder, *_ = _make_omni()
    captured_count: list[tuple[int, bool]] = []
    captured_slot: list[tuple[str, bool, bool]] = []
    omni.cq_count_changed.connect(
        lambda c, e: captured_count.append((c, e))
    )
    omni.slot_action.connect(
        lambda lbl, tx, tev: captured_slot.append((lbl, tx, tev))
    )
    omni.start()
    # fake_time so wahlen dass cycle_num gerade ist (Even)
    fake_time = 15.0  # cycle 1 -> odd. Lass uns 30.0 nehmen -> cycle 2 -> even
    fake_time = 30.0  # cycle 2 -> even
    with patch("core.omni_cq.time.time", return_value=fake_time):
        omni.on_cycle_start(cycle_num=999, is_even=False)
    assert omni.cq_tx_even is True  # fresh ist Even
    encoder.transmit.assert_called_once_with(
        "CQ DA1MHH JN58", tx_even=True, audio_freq_hz=1500,
    )
    assert omni.cq_count == 1
    assert captured_count == [(1, True)]
    assert len(captured_slot) == 1
    assert captured_slot[0][1] is True   # is_tx
    assert captured_slot[0][2] is True   # tx_even


# ── T4: AC4 Non-matching Slot -> kein encoder ──────────────────────


def test_non_matching_cycle_skips_encoder(app):
    """T4 (AC4): Slot mit anderer Paritaet -> KEIN encoder.transmit."""
    omni, encoder, *_ = _make_omni()
    omni.start()
    omni._cq_tx_even = True  # OMNI sendet in Even
    omni._cq_audio_hz = 1500  # bereits initialisiert
    fake_time = 15.0  # cycle 1 -> Odd (mismatch)
    with patch("core.omni_cq.time.time", return_value=fake_time):
        omni.on_cycle_start(cycle_num=999, is_even=True)
    encoder.transmit.assert_not_called()
    assert omni.cq_count == 0


# ── T5: AC5 No-op waehrend Diversity-Mess-Phase ────────────────────


def test_skips_during_diversity_measure_phase(app):
    """T5 (AC5): on_cycle_start no-op wenn diversity.phase != 'operate'."""
    omni, encoder, diversity, _ = _make_omni(diversity_phase="measure")
    omni.start()
    omni.on_cycle_start(cycle_num=100, is_even=True)
    encoder.transmit.assert_not_called()
    assert omni.cq_tx_even is None  # nicht initialisiert


# ── T6: AC6 flip_tx_parity toggelt + emit parity_flipped ───────────


def test_flip_tx_parity_toggles_and_emits(app):
    """T6 (AC6): flip toggelt _cq_tx_even, emit parity_flipped(new_value)."""
    omni, *_ = _make_omni()
    captured: list[bool] = []
    omni.parity_flipped.connect(lambda new: captured.append(new))
    omni.start()
    omni._cq_tx_even = True
    omni.flip_tx_parity()
    assert omni.cq_tx_even is False
    assert captured == [False]
    omni.flip_tx_parity()
    assert omni.cq_tx_even is True
    assert captured == [False, True]


# ── T7: AC7 flip bei _cq_tx_even=None -> no-op ─────────────────────


def test_flip_tx_parity_noop_when_uninitialized(app):
    """T7 (AC7): flip vor erstem on_cycle_start (_cq_tx_even=None) -> no-op."""
    omni, *_ = _make_omni()
    captured: list[bool] = []
    omni.parity_flipped.connect(lambda new: captured.append(new))
    omni.start()
    assert omni.cq_tx_even is None
    omni.flip_tx_parity()
    assert omni.cq_tx_even is None
    assert captured == []


def test_flip_tx_parity_noop_when_inactive(app):
    """T7b: flip bei nicht-aktivem OMNI -> no-op."""
    omni, *_ = _make_omni()
    captured: list[bool] = []
    omni.parity_flipped.connect(lambda new: captured.append(new))
    # nicht gestartet -> _active=False
    omni._cq_tx_even = True  # manuell setzen
    omni.flip_tx_parity()
    assert captured == []


# ── T8: AC8 on_search_trigger Counter + Flip bei Threshold ─────────


def test_on_search_trigger_counts_and_flips_at_threshold(app):
    """T8 (AC8): Counter inkrementiert, bei _OMNI_FLIP_AFTER_SEARCHES flip + Reset."""
    omni, *_ = _make_omni()
    captured: list[bool] = []
    omni.parity_flipped.connect(lambda new: captured.append(new))
    omni.start()
    omni._cq_tx_even = True  # initialisiert (sonst flip no-op)

    # _OMNI_FLIP_AFTER_SEARCHES - 1 mal triggern: noch kein Flip
    for _ in range(_OMNI_FLIP_AFTER_SEARCHES - 1):
        omni.on_search_trigger()
    assert omni._search_trigger_count == _OMNI_FLIP_AFTER_SEARCHES - 1
    assert omni.cq_tx_even is True
    assert captured == []

    # N-ter Trigger: flip + Counter-Reset
    omni.on_search_trigger()
    assert omni._search_trigger_count == 0
    assert omni.cq_tx_even is False
    assert captured == [False]


def test_on_search_trigger_inactive_noop(app):
    """T8b: on_search_trigger no-op wenn nicht aktiv."""
    omni, *_ = _make_omni()
    omni.on_search_trigger()  # nicht gestartet
    assert omni._search_trigger_count == 0


# ── T10: AC10 Pause: _cq_tx_even bleibt; Resume: bleibt ────────────


def test_pause_resume_preserves_parity(app):
    """T10 (AC10): pause + resume_after_qso bewahren _cq_tx_even."""
    omni, *_ = _make_omni()
    omni.start()
    omni._cq_tx_even = True
    omni._cq_audio_hz = 1500
    omni._cq_count = 5

    omni.pause()
    assert omni.is_paused() is True
    assert omni.cq_tx_even is True   # bleibt
    assert omni.cq_count == 5         # bleibt

    omni.resume_after_qso(last_was_even=False)
    assert omni.is_paused() is False
    assert omni.cq_tx_even is True   # bleibt (last_was_even ignoriert)
    assert omni.cq_count == 5


# ── T11: AC11 Frequenz-Sticky ueber Flip ───────────────────────────


def test_frequency_sticky_across_flip(app):
    """T11 (AC11): _cq_audio_hz bleibt unveraendert ueber Paritaets-Wechsel."""
    omni, encoder, diversity, _ = _make_omni(free_cq_freq=1700)
    omni.start()
    # Erster on_cycle_start -> Frequenz initialisiert
    with patch("core.omni_cq.time.time", return_value=30.0):
        omni.on_cycle_start(cycle_num=1, is_even=True)
    assert omni.cq_audio_hz == 1700

    # Flip -> Frequenz bleibt
    omni.flip_tx_parity()
    assert omni.cq_audio_hz == 1700

    # diversity.get_free_cq_freq nur 1x gerufen (sticky)
    assert diversity.get_free_cq_freq.call_count == 1


# ── T12: AC12 stop reset ────────────────────────────────────────────


def test_stop_resets_all_state(app):
    """T12 (AC12): stop setzt alles zurueck."""
    omni, *_ = _make_omni()
    omni.start()
    omni._cq_tx_even = True
    omni._cq_audio_hz = 1500
    omni._cq_count = 7
    omni._search_trigger_count = 3

    omni.stop("manual_halt")
    assert omni.is_active() is False
    assert omni.is_paused() is False
    assert omni.cq_tx_even is None
    assert omni.cq_audio_hz is None
    assert omni.cq_count == 0
    assert omni._search_trigger_count == 0


# ── T13: AC13 resume_after_qso Signatur kompatibel ─────────────────


def test_resume_after_qso_signature_compat(app):
    """T13 (AC13): resume_after_qso ohne Argument UND mit last_was_even."""
    omni, *_ = _make_omni()
    omni.start()
    omni._cq_tx_even = True
    omni.pause()

    # Ohne Argument
    omni.resume_after_qso()
    assert omni.is_paused() is False

    # Wieder Pausieren + mit Argument
    omni.pause()
    omni.resume_after_qso(last_was_even=True)
    assert omni.is_paused() is False
    omni.pause()
    omni.resume_after_qso(last_was_even=False)
    assert omni.is_paused() is False
    # Argument wird ignoriert -> Paritaet bleibt
    assert omni.cq_tx_even is True


# ── T14: R1-SF-3 on_search_trigger waehrend Pause -> no-op ─────────


def test_on_search_trigger_during_pause_noop(app):
    """T14 (R1-SF-1/SF-3): Defense-in-Depth — Counter zaehlt nicht waehrend Pause."""
    omni, *_ = _make_omni()
    omni.start()
    omni._cq_tx_even = True
    omni.pause()
    omni.on_search_trigger()
    assert omni._search_trigger_count == 0  # no-op trotz active=True


# ── Zusatz: omni_started Signal ────────────────────────────────────


def test_start_emits_omni_started(app):
    """omni_started.emit beim ersten start()."""
    omni, *_ = _make_omni()
    captured: list[None] = []
    omni.omni_started.connect(lambda: captured.append(None))
    omni.start()
    assert captured == [None]
    # idempotent: zweiter start kein Emit
    omni.start()
    assert captured == [None]


def test_stop_emits_omni_stopped_with_reason(app):
    """omni_stopped.emit mit reason."""
    omni, *_ = _make_omni()
    captured: list[str] = []
    omni.omni_stopped.connect(lambda r: captured.append(r))
    omni.start()
    omni.stop("band_change")
    assert captured == ["band_change"]


def test_busy_encoder_no_count(app):
    """encoder.transmit returnt False -> kein Counter, kein slot_action."""
    omni, encoder, *_ = _make_omni()
    encoder.transmit.return_value = False
    captured_count: list[tuple[int, bool]] = []
    captured_slot: list = []
    omni.cq_count_changed.connect(
        lambda c, e: captured_count.append((c, e))
    )
    omni.slot_action.connect(
        lambda *args: captured_slot.append(args)
    )
    omni.start()
    with patch("core.omni_cq.time.time", return_value=30.0):
        omni.on_cycle_start(cycle_num=1, is_even=True)
    encoder.transmit.assert_called_once()
    assert omni.cq_count == 0
    assert captured_count == []
    assert captured_slot == []
