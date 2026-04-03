# SimpleFT8 — TODO & Roadmap

**Stand:** 02.04.2026 abends | **Status:** TEMPORAL POLARIZATION DIVERSITY! 48 Stationen bei POOR, 3x NORMAL, IC-7300 geschlagen!
**Backup:** backup_diversity_stable/

---

## Was FUNKTIONIERT (nicht anfassen!)

- [x] FlexRadio Verbindung (SmartSDR-M Disconnect, eigener Slice, Keepalive)
- [x] VITA-49 RX Audio (int16 mono 24kHz, PCC 0x0123)
- [x] VITA-49 TX Audio (int16 mono 24kHz, dax_tx, Opus-Header)
- [x] FT8 Decoder (PyFT8 + Noise-Floor-Norm + LDPC 50 Iter + Multi-Sync + 5 Subtraction Passes)
- [x] FT8 Encoder (PyFT8 12kHz → 24kHz int16 mono BE)
- [x] OSD Fallback-Decoder (eingebaut, braucht Tuning)
- [x] GUI: QTableWidget RX-Panel, Ländernamen, km, Sortierung, RX ON/OFF
- [x] GUI: Band-Wechsel, Power-Slider, TX-Level, TUNE, Watt/SWR/ALC
- [x] GUI: PSKReporter-Anzeige (Spots, km, Richtungen, Map-Button)
- [x] GUI: Config-Dialog (Einstellungen-Button)
- [x] GUI: CQ-Modus, QSO State Machine, ADIF Export
- [x] Instanz-Cleanup (osascript + pkill + Port-Check)
- [x] DT-Korrektur (geeicht an SDR-Control)
- [x] SWR-Schutz (TX blockiert bei hohem SWR)

---

## Erkenntnisse 02.04.2026 — EPISCHER TAG

- **TEMPORAL POLARIZATION DIVERSITY erfunden und implementiert!**
  - Antenne pro FT8-Zyklus wechseln (ANT1 ↔ ANT2), Stationen akkumulieren
  - NORMAL: 14 Stationen → DIVERSITY: 48 Stationen (3.4x!)
  - Funktioniert auf jedem FlexRadio mit 2 Antennenanschluessen, auch 1-SCU
  - Kein zweiter Slice noetig, ein Decoder, ~20 Zeilen Code
  - Neuseeland (18.000 km) empfangen bei POOR Conditions mit Regenrinne!
- **DX Tuning Dialog** mit automatischer Top-5 SNR Messung
  - Presets pro Band, automatisch laden bei Bandwechsel
  - ANT2 (Regenrinne) +5.6 dB besser als ANT1 (Multiband-Dipol) auf 20m
- **FLEX-8400M hat nur 1 SCU** — echtes Simultandiversity braucht 8600M
  - Aber: Temporal Diversity liefert 90% des Nutzens auf dem halben-Preis-Radio
- QSO-Panel aufgeraeumt, Statusmeldungen via MessageBox
- 3-Klick RX-Modus: NORMAL / DIVERSITY / DX TUNING
- LEVEL Meter Fix (src=SLC + num=slice_idx Matching)
- Mail an Marcus Roskosch (DL8MRE, HAM-Radio-Apps.com) mit Feature-Idee geschrieben

## Erkenntnisse 01.04.2026

- SimpleFT8 schlaegt SDR-Control auf GLEICHEM FLEX-8400M: 13 vs 12 Stationen
- Bei gemeinsamen Stationen 4-18 dB staerker als IC-7300
- FLEX-8400M hat hoeheren Noise Floor als IC-7300 (-128 vs -140 dBm) → schwache Signale <-15 dB fehlen
- Das ist BY DESIGN (Direct Sampling 16-bit ADC), KEIN Defekt
- DX-Modus (32-bit float 48kHz) funktioniert, bringt mehr Dynamik
- AP-Decoder funktioniert: -24 dB von 10% auf 45% im Benchmark
- OSD bringt wenig weil Bottleneck die Demodulation ist, nicht LDPC

