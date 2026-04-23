"""SimpleFT8 DT-basierte Zeitkorrektur.

Strategie (Mike + Claude + DeepSeek, optimiert 23.04.2026):
  1. Start: gespeicherten Korrekturwert fuer aktuellen Modus+Band laden
  2. 2 Zyklen messen, Median → Korrektur verfeinern
  3. 10 Zyklen mit Korrektur arbeiten
  4. Wiederholen + nach jeder Messung speichern

Korrekturwerte werden PRO MODUS+BAND gespeichert:
  {"FT8_20m": +0.27, "FT8_40m": +0.25, "FT4_20m": +0.26, ...}

Beim Modus/Band-Wechsel: gespeicherten Wert laden → sofort gute Grundkorrektur.
Dadurch kein Kaltstart bei FT4/FT2 wo wenig Stationen fuer Neuberechnung.

Hinweis: Die 0.5s WSJT-X Protokoll-Konvention ist bereits im DT_BUFFER_OFFSET
des Decoders eingerechnet. Die Korrektur hier kompensiert nur noch die
FlexRadio VITA-49 Hardware-Latenz (~0.27s). Siehe dt.md fuer Details.
"""

import json
import statistics
import threading
from pathlib import Path

# ── Konfiguration ─────────────────────────────────────────────────────────────

INITIAL_MEASURE_CYCLES = 2   # Erste Messung: 2 Zyklen (schnelle Erstkorrektur)
STEADY_MEASURE_CYCLES = 2    # Folgemessungen: 2 Zyklen
OPERATE_CYCLES = 10          # 10 Zyklen Betrieb zwischen Messungen
MIN_STATIONS = 3             # Mindestanzahl Stationen (FT8)
MAX_CORRECTION = 2.0         # Maximale Korrektur FT8 (±2.0s)
DEADBAND = 0.05              # 50ms Totband
DAMPING = 0.7                # 70% Daempfung fuer Folge-Korrekturen

# Per-Modus engere Grenzen (FT4/FT2 haben kuerzere Slots)
_MAX_CORR = {"FT8": 1.0, "FT4": 0.5, "FT2": 0.3}

_DT_FILE = Path.home() / ".simpleft8" / "dt_corrections.json"

# ── Zustand ───────────────────────────────────────────────────────────────────

_lock = threading.Lock()

_correction: float = 0.0
_mode: str = "FT8"
_band: str = "20m"
_phase: str = "measure"
_cycle_count: int = 0
_measure_buffer: list = []
_last_median_dt: float = 0.0
_last_sample_count: int = 0
_is_initial: bool = True
_saved: dict = {}


def _mode_key() -> str:
    """Speicher-Schluessel: 'FT8_20m', 'FT4_40m', etc."""
    return f"{_mode}_{_band}"


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
    """Aktuellen Korrekturwert fuer Modus+Band speichern."""
    global _saved
    key = _mode_key()
    _saved[key] = round(_correction, 4)
    try:
        _DT_FILE.parent.mkdir(parents=True, exist_ok=True)
        _DT_FILE.write_text(json.dumps(_saved, indent=2))
    except Exception as e:
        print(f"[DT-Korr] Speichern fehlgeschlagen: {e}")


def _load_for_current_key() -> float:
    """Gespeicherten Wert laden, mit Migration von altem Format ('FT8' → 'FT8_20m')."""
    key = _mode_key()
    val = _saved.get(key, None)
    if val is not None:
        return val
    # Migration: alter Schluessel ohne Band
    old_val = _saved.get(_mode, None)
    if old_val is not None:
        print(f"[DT-Korr] Migration: '{_mode}' → '{key}' = {old_val:+.3f}s")
        return old_val
    return 0.0


# Beim Import laden
_load_saved()


