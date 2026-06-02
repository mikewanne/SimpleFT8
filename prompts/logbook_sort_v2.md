# Review: Logbuch-Tabelle sortiert Datum als String (Bug-Fix-Plan)

Hobby-Funker-FT8-Tool (SimpleFT8, PySide6). KISS. Antworte knapp + kritisch,
Findings 🔴/🟠/🟡.

## Bug (Mike-Field)
Logbuch-Tabelle (`ui/logbook_widget.py`, `QTableWidget`, `setSortingEnabled(True)`)
sortiert die Datums-Spalte falsch: 01.06. und 02.06. stehen ÜBER 12.05./13.05.
Ursache verifiziert: `_format_datetime` liefert die DisplayRole als String
`"DD.MM.YY"` (z. B. "02.06.26"); `QTableWidgetItem.__lt__` vergleicht diesen
String alphabetisch → Tag-Zahl dominiert, Monat/Jahr ignoriert. Mike will:
neuestes oben (02.06. → 01.06. → 31.05. …).

## Ist-Code (relevant)
```python
_COLUMNS = [("_DATETIME","Datum",68),("CALL",..),("BAND",..),("MODE",..),
            ("_COUNTRY","Land",90),("_KM","km",50)]

def _format_datetime(record):
    d = record.get("QSO_DATE","")   # "20260602"
    t = record.get("TIME_ON","")    # "1346"
    if len(d) == 8:
        return f"{d[6:8]}.{d[4:6]}.{d[2:4]}"   # -> "02.06.26"
    return d

# _populate_table:
item = QTableWidgetItem(value)
if col == 0:
    item.setData(Qt.ItemDataRole.UserRole, rec)   # UserRole = Record (Klick-Lookup!)
...
self.table.setItem(row, col, item)
```
km-Spalte (`_estimate_km`) liefert auch Strings: "311", "~4281", "" → sortiert
ebenfalls falsch (numerisch als String).

## Fix-Plan (V1)
Eigene Sortier-Rolle (UserRole ist in col0 belegt):
```python
_SORT_ROLE = Qt.ItemDataRole.UserRole + 1

class _SortableItem(QTableWidgetItem):
    def __lt__(self, other):
        a = self.data(_SORT_ROLE); b = other.data(_SORT_ROLE)
        if a is not None and b is not None:
            return a < b
        return super().__lt__(other)   # Fallback: DisplayRole-String
```
In `_populate_table`: `item = _SortableItem(value)` für alle Zellen.
- **Datum** (col 0): `item.setData(_SORT_ROLE, d + t)` = "202606021346"
  (lexikografisch == chronologisch; leeres Datum → "" sortiert konsistent).
- **km**: numerischen Schlüssel, "~4281"→4281, "311"→311, ""→ -1.
Andere Spalten (Call/Band/Mode/Land) ohne Sort-Role → Fallback String-Sort.

## V2 Self-Review / Fragen
1. `__lt__`: Vergleich erfolgt IMMER nur innerhalb einer Spalte (QTableWidget
   sortiert spaltenweise) → Datum-Schlüssel (str) und km-Schlüssel (int) treffen
   nie aufeinander, kein `str<int`-TypeError. Korrekt so?
2. Datums-Schlüssel `QSO_DATE+TIME_ON` als String — robust gegen fehlende/kurze
   Felder? (TIME_ON mal 4-, mal 6-stellig → Länge inkonsistent, aber innerhalb
   eines Tages selten kollidierend; reicht das oder auf feste Breite zfill?)
3. km: leeres "" → -1 (unten bei aufsteigend) ok? "~"-Strip korrekt?
4. Übersehe ich was bei `setSortingEnabled` + Custom-Item (z. B. dass das
   Default-Sort beim Befüllen die Reihenfolge zerstört)? Aktuell wird während
   Befüllung `setSortingEnabled(False)`, danach True — Default-Sortierspalte?
5. Scope: km gleich mitnehmen (gleicher Bug) oder nur Datum (Mike erwähnte nur
   Datum)? KISS-Urteil.
6. Soll initial nach Datum absteigend (neuestes oben) vorsortiert werden
   (`sortItems(0, DescendingOrder)`), oder dem User den Header-Klick überlassen?
```
