"""Bundle F (14.05.2026, v0.97.22 → v0.97.23) — Field-Test Bug-Fixes.

3 Bugs als Bundle:
1. OMNI Phase-Check raus (P34-Stufe2-Partial-Fix-Aufräumen)
2. cycle_bar weg (Bundle D hatte _slot_progress_bar in Statusbar
   ergänzt, aber alten Balken nicht entfernt)
3. Magenta `#FF66CC` → Orange `#FFAA00` (Mike: „nix funker-like")

Tests in dieser Datei dienen primär als Bug-Schutz gegen Regression.
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


# ── T1: Bug-Schutz gegen P34-Stufe2-Regression ─────────────────────


def test_diversity_controller_has_no_phase_attribute():
    """T1: DiversityController hat KEIN `phase`-Attribut mehr.

    P34-Stufe2 (v0.97.19, 13.05.2026) hat die Mess-Phase entfernt.
    `core/omni_cq.py` greift in v0.97.22 noch auf `diversity.phase`
    zu → AttributeError im Qt-Slot, silently → OMNI sendet nie
    (Bundle F Wurzel).

    Falls jemand `phase` wieder einführt: OMNI muss synchron
    angepasst werden (Phase-Check zurück oder anderer Schutz).
    """
    from core.diversity import DiversityController
    from core.timing import FT8Timer
    d = DiversityController(FT8Timer())
    assert not hasattr(d, 'phase'), (
        "DiversityController hat wieder `phase`-Attribut — OMNI in "
        "`core/omni_cq.py` muss synchron angepasst werden (sonst "
        "silent AttributeError im Qt-Slot, siehe Bundle F Lesson)."
    )


# ── T2: OMNI funktioniert mit echtem DiversityController ───────────


def test_omni_on_cycle_start_no_phase_access(app):
    """T2: `OmniCQ.on_cycle_start` ruft `encoder.transmit` ohne
    Zugriff auf `diversity.phase`.

    Nutzt **echten** `DiversityController` (kein MagicMock) damit
    AttributeError tatsächlich triggern würde wenn Phase-Check
    drinbliebe. Lesson aus
    `feedback_test_critical_path_not_mock.md`.
    """
    from core.diversity import DiversityController
    from core.omni_cq import OmniCQ
    from core.timing import FT8Timer

    encoder = MagicMock()
    encoder.transmit = MagicMock(return_value=True)
    timer = FT8Timer()  # echt
    diversity = DiversityController(timer)  # echt
    omni = OmniCQ(
        encoder=encoder, diversity_ctrl=diversity, timer=timer,
        my_call="DA1MHH", my_grid="JN58",
    )
    omni.start()
    # Direkter Aufruf — falls Phase-Check noch existieren würde,
    # würde dieser Aufruf still abbrechen (AttributeError im Slot)
    # und `encoder.transmit` nicht gerufen werden.
    omni.on_cycle_start(cycle_num=100, is_even=True)
    encoder.transmit.assert_called_once()


# ── T3: cycle_bar entfernt ─────────────────────────────────────────


def test_control_panel_has_no_cycle_bar(app):
    """T3: ControlPanel hat KEIN `cycle_bar`-Attribut mehr.

    Bundle D hat `_slot_progress_bar` in Statusbar ergänzt, der
    alte `cycle_bar` (großer QLabel im STATUS-Block) wurde aber
    vergessen zu entfernen → Doppelanzeige. Bundle F räumt auf.
    """
    from ui.control_panel import ControlPanel
    cp = ControlPanel()
    assert not hasattr(cp, 'cycle_bar'), (
        "ControlPanel hat wieder `cycle_bar` — Bundle F-Aufräumung "
        "wurde rückgängig gemacht (doppelte Slot-Anzeige droht)."
    )


def test_control_panel_has_no_update_cycle_bar(app):
    """T4: `update_cycle_bar`-Methode existiert nicht mehr.

    Aufrufer in mw_cycle.py:519 wurde mit entfernt. Falls Methode
    wieder eingeführt: Caller fehlt → tote API.
    """
    from ui.control_panel import ControlPanel
    cp = ControlPanel()
    assert not hasattr(cp, 'update_cycle_bar'), (
        "ControlPanel hat wieder `update_cycle_bar`-Methode — "
        "Bundle F-Aufräumung rückgängig?"
    )


# ── T5: Orange-Farbe im _slot_progress_bar ─────────────────────────


def test_slot_progress_bar_uses_orange_for_odd(app):
    """T5: `_update_slot_progress_bar` setzt Orange `#FFAA00`
    bei Odd-Slot (war Magenta `#FF66CC` in Bundle D).

    Mike-Wunsch nach Field-Test: „nix rosa, funker-like Orange."
    """
    from PySide6.QtWidgets import QProgressBar
    from ui.main_window import MainWindow
    self_mock = MagicMock()
    self_mock._slot_progress_bar = QProgressBar()
    self_mock._slot_progress_bar.setRange(0, 1000)
    self_mock.timer = MagicMock()
    self_mock.timer.cycle_duration = 15.0
    self_mock._slot_progress_is_even = True

    bound_method = MainWindow._update_slot_progress_bar.__get__(self_mock)
    import time as _t
    real_time = _t.time
    try:
        _t.time = lambda: 15.5  # odd-Slot
        bound_method()
        assert self_mock._slot_progress_is_even is False
        style = self_mock._slot_progress_bar.styleSheet()
        assert "#FFAA00" in style, (
            f"Expected orange (#FFAA00) for odd slot, got: {style}"
        )
        assert "#FF66CC" not in style, (
            "Magenta `#FF66CC` darf nicht mehr verwendet werden "
            "(Bundle F: Mike-Wunsch funker-like Orange)."
        )
    finally:
        _t.time = real_time
