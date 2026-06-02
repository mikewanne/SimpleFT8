# P169 — Review: ADIF-Migrations-Skript (löscht 18k-QSO-Ordner!)

Reviewe `tools/migrate_adif_erfasst.py` KRITISCH. Es konsolidiert alle verstreuten
.adi-Dateien nach `adif/erfasst/{neu,hochgeladen,importiert}/` und LÖSCHT danach
die alten Ordner. Es fasst Mikes ~18.000-QSO-Historie an — ein Datenverlust wäre
fatal. Finde JEDE Lücke. Am Ende: **AUSFÜHREN FREIGEBEN** / **NICHT FREIGEBEN**.

## Kontext (verifiziert)
- Trockenlauf-Ergebnis: 72 Dateien migriert (11→neu, 15→hochgeladen, 46→importiert),
  9646 unique (Call,Band) zu sichern. 3 leere `adif/adif/exports`-Dateien (0 QSOs)
  werden übersprungen + der Ordner gelöscht.
- Klassifikation ist Mike-freigegeben (Variante A): historisch → importiert/
  (kein Re-Upload), frische App-QSOs (adif/-Wurzel) → neu/, schon-hochgeladene →
  hochgeladen/.
- Strategie: COPY → VERIFY → DELETE. Backup-ZIP zuerst. Bei Verifikations-
  Abweichung ABBRUCH ohne Löschen.
- Danach lesen Filter/Logbuch/LocatorDB `erfasst/` REKURSIV (rglob).

## Meine Selbst-Review-Bedenken (bitte prüfen + ergänzen)
1. **Verifikations-Granularität:** Ich vergleiche die Menge `(Call, Band)`
   (`pre - post` muss leer sein). Das schützt das FILTER-Ziel. ABER: zwei QSOs
   mit gleicher (Call,Band) → wenn eine Datei verloren ginge, bliebe (Call,Band)
   trotzdem da (aus der anderen) → Verifikation würde es NICHT merken. Sollte ich
   zusätzlich auf RECORD-Ebene prüfen (Anzahl QSO-Records in erfasst/ ≥ Quelle,
   oder Datei-für-Datei dass jede Quelldatei kopiert wurde)? Was ist robust genug?
2. **copy2 + Namens-Konflikt:** bei Namensgleichheit hänge ich `ts_parent_name`
   davor. Reicht das, oder kann eine Datei still überschrieben werden?
3. **Lösch-Reihenfolge:** ich lösche erst NACH grüner Verifikation. Backup-ZIP
   vorher. Ist die Reihenfolge wasserdicht? Was wenn rmtree mittendrin scheitert?
4. **Re-Run:** Wenn das Skript nach Teilausführung erneut läuft (erfasst/ existiert
   schon) — Doppel-Kopien? Datenverlust? (`_source_files` schließt erfasst/ aus,
   `_key_for` gibt für erfasst/ None zurück.)
5. **Backup-Vollständigkeit:** ZIP des ganzen adif/ inkl. evtl. schon vorhandenem
   erfasst/. Größen-Mindestcheck (>1000 Bytes). Genug?
6. **Übersehe ich Datenverlust-Pfade?** Symlinks, versteckte Dateien, Nicht-.adi-
   Dateien in den Ordnern die mit-gelöscht würden (rmtree löscht alles im Ordner,
   nicht nur .adi!). Gibt es in repaired/archiv/exports evtl. Nicht-.adi-Dateien
   die wichtig sind?

## Fragen
- Ist copy→verify→delete + Backup sicher genug für 18k QSOs?
- Beste Verifikations-Methode (Punkt 1 + 6)?
- Konkrete Bugs/Edge-Cases im Code?

Sei maximal kritisch — lieber ein Risiko zu viel. Code im Anhang.
