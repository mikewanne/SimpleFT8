# SimpleFT8 TODO — Stand 15.04.2026, Session 2

---

## HEUTE ERLEDIGT (15.04.2026)

### Bugs gefixt
- [x] FT4 Einmessen: `CYCLE_SAMPLES_12K` → `self._slot_samples`
- [x] FT2 C-Library: `FTX_PROTOCOL_FT2` nativ (288 sps, kein Resample), Decodium-kompatibel bestaetigt
- [x] Diversity 50:50: Einzelmessungen, Median, 8% Schwelle, Standard/DX Modi
- [x] QSO komplett + Timeout: `WAIT_73` in Ausnahmeliste
- [x] RR73 Hoeflichkeit: max 2x wiederholen wenn Station weiter R-Report sendet
- [x] Detail-Overlay: schliesst bei Tab-Wechsel, Delete-Signal verbunden
- [x] DT-Korrektur bei Modus-Wechsel: Wert wird jetzt BEHALTEN (`keep_correction=True`)

### Neue Features
- [x] Diversity Standard/DX: Button zeigt "DIVERSITY DX", DX zaehlt schwache Stationen (SNR<-10)
- [x] Info-Dialoge: Gain-Messung + Diversity mit "Nicht mehr anzeigen"
- [x] CQ Sweet Spot: 800-2000 Hz statt gesamter Bereich
- [x] OMNI-TX: CQ-Button zeigt "OMNI CQ" wenn aktiviert
- [x] Even/Odd Spalte: "E"/"O" in RX-Liste
- [x] FT2 Frequenzen: DXZone Community-Frequenzen (40m=7.052, 20m=14.084, etc.)
- [x] RX-Filter automatisch: FT8/FT4=100-3100Hz, FT2=100-4000Hz beim Modus-Wechsel
- [x] Button "EINMESSEN" → "GAIN-MESSUNG"
- [x] DT-Korrektur beschleunigt: 2 Zyklen statt 4, 10 Betrieb statt 20, 70% Daempfung

---

## PRIO NIEDRIG — Doku/Test-Pipeline (Stand 2026-04-25)

> Mike-Entscheidung: „lassen wir so weil es super und robust schon seit Tagen läuft."
> Nur Doku korrigieren wenn ohnehin am GitHub gearbeitet wird; Test-Pipeline später,
> wenn AP-Lite real angefasst wird. Code bleibt unverändert.

### 1. Doku korrigieren: „UCB1 Bandit" ist im Code NICHT implementiert
**Betroffen:** `docs/DIVERSITY_DE.md`, `docs/DIVERSITY.md`, `README.md`, `README_DE.md` (alle GitHub-sichtbar!)

**Problem:** Doku verkauft die Diversity-Antennen-Wahl als „UCB1 (Upper Confidence Bound) Multi-Armed-Bandit". Tatsächlich implementiert `core/diversity.py::_evaluate()` jedoch **Median über 4 Messungen pro Antenne + 8 %-Schwellwert** (siehe Zeile 348-378). Kein Reward-Tracking, keine Confidence-Bound-Formel, kein kontinuierliches Lernen.

**Was tatsächlich passiert:**
- 8 Mess-Zyklen (4× A1, 4× A2)
- Median pro Antenne (robust gegen Ausreißer)
- `|s1-s2|/peak < 8%` → 50:50, sonst 70:30 zur besseren Antenne
- Nach 60 Operate-Zyklen → Neueinmessung

**Aufgabe:**
- DIVERSITY_DE.md / DIVERSITY.md: Abschnitt „UCB1 Adaptives Verhältnis" umschreiben → ehrlich „Median + 8 %-Schwellwert" benennen
- README.md / README_DE.md: gleiche Stellen prüfen + korrigieren
- UEBERGABE.md: Erwähnung „Temporal Polarization Diversity" bleibt (ist OK), nur Bandit-Sprache raus
- **Marke „Temporal Polarization Diversity" bleibt** — das Antennen-Wechsel-Konzept stimmt, nur die Bezeichnung der Entscheidungslogik ist Marketing-Quark

