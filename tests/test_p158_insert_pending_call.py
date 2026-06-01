"""P164 (30.05.2026, generalisiert aus P158) — Klick auf uns-rufende Station
im QSO-Log.

Mike-Spec 30.05.: Eine Station die UNS ruft (im QSO-Fenster sichtbar) soll
IMMER klickbar sein — KEIN Auto-Hunt-Zwang, KEIN "anderes aktives QSO muss
laufen". Einzige inhaltliche Bedingung: sie ruft uns. Doktrin: Höflichkeit >
Stationszahl (Memory feedback_hoeflichkeit_vor_stationszahl).

Mike-Einsicht: Der EINE Schutz der bleibt — nicht die Station anklickbar
machen, mit der wir GERADE funken (sonst Doppel-QSO). Greift via
ACTIVE_QSO_STATES + qso.their_call == caller.

State-abhängige Klick-Wirkung (ein Pfad, kein Doppel-Pfad):
- Aktives QSO mit ANDERER Station → B vormerken (_qso_pending_insert), A zu
  Ende, B danach via _on_station_clicked.
- Kein aktives QSO (IDLE) → B SOFORT via _on_station_clicked.
- Klick auf aktuellen Partner → ignoriert.

Der Einschub-Merker `_qso_pending_insert` lebt in MainWindow (vom Auto-Hunt
ENTKOPPELT, ersetzt auto_hunt.set/take_pending_insert). DeepSeek-v4-pro
Plan-R1: GO. Findings eingebaut: F2 🔴 HALT nullt _qso_pending_insert,
F4 ACTIVE_QSO_STATES-Alias.

Tests:
- T1-T9: _p158_is_insertable_caller (Source-Extraktion, kein Qt)
- T10-T15: _on_hunt_insert_clicked (state-abhängige Wirkung, Mocks)
- T16-T19: _p158_maybe_start_inserted_call (mw_qso, vom Auto-Hunt entkoppelt)
- T20-T31: Source-Inspektion Verdrahtung (render/wiring/cleanup/HALT/alt-API-weg)
- T32-T34: echte QTextBrowser-Render + Signal-Roundtrip
"""

from __future__ import annotations

import re
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest


@pytest.fixture(scope="module")
def qapp():
    """Minimal QApplication für QObject/Signal-Lifecycle (kein pytest-qt)."""
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app


REPO = Path(__file__).resolve().parent.parent
MW_CYCLE_SRC = (REPO / "ui" / "mw_cycle.py").read_text()
MW_QSO_SRC = (REPO / "ui" / "mw_qso.py").read_text()
QSO_PANEL_SRC = (REPO / "ui" / "qso_panel.py").read_text()
MAIN_WINDOW_SRC = (REPO / "ui" / "main_window.py").read_text()
AUTO_HUNT_SRC = (REPO / "core" / "auto_hunt.py").read_text()

# Echte State-Werte für die Source-extrahierten Funktionen (kein Qt-Import).
from core.qso_state import QSOState, ACTIVE_QSO_STATES  # noqa: E402


# ---------------------------------------------------------------------------
# Helper: Methode als unbound function aus Source extrahieren (kein Qt)
# ---------------------------------------------------------------------------

def _extract_method(src: str, name: str, extra_ns: dict | None = None):
    """Extrahiert eine Methode `def <name>(self, ...)` bis zur nächsten `def`
    (oder deren Decorator) und exec't sie in isoliertem Namespace."""
    m = re.search(
        rf"def {re.escape(name)}\(self.*?(?=\n    (?:def |@))",
        src, re.S,
    )
    assert m is not None, f"Methode {name} nicht gefunden"
    body = "\n".join(
        line[4:] if line.startswith("    ") else line
        for line in m.group(0).splitlines()
    )
    ns: dict = {"FT8Message": object,
                "ACTIVE_QSO_STATES": ACTIVE_QSO_STATES}
    if extra_ns:
        ns.update(extra_ns)
    exec(body, ns)  # noqa: S102 — kontrollierter Test-Code
    return ns[name]


def _insertable_fn():
    return _extract_method(MW_CYCLE_SRC, "_p158_is_insertable_caller")


def _make_self(
    *,
    state=QSOState.WAIT_REPORT,
    cq_mode: bool = False,
    their_call: str = "EB3JT",
    my_call: str = "DA1MHH",
):
    qso = SimpleNamespace(their_call=their_call) if their_call else None
    qso_sm = SimpleNamespace(qso=qso, state=state, cq_mode=cq_mode)
    settings = SimpleNamespace(callsign=my_call)
    return SimpleNamespace(qso_sm=qso_sm, settings=settings)


