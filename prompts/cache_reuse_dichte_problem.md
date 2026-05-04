# Mess-Statistik bei dünner Decoder-Dichte (R1-Diskussion)

## Auftrag

Mike hat einen Punkt aufgegriffen den V1/V2/Vorgängerdiskussion **nicht
adressiert** hat. **NUR DISKUSSION** — keine Code-Vorschläge.

## Mike's Praxis-Beobachtung (entscheidend!)

20 m Band, typische Stationen-Anzahl pro Mess-Slot:
- **FT8:** ~34 Stationen pro Zyklus
- **FT4:** ~8 Stationen pro Zyklus
- **FT2:** 1-2 Stationen pro Zyklus

Hintergrund: FT4/FT2 sind weniger verbreitet als FT8. Auf 20 m hat FT8
durchgehend Aktivität, FT4 sporadisch, FT2 fast leer.

## Was Code aktuell macht

`core/diversity.py:374-385` (record_measurement):
```python
def record_measurement(self, ant, score, station_count, ...):
    if self._scoring_mode == "dx":
        self._measurements[ant].append(float(dx_weak_count))
    else:
        self._measurements[ant].append(float(station_count))
```

Pro Slot wird **ein Wert** gespeichert: die Stations-Anzahl (oder DX-Weak-
Count) in diesem Slot.

`core/diversity.py:421-429` (_evaluate):
```python
m1 = self._measurements["A1"]
m2 = self._measurements["A2"]
s1 = statistics.median(m1)  # Median über Slot-Werte
s2 = statistics.median(m2)
```

→ Median wird über Slot-Werte gebildet, nicht über einzelne Stations-
SNRs.

## `_MULT`-Skalierung für MEASURE_CYCLES

Aktuell in `mw_radio.py:824`:
```python
self._diversity_ctrl.MEASURE_CYCLES = 6 * _MULT.get(mode, 1)
# FT8: 6 Slots, FT4: 12, FT2: 24
```

→ Damit sind 3:3-Pattern entsprechend skaliert: A1 bekommt 3, 6, oder 12
Slots — A2 entsprechend.

### Median-Datenpunkte pro Antenne:

| Modus | MEASURE_CYCLES | Slots/Antenne | Slot-Werte (Stationen) | Median über |
|---|---|---|---|---|
| FT8 | 6 | 3 | je 0–34 | 3 Werte |
| FT4 | 12 | 6 | je 0–8 | 6 Werte |
| FT2 | 24 | 12 | je 0–2 | 12 Werte |

## Mike's konkrete Frage

Bei **FT2 mit 1-2 Stationen pro Slot** sind die Slot-Werte aus dem Set
`{0, 1, 2}`. Median über 12 solcher Werte ist `0`, `1`, oder `2`.

→ **Differenzierung zwischen A1 und A2 ist statistisch kaum möglich.**

Bei FT8 mit 0-34 Stationen pro Slot ist der Median über 3 Werte
deutlich aussagekräftiger (z.B. A1=24, A2=12 → klar 70:30).

**Mike's Beobachtung:** „24 Zyklen × 1.5 Stationen ist nicht besser als
6 Zyklen × 1.5 Stationen — der Engpass ist die Stations-Anzahl pro
Slot, nicht die Mess-Dauer."

## Konkretes Zahlenbeispiel (FT2 20m)

Annahme: 1.5 Stationen pro Slot durchschnittlich.

**Szenario A1 ist 70 % besser:**
- A1: ~1.8 Stationen pro Slot
- A2: ~1.2 Stationen pro Slot

Mit MEASURE_CYCLES = 24 (12 Slots/Antenne):
- A1-Slots: kommt zwischen `[1, 2, 1, 2, 2, 1, 1, 2, 2, 2, 1, 1]` (Mittelwert 1.5+x)
- A2-Slots: zwischen `[0, 1, 1, 1, 2, 0, 1, 1, 2, 1, 0, 1]` (Mittelwert 0.92)
- Median A1 = 1.5, Median A2 = 1.0
- rel_diff = (1.5 - 1.0) / 1.5 = 33 % → erkannt als 70:30 ✅

Mit MEASURE_CYCLES = 6 (3 Slots/Antenne):
- A1-Slots: `[2, 1, 2]` → Median = 2
- A2-Slots: `[1, 1, 2]` → Median = 1
- rel_diff = 50 % → erkannt als 70:30 ✅

→ Beide funktionieren bei diesem Beispiel.

**Aber:** mit Stations-Streuung kann bei 6 Slots leicht passieren:
- A1: `[1, 2, 1]` → Median = 1
- A2: `[1, 2, 0]` → Median = 1
- → 50:50 verpasst Differenzierung ✗

Bei 24 Slots ist das robuster — Mehr Datenpunkte glätten die Streuung.

## Aber: ist 24 Slots für FT2 trotzdem genug?

