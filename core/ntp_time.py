"""SimpleFT8 DT-basierte Zeitkorrektur.

Strategie (Mike's Ansatz, bestaetigt durch DeepSeek):
  1. Start mit Systemzeit (correction = 0)
  2. 4 Zyklen messen, Median bilden → ERSTE kumulative Korrektur
  3. 20 Zyklen mit Korrektur arbeiten
  4. Wieder 4 Zyklen messen → ZWEITE kumulative Korrektur (addiert!)
  5. Wiederholen

Korrektur ist KUMULATIV: correction += neuer_median
Jede Messung gibt nur den REST-Fehler nach vorheriger Korrektur.

Beispiel:
  Systemuhr 0.8s daneben
  Messung 1: DT +0.5 → correction = 0.5 → DT jetzt bei +0.3
  Messung 2: DT +0.3 → correction = 0.5 + 0.3 = 0.8 → DT bei ±0.1
"""

import statistics
import threading

# ── Konfiguration ─────────────────────────────────────────────────────────────

MEASURE_CYCLES = 4     # Zyklen pro Messphase
OPERATE_CYCLES = 20    # Zyklen Betrieb zwischen Messungen
MIN_STATIONS = 5       # Mindestanzahl Stationen pro Zyklus
MAX_CORRECTION = 2.0   # Maximale kumulative Korrektur (±2.0s)

# ── Zustand ───────────────────────────────────────────────────────────────────

_lock = threading.Lock()

_correction: float = 0.0          # Kumulative Korrektur in Sekunden
_phase: str = "measure"           # "measure" oder "operate"
_cycle_count: int = 0             # Zaehler innerhalb der Phase
_measure_buffer: list = []        # DT-Mediane der Messzyklen
_last_median_dt: float = 0.0      # Letzter Median (fuer Anzeige)
_last_sample_count: int = 0       # Letzte Stationsanzahl (fuer Anzeige)


def get_time() -> float:
    """Korrigierte Zeit — ueberall statt time.time() verwendbar."""
    import time
    return time.time() + _correction


def get_correction() -> float:
    """Aktuelle kumulative Korrektur in Sekunden."""
    return _correction


def get_status_text() -> str:
    """Status-String fuer UI."""
    if _last_sample_count == 0 and _correction == 0.0:
        return "DT-Korr: —"
    return (f"DT-Korr: {_correction:+.2f}s "
            f"(Median {_last_median_dt:+.2f}s, "
            f"Phase: {_phase} {_cycle_count})")


def update_from_decoded(dt_values: list) -> bool:
    """Pro Zyklus aufrufen mit den DT-Werten aller dekodierten Stationen.

    Sammelt Messungen waehrend MEASURE-Phase, ignoriert waehrend OPERATE-Phase.
    """
    global _correction, _phase, _cycle_count, _measure_buffer
    global _last_median_dt, _last_sample_count

    # Ausreisser filtern
    valid = [dt for dt in dt_values if -2.0 <= dt <= 2.0]
    if len(valid) < MIN_STATIONS:
        return False

    median_dt = statistics.median(valid)

    with _lock:
        _last_median_dt = median_dt
        _last_sample_count = len(valid)

        if _phase == "measure":
            # Median dieses Zyklus zum Mess-Buffer hinzufuegen
            _measure_buffer.append(median_dt)
            _cycle_count += 1

            if _cycle_count >= MEASURE_CYCLES:
                # Messphase abgeschlossen — Korrektur berechnen
                avg_median = statistics.median(_measure_buffer)

                # Nur korrigieren wenn signifikant (>100ms)
                if abs(avg_median) > 0.1:
                    _correction += avg_median  # KUMULATIV!
                    _correction = max(-MAX_CORRECTION, min(MAX_CORRECTION, _correction))
                    print(f"[DT-Korr] Messung fertig: Median={avg_median:+.3f}s "
                          f"→ Korrektur={_correction:+.3f}s (kumulativ)")
                else:
                    print(f"[DT-Korr] Messung fertig: Median={avg_median:+.3f}s "
                          f"→ kein Update (< 100ms)")

                # Wechsel in Betriebsphase
                _measure_buffer.clear()
                _cycle_count = 0
                _phase = "operate"
                return True

        elif _phase == "operate":
            _cycle_count += 1

            # Sprung-Erkennung: wenn DT ploetzlich >1.5s → Systemuhr geaendert
            if abs(median_dt) > 1.5:
                print(f"[DT-Korr] SPRUNG erkannt: DT={median_dt:+.2f}s → RESET + neu messen")
                _correction = 0.0
                _phase = "measure"
                _cycle_count = 0
                _measure_buffer.clear()
                return True

            if _cycle_count >= OPERATE_CYCLES:
                # Betriebsphase vorbei → neue Messung starten
                _cycle_count = 0
                _phase = "measure"
                _measure_buffer.clear()
                print(f"[DT-Korr] Neue Messphase gestartet (Korrektur={_correction:+.3f}s)")

    return False


def reset(keep_correction: bool = True):
    """Neue Messphase starten. Korrekturwert bleibt erhalten (Bandwechsel).

    keep_correction=True: Letzten Korrekturwert behalten, nur neu messen.
    keep_correction=False: Alles auf 0 (nur bei App-Start).
    """
    global _correction, _phase, _cycle_count, _measure_buffer
    global _last_median_dt, _last_sample_count
    with _lock:
        if not keep_correction:
            _correction = 0.0
        # Neu messen, aber Korrektur behalten
        _phase = "measure"
        _cycle_count = 0
        _measure_buffer = []
        _last_median_dt = 0.0
        _last_sample_count = 0
