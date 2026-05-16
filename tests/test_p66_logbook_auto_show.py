"""P66 (v0.97.42) — Logbuch-Tab-Auto-Show: Detail bei selektierter Station.

Mike-Wunsch 16.05.2026: Wenn User auf Logbuch-Tab wechselt UND eine Zeile
ist selektiert → Detail-Overlay rechts automatisch zeigen (statt manuell
nochmal klicken zu muessen).

T1: Auto-Show bei selektiertem Record
T2: No-Op ohne Selektion
T3: Index=0 (QSO-Live) ruft Overlay-Close (Regression)
T4: Exception in _selected_record() abgefangen (R1-V3 Defensive)
T5: Source-Level — Handler ruft _selected_record und _on_logbook_qso_clicked
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock


# ── T1 — Auto-Show bei Selektion ────────────────────────────────────────


def test_t1_auto_show_with_selection():
    """index=1 mit selektiertem Record → _on_logbook_qso_clicked aufgerufen."""
    from ui import mw_qso
    record = {"CALL": "EA5D", "BAND": "30M", "MODE": "FT8"}

    obj = MagicMock()
    obj.qso_panel.logbook._selected_record = MagicMock(return_value=record)
    obj._on_logbook_qso_clicked = MagicMock()
    obj._right_stack.setCurrentIndex = MagicMock()

    # _on_qso_tab_changed an Mock-Objekt binden
    mw_qso.QSOMixin._on_qso_tab_changed(obj, 1)

    obj._on_logbook_qso_clicked.assert_called_once_with(record)


# ── T2 — Keine Selektion → No-Op ────────────────────────────────────────


def test_t2_no_action_without_selection():
    """index=1 ohne Selektion → _on_logbook_qso_clicked NICHT aufgerufen."""
    from ui import mw_qso

    obj = MagicMock()
    obj.qso_panel.logbook._selected_record = MagicMock(return_value=None)
    obj._on_logbook_qso_clicked = MagicMock()
    obj._right_stack.setCurrentIndex = MagicMock()

    mw_qso.QSOMixin._on_qso_tab_changed(obj, 1)

    obj._on_logbook_qso_clicked.assert_not_called()
    obj._right_stack.setCurrentIndex.assert_not_called()


# ── T3 — Index=0 ruft setCurrentIndex(0) (Regression) ───────────────────


def test_t3_index_zero_closes_overlay():
    """index=0 → _right_stack.setCurrentIndex(0) — kein Overlay."""
    from ui import mw_qso

    obj = MagicMock()
    obj._right_stack.setCurrentIndex = MagicMock()

    mw_qso.QSOMixin._on_qso_tab_changed(obj, 0)

    obj._right_stack.setCurrentIndex.assert_called_once_with(0)


# ── T4 — Exception abgefangen (R1-V3 Defensive) ────────────────────────


def test_t4_exception_swallowed():
    """Wenn _selected_record() Exception wirft → Handler bricht sauber ab."""
    from ui import mw_qso

    obj = MagicMock()
    obj.qso_panel.logbook._selected_record = MagicMock(
        side_effect=RuntimeError("defekter UserRole-Dict"))
    obj._on_logbook_qso_clicked = MagicMock()
    obj._right_stack.setCurrentIndex = MagicMock()

    # Sollte KEIN Exception nach oben werfen
    mw_qso.QSOMixin._on_qso_tab_changed(obj, 1)

    obj._on_logbook_qso_clicked.assert_not_called()


# ── T5 — Source-Level: Handler enthält erwartete Aufrufe ───────────────


def test_t5_source_contains_expected_calls():
    """`_on_qso_tab_changed` ruft `_selected_record` und behandelt Logbuch."""
    src = (Path(__file__).parent.parent / "ui" / "mw_qso.py").read_text()
    idx = src.find("def _on_qso_tab_changed")
    assert idx > 0
    next_def = src.find("\n    def ", idx + 10)
    body = src[idx:next_def if next_def > 0 else idx + 2000]

    assert "elif index == 1" in body, (
        "P66: Handler muss elif-Branch fuer Logbuch-Tab haben")
    assert "_selected_record()" in body, (
        "P66: Handler muss logbook._selected_record() aufrufen")
    assert "_on_logbook_qso_clicked" in body, (
        "P66: Handler muss _on_logbook_qso_clicked weiterleiten")
    assert "try:" in body and "except" in body, (
        "P66 R1-V3: Defensive try/except fuer _selected_record()")
