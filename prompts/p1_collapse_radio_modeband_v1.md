# P1.COLLAPSE-RADIO-MODEBAND V1 — Modus+Band + Radio einklappbar

**Stand:** 2026-05-07.
**Workflow:** **V1 (diese Datei)** → V2 (Self-Review) → R1 (DeepSeek) → V3 → Compact → Code.
**Ausloeser:** Mike-Wunsch 07.05. nach v0.95.16-Push: „radio und mouds hätte ich
gerne auch zum einklappen der kachel wie die Antennen kachel".
**Vorbild:** P1.ANTENNE-COLLAPSE (v0.95.11, atomarer Commit `a0ce1ae`,
10 Tests, 5 R1-KP-Findings adressiert).

---

## 1. Mike-Anforderung (Original-Zitat)

> „einmal wo man den modus und band auswählt - wenn ich eine stunde lang ft8
> auf 20 meter machen möchte brauche ich das nicht permanent eingeblenden,
> genauso die anzeige mit watt zahl die verstelle ich ja seltener das tunen
> macht die app in diversity modus automatisch also auch nur nach bedarf.
> beide unabhängig und letzte status laden ob eingeklapp war det nicht
> genauso sollte die ander kachel auch gehandelt worden sein die einzige
> kachel die wir immer braucehn ist de cq ruf kacel"

**Mike-Logik:** Modus + Band stellt man 1× pro Hour ein, dann ist gut.
Power + TUNE + SWR ebenfalls selten — Diversity tunet automatisch bei Bedarf.
QSO-Kachel (CQ-Button + Statusbar) ist die einzige die immer offen sein muss.

## 2. Symptom (heute 07.05.2026)

- `_ModeBandCard` (`ui/control_panel.py:232`) ist **fest sichtbar** — Modus
  (FT8/FT4/FT2) + Frequenz + Band-Buttons (10m-80m mit Propagations-Indikatoren).
  Permanent ~95-110 Pixel hoch.
- `_RadioCard` (`ui/control_panel.py:650`) ist **fest sichtbar** — PSK-Info
  + Map-Button + 10×Power-Buttons + TX-Status-Frame (Clipschutz/TX-Pegel/RF
  + TUNE + Watt/SWR). Permanent ~120-140 Pixel hoch.
- `_AntenneCard` (`ui/control_panel.py:425`) ist **bereits einklappbar**
  (v0.95.11, `set_collapsed/_toggle_collapsed/collapse_changed`).
