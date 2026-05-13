"""Tests fuer P40 — P37-Komplettierung: current_ant in allen Aufrufern.

R1-Empfehlung (SOLLTE): Integration-Test fuer
`_on_dynamic_ratio_changed`-Slot. Slot wird bei jedem Ratio-Wechsel
gerufen — wenn er das Label OHNE current_ant ueberschreibt, geht der
RX-Antennen-Suffix verloren (Mike-Field-Test 12.05. abends).

Strategie: Slot als unbound method auf einer Stub-Instanz aufrufen.
Verifiziert dass `update_diversity_ratio` mit `current_ant`-Parameter
aufgerufen wird, ohne volle MainWindow-Init.
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
from ui.main_window import MainWindow  # noqa: E402


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def _make_stub(current_ant: str | None):
    """Erzeugt minimalen Stub mit allen Attributen die der Slot liest."""
    stub = MagicMock()
    stub._diversity_current_ant = current_ant
    stub._diversity_ctrl = MagicMock(
        phase="operate",
        seconds_until_remeasure=1800,
        scoring_mode="normal",
    )
    stub.control_panel = MagicMock()
    return stub


def test_slot_passes_current_ant_a1(app):
    """Slot reicht current_ant=A1 durch zum Panel."""
    stub = _make_stub(current_ant="A1")
    MainWindow._on_dynamic_ratio_changed(stub, "30:70")
    stub.control_panel.update_diversity_ratio.assert_called_once()
    kwargs = stub.control_panel.update_diversity_ratio.call_args.kwargs
    assert kwargs.get("current_ant") == "A1", \
        f"Slot muss current_ant=A1 durchreichen, kwargs={kwargs}"


def test_slot_passes_current_ant_a2(app):
    """Slot reicht current_ant=A2 durch zum Panel."""
    stub = _make_stub(current_ant="A2")
    MainWindow._on_dynamic_ratio_changed(stub, "70:30")
    kwargs = stub.control_panel.update_diversity_ratio.call_args.kwargs
    assert kwargs.get("current_ant") == "A2"


def test_slot_passes_none_when_unset(app):
    """Wenn _diversity_current_ant nicht gesetzt → current_ant=None
    (getattr-Default), kein Crash, kein Suffix."""
    stub = MagicMock(spec=[])  # leerer Mock, keine Attribute
    stub._diversity_ctrl = MagicMock(
        phase="operate",
        seconds_until_remeasure=1800,
        scoring_mode="normal",
    )
    stub.control_panel = MagicMock()
    MainWindow._on_dynamic_ratio_changed(stub, "50:50")
    kwargs = stub.control_panel.update_diversity_ratio.call_args.kwargs
    assert kwargs.get("current_ant") is None


def test_slot_passes_scoring_mode(app):
    """P34-Stufe2: Slot reicht scoring_mode durch (is_dynamic-Argument
    gibt es nicht mehr — Anzeige ist immer DYNAMISCH (live))."""
    stub = _make_stub(current_ant="A1")
    MainWindow._on_dynamic_ratio_changed(stub, "30:70")
    kwargs = stub.control_panel.update_diversity_ratio.call_args.kwargs
    assert kwargs.get("scoring_mode") == "normal"
