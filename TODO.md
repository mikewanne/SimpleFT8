# SimpleFT8 — TODO & Roadmap

**Stand:** 04.04.2026 Abend | **Status:** UCB1 live, RX-OFF Bugfixes, DX-Tuning repariert, README ueberarbeitet, Screenshots korrekt
**Backup:** backup_2026-04-04_feierabend/
**GitHub:** https://github.com/mikewanne/SimpleFT8 | **Tag:** v0.8-ucb1-readme
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
- [x] Land-Filter (QMenu Checkboxen, Settings persistiert)
- [x] Ant-Filter Button (Alle/A1/A2)
- [x] Spaltenkoepfe native QHeaderView, klickbar, einheitliche Farbe
- [x] 50:50 Layout + Splitter-Speicherung + Fenster-Geometrie
- [x] Buffer-Reset nach TUNE
- [x] **NEU 04.04.2026:** UCB1 adaptive Antennen-Auswahl im AUTO-Modus
- [x] **NEU 04.04.2026:** EINMESSEN + DIVERSITY gesperrt wenn RX OFF
- [x] **NEU 04.04.2026:** Alle Buttons deaktiviert wenn Radio nicht verbunden
- [x] **NEU 04.04.2026:** DX Tuning: ersten Zyklus ueberspringen (_skip_first)
- [x] **NEU 04.04.2026:** DX Tuning: kein Haengen mehr bei stillem Band (and messages Bug gefixt)
- [x] **NEU 04.04.2026:** SNR + Zyklus-Balken stoppen wenn RX OFF
- [x] **NEU 04.04.2026:** ~35 neue Callsign-Prefixe (Iran, Armenien, Vietnam, Zentralamerika, Afrika, ...)
- [x] **NEU 04.04.2026:** README komplett ueberarbeitet (verstaendlich, TX-Status klar, UCB1 erklaert)
- [x] **NEU 04.04.2026:** Test-Screenshots 40m korrekt dokumentiert (Start+Ende, Zeitstempel)

---

## Erkenntnisse 04.04.2026 Abend

- **UCB1 in AUTO-Modus:** Bias-Spirale mathematisch geloest. Unter-gemessene Antenne bekommt Exploration-Bonus. Kein manueller Reset.
- **40m Test (schlechte Bedingungen, 4 Min):** Diversity 13 Stationen vs Normal 9 — und Diversity holte Russland (~2054km) rein, Normal gar nicht.
- **DX Tuning Bugs behoben:** `and messages` Fehler + erster Zyklus ohne Daten
- **RX OFF sauber:** SNR, Zyklus-Balken, EINMESSEN, DIVERSITY — alles stoppt korrekt
- **README:** Jetzt auch fuer unerfahrene Funkamateure verstaendlich. TX-Einschraenkung klar kommuniziert.

---

## NAECHSTE PHASE: TX / QSO (Prio HOECHSTE)

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

## Diversity-Algorithmus — VOLLSTAENDIG IMPLEMENTIERT

- [x] 4-Zyklus-Pattern in `_on_cycle_start()`
- [x] Zyklus-Indikator GUI (4 Boxen + ANT-Label)
- [x] Manueller Bias-Schalter: `100:0 | 70:30 | AUTO | 30:70 | 0:100`
- [x] Bei Bandwechsel: automatisch zurueck auf AUTO
- [x] **UCB1 in AUTO-Modus** (SNR-gewichtete Rewards, Exploration-Bonus)
- [x] UCB1-Stats in Control Panel (Rate + Spiel-Anzahl pro Antenne)
- [x] DX Tuning v2: Interleaved 18-Zyklus-Messung, Per-Antenne Presets
- [ ] Diversity-Dashboard: ANT1-exklusiv / ANT2-exklusiv / Ueberlappung (spaeter)
- [ ] Dynamisches Aging fuer angerufene Stationen (150s statt 75s)

---

## NOCH OFFEN

1. **Erster vollstaendiger QSO-Durchlauf** noch nicht getestet
2. **FT4-Modus** nicht implementiert (7.5s Zyklen)
3. **ITU-Prefixe** noch nicht vollstaendig (~85% nach heutigen Ergaenzungen)

---

## IDEEN / SPAETERE FEATURES

### DX Cluster / PSKReporter konsumieren (Prio: MITTEL)
- PSKReporter API oder DX Cluster (Telnet) als Input nutzen
- Alert wenn gesuchte DXCC-Entity gerade auf aktivem Band gehoert wird
- Ziel-Callsign/DXCC-Liste → automatische Benachrichtigung

### macOS Menu Bar Extra (Prio: NIEDRIG)
- Symbol in Menuleiste: Band, Stationszahl, Decode-Status
- Library: rumps oder pyobjus

---

## NICHT machen (bewusste Entscheidung)

- Library wechseln (PyFT8 2.6.1 funktioniert, Risiko zu hoch)
- DAXIQ statt Audio (Overkill, kein Gewinn fuer FT8)
- Parallele Test-Skripte zum Radio (NIE WIEDER!)
- Auto-Bias ohne UCB1 (Bias-Spirale mathematisch gefaehrlich)
- FT2 (noch nicht oeffentlich verfuegbar, keine Python-Implementation)

---

## Leistungsdaten

| Metrik | SimpleFT8 NORMAL | SimpleFT8 DIVERSITY | IC-7300 WSJT-X |
|--------|-----------------|--------------------|----------------|
| 40m Stationen (gut) | 13 | **43** | — |
| 40m Stationen (schlecht, 4min) | **9** | **13** | — |
| 20m Stationen | 8 | **63** | 13 |
| 15m PSK Spots | — | **25** (TX) | — |
| Weiteste RX | — | **Kiribati ~13.000 km** | — |
| Weiteste TX | — | **Indonesien 11.996 km** | — |
| 40m Ausreisser Diversity | — | **Russland ~2054km** (Normal: nicht dekodiert) | — |

**SimpleFT8 DIVERSITY > IC-7300 WSJT-X (63 vs 13 auf 20m)**

---

*04.04.2026 Abend — DA1MHH / Mike + Claude + DeepSeek — UCB1, Bugfixes, README, Feierabend*
