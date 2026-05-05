# P1-Bundle1 Plan V1 — Code-Diffs

**Stand:** 2026-05-06.
**Workflow:** Plan-V1 → Plan-V2 → Plan-R1 → Plan-V3 → Code.
**Diagnose-Quelle:** `prompts/p1_bundle1_v3.md` (R1-Findings eingearbeitet).
**Code-Verifikation:** alle Datei:Zeile-Refs gegen aktuellen Code verifiziert.

---

## 1. P1.6 — Versionsnummer Color-Fix

### Diff
**File:** `ui/control_panel.py:1086-1090`

```diff
         self._version_label = QLabel(f"SimpleFT8 v{APP_VERSION}")
         self._version_label.setStyleSheet(
-            f"color: #333; font-family: {_FONT}; font-size: 10px; "
+            f"color: #666; font-family: {_FONT}; font-size: 10px; "
             "border: none; background: transparent;"
         )
```

**Aufwand:** 1 Zeile, 1 Sekunde.

---

## 2. P1.12 — NEU-Button entfernen

### Diff 1: `ui/control_panel.py:506-526` (Button-Definition + Spacing)

```diff
         div_lay.addLayout(ratio_row)
         phase_row = QHBoxLayout()
         phase_row.setContentsMargins(0, 0, 0, 0)
-        # 36px Spacer links balanciert den NEU-Button rechts → echte Zentrierung
-        phase_row.addSpacing(36)
         self._phase_label = QLabel("")
         self._phase_label.setStyleSheet(
             f"color:#FFCC00;font-size:9px;font-family:{_FONT};font-style:italic;"
         )
         self._phase_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
         phase_row.addWidget(self._phase_label)
-        self.btn_remeasure = QPushButton("NEU")
-        self.btn_remeasure.setFixedSize(36, 18)
-        self.btn_remeasure.setStyleSheet(
-            f"QPushButton {{ background: rgba(60,60,100,0.4); color: #88AACC; "
-            f"border: 1px solid #446; border-radius: 3px; font-size: 9px; "
-            f"font-family: {_FONT}; font-weight: bold; }}"
-            f"QPushButton:hover {{ background: rgba(80,80,140,0.6); }}"
-        )
-        self.btn_remeasure.setToolTip("Diversity sofort neu einmessen")
-        phase_row.addWidget(self.btn_remeasure)
         div_lay.addLayout(phase_row)
```

**Wichtig:** `addSpacing(36)` MUSS auch raus — war Balance fuer den Button.
Ohne Button + ohne Spacing: `_phase_label` zentriert sich natuerlich.

### Diff 2: `ui/control_panel.py:947` (Signal-Definition raus)

```diff
     einmessen_clicked = Signal()
-    remeasure_clicked = Signal()
     map_clicked = Signal()
```

### Diff 3: `ui/control_panel.py:1023-1024` (Connect-Code raus)

```diff
         self.btn_einmessen.clicked.connect(self.einmessen_clicked.emit)
-        self.btn_remeasure = ant_card.btn_remeasure
-        self.btn_remeasure.clicked.connect(self.remeasure_clicked.emit)
         layout.addWidget(ant_card)
```

### Diff 4: `ui/main_window.py:530` (Connect zur Methode raus)

```diff
         self.control_panel.einmessen_clicked.connect(self._handle_dx_tuning)
-        self.control_panel.remeasure_clicked.connect(self._on_diversity_remeasure)
         self.control_panel.settings_clicked.connect(self._on_settings_clicked)
```

### Diff 5: `ui/mw_radio.py:985-997` (Handler-Methode raus)

```diff
-    def _on_diversity_remeasure(self):
-        """NEU-Button: Diversity sofort neu einmessen.
-        ...
-        ...
-        """
-        ... # komplette Methode raus
```

(Genaue Zeilen werden bei Implementation aus dem Code entnommen.)

**Aufwand:** 5 Stellen, ~30 Zeilen Loeschen.

---

## 3. P1.15 — `→ Call | RX: ANT` raus

### Diff: `ui/main_window.py:917-934`

```diff
         if _in_qso and self.qso_sm.qso.their_call:
-            their_call = self.qso_sm.qso.their_call
-            ant_text = "RX: ANT1"
-            ant_color = "#888888"
-            if (self._rx_mode == "diversity"
-                    and hasattr(self, '_antenna_prefs')):
-                pref_entry = self._antenna_prefs.get_pref(their_call)
-                if pref_entry and pref_entry['best_ant'] == "A2":
-                    delta = pref_entry.get('delta_db')
-                    if delta is None:
-                        ant_text = "RX: ANT2"
-                    else:
-                        ant_text = f"RX: ANT2 ↑{abs(delta):.1f} dB"
-                    ant_color = "#44FF88"
-            self.qso_panel.status_label.setText(f"→ {their_call}  |  {ant_text}")
-            self.qso_panel.status_label.setStyleSheet(
-                f"color: {ant_color}; font-size: 11px; padding: 2px; font-weight: bold;"
-            )
+            pass  # P1.15: Status-Anzeige `→ Call | RX: ANT` entfernt
```

