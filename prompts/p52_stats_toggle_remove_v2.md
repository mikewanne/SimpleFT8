Du bist Senior Python-Entwickler spezialisiert auf Amateurfunk-Software
und PySide6 (Signal statt pyqtSignal, Slot statt pyqtSlot). Das Projekt
ist ein Hobby-Funker-Tool für einen einzelnen Operator — NICHT Multi-Tenant.

Deine einzige Aufgabe: diesen Prompt kritisieren — NICHT das Problem lösen.
Strukturierte Liste: Lücken, Unklarheiten, Widersprüche, Verbesserungen.

KRITISCHE REGELN:
1. SCOPE-RESPEKT: Explizit als out-of-scope markiertes NICHT als Finding melden.
2. KISS VOR DEFENSIV: Komplexität nur wenn Wahrscheinlichkeit > 50%.
3. PROJEKT-BEZUG: Jedes Finding am konkreten Use-Case messen.
4. FORMAT: Tabelle Schwere | Finding | Datei:Zeile | Empfehlung.
   Severity: Bug (rot) / Risiko (orange) / Verbesserung (gelb) / Hinweis (grau).

Overengineering ist selbst ein Fehler den du benennen sollst.

---

# P52 — Statistik-Toggle raus + 90-Tage-Rolling-Window

## 1. Kontext

Settings-Toggle „Statistik-Erfassung aktivieren" ist seit langem in
Settings-Dialog → Tab „Allgemein" enthalten. Mike-Klärung 14.05.2026:
sinnlos, weil Bandpilot + Auswertungen die Stats zwingend brauchen.
Plus: Stats wachsen unbegrenzt (~1 MB/Tag bei 40m-FT8-24h-Betrieb).

**Ziel:** Toggle komplett raus, Stats immer an, Files älter als 90 Tage
beim App-Start automatisch löschen.

## 2. Akzeptanzkriterien

| AC | Was |
|---|---|
| **AC1** | `ui/settings_dialog.py`: QCheckBox „Statistik-Erfassung aktivieren" Block (Z.316–322) + Load (Z.598) + Save (Z.741) + Reset (Z.790) entfernt. Z.787 Kommentar `# stats_cb...` aktualisieren auf nur `# debug_console_cb`. |
| **AC2** | `config/settings.py:DEFAULTS`: `"stats_enabled": True`-Zeile (Z.65) entfernt |
| **AC3** | `config/settings.py:Settings.load()` (~Z.103): idempotenter Pop von `stats_enabled` analog `audio_freq_hz`/`max_decode_freq` (P47-Pattern). Eine Zeile: `self._data.pop("stats_enabled", None)` |
| **AC4** | `ui/mw_cycle.py:_log_stats` (Z.686–687): Stats-Enabled-Guard komplett entfernt — Stats laufen immer. Andere Guards (logger-None, Band-Filter, Warmup, Tuning, CQ/QSO) bleiben unverändert |
| **AC5** | `ui/main_window.py:491`: Zeile `self._stats_indicator.setVisible(...)` komplett entfernt — Widget ist by-default sichtbar. Kommentar darüber (Z.485) aktualisieren: „Statistik-Indikator (permanent, immer sichtbar seit P52)" |
| **AC6** | Neue Datei `core/stats_cleanup.py` mit Funktion `cleanup_stats_older_than_days(stats_dir: Path, days: int = 90) -> int` — gibt Anzahl gelöschter Dateien zurück. Pattern analog `core/log_setup.py:cleanup_old_main_logs` |
| **AC7** | Cleanup berücksichtigt **zwei** Pattern via separater Regex: |
|  | `_DATED_HOUR = re.compile(r"^(\d{4}-\d{2}-\d{2})_\d{2}\.md$")` — Haupt-Stats + Rescue-Files |
|  | `_DATED_DAY = re.compile(r"^(\d{4}-\d{2}-\d{2})\.md$")` — `antenna_qso/`-Format |
| **AC8** | Cleanup nutzt `rglob("*.md")` für rekursiven Walk durch alle Unterverzeichnisse von `stats_dir`. Cutoff aus Dateiname (NICHT mtime — Backup/Restore-robust) |
| **AC9** | `main.py` App-Start ruft Cleanup mit `days=90` vor App-Init auf. Fail-silent bei Exception (analog `setup_main_log`) — App startet immer, Cleanup ist Best-Effort |
| **AC10** | Cleanup ignoriert nicht-passende Dateinamen (Regex-mismatch → skip). Fail-silent pro Datei bei OSError |
| **AC11** | 7 neue Tests in `tests/test_p52_stats_cleanup.py` (siehe Test-Matrix unten) |
| **AC12** | Bestehender Test `tests/test_settings_dialog_smoke.py:33` (mock-Dict mit `"stats_enabled": True`): Schlüssel im Mock-Dict bleibt für Migration-Test relevant ODER wird entfernt — V2 prüft welches sauberer ist (mein Vorschlag: drinlassen, da nicht störend und migration zeigt) |
| **AC13** | Bestehender Test `tests/test_p45_omni_stats_guard.py:53` Mock `settings.get` returnt True — Kommentar `# stats_enabled` durch `# generic settings.get returns True` ersetzen |
| **AC14** | APP_VERSION 0.97.40 → 0.97.41 in `main.py` |
| **AC15** | Backup `Appsicherungen/2026-05-16_v0.97.40_vor_p52/` |
| **AC16** | HISTORY.md neuer Eintrag, HANDOFF.md aktualisiert, CLAUDE.md Header, Memory `project_p52_stats_cleanup.md`, TODO.md P52-Block auf ERLEDIGT umschreiben |

