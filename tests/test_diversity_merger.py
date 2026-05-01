"""Tests fuer core/diversity_merger.py — DiversityMerger Fusionslogik.

Prueft:
- A1+A2 ohne Duplikat: beide vorhanden mit korrekten Antenna-Labels
- Duplikat A1 staerker: antenna='A1>2', SNR-Felder korrekt
- Duplikat A2 staerker: antenna='A2>1', SNR-Felder korrekt
- Timeout-Pfad A1 only: _do_merge() mit nur A1-Ergebnissen
- Timeout-Pfad A2 only: _do_merge() mit nur A2-Ergebnissen
- Reset loescht Zustand (kein Emit nach Reset)
- Kein Emit bei leerem Merge (beide Decoder geben [])
- Signal merged_decoded emittiert korrekte Liste
- Whitespace-Normalisierung im Key (raw mit Leerzeichen)
"""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication

from core.diversity_merger import DiversityMerger


def _app():
    return QApplication.instance() or QApplication([])


class _Msg:
    """Minimales FT8Message-Fake-Objekt."""

    def __init__(self, raw: str, snr: int):
        self.raw = raw
        self.snr = snr
        self.antenna: str = ""
        self._snr_a1 = None
        self._snr_a2 = None


# ── Hilfsfunktion ─────────────────────────────────────────────────────────────

def _capture(merger: DiversityMerger) -> list:
    """Verbindet Signal, fuehrt Merge aus und gibt Ergebnis zurueck."""
    captured = []
    merger.merged_decoded.connect(lambda msgs: captured.extend(msgs))
    return captured


# ── Tests ─────────────────────────────────────────────────────────────────────

def test_no_duplicate_both_antennas():
    """A1+A2 ohne Duplikat: beide Nachrichten in Ergebnis, Labels A1/A2."""
    _app()
    merger = DiversityMerger()
    captured = _capture(merger)

    msg_a = _Msg("DA1MHH DL1ABC JO31", snr=-10)
    msg_b = _Msg("DK5PD DA2XX JO52", snr=-15)

    merger.on_decoder_a_done([msg_a])
    merger.on_decoder_b_done([msg_b])

    assert len(captured) == 2
    by_raw = {m.raw: m for m in captured}
    assert by_raw["DA1MHH DL1ABC JO31"].antenna == "A1"
    assert by_raw["DK5PD DA2XX JO52"].antenna == "A2"


def test_duplicate_a1_stronger():
    """Duplikat: A1 hat hoeheren SNR → antenna='A1>2', _snr_a1 und _snr_a2 gesetzt."""
    _app()
    merger = DiversityMerger()
    captured = _capture(merger)

    msg_a = _Msg("CQ DA1MHH JO31", snr=-5)
    msg_b = _Msg("CQ DA1MHH JO31", snr=-12)

    merger.on_decoder_a_done([msg_a])
    merger.on_decoder_b_done([msg_b])

    assert len(captured) == 1
    msg = captured[0]
    assert msg.antenna == "A1>2"
    assert msg.snr == -5
    assert msg._snr_a1 == -5
    assert msg._snr_a2 == -12


def test_duplicate_a2_stronger():
    """Duplikat: A2 hat hoeheren SNR → antenna='A2>1', _snr_a1 und _snr_a2 gesetzt."""
    _app()
    merger = DiversityMerger()
    captured = _capture(merger)

    msg_a = _Msg("CQ DA1MHH JO31", snr=-15)
    msg_b = _Msg("CQ DA1MHH JO31", snr=-3)

    merger.on_decoder_a_done([msg_a])
    merger.on_decoder_b_done([msg_b])

    assert len(captured) == 1
    msg = captured[0]
    assert msg.antenna == "A2>1"
    assert msg.snr == -3
    assert msg._snr_a1 == -15
    assert msg._snr_a2 == -3


