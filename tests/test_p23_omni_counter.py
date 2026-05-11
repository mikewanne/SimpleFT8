"""Tests fuer P23.OMNI-COUNTER-EIGEN — eigener Down-Counter im OMNI.

Mike-Spec 10.05.2026:
- Counter pro Modus: FT8=10, FT4=20, FT2=40 (alle ~5 Min Wallclock)
- Counter zaehlt DOWN nach jedem TX. Bei 0: flip + reset auf TARGET.
- QSO eingehend → Counter Reset auf TARGET
- Antennen-Mess fertig → Counter Reset auf TARGET
- Bandwechsel/Modus-Wechsel → OMNI STOP (heutiges Verhalten)

Tests rufen on_cycle_start direkt mit synthetischen Werten — KEIN
Worker/Sleep-Mock (Lesson feedback_test_critical_path_not_mock.md).
"""
from __future__ import annotations

import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtWidgets import QApplication

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from core.omni_cq import OmniCQ, _OMNI_TARGETS, _OMNI_DEFAULT_TARGET  # noqa: E402


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def _make_omni(*, mode: str = "FT8",
               cycle_duration: float = 15.0,
               free_cq_freq: int | None = 1500,
               diversity_phase: str = "operate"):
    """Test-Setup: OmniCQ mit Mock-Encoder/Diversity/Timer.

    `mode` wird auf timer.mode gesetzt (steuert _OMNI_TARGETS-Lookup).
    `cycle_duration` muss zum Modus passen (FT8=15, FT4=7.5, FT2=3.8).
    """
    encoder = MagicMock()
    encoder.transmit = MagicMock(return_value=True)
    diversity = MagicMock()
    diversity.get_free_cq_freq = MagicMock(return_value=free_cq_freq)
    diversity.phase = diversity_phase
    timer = MagicMock()
    timer.cycle_duration = cycle_duration
    timer.mode = mode
    omni = OmniCQ(
        encoder=encoder,
        diversity_ctrl=diversity,
        timer=timer,
        my_call="DA1MHH",
        my_grid="JN58",
    )
    return omni, encoder, diversity, timer


# ── T1-T4: start() initialisiert remaining=target pro Modus ────────


def test_start_initializes_remaining_to_target_for_ft8(app):
    """T1: FT8 → remaining == 10."""
    omni, *_ = _make_omni(mode="FT8")
    omni.start()
    assert omni.cq_target == 10
    assert omni.cq_remaining == 10


def test_start_target_for_ft4(app):
    """T2: FT4 → remaining == 20."""
    omni, *_ = _make_omni(mode="FT4", cycle_duration=7.5)
    omni.start()
    assert omni.cq_target == 20
    assert omni.cq_remaining == 20


def test_start_target_for_ft2(app):
    """T3: FT2 → remaining == 40."""
    omni, *_ = _make_omni(mode="FT2", cycle_duration=3.8)
    omni.start()
    assert omni.cq_target == 40
    assert omni.cq_remaining == 40


def test_start_target_default_for_unknown_mode(app):
    """T4: unbekannter Modus → Fallback _OMNI_DEFAULT_TARGET (10)."""
    omni, *_ = _make_omni(mode="WSPR")
    omni.start()
    assert omni.cq_target == _OMNI_DEFAULT_TARGET
    assert omni.cq_remaining == _OMNI_DEFAULT_TARGET


# ── T5: TX dekrementiert um 1 + 1 Emit ─────────────────────────────


def test_tx_decrements_remaining_by_one(app):
    """T5: nach 1 erfolgreichem TX: remaining == TARGET-1 (intern), GENAU 1 Emit.

    P31 (11.05.2026): Display-Wert ist PRE-decrement (Mike-Erwartung: ↻10
    fuer ersten Slot, ↻9 fuer zweiten, ...). Emit liefert pre-decrement.
    Interner _cq_remaining bleibt post-decrement (verbleibende Versuche).
    """
    omni, *_ = _make_omni(mode="FT8")
    captured: list[tuple[int, bool]] = []
    omni.cq_count_changed.connect(lambda r, e: captured.append((r, e)))
    omni.start()
    target = omni.cq_target
    # Slot mit passender Paritaet (Even bei time=30.0/15 = cycle 2 = Even)
    with patch("core.omni_cq.time.time", return_value=30.0):
        omni.on_cycle_start(cycle_num=2, is_even=True)
    assert omni.cq_remaining == target - 1  # interner Counter
    assert omni.cq_remaining_display == target  # P31: Display = pre-decrement
    assert captured == [(target, True)]  # P31: Emit = Display-Wert