**Begründung Code lassen:** Aktuelle Logik läuft seit Tagen robust und stabil; UCB1 würde bei nur 2 Antennen + hoher Reward-Varianz (Fading) keinen spürbaren Vorteil bringen, aber Wartung erschweren.

**Tests:** Bereits ab v0.55 abgesichert — 7 neue Tests in `tests/test_modules.py` decken `_evaluate()` ab (Threshold-Verhalten, A1/A2-Dominanz, DX-Mode, Phase-Übergänge, Operate-Filter).

**Aufwand:** ~30 Min reine Doku-Arbeit, kein Code.

---

### 2. AP-Lite v2.2 Test-Pipeline bauen (vor jeglichem Code-Fix!)
**Betroffen:** `core/ap_lite.py`, `tests/test_modules.py` (neue Datei `tests/test_ap_lite_pipeline.py` denkbar)

**Problem:** AP-Lite ist live (`AP_LITE_ENABLED = True`) aber laut eigenem Docstring + CLAUDE.md komplett ungetestet. Im Code stehen drei explizite TODOs vom Autor:
1. `_build_costas_reference`: „Aktuell: vereinfachte Näherung" — kein echtes 7×3-Costas-Pattern mit FSK-Tönen
2. `align_buffers`: „Validieren! Insbesondere Phasenkorrektur für kohärente Addition" — Phase wird aktuell NICHT korrigiert; bei kohärenter Addition kritisch (sonst Auslöschung statt Verstärkung)
3. `SCORE_THRESHOLD = 0.75` — geraten, nie kalibriert
4. Zusatz-Verdacht: `encoder.generate_reference_wave()` muss echte FT8-Symbole produzieren — Stub-Verhalten würde Korrelation zu Müll machen

**Reihenfolge unverhandelbar:**
1. **ZUERST** synthetische End-to-End-Tests bauen — verrauschtes FT8-Signal generieren → 2 Slots erzeugen → durch `try_rescue` schicken → prüfen ob die richtige Nachricht rauskommt
2. Dann zeigen die Tests welcher der 4 Verdachtspunkte tatsächlich Bugs sind
3. Dann gezielt fixen mit Test als Schutznetz
4. Erst dann Feldtest

**Warum nicht direkt fixen:** Ohne Test ist jede „Verbesserung" Schuss ins Blaue — könnte einen funktionierenden Teil kaputt machen oder einen anderen Bug übersehen.

**Aufwand Pipeline:** ~1-2 h. Brauchen FT8-Signal-Generator (vermutlich über vorhandenen `Encoder.generate_reference_wave`), AWGN-Rauschen-Helfer, Test-Cases mit unterschiedlichen SNR-Bereichen.

**Aufgabe für nächste Session:** Test-Pipeline aufsetzen und als Baseline laufen lassen — dann sehen wir was wirklich kaputt ist.

---

## OFFEN — Naechste Schritte

### CQ-Frequenz-Algorithmus (core/diversity.py)
- [x] **Auswahllogik Score-basiert (v0.58):** `_score_gap()` ersetzt Median-Distance — Lückenbreite
  dominiert (1 Hz = 1 Punkt), Nachbarn ±1 Bin = 50 Hz Strafe pro Station, ±2 Bins halb so viel,
  Median-Distance nur als 0.01-Tiebreaker.
- [x] **Fester Sweet-Spot 800-2000 Hz (v0.58):** `SWEET_SPOT_MIN_HZ=800` / `MAX_HZ=2000` —
  TX-Frequenz nur noch im Sweet-Spot. Median wird nur über Sweet-Spot-Stationen berechnet.
- [x] **Modus-abhängige Dwell + Recalc (v0.58):** `set_mode()` setzt FT8=4z, FT4=8z, FT2=16z
  Dwell (~60 s einheitlich), Recalc = 5 × Dwell = ~300 s.
- [~] **Frequenzwechsel im Statistics-Modus sperren — VERWORFEN (Mike-Entscheidung 25.04.2026):**
  Variance, kein Bias. Wechsel mitteln sich über 22.000+ Zyklen raus, treffen alle Modi gleich.
  Sticky-Gap (50 Hz) + verfeinerte Kollision reduzieren Wechsel-Frequenz ausreichend.
