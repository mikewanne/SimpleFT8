"""Unit-Tests für core/ap_lite.py — AP-Lite A-Priori-Kandidaten-Matching.

Deckt ab (ohne DSP/Encoder — pure Logik):
- generate_candidates() für alle QSO-States
- correlate_candidate() Guards (kein Encoder, leerer Buffer)
- APLite.try_rescue() Guards (aus, leeres Call, ungültiger State, kein PCM)
- persistenter Rescue-Zähler (laden/speichern, stats_path=None)
- get_instance() Singleton

Algorithmus-Verhalten mit echtem FT8-Audio → test_ap_lite_e2e.py.

Historie: AP-Lite v0.97.90 (Option D) ersetzte die „kohärente Addition"
durch reines A-Priori-Matching auf EINEM Slot. Tests für align_buffers /
FailedDecodeBuffer / SCORE_THRESHOLD entfielen mit dem Mechanismus.
"""

import json
import re

import numpy as np
import pytest

from core.ap_lite import (
    APLite,
    APLiteResult,
    MARGIN_MIN,
    correlate_candidate,
    generate_candidates,
    get_instance,
)


# ── generate_candidates() ────────────────────────────────────────────────────

def test_generate_state1_candidate_count():
    """State 1 (WAIT_REPORT): 11 Report-Kandidaten (±5 dB, jede dB-Stufe)."""
    cands = generate_candidates(1, "DK5ON", "DA1MHH", "JO31", snr_estimate=-10.0)
    assert len(cands) == 11


def test_generate_state1_three_token_format():
    """State 1: alle Kandidaten FT8-konform 3-Token OWN THEIR +-NN."""
    cands = generate_candidates(1, "DK5ON", "DA1MHH", "JO31", snr_estimate=-10.0)
    report_re = re.compile(r"^[+-]\d{2}$")
    for c in cands:
        tok = c.split()
        assert len(tok) == 3, f"3 Tokens erwartet: '{c}'"
        assert tok[0] == "DA1MHH"
        assert tok[1] == "DK5ON"
        assert report_re.match(tok[2]), f"Ungültiger Report '{tok[2]}'"


def test_generate_state1_snr_clamping():
    """State 1: Report-Werte bleiben in -30..+29 (FT8-Bereich)."""
    cands = generate_candidates(1, "DK5ON", "DA1MHH", "JO31", snr_estimate=-28.0)
    for c in cands:
        val = int(c.split()[-1])
        assert -30 <= val <= 29


def test_generate_state2_rr73_variants():
    """State 2 (WAIT_RR73): genau RR73, 73, RRR."""
    cands = generate_candidates(2, "DK5ON", "DA1MHH", "JO31")
    assert len(cands) == 3
    raw = " ".join(cands)
    assert "RR73" in raw and "RRR" in raw
    assert any(c.split()[-1] == "73" for c in cands)


def test_generate_state2_callsigns():
    """State 2: jeder Kandidat enthält beide Rufzeichen."""
    for c in generate_candidates(2, "DK5ON", "DA1MHH", "JO31"):
        assert "DA1MHH" in c and "DK5ON" in c


def test_generate_state3_empty():
    """State 3 (CQ_WAIT): keine Kandidaten (Locator unbekannt)."""
    assert generate_candidates(3, "DK5ON", "DA1MHH", "JO31") == []


def test_generate_unknown_state_empty():
    """Unbekannter State → leere Liste, kein Crash."""
    assert generate_candidates(99, "DK5ON", "DA1MHH", "JO31") == []


# ── correlate_candidate() Guards ─────────────────────────────────────────────

def test_correlate_without_encoder_zero():
    """Ohne Encoder → 0.0."""
    buf = np.zeros(1000, dtype=np.float32)
    assert correlate_candidate(buf, "DA1MHH DK5ON RR73", 1500.0, encoder=None) == 0.0


def test_correlate_empty_buffer_zero():
    """Leerer Buffer → 0.0 (kein Crash)."""
    buf = np.zeros(0, dtype=np.float32)
    assert correlate_candidate(buf, "DA1MHH DK5ON RR73", 1500.0, encoder=None) == 0.0


# ── APLite.try_rescue() Guards ───────────────────────────────────────────────

def _pcm():
    return np.zeros(180000, dtype=np.float32)


