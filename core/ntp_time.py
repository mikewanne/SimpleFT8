"""SimpleFT8 DT-basierte Zeitkorrektur.

Strategie:
  Jede dekodierte FT8-Station hat einen DT-Wert (Delta Time).
  Der Median aller DT-Werte eines Zyklus zeigt wie weit unsere
  Zeit (inkl. Radio-Latenz) vom FT8-Band-Konsens abweicht.

  Vorteil gegenüber NTP:
  - Kein Internet nötig
  - Inkludiert automatisch Radio-Latenz
  - Selbstkalibrierend aus echtem Bandgeschehen
  - Keine externen Abhängigkeiten

  Beispiel:
    Alle Stationen zeigen DT ≈ +0.4s
    → unsere Uhr geht 0.4s nach
    → get_time() gibt time.time() + 0.4 zurück

TODO: UNGETESTET — muss im Heimstudio mit echtem Radio und
      echtem Bandverkehr validiert werden.
      Besonders prüfen:
      - Vorzeichen der Korrektur korrekt?
      - Smoothing-Faktor 0.3 sinnvoll?
      - Mindestanzahl Stationen (aktuell 5) ausreichend?
      - Verhalten bei wenig Bandverkehr?
"""

import time
import statistics
import threading

# Aktuelle Zeitkorrektur in Sekunden (Median-DT basiert)
_dt_correction: float = 0.0

# Anzahl der DT-Werte die in die letzte Berechnung eingeflossen sind
_last_sample_count: int = 0

# Letzter berechneter Median-DT (für UI-Anzeige / Debugging)
_last_median_dt: float = 0.0

# Lock für thread-sichere Zugriffe
_lock = threading.Lock()


def get_time() -> float:
    """Korrigierte Zeit — überall statt time.time() verwenden.

    Gibt time.time() + DT-Korrektur zurück.
    Ohne ausreichend Dekodierungen: identisch mit time.time().
    """
    return time.time() + _dt_correction


def get_correction() -> float:
    """Aktuelle DT-Korrektur in Sekunden (für UI/Debug)."""
    return _dt_correction


def get_status_text() -> str:
    """Kurzer Status-String für UI-Anzeige."""
    if _last_sample_count == 0:
        return "DT-Korr: —"
    return (f"DT-Korr: {_dt_correction:+.3f}s "
            f"(Median {_last_median_dt:+.3f}s, "
            f"n={_last_sample_count})")


def update_from_decoded(dt_values: list) -> bool:
    """DT-Korrektur aus dekodierten Stationen aktualisieren.

    Soll nach jedem Dekodier-Zyklus mit den DT-Werten aller
    dekodierten Stationen aufgerufen werden.

    DT-Interpretation:
      median_dt > 0: Stationen kommen "zu spät" bei uns an
                     → unsere Uhr geht nach → positiv korrigieren
      median_dt < 0: Stationen kommen "zu früh"
                     → unsere Uhr geht vor → negativ korrigieren

    Smoothing: Neue Korrektur fließt nur zu 30% ein um
               Sprünge durch einzelne Ausreißer-Zyklen zu dämpfen.

    Args:
        dt_values: Liste der DT-Werte aller dekodierten Nachrichten
                   (in Sekunden, typisch -2.0 bis +2.0).
    Returns:
        True wenn Korrektur aktualisiert wurde, False wenn zu wenig
        Daten.

    TODO: Vorzeichen, Smoothing-Faktor und Schwellwerte im
          Feldtest validieren!
    """
    global _dt_correction, _last_sample_count, _last_median_dt

    # Mindestens 5 Stationen für aussagekräftigen Median
    if len(dt_values) < 5:
        return False

    # Ausreißer filtern: nur DT zwischen -2s und +2s gültig
    valid = [dt for dt in dt_values if -2.0 <= dt <= 2.0]
    if len(valid) < 5:
        return False

    median_dt = statistics.median(valid)

    # Totband: ±0.3s → NICHT korrigieren (normaler Stations-Jitter)
    # Verhindert Oszillation: Korrektur schiesst auf 0.0, Jitter bringt +0.3,
    # Korrektur reagiert → Welle. Mit Totband: einmal kalibriert, stabil.
    if abs(median_dt) < 0.3:
        with _lock:
            _last_median_dt = median_dt
            _last_sample_count = len(valid)
        return False

    # 1. Zyklus: volle Korrektur sofort anwenden
    # Danach: sanfte 20/80 Mischung (kein Ueberschiessen)
    target = median_dt
    with _lock:
        if _last_sample_count == 0:
            _dt_correction = target
        else:
            _dt_correction = _dt_correction * 0.8 + target * 0.2
        # Korrektur auf ±2.0s begrenzen (Sicherheit)
        _dt_correction = max(-2.0, min(2.0, _dt_correction))
        _last_median_dt = median_dt
        _last_sample_count = len(valid)
        correction = _dt_correction

    print(f"[DT-Korr] Median={median_dt:+.3f}s "
          f"→ Korrektur={correction:+.3f}s "
          f"(n={len(valid)})")
    return True


def reset():
    """Korrektur zurücksetzen (z.B. bei Bandwechsel)."""
    global _dt_correction, _last_sample_count, _last_median_dt
    with _lock:
        _dt_correction = 0.0
        _last_sample_count = 0
        _last_median_dt = 0.0
