"""Tests fuer P1.10 End-of-QSO Icom-73-Loop-Fix (v0.95.4).

Bug: IC-7300 (DA1TST) sendet nach Empfang unseres RR73 + Senden seines 73
weiter 5x 73 in den Folgeslots, weil seine Auto-Sequence auf abschliessendes
Hoeflichkeits-73 von uns wartet. SimpleFT8 sendet bisher kein Courtesy-73.

Fix: in WAIT_73 + 73/RR73-Empfang -> einmaliges Courtesy-73 senden, neuer
State TX_73_COURTESY, Counter qso.courtesy_73_sent, on_message_sent-Branch
ruft qso_confirmed.emit + _resume_cq_if_needed.

Tests decken (13 Tests):
1-2: Courtesy-73 senden bei 73 oder RR73 in WAIT_73
3:   Counter-Schutz gegen Doppel-Senden
4-5: on_message_sent in TX_73_COURTESY (cq_mode=True/False)
6-7: Doppel-ADIF-Schutz (qso_complete genau 1x)
8:   WAIT_73-Timeout 3 Slots ohne 73 unveraendert
9:   Slot-Paritaet (R1 KP1)
10:  Doppel-73 in TX_73_COURTESY-State faellt durch
11:  Vorwaertssprung WAIT_REPORT+RR73 -> kein Doppel-ADIF (defensiv)
12:  RR73 waehrend TX_73_COURTESY faellt durch (Plan-R1 F3)
13:  R-Report-Hoeflichkeits-Pfad in WAIT_73 unveraendert (Plan-R1 F5)
"""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from core.qso_state import QSOStateMachine, QSOState, QSOData
from core.message import FT8Message


def _ensure_app():
    return QApplication.instance() or QApplication([])


def _make_73_msg(caller="DA1TST", target="DA1MHH", tx_even=False, freq=1500):
    """FT8Message mit '73' (z.B. 'DA1MHH DA1TST 73')."""
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


def _make_rr73_msg(caller="DA1TST", target="DA1MHH", tx_even=False, freq=1500):
    """FT8Message mit 'RR73'."""
    msg = FT8Message(
        raw=f"{target} {caller} RR73",
        field1=target,
        field2=caller,
        field3="RR73",
        snr=-15,
        freq_hz=freq,
    )
    msg._tx_even = tx_even
    return msg


def _setup_wait_73_state(sm: QSOStateMachine, their_call="DA1TST",
                         their_grid="JN66", cq_mode=True, was_cq=False):
    """SM in WAIT_73 versetzen mit aktivem QSO."""
    sm.cq_mode = cq_mode
    sm._was_cq = was_cq
    sm.qso = QSOData(
        their_call=their_call,
        their_grid=their_grid,
        freq_hz=1500,
        start_time=1700000000.0,
        timeout_cycles=0,
    )
    sm._set_state(QSOState.WAIT_73)


# Test 1+2: Courtesy-73 senden bei 73 oder RR73 ────────────────────


def test_wait_73_with_73_sends_courtesy_73():
    """P1.10: WAIT_73 + 73 -> Courtesy-73 gesendet, State=TX_73_COURTESY."""
    _ensure_app()
    sm = QSOStateMachine("DA1MHH", "JO31")
    _setup_wait_73_state(sm)
    sent = []
    sm.send_message.connect(sent.append)

    msg = _make_73_msg()
    sm.on_message_received(msg)

    assert len(sent) == 1
    assert sent[0] == "DA1TST DA1MHH 73"
    assert sm.qso.courtesy_73_sent is True
    assert sm.state == QSOState.TX_73_COURTESY


def test_wait_73_with_rr73_sends_courtesy_73():
    """P1.10: WAIT_73 + RR73 -> ebenfalls Courtesy-73."""
    _ensure_app()
    sm = QSOStateMachine("DA1MHH", "JO31")
    _setup_wait_73_state(sm)
    sent = []
    sm.send_message.connect(sent.append)

    msg = _make_rr73_msg()
    sm.on_message_received(msg)

    assert len(sent) == 1
    assert sent[0] == "DA1TST DA1MHH 73"
    assert sm.qso.courtesy_73_sent is True
    assert sm.state == QSOState.TX_73_COURTESY


