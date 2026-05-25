"""P124 (25.05.2026) — Hash-Call '<...>' kontextuell aus aktivem QSO auflösen.

Mike's KISS-Idee: bei i3-Frame `DA1MHH <...> R+10` während aktivem QSO mit
RA9LL ist `<...>` der Hash der Gegenstation → ersetzen durch qso.their_call.

Tests:
- T1-T5: is_hash_marker (5 Cases)
- T6-T9: resolve_hash_in_msg (4 Cases)
- T10-T11: _p124_resolve_hash_if_active_qso State-Gates
- T12: End-to-end Mock — on_message_received matcht nach Resolution
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from core.message import parse_ft8_message, FT8Message
from core.qso_state import (
    HASH_MARKER,
    HASH_RESOLVE_STATES,
    QSOData,
    QSOState,
    QSOStateMachine,
    is_hash_marker,
    resolve_hash_in_msg,
)


# ---------------------------------------------------------------------------
# T1-T5: is_hash_marker
# ---------------------------------------------------------------------------


def test_t1_is_hash_marker_unresolved():
    """T1: '<...>' (ft8_lib lookup_callsign:709 unresolved Pfad) erkannt."""
    assert is_hash_marker("<...>") is True
    assert HASH_MARKER == "<...>"


def test_t2_is_hash_marker_resolved_call():
    """T2: '<RA9LL>' (ft8_lib lookup_callsign:713 resolved + add_brackets) erkannt."""
    assert is_hash_marker("<RA9LL>") is True
    assert is_hash_marker("<DA1MHH>") is True


def test_t3_is_hash_marker_plain_call():
    """T3: Echte Calls ohne Brackets sind keine Hash-Marker."""
    assert is_hash_marker("RA9LL") is False
    assert is_hash_marker("DA1MHH") is False
    assert is_hash_marker("CQ") is False


def test_t4_is_hash_marker_too_short():
    """T4: Strings < 3 Zeichen nie Hash (z.B. '<' allein)."""
    assert is_hash_marker("<") is False
    assert is_hash_marker("<>") is False
    assert is_hash_marker("") is False


def test_t5_is_hash_marker_missing_bracket():
    """T5: Nur 1 Bracket reicht nicht."""
    assert is_hash_marker("<RA9LL") is False
    assert is_hash_marker("RA9LL>") is False


# ---------------------------------------------------------------------------
# T6-T9: resolve_hash_in_msg
# ---------------------------------------------------------------------------


def test_t6_resolve_unresolved_hash():
    """T6: '<...>' Marker + valid expected_call → mutiert field2+raw, True."""
    msg = parse_ft8_message("DA1MHH <...> R+10")
    assert msg.field2 == "<...>"
    assert resolve_hash_in_msg(msg, "RA9LL") is True
    assert msg.field2 == "RA9LL"
    assert msg.raw == "DA1MHH RA9LL R+10"


def test_t7_resolve_bracketed_call():
    """T7: '<RA9LL>' (Hashtable-aufgelöst, Brackets) → Brackets weg."""
    msg = parse_ft8_message("DA1MHH <RA9LL> R+10")
    assert msg.field2 == "<RA9LL>"
    assert resolve_hash_in_msg(msg, "RA9LL") is True
    assert msg.field2 == "RA9LL"
    assert msg.raw == "DA1MHH RA9LL R+10"


def test_t8_resolve_no_hash_noop():
    """T8: Plain Call (kein Hash) → no-op, False, msg unverändert."""
    msg = parse_ft8_message("DA1MHH RA9LL R+10")
    raw_before = msg.raw
    f2_before = msg.field2
    assert resolve_hash_in_msg(msg, "EA1FLB") is False
    assert msg.field2 == f2_before
    assert msg.raw == raw_before


def test_t9_resolve_empty_expected_noop():
    """T9: Hash-Marker da, aber expected_call leer → no-op, False."""
    msg = parse_ft8_message("DA1MHH <...> R+10")
    assert resolve_hash_in_msg(msg, "") is False
    assert msg.field2 == "<...>"
    assert msg.raw == "DA1MHH <...> R+10"


# ---------------------------------------------------------------------------
# T10-T11: _p124_resolve_hash_if_active_qso — State-Gates
# ---------------------------------------------------------------------------


class _Mw:
    """Minimal-Mock für die Mixin-Methode."""

    def __init__(self, my_call: str, state: QSOState, their_call: str):
        self.settings = MagicMock()
        self.settings.callsign = my_call
        self.qso_sm = MagicMock()
        self.qso_sm.state = state
        if their_call:
            self.qso_sm.qso = QSOData(their_call=their_call)
        else:
            self.qso_sm.qso = None
        # Methode aus Mixin importieren
        from ui.mw_cycle import CycleMixin
        self._impl = CycleMixin._p124_resolve_hash_if_active_qso.__get__(self, _Mw)


def test_t10_resolve_idle_state_no_op():
    """T10: State IDLE → no Resolution (kein aktiver QSO-Kontext)."""
    mw = _Mw(my_call="DA1MHH", state=QSOState.IDLE, their_call="RA9LL")
    msg = parse_ft8_message("DA1MHH <...> R+10")
    assert mw._impl(msg) is False
    assert msg.field2 == "<...>"


def test_t11_resolve_wait_report_state_resolves():
    """T11: State WAIT_REPORT + Hash + qso.their_call → Resolution greift."""
    mw = _Mw(my_call="DA1MHH", state=QSOState.WAIT_REPORT, their_call="RA9LL")
    msg = parse_ft8_message("DA1MHH <...> R+10")
    assert mw._impl(msg) is True
    assert msg.field2 == "RA9LL"
    assert msg.raw == "DA1MHH RA9LL R+10"


def test_t11b_resolve_cq_wait_no_op():
    """T11b: State CQ_WAIT → kein Resolution (Mike-Spec: nur in aktivem QSO)."""
    mw = _Mw(my_call="DA1MHH", state=QSOState.CQ_WAIT, their_call="")
    msg = parse_ft8_message("DA1MHH <...> R+10")
    assert mw._impl(msg) is False


def test_t11c_resolve_target_not_me_no_op():
    """T11c: msg.target != my_call → no Resolution (an andere adressiert)."""
    mw = _Mw(my_call="DA1MHH", state=QSOState.WAIT_REPORT, their_call="RA9LL")
    msg = parse_ft8_message("EA1FLB <...> R+10")
    assert mw._impl(msg) is False
    assert msg.field2 == "<...>"


def test_t11d_resolve_no_qso_no_op():
    """T11d: qso ist None → no Resolution."""
    mw = _Mw(my_call="DA1MHH", state=QSOState.WAIT_REPORT, their_call="")
    msg = parse_ft8_message("DA1MHH <...> R+10")
    assert mw._impl(msg) is False


def test_t11e_all_resolve_states_covered():
    """T11e: alle States in HASH_RESOLVE_STATES triggern Resolution."""
    for state in HASH_RESOLVE_STATES:
        mw = _Mw(my_call="DA1MHH", state=state, their_call="RA9LL")
        msg = parse_ft8_message("DA1MHH <...> R+10")
        assert mw._impl(msg) is True, f"State {state.name} sollte resolven"


# ---------------------------------------------------------------------------
# T12: End-to-end — on_message_received matcht nach Resolution
# ---------------------------------------------------------------------------


def test_t12_end_to_end_state_machine_match_after_resolution():
    """T12 (R1-F3): Echter Bug-Fix-Beweis.

    Sequenz:
    1. State-Machine in WAIT_REPORT mit qso.their_call="RA9LL"
    2. Decoded msg: `DA1MHH <...> R+10` (Hash unresolved)
    3. Vor Resolution: on_message_received würde mismatch → return
    4. Nach Resolution: msg.caller == 'RA9LL' == qso.their_call → R-Report
       wird verarbeitet, State wechselt zu TX_RR73
    """
    sm = QSOStateMachine(my_call="DA1MHH", my_grid="JO31")
    sm.start_qso(their_call="RA9LL", their_grid="LO63", freq_hz=1500,
                 their_snr=-10)
    # State-Machine setzt sich auf TX_CALL → simuliere TX-Abschluss via
    # on_message_sent zu WAIT_REPORT
    sm.on_message_sent()
    assert sm.state == QSOState.WAIT_REPORT, (
        f"erwarte WAIT_REPORT, ist {sm.state.name}")

    # Hash-Frame reinkommend
    msg = parse_ft8_message("DA1MHH <...> R+10")
    msg.snr = -10

    # OHNE Resolution: caller mismatch, on_message_received verwirft
    # (Z. 604 if msg.caller != self.qso.their_call: return)
    # MIT Resolution: caller wird "RA9LL" → match → R-Report verarbeitet
    assert resolve_hash_in_msg(msg, sm.qso.their_call) is True

    # Signal-Capture für send_message + state-Wechsel
    sent_messages = []
    sm.send_message.connect(lambda m: sent_messages.append(m))

    sm.on_message_received(msg)

    # Erwartung: State wechselt zu TX_RR73, RR73 wird gesendet
    assert sm.state == QSOState.TX_RR73, (
        f"erwarte TX_RR73, ist {sm.state.name}")
    assert len(sent_messages) == 1
    assert sent_messages[0] == "RA9LL DA1MHH RR73"
