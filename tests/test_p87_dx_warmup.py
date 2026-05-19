"""P87 — DX-Mode Warmup-Anzeige analog P85 Standard-Mode (v0.97.57)

Mike-Field-Test 19.05.2026: Diversity DX gerade aktiviert, Ratio zeigt
50:50, aber DX-Counts 26:06 (ANT1 dominiert). Widerspruch wegen
Pattern-Anfangs-Versatz.

Fix: 4-Zyklus-Warmup analog P85 Standard-Mode. < 4 Zyklen → „Diversity
läuft...". Reset via `reset_win_rate_history` bei Mode/Band/Diversity-
Wechsel.

Tests T1-T4:
- T1: DX-Mode 1.-3. Aufruf → „Diversity läuft..." (Warmup)
- T2: DX-Mode 4. Aufruf → echte Counts (`26 DX` / `06 DX`)
- T3: `reset_win_rate_history` → `_dx_warmup_count` zurück auf 0
- T4: Standard-Mode unverändert (Counter wird NICHT incrementiert)
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


# ── T1 — DX-Mode 1.-3. Aufruf zeigt "Diversity läuft..." ──────────────


def test_t1_dx_warmup_zeigt_diversity_laeuft(qapp):
    """P89 (v0.97.59): DX-Mode 1.-3. Aufruf → „Berechnung läuft..."."""
    from ui.control_panel import ControlPanel

    cp = ControlPanel()
    try:
        # Cycle 1, 2, 3 → Warmup
        for i in range(1, 4):
            cp.update_diversity_counts(
                a1_count=30, a2_count=0,
                scoring_mode="dx",
                a1_weak_count=26, a2_weak_count=0
            )
            assert cp._a1_count_label.text() == "Berechnung läuft...", \
                f"Cycle {i}: Warmup-Text fehlt"
            assert cp._a2_count_label.text() == "", \
                f"Cycle {i}: a2-Label muss leer sein im Warmup"
        assert cp._dx_warmup_count == 3
    finally:
        cp.deleteLater()


# ── T2 — DX-Mode 4. Aufruf zeigt echte Counts ─────────────────────────


def test_t2_dx_nach_4_zyklen_labels_leer(qapp):
    """P89 (v0.97.59): DX-Mode 4. Aufruf → beide Labels LEER (keine Counts mehr)."""
    from ui.control_panel import ControlPanel

    cp = ControlPanel()
    try:
        for _ in range(4):
            cp.update_diversity_counts(
                a1_count=30, a2_count=5,
                scoring_mode="dx",
                a1_weak_count=26, a2_weak_count=6
            )
        # Nach 4 Aufrufen Warmup vorbei → P89 Labels leer
        assert cp._dx_warmup_count == 4
        assert cp._a1_count_label.text() == ""
        assert cp._a2_count_label.text() == ""
    finally:
        cp.deleteLater()


# ── T3 — reset_win_rate_history resettet auch DX-Counter ──────────────


def test_t3_reset_win_rate_history_resettet_dx_counter(qapp):
    """`reset_win_rate_history` muss auch `_dx_warmup_count` auf 0 setzen
    (Mode/Band/Diversity-Wechsel-Pfad).
    """
    from ui.control_panel import ControlPanel

    cp = ControlPanel()
    try:
        # 5 DX-Zyklen → Warmup vorbei
        for _ in range(5):
            cp.update_diversity_counts(
                a1_count=30, a2_count=5,
                scoring_mode="dx",
                a1_weak_count=26, a2_weak_count=6
            )
        assert cp._dx_warmup_count == 5

        cp.reset_win_rate_history()

        assert cp._dx_warmup_count == 0, \
            "P87: reset_win_rate_history muss auch _dx_warmup_count auf 0 setzen"
        # P85: _win_rate_history bleibt parallel resettet
        assert len(cp._win_rate_history) == 0
    finally:
        cp.deleteLater()


# ── T4 — Standard-Mode unverändert (kein DX-Counter-Side-Effect) ──────


def test_t4_standard_mode_inkrementiert_dx_counter_nicht(qapp):
    """Standard-Mode darf `_dx_warmup_count` NICHT inkrementieren —
    sonst Wechsel-Logik kaputt. P89: Standard-Display nach Warmup leer.
    """
    from ui.control_panel import ControlPanel

    cp = ControlPanel()
    try:
        for _ in range(10):
            cp.update_diversity_counts(
                a1_count=10, a2_count=10,
                scoring_mode="normal",
                ant2_wins=5, total_compared=10
            )
        # Standard-Mode darf DX-Counter nicht anfassen
        assert cp._dx_warmup_count == 0, \
            "Standard-Mode darf _dx_warmup_count nicht inkrementieren"
        # P89: cum_total=100 >= 4 → Labels leer (kein ANT2-Win mehr)
        assert cp._a1_count_label.text() == ""
        assert cp._a2_count_label.text() == ""
    finally:
        cp.deleteLater()


# ── T5 — Reset bei beiden Counts==0 inkrementiert NICHT ───────────────


def test_t5_zero_counts_inkrementieren_warmup_counter(qapp):
    """P89 (v0.97.59): `--`-Early-Return ENTFÄLLT. Auch bei Zero-Counts
    inkrementiert der DX-Branch den Warmup-Counter — Display zeigt
    „Berechnung läuft..." statt „--" für konsistente UX.
    """
    from ui.control_panel import ControlPanel

    cp = ControlPanel()
    try:
        for _ in range(3):
            cp.update_diversity_counts(
                a1_count=0, a2_count=0,
                scoring_mode="dx",
                a1_weak_count=0, a2_weak_count=0
            )
        assert cp._dx_warmup_count == 3, \
            "P89: Zero-Counts füttern jetzt den Warmup-Counter (kein Early-Return)"
        # Display zeigt „Berechnung läuft..." (konsistent)
        assert cp._a1_count_label.text() == "Berechnung läuft..."
        assert cp._a2_count_label.text() == ""
    finally:
        cp.deleteLater()
