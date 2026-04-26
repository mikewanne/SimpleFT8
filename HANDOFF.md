# HANDOFF — SimpleFT8 — 2026-04-26

## Heute erledigt — 5 Versionen, 11 Commits, alle gepusht

**v0.60 — CQ-Counter QSO-Reset + Info-Box Normal-Preset alt** (commit `68cb208`, `b9ed2eb`)
- Bei aktivem QSO wird der 60s-CQ-Such-Counter pro Slot zurueckgesetzt → kein Mid-QSO-Frequenzsprung
- Bei Wechsel zum Normal-Modus mit Preset > 30 Tage: einmaliger Info-Dialog mit Empfehlung KALIBRIEREN-Button

**v0.61 — Antenna-Pref Hysterese + Live-QSO-Anzeige** (commit `5138cce`)
- `core/antenna_pref.py`: `if delta > HYSTERESIS_DB` → `>=`. Bei delta=+1.0 (haeufig) wird jetzt korrekt A2 gewaehlt.
- Label-Format vereinheitlicht ueber `_antenna_pref_label`: `(ANT2 ↑X.X dB)` mit Pfeil = Diversity-Gewinn
- Live-Anzeige im QSO-Panel `status_label`: waehrend aktivem QSO `→ CALL  |  RX: ANT2 ↑1.0 dB` (gruen, fett)
- 3 neue Tests fuer Hysterese-Edge-Cases

**v0.62 — Normal-Modus = WSJT-X-Standard** (commit `e007dc4`)
- Auto-CQ-Frequenz-Suche im Normal-Modus entfernt
- Klick im Histogramm setzt TX-Marker, QSpinBox unter Histogramm zur Feinjustierung
- Persistenz pro Band: `normal_tx_freq_per_band`
- Diversity-Modus bleibt mit Auto-Suche (USP)

**v0.63 — 20m FT8 PDF + Stats-Filter** (commit `8693ee2`)
- Stats-Filter: nur 20m + 40m FT8 werden in `statistics/` protokolliert (Skalierungs-Entscheidung)
- 20m FT8 PDF (DE+EN) mit eigenem Narrativ: resonante TX + Diversity-RX = asymmetrischer Vorteil
- Theorie-Block: Faraday-Rotation skaliert mit f² → 20m-Diversity wirkt staerker als 40m

**v0.64 — Aging-Bug-Fix** (commit `47f96aa`)
- Aging in SLOTS statt Sekunden: `7/14/20` Slots fuer normal/active_qso/cq_caller
- DeepSeek-Korrektur: `7/14/20` statt urspruenglich `5/10/20` (auf FT4 zu aggressiv gewesen)
- FT2 jetzt sauber: 27s Aging statt vorher 75s = 20 Slots
- Architektur: `slot_duration_s` als Parameter durchgereicht
- 2 neue Tests + 1 angepasst, 220 grün

**v0.65 — CSV-Export Diversity-Daten + UI-Integration** (commit `3315ff6`)
- Standalone-Script `scripts/export_diversity_csv.py`: 4 CSVs, 675 Datensaetze
- UI-Integration im Settings-Dialog: GroupBox "Datenexport" + QFileDialog → Verzeichnis-Wahl
- Refactor `export_all(output_dir)` Helper, vom Script und UI nutzbar
- Letzter Pfad in `csv_export_dir` Setting persistiert

**Brainstorming + TODO-Plan dokumentiert** (commit `61eee49`)
- DeepSeek-Beratung zu Verbesserungen + Architektur (continuation_id 625b1dab)
- 6 Features priorisiert in TODO.md: Aging-Fix(✓), PSK-Reporter, Richtungs-Keulen TX/RX, CSV(✓), Audio-Export
- PSK-Reporter API technisch verifiziert (Endpoints, Polling, Trend-Detection)

## Offen / Naechste Schritte (priorisiert)

Siehe `TODO.md` fuer detaillierten Plan und Code-Skeletons.

1. **B) Band-Indikatoren live mit PSK-Reporter** (1-2 Tage)
   - Bestehende HamQSL-Indikatoren unter Band-Buttons ergaenzen mit Live-Aktivitaets-Daten
   - Pulsierender Balken bei Trend (oeffnet/schliesst) — je staerker desto schneller
   - QPropertyAnimation auf eigenem Widget mit paintEvent
   - PSK-Reporter API: `psk-find.pl?mode=FT8&lastMinutes=5` — 1 Request alle Baender

2. **C) Richtungs-Keulen TX-Pattern** (2-3 Tage) — **USP-Killer**
   - Welche Sektoren haben mich gehoert? PSK-Reporter Reverse-Lookup
   - Maidenhead → Lat/Lon → Großkreis-Azimut von JO31 → 16-Sektor-Bin
   - Visualisierung: Weltkarte mit Sektor-Overlay (Keulen) oder Polar-Diagramm

3. **D) Richtungs-Keulen ANT2 RX-Rescue** (1-2 Tage zusaetzlich)
   - Lokale Rescue-Daten (ANT1 ≤ -24, ANT2 dekodiert) → Sektor-Verteilung
   - Im selben Diagramm wie C ueberlagert (TX vs RX-Diversity)

4. **F) Audio-Export per Slot** (<1 Tag, optional)

5. Aus alter Liste: Even/Odd Timer, Gain-Bias, Tertile-Analyse, IC-7300 Fork

## Warnungen & Fallen (heute neu)

- **Aging-Bug-Fix v0.64:** Wenn Tests irgendwo `accumulate_stations()` ohne `slot_duration_s` aufrufen,
  wird Default 15.0 (FT8) genommen. Bei FT2-Tests muss `slot_duration_s=3.8` uebergeben werden.
- **CSV-Export Output-Dir:** Default ist `auswertung/` im Repo. Im UI waehlt User Verzeichnis,
  Pfad wird in `csv_export_dir` Setting persistiert (mehrfach-Klicks merken letzte Wahl).
- **DeepSeek Continuation-IDs:** bei Folge-Fragen kann es zur Verwechslung kommen wenn vorheriger
  Kontext noch im Thread ist. Ggf. neuen Thread starten ohne `continuation_id`.
- **20m-Datenbasis duenn:** PDF zeigt das ehrlich mit "Datenbasis waechst noch"-Caveat. Stunden
  06-09 UTC und 20-23 UTC sind unterrepraesentiert — gezielt messen.

## Test-Suite Status

`./venv/bin/python3 -m pytest tests/ -q` → **220 passed**

## Letzter bekannter guter Zustand

- Branch `main`, alle Commits gepusht (`66f44c8` → `3315ff6`)
- App v0.65 laeuft, alle 5 Features stabil (Live-Anzeige, manuelle TX, Antenna-Pref, Aging, CSV-Export)
- Statistiken aktuell, PDFs DE+EN fuer 40m+20m generiert
- TODO-Plan in `TODO.md` mit DeepSeek-validierter Naechste-Schritte-Reihenfolge

## Heute insgesamt

- **5 Versionen** (v0.60 → v0.65)
- **11 Commits** auf main, alle gepusht
- **220 Tests grün** (vorher 211)
- **9 neue Tests** (Hysterese, Aging-Edge-Cases, Settings-tx_freq)
- **2 neue PDFs** (20m DE + EN)
- **4 neue CSV-Exports** (675 Datensaetze)
- **1 strategische TODO-Liste** mit 6 priorisierten Next-Features
- **DeepSeek-Beratung** durchgaengig genutzt, Vorschlaege immer kritisch verifiziert
