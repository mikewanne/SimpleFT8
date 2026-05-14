# Bundle D — R1 DeepSeek-Antwort (14.05.2026)

## Q1-Q9 verbindlich

- **Q1 Ausblenden** (KISS, Mike-Use-Case)
- **Q2 Entfällt** (Auto-Hunt Diversity-only, Filter Normal-only)
- **Q3 NEIN** persistieren — Default „both" bei App-Start
- **Q4 IMMER reset** auf „both" bei Modus-Wechsel (Diversity↔Normal)
- **Q5 Even=`#00CCFF` Cyan, Odd=`#FF66CC` Magenta** — keine Kollision
  mit grün/gelb/blau/rot, neon-konform
- **Q6 QProgressBar** mit Farb-Wechsel
- **Q7 2 exclusive QPushButton + QButtonGroup** — keiner aktiv = beide
- **Q8 Keine** Auswirkung auf weitere RX-Anzeigen
- **Q9 Live umfiltern** (sofort, nicht erst neue Decodes)

## Bewertung 7/10

Plan sauber, aber: F1 Signal-Verdrahtung fehlt, Tests Pflicht (S2),
Style-Konsistenz (S1), cycle_dur dynamisch statt 15 hardcoded (S3),
DT-Formatter-Code-Stelle präzise benennen (S4).

## Findings

### KRITISCH
- **F1** Filter-State wird nicht propagiert: muss in `main_window`
  `qso_panel.slot_filter_changed.connect(rx_panel.apply_slot_filter)`
  + `apply_slot_filter` in `rx_panel.py` bauen.

### SOLLTE
- **S1** Style aus `rx_panel._FILTER_STYLE` für Even/Odd-Buttons
  übernehmen (konsistent).
- **S2** Tests T1-T11 Pflicht im Bundle.
- **S3** Slot-Balken `cycle_dur` aus `core/timing.py` lesen (FT8=15,
  FT4=7.5, FT2=3.8), nicht hardcoden.
- **S4** DT-Formatter-Patch in `rx_panel._populate_row` Z.409-411
  ersetzen.

### KÖNNTE
- **K1** 500ms-Update für Slot-Balken (smoother) — KISS bleibt sekündlich.
- **K2** Bei Normal→Diversity: Filter-Reset OK; Rücksprung
  Diversity→Normal: Filter wieder „both" (bereits in V2 ACs).

### HINWEIS
- **H1** Settings-Min-1-Logik OK so.
- **H2** `_cycle_duration` muss bei Modus-Wechsel aktualisiert werden.
- **H3** `_on_rx_mode_changed` triggert Filter-Reset.

## V3-Marschrute

1. Settings-API für Filter (kein settings-Key — nur in-Memory)
2. `qso_panel.slot_filter_changed` Signal + Buttons + Style
3. `rx_panel.apply_slot_filter(filter)` + live-Re-Render
4. `main_window` Signal-Connect + Mode-Wechsel-Reset
5. Slot-Progress-Bar in Statusbar mit cycle_dur + Farb-Wechsel
6. Tests T1-T11 + Final-R1
