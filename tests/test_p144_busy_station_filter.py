"""P144 (27.05.2026) — Auto-Hunt busy-station Filter.

Mike-Field-Bug 26.05.2026 17:38 (Auto-Hunt 20m FT8):
- Empfangsfenster zeigte "R2BRD RA5AD RR73" (RA5AD beendet QSO mit R2BRD).
- 1:45 Min später picked Auto-Hunt RA5AD trotzdem → 5 Versuche ins Leere.
- RA5AD antwortete erst 15s NACH unserem Timeout → QSO verloren +
  2:30 Min Band-QRM.

Mike-Wahl Option 1: Abort+Skip ohne Cooldown, später Retry möglich.
Defer-Familie 9. Iteration (P81/P122/P124/P127/P128/P129/P126/P131/P144).

R1-V4-pro Findings eingebaut:
- F1: _manual_override-Check (User-Klick → User entscheidet)
- F2: clear_current_target() statt direkter _current_target-Zugriff
- F5: debug_log("HUNT", "P144_SKIP ...") für Field-Diagnose

Tests:
- T1-T3: Filter True bei RR73/R-Report/Grid an Fremd
- T4: Filter False bei neuem CQ
- T5: Filter False bei Antwort an uns
- T6: Filter False bei anderem Caller (nicht Target)
- T7: Filter False wenn Auto-Hunt inaktiv
- T8: Filter False bei _manual_override=True (R1-F1)
- T9: _p144_abort_and_skip-Body Source-Inspektion (cleanup-Calls)
- T10: Reihenfolge in on_message_decoded: P124 → P128 → P144 → SM
- T11: clear_current_target setzt _current_target=None, KEIN Cooldown
- T12: debug_log-Aufruf in _p144_abort_and_skip (R1-F5)
"""

from __future__ import annotations

import re
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock


REPO = Path(__file__).resolve().parent.parent
MW_CYCLE_SRC = (REPO / "ui" / "mw_cycle.py").read_text()
AUTO_HUNT_SRC = (REPO / "core" / "auto_hunt.py").read_text()


# ---------------------------------------------------------------------------
# Helper: Fake-Self-Objekt für Filter-Funktion ohne Qt-Imports
# ---------------------------------------------------------------------------

def _make_fake_self(
    *,
    auto_hunt_active: bool = True,
    manual_override: bool = False,
    their_call: str = "RA5AD",
    my_call: str = "DA1MHH",
):
    """Baut ein Minimal-`self` für _p144_target_busy_with_other auf."""
    qso = SimpleNamespace(their_call=their_call) if their_call else None
    qso_sm = SimpleNamespace(qso=qso)
    auto_hunt = SimpleNamespace(
        active=auto_hunt_active,
        _manual_override=manual_override,
    )
    settings = SimpleNamespace(callsign=my_call)
    return SimpleNamespace(
        _auto_hunt=auto_hunt,
        qso_sm=qso_sm,
        settings=settings,
    )


def _make_msg(target: str, caller: str, field3: str = ""):
    """Baut ein Minimal-FT8Message-Fake mit caller/target/is_cq Properties."""
    field1 = target
    field2 = caller
    is_cq = field1 == "CQ" or field1.startswith("CQ ")
    return SimpleNamespace(
        field1=field1,
        field2=field2,
        field3=field3,
        target=field1,
        caller=field2,
        is_cq=is_cq,
    )


def _filter_fn():
    """Lädt _p144_target_busy_with_other als unbound function aus mw_cycle.py.

    Wir extrahieren den Source-Code und exec'en ihn in einem isolierten
    Namespace — vermeidet Qt-Import beim Test.
    """
    m = re.search(
        r"def _p144_target_busy_with_other\(self, msg.*?(?=\n    def )",
        MW_CYCLE_SRC, re.S,
    )
    assert m is not None, "Funktion _p144_target_busy_with_other nicht gefunden"
    src = "def _p144_target_busy_with_other(self, msg):\n" + \
          "\n".join(line[4:] if line.startswith("    ") else line
                    for line in m.group(0).splitlines()[1:])
    ns = {}
    exec(src, ns)
    return ns["_p144_target_busy_with_other"]


# ---------------------------------------------------------------------------
# T1-T3: Filter True bei Fremd-Adressen (RR73, R-Report, Grid)
# ---------------------------------------------------------------------------


def test_t1_rr73_to_other_call_returns_true():
    """T1: 'R2BRD RA5AD RR73' + Target=RA5AD → Filter True (Mike-Field)."""
    fn = _filter_fn()
    self = _make_fake_self(their_call="RA5AD")
    msg = _make_msg(target="R2BRD", caller="RA5AD", field3="RR73")
    assert fn(self, msg) is True


