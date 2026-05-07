# P1.ANTENNE-COLLAPSE V3 — Final-Plan (Compact-fest, R1-freigegeben)

**Stand:** 2026-05-06.
**Workflow:** V1 → V2 → R1 ✅ („Plan freigegeben mit konkreten KP-Korrekturen") → **V3 (diese Datei)** → Mike-Freigabe → Code.
**R1-Empfehlung:** „Minimales Risiko, sauber durchführbar, KISS-konform."

**Compact-fest:** Diese Datei enthält ALLE Diffs. Nach Compact aus
hier lesen und umsetzen. Reihenfolge zwingend einhalten.

---

## 1. Mike's Designentscheidung (NICHT verhandelbar)

`_AntenneCard` (`ui/control_panel.py:421-590`) wird einklappbar:

- Toggle-Button im Header (links vor „ANTENNE")
- Klick → Body-Container `setVisible(not visible)`
- State persistiert in `Settings._data["antenne_card_collapsed"]`
- Beim App-Start: State aus Settings geladen
- Default-State: `False` (= aufgeklappt)

**KISS:** instant hide/show, keine Animation, kein Keyboard-Shortcut.

---

## 2. Konkrete Diffs (Compact-fest)

### Diff 1 — `ui/control_panel.py:421-590` `_AntenneCard.__init__` Refactor

**Block-Refactor:** Body-Inhalt (alles zwischen Header und Ende) in
einen `_body_widget`-Container umziehen. Header (`lbl_ant`) wird in ein
neues `header_row`-`QHBoxLayout` mit Toggle-Button.

```python
class _AntenneCard(QFrame):
    """Kachel 2 (grün) — ANTENNE alleine (NORMAL/DIVERSITY/EINMESSEN + LED).

    P1.ANTENNE-COLLAPSE (v0.95.11): Body ist einklappbar via Toggle-Button
    im Header. State persistiert in Settings, wird vom MainWindow geladen.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("card")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(_CARD_SS_GREEN)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 8, 10, 8)
        lay.setSpacing(5)

        # ── Header-Row: Toggle-Button + ANTENNE-Label ─────────────────────
        header_row = QHBoxLayout()
        header_row.setContentsMargins(0, 0, 0, 0)
        header_row.setSpacing(6)

        self.toggle_btn = QPushButton("▼")
        self.toggle_btn.setFixedSize(20, 20)
        self.toggle_btn.setFlat(True)
        self.toggle_btn.setStyleSheet(
            "QPushButton { background: transparent; color: #55BBAA; "
            "border: none; font-size: 11px; font-weight: bold; padding: 0; }"
            "QPushButton:hover { color: #88EECC; }"
        )
        self.toggle_btn.setToolTip("Antennen-Kachel ein-/ausklappen")
        self.toggle_btn.clicked.connect(self._toggle_collapsed)
        header_row.addWidget(self.toggle_btn)

        lbl_ant = QLabel("ANTENNE")
        lbl_ant.setStyleSheet(f"color: #55BBAA; font-size: 10px; "
                              f"font-family: {_FONT}; font-weight: bold;")
        header_row.addWidget(lbl_ant)
        header_row.addStretch()
        lay.addLayout(header_row)

        # ── Body-Container (einklappbar) ──────────────────────────────────
        self._body_widget = QWidget()
        body_lay = QVBoxLayout(self._body_widget)
        body_lay.setContentsMargins(0, 0, 0, 0)  # KP-8: keine doppelten Margins
        body_lay.setSpacing(5)

        # >>> AB HIER: alles bisherige Body-Inhalt unverändert,
        #     nur `lay.add...` → `body_lay.add...` ersetzen <<<

        # btn_row
        btn_row = QHBoxLayout()
        btn_row.setSpacing(4)
        self.btn_normal = QPushButton("NORMAL")
        self.btn_normal.setFixedHeight(28)
        # ... [BISHERIGER CODE Z.440-454 unverändert] ...
        body_lay.addLayout(btn_row)

        self.dx_info = QLabel("")
        # ... [Z.457-458 unverändert] ...
        body_lay.addWidget(self.dx_info)

        # Diversity Ratio Display
        self._div_widget = QWidget()
        # ... [Z.462-516 unverändert] ...
        self._div_widget.setVisible(False)
        body_lay.addWidget(self._div_widget)

        # Frequenz-Histogramm
        self._freq_hist = FrequencyHistogramWidget(self)
        self._freq_hist.setVisible(False)
        body_lay.addWidget(self._freq_hist)

        # TX-Freq Manuell-Eingabe
        self._tx_freq_row = QWidget()
        # ... [Z.526-562 unverändert] ...
        self._tx_freq_row.setVisible(False)
        body_lay.addWidget(self._tx_freq_row)

        # CQ-Freq Countdown
        cq_row_layout = QHBoxLayout()
        # ... [Z.566-589 unverändert] ...
        body_lay.addLayout(cq_row_layout)

        lay.addWidget(self._body_widget)

    # ── Collapse-API ─────────────────────────────────────────────────────
    def set_collapsed(self, collapsed: bool) -> None:
        """Body aus-/einklappen. Setzt Toggle-Icon mit."""
        self._body_widget.setVisible(not collapsed)
        self.toggle_btn.setText("▶" if collapsed else "▼")
        # KP-Empfehlung R1: setMaximumHeight für sauberes Schrumpfen
        if collapsed:
            self.setMaximumHeight(36)  # Header-Höhe + Margins
        else:
            from PySide6.QtWidgets import QWIDGETSIZE_MAX
            self.setMaximumHeight(QWIDGETSIZE_MAX)

    def is_collapsed(self) -> bool:
        return not self._body_widget.isVisible()

    def _toggle_collapsed(self) -> None:
        """Slot für Toggle-Button-Klick. Nur UI — Persistenz übernimmt
        ControlPanel via Signal."""
        self.set_collapsed(not self.is_collapsed())
        self.collapse_changed.emit(self.is_collapsed())

    # Signal für ControlPanel (Persistenz-Hook)
    collapse_changed = Signal(bool)
```

**Wichtig:**
- `Signal(bool)` muss `from PySide6.QtCore import Signal` importieren
  (vermutlich schon im File vorhanden — verifizieren).
- `QWIDGETSIZE_MAX` muss importiert werden.
- `cq_row_layout` ist ein `QHBoxLayout` — beim Umzug `body_lay.addLayout(cq_row_layout)`.

### Diff 2 — `ui/control_panel.py:1022-1045` `ControlPanel._setup_ui`

```diff
         # ── Kachel 2: ANTENNE (grün) ─────────────────────────────────────
         ant_card = _AntenneCard(self)
+        self._ant_card = ant_card  # KP-7: Expose für MainWindow-Collapse-Init
         self.btn_normal = ant_card.btn_normal
         self.btn_diversity = ant_card.btn_diversity
         self.btn_einmessen = ant_card.btn_einmessen
         # ... [bisherige Expose-Lines unverändert] ...
         self.btn_normal.clicked.connect(lambda: self._on_rx_mode_clicked("normal"))
         self.btn_diversity.clicked.connect(lambda: self._on_rx_mode_clicked("diversity"))
         self.btn_einmessen.clicked.connect(self.einmessen_clicked.emit)
+        # P1.ANTENNE-COLLAPSE: Toggle persistiert in Settings (über MainWindow)
+        ant_card.collapse_changed.connect(self._on_antenne_collapse_changed)
         layout.addWidget(ant_card)
```

Plus neues Signal in `ControlPanel`-Klasse + Methode:

```python
# Im Class-Body von ControlPanel (vermutlich am Anfang bei anderen Signals):
antenne_collapse_changed = Signal(bool)

# Neue Methode (vermutlich am Ende der Klasse oder bei _on_*-Methoden):
def _on_antenne_collapse_changed(self, collapsed: bool) -> None:
    """Forward Toggle-Event an MainWindow für Settings-Persistenz."""
    self.antenne_collapse_changed.emit(collapsed)
```

### Diff 3 — `ui/main_window.py:420` Initial-State + Persistenz

```diff
         self.control_panel = ControlPanel(callsign=self.settings.callsign)
+        # P1.ANTENNE-COLLAPSE: Initial-State aus Settings laden + Persistenz-Hook
+        _antenne_collapsed = self.settings.get("antenne_card_collapsed", False)
+        self.control_panel._ant_card.set_collapsed(_antenne_collapsed)
+        self.control_panel.antenne_collapse_changed.connect(
+            self._on_antenne_collapse_changed)
```

Plus neue Methode in `MainWindow` (vermutlich bei anderen `_on_*`-Slots):

```python
def _on_antenne_collapse_changed(self, collapsed: bool) -> None:
    """Persistiert Toggle-State in Settings."""
    self.settings.set("antenne_card_collapsed", collapsed)
    self.settings.save()
```

### Diff 4 — `tests/test_antenne_card.py` (NEU, 10 Tests)

```python
"""Tests fuer P1.ANTENNE-COLLAPSE — _AntenneCard einklappbar.

Prueft Toggle-API, Persistence-Hook und Initial-State-Laden.
"""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication
from ui.control_panel import _AntenneCard


@pytest.fixture
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def card(app):
    return _AntenneCard()


def test_default_expanded(card):
    """Default: Body sichtbar, Toggle zeigt ▼."""
    assert card._body_widget.isVisible() is True
    assert card.toggle_btn.text() == "▼"
    assert card.is_collapsed() is False


def test_set_collapsed_hides_body(card):
    """set_collapsed(True) → Body unsichtbar, Toggle ▶."""
    card.set_collapsed(True)
    assert card._body_widget.isVisible() is False
    assert card.toggle_btn.text() == "▶"
    assert card.is_collapsed() is True


def test_set_collapsed_false_shows_body(card):
    """set_collapsed(False) → Body sichtbar, Toggle ▼."""
    card.set_collapsed(True)
    card.set_collapsed(False)
    assert card._body_widget.isVisible() is True
    assert card.toggle_btn.text() == "▼"


def test_toggle_button_click_collapses(card, qtbot=None):
    """Toggle-Button-Klick → wechselt zwischen sichtbar/unsichtbar."""
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    QTest.mouseClick(card.toggle_btn, Qt.LeftButton)
    assert card.is_collapsed() is True
    QTest.mouseClick(card.toggle_btn, Qt.LeftButton)
    assert card.is_collapsed() is False


def test_toggle_emits_collapse_changed(card):
    """Toggle-Click emitiert collapse_changed-Signal."""
    received = []
    card.collapse_changed.connect(lambda c: received.append(c))
    card._toggle_collapsed()
    assert received == [True]
    card._toggle_collapsed()
    assert received == [True, False]


def test_max_height_set_when_collapsed(card):
    """Bei Collapse: setMaximumHeight = 36, bei Expand: zurück."""
    card.set_collapsed(True)
    assert card.maximumHeight() == 36
    card.set_collapsed(False)
    # QWIDGETSIZE_MAX = 16777215
    assert card.maximumHeight() > 1000


def test_diversity_widget_visibility_preserved_through_toggle(card):
    """Mode-State (_div_widget.setVisible) bleibt durch Toggle erhalten."""
    card._div_widget.setVisible(True)
    card.set_collapsed(True)
    card.set_collapsed(False)
    assert card._div_widget.isVisible() is True


def test_tooltip_set_on_toggle_button(card):
    """Toggle-Button hat Tooltip."""
    assert "ein-/ausklappen" in card.toggle_btn.toolTip().lower()


def test_collapse_with_existing_body_state(card):
    """Body-Children behalten ihre eigene Visibility nach Toggle."""
    card._freq_hist.setVisible(True)
    card._tx_freq_row.setVisible(True)
    card.set_collapsed(True)
    card.set_collapsed(False)
    assert card._freq_hist.isVisible() is True
    assert card._tx_freq_row.isVisible() is True


def test_signal_not_emitted_by_set_collapsed_api(card):
    """set_collapsed() ist Programm-API — emitiert KEIN Signal.
    Nur _toggle_collapsed (User-Klick) emitiert."""
    received = []
    card.collapse_changed.connect(lambda c: received.append(c))
    card.set_collapsed(True)
    card.set_collapsed(False)
    assert received == []
```

---

## 3. Implementations-Reihenfolge (nach Compact)

1. **Files lesen:**
   - `prompts/p1_antenne_collapse_v3.md` (diese Datei)
   - `ui/control_panel.py:421-590` (Body-Inhalt der Card)
   - `ui/control_panel.py:1022-1045` (ControlPanel-Expose)
   - `ui/main_window.py:418-432` (ControlPanel-Construction)

2. **Diff 1** anwenden: `_AntenneCard.__init__` Refactor.
   - Imports prüfen: `Signal`, `QWIDGETSIZE_MAX`.
   - Header-Row + Toggle-Button.
   - `_body_widget` + `body_lay`, alle Body-Widgets umziehen.
   - `set_collapsed`, `is_collapsed`, `_toggle_collapsed`, `collapse_changed`-Signal.

3. **Diff 2** anwenden: `ControlPanel._setup_ui`.
   - `self._ant_card = ant_card`.
   - Signal `antenne_collapse_changed = Signal(bool)` in Klasse.
   - Methode `_on_antenne_collapse_changed`.
   - `ant_card.collapse_changed.connect(...)`.

4. **Diff 3** anwenden: `MainWindow.__init__`.
   - Initial-State aus Settings laden.
   - Persistenz-Slot `_on_antenne_collapse_changed`.

5. **Diff 4** anwenden: `tests/test_antenne_card.py` NEU.

6. **Tests laufen:** `QT_QPA_PLATFORM=offscreen ./venv/bin/python3 -m pytest tests/ -q`
   → erwartet 841 grün (831 + 10 neu).

7. **Field-Test (manuell, optional vor Push):**
   - App starten, Kachel zuklappen, App schliessen, App öffnen
   - → Kachel noch immer zugeklappt
   - Kachel zugeklappt → Bandwechsel → KALIBRIEREN-Button im Hintergrund
     funktioniert (Code-Pfad-Test, R1 KP-8 verifiziert)
   - Kachel öffnen während aktivem QSO → keine Funktionsstörung

8. **Final-R1-Codereview** (Skill Schritt 5b, Pflicht):
   ```bash
   echo "Reviewe P1.ANTENNE-COLLAPSE Implementierung — \
   ui/control_panel.py + ui/main_window.py + tests/test_antenne_card.py. \
   Korrektheit, KISS, Tests, Race-Conditions?" | \
   ./venv/bin/python3 tools/deepseek_review.py ui/control_panel.py \
   ui/main_window.py tests/test_antenne_card.py
   ```

9. **APP_VERSION** in `main.py` 0.95.10 → 0.95.11.

10. **Atomare Commits:**
    - Code+Tests: `P1.ANTENNE-COLLAPSE (v0.95.11): _AntenneCard einklappbar`
    - Doku: `docs (v0.95.11): P1.ANTENNE-COLLAPSE HISTORY+TODO+HANDOFF+CLAUDE`

11. **Doku-Updates** (Pflicht laut Skill Schritt 6):
    - `HISTORY.md` Eintrag v0.95.11 (Mike-Designentscheidung explizit)
    - `HANDOFF.md` beide Pfade
    - `CLAUDE.md` Header beide Pfade + Test-Count 841
    - `TODO.md` P1.ANTENNE-COLLAPSE als ERLEDIGT
    - Memory: neue feedback-Lesson „Mike's Designentscheidung schlägt
      DeepSeek-Konvention bei Hobby-Tool-UI" oder Update bestehender
      Memory.

12. **Push** (NUR nach Mike-Bestätigung): `git push origin main`.

13. **Lessons-Learned** (Skill Schritt 6 final):
    1. Was war an P1.ANTENNE-COLLAPSE überraschend?
    2. Was würde ich rückblickend anders machen?
    3. Welches Memory soll geschrieben werden?

---

## 4. Akzeptanz-Checkliste (final)

```
- [ ] _AntenneCard mit Header-Row + Toggle-Button
- [ ] _body_widget Container mit allen ehemaligen Body-Widgets
- [ ] set_collapsed/is_collapsed/_toggle_collapsed/collapse_changed-Signal
- [ ] body_lay.setContentsMargins(0,0,0,0) (KP-8)
- [ ] setMaximumHeight(36) bei Collapse, QWIDGETSIZE_MAX bei Expand
- [ ] ControlPanel._ant_card-Attribut + antenne_collapse_changed-Signal
- [ ] MainWindow lädt Initial-State + persistiert via Settings
- [ ] 10 Tests in test_antenne_card.py grün
- [ ] 841 Tests gesamt grün (831 + 10)
- [ ] Final-R1-Codereview ohne 🔴-Findings
- [ ] APP_VERSION 0.95.10 → 0.95.11
- [ ] HISTORY/TODO/HANDOFF/CLAUDE updated
- [ ] Atomare Commits erstellt
- [ ] Lessons-Learned beantwortet
```

---

## 5. Risiken & Notbremse

- **Layout-Shrink-Edge-Cases:** `setMaximumHeight(36)` ist konservativ
  geschätzt — falls Card zugeklappt zu klein/zu groß: Wert anpassen,
  KEIN Workflow-Re-Loop. Visueller Test im Field-Test.
- **Signal-Connect-Race:** `MainWindow` connectet
  `antenne_collapse_changed` NACH `set_collapsed(False/True)`-Initial-Call
  → der Initial-Aufruf emitiert kein Signal (set_collapsed ist Programm-API,
  Test 10 sichert das). Persistenz wird also NICHT bei jedem App-Start
  unnötig geschrieben.
- **Compact-Risiko:** Diese Datei MUSS alle Infos für Code enthalten —
  wenn nach Compact etwas fehlt: V3 erweitern und re-loop.
- **Mike's Notbremse:** falls Field-Test zeigt dass Kachel-Schrumpfung
  visuell stört → `setMaximumHeight`-Werte anpassen, KEIN Architektur-
  Re-Design.

---

**Plan-V3 Ende. Bereit für Mike-Freigabe + Code.**
