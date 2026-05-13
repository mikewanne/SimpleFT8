# Doku-Konsolidierung SimpleFT8 — V3 (final, mit R1-Findings)

## R1-Findings-Verarbeitung

| # | Finding (R1) | Status | Begründung |
|---|---|---|---|
| 1 | Feature-Zähl-Bug 16 vs 20 | **angenommen** | Korrekt — 11+9=20 Features, 40 Files |
| 2 | RR73 fehlt in `_FEATURES` | **teilweise angenommen** | RR73 ist Sub-Feature von QSO-Flow → aus Reihenfolge gestrichen, KEIN eigenes Feature |
| 3 | Lösch-Heuristik fehlt | **angenommen** | "Alle Konzepte der alten Datei in neuer abgedeckt" — manueller Diff vor Löschung |
| 4 | README_DE.md Doppelpflege | **angenommen+korrigiert** | Verifikation ergab: README_DE.md nicht aus README.md verlinkt, nicht GitHub-Default → AUS SCOPE. Nur `README.md` (bilingual) pflegen |
| 5 | omni-tx Widerspruch | **angenommen+verifiziert** | Code-Check: Z.56 in beiden omni-tx-Files enthält Aktivierungs-Methode → MUSS Phase 0 entfernt werden |
| 6 | Alphabetische `_FEATURES` | **angenommen** | KISS — Sortierung nach Anzeige-Name |
| 7 | direction-map zu groß | **angenommen** | 100-130 Z. statt 150-200 |
| 8 | Tooltip kürzer | **abgelehnt** | Mike wollte explizit "Funktionsuebersicht" — bleibt informativ |
| 9 | Phase 11 Memory entfernen | **abgelehnt** | ft8_workflow Schritt 6 fordert Memory bei Lessons |
| 10 | Bandpilot Key Innov knapp | **angenommen** | 1-2 Sätze, Details in Doku |
| 11 | Gain-Measurement Klarstellung | **angenommen** | Explizit erwähnt |
| 12 | Cross-Links in explained/ prüfen | **verifiziert** | Code-Grep: keine Treffer, kein Issue |
| 13 | Doppelter Zählfehler 22 vs 40 | **angenommen** | konsistent korrigiert |

## Ziel

Single Source of Truth für jede Feature-Dokumentation in
`docs/explained/<feat>_de.md` + `<feat>.md`. App-Help-Dialog und
GitHub-README beziehen Inhalt aus diesem Ordner. **20 echte
User-Features** sind dokumentiert (DE+EN = 40 Files). App-Help-Dialog
und `README.md` (bilingual) synchron, GitHub-Push.

## Akzeptanzkriterien (final)

1. **Single Source of Truth:** Jedes der 20 User-Features hat genau
   zwei Doku-Dateien in `docs/explained/`: `<feat>_de.md` + `<feat>.md`.
   Keine Doku-Duplikate in `docs/`.

2. **Naming-Konvention:** kebab-case, `_de.md`-Suffix für DE,
   ohne Suffix (`.md`) für EN.

3. **Bandpilot vollständig integriert:**
   - Verschoben+umbenannt:
     `docs/bandpilot_help_de.md` → `docs/explained/bandpilot_de.md`
     `docs/bandpilot_help_en.md` → `docs/explained/bandpilot.md`
     (Inhalt 1:1, ein Hinweis-Block "Im Feldtest" am Anfang ergänzen).
   - In alphabetisch sortierter `_FEATURES`-Liste in
     `ui/help_dialog.py:12-24`.
   - In `ui/settings_dialog.py:_show_bandpilot_help()` (~Z. 343-358):
     Pfad-Konstante umstellen auf `bandpilot_de.md` / `bandpilot.md`.
   - In `README.md` (bilingual): kurze Erwähnung in Key Innovations
     (1-2 Sätze), in All Features Liste, in In Field Test, in
     Detailed Feature Documentation Tabelle.