## 3. Betroffene Module/Dateien (verifiziert)

| Datei | Aktion |
|---|---|
| `ui/settings_dialog.py` | stats_cb-Block raus (4 Stellen: Z.316–322 Definition, Z.598 Load, Z.741 Save, Z.790 Reset; plus Kommentar Z.787 anpassen) |
| `config/settings.py` | DEFAULTS-Z.65 raus, Pop in Z.~103 hinzufügen |
| `ui/main_window.py` | Z.491 raus, Kommentar Z.485 anpassen |
| `ui/mw_cycle.py` | Z.686–687 raus, kein anderer Code in `_log_stats` betroffen |
| `core/stats_cleanup.py` | NEU |
| `main.py` | APP_VERSION + Cleanup-Aufruf |
| `tests/test_p52_stats_cleanup.py` | NEU (7 Tests) |
| `tests/test_settings_dialog_smoke.py` | evtl. anpassen (siehe AC12) |
| `tests/test_p45_omni_stats_guard.py` | Kommentar Z.53 anpassen |
| HISTORY.md, HANDOFF.md, CLAUDE.md, TODO.md | Updates |
| `memory/project_p52_stats_cleanup.md` | NEU |
| `Appsicherungen/2026-05-16_v0.97.40_vor_p52/` | NEU |

## 4. Code-Skizzen

### `core/stats_cleanup.py`

```python
"""90-Tage-Rolling-Window fuer statistics/ (P52, v0.97.41).

Bei App-Start werden Stats-Dateien aelter als ``days`` (Default 90)
geloescht — analog ``core/log_setup.cleanup_old_main_logs`` aber
rekursiv durch alle Modus/Band/Protokoll-Unterverzeichnisse.

Pattern:
    statistics/<Modus>/<Band>/<Proto>/YYYY-MM-DD_HH.md
    statistics/<Modus>/<Band>/<Proto>/stations/YYYY-MM-DD_HH.md
    statistics/antenna_qso/YYYY-MM-DD.md

Cutoff: UTC-Datum aus Dateiname (NICHT mtime — Backup-robust).
Fail-silent pro Datei. Idempotent.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta
from pathlib import Path


_DATED_HOUR = re.compile(r"^(\d{4}-\d{2}-\d{2})_\d{2}\.md$")
_DATED_DAY = re.compile(r"^(\d{4}-\d{2}-\d{2})\.md$")


def cleanup_stats_older_than_days(
    stats_dir: Path, days: int = 90
) -> int:
    """Loescht Stats-Files aelter als ``days`` Tage (UTC).

    Returns Anzahl geloeschter Dateien. Fail-silent pro Datei.
    """
    stats_dir = Path(stats_dir)
    if not stats_dir.exists():
        return 0
    cutoff = (datetime.utcnow() - timedelta(days=days)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    deleted = 0
    for f in stats_dir.rglob("*.md"):
        try:
            m = _DATED_HOUR.match(f.name) or _DATED_DAY.match(f.name)
            if not m:
                continue
            file_date = datetime.strptime(m.group(1), "%Y-%m-%d")
            if file_date < cutoff:
                f.unlink()
                deleted += 1
        except (ValueError, OSError):
            continue
    return deleted
```

