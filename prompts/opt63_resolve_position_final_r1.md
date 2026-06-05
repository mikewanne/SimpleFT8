# OPT-63 Final-R1 (Bestätigungspass auf den fertigen Diff)

Du gabst in R1 GO für den `_resolve_station_position`-Helfer. Hier der UMGESETZTE
Diff. Bitte NUR prüfen: plan-konform + verhaltensneutral? Knapp: PUSH FREIGEBEN
oder NICHT (Grund).

## Umgesetzt
- Helfer `_resolve_station_position(call, fallback_loc, locator_db, locator_cache)`
  in `ui/direction_map_widget.py` (wie in R1 abgesegnet).
- `snapshot_to_station_points`: DB-/Fallback-Block (24 Z.) → 7-Z. Helfer-Aufruf
  mit `fallback_loc = data.get("locator") or locator_cache.get(call)`, cache übergeben.
- `entries_to_station_points`: gleicher Block → Helfer-Aufruf mit
  `fallback_loc = getattr(e, "locator", None)`, OHNE cache.
- Rescue-Klassifikation, band, StationPoint-Bau unverändert.
- pyflakes sauber (keine toten `pos`/`entry`/`latlon`-Locals), AST OK.

## Tests
Volle Suite **2461 passed** (2453 → +8 neuer `test_resolve_station_position.py`:
DB-Treffer-kein-cache-update, leeres entry→loc="", DB-None-durchfallen, Fallback
4-/6-stellig prec 110/5, cache-Update, cache=None-kein-Crash, None/ungültig→None).
Die 6 bestehenden `snapshot_to_points`-Tests (skip/cache/explicit-caches/mobile/
rescue) weiter grün.

## Fragen
1. Diff verhaltensneutral + plan-konform?
2. Etwas übersehen? Sonst: PUSH FREIGEBEN.

---
## DIFF
diff --git a/ui/direction_map_widget.py b/ui/direction_map_widget.py
index fec8492..d5f34f0 100644
--- a/ui/direction_map_widget.py
+++ b/ui/direction_map_widget.py
@@ -192,6 +192,34 @@ class LocatorCache:
         self._cache.clear()
 
 
+def _resolve_station_position(call, fallback_loc, locator_db=None, locator_cache=None):
+    """Position (lat, lon, prec_km, locator) einer Station auflösen (OPT-63 DRY).
+
+    Reihenfolge:
+      1. locator_db.get_position(call) — persistent, mit prec_km (wenn db gegeben)
+      2. fallback_loc → safe_locator_to_latlon; prec_km = 5 (6-stellig) / 110 (sonst)
+    locator_cache (optional): wird NUR bei Fallback-Treffer aktualisiert (nicht bei
+    DB-Treffer). Returns (lat, lon, prec_km, loc) oder None wenn nicht auflösbar.
+    """
+    if locator_db is not None:
+        pos = locator_db.get_position(call)
+        if pos is not None:
+            lat, lon, prec_km = pos
+            entry = locator_db.get(call)
+            return lat, lon, prec_km, (entry.locator if entry else "")
+    loc = fallback_loc or ""
+    if loc and locator_cache is not None:
+        locator_cache.update(call, loc)
+    if not loc:
+        return None
+    latlon = safe_locator_to_latlon(loc)
+    if latlon is None:
+        return None
+    lat, lon = latlon
+    prec_km = 5 if len(loc) >= 6 else 110
+    return lat, lon, prec_km, loc
+
+
 def snapshot_to_station_points(
     snapshot: dict,
     locator_cache: LocatorCache,
@@ -221,30 +249,14 @@ def snapshot_to_station_points(
         if is_mobile(call):
             continue
 
-        # 1) DB-Lookup (priorisiert, mit Genauigkeitsangabe)
-        lat = lon = None
-        prec_km = 110
-        loc = ""
-        if locator_db is not None:
-            pos = locator_db.get_position(call)
-            if pos is not None:
-                lat, lon, prec_km = pos
-                entry = locator_db.get(call)
-                loc = entry.locator if entry else ""
-
-        # 2) Fallback: Snapshot-Feld + Session-Cache
-        if lat is None:
-            loc = data.get("locator") or locator_cache.get(call) or ""
-            if loc:
-                locator_cache.update(call, loc)
-            if not loc:
-                continue
-            latlon = safe_locator_to_latlon(loc)
-            if latlon is None:
-                continue
-            lat, lon = latlon
-            # 6-stellig=5km, 4-stellig=110km
-            prec_km = 5 if len(loc) >= 6 else 110
+        # Position auflösen: DB (priorisiert, mit Genauigkeit) → Snapshot-Feld /
+        # Session-Cache → safe_locator_to_latlon (siehe _resolve_station_position).
+        resolved = _resolve_station_position(
+            call, data.get("locator") or locator_cache.get(call),
+            locator_db=locator_db, locator_cache=locator_cache)
+        if resolved is None:
+            continue
+        lat, lon, prec_km, loc = resolved
 
         # Rescue-Klassifikation (Antenna)
         snr_a1 = data.get("snr_a1")
@@ -286,24 +298,11 @@ def entries_to_station_points(
         if not call or is_mobile(call):
             continue
 
-        lat = lon = None
-        prec_km = 110
-        loc = ""
-        if locator_db is not None:
-            pos = locator_db.get_position(call)
-            if pos is not None:
-                lat, lon, prec_km = pos
-                ent = locator_db.get(call)
-                loc = ent.locator if ent else ""
-        if lat is None:
-            loc = getattr(e, "locator", None) or ""
-            if not loc:
-                continue
-            latlon = safe_locator_to_latlon(loc)
-            if latlon is None:
-                continue
-            lat, lon = latlon
-            prec_km = 5 if len(loc) >= 6 else 110
+        resolved = _resolve_station_position(
+            call, getattr(e, "locator", None), locator_db=locator_db)
+        if resolved is None:
+            continue
+        lat, lon, prec_km, loc = resolved
 
         points.append(StationPoint(
             call=call,
