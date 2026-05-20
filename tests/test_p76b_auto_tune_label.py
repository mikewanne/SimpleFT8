"""P76-B (20.05.2026, v0.97.63) — Auto-TUNE-Dauer-Anzeige UX.

Mike-Field-Test 18.05.2026 nach P75: "wesentlich länger als 5 s
gedauert" bei tune_duration_s=5 + 10m-Band. Wurzel: Soll-Anzeige
"N / 5 s" lief weiter während Phase B (Closed-Loop-Convergenz)
und Post-SWR-Check noch liefen (real bis 13.5 s worst-case).

Fix: 2-Phasen-Label im `_on_tick`:
- Phase 1 (_elapsed_s <= duration_s): "X / N s" + #AAA grau
- Phase 2 (_elapsed_s > duration_s): "Leistung wird auf 10 W
  eingeregelt · X s" + #DDA heller Akzent (R1-F4)
- Defensive `max(1, duration_s)` gegen duration_s<=0 (R1-F1)

Test-Coverage:
- T1 Phase 1 Soll-Anzeige
- T2 Phase 2 ohne Soll
- T3 Phase-Wechsel-Grenze
- T4 duration_s=0 defensiv
- T5 _on_auto_tune_done überschreibt Phase 2 (R1-F5)
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from PySide6.QtWidgets import QApplication

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def _make_dialog_mock(*, duration_s=5, mode="FT8", elapsed_s=0,
                      swr=1.3, fwdpwr=9.5):
    """Minimaler Mock analog Bundle-G Pattern für `_on_tick`."""
    from ui.auto_tune_dialog import AutoTuneDialog
    obj = MagicMock(spec=AutoTuneDialog)
    obj._duration_s = duration_s
    obj._mode = mode
    obj._elapsed_s = elapsed_s
    obj._parent = MagicMock()
    obj._parent.radio = MagicMock()
    obj._parent.radio.last_swr = swr
    obj._parent._fwdpwr_samples = [fwdpwr]
    obj._status_label = MagicMock()
    obj._on_tick = AutoTuneDialog._on_tick.__get__(obj)
    return obj


# ── T1: Phase 1 zeigt Soll-Anzeige ─────────────────────────────────


def test_phase1_label_shows_soll_anzeige_within_duration(app):
    """T1: _elapsed_s=3, duration_s=5 → Tick → "4 / 5 s"."""
    obj = _make_dialog_mock(duration_s=5, elapsed_s=3)
    obj._on_tick()
    assert obj._elapsed_s == 4
    text = obj._status_label.setText.call_args[0][0]
    assert "4 / 5 s" in text, f"Phase-1-Soll-Anzeige fehlt: {text!r}"
    assert "FT8" in text
    assert "SWR 1.3" in text
    assert "FWDPWR 9.5W" in text
    # Phase 1 Style: #AAA
    style = obj._status_label.setStyleSheet.call_args[0][0]
    assert "#AAA" in style, f"Phase-1-Style falsch: {style!r}"


# ── T2: Phase 2 zeigt keine Soll-Anzeige mehr ─────────────────────


def test_phase2_label_drops_soll_anzeige_after_duration(app):
    """T2: _elapsed_s=6, duration_s=5 → Tick → "Leistung wird auf 10 W"."""
    obj = _make_dialog_mock(duration_s=5, elapsed_s=6)
    obj._on_tick()
    assert obj._elapsed_s == 7
    text = obj._status_label.setText.call_args[0][0]
    assert "Leistung wird auf 10 W eingeregelt" in text, (
        f"Phase-2-Wording fehlt: {text!r}")
    assert "7 s" in text
    assert "/ 5" not in text, f"Phase 2 zeigt fälschlich Soll: {text!r}"
    # SWR + FWDPWR bleiben sichtbar
    assert "SWR 1.3" in text
    assert "FWDPWR 9.5W" in text
    # Phase 2 Style: #DDA heller Akzent
    style = obj._status_label.setStyleSheet.call_args[0][0]
    assert "#DDA" in style, f"Phase-2-Style falsch: {style!r}"


# ── T3: Phase-Wechsel-Grenze ──────────────────────────────────────


def test_phase_transition_at_duration_boundary(app):
    """T3: Grenze elapsed_s = duration_s ist noch Phase 1,
    elapsed_s = duration_s+1 ist Phase 2."""
    # _elapsed_s=4 → Tick → _elapsed_s=5 = duration_s → Phase 1
    obj1 = _make_dialog_mock(duration_s=5, elapsed_s=4)
    obj1._on_tick()
    text1 = obj1._status_label.setText.call_args[0][0]
    assert "5 / 5 s" in text1, f"Grenze (elapsed=duration) sollte Phase 1 sein: {text1!r}"

    # _elapsed_s=5 → Tick → _elapsed_s=6 > duration_s → Phase 2
    obj2 = _make_dialog_mock(duration_s=5, elapsed_s=5)
    obj2._on_tick()
    text2 = obj2._status_label.setText.call_args[0][0]
    assert "Leistung wird auf 10 W eingeregelt" in text2, (
        f"Übergang elapsed=duration+1 sollte Phase 2 sein: {text2!r}")


# ── T4: duration_s<=0 defensive ───────────────────────────────────


def test_duration_zero_defensive_clamp(app):
    """T4: duration_s=0 (Edge-Case) crashed nicht, kein '/ 0 s'."""
    obj = _make_dialog_mock(duration_s=0, elapsed_s=0)
    obj._on_tick()
    text = obj._status_label.setText.call_args[0][0]
    assert "/ 0 s" not in text, f"duration_s=0 sollte clamped sein: {text!r}"
    # Output ist sinnvoll lesbar (entweder Phase 1 mit "/ 1 s" oder Phase 2)
    assert ("/ 1 s" in text) or ("eingeregelt" in text), (
        f"duration_s=0 output sinnlos: {text!r}")


# ── T5: auto_tune_done überschreibt Phase 2 (R1-F5) ───────────────


def test_auto_tune_done_overrides_phase2_label(app):
    """T5: _on_auto_tune_done in Phase 2 zeigt Erfolgs-Label."""
    from ui.auto_tune_dialog import AutoTuneDialog
    obj = MagicMock(spec=AutoTuneDialog)
    obj._duration_s = 5
    obj._mode = "FT8"
    obj._elapsed_s = 8  # Phase 2 aktiv
    obj._parent = MagicMock()
    obj._parent.radio.last_swr = 1.3
    obj._parent._fwdpwr_samples = [9.5]
    obj._status_label = MagicMock()
    obj._tick_timer = MagicMock()
    obj._backup_timer = MagicMock()
    obj._on_auto_tune_done = (
        AutoTuneDialog._on_auto_tune_done.__get__(obj))
    # Erfolg: success=True
    obj._on_auto_tune_done(True, 1.2, 9.8)
    # Erfolgs-Label überschreibt Phase-2-Label
    text = obj._status_label.setText.call_args[0][0]
    assert "✓ TUNE OK" in text, (
        f"Erfolgs-Label fehlt nach auto_tune_done: {text!r}")
    assert "SWR 1.2" in text
    assert "FWDPWR 9.8 W" in text
    # Beide Timer gestoppt
    obj._tick_timer.stop.assert_called_once()
    obj._backup_timer.stop.assert_called_once()
