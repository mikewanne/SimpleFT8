# P1.QRZ-UPLOAD-UI-2 V2 — Self-Review

**Stand:** 2026-05-07.
**Workflow:** V1 → **V2 (diese Datei)** → R1 → V3 → Compact → Code.
**Aufgabe:** V1 als „frische KI" reviewen — Luecken, Mehrdeutigkeiten,
falsche Annahmen.

---

## L1 — V1 §4.1 hat falsche Annahme: `parse_all_adif_files` setzt schon `_DATETIME`

V1 sagt: „record bekommt _source_file, schon teilweise da via _DATETIME
und Co." — das ist **falsch**. `_DATETIME` wird in `logbook_widget.py`
in `_format_datetime(record)` zur Anzeigezeit gebaut, NICHT als
record-Field. ADIF-Records aus `parse_all_adif_files` haben nur die
ADIF-Standard-Keys (`CALL`, `BAND`, `MODE`, `QSO_DATE`, `TIME_ON`, ...).

**V2-Korrektur:** `_source_file` wird als ERSTES interne Feld eingefuehrt.
Pattern: alle internen Felder mit `_`-Prefix (siehe `key.startswith("_")`-
Skip in `log/qrz.py:upload_qso_from_dict`). Damit landet `_source_file`
NIEMALS im ADIF-Upload — perfekt.

`log/adif.py:parse_all_adif_files(adif_dir)` Schleife muss umbauen:
```python
for adi_file in sorted(adif_dir.glob("*.adi")):
    records_in_file = parse_adi(adi_file)
    for rec in records_in_file:
        rec["_source_file"] = str(adi_file.resolve())
    all_records.extend(records_in_file)
```

---

## L2 — V1 verpasst: `parse_all_adif_files` muss `recursive=False` bleiben

Wenn `LogbookWidget.load_adif()` plant beide Verzeichnisse zu lesen
(`adif/` UND `adif/hochgeladen/`), dann muss `parse_all_adif_files`
NICHT recursive werden — sonst:
- `adif/` wuerde `adif/hochgeladen/` MIT-laden
- File-Move-Logik wuerde wieder zurueckgreifen auf alle Files

**V2-Empfehlung:** zwei separate Aufrufe:
```python
records_active = parse_all_adif_files(adif_dir / ".")  # nur top-level
records_archived = parse_all_adif_files(adif_dir / "hochgeladen")
all_records = records_active + records_archived
```

`parse_all_adif_files` selbst nutzt `glob("*.adi")` (NICHT `rglob`) —
muss aktuell schon so sein, V2 verifiziert das in V3.

---

## L3 — V1 §4.3 Worker-Signal-Erweiterung: 6 Args sind grenzwertig

V1 schlaegt vor: `finished(int, int, int, bool, int, dict)` — 6 Args.
Qt-Signale werden mit zu vielen Args unleserlich. Plus: bestehender Slot
`_on_qrz_bulk_finished` haette dann 6 Args, Tests muessten alle migrieren.

**V2-Empfehlung — sauberere Loesung:** zweites Signal `file_results_ready(dict)`,
emittiert NACH `finished`. Dann:
- `finished(ok, dup, fail, cancelled, total_processed)` bleibt unveraendert
- `file_results_ready(dict)` neu, mw_qso connectet auf separaten Slot
- Bestehende Tests bleiben kompatibel

Oder noch einfacher: kein Signal, sondern Property `worker.file_results`
(dict, threadsafe-final am Ende des `_run`-Loops gesetzt). mw_qso liest
sie im `_on_qrz_bulk_finished`-Slot.

**V2 finale Empfehlung:** Property `worker.file_results` (dict). Kein
zusaetzliches Signal. Spart Boilerplate, Tests einfacher.

---

## L4 — V1 §4.4 Title-Update: Race mit Window-Title-Aenderungen anderswo

`MainWindow.__init__` hat `self.setWindowTitle(f"SimpleFT8 — {settings.callsign}")`.
Das ist die EINZIGE Stelle wo Title gesetzt wird. Aber: was wenn z.B.
ein ander Plan-Feature in Zukunft den Title aendert?

**V2-Loesung:** Title-Update macht NICHT `setWindowTitle(neu)` mit
hartcodiertem Base-String. Stattdessen:
- `_qrz_title_suffix: str = ""` als Instanz-Attribut
- Neue Methode `_update_window_title()` die immer
  `f"SimpleFT8 — {self.settings.callsign}{self._qrz_title_suffix}"`
  setzt
