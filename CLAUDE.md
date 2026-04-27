Lies nach dieser Datei sofort auch HANDOFF.md und bestätige beide mit je einer Zeile.

# SimpleFT8 — Claude Kontext

**Start:** `cd "/Users/mikehammerer/Documents/KI N8N Projekte/FT8/SimpleFT8" && ./venv/bin/python3 main.py`
**Aktueller Stand:** v0.71 (27.04.2026) — TX-Reichweiten-Sektoren: PSK-Reporter Sektor-Wedges im Karten-TX-Modus zeigen jetzt **Reichweiten-Pattern** (max-Distanz pro Sektor) statt Cluster-Dichte. Spot aus VK6 (16000 km) erzeugt langen Wedge, Iberien-Cluster bleibt bescheiden. Mike sieht auf einen Blick wo sein Signal hingeht. RX-Modus unveraendert. NaN/Inf-Guards in `SectorBucket.max_distance_km`. 4 atomare Commits, V1→V2→V3-Workflow mit DeepSeek-Reviewer.
**Tests:** `./venv/bin/python3 -m pytest tests/ -q` → 426 passed (Qt-Smoke-Tests via `QT_QPA_PLATFORM=offscreen`)
**Vor Commits:** Tests grün + bei nicht-trivialen Änderungen DeepSeek-Review (`pal codereview` model `deepseek-chat`) — bereits durch globale §0 + Projektregeln gefordert.

⚠️ **DeepSeek V4 (deepseek-chat) — Neues Modell, Verhalten noch unbestätigt (Stand 2026-04-25):**
DeepSeek-Antworten IMMER kritisch prüfen — Vorschläge nicht blind übernehmen.
Bekanntes Risiko: KI kann plausibel klingende aber falsche Zeilen-/Datei-Angaben machen.
Vorgehen: DeepSeek-Review als Zweitmeinung nutzen, Claude verifiziert jeden Vorschlag
am tatsächlichen Code bevor er übernommen wird. Bei Widerspruch: Code ist Referenz.
## ⛔ Projekt-Philosophie (PFLICHT bei Architektur-Entscheidungen!)

**SimpleFT8 ist ein Hobby-Funker-Tool. KEIN Contest-Tool.** Diese Leitlinien
gelten fuer Claude UND DeepSeek bei Feature-Vorschlaegen, Architektur-Beratung,
Implementierungen:

- **Zielgruppe:** Hobby-Funker. Nicht Pileup-Jaeger, nicht Contest-Operatoren,
  keine 1000-QSO-pro-Tag-Stationen.
- **Use-Case:** App starten → ein bisschen FT8/FT4/FT2 funken → fertig.
  Keine Stunden-langen Sessions mit komplexer Konfiguration.
- **UX-Prinzip:** Einfache Bedienung > Vollstaendigkeit. Lieber 3 gut funktio-
  nierende Features als 30 die Mike erst lernen muss.
- **Visueller Stil:** Modern (dunkles Theme, Neon-Akzente, weiche Verlaeufe).
  Nicht 90er-Jahre-Funktionalitaets-UI wie WSJT-X / JTDX.
- **NICHT geplant:** Contest-Modi, Multi-Operator, RTTY/CW/SSB, Skimmer-
  Integration, Pileup-Tools, komplexe Filter-Macros, Cluster-Spotting fuer
  DX-Hunting. Wenn ein DeepSeek-Vorschlag in diese Richtung geht: ablehnen.
- **Was modern bedeutet:** 3D-Globus statt platter PSK-Reporter-Karte,
  Live-Diversity-Visualisierung, Antennen-Farb-Coding, glow-Effekte —
  Dinge die in 2026 selbstverstaendlich sind aber im Funker-Tool-Alltag fehlen.

**Wenn DeepSeek oder ich ein Feature vorschlagen, immer pruefen:** „Hilft das
einem Hobby-Funker beim Hobby-Funken? Oder waere das nur fuer Power-User /
Contester sinnvoll?" — bei letzterem: NICHT umsetzen, in eine optionale
Erweiterung ausgliedern oder ganz verwerfen.

---

**Diagramme:** `./venv/bin/python3 scripts/generate_plots.py`
→ Generiert IMMER beide Sprachen: DE → `auswertung/` + EN → `auswertung/en/`
→ DE: `SimpleFT8_Bericht.pdf` (7 S.) | EN: `SimpleFT8_Report.pdf` (7 p.)
→ Regel: Statistiken und PDFs IMMER auf Deutsch UND Englisch erstellen!

