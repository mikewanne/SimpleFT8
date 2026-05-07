# P1.QRZ-UPLOAD-UI-2 V1 — Titelleiste + File-Move + Cleanup

**Stand:** 2026-05-07.
**Workflow:** **V1 (diese Datei)** → V2 (Self-Review) → R1 (DeepSeek) → V3 → Compact → Code.
**Vorgaenger:** P1.QRZ-UPLOAD-UI v0.95.14 (Confirm + Progress-Dialog +
ThreadPool-Worker + Single-Instance 3-fach + KP-1/2/3 + Final-R1-Cancel-Bug-Fix).
**Mike-Field-Test 07.05.2026 nach v0.95.14:**

> „okay das upload fenster liegt jetzt immer vor der app können wir nicht den
> uploadstatus oben in der titelleiste von simpleft8 unterbringen und wie
> merken wir uns welche schon hochgeladen wurden. können wir hochgeladene
> dateien nicht verschieben in einen verzeichniss /hochgeladen."

---

## 1. Aktueller Zustand (v0.95.14, gerade pushready)

### Symptome aus Mike's Field-Test

1. **Progress-Dialog ist `WindowStaysOnTopHint`** → liegt staendig vor der
   App. Mike kann nicht entspannt weiter funken — der Dialog ist visuell
   im Weg, auch wenn er non-modal ist.
2. **Keine Persistierung welche QSOs schon hochgeladen wurden** → bei
   jedem Bulk werden alle 18.443 Files gesendet, QRZ.com filtert
   serverseitig (`duplicate`-Reason). Funktioniert, ist aber:
   - **Ineffizient:** 18.443 HTTP-Calls statt z.B. 5 neuer
   - **Trotzdem 1h Upload-Zeit** — keine Verbesserung gegenueber v0.95.14
   - **Lange Wartezeit** auch fuer Mike der nur „die letzten 50 hochladen" will

### Code-Pfad (`ui/mw_qso.py:418-...` `_on_qrz_upload`)

Aktueller Worker liest `self.qso_panel.logbook._all_records` — alle 18.443.
Worker callt `client.upload_qso_from_dict(rec)` pro Record. QRZ-Response:
- `RESULT=OK` → `ok += 1`
- `REASON=duplicate` → `dup += 1`
- sonst → `fail += 1`

Kein Tracking welche Records aus welcher Datei kamen. Kein File-Move.

---

## 2. Mike's Vision (klar formuliert)

### A — Status in Titelleiste statt Dialog

> „den uploadstatus oben in der titelleiste von simpleft8 unterbringen"

- Waehrend Upload: `SimpleFT8 — DA1MHH — QRZ ↑ 4123/18443 (22%)`
- Nach Upload: zurueck zu `SimpleFT8 — DA1MHH`
- Progress-Dialog (`QRZUploadDialog`) komplett raus.
- **Confirm-Dialog (`QRZConfirmDialog`) bleibt** — der ist nur 1× am Start,
  blockt nicht die App, ist Mike's UX-OK (Bestaetigung vor 18443 HTTP-Calls).

### B — File-Move nach Upload

> „können wir hochgeladene dateien nicht verschieben in einen verzeichniss
> /hochgeladen"

- Pro Record merken aus welcher Datei er stammt (`record["_source_file"]`
  setzen in `parse_all_adif_files()` — schon teilweise da via `_DATETIME`
  und Co., aber `_source_file` muss neu).
- Worker aggregiert pro File: Set von OK/Dup/Fail.
- **Wenn FAIL-Set leer** → File von `adif/YYYY-MM-DD.adi` nach
  `adif/hochgeladen/YYYY-MM-DD.adi` verschieben (`shutil.move`, atomic
  innerhalb gleichem Filesystem).
- Bei FAIL: Datei bleibt → naechster Bulk versucht's wieder.
- Bei Cancel: nur die Files verschieben deren Records vor Cancel alle
  abgehakt waren; offene Records → File bleibt.

### C — Cancel-UI

> Status in Titelleiste — wo ist Cancel-Button?

