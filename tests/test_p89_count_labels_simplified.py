"""P89 — Diversity-Count-Labels vereinfacht (v0.97.59)

Mike-Beobachtung 19.05.2026 nach P88: Quantitative Anzeigen sorgten
fuer Verwirrung, weil sie zeitlich immer 1-3 Zyklen vor dem Ratio-Sprung
liefen (Hysterese 8%). Beispiel: ANT2-Win 25% aber Ratio noch 50:50 →
User denkt „ist was kaputt".

Mike-Spec KISS: „Berechnung laeuft..." waehrend Warmup, sonst leer.
Ratio + Bedien-% sprechen fuer sich.

DeepSeek-V4-pro Brainstorm-R1 empfahl Variante C mit 2 Verbesserungen:
1. `--`-Early-Return entfernen → einheitlich „Berechnung laeuft..."
2. DX-Mode nach Warmup auch leer (kein „X DX" mehr)

Tests T1-T6 (alle ohne Radio):
- T1: Standard-Mode Warmup zeigt „Berechnung laeuft..."
- T2: Standard-Mode nach Warmup → beide Labels leer
- T3: DX-Mode Warmup zeigt „Berechnung laeuft..."
- T4: DX-Mode nach Warmup → beide Labels leer
- T5: Zero-Counts haengen im Warmup (kein „--"-Pfad mehr)
- T6: APP_VERSION-Bump auf 0.97.59+
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


# ── T1 — Standard-Mode Warmup zeigt „Berechnung läuft..." ─────────────


def test_t1_standard_warmup_text(qapp):
    """Standard-Mode mit cum_total < 4 → „Berechnung läuft..."."""
    from ui.control_panel import ControlPanel

    cp = ControlPanel()
    try:
        cp.update_diversity_counts(
            a1_count=5, a2_count=5,
            scoring_mode="normal",
            ant2_wins=1, total_compared=2,
        )
        assert cp._a1_count_label.text() == "Berechnung läuft..."
        assert cp._a2_count_label.text() == ""
    finally:
        cp.deleteLater()


# ── T2 — Standard-Mode nach Warmup → Labels leer ──────────────────────


def test_t2_standard_nach_warmup_leer(qapp):
    """Standard-Mode mit cum_total >= 4 → beide Labels leer."""
    from ui.control_panel import ControlPanel

    cp = ControlPanel()
    try:
        # 2 Zyklen, cum_total=6
        cp.update_diversity_counts(
            a1_count=3, a2_count=3, scoring_mode="normal",
            ant2_wins=2, total_compared=3,
        )
        cp.update_diversity_counts(
            a1_count=3, a2_count=3, scoring_mode="normal",
            ant2_wins=1, total_compared=3,
        )
        assert cp._a1_count_label.text() == ""
        assert cp._a2_count_label.text() == ""
    finally:
        cp.deleteLater()


# ── T3 — DX-Mode Warmup zeigt „Berechnung läuft..." ───────────────────


def test_t3_dx_warmup_text(qapp):
    """DX-Mode 1.-3. Aufruf → „Berechnung läuft..."."""
    from ui.control_panel import ControlPanel

    cp = ControlPanel()
    try:
        for i in range(1, 4):
            cp.update_diversity_counts(
                a1_count=30, a2_count=5,
                scoring_mode="dx",
                a1_weak_count=26, a2_weak_count=6,
            )
            assert cp._a1_count_label.text() == "Berechnung läuft...", \
                f"Cycle {i}: Warmup-Text fehlt"
            assert cp._a2_count_label.text() == ""
    finally:
        cp.deleteLater()


# ── T4 — DX-Mode nach Warmup → Labels leer ────────────────────────────


def test_t4_dx_nach_warmup_leer(qapp):
    """DX-Mode 4.+ Aufruf → beide Labels leer (kein „X DX" mehr)."""
    from ui.control_panel import ControlPanel

    cp = ControlPanel()
    try:
        for _ in range(5):
            cp.update_diversity_counts(
                a1_count=30, a2_count=5,
                scoring_mode="dx",
                a1_weak_count=26, a2_weak_count=6,
            )
        assert cp._a1_count_label.text() == ""
        assert cp._a2_count_label.text() == ""
    finally:
        cp.deleteLater()


# ── T5 — Zero-Counts hängen im Warmup ─────────────────────────────────


def test_t5_zero_counts_warmup_hint(qapp):
    """Zero-Counts (a1=a2=0) → „Berechnung läuft..." statt „--"
    (Pre-P89 hatte hier Early-Return mit „--" / „  --").

    Standard: cum_total bleibt 0 → Warmup-Branch.
    DX: _dx_warmup_count inkrementiert → bei < 4 Warmup-Branch.
    """
    from ui.control_panel import ControlPanel

    cp = ControlPanel()
    try:
        # Standard-Mode mit nichts
        cp.update_diversity_counts(
            a1_count=0, a2_count=0,
            scoring_mode="normal",
            ant2_wins=0, total_compared=0,
        )
        assert cp._a1_count_label.text() == "Berechnung läuft..."
        assert cp._a2_count_label.text() == ""

        # DX-Mode mit nichts (3 Zyklen, vor Warmup)
        cp.reset_win_rate_history()
        for _ in range(3):
            cp.update_diversity_counts(
                a1_count=0, a2_count=0,
                scoring_mode="dx",
                a1_weak_count=0, a2_weak_count=0,
            )
        assert cp._dx_warmup_count == 3
        assert cp._a1_count_label.text() == "Berechnung läuft..."
        assert cp._a2_count_label.text() == ""
    finally:
        cp.deleteLater()


# ── T6 — APP_VERSION-Bump ─────────────────────────────────────────────


def test_t6_app_version_bump():
    """APP_VERSION muss >= 0.97.59 sein (P89)."""
    import main
    assert main.APP_VERSION >= "0.97.59", \
        f"APP_VERSION ist {main.APP_VERSION}, erwartet >= 0.97.59"
