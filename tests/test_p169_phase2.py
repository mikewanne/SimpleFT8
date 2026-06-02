"""P169 Phase 2 — mode-genauer Worked-Filter (call, band, mode).

Deckt ab:
- QSOLog._worked_band_mode + is_worked_on_band_mode (Basis, Normalisierung
  SUBMODE-vor-MODE, Leer-Mode nicht indiziert, Leer-Param → False, clear()).
- Auto-Hunt mode-genauer Worked-Filter (anderer Mode = waehlbar, gleicher Mode =
  gefiltert) + all_worked-Transparenz-Signal (entprellt, Reset bei Mode-Wechsel,
  kein Emit bei leerem Band / bei erfolgreichem Pick).
- rx_panel NEUE-Filter band+mode-genau via Provider + call-only-Fallback.
"""
from pathlib import Path
from types import SimpleNamespace

import pytest

from log.qso_log import QSOLog
from core.auto_hunt import AutoHunt


@pytest.fixture
def qapp():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def _cq(call, snr=-10, tx_even=True):
    """Mini-Mock einer FT8-CQ-Message fuer select_next."""
    return SimpleNamespace(is_cq=True, caller=call, grid_or_report="",
                           is_grid=False, snr=snr, freq_hz=1500, _tx_even=tx_even)


# ── QSOLog: mode-genauer Index ───────────────────────────────────────────────

def test_is_worked_on_band_mode_basics():
    q = QSOLog()
    q.add_qso("AA1AA", "20m", "FT8")
    assert q.is_worked_on_band_mode("AA1AA", "20m", "FT8")
    assert not q.is_worked_on_band_mode("AA1AA", "20m", "FT4")   # anderer Mode
    assert not q.is_worked_on_band_mode("AA1AA", "15m", "FT8")   # anderes Band
    # case-insensitiv + Portable-Suffix
    assert q.is_worked_on_band_mode("aa1aa", "20M", "ft8")
    q.add_qso("BB2BB/P", "40m", "FT4")
    assert q.is_worked_on_band_mode("BB2BB", "40m", "FT4")


def test_is_worked_on_band_mode_empty_param_returns_false():
    q = QSOLog()
    q.add_qso("AA1AA", "20m", "FT8")
    assert q.is_worked_on_band_mode("AA1AA", "20m", "") is False
    assert q.is_worked_on_band_mode("AA1AA", "20m", None) is False


def test_load_adif_submode_before_mode(tmp_path):
    """Normalisierung: SUBMODE schlaegt MODE; QRZ MODE=FT4 ⇒ FT4; FT8 ⇒ FT8."""
    p = tmp_path / "x.adi"
    p.write_text(
        "<adif_ver:5>3.1.7<eoh>\n"
        "<call:5>AA1FT <band:3>20m <mode:4>MFSK <submode:3>FT4 <eor>\n"  # → FT4
        "<call:5>BB2QZ <band:3>20m <mode:3>FT4 <eor>\n"                  # QRZ → FT4
        "<call:5>CC3F8 <band:3>20m <mode:3>FT8 <eor>\n"                  # → FT8
    )
    q = QSOLog()
    q.load_adif(p)
    assert q.is_worked_on_band_mode("AA1FT", "20m", "FT4")
    assert q.is_worked_on_band_mode("BB2QZ", "20m", "FT4")
    assert q.is_worked_on_band_mode("CC3F8", "20m", "FT8")
    assert not q.is_worked_on_band_mode("AA1FT", "20m", "FT8")   # MFSK+FT4 ≠ FT8


def test_empty_mode_not_indexed(tmp_path):
    """Leerer Mode (ADIF ohne MODE / add_qso ohne mode) wird NIE indiziert —
    der mode-blinde Index wird aber trotzdem gefuellt."""
    p = tmp_path / "y.adi"
    p.write_text("<adif_ver:5>3.1.7<eoh>\n<call:5>NM1OD <band:3>20m <eor>\n")
    q = QSOLog()
    q.load_adif(p)
    assert not q.is_worked_on_band_mode("NM1OD", "20m", "FT8")
    assert q.is_worked_on_band("NM1OD", "20m")     # mode-blind dennoch gefuellt
    q.add_qso("ZZ9ZZ", "40m")                       # kein Mode
    assert not q.is_worked_on_band_mode("ZZ9ZZ", "40m", "FT8")
    assert q.is_worked_on_band("ZZ9ZZ", "40m")


def test_clear_empties_band_mode_index():
    q = QSOLog()
    q.add_qso("AA1AA", "20m", "FT8")
    assert q.is_worked_on_band_mode("AA1AA", "20m", "FT8")
    q.clear()
    assert not q.is_worked_on_band_mode("AA1AA", "20m", "FT8")


# ── Auto-Hunt: mode-genauer Worked-Filter ────────────────────────────────────