def _make_msg(caller: str, *, is_73=False, is_rr73=False):
    return SimpleNamespace(caller=caller, is_73=is_73, is_rr73=is_rr73)


# ---------------------------------------------------------------------------
# T1-T9: _p158_is_insertable_caller (P164 generalisierte Regel)
# ---------------------------------------------------------------------------

def test_t1_foreign_caller_during_active_qso_is_insertable():
    """T1: B ruft uns während QSO mit A → klickbar (Kern-Szenario, Höflichkeit)."""
    fn = _insertable_fn()
    self = _make_self(their_call="EB3JT")
    assert fn(self, _make_msg("F5MYK")) is True


def test_t2_clickable_in_idle_without_autohunt():
    """T2 (P164-KERN): IDLE, KEIN Auto-Hunt, Station ruft uns → KLICKBAR.

    Genau Mikes YO60GW-Fall: P158 (alt) hätte hier NICHT gegriffen
    (Auto-Hunt-Zwang), P164 schon."""
    fn = _insertable_fn()
    self = _make_self(state=QSOState.IDLE, their_call="")
    assert fn(self, _make_msg("YO60GW")) is True


def test_t3_clickable_during_manual_qso():
    """T3: manuelles QSO mit A (kein Auto-Hunt), B ruft → klickbar."""
    fn = _insertable_fn()
    self = _make_self(state=QSOState.WAIT_RR73, their_call="DL1ABC")
    assert fn(self, _make_msg("SP9XYZ")) is True


def test_t4_current_partner_not_insertable():
    """T4: Doppel-Ruf-Schutz — die Station mit der wir GERADE funken → NEIN."""
    fn = _insertable_fn()
    self = _make_self(state=QSOState.WAIT_REPORT, their_call="EB3JT")
    assert fn(self, _make_msg("EB3JT")) is False


def test_t5_partner_in_idle_state_is_insertable():
    """T5: their_call gesetzt aber State NICHT aktiv (IDLE) → Doppel-Ruf-Schutz
    greift NICHT (kein laufendes QSO mehr) → klickbar."""
    fn = _insertable_fn()
    self = _make_self(state=QSOState.IDLE, their_call="EB3JT")
    assert fn(self, _make_msg("EB3JT")) is True


def test_t6_own_call_not_insertable():
    fn = _insertable_fn()
    self = _make_self(my_call="DA1MHH")
    assert fn(self, _make_msg("DA1MHH")) is False


def test_t7_confirmation_msgs_not_insertable():
    """T7: 73/RR73 = Bestätigung, nicht 'will Kontakt' → nicht klickbar."""
    fn = _insertable_fn()
    self = _make_self(their_call="EB3JT")
    assert fn(self, _make_msg("F5MYK", is_73=True)) is False
    assert fn(self, _make_msg("F5MYK", is_rr73=True)) is False


def test_t8_not_insertable_in_cq_mode():
    """T8 (R1-F1): CQ-Modus → caller_queue ist zuständig, P164 schließt aus."""
    fn = _insertable_fn()
    self = _make_self(cq_mode=True, their_call="EB3JT")
    assert fn(self, _make_msg("F5MYK")) is False


def test_t9_empty_caller_not_insertable():
    fn = _insertable_fn()
    self = _make_self(their_call="EB3JT")
    assert fn(self, _make_msg("")) is False


# ---------------------------------------------------------------------------
# T10-T15: _on_hunt_insert_clicked (state-abhängige Wirkung)
# ---------------------------------------------------------------------------

def _click_fn():
    return _extract_method(MW_CYCLE_SRC, "_on_hunt_insert_clicked")


def _make_click_self(*, state=QSOState.WAIT_REPORT, their_call="EB3JT",
                     insertable=None):
    qso = SimpleNamespace(their_call=their_call) if their_call else None
    return SimpleNamespace(
        qso_sm=SimpleNamespace(qso=qso, state=state),
        qso_panel=MagicMock(),
        _p158_insertable=insertable if insertable is not None else {},
        _qso_pending_insert=None,
        _on_station_clicked=MagicMock(),
    )


