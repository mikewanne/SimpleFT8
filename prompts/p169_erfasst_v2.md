# P169 — Design-Review: „erfasst/"-Verzeichnis + mode-genauer Worked-Filter

Du bist Senior-Architekt für SimpleFT8 (PySide6/Python, Hobby-Funker-Tool, KISS,
FlexRadio). Reviewe diesen DESIGN-Entwurf kritisch — noch KEIN Code. Mike hat die
Richtung freigegeben; ich brauche deine Architektur-Prüfung + Stolperfallen +
KISS-Check (Overengineering?), bevor ich den finalen Plan vorlege.

## Ziel (Mike)
1. **Ordnung:** EIN Verzeichnis `adif/erfasst/` = einzige Quelle für „schon
   gearbeitet?" (Filter). Alle anderen (Kraut-und-Rüben-)Ordner weg.
2. **Import-Funktion:** fertige `.adi` (z.B. QRZ-Export) wählen → Kopie nach
   `erfasst/` → Index neu lesen.
3. **Mode-genauer „NEUE"-Filter** in der RX-Liste: Station auf 20m FT8 gearbeitet
   → bei NEUE auf 20m FT8 ausblenden, auf 20m FT4 ZEIGEN, auf 15m FT8 ZEIGEN.
4. Auto-Hunt soll dieselbe mode-genaue „gearbeitet"-Erkennung nutzen + bei „alles
   gearbeitet" eine Transparenz-Meldung zeigen (statt still nichts zu tun).

## Verifizierter IST-Zustand (Code gelesen)
- **Filter-Index** `log/qso_log.py`: lädt aus 4 Orten via `directory.glob("*.adi")`
  (NICHT rekursiv): `Path.cwd()` (=SimpleFT8/, 0 Dateien), optional
  `settings["adif_import_path"]`, `adif/hochgeladen/` (15), `adif/_backup_qrz_export/`
  (2, ~18k QSOs). Index ist `_worked` (set[call]) + `_worked_band` (set[(call,band)])
  + Land-Zähler. **Keine Betriebsart.**
- **`add_qso(call, band)`** wird beim QSO-Abschluss LIVE aufgerufen (mw_qso.py:657)
  — aber mode-blind, und nur im RAM (nicht persistiert in eine geladene Quelle).
- **App schreibt** neue QSOs via `AdifWriter` nach `adif/` (cwd/adif). Diese
  Dateien sind NICHT im Filter-Index (qso_log lädt cwd, nicht cwd/adif).
- **Upload-Tracking:** `_on_qrz_upload` lädt `logbook._all_records` (aus adif/ +
  adif/hochgeladen/), filtert Records deren `_SOURCE_FILE` NICHT „hochgeladen"
  enthält → das sind die noch-hochzuladenden. Nach Upload wandern Dateien nach
  `adif/hochgeladen/`. Also ordner-basiertes Upload-Tracking via `_SOURCE_FILE`.
- **ADIF schreiben** (adif.py:273): FT8→`MODE=FT8`, FT4→`MODE=MFSK+SUBMODE=FT4`,
  FT2→`MFSK+FT2` (ADIF-Standard). Parser liest MODE+SUBMODE bereits in `rec`.
- **Mikes QRZ-Export** hat `MODE=FT8` (10877) + `MODE=FT4` (1147), KEIN SUBMODE
  (QRZ-Konvention). → Normalisierung muss BEIDE Schreibweisen fangen.
- **Migrations-Umfang gemessen:** aktuell geladen = 8007 unique Calls; ALLE .adi
  unter adif/ rekursiv = 8102. → **95 Calls leben NUR in nicht-geladenen Ordnern**
  (`repaired/` 22 Dateien, `archiv/_konsolidiert/` 20, `adif/adif/` etc.). Dürfen
  bei der Migration NICHT verloren gehen.
- **NEUE-Filter** (rx_panel.py:798): nutzt `qso_log.is_worked(caller)` =
  gearbeitet auf IRGENDEINEM Band/Mode/jemals. Viel zu grob.
- **Auto-Hunt** (auto_hunt.py:484): filtert `is_worked_on_band(call, band)` (P165,
  band-only) → auf vollem Band „all_worked_on_band" → still kein Ruf.

## Mein Design-Entwurf (V1)

### A) Verzeichnis `adif/erfasst/` — eine Quelle, REKURSIV gelesen
```
adif/
  erfasst/
    neu/          ← App schreibt fertige QSOs hierher (noch nicht zu QRZ hoch)
    hochgeladen/  ← nach QRZ-Upload hierher verschoben
    importiert/   ← importierte Fremd-Exporte (QRZ etc.) — schon auf QRZ
  exports/        ← generierte Gesamt-Exporte (Output, KEIN Filter-Input)
```
- **Filter + Logbuch lesen `erfasst/` REKURSIV** (rglob) → alles darin zählt als
  „gearbeitet" (neu + hochgeladen + importiert). Erfüllt Mikes „alles in erfasst".
- **Upload-Kandidaten** = Records deren `_SOURCE_FILE` in `erfasst/neu/` liegt
  (NICHT hochgeladen/, NICHT importiert/ — importierte sind schon auf QRZ!).
  Nach Upload: `neu/` → `hochgeladen/`. Bestehende `_SOURCE_FILE`-Logik bleibt,
  nur Pfade ändern sich.
