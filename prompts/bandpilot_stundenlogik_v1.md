# Bandpilot Stunden-Logik — V1 Final (Stand 2026-05-04 nach Mike + R1)

## Ziel

Bandpilot komplett neu konzipieren. Statt globalem Pooled Mean +
Aggregat-Empfehlung mit Confirm-Dialog: **Stunden-genaue Anzeige der
drei Modus-Werte (Normal / Diversity Standard / Diversity DX) ohne
Aggregation, mit Auto- oder Manuell-Schaltung**.

**Hintergrund:** Die alte Aggregat-Logik (Std+DX)/2 ist statistisch
nicht sauber (R1, Mai 2026): Std und DX repraesentieren
unterschiedliche Grundgesamtheiten. Mike's Vorschlag (drei direkte
Werte, max-Pick oder User-Wahl) ist konzeptionell klarer und
zugleich KISS.

## Akzeptanzkriterien

### 1. Drei direkte Stunden-Werte (KEINE Aggregation)

Pro UTC-Stunde aus Statistik:
- `Normal_Mean` — gemittelte Stationen/Slot ueber alle Tage in dieser Stunde
- `Diversity_Standard_Mean`
- `Diversity_DX_Mean`

### 2. Markdown-Empfehlungs-Datei pro Band

Pfad: `auswertung/Bandpilot-<band>-FT8.md`
Format: 24-Zeilen-Tabelle (UTC 00..23) mit Spalten:
- UTC | Normal Tage·Sta | Diversity Std Tage·Sta | Diversity DX Tage·Sta | Top-1

Generierung:
- **Beim App-Start** (sync, < 1 s pro Band, in `_init_optional_features`)
- **Bei `scripts/generate_plots.py`-Lauf** (mitziehen)

### 3. Settings-Combo NEU (statt vorher 3-Wege-Pref)

```
Bandpilot — Verhalten:    [Manuell ▼]
                          Aus
                          Auto (bester Wert)
                          Manuell (Dialog)
```

Settings-Key: `bandpilot_mode` (Werte: `"off"` | `"auto"` | `"manual"`)

**Migration aus alten Settings:**
- `bandpilot_enabled = false` -> `bandpilot_mode = "off"`
- `bandpilot_enabled = true` (egal welche `diversity_pref`) ->
  `bandpilot_mode = "auto"` (Default sinnvollster Fall)
- `bandpilot_diversity_pref` wird verworfen
- Migration einmalig beim ersten Start mit neuer Version

### 4. AUTO-Modus

- Vergleich: `max(Normal_Mean, Std_Mean, DX_Mean)`
- **Toleranz:** Wenn `Top-1 - Top-2 < max(5%, 1 Station)` -> bleibt
  aktueller Modus (verhindert Pingpong bei Rauschen / Messungenauigkeit)
- **3-Sekunden-Toast mittig auf Bildschirm**, self-closing,
  optional [×]-Button zum Sofort-Schliessen
- Toast-Inhalt: alle 3 Werte + welcher gewaehlt
- Beispiel:
  ```
  Bandpilot — 40m FT8, 13 UTC
  Diversity DX gewaehlt (80,4 Sta./Slot)
    Normal:        65,2
    Diversity Std: 63,1
    Diversity DX:  80,4 ← ausgewaehlt
  ```

### 5. MANUELL-Modus (R1-smart)

- Dialog **nur** wenn `Top-1 != aktueller Modus` (sonst stillschweigend
  bestaetigt)
- Wenn Top-1 == aktueller Modus: kein Dialog, App-Verhalten unveraendert
- Falls User trotzdem Werte sehen will: kleiner Bandpilot-Button in der
  UI (zukuenftige Erweiterung, nicht V1)

Dialog-Aufbau:
```
┌─ Bandpilot — 40m FT8, 13 UTC ────────────────────────────┐
│                                                           │
│   Genug Daten fuer Vergleich vorhanden:                   │
│                                                           │
│      1.  Diversity DX        80,4 Sta./Slot   ← gruen     │
│      2.  Normal              65,2 Sta./Slot                │
│      3.  Diversity Standard  63,1 Sta./Slot                │
│                                                           │
│   ● aktueller Modus: Normal                                │
│                                                           │
│   [Normal]  [Diversity Standard]  [Diversity DX]          │
│                                                           │
└───────────────────────────────────────────────────────────┘
```

Highlighting (R1-KISS):
- **Top-1: gruene Schrift** (kraeftig)
- Top-2/Top-3: neutral (Default-Textfarbe)
- Zusaetzlich **"1/2/3"-Marker** vorne -> Farbenblind-Friendly
- **Aktueller Modus: ●-Marker links neben Modus-Name**

### 6. Stille bei zu wenig Daten

