# P1-Bundle1 Plan V3 — Final (Plan-R1 eingearbeitet)

**Stand:** 2026-05-06.
**Workflow:** Plan-V1 → Plan-V2 → Plan-R1 (4 Findings, 4 Test-Erweiterungen) → **Plan-V3** (diese Datei) → Code.
**Status:** Plan freigegeben, ready fuer Implementation.

---

## 0. Plan-R1 → Plan-V3 Diff

| # | R1-Finding | V3-Loesung |
|---|---|---|
| B1 | qtbot statt _ensure_app | bereits in V2 (L1) — Tests mit `_ensure_app()` |
| B2 | P1.15-Test stub | bereits in V2 (L6) — Source-Grep-Test |
| B3 | `_append_two_color` Timestamp-Test fehlt | **NEU T1**: Test #15 |
| B4 | StarsConditionWidget Clamping ungestestet | **NEU T2**: Tests #16+#17 |

---

## 1. Konsolidierte Test-Liste (16 Tests)

| # | Test | Datei | Was |
|---|---|---|---|
| 1 | btn_remeasure removed | `test_p1_bundle1.py` | hasattr-False |
| 2 | P1.15 grep-Verifikation | `test_p1_bundle1.py` | Static-Source-Read |
| 3 | block_timestamps appended | `test_qso_panel_rolling.py` | `_append_colored` |
| 4 | _auto_trim_by_age — 5/10 alt | `test_qso_panel_rolling.py` | mock time.time |
| 5 | _auto_trim_by_age unter Schwelle | `test_qso_panel_rolling.py` | mock time.time |
| 6 | clear_resync defensive | `test_qso_panel_rolling.py` | log_view.clear() |
| 7 | scroll_at_bottom_preserved | `test_qso_panel_rolling.py` | scrollbar-API |
| 8 | empty_dict | `test_local_conditions.py` | pure logic |
| 9 | 31_stations_strong | `test_local_conditions.py` | pure logic |
| 10 | 2_stations_weak | `test_local_conditions.py` | pure logic |
| 11 | 8_stations_borderline | `test_local_conditions.py` | pure logic |
| 12 | no_snr_attr | `test_local_conditions.py` | pure logic |
| 13 | stars_widget render | `test_stars_widget.py` | _ensure_app |
| 14 | stars_widget tooltip | `test_stars_widget.py` | _ensure_app |
| **15** | **two_color timestamp (T1)** | `test_qso_panel_rolling.py` | `_append_two_color` |
| **16** | **stars_widget clamping_low+high (T2)** | `test_stars_widget.py` | score=0 + score=6 |

---

## 2. Code-Diffs (final, alle V1+V2-Korrekturen)

### 2.1 `main.py:16` (V2-Korrektur L5)
```diff
-APP_VERSION = "0.95.5"
+APP_VERSION = "0.95.6"
```

### 2.2 `ui/control_panel.py` (P1.6 + P1.12 + P1.19)

**Z.506-526 (P1.12):**
- Z.508-509: `addSpacing(36)` raus
- Z.516-525: `btn_remeasure` Definition raus

**Z.875-885 (P1.19 in `_QSOStatusCard`):**
- `snr_label` → `conditions_widget` (StarsConditionWidget)
- Import `from ui.widgets.stars_widget import StarsConditionWidget` am Top

**Z.947 (P1.12):** `remeasure_clicked = Signal()` raus

**Z.1023-1024 (P1.12):** Connect-Code raus

**Z.1065 (P1.19):** `self.snr_label = qso_card.snr_label` → `self.conditions_widget = qso_card.conditions_widget`

**Z.1086-1090 (P1.6):** `color: #333` → `color: #666`

**Z.1584-1585 (P1.19):** `update_snr` als No-Op + neue Methode `update_local_conditions`

### 2.3 `ui/main_window.py` (P1.12 + P1.15)

**Z.530 (P1.12):** `remeasure_clicked.connect(...)` raus

**Z.917-934 (P1.15):** Block kompletter Inhalt → `pass` (oder `if`-Block ganz raus)

### 2.4 `ui/mw_radio.py` (P1.12)

**Z.985-997:** `_on_diversity_remeasure` Methode komplett raus

### 2.5 `ui/qso_panel.py` (P1.16)

**`__init__`:** Cleanup-Timer + `_block_timestamps` Liste

**`_append_colored` (Z.241-249):** `self._block_timestamps.append(time.time())` ergaenzt

**`_append_two_color` (Z.251-264):** `self._block_timestamps.append(time.time())` ergaenzt

**`_auto_trim` (Z.266-276):** ersetzt durch `_auto_trim_by_age` mit:
- KP2 Resync (`_block_timestamps[-blockCount():]`)
- Scroll-Position-Logik
- Mindest-Schwelle 5

**`add_tx` Z.176:** `self._auto_trim()` Aufruf entfernen

### 2.6 `ui/mw_cycle.py` (P1.19)

