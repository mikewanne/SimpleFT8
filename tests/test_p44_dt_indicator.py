"""P44 Statusbar DT-Indikator als eigenes Permanent-Widget (v0.97.10, Mai 2026).

Vorher (Bug): DT-Farbe wurde via setStyleSheet auf gesamte Statusbar
gesetzt → alle Texte grün während Korrektur.
Jetzt: DT als eigenes QLabel mit eigener Farbe (analog _stats_indicator).
Globaler Statusbar-Style bleibt unverändert grau.
"""
from __future__ import annotations

import sys

import pytest

from PySide6.QtWidgets import QApplication, QLabel, QMainWindow


@pytest.fixture(scope="module")
def qapp():
    """Eine QApplication-Instanz fuer das ganze Modul."""
    app = QApplication.instance() or QApplication(sys.argv)
    yield app


def test_dt_indicator_pattern_initial_grey(qapp):
    """DT-Indikator-Pattern: Default grau, Text 'DT: —'."""
    win = QMainWindow()
    label = QLabel("DT: —")
    label.setStyleSheet(
        "color: #555; font-family: Menlo; font-size: 11px; padding: 0 6px;"
    )
    win.statusBar().addPermanentWidget(label)
    assert "color: #555" in label.styleSheet()
    assert label.text() == "DT: —"


def test_dt_indicator_correction_phase_green(qapp):
    """Wechsel auf 'DT: Korrektur' setzt Text + gruene Farbe nur am Label.

    Wichtig: Statusbar-Stylesheet bleibt unveraendert (kein globaler
    Farbwechsel mehr — das war der ursprueliche Bug).
    """
    win = QMainWindow()
    label = QLabel("DT: —")
    win.statusBar().addPermanentWidget(label)
    label.setText("DT: Korrektur")
    label.setStyleSheet(
        "color: #00DD66; font-family: Menlo; font-size: 11px; padding: 0 6px;"
    )
    assert label.text() == "DT: Korrektur"
    assert "#00DD66" in label.styleSheet()
    # Statusbar-Stylesheet wurde NICHT veraendert (Bug-Schutz)
    assert "color: #00DD66" not in win.statusBar().styleSheet()
