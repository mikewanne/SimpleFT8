# R1-Review: P161 — Toggle-Sortierung im RX-Header (Wechselschalter)

Du bist Senior-Python/PySide6-Reviewer für SimpleFT8 (FT8-Hobby-Funker-Tool,
KISS, kein Contest-Tool). Prüfe meinen Plan KRITISCH auf Bugs, Edge-Cases,
Overengineering. Antworte mit nummerierten Findings (🔴 Blocker / 🟠 sollte /
🟡 nice). Am Ende: GO oder NO-GO.

## Mike-Wunsch (wörtlich)
„Im Empfangsfenster oben im Listen-Header: wenn ich auf km drücke nach km
sortieren, auf dB nach dB. Das geht aber nur in eine Richtung (klein→groß).
Schön wäre ein WECHSELSCHALTER statt normaler Schalter: nochmal drücken =
andere Richtung. Einmal von unten nach oben, einmal von oben nach unten.
Betroffen: dB, km, Uhrzeit (UTC) und Land."

## Ist-Zustand (verifiziert im Code, ui/rx_panel.py)

`self._sort_mode: str` ∈ {"time","snr","dist","country"} (Default "time").

`_on_header_clicked(col)`:
```python
_COL_TO_SORT = {COL_UTC:"time", COL_DB:"snr", COL_LAND:"country", COL_KM:"dist"}
if col in _COL_TO_SORT:
    self._set_sort(_COL_TO_SORT[col])
    self._update_sort_colors()
```

`_set_sort(mode)` — setzt `self._sort_mode = mode`, sammelt alle Zeilen als
`(msg, country, dist_km)`, sortiert mit FEST verdrahteter Richtung:
```python
if mode == "snr":      messages.sort(key=lambda x: x[0].snr, reverse=True)   # höchste oben
elif mode == "dist":   messages.sort(key=lambda x: -x[2])                    # größte oben
elif mode == "country":messages.sort(key=lambda x: x[1])                     # A→Z
elif mode == "time":   messages.sort(key=_time_key, reverse=True)            # neueste oben
```
Danach Tabelle neu aufbauen + `_apply_active_highlight()`.

`_update_sort_colors()`: hängt beim aktiven Modus immer `▾` an das Label +
färbt #00AAFF, sonst neutral. (Enthält eine zweite lokale `_COL_TO_SORT`-Kopie.)

`reapply_sort()`: `if self._sort_mode != "time": self._set_sort(self._sort_mode)`
— wird in mw_cycle.py 2× NACH JEDEM Cycle-Rebuild aufgerufen (Tabelle wird pro
Slot via setRowCount(0) geleert + neu befüllt).

Datenlage:
- `x[2]` = dist_km (int). Stationen OHNE bekannte Entfernung haben `dist_km=0`,
  Anzeige "-".
- `snr == -30` wird als "?" angezeigt (unbekannt).
- country fehlend = "?".

## Mein Plan (V1, nach V2-Self-Review)

**1. Neuer Instanz-State** in `__init__`: `self._sort_reverse: bool = True`.

**2. Modul-Konstanten** (DRY — `_COL_TO_SORT` war 2× lokal):
```python
_COL_TO_SORT = {COL_UTC:"time", COL_DB:"snr", COL_LAND:"country", COL_KM:"dist"}
_DEFAULT_REVERSE = {"time": True, "snr": True, "dist": True, "country": False}
```
(erhält Erst-Klick-Verhalten EXAKT wie heute)

**3. `_on_header_clicked` umbauen:**
```python
if col not in _COL_TO_SORT:
    return
mode = _COL_TO_SORT[col]
if mode == self._sort_mode:
    self._sort_reverse = not self._sort_reverse      # gleiche Spalte → kippen
else:
    self._sort_mode = mode
    self._sort_reverse = _DEFAULT_REVERSE[mode]       # neue Spalte → Default
self._set_sort(mode)
self._update_sort_colors()
```

**4. `_set_sort` — stabiler Doppel-Sort (statt -x[2]-Negation, einheitlich für
alle 4 Modi inkl. country-Strings):**
```python
rev = self._sort_reverse
if mode == "snr":
    messages.sort(key=lambda x: x[0].snr, reverse=rev)
    messages.sort(key=lambda x: x[0].snr == -30)   # "?" unten (stabil)
elif mode == "dist":
    messages.sort(key=lambda x: x[2], reverse=rev)
    messages.sort(key=lambda x: x[2] == 0)         # "-" unten
elif mode == "country":
    messages.sort(key=lambda x: x[1], reverse=rev)
    messages.sort(key=lambda x: x[1] == "?")       # "?" unten
elif mode == "time":
    messages.sort(key=_time_key, reverse=rev)
```
`_set_sort` ändert `_sort_reverse` NICHT (nur `_on_header_clicked` tut das) →
`reapply_sort()` behält die User-Richtung über alle Cycles.

**5. `_update_sort_colors`**: `arrow = "▾" if self._sort_reverse else "▴"`,
nur beim aktiven Modus anhängen. Lokale `_COL_TO_SORT`-Kopie raus → Modul-Konst.

## Gezielte Fragen

F1: Default-Verhalten 100% identisch beim ersten Klick? Stimmt
_DEFAULT_REVERSE mit den heutigen reverse-Werten überein?

F2: dist/snr/country aufsteigend → "-"/0 bzw "?"/-30 Sentinels: mein
Doppel-Sort hält sie unten. Korrekt + KISS, oder Overengineering für ein
Hobby-Tool? (Mike will Einfachheit.)

F3: Doppel-Sort korrekt? Python list.sort ist stabil → zweiter Sort verschiebt
nur Sentinel-Gruppe ans Ende, Rest-Reihenfolge bleibt. Stimmt das für alle 4?

F4: reapply_sort läuft pro Cycle und ruft `_set_sort(self._sort_mode)`. Da
`_sort_reverse` NICHT in `_set_sort` verändert wird, bleibt Richtung. Übersehe
ich einen Pfad der `_sort_mode`/`_sort_reverse` resettet (Band/Mode/RX-Toggle)?

F5: time-Modus (Default) auch toggle-bar — UTC klicken + nochmal = älteste
oben. Harmlos/erwünscht oder soll UTC vom Toggle ausgenommen sein? KISS?

F6: Overengineering — reicht EIN `_sort_reverse` + Default-bei-Spaltenwechsel,
oder braucht's pro-Spalte gemerkte Richtungen (dict)? Ich tendiere zu Ersterem.

F7: Pfeil-Glyphen ▾/▴ in Menlo/Monospace breiten-stabil render-bar?
Alternativ ↓/↑?

Sei knapp. Code ist Referenz, keine Spekulation.