# Test 3: Counter-Schutz ────────────────────────────────────────────


def test_courtesy_73_only_once_per_qso():
    """P1.10: Doppel-73 in WAIT_73 -> nur 1x Courtesy-73 (Counter-Schutz).

    Hypothetisches Szenario: nach Courtesy-73 wird zurueck in WAIT_73 gewechselt
    (sollte nicht passieren, aber Counter muss schuetzen). Der else-Branch
    ruft _resume_cq_if_needed -> _send_cq -> CQ-Sendung. Das ist KORREKT.
    Wichtig ist nur: KEIN zweites '73'-Send.
    """
    _ensure_app()
    sm = QSOStateMachine("DA1MHH", "JO31")
    _setup_wait_73_state(sm)
    sent = []
    sm.send_message.connect(sent.append)

    # Erstes 73 -> Courtesy-73 + State-Wechsel zu TX_73_COURTESY
    sm.on_message_received(_make_73_msg())
    assert len(sent) == 1
    assert sent[0] == "DA1TST DA1MHH 73"
    assert sm.state == QSOState.TX_73_COURTESY

    # Hypothetisch: zurueck nach WAIT_73 (sollte nicht passieren, aber
    # courtesy_73_sent muss schuetzen)
    sm._set_state(QSOState.WAIT_73)
    sm.on_message_received(_make_73_msg())
    # KEIN zweites Courtesy-73 — nur 1 '73'-Send insgesamt
    assert sent.count("DA1TST DA1MHH 73") == 1
    # else-Branch hat _resume_cq_if_needed gerufen -> CQ ist OK
    assert any(s.startswith("CQ ") for s in sent)


# Test 4-5: on_message_sent in TX_73_COURTESY ──────────────────────


def test_tx_73_courtesy_finished_with_cq_mode_resumes_cq():
    """P1.10: on_message_sent in TX_73_COURTESY + cq_mode=True ->
    qso_confirmed + _send_cq -> State=CQ_CALLING."""
    _ensure_app()
    sm = QSOStateMachine("DA1MHH", "JO31")
    _setup_wait_73_state(sm, cq_mode=True)
    sm.qso.courtesy_73_sent = True  # simulate Courtesy-73 wurde gesendet
    sm._set_state(QSOState.TX_73_COURTESY)

    confirmed = []
    sent = []
    sm.qso_confirmed.connect(confirmed.append)
    sm.send_message.connect(sent.append)

    sm.on_message_sent()

    assert len(confirmed) == 1
    assert sm.state == QSOState.CQ_CALLING
    # _send_cq wurde aufgerufen
    assert any(s.startswith("CQ ") for s in sent)


def test_tx_73_courtesy_finished_without_cq_mode_goes_idle():
    """P1.10: on_message_sent in TX_73_COURTESY + cq_mode=False + _was_cq=False
    -> qso_confirmed + State=IDLE.

    Wichtig: BEIDE flags muessen False sein, sonst _resume_cq_if_needed
    interpretiert _was_cq als 'CQ-Modus war aktiv -> CQ resumieren'.
    """
    _ensure_app()
    sm = QSOStateMachine("DA1MHH", "JO31")
    _setup_wait_73_state(sm, cq_mode=False, was_cq=False)
    sm.qso.courtesy_73_sent = True
    sm._set_state(QSOState.TX_73_COURTESY)

    confirmed = []
    sm.qso_confirmed.connect(confirmed.append)

    sm.on_message_sent()

    assert len(confirmed) == 1
    assert sm.state == QSOState.IDLE


# Test 6-7: Doppel-ADIF-Schutz ─────────────────────────────────────


def test_qso_complete_fires_once_during_full_cq_qso_cycle():
    """P1.10: qso_complete.emit feuert genau 1x pro QSO (TX_RR73 only,
    NICHT in TX_73_COURTESY)."""
    _ensure_app()
    sm = QSOStateMachine("DA1MHH", "JO31")
    _setup_wait_73_state(sm)

    completes = []
    sm.qso_complete.connect(completes.append)

    # Phase 1: TX_RR73 -> on_message_sent
    sm._set_state(QSOState.TX_RR73)
    sm.on_message_sent()
    assert len(completes) == 1
    assert sm.state == QSOState.WAIT_73

    # Phase 2: 73-Empfang -> Courtesy-73-Sequenz
    sm.on_message_received(_make_73_msg())
    assert sm.state == QSOState.TX_73_COURTESY
    sm.on_message_sent()  # Courtesy-73 fertig

    # qso_complete sollte NICHT erneut feuern
    assert len(completes) == 1


