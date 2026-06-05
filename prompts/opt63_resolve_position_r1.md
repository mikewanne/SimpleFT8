# OPT-63 (K3) Review-Anfrage (R1) — KISS: `_resolve_station_position()`-Helfer

## Kontext
Autonome Optimierungs-Kampagne. NUR Optimierung, **keine Verhaltensänderung**, KISS.
`ui/direction_map_widget.py`: Karten-Stations-Punkte. Kein TX-Pfad (reine Anzeige),
ANT1=TX unberührt.

## Befund (verifiziert)
Zwei Modul-Funktionen lösen Stations-Position fast identisch auf (DB → Fallback-
Locator → `safe_locator_to_latlon` → prec_km). Unterschiede: (a) Fallback-Quelle,
(b) nur `snapshot_to_station_points` aktualisiert den `locator_cache`.

### IST — `snapshot_to_station_points` (Kern):
```python
lat = lon = None
prec_km = 110
loc = ""
if locator_db is not None:
    pos = locator_db.get_position(call)
    if pos is not None:
        lat, lon, prec_km = pos
        entry = locator_db.get(call)
        loc = entry.locator if entry else ""
if lat is None:
    loc = data.get("locator") or locator_cache.get(call) or ""
    if loc:
        locator_cache.update(call, loc)
    if not loc:
        continue
    latlon = safe_locator_to_latlon(loc)
    if latlon is None:
        continue
    lat, lon = latlon
    prec_km = 5 if len(loc) >= 6 else 110
# ... danach: rescue-Antenna-Klassifikation + StationPoint(...) mit band
```

### IST — `entries_to_station_points` (Kern):
```python
lat = lon = None
prec_km = 110
loc = ""
if locator_db is not None:
    pos = locator_db.get_position(call)
    if pos is not None:
        lat, lon, prec_km = pos
        ent = locator_db.get(call)
        loc = ent.locator if ent else ""
if lat is None:
    loc = getattr(e, "locator", None) or ""
    if not loc:
        continue
    latlon = safe_locator_to_latlon(loc)
    if latlon is None:
        continue
    lat, lon = latlon
    prec_km = 5 if len(loc) >= 6 else 110
# ... danach: StationPoint(...) OHNE band, OHNE rescue
```
(entries macht KEIN locator_cache.update — hat keinen cache-Parameter.)

## V3-Kandidat — Helfer (Modul-Funktion, vor snapshot_to_station_points)
```python
def _resolve_station_position(call, fallback_loc, locator_db=None, locator_cache=None):
    """Position (lat, lon, prec_km, locator) einer Station auflösen.

    Reihenfolge:
      1. locator_db.get_position(call) — persistent, mit prec_km (wenn db gegeben)
      2. fallback_loc → safe_locator_to_latlon; prec_km = 5 (6-stellig) / 110 (sonst)
    locator_cache (optional): wird NUR bei Fallback-Treffer aktualisiert.
    Returns (lat, lon, prec_km, loc) oder None wenn nicht auflösbar.
    """
    if locator_db is not None:
        pos = locator_db.get_position(call)
        if pos is not None:
            lat, lon, prec_km = pos
            entry = locator_db.get(call)
            return lat, lon, prec_km, (entry.locator if entry else "")
    loc = fallback_loc or ""
    if loc and locator_cache is not None:
        locator_cache.update(call, loc)
    if not loc:
        return None
    latlon = safe_locator_to_latlon(loc)
    if latlon is None:
        return None
    lat, lon = latlon
    prec_km = 5 if len(loc) >= 6 else 110
    return lat, lon, prec_km, loc
```

### Aufrufer snapshot:
```python
resolved = _resolve_station_position(
    call, data.get("locator") or locator_cache.get(call),
    locator_db=locator_db, locator_cache=locator_cache)
if resolved is None:
    continue
lat, lon, prec_km, loc = resolved
```
### Aufrufer entries:
```python
resolved = _resolve_station_position(
    call, getattr(e, "locator", None), locator_db=locator_db)
if resolved is None:
    continue
lat, lon, prec_km, loc = resolved
```
Die `is_mobile`-Filter, Rescue-Klassifikation, StationPoint-Konstruktion bleiben
unverändert in den jeweiligen Funktionen.

## Fragen
1. **Verhaltensgleichheit** beider Aufrufer? Kritisch: (a) cache.update NUR bei
   Fallback-Treffer, nicht bei DB-Treffer (Helfer returnt vor dem cache-Block) —
   korrekt? (b) `data.get("locator") or locator_cache.get(call)` vor dem Helfer
   berechnen = identisch zum Inline-`... or ""`? (c) DB gegeben aber get_position
   = None → fällt korrekt zum Fallback durch?
2. **Rückgabe-Form** 4-Tuple + None — KISS-OK oder NamedTuple sinnvoller (ohne
   Overengineering)?
3. **Scope**: nur den Auflösungs-Block extrahieren, Rest in den Funktionen lassen —
   richtig abgegrenzt?
4. Etwas übersehen? Sonst GO/NO-GO.

Knapp + konkret. Code ist Referenz.