4. **Migration aus `docs/` nach `docs/explained/`:**
   | Quelle | Ziel |
   |---|---|
   | `POWER_REGULATION_DE/EN.md` | `power-regulation_de.md` + `.md` |
   | `FREQUENCY_HISTOGRAM_DE/EN.md` | `cq-frequency_de.md` + `.md` |
   | `DX_TUNING_DE/EN.md` | `dx-tuning_de.md` + `.md` |

   **Klarstellung Naming-Konflikt:**
   - `gain-measurement` (existing in explained/) bleibt — beschreibt
     Audio-Eingangspegel-Kalibrierung mit "GAIN-MESSUNG"-Button.
     KEINE Migration, KEIN Mapping.
   - `dx-tuning` (NEU in explained/) — beschreibt 4.5-Min-18-Zyklus-
     Antennen-Vergleichsmessung mit Preset-Speicherung pro Band+
     FT-Mode.
   - In `_FEATURES` Display-Namen: "Gain-Messung (Audio-Pegel)" und
     "DX-Tuning (Antennen-Messung)" — klare Abgrenzung.

5. **Lösch-Heuristik (R1 Finding 3):**
   Vor `git rm`: Alte Datei vollständig lesen, neue Pendant-Datei
   vollständig lesen, dann prüfen: "Sind alle Konzepte/Sektionen der
   alten Datei sinnvoll in der neuen abgedeckt?" — Stichprobe für
   jede Sektion der alten Datei.
   - Wenn ja (≥90% Konzept-Abdeckung) → `git rm` der alten.
   - Wenn nein → einzigartige Sektionen aus der alten in die neue
     mergen, dann `git rm`.

   **Lösch-Kandidaten:**
   - `docs/DIVERSITY_DE.md` + `DIVERSITY.md` (Pendant
     `docs/explained/diversity-modes_de.md` + `.md`)
   - `docs/DT_CORRECTION_DE.md` + `DT_CORRECTION.md` (Pendant
     `docs/explained/dt-correction_de.md` + `.md`)

6. **Neue Doku-Files (DE+EN, 5 Features × 2 = 10 Files):**

   | Feature | Slug | Display-Name DE | Display-Name EN | Größe |
   |---|---|---|---|---|
   | Pro-Station Antennen-Pref | `antenna-preference` | "Antennen-Praeferenz pro Station" | "Per-Station Antenna Preference" | 80-120 Z. |
   | Caller Waitlist | `waitlist` | "Anrufer-Warteliste" | "Caller Waitlist" | 80-120 Z. |
   | 3D-Globus Karte | `direction-map` | "Richtungs-Karte (3D-Globus)" | "Direction Map (3D Globe)" | 100-130 Z. |
   | Live Locator-DB | `locator-mining` | "Live Locator-DB" | "Live Locator Mining" | 80-120 Z. |
   | Auto-Hunt | `auto-hunt` | "Auto-Hunt" | "Auto-Hunt" | 80-120 Z. |

   Inhaltsstruktur jeder Datei (Hobby-Funker-Zielgruppe, KISS):
   - "Was macht das Feature?" (1-2 Absätze)
   - "Wie funktioniert es?" (technisch, 2-4 Absätze)
   - "Wann nützlich?" (Use-Cases)
   - "Wo zu finden?" (UI-Position / Aktivierung)
   - **Hardware-Pflicht** wo TX (Auto-Hunt!): ANT1=TX, ANT2=nur RX
     explizit.

   Workflow: Claude liest betroffene Code-Module (`Read`/`Grep`),
   schreibt kompakten Draft, kein Pro-File-Mike-Approval (Mike's
   "autonom"-Anweisung).

7. **DE/EN-Konsistenz:**
   - `docs/explained/diversity-modes.md` (EN, 106 Z.) auf DE-Stand
     bringen (159 Z.). Inhalt aus DE-Datei sinngemäß übersetzen.
   - Übrige 10 Pendants: schneller `wc -l`-Diff, bei Diff > 25%
     nachziehen.

