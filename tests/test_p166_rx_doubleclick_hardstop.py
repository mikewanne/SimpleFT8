"""P166 (01.06.2026) — RX-Listen-Doppelklick = harter Auto-Hunt-Stop.

Mike-Spec (Field 01.06.2026): Ein Doppelklick in der Empfangsliste ist eine
BEWUSSTE Übernahme durch den Operator → ALLES unterbrechen (laufendes CQ,
laufendes QSO, aktiver Auto-Hunt) und sofort die geklickte Station rufen.
KEIN Auto-Resume — Auto-Hunt ist beendet bis zum nächsten User-Start.

Abgrenzung (bleibt unverändert): Der P164-Klick im QSO-FENSTER ist höflich →
`hard_stop=False` (pausieren + Auto-Resume). Nur der RX-Listen-Klick stoppt hart.

Umsetzung: `_on_station_clicked(msg, hard_stop=True)` — ein Stop-Block GANZ OBEN
(vor allen Vorab-Returns) ruft `stop_auto_hunt("manual_halt")` und verwirft den
P164-Einschub-Merker. Getestet über den kurzen SWR-Sperre-Pfad (returnt direkt
nach dem Stop-Block, isoliert ihn vom komplexen start_qso-Pfad) + Source-
Inspektion der Verdrahtung.

Run: QT_QPA_PLATFORM=offscreen ./venv/bin/python3 -m pytest tests/test_p166_rx_doubleclick_hardstop.py -v
"""
from __future__ import annotations

import re
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

REPO = Path(__file__).resolve().parent.parent
MW_QSO_SRC = (REPO / "ui" / "mw_qso.py").read_text()
MW_CYCLE_SRC = (REPO / "ui" / "mw_cycle.py").read_text()
MAIN_WINDOW_SRC = (REPO / "ui" / "main_window.py").read_text()


def _extract_method(src: str, name: str):
    """Extrahiert `def <name>(self, ...)` bis zur nächsten def/@ und exec't sie."""
    m = re.search(rf"def {re.escape(name)}\(self.*?(?=\n    (?:def |@))", src, re.S)
    assert m is not None, f"Methode {name} nicht gefunden"
    body = "\n".join(
        line[4:] if line.startswith("    ") else line
        for line in m.group(0).splitlines()
    )
    ns: dict = {"FT8Message": object}
    exec(body, ns)  # noqa: S102 — kontrollierter Test-Code
    return ns[name]


def _click_fn():
    return _extract_method(MW_QSO_SRC, "_on_station_clicked")


def _make_self(*, auto_hunt_active=True, pending=None, insertable=None,
               band="20m", blocked=("20M",)):
    """Mock-self das den kurzen SWR-Sperre-Pfad fährt: Stop-Block läuft GANZ
    OBEN, dann return beim SWR-Check → isoliert den P166-Stop-Block."""
    return SimpleNamespace(
        _auto_hunt=MagicMock(active=auto_hunt_active),
        _qso_pending_insert=pending,
        _p158_insertable=dict(insertable or {}),
        settings=SimpleNamespace(band=band),
        _swr_blocked_bands=set(blocked),
        encoder=SimpleNamespace(is_transmitting=False),
        qso_panel=MagicMock(),
    )


def _msg(call="VP8LP"):
    return SimpleNamespace(caller=call)


# ── Harter Stop (RX-Doppelklick, hard_stop=True default) ─────────────

def test_hard_stop_stops_auto_hunt_not_pause():
    """RX-Doppelklick (Default) → stop_auto_hunt('manual_halt'), NICHT pausieren."""
    fn = _click_fn()
    self = _make_self(auto_hunt_active=True)
    fn(self, _msg())  # hard_stop default True
    self._auto_hunt.stop_auto_hunt.assert_called_once_with("manual_halt")
    self._auto_hunt.on_manual_qso_start.assert_not_called()


def test_hard_stop_clears_pending_insert():
    """Harter Stop verwirft den P164-Einschub-Merker (wie HALT)."""
    fn = _click_fn()
    pending = _msg("F5MYK")
    self = _make_self(pending=pending, insertable={"F5MYK": pending})
    fn(self, _msg("VP8LP"))
    assert self._qso_pending_insert is None
    assert self._p158_insertable == {}