- Worker-Progress-Slot setzt `self._qrz_title_suffix = f" — QRZ ↑ {c}/{t} ({p}%)"`
  und ruft `_update_window_title()` auf
- Worker-Finished setzt `self._qrz_title_suffix = ""` und ruft
  `_update_window_title()` auf

Damit ist Title-Logik zentralisiert, andere Features koennen das
gleiche Pattern nutzen.

---

## L5 — V1 §4.5 Statusbar-Widget: Layout zu vage

V1 sagt: „QLabel mit Text + QPushButton mit ✕". Aber Mike's Statusbar
ist schon voll mit `freq_display | filter | mode | DT | omni | RX:ANT`.
Noch ein Widget rechts ist OK (permanentWidget), aber:
- Wie viel Platz bekommt es?
- Wird es bei kleiner App-Breite verdraengt?

**V2-Konkret:**
```python
# In _init_statusbar:
self._qrz_status_widget = QWidget()
_lay = QHBoxLayout(self._qrz_status_widget)
_lay.setContentsMargins(0, 0, 0, 0)
_lay.setSpacing(4)
self._qrz_status_label = QLabel("QRZ ↑")
self._qrz_status_label.setStyleSheet(
    "color: #4488cc; font-family: Menlo; font-size: 11px;")
self._qrz_status_cancel_btn = QPushButton("✕")
self._qrz_status_cancel_btn.setFixedSize(18, 18)
self._qrz_status_cancel_btn.setStyleSheet(
    "QPushButton { background: rgba(180,30,30,0.4); color: #FFAAAA;"
    " border: 1px solid #533; border-radius: 3px; font-size: 10px;}"
    "QPushButton:hover { background: rgba(220,40,40,0.6); }")
_lay.addWidget(self._qrz_status_label)
_lay.addWidget(self._qrz_status_cancel_btn)
self._qrz_status_widget.hide()
self.statusBar().addPermanentWidget(self._qrz_status_widget)
```

Cancel-Connect ist tricky: Worker existiert nur waehrend Upload. Loesung:
beim Anzeigen `_qrz_status_cancel_btn.clicked.disconnect(); .connect(self._qrz_worker.cancel)`.
Oder einfacher: Slot `_on_qrz_status_cancel_clicked()` der wenn
`_qrz_worker is not None and active` cancel ruft.

V2-finale: feste Slot-Methode, kein dynamisches connect/disconnect.

---

## L6 — V1 §4.5 File-Move: Cancel-Pfad ungeklaert

V1 §5: „Pro File: wenn auch nur ein Record nicht bearbeitet wurde
(weil cancel vorher kam) → File bleibt." Aber wie wissen wir das?

Worker hat `_file_results: Dict[str, {ok, dup, fail}]`. Bei Cancel sind
einige Files noch unvollstaendig — wir muessen tracken **wie viele Records
pro File ueberhaupt drin sind** vs. wie viele bearbeitet.

**V2-Loesung:** Worker baut beim Init ein zweites Dict
`_file_record_count: Dict[str, int]` (wie viele Records pro File geplant).
File-Move-Bedingung wird:
```python
def _is_file_complete(file_path):
    expected = self._file_record_count[file_path]
    counts = self._file_results[file_path]
    processed = counts["ok"] + counts["dup"] + counts["fail"]
    return processed == expected and counts["fail"] == 0
```

Oder einfacher: als Property `worker.file_results` Dict bauen, und
File-Move-Helper in mw_qso pruefen.

V2 detailliert das in V3.

---

## L7 — V1 §4.6 `qso_log` Multi-Dir: bestehende Implementierung pruefen

`core/qso_log.py:QSOLog.load_directory(path)` lädt aktuell ein Verzeichnis.
V1 sagt: „zusaetzlich aufrufen mit `adif/hochgeladen/`-Pfad". Korrekt,
aber:
- `MainWindow._init_qso_log` hat schon zwei Aufrufe
  (`Path.cwd()` + `adif_import_path`).
- Pattern: `self.qso_log.load_directory(Path.cwd() / "adif")` ist die
  Standard-Quelle. NEU: zusaetzlich
  `self.qso_log.load_directory(Path.cwd() / "adif" / "hochgeladen")`.
- `bulk_import_directory` fuer LocatorDB analog.

**V2-Verifikation in V3:** `MainWindow._init_qso_log` Z.162-188 muss
genau diese Stellen ergaenzen. Kein Verhalten-Bruch falls
`adif/hochgeladen/` noch nicht existiert (`load_directory` macht
`Path.is_dir()`-Check intern? V3 verifiziert).

