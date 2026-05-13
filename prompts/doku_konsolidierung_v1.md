# Doku-Konsolidierung SimpleFT8 — Prompt V1

## Ziel

Vollständige Konsolidierung der SimpleFT8-Dokumentation: einheitliche
Struktur (`docs/explained/<feat>_de.md` + `<feat>.md`), vollständige
Feature-Abdeckung (DE+EN), saubere App-Verlinkung über den `?`-Button im
Hauptfenster, aktualisierte README, finalem GitHub-Push. Eine Single
Source of Truth für jede Feature-Dokumentation — App und GitHub-Reader
bekommen identische Erklärungen.

## Akzeptanzkriterien

1. **Single Source of Truth:** Jedes User-Feature hat genau zwei Doku-
   Dateien: `docs/explained/<feat>_de.md` (Deutsch) und `<feat>.md`
   (Englisch). Keine Duplikate in `docs/`.
2. **Naming-Konvention:** kebab-case, `_de.md`-Suffix für Deutsch,
   ohne Suffix (`.md`) für Englisch — wie bisheriger explained/-Standard.
3. **Bandpilot vollständig integriert:**
   - Verschoben/umbenannt von `docs/bandpilot_help_<de|en>.md` auf
     `docs/explained/bandpilot_<de|en>.md` (Suffix-Norm).
   - In `_FEATURES` von `ui/help_dialog.py` aufgenommen.
   - Erwähnt in README "Key Innovations" + "All Features" + "In Field
     Test" + "Detailed Feature Documentation"-Tabelle.
   - `ui/settings_dialog.py:_show_bandpilot_help()` zeigt auf neue Datei.
4. **Migrationen aus `docs/` nach `docs/explained/`:**
   - `POWER_REGULATION_DE/EN.md` → `power-regulation_de.md` + `.md`
   - `FREQUENCY_HISTOGRAM_DE/EN.md` → `cq-frequency_de.md` + `.md`
   - `DX_TUNING_DE/EN.md` → `dx-tuning_de.md` + `.md` (NICHT redundant
     zu gain-measurement — DX-Tuning ist die 4.5-Min-18-Zyklus-Messung
     mit Preset-Speicherung; gain-measurement ist Audio-Pegel-
     Kalibrierung)
5. **Lösch-Kandidaten (Inhalt von explained/-Pendant abgedeckt):**
   - `DIVERSITY_DE/EN.md` (zugunsten `diversity-modes_de.md` + `.md`)
   - `DT_CORRECTION_DE/EN.md` (zugunsten `dt-correction_de.md` + `.md`)
   - **Bedingung:** Vor Löschung Inhalt vergleichen, einzigartige
     Passagen ggf. nach explained/ mergen.
6. **Neue Doku-Files für nicht-doku­men­tierte Features (DE+EN):**
   - `antenna-preference` — Smart Antenna Selection (Pro-Station Pref)
   - `waitlist` — Caller Waitlist (Grid + Report Queue)
   - `direction-map` — 3D-Globus mit 16 Sektor-Wedges
   - `locator-mining` — Live Locator-DB aus CQ-Calls
   - `auto-hunt` — Automatische Waitlist-Abarbeitung (v0.75)
7. **DE/EN-Konsistenz:**
   - `diversity-modes.md` (EN) auf DE-Stand bringen (159 → ~159 Zeilen).
   - Übrige DE/EN-Pendants prüfen, Linecount-Diff < 25% halten.
8. **Help-Dialog erweitert:** `_FEATURES` in `ui/help_dialog.py`
   listet ALLE explained/-Features inkl. der neuen.
9. **Tooltip am `?`-Button** in `ui/main_window.py:374-383`:
   "Funktionsübersicht — alle Features mit Erklärung" /
   "Feature Overview — all features explained".
10. **README aktualisiert:**
    - Bandpilot in Key Innovations (English + Deutsch).
    - Bandpilot in All Features / Alle Funktionen.
    - Bandpilot in "In Field Test / Im Feldtest".
    - "Detailed Feature Documentation"-Tabelle vollständig
      (alle 16 Features = 11 alt + Bandpilot + 5 neu — 32 Links).
    - Tests-Badge: 563 → 593.
    - Versions-Erwähnungen: v0.86 → v0.87 (auch in Architektur-Block).
    - Gleiches in `README_DE.md` (eigene deutsche Datei, 379 Zeilen).