Wenn ein oder mehrere der 3 Modi unter `MIN_DAYS_HOUR=3` ODER
`MIN_CYCLES_HOUR=20` liegt:
- **Kein Dialog, kein Toast, kein Auto-Wechsel**
- **Dezenter Statusbar-Hinweis 5 Sekunden:**
  `"Bandpilot: nicht genug Daten fuer 40m um 03 UTC"`
- Manuelle Wahl bleibt erhalten

### 7. TX-Schutz

Wenn TX gerade aktiv ist (Encoder transmittet):
- Modus-Wechsel **verzoegern** bis TX beendet ist
- Toast erscheint sofort: `"Bandpilot wechselt zu Diversity DX nach TX-Ende"`
- Nach `tx_finished`-Signal: Modus-Switch + kurzer Bestaetigungs-Toast
  (0,5s) "Bandpilot: Modus angewendet"

### 8. Pingpong-Schutz

Erste Iteration: nur die 5%-Toleranz aus AK 4. **Keine Zeit-Hysterese.**
Falls im Feldtest Pingpong sichtbar wird: spaeter "letzte 10 Minuten
gleicher Wechsel war schon"-Hysterese ergaenzen (R1's Empfehlung).

### 9. Datenbasis-Schwellen pro Stunde

- `MIN_DAYS_HOUR = 3` (3 Messtage in DIESER UTC-Stunde)
- `MIN_CYCLES_HOUR = 20` (20 Slots in DIESER UTC-Stunde)
- **Alle drei** Modi muessen das erfuellen — sonst Stille (siehe AK 6)

### 10. Tests

Mindestens 6 neue Tests in `tests/test_mode_recommender.py`:
- `aggregate_stats_by_hour()` mit fiktiven MD-Files
- `recommend_for_hour(summary, hour, mode)` mit `"auto"` Pfad
- Toleranz-Test: Top-1 vs Top-2 unter 5%/1 Station -> kein Wechsel
- Toleranz-Test: deutlich Top-1 -> Wechsel
- Migrations-Test: alte Settings -> neue Settings
- Edge-Case: zu wenig Daten -> None / Skip

Plus mind. 2 Smoke-Tests in `tests/test_bandpilot_md.py` (neu):
- MD-Datei wird korrekt generiert
- Format-Stabilitaet (Tabellen-Header, 24 Zeilen)

Aktuell 616 Tests, Erwartung: ~625-628 Tests gruen.

### 11. Doku-Komplett-Update

**`docs/explained/bandpilot_de.md` + `bandpilot.md`:** komplett neu
schreiben — das ALTE Konzept (Aggregat + Confirm-Dialog Ja/Nein +
Sub-Mode aus Settings) ist obsolet. Neues Konzept:
- Drei Stunden-Werte, Auto vs Manuell, Toleranz, MD-Datei,
  Datenbasis-Schwellen.

**README.md (bilingual):**
- "Key Innovations" / "Wichtige Innovationen": Bandpilot-Beschreibung
  auf Stunden-Logik anpassen.
- "All Features" Liste: Bandpilot-Eintrag updaten.
- "Detailed Feature Documentation"-Tabelle: Link bleibt, Inhalt
  unter dem Link aendert sich aber.

## Betroffene Module

### Code

- **`core/mode_recommender.py`**:
  - Neue Funktion `aggregate_stats_by_hour(stats_dir, band) -> dict[int, dict]`
  - Neue Funktion `recommend_for_hour(summary, hour, mode, current_mode) -> str | None`
    - Nimmt aktuellen Modus rein wegen Toleranz-Schwelle
    - Returnt neuen Modus-String oder None (kein Wechsel)
  - Alte `aggregate_stats()` + `recommend()` koennen optional bleiben
    fuer Backwards-Compat, oder geloescht werden

- **`tools/build_bandpilot_recommendations.py`** (neu, ~80-100 Zeilen):
  - `write_bandpilot_md(band, ft_mode, output_dir)` schreibt
    24-Zeilen-Tabelle mit Top-1-Markierung

- **`scripts/generate_plots.py`** — eine Zeile am Ende:
  fuer jedes (band, ft_mode) `write_bandpilot_md()` aufrufen

- **`ui/main_window.py`**:
  - `_init_optional_features()` ergaenzt um
    `_init_bandpilot_recommendations()` der MD-Files generiert
  - Migrations-Logik fuer Settings-Keys beim ersten Start

- **`ui/mw_radio.py`**:
  - `_maybe_apply_bandpilot()` neu schreiben:
    - aktuelle UTC-Stunde holen
    - Stunden-Aggregat lesen
    - Datenbasis-Check
    - bei wenig Daten: Statusbar-Hinweis 5s
    - Auto-Modus: Toleranz-Check, Toast, ggf. TX-Verzoegerung
    - Manuell-Modus: nur Dialog wenn Top-1 != aktuell
  - `_bandpilot_overridden_bands` + Override-Logik in
    `_on_rx_mode_changed` ENTFERNEN
  - Neue Methode `_show_bandpilot_dialog()` mit 3 Werten + 3 Buttons
  - Neue Methode `_show_bandpilot_auto_toast()` mit zentrierter
    Self-Close-QDialog
  - Neue Methode `_apply_bandpilot_after_tx()` fuer TX-Verzoegerung

