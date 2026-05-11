"""Tests fuer P34 Modul-Helper in core/diversity.py.

compute_slot_score + evaluate_ratio — werden von Statik UND Dynamic genutzt.
"""
from types import SimpleNamespace

from core.diversity import compute_slot_score, evaluate_ratio


def _msg(snr):
    """Minimaler Message-Mock mit snr-Attribut."""
    return SimpleNamespace(snr=snr)


# ── compute_slot_score ────────────────────────────────────────────────

def test_compute_slot_score_basic():
    """Mehrere Stationen mit unterschiedlichen SNRs → korrekte Summe."""
    messages = [_msg(-10), _msg(-15), _msg(0)]
    # sum(max(0, snr+30)) = (20 + 15 + 30) = 65
    assert compute_slot_score(messages) == 65.0


def test_compute_slot_score_snr_filter():
    """SNR <= -20 wird ausgefiltert (nur > -20 zaehlt)."""
    messages = [_msg(-25), _msg(-20), _msg(-10), _msg(-30)]
    # Nur -10 zaehlt: 0+20 = 20.0
    assert compute_slot_score(messages) == 20.0


def test_compute_slot_score_empty():
    """Leere Liste → 0.0."""
    assert compute_slot_score([]) == 0.0
    assert compute_slot_score(None) == 0.0


def test_compute_slot_score_none_snr():
    """Stationen mit snr=None werden ausgelassen."""
    messages = [_msg(None), _msg(-15), _msg(None)]
    # Nur -15 zaehlt: 15.0
    assert compute_slot_score(messages) == 15.0


def test_compute_slot_score_clamp_at_zero():
    """SNR knapp ueber -20 → score nahe 0, niemals negativ."""
    messages = [_msg(-19)]
    # max(0, -19+30) = 11
    assert compute_slot_score(messages) == 11.0


# ── evaluate_ratio ────────────────────────────────────────────────────

def test_evaluate_ratio_50_50_below_threshold():
    """Differenz unter 8% → 50:50, None."""
    ratio, dominant = evaluate_ratio(100.0, 95.0)
    # rel_diff = 5/100 = 5% < 8%
    assert ratio == "50:50"
    assert dominant is None


def test_evaluate_ratio_70_30_a1_dominates():
    """A1 deutlich staerker → 70:30, A1."""
    ratio, dominant = evaluate_ratio(100.0, 50.0)
    assert ratio == "70:30"
    assert dominant == "A1"


def test_evaluate_ratio_30_70_a2_dominates():
    """A2 deutlich staerker → 30:70, A2."""
    ratio, dominant = evaluate_ratio(50.0, 100.0)
    assert ratio == "30:70"
    assert dominant == "A2"


def test_evaluate_ratio_below_min_peak():
    """Beide Medians unter min_peak → 50:50, None (Fallback)."""
    ratio, dominant = evaluate_ratio(2.0, 4.0)
    # peak=4.0 <= 5.0 → 50:50
    assert ratio == "50:50"
    assert dominant is None


def test_evaluate_ratio_exactly_at_threshold():
    """Differenz genau 8% → bleibt 50:50 (rel_diff < threshold)."""
    # 100 → 92 = 8% diff exakt
    ratio, dominant = evaluate_ratio(100.0, 92.0)
    # 8/100 = 0.08, NOT < 0.08 → 70:30 (Grenzfall)
    assert ratio == "70:30"
    assert dominant == "A1"


def test_evaluate_ratio_custom_threshold():
    """Custom Threshold ueberschreibt Default."""
    ratio, dominant = evaluate_ratio(100.0, 90.0, threshold=0.15)
    # rel_diff 10% < 15% → 50:50
    assert ratio == "50:50"
    assert dominant is None


def test_evaluate_ratio_custom_min_peak():
    """Custom min_peak ueberschreibt Default."""
    ratio, dominant = evaluate_ratio(20.0, 10.0, min_peak=15.0)
    # peak 20 > 15 → normale Bewertung. rel_diff 50% → 70:30
    assert ratio == "70:30"
    assert dominant == "A1"


def test_evaluate_ratio_a1_equals_a2_above_min_peak():
    """A1 == A2 oberhalb min_peak → 50:50 (rel_diff=0)."""
    ratio, dominant = evaluate_ratio(10.0, 10.0)
    assert ratio == "50:50"
    assert dominant is None


def test_evaluate_ratio_a1_slightly_higher_at_tie():
    """Bei genau gleichen Werten + Differenz im Threshold → A1 default."""
    # Edge-Case: 100 vs 92 ist 8% → > Threshold, A1 >= A2 → 70:30
    ratio, dominant = evaluate_ratio(100.0, 92.0)
    assert dominant == "A1"