def test_timeout_path_a1_only():
    """Timeout-Pfad: nur A1-Ergebnisse (B haengt) → Merge mit A1-only."""
    _app()
    merger = DiversityMerger()
    captured = _capture(merger)

    msg_a = _Msg("CQ DX DA1MHH", snr=-8)
    merger.on_decoder_a_done([msg_a])
    # Timeout simulieren: _do_merge direkt aufrufen (b bleibt None)
    merger._do_merge()

    assert len(captured) == 1
    assert captured[0].antenna == "A1"
    assert captured[0].snr == -8


def test_timeout_path_a2_only():
    """Timeout-Pfad: nur A2-Ergebnisse (A haengt) → Merge mit A2-only."""
    _app()
    merger = DiversityMerger()
    captured = _capture(merger)

    msg_b = _Msg("DX5ABC DA1MHH RR73", snr=-20)
    merger.on_decoder_b_done([msg_b])
    merger._do_merge()

    assert len(captured) == 1
    assert captured[0].antenna == "A2"
    assert captured[0].snr == -20


def test_no_emit_when_both_empty():
    """Beide Decoder geben [] → kein merged_decoded-Emit (result ist leer)."""
    _app()
    merger = DiversityMerger()
    captured = _capture(merger)

    merger.on_decoder_a_done([])
    merger.on_decoder_b_done([])

    assert captured == [], "Signal darf bei leerem Merge NICHT emittieren"


def test_reset_clears_state():
    """reset() loescht pending-Zustand; nachfolgender Merge liefert leeres Ergebnis."""
    _app()
    merger = DiversityMerger()
    captured = _capture(merger)

    msg_a = _Msg("CQ DA1MHH JO31", snr=-10)
    merger.on_decoder_a_done([msg_a])

    # Reset vor B-Ergebnis: A-State weg
    merger.reset()

    # Direkt _do_merge aufrufen — _results_a + _results_b sind None nach Reset
    merger._do_merge()
    assert captured == [], "Nach reset() darf kein Emit kommen"


def test_reset_stops_timer():
    """reset() stoppt laufenden Timer."""
    _app()
    merger = DiversityMerger()

    msg_a = _Msg("CQ DA1MHH JO31", snr=-10)
    merger.on_decoder_a_done([msg_a])
    assert merger._timer.isActive(), "Timer muss nach on_decoder_a_done laufen"

    merger.reset()
    assert not merger._timer.isActive(), "Timer muss nach reset() gestoppt sein"


def test_whitespace_normalization():
    """Doppel-Leerzeichen im raw-String werden korrekt normalisiert (Key-Matching)."""
    _app()
    merger = DiversityMerger()
    captured = _capture(merger)

    # A1 hat doppeltes Leerzeichen, A2 single — muss als Duplikat erkannt werden
    msg_a = _Msg("CQ  DA1MHH  JO31", snr=-10)   # extra spaces
    msg_b = _Msg("CQ DA1MHH JO31", snr=-5)

    merger.on_decoder_a_done([msg_a])
    merger.on_decoder_b_done([msg_b])

    assert len(captured) == 1, (
        f"Doppel-Leerzeichen im raw muss als Duplikat erkannt werden, "
        f"stattdessen {len(captured)} Eintraege"
    )
    # A2 ist staerker (-5 > -10)
    assert captured[0].antenna == "A2>1"


def test_signal_emits_full_list():
    """merged_decoded emittiert die vollstaendige fusionierte Liste in einem Emit."""
    _app()
    merger = DiversityMerger()

    emit_count = [0]
    results = []

    def _on_merged(msgs):
        emit_count[0] += 1
        results.extend(msgs)

    merger.merged_decoded.connect(_on_merged)

    msgs_a = [_Msg(f"MSG A{i} JO31", snr=-i) for i in range(3)]
    msgs_b = [_Msg(f"MSG B{i} JO52", snr=-i - 5) for i in range(2)]

    merger.on_decoder_a_done(msgs_a)
    merger.on_decoder_b_done(msgs_b)

    assert emit_count[0] == 1, "Signal muss genau 1x emittieren (nicht pro Nachricht)"
    assert len(results) == 5, f"3 A1 + 2 A2 = 5 Nachrichten, aber {len(results)}"
