"""P140 (26.05.2026) — Cooldown-Trigger an optischen ✓-Zeitpunkt umhängen.

Spec-Korrektur zu P138 (gleicher Tag): Der _recently_completed_qsos-
Cooldown wurde faelschlich in _on_qso_complete (= interner RR73-Send-
Trigger) gesetzt. Folge: 73 der Gegenstation das ZWISCHEN RR73-Send
und optischem ✓ ankam wurde geblockt.

Mike-Field-Bug 26.05. (5P1KZX/IQ5VK/OE4AHG):
- 14:32:45 -> Gesendet 5P1KZX DA1MHH RR73  -- qso_complete (intern)
- 14:33:15 -> Gegenstation-73 zwischendrin -- VOR optischem ✓
- 14:33:30 -> optisches ✓ erscheint        -- qso_confirmed_visual

Vor P140: Cooldown 14:32:45 gesetzt -> Gegenstation-73 14:33:15
geblockt -> NIE im Log gesehen.

Nach P140: Cooldown 14:33:30 gesetzt -> Gegenstation-73 14:33:15
kommt durch -> Mike sieht Bestaetigung im Log.

Diese Tests pruefen die SET-Stellen:
- T1: _on_qso_complete setzt KEINEN Cooldown mehr
- T2: _on_qso_confirmed_visual setzt Cooldown (✓-Zeitpunkt)
- T3: _on_qso_timeout setzt Cooldown (Mike-Spec defensiv)
- T4: Reihenfolge: Cooldown wird NACH add_qso_complete gesetzt
- T5: their_call leer -> kein Eintrag (defensiv)
- T6: Auto-Hunt-Cooldown (_recent_qso aus P61) unabhaengig

Filter-Logik selbst ist in test_p138_*.py geprueft.
"""

from __future__ import annotations

import time
from pathlib import Path


# ---------------------------------------------------------------------------
# T1-T3: Verifikation der Set-Stellen durch Source-Inspektion
# ---------------------------------------------------------------------------

MW_QSO_SRC = (Path(__file__).resolve().parent.parent
              / "ui" / "mw_qso.py").read_text()


def test_t1_on_qso_complete_does_not_set_cooldown():
    """T1: _on_qso_complete enthaelt KEINE _recently_completed_qsos[*]=
    Zuweisung mehr (P140 entfernt).

    Wir grep'en die Methode _on_qso_complete (start bis naechste def).
    Innerhalb darf kein Set-Pattern vorkommen.
    """
    import re
    m = re.search(
        r"def _on_qso_complete\(self,.*?(?=\n    def )",
        MW_QSO_SRC, re.S)
    assert m is not None, "Methode _on_qso_complete nicht gefunden"
    body = m.group(0)
    # P140: das Set-Pattern soll WEG sein
    assert "_recently_completed_qsos[qso_data.their_call]" not in body, (
        "P140: _on_qso_complete darf den Cooldown NICHT mehr setzen "
        "-- gehoert in _on_qso_confirmed_visual.")


def test_t2_on_qso_confirmed_visual_sets_cooldown():
    """T2: _on_qso_confirmed_visual enthaelt das Set-Pattern (P140 added)."""
    import re
    m = re.search(
        r"def _on_qso_confirmed_visual\(self,.*?(?=\n    @?Slot|\n    def )",
        MW_QSO_SRC, re.S)
    assert m is not None, "Methode _on_qso_confirmed_visual nicht gefunden"
    body = m.group(0)
    assert "_recently_completed_qsos[qso_data.their_call]" in body, (
        "P140: _on_qso_confirmed_visual MUSS Cooldown setzen "
        "(✓-Zeitpunkt).")
    assert "monotonic()" in body, (
        "P140: Cooldown-Stempel via time.monotonic() (nicht time.time())")


def test_t3_on_qso_timeout_sets_cooldown():
    """T3: _on_qso_timeout enthaelt das Set-Pattern (P140 defensiv)."""
    import re
    m = re.search(
        r"def _on_qso_timeout\(self,.*?(?=\n    @?Slot|\n    def )",
        MW_QSO_SRC, re.S)
    assert m is not None, "Methode _on_qso_timeout nicht gefunden"
    body = m.group(0)
    assert "_recently_completed_qsos[their_call]" in body, (
        "P140: _on_qso_timeout MUSS Cooldown setzen (Mike-Spec "
        "'beendet ist beendet' auch nach ✗).")


# ---------------------------------------------------------------------------
# T4: Reihenfolge -- Cooldown NACH add_qso_complete
# ---------------------------------------------------------------------------


def test_t4_visual_cooldown_after_add_qso_complete():
    """T4: In _on_qso_confirmed_visual kommt der Cooldown-Set NACH
    add_qso_complete -- semantisch passend (erst ✓-Anzeige, dann
    Block-Filter aktivieren).
    """
    import re
    m = re.search(
        r"def _on_qso_confirmed_visual\(self,.*?(?=\n    @?Slot|\n    def )",
        MW_QSO_SRC, re.S)
    body = m.group(0)
    pos_add = body.find("add_qso_complete(qso_data.their_call)")
    pos_set = body.find("_recently_completed_qsos[qso_data.their_call]")
    assert pos_add > 0, "add_qso_complete fehlt in _on_qso_confirmed_visual"
    assert pos_set > 0, "Cooldown-Set fehlt in _on_qso_confirmed_visual"
    assert pos_set > pos_add, (
        "P140: Cooldown muss NACH add_qso_complete kommen "
        "(erst optisches ✓, dann Block-Filter).")


