"""P55 (15.05.2026, v0.97.29 → v0.97.30) — Easter-Egg + Diversity-CQ-Cleanup.

Mike-Spec 15.05.2026: „In Diversity soll es nur OMNI CQ geben, keinen
normalen CQ auch nicht versteckt. Es gibt auch keine Easter-Egg-Funktion
mehr. Normal ist so als wenn es ein ganz normales FT8-Programm wäre."

Voller V1→V2→R1→V3-Workflow mit DeepSeek-V4-pro. R1-V4-pro fand 5
Findings, alle 5 angenommen (Halluzinations-Rate 0/5). Bug F1 sehr stark:
`core/auto_hunt.py` Doc-String-Verweise auf `easter_egg_off` waren in V2
nicht in der Datei-Liste — V4-pro hat das gefunden.

Diese Test-Suite ist Regressions-Schutz auf Source-Level (Pattern wie
P53 T9/T10/T13 — grep auf .py-Datei statt funktionalem Test).

HINWEIS: Diese Tests sind symptomatisch (rein Source-grep). Wenn künftig
ein legitimes Feature den Identifier 'easter_egg' verwendet (sehr
unwahrscheinlich, war historisches Konzept), müssen die Patterns hier
nachjustiert werden. Bewusst KISS gegen Regression-Schutz.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def _strip_comments(text: str) -> str:
    """Entferne reine `#`-Kommentar-Zeilen — historische Doku-Kommentare
    sind erlaubt (AC1 R1-F3 präzisiert: nur reine Doku-Kommentare OK,
    kein auskommentierter Code, keine TODO-Notizen).

    Aktuelle Definition (KISS): jede Zeile die nach lstrip mit `#` beginnt.
    """
    lines = []
    for line in text.split("\n"):
        if line.lstrip().startswith("#"):
            continue
        lines.append(line)
    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────
# T1: AC1 — kein easter_egg-Code in ui/ core/ radio/ (rekursiv)
# ─────────────────────────────────────────────────────────────────────

def test_t1_no_easter_egg_in_code(app):
    """Rekursive grep über alle .py in ui/, core/, radio/.

    Reine `#`-Doku-Kommentare die Historie erklären sind OK; ansonsten
    KEIN Auftreten von `easter_egg` als Identifier (auch nicht in
    Doc-Strings) — Doc-Strings sind keine `#`-Kommentare und werden
    von _strip_comments nicht entfernt.
    """
    bad = []
    for subdir in ("ui", "core", "radio"):
        for py in (ROOT / subdir).rglob("*.py"):
            if "__pycache__" in py.parts:
                continue
            text = py.read_text()
            stripped = _strip_comments(text)
            if "easter_egg" in stripped:
                bad.append(py.relative_to(ROOT))
    assert not bad, f"Easter-Egg-Code-Reste in: {bad}"


# ─────────────────────────────────────────────────────────────────────
# T2: AC2 — ControlPanel._omni_active gelöscht
# ─────────────────────────────────────────────────────────────────────

def test_t2_control_panel_no_omni_active(app):
    src = (ROOT / "ui" / "control_panel.py").read_text()
    assert "_omni_active" not in src, \
        "P55: ControlPanel._omni_active muss vollständig entfernt sein"


# ─────────────────────────────────────────────────────────────────────
# T3: AC4 — _update_button_visibility ohne Override-Branch
# ─────────────────────────────────────────────────────────────────────

def test_t3_update_button_visibility_simple(app):
    """_update_button_visibility ist 2-Wege ohne _easter_egg_active."""
    src = (ROOT / "ui" / "main_window.py").read_text()
    # Methode existiert
    assert "def _update_button_visibility" in src
    # Kein _easter_egg_active drin (würde in Override-Branch sein)
    assert "_easter_egg_active" not in src
    # Kein "show_power_buttons = ... or" — V2 hatte das Pattern,
    # sauber jetzt: nur is_diversity entscheidet
    assert "show_power_buttons = is_diversity or" not in src


# ─────────────────────────────────────────────────────────────────────
# T4: AC5 — Version-Label ohne Click-Handler + ohne PointingHandCursor
# ─────────────────────────────────────────────────────────────────────

def test_t4_version_label_no_click_handler(app):
    """Version-Label hat kein mousePressEvent und keinen PointingHandCursor."""
    src = (ROOT / "ui" / "control_panel.py").read_text()
    assert "_version_label.mousePressEvent" not in src, \
        "P55: Version-Label-Click-Handler muss entfernt sein"
    assert "_version_label.setCursor" not in src, \
        "P55: PointingHandCursor am Version-Label muss entfernt sein"


# ─────────────────────────────────────────────────────────────────────
# T5: AC6 — Kein easter_egg_toggle_clicked-Signal mehr
# ─────────────────────────────────────────────────────────────────────

def test_t5_no_easter_egg_signal(app):
    """easter_egg_toggle_clicked-Signal in ControlPanel raus."""
    src = (ROOT / "ui" / "control_panel.py").read_text()
    assert "easter_egg_toggle_clicked" not in src, \
        "P55: easter_egg_toggle_clicked-Signal muss entfernt sein"


# ─────────────────────────────────────────────────────────────────────
# T6: AC9 — core/auto_hunt.py Doc-Strings bereinigt (R1-F1)
# ─────────────────────────────────────────────────────────────────────

def test_t6_auto_hunt_docstrings_clean(app):
    """core/auto_hunt.py Doc-Strings ohne easter_egg-Verweise.

    R1-V4-pro-F1 hatte in V2 entdeckt dass auto_hunt.py 3 Doc-String-
    Verweise auf easter_egg_off in Reason-Listen hat — Datei war in
    V2-Datei-Liste vergessen.
    """
    src = (ROOT / "core" / "auto_hunt.py").read_text()
    assert "easter_egg" not in src, \
        "P55: core/auto_hunt.py darf kein easter_egg mehr enthalten"
