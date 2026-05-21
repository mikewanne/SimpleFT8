"""P109 (21.05.2026, v0.97.86) — X-Button im QSO-Detail-Overlay schliesst auch Logbuch-Tab.

Mike-Beobachtung 21.05.: Klick auf X im Detail-Overlay schloss nur das Overlay,
aber der Logbuch-Tab blieb aktiv. Spec: X soll wie QSO-Button-Klick wirken —
beide Bereiche schliessen (Tab zurueck auf QSO-Live).

Loesung: btn_close.clicked triggert tabs.setCurrentIndex(0). Der existierende
_on_qso_tab_changed(0)-Handler erledigt dann Stack-Switch automatisch.

Tests:
- T1: btn_close-Click ruft tabs.setCurrentIndex(0)
- T2: Source-Pattern verifiziert
"""
from __future__ import annotations

import re
from pathlib import Path


def _read(rel: str) -> str:
    return (Path(__file__).resolve().parent.parent / rel).read_text(
        encoding="utf-8")


def test_t1_btn_close_triggers_tab_switch():
    """Source: btn_close.clicked verbindet zu tabs.setCurrentIndex(0)."""
    src = _read("ui/main_window.py")
    # Such-Pattern: btn_close.clicked.connect(...) muss tabs.setCurrentIndex(0) enthalten
    m = re.search(
        r"_detail_overlay\.btn_close\.clicked\.connect\(\s*"
        r"lambda:\s*self\.qso_panel\.tabs\.setCurrentIndex\(0\)\s*\)",
        src,
    )
    assert m, ("P109: btn_close.clicked muss tabs.setCurrentIndex(0) "
               "auslösen (statt nur _right_stack.setCurrentIndex)")


def test_t2_old_stack_only_pattern_gone():
    """Alter Pfad btn_close → _right_stack direkt darf nicht mehr existieren."""
    src = _read("ui/main_window.py")
    bad = re.search(
        r"_detail_overlay\.btn_close\.clicked\.connect\(\s*"
        r"lambda:\s*self\._right_stack\.setCurrentIndex\(0\)\s*\)",
        src,
    )
    assert not bad, ("P109: alter X-Handler (nur _right_stack) muss "
                     "durch tabs-Switch ersetzt sein")
