# Bundle D — UI-Tweaks v1 (14.05.2026 morgens)

**Status:** V1 (Initial-Entwurf, geht in V2-Self-Review)
**Mike-Trigger:** P50 Field-Test ✓ + 5 UI-Wünsche in einem Satz:

1. Settings „Sichtbare Bänder" wirkt optisch gedrängt → luftiger
2. DT-Anzeige `+0.0` / `-0.0` → ohne Vorzeichen, einfach `0.0`
3. Even/Odd-Anzeige oben (EVEN | ODD | QSO | Logbuch) → Even/Odd als
   Filter-**Buttons** statt Anzeige. **Nur in Normal-Modus** —
   in Diversity ausblenden, weil zu komplex.
4. Diversity-Modus: Even/Odd weg, QSO/Logbuch-Buttons breiter
5. 15s-Slot-Balken unten rechts farblich grün/gelb für even/odd
   (Mike-Vermutung „haben wir schon" → **stimmt nicht**, gibt's nicht;
   wir bauen ihn). Farb-Empfehlung von DeepSeek einholen.

---

## Ziel

Bundle D ist ein UI-Tweak-Bundle ohne Architektur-Eingriff. KISS-Patches
an 4 Files. Field-Test-tauglich.

---

## Code-Verifikation (Schritt 0 — abgeschlossen)

### A) Settings Bänder-Block
- `ui/settings_dialog.py:339` `bands_grid.setSpacing(6)` (andere
  Layouts im Dialog: `setSpacing(10)`). Auf 10 erhöhen.
- Plus: QGroupBox-`contentsMargins` evtl. erhöhen.

### B) DT-Anzeige
- `ui/rx_panel.py:409-411`:
  ```python
  dt_str = (f"{msg.dt:+.1f}" if abs(msg.dt) < 10
            else f"{msg.dt:.0f}")
  ```
  `f"{0.0:+.1f}"` ergibt `"+0.0"`. `f"{-0.04:+.1f}"` ergibt `"-0.0"`.
  Mike will: `"0.0"` ohne Vorzeichen wenn das Ergebnis 0.0 ist
  (== rundet auf 0.0).

### C+D) Even/Odd & QSO-Panel-Buttons
- `ui/qso_panel.py:45-89` baut die Header-Row:
  - Z.51-52: `_even_label`, `_odd_label` (QLabel, 22 px high, expanding)
  - Z.62-80: `_btn_tab_qso`, `_btn_tab_log` (QPushButton, checkable,
    expanding)
- `slot_container` (HBoxLayout) und `tabs_container` (HBoxLayout) sind
  zwei separate Container nebeneinander.
- `_update_slot_display` (Z.268-289) läuft alle 500 ms, färbt das
  aktive Slot-Label grün (`#00FF88`), das inaktive dunkel.

### E) 15s-Slot-Balken unten rechts
- **Existiert NICHT** in der Statusbar (Code-Check). `_cq_freq_bar`
  (Z.707 control_panel.py) ist 60-Sek-CQ-Such-Balken im Antennen-Card,
  nicht unten rechts.
- Mike-Vermutung war falsch → wir bauen einen neuen Permanent-Widget
  links neben `_stats_indicator` in der Statusbar.

### Slot-Parity-API (wiederverwendbar)
- `core/timing.py` `FT8Timer.is_even_cycle()`
- Universell: `int(time.time() / cycle_dur) % 2 == 0`

---

## Akzeptanz-Kriterien V1 (10 ACs)

### A — Settings-Block luftiger
- **AC1** `bands_grid.setSpacing(10)` (war 6) → konsistent mit anderen
  Dialog-Group-Layouts.
- **AC2** `bands_group.setContentsMargins(10, 18, 10, 10)` oder
  vergleichbarer Wert → mehr Luft zwischen Header und Checkbox-Reihen.

### B — DT-Vorzeichen-Entfernung bei 0.0
- **AC3** `f"{msg.dt:+.1f}"` ersetzt durch Logik: wenn `round(msg.dt, 1)
  == 0.0` → `"0.0"`, sonst `f"{msg.dt:+.1f}"`. **Achtung Python-Falle:**
  `-0.04` rundet auf `-0.0` mit `:+.1f` → muss `abs(round(...)) < 0.05`
  o.ä. nutzen.

### C — Even/Odd als Filter-Buttons (Normal-only)
- **AC4** `_even_label` / `_odd_label` werden zu `QPushButton`
  (checkable, exclusiveGroup mit „BEIDE" als 3. Option, oder
  Toggle-Pattern).
- **AC5** Neuer Zustand: `_slot_filter` ∈ `{"both", "even", "odd"}`.
  Default `"both"`.
- **AC6** Filter wirkt auf RX-Panel: wenn `_slot_filter="even"`,
  werden Odd-Slot-Decodes ausgeblendet (oder ausgegraut?). R1 fragen.
- **AC7** Filter wirkt auf QSO-Verhalten: bei eingehendem Anruf in
  „falschem" Slot → ignorieren? Oder wechseln? R1 fragen.

### D — Diversity-Layout
- **AC8** Im Diversity-Modus (rx_mode == "diversity"): `_even_label`
  und `_odd_label` (bzw. Buttons nach C) werden `setVisible(False)`.