def test_qso_confirmed_fires_once_after_courtesy_73():
    """P1.10: qso_confirmed.emit feuert genau 1x — nach Courtesy-73-Senden."""
    _ensure_app()
    sm = QSOStateMachine("DA1MHH", "JO31")
    _setup_wait_73_state(sm)

    confirmed = []
    sm.qso_confirmed.connect(confirmed.append)

    # 73-Empfang -> Courtesy-73 (qso_confirmed darf NICHT direkt feuern)
    sm.on_message_received(_make_73_msg())
    assert len(confirmed) == 0  # noch nicht — erst nach Send

    # Courtesy-73-TX fertig -> qso_confirmed feuert
    sm.on_message_sent()
    assert len(confirmed) == 1


# Test 8: WAIT_73-Timeout unveraendert ──────────────────────────────


def test_wait_73_timeout_without_73_unchanged():
    """P1.10: WAIT_73-Timeout 3 Slots ohne 73 -> bisheriges Verhalten."""
    _ensure_app()
    sm = QSOStateMachine("DA1MHH", "JO31")
    _setup_wait_73_state(sm)

    confirmed = []
    sent = []
    sm.qso_confirmed.connect(confirmed.append)
    sm.send_message.connect(sent.append)

    # 3x on_cycle_end ohne 73-Empfang -> Timeout-Pfad
    for _ in range(3):
        sm.on_cycle_end()

    # Bisheriges Verhalten: qso_confirmed + _resume_cq, kein Courtesy-73
    assert len(confirmed) == 1
    assert sm.qso.courtesy_73_sent is False  # nicht gesetzt
    # _send_cq wurde aufgerufen (cq_mode=True)
    assert any(s.startswith("CQ ") for s in sent)


# Test 9: Slot-Paritaet (R1 KP1) ───────────────────────────────────


def test_courtesy_73_slot_parity_via_signal():
    """P1.10: tx_slot_for_partner.emit(msg) wird mit dem 73-msg gefeuert,
    damit mw_qso encoder.tx_even = not msg._tx_even setzt.

    Hinweis: Dieser Unit-Test prueft NUR die Signal-Emission.
    Der Effekt auf encoder.tx_even wird in Integration durch mw_qso
    `_on_tx_slot_for_partner` (mw_qso.py:425+) angewendet.
    Field-Test bestaetigt korrekten EVEN-Slot fuer Courtesy-73.
    """
    _ensure_app()
    sm = QSOStateMachine("DA1MHH", "JO31")
    _setup_wait_73_state(sm)

    slot_msgs = []
    sm.tx_slot_for_partner.connect(slot_msgs.append)

    msg = _make_73_msg(tx_even=False)
    sm.on_message_received(msg)

    assert len(slot_msgs) == 1
    assert slot_msgs[0] is msg
    assert getattr(slot_msgs[0], "_tx_even", None) is False


# Test 10: Doppel-73 in TX_73_COURTESY ─────────────────────────────


def test_second_73_in_tx_73_courtesy_state_falls_through():
    """P1.10: 73 waehrend TX_73_COURTESY -> kein Trigger, State unveraendert."""
    _ensure_app()
    sm = QSOStateMachine("DA1MHH", "JO31")
    _setup_wait_73_state(sm)

    sent = []
    sm.send_message.connect(sent.append)

    # Erstes 73 -> Courtesy-73 + TX_73_COURTESY
    sm.on_message_received(_make_73_msg())
    assert sm.state == QSOState.TX_73_COURTESY
    initial_sent = len(sent)

    # Zweites 73 waehrend TX_73_COURTESY
    sm.on_message_received(_make_73_msg())

    # Kein zusaetzlicher Send, State bleibt TX_73_COURTESY
    assert len(sent) == initial_sent
    assert sm.state == QSOState.TX_73_COURTESY


# Test 11: Vorwaertssprung ohne Doppel-ADIF (defensiv) ─────────────


