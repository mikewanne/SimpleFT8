Du bist Senior Python-Entwickler spezialisiert auf Amateurfunk-Software und
PySide6 (Signal statt pyqtSignal). Hobby-FT8-Tool, ein Operator.

Deine einzige Aufgabe: diesen Prompt KRITISIEREN — NICHT lösen. Strukturierte
Liste: Lücken, Unklarheiten, Widersprüche, Risiken (besonders DATENVERLUST),
Verbesserungen. Severity: 🔴 Bug | 🟠 Risiko | 🟡 Verbesserung | ⚪ Hinweis.
SCOPE-RESPEKT, KISS vor Defensiv. Overengineering ist selbst ein Fehler.

================================================================================
P170 — Upload-Move: bei Namens-Kollision MERGEN statt überspringen
================================================================================

## Ist-Zustand (verifiziert am echten Datenstand)

Nach erfolgreichem QRZ-Bulk-Upload verschiebt `ui/mw_qso.py:_handle_qrz_file_results`
jede vollständig hochgeladene Tagesdatei von `adif/erfasst/neu/` nach
`adif/erfasst/hochgeladen/` (Bedingung: `fail==0 && processed==expected &&
processed>0`; nur Pfade unter `/erfasst/neu/`; `processed = ok+dup+fail`).

**Bug (Mike-Field):** Liegt im Ziel `hochgeladen/` schon eine Datei mit
GLEICHEM Namen, bricht der Move ab (`if dest.exists(): skip`) → die Datei bleibt
in `neu/` → die QSOs häufen sich dort an und werden bei jedem Upload erneut
angeboten (als QRZ-Dups). Das passiert NICHT selten: WSJT-artige Tagesdateien
heißen immer gleich (`SimpleFT8_LOG_YYYYMMDD.adi`) — wer vormittags hochlädt
(→ hochgeladen/) und nachmittags weiterfunkt, erzeugt eine gleichnamige
neu/-Datei. Aktuell echt: `neu/` = 205 QSOs in 12 Dateien, **11 davon haben einen
gleichnamigen Zwilling in `hochgeladen/`** (Folge der Phase-1-Migration, die
Vormittags-/Nachmittags-Sessions desselben Tages in beide Ordner einsortierte).
Inhalte der Zwillinge sind VERSCHIEDEN (verschiedene QSOs desselben Tages).

## Mike-Entscheidung: MERGEN (eine Tagesdatei)

Bei Kollision sollen die QSO-Records der `neu/`-Datei an die vorhandene
`hochgeladen/`-Datei ANGEHÄNGT werden (eine Datei pro Tag), dann die
`neu/`-Datei gelöscht. Nicht: umbenennen (`_2.adi`).

================================================================================
## ZIEL
================================================================================

`_handle_qrz_file_results` mergt bei `dest.exists()` statt zu überspringen.
Die eigentliche Merge-Logik liegt in einer PUREN, testbaren Funktion in
`log/adif.py`.

================================================================================
## AKZEPTANZKRITERIEN
================================================================================

1. Neue Funktion `log/adif.py:merge_adif_files(src: Path, dest: Path) ->
   tuple[int, int]`:
   - Hängt die QSO-Records aus `src` an `dest` an. Dedup per Key
     `(CALL, QSO_DATE, TIME_ON)` gegen die bereits in `dest` vorhandenen
     Records UND innerhalb von `src` (kein Doppelt-Anhängen).
   - `dest`-Header bleibt; `src`-Header (alles vor `<EOH>`) wird verworfen.
     Nur Blöcke mit `CALL` werden angehängt (kein Header-/Leer-Müll).
   - **Atomar schreiben:** neuen Dest-Inhalt in eine Temp-Datei schreiben, dann
     `os.replace(tmp, dest)`. Original-Records byte-erhaltend (Blöcke + `<EOR>`
     im Originaltext anhängen, NICHT neu serialisieren).
   - Gibt `(appended, skipped_dup)` zurück. `dest` MUSS existieren (Aufrufer
     garantiert das).
2. `_handle_qrz_file_results` (`ui/mw_qso.py`): im `dest.exists()`-Zweig statt
   skip → `merge_adif_files(src, dest)`, dann `src.unlink()` ERST NACH
   erfolgreichem Merge (so ist ein Abbruch idempotent — Re-Run dedupt). Eigener
   Zähler `merged`. Fehler (OSError) abfangen + Statusbar, src bleibt.
