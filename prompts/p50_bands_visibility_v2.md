# P50.BANDS-VISIBILITY — Plan V2 (Self-Review)

**Datum:** 2026-05-13 nachmittags
**Status:** V2 (Self-Review nach V1, geht an R1)

V1 lesen: `prompts/p50_bands_visibility_v1.md`

V2 ist die kritische Eigen-Durchsicht VOR DeepSeek. Ich gehe jede Annahme
in V1 nochmal durch und sammle das was ich übersehen habe.

---

## A. Was V1 richtig macht

- KISS-Ansatz (kein Auto-Switch, keine Bandpilot-Filter, kein Statistik-Filter).
- Persistenz-Pattern aus P32 wiederverwendet (defensive Filter + Default Fallback).
- AC3 Min-1-Logik verhindert „Toter Settings-Dialog".
- 8 Tests T1-T8 deckt Settings + UI + Roundtrip ab.

---

## B. Was V1 übersehen hat — Schwachstellen

### B1 — Grid-Layout-Lücken bei `setVisible(False)` ⚠️

`ui/control_panel.py` Z.291-368 baut die Band-Buttons in einem
**QGridLayout mit `setColumnStretch(col, 1)` für Spalten 1-5**. Wenn ich
einen Button via `setVisible(False)` verstecke, **bleibt die Grid-Zelle
leer** — die Spalte wird trotzdem gestretcht. Bei deaktiviertem 12m und
17m hätte Zeile 1 dann: `[10m] [GAP] [15m] [GAP] [20m]` mit jeweils 20%
Spaltenbreite.

**Optisch hässlich.** Mike wird das nach Field-Test bemängeln.

**Optionen:**
- **Opt-A (KISS):** Lücken akzeptieren. Begründung: Mike deaktiviert
  meist nur 1-2 Bänder; falls er wirklich viele deaktiviert sieht es
  zwar nicht ideal aus aber das Feature ist trotzdem nützlich. Code
  bleibt klein.
- **Opt-B (Re-Layout):** Bei jeder `set_visible_bands(...)` das Grid
  reorganisieren. Alle sichtbaren Buttons werden in Reihe gepackt
  (Zeile 1 = ersten 5, Zeile 2 = nächsten). Komplex weil die Prop-Bars
  unterhalb der Buttons mitwandern müssen.
- **Opt-C (Compromise):** Buttons aus Layout entfernen+wieder einsetzen
  bei Toggle. Reorder via `grid.addWidget(btn, row, new_col)`.

**Mein Vorschlag:** Opt-A erst probieren. Wenn Mike's Field-Test sagt
„zu hässlich", in v0.98+ Opt-C nachziehen.

→ **R1 fragen welche Variante empfohlen wird.**

### B2 — Prop-Bars müssen mitversteckt werden

Zeile 343-346 / 356-359 in `control_panel.py`: zu jedem Band-Button
gehört eine `_PulseBar` direkt darunter (Propagation-Indikator).
Wenn ich nur den Button verstecke aber die Prop-Bar weiterläuft,
bleibt die Bar als „Geister-Pulse" sichtbar.

→ **V1 hat das nicht erwähnt.** In V3 explizit: `prop_bars[b].setVisible(False)`
für jedes deaktivierte Band.

### B3 — Initial-Band bei App-Start prüfen

Aktuell: bei App-Start wird `current_band` aus Settings geladen
(`main_window.py` Init-Logik). Was wenn das Band deaktiviert wurde
während der App-Laufzeit, dann App geschlossen, dann neu gestartet?

**Szenario:** User hat 20m aktiv. Deaktiviert 20m in Settings, OK
geklickt. Aktuelles Band bleibt 20m sichtbar (AC5). User schließt App.
App neu starten → liest 20m aus Settings → setzt aktuell auf 20m.
Aber 20m ist nicht in `enabled_bands`. Was zeigt das Panel?

**Risiko:** Der Button für 20m existiert nicht im sichtbaren Bereich.
Aber `_set_band("20m")` ruft `setChecked(True)` auf einem versteckten
Button. Optisch ist das ein Bug — der User sieht das aktive Band
nirgendwo angezeigt.

**Fix:** Bei App-Start: wenn `current_band not in enabled_bands` →
2 Optionen:
- **A:** `current_band` in `enabled_bands` zwangs-aufnehmen (sichtbar
  machen), wie AC5 für Live-Toggle.
