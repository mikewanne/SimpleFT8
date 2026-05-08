"""Tests fuer P1.HUNT-SNR (v0.95.21).

Hunt-Klick + Auto-Hunt nutzen station-spezifischen SNR aus FT8Message
statt _last_snr. Plus advance() liest qso.our_snr statt _last_snr.
Hardware-frei, Qt-offscreen via env.
"""
from __future__ import annotations

import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from PySide6.QtWidgets import QApplication

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from core.qso_state import QSOStateMachine, QSOState  # noqa: E402


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def _new_sm(my_call: str = "DA1MHH", my_grid: str = "JN58") -> QSOStateMachine:
    sm = QSOStateMachine(my_call, my_grid)
    sm._last_snr = -25  # bewusst „falscher" Wert um zu zeigen dass their_snr gewinnt
    return sm


# ── start_qso(): their_snr ueberschreibt _last_snr ──────────────────


def test_start_qso_uses_their_snr_when_provided(app):
    sm = _new_sm()
    sent = []
    sm.send_message.connect(lambda m: sent.append(m))
    sm.start_qso(their_call="EV81AB", their_grid="KN12", freq_hz=946,
                 their_snr=-18)
    assert sm.qso.our_snr == "-18"
    assert sent[-1] == "EV81AB DA1MHH -18"


def test_start_qso_falls_back_to_last_snr_when_none(app):
    sm = _new_sm()
    sm._last_snr = -12
    sent = []
    sm.send_message.connect(lambda m: sent.append(m))
    sm.start_qso(their_call="EV81AB", their_grid="KN12", freq_hz=946)
    # Backward-compat: kein their_snr → _last_snr=-12 gewinnt
    assert sm.qso.our_snr == "-12"
    assert sent[-1] == "EV81AB DA1MHH -12"


def test_start_qso_clamps_weak_snr(app):
    sm = _new_sm()
    sent = []
    sm.send_message.connect(lambda m: sent.append(m))
    sm.start_qso(their_call="EV81AB", their_grid="KN12", freq_hz=946,
                 their_snr=-99)
    assert sm.qso.our_snr == "-10"
    assert sent[-1] == "EV81AB DA1MHH -10"


def test_start_qso_zero_snr_not_treated_as_falsy(app):
    """Edge-Case: their_snr=0 muss als gueltiger Wert behandelt werden."""
    sm = _new_sm()
    sm._last_snr = -25  # falscher Wert, soll NICHT gewinnen
    sent = []
    sm.send_message.connect(lambda m: sent.append(m))
    sm.start_qso(their_call="EV81AB", their_grid="KN12", freq_hz=946,
                 their_snr=0)
    assert sm.qso.our_snr == "+00"


def test_start_qso_positive_snr(app):
    sm = _new_sm()
    sent = []
    sm.send_message.connect(lambda m: sent.append(m))
    sm.start_qso(their_call="EV81AB", their_grid="KN12", freq_hz=946,
                 their_snr=15)
    assert sm.qso.our_snr == "+15"


def test_multi_decode_slot_uses_clicked_station_snr(app):
    """Mike's Field-Test: 3 Stationen im Slot, Klick auf mittlere SNR.

    Decoder iteriert -15, -18, -23 → _last_snr=-23. Klick auf -18.
    Report MUSS -18 sein, nicht -23 (alter Bug) oder -15.
    """
    sm = _new_sm()
    # Simulate Decoder-Iterator-Update
    sm.set_last_snr(-15)
    sm.set_last_snr(-18)
    sm.set_last_snr(-23)  # zuletzt iteriert
    assert sm._last_snr == -23
    sent = []
    sm.send_message.connect(lambda m: sent.append(m))
    # Mike klickt auf mittlere Station (msg.snr=-18)
    sm.start_qso(their_call="EV81AB", their_grid="KN12", freq_hz=946,
                 their_snr=-18)
    # Report station-spezifisch, NICHT _last_snr
    assert sm.qso.our_snr == "-18"
    assert sent[-1] == "EV81AB DA1MHH -18"


def test_our_snr_persisted_in_qso_data(app):
    sm = _new_sm()
    sm.start_qso(their_call="EV81AB", their_grid="KN12", freq_hz=946,
                 their_snr=-18)
    # Konsumenten (Logbuch ADIF, qso_panel) lesen qso.our_snr
    assert sm.qso.our_snr == "-18"
    assert sm.qso.their_call == "EV81AB"


def test_start_qso_during_active_qso_resets_pendings(app):
    """Backward-compat: start_qso bei nicht-IDLE-State macht Reset."""
    sm = _new_sm()
    sm.start_qso(their_call="OLD", their_snr=-15)
    sm._pending_reply = MagicMock()
    sm._pending_hunt_reply = MagicMock()
    sm._pending_rr73 = MagicMock()
    # Neuer Hunt → Pendings resettet
    sm.start_qso(their_call="NEW", their_snr=-20)
    assert sm._pending_reply is None
    assert sm._pending_hunt_reply is None
    assert sm._pending_rr73 is None
    assert sm.qso.our_snr == "-20"
    assert sm.qso.their_call == "NEW"


# ── advance(): nutzt qso.our_snr statt _last_snr ────────────────────


def test_advance_uses_our_snr_not_last_snr(app):
    """P1.HUNT-SNR R1-SOLLTE: advance() darf nicht _last_snr nehmen
    wenn qso.our_snr schon korrekt gesetzt ist.

    Szenario: Hunt mit -18 gestartet, dann decodierte starke Station
    setzt _last_snr=-5. Manuelles advance() muss R-18 senden, nicht R-5.
    """
    sm = _new_sm()
    sm.start_qso(their_call="EV81AB", their_grid="KN12", freq_hz=946,
                 their_snr=-18)
    sm._set_state(QSOState.WAIT_REPORT)
    sm.qso.their_snr = "-12"  # advance-Pre-Cond: their_snr existiert
    # Andere Station wurde decodiert mit starkem Signal
    sm.set_last_snr(-5)
    sent = []
    sm.send_message.connect(lambda m: sent.append(m))
    sm.advance()
    # advance() nutzt qso.our_snr=-18 (nicht _last_snr=-5)
    assert sm.qso.our_snr == "R-18"
    assert sent[-1] == "EV81AB DA1MHH R-18"


def test_advance_falls_back_to_last_snr_when_our_snr_empty(app):
    """Edge-Case: our_snr leer → advance() nutzt _last_snr (Backward-compat)."""
    sm = _new_sm()
    sm.start_qso(their_call="EV81AB", their_snr=-18)
    sm._set_state(QSOState.WAIT_REPORT)
    sm.qso.their_snr = "-12"
    sm.qso.our_snr = ""  # explizit leer machen
    sm.set_last_snr(-7)
    sent = []
    sm.send_message.connect(lambda m: sent.append(m))
    sm.advance()
    # Fallback auf _last_snr=-7
    assert sm.qso.our_snr == "R-07"
    assert sent[-1] == "EV81AB DA1MHH R-07"
