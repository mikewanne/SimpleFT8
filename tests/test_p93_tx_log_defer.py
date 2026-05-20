"""P93 (20.05.2026, v0.97.65) — Sende-Log-Eintrag defern auf tx_finished.

Mike-Beobachtung 20.05.2026 nach P73-A-Field-Test: „Sende"-Eintrag
erschien am Slot-Start, „Empf."-Eintrag am Slot-Ende → optisch
„2 Meldungen auf einmal, dann 30 s Pause".

Fix: TX-Args in `_pending_tx_log` zwischenspeichern (`_on_tx_started`),
`add_tx` erst in `_on_tx_finished` rufen. Dadurch erscheinen Sende-
und Empfangs-Einträge beide am Slot-Ende, alle 15 s gleichmäßig.

Test-Coverage:
- T1: _on_tx_started ruft NICHT mehr add_tx, sondern füllt _pending_tx_log
- T2: _on_tx_finished gibt _pending_tx_log via add_tx aus, dann None
- T3: ohne pending Log läuft _on_tx_finished sauber durch (defensiv)
- T4: _has_sent_cq wird weiterhin in _on_tx_started gesetzt
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from PySide6.QtWidgets import QApplication

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def _make_qso_mixin(*, omni_active=False):
    """Minimaler Mock analog Bundle G / P92 Pattern."""
    from ui.mw_qso import QSOMixin
    obj = MagicMock(spec=QSOMixin)
    obj._on_tx_started = QSOMixin._on_tx_started.__get__(obj)
    obj._on_tx_finished = QSOMixin._on_tx_finished.__get__(obj)
    obj.qso_panel = MagicMock()
    obj.control_panel = MagicMock()
    obj.qso_sm = MagicMock()
    obj.encoder = MagicMock()
    obj.encoder.tx_even = False
    obj._has_sent_cq = False
    obj._omni_cq = MagicMock()
    obj._omni_cq.is_active = MagicMock(return_value=omni_active)
    obj._omni_cq.is_paused = MagicMock(return_value=False)
    obj._omni_cq.cq_remaining_display = 3
    obj._pending_station_click = None
    obj._swr_blocked_bands = set()
    obj.settings = MagicMock()
    obj.settings.band = "40m"
    return obj


# ── T1: _on_tx_started füllt _pending_tx_log, ruft NICHT add_tx ────


def test_tx_started_fills_pending_log_no_add_tx(app):
    """T1: _on_tx_started → _pending_tx_log gesetzt, qso_panel.add_tx NICHT gerufen."""
    obj = _make_qso_mixin()
    obj._on_tx_started("DA1MHH G8KHF -15", tx_even=True,
                       slot_start_ts=1234567890.0)
    # add_tx wurde NICHT gerufen
    obj.qso_panel.add_tx.assert_not_called()
    # _pending_tx_log enthält die Args
    assert obj._pending_tx_log is not None
    assert obj._pending_tx_log["message"] == "DA1MHH G8KHF -15"
    assert obj._pending_tx_log["tx_even"] is True
    assert obj._pending_tx_log["slot_start_ts"] == 1234567890.0
    assert obj._pending_tx_log["omni_remaining"] is None


# ── T2: _on_tx_finished gibt add_tx aus und leert pending ─────────


def test_tx_finished_emits_add_tx_and_clears_pending(app):
    """T2: _on_tx_finished → add_tx mit pending Args, danach pending=None."""
    obj = _make_qso_mixin()
    obj._on_tx_started("CQ DA1MHH JN58", tx_even=False,
                       slot_start_ts=42.0)
    # Pending ist gesetzt
    assert obj._pending_tx_log is not None
    # Jetzt tx_finished
    obj._on_tx_finished()
    # add_tx wurde mit den pending-Args gerufen
    obj.qso_panel.add_tx.assert_called_once()
    args, kwargs = obj.qso_panel.add_tx.call_args
    assert args[0] == "CQ DA1MHH JN58"
    assert args[1] == ""  # ant_label leer (P15)
    assert kwargs["tx_even"] is False
    assert kwargs["slot_start_ts"] == 42.0
    assert kwargs["omni_remaining"] is None
    # Pending wurde geleert
    assert obj._pending_tx_log is None


# ── T3: _on_tx_finished ohne pending Log läuft defensiv durch ─────


def test_tx_finished_without_pending_log_does_not_crash(app):
    """T3: _on_tx_finished ohne vorheriges _on_tx_started → kein Crash,
    add_tx wird nicht gerufen."""
    obj = _make_qso_mixin()
    # NICHT _on_tx_started aufrufen — _pending_tx_log existiert nicht
    obj._on_tx_finished()
    obj.qso_panel.add_tx.assert_not_called()


# ── T4: _has_sent_cq wird weiter in tx_started gesetzt ─────────────


def test_has_sent_cq_still_set_in_tx_started(app):
    """T4: P28-Verhalten unverändert — _has_sent_cq=True bei CQ-Nachricht."""
    obj = _make_qso_mixin()
    obj._on_tx_started("CQ DA1MHH JN58", tx_even=True, slot_start_ts=1.0)
    assert obj._has_sent_cq is True


# ── T5: OMNI cq_remaining_display wird mitgespeichert ──────────────


def test_omni_remaining_captured_in_pending_log(app):
    """T5: bei aktivem OMNI wird der Counter im pending Log gespeichert
    und in tx_finished an add_tx weitergereicht."""
    obj = _make_qso_mixin(omni_active=True)
    obj._on_tx_started("CQ DA1MHH JN58", tx_even=False, slot_start_ts=99.0)
    assert obj._pending_tx_log["omni_remaining"] == 3
    obj._on_tx_finished()
    kwargs = obj.qso_panel.add_tx.call_args.kwargs
    assert kwargs["omni_remaining"] == 3
