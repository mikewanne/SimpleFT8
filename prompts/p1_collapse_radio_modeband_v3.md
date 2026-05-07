# P1.COLLAPSE-RADIO-MODEBAND V3 — Final-Plan (Compact-fest, R1-freigegeben)

**Stand:** 2026-05-07.
**Workflow:** V1 → V2 → R1 ✅ (Plan freigegeben, 0 KRITISCH-Findings, 5 kleine Hinweise alle in V2/V1 erfasst) → **V3** → Compact → Code.
**Vorgaenger:** v0.95.16 (P1.LOCATOR-SLASH). Tests 902 gruen.
**Compact-fest:** Diese Datei enthaelt ALLE Diffs. Nach Compact direkt Code.

---

## 1. R1-Findings (alle adressiert)

| Finding | Status |
|---|---|
| Pattern-Spiegelung von `_AntenneCard` korrekt | ✅ V3 nutzt 1:1 Pattern |
| Refactor-Risiko `_ModeBandCard` Member-Refs | ✅ R1: `self.btn_ft8`, `self.band_buttons`, `self.freq_label`, `self.prop_bars` bleiben Attribute (werden VOR `grid.addLayout` erstellt). Keine Aenderung an `ControlPanel`-Refs. |
| Frequenz-Anzeige im Header bei collapse | ✅ V2-Empfehlung „weg ist OK" akzeptiert (KISS). Statusbar zeigt Frequenz permanent. |
| Tests-Strategie pytest-parametrize | ✅ EIN File mit `@pytest.mark.parametrize("card_cls, title", [...])`, 16 Tests. |
| R1-Vorbehalt Settings.save Debounce | ✅ Nicht relevant (Mike's M-Mac, <10ms save). |
| TUNE-Anzeige bei collapsed Radio-Card | ✅ Statusbar zeigt TUNE-Status (`_update_statusbar`). User sieht's auch wenn Card collapsed. |
| APP_VERSION 0.95.17 | ✅ Patch +0.01 (Feature). |
| Init-Loop-Schutz pro Card | ✅ 2 Unit-Tests parametrisiert (`test_signal_not_emitted_by_set_collapsed_api`). |
| Default-State `False` (ausgeklappt) | ✅ `Settings.get(key, default=False)`. |

---

## 2. Konkrete Diffs (Compact-fest)

### Diff 1 — `ui/control_panel.py:232` `_ModeBandCard` Refactor

**Aktuell (Z.235-247):**
```python
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("card")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(_CARD_SS_BLUE)

        # Pulsier-State pro Band: ...
        self._pulse: dict = {}

        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 10, 10, 10)
        lay.setSpacing(8)
```

**Neu (Header-Row + body_widget einfuegen, Klassen-Signal als Klassenattribut):**

```python
class _ModeBandCard(QFrame):
    """Kachel 1 (blau) — Modus (FT8/FT4) + Band-Auswahl.

    P1.COLLAPSE-RADIO-MODEBAND (v0.95.17): Body ist einklappbar via
    Toggle-Button im Header. State persistiert in Settings, wird vom
    MainWindow geladen.
    """

    collapse_changed = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("card")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(_CARD_SS_BLUE)

        # Pulsier-State pro Band: {band: {"state": (cond_now, cond_60, fast),
        # "anim": QPropertyAnimation}} — leer wenn statisch.
        self._pulse: dict = {}

        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 10, 10, 10)
        lay.setSpacing(8)

        # ── Header-Row: Toggle-Button + MODUS+BAND-Label ─────────────────
        header_row = QHBoxLayout()
        header_row.setContentsMargins(0, 0, 0, 0)
        header_row.setSpacing(6)

        self.toggle_btn = QPushButton("▼")
        self.toggle_btn.setFixedSize(20, 20)
        self.toggle_btn.setFlat(True)
        self.toggle_btn.setStyleSheet(
            "QPushButton { background: transparent; color: #7799FF; "
            "border: none; font-size: 11px; font-weight: bold; padding: 0; }"
            "QPushButton:hover { color: #99BBFF; }"
        )
        self.toggle_btn.setToolTip("Modus+Band-Kachel ein-/ausklappen")
        self.toggle_btn.clicked.connect(self._toggle_collapsed)
        header_row.addWidget(self.toggle_btn)

        lbl_mb = QLabel("MODUS+BAND")
        lbl_mb.setStyleSheet(
            f"color: #7799FF; font-size: 10px; font-family: {_FONT}; font-weight: bold;"
        )
        header_row.addWidget(lbl_mb)
        header_row.addStretch()
        lay.addLayout(header_row)

        # ── Body-Container (einklappbar) ─────────────────────────────────
        self._body_widget = QWidget()
        body_lay = QVBoxLayout(self._body_widget)
        body_lay.setContentsMargins(0, 0, 0, 0)
        body_lay.setSpacing(0)

        # ── Alles in einem Grid → exakte Spalten-Ausrichtung ─────
        # ... (existierender Grid-Code von Z.249-330 unveraendert UEBERNEHMEN,
        #      aber statt `lay.addLayout(grid)` am Ende: `body_lay.addLayout(grid)`)
        # ... [Grid-Aufbau wie bisher: btn_ft8, btn_ft4, btn_ft2, freq_frame,
        #      band_buttons, prop_bars]
        body_lay.addLayout(grid)

        # ── Body-Container an Card-Layout anhaengen ──────────────────────
        lay.addWidget(self._body_widget)
```

**Konkrete Aenderung:** Z.245 `lay = QVBoxLayout(self)`-Block beibehalten,
**davor** `collapse_changed = Signal(bool)` als Klassenattribut. **Nach**
`lay.setSpacing(8)` Header-Row einfuegen + `_body_widget` + `body_lay`.
**`grid` und `lay.addLayout(grid)`-Zeilen-Aenderung:** alle Member-Erstellungen
(`self.btn_ft8 = QPushButton(...)`, `grid.addWidget(...)`-Aufrufe) unveraendert
lassen. **Nur Z.330** `lay.addLayout(grid)` ersetzen durch:
```python
body_lay.addLayout(grid)
lay.addWidget(self._body_widget)
```

**Plus Collapse-API ans Ende der Klasse einfuegen** (vor `def update_propagation`,
genauer nach dem `__init__`-Block aber vor dem ersten Method-Def):

```python
    # ── Collapse-API ─────────────────────────────────────────────────────
    def set_collapsed(self, collapsed: bool) -> None:
        """Body aus-/einklappen. Setzt Toggle-Icon + MaximumHeight.

        Programm-API — emitiert KEIN collapse_changed-Signal (Init-Loop-
        Schutz). User-Klick geht ueber _toggle_collapsed.
        """
        self._body_widget.setVisible(not collapsed)
        self.toggle_btn.setText("▶" if collapsed else "▼")
        if collapsed:
            self.setMaximumHeight(36)
        else:
            self.setMaximumHeight(_QWIDGETSIZE_MAX)

    def is_collapsed(self) -> bool:
        return not self._body_widget.isVisible()

    def _toggle_collapsed(self) -> None:
        """Slot fuer Toggle-Button-Klick. Persistenz ueber Signal."""
        self.set_collapsed(not self.is_collapsed())
        self.collapse_changed.emit(self.is_collapsed())
```

### Diff 2 — `ui/control_panel.py:650` `_RadioCard` Refactor

**Aktuell (Z.659-665):**
```python
        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 8, 10, 8)
        lay.setSpacing(5)

        lbl_radio = QLabel("RADIO")
        lbl_radio.setStyleSheet(f"color: #00aacc; font-size: 10px; font-family: {_FONT}; font-weight: bold;")
        lay.addWidget(lbl_radio)
```

**Neu:** existierendes `lbl_radio` in Header-Row + body_widget.

```python
class _RadioCard(QFrame):
    """Kachel 3 (tuerkis) — RADIO Controls (PSK, Freq, Power, TUNE, ALC, TX).

    P1.COLLAPSE-RADIO-MODEBAND (v0.95.17): Body ist einklappbar via
    Toggle-Button im Header. State persistiert in Settings, wird vom
    MainWindow geladen.
    """

    collapse_changed = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("card")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(_CARD_SS_TEAL)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 8, 10, 8)
        lay.setSpacing(5)

        # ── Header-Row: Toggle-Button + RADIO-Label ──────────────────────
        header_row = QHBoxLayout()
        header_row.setContentsMargins(0, 0, 0, 0)
        header_row.setSpacing(6)

        self.toggle_btn = QPushButton("▼")
        self.toggle_btn.setFixedSize(20, 20)
        self.toggle_btn.setFlat(True)
        self.toggle_btn.setStyleSheet(
            "QPushButton { background: transparent; color: #00aacc; "
            "border: none; font-size: 11px; font-weight: bold; padding: 0; }"
            "QPushButton:hover { color: #44CCEE; }"
        )
        self.toggle_btn.setToolTip("Radio-Kachel ein-/ausklappen")
        self.toggle_btn.clicked.connect(self._toggle_collapsed)
        header_row.addWidget(self.toggle_btn)

        lbl_radio = QLabel("RADIO")
        lbl_radio.setStyleSheet(
            f"color: #00aacc; font-size: 10px; font-family: {_FONT}; font-weight: bold;"
        )
        header_row.addWidget(lbl_radio)
        header_row.addStretch()
        lay.addLayout(header_row)

        # ── Body-Container (einklappbar) ─────────────────────────────────
        self._body_widget = QWidget()
        body_lay = QVBoxLayout(self._body_widget)
        body_lay.setContentsMargins(0, 0, 0, 0)
        body_lay.setSpacing(5)

        _SEP_SS = "background: #445544; max-height: 1px; min-height: 1px;"

        # ── Sektion 1: PSK Info + Map ────────────────────────────────────
        # ... (existierender PSK-Frame-Code Z.669-691 unveraendert,
        #      aber statt `lay.addWidget(psk_frame)` am Ende: `body_lay.addWidget(psk_frame)`)
        body_lay.addWidget(psk_frame)

        # ── Sektion 2: Power Buttons ─────────────────────────────────────
        # ... (existierender Power-Code Z.694-720 unveraendert,
        #      aber `lay.addLayout(power_row)` → `body_lay.addLayout(power_row)`)
        body_lay.addLayout(power_row)

        # ── Sektion 3: TX Status (gerahmt) ───────────────────────────────
        # ... (existierender TX-Frame-Code Z.722-792 unveraendert,
        #      aber `lay.addWidget(tx_frame)` am Ende: `body_lay.addWidget(tx_frame)`)
        body_lay.addWidget(tx_frame)

        # ── Body-Container an Card-Layout anhaengen ──────────────────────
        lay.addWidget(self._body_widget)
```

**Plus Collapse-API ans Ende der Klasse:**

```python
    # ── Collapse-API ─────────────────────────────────────────────────────
    def set_collapsed(self, collapsed: bool) -> None:
        """Body aus-/einklappen. Setzt Toggle-Icon + MaximumHeight.

        Programm-API — emitiert KEIN collapse_changed-Signal (Init-Loop-
        Schutz). User-Klick geht ueber _toggle_collapsed.
        """
        self._body_widget.setVisible(not collapsed)
        self.toggle_btn.setText("▶" if collapsed else "▼")
        if collapsed:
            self.setMaximumHeight(36)
        else:
            self.setMaximumHeight(_QWIDGETSIZE_MAX)

    def is_collapsed(self) -> bool:
        return not self._body_widget.isVisible()

    def _toggle_collapsed(self) -> None:
        """Slot fuer Toggle-Button-Klick. Persistenz ueber Signal."""
        self.set_collapsed(not self.is_collapsed())
        self.collapse_changed.emit(self.is_collapsed())
```

**Konkrete Aenderung:** Z.663-665 `lbl_radio` raus aus `lay.addWidget`, in
Header-Row. Z.666 `_SEP_SS` inline in body_lay-Block. Alle 3 `lay.addWidget(...)`-
Aufrufe (Z.691 psk_frame, Z.720 power_row, Z.792 tx_frame) → `body_lay`.

### Diff 3 — `ui/control_panel.py:1036` `ControlPanel`-Klasse Signale

**Aktuell (Z.1036):**
```python
    antenne_collapse_changed = Signal(bool)  # P1.ANTENNE-COLLAPSE → MainWindow
```

**Neu:**
```python
    antenne_collapse_changed = Signal(bool)  # P1.ANTENNE-COLLAPSE → MainWindow
    modeband_collapse_changed = Signal(bool)  # P1.COLLAPSE-RADIO-MODEBAND → MainWindow
    radio_collapse_changed = Signal(bool)     # P1.COLLAPSE-RADIO-MODEBAND → MainWindow
```

### Diff 4 — `ui/control_panel.py:1075` `_setup_ui` Card-Connects

**Aktuell (Z.1078-1085 — `_ModeBandCard`-Block):**
```python
        mb_card = _ModeBandCard(self)
        # ... existierende Member-Refs:
        self.btn_ft8 = mb_card.btn_ft8
        ...
        layout.addWidget(mb_card)
```

**Neu (zwei neue Zeilen einfuegen):**
```python
        mb_card = _ModeBandCard(self)
        self._modeband_card = mb_card  # P1.COLLAPSE-RADIO-MODEBAND: expose for MainWindow init
        # ... existierende Member-Refs UNVERAENDERT
        ...
        # P1.COLLAPSE-RADIO-MODEBAND: Toggle-Signal forwarden
        mb_card.collapse_changed.connect(self.modeband_collapse_changed.emit)
        layout.addWidget(mb_card)
```

**Aktuell (Z.1117 — `_RadioCard`-Block):**
```python
        radio_card = _RadioCard(self)
        self.psk_label = radio_card.psk_label
        ...
        layout.addWidget(radio_card)
```

**Neu (zwei neue Zeilen einfuegen):**
```python
        radio_card = _RadioCard(self)
        self._radio_card = radio_card  # P1.COLLAPSE-RADIO-MODEBAND: expose for MainWindow init
        # ... existierende Member-Refs UNVERAENDERT
        ...
        # P1.COLLAPSE-RADIO-MODEBAND: Toggle-Signal forwarden
        radio_card.collapse_changed.connect(self.radio_collapse_changed.emit)
        layout.addWidget(radio_card)
```

### Diff 5 — `ui/main_window.py:456-461` Initial-State + Connect

**Aktuell:**
```python
        self.control_panel = ControlPanel(callsign=self.settings.callsign)
        # P1.ANTENNE-COLLAPSE: Initial-State aus Settings laden + Persistenz-Hook
        _antenne_collapsed = self.settings.get("antenne_card_collapsed", False)
        self.control_panel._ant_card.set_collapsed(_antenne_collapsed)
        self.control_panel.antenne_collapse_changed.connect(
            self._on_antenne_collapse_changed)
```

**Neu (NACH dem antenne-Block):**
```python
        self.control_panel = ControlPanel(callsign=self.settings.callsign)
        # P1.ANTENNE-COLLAPSE: Initial-State aus Settings laden + Persistenz-Hook
        _antenne_collapsed = self.settings.get("antenne_card_collapsed", False)
        self.control_panel._ant_card.set_collapsed(_antenne_collapsed)
        self.control_panel.antenne_collapse_changed.connect(
            self._on_antenne_collapse_changed)
        # P1.COLLAPSE-RADIO-MODEBAND (v0.95.17): Initial-State + Persistenz
        _modeband_collapsed = self.settings.get("modeband_card_collapsed", False)
        self.control_panel._modeband_card.set_collapsed(_modeband_collapsed)
        self.control_panel.modeband_collapse_changed.connect(
            self._on_modeband_collapse_changed)
        _radio_collapsed = self.settings.get("radio_card_collapsed", False)
        self.control_panel._radio_card.set_collapsed(_radio_collapsed)
        self.control_panel.radio_collapse_changed.connect(
            self._on_radio_collapse_changed)
```

### Diff 6 — `ui/main_window.py:861` Slot-Methods

**Aktuell:**
```python
    def _on_antenne_collapse_changed(self, collapsed: bool) -> None:
        """P1.ANTENNE-COLLAPSE: persistent state in settings."""
        self.settings.set("antenne_card_collapsed", collapsed)
```

**Neu (zwei zusaetzliche Methoden DARUNTER einfuegen):**
```python
    def _on_antenne_collapse_changed(self, collapsed: bool) -> None:
        """P1.ANTENNE-COLLAPSE: persistent state in settings."""
        self.settings.set("antenne_card_collapsed", collapsed)

    def _on_modeband_collapse_changed(self, collapsed: bool) -> None:
        """P1.COLLAPSE-RADIO-MODEBAND: persist Modus+Band-Card collapse state."""
        self.settings.set("modeband_card_collapsed", collapsed)

    def _on_radio_collapse_changed(self, collapsed: bool) -> None:
        """P1.COLLAPSE-RADIO-MODEBAND: persist Radio-Card collapse state."""
        self.settings.set("radio_card_collapsed", collapsed)
```

### Diff 7 — `tests/test_p1_collapse_radio_modeband.py` (NEU)

```python
"""Tests fuer P1.COLLAPSE-RADIO-MODEBAND (v0.95.17).

Modus+Band-Card und Radio-Card sind einklappbar analog zur Antennen-
Kachel (v0.95.11). Beide unabhaengig, Settings-persistiert. Mike-
Anweisung 2026-05-07: „radio und mouds haette ich gerne auch zum
einklappen der kachel wie die Antennen kachel".

Spiegelt `tests/test_antenne_card.py` per pytest-parametrize fuer
beide Cards.
"""
from __future__ import annotations

import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from ui.control_panel import _ModeBandCard, _RadioCard


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture(params=[
    pytest.param(_ModeBandCard, id="modeband"),
    pytest.param(_RadioCard, id="radio"),
])
def card(app, request):
    """Frische Card pro Test (parametrisiert auf beide Klassen)."""
    c = request.param()
    c.show()
    return c


# ── Per-Card-Tests (parametrisiert) ─────────────────────────────────────


def test_default_expanded(card):
    """Default: Body sichtbar, Toggle-Icon ▼."""
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
    """set_collapsed(False) nach True → Body wieder sichtbar."""
    card.set_collapsed(True)
    card.set_collapsed(False)
    assert card._body_widget.isVisible() is True
    assert card.toggle_btn.text() == "▼"
    assert card.is_collapsed() is False


def test_toggle_button_click_collapses(card):
    """Klick auf Toggle-Button → wechselt zwischen sichtbar/unsichtbar."""
    QTest.mouseClick(card.toggle_btn, Qt.LeftButton)
    assert card.is_collapsed() is True
    QTest.mouseClick(card.toggle_btn, Qt.LeftButton)
    assert card.is_collapsed() is False


def test_toggle_emits_collapse_changed(card):
    """_toggle_collapsed (User-Klick-Pfad) emitiert collapse_changed."""
    received = []
    card.collapse_changed.connect(lambda c: received.append(c))
    card._toggle_collapsed()
    assert received == [True]
    card._toggle_collapsed()
    assert received == [True, False]


def test_max_height_set_when_collapsed(card):
    """Bei Collapse: setMaximumHeight=36, bei Expand: zurueck auf MAX."""
    card.set_collapsed(True)
    assert card.maximumHeight() == 36
    card.set_collapsed(False)
    assert card.maximumHeight() > 1000  # _QWIDGETSIZE_MAX = 16777215


def test_tooltip_set_on_toggle_button(card):
    """Toggle-Button hat Tooltip mit 'ein-/ausklappen'-Hint."""
    assert "ein-/ausklappen" in card.toggle_btn.toolTip().lower()


def test_signal_not_emitted_by_set_collapsed_api(card):
    """set_collapsed() (Programm-API) emitiert KEIN Signal.

    Init-Loop-Schutz: MainWindow ruft set_collapsed beim App-Start mit
    Settings-Wert auf — wuerde es ein Signal emittieren, kaeme es zu
    unnoetigem set+save-Roundtrip in Settings.
    Nur _toggle_collapsed (User-Klick) emitiert collapse_changed.
    """
    received = []
    card.collapse_changed.connect(lambda c: received.append(c))
    card.set_collapsed(True)
    card.set_collapsed(False)
    assert received == []


# ── Integration-Tests (kein Parametrize) ────────────────────────────────


def test_modeband_and_radio_independent(app):
    """Beide Karten getrennt togglen — keine gegenseitige Beeinflussung."""
    mb = _ModeBandCard()
    rd = _RadioCard()
    mb.show()
    rd.show()
    mb.set_collapsed(True)
    assert mb.is_collapsed() is True
    assert rd.is_collapsed() is False
    rd.set_collapsed(True)
    assert mb.is_collapsed() is True
    assert rd.is_collapsed() is True
    mb.set_collapsed(False)
    assert mb.is_collapsed() is False
    assert rd.is_collapsed() is True


def test_modeband_card_preserves_button_refs(app):
    """Refactor darf existierende Member-Refs nicht zerstoeren."""
    mb = _ModeBandCard()
    # Diese Refs werden von ControlPanel weiterverwendet (Z.1080-1084):
    assert mb.btn_ft8 is not None
    assert mb.btn_ft4 is not None
    assert mb.btn_ft2 is not None
    assert mb.freq_label is not None
    assert "20m" in mb.band_buttons
    assert "10m" in mb.band_buttons
    assert "20m" in mb.prop_bars


def test_radio_card_preserves_button_refs(app):
    """Refactor darf existierende Member-Refs nicht zerstoeren."""
    rd = _RadioCard()
    assert rd.psk_label is not None
    assert rd.btn_psk_map is not None
    assert rd.btn_tune is not None
    assert rd.watt_label is not None
    assert rd.swr_label is not None
    assert 10 in rd.power_buttons
    assert 100 in rd.power_buttons
```

**Test-Anzahl:** 8 parametrisiert × 2 Cards = 16 + 3 Integration = **19 Tests**.

### Diff 8 — `main.py:16` APP_VERSION

```python
APP_VERSION = "0.95.17"
```

---

## 3. Implementations-Reihenfolge (nach Compact)

1. **Files lesen** (Verifikation):
   - `prompts/p1_collapse_radio_modeband_v3.md` (diese Datei)
   - `ui/control_panel.py` (`_ModeBandCard` Z.232-414, `_RadioCard` Z.650-794, `ControlPanel._setup_ui` Z.1075+)
   - `ui/main_window.py` (Z.456-461 Antennen-Init, Z.861 Slot)
   - `tests/test_antenne_card.py` (Vorbild)
2. **Diff 1** — `_ModeBandCard` Header-Row + body_widget + Collapse-API.
3. **Diff 2** — `_RadioCard` Header-Row + body_widget + Collapse-API.
4. **Diff 3** — `ControlPanel`-Klasse 2 neue Signale.
5. **Diff 4** — `ControlPanel._setup_ui` 2 Exposes + 2 Connects.
6. **Diff 5** — `MainWindow.__init__` 2 Initial-Loads + 2 Connects.
7. **Diff 6** — `MainWindow` 2 neue Slot-Methods.
8. **Diff 7** — `tests/test_p1_collapse_radio_modeband.py` NEU mit 19 Tests.
9. **Diff 8** — `main.py` APP_VERSION 0.95.16 → 0.95.17.
10. **Tests laufen:** `902 → 921 erwartet gruen` (+19).
11. **Final-R1-Codereview:**
    ```bash
    echo "Reviewe P1.COLLAPSE-RADIO-MODEBAND v0.95.17 final-Code.
    _ModeBandCard + _RadioCard einklappbar analog Antennen-Kachel.
    Init-Loop-Schutz, Refactor ohne Member-Ref-Bruch. Tests 902 → 921." | \
    ./venv/bin/python3 tools/deepseek_review.py \
    ui/control_panel.py ui/main_window.py \
    tests/test_p1_collapse_radio_modeband.py
    ```
12. **Atomare Commits:**
    - Code+Tests: `P1.COLLAPSE-RADIO-MODEBAND (v0.95.17): Modus+Band + Radio einklappbar`
    - Doku: `docs (v0.95.17): P1.COLLAPSE-RADIO-MODEBAND HISTORY+HANDOFF+CLAUDE`
13. **Doku-Updates** (HISTORY, HANDOFF beide Pfade, CLAUDE beide Pfade).
14. **Push** NUR nach Mike-Freigabe + visueller App-Test.
15. **Lessons-Learned**.

---

## 4. Akzeptanz-Checkliste (final)

```
- [ ] _ModeBandCard: Header-Row + body_widget + Collapse-API
- [ ] _RadioCard:    Header-Row + body_widget + Collapse-API
- [ ] ControlPanel:  2 Signale + 2 Exposes + 2 Forward-Connects
- [ ] MainWindow:    2 Initial-Loads + 2 Slot-Methods
- [ ] tests/test_p1_collapse_radio_modeband.py: 19 Tests gruen
- [ ] 921 Tests gesamt gruen (902 + 19)
- [ ] Init-Loop-Schutz pro Card via test_signal_not_emitted_by_set_collapsed_api
- [ ] APP_VERSION 0.95.16 → 0.95.17
- [ ] Final-R1 ohne 🔴-Findings
- [ ] HISTORY/HANDOFF/CLAUDE updated (beide Pfade)
- [ ] Atomare Commits
- [ ] Mike-Freigabe fuer Push EXPLIZIT (nach visuellem Test)
- [ ] Lessons-Learned
```

---

## 5. Risiken & Notbremse

- **Refactor-Risiko Member-Refs:** R1 verifiziert: alle `self.btn_ft8`,
  `self.band_buttons`, `self.prop_bars`, `self.freq_label`, `self.psk_label`,
  `self.btn_tune`, `self.watt_label`, `self.swr_label`, `self.power_buttons`,
  `self.tx_level_bar`, `self.peak_label`, `self.tx_level_label`,
  `self.rf_power_label`, `self.btn_psk_map` bleiben Attribute (werden VOR
  body-Layout-Umbau erstellt). ✅
- **Bestehende Tests `test_antenne_card.py`:** unberuehrt — nur `_AntenneCard`
  getestet. ✅
- **Karten-Code (`direction_map_widget.py`):** unbeeinflusst. ✅
- **Statistik-Code:** unbeeinflusst. ✅
- **Kachel-Hoehe bei collapsed:** 36 Pixel reicht laut Antennen-Erfahrung.
  Falls visuell unzureichend: V3 erlaubt Erhoehung auf 38-40 Pixel.
- **Performance:** `setVisible(False)` auf body → Qt versteckt komplett,
  keine Repaints im Body-Subtree. Animations laufen weiter (R1 OK).
- **Compact-Risiko:** alle Diffs konkret in V3, R1 hat freigegeben.

---

## 6. Lessons-Learned-Fragen (Skill Schritt 6 final, nach Code+Push)

1. Was war an P1.COLLAPSE-RADIO-MODEBAND ueberraschend?
2. Was wuerde ich rueckblickend anders machen?
3. Welches Memory soll geschrieben werden? Vorschlag:
   `feedback_pattern_spiegelung_lohnt.md` — Wenn ein Pattern (wie
   Antennen-Card) bereits etabliert + getestet ist, kann der Workflow
   stark verkuerzt werden (V1+V2+R1 in 1 Stunde, Tests parametrisierbar).
   Zeitspar-Lesson fuer aehnliche Folge-Aufgaben.

---

**Plan-V3 Ende. Bereit fuer Compact + Code.**
