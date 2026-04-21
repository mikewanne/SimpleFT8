"""SimpleFT8 Propagation — Bandbedingungen von HamQSL.com.

Strategie:
  XML von https://www.hamqsl.com/solarxml.php abrufen.
  Bereits enthält poor/fair/good pro Band für Tag UND Nacht.
  Zusätzlich: jahreszeitabhängige Öffnungsfenster pro Band (Mitteleuropa 48°N)
  → ehrlicher als HAM-Toolbox (pauschale 06-18 UTC Tag/Nacht).

Mehrwert:
  HamQSL sagt "fair" für 20m um 07 UTC — aber im Winter ist 20m erst ab 06 UTC offen.
  10m/12m/15m im Winter: praktisch tot → immer poor unabhängig von HamQSL.
  Nachtbänder (40m/80m): nur innerhalb des echten Nacht-Öffnungsfensters bewertet.

Keine API-Keys. Kein Login. Kein externer Service außer HamQSL.
Bei Netzwerkfehler: None zurück, Balken unsichtbar.
"""

import threading
import time
import xml.etree.ElementTree as ET
import urllib.request
import urllib.error
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

# ─────────────────────────────────────────────────────────────────────────────
DATA_URL         = "https://www.hamqsl.com/solarxml.php"
UPDATE_INTERVAL  = 3 * 60 * 60   # 3 Stunden
FETCH_TIMEOUT    = 10             # Sekunden

ALL_BANDS   = ["10m", "12m", "15m", "17m", "20m", "30m", "40m", "60m", "80m"]
XML_BANDS   = ["10m", "12m", "15m", "17m", "20m", "30m", "40m", "80m"]  # 60m fehlt in XML

# Stufenregel: good→fair, fair→poor, poor→poor
_CONDITION_ORDER = ["good", "fair", "poor"]

# Farben
COLORS: Dict[str, str] = {
    "good":    "#00CC00",
    "fair":    "#FFAA00",
    "poor":    "#CC0000",
    "grey":    "#555555",
    "loading": "#555555",
}

# ─────────────────────────────────────────────────────────────────────────────
# Jahreszeitabhängige Band-Öffnungsfenster (Mitteleuropa 48°N, UTC)
# Quelle: Funkpraxis + DeepSeek-Analyse (April 2026)
#
# Format: (open_utc, close_utc, is_na)
#   open_utc  — ab dieser Stunde ist DX möglich ("fair" nutzbar)
#   close_utc — ab dieser Stunde geschlossen (wieder poor)
#   is_na     — True = Band in dieser Jahreszeit praktisch tot (immer poor)
#
# Nachtbänder (40m, 80m): close_utc < open_utc = Mitternachts-Übergang
# Außerhalb des Fensters → immer "poor", unabhängig von HamQSL-Wert.
# Innerhalb → HamQSL-Wert unverändert (kein Boosting).
# ─────────────────────────────────────────────────────────────────────────────
_SEASONAL_SCHEDULE: Dict[str, Dict[str, tuple]] = {
    "winter": {  # Dez, Jan, Feb
        "10m": (None, None, True),   # Band tot (kein F2-DX)
        "12m": (None, None, True),   # Band tot
        "15m": (None, None, True),   # Band tot (gelegentlich, aber nicht verlässlich)
        "17m": (8,  16, False),      # 08:00–16:00
        "20m": (6,  18, False),      # 06:00–18:00
        "30m": (4,  20, False),      # 04:00–20:00
        "40m": (14,  7, False),      # 14:00–07:00 (Nachtband, Mitternachts-Übergang)
        "80m": (16,  8, False),      # 16:00–08:00 (Nachtband)
    },
    "spring": {  # Mär, Apr, Mai
        "10m": (9,  17, False),      # ~09:00–17:00
        "12m": (8,  18, False),      # ~08:00–18:00
        "15m": (7,  20, False),      # 07:00–20:00
        "17m": (6,  21, False),      # 06:00–21:00
        "20m": (5,  22, False),      # 05:00–22:00
        "30m": (3,  23, False),      # 03:00–23:00
        "40m": (15,  8, False),      # 15:00–08:00 (Nachtband)
        "80m": (17,  7, False),      # 17:00–07:00 (Nachtband)
    },
    "summer": {  # Jun, Jul, Aug
        "10m": (8,  19, False),      # 08:00–19:00
        "12m": (7,  20, False),      # 07:00–20:00
        "15m": (6,  22, False),      # 06:00–22:00
        "17m": (5,  23, False),      # 05:00–23:00
        "20m": (4,  24, False),      # 04:00–24:00 (praktisch ganztags offen)
        "30m": (2,  24, False),      # 02:00–24:00 (fast 24h)
        "40m": (16,  5, False),      # 16:00–05:00 (kürzere Nacht im Sommer)
        "80m": (18,  4, False),      # 18:00–04:00
    },
    "autumn": {  # Sep, Okt, Nov
        "10m": (9,  16, False),      # ~09:00–16:00
        "12m": (8,  17, False),      # ~08:00–17:00
        "15m": (7,  19, False),      # 07:00–19:00
        "17m": (6,  20, False),      # 06:00–20:00
        "20m": (5,  21, False),      # 05:00–21:00
        "30m": (3,  22, False),      # 03:00–22:00
        "40m": (14,  8, False),      # 14:00–08:00 (Nachtband)
        "80m": (16,  8, False),      # 16:00–08:00
    },
}


