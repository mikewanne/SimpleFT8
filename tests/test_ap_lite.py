"""Tests fuer core/ap_lite.py — AP-Lite Kandidaten-Generierung + Buffer-Management.

Prueft (OHNE Encoder/DSP-Abhängigkeiten — Unit-Tests fuer pure Logik):
- generate_candidates() fuer alle QSO-States (1/2/3)
- SNR-Clamping (-30..+29 dB)
- on_decode_failed() Buffer-Speicherung und Cache-Limit
- on_decode_failed() ignoriert leere Callsigns + ungültige States
- try_rescue() Guard: kein Buffer → None
- try_rescue() Guard: Frequenz-Abweichung > 30 Hz → None
- try_rescue() Guard: Slot-Timing ausserhalb 10-20s → None
- try_rescue() State-3 → APLiteResult(success=False) wegen leere Kandidaten
- correlate_candidate() ohne Encoder → 0.0
- APLite.clear() loescht alle Buffers
- get_instance() Singleton-Semantik
"""

import time
import numpy as np
import pytest

from core.ap_lite import (
    APLite,
    APLiteResult,
    FailedDecodeBuffer,
    generate_candidates,
    correlate_candidate,
    get_instance,
    SCORE_THRESHOLD,
)


# ── generate_candidates() ─────────────────────────────────────────────────────

def test_generate_state1_basic():
    """State 1 (WAIT_REPORT): 3-Token-Kandidaten mit Report (FT8-konform).

    Nach P1.AP-FIX (v0.95.10): Locator NICHT mehr im Kandidat —
    FT8 erlaubt nur 3 Tokens pro Frame.
    """
    import re
    cands = generate_candidates(
        qso_state=1,
        their_callsign="DK5ON",
        own_callsign="DA1MHH",
        own_locator="JO31",
        snr_estimate=-10.0,
    )
    assert len(cands) > 0, "State 1 muss Kandidaten liefern"
    # Alle Kandidaten 3-Token-Format: OWN_CALL THEIR_CALL [+-]NN
    report_pattern = re.compile(r'^[+-]\d{2}$')
    for c in cands:
        tokens = c.split()
        assert len(tokens) == 3, f"3 Tokens erwartet, habe {len(tokens)}: '{c}'"
        assert tokens[0] == "DA1MHH"
        assert tokens[1] == "DK5ON"
        assert report_pattern.match(tokens[2]), f"Ungueltiger Report '{tokens[2]}'"
        val = int(tokens[2])
        assert -30 <= val <= 29, f"Report {val} ausserhalb -30..+29"


def test_generate_state1_snr_range():
    """State 1: SNR-Fenster deckt ±5 dB ab (6 Werte im 2er-Schritt)."""
    cands = generate_candidates(1, "DK5ON", "DA1MHH", "JO31", snr_estimate=-10.0)
    # range(-5, 6, 2) = 6 Werte: -5, -3, -1, +1, +3, +5
    assert len(cands) == 6


def test_generate_state1_snr_clamping():
    """SNR-Werte werden auf -30..+29 geclamppt."""
    # snr_estimate=-28 → clamped range enthält keine Werte unter -30
    cands = generate_candidates(1, "DK5ON", "DA1MHH", "JO31", snr_estimate=-28.0)
    for c in cands:
        # Finde den SNR-Teil (letztes Wort)
        snr_str = c.split()[-1]
        val = int(snr_str)
        assert -30 <= val <= 29, f"SNR {val} ausserhalb -30..+29"


def test_generate_state2_rr73():
    """State 2 (WAIT_RR73): RR73, 73, RRR werden generiert."""
    cands = generate_candidates(2, "DK5ON", "DA1MHH", "JO31")
    raw = " ".join(cands)
    assert "RR73" in raw
    assert " 73" in raw or raw.endswith("73")
    assert "RRR" in raw
    assert len(cands) == 3


def test_generate_state2_callsigns():
    """State 2: Alle Kandidaten enthalten beide Rufzeichen."""
    cands = generate_candidates(2, "DK5ON", "DA1MHH", "JO31")
    for c in cands:
        assert "DA1MHH" in c
        assert "DK5ON" in c


def test_generate_state3_empty():
    """State 3 (CQ_WAIT): Zu viele Unbekannte → leere Liste."""
    cands = generate_candidates(3, "DK5ON", "DA1MHH", "JO31")
    assert cands == [], "State 3 liefert keine Kandidaten (Locator unbekannt)"


def test_generate_unknown_state():
    """Unbekannter State → leere Liste (kein Crash)."""
    cands = generate_candidates(99, "DK5ON", "DA1MHH", "JO31")
    assert cands == []


# ── correlate_candidate() — kein Encoder ─────────────────────────────────────

def test_correlate_without_encoder():
    """correlate_candidate() ohne Encoder gibt 0.0 zurueck."""
    buf = np.zeros(1000, dtype=np.float32)
    score = correlate_candidate(buf, "DA1MHH DK5ON RR73", freq_hz=1500.0, encoder=None)
    assert score == 0.0


# ── APLite.on_decode_failed() ─────────────────────────────────────────────────

def _pcm():
    return np.zeros(180000, dtype=np.float32)


def test_on_decode_failed_stores_buffer():
    """Gueltiger Aufruf → Buffer gespeichert."""
    ap = APLite()
    ap.on_decode_failed(_pcm(), time.time(), "DK5ON", 1500.0, 1, "DA1MHH", "JO31")
    assert ("DK5ON", 1) in ap._buffers


def test_on_decode_failed_empty_callsign_ignored():
    """Leeres Rufzeichen → kein Buffer."""
    ap = APLite()
    ap.on_decode_failed(_pcm(), time.time(), "", 1500.0, 1, "DA1MHH", "JO31")
    assert len(ap._buffers) == 0


