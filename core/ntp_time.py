"""SimpleFT8 DT-basierte Zeitkorrektur — manueller Kalibrier-Knopf (v0.99.0).

EIN globaler Korrekturwert (~0.26s) gleicht zwei Dinge aus: die KONSTANTE
FlexRadio-RX-Transport-Latenz (VITA-49) UND eine eventuelle Abweichung der
System-Uhr. Die protokoll-/slot-abhaengige Fensterlage liegt SEPARAT in
``decoder._DT_OFFSETS`` und ist NICHT Teil dieser Korrektur.

**Bis v0.98.x** wurde der Wert AUTOMATISCH und DAUERHAFT aus den FT8-Stationen
nachgeregelt (Mess-/Operate-Phasen, Daempfung, Sprung-Reset). Diese Regelschleife
war fragil: der Wert pendelte, sprang ins Minus, ein Modus-Wechsel-Uebergang
verdarb ihn (→ OMNI-CQ-Sende-Takt verdoppelte sich). **v0.99.0 ersetzt sie durch
einen MANUELLEN Kalibrier-Knopf** (Mike-Entscheidung 03.06.2026):

  - Der Wert aendert sich NUR auf Knopfdruck → stabil, kein Pendeln, kein
    Uebergangs-Bug. Zwischen Kalibrierungen ein fester Wert.
  - ``record_samples()`` puffert die DT-Werte der letzten FT8-Slots (gleitendes
    Fenster), LERNT aber nicht. ``calibrate()`` nimmt diesen Puffer EINMAL,
    bildet den (MAD-gefilterten) Median der Residuen und korrigiert.
  - Warum kein FESTER Konstanten-Wert? Mikes Ferienhaus-iMac hat eine defekte
    Pufferbatterie → die System-Uhr driftet je nach Standzeit um 3–5 s (mal vor,
    mal nach). Ein fester Wert wuerde veralten; ein Knopfdruck justiert nach.
    Negative Werte sind daher LEGITIM (Uhr geht vor) — KEIN Negativ-Riegel, nur
    ein symmetrischer Sanity-Clamp ``±MAX_CORRECTION``.

INKREMENTELL, nicht absolut: der Decoder verschiebt das Audio bereits um
``get_correction()``, die gemessenen ``m.dt`` sind also die RESIDUEN nach der
aktuellen Korrektur. ``calibrate()`` rechnet darum ``_correction += median`` —
ein Klick konvergiert voll (z.B. corr=0.26, Bedarf 0.0 → Residuen ~−0.26 →
0.26+(−0.26)=0.0).

Gelernt/kalibriert wird NUR aus FT8 (viele Stationen → robuster Median). FT4/FT2
NUTZEN den Wert (plus ``_MODE_DELTA``), tragen aber nie zur Kalibrierung bei.

Persistenz: ``{"dt_correction_s": <float>}`` in
``~/.simpleft8/dt_corrections.json`` (Migration vom alten per-(Modus,Band)-Format:
Median der FT8-Werte).
"""

import json
import os
import statistics
import threading
from collections import deque
from pathlib import Path

# ── Konfiguration ─────────────────────────────────────────────────────────────

MIN_STATIONS = 5             # Mindestanzahl FT8-Stationen fuer eine Kalibrierung
MAX_CORRECTION = 1.0         # symmetrischer Sanity-Clamp ±1.0s (Werte liegen ~0.26)
RECENT_SLOTS = 3             # gleitendes Fenster: DT-Werte der letzten 3 FT8-Slots
                             # (~45s) — genug um auch auf ruhigen Baendern sicher
                             # MIN_STATIONS Stationen zu sammeln.

# ── Modus-Versatz (field-kalibriert, PROVISORISCH) ────────────────────────────
# Der Korrekturwert ist NICHT rein die Funkgeraet-Latenz — er ist MODUS-ABHAENGIG
# (Mike-Field 03.06.2026): FT8 braucht ~+0.29s, FT4 effektiv ~0. Der Unterschied
# ist ein protokoll-/fenster-abhaengiger Versatz (je schneller der Modus, desto
# enger die Toleranz). Darum: nur FT8 wird kalibriert (`_correction`, viele
# Stationen); FT4/FT2 bekommen einen FESTEN Delta obendrauf.
# `effektive_Korrektur(mode) = _correction + _MODE_DELTA[mode]`.
#
# _MODE_DELTA["FT4"] = -0.30: zentriert FT4 in Anzeige + RX-Decode-Fensterlage
# (beide ueber get_correction()). NICHT im Slot-Takt/TX: der laeuft ueber
# get_time() auf der reinen FT8-Basis (sonst feuert cycle_start auf FT4 zu spaet
# und der Encoder-Drift-Guard verdoppelt den Sende-Takt — Field-Bug v0.98.63).
# ⚠️ PROVISORISCH/empirisch. FT2 = 0.0 (Button versteckt, spaeter kalibrieren).
_MODE_DELTA = {"FT8": 0.0, "FT4": -0.30, "FT2": 0.0}

