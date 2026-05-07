# P1.COLLAPSE-RADIO-MODEBAND V2 — Self-Review von V1

**Stand:** 2026-05-07.
**Workflow:** V1 ✅ → **V2 (diese Datei)** → R1 (DeepSeek) → V3 → Compact → Code.
**Aufgabe Self-Review:** mit frischen Augen lesen — was fehlt, was ist
mehrdeutig, was hat V1 uebersehen?

---

## Lessons (L1-L14)

### L1 — Antennen-Pattern ist sauber spiegelbar, ABER `_ModeBandCard`-Refactor ist NICHT-trivial

V1 sagt „analog Antennen-Card". Das stimmt nur bedingt:

- `_AntenneCard.__init__` baut `lay = QVBoxLayout(self)` mit Header-Row +
  body_widget, alle Body-Member (`btn_normal`, `dx_info`, `_div_widget`,
  `_freq_hist`, etc.) liegen IM body_widget. Das war von Anfang an so designt
  in v0.95.11.
- `_ModeBandCard.__init__` baut `lay = QVBoxLayout(self)` direkt + `lay.addLayout(grid)`.
  Das `grid` enthaelt **alle** UI-Elemente (FT8/FT4/FT2-Buttons, Freq-Box,
  Band-Buttons, Prop-Bars). Refactor: das `grid` muss in ein neues
  `body_widget` verlagert werden, dazu braucht der body_widget einen eigenen
  Layout-Container der das Grid haelt.

→ **Lesson:** beide bestehenden Cards (`_ModeBandCard`, `_RadioCard`) sind
NICHT mit Body-Container gebaut. Refactor noetig: `lay` haelt Header-Row +
`_body_widget` (QWidget mit eigenem Layout); aktuelle Inhalte kommen ins
body_widget-Layout. Das ist ~30 Zeilen Indent-Aenderung pro Card, keine
Logik-Aenderung.

### L2 — `freq_label` ist im Modus+Band-Card, NICHT im Radio-Card

Mike's Zitat: „die anzeige mit watt zahl die verstelle ich ja seltener". Das
betrifft die WATT-Anzeige (`self.watt_label` im RadioCard, Z.775). Aber: die
**Frequenz-Anzeige** `self.freq_label` (`14074.000 kHz`, Z.283) ist im
ModeBandCard. Wenn der User Modus+Band-Kachel collapsed, sieht er die Frequenz
nicht mehr.

V1 erwaehnt das in Punkt 7: „Header-Status-Hint im collapsed State — Mike
sagt die Info ist schon woanders sichtbar". → Ist sie das wirklich? Statusbar
zeigt laut CLAUDE.md u.a. `TUNE: xx kHz` aber nur waehrend TUNE.
**Verifikations-Auftrag fuer V3:** grep `_update_statusbar` und schauen ob
Frequenz/Band/Modus permanent in der Statusbar steht.

→ Falls nicht: V3 muss entscheiden:
  (a) Header-Hint einbauen (Frequenz im Modus+Band-Header bei collapsed)
  (b) Ohne, Mike akzeptiert dass er bei collapsed-Modus+Band die Frequenz
      nicht mehr sieht (er weiss eh sein Band, und Settings persistieren
      Band).

V2-Empfehlung: **Variante (b) — KISS.** Mike kann zu jeder Zeit aufklappen.
Hobby-Tool, keine Dauer-Anzeige im Header noetig. Statusbar-Frequenz-Anzeige
waere ein neues Feature im falschen Plan.

### L3 — `_RadioCard` Header-Label „RADIO" ist KEIN eigenstaendiges Element

Z.663-665:
```python
lbl_radio = QLabel("RADIO")
lbl_radio.setStyleSheet(...)
lay.addWidget(lbl_radio)
```

Beim Refactor wandert das Label in die Header-Row analog Antennen
(`lbl_ant = QLabel("ANTENNE")`). Code-Analoge:

```python
self.toggle_btn = QPushButton("▼")
...
header_row.addWidget(self.toggle_btn)
lbl_radio = QLabel("RADIO")
lbl_radio.setStyleSheet(f"color: #00aacc; font-size: 10px; ...")
header_row.addWidget(lbl_radio)
header_row.addStretch()
lay.addLayout(header_row)
```

