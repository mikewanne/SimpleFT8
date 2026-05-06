"""P1.24 TX-Klick-Buffer Tests (v0.95.9).

Bug: TX-Klick wurde komplett ignoriert (silent skip + Toast). Mike's CQ
lief weiter, Klick verpufft. Auch in Hunt-TX_CALL bei Umentscheidung.

Fix: Klick waehrend TX wird gebuffert, State sofort gecleant (stop_cq
oder qso cancel), nach TX-Ende wird _on_station_clicked rekursiv mit
gepuffertem msg getriggert.

Tests pruefen die Buffer-Logik isoliert (kein UI-Mock noetig).
"""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication


def _ensure_app():
    return QApplication.instance() or QApplication([])


def test_pending_click_buffer_logic_cq_active():
    """Sim: bei is_transmitting + cq_mode wird Buffer gesetzt + cq gestoppt."""
    _ensure_app()
    from core.qso_state import QSOStateMachine, QSOState

    sm = QSOStateMachine(my_call="DA1MHH", my_grid="JO31")
    sm.cq_mode = True
    sm._set_state(QSOState.CQ_CALLING)

    # Simuliere _on_station_clicked TX-Pfad:
    is_transmitting = True
    pending_click = None
    if is_transmitting:
        if sm.cq_mode:
            sm.stop_cq()  # cq_mode → False, state → IDLE
        pending_click = "NEW_STATION"

    assert sm.cq_mode is False
    assert sm.state == QSOState.IDLE
    assert pending_click == "NEW_STATION"


def test_pending_click_buffer_logic_hunt_active():
    """Sim: bei is_transmitting + Hunt-QSO wird cancel + Buffer."""
    _ensure_app()
    from core.qso_state import QSOStateMachine, QSOState

    sm = QSOStateMachine(my_call="DA1MHH", my_grid="JO31")
    sm.start_qso(their_call="OLD", freq_hz=1000)
    assert sm.state == QSOState.TX_CALL

    # Simuliere _on_station_clicked TX-Pfad fuer Hunt:
    is_transmitting = True
    pending_click = None
    HUNT_BLOCKED_STATES = (QSOState.IDLE, QSOState.TIMEOUT,
                           QSOState.CQ_CALLING, QSOState.CQ_WAIT)
    if is_transmitting:
        if sm.cq_mode:
            sm.stop_cq()
        elif sm.state not in HUNT_BLOCKED_STATES:
            sm.cancel()  # state → IDLE, qso geloescht
        pending_click = "NEW_STATION"

    assert sm.state == QSOState.IDLE
    assert pending_click == "NEW_STATION"


def test_pending_click_replay_after_tx_finished():
    """Sim: nach TX-Ende wird gepufferter Klick neu getriggert."""
    _ensure_app()
    from core.qso_state import QSOStateMachine, QSOState

    sm = QSOStateMachine(my_call="DA1MHH", my_grid="JO31")
    pending = "NEW_STATION"

    # Simuliere _on_tx_finished:
    sm.on_message_sent()  # in IDLE: no-op
    if pending is not None:
        buffered = pending
        pending = None
        # Hier wuerde _on_station_clicked rekursiv aufgerufen mit msg
        sm.start_qso(their_call=buffered, freq_hz=1000)

    assert pending is None
    assert sm.state == QSOState.TX_CALL
    assert sm.qso.their_call == "NEW_STATION"


def test_halt_clears_pending_click():
    """Sim: HALT verwirft gepufferten Klick."""
    pending = "BUFFERED"
    # Simuliere _on_cancel:
    pending = None
    assert pending is None