**Wichtig:** Der `if _in_qso ...`-Block bleibt (falls weitere Logik dort hinzugefuegt wird), nur der Inhalt wird zu `pass`.

**Alternative (sauberer):** den ganzen `if _in_qso ...`-Block loeschen.
**V1-Entscheidung:** `pass` lassen, falls spaeter wieder was rein soll. KISS-konform.

**Aufwand:** ~17 Zeilen Loeschen.

---

## 4. P1.16 — 5-Min-Rolling-Window

### Diff 1: `ui/qso_panel.py` Imports + `__init__`

```diff
 from PySide6.QtCore import Qt, QTimer
+from PySide6.QtCore import Qt, QTimer
+import time

 class QSOPanel:
     def __init__(self, ...):
         ...
+        self._block_timestamps: list[float] = []
+        self._cleanup_timer = QTimer(self)
+        self._cleanup_timer.setInterval(30_000)  # 30s
+        self._cleanup_timer.timeout.connect(self._auto_trim_by_age)
+        self._cleanup_timer.start()
```

(time-Import: bereits vorhanden Z.~1, QTimer-Import: pruefen ob da.)

### Diff 2: `ui/qso_panel.py` `_append_colored` (Z.241-249)

```diff
     def _append_colored(self, text: str, color: str):
         cursor = self.log_view.textCursor()
         cursor.movePosition(QTextCursor.MoveOperation.End)
         self.log_view.setTextCursor(cursor)
         self.log_view.setTextColor(QColor(color))
         self.log_view.append(text)
+        self._block_timestamps.append(time.time())
         scrollbar = self.log_view.verticalScrollBar()
         scrollbar.setValue(scrollbar.maximum())
```

### Diff 3: `ui/qso_panel.py` `_append_two_color` (Z.251-264)

```diff
     def _append_two_color(self, text1: str, color1: str, text2: str, color2: str):
         cursor = self.log_view.textCursor()
         cursor.movePosition(QTextCursor.MoveOperation.End)
         self.log_view.setTextCursor(cursor)
         self.log_view.setTextColor(QColor(color1))
         self.log_view.append(text1)
+        # _append_two_color erzeugt EINEN Block (append=Block, insertText=im-Block)
+        self._block_timestamps.append(time.time())
         cursor = self.log_view.textCursor()
         cursor.movePosition(QTextCursor.MoveOperation.End)
         fmt = QTextCharFormat()
         fmt.setForeground(QColor(color2))
         cursor.insertText(text2, fmt)
         self.log_view.setTextCursor(cursor)
         scrollbar = self.log_view.verticalScrollBar()
         scrollbar.setValue(scrollbar.maximum())
```

### Diff 4: `ui/qso_panel.py` `_auto_trim` ersetzen durch `_auto_trim_by_age`

```diff
-    def _auto_trim(self, max_lines: int = 40):
-        """QSO-Log auf ~40 Zeilen begrenzen (~3 Min Traffic)."""
-        doc = self.log_view.document()
-        excess = doc.blockCount() - max_lines
-        if excess > 5:
-            cursor = QTextCursor(doc)
-            cursor.movePosition(QTextCursor.MoveOperation.Start)
-            for _ in range(excess):
-                cursor.movePosition(
-                    QTextCursor.MoveOperation.Down,
-                    QTextCursor.MoveMode.KeepAnchor)
-            cursor.removeSelectedText()
-            cursor.deleteChar()
+    def _auto_trim_by_age(self, max_age_s: float = 300.0):
+        """Eintraege aelter als max_age_s entfernen.
+        Defensiv gegen externe `clear()` (KP2): synct Liste mit blockCount.
+        """
+        doc = self.log_view.document()
+        block_count = doc.blockCount()
+        # KP2 Resync: falls extern geleert oder Liste-out-of-sync
+        if len(self._block_timestamps) > block_count:
+            self._block_timestamps = self._block_timestamps[-block_count:]
+
+        now = time.time()
+        cutoff = now - max_age_s
+        n_old = sum(1 for ts in self._block_timestamps if ts < cutoff)
+        if n_old < 5:  # Mindest-Schwelle gegen Flackern
+            return
+
+        # Scroll-Position merken (V2-Fund)
+        scrollbar = self.log_view.verticalScrollBar()
+        was_at_bottom = scrollbar.value() >= scrollbar.maximum() - 5
+
+        cursor = QTextCursor(doc)
+        cursor.movePosition(QTextCursor.MoveOperation.Start)
+        for _ in range(n_old):
+            cursor.movePosition(
+                QTextCursor.MoveOperation.Down,
+                QTextCursor.MoveMode.KeepAnchor)
+        cursor.removeSelectedText()
+        cursor.deleteChar()
+
+        self._block_timestamps = self._block_timestamps[n_old:]
+
+        if was_at_bottom:
+            scrollbar.setValue(scrollbar.maximum())
```

