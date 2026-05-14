# Review-Auftrag fuer R1 (deepseek-reasoner)

Du bist erfahrener Python-Engineer + Signal-Processing-Reviewer. **Du loest das Problem NICHT — du kritisierst und verbesserst den Plan.**

## Kontext (FT8-Funk-Tool SimpleFT8, v0.97.15, Hobby-Projekt)

Mike sieht in FT8-RX-Panel die DT-Werte (Time-Delta zur Slot-Boundary) klar asymmetrisch im Minus. Korrektur in `core/ntp_time.py` steht auf **+0.2705s**, RX-Stationen zeigen aber Median ~-0.1s. System sollte Median bei 0 ± 0.05 halten.

**Mike's Screenshot 20 RX-Stationen, sortiert:**
```
-1.2, -0.7, -0.7, -0.4, -0.3, -0.2, -0.1, -0.1, -0.1, -0.1,
-0.1,  0.0,  0.0,  0.0,  0.0,  0.0,  0.0,  0.0,  0.0, +0.3
```

11 negativ, 1 positiv (≥0.1), 8 nahe 0. Ausreißer bei -1.2, -0.7, -0.7, -0.4, -0.3 (vermutlich Mobile/QRP/QSB).

## Aktueller Algorithmus (core/ntp_time.py)

- `update_from_decoded(dt_values)` pro Slot
- `valid = [-2.0 ≤ dt ≤ 2.0]` Filter
- `median_dt = statistics.median(valid)` (einfacher Median)
- MEASURE-Phase: 2 Slots sammeln, dann `avg_median = median(buffer)`
- `if abs(avg_median) > DEADBAND (0.05)`: `_correction += avg_median * DAMPING (0.7)`
- OPERATE: 10 Slots Pause, dann zurück MEASURE
- Max-Korrektur FT8: ±1.0s
- Sprung-Reset bei |median| > 1.0
- P48-D Fast-Path: 1 Slot reicht wenn _is_initial + ≥10 Stationen + stddev < 0.1

## V3-Plan (geplante Aenderung, Variante C)

**Primaer:** `_trimmed_median(values, trim_frac=0.1)` — bei n≥10 Trim `floor(n×0.1)` oben+unten, sonst normaler Median. Ersetzt `statistics.median(valid)` in `update_from_decoded`.

**Sekundaer:** `DAMPING = 0.7 → 0.5` — schnellere Konvergenz.

**Bewusst weggelassen:** Asymmetrisches Totband (Ziel ins Positive verschieben) — Konvention-bruch, Symptom-Fix.

## Konkrete Effekt-Rechnung Mike's 20 Werte

- Sortiert, trim=2 → entferne `-1.2, -0.7` (untere 2) + `+0.3, 0.0` (obere 2)
- Übrig: 16 Werte, Mitte bei Position 7/8 (0-indexed) → `-0.1` und `0.0`
- Trimmed Median = -0.05
- |−0.05| ≤ 0.05 → kein Update (im Totband)
- Korrektur bleibt 0.2705 ✓ (vs. ohne Trim wuerde -0.1 ein Update -0.07 ausloesen → 0.20)

## Dein Auftrag (Kritik des V3-Plans)

1. **Statistik:** Ist Trimmed-Median bei trim=10% das richtige Werkzeug? Alternative: Huber-Loss, Hampel-Filter, MAD-basiertes Outlier-Cutoff? **Bei Hobby-FT8 mit 5-30 Stationen pro Slot.**
2. **Damping-Aenderung 0.7→0.5:** Schwingungsrisiko? Konvergenz-Rate analytisch? Bei Hobby-Tool unnoetiger 2. Knopf? KISS-Bewertung.
3. **Symmetrie-Annahme:** Stimmt Mike's Annahme ueberhaupt? Soll Median bei 0 liegen oder bei +DT_BUFFER_OFFSET (FT8=2.0s)? **Verifiziere die DT-Konvention.**
4. **Edge-Cases:** Was bei n=10 genau (trim=1 Wert pro Seite — minimaler Effekt)? Was bei FT2 mit n=1-3 (MIN_STATIONS dort = 1)?
5. **Wurzel:** Ist Trimmed-Median wirklich die Wurzel oder Symptom-Fix? **Koennte die Wurzel woanders liegen?** (Decoder-DT-Berechnung? FlexRadio-Audio-Latenz nicht-konstant? Atmospheric-Skew bei Sonnenauf-/untergang?)
6. **Tests:** Sind die 8 Tests (T1-T8) ausreichend? Was fehlt?
7. **Field-Test:** Reicht „Mike schickt Screenshots ab und zu" oder brauchen wir Log-Output?
8. **Konventions-Risiko:** WSJT-X / JTDX und andere FT8-Tools — wie korrigieren die DT? Bewährte Verfahren?

## Format der Antwort

Tabelle pro Finding:

| Schwere | Finding | Datei:Zeile | Empfehlung |

Schweregrade:
- **KRITISCH** — Plan muss geaendert werden, sonst Bug/Regression
- **SOLLTE-FIX** — Plan-Verbesserung empfohlen, kein Blocker
- **KOENNTE** — Optional, Nice-to-have
- **HINWEIS** — Information, keine Aktion

Begruende JEDES Finding kurz (1-2 Saetze). Bei Statistik-Fragen mit Zahlen rechnen.

Am Ende: **Gesamtbewertung 1-10** und **„Code-Schreiben freigegeben mit Aenderungen X/Y/Z"** ODER **„V3 muss erst Y machen"**.

## Beispiel-Ton

> KRITISCH — Trim-Anteil 10% bei n=10 hat keinen statistischen Effekt. floor(10×0.1)=1 → entferne 1 oben+1 unten → arbeitet auf n=8. Sortierter Mittel-Wert ist faktisch gleich wie ohne Trim weil die Outliers in der unteren Haelfte liegen (Wert -1.2 ist nicht 2x weiter weg vom Median als -0.4). Empfehlung: trim_frac=0.2 bei n>=10 oder MAD-Cutoff.

Sei brutal-ehrlich. Mike hat 10 Jahre Funker-Erfahrung — Annahmen muessen passen.