**⚠ Tages-/Pooled-Mean-Auswertungen:** ZUERST `auswertung.md` lesen!
Format-Stolpersteine (3 vs 5 Tabellenspalten, Rescue extern in `stations/`,
DX-Modus zählt nur SNR<-10) sind dort dokumentiert inkl. Code-Vorlage.
Mike's „Tagestrend"-Anfragen → stundenweise Tabelle, nicht nur Pooled-Mean.
**Git:** branch `main`, Repo aktiv, Statistics-Daten committed

---

## Rollen

- **Mike (Ideengeber, Tester, Inspirator):** definiert Ziele, testet im Feld, entdeckt
  Ideen und Probleme aus der Praxis, entscheidet bei strategischen Architektur-Fragen
  und über alles was nach außen sichtbar wird (Push, Doku auf GitHub, Releases).
- **Claude (Chef-Programmierer):** verantwortlich für Code-Qualität, Struktur,
  Wartbarkeit, Fehlerfreiheit, Tests. Trifft Code-Architektur-Entscheidungen
  innerhalb des vereinbarten Ziels eigenständig und proaktiv. Bei wirklich
  grundlegenden Weichenstellungen einmal kurz vorlegen, dann umsetzen.

## Mehrstufiger Prompt-Workflow (PFLICHT bei nicht-trivialen Features/Bugs)

Vor jeder nicht-trivialen Umsetzung (>5 Zeilen, neues Modul, Architekturfrage,
mehrere Probleme zugleich) durchlaufen wir gemeinsam diesen Ablauf — KEIN
direkter Sprung in `/plan`:

1. **Probleme erkennen + Prompt V1 entwerfen** (Claude)
   — Symptome präzise beschreiben, Datei:Zeile-Referenzen, Akzeptanzkriterien.
2. **Rolle frischer KI: Self-Review → V2** (Claude)
   — Was fehlt? Was ist mehrdeutig? Was übersieht V1? Lücken füllen, V2 schreiben.
3. **V2 an DeepSeek** (`pal chat` model `deepseek-chat`)
   — DeepSeek bekommt explizit den Auftrag den Prompt zu kritisieren und
   konkret zu verbessern (nicht das Problem zu lösen).
4. **DeepSeek-Findings einarbeiten → V3** (Claude)
   — Kritisch prüfen (siehe DeepSeek-Caveat oben), V3 schreiben.
5. **Mike vorlegen** — Mike liest V3, gibt Freigabe oder Korrekturen.
6. **Planungsmodus + Umsetzung** — erst dann `/plan`, dann atomare Commits.

**Trigger-Sätze von Mike** für diesen Workflow:
- „selbe vervahrensweise wieder" / „wie bei Locator-DB"
- „erst V1 dann zu deepseek" / „prompt entwerfen"

