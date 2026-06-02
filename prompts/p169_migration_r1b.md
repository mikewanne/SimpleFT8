# P169 — Re-Review Migrations-Skript (nach deinen R1-Findings gehärtet)

Du hattest `tools/migrate_adif_erfasst.py` mit **NICHT FREIGEBEN** + 7 Findings
abgelehnt. Hier die überarbeitete Version. Prüfe ob die kritischen Punkte (1,2,3,5)
sauber gelöst sind. Am Ende: **AUSFÜHREN FREIGEBEN** / **NICHT FREIGEBEN**.

## Was ich geändert habe (Bezug auf deine Findings)
- **Finding 1 (Verifikation zu schwach, nur Call/Band):** ersetzt durch
  **byte-genaue SHA256-Verifikation**. Jede Quell-.adi MUSS per Hash in erfasst/
  vorhanden sein, bevor gelöscht wird. Parse-unabhängig → fängt auch zwei
  verschiedene QSOs mit gleicher (Call,Band) und korrupte Dateien (Finding 6).
- **Finding 2 (Re-Run-Duplikate):** Kopieren ist jetzt **content-addressed**:
  ist der Hash schon in erfasst/, wird übersprungen. → idempotent + dedupt
  byte-identische Dateien über Ordner hinweg. Re-Run nach Teilausführung erzeugt
  KEINE Duplikate mehr.
- **Finding 3 (rmtree löscht Nicht-ADIF):** **kein rmtree mehr**. Nur verifizierte
  .adi werden EINZELN gelöscht; danach werden nur LEERE Ordner entfernt.
  Nicht-ADIF-Dateien (real gefunden: `_backup_qrz_export/adif_stdout.log`) bleiben
  + werden gemeldet (`leftover`).
- **Finding 4 (kein Rollback):** Löschen einzeln in try/except, Fehler werden
  gezählt + gemeldet; da ALLES vorher kopiert+verifiziert+gesichert ist, ist ein
  Teil-Fehler kein Datenverlust (übrige Quellen = Dubletten von erfasst/).
- **Finding 5 (adif/adif/ blind gelöscht):** wird jetzt NICHT mehr sonderbehandelt
  — `_target_for` schickt adif/adif/*.adi nach importiert/, sie werden also
  kopiert+verifiziert wie alle (Trockenlauf: importiert 46→49). Kein Löschen ohne
  Capture mehr.
- **Finding 7 (Backup mit erfasst/):** Backup-ZIP schließt erfasst/ jetzt aus.

## Verbleibende bewusste Entscheidungen
- Byte-identische Dateien über Ordner werden dedupt (eine Kopie in erfasst/) —
  das ist gewollt (identischer Inhalt, kein Verlust; Hash-Verify garantiert dass
  jeder eindeutige Inhalt erhalten bleibt).
- Nicht-leere Rest-Ordner (z.B. mit adif_stdout.log) bleiben stehen + gemeldet —
  bewusst, lieber etwas Aufräum-Rest als blindes Löschen.

## Fragen
- Sind die kritischen Findings (1,2,3,5) damit wirklich geschlossen?
- Neue Bugs in der überarbeiteten Logik (Hash-Set, Lösch-/rmdir-Schleife,
  leftover-Erkennung)?
- Ist die Migration der 18k QSOs damit vertretbar?

Code im Anhang. Sei wieder maximal kritisch.
