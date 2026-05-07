# P1.ANTENNE-COLLAPSE V1 — Antennen-Kachel einklappbar

**Stand:** 2026-05-06.
**Workflow:** **V1 (diese Datei)** → V2 (Self-Review) → R1 (DeepSeek) → V3 → Plan → Code.
**Mike-Anweisung 06.05.:** „Antennen-Fenster Kachel einklappbar machen.
DeepSeek hat in vorheriger Session abgeraten — Mike überschreibt explizit.
SimpleFT8 ist Hobby-Tool, KEIN Contest-Tool, wir machen es so wie wir wollen."

---

## 1. Ziel

`_AntenneCard` (`ui/control_panel.py:421`) bekommt einen Toggle-Button im
Header. Klick → Body wird ein-/ausgeklappt. State wird in `Settings`
persistiert und beim App-Start wieder geladen.

**Use-Case:** Mike funkt stundenlang auf einem Band+Modus. Antennen-
Status (Diversity-Ratio, Phase, Frequenz-Histogramm) ist dann nicht
notwendig auf dem Bildschirm — Kachel wegklappen, mehr Platz für
QSO-Panel + RX-Panel. Bei Bedarf (Bandwechsel, KALIBRIEREN) öffnet er
sie wieder.

**KISS:** Reines Hide/Show des Body-Containers. Keine Animation, kein
Keyboard-Shortcut, keine separate Header-Klasse.

---

## 2. Akzeptanzkriterien

1. Header der `_AntenneCard` zeigt Toggle-Button (z.B. `▼` aufgeklappt /
   `▶` zugeklappt). Position: links neben/vor `lbl_ant` „ANTENNE", oder
   rechts ganz aussen — V2/R1 entscheiden was UX-besser ist.
2. Klick auf Toggle-Button → alle Body-Widgets ausser dem Header werden
   `setVisible(not visible)` durchgeschaltet.
3. Body umfasst: `btn_row` (NORMAL/DIVERSITY/KALIBRIEREN), `dx_info`,
   `_div_widget`, `_freq_hist`, `_tx_freq_row`, `cq_row_layout` (CQ-
   Countdown). Alle in einem gemeinsamen Container `_body_widget`
   bündeln, damit `setVisible(False)` sie als Block ausblendet.
4. Beim Einklappen schrumpft die Kachel auf Header-Höhe (~28-32 px,
   nur ANTENNE-Label + Toggle-Button). Layout darunter rückt nach.
5. State persistiert in `Settings._data["antenne_card_collapsed"]`
   (bool, default `False` = aufgeklappt).
6. Beim App-Start: Settings-Wert lesen → Body initial entsprechend
   sichtbar/versteckt setzen, Toggle-Icon entsprechend.
7. Keine Regression: Diversity-Ratio-Anzeige, KALIBRIEREN-Pipeline,
   Frequenz-Histogramm, TX-Freq-Spinner und CQ-Countdown funktionieren
   wenn Kachel offen ist genauso wie vor dem Fix.
8. Tests grün (831 → ≥ 831 + Coverage für Toggle-Logik + Persistenz).

---

## 3. Betroffene Module/Dateien

- **`ui/control_panel.py:421-590`** — `_AntenneCard.__init__`:
  - `_body_widget = QWidget()` einfügen, `_body_lay = QVBoxLayout(_body_widget)`
  - alle bestehenden Body-Widgets + Layouts in `_body_widget` umziehen
    (statt direkt in `lay`)
  - Header mit Toggle-Button: `QHBoxLayout` mit Toggle-Button + lbl_ant
  - Methode `_toggle_collapsed()` + `set_collapsed(bool)` einführen
- **`ui/control_panel.py:958-1045`** — `ControlPanel`:
  - Kein direkter Eingriff nötig (alle bisherigen Attribut-Exposes
    bleiben — `_body_widget` ist Implementation-Detail von `_AntenneCard`)
- **`config/settings.py`** — keine API-Erweiterung nötig:
  - generische `get("antenne_card_collapsed", False)` + `set(...)` reicht
  - alternativ: explizite `get_antenne_collapsed()` / `save_antenne_collapsed(bool)`
    für API-Konsistenz (V2/R1 entscheiden)
- **`ui/main_window.py`** ODER **`ui/control_panel.py.__init__`** —
  Initial-State setzen aus Settings nach Widget-Konstruktion (V2/R1
  entscheiden welche Stelle sauberer ist):
  - Variante A: `_AntenneCard` bekommt `settings`-Parameter im
    Konstruktor, lädt selbst → KISS aber neue Abhängigkeit
  - Variante B: `MainWindow` setzt nach `ControlPanel`-Konstruktion
    via `control_panel._ant_card.set_collapsed(bool)` → keine neue
    Abhängigkeit, aber zwei Stellen

---

## 4. Randbedingungen