Bei FT2 = 1-2 Stationen pro Slot ist auch 24 Slots × 1.5 = 36 Datenpunkte
limitiert. Wenn die echte Differenz zwischen A1/A2 nur 0.3 Stationen
pro Slot ist, ist auch 36 Datenpunkte zu wenig.

## Was R1 bewerten soll

### Fragenbatterie

**1. Ist Median über Slot-Stations-Anzahl bei dünner Dichte überhaupt
ein gutes Score?**

Bei FT2 mit Slot-Werten ∈ `{0,1,2}` ist der Median ein Diskret-Wert,
keine Glättung. Wäre ein anderer Score besser?
- z.B. SUM statt MEDIAN (Robustheit verloren, aber mehr Auflösung)
- z.B. MEAN statt MEDIAN (sensitiver auf Ausreißer)
- z.B. SNR-basiert statt Stations-Anzahl (jede Station hat einen SNR-Wert,
  damit aussagekräftiger über kleinem Stations-Pool)

**2. Sollte SCORING-MODE für FT4/FT2 anders sein?**

`scoring_mode = "normal"` zählt Stationen — bei FT2 fast nutzlos.
`scoring_mode = "dx"` zählt Weak-Stationen (SNR<-10) — bei FT2 noch
sparsamer.

Vielleicht für FT4/FT2: zähle SNR-Summe statt Stations-Anzahl?

**3. _MULT für MEASURE_CYCLES — behalten oder weg?**

Mike's Argument: weniger Stationen pro Slot heißt mehr Slots helfen
nur begrenzt. KISS: alle Modi 6 Slots. Mike's Gegen-Argument: trotzdem
hilft die Robustheit mit mehr Datenpunkten.

**Drei Optionen:**
- **a)** `_MULT` ganz weg: alle 6 Slots — KISS, FT2/FT4 wackliger
- **b)** `_MULT` behalten: FT8=6, FT4=12, FT2=24 — wie aktuell
- **c)** `_MULT` umkehren: FT8=6, FT4=6, FT2=6 — dafür **adaptive Slot-
  Anzahl basierend auf Stations-Dichte** (z.B. „messe bis insgesamt 50
  Datenpunkte gesammelt")

**4. MIN_MEASURE_STATIONS für FT4/FT2?**

Aktuell `MIN_MEASURE_STATIONS = 5`. Wenn FT2 nur 1-2 Stationen pro Slot
hat, wird `can_measure()` oft `False` zurückgeben → Phase 3 startet nicht.

Wäre eine Modus-spezifische Schwelle sinnvoll?
- FT8: 5
- FT4: 3
- FT2: 1

**5. Pragmatik: was passiert wenn FT2 30 Min keine 5 Stationen hat?**

Aktuell: `can_measure()=False` → keine Messung gestartet → fällt zurück
auf 50:50 oder letztes valides Pattern. Mit Mike's 1-h-Auto-Refresh
wartet System eine Stunde, scheitert wieder, wartet wieder.

→ Soll FT2 ein **anderes Mess-System** bekommen oder einfach
„fallback auf 50:50 + warten"?

**6. Mike's Hobby-Use-Case:**

FT8 ist Mike's Hauptmodus. FT4/FT2 sind sehr selten genutzt. Lohnt es
sich überhaupt FT4/FT2-Optimierung zu betreiben?

**Pragmatische Variante:**
- FT8: voll optimiert (6 Slots, fair 3:3, Adaptiv-Stop, Cache-Reuse)
- FT4/FT2: einfaches Fallback (z.B. immer 50:50, keine Phase 3
  Mess-Phase)

Wäre das KISS oder feature-incomplete?

## Was R1 NICHT machen soll

- Code schreiben
- Pattern fair 3:3 ändern (v0.90 fix bleibt)
- Cache-Reuse-Logik selbst bewerten (das war R1's vorheriger Auftrag)
- UI-Vorschläge

## Format Antwort

Strukturiert nach 1–6. Pro Punkt:
1. Klar/unklar
2. Empfehlung mit Begründung aus Statistik + Funk-Praxis
3. Wenn relevant: KISS-Bewertung

Am Ende: **Klare Empfehlung** — was ändert sich für FT4/FT2 im Refactor-Plan?

## Ergänzung: konsistenter Wunsch

Mikes Refactor-Plan (vorher diskutiert):
- 1 h Auto-Refresh atmosphärisch korrekt
- Cache-Reuse pro Band+Modus
- Normal raus aus Cache
- OPERATE_CYCLES weg, Settings-Option weg

Diese Punkte sind R1-bestätigt. **Diese Diskussion bezieht sich NUR auf
MEASURE_CYCLES und Mess-Statistik bei dünner Dichte.**

Also: gilt R1's „behalte _MULT für MEASURE_CYCLES" weiter? Oder muss
das nochmal gedacht werden mit Mike's neuen Praxis-Zahlen (34 / 8 / 1-2)?