- **AC9** Filter-State wird in Diversity zurückgesetzt auf `"both"`
  (sonst „Filter aktiv aber unsichtbar"-Bug).
- **AC10** QSO/Logbuch-Buttons werden automatisch breiter (QSizePolicy
  Expanding ist schon da — beide teilen den freigewordenen Platz).

### E — 15s-Slot-Balken unten rechts
- **AC11** Neues Permanent-Widget `_slot_progress_bar` in
  `_init_statusbar()` (`main_window.py:458`).
- **AC12** Aktualisiert sekündlich (im `_tick_cq_countdown`-Timer mit
  einklinken).
- **AC13** Farbe wechselt mit Slot-Parity: grün für even, gelb für odd
  (oder welche Farben R1 empfiehlt — siehe R1-Frage Q5).
- **AC14** Tooltip: „Aktueller FT8-Slot — grün=Even, gelb=Odd".

---

## Atomare Commits (Plan)

| # | Commit | Files | LOC |
|---|--------|-------|-----|
| C1 | Settings-Block-Padding | `ui/settings_dialog.py` | ~3 |
| C2 | DT-Vorzeichen-Entfernung | `ui/rx_panel.py` | ~5 |
| C3 | Even/Odd → Filter-Buttons | `ui/qso_panel.py` (+ rx_panel oder mw_qso für Filter-Anwendung) | ~80 |
| C4 | Diversity-Modus: Slot-Buttons ausblenden | `ui/qso_panel.py`, `ui/mw_radio.py` (Signal-Hook) | ~30 |
| C5 | Slot-Balken in Statusbar | `ui/main_window.py` | ~40 |
| C6 | Tests Bundle D | `tests/test_bundle_d.py` NEU | ~150 |
| C7 | APP_VERSION 0.97.21 + Doku | main.py + HISTORY + HANDOFF + CLAUDE + TODO + Memory | — |

---

## Edge-Cases (offen)

- **E1** User aktiviert Even-Filter, dann wechselt App auf Diversity →
  Filter wird auto-reset (AC9). Beim Zurückwechsel auf Normal: Filter
  wieder `"both"` oder letzter Wert? R1 fragen.
- **E2** Was passiert mit Auto-Hunt im Even-Filter? Auto-Hunt
  wählt evtl. Stationen aus dem ausgeblendeten Slot → conflicting?
  → R1 fragen ob Auto-Hunt-Skip oder Filter-Override.
- **E3** OMNI-CQ-Pattern im Filter-Modus? OMNI hat eigene Even/Odd-
  Wahl. Im Filter-Modus Konflikt? OMNI ist Diversity-only → entfällt
  weil Filter Normal-only.
- **E4** Slot-Balken-Granularität: alle 500 ms (passend zu Slot-Label)
  oder sekündlich? KISS: sekündlich (im bestehenden Timer).

---

## R1-Fragen (Q1-Q7)

- **Q1** Even-Filter-Wirkung: RX-Decodes komplett ausblenden oder
  ausgegraut anzeigen (nicht klickbar)? Mike's Use-Case ist „eine
  spezifische Station im Even-Slot anrufen ohne Odd-Stationen
  abzulenken" — ausblenden wäre konsequent. R1: pragmatisch?
- **Q2** Auto-Hunt bei Filter aktiv: Stationen aus gefiltertem Slot
  überspringen oder weiter alle anrufen? R1: was ist UX-intuitiv?
- **Q3** Filter-State über App-Restart persistieren (Settings-Key
  `slot_filter`) oder bei jedem Start auf `"both"`? KISS: nicht
  persistieren.
- **Q4** Filter-State über Modus-Wechsel (Normal → Diversity →
  Normal): zurück auf letzten Wert oder `"both"`? Sicherer:
  `"both"`.
- **Q5** Farben Slot-Balken even/odd: Mike sagt „grün/gelb". Aber
  grün ist schon „aktiv". Andere Vorschläge? Eventuell:
  - Even = **cyan** (`#00CCFF`)
  - Odd = **magenta** (`#FF66CC`)
  oder
  - Even = **grün** (`#00CC66` wie Freq-Label)
  - Odd = **orange** (`#FF8800`)
  R1 hat aesthetisches Auge — welche 2 Farben sind in dunklem Theme
  mit Neon-Akzenten am klarsten unterscheidbar UND nicht schon
  für andere Status-Indikatoren reserviert?
- **Q6** Balken-Form: QProgressBar (zeigt Sekunden 0-15) ODER
  fixe-Breite-Label mit Hintergrundfarbe (zeigt nur Parity, kein
  Sekunden-Fortschritt)? Mike sagt „Balken" → eher Progress.
- **Q7** Even/Odd-Buttons-Style: 2 Toggle-Buttons (exclusive, plus
  „Beide"=`None`) ODER 3 Buttons („Beide/Even/Odd") ODER QComboBox?
  Was passt zu SimpleFT8-Stil (siehe `ui/control_panel.py` Antennen-
  Mode-Buttons als Vorlage)?

---

## Field-Test (für Mike nach Code)

- **F1** Settings öffnen → „Sichtbare Bänder"-Block hat mehr Luft
- **F2** Im RX-Panel: kein `+0.0` / `-0.0` mehr, nur `0.0`
- **F3** Normal-Modus: oben EVEN und ODD sind klickbare Buttons.
  Klick auf EVEN → Filter aktiv → nur Even-Stationen sichtbar.
- **F4** Filter aus → Stationen wieder beide
- **F5** Modus → Diversity: Even/Odd verschwinden, QSO/Logbuch
  füllen die Breite.
- **F6** Modus zurück → Normal: Even/Odd wieder da, Filter auf „Beide".
- **F7** Unten rechts neuer Slot-Balken, wechselt Farbe alle 15 s.