def _hunt(log, band="20m", mode="FT8"):
    h = AutoHunt()
    h.set_qso_log(log)
    h.set_band(band)
    h.set_mode(mode)
    h.active = True
    h.start_auto_hunt(600)
    h._last_tx_even = None
    return h


def test_autohunt_worked_same_mode_filtered(qapp):
    log = QSOLog()
    log.add_qso("VP8LP", "20m", "FT8")
    h = _hunt(log, "20m", "FT8")
    assert h.select_next([_cq("VP8LP", snr=-12)], True, True) is None


def test_autohunt_worked_other_mode_still_candidate(qapp):
    log = QSOLog()
    log.add_qso("VP8LP", "20m", "FT8")
    h = _hunt(log, "20m", "FT4")            # gleicher Call+Band, anderer Mode
    res = h.select_next([_cq("VP8LP", snr=-12)], True, True)
    assert res is not None and res.call == "VP8LP"


# ── Auto-Hunt: all_worked-Transparenz-Signal ─────────────────────────────────

def test_all_worked_signal_debounced_and_reset(qapp):
    log = QSOLog()
    log.add_qso("VP8LP", "20m", "FT8")
    h = _hunt(log, "20m", "FT8")
    emitted = []
    h.all_worked.connect(lambda b, m, n: emitted.append((b, m, n)))

    # 1. Runde: rufbare Station, aber gearbeitet → genau 1 Emit
    assert h.select_next([_cq("VP8LP")], True, True) is None
    assert emitted == [("20m", "FT8", 1)]

    # 2. Runde gleiche Lage → KEIN weiterer Emit (Debounce)
    assert h.select_next([_cq("VP8LP")], True, True) is None
    assert len(emitted) == 1

    # Mode-Wechsel resettet das Flag; auf FT4 ist VP8LP neu → Pick, kein Emit
    h.set_mode("FT4")
    assert h.select_next([_cq("VP8LP")], True, True) is not None
    assert len(emitted) == 1

    # Zurueck auf FT8 (Reset durch set_mode) → wieder alle gearbeitet → neuer Emit
    h.set_mode("FT8")
    assert h.select_next([_cq("VP8LP")], True, True) is None
    assert len(emitted) == 2


def test_all_worked_not_fired_on_empty_band(qapp):
    log = QSOLog()
    h = _hunt(log, "20m", "FT8")
    emitted = []
    h.all_worked.connect(lambda *a: emitted.append(a))
    assert h.select_next([], True, True) is None        # keine CQ-Station
    assert emitted == []


def test_set_band_resets_all_worked_flag(qapp):
    log = QSOLog()
    log.add_qso("VP8LP", "20m", "FT8")
    h = _hunt(log, "20m", "FT8")
    emitted = []
    h.all_worked.connect(lambda b, m, n: emitted.append((b, m, n)))
    assert h.select_next([_cq("VP8LP")], True, True) is None
    assert len(emitted) == 1
    # set_band (auch bei aktiver Session) resettet das Flag → erneuter Emit moeglich
    h.set_band("20m")
    assert h.select_next([_cq("VP8LP")], True, True) is None
    assert len(emitted) == 2


# ── rx_panel: NEUE-Filter band+mode-genau ────────────────────────────────────

def test_rx_panel_neue_filter_band_mode_aware(qapp):
    from ui.rx_panel import RXPanel
    from core.message import parse_ft8_message
    log = QSOLog()
    log.add_qso("AA1AA", "20m", "FT8")
    panel = RXPanel()
    panel.set_qso_log(log)
    ctx = ["20m", "FT8"]
    panel.set_band_mode_provider(lambda: (ctx[0], ctx[1]))
    panel.btn_new_filter.setChecked(True)
    panel.add_message(parse_ft8_message("CQ AA1AA JO31", snr=-10, freq_hz=1500))

    # 20m FT8: gearbeitet → versteckt
    assert panel.table.isRowHidden(0) is True
    # 20m FT4: nicht gearbeitet → sichtbar
    ctx[1] = "FT4"
    panel._apply_filters()
    assert panel.table.isRowHidden(0) is False
    # 15m FT8: nicht gearbeitet → sichtbar
    ctx[0], ctx[1] = "15m", "FT8"
    panel._apply_filters()
    assert panel.table.isRowHidden(0) is False


def test_rx_panel_neue_filter_fallback_call_only(qapp):
    """Ohne Provider faellt der NEUE-Filter auf call-only is_worked zurueck
    (mode-blind, altes Verhalten — fuer Test-Setups ohne Verdrahtung)."""
    from ui.rx_panel import RXPanel
    from core.message import parse_ft8_message
    log = QSOLog()
    log.add_qso("AA1AA", "20m", "FT8")
    panel = RXPanel()
    panel.set_qso_log(log)              # KEIN Provider
    panel.btn_new_filter.setChecked(True)
    panel.add_message(parse_ft8_message("CQ AA1AA JO31", snr=-10, freq_hz=1500))
    assert panel.table.isRowHidden(0) is True   # irgendwo gearbeitet → versteckt