### Diff 5: `_auto_trim()`-Aufruf in `add_tx` (Z.176)

```diff
-        self._auto_trim()
+        # _auto_trim_by_age laeuft via Timer; kein expliziter Aufruf hier
```

**Aufwand:** ~50 Zeilen (Refactor + Replace).

---

## 5. P1.19 — Sterne-Anzeige

### Diff 1: NEU `ui/widgets/__init__.py` (falls nicht existiert)

```python
"""UI-Widgets — wiederverwendbare Custom-Widgets."""
```

### Diff 2: NEU `ui/widgets/stars_widget.py`

```python
"""StarsConditionWidget — 5-Sterne-Anzeige fuer lokale Conditions."""
from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel


class StarsConditionWidget(QWidget):
    """5 Sterne ★, aktive in Neon-Cyan, inaktive in dezentem Grau.

    Theme-konform: #00DDFF (aktiv), #555 (inaktiv, R1-Empfehlung).
    """

    _STAR_ACTIVE_STYLE = (
        "color: #00DDFF; font-size: 14px; "
        "font-family: Menlo; padding: 0 1px;"
    )
    _STAR_INACTIVE_STYLE = (
        "color: #555; font-size: 14px; "
        "font-family: Menlo; padding: 0 1px;"
    )

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self._stars: list[QLabel] = []
        for _ in range(5):
            lbl = QLabel("★")
            lbl.setStyleSheet(self._STAR_INACTIVE_STYLE)
            self._stars.append(lbl)
            layout.addWidget(lbl)
        layout.addStretch()
        self.set_score(1, "0 Stationen")

    def set_score(self, score: int, tooltip: str = "") -> None:
        """Score 1-5: setzt aktive Sterne, klamert auf [1,5]."""
        score = max(1, min(5, int(score)))
        for i, lbl in enumerate(self._stars):
            if i < score:
                lbl.setStyleSheet(self._STAR_ACTIVE_STYLE)
            else:
                lbl.setStyleSheet(self._STAR_INACTIVE_STYLE)
        self.setToolTip(tooltip)
```

### Diff 3: `ui/control_panel.py:875-885` (`_QSOStatusCard`)

```diff
+from ui.widgets.stars_widget import StarsConditionWidget
+
 ...
         # SNR + UTC in einer Zeile
         snr_utc_row = QHBoxLayout()
         snr_utc_row.setSpacing(8)
-        self.snr_label = QLabel("SNR: — dB")
-        self.snr_label.setStyleSheet(f"color: {_TEXT}; font-family: {_FONT}; font-size: 11px;")
+        self.conditions_widget = StarsConditionWidget()
         self.utc_label = QLabel("UTC: --:--:--")
         self.utc_label.setStyleSheet(f"color: {_TEXT}; font-family: {_FONT}; font-size: 11px;")
-        snr_utc_row.addWidget(self.snr_label)
+        snr_utc_row.addWidget(self.conditions_widget)
         snr_utc_row.addStretch()
         snr_utc_row.addWidget(self.utc_label)
         lay.addLayout(snr_utc_row)
```

### Diff 4: `ui/control_panel.py:1065` (ControlPanel `__init__`)

```diff
-        self.snr_label = qso_card.snr_label
+        self.conditions_widget = qso_card.conditions_widget
```

### Diff 5: `ui/control_panel.py:1584` (`update_snr` no-op + neue Methode)

```diff
-    def update_snr(self, snr: int):
-        self.snr_label.setText(f"SNR:  {snr:+d} dB")
+    def update_snr(self, snr: int):
+        """No-Op (P1.19). Sterne-Anzeige nutzt update_local_conditions."""
+        pass
+
+    def update_local_conditions(self, score: int, n_stations: int, median_snr: float):
+        """Sterne-Anzeige fuer lokale Conditions aktualisieren."""
+        if median_snr <= -98:
+            tooltip = f"{n_stations} Stationen (kein Signal)"
+        else:
+            tooltip = f"{n_stations} Stationen, Median {median_snr:+.0f} dB"
+        self.conditions_widget.set_score(score, tooltip)
```