def test_hard_stop_greift_auch_bei_swr_sperre():
    """F4: Auch wenn der Ruf an der Bandsperre scheitert, ist Auto-Hunt gestoppt
    (Stop-Block steht VOR dem SWR-Return)."""
    fn = _click_fn()
    self = _make_self(auto_hunt_active=True, band="20m", blocked=("20M",))
    fn(self, _msg())
    self._auto_hunt.stop_auto_hunt.assert_called_once_with("manual_halt")
    # Ruf selbst wurde abgebrochen (SWR-Sperre-Meldung), kein start_qso
    assert self.qso_panel.add_info.called


def test_hard_stop_noop_when_auto_hunt_inactive():
    """Auto-Hunt nicht aktiv → kein stop_auto_hunt, aber Merker wird genullt."""
    fn = _click_fn()
    pending = _msg("F5MYK")
    self = _make_self(auto_hunt_active=False, pending=pending)
    fn(self, _msg("VP8LP"))
    self._auto_hunt.stop_auto_hunt.assert_not_called()
    assert self._qso_pending_insert is None


# ── Sanft (P164-Einschub, hard_stop=False) ──────────────────────────

def test_soft_does_not_hard_stop():
    """hard_stop=False (P164) → KEIN stop_auto_hunt, Merker bleibt erhalten."""
    fn = _click_fn()
    pending = _msg("F5MYK")
    self = _make_self(auto_hunt_active=True, pending=pending,
                      insertable={"F5MYK": pending})
    fn(self, _msg("VP8LP"), hard_stop=False)
    self._auto_hunt.stop_auto_hunt.assert_not_called()
    # Merker NICHT verworfen (P164 will den Einschub behalten/resumen)
    assert self._qso_pending_insert is pending
    assert self._p158_insertable == {"F5MYK": pending}


# ── Source-Inspektion: Verdrahtung der Aufrufer ─────────────────────

def test_signature_default_hard_stop_true():
    """_on_station_clicked hat hard_stop mit Default True (RX-Klick = Standard)."""
    assert "def _on_station_clicked(self, msg: FT8Message, hard_stop: bool = True)" \
        in MW_QSO_SRC


def test_stop_block_before_swr_check():
    """Der harte Stop-Block steht VOR dem SWR-Sperre-Check (F4: greift immer)."""
    m = re.search(r"def _on_station_clicked\(self.*?(?=\n    (?:def |@))",
                  MW_QSO_SRC, re.S)
    body = m.group(0)
    idx_stop = body.find('stop_auto_hunt("manual_halt")')
    idx_swr = body.find("_swr_blocked_bands")
    assert idx_stop > 0 and idx_swr > 0
    assert idx_stop < idx_swr, "Stop-Block muss VOR dem SWR-Check stehen"


def test_p164_idle_path_is_soft():
    """mw_cycle._on_hunt_insert_clicked (P164 QSO-Fenster) ruft im IDLE-Fall
    mit hard_stop=False (sanft)."""
    m = re.search(r"def _on_hunt_insert_clicked\(self.*?(?=\n    (?:def |@))",
                  MW_CYCLE_SRC, re.S)
    assert "self._on_station_clicked(msg, hard_stop=False)" in m.group(0)


def test_tx_buffer_resume_is_hard():
    """TX-Buffer-Resume ruft _on_station_clicked OHNE hard_stop → Default True
    (war ein RX-Klick, soll hart stoppen)."""
    # Der gepufferte Resume-Aufruf nutzt den Default (kein explizites False).
    assert "self._on_station_clicked(buffered)" in MW_QSO_SRC
    assert "self._on_station_clicked(buffered, hard_stop=False)" not in MW_QSO_SRC


def test_rx_signal_uses_default_hard_stop():
    """RX-Panel-Signal verbindet auf _on_station_clicked ohne hard_stop-Override
    → Default True (RX-Listen-Doppelklick = harter Stop)."""
    assert "self.rx_panel.station_clicked.connect(self._on_station_clicked)" \
        in MAIN_WINDOW_SRC