→ **Konsequenz:** kein Doppel-Label, kein Tests-Bruch.

### L4 — `_ModeBandCard` hat KEIN Header-Label aktuell

Z.249-256: direkt zum Grid. Header braucht ein NEUES Label „MODUS / BAND"
(oder kuerzer „MODUS+BAND" / „BAND"). V1-Vorschlag: „MODUS / BAND". V2:
oder vielleicht NUR „BAND", das ist visuell kompakter — aber Modus + Band
sind zusammen im Card, also „MODUS+BAND" ist klarer. **Mike-Entscheidung
unkritisch — V3 nimmt „MODUS+BAND" als Default**, kann Mike spaeter aendern.

### L5 — Init-Loop-Schutz: V1 hat es richtig erkannt, aber Test-Reproduktion fehlt

V1 sagt: AC-6 + Test analog `test_signal_not_emitted_by_set_collapsed_api`.
Wichtig: in V1 nicht einzeln pro Card gefordert. **V3 muss explizit zwei
Tests haben** (einer pro Card), nicht einen, sonst fehlt Coverage.

### L6 — `Settings.get(key, default=False)` ist API-Konform

`config/settings.py:122` `def get(self, key, default=None)` — `False` als
Default ist OK. Wert wird als bool gespeichert (`Settings.set` JSON-roundtrip).
**Verifikation in V3:** existierende Settings-File enthaelt
`antenne_card_collapsed` als bool? grep `~/.simpleft8/settings.json`.

### L7 — `_QWIDGETSIZE_MAX` ist Modul-Konstante in `ui/control_panel.py:14`

V1-erwaehnt aber nicht spezifiziert. V3 nutzt einfach die existierende
Konstante (kein Re-Import).

### L8 — Animation `_PulseBar` weiterlaufen-lassen ist OK

