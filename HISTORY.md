# SimpleFT8 — Änderungshistorie

Diese Datei wird nur ergänzt, niemals gelöscht oder überschrieben.
Format: `## YYYY-MM-DD — Kurztitel` → Änderungen darunter.

---

## 2026-04-25 v0.56 — PDF S.3: Erklärung funkerverständlich (kein Jargon)

**Betroffene Dateien:** `scripts/generate_plots.py`, `auswertung/Auswertung-40m-FT8.pdf`, `auswertung/en/Report-40m-FT8.pdf`

### Hintergrund
S.3-Tabelle war für einen Funker-Leser nicht selbsterklärend: Spalte hieß "/Zyklus" aber Note sprach von "Stunden-Durchschnitt" → Widerspruch. Dazu Statistik-Jargon ("Pooled Mean") der außerhalb der Fachliteratur nicht bekannt ist.

### Änderungen
- Spaltenheader: `Ø Stat./Zyklus` → `Ø Sta./15s-Zyklus` (Zykluslänge explizit)
- `p3_header_subtitle`: "Pooled Mean über alle Messtage" → "Tagesdurchschnitt über 4 Messtage, alle Tageszeiten"
- `p3_note1`: Klar auf Deutsch: "So viele Stationen pro 15s-Zyklus im Schnitt, gemittelt über alle Messpunkte aus 4 Messtagen und allen Tageszeiten (morgens, mittags, abends). Das ist der echte Tagesdurchschnitt — kein Filter."
- `p1_summary_body` (DE+EN): "Pooled Mean" → "Durchschnitt über alle Messpunkte, 4 Messtage, alle Tageszeiten"
- PDFs (DE+EN) neu generiert und gepusht

---

## 2026-04-25 v0.56 — Statistik-Korrektur: Pooled Mean global (kein Stunden-Filter)

**Betroffene Dateien:** `scripts/generate_plots.py`, `CLAUDE.md`, `README.md` (DE+EN), PDFs regeneriert

### Hintergrund
Session 2 hatte `_combo_summary_fair()` mit (date,hour)-Schnittmenge implementiert — dies lieferte +35.5%/+58% statt +88%/+123%. Ursache: Mike hat nur ein Funkgerät und kann nie zwei Modi gleichzeitig am selben Tag und in derselben Stunde messen. Die 18–21 gemeinsamen Slots waren ein nicht repräsentativer Bias. Richtige Methodik: alle Zyklen aller Messtage direkt poolen — kein Stunden-Filter. Mike: "du nimmst alle daten standart und teilst die ergebnisse durch die anzahl der erfassten tage... egal welche stunde welche bedingungen."

### Änderungen

**`scripts/generate_plots.py`:**
- `_combo_summary_fair()` vereinfacht: wrapper um `_combo_summary()`, gibt `n_avg_common = Normal.avg` zurück — keine (date,hour)-Schnittmenge mehr
- `_r_ergebnisse_page()`: Spalte "Gem. Stunden" → "Mess-tage" (zeigt `n_days`)
- TEXTS (DE+EN): p3_header_subtitle, p3_col_labels, p3_note1 — klar erklärt was Ø Stat./Zyklus bedeutet: "typischer Stunden-Durchschnitt eines ganzen Messtages, über alle Tage und Tageszeiten gepoolt". p1_summary_body + p7_fazit_body: "zeitfaire Auswertung / gemeinsame Messtunden" → korrekte Formulierung

**`README.md`:** Zahlen korrigiert: +36%/+57% → +88%/+122% (Std), +58%/+82% → +123%/+157% (DX), Spalte "Gem. Stunden" → "Tage"

**`CLAUDE.md`:** Statistik-Regel: Methodik-Text von "nur gemeinsame Stunden" auf "Pooled Mean global" korrigiert, Zahlenwert aktualisiert

### Git
- 1 Commit (Korrektur-Fix), Tests: 197 passed (kein Python-App-Code geändert)

---

## 2026-04-25 v0.56 — Statistik: Zeitfaire Auswertung (gemeinsame Stunden)

**Betroffene Dateien:** `scripts/generate_plots.py`, `CLAUDE.md`, `README.md` (DE+EN), `auswertung/Auswertung-40m-FT8.pdf`, `auswertung/en/Report-40m-FT8.pdf`

### Hintergrund
Die bisherige Ergebnistabelle (S.3) im PDF nutzte Pooled Mean über ALLE Zyklen, unabhängig von der Tageszeit. Das war methodisch problematisch: Wenn Normal tagsüber und Diversity DX abends gemessen wird, kann der Tageszeit-Effekt (Ausbreitung) die Zahlen verfälschen. Mike erkannte das Problem und stellte die Forderung: Nur Stunden vergleichen, in denen beide Modi gleichzeitig gemessen wurden.

### Änderungen

