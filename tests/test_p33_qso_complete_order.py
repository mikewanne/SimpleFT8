"""P33 QSO-Komplett-Reihenfolge: ✓ vor naechstem CQ (v0.97.14, Mai 2026).

Vorher (Bug): `qso_confirmed.emit` feuerte erst nach Courtesy-73-Send →
`✓ QSO komplett` erschien EINEN Slot zu spaet (nach OMNI-CQ).
Jetzt: 2-Signal-Split — `qso_confirmed_visual` sofort bei 73-Empfang
fuer UI-Update, `qso_confirmed` (full) nach Courtesy fuer alle anderen
Operationen (OMNI-Resume etc.).
"""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from core.qso_state import QSOStateMachine, QSOState, QSOData
from core.message import FT8Message


def _ensure_app():
    return QApplication.instance() or QApplication([])


def _make_73_msg(caller="DA1TST", target="DA1MHH", tx_even=False, freq=1500):
    msg = FT8Message(
        raw=f"{target} {caller} 73",
        field1=target,
        field2=caller,
        field3="73",
        snr=-15,
        freq_hz=freq,
    )
    msg._tx_even = tx_even
    return msg


def _setup_wait_73_state(sm: QSOStateMachine, their_call="DA1TST"):
    sm.cq_mode = True
    sm._was_cq = False
    sm.qso = QSOData(
        their_call=their_call,
        their_grid="JN66",
        freq_hz=1500,
        start_time=1700000000.0,
        timeout_cycles=0,
    )
    sm._set_state(QSOState.WAIT_73)


# T1: visual emit sofort bei 73-Empfang ──────────────────────────────

def test_qso_confirmed_visual_fires_on_73_received_in_wait_73():
    """T1 (AK3): WAIT_73 + 73 → visual.emit 1×, full.emit 0×."""
    _ensure_app()
    sm = QSOStateMachine("DA1MHH", "JO31")
    _setup_wait_73_state(sm)
    visual_emits = []
    full_emits = []
    sm.qso_confirmed_visual.connect(visual_emits.append)
    sm.qso_confirmed.connect(full_emits.append)

    msg = _make_73_msg()
    sm.on_message_received(msg)

    assert len(visual_emits) == 1, "visual.emit muss 1× bei 73-Empfang feuern"
    assert len(full_emits) == 0, "full.emit darf NICHT bei 73-Empfang feuern"
    assert sm.state == QSOState.TX_73_COURTESY


# T2: full emit nach Courtesy-Send ───────────────────────────────────

def test_qso_confirmed_full_fires_after_courtesy_73_sent():
    """T2 (AK4): nach T1, on_message_sent(TX_73_COURTESY) → full.emit 1×."""
    _ensure_app()
    sm = QSOStateMachine("DA1MHH", "JO31")
    _setup_wait_73_state(sm)
    visual_emits = []
    full_emits = []
    sm.qso_confirmed_visual.connect(visual_emits.append)
    sm.qso_confirmed.connect(full_emits.append)

    # Simuliere 73-Empfang → State=TX_73_COURTESY, Courtesy gesendet
    sm.on_message_received(_make_73_msg())
    assert sm.state == QSOState.TX_73_COURTESY

    # Simuliere on_message_sent fuer Courtesy-73
    sm.on_message_sent()

    # visual nur 1× (von 73-Empfang), full 1× (von Courtesy-Send)
    assert len(visual_emits) == 1, "visual nur 1× (kein 2. visual nach Courtesy)"
    assert len(full_emits) == 1, "full feuert 1× nach Courtesy-Send"


# T3: WAIT_73-Timeout emittet visual + full ──────────────────────────

def test_wait_73_timeout_emits_visual_and_full_in_order():
    """T3 (AK5): 3× on_cycle_end in WAIT_73 → visual + full direkt nacheinander."""
    _ensure_app()
    sm = QSOStateMachine("DA1MHH", "JO31")
    _setup_wait_73_state(sm)
    # use start_time in past so MAX_QSO_DURATION not yet hit
    sm.qso.start_time = 1.0  # 1970 — but timeout_cycles drives the path
    # Reset start_time to recent to avoid 3-min timeout
    import time as _time
    sm.qso.start_time = _time.time()

    emit_order = []
    sm.qso_confirmed_visual.connect(lambda q: emit_order.append("visual"))
    sm.qso_confirmed.connect(lambda q: emit_order.append("full"))

    # 3× on_cycle_end ohne 73
    sm.on_cycle_end()  # timeout_cycles=1
    sm.on_cycle_end()  # timeout_cycles=2
    sm.on_cycle_end()  # timeout_cycles=3 → trigger

    assert emit_order == ["visual", "full"], (
        f"Erwartet ['visual', 'full'], bekommen: {emit_order}"
    )


# T4: add_qso_complete genau 1× pro QSO ──────────────────────────────

def test_visual_signal_fires_once_per_qso():
    """T4 (AK6): visual feuert genau 1× pro QSO — kein Doppel-Eintrag im Panel.

    Simuliert vollen 73-Empfang + Courtesy-Send-Done.
    """
    _ensure_app()
    sm = QSOStateMachine("DA1MHH", "JO31")
    _setup_wait_73_state(sm)
    visual_emits = []
    sm.qso_confirmed_visual.connect(visual_emits.append)

    sm.on_message_received(_make_73_msg())  # visual 1×
    sm.on_message_sent()  # full, kein 2. visual

    assert len(visual_emits) == 1, "visual genau 1× pro QSO"


# T5: Doppelschutz-Pfad funktioniert ─────────────────────────────────

def test_hypothetic_double_protection_path():
    """T6 (AK7): courtesy_73_sent=True + neues is_73 → visual + full beide 1×."""
    _ensure_app()
    sm = QSOStateMachine("DA1MHH", "JO31")
    _setup_wait_73_state(sm)
    sm.qso.courtesy_73_sent = True  # Vor-Bedingung fuer Doppelschutz-Branch

    visual_emits = []
    full_emits = []
    sm.qso_confirmed_visual.connect(visual_emits.append)
    sm.qso_confirmed.connect(full_emits.append)

    sm.on_message_received(_make_73_msg())

    # visual oben gefeuert, full im else-Branch
    assert len(visual_emits) == 1, "visual feuert auch im Doppelschutz-Pfad"
    assert len(full_emits) == 1, "full feuert im else-Branch (courtesy schon gesendet)"


# T6: Bug-Schutz auf Source-Level ────────────────────────────────────

def test_qso_state_has_both_signals_defined():
    """Bug-Schutz: qso_confirmed_visual + qso_confirmed beide definiert."""
    import inspect
    from core import qso_state as _module
    src = inspect.getsource(_module)
    assert "qso_confirmed_visual = Signal(object)" in src, (
        "qso_confirmed_visual Signal-Definition fehlt"
    )
    assert "qso_confirmed = Signal(object)" in src, (
        "qso_confirmed Signal-Definition fehlt"
    )
    # Wichtig: visual.emit MUSS in on_message_received WAIT_73-is_73-Branch
    assert "self.qso_confirmed_visual.emit(self.qso)" in src, (
        "visual.emit irgendwo aufgerufen muss vorhanden sein"
    )
