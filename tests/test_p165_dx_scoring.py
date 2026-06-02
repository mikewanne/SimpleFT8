"""P165 — Auto-Hunt DX-Scoring (Seltenheit > Land-auf-Band-neu > Distanz > SNR).

Mike-Feldtest 02.06.2026: Auto-Hunt soll seltene/weite DX-Perlen bevorzugen
statt der naechsten lauten Europa-Station. SNR ist kein K.o.-Kriterium mehr —
FT8 ist ein Schwachsignal-DX-Modus.

Run: QT_QPA_PLATFORM=offscreen ./venv/bin/python3 -m pytest tests/test_p165_dx_scoring.py -v
"""
from __future__ import annotations

import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from types import SimpleNamespace

import pytest

from core.auto_hunt import (
    AutoHunt, country_rarity_class, SNR_FLOOR, _RARITY_UNKNOWN,
)
from core.geo import callsign_to_country
from log.qso_log import QSOLog


@pytest.fixture
def qapp():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def _seed(log: QSOLog, call: str, count: int, bands=()):
    """Fake-Historie: Land von `call` mit `count` QSOs + optional Baender setzen.

    Bestimmt das Land ueber callsign_to_country (wie der Live-Pfad), damit
    Historie und Live-Lookup garantiert denselben Schluessel verwenden.
    """
    cty = callsign_to_country(call)
    log._country_count[cty] = count
    for b in bands:
        log._country_band.add((cty, b.upper()))


def _cand(call: str, snr: int = -10, tx_even: bool = True):
    """Minimaler _HuntCandidate-Stand-in fuer _compute_priority."""
    return SimpleNamespace(call=call, snr=snr, tx_even=tx_even)


def _cq(call: str, snr: int = -10, tx_even: bool = True):
    """Mini-Mock einer FT8-CQ-Message fuer select_next."""
    return SimpleNamespace(is_cq=True, caller=call, grid_or_report="",
                           is_grid=False, snr=snr, freq_hz=1500, _tx_even=tx_even)


def _hunt(log: QSOLog | None = None, band: str = "20m", grid: str = "JO31"):
    h = AutoHunt()
    if log is not None:
        h.set_qso_log(log)
    h.set_band(band)
    h.set_my_grid(grid)
    h.start_auto_hunt(600)
    h._last_tx_even = None  # kein Slot-Vorzug in den Scoring-Tests
    return h


# ── country_rarity_class ────────────────────────────────────────────

def test_rarity_class_boundaries():
    assert country_rarity_class(0) == 0     # ATNO
    assert country_rarity_class(1) == 1
    assert country_rarity_class(5) == 1
    assert country_rarity_class(6) == 2
    assert country_rarity_class(20) == 2
    assert country_rarity_class(21) == 3
    assert country_rarity_class(100) == 3
    assert country_rarity_class(101) == 4
    assert country_rarity_class(4000) == 4


# ── qso_log Laender-API ─────────────────────────────────────────────

def test_qso_log_counts_countries_via_add():
    log = QSOLog()
    log.add_qso("DL1ABC", "20m")
    log.add_qso("DL2XYZ", "40m")
    log.add_qso("VP8LP", "20m")
    assert log.get_country_count("Germany") == 2
    assert log.get_country_count("Falkland") == 1
    assert log.get_country_count("Japan") == 0  # nie gearbeitet
    assert log.is_country_worked_on_band("Germany", "20m") is True
    assert log.is_country_worked_on_band("Germany", "40m") is True
    assert log.is_country_worked_on_band("Falkland", "40m") is False


# ── Kern: Worked Examples (DeepSeek-Tabelle) ────────────────────────

def test_falkland_atno_beats_strong_local(qapp):
    """Schwaches Falkland-ATNO (-24 dB) schlaegt laute neue DL-Station (+5 dB)."""
    log = QSOLog()
    _seed(log, "DL9XYZ", 4000, ["20M"])  # Allerweltsland, schon
    h = _hunt(log)
    p_vp8 = h._compute_priority(_cand("VP8LP", snr=-24))
    p_dl = h._compute_priority(_cand("DL9XYZ", snr=5))
    assert p_vp8 < p_dl, "Falkland-ATNO muss vor lauter DL-Station liegen"


def test_rare_near_beats_common_far(qapp):
    """Nahe ATNO-Perle (San Marino) schlaegt weite, haeufige Station (Japan 30x).

    Persoenliche Seltenheit ist Leitmaß — Distanz nur Tiebreaker bei gleicher R.
    """
    log = QSOLog()
    _seed(log, "JA1ABC", 30, ["20M"])  # Klasse 3
    h = _hunt(log)
    p_sm = h._compute_priority(_cand("T70A", snr=-5))    # ATNO, nah
    p_ja = h._compute_priority(_cand("JA1ABC", snr=-10))  # weit, aber haeufig
    assert p_sm < p_ja, "Nahe ATNO schlaegt weites haeufiges Land"


