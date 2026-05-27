# AP-Lite Strategie-Konsultation — Feld-Daten zeigen Algo funktioniert nicht

Wir haben für SimpleFT8 (FT8 FlexRadio Hobby-Funker-Tool, DA1MHH/Mike) die Feature
"AP-Lite" gebaut — eine A-Priori-Schicht oberhalb des Decoders, die marginale
Partner-Decodes via Matched-Filter-Korrelation gegen FT8-Kandidaten "retten" soll.

**Mike's Ziel:** marginale Signale bei -24 bis -26 dB SNR noch erkennen
(z.B. DXpeditions, Falklands — die "Perlen" wo nahe Stationen gute SNRs haben
und nur die schwachen interessant sind).

**FT8-Decoder-Limit (kgoba ft8_lib):** typischerweise -21 dB, mit "Deep"-Settings
geht WSJT-X bis -24 dB.

## Architektur AP-Lite (heutiger Stand v0.98.31)

### Kandidaten-Generierung (`core/ap_lite.py:95-141`)

```python
def generate_candidates(qso_state, their_call, own_call, locator, snr_estimate):
    if qso_state == 1:  # WAIT_REPORT (Partner soll uns Signal-Report senden)
        # 11 Varianten: "DA1MHH SX20RCK -09" bis "DA1MHH SX20RCK -19"
        # (snr_estimate ± 5 dB, Schrittweite 1 dB)
        for snr_delta in range(-5, 6, 1):
            r = max(-30, min(29, snr_clamped + snr_delta))
            candidates.append(f"{own_call} {their_call} {r:+03d}")
    elif qso_state == 2:  # WAIT_RR73 (Partner soll RR73 senden)
        # 3 Varianten: "DA1MHH SX20RCK RR73", "73", "RRR"
```

### Korrelator (`core/ap_lite.py:169-225`)

Nicht-kohärenter Matched Filter:
1. `encoder.generate_reference_wave(candidate_msg, freq_hz, SAMPLE_RATE)` →
   FT8-Referenzsignal aus String generieren
2. Hilbert-Transformation beider Signale (Empfang + Referenz)
3. `mixed = conj(ref_analytic) * buf_analytic`
4. FFT → Frequenz-Offset-Suche ±FREQ_SEARCH_HZ
5. `score = max(spectrum) / (norm(ref) * norm(buf))` ∈ [0, 1]

### Entscheidung

- `margin = best_score - runner_up_score`
- Match wenn `margin >= margin_min` (locker=0.04, normal=0.05, streng=0.10)

## Feld-Daten (Mike, 27.05.2026, 3 QSOs, ~70 Min)

```
208 GUARD_SKIP wrong_state IDLE (normal, keine QSOs in der Phase)
 32 CALLs (in QSO-Phase = WAIT_REPORT, state=1)
 16 SCORED-Auswertungen (die anderen 16 brachen frueher ab — wahrscheinlich Pre-PCM-Check)
  0 MATCHES (= 0% Trefferquote)
 16 NO_MATCH
```

**Score-Verteilung (Top 10):**

```
best=0.045  margin=0.003  DA1MHH YO9IAB -15
best=0.023  margin=0.001  DA1MHH YO9IAB -18
best=0.019  margin=0.005  DA1MHH YO9IAB -15
best=0.007  margin=0.000  DA1MHH RU3X -11
best=0.007  margin=0.000  DA1MHH SX20RCK -13
best=0.006  ...
```

**Decoder-Vergleich (Test-Modus):** Decoder hat in ALLEN 16 Vergleichs-Slots
NICHTS dekodiert (`decoder='None'` 16×). Wir können also nicht messen
"Algo stimmt mit Decoder überein" — der Decoder ist hier auch blind.

**Partner-SNR-Filter (R1-F3-Fix):** greift 0× ein. War nicht die Ursache
für rescue_count=0.

## Meine Hypothese — bitte verifiziere/widerlege

