# P43+P20+P18 — Quality-of-Life-Bundle (V3)

> **R1-Findings eingearbeitet:** 3 Risiken + 1 Verbesserung + 1 Hinweis
> angenommen, 2 Hinweise mit Begründung beibehalten.

---

## Ziel

Drei kleine, voneinander unabhängige Hygiene-Fixes als gemeinsames
Bundle. Alle hardware-frei, kein Field-Test nötig.

1. **P43 setproctitle** — macOS Activity Monitor zeigt
   `SimpleFT8 v0.97.12` statt nur `Python`.
2. **P20 Log-Rotation** — `~/.simpleft8/simpleft8.log` wird täglich
   rotiert, alte Logs (>7 Tage) werden gelöscht. Mike's bestehende
   `simpleft8.log` landet **dauerhaft** im Archiv-Unterordner.
3. **P18 DT-Korr-Print-Spam** — `[DT-Korr] FT8_20m: Gespeicherter Wert
   +0.650s geladen` nur 1× pro Wertstand.

## Hintergrund (Code-Verifikation 13.05.)

- **P43:** `setproctitle` nicht installiert → neue Dependency.
- **P20:** Zwei Open-Stellen synchron halten: `main.py:32` und
  `tools/remote/start_simpleft8_nokill.py:24`. Helper-Modul
  `core/log_setup.py` (NEU) konsolidiert Logik.
- **P18:** `core/ntp_time.py:119` und `:139` printen identisch.
  Aufrufer-Pfad (3× beim Start aus `mw_radio.py:167/322/458`) bleibt
  unverändert — nur Print-Dedup.

## Akzeptanzkriterien

**AK1 — P43 setproctitle.**

- `requirements.txt` ergänzt um `setproctitle`.
- `main.py` direkt nach Z.16 (`APP_VERSION = ...`) und vor Z.18
  (Single-Instance-Lock-Block):
  ```python
  # ── P43: Activity Monitor zeigt Prozess-Namen statt nur "Python" ──
  try:
      import setproctitle
      setproctitle.setproctitle(f"SimpleFT8 v{APP_VERSION}")
  except ImportError:
      pass  # setproctitle ist optional — App laeuft auch ohne
  ```
- `tools/remote/start_simpleft8_nokill.py` analog am Anfang ergänzt.

**AK2 — P20 Log-Rotation.**

Neue Datei `core/log_setup.py` mit 3 Funktionen:

1. **`dated_log_filename(log_dir, date=None) -> Path`**
   - liefert `{log_dir}/simpleft8-YYYY-MM-DD.log` für UTC-Datum
   - `date=None` → `datetime.utcnow()` (bewusst beibehalten, konsistent
     mit `core/debug_log.py`; Migration auf `datetime.now(timezone.utc)`
     ist projektweite separate Aufgabe)

2. **`cleanup_old_main_logs(log_dir, keep_days=7) -> int`**
   - Glob-Muster `simpleft8-????-??-??.log` (nicht der Symlink, nicht
     `simpleft8-pre-rotation-*.log`)
   - `try/except (ValueError, OSError): continue` Robustheit
   - Returns Anzahl gelöschter Dateien

3. **`setup_main_log(log_dir=None) -> tuple[Path, IO]`** —
   Eintritts-API:
   - `log_dir = log_dir or (Path.home() / ".simpleft8")`
   - Gesamt-Try/Except (R1-Risiko 3 + Hinweis 3): bei jedem
     Fehler in mkdir/Symlink/Open → Print-Warning + Fallback auf
     direkten Open `_log_dir / "simpleft8.log"` im append-mode (alter
     Pfad, kein Symlink, kein Rotation).
   - Sub-Try um Archivierung: alte `simpleft8.log` (reguläre Datei,
     **nicht** Symlink) wird verschoben in
     `{log_dir}/archive/simpleft8-pre-rotation-YYYY-MM-DD.log`.
     **Archive-Unterordner wird vom Cleanup NICHT angefasst** (R1
     Risiko 1) — Mike's Historie bleibt dauerhaft erhalten.
   - Sub-Try um Symlink-Setup (R1 Risiko 3): bei `OSError`
     → Fallback auf direkten Datei-Open ohne Symlink + Warning.
     Bei Erfolg: atomar via tmp-Symlink + `os.replace`.
   - Cleanup aufrufen vor Datei-Open (löscht nur datierte Logs > 7
     Tage, niemals Archive).
   - Datei öffnen in append-mode mit `buffering=1`, return `(path,
     handle)`.

**Aufruf in `main.py` Z.29-32:**
```python
# ── File Logging mit Tages-Rotation (P20) ─────────────────────
from core.log_setup import setup_main_log
_log_path, _log_file = setup_main_log()
```

`tools/remote/start_simpleft8_nokill.py` Z.22-24 analog.

**AK3 — P18 DT-Korr-Print-Spam.**

In `core/ntp_time.py` Modul-Level (nach Z.53):
```python
_last_logged_load: tuple | None = None  # (key, saved_val) — R1-vereinfacht
```

