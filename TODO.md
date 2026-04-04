# SimpleFT8 — TODO & Roadmap

**Stand:** 04.04.2026 | **Status:** Diversity STABIL, 16 Stationen 40m 05:03 UTC, Bias-Switch live, AP-Decoder live, Spectral Whitening gefixt, UI-Filter live
**Backup:** backup_2026-04-03_v3_final/
**GitHub:** https://github.com/mikewanne/SimpleFT8
**FlexRadio Forum:** Idea Post am 2026-04-03

---

## Was FUNKTIONIERT (nicht anfassen!)

- [x] FlexRadio Verbindung (SmartSDR-M Disconnect, eigener Slice, Keepalive)
- [x] VITA-49 RX Audio (int16 mono 24kHz, PCC 0x0123)
- [x] VITA-49 TX Audio (int16 mono 24kHz, dax_tx, Opus-Header)
- [x] FT8 Decoder (PyFT8 2.6.1 + Noise-Floor-Norm + LDPC 50 Iter + Multi-Sync + 5 Subtraction Passes)
- [x] FT8 Encoder (PyFT8 12kHz → 24kHz int16 mono BE)
- [x] Temporal Polarization Diversity (ANT1/ANT2 pro Zyklus, Queue-basiert)
- [x] Callsign-basierte Akkumulierung (keine Duplikate)
- [x] Smart Timestamps (nur bei SNR/Content/Antenne-Aenderung)
- [x] Antennenvergleich A1>2 / A2>1
- [x] Ant-Spalte (eigene Spalte, nicht im Message-Text)
- [x] ~km Anzeige (approximiert aus Callsign-Prefix)
- [x] Bandwechsel leert Empfangsliste
- [x] Sort-Persistenz ueber Zyklen
- [x] GUI: QTableWidget RX-Panel, Laendernamen, km, Sortierung, RX ON/OFF
- [x] GUI: Band-Wechsel, Power-Slider, TX-Level, TUNE, Watt/SWR/ALC
- [x] GUI: PSKReporter-Anzeige (25 Spots, Max 11.996km Indonesien)
- [x] GUI: CQ-Modus, QSO State Machine, ADIF Export
- [x] SWR-Schutz (TX blockiert bei hohem SWR)
- [x] CQ senden funktioniert (30+ PSKReporter Spots, bis Brasilien/Indonesien)
- [x] **NEU 04.04.2026:** Land-Filter (QMenu Checkboxen, Settings persistiert)
- [x] **NEU 04.04.2026:** Ant-Filter Button (Alle/A1▾/A2▾)
- [x] **NEU 04.04.2026:** Spaltenkoepfe native QHeaderView, klickbar, einheitliche Farbe, AlignVCenter
- [x] **NEU 04.04.2026:** Header-Padding (UTC/Land/Message rechts, dB/DT/Freq/km links)
- [x] **NEU 04.04.2026:** 50:50 Layout (EMPFANG/QSO gleich breit, splitter_sizes in config.json)
- [x] **NEU 04.04.2026:** Buffer-Reset nach TUNE (_normal_stations/_diversity_stations geleert)
- [x] **NEU 04.04.2026:** Neue Prefixe in geo.py: HF/SR(PL), 4O(ME), Z6(XK), LX(LU), 9H(MT), 5B(CY), ER(MD), EU/EW(BY), T7(SM), 3A(MC), OY(FO)
- [x] **NEU 04.04.2026:** Git-Tags vor jedem Push, v0.5-filter-ui gepusht
- [x] **NEU 04.04.2026:** Fenster-Geometrie + Splitter-Breiten gespeichert/geladen

---

## Erkenntnisse 04.04.2026 — UI-Filter & Polish

