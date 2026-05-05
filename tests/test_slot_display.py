"""Tests fuer QSO-Panel Slot-Tag/Zeit-Display-Fix (V3-Plan).

Verifiziert dass add_rx/add_tx mit explizitem tx_even/slot_start_ts
die Decoder-gesetzten Werte verwenden (latenz-frei) — und der Fallback
auf time.time() weiterhin fuer Tests/Mocks funktioniert.

Plus _assign_slot_parity:
- respektiert vom Decoder gesetzte Felder (kein Ueberschreiben)
- ergaenzt fehlende Felder per Fallback (Test-Mocks/AP-Lite-Rescue)
"""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from types import SimpleNamespace
from PySide6.QtWidgets import QApplication

from ui.qso_panel import QSOPanel


def _ensure_app():
    return QApplication.instance() or QApplication([])


def _last_line(panel: QSOPanel) -> str:
    """Letzte nicht-leere Zeile aus dem QSO-Log holen."""
    txt = panel.log_view.toPlainText()
    lines = [ln for ln in txt.splitlines() if ln.strip()]
    return lines[-1] if lines else ""


# ── add_rx ───────────────────────────────────────────────────────────────────

def test_add_rx_uses_provided_slot():
    """Wenn tx_even/slot_start_ts gesetzt sind, nutzt add_rx genau diese
    Werte fuer Tag und Zeit — unabhaengig von time.time()."""
    _ensure_app()
    panel = QSOPanel()
    # Slot-Start :15 (ODD bei FT8): Unix-Timestamp 1730000115
    # int(1730000115/15)=115333341, mod 2 = 1 → ODD ✓
    panel.add_rx("DA1MHH DA1TST -22",
                 tx_even=False, slot_start_ts=1730000115.0)
    line = _last_line(panel)
    assert "[O]" in line, f"erwartet [O], bekam: {line}"
    # Zeitstempel: 1730000115 = 2024-10-27 03:35:15 UTC → "03:35:15"
    assert "03:35:15" in line, f"erwartet 03:35:15, bekam: {line}"
    assert "DA1MHH DA1TST -22" in line


def test_add_rx_fallback_when_no_slot_info():
    """Default-Aufruf add_rx(message) ohne neue Parameter funktioniert
    weiterhin (Backward-Compat). Tag und Zeit kommen aus time.time()."""
    _ensure_app()
    panel = QSOPanel()
    panel.add_rx("CQ DA1MHH J031")  # alter Caller-Stil
    line = _last_line(panel)
    # Ein Tag muss da sein, egal welcher — Fallback laeuft durch
    assert "[E]" in line or "[O]" in line, f"kein Tag: {line}"
    assert "Empf." in line and "CQ DA1MHH J031" in line


def test_add_rx_explicit_even_overrides_wallclock():
    """tx_even=True erzwingt [E], unabhaengig wann die Funktion laeuft."""
    _ensure_app()
    panel = QSOPanel()
    # slot_start_ts auf einen ODD-Slot gesetzt, aber tx_even=True (inkonsistent
    # absichtlich). Tag folgt tx_even.
    panel.add_rx("test", tx_even=True, slot_start_ts=1730000115.0)
    line = _last_line(panel)
    assert "[E]" in line and "[O]" not in line


# ── add_tx ───────────────────────────────────────────────────────────────────

def test_add_tx_uses_provided_slot():
    """add_tx mit Slot-Parametern verwendet diese statt time.time()."""
    _ensure_app()
    panel = QSOPanel()
    # Unix 1730000100 = :00 EVEN
    panel.add_tx("CQ DA1MHH J031", "(ANT1)",
                 tx_even=True, slot_start_ts=1730000100.0)
    line = _last_line(panel)
    assert "[E]" in line
    assert "03:35:00" in line
    assert "Sende" in line and "CQ DA1MHH J031" in line


# ── _assign_slot_parity ──────────────────────────────────────────────────────

class _MockTimer:
    cycle_duration = 15.0
    def is_even_cycle(self):
        return True


class _MockSettings:
    mode = "FT8"


class _SlotParityHost:
    """Minimal-Mock fuer _assign_slot_parity-Methode (umgeht MainWindow)."""
    def __init__(self):
        self.timer = _MockTimer()
        self.settings = _MockSettings()


def _call_assign(host, messages):
    """_assign_slot_parity aus mw_cycle als gebundene Methode aufrufen."""
    from ui.mw_cycle import CycleMixin
    return CycleMixin._assign_slot_parity(host, messages)


def test_assign_slot_parity_respects_decoder():
    """Wenn Message _tx_even/_slot_start_ts hat, werden sie nicht ueberschrieben."""
    host = _SlotParityHost()
    msg = SimpleNamespace(_tx_even=False, _slot_start_ts=1730000115.0)
    _call_assign(host, [msg])
    assert msg._tx_even is False  # NICHT auf True (Timer) ueberschrieben
    assert msg._slot_start_ts == 1730000115.0


def test_assign_slot_parity_fallback():
    """Message ohne Felder bekommt Werte aus Timer-Fallback."""
    host = _SlotParityHost()
    msg = SimpleNamespace()  # weder _tx_even noch _slot_start_ts
    # ntp_time.get_time() braucht Mock — wir importieren das Modul direkt
    import core.ntp_time as ntp
    orig_get = ntp.get_time
    ntp.get_time = lambda: 1730000115.0
    try:
        _call_assign(host, [msg])
    finally:
        ntp.get_time = orig_get
    # Timer.is_even_cycle() = True → fallback_even = True
    assert msg._tx_even is True
    # 1730000115 / 15 = 115333341 → 115333341 * 15 = 1730000115 (Slot-Start)
    assert msg._slot_start_ts == 1730000115.0


def test_assign_slot_parity_partial_fields():
    """Message mit nur _tx_even (nicht _slot_start_ts) bekommt fehlendes Feld
    ergaenzt, vorhandenes bleibt."""
    host = _SlotParityHost()
    msg = SimpleNamespace(_tx_even=False)  # nur einer der beiden
    import core.ntp_time as ntp
    orig_get = ntp.get_time
    ntp.get_time = lambda: 1730000115.0
    try:
        _call_assign(host, [msg])
    finally:
        ntp.get_time = orig_get
    assert msg._tx_even is False  # bleibt
    assert msg._slot_start_ts == 1730000115.0  # ergaenzt