def test_forward_jump_wait_report_rr73_no_double_adif():
    """P1.10: Vorwaertssprung WAIT_REPORT + RR73 -> TX_RR73 sendet '73' + ADIF.
    Spaetere 73-Empfang in WAIT_73 -> Courtesy-73 (ADIF NICHT erneut).
    Sicherheit gegen Doppel-ADIF auch bei Sprung-Pfad.

    Hunt-Modus (cq_mode=False) damit qso_confirmed _resume_cq=False
    -> State=IDLE statt CQ_CALLING (kein Test-Stoerer).
    """
    _ensure_app()
    sm = QSOStateMachine("DA1MHH", "JO31")
    sm.cq_mode = False
    sm._was_cq = False
    sm.qso = QSOData(
        their_call="DA1TST",
        their_grid="JN66",
        freq_hz=1500,
        start_time=1700000000.0,
    )
    sm._set_state(QSOState.WAIT_REPORT)

    completes = []
    sm.qso_complete.connect(completes.append)

    # Vorwaertssprung: RR73 in WAIT_REPORT -> TX_RR73 + sende '73'
    rr73 = _make_rr73_msg()
    sm.on_message_received(rr73)
    assert sm.state == QSOState.TX_RR73

    # TX_RR73 fertig -> qso_complete (= ADIF)
    sm.on_message_sent()
    assert len(completes) == 1
    assert sm.state == QSOState.WAIT_73

    # In WAIT_73 — 73 -> Courtesy-73-Pfad
    sm.on_message_received(_make_73_msg())
    assert sm.state == QSOState.TX_73_COURTESY

    # Courtesy-73 fertig -> qso_confirmed, KEIN zweites qso_complete
    sm.on_message_sent()
    assert len(completes) == 1


# Test 12: RR73 waehrend TX_73_COURTESY (Plan-R1 F3) ──────────────


def test_second_rr73_in_tx_73_courtesy_state_falls_through():
    """P1.10 (R1 F3): RR73 waehrend TX_73_COURTESY -> kein Trigger,
    State unveraendert. Symmetrisch zu Test 10 (73 in TX_73_COURTESY)."""
    _ensure_app()
    sm = QSOStateMachine("DA1MHH", "JO31")
    _setup_wait_73_state(sm)

    sent = []
    sm.send_message.connect(sent.append)

    # Erstes 73 -> Courtesy-73 + TX_73_COURTESY
    sm.on_message_received(_make_73_msg())
    assert sm.state == QSOState.TX_73_COURTESY
    initial_sent = len(sent)

    # RR73 waehrend TX_73_COURTESY
    sm.on_message_received(_make_rr73_msg())

    # Kein zusaetzlicher Send, State bleibt TX_73_COURTESY
    assert len(sent) == initial_sent
    assert sm.state == QSOState.TX_73_COURTESY


# Test 13: R-Report-Hoeflichkeits-Pfad in WAIT_73 unveraendert (R1 F5)


def test_wait_73_with_r_report_before_73_unchanged():
    """P1.10 (R1 F5): WAIT_73 + R-Report (Hoeflichkeits-Pfad) bleibt
    unveraendert nach P1.10. Courtesy-73 wird NICHT getriggert weil
    is_r_report nicht is_73."""
    _ensure_app()
    sm = QSOStateMachine("DA1MHH", "JO31")
    _setup_wait_73_state(sm)

    sent = []
    sm.send_message.connect(sent.append)

    # R-Report (z.B. R-15) -> Hoeflichkeits-RR73-Retry-Pfad (Z.587-596)
    r_report_msg = FT8Message(
        raw="DA1MHH DA1TST R-15",
        field1="DA1MHH",
        field2="DA1TST",
        field3="R-15",
        snr=-15,
        freq_hz=1500,
    )
    sm.on_message_received(r_report_msg)

    # Erwartet: RR73-Retry, NICHT Courtesy-73
    assert len(sent) == 1
    assert sent[0] == "DA1TST DA1MHH RR73"
    assert sm.qso.rr73_retries == 1
    # courtesy_73_sent bleibt False (Pfad nicht durchlaufen)
    assert sm.qso.courtesy_73_sent is False
    # State bleibt WAIT_73 (Hoeflichkeits-Retry setzt KEIN _set_state)
    assert sm.state == QSOState.WAIT_73
