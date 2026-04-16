"""SimpleFT8 DT-basierte Zeitkorrektur.

Strategie (Mike + Claude + DeepSeek, optimiert 15.04.2026):
  1. Start: gespeicherten Korrekturwert fuer aktuellen Modus laden
  2. 2 Zyklen messen, Median → Korrektur verfeinern
  3. 10 Zyklen mit Korrektur arbeiten
  4. Wiederholen + nach jeder Messung speichern

Korrekturwerte werden PRO MODUS in config.json gespeichert:
  {"FT8": +0.73, "FT4": +0.45, "FT2": +0.12}
Beim Modus-Wechsel: gespeicherten Wert laden → sofort gute Grundkorrektur.
"""

import json
import statistics
import threading
from pathlib import Path

# ── Konfiguration ─────────────────────────────────────────────────────────────

INITIAL_MEASURE_CYCLES = 2   # Erste Messung: 2 Zyklen (schnelle Erstkorrektur)
STEADY_MEASURE_CYCLES = 2    # Folgemessungen: 2 Zyklen (robust genug)
OPERATE_CYCLES = 10           # 10 Zyklen Betrieb zwischen Messungen (2.5 Min FT8)
MIN_STATIONS = 3              # Mindestanzahl Stationen
MAX_CORRECTION = 2.0          # Maximale kumulative Korrektur (±2.0s)
DEADBAND = 0.05               # 50ms Totband (statt 100ms — praeziser)
DAMPING = 0.7                 # 70% Daempfung fuer Folge-Korrekturen

_DT_FILE = Path.home() / ".simpleft8" / "dt_corrections.json"

# ── Zustand ───────────────────────────────────────────────────────────────────

_lock = threading.Lock()

_correction: float = 0.0          # Kumulative Korrektur in Sekunden
_mode: str = "FT8"                # Aktueller Modus
_phase: str = "measure"           # "measure" oder "operate"
_cycle_count: int = 0             # Zaehler innerhalb der Phase
_measure_buffer: list = []        # DT-Mediane der Messzyklen
_last_median_dt: float = 0.0      # Letzter Median (fuer Anzeige)
_last_sample_count: int = 0       # Letzte Stationsanzahl (fuer Anzeige)
_is_initial: bool = True          # Erste Messung nach Start/Reset?
_saved: dict = {}                 # Gespeicherte Korrekturwerte pro Modus


def _load_saved():
    """Gespeicherte Korrekturwerte laden."""
    global _saved
    try:
        if _DT_FILE.exists():
            _saved = json.loads(_DT_FILE.read_text())
            print(f"[DT-Korr] Gespeicherte Werte geladen: {_saved}")
    except Exception:
        _saved = {}


def _save_current():
    """Aktuellen Korrekturwert fuer den Modus speichern."""
    global _saved
    _saved[_mode] = round(_correction, 4)
    try:
        _DT_FILE.parent.mkdir(parents=True, exist_ok=True)
        _DT_FILE.write_text(json.dumps(_saved, indent=2))
    except Exception as e:
        print(f"[DT-Korr] Speichern fehlgeschlagen: {e}")


# Beim Import laden
_load_saved()


def set_mode(mode: str):
    """Modus wechseln — gespeicherten Korrekturwert laden.

    Wird bei FT8↔FT4↔FT2 Wechsel aufgerufen.
    Laedt den zuletzt gespeicherten Wert fuer diesen Modus.
    """
    global _correction, _mode, _phase, _cycle_count, _measure_buffer, _is_initial
    with _lock:
        # Alten Wert speichern bevor wir wechseln
        if _correction != 0.0:
            _save_current()
        _mode = mode
        # Gespeicherten Wert fuer neuen Modus laden
        saved_val = _saved.get(mode, 0.0)
        _correction = saved_val
        _phase = "measure"
        _cycle_count = 0
        _measure_buffer = []
        _is_initial = (saved_val == 0.0)  # Nur initial wenn kein Wert gespeichert
        if saved_val != 0.0:
            print(f"[DT-Korr] Modus {mode}: Gespeicherter Wert {saved_val:+.3f}s geladen")
        else:
            print(f"[DT-Korr] Modus {mode}: Kein gespeicherter Wert, starte bei 0")


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

    # Ausreisser filtern + modus-abhaengige Mindestanzahl
    valid = [dt for dt in dt_values if -2.0 <= dt <= 2.0]
    _MIN = {"FT8": 3, "FT4": 2, "FT2": 1}.get(_mode, MIN_STATIONS)
    if len(valid) < _MIN:
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
                    _save_current()  # Nach jeder Korrektur speichern
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