---

## L8 — V1 §4.7 Tests: zwei Tests fehlen

V1 listet 10 Tests. Fehlt:
- `test_cancel_during_bulk_partial_files_not_moved` — explizit den
  Edge-Case aus L6
- `test_logbook_widget_shows_records_from_hochgeladen_dir` — nicht nur
  load, sondern auch Display

**V2-Empfehlung:** auf 12 Tests aufstocken.

---

## L9 — V1 verpasst: bestehender QRZUploadDialog → komplett raus oder behalten?

V1 §3 AC-3: „QRZUploadDialog wird nicht mehr instanziert."
Aber V1 sagt nicht WAS damit passiert (Klasse loeschen oder behalten?).

**V2-Empfehlung:** **Klasse loeschen** in `ui/qrz_upload_dialogs.py`.
Plus dazugehoerige Tests:
- `test_progress_dialog_update_renders_correctly`
- `test_progress_dialog_finished_shows_close_button`
- `test_progress_dialog_cancelled_title_yellow`
- `test_progress_dialog_auto_close_timer_starts`

Diese 4 Tests werden geloescht (4 Tests weg). 12 neue dazu = Netto +8.
Erwartung: 872 → ~880 Tests.

Datei `ui/qrz_upload_dialogs.py` enthaelt dann nur noch `QRZConfirmDialog`
+ `_DLG_STYLE`. Saubere Loesung.

---

## L10 — V1 verpasst: Field-Test hat einen weiteren Aspekt — Mike funkt waehrend Upload

Mike's Quote 07.05. (vor v0.95.14):
> „aber wir können ja später ein seperates helper script schreiben"

und urspruenglich:
> „Fenster wo wir es auch sehen, Anzahl der QSO, wo wie weit wir stehen
> mit den Upload"

→ Mike will den Status SEHEN waehrend er funkt. Titelleiste alleine
reicht ihm? Oder will er auch die Counter „Neu/Dup/Fehler" sehen?

**V2-Empfehlung:** Titelleiste nur Progress (`X/Y P%`). Counter
„Neu/Dup/Fehler" gehen verloren. Mike kann sie am Ende per Statusbar-
Toast (5s) sehen, plus print-Log.

Alternative: Statusbar-Widget zeigt zusaetzlich `↑X ✓Y ✗Z` neben dem
Progress. Aber: Statusbar hat schon viele Infos. Mike-Frage R1: zu voll?

V2 finale Position: minimalistisch — Title nur Progress, Statusbar nur
`[QRZ ↑ X/Y P%] [✕]`. Counter werden beim Finish via Statusbar-Toast 10s
angezeigt: `"QRZ Upload fertig: 1234 neu, 17231 dup, 0 fail"`.

---

## L11 — V1 verpasst: was passiert mit dem Progress nach Cancel?

V1 zeigt nicht: nach User-Cancel-Klick was zeigt die Titelleiste?
- Sofort zurueck `SimpleFT8 — DA1MHH`?
- Oder bis cancel_event greift `SimpleFT8 — DA1MHH — QRZ wird abgebrochen ...`?

**V2-Empfehlung:** Statusbar-Widget zeigt sofort nach Cancel-Klick
„QRZ ↑ wird abgebrochen ..." (Cancel-Button wird disabled). Title bleibt
beim letzten Progress-Stand bis `finished` kommt (max 10s wegen
HTTP-Timeout). Dann reset Title + Toast „Upload abgebrochen bei X/Y".

---

## L13 — KRITISCH: Mike's Feldtest 07.05. 12:xx — Log-Datei PFLICHT

Mike's Beobachtung waehrend des laufenden v0.95.14-Bulks:
> „wir brauchen ein log ob die datennach qrz ok hochgeladen wurden oder
> nicht jetzt macht der beim hochladen nach Duplikate 12134 nur noch
> jede qso feler nacheinander"

Zwei Findings:

**FINDING 1 — Persistentes Log-File (Mike-Anforderung):**
Mike will pro QSO sehen ob OK/Dup/Fail + bei Fail die Reason. Aktuell
gibt's nur den Endcounter „X neu, Y dup, Z fail" — keine Detail-
Information. Bei Fehler-Burst kann Mike nicht analysieren WAS schief lief.

