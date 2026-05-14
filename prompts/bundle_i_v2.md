# Bundle I — V2 — Settings-Spacing + QSO-komplett-Reihenfolge + OMNI-CQ-Race

**Datum:** 2026-05-14 nachmittags
**Version-Ziel:** v0.97.26
**Trigger:** Mike-Field-Test 14.05.2026 nachmittags
**Aufwand-Schätzung:** klein bis mittel — ~1 Tag inkl. Tests + DeepSeek-Workflow

---

Du bist Senior Python-Entwickler spezialisiert auf Amateurfunk-Software
und PySide6 (Signal statt pyqtSignal, Slot statt pyqtSlot). Das Projekt
ist ein Hobby-Funker-Tool für einen einzelnen Operator — NICHT Multi-Tenant.

Deine einzige Aufgabe: diesen Prompt kritisieren — NICHT das Problem lösen.
Strukturierte Liste: Lücken, Unklarheiten, Widersprüche, Verbesserungen.

KRITISCHE REGELN:
1. SCOPE-RESPEKT: Explizit als out-of-scope markiertes NICHT als Finding melden.
2. KISS VOR DEFENSIV: Komplexität nur wenn Wahrscheinlichkeit > 50%.
3. PROJEKT-BEZUG: Jedes Finding am konkreten Use-Case messen.
4. FORMAT: Tabelle Schwere | Finding | Datei:Zeile | Empfehlung.
   Severity: Bug (rot) / Risiko (orange) / Verbesserung (gelb) / Hinweis (grau).

Overengineering ist selbst ein Fehler den du benennen sollst.

---

## Ziel

Drei orthogonale Befunde aus dem Mike-Field-Test 14.05.2026 nachmittags
zusammen einspielen — alle klein bis mittel, gemeinsame Test-Suite
„Bundle I" hält den Workflow-Overhead niedrig.

### Punkt 1 — Settings „Sichtbare Bänder" gedrungen

Bundle D (v0.97.21) hatte Spacing 6→10 erhöht. Mike-Visual-Check
14.05. (Screenshot Settings-Dialog, FT8 & Diversity-Tab):
3×3-Checkbox-Raster wirkt weiterhin gedrückt, Checkboxen kleben
aneinander. Reine UI-Verbesserung, keine Logik-Änderung.

### Punkt 2 — „✓ QSO komplett" erscheint vor Courtesy-73-Sendung

