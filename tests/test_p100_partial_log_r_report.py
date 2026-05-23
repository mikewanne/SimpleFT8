"""P100 (v0.97.96) — Partial-Log bei R-Report-Empfang trotz P99-Cap.

Mike-Spec 23.05.: wenn die Gegenstation den R-Report empfängt und uns
zurückschickt, ist das QSO inhaltlich komplett (their_call, their_grid,
our_snr, their_snr alle da). Beide Stationen loggen normal → bei
QRZ.com/LoTW gibt es Match. P99 hätte das in einem Edge-Case
verworfen: wenn `rr73_retries` durch 4-5 Leerlauf-Zyklen im Decoder-
Cap-Pfad (qso_state.py:429-444 P98) hochgetrieben wurde, blockierte
P99 den 1. eintreffenden R-Report → kein RR73-Send → kein
qso_complete → QSO verloren.

P100-Fix: im is_r_report-Cap-Pfad (Z.679-700) qso_complete statt
qso_timeout feuern. their_snr wird aus msg.grid_or_report gesetzt
damit ADIF-Eintrag vollständig.

DeepSeek R1 V4-pro (23.05.) bestätigt:
- 🟢 Architektur korrekt
- 🟢 Doppel-Log-Risiko nicht gegeben
- 🟢 State TIMEOUT richtig (kein RR73 raus → WAIT_73 wäre falsch)
- 🟡 cq_qso_count += 1 eingebaut (Konsistenz mit TX_RR73-Pfad)
- 🟡 Debug-Log-Kategorie „COMPLETE" statt „TIMEOUT"

T1: Edge-Case Decoder-Cap auf 5 + R-Report → qso_complete + their_snr
T2: cq_qso_count wird inkrementiert
T3: their_snr aus R-Report-Wert übernommen (z.B. R+12)
T4: is_report-Cap unverändert (kein R-Report → kein Log)
T5: is_grid-Cap unverändert (kein R-Report → kein Log)
"""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from core.qso_state import QSOStateMachine, QSOState, MAX_RR73_RETRIES
from core.message import FT8Message


def _msg(field1: str, field2: str, field3: str) -> FT8Message:
    return FT8Message(
        raw=f"{field1} {field2} {field3}",
        field1=field1, field2=field2, field3=field3,
    )


def _make_sm_in_wait_rr73_at_cap() -> tuple:
    """Realistisches Setup: WAIT_RR73 + rr73_retries auf 5 (Decoder-
    Pfad hat 5 Leerlauf-Zyklen abgearbeitet). Liefert (sm, completes,
    timeouts) — Slot-Listen für Assertion.
    """
    sm = QSOStateMachine("DA1MHH", "JO31")
    sm.state = QSOState.WAIT_RR73
    sm.qso.their_call = "DA1TST"
    sm.qso.their_grid = "JN58"
    sm.qso.our_snr = "R-15"
    sm.qso.rr73_retries = 5  # Cap-Schwelle erreicht
    completes: list = []
    timeouts: list = []
    sm.qso_complete.connect(lambda q: completes.append(q))
    sm.qso_timeout.connect(lambda c: timeouts.append(c))
    return sm, completes, timeouts


# ── T1 — Edge-Case: Decoder-Cap auf 5 + R-Report → qso_complete ─────

def test_t1_r_report_at_cap_triggers_partial_log():
    sm, completes, timeouts = _make_sm_in_wait_rr73_at_cap()
    sm.on_message_received(_msg("DA1MHH", "DA1TST", "R-12"))
    # P100: qso_complete gefeuert mit vollem QSOData
    assert len(completes) == 1, "P100 löst qso_complete aus"
    assert completes[0].their_call == "DA1TST"
    assert completes[0].their_snr == "R-12"
    assert completes[0].their_grid == "JN58"
    assert completes[0].our_snr == "R-15"
    # KEIN qso_timeout (das war P99-Verhalten vor P100)
    assert len(timeouts) == 0, "P100: kein qso_timeout im R-Report-Pfad"


# ── T2 — cq_qso_count wird inkrementiert (R1-F1) ────────────────────

def test_t2_cq_qso_count_increments_on_partial_log():
    sm, _, _ = _make_sm_in_wait_rr73_at_cap()
    initial_count = sm.cq_qso_count
    sm.on_message_received(_msg("DA1MHH", "DA1TST", "R-08"))
    assert sm.cq_qso_count == initial_count + 1, (
        "R1-F1: cq_qso_count muss inkrementiert werden (Konsistenz "
        "mit TX_RR73-Pfad Z.529)")


# ── T3 — their_snr aus R-Report-Wert übernommen ─────────────────────

def test_t3_their_snr_set_from_r_report_value():
    """Verschiedene R-Report-Werte korrekt übernommen."""
    for r_value in ("R+15", "R-08", "R+00", "R-30"):
        sm, completes, _ = _make_sm_in_wait_rr73_at_cap()
        sm.on_message_received(_msg("DA1MHH", "DA1TST", r_value))
        assert len(completes) == 1
        assert completes[0].their_snr == r_value, (
            f"P100: their_snr muss '{r_value}' sein, ist "
            f"'{completes[0].their_snr}'")


# ── T4 — is_report-Cap unverändert (kein Log gerechtfertigt) ────────

def test_t4_plain_report_cap_no_complete_signal():
    """Plain-Report (ohne R-Prefix) wiederholt → P99-Pfad: qso_timeout,
    KEIN qso_complete. Mike-Kriterium: Plain-Report ≠ Bestätigung.
    """
    sm, completes, timeouts = _make_sm_in_wait_rr73_at_cap()
    sm.on_message_received(_msg("DA1MHH", "DA1TST", "-08"))
    assert len(timeouts) == 1, "is_report-Cap-Pfad: qso_timeout"
    assert len(completes) == 0, "is_report-Cap: KEIN qso_complete (P100 nicht zuständig)"


# ── T5 — is_grid-Cap unverändert (kein Log gerechtfertigt) ──────────

def test_t5_grid_cap_no_complete_signal():
    """Grid wiederholt → P99-Pfad: qso_timeout, KEIN qso_complete."""
    sm, completes, timeouts = _make_sm_in_wait_rr73_at_cap()
    sm.on_message_received(_msg("DA1MHH", "DA1TST", "JN58"))
    assert len(timeouts) == 1, "is_grid-Cap-Pfad: qso_timeout"
    assert len(completes) == 0, "is_grid-Cap: KEIN qso_complete"