**Top-Level Helper hinzu:**
```python
def compute_local_conditions(stations: dict) -> tuple[int, int, float]:
    """5-Sterne-Score aus Stations-Dict."""
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
    if n >= 25 or median > -12: return 5, n, median
    if n >= 15 or median > -15: return 4, n, median
    if n >= 8 or median > -18: return 3, n, median
    if n >= 3 or median > -22: return 2, n, median
    return 1, n, median
```

**Aufruf in `_on_cycle_decoded` nach Z.418 (`_log_stats`):**
```python
        # P1.19: Sterne-Anzeige (immer, auch bei leerem Slot)
        stations = (self._diversity_stations
                    if self._rx_mode == "diversity"
                    else self._normal_stations)
        score, n_st, median = compute_local_conditions(stations)
        self.control_panel.update_local_conditions(score, n_st, median)
```

### 2.7 NEU `ui/widgets/__init__.py`
```python
"""UI-Widgets — wiederverwendbare Custom-Widgets."""
from ui.widgets.stars_widget import StarsConditionWidget

__all__ = ["StarsConditionWidget"]
```

### 2.8 NEU `ui/widgets/stars_widget.py`
```python
"""StarsConditionWidget — 5-Sterne-Anzeige fuer lokale Conditions."""
from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel


class StarsConditionWidget(QWidget):
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
        score = max(1, min(5, int(score)))
        for i, lbl in enumerate(self._stars):
            if i < score:
                lbl.setStyleSheet(self._STAR_ACTIVE_STYLE)
            else:
                lbl.setStyleSheet(self._STAR_INACTIVE_STYLE)
        self.setToolTip(tooltip)
```

---

## 3. Test-Files (final, ohne pytest-qt)

### 3.1 NEU `tests/test_p1_bundle1.py`
```python
"""P1-Bundle1: P1.12 + P1.15 statische Tests."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from pathlib import Path
from PySide6.QtWidgets import QApplication


def _ensure_app():
    return QApplication.instance() or QApplication([])


def test_p1_12_btn_remeasure_removed():
    """P1.12: btn_remeasure muss entfernt sein."""
    _ensure_app()
    from ui.control_panel import ControlPanel
    cp = ControlPanel()
    assert not hasattr(cp, 'btn_remeasure')


def test_p1_15_no_arrow_call_in_status():
    """P1.15: → {their_call}-Setzung in main_window.py darf nicht existieren."""
    src = (Path(__file__).parent.parent / "ui" / "main_window.py").read_text()
    assert "→ {their_call}" not in src


def test_p1_12_remeasure_signal_removed():
    """P1.12: remeasure_clicked Signal-Definition raus."""
    src = (Path(__file__).parent.parent / "ui" / "control_panel.py").read_text()
    assert "remeasure_clicked = Signal()" not in src


def test_p1_12_handler_removed():
    """P1.12: _on_diversity_remeasure Methode raus."""
    src = (Path(__file__).parent.parent / "ui" / "mw_radio.py").read_text()
    assert "_on_diversity_remeasure" not in src
```

### 3.2 NEU `tests/test_qso_panel_rolling.py`
```python
"""P1.16: QSO-Panel 5-Min-Rolling-Window."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from unittest.mock import patch
from PySide6.QtWidgets import QApplication


def _ensure_app():
    return QApplication.instance() or QApplication([])


def _make_panel():
    _ensure_app()
    from ui.qso_panel import QSOPanel
    return QSOPanel()


def test_qso_panel_block_timestamps_appended():
    panel = _make_panel()
    initial = len(panel._block_timestamps)
    panel._append_colored("test", "#FFF")
    assert len(panel._block_timestamps) == initial + 1


def test_qso_panel_two_color_timestamp_appended():
    """T1: _append_two_color setzt auch Timestamp."""
    panel = _make_panel()
    initial = len(panel._block_timestamps)
    panel._append_two_color("a", "#F00", "b", "#0F0")
    assert len(panel._block_timestamps) == initial + 1


def test_qso_panel_auto_trim_by_age():
    panel = _make_panel()
    base = 1_000_000.0
    for i in range(10):
        with patch('ui.qso_panel.time.time', return_value=base + i*60):
            panel._append_colored(f"test{i}", "#FFF")
    with patch('ui.qso_panel.time.time', return_value=base + 600):
        panel._auto_trim_by_age(max_age_s=300.0)
    assert len(panel._block_timestamps) <= 5


def test_qso_panel_trim_below_threshold():
    panel = _make_panel()
    base = 1_000_000.0
    for i in range(4):
        with patch('ui.qso_panel.time.time', return_value=base + i):
            panel._append_colored(f"old{i}", "#FFF")
    before = len(panel._block_timestamps)
    with patch('ui.qso_panel.time.time', return_value=base + 1000):
        panel._auto_trim_by_age(max_age_s=300.0)
    assert len(panel._block_timestamps) == before


def test_qso_panel_clear_resync():
    panel = _make_panel()
    for i in range(10):
        panel._append_colored(f"x{i}", "#FFF")
    panel.log_view.clear()
    panel._auto_trim_by_age(max_age_s=300.0)
    assert len(panel._block_timestamps) <= panel.log_view.document().blockCount()


def test_qso_panel_scroll_at_bottom_preserved():
    panel = _make_panel()
    base = 1_000_000.0
    for i in range(20):
        with patch('ui.qso_panel.time.time', return_value=base + i*30):
            panel._append_colored(f"line{i}", "#FFF")
    sb = panel.log_view.verticalScrollBar()
    sb.setValue(sb.maximum())
    bottom_before = sb.value()
    with patch('ui.qso_panel.time.time', return_value=base + 600):
        panel._auto_trim_by_age(max_age_s=300.0)
    # Nach Trim wieder am Bottom (oder zumindest am neuen Bottom)
    assert sb.value() >= bottom_before - 5 or sb.value() == sb.maximum()
```