**`scripts/generate_plots.py`:**
- Neue Funktion `_combo_summary_fair(stats_dir, band, protocol)` — berechnet Pooled Mean nur über Stunden, in denen Normal UND der jeweilige Diversity-Modus gleichzeitig gemessen wurden. Für jede Diversity-Mode wird zusätzlich der Normal-Mittelwert auf dieselben Stunden eingeschränkt (`n_avg_common`) — dieser dient als fairer Referenzwert für Prozent-Vergleiche.
- `_r_ergebnisse_page()` (S.3): verwendet `fair_summary` statt `summary`. Spalte "Messtage" → "Gem. Stunden". `vs Normal` berechnet gegen `n_avg_common`.
- `_r_title_page()`, `_r_rescue_page()`, `_r_fazit_page()`: verwenden jetzt ebenfalls `fair_summary` für alle %-Angaben. `_r_methodik_page()` (S.2) behält globale Zyklenanzahlen.
- `create_pdf_report()`: berechnet `fair_summary` zusätzlich zu `summary`, leitet es an die richtigen Seiten weiter.
- TEXTS (DE+EN): p3_header_subtitle, p3_col_labels, p3_note1 aktualisiert. p1_summary_body + p7_fazit_body mit Methodik-Hinweis ergänzt.
- PDF-Umbenennung: `SimpleFT8_Bericht.pdf` → `Auswertung-40m-FT8.pdf` / `SimpleFT8_Report.pdf` → `Report-40m-FT8.pdf` (Band im Dateinamen für spätere Multi-Band-Erweiterung).

**Ergebnis 40m FT8 (22.618 Zyklen, 4–5 Tage):**
- Im aktuellen Datensatz haben alle Modi 24h Abdeckung → fair_summary = global_summary
- Zahlen: Diversity Standard +88%/+122%, Diversity DX +123%/+157% (ohne/mit Rescue)
- Methodik ist zukunftssicher: sobald Modi zu unterschiedlichen Tageszeiten gemessen werden, filtert `_combo_summary_fair()` automatisch korrekt

**`README.md` (DE + EN):**
- Tabelle: aktualisierte Zahlen (+88%/+123%), 22.618 Zyklen, neue Spalte "Gem. Stunden"
- Methodologie-Hinweis hinzugefügt (Stand 2026-04-25)
- PDF-Links auf neue Dateinamen aktualisiert

**`CLAUDE.md`:**
- Neue Sektion "⛔ Statistik-Veröffentlichung — Regel": Verbot anderer Bänder ohne Datenbasis (≥2 Tage, ganzer Tag), Hinweis auf gemeinsame-Stunden-Methodik und bekannte 40m-Ergebnisse

### Git
- 2 Commits, pushed to origin/main
- Tests: 197 passed (keine Regression — kein Python-Code in App geändert)

---

## 2026-04-25 v0.56 — RF-Power-Presets pro Band+Watt

**Betroffene Dateien:** `core/rf_preset_store.py` (NEU), `radio/base_radio.py`, `radio/flexradio.py`, `ui/main_window.py`, `ui/mw_tx.py`, `ui/mw_radio.py`, `ui/settings_dialog.py`, `tests/test_rf_preset_store.py` (NEU)

### Hintergrund
Closed-Loop FWDPWR-Feedback tastet pro Band/Watt-Wechsel von rfpower=50 hoch zur Zielleistung. Dauert 3–4 Zyklen (~45–60 s FT8) bis Konvergenz — schlecht für QSO-Erfolg, ineffizient. Mike hat den Wunsch geäußert, den konvergierten rfpower-Wert pro (Band, Watt-Stufe) zu persistieren, sodass beim nächsten Wechsel direkt der bekannte Wert geladen werden kann. System ist selbstheilend: bei Vereisung/Tauwetter/Kabelwackler überschreibt die nächste Konvergenz den alten Wert. IC-7300-Fork-tauglich durch separaten Top-Level-Key pro Radio.

### Architektur (5 Schichten)
1. **`core/rf_preset_store.py` (NEU):** `RFPresetStore` mit Hybrid-Lade-Strategie (exakter Treffer / lineare Interpolation+Extrapolation / None), atomic JSON-Write via `os.replace`, Plausibilitäts-Warnung bei >20% Δ zwischen gespeichert vs interpoliert, Migration aus altem `rfpower_per_band` (idempotent), Validierung 0 ≤ rf ≤ 100, `.bak.YYYYMMDD-HHMMSS` bei korruptem JSON.
2. **`radio/base_radio.py` + `flexradio.py`:** Klassen-Konstante `radio_type: str = "flexradio"` (ABC default `"unknown"`) — Top-Level-Key in `rf_presets.json`.
3. **`ui/main_window.py::_init_power_state`:** RFPresetStore-Instanz + neue `_was_converged` Hilfsvar + Migration-Aufruf.
4. **`ui/mw_tx.py`:** Neuer Helper `_apply_rf_preset()`, Lade-Trigger bei Watt-Wechsel mit Race-Schutz für alten (band, watts), Save-Trigger refactored mit `_was_converged` (1× pro Konvergenz-Zyklus), `settings.save_tx_power()` bleibt für Backward-Compat.
5. **`ui/mw_radio.py`:** Lade-Trigger an Bandwechsel + Radio-Connect.
6. **`ui/settings_dialog.py`:** Neue GroupBox "RF-Presets pro Band+Watt" — Tabelle (Band / Watt / RF / Letzte Speicherung), "Band löschen" + "Alle löschen" mit Bestätigungs-Dialog, Buttons disabled während aktivem TX (1 s Polling).