P33 (Bundle B', v0.97.14) führte ein 2-Signal-Split ein:
- `qso_confirmed_visual` SOFORT bei 73-Empfang (UI-Update)
- `qso_confirmed` NACH Courtesy-Send (OMNI-Resume, Auto-Hunt-Reset,
  Logbuch)

Mike-Field-Test 14.05.: Visual-Emit ist **zu früh**. Reihenfolge in
QSO-Panel heute:

```
10:11:00 [E] Empf. 73                  ← 73 vom anderen
     ✓ QSO mit X komplett              ← visual SOFORT
10:11:15 [O] Sende X DA1MHH 73 ↻10     ← unser Courtesy
```

Mike-Wunsch: visual-Bestätigung NACH Courtesy-Send (zwischen
Courtesy-Zeile und nächstem CQ-Slot). Logisch sauber weil QSO erst
dann „echt durch ist". Mike-Begründung: „wenn wir IMMER das 2. 73
aus Höflichkeit senden, dann können wir das QSO komplett auch
DANACH zeigen — dann ist das sauber und vor dem nächsten CQ."

### Punkt 4 — OMNI-CQ-Race beim Mode-Wechsel

Mike-Field-Test 14.05.: OMNI-CQ aktiv, Mode-Wechsel zwischen
Diversity-Submodi oder Diversity↔Normal, OMNI-Schalter geht visuell
aus — aber **EIN** weiterer CQ-Slot wird gesendet. Danach Stille
(Stop greift letztendlich). Screenshot zeigt `→ Sende CQ DA1MHH
JO31` **ohne** `↻N`-Suffix → der TX kam aus dem **normalen
CQ-Pfad** (`qso_sm.cq_mode`), nicht aus dem OMNI-Pfad
(`core/omni_cq.py`).

Mikes eigene Hypothese (klärungsweise): „kann sein dass cq normal
gerufen wurde, der State erhalten blieb beim Wechsel auf Diversity,
und es noch einmal verzögert gefeuert hatte ODER nur die Anzeige
einmal nachgeschoben hatte". Danach **keine** weiteren CQ-Rufe.

Schritt-0-Verifikation an `ui/mw_radio.py:541-545`:

```python
if mode != old_mode:
    if hasattr(self, "_omni_cq") and self._omni_cq.is_active():
        self._omni_cq.stop("rx_mode_change")
    if hasattr(self, "_auto_hunt") and self._auto_hunt.active:
        self._auto_hunt.stop_auto_hunt("rx_mode_change")
    self._easter_egg_active = False
```

→ `qso_sm.cq_mode` und ein evtl. schon armed-er Encoder-Slot werden
**NICHT** mit-gestoppt. Hypothese: das ist die Race-Quelle.

---

## Akzeptanzkriterien

### Punkt 1 — Settings-Spacing

- **AC1.1** GroupBox „Sichtbare Bänder" hat luftiges 3×3-Raster mit
  klar sichtbarem Spacing zwischen allen Reihen und Spalten (≥ 16
  px horizontal und vertikal). Werte aktuell:
  `bands_grid.setSpacing(10)` und
  `bands_grid.setContentsMargins(12, 8, 12, 10)` in
  `ui/settings_dialog.py:342-343`.
- **AC1.2** GroupBox-Innen-Margins großzügig — empfohlen `(16, 16,
  16, 16)` allseits.
- **AC1.3** Checkbox-Indicator deutlich größer als Default-13×13.
  Lösung per Stylesheet auf der GroupBox (nicht global):
  ```css
  QCheckBox::indicator { width: 18px; height: 18px; }
  ```
- **AC1.4** Label-Font der Checkbox-Texte +1 pt gegenüber Default
  (optional — falls Stylesheet eh dran ist, kostet nichts).
- **AC1.5** Layout-Bruch verhindern — GroupBox-Breite darf um
  ≤ 30 px wachsen (durch größere Checkboxen). Wenn der Settings-Tab
  insgesamt breiter wird ist das OK, kein hartes Limit.
- **AC1.6** P50-Min-1-Logik unangetastet
  (`_on_band_visibility_toggled`).
- **AC1.7** P50-Reset-Button setzt Werte korrekt zurück
  (Default-Verhalten beibehalten).
- **AC1.8** Andere Settings-Tabs / -Blöcke werden vom Stylesheet
  NICHT beeinflusst (Stylesheet auf `bands_group` setzen, nicht
  auf Dialog-Root).

### Punkt 2 — QSO-komplett-Reihenfolge

- **AC2.1** Bei normalem QSO-Abschluss (73- ODER RR73-Empfang in
  `WAIT_73` + Courtesy-Send): Reihenfolge in QSO-Panel ist `Empf.
  73` (oder `Empf. RR73`) → `Sende 73` → `✓ QSO komplett` → (nächster
  Slot ggf. CQ).
- **AC2.2** Im WAIT_73-Timeout-Pfad (kein 73/RR73 vom anderen,
  3 Cycles, `core/qso_state.py:357-365`): visual + full direkt
  hintereinander, unverändert. Kein Courtesy-Send in diesem Pfad
  → kein Timing-Konflikt.
- **AC2.3** Im Force-73-Pfad via `advance()` (manuell QSO Finish
  in WAIT_73, `core/qso_state.py:754-768`): Verhalten muss analog
  AC2.1 sein. `advance()` ruft `send_message.emit(...)` für Force-73
  → Encoder → `_on_tx_finished` → `on_message_sent` → State =
  `TX_73_COURTESY` → visual+full feuern dort. Schon
  architektonisch abgedeckt wenn V2-Lösung in `TX_73_COURTESY`-Branch
  von `on_message_sent` greift.
- **AC2.4** Kein Doppel-Eintrag „✓ QSO komplett" — visual exakt
  einmal pro QSO.
- **AC2.5** `qso_confirmed` (full) feuert wie heute nach
  Courtesy-Send (notwendig für OMNI-Resume, Auto-Hunt-Reset,
  Logbuch). Reihenfolge `visual` vor `full` im selben Branch ist
  OK weil beide dasselbe QSO-Datenobjekt teilen und kein
  asynchroner Receiver dazwischen agiert (Qt.DirectConnection im
  GUI-Thread).
- **AC2.6** Während des Courtesy-Slots (`Sende 73` ist sichtbar,
  TX läuft) ist die Bestätigungszeile NICHT im Panel. Test prüft
  Emit-Counter:
  - Direkt nach 73-Empfang in WAIT_73: `qso_confirmed_visual`-Spy
    hat 0 Calls.
  - Nach `on_message_sent`-Aufruf mit State `TX_73_COURTESY`:
    `qso_confirmed_visual`-Spy hat genau 1 Call.

**Bekannte Lücke (out of scope, dokumentieren):** wenn der
Courtesy-Send abgebrochen wird (User klickt QSO Finish während
TX, App-Crash, Encoder-Fehler, Mode-Wechsel mid-Slot), fehlt die
Visual-Bestätigung obwohl `qso_complete` schon in TX_RR73 gefeuert
wurde und das QSO im ADIF-Logbuch landet. Sehr selten. Fix-Plan:
falls Mike Bedarf meldet, könnte ein Fallback in `cancel()`/`stop_cq()`
das visual-Signal noch nachschießen wenn `qso_complete` schon raus
war. Heute: Doku-Hinweis in HISTORY genügt.

### Punkt 4 — OMNI-CQ Race-Stop

- **AC4.1** Beim RX-Mode-Wechsel (`ui/mw_radio.py:541-545`) wird
  neben OMNI und Auto-Hunt auch der normale CQ-Modus mit gestoppt,
  sofern aktiv:
  ```python
  if hasattr(self, "qso_sm") and self.qso_sm.cq_mode:
      self.qso_sm.stop_cq()
  ```
- **AC4.2** Mike's Symptom abgedeckt durch Test: `cq_mode=True`
  vor Mode-Wechsel, `_on_rx_mode_changed("diversity")` aufgerufen,
  danach `cq_mode=False`, State=IDLE, `send_message`-Spy zeigt
  KEINEN neuen Emit.
- **AC4.3** Encoder-Sicherheit: falls beim Mode-Wechsel ein
  TX-Slot bereits aktiv ist (PTT on, Audio läuft), wird er NICHT
  hart abgebrochen — Hardware-Sicherheit für FlexRadio. Aber:
  **keine neuen Slots** werden begonnen. Encoder-Pending-Queue
  muss leer sein nach Mode-Wechsel (vgl.
  `core/encoder.py` P5.OMNI-PATTERN-FIX-3 Pending-Queue mit
  Verfall). Falls Pending-Queue beim Mode-Wechsel nicht leer
  ist: das gehört in den Stop-Block dazu — ABER nur wenn die
  Queue für CQ-Pakete da ist (OMNI nutzt sie, normaler CQ ggf.
  auch).
- **AC4.4** ANT1=TX-Pflicht: keine Antennen-Umschaltung im
  Stop-Block. Test prüft per Mock dass `set_tx_antenna` während
  `_on_rx_mode_changed` NICHT aufgerufen wird.
- **AC4.5** Bandpilot-Pfad (`_apply_bandpilot_auto` ruft
  programmatisch `_on_rx_mode_changed`): wir wollen die
  zusätzliche `qso_sm.stop_cq()`-Logik nicht in den Bandpilot-Pfad
  hineintragen wenn er einen User-CQ unterbrechen würde. ABER:
  laut Mike-Vision soll Bandpilot eher dann zuschlagen wenn der
  User gerade nicht aktiv funkt. Frage an R1: ist es richtig den
  CQ unbedingt zu stoppen auch wenn Bandpilot der Auslöser ist?
  → V1-Empfehlung: ja, stoppen — Bandpilot ist ein User-Move
  (auto-Mode), kein passives Auto-Switching. Wenn Mike CQ ruft
  und Bandpilot schaltet auf Diversity DX, ist es OK den CQ zu
  beenden weil sich die Antennen-Bedingungen ändern.
- **AC4.6** „Partial-Fix"-Check (Memory
  `feedback_partial_fix_check_other_paths.md`):
  - `mw_radio.py:1341` ruft `self._on_rx_mode_changed("normal")`
    nach SWR-Fehler → läuft durch unseren Fix
    automatisch durch.
  - `mw_radio.py:464` und `1167` rufen direkt `_apply_normal_mode`
    OHNE Umweg über `_on_rx_mode_changed`. Wird der CQ dort
    auch gebraucht zu stoppen? → V1-Antwort: nein, beide Pfade
    sind interne Restore-Pfade aus Diversity-Disable. Mike's
    Bug-Symptom kommt aus dem User-Mode-Wechsel-Pfad. Aber R1
    soll das verifizieren — falls `_apply_normal_mode` z.B. von
    einem programmatischen Pfad gerufen wird der CQ aktiv lässt,
    fehlt der Schutz.

