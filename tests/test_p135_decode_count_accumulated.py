"""P135 (26.05.2026) — Decode-Statusbar zeigt akkumulierte Anzahl.

Mike-Field-Bug 26.05. (Screenshots): Decode-Anzeige sprang zwischen
„39 Stationen" und „—" je nach Slot-Parität. Reproduzierbar bei 15m
DX-Mode mit ANT2 (eine Slot-Parität dekodiert null Messages).

Root Cause: ui/mw_cycle.py:88 setzte per-Slot rohe Decode-Anzahl.
Akkumulator-Aktualisierung in _handle_diversity_operate (Z.387) lief
nur `if messages` → bei leerem Slot blieb 0.

V3 (R1-Catch): mode-aware akkumulierte Anzeige fuer diversity + normal,
ELSE-Branch behaelt per-Slot-Anzahl fuer dx_tune (kein Akkumulator).

ACs:
- AC1: diversity-Pfad nutzt len(_diversity_stations)
- AC2: normal-Pfad nutzt len(_normal_stations)
- AC3: else-Branch (dx_tune) behaelt len(messages)-Fallback
- AC4: P135-Marker im Kommentar
- AC5: KEIN "len(messages) if messages else 0" mehr als einziger Aufruf
"""

from __future__ import annotations

import ast
from pathlib import Path


MW_CYCLE = Path(__file__).parent.parent / "ui" / "mw_cycle.py"


def _on_cycle_decoded_body() -> str:
    """Source-Slice des _on_cycle_decoded-Anfangs (inkl. Kommentare)."""
    src = MW_CYCLE.read_text()
    pos = src.find("def _on_cycle_decoded(self, messages: list):")
    assert pos > 0, "_on_cycle_decoded nicht gefunden"
    # Bis zur naechsten Funktion lesen
    end = src.find("\n    def ", pos + 1)
    if end == -1:
        end = pos + 3000
    return src[pos:end]


def test_t1_diversity_uses_diversity_stations():
    """T1: Diversity-Zweig nutzt len(self._diversity_stations)."""
    body = _on_cycle_decoded_body()
    assert "self._rx_mode == \"diversity\"" in body or \
        "self._rx_mode == 'diversity'" in body
    assert "len(self._diversity_stations)" in body


def test_t2_normal_uses_normal_stations():
    """T2: Normal-Zweig nutzt len(self._normal_stations)."""
    body = _on_cycle_decoded_body()
    assert "self._rx_mode == \"normal\"" in body or \
        "self._rx_mode == 'normal'" in body
    assert "len(self._normal_stations)" in body


def test_t3_else_branch_keeps_per_slot_fallback():
    """T3: ELSE-Branch (DX-Tune etc.) behaelt per-Slot-Anzahl (R1-Auflage)."""
    body = _on_cycle_decoded_body()
    # Fallback-Pattern muss erhalten sein
    assert "len(messages) if messages else 0" in body, (
        "P135 R1-Auflage: DX-Tune else-Zweig mit per-Slot-Anzahl fehlt")


def test_t4_p135_marker_in_comment():
    """T4: P135-Marker im Kommentar des Fix-Blocks."""
    body = _on_cycle_decoded_body()
    assert "P135" in body, "P135-Marker fehlt"


def test_t5_no_unconditional_per_slot_update():
    """T5: Der frühere Z.88-Pattern als EINZIGER Aufruf ist weg.

    Frueher: `update_decode_count(len(messages) if messages else 0)`
    unmittelbar nach `_assign_slot_parity`. Jetzt: mode-aware Block.
    """
    body = _on_cycle_decoded_body()
    # Mode-Branch muss vor _update_dt_correction stehen
    pos_parity = body.find("_assign_slot_parity")
    pos_branch = body.find("self._rx_mode == ")
    pos_dt = body.find("_update_dt_correction")
    assert pos_parity > 0 and pos_branch > 0 and pos_dt > 0
    assert pos_parity < pos_branch < pos_dt, (
        "Mode-Branch muss zwischen _assign_slot_parity und "
        "_update_dt_correction stehen")


def test_t6_update_decode_count_called_three_times():
    """T6: update_decode_count wird in allen 3 Zweigen gerufen.

    Strukturpruefung: 3 Aufrufe innerhalb des if/elif/else-Blocks.
    """
    body = _on_cycle_decoded_body()
    # Im Fix-Block: 3 update_decode_count-Aufrufe
    pos_branch = body.find("self._rx_mode == ")
    pos_dt = body.find("_update_dt_correction")
    block = body[pos_branch:pos_dt]
    count = block.count("update_decode_count(")
    assert count == 3, (
        f"P135: 3 update_decode_count-Aufrufe erwartet (diversity, normal, "
        f"else), gefunden: {count}")