def _get_season(month: int) -> str:
    if month in (12, 1, 2):
        return "winter"
    if month in (3, 4, 5):
        return "spring"
    if month in (6, 7, 8):
        return "summer"
    return "autumn"


def _apply_seasonal_correction(band: str, condition: str,
                                utc_hour: int, month: int) -> str:
    """Jahreszeitabhängige Band-Öffnungskorrektur.

    Außerhalb des Öffnungsfensters → "poor".
    Innerhalb → HamQSL-Wert unverändert (kein Boosting).
    N/A-Band (is_na=True) → immer "poor".
    """
    season = _get_season(month)
    entry = _SEASONAL_SCHEDULE.get(season, {}).get(band)
    if entry is None:
        return condition  # 60m o.ä. → unverändert

    open_h, close_h, is_na = entry

    if is_na:
        return "poor"

    # Nachtband: close_h < open_h → Mitternachts-Übergang
    if close_h < open_h:
        is_open = (utc_hour >= open_h) or (utc_hour < close_h)
    else:
        is_open = (open_h <= utc_hour < close_h)

    return condition if is_open else "poor"


# ─────────────────────────────────────────────────────────────────────────────
# XML Abruf + Parsen
# ─────────────────────────────────────────────────────────────────────────────

def _fetch_raw() -> Optional[Dict[str, Dict[str, str]]]:
    """HamQSL XML abrufen und ROHDATEN speichern (ohne Zeitkorrektur).

    Returns:
        Dict mit Bandnamen → {"day": condition, "night": condition}, oder None.
    """
    try:
        with urllib.request.urlopen(DATA_URL, timeout=FETCH_TIMEOUT) as resp:
            root = ET.fromstring(resp.read())
    except (urllib.error.URLError, urllib.error.HTTPError, ET.ParseError, OSError) as e:
        print(f"[Propagation] Fehler beim Abruf: {e}")
        return None

    raw_data: Dict[str, Dict[str, str]] = {b: {"day": "grey", "night": "grey"} for b in ALL_BANDS}

    calc = root.find(".//calculatedconditions")
    if calc is None:
        return raw_data

    for elem in calc.findall("band"):
        xml_name = elem.get("name", "")
        xml_time = elem.get("time", "")
        raw      = (elem.text or "").strip().lower()

        if xml_time not in ("day", "night") or raw not in _CONDITION_ORDER:
            continue

        parts = xml_name.split("-")
        if len(parts) == 2:
            bands_in_group = _expand_band_range(parts[0], parts[1])
        else:
            bands_in_group = [xml_name]

        for band in bands_in_group:
            if band in XML_BANDS:
                raw_data[band][xml_time] = raw

    # 60m fehlt in XML → Mittelwert aus 40m+80m; Fallback: nur einer → diesen; keiner → grey
    for time_key in ("day", "night"):
        vals = [
            raw_data[b][time_key]
            for b in ("40m", "80m")
            if raw_data[b][time_key] in _CONDITION_ORDER
        ]
        if vals:
            avg_idx = round(sum(_CONDITION_ORDER.index(v) for v in vals) / len(vals))
            raw_data["60m"][time_key] = _CONDITION_ORDER[max(0, min(avg_idx, 2))]

    print(f"[Propagation] Daten aktualisiert (UTC {datetime.now(timezone.utc).strftime('%H:%M')})")
    return raw_data


