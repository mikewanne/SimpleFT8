"""Toast-Bundle (v0.97.18) — Medaillen-Marker + 6s Display.

Mike-Feedback 13.05.2026 nach P46-Field-Test:
- Ranking 1./2./3. nicht klar als Ranking erkennbar bei 5s-Toast
- 5s zu kurz fuer Ranking-Lesezeit → 6s

R1-SOLLTE-Defensive: Emoji-Fallback fuer Systeme ohne Color-Emoji-
Renderer via `SIMPLEFT8_TEXT_MARKERS=1`.

6 Tests:
- T1 Default-Medaillen 🥇🥈🥉
- T2 Out-of-range returnt ""
- T3 Auto-Toast enthaelt 🥇
- T4 Manual-Dialog enthaelt 🥇
- T5 _TOAST_DISPLAY_MS == 6000
- T6 Text-Fallback via Env-Var
"""

import importlib
import pytest


@pytest.fixture(scope="module")
def qapp():
    """Qt Application Instance — module-scoped."""
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def sample_rec():
    return {
        "top1": "diversity_dx",
        "top1_mean": 50.4,
        "ranking": [("diversity_dx", 50.4), ("normal", 35.2),
                    ("diversity_normal", 30.1)],
        "decision": "switch",
        "decision_mode": "diversity_dx",
    }


# ── T1: Default-Medaillen ─────────────────────────────────────────────────


def test_rank_marker_default_medals():
    """Default (kein Env-Var): _rank_marker returnt 🥇🥈🥉 fuer idx 0/1/2."""
    from ui.bandpilot_dialogs import _rank_marker, _USE_EMOJI
    # Test geht davon aus dass die Test-Shell SIMPLEFT8_TEXT_MARKERS nicht
    # gesetzt hat (Default-Verhalten)
    if _USE_EMOJI:
        assert _rank_marker(0) == "🥇"
        assert _rank_marker(1) == "🥈"
        assert _rank_marker(2) == "🥉"


# ── T2: Out-of-range ──────────────────────────────────────────────────────


def test_rank_marker_returns_empty_for_invalid_idx():
    """idx > 2 oder idx < 0 returnt ""."""
    from ui.bandpilot_dialogs import _rank_marker
    assert _rank_marker(3) == ""
    assert _rank_marker(-1) == ""
    assert _rank_marker(100) == ""


# ── T3: Auto-Toast enthaelt Medaille ──────────────────────────────────────


def test_auto_toast_uses_medal_markers(qapp, sample_rec):
    """BandpilotAutoToast enthaelt 🥇-Marker im Ranking-Label."""
    from ui.bandpilot_dialogs import BandpilotAutoToast, _USE_EMOJI
    toast = BandpilotAutoToast(None, "40m", 13, sample_rec)
    from PySide6.QtWidgets import QLabel
    texts = [w.text() for w in toast.findChildren(QLabel)]
    combined = " ".join(texts)
    if _USE_EMOJI:
        assert "🥇" in combined, f"Top-1-Medaille fehlt in Toast: {texts!r}"
        assert "🥈" in combined, f"2.-Medaille fehlt in Toast: {texts!r}"
        assert "🥉" in combined, f"3.-Medaille fehlt in Toast: {texts!r}"
    else:
        assert "Top:" in combined
    toast.close()


# ── T4: Manual-Dialog enthaelt Medaille ───────────────────────────────────


def test_manual_dialog_uses_medal_markers(qapp, sample_rec):
    """BandpilotManualDialog enthaelt 🥇-Marker im Ranking-Label."""
    from ui.bandpilot_dialogs import BandpilotManualDialog, _USE_EMOJI
    dlg = BandpilotManualDialog(None, "40m", 13, sample_rec, "normal")
    from PySide6.QtWidgets import QLabel
    texts = [w.text() for w in dlg.findChildren(QLabel)]
    combined = " ".join(texts)
    if _USE_EMOJI:
        assert "🥇" in combined, f"Top-1-Medaille fehlt in Dialog: {texts!r}"
    else:
        assert "Top:" in combined
    # ●-Marker bleibt fuer current
    assert "●" in combined, "current-Marker ● fehlt"
    dlg.close()


# ── T5: Display-Konstante 6000ms ──────────────────────────────────────────


def test_toast_display_ms_is_6000():
    """Self-Close-Zeit 6 Sekunden (Mike-Wunsch 13.05.)."""
    from ui.bandpilot_dialogs import _TOAST_DISPLAY_MS
    assert _TOAST_DISPLAY_MS == 6000


# ── T6: Text-Fallback (R1-SOLLTE) ─────────────────────────────────────────


def test_rank_marker_text_fallback(monkeypatch):
    """Mit SIMPLEFT8_TEXT_MARKERS=1 → Text-Marker statt Emoji.

    Modul muss neu importiert werden damit `_USE_EMOJI` neu evaluiert
    wird (Modul-Level-Konstante).
    """
    monkeypatch.setenv("SIMPLEFT8_TEXT_MARKERS", "1")
    import ui.bandpilot_dialogs
    importlib.reload(ui.bandpilot_dialogs)
    from ui.bandpilot_dialogs import _rank_marker, _USE_EMOJI
    assert _USE_EMOJI is False
    assert _rank_marker(0) == "Top:"
    assert _rank_marker(1) == "2.:"
    assert _rank_marker(2) == "3.:"
    # Cleanup: monkeypatch.delenv + reload danach
    monkeypatch.delenv("SIMPLEFT8_TEXT_MARKERS")
    importlib.reload(ui.bandpilot_dialogs)
