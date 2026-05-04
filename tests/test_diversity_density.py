#!/usr/bin/env python3
"""Tests fuer v0.93 Score-basierte Messung — FT2 mit duenner Decoder-Dichte.

Mod 4 (KILLER): Statt diskreter ``station_count`` (0/1/2 bei FT2) speichert
``record_measurement`` jetzt den kontinuierlichen ``score = sum(snr+30)``.
Damit liefert der Median auch bei 1-2 Stationen pro Slot Antennen-
Differenzierung statt 50:50-Default.

Mod 5 (Bonus): ``MIN_MEASURE_STATIONS`` entfernt — ``can_measure()`` immer
True, Auswertung in ``_evaluate`` faellt bei ``peak <= MIN_PEAK_SCORE``
auf 50:50 zurueck.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.diversity import DiversityController


# ── Score-basierte Differenzierung bei niedriger Dichte ─────────────────────


def test_score_resolves_ft2_density_a1_dominant():
    """FT2-Szenario: A1 hat 2 Stationen á SNR -10, A2 nur 1 á SNR -15.

    Diskrete Logik (alt): A1=[2,2,2], A2=[1,1,1] → Median 2 vs 1 → diff=50%,
    aber peak=2 < alte Schwelle 1.0? — eigentlich okay. Bei A1=[1,1,1] vs
    A2=[1,1,1] dagegen: Median 1 vs 1 → 50:50 (keine Aufloesung).

    Score (neu): A1 score=2*(snr+30)=2*20=40, A2 score=1*15=15.
    → Median 40 vs 15 → rel_diff=25/40=62 % > 8 % → 70:30 mit dominant=A1.
    """
    dc = DiversityController()
    dc._phase = "measure"
    for _ in range(3):
        dc.record_measurement("A1", score=40.0)  # 2 Stationen á snr=-10
        dc.record_measurement("A2", score=15.0)  # 1 Station á snr=-15
    assert dc.phase == "operate"
    assert dc.ratio == "70:30"
    assert dc.dominant == "A1"


def test_score_resolves_ft2_density_a2_dominant():
    """FT2-Szenario inverse: A2 dominant trotz duenner Dichte."""
    dc = DiversityController()
    dc._phase = "measure"
    for _ in range(3):
        dc.record_measurement("A1", score=15.0)
        dc.record_measurement("A2", score=40.0)
    assert dc.phase == "operate"
    assert dc.ratio == "30:70"
    assert dc.dominant == "A2"


def test_score_below_min_peak_falls_back_to_5050():
    """Sehr schwacher Empfang (peak <= MIN_PEAK_SCORE=5) → 50:50 Default.

    Beispiel: A1 hat sporadisch 0.3 Stationen á snr=-25 → score≈1.5.
    Median bleibt unter 5 → kein Antennen-Vorteil ableitbar → 50:50.
    """
    dc = DiversityController()
    dc._phase = "measure"
    for _ in range(3):
        dc.record_measurement("A1", score=2.0)
        dc.record_measurement("A2", score=4.0)
    assert dc.phase == "operate"
    assert dc.ratio == "50:50"
    assert dc.dominant is None


def test_score_at_min_peak_threshold_still_5050():
    """Genau auf MIN_PEAK_SCORE=5 → noch 50:50 (Schwelle inklusive)."""
    dc = DiversityController()
    dc._phase = "measure"
    for _ in range(3):
        dc.record_measurement("A1", score=5.0)
        dc.record_measurement("A2", score=5.0)
    assert dc.phase == "operate"
    assert dc.ratio == "50:50"


def test_score_just_above_min_peak_resolves_ratio():
    """Knapp ueber MIN_PEAK_SCORE → reguläre rel-Differenz-Auswertung."""
    dc = DiversityController()
    dc._phase = "measure"
    # peak=10, A1=10, A2=5 → rel_diff=5/10=50 % > 8 % → 70:30
    for _ in range(3):
        dc.record_measurement("A1", score=10.0)
        dc.record_measurement("A2", score=5.0)
    assert dc.phase == "operate"
    assert dc.ratio == "70:30"
    assert dc.dominant == "A1"


# ── Mod 5: MIN_MEASURE_STATIONS entfernt ────────────────────────────────────


def test_can_measure_no_longer_blocks_low_station_counts():
    """v0.93: can_measure() ist immer True — alte 5-Stations-Pre-Block weg."""
    dc = DiversityController()
    assert dc.can_measure() is True
    assert dc.can_measure(0) is True
    assert dc.can_measure(1) is True
    assert dc.can_measure(2) is True


def test_can_measure_attribute_is_callable_without_args():
    """Defensiv: alte Aufrufstellen ohne Argument sollen weiter laufen."""
    dc = DiversityController()
    # Sollte nicht raisen
    assert dc.can_measure() is True


# ── Adaptiv-Stop mit Score-basierter Schwelle ───────────────────────────────


def test_phase3_early_stop_with_score_above_threshold():
    """v0.93: Adaptiv-Stop nutzt MIN_PEAK_SCORE (5.0) statt 1.0.

    Score 100 vs 25 → median 100/25 → peak=100 > 5 → rel_diff=75 % >= 15 %
    → Stop nach 4 Zyklen.
    """
    dc = DiversityController()
    dc._phase = "measure"
    for _ in range(2):
        dc.record_measurement("A1", score=100.0)
        dc.record_measurement("A2", score=25.0)
    assert dc.phase == "operate"
    assert dc.ratio == "70:30"
    assert dc._was_early_stopped is True
    assert dc._measure_step == 4


def test_phase3_no_early_stop_when_peak_below_min():
    """Adaptiv-Stop greift NICHT wenn peak<=MIN_PEAK_SCORE — Schutz vor
    Falsch-Stop bei sehr schwachem Empfang.
    """
    dc = DiversityController()
    dc._phase = "measure"
    # A1 peak=4 (< 5), A2 peak=1 → kein Stop
    for _ in range(2):
        dc.record_measurement("A1", score=4.0)
        dc.record_measurement("A2", score=1.0)
    assert dc.phase == "measure"
    assert dc._was_early_stopped is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