### `main.py` Integration (Skizze)

```python
# Existing imports
from core.log_setup import setup_main_log

# NEU
from core.stats_cleanup import cleanup_stats_older_than_days

# In main() VOR Qt-Init (nach log_setup):
try:
    _stats_dir = Path(__file__).parent / "statistics"
    _deleted = cleanup_stats_older_than_days(_stats_dir, days=90)
    if _deleted:
        print(f"[Stats-Cleanup] {_deleted} Dateien >90 Tage geloescht")
except Exception as e:
    print(f"[Stats-Cleanup] Fehler ignoriert: {e}")
```

## 5. Randbedingungen

- **Threading:** Cleanup synchron beim App-Start vor Qt-Event-Loop. Bei
  realistischer Datenlage (5–10k Files) unter 100 ms. Notfalls in v0.98+
  Hintergrund-Thread, aktuell unnötig.
- **Hardware:** irrelevant — kein TX/RX/Antennen-Pfad.
- **Cutoff-Quelle:** Dateiname (UTC-Datum extrahiert aus Pattern), NICHT
  mtime — sonst würde Backup-Restore alle Daten verjüngen und Cleanup
  würde nichts löschen.
- **Idempotenz:** Cleanup ohne Schaden mehrfach ausführbar. Pop ebenfalls.
- **Bestehende-Daten-Schutz:** Mike's aktuelle Stats sind aus April-Mai
  2026 (Datenlage in CLAUDE.md). Heute (16.05.) sind alle <30 Tage —
  Cleanup würde nichts löschen. Erst in Juli 2026 fängt Cleanup an
  Effekt zu zeigen. Mike kann externe Backups vor 1. Aug 2026 anlegen
  falls er pre-90-Tage-Daten behalten will.

## 6. Nicht im Scope

- Migration weiterer legacy-Keys (nur `stats_enabled`)
- Hintergrund-Thread für Cleanup
- Konfigurierbares Cleanup-Limit (Settings-Toggle für die 90 Tage)
- Stats-Format-Änderungen
- Bandpilot-Logik
- `_stats_indicator` Style/Position
- Per-Modus/Per-Band-Cleanup (gleichbehandelt)
- Backup-vor-Cleanup
- `aggregate_stats_by_hour` und andere Reader-APIs — die laufen
  weiter, lesen nur was da ist

## 7. Tests (T1–T7)

| T# | Was | Aufbau |
|---|---|---|
| **T1** | Hour-Pattern, alte Datei wird gelöscht | tmp_path mit Datei `<Modus>/<Band>/<Proto>/2024-01-01_12.md` + frischer Datei `2026-05-15_12.md`. Cleanup days=90, assert alte weg, neue da, return=1 |
| **T2** | Day-Pattern, alte antenna_qso/-Datei gelöscht | tmp_path mit `antenna_qso/2024-01-01.md` + `antenna_qso/2026-05-15.md`. Cleanup days=90, assert alte weg, return=1 |
| **T3** | Junge Datei (<90 Tage) bleibt | tmp_path mit `<Modus>/<Band>/<Proto>/2026-05-15_12.md` heute. Cleanup days=90, return=0, Datei da |
| **T4** | Nicht-passender Dateiname bleibt | `notes.md`, `summary.md`, `README.md` in Verzeichnis. Cleanup, return=0, alle da |
| **T5** | Rekursiver Walk durch `stations/`-Unterverzeichnis | Datei `<Modus>/<Band>/<Proto>/stations/2024-01-01_12.md` (Rescue). Cleanup, gelöscht |
| **T6** | Nicht-existentes Verzeichnis | Cleanup auf `/tmp/nonexistent`, return=0, keine Exception |
| **T7** | Settings-Migration: `stats_enabled` wird gepoppt | Settings mit `stats_enabled=False` im JSON. `Settings.load()`, danach `"stats_enabled" not in settings._data` |

