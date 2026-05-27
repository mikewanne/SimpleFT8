"""AP-Lite — A-Priori-Kandidaten-Rettung für marginale QSO-Decodes.

Konzept (a priori = „im Voraus bekannt"):
  Während eines QSOs kennen wir aus dem QSO-Zustand fast die ganze
  erwartete Nachricht der Gegenstation — beide Rufzeichen und die
  Nachrichten-Struktur. Es bleiben nur wenige Restvarianten
  (WAIT_RR73 → genau 3: RR73/RRR/73; WAIT_REPORT → wenige Report-Werte).

  Wenn der FT8-Decoder den Partner-Slot nicht schafft, erzeugt AP-Lite
  für jede Restvariante das FT8-Referenzsignal und matcht es
  phasen-invariant gegen den empfangenen Slot. Schlägt der beste
  Kandidat den zweitbesten klar (Margen-Test), gilt die Nachricht als
  erkannt.

  Kein Signal-Decoding von Grund auf, kein Slot-Stapeln. Nur:
  „wir wissen, was wahrscheinlich gesendet wurde — passt einer der
  wenigen Kandidaten klar genug zum Empfang?"

AP-Lite ist rein BERATEND: bei einem Treffer zeigt die App eine
Info-Zeile. Es loggt kein QSO automatisch und löst kein TX aus —
der Operator entscheidet. Darum besteht keine Falsch-Positiv-Gefahr
für das Logbuch.

Historie: bis v0.97.x implementierte dieses Modul „kohärente Addition"
zweier Slots für SNR-Gewinn — ein konzeptioneller Irrweg (phasenabhängig,
im Mittel 0 dB Gewinn). v0.97.90 (Option D) baut AP-Lite auf das
ursprüngliche A-Priori-Konzept zurück.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from typing import List, Optional

import numpy as np

# ─────────────────────────────────────────────────────────────────────────────
# FEATURE FLAG — AP-Lite ist beratend (nur Info-Anzeige), daher gefahrlos an.
# P149 (27.05.2026): nur Fallback, Laufzeit-Wert kommt aus Settings via
# `APLite.apply_settings()`. Erlaubt Standalone-Tests ohne Settings-Objekt.
AP_LITE_ENABLED: bool = True
# ─────────────────────────────────────────────────────────────────────────────

SAMPLE_RATE = 12000

# Detektion: der beste Kandidat muss den zweitbesten um mindestens MARGIN_MIN
# schlagen. Synthetisch gemessen: echte Nachricht → Marge ~0.11, Rauschen/
# Fremdsignal → Marge ≤ 0.023. 0.05 liegt sicher dazwischen.
# P149 (27.05.2026): nur Fallback, Laufzeit-Wert kommt aus
# `APLite.margin_min` (via Settings `ap_lite_strictness`).
MARGIN_MIN: float = 0.05

# P149 (27.05.2026): Strenge-Stufen fuer Mike's UX-Slider.
# Werte basieren auf synthetischen Messungen v0.97.90 — nach 1-2 Field-
# Sessions mit Test-Modus AN ggf. neu kalibrieren.
STRICTNESS_MARGIN_MAP: dict[str, float] = {
    "locker": 0.04,   # Sicherheitsabstand zum Rauschen (0.023)
    "normal": 0.05,   # heutiger MARGIN_MIN — Verhalten unveraendert bei Default
    "streng": 0.10,   # konservativ fuer klare Treffer
}


def _resolve_margin(strictness: str) -> float:
    """Strenge-String -> Margen-Wert. Unbekannt -> 'normal'."""
    return STRICTNESS_MARGIN_MAP.get(strictness, STRICTNESS_MARGIN_MAP["normal"])

# Frequenz-Offset-Suche: reale Stationen liegen oft ±2-5 Hz neben der
# erwarteten Frequenz. Der Korrelator sucht dieses Fenster ab (via FFT,
# volle Auflösung — siehe correlate_candidate).
FREQ_SEARCH_HZ: float = 5.0

# Persistenter Rescue-Zähler — für Feld-Beobachtung („zu Testzwecken"):
# zählt erfolgreiche AP-Lite-Treffer über App-Neustarts hinweg.
_STATS_PATH = os.path.expanduser("~/.simpleft8/ap_lite_stats.json")

logger = logging.getLogger(__name__)


@dataclass
class APLiteResult:
    """Ergebnis eines AP-Lite Match-Versuchs."""
    success: bool
    score: float
    margin: float = 0.0
    recovered_message: Optional[str] = None


# ─────────────────────────────────────────────────────────────────────────────
# Kandidaten-Generierung (A-Priori-Kern — unverändert seit v0.95.10)
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
        Liste möglicher Nachrichten-Strings (3-Token-FT8-konform).
    """
    snr_clamped = max(-30, min(29, int(round(snr_estimate))))

    candidates: List[str] = []

    if qso_state == 1:
        # WAIT_REPORT: Gegenstation sendet einen Signal-Report.
        # Format: "OWN_CALL THEIR_CALL +-NN" (3 Tokens, FT8-konform).
        # SNR-Fenster ±5 dB, JEDE dB-Stufe. Schrittweite 2 (alte Version)
        # verfehlte wegen Parität jeden zweiten realen Report.
        for snr_delta in range(-5, 6, 1):
            r = max(-30, min(29, snr_clamped + snr_delta))
            candidates.append(f"{own_callsign} {their_callsign} {r:+03d}")

    elif qso_state == 2:
        # WAIT_RR73: Wir warten auf RR73, 73 oder RRR — genau 3 Varianten.
        candidates = [
            f"{own_callsign} {their_callsign} RR73",
            f"{own_callsign} {their_callsign} 73",
            f"{own_callsign} {their_callsign} RRR",
        ]

    elif qso_state == 3:
        # CQ_WAIT: Locator der anrufenden Station unbekannt → zu viele
        # Unbekannte für ein sinnvolles A-Priori-Matching.
        candidates = []

    logger.debug(f"AP-Lite Kandidaten (State {qso_state}): {candidates}")
    return candidates


