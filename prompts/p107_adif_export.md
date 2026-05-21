# P107 — Brainstorm: ADIF-Export-Button

Mike-Wunsch 21.05.2026 nach P106-ADIF-Reparatur. Mike braucht künftig
einen UI-Button um manuell ADIF-Files zu exportieren (statt das
adif_repair.py-Script via Terminal zu nutzen).

## Mike-Fragen

1. **Wo gehört der Export-Button hin — Logbuch oder Settings?**
2. **Export-Reichweite:**
   - Alle jemals geloggten QSOs?
   - Ab bestimmten Zeitraum (Datum-Range)?
   - Beides als Optionen?
3. **Output-Verzeichnis** — File-Dialog für User, oder fest in
   `adif/exports/`?

## Aktueller Stand

- Pro Tag wird eine eigene ADIF-Datei geschrieben:
  `adif/SimpleFT8_LOG_YYYYMMDD.adi`
- Reparatur-Script `tools/adif_repair.py` kann alle Files seit 29.03.
  in 1 Komplett-File zusammenfassen.
- Heute hat Mike das per Skript zu
  `/Users/mikehammerer/Downloads/test/SimpleFT8_ALL_repaired.adi`
  zusammengefasst (147 Records) und zu QRZ hochgeladen.
- ADIF-Format ist seit P106 v0.97.83 WSJT-X-Minimal (Industry-Standard).

## Vorhandene UI

- **QSO-Panel** (`ui/qso_panel.py`) hat 2 Tabs:
  - „QSO" (Live-Verlauf)
  - „Logbuch" (`LogbookWidget`)
- **Logbuch** hat schon Buttons: „QRZ" (Bulk-Upload), Spalten-Header,
  Tabellen-Layout.
- **Settings-Dialog** hat 4 Tabs (Station, TX & Schutz, FT8 & Diversity,
  Daten & Tools).
- „Daten & Tools"-Tab wäre logischer Heimathafen — passt zu
  „Export"-Semantik.

## Hypothesen wo der Button hin sollte

**H1 — Logbuch-Tab:** direkt im Logbuch oben/unten neben „QRZ"-Button.
Vorteil: User ist beim Anschauen seiner QSOs, Button-Klick zum Export
ist natürlich. Nachteil: Logbuch ist QSO-Verlauf-Anzeige, Export ist
„Wartungs"-Aktion.

**H2 — Settings „Daten & Tools":** wie alle anderen Wartungs-Aktionen
(Bandpilot-MD-Export, Statistik-Cleanup). Vorteil: konsistent mit
anderen Tools. Nachteil: User muss Settings öffnen für Routine-Export.

**H3 — Beides:** Quick-Button im Logbuch (Default: alles export) +
erweiterte Optionen in Settings (Datum-Range, Format-Wahl).

## R1-Fragen

1. Welche der H1-H3 ist am Mike-Spec-konformsten (Hobby-Funker-Tool)?
2. Export-Reichweite: alles oder Datum-Range? Falls Range — wie ist
   die UI ohne Overengineering (Datepicker × 2)?
3. Naming: „ADIF Export"? „Logbuch exportieren"? „QSO-Export"?
4. File-Dialog wirklich pro Klick öffnen, oder Standard-Pfad mit
   Datum-Suffix (`Logbuch_2026-05-21.adi`) als Default?
5. Sollte nach Export ein Confirm-Dialog kommen („X QSOs exportiert
   nach Y") oder reicht Statusbar-Toast?
6. KISS-Antwort bitte — kein Overengineering.
