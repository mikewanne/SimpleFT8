# SimpleFT8 — Projekt-Dokumentation

**Rufzeichen:** DA1MHH | **Locator:** JO31 | **Radio:** FlexRadio 8400M
**Erstellt:** 29. Maerz 2026 | **Letztes Update:** 07. April 2026
**Status:** v0.19 — ft8lib C-Backend (MIT, 400x schneller), QSO 2min->1min, kein GPL mehr

---

## Was ist SimpleFT8?

Minimaler FT8/FT4 Client fuer macOS. Gegenentwurf zu WSJT-X.
Kein Wasserfall, kein Klimbim. 3-Fenster-Layout: Empfang | QSO-Verlauf | Control.
Der Operator ist der DX-Hunter — die Software macht den Papierkram.

**Kein SmartSDR noetig!** Komplett standalone ueber VITA-49.

## Quick Start

```bash
cd "/Users/mikehammerer/Documents/KI N8N Projekte/FT8/SimpleFT8"
./venv/bin/python3 main.py
```
Alte Instanzen werden automatisch beendet.

## Tech-Stack

| Komponente | Technologie |
|-----------|-------------|
| GUI | Python 3.12 + PySide6 |
| FT8 Decode/Encode | libft8simple.dylib (C, MIT, kgoba/ft8_lib) |
| Audio RX | VITA-49 UDP DAX RX (Fallback: remote_audio_rx) |
| Audio TX | VITA-49 UDP DAX TX (float32 stereo 48kHz, PCC 0x03E3) |
| Rig Control | SmartSDR TCP API (Port 4992) |
| Logging | ADIF 3.1.7 (Append) |
| Config | ~/.simpleft8/config.json |

## Architektur

```
SimpleFT8/
├── main.py                  # App-Einstieg + Instanz-Cleanup
├── config/
│   └── settings.py          # Settings, Band-Frequenzen, FlexRadio IP
├── core/
│   ├── decoder.py           # FT8 Decoder (PyFT8 + Signal Subtraction + Whitening + Anti-Alias)
│   ├── encoder.py           # FT8 Encoder (PyFT8 → VITA-49 TX)
│   ├── message.py           # FT8-Message Parser (CQ, Report, Grid, RR73)
│   ├── qso_state.py         # QSO-Zustandsmaschine (Hunt + CQ Modus)
│   ├── timing.py            # UTC-Takt, 15s/7.5s Zyklen
│   ├── ntp_time.py          # DT-basierte Zeitkorrektur (Median-DT aus Dekodierungen, UNGETESTET)
│   ├── ap_lite.py           # AP-Lite v2.2: Schwache QSOs retten via Kohärenter Addition (DEAKTIVIERT)
│   ├── propagation.py       # Bandbedingungen von HamQSL.com (poor/fair/good, Tageszeit-Korrektur)
│   └── omni_tx.py           # Experimentelles TX-Scheduling (DEAKTIVIERT)
├── radio/
│   ├── base_radio.py        # RadioInterface ABC — Kontrakt für alle Radio-Implementierungen
│   ├── presets.py           # PREAMP_PRESETS — Band-Gain-Werte (radio-agnostisch)
│   ├── radio_factory.py     # create_radio(settings) → FlexRadio | IC7300Interface (zukünftig)
│   └── flexradio.py         # SmartSDR TCP + VITA-49 RX/TX Audio-Streaming
├── log/
│   └── adif.py              # ADIF 3.1.7 Writer
├── ui/
│   ├── main_window.py       # 3-Fenster QSplitter Layout
│   ├── rx_panel.py          # Empfangsliste (rot=CQ, gruen=fertig)
│   ├── qso_panel.py         # QSO-Verlauf (TX/RX chronologisch)
│   └── control_panel.py     # Modus/Band/Freq/Power/CQ-Button/Auto
├── requirements.txt
├── PROBLEME.md              # Bekannte Probleme + Loesungen
└── venv/                    # Python Virtual Environment
```

## FlexRadio Verbindung (OHNE SmartSDR!)

- **IP:** 192.168.1.68 (Auto-Discovery per UDP Broadcast)
- **TCP Port 4992:** Befehle
- **UDP Port 4991:** VITA-49 Audio-Streaming (RX + TX)

