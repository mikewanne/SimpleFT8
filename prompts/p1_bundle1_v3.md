# P1-Bundle1 V3 — R1-Findings eingearbeitet

**Stand:** 2026-05-06.
**Workflow:** V1 → V2 → R1 → **V3** (diese Datei) → Plan → Code.
**R1-Findings:** 5 KP + Theme-Korrektur + Test-Liste-Praezisierung.

---

## 0. R1 → V3 Diff (was sich aendert)

| # | R1-Finding | V3-Loesung |
|---|---|---|
| KP1 | `update_snr()` bricht nach Ersetzung von `snr_label` | `update_snr()` wird **No-Op** (Method bleibt fuer Backward-Compat, tut aber nichts). `update_local_conditions(score, n, median)` ist der echte UI-Pfad. Aufrufer in `mw_cycle.py:415, 750` bleiben unveraendert |
| KP2 | P1.16 Clear-Bug-Schutz | `_auto_trim_by_age` macht defensiven Resync: wenn `len(_block_timestamps) > document.blockCount()` → Liste auf `[-blockCount():]` zuschneiden |
| KP3 | Orphan-Signal `remeasure_clicked` | Signal-Definition aus `ControlPanel`-Klasse loeschen (5. Stelle in P1.12) |
| KP4 | P1.15 praezise Code-Stelle | `MainWindow._update_statusbar()` Zeilen ~930-944 (statt `_on_state_changed`) |
| KP5 | P1.19 Widget-Zuordnung | `StarsConditionWidget` wird in `_QSOStatusCard.__init__` instanziert. `ControlPanel.__init__` holt's via `self.conditions_widget = qso_card.conditions_widget` |
| Theme | `#3a3a4e` zu schwach | Inaktive Sterne: **`#555`** (lesbarer auf `#1a1a2e`) |
| Tests | 14 Tests nicht aufgeschluesselt | V3 §6: 13 konkrete Tests |

---

## 1. P1.6 — Versionsnummer-Anzeige (UNVERAENDERT)

`control_panel.py:1086-1090` Color `#333` → `#666`.

**Tests:** 0 Unit-Tests (reine Color-Aenderung). Smoke-Test bei App-Start.

---

## 2. P1.12 — NEU-Button entfernen (R1-KP3 ergaenzt)

### 6 Code-Stellen (statt 5):
1. `control_panel.py:516-525` — Button-Definition in Antennen-Card
2. `control_panel.py:947` — `remeasure_clicked = Signal()` ⛔ NEU GELOESCHT (R1-KP3)
3. `control_panel.py:1023-1024` — `self.btn_remeasure = ant_card.btn_remeasure` + Connect
4. `main_window.py:530` — `self.control_panel.remeasure_clicked.connect(...)`
5. `mw_radio.py:985-997` — `_on_diversity_remeasure` Methode

(Eintrag 2 + Eintrag 3 sind in V2 schon erwaehnt, V3 bestaetigt nur dass beide raus.)

**Tests:** 1 neuer Test (Smoke): `assert not hasattr(control_panel, 'btn_remeasure')`.

---

## 3. P1.15 — `→ Call | RX: ANT` raus (R1-KP4 praezisiert)

**Praezise Code-Stelle:** `main_window.py:_update_statusbar()` Zeilen ~930-944.

Der zu loeschende Block:
```python
# AB Z.~930 IN _update_statusbar:
ant_color = "#888888"
if (self._rx_mode == "diversity"
        and hasattr(self, '_antenna_prefs')):
    pref_entry = self._antenna_prefs.get_pref(their_call)
    if pref_entry and pref_entry['best_ant'] == "A2":
        delta = pref_entry.get('delta_db')
        if delta is None:
            ant_text = "RX: ANT2"
        else:
            ant_text = f"RX: ANT2 ↑{abs(delta):.1f} dB"
        ant_color = "#44FF88"
self.qso_panel.status_label.setText(f"→ {their_call}  |  {ant_text}")
self.qso_panel.status_label.setStyleSheet(...)
```

