"""P141 (27.05.2026) — Sterne-Empfangsqualität im Diversity-Pfad
symmetrisch zu Normal-Mode.

Mike-Field-Bug 26.05. 17:15: Diversity Standard 15m FT8, 14 Stationen
sichtbar mit SNR -16..-22 (Median im Top-Half ~-18/-19). Anzeige
"Lokale Empfangsqualitaet: ★☆☆☆☆" (1 Sternchen) statt rechnerisch
3-4★ nach P120-Schwellen.

Root Cause: `compute_local_conditions` + `update_local_conditions`
wurde nur in _handle_normal_mode (Z. 451-456) gerufen, nicht in
_handle_diversity_operate. Anzeige hing auf Init-Default 1★.

Fix: 2-Zeilen-Aufruf am Ende von _handle_diversity_operate (analog
Normal-Mode-Stelle, vor _emit_map_snapshot_if_open).

Pattern-Klasse: mode-aware Symmetrie-Fehler (gleicher Bug-Typ wie
P135 Decode-Count). DeepSeek-R1 hat empfohlen ein Pattern-Check-
Skript zu bauen — separates Followup-Ticket.
"""

from __future__ import annotations

from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# T1: Source-Inspektion — _handle_diversity_operate ruft Sterne-Update
# ---------------------------------------------------------------------------

MW_CYCLE_SRC = (Path(__file__).resolve().parent.parent
                / "ui" / "mw_cycle.py").read_text()


def test_t1_diversity_operate_calls_compute_local_conditions():
    """T1: _handle_diversity_operate enthaelt compute_local_conditions
    auf _diversity_stations (P141 Variante A)."""
    import re
    m = re.search(
        r"def _handle_diversity_operate\(self,.*?(?=\n    def )",
        MW_CYCLE_SRC, re.S)
    assert m is not None, "_handle_diversity_operate nicht gefunden"
    body = m.group(0)
    assert "compute_local_conditions(self._diversity_stations)" in body, (
        "P141: _handle_diversity_operate MUSS "
        "compute_local_conditions(self._diversity_stations) rufen "
        "(symmetrisch zu Normal-Mode).")
    assert "update_local_conditions" in body, (
        "P141: _handle_diversity_operate MUSS "
        "control_panel.update_local_conditions rufen.")


# ---------------------------------------------------------------------------
# T2: Symmetrie-Test — beide Handler rufen die Sterne-Funktionen
# ---------------------------------------------------------------------------


def test_t2_both_handlers_have_local_conditions_calls():
    """T2: Symmetrie zwischen _handle_normal_mode und
    _handle_diversity_operate -- beide MUESSEN
    compute_local_conditions + update_local_conditions rufen.

    Pattern-Klasse mode-aware Symmetrie -- wenn neuer rx_mode-Pfad
    eingebaut wird muss er das gleiche tun.
    """
    import re
    for handler in ("_handle_normal_mode", "_handle_diversity_operate"):
        m = re.search(
            rf"def {handler}\(self,.*?(?=\n    def )",
            MW_CYCLE_SRC, re.S)
        assert m is not None, f"{handler} nicht gefunden"
        body = m.group(0)
        assert "compute_local_conditions" in body, (
            f"Pattern-Klasse mode-aware: {handler} MUSS "
            "compute_local_conditions rufen.")
        assert "update_local_conditions" in body, (
            f"Pattern-Klasse mode-aware: {handler} MUSS "
            "update_local_conditions rufen.")


# ---------------------------------------------------------------------------
# T3: Reihenfolge — vor _emit_map_snapshot_if_open
# ---------------------------------------------------------------------------


def test_t3_diversity_call_before_emit_map_snapshot():
    """T3: In _handle_diversity_operate kommt der Sterne-Update VOR
    _emit_map_snapshot_if_open() -- analog Normal-Mode-Reihenfolge.
    """
    import re
    m = re.search(
        r"def _handle_diversity_operate\(self,.*?(?=\n    def )",
        MW_CYCLE_SRC, re.S)
    body = m.group(0)
    pos_update = body.find("update_local_conditions")
    pos_emit = body.find("_emit_map_snapshot_if_open()")
    assert pos_update > 0 and pos_emit > 0
    assert pos_update < pos_emit, (
        "P141: update_local_conditions muss VOR "
        "_emit_map_snapshot_if_open() kommen (semantische Symmetrie "
        "zu Normal-Mode-Pfad).")