def test_t2_r_report_to_other_call_returns_true():
    """T2: 'R2BRD RA5AD R-15' (R-Report an Fremd) → Filter True."""
    fn = _filter_fn()
    self = _make_fake_self(their_call="RA5AD")
    msg = _make_msg(target="R2BRD", caller="RA5AD", field3="R-15")
    assert fn(self, msg) is True


def test_t3_grid_to_other_call_returns_true():
    """T3: 'R2BRD RA5AD KO80' (Grid an Fremd) → Filter True."""
    fn = _filter_fn()
    self = _make_fake_self(their_call="RA5AD")
    msg = _make_msg(target="R2BRD", caller="RA5AD", field3="KO80")
    assert fn(self, msg) is True


# ---------------------------------------------------------------------------
# T4-T6: Filter False bei legitimen Szenarien
# ---------------------------------------------------------------------------


def test_t4_new_cq_returns_false():
    """T4: 'CQ RA5AD KO80' (Target macht neuen CQ) → Filter False.
    Target ist wieder frei — Auto-Hunt darf wieder picken."""
    fn = _filter_fn()
    self = _make_fake_self(their_call="RA5AD")
    msg = _make_msg(target="CQ", caller="RA5AD", field3="KO80")
    assert fn(self, msg) is False


def test_t4b_cq_dx_returns_false():
    """T4b: 'CQ DX RA5AD' (is_cq via startswith) → Filter False."""
    fn = _filter_fn()
    self = _make_fake_self(their_call="RA5AD")
    msg = _make_msg(target="CQ DX", caller="RA5AD", field3="")
    assert fn(self, msg) is False


def test_t5_reply_to_us_returns_false():
    """T5: 'DA1MHH RA5AD RR73' (Target antwortet UNS) → Filter False.
    Genau die Antwort die wir wollen."""
    fn = _filter_fn()
    self = _make_fake_self(their_call="RA5AD")
    msg = _make_msg(target="DA1MHH", caller="RA5AD", field3="RR73")
    assert fn(self, msg) is False


def test_t6_other_caller_returns_false():
    """T6: 'R2BRD F1ABC RR73' (anderer Caller, nicht unser Target) →
    Filter False (kein Eingriff in unsere Sicht)."""
    fn = _filter_fn()
    self = _make_fake_self(their_call="RA5AD")
    msg = _make_msg(target="R2BRD", caller="F1ABC", field3="RR73")
    assert fn(self, msg) is False


# ---------------------------------------------------------------------------
# T7-T8: Filter False bei inaktivem Auto-Hunt / manuellem QSO
# ---------------------------------------------------------------------------


def test_t7_autohunt_inactive_returns_false():
    """T7: Auto-Hunt-Session NICHT aktiv → Filter False (manuelles QSO,
    User entscheidet selbst)."""
    fn = _filter_fn()
    self = _make_fake_self(auto_hunt_active=False, their_call="RA5AD")
    msg = _make_msg(target="R2BRD", caller="RA5AD", field3="RR73")
    assert fn(self, msg) is False


def test_t8_manual_override_returns_false():
    """T8 (R1-F1): _manual_override=True (User-Klick auf Station während
    Auto-Hunt-Session läuft) → Filter False.

    Mike-Spec: bei manuellem Klick entscheidet User, nicht Filter."""
    fn = _filter_fn()
    self = _make_fake_self(
        auto_hunt_active=True,
        manual_override=True,
        their_call="RA5AD",
    )
    msg = _make_msg(target="R2BRD", caller="RA5AD", field3="RR73")
    assert fn(self, msg) is False


def test_t8b_no_qso_returns_false():
    """T8b: qso.their_call leer (kein aktives QSO) → Filter False."""
    fn = _filter_fn()
    self = _make_fake_self(their_call="")
    msg = _make_msg(target="R2BRD", caller="RA5AD", field3="RR73")
    assert fn(self, msg) is False


# ---------------------------------------------------------------------------
# T9: _p144_abort_and_skip-Body — Source-Inspektion
# ---------------------------------------------------------------------------


def _abort_skip_body():
    m = re.search(
        r"def _p144_abort_and_skip\(self, target.*?(?=\n    def )",
        MW_CYCLE_SRC, re.S,
    )
    assert m is not None
    return m.group(0)


def test_t9_abort_calls_encoder_abort():
    """T9: _p144_abort_and_skip ruft encoder.abort() wenn TX läuft."""
    body = _abort_skip_body()
    assert "self.encoder.abort()" in body, (
        "P144: encoder.abort() Pflicht — Race-Schutz P126/P127-Pattern.")
    assert "is_transmitting" in body, (
        "P144: Check is_transmitting bevor abort().")


