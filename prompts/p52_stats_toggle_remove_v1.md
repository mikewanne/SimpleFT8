# P52 — Statistik-Toggle raus + 90-Tage-Rolling-Window

## 1. Ziel

Settings-Toggle „Statistik-Erfassung aktivieren" entfernen — Stats sind
immer an (Bandpilot + Auswertungen brauchen sie). Beim App-Start
Statistik-Dateien älter als 90 Tage automatisch löschen damit der
Disk-Footprint nicht unbegrenzt wächst.

## 2. Akzeptanzkriterien

| AC | Was |
|---|---|
| **AC1** | `ui/settings_dialog.py`: QCheckBox „Statistik-Erfassung aktivieren" + alle Load/Save/Reset-Stellen für `stats_cb` entfernt |
| **AC2** | `config/settings.py:DEFAULTS`: `"stats_enabled": True`-Key entfernt |
| **AC3** | `config/settings.py:Settings.load()`: idempotenter Pop von `stats_enabled` (Migration alter Configs analog P47 `audio_freq_hz`) |
| **AC4** | `ui/mw_cycle.py:_log_stats`: Stats-Enabled-Guard entfernt (Z.686-687) — Stats laufen immer |
| **AC5** | `ui/main_window.py:_stats_indicator.setVisible(...)`: Argument auf `True` fest (Indikator immer sichtbar) |
| **AC6** | Neue Datei `core/stats_cleanup.py` mit Funktion `cleanup_stats_older_than_days(stats_dir, days=90) → int` — gibt Anzahl gelöschter Dateien zurück |
| **AC7** | Cleanup berücksichtigt beide Pattern: `YYYY-MM-DD_HH.md` (Stunde-basiert) UND `YYYY-MM-DD.md` (Tag-basiert in `antenna_qso/`). Rescue-Unterverzeichnisse `stations/` werden mit erfasst |
| **AC8** | `main.py` App-Start ruft Cleanup mit `days=90` auf — VOR App-Init, fail-silent bei OSError |
| **AC9** | Cleanup ignoriert nicht-passende Dateinamen (Regex-Match) und schweigt bei OSError pro Datei (analog `cleanup_old_main_logs`) |
| **AC10** | 5–7 neue Tests in `tests/test_p52_stats_cleanup.py`: Pattern-Match-Stunde, Pattern-Match-Tag, alter Datei wird gelöscht, junge Datei bleibt, Nicht-passende Dateinamen unangetastet, Verzeichnis-Existenz-Check, rekursiver Walk durch alle Unterverzeichnisse |
| **AC11** | Bestehender Test `tests/test_settings_dialog_smoke.py:33` (mock `stats_enabled`) bleibt grün durch Migration-Pop (legacy-Key wird stillschweigend verworfen). Falls Mock einen anderen Schlüssel braucht: anpassen |
| **AC12** | Bestehender Test `tests/test_p45_omni_stats_guard.py:53` Kommentar zu `stats_enabled` aktualisieren — Mock kann bleiben (returnt True), Stats-Guard ist eh weg, Test prüft OMNI-Guard separat |
| **AC13** | APP_VERSION 0.97.40 → 0.97.41 |
| **AC14** | Backup `Appsicherungen/2026-05-16_v0.97.40_vor_p52/` |
| **AC15** | HISTORY + HANDOFF + CLAUDE + Memory + TODO aktualisiert |

## 3. Betroffene Module/Dateien

| Datei | Zeile | Was |
|---|---|---|
| `ui/settings_dialog.py` | 316–322 | `stats_cb`-Block raus |
| `ui/settings_dialog.py` | 598 | Load-Zeile raus |
| `ui/settings_dialog.py` | 741 | Save-Zeile raus |
| `ui/settings_dialog.py` | 787, 790 | Reset-Block raus |
| `config/settings.py` | 65 | DEFAULTS-Key raus |
| `config/settings.py` | ~103 | Pop `stats_enabled` in `load()` |
| `ui/main_window.py` | 491 | `setVisible(True)` statt `settings.get(...)` |
| `ui/mw_cycle.py` | 686–687 | Guard raus |
| `core/stats_cleanup.py` | NEU | `cleanup_stats_older_than_days` |
| `main.py` | App-Start | Cleanup-Aufruf vor Init |
| `tests/test_p52_stats_cleanup.py` | NEU | 5–7 Tests |
| `tests/test_settings_dialog_smoke.py` | 33 | mock-Dict ggf. anpassen |
| `tests/test_p45_omni_stats_guard.py` | 53 | Kommentar update |
| `main.py` | APP_VERSION | 0.97.41 |
| `HISTORY.md` | EOF | Eintrag |
| `HANDOFF.md` | Header | Update |
| `CLAUDE.md` | Header | Update |
| `memory/project_p52_stats_cleanup.md` | NEU | Memory |
| `TODO.md` | P52-Block | Auf ERLEDIGT umschreiben |
| `Appsicherungen/2026-05-16_v0.97.40_vor_p52/` | NEU | Backup |

