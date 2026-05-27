"""P138 (26.05.2026) — P129-Whitelist entfernt, 73/RR73 nach QSO-Ende blocken.

Spec-Umkehr von P129 (vor 1 Tag): Mike's heutiger Field-Bug zeigte
einen 73-Eintrag NACH dem '✓ QSO komplett' der ins neue QSO „herein-
rutschte". Mike-Spec: 'beendet ist beendet' -- alles nach ✓ blocken
inklusive 73/RR73.

Mechanik (warum 'vor ✓ durchlassen, nach ✓ blocken' automatisch
funktioniert):
- Cooldown-Stempel wird in _on_qso_confirmed_visual gesetzt
  (mw_qso.py, P140 26.05.2026 -- vorher faelschlich in
  _on_qso_complete = interner RR73-Send-Trigger, zu frueh)
  + symmetrisch in _on_qso_timeout (defensiv).
- VOR ✓: kein Cooldown-Eintrag -> Filter inaktiv -> 73 kommt durch
- NACH ✓: Cooldown 60s aktiv -> Filter blockt alles inkl. 73

Filter-Logik selbst ist unveraendert -- diese Tests pruefen den
Filter direkt durch manuelles Setzen von _recently_completed_qsos.
Die Set-Trigger-Stellen werden in test_p140_cooldown_trigger.py
geprueft.

Was sich aendert:
- P129-Whitelist 'msg.is_73 or msg.is_rr73 -> return False' ENTFERNT
- msg-Param der Helper-Funktion ENTFERNT (R1-KISS-Empfehlung)
- Call-Site on_message_decoded ruft nur noch (caller)

Was bleibt:
- Lazy-Aging > 60s loescht Eintrag
- accumulate_stations / RX-Tabelle / Wasserfall unberuehrt
- State-Machine-Pfad on_message_received laeuft unabhaengig
"""

from __future__ import annotations

import time

import pytest

from core.message import parse_ft8_message
from ui.mw_cycle import _RECENTLY_COMPLETED_BLOCK_S


class _MwBlockMixin:
    """Stub fuer _p128_recently_completed_block."""

    def __init__(self):
        self._recently_completed_qsos: dict[str, float] = {}
        from ui.mw_cycle import CycleMixin
        self._fn = CycleMixin._p128_recently_completed_block.__get__(
            self, _MwBlockMixin)


# ---------------------------------------------------------------------------
# T1-T2: NACH ✓ — 73/RR73 wird jetzt BLOCKIERT (Spec-Umkehr)
# ---------------------------------------------------------------------------


def test_t1_73_blocked_after_complete():
    """T1: 73-Message von Cooldown-Caller → BLOCKIERT (P138 Spec-Umkehr).

    Vor P138 (P129-Whitelist): durchgelassen.
    Nach P138 (Mike heute): blockiert -- 'beendet ist beendet'.
    """
    mw = _MwBlockMixin()
    mw._recently_completed_qsos["M1DBW"] = time.monotonic()
    msg = parse_ft8_message("DA1MHH M1DBW 73")
    assert msg.is_73 is True
    assert mw._fn("M1DBW") is True, (
        "P138: 73 NACH ✓ muss geblockt werden -- 'beendet ist beendet'")


def test_t2_rr73_blocked_after_complete():
    """T2: RR73-Message von Cooldown-Caller → BLOCKIERT (Spec-Umkehr)."""
    mw = _MwBlockMixin()
    mw._recently_completed_qsos["EA1FLB"] = time.monotonic()
    msg = parse_ft8_message("DA1MHH EA1FLB RR73")
    assert msg.is_rr73 is True
    assert mw._fn("EA1FLB") is True


# ---------------------------------------------------------------------------
# T3-T4: Spam-Schutz bleibt (Reports/Grid weiterhin geblockt)
# ---------------------------------------------------------------------------


def test_t3_r_report_blocked_after_complete():
    """T3: R-Report von Cooldown-Caller → blockiert (P128-Originalverhalten)."""
    mw = _MwBlockMixin()
    mw._recently_completed_qsos["G0CLT"] = time.monotonic()
    msg = parse_ft8_message("DA1MHH G0CLT R+01")
    assert msg.is_r_report is True
    assert mw._fn("G0CLT") is True


def test_t4_plain_report_blocked_after_complete():
    """T4: Plain Report ohne R-Prefix von Cooldown-Caller → blockiert."""
    mw = _MwBlockMixin()
    mw._recently_completed_qsos["5B4AMX"] = time.monotonic()
    msg = parse_ft8_message("DA1MHH 5B4AMX -02")
    assert msg.is_report is True
    assert mw._fn("5B4AMX") is True


def test_t4b_grid_blocked_after_complete():
    """T4b: Grid-Message von Cooldown-Caller → blockiert."""
    mw = _MwBlockMixin()
    mw._recently_completed_qsos["F4UIT"] = time.monotonic()
    msg = parse_ft8_message("DA1MHH F4UIT JN18")
    assert msg.is_grid is True
    assert mw._fn("F4UIT") is True


