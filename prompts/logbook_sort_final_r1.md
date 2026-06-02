# Final-Review: Logbuch-Sortier-Fix (implementiert)

Hobby-FT8-Tool. Push-Freigabe ja/nein + Findings 🔴/🟠/🟡. Knapp.

## Umgesetzt (gegen deinen Plan-Review)
- `_SortableItem(QTableWidgetItem)` mit `__lt__`: vergleicht `_SORT_ROLE`-Schlüssel
  wenn bei BEIDEN gesetzt, sonst Text-Vergleich.
- **Wichtig — Abweichung vom Plan:** `super().__lt__(other)` als Fallback führt in
  PySide6 zu **RecursionError** (C++-Basis ruft die Python-Override erneut auf).
  Vom Test gefangen. Fallback ist jetzt `return self.text() < other.text()`.
- `_date_sort_key`: `QSO_DATE + TIME_ON.ljust(6,"0")` (dein 🔴 TIME_ON-Padding).
- `_km_sort_key`: `strip().lstrip("~")`, `int(s) if s.isdigit() else -1`
  (dein 🟠 — kein int()-Crash, kein try nötig).
- In `_populate_table`: `_SortableItem` statt `QTableWidgetItem`, Schlüssel nur
  für `_DATETIME` + `_KM`. Andere Spalten Fallback-Text.
- Kein `sortItems`-Initialsort (Python-Sort befüllt schon absteigend, dein 🟡).

## Verifiziert
- 8 neue Tests grün, u.a. Screenshot-Bug (01.06/02.06/12.05/13.05 → chronologisch
  12.05/13.05/01.06/02.06) + End-to-End QTableWidget descending. Volle Suite
  **2286 passed**.
- Reine UI-Sortierung, kein TX, keine Hardware.

## Bitte prüfen
1. `__lt__`-Fallback `self.text() < other.text()` — korrekt + rekursionsfrei?
   Edge wenn `other` ein plain QTableWidgetItem ist (hat `.text()`/`.data()`)?
2. Übersehe ich einen Pfad, der noch ein plain `QTableWidgetItem` in die Tabelle
   setzt (Mischung Custom/plain → inkonsistenter Vergleich)?
3. Sonst etwas?

**PUSH FREIGEBEN** oder **NICHT**?