def test_t9b_clears_pending_tx_log():
    """T9b: _pending_tx_log = None (P127/P131-Pattern, verspätete
    Sende-Eintrag verwerfen)."""
    body = _abort_skip_body()
    assert "_pending_tx_log = None" in body, (
        "P144: _pending_tx_log = None Pflicht (P127/P131-Defer-Pattern).")


def test_t9c_calls_qso_sm_cancel():
    """T9c: qso_sm.cancel() setzt State auf IDLE."""
    body = _abort_skip_body()
    assert "self.qso_sm.cancel()" in body, (
        "P144: qso_sm.cancel() Pflicht — State zurücksetzen.")


def test_t9d_calls_clear_current_target():
    """T9d (R1-F2): _auto_hunt.clear_current_target() Pflicht."""
    body = _abort_skip_body()
    assert "clear_current_target()" in body, (
        "P144 (R1-F2): _auto_hunt.clear_current_target() statt direkter "
        "_current_target-Zugriff.")


def test_t9e_no_mark_pick_no_cooldown():
    """T9e: KEIN mark_pick() + KEIN _cooldown-Eintrag (Mike-Spec:
    Target bleibt für späteren Pick verfügbar)."""
    body = _abort_skip_body()
    assert "mark_pick(" not in body, (
        "P144 Mike-Spec: KEIN mark_pick() — Target bleibt pickbar.")
    assert "on_qso_timeout(" not in body, (
        "P144: NICHT on_qso_timeout-Pfad (setzt 5-Min-Cooldown).")
    assert "on_qso_complete(" not in body, (
        "P144: NICHT on_qso_complete-Pfad (setzt P61-Cooldown).")


def test_t9f_adds_info_to_qso_panel():
    """T9f: User-Info via qso_panel.add_info."""
    body = _abort_skip_body()
    assert "qso_panel.add_info(" in body, (
        "P144: User soll im QSO-Log sehen warum gespringen wurde.")
    assert "im QSO" in body, (
        "P144: Info-Text soll 'ist im QSO' enthalten (Mike-Stil, kurz "
        "— gekürzt 28.05.2026, busy_with nur noch im Debug-Log).")


def test_t9g_debug_log_called():
    """T9g (R1-F5): debug_log('HUNT', 'P144_SKIP ...') für Field-Diagnose."""
    body = _abort_skip_body()
    assert "debug_log" in body, (
        "P144 (R1-F5): P139-Debug-Logging Pflicht für Field-Diagnose.")
    assert "P144_SKIP" in body, (
        "P144 (R1-F5): Event-Tag P144_SKIP für grep-Filter.")


# ---------------------------------------------------------------------------
# T10: Reihenfolge in on_message_decoded — P124 → P128 → P144 → P94/OMNI → SM
# ---------------------------------------------------------------------------


def test_t10_filter_order_in_on_message_decoded():
    """T10: P144-Aufruf kommt NACH P124-Hash-Resolve, NACH P128-Block-Check,
    VOR P94-Quick73 und OMNI-Handler, VOR qso_sm.on_message_received."""
    m = re.search(
        r"def on_message_decoded\(self, msg.*?(?=\n    def )",
        MW_CYCLE_SRC, re.S,
    )
    assert m is not None
    body = m.group(0)

    pos_p124 = body.find("_p124_resolve_hash_if_active_qso")
    pos_p128 = body.find("_p128_recently_completed_block")
    pos_p144 = body.find("_p144_target_busy_with_other")
    pos_p94 = body.find("_p94_quick73_filter")
    pos_omni = body.find("self._omni_cq.is_active()")
    pos_sm = body.find("self.qso_sm.on_message_received(msg)")

    assert pos_p124 > 0 and pos_p144 > 0 and pos_sm > 0, (
        "Mindestens P124, P144 und State-Machine-Aufruf müssen vorhanden sein")
    assert pos_p124 < pos_p144, "P124-Resolve muss VOR P144-Filter laufen"
    assert pos_p128 < pos_p144, "P128-Block muss VOR P144-Filter laufen"
    assert pos_p144 < pos_p94, "P144 muss VOR P94-Quick73 laufen"
    assert pos_p144 < pos_omni, "P144 muss VOR OMNI-Handler laufen"
    assert pos_p144 < pos_sm, (
        "P144 muss VOR qso_sm.on_message_received laufen "
        "(sonst State-Machine sieht Fremd-Frame und treibt Counter hoch).")


# ---------------------------------------------------------------------------
# T11: clear_current_target in auto_hunt.py — setzt _current_target=None,
#      KEIN Cooldown
# ---------------------------------------------------------------------------