Erwarteter Test-Count: 1339 + 7 = **1346 grün**.

## 8. Mike-Field-Test (kein Radio nötig)

| F# | Was prüfen |
|---|---|
| **F1** | Settings-Dialog öffnen → „Allgemein"-Tab → kein Checkbox „Statistik-Erfassung aktivieren" mehr |
| **F2** | Statusbar rechts: „Statistik"-Indikator immer sichtbar (grau wenn pausiert, grün wenn loggt) |
| **F3** | Settings-File `~/.simpleft8/config.json` nach App-Start: kein `stats_enabled`-Key mehr drin (alte Configs werden migriert) |
| **F4** | Konsolen-Output beim App-Start: `[Stats-Cleanup] N Dateien >90 Tage geloescht` (oder still wenn nichts zu tun) |

## 9. Plan-Sequenz (atomare Commits)

| C# | Was | Datei(en) |
|---|---|---|
| **C1** | Backup-Verzeichnis | `Appsicherungen/2026-05-16_v0.97.40_vor_p52/` |
| **C2** | `core/stats_cleanup.py` NEU | `core/stats_cleanup.py` |
| **C3** | Tests T1-T6 für stats_cleanup | `tests/test_p52_stats_cleanup.py` |
| **C4** | Settings-Migration + Pop + Test T7 | `config/settings.py`, `tests/test_p52_stats_cleanup.py` |
| **C5** | settings_dialog stats_cb-Block raus | `ui/settings_dialog.py` |
| **C6** | mw_cycle Guard raus | `ui/mw_cycle.py` |
| **C7** | main_window setVisible raus | `ui/main_window.py` |
| **C8** | main.py APP_VERSION + Cleanup-Aufruf | `main.py` |
| **C9** | Bestehende Tests anpassen | `tests/test_settings_dialog_smoke.py`, `tests/test_p45_omni_stats_guard.py` |
| **C10** | Doku-Updates | HISTORY, HANDOFF, CLAUDE, TODO, Memory |

## 10. Offene Fragen an R1

1. **AC12** — Im `test_settings_dialog_smoke.py` Mock-Dict steht `"stats_enabled": True`. Drinlassen (zeigt dass Migration-Pop nicht crasht wenn Key noch da ist) oder rausnehmen (cleaner)? Ich tendiere zu drinlassen.
2. **AC7** — Zwei separate Regex (`_DATED_HOUR` + `_DATED_DAY`) oder ein kombiniertes (`r"^(\d{4}-\d{2}-\d{2})(?:_\d{2})?\.md$"`)? KISS: separate.
3. **AC9** — Cleanup-Aufruf in `main.py` vor oder nach `setup_main_log()`? Reihenfolge spielt keine Rolle (verschiedene Dateien), aber Konvention?
4. **Performance:** `rglob("*.md")` auf 10k+ Files — okay für synchron, oder Background-Thread schon jetzt?
5. **Pattern für `stations/`-Files:** Werden die wirklich von Mike's Reader-Code (`generate_plots.py:load_rescue_by_hour` Z.824) gelesen, oder sind das nur Rescue-Counter? Falls Reader sie braucht → muss Reader auch tolerieren wenn alte Daten weg sind (sollte er, fail-silent).
6. **Settings-Save:** Wenn `Settings.save()` ohne `stats_enabled` schreibt — kommt der Key komplett aus dem JSON-File raus oder bleibt er hängen? Migration-Pop ist in `load()`, also nächster Save schreibt ohne den Key. ✓
