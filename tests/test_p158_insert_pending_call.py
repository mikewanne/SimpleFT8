"""P158 (29.05.2026) — Wartende Station ins Auto-Hunt-QSO einschieben.

Mike-Field-Szenario: Auto-Hunt fährt ein QSO mit A. Fremde Station B ruft uns
(DA1MHH) dazwischen → Zeile `← Empf. DA1MHH F5MYK IN97` im QSO-Log. Heute geht
B verloren. P158: Zeile klickbar → B vorgemerkt → A ZU ENDE → B gerufen →
Auto-Hunt Auto-Resume.

Mike-Philosophie: RX-Liste = aktiv jagen, QSO-Fenster = passiv höflich
antworten. Klick gehört ins QSO-Log, NICHT in die RX-Liste. Abgegrenzt von
_pending_station_click (P1.24, bricht ab) + Caller-Queue (CQ-Modus).

DeepSeek-v4-pro Design-R1: 0 Blocker. Eingebaute Findings:
- 🟠1: _p158_insertable-Dict-Cleanup bei jedem Auto-Hunt-Stop
- 🟠2: expliziter their_call-Null/Leer-Check im Guard
- F1: QTextBrowser + anchorClicked statt QTextEdit-Subklasse
- F2: Hook am Ende von _on_qso_confirmed/_on_qso_timeout (TX frei, IDLE)

Tests:
- T1-T7: _p158_is_insertable_caller Logik (Source-Extraktion, kein Qt)
- T8-T11: _on_hunt_insert_clicked Guards (Mocks)
- T12-T14: _p158_maybe_start_inserted_call (mw_qso, Mocks)
- T15-T17: AutoHunt set/take/stop-Puffer-API (qapp)
- T18-T24: Source-Inspektion Verdrahtung (qso_panel/main_window/mw_qso/mw_cycle)
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


# ---------------------------------------------------------------------------
# Helper: Methode als unbound function aus mw_cycle.py extrahieren (kein Qt)
# ---------------------------------------------------------------------------

def _extract_method(src: str, name: str):
    """Extrahiert eine Methode `def <name>(self, ...)` bis zur nächsten `def`
    und exec't sie in isoliertem Namespace (vermeidet Qt-Import)."""
    # Lookahead stoppt an nächster Methode ODER deren Decorator (@Slot etc.).
    m = re.search(
        rf"def {re.escape(name)}\(self.*?(?=\n    (?:def |@))",
        src, re.S,
    )
    assert m is not None, f"Methode {name} nicht gefunden"
    # Dedent um 4: def-Zeile steht bei col 0, Body bei col 8 → col 4.
    body = "\n".join(
        line[4:] if line.startswith("    ") else line
        for line in m.group(0).splitlines()
    )
    # FT8Message-Annotation im isolierten Namespace auflösbar machen.
    ns: dict = {"FT8Message": object}
    exec(body, ns)  # noqa: S102 — kontrollierter Test-Code
    return ns[name]


def _insertable_fn():
    return _extract_method(MW_CYCLE_SRC, "_p158_is_insertable_caller")


def _make_self(
    *,
    ah_active: bool = True,
    manual_override: bool = False,
    their_call: str = "EB3JT",
    my_call: str = "DA1MHH",
):
    qso = SimpleNamespace(their_call=their_call) if their_call else None
    qso_sm = SimpleNamespace(qso=qso)
    auto_hunt = SimpleNamespace(active=ah_active, _manual_override=manual_override)
    settings = SimpleNamespace(callsign=my_call)
    return SimpleNamespace(_auto_hunt=auto_hunt, qso_sm=qso_sm, settings=settings)


def _make_msg(caller: str, *, is_73=False, is_rr73=False):
    return SimpleNamespace(caller=caller, is_73=is_73, is_rr73=is_rr73)


# ---------------------------------------------------------------------------
# T1-T7: _p158_is_insertable_caller
# ---------------------------------------------------------------------------

def test_t1_foreign_caller_during_autohunt_qso_is_insertable():
    """T1: B ruft uns während Auto-Hunt-QSO mit A → klickbar (Kern-Szenario)."""
    fn = _insertable_fn()
    self = _make_self(their_call="EB3JT")
    msg = _make_msg("F5MYK")
    assert fn(self, msg) is True


