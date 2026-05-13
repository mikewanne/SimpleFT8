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

# Doku-Konsolidierung SimpleFT8 — Prompt V2

## Kontext (kurz)

SimpleFT8 ist ein FT8/FT4/FT2-Client für FlexRadio (DA1MHH/Mike,
Hobby-Tool). Heute v0.87 nach gestrigem Bandpilot-Feature, 593 Tests grün.
Doku-Layout ist gewachsen-chaotisch:
- `docs/` enthält 16 Files (alte UPPER_SNAKE_CASE-Doks + interne
  Workflow-Files + die neuen Bandpilot-Files).
- `docs/explained/` enthält 22 Files (11 Features × DE+EN, kebab-case).
- App `?`-Button öffnet `ui/help_dialog.py` mit Liste aus 11 Features
  (Bandpilot fehlt) — liest `docs/explained/<base>_de.md` (DE) bzw.
  `<base>.md` (EN).
- README + README_DE haben unvollständige Doc-Tabelle (5 von 11
  Features verlinkt) und Bandpilot fehlt komplett.
- Versions-Daten outdated (v0.86, 563 Tests in Badge).

Mike's Ziel: einmal aufräumen, einheitlich, alle Features dokumentiert,
App + GitHub aus EINER Doku-Quelle, Push.

## Ziel

Single Source of Truth für jede Feature-Dokumentation in
`docs/explained/<feat>_de.md` + `<feat>.md`. App-Help-Dialog und
GitHub-README beziehen Inhalt aus diesem Ordner. Alle 16 echten
User-Features sind dokumentiert (DE+EN), App + README synchron, Push.

## Akzeptanzkriterien

1. **Single Source of Truth:** Jedes User-Feature hat genau zwei Files
   in `docs/explained/`: `<feat>_de.md` (Deutsch), `<feat>.md` (Englisch).
   Keine Doku-Duplikate in `docs/`.

2. **Naming-Konvention strikt:** kebab-case, `_de.md`-Suffix für DE,
   keine Suffix (`.md`) für EN. Wie der bisherige `docs/explained/`-Standard.

3. **Bandpilot vollständig integriert:**
   - Files verschoben+umbenannt:
     `docs/bandpilot_help_de.md` → `docs/explained/bandpilot_de.md`
     `docs/bandpilot_help_en.md` → `docs/explained/bandpilot.md`
     (Inhalt 1:1 übernehmen, Field-Test-Hinweis ergänzen).
   - In `_FEATURES` (`ui/help_dialog.py:12-24`) eingefügt — Position
     direkt nach Diversity, weil semantisch verwandt.
   - In `ui/settings_dialog.py:_show_bandpilot_help()` (~Zeile 343-358):
     Konstante umstellen auf `bandpilot_de.md` / `bandpilot.md`.
   - In README und README_DE: Bandpilot in "Key Innovations / Wichtige
     Innovationen", in "All Features / Alle Funktionen", in "In Field
     Test / Im Feldtest", in "Detailed Feature Documentation"-Tabelle.

4. **Migration aus `docs/` nach `docs/explained/`:**
   | Quelle | Ziel |
   |---|---|
   | `POWER_REGULATION_DE.md` | `power-regulation_de.md` |
   | `POWER_REGULATION.md` | `power-regulation.md` |
   | `FREQUENCY_HISTOGRAM_DE.md` | `cq-frequency_de.md` |
   | `FREQUENCY_HISTOGRAM.md` | `cq-frequency.md` |
   | `DX_TUNING_DE.md` | `dx-tuning_de.md` |
   | `DX_TUNING.md` | `dx-tuning.md` |

   **Hinweis Naming-Konflikt zur Klärung:** `docs/explained/`
   enthält bereits `gain-measurement_de.md` + `.md` mit dem
   Display-Namen "Gain-Messung (DX Tuning)". Beim Migrieren von
   `DX_TUNING_DE.md` als `dx-tuning_de.md` muss klar werden, dass
   `gain-measurement` und `dx-tuning` ZWEI Features sind:
   - `gain-measurement`: Audio-Eingangspegel-Kalibrierung mit
     "GAIN-MESSUNG"-Button (RMS-Audio-Pegel finden).
   - `dx-tuning`: 4.5-Min-18-Zyklus-Antennen-Vergleichsmessung mit
     Preset-Speicherung pro Band+FT-Mode.

   Ergebnis: Display-Name `gain-measurement` ändern zu
   "Gain-Messung (Audio-Pegel)" und neues Feature `dx-tuning` als
   "DX-Tuning (Antennen-Messung)" in `_FEATURES` aufnehmen.

