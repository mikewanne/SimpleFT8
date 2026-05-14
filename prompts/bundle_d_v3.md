# Bundle D — V3 (Compact-fest, finale Marschrute)

**Datum:** 2026-05-14 morgens
**Status:** V3 (final, geht ins Code)
**Pre-Files:** `prompts/bundle_d_v[1,2].md` + `bundle_d_r1.md`

V3 fasst alle Findings zusammen und ist die einzige Wahrheit beim
Code-Schreiben. Bei Compact mid-Code muss neue Session aus diesem File
weitermachen können.

---

## 1. Ziel + Scope

5 UI-Tweaks als Bundle nach P50 Field-Test:
A) Settings-Block luftiger | B) DT ±0.0 → 0.0 |
C) Even/Odd-Filter-Buttons (Normal-only) | D) Diversity-Layout-Anpassung
| E) 15s-Slot-Balken Statusbar (NEU, cyan/magenta)

**Version:** 0.97.20 → 0.97.21

---

## 2. R1-verbindliche Antworten (eingearbeitet)

| Q | Entscheidung |
|---|---|
| Q1 Filter-Wirkung | Ausblenden komplett |
| Q4 Modus-Wechsel | Filter immer reset auf „both" |
| Q5 Farben | Even `#00CCFF` cyan, Odd `#FF66CC` magenta |
| Q6 Balken-Form | QProgressBar |
| Q7 Buttons-Style | 2 exclusive QPushButton + QButtonGroup, keiner aktiv = beide |
| Q9 Filter-Klick | Live umfiltern |

---

## 3. Akzeptanzkriterien (final 16 ACs)

### A — Settings-Block luftiger
- **AC1** `bands_grid.setSpacing(6)` → `setSpacing(10)` (konsistent mit
  anderen Dialog-Layouts).
- **AC2** `bands_group.setContentsMargins(10, 18, 10, 10)` für mehr
  Top-Padding (oder vergleichbarer Wert).

### B — DT-Vorzeichen-Entfernung
- **AC3 (R1-S4)** In `ui/rx_panel.py:409-411` ersetzen:
  ```python
  if abs(round(msg.dt, 1)) < 0.05:
      dt_str = "0.0"
  elif abs(msg.dt) < 10:
      dt_str = f"{msg.dt:+.1f}"
  else:
      dt_str = f"{msg.dt:.0f}"
  ```
  Edge-Cases: `+0.04` → `"0.0"`, `-0.04` → `"0.0"`, `+0.06` → `"+0.1"`,
  `-0.06` → `"-0.1"`, `+12.5` → `"13"`.

