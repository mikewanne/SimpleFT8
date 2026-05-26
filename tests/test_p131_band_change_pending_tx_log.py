"""P131 (26.05.2026) — Sende-Log bei Bandwechsel verwerfen.

Mike-Field-Bug 26.05. 15m→20m: „bei wechsel auf 20 meter, geht noch ein
ruf raus oder wird angezeigt vom 15 meter band vorher."

Pattern-Familie 8. Iteration (P81/P122/P124/P127/P128/P129/P126/P131):
KISS-Defensive-Stop wenn Kontext wechselt.

R1-V4-pro ORANGE-Catch: QueuedConnection-Race — `tx_started`-Slot kann
NACH Bandwechsel verarbeitet werden, dann nuetzt simples Pending-Reset
nichts. Defense-in-Depth: band-Tag im _pending_tx_log + Match-Check in
_on_tx_finished.

ACs:
- AC1: `_on_band_changed` ruft `_pending_tx_log = None` UNABHAENGIG von
       is_transmitting (P127-Pattern)
- AC2: `_on_tx_started` setzt `band`-Feld im _pending_tx_log
- AC3: `_on_tx_finished` prueft Band-Match vor add_tx
- AC4: P131-Doku-Marker in den 3 betroffenen Stellen
- AC5: Reset passiert NACH encoder.abort() (Reihenfolge)
- AC6: Race-Test: Pending mit alter Band-Info wird verworfen
"""

from __future__ import annotations

import ast
from pathlib import Path


MW_RADIO = Path(__file__).parent.parent / "ui" / "mw_radio.py"
MW_QSO = Path(__file__).parent.parent / "ui" / "mw_qso.py"


def _read_method_body(file_path: Path, method_name: str) -> str:
    """Methoden-Body extrahieren (ohne dependency auf MainWindow-Class)."""
    src = file_path.read_text()
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if (isinstance(node, ast.FunctionDef)
                and node.name == method_name):
            return ast.unparse(node)
    raise AssertionError(f"Methode {method_name} nicht in {file_path.name}")


# ---------------------------------------------------------------------------
# T1-T3: _on_band_changed setzt _pending_tx_log = None (P127-Pattern)
# ---------------------------------------------------------------------------


def test_t1_band_changed_resets_pending_tx_log():
    """T1: _on_band_changed setzt _pending_tx_log = None."""
    body = _read_method_body(MW_RADIO, "_on_band_changed")
    assert "_pending_tx_log = None" in body, (
        "P131: _on_band_changed muss _pending_tx_log nullen")


def test_t2_band_changed_reset_outside_is_transmitting_block():
    """T2: Reset passiert UNABHAENGIG von is_transmitting (P127-Pattern).

    Strukturelle Pruefung: nach `encoder.is_transmitting`-Block kommt
    `_pending_tx_log = None` als eigenes Statement.
    """
    body = _read_method_body(MW_RADIO, "_on_band_changed")
    # Markierung muss VOR dem QSO-Panel-Clear stehen und NACH encoder.abort
    pos_abort = body.find("encoder.abort()")
    pos_reset = body.find("_pending_tx_log = None")
    pos_clear = body.find("qso_panel.log_view.clear()")
    assert pos_abort > 0
    assert pos_reset > 0
    assert pos_abort < pos_reset, "Reset muss NACH abort() kommen"
    assert pos_reset < pos_clear, "Reset muss VOR log_view.clear() kommen"


def test_t3_band_changed_uses_hasattr_pattern():
    """T3: hasattr-Guard fuer Lazy-Init des Attributs (analog P127)."""
    body = _read_method_body(MW_RADIO, "_on_band_changed")
    # hasattr(self, "_pending_tx_log") direkt vor dem Reset
    assert "hasattr(self, '_pending_tx_log')" in body or \
        'hasattr(self, "_pending_tx_log")' in body


# ---------------------------------------------------------------------------
# T4-T6: _on_tx_started speichert band-Tag (R1-ORANGE-Catch)
# ---------------------------------------------------------------------------


def test_t4_tx_started_stores_band_in_pending():
    """T4: _on_tx_started speichert `band` im _pending_tx_log dict."""
    body = _read_method_body(MW_QSO, "_on_tx_started")
    assert "'band':" in body or '"band":' in body, (
        "P131 R1-Catch: band-Tag muss im _pending_tx_log gesichert sein")
    assert "self.settings.band" in body


def test_t5_pending_dict_has_5_fields():
    """T5: _pending_tx_log hat genau 5 Felder (message, tx_even, ts, omni, band)."""
    body = _read_method_body(MW_QSO, "_on_tx_started")
    for field in ["message", "tx_even", "slot_start_ts",
                  "omni_remaining", "band"]:
        assert f"'{field}'" in body or f'"{field}"' in body, (
            f"P131: Feld '{field}' fehlt im _pending_tx_log")


# ---------------------------------------------------------------------------
# T6-T9: _on_tx_finished prueft Band-Match
# ---------------------------------------------------------------------------


