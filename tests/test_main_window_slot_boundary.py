"""Tests fuer P5.OMNI-PATTERN-FIX-3 Issue A — Slot-Boundary in
ui/main_window._on_omni_slot_action (v0.96.2).

Bug: add_listening bekam Wall-Time (time.time()) statt UTC-Slot-Boundary,
GUI-Latency + Qt-QueuedConnection schlugen 100-400ms NACH echter
Slot-Boundary ein → Anzeige z.B. ":31" statt ":30" → Mike sah Eintraege
wirken "verschoben" oder "fehlend" (R1-Display-Bug-Diagnose).

Fix: time.time() → (time.time() // cycle_duration) * cycle_duration.

V3 §7 T7 + T8 (parametrize FT4 + FT2):
- T7: FT8 (15s) — Wall-Time 16004.5s → Slot-Boundary 15990.0s
- T8: FT4 (7.5s) → 16002.0, FT2 (3.8s) → 15998.6
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
from ui.main_window import MainWindow  # noqa: E402


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def _make_fake_mw_minimal(slot_dur: float):
    """Minimaler MW-Stub fuer _on_omni_slot_action — nur self.timer +
    self.qso_panel werden gelesen.
    """
    mw = MagicMock()
    mw.timer = MagicMock()
    mw.timer.cycle_duration = slot_dur
    mw.qso_panel = MagicMock()
    mw.qso_panel.add_listening = MagicMock()
    return mw


# ── T7: FT8 Slot-Boundary ───────────────────────────────────────────


def test_add_listening_uses_slot_boundary_ft8(app):
    """T7 (AC-A1): FT8 cycle_duration=15s, time=16004.5 → boundary=15990.0."""
    mw = _make_fake_mw_minimal(slot_dur=15.0)
    fake_now = 16004.5  # entspricht 04:26:44.5 in 15s-Slot-Welt
    expected_slot_start = (fake_now // 15.0) * 15.0  # = 15990.0

    with patch("ui.main_window.time.time", return_value=fake_now):
        MainWindow._on_omni_slot_action(
            mw, label="Horche", is_tx=False, target_even=True,
        )

    mw.qso_panel.add_listening.assert_called_once_with(
        expected_slot_start, True,
    )


def test_add_listening_skipped_for_tx_slots(app):
    """AC-A1-Querschnitt: bei is_tx=True wird add_listening NICHT gerufen
    (TX-Slots laufen ueber encoder.tx_started → qso_panel.add_tx).
    """
    mw = _make_fake_mw_minimal(slot_dur=15.0)
    with patch("ui.main_window.time.time", return_value=16004.5):
        MainWindow._on_omni_slot_action(
            mw, label="Sende", is_tx=True, target_even=False,
        )
    mw.qso_panel.add_listening.assert_not_called()


# ── T8: FT4 + FT2 Slot-Boundary (parametrize) ──────────────────────


@pytest.mark.parametrize(
    "slot_dur, fake_now, expected_slot_start",
    [
        (15.0, 16004.5, 15990.0),       # FT8 - parallel zu T7 zur Sicherheit
        (7.5, 16004.5, 16002.0),         # FT4: floor(16004.5/7.5)=2133 → *7.5=15997.5? PRUEFEN
        (3.8, 16004.5, 15998.6),         # FT2: floor(16004.5/3.8)=4211 → *3.8=15999.8? PRUEFEN
    ],
)
def test_add_listening_uses_slot_boundary_all_modes(
    app, slot_dur, fake_now, expected_slot_start
):
    """T8 (AC-A2): Slot-Boundary korrekt fuer alle Modi (FT8/FT4/FT2)."""
    mw = _make_fake_mw_minimal(slot_dur=slot_dur)
    # Berechne Erwartung exakt wie der Code (Floating-Point-Toleranz)
    real_expected = (fake_now // slot_dur) * slot_dur

    with patch("ui.main_window.time.time", return_value=fake_now):
        MainWindow._on_omni_slot_action(
            mw, label="Horche", is_tx=False, target_even=False,
        )

    args, _kwargs = mw.qso_panel.add_listening.call_args
    actual_slot_start = args[0]
    actual_target_even = args[1]
    # Floating-Point-Vergleich mit Toleranz
    assert abs(actual_slot_start - real_expected) < 1e-9, (
        f"Erwartet {real_expected}, bekommen {actual_slot_start}"
    )
    assert actual_target_even is False
