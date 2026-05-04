#!/usr/bin/env python3
"""Tests fuer v0.93 should_remeasure() — zeit-basiert + CQ-Lock.

API-Erweiterung (v0.92 → v0.93):
  - alt: should_remeasure(qso_active)
  - neu: should_remeasure(qso_active, cq_active)
  - Frist: time.time() - _last_measured_at >= REMEASURE_INTERVAL_SECONDS
  - Defensiv (R1-Hinweis): _last_measured_at None → True (App-Start)

Mod 3 (R1): CQ-Lock zusaetzlich zu QSO-Lock — waehrend CQ-Ruf darf nicht
gemessen werden (TX-Slots gebraucht).
"""

import os
import sys
import time

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.diversity import DiversityController


# ── Phase-Pre-Condition ─────────────────────────────────────────────────────


def test_should_remeasure_returns_false_in_measure_phase():
    """Phase=measure → kein Remeasure (laeuft schon)."""
    dc = DiversityController()
    dc._phase = "measure"
    assert dc.should_remeasure(qso_active=False, cq_active=False) is False


def test_should_remeasure_in_operate_phase_required():
    """Phase=operate ist Pre-Condition fuer Remeasure-Trigger."""
    dc = DiversityController()
    dc._phase = "operate"
    dc._last_measured_at = None  # App-Start — defensiv True
    assert dc.should_remeasure(qso_active=False, cq_active=False) is True


# ── QSO/CQ-Locks ────────────────────────────────────────────────────────────


def test_should_remeasure_blocked_by_qso_active():
    dc = DiversityController()
    dc._phase = "operate"
    dc._last_measured_at = time.time() - 7200  # 2h alt → Frist klar abgelaufen
    assert dc.should_remeasure(qso_active=True, cq_active=False) is False


def test_should_remeasure_blocked_by_cq_active():
    """v0.93 Mod 3: CQ-Ruf blockt ebenfalls Remeasure."""
    dc = DiversityController()
    dc._phase = "operate"
    dc._last_measured_at = time.time() - 7200
    assert dc.should_remeasure(qso_active=False, cq_active=True) is False


def test_should_remeasure_blocked_by_both():
    dc = DiversityController()
    dc._phase = "operate"
    dc._last_measured_at = time.time() - 7200
    assert dc.should_remeasure(qso_active=True, cq_active=True) is False


def test_should_remeasure_cq_active_default_false():
    """Backwards-Kompat: cq_active=False als Default akzeptiert."""
    dc = DiversityController()
    dc._phase = "operate"
    dc._last_measured_at = time.time() - 7200
    # Aufruf ohne cq_active-Argument
    assert dc.should_remeasure(qso_active=False) is True


# ── Zeit-Frist (1h) ─────────────────────────────────────────────────────────


def test_should_remeasure_after_1h_triggers():
    """Cache > 1h → Remeasure."""
    dc = DiversityController()
    dc._phase = "operate"
    dc._last_measured_at = time.time() - 3601  # 1h + 1s alt
    assert dc.should_remeasure(qso_active=False, cq_active=False) is True


def test_should_remeasure_under_1h_no_trigger():
    """Cache < 1h → kein Remeasure."""
    dc = DiversityController()
    dc._phase = "operate"
    dc._last_measured_at = time.time() - 3000  # 50 Min alt
    assert dc.should_remeasure(qso_active=False, cq_active=False) is False


def test_should_remeasure_exactly_1h_triggers():
    """Genau 1h alt (Schwelle inklusive) → Remeasure."""
    dc = DiversityController()
    dc._phase = "operate"
    dc._last_measured_at = time.time() - 3600  # exakt 1h
    assert dc.should_remeasure(qso_active=False, cq_active=False) is True


# ── Defensiv: None-Schutz (R1-Hinweis V3) ──────────────────────────────────


def test_should_remeasure_with_none_last_measured_returns_true():
    """App-Start oder nach reset(): _last_measured_at=None → True (defensiv)."""
    dc = DiversityController()
    dc._phase = "operate"
    dc._last_measured_at = None
    assert dc.should_remeasure(qso_active=False, cq_active=False) is True


# ── _evaluate setzt _last_measured_at ───────────────────────────────────────


def test_evaluate_sets_last_measured_at():
    """Nach _evaluate() ist _last_measured_at gesetzt (1h-Frist startet)."""
    dc = DiversityController()
    dc._phase = "measure"
    assert dc._last_measured_at is None
    for _ in range(3):
        dc.record_measurement("A1", score=150.0)
        dc.record_measurement("A2", score=150.0)
    assert dc.phase == "operate"
    assert dc._last_measured_at is not None
    # Sollte gerade frisch (< 1s alt) sein
    assert (time.time() - dc._last_measured_at) < 1.0


def test_adaptiv_stop_also_sets_last_measured_at():
    """Adaptiv-Stop ruft _evaluate auf → _last_measured_at gesetzt."""
    dc = DiversityController()
    dc._phase = "measure"
    for _ in range(2):
        dc.record_measurement("A1", score=300.0)
        dc.record_measurement("A2", score=75.0)
    assert dc._was_early_stopped is True
    assert dc._last_measured_at is not None


def test_reset_clears_last_measured_at():
    """reset() loescht _last_measured_at — nach Bandwechsel App-Start-Verhalten."""
    dc = DiversityController()
    dc._last_measured_at = time.time()
    dc.reset()
    assert dc._last_measured_at is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