Empfehlung:
- **Inline-Cancel-Widget rechts in der Statusbar** waehrend Upload sichtbar:
  `[QRZ ↑] [✕]`. Klein, klickbar, blockiert nicht.
- Nach Upload (oder Cancel-Klick): Widget unsichtbar.

---

## 3. Akzeptanzkriterien

1. **AC-1 Titelleiste:** waehrend Upload zeigt `setWindowTitle()` zusaetzlichen
   Suffix `— QRZ ↑ X/Y (P%)`. Update alle 10 QSOs (synchron mit Worker
   `progress`-Signal).
2. **AC-2 Statusbar-Cancel-Widget:** `_qrz_status_widget` (QLabel + Button)
   wird waehrend Upload als `permanentWidget` rechts angezeigt. Klick auf
   `[✕]` triggert `_qrz_worker.cancel()`.
3. **AC-3 Kein Progress-Dialog mehr:** `QRZUploadDialog` wird nicht mehr
   instanziert. `ui/qrz_upload_dialogs.py` enthaelt nur noch
   `QRZConfirmDialog`.
4. **AC-4 File-Tracking:** `record["_source_file"]` wird in
   `log/adif.py:parse_all_adif_files()` gesetzt (relativer Pfad zur
   ADIF-Datei).
5. **AC-5 File-Move bei Fertig:** im Slot `_on_qrz_bulk_finished` werden
   Files verschoben deren Records ALLE OK oder Duplicate sind. Atomic
   `shutil.move`. Verzeichnis `adif/hochgeladen/` wird bei Bedarf erstellt.
6. **AC-6 Logbuch zeigt beide Verzeichnisse:** `LogbookWidget.load_adif()`
   liest aus `adif/` UND `adif/hochgeladen/` (damit Mike alle QSOs sieht
   inkl. Worked-Before-Statistik). `qso_log.QSOLog.load_directory()`
   ebenfalls.
7. **AC-7 Bulk-Upload nimmt NUR `adif/`-Records:** Worker bekommt nur
   Records mit `_source_file` aus `adif/` (NICHT `adif/hochgeladen/`).
   Filter: `[r for r in _all_records if "hochgeladen" not in r["_source_file"]]`.
8. **AC-8 Logbuch-Refresh nach Move:** nach erfolgreichem File-Move
   `qso_panel.logbook.refresh()` aufrufen — Records aus `hochgeladen/`
   Files behalten ihre Records, kein UI-Bruch.
9. **AC-9 Tests gruen:** alle bestehenden Tests + neue fuer File-Move +
   Title-Update + Statusbar-Widget. Erwartung: 872 → ~882 gruen.
10. **AC-10 Field-Test post-Kur:** Mike testet 1) Title-Update, 2) Cancel
    via Statusbar, 3) File-Move geprueft per `ls adif/hochgeladen/`,
    4) zweiter Bulk lädt nur neue QSOs (idR. 0 da QRZ schon alle hat).

---

## 4. Betroffene Module/Dateien

### 4.1 `log/adif.py` — `_source_file` ergaenzen

`parse_all_adif_files(adif_dir)` muss pro Record das Source-File mit-
geben. Aktuell wird nur der Inhalt geparst.

Vorschlag: in der Schleife pro Datei `record["_source_file"] = str(path)`
setzen (absoluter Pfad oder relativ zu CWD).

Bei `delete_qso()` zusaetzlich auf Source-File-Match pruefen falls schon
vorhanden — sonst keine Aenderung.

### 4.2 `ui/logbook_widget.py` — Multi-Directory-Load

`load_adif(directory)` liest aktuell nur EIN Verzeichnis. Erweitern:
- Default: lese sowohl `adif/` als auch `adif/hochgeladen/`
- Records aus `hochgeladen/` bekommen visuelle Markierung (z.B. dezenter
  grauer Pfeil ↑ oder dimmer-color)?

V2/R1-Frage: brauchen wir das visuell? Oder nur `_source_file`-Tracking
intern?

### 4.3 `core/qrz_upload_worker.py` — File-Tracking