- **B:** Auf erstes verfügbares Band wechseln.

→ **R1 fragen welche Variante.** Vorschlag: **A** für Konsistenz mit AC5.

### B4 — Bandpilot Frage Q1 nochmal

V1 sagt: Bandpilot ignoriert `enabled_bands`. R1 soll bestätigen.
Aber ich finde V1's Begründung („Bandpilot soll Empfehlung ungestört
abgeben") schwach. Wenn der User ein Band deaktiviert hat, will er es
wirklich nicht — eine Bandpilot-Empfehlung dafür wäre verwirrend
(„Wechsel zu 60m" wo 60m gar nicht klickbar ist).

**Bessere Variante:** Bandpilot soll deaktivierte Bänder nicht
empfehlen. Aber das ist Eingriff in `core/mode_recommender.py` (Folge:
mehr Test-Aufwand). → R1 fragen.

### B5 — Statusbar/Indikator?

V1 hat Q4: „NEIN, kein Statusbar-Hinweis". Aber: wenn der User nicht
weiß warum Bänder fehlen (z.B. er hat in Settings geklickt und vergessen),
hilft ein dezenter Hinweis. **Mein Vorschlag:** Tooltip auf dem
ControlPanel-Header („Sichtbar: 7 von 9 Bändern"). Kein Statusbar-
Eintrag. Minimal-invasiv.

→ R1 fragen ob das nötig oder Overengineering.

### B6 — Edge-Case: Bandwechsel via Bandpilot zu unsichtbarem Band

Wenn Bandpilot Auto-Switch zu z.B. 60m ausführt und 60m ist deaktiviert,
würde das Band gesetzt UND der unsichtbare Button getoggled. User sieht
„kein Band aktiv". Selbe Wurzel wie B3.

→ Wenn B3 mit Variante A löst (current_band zwangs-aufnehmen), ist
B6 auch gelöst.

### B7 — Tests für Prop-Bars

V1's Tests T1-T8 prüfen Buttons aber **nicht die Prop-Bars**. Neuer
Test T9: nach `set_visible_bands(["20m", "40m"])` ist `prop_bars["10m"]`
nicht sichtbar.

### B8 — Settings-Migration / Default-Persistenz

V1 Q5 sagt: Default wird nicht persistiert. Aber wenn der Default-Wert
sich in einer zukünftigen Version ändert (z.B. neues Band kommt dazu),
gibt es User die haben den alten Default in Settings stehen — und
verpassen das neue Band. **Aber:** bei `enabled_bands` ist der Default
„alle 9 Bänder" und das ändert sich kaum. → R1 Frage: Eventuell trotzdem
beim ersten Speichern persistieren?

### B9 — Visueller Style des Settings-Blocks

V1 sagt 3×3 QCheckBox-Grid. Aber: SimpleFT8 hat ein dunkles Theme mit
Neon-Akzenten. Standard-QCheckBox sieht „Windows-Standard"-mäßig aus.
**Mein Vorschlag:** Stylesheet-Anpassung mit dem App-Theme (grüne
Checkmarks, dunkler Background). Oder QPushButton.setCheckable als
Toggle-Buttons wie im Band-Panel selbst (visuell konsistent).

→ R1 fragen ob das Overengineering oder UX-relevant ist.

### B10 — Live-Update via Signal vs. Method-Call

V1 architektiert „settings_dialog ruft main_window.apply_visible_bands()".
Aber das ist Pull-Pattern (UI ruft Method). Sauberer wäre ein Signal
`settings_dialog.visible_bands_changed.emit(list)` → main_window connected.
Pattern wie `country_filter_changed`. Konsistent mit Codebase.

---

## C. ACs erweitert / korrigiert

Auf Basis B1-B10:

- **AC1 unverändert** Settings-Dialog Tab „Sonstiges" mit Grid.
- **AC2 unverändert** Default = alle 9.
- **AC3 unverändert** Min 1 aktiv.
- **AC4 unverändert** Live-Update beim Apply.
- **AC5 NEU präzisiert** Aktuelles Band wird AUTOMATISCH in `enabled_bands`
  aufgenommen wenn `current_band not in enabled_bands` — sowohl bei
  Live-Toggle ALS AUCH bei App-Start. Konsistenz B3+B6.
- **AC6 unverändert** Persistierung Key `enabled_bands`.
- **AC7 unverändert** Defensive Filter.
- **AC8 unverändert** Empty-Fallback.
- **AC9 NEU** Prop-Bars werden mit dem Band-Button mit-versteckt (B2).
- **AC10 NEU (R1-abhängig)** Layout-Variante: A (Lücken-KISS) oder C
  (Re-Layout). R1 entscheidet.
- **AC11 NEU (R1-abhängig)** Bandpilot filtert deaktivierte Bänder
  aus seinen Empfehlungen oder nicht. R1 entscheidet.

---

## D. Offene Fragen an R1

- **Q1 (V1 Q1)** Bandpilot deaktivierte Bänder filtern oder nicht?
- **Q2 NEU (V2 B1)** Layout-Lücken-Variante A vs. C — welche?
- **Q3 (V1 Q3)** Live-Update via Signal vs. Method-Call — Signal sauberer?
- **Q4 (V1 Q5)** Default beim ersten Save persistieren?
- **Q5 NEU (V2 B9)** Settings-UI: QCheckBox-Standard oder Toggle-Buttons
  mit App-Theme?
- **Q6 NEU (V2 B5)** Tooltip auf ControlPanel-Header („X von 9 sichtbar")
  oder gar nichts?
- **Q7 NEU (V2 B3)** Aktuelles Band beim App-Start in enabled_bands
  zwangs-aufnehmen oder auf erstes verfügbares wechseln?
- **Q8 NEU (V2 B7)** Test-Coverage für Prop-Bar-Visibility ist Pflicht
  — bestätigen oder als „nice to have" einstufen?

---

## E. Implementations-Reihenfolge (V2-aktualisiert)

| # | Commit | Files | Größe |
|---|--------|-------|-------|
| C1 | settings: enabled_bands API + Default | `config/settings.py` | ~30 LOC |
| C2 | control_panel: set_visible_bands + Prop-Bar Sync | `ui/control_panel.py` | ~30 LOC |
| C3 | settings_dialog: UI-Block + Signal | `ui/settings_dialog.py` | ~80 LOC |
| C4 | main_window: Signal-Connect + Initial-Apply | `ui/main_window.py` | ~15 LOC |
| C5 | (R1) Bandpilot-Filter falls Q1=ja | `core/mode_recommender.py` | ~15 LOC |
| C6 | Tests T1-T11 | `tests/test_p50_bands_visibility.py` NEU | ~320 LOC |
| C7 | APP_VERSION + HISTORY + HANDOFF + TODO + CLAUDE + Memory + Backup | Doku | — |

**Größe:** wenn Q1=nein, ~155 LOC + ~320 Tests.
Wenn Q1=ja, ~170 LOC + ~370 Tests.

---

## F. Tests V2-aktualisiert (T1-T11)

| # | Test | Bestätigt was? |
|---|------|---|
| T1 | Settings load — kein Key | Default alle 9 |
| T2 | Settings load — ungültige Bänder | defensive Filter |
| T3 | Settings load — leere Liste | Default Fallback |
| T4 | control_panel.set_visible_bands | Buttons werden versteckt |
| T5 | set_visible_bands — aktuelles Band | bleibt + wird in Liste aufgenommen |
| T6 | settings_dialog Mindest-1 | letzte Checkbox geblockt |
| T7 | settings_dialog roundtrip | Toggle → Save → Load → identisch |
| T8 | settings_dialog Apply | Signal/Method ruft Main-Window |
| T9 NEU | Prop-Bar Visibility | `prop_bars[b].setVisible(False)` |
| T10 NEU | App-Start mit ungültigem current_band | wird in enabled_bands aufgenommen |
| T11 NEU | (falls Q1=ja) Bandpilot filtert deaktivierte | `recommend()` returnt nur enabled |

---

## G. Workflow-Compliance-Check

- ✅ Code-Verifikation gemacht (Schritt 0)
- ✅ V1 entworfen
- ✅ V2 Self-Review fertig (B1-B10 + Q1-Q8 + ACs aktualisiert + AC9-AC11
  neu + Tests T9-T11)
- ⏳ Geht jetzt an R1
- ⏳ V3 nach R1-Antwort
- ⏳ Code in atomaren Commits
- ⏳ Final-R1
- ⏳ Doku-Update

R1 muss explizit auf Q1-Q8 antworten + V1+V2 Konsistenz prüfen +
ggf. eigene Schwachstellen finden die ich übersehen habe.