## 4. Randbedingungen

- **Threading:** Cleanup läuft synchron beim App-Start (vor Qt-Event-Loop).
  Bei großen Verzeichnissen (10k+ Dateien) könnte das spürbar sein —
  aber bei realistischer Datenlage (~30 MB / 3 Modi × 9 Bänder × 3 Modi ×
  24 Std × 90 Tage = max 174960 Files, eher 5–10k aktuell) ist ein
  rglob+stat-Loop unter 100 ms. Notfalls in Hintergrund-Thread.
- **Hardware:** irrelevant — kein TX/RX-Pfad.
- **Persistence:** Cleanup `unlink`-only. Keine atomic-write-Anforderung.
- **Dateinamen-Pattern:**
  - `YYYY-MM-DD_HH.md` — Haupt-Stats unter `<Modus>/<Band>/<Proto>/`
  - `YYYY-MM-DD_HH.md` — Rescue-Files unter `<Modus>/<Band>/<Proto>/stations/`
  - `YYYY-MM-DD.md` — Antennen-QSO-Log unter `antenna_qso/`
- **Cutoff:** UTC-basiert (analog `cleanup_old_main_logs`). 00:00:00 des
  Tages der vor 90 Tagen war. File-Date aus Dateiname extrahiert (NICHT
  aus mtime — mtime ist unzuverlässig nach Backup/Restore).
- **Idempotenz:** Cleanup mehrfach ausführbar ohne Schaden. Pop `stats_enabled`
  ebenfalls (Dict.pop mit Default = no-op bei fehlendem Key).
- **Migration:** Alte Configs mit `stats_enabled=False` haben praktisch
  niemand (Default war True). Trotzdem sauberer Pop damit Settings-File
  nach Save den Key nicht mehr enthält.

## 5. Nicht im Scope

- Settings-Migration für ALLE legacy-Keys (nur `stats_enabled`)
- Hintergrund-Thread für Cleanup (synchron reicht)
- Konfigurierbares Cleanup-Limit (fest 90 Tage)
- Stats-Format-Änderungen
- Bandpilot-Logik (bleibt unverändert)
- `_stats_indicator` Style/Position (bleibt — nur `setVisible(True)`)
- Per-Modus/Per-Band-Cleanup (alle gleichberechtigt)
- Backup-vor-Cleanup (Mike hat externe Backups; pre-90-Tage-Daten sind
  bewusst weg)

## 6. Testbarkeit

7 Tests in `tests/test_p52_stats_cleanup.py`:

| T# | Was |
|---|---|
| **T1** | Pattern-Match `YYYY-MM-DD_HH.md` — alte Datei wird gelöscht |
| **T2** | Pattern-Match `YYYY-MM-DD.md` — alte Datei in `antenna_qso/` gelöscht |
| **T3** | Junge Datei (< 90 Tage) bleibt |
| **T4** | Nicht-passender Dateiname (z.B. `notes.md`, `README.md`) bleibt |
| **T5** | Rekursiver Walk: alte Datei in `<Modus>/<Band>/<Proto>/stations/` wird auch gelöscht |
| **T6** | Cleanup auf nicht-existentem Verzeichnis returnt 0 ohne Exception |
| **T7** | Pop von `stats_enabled` in `Settings.load()` ist idempotent + entfernt den Key wirklich (legacy migration) |

Plus 1 angepasster Test (`test_settings_dialog_smoke.py` falls Mock-Dict-
Schlüssel-Set jetzt fehlt).

Erwarteter Test-Count: 1339 + 7 = **1346 grün**.

## 7. Mike-Field-Test (kein Radio nötig)

| F# | Was prüfen |
|---|---|
| **F1** | Settings-Dialog öffnen → „Statistik-Erfassung aktivieren"-Checkbox **NICHT MEHR DA** |
| **F2** | Statusbar rechts: `Statistik`-Indikator **immer sichtbar** (war früher abhängig vom Toggle) |
| **F3** | App-Start mit altem `config.json` der `stats_enabled: false` enthält → App startet ohne Fehler, Settings-File nach Save enthält Key nicht mehr |
| **F4** | App-Start in 90+ Tagen: Statistics-Dateien älter als 90 Tage sind im Verzeichnis-Listing weg (visueller Check via `ls statistics/Normal/40m/FT8/`) |

## 8. Plan-Sequenz für Code

C1: Backup
C2: `core/stats_cleanup.py` NEU + Tests T1-T6
C3: `config/settings.py` DEFAULTS-Key raus + Pop + Test T7
C4: `ui/settings_dialog.py` stats_cb-Block raus (3 Stellen)
C5: `ui/mw_cycle.py` Guard raus
C6: `ui/main_window.py` setVisible-Argument auf True
C7: `main.py` APP_VERSION + Cleanup-Aufruf
C8: `tests/test_settings_dialog_smoke.py` + `test_p45_omni_stats_guard.py` anpassen
C9: TODO/HISTORY/HANDOFF/CLAUDE/Memory updates
