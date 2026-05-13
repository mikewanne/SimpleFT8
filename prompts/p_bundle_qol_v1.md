# P43+P20+P18 — Quality-of-Life-Bundle (V1)

Drei kleine, voneinander unabhängige Hygiene-Fixes als ein
Bundle-Workflow. Alle hardware-frei, kein Field-Test nötig.

## Ziel

1. **P43 setproctitle** — macOS Activity Monitor zeigt
   `SimpleFT8 v0.97.12` statt nur `Python`. Bei P30-Memory-Leak-Suche
   am 12.05. konnte Mike nicht zwischen SimpleFT8 und Qwen3-TTS
   unterscheiden (beide gleicher Python-Name) — exakt das Problem soll
   weg sein.
2. **P20 Log-Rotation** — `~/.simpleft8/simpleft8.log` wächst
   append-only ins MB-Bereich. Eine Datei pro UTC-Tag,
   `simpleft8.log`-Symlink zeigt auf heute, Dateien älter als 7 Tage
   werden gelöscht.
3. **P18 DT-Korr 3×-Reload-Spam** — Beim App-Start steht 3× identisch
   `[DT-Korr] FT8_20m: Gespeicherter Wert +0.650s geladen`. Kosmetik:
   gleicher Output nur 1× pro Wertstand.

## Akzeptanzkriterien

**AK1 — P43 setproctitle.**

- Neue Dependency `setproctitle` in `requirements.txt` ergänzt.
- In `main.py` direkt nach `APP_VERSION = ...` (vor Logging-Init):
  ```python
  try:
      import setproctitle
      setproctitle.setproctitle(f"SimpleFT8 v{APP_VERSION}")
  except ImportError:
      pass  # setproctitle ist optional — App laeuft auch ohne
  ```
- Im Activity Monitor erscheint der Prozessname „SimpleFT8 v0.97.12"
  statt „Python".
- **Import-Schutz** weil setproctitle nicht zur Standardbibliothek
  gehört und auf manchen Systemen ohne C-Compiler fehlschlagen kann.

**AK2 — P20 Log-Rotation.**

- `main.py` Z.29-32: aktueller append-only-Open wird ersetzt durch:
  - Datierter Filename `simpleft8-YYYY-MM-DD.log` (UTC-Datum) wird
    geöffnet im append-mode.
  - Symlink `simpleft8.log` zeigt auf die heutige Datei (atomar via
    tmp+rename neu gesetzt bei App-Start).
  - Cleanup-Funktion löscht alle `simpleft8-*.log`-Dateien älter als 7
    Tage (in `_LOG_DIR`).
- Datum-Roll-over: Bei Tageswechsel während laufender App passiert
  **nichts Aktives** — Datei bleibt heutige, wird beim nächsten App-Start
  auf neue Datei umgestellt. KISS für Hobby-Tool (Mike startet ohnehin
  täglich neu / morgens).
- Cleanup wird beim App-Start synchron ausgeführt, fail-silent.
- Symlink statt Datei-Open: `tail -f ~/.simpleft8/simpleft8.log`
  funktioniert weiterhin wie bisher.

**AK3 — P18 DT-Korr-Spam.**

- In `core/ntp_time.py` Modul-Level neues:
  ```python
  _last_logged_load: tuple | None = None  # (key, saved_val)
  ```
- In `set_mode` (Z.117-121) und `set_band` (Z.137-141): print nur
  ausgeben wenn `(key, saved_val) != _last_logged_load`. Nach print
  Cache aktualisieren.
- „Kein gespeicherter Wert"-Pfad bleibt unverändert (anderer Inhalt,
  selten ohnehin nur 1×).
- Wirkung: Statt 3× identischem Spam beim Start → 1×. Echte
  Wert-Änderungen (z.B. nach Konvergenz + Bandwechsel) werden weiterhin
  geloggt.

**AK4 — Tests grün.** Bestehende Suite läuft weiter. Erwartete neue
Tests: ~5 (siehe Testbarkeit).

**AK5 — Kein Verhaltens-/Architektur-Eingriff.** Keine Veränderung an
Decoder/Encoder/Diversity/QSO-State-Machine/Statistik/Radio-Pfad.
Reine Diagnose-/Wartungs-UX.

## Betroffene Module/Dateien