### Tests (verbindlich)

**Punkt 1 — Settings-Spacing:**
- T1.1 Settings-Dialog initialisiert ohne Crash (Smoke).
- T1.2 `_band_checkboxes` hat genau 9 Einträge, alle in 3×3-Grid.
- T1.3 P50 Min-1-Logik: mock 1 aktiv → letzte Checkbox `setEnabled(False)`.
- T1.4 Stylesheet auf `bands_group` wirkt (Indicator-Größe per
  `cb.style().pixelMetric(...)` oder einfach: Style-String enthält
  `width: 18px`).

**Punkt 2 — QSO-Reihenfolge:**
- T2.1 In `WAIT_73`: 73 empfangen → `qso_confirmed_visual`-Spy
  hat 0 Calls direkt danach. State = `TX_73_COURTESY`.
- T2.2 `on_message_sent` mit State `TX_73_COURTESY` → visual + full
  feuern beide, in dieser Reihenfolge, je 1 Call.
- T2.3 WAIT_73-Timeout (3 Cycles): visual + full feuern wie heute
  direkt nacheinander (unverändert).
- T2.4 Force-73 via `advance()`: visual feuert NICHT bei
  `advance()`-Aufruf, sondern erst beim folgenden
  `on_message_sent`-Aufruf in State `TX_73_COURTESY`.