def test_full_ranking_matches_deepseek_table(qapp):
    """Komplette Rangfolge: Falkland > San Marino > Japan > USA > Deutschland."""
    log = QSOLog()
    _seed(log, "DL9XYZ", 4000, ["20M"])
    _seed(log, "JA1ABC", 30, ["20M"])
    _seed(log, "W1ABC", 200, ["40M"])  # USA: auf 20m NEU (nur 40m gehabt)
    # VP8LP (Falkland) + T70A (San Marino): nie gearbeitet → ATNO
    h = _hunt(log)
    cands = [_cand("VP8LP", -24), _cand("DL9XYZ", 5), _cand("JA1ABC", -10),
             _cand("T70A", -5), _cand("W1ABC", -8)]
    calls = [c.call for c in sorted(cands, key=h._compute_priority)]
    assert calls == ["VP8LP", "T70A", "JA1ABC", "W1ABC", "DL9XYZ"], calls


def test_band_new_country_upgraded(qapp):
    """Land auf NEUEM Band wird ueber dasselbe Land auf altem Band gestuft."""
    log = QSOLog()
    _seed(log, "JA1ABC", 30, ["20M"])  # Japan auf 20m gehabt, 40m NICHT
    # Auf 40m ist Japan ein neues Band-Land → band_new=0
    h40 = _hunt(log, band="40m")
    h20 = _hunt(log, band="20m")
    p_ja_40 = h40._compute_priority(_cand("JA2NEW", snr=-12))
    p_ja_20 = h20._compute_priority(_cand("JA2NEW", snr=-12))
    # Gleiche R(3)+Distanz+SNR, aber band_new unterscheidet (0 < 1)
    assert p_ja_40[1] == 0 and p_ja_20[1] == 1
    assert p_ja_40 < p_ja_20


# ── select_next-Integration ─────────────────────────────────────────

def test_select_next_picks_rarest(qapp):
    """select_next waehlt aus echten Messages die seltenste/beste Station."""
    log = QSOLog()
    _seed(log, "DL9XYZ", 4000, ["20M"])
    h = _hunt(log)
    msgs = [_cq("DL9XYZ", snr=8), _cq("VP8LP", snr=-22)]
    best = h.select_next(msgs, qso_idle=True, presence_ok=True)
    assert best is not None
    assert best.call == "VP8LP", "Auto-Hunt muss die Falkland-Perle picken"


def test_worked_station_on_band_skipped(qapp):
    """Schon gearbeitete STATION (Call+Band) wird uebersprungen (keine Dublette).

    Eine ANDERE Station aus demselben Land bleibt waehlbar.
    """
    log = QSOLog()
    # P169 Phase 2: mode-genauer Filter → Mode mitgeben (Hunt default FT8).
    log.add_qso("VP8LP", "20m", "FT8")  # diese exakte Station auf 20m FT8 schon gehabt
    h = _hunt(log)
    # Nur die bereits gearbeitete Station ruft → nichts zu tun
    assert h.select_next([_cq("VP8LP", snr=-12)], True, True) is None
    # Andere Falkland-Station (neuer Call) → waehlbar
    best = h.select_next([_cq("VP8XYZ", snr=-12)], True, True)
    assert best is not None and best.call == "VP8XYZ"


def test_weak_signal_passes_floor_but_noise_rejected(qapp):
    """-24 dB (echte FT8-DX) kommt durch, -27 dB (unter Boden) wird verworfen."""
    log = QSOLog()
    h = _hunt(log)
    assert h.select_next([_cq("VP8LP", snr=-24)], True, True) is not None
    assert h.select_next([_cq("VP8LP", snr=SNR_FLOOR - 1)], True, True) is None


def test_unknown_country_is_neutral_not_atno(qapp):
    """Unaufloesbares Land ('?') ist neutral (Mitte), NICHT ATNO-Perle (0)."""
    log = QSOLog()
    h = _hunt(log)
    # Kunst-Call den die Praefix-Map nicht kennt → '?'
    fake = "QZ9ZZ"
    assert callsign_to_country(fake) == "?"
    prio = h._compute_priority(_cand(fake, snr=-10))
    assert prio[0] == _RARITY_UNKNOWN
    assert prio[0] != 0, "Unbekannt darf NICHT als ATNO ganz nach oben"


def test_no_qso_log_uses_neutral_rarity(qapp):
    """Ohne QSO-Log faellt das Scoring auf neutrale Seltenheit zurueck (Crash-frei)."""
    h = _hunt(log=None)
    prio = h._compute_priority(_cand("VP8LP", snr=-10))
    assert prio[0] == _RARITY_UNKNOWN