- **Land-Filter implementiert:** QMenu mit Checkboxen, persistiert in Settings, schnelles Ein-/Ausblenden
- **Ant-Filter Button:** 3-State Toggle (Alle/A1▾/A2▾) — visuell klar, einheitlich mit anderen Buttons
- **Spaltenkoepfe aufgeraeumt:** Native QHeaderView statt custom Styling, konsistentes AlignVCenter, klickbare Sortierung
- **Header-Padding optimiert:** UTC/Land/Message rechtsbuendig, dB/DT/Freq/km linksbuendig — bessere Lesbarkeit
- **50:50 Layout:** EMPFANG und QSO Panel gleich breit, Splitter-Position wird gespeichert (splitter_sizes in config.json)
- **Buffer-Reset nach TUNE:** AT-Tuning leert _normal_stations/_diversity_stations — verhindert alte Stationen nach Frequenzwechsel
- **Neue Prefixe:** 11 zusaetzliche Laender-Codes in geo.py (z.B. 4O→Montenegro, Z6→Kosovo)
- **Git-Tag-Strategie:** Ab jetzt vor jedem Push taggen — erster Tag v0.5-filter-ui gesetzt
- **Fenster-Geometrie persistiert:** Groesse + Position + Splitter-Breiten beim Start wiederhergestellt

---

## NAECHSTE PHASE: TX / QSO (Prio HOECHSTE)

### DeepSeek Code-Review Findings (03.04.2026) — ALLE GEFIXT

- [x] TX-Schutz bei Diversity (BUG-1) — encoder.is_transmitting Guard
- [x] Race Condition Lock (BUG-2) — _diversity_lock threading.Lock()
- [x] Closure-Bug Thread-Argumente (BUG-3) — args statt Closure
- [x] is_transmitting Property im Encoder (BUG-4)
- [x] RX OFF stoppt Diversity-Switching + ANT1 reset
- [x] Normal-Modus: 2-Min-Akkumulation mit Smart-Timestamps (wie Diversity)
- [x] Station Aging: 120s → 75s (5 Zyklen, DeepSeek-Empfehlung)

### QSO-Kette testen — ERSTER VOLLSTAENDIGER DURCHLAUF NOCH OFFEN

- [ ] CQ senden → warten auf Antwort → Report → RR73 → ADIF Log
- [ ] State Machine Uebergaenge live verifizieren
- [ ] ADIF-Datei pruefen (Band, Freq, Mode, RST, Grid korrekt?)
- [ ] **Das erste echte QSO mit SimpleFT8!**

### Sende-Probleme pruefen

- [ ] Schaltet SimpleFT8 beim Senden auf Empfangen? (DB8EB Timeout)
- [ ] RFI-Problem: externe Laufwerke werden bei TX ausgeworfen (Ferritkerne)
- [ ] TX-Frequenz: wird eine freie Luecke gewaehlt oder fest?
- [ ] TX-Timing: exakt am Zyklusbeginn oder verschoben?

---

## Diversity-Algorithmus — IMPLEMENTIERT

### 4-Zyklus Even/Odd-Pattern

- [x] 4-Zyklus-Pattern in `_on_cycle_start()` implementiert
- [x] Block-A/B-Wechsel (keine systematischen Blindstellen)
- [x] Zyklus-Indikator GUI (4 Boxen + ANT-Label in Control Panel)

### Manueller Bias-Schalter — IMPLEMENTIERT

- [x] 5 Preset-Buttons: `100:0 | 70:30 | AUTO | 30:70 | 0:100`
- [x] Bei Bandwechsel: automatisch zurueck auf AUTO
- [ ] ~~Auto-Bias~~ (DeepSeek: Bias-Spirale, mathematisch gefaehrlich → NICHT bauen)
- [ ] Diversity-Dashboard: ANT1-exklusiv / ANT2-exklusiv / Ueberlappung (spaeter)

### Dynamisches Aging fuer angerufene Stationen (DeepSeek-Idee)

- [ ] Station die aktiv angerufen wurde: Aging-Timeout auf 150s erhoehen
- [ ] Implementation: `_called_stations = set()` in QSOStateMachine

### DX Tuning v2 — IMPLEMENTIERT