def set_mode(mode: str, band: str | None = None):
    """Modus (und optional Band) wechseln — gespeicherten Korrekturwert laden."""
    global _correction, _mode, _band, _phase, _cycle_count, _measure_buffer, _is_initial
    with _lock:
        if _correction != 0.0:
            _save_current()
        _mode = mode
        if band is not None:
            _band = band
        saved_val = _load_for_current_key()
        _correction = saved_val
        _phase = "measure"
        _cycle_count = 0
        _measure_buffer = []
        _is_initial = (saved_val == 0.0)
        key = _mode_key()
        if saved_val != 0.0:
            print(f"[DT-Korr] {key}: Gespeicherter Wert {saved_val:+.3f}s geladen")
        else:
            print(f"[DT-Korr] {key}: Kein gespeicherter Wert, starte bei 0")


def set_band(band: str):
    """Band wechseln — gespeicherten Korrekturwert fuer neues Modus+Band laden."""
    global _correction, _band, _phase, _cycle_count, _measure_buffer, _is_initial
    with _lock:
        if _correction != 0.0:
            _save_current()
        _band = band
        saved_val = _load_for_current_key()
        _correction = saved_val
        _phase = "measure"
        _cycle_count = 0
        _measure_buffer = []
        _is_initial = (saved_val == 0.0)
        key = _mode_key()
        if saved_val != 0.0:
            print(f"[DT-Korr] {key}: Gespeicherter Wert {saved_val:+.3f}s geladen")
        else:
            print(f"[DT-Korr] {key}: Kein gespeicherter Wert, starte bei 0")


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
    Erste Korrektur bei wenig Stationen: gedaempft (verhindert Runaway).
    """
    global _correction, _phase, _cycle_count, _measure_buffer
    global _last_median_dt, _last_sample_count, _is_initial

    valid = [dt for dt in dt_values if -2.0 <= dt <= 2.0]

    # Mindestanzahl pro Modus
    _MIN = {"FT8": 3, "FT4": 1, "FT2": 1}.get(_mode, MIN_STATIONS)
    if len(valid) < _MIN:
        return False

    median_dt = statistics.median(valid)

    with _lock:
        _last_median_dt = median_dt
        _last_sample_count = len(valid)

        _max = _MAX_CORR.get(_mode, MAX_CORRECTION)

        if _phase == "measure":
            _measure_buffer.append(median_dt)
            _cycle_count += 1

            needed = INITIAL_MEASURE_CYCLES if _is_initial else STEADY_MEASURE_CYCLES
            if _cycle_count >= needed:
                avg_median = statistics.median(_measure_buffer)

                if abs(avg_median) > DEADBAND:
                    if _is_initial:
                        # Erste Korrektur: bei wenig Stationen gedaempft
                        strength = DAMPING if len(valid) <= 2 else 1.0
                        delta = avg_median * strength
                        _correction += delta
                        _is_initial = False
                        print(f"[DT-Korr] {_mode_key()} Erstkorrektur: "
                              f"Median={avg_median:+.3f}s ×{strength:.1f} "
                              f"→ Δ{delta:+.3f}s → Korrektur={_correction:+.3f}s")
                    else:
                        delta = avg_median * DAMPING
                        _correction += delta
                        print(f"[DT-Korr] {_mode_key()} Feinkorrektur: "
                              f"Median={avg_median:+.3f}s ×{DAMPING} "
                              f"→ Δ{delta:+.3f}s → Korrektur={_correction:+.3f}s")

                    _correction = max(-_max, min(_max, _correction))
                    _save_current()
                else:
                    print(f"[DT-Korr] {_mode_key()} Messung: "
                          f"Median={avg_median:+.3f}s → Totband ({DEADBAND}s), kein Update")

                _measure_buffer.clear()
                _cycle_count = 0
                _phase = "operate"
                return True

        elif _phase == "operate":
            _cycle_count += 1

            # Sprung-Erkennung: DT ploetzlich > 1.0s → Reset
            if abs(median_dt) > 1.0:
                print(f"[DT-Korr] {_mode_key()} SPRUNG: DT={median_dt:+.2f}s → RESET")
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
                print(f"[DT-Korr] {_mode_key()} Neue Messphase "
                      f"(Korrektur={_correction:+.3f}s)")

    return False


def reset(keep_correction: bool = True):
    """Neue Messphase starten.

    keep_correction=True: Korrekturwert behalten, nur neu messen (Bandwechsel).
    keep_correction=False: Alles auf 0 (App-Start).
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