# ── T6: encoder busy → kein Decrement, kein Emit ───────────────────


def test_tx_busy_does_not_decrement(app):
    """T6: encoder.transmit returnt False → remaining unveraendert + KEIN Emit."""
    omni, encoder, *_ = _make_omni(mode="FT8")
    encoder.transmit.return_value = False
    captured: list = []
    omni.cq_count_changed.connect(lambda r, e: captured.append((r, e)))
    omni.start()
    target = omni.cq_target
    with patch("core.omni_cq.time.time", return_value=30.0):
        omni.on_cycle_start(cycle_num=2, is_even=True)
    assert omni.cq_remaining == target
    assert captured == []


# ── T7: TARGET TXs → Auto-Flip + Reset, GENAU 1 Emit pro Slot ──────


def test_remaining_reaches_zero_triggers_flip_and_reset_with_one_emit(app):
    """T7 (R1-S1 + P31): TARGET TXs in Folge → genau TARGET Emits.

    P31 (11.05.2026): Emits liefern Display-Wert (pre-decrement). Sequenz:
    TARGET, TARGET-1, ..., 1 (statt frueher TARGET-1, ..., 1, TARGET-mit-Reset).
    Tx_even im Emit ist DISPLAY-Paritaet (vor Flip) = True bis zum Schluss.
    Genau 1 parity_flipped am Ende.
    """
    omni, *_ = _make_omni(mode="FT8")
    captured_count: list[tuple[int, bool]] = []
    captured_flips: list[bool] = []
    omni.cq_count_changed.connect(lambda r, e: captured_count.append((r, e)))
    omni.parity_flipped.connect(lambda new: captured_flips.append(new))
    omni.start()
    target = omni.cq_target  # FT8 = 10
    # TARGET TXs ausfuehren (alle in Even-Slot)
    for i in range(target):
        with patch("core.omni_cq.time.time", return_value=30.0):
            omni.on_cycle_start(cycle_num=2, is_even=True)
    # GENAU TARGET cq_count_changed-Emits
    assert len(captured_count) == target
    # P31: Display-Sequenz pre-decrement: TARGET, TARGET-1, ..., 1
    expected_values = list(range(target, 0, -1))
    actual_values = [c[0] for c in captured_count]
    assert actual_values == expected_values
    # P31: tx_even im Emit ist DISPLAY-Paritaet (pre-flip) = True alle 10x
    actual_parities = [c[1] for c in captured_count]
    assert all(p is True for p in actual_parities)
    # Genau 1 Flip am Schluss
    assert len(captured_flips) == 1
    assert captured_flips[0] is False  # von Even auf Odd
    # remaining (intern) ist jetzt TARGET (nach Reset), Paritaet ist Odd
    assert omni.cq_remaining == target
    assert omni.cq_tx_even is False


# ── T8: resume_after_qso resettet remaining ────────────────────────


def test_resume_after_qso_resets_remaining(app):
    """T8: pause + dekrementieren auf TARGET-3 + resume_after_qso → TARGET."""
    omni, *_ = _make_omni(mode="FT8")
    captured: list[tuple[int, bool]] = []
    omni.cq_count_changed.connect(lambda r, e: captured.append((r, e)))
    omni.start()
    target = omni.cq_target
    omni._cq_tx_even = True
    omni._cq_remaining = target - 3  # mid-Counter

    omni.pause()
    captured.clear()  # nur den Resume-Emit messen
    omni.resume_after_qso()
    assert omni.cq_remaining == target
    assert captured == [(target, True)]


# ── T9-T12: reset_counter_after_measure ────────────────────────────


def test_reset_counter_after_measure_resets_remaining(app):
    """T9: aktiver OMNI mit remaining=5 → reset → remaining=TARGET + 1 Emit."""
    omni, *_ = _make_omni(mode="FT8")
    captured: list[tuple[int, bool]] = []
    omni.cq_count_changed.connect(lambda r, e: captured.append((r, e)))
    omni.start()
    target = omni.cq_target
    omni._cq_tx_even = True
    omni._cq_remaining = 5

    omni.reset_counter_after_measure()
    assert omni.cq_remaining == target
    assert captured == [(target, True)]