### Verbindungssequenz

```
1. TCP connect → V (Version) + H (Handle)
2. client gui SimpleFT8
3. client udpport 4991
4. UDP Socket binden, 1-byte an Radio:4992 senden
5. slice set 0 tx=1 / interlock tx1_enabled=1 / transmit set rfpower=50
6. slice set 0 dax=1 / transmit set dax=1
7. dax audio set 1 slice=0                    ← KRITISCH!
8. stream create type=dax_rx dax_channel=1    ← RX Stream
9. stream create type=dax_tx1                 ← TX Stream (NICHT "dax_tx dax_channel=1"!)
10. FT8 Preset anwenden (AGC slow, NR/NB/ANF off)
```

### TX-Audio Format (VITA-49)

- **float32 stereo big-endian @ 48kHz**
- PCC: 0x03E3, ICC: 0x534C, OUI: 0x001C2D
- 128 Stereo-Paare (256 floats) pro Paket
- KRITISCH: **int16 MONO big-endian @ 24kHz (PCC 0x0123)!**
- NICHT float32 stereo (PCC 0x03E3) — das erzeugt nur Dauerton!
- Stream: `dax_tx` (NICHT dax_tx1, NICHT remote_audio_tx!)
- Header: Type=1, C=1, TSI=3, TSF=1 (W0=0x1CD1xxxx)
- 128 Mono-Samples pro Paket (256 Bytes)
- Pacing: 128/24000 = 5.33ms pro Paket
- Senden an Radio-IP Port **4991**
- Audio bei 12kHz erzeugen (PyFT8) → auf 24kHz resamplen
- Quelle: AetherSDR `src/core/AudioEngine.cpp` Zeile 948-998

### RX-Audio Format (VITA-49)

- Empfang: int16 mono big-endian @ 24kHz (PCC 0x0123) mit `send_reduced_bw_dax=1`
- Resampling auf 12kHz mit Anti-Alias Sinc-Filter (63 Taps, Hamming)

## Decoder-Pipeline

```
VITA-49 Audio (24/48kHz)
  → Anti-Alias Tiefpass (Sinc/Hamming, fc=6kHz)
  → Resample auf 12kHz
  → DC-Remove
  → Spectral Whitening (Overlap-Add FFT, Median-Noise-Floor)
  → Normalisierung (-12 dBFS)
  → Fenster-Sliding (0, +0.3s, -0.3s Offset)
  → FT8 Decode (Costas-Sync → Demap → LDPC → CRC → Unpack)
  → Signal Subtraction (bis 3 Passes)
  → Ergebnis-Fusion + Deduplizierung
```

## QSO-Modi

### Hunt-Modus (Station anklicken)
```
IDLE → TX_CALL → WAIT_REPORT → TX_REPORT → WAIT_RR73 → TX_RR73 → LOG → IDLE
```

### CQ-Modus (CQ-Button)
```
IDLE → CQ_CALLING → CQ_WAIT → (Anrufer) → TX_REPORT → WAIT_RR73 → TX_RR73 → LOG → CQ_CALLING
```
- QSO-Zaehler: "(X) QSOs bearbeitet"
- Auto-Wiederholung CQ nach 2 Zyklen ohne Antwort

## Was funktioniert (05.04.2026)

- FlexRadio Discovery + TCP/UDP Verbindung (standalone!)
- SmartSDR-M Auto-Disconnect + eigener Panadapter/Slice
- VITA-49 RX Audio-Stream + FT8-Dekodierung (typisch 10-20 Stationen/Zyklus auf 20m/40m)
- **VITA-49 TX funktioniert!** int16 mono 24kHz, 155 PSKReporter Spots weltweit
- **TEMPORAL POLARIZATION DIVERSITY!** Antenne pro Zyklus wechseln (ANT1/ANT2)
  - Stationen akkumulieren, bei Duplikaten besseren SNR behalten
  - Markierung: [A1], [A2], [A1>2], [A2>1]
  - Bis 63 Stationen akkumuliert bei Diversity (20m)
  - Stationen altern nach 2 Min raus, UTC zeigt letzte Erfassung
  - Funktioniert auf JEDEM FlexRadio mit 2 Antennenanschluessen (auch 1-SCU)
