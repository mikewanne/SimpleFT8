"""SimpleFT8 DT-basierte Zeitkorrektur — EIN globaler Wert (P171).

Die gelernte Korrektur (~0.26s) ist die KONSTANTE FlexRadio-RX-Hardware-/
Transport-Latenz (VITA-49) — **modus- UND band-unabhaengig**. Die protokoll-/
slot-abhaengige Fensterlage liegt SEPARAT in ``decoder._DT_OFFSETS`` und ist
NICHT Teil dieser Korrektur. Daraus folgt das Design:

  - EIN globaler Korrekturwert fuer ALLE Modi und Baender.
  - Gelernt NUR aus FT8 (viele Stationen → robuster Median). FT4/FT2 NUTZEN den
    Wert, messen/schreiben NIE — wenige Stationen verschlechterten ihn frueher
    (z.B. FT4_20m=0.045 statt 0.27, 1-Stationen-Artefakt).
  - Persistenz: ``{"dt_correction_s": <float>}`` in
    ``~/.simpleft8/dt_corrections.json`` (Migration vom alten per-(Modus,Band)-
    Format: Median der FT8-Werte).

Decode-Unabhaengigkeit: die Korrektur ist KEINE Voraussetzung fuers Dekodieren
(der Decoder sucht die Sync ueber Sekunden; die DT wird AUS dekodierten
Stationen gelernt; Kaltstart = Hardware-Default 0.26). Sie macht die Anzeige
sauber und zentriert den Sende-Slot.

Historie: bis v0.98.59 per-(Modus,Band) + Cross-Modus-Fallback (P48-B). P171
(03.06.2026) auf einen Globalwert vereinfacht — Mike + DeepSeek: die Latenz ist
EINE physikalische Konstante, gepoolte FT8-Messung ist die genaueste Schaetzung.
"""

import json
import os
import statistics
import threading
from pathlib import Path

# ── Konfiguration ─────────────────────────────────────────────────────────────

INITIAL_MEASURE_CYCLES = 2   # Erste Messung: 2 Zyklen (schnelle Erstkorrektur)
STEADY_MEASURE_CYCLES = 2    # Folgemessungen: 2 Zyklen
OPERATE_CYCLES = 10          # 10 Zyklen Betrieb zwischen Messungen
MIN_STATIONS = 3             # Mindestanzahl Stationen (nur FT8 misst)
MAX_CORRECTION = 1.0         # Clamp ±1.0s (Werte liegen ~0.26)
DEADBAND = 0.02              # 20ms Totband (Anti-Einfrier)
DAMPING = 0.7                # 70% Daempfung fuer Folge-Korrekturen

# MAD-basierter Outlier-Filter (Hampel-Filter).
_MAD_K = 2.5
_MAD_MIN_N = 7    # Unter 7 Werten kein Filter
_MAD_MIN_OUT = 3  # Notnagel: Filter darf nicht mehr als (n-3) Werte entfernen

# Opt-in Debug-Logging: `export SIMPLEFT8_DT_DEBUG=1`
_DT_DEBUG = os.environ.get("SIMPLEFT8_DT_DEBUG", "0") == "1"

# Schnell-Konvergenz beim Erst-Mess-Slot wenn schon viele Stationen mit kleiner
# Streuung dabei sind — kein zweiter Slot zur Bestaetigung noetig.
_FAST_CONVERGENCE_MIN_STATIONS = 10
_FAST_CONVERGENCE_MAX_STDEV = 0.1

_DT_FILE = Path.home() / ".simpleft8" / "dt_corrections.json"
_SAVE_KEY = "dt_correction_s"   # neues Single-Value-Format

# ── Zustand ───────────────────────────────────────────────────────────────────

_lock = threading.Lock()

_correction: float = 0.0
_mode: str = "FT8"          # nur fuers Mess-Gating (nur FT8 misst) + Logging
_band: str = "20m"          # nur fuers Logging
_phase: str = "measure"
_cycle_count: int = 0
_measure_buffer: list = []
_last_median_dt: float = 0.0
_last_sample_count: int = 0
# _is_initial = "globaler Wert noch nie GEMESSEN" (Seed/Hardware-Default zaehlt
# nicht als Messung → erste FT8-Messung macht die gedaempfte Erstkorrektur).
_is_initial: bool = True

# Hardware-Default (FlexRadio ~0.26) fuer Kaltstart. Von main_window gesetzt.
_hardware_default_offset: float = 0.0


