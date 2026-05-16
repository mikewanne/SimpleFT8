"""P61 (v0.97.33): Auto-Hunt Recent-QSO-Cooldown.

Mike-Field-Test 15.05.2026 morgens: Auto-Hunt picked HA8RC 30s nach
abgeschlossenem QSO erneut. Existierende `qso_log.is_worked_on_band`-
Filterung hat aus unbekannten Gruenden versagt (Race oder
ADIF-Exception denkbar).

Fix: zusaetzliche Cooldown-Schicht in AutoHunt mit Key (call, band, mode),
gefuellt SOFORT beim Pick. Belt-and-Suspenders gegen Race + ADIF-Fehler.
"""

from __future__ import annotations

import inspect
import re
import time
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from core.auto_hunt import AutoHunt, _RECENT_QSO_COOLDOWN_S


def _msg(call: str, is_cq: bool = True, snr: int = 0,
         freq_hz: int = 1500, tx_even: bool = True):
    """Mini-FT8-Message-Mock fuer select_next."""
    m = MagicMock()
    m.is_cq = is_cq
    m.caller = call
    m.snr = snr
    m.freq_hz = freq_hz
    m.grid_or_report = ""
    m.is_grid = False
    m._tx_even = tx_even
    return m


def _make_hunt(band: str = "20m", mode: str = "FT8") -> AutoHunt:
    """AutoHunt mit aktiver Session und gesetztem qso_log-Mock."""
    h = AutoHunt()
    h.active = True
    h._manual_override = False
    h.set_band(band)
    h.set_mode(mode)
    # qso_log-Mock: is_worked True (worst case — Test sollte trotzdem
    # filtern weil _recent_qso vorhanden ist). Default ist Filter-Logik
    # in select_next.
    qso_log = MagicMock()
    qso_log.is_worked.return_value = False  # Erste QSO simuliert
    qso_log.is_worked_on_band.return_value = False
    h.set_qso_log(qso_log)
    return h


# ── T1 — select_next direkt nach mark_pick → None ──────────────────────────

def test_t1_pick_blockt_sofort():
    """T1: mark_pick → select_next sofort danach gibt None."""
    h = _make_hunt()
    h.mark_pick("HA8RC")
    # Selbe Station nochmal anbieten
    result = h.select_next(
        messages=[_msg("HA8RC")],
        qso_idle=True,
        presence_ok=True,
    )
    assert result is None, "Cooldown muss direkten Re-Pick blocken"


# ── T2 — nach Ablauf wieder pickbar ────────────────────────────────────────

def test_t2_cooldown_ablauf_pickbar():
    """T2: 301s nach mark_pick → Pick erlaubt (Lazy-Cleanup entfernt Eintrag)."""
    h = _make_hunt()
    h.mark_pick("HA8RC")
    # Künstlich Eintrag in die Vergangenheit setzen
    key = ("HA8RC", "20M", "FT8")
    h._recent_qso[key] = time.time() - (_RECENT_QSO_COOLDOWN_S + 1)
    result = h.select_next(
        messages=[_msg("HA8RC")],
        qso_idle=True,
        presence_ok=True,
    )
    assert result is not None, "Nach Cooldown-Ablauf muss Pick erlaubt sein"
    assert result.call == "HA8RC"
    # Lazy-Cleanup: Eintrag muss entfernt sein
    assert key not in h._recent_qso, "Lazy-Cleanup muss abgelaufenen Eintrag entfernen"


# ── T3 — Band-Wechsel: selbes Call auf anderem Band sofort pickbar ─────────

def test_t3_anderes_band_sofort_pickbar():
    """T3: HA8RC auf 20m im Cooldown — wechsel auf 40m → sofort pickbar."""
    h = _make_hunt(band="20m")
    h.mark_pick("HA8RC")
    # Sicherstellen dass Eintrag wirklich da
    assert ("HA8RC", "20M", "FT8") in h._recent_qso
    # Bandwechsel
    h.set_band("40m")
    result = h.select_next(
        messages=[_msg("HA8RC")],
        qso_idle=True,
        presence_ok=True,
    )
    assert result is not None, "Cooldown muss band-spezifisch sein"
    assert result.call == "HA8RC"


# ── T4 — Mode-Wechsel: selbes Call auf anderem Mode sofort pickbar ─────────

def test_t4_anderes_mode_sofort_pickbar():
    """T4: HA8RC auf FT8 im Cooldown — wechsel auf FT4 → sofort pickbar."""
    h = _make_hunt(mode="FT8")
    h.mark_pick("HA8RC")
    h.set_mode("FT4")
    result = h.select_next(
        messages=[_msg("HA8RC")],
        qso_idle=True,
        presence_ok=True,
    )
    assert result is not None, "Cooldown muss mode-spezifisch sein"
    assert result.call == "HA8RC"


# ── T5 — Base-Call-Normalisierung (HA8RC/P matched HA8RC) ──────────────────

def test_t5_portable_suffix_match():
    """T5: mark_pick(HA8RC/P) muss HA8RC im naechsten select_next blocken."""
    h = _make_hunt()
    h.mark_pick("HA8RC/P")
    # Eintrag ist unter base "HA8RC"
    assert ("HA8RC", "20M", "FT8") in h._recent_qso
    # CQ von HA8RC (ohne Suffix) muss geblockt sein
    result = h.select_next(
        messages=[_msg("HA8RC")],
        qso_idle=True,
        presence_ok=True,
    )
    assert result is None, "Base-Call-Normalisierung muss greifen"


