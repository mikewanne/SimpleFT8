# P50.BANDS-VISIBILITY — Plan V1

**Datum:** 2026-05-13 nachmittags
**Status:** V1 (Initial-Entwurf, geht in V2-Self-Review)
**Trigger:** Mike-Wunsch nach P34-Stufe2: „und dann machen wir die bänder zum abwählen :-)"

---

## 1. Ziel

Der User soll im Settings-Dialog einstellen können welche Bänder im
Band-Panel angezeigt werden. Bänder die er nicht braucht (z.B. weil er
keine passende Antenne hat oder das Band nie betreibt) verschwinden aus
dem Button-Grid in `ControlPanel.ModeBandCard` — kein Klick-Risiko, kein
visueller Müll.

**Was es NICHT ist:** Kein Bandpilot-Filter, kein Auto-Hunt-Eingriff,
keine Statistik-Filterung. Es ist ein reiner UI-Sichtbarkeits-Toggle.

---

## 2. Ist-Zustand (Code-Verifikation Schritt 0)

- **Band-Buttons:** `ui/control_panel.py:335,349` — zwei hardcoded Listen
  `bands_row1 = ["10m", "12m", "15m", "17m", "20m"]` und
  `bands_row2 = ["30m", "40m", "60m", "80m"]`. Speicherung in Dict
  `self.band_buttons[b] = btn` (Z.290 init, Z.341/354 fill).
- **Band-Wahl:** `_set_band(self, band)` Z.1412-1417 setzt
  `_current_band`, ruft `setChecked()`, emittet `band_changed`-Signal.
- **Kanonische Bänder-Liste:** `config/settings.py:13-23` — `BAND_FREQUENCIES`
  Dict mit allen 9 Bändern und Modi-Frequenzen.
- **Persistenz-Pattern (Vorlage P32):** `rx_panel_hidden_cols` —
  `settings.get("rx_panel_hidden_cols", [])` + defensive Filter im UI
  + Save via Signal-Pattern.
- **Settings-Dialog:** `ui/settings_dialog.py` Tab-basiert (Radio/Audio/
  Betrieb/Sonstiges). Kein bestehendes Multi-Choice-Widget — neu bauen.

---

## 3. Akzeptanzkriterien (AC)

- **AC1** Im Settings-Dialog Tab „Sonstiges" gibt es eine QGroupBox
  „Sichtbare Bänder" mit 9 QCheckBoxes in 3×3-Raster (10/12/15, 17/20/30,
  40/60/80).
- **AC2** Default (keine Einstellung gespeichert) = alle 9 Bänder
  aktiviert. Backward-kompatibel mit existierenden settings.json.