def _evaluate_conditions(raw_data: Dict[str, Dict[str, str]]) -> Dict[str, str]:
    """Rohdaten MIT aktueller UTC-Stunde auswerten (Zeitkorrektur bei jedem Aufruf)."""
    now = datetime.now(timezone.utc)
    utc_hour = now.hour
    month = now.month
    time_of_day = "day" if 6 <= utc_hour < 18 else "night"

    conditions: Dict[str, str] = {}
    for band in ALL_BANDS:
        band_data = raw_data.get(band, {"day": "grey", "night": "grey"})
        base_condition = band_data.get(time_of_day, "grey")
        conditions[band] = _apply_seasonal_correction(band, base_condition, utc_hour, month)

    return conditions


def _expand_band_range(band_from: str, band_to: str) -> list:
    """Band-Bereich aufloesen: '80m','40m' → ['80m','60m','40m']."""
    # Alle Baender in absteigender Wellenlaenge
    _ALL_ORDERED = ["160m", "80m", "60m", "40m", "30m", "20m", "17m", "15m", "12m", "10m"]
    try:
        idx_from = _ALL_ORDERED.index(band_from)
        idx_to = _ALL_ORDERED.index(band_to)
        if idx_from > idx_to:
            idx_from, idx_to = idx_to, idx_from
        return _ALL_ORDERED[idx_from:idx_to + 1]
    except ValueError:
        return [band_from, band_to]


# ─────────────────────────────────────────────────────────────────────────────
# Globaler Zustand + Hintergrund-Thread
# ─────────────────────────────────────────────────────────────────────────────

_lock       = threading.Lock()
_raw_data: Optional[Dict[str, Dict[str, str]]] = None  # Rohdaten (day/night pro Band)
_thread: Optional[threading.Thread] = None


def _run_updater() -> None:
    """Hintergrund-Thread: sofort abrufen, dann alle 3 Stunden wiederholen."""
    global _raw_data
    while True:
        result = _fetch_raw()
        with _lock:
            _raw_data = result
        time.sleep(UPDATE_INTERVAL)


def start_background_updater() -> None:
    """Startet den Hintergrund-Thread (einmalig, idempotent)."""
    global _thread
    if _thread is not None and _thread.is_alive():
        return
    _thread = threading.Thread(target=_run_updater, daemon=True, name="PropUpdater")
    _thread.start()


def get_conditions() -> Optional[Dict[str, str]]:
    """Aktuelles Bedingungen-Dict MIT Live-Zeitkorrektur.

    Zeitkorrektur wird bei JEDEM Aufruf neu berechnet — nicht gecacht.
    None = Balken ausblenden.
    """
    with _lock:
        raw = dict(_raw_data) if _raw_data is not None else None
    if raw is None:
        return None
    return _evaluate_conditions(raw)


def get_color(band: str) -> str:
    """Hex-Farbe für ein Band. #555555 wenn keine Daten."""
    cond = (get_conditions() or {}).get(band, "grey")
    return COLORS.get(cond, "#555555")