def test_try_rescue_disabled_returns_none():
    """enabled=False → None."""
    ap = APLite(stats_path=None)
    ap.enabled = False
    assert ap.try_rescue(_pcm(), 1500.0, "DK5ON", 2) is None


def test_try_rescue_empty_callsign_returns_none():
    """Leeres Rufzeichen → None."""
    ap = APLite(stats_path=None)
    assert ap.try_rescue(_pcm(), 1500.0, "", 2) is None


def test_try_rescue_invalid_state_returns_none():
    """State außerhalb 1/2/3 → None."""
    ap = APLite(stats_path=None)
    assert ap.try_rescue(_pcm(), 1500.0, "DK5ON", 99) is None


def test_try_rescue_state3_returns_none():
    """State 3 erzeugt keine Kandidaten → None."""
    ap = APLite(stats_path=None)
    assert ap.try_rescue(_pcm(), 1500.0, "DK5ON", 3, "DA1MHH", "JO31") is None


def test_try_rescue_none_pcm_returns_none():
    """pcm=None → None (kein Crash)."""
    ap = APLite(stats_path=None)
    assert ap.try_rescue(None, 1500.0, "DK5ON", 2) is None


def test_try_rescue_empty_pcm_returns_none():
    """Leerer pcm → None."""
    ap = APLite(stats_path=None)
    assert ap.try_rescue(np.zeros(0, dtype=np.float32), 1500.0, "DK5ON", 2) is None


# ── Persistenter Rescue-Zähler ───────────────────────────────────────────────

def test_rescue_count_starts_zero_without_file(tmp_path):
    """Ohne vorhandene Stats-Datei → Zähler 0."""
    ap = APLite(stats_path=str(tmp_path / "fehlt.json"))
    assert ap.rescue_count == 0


def test_rescue_count_persists_round_trip(tmp_path):
    """rescue_count wird gespeichert und von neuer Instanz geladen."""
    path = str(tmp_path / "stats.json")
    ap = APLite(stats_path=path)
    ap.rescue_count = 7
    ap._save_rescue_count()
    ap2 = APLite(stats_path=path)
    assert ap2.rescue_count == 7


def test_rescue_count_saved_file_is_json(tmp_path):
    """Gespeicherte Datei ist valides JSON mit rescue_count."""
    path = tmp_path / "stats.json"
    ap = APLite(stats_path=str(path))
    ap.rescue_count = 3
    ap._save_rescue_count()
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["rescue_count"] == 3


def test_no_persistence_when_path_none():
    """stats_path=None → keine Persistenz, kein Crash beim Speichern."""
    ap = APLite(stats_path=None)
    assert ap.rescue_count == 0
    ap.rescue_count = 5
    ap._save_rescue_count()  # no-op
    assert APLite(stats_path=None).rescue_count == 0


def test_corrupt_stats_file_loads_zero(tmp_path):
    """Defekte Stats-Datei → Zähler 0 statt Crash."""
    path = tmp_path / "kaputt.json"
    path.write_text("kein json {{{", encoding="utf-8")
    assert APLite(stats_path=str(path)).rescue_count == 0


# ── get_instance() Singleton ─────────────────────────────────────────────────

def test_get_instance_singleton():
    """get_instance() liefert immer dasselbe Objekt."""
    from core import ap_lite
    ap_lite._instance = None
    assert get_instance() is get_instance()


def test_get_instance_is_aplite():
    """get_instance() liefert ein APLite-Objekt."""
    from core import ap_lite
    ap_lite._instance = None
    assert isinstance(get_instance(), APLite)


# ── APLiteResult ─────────────────────────────────────────────────────────────

def test_apliteresult_fields():
    """APLiteResult hält success/score/margin/recovered_message."""
    r = APLiteResult(success=True, score=0.3, margin=0.1,
                     recovered_message="DA1MHH DK5ON RR73")
    assert r.success and r.score == 0.3 and r.margin == 0.1
    assert r.recovered_message == "DA1MHH DK5ON RR73"


def test_margin_min_sane():
    """MARGIN_MIN liegt im sinnvollen Bereich (gemessen: Rausch-Ceiling
    ~0.02, Echtsignal-Marge ~0.1)."""
    assert 0.02 < MARGIN_MIN < 0.1
