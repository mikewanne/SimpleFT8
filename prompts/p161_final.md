# Final-R1: P161 Toggle-Sortierung — fertiger Code nach R1-GO

Du hast den Plan in R1 mit GO bewertet. Deine 🟠-Empfehlungen wurden umgesetzt:
- 🟠2 Pfeil-Glyphen: ▾/▴ → **↓/↑** (breitenstabil in Menlo). ✓
- 🟠1 Sentinel-always-bottom: **nur noch für dist** (km „-") behalten — das ist
  Mikes Haupt-Use-Case „nächste Station oben, nicht 50 Unbekannte". snr/country
  sind jetzt **reine Umkehr** (kein Sentinel). ✓
- 🟠3 `_set_sort` setzt `_sort_mode` redundant: BEWUSST belassen — `reapply_sort()`
  ruft `_set_sort(self._sort_mode)` und verlässt sich auf konsistenten State;
  harmloser Self-Assign, kein Bug.

Prüfe die finale Fassung auf neue Bugs. Verdict: PUSH FREIGEBEN oder NACHBESSERN.

## _on_header_clicked
```python
if col not in _COL_TO_SORT:
    return
mode = _COL_TO_SORT[col]
if mode == self._sort_mode:
    self._sort_reverse = not self._sort_reverse
else:
    self._sort_mode = mode
    self._sort_reverse = _DEFAULT_REVERSE[mode]
self._set_sort(mode)
self._update_sort_colors()
```

## _set_sort (Sentinel NUR für dist)
```python
rev = self._sort_reverse
if mode == "snr":
    messages.sort(key=lambda x: x[0].snr, reverse=rev)
elif mode == "dist":
    messages.sort(key=lambda x: x[2], reverse=rev)
    messages.sort(key=lambda x: x[2] == 0)   # "-" (keine km) immer unten
elif mode == "country":
    messages.sort(key=lambda x: x[1], reverse=rev)
elif mode == "time":
    messages.sort(key=_time_key, reverse=rev)
```

## _update_sort_colors
```python
arrow = "↓" if self._sort_reverse else "↑"
... if _COL_TO_SORT.get(col) == self._sort_mode:
        item.setText(f"{label}{arrow}")
```

## Modul-Konstanten (genau 1× definiert, verifiziert)
```python
_COL_TO_SORT = {COL_UTC:"time", COL_DB:"snr", COL_LAND:"country", COL_KM:"dist"}
_DEFAULT_REVERSE = {"time":True, "snr":True, "dist":True, "country":False}
```
__init__: `self._sort_reverse = True`

## Bekannte, bewusst akzeptierte Eigenschaft
Eine Station mit echter Entfernung 0 km wird im UI ohnehin als „-" angezeigt
(`_populate_row`: `if dist_km > 0: ... else: km_str = "-"`) — sie ist optisch
nicht von „unbekannt" unterscheidbar und landet daher konsistent mit ihnen
unten. Das ist bestehende UI-Realität, kein durch P161 neu eingeführter Fehler.

## Tests: 9 neu (test_p161_toggle_sort.py), volle Suite 2205 passed, 0 Regression
toggle_flips_reverse, first_click_uses_default_reverse (snr/dist/country),
utc_first_click_is_toggle_since_default_active, new_column_resets_to_default,
snr_ascending_and_descending, dist_unknown_stays_bottom_ascending,
dist_descending_unknown_still_bottom, reapply_keeps_direction,
header_arrow_reflects_direction.

## Prüf-Fragen
1. Alle 3 R1-🟠 korrekt adressiert?
2. snr/country reine Umkehr — beim Aufsteigend landen jetzt schwächste SNR /
   "?"-Land oben. Konsistent mit „reiner Umkehr", richtig?
3. Regression: erster Klick exakt wie vor P161?
4. Übersehener Bug in der finalen Fassung?

Knapp. ui/rx_panel.py ist angehängt — Code ist Referenz.