`_pulse[band]["anim"]` ist eine `QPropertyAnimation` die endless cycled
auf `bar.color`. Wenn Body collapsed, ist `bar` nicht sichtbar — Animation
laeuft trotzdem (Qt minimal CPU-Overhead). **Performance-Risiko fast 0**
(Mike's Hardware: M-Mac mit reichlich Reserve). Nicht-stoppen ist sauberer
weil Re-Expand sofort wieder Animation hat ohne Restart-Glitch.

### L9 — `update_propagation` wird WEITER aufgerufen wenn collapsed

`update_propagation` setzt `bar.setVisible()` und `bar.set_color()`. Bei
collapsed body wird `setVisible(True)` keinen Effekt haben (Parent body
selbst ist invisible). Aber: kein Crash, kein Warning. **OK.**

### L10 — `setMaximumHeight(36)` ist konservativ, V2 prueft Werte

Antennen-Card nutzt 36 Pixel. ModeBand-Card hat in der Header-Row dasselbe
Layout (`QHBoxLayout` mit `addWidget(toggle_btn)` + `addWidget(label)` +
`addStretch()`). Sollte mit 36 funktionieren. Radio-Card analog. **Gleiche
Konstante 36 fuer alle drei.** V3 verifiziert visuell + setzt notfalls 38.

### L11 — Test-Datei: ein File oder zwei?

V1: `tests/test_p1_collapse_radio_modeband.py` (ein File). V2-Vorschlag:
EIN File mit zwei Test-Sektionen + ein paar Integration-Tests. Code-
Duplikation pro Card minimal (Fixture + parametrize wo moeglich).

ODER zwei separate Files (`test_modeband_card.py` + `test_radio_card.py`)
analog `test_antenne_card.py`. **V2-Empfehlung:** EIN File `test_p1_collapse_
radio_modeband.py` mit pytest-parametrize (`@pytest.mark.parametrize("card_cls,
title", [(_ModeBandCard, "MODUS+BAND"), (_RadioCard, "RADIO")])`). Spart
Duplikation, klarer Workflow-Bezug.

V3 nimmt EIN File mit Parametrize.

### L12 — Bestehende Tests muessen nicht geaendert werden

Bestehende `test_antenne_card.py` (10 Tests) testet nur `_AntenneCard`,
nicht `ControlPanel` als Ganzes. Refactor von `_ModeBandCard` /
`_RadioCard` beruehrt sie nicht. Aber: **V3 muss laufen lassen** dass
alle bestehenden Tests inkl. `test_antenne_card.py` gruen bleiben.

### L13 — UI-Tests reichen, Headless-Smoke ohne Hardware

Alle Tests laufen mit `QT_QPA_PLATFORM=offscreen`, kein FlexRadio noetig.
Spiegelt `test_antenne_card.py`. Kein Field-Test fuer **Funktionalitaet**
noetig — Mike kann visuell pruefen ob Toggle huebsch aussieht (Radio-Card-
Body collapsed/expanded), aber Code-Korrektheit ist via Tests gesichert.

### L14 — Folge-Bug-Risiko: tx_level_bar ist im RadioCard und unsichtbar

Z.748-749: `self.tx_level_bar = QProgressBar(); self.tx_level_bar.setVisible(False)`.
Bei Refactor: bleibt im Body. Wenn body collapsed → tx_level_bar bleibt
unsichtbar (war's schon). **Nicht-Issue.**

Aber: `self.power_buttons[10].setChecked(True)` (Default 10W vorselektiert)
laeuft im `__init__` BEVOR Body collapsed werden kann (set_collapsed wird
erst nach `__init__` von MainWindow aufgerufen). **OK, kein Bug.**

---

## Konsolidierte Empfehlung fuer V3

### Architektur-Entscheidung

**Pattern 1:1 spiegeln** — Header-Row + body_widget + Collapse-API analog
Antennen-Card. KEIN Status-Hint im Header (KISS, Mike akzeptiert).
KEINE Header-Label-Aenderung in Radio-Card (vorhandenes „RADIO" wandert
nur ins Header-Row-Layout). Modus+Band-Card bekommt **neu** Label
„MODUS+BAND".

### Konkreter Diff-Plan fuer V3

**5 Diffs:**

1. **`ui/control_panel.py:232` `_ModeBandCard.__init__`**:
   - Header-Row mit Toggle-Button („▼") + Label „MODUS+BAND" einfuegen
   - `_body_widget = QWidget()` + `body_lay = QVBoxLayout(_body_widget)`
   - Existierendes `grid` ins `body_lay` umziehen
   - `lay.addWidget(_body_widget)` am Ende
   - Collapse-API-Methoden anhaengen: `set_collapsed`, `is_collapsed`,
     `_toggle_collapsed`, Signal `collapse_changed = Signal(bool)`

2. **`ui/control_panel.py:650` `_RadioCard.__init__`**:
   - Existierendes `lbl_radio` (Z.663-665) in Header-Row mit Toggle-Button
   - `_body_widget` analog
   - PSK-Frame, Power-Row, TX-Frame ins body_lay
   - Collapse-API-Methoden + Signal

3. **`ui/control_panel.py:1036+` `ControlPanel`**:
   - 2 neue Klassen-Signale: `modeband_collapse_changed`, `radio_collapse_changed`
   - 2 Exposes: `self._modeband_card`, `self._radio_card`
   - 2 Forward-Connects (`mb_card.collapse_changed.connect(self.modeband_collapse_changed.emit)`)

4. **`ui/main_window.py:456-461`** (nach existierendem antenne-Block):
   - 2 Initial-Loads + 2 Connects fuer modeband + radio

5. **`ui/main_window.py:861`** (nach `_on_antenne_collapse_changed`):
   - 2 neue Slots: `_on_modeband_collapse_changed`, `_on_radio_collapse_changed`

**+ 1 Diff fuer Tests:**

6. **`tests/test_p1_collapse_radio_modeband.py` NEU** mit pytest-parametrize:
   - 8-9 Tests pro Card (parametrisiert)
   - 2 Integration-Tests (Settings-Persistenz, Unabhaengigkeit)
   - **Total ~16 Tests** (8 parametrize × 2 = 16, plus 2 Integration = 18)
   - Lieber 14-16 als 18 — V3 entscheidet was wirklich Wert hat.

**+ 1 Diff main.py:**

7. **`main.py:16` APP_VERSION 0.95.16 → 0.95.17**

### Test-Schaetzung

```
parametrize cards [_ModeBandCard, _RadioCard]:
  test_default_expanded                          (×2 = 2)
  test_set_collapsed_hides_body                  (×2 = 2)
  test_set_collapsed_false_shows_body            (×2 = 2)
  test_toggle_button_click_collapses             (×2 = 2)
  test_toggle_emits_collapse_changed             (×2 = 2)
  test_max_height_collapsed                      (×2 = 2)
  test_signal_not_emitted_by_set_collapsed_api   (×2 = 2)  ← Init-Loop-Schutz Pflicht
plus:
  test_modeband_and_radio_independent            (×1 = 1)
  test_settings_persist_independently            (×1 = 1)  (mit MainWindow-Stub)
```

→ **16 Tests gesamt.** Tests 902 → 918 gruen.

### Decoder-Verifikation

Nicht relevant — UI-only Aenderung, kein Decoder/Encoder/Stats-Pfad
beruehrt. Karten-Code (`direction_map_widget.py`) unbeeinflusst.

### Gesamt-Aufwand

- 5 Code-Diffs in 2 Files (~80 Zeilen netto neu, davon ~60 Boilerplate
  copy-paste vom Antennen-Pattern)
- 1 NEU-Test-File mit pytest-parametrize (~150 Zeilen)
- 1 main.py-Bump
→ **Sehr klein.** Kein Architektur-Risiko, weil das Pattern bereits
in v0.95.11 etabliert + getestet wurde.

---

## Naechste Schritte

V2 fertig. Weiter mit R1-DeepSeek-Review von V1+V2 zusammen.

R1-Prompt (fuer V3-Vorbereitung):
```
Du reviewst zwei Plans (V1 + V2) fuer P1.COLLAPSE-RADIO-MODEBAND in
SimpleFT8. Mike-Wunsch: Modus+Band + Radio-Kachel einklappbar analog
zur Antennen-Kachel (v0.95.11, atomarer Commit `a0ce1ae`, 10 Tests
in `test_antenne_card.py`).

PRUEFAUFTRAG:
1. Ist das Pattern-Spiegeln korrekt? Edge-Cases gegenueber Antennen-
   Card uebersehen?
2. Refactor-Risiko fuer `_ModeBandCard` (alle UI-Elemente direkt im
   `lay`, jetzt body_widget): bricht das bestehende Member-Refs in
   `ControlPanel` (z.B. `mb_card.btn_ft8` referenziert in Z.1080)?
3. Sollte Frequenz-Anzeige (`freq_label`) im Header sichtbar bleiben
   wenn Modus+Band collapsed (Status-Hint), oder akzeptiert KISS?
4. Tests-Strategie: pytest-parametrize fuer beide Cards in einem File
   sinnvoll oder lieber zwei Files wie `test_antenne_card.py`?
5. R1-Vorbehalt P1.ANTENNE-COLLAPSE (Settings.save Debounce): wieder
   relevant fuer 2 weitere Cards mit demselben Pattern?
6. Risiko-Bewertung: was kann der Refactor kaputt machen das aktuell
   funktioniert? (Propagation-Bars, TUNE-Anzeige, Settings-Persistenz?)
7. APP_VERSION 0.95.17 oder 0.95.16.x?
8. Init-Loop-Schutz: identische Implementierung in beiden neuen Cards
   sicherstellen — was uebersehen?

Antworte strukturiert mit Datei:Zeile-Referenzen.
Halte dich an SimpleFT8-Philosophie: Hobby-Tool, KISS, kein Overengineering.
```

R1-Files mitsenden:
- `prompts/p1_collapse_radio_modeband_v1.md`
- `prompts/p1_collapse_radio_modeband_v2.md` (diese Datei)
- `ui/control_panel.py` (Z.232+650+1036 + Antennen-Card Z.425-647 als Vorbild)
- `ui/main_window.py` (Z.456+861 fuer Antennen-Pattern)
- `tests/test_antenne_card.py` (Test-Vorbild)
