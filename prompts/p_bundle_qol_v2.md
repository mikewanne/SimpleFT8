# P43+P20+P18 — Quality-of-Life-Bundle (V2)

> **Pflicht-Kopf für DeepSeek-R1-Review:**
>
> Du bist Senior Python-Entwickler spezialisiert auf Amateurfunk-Software
> und PySide6 (`Signal` statt `pyqtSignal`, `Slot` statt `pyqtSlot`). Das
> Projekt ist ein Hobby-Funker-Tool für einen einzelnen Operator —
> NICHT Multi-Tenant.
>
> Deine einzige Aufgabe: diesen Prompt kritisieren — NICHT das Problem
> lösen. Strukturierte Liste: Lücken, Unklarheiten, Widersprüche,
> Verbesserungen.
>
> KRITISCHE REGELN:
> 1. **SCOPE-RESPEKT:** Was explizit als out-of-scope markiert ist NICHT
>    als Finding melden.
> 2. **KISS VOR DEFENSIV:** Komplexität nur wenn Wahrscheinlichkeit > 50 %.
> 3. **PROJEKT-BEZUG:** Jedes Finding am konkreten Use-Case messen.
> 4. **FORMAT:** Tabelle `Schwere | Finding | Datei:Zeile | Empfehlung`.
>    Severity: Bug (rot) / Risiko (orange) / Verbesserung (gelb) /
>    Hinweis (grau).
>
> Overengineering ist selbst ein Fehler den du benennen sollst.

---

## Ziel

Drei kleine, voneinander unabhängige Hygiene-Fixes als gemeinsames
Bundle. Alle hardware-frei, kein Field-Test nötig.

1. **P43 setproctitle** — macOS Activity Monitor zeigt
   `SimpleFT8 v0.97.12` statt nur `Python`. Bei der P30-Diagnose am
   12.05. konnte Mike nicht zwischen SimpleFT8 und Qwen3-TTS
   unterscheiden (beide gleicher Python-Name).