→ Komplett raus. Falls `their_call` weiter unten benoetigt wird: nur die `setText`/`setStyleSheet`-Zeilen entfernen, Variable behalten.

**Tests:** 1 Smoke-Test: nach `MainWindow._update_statusbar()` Aufruf bei aktivem QSO darf `qso_panel.status_label.text()` NICHT mit `"→ "` beginnen.

---

## 4. P1.16 — 5-Min-Rolling-Window (R1-KP2 ergaenzt)

### Implementierung (V2 + KP2-Resync)

```python
class QSOPanel:
    def __init__(self):
        ...
        self._block_timestamps: list[float] = []
        self._cleanup_timer = QTimer(self)
        self._cleanup_timer.setInterval(30_000)
        self._cleanup_timer.timeout.connect(self._auto_trim_by_age)
        self._cleanup_timer.start()

    def _append_colored(self, text: str, color: str):
        # ... bestehender Code (existiert bereits) ...
        self._block_timestamps.append(time.time())  # NEU am Ende

    def _auto_trim_by_age(self, max_age_s: float = 300.0):
        doc = self.log_view.document()

        # KP2 RESYNC: Falls extern geleert wurde
        if len(self._block_timestamps) > doc.blockCount():
            self._block_timestamps = self._block_timestamps[-doc.blockCount():]

        now = time.time()
        cutoff = now - max_age_s
        n_old = sum(1 for ts in self._block_timestamps if ts < cutoff)
        if n_old < 5:  # Mindest-Schwelle gegen Flackern
            return

        # Scroll-Position merken
        scrollbar = self.log_view.verticalScrollBar()
        was_at_bottom = scrollbar.value() >= scrollbar.maximum() - 5

        # Top n_old Blocks aus Document loeschen
        cursor = QTextCursor(doc)
        cursor.movePosition(QTextCursor.MoveOperation.Start)
        for _ in range(n_old):
            cursor.movePosition(
                QTextCursor.MoveOperation.Down,
                QTextCursor.MoveMode.KeepAnchor)
        cursor.removeSelectedText()
        cursor.deleteChar()

        # Liste synchron halten
        self._block_timestamps = self._block_timestamps[n_old:]

        # Scroll-Position
        if was_at_bottom:
            scrollbar.setValue(scrollbar.maximum())
```

### Bestehender `_auto_trim` (Zeile 266-276)
**Bleibt bestehen** als zweite Sicherung gegen unbegrenztes Wachstum (max 200 Zeilen).
Die zwei Methoden ergaenzen sich:
- `_auto_trim` (existing): bei jedem Append, max 40 Zeilen → entfernt
- `_auto_trim_by_age` (NEU): alle 30s, alles aelter 5 Min → entfernt

**KISS-Entscheidung:** Wir loeschen `_auto_trim` (zeilenbasiert) und ersetzen durch nur `_auto_trim_by_age`. Bei intensiver Session (>20 QSOs/5 Min) bleiben max ~200 Zeilen — akzeptabel.

→ V3-Entscheidung: **`_auto_trim` ersetzen** (nicht parallel halten). Aufrufe in `add_tx`/`add_rx`/`add_info` entfernen.

**Tests (5):**
1. `test_qso_panel_block_timestamps_appended` — `_append_colored` einmal → `len(_block_timestamps) == 1`
2. `test_qso_panel_auto_trim_by_age` — Mock `time.time()` → 10 Eintraege ueber 600s → `_auto_trim_by_age()` → bleiben Eintraege < 300s
3. `test_qso_panel_trim_below_threshold` — 4 alte Eintraege → `_auto_trim_by_age()` aendert nichts (Threshold 5)
4. `test_qso_panel_clear_resync` — `log_view.clear()` simuliert + `_auto_trim_by_age()` → keine `IndexError`, Liste passt zu blockCount
5. `test_qso_panel_scroll_at_bottom_preserved` — User am Bottom → nach Trim wieder am Bottom