3. Unverändertes Verhalten: kein Ziel vorhanden → normaler `shutil.move`;
   `fail>0` oder `processed<expected` → skip (kein Move/Merge); Pfade NICHT unter
   `/erfasst/neu/` → nie bewegt (Doppel-Move-Schutz bleibt).
4. Idempotenz: zweiter Lauf mit derselben (schon gemergten) Quelle hängt 0 an
   (alle Keys schon in dest) und löscht src.
5. Tests grün: `QT_QPA_PLATFORM=offscreen ./venv/bin/python3 -m pytest tests/ -q`.

================================================================================
## BETROFFENE DATEIEN
================================================================================

- `log/adif.py` — neue `merge_adif_files` (Vorbild Block-Splitting: bestehende
  `delete_qso`, Zeile 66; `parse_adif_file`, Zeile 41).
- `ui/mw_qso.py:942-986` — `_handle_qrz_file_results` dest-exists-Zweig.
- `tests/test_p1_qrz_upload_ui_2.py:321` — `test_handle_file_results_skips_when_
  dest_exists` schreibt das ALTE Skip-Verhalten fest (greift dort sogar nur über
  den Pfad-Guard, weil src NICHT unter erfasst/neu/ liegt) → auf Merge umstellen
  (src unter erfasst/neu/ mit echtem ADIF, dest mit echtem ADIF, nach Aufruf:
  src weg, dest = Union dedupliziert).

================================================================================
## RANDBEDINGUNGEN
================================================================================

- **DATENSICHERHEIT (höchste Prio):** `dest` enthält echte, bereits auf QRZ
  hochgeladene QSOs. Append darf NIE Records verlieren oder dest korrumpieren.
  Atomar (Temp + os.replace). `src` erst nach erfolgreichem dest-Write löschen.
- **Threading:** läuft im GUI-Thread (`_on_qrz_bulk_finished`), keine
  Nebenläufigkeit auf diesen Dateien.
- **Keine externen Aufrufe** (kein erneuter QRZ-Call) — reine Dateioperation.
- **Encoding:** `parse_adif_file` liest mit `errors="replace"`; Append konsistent
  (utf-8).
- Hardware/TX: nicht berührt.

================================================================================
## NICHT IM SCOPE
================================================================================

- Den QRZ-Upload selbst, die Kandidaten-Auswahl (= nur neu/), die
  Move-Bedingung (fail/processed) ändern.
- Einmal-Bulk-Bereinigung der aktuellen 205: passiert von selbst, sobald Mike
  nach dem Fix EINMAL „QRZ" klickt (Re-Upload = lauter Dups, fail==0 → Merge je
  Datei → neu/ leert sich). KEIN Skript, kein Hand-Anlegen an den Daten.
- Umbenennen-Strategie (`_2.adi`) — bewusst verworfen (Mike: mergen).
- Verändern, wie Logbuch/Export erfasst/ liest (dedupt schon per Key).

================================================================================
## TESTBARKEIT (unverzichtbar)
================================================================================

- `merge_adif_files`: dest 1 QSO + src 2 QSOs (1 davon = Dup zu dest) → nach
  Merge dest 2 QSOs, return (1,1); src bleibt unangetastet (nur Aufrufer löscht).
  dest-Header genau einmal vorhanden. Records byte-erhalten.
- Atomarität: keine `.tmp`-Reste nach Erfolg.
- `_handle_qrz_file_results` Kollision: src(erfasst/neu/) + gleichnamige dest →
  src gelöscht, dest = Union dedupliziert.
- Idempotenz: zweiter Merge-Aufruf hängt 0 an.

================================================================================
## OFFENE FRAGEN AN DICH (DeepSeek)
================================================================================

A) Atomares Schreiben via Temp + os.replace im selben Verzeichnis — korrekt für
   Datensicherheit, oder Overkill für kleine Tagesdateien (append-Modus reicht)?
B) Dedup-Key (CALL, QSO_DATE, TIME_ON) — ausreichend eindeutig für FT8/FT4, oder
   Kollisionsgefahr (2 echte QSOs gleicher Call/Datum/Sekunde)? Folge?
C) Übersehene Datenverlust-/Korruptions-Pfade beim Append an echte 18k-relevante
   Daten?
D) Soll bei einem Block OHNE CALL (nur Header-Rest/Müll) wirklich übersprungen
   werden, oder gibt es legitime ADIF-Records ohne CALL, die verloren gingen?