def test_reset_counter_after_measure_noop_when_inactive(app):
    """T10: nicht aktiv → no-op (kein Emit, remaining bleibt 0)."""
    omni, *_ = _make_omni(mode="FT8")
    captured: list = []
    omni.cq_count_changed.connect(lambda r, e: captured.append((r, e)))
    # nicht gestartet
    omni.reset_counter_after_measure()
    assert omni.cq_remaining == 0
    assert captured == []


def test_reset_counter_after_measure_noop_when_paused(app):
    """T11: paused → no-op (resume_after_qso macht den Reset selbst)."""
    omni, *_ = _make_omni(mode="FT8")
    captured: list = []
    omni.cq_count_changed.connect(lambda r, e: captured.append((r, e)))
    omni.start()
    omni._cq_tx_even = True
    omni._cq_remaining = 5
    omni.pause()
    omni.reset_counter_after_measure()
    assert omni.cq_remaining == 5  # unveraendert
    assert captured == []


def test_reset_counter_after_measure_noop_when_already_target(app):
    """T12: remaining bereits TARGET → no-op (kein Emit)."""
    omni, *_ = _make_omni(mode="FT8")
    captured: list = []
    omni.cq_count_changed.connect(lambda r, e: captured.append((r, e)))
    omni.start()
    omni._cq_tx_even = True
    # remaining ist nach start() schon TARGET
    omni.reset_counter_after_measure()
    assert captured == []


# ── T13: pause aendert remaining nicht ─────────────────────────────


def test_pause_does_not_reset_remaining(app):
    """T13: start + dekrementieren via TX + pause() → remaining unveraendert."""
    omni, *_ = _make_omni(mode="FT8")
    omni.start()
    target = omni.cq_target
    with patch("core.omni_cq.time.time", return_value=30.0):
        omni.on_cycle_start(cycle_num=2, is_even=True)
    assert omni.cq_remaining == target - 1
    omni.pause()
    assert omni.cq_remaining == target - 1   # bleibt


# ── T14: stop reset zu 0 + target zu DEFAULT ───────────────────────


def test_stop_resets_remaining_to_zero_and_target_to_default(app):
    """T14: stop() → remaining == 0, target == _OMNI_DEFAULT_TARGET."""
    omni, *_ = _make_omni(mode="FT8")
    omni.start()
    omni._cq_tx_even = True
    omni._cq_remaining = 7
    omni.stop("test_reason")
    assert omni.cq_remaining == 0
    assert omni.cq_target == _OMNI_DEFAULT_TARGET


# ── T15: on_search_trigger entfaellt komplett ──────────────────────


def test_on_search_trigger_method_removed(app):
    """T15: on_search_trigger-Methode existiert nicht mehr (P23 raus)."""
    assert not hasattr(OmniCQ, 'on_search_trigger')
    # Auch keine Konstante mehr:
    import core.omni_cq as omni_mod
    assert not hasattr(omni_mod, '_OMNI_FLIP_AFTER_SEARCHES')


# ── T16: qso_panel.add_tx mit omni_remaining rendert Suffix ────────


def test_qso_panel_add_tx_with_omni_remaining_renders_suffix(app):
    """T16: add_tx(message, omni_remaining=7) → Output enthaelt `↻7`."""
    from ui.qso_panel import QSOPanel
    panel = QSOPanel()
    panel.add_tx("CQ DA1MHH JN58",
                 tx_even=True, slot_start_ts=30.0,
                 omni_remaining=7)
    log_text = panel.log_view.toPlainText()
    assert "↻7" in log_text
    # Nachricht selbst auch noch da
    assert "CQ DA1MHH JN58" in log_text


def test_qso_panel_add_tx_without_omni_remaining_no_suffix(app):
    """T16b: add_tx ohne omni_remaining → KEIN ↻ im Output."""
    from ui.qso_panel import QSOPanel
    panel = QSOPanel()
    panel.add_tx("73 DL3AQJ DA1MHH",
                 tx_even=False, slot_start_ts=15.0)
    log_text = panel.log_view.toPlainText()
    assert "↻" not in log_text
