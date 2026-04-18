# Changelog — SimpleFT8

## v0.25 (2026-04-18)

### Neue Features

**Stations-Statistik Logger**
- Pro-Zyklus Logging: Stationen, SNR, Band, Modus (FT8/FT4)
- Verzeichnis: `statistics/<Modus>/<Band>/<Protokoll>/`
- Modi: Normal, Diversity_Normal, Diversity_DX
- Stunden-Dateien (.md) mit Markdown-Tabelle + Zusammenfassung
- Async via Queue + Daemon-Thread (null Decoder-Impact)
- Auto-Pause bei Antennen-Tuning/Einmessung
- Settings-Toggle: "Statistik-Erfassung aktivieren"
- *Statistik-Konzept: DL2YMR*

**Ant2 Superiority Counter**
- Misst wie oft Ant2 strikt besseren SNR hat als Ant1
- Debug-Ausgabe: `[Diversity] 34 St. | A1>A2: 26 | A2>A1: 8 (24%)`
- Ant2-Wins Spalte in Diversity Stats-Dateien

**Debug-Konsole**
- Ein/ausblendbar via Ctrl+D oder Settings
- Schriftgroesse 11pt (vorher 9pt)
- Live-Filter Eingabefeld (grep-artig)
- Copy + Clear Buttons
- stdout/stderr Umleitung ins UI

**OMNI-TX Verbesserungen**
- Even/Odd Alternierung gefixt (Block 1: Even→Odd, Block 2: Odd→Even)
- CQ-Stop Bug behoben (RX-Slots zaehlen nicht als Fehlversuch)
- Encoder-Paritaet wird korrekt gesetzt
- Button-Label bleibt "OMNI CQ" (nicht mehr ueberschrieben)
- Even/Odd Counter in Statusbar
- Block-Switch Overshoot Bug gefixt (_pending_switch Flag)
- Hilfe-Datei DE+EN erstellt + im Menu

**Adaptive CQ-Frequenzwahl**
- Kollisionserkennung: wechselt sofort wenn TX-Freq belegt
- Minimum Dwell Time: 3 Zyklen
- Zeit-Fallback: alle 10 Zyklen statt 20
- TX-Marker 4px + Glow-Effekt

### Bug Fixes

- **Propagation:** Zeitkorrektur war gecacht statt live → 15m/17m zeigte mittags "Poor" statt "Fair"
- **Diversity Histogram:** Wurde im Diversity-Modus nie aktualisiert (NameError hist_copy)
- **Diversity Pattern:** Even+Odd Paarung — alle Antennen empfangen jetzt beide Paritaeten
- **Histogram:** TX-Freq konnte ausserhalb des Sweetspot landen
- **QSO komplett:** Erscheint nicht mehr doppelt (erst nach 73/Timeout)
- **PSK Reporter:** Erste Abfrage nach 2 Min statt 3, Band+Zeit in Anzeige
- **ADIF:** FT4 → MODE=MFSK + SUBMODE=FT4, erweiterte QRZ/LoTW Felder
- **Tests:** 6 pre-existing Bugs gefixt (_make_msg Monkey-Patch, NTP Deadband)

### Refactoring

- `ui/styles.py` — Stylesheets zentralisiert
- `_update_histogram()` als eigenstaendige Methode
- Histogram-Reset bei Bandwechsel
- Signal-Connections waren schon sauber in `_connect_signals()`
- 132 Tests (116 test_modules + 16 test_patterns)

---

## v0.24 und frueher

Siehe Git-History.