def test_t10_click_during_active_qso_sets_pending():
    """T10: aktives QSO mit A, Klick auf B → B vorgemerkt (kein Sofort-Ruf)."""
    fn = _click_fn()
    msg = _make_msg("F5MYK")
    self = _make_click_self(state=QSOState.WAIT_REPORT, their_call="EB3JT",
                            insertable={"F5MYK": msg})
    fn(self, "F5MYK")
    assert self._qso_pending_insert is msg
    self._on_station_clicked.assert_not_called()
    assert self.qso_panel.add_info.called


def test_t11_click_in_idle_calls_immediately():
    """T11 (P164-KERN): kein aktives QSO → B SOFORT via _on_station_clicked."""
    fn = _click_fn()
    msg = _make_msg("F5MYK")
    self = _make_click_self(state=QSOState.IDLE, their_call="",
                            insertable={"F5MYK": msg})
    fn(self, "F5MYK")
    # P166: P164-Klick im QSO-Fenster bleibt sanft → hard_stop=False
    self._on_station_clicked.assert_called_once_with(msg, hard_stop=False)
    assert self._qso_pending_insert is None


def test_t12_click_on_current_partner_ignored():
    """T12: Klick auf die Station mit der wir GERADE funken → noop."""
    fn = _click_fn()
    msg = _make_msg("EB3JT")
    self = _make_click_self(state=QSOState.WAIT_REPORT, their_call="EB3JT",
                            insertable={"EB3JT": msg})
    fn(self, "EB3JT")
    self._on_station_clicked.assert_not_called()
    assert self._qso_pending_insert is None


def test_t13_click_ignored_when_call_not_in_dict():
    """T13: Call nicht (mehr) im Merk-Dict → ignoriert."""
    fn = _click_fn()
    self = _make_click_self(insertable={})
    fn(self, "F5MYK")
    self._on_station_clicked.assert_not_called()
    assert self._qso_pending_insert is None


def test_t14_click_in_idle_pops_only_clicked_key():
    """T14 (DeepSeek-Final-R1-🔴): Sofort-Ruf im IDLE entfernt NUR den geklickten
    Key — andere im selben Slot uns-rufende Stationen bleiben klickbar."""
    fn = _click_fn()
    msg = _make_msg("F5MYK")
    other = _make_msg("OTHER")
    self = _make_click_self(state=QSOState.IDLE, their_call="",
                            insertable={"F5MYK": msg, "OTHER": other})
    fn(self, "F5MYK")
    assert "F5MYK" not in self._p158_insertable
    assert self._p158_insertable.get("OTHER") is other  # bleibt klickbar


def test_t15_click_during_qso_keeps_dict_until_consumed():
    """T15: Vormerken (aktives QSO) leert das Dict NICHT sofort — erst der
    Einschub-Konsum (_p158_maybe_start_inserted_call) räumt auf."""
    fn = _click_fn()
    msg = _make_msg("F5MYK")
    self = _make_click_self(state=QSOState.WAIT_REPORT, their_call="EB3JT",
                            insertable={"F5MYK": msg})
    fn(self, "F5MYK")
    assert "F5MYK" in self._p158_insertable


# ---------------------------------------------------------------------------
# T16-T19: _p158_maybe_start_inserted_call (mw_qso, vom Auto-Hunt entkoppelt)
# ---------------------------------------------------------------------------

def _maybe_start_fn():
    return _extract_method(MW_QSO_SRC, "_p158_maybe_start_inserted_call")


def test_t16_maybe_start_happy_path_calls_station_clicked():
    """T16: _qso_pending_insert gesetzt → _on_station_clicked(msg) + cleanup,
    OHNE Auto-Hunt-Abhängigkeit (P164-Entkopplung)."""
    fn = _maybe_start_fn()
    msg = _make_msg("F5MYK")
    self = SimpleNamespace(
        _qso_pending_insert=msg,
        _p158_insertable={"F5MYK": msg},
        _on_station_clicked=MagicMock(),
    )
    fn(self)
    # P166: Einschub bleibt sanft (pausieren + Auto-Resume) → hard_stop=False
    self._on_station_clicked.assert_called_once_with(msg, hard_stop=False)
    assert self._qso_pending_insert is None
    assert self._p158_insertable == {}