**V2-Loesung:** `~/.simpleft8/qrz_upload.log` (append-only, JSON-Lines):
```jsonl
{"ts": "2026-05-07T11:42:13Z", "call": "DA1ABC", "band": "40m", "mode": "FT8", "date": "20260507", "result": "OK"}
{"ts": "2026-05-07T11:42:14Z", "call": "F5XYZ", "band": "20m", "mode": "FT8", "date": "20260420", "result": "duplicate"}
{"ts": "2026-05-07T11:42:15Z", "call": "JA1AAA", "band": "40m", "mode": "FT8", "date": "20260507", "result": "fail", "reason": "Connection timeout"}
```

JSON-Lines (NDJSON) ist crash-safe (jede Zeile fuer sich, kein Bedarf
fuer atomic-write). Append per `open(path, "a")`.

Worker schreibt in `_run` nach jedem Result, NICHT erst am Ende. Mike
kann live `tail -f ~/.simpleft8/qrz_upload.log` machen.

**FINDING 2 — Rate-Limit-Detection (Burst-Fail):**
Mike's Beobachtung: nach 12134 Duplikaten kommen nur noch FAIL hintereinander.
Wahrscheinliche Ursachen:
- QRZ.com Rate-Limit (kein offizielles Limit dokumentiert, aber bei 12k+
  Calls in 1h denkbar)
- Session/Network-Problem (nach langem Upload)

**V2-Loesung:** Burst-Detection im Worker:
- `_consecutive_fails: int` Counter
- Bei `fail` inkrementieren, bei OK/dup auf 0 zuruecksetzen
- Wenn `_consecutive_fails >= MAX_CONSECUTIVE_FAILS` (z.B. 20) → Worker
  PAUSIERT 60 Sekunden (Rate-Limit-Cooldown), zeigt Status „QRZ pausiert
  60s wegen Fehler-Burst..."
- Nach Cooldown: Retry. Wenn weitere 20 fails → Worker `cancel`-flagged,
  `finished` mit `cancelled=True` und Reason im Log.

Threshold konservativ (20 statt z.B. 5) damit normale Einzelfehler nicht
zu Pausen fuehren.

**Statusbar-Anzeige bei Pause:** `QRZ ↑ pausiert 45s ...` (Countdown).
Cancel-Button bleibt nutzbar — Mike kann jederzeit haendisch stoppen.

---

## L14 — File-Move-Logik mit FAIL-Burst zusammenbringen

Mike's Symptom: 12134 Dups + danach nur Fails. Wenn Worker bei fail-burst
abbricht (L13), dann sind:
- Files wo alle Records OK/Dup waren → Move nach `hochgeladen/` ✅
- Files wo einige Records FAIL waren → bleiben in `adif/` ✅
- Files die noch nicht angefangen wurden → bleiben in `adif/` ✅

→ V1's File-Move-Logik passt genau. Beim naechsten Bulk werden die
verbliebenen Files nochmal versucht. QRZ-Cache ist serverseitig idempotent
(Duplikate werden erkannt).

**V2-Klarstellung:** File-Move-Helper in `_handle_qrz_file_results`:
```python
def _handle_qrz_file_results(file_results: dict):
    target_dir = adif_dir / "hochgeladen"
    target_dir.mkdir(exist_ok=True)
    moved = 0
    for src_path, counts in file_results.items():
        if counts["fail"] == 0 and counts["expected"] == counts["processed"]:
            dest = target_dir / Path(src_path).name
            try:
                shutil.move(src_path, dest)
                moved += 1
            except OSError as e:
                print(f"[QRZ] File-Move {src_path} fehlgeschlagen: {e}")
    return moved
```

`expected` muss vom Worker mitkommen (siehe L6).

---

## L12 — Compact-Strategie

V3 muss compact-fest sein, alle Diffs konkret. Memory-File neu:
`project_p1_qrz_upload_ui_2_in_progress.md` mit:
- Trigger-Phrase „weiter mit P1.QRZ-UPLOAD-UI-2"
- Stand: V1+V2+R1+V3 fertig
- Naechste Schritte (Code-Phase autonom)
- Field-Test-Pflicht-Liste
- Lessons-Learned-Vorschlag

---

## Pruefauftraege fuer R1

0. **L13 Log-File Format:** JSON-Lines append-only in `~/.simpleft8/qrz_upload.log`
   (V2-Vorschlag) — KISS oder Overengineering? Alternative: einfaches
   CSV. Mike's Anforderung „log ob ... ok hochgeladen wurden" — sollte
   per UI auch zugaenglich sein? Oder nur Datei?
