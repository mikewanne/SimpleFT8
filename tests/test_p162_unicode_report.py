"""P162 (30.05.2026): EG5SUN-Field-Bug — typografisches Minus im Rapport.

Mike-Field-Bug 30.05.: Auto-Hunt rief EG5SUN (sehr schwache Station, -25 dB).
EG5SUN bestaetigte mit einem R-Report, aber statt RR73 zu senden wiederholte
die App 5x stur den eigenen Rapport -> Timeout, QSO verloren.

Root Cause: Der Decode-String enthielt ein typografisches Minus U+2212 ('-')
statt eines ASCII-Bindestrichs. `int("-12")` (Unicode) wirft ValueError ->
`is_report` war False -> der R-Report wurde von KEINEM State-Block in
`on_message_received` verarbeitet -> der Slot-Ende-Retry (`on_decoder_finished`)
wiederholte stur den eigenen Rapport ohne R-Praefix.

Fix (core/message.py:is_report): typografisches Minus -> ASCII normalisieren
BEVOR int() prueft. Damit erkennt der bestehende WAIT_REPORT-R-Report-Pfad den
Rapport korrekt und sendet RR73.

Diese Tests reproduzieren den Bug end-to-end durch die State-Machine.
"""
import pytest
from PySide6.QtWidgets import QApplication
from core.qso_state import QSOStateMachine, QSOState
from core.message import parse_ft8_message

UNICODE_MINUS = "−"  # '-' typografisches Minus (sieht aus wie ASCII '-')


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def sm(qapp):
    m = QSOStateMachine(my_call="DA1MHH", my_grid="JO31")
    sent = []
    m.send_message.connect(lambda msg: sent.append(msg))
    m._sent = sent
    return m


# ── Parser-Ebene: typografisches Minus wird normalisiert ──────────────

def test_parser_ascii_r_report():
    m = parse_ft8_message("DA1MHH EG5SUN R-12")
    assert m.is_report is True
    assert m.is_r_report is True


def test_parser_unicode_r_report_is_recognized():
    # DER BUG: vor dem Fix war is_report hier False
    raw = f"DA1MHH EG5SUN R{UNICODE_MINUS}12"
    m = parse_ft8_message(raw)
    assert m.is_report is True, "Unicode-Minus R-Report muss als Report erkannt werden"
    assert m.is_r_report is True, "Unicode-Minus R-Report muss als R-Report erkannt werden"


def test_parser_unicode_plain_report_is_recognized():
    raw = f"DA1MHH EG5SUN {UNICODE_MINUS}25"
    m = parse_ft8_message(raw)
    assert m.is_report is True
    assert m.is_r_report is False


def test_parser_grid_still_not_report():
    # Regression: Grid (mit Ziffern, ohne Vorzeichen) bleibt KEIN Report
    m = parse_ft8_message("DA1MHH EG5SUN JN65")
    assert m.is_report is False
    assert m.is_grid is True


def test_parser_rr73_still_not_report():
    m = parse_ft8_message("DA1MHH EG5SUN RR73")
    assert m.is_report is False
    assert m.is_rr73 is True


# ── State-Machine end-to-end: EG5SUN-Szenario ─────────────────────────

def test_eg5sun_unicode_r_report_sends_rr73(sm):
    """Kern-Reproduktion: WAIT_REPORT + Unicode-R-Report -> RR73 (nicht -25)."""
    sm.start_qso(their_call="EG5SUN", their_grid="IM99", freq_hz=1000)
    sm.on_message_sent()  # TX_CALL -> WAIT_REPORT
    assert sm.state == QSOState.WAIT_REPORT
    sm._sent.clear()
    # EG5SUN bestaetigt mit Unicode-Minus-R-Report
    raw = f"DA1MHH EG5SUN R{UNICODE_MINUS}12"
    sm.on_message_received(parse_ft8_message(raw))
    # MUSS RR73 senden, NICHT den eigenen Rapport wiederholen
    assert sm.state == QSOState.TX_RR73, f"State war {sm.state.name}, erwartet TX_RR73"
    assert "RR73" in sm._sent[-1], f"Gesendet: {sm._sent[-1]!r}"
    assert "EG5SUN" in sm._sent[-1]


def test_eg5sun_no_report_repeat_loop(sm):
    """Negativ-Kontrolle: wir wiederholen NICHT stur den Rapport (-25)."""
    sm.start_qso(their_call="EG5SUN", their_grid="IM99", freq_hz=1000)
    sm.on_message_sent()  # -> WAIT_REPORT
    sm._sent.clear()
    raw = f"DA1MHH EG5SUN R{UNICODE_MINUS}12"
    sm.on_message_received(parse_ft8_message(raw))
    # Der gesendete String darf KEIN nackter Rapport sein
    last = sm._sent[-1]
    assert "RR73" in last
    assert not last.endswith("-25"), "Bug: stur eigener Rapport statt RR73"


def test_ascii_r_report_unchanged(sm):
    """Regression: ASCII-R-Report verhaelt sich exakt wie bisher."""
    sm.start_qso(their_call="G4ABC", their_grid="IO91", freq_hz=1000)
    sm.on_message_sent()
    sm._sent.clear()
    sm.on_message_received(parse_ft8_message("DA1MHH G4ABC R-10"))
    assert sm.state == QSOState.TX_RR73
    assert "RR73" in sm._sent[-1]


def test_unicode_plain_report_advances_normally(sm):
    """Unicode plain-Report (ohne R) -> normaler Austausch (TX_REPORT)."""
    sm.start_qso(their_call="EG5SUN", their_grid="IM99", freq_hz=1000)
    sm.on_message_sent()  # -> WAIT_REPORT
    sm._sent.clear()
    raw = f"DA1MHH EG5SUN {UNICODE_MINUS}12"
    sm.on_message_received(parse_ft8_message(raw))
    # plain Report -> wir senden unseren R-Report (advance), bleiben nicht haengen
    assert sm.state == QSOState.TX_REPORT