- **DX Tuning Dialog** — automatische Antennen+Preamp Messung mit Top-5 SNR
  - Presets pro Band gespeichert, bei Bandwechsel automatisch geladen
  - ANT2 (Regenrinne) +5.6 dB besser als ANT1 auf 20m
- **3-Klick RX-Modus:** NORMAL → DIVERSITY → DX TUNING
- **QSO State Machine komplett:**
  - Hunt-Modus (Station anklicken) + CQ-Modus (auto)
  - Stationen antworten: DK5ON, UR5DU, UR5WCS, DB2HA, IN3LHF, F5PBG
  - Anrufversuche einstellbar (3/5/7/99)
  - TX-Queue fuer Antworten waehrend CQ
  - Even/Odd Slot-Korrektur
  - TX-Frequenz 1500 Hz (WSJT-X Standard)
  - caller/target Fix (korrekte Zuordnung wer ruft wen)
  - Station-Wechsel bricht laufendes QSO ab
- QSO-Panel aufgeraeumt: nur QSO-Traffic, Status via MessageBox
- 3-Panel GUI Dark Theme (QTableWidget mit UTC/dB/DT/Freq/Land/km/Antenne)
- Band-Wechsel → Radio-Steuerung
- Sort-Buttons: Zeit / dB / km / Land
- Laender-Erkennung aus Callsign-Prefix + Entfernung in km
- Signal Subtraction (5 Passes) + Spectral Whitening + Anti-Alias Resampling
- Noise-Floor-basierte Normalisierung
- LDPC 50 Iterationen, 200 Kandidaten, Multi-Sync LLR-Sweep
- SWR-Alarm nur Statusbar (kein Popup), ALC-Meter, TX Audio-Level, Power-Slider
- Info-Buttons in Settings mit Reset auf Standardwerte
- Config-Dialog, ADIF-Export, Settings persistent (JSON)

## Git Workflow (PFLICHT bei jedem Feature-Push!)

**Repository:** https://github.com/mikewanne/SimpleFT8.git

### Tagging-Strategie
Bei JEDEM Feature-Push einen Tag setzen:
```bash
git add <dateien>
git commit -m "feat: kurze Beschreibung"
git tag -a v0.X-feature-name -m "Kurzbeschreibung"
git push origin main --tags
```

### Zu alter Version zurueck
```bash
# Nur anschauen (safe):
git checkout v0.5-filter-ui

# Zurueck zu main:
git checkout main

# Dauerhaft rollback (VORSICHT: loescht nicht-committete Aenderungen!):
git reset --hard v0.5-filter-ui
```