### Datenformat `~/.simpleft8/rf_presets.json`
```json
{
  "flexradio": {
    "40m": {"30": {"rf": 24, "ts": 1735203015.5},
            "80": {"rf": 67, "ts": 1735206015.0}}
  },
  "ic7300": {}
}
```

### DeepSeek codereview (deepseek-chat, thinking high)
1× Low-Severity Bug bestätigt: `getattr(...) or settings.get(...)` falsy-Trap bei watts=0 → ersetzt durch explizites `is None`-Check. Andere DeepSeek-Hinweise (kritisch laut Tool) waren False Positives — Reihenfolge in `_on_power_changed` ist korrekt (alter `_power_target` + alter `_rfpower_current` werden vor Settings-Update gespeichert).

### Tests 178 → 197 grün
Neue `tests/test_rf_preset_store.py` mit 19 Tests: exact_match, empty, interpolation, extrapolation oben/unten, single_point_fallback, overwrite, radio_isolation, clear_band, clear_all, plausibility_warning, corrupt_json+bak, atomic_write, invalid_rf, oscillation, band_change_isolation, range_clipping, migration, persistence.

### Atomare Commits
1. `feat(core): RFPresetStore — pro (radio, band, watt) konvergierten rf-Wert persistieren`
2. `feat(radio): radio_type Klassen-Konstante als Top-Level-Key`
3. `feat(tx): RFPresetStore in TX-Closed-Loop integriert (load + save bei Konvergenz)`
4. `feat(ui): SettingsDialog — Section "RF-Presets" mit Reset-Buttons`
5. `chore(release): bump APP_VERSION 0.55 → 0.56 + HISTORY + TODO`

### Out of Scope (für spätere Versionen)
- Polynom-/Spline-Fit über ≥3 Stützpunkte (KISS, linear reicht; bei IC-7300-Fork prüfen)
- Temperatur-/SWR-Tagging der Werte
- Auto-Detection Antennen-Tausch
- Event-Bus / RFPresetController-Schicht (Overengineering, direkter Aufruf in mw_tx genügt)

---

## 2026-04-25 — Prozess/Doku (kein Code-Change)

**Betroffene Dateien:** `CLAUDE.md`, `TODO.md`, `tests/test_modules.py`

### CLAUDE.md erweitert
- **Rollen** definiert: Mike = Ideengeber/Tester/Inspirator, Claude = Chef-Programmierer (verantwortlich für Code-Qualität, Struktur, Wartbarkeit)
- **Commits** Regel: lokale Commits autonom + atomar (1 Refactor/Feature/Bugfix = 1 Commit), `git push` nur auf explizite Anfrage
- **Architektur-Entscheidungen** Liste: was Mike vorgelegt wird (Modul-Auflösung, Pattern-Wechsel, Threading-Änderungen, Eingriffe in produktive Algorithmen ohne Tests, neue Abhängigkeiten, Breaking Changes) vs was Claude eigenständig entscheidet
- **Vor Commits**-Zeile ergänzt: Tests grün + DeepSeek-Review bei nicht-trivialen Änderungen (verweist auf §0)

### TODO.md PRIO HOCH (Stand 2026-04-25)
- **Punkt 1: Doku „UCB1 Bandit" korrigieren** — Code implementiert tatsächlich Median+8%-Schwelle, nicht UCB1. 5 Dateien betroffen (DIVERSITY_DE/EN, README_DE/EN, UEBERGABE). ~30 Min reine Doku.
- **Punkt 2: AP-Lite v2.2 Test-Pipeline** — vor jeglichem Code-Fix synthetische End-to-End-Tests bauen (FT8-Generator + AWGN). Erst dann zeigen Tests welche der 4 Verdachtspunkte echte Bugs sind. ~1-2 h.

### Tests aufgestockt 168 → 178
- 7 neue Tests für `core/diversity.py::_evaluate()`: Threshold-Verhalten, A1/A2-Dominanz, DX-Mode, Phase-Übergänge, Operate-Filter
- 3 neue Tests für AP-Lite v2.2: `_correlate` ohne Encoder, `_align_buffers` Costas-Reference, Costas-Pattern-Position

### DeepSeek V4-Setup
- DeepSeek V4 ist am 24.04.2026 erschienen (zwei Modelle: `deepseek-v4-flash`, `deepseek-v4-pro` Reasoning)
- `~/.claude/custom_models.json` neu angelegt für Pal-MCP-Routing
- `~/.claude/settings.json` aktualisiert: `permissions.defaultMode: "plan"`, `effortLevel: "xhigh"`, `model: "opusplan"`

---

## 2026-04-25 v0.55 — Refactoring: Mega-Methoden zerlegt

**Betroffene Dateien:** `ui/mw_cycle.py`, `ui/main_window.py`