2. **P20 Log-Rotation** — `~/.simpleft8/simpleft8.log` wächst
   append-only ins MB-Bereich. Eine Datei pro UTC-Tag,
   `simpleft8.log`-Symlink zeigt auf heute, Dateien älter als 7 Tage
   werden gelöscht. Bestehende `simpleft8.log` (Mike's Historie)
   wird einmalig archiviert, nicht gelöscht.
3. **P18 DT-Korr-Print-Spam** — Beim App-Start steht 3× identisch
   `[DT-Korr] FT8_20m: Gespeicherter Wert +0.650s geladen`. Gleicher
   Output nur 1× pro Wert ausgeben.

## Hintergrund (Code-Verifikation 13.05.)

- **P43:** `setproctitle` ist **nicht** installiert
  (`./venv/bin/python3 -c "import setproctitle"` → `ModuleNotFoundError`).
  Wird neue Dependency in `requirements.txt`. Stelle in `main.py`
  direkt nach `APP_VERSION = ...` (Z.16) und vor Logging-Init (Z.29).
- **P20:** Aktueller Pfad `main.py:32`
  `_log_file = open(_LOG_DIR / "simpleft8.log", "a", buffering=1)`.
  Es gibt **zwei** Stellen die so öffnen:
  1. `main.py:32` (App-Start)
  2. `tools/remote/start_simpleft8_nokill.py:24` (Fernwartungs-Start
     vom Ferienhaus)
  Beide Pfade müssen die gleiche Rotation-Logik nutzen — sonst springt
  der eine Start auf neue Datei und der andere überschreibt die alte
  Logik. **Helper-Funktion in einem gemeinsamen Modul** (z.B.
  `core/log_setup.py` NEU) ist die saubere Lösung, **nicht
  Copy-Paste**.
- **P18:** `core/ntp_time.py:119` und `:139` printen identisch
  `[DT-Korr] {key}: Gespeicherter Wert {saved_val:+.3f}s geladen`.
  Wer ruft beim App-Start `set_mode`/`set_band` 3×?
  - `ui/mw_radio.py:167` (in Start-Radio-Pfad)
  - `ui/mw_radio.py:322` (in `_on_mode_changed`)
  - `ui/mw_radio.py:458` (in `_on_band_changed`)
  Beim App-Start triggern alle drei. Aufrufer-Konsolidierung wäre
  riskanter Architektur-Eingriff (set_mode/set_band haben jeweils
  Seiteneffekte) — daher nur **Print-Dedup**, keine Logik-Änderung.

## Akzeptanzkriterien

**AK1 — P43 setproctitle.**

- `requirements.txt` ergänzt um `setproctitle` (Version-Pin nicht
  zwingend — KISS, neueste stabile).
- `main.py` direkt nach Z.16 (`APP_VERSION = "0.97.11"`) und vor Z.18
  (Single-Instance-Lock-Block) einfügen:
  ```python
  # ── P43: Activity Monitor zeigt Prozess-Namen statt nur "Python" ──
  try:
      import setproctitle
      setproctitle.setproctitle(f"SimpleFT8 v{APP_VERSION}")
  except ImportError:
      pass  # setproctitle ist optional — App laeuft auch ohne
  ```
- `tools/remote/start_simpleft8_nokill.py` analog am Anfang ergänzt
  (vor Logging-Init).
- Effekt: `ps -axc -o pid,command | grep -i simpleft8` zeigt
  `SimpleFT8 v0.97.12`. Activity Monitor zeigt das gleiche.

**AK2 — P20 Log-Rotation.**

- Neue Datei `core/log_setup.py` mit 3 Funktionen:
  1. `dated_log_filename(date: datetime | None = None) -> Path` —
     liefert `~/.simpleft8/simpleft8-YYYY-MM-DD.log` für UTC-Datum.
     None = `datetime.utcnow()`.
  2. `cleanup_old_main_logs(keep_days: int = 7) -> int` — löscht
     `simpleft8-*.log`-Dateien älter als `keep_days`. Glob-Muster
     `simpleft8-YYYY-MM-DD.log` (KEIN `simpleft8.log` Symlink trifft
     das Muster nicht), `try/except (ValueError, OSError): continue`
     für Robustheit (analog `core/debug_log.py:cleanup_old_files`).
     Returns Anzahl gelöschter Dateien.
  3. `setup_main_log(archive_existing: bool = True) -> tuple[Path, IO]`
     — Eintritts-API: ruft Cleanup auf, ermittelt heutigen
     datierten Pfad, archiviert vorhandene `simpleft8.log` falls
     **regulär e Datei (nicht Symlink)** → umbenennen in
     `simpleft8-pre-rotation-YYYY-MM-DD.log` (heutiges Datum als
     Archiv-Marker). Anschließend Symlink `simpleft8.log` →
     datierter Pfad (atomar via `tmp_symlink + os.replace`). Öffnet
     datierten Pfad in append-mode, returns `(path, file_handle)`.
- `main.py` Z.29-32 wird zu:
  ```python
  # ── File Logging mit Tages-Rotation (P20) ─────────────────────
  from core.log_setup import setup_main_log
  _log_path, _log_file = setup_main_log()
  ```
- `tools/remote/start_simpleft8_nokill.py` Z.22-24 analog umgebaut.
- Migration für Mike's bestehende `simpleft8.log` (Historie über
  Wochen): einmalig in `simpleft8-pre-rotation-YYYY-MM-DD.log`
  umbenannt — kein Datenverlust. Nach 7 Tagen löscht Cleanup das
  Archiv-File mit (akzeptiert, Mike kann es vorher manuell sichern
  wenn er Daten von früher 7 Tage zurück braucht).
- Datum-Roll-over zur Laufzeit: **bewusst nicht implementiert** (Mike
  startet täglich neu, KISS für Hobby-Tool).

**AK3 — P18 DT-Korr-Print-Spam.**

- In `core/ntp_time.py` Modul-Level (nach Z.53 bei den Zustands-Vars)
  neu:
  ```python
  _last_logged_load: tuple | None = None  # (key, saved_val, was_loaded)
  ```
- In `set_mode` (Z.117-121) und `set_band` (Z.137-141): Vor jedem
  print prüfen `if (key, saved_val, saved_val != 0.0) ==
  _last_logged_load`. Wenn ja → skip print. Wenn nein → print +
  `_last_logged_load = (key, saved_val, saved_val != 0.0)`.