# ─────────────────────────────────────────────────────────────────────────────
# Phasen-invariante Korrelation (nicht-kohärenter Matched Filter)
# ─────────────────────────────────────────────────────────────────────────────

def _analytic(x: np.ndarray) -> np.ndarray:
    """Analytisches Signal via FFT (Hilbert-Transformation).

    Liefert das komplexe Basisband-Äquivalent eines reellen Signals —
    Grundlage für die phasen-invariante Korrelation.
    """
    x = np.asarray(x, dtype=np.float64)
    n = len(x)
    if n == 0:
        return np.zeros(0, dtype=np.complex128)
    X = np.fft.fft(x)
    h = np.zeros(n)
    h[0] = 1.0
    if n % 2 == 0:
        h[n // 2] = 1.0
        h[1:n // 2] = 2.0
    else:
        h[1:(n + 1) // 2] = 2.0
    return np.fft.ifft(X * h)


def correlate_candidate(
    buf: np.ndarray,
    candidate_msg: str,
    freq_hz: float,
    encoder=None,
) -> float:
    """Einen Kandidaten phasen-invariant gegen den empfangenen Slot matchen.

    Bildet das analytische Signal von Empfang und Kandidaten-Referenz und
    berechnet den Betrag der normierten komplexen Kreuzkorrelation
    (nicht-kohärenter Matched Filter → unabhängig von der Trägerphase).
    Sucht zusätzlich ein kleines Frequenz-Fenster ab (±FREQ_SEARCH_HZ),
    weil reale Stationen ein paar Hz neben der Sollfrequenz liegen können.

    Args:
        buf: Empfangener PCM-Slot (float, 12 kHz).
        candidate_msg: FT8-Nachricht als String.
        freq_hz: Erwartete Audio-Frequenz des Signals.
        encoder: SimpleFT8 Encoder-Instanz (für Referenz-Signal).

    Returns:
        Korrelations-Score 0.0-1.0 (1.0 = perfekte Übereinstimmung).
    """
    if encoder is None:
        logger.warning("AP-Lite: Kein Encoder — Korrelation nicht möglich")
        return 0.0

    ref_wave = encoder.generate_reference_wave(candidate_msg, freq_hz, SAMPLE_RATE)
    if ref_wave is None:
        return 0.0

    n = min(len(buf), len(ref_wave))
    if n == 0:
        return 0.0

    ab = _analytic(np.asarray(buf[:n]))
    ar = _analytic(np.asarray(ref_wave[:n]))
    norm = np.linalg.norm(ab) * np.linalg.norm(ar)
    if norm <= 0:
        return 0.0

    # Frequenz-Offset-Suche: |Σ mixed·exp(-j2π·df·t)| ist die DFT von
    # mixed[k] = conj(ar[k])·ab[k] an der Frequenz df. EIN FFT liefert alle
    # df-Bins mit voller Auflösung fs/n (~0.08 Hz). Ein grobes Hz-Raster
    # würde den schmalen Peak verfehlen — über ~12 s Integration dreht
    # schon 0.5 Hz Versatz den Korrelations-Zeiger mehrfach durch.
    mixed = np.conj(ar) * ab
    spectrum = np.abs(np.fft.fft(mixed))
    max_bin = min(int(FREQ_SEARCH_HZ * n / SAMPLE_RATE), n // 2 - 1)
    best = spectrum[0]  # df = 0
    if max_bin >= 1:
        best = max(
            best,
            spectrum[1:max_bin + 1].max(),   # df > 0
            spectrum[n - max_bin:].max(),    # df < 0
        )
    return float(max(0.0, min(1.0, best / norm)))


# ─────────────────────────────────────────────────────────────────────────────
# Haupt-Klasse
# ─────────────────────────────────────────────────────────────────────────────

class APLite:
    """AP-Lite Prozessor — marginale QSO-Decodes via A-Priori-Matching erkennen.

    Verwendung:
        ap = APLite(encoder=self.encoder)
        # Wenn der Partner-Decode in einem aktiven QSO fehlschlägt:
        result = ap.try_rescue(pcm, freq_hz, their_call, qso_state, ...)
        if result and result.success:
            # Info anzeigen — der Operator entscheidet.
    """

    def __init__(self, encoder=None, stats_path: Optional[str] = _STATS_PATH):
        # P149 (27.05.2026): Settings-getriebene Defaults. Laufzeit-Werte
        # kommen aus `apply_settings()`. Konstanten sind nur Fallback.
        self.enabled = AP_LITE_ENABLED
        self.test_mode: bool = False
        self.min_snr_db: int = -20
        self.margin_min: float = MARGIN_MIN
        self.encoder = encoder
        self._stats_path = stats_path
        self.attempt_count: int = 0      # Match-Versuche (nur aktuelle Session)
        self.rescue_count: int = self._load_rescue_count()  # persistent

    def apply_settings(self, settings) -> None:
        """P149: Settings-Werte uebernehmen — idempotent.

        Aufruf-Punkte:
        1. `main_window.__init__` nach `get_instance()`.
        2. Nach Settings-Dialog-Save (Live-Update — naechster Slot greift).

        Live-Aenderungen mitten in `try_rescue` greifen erst beim
        naechsten Slot (kein Lock — KISS, Diagnose-Funktion).
        """
        self.enabled = bool(settings.get("ap_lite_enabled", True))
        self.test_mode = bool(settings.get("ap_lite_test_mode", False))
        self.min_snr_db = int(settings.get("ap_lite_min_snr_db", -20))
        strict = str(settings.get("ap_lite_strictness", "normal"))
        self.margin_min = _resolve_margin(strict)

    def _load_rescue_count(self) -> int:
        """Persistenten Rescue-Zähler laden (0 wenn keine/defekte Datei)."""
        if not self._stats_path:
            return 0
        try:
            with open(self._stats_path, "r", encoding="utf-8") as f:
                return max(0, int(json.load(f).get("rescue_count", 0)))
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            return 0

    def _save_rescue_count(self) -> None:
        """Rescue-Zähler atomar speichern — für Feld-Beobachtung."""
        if not self._stats_path:
            return
        try:
            os.makedirs(os.path.dirname(self._stats_path), exist_ok=True)
            tmp = self._stats_path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump({"rescue_count": self.rescue_count}, f)
            os.replace(tmp, self._stats_path)
        except OSError as e:
            logger.warning(f"[AP-Lite] Zähler speichern fehlgeschlagen: {e}")

    def try_rescue(
        self,
        pcm: np.ndarray,
        freq_hz: float,
        callsign: str,
        qso_state: int,
        own_callsign: str = "",
        own_locator: str = "",
        snr_estimate: float = -10.0,
        count_rescue: bool = True,
    ) -> Optional[APLiteResult]:
        """A-Priori-Match auf EINEM fehlgeschlagenen Slot.

        Args:
            pcm: Empfangener PCM-Slot (float, 12 kHz).
            freq_hz: Erwartete Audio-Frequenz der Gegenstation.
            callsign: Rufzeichen der Gegenstation.
            qso_state: 1=WAIT_REPORT, 2=WAIT_RR73, 3=CQ_WAIT.
            own_callsign / own_locator: eigene Stationsdaten.
            snr_estimate: letzter bekannter SNR (für Report-Kandidaten).
            count_rescue: P149 (R1-F7-Catch) — wenn False, wird der
                persistente `rescue_count` NICHT inkrementiert.
                Im Test-Modus auf False setzen damit die Metrik nicht
                durch Decoder-bestaetigte Treffer verfaelscht wird.

        Returns:
            APLiteResult, oder None wenn AP-Lite aus / keine Kandidaten /
            kein verwertbarer Slot.
        """
        from core.debug_log import debug_log as _dbg
        _dbg("AP-LITE",
            f"CALL call={callsign} state={qso_state} freq_hz={freq_hz:.0f} "
            f"snr_est={snr_estimate:.0f} test_mode={not count_rescue}")
        if not self.enabled:
            _dbg("AP-LITE", "SKIP reason=disabled")
            return None
        if not callsign or qso_state not in (1, 2, 3):
            _dbg("AP-LITE", f"SKIP reason=bad_args call='{callsign}' state={qso_state}")
            return None
        if pcm is None or len(pcm) == 0:
            _dbg("AP-LITE", "SKIP reason=no_pcm")
            return None

        candidates = generate_candidates(
            qso_state, callsign, own_callsign, own_locator, snr_estimate
        )
        if len(candidates) < 2:
            # Der Margen-Test (bester − zweitbester) ist erst ab 2 Kandidaten
            # definiert. State 3 liefert 0 Kandidaten.
            _dbg("AP-LITE",
                f"SKIP reason=few_cands n={len(candidates)} state={qso_state}")
            return None

        self.attempt_count += 1

        scored = sorted(
            (
                (correlate_candidate(pcm, cand, freq_hz, self.encoder), cand)
                for cand in candidates
            ),
            key=lambda sc: sc[0],
            reverse=True,
        )
        best_score, best_cand = scored[0]
        runner_up = scored[1][0] if len(scored) > 1 else 0.0
        margin = best_score - runner_up

        _dbg("AP-LITE",
            f"SCORED n_cands={len(candidates)} best={best_score:.3f} "
            f"runner={runner_up:.3f} margin={margin:.3f} "
            f"threshold={self.margin_min:.3f} best_cand='{best_cand}'")

        if margin >= self.margin_min:
            if count_rescue:
                self.rescue_count += 1
                self._save_rescue_count()
            _dbg("AP-LITE",
                f"MATCH cand='{best_cand}' score={best_score:.3f} "
                f"margin={margin:.3f} total_rescues={self.rescue_count} "
                f"counted={count_rescue}")
            logger.info(
                f"[AP-Lite] MATCH: '{best_cand}' score={best_score:.3f} "
                f"margin={margin:.3f}"
            )
            return APLiteResult(
                success=True,
                score=best_score,
                margin=margin,
                recovered_message=best_cand,
            )

        _dbg("AP-LITE",
            f"NO_MATCH best={best_score:.3f} margin={margin:.3f} "
            f"threshold={self.margin_min:.3f}")
        logger.info(
            f"[AP-Lite] kein klarer Treffer: best={best_score:.3f} "
            f"margin={margin:.3f} < {self.margin_min:.3f}"
        )
        return APLiteResult(success=False, score=best_score, margin=margin)


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