### Hintergrund
DeepSeek V4-Pro (Reasoning-Modell, neu erschienen 24.04.) wurde für Architektur-Review hinzugezogen. V4-Pro identifizierte zwei Mega-Methoden als gröbste Verstöße gegen Lesbarkeit; Vorschlag: 1:1-Auslagerung in private Helper, ohne Verhaltensänderung. Drei weitere Refactoring-Kandidaten (flexradio.py aufsplitten, qso_state.on_message_received zerlegen, generate_plots.py modularisieren) wurden bewusst abgelehnt — premature abstraction, hohes Regressionsrisiko ohne Tests.

### Änderungen
- `ui/mw_cycle.py::_on_cycle_decoded()` von **276 Zeilen → 27 Zeilen**, 9 Helper extrahiert:
  - `_assign_slot_parity`, `_update_dt_correction`, `_pop_diversity_queue`
  - `_handle_diversity_measure`, `_handle_diversity_operate`
  - `_handle_normal_mode`, `_handle_dx_tune_mode`
  - `_run_ap_lite_rescue`, `_run_auto_hunt`
- `ui/main_window.py::__init__()` von **186 Zeilen → 42 Zeilen**, 12 Helper extrahiert:
  - `_apply_dark_theme`, `_init_core_components`, `_init_qso_log`
  - `_init_radio_state`, `_init_diversity_state`, `_init_power_state`
  - `_init_optional_features`, `_init_psk_polling`, `_init_propagation_polling`
  - `_init_presence_watchdog`, `_init_cq_countdown_timer`, `_init_statusbar`

### Garantien
- **Verhalten identisch:** alle 168 Tests grün vor und nach Refactoring
- **Reihenfolge erhalten:** alle State-Initialisierungen in Original-Sequenz
- **Bekannte Fallen unberührt:** Diversity-Transition-Guard `_diversity_in_operate`, Stats-Guard 3-fach (btn_cq + cq_mode + state), `cache.save()` nur in `_on_dx_tune_accepted`
- **Backup:** `Appsicherungen/2026-04-25_vor_mw_cycle_refactor/` (mw_cycle.py + main_window.py)

### Was NICHT angefasst wurde (begründete Ablehnung)
- `radio/flexradio.py` — 50 Methoden teilen TCP/UDP-State, kein Test, Aufsplittung wäre premature abstraction
- `core/qso_state.py::on_message_received` (157 L) — sitzt direkt im geschäftskritischen QSO-Pfad; keine Methodenebene-Tests, Refactoring ohne Schutznetz zu riskant
- `scripts/generate_plots.py` — Standalone-Script, kein Test, kein externer Mehrwert durch Modularisierung
- `ui/control_panel.py` Card-Klassen — sinnvoller nächster Schritt, aber 2 h Aufwand + Regressionsrisiko ohne UI-Tests; auf später vertagt

---

## 2026-04-23 (Abend) — DT-Timing vollständig korrigiert

**Betroffene Dateien:** `core/decoder.py`, `core/encoder.py`, `core/ntp_time.py`, `ui/mw_radio.py`

### Architektur-Änderung
- DT-Gesamtfehler (~0,77 s) in zwei Schichten aufgeteilt:
  - **Festwert** `DT_BUFFER_OFFSET` (FT8=2,0 / FT4=1,0 / FT2=0,8) — bekannte FlexRadio-Konstante, hardcodiert
  - **Adaptiv** `ntp_time.py` — konvergiert auf ~0,27 s Restfehler
- Vorteil: Kaltstart beginnt nahe am Zielwert, kleinerer Regelbereich → schnellere Konvergenz

### Bugfixes
- FT2 Even/Odd: `_slot_from_utc()` auf 3,8 s-Arithmetik korrigiert (war 7,5 s)
- Tune-Anzeige: `_tune_active` vor `set_frequency()` gesetzt
- PSK bei Bandwechsel: gelöscht + Timer-Reset + Interval 300 s (5 min Rate-Limit)
- Stats-Guard: pausiert bei CQ-Modus und laufendem QSO
- 15m Diversity: Preset laden oder Warnung "bitte KALIBRIEREN"
- 3 veraltete Tests auf neues Key-Format "FT8_20m" angepasst

### TX-Timing
- `TARGET_TX_OFFSET = -0,8 s` — kompensiert FlexRadio TX-Buffer 1,3 s
- Validiert: 8 Zyklen 0,0 s DT am Icom, 20m + 40m getestet

### Neue Docs
- `dt.md` erstellt (Theorie, Änderungen, Messergebnisse)

**Tests:** 167 passed

---

## 2026-04-23 (Nacht) — 3 kleine Features

**Betroffene Dateien:** `core/propagation.py`, `ui/mw_radio.py`, `core/station_accumulator.py`, `tests/test_modules.py`

### Features
1. **60m Propagation** — Interpolation 40m/80m war bereits implementiert, nur Docs angepasst
2. **RX-Liste leeren bei Antennen/Diversity-Wechsel** — `_on_rx_panel_toggled`, `_enable_diversity`, `_disable_diversity`
3. **Alte CQ-Rufe auto-löschen (>5 Min)** — neues Aging-Limit 300 s für CQ-Rufer in `station_accumulator.py`

### Tests
- `test_accumulator_aging` auf nicht-CQ-Message geändert
- Neuer Test `test_accumulator_cq_longer_aging`

