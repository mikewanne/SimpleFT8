"""SimpleFT8 Propagation — Bandbedingungen von HamQSL.com.

Strategie:
  XML von https://www.hamqsl.com/solarxml.php abrufen.
  Bereits enthält poor/fair/good pro Band für Tag UND Nacht.
  Zusätzlich: bandspezifische UTC-Tageszeit-Korrektur (Mitteleuropa)
  → ehrlicher als HAM-Toolbox weil Übergangsstunden abgebildet werden.

Mehrwert:
  HamQSL sagt "day: fair" für 80m — aber um 12 UTC ist 80m trotzdem schlecht.
  Unsere Tageszeit-Korrektur senkt die Bewertung in Übergangsstunden um 1 Stufe.

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
# Bandspezifische UTC-Tageszeit-Korrektur (Mitteleuropa-Faustregel)
# Format: (stunde_von, stunde_bis_exkl, "-1" | "normal")
# ─────────────────────────────────────────────────────────────────────────────
_TIME_CORRECTIONS: Dict[str, List[Tuple[int, int, str]]] = {
    "80m": [(0,  7, "normal"), (7,  20, "-1"), (20, 24, "normal")],
    "40m": [(0,  7, "normal"), (7,  19, "-1"), (19, 24, "normal")],
    "30m": [(0,  8, "-1"),     (8,  20, "normal"), (20, 24, "-1")],
    "20m": [(0,  9, "-1"),     (9,  20, "normal"), (20, 24, "-1")],
    "17m": [(0, 10, "-1"),     (10, 19, "normal"), (19, 24, "-1")],
    "15m": [(0, 10, "-1"),     (10, 19, "normal"), (19, 24, "-1")],
    "12m": [(0, 11, "-1"),     (11, 18, "normal"), (18, 24, "-1")],
    "10m": [(0, 11, "-1"),     (11, 18, "normal"), (18, 24, "-1")],
    # 60m: kein Eintrag → bleibt immer grey
}


def _step_down(condition: str) -> str:
    """Bedingung eine Stufe verschlechtern (good→fair, fair→poor, poor→poor)."""
    try:
        idx = _CONDITION_ORDER.index(condition.lower())
        return _CONDITION_ORDER[min(idx + 1, len(_CONDITION_ORDER) - 1)]
    except ValueError:
        return condition


def _apply_time_correction(band: str, condition: str, utc_hour: int) -> str:
    """UTC-Stunden-Korrektur für Band anwenden."""
    rules = _TIME_CORRECTIONS.get(band)
    if not rules:
        return condition
    for h_from, h_to, action in rules:
        if h_from <= utc_hour < h_to:
            return _step_down(condition) if action == "-1" else condition
    return condition


# ─────────────────────────────────────────────────────────────────────────────
# XML Abruf + Parsen
# ─────────────────────────────────────────────────────────────────────────────

def _fetch_and_parse() -> Optional[Dict[str, str]]:
    """HamQSL XML abrufen und in Bedingungen-Dict umwandeln.

    Returns:
        Dict mit Bandnamen → 'good'/'fair'/'poor'/'grey', oder None bei Fehler.
    """
    try:
        with urllib.request.urlopen(DATA_URL, timeout=FETCH_TIMEOUT) as resp:
            root = ET.fromstring(resp.read())
    except (urllib.error.URLError, urllib.error.HTTPError, ET.ParseError, OSError) as e:
        print(f"[Propagation] Fehler beim Abruf: {e}")
        return None

    utc_hour = datetime.now(timezone.utc).hour
    # HamQSL: "day" = 06-18 UTC (vereinfacht für globale Verwendung)
    time_of_day = "day" if 6 <= utc_hour < 18 else "night"

    conditions: Dict[str, str] = {b: "grey" for b in ALL_BANDS}

    # HamQSL: calculatedconditions ist unter solardata (rekursiv suchen)
    calc = root.find(".//calculatedconditions")
    if calc is None:
        return conditions

    for elem in calc.findall("band"):
        xml_name = elem.get("name", "")   # z.B. "80m-40m" oder "30m-20m"
        xml_time = elem.get("time", "")   # "day" oder "night"
        raw      = (elem.text or "").strip().lower()  # "good"/"fair"/"poor"

        if xml_time != time_of_day or raw not in _CONDITION_ORDER:
            continue

        # Band-Gruppe aufloesen: "80m-40m" → ["80m", "40m"]
        # HamQSL gruppiert: 80m-40m, 30m-20m, 17m-15m, 12m-10m
        parts = xml_name.split("-")
        if len(parts) == 2:
            # "80m-40m" → beide Bänder bekommen den gleichen Wert
            bands_in_group = _expand_band_range(parts[0], parts[1])
        else:
            bands_in_group = [xml_name]

        for band in bands_in_group:
            if band in XML_BANDS:
                conditions[band] = _apply_time_correction(band, raw, utc_hour)

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
_conditions: Optional[Dict[str, str]] = None   # None = noch nicht geladen / Fehler
_thread: Optional[threading.Thread] = None


def _run_updater() -> None:
    """Hintergrund-Thread: sofort abrufen, dann alle 3 Stunden wiederholen."""
    global _conditions
    while True:
        result = _fetch_and_parse()
        with _lock:
            _conditions = result  # None bei Fehler
        time.sleep(UPDATE_INTERVAL)


def start_background_updater() -> None:
    """Startet den Hintergrund-Thread (einmalig, idempotent)."""
    global _thread
    if _thread is not None and _thread.is_alive():
        return
    _thread = threading.Thread(target=_run_updater, daemon=True, name="PropUpdater")
    _thread.start()


def get_conditions() -> Optional[Dict[str, str]]:
    """Aktuelles Bedingungen-Dict oder None wenn kein Netzwerk / noch nicht geladen.

    None = Balken ausblenden.
    Dict mit 'good'/'fair'/'poor'/'grey' = Balken anzeigen.
    """
    with _lock:
        return dict(_conditions) if _conditions is not None else None


def get_color(band: str) -> str:
    """Hex-Farbe für ein Band. #555555 wenn keine Daten."""
    cond = (get_conditions() or {}).get(band, "grey")
    return COLORS.get(cond, "#555555")