Worker muss pro Record die `_source_file` rausziehen und beim Senden
das Result pro File aggregieren.

Neue Datenstruktur: `_file_results: Dict[str, Dict[str, int]]`
- Key: source_file Pfad
- Value: `{"ok": N, "dup": N, "fail": N}`

Am Ende: `finished` Signal um Liste der File-Results erweitern, oder
neuer `Signal(dict)` `file_results_ready`.

V2/R1-Frage: Signal-Erweiterung oder separater Slot?

### 4.4 `ui/mw_qso.py` — Title-Update + Statusbar-Widget

Neue Methoden:
- `_on_qrz_progress_titlebar(current, total, ok, dup, fail)`:
  Title aktualisieren auf `f"{base} — QRZ ↑ {current}/{total} ({pct}%)"`
- `_show_qrz_status_widget(visible: bool)`: Statusbar-Widget toggle.
- `_handle_qrz_file_results(file_results: dict)`: pro File pruefen ob
  alle OK/Dup → `shutil.move` nach `adif/hochgeladen/`.

`_on_qrz_bulk_finished` ruft `_handle_qrz_file_results` UND resetet Title
auf Ursprung.

`_on_qrz_upload`:
- `QRZUploadDialog` Instanziierung entfernen
- Worker erstellen, progress an `_on_qrz_progress_titlebar` connecten
- Statusbar-Widget zeigen
- Title-Original speichern

### 4.5 `ui/main_window.py` — Statusbar-Widget Init

Im `_init_statusbar`: `_qrz_status_widget` als `permanentWidget` mit
`hide()` initial. Layout: `[QRZ ↑ ... ] [✕]`. Cancel-Button connected an
`_qrz_worker.cancel()` (bzw. None-Check, Worker existiert nur waehrend Upload).

### 4.6 `core/qso_log.py` — Multi-Directory-Load (V2-Frage)

Worked-Before-Statistik soll auch QSOs aus `hochgeladen/` enthalten,
sonst denkt Mike er hat eine Station noch nie gearbeitet obwohl sie schon
in einem hochgeladenen File ist.

Loesung: `qso_log.load_directory(adif_path)` zusaetzlich aufrufen mit
`adif/hochgeladen/`-Pfad.

### 4.7 `tests/test_p1_qrz_upload_ui_2.py` (NEU)

- `test_record_has_source_file_after_parse`
- `test_worker_aggregates_results_per_file`
- `test_file_move_when_all_ok_or_dup`
- `test_file_not_moved_when_any_fail`
- `test_titlebar_updates_during_progress`
- `test_titlebar_resets_after_finished`
- `test_statusbar_widget_visible_during_upload`
- `test_statusbar_widget_hidden_after_finished`
- `test_logbook_loads_both_dirs`
- `test_bulk_skips_records_from_hochgeladen_dir`

→ **10 neue Tests.**

---

## 5. Randbedingungen / Kritische Punkte

- **Atomicity File-Move:** `shutil.move` ist atomisch innerhalb gleichem
  Filesystem (rename). Bei `os.replace` 100% atomar. Defensive: vorher
  Zielverzeichnis erstellen, bei Fehler Datei stehen lassen.
- **Race Condition:** Was wenn Mike waehrend Bulk eine neue Datei in
  `adif/` schreibt (neues QSO via Auto-Upload)? Worker hat bereits
  `_all_records` aus aktiver Bulk-Snapshot. Neue Datei wird beim naechsten
  Bulk genommen. Auto-Upload-Skip (KP-1) verhindert paralleles Schreiben.
- **Logbook-View nach Move:** wenn Datei verschoben, Records sind „weg"
  aus `adif/`-Liste, aber Logbook lädt aus `adif/` UND `adif/hochgeladen/`
  → Records bleiben sichtbar. `refresh()` reicht.
- **Initial-Migration:** beim ersten Bulk wandern fast alle 18443 Records
  nach `hochgeladen/` (alle waren ja Duplikate). Mike's Logbook zeigt sie
  weiter, aber `adif/` ist fast leer. OK fuer Mike?