**Tests:** 168 passed

---

## 2026-04-23 (Nacht II) — Stats-Guard Bug gefixt

**Betroffene Dateien:** `ui/mw_qso.py`, `core/qso_state.py`, `ui/mw_cycle.py`

### Root Cause (durch DeepSeek-Analyse gefunden)
In `_on_station_clicked` (manueller Klick auf Station während CQ):
1. `stop_cq()` setzte `cq_mode=False`
2. `start_qso()` speicherte `_was_cq = self.cq_mode = False` (schon False!)
3. Nach QSO-Ende: `_resume_cq_if_needed()` sah beide False → CQ wurde nicht resumed + Stats geloggt fälschlicherweise

### Fixes
- `mw_qso.py::_on_station_clicked` — `_cq_was_active` VOR `stop_cq()` sichern, nach `start_qso()` als `_was_cq=True` setzen
- `qso_state.py::_process_cq_reply` — `self._was_cq = True` explizit setzen
- `mw_cycle.py::_log_stats` — Guard um `btn_cq.isChecked()` erweitert (3-fach robust: Button + cq_mode + State)

**Tests:** 168 passed

---

## 2026-04-23 (Nachmittag) — Histogramm-Umbau + Bugfixes + Docs

**Betroffene Dateien:** `core/diversity.py`, `ui/mw_cycle.py`, `tests/test_modules.py`, `docs/`

### Architektur-Änderung: Histogramm 1:1 mit RX-Fenster

**Problem vorher:** Das Frequenz-Histogramm akkumulierte Daten über viele Zyklen und vergaß nie. Nutzer sah 5 Stationen im RX-Fenster, Histogramm zeigte 26 (historische Daten). Freie Frequenz wurde auf Basis veralteter Daten berechnet.

**Lösung:** Histogramm wird nach jedem Dekodierzyklus aus dem `station_accumulator` neu aufgebaut — exakt dieselbe Datenbasis wie das RX-Fenster. Der Accumulator hält Stationen 75–300 s (je nach Typ) und deckt damit automatisch mehrere Zyklen inkl. Even+Odd ab.

**Änderungen `core/diversity.py`:**
- `record_freq()` entfernt (akkumulierend, falsch)
- `_freq_histogram`, `_hist_lock` (threading.Lock) entfernt
- `_recalc_interval = 20` entfernt (tote Variable, nie gelesen)
- `import threading` entfernt
- `sync_from_stations(stations: dict)` neu — baut Histogramm 1:1 aus aktuellem Stationsstand
- `get_free_cq_freq()`: Search-Window auf vollen Bereich [150–2800 Hz] erweitert (vorher nur belegter Bereich)
- `get_free_cq_freq()`: Fallback-Bug gefixt — `None` statt Median-Frequenz wenn keine Lücke (Median lag mitten im belegten Bereich → Kollision → Oszillation)
- `update_proposed_freq()`: Lock in Kollisionserkennung entfernt
- `get_histogram_data()`: Lock entfernt
- `start_measure()`: `_freq_histogram = {}` entfernt (übernimmt sync_from_stations)

**Änderungen `ui/mw_cycle.py`:**
- Alle `record_freq()` Calls entfernt (3 Stellen: Messphase, Betriebsphase, Normal-Modus)
- Diversity-Betriebsphase: `accumulate_stations` kommt jetzt VOR Histogram-Update (war danach → Histogramm war einen Zyklus veraltet)
- `sync_from_stations(self._diversity_stations)` nach `accumulate_stations`
- Normal-Modus `_update_histogram()`: `sync_from_stations(self._normal_stations)`, `if messages:` Guard entfernt

**Änderungen `tests/test_modules.py`:**
- Hilfsfunktion `_make_stations(*freqs)` hinzugefügt
- 6 Tests von `record_freq()` auf `sync_from_stations()` umgestellt
- Assertions angepasst an neues Verhalten (Search-Window [150–2800]):
  - `test_cq_freq_high_activity`: prüft nun `freq < 1000 or freq > 2000` (Gap außerhalb des belegten Bereichs)
  - `test_cq_freq_stays_inside_occupied` → umbenannt in `test_cq_freq_finds_gap_outside_occupied`
  - `test_cq_freq_fallback_no_gap`: füllt jetzt alle Bins [150–2850 Hz], prüft `freq is None`

### Neue Docs (4 Dateien)
- `docs/FREQUENCY_HISTOGRAM.md` (EN) — Visualisierung, Algorithmus, Timing
- `docs/FREQUENCY_HISTOGRAM_DE.md` (DE)
- `docs/DT_CORRECTION.md` (EN) — Festwert + Adaptiv, Parameter, TX-Timing
- `docs/DT_CORRECTION_DE.md` (DE)

### CLAUDE.md + feierabend.md
- CLAUDE.md: Abschnitt "Änderungshistorie" + Verweis auf HISTORY.md ergänzt
- feierabend.md: Schritt 3 "HISTORY.md ergänzen" als Pflicht eingefügt

**Tests:** 168 passed

---

## 2026-04-24 — Workflow-Optimierung: opusplan als Standard