---

## 5. P1.19 — Sterne-Anzeige (R1-KP1+KP5 eingearbeitet)

### Datenmodell (V3-final)

```python
def compute_local_conditions(stations: dict) -> tuple[int, int, float]:
    """Returnt (score 1-5, n_stations, median_snr_top_half)."""
    if not stations:
        return 1, 0, -99.0

    snrs = sorted([float(s.snr) for s in stations.values()
                   if hasattr(s, 'snr') and s.snr is not None],
                  reverse=True)
    n = len(snrs)
    if n == 0:
        return 1, 0, -99.0

    top_half = snrs[:max(1, n // 2)]
    median = top_half[len(top_half) // 2] if top_half else -99.0

    if n >= 25 or median > -12:
        return 5, n, median
    if n >= 15 or median > -15:
        return 4, n, median
    if n >= 8 or median > -18:
        return 3, n, median
    if n >= 3 or median > -22:
        return 2, n, median
    return 1, n, median
```

→ Datei: NEU `core/local_conditions.py` (oder als Helper in `mw_cycle.py`).
**KISS-Entscheidung V3:** **`mw_cycle.py` als Helper** (nicht neue Datei) — wird nur dort gebraucht.

### UI-Widget (V3-final)

**Datei:** NEU `ui/widgets/stars_widget.py`

```python
from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel

class StarsConditionWidget(QWidget):
    _STAR_ACTIVE_STYLE = (
        "color: #00DDFF; font-size: 14px; "
        "font-family: Menlo; padding: 0 1px;"
    )
    _STAR_INACTIVE_STYLE = (
        "color: #555; font-size: 14px; "  # KP/Theme: #555 statt #3a3a4e
        "font-family: Menlo; padding: 0 1px;"
    )

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self._stars = []
        for i in range(5):
            lbl = QLabel("★")
            lbl.setStyleSheet(self._STAR_INACTIVE_STYLE)
            self._stars.append(lbl)
            layout.addWidget(lbl)
        layout.addStretch()
        self.set_score(1, "0 Stationen")

    def set_score(self, score: int, tooltip: str = ""):
        score = max(1, min(5, int(score)))
        for i, lbl in enumerate(self._stars):
            if i < score:
                lbl.setStyleSheet(self._STAR_ACTIVE_STYLE)
            else:
                lbl.setStyleSheet(self._STAR_INACTIVE_STYLE)
        self.setToolTip(tooltip)
```

### Anbindung (KP5: Widget in `_QSOStatusCard`)

**`control_panel.py` `_QSOStatusCard.__init__`:**
```python
# ALT (Z.878-882):
# self.snr_label = QLabel("SNR: — dB")
# ... setStyleSheet ...
# snr_utc_row.addWidget(self.snr_label)

# NEU:
from ui.widgets.stars_widget import StarsConditionWidget
self.conditions_widget = StarsConditionWidget()
snr_utc_row.addWidget(self.conditions_widget)
```

**`ControlPanel.__init__` (Z.1065 Bereich):**
```python
# ALT: self.snr_label = qso_card.snr_label
# NEU:
self.conditions_widget = qso_card.conditions_widget
```

**`update_snr()` Methode (Z.1584) wird No-Op (KP1):**
```python
def update_snr(self, snr: int):
    """No-Op (P1.19). update_local_conditions(score, n, median) is the new path."""
    pass

def update_local_conditions(self, score: int, n_stations: int, median_snr: float):
    if median_snr <= -98:
        tooltip = f"{n_stations} Stationen (kein Signal)"
    else:
        tooltip = f"{n_stations} Stationen, Median {median_snr:+.0f} dB"
    self.conditions_widget.set_score(score, tooltip)
```

### Aufruf in `mw_cycle.py:411` (oder `_on_cycle_decoded` Slot-Ende)

