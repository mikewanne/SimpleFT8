"""Tests fuer die Logbuch-Datums-/km-Sortierung (v0.98.54).

Bug (Mike-Field, Screenshot 02.06.2026): die Datums-Spalte wurde alphabetisch
(„02.06.26") statt chronologisch sortiert → 01.06./02.06. standen ueber
12.05./13.05. Fix: `_SortableItem` sortiert nach hinterlegtem Schluessel
(`_date_sort_key` = QSO_DATE+TIME_ON, `_km_sort_key` numerisch).
"""

import pytest

from ui.logbook_widget import (
    _SortableItem, _SORT_ROLE, _date_sort_key, _km_sort_key,
)


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


# --------------------------------------------------------------- Sort-Keys

def test_date_sort_key_chronological():
    feb = _date_sort_key({"QSO_DATE": "20260602", "TIME_ON": "1346"})
    jun01 = _date_sort_key({"QSO_DATE": "20260601", "TIME_ON": "2359"})
    may = _date_sort_key({"QSO_DATE": "20260531", "TIME_ON": "0001"})
    assert feb > jun01 > may   # chronologisch, nicht alphabetisch


def test_date_sort_key_time_padding():
    # 13:46 (HHMM) muss VOR 13:46:23 (HHMMSS) liegen, nicht danach.
    k_hhmm = _date_sort_key({"QSO_DATE": "20260602", "TIME_ON": "1346"})    # 134600
    k_hhmmss = _date_sort_key({"QSO_DATE": "20260602", "TIME_ON": "134623"})  # 134623
    assert k_hhmm < k_hhmmss
    assert k_hhmm.endswith("134600")


def test_date_sort_key_empty_safe():
    # Leeres Datum darf nicht crashen; sortiert konsistent ganz unten.
    assert _date_sort_key({}) == "000000"
    assert _date_sort_key({"QSO_DATE": "20260602", "TIME_ON": ""}) == "20260602000000"


def test_km_sort_key():
    assert _km_sort_key("311") == 311
    assert _km_sort_key("~4281") == 4281
    assert _km_sort_key("  ~999 ") == 999
    assert _km_sort_key("") == -1
    assert _km_sort_key("abc") == -1
    assert _km_sort_key("~") == -1


# --------------------------------------------------- _SortableItem.__lt__

def test_sortable_item_uses_key_not_text(qapp):
    # Mit Schluessel: chronologisch (12.05 < 02.06), trotz „02" < „12" im Text.
    a = _SortableItem("02.06.26")
    a.setData(_SORT_ROLE, _date_sort_key({"QSO_DATE": "20260602", "TIME_ON": "0"}))
    b = _SortableItem("12.05.26")
    b.setData(_SORT_ROLE, _date_sort_key({"QSO_DATE": "20260512", "TIME_ON": "0"}))
    assert b < a            # Mai vor Juni
    assert not (a < b)


def test_sortable_item_fallback_string(qapp):
    # Ohne Schluessel: Standard-String-Vergleich (DisplayRole).
    a = _SortableItem("Apple")
    b = _SortableItem("Banana")
    assert a < b


def test_screenshot_bug_fixed(qapp):
    # Exakt die Daten aus Mikes Screenshot, aufsteigend sortiert.
    rows = [("01.06.26", "20260601"), ("02.06.26", "20260602"),
            ("12.05.26", "20260512"), ("13.05.26", "20260513")]
    items = []
    for disp, date in rows:
        it = _SortableItem(disp)
        it.setData(_SORT_ROLE, _date_sort_key({"QSO_DATE": date, "TIME_ON": "0000"}))
        items.append(it)
    ordered = [i.text() for i in sorted(items)]   # sorted nutzt __lt__
    # Chronologisch: Mai zuerst, dann Juni — NICHT die alte String-Reihenfolge
    # 01.06/02.06/12.05/13.05.
    assert ordered == ["12.05.26", "13.05.26", "01.06.26", "02.06.26"]


def test_full_table_sort_descending(qapp):
    # End-to-End ueber ein echtes QTableWidget: absteigend = neuestes oben.
    from PySide6.QtWidgets import QTableWidget
    from PySide6.QtCore import Qt
    rows = [("31.05.26", "20260531"), ("02.06.26", "20260602"),
            ("01.06.26", "20260601")]
    t = QTableWidget(len(rows), 1)
    for r, (disp, date) in enumerate(rows):
        it = _SortableItem(disp)
        it.setData(_SORT_ROLE, _date_sort_key({"QSO_DATE": date, "TIME_ON": "1200"}))
        t.setItem(r, 0, it)
    t.setSortingEnabled(True)
    t.sortItems(0, Qt.SortOrder.DescendingOrder)
    shown = [t.item(r, 0).text() for r in range(t.rowCount())]
    assert shown == ["02.06.26", "01.06.26", "31.05.26"]
    t.deleteLater()
