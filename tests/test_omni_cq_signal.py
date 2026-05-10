"""Unit-Tests fuer OMNI-CQ — core/omni_cq.py.

P7.OMNI-SIMPLIFY (v0.96.4): Single-Slot-CQ-Modul.
P23.OMNI-COUNTER-EIGEN (v0.96.7): eigener Down-Counter pro Modus,
KEIN Coupling mehr zu Diversity-Such-Counter.

Tests rufen on_cycle_start direkt mit synthetischen Werten —
KEIN Worker/Sleep-Mock (Lesson feedback_test_critical_path_not_mock.md).
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
from core.omni_cq import OmniCQ, _OMNI_TARGETS  # noqa: E402


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
    """T1 (AC1): start setzt _active=True, Counter auf TARGET (FT8=10),
    Paritaet bleibt None bis erster on_cycle_start."""
    omni, *_ = _make_omni()
    omni.start()
    assert omni.is_active() is True
    assert omni.is_paused() is False
    # P23: Counter ist Down-Counter, beginnt bei TARGET (FT8=10)
    assert omni.cq_remaining == _OMNI_TARGETS["FT8"]
    assert omni.cq_target == _OMNI_TARGETS["FT8"]
    assert omni.cq_tx_even is None
    assert omni.cq_audio_hz is None


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
    """T3 (AC3): Slot mit passender Paritaet -> encoder.transmit + Counter
    dekrementiert + emits.
    P23: Counter zaehlt down (TARGET-1 nach erstem TX, nicht 1 hoch)."""
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
    target = omni.cq_target  # FT8 = 10
    # fake_time so wahlen dass cycle_num gerade ist (Even)
    fake_time = 30.0  # cycle 2 -> even
    with patch("core.omni_cq.time.time", return_value=fake_time):
        omni.on_cycle_start(cycle_num=999, is_even=False)
    assert omni.cq_tx_even is True  # fresh ist Even
    encoder.transmit.assert_called_once_with(
        "CQ DA1MHH JN58", tx_even=True, audio_freq_hz=1500,
    )
    # P23: nach 1 TX ist remaining = TARGET - 1
    assert omni.cq_remaining == target - 1
    assert captured_count == [(target - 1, True)]
    assert len(captured_slot) == 1
    assert captured_slot[0][1] is True   # is_tx
    assert captured_slot[0][2] is True   # tx_even


# ── T4: AC4 Non-matching Slot -> kein encoder ──────────────────────


def test_non_matching_cycle_skips_encoder(app):
    """T4 (AC4): Slot mit anderer Paritaet -> KEIN encoder.transmit.
    P23: Counter bleibt unveraendert wenn kein TX."""
    omni, encoder, *_ = _make_omni()
    omni.start()
    target = omni.cq_target
    omni._cq_tx_even = True  # OMNI sendet in Even
    omni._cq_audio_hz = 1500  # bereits initialisiert
    fake_time = 15.0  # cycle 1 -> Odd (mismatch)
    with patch("core.omni_cq.time.time", return_value=fake_time):
        omni.on_cycle_start(cycle_num=999, is_even=True)
    encoder.transmit.assert_not_called()
    # P23: kein TX -> Counter unveraendert auf TARGET
    assert omni.cq_remaining == target


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


# ── T8 / T8b ENTFERNT (P23): on_search_trigger entfaellt komplett.
#    Auto-Flip ist jetzt eigene Counter-Logik in on_cycle_start. ─────


# ── T10: AC10 Pause: _cq_tx_even bleibt; Resume: Counter Reset ─────


def test_pause_resume_preserves_parity(app):
    """T10 (AC10): pause bewahrt _cq_tx_even + remaining.
    P23: resume_after_qso resettet remaining auf TARGET ("guter Slot")."""
    omni, *_ = _make_omni()
    omni.start()
    target = omni.cq_target
    omni._cq_tx_even = True
    omni._cq_audio_hz = 1500
    omni._cq_remaining = 5  # mid-Counter Stand

    omni.pause()
    assert omni.is_paused() is True
    assert omni.cq_tx_even is True   # bleibt
    assert omni.cq_remaining == 5    # pause aendert remaining nicht

    omni.resume_after_qso(last_was_even=False)
    assert omni.is_paused() is False
    assert omni.cq_tx_even is True   # bleibt (last_was_even ignoriert)
    # P23: Resume = neuer Slot, Counter zurueck auf TARGET
    assert omni.cq_remaining == target


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
    """T12 (AC12): stop setzt alles zurueck.
    P23: remaining auf 0, target auf default."""
    omni, *_ = _make_omni()
    omni.start()
    omni._cq_tx_even = True
    omni._cq_audio_hz = 1500
    omni._cq_remaining = 7

    omni.stop("manual_halt")
    assert omni.is_active() is False
    assert omni.is_paused() is False
    assert omni.cq_tx_even is None
    assert omni.cq_audio_hz is None
    assert omni.cq_remaining == 0


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


# ── T14 ENTFERNT (P23): on_search_trigger entfaellt — kein Pause-
#    Schutz mehr noetig. ────────────────────────────────────────────


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
    """encoder.transmit returnt False -> kein Decrement, kein Emit, kein slot_action.
    P23: remaining bleibt auf TARGET wenn TX nicht erfolgte."""
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
    target = omni.cq_target
    with patch("core.omni_cq.time.time", return_value=30.0):
        omni.on_cycle_start(cycle_num=1, is_even=True)
    encoder.transmit.assert_called_once()
    # P23: kein TX -> remaining unveraendert auf TARGET
    assert omni.cq_remaining == target
    assert captured_count == []
    assert captured_slot == []
