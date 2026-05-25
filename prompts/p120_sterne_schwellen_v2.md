# R1 — P120 Sterne-Schwellen FT8-realistisch

## Was ich will

Reviewer. KEIN Code. Severity-Findings, KISS-Bewertung. **Du bist
FT8-Experte:** Sag was realistisch ist. Code ist Referenz.

## Kontext

`compute_local_conditions` in `ui/mw_cycle.py:33-65` zeigt ein 5-Sterne-
Rating für „lokale Empfangsqualität" basierend auf Median-SNR der
Top-Hälfte aller dekodierten Stationen.

**Mike-Field-Beobachtung 25.05.:** Auf 15m FT8 mit Median-SNR **-17 dB**
zeigt die App **3★**. Mike: „-17 dB ist in FT8 normal-gut, Decoder läuft
bis ~-24 dB, Stationen >-10 dB sind außergewöhnlich stark". Heutige
Schwellen sind aus SSB/CW-Denke übernommen — 5★ (> -10 dB) ist
praktisch unerreichbar.

## Aktueller Code (`mw_cycle.py:57-64`)

```python
if median > -10: return 5, n, median   # 5★
if median > -14: return 4, n, median   # 4★
if median > -18: return 3, n, median   # 3★
if median > -22: return 2, n, median   # 2★
return 1, n, median                    # 1★
```

## Mike's Vorschlag (aus TODO.md)

| Sterne | Heute | Mike-Vorschlag |
|---|---|---|
| 5 ★ | > -10 dB | > **-13** dB |
| 4 ★ | > -14 dB | > **-16** dB |
| 3 ★ | > -18 dB | > **-19** dB |
| 2 ★ | > -22 dB | unverändert |
| 1 ★ | drunter | unverändert |

Mike behauptet: „Median -17 würde damit von 3★ auf **4★** springen".

## ⚠ Spec-Inkonsistenz erkannt (V2 Self-Review)

Mit Mike's Schwellen `> -16` für 4★: `-17 > -16` ist **False** →
fällt auf 3★ (> -19), nicht 4★ wie Mike sagt.

Verifikation per Python:
```
Median  -16dB → 3★ (>-16 ist False)
Median  -17dB → 3★ (>-19 ist True)
Median  -18dB → 3★
Median  -19dB → 2★
```

Mike's Outcome-Behauptung „-17 → 4★" stimmt nur wenn 4★-Schwelle
**> -18** oder **>= -17** ist.

## Fragen für R1

**Frage 1 (FT8-Realismus, KRITISCH):**
Sind Mike's Schwellen (-13 / -16 / -19) FT8-realistisch? Du bist
FT8-Experte: was sind typische Median-SNR-Werte bei guten/maessigen/
schlechten Bedingungen? Bandpläne (40m abends vs 20m mittags) und
Solar-Cycle berücksichtigen.

Konkret bewerten:
- **5★ Schwelle**: > -10 dB (alt) vs > -13 dB (Mike). Was ist
  realistisch erreichbar bei „sehr gutem" Empfang?
- **4★ Schwelle**: > -14 dB (alt) vs > -16 dB (Mike) — Mike will -17
  als 4★, aber -16 wäre dann das Limit.
- **3★ Schwelle**: > -18 dB (alt) vs > -19 dB (Mike).
- **Untere Schwellen** (2★ > -22, 1★ drunter) bleiben.

**Frage 2 (Spec-Inkonsistenz auflösen):**
Mike's Outcome „-17 → 4★" stimmt nicht mit seinen Schwellen. Welche
Auflösung ist richtig?

- **Option A:** Mike-Schwellen exakt übernehmen (-13/-16/-19), Mike's
  Outcome-Behauptung ignorieren (war Rechen-Fehler).
- **Option B:** Schwellen so anpassen dass -17 → 4★ ergibt:
  z.B. `> -13 / > -18 / > -21` (Mike's Intent: „-17 dB ist 4★ wert
  für FT8").
- **Option C:** `>= -17` statt `> -17` (semantisch sauberer aber
  Code-Style-Bruch — andere Schwellen sind alle `>`).

**Frage 3 (Test-Anpassungen):**
Bestehende `test_local_conditions.py` hat:
- `test_4_stars` mit SNR -12 → alt 4★, neu 5★ (mit -13-Schwelle)
- `test_3_stars` mit SNR -16 → alt 3★, neu 3★ (mit -16 nicht > -16)

Müsste angepasst werden. Plus: Mike-Field-Test-Beispiel als neuer Test.

**Frage 4 (KISS-Bewertung):**
5 Schwellen-Zeilen Änderung + Docstring + Tests. Pure UI, kein
Hardware. Mike-Spec klar (auch wenn Outcome inkonsistent). Was übersehe
ich?

**Frage 5 (Edge-Cases):**
- Was wenn nur 1 Station dekodiert (Top-Hälfte = 1 Station)? Aktueller
  Code: `top_half = snrs[:max(1, n // 2)]` — OK.
- Solar-Variation: Schwellen sollten konstant sein, nicht solar-adaptiv.
  Korrekt?
- Bandabhängige Schwellen? z.B. 15m anders als 80m? Vermutlich KISS-NEIN.

## Verdict erwartet

FT8-Realismus + Spec-Auflösung. Sag welche Option (A/B/C) du
empfiehlst und warum.