# MAD-basierter Outlier-Filter (Hampel-Filter).
_MAD_K = 2.5
_MAD_MIN_N = 7    # Unter 7 Werten kein Filter
_MAD_MIN_OUT = 3  # Notnagel: Filter darf nicht mehr als (n-3) Werte entfernen

# Opt-in Debug-Logging: `export SIMPLEFT8_DT_DEBUG=1`
_DT_DEBUG = os.environ.get("SIMPLEFT8_DT_DEBUG", "0") == "1"

_DT_FILE = Path.home() / ".simpleft8" / "dt_corrections.json"
_SAVE_KEY = "dt_correction_s"   # Single-Value-Format

# ── Zustand ───────────────────────────────────────────────────────────────────

_lock = threading.Lock()

_correction: float = 0.0
_mode: str = "FT8"          # nur fuers Kalibrier-Gating (nur FT8) + Delta + Logging
_band: str = "20m"          # nur fuers Logging
_last_median_dt: float = 0.0
_last_sample_count: int = 0
# _is_initial = "globaler Wert noch nie kalibriert" (Seed/Hardware-Default zaehlt
# nicht als Kalibrierung). Steuert nur die "DT: —"-Anzeige im uninitialisierten
# Zustand.
_is_initial: bool = True

# Gleitendes Fenster der letzten FT8-Slots: je Slot eine Liste valider DT-Werte.
# Quelle fuer calibrate(). Geleert bei Modus-/Band-Wechsel (frischer Start).
_recent_samples: deque = deque(maxlen=RECENT_SLOTS)

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

    Setzt ``_correction`` NUR, wenn global noch kein Wert kalibriert/migriert
    wurde (``_is_initial`` und ``_correction == 0.0``). ``_is_initial`` bleibt
    danach True — der Default ist keine eigene Kalibrierung, die erste manuelle
    Kalibrierung setzt ihn auf False.
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
    Datei wird beim naechsten ``_save_current()`` (erste Kalibrierung) ins neue
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
    # Migration alt→global: Median NUR der FT8_*-Werte (viele Stationen → robust).
    # FT4/FT2-Ausreisser (z.B. FT4_20m=0.045) sind durch ihren Modus-Versatz KEINE
    # gueltige globale Basis. Gibt es KEINE FT8-Keys, ist keine sichere Basis
    # ableitbar → NICHT migrieren, bei _is_initial=True / _correction=0.0 bleiben
    # (Hardware-Default bzw. erste Kalibrierung korrigiert sauber).
    ft8 = [v for k, v in data.items()
           if isinstance(v, (int, float)) and not isinstance(v, bool)
           and k.upper().startswith("FT8")]
    if not ft8:
        return
    _correction = round(statistics.median(ft8), 4)
    _is_initial = False
    print(f"[DT-Korr] Migration alt→global: Median {_correction:+.3f}s "
          f"aus {len(ft8)} FT8-Werten (FT4/FT2-Ausreisser verworfen)")


# Beim Import laden
_load_saved()


def _save_current() -> None:
    """Globalen Korrekturwert speichern (Single-Value-Format)."""
    try:
        _DT_FILE.parent.mkdir(parents=True, exist_ok=True)
        _DT_FILE.write_text(json.dumps({_SAVE_KEY: round(_correction, 4)}, indent=2))
    except Exception as e:
        print(f"[DT-Korr] Speichern fehlgeschlagen: {e}")


def set_mode(mode: str, band: str | None = None) -> None:
    """Modus (und optional Band) wechseln.

    Aendert den GLOBALEN Korrekturwert NICHT (Umschalten auf FT4/FT2 behaelt den
    Wert; nur ``_MODE_DELTA`` wirkt zusaetzlich). Leert das gleitende
    Kalibrier-Fenster (frischer Start nach Wechsel) und merkt Modus/Band fuers
    Delta + Logging.
    """
    global _mode, _band
    with _lock:
        _mode = mode
        if band is not None:
            _band = band
        _recent_samples.clear()


def set_band(band: str) -> None:
    """Band wechseln. Globaler Korrekturwert bleibt — nur Kalibrier-Fenster
    leeren + Band fuers Logging merken."""
    global _band
    with _lock:
        _band = band
        _recent_samples.clear()


def get_time() -> float:
    """Hardware-korrigierte Zeit fuer den Slot-TAKT — ueberall statt time.time().

    Nutzt NUR die kalibrierte FT8-Basis ``_correction`` (Hardware-/Transport-
    Latenz + Uhr-Offset), bewusst OHNE den modus-abhaengigen ``_MODE_DELTA``:
    Der Cycle-Timer (``timing.py``) leitet daraus den Slot-Takt ab (u.a.
    OMNI-CQ-TX). Der Modus-Versatz ist ein RX-/Anzeige-Phaenomen und gehoert
    NICHT in den Sende-Takt (sonst Sende-Takt-Verdopplung, Field-Bug v0.98.63).
    TX-Timing selbst laeuft im Encoder ohnehin gegen reine ``time.time()``."""
    import time
    return time.time() + _correction