- „Kein gespeicherter Wert"-Pfad wird gleich behandelt (auch dedupliziert).
- Wert-Update-Sicht: Wenn die DT-Korrektur sich später real ändert
  (Konvergenz), wird `_correction` per `_save_current()` gespeichert
  und beim nächsten set_mode/set_band geladen → neuer `saved_val` →
  Cache-Mismatch → print erneut. Sichtbar bleibt also alles
  Inhaltliche.

**AK4 — Bestehende Tests bleiben grün.**

- `tests/test_debug_log.py` betrifft `debug_*.log`-Pattern, nicht
  `simpleft8-*.log` — bleibt unangetastet.
- `tests/test_modules.py:1257` `test_dt_save_load_per_mode_band`
  verwendet `_save_current()`/`_load_for_current_key()` direkt ohne
  über `set_mode`/`set_band` zu gehen → kein print, kein
  Dedup-Cache-Konflikt. Bleibt grün.

**AK5 — Neue Tests (`tests/test_p_bundle_qol.py`).**

- **T1 — `test_setproctitle_safe_when_missing`:** Source-Check —
  `main.py` enthält `try:\n    import setproctitle` + `except
  ImportError:` Pattern. (Pragmatischer Test analog
  P47 T5-Pattern — Mock-Test wäre fragil.)
- **T2 — `test_dated_log_filename_format`:** Aufruf
  `dated_log_filename(datetime(2026, 5, 13))` liefert Pfad endend auf
  `simpleft8-2026-05-13.log`.
- **T3 — `test_cleanup_old_main_logs_keeps_recent`:** tmp-Dir mit 3
  Dateien (vorgestern, vor 5 Tagen, vor 30 Tagen + 1 Symlink) →
  Cleanup mit `keep_days=7` löscht 1 (30 Tage), behält 2 + Symlink
  intakt.
- **T4 — `test_setup_main_log_archives_existing_file`:** tmp-Dir mit
  vorhandener regulärer `simpleft8.log` → `setup_main_log` benennt
  sie um in `simpleft8-pre-rotation-YYYY-MM-DD.log`, Symlink zeigt
  auf heutige datierte Datei.
- **T5 — `test_setup_main_log_replaces_existing_symlink`:** tmp-Dir
  mit Symlink `simpleft8.log` → `simpleft8-2026-05-10.log` (alte
  Datei, älter als heute) → `setup_main_log` ersetzt Symlink atomar
  auf heutigen Pfad. Alte datierte Datei bleibt unangetastet.
- **T6 — `test_dt_dedup_skips_repeat`:** Reset `_last_logged_load =
  None`, dann 2× `set_mode("FT8", "20m")` mit gleichem gespeicherten
  Wert → `capsys` capturet nur 1× DT-Korr-print.
- **T7 — `test_dt_dedup_logs_on_change`:** Reset, dann
  `set_mode("FT8", "20m")` + `set_mode("FT4", "40m")` → 2× print
  (Cache-Mismatch).

Erwartung: **1167 → 1174** (+7 Bundle A).

**AK6 — Kein Architektur-Eingriff.** Keine Veränderung an
Decoder/Encoder/Diversity/QSO-State-Machine/Radio-Pfad/Statistik.
Reine Diagnose-/Wartungs-UX.

## Betroffene Module/Dateien

| Datei | Funktion / Block | Was |
|---|---|---|
| `requirements.txt` | (Top-Level) | `setproctitle` als neue Dependency |
| `main.py` | nach `APP_VERSION` (Z.16) | setproctitle-Init |
| `main.py` | Z.29-32 (Log-Init-Block) | `setup_main_log()`-Aufruf |
| `tools/remote/start_simpleft8_nokill.py` | Z.18-24 | analog setproctitle + setup_main_log |
| `core/log_setup.py` | NEU | 3 Funktionen (dated_log_filename, cleanup_old_main_logs, setup_main_log) |
| `core/ntp_time.py` | Z.53 Zustands-Vars | `_last_logged_load` neu |
| `core/ntp_time.py` | Z.117-121 (set_mode) | Dedup-Check |
| `core/ntp_time.py` | Z.137-141 (set_band) | Dedup-Check |
| `tests/test_p_bundle_qol.py` | NEU | T1-T7 |

## Randbedingungen