- **App-Schreibziel:** `AdifWriter` → `erfasst/neu/` statt `adif/`. Damit ist ein
  QSO sofort „erfasst" (gefiltert), unabhängig vom Upload → schließt die Lücke
  „eben gefunkt, taucht nach Neustart wieder als neu auf".

### B) Migration (EINMALIG, Datensicherheit!)
1. **Backup** des ganzen `adif/` (ZIP, Zeitstempel).
2. Alle `.adi` rekursiv parsen, nach Herkunft sortieren:
   - schon-hochgeladene App-QSOs (waren in `hochgeladen/`) → `erfasst/hochgeladen/`
   - Fremd-Importe (`_backup_qrz_export`) → `erfasst/importiert/`
   - lose App-QSOs (adif/ Wurzel, repaired/, archiv/) → `erfasst/neu/` (noch
     hochzuladen?) ODER `erfasst/hochgeladen/`? (→ FRAGE 3 unten)
3. **Verifikation:** unique-Call-Zahl vorher (8102) == nachher. Bei Abweichung
   → STOPP, nicht löschen.
4. Erst nach grüner Verifikation die alten Ordner löschen.

### C) Mode-genauer Index (`qso_log.py`)
- Beim Einlesen Mode normalisieren: `effective_mode = SUBMODE if SUBMODE else MODE`
  (fängt `MFSK+FT4`→FT4, `FT4`→FT4, `FT8`→FT8, `MFSK+FT2`→FT2).
- Neuer Index `_worked_band_mode: set[(call, band, mode)]` + Methode
  `is_worked_on_band_mode(call, band, mode)`. `_worked` + `_worked_band` bleiben
  (Awards/Land-Logik nutzen sie weiter).
- `add_qso(call, band, mode="")` erweitern (Live-Vermerk mode-genau).

### D) NEUE-Filter (rx_panel.py)
- `is_worked(caller)` → `is_worked_on_band_mode(caller, aktuelles_band, aktueller_mode)`.
- rx_panel braucht Zugriff auf aktuelles Band + Mode (via Setter/Callback aus
  main_window — heute hat es nur `_qso_log`).

### E) Auto-Hunt (auto_hunt.py)
- `is_worked_on_band(call, band)` → `is_worked_on_band_mode(call, band, mode)`.
- Wenn nach Filterung 0 Kandidaten weil alle gearbeitet → einmalige Meldung im
  QSO-Log/Status: „Alle N sichtbaren Stationen auf {band} {mode} schon gearbeitet
  — warte auf neue." (Transparenz, Mikes Wunsch.)

### F) Import-Funktion (UI)
- Button „ADIF importieren" im Logbuch → QFileDialog → Datei validieren (parsebar?)
  → nach `erfasst/importiert/` kopieren (Namensconflict-sicher) → qso_log reload →
  Meldung „X QSOs erfasst (Y neu)".

## Meine Selbst-Review-Bedenken (V2) — bitte mitprüfen
1. **Datenverlust-Risiko Migration** — die 95 nur-in-Altordnern-Calls. Reicht
   Backup + Vorher/Nachher-Count, oder brauchen wir mehr (z.B. pro-QSO-Diff)?
2. **Re-Upload-Gefahr:** importierte QRZ-QSOs dürfen NIE wieder hochgeladen werden.
   Ist „Upload-Kandidat = nur erfasst/neu/" wasserdicht? Was wenn jemand einen
   Export aus Versehen nach neu/ legt?
3. **Migration von losen App-QSOs:** woher weiß ich ob ein loses `adif/*.adi`
   schon hochgeladen wurde? Wenn unklar → nach `neu/` (Risiko: Doppel-Upload zu
   QRZ — QRZ lehnt Dubletten aber ab?) oder nach `hochgeladen/` (Risiko: nie
   hochgeladen)? Was ist sicherer?
4. **Rekursives Lesen** von `erfasst/` bei ~8100 Calls / ~12k QSOs: ~0.5s gemessen
   für den großen Export — unkritisch? Doppel-Parsen wenn dieselbe QSO in mehreren
   Unterordnern? (Set-Dedup fängt's, aber Performance.)
5. **Flat vs. Unterordner:** Mike wollte „alles in erfasst". Ist die `neu/
   hochgeladen/ importiert/`-Struktur ein guter Kompromiss (rekursiv gelesen) oder
   sollte erfasst/ FLACH sein + Upload-Status über einen Marker (z.B. JSON-Set)?
   Was ist KISS-konformer?
6. **Scope/Reihenfolge:** Ist es klüger, das als ZWEI getrennte Workflows zu
   machen (Phase 1 Ordnung+Migration+Import, Phase 2 Mode-Filter) — oder als eins?
7. **Übersehe ich etwas?** LocatorDB lädt auch aus diesen Ordnern (main_window
   ~264), Logbuch-Anzeige, `adif_import_path`-Setting (Altlast?). Bricht was?

## Fragen an dich
- Ist das Design sauber + KISS, oder Overengineering (3 Unterordner zu viel)?
- Sicherste Migrations-Strategie für die losen/unklaren App-QSOs (V2-Punkt 3)?
- Flat+Marker vs. Unterordner-rekursiv (V2-Punkt 5) — deine Empfehlung?
- Mode-Normalisierung `SUBMODE else MODE` — Edge-Cases (CW/SSB/leer/Q65)?
- Reihenfolge: ein Feature oder zwei Phasen?
- Konkrete Stolperfallen die ich übersehe?

Sei kritisch und konkret. Code ist Referenz. Anhang: qso_log.py + adif.py.