8. **`_FEATURES` (alphabetisch sortiert nach Display-Name DE):**

   ```
   "Anrufer-Warteliste"             → waitlist
   "Antennen-Praeferenz pro Station" → antenna-preference
   "AP-Lite Rettung"                → ap-lite
   "Auto-Hunt"                      → auto-hunt
   "Bandpilot"                      → bandpilot
   "CQ-Frequenz (Histogramm)"       → cq-frequency
   "Diversity-Modi (Standard/DX)"   → diversity-modes
   "DT-Zeitkorrektur"               → dt-correction
   "DX-Tuning (Antennen-Messung)"   → dx-tuning
   "FT2-Modus (Decodium)"           → ft2-mode
   "Gain-Messung (Audio-Pegel)"     → gain-measurement
   "Logbuch & QRZ"                  → logbook
   "Live Locator-DB"                → locator-mining
   "OMNI-TX (Slot-Rotation)"        → omni-tx
   "Operator-Praesenz"              → operator-presence
   "Power-Regulation"               → power-regulation
   "Propagation-Anzeige"            → propagation-indicators
   "QSO-Ablauf (Hunt/CQ)"           → qso-flow
   "Richtungs-Karte (3D-Globus)"    → direction-map
   "Signalverarbeitung"             → signal-processing
   ```
   = 20 Features.

9. **Tooltip am `?`-Button** in `ui/main_window.py:374-383`:
   `_help_btn.setToolTip("Funktionsuebersicht — Feature Overview")`
   (statisch bilingual, kompakt).

10. **README-Update (NUR `README.md` — README_DE.md aus Scope, R1
    Finding 4):**

    `README.md` (bilingual mit Anker `#english` / `#deutsch`):
    - **English Section "Key Innovations":** Bandpilot mit 1-2
      Sätzen ergänzen (knapp). Position nach „Dual-Mode Diversity".
    - **English Section "All Features":** Bandpilot in Liste
      (`✅ Bandpilot — RX-Modus-Empfehlung pro Band aus Statistik`),
      Position nach Dual-Mode Diversity.
    - **English Section "In Field Test":** Bandpilot mit `⚠️`.
    - **English Section "Detailed Feature Documentation":**
      Tabelle vollständig erweitern auf alle 20 Features mit DE+EN-
      Links auf `docs/explained/<slug>{_de}.md`.
    - **Deutsche Sektion (gleiche Anker):** spiegelbildlich gleiche
      Updates. Wichtig: README.md hat zwei Sprachen-Sektionen —
      BEIDE müssen synchron.
    - **Tests-Badge:** `563` → `593`.
    - **Versions-Erwähnungen** `(v0.86)` → `(v0.87)` (auch
      Architektur-Block).
    - **README_DE.md bleibt unverändert** (nicht aktiv).

11. **Test-Anpassung:**
    - **Neuer pytest-Test** `tests/test_help_dialog_features.py`
      mit `@pytest.mark.parametrize`-Iteration über `_FEATURES`,
      prüft `<base>_de.md` UND `<base>.md` existieren in
      `docs/explained/`. Erwartet: 20 Tests grün.
    - Existing 593 Tests bleiben grün.
    - Existing `test_settings_dialog_smoke.py:test_bandpilot_save_round_trip`
      bleibt grün.

12. **OMNI-TX Aktivierungs-Methode aus Doku entfernen (R1 Finding 5,
    Code-verifiziert!):**

    `docs/explained/omni-tx_de.md:56` enthält
    `1. Klick auf die **Versionsnummer** unten rechts im Hauptfenster`
    — DAS MUSS RAUS bevor irgendwas auf GitHub geht.
    Gleiches in `docs/explained/omni-tx.md:56`.
    Vorgehen: Aktivierungs-Sektion durch generische Formulierung
    ersetzen, z.B. „Aktivierung: aktuell deaktiviert (Feldtest
    ausstehend) — Details intern".