def test_t2_current_partner_not_insertable():
    """T2: Der aktuelle QSO-Partner selbst ist NICHT klickbar."""
    fn = _insertable_fn()
    self = _make_self(their_call="EB3JT")
    msg = _make_msg("EB3JT")
    assert fn(self, msg) is False


def test_t3_autohunt_inactive_not_insertable():
    """T3: Ohne aktiven Auto-Hunt kein Einschub-Angebot."""
    fn = _insertable_fn()
    self = _make_self(ah_active=False)
    assert fn(self, _make_msg("F5MYK")) is False


def test_t4_manual_override_not_insertable():
    """T4: Bei manuellem QSO (override) entscheidet User selbst, kein Angebot."""
    fn = _insertable_fn()
    self = _make_self(manual_override=True)
    assert fn(self, _make_msg("F5MYK")) is False


def test_t5_no_active_qso_not_insertable():
    """T5 (R1-🟠2): kein aktives QSO (their_call leer) → kein Einschub."""
    fn = _insertable_fn()
    self = _make_self(their_call="")
    assert fn(self, _make_msg("F5MYK")) is False
    self2 = _make_self(their_call=None)
    assert fn(self2, _make_msg("F5MYK")) is False


def test_t6_own_call_not_insertable():
    """T6: Defensive — eigener Call ist nie klickbar."""
    fn = _insertable_fn()
    self = _make_self(my_call="DA1MHH")
    assert fn(self, _make_msg("DA1MHH")) is False


def test_t7_confirmation_msgs_not_insertable():
    """T7: 73/RR73 = Bestätigung, nicht 'will Kontakt' → nicht klickbar."""
    fn = _insertable_fn()
    self = _make_self(their_call="EB3JT")
    assert fn(self, _make_msg("F5MYK", is_73=True)) is False
    assert fn(self, _make_msg("F5MYK", is_rr73=True)) is False


# ---------------------------------------------------------------------------
# T8-T11: _on_hunt_insert_clicked (Mocks)
# ---------------------------------------------------------------------------

def _click_fn():
    return _extract_method(MW_CYCLE_SRC, "_on_hunt_insert_clicked")


def _make_click_self(*, ah_active=True, their_call="EB3JT", insertable=None):
    qso = SimpleNamespace(their_call=their_call) if their_call else None
    auto_hunt = MagicMock()
    auto_hunt.active = ah_active
    return SimpleNamespace(
        _auto_hunt=auto_hunt,
        qso_sm=SimpleNamespace(qso=qso),
        qso_panel=MagicMock(),
        _p158_insertable=insertable if insertable is not None else {},
    )


def test_t8_click_happy_path_sets_pending_and_info():
    """T8: gültiger Klick → set_pending_insert + add_info."""
    fn = _click_fn()
    msg = _make_msg("F5MYK")
    self = _make_click_self(their_call="EB3JT", insertable={"F5MYK": msg})
    fn(self, "F5MYK")
    self._auto_hunt.set_pending_insert.assert_called_once_with(msg)
    assert self.qso_panel.add_info.called


def test_t9_click_ignored_when_autohunt_inactive():
    """T9: Auto-Hunt inaktiv → Klick ignoriert."""
    fn = _click_fn()
    self = _make_click_self(ah_active=False, insertable={"F5MYK": _make_msg("F5MYK")})
    fn(self, "F5MYK")
    self._auto_hunt.set_pending_insert.assert_not_called()


def test_t10_click_ignored_when_no_other_qso():
    """T10: kein aktives QSO ODER Klick == aktueller Partner → ignoriert
    (deckt veraltete Zeile nach QSO-Ende + Klick-auf-B-während-B-QSO)."""
    fn = _click_fn()
    # kein QSO
    s1 = _make_click_self(their_call="", insertable={"F5MYK": _make_msg("F5MYK")})
    fn(s1, "F5MYK")
    s1._auto_hunt.set_pending_insert.assert_not_called()
    # Klick auf aktuellen Partner
    s2 = _make_click_self(their_call="F5MYK", insertable={"F5MYK": _make_msg("F5MYK")})
    fn(s2, "F5MYK")
    s2._auto_hunt.set_pending_insert.assert_not_called()


def test_t11_click_ignored_when_call_not_in_dict():
    """T11: Call nicht (mehr) im Merk-Dict → ignoriert, kein Pending."""
    fn = _click_fn()
    self = _make_click_self(their_call="EB3JT", insertable={})
    fn(self, "F5MYK")
    self._auto_hunt.set_pending_insert.assert_not_called()


