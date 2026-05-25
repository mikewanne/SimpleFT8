"""P129 (25.05.2026) — P128-Filter 73/RR73 als Whitelist durchlassen.

Mike-Field-Beobachtung 25.05. 13:24 (Screenshot 3 QSOs hintereinander
M1DBW, 5B4AMX, G0CLT — alle ohne 73-Empfang im Log).

Mike-Hypothese: „kann das sein das wir die meldung blocken?"

Root Cause: P128 (v0.98.07, gleiche Session) setzt 60s-Cooldown nach
qso_complete → blockt ALLE Empf.-Einträge inkl. 73-Bestätigungen.

P129-Fix: is_73/is_rr73 IMMER durchlassen (Whitelist). is_r_report
und Plain-Reports bleiben geblockt (Spam-Schutz wie P128 intendiert).
"""

from __future__ import annotations

import time
from unittest.mock import MagicMock

import pytest

from core.message import parse_ft8_message
from ui.mw_cycle import _RECENTLY_COMPLETED_BLOCK_S


class _MwBlockMixin:
    """Stub für _p128_recently_completed_block."""

    def __init__(self):
        self._recently_completed_qsos: dict[str, float] = {}
        from ui.mw_cycle import CycleMixin
        self._fn = CycleMixin._p128_recently_completed_block.__get__(
            self, _MwBlockMixin)


# ---------------------------------------------------------------------------
# T1-T2: Whitelist greift — 73 und RR73 werden durchgelassen
# ---------------------------------------------------------------------------


def test_t1_73_message_passes_through_cooldown():
    """T1: 73-Message von Cooldown-Caller → durchgelassen (False)."""
    mw = _MwBlockMixin()
    mw._recently_completed_qsos["M1DBW"] = time.monotonic()  # frischer Cooldown
    msg = parse_ft8_message("DA1MHH M1DBW 73")
    assert msg.is_73 is True
    assert mw._fn("M1DBW", msg) is False, (
        "73-Bestätigung muss im Cooldown durchgelassen werden (P129)")


def test_t2_rr73_message_passes_through_cooldown():
    """T2: RR73-Message von Cooldown-Caller → durchgelassen."""
    mw = _MwBlockMixin()
    mw._recently_completed_qsos["EA1FLB"] = time.monotonic()
    msg = parse_ft8_message("DA1MHH EA1FLB RR73")
    assert msg.is_rr73 is True
    assert mw._fn("EA1FLB", msg) is False


# ---------------------------------------------------------------------------
# T3-T4: Spam bleibt geblockt — R-Reports + Plain Reports
# ---------------------------------------------------------------------------


def test_t3_r_report_still_blocked():
    """T3: R-Report von Cooldown-Caller → weiter geblockt (P128-Schutz)."""
    mw = _MwBlockMixin()
    mw._recently_completed_qsos["G0CLT"] = time.monotonic()
    msg = parse_ft8_message("DA1MHH G0CLT R+01")
    assert msg.is_r_report is True
    assert mw._fn("G0CLT", msg) is True, (
        "R-Report ist KEINE Bestätigung — muss weiter geblockt werden "
        "(R1-Empfehlung: nicht Whitelisten, sonst Spam-Schutz hin)")


def test_t4_plain_report_still_blocked():
    """T4: Plain Report (ohne R-Prefix) von Cooldown-Caller → geblockt."""
    mw = _MwBlockMixin()
    mw._recently_completed_qsos["5B4AMX"] = time.monotonic()
    msg = parse_ft8_message("DA1MHH 5B4AMX -02")
    assert msg.is_report is True
    assert msg.is_r_report is False
    assert mw._fn("5B4AMX", msg) is True


def test_t4b_grid_still_blocked():
    """T4b: Grid-Message von Cooldown-Caller → geblockt."""
    mw = _MwBlockMixin()
    mw._recently_completed_qsos["F4UIT"] = time.monotonic()
    msg = parse_ft8_message("DA1MHH F4UIT JN18")
    assert msg.is_grid is True
    assert mw._fn("F4UIT", msg) is True


# ---------------------------------------------------------------------------
# T5: Backward-Compat — msg=None Default
# ---------------------------------------------------------------------------


