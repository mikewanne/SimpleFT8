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

## OFFEN — Naechste Schritte

### CQ-Frequenz-Algorithmus (core/diversity.py)
- [ ] **Auswahllogik verbessern: Breiteste/ruhigste Luecke statt median-naechste.**
  Aktuell: `best_gap = min(gaps, key=lambda g: abs(gap_center - median_bin))` → waehlt immer
  die Luecke in der Mitte des belegten Bereichs. User sieht TX immer zentral, nie in freien Randbereichen.
  Fix: Score-basierte Bewertung mit Prioritaet:
  1. Lueckenbreite (groesste Gewichtung)
  2. Anzahl Nachbar-Stationen in Bins ±1 und ±2 (Stoerer-Penalty)
  3. Erst dann: Abstand zum Median (kleinste Gewichtung)
  Fuer DX-Betrieb besonders wichtig: freiste Luecke schlaegt zentrale Position.

- [ ] **Suchbereich: Fester Sweet-Spot 800-2000Hz statt occupied_min/max.**
  Aktuell: FREQ_MIN_HZ=150, FREQ_MAX_HZ=2800 → SEARCH_MIN/MAX auf belegten Bereich begrenzt.
  Problem: Unter 800Hz oder ueber 2000Hz werden wir von anderen Stationen ignoriert (ausserhalb
  des FT8-Sweet-Spots). Andererseits: Bereiche INNERHALB 800-2000Hz ausserhalb der aktuellen
  Stationsmasse werden auch nicht durchsucht.
  Fix: FREQ_MIN_HZ=800, SEARCH_MIN=800, SEARCH_MAX=2000 (fest) — gesamten Sweet-Spot durchsuchen,
  aber nie darueber hinaus. Damit bekommt auch der Randbereich 800-900Hz eine Chance wenn er frei ist.

- [ ] **Modus-abhaengige Dwell-Time und Neuberechnungs-Intervall.**
  Aktuell: recalc_interval=20 Zyklen (passt fuer FT8=5 Min), dwell=3 Zyklen (=45s FT8).
  Problem: FT4 und FT2 haben kuerzere Zyklen → gleiche Zyklenanzahl = viel kuerzere Zeit.
  Zu haeufiges Springen macht uns "unbeliebt" — wer uns einmal gehoert hat findet uns nicht mehr.
  Ziel: Einheitlich ~1 Min Minimum Dwell-Time und ~5 Min Routine-Intervall in allen Modi.
  Konkrete Werte (DeepSeek + Analyse):
  | Modus | Zykluszeit | Min Dwell | Timer-Intervall | Max Wechsel/h |
  | FT8   | 15s        | 4 Zyklen  | 20 Zyklen       | 6-8           |
  | FT4   | 7,5s       | 8 Zyklen  | 40 Zyklen       | 6-8           |
  | FT2   | 3,75s      | 16 Zyklen | 80 Zyklen       | 6-8           |
  Implementierung: Klasse muss aktiven Modus kennen und Werte dynamisch setzen.

- [ ] **Frequenzwechsel im Statistics-Modus sperren.**
  Waehrend einer Mess-Session (Statistics aktiv) TX-Frequenz festhalten — Wechsel verfaelscht
  den Vergleich (andere Stationen hoeren uns, andere QRM-Umgebung).
  Fix: Im Stats-Modus nur bei schwerer Kollision (≥5 Nachbarn) wechseln, sonst einfrieren.

- [ ] **Kollisionserkennung verfeinern.**
  Aktuell: ≥3 Stationen in Nachbar-Bins nach ≥3 Zyklen Dwell-Time.
  Fix: ≥2 in direkten Nachbarn (±1 Bin) ODER ≥3 in erweitertem Bereich (±2 Bins).
  QSO-Schutz bleibt wie er ist (qso_active → kein Wechsel, auch bei Kollision) — korrekt!

- [ ] **Sticky Gap (DeepSeek-Idee):** Nur wechseln wenn neue Luecke >50Hz breiter ist ALS die aktuelle
  ODER aktuelle Luecke unbrauchbar (≥3 direkte Nachbarn). Verhindert nervöses "Pendeln" wenn zwei
  Luecken fast gleich gut sind. Implementierung: `if new_gap_width > current_gap_width + 50: switch()`.