def test_t17_maybe_start_works_without_autohunt():
    """T17 (P164-KERN): kein _auto_hunt-Attribut nötig — Einschub funktioniert
    auch nach manuellem QSO ohne laufenden Auto-Hunt."""
    fn = _maybe_start_fn()
    msg = _make_msg("F5MYK")
    self = SimpleNamespace(
        _qso_pending_insert=msg,
        _p158_insertable={},
        _on_station_clicked=MagicMock(),
    )
    fn(self)  # darf NICHT auf self._auto_hunt zugreifen
    self._on_station_clicked.assert_called_once_with(msg, hard_stop=False)


def test_t18_maybe_start_noop_when_no_pending():
    """T18: kein Pending → kein B-Start."""
    fn = _maybe_start_fn()
    self = SimpleNamespace(
        _qso_pending_insert=None,
        _p158_insertable={},
        _on_station_clicked=MagicMock(),
    )
    fn(self)
    self._on_station_clicked.assert_not_called()


def test_t19_maybe_start_resets_pending_before_call():
    """T19: _qso_pending_insert wird VOR _on_station_clicked genullt
    (Reentrancy-Schutz — kein Doppel-Start)."""
    fn = _maybe_start_fn()
    msg = _make_msg("F5MYK")
    seen = {}

    def _spy(m, hard_stop=True):
        seen["pending_at_call"] = self._qso_pending_insert

    self = SimpleNamespace(
        _qso_pending_insert=msg,
        _p158_insertable={},
        _on_station_clicked=_spy,
    )
    fn(self)
    assert seen["pending_at_call"] is None


# ---------------------------------------------------------------------------
# T20-T31: Source-Inspektion Verdrahtung
# ---------------------------------------------------------------------------

def test_t20_qso_panel_uses_qtextbrowser_with_anchor():
    assert "self.log_view = QTextBrowser()" in QSO_PANEL_SRC
    assert "setOpenLinks(False)" in QSO_PANEL_SRC
    assert "anchorClicked.connect(self._on_anchor_clicked)" in QSO_PANEL_SRC
    assert "hunt_insert_clicked = Signal(str)" in QSO_PANEL_SRC


def test_t21_add_rx_has_insert_call_param_and_anchor_render():
    assert "insert_call: str = \"\"" in QSO_PANEL_SRC
    assert "_append_anchor_line" in QSO_PANEL_SRC
    assert "huntinsert:" in QSO_PANEL_SRC


def test_t22_main_window_inits_dict_pending_and_wires_signal():
    """T22: _p158_insertable + _qso_pending_insert initialisiert, Signal
    verdrahtet."""
    assert "self._p158_insertable" in MAIN_WINDOW_SRC
    assert "self._qso_pending_insert" in MAIN_WINDOW_SRC
    assert ("hunt_insert_clicked.connect(self._on_hunt_insert_clicked)"
            in MAIN_WINDOW_SRC)


def test_t23_main_window_clears_dict_on_stop():
    """T23: _on_auto_hunt_stopped leert das Merk-Dict (Auto-Hunt-Ende)."""
    m = re.search(r"def _on_auto_hunt_stopped\(self.*?(?=\n    (?:def |@))",
                  MAIN_WINDOW_SRC, re.S)
    assert m is not None
    assert "_p158_insertable.clear()" in m.group(0)


def test_t24_hook_in_both_qso_end_handlers():
    """T24: _p158_maybe_start_inserted_call in _on_qso_confirmed UND
    _on_qso_timeout aufgerufen."""
    conf = re.search(r"def _on_qso_confirmed\(self.*?(?=\n    (?:def |@))",
                     MW_QSO_SRC, re.S)
    tmo = re.search(r"def _on_qso_timeout\(self.*?(?=\n    (?:def |@))",
                    MW_QSO_SRC, re.S)
    assert conf and "_p158_maybe_start_inserted_call()" in conf.group(0)
    assert tmo and "_p158_maybe_start_inserted_call()" in tmo.group(0)


def test_t25_halt_nulls_pending_insert():
    """T25 (R1-F2 🔴 BLOCKER): _on_cancel (HALT) nullt _qso_pending_insert —
    sonst feuert ein vorgemerktes B nach dem nächsten QSO-Ende (Geister-B)."""
    m = re.search(r"def _on_cancel\(self.*?(?=\n    (?:def |@))",
                  MW_QSO_SRC, re.S)
    assert m is not None
    assert "self._qso_pending_insert = None" in m.group(0)