13. **Implementierungs-Reihenfolge (Verlinkungs-Risiko-bewusst):**

    1. **Phase 0 — Säubern:** OMNI-TX-Aktivierungs-Methode aus
       `omni-tx_de.md` + `.md` entfernen. Atomarer Commit.
    2. **Phase 1 — Schritt-0-Inhaltsvergleich:**
       `DIVERSITY_DE` vs `diversity-modes_de`,
       `DT_CORRECTION_DE` vs `dt-correction_de`. Entscheidung
       Lösch vs Merge dokumentieren.
    3. **Phase 2 — Migrationen** (Bandpilot, Power, CQ-Freq,
       DX-Tuning): `git mv` bzw. Move + Cross-Link-Update + 4
       atomare Commits.
    4. **Phase 3 — EN-Update** `diversity-modes.md` (EN auf
       DE-Stand). Atomarer Commit.
    5. **Phase 4 — Lösch-Op** `git rm` für DIVERSITY*,
       DT_CORRECTION* (nach Phase 1 Entscheidung).
       Atomarer Commit.
    6. **Phase 5 — Neue Docs** (5 Features × DE+EN): pro Feature
       ein atomarer Commit. Claude drafted, kein Mike-Approval pro
       Datei. 5 Commits.
    7. **Phase 6 — App-Code:** `_FEATURES` alphabetisch erweitern,
       `setToolTip` ergänzen, Settings-Bandpilot-Pfad. 1-3
       atomare Commits.
    8. **Phase 7 — Tests:** neuer
       `test_help_dialog_features.py`, full pytest-Run.
       Atomarer Commit.
    9. **Phase 8 — README-Update:** `README.md` (bilingual) —
       Bandpilot, Tabelle, Version, Badge. Atomarer Commit.
    10. **Phase 9 — Final-R1-Codereview:** alle App-Code-Files +
        neuer Test gegen DeepSeek-R1.
    11. **Phase 10 — `git push origin main`.**
    12. **Phase 11 — HISTORY/HANDOFF/CLAUDE/Memory:**
        - HISTORY.md: `## 2026-05-02 v0.87.1 — Doku-Konsolidierung`
        - HANDOFF.md (BEIDE Pfade): Test-Count 593 → 614 (593+1+20)
        - CLAUDE.md (BEIDE Pfade): Stand-Header.
        - Memory: "single-source-doku-refactor"-Lesson wenn
          überraschend.

## Betroffene Module / Dateien

### Doku-Files

**Verschieben/Umbenennen:**
- `docs/bandpilot_help_de.md` → `docs/explained/bandpilot_de.md`
- `docs/bandpilot_help_en.md` → `docs/explained/bandpilot.md`
- `docs/POWER_REGULATION_DE.md` → `docs/explained/power-regulation_de.md`
- `docs/POWER_REGULATION.md` → `docs/explained/power-regulation.md`
- `docs/FREQUENCY_HISTOGRAM_DE.md` → `docs/explained/cq-frequency_de.md`
- `docs/FREQUENCY_HISTOGRAM.md` → `docs/explained/cq-frequency.md`
- `docs/DX_TUNING_DE.md` → `docs/explained/dx-tuning_de.md`
- `docs/DX_TUNING.md` → `docs/explained/dx-tuning.md`

**Bei Migration:** Cross-Links innerhalb des Dateiinhalts auf
neue Pfade umbiegen (`[Diversity](DIVERSITY_DE.md)` →
`[Diversity-Modi](diversity-modes_de.md)`).

**Säubern (Phase 0):**
- `docs/explained/omni-tx_de.md` (Z. 56 ff. Aktivierungs-Sektion)
- `docs/explained/omni-tx.md` (Z. 56 ff. Aktivierungs-Sektion)

**Löschen (nach Phase 1 Inhaltsvergleich):**
- `docs/DIVERSITY_DE.md` + `DIVERSITY.md`
- `docs/DT_CORRECTION_DE.md` + `DT_CORRECTION.md`

**Neu (5 × 2 = 10 Files):**
- `docs/explained/antenna-preference_de.md` + `.md`
- `docs/explained/waitlist_de.md` + `.md`
- `docs/explained/direction-map_de.md` + `.md`
- `docs/explained/locator-mining_de.md` + `.md`
- `docs/explained/auto-hunt_de.md` + `.md`

**EN-Inhalts-Update:**
- `docs/explained/diversity-modes.md`