In `set_mode` (Z.117-121) und `set_band` (Z.137-141):

```python
key = _mode_key()
load_marker = (key, saved_val)
global _last_logged_load
if load_marker != _last_logged_load:
    if saved_val != 0.0:
        print(f"[DT-Korr] {key}: Gespeicherter Wert {saved_val:+.3f}s geladen")
    else:
        print(f"[DT-Korr] {key}: Kein gespeicherter Wert, starte bei 0")
    _last_logged_load = load_marker
```

Wirkung: 3× identischer Spam beim Start → 1×. Real e Wertänderungen
weiterhin sichtbar.

**AK4 — Bestehende Tests bleiben grün.**

- `tests/test_debug_log.py`: betrifft `debug_*.log`, unangetastet.
- `tests/test_modules.py:1257` `test_dt_save_load_per_mode_band`:
  nutzt `_save_current()/_load_for_current_key()` direkt ohne
  set_mode/set_band → kein Print, kein Dedup-Konflikt.

**AK5 — Neue Tests (`tests/test_p_bundle_qol.py`).**

Helper am Test-Top: Reset von `_last_logged_load` und `_saved`:
```python
@pytest.fixture(autouse=False)
def reset_ntp(monkeypatch):
    import core.ntp_time as nt
    monkeypatch.setattr(nt, "_last_logged_load", None)
    monkeypatch.setattr(nt, "_saved", {})
    yield
```

- **T1 — `test_setproctitle_safe_when_missing`:** Source-Check —
  `main.py` enthält Pattern `try:` + `import setproctitle` +
  `except ImportError:` als Substring. Pragmatischer Source-Check
  analog P47 T5-Pattern (R1-Hinweis 2 akzeptiert — Mock-Test wäre
  overengineering). Mike kann den Test bei UI-Refactor anpassen.

- **T2 — `test_dated_log_filename_format`:** Aufruf
  `dated_log_filename(tmp_path, datetime(2026, 5, 13))` liefert
  `tmp_path / "simpleft8-2026-05-13.log"`.

- **T3 — `test_cleanup_old_main_logs_keeps_recent`:** `tmp_path` mit:
  - `simpleft8-2026-05-13.log` (heute)
  - `simpleft8-2026-05-08.log` (vor 5 Tagen, mtime gesetzt)
  - `simpleft8-2026-04-13.log` (vor 30 Tagen, mtime gesetzt)
  - `simpleft8.log` (Symlink, sollte unangetastet bleiben)
  → `cleanup_old_main_logs(tmp_path, keep_days=7)` löscht 1 Datei
  (30 Tage), behält die anderen 2 + Symlink.

