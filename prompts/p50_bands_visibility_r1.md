# P50.BANDS-VISIBILITY — R1 DeepSeek-Antwort (2026-05-13)

## Q1-Q8 verbindlich

- **Q1 JA — beim Code-Schreiben verworfen (R1-Halluzination).**
  R1 sagte: „Bandpilot soll deaktivierte Bänder nicht empfehlen."
  Beim Code-Schreiben fiel auf dass Bandpilot **nur Mode-Wechsel
  innerhalb eines Bandes** vorschlägt (`recommend_for_hour(band, hour,
  current_mode)` → returnt einen Mode-Code, nicht ein Band). Bandpilot
  kann ein deaktiviertes Band NIE empfehlen, weil er gar keine Band-
  Wechsel macht. C5 entfällt. T11 entfällt. AC11/AC14 entfällt.
  → Code ist Referenz, nicht R1.
- **Q2 Variante A** Grid-Lücken akzeptieren (KISS), Prop-Bars
  mit-verstecken. Variante C als v0.98+ falls Mike das hässlich findet.
- **Q3 JA Signal** wie `country_filter_changed`. Pull-Pattern wäre
  inkonsistent mit Codebase.
- **Q4 NEIN** Default nicht persistieren. Idempotent → neue Bänder
  zukünftig automatisch aktiv.
- **Q5 QCheckBox-Standard** KISS. Toggle-Buttons wäre Overengineering.
- **Q6 NEIN** Kein Tooltip / Statusbar-Anzeige. Settings-Dialog reicht.
- **Q7 Variante A** Aktuelles Band beim App-Start in enabled_bands
  zwangs-aufnehmen. Konsistent mit AC5 für Live-Toggle.
- **Q8 JA Pflicht** Prop-Bar-Test T9.

## Bewertung 7/10

Solider KISS-Ansatz, P32-Pattern wiederverwendet, aber „Underengineering
an kritischen Stellen" — speziell `_set_band()` ohne enabled_bands-Check.

## Findings

### KRITISCH
- **F1** `_set_band()` ohne enabled_bands-Guarantee: externe Aufrufer
  (Bandpilot, Auto-Hunt) können unsichtbares Band setzen → unsichtbarer
  aktiver Button. **Fix:** `set_visible_bands()` MUSS sicherstellen dass
  `current_band` immer sichtbar bleibt.
- **F2** Prop-Bars werden nicht mit-versteckt → Geister-Pulse.

### SOLLTE
- **S3** Reset-Button in Settings setzt enabled_bands nicht zurück.
- **S4** Bandpilot filtert deaktivierte Bänder nicht.

### KÖNNTE
- **K5** Grid-Re-Layout bei vielen deaktivierten Bändern (v0.98+).

### HINWEIS
- **H6** Tests T9+T10 fest eingeplant.
- **H7** Settings-Persistenz robust (try/except in load, kein concurrent write).

## V3-Marschrute

1. Settings-API (get/set_enabled_bands)
2. `set_visible_bands()` mit Prop-Bar + current_band-Guarantee
3. `_set_band()` absichern via `set_visible_bands()`
4. Bandpilot-Filter
5. Reset-Button fixen
6. Tests T1-T11 inkl. T9 Prop-Bars + T10 App-Start
