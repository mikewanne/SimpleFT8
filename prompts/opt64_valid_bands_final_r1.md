# OPT-64 Final-R1 (Bestätigungspass auf den fertigen Diff)

Du gabst R1 GO + empfahlst Variante A als **Modul-Funktion** (statt Instanz-
Methode). Hier der umgesetzte Diff. Bitte NUR prüfen: plan-konform +
verhaltensneutral (im Betrieb)? Knapp: PUSH FREIGEBEN oder NICHT.

## Umgesetzt (wie in R1 abgesegnet)
- Modul-Funktion `_valid_bands(raw)` in `config/settings.py` (bei den anderen
  Modul-Funktionen, vor DEFAULTS) — Variante A mit isinstance-Check im Helfer.
- `get_enabled_bands` → `return _valid_bands(self._data.get("enabled_bands"))`.
- `set_enabled_bands` → `self._data["enabled_bands"] = _valid_bands(bands)`.
- Reihenfolge-Erhalt (append-Loop) + Dedup (`seen`) + Fallback
  (`valid or list(BAND_FREQUENCIES.keys())`) wie Original.

## Tests
Volle Suite **2469 passed** (2461 → +8 neuer `test_valid_bands.py`: None/non-list/
leer/nur-Garbage → Default; Reihenfolge-Erhalt; Dedup-erstes-Vorkommen; gemischt
filtert Garbage; all-roundtrip). Die 11 bestehenden `test_p50_bands_visibility`-
Tests (T1-T11 inkl. set-garbage-fallback) weiter grün. pyflakes sauber, AST OK.

## Fragen
1. Diff plan-konform + im Betrieb verhaltensneutral (einziger Unterschied
   `set(None)`→Default tritt nie auf)?
2. Etwas übersehen? Sonst: PUSH FREIGEBEN.

---
## DIFF
diff --git a/config/settings.py b/config/settings.py
index b9abb3f..5263270 100755
--- a/config/settings.py
+++ b/config/settings.py
@@ -49,6 +49,25 @@ def get_tune_freq_mhz(band: str, mode: str) -> float | None:
         m = "FT8"
     return TUNE_FREQS.get(f"{band}_{m}")
 
+
+def _valid_bands(raw) -> list[str]:
+    """Rohe Band-Liste defensiv validieren (OPT-64, DRY für get_/set_enabled_bands).
+
+    Nur Strings die in ``BAND_FREQUENCIES`` sind, dedupliziert (Reihenfolge des
+    ersten Auftretens erhalten). Bei nicht-Liste ODER leerem Ergebnis → Default
+    (alle Bänder).
+    """
+    if not isinstance(raw, list):
+        return list(BAND_FREQUENCIES.keys())
+    valid: list[str] = []
+    seen: set[str] = set()
+    for b in raw:
+        if isinstance(b, str) and b in BAND_FREQUENCIES and b not in seen:
+            valid.append(b)
+            seen.add(b)
+    return valid or list(BAND_FREQUENCIES.keys())
+
+
 DEFAULTS = {
     "callsign": "DA1MHH",
     "locator": "JO31",
@@ -260,18 +279,7 @@ class Settings:
         Einträge (kein String, nicht in ``BAND_FREQUENCIES``, Duplikate).
         Bei leerer/komplett-ungültiger Liste → Fallback auf Default.
         """
-        raw = self._data.get("enabled_bands")
-        if not isinstance(raw, list):
-            return list(BAND_FREQUENCIES.keys())
-        valid: list[str] = []
-        seen: set[str] = set()
-        for b in raw:
-            if isinstance(b, str) and b in BAND_FREQUENCIES and b not in seen:
-                valid.append(b)
-                seen.add(b)
-        if not valid:
-            return list(BAND_FREQUENCIES.keys())
-        return valid
+        return _valid_bands(self._data.get("enabled_bands"))
 
     def set_enabled_bands(self, bands: list[str]) -> None:
         """Setzt die Liste der sichtbaren Bänder.
@@ -280,15 +288,7 @@ class Settings:
         resultierender Liste → Default (alle 9). Persistiert NICHT
         automatisch — Caller ruft ``save()``.
         """
-        valid: list[str] = []
-        seen: set[str] = set()
-        for b in bands:
-            if isinstance(b, str) and b in BAND_FREQUENCIES and b not in seen:
-                valid.append(b)
-                seen.add(b)
-        if not valid:
-            valid = list(BAND_FREQUENCIES.keys())
-        self._data["enabled_bands"] = valid
+        self._data["enabled_bands"] = _valid_bands(bands)
 
     @property
     def callsign(self):