**Wann der volle V1→V2→V3-Workflow lohnt (Trigger-Schwelle):**
Mindestens EINES der folgenden Kriterien erfüllt → vollen Workflow fahren:
- Task hat ≥2 unabhaengige Akzeptanzkriterien
- Mathematisch/geometrisch (Projektion, Rotation, Filter, Algorithmen)
- Beruehrt ≥2 Dateien oder fuehrt neues Modul ein
- Threading/Persistence/IO neu beteiligt
- Architektur-Entscheidung (siehe „Architektur-Entscheidungen" oben)

**Wann V1 direkt reicht (Workflow uebersprungen):**
- Tippfehler, Umbenennungen, <5 Zeilen
- Lokaler Patch in EINER Methode ohne Architekturwirkung
- Reines Doku-Update, Test-Anpassung an bestehende API
- Bugfix mit klarer Datei:Zeile-Diagnose und einzigem Akzeptanzkriterium

→ Bei Grenzfall lieber Workflow fahren als Sackgasse riskieren.
   Beispiel-Mehrwert siehe v0.66 Map-UI (Sektor-Rotation): DeepSeek fand
   1°→5°-Stabilitaetsproblem, Helper-Extraktion, Test-Reduktion.

**Bei Plan-Mode selbst:** nur die Plan-Datei editieren. Read/Grep/Glob zum
Verifizieren von Code-Behauptungen ist ok. Plan-Datei mit konkreten
Datei:Zeile-Referenzen versehen — Subagents können das schnell verifizieren.

**Begründung:** Mehrstufige Validierung verhindert Over-Engineering.
Beispiel v0.67-Locator-DB: V2 hatte 26-Buchstaben-Splitting, LRU-Cache,
Write-Ahead-Log — DeepSeek hat die Komplexität auf 1/4 reduziert.

## Commits

Lokale Commits trifft Claude eigenständig wenn ein Schritt logisch in sich geschlossen
ist. Aufteilung **atomar** — pro Refactoring/Feature/Bugfix ein Commit, nicht alles in
einen Mega-Commit zusammenwerfen. Beispiel: Refactoring + neue Tests + Doku =
3 Commits, nicht 1.

`git push` und alles was nach außen sichtbar wird (PRs, Releases, Tags) **nur nach
expliziter Anfrage von Mike**.

## Architektur-Entscheidungen

Folgende Änderungen werden Mike VOR Umsetzung kurz vorgelegt (Plan + Begründung,
dann seine Bestätigung):

- **Modul-Auflösung:** eine Klasse/Datei in mehrere Module splitten
  (z.B. `flexradio.py` in connection/audio/slice aufteilen)
- **Architektur-Pattern-Wechsel:** z.B. von Mixins zu Composition,
  von Singleton zu DI-Container
- **Threading-Modell-Änderungen:** neue Threads, Lock-Strukturen, Async-Migration
- **Eingriffe in produktive Algorithmen ohne Test-Schutz**
  (siehe AP-Lite v2.2: kein End-to-End-Test → kein blinder Fix)
- **Neue externe Abhängigkeiten** (Pip-Pakete, C-Libraries)
- **Breaking Changes** an öffentlichen Schnittstellen
  (Settings-Dateiformat, Statistics-MD-Format, ADIF-Export, JSON-Cache-Schemas)

Alles andere — Helper-Extraktion innerhalb derselben Datei, Bug-Fixes über
mehrere Dateien, neue Tests, Doku-Updates, lokales Refactoring, Optimierungen
ohne Verhaltensänderung — entscheidet Claude eigenständig und meldet im
Anschluss was gemacht wurde.

---

## Architektur & Module

```
core/
  decoder.py          RMS AGC (-12 dBFS Ziel, ±3 dB Hysterese), 5-Pass Subtraktion
                      DT_BUFFER_OFFSET: FT8=2.0, FT4=1.0, FT2=0.8 (WSJT-X 0.5s eingerechnet!)
  encoder.py          FT8/FT4/FT2 encode → VITA-49 TX
                      TARGET_TX_OFFSET=-0.8s (kompensiert FlexRadio TX-Buffer 1.3s)
  qso_state.py        State Machine: Hunt, CQ, Waitlist, RR73 Courtesy (max 2×)
                      _was_cq: in start_qso() UND _process_cq_reply() gesetzt (Bug-Fix!)
  diversity.py        Controller: Standard(Stationsanzahl) / DX(SNR<-10dB)
  diversity_merger.py Merged A1/A2 Dekodierungen
  ntp_time.py         DT-Korrektur v3: pro Modus+Band (Key "FT8_20m"), set_band(),
                      2-Zyklen-Messen, 70% Dämpfung, engere Grenzen pro Modus,
                      gedämpfte Erstkorrektur bei ≤2 Stationen
  station_accumulator.py Gemeinsame Logik Normal+Diversity
                      Aging: 75s normal / 150s active_qso / 300s CQ-Rufer
  station_stats.py    Async Queue+Daemon-Thread Logging → statistics/<Modus>/<Band>/<Proto>/
                      + Entry-Typ antenna_qso → statistics/antenna_qso/YYYY-MM-DD.md
  antenna_pref.py     AntennaPreferenceStore: {best_ant, delta_db} pro Callsign,
                      1dB Hysterese, kein Timeout (jeder Zyklus überschreibt)
  propagation.py      HamQSL + _apply_seasonal_correction(band, condition, utc_hour, month)
                      60m fehlt in XML → Interpolation 40m/80m (day+night getrennt, implementiert)
  ap_lite.py          ⛔ UNGETESTET — Feldtest ausstehend (SCORE_THRESHOLD=0.75)
  omni_tx.py          ⛔ DEAKTIVIERT — Feldtest ausstehend (Klick auf Versionsnummer)
  auto_hunt.py        Auto-Hunt Logik
  timing.py           UTC-Takt, modus-abh. Zyklen
  protocol.py         FTX_PROTOCOL_FT8/FT4/FT2
  ft8lib_decoder.py   C-Library Wrapper
  geo.py              Maidenhead, Haversine, Großkreis-Bearing (atan2),
                      Azimuthal-Equidistant-Projektion (Karten-Render),
                      safe_locator_to_latlon (None-safe Wrapper)
  direction_pattern.py Sektor-Aggregation (16x 22.5°), Mobile-Filter,
                      StationPoint/SectorBucket Datenklassen,
                      NaN/Inf-Schutz fuer korrupte externe Inputs
  psk_reporter.py     PSKReporterClient: XML-Polling mit Cache + Backoff
                      (1.5x bis 60min), Call-Normalisierung (.rsplit('/',1)),
                      atomarer Cache-Write (.tmp + os.replace)
  locator_db.py       LocatorDB: persistenter Locator-Cache (~/.simpleft8/
                      locator_cache.json). Source-Priority (cq_6 > psk_6 >
                      qso_log_6 > _4-Varianten). RLock-Threading, atomic-Write,
                      Mobile-Suffixe (/MM/AM/QRP) prec_km x 1.5. get() returnt
                      Kopie. Bulk-Import aus ADIF-Dateien. Save bei App-Close.

radio/
  base_radio.py       RadioInterface ABC
  radio_factory.py    create_radio(settings)
  flexradio.py        SmartSDR TCP + VITA-49 + Auto RX-Filter

ui/
  main_window.py      3-Panel + Statusbar; _tune_active/_tune_freq_mhz State-Vars
  mw_cycle.py         Cycle Processing; _diversity_in_operate Flag (Transition Guard!)
                      _log_stats Guard: btn_cq.isChecked() + cq_mode + state (3-fach robust)
  mw_radio.py         Band/Modus/Diversity, _diversity_in_operate Reset bei _enable_diversity()
                      set_band()/set_mode() bei Wechsel + Radio-Connect (DT-Korrektur!)
  mw_tx.py            TX-Regelung: rfpower konvergiert → save_tx_power();
                      _on_tune_clicked() setzt _tune_active/_tune_freq_mhz + _update_statusbar()
  mw_qso.py           QSO Callbacks, CQ, Logbuch;
                      _on_station_clicked: _cq_was_active VOR stop_cq() sichern → _was_cq fix
                      _antenna_pref_label() → "(ANT1)" in Normal, "(ANT2, +6.3 dB)" in Diversity
  control_panel.py    UI Controls (57 KB — größte UI-Datei); Frequenz in kHz
  rx_panel.py         RX-Tabelle; Answer-Me-Highlighting; Spalten per Rechtsklick
  dx_tune_dialog.py   18-Zyklus interleaved Messung; cache.save() HIER nach Messung!
  direction_map_widget.py  Azimuthal-Karte mit RX/TX-Toggle (v0.66).
                      MapCanvas (paintEvent + QPixmap-Background-Cache, Resize-
                      Debounce 200ms) + DirectionMapDialog (non-modal QDialog,
                      Toggle, Filter-Bar, Status). LocatorCache fuer FT8 (CQ
                      ist die einzige Quelle fuer Locators). Aufruf via
                      Settings-Dialog → "Karte oeffnen ..."-Button.

scripts/
  generate_plots.py   3-Modus Vergleich, pooled mean, Error Bars
                      PDF-Bericht 7 Seiten (nur 40m FT8), cursor-basiertes Inch-Layout
                      Helpers: _ctext/_chline/_csection (y in Zoll von oben, kein hardcoded fig-y)

config/settings.py    Frequenzen, Band-Configs, mode-aware get/save_dx_preset()
                      TUNE_FREQS (Band_Mode → Nebenfrequenz -2kHz) + get_tune_freq_mhz()
log/adif.py           ADIF 3.1.7
dt.md                 DT-Timing Analyse: Theorie, Änderungen, Validierungsergebnisse
```

---

## DT-Timing (Stand 23.04.2026 — validiert)

```
RX: DT_BUFFER_OFFSET FT8=2.0 (= 1.5 Buffer + 0.5 WSJT-X Protokoll)
    Korrektur konvergiert auf ~0.24s (nur FlexRadio VITA-49 RX-Hardware)
    Stationen zeigen DT ≈ 0.0–0.2 nach Konvergenz

TX: TARGET_TX_OFFSET = -0.8s = 0.5 (Protokoll) - 1.3 (FlexRadio TX-Buffer)
    FlexRadio puffert TX-Samples konstant 1.3s vor RF-Ausgabe
    Validiert: 8 Zyklen 0.0s DT am Icom, 20m + 40m getestet

Speicherung: ~/.simpleft8/dt_corrections.json → Key "FT8_20m" (pro Modus+Band)
    set_band() / set_mode(mode, band) lädt gespeicherten Wert sofort
```

---

## Gain-Algorithmus & Hard-Limit

- **Ziel:** -12 dBFS RMS (±3 dB Hysterese)
- **Normalisierung:** -18 dBFS RMS nach AGC
- **TX-Power:** Closed-Loop FWDPWR Feedback, `_rfpower_current` (0-100)
- **rfpower pro Band:** `settings.save_tx_power(band, val)` / `get_tx_power(band, default=50)`, Clamp 10–80%
- **Konvergenz-Flag:** `_rfpower_converged` — True wenn stabil, reset bei Änderung/Bandwechsel

---

## DX-Preset System & Cache

- **Mode-aware Keys:** `"20m_FT8"` hat Vorrang vor `"20m"`
- `get_dx_preset(band, mode=None)` / `save_dx_preset(..., scoring="standard"/"dx")`
- **DiversityCache:** 2h Gültigkeit, Key `diversity_cache_{band}_{scoring}`
- **cache.save() NUR in `_on_dx_tune_accepted()`** — NICHT im Cycle-Loop!
- Bei Normal+Standard: Dialog "Vorhandene Daten verwenden oder neu einmessen?" (wie bei DX)

---

## Verzeichnis-Struktur (Dateiablage)

### Kalibrierungsdateien
- **Pfad:** `~/.simpleft8/kalibrierung/`
- `presets_standard.json` → Gain + Ratio für Diversity Standard (pro Band+FTMode)
- `presets_dx.json`       → Gain + Ratio für Diversity DX (pro Band+FTMode)
- **Format Key:** `"40m_FT8"`, Werte: `rxant, ant1_gain, ant2_gain, ant1_avg, ant2_avg, ratio, dominant, timestamp, measured`
- **Klasse:** `core/preset_store.py` → `PresetStore("presets_standard.json")` / `PresetStore("presets_dx.json")`
- **Auto-Migration:** PresetStore verschiebt automatisch alte Dateien aus `~/.simpleft8/` nach `~/.simpleft8/kalibrierung/`

### DT-Korrektur
- **Pfad:** `~/.simpleft8/dt_corrections.json`
- **Format:** `{"FT8_20m": 0.24, "FT8_40m": 0.24, ...}` (pro Modus+Band)
- Migration von altem Format (`"FT8"` → `"FT8_20m"`) automatisch in `_load_for_current_key()`

### App-Sicherungen
- **Pfad:** `SimpleFT8/Appsicherungen/`
- Letzte stabile Sicherung: `2026-04-22_stable/`
- DT-Optimierung Backup: `2026-04-23_vor_dt_optimierung_core/` + `_ui/`

---

## Diversity-System

- **`_diversity_in_operate`** — Transition Guard in mw_cycle.py
  - Verhindert dass once-only Code (warmup, CQ-unlock, freq-update) jeden Zyklus läuft
  - Wird in `_enable_diversity()` auf False gesetzt (Reset)
  - Wird True beim ersten operate-Eintritt nach measure
- **THRESHOLD = 0.08** (8%) → 70:30 Ratio; darunter 50:50
- **MIN_MEASURE_STATIONS = 5**
- Median über 4 Zyklen
- Stats-Warmup: 60s nach Band/Modus-/App-Start

### CQ-Frequenz-Algorithmus (v0.59, dynamisch + slot-synchron)
- **Suchbereich DYNAMISCH:** `min(occupied_bins)..max(occupied_bins)` + `SEARCH_MARGIN_BINS=0`.
  TX landet immer ZWISCHEN niedrigster und höchster Station (= dort wo zugehört wird).
  Kein fester Sweet-Spot mehr (war v0.58-Sackgasse, in v0.59 verworfen).
- **Graduelle Lücken-Toleranz:** stufenweise `(max_count_per_bin, min_gap_bins)`:
  `(0,3)` → `(0,2)` → `(0,1)` → `(1,3)` → `(1,2)`. Bei vollem Band findet der Algo IMMER
  noch eine Position (notfalls in schwach-belegtem Bereich), nie mehr None außer leerem Histogramm.
- **Score:** `gap_width − 100·n_self − 50·n_close − 25·n_near − 0.01·median_distance`
  - `n_self` (Stationen IM TX-Bin) = höchste Strafe (100 Hz/Station) — für Notfall-Stufen
  - `n_close` (±1 Bin) = 50 Hz/Station, `n_near` (±2 Bin) = 25 Hz/Station
  - Median-Distance nur Tiebreaker (0.01)
- **Sticky Gap:** bleibt bei aktueller Frequenz wenn im dynamischen Suchbereich, keine Kollisions-
  Schwelle erreicht (`n_direct >= 2` ODER `n_in_band >= 3`) und neue Lücke nicht > +50 Hz breiter.
  `_measure_gap_around()` refresht `_current_gap_width_hz` nach Sticky-Hit.
- **Such-Trigger SLOT-SYNCHRON (v0.59 Punkt 3):** `_search_slots_remaining` Counter, modus-abhängig
  initialisiert via `_SEARCH_INTERVAL_SLOTS = {FT8:4, FT4:8, FT2:16}` = ~60 s alle Modi.
  `tick_slot()` dekrementiert pro Slot, bei 0 → Such-Trigger + auto-reset.
  Anzeige `seconds_until_search` = `remaining_slots × cycle_s`. Wert friert bei App-Pause ein (gut).
- **Pro-Slot-Aufruf:** `mw_cycle._refresh_diversity_freq_view()` läuft JEDEN Slot in
  `_on_cycle_decoded`, UNABHÄNGIG vom messages-Inhalt. Hinter `if messages:` Guard darf NIE
  was hin was UI/Such-Logik betrifft (P1-Bug aus v0.54-v0.58, fixed in v0.59).
- **`reset()` muss `_current_gap_width_hz = 0` und `_search_slots_remaining` setzen** —
  sonst Bandwechsel-Bug.

---

## Cycle-Zeiten

| Modus | Zyklusdauer | RX-Filter |
|-------|------------|-----------|
| FT8   | 15.0s      | 100-3100 Hz |
| FT4   | 7.5s       | 100-3100 Hz |
| FT2   | 3.8s       | 100-4000 Hz |

---

## ⛔ Statistik-Veröffentlichung — Regel

- **Kein Push anderer Bänder ohne ausreichende Datenbasis** — Minimum: Normal + Diversity_Standard
  + Diversity_Dx je ≥ 2 Messtage, Stunden über den ganzen Tag verteilt (mind. 06–22 UTC).
- **Auswertungs-Methodik:** Pooled Mean über ALLE Messzyklen aller Messtage und Tageszeiten —
  kein Stunden-Filter. Je mehr Tage, desto stabiler. Monatlich wachsende Datenbasis.
- Ergebnis 40m FT8 (Pooled Mean, global, Stand 25.04.2026): Diversity Standard +88%, Diversity DX +123%.

---

## generate_plots.py — Berechnungsmethodik (Tagesdurchschnitt)

**Wie der Ø Sta./15s-Zyklus berechnet wird:**

```
statistics/<Modus>/<Band>/<Proto>/YYYY-MM-DD_HH.md
  → jede Datei = 1 UTC-Stunde, 1 Modus, 1 Band
  → jede Zeile = 1 FT8-Zyklus (15s) mit Spalte "stationen" (Anzahl dekodierter Stationen)

Ø Sta./15s = Summe aller Stationswerte ÷ Anzahl aller Zyklen
             (über ALLE Dateien = alle Tage × alle Stunden × alle Zyklen)

Beispiel Normal: 6.744 Zyklen × ~18.5 Sta./Zyklus
  → Das entspricht dem Tagesdurchschnitt wenn man morgens, mittags, abends misst
  → KEIN Tageszeit-Filter, KEINE Gewichtung nach Stunde oder Tag
  → Je mehr Messpunkte (Zyklen), desto stabiler der Wert
```

**Was der Wert NICHT ist:**
- ❌ Nicht Stationen pro Stunde (wäre 18.5 × 240 = 4.440/h)
- ❌ Nicht der Spitzenwert einer bestimmten Tageszeit
- ✅ Der Durchschnitt über einen ganzen typischen Betriebstag

**Weitere PDF-Layout-Details:**
- **Inch-Koordinaten:** `_yf(y_in) = 1.0 - y_in / _PH` konvertiert Zoll→figure-coord
- **Cursor-Helpers:** `_ctext(fig, y, text, fs)` → gibt neues y zurück; `_chline` → Linie; `_csection` → Titel+Linie+Body
- **Seitenhöhe:** A4 landscape: `_PH=8.27`, `_PW=11.69`, `_CTOP=1.00`, `_CBOT=7.71`
- **Body 11pt / Titel 13pt** — nie hardcoded figure-y, nie `_r_hline` (veraltet, gelöscht)
- **Rescue-Kappen:** grün, nur Diversity-Modi, `load_rescue_by_hour(stats_dir, mode, band, proto)`
- Statistics-Daten: `statistics/<Modus>/<Band>/<Proto>/YYYY-MM-DD_HH.md`

---

## Datenlage (Stand 26.04.2026)

**WICHTIG:** Statistik-Filter v0.63 — nur 20m + 40m FT8 werden noch protokolliert.
Andere Baender werden empfangen aber nicht gespeichert (Skalierungs-Entscheidung).

| Modus            | Band | Tage | Zyklen | Bemerkung |
|------------------|------|------|--------|-----------|
| Normal           | 40m  | 4    | 6.744  | 24h Abdeckung |
| Diversity_Normal | 40m  | 4    | 6.827  | 24h Abdeckung |
| Diversity_Dx     | 40m  | 4    | 9.125  | 24h Abdeckung |
| Normal           | 20m  | 5    | 688    | 13 Stunden, waechst |
| Diversity_Normal | 20m  | 2    | 364    | 5 Stunden, schwach |
| Diversity_Dx     | 20m  | 4    | 2.469  | 18 Stunden |

**40m FT8 Ergebnis (Pooled Mean global, 22.696 Zyklen):**
- Diversity Standard: **+88% / +122%** (ohne/mit Rescue), Rescue allein +35%
- Diversity DX:       **+124% / +158%** (ohne/mit Rescue), Rescue allein +34%

**20m FT8 Ergebnis (Pooled Mean Stunden-Vergleich, Stand 26.04.):**
- Diversity_Normal: +15-30% im Tageshoch (12-16 UTC) — KEIN Antennen-Mismatch
  wie auf 40m, sondern echte Pol-/Pattern-Diversity (ANT1 ist resonant!)
- Diversity_Dx: +59% beim Tag→Nacht-Uebergang (18 UTC) — DX-Modus glaenzt am Skip-Zonen-Rand
- ANT2-Win-Rate Doppelempfaenge: 79% (Std), 86% (Dx) trotz resonantem Kelemen-Dipol auf ANT1
- Datenbasis waechst noch — siehe `Auswertung-20m-FT8.pdf` mit eigenem Narrativ

---

## ⛔ OMNI-TX (PRIVAT — NICHT AUF GITHUB WIE MAN ES AKTIVIERT)

- Aktivierung: Klick auf Versionsnummer → CQ-Button wird "OMNI CQ"
- Status: **DEAKTIVIERT** — Feldtest ausstehend
- GitHub: Feature darf erwähnt werden, NICHT wie aktiviert

---

## Thread-Safety

| Modul | Lock | Was geschützt |
|-------|------|---------------|
| `core/diversity.py` | `threading.Lock()` (`_hist_lock`) | Histogramm-Daten |
| `core/station_stats.py` | `queue.Queue` + Daemon-Thread | File-Writes |
| `core/ntp_time.py` | `threading.Lock()` (`_lock`) | Korrekturwert + Phase |
| `core/antenna_pref.py` | `threading.RLock()` (`_lock`) | _prefs dict (Karten-Render-Pfad) |
| `core/psk_reporter.py` | `threading.Lock()` (`_lock`) | _thread/_stop_event Lifecycle |
| `core/locator_db.py` | `threading.RLock()` (`_lock`) | _calls dict (Decoder + PSK-Worker konkurrent) |

**Karten-Live-Daten-Pfad (v0.66):** Decoder-Thread → `_emit_map_snapshot_if_open`
→ `direction_map_signal.emit(snapshot, band)` → `Qt.QueuedConnection` →
`_on_direction_map_snapshot` (GUI-Thread) → `canvas.update_stations`. Niemals
direkt aus dem Decoder-Thread Widget-Methoden aufrufen — immer ueber das Signal.

---

## Änderungshistorie

**HISTORY.md** — lückenlose Aufzeichnung aller Änderungen, Bugfixes und Features.
- Datei: `SimpleFT8/HISTORY.md`
- Regel: **Nur anhängen, niemals löschen oder überschreiben.**
- Bei jeder Session: Änderungen am Ende eintragen (Feierabend-Routine Schritt 3).
- **Versionsnummer IMMER mitführen!** Format: `## YYYY-MM-DD vX.YY — Kurztitel`
  - `APP_VERSION` steht in `main.py` (erste Konstante nach den Imports)
  - Bei neuen Features: Patch-Version +0.01 erhöhen, bei Bugfix-only: unverändert lassen
  - So ist für jedes Appsicherungen-Backup sofort klar, welcher HISTORY-Eintrag dazugehört

---

## Offene TODOs (nach Schwierigkeit)

**v0.60-v0.66 (26.04.2026) — UMGESETZT:**
- v0.60: CQ-Counter QSO-Reset (kein Mid-QSO-Sprung) + Info-Box Normal-Preset alt
- v0.61: Antenna-Pref Hysterese `>=` Fix + Live-QSO-Anzeige + Label `(ANT2 ↑X.X dB)`
- v0.62: Normal-Modus = WSJT-X-Standard (manuelle TX-Frequenz, Klick im Histogramm)
- v0.63: 20m FT8 PDF (DE+EN) + Stats-Filter (nur 20m+40m FT8)
- v0.64: Aging-Bug-Fix — Aging in Slots statt Sekunden (FT2 jetzt sauber)
- v0.65: CSV-Export Diversity-Daten + UI-Integration im Settings-Dialog
- v0.66: Richtungs-Karte mit RX/TX-Toggle (Azimuthal-Karte, Coastlines, 16
  Sektoren à 22.5°, RX-Live-Layer aus mw_cycle, TX-Modus mit PSK-Reporter,
  Settings-Button); 10 atomare Commits, +141 Tests, alle Module DeepSeek-reviewed
- 361 Tests grün

**Naechste Features (siehe TODO.md fuer Details):**
- B) Band-Indikatoren live mit PSK-Reporter ergaenzen (1-2 Tage)
- C) Richtungs-Keulen TX-Pattern-Karte (2-3 Tage) — USP-Killer
- D) Richtungs-Keulen ANT2 RX-Rescue (1-2 Tage zusaetzlich)
- F) Audio-Export per Slot (<1 Tag, optional)

