# P164 — Final-R1 Runde 2 (Bestätigung der Nachbesserungen)

Du bist Senior-Reviewer. In Runde 1 hast du **NACHBESSERN** verlangt mit 2 🔴:
1. 🔴 HALT (`_on_cancel`) löscht `_qso_pending_insert` nicht.
2. 🔴 IDLE-Sofort-Ruf (`_on_hunt_insert_clicked` else-Zweig) macht
   `_p158_insertable.clear()` → löscht ALLE anderen uns-rufenden Stationen.

Plus 🟡: auto_hunt Dead Code (`_insert_pending_call`), Band/Mode/RX-Cleanup prüfen.

## Was ich geändert habe (bitte verifizieren)

**Fix 1 (HALT):** In `_on_cancel` (mw_qso.py) steht jetzt direkt nach
`_abort_active_tx()`:
```python
self._qso_pending_insert = None
```
mit Kommentar (cancel() emittiert kein QSO-Signal → maybe_start läuft nicht).

**Fix 2 (IDLE-pop):** else-Zweig in `_on_hunt_insert_clicked` (mw_cycle.py):
```python
else:
    self._p158_insertable.pop(call, None)  # nur geklickten Key
    self._on_station_clicked(msg)
```

**Fix 3 (Dead Code):** `auto_hunt.py` — `_insert_pending_call`-Attribut (__init__
+ stop_auto_hunt) + `set_pending_insert`/`take_pending_insert` komplett entfernt.
`grep _insert_pending_call core/auto_hunt.py` → 0 Treffer.

**Fix 4 (Cleanup):** `mw_radio.py` — an allen 3 `clear_log_completely()`-Stellen
(Band/Mode/RX-Wechsel) folgt jetzt:
```python
self._qso_pending_insert = None
self._p158_insertable.clear()
```

## Tests: volle Suite 2212 passed, 0 Regression. test_p158_insert_pending_call.py
34 Tests grün (T14 auf pop-Semantik angepasst, T25 HALT-Null, T30 Band-Cleanup).

## Frage
Sind die 2 🔴 korrekt behoben? Übersehe ich durch die Fixes einen neuen
Edge-Case (z.B. pop(call) bei nicht-vorhandenem Key, HALT-Null-Reihenfolge,
mehrfaches `_qso_pending_insert = None`)? Verdikt: PUSH FREIGEBEN / NACHBESSERN.

## Code folgt.
