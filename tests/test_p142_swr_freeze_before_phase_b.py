"""P142 (27.05.2026) — SWR-Freeze VOR Phase B nehmen statt nach.

Mike-Field-Reproduktion 27.05.2026 12:08-12:10:
- Bandsperre triggered → manueller TUNE → Live-Widget zeigt SWR 2.5
- Log-Eintrag „✓ Band 15M freigegeben — SWR 1.0" ← FALSCH
- 2. TUNE → „✓ TUNE OK — SWR 2.5" ← KORREKT (rfpower vom 1. Lauf
  schon klein, Phase B konvergiert sofort, kein Power-Drop)

Root Cause: SWR-Freeze in `_tune_stop` wurde NACH Phase B gelesen.
Phase B regelt rfpower runter → FlexRadio-Sensor clampt auf 1.0
während Power-Drop. Der echte Match-SWR aus Phase A (2.5) wurde
nur als Schwellenwert-Check verwendet, danach verworfen.

Fix Variante C (R1-empfohlen): Freeze VOR Phase B nehmen, Phase B
beeinflusst nur noch RF-Stützpunkt-Speicherung.

R1-V4-pro ORANGE-Catch: Cancel WÄHREND Phase B würde den schon
gesetzten Freeze zum Post-Check durchreichen → fälschliche Freigabe
trotz User-Abbruch. Fix: Cancel-Pfad invalidiert Freeze explizit
auf None.

Hardware-Sicherheit: bei knapp-zu-hohem SWR (z.B. 4.5) hätte der
alte Code 1.0 eingefroren → Band fälschlich freigegeben → nächster
TX auf defekter Antenne. Mit P142 bleibt 4.5 im Freeze → Band
bleibt korrekt gesperrt.

Tests:
- T1: Freeze wird VOR Phase B (vor _tune_converge_to_target) gesetzt
- T2: Alter Freeze-Code NACH Phase B (Z. 275) entfernt
- T3: User-Cancel-Pfad (token=None) setzt Freeze auf None
- T4: Cancel-während-Phase-B (Re-Entry-Sperre) setzt Freeze auf None
- T5: SWR > Limit (Phase B Skip) hält den hohen Freeze-Wert
- T6: Disconnect-Pfad (radio.ip=False) setzt Freeze auf None
- T7: P142-Kommentar im Code mit Mike-Field-Bug-Datum
- T8: Funktional Mike-Field-Szenario — Phase A 2.5, Phase B Power-Drop,
  Freeze bleibt 2.5
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest


REPO = Path(__file__).resolve().parent.parent
MW_TX_SRC = (REPO / "ui" / "mw_tx.py").read_text()


def _tune_stop_body():
    """Extrahiert den Body von `_tune_stop` aus mw_tx.py."""
    m = re.search(
        r"def _tune_stop\(self, token.*?(?=\n    def )",
        MW_TX_SRC, re.S,
    )
    assert m is not None, "_tune_stop nicht gefunden"
    return m.group(0)


# ---------------------------------------------------------------------------
# T1: Freeze wird VOR Phase B gesetzt
# ---------------------------------------------------------------------------


def test_t1_freeze_set_before_phase_b():
    """T1 (P142 Kern-Fix): _tune_last_valid_swr wird VOR
    _tune_converge_to_target gesetzt, nicht danach."""
    body = _tune_stop_body()
    pos_freeze = body.find("self._tune_last_valid_swr = swr_after_match")
    pos_converge = body.find("_tune_converge_to_target")
    assert pos_freeze > 0, (
        "P142: Freeze auf swr_after_match (Phase-A-Wert) muss existieren.")
    assert pos_converge > 0, (
        "Phase B (_tune_converge_to_target) muss noch im Code sein.")
    assert pos_freeze < pos_converge, (
        "P142: Freeze MUSS VOR Phase B kommen — sonst Sensor-Clamp-Bug.")


def test_t1b_swr_after_match_read_once():
    """T1b: swr_after_match wird einmal ermittelt und sowohl als Freeze
    als auch für Schwellenwert-Check genutzt (KISS, eine Quelle).

    P153 (28.05.): Quelle ist jetzt _compute_match_swr() (Median-Fenster)
    statt direkter radio.last_swr-Snapshot. Die P142-Kernaussage (eine
    Quelle, Freeze VOR Phase B) bleibt — nur die Lesung ist robuster.
    """
    body = _tune_stop_body()
    # swr_after_match-Ermittlung (P153: über Median-Helper)
    assert "swr_after_match = self._compute_match_swr()" in body, (
        "P153: Phase-A-Wert kommt jetzt aus _compute_match_swr (Median).")
    # Im SWR-Limit-Check (P153: mit is-None-Guard)
    assert "swr_after_match <= swr_limit" in body, (
        "Schwellenwert-Check muss swr_after_match verwenden.")
    # Als Freeze
    assert "self._tune_last_valid_swr = swr_after_match" in body, (
        "P142: Freeze muss swr_after_match nutzen (eine Quelle).")


# ---------------------------------------------------------------------------
# T2: Alter Post-Phase-B-Freeze (Z. 275) entfernt
# ---------------------------------------------------------------------------


def test_t2_old_post_phase_b_freeze_removed():
    """T2: Die alte Zeile `self._tune_last_valid_swr = self.radio.last_swr`
    (war Z. 275 NACH Phase B) existiert nicht mehr im Body.

    Pattern `_tune_last_valid_swr = self.radio.last_swr` darf nur in
    Doku-Kommentaren auftauchen, nicht als ausgeführter Code.
    """
    body = _tune_stop_body()
    # Code-only (Doku-Kommentare entfernen)
    lines = body.split("\n")
    code_lines = [
        l for l in lines
        if l.strip() and not l.strip().startswith("#")
    ]
    code_text = "\n".join(code_lines)
    assert "self._tune_last_valid_swr = self.radio.last_swr" not in code_text, (
        "P142: Alter Freeze NACH Phase B muss entfernt sein "
        "(führte zu Mike's Field-Bug mit SWR 1.0 statt 2.5).")


# ---------------------------------------------------------------------------
# T3: User-Cancel-Pfad (token=None oder kein radio.ip) setzt None
# ---------------------------------------------------------------------------


def test_t3_user_cancel_path_freeze_none():
    """T3: `else`-Pfad (token is None oder radio.ip leer) setzt
    _tune_last_valid_swr = None."""
    body = _tune_stop_body()
    # Finde den else-Block nach `if token is not None and self.radio.ip:`
    pos_main_if = body.find("if token is not None and self.radio.ip:")
    pos_else = body.find("else:", pos_main_if + 30)
    pos_next_def_or_phase = body.find("# P76-A SAFETY-Doku-Anker", pos_else)
    if pos_next_def_or_phase == -1:
        pos_next_def_or_phase = body.find("# tune_off", pos_else)
    assert 0 < pos_main_if < pos_else, (
        "Main if/else-Struktur muss erhalten sein")
    else_block = body[pos_else:pos_next_def_or_phase]
    assert "self._tune_last_valid_swr = None" in else_block, (
        "P142: User-Cancel/Disconnect-Pfad muss Freeze auf None setzen "
        "(sonst stale Wert von vorigem TUNE-Run).")


# ---------------------------------------------------------------------------
# T4: Cancel-während-Phase-B (R1-Catch) — Re-Entry-Sperre setzt None
# ---------------------------------------------------------------------------


def test_t4_cancel_during_phase_b_invalidates_freeze():
    """T4 (R1-V4-pro ORANGE-Catch): Cancel mitten in Phase B trifft die
    Re-Entry-Sperre `_tune_stop_active`. Dort muss _tune_last_valid_swr
    auf None gesetzt werden — sonst würde der schon gesetzte Phase-A-
    Freeze den Post-Check zu „freigegeben" verleiten obwohl User abbrach.

    Hardware-Sicherheit: Band MUSS gesperrt bleiben wenn User cancelt.
    """
    body = _tune_stop_body()
    # Finde Re-Entry-Sperre-Block
    pos_reentry = body.find("if getattr(self, '_tune_stop_active', False):")
    assert pos_reentry > 0, "Re-Entry-Sperre muss erhalten sein"
    # Block bis zum nächsten `self._tune_stop_active = True`
    pos_set_active = body.find("self._tune_stop_active = True", pos_reentry)
    assert pos_set_active > pos_reentry
    reentry_block = body[pos_reentry:pos_set_active]
    assert "self._tune_last_valid_swr = None" in reentry_block, (
        "P142 R1-F (Cancel-während-Phase-B): Re-Entry-Sperre muss "
        "_tune_last_valid_swr = None setzen — sonst Hardware-Risiko "
        "(falsche Freigabe trotz User-Abbruch).")


def test_t4b_cancel_pflicht_kommentar():
    """T4b: Cancel-Block hat P142-R1-F-Kommentar (Hardware-Sicherheits-
    Doku-Pflicht)."""
    body = _tune_stop_body()
    pos_reentry = body.find("if getattr(self, '_tune_stop_active', False):")
    pos_set_active = body.find("self._tune_stop_active = True", pos_reentry)
    reentry_block = body[pos_reentry:pos_set_active]
    assert "P142" in reentry_block, (
        "P142-Tag im Cancel-Block Pflicht — sonst Refactor-Falle.")


# ---------------------------------------------------------------------------
# T5: SWR > Limit (Phase B Skip) hält den hohen Freeze-Wert
# ---------------------------------------------------------------------------


def test_t5_high_swr_freeze_preserved():
    """T5: Wenn swr_after_match > swr_limit (z.B. 4.5), wird Phase B
    geskippt — der hohe Freeze-Wert bleibt erhalten, NICHT überschrieben.

    Mike-Hardware-Sicherheits-Szenario: defekte Antenne, Phase A misst
    4.5, Limit ist 3.0 → Band bleibt gesperrt. Mit Phase-B-Bug hätte
    der alte Code 1.0 eingefroren → falsche Freigabe.
    """
    body = _tune_stop_body()
    # Freeze ist VOR Phase B → wird in keinem Pfad überschrieben.
    # Phase-B-Skip-Branch (else nach Limit-Check) darf _tune_last_valid_swr
    # nicht setzen. P153: Limit-Check hat jetzt is-None-Guard.
    pos_freeze = body.find("self._tune_last_valid_swr = swr_after_match")
    pos_limit_check = body.find("swr_after_match is not None and swr_after_match <= swr_limit")
    assert 0 < pos_freeze < pos_limit_check, (
        "P142: Freeze MUSS VOR der Phase-B-Limit-Verzweigung kommen.")


# ---------------------------------------------------------------------------
# T6: Disconnect-Pfad setzt Freeze auf None
# ---------------------------------------------------------------------------


def test_t6_disconnect_freeze_none():
    """T6: Wenn radio.ip leer ist (Disconnect mitten in TUNE), läuft
    der else-Branch — Freeze auf None statt stale-Wert."""
    body = _tune_stop_body()
    # Der else-Branch nach `if token is not None and self.radio.ip:`
    # setzt _tune_last_valid_swr = None (siehe T3 — gleicher Block)
    pos_main_if = body.find("if token is not None and self.radio.ip:")
    pos_else = body.find("else:", pos_main_if + 30)
    # Block zwischen else und Z. 275 (alter Freeze-Code, jetzt weg)
    pos_block_end = body.find("# P76-A SAFETY", pos_else)
    if pos_block_end == -1:
        pos_block_end = body.find("# tune_off", pos_else)
    else_block = body[pos_else:pos_block_end]
    assert "self._tune_last_valid_swr = None" in else_block


# ---------------------------------------------------------------------------
# T7: P142-Kommentar mit Mike-Field-Bug-Doku
# ---------------------------------------------------------------------------


def test_t7_p142_comment_with_field_bug():
    """T7: P142-Kommentar referenziert Mike-Field-Bug 27.05.2026
    und erklärt Phase-B-Power-Drop-Mechanik (Doku-Anker für zukünftige
    Refactorings)."""
    body = _tune_stop_body()
    assert "P142" in body
    assert "27.05.2026" in body, (
        "P142: Datum des Field-Bugs muss dokumentiert sein.")
    assert "Phase B" in body or "Phase-B" in body, (
        "P142: Phase-B-Power-Drop-Erklärung muss im Kommentar stehen.")


# ---------------------------------------------------------------------------
# T8: Funktional via Mock (vereinfacht) — Phase A 2.5, Freeze ist 2.5
# ---------------------------------------------------------------------------


def test_t8_mike_field_scenario_freeze_keeps_phase_a():
    """T8: Mike-Field-Szenario simuliert via Source-Inspektion.

    Vorbedingung: `swr_after_match = self.radio.last_swr` (Z. ~255)
    liest den echten Phase-A-Wert (z.B. 2.5).
    Folge: `_tune_last_valid_swr` wird mit 2.5 gesetzt.
    Phase B läuft ggf., aber Freeze-Wert bleibt 2.5 weil schon gesetzt.
    Post-Check liest 2.5 → Meldung „freigegeben — SWR 2.5".

    Test-Strategie: prüfe dass die Variable die im Limit-Check und im
    Freeze ist IDENTISCH (swr_after_match), also keine zweite Lesung
    der `radio.last_swr` für den Freeze stattfindet.
    """
    body = _tune_stop_body()
    # P153 (28.05.): swr_after_match kommt aus _compute_match_swr() (Median),
    # genau EINE Ermittlung, sowohl Freeze als auch Limit-Check.
    assignments = [
        l for l in body.split("\n")
        if l.strip().startswith("swr_after_match = self._compute_match_swr()")
    ]
    assert len(assignments) == 1, (
        f"P153: swr_after_match darf nur EINMAL ermittelt werden, "
        f"gefunden: {len(assignments)} ({assignments})")
    # Und _tune_last_valid_swr wird mit dieser Variable gesetzt
    assert "self._tune_last_valid_swr = swr_after_match" in body, (
        "P142: Freeze muss swr_after_match-Variable verwenden (eine Quelle).")


# ---------------------------------------------------------------------------
# T9: Reihenfolge Cancel-Pfad ist sauber (Hardware-Safety)
# ---------------------------------------------------------------------------


def test_t9_cancel_path_order():
    """T9: Im Re-Entry-Cancel-Block: erst _tune_convergence_cancelled = True,
    dann _tune_last_valid_swr = None, dann return.
    Reihenfolge ist nicht zwingend kritisch (atomar in einer Funktion),
    aber dokumentiert die Absicht."""
    body = _tune_stop_body()
    pos_reentry = body.find("if getattr(self, '_tune_stop_active', False):")
    pos_return = body.find("return", pos_reentry)
    block = body[pos_reentry:pos_return]
    assert "_tune_convergence_cancelled = True" in block
    assert "_tune_last_valid_swr = None" in block
