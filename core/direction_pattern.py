"""SimpleFT8 Direction Pattern — Sektor-Aggregation fuer Richtungs-Karte.

Pure Funktionen + Datenklassen. Keine Qt-Abhaengigkeit, keine I/O.
Nutzt core/geo fuer Bearing-Berechnung. Wird vom Karten-Widget aufgerufen,
um eine Snapshot-Liste von Stationen in 16 Sektoren à 22.5° zu aggregieren.

Datenfluss:
    raw stations (RX/TX-Quelle) → list[StationPoint] → aggregate_sectors() →
    list[SectorBucket] → Wedges im paintEvent

Mobile-Filter: Calls mit Suffix wie /P /MM /AM /QRP haben keinen stationaeren
Locator und werden ausgeschlossen (kein Mapping-Sinn).
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field

from core.geo import great_circle_bearing


SECTOR_COUNT = 16
SECTOR_WIDTH_DEG = 360.0 / SECTOR_COUNT  # 22.5°

# Mobile/Maritime/QRP-Suffixe — Stationen mit nicht-stationaerem Locator.
# Regex matcht ein "/" gefolgt von 1-4 alphanum-Zeichen am Call-Ende.
_MOBILE_RE = re.compile(r"/[A-Z0-9]{1,4}$")


@dataclass
class StationPoint:
    """Ein Punkt auf der Karte (eine Station an ihrer geo. Position)."""
    call: str
    locator: str
    lat: float
    lon: float
    snr: float
    antenna: str = ""        # "A1" | "A2" | "rescue" (RX) | "" (TX)
    timestamp: float = 0.0
    band: str = ""
    distance_km: float = 0.0
    prec_km: int = 110       # Lokalisierungs-Genauigkeit; 5=6-stellig, 110=Country/4-stellig


@dataclass
class SectorBucket:
    """Ein Sektor (22.5°-Keule) mit Aktivitaets-Statistik."""
    index: int               # 0..15, 0 = Norden
    count: int = 0           # unique calls in Sektor
    avg_snr: float = 0.0
    ant1_count: int = 0
    ant2_count: int = 0
    rescue_count: int = 0
    last_update: float = 0.0
    max_distance_km: float = 0.0  # max distance_km der deduplizierten Stations
    _calls: set = field(default_factory=set, repr=False)
    _snr_sum: float = field(default=0.0, repr=False)


def is_mobile(call: str) -> bool:
    """Call-Suffix /P, /MM, /AM, /QRP, /M etc. → mobile/portable.

    Hinweis: einige Suffixe wie /W2 sind Region-Indikatoren, kein Mobile-Marker.
    Der Filter ist absichtlich grob — fuer Karten-Darstellung lieber zu viel
    filtern als hin und wieder einen mobilen Locator falsch zu plotten.
    Stationaere Region-Calls (z.B. K1ABC/W2) gehen damit auch raus, das ist
    akzeptabel: in der Statistik werden sie weiter gezaehlt, nur nicht gemapt.
    """
    if not call:
        return False
    return bool(_MOBILE_RE.search(call.upper().strip()))


def sector_index(bearing_deg: float) -> int:
    """Sektor-Bin (0..15) fuer ein gegebenes Bearing.

    0 = Norden (337.5–22.5°), 1 = NNE (22.5–45°) ... 15 = NNW (315–337.5°).
    Sektor-0 wrappt um den Antimeridian-Aequivalent (337.5° und 0° sind im
    selben Bin).

    Bearing-Range: [0, 360). Werte ausserhalb werden via Modulo normalisiert.
    """
    # +SECTOR_WIDTH/2 verschiebt so, dass Sektor 0 um 0° (Norden) zentriert ist
    shifted = (bearing_deg + SECTOR_WIDTH_DEG / 2.0) % 360.0
    return int(shifted / SECTOR_WIDTH_DEG) % SECTOR_COUNT


def aggregate_sectors(
    stations: list[StationPoint],
    my_lat: float,
    my_lon: float,
) -> list[SectorBucket]:
    """Stationen in 16 Sektoren binnen.

    Call-Dedup: gleiche Station mehrfach in der Liste → 1× pro Sektor gezaehlt
    (erste Sichtung gewinnt). Antennen-Counter zaehlen entsprechend nur die
    erste Sichtung — wenn der Aufrufer zwei Eintraege mit unterschiedlichem
    `antenna`-Feld fuer dieselbe Station schickt, wird nur das erste gezaehlt.
    Das ist intentional: eine Station hat zu einem Zeitpunkt EINE beste Antenne
    (siehe AntennaPreferenceStore), nicht mehrere parallel.

    Defense-in-Depth: Stationen mit nicht-finiten lat/lon (NaN/Inf, z.B. aus
    korrupten externen Daten) werden silent geskippt — sonst wuerden sie alle
    in Sektor 0 landen.

    Args:
        stations: Liste von StationPoint (kann Duplikate enthalten — wird
            pro Sektor dedupliziert).
        my_lat, my_lon: Karten-Center fuer Bearing-Berechnung.
    Returns:
        Genau 16 SectorBucket-Objekte (auch leere). Reihenfolge nach index.
    """
    buckets = [SectorBucket(index=i) for i in range(SECTOR_COUNT)]

    for s in stations:
        if not (math.isfinite(s.lat) and math.isfinite(s.lon)):
            continue  # NaN/Inf abwerfen statt in Sektor 0 zu landen
        bearing = great_circle_bearing(my_lat, my_lon, s.lat, s.lon)
        idx = sector_index(bearing)
        b = buckets[idx]
        if s.call in b._calls:
            continue  # Call-Dedup pro Sektor
        b._calls.add(s.call)
        b.count += 1
        b._snr_sum += s.snr
        if s.timestamp > b.last_update:
            b.last_update = s.timestamp
        # NaN/Inf-Guard: max() ueber NaN propagiert NaN durchs paintEvent
        if math.isfinite(s.distance_km) and s.distance_km > b.max_distance_km:
            b.max_distance_km = s.distance_km
        if s.antenna == "A1":
            b.ant1_count += 1
        elif s.antenna == "A2":
            b.ant2_count += 1
        elif s.antenna == "rescue":
            b.rescue_count += 1

    for b in buckets:
        if b.count > 0:
            b.avg_snr = b._snr_sum / b.count

    return buckets
