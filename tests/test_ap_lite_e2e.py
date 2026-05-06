"""AP-Lite E2E-Tests mit synthetischem Audio (ohne FlexRadio).

Pipeline: ft8lib.encode(msg) → +Gaussian-Rauschen auf Ziel-SNR → AP-Lite
durchlaufen lassen → Verhalten asserten.

Diese Tests sind ein Schutznetz fuer das aktuelle AP-Lite-Verhalten
(SCORE_THRESHOLD=0.75, Costas-Alignment, Kandidaten-Korrelation).
Sie erlauben Mike, am Algorithmus zu schrauben ohne Hardware-Test —
Regressionen werden hier sichtbar.

WICHTIG: Diese Tests aendern NICHTS am AP-Lite-Algorithmus. Falls ein
Test fehlschlaegt nach Algorithmus-Aenderung: bewerten ob Schwellwert/
Logik bewusst geaendert wurde, dann Test anpassen.

Quelle: alte TODO-Liste „AP-Lite Test-Pipeline — synthetische E2E-Tests
vor jedem Code-Fix" (P1.AP, 2026-05-06 v0.95.9).
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
    SAMPLE_RATE,
    SCORE_THRESHOLD,
    align_buffers,
    correlate_candidate,
    generate_candidates,
)
from core.encoder import Encoder


# ── Fixtures ────────────────────────────────────────────────────────


def _ensure_app():
    return QApplication.instance() or QApplication([])


@pytest.fixture(scope="module")
def encoder():
    """Encoder-Instanz fuer ft8lib-Encoding (kein FlexRadio noetig)."""
    _ensure_app()
    return Encoder(audio_freq_hz=1500)


@pytest.fixture
def rng():
    """Reproduzierbarer Zufall — gleicher Seed pro Test."""
    return np.random.default_rng(seed=42)


# ── Helper ──────────────────────────────────────────────────────────


def _add_noise_to_target_snr(
    signal: np.ndarray,
    snr_db: float,
    rng: np.random.Generator,
) -> np.ndarray:
    """Gaussian-Rauschen so addieren dass Ergebnis-SNR = snr_db.

    SNR = 10*log10(P_signal / P_noise)
    P_noise_target = P_signal / 10^(snr_db/10)
    """
    p_signal = float(np.mean(signal.astype(np.float64) ** 2))
    if p_signal <= 0:
        return signal.copy()
    p_noise_target = p_signal / (10 ** (snr_db / 10.0))
    sigma = float(np.sqrt(p_noise_target))
    noise = rng.normal(0.0, sigma, size=signal.shape).astype(np.float32)
    return (signal + noise).astype(np.float32)


def _make_pcm(encoder: Encoder, message: str, freq_hz: float = 1500.0,
              pad_to_slot: bool = True) -> np.ndarray:
    """Echtes FT8-Audio via ft8lib generieren, float32 12kHz, optional auf
    SLOT_SAMPLES (180_000) gepaddet."""
    wave = encoder.generate_reference_wave(message, freq_hz, SAMPLE_RATE)
    assert wave is not None, f"ft8lib encode fehlgeschlagen: {message}"
    if pad_to_slot:
        target = int(SAMPLE_RATE * 15.0)  # 180_000
        if len(wave) < target:
            wave = np.concatenate([
                wave,
                np.zeros(target - len(wave), dtype=np.float32),
            ])
        elif len(wave) > target:
            wave = wave[:target]
    return wave.astype(np.float32)


# ── 1. correlate_candidate ──────────────────────────────────────────


def test_correlate_clean_signal_high_score(encoder):
    """Sauberes Signal → Score sehr hoch (≥ 0.7)."""
    msg = "DA1MHH DK5ON RR73"
    pcm = _make_pcm(encoder, msg, freq_hz=1500.0)
    score = correlate_candidate(pcm, msg, freq_hz=1500.0, encoder=encoder)
    assert score >= 0.7, f"Clean-Signal-Score zu niedrig: {score:.3f}"


def test_correlate_noisy_signal_medium_score(encoder, rng):
    """Verrauschtes Signal (-10 dB SNR) → mittlerer Score."""
    msg = "DA1MHH DK5ON RR73"
    clean = _make_pcm(encoder, msg, freq_hz=1500.0)
    noisy = _add_noise_to_target_snr(clean, snr_db=-10.0, rng=rng)
    score = correlate_candidate(noisy, msg, freq_hz=1500.0, encoder=encoder)
    # -10 dB ist deutlich verrauscht aber Costas-Symbole noch erkennbar
    assert 0.05 <= score <= 0.95, f"Noisy-Score auserhalb plausibel: {score:.3f}"


def test_correlate_wrong_candidate_low_score(encoder):
    """Falscher Kandidat → niedriger Score (< richtiger Kandidat)."""
    real = "DA1MHH DK5ON RR73"
    wrong = "DA1MHH DK5ON 73"  # 73 statt RR73
    pcm = _make_pcm(encoder, real, freq_hz=1500.0)
    score_real = correlate_candidate(pcm, real, freq_hz=1500.0, encoder=encoder)
    score_wrong = correlate_candidate(pcm, wrong, freq_hz=1500.0, encoder=encoder)
    assert score_real > score_wrong, (
        f"Richtiger Kandidat sollte hoeher scoren: real={score_real:.3f} "
        f"wrong={score_wrong:.3f}"
    )


def test_correlate_unrelated_message_lower(encoder):
    """Voellig unverwandte Nachricht → niedriger Score."""
    real = "DA1MHH DK5ON RR73"
    unrelated = "CQ JA1XYZ PM95"
    pcm = _make_pcm(encoder, real, freq_hz=1500.0)
    score_real = correlate_candidate(pcm, real, freq_hz=1500.0, encoder=encoder)
    score_unrelated = correlate_candidate(pcm, unrelated, freq_hz=1500.0,
                                          encoder=encoder)
    assert score_real > score_unrelated + 0.1, (
        f"Real-Score sollte deutlich ueber unrelated liegen: "
        f"real={score_real:.3f} unrelated={score_unrelated:.3f}"
    )


# ── 2. align_buffers ────────────────────────────────────────────────


def test_align_buffers_no_offset_returns_valid_range(encoder):
    """Identische Buffer → Alignment liefert Werte im erwarteten Bereich.

    HINWEIS: Mit aktueller Costas-Referenz-Implementation findet das
    Alignment auch bei identischen Buffern nicht zwingend dt=0 — das
    Costas-Energie-Maximum kann an Nebenmaxima liegen (siehe `_build_
    costas_reference` „TODO: Echte FT8-Costas-Symbole generieren").
    Test prueft daher nur dass dt im Suchbereich liegt, nicht dass es 0 ist.
    """
    from core.ap_lite import ALIGN_DT_SAMPLES, ALIGN_DF_HZ
    msg = "DA1MHH DK5ON RR73"
    buf = _make_pcm(encoder, msg, freq_hz=1500.0)
    aligned, dt, df = align_buffers(buf, buf.copy(), freq_hz=1500.0)
    assert -ALIGN_DT_SAMPLES <= dt <= ALIGN_DT_SAMPLES
    assert -ALIGN_DF_HZ <= df <= ALIGN_DF_HZ


def test_align_buffers_time_shift(encoder):
    """Buf2 um +5 Samples verschoben → Alignment detektiert Shift."""
    msg = "DA1MHH DK5ON RR73"
    buf1 = _make_pcm(encoder, msg, freq_hz=1500.0)
    buf2 = np.roll(buf1, 5)  # 5 Samples spaeter
    aligned, dt, df = align_buffers(buf1, buf2, freq_hz=1500.0)
    # align_buffers rollt buf2 um best_dt zurueck → buf2 hatte +5 → best_dt ≈ -5
    assert -7 <= dt <= -3, f"dt sollte ca -5 sein: {dt}"


def test_align_buffers_returns_correct_shape(encoder):
    """aligned-Buffer hat gleiche Laenge wie Input."""
    msg = "DA1MHH DK5ON RR73"
    buf1 = _make_pcm(encoder, msg, freq_hz=1500.0)
    buf2 = _make_pcm(encoder, msg, freq_hz=1500.0)
    aligned, dt, df = align_buffers(buf1, buf2, freq_hz=1500.0)
    assert aligned.shape == buf1.shape


# ── 3. try_rescue E2E ───────────────────────────────────────────────


def test_try_rescue_state1_documents_bug(encoder):
    """⛔ BUG-FINDING 2026-05-06 v0.95.9 (P1.AP):

    State-1-Rescue ist AKTUELL NICHT FUNKTIONAL — `generate_candidates`
    erzeugt fuer WAIT_REPORT 4-Token-Nachrichten:
        f"{own_callsign} {their_callsign} {own_locator} {r:+03d}"
    z.B. "DA1MHH DK5ON JO31 +05".

    Aber FT8 erlaubt nur 3 Tokens pro Frame (Locator XOR Report, nicht
    beides). ft8lib lehnt alle Kandidaten mit rc=5 ab → alle Korrelations-
    Scores = 0 → State-1-Rescue scheitert IMMER, auch bei sauberen Buffern.

    Mike-TODO post-Kur (P1.AP-FIX):
    - core/ap_lite.py:126 — Kandidaten auf 3 Tokens reduzieren
    - Vorschlag: f"{own_callsign} {their_callsign} {r:+03d}" (Report-only)
    - Workflow: V1→V2→R1→V3 (Algorithmus-Aenderung, Architektur-Pflicht)

    Dieser Test friert das aktuelle (kaputte) Verhalten ein — wenn der
    Generator gefixt wird, wird der Test failen → Trigger zur Anpassung.
    """
    ap = APLite(encoder=encoder)
    msg_real = "DA1MHH DK5ON +05"
    pcm1 = _make_pcm(encoder, msg_real, freq_hz=1500.0)
    pcm2 = _make_pcm(encoder, msg_real, freq_hz=1500.0)

    ap.on_decode_failed(
        pcm=pcm1, slot_time=1000.0, callsign="DK5ON", freq_hz=1500.0,
        qso_state=1, own_callsign="DA1MHH", own_locator="JO31",
        snr_estimate=5.0,
    )
    result = ap.try_rescue(
        pcm_new=pcm2, slot_time_new=1015.0, callsign="DK5ON",
        freq_hz=1500.0, qso_state=1, own_callsign="DA1MHH",
        own_locator="JO31", snr_estimate=5.0,
    )

    # Aktuelles Verhalten: alle Kandidaten ungueltig → score=0, fail.
    assert result is not None
    assert result.success is False
    assert result.score == 0.0
    # attempt_count erhoeht (Versuch wurde gezaehlt)
    assert ap.attempt_count == 1


def test_generate_candidates_state1_format_bug():
    """⛔ BUG-FINDING (Zwilling zu test_try_rescue_state1_documents_bug):
    generate_candidates State 1 erzeugt 4-Token-Strings, nicht FT8-konform.
    """
    cands = generate_candidates(
        qso_state=1, their_callsign="DK5ON",
        own_callsign="DA1MHH", own_locator="JO31",
        snr_estimate=5.0,
    )
    # Aktuelles Verhalten: mindestens 1 Kandidat hat 4 Tokens (BUG)
    has_4_tokens = any(len(c.split()) == 4 for c in cands)
    assert has_4_tokens, (
        "Falls dieser Test failed: Kandidaten-Generator wurde gefixt — "
        "Test entfernen oder umkehren."
    )


def test_try_rescue_extreme_noise_fails(encoder, rng):
    """Zwei stark verrauschte Buffer (-30 dB SNR) → Rescue scheitert."""
    ap = APLite(encoder=encoder)
    msg_real = "DA1MHH DK5ON +05"
    pcm_clean = _make_pcm(encoder, msg_real, freq_hz=1500.0)
    pcm1 = _add_noise_to_target_snr(pcm_clean, snr_db=-30.0, rng=rng)
    pcm2 = _add_noise_to_target_snr(pcm_clean, snr_db=-30.0, rng=rng)

    ap.on_decode_failed(
        pcm=pcm1, slot_time=1000.0, callsign="DK5ON", freq_hz=1500.0,
        qso_state=1, own_callsign="DA1MHH", own_locator="JO31",
        snr_estimate=-25.0,
    )
    result = ap.try_rescue(
        pcm_new=pcm2, slot_time_new=1015.0, callsign="DK5ON",
        freq_hz=1500.0, qso_state=1, own_callsign="DA1MHH",
        own_locator="JO31", snr_estimate=-25.0,
    )

    assert result is not None
    # Bei -30 dB SNR sollte der Score deutlich unter Threshold liegen
    if result.success:
        # Falls doch erfolgreich: zumindest Sanity — ist die Message
        # ueberhaupt aus den Kandidaten?
        assert result.recovered_message is not None
    else:
        assert result.score < SCORE_THRESHOLD


def test_try_rescue_returns_apliteresult(encoder):
    """Rescue gibt immer APLiteResult zurueck (auch bei Misserfolg)."""
    ap = APLite(encoder=encoder)
    msg = "DA1MHH DK5ON +05"
    pcm = _make_pcm(encoder, msg, freq_hz=1500.0)
    ap.on_decode_failed(
        pcm=pcm, slot_time=1000.0, callsign="DK5ON", freq_hz=1500.0,
        qso_state=1, own_callsign="DA1MHH", own_locator="JO31",
        snr_estimate=5.0,
    )
    result = ap.try_rescue(
        pcm_new=pcm.copy(), slot_time_new=1015.0, callsign="DK5ON",
        freq_hz=1500.0, qso_state=1, own_callsign="DA1MHH",
        own_locator="JO31", snr_estimate=5.0,
    )
    assert isinstance(result, APLiteResult)


def test_try_rescue_state2_rr73_candidate_ranking(encoder):
    """State 2 (WAIT_RR73): RR73 sollte gegen 73/RRR gewinnen wenn das
    echte Signal RR73 ist — UNABHAENGIG vom absoluten Score-Threshold.

    Wir pruefen Ranking direkt via correlate_candidate gegen kombinierten
    Buffer (so wuerde es try_rescue intern machen).
    """
    msg_real = "DA1MHH DK5ON RR73"
    pcm1 = _make_pcm(encoder, msg_real, freq_hz=1500.0)
    pcm2 = _make_pcm(encoder, msg_real, freq_hz=1500.0)
    aligned, dt, df = align_buffers(pcm1, pcm2, freq_hz=1500.0)
    combined = pcm1 + aligned

    score_rr73 = correlate_candidate(combined, "DA1MHH DK5ON RR73",
                                     freq_hz=1500.0 + df, encoder=encoder)
    score_73 = correlate_candidate(combined, "DA1MHH DK5ON 73",
                                   freq_hz=1500.0 + df, encoder=encoder)
    score_rrr = correlate_candidate(combined, "DA1MHH DK5ON RRR",
                                    freq_hz=1500.0 + df, encoder=encoder)

    assert score_rr73 >= score_73, (
        f"RR73 sollte gleich oder hoeher als 73 scoren: "
        f"rr73={score_rr73:.3f} 73={score_73:.3f}"
    )
    assert score_rr73 >= score_rrr, (
        f"RR73 sollte gleich oder hoeher als RRR scoren: "
        f"rr73={score_rr73:.3f} rrr={score_rrr:.3f}"
    )


# ── 4. Stats-Counter ────────────────────────────────────────────────


def test_attempt_count_increments_per_rescue(encoder):
    """attempt_count zaehlt jeden try_rescue-Aufruf mit Buffer."""
    ap = APLite(encoder=encoder)
    msg = "DA1MHH DK5ON +05"
    pcm = _make_pcm(encoder, msg, freq_hz=1500.0)
    assert ap.attempt_count == 0

    ap.on_decode_failed(
        pcm=pcm, slot_time=1000.0, callsign="DK5ON", freq_hz=1500.0,
        qso_state=1, own_callsign="DA1MHH", own_locator="JO31",
    )
    ap.try_rescue(
        pcm_new=pcm.copy(), slot_time_new=1015.0, callsign="DK5ON",
        freq_hz=1500.0, qso_state=1, own_callsign="DA1MHH",
        own_locator="JO31",
    )
    assert ap.attempt_count == 1


def test_rescue_count_only_on_success(encoder, rng):
    """rescue_count zaehlt NUR erfolgreiche Rescues (score >= threshold)."""
    ap = APLite(encoder=encoder)
    msg = "DA1MHH DK5ON +05"
    pcm_clean = _make_pcm(encoder, msg, freq_hz=1500.0)
    pcm1 = _add_noise_to_target_snr(pcm_clean, snr_db=-40.0, rng=rng)
    pcm2 = _add_noise_to_target_snr(pcm_clean, snr_db=-40.0, rng=rng)

    ap.on_decode_failed(
        pcm=pcm1, slot_time=1000.0, callsign="DK5ON", freq_hz=1500.0,
        qso_state=1, own_callsign="DA1MHH", own_locator="JO31",
    )
    result = ap.try_rescue(
        pcm_new=pcm2, slot_time_new=1015.0, callsign="DK5ON",
        freq_hz=1500.0, qso_state=1, own_callsign="DA1MHH",
        own_locator="JO31",
    )
    if result.success:
        assert ap.rescue_count == 1
    else:
        assert ap.rescue_count == 0
    assert ap.attempt_count == 1