---

## Phase 1: Empfang optimieren

### 1.1 OSD Tuning (Prio HOCH, Aufwand 1-2h)
- [x] OSD debuggt — bringt bei aktuellem Demodulations-Level wenig (BP schafft -22dB, OSD hilft erst wenn BP fast konvergiert)
- [x] Gauss-Elimination über GF(2) — korrigiert, proper RREF implementiert
- [x] CRC-Check nach OSD — funktioniert
- [x] Benchmarked: OSD depth 1-2, bringt 0 Extra bei aktuellem Demod-Level
- **Erkenntnis:** Bottleneck ist Demodulation (demap), nicht LDPC. OSD bleibt als Fallback drin.
- **Erwarteter Gewinn:** +2-4 Stationen/Zyklus
- **Risiko:** Niedrig (Fallback, ändert BP nicht)

### 1.2 AP-Dekodierung (Prio HOCH, Aufwand 4-6h)
- [ ] LLR-Injection: bekannte Calls → 28 Bits auf ±100 setzen vor BP
- [ ] AP-Datenbank aus `decoder.recent_calls` (schon vorhanden!)
- [ ] 3-Pass Decoder:
  - Pass 1: Blind (wie jetzt)
  - Pass 2: AP mit eigenem Call (DA1MHH) als Constraint
  - Pass 3: AP mit allen gehörten Calls als Constraint
- [ ] Call-zu-Bits Mapping implementieren (77-Bit FT8 Frame → welche Bits = Call?)
- **Erwarteter Gewinn:** +8-12 Stationen, SNR-Schwelle von -18 auf -24 dB
- **Risiko:** Niedrig (zusätzliche Passes, BP bleibt unverändert)

### 1.3 Spektrum-Akkumulierung (Prio MITTEL, Aufwand 2-3h)
- [ ] Kandidaten-Scores über 2-3 Zyklen gewichtet mitteln
- [ ] Persistente DX-Signale die knapp unter Schwelle liegen → über Schwelle heben
- [ ] MUSS in separatem Thread laufen (sonst blockiert Keepalive → Disconnect!)

### 1.4 DX-Modus Feinschliff (Prio MITTEL, Aufwand 2h)
- [x] NORMAL/DX Schalter eingebaut (16-bit 24kHz vs 32-bit float 48kHz)
- [ ] DX-Modus mid-session umschaltbar machen (braucht Reconnect)
- [ ] DT-Kalibrierung fuer DX-Modus (DT-Werte verschoben durch 48k→24k Downsampling)

### 1.5 Preamp-Optimierung pro Band (Prio MITTEL, Aufwand 2h)
- [ ] LOW/MID/HIGH Preamp pro Band einstellbar
- [ ] "8-10 dB Noise Rise" Regel: Antenne ab → messen → Antenne dran → 8-10 dB Anstieg = optimal
- [ ] FLEX-8400M hat hoeheren Noise Floor als IC-7300 (-128 vs -140 dBm) → Preamp kann helfen
- [ ] Automatische Preamp-Kalibrierung (Noise Floor messen + optimal einstellen)
- [ ] History-Buffer für Sync-Scores pro Frequenz-Bin
- **Erwarteter Gewinn:** +3-5 schwache DX-Stationen
- **Risiko:** Niedrig (additiv)

### 1.4 Blackman-Harris Fenster (Prio NIEDRIG, Aufwand 1h)
- [ ] Audio-Buffer vor PyFT8 mit Blackman-Harris fenstern (statt Hanning)
- [ ] Vorher/Nachher Vergleich: gleiche 15s Audio, Stationen zählen
- [ ] Zurückrollen wenn schlechter
- **Erwarteter Gewinn:** ~1 dB, vielleicht +1-2 Stationen
- **Risiko:** Mittel (Doppel-Fensterung möglich)

---

## Phase 2: Features

