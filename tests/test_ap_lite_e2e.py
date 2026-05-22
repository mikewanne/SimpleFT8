"""E2E-Tests für AP-Lite (Option D) mit synthetischem FT8-Audio.

Pipeline: ft8lib.encode(msg) → optional Phasen-Drehung / Frequenz-Versatz /
Gaussian-Rauschen → AP-Lite-Korrelation bzw. try_rescue → Verhalten asserten.

Kein FlexRadio nötig. Diese Tests decken den KRITISCHEN Pfad ab, den die
alte Pipeline verfehlte: Trägerphasen-Drehung und Frequenz-Offset. Eine
phasen-gleiche Test-Pipeline (wie vor v0.97.90) würde die phasen-invariante
Korrelation nie wirklich prüfen.
"""
from __future__ import annotations

import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np
import pytest
from PySide6.QtWidgets import QApplication

from core.ap_lite import (
    APLite,
    APLiteResult,
    MARGIN_MIN,
    SAMPLE_RATE,
    correlate_candidate,
)
from core.encoder import Encoder


# ── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def encoder():
    QApplication.instance() or QApplication([])
    return Encoder(audio_freq_hz=1500)


@pytest.fixture
def rng():
    return np.random.default_rng(seed=42)


# ── Helper ───────────────────────────────────────────────────────────────────

def _pcm(encoder: Encoder, message: str, freq_hz: float = 1500.0) -> np.ndarray:
    """Echtes FT8-Audio via ft8lib, float32 12 kHz."""
    wave = encoder.generate_reference_wave(message, freq_hz, SAMPLE_RATE)
    assert wave is not None, f"ft8lib-Encode fehlgeschlagen: {message}"
    return np.asarray(wave, dtype=np.float32)


def _add_noise(sig: np.ndarray, snr_db: float, rng: np.random.Generator) -> np.ndarray:
    """Gaussian-Rauschen auf Ziel-SNR addieren."""
    s = np.asarray(sig, dtype=np.float64)
    p = float(np.mean(s ** 2))
    if p <= 0:
        return np.asarray(sig, dtype=np.float32)
    sigma = float(np.sqrt(p / (10 ** (snr_db / 10.0))))
    return (s + rng.normal(0.0, sigma, size=s.shape)).astype(np.float32)