**Bleiben unverändert (privat/internal):**
- `docs/OMNI_TX_DESIGN.md`
- `docs/SESSION_WORKFLOW.md`
- `docs/WORKFLOW.md`
- `docs/TIMING_BUG_TESTPLAN_2026-05-01.md`
- `README_DE.md` (nicht aktiv genutzt)

### App-Code

- `ui/help_dialog.py:12-24` — `_FEATURES` alphabetisch (20 Einträge).
- `ui/main_window.py:374-383` — `setToolTip` bilingual.
- `ui/settings_dialog.py` `_show_bandpilot_help()` (~Z. 343-358) —
  Pfad-Konstante: `bandpilot_help_<de|en>.md` →
  `bandpilot_de.md` (DE) / `bandpilot.md` (EN).

### Tests

- Neu: `tests/test_help_dialog_features.py` (parametrisiert).

### README

- `README.md` (bilingual)

### Doku-Trail

- `HISTORY.md` Append
- `HANDOFF.md` BEIDE Pfade
- `CLAUDE.md` BEIDE Pfade
- Memory wenn Lesson

## Randbedingungen

- **Hardware-Pflicht (CLAUDE.md):** ANT1=TX immer, ANT2=nur RX.
  In neuen Doku-Files (Auto-Hunt, Bandpilot-Migration mit
  Diversity-Switch) explizit erwähnen.
- **Naming:** kebab-case + `_de.md` / `.md`. Keine Abweichung.
- **OMNI-Privat:** Aktivierungs-Methode bleibt privat. Phase 0
  säubert die existing Doku.
- **App muss laufen** durchgehend: keine breaking changes an Decoder,
  Encoder, QSO-State.
- **Tests bleiben 593+ grün** nach jedem Commit.
- **Settings-Dialog Pfad-Update SOFORT** wenn Bandpilot verschoben:
  beide Operationen im selben Commit (oder Migration zuerst, dann
  Code-Update direkt).
- **Atomare Commits:** ein Commit pro logischer Einheit, kein
  Mega-Commit.
- **Push:** am Ende, nach Final-R1-Review.
- **README_DE.md außerhalb des Scope:** wird NICHT angefasst.

## Nicht im Scope

- Inhaltliche Erweiterung der existierenden 11 explained/-Files
  (außer EN-Update bei diversity-modes wo Diff > 25%).
- Code-Refactor jenseits der drei UI-Dateien.
- Neue Features (Bandpilot ist v0.87 — heute nur Doku-Refactoring).
- OMNI-TX-Design-Dokument auf GitHub veröffentlichen.
- Inhaltliches Bearbeiten von `docs/SESSION_WORKFLOW.md` /
  `WORKFLOW.md` (interne Prozesse).
- Übersetzung der internen Workflow-Files DE→EN.
- Versionsbump auf v0.88 — bleibt v0.87 (Doku-Refactoring kein
  Feature-Bump).
- README_DE.md aktualisieren — nicht aktiv genutzt (Verifikation:
  nicht aus README.md verlinkt, GitHub-Default ist README.md).
- Tooltip-Internationalisierung über Settings.

## Testbarkeit

- **`tests/test_help_dialog_features.py`:** parametrisiert über
  `_FEATURES`, prüft Existenz beider Doku-Files in `docs/explained/`.
  20 Test-Cases (für 20 Features).
- **Existing Tests** bleiben grün (593 → 593 + 20 = ~613).
- **App-Smoke (manuell):** App startet, `?`-Button öffnet
  Hilfe-Dialog mit 20 Features alphabetisch sortiert, Tooltip beim
  Hover sichtbar.
- **README Link-Check (manuell):** alle `docs/explained/*.md`-Links
  in `README.md` auflösbar (auch in englischer + deutscher Sektion).

## Final-R1-Codereview-Scope (Phase 9)

DeepSeek-R1 prüft am Ende vor Push:
- `ui/help_dialog.py` (alphabetische Liste OK?)
- `ui/main_window.py` (Tooltip-String)
- `ui/settings_dialog.py` (Pfad-Update Bandpilot)
- `tests/test_help_dialog_features.py` (Test-Coverage OK?)
- 1-2 stichprobenartige neue Doku-Files (Inhalt KISS, korrekt?)