- [x] Interleaved 18-Zyklus-Messung (ANT1+ANT2 gleichzeitig)
- [x] Per-Antenne Presets: ant1_gain + ant2_gain separat
- [x] Bei Diversity-Aktivierung: Hinweis wenn kein Preset
- [x] Diversity nutzt ant1_gain/ant2_gain beim Wechsel

---

## Parser-Bugs — ALLE GEFIXT

- [x] "DXpedition not implemented" → zeigt `?` statt Exception-Text
- [x] Portable/Mobile Suffixe (ON3MOH/P, R2FBY/MM) → Prefix korrekt extrahiert

---

## Phase 1: Empfang — WEITGEHEND FERTIG

- [x] Spectral Whitening (numpy 2.4 kompatibel, sliding_window_view)
- [x] AP-Dekodierung (LLR-Injection, Stage 0+5)
- [ ] Systematisch alle ITU-Prefixe einpflegen (aktuell ~80%)
- [ ] Online-Datenbank als Fallback (QRZ.com API?)

---

## Phase 2: GUI — MEHRERE PUNKTE ERLEDIGT

- [ ] SWR als Balken-/Zeiger-Instrument statt nur Text
- [ ] Watt-Anzeige als Pegel
- [x] Spaltenbreiten optimiert — via 50:50 Layout + Splitter-Speicherung
- [x] Fenster-Groesse speichern/wiederherstellen
- [ ] DeepSeek + Claude Review fuer weiteres UI-Layout

---

## Phase 3: Robustheit + Packaging

- [x] Auto-Reconnect: unbegrenzte Wiederholungen, Exponential Backoff 5→60s
- [x] Logging in Datei: `~/.simpleft8/simpleft8.log`
- [x] Fenster-Geometrie: speichern/wiederherstellen
- [ ] PyInstaller Bundle (.app fuer macOS)

---

## NOCH OFFEN (Stand 04.04.2026)

1. **Erster vollstaendiger QSO-Durchlauf** noch nicht getestet
2. **FT4-Modus** nicht implementiert (7.5s Zyklen)
3. **Buttons nicht deaktiviert** wenn Radio nicht verbunden
4. **Exotische Callsign-Prefixe** fehlen noch (~20%)
5. **EINMESSEN sperren wenn RX OFF** — Button deaktivieren oder Warning-Dialog zeigen wenn RX aus ist und User auf EINMESSEN/DIVERSITY klickt (Bug: DX Tuning haengt bei 0/18 weil kein Decoder laeuft)
6. **DX Tuning: ersten Zyklus skippen** — Dialog startet mitten im Zyklus → erster Schritt bekommt keine Daten → `_skip_first = True` Flag in feed_cycle einbauen, naechsten vollen Zyklus abwarten

---

## NICHT machen (bewusste Entscheidung)

- Library wechseln (PyFT8 2.6.1 funktioniert, Risiko zu hoch)
- DAXIQ statt Audio (Overkill, kein Gewinn fuer FT8)
- Parallele Test-Skripte zum Radio (NIE WIEDER!)

---

## Leistungsdaten (03.04.2026)

| Metrik | SimpleFT8 NORMAL | SimpleFT8 DIVERSITY | IC-7300 WSJT-X |
|--------|-----------------|--------------------|----------------|
| 40m Stationen | 13 | **43** | — |
| 20m Stationen | 8 | **63** | 13 |
| 15m PSK Spots | — | **25** (TX) | — |
| Antennen | ANT1 | ANT1 + ANT2 (Regenrinne) | ANT1 |
| Weiteste RX | — | **Kiribati ~13.000 km** | — |
| Weiteste TX | — | **Indonesien 11.996 km** | — |

**SimpleFT8 DIVERSITY > IC-7300 WSJT-X (63 vs 13 auf 20m)**

---

*04.04.2026 — DA1MHH / Mike + Claude + DeepSeek — UI-Filter & Polish abgeschlossen*