11. **Tests grün:** vorhandene 593 + ggf. minimal Smoke-Tests bleiben grün.
12. **Push auf GitHub** nach Abschluss (Mike hat Push für diesen
    Workflow explizit eingeschlossen).

## Betroffene Module / Dateien

### Doku-Operations:

| Action | Pfad | Notiz |
|---|---|---|
| Move/Rename | `docs/bandpilot_help_de.md` → `docs/explained/bandpilot_de.md` | Suffix-Norm |
| Move/Rename | `docs/bandpilot_help_en.md` → `docs/explained/bandpilot.md` | Suffix-Norm |
| Migrate | `docs/POWER_REGULATION_DE.md` → `docs/explained/power-regulation_de.md` | Verlinkungen anpassen |
| Migrate | `docs/POWER_REGULATION.md` → `docs/explained/power-regulation.md` | Verlinkungen anpassen |
| Migrate | `docs/FREQUENCY_HISTOGRAM_DE.md` → `docs/explained/cq-frequency_de.md` | Umbenennen + Inhalt |
| Migrate | `docs/FREQUENCY_HISTOGRAM.md` → `docs/explained/cq-frequency.md` | Umbenennen + Inhalt |
| Migrate | `docs/DX_TUNING_DE.md` → `docs/explained/dx-tuning_de.md` | Verlinkungen anpassen |
| Migrate | `docs/DX_TUNING.md` → `docs/explained/dx-tuning.md` | Verlinkungen anpassen |
| Delete (nach Inhaltsvergleich) | `docs/DIVERSITY_DE/EN.md` | Pendant in explained/ |
| Delete (nach Inhaltsvergleich) | `docs/DT_CORRECTION_DE/EN.md` | Pendant in explained/ |
| Update | `docs/explained/diversity-modes.md` (EN) | DE-Inhalts-Stand |
| Create new | `docs/explained/antenna-preference_de.md` + `.md` | ~80-120 Z. pro Datei |
| Create new | `docs/explained/waitlist_de.md` + `.md` | ~80-120 Z. |
| Create new | `docs/explained/direction-map_de.md` + `.md` | ~120-180 Z. |
| Create new | `docs/explained/locator-mining_de.md` + `.md` | ~80-120 Z. |
| Create new | `docs/explained/auto-hunt_de.md` + `.md` | ~80-120 Z. |
| Keep private | `docs/OMNI_TX_DESIGN.md` | bleibt internal — NICHT auf GitHub |
| Keep | `docs/SESSION_WORKFLOW.md`, `WORKFLOW.md` | interne Workflows |
| Optional Delete | `docs/TIMING_BUG_TESTPLAN_2026-05-01.md` | temporär abgehakt |

### App-Code:

- `ui/help_dialog.py:12-24` — `_FEATURES` erweitern um Bandpilot + 5
  neue + power-regulation + cq-frequency + dx-tuning. Achtung Naming:
  Help-Dialog erwartet `<base>_de.md` für DE und `<base>.md` für EN.
- `ui/main_window.py:374-383` — `_help_btn.setToolTip(...)` ergänzen
  (DE+EN bilingual oder via settings.language).
- `ui/settings_dialog.py:_show_bandpilot_help()` (~Zeile 343-358) —
  Pfad-Konstante anpassen auf neue Datei `bandpilot_de.md` /
  `bandpilot.md`.

### README:

- `README.md` — bilingual mit Anker-Sprung. Bandpilot + Doc-Tabelle +
  Version + Tests-Badge. **Beide Sprachen-Sektionen anfassen.**
- `README_DE.md` (379 Zeilen, eigene Datei) — gleiche Updates wie
  `README.md`.

## Randbedingungen

- **Hardware-Pflicht (CLAUDE.md):** ANT1=TX immer, ANT2=nur RX. In
  allen Doku-Files die TX-Funktionalität erwähnen (Auto-Hunt, OMNI,
  Bandpilot wo Diversity-Switch passiert) explizit.
- **Naming-Konvention:** kebab-case für alle neuen Doku-Files.
  `_de.md` für DE, `.md` (kein `_en` Suffix) für EN.
