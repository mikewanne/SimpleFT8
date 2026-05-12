"""Tests fuer P37 — RX-Antennen-Anzeige im Dynamic-Label.

Mike-Wunsch 12.05.2026: Phase-Label „● DYNAMISCH (live)" um aktive
RX-Antenne erweitern: „● DYNAMISCH (live) — RX Ant1" / „— RX Ant2".

R1-Coverage (5 Cases):
- T1: is_dynamic=True, current_ant="A1" → „RX Ant1" im Label
- T2: is_dynamic=True, current_ant="A2" → „RX Ant2" im Label
- T3: is_dynamic=True, current_ant=None  → kein Anhang (Backwards-Compat)
- T4: is_dynamic=True, current_ant="X"   → kein Anhang (Robustheit)
- T5: is_dynamic=False, current_ant="A1" → statisches Label, kein Anhang
"""
from __future__ import annotations

import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import sys
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from ui.control_panel import ControlPanel  # noqa: E402


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def panel(app):
    cp = ControlPanel()
    yield cp
    cp.deleteLater()


def _label_text(panel: ControlPanel) -> str:
    return panel._phase_label.text()


def test_dynamic_with_ant1_shows_rx_ant1(panel):
    """T1: is_dynamic=True + current_ant='A1' → Label enthaelt 'RX Ant1'."""
    panel.update_diversity_ratio(
        "30:70", "operate",
        operate_seconds_remaining=1800,
        is_dynamic=True,
        current_ant="A1",
    )
    text = _label_text(panel)
    assert "DYNAMISCH (live)" in text
    assert "RX Ant1" in text
    assert "RX Ant2" not in text


def test_dynamic_with_ant2_shows_rx_ant2(panel):
    """T2: is_dynamic=True + current_ant='A2' → Label enthaelt 'RX Ant2'."""
    panel.update_diversity_ratio(
        "30:70", "operate",
        operate_seconds_remaining=1800,
        is_dynamic=True,
        current_ant="A2",
    )
    text = _label_text(panel)
    assert "DYNAMISCH (live)" in text
    assert "RX Ant2" in text
    assert "RX Ant1" not in text


def test_dynamic_with_no_ant_has_no_suffix(panel):
    """T3: is_dynamic=True + current_ant=None → kein RX-Anhang (Backwards-Compat)."""
    panel.update_diversity_ratio(
        "50:50", "operate",
        operate_seconds_remaining=1800,
        is_dynamic=True,
        current_ant=None,
    )
    text = _label_text(panel)
    assert text == "● DYNAMISCH (live)"
    assert "RX Ant" not in text


def test_dynamic_with_invalid_ant_has_no_suffix(panel):
    """T4: ungueltiges current_ant (z.B. 'X') → kein Anhang (Robustheit)."""
    panel.update_diversity_ratio(
        "70:30", "operate",
        operate_seconds_remaining=1800,
        is_dynamic=True,
        current_ant="X",
    )
    text = _label_text(panel)
    assert text == "● DYNAMISCH (live)"
    assert "RX Ant" not in text


def test_static_mode_ignores_current_ant(panel):
    """T5: is_dynamic=False → statisches Label, current_ant wird ignoriert."""
    panel.update_diversity_ratio(
        "70:30", "operate",
        operate_seconds_remaining=600,
        is_dynamic=False,
        current_ant="A1",
    )
    text = _label_text(panel)
    assert "DYNAMISCH" not in text
    assert "RX Ant" not in text
    assert "Neuberechnung" in text  # Statik-Text bleibt