- T2.5 Kein Doppel-Emit: 73-Empfang + on_message_sent zusammen
  → visual genau 1×.
- T2.6 RR73 statt 73 in WAIT_73 (`is_rr73`-Branch, Z.686): gleiche
  Reihenfolge wie bei 73.

**Punkt 4 — OMNI-Race:**
- T4.1 `_on_rx_mode_changed("diversity")` mit `qso_sm.cq_mode=True`
  → `qso_sm.stop_cq()` wird genau 1× aufgerufen.
- T4.2 Nach Mode-Wechsel: `qso_sm.cq_mode=False`, State=IDLE,
  `send_message`-Spy zeigt 0 Calls in den nächsten 2 Cycle-Ticks.
- T4.3 Mode-Wechsel ohne aktiven CQ: `stop_cq()` wird NICHT
  aufgerufen (kein No-Op-Spam).
- T4.4 OMNI + qso_sm.cq_mode beide an (Edge-Case): beide werden
  korrekt gestoppt.
- T4.5 `set_tx_antenna`-Spy: nicht aufgerufen während Mode-Wechsel.
- T4.6 Bandpilot programmatischer Mode-Wechsel: `qso_sm.stop_cq`
  wird aufgerufen — Test bestätigt das Verhalten (Mike-Bestätigung
  via R1-Klärung empfohlen, siehe AC4.5).