def test_on_decode_failed_none_callsign_ignored():
    """None als Rufzeichen → kein Buffer."""
    ap = APLite()
    ap.on_decode_failed(_pcm(), time.time(), None, 1500.0, 1, "DA1MHH", "JO31")
    assert len(ap._buffers) == 0


def test_on_decode_failed_invalid_state_ignored():
    """State ausserhalb 1/2/3 → kein Buffer."""
    ap = APLite()
    ap.on_decode_failed(_pcm(), time.time(), "DK5ON", 1500.0, 99, "DA1MHH", "JO31")
    assert len(ap._buffers) == 0


def test_on_decode_failed_cache_limit():
    """Mehr als _max_buffers (3) Eintraege → aeltester wird verdraengt."""
    ap = APLite()
    t = time.time()
    ap.on_decode_failed(_pcm(), t, "DK1", 1500.0, 1)
    ap.on_decode_failed(_pcm(), t, "DK2", 1500.0, 1)
    ap.on_decode_failed(_pcm(), t, "DK3", 1500.0, 1)
    ap.on_decode_failed(_pcm(), t, "DK4", 1500.0, 1)
    assert len(ap._buffers) == ap._max_buffers
    assert ("DK1", 1) not in ap._buffers, "Aeltester Buffer muss verdraengt worden sein"
    assert ("DK4", 1) in ap._buffers


def test_on_decode_failed_disabled():
    """enabled=False → kein Buffer."""
    ap = APLite()
    ap.enabled = False
    ap.on_decode_failed(_pcm(), time.time(), "DK5ON", 1500.0, 1, "DA1MHH", "JO31")
    assert len(ap._buffers) == 0


# ── APLite.try_rescue() Guard-Conditions ─────────────────────────────────────

def test_try_rescue_no_buffer_returns_none():
    """Kein vorheriger Buffer → try_rescue gibt None zurueck."""
    ap = APLite()
    result = ap.try_rescue(_pcm(), time.time(), "DK5ON", 1500.0, 1)
    assert result is None


def test_try_rescue_freq_deviation_too_large():
    """Frequenz-Abweichung > 30 Hz → None."""
    ap = APLite()
    t = time.time()
    ap.on_decode_failed(_pcm(), t, "DK5ON", 1500.0, 1, "DA1MHH", "JO31")
    result = ap.try_rescue(_pcm(), t + 15.0, "DK5ON", 1500.0 + 35.0, 1)
    assert result is None


def test_try_rescue_slot_timing_too_short():
    """Slot-Abstand < 10s → None."""
    ap = APLite()
    t = time.time()
    ap.on_decode_failed(_pcm(), t, "DK5ON", 1500.0, 1, "DA1MHH", "JO31")
    result = ap.try_rescue(_pcm(), t + 5.0, "DK5ON", 1500.0, 1)
    assert result is None


def test_try_rescue_slot_timing_too_long():
    """Slot-Abstand > 20s → None."""
    ap = APLite()
    t = time.time()
    ap.on_decode_failed(_pcm(), t, "DK5ON", 1500.0, 1, "DA1MHH", "JO31")
    result = ap.try_rescue(_pcm(), t + 25.0, "DK5ON", 1500.0, 1)
    assert result is None


def test_try_rescue_state3_no_candidates():
    """State 3 generiert keine Kandidaten → APLiteResult(success=False)."""
    ap = APLite()
    t = time.time()
    ap.on_decode_failed(_pcm(), t, "DK5ON", 1500.0, 3, "DA1MHH", "JO31")
    result = ap.try_rescue(_pcm(), t + 15.0, "DK5ON", 1500.0, 3, "DA1MHH", "JO31")
    assert result is not None
    assert result.success is False


def test_try_rescue_disabled():
    """enabled=False → None ohne Buffer-Zugriff."""
    ap = APLite()
    ap.enabled = False
    result = ap.try_rescue(_pcm(), time.time() + 15.0, "DK5ON", 1500.0, 1)
    assert result is None


def test_try_rescue_removes_buffer_after_attempt():
    """Nach try_rescue (State 3) ist Buffer bereinigt."""
    ap = APLite()
    t = time.time()
    ap.on_decode_failed(_pcm(), t, "DK5ON", 1500.0, 3, "DA1MHH", "JO31")
    ap.try_rescue(_pcm(), t + 15.0, "DK5ON", 1500.0, 3, "DA1MHH", "JO31")
    assert ("DK5ON", 3) not in ap._buffers, "Buffer muss nach Rescue-Versuch geloescht sein"


# ── APLite.clear() ────────────────────────────────────────────────────────────

def test_clear_empties_buffers():
    """clear() entfernt alle gespeicherten Buffers."""
    ap = APLite()
    t = time.time()
    ap.on_decode_failed(_pcm(), t, "DK1", 1500.0, 1)
    ap.on_decode_failed(_pcm(), t, "DK2", 1500.0, 2)
    ap.clear()
    assert len(ap._buffers) == 0


# ── get_instance() Singleton ──────────────────────────────────────────────────

def test_get_instance_returns_same_object():
    """get_instance() gibt dasselbe Objekt zurueck (Singleton)."""
    from core import ap_lite
    ap_lite._instance = None  # Reset fuer sauberen Test
    inst1 = get_instance()
    inst2 = get_instance()
    assert inst1 is inst2


def test_get_instance_is_aplite():
    """get_instance() liefert ein APLite-Objekt."""
    from core import ap_lite
    ap_lite._instance = None
    inst = get_instance()
    assert isinstance(inst, APLite)