- **OMNI_TX_DESIGN.md privat:** bleibt im docs/, **darf NICHT** auf
  GitHub erwähnt werden außer als High-Level-Feature in README.
  Existing `omni-tx_de.md` + `.md` in explained/ bleiben (User-Doku).
- **App muss laufen:** keine breaking changes an Decoder, Encoder,
  QSO-State, Diversity. Nur UI-Strings + Pfade.
- **Tests bleiben 593+ grün** nach jedem Schritt.
- **Settings-Dialog Pfad:** wenn Bandpilot nach `explained/` verschoben
  wird, muss `_show_bandpilot_help()` sofort den neuen Pfad nutzen,
  sonst broken Help-Dialog beim ?-Klick im Settings.
- **Test-Cases für Help-Dialog:** falls vorhanden, Smoke-Test prüfen,
  sonst minimal-Test ergänzen ("alle in `_FEATURES` referenzierten
  Doku-Files existieren").
- **Atomare Commits:** ein Commit pro logischer Einheit (Migration,
  neue Doku, App-Updates, README-Update).
- **Push:** am Ende, bei grünen Tests, in einem Commit-Block.

## Nicht im Scope

- Inhaltliche Erweiterung der existierenden 11 explained/-Files (nur
  EN-Update bei diversity-modes wenn Diff > 25%).
- Code-Refactor jenseits der drei UI-Dateien.
- Neue Features (Bandpilot war v0.87 gestern — heute nur Doku).
- OMNI-TX-Design-Dokument auf GitHub veröffentlichen.
- Inhaltliches Bearbeiten von `docs/SESSION_WORKFLOW.md` /
  `WORKFLOW.md` (interne Prozesse, separat).
- Übersetzung der internen Workflow-Files DE→EN.
- Versionsbump auf v0.88 — das ist reines Doku-Refactoring.

## Testbarkeit

- **Doku-Existenz-Skript:** `bash`-Loop iteriert `_FEATURES` aus
  help_dialog.py und prüft `<base>_de.md` + `<base>.md` in
  `docs/explained/`. Ein Failed-Path stoppt den Push.
- **Help-Dialog Smoke-Test:** existing oder neuer Test in
  `tests/test_help_dialog_smoke.py` — alle Features lassen sich
  selektieren, Markdown wird angezeigt (kein "Dokument noch nicht
  vorhanden").
- **Settings-Dialog Bandpilot-Hilfe:** Test öffnet
  `_show_bandpilot_help`, prüft dass die neue Datei geladen wird.
- **README Link-Check (manuell):** Alle `docs/explained/*.md`-Links
  in README + README_DE auflösbar.
- **DE/EN-Linecount-Check:** schnelles `wc -l`-Diff pro Doku-Paar,
  Diff < 25% (manuell visuell).
- **Pytest 593+ grün** unverändert nach jedem Commit.

## Workflow für Doku-Erstellung (intern)

Pro neue Doku-Datei (5 Features × DE+EN = 10 Files):

1. DeepSeek-R1 als Author: kompakter Draft (~80-120 Zeilen)
   basierend auf Code-Verifikation der referenzierten Module.
2. Claude reviewed Inhalt: Klarheit, Hobby-Funker-Zielgruppe (KISS),
   keine Contest-Sprache, Hardware-Pflichten korrekt.
3. Mike erhält Liste der erstellten Files am Ende, KEINE Pro-File-
   Freigabe (Mike's "autonom"-Anweisung).

## Reihenfolge der Implementierung

1. Schritt-0-Check Inhalt: `DIVERSITY_DE` vs `diversity-modes_de`,
   `DT_CORRECTION_DE` vs `dt-correction_de` (sind sie wirklich
   redundant?) → Entscheidung Löschen vs Mergen.
2. Migration: Bandpilot + POWER + FREQUENCY + DX_TUNING nach
   explained/.
3. EN-Update: `diversity-modes.md` auf DE-Stand.
4. Lösch-Op: redundante alte Docs.
5. Neue Docs: 5 × DE+EN — DeepSeek drafted, Claude reviewt.
6. Help-Dialog erweitern, Tooltip ergänzen, Settings-Pfad anpassen.
7. README + README_DE: Bandpilot, Doc-Tabelle, Version, Badge.
8. Tests grün halten.
9. Final-R1-Review aller geänderten Files.
10. Atomare Commits, Push.
11. HISTORY + HANDOFF + CLAUDE + Memory updaten.