| Datei | Was |
|---|---|
| `requirements.txt` | `setproctitle` als neue Dependency |
| `main.py` (Z.16+ und Z.29-32) | setproctitle-Init + Log-Rotation-Init |
| `core/ntp_time.py` (Z.119 + Z.139 + neuer Modul-Var) | print-Dedup-Cache |
| `tests/test_p_bundle_qol.py` (NEU) | 5 Tests fuer alle 3 Fixes |

## Randbedingungen

- **KISS:** Keine Helper-Klassen, keine Custom-Logger. setproctitle =
  try/except 3 Zeilen, Log-Rotation = datierter Filename + Symlink +
  Cleanup-Loop, DT-Spam = Modul-Var-Cache.
- **Optional-Dependency setproctitle:** Try/Except-Import, kein
  KeyError wenn fehlt. `requirements.txt` listet es, aber Code arbeitet
  ohne weiter.
- **Hardware-Pflicht ANT1=TX bleibt unberührt.**
- **Hobby-Tool-Philosophie:** Mike als Single-User, kein
  Multi-Profile-Log-Switching.
- **Backward-Kompat:** Alte `simpleft8.log` als regulär e Datei muss
  überleben — Logik prüft ob Pfad ein Symlink ist, falls nicht: ein-
  malig in `simpleft8-archive.log` umbenennen (oder ignorieren? siehe
  V2-Self-Review).

## Nicht im Scope

- **Strukturiertes Debug-Log** (P21) — separater Workflow.
- **Konsolidierung der 3× set_mode/set_band-Calls** beim App-Start —
  riskanter Architektur-Eingriff. Mike selbst sagt „funktional egal",
  nur Spam-Reduktion.
- **Kein Rotation während laufender App** (kein Datum-Roll-Detection
  zur Laufzeit).
- **Keine Komprimierung alter Logs** (.gz o.ä.).
- **Encoder/Decoder/Decoder-AGC-Pfade** bleiben unangetastet.

## Testbarkeit

- **T1 — `test_setproctitle_import_safe`:** Import-Try-Pattern wird
  ausgeführt ohne Crash, auch wenn `setproctitle`-Modul fehlt
  (Mock-Test mit `sys.modules['setproctitle'] = None` o.ä.).
- **T2 — `test_log_filename_dated`:** Helper-Funktion liefert
  datierten Filename `simpleft8-YYYY-MM-DD.log` für gegebenes Datum.
- **T3 — `test_log_cleanup_keeps_recent`:** Cleanup in tmp-Dir löscht
  Dateien älter als 7 Tage, behält jüngere. (Analog
  `core/debug_log.py::test_cleanup_removes_old_files_keeps_recent`.)
- **T4 — `test_dt_dedup_skips_repeat`:** Zweimaliger Aufruf
  `set_mode("FT8", "20m")` produziert nur 1× print mit gleichem Wert
  (capsys-Capture).
- **T5 — `test_dt_dedup_logs_changes`:** Wechsel auf anderen Modus
  oder anderen Wert → erneut print (Cache invalidiert).

Erwartung: **1167 → ~1172** (+5 Bundle A).

## Geplante Commit-Reihenfolge (atomar)

1. **C1** `requirements.txt` + `main.py` (setproctitle-Init).
2. **C2** `main.py` (Log-Rotation-Setup).
3. **C3** `core/ntp_time.py` (DT-Print-Dedup).
4. **C4** `tests/test_p_bundle_qol.py` NEU (T1–T5).
5. **C5** APP_VERSION 0.97.11 → 0.97.12 + HISTORY + HANDOFF + CLAUDE
   Header + TODO P43/P20/P18 als erledigt.

Backup vor C1:
`Appsicherungen/2026-05-13_v0.97.11_vor_bundle_qol/` mit `main.py` +
`core/ntp_time.py` + `requirements.txt`.

## Risiko

**LOW.** Drei kleine, voneinander unabhängige Patches. setproctitle ist
optional (Import-Schutz), Log-Rotation ist nur Datei-Layout (keine
Logik-Änderung), DT-Dedup ist reines Print-Skipping (keine Logik-
Änderung). Keine Tests betreffen Decoder/Encoder/QSO-Pfade. Worst case
bei Fehlfunktion: alter Log-Pfad oder Spam wieder da — keine
Funktions-Regression möglich.