# ── T6 — Source-Level: _recent_qso existiert in core/auto_hunt.py ──────────

def test_t6_source_recent_qso_exists():
    """T6: Bug-Schutz — _recent_qso muss in auto_hunt.py existieren."""
    src = Path(__file__).parent.parent / "core" / "auto_hunt.py"
    text = src.read_text()
    assert "_recent_qso" in text, "P61 _recent_qso fehlt in core/auto_hunt.py"
    assert "_RECENT_QSO_COOLDOWN_S" in text, "P61 Konstante fehlt"
    assert "def mark_pick" in text, "P61 mark_pick-Methode fehlt"
    assert "def set_mode" in text, "P61 set_mode-Methode fehlt"


# ── T7 — Race-Schutz: mark_pick wirkt OHNE on_qso_complete ─────────────────

def test_t7_pick_ohne_qso_complete_blockt():
    """T7: mark_pick alleine muss reichen — kein on_qso_complete noetig.

    Schuetzt vor Race zwischen Decoder-cycle_decoded und
    Encoder-tx_finished — wenn select_next in der naechsten Decoder-
    Runde laeuft BEVOR on_qso_complete gerufen wurde, muss Cooldown
    trotzdem greifen.
    """
    h = _make_hunt()
    h.mark_pick("HA8RC")
    # KEIN on_qso_complete-Aufruf — simuliert Race
    # Direkt naechster select_next
    result = h.select_next(
        messages=[_msg("HA8RC")],
        qso_idle=True,
        presence_ok=True,
    )
    assert result is None, (
        "mark_pick allein muss reichen — on_qso_complete kommt erst spaeter"
    )


# ── T8 — Source-Level: Reihenfolge _recent_qso VOR _cooldown ───────────────

def test_t8_filter_reihenfolge_im_select_next():
    """T8: _recent_qso-Check muss VOR _cooldown-Check stehen.

    Grund: wir wollen lieber gar nicht anrufen statt nach Fehlschlag
    weiter zu versuchen. Bei umgekehrter Reihenfolge wuerde Fail-Cooldown
    weniger restriktiv wirken als Recent-QSO-Cooldown.
    """
    src_text = inspect.getsource(AutoHunt.select_next)
    # Index suchen
    idx_recent = src_text.find("_recent_qso")
    idx_cooldown = src_text.find("_cooldown.get")
    assert idx_recent > 0, "P61 _recent_qso fehlt in select_next"
    assert idx_cooldown > 0, "Fail-Cooldown _cooldown.get fehlt"
    assert idx_recent < idx_cooldown, (
        "P61 _recent_qso-Check MUSS vor _cooldown-Check stehen"
    )


# ── T9 — on_qso_complete ruft mark_pick (manuelle QSOs) ────────────────────

def test_t9_on_qso_complete_ruft_mark_pick():
    """T9: Manuelle QSOs (User-Klick statt Auto-Pick) muessen auch
    Cooldown setzen. on_qso_complete wird IMMER gerufen (auch fuer
    manuelle QSOs in mw_qso._on_qso_complete) — also muss dort der
    Cooldown gesetzt werden.
    """
    h = _make_hunt()
    # Simuliere abgeschlossenes QSO (kein vorheriger mark_pick — manuell)
    assert ("HA8RC", "20M", "FT8") not in h._recent_qso
    h.on_qso_complete("HA8RC")
    assert ("HA8RC", "20M", "FT8") in h._recent_qso, (
        "on_qso_complete MUSS Recent-Cooldown setzen (manuelle QSOs)"
    )
    # Verifikation: select_next wuerde nun blocken
    result = h.select_next(
        messages=[_msg("HA8RC")],
        qso_idle=True,
        presence_ok=True,
    )
    assert result is None


# ── T10 — Mode-Trennung im Detail ──────────────────────────────────────────

def test_t10_mode_trennung_im_key():
    """T10: Key (call, band, mode) — zwei Modi unabhaengig blockierbar.

    Hobby-Praxis: Mike macht 20m/FT8-QSO mit HA8RC, will gleich darauf
    auf 20m/FT4 wechseln und HA8RC dort auch picken duerfen.
    """
    h = _make_hunt(band="20m", mode="FT8")
    h.mark_pick("HA8RC")
    # 20m/FT8 ist im Cooldown
    assert ("HA8RC", "20M", "FT8") in h._recent_qso
    # Mode-Wechsel auf FT4
    h.set_mode("FT4")
    # Eintrag fuer FT4 ist NICHT im Cooldown
    assert ("HA8RC", "20M", "FT4") not in h._recent_qso
    # select_next im neuen Modus erlaubt Pick
    result = h.select_next(
        messages=[_msg("HA8RC")],
        qso_idle=True,
        presence_ok=True,
    )
    assert result is not None
    # FT4-Pick setzt jetzt FT4-Cooldown
    h.mark_pick("HA8RC")
    assert ("HA8RC", "20M", "FT4") in h._recent_qso
    # Beide Cooldowns aktiv
    assert ("HA8RC", "20M", "FT8") in h._recent_qso
    assert ("HA8RC", "20M", "FT4") in h._recent_qso