def test_t11_clear_current_target_exists():
    """T11: auto_hunt.clear_current_target() Methode existiert (R1-F2)."""
    assert "def clear_current_target(self):" in AUTO_HUNT_SRC, (
        "P144 (R1-F2): clear_current_target() Methode fehlt in auto_hunt.py.")


def test_t11b_clear_current_target_no_cooldown():
    """T11b: clear_current_target setzt nur _current_target=None,
    KEIN mark_pick + KEIN _cooldown-Eintrag (Code-Body ohne Docstring)."""
    m = re.search(
        r"def clear_current_target\(self\):.*?(?=\n    def )",
        AUTO_HUNT_SRC, re.S,
    )
    assert m is not None
    body = m.group(0)
    # Docstring entfernen (alles zwischen den ersten """...""")
    code_only = re.sub(r'""".*?"""', "", body, count=1, flags=re.S)
    assert "self._current_target = None" in code_only
    assert "mark_pick(" not in code_only, (
        "P144: clear_current_target darf mark_pick() NICHT aufrufen.")
    assert "_cooldown[" not in code_only, (
        "P144: clear_current_target darf KEIN Cooldown setzen.")
    assert "_recent_qso[" not in code_only, (
        "P144: clear_current_target darf KEIN _recent_qso setzen.")


# ---------------------------------------------------------------------------
# T12: Dynamisch-funktionaler Test mit Mocks — Abort-Skip-Effekt
# ---------------------------------------------------------------------------


def test_t12_abort_skip_resets_state_via_mocks():
    """T12 (R1-F6): _p144_abort_and_skip ruft ALLE Cleanup-Funktionen.

    Wir bauen ein Mock-self und führen die extrahierte Helper-Body aus,
    prüfen dass alle erwarteten Methoden aufgerufen wurden.
    """
    m = re.search(
        r"def _p144_abort_and_skip\(self, target.*?(?=\n    def )",
        MW_CYCLE_SRC, re.S,
    )
    src = "def _p144_abort_and_skip(self, target, busy_with):\n" + \
          "\n".join(line[4:] if line.startswith("    ") else line
                    for line in m.group(0).splitlines()[1:])
    ns = {}
    exec(src, ns)
    fn = ns["_p144_abort_and_skip"]

    encoder = MagicMock()
    encoder.is_transmitting = True
    qso_sm = MagicMock()
    auto_hunt = MagicMock()
    qso_panel = MagicMock()

    self_obj = SimpleNamespace(
        encoder=encoder,
        _pending_tx_log={"foo": "bar"},  # Pre-set, soll auf None
        qso_sm=qso_sm,
        _auto_hunt=auto_hunt,
        qso_panel=qso_panel,
    )

    fn(self_obj, target="RA5AD", busy_with="R2BRD")

    encoder.abort.assert_called_once()
    assert self_obj._pending_tx_log is None, (
        "P144: _pending_tx_log muss auf None gesetzt sein.")
    qso_sm.cancel.assert_called_once()
    auto_hunt.clear_current_target.assert_called_once()
    qso_panel.add_info.assert_called_once()
    info_text = qso_panel.add_info.call_args[0][0]
    assert "RA5AD" in info_text
    assert "im QSO" in info_text
    # busy_with (R2BRD) ist seit 28.05.2026 NICHT mehr in der Kurz-Meldung
    # (Mike-Wunsch: kurze Nachricht reicht) — nur noch im Debug-Log.
    assert "R2BRD" not in info_text


def test_t12b_abort_skip_no_tx_running():
    """T12b: Wenn encoder.is_transmitting=False, abort() NICHT gerufen
    (kein no-op-Spam). _pending_tx_log + cancel + clear bleiben."""
    m = re.search(
        r"def _p144_abort_and_skip\(self, target.*?(?=\n    def )",
        MW_CYCLE_SRC, re.S,
    )
    src = "def _p144_abort_and_skip(self, target, busy_with):\n" + \
          "\n".join(line[4:] if line.startswith("    ") else line
                    for line in m.group(0).splitlines()[1:])
    ns = {}
    exec(src, ns)
    fn = ns["_p144_abort_and_skip"]

    encoder = MagicMock()
    encoder.is_transmitting = False
    self_obj = SimpleNamespace(
        encoder=encoder,
        _pending_tx_log=None,
        qso_sm=MagicMock(),
        _auto_hunt=MagicMock(),
        qso_panel=MagicMock(),
    )

    fn(self_obj, target="RA5AD", busy_with="R2BRD")

    encoder.abort.assert_not_called()
    self_obj.qso_sm.cancel.assert_called_once()
    self_obj._auto_hunt.clear_current_target.assert_called_once()
