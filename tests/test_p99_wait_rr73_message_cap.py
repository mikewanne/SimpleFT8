"""P99 (v0.97.95) — WAIT_RR73 Message-Pfade gegen rr73_retries cappen.

Bisher (vor P99): drei message-getriebene Schleifen-Vektoren im
WAIT_RR73-Branch (`is_r_report`, `is_report`, `is_grid`) liefen
unbegrenzt — nur der 3-Min-Gesamttimeout (MAX_QSO_DURATION=180s)
bremste.

P99-Spec (Folge-Ticket aus P98 Final-R1): alle 3 Pfade gegen den
gemeinsamen Counter `rr73_retries` (Pattern aus on_decoder_finished
Z.429-444) cappen, mit `MAX_RR73_RETRIES = 5`. RR73/73-Pfad
unverändert (QSO erfolgreich, kein Counter).

DeepSeek R1 (V4-pro 23.05.2026) bestätigt Architektur:
- 🟢 Gemeinsamer Counter `rr73_retries`
- 🟢 Inkrement VOR send, Cap-Check `> MAX_RR73_RETRIES`
- 🟢 Standard-Timeout-Cleanup (_set_state + emit + _resume_cq)
- 🟡 Harte Grenze kann auch gültige Antwort blockieren — akzeptiert

T1: 5× R-Report erlaubt, 6. → TIMEOUT
T2: 5× Plain-Report erlaubt, 6. → TIMEOUT
T3: 5× Grid erlaubt, 6. → TIMEOUT
T4: Mixed-Pfade addieren auf gemeinsamen Counter
T5: RR73/73 unverändert — kein Counter-Increment
"""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from core.qso_state import QSOStateMachine, QSOState, MAX_RR73_RETRIES
from core.message import FT8Message


def _make_msg(field1: str, field2: str, field3: str) -> FT8Message:
    """Echte FT8Message-Instanz statt Mock — Properties wie is_r_report,
    is_report, is_grid, is_rr73, is_73 leiten sich aus field3 ab.
    """
    return FT8Message(
        raw=f"{field1} {field2} {field3}",
        field1=field1, field2=field2, field3=field3,
    )


def _make_sm() -> QSOStateMachine:
    """Saubere StateMachine in WAIT_RR73 mit Test-Call."""
    sm = QSOStateMachine("DA1MHH", "JO31")
    sm.state = QSOState.WAIT_RR73
    sm.qso.their_call = "DA1TST"
    sm.qso.our_snr = "R-15"
    sm.qso.rr73_retries = 0
    return sm


# ── T1 — 5× R-Report erlaubt, 6. → TIMEOUT ──────────────────────────

def test_t1_r_report_cap_5_then_timeout():
    """DG8DBW-Pfad: Gegenstation sendet wiederholt R-Report."""
    sm = _make_sm()
    sent: list[str] = []
    timeouts: list[str] = []
    sm.send_message.connect(lambda m: sent.append(m))
    sm.qso_timeout.connect(lambda c: timeouts.append(c))

    # 5 R-Reports → 5 advance()-Calls = 5 RR73-Sends
    for i in range(MAX_RR73_RETRIES):
        sm.state = QSOState.WAIT_RR73  # advance wechselt auf TX_RR73
        msg = _make_msg("DA1MHH", "DA1TST", "R-12")
        sm.on_message_received(msg)
        assert sm.qso.rr73_retries == i + 1
    assert len(sent) == MAX_RR73_RETRIES, "5 RR73-Sends erlaubt"
    assert len(timeouts) == 0, "Noch kein Timeout"

    # 6. R-Report → Counter > MAX_RR73_RETRIES → TIMEOUT.
    # `_resume_cq_if_needed` schaltet im Test-Setup (kein CQ-Mode) das
    # State sofort TIMEOUT → IDLE weiter — wir prüfen primär das
    # Signal + dass kein weiterer Send rausging.
    sm.state = QSOState.WAIT_RR73
    sm.on_message_received(_make_msg("DA1MHH", "DA1TST", "R-12"))
    assert len(timeouts) == 1
    assert timeouts[0] == "DA1TST"
    assert len(sent) == MAX_RR73_RETRIES, "Kein weiterer Send nach Timeout"


# ── T2 — 5× Plain-Report erlaubt, 6. → TIMEOUT ──────────────────────