**Die Margen sind ~0 weil sich die 11 Kandidaten nur in 7 Bit (SNR-Wert)
unterscheiden:**

- FT8 codiert 77-Bit-Payload zu 174 Bit (LDPC) → 8-FSK über 79 Symbole
- "DA1MHH SX20RCK -09" vs "DA1MHH SX20RCK -10" differiert nur im
  Signal-Report-Feld (7 Bit für i3=1 Type-Frames mit Report)
- Nach LDPC-Encoding ist der Unterschied stochastisch über die 174 Bits
  verteilt — aber im Erwartungswert sind ~96% der Bits identisch
- → Korrelator-Score "+0.5%" Unterschied zwischen Kandidaten ist physikalisch
  zu erwarten

**Wenn das stimmt: der Margin-Diskriminator funktioniert NUR für sehr
unterschiedliche Kandidaten — z.B. WAIT_RR73 mit 3 strukturell verschiedenen
Nachrichten (RR73 vs 73 vs RRR). Bei WAIT_REPORT mit SNR-Variationen ist
Margin systematisch nahe null.**

**Korollar:** Best-Score 0.045 als Maximum deutet darauf hin dass im Slot
KEIN Signal des Partners war (sonst Score > 0.3-0.7). Mike's 3 QSOs hatten
einfach Partner die nicht geantwortet haben.

## Decoder-Tiefe als Alternative

```c
// ft8_lib/libft8simple.c (3× verwendet)
const int kMax_candidates  = 140;        // bereits hoch
const int kLDPC_iterations = 50;         // bereits hoch (WSJT-X: 20-40)
const int kMin_score       = 10;         // ← WSJT-X "Deep" nutzt ~2.5
```

`kMin_score=10` filtert Sync-Pattern unter Schwelle 10 aus. Senken auf 2.5
würde mehr schwache Sync-Patterns durchlassen → tiefere Decodes, aber
Rechenlast steigt + Falsch-Positiv-Risiko.

## Meine 3 Optionen

### A) AP-Lite verwerfen
- Datenlage klar negativ (0/16)
- Architektur-bedingt kann Margin-Diskriminator hier nicht funktionieren
- Mike's Wunsch -24 dB sehr ambitioniert für Hobby-Tool

### B) AP-Lite umbauen
- Margin-Diskriminator ersetzen durch absoluten Score-Threshold + Constraint
  "Decoder hat im Slot nichts gefunden + best-Score > 0.3"
- Risiko: Falsch-Positive bei reinem Rauschen (best=0.045 als Maximum gibt 0
  echte Treffer, aber statistisches Rauschen kann mal höher liegen)

### C) ft8_lib-Decoder-Tiefe hochschrauben
- `kMin_score` von 10 auf 3-5 senken
- AP-Lite verwerfen
- WSJT-X-Niveau (-24 dB) ist mit Deep-Settings dokumentiert erreichbar
- Risiko: mehr Falsch-Decodes, CPU-Last höher (egal auf moderner Hardware)

## Frage an dich

1. **Stimmt meine Diagnose** (Margin-Diskriminator architektonisch unmöglich
   für WAIT_REPORT-Variationen wegen ~96% Bit-Identität)?
2. **Welche Option** (A/B/C) — oder eine vierte die ich übersehe?
3. **Bei C:** ist `kMin_score=10 → ~3` sinnvoll? Gibt es Erfahrungswerte
   aus kgoba's ft8_lib oder WSJT-X-Code?
4. **Wenn B:** welcher absolute Threshold wäre für nicht-kohärente
   Matched-Filter-Korrelation realistisch (best-Score-Verteilung bei
   echtem Signal vs Rauschen)?

Kritisch antworten, halluzinieren ist verboten. Bei Unsicherheit sage
"weiß ich nicht" statt zu raten. Mike ist erfahrener Funker, Entscheidung
fällt bei mir nach deinem Input.