5. **Lösch-Kandidaten — Inhalts-Vergleich vor Löschung:**
   - `DIVERSITY_DE/EN.md` vs `diversity-modes_de.md` + `.md`
   - `DT_CORRECTION_DE/EN.md` vs `dt-correction_de.md` + `.md`

   Vorgehen: Inhalt der alten Datei lesen, prüfen ob ALLE Konzepte
   in der neuen Datei abgedeckt sind. Wenn ja → `git rm` der alten.
   Wenn nein → einzigartige Passagen in die neue mergen, dann löschen.

6. **Neue Doku-Files (DE+EN, 5 Features × 2 = 10 Files):**

   | Feature | Slug | Erwartete Größe |
   |---|---|---|
   | Pro-Station Antennen-Präferenz | `antenna-preference` | 80-120 Z. |
   | Caller Waitlist | `waitlist` | 80-120 Z. |
   | 3D-Globus Richtungs-Karte | `direction-map` | 150-200 Z. |
   | Live Locator Mining | `locator-mining` | 80-120 Z. |
   | Auto-Hunt | `auto-hunt` | 80-120 Z. |

   Inhalt pro Datei (Hobby-Funker-Zielgruppe, KISS):
   - "Was macht das Feature?" (1-2 Absätze)
   - "Wie funktioniert es?" (technisch, 2-4 Absätze)
   - "Wann ist es nützlich?" (Use-Cases)
   - "Wo finde ich es?" (UI-Position / Aktivierung)
   - **Hardware-Pflicht** wo TX im Spiel: ANT1=TX, ANT2=nur RX explicit.

   Workflow für Drafts: Claude liest Code (`Read`/`Grep`), schreibt
   kompakten Draft (KISS), Mike erhält am Ende die Liste — KEINE
   Pro-File-Mike-Freigabe (Mike's "autonom"-Anweisung).

7. **DE/EN-Konsistenz:**
   - `docs/explained/diversity-modes.md` (EN, 106 Zeilen) auf
     DE-Stand bringen (159 Zeilen). DE-Datei wurde aktualisiert,
     EN ist hinterher.
   - Übrige Pendants: schneller `wc -l`-Diff-Check, bei Diff > 25%
     auf gleichen Stand bringen.

8. **Help-Dialog erweitert** in `ui/help_dialog.py:12-24`:
   - `_FEATURES` listet alle 16 Features inkl.:
     - Existing: QSO-Flow, Gain-Messung (Audio-Pegel),
       Diversity-Modi, FT2, DT-Korrektur, Signal-Processing, Logbuch,
       AP-Lite, Propagation, Operator-Praesenz, OMNI-TX
     - Neu: Bandpilot, Antennen-Praeferenz, Waitlist, Direction-Map,
       Locator-Mining, Auto-Hunt, DX-Tuning, Power-Regulation,
       CQ-Frequenz
   - Reihenfolge logisch: Operations-Features zuerst (QSO-Flow,
     CQ-Frequenz, Waitlist, Auto-Hunt, RR73), dann Antennen
     (Diversity, Antennen-Pref, DX-Tuning, Bandpilot, OMNI-TX),
     dann Decoder/Karten (Signal, AP-Lite, FT2, Direction-Map,
     Locator-Mining), dann Sonstiges (Power-Regulation, DT, Propagation,
     Operator-Praesenz, Logbuch).

9. **Tooltip am `?`-Button** in `ui/main_window.py:374-383`:
   `_help_btn.setToolTip("Funktionsuebersicht — alle Features mit Erklaerung\nFeature Overview — all features explained")`
   (statisch bilingual, kein Lang-Switch — Tooltip wird nur beim
   Hover gerendert, ändert sich nicht zur Laufzeit).

10. **README-Updates (BEIDE Sprachen):**

    `README.md` (bilingual mit Anker-Sprung — KEIN externes
    `README_DE.md`-Verweis erwartet) UND `README_DE.md` (eigene Datei,
    379 Zeilen).

    Verifikations-Pflicht in V3: prüfen ob `README_DE.md` aktiv genutzt
    wird (Verlinkung von `README.md` aus oder von GitHub-Default).

    Inhalt:
    - Bandpilot in "Key Innovations / Wichtige Innovationen" mit
      Kurzbeschreibung (3-5 Sätze).
    - Bandpilot in "All Features / Alle Funktionen" Liste, Position
      nach Dual-Mode Diversity.
    - Bandpilot mit `⚠️` in "In Field Test / Im Feldtest" Sektion.
    - "Detailed Feature Documentation"-Tabelle vollständig: alle 16
      Features mit DE+EN-Links auf `docs/explained/<slug>{_de}.md`.
    - Tests-Badge: `563` → `593`.
    - Versions-Erwähnungen `(v0.86)` → `(v0.87)` durchgehend.
    - Architektur-Block: `563 unit tests` → `593 unit tests`.

11. **Test-Anpassung:**
    - **Neuer pytest-Test** `tests/test_help_dialog_features.py`:
      Iteriert `_FEATURES` aus help_dialog.py, prüft für jedes Feature
      dass `docs/explained/<base>_de.md` UND `<base>.md` existieren.
      Fail wenn nicht.
    - Existing `test_settings_dialog_smoke.py:test_bandpilot_save_round_trip`
      bleibt grün (Pfad-Update in `_show_bandpilot_help` ist Read-Pfad,
      nicht Save).
    - Existing 593 Tests bleiben unverändert grün.

12. **OMNI-TX-Privatstatus:**
    Existing `omni-tx_de.md` + `.md` in `explained/` beschreibt das
    Feature — die Aktivierungs-Methode (Klick auf Versionsnummer)
    darf NICHT in der Doku stehen. Vor Migration: existierende
    `omni-tx`-Files prüfen, ggf. säubern. `docs/OMNI_TX_DESIGN.md`
    bleibt PRIVAT, wird NICHT auf GitHub erwähnt.

13. **Implementierungs-Reihenfolge (kritisch — Verlinkungs-Risiko):**

    1. **Phase 1 — Vorbereitung:** Inhalts-Vergleich `DIVERSITY_DE`
       vs `diversity-modes_de` + `DT_CORRECTION_DE` vs `dt-correction_de`
       (Schritt-0-Verifikation).
    2. **Phase 2 — Migrationen:** alte Files nach `explained/`
       verschieben/umbenennen (Bandpilot, Power-Regulation,
       CQ-Frequenz, DX-Tuning). 4 atomare git-Commits.
    3. **Phase 3 — EN-Update diversity-modes:** EN-Variante an
       DE-Stand anpassen.
    4. **Phase 4 — Lösch-Op alte Redundanzen:** `git rm` für
       DIVERSITY*, DT_CORRECTION*. Atomarer Commit.
    5. **Phase 5 — Neue Docs:** 5 × DE+EN Drafts. Pro Feature ein
       Commit (10 Files, 5 Commits — atomar).
    6. **Phase 6 — App-Code:** help_dialog._FEATURES erweitern,
       main_window Tooltip, settings_dialog-Pfad. Ein Commit oder
       zwei atomare.
    7. **Phase 7 — Tests:** neuer Test `test_help_dialog_features.py`,
       full pytest-Run, grün-Verifikation.
    8. **Phase 8 — README-Update (DE+EN):** Bandpilot, Doc-Tabelle,
       Version, Badge. Ein oder zwei Commits.
    9. **Phase 9 — Final-R1-Codereview:** alle App-Code-Änderungen
       + neuer Test gegen DeepSeek-R1.
    10. **Phase 10 — Push:** atomare Commits sind durch, jetzt
       `git push origin main`.
    11. **Phase 11 — HISTORY/HANDOFF/CLAUDE/Memory:**
        - HISTORY.md: neuer Eintrag `## 2026-05-02 v0.87.1 — Doku-Konsolidierung`
        - HANDOFF.md (beide Pfade): Stand + Test-Count.
        - CLAUDE.md (beide Pfade): "Aktueller Stand"-Header.
        - Memory: Lesson "Single-Source-Doku-Refactor: erst migrieren,
          dann lückenfüllen, dann Code, dann README, dann Push".

## Betroffene Module / Dateien (vollständige Liste)

### Doku-Files

**Verschieben/Umbenennen (in `git`):**
- `docs/bandpilot_help_de.md` → `docs/explained/bandpilot_de.md`
- `docs/bandpilot_help_en.md` → `docs/explained/bandpilot.md`
- `docs/POWER_REGULATION_DE.md` → `docs/explained/power-regulation_de.md`
- `docs/POWER_REGULATION.md` → `docs/explained/power-regulation.md`
- `docs/FREQUENCY_HISTOGRAM_DE.md` → `docs/explained/cq-frequency_de.md`
- `docs/FREQUENCY_HISTOGRAM.md` → `docs/explained/cq-frequency.md`
- `docs/DX_TUNING_DE.md` → `docs/explained/dx-tuning_de.md`
- `docs/DX_TUNING.md` → `docs/explained/dx-tuning.md`

**Migrierter Inhalt:** Cross-Links innerhalb der migrierten Files
auf neue Pfade umbiegen (Beispiel: `[Diversity](DIVERSITY_DE.md)` →
`[Diversity](diversity-modes_de.md)`).

**Löschen (nach Inhalts-Vergleich-OK):**
- `docs/DIVERSITY_DE.md`
- `docs/DIVERSITY.md`
- `docs/DT_CORRECTION_DE.md`
- `docs/DT_CORRECTION.md`

**Neu erstellen:**
- `docs/explained/antenna-preference_de.md` + `.md`
- `docs/explained/waitlist_de.md` + `.md`
- `docs/explained/direction-map_de.md` + `.md`
- `docs/explained/locator-mining_de.md` + `.md`
- `docs/explained/auto-hunt_de.md` + `.md`

**Updaten (Inhalt):**
- `docs/explained/diversity-modes.md` (EN auf DE-Stand)

**Bleiben unverändert (privat/internal):**
- `docs/OMNI_TX_DESIGN.md`
- `docs/SESSION_WORKFLOW.md`
- `docs/WORKFLOW.md`
- `docs/TIMING_BUG_TESTPLAN_2026-05-01.md`

### App-Code

- `ui/help_dialog.py:12-24` — `_FEATURES` Liste erweitern.
- `ui/main_window.py:374-383` — `setToolTip` ergänzen.
- `ui/settings_dialog.py:_show_bandpilot_help()` (~Z. 343-358) —
  Pfad-Konstante: `bandpilot_help_de.md` → `bandpilot_de.md`,
  `bandpilot_help_en.md` → `bandpilot.md`.

### Tests

- Neu: `tests/test_help_dialog_features.py` — File-Existenz-Check.

### README

- `README.md` (bilingual)
- `README_DE.md` (separat)

### Doku-Updates Trail

- `HISTORY.md` (Append)
- `HANDOFF.md` (BEIDE Pfade)
- `CLAUDE.md` (BEIDE Pfade)
- Memory: neuer Eintrag

## Randbedingungen

- **Hardware-Pflicht (CLAUDE.md):** ANT1=TX immer, ANT2=nur RX.
  Wo TX/Auto-Hunt/OMNI/Bandpilot in Doku erwähnt: explizit.
- **Naming:** kebab-case + `_de.md` / `.md`. Keine Abweichung.
- **OMNI_TX_DESIGN.md privat:** bleibt im docs/, **darf NICHT** auf
  GitHub erwähnt werden. `omni-tx_de.md` + `.md` in explained/ bleiben
  als User-Doku, OHNE Aktivierungs-Hinweis (Versionsnummer-Klick).
- **App muss laufen** durchgehend: keine breaking changes an Decoder,
  Encoder, QSO-State. Nur UI-Strings + Pfade.
- **Tests bleiben 593+ grün** nach jedem Commit. Neuer Test bringt
  +1 (mit mehreren Asserts via parametrize).
- **Settings-Dialog Pfad-Update SOFORT:** wenn Bandpilot nach
  `explained/` verschoben wird, muss `_show_bandpilot_help()` im
  selben Commit den neuen Pfad nutzen — sonst broken Help-Dialog
  beim ?-Klick.
- **Atomare Commits:** ein Commit pro logischer Einheit.
- **Push:** am Ende, nach Final-R1-Review, in einem Block.

## Nicht im Scope

- Inhaltliche Erweiterung der existierenden 11 explained/-Files
  (außer EN-Update bei diversity-modes wo Diff > 25%).
- Code-Refactor jenseits der drei UI-Dateien.
- Neue Features (Bandpilot war v0.87 gestern — heute reines Doku-Refactoring).
- OMNI-TX-Design-Dokument auf GitHub veröffentlichen.
- Inhaltliches Bearbeiten von `docs/SESSION_WORKFLOW.md` /
  `WORKFLOW.md` (interne Prozesse).
- Übersetzung der internen Workflow-Files DE→EN.
- Versionsbump auf v0.88 — das ist reines Doku-Refactoring,
  Patch-Version v0.87.1 reicht (oder unverändert v0.87, da nur Doku).
- Tooltip-Internationalisierung über Settings (statischer
  bilingualer String reicht).

## Testbarkeit

- **`tests/test_help_dialog_features.py`:** parametrisierter Test
  iteriert `_FEATURES`, prüft Existenz beider Doku-Files.
- **`test_settings_dialog_smoke.py`:** existierende Bandpilot-Tests
  bleiben grün (Pfad-Read-Operation in `_show_bandpilot_help`).
- **README Link-Check (manuell):** Alle `docs/explained/*.md`-Links
  in beiden README-Files auflösbar.
- **DE/EN-Linecount-Check (manuell):** schneller `wc -l`-Diff pro
  Doku-Paar.
- **Pytest-Run gesamt:** 593 → 594+ grün.
- **App-Smoke:** App startet, `?`-Button öffnet Hilfe-Dialog mit
  vollständiger Feature-Liste, Tooltip beim Hover sichtbar.

## Erwartete Findings (Self-Reflection für DeepSeek)

DeepSeek soll insbesondere prüfen:

1. **DX-Tuning vs gain-measurement:** Ist die Aufspaltung in zwei
   Features korrekt oder Über-Engineering? Code-Pfade in
   `core/diversity.py`, `ui/dx_tune_dialog.py` sind Referenz.
2. **README-Bilingual vs README_DE.md:** Welche Datei wird von der
   GitHub-Hauptseite verlinkt? Doppelpflege riskant.
3. **Feature-Reihenfolge in `_FEATURES`:** logische Gruppierung
   plausibel, oder einfach alphabetisch besser?
4. **Lösch-Kriterium DIVERSITY/DT_CORRECTION:** "Inhalt komplett in
   neuer Datei?" — wer entscheidet das? Klare Heuristik fehlt.
5. **Direction-Map Doku-Größe:** 150-200 Zeilen realistisch oder zu
   ambitioniert? Komplexität von 3D-Globus + Sektoren + Themes
   rechtfertigt es.
6. **Workflow-Skip pro Doku-Datei:** Mike hat "autonom" gesagt — pro
   Doku ein V1→V2→R1 wäre Over-Engineering, ein einziger V1→V2→R1
   für die Konsolidierung reicht. KISS-validiert?

## Files für DeepSeek mitsenden

- `ui/help_dialog.py` (Feature-Liste-Quelle)
- `ui/main_window.py` (?-Button)
- `ui/settings_dialog.py` (Bandpilot-Hilfe-Pfad)
- `README.md` (Hauptdoku)
- `README_DE.md` (deutsche Hauptdoku)
- `docs/explained/diversity-modes_de.md` (DE-Stand für EN-Update)
- `docs/explained/diversity-modes.md` (EN-veraltet)
- `docs/explained/bandpilot_de.md`-existing (heißt aktuell
  `docs/bandpilot_help_de.md` — als Beispiel-Inhalt)
- `docs/POWER_REGULATION_DE.md` (Beispiel Migrations-Quelle)
- `docs/FREQUENCY_HISTOGRAM_DE.md` (Beispiel Migrations-Quelle)
- `docs/DX_TUNING_DE.md` (Beispiel Migrations-Quelle)
- `docs/DIVERSITY_DE.md` (Lösch-Kandidat)
- `docs/DT_CORRECTION_DE.md` (Lösch-Kandidat)