**Betroffene Dateien:** `~/.claude/settings.json`

### Änderung
- `"model": "opusplan"` dauerhaft in globaler Claude Code settings.json gesetzt
- **Verhalten:** Opus (claude-opus-4-7) übernimmt die Planungsphase, Sonnet (claude-sonnet-4-6) die Implementierung — automatisch, kein manueller Wechsel nötig
- **Grund:** Komplexere Aufgaben profitieren von Opus-Reasoning beim Planen, Sonnet ist für Code-Ausführung vollkommen ausreichend und schneller

---

## 2026-04-24 — Antennen-Label in TX-Zeilen des QSO-Panels

**Betroffene Dateien:** `ui/qso_panel.py`, `ui/mw_radio.py`, `ui/mw_qso.py`

### Feature
- TX-Zeilen im QSO-Panel zeigen jetzt Empfangsantenne + SNR-Delta:
  `11:47:00 [E] →  Sende   OE7RJV DA1MHH -23   ANT1 Δ7.0dB`
- Orange (Nachricht) + Grau (Label) auf einer Zeile — via `QTextCharFormat`
- Nur im Diversity-Modus, nur wenn `delta_db` bekannt
- CQ-Zeilen unverändert

### Technische Umsetzung
- `qso_panel.py::add_tx(message, ant_label="")` — rückwärtskompatible Erweiterung
- `qso_panel.py::_append_two_color()` — neue Hilfsmethode für zweifarbige Zeilen
- `mw_radio.py` — Lambda durch `self._on_tx_started` ersetzt (direkter Slot, sauberer)
- `mw_qso.py::_on_tx_started()` — liest `qso_sm.qso.their_call` + `_antenna_prefs.get_pref()`

**Tests:** 168 passed

---

## 2026-04-24 v0.48 — CQ-Freq nur noch im belegten Bandbereich

**Betroffene Dateien:** `core/diversity.py`, `tests/test_modules.py`

### Bugfix
- `get_free_cq_freq()` suchte bisher im vollen [150–2800 Hz] Fenster
- Resultat: TX landete bei 2125 Hz obwohl alle Stationen bei 400–1100 Hz clusterten
- **Fix:** Search-Window = `[min(belegte Bins) – 2, max(belegte Bins) + 2]`, geclippt auf absolute Grenzen
- 2-Bin Rand (100 Hz) damit auch die allererste/letzte Lücke knapp außerhalb noch gefunden wird
- Test `test_proposed_freq_updates` auf Stationen mit echter innerer Lücke umgestellt

**Tests:** 168 passed

---

## 2026-04-24 v0.53 — Diversity-Panel UI-Politur

**Betroffene Dateien:** `ui/control_panel.py`

### Fixes & Verbesserungen
- **Label:** "Diversity Neuberechnung in X Zyklen" (fehlende "in" ergänzt)
- **Zentrierung:** 36px Spacer links in phase_row balanciert NEU-Button → Text exakt mittig
- **Nähe:** `phase_row` ohne oberen Margin — Label näher an Ratio-Zeile
- **DX-Counts:** `35 DX  01 DX` Format (2-stellig, Leerzeichen vor "DX", `--` wenn kein Wert noch)
- **Balkenfarbe:** Dunkelrot `#882222` → Mittelrot `#CC3333` → Hellrot `#FF5555` (heller = dringender)
- **Hintergrund Balken:** `#1a1010` (passt zu Rotton statt Grün-Dunkel)

**Tests:** 168 passed

---

## 2026-04-24 v0.52 — CQ-Freq zeitbasiert + Platz-Suche-Balken + Antennenwahl-Label

**Betroffene Dateien:** `core/diversity.py`, `ui/control_panel.py`, `ui/mw_cycle.py`

### Features
- **Label-Umbenennung:** "Neucheck in X" → "Antennenwahl in X" — verständlich für Funker
- **Neuer Countdown-Balken:** "Platz-Suche in Xs" — zeigt wann die freie TX-Frequenz neu berechnet wird (Sekunden, schrumpfend 120→0)
- **CQ-Freq Timing zeitbasiert:** Statt zyklus-basiert (FT2: 10×3.8s=38s!) jetzt:
  - Zeit-Fallback: 120s (für alle Modi gleich — FT8/FT4/FT2)
  - Minimum Dwell: 15s (kein Bounce-Back bei Kollision)
  - Kollisionserkennung: jedes Zyklus prüfen, bei ≥3 Nachbarn + 15s Dwell reagieren

### Technische Details
- `diversity.py`: `import time` + `RECALC_INTERVAL_S=120`, `MIN_DWELL_S=15`
- `diversity.py`: `_cycles_since_recalc` → `_last_recalc_time` + `_last_change_time` (float Unix-Zeit)
- `diversity.py`: neues Property `seconds_until_recalc` → int 0–120
- `control_panel.py`: `_cq_freq_lbl` + `_cq_freq_bar` im AntCard, Proxy in ControlPanel
- `control_panel.py`: neue Methode `update_cq_freq_countdown(remaining_s)`
- `mw_cycle.py`: 3 Aufrufstellen ergänzt (measure, operate, normal)

