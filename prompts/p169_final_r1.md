# P169 Phase 1 — Final-R1: Code-Umstellung auf adif/erfasst/

Reviewe die Code-Änderungen (Diff im Anhang) der Phase 1. Migration-TOOL +
Design wurden bereits separat freigegeben (PUSH/AUSFÜHREN FREIGEBEN). Hier geht
es um die App-Code-Umstellung. Am Ende: **PUSH FREIGEBEN** / **NICHT FREIGEBEN**.

## Kontext
Ziel: EINE rekursiv gelesene Worked-Before-Quelle `adif/erfasst/` (Unterordner
neu/ hochgeladen/ importiert/) statt der alten verstreuten Mehr-Quellen-Logik.
Migration der echten 18k QSOs ist bereits gelaufen + verifiziert (byte-genau,
9647 (Call,Band) erhalten). Tests: 2303→**2312** grün (+9 `test_p169_erfasst.py`).

## Was geändert wurde (Diff anbei)
- **log/qso_log.py:** `load_directory(dir, recursive=False)` + neuer `clear()`
  (für Reload nach Import in DERSELBEN Instanz → Referenzen in auto_hunt/rx_panel
  bleiben gültig, kein Doppel-_count).
- **log/adif.py:** `parse_all_adif_files(dir, recursive=False)`;
  `AdifWriter.directory` → `adif/erfasst/neu/` (App-Schreibziel);
  `export_all_records` liest jetzt `adif/erfasst/` rekursiv, nur `SimpleFT8_LOG_*`
  (App-Logs) → importierte QRZ-Historie (andere Namen) wird NICHT re-exportiert.
- **core/locator_db.py:** `bulk_import_directory(dir, recursive=False)`.
- **ui/main_window.py:** qso_log + LocatorDB laden nur noch `adif/erfasst/`
  rekursiv (alte 3-Quellen-Logik raus); neuer Handler `_on_adif_imported` →
  `qso_log.clear()` + reload + LocatorDB-Reload.
- **ui/mw_qso.py:** Upload-Kandidaten = NUR Records mit `_SOURCE_FILE` in
  `/erfasst/neu/` (hochgeladen/ + importiert/ ausgeschlossen — kein Re-Upload der
  Fremd-Historie!); Verschieben nach Upload `erfasst/neu/` → `erfasst/hochgeladen/`.
- **ui/logbook_widget.py:** Anzeige lädt `erfasst/` rekursiv; Diplome nutzen
  `_all_records` direkt (enthält jetzt die importierte Historie → separater
  Backup-Load entfällt); neuer Import-Button + `_import_adif_file`-Kern
  (validiert ≥1 CALL, kopiert mit Zeitstempel nach `erfasst/importiert/`) +
  Signal `adif_imported` → MainWindow-Reload.

## Worauf ich besonders deine Prüfung will
1. **Upload-Kandidaten-Filter** (`"/erfasst/neu/" in _SOURCE_FILE`): wasserdicht,
   dass importierte (erfasst/importiert/) + schon-hochgeladene NIE erneut zu QRZ
   gehen? Funktioniert die `_SOURCE_FILE`-Pfad-Prüfung mit Windows-Backslashes
   (`.replace("\\","/")` ist drin)?
2. **clear()+reload nach Import**: korrekt, dass die SELBE qso_log-Instanz geleert
   + neu geladen wird (statt neue Instanz)? Übersehe ich eine Referenz die nach
   clear() kurz inkonsistent ist (Thread/Decoder liest parallel)?
3. **export_all_records**: `rglob("SimpleFT8_LOG_*.adi")` unter erfasst/ — schließt
   das die importierte Historie wirklich zuverlässig aus? Was wenn migrierte
   App-Logs (repaired/) in importiert/ liegen und SimpleFT8_LOG_* heißen → werden
   die mit-exportiert? Schlimm?
4. **Diplome ohne separaten Backup-Load**: stimmt, dass `_all_records` (= erfasst/
   rekursiv inkl. importiert/) die komplette Diplom-Datenbasis ist?
5. **Übersehene Stellen**: greift noch irgendwo Code auf adif/hochgeladen/,
   adif/_backup_qrz_export/ oder adif/ (flach) zu? (Ich habe 8 Touchpoints
   umgestellt.)
6. Bugs/Edge-Cases im Diff?

Sei kritisch. Diff im Anhang.