def _rotate_phase(sig: np.ndarray, phi_deg: float) -> np.ndarray:
    """Trägerphase eines reellen Signals drehen (via analytisches Signal)."""
    x = np.asarray(sig, dtype=np.float64)
    n = len(x)
    X = np.fft.fft(x)
    h = np.zeros(n)
    h[0] = 1.0
    if n % 2 == 0:
        h[n // 2] = 1.0
        h[1:n // 2] = 2.0
    else:
        h[1:(n + 1) // 2] = 2.0
    analytic = np.fft.ifft(X * h)
    return np.real(analytic * np.exp(1j * np.deg2rad(phi_deg))).astype(np.float32)


# ── 1. correlate_candidate — Grundverhalten ──────────────────────────────────

def test_correlate_clean_signal_high(encoder):
    """Sauberes Signal → Score nahe 1.0."""
    msg = "DA1MHH DK5ON RR73"
    score = correlate_candidate(_pcm(encoder, msg), msg, 1500.0, encoder)
    assert score >= 0.9, f"Clean-Score zu niedrig: {score:.3f}"


def test_correlate_phase_invariant(encoder):
    """KRITISCH: Trägerphase gedreht → Score bleibt hoch (nicht-kohärent)."""
    msg = "DA1MHH DK5ON RR73"
    clean = _pcm(encoder, msg)
    for phi in (0, 45, 90, 135, 180):
        rotated = _rotate_phase(clean, phi)
        score = correlate_candidate(rotated, msg, 1500.0, encoder)
        assert score >= 0.9, f"Phasen-Drehung {phi}° brach Score ein: {score:.3f}"


def test_correlate_freq_offset_found(encoder):
    """Signal ±Hz neben Sollfrequenz → Frequenz-Scan findet es."""
    msg = "DA1MHH DK5ON RR73"
    for offset in (-5.0, -2.0, 3.0, 5.0):
        sig = _pcm(encoder, msg, freq_hz=1500.0 + offset)
        score = correlate_candidate(sig, msg, 1500.0, encoder)
        assert score >= 0.9, f"Offset {offset:+} Hz nicht gefunden: {score:.3f}"


def test_correlate_wrong_candidate_lower(encoder):
    """Falscher Kandidat scort niedriger als der richtige."""
    real = "DA1MHH DK5ON RR73"
    pcm = _pcm(encoder, real)
    s_real = correlate_candidate(pcm, real, 1500.0, encoder)
    s_wrong = correlate_candidate(pcm, "DA1MHH DK5ON 73", 1500.0, encoder)
    assert s_real > s_wrong


def test_correlate_unrelated_message_lower(encoder):
    """Völlig fremde Nachricht scort deutlich niedriger."""
    real = "DA1MHH DK5ON RR73"
    pcm = _pcm(encoder, real)
    s_real = correlate_candidate(pcm, real, 1500.0, encoder)
    s_unrel = correlate_candidate(pcm, "CQ JA1XYZ PM95", 1500.0, encoder)
    assert s_real > s_unrel + 0.1


# ── 2. try_rescue E2E ────────────────────────────────────────────────────────

def test_try_rescue_real_signal_success(encoder, rng):
    """Echtes RR73 bei moderatem SNR → Treffer mit korrekter Nachricht."""
    ap = APLite(encoder=encoder, stats_path=None)
    real = "DA1MHH DK5ON RR73"
    pcm = _add_noise(_pcm(encoder, real), -6.0, rng)
    res = ap.try_rescue(pcm, 1500.0, "DK5ON", 2, "DA1MHH", "JO31")
    assert res is not None and res.success
    assert res.recovered_message == real
    assert res.margin >= MARGIN_MIN


def test_try_rescue_phase_rotated_still_success(encoder, rng):
    """KRITISCH E2E: phasen-gedrehtes echtes Signal → trotzdem Treffer."""
    ap = APLite(encoder=encoder, stats_path=None)
    real = "DA1MHH DK5ON RR73"
    pcm = _add_noise(_rotate_phase(_pcm(encoder, real), 90.0), -6.0, rng)
    res = ap.try_rescue(pcm, 1500.0, "DK5ON", 2, "DA1MHH", "JO31")
    assert res is not None and res.success
    assert res.recovered_message == real


def test_try_rescue_pure_noise_fails(encoder, rng):
    """Reines Rauschen → kein Treffer (Marge unter Schwelle)."""
    ap = APLite(encoder=encoder, stats_path=None)
    noise = rng.normal(0.0, 1.0, SAMPLE_RATE * 13).astype(np.float32)
    res = ap.try_rescue(noise, 1500.0, "DK5ON", 2, "DA1MHH", "JO31")
    assert res is not None and not res.success
    assert res.margin < MARGIN_MIN


def test_try_rescue_picks_correct_rr73_variant(encoder, rng):
    """State 2: echtes RR73 → recovered_message ist RR73, nicht 73/RRR."""
    ap = APLite(encoder=encoder, stats_path=None)
    pcm = _add_noise(_pcm(encoder, "DA1MHH DK5ON RR73"), -6.0, rng)
    res = ap.try_rescue(pcm, 1500.0, "DK5ON", 2, "DA1MHH", "JO31")
    assert res.success and res.recovered_message.endswith("RR73")


def test_try_rescue_returns_apliteresult(encoder, rng):
    """try_rescue gibt bei gültigem Slot immer ein APLiteResult zurück."""
    ap = APLite(encoder=encoder, stats_path=None)
    pcm = _add_noise(_pcm(encoder, "DA1MHH DK5ON RR73"), -20.0, rng)
    res = ap.try_rescue(pcm, 1500.0, "DK5ON", 2, "DA1MHH", "JO31")
    assert isinstance(res, APLiteResult)


def test_attempt_count_increments(encoder, rng):
    """attempt_count zählt jeden Versuch mit gültigem Slot."""
    ap = APLite(encoder=encoder, stats_path=None)
    assert ap.attempt_count == 0
    ap.try_rescue(_add_noise(_pcm(encoder, "DA1MHH DK5ON RR73"), -6.0, rng),
                  1500.0, "DK5ON", 2, "DA1MHH", "JO31")
    assert ap.attempt_count == 1


def test_rescue_count_increments_on_success(encoder, rng):
    """rescue_count zählt nur erfolgreiche Treffer."""
    ap = APLite(encoder=encoder, stats_path=None)
    ap.try_rescue(_add_noise(_pcm(encoder, "DA1MHH DK5ON RR73"), -6.0, rng),
                  1500.0, "DK5ON", 2, "DA1MHH", "JO31")
    assert ap.rescue_count == 1


def test_rescue_count_persists_on_success(encoder, rng, tmp_path):
    """Erfolgreicher Treffer → Zähler wird auf Platte gespeichert."""
    path = str(tmp_path / "ap_stats.json")
    ap = APLite(encoder=encoder, stats_path=path)
    ap.try_rescue(_add_noise(_pcm(encoder, "DA1MHH DK5ON RR73"), -6.0, rng),
                  1500.0, "DK5ON", 2, "DA1MHH", "JO31")
    assert ap.rescue_count == 1
    # neue Instanz lädt den persistierten Wert
    assert APLite(encoder=encoder, stats_path=path).rescue_count == 1


def test_try_rescue_state1_report(encoder, rng):
    """State 1 (WAIT_REPORT): echter Report wird erkannt."""
    ap = APLite(encoder=encoder, stats_path=None)
    real = "DA1MHH DK5ON -09"
    pcm = _add_noise(_pcm(encoder, real), -6.0, rng)
    res = ap.try_rescue(pcm, 1500.0, "DK5ON", 1, "DA1MHH", "JO31",
                        snr_estimate=-9.0)
    assert res is not None and res.success
    assert res.recovered_message == real