**Helper:**
```python
def _refresh_local_conditions(self):
    """Nach Slot-Ende Sterne aktualisieren."""
    stations = (self._diversity_stations
                if self._rx_mode == "diversity"
                else self._normal_stations)
    score, n, median = compute_local_conditions(stations)
    self.control_panel.update_local_conditions(score, n, median)
```

**Aufruf:** im Slot-Ende-Pfad wo `update_decode_count` ist (Z.411-415 Bereich).

**Tests (7):**
1. `test_local_conditions_empty_dict` — `compute_local_conditions({})` → `(1, 0, -99.0)`
2. `test_local_conditions_31_stations_strong` — 31 Stations alle -10 → `(5, 31, -10)`
3. `test_local_conditions_2_stations_weak` — 2 Stations -25 → `(1, 2, -25)`
4. `test_local_conditions_8_stations_borderline` — 8 Stations -19 → `(3, 8, -19)` (n=8 trigger)
5. `test_local_conditions_no_snr_attr` — Stations ohne `.snr` → `(1, 0, -99.0)` (filter)
6. `test_stars_widget_set_score_renders` — `set_score(3)` → 3 Sterne aktiv-Style
7. `test_stars_widget_tooltip` — `set_score(5, "31 Sta, +-10 dB")` → `toolTip() == "31 Sta, +-10 dB"`

---

## 6. Test-Liste konkret (V3-final, 14 Tests gesamt)

| # | Test | Datei | Coverage |
|---|---|---|---|
| 1 | btn_remeasure removed | `tests/test_p1_bundle1.py` | P1.12 |
| 2 | status_label no `→ Call` | `tests/test_p1_bundle1.py` | P1.15 |
| 3-7 | QSO-Panel Rolling-Window (5) | `tests/test_qso_panel_rolling.py` NEU | P1.16 |
| 8-12 | compute_local_conditions (5) | `tests/test_local_conditions.py` NEU | P1.19 |
| 13-14 | StarsConditionWidget (2) | `tests/test_stars_widget.py` NEU | P1.19 |

**P1.6:** kein Unit-Test, Smoke beim App-Start.

---

## 7. Akzeptanzkriterien (V3-final)

### Code
- [ ] P1.6: Versionsnummer Color `#666`
- [ ] P1.12: Button + Signal + Handler entfernt (5 Stellen, inkl. orphan Signal)
- [ ] P1.15: `→ Call | RX: ANT`-Block in `_update_statusbar` raus
- [ ] P1.16: 5-Min-Rolling-Window mit Block-Timestamps + Clear-Resync
- [ ] P1.19: `StarsConditionWidget` ersetzt SNR-Label
- [ ] `update_snr()` ist No-Op (Backward-Compat ohne Crash)
- [ ] 14 neue Tests gruen
- [ ] Bestehende 777 Tests gruen (oder angepasst wo `snr_label` referenziert)

### Field-Test (Mike)
- [ ] App startet ohne Fehler
- [ ] Versionsnummer rechts unten lesbar
- [ ] KALIBRIEREN-Button funktioniert weiter
- [ ] NEU-Button verschwunden, Antennen-Card sauber
- [ ] Bei aktivem QSO: keine `→ Call`-Anzeige
- [ ] Nach 5+ Min Funken: alte QSO-Eintraege weg
- [ ] Sterne reagieren auf Conditions

---

## 8. Workflow-Plan (V3)

1. ✅ V1
2. ✅ V2
3. ✅ R1 (DeepSeek-Reasoner, 5 KP-Findings)
4. ✅ V3 (diese Datei)
5. → **Mike-Freigabe** (in dieser Session: Mike hat volle Autonomie gegeben)
6. → Plan-V1 (mit Code-Diffs pro Sub-Aufgabe)
7. → Plan-V2 (Self-Review)
8. → Plan-R1 (DeepSeek)
9. → Plan-V3
10. → Code-Implementation + Tests
11. → Atomarer Commit + Doku-Commit

**V3 Ende — Mike's Auto-Freigabe gilt — weiter mit Plan-V1.**