def test_t2_plain_report_repeat_cap_5_then_timeout():
    """Gegenstation wiederholt Report ohne R-Prefix (z.B. -08)."""
    sm = _make_sm()
    sent: list[str] = []
    timeouts: list[str] = []
    sm.send_message.connect(lambda m: sent.append(m))
    sm.qso_timeout.connect(lambda c: timeouts.append(c))

    for i in range(MAX_RR73_RETRIES):
        sm.state = QSOState.WAIT_RR73
        sm.on_message_received(_make_msg("DA1MHH", "DA1TST", "-08"))
        assert sm.qso.rr73_retries == i + 1
    assert len(sent) == MAX_RR73_RETRIES
    assert len(timeouts) == 0

    sm.state = QSOState.WAIT_RR73
    sm.on_message_received(_make_msg("DA1MHH", "DA1TST", "-08"))
    assert len(timeouts) == 1
    assert timeouts[0] == "DA1TST"
    assert len(sent) == MAX_RR73_RETRIES


# ── T3 — 5× Grid erlaubt, 6. → TIMEOUT ──────────────────────────────

def test_t3_grid_repeat_cap_5_then_timeout():
    """Gegenstation wiederholt Grid → wir senden Report nochmal."""
    sm = _make_sm()
    sent: list[str] = []
    timeouts: list[str] = []
    sm.send_message.connect(lambda m: sent.append(m))
    sm.qso_timeout.connect(lambda c: timeouts.append(c))

    for i in range(MAX_RR73_RETRIES):
        sm.state = QSOState.WAIT_RR73
        sm.on_message_received(_make_msg("DA1MHH", "DA1TST", "JN58"))
        assert sm.qso.rr73_retries == i + 1
    assert len(sent) == MAX_RR73_RETRIES

    sm.state = QSOState.WAIT_RR73
    sm.on_message_received(_make_msg("DA1MHH", "DA1TST", "JN58"))
    assert len(timeouts) == 1
    assert timeouts[0] == "DA1TST"


# ── T4 — Mixed-Pfade addieren auf gemeinsamen Counter ───────────────

def test_t4_mixed_paths_share_counter():
    """3× R-Report + 2× Plain-Report = 5 Sends. 6. (Grid) → TIMEOUT."""
    sm = _make_sm()
    sent: list[str] = []
    timeouts: list[str] = []
    sm.send_message.connect(lambda m: sent.append(m))
    sm.qso_timeout.connect(lambda c: timeouts.append(c))

    # 3× R-Report
    for _ in range(3):
        sm.state = QSOState.WAIT_RR73
        sm.on_message_received(_make_msg("DA1MHH", "DA1TST", "R-05"))
    assert sm.qso.rr73_retries == 3
    # 2× Plain-Report
    for _ in range(2):
        sm.state = QSOState.WAIT_RR73
        sm.on_message_received(_make_msg("DA1MHH", "DA1TST", "-10"))
    assert sm.qso.rr73_retries == 5
    assert len(sent) == 5
    assert len(timeouts) == 0

    # 6. (Grid) → Counter geht auf 6, TIMEOUT greift
    sm.state = QSOState.WAIT_RR73
    sm.on_message_received(_make_msg("DA1MHH", "DA1TST", "JN58"))
    assert len(timeouts) == 1
    assert timeouts[0] == "DA1TST"
    assert sm.qso.rr73_retries == 6
    assert len(sent) == 5, "Kein weiterer Send nach Timeout"


# ── T5 — RR73/73 unverändert, kein Counter-Increment ────────────────

def test_t5_rr73_does_not_increment_counter():
    """is_rr73 oder is_73 = QSO erfolgreich → kein Counter-Touch."""
    sm = _make_sm()
    # Counter künstlich auf 5 — würde bei einem 6. inkrement Timeout geben.
    sm.qso.rr73_retries = 5

    advances: list[bool] = []
    # advance() wird im WAIT_RR73-Pfad nicht gemockt — wir prüfen via
    # State-Wechsel und qso_complete-Signal.
    completed: list[str] = []
    sm.qso_complete.connect(lambda c: completed.append(c))
    timeouts: list[str] = []
    sm.qso_timeout.connect(lambda c: timeouts.append(c))

    sm.on_message_received(_make_msg("DA1MHH", "DA1TST", "RR73"))
    # advance() ruft _set_state und qso_complete.emit — Counter
    # unverändert, kein Timeout.
    assert sm.qso.rr73_retries == 5, "RR73-Empfang darf Counter nicht ändern"
    assert len(timeouts) == 0, "Kein Timeout bei erfolgreichem QSO"
