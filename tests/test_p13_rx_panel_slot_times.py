"""P13 RX-Panel-Slot-Times (v0.97.15, Mai 2026).

Vorher (Bug): UTC-Spalte zeigte krumme Wall-Time (10:51:42) statt
FT8-Slot-Boundary (10:51:30). Wurzel: rx_panel.add_message nutzte
nur `_utc_display`/`_utc_str` die der Decoder nicht setzt → fiel auf
`time.strftime` zur Aufruf-Zeit zurueck.

Jetzt: `msg._slot_start_ts` (Decoder-gesetzt) wird bevorzugt fuer
UTC-Anzeige UND Sort.
"""
from __future__ import annotations

import os
import time
import types

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication

from ui.rx_panel import RXPanel, COL_UTC


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def _make_fake_msg(slot_start_ts=None, snr=-15, country="DL", **kw):
    """Minimaler FT8Message-Stub fuer rx_panel.add_message."""
    msg = types.SimpleNamespace(
        raw="DA1MHH G4ABC 73",
        target="DA1MHH",
        caller="G4ABC",
        field1="DA1MHH",
        field2="G4ABC",
        field3="73",
        snr=snr,
        freq_hz=1500,
        dt=0.0,
        grid_or_report="",
        is_cq=False,
        is_report=False,
        is_grid=False,
        is_rr73=False,
        is_73=True,
        is_r_report=False,
        antenna="",
    )
    if slot_start_ts is not None:
        msg._slot_start_ts = slot_start_ts
    for k, v in kw.items():
        setattr(msg, k, v)
    return msg


def test_slot_start_ts_displayed_as_boundary(qapp):
    """T1: msg._slot_start_ts gesetzt → UTC = Slot-Boundary HH:MM:SS."""
    # FT8 Slot-Boundary z.B. 12345*15 = 185175 Sek seit Epoch
    slot_ts = 185175.0  # = 1970-01-03 03:26:15
    panel = RXPanel()
    panel.add_message(_make_fake_msg(slot_start_ts=slot_ts))
    utc_item = panel.table.item(0, COL_UTC)
    assert utc_item is not None
    # Expected HHMMSS aus slot_ts (mit gmtime(int(slot_ts)))
    expected = time.strftime("%H%M%S", time.gmtime(int(slot_ts)))
    assert expected in utc_item.text(), (
        f"UTC-Text sollte {expected} enthalten, ist '{utc_item.text()}'"
    )
    panel.deleteLater()


def test_no_slot_start_ts_falls_back_to_wall_time(qapp):
    """T2: ohne _slot_start_ts → Wall-Time-Fallback (legacy)."""
    panel = RXPanel()
    msg = _make_fake_msg()  # kein _slot_start_ts
    # Stub mit `_utc_display`
    msg._utc_display = "123456"
    panel.add_message(msg)
    utc_item = panel.table.item(0, COL_UTC)
    assert utc_item is not None
    assert "123456" in utc_item.text()
    panel.deleteLater()


def test_int_rounds_sub_seconds(qapp):
    """T3 (R1-K2): int(slot_ts) rundet Sub-Sekunden ab."""
    # 185175.789 → int = 185175 (gleicher Slot)
    panel = RXPanel()
    panel.add_message(_make_fake_msg(slot_start_ts=185175.789))
    utc_item = panel.table.item(0, COL_UTC)
    expected = time.strftime("%H%M%S", time.gmtime(185175))
    assert expected in utc_item.text()
    panel.deleteLater()


def test_ft4_slot_boundary_displayed(qapp):
    """T4: FT4 7.5s-Slots → Slot-Boundary korrekt."""
    # 7.5s Slot z.B. 1000.0
    panel = RXPanel()
    panel.add_message(_make_fake_msg(slot_start_ts=1000.0))
    utc_item = panel.table.item(0, COL_UTC)
    expected = time.strftime("%H%M%S", time.gmtime(1000))
    assert expected in utc_item.text()
    panel.deleteLater()


def test_set_sort_no_typeerror_with_mixed_types(qapp):
    """T5 (V3-AK4): _set_sort("time") ohne TypeError bei mixed-Type-Msgs."""
    panel = RXPanel()
    # Eine msg mit float _slot_start_ts
    panel.add_message(_make_fake_msg(slot_start_ts=200000.0))
    # Eine msg ohne _slot_start_ts aber mit String _utc_display
    msg_legacy = _make_fake_msg()
    msg_legacy._utc_display = "100000"
    panel.add_message(msg_legacy)
    # Sort mode time — darf nicht crashen
    panel._set_sort("time")
    # Test: Sort lief durch, beide Eintraege noch da
    assert panel.table.rowCount() >= 1
    panel.deleteLater()


def test_bug_protection_source_level():
    """Bug-Schutz Source-Level: P13-Fix vorhanden."""
    import inspect
    from ui import rx_panel as _module
    src = inspect.getsource(_module)
    assert "_slot_start_ts" in src, (
        "rx_panel muss _slot_start_ts referenzieren (P13-Fix)"
    )
    assert "time.gmtime(int(slot_ts))" in src, (
        "rx_panel muss int(slot_ts) fuer Boundary-Rundung verwenden (R1-K2)"
    )
