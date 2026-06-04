"""v0.99.7 — Auto-Hunt aus akkumuliertem Pool + Frische-Fenster + Worked-Schalter.

Deckt ab:
- AUTO_HUNT_FRESH_SLOTS-Konstante (modus-aware, alle 3).
- set_skip_worked / _skip_worked-Default + Worked-Filter an/aus (Diplom-Modus).
- all_worked feuert im Diplom-Modus NIE.
- _build_auto_hunt_pool (mw_cycle): Frische-Filter (frisch drin / alt raus),
  is_cq-Live-Filter, +1s-Jitter-Puffer, modus-aware Slot-Dauer, Pool-Auswahl.

Reine State-/Auswahl-Logik. Kein TX-Pfad, ANT1/ANT2 unberuehrt.
"""
from __future__ import annotations

import time
from types import SimpleNamespace

import pytest

from core.auto_hunt import AutoHunt, AUTO_HUNT_FRESH_SLOTS
from core.message import FT8Message
from log.qso_log import QSOLog
from ui.mw_cycle import CycleMixin


@pytest.fixture
def qapp():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


# ─────────────────────────────────────────────────────────────────────────────
# A) Frische-Konstante
# ─────────────────────────────────────────────────────────────────────────────

def test_fresh_slots_constant_all_three():
    """Alle Modi 3 Slots — FT4 bewusst NICHT mehr (CQ ruft modus-invariant
    jeden 2. Slot; FT4 ruft haeufiger, faengt man schneller)."""
    assert AUTO_HUNT_FRESH_SLOTS == {"FT8": 3, "FT4": 3, "FT2": 3}


# ─────────────────────────────────────────────────────────────────────────────
# B) Worked-Schalter (Diplom-Modus)
# ─────────────────────────────────────────────────────────────────────────────

def _cq(call, snr=-10, tx_even=True):
    return SimpleNamespace(is_cq=True, caller=call, grid_or_report="",
                           is_grid=False, snr=snr, freq_hz=1500, _tx_even=tx_even)


def _hunt(log, band="20m", mode="FT8"):
    h = AutoHunt()
    h.set_qso_log(log)
    h.set_band(band)
    h.set_mode(mode)
    h.active = True
    h.start_auto_hunt(600)
    h._last_tx_even = None
    return h


def test_skip_worked_default_true():
    assert AutoHunt()._skip_worked is True


def test_set_skip_worked_toggles():
    h = AutoHunt()
    h.set_skip_worked(False)
    assert h._skip_worked is False
    h.set_skip_worked(True)
    assert h._skip_worked is True


def test_worked_filtered_when_skip_on(qapp):
    """Default: gearbeitete Station auf Band+Mode wird gefiltert (wie P169)."""
    log = QSOLog()
    log.add_qso("VP8LP", "20m", "FT8")
    h = _hunt(log, "20m", "FT8")          # _skip_worked default True
    assert h.select_next([_cq("VP8LP", snr=-12)], True, True) is None


def test_worked_still_called_when_skip_off(qapp):
    """Diplom-Modus: gearbeitete Station bleibt Kandidat."""
    log = QSOLog()
    log.add_qso("VP8LP", "20m", "FT8")
    h = _hunt(log, "20m", "FT8")
    h.set_skip_worked(False)
    res = h.select_next([_cq("VP8LP", snr=-12)], True, True)
    assert res is not None and res.call == "VP8LP"


def test_all_worked_never_fires_in_diploma_mode(qapp):
    """Bei _skip_worked=False darf die „alle gearbeitet"-Meldung NIE feuern —
    gearbeitete sind ja gewollte Ziele."""
    log = QSOLog()
    log.add_qso("VP8LP", "20m", "FT8")
    h = _hunt(log, "20m", "FT8")
    h.set_skip_worked(False)
    emitted = []
    h.all_worked.connect(lambda *a: emitted.append(a))
    h.select_next([_cq("VP8LP")], True, True)
    assert emitted == []


# ─────────────────────────────────────────────────────────────────────────────
# C) Pool-Builder (mw_cycle._build_auto_hunt_pool)
# ─────────────────────────────────────────────────────────────────────────────