- [x] **Kollisionserkennung verfeinert (v0.58):** `n_direct >= 2` ODER `n_in_band >= 3`
  (n_in_band inkl. current_bin). QSO-Schutz unverändert.
- [x] **Sticky Gap (v0.58):** Bleibt bei aktueller Frequenz wenn im Sweet-Spot, keine
  Kollisions-Schwelle erreicht und neue Lücke nicht > +50 Hz breiter. `_measure_gap_around()`
  refresht aktuelle Lück-Breite nach Sticky-Hit. `reset()` setzt `_current_gap_width_hz=0`.

### Propagation (core/propagation.py)
- [x] **60m Propagations-Balken:** Interpolation aus 40m+80m implementiert in
  `core/propagation.py::_fetch_raw()` (L181-190). Mittelwert per _CONDITION_ORDER-Index,
  day+night getrennt. (23.04.2026 erledigt)

### UI-Verbesserungen (SPAETER)
- [x] **Statusbar DT-Anzeige:** Zeigt `DT: —` / `DT: Korrektur` (grün) / `DT: Aktiv` —
  kein exakter Wert mehr. Implementiert in main_window.py::_update_statusbar() (Zeile 558-565).
- [x] **Statusbar Mode+Filter:** Zeigt `FT8 40m | 14074.000 kHz | Filter: 100-3100 Hz` —
  Filter-String pro Modus in _FILTERS dict. Implementiert in _update_statusbar() (Zeile 573-609).
- [ ] **Spalten-Konfig in Settings:** RX-Spalten ein/ausblendbar + gespeichert/geladen (Slot, Ant, DT, etc.)

### RX-Liste (UI)
- [x] **Sortierung UTC absteigend:** Bereits implementiert — `rx_panel.py:276` sorted insert mit absteigendem HHMMSS-Vergleich + `_set_sort("time", reverse=True)`. (2026-04-25 verifiziert)
- [ ] **CQ-Zusammenfassung ueberarbeiten:** Aktuell werden CQ-Rufe zu "CQ ×N" zusammengefasst — kaum sichtbar.
  Optionen (Mike entscheidet):
  (a) CQ-Rufe ins QSO-Panel verschieben: erste Zeile "CQ", ab 5× nur noch "CQ ×6" mit aktualisierter Zahl
  (b) CQ-Rufe komplett aus RX-Liste entfernen (sauberere Liste, weniger Ablenkung)
- [x] **Alte CQ-Rufe automatisch loeschen:** CQ-Rufer bekommen 300s Aging (5 Min) in
  `core/station_accumulator.py::remove_stale`, nicht-CQ bleibt bei 75s, active_qso bei 150s.
  Test: `test_accumulator_cq_longer_aging`. (23.04.2026 erledigt)

- [x] **Answer-Me Highlighting (DeepSeek-Idee):** Wenn eine Station unser Callsign in ihrer Nachricht
  sendet (z.B. "DA1MHH -07"), Zeile in der RX-Liste GELB hinterlegen. Verhindert dass wir ein QSO-Angebot
  uebersehen wenn gerade viel Traffic ist. Prio: hoch — direkter Nutzwert beim Pileup.
  (25.04.2026 erledigt — v0.57: Farbe `#5A4A10` Gold + Bold an 3 Stellen in `ui/rx_panel.py`)

### Statistik & Analyse (nach mehr Messdaten)
- [ ] **DIAGRAMM-AUSWERTUNG 20m — für GitHub (wenn genug Daten vorhanden):**
  Zwei Diagramme, Skripte fertig unter `tools/`:
  1. `tools/plot_20m_stations.py` — Stationsanzahl über Zeit: Normal / Div Standard / Div DX
     Aufruf: `./venv/bin/python3 tools/plot_20m_stations.py --date 2026-04-21`
  2. `tools/plot_ant2_performance.py` — ANT2 Performance stündlich:
     Oben: Ant2 Win-Rate % (wie oft ANT2 besser als ANT1)
     Unten: Ø ΔSNR gesamt + Ø ΔSNR wenn A2 gewinnt (in dB)
     Aufruf: `./venv/bin/python3 tools/plot_ant2_performance.py --band 20m --date 2026-04-21`
  **Wann ausführen:** Nach A/B-Test 20m (alle 10 Min Normal ↔ Div DX ab ~10:00 UTC).
  Mind. 3 Stunden Daten → dann Diagramme generieren + in STATISTICS.md oder README einbetten.
  Vorläufige Ergebnisse (2026-04-20, wenig Daten):
    Normal Ø 35.4 St. | Div Standard Ø 37.7 (+6%) | Div DX Ø 41.5 (+17%)
    ANT2 Win-Rate 20m: ~27-29% | 40m Nacht: 21-31% | Ø ΔSNR -0.29 dB (A1 leicht dominant)