- **Hobby-Tool-Philosophie:** Mike's Designentscheidung steht. R1
  darf KISS-Bedenken äussern, aber das „einklappbar Ja/Nein" ist NICHT
  verhandelbar.
- **Default-State:** Aufgeklappt (`False`). Mike hat keinen anderen Wunsch
  geäussert; aufgeklappt ist der Zustand vor dem Feature.
- **Kein UI-Bruch bei zugeklappter Kachel:** wenn Mike Band/Modus wechselt
  oder KALIBRIEREN startet während Kachel zu ist — funktioniert das?
  Diversity-Ratio-Update, Histogramm-Update, CQ-Countdown laufen weiter
  (Signale + Slots ändern sich nicht durch Visibility-Toggle), nur unsichtbar.
- **DeepSeek-Vorbehalt:** R1 könnte argumentieren „alles muss sichtbar
  sein" (Standard-WSJT-X-Praxis). Ablehnen — Mike's Entscheidung,
  R1 prüft nur die Umsetzung.
- **Keine Animation:** instant hide/show. KISS, keine `QPropertyAnimation`,
  keine fade-in/out.
- **Toggle-Icon:** Unicode-Pfeil (`▼` aufgeklappt, `▶` zugeklappt) ist
  ohne externe Resourcen verfügbar. Alternative: `QToolButton` mit
  `Qt::ArrowType` (Arrow-Down / Arrow-Right) — nativer, aber V2 prüft.

---

## 5. Nicht im Scope

- Animation des Toggles
- Keyboard-Shortcut (`Strg+H` o.ä.)
- Andere Kacheln einklappbar machen (nur Antenne, Mike-Wunsch
  einer Kachel — Pattern lässt sich später auf andere übertragen)
- TX-Freq-Spinner-Position ändern (bleibt im Body, NORMAL-Modus
  zeigt ihn weiterhin nur wenn Kachel offen)
- Doppel-Klick auf Header für Toggle (nur Button-Klick, KISS)
- Default-State je Modus (z.B. Normal = zugeklappt, Diversity =
  aufgeklappt) — Mike hat das nicht verlangt, KISS

---

## 6. Testbarkeit

**Pflicht-Tests:**

1. `test_antenne_card_default_expanded`:
   - `card = _AntenneCard()` → `card._body_widget.isVisible()` True
   - Toggle-Button-Icon = aufgeklappt-Symbol

2. `test_antenne_card_toggle_collapses`:
   - Toggle-Button klicken → Body unsichtbar
   - Erneut klicken → wieder sichtbar

3. `test_antenne_card_set_collapsed_api`:
   - `card.set_collapsed(True)` → Body unsichtbar, Icon zugeklappt
   - `card.set_collapsed(False)` → Body sichtbar

4. `test_antenne_card_persistence_save`:
   - User klickt Toggle → Settings-Mock erhält
     `set("antenne_card_collapsed", True)` + `save()`-Call

5. `test_antenne_card_persistence_load`:
   - Settings hat `antenne_card_collapsed=True` →
     `MainWindow.__init__` ruft `set_collapsed(True)` auf der Karte

6. `test_diversity_update_works_when_collapsed`:
   - Kachel zugeklappt → Diversity-Update-Signal eintragen →
     interne Labels werden trotzdem aktualisiert (kein early-return,
     keine Crash bei `setVisible(False)`-Widget)

**Manuelle Smoke-Tests (Mike post-Kur):**
- App starten, Kachel zuklappen, App schliessen, App öffnen → Kachel
  noch immer zugeklappt
- Kachel zugeklappt → KALIBRIEREN starten → Kachel bleibt zu, Phase 1+2+3
  laufen (Diversity-Pattern wird gespeichert)
- Kachel öffnen während aktivem QSO → keine Funktionsstörung

---

## 7. Offene Fragen für V2/R1

1. **Toggle-Position:** Links vor „ANTENNE"-Label oder rechts ganz aussen?
   WSJT-X-Konvention wäre rechts (≡-Burger oder Pfeil).
2. **Toggle-Stil:** `QPushButton` mit Unicode-Pfeil oder `QToolButton`
   mit `Qt.ArrowType.DownArrow`/`RightArrow`?
3. **Settings-Integration:** Generic `settings.get("antenne_card_collapsed")` /
   `set(...)` ODER explizite Properties wie `get_antenne_collapsed()`?
4. **Init-Stelle:** `_AntenneCard.__init__(settings)` ODER
   `MainWindow` ruft nach Konstruktion `set_collapsed(...)` auf?
5. **Kachel-Header-Höhe wenn zugeklappt:** explizit `setMinimumHeight(28)`
   oder über Layout natürlich? (Letzteres KISS, aber Stylesheet padding
   könnte die Höhe wackelig machen.)
6. **Klick auf gesamten Header (nicht nur Button) für Toggle:** UX-nice,
   aber neuer EventFilter — KISS-konform?

---

**Workflow-Status:** V1 fertig. Weiter mit V2 (Self-Review).