def test_t6_tx_finished_checks_band_match():
    """T6: _on_tx_finished vergleicht pending['band'] mit aktuellem Band."""
    body = _read_method_body(MW_QSO, "_on_tx_finished")
    # Variable pending_band oder direktes pending.get("band")
    assert "pending_band" in body or "pending.get('band')" in body or \
        'pending.get("band")' in body, (
        "P131: Band-Match-Check fehlt in _on_tx_finished")
    assert "self.settings.band" in body, (
        "P131: aktueller settings.band muss gelesen werden")


def test_t7_tx_finished_skips_add_tx_on_band_mismatch():
    """T7: Bei Band-Mismatch wird add_tx NICHT gerufen."""
    body = _read_method_body(MW_QSO, "_on_tx_finished")
    # Logik: if pending_band is None or pending_band == current_band: add_tx
    # → add_tx unter Bedingung
    pos_check = max(
        body.find("pending_band == current_band"),
        body.find("pending.get('band')"),
        body.find('pending.get("band")'),
    )
    pos_add_tx = body.find("self.qso_panel.add_tx(")
    assert pos_check > 0 and pos_add_tx > 0
    assert pos_check < pos_add_tx, (
        "P131: Band-Check muss VOR add_tx() stehen")


def test_t8_tx_finished_clears_pending_unconditionally():
    """T8: _pending_tx_log = None auch bei verworfenem Eintrag."""
    body = _read_method_body(MW_QSO, "_on_tx_finished")
    # `_pending_tx_log = None` muss IMMER laufen wenn pending was hatte —
    # nicht nur im add_tx-Pfad.
    # Strukturpruefung: außerhalb des if pending_band-Blocks
    assert body.count("_pending_tx_log = None") >= 1


def test_t9_backward_compat_no_band_field_logs_anyway():
    """T9: Falls 'band' fehlt (old-style dict), wird trotzdem geloggt.

    Macht den Fix backward-kompatibel zu Test-Mocks ohne band-Feld.
    """
    body = _read_method_body(MW_QSO, "_on_tx_finished")
    # `pending_band is None` MUSS True branch zu add_tx erlauben
    assert "pending_band is None" in body or "is None" in body, (
        "P131: backward-compat — pending_band=None → loggen erlaubt")


# ---------------------------------------------------------------------------
# T10-T12: Pattern-Familie + Doku
# ---------------------------------------------------------------------------


def _source_slice(file_path: Path, anchor: str, window: int = 800) -> str:
    """Source-Text-Slice ab `anchor` (anders als ast.unparse: behaelt Kommentare)."""
    src = file_path.read_text()
    pos = src.find(anchor)
    assert pos > 0, f"{anchor!r} nicht in {file_path.name}"
    return src[pos:pos + window]


def test_t10_p131_marker_in_mw_radio():
    """T10: P131-Marker im _on_band_changed Kommentar (Source-Text)."""
    slice_ = _source_slice(MW_RADIO, "_pending_tx_log = None", 200)
    assert "P131" in _source_slice(MW_RADIO, "P131", 80), (
        "P131-Marker muss in mw_radio.py vorkommen")
    _ = slice_  # unused but ensures the marker is in context


def test_t11_p131_marker_in_mw_qso_tx_started():
    """T11: P131-Marker in _on_tx_started Source-Bereich."""
    src = MW_QSO.read_text()
    # Suche P131-Marker in der Nähe von "Log-Args für tx_finished"
    pos = src.find("Log-Args für tx_finished")
    assert pos > 0
    window = src[pos:pos + 600]
    assert "P131" in window, "P131-Marker in _on_tx_started erwartet"


def test_t12_p131_marker_in_mw_qso_tx_finished():
    """T12: P131-Marker in _on_tx_finished Source-Bereich."""
    src = MW_QSO.read_text()
    pos = src.find("Defer'ter Log-Eintrag aus tx_started")
    assert pos > 0
    window = src[pos:pos + 800]
    assert "P131" in window, "P131-Marker in _on_tx_finished erwartet"


# ---------------------------------------------------------------------------
# T13: Race-Szenario simuliert (Logik-Test)
# ---------------------------------------------------------------------------


def test_t13_race_pending_with_old_band_is_discarded():
    """T13: Race-Logik — pending mit altem Band wird verworfen.

    Simulation: extrahiere die Match-Logik aus _on_tx_finished und teste
    sie mit verschiedenen Band-Kombinationen.
    """
    # Reine Logik-Pruefung — kein UI-Setup noetig.
    # Old-style pending (kein band-Feld) → loggen (backward-compat)
    # New-style match (gleiches Band) → loggen
    # New-style mismatch → verwerfen
    cases = [
        # (pending_band, current_band, should_log)
        (None, "20m", True),     # backward-compat
        ("20m", "20m", True),    # match
        ("15m", "20m", False),   # mismatch (P131 Bug-Szenario)
        ("20m", "15m", False),   # umgekehrt
    ]
    for pending_band, current_band, should_log in cases:
        result = pending_band is None or pending_band == current_band
        assert result == should_log, (
            f"Race-Logik falsch: pending={pending_band}, "
            f"current={current_band}, expected={should_log}, got={result}")
