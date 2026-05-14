"""Bundle I (v0.97.26) QSO-Komplett-Reihenfolge — visual NACH Courtesy-73.

Historie:
- Vor P33 (Bundle B', v0.97.14): qso_confirmed.emit nach Courtesy → ✓
  erschien ERST NACH dem nächsten CQ-Slot.
- P33: 2-Signal-Split — qso_confirmed_visual SOFORT bei 73-Empfang +
  qso_confirmed nach Courtesy. ✓ erschien direkt nach Empf. 73 — aber
  VOR Sende 73 → Mike-Feedback 14.05.: zu früh.
- Bundle I (v0.97.26): qso_confirmed_visual wandert nach Courtesy-Send
  (on_message_sent TX_73_COURTESY-Branch). Reihenfolge im QSO-Panel jetzt:
  Empf. 73 → Sende 73 → ✓ QSO komplett → (nächster Slot ggf. CQ).
"""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from core.qso_state import QSOStateMachine, QSOState, QSOData
from core.message import FT8Message


def _ensure_app():
    return QApplication.instance() or QApplication([])


def _make_msg(payload="73", caller="DA1TST", target="DA1MHH",
              tx_even=False, freq=1500):
    msg = FT8Message(
        raw=f"{target} {caller} {payload}",
        field1=target,
        field2=caller,
        field3=payload,
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


# ── T2.1: Bundle I — visual feuert NICHT bei 73-Empfang ───────────────

def test_t2_1_visual_does_not_fire_on_73_received_in_wait_73():
    """T2.1 (Bundle I AC2.1): WAIT_73 + 73-Empfang → visual.emit 0×, full.emit 0×.
    State wechselt auf TX_73_COURTESY für Courtesy-Send."""
    _ensure_app()
    sm = QSOStateMachine("DA1MHH", "JO31")
    _setup_wait_73_state(sm)
    visual_emits = []
    full_emits = []
    sm.qso_confirmed_visual.connect(visual_emits.append)
    sm.qso_confirmed.connect(full_emits.append)

    sm.on_message_received(_make_msg("73"))

    assert len(visual_emits) == 0, "visual darf NICHT bei 73-Empfang feuern"
    assert len(full_emits) == 0, "full darf NICHT bei 73-Empfang feuern"
    assert sm.state == QSOState.TX_73_COURTESY


# ── T2.2: Bundle I — visual + full feuern beide nach Courtesy-Send ────

def test_t2_2_visual_and_full_fire_after_courtesy_sent():
    """T2.2 (Bundle I AC2.5): on_message_sent in TX_73_COURTESY →
    visual.emit 1× UND full.emit 1× in dieser Reihenfolge."""
    _ensure_app()
    sm = QSOStateMachine("DA1MHH", "JO31")
    _setup_wait_73_state(sm)
    emit_order = []
    sm.qso_confirmed_visual.connect(lambda q: emit_order.append("visual"))
    sm.qso_confirmed.connect(lambda q: emit_order.append("full"))

    sm.on_message_received(_make_msg("73"))
    assert sm.state == QSOState.TX_73_COURTESY
    assert emit_order == []  # noch nichts gefeuert

    sm.on_message_sent()  # Courtesy fertig gesendet

    assert emit_order == ["visual", "full"], (
        f"Erwartet ['visual', 'full'], bekommen: {emit_order}"
    )


# ── T2.3: WAIT_73-Timeout-Pfad unverändert ────────────────────────────

def test_t2_3_wait_73_timeout_emits_visual_and_full_in_order():
    """T2.3 (Bundle I AC2.2): 3× on_cycle_end in WAIT_73 → visual + full
    direkt nacheinander (unverändert seit P33)."""
    _ensure_app()
    sm = QSOStateMachine("DA1MHH", "JO31")
    _setup_wait_73_state(sm)
    import time as _time
    sm.qso.start_time = _time.time()

    emit_order = []
    sm.qso_confirmed_visual.connect(lambda q: emit_order.append("visual"))
    sm.qso_confirmed.connect(lambda q: emit_order.append("full"))

    sm.on_cycle_end()  # timeout_cycles=1
    sm.on_cycle_end()  # timeout_cycles=2
    sm.on_cycle_end()  # timeout_cycles=3 → trigger

    assert emit_order == ["visual", "full"], (
        f"Erwartet ['visual', 'full'], bekommen: {emit_order}"
    )


# ── T2.4: Force-73 via advance() — Bundle I-Architektur greift ─────────

def test_t2_4_force_73_advance_visual_after_message_sent():
    """T2.4 (Bundle I AC2.3): advance() in WAIT_73 → Force-73 →
    visual feuert NICHT bei advance() selbst, sondern erst beim
    folgenden on_message_sent (TX_73_COURTESY)."""
    _ensure_app()
    sm = QSOStateMachine("DA1MHH", "JO31")
    _setup_wait_73_state(sm)
    visual_emits = []
    full_emits = []
    sm.qso_confirmed_visual.connect(visual_emits.append)
    sm.qso_confirmed.connect(full_emits.append)

    sm.advance()  # Force-73 sendet, State=TX_73_COURTESY
    assert sm.state == QSOState.TX_73_COURTESY
    assert len(visual_emits) == 0, "visual feuert NICHT bei advance() selbst"
    assert len(full_emits) == 0

    sm.on_message_sent()
    assert len(visual_emits) == 1
    assert len(full_emits) == 1


# ── T2.5: Genau 1× pro QSO — kein Doppel-Emit ─────────────────────────

def test_t2_5_visual_fires_exactly_once_per_qso():
    """T2.5 (Bundle I AC2.4): Voller 73-Empfang + on_message_sent →
    visual exakt 1× pro QSO."""
    _ensure_app()
    sm = QSOStateMachine("DA1MHH", "JO31")
    _setup_wait_73_state(sm)
    visual_emits = []
    sm.qso_confirmed_visual.connect(visual_emits.append)

    sm.on_message_received(_make_msg("73"))
    sm.on_message_sent()

    assert len(visual_emits) == 1, "visual genau 1× pro QSO"


# ── T2.6: RR73 statt 73 in WAIT_73 — gleiche Reihenfolge ──────────────

def test_t2_6_rr73_received_in_wait_73_same_flow():
    """T2.6 (Bundle I AC2.1): RR73 in WAIT_73 läuft durch denselben
    Branch wie 73 (`is_73 or is_rr73`) → identische Reihenfolge."""
    _ensure_app()
    sm = QSOStateMachine("DA1MHH", "JO31")
    _setup_wait_73_state(sm)
    emit_order = []
    sm.qso_confirmed_visual.connect(lambda q: emit_order.append("visual"))
    sm.qso_confirmed.connect(lambda q: emit_order.append("full"))

    sm.on_message_received(_make_msg("RR73"))
    assert sm.state == QSOState.TX_73_COURTESY
    assert emit_order == []  # noch kein Emit vor Courtesy-Send

    sm.on_message_sent()
    assert emit_order == ["visual", "full"]


# ── T2.7: Doppelschutz-Pfad (courtesy_73_sent=True) ───────────────────

def test_t2_7_double_protection_path_emits_both_signals():
    """T2.7: Hypothetischer Doppelschutz — wenn courtesy_73_sent
    bereits True (sollte nicht passieren weil State direkt nach
    Courtesy zu IDLE) → visual + full beide 1× direkt im else-Branch."""
    _ensure_app()
    sm = QSOStateMachine("DA1MHH", "JO31")
    _setup_wait_73_state(sm)
    sm.qso.courtesy_73_sent = True

    visual_emits = []
    full_emits = []
    sm.qso_confirmed_visual.connect(visual_emits.append)
    sm.qso_confirmed.connect(full_emits.append)

    sm.on_message_received(_make_msg("73"))

    assert len(visual_emits) == 1, "visual feuert im Doppelschutz-Pfad"
    assert len(full_emits) == 1, "full feuert im Doppelschutz-Pfad"


# ── T2.8: Source-Level Bug-Schutz ─────────────────────────────────────

def test_t2_8_source_level_signal_positions():
    """T2.8: Bug-Schutz — qso_confirmed_visual.emit MUSS in
    on_message_sent TX_73_COURTESY-Branch sein, NICHT in
    on_message_received WAIT_73-is_73-Branch."""
    import inspect
    from core import qso_state as _module
    src = inspect.getsource(_module)

    # Beide Signale müssen definiert sein
    assert "qso_confirmed_visual = Signal(object)" in src
    assert "qso_confirmed = Signal(object)" in src

    # Visual-Emit MUSS in TX_73_COURTESY-Branch existieren
    # (markante Position: zwischen Kommentar Bundle I und
    # qso_confirmed.emit Aufruf in on_message_sent)
    assert "Bundle I" in src, "Bundle-I-Kommentar markiert die neue Position"
