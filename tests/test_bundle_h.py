"""Bundle H (14.05.2026, v0.97.24 → v0.97.25) — Bandpilot-Aware Diversity-Klick.

Mike-Spec: Beim Klick auf DIVERSITY (Normal → Diversity) je nach
Bandpilot-Modus unterschiedlich verhalten:

| Bandpilot | Daten | Verhalten |
|---|---|---|
| off | egal | Dialog „Welchen Modus verwenden?" (heute) |
| auto | genug | kein Dialog — Bandpilot wählt + Toast 6s |
| auto | zu wenig | Dialog dynamisch „Nicht genug Daten — bitte wählen" |
| manual | genug | Manual-Dialog mit Std/DX-Empfehlung |
| manual | zu wenig | Dialog wie off |

Architektur:
- `recommend_for_hour(..., allowed_modes=)` Subset-Vergleich
- `code_mode_to_scoring()` Mapping
- `_show_diversity_choice_dialog(intro_text)` dynamischer Wahl-Dialog
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


# ─────────────────────────────────────────────────────────────────────
# T1: recommend_for_hour mit allowed_modes — ECHTE Logik (Anti-Mock)
# ─────────────────────────────────────────────────────────────────────


def _make_summary(hour: int = 12, days: int = 5, cycles: int = 500,
                  normal_mean: float = 20.0,
                  div_std_mean: float = 30.0,
                  div_dx_mean: float = 25.0):
    """Synthetisches summary_24h-Dict mit 3 Modi."""
    return {
        hour: {
            "normal": {"days": days, "cycles": cycles, "mean": normal_mean},
            "diversity_normal": {
                "days": days, "cycles": cycles, "mean": div_std_mean},
            "diversity_dx": {
                "days": days, "cycles": cycles, "mean": div_dx_mean},
        }
    }


def test_recommend_default_returns_3_modes():
    """T1a: allowed_modes=None Default → 3-Wege-Ranking (Backward-Compat)."""
    from core.mode_recommender import recommend_for_hour
    summary = _make_summary()
    rec = recommend_for_hour(summary, 12, current_mode="normal")
    assert rec is not None
    assert len(rec["ranking"]) == 3, "Default sollte 3-Wege-Ranking liefern"
    assert rec["top1"] == "diversity_normal"  # 30.0 > 25.0 > 20.0


def test_recommend_allowed_modes_diversity_only_subset_ranking():
    """T1b: allowed_modes=Div-only + current=normal → 2-er Ranking,
    decision=switch (current nicht in allowed_modes)."""
    from core.mode_recommender import recommend_for_hour
    summary = _make_summary()
    rec = recommend_for_hour(
        summary, 12, current_mode="normal",
        allowed_modes=("diversity_normal", "diversity_dx"),
    )
    assert rec is not None
    assert len(rec["ranking"]) == 2, "Subset sollte 2-er Ranking liefern"
    assert rec["decision"] == "switch"
    assert rec["decision_mode"] == "diversity_normal"  # 30 > 25
    # Ranking enthält KEIN "normal"
    modes_in_ranking = [m for m, _ in rec["ranking"]]
    assert "normal" not in modes_in_ranking


def test_recommend_allowed_modes_missing_data_returns_none():
    """T1c: allowed_modes + ein Mode hat zu wenig Daten → None."""
    from core.mode_recommender import recommend_for_hour
    summary = _make_summary(cycles=10)  # zu wenig (MIN_CYCLES_HOUR > 10)
    rec = recommend_for_hour(
        summary, 12, current_mode="normal",
        allowed_modes=("diversity_normal", "diversity_dx"),
    )
    assert rec is None


# ─────────────────────────────────────────────────────────────────────
# T2: code_mode_to_scoring Mapping
# ─────────────────────────────────────────────────────────────────────


def test_code_mode_to_scoring_diversity_dx():
    """T2a: diversity_dx → 'dx'."""
    from core.mode_recommender import code_mode_to_scoring
    assert code_mode_to_scoring("diversity_dx") == "dx"


def test_code_mode_to_scoring_diversity_normal():
    """T2b: diversity_normal → 'normal' (Standard-Scoring)."""
    from core.mode_recommender import code_mode_to_scoring
    assert code_mode_to_scoring("diversity_normal") == "normal"


def test_code_mode_to_scoring_normal_fallback():
    """T2c: 'normal' (Code-Mode) → 'normal' (Default-Fallback)."""
    from core.mode_recommender import code_mode_to_scoring
    assert code_mode_to_scoring("normal") == "normal"


def test_code_mode_to_scoring_unknown_fallback():
    """T2d: unbekannter String → 'normal' (Default-Fallback)."""
    from core.mode_recommender import code_mode_to_scoring
    assert code_mode_to_scoring("unknown_mode") == "normal"


# ─────────────────────────────────────────────────────────────────────
# T9: BandpilotAutoToast mit 2-elementigem Ranking — kein Crash
# ─────────────────────────────────────────────────────────────────────


def test_bandpilot_auto_toast_with_2_elements_ranking(app):
    """T9: AutoToast iteriert ranking-len-agnostisch — 2-er OK."""
    from ui.bandpilot_dialogs import BandpilotAutoToast
    rec = {
        "top1": "diversity_normal",
        "top1_mean": 30.0,
        "ranking": [("diversity_normal", 30.0), ("diversity_dx", 25.0)],
        "decision": "switch",
        "decision_mode": "diversity_normal",
    }
    toast = BandpilotAutoToast(None, "30m", 12, rec)
    assert toast is not None
    toast.deleteLater()


# ─────────────────────────────────────────────────────────────────────
# T8a/b: BandpilotManualDialog Hint bei current=None (Bundle H)
# ─────────────────────────────────────────────────────────────────────


def test_manual_dialog_with_current_none_hides_hint(app):
    """T8a: Bei current=None wird Hint NICHT erzeugt (kein leeres Label)."""
    from ui.bandpilot_dialogs import BandpilotManualDialog
    rec = {
        "top1": "diversity_normal",
        "top1_mean": 30.0,
        "ranking": [("diversity_normal", 30.0), ("diversity_dx", 25.0)],
        "decision": "switch",
        "decision_mode": "diversity_normal",
    }
    dlg = BandpilotManualDialog(None, "30m", 12, rec, current=None)
    # Hint-Label sollte nicht im Layout sein wenn current=None
    from PySide6.QtWidgets import QLabel
    hint_found = False
    for child in dlg.findChildren(QLabel):
        if child.objectName() == "hint":
            hint_found = True
    assert not hint_found, (
        "Bei current=None darf KEIN hint-Label im Layout sein "
        "(verwirrt User wenn current nicht im Ranking)")
    dlg.deleteLater()


def test_manual_dialog_with_current_set_shows_hint(app):
    """T8b: Bei current gesetzt erscheint Hint wie heute."""
    from ui.bandpilot_dialogs import BandpilotManualDialog
    rec = {
        "top1": "diversity_normal",
        "top1_mean": 30.0,
        "ranking": [("normal", 20.0), ("diversity_normal", 30.0),
                    ("diversity_dx", 25.0)],
        "decision": "switch",
        "decision_mode": "diversity_normal",
    }
    dlg = BandpilotManualDialog(None, "30m", 12, rec, current="normal")
    from PySide6.QtWidgets import QLabel
    hint_found = False
    for child in dlg.findChildren(QLabel):
        if child.objectName() == "hint":
            hint_found = True
    assert hint_found, "Bei current gesetzt MUSS hint-Label vorhanden sein"
    dlg.deleteLater()


# ─────────────────────────────────────────────────────────────────────
# T10: defensive no_change-Fallback bei H-Pfad
# ─────────────────────────────────────────────────────────────────────


def test_recommend_no_change_impossible_when_current_not_in_allowed():
    """T10: allowed_modes-Subset + current nicht drin → decision IMMER
    'switch' (kein no_change möglich, weil current-Mean fehlt → kein
    Tolerance-Check).
    """
    from core.mode_recommender import recommend_for_hour
    # current=normal, allowed=Div-only → current nicht in modes_to_check
    summary = _make_summary(normal_mean=29.5, div_std_mean=30.0, div_dx_mean=25.0)
    rec = recommend_for_hour(
        summary, 12, current_mode="normal",
        allowed_modes=("diversity_normal", "diversity_dx"),
    )
    assert rec is not None
    assert rec["decision"] == "switch", (
        "H-Pfad muss IMMER decision='switch' liefern, weil current "
        "(normal) nie in allowed_modes (div_normal, div_dx) ist.")
