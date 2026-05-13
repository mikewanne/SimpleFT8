"""SimpleFT8 Pattern Tests — Operate-Antennen-Pattern.

P34-Stufe2 (v0.97.19): Statik-Mess-Phase entfernt. Nur noch Operate-
Pattern werden hier getestet (50:50, 70:30, 30:70). DiversityController
hat keine `_phase` / `record_measurement` / `_evaluate` / `MEASURE_CYCLES`
mehr — die Ratio-Bestimmung uebernimmt `DynamicDiversityController` live.

Prueft:
- Paritaets-Verteilung (Even+Odd fuer jede Antenne)
- Loop-Uebergang nahtlos (max N hintereinander)
- Ratio korrekt

OMNI-CQ Pattern-Tests siehe tests/test_omni_cq_worker.py.
"""

import pytest
from core.diversity import DiversityController


# ─── Hilfsfunktionen ─────────────────────────────────────────────────────────

def get_pattern(dc, n_cycles):
    """Pattern aus DiversityController extrahieren (Operate-Phase)."""
    pattern = []
    for _ in range(n_cycles):
        pattern.append(dc.choose())
        dc._operate_cycles += 1
    return pattern


def check_max_consecutive(pattern, max_allowed):
    """Prueft dass nie mehr als max_allowed gleiche hintereinander kommen."""
    for i in range(len(pattern) - max_allowed):
        window = pattern[i:i + max_allowed + 1]
        if len(set(window)) == 1:
            pytest.fail(f">{max_allowed}× '{window[0]}' ab Position {i}: {pattern}")


def check_both_parities(pattern, antenna, start_parity="even"):
    """Prueft dass eine Antenne BEIDE Paritaeten (Even+Odd) bekommt."""
    parities = set()
    for i, ant in enumerate(pattern):
        if ant == antenna:
            parity = "even" if (i % 2 == 0) else "odd"
            if start_parity == "odd":
                parity = "odd" if parity == "even" else "even"
            parities.add(parity)
    assert len(parities) == 2, \
        f"{antenna} bekommt nur {parities} (braucht even+odd): {pattern}"


def check_seamless_loop(pattern, max_consecutive):
    """Prueft Loop-Uebergang: Pattern 3× hintereinander, max N gleiche."""
    triple = pattern + pattern + pattern
    check_max_consecutive(triple, max_consecutive)


# ─── 50:50 Pattern ────────────────────────────────────────────────────────────

def test_5050_ratio():
    dc = DiversityController()
    dc.ratio = "50:50"
    p = get_pattern(dc, 8)
    assert p.count("A1") == 4 and p.count("A2") == 4


def test_5050_parities():
    dc = DiversityController()
    dc.ratio = "50:50"
    p = get_pattern(dc, 8)
    check_both_parities(p, "A1")
    check_both_parities(p, "A2")


def test_5050_seamless():
    dc = DiversityController()
    dc.ratio = "50:50"
    p = get_pattern(dc, 4)
    check_seamless_loop(p, 2)


# ─── 70:30 Pattern (A1 dominant) ─────────────────────────────────────────────

def test_6733_ratio():
    dc = DiversityController()
    dc.ratio = "70:30"
    p = get_pattern(dc, 6)
    assert p.count("A1") == 4 and p.count("A2") == 2


def test_6733_parities():
    dc = DiversityController()
    dc.ratio = "70:30"
    p = get_pattern(dc, 12)  # 2 Perioden
    check_both_parities(p, "A1")
    check_both_parities(p, "A2")


def test_6733_seamless():
    dc = DiversityController()
    dc.ratio = "70:30"
    p = get_pattern(dc, 6)
    check_seamless_loop(p, 2)


def test_6733_max_consecutive():
    dc = DiversityController()
    dc.ratio = "70:30"
    p = get_pattern(dc, 18)  # 3 Perioden
    check_max_consecutive(p, 2)


# ─── 30:70 Pattern (A2 dominant) ─────────────────────────────────────────────

def test_3367_ratio():
    dc = DiversityController()
    dc.ratio = "30:70"
    p = get_pattern(dc, 6)
    assert p.count("A2") == 4 and p.count("A1") == 2


def test_3367_seamless():
    dc = DiversityController()
    dc.ratio = "30:70"
    p = get_pattern(dc, 6)
    check_seamless_loop(p, 2)


# OMNI-CQ Pattern-Tests siehe tests/test_omni_cq_worker.py (P4.OMNI-NEUBAU).