- **Source-File-Pfad als String:** absolute oder relativ? Vorschlag:
  absolute via `Path.resolve()` damit File-Move-Ziel deterministisch ist.
- **Cancel waehrend Bulk:** File-Move nur fuer voll-bearbeitete Files.
  Pro File: wenn auch nur ein Record nicht bearbeitet wurde (weil cancel
  vorher kam) → File bleibt. V2: explizit testen.

---

## 6. Nicht im Scope (P2 oder spaeter)

- **P2 — `tools/adif_archive.py`** Standalone-Script: alle Tagesdateien
  in `adif/hochgeladen/` zu Jahresarchiven `archiv/2024.adi`,
  `archiv/2025.adi` konsolidieren. Wird SEPARAT entwickelt nachdem
  P1.QRZ-UPLOAD-UI-2 durch ist (Mike-Plan 07.05.).
- **Visuelle Markierung im Logbook fuer „hochgeladen"** — V2-Frage.
- **Resume-Bulk** (nur neue Records) — aktuell nicht noetig: Worker geht
  alle records aus `adif/` durch, `hochgeladen/` ausgenommen → automatisch
  nur neue.
- **QRZ-Status-Anfrage** vor Bulk (welche QSOs schon im QRZ-Log) — nicht
  noetig, File-Move loest das.

---

## 7. Offene Fragen fuer V2/R1

1. **Title-Update-Frequenz:** alle 10 QSOs (gleich Worker-`PROGRESS_INTERVAL`)
   oder seltener? V1: alle 10 Reicht (Title-Flicker minimal).
2. **Statusbar-Widget Layout:** `QLabel` mit Text + `QPushButton` mit
   `[✕]`. Oder kompakter inline `QLabel` `QRZ ↑ 4123/18443  ✕` mit
   Click-Detection auf Label?
3. **`_source_file` Storage:** absoluter Pfad oder relativ zu CWD?
4. **File-Move-Fehler:** wenn Disk voll oder Permission denied → was
   tun? Statusbar-Toast, Datei stehen lassen. V2 spezifizieren.
5. **`adif/hochgeladen/` als auto-erstellt** oder muss Mike manuell?
   V1 Vorschlag: auto via `Path.mkdir(exist_ok=True)`.
6. **Logbook visuelle Markierung** fuer hochgeladene Records noetig oder
   nicht? V2-Mike-Frage.
7. **Worker-Signal-Erweiterung:** `finished(ok, dup, fail, cancelled,
   total_processed, file_results)` (6 Args) oder neues Signal
   `file_results_ready(dict)`? V1 Vorschlag: Erweiterung um `file_results`
   Dict — kein zweites Signal.
8. **Migration:** wenn schon `adif/hochgeladen/` existiert (z.B. von
   manueller Verschiebung), wird das mitgeladen? V1: ja.
9. **Test-Strategie:** wie testen wir File-Move ohne echtes Filesystem?
   `tmpdir`-Fixture in pytest. V2 detaillieren.

---

## 8. Compact-Strategie

V1 ist nur Diagnose + Akzeptanzkriterien + offene Fragen. V2 wird
Self-Review mit konkreten Lessons. R1 reviewt V2 + V1. V3 ist Compact-
fest mit allen Diffs:
- `log/adif.py` Diff (parse_all_adif_files)
- `ui/logbook_widget.py` Diff (Multi-Dir-Load)
- `core/qrz_upload_worker.py` Diff (File-Tracking + Signal-Erweiterung)
- `ui/mw_qso.py` Diff (Title + Statusbar + File-Move)
- `ui/main_window.py` Diff (Statusbar-Widget Init)
- `core/qso_log.py` Diff (Multi-Dir-Load)
- `tests/test_p1_qrz_upload_ui_2.py` (NEU)
- Eventuell `ui/qrz_upload_dialogs.py` (QRZUploadDialog komplett raus)

---

**Workflow-Status:** V1 fertig. Weiter mit V2 (Self-Review).