### 3.3 NEU `tests/test_local_conditions.py`
```python
"""P1.19: compute_local_conditions Logik-Tests."""


class _Station:
    def __init__(self, snr):
        self.snr = snr


def test_local_conditions_empty_dict():
    from ui.mw_cycle import compute_local_conditions
    score, n, median = compute_local_conditions({})
    assert score == 1 and n == 0 and median == -99.0


def test_local_conditions_31_stations_strong():
    from ui.mw_cycle import compute_local_conditions
    stations = {f"call{i}": _Station(-10) for i in range(31)}
    score, n, _ = compute_local_conditions(stations)
    assert score == 5 and n == 31


def test_local_conditions_2_stations_weak():
    from ui.mw_cycle import compute_local_conditions
    stations = {f"call{i}": _Station(-25) for i in range(2)}
    score, n, _ = compute_local_conditions(stations)
    assert score == 1 and n == 2


def test_local_conditions_8_stations_borderline():
    from ui.mw_cycle import compute_local_conditions
    stations = {f"call{i}": _Station(-19) for i in range(8)}
    score, n, _ = compute_local_conditions(stations)
    assert score == 3 and n == 8


def test_local_conditions_no_snr_attr():
    from ui.mw_cycle import compute_local_conditions
    class NoSNR:
        pass
    stations = {f"call{i}": NoSNR() for i in range(5)}
    score, n, _ = compute_local_conditions(stations)
    assert score == 1 and n == 0
```

### 3.4 NEU `tests/test_stars_widget.py`
```python
"""P1.19: StarsConditionWidget Render-Tests."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication


def _ensure_app():
    return QApplication.instance() or QApplication([])


def _make_widget():
    _ensure_app()
    from ui.widgets.stars_widget import StarsConditionWidget
    return StarsConditionWidget()


def test_stars_widget_set_score_renders():
    w = _make_widget()
    w.set_score(3)
    actives = sum(1 for lbl in w._stars if "#00DDFF" in lbl.styleSheet())
    assert actives == 3


def test_stars_widget_tooltip():
    w = _make_widget()
    w.set_score(5, "31 Stationen, Median -10 dB")
    assert w.toolTip() == "31 Stationen, Median -10 dB"


def test_stars_widget_clamping_low():
    """T2: score=0 → 1 Stern aktiv (clamping)."""
    w = _make_widget()
    w.set_score(0)
    actives = sum(1 for lbl in w._stars if "#00DDFF" in lbl.styleSheet())
    assert actives == 1


def test_stars_widget_clamping_high():
    """T2: score=6 → 5 Sterne aktiv (clamping)."""
    w = _make_widget()
    w.set_score(6)
    actives = sum(1 for lbl in w._stars if "#00DDFF" in lbl.styleSheet())
    assert actives == 5
```

---

## 4. Implementation-Reihenfolge

1. APP_VERSION bump + Doku-vorbereitend
2. P1.6 (Color-Fix, 1 Zeile)
3. P1.12 (NEU-Button raus, 5 Stellen)
4. P1.15 (Status-Zeile raus, 1 Stelle)
5. NEU `ui/widgets/__init__.py` + `stars_widget.py`
6. P1.19 control_panel.py Refactor (snr_label → conditions_widget)
7. P1.19 mw_cycle.py Helper + Aufruf
8. P1.16 qso_panel.py Refactor (rolling-window)
9. Test-Files schreiben (16 Tests)
10. `pytest tests/ -q` → alle gruen
11. App-Smoke-Test (start, click, check)
12. Atomarer Code-Commit + Doku-Commit

---

## 5. Akzeptanz (final)

- [ ] APP_VERSION 0.95.6
- [ ] 16 neue Tests gruen
- [ ] 777 + 16 = 793 Tests gruen total
- [ ] App startet, smoke OK
- [ ] HISTORY.md, HANDOFF.md, CLAUDE.md, TODO.md aktualisiert
- [ ] Atomarer Commit + Doku-Commit

---

**Plan-V3 Ende. Implementation darf starten.**
