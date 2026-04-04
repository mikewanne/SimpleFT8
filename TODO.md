# SimpleFT8 — TODO & Roadmap

**Stand:** 04.04.2026 | **Status:** Diversity STABIL, 16 Stationen 40m 05:03 UTC, Bias-Switch live, AP-Decoder live, Spectral Whitening gefixt
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

- [x] 4-Zyklus-Pattern in `_on_cycle_start()` implementieren
- [x] `_diversity_cycle % 4` statt `% 2` + Block-A/B-Flag
- [x] Zyklus-Indikator GUI (4 Boxen + ANT-Label in Control Panel)

### Adaptiver Bias (Mike's Idee — naechste Stufe nach 4-Zyklus)

**Problem:** Wenn ANT2 heute schwaecher ist, kostet 50/50 Aufteilung Stationen.
**Loesung:** Bias-Slider ANT1 ↔ Balanced ↔ ANT2 — manuell oder automatisch.

```
3:1 ANT1 → Block A: ANT1 ANT2 ANT1 ANT1, Block B: ANT1 ANT1 ANT2 ANT1
1:1 Balanced → aktuelles 4-Zyklus-Pattern (Standard)
3:1 ANT2 → Block A: ANT2 ANT1 ANT2 ANT2, Block B: ANT2 ANT2 ANT1 ANT2
```

- [x] **Manueller Bias-Schalter** (5 Preset-Buttons im Control Panel): `100:0 | 70:30 | AUTO | 30:70 | 0:100`
      - AUTO = aktuelles 4-Zyklus Even/Odd Pattern (50:50)
      - Bei 70:30: 5-Slot-Block [A1,A2,A1,A1,A2] → A2 auf Pos 2+5 = gerade UND ungerade ✓
      - Bei 30:70: 5-Slot-Block [A2,A1,A2,A2,A1] → A1 auf Pos 2+5 = gerade UND ungerade ✓
      - Bei Bandwechsel: zurueck auf AUTO — implementiert 04.04.2026
- [ ] ~~Auto-Bias~~ (DeepSeek: Bias-Spirale, mathematisch gefaehrlich → NICHT bauen)
- [ ] Diversity-Dashboard: ANT1-exklusiv / ANT2-exklusiv / Ueberlappung anzeigen (spaeter)

### Dynamisches Aging fuer angerufene Stationen (DeepSeek-Idee)

- [ ] Station die aktiv angerufen wurde: Aging-Timeout auf 150s erhoehen
- [ ] Begruendung: Warte auf Antwort auch wenn Propagation kurz einbricht
- [ ] Implementation: `_called_stations = set()` in QSOStateMachine, Aging-Check beachtet das

### Antennen-Einmessung vor Diversity (DX Tuning)

- [x] DX Tuning Dialog v2: Interleaved 18-Zyklus-Messung (ANT1+ANT2 bei gleichem Gain gleichzeitig)
- [x] Per-Antenne Presets: ant1_gain + ant2_gain separat gespeichert
- [x] Bei Diversity-Aktivierung: Hinweis wenn kein Preset fuer aktuelles Band gespeichert
- [x] Diversity nutzt ant1_gain fuer ANT1 und ant2_gain fuer ANT2 beim Wechsel

---

## Parser-Bugs

- [x] **"DXpedition not implemented"** — `message.py` erkennt PyFT8-Fehler-Prefixe → zeigt `?` statt rohem Exception-Text (04.04.2026)
- [x] **Portable/Mobile Suffixe** — `ON3MOH/P`, `R2FBY/MM` etc. → Prefix vor `/` extrahieren → Land + km korrekt anzeigen (rx_panel.py _populate_row)

---

## Phase 1: Empfang weiter optimieren

### Spectral Whitening (ERLEDIGT 04.04.2026)
- [x] numpy 2.4 kompatibel: `sliding_window_view` statt `as_strided`
- [x] RMS-Threshold gefixt: `1e-6` statt `0.1` (irfft/N Normalisierung beachtet)
- [x] Wieder aktiviert — Peak=32767 stabil, 2-4 Stationen pro Zyklus ✓

### AP-Dekodierung (ERLEDIGT 04.04.2026)
- [x] `core/ap_decoder.py` — LLR-Injection mit i3/CQ/myCall/recentCalls/priorityCall
- [x] `recent_calls` deque(maxlen=200) mit `appendleft()` fuer Recency-Ordering
- [x] `priority_call` = aktiver QSO-Partner → hoechste Prioritaet (59-Bit-Hint)
- [x] Stage 0: QSO-Partner C1 + eigenes Call C2 (staerkster Hint)
- [x] Stage 5: 20 bekannte Calls als C1 + CQ-Kombination

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

- [x] Auto-Reconnect: unbegrenzte Wiederholungen, Exponential Backoff 5→10→20→40→60s, Discovery nach 10 Fehlversuchen, GUI-Countdown (04.04.2026)
- [x] Logging in Datei: `~/.simpleft8/simpleft8.log` via `_Tee` in `main.py` (04.04.2026)
- [x] Fenster-Geometrie: speichern/wiederherstellen in `~/.simpleft8/config.json` (04.04.2026)
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