### Diff 6: `ui/mw_cycle.py` Helper + Aufruf

**Position:** im Modul-Top als Helper-Funktion (nicht Methode), dann Aufruf in `_on_cycle_decoded` Slot-Ende-Bereich (Z.~411-415).

```python
# ui/mw_cycle.py — Helper am Modul-Anfang
def compute_local_conditions(stations: dict) -> tuple[int, int, float]:
    """5-Sterne-Score aus Stations-Dict.

    Returnt (score 1-5, n_stations, median_snr_top_half).
    """
    if not stations:
        return 1, 0, -99.0

    snrs = sorted(
        [float(s.snr) for s in stations.values()
         if hasattr(s, 'snr') and s.snr is not None],
        reverse=True,
    )
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

**Aufruf:** im Slot-Ende-Pfad in `_on_cycle_decoded` nach `update_decode_count`:
```python
        # P1.19: Sterne-Anzeige
        stations = (self._diversity_stations
                    if self._rx_mode == "diversity"
                    else self._normal_stations)
        score, n_st, median = compute_local_conditions(stations)
        self.control_panel.update_local_conditions(score, n_st, median)
```

**Aufwand:** ~80 Zeilen (NEU + Refactor).

---

## 6. Test-Files

### NEU `tests/test_p1_bundle1.py` (Sammel-File)

```python
"""P1-Bundle1: P1.6, P1.12, P1.15 Smoke-Tests."""
from PySide6.QtWidgets import QApplication
import pytest

@pytest.fixture
def app(qtbot):
    return qtbot

def test_p1_12_btn_remeasure_removed(qtbot):
    from ui.control_panel import ControlPanel
    cp = ControlPanel()
    qtbot.addWidget(cp)
    assert not hasattr(cp, 'btn_remeasure'), \
        "btn_remeasure muss entfernt sein (P1.12)"

def test_p1_15_status_label_no_arrow_call(qtbot, monkeypatch):
    """status_label darf nach _update_statusbar bei aktivem QSO
    NICHT mit '→ ' beginnen (P1.15)."""
    # ... Mock MainWindow + qso_sm.qso.their_call setzen ...
    # ... _update_statusbar aufrufen ...
    # ... assert not status_label.text().startswith("→")
    pass  # Implementation bei Code
```

### NEU `tests/test_qso_panel_rolling.py`

```python
"""P1.16: QSO-Panel 5-Min-Rolling-Window."""
from unittest.mock import patch
import pytest

def test_qso_panel_block_timestamps_appended(qtbot):
    from ui.qso_panel import QSOPanel
    panel = QSOPanel()
    qtbot.addWidget(panel)
    initial = len(panel._block_timestamps)
    panel._append_colored("test", "#FFF")
    assert len(panel._block_timestamps) == initial + 1

def test_qso_panel_auto_trim_by_age(qtbot):
    from ui.qso_panel import QSOPanel
    panel = QSOPanel()
    qtbot.addWidget(panel)
    # 10 Eintraege ueber 600s simulieren
    base = 1_000_000.0
    for i in range(10):
        with patch('ui.qso_panel.time.time', return_value=base + i*60):
            panel._append_colored(f"test{i}", "#FFF")
    # Cleanup mit 'now' = base + 600
    with patch('ui.qso_panel.time.time', return_value=base + 600):
        panel._auto_trim_by_age(max_age_s=300.0)
    # Bleiben sollen Eintraege > base+300, also Index 5-9 (5 Eintraege)
    assert len(panel._block_timestamps) == 5

def test_qso_panel_trim_below_threshold(qtbot):
    from ui.qso_panel import QSOPanel
    panel = QSOPanel()
    qtbot.addWidget(panel)
    base = 1_000_000.0
    for i in range(4):
        with patch('ui.qso_panel.time.time', return_value=base + i):
            panel._append_colored(f"old{i}", "#FFF")
    # 4 alte Eintraege < Schwelle 5 → kein Trim
    before = len(panel._block_timestamps)
    with patch('ui.qso_panel.time.time', return_value=base + 1000):
        panel._auto_trim_by_age(max_age_s=300.0)
    assert len(panel._block_timestamps) == before