- `_QSOStatusCard` (`ui/control_panel.py:795`) bleibt **immer sichtbar**
  (CQ-Button, Status, HALT — Mike's Hauptkachel).

→ Viel Platz im ControlPanel verbraucht durch Kacheln die nicht permanent
gebraucht werden. Mike will das anlegen wie Antennen-Kachel.

## 3. Ziel — Bug-Detail mit Datei:Zeile

### 🟢 Aufgabe 1 — `_ModeBandCard` einklappbar (ui/control_panel.py:232-414)

**Aktuell:** `__init__` baut direkt `lay = QVBoxLayout(self) + grid` — keine
Header-Row, kein Body-Container, keine Collapse-API.

**Neu (Spiegelung Antennen-Pattern):**
- Header-Row (0-Margins) mit Toggle-Button (`▼`/`▶`, Farbe `#7799FF` blau,
  passend zu `_CARD_SS_BLUE`) + Label „MODUS / BAND" (10px, blau, fett).
- Body-Container `_body_widget` mit aktuellem `grid`-Inhalt (Modus + FT8/FT4/
  FT2 + Freq-Box + Bands + Prop-Bars).
- API: `set_collapsed(bool)`, `is_collapsed() -> bool`, `_toggle_collapsed()`.
- Signal `collapse_changed = Signal(bool)`, **NUR** bei User-Klick emittiert
  (Init-Loop-Schutz — kritischer Punkt aus P1.ANTENNE-COLLAPSE-R1!).
- `setMaximumHeight(36)` bei Collapse, `_QWIDGETSIZE_MAX` bei Expand.

### 🟢 Aufgabe 2 — `_RadioCard` einklappbar (ui/control_panel.py:650-792)

**Aktuell:** `__init__` baut Label „RADIO" (Z.663-665) direkt + Body-Inhalt
ohne Trennung. Keine Collapse-API.

**Neu:** identisches Pattern. Bestehendes Label „RADIO" wird in Header-Row
mit Toggle-Button kombiniert. Toggle-Button-Farbe `#00aacc` (teal).
Body = PSK-Frame + Power-Row + TX-Status-Frame.

### 🟢 Aufgabe 3 — `ControlPanel`-Integration (ui/control_panel.py:1036+)

- 2 neue Klassen-Signale in `ControlPanel`:
  - `modeband_collapse_changed = Signal(bool)`
  - `radio_collapse_changed = Signal(bool)`
- 2 neue `self.X = card`-Exposes:
  - `self._modeband_card = mb_card` (analog `self._ant_card`)
  - `self._radio_card = radio_card`
- 2 neue Forward-Connects (lambda-frei, exakt wie bei Antennen):
  - `mb_card.collapse_changed.connect(self.modeband_collapse_changed.emit)`
  - `radio_card.collapse_changed.connect(self.radio_collapse_changed.emit)`

### 🟢 Aufgabe 4 — `MainWindow`-Integration (ui/main_window.py:456+)

- 2 neue Settings-Keys: `modeband_card_collapsed`, `radio_card_collapsed`.
- 2 neue Initial-State-Loads nach `self.control_panel = ControlPanel(...)`:
  ```python
  _modeband_collapsed = self.settings.get("modeband_card_collapsed", False)
  self.control_panel._modeband_card.set_collapsed(_modeband_collapsed)
  self.control_panel.modeband_collapse_changed.connect(
      self._on_modeband_collapse_changed)
  _radio_collapsed = self.settings.get("radio_card_collapsed", False)
  self.control_panel._radio_card.set_collapsed(_radio_collapsed)
  self.control_panel.radio_collapse_changed.connect(
      self._on_radio_collapse_changed)
  ```
- 2 neue Slots analog `_on_antenne_collapse_changed` (bei Z.861):
  ```python
  def _on_modeband_collapse_changed(self, collapsed: bool) -> None:
      self.settings.set("modeband_card_collapsed", collapsed)
  def _on_radio_collapse_changed(self, collapsed: bool) -> None:
      self.settings.set("radio_card_collapsed", collapsed)
  ```

### 🟢 Aufgabe 5 — Tests (tests/test_p1_collapse_radio_modeband.py NEU)

Spiegel `tests/test_antenne_card.py` (10 Tests in v0.95.11). Erwartung:
~14-16 neue Tests (zwei Karten × ~7-8 Tests). Tests 902 → ~916 gruen.

## 4. Akzeptanzkriterien

1. **AC-1 ModeBand-Toggle:** Klick auf Toggle-Button klappt Body ein/aus,
   Toggle-Icon wechselt `▼`/`▶`, `setMaximumHeight(36)` bei Collapse.
2. **AC-2 Radio-Toggle:** Identisch fuer Radio-Kachel.
3. **AC-3 Beide unabhaengig:** Toggle einer Kachel beeinflusst die andere
   nicht. Settings-Keys getrennt.
4. **AC-4 Init-State:** Beim App-Start lädt jede Kachel ihren letzten
   Zustand aus Settings (Default: ausgeklappt = `False`).
5. **AC-5 Persistenz:** User-Klick → Signal → Slot → `Settings.set` →
   nächster App-Start hat denselben Zustand.
6. **AC-6 Init-Loop-Schutz:** `set_collapsed()` (Programm-API) emittiert
   KEIN `collapse_changed`-Signal — sonst beim App-Start endlose Schleife
   mit `Settings.set`. (R1-KP aus P1.ANTENNE-COLLAPSE.)
7. **AC-7 Antennen-Kachel unbeeinflusst:** Bestehende Antennen-Collapse
   funktioniert weiter (10 Tests in `test_antenne_card.py` muessen
   unveraendert gruen bleiben).
8. **AC-8 QSO-Kachel unbeeinflusst:** `_QSOStatusCard` bleibt immer voll
   sichtbar — kein Toggle, kein Header-Refactor.
9. **AC-9 Modus/Band-Funktionalitaet intakt:** FT8/FT4/FT2-Buttons +
   Band-Buttons + Frequenz-Display + Propagations-Bars funktionieren
   unveraendert nach Collapse-Refactor (Body wird nur sichtbar/unsichtbar,
   nicht zerstoert).
10. **AC-10 Radio-Funktionalitaet intakt:** PSK-Map + Power-Buttons +
    TUNE + Watt/SWR funktionieren unveraendert.
11. **AC-11 Tests gruen:** 902 → ~916 (+14-16 neue Tests). Bestehende
    Tests gruen.
12. **AC-12 KEINE Behavior-Aenderung:** Wenn Kachel ausgeklappt ist
    (Default), sieht UI identisch aus zu vor v0.95.17 (lediglich Toggle-
    Button im Header neu).
13. **AC-13 APP_VERSION:** 0.95.16 → 0.95.17 (UI-Feature, Patch +0.01
    Mike-Konvention).

## 5. Betroffene Module/Dateien

### 5.1 `ui/control_panel.py` — 3 Bereiche
- Z.232 `_ModeBandCard` — Refactor `__init__` (Header-Row + body_widget),
  Collapse-API (~30 neue Zeilen).
- Z.650 `_RadioCard` — analog (~30 Zeilen).
- Z.1036+ `ControlPanel` — 2 Signale, 2 Exposes, 2 Forward-Connects
  (~6 Zeilen).

### 5.2 `ui/main_window.py` — 2 Stellen
- Z.456 nach ControlPanel-Init: 2 Initial-Loads + 2 Connects (~6 Zeilen).
- Z.861 nach `_on_antenne_collapse_changed`: 2 neue Slots (~6 Zeilen).

### 5.3 `tests/test_p1_collapse_radio_modeband.py` (NEU)
Tests pro Kachel:
- `test_*_initial_state_expanded` — Default ausgeklappt
- `test_*_set_collapsed_true_hides_body`
- `test_*_set_collapsed_false_shows_body`
- `test_*_toggle_button_click_emits_signal`
- `test_*_set_collapsed_does_not_emit` (Init-Loop-Schutz)
- `test_*_max_height_when_collapsed`
- `test_*_max_height_when_expanded` (`_QWIDGETSIZE_MAX`)
- `test_*_toggle_icon_switches`
Plus 1-2 Integration-Tests:
- `test_modeband_and_radio_independent` — beide Karten getrennt togglen
- `test_settings_persist_independently` (mit MainWindow + Settings-Mock)

→ ~14-16 Tests.

### 5.4 `main.py` APP_VERSION 0.95.16 → 0.95.17

## 6. Randbedingungen / Kritische Punkte (V1-Sicht)

- **Init-Loop-Schutz:** `set_collapsed` darf KEIN Signal emittieren, sonst
  beim Settings-Load → set_collapsed → Signal → Slot → Settings.set →
  Endlosschleife. (P1.ANTENNE-COLLAPSE-R1-KP, Test 10 in `test_antenne_card.py`.)
- **`_ModeBandCard.update_propagation`** schreibt in `self.prop_bars[band]`
  — diese sind im Body. Wenn collapsed, sind Bars unsichtbar — `setVisible`-
  Calls bleiben funktional, kein Crash. **Aber:** wird `update_propagation`
  pro Slot/Band-Wechsel aufgerufen — auch wenn Bar collapsed? Code-Verifikation
  in V2 Pflicht.
- **`_RadioCard` Power-Buttons + TX-Frame** sind ausschliesslich im Body.
  Wenn collapsed, keine UI-Updates sichtbar — aber `power_buttons.setChecked`,
  `watt_label.setText`, `swr_label.setText` bleiben funktional.
- **TUNE-Button:** wenn TUNE aktiv (`_tune_active=True`) UND Kachel collapsed,
  sieht User nicht dass TX laeuft. **Sicherheits-Risiko?** Statusbar zeigt
  „TUNE: xx kHz" laut CLAUDE.md `mw_tx.py:_on_tune_clicked`. Also: collapse
  ist sicher solange Statusbar nicht auch verloren geht.
- **TX-Slot-Anzeige:** Watt/SWR bei TX collapsed → User sieht nicht ob
  Sendung laeuft. Aber: Encoder-Signal `tx_started` updatet Statusbar
  separat (`_update_statusbar` Calls). Sollte ausreichen — V2 verifiziert.
- **Fenster-Resize / Layout-Stretch:** wenn beide neuen Karten collapsed
  PLUS Antennen collapsed, schrumpft ControlPanel auf nur Header-Rows +
  QSO-Kachel. Stretch-Verhalten beobachten.
- **`_PulseBar`-Animations:** `_start_pulse`/`_stop_pulse` arbeiten auf
  `prop_bars`. Im collapsed-State wird Animation weiter laufen — ist das
  Performance-Problem? V2 prueft.
- **Settings-File-Format:** `Settings.set` schreibt JSON synchron. Bei
  schnellem Toggle (mehrere pro Sekunde) ist das I/O-Heavy — bei P1.ANTENNE-
  COLLAPSE als R1-Vorbehalt notiert, aber NICHT umgesetzt (KISS). Selbe
  Begruendung gilt hier.

## 7. Nicht im Scope (P2 oder später)

- **QSO-Kachel einklappbar** — Mike: „die einzige kachel die wir immer
  braucehn ist de cq ruf kacel" → bewusst exkludiert.
- **Kachel-Reihenfolge / Drag-and-Drop / Floating-Cards** — nicht Mike-
  Anforderung.
- **Animation des Collapse-Toggles** (Smooth Slide) — KISS, sofort schalten
  reicht (Antennen-Kachel macht's auch so).
- **Header-Status-Hint im collapsed State** (z.B. „MODUS+BAND — FT8/20m")
  — Overengineering, Mike sagt die Info ist schon woanders sichtbar
  (Frequenz steht eh in der Freq-Box, Band kann er sich merken).

## 8. Offene Fragen für V2/R1

1. **Refactor-Risiko `_ModeBandCard`:** das aktuelle `__init__` baut alles
   direkt in `self` (`lay = QVBoxLayout(self)`). Refactor: `lay` haelt
   Header-Row + body_widget, Grid wandert ins body_widget. Sind alle
   Member-Refs (`self.btn_ft8`, `self.band_buttons`, `self.prop_bars`,
   `self.freq_label`) noch zugaenglich? V2 grep-verifiziert.
2. **`_RadioCard` analog:** `self.psk_label`, `self.btn_psk_map`,
   `self.power_buttons`, `self.btn_tune`, `self.watt_label`, `self.swr_label`,
   `self.peak_label`, `self.tx_level_label`, `self.rf_power_label`,
   `self.tx_level_bar` — alles bleibt zugaenglich nach Refactor, V2 grep.
3. **Header-Label-Doppelung:** im aktuellen `_RadioCard:663` gibt es schon
   `lbl_radio = QLabel("RADIO")`. Bei Refactor wandert das in Header-Row.
   Wird das Label noch gebraucht (z.B. fuer Tests)? — Vermutlich nicht.
4. **Default-Collapse-State:** Mike sagt „letzte status laden ob eingeklapp
   war" — also Settings. Default beim ersten App-Start: `False` (= ausgeklappt,
   wie Antennen). Bestaetigt in V1 Punkt 4 AC-4.
5. **Fehler-Robustheit Settings-Load:** wenn Settings-File korrupt oder
   Key fehlt → `Settings.get(key, default=False)` faengt das ab. KISS.
6. **Test-Datenbasis:** wie testen wir mit `MainWindow` + `Settings`?
   `test_antenne_card.py` macht's vermutlich mit Stub — V2 schaut nach.
7. **APP_VERSION-Konvention:** 0.95.16 → 0.95.17 (Feature, Patch +0.01).
   Bestaetigt durch v0.95.11 (P1.ANTENNE-COLLAPSE auch Patch-Increment).
8. **R1-Vorbehalt P1.ANTENNE-COLLAPSE (Settings.save Debounce):** wieder
   relevant? V2 prueft + KISS-Bewertung.

## 9. Compact-Strategie

V1 ist Diagnose. V2 wird Self-Review mit Lessons. R1 reviewt V2+V1 mit
Code-Files. V3 ist Compact-fest mit allen Diffs. Erwartung Tests
902 → ~916 gruen (+14-16). APP_VERSION 0.95.16 → 0.95.17.

---

**Workflow-Status:** V1 fertig. Weiter mit V2 (Self-Review).