def _filter_outliers_mad(values: list, k: float = _MAD_K) -> list:
    """MAD-basierter Outlier-Filter (Hampel-Filter).

    Median Absolute Deviation ist robuster als Standardabweichung gegen
    Ausreisser. Werte mit |x - median| > k * MAD werden verworfen.

    Edge-Cases: < _MAD_MIN_N Werte → Identity; MAD=0 → Identity; nach Filter
    < _MAD_MIN_OUT uebrig → Identity (Notnagel). Pure function, thread-safe.
    """
    if len(values) < _MAD_MIN_N:
        return list(values)
    med = statistics.median(values)
    mad = statistics.median([abs(x - med) for x in values])
    if mad <= 0:
        return list(values)
    threshold = k * mad
    filtered = [x for x in values if abs(x - med) <= threshold]
    if len(filtered) < _MAD_MIN_OUT:
        return list(values)
    return filtered


def set_hardware_default(value_s: float) -> None:
    """Kaltstart-Seed (FlexRadio ~0.26). Von main_window._init_core_components.

    Setzt ``_correction`` NUR, wenn global noch kein Wert gemessen/migriert
    wurde (``_is_initial`` und ``_correction == 0.0``). ``_is_initial`` bleibt
    danach True — der Default ist kein eigener Messwert, die erste FT8-Messung
    soll die gedaempfte Erstkorrektur machen.
    """
    global _hardware_default_offset, _correction
    _hardware_default_offset = float(value_s)
    with _lock:
        if _is_initial and _correction == 0.0:
            _correction = _hardware_default_offset


def _load_saved() -> None:
    """Globalen Korrekturwert laden — mit In-Memory-Migration vom alten
    per-(Modus,Band)-Format. **Schreibt die Datei beim Import NICHT** (Tests
    importieren das Modul; Mikes echte Datei nicht beim Import anfassen). Die
    Datei wird beim naechsten ``_save_current()`` (erste FT8-Messung) ins neue
    Format ueberfuehrt.
    """
    global _correction, _is_initial
    try:
        if not _DT_FILE.exists():
            return
        data = json.loads(_DT_FILE.read_text())
    except Exception:
        return
    if not isinstance(data, dict):
        return
    # Neues Format
    if _SAVE_KEY in data:
        try:
            _correction = float(data[_SAVE_KEY])
            _is_initial = False
            print(f"[DT-Korr] Globaler Wert geladen: {_correction:+.3f}s")
        except (TypeError, ValueError):
            pass
        return
    # Migration alt→global: Median der FT8_*-Werte (sonst aller numerischen).
    # FT4/FT2-Ausreisser (z.B. FT4_20m=0.045) werden so verworfen.
    ft8 = [v for k, v in data.items()
           if isinstance(v, (int, float)) and not isinstance(v, bool)
           and k.upper().startswith("FT8")]
    allnum = [v for v in data.values()
              if isinstance(v, (int, float)) and not isinstance(v, bool)]
    pool = ft8 or allnum
    if pool:
        _correction = round(statistics.median(pool), 4)
        _is_initial = False
        src = (f"{len(ft8)} FT8-Werten (FT4/FT2-Ausreisser verworfen)" if ft8
               else f"{len(allnum)} numerischen Werten (keine FT8-Keys)")
        print(f"[DT-Korr] Migration alt→global: Median {_correction:+.3f}s aus {src}")


# Beim Import laden
_load_saved()


def _save_current() -> None:
    """Globalen Korrekturwert speichern (neues Single-Value-Format)."""
    try:
        _DT_FILE.parent.mkdir(parents=True, exist_ok=True)
        _DT_FILE.write_text(json.dumps({_SAVE_KEY: round(_correction, 4)}, indent=2))
    except Exception as e:
        print(f"[DT-Korr] Speichern fehlgeschlagen: {e}")


def set_mode(mode: str, band: str | None = None) -> None:
    """Modus (und optional Band) wechseln.

    P171: aendert den GLOBALEN Korrekturwert NICHT (Umschalten auf FT4/FT2
    behaelt den FT8-Wert). Nur Kontext fuers Mess-Gating/Logging aktualisieren
    und die Mess-Phase zuruecksetzen. ``_is_initial`` bleibt unangetastet
    (global — aendert sich nur bei der ersten FT8-Messung / beim Laden).
    """
    global _mode, _band, _phase, _cycle_count, _measure_buffer
    with _lock:
        _mode = mode
        if band is not None:
            _band = band
        _phase = "measure"
        _cycle_count = 0
        _measure_buffer = []


