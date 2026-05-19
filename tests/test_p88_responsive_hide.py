"""P88 — Responsive Hide bei schmaler Spalte (v0.97.58)

Mike-Field-Test 19.05.2026 (Screenshots 14:17): Bei schmaler Control-
Panel-Spalte werden die Diversity-Count-Labels (_a1_count_label,
_a2_count_label) gequetscht und unlesbar.

Fix KISS: Schwellwert 380px, darunter labels via setHidden(True).
Andere Elemente (Prozent-Labels mit minWidth=30) bleiben sichtbar.

Tests T1-T5:
- T1: Width < 380 → beide Count-Labels hidden
- T2: Width >= 380 → beide sichtbar
- T3: Toggle schmal → breit → schmal mehrfach korrekt
- T4: setText während hidden bleibt funktional (Text bei wieder-wide sichtbar)
- T5: _COUNT_LABEL_HIDE_THRESHOLD Konstante 380
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


# ── T1 — Schmal → labels hidden ──────────────────────────────────────


def test_t1_schmal_count_labels_hidden(qapp):
    """Width < 380 → _a1_count_label + _a2_count_label hidden."""
    from ui.control_panel import ControlPanel

    cp = ControlPanel()
    try:
        cp.resize(350, 600)
        cp._update_count_label_visibility()
        assert cp._a1_count_label.isHidden() is True
        assert cp._a2_count_label.isHidden() is True
    finally:
        cp.deleteLater()


# ── T2 — Breit → labels visible ───────────────────────────────────────


def test_t2_breit_count_labels_visible(qapp):
    """Width >= 380 → beide Count-Labels NICHT hidden."""
    from ui.control_panel import ControlPanel

    cp = ControlPanel()
    try:
        cp.resize(500, 600)
        cp._update_count_label_visibility()
        assert cp._a1_count_label.isHidden() is False
        assert cp._a2_count_label.isHidden() is False
    finally:
        cp.deleteLater()


# ── T3 — Toggle schmal/breit mehrfach ────────────────────────────────


def test_t3_toggle_schmal_breit_korrekt(qapp):
    """Mehrfaches Resize zwischen schmal und breit → State immer korrekt."""
    from ui.control_panel import ControlPanel

    cp = ControlPanel()
    try:
        for width, should_hide in [
            (300, True),
            (500, False),
            (200, True),
            (600, False),
            (379, True),  # genau unter Schwelle
            (380, False),  # genau auf Schwelle (>=)
        ]:
            cp.resize(width, 600)
            cp._update_count_label_visibility()
            assert cp._a1_count_label.isHidden() is should_hide, \
                f"width={width}: erwartet hidden={should_hide}"
            assert cp._a2_count_label.isHidden() is should_hide
    finally:
        cp.deleteLater()


# ── T4 — setText während hidden bleibt funktional ─────────────────────


def test_t4_settext_waehrend_hidden_persistent(qapp):
    """Hidden + setText → bei wieder-wide ist Text sichtbar und korrekt."""
    from ui.control_panel import ControlPanel

    cp = ControlPanel()
    try:
        # 1. Schmal → hidden
        cp.resize(300, 600)
        cp._update_count_label_visibility()
        assert cp._a1_count_label.isHidden() is True

        # 2. setText während hidden
        cp._a1_count_label.setText("ANT2-Win 86%")
        cp._a2_count_label.setText("test")
        assert cp._a1_count_label.text() == "ANT2-Win 86%"

        # 3. Breit → visible mit gespeichertem Text
        cp.resize(500, 600)
        cp._update_count_label_visibility()
        assert cp._a1_count_label.isHidden() is False
        assert cp._a1_count_label.text() == "ANT2-Win 86%"
    finally:
        cp.deleteLater()


# ── T5 — Konstante _COUNT_LABEL_HIDE_THRESHOLD == 380 ─────────────────


def test_t5_schwellwert_konstante(qapp):
    """Schwellwert ist Konstante 380px (aus Mike-Field-Test-Screenshots)."""
    from ui.control_panel import ControlPanel

    assert ControlPanel._COUNT_LABEL_HIDE_THRESHOLD == 380


# ── T6 — Defensive: ohne _a1_count_label kein Crash ───────────────────


def test_t6_defensive_ohne_labels(qapp):
    """`_update_count_label_visibility` ohne `_a1_count_label`-Attribut
    → kein AttributeError (resizeEvent kann vor _setup_ui feuern).
    """
    from ui.control_panel import ControlPanel

    cp = ControlPanel()
    try:
        # Attribute simuliert entfernen
        a1_backup = cp._a1_count_label
        a2_backup = cp._a2_count_label
        del cp._a1_count_label
        del cp._a2_count_label
        # Darf KEIN AttributeError werfen
        cp._update_count_label_visibility()
        # Restore für Cleanup
        cp._a1_count_label = a1_backup
        cp._a2_count_label = a2_backup
    finally:
        cp.deleteLater()