### 2.1 Erster QSO-Durchlauf (Prio HOCH, Aufwand 1h)
- [ ] CQ senden → warten auf Antwort → Report → RR73 → ADIF Log
- [ ] Verifizieren: State Machine Übergänge korrekt
- [ ] ADIF-Datei prüfen (Band, Freq, Mode, RST, Grid korrekt?)
- **Das erste echte QSO mit SimpleFT8!**

### 2.2 FT4 Modus (Prio MITTEL, Aufwand 3-4h)
- [ ] Timer auf 7.5s Zyklen umschalten
- [ ] FT4-Frequenzen aus settings.py (schon definiert!)
- [ ] FT4 Encoding/Decoding — PyFT8 unterstützt FT4?
- [ ] GUI: FT4-Button funktional machen
- **Risiko:** Niedrig (separater Timer, gleicher Encoder/Decoder falls PyFT8 FT4 kann)

### 2.3 PSKReporter-Verbesserung (Prio NIEDRIG, Aufwand 2h)
- [ ] Abfrage häufiger wenn TX aktiv (alle 60s statt 180s)
- [ ] Callsign aus Settings statt hardcoded DA1MHH
- [ ] Spot-Historie: Trend anzeigen (wird Reichweite besser/schlechter?)
- [ ] Top-10 weiteste Stationen als eigene Liste

---

## Phase 3: Feinschliff

### 3.1 GUI Polish
- [ ] Spaltenbreiten noch besser (Land-Spalte zu schmal für "Netherlands")
- [ ] QSO-Panel: TX/RX Nachrichten farblich trennen
- [ ] Band-Wechsel: gespeichertes Band korrekt laden (Bug war da)
- [ ] Fenster-Größe speichern/wiederherstellen

### 3.2 Robustheit
- [ ] Auto-Reconnect verbessern (nach Radio-Neustart)
- [ ] Fehlerbehandlung bei UDP-Verlust
- [ ] Logging in Datei (nicht nur stdout)

### 3.3 Packaging
- [ ] PyInstaller Bundle (.app für macOS)
- [ ] Icon, App-Name, Version
- [ ] Einzel-Datei Distribution

---

## NICHT machen (bewusste Entscheidung)

- ❌ Library wechseln (PyFT8 funktioniert, Risiko zu hoch)
- ❌ DAXIQ statt Audio (Overkill, kein Gewinn für FT8)
- ❌ Globus-Karte in App (Browser-Link reicht)
- ❌ NAH/MITTEL/DX Presets (entfernt, automatisch optimal pro Band)
- ❌ Parallele Test-Skripte zum Radio (NIE WIEDER!)

---

## Radio-Einstellungen (optimal, nicht ändern)

```
Mode: DIGU
Filter: 100-3100 Hz
AGC: slow (threshold 50)
NR/NB/ANF/WNB/NBFM/APF: OFF
Preamp: pro Band (80m=0, 40m=10, 20m=10, 15m=20, 10m=20)
DAX: send_reduced_bw_dax=1 (int16 mono 24kHz)
TX: dax_tx Stream, int16 mono 24kHz BE, PCC 0x0123
```

---

## Leistungsdaten (02.04.2026)

| Metrik | SimpleFT8 NORMAL | SimpleFT8 DIVERSITY | SDR-Control IC-7300 |
|--------|-----------------|--------------------|--------------------|
| Stationen | 11-15 | **42-52** | 17-22 |
| Peak | 15 | **52** | 22 |
| Antennen | ANT1 | ANT1 + ANT2 (Regenrinne) | ANT1 |
| Conditions | POOR | POOR | POOR |
| Weiteste Station | — | **Neuseeland 18.000 km** | — |

**SimpleFT8 DIVERSITY > IC-7300 WSJT-X (48 vs 22)**
**Temporal Polarization Diversity: 3x mehr Stationen als Single-Antenna**
**Setup: FLEX-8400M + Multiband-Dipol (10cm Wandabstand) + Regenrinne**

---

*02.04.2026 — DA1MHH / Mike + Claude — Temporal Polarization Diversity Tag*
