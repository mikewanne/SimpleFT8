# SimpleFT8 — TODO & Roadmap

**Stand:** 03.04.2026 abends | **Status:** Diversity STABIL, 63 Stationen 20m, Kiribati 13k auf Regenrinne, GitHub + Forum LIVE
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

---

## Erkenntnisse 03.04.2026 — NOCH EPISCHERER TAG

- **Neuer Rechner (Mac Mini M2)** — SimpleFT8 laeuft auf beiden Rechnern
- **Spectral Whitening Bug gefunden:** numpy 2.4 as_strided zerstoert Signal (Peak→1). Deaktiviert.
- **PyFT8 2.8.0 hat Breaking Changes** — auf 2.6.1 gepinnt
- **Diversity Queue-Desync gefixt:** leere Zyklen muessen Queue poppen
- **63 Stationen auf 20m** (Rekord, Indonesien 11k, Neuseeland 18k, Japan 9k)
- **43 Stationen auf 40m** bei K=4, Fair/Poor
- **15m offen:** Kiribati ~13k, Brasilien ~9.5k, Indonesien ~11k — alles auf Regenrinne!
- **IC-7300 + WSJT-X geschlagen:** 13 vs 32 auf 20m
- **PSKReporter:** 25 Spots, Max 11.996km (YB8DYX Indonesien)
- **GitHub veroeffentlicht:** https://github.com/mikewanne/SimpleFT8
- **FlexRadio Community Forum:** Idea Post live

---

## NAECHSTE PHASE: TX / QSO (Prio HOECHSTE)

### DeepSeek Code-Review Findings (03.04.2026)

**KRITISCH — VOR dem ersten QSO fixen:**

1. **TX-Schutz bei Diversity** (GEFAHR!)
   - Antenne kann waehrend TX umgeschaltet werden
   - Fix: In `_on_cycle_start` TX-Status pruefen, Switch blockieren wenn TX aktiv
   - Beim Senden IMMER auf ANT1 bleiben
   ```python
   if self._rx_mode == "diversity" and self.radio.ip:
       if self.encoder.is_transmitting:  # TX aktiv? Nicht switchen!
           return
   ```

2. **Race Condition Threading**
   - `_diversity_current_ant` wird ohne Lock in verschiedenen Threads gelesen/geschrieben
   - Fix: `threading.Lock()` fuer alle Diversity-Variablen
   ```python
   self._diversity_lock = threading.Lock()
   ```

3. **Thread-Argumente korrekt uebergeben**
   - `ant_cmd` als Parameter an Thread, nicht als Closure-Variable
   ```python
   threading.Thread(target=_switch, args=(ant_cmd, gain), daemon=True).start()
   ```

### Bereits gefixt (03.04.2026 Session)

- [x] TX-Schutz bei Diversity (BUG-1) — encoder.is_transmitting Guard
- [x] Race Condition Lock (BUG-2) — _diversity_lock threading.Lock()
- [x] Closure-Bug Thread-Argumente (BUG-3) — args statt Closure
- [x] is_transmitting Property im Encoder (BUG-4)
- [x] RX OFF stoppt Diversity-Switching + ANT1 reset (neuer Bug)
- [x] Normal-Modus: 2-Min-Akkumulation mit Smart-Timestamps (wie Diversity)
- [x] Station Aging: 120s → 75s (5 Zyklen, DeepSeek-Empfehlung)

### QSO-Kette testen

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

---

## Diversity-Algorithmus verbessern (Prio HOCH)

### 4-Zyklus Even/Odd-Pattern (Mike's Idee, DeepSeek bestaetigt)

**Problem:** Aktuelles 2-Zyklus-Muster hat systematische Blindstellen:
- ANT1 hoert immer nur ungerade Slots → verpasst Stationen die nur auf ANT2 + geraden Slots senden
- ANT2 hoert immer nur gerade Slots → verpasst Stationen die nur auf ANT1 + ungeraden Slots senden

**Loesung: 4-Zyklus-Block mit Block-A/B-Wechsel:**
```
Block A (Zyklen 1-4):
  Zyklus 1 (ungerade): ANT1
  Zyklus 2 (gerade):   ANT2
  Zyklus 3 (ungerade): ANT2  ← ANT2 bekommt auch ungeraden Slot
  Zyklus 4 (gerade):   ANT1  ← ANT1 bekommt auch geraden Slot

Block B (Zyklen 5-8, umgekehrt):
  Zyklus 5 (ungerade): ANT2
  Zyklus 6 (gerade):   ANT1
  Zyklus 7 (ungerade): ANT1
  Zyklus 8 (gerade):   ANT2
```
→ Jede Antenne deckt BEIDE Phasen (gerade + ungerade) ab
→ Keine systematischen Blindstellen mehr
→ Passt perfekt zu 75s Aging (= 5 Zyklen, mindestens 1 kompletter Block)