def test_t4b_timeout_cooldown_after_add_timeout():
    """T4b: In _on_qso_timeout kommt der Cooldown-Set NACH add_timeout."""
    import re
    m = re.search(
        r"def _on_qso_timeout\(self,.*?(?=\n    @?Slot|\n    def )",
        MW_QSO_SRC, re.S)
    body = m.group(0)
    pos_add = body.find("add_timeout(their_call)")
    pos_set = body.find("_recently_completed_qsos[their_call]")
    assert pos_add > 0 and pos_set > 0
    assert pos_set > pos_add, (
        "P140: Cooldown muss NACH add_timeout kommen "
        "(erst optisches ✗, dann Block-Filter).")


# ---------------------------------------------------------------------------
# T5: Defensive `if call:` Check vorhanden
# ---------------------------------------------------------------------------


def test_t5_defensive_check_visual():
    """T5: _on_qso_confirmed_visual hat defensive `if qso_data.their_call:`
    vor dem Set-Pattern -- verhindert leeren-String-Eintrag."""
    import re
    m = re.search(
        r"def _on_qso_confirmed_visual\(self,.*?(?=\n    @?Slot|\n    def )",
        MW_QSO_SRC, re.S)
    body = m.group(0)
    # Block zwischen `if qso_data.their_call:` und set-pattern darf nicht
    # > 200 Zeichen sein (sonst ist der Guard woanders)
    guard_idx = body.find("if qso_data.their_call:")
    set_idx = body.find("_recently_completed_qsos[qso_data.their_call]")
    assert guard_idx > 0, "Defensive Guard fehlt in _on_qso_confirmed_visual"
    assert 0 < (set_idx - guard_idx) < 200, (
        "Defensive Guard muss direkt vor Set-Pattern stehen.")


def test_t5b_defensive_check_timeout():
    """T5b: _on_qso_timeout hat defensive `if their_call:` vor Set."""
    import re
    m = re.search(
        r"def _on_qso_timeout\(self,.*?(?=\n    @?Slot|\n    def )",
        MW_QSO_SRC, re.S)
    body = m.group(0)
    guard_idx = body.find("if their_call:")
    set_idx = body.find("_recently_completed_qsos[their_call]")
    assert guard_idx > 0, "Defensive Guard fehlt in _on_qso_timeout"
    assert 0 < (set_idx - guard_idx) < 200


# ---------------------------------------------------------------------------
# T6: Auto-Hunt-Cooldown ist UNABHAENGIG (R1-F1-Klaerung)
# ---------------------------------------------------------------------------


def test_t6_autohunt_cooldown_independent():
    """T6: core/auto_hunt.py nutzt eigenen Cooldown `_recent_qso`
    (P61, mark_pick) -- NICHT _recently_completed_qsos.

    Damit ist Auto-Hunt-Re-Pick-Schutz unabhaengig von dieser P140-
    Aenderung. R1 hatte Sorge dass Auto-Hunt zwischen qso_complete
    und qso_confirmed_visual dieselbe Station erneut pickt -- diese
    Sorge ist unbegruendet weil Auto-Hunt seine eigene Skip-Liste hat.
    """
    src = (Path(__file__).resolve().parent.parent
           / "core" / "auto_hunt.py").read_text()
    # Auto-Hunt's eigener Cooldown-Mechanismus
    assert "_recent_qso" in src, (
        "Auto-Hunt muss eigenen Cooldown _recent_qso haben (P61).")
    assert "mark_pick" in src, (
        "Auto-Hunt muss mark_pick() haben (setzt _recent_qso).")
    # Auto-Hunt darf den UI-Cooldown nicht referenzieren
    assert "_recently_completed_qsos" not in src, (
        "Auto-Hunt darf nicht von _recently_completed_qsos abhaengen "
        "-- eigener Skip-Mechanismus.")


# ---------------------------------------------------------------------------
# T7: P140-Kommentar im Code dokumentiert die Aenderung
# ---------------------------------------------------------------------------


def test_t7_p140_comment_in_qso_complete():
    """T7: _on_qso_complete hat P140-Kommentar der erklaert WARUM
    der Cooldown entfernt wurde (Mike-Field-Bug-Doku)."""
    import re
    m = re.search(
        r"def _on_qso_complete\(self,.*?(?=\n    def )",
        MW_QSO_SRC, re.S)
    body = m.group(0)
    assert "P140" in body, (
        "P140-Kommentar fehlt in _on_qso_complete -- Doku-Pflicht.")
    assert "_on_qso_confirmed_visual" in body, (
        "P140-Kommentar muss neuen Set-Ort referenzieren.")