# ---------------------------------------------------------------------------
# T4: Funktionaler Test — Mike-Field-Bug-Szenario
# ---------------------------------------------------------------------------


class _FakeMsg:
    """Stub fuer Decoder-Message mit SNR-Attribut."""
    def __init__(self, snr: int):
        self.snr = snr


def test_t4_mike_field_scenario_14_stations_correct_stars():
    """T4: Mike-Field-Bug-Reproduktion. 14 Stationen bei SNR -16..-22
    (Median Top-Half ~-18) MUSS nach P120-Schwellen 4★ (nicht 1★)
    zurueckgeben.

    Vor P141 wurde diese Berechnung im Diversity-Pfad nie gemacht
    -> Anzeige hing auf 1★. Nach P141 wird sie pro Slot gemacht.
    """
    from ui.mw_cycle import compute_local_conditions

    # Mike-Field-Daten: 14 Stationen, SNR-Verteilung wie im Screenshot
    snr_values = [-16, -16, -17, -17, -17, -18, -18, -19, -19, -20,
                  -20, -21, -22, -22]
    stations = {f"CALL{i}": _FakeMsg(s)
                for i, s in enumerate(snr_values)}

    score, n_st, median = compute_local_conditions(stations)

    assert n_st == 14, f"n_st erwartet 14, ist {n_st}"
    # Top-Half = erste 7 SNRs (sortiert absteigend): -16,-16,-17,-17,-17,-18,-18
    # Median Top-Half = mittlerer Index 7//2=3 -> -17
    assert median == -17, f"Median erwartet -17, ist {median}"
    # P120: median > -18 -> 4★
    assert score == 4, (
        f"P141 + P120: Score muss 4★ sein bei Median {median}, "
        f"ist aber {score}. Mike-Field-Bug-Wiederholung.")


def test_t4b_empty_diversity_stations_returns_one_star():
    """T4b: Leeres _diversity_stations Dict -> 1★ (Default)."""
    from ui.mw_cycle import compute_local_conditions
    score, n_st, median = compute_local_conditions({})
    assert (score, n_st) == (1, 0)


# ---------------------------------------------------------------------------
# T5: P141-Kommentar dokumentiert die Aenderung
# ---------------------------------------------------------------------------


def test_t5_p141_comment_in_diversity_handler():
    """T5: _handle_diversity_operate enthaelt P141-Kommentar mit
    Mike-Field-Bug-Datum (Doku-Pflicht, damit zukuenftige Claude-
    Instanz versteht WARUM der Aufruf da ist)."""
    import re
    m = re.search(
        r"def _handle_diversity_operate\(self,.*?(?=\n    def )",
        MW_CYCLE_SRC, re.S)
    body = m.group(0)
    assert "P141" in body, (
        "P141-Kommentar fehlt in _handle_diversity_operate -- "
        "Doku-Pflicht.")


# ---------------------------------------------------------------------------
# T6: Aufruf-Argument ist _diversity_stations (NICHT _normal_stations)
# ---------------------------------------------------------------------------


def test_t6_diversity_handler_uses_diversity_stations():
    """T6: Im Diversity-Pfad wird _diversity_stations uebergeben,
    NICHT _normal_stations (sonst Anzeige verzerrt bei Mode-Wechsel)."""
    import re
    m = re.search(
        r"def _handle_diversity_operate\(self,.*?(?=\n    def )",
        MW_CYCLE_SRC, re.S)
    body = m.group(0)
    # Variante A: hartcodiert _diversity_stations
    assert "compute_local_conditions(self._diversity_stations)" in body
    # NICHT (defensive Variante B with if/else)
    # Diese Pruefung schuetzt vor unbeabsichtigtem Mix
    p141_block_start = body.find("# P141")
    p141_block_end = body.find("_emit_map_snapshot_if_open()", p141_block_start)
    p141_block = body[p141_block_start:p141_block_end]
    assert "_normal_stations" not in p141_block, (
        "P141-Block darf nicht _normal_stations referenzieren "
        "(Variante A KISS, R1-V4-pro F2 GELB).")