# ---------------------------------------------------------------------------
# T12-T14: _p158_maybe_start_inserted_call (mw_qso, Mocks)
# ---------------------------------------------------------------------------

def _maybe_start_fn():
    return _extract_method(MW_QSO_SRC, "_p158_maybe_start_inserted_call")


def test_t12_maybe_start_happy_path_calls_station_clicked():
    """T12: Puffer gesetzt + Auto-Hunt aktiv → _on_station_clicked(msg) +
    Dict geleert (Einschub durch bestehenden Klick-Pfad)."""
    fn = _maybe_start_fn()
    msg = _make_msg("F5MYK")
    auto_hunt = MagicMock()
    auto_hunt.active = True
    auto_hunt.take_pending_insert.return_value = msg
    self = SimpleNamespace(
        _auto_hunt=auto_hunt,
        _p158_insertable={"F5MYK": msg},
        _on_station_clicked=MagicMock(),
    )
    fn(self)
    self._on_station_clicked.assert_called_once_with(msg)
    assert self._p158_insertable == {}


def test_t13_maybe_start_noop_when_autohunt_stopped():
    """T13 (Edge-Case): Auto-Hunt zwischenzeitlich gestoppt → kein B-Start."""
    fn = _maybe_start_fn()
    auto_hunt = MagicMock()
    auto_hunt.active = False
    self = SimpleNamespace(
        _auto_hunt=auto_hunt,
        _p158_insertable={},
        _on_station_clicked=MagicMock(),
    )
    fn(self)
    self._on_station_clicked.assert_not_called()
    auto_hunt.take_pending_insert.assert_not_called()


def test_t14_maybe_start_noop_when_no_pending():
    """T14: aktiv aber kein Puffer → kein B-Start."""
    fn = _maybe_start_fn()
    auto_hunt = MagicMock()
    auto_hunt.active = True
    auto_hunt.take_pending_insert.return_value = None
    self = SimpleNamespace(
        _auto_hunt=auto_hunt,
        _p158_insertable={},
        _on_station_clicked=MagicMock(),
    )
    fn(self)
    self._on_station_clicked.assert_not_called()


# ---------------------------------------------------------------------------
# T15-T17: AutoHunt Puffer-API (qapp)
# ---------------------------------------------------------------------------

def test_t15_set_take_roundtrip(qapp):
    """T15: set_pending_insert → take_pending_insert gibt msg zurück."""
    from core.auto_hunt import AutoHunt
    ah = AutoHunt()
    sentinel = object()
    ah.set_pending_insert(sentinel)
    assert ah.take_pending_insert() is sentinel


def test_t16_take_clears_buffer(qapp):
    """T16: take leert den Puffer (zweiter take → None)."""
    from core.auto_hunt import AutoHunt
    ah = AutoHunt()
    ah.set_pending_insert(object())
    ah.take_pending_insert()
    assert ah.take_pending_insert() is None


def test_t17_stop_clears_pending_insert(qapp):
    """T17 (R1-🟠1 + Edge-Case): Session-Ende verwirft den Puffer."""
    from core.auto_hunt import AutoHunt
    ah = AutoHunt()
    ah.active = True
    ah.set_pending_insert(object())
    ah.stop_auto_hunt("manual_halt")
    assert ah.take_pending_insert() is None


# ---------------------------------------------------------------------------
# T18-T24: Source-Inspektion Verdrahtung
# ---------------------------------------------------------------------------

def test_t18_qso_panel_uses_qtextbrowser_with_anchor():
    """T18 (F1): log_view ist QTextBrowser, Links abgefangen via anchorClicked,
    Auto-Navigation aus."""
    assert "self.log_view = QTextBrowser()" in QSO_PANEL_SRC
    assert "setOpenLinks(False)" in QSO_PANEL_SRC
    assert "anchorClicked.connect(self._on_anchor_clicked)" in QSO_PANEL_SRC
    assert "hunt_insert_clicked = Signal(str)" in QSO_PANEL_SRC


def test_t19_add_rx_has_insert_call_param_and_anchor_render():
    """T19: add_rx kennt insert_call; rx-Render nutzt _append_anchor_line."""
    assert "insert_call: str = \"\"" in QSO_PANEL_SRC
    assert "_append_anchor_line" in QSO_PANEL_SRC
    # Anchor-Helper baut huntinsert:-href
    assert "huntinsert:" in QSO_PANEL_SRC


