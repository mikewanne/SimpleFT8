# OPT-64 (K4) Review-Anfrage (R1) — KISS: `_valid_bands(raw)`-Helfer

## Kontext
Autonome Optimierungs-Kampagne. NUR Optimierung, **keine (observierbare)
Verhaltensänderung**, KISS. `config/settings.py`. Kein TX-Pfad (reine
Settings-Logik), ANT1=TX unberührt.

## Befund (verifiziert)
`get_enabled_bands` + `set_enabled_bands` enthalten dieselbe Band-Validierung
(Filter auf Strings die in `BAND_FREQUENCIES` sind, dedupliziert mit
Reihenfolge-Erhalt, Fallback Default bei leer) → privater Helfer `_valid_bands`.

### IST — get_enabled_bands:
```python
raw = self._data.get("enabled_bands")
if not isinstance(raw, list):
    return list(BAND_FREQUENCIES.keys())
valid: list[str] = []
seen: set[str] = set()
for b in raw:
    if isinstance(b, str) and b in BAND_FREQUENCIES and b not in seen:
        valid.append(b)
        seen.add(b)
if not valid:
    return list(BAND_FREQUENCIES.keys())
return valid
```
### IST — set_enabled_bands:
```python
valid: list[str] = []
seen: set[str] = set()
for b in bands:                      # ← KEIN isinstance(bands, list)-Check!
    if isinstance(b, str) and b in BAND_FREQUENCIES and b not in seen:
        valid.append(b)
        seen.add(b)
if not valid:
    valid = list(BAND_FREQUENCIES.keys())
self._data["enabled_bands"] = valid
```

## Verifizierte Fakten
- Einziger App-Aufrufer: `ui/settings_dialog.py:860` `set_enabled_bands(enabled_bands)`
  (echte Liste aus Checkboxen).
- Test T11 (`test_p50_bands_visibility.py`): `set_enabled_bands(["junk", None, 42])`
  → Default (Liste MIT Garbage-Elementen, KEIN non-list-Input).
- KEIN Aufrufer/Test übergibt `None`/String (non-list) an `set`.

## Zwei Varianten

### Variante A — voller Helfer (isinstance-Check IM Helfer):
```python
def _valid_bands(self, raw) -> list[str]:
    if not isinstance(raw, list):
        return list(BAND_FREQUENCIES.keys())
    valid: list[str] = []
    seen: set[str] = set()
    for b in raw:
        if isinstance(b, str) and b in BAND_FREQUENCIES and b not in seen:
            valid.append(b); seen.add(b)
    return valid or list(BAND_FREQUENCIES.keys())

def get_enabled_bands(self):
    return self._valid_bands(self._data.get("enabled_bands"))

def set_enabled_bands(self, bands):
    self._data["enabled_bands"] = self._valid_bands(bands)
```
→ get: exakt verhaltensgleich. set: bei Listen identisch; bei `set(None)` →
Default statt TypeError-Crash (Mini-Robustheits-Verbesserung, im Betrieb nie
ausgelöst). Volle Kapselung, kürzer.

### Variante B — strikt verhaltensneutral (isinstance bleibt in get):
```python
def _valid_bands(self, raw) -> list[str]:
    valid: list[str] = []
    seen: set[str] = set()
    for b in raw:                    # raw MUSS iterierbar sein
        if isinstance(b, str) and b in BAND_FREQUENCIES and b not in seen:
            valid.append(b); seen.add(b)
    return valid or list(BAND_FREQUENCIES.keys())

def get_enabled_bands(self):
    raw = self._data.get("enabled_bands")
    if not isinstance(raw, list):
        return list(BAND_FREQUENCIES.keys())
    return self._valid_bands(raw)

def set_enabled_bands(self, bands):
    self._data["enabled_bands"] = self._valid_bands(bands)
```
→ beide exakt verhaltensgleich (set(None) crasht wie Original). isinstance-Check
bleibt in get (außerhalb Helfer).

## Meine Tendenz
**A** — der einzige Unterschied (`set(None)` → Default statt Crash) ist eine reine
Robustheits-Verbesserung in einem nie-auftretenden Pfad (set wird immer mit
list[str] gerufen), und A kapselt vollständig + ist kürzer. „Keine
Verhaltensänderung" meint m.E. kein observierbares Betriebsverhalten — set(None)
existiert nicht.

## Fragen
1. A oder B? Ist die `set(None)`-Robustheits-Verbesserung in A vertretbar unter
   der „keine Verhaltensänderung"-Regel, oder soll ich strikt B nehmen?
2. Reihenfolge-Erhalt + Dedup-Semantik in beiden korrekt beibehalten?
3. `_valid_bands` als Instanz-Methode (`self`) ok, oder Modul-Funktion besser
   (nutzt nur BAND_FREQUENCIES, kein self-State)? KISS-Sicht.
4. Übersehe ich etwas? GO/NO-GO.

Knapp + konkret. Code ist Referenz.