### C — Even/Odd-Filter-Buttons (Normal-only)
- **AC4 (R1-Q7)** `_even_label` / `_odd_label` in `ui/qso_panel.py` werden
  durch `_btn_even` / `_btn_odd` (QPushButton, checkable) ersetzt. In
  einer `QButtonGroup` mit `setExclusive(False)` — beide können
  ausgeschaltet sein („both"-Modus).
- **AC5** Filter-State `_slot_filter` ∈ {"both", "even", "odd"}.
  Default `"both"`. Nicht persistiert (Q3).
- **AC6** Klick auf `_btn_even` (Toggle):
  - Wenn `_btn_even.isChecked()` und `_btn_odd.isChecked()` → beide
    setChecked(True) widersprüchlich → Filter aus auf „both"
    (uncheck odd).
  - Wenn nur `_btn_even.isChecked()` → Filter = "even".
  - Wenn keiner checked → Filter = "both".
  - Filter = "odd" analog.
  - **KISS-Variante:** QButtonGroup mit exklusivem Toggle, aber Klick
    auf bereits aktiven Button → uncheck (Filter aus). 3 Zustände,
    2 Buttons.
- **AC7 (R1-Q9)** Filter wirkt LIVE auf RX-Panel: `apply_slot_filter`
  iteriert über alle existierenden Zeilen + neue Decodes.
- **AC8 (R1-F1 KRITISCH)** Signal-Verdrahtung: `qso_panel.slot_filter_changed`
  → `rx_panel.apply_slot_filter` connect in `main_window._connect_signals`.
- **AC9 (R1-Q1)** Filter blendet RX-Zeilen des gefilterten Slots
  komplett aus (nicht ausgegraut).
- **AC10 (R1-S1)** Buttons-Style: nutze `rx_panel._FILTER_STYLE` als
  Vorlage (orange-Highlight für active checked).

### D — Diversity-Layout
- **AC11** Im Diversity-Modus: `qso_panel.slot_container.setVisible(False)`.
  QSO/Logbuch-Buttons füllen den freien Platz automatisch (Expanding
  schon da).
- **AC12 (R1-Q4)** Filter-State wird auf „both" gesetzt bei jedem
  rx_mode-Wechsel (Diversity→Normal oder Normal→Diversity), Buttons
  uncheck. Trigger: `main_window._on_rx_mode_changed`.

### E — Slot-Balken Statusbar
- **AC13** Neues Permanent-Widget `_slot_progress_bar` (QProgressBar)
  in `_init_statusbar()` (`main_window.py:458`). Range 0..1000
  (Promille für Smooth), Höhe ~14 px, Text versteckt.
- **AC14 (R1-S3)** `cycle_dur` aus `core/timing.py` lesen (FT8=15s,
  FT4=7.5s, FT2=3.8s). Per Signal/Property gehört der `cycle_seconds()`
  zum Timer.
- **AC15 (R1-Q5)** Farbe wechselt mit Slot-Parity:
  - Even (Slot mit ungeradem Index Sekunde 0-15 etc.) → Cyan `#00CCFF`
  - Odd → Magenta `#FF66CC`
  Über Stylesheet `QProgressBar::chunk { background: <farbe>; }`.
- **AC16** Update via `_tick_cq_countdown` (bereits sekündlich, KISS).
  Auch im Diversity-Modus sichtbar (Slot-Phase ist allgemein, kein
  Filter daran gekoppelt).

---

## 4. Architektur (final)

```
config/settings.py
  ─ unverändert (Filter nicht persistiert per R1-Q3)

ui/settings_dialog.py — Patch
  Z.339:  bands_grid.setSpacing(10)            # AC1
  Z.334+: bands_group.setContentsMargins(...)  # AC2

ui/rx_panel.py — Patch
  Z.409-411: DT-Format mit 0.0-Schutz (AC3)
  NEU: self._slot_filter: str = "both"
  NEU: apply_slot_filter(filter: str)
       → setzt _slot_filter
       → _re_render_all() iteriert + setVisible(False) für falsche Parity
  Z._populate_row: bei neuer Zeile auch _slot_filter prüfen → setVisible

ui/qso_panel.py — Patch
  Z.51-59: _even_label/_odd_label → _btn_even/_btn_odd (QPushButton
           checkable, _FILTER_STYLE)
  NEU: QButtonGroup nicht-exclusive
  NEU: slot_filter_changed = Signal(str)
  NEU: _on_btn_slot_clicked(parity: str) → emittet slot_filter_changed
  NEU: set_slot_buttons_visible(visible: bool)  # AC11
  NEU: reset_slot_filter()  # AC12 → beide uncheck + emit "both"
  Z._update_slot_display: weiter Highlight-Logik, aber an Buttons (nicht
  Labels)

ui/main_window.py — Patch
  Z._init_statusbar (Z.458):
    + self._slot_progress_bar = QProgressBar()
    + setRange(0, 1000); setFixedHeight(14); setTextVisible(False)
    + Stylesheet (border + initial chunk-color)
    + statusBar().addPermanentWidget(_slot_progress_bar)
  Z._connect_signals:
    + qso_panel.slot_filter_changed.connect(rx_panel.apply_slot_filter)
  Z._on_rx_mode_changed (oder vergleichbar):
    + qso_panel.set_slot_buttons_visible(rx_mode == "normal")
    + qso_panel.reset_slot_filter()
  Z._tick_cq_countdown (Z.1191):
    + self._update_slot_progress_bar()
  NEU: _update_slot_progress_bar()
    → cycle_dur = self.timer.cycle_seconds() (oder analog)
    → now_in_slot = time.time() % cycle_dur
    → value = int(now_in_slot / cycle_dur * 1000)
    → is_even = FT8Timer.is_even_cycle() (oder analog)
    → setValue(value)
    → Style-Update mit Cyan/Magenta

tests/test_bundle_d.py NEU — 11 Tests (T1-T11)
```

---

## 5. Atomare Commits (Plan)

| # | Commit | Files | LOC |
|---|--------|-------|-----|
| C1 | Settings-Block-Padding | `ui/settings_dialog.py` | ~5 |
| C2 | DT-Vorzeichen-Entfernung | `ui/rx_panel.py` | ~10 |
| C3 | RX-Panel slot_filter API | `ui/rx_panel.py` | ~50 |
| C4 | QSO-Panel Even/Odd-Buttons | `ui/qso_panel.py` | ~100 |
| C5 | MainWindow Signal + Mode-Reset | `ui/main_window.py` | ~25 |
| C6 | Slot-Progress-Bar Statusbar | `ui/main_window.py` | ~50 |
| C7 | Tests Bundle D | `tests/test_bundle_d.py` NEU | ~250 |
| C8 | APP_VERSION 0.97.21 + Doku + Memory | main.py + HISTORY/HANDOFF/CLAUDE/TODO/Memory | — |

**Gesamt:** ~240 LOC + ~250 Tests + Doku.

---

## 6. Tests T1-T11 (Pflicht per R1-S2)

| # | Test | Was wird verifiziert |
|---|------|---|
| T1 | Settings-Block setSpacing | gridLayout.spacing() == 10 |
| T2 | DT-Format 0.0 → „0.0" | _format_dt(0.0) == "0.0" |
| T3 | DT-Format ±0.04 → „0.0" | beide Vorzeichen rounden auf 0 |
| T4 | DT-Format +0.2 → „+0.2" | positive unverändert |
| T5 | DT-Format -0.5 → „-0.5" | negative unverändert |
| T6 | RXPanel apply_slot_filter("even") | odd-Zeilen hidden |
| T7 | RXPanel apply_slot_filter("both") | alle sichtbar |
| T8 | QSOPanel btn_even click | emittet slot_filter_changed("even") |
| T9 | QSOPanel set_slot_buttons_visible(False) | Container versteckt |
| T10 | MainWindow rx_mode-change Normal→Diversity | buttons hidden + Filter reset |
| T11 | MainWindow Slot-Progress-Bar Farbe | Even=cyan, Odd=magenta Style |

---

## 7. Edge-Cases (final)

- **E1** Filter aktiv bei Mode-Wechsel → reset auf „both" (AC12)
- **E2** Filter wirkt nur RX-Anzeige, NICHT TX/CQ-State (B5 V2)
- **E3** Slot-Balken aktiv auch in Diversity-Modus (zeigt allgemeine
  Slot-Phase, kein Filter-Bezug)
- **E4** `cycle_dur` aus Timer dynamisch — FT4/FT2-Modus passt
- **E5** `_format_dt(-0.0)` muss explizit als „0.0" formattieren (Python
  hat `-0.0 != 0.0` als Float)
