"""P136 (26.05.2026) — Call-Validation Auto-Hunt + Parser-Fix CQ-mit-Richtung.

Mike-Field-Bug 26.05.: Auto-Hunt picked „JA" als Call aus „CQ JA HG60IPA"
→ 5x „Sende JA DA1MHH -17" → Timeout. Etikette-Verletzung.

Diagnose: 2 Schichten kaputt:
1. Parser `core/message.py:114` erkannte Richtungs-Anrufe nur bei
   `len(parts) == 4` — bei „CQ JA HG60IPA" (3 parts) fiel das durch
   → field2="JA" → caller="JA".
2. Auto-Hunt `core/auto_hunt.py:332` nahm `msg.caller` ohne Validation.

V3 (R1-PUSH FREIGEGEBEN 6× GRÜN):
- Parser: `len(parts) >= 3` (war 4), Index-Defensive bei f3
- `_looks_like_call` → `looks_like_callsign` (public)
- Auto-Hunt: slash-tolerante Validation als Defense-in-Depth

ACs:
- AC1: `CQ JA HG60IPA` → caller=HG60IPA (Bug-Fix)
- AC2: `CQ DX DA1MHH JN58` unverändert (4 parts mit Grid)
- AC3: `CQ DA1MHH JN58` unverändert (valides Call ohne Direction)
- AC4: `CQ TEST DA1ABC` → caller=DA1ABC (R1-Auflage)
- AC5: `looks_like_callsign` filtert JA/TEST/CQ raus, lässt Sonderformate
       wie 1A0KM/4U1UN durch
- AC6: Auto-Hunt überspringt Kandidaten mit nicht-callsign-Caller
- AC7: Slash-tolerant (DA1MHH/P → Validation auf DA1MHH)
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from core.message import parse_ft8_message, looks_like_callsign


# ---------------------------------------------------------------------------
# T1-T8: Parser-Fix CQ-mit-Richtung
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("raw, expected_caller, expected_field3", [
    # Mike-Field-Bug 26.05.: 3 parts, ohne Grid
    ("CQ JA HG60IPA", "HG60IPA", ""),
    # Standard-DX-Aufruf mit Grid
    ("CQ DX DA1MHH JN58", "DA1MHH", "JN58"),
    # DX-Aufruf ohne Grid (vorher schon fehlerhaft)
    ("CQ DX DA1MHH", "DA1MHH", ""),
    # Standard ohne Direction (keine Aenderung)
    ("CQ DA1MHH JN58", "DA1MHH", "JN58"),
    # R1-Auflage: TEST-Modifier
    ("CQ TEST DA1ABC", "DA1ABC", ""),
    # North America Direction
    ("CQ NA K1ABC FN42", "K1ABC", "FN42"),
    # Europe Direction
    ("CQ EU DA1MHH", "DA1MHH", ""),
    # Sonderformat 1A0KM als direkter Caller
    ("CQ 1A0KM", "1A0KM", ""),
])
def test_t1_parser_cq_with_direction(raw, expected_caller, expected_field3):
    """T1: Parser erkennt CQ-mit-Richtung korrekt (mit/ohne Grid)."""
    msg = parse_ft8_message(raw)
    assert msg.is_cq is True, f"is_cq sollte True sein fuer {raw!r}"
    assert msg.caller == expected_caller, (
        f"{raw!r}: caller={msg.caller!r}, expected={expected_caller!r}")
    assert msg.field3 == expected_field3, (
        f"{raw!r}: field3={msg.field3!r}, expected={expected_field3!r}")


def test_t2_parser_cq_short_format_unchanged():
    """T2: 2-Felder-CQ (`CQ DA1MHH`) bleibt unverändert."""
    msg = parse_ft8_message("CQ DA1MHH")
    assert msg.is_cq is True
    assert msg.field1 == "CQ"
    assert msg.caller == "DA1MHH"


def test_t3_parser_no_regression_4_parts_with_grid():
    """T3: 4-Parts-Format (CQ DX CALL GRID) verhält sich identisch zu vorher."""
    msg = parse_ft8_message("CQ DX DA1MHH JN58")
    assert msg.field1 == "CQ DX"
    assert msg.caller == "DA1MHH"
    assert msg.field3 == "JN58"


# ---------------------------------------------------------------------------
# T4-T9: looks_like_callsign Heuristik
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("token, expected", [
    # Echte Rufzeichen
    ("DA1MHH", True),
    ("HG60IPA", True),
    ("K1ABC", True),
    ("1A0KM", True),       # Order of Malta
    ("4U1UN", True),       # UN Geneva
    ("R1A0KM", True),      # Antarktis (hypothetisch)
    # Direction-Marker — sollen RAUS
    ("JA", False),         # zu kurz
    ("EU", False),
    ("NA", False),
    ("DX", False),
    # Keywords — sollen RAUS (Buchstaben ohne Ziffer)
    ("TEST", False),
    ("STATION", False),
    ("CQ", False),
    ("QSO", False),
    ("RR73", True),        # hat Ziffer + Buchstaben → würde durchrutschen,
                            # aber kein gültiges Call in der Praxis. Fix
                            # via Auto-Hunt-Cooldown / kein Direct-Call.
    # Edge-Cases
    ("123", False),        # nur Ziffern
    ("ABCDEFGHIJK", False),  # zu lang (>10)
    ("AB", False),         # zu kurz
])
def test_t4_looks_like_callsign(token, expected):
    """T4: Heuristik Plausibilitäts-Check."""
    assert looks_like_callsign(token) is expected, (
        f"looks_like_callsign({token!r}) erwartete {expected}")


def test_t5_looks_like_callsign_backward_compat_alias():
    """T5: Alter Name `_looks_like_call` ist weiterhin Alias."""
    from core.message import _looks_like_call, looks_like_callsign
    assert _looks_like_call is looks_like_callsign


# ---------------------------------------------------------------------------
# T6-T9: Auto-Hunt-Validation (Defense-in-Depth)
# ---------------------------------------------------------------------------


def _make_cq_msg(caller_str: str, snr: int = -10, tx_even: bool = True):
    """Mock-Message für Auto-Hunt-Tests."""
    msg = MagicMock()
    msg.is_cq = True
    msg.caller = caller_str
    msg.snr = snr
    msg.freq_hz = 1500
    msg._tx_even = tx_even
    msg.grid_or_report = ""
    msg.is_grid = False
    return msg


def test_t6_auto_hunt_skips_invalid_caller():
    """T6: Auto-Hunt überspringt Kandidaten mit nicht-callsign-Caller."""
    from core.auto_hunt import AutoHunt
    hunt = AutoHunt()
    hunt.set_band("20m")
    hunt.set_mode("FT8")
    hunt.start_auto_hunt()
    # JA = nicht callsign, HG60IPA = callsign
    messages = [
        _make_cq_msg("JA"),
        _make_cq_msg("HG60IPA"),
    ]
    candidate = hunt.select_next(messages, qso_idle=True, presence_ok=True)
    assert candidate is not None
    assert candidate.call == "HG60IPA", (
        f"Erwartete HG60IPA, bekam {candidate.call}")


def test_t7_auto_hunt_returns_none_when_only_invalid_callers():
    """T7: Auto-Hunt liefert None wenn ALLE Kandidaten ungültig sind."""
    from core.auto_hunt import AutoHunt
    hunt = AutoHunt()
    hunt.set_band("20m")
    hunt.set_mode("FT8")
    hunt.start_auto_hunt()
    messages = [
        _make_cq_msg("JA"),
        _make_cq_msg("TEST"),
        _make_cq_msg("DX"),
    ]
    candidate = hunt.select_next(messages, qso_idle=True, presence_ok=True)
    assert candidate is None, (
        f"Erwartete None bei nur ungueltigen Callers, bekam {candidate}")


def test_t8_auto_hunt_slash_tolerant():
    """T8: Slash-Suffix-Calls (DA1MHH/P) werden akzeptiert."""
    from core.auto_hunt import AutoHunt
    hunt = AutoHunt()
    hunt.set_band("20m")
    hunt.set_mode("FT8")
    hunt.start_auto_hunt()
    messages = [_make_cq_msg("DA1MHH/P")]
    candidate = hunt.select_next(messages, qso_idle=True, presence_ok=True)
    assert candidate is not None
    assert candidate.call == "DA1MHH/P"


def test_t9_auto_hunt_skips_pure_direction_marker_call():
    """T9: Reine Direction-Calls (JA, EU, NA) werden geblockt."""
    from core.auto_hunt import AutoHunt
    hunt = AutoHunt()
    hunt.set_band("20m")
    hunt.set_mode("FT8")
    hunt.start_auto_hunt()
    for direction in ["JA", "EU", "NA", "DX", "CQ", "TEST"]:
        msg = _make_cq_msg(direction)
        candidate = hunt.select_next([msg], qso_idle=True, presence_ok=True)
        assert candidate is None, (
            f"Direction-Marker {direction!r} darf NICHT als Kandidat "
            f"durchgehen — bekam {candidate}")


# ---------------------------------------------------------------------------
# T10: Doku-Marker
# ---------------------------------------------------------------------------


def test_t10_p136_markers_in_code():
    """T10: P136-Marker in message.py + auto_hunt.py."""
    from pathlib import Path
    msg_src = (Path(__file__).parent.parent / "core" / "message.py").read_text()
    hunt_src = (Path(__file__).parent.parent / "core" / "auto_hunt.py").read_text()
    assert "P136" in msg_src, "P136-Marker fehlt in core/message.py"
    assert "P136" in hunt_src, "P136-Marker fehlt in core/auto_hunt.py"
