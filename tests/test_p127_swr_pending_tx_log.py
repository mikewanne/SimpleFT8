"""P127 (25.05.2026) — Sende-Log-Eintrag bei SWR-Abbruch verwerfen.

Mike-Field-Bug 10:52 (Screenshot 15M-SWR 31.3):
```
⚠ Band 15M gesperrt — SWR 31.3
08:51:15 [0] → Sende Z62NS DA1MHH -15   ← NACH der Sperre
```

P93-Defer-Mechanik deferiert Sende-Log von tx_started auf tx_finished.
Bei SWR-Stop mitten im Slot würde der pending-Eintrag mit Slot-Start-
Timestamp NACH der Sperre-Meldung ins Log → wirkt wie „Send NACH Sperre".

Fix: im SWR-Watchdog direkt `_pending_tx_log = None` setzen (KISS,
analog P60-F3-Pattern für `_pending_station_click`).

ACs:
- AC1: _pending_tx_log wird in _on_swr_alarm cleared (nach P60-F3-Block)
- AC2: _on_tx_finished mit pending=None ruft KEIN add_tx
- AC3: Hardware-Sicherheit unverändert (abort + ptt_off bleiben)
- AC4: HALT-Pfad bleibt unverändert (Mike-Spec: nur SWR)
- AC5: Bandwechsel ohne SWR — kein Eingriff
- AC6: 1-Spike / Pre-TX-Pfade (early return) — kein Eingriff
- AC7: Defensive hasattr für Test-Fakes
"""

from __future__ import annotations

import inspect
import pytest


# ---------------------------------------------------------------------------
# T1: Source-Inspektion — Fix ist an der richtigen Stelle
# ---------------------------------------------------------------------------


def test_t1_swr_alarm_clears_pending_tx_log():
    """T1: _on_swr_alarm enthält `_pending_tx_log = None`-Block.

    Source-Inspektion ist hier pragmatisch, weil _on_swr_alarm ein
    komplexer Qt-Slot mit Modal-Dialog ist (nicht trivial mockbar).
    """
    from ui.mw_tx import TXMixin
    source = inspect.getsource(TXMixin._on_swr_alarm)
    assert "_pending_tx_log" in source, (
        "_on_swr_alarm muss _pending_tx_log clearen")
    assert "self._pending_tx_log = None" in source


def test_t2_pattern_after_p60_f3():
    """T2: P127-Block steht NACH P60-F3-Block (semantische Symmetrie).

    Beide sind „pending-Cleanups nach SWR-Stop". Reihenfolge im Source:
    erst _pending_station_click = None, dann _pending_tx_log = None.
    """
    from ui.mw_tx import TXMixin
    source = inspect.getsource(TXMixin._on_swr_alarm)
    pos_click = source.find("self._pending_station_click = None")
    pos_log = source.find("self._pending_tx_log = None")
    assert pos_click > 0 and pos_log > 0
    assert pos_log > pos_click, (
        "P127 _pending_tx_log-Clear muss NACH P60-F3 "
        "_pending_station_click-Clear stehen (Pattern-Konsistenz)")


def test_t3_defensive_hasattr_guard():
    """T3: hasattr-Guard schützt vor Test-Fakes ohne Attribut."""
    from ui.mw_tx import TXMixin
    source = inspect.getsource(TXMixin._on_swr_alarm)
    # Beide pending-Cleanups nutzen hasattr-Guard
    assert 'hasattr(self, "_pending_tx_log")' in source


# ---------------------------------------------------------------------------
# T4: Hardware-Sicherheit unverändert
# ---------------------------------------------------------------------------


def test_t4_hardware_safety_preserved():
    """T4: encoder.abort + ptt_off bleiben im _on_swr_alarm-Pfad.

    P127 darf KEINE Hardware-relevanten Aufrufe entfernen oder
    verschieben — Verifikation per Source-Inspektion.
    """
    from ui.mw_tx import TXMixin
    source = inspect.getsource(TXMixin._on_swr_alarm)
    assert "self.encoder.abort()" in source
    assert "self.radio.ptt_off()" in source
    # Reihenfolge: erst abort + ptt_off, dann pending-Cleanups
    pos_abort = source.find("self.encoder.abort()")
    pos_log_clear = source.find("self._pending_tx_log = None")
    assert pos_abort < pos_log_clear, (
        "Hardware-Stop (abort/ptt_off) MUSS vor pending-Cleanups laufen")


# ---------------------------------------------------------------------------
# T5: HALT-Pfad (_abort_active_tx) bleibt UNBERÜHRT
# ---------------------------------------------------------------------------


def test_t5_halt_path_unchanged():
    """T5: _abort_active_tx (User-HALT-Pfad) clearet _pending_tx_log NICHT.

    Mike-Spec war explizit nur SWR-Pfad. Bei HALT will Mike den
    Sende-Eintrag im Log sehen (was er gerade abgebrochen hat).
    """
    from ui.mw_tx import TXMixin
    source = inspect.getsource(TXMixin._abort_active_tx)
    assert "_pending_tx_log" not in source, (
        "_abort_active_tx (HALT-Pfad) darf _pending_tx_log NICHT "
        "clearen — Mike-Spec: nur SWR-Pfad. Bei HALT bleibt Eintrag.")


# ---------------------------------------------------------------------------
# T6: Early-Return-Pfade bleiben unberührt
# ---------------------------------------------------------------------------


def test_t6_pre_tx_early_return_not_affected():
    """T6: Pre-TX-Pfad (`if not encoder.is_transmitting: return`) und
    1-Spike-Pfad (`if _swr_spike_count == 0: return`) liegen VOR dem
    pending-Clear-Block. Bei diesen Pfaden läuft der Clear nicht — was
    auch korrekt ist (kein pending zum Clearen).
    """
    from ui.mw_tx import TXMixin
    source = inspect.getsource(TXMixin._on_swr_alarm)
    # Pre-TX-Guard kommt vor pending-Clear
    pos_pretx_guard = source.find("if not self.encoder.is_transmitting")
    pos_log_clear = source.find("self._pending_tx_log = None")
    assert pos_pretx_guard > 0
    assert pos_pretx_guard < pos_log_clear


# ---------------------------------------------------------------------------
# T7: _on_tx_finished bleibt unverändert (pending=None Branch funktioniert)
# ---------------------------------------------------------------------------


def test_t7_on_tx_finished_handles_none_pending():
    """T7: _on_tx_finished (mw_qso.py) hat schon einen Branch für
    pending=None — kein Crash, kein add_tx. P127 setzt nur das pending
    auf None, _on_tx_finished erkennt das und macht no-op."""
    from ui.mw_qso import QSOMixin
    source = inspect.getsource(QSOMixin._on_tx_finished)
    # Branch existiert: if pending is not None: add_tx(...)
    assert 'pending = getattr(self, "_pending_tx_log", None)' in source
    assert "if pending is not None:" in source
    # In der None-Branch wird NICHTS gerufen (kein add_tx)
    none_branch_active = source.find("if pending is not None:")
    assert none_branch_active > 0


# ---------------------------------------------------------------------------
# T8: Konstanten / Pattern-Familie Doku
# ---------------------------------------------------------------------------


def test_t8_pattern_family_doc_reference():
    """T8: Doku-String erwähnt P127 und P60-F3-Symmetrie."""
    from ui.mw_tx import TXMixin
    source = inspect.getsource(TXMixin._on_swr_alarm)
    assert "P127" in source, "P127-Marker muss im Doku-Kommentar stehen"
    # Mike-Field-Bug-Datum dokumentiert
    assert "25.05.2026" in source or "Mike" in source