- **`ui/settings_dialog.py`**:
  - Combo `bandpilot_diversity_pref` ENTFERNEN
  - Combo `Bandpilot — Verhalten` mit Werten Aus/Auto/Manuell
  - `?`-Button-Hilfe-Pfad bleibt unveraendert

- **`config/settings.py`**:
  - `bandpilot_enabled` und `bandpilot_diversity_pref` aus DEFAULTS raus
  - `bandpilot_mode = "off"` als Default ergaenzen
  - Migrations-Funktion: bei Load alten Schluesseln in neuen umrechnen

### Tests

- `tests/test_mode_recommender.py` — bestehende Tests anpassen
  (alte API ggf. raus oder als deprecated)
- `tests/test_bandpilot_md.py` — neu
- `tests/test_settings_dialog_smoke.py` — Bandpilot-Tests anpassen
  (neue Combo statt alter)
- `tests/test_modules.py` — falls Bandpilot-Imports

### Doku

- `docs/explained/bandpilot_de.md` — komplett neu
- `docs/explained/bandpilot.md` — komplett neu (parallel zur DE)
- `README.md` — Bandpilot-Erwaehnung in Key Innov + All Features +
  In Field Test bleibt aber Inhalt aktualisieren (3-Werte-Konzept)
- `HISTORY.md` — neuer Eintrag `## 2026-05-XX v0.88 — Bandpilot
  Stunden-Refactor`
- `HANDOFF.md` (BEIDE Pfade) — neuer Stand
- `CLAUDE.md` (BEIDE Pfade) — Header aktuell halten
- Memory: `feedback_bandpilot_ux_pref_in_settings.md` markieren
  als obsolet ODER neu fassen mit finaler UX

## Out of Scope

- Default-Modus pro Band-Setting (Variante B aus alter Diskussion)
- Band-Empfehlung (Bandpilot empfiehlt aktiv anderes Band)
- Zeit-Hysterese 10 Min (erst wenn Pingpong im Feld)
- Manueller "Bandpilot-Dialog jetzt zeigen"-Button (Erweiterung)
- Color-Blind-Friendly: nur Zahlen-Marker, keine zusaetzlichen
  Symbol-Pattern

## Versionsbump

V0.87.1 -> **V0.88** (Konzept-Bruch, nicht Patch). Neuer
Release-Tag + GitHub Release nach Push.

## Workflow ab hier

V1 ist final. Naechste Schritte:
1. Self-Review V2 (Frische-KI-Brille — Luecken? Mehrdeutigkeiten?)
2. R1-Review V2 mit Files (`core/mode_recommender.py`,
   `ui/settings_dialog.py`, `ui/mw_radio.py`, `config/settings.py`,
   bestehende Bandpilot-Doks, README)
3. Schritt 2.5: R1-Findings gegen Code verifizieren
4. V3 + impliziter Mike-Freigabe (durch dieses Dokument)
5. Atomare Commits gem. Phasen:
   - Phase 1: `core/mode_recommender.py` + Tests
   - Phase 2: `tools/build_bandpilot_recommendations.py` + Smoke-Tests
   - Phase 3: Settings-Migration + Combo-Update
   - Phase 4: `_maybe_apply_bandpilot()` neu, Override-Set raus
   - Phase 5: Toast-Dialog + Manuell-Dialog (mit Highlighting)
   - Phase 6: TX-Schutz + Statusbar-Hinweis
   - Phase 7: App-Start-Hook fuer MD-Generierung
   - Phase 8: Doku-Komplett-Update (DE+EN)
   - Phase 9: README + Version v0.88
   - Phase 10: Tests gruen, Final-R1
   - Phase 11: HISTORY/HANDOFF/CLAUDE/Memory + Push + GitHub-Release
6. Final-R1-Codereview vor letztem Commit
7. Push + GitHub-Release v0.88

## Konsens-Snapshot

Alle 7 R1-Punkte aus 2026-05-04-Review:
| Punkt | Mike-Entscheidung |
|-------|---|
| 1 Farben | R1-KISS: Top-1 gruen, Rest neutral, Zahlen-Marker 1/2/3 |
| 2 Toleranz | `max(5%, 1 Station)` |
| 3 Stille | Statusbar-Hinweis 5s (nicht komplett still) |
| 4 Manuell-Dialog | R1-smart: nur wenn Top-1 != aktuell |
| 5 TX-Schutz | Wechsel verzoegern bis TX-Ende |
| 6 Pingpong | Erst nur 5%-Regel, Hysterese spaeter |
| 7 Migration | enabled=false -> off; sonst -> auto |