- **E6** Filter „even" + alle Stationen sind in Odd-Slot → RX-Panel
  leer. Tooltip auf Filter-Button: „Klick zum Aufheben des Filters".

---

## 8. Field-Test-Checkliste F1-F8

- **F1** Settings → Tab „FT8 & Diversity" → Bänder-Block hat sichtbar
  mehr Luft
- **F2** RX-Panel: DT-Spalte zeigt `0.0` ohne Vorzeichen für sehr
  kleine Werte (z.B. < 0.05)
- **F3** Normal-Modus: EVEN/ODD oben sind klickbare Buttons
- **F4** Klick auf EVEN → Filter aktiv → nur Even-Stationen im
  RX-Panel sichtbar
- **F5** Erneut Klick EVEN oder Klick ODD → Filter ändert sich
- **F6** Modus → Diversity: EVEN/ODD-Buttons verschwinden, QSO/Logbuch
  füllen Breite
- **F7** Modus zurück Normal: Filter ist „both" (beide Buttons aus)
- **F8** Unten rechts: 15s-Slot-Balken füllt sich, wechselt Farbe
  Cyan→Magenta alle Slot (15s/7.5s/3.8s je Modus)

---

## 9. Doku-Update am Ende

- `HISTORY.md` `## 2026-05-14 v0.97.21 — Bundle D UI-Tweaks`
- `HANDOFF.md` neuer Stand + F1-F8
- `CLAUDE.md` Header v0.97.21
- `TODO.md` Bundle D erledigt
- `Memory/project_bundle_d_ui_tweaks.md` + MEMORY.md Index
- `Appsicherungen/2026-05-14_v0.97.20_vor_bundle_d/` Backup

---

## 10. Compact-Fest-Check

- ✅ 16 ACs explizit
- ✅ R1-F1 KRITISCH + R1-S1-S4 als Lösungs-Punkte integriert
- ✅ Q1-Q9 alle verbindlich entschieden
- ✅ 8 atomare Commits mit konkretem Code-Plan
- ✅ 11 Tests T1-T11
- ✅ 8 Field-Test-Punkte F1-F8
- ✅ 6 Edge-Cases E1-E6
- ✅ Doku-Liste
- ✅ Backup-Pfad benannt

**Wenn Compact passiert:** neue Session muss nur dieses File lesen +
Schritt 5 (Code) starten.
