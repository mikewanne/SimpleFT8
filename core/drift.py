"""SimpleFT8 Frequenz-Drift-Kompensation.

Billige QRP-Gegenstationen (QRP Labs, uBITX etc.) driften 0.5-5 Hz
ueber die 15s eines FT8-Slots. Unser FlexRadio (GNSS) driftet nicht,
aber die Gegenstationen schon → Dekodierung verschlechtert sich.

Strategie:
  Nach den normalen Decode-Passes wird das Audio mit verschiedenen
  linearen Drift-Korrekturen versehen und nochmal dekodiert.
  Neue Stationen die nur mit Korrektur dekodiert werden = Gewinn.

  Drift-Korrektur: Analytisches Signal (Hilbert) × exp(-jπ·d·t²)
  d = Drift-Rate in Hz/s, t = Zeit in Sekunden

Drift-Werte: ±0.5, ±1.5 Hz/s
  → deckt 0.5-2.0 Hz Gesamtdrift ueber 12.64s ab
  → entspricht 80-90% realer QRP-Station-Drift

Performance: ~2ms pro Korrektur (152k Samples FFT) + Decode-Zeit der C-Library.
  4 Drift-Werte × ~100ms Decode = ~400ms extra pro Zyklus.

TODO: KOMPLETT UNGETESTET — Feldtest-Validierung erforderlich!
      Insbesondere: Bringt es tatsaechlich neue Decodes?
      False Positives? Performance-Impact akzeptabel?
"""

import numpy as np

# Drift-Werte zum Ausprobieren (Hz/s)
# Positiv = Station driftet nach oben, negativ = nach unten
DRIFT_RATES = [-1.5, -0.5, 0.5, 1.5]

# Minimaler Drift ab dem Korrektur Sinn macht (darunter: kein Effekt)
MIN_DRIFT_RATE = 0.3  # Hz/s → ~3.8 Hz Gesamtdrift ueber 12.64s


def _to_analytic(signal_real: np.ndarray) -> np.ndarray:
    """Reelles Signal → analytisches Signal via FFT (ohne scipy).

    Nullt negative Frequenzen, verdoppelt positive → komplexes Signal
    dessen Realteil das Original ist und Imaginaerteil die Hilbert-Transformierte.
    """
    n = len(signal_real)
    spectrum = np.fft.fft(signal_real.astype(np.float64))

    # Hilbert-Multiplikator: DC=1, positive freq=2, negative freq=0, Nyquist=1
    h = np.zeros(n)
    h[0] = 1.0
    if n % 2 == 0:
        h[1:n // 2] = 2.0
        h[n // 2] = 1.0
    else:
        h[1:(n + 1) // 2] = 2.0

    return np.fft.ifft(spectrum * h)


def apply_drift_correction(
    audio_int16: np.ndarray,
    drift_hz_per_sec: float,
    sample_rate: int = 12000,
) -> np.ndarray:
    """Lineare Frequenz-Drift aus int16 Audio entfernen.

    Wandelt in analytisches Signal (Hilbert), wendet quadratische
    Phasenkorrektur an, gibt reelles int16 Signal zurueck.

    Args:
        audio_int16: 1D int16 Array @ sample_rate
        drift_hz_per_sec: Drift-Rate (positiv = Station driftet hoch)
        sample_rate: Abtastrate (Standard 12000)

    Returns:
        Drift-korrigiertes int16 Array gleicher Laenge.
    """
    if abs(drift_hz_per_sec) < 0.01:
        return audio_int16  # Kein messbarer Drift

    # Analytisches Signal (komplex)
    analytic = _to_analytic(audio_int16)

    # Quadratische Phasenkorrektur: exp(-jπ · drift · t²)
    # Entfernt lineare Frequenzaenderung ueber die Zeit
    t = np.arange(len(analytic)) / sample_rate
    correction = np.exp(-1j * np.pi * drift_hz_per_sec * t * t)
    corrected = analytic * correction

    # Zurueck zu reellem int16
    result = np.clip(corrected.real, -32767, 32767).astype(np.int16)
    return result


def generate_drift_variants(
    audio_int16: np.ndarray,
    drift_rates: list[float] | None = None,
    sample_rate: int = 12000,
) -> list[tuple[float, np.ndarray]]:
    """Mehrere Drift-korrigierte Varianten des Audios erzeugen.

    Args:
        audio_int16: Original-Audio (int16, 12kHz)
        drift_rates: Liste von Drift-Raten (Hz/s). Default: DRIFT_RATES
        sample_rate: Abtastrate

    Returns:
        Liste von (drift_rate, korrigiertes_audio) Tupeln.
    """
    if drift_rates is None:
        drift_rates = DRIFT_RATES

    variants = []
    for rate in drift_rates:
        corrected = apply_drift_correction(audio_int16, rate, sample_rate)
        variants.append((rate, corrected))

    return variants
