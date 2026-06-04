"""v0.99.5 — WAIT_73-Horchphase verkürzt (Schwelle 3 → WAIT_73_MAX_CYCLES = 2).

Nach dem Senden von RR73 ist das QSO bereits geloggt (qso_complete in TX_RR73).
WAIT_73 horcht danach nur noch auf ein optionales 73 / einen wiederholten
R-Report (Nachsende-Schutz). Früher 3 Leer-Slots (45 s), jetzt 2 (30 s) —
WSJT-X-konform (verkürzter Modus beobachtet genau 1 Empfangs-Slot nach RR73).

KRITISCH (Off-by-one, FEATURES §24): „2" ist die Untergrenze. on_cycle_end
zählt am Slot-START; der erste RX-Slot (in dem das 73 der Gegenstation kommt)
wird am Slot-ENDE dekodiert. Mit Schwelle 2 ist die Maschine bei tc=1 noch in
WAIT_73 → das 73 wird via on_message_received gefangen. Mit Schwelle 1 würde
on_cycle_end am ersten Slot-START schon triggern (Zustand verlassen) → das 73
fiele in den IDLE-Branch und das Höflichkeits-73 + Nachsende-Schutz gingen
verloren. Test 4 sichert genau das ab.
"""

import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import time

from PySide6.QtWidgets import QApplication

from core.qso_state import (
    QSOStateMachine, QSOState, QSOData, WAIT_73_MAX_CYCLES,
)
from core.message import FT8Message


def _ensure_app():
    return QApplication.instance() or QApplication([])


def _setup_wait_73(sm: QSOStateMachine, their_call="DA1TST"):
    """SM in WAIT_73 (QSO bereits geloggt), CQ-Resume aus → Trigger mündet IDLE."""
    sm.cq_mode = False
    sm._was_cq = False
    sm.qso = QSOData(
        their_call=their_call,
        their_grid="JN66",
        freq_hz=1500,
        start_time=time.time(),
        timeout_cycles=0,
    )
    sm._set_state(QSOState.WAIT_73)


def _make_73(caller="DA1TST", target="DA1MHH"):
    msg = FT8Message(
        raw=f"{target} {caller} 73",
        field1=target,
        field2=caller,
        field3="73",
        snr=-15,
        freq_hz=1500,
    )
    msg._tx_even = False
    return msg


def test_threshold_constant_is_two():
    """Dokumentiert + sichert den Wert. Wer ihn ändert, ändert bewusst auch
    diesen Test (verhindert versehentliches Zurückdrehen auf 1 oder 3)."""
    assert WAIT_73_MAX_CYCLES == 2


def test_no_trigger_before_threshold():
    """Vor Erreichen der Schwelle KEIN qso_confirmed, State bleibt WAIT_73."""
    _ensure_app()
    sm = QSOStateMachine("DA1MHH", "JO31")
    _setup_wait_73(sm)
    confirmed = []
    sm.qso_confirmed.connect(confirmed.append)

    for _ in range(WAIT_73_MAX_CYCLES - 1):
        sm.on_cycle_end()

    assert len(confirmed) == 0
    assert sm.state == QSOState.WAIT_73


def test_trigger_exactly_at_threshold():
    """Genau bei WAIT_73_MAX_CYCLES Leer-Slots → qso_confirmed genau 1×."""
    _ensure_app()
    sm = QSOStateMachine("DA1MHH", "JO31")
    _setup_wait_73(sm)
    confirmed = []
    sm.qso_confirmed.connect(confirmed.append)

    for _ in range(WAIT_73_MAX_CYCLES):
        sm.on_cycle_end()

    assert len(confirmed) == 1
    # cq_mode=False, _was_cq=False → _resume_cq_if_needed mündet in IDLE
    assert sm.state == QSOState.IDLE


def test_73_still_caught_in_first_rx_slot():
    """Off-by-one-GARANTIE: nach (Schwelle−1) Leer-Slots ist die Maschine noch
    in WAIT_73 → ein 73 der Gegenstation (im ersten RX-Slot, am Slot-Ende
    dekodiert) wird gefangen und löst das Höflichkeits-73 aus, statt ignoriert
    zu werden. Bei Schwelle 1 wäre nach dem ersten on_cycle_end schon getriggert
    → dieser Test würde fehlschlagen (State nicht TX_73_COURTESY)."""
    _ensure_app()
    sm = QSOStateMachine("DA1MHH", "JO31")
    _setup_wait_73(sm)
    sent = []
    sm.send_message.connect(sent.append)

    # Realer Ablauf: in Slot N senden wir RR73 (tc=0). Am START von Slot N+1
    # läuft GENAU EIN on_cycle_end (tc=1). Am ENDE von Slot N+1 dekodiert der
    # Decoder das 73 der Gegenstation. → Mit Schwelle 2 ist die Maschine bei
    # tc=1 noch in WAIT_73; mit Schwelle 1 wäre sie nach diesem einen Aufruf
    # schon getriggert (State verlassen) und der folgende Test-Assert bräche.
    sm.on_cycle_end()
    assert sm.state == QSOState.WAIT_73, (
        "nach dem ersten Slot-Start (tc=1) MUSS WAIT_73 noch aktiv sein — "
        "sonst verpasst die verkürzte Phase das 73 (Schwelle zu niedrig)"
    )

    # Jetzt kommt (wie am Slot-ENDE dekodiert) das 73 der Gegenstation.
    sm.on_message_received(_make_73())

    assert sm.state == QSOState.TX_73_COURTESY, "73 muss gefangen werden"
    assert sm.qso.courtesy_73_sent is True
    assert any(s.endswith("73") for s in sent), "Höflichkeits-73 gesendet"