def test_t5_msg_none_default_preserves_old_behavior():
    """T5: Aufruf ohne msg-Param (alte Tests) → Verhalten wie bisher."""
    mw = _MwBlockMixin()
    mw._recently_completed_qsos["TEST"] = time.monotonic()
    # Kein msg → nur Caller-Check → bleibt blockiert
    assert mw._fn("TEST") is True
    # Anderer Caller → nicht im Store → durchgelassen
    assert mw._fn("OTHER") is False


# ---------------------------------------------------------------------------
# T6: Andere Station (nicht im Cooldown) — 73 + Reports passieren
# ---------------------------------------------------------------------------


def test_t6_other_station_73_passes():
    """T6: 73 von Station die NICHT im Cooldown ist → durchgelassen.

    Whitelist ist nur relevant innerhalb eines aktiven Cooldowns —
    Stationen ohne Cooldown-Eintrag werden eh nicht blockiert.
    """
    mw = _MwBlockMixin()
    mw._recently_completed_qsos["M1DBW"] = time.monotonic()
    msg = parse_ft8_message("DA1MHH UNKNOWN 73")
    assert mw._fn("UNKNOWN", msg) is False


def test_t6b_other_station_report_passes():
    """T6b: R-Report von Station die NICHT im Cooldown → durchgelassen."""
    mw = _MwBlockMixin()
    mw._recently_completed_qsos["M1DBW"] = time.monotonic()
    msg = parse_ft8_message("DA1MHH UNKNOWN R-15")
    assert mw._fn("UNKNOWN", msg) is False


# ---------------------------------------------------------------------------
# T7: Aging-Pfad bleibt unverändert (P128-Funktion)
# ---------------------------------------------------------------------------


def test_t7_aging_after_60s_for_blocked_message():
    """T7: Nach 60s wird Eintrag bei nicht-Whitelist-Message gelöscht."""
    mw = _MwBlockMixin()
    mw._recently_completed_qsos["AGING"] = (
        time.monotonic() - _RECENTLY_COMPLETED_BLOCK_S - 1.0)
    msg = parse_ft8_message("DA1MHH AGING R-15")  # blockierbar
    assert mw._fn("AGING", msg) is False
    assert "AGING" not in mw._recently_completed_qsos


def test_t7b_whitelist_short_circuit_no_aging():
    """T7b: Whitelist-Pfad short-circuited VOR Aging-Check.

    Konsequenz: alter Cooldown-Eintrag bleibt im store wenn nur 73-Messages
    kommen. Akzeptabel — wird beim nächsten R-Report oder bei Band/Mode-
    Wechsel aufgeräumt. KEIN Memory-Leak weil dict klein bleibt
    (max ~20 Calls pro Session).
    """
    mw = _MwBlockMixin()
    mw._recently_completed_qsos["SHORT"] = (
        time.monotonic() - _RECENTLY_COMPLETED_BLOCK_S - 1.0)
    msg = parse_ft8_message("DA1MHH SHORT 73")
    assert mw._fn("SHORT", msg) is False
    # Eintrag bleibt — Whitelist hat vor Aging geschlossen
    assert "SHORT" in mw._recently_completed_qsos


# ---------------------------------------------------------------------------
# T8: Source-Inspektion — Call-Site übergibt msg-Objekt
# ---------------------------------------------------------------------------


def test_t8_call_site_passes_msg():
    """T8: on_message_decoded ruft `_p128_recently_completed_block(caller, msg)`.

    Source-Inspektion garantiert dass der Call-Site die msg-Übergabe nicht
    bei späterem Refactoring verliert.
    """
    import inspect
    from ui.mw_cycle import CycleMixin
    source = inspect.getsource(CycleMixin.on_message_decoded)
    assert "self._p128_recently_completed_block(msg.caller, msg)" in source, (
        "Call-Site muss msg als 2. Param übergeben — P129-Whitelist greift "
        "sonst nie")


def test_t9_function_signature_has_optional_msg():
    """T9: Funktion akzeptiert optional msg-Param mit None-Default."""
    import inspect
    from ui.mw_cycle import CycleMixin
    sig = inspect.signature(CycleMixin._p128_recently_completed_block)
    assert "msg" in sig.parameters
    assert sig.parameters["msg"].default is None