def test_t26_maybe_start_reuses_station_clicked():
    """T26: Einschub läuft über bestehenden _on_station_clicked-Pfad (KISS +
    alle Safety-Guards)."""
    m = re.search(r"def _p158_maybe_start_inserted_call\(self.*?(?=\n    (?:def |@))",
                  MW_QSO_SRC, re.S)
    assert m is not None
    # P166: Einschub ruft jetzt mit hard_stop=False (sanft, Auto-Resume)
    assert "self._on_station_clicked(msg, hard_stop=False)" in m.group(0)


def test_t27_maybe_start_decoupled_from_autohunt():
    """T27 (P164): _p158_maybe_start_inserted_call greift NICHT mehr auf
    _auto_hunt/take_pending_insert zu (vollständige Entkopplung)."""
    m = re.search(r"def _p158_maybe_start_inserted_call\(self.*?(?=\n    (?:def |@))",
                  MW_QSO_SRC, re.S)
    assert m is not None
    body = m.group(0)
    assert "take_pending_insert" not in body
    assert "_auto_hunt" not in body
    assert "_qso_pending_insert" in body


def test_t28_old_autohunt_insert_api_removed():
    """T28 (P164): set_pending_insert/take_pending_insert/_insert_pending_call
    sind aus auto_hunt.py ENTFERNT (Mike: alte Logik ersetzen, kein Doppel)."""
    assert "def set_pending_insert" not in AUTO_HUNT_SRC
    assert "def take_pending_insert" not in AUTO_HUNT_SRC
    assert "_insert_pending_call" not in AUTO_HUNT_SRC


def test_t29_on_message_decoded_offers_insert_before_dispatch():
    """T29: on_message_decoded prüft _p158_is_insertable_caller und reicht
    insert_call an add_rx durch (im my_call-Zweig, vor State-Machine)."""
    m = re.search(r"def on_message_decoded\(self.*?(?=\n    (?:def |@))",
                  MW_CYCLE_SRC, re.S)
    assert m is not None
    body = m.group(0)
    assert "_p158_is_insertable_caller(msg)" in body
    assert "insert_call=insert_call" in body
    assert "self._p158_insertable[msg.caller] = msg" in body


def test_t30_band_change_nulls_pending_insert():
    """T30: Bandwechsel nullt _qso_pending_insert (Pending von Band A nicht
    auf Band B feuern)."""
    assert MW_QSO_SRC or True  # Marker
    from pathlib import Path as _P
    mw_radio = (REPO / "ui" / "mw_radio.py").read_text()
    # mind. eine Clear-Stelle gekoppelt an _p158_insertable.clear()
    assert mw_radio.count("self._qso_pending_insert = None") >= 1
    # symmetrisch zu den _p158_insertable.clear()-Stellen
    assert "self._qso_pending_insert = None" in mw_radio


def test_t31_active_qso_states_alias_exists():
    """T31 (R1-F4): qso_state.py exportiert ACTIVE_QSO_STATES (semantischer
    Alias auf HASH_RESOLVE_STATES)."""
    from core.qso_state import ACTIVE_QSO_STATES, HASH_RESOLVE_STATES
    assert ACTIVE_QSO_STATES == HASH_RESOLVE_STATES


# ---------------------------------------------------------------------------
# T32-T34: echte QTextBrowser-Render + Signal-Roundtrip (kein Mock)
# ---------------------------------------------------------------------------

def test_t32_add_rx_renders_real_anchor(qapp):
    from ui.qso_panel import QSOPanel
    panel = QSOPanel()
    panel.add_rx("DA1MHH F5MYK IN97", tx_even=True,
                 slot_start_ts=0.0, insert_call="F5MYK")
    h = panel.log_view.toHtml()
    assert "huntinsert:F5MYK" in h
    assert "F5MYK IN97" in h


def test_t33_normal_rx_has_no_anchor(qapp):
    from ui.qso_panel import QSOPanel
    panel = QSOPanel()
    panel.add_rx("DA1MHH OK1ABC 73", tx_even=True, slot_start_ts=0.0)
    assert "huntinsert:" not in panel.log_view.toHtml()


def test_t34_anchor_clicked_emits_only_for_huntinsert(qapp):
    from PySide6.QtCore import QUrl
    from ui.qso_panel import QSOPanel
    panel = QSOPanel()
    captured = []
    panel.hunt_insert_clicked.connect(captured.append)
    panel._on_anchor_clicked(QUrl("huntinsert:F5MYK"))
    panel._on_anchor_clicked(QUrl("https://example.com"))
    assert captured == ["F5MYK"]