---

## Betroffene Module/Dateien

### Punkt 1
- `ui/settings_dialog.py:333-356` — GroupBox + Stylesheet
- `tests/test_settings_dialog_smoke.py` — Smoke + neue T1.x

### Punkt 2
- `core/qso_state.py:685-715` — `WAIT_73`-Branch in
  `on_message_received`: `qso_confirmed_visual.emit` (Z.692)
  **entfernen**
- `core/qso_state.py:530-539` — `TX_73_COURTESY`-Branch in
  `on_message_sent`: `qso_confirmed_visual.emit(self.qso)` vor
  `qso_confirmed.emit(self.qso)` **hinzufügen**
- `core/qso_state.py:357-365` — `WAIT_73`-Timeout: unverändert
- `core/qso_state.py:754-768` — `advance()` Force-73: profitiert
  automatisch von der Architektur-Änderung (kein Code-Eingriff)
- Tests: `tests/test_p33_qso_komplett_reihenfolge.py` (bestehend)
  T1.x-T6.x prüfen + Bundle-I-Erweiterungen

### Punkt 4
- `ui/mw_radio.py:541-545` — Stop-Block erweitern um
  `qso_sm.stop_cq()`-Aufruf wenn `cq_mode` aktiv
- Tests: neuer `tests/test_bundle_i_omni_race.py` für AC4.1-AC4.6
  bzw. an `tests/test_modules.py` anhängen wenn schlanker

---

## Randbedingungen

### Hardware-Pflicht ANT1=TX (CLAUDE.md HARDWARE-WARNUNG)
- Punkt 4 betrifft TX-Pfad. Keine Antennen-Umschaltung im
  Stop-Block. Test (T4.5) sichert das ab.

### KISS-Pflicht (CLAUDE.md Programmier-Leitsätze)
- Punkt 1: nur Werte-Änderung + Stylesheet-Block in der GroupBox.
  Kein Custom-Widget, keine Subclass, keine Layout-Helper.
- Punkt 2: zwei Zeilen verschieben. Kein Refactor des P33-
  Architektur-Splits.
- Punkt 4: vier Zeilen Stop-Erweiterung. Kein neuer Lock, kein
  Encoder-Abort-Refactor.

### Threading
- Punkt 4 `_on_rx_mode_changed` ist GUI-Thread-Slot.
  `qso_sm.stop_cq()` ist heute schon thread-safe (wird an mehreren
  Stellen aufgerufen, z.B. `mw_radio.py:335, 407, 1038, 1308`).

### Tests grün
- Vor jedem Commit: `QT_QPA_PLATFORM=offscreen
  ./venv/bin/python3 -m pytest tests/ -q` → grün.
- Test-Count vor Bundle I: 1205 (v0.97.25).
- Test-Count nach Bundle I: ~1215-1225 (geschätzt +10 bis +20).

### Backup vor Code-Änderung
- `Appsicherungen/2026-05-14_v0.97.25_vor_bundle_i/` anlegen
  bevor Commits beginnen.