- **T4 — `test_setup_main_log_archives_existing_file`:** `tmp_path`
  mit vorhandener regulärer Datei `simpleft8.log` (echte Datei,
  Content „alt") → `setup_main_log(tmp_path)` → Datei in
  `tmp_path / "archive" / "simpleft8-pre-rotation-YYYY-MM-DD.log"`
  verschoben, Symlink `simpleft8.log` zeigt auf heutige datierte
  Datei.

- **T5 — `test_setup_main_log_replaces_existing_symlink`:** `tmp_path`
  mit existierendem Symlink `simpleft8.log` → alte
  `simpleft8-2026-05-10.log` → `setup_main_log(tmp_path)` ersetzt
  Symlink atomar auf heutigen Pfad. Alte datierte Datei bleibt
  unangetastet.

- **T6 — `test_setup_main_log_fallback_on_symlink_error`** (R1
  Risiko 3): monkeypatch `os.symlink` → `OSError("EPERM")`.
  `setup_main_log(tmp_path)` darf nicht crashen, liefert
  (path, handle), und path ist `tmp_path / "simpleft8.log"`
  (Fallback ohne Symlink).

- **T7 — `test_dt_dedup_skips_repeat`** (mit `reset_ntp`-Fixture):
  `_saved["FT8_20m"] = 0.65` (R1 Risiko 2 — deterministisch),
  dann 2× `set_mode("FT8", "20m")`. `capsys.readouterr().out` enthält
  genau 1× `[DT-Korr] FT8_20m: Gespeicherter Wert +0.650s`.

- **T8 — `test_dt_dedup_logs_on_change`** (mit `reset_ntp`-Fixture):
  `_saved["FT8_20m"] = 0.65`, `_saved["FT4_40m"] = 0.42`,
  dann `set_mode("FT8", "20m")` + `set_mode("FT4", "40m")` →
  2× distinct prints.

Erwartung: **1167 → 1175** (+8 Bundle A).

**AK6 — Kein Architektur-Eingriff.** Keine Veränderung an
Decoder/Encoder/Diversity/QSO-State-Machine/Radio-Pfad/Statistik.

## Betroffene Module/Dateien

| Datei | Funktion / Block | Was |
|---|---|---|
| `requirements.txt` | (Top-Level) | `setproctitle` als neue Dependency |
| `main.py` | nach `APP_VERSION` (Z.16) | setproctitle-Init |
| `main.py` | Z.29-32 (Log-Init-Block) | `setup_main_log()`-Aufruf |
| `tools/remote/start_simpleft8_nokill.py` | Z.18-24 | analog setproctitle + setup_main_log |
| `core/log_setup.py` | NEU | 3 Funktionen mit Fallback-Try/Except |
| `core/ntp_time.py` | Z.53 Zustands-Vars | `_last_logged_load` neu |
| `core/ntp_time.py` | Z.117-121 (set_mode) | Dedup-Check |
| `core/ntp_time.py` | Z.137-141 (set_band) | Dedup-Check |
| `tests/test_p_bundle_qol.py` | NEU | T1-T8 |

## Randbedingungen

- **KISS:** 3 freie Funktionen statt Klasse, try/except statt
  defensiver Type-Checks, Dedup-Cache als Modul-Var statt Singleton.
- **Optional-Dependency setproctitle:** Try/Except — App läuft auch
  ohne.
- **Hardware-Pflicht ANT1=TX bleibt unberührt.**
- **Hobby-Tool:** Single-User, keine Multi-Profile-Logs, keine
  Komprimierung.
- **Backward-Kompat:** Mike's vorhandene `simpleft8.log` →
  `archive/simpleft8-pre-rotation-YYYY-MM-DD.log` (dauerhaft, kein
  Cleanup). R1-Widerspruch aufgelöst.
- **Atomic-Symlink-Update mit Fallback:** `os.symlink(target,
  tmp) + os.replace(tmp, final)`; bei `OSError` Fallback auf
  direkten Open ohne Symlink.
- **UTC-Datum** für Filename und Cleanup (konsistent mit
  `core/debug_log.py` — Migration auf timezone-aware ist projektweite
  separate Aufgabe).
- **Cleanup fail-silent:** `try/except (ValueError, OSError):
  continue` pro Datei.
- **Tests deterministisch** durch `monkeypatch._saved` +
  `_last_logged_load = None` Reset (R1 Risiko 2).

## Nicht im Scope

- **Strukturiertes Debug-Log** (P21).
- **Konsolidierung der 3× set_mode/set_band-Calls** beim App-Start.
- **Rotation während laufender App** (kein Roll-Detection).
- **Komprimierung** alter Logs.
- **Encoder/Decoder/Diversity/Radio-Pfade.**
- **Keine Migration alter `debug_*.log`** (separate Logik).
- **Datetime.utcnow → timezone.utc-Migration** (projektweite
  Aufgabe, eigenes Thema).

## Geplante Commit-Reihenfolge (atomar)

1. **C1** `requirements.txt` + `main.py` + `tools/remote/...` setproctitle.
2. **C2** `core/log_setup.py` NEU.
3. **C3** `main.py` + `tools/remote/...` Log-Setup-Umstellung.
4. **C4** `core/ntp_time.py` DT-Dedup.
5. **C5** `tests/test_p_bundle_qol.py` NEU (T1-T8).
6. **C6** APP_VERSION 0.97.11 → 0.97.12 + HISTORY + HANDOFF + CLAUDE
   Header + TODO P43/P20/P18 als erledigt + setproctitle pip install
   im venv.

Backup vor C1:
`Appsicherungen/2026-05-13_v0.97.11_vor_bundle_qol/` mit `main.py`,
`core/ntp_time.py`, `requirements.txt`,
`tools/remote/start_simpleft8_nokill.py`.

## R1-Findings-Bilanz (V2 → V3)

| Finding | Schwere | Aktion |
|---|---|---|
| Archiv-Widerspruch (löschen/nicht löschen) | 🟠 Risiko | **Angenommen** — Archive in Unterordner `archive/` ohne Cleanup |
| T6/T7 hängen an Mike's dt_corrections.json | 🟠 Risiko | **Angenommen** — `_saved` per monkeypatch deterministisch |
| Symlink ohne Fallback | 🟠 Risiko | **Angenommen** — try/except + Fallback direkter Open + T6-Test |
| Dedup-Tupel mit redundantem Bool | 🟢 Verbesserung | **Angenommen** — `(key, saved_val)` |
| datetime.utcnow() deprecated | 🔘 Hinweis | **Beibehalten** — projektweite Migration ist eigene Aufgabe, hier konsistent mit `core/debug_log.py` |
| T1 Source-Check fragil | 🔘 Hinweis | **Beibehalten** — Mock-Test = overengineering, P47-Pattern bewährt |
| mkdir-Fehler | 🔘 Hinweis | **Angenommen** — Gesamt-Try/Except in `setup_main_log` mit Fallback |

## Risiko

**LOW.** Drei kleine, voneinander unabhängige Patches. setproctitle
optional. Log-Rotation: bestehende Datei in `archive/` (dauerhaft).
DT-Dedup: reines Print-Skipping. Worst case: Symlink-Setup auf macOS
schlägt fehl → Fallback auf direkten Open (T6 verifiziert) → App
läuft normal, nur ohne Symlink-Komfort.
