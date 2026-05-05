# P1-Bundle1 Plan V2 — Self-Review

**Stand:** 2026-05-06.
**Workflow:** Plan-V1 → **Plan-V2** (diese Datei) → Plan-R1 → Plan-V3 → Code.
**Methode:** frische KI liest Plan-V1, sucht Luecken, korrigiert.

---

## 0. V1-Luecken-Tabelle

| # | V1-Luecke | V2-Korrektur |
|---|---|---|
| L1 | V1 nutzt `qtbot` Fixture (pytest-qt), Repo nutzt aber `_ensure_app()` | Test-Files mit `QApplication.instance() or QApplication([])` schreiben |
| L2 | Sterne-Update nur wenn `_normal_stations` gefuellt (V1 ruft via `update_decode_count`-Pfad) | Sterne MUESSEN immer aktualisieren (auch leerer Cycle → 1 Stern) |
| L3 | `compute_local_conditions` Aufruf-Site nicht praezise | Aufruf in `_on_cycle_decoded` nach Z.418 (`_log_stats`), unabhaengig von messages-Inhalt |
| L4 | `ui/widgets/__init__.py` wird gebraucht aber nicht im Diff | NEUES Verzeichnis + `__init__.py` muss explizit angelegt werden |
| L5 | APP_VERSION-Bump 0.95.5 → 0.95.6 erwaehnt aber nicht im Diff | `main.py:16` Diff hinzu |
| L6 | P1.15 Test stub `pass` — Methode `_update_statusbar` ist `MainWindow`-Methode, nicht trivial mockbar | Test umstellen auf direkten qso_panel-Test: nach P1.15 darf `qso_panel.status_label.text()` keinen `→` enthalten wenn QSO aktiv ist |
| L7 | qso_panel.py — `time` und `QTimer` Imports schon da (Z.3+9) | Diff korrigieren: keine doppelten Imports |
| L8 | `_auto_trim()` Aufruf nur in `add_tx` Z.176 — kein Aufruf in `add_rx`/`add_info` | Nur eine Stelle zu entfernen, V1 Diff korrekt |
| L9 | Plan-V1 Test test_qso_panel_clear_resync — `panel.log_view.clear()` setzt blockCount auf 1, nicht 0. Resync `[-1:]` haelt 1 Eintrag | Test pruefen: `len(timestamps) <= blockCount` (1) — V1 hat das so, OK |
| L10 | Plan-V1 erwaehnt `_block_timestamps[-doc.blockCount():]` — wenn blockCount > Liste = OK (kein Slice-Fehler) | Defensive Implementation OK |
| L11 | `update_snr` weiter aufgerufen Z.415, 750 — beide bleiben funktional als No-Op (R1-KP1-Loesung) | Bestaetigt |
| L12 | Test test_p1_15 stub: brauchte MainWindow + qso_sm + qso → komplex | Pragmatisch: nicht testen, Smoke-Test reicht. ODER: nur Code-Verifikation per grep — `grep -c "→ {their_call}" main_window.py` muss 0 sein |
| L13 | mw_radio.py Z.985 `_on_diversity_remeasure` — komplette Methode loeschen, Test pruefen | Tests fuer `_on_diversity_remeasure` existieren nicht (grep verifiziert) |

---

## 1. V2-Korrektur Test-Pattern

**Repo-Konvention** (aus `tests/test_calibration_dialog_smoke.py`):

```python
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

def _ensure_app():
    return QApplication.instance() or QApplication([])
```

→ Alle neuen Tests in V3 ohne `qtbot` schreiben, mit `_ensure_app()`.

---

## 2. V2-Korrektur Sterne-Update-Position

**V1-Lücke (L2+L3):** V1 ruft `compute_local_conditions` neben `update_snr`,
das ist Z.415 in `_on_cycle_decoded`. Aber Z.415 ist im `if self._normal_stations:`-
Block (Z.413). Bei leerem Slot wird Sterne nicht aktualisiert.

**V2-Loesung:** Aufruf NACH dem `_log_stats`-Block (Z.418), unabhaengig von messages:

```python
# Aktueller Z.411-418 Bereich:
        self.control_panel.update_decode_count(len(self._normal_stations))
        avg_snr = -30
        if self._normal_stations:
            avg_snr = round(sum(m.snr for m in self._normal_stations.values())
                            / len(self._normal_stations))
            self.control_panel.update_snr(avg_snr)  # No-Op nach P1.19

        self._log_stats(len(self._normal_stations), messages or [], avg_snr=avg_snr)

        # P1.19 NEU: Sterne immer aktualisieren (auch leerer Slot)
        stations = (self._diversity_stations
                    if self._rx_mode == "diversity"
                    else self._normal_stations)
        score, n_st, median = compute_local_conditions(stations)
        self.control_panel.update_local_conditions(score, n_st, median)
```

---

## 3. V2-Korrektur ui/widgets/

**V1-Lücke (L4):** `ui/widgets/` Verzeichnis existiert nicht.

**V2-Loesung:** `mkdir ui/widgets && touch ui/widgets/__init__.py`.
Der `__init__.py` Inhalt:

```python
"""UI-Widgets — wiederverwendbare Custom-Widgets."""
from ui.widgets.stars_widget import StarsConditionWidget

__all__ = ["StarsConditionWidget"]
```

→ Re-Export macht Imports schoener: `from ui.widgets import StarsConditionWidget`.

---

## 4. V2-Korrektur APP_VERSION

**V1-Lücke (L5):** Bump erwaehnt aber kein Diff.

**Diff:** `main.py:16`
```diff
-APP_VERSION = "0.95.5"
+APP_VERSION = "0.95.6"
```

---

## 5. V2-Korrektur P1.15-Test

**V1-Lücke (L6+L12):** Test-Stub `pass` ist nicht hilfreich.

**V2-Loesung:** Pragmatisch — kein Unit-Test, sondern grep-Verifikation in
einem einfachen Test:

```python
def test_p1_15_no_arrow_call_in_status():
    """P1.15: status_label-Setzung mit `→ {their_call}` darf nicht mehr im Code sein."""
    src = (Path(__file__).parent.parent / "ui" / "main_window.py").read_text()
    assert "f\"→ {their_call}" not in src, \
        "P1.15: → Call-Setzung in main_window.py noch vorhanden"
    assert "→ {their_call}" not in src
```

Das pruefelt am Code (statisch), nicht an Runtime. KISS.

---

## 6. Akzeptanz-Update fuer V3

V3 muss enthalten:
- L1: Test-Pattern korrigiert (`_ensure_app()`)
- L2: Sterne-Update nach `_log_stats` (immer)
- L3: Aufruf-Site praezise dokumentiert
- L4: `ui/widgets/__init__.py` Diff
- L5: `main.py:16` APP_VERSION Diff
- L6: P1.15 Test als grep-Verifikation
- L7: kein doppelter Import in qso_panel.py
- L11: Bestaetigung dass `update_snr` als No-Op weiter aufgerufen wird

---

## 7. Test-Liste V2-final

| # | Test | Datei | Methode |
|---|---|---|---|
| 1 | btn_remeasure removed | `test_p1_bundle1.py` | `_ensure_app()` + ControlPanel-Instanz |
| 2 | P1.15 grep-Verifikation | `test_p1_bundle1.py` | Static-Source-Read |
| 3 | block_timestamps appended | `test_qso_panel_rolling.py` | `_ensure_app()` + QSOPanel |
| 4 | _auto_trim_by_age — 5/10 alt | `test_qso_panel_rolling.py` | mock time.time |
| 5 | _auto_trim_by_age unter Schwelle | `test_qso_panel_rolling.py` | mock time.time |
| 6 | clear_resync defensive | `test_qso_panel_rolling.py` | `log_view.clear()` |
| 7 | scroll_at_bottom_preserved | `test_qso_panel_rolling.py` | scrollbar-API |
| 8 | empty_dict | `test_local_conditions.py` | pure logic |
| 9 | 31_stations_strong | `test_local_conditions.py` | pure logic |
| 10 | 2_stations_weak | `test_local_conditions.py` | pure logic |
| 11 | 8_stations_borderline | `test_local_conditions.py` | pure logic |
| 12 | no_snr_attr | `test_local_conditions.py` | pure logic |
| 13 | stars_widget render | `test_stars_widget.py` | `_ensure_app()` + Widget |
| 14 | stars_widget tooltip | `test_stars_widget.py` | `_ensure_app()` + Widget |

= 14 Tests, alle ohne pytest-qt.

---

**Plan-V2 Ende. Naechster Schritt: Plan-R1 (DeepSeek-Reasoner Final-Check).**