### Propagation (core/propagation.py)
- [ ] **60m Propagations-Balken (HamQSL liefert keine Daten):**
  60m (5.357 MHz) ist als Band konfiguriert und FT8-faehig (IARU-Frequenz), aber HamQSL XML
  enthaelt kein 60m-Feld → Balken bleibt immer grau (`XML_BANDS` ohne 60m, Zeile 31).
  Optionen:
  (a) **Interpolation** (einfach): 60m-Wert = Mittelwert aus HamQSL 40m + 80m.
      Begruendung: 60m liegt frequenztechnisch dazwischen, NVIS-Charakteristik aehlich 80m.
      Implementierung: ~5 Zeilen in `_apply_time_correction()`.
  (b) **PSKReporter API** (genauer): Echte Spots auf 5.357 MHz der letzten Stunde zaehlen →
      0-5 Spots=poor, 5-20=fair, >20=good. Braucht zusaetzlichen HTTP-Request alle 15 Min.
  Empfehlung: Erstmal (a) als Quick-Win, langfristig (b) als Option.

### UI-Verbesserungen (SPAETER)
- [ ] **Statusbar DT-Anzeige:** Statt `DT: +0.78s` nur `DT: Aktiv` oder `DT: Korrektur` — exakte Zeit macht Funker nervoes
- [ ] **Statusbar Mode+Filter:** `Mode: FT8 | Filter: 100-3100 Hz` (oder FT4/FT2 mit jeweiligem Filter) — damit jeder sieht welcher Filter aktiv ist
- [ ] **Spalten-Konfig in Settings:** RX-Spalten ein/ausblendbar + gespeichert/geladen (Slot, Ant, DT, etc.)

### RX-Liste (UI)
- [ ] **Sortierung UTC absteigend:** Neueste Station oben, aelteste unten. Derzeit unsortiert/aufsteigend.
- [ ] **CQ-Zusammenfassung ueberarbeiten:** Aktuell werden CQ-Rufe zu "CQ ×N" zusammengefasst — kaum sichtbar.
  Optionen (Mike entscheidet):
  (a) CQ-Rufe ins QSO-Panel verschieben: erste Zeile "CQ", ab 5× nur noch "CQ ×6" mit aktualisierter Zahl
  (b) CQ-Rufe komplett aus RX-Liste entfernen (sauberere Liste, weniger Ablenkung)
- [ ] **Alte CQ-Rufe automatisch loeschen:** Unbeantwortete CQ-Rufe nach 2-5 Min aus der Liste entfernen.
  Haelt die Liste uebersichtlich, verhindert "tote Zeilen" von Stationen die laengst weg sind.

- [ ] **Answer-Me Highlighting (DeepSeek-Idee):** Wenn eine Station unser Callsign in ihrer Nachricht
  sendet (z.B. "DA1MHH -07"), Zeile in der RX-Liste GELB hinterlegen. Verhindert dass wir ein QSO-Angebot
  uebersehen wenn gerade viel Traffic ist. Prio: hoch — direkter Nutzwert beim Pileup.

### Statistik & Analyse (nach mehr Messdaten)
- [ ] **ANT1 vs ANT2 SNR direkt loggen:** Pro Station beide SNR-Werte erfassen (ant1_snr, ant2_snr, delta).
  Aktuell: nur "Ant2 Wins" als Zaehler. Ziel: "ANT2 war im Schnitt +X dB besser bei Y% der Stationen".