0a. **L13 Rate-Limit-Detection:** `MAX_CONSECUTIVE_FAILS = 20` + 60s Cooldown,
   bei zweitem Burst Cancel — vernuenftig oder zu rigide? Mike's Beobachtung
   12134 Dups + Fail-Burst → wahrscheinlich QRZ-Server (kein App-Bug).
   Soll Cooldown laenger sein (5 Min)? Oder soll es einen User-Confirm-
   Dialog geben „QRZ scheint Probleme zu haben — pausieren oder
   abbrechen?"

1. **Signal-vs-Property fuer file_results:** Signal `file_results_ready(dict)`
   ODER Property `worker.file_results`? V2 vorschlaegt Property.
2. **Title-Suffix-Pattern:** zentrale `_update_window_title()`-Methode
   (V2-Vorschlag) — Overengineering oder elegant?
3. **Statusbar-Widget Cancel-Slot:** feste Methode
   `_on_qrz_status_cancel_clicked()` mit `if self._qrz_worker:` Check
   (V2-Vorschlag) ODER dynamisches connect/disconnect?
4. **Counter-Anzeige waehrend Upload:** nur Progress in Title (V2-Vorschlag),
   Counter nur am Ende per Toast — ODER auch waehrend Upload zusaetzlich
   in Statusbar `↑X ✓Y ✗Z`?
5. **`adif/hochgeladen/`-Verzeichnis:** auto-erstellt bei File-Move
   (V2-Vorschlag) ODER Mike muss vorab anlegen?
6. **Source-File-Pfad:** `str(path.resolve())` (absolut, V2-Vorschlag)
   ODER relativ zu CWD?
7. **Cancel-Pfad File-Move:** Edge-Case wenn ein File teilweise upgeloaded —
   File bleibt (V2-Vorschlag). R1-Pruefung: was wenn der eine Record im
   File OK war? File bleibt → naechster Bulk versucht ihn nochmal,
   QRZ-Server filtert als duplicate → rein-OK Result → File wird dann
   bewegt. Korrekt?
8. **`parse_all_adif_files` rekursiv vs. flat:** muss flat bleiben (L2),
   sonst File-Move bricht. R1-Verifikation: aktueller Code ist `glob("*.adi")`?
9. **QRZUploadDialog vs. QRZConfirmDialog:** Klasse + Tests loeschen
   (V2-Vorschlag) — sauberer Cleanup oder Risiko fuer breaking changes?
10. **Migration `_DATETIME` Field:** wird in logbook_widget.py zur
    Anzeige gebaut, nicht in parse. Wird `_source_file` an gleicher Stelle
    gebaut oder im Parser? V2: im Parser (eleganter, einmal fuer alle
    Konsumenten).

---

## Zusammenfassung der V2-Korrekturen fuer V3

1. **`_source_file` als interne `_`-Field im Parser** (nicht in Widget) (L1)
2. **`parse_all_adif_files` flat halten, zwei Aufrufe** in load_adif (L2)
3. **`worker.file_results` Property** statt 6-Arg-Signal-Erweiterung (L3)
4. **Zentrale `_update_window_title()`-Methode** mit `_qrz_title_suffix` (L4)
5. **Konkretes Statusbar-Widget Layout** (QHBoxLayout mit Label + ✕-Btn) (L5)
6. **Worker-`_file_record_count` Dict** fuer Cancel-Edge-Case (L6)
7. **`qso_log.load_directory` zweiter Aufruf** in `_init_qso_log` (L7)
8. **Tests von 10 auf 12 erweitern** (L8) → mit L13 nochmal +3 = 15
9. **`QRZUploadDialog` Klasse + 4 Tests loeschen** (L9, Netto +11 Tests)
10. **Counter nicht im Title** — nur am Ende per Statusbar-Toast 10s (L10)
11. **Cancel-Pfad: Title bleibt bis finished, dann reset + Toast** (L11)
12. **Compact-Strategie + Memory-File** (L12)
13. **NEU L13 — JSON-Lines Log-Datei + Rate-Limit-Detection** (Mike-
    Anforderung 07.05. mid-V2: 12134 Dups + Fail-Burst). Worker schreibt
    pro Result Line, Burst-Detection mit Cooldown.
14. **NEU L14 — File-Move-Helper konkretisiert** mit `expected` vs.
    `processed` Vergleich + try/except OSError.

---

**Workflow-Status:** V2 fertig. Weiter mit R1 (DeepSeek-Reasoner).