**OFFEN AUS ALTER TODO-LISTE:**
1. **Even/Odd dedizierter Timer** — unabhaengig vom Decoder-Thread (FT2 kritischsten)
2. **Gain-Bias beheben** — Normal-Modus Gain-Messung wenn Stats aktiv erzwingen
3. **CQ-Zusammenfassung RX-Liste** — DeepSeek-Idee: ins QSO-Panel verschieben oder ganz raus
4. **Tertile-Analyse Statistik** — kein Datencropping, alle Werte in 3 Drittel
5. **AP-Lite Test-Pipeline** — synthetische E2E-Tests vor jedem Code-Fix
6. **Per-Station DT-Offset TX** — encoder._station_dt_offset (erst nach mehr Feldtest-Daten)
7. **IC-7300 Fork** — TARGET_TX_OFFSET dort separat messen!
8. **Warteliste-Screenshot** — sobald DL3AQJ antwortet

**VERMUTLICHER BUG (beobachten):**
- TX-Frequenz Normal-Modus manchmal ohne Histogramm-Marker — noch nicht reproduzierbar

---

## Bekannte Fallen & Bugs

- **cache.save() nie im Cycle-Loop** — refresht Timestamp → 2h Gültigkeit wird sinnlos
- **_diversity_in_operate vergessen** — once-only Code läuft sonst jeden Zyklus
- **Gain-Messung** — sperrt GUI always-on-top; TX vorher stoppen
- **Stats Warmup** — `_stats_warmup_cycles` an mehreren Stellen in mw_radio.py
- **Statusbar Race** — nach Radio-Connect kurz unsichtbar; Workaround: QTimer.singleShot(200, ...)
- **_r_hline existiert nicht mehr** — ersetzt durch `_chline` in generate_plots.py (nie wieder einbauen)
- **`_tune_active` + `_tune_freq_mhz`** — in `main_window.__init__` initialisiert; `_update_statusbar()` liest beide für `TUNE: xx kHz` Anzeige
- **CQ set_cq_active()** — muss immer wenn `cq_mode=True` aufgerufen werden, nicht nur in CQ_CALLING/CQ_WAIT (sonst bleibt Button nach QSO visuell inaktiv)
- **DT_BUFFER_OFFSET** — FT8=2.0, FT4=1.0, FT2=0.8 (WSJT-X 0.5s eingerechnet!) — bei Modus-Änderungen immer prüfen
- **TARGET_TX_OFFSET = -0.8** — FlexRadio-spezifisch! IC-7300 Fork braucht eigenen Wert
- **dt_corrections.json Key-Format** — "FT8_20m" (Modus_Band), Migration von "FT8" automatisch
- **_was_cq Bug (gefixt)** — `_on_station_clicked` rief `stop_cq()` VOR `start_qso()` → `_was_cq=False` → CQ resumte nicht nach manuellem QSO; Fix: `_cq_was_active` vor stop_cq() sichern, nach start_qso() als `_was_cq=True` setzen
- **Stats Guard (3-fach)** — `btn_cq.isChecked()` + `cq_mode` + `state not in IDLE/TIMEOUT` → robuster gegen desynchronisierte States
- **Histogramm-/Freq-View Update muss IMMER pro Slot laufen** (v0.59 Punkt 3 / P1-Bug-Fix). Niemals einen `if messages:` Guard um `_refresh_diversity_freq_view()` legen — sonst Counter-Drift, hängende Anzeige, TX-Position veraltet
- **CQ-Such-Periode = 60 s konstant** alle Modi (DeepSeek + WSJT-X-Praxis: < 30 s killt QSO-Aufbau weil antwortende Station auf alter TX-Frequenz fixiert ist)
- **`SWEET_SPOT_MIN_HZ`/`MAX_HZ` Klassenkonstanten gibt's NICHT mehr** (v0.58-Sackgasse, v0.59 entfernt). Falls in altem Code Verweis auftaucht: Suchbereich ist dynamisch, nicht fest