def test_qso_panel_clear_resync(qtbot):
    from ui.qso_panel import QSOPanel
    panel = QSOPanel()
    qtbot.addWidget(panel)
    for i in range(10):
        panel._append_colored(f"x{i}", "#FFF")
    # Externes clear simulieren
    panel.log_view.clear()
    # Liste ist jetzt out-of-sync (10 entries, blockCount=1)
    panel._auto_trim_by_age(max_age_s=300.0)
    # Defensive Resync soll greifen
    assert len(panel._block_timestamps) <= panel.log_view.document().blockCount()

def test_qso_panel_scroll_at_bottom_preserved(qtbot):
    from ui.qso_panel import QSOPanel
    panel = QSOPanel()
    qtbot.addWidget(panel)
    base = 1_000_000.0
    for i in range(20):
        with patch('ui.qso_panel.time.time', return_value=base + i*30):
            panel._append_colored(f"line{i}", "#FFF")
    sb = panel.log_view.verticalScrollBar()
    sb.setValue(sb.maximum())
    with patch('ui.qso_panel.time.time', return_value=base + 600):
        panel._auto_trim_by_age(max_age_s=300.0)
    # Nach Trim wieder am Bottom
    assert sb.value() == sb.maximum()
```

### NEU `tests/test_local_conditions.py`

```python
"""P1.19: compute_local_conditions Logik-Tests."""
from ui.mw_cycle import compute_local_conditions


class _Station:
    def __init__(self, snr):
        self.snr = snr


def test_local_conditions_empty_dict():
    score, n, median = compute_local_conditions({})
    assert score == 1
    assert n == 0
    assert median == -99.0


def test_local_conditions_31_stations_strong():
    stations = {f"call{i}": _Station(-10) for i in range(31)}
    score, n, median = compute_local_conditions(stations)
    assert score == 5
    assert n == 31


def test_local_conditions_2_stations_weak():
    stations = {f"call{i}": _Station(-25) for i in range(2)}
    score, n, median = compute_local_conditions(stations)
    assert score == 1
    assert n == 2


def test_local_conditions_8_stations_borderline():
    stations = {f"call{i}": _Station(-19) for i in range(8)}
    score, n, median = compute_local_conditions(stations)
    assert score == 3  # n >= 8 trigger
    assert n == 8


def test_local_conditions_no_snr_attr():
    class NoSNR:
        pass
    stations = {f"call{i}": NoSNR() for i in range(5)}
    score, n, median = compute_local_conditions(stations)
    assert score == 1
    assert n == 0
```

### NEU `tests/test_stars_widget.py`

```python
"""P1.19: StarsConditionWidget Render-Tests."""
import pytest

def test_stars_widget_set_score_renders(qtbot):
    from ui.widgets.stars_widget import StarsConditionWidget
    w = StarsConditionWidget()
    qtbot.addWidget(w)
    w.set_score(3)
    # 3 aktive Sterne pruefen via styleSheet
    actives = sum(1 for lbl in w._stars if "#00DDFF" in lbl.styleSheet())
    assert actives == 3


def test_stars_widget_tooltip(qtbot):
    from ui.widgets.stars_widget import StarsConditionWidget
    w = StarsConditionWidget()
    qtbot.addWidget(w)
    w.set_score(5, "31 Stationen, Median -10 dB")
    assert w.toolTip() == "31 Stationen, Median -10 dB"
```

---

## 7. Commit-Strategie

**1 atomarer Commit** mit Message:
```
P1-Bundle1: 5 UI-Cleanups (P1.6+P1.12+P1.15+P1.16+P1.19)

- P1.6: Versionsnummer Color #333 → #666 (lesbar)
- P1.12: NEU-Button (btn_remeasure) entfernt — KALIBRIEREN macht Phase 2+3 alleine
- P1.15: Statusbar `→ Call | RX: ANT` entfernt (Mike: stoerend)
- P1.16: QSO-Panel zeitbasiertes 5-Min-Rolling-Window (statt 40-Zeilen)
- P1.19: Sterne-Anzeige `★★★☆☆` ersetzt SNR-Label (lokale Conditions)

Tests 777 → 791 (+14: Bundle1 + Rolling + LocalConditions + Stars)
```

**+ Doku-Commit:** HISTORY.md, CLAUDE.md, HANDOFF.md, TODO.md.

---

## 8. Akzeptanz-Checkliste

- [ ] 5 Diff-Bloecke implementiert
- [ ] 14 neue Tests gruen
- [ ] 777 bestehende Tests gruen
- [ ] App startet, Smoke-Test OK
- [ ] APP_VERSION in main.py 0.95.5 → 0.95.6

---

**Plan-V1 Ende. Naechster Schritt: Plan-V2 Self-Review.**