- [ ] 4-Zyklus-Pattern in `_on_cycle_start()` implementieren
- [ ] `_diversity_cycle % 4` statt `% 2` + Block-A/B-Flag

### Dynamisches Aging fuer angerufene Stationen (DeepSeek-Idee)

- [ ] Station die aktiv angerufen wurde: Aging-Timeout auf 150s erhoehen
- [ ] Begruendung: Warte auf Antwort auch wenn Propagation kurz einbricht
- [ ] Implementation: `_called_stations = set()` in QSOStateMachine, Aging-Check beachtet das

### Antennen-Einmessung vor Diversity (DX Tuning)

- [ ] DX Tuning Dialog laeuft bereits separat — Integration als "vor Diversity Messen"-Empfehlung
- [ ] Bei Diversity-Aktivierung: Hinweis wenn kein Preset fuer aktuelles Band gespeichert

---

## Phase 1: Empfang weiter optimieren

### Spectral Whitening fixen (Prio HOCH)
- [ ] numpy 2.4 kompatible Implementierung (kein as_strided Trick)
- [ ] Einfache Sliding-Window Median ohne Stride-Trick
- [ ] Vorher/Nachher Vergleich: Stationszahl mit/ohne Whitening
- **Erwartet:** +10-20% mehr schwache Stationen

### AP-Dekodierung (Prio HOCH, Aufwand 4-6h)
- [ ] LLR-Injection: bekannte Calls → 28 Bits auf ±100 setzen vor BP
- [ ] AP-Datenbank aus `decoder.recent_calls` (schon vorhanden!)
- [ ] Call-zu-Bits Mapping implementieren (77-Bit FT8 Frame)
- **Erwarteter Gewinn:** +8-12 Stationen, SNR-Schwelle von -18 auf -24 dB

### Fehlende Callsign-Prefixe
- [ ] Systematisch alle ITU-Prefixe einpflegen (aktuell ~80%, fehlen exotische)
- [ ] Online-Datenbank als Fallback (QRZ.com API?)

---

## Phase 2: GUI Verbesserungen

### Diversity-Statistiken (DeepSeek Vorschlag)
- [ ] Zaehler: ANT1 besser / ANT2 besser / nur ANT1 / nur ANT2
- [ ] Anzeige im Control Panel
- [ ] Globus-View: welche Antenne empfaengt aus welcher Richtung besser

### GUI Polish
- [ ] SWR als Balken-/Zeiger-Instrument statt nur Text
- [ ] Watt-Anzeige als Pegel
- [ ] Spaltenbreiten optimieren
- [ ] Fenster-Groesse speichern/wiederherstellen
- [ ] DeepSeek + Claude Review fuer UI-Layout (naechste Session)

---

## Phase 3: Robustheit + Packaging

- [ ] Auto-Reconnect verbessern (nach Radio-Neustart)
- [ ] Logging in Datei (nicht nur stdout)
- [ ] PyInstaller Bundle (.app fuer macOS)

---

## NICHT machen (bewusste Entscheidung)

- Library wechseln (PyFT8 2.6.1 funktioniert, Risiko zu hoch)
- DAXIQ statt Audio (Overkill, kein Gewinn fuer FT8)
- Parallele Test-Skripte zum Radio (NIE WIEDER!)

---

## Leistungsdaten (03.04.2026)

| Metrik | SimpleFT8 NORMAL | SimpleFT8 DIVERSITY | IC-7300 WSJT-X |
|--------|-----------------|--------------------|--------------------|
| 40m Stationen | 13 | **43** | — |
| 20m Stationen | 8 | **63** | 13 |
| 15m PSK Spots | — | **25** (TX) | — |
| Peak | 13 | **63** | 13 |
| Antennen | ANT1 | ANT1 + ANT2 (Regenrinne) | ANT1 |
| Weiteste RX | — | **Kiribati ~13.000 km** | — |
| Weiteste TX | — | **Indonesien 11.996 km** | — |

**SimpleFT8 DIVERSITY > IC-7300 WSJT-X (63 vs 13 auf 20m)**
**Kiribati, Japan, Indonesien, Brasilien, Venezuela, Neuseeland — alles mit Regenrinne**

---

*03.04.2026 — DA1MHH / Mike + Claude + DeepSeek — Epischster Tag*