### Tags bisher
- `v0.5-filter-ui` — Land-Filter, Ant-Filter, Spaltenkoepfe, 50:50 Layout, Splitter-Speichern
- `v0.6-diversity-proof` — Diversity-Beweis mit Messergebnissen
- `v0.7-bugfixes` — UI-Schutz, DX Tuning, Prefixe
- `v0.8-ucb1-readme` — UCB1 Algorithmus, README ueberarbeitet
- `v0.9-dashboard-aging-prefixes` — Diversity Dashboard, dynamisches Aging, ITU-Prefixe
- `v0.10-max-calls` — Anrufversuche-Setting (3/5/7/99)
- `v0.11-qso-fix` — QSO-Flow komplett ueberarbeitet, caller/target Fix, Even/Odd Slots
- `v0.12-qso-flow` — 155 PSKReporter Spots, Stationen antworten, QSO-Sequenz laeuft
- `v0.13-auto-power` — Auto TX Power Regulation, 10 Buttons, Peak-Monitor, UI Redesign
- `v0.14-logbook` — Integriertes Logbuch, QSO Detail Overlay, QRZ.com API
- `v0.15-logbook-docs` — Logbuch Polish, 3 Innovation Docs mit Screenshots
- `v0.16-bugfixes` — R-Report, Memory Leak, Thread Safety, AP Decoder
- `v0.17-power-pi` — PI Controller, rfpower Headroom, non-blocking QRZ
- `v0.18-robust-qso` — Bandwechsel-Schutz, HALT, QSO Timeouts, deutsche Docs
- `v0.19-ft8lib-c` — ft8lib C-Backend (MIT), 400x schneller, QSO 2min->1min, kein GPL
- `v0.20-diversity-cq-fixes` — Diversity-Messung pausiert bei CQ/QSO, UCB1-Ratio, CQ-Freq-Histogramm
- `v0.21-dt-correction` — DT-basierte Zeitkorrektur (ntp_time.py), FrequencyHistogramWidget
- `v0.22-ap-lite-skeleton` — AP-Lite v2.2 Skeleton (deaktiviert, AP_LITE_ENABLED=False)
- `v0.23-propagation-bars` — Propagation-Balken unter Band-Buttons (HamQSL + Tageszeit-Korrektur)
- `v0.24-omni-tx-skeleton` — Experimentelles TX-Scheduling Skeleton (deaktiviert)
- `v0.24.1-bugfixes` — DeepSeek-Review: 3 Bugfixes (omni_tx Block-Switch Guard, propagation dead code, ntp_time Thread-Safety)
- `v0.24.2-diversity-fix` — 50:50 Diversity Bug: A1-A2-A1-A2 → A1-A1-A2-A2 (Even+Odd beide pro Antenne, echter per-Station Diversity)
- `v0.25-radio-abstraction` — RadioInterface ABC + radio_factory.py + presets.py (IC-7300 Fork vorbereitet)

### Regel
→ Vor jedem nicht-trivialen Feature: zuerst committen was stabil ist + taggen.
→ Dann neues Feature bauen. So kann man immer zum letzten stabilen Stand.

---

## Offen / Naechste Schritte (siehe TODO.md fuer Details)

1. **DT-Zeitkorrektur (core/ntp_time.py)** — implementiert, UNGETESTET. Feldtest: Vorzeichen, Smoothing, Threshold validieren.
2. **AP-Lite v2.2 (core/ap_lite.py)** — Skeleton fertig, AP_LITE_ENABLED=False. Noch fehlt: Encoder-Integration + 2 Hooks in main_window.py.
3. **Experimentelles TX-Scheduling (core/omni_tx.py)** — Skeleton fertig, deaktiviert. Noch fehlt: 3 Hooks in _on_cycle_decoded.
4. **Propagation-Balken (core/propagation.py)** — Aktiv! Feldtest: Farben plausibel? Tageszeit-Korrektur stimmt?
5. **Architektur-Refactoring** — main_window.py + flexradio.py aufteilen (langfristig)
6. **Features:** QSO-Resume, Logbuch loeschen/editieren, FT4, Antennen-Info im QSO Log

## FLEX-8400M Verbindungssequenz (AKTUELL, Stand 30.03.2026)

```
# Phase 1: SmartSDR-M disconnecten (gibt Receiver frei)
tcp1 = connect()
client gui → sub client all → SmartSDR-M Handle finden
client disconnect <handle>
tcp1.close()
time.sleep(2)

# Phase 2: Frisch verbinden + eigenen Slice erstellen
tcp2 = connect()
client gui
time.sleep(5)  # Persistence
client set send_reduced_bw_dax=1
keepalive enable
sub slice/tx/audio/dax/radio all
client udpport 4991

# Eigenen Panadapter + Slice erstellen
display panafall create x=500 y=300   ← Parameter MUESSEN >0 sein!
# → Slice 0 automatisch erstellt

# Konfiguration
slice tune 0 14.074
slice set 0 mode=DIGU / tx=1 / dax=1
interlock tx1_enabled=1
transmit set rfpower=50 / dax=1
dax audio set 1 slice=0
stream create type=dax_rx dax_channel=1
stream create type=dax_tx1

# Keepalive alle 5s: ping
```

## Config

```json
{
  "callsign": "DA1MHH",
  "locator": "JO31",
  "power_watts": 50,
  "flexradio_ip": "192.168.1.68",
  "flexradio_port": 4992,
  "band": "20m",
  "mode": "FT8",
  "audio_freq_hz": 1000,
  "max_decode_freq": 3000
}
```