def test_t20_main_window_inits_dict_and_wires_signal():
    """T20: _p158_insertable initialisiert + hunt_insert_clicked verdrahtet."""
    assert "self._p158_insertable" in MAIN_WINDOW_SRC
    assert "hunt_insert_clicked.connect(self._on_hunt_insert_clicked)" in MAIN_WINDOW_SRC


def test_t21_main_window_clears_dict_on_stop():
    """T21 (R1-🟠1): _on_auto_hunt_stopped leert das Merk-Dict."""
    m = re.search(r"def _on_auto_hunt_stopped\(self.*?(?=\n    def )",
                  MAIN_WINDOW_SRC, re.S)
    assert m is not None
    assert "_p158_insertable.clear()" in m.group(0)


def test_t22_hook_in_both_qso_end_handlers():
    """T22 (F2): _p158_maybe_start_inserted_call in _on_qso_confirmed UND
    _on_qso_timeout aufgerufen."""
    conf = re.search(r"def _on_qso_confirmed\(self.*?(?=\n    def )",
                     MW_QSO_SRC, re.S)
    tmo = re.search(r"def _on_qso_timeout\(self.*?(?=\n    def )",
                    MW_QSO_SRC, re.S)
    assert conf and "_p158_maybe_start_inserted_call()" in conf.group(0)
    assert tmo and "_p158_maybe_start_inserted_call()" in tmo.group(0)


def test_t23_maybe_start_reuses_station_clicked():
    """T23: Einschub läuft über bestehenden _on_station_clicked-Pfad
    (kein dupliziertes Start-Logik — KISS + Auto-Resume gratis)."""
    m = re.search(r"def _p158_maybe_start_inserted_call\(self.*?(?=\n    def )",
                  MW_QSO_SRC, re.S)
    assert m is not None
    assert "self._on_station_clicked(msg)" in m.group(0)


def test_t24_on_message_decoded_offers_insert_before_dispatch():
    """T24: on_message_decoded prüft _p158_is_insertable_caller und reicht
    insert_call an add_rx durch (im my_call-Zweig, vor State-Machine)."""
    m = re.search(r"def on_message_decoded\(self.*?(?=\n    def )",
                  MW_CYCLE_SRC, re.S)
    assert m is not None
    body = m.group(0)
    assert "_p158_is_insertable_caller(msg)" in body
    assert "insert_call=insert_call" in body
    assert "self._p158_insertable[msg.caller] = msg" in body


# ---------------------------------------------------------------------------
# T25-T27: Echte QTextBrowser-Render + Signal-Roundtrip (kein Mock)
# ---------------------------------------------------------------------------

def test_t25_add_rx_renders_real_anchor(qapp):
    """T25 (F1 real): add_rx(insert_call=...) erzeugt einen echten HTML-Anchor
    mit huntinsert:-href im QTextBrowser-Dokument."""
    from ui.qso_panel import QSOPanel
    panel = QSOPanel()
    panel.add_rx("DA1MHH F5MYK IN97", tx_even=True,
                 slot_start_ts=0.0, insert_call="F5MYK")
    h = panel.log_view.toHtml()
    assert "huntinsert:F5MYK" in h
    assert "F5MYK IN97" in h


def test_t26_normal_rx_has_no_anchor(qapp):
    """T26: normale RX-Zeile (ohne insert_call) bleibt Plain — kein huntinsert."""
    from ui.qso_panel import QSOPanel
    panel = QSOPanel()
    panel.add_rx("DA1MHH OK1ABC 73", tx_even=True, slot_start_ts=0.0)
    assert "huntinsert:" not in panel.log_view.toHtml()


def test_t27_anchor_clicked_emits_only_for_huntinsert(qapp):
    """T27: _on_anchor_clicked emittiert hunt_insert_clicked(call) nur für
    huntinsert:-Links, ignoriert fremde URLs."""
    from PySide6.QtCore import QUrl
    from ui.qso_panel import QSOPanel
    panel = QSOPanel()
    captured = []
    panel.hunt_insert_clicked.connect(captured.append)
    panel._on_anchor_clicked(QUrl("huntinsert:F5MYK"))
    panel._on_anchor_clicked(QUrl("https://example.com"))
    assert captured == ["F5MYK"]