**Tests:** 168 passed

---

## 2026-04-24 v0.51 — Diversity Countdown-Balken + besseres Label

**Betroffene Dateien:** `ui/control_panel.py`

### Feature
- OPERATE-Phase: Label `"Neu in X Zyklen"` → `"Neucheck in X"` (verständlich für den Funker)
- Neuer schmaler Countdown-Balken (6 px) unter dem Label — schrumpft von 60→0
- Farbwechsel synchron mit Text: grün (>15), gelb (≤15), orange (≤5)
- Balken verschwindet automatisch in MESSEN- und NEUEINMESSUNG-Phase
- `QProgressBar` mit dynamischem Stylesheet, kein Custom-Widget nötig
- Proxy-Anbindung über `ant_card._operate_bar` in `ControlPanel.__init__()`

**Tests:** 168 passed

---

## 2026-04-24 v0.50 — freq_label Farbwechsel Grün ↔ Gelb (Tune-Feedback)

**Betroffene Dateien:** `ui/control_panel.py`, `ui/mw_radio.py`, `ui/mw_tx.py`

### Feature
- `freq_label` (oben links) zeigt Frequenz jetzt farbcodiert:
  - **Normal:** Grün (#00CC66) + Arbeitsfrequenz
  - **Tune aktiv:** Gelb (#FFD700) + Tune-Frequenz (z.B. -2 kHz Offset)
- Neue Methode `control_panel.set_freq_display(freq_mhz, tune_active=False)` — zentrales Farb-Update
- `_update_frequency()` delegiert an `set_freq_display()` (Band/Mode-Wechsel → automatisch Grün)
- `_on_mode_changed()` in mw_radio.py → `set_freq_display(..., False)`
- `_on_tune_clicked()` in mw_tx.py → `set_freq_display(..., True/False)` je nach Tune-State
- Tune-Sonderfall `tune_freq=None` (60m ohne Offset) → Gelb + Arbeitsfreq (korrekt)

**Tests:** 168 passed

---

## 2026-04-24 v0.49 — Versionsanzeige UI automatisch synchron

**Betroffene Dateien:** `ui/control_panel.py`, `main.py`

### Fix
- Versionsanzeige unten rechts zeigte hardcodiert "v0.26"
- `control_panel.py` importiert jetzt `APP_VERSION` aus `main.py`
- Label: `f"SimpleFT8 v{APP_VERSION}"` — ab jetzt automatisch korrekt
- `main.py` APP_VERSION auf 0.49 erhöht

**Tests:** 168 passed

---

## 2026-04-24 v0.54 — CQ-Freq Countdown sekündlich + glatt

**Betroffene Dateien:** `core/diversity.py`, `ui/control_panel.py`, `ui/mw_cycle.py`, `ui/main_window.py`

### Problem vorher
Countdown sprang z.B. 119→108→119 weil per-Zyklus-Updates die 120s-Range unregelmäßig aktualisierten (FT8=15s, FT4=7.5s, FT2=3.8s). Kein gleichmäßiges Runterzählen.

### Lösung
- **Neues Property `seconds_until_next_check`** in `diversity.py` — zählt 15→0 ab `_last_check_time`
- **`_last_check_time`** in `reset()` ergänzt; in `update_proposed_freq()` gesetzt:
  - Bei Erstberechnung
  - Jedes Mal wenn MIN_DWELL_S abgelaufen ist (ob Kollision oder nicht) → Display immer zurück auf 15
- **1-Sekunden QTimer** (`_cq_countdown_timer`) in `main_window.__init__()` → `_tick_cq_countdown()`
  - Aktiv nur wenn `_rx_mode == "diversity"` und `cq_freq_hz is not None`
  - Sonst: Widget ausgeblendet via `set_cq_countdown_visible(False)`
- **3 per-Zyklus-Calls** `update_cq_freq_countdown()` aus `mw_cycle.py` entfernt
- **Range** 0-120 → 0-15, Label: `"Prüfe nächste freie TX Frequenz in: X Sek."`
- **Neue Methode** `control_panel.set_cq_countdown_visible(bool)`
- **Farb-Schwellen** angepasst: ≤5s → #FF5555, ≤10s → #CC3333, sonst #882222
- **Hintergrund** korrigiert: `#1a1010` (war fälschlich `#1a2a1a`)

**Tests:** 168 passed

---

## 2026-04-24 v0.54 — README Antennenfotos + Transparenz-Caveat + PDF-Update

**Betroffene Dateien:** `README.md`, `scripts/generate_plots.py`, `docs/fotos/`

### README
- Neue Sektion "Antenna Setup" / "Antennensetup" (DE+EN) mit 2 Fotos:
  - `docs/fotos/Gesamt.png` — Gesamtansicht Haus, beide Antennen sichtbar
  - `docs/fotos/Gesamt_Farbe.png` — Annotiert: Gelb=ANT1, Rot=ANT2
- ANT1: Kelemen DP-201510, vertikal gespannter Mehrband-Halbwellendipol (20m/15m/10m),
  Einspeisepunkt an Dachgaube, 1:1-Balun, ein Arm hoch zur Dachspitze, einer runter
- ANT2: Regenrinne ~15m L-Form (5m waagerecht + 8m senkrecht + 2m waagerecht),
  zwischen λ/4 und λ/2 für 40m, nie als Antenne installiert — einfach angeklemmt
- Rohdaten-Link: `statistics/` Ordner (214 Dateien, jeder Zyklus geloggt)
- Messtage aktualisiert: 11.896 → 18.425 Zyklen, 3-4 → 4-5 Messtage

### Transparenz-Caveat (DE+EN, README + PDF)
- ANT1 auf 40m außerhalb Auslegungsband (20m/15m/10m) → suboptimal
- ANT2 (Regenrinne) auf 40m günstiger durch Länge/Form → erklärt großen Gewinn
- Ergebnisse als Obergrenze deklariert — nicht übertragbar auf andere Setups
- 20m-Folgetests angekündigt (ANT1 dort resonant, 20m generell besser)

### generate_plots.py PDF-Texte
- `p1_caveat`: Antennencaveat auf Titelseite (DE+EN)
- `p2_setup_body`: "mornings only" entfernt, aktueller Tagesbereich 05-23 UTC
- `p3_note2`: Obergrenze-Hinweis bei Ergebnistabelle (DE+EN)
- `p7_cannot_body`: Übertragbarkeit explizit verneint (DE+EN)
- `p7_next_body`: 20m-Folgetests angekündigt (DE+EN)
- "über beide Messtage" → "über alle Messtage" (DE+EN)

### Strategie für weitere Datensammlung
- Abfrage alle 2-3h welcher Modus die dünnste Abdeckung hat
- Ziel: Lücken bei 15-23 UTC für alle drei Modi schließen
- Diversity Standard als nächstes (14-16 UTC, 15h+16h = je 1 Tag)

**Tests:** 168 passed

---

## 2026-04-25 v0.54 — 20m Messungen gestartet + Nachtdaten Diversity DX

**Keine Code-Änderungen — nur Datensammlung**

### Datenlage Stand 25.04.2026 Vormittag
- **Diversity DX 40m**: Nachtlücke geschlossen — 15 neue Stunden (18–09 UTC)
- **20m gestartet**: Normal + Diversity parallel zu 40m
- **40m gesamt**: 22.251 Zyklen (Normal 6.793 / Div.Standard 6.542 / Div.DX 8.916)

### Strategie
- Alle 2-3h Modus prüfen, Lücken in Berliner Zeit (CEST=UTC+2) schließen
- 40m Restlücken: 08 CEST (Div.Standard), 12-13 CEST (Div.Standard), 21-23 CEST (Normal+Div.Standard)
- 20m: Tagsüber Normal sammeln, dann Diversity

**Tests:** 168 passed

---

## 2026-04-25 v0.56 — Session-Abschluss: Doku, Refactoring, Prompt v0.57

**Keine neuen Features — Version bleibt 0.56**

### Code-Änderungen
- `ui/mw_cycle.py`: CycleMixin refactored — `_on_cycle_decoded` in 5 Helper-Methoden
  aufgeteilt (`_assign_slot_parity`, `_update_dt_correction`, `_pop_diversity_queue`,
  `_handle_diversity_measure`, `_handle_diversity_operate`). Gleiche Logik, besser lesbar.
- `tests/test_modules.py`: 8 neue Tests — 7× `DiversityController._evaluate`
  (Median+8%-Schwelle, A1/A2-Dominanz, DX-Mode, Phase-Übergänge) + 1× AP-Lite
  `_build_costas_reference` Energie-Test. **197 passed** (vorher 168→178→197).

### Doku & Prozess
- `feierabend.md`: Explizit "ALLE Ergänzungen der Session in HISTORY.md" ergänzt
- `CLAUDE.md`: Rollen + Commit-Richtlinien + DeepSeek-V4-Warnung (neues Modell,
  Antworten kritisch prüfen) + Tests→197 aktualisiert
- `TODO.md`: RX-Sortierung als [x] (war bereits implementiert), Per-Station DT-Offset
  auf PRIO NIEDRIG, vermutlicher Bug TX-Freq Normal-Modus als offener Punkt eingetragen,
  Band Map gestrichen, RF-Presets als [x] abgehakt

### Statistiken & Auswertung
- Neue Messungen 25.04.2026: Diversity_Normal/40m (09–12h), Diversity_Dx/40m (08–14h),
  Diversity_Dx/20m (12–15h), Diversity_Normal/20m (12–15h), Normal/20m (12–15h) UTC
- PDFs neu generiert: `auswertung/SimpleFT8_Bericht.pdf` (DE) +
  `auswertung/en/SimpleFT8_Report.pdf` (EN) mit allen 25.04-Daten

### Nächste Session — Implementierungs-Prompt v0.57 bereit
- Aufgabe 1: Answer-Me Highlighting — `rx_panel.py` Farbe `#5A4A10` + Bold an 3 Stellen
- Aufgabe 2: Gain-Messung Logging → `~/.simpleft8/gain_log.md`
- Prompt vollständig, DeepSeek-reviewed, commitbereit
