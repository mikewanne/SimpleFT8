#!/usr/bin/env python3
"""Build-Script fuer Coastline-Asset (assets/ne_110m_land_antimeridian_split.geojson).

Laedt Natural Earth 110m Land GeoJSON von github.com/nvkelso/natural-earth-vector,
splittet Polygon-Ringe an Antimeridian-Crossings und schreibt eine kompakte
JSON-Datei mit Liste-von-LineStrings raus. Nur einmalig auszufuehren — Output
wird ins Repo committet, das Karten-Widget liest die Datei zur Laufzeit.

Pure Python (urllib + json) — keine externen Dependencies. Damit kann jeder
Entwickler das Asset reproduzieren, ohne shapely/geopandas/etc. zu installieren.

Format des Outputs:
    {
        "type": "coastlines",
        "source": "Natural Earth 110m Land",
        "url": "...",
        "license": "Public Domain (Natural Earth)",
        "n_lines": int,
        "lines": [[[lon, lat], [lon, lat], ...], ...]
    }

Ausfuehren:
    cd SimpleFT8
    ./venv/bin/python3 tools/build_coastlines.py
"""

import json
import os
import sys
import urllib.request

URL = (
    "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/"
    "geojson/ne_110m_land.geojson"
)
OUT_REL = "assets/ne_110m_land_antimeridian_split.geojson"


def split_at_antimeridian(coords: list) -> list:
    """Polygon-Ring an Antimeridian-Crossings in mehrere LineStrings aufteilen.

    Heuristik: ein Sprung in lon um mehr als 180° ist physisch unmoeglich auf
    einem Großkreis und deutet auf einen Wrap am Antimeridian hin. Dort schneiden
    wir den Ring auf.

    Args:
        coords: Liste von [lon, lat]-Paaren (Polygon-Ring).
    Returns:
        Liste von LineStrings (jeder mit >= 2 Punkten).
    """
    if len(coords) < 2:
        return []
    lines = []
    current = [coords[0]]
    for i in range(1, len(coords)):
        prev_lon = coords[i - 1][0]
        cur_lon = coords[i][0]
        if abs(cur_lon - prev_lon) > 180.0:
            if len(current) >= 2:
                lines.append(current)
            current = [coords[i]]
        else:
            current.append(coords[i])
    if len(current) >= 2:
        lines.append(current)
    return lines


def main() -> int:
    print(f"Downloading {URL} …")
    try:
        with urllib.request.urlopen(URL, timeout=30) as resp:
            raw = resp.read()
    except Exception as e:
        print(f"FEHLER beim Download: {e}", file=sys.stderr)
        return 1

    print(f"  {len(raw):,} Bytes empfangen")
    data = json.loads(raw)

    if data.get("type") != "FeatureCollection":
        print(f"FEHLER: Unerwartetes GeoJSON-Format: {data.get('type')}", file=sys.stderr)
        return 1

    out_lines: list = []
    out_polygons: list = []  # Geschlossene Aussenringe fuer Land-Fill (Globus-Look)
    n_features = 0
    n_polygons = 0
    n_splits = 0

    for feature in data["features"]:
        geom = feature.get("geometry") or {}
        gtype = geom.get("type")
        if gtype == "Polygon":
            polys = [geom["coordinates"]]
        elif gtype == "MultiPolygon":
            polys = geom["coordinates"]
        else:
            continue
        n_features += 1
        for poly in polys:
            n_polygons += 1
            outer_ring = poly[0] if poly else []
            # Polygone mit Antimeridian-Crossing splittet das Build-Script in
            # mehrere Sub-Polygone — fuer Globus-Render alle-Punkte-sichtbar Filter
            poly_segments = split_at_antimeridian(outer_ring)
            for seg in poly_segments:
                # Ring schliessen falls noetig
                if len(seg) >= 3 and seg[0] != seg[-1]:
                    seg = seg + [seg[0]]
                if len(seg) >= 4:
                    out_polygons.append(seg)
            # Lines (Coastlines) auch raus geben: alle Ringe (outer + holes)
            for ring in poly:
                segments = split_at_antimeridian(ring)
                if len(segments) > 1:
                    n_splits += 1
                out_lines.extend(segments)

    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    out_path = os.path.join(repo_root, OUT_REL)
    out = {
        "type": "coastlines",
        "source": "Natural Earth 110m Land",
        "url": URL,
        "license": "Public Domain (Natural Earth)",
        "n_lines": len(out_lines),
        "n_polygons": len(out_polygons),
        "lines": out_lines,
        "polygons": out_polygons,
    }
    with open(out_path, "w") as f:
        json.dump(out, f, separators=(",", ":"))

    size = os.path.getsize(out_path)
    print(f"  Features verarbeitet:   {n_features}")
    print(f"  Polygone insgesamt:     {n_polygons}")
    print(f"  Ringe mit AM-Split:     {n_splits}")
    print(f"  LineStrings im Output:  {len(out_lines)}")
    print(f"  Polygone (Land-Fill):   {len(out_polygons)}")
    print(f"  Output: {out_path}  ({size:,} Bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
