"""AP-Lite v2.2 — Schwaches QSO retten via kohärenter Addition wiederholter Slots.

Strategie:
  Decode schlägt fehl, aber Gegenstation wiederholt auf gleicher Frequenz.
  Zwei unabhängige Rausch-Samples derselben Nachricht kohärent addieren
  → ~4-5 dB SNR-Gewinn via Costas-basiertem Alignment.

Ablauf:
  1. Decode-Fail → PCM-Buffer speichern (on_decode_failed)
  2. Nächster Slot: gleiche Frequenz, gleicher State → AP-Lite triggert
  3. Costas-Alignment: ±8 Samples Zeit + ±1.5 Hz Freq
  4. Kohärente Addition → gewichtete Korrelation mit Kandidaten
  5. Score ≥ 0.75 → annehmen und senden
  6. Gegenstation antwortet → loggen. Sonst → tot.

TODO: KOMPLETT UNGETESTET — scharfschalten nur nach Feldtest!
      Insbesondere validieren:
      - Korrelations-Threshold 0.75 korrekt?
      - Costas-Alignment Suchbereich ausreichend?
      - Kandidaten-Generierung vollständig?
      - Buffer-Länge/Timing bei verschiedenen Slot-Typen?
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Tuple

import numpy as np

# ─────────────────────────────────────────────────────────────────────────────
# FEATURE FLAG — auf True setzen erst wenn Feldtest abgeschlossen!
AP_LITE_ENABLED: bool = False
# ─────────────────────────────────────────────────────────────────────────────

# FT8 Konstanten (12 kHz Sample-Rate, 15s Slots)
SAMPLE_RATE   = 12000
SLOT_SECONDS  = 15.0
SLOT_SAMPLES  = int(SAMPLE_RATE * SLOT_SECONDS)  # 180000

# FT8 Symbol-Timing
SYMBOL_RATE   = 6.25        # Hz
SYMBOL_SAMPLES = int(SAMPLE_RATE / SYMBOL_RATE)  # 1920 Samples/Symbol
N_SYMBOLS     = 79

# Costas-Array Positionen (bekannte Sync-Symbole, Index in 0-78)
COSTAS_POSITIONS = list(range(0, 7)) + list(range(36, 43)) + list(range(72, 79))
# Costas-Array Werte (7-element Muster, wiederholt 3x)
COSTAS_VALUES = [3, 1, 4, 0, 6, 5, 2]

# Alignment-Suchbereich
ALIGN_DT_SAMPLES = 8      # ±8 Samples ≈ ±0.67ms bei 12kHz
ALIGN_DF_HZ      = 1.5    # ±1.5 Hz
ALIGN_DF_STEPS   = 31     # Schrittweite ≈ 0.1 Hz

# Korrelations-Schwellwert
SCORE_THRESHOLD  = 0.75   # TODO: Im Feldtest kalibrieren!

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Datenstrukturen
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class FailedDecodeBuffer:
    """PCM-Buffer eines fehlgeschlagenen Decode-Versuchs."""
    pcm: np.ndarray          # float32, 12kHz, ~180k Samples
    slot_time: float         # UTC-Timestamp des Slot-Starts
    callsign: str            # Erwartetes Rufzeichen der Gegenstation
    freq_hz: float           # Erwartete Frequenz ±30 Hz
    qso_state: int           # QSO-State: 1=WAIT_REPORT, 2=WAIT_RR73, 3=CQ_WAIT
    own_callsign: str        # Eigenes Rufzeichen (für Kandidaten)
    own_locator: str         # Eigener Locator (für Kandidaten)
    snr_estimate: float = -10.0  # Letzter bekannter SNR der Gegenstation


@dataclass
class APLiteResult:
    """Ergebnis eines AP-Lite Rescue-Versuchs."""
    success: bool
    score: float
    recovered_message: Optional[str] = None
    aligned_dt_samples: float = 0.0
    aligned_df_hz: float = 0.0
    candidate_used: Optional[str] = None


# ─────────────────────────────────────────────────────────────────────────────
# Kandidaten-Generierung
# ─────────────────────────────────────────────────────────────────────────────

def generate_candidates(
    qso_state: int,
    their_callsign: str,
    own_callsign: str,
    own_locator: str,
    snr_estimate: float = -10.0,
) -> List[str]:
    """Mögliche FT8-Nachrichten basierend auf QSO-State generieren.

    Args:
        qso_state: 1=WAIT_REPORT, 2=WAIT_RR73, 3=CQ_WAIT
        their_callsign: Rufzeichen der Gegenstation
        own_callsign: Eigenes Rufzeichen
        own_locator: Eigener 4-Buchstaben-Locator (z.B. "JO31")
        snr_estimate: Letzter bekannter SNR für Report-Generierung

    Returns:
        Liste möglicher Nachrichten-Strings (werden danach encodiert)
    """
    # SNR auf FT8-Report mappen (-30 bis +29 dB)
    snr_clamped = max(-30, min(29, int(round(snr_estimate))))
    report = f"{snr_clamped:+03d}"  # z.B. "+01" oder "-15"

    candidates = []

    if qso_state == 1:
        # WAIT_REPORT: Wir warten auf Report + Locator von der Gegenstation
        # Format: "DA1MHH DK5ON JO31 -15" oder Varianten
        for snr_delta in range(-5, 6, 2):  # SNR-Fenster ±4 dB
            r = max(-30, min(29, snr_clamped + snr_delta))
            candidates.append(f"{own_callsign} {their_callsign} {own_locator} {r:+03d}")
        # TODO: Locator der Gegenstation fehlt hier — aus vorheriger Dekodierung merken!

    elif qso_state == 2:
        # WAIT_RR73: Wir warten auf RR73, 73 oder RRR
        candidates = [
            f"{own_callsign} {their_callsign} RR73",
            f"{own_callsign} {their_callsign} 73",
            f"{own_callsign} {their_callsign} RRR",
        ]

    elif qso_state == 3:
        # CQ_WAIT: Wir haben CQ gerufen, warten auf Anruf
        # Format: "<their_call> <our_call> <their_locator>" — Locator unbekannt!
        # Deshalb nur generisch mit bekannten DXCC-Präfixen
        # TODO: Locator-Kandidaten aus historischen Dekodierungen dieser Station?
        candidates = []  # Zu viele Unbekannte für State 3

    logger.debug(f"AP-Lite Kandidaten (State {qso_state}): {candidates}")
    return candidates


# ─────────────────────────────────────────────────────────────────────────────
# Costas-basiertes Alignment
# ─────────────────────────────────────────────────────────────────────────────

def _build_costas_reference(freq_hz: float, n_samples: int) -> np.ndarray:
    """Referenz-Signal NUR aus Costas-Sync-Symbolen generieren.

    TODO: Echte FT8-Costas-Symbole generieren (korrekte Phase, FSK).
          Aktuell: vereinfachte Näherung.
    """
    ref = np.zeros(n_samples, dtype=np.float32)
    t = np.arange(n_samples) / SAMPLE_RATE

    for i, (pos, val) in enumerate(zip(COSTAS_POSITIONS, COSTAS_VALUES * 3)):
        # Frequenz des Costas-Symbols: Basis + val * 6.25 Hz Spacing
        sym_freq = freq_hz + val * SYMBOL_RATE
        start = pos * SYMBOL_SAMPLES
        end = min(start + SYMBOL_SAMPLES, n_samples)
        if end > start:
            ref[start:end] = np.sin(2 * np.pi * sym_freq * t[start:end]).astype(np.float32)

    return ref


def align_buffers(
    buf1: np.ndarray,
    buf2: np.ndarray,
    freq_hz: float,
) -> Tuple[np.ndarray, float, float]:
    """Buf2 an Buf1 ausrichten via Costas-Sync-Suche.

    Sucht den Zeit-Offset (±ALIGN_DT_SAMPLES Samples) und
    Frequenz-Offset (±ALIGN_DF_HZ Hz) der buf2 maximiert die
    Korrelationsenergie auf den Costas-Symbol-Positionen.

    Args:
        buf1: Erster fehlgeschlagener Slot (Referenz)
        buf2: Zweiter fehlgeschlagener Slot (wird ausgerichtet)
        freq_hz: Erwartete Signal-Frequenz

    Returns:
        (aligned_buf2, dt_samples, df_hz)

    TODO: Validieren! Insbesondere Phasenkorrektur für kohärente Addition.
    """
    n = min(len(buf1), len(buf2))
    buf1 = buf1[:n]
    buf2 = buf2[:n]

    ref = _build_costas_reference(freq_hz, n)

    best_score = -1.0
    best_dt = 0
    best_df = 0.0
    t = np.arange(n) / SAMPLE_RATE

    df_values = np.linspace(-ALIGN_DF_HZ, ALIGN_DF_HZ, ALIGN_DF_STEPS)

    for dt in range(-ALIGN_DT_SAMPLES, ALIGN_DT_SAMPLES + 1):
        shifted = np.roll(buf2, dt)
        for df in df_values:
            # Frequenz-Korrektur (reales Signal via Multiplikation)
            corrected = shifted * np.cos(2 * np.pi * df * t).astype(np.float32)
            # Korrelation mit Costas-Referenz (nur auf Sync-Positionen)
            # Energie-Berechnung: Punkt-Produkt auf Costas-Samples
            costas_energy = 0.0
            for pos in COSTAS_POSITIONS:
                start = pos * SYMBOL_SAMPLES
                end = min(start + SYMBOL_SAMPLES, n)
                if end > start:
                    costas_energy += float(np.dot(corrected[start:end], ref[start:end]))
            if costas_energy > best_score:
                best_score = costas_energy
                best_dt = dt
                best_df = df

    # Optimales Alignment anwenden
    aligned = np.roll(buf2, best_dt)
    t_full = np.arange(len(aligned)) / SAMPLE_RATE
    aligned = aligned * np.cos(2 * np.pi * best_df * t_full).astype(np.float32)

    logger.debug(f"AP-Lite Alignment: dt={best_dt} samples, df={best_df:.2f} Hz, "
                 f"score={best_score:.2f}")
    return aligned, float(best_dt), best_df


# ─────────────────────────────────────────────────────────────────────────────
# Korrelation
# ─────────────────────────────────────────────────────────────────────────────

def correlate_candidate(
    combined_buf: np.ndarray,
    candidate_msg: str,
    freq_hz: float,
    encoder=None,
) -> float:
    """Einen Kandidaten gegen den kombinierten Buffer korrelieren.

    Args:
        combined_buf: Kohärent addierter Buffer (buf1 + aligned_buf2), float32 12kHz
        candidate_msg: FT8-Nachricht als String (z.B. "DA1MHH DK5ON RR73")
        freq_hz: Erwartete Frequenz des Signals
        encoder: SimpleFT8 Encoder-Instanz (für Referenz-Signal-Generierung)

    Returns:
        Korrelations-Score 0.0-1.0
    """
    if encoder is None:
        logger.warning("AP-Lite: Kein Encoder — Korrelation nicht möglich")
        return 0.0

    ref_wave = encoder.generate_reference_wave(candidate_msg, freq_hz, SAMPLE_RATE)
    if ref_wave is None:
        return 0.0

    # Normalisierte Kreuzkorrelation (Cosinus-Ähnlichkeit)
    n = min(len(combined_buf), len(ref_wave))
    buf = combined_buf[:n]
    ref = ref_wave[:n]
    norm = np.linalg.norm(buf) * np.linalg.norm(ref)
    overall_score = float(np.dot(buf, ref) / norm) if norm > 0 else 0.0

    # Costas-Symbol-Gewichtung: 21 bekannte Sync-Symbole einzeln normalisiert
    # DeepSeek-Empfehlung: pro Symbol normalisieren um Spike-Dominanz zu vermeiden
    costas_scores = []
    for pos in COSTAS_POSITIONS:
        start = pos * SYMBOL_SAMPLES
        end = min(start + SYMBOL_SAMPLES, n)
        if end - start < SYMBOL_SAMPLES // 2:
            continue
        seg_buf = buf[start:end]
        seg_ref = ref[start:end]
        seg_norm = np.linalg.norm(seg_buf) * np.linalg.norm(seg_ref)
        if seg_norm > 0:
            costas_scores.append(float(np.dot(seg_buf, seg_ref) / seg_norm))

    costas_score = float(np.mean(costas_scores)) if costas_scores else 0.0

    # 50% Gesamt + 50% Costas-Gewichtung
    weighted_score = 0.5 * overall_score + 0.5 * costas_score
    return max(0.0, min(1.0, weighted_score))


# ─────────────────────────────────────────────────────────────────────────────
# Haupt-Klasse
# ─────────────────────────────────────────────────────────────────────────────

class APLite:
    """AP-Lite Prozessor — schwache QSOs durch kohärente Addition retten.

    Verwendung:
        ap = APLite(encoder=self.encoder)
        # Bei Decode-Fail (aus main_window.py):
        ap.on_decode_failed(pcm, slot_time, callsign, freq, qso_state, ...)
        # Im nächsten Slot nach Decode-Fail:
        result = ap.try_rescue(pcm_new, slot_time_new, callsign, freq, qso_state, ...)
        if result and result.success:
            # QSO retten!
    """

    def __init__(self, encoder=None):
        self.enabled = AP_LITE_ENABLED
        self.encoder = encoder
        # Buffer: key = (callsign, qso_state)
        self._buffers: Dict[Tuple[str, int], FailedDecodeBuffer] = {}
        self._max_buffers = 3  # Mehr als 3 QSOs gleichzeitig = unwahrscheinlich

    def on_decode_failed(
        self,
        pcm: np.ndarray,
        slot_time: float,
        callsign: str,
        freq_hz: float,
        qso_state: int,
        own_callsign: str = "",
        own_locator: str = "",
        snr_estimate: float = -10.0,
    ) -> None:
        """Aufruf wenn Decode fehlschlägt ABER eine Nachricht erwartet wurde.

        Darf nur aufgerufen werden wenn ein aktives QSO läuft und
        die Gegenstation gerade hätte senden sollen.

        TODO: Hook-Punkt in main_window.py: _on_cycle_decoded wenn
              qso_sm.state in (WAIT_REPORT, WAIT_RR73) und messages leer.
        """
        if not self.enabled:
            return
        if callsign not in ("", None) and qso_state in (1, 2, 3):
            key = (callsign, qso_state)
            buf = FailedDecodeBuffer(
                pcm=pcm.copy(),
                slot_time=slot_time,
                callsign=callsign,
                freq_hz=freq_hz,
                qso_state=qso_state,
                own_callsign=own_callsign,
                own_locator=own_locator,
                snr_estimate=snr_estimate,
            )
            self._buffers[key] = buf
            # Cache-Limit durchsetzen
            if len(self._buffers) > self._max_buffers:
                oldest = next(iter(self._buffers))
                del self._buffers[oldest]
            logger.info(f"[AP-Lite] Buffer gespeichert: {callsign} State={qso_state} "
                        f"freq={freq_hz:.0f}Hz")

    def try_rescue(
        self,
        pcm_new: np.ndarray,
        slot_time_new: float,
        callsign: str,
        freq_hz: float,
        qso_state: int,
        own_callsign: str = "",
        own_locator: str = "",
        snr_estimate: float = -10.0,
    ) -> Optional[APLiteResult]:
        """Rescue-Versuch mit neuem Buffer starten.

        Aufruf: Wenn zweiter Slot fehlschlägt (gleicher State, gleiche Frequenz).

        Returns:
            APLiteResult wenn Rescue möglich, None wenn kein Buffer vorhanden.

        TODO: Hook-Punkt in main_window.py: zweiter Fehler im gleichen State.
        """
        if not self.enabled:
            return None

        key = (callsign, qso_state)
        prev_buf = self._buffers.get(key)
        if prev_buf is None:
            return None

        # Frequenz-Plausibilität prüfen (±30 Hz Toleranz)
        if abs(prev_buf.freq_hz - freq_hz) > 30.0:
            logger.debug(f"[AP-Lite] Freq-Abweichung zu gross: "
                         f"{prev_buf.freq_hz:.0f} vs {freq_hz:.0f} Hz")
            return None

        # Zeitlicher Abstand prüfen (sollte ~15s sein)
        dt_slots = slot_time_new - prev_buf.slot_time
        if not (10.0 <= dt_slots <= 20.0):
            logger.debug(f"[AP-Lite] Slot-Abstand unplausibel: {dt_slots:.1f}s")
            return None

        logger.info(f"[AP-Lite] Rescue-Versuch für {callsign} State={qso_state}")

        # Kandidaten generieren
        candidates = generate_candidates(
            qso_state=qso_state,
            their_callsign=callsign,
            own_callsign=own_callsign or prev_buf.own_callsign,
            own_locator=own_locator or prev_buf.own_locator,
            snr_estimate=prev_buf.snr_estimate,
        )
        if not candidates:
            logger.debug("[AP-Lite] Keine Kandidaten verfügbar")
            del self._buffers[key]
            return APLiteResult(success=False, score=0.0)

        # Alignment + kohärente Addition
        aligned_new, dt_s, df_hz = align_buffers(prev_buf.pcm, pcm_new, prev_buf.freq_hz)
        combined = prev_buf.pcm + aligned_new

        # Kandidaten korrelieren
        best_score = 0.0
        best_candidate = None
        for cand in candidates:
            score = correlate_candidate(combined, cand, prev_buf.freq_hz + df_hz, self.encoder)
            if score > best_score:
                best_score = score
                best_candidate = cand

        # Buffer aufräumen — max 2 Versuche
        del self._buffers[key]

        if best_score >= SCORE_THRESHOLD and best_candidate:
            logger.info(f"[AP-Lite] ERFOLG: '{best_candidate}' score={best_score:.3f}")
            return APLiteResult(
                success=True,
                score=best_score,
                recovered_message=best_candidate,
                aligned_dt_samples=dt_s,
                aligned_df_hz=df_hz,
                candidate_used=best_candidate,
            )
        else:
            logger.info(f"[AP-Lite] Fehlgeschlagen: score={best_score:.3f} < {SCORE_THRESHOLD}")
            return APLiteResult(success=False, score=best_score)

    def clear(self) -> None:
        """Alle Buffers löschen (bei QSO-Ende oder Band-Wechsel)."""
        self._buffers.clear()
        logger.debug("[AP-Lite] Buffers gelöscht")


# ─────────────────────────────────────────────────────────────────────────────
# Globale Singleton-Instanz
# ─────────────────────────────────────────────────────────────────────────────

_instance: Optional[APLite] = None


def get_instance(encoder=None) -> APLite:
    """Singleton-Accessor. encoder beim ersten Aufruf übergeben."""
    global _instance
    if _instance is None:
        _instance = APLite(encoder=encoder)
    return _instance