- **AC3** Mindestens 1 Band muss aktiviert sein. Wenn User das letzte
  ankreuzt-aus, wird die Checkbox geblockt (gleichzeitig disable +
  Tooltip „Mindestens ein Band muss aktiv sein").
- **AC4** Beim Schließen des Settings-Dialogs (Apply/OK) wird
  `ControlPanel.set_visible_bands(list)` gerufen → Band-Buttons werden
  live aktualisiert (deaktivierte verschwinden, aktivierte erscheinen
  wieder).
- **AC5** Aktuell ausgewähltes Band wird vom User deaktiviert →
  **bleibt sichtbar** (Mike-KISS-Variante: Auto-Switch wäre Overengineering;
  User wählt selbst nächstes Band beim nächsten Bandwechsel).
- **AC6** Persistierung in `~/.simpleft8/settings.json` Key
  `"enabled_bands"`: List of strings, z.B. `["20m", "40m"]`.
- **AC7** Defensive Filter beim Load: ungültige Einträge (kein String,
  Band nicht in `BAND_FREQUENCIES`, Duplikate) werden ignoriert.
- **AC8** Defensive Filter bei leerer Liste (z.B. korrupte Settings) →
  Fallback: alle 9 Bänder. Kein leeres Band-Panel.

---

## 4. Architektur

```
config/settings.py
  + Default: enabled_bands = list(BAND_FREQUENCIES.keys())
  + get_enabled_bands() → list[str]   (mit defensiver Filterung)
  + set_enabled_bands(list[str])      (Filter + Save)

ui/control_panel.py (ModeBandCard)
  + set_visible_bands(bands: list[str])
    → Buttons anzeigen/verstecken via .setVisible()
    → Buttons bleiben im Dict, nur die Sichtbarkeit ändert sich
    → Falls aktuelles Band versteckt: bleibt sichtbar (Override)
  + _all_band_buttons (Dict bleibt vollständig, set_visible_bands filtert)

ui/settings_dialog.py
  + Neue QGroupBox „Sichtbare Bänder" in Tab „Sonstiges"
  + 9 QCheckBoxes in 3×3-Grid, geladen aus settings.get_enabled_bands()
  + on_apply: settings.set_enabled_bands(checked) + main_window.apply_visible_bands()
  + Mindest-1-Logik: bei letzter aktiver Checkbox → setEnabled(False) +
    setToolTip + on_click_attempt re-check

ui/main_window.py
  + apply_visible_bands() Methode
    → liest settings.get_enabled_bands()
    → ruft control_panel.set_visible_bands(...)
  + Aufruf 1: am __init__-Ende nach control_panel.show()
  + Aufruf 2: aus settings_dialog Apply-Callback

tests/test_p50_bands_visibility.py NEU
  T1: Settings load — kein Key → Default alle 9 Bänder
  T2: Settings load — ungültige Bänder werden gefiltert
  T3: Settings load — leere Liste → Default Fallback
  T4: control_panel.set_visible_bands — Buttons werden versteckt/gezeigt
  T5: control_panel.set_visible_bands — aktuelles Band bleibt sichtbar
  T6: settings_dialog Mindest-1-Logik — letzte Checkbox kann nicht aus
  T7: settings_dialog roundtrip — Toggle → Save → reload → identisch
  T8: settings_dialog Apply ruft main_window.apply_visible_bands
```

---

## 5. Implementations-Reihenfolge (atomare Commits)

| # | Commit | Files | Größe |
|---|--------|-------|-------|
| C1 | settings: enabled_bands API | `config/settings.py` | ~30 LOC |
| C2 | control_panel: set_visible_bands | `ui/control_panel.py` | ~20 LOC |
| C3 | settings_dialog: UI-Block | `ui/settings_dialog.py` | ~70 LOC |
| C4 | main_window: apply_visible_bands + Signal | `ui/main_window.py` | ~15 LOC |
| C5 | Tests P50 | `tests/test_p50_bands_visibility.py` NEU | ~250 LOC |
| C6 | APP_VERSION + HISTORY + HANDOFF + TODO + CLAUDE | Doku | — |

**Gesamt:** ~135 LOC Code + ~250 LOC Tests + Doku.

---

## 6. Edge-Cases & offene Fragen

### Edge-Cases (eingeplant)

- **E1** Aktuelles Band wird deaktiviert → bleibt sichtbar (AC5).
- **E2** Letztes aktives Band → Checkbox-Block (AC3).
- **E3** Settings ohne `enabled_bands`-Key → Default alle 9 (AC2).
- **E4** Ungültige/korrupte enabled_bands-Werte → defensive Filter (AC7).
- **E5** Leere Liste → Default Fallback (AC8).

### Offene Fragen für V2 / R1

- **Q1 (Bandpilot)** Bandpilot empfiehlt evtl. ein deaktiviertes Band.
  Sollen wir diese Empfehlung skippen? **Vorschlag:** NEIN — Bandpilot
  ist über alle Bänder hin gleich, der User sieht ja die Empfehlung im
  Toast/Dialog und kann selber entscheiden. Wenn er ein deaktiviertes
  Band empfohlen bekommt, ignoriert er es. Bandpilot soll seine
  Empfehlung ungestört abgeben, andernfalls verzerren wir seine Daten.
  → Bestätigung von R1 holen.
- **Q2 (Auto-Hunt)** Auto-Hunt arbeitet auf aktuellem Band, nicht
  Band-übergreifend. Kein Eingriff nötig.
- **Q3 (Live-Update vs. Restart-Required)** Live-Update beim Settings-OK
  ist KISS — Buttons werden via `.setVisible(False/True)` umgeschaltet,
  kein Re-Build des UI nötig. **Vorschlag:** Live-Update.
- **Q4 (Statusbar-Anzeige)** Soll die Statusbar zeigen wenn nicht alle
  Bänder sichtbar sind? **Vorschlag:** NEIN — der Settings-Dialog ist
  die einzige Stelle wo der Status sichtbar wird. Statusbar nicht
  überladen.
- **Q5 (Migration)** Existierende settings.json haben kein `enabled_bands`.
  Beim ersten Lesen wird der Default gesetzt — soll bei Save (auch ohne
  User-Aktion) der Key persistiert werden? **Vorschlag:** NEIN —
  Idempotenter Default, kein Migrations-Eintrag. Settings bleibt minimal.

---

## 7. Doku-Update (am Ende)

- `HISTORY.md` Eintrag `## 2026-05-13 v0.97.20 — P50 Bänder-Sichtbarkeit`
- `HANDOFF.md` neuen Stand
- `CLAUDE.md` Header v0.97.20 + Test-Count
- `TODO.md` Bänder-Deaktivierung als ERLEDIGT markieren
- `Memory` `project_p50_bands_visibility.md` + MEMORY.md Index
- `Appsicherungen/2026-05-13_v0.97.19_vor_p50_bands_visibility/` Backup

---

## 8. Field-Test-Checkliste (für Mike nach Push)

- **F1** Settings öffnen → Tab „Sonstiges" → Sichtbare Bänder-Block sichtbar?
- **F2** Alle 9 Checkboxes aktiv (Default)?
- **F3** 60m + 80m abwählen → OK → Band-Panel zeigt nur noch 7 Bänder?
- **F4** Settings erneut öffnen → 60m/80m noch abgewählt?
- **F5** App neu starten → 60m/80m noch abgewählt?
- **F6** Alle bis auf 1 abwählen → letzte Checkbox blockiert?
- **F7** Auf 60m wechseln, dann 60m abwählen → 60m bleibt aktuell sichtbar bis Bandwechsel?
- **F8** Bei Bandwechsel: ist 60m noch im Panel? (KISS: ja, bis User selbst wechselt)
