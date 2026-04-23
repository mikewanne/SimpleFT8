# DT-Timing Analyse & Optimierung — SimpleFT8
Stand: 2026-04-23 | Mike + Claude + DeepSeek

---

## Architektur-Verständnis

### Wie DT entsteht (RX-Seite)

```
RF-Signal → FlexRadio → VITA-49 UDP → App-Buffer → ft8lib-Decoder
           ~0.1s HW      ~0.17s HW     Buffer-Offset  → DT-Wert
```

Der Decoder wacht 1.5s (FT8) vor Slot-Ende auf.  
Der Audio-Buffer enthält Audio ab 1.5s VOR dem aktuellen Slot-Start.

**WSJT-X Protokoll-Konvention:** TX startet bei t=0.5s im Slot (nicht bei t=0).

Ein "perfektes" WSJT-X Signal liegt bei:
```
Buffer-Position = 0.5s (Signal) - (-1.5s Buffer-Start) = 2.0s vom Buffer-Anfang
ft8lib raw_dt   = 2.0s
```

### Woher kommen die 0.77s Korrektur?

```
raw_dt                   = 2.00s  (WSJT-X Signal im Buffer)
- DT_BUFFER_OFFSET alt   = 1.50s
                         ──────
Korrigierter DT          = 0.50s  ← WSJT-X Protokoll-Offset (nicht Hardware!)
+ FlexRadio VITA-49 HW   ≈ 0.27s  ← echte Hardware-Latenz
                         ──────
Korrektur konvergiert auf  0.77s  ← gemessen, stimmt überein
```

**Erkenntnis:** Die 0.5s kommen NICHT vom Radio, sondern vom WSJT-X Protokoll.
Die 0.27s sind die echte FlexRadio VITA-49 RX-Latenz.

---

## Änderung 1: DT_BUFFER_OFFSET (decoder.py) — UMGESETZT 2026-04-23

**Problem:** 0.5s Protokoll-Offset war im Korrekturwert "versteckt" → Korrektur konvergierte auf 0.77s.

**Fix:** 0.5s Protokoll-Offset direkt im DT_BUFFER_OFFSET einbauen.

| Modus | Vorher | Nachher | Formel |
|-------|--------|---------|--------|
| FT8   | 1.5    | 2.0     | 1.5 + 0.5 |
| FT4   | 0.5    | 1.0     | 0.5 + 0.5 |
| FT2   | 0.3    | 0.8     | 0.3 + 0.5 |

**Erwartetes Ergebnis:**
- Korrektur konvergiert jetzt auf ~0.27s (nur FlexRadio Hardware)
- Stationen zeigen DT ≈ 0 nach wenigen Zyklen
- Konvergiert 3× schneller als vorher

**Achtung:** dt_corrections.json wurde geleert — System lernt neu.

---

## Änderung 2: TX-Timing entkoppeln (encoder.py) — UMGESETZT 2026-04-23

**Problem:** RX-Korrektur (0.77s) wurde auch für TX verwendet.
TX hat aber keine Decoder-Buffer-Verzögerung → TX sendete 0.67s zu früh.

**Fix:** TARGET_TX_OFFSET = 0.5 (WSJT-X Protokoll), keine dynamische Korrektur für TX.

```python
# ALT:
TARGET_TX_OFFSET = 0.0
silence = (boundary - dt_adj) - now   # dt_adj = 0.77 → TX 0.67s zu früh

# NEU:
TARGET_TX_OFFSET = 0.5
silence = (boundary + 0.5) - now      # TX startet bei boundary+0.5s = korrekt
```

**Erwartetes Ergebnis:**
- TX DT ≈ 0 für FT8, FT4, FT2 (nur noch ~0.1s FlexRadio TX-Latenz als Rest)
- FT4 TX-DT-Runaway-Problem behoben

---

## CPU-Abhängigkeit der Verarbeitung

**Frage:** Ist die App-Verzögerung CPU-abhängig?

**Ergebnis (DeepSeek-Analyse):**
- np.convolve 63 Taps × 360k Samples: 10ms (schnell) bis 50ms (langsam)
- 174× FFT(2048) + iFFT: 20ms bis 80ms
- np.add.at Overlap-Add: 10ms bis 50ms
- **Gesamt CPU: <50ms modern, <200ms alt**
- **NICHT die Ursache der 0.77s** — die CPU-Zeit beeinflusst DT-Werte nicht

Die 0.77s sind **KONSTANT** und hardware/protokoll-bedingt.

---

## Offene Fragen / Nächste Schritte

### RX (erst lösen):
- [x] Beobachten: Konvergiert Korrektur auf ~0.27s? **JA — konvergiert auf +0.24s** ✓
- [x] Beobachten: Zeigen Stationen DT ≈ 0 nach Konvergenz? **JA — 12 Stationen auf 0.0/0.2, 1-2 Ausreißer (externe Ursache)** ✓
- [ ] Prüfen: FT4 RX — konvergiert schneller/stabiler als vorher?

### TX (danach):
- [x] FT8 TX DT gemessen (Icom): **+1.3s konstant** → FlexRadio TX-VITA-49-Buffer = 1.3s ✓
- [x] Fix: TARGET_TX_OFFSET = 0.5 - 1.3 = **-0.8s** → Audio 1.3s früher senden ✓
- [x] FT8 TX DT nach Fix gemessen (Icom): **0.0s** ✓✓
- [ ] FT4 TX DT prüfen → war -0.5 bis -1.1, soll ≈ 0 sein nach Fix

### Weitere geplante Verbesserungen (noch nicht umgesetzt):
- [ ] Per-Band+Modus Speicherung: Key "FT8_20m" statt "FT8"
- [ ] Engere Korrektur-Grenzen: FT8=±2.0s, FT4=±1.0s, FT2=±0.5s
- [ ] Gedämpfte Erstkorrekturen bei <3 Stationen

---

## Theorien / Hypothesen

### TX DT = -0.5 bei FT4 mit Korrektur=0 (GELÖST durch Änderung 2)
- Ursache: RX-Korrektur 0.77s wurde auf TX angewendet → silence=0 → TX 0.5s zu früh
- Fix: Entkopplung TX/RX in encoder.py

### FT2 Korrektur = 1.9s (PROBLEM)
- War klar falsch: 50% eines 3.8s Slots
- Ursache: wenige Stationen, keine Dämpfung, Runaway
- dt_corrections.json geleert → neu lernen

---

## Backup

`Appsicherungen/2026-04-23_vor_dt_optimierung_core/` + `_ui/`
Zurückspringen: `cp -r Appsicherungen/2026-04-23_vor_dt_optimierung_core/* core/`
