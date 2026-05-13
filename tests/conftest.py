"""Globale Test-Schutzschicht — kein Test darf je Mike's echte
``~/.simpleft8/``-Dateien beschreiben.

Hintergrund 13.05.2026:

Bundle-A-Test ``test_dt_dedup_logs_on_change`` hat ueber den
ungemockten ``set_mode``-Pfad ``core.ntp_time._save_current()`` ge-
triggert, der unmittelbar auf ``~/.simpleft8/dt_corrections.json``
schreibt. Mike's echte DT-Korrekturen wurden mit Testwerten ueber-
schrieben.

Bei der Diagnose stellte sich raus dass schon ``tests/test_modules.py``
(Z.569, Z.1262, Z.1276, Z.1297, ...) seit jeher dasselbe Muster nutzt
— direkter Zugriff auf ``ntp_time._saved`` + ``set_mode()`` ohne
Disk-Schutz. Die Datei wurde also bei jedem ``pytest``-Run heimlich
veraendert.

Diese Fixture schiebt fuer JEDEN Test eine tmp-Datei vor ``_DT_FILE``
— Tests laufen unveraendert, Mike's Datei bleibt unangetastet.
"""
from __future__ import annotations

import os
import sys

import pytest

# Projekt-Root in den Pfad — damit `import core.ntp_time` funktioniert,
# bevor irgendein Test es selbst importiert.
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import core.ntp_time as _ntp_time  # noqa: E402


@pytest.fixture(autouse=True)
def _protect_dt_corrections_file(monkeypatch, tmp_path):
    """Lenkt ``core.ntp_time._DT_FILE`` auf tmp — jeder Test bekommt
    seine eigene Datei. Mike's echte ``~/.simpleft8/dt_corrections.json``
    bleibt unberuehrt.
    """
    monkeypatch.setattr(
        _ntp_time, "_DT_FILE", tmp_path / "dt_corrections.json"
    )
    yield
