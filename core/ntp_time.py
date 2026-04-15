"""SimpleFT8 DT-basierte Zeitkorrektur.

Strategie (Mike + Claude + DeepSeek, optimiert 15.04.2026):
  1. Start mit Systemzeit (correction = 0)
  2. 2 Zyklen messen, Median → ERSTE Korrektur (100% aggressiv)
  3. 10 Zyklen mit Korrektur arbeiten
  4. 2 Zyklen messen → Folge-Korrektur (70% gedaempft, verhindert Oszillation)
  5. Wiederholen

Korrektur ist KUMULATIV: correction += neuer_median * daempfung
Jede Messung gibt nur den REST-Fehler nach vorheriger Korrektur.
Erste Runde: volle Korrektur. Danach: 70% Daempfung gegen Rauschen.
"""

import statistics
import threading

# ── Konfiguration ─────────────────────────────────────────────────────────────

INITIAL_MEASURE_CYCLES = 2   # Erste Messung: 2 Zyklen (schnelle Erstkorrektur)
STEADY_MEASURE_CYCLES = 2    # Folgemessungen: 2 Zyklen (robust genug)
OPERATE_CYCLES = 10           # 10 Zyklen Betrieb zwischen Messungen (2.5 Min FT8)
MIN_STATIONS = 3              # Mindestanzahl Stationen
MAX_CORRECTION = 2.0          # Maximale kumulative Korrektur (±2.0s)
DEADBAND = 0.05               # 50ms Totband (statt 100ms — praeziser)
DAMPING = 0.7                 # 70% Daempfung fuer Folge-Korrekturen

# ── Zustand ───────────────────────────────────────────────────────────────────

_lock = threading.Lock()

_correction: float = 0.0          # Kumulative Korrektur in Sekunden
_phase: str = "measure"           # "measure" oder "operate"
_cycle_count: int = 0             # Zaehler innerhalb der Phase
_measure_buffer: list = []        # DT-Mediane der Messzyklen
_last_median_dt: float = 0.0      # Letzter Median (fuer Anzeige)
_last_sample_count: int = 0       # Letzte Stationsanzahl (fuer Anzeige)
_is_initial: bool = True          # Erste Messung nach Start/Reset?


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
    Erste Korrektur: 100% aggressiv. Folge-Korrekturen: 70% gedaempft.
    """
    global _correction, _phase, _cycle_count, _measure_buffer
    global _last_median_dt, _last_sample_count, _is_initial

    # Ausreisser filtern
    valid = [dt for dt in dt_values if -2.0 <= dt <= 2.0]
    if len(valid) < MIN_STATIONS:
        return False

    median_dt = statistics.median(valid)

    with _lock:
        _last_median_dt = median_dt
        _last_sample_count = len(valid)

        if _phase == "measure":
            _measure_buffer.append(median_dt)
            _cycle_count += 1

            # Messphase: 2 Zyklen (statt 4)
            needed = INITIAL_MEASURE_CYCLES if _is_initial else STEADY_MEASURE_CYCLES
            if _cycle_count >= needed:
                avg_median = statistics.median(_measure_buffer)

                if abs(avg_median) > DEADBAND:
                    if _is_initial:
                        # Erste Korrektur: volle Staerke (schnell einrasten)
                        _correction += avg_median
                        _is_initial = False
                        print(f"[DT-Korr] Erstkorrektur: Median={avg_median:+.3f}s "
                              f"→ Korrektur={_correction:+.3f}s (100%)")
                    else:
                        # Folge-Korrektur: gedaempft (verhindert Oszillation)
                        delta = avg_median * DAMPING
                        _correction += delta
                        print(f"[DT-Korr] Feinkorrektur: Median={avg_median:+.3f}s "
                              f"×{DAMPING} → Δ{delta:+.3f}s → Korrektur={_correction:+.3f}s")
                    _correction = max(-MAX_CORRECTION, min(MAX_CORRECTION, _correction))
                else:
                    print(f"[DT-Korr] Messung: Median={avg_median:+.3f}s "
                          f"→ im Totband ({DEADBAND}s), kein Update")

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
                _is_initial = True
                _phase = "measure"
                _cycle_count = 0
                _measure_buffer.clear()
                return True

            if _cycle_count >= OPERATE_CYCLES:
                _cycle_count = 0
                _phase = "measure"
                _measure_buffer.clear()
                print(f"[DT-Korr] Neue Messphase (Korrektur={_correction:+.3f}s)")

    return False


def reset(keep_correction: bool = True):
    """Neue Messphase starten. Korrekturwert bleibt erhalten (Bandwechsel).

    keep_correction=True: Letzten Korrekturwert behalten, nur neu messen.
    keep_correction=False: Alles auf 0 (nur bei App-Start).
    """
    global _correction, _phase, _cycle_count, _measure_buffer
    global _last_median_dt, _last_sample_count, _is_initial
    with _lock:
        if not keep_correction:
            _correction = 0.0
            _is_initial = True
        _phase = "measure"
        _cycle_count = 0
        _measure_buffer = []
        _last_median_dt = 0.0
        _last_sample_count = 0