def set_band(band: str) -> None:
    """Band wechseln. P171: globaler Korrekturwert bleibt — nur Mess-Phase
    zuruecksetzen + Band fuers Logging merken."""
    global _band, _phase, _cycle_count, _measure_buffer
    with _lock:
        _band = band
        _phase = "measure"
        _cycle_count = 0
        _measure_buffer = []


def get_time() -> float:
    """Korrigierte Zeit — ueberall statt time.time() verwendbar."""
    import time
    return time.time() + _correction


def get_correction() -> float:
    """Aktueller globaler Korrekturwert in Sekunden."""
    return _correction


def get_status_text() -> str:
    """Status-String fuer UI."""
    if _last_sample_count == 0 and _correction == 0.0:
        return "DT-Korr: —"
    return (f"DT-Korr: {_correction:+.2f}s "
            f"(Median {_last_median_dt:+.2f}s, "
            f"Phase: {_phase} {_cycle_count})")


def update_from_decoded(dt_values: list) -> bool:
    """Pro Zyklus mit den DT-Werten aller dekodierten Stationen aufrufen.

    P171: NUR FT8 misst/schreibt — der gelernte Wert ist die Hardware-Latenz und
    gilt global fuer alle Modi/Baender. Auf FT4/FT2 No-op (der globale FT8-Wert
    wird weiter angewandt; die Einzel-Station-DT steht in der RX-Liste).
    """
    global _correction, _phase, _cycle_count, _measure_buffer
    global _last_median_dt, _last_sample_count, _is_initial

    # Nur FT8 lernt die Korrektur.
    if _mode != "FT8":
        return False

    valid = [dt for dt in dt_values if -2.0 <= dt <= 2.0]
    if len(valid) < MIN_STATIONS:
        return False

    filtered = _filter_outliers_mad(valid)
    median_dt = statistics.median(filtered)

    if _DT_DEBUG:
        raw_med = statistics.median(valid)
        print(f"[DT-DBG] {_mode}/{_band} n={len(valid)} "
              f"raw={raw_med:+.3f} filt={median_dt:+.3f} "
              f"outliers={len(valid) - len(filtered)} corr={_correction:+.3f}")

    with _lock:
        _last_median_dt = median_dt
        _last_sample_count = len(valid)

        if _phase == "measure":
            _measure_buffer.append(median_dt)
            _cycle_count += 1

            # Schnell-Konvergenz: 1. Slot schon viele Stationen, kleine Streuung.
            can_fast = (
                _is_initial
                and _cycle_count == 1
                and len(valid) >= _FAST_CONVERGENCE_MIN_STATIONS
                and statistics.stdev(valid) < _FAST_CONVERGENCE_MAX_STDEV
            )
            needed = 1 if can_fast else (
                INITIAL_MEASURE_CYCLES if _is_initial else STEADY_MEASURE_CYCLES
            )
            if _cycle_count >= needed:
                avg_median = statistics.median(_measure_buffer)

                if abs(avg_median) > DEADBAND:
                    if _is_initial:
                        # Erste Korrektur: bei wenig Stationen gedaempft.
                        strength = DAMPING if len(valid) <= 2 else 1.0
                        delta = avg_median * strength
                        _correction += delta
                        _is_initial = False
                        print(f"[DT-Korr] Erstkorrektur: Median={avg_median:+.3f}s "
                              f"×{strength:.1f} → Δ{delta:+.3f}s → {_correction:+.3f}s")
                    else:
                        delta = avg_median * DAMPING
                        _correction += delta
                        print(f"[DT-Korr] Feinkorrektur: Median={avg_median:+.3f}s "
                              f"×{DAMPING} → Δ{delta:+.3f}s → {_correction:+.3f}s")

                    _correction = max(-MAX_CORRECTION, min(MAX_CORRECTION, _correction))
                    _save_current()
                else:
                    print(f"[DT-Korr] Messung: Median={avg_median:+.3f}s → "
                          f"Totband ({DEADBAND}s), kein Update")

                _measure_buffer.clear()
                _cycle_count = 0
                _phase = "operate"
                return True

        elif _phase == "operate":
            _cycle_count += 1

            # Sprung-Erkennung: DT ploetzlich > 1.0s → Reset (nur FT8).
            if abs(median_dt) > 1.0:
                print(f"[DT-Korr] SPRUNG: DT={median_dt:+.2f}s → RESET")
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


def reset(keep_correction: bool = True) -> None:
    """Neue Messphase starten.

    keep_correction=True: globalen Korrekturwert behalten, nur neu messen.
    keep_correction=False: Korrektur auf 0 (voller App-Start-Reset).
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