- [ ] **ANT1 vs ANT2 SNR direkt loggen:** Pro Station beide SNR-Werte erfassen (ant1_snr, ant2_snr, delta).
  Aktuell: nur "Ant2 Wins" als Zaehler. Ziel: "ANT2 war im Schnitt +X dB besser bei Y% der Stationen".
- [ ] **Statistik-Diagramme fuer GitHub:** matplotlib-Script das aus statistics/*.md automatisch
  SVG/PNG-Charts generiert (Normal vs Diversity_Normal vs Diversity_Dx, pro Band + Uhrzeit).
  Einbetten in README oder eigene STATISTICS.md.
- [ ] **Auswertung per Tertile-Analyse — KEIN Datencropping (Entscheidung final):**
  Alle Messwerte behalten, in drei gleich grosse Drittel aufteilen, Normal vs Diversity pro Tertile
  separat vergleichen. Kein Wegwerfen von Extremwerten.
  - Unteres Drittel (33%): Schlechte Bedingungen — bringt Diversity ueberhaupt was?
  - Mittleres Drittel (33%): Alltagsbetrieb — typischer Gewinn im Normalbetrieb
  - Oberes Drittel (33%): Spitzentage / Sporadic-E — steigert Diversity noch weiter oder Saettigung?
  Begruendung: Gerade die oberen Messtage (DX-Oeffnungen) zeigen den groessten Diversity-Effekt.
  Die wegzuwerfen wuerde das erreichte Ergebnis beschneiden. Tertile behält ALLE Daten, basiert
  auf Raengen — bimodale Verteilung (Normal-Tage vs Sporadic-E) kein Problem.
  Implementierung: pandas.qcut(stations, q=3) → pro Label [low/medium/high] Mittelwert + Diff %.
  Script liest aus statistics/*.md, vergleicht Modi pro Tertile, gibt Tabelle aus.
- [ ] **WICHTIG — Gain-Bias beheben (faire Vergleiche!):** DX-Modus macht VOR dem Start IMMER
  automatisch eine Gain-Messung (optimierter Empfangspegel). Normal-Modus nur freiwillig.
  → DX startet systematisch mit besserem Gain → DX sieht im Vergleich kuenstlich besser aus.
  Fix: Wenn Statistik-Erfassung aktiv ist, Gain-Messung fuer ALLE Modi erzwingen (nicht nur DX).
  Wahrscheinlich nur ein Flag in der Gain-Logik — geringer Aufwand, grosser Effekt auf Fairness.

- [ ] **Gain-Bias Compensator (DeepSeek-Idee):** Parallel-Dekodierungen (beide Antennen hören gleiche
  Station) nutzen um systematischen SNR-Offset zwischen ANT1 und ANT2 zu messen. Über viele Stationen
  mitteln → Offset in dB speichern → bei Diversity-Auswahl-Schwelle abziehen. Macht Vergleich fair
  auch OHNE vorher beide Gain-Messungen abzugleichen. Komplex aber elegant — für spätere Phase.

### Bugs
- [ ] **VERMUTLICHER BUG — Freie TX-Frequenz im Normal-Modus (unregelmäßig):**
  Beobachtung (Mike, 2026-04-25): Im Normal-Modus wird die freie TX-Frequenz aus dem
  Histogramm manchmal NICHT gesetzt — kein Marker im Histogramm sichtbar, TX bleibt auf
  alter Frequenz. Im CQ-Modus funktioniert `get_free_cq_freq()` + Histogramm-Marker
  zuverlässig (`mw_qso.py:109–115`).
  Verdacht: Timing-Problem oder Überschneidung mit Band/Modus-Wechsel — noch nicht
  reproduzierbar. **Kein Code-Fix bis weiteres Auftreten dokumentiert ist.**
  Nächste Schritte: Konsolen-Ausgabe `[CQ] TX-Frequenz auf X Hz` beobachten, ob
  `get_free_cq_freq()` None zurückgibt oder der Wert gleich dem aktuellen ist.

- [x] **RX-Liste + QSO-Fenster nicht geleert bei Wechsel (BUG):**
  Jetzt gelöscht in: Band-Wechsel, Modus-Wechsel, Normal↔Diversity
  (_on_rx_mode_changed), _enable_diversity, _disable_diversity,
  RX ON/OFF (_on_rx_panel_toggled). (23.04.2026 erledigt)

- [ ] **Even/Odd Slot-Anzeige asynchron (FT2/FT4/FT8 pruefen):** Die Even/Odd-Anzeige oben im
  QSO-Fenster springt bei FT2 (3,75s Zyklen) moeglicherweise nicht exakt mit der echten Slot-Zeit um.
  Bei FT8 (15s) und FT4 (7,5s) ebenfalls verifizieren. Anzeige muss IMMER exakt der Slot-Zeit
  entsprechen, sonst ist sie wertlos.
  DeepSeek-Verdacht: Timing/Threading-Problem (nicht Logik-Fehler). FT2 hat kuerzestes Fenster
  (3,75s), daher dort am kritischsten. Loesung: eigenen dedizierten Timer fuer Slot-Anzeige,
  unabhaengig vom Decoder-Thread.
- [x] **Warteliste:** Queue akzeptiert jetzt Grid + Report (EA3FHP-Fix, v0.36)
- [x] **Logbuch-Loeschen:** Funktioniert (bestaetigt 15.04)
- [x] **km Fallback:** Callsign-Prefix Naeherung (~km) im Logbuch eingebaut (v0.37)

### Gain-Messung Scoring (UNTERSUCHEN)
- [ ] **Scoring-Logik pruefen:** Zeigt "optimal" Gain mit WENIGER Stationen als andere Gains.
  Aktuell: waehlt nach bestem Top-5 SNR. Aber Stationsanzahl wird daneben angezeigt → verwirrend.
  Optionen: (a) Scoring klar beschriften "Bester SNR", (b) Stationsanzahl statt SNR als Kriterium,
  (c) Kombination aus beiden, (d) Alle Zyklen-Durchschnitt pruefen (nur letzte Messung oder Schnitt?)
- [x] **Logging:** Jede Messung protokollieren fuer spaetere Analyse
  (25.04.2026 erledigt — v0.57: `_log_gain_result()` in `ui/mw_radio.py`, append-only `~/.simpleft8/gain_log.md`,
  loggt Normal-Kalibrierung + Diversity-Messung mit UTC + Band/Mode + ANT1/ANT2 Gains + Ø SNRs)

### Feldtest (NUR MIT RADIO)
- [ ] **FT2 Feldtest:** Ein bestätigtes QSO gefahren (Decodium-kompatibel bestaetigt). Ausführliches Testen auf 40m (7.052 MHz) / 20m (14.084 MHz) steht noch aus — DT-Korrektur, Timing-Randfahlle, laengere Sessions.
- [ ] **DT-Korrektur v2:** Konvergenz pruefen (soll jetzt 3-6 Min statt 12-18 Min dauern)
- [ ] **AP-Lite Threshold:** 0.75 kalibrieren → dann `AP_LITE_ENABLED = True`
- [ ] **OMNI-TX + Auto-Hunt:** Integriert (Easter Egg: Klick auf Versionsnummer). Feldtest ausstehend.
  GitHub: Darf als Feature "Optimierter CQ-Ruf (OMNI-TX)" erwaehnt werden, aber NICHT wie man es aktiviert.
  TODO: EN+DE README/Hilfe-Seite erstellen mit: Was ist OMNI-TX, wie funktioniert es (Even+Odd abwechselnd),
  was erwartet man (mehr Chancen gehoert zu werden), Einschraenkungen (Double-TX-Pausen).

### TX-Optimierungen — PRIO NIEDRIG
- [ ] **Per-Station DT-Offset beim QSO-Anruf (encoder._station_dt_offset):**
  Wenn Station X mit DT=+1.2s angerufen wird, die eigene TX um +1.2s verschieben →
  Signal landet im Zentrum ihres Decode-Fensters. Globale DT-Korrektur (ntp_time) bleibt
  unberührt. Nach QSO-Ende/Abbruch automatisch reset auf 0.0.
  Implementierung: `encoder._station_dt_offset = station.dt` beim Ansprechen,
  `encoder._station_dt_offset = 0.0` in qso_state auf IDLE/TIMEOUT.
  Kein Diversity-Feature — reine TX-Pfad-Optimierung.
  > Mike-Entscheidung 2026-04-25: PRIO NIEDRIG — erst nach mehr Feldtest-Daten.

### Langfristig
- [ ] IC-7300 Fork: `radio/ic7300.py` implementieren
- [ ] QSO-Resume bei App-Neustart

> "Band Map (visuelle Frequenz-Belegung)" gestrichen 2026-04-25 — das vorhandene
> Diversity-Histogramm mit TX-Cursor (control_panel) deckt den FT8-relevanten
> 100–1550 Hz-Bereich bereits ab. Ein separater Wasserfall über das gesamte Band
> ist für FT8 nicht nötig.
- [x] **RF-Power-Presets pro Band+Watt (lernendes System):** ERLEDIGT in v0.56 (2026-04-25)
  Implementierung: `core/rf_preset_store.py` mit Hybrid-Lade-Strategie (exakter Treffer →
  lineare Interpolation/Extrapolation → Default), atomic JSON-Write, Plausibilitäts-Warnung,
  Migration aus altem `rfpower_per_band`-Eintrag. Pro Radio (FlexRadio jetzt, IC-7300 später)
  separate Tabelle. UI: SettingsDialog-Section "RF-Presets" mit Tabelle + Reset-Buttons
  (disabled während aktivem TX). Selbstheilend: bei jedem Konvergenz-Übergang wird
  überschrieben. Tests 178 → 197 grün. Siehe HISTORY.md "v0.56".

---

## ERLEDIGTE FEATURES (Kurzform)

### 15.04.2026
- FT2 nativ + Decodium-kompatibel (Source Code verifiziert: NN=103, NSPS=288, 4-GFSK)
- FT2 QSO erfolgreich abgeschlossen (Empfang + Senden funktioniert)
- Diversity Standard/DX Modi + DX-Score (schwache Stationen <-10dB)
- QSO-Bugs: WAIT_73 Timeout, RR73 Hoeflichkeit (max 2x), Overlay
- DT-Korrektur v2: schneller, gedaempft, pro Modus gespeichert (~/.simpleft8/dt_corrections.json)
- RX-Filter automatisch pro Modus (FT8/FT4=3100Hz, FT2=4000Hz)
- CQ Frequenz Sweet Spot (800-2000 Hz)
- OMNI-TX CQ Button, Even/Odd Spalte RX + QSO-Panel [E]/[O]
- CQ-Zeilen zusammengefasst (CQ ×24 statt 24 Einzelzeilen)
- QSO-Panel Auto-Trim (max 40 Zeilen)
- Even/Odd Anzeige modus-abhaengig (nicht mehr hardcoded 15s)
- FT2 Frequenzen DXZone (40m=7.052, 20m=14.084)
- Info-Dialoge mit "Nicht mehr anzeigen"

### 14.04.2026
- FT4/FT2 Integration (Decoder, Encoder, Timing, UI)
- DT-Korrektur kumulative Strategie
- Presence Timer, Auto-Hunt, Diversity Fixes

### 13.04.2026
- Propagation-Balken (HamQSL), Radio-Abstraktion getestet
- AGC deaktiviert (kollidiert mit Noise-Floor-Norm)
- Drift-Kompensation entfernt (0 Nutzen)

### 12.04.2026
- Radio-Abstraktion komplett (v0.25-v0.28)
- main_window.py Split (1755→473 Zeilen, 4 Mixins)
- AP-Lite v2.2, OMNI-TX Hooks, DeepSeek Full Review