### Doku-Pflicht nach Bundle (CLAUDE.md §0-Reihenfolge)
1. HISTORY.md anhängen — `## 2026-05-14 v0.97.26 — Bundle I`
2. HANDOFF.md updaten (Stand + Test-Count)
3. CLAUDE.md Header (Symlink in FT8/ aktualisiert sich)
4. TODO.md (Punkte 1/2/4 erledigt-Sektion)
5. Memory wenn Lesson gelernt — Kandidaten:
   - „Stop-Block bei Mode-Wechsel muss ALLE CQ-Pfade erfassen"
     (lessons-learned aus Punkt 4)
   - „P33-Signal-Split funktioniert nicht so wie gedacht weil
     Courtesy-Send eingebaut ist" (Lesson aus Punkt 2 — eher
     historisch)

### Memory-Lessons relevant
- `feedback_omni_separate_architecture.md` — OMNI ist eigene
  Struktur (Punkt 4 respektiert das: wir greifen NUR `qso_sm.cq_mode`,
  nicht OMNI internals)
- `feedback_partial_fix_check_other_paths.md` — wir prüfen
  `_apply_normal_mode` als parallelen Pfad (AC4.6)
- `feedback_easter_egg_features_e2e_test.md` — E2E-Test-Pflicht
  für OMNI-Features (Punkt 4 Test-Bundle erfüllt das)
- `feedback_r1_encoder_busy_blindspot.md` — R1 verpasst manchmal
  Encoder-Throughput-Races. Für AC4.3 (Encoder-Pending-Queue)
  R1 explizit prompten

---

## Nicht im Scope

- **Gain-Messung vereinheitlichen (P51)** — eigener Workflow, in
  TODO.md notiert, kommt nach Bundle I.
- **Bundle-G/H Field-Tests** — separate Mike-Abnahmen.
- **OMNI-CQ Architektur-Eingriff** — nur Stop-Erweiterung im
  Mode-Wechsel-Pfad. Kein Refactor von `core/omni_cq.py`.
- **P33-Architektur** (2-Signal-Split) bleibt — nur Timing
  ändert sich.
- **PSK-Reset bei Modus-Wechsel** — heute schon korrekt (Bundle C
  P10 reagiert nur auf Protokoll + Band, nicht RX-Mode).
- **Encoder-Abort mid-Slot** — wenn Hardware schon TX, läuft Slot
  zu Ende. Kein hartes Abbrechen.
- **Bekannte Lücke Punkt 2:** Courtesy-Send-Fehler → visual fehlt.
  Wird in HISTORY dokumentiert, kein Fix in diesem Bundle.

---

## Offene Fragen an R1 (V2 → R1 Review-Hinweise)

1. **Encoder-Pending-Queue:** ist sie in
   `core/encoder.py` für normalen CQ-TX überhaupt relevant, oder
   nur OMNI? Falls relevant: muss der Stop-Block sie zusätzlich
   leeren (AC4.3)?

2. **`_apply_normal_mode` parallele Pfade:** sind `mw_radio.py:464`
   und `1167` wirklich nur interne Restore-Pfade (kein User-CQ
   aktiv), oder gibt es einen Pfad wo `_apply_normal_mode` ohne
   `_on_rx_mode_changed` aufgerufen wird UND `qso_sm.cq_mode=True`
   sein kann? (AC4.6)

3. **Bandpilot stoppt CQ — wirklich gewollt?** AC4.5 — Mike-
   Klärung empfohlen, aber R1 soll Plausibilität bewerten.

4. **`on_message_sent` Race mit Decoder:** `_on_tx_finished` ruft
   `on_message_sent`. Kann zwischen TX-Slot-Ende und `on_tx_finished`
   noch ein Decoder-Signal feuern das `on_message_received` triggert
   und damit ein zweites Mal visual emittet? (T2.5 prüft das, aber
   R1 soll Architektur-Verständnis bestätigen.)

5. **Settings-Stylesheet-Vererbung:** wirkt
   `bands_group.setStyleSheet("QCheckBox::indicator { ... }")`
   wirklich nur lokal oder leckt das auf andere QCheckBoxes im
   Settings-Dialog? Qt-Stylesheet-Scope bei nested Widgets ist
   manchmal überraschend.

---

## V2-Ende