- **KISS:** Keine Custom-Logger-Klasse, keine Klassen-Hierarchie. 3
  freie Funktionen in `core/log_setup.py`. setproctitle =
  try/except 3 Zeilen. DT-Dedup = 1 Modul-Var + 2× if-Check.
- **Optional-Dependency setproctitle:** Try/Except-Import — App läuft
  auch ohne. `requirements.txt` listet es als Soll-Install.
- **Hardware-Pflicht ANT1=TX bleibt unberührt.**
- **Hobby-Tool-Philosophie:** Mike als Single-User, keine
  Multi-Profile-Logs, keine Komprimierung.
- **Backward-Kompat:** Mike's vorhandene `simpleft8.log` (echte Datei)
  wird einmalig archiviert (umbenannt), nicht gelöscht. Nach 7 Tagen
  fällt das Archiv unter Cleanup — Mike kann es vorher manuell
  sichern wenn er ältere Daten braucht.
- **Atomic-Symlink-Update:** `tmp_symlink.symlink_to(target);
  os.replace(tmp_symlink, final_symlink)` — atomar auf POSIX. Auf
  macOS funktioniert das (validiert in vielen Python-Tools, kein
  bekanntes Issue).
- **UTC-Datum** für Filename und Cleanup (konsistent mit
  `core/debug_log.py`).
- **Cleanup fail-silent:** Bei `OSError` (Permission, FileNotFound,
  etc.) wird die einzelne Datei übersprungen, nicht der App-Start
  abgebrochen.

## Nicht im Scope

- **Strukturiertes Debug-Log** (P21) — separater Workflow.
- **Konsolidierung der 3× set_mode/set_band-Calls** beim App-Start —
  Architektur-Eingriff, Mike sagt „funktional egal".
- **Rotation während laufender App** — kein Datum-Roll-Detection zur
  Laufzeit.
- **Komprimierung** alter Logs (.gz o.ä.).
- **Encoder/Decoder/Diversity/Radio-Pfade** bleiben unangetastet.
- **Keine Migration alter `debug_*.log`** (separate Logik in
  `core/debug_log.py`).
- **Keine Veränderung der Print-Statements im DT-Modul** außer
  Dedup-Check — Wortlaut, Format und Häufigkeit bei
  Wertänderungen bleiben.

## Geplante Commit-Reihenfolge (atomar)

1. **C1** `requirements.txt` + `main.py` setproctitle + Stub-Import +
   `tools/remote/start_simpleft8_nokill.py` setproctitle.
2. **C2** `core/log_setup.py` NEU (3 Funktionen).
3. **C3** `main.py` Z.29-32 → `setup_main_log()` +
   `tools/remote/start_simpleft8_nokill.py` analog.
4. **C4** `core/ntp_time.py` DT-Dedup (Modul-Var + 2× if-Check).
5. **C5** `tests/test_p_bundle_qol.py` NEU (T1-T7).
6. **C6** APP_VERSION 0.97.11 → 0.97.12 + HISTORY + HANDOFF + CLAUDE
   Header + TODO P43/P20/P18 als erledigt.

Backup vor C1:
`Appsicherungen/2026-05-13_v0.97.11_vor_bundle_qol/` mit `main.py`,
`core/ntp_time.py`, `requirements.txt`,
`tools/remote/start_simpleft8_nokill.py`.

## Risiko

**LOW.** Drei kleine, voneinander unabhängige Patches. setproctitle ist
optional (Import-Schutz). Log-Rotation: bestehende Datei wird
**archiviert nicht gelöscht** (Mike's Historie überlebt). DT-Dedup ist
reines Print-Skipping. Worst case: Symlink-Setup auf macOS schlägt
fehl (sehr unwahrscheinlich) → Fallback wäre direktes Datei-Open ohne
Symlink. Add-Test T5 verifiziert das Pfad-Atomicness im tmp-Dir.

**Verbleibende Sorge:** Bei Symlink-Erstellung mit `os.replace` auf
macOS verhalten sich Symlinks anders als reguläre Dateien — wenn das
unerwartet auftritt, fall ich auf direkten Datei-Open zurück (kein
Symlink, Mike nutzt `tail -f simpleft8-YYYY-MM-DD.log` mit aktuellem
Datum). Wird in V3 nach R1-Review entschieden.