# ---------------------------------------------------------------------------
# T5: VOR ✓ — alle Messages kommen durch (kein Cooldown-Eintrag)
# ---------------------------------------------------------------------------


def test_t5_73_passes_before_complete():
    """T5 (Spec-Schluessel-Test): 73 VOR ✓ kommt durch.

    Mike-Spec: 'VOR dem qso ende wenn 73 kommt sehen wir es'.
    Kein Cooldown-Eintrag fuer den Call -> Filter inaktiv.
    """
    mw = _MwBlockMixin()
    # KEIN Eintrag in _recently_completed_qsos -- noch kein ✓
    msg = parse_ft8_message("DA1MHH M1DBW 73")
    assert mw._fn("M1DBW") is False, (
        "P138: 73 VOR ✓ muss durchgelassen werden -- "
        "Mike sieht die Bestaetigung im Log")


def test_t5b_rr73_passes_before_complete():
    """T5b: RR73 VOR ✓ kommt durch (analog)."""
    mw = _MwBlockMixin()
    msg = parse_ft8_message("DA1MHH EA1FLB RR73")
    assert mw._fn("EA1FLB") is False


def test_t5c_report_passes_before_complete():
    """T5c: Auch Reports kommen durch VOR ✓ (keine Aenderung)."""
    mw = _MwBlockMixin()
    msg = parse_ft8_message("DA1MHH G0CLT R-08")
    assert mw._fn("G0CLT") is False


# ---------------------------------------------------------------------------
# T6: Andere Station (nicht im Cooldown) — alles durchgelassen
# ---------------------------------------------------------------------------


def test_t6_other_station_passes():
    """T6: 73 von Station OHNE Cooldown → durchgelassen."""
    mw = _MwBlockMixin()
    mw._recently_completed_qsos["M1DBW"] = time.monotonic()
    assert mw._fn("UNKNOWN") is False


# ---------------------------------------------------------------------------
# T7: Aging-Pfad — Eintrag > 60s wird geloescht
# ---------------------------------------------------------------------------


def test_t7_aging_after_60s():
    """T7: Eintrag > 60s wird beim naechsten Filter-Aufruf geloescht."""
    mw = _MwBlockMixin()
    mw._recently_completed_qsos["AGING"] = (
        time.monotonic() - _RECENTLY_COMPLETED_BLOCK_S - 1.0)
    # Nach Aging: Filter returnt False (= nicht blockiert)
    assert mw._fn("AGING") is False
    # Eintrag wurde geloescht
    assert "AGING" not in mw._recently_completed_qsos


# ---------------------------------------------------------------------------
# T8-T9: Source-Inspektion + Funktions-Signatur
# ---------------------------------------------------------------------------


def test_t8_call_site_uses_caller_only():
    """T8: on_message_decoded ruft Filter ohne msg-Param (P138 KISS)."""
    import inspect
    from ui.mw_cycle import CycleMixin
    source = inspect.getsource(CycleMixin.on_message_decoded)
    # Call-Site ohne msg-Param
    assert "self._p128_recently_completed_block(msg.caller)" in source, (
        "P138: Call-Site uebergibt nur caller, kein msg mehr")
    # Alter P129-Pattern darf nicht zurueck
    assert "self._p128_recently_completed_block(msg.caller, msg)" not in source


def test_t9_function_signature_no_msg_param():
    """T9: _p128_recently_completed_block hat KEINEN msg-Parameter mehr."""
    import inspect
    from ui.mw_cycle import CycleMixin
    sig = inspect.signature(CycleMixin._p128_recently_completed_block)
    assert "msg" not in sig.parameters, (
        "P138 R1-KISS: msg-Parameter entfernt nach Whitelist-Removal")


def test_t10_p138_marker_in_doc():
    """T10: P138-Marker in der Helper-Funktion Doku."""
    import inspect
    from ui.mw_cycle import CycleMixin
    source = inspect.getsource(CycleMixin._p128_recently_completed_block)
    assert "P138" in source, "P138-Marker fehlt in Helper-Doku"
    assert "Spec-Umkehr" in source or "Whitelist" in source, (
        "Doku muss Spec-Umkehr / Whitelist-Entfernung erklaeren")


def test_t11_p129_whitelist_logic_removed():
    """T11 (Regression-Schutz): KEIN is_73-Whitelist-Pattern mehr."""
    import inspect
    from ui.mw_cycle import CycleMixin
    source = inspect.getsource(CycleMixin._p128_recently_completed_block)
    # Diese Patterns waren typische P129-Whitelist-Marker
    assert "msg.is_73" not in source, (
        "P138 Regression-Schutz: msg.is_73 darf nicht zurueck in Filter")
    assert "msg.is_rr73" not in source