def get_correction() -> float:
    """Effektive Korrektur fuer den AKTUELLEN Modus in Sekunden.

    = kalibrierte FT8-Basis ``_correction`` + fester ``_MODE_DELTA[_mode]``.
    Auf FT8 identisch zur Basis (Delta 0); FT4/FT2 bekommen ihren Versatz.
    Wird vom RX-Decode-Shift (decoder) und der Anzeige genutzt — NICHT vom
    Slot-Takt (der laeuft ueber get_time() auf der reinen FT8-Basis)."""
    return _correction + _MODE_DELTA.get(_mode, 0.0)


def get_status_text() -> str:
    """Status-String fuer UI — zeigt die EFFEKTIVE Korrektur des aktuellen Modus."""
    eff = get_correction()
    if _is_initial and _correction == 0.0:
        return "DT-Korr: — (nicht kalibriert)"
    return (f"DT-Korr: {eff:+.2f}s "
            f"(letzter Slot: {_last_sample_count} St., "
            f"Median {_last_median_dt:+.2f}s)")


def record_samples(dt_values: list) -> None:
    """Pro Slot mit den DT-Werten aller dekodierten Stationen aufrufen.

    Puffert NUR (fuers spaetere ``calibrate()``) und aktualisiert die Anzeige-
    Werte — **kein automatisches Lernen mehr** (v0.99.0). Der Kalibrier-Puffer
    sammelt ausschliesslich FT8-Slots (nur FT8 wird kalibriert); die Anzeige-
    Werte (``_last_median_dt``/``_last_sample_count``) werden fuer ALLE Modi
    gesetzt (informativ — auf FT4/FT2 sieht man die Residuen des effektiven
    Modus-Versatzes).
    """
    global _last_median_dt, _last_sample_count
    valid = [dt for dt in dt_values if -2.0 <= dt <= 2.0]
    with _lock:
        if valid:
            _last_median_dt = statistics.median(valid)
            _last_sample_count = len(valid)
            if _mode == "FT8":
                _recent_samples.append(valid)
    if _DT_DEBUG and valid:
        print(f"[DT-DBG] {_mode}/{_band} n={len(valid)} "
              f"median={statistics.median(valid):+.3f} corr={_correction:+.3f} "
              f"buffered_slots={len(_recent_samples)}")


def calibrate() -> tuple[bool, str]:
    """Manuelle Einmal-Kalibrierung aus dem gleitenden FT8-Fenster.

    Nimmt alle gepufferten DT-Werte der letzten ``RECENT_SLOTS`` FT8-Slots,
    filtert Ausreisser (MAD), bildet den Median der Residuen und korrigiert
    INKREMENTELL: ``_correction += median`` (die Werte sind Residuen nach der
    aktuellen Korrektur — ein Klick konvergiert voll). Symmetrischer Clamp ±1.0
    (KEIN Negativ-Riegel: bei voreilender Uhr ist ein negativer Wert legitim).
    Speichert sofort.

    Nur sinnvoll auf FT8 (der Puffer enthaelt nur FT8-Slots) — der Aufrufer
    (``mw_radio._on_calibrate_dt``) prueft den Modus und meldet sonst.

    Returns ``(ok, meldung)`` fuer die Info-Zeile.
    """
    global _correction, _is_initial
    with _lock:
        samples = [dt for slot in _recent_samples for dt in slot]
        n = len(samples)
        if n < MIN_STATIONS:
            return (False,
                    f"DT-Kalibrierung: zu wenige FT8-Stationen ({n}) — mindestens "
                    f"{MIN_STATIONS} noetig. Kurz warten und nochmal druecken.")
        filtered = _filter_outliers_mad(samples)
        median_residual = statistics.median(filtered)
        _correction = max(-MAX_CORRECTION,
                          min(MAX_CORRECTION, _correction + median_residual))
        _is_initial = False
        _save_current()
        # Puffer NUR im Erfolgsfall leeren: die gerade verbrauchten Slots wurden
        # gegen die ALTE Korrektur gemessen — nach dem Anwenden sind sie veraltet.
        # Sonst würde ein erneuter Druck (bevor 3 neue Slots das Fenster spülen)
        # denselben Residuen-Median nochmal addieren → Wert klettert (Field-Bug
        # 03.06.2026). Der nächste Druck misst frisch gegen die neue Korrektur.
        _recent_samples.clear()
        print(f"[DT-Korr] Kalibriert: Median(Residuen)={median_residual:+.3f}s "
              f"aus {n} Stationen → {_correction:+.3f}s")
        return (True,
                f"DT kalibriert: {_correction:+.2f}s (aus {n} FT8-Stationen)")