def _pool_msg(call, last_heard, is_cq=True):
    """Echte FT8Message (is_cq ist Live-Property aus field1) + _last_heard."""
    if is_cq:
        m = FT8Message(raw=f"CQ {call} JO31", field1="CQ",
                       field2=call, field3="JO31", snr=-10, freq_hz=1500)
    else:
        m = FT8Message(raw=f"{call} DA1MHH -05", field1=call,
                       field2="DA1MHH", field3="-05", snr=-10, freq_hz=1500)
    m._last_heard = last_heard
    m._tx_even = True
    return m


def _mock_self(stations, mode="FT8", slot=15.0, rx_mode="diversity"):
    return SimpleNamespace(
        _diversity_stations=stations if rx_mode == "diversity" else {},
        _normal_stations=stations if rx_mode != "diversity" else {},
        _rx_mode=rx_mode,
        timer=SimpleNamespace(cycle_duration=slot),
        settings=SimpleNamespace(mode=mode),
    )


def test_pool_fresh_in_old_out_ft8():
    """FT8: max_age = 3*15 + 1 = 46s. 40s alt → drin, 50s alt → raus."""
    now = time.time()
    stations = {
        "FRESH": _pool_msg("FRESH", now - 40),
        "OLD": _pool_msg("OLD", now - 50),
    }
    pool = CycleMixin._build_auto_hunt_pool(_mock_self(stations, "FT8", 15.0))
    calls = {m.caller for m in pool}
    assert calls == {"FRESH"}


def test_pool_excludes_non_cq():
    """is_cq ist Live-Property — eine Station ohne CQ-Text faellt raus."""
    now = time.time()
    stations = {
        "CQER": _pool_msg("CQER", now - 5, is_cq=True),
        "INQSO": _pool_msg("INQSO", now - 5, is_cq=False),
    }
    pool = CycleMixin._build_auto_hunt_pool(_mock_self(stations, "FT8", 15.0))
    calls = {m.caller for m in pool}
    assert calls == {"CQER"}


def test_pool_jitter_buffer_one_second():
    """+1s-Puffer: eine Station exakt bei 3*slot (45.5s) bleibt drin (≤46),
    knapp drueber (46.5s) faellt raus — beweist den Puffer."""
    now = time.time()
    stations = {
        "EDGE_IN": _pool_msg("EDGE_IN", now - 45.5),
        "EDGE_OUT": _pool_msg("EDGE_OUT", now - 46.5),
    }
    pool = CycleMixin._build_auto_hunt_pool(_mock_self(stations, "FT8", 15.0))
    calls = {m.caller for m in pool}
    assert calls == {"EDGE_IN"}


def test_pool_mode_aware_ft4_shorter_window():
    """FT4: slot=7.5 → max_age = 3*7.5 + 1 = 23.5s. Eine 30s-alte Station, die
    auf FT8 (46s) noch frisch waere, faellt auf FT4 raus."""
    now = time.time()
    stations = {"S": _pool_msg("S", now - 30)}
    pool_ft8 = CycleMixin._build_auto_hunt_pool(_mock_self(stations, "FT8", 15.0))
    pool_ft4 = CycleMixin._build_auto_hunt_pool(_mock_self(stations, "FT4", 7.5))
    assert {m.caller for m in pool_ft8} == {"S"}
    assert pool_ft4 == []


def test_pool_unknown_mode_defaults_to_three():
    """Unbekannter Modus → Default 3 Slots (kein KeyError)."""
    now = time.time()
    stations = {"S": _pool_msg("S", now - 40)}
    pool = CycleMixin._build_auto_hunt_pool(_mock_self(stations, "ZZ", 15.0))
    assert {m.caller for m in pool} == {"S"}


def test_pool_empty_when_all_stale():
    now = time.time()
    stations = {"OLD1": _pool_msg("OLD1", now - 200),
                "OLD2": _pool_msg("OLD2", now - 999)}
    pool = CycleMixin._build_auto_hunt_pool(_mock_self(stations, "FT8", 15.0))
    assert pool == []