- [ ] **Statistik-Diagramme fuer GitHub:** matplotlib-Script das aus statistics/*.md automatisch
  SVG/PNG-Charts generiert (Normal vs Diversity_Normal vs Diversity_Dx, pro Band + Uhrzeit).
  Einbetten in README oder eigene STATISTICS.md.
- [ ] **Tertile-Analyse statt Trimmed Mean (DeepSeek bestaetigt: bessere Methode):**
  Statt Daten wegzuschneiden: Messwerte (Stationen/Zyklus) in drei gleich grosse Drittel aufteilen
  und Normal vs Diversity pro Tertile separat vergleichen.
  - Unteres Drittel (33%): Schlechte Bedingungen — bringt Diversity ueberhaupt was?
  - Mittleres Drittel (33%): Alltagsbetrieb — typischer Gewinn
  - Oberes Drittel (33%): Spitzentage / Sporadic-E — Sättigung oder weiterer Gewinn?
  Warum besser als Trimmed Mean: Trimmed Mean wirft genau die Sporadic-E/DX-Tage raus die den
  Diversity-Effekt am deutlichsten zeigen — das beschneidet das erreichte Ergebnis.
  Tertile basiert auf Raengen (nicht Mittelwert), bimodale Verteilung ist kein Problem.
  Implementierung: pandas.qcut(stations, q=3) → Vergleich pro Label [low/medium/high].
  Trimmed Mean weiterhin als SEKUNDAERE Robustheitspruefung nutzen (beide Methoden gleiche Richtung = wasserdicht).
  Script: aus statistics/*.md lesen, pro Modus+Tertile Mittelwert berechnen, Differenz in %.
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
- [ ] **RX-Liste + QSO-Fenster nicht geleert bei Wechsel (BUG):**
  Beim Wechsel von Band, Modus (FT8/FT4/FT2), Antenne oder Diversity-Modus (Normal/Standard/DX)
  bleiben alte Stationen in der RX-Liste und im QSO-Fenster stehen.
  Beispiel: 12m → 10m Bandwechsel → RX-Liste zeigt noch 12m-Stationen.
  Fix: Bei JEDEM dieser Wechsel RX-Liste UND QSO-Fenster komplett leeren.
  Betroffene Trigger: Band, Modus, Antennenwahl, Diversity-Modus.

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
- [ ] **Logging:** Jede Messung protokollieren fuer spaetere Analyse

### Feldtest (NUR MIT RADIO)
- [ ] **FT2 Feldtest:** Ein bestätigtes QSO gefahren (Decodium-kompatibel bestaetigt). Ausführliches Testen auf 40m (7.052 MHz) / 20m (14.084 MHz) steht noch aus — DT-Korrektur, Timing-Randfahlle, laengere Sessions.
- [ ] **DT-Korrektur v2:** Konvergenz pruefen (soll jetzt 3-6 Min statt 12-18 Min dauern)
- [ ] **AP-Lite Threshold:** 0.75 kalibrieren → dann `AP_LITE_ENABLED = True`
- [ ] **OMNI-TX + Auto-Hunt:** Integriert (Easter Egg: Klick auf Versionsnummer). Feldtest ausstehend.
  GitHub: Darf als Feature "Optimierter CQ-Ruf (OMNI-TX)" erwaehnt werden, aber NICHT wie man es aktiviert.
  TODO: EN+DE README/Hilfe-Seite erstellen mit: Was ist OMNI-TX, wie funktioniert es (Even+Odd abwechselnd),
  was erwartet man (mehr Chancen gehoert zu werden), Einschraenkungen (Double-TX-Pausen).

### Langfristig
- [ ] IC-7300 Fork: `radio/ic7300.py` implementieren
- [ ] Band Map (visuelle Frequenz-Belegung)
- [ ] QSO-Resume bei App-Neustart
- [ ] **RF-Power-Presets pro Band+Watt (lernendes System):**
  Aktuell tastet sich die Closed-Loop-Regelung (FWDPWR-Feedback) 3-4 Zyklen (~45-60s) an die
  Ziel-Watt heran. Idee: pro (Band, Ziel-Watt) den letzten stabilen RF-Wert in config.json
  speichern und beim Band-/Wattwechsel sofort laden als Startpunkt — Regelung laeuft weiter
  aber startet nah am Ziel statt bei 0.
  DeepSeek-Empfehlung:
  - Pro (Band, Watt-Stufe) speichern, NICHT nur pro Band (RF-Kennlinie nicht linear)
  - Als "stabil" gilt: 3 aufeinanderfolgende Zyklen mit Abweichung < 5% vom Zielwert
  - Gespeicherten Wert nach 7 Tagen als "veraltet" markieren (Temperatur-/SWR-Drift)
  - Einfacher Einstieg: Nur RF-Wert + Timestamp, ohne Temperatur/Antennen-Metadaten
  Vorteil: Nach wenigen Sessions fuer jede Band+Watt-Kombi sofort in der Naehe der Zielleistung.
  Hinweis (bis Feature fertig): Vor Normal-Messungen MANUELL Tune + Gain-Messung machen,
  damit Vergleich mit DX-Modus (automatisch Gain) fair bleibt.

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
