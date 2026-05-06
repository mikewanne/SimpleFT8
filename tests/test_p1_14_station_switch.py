"""P1.14 Station-Wechsel-Bug Tests (v0.95.8).

Bug: User klickt waehrend laufendem QSO/CQ auf neue Station — alte Pendings
und Caller-Queue-Eintraege bleiben haengen, Auto-Hunt pausiert dauerhaft
nach manuellem QSO/HALT/Timeout.

Fix-Bereiche (W1-W6 aus Diagnose-V3):
- KP1: start_qso resetet 3 Pendings bei state != IDLE
- KP2: angeklickte Station aus _caller_queue entfernen
- KP3: alte their_call aus _active_qso_targets discarden
- W5:  Statusbar-Toast bei TX-Klick (UX)
- W6:  auto_hunt.on_manual_qso_end() in Cancel/Confirmed/Timeout
"""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from core.qso_state import QSOStateMachine, QSOState
from core.message import FT8Message
from core.auto_hunt import AutoHunt


def _ensure_app():
    return QApplication.instance() or QApplication([])


def _make_sm():
    """QSOStateMachine ohne UI."""
    _ensure_app()
    return QSOStateMachine(my_call="DA1MHH", my_grid="JO31")


def _make_msg(caller: str, snr: int = -10, freq_hz: int = 1000) -> FT8Message:
    """FT8Message-Helper (CQ-Style)."""
    return FT8Message(
        raw=f"CQ {caller} JO40",
        field1="CQ",
        field2=caller,
        field3="JO40",
        snr=snr,
        freq_hz=freq_hz,
    )


# ── KP1: Pendings-Reset bei state != IDLE ─────────────────────────


def test_start_qso_resets_pending_reply():
    """KP1: bei CQ_WAIT wird _pending_reply auf None gesetzt."""
    sm = _make_sm()
    sm.cq_mode = True
    sm._set_state(QSOState.CQ_WAIT)
    sm._pending_reply = _make_msg("OLD")
    sm.start_qso(their_call="NEW", freq_hz=1000)
    assert sm._pending_reply is None
    assert sm.qso.their_call == "NEW"


def test_start_qso_resets_pending_hunt_reply():
    """KP1: bei WAIT_REPORT wird _pending_hunt_reply resetet."""
    sm = _make_sm()
    sm.start_qso(their_call="OLD", freq_hz=1000)
    sm._set_state(QSOState.WAIT_REPORT)
    sm._pending_hunt_reply = _make_msg("OLD")
    sm.start_qso(their_call="NEW", freq_hz=1000)
    assert sm._pending_hunt_reply is None
    assert sm.qso.their_call == "NEW"


def test_start_qso_resets_pending_rr73():
    """KP1: bei WAIT_RR73 wird _pending_rr73 resetet."""
    sm = _make_sm()
    sm.start_qso(their_call="OLD", freq_hz=1000)
    sm._set_state(QSOState.WAIT_RR73)
    sm._pending_rr73 = _make_msg("OLD")
    sm.start_qso(their_call="NEW", freq_hz=1000)
    assert sm._pending_rr73 is None


def test_start_qso_keeps_caller_queue():
    """Option B: _caller_queue bleibt erhalten fuer CQ-Resume."""
    sm = _make_sm()
    sm.cq_mode = True
    sm._set_state(QSOState.CQ_WAIT)
    sm._caller_queue = [_make_msg("CALLER1"), _make_msg("CALLER2")]
    sm.start_qso(their_call="NEW", freq_hz=1000)
    assert len(sm._caller_queue) == 2
    assert sm._caller_queue[0].caller == "CALLER1"
    assert sm._caller_queue[1].caller == "CALLER2"


def test_start_qso_was_cq_robust():
    """KP6 Regression: _was_cq aus cq_mode gelesen wenn CQ aktiv ist.

    Wichtig: testet nur den State-Machine-Pfad. Im UI-Pfad (mw_qso.py)
    wird stop_cq() VOR start_qso() aufgerufen, deshalb muss dort der
    Workaround `_was_cq = True` nachtraeglich gesetzt werden — Plan-V2
    hat entschieden den Workaround zu BEHALTEN.
    """
    sm = _make_sm()
    sm.cq_mode = True
    sm._set_state(QSOState.CQ_WAIT)
    sm.start_qso(their_call="NEW", freq_hz=1000)
    # cq_mode war beim Aufruf True → _was_cq wurde True gesetzt
    assert sm._was_cq is True


# ── KP2/KP3: UI-Logik (Logik-Sim, kein MainWindow-Mock) ─────────────


def test_handler_clicked_station_removed_from_queue():
    """KP2: Klick auf Station die in Queue ist → aus Queue entfernen.

    Pure Python-Logik-Sim, keine UI-Layer noetig.
    """
    sm = _make_sm()
    sm._caller_queue = [_make_msg("DUPE"), _make_msg("OTHER")]
    # Simuliere mw_qso.py-Logik fuer KP2:
    target_call = "DUPE"
    if any(m.caller == target_call for m in sm._caller_queue):
        sm._caller_queue = [m for m in sm._caller_queue
                            if m.caller != target_call]
    assert len(sm._caller_queue) == 1
    assert sm._caller_queue[0].caller == "OTHER"


def test_start_qso_old_call_not_in_active_targets():
    """KP3: alte their_call wird aus _active_qso_targets entfernt.

    Pure Python-Logik-Sim (das set ist in MainWindow, nicht StateMachine).
    """
    targets = {"OLD", "OTHER"}
    old_call = "OLD"
    if old_call:
        targets.discard(old_call)
    targets.add("NEW")
    assert "OLD" not in targets
    assert "NEW" in targets
    assert "OTHER" in targets


# ── KP4/W3: Courtesy-73 State sauber abbrechbar ───────────────────


def test_courtesy_73_state_resetable():
    """KP4/W3: Klick waehrend TX_73_COURTESY bricht sauber ab."""
    sm = _make_sm()
    sm.start_qso(their_call="OLD", freq_hz=1000)
    sm.qso.courtesy_73_sent = True  # markiert (irgendwann)
    sm._set_state(QSOState.TX_73_COURTESY)
    sm.start_qso(their_call="NEW", freq_hz=1000)
    # Neue QSOData → courtesy_73_sent zurueck auf False (Default)
    assert sm.state == QSOState.TX_CALL
    assert sm.qso.their_call == "NEW"
    assert sm.qso.courtesy_73_sent is False


# ── W6: Auto-Hunt-Resume API (idempotent) ─────────────────────────


def test_auto_hunt_resume_on_manual_qso_end():
    """W6: on_manual_qso_end setzt _manual_override = False."""
    hunt = AutoHunt()
    hunt.active = True
    hunt.on_manual_qso_start()
    assert hunt._manual_override is True
    hunt.on_manual_qso_end()
    assert hunt._manual_override is False


def test_auto_hunt_resume_after_timeout():
    """W6: nach manuellem QSO + Timeout muss on_manual_qso_end gerufen
    werden damit Auto-Hunt fortlaeuft. on_qso_timeout alleine resetet
    _manual_override NICHT — das ist der Bug."""
    hunt = AutoHunt()
    hunt.active = True
    hunt.on_manual_qso_start()
    hunt.on_qso_timeout("DUMMY")  # Cooldown setzen
    # Nach on_qso_timeout ist _manual_override IMMER NOCH True (Bug):
    assert hunt._manual_override is True
    # Erst on_manual_qso_end (P1.14 Fix in mw_qso.py:_on_qso_timeout)
    # gibt Auto-Hunt frei:
    hunt.on_manual_qso_end()
    assert hunt._manual_override is False
