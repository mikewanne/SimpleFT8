# Block 2 — Kalibrier-Pipeline-Optimierung (V2 — Self-Review)

## Was V2 anders/besser macht als V1

V1 hatte folgende Luecken die V2 schliesst:

1. **Schwellen-Rationale fehlte** → V2 begruendet jeden Wert (4 dB / 50 % / 15 %)
2. **Pre-Conditions Adaptiv-Stop unvollstaendig** → V2 listet 3 Sanity-Checks
3. **Modus-Skalierung als Konstante problematisch** → V2 nutzt Property
4. **Test-Strategie unklar** → V2 nennt konkrete Files + Test-Anzahl
5. **Risk: Phase-2-Stop bei klarer ANT-Hierarchie aber unklarer Gain-Wahl** → V2 fixt mit Pro-Antenne-Pruefung
6. **Field-Test vs Unit-Test nicht getrennt** → V2 markiert ACs explizit

---

## Kontext (unveraendert aus V1)

SimpleFT8 v0.90, 04.05.2026. Block 1 (v0.89) hat Pipeline 6:50 → ~4:31 Min
gebracht. Block 2 soll auf typisch ~3:20 Min runter (-52 % vs Pre-Block-1).

Pipeline aktuell:
- **Phase 2 — Gain-Messung** via `dx_tune_dialog.DXTuneDialog` —
  Schedule = 12 Zyklen × 15 s = 3:00 Min (3 Runden × 2 Gain × 2 ANT)
- **Phase 3 — Diversity-Einmessung** via `core/diversity.py` Mess-Phase —
  6 Zyklen × 15 s = 1:30 Min (Pattern A1A1A2A2A1A2 fair 3:3 seit v0.90)

## 3 Optimierungen

| # | Was | Wo | Aktuell | Neu | Ersparnis |
|---|---|---|---|---|---|
| 6 | ROUNDS=3 → 2 | `ui/dx_tune_dialog.py:23` | 3 Runden = 3:00 Min | 2 Runden = 2:00 Min | **-60 s** |
| 7 | Adaptiv-Stop Phase 2 | `ui/dx_tune_dialog.py:feed_cycle` | nach #6: immer 2 Runden | Stop nach Runde 1 (4 Schritte) bei klarer Differenz | **-30 bis -60 s** |
| 8 | Adaptiv-Stop Phase 3 | `core/diversity.py:record_measurement` | immer 6 Zyklen | Stop nach 4 Zyklen bei klarer Differenz | **-30 s** |

---

## Code-Referenzen (verifiziert 04.05.2026)

### dx_tune_dialog.py
```
Z. 22:  GAIN_VALUES = [10, 20]
Z. 23:  ROUNDS = 3                                 # ← #6
Z. 26:  def _build_interleaved_schedule() -> list:
        # 4 Schritte/Runde: ANT1@10, ANT2@10, ANT1@20, ANT2@20
        # Gerade Runden: ANT1 zuerst | Ungerade Runden: ANT2 zuerst
Z. 211: def feed_cycle(self, messages: list):     # ← #7 hier einklinken
        # Nach _step += 1: Adaptiv-Stop-Check
Z. 240: def _detect_overload(messages) -> bool
Z. 257: def _top5_avg(self, key) -> float | None
Z. 271: def _station_count(self, key) -> int
Z. 276: def _finish(self):                         # ← bei Stop direkt aufrufen
```

### core/diversity.py
```
Z. 26:  MEASURE_CYCLES = 6                         # ← Wert wird per Mode ueberschrieben
Z. 28:  THRESHOLD = 0.08
Z. 86:  def choose(self):
Z. 88:    return ("A1","A1","A2","A2","A1","A2")[self._measure_step % 6]
Z. 360: def record_measurement(self, ant, ...):    # ← #8 hier einklinken
Z. 384:   if self._measure_step >= self.MEASURE_CYCLES: self._evaluate()
Z. 421: def _evaluate(self):
Z. 428:   s1 = statistics.median(m1)
Z. 429:   s2 = statistics.median(m2)
Z. 432:   diff = abs(s1 - s2) / peak
```

### mw_radio.py — Modus-Override
```
Z. 798: self._diversity_ctrl.MEASURE_CYCLES = 6 * _MULT.get(mode, 1)
        # FT8: 6, FT4: 12, FT2: 24
        # ⚠ ADAPTIV-STOP MUSS DYNAMISCH SEIN, nicht hardcoded auf 4
```

---

## Akzeptanzkriterien

### AC1 — #6 ROUNDS=3 → 2 (UNIT-TESTBAR)

- `ui/dx_tune_dialog.py:23` `ROUNDS = 2`
- Hint-Text Anpassungen:
  - Z. 6 Docstring: „12 Zyklen interleaved" → „8 Zyklen interleaved"
  - Z. 23 Inline-Kommentar: „3 Runden × 4 Kombos = 12 Zyklen" → „2 Runden × 4 Kombos = 8 Zyklen"
  - Z. 92 UI-Hint: „12 Zyklen" → „8 Zyklen"
  - Z. 93 UI-Hint: „ca. 3 Minuten" → „ca. 2 Minuten"
  - Z. 201 step_label: „Runde X/3" → „Runde X/2"
- Verifikation: `len(_build_interleaved_schedule()) == 8`
- Pipeline Phase 2: 3:00 → 2:00 Min (FELD-TEST)

### AC2 — #7 Adaptiv-Stop Phase 2 (UNIT + FIELD-TESTBAR)

**Trigger-Ort:** `feed_cycle()` nach `self._step += 1` aber vor
`self._start_step()`. Trigger-Bedingung: `self._step == 4`
(genau Runde 1 abgeschlossen, alle 4 Buckets haben 1 Wert).

**Pre-Conditions (ALLE muessen erfuellt sein, sonst kein Stop):**

1. `self._step == 4` (genau Round-1-Ende, nicht spaeter)
2. Alle 4 Buckets `(ant, gain)` mit `(ant, gain) ∈ {(ANT1,10), (ANT2,10), (ANT1,20), (ANT2,20)}` haben min. 1 gueltigen SNR-Wert (`_phase_data[key]` non-empty UND non-None)
3. Kein Bucket hat Overload-Marker (`_has_overload(key) == False` fuer alle 4)
4. Mind. 5 Stationen pro Bucket (`_station_count(key) >= 5`) — **identisch
   zu MIN_MEASURE_STATIONS in Phase 3, KISS** — verhindert Mess-Streuung-
   Falsch-Stop bei sehr ruhigem Band

**Stop-Bedingung (mind. EINE der beiden erfuellt nach Best-Gain-Auswahl):**

```python
# Pro Antenne den BESTEN Gain (analog _finish())
ant1_best_gain = best_gain_for(ANT1)  # 10 oder 20
ant2_best_gain = best_gain_for(ANT2)
ant1_snr = _top5_avg((ANT1, ant1_best_gain))
ant2_snr = _top5_avg((ANT2, ant2_best_gain))
ant1_n = _station_count((ANT1, ant1_best_gain))
ant2_n = _station_count((ANT2, ant2_best_gain))

delta_snr_db = abs(ant1_snr - ant2_snr)
peak_n = max(ant1_n, ant2_n)
delta_stations_pct = abs(ant1_n - ant2_n) / peak_n if peak_n > 0 else 0.0

stop = (delta_snr_db >= 4.0) or (delta_stations_pct >= 0.50)
```

**Schwellen-Rationale (V2 begruendet):**
- **4 dB SNR**: Typische Antennen-Streuung pro Slot ~1-2 dB. 4 dB =
  2× Streuung = klares Signal. WSJT-X-Erfahrung: <3 dB als Mess-
  Rauschen, ≥4 dB als verlaesslich klassifiziert.
- **50 % Stationen**: 1 Slot Streuung kann ±20 % sein (15 → 18 oder 12).
  50 % = klar darueber. Beispiel: ANT1=20 St., ANT2=10 St. → 50 %.
- **Konservativ statt aggressiv**: Lieber kein Stop als falscher Stop —
  v0.90-Mess-Pattern-Bug hat gezeigt was kleine Bias-Schwellen anrichten.

**Bei Stop:**
- Print-Log: `[DX-Tune] Adaptiv-Stop nach Runde 1 — Δ_SNR=X.X dB, Δ_STAT=Y %, Restzeit gespart: ~60 s`
- Direktaufruf `self._finish()` (waehlt Gain pro ANT aus den vorhandenen Daten — gleiche Logik wie regulaerer Pfad, robust auch mit 1 Wert pro Bucket dank max-Score)

**Edge-Cases:**
- Cancel-Button waehrend Adaptiv-Stop-Check → kein Stop-Trigger (`if self._cancelled: return`)
- 2/4 Buckets haben nur 4 Stationen (knapp unter Schwelle) → kein Stop, weiter
- Overload in 1 Bucket → kein Stop, weiter (regulaerer Pfad ignoriert overload-Bucket eh in `_finish()`)

### AC3 — #8 Adaptiv-Stop Phase 3 (UNIT + FIELD-TESTBAR)

**Trigger-Ort:** `record_measurement()` nach `_measure_step += 1`,
**vor** dem Check `if self._measure_step >= self.MEASURE_CYCLES`.

**Pre-Conditions:**

1. `self._measure_step == self._early_stop_at` (proportional skaliert,
   siehe unten)
2. `len(m1) >= self._early_stop_min_per_ant` UND `len(m2) >= self._early_stop_min_per_ant`
3. `peak > 1.0` (gleiche Bedingung wie regulaerer `_evaluate()`)

**Modus-Skalierung als Property:**

```python
# Klassen-Konstante:
EARLY_STOP_FRACTION = 2 / 3   # nach 2/3 der Mess-Phase

# Property:
@property
def _early_stop_at(self) -> int:
    """Step-Index ab dem Frueh-Stop geprueft wird (2/3 von MEASURE_CYCLES)."""
    return int(self.MEASURE_CYCLES * self.EARLY_STOP_FRACTION)

@property
def _early_stop_min_per_ant(self) -> int:
    """Min Werte pro Antenne fuer robusten Median (>=2 fuer 2-Punkt-Median)."""
    return max(2, self._early_stop_at // 3)  # FT8: 1, mind. 2; FT4: 2; FT2: 5
```

**Skalierung pro Modus (Verifikation):**
| Mode | MEASURE_CYCLES | _early_stop_at | _early_stop_min_per_ant | Pattern bis Stop |
|---|---|---|---|---|
| FT8 | 6 | 4 | 2 | A1,A1,A2,A2 (2:2) |
| FT4 | 12 | 8 | 2 | A1,A1,A2,A2,A1,A2,A1,A1 (5:3) — abweichend! |
| FT2 | 24 | 16 | 5 | aehnlich (mehr Pattern-Wiederholungen) |

**⚠ FT4-Problem (V2 entdeckt):** Mess-Pattern ist `("A1","A1","A2","A2","A1","A2")` mit Modulo 6. Bei FT4 mit MEASURE_CYCLES=12 wiederholt sich das 2× → 6 A1 + 6 A2 sind erst nach 12 Zyklen. Bei Stop nach 8: 5×A1 + 3×A2 (nicht balanced). 

→ **Loesung V2:** Stop nur wenn `len(m1) == len(m2)` (gleichviel Werte pro Antenne). Bei FT8 nach 4 Zyklen: 2:2 OK. Bei FT4 nach 8: 5:3 → kein Stop, weiter bis nach 12 (regulaer). Bei FT2 nach 16: ungleich → kein Stop. **Effektiv profitiert nur FT8 von #8** — das ist akzeptabel (FT8 = 99 % Use-Case).

**Stop-Bedingung:**
```python
EARLY_STOP_THRESHOLD = 0.15  # 15 % rel. Differenz, ~2× THRESHOLD=8 %

s1 = statistics.median(m1)
s2 = statistics.median(m2)
peak = max(s1, s2)
if peak > 1.0:
    rel_diff = abs(s1 - s2) / peak
    if rel_diff >= self.EARLY_STOP_THRESHOLD:
        # → _evaluate() jetzt aufrufen
```

**Schwellen-Rationale:**
- **15 % rel. Differenz** (= ~2× THRESHOLD=8 %): Bei 8 % wird sowieso
  als 70:30 evaluated. Bei 15 % ist die Differenz so klar, dass auch
  weitere Messungen das Ergebnis nicht mehr aendern duerften.
- **Konservativ statt aggressiv**: Falsch-Stop wuerde 30 s sparen aber
  potenziell falsches ratio liefern. Lieber 30 s mehr und sicheres
  Ergebnis.

**Bei Stop:**
- Print-Log: `[Diversity] Adaptiv-Stop nach 4 Zyklen — rel_diff=X.X %, ratio=Y, Restzeit gespart: ~30 s`
- Direktaufruf `self._evaluate()` (setzt _phase=operate, _operate_cycles=0)

---

## Test-Strategie

### NEU: `tests/test_dx_tune_adaptive_stop.py` (~6 Tests)

```python
def test_phase2_stop_on_clear_snr_diff()
    # ANT1@20 = 0 dB im Top5, ANT2@20 = -10 dB → Δ=10 dB → Stop
    
def test_phase2_stop_on_clear_station_diff()
    # ANT1=20 Stationen, ANT2=8 Stationen → Δ_pct=60 % → Stop
    
def test_phase2_no_stop_on_fair_metrics()
    # ANT1@20=−5 dB/15 St., ANT2@20=−6 dB/14 St. → Δ klein → kein Stop
    
def test_phase2_no_stop_on_overload()
    # 1 Bucket mit Overload trotz Δ_SNR=10 dB → kein Stop
    
def test_phase2_no_stop_on_low_station_count()
    # Alle Buckets nur 3 Stationen → kein Stop (< MIN_MEASURE_STATIONS)
    
def test_phase2_stop_calls_finish()
    # Verifikation: nach Stop ist _finished=True und _results gesetzt
```

### ERWEITERUNG: `tests/test_patterns.py` (~5 Tests)

```python
def test_phase3_early_stop_on_a1_dominant()
    # Nach 4 Zyklen: m1=[20, 18], m2=[5, 4] → rel=15/20=0.75 → Stop, ratio=70:30
    
def test_phase3_early_stop_on_a2_dominant()
    # Nach 4 Zyklen: m1=[5, 4], m2=[20, 18] → ratio=30:70

def test_phase3_no_early_stop_on_fair()
    # Nach 4 Zyklen: m1=[10, 11], m2=[10, 9] → rel<15 % → kein Stop

def test_phase3_no_early_stop_on_unbalanced_counts_ft4()
    # FT4: MEASURE_CYCLES=12, nach 8 Schritten: m1=5 m2=3 → kein Stop (ungleich)
    
def test_phase3_full_cycles_when_no_early_stop()
    # rel_diff knapp < 15 % → kein Frueh-Stop, regulaerer Stop bei 6
```

### ANPASSUNG: bestehende Tests
- `test_calibration_dialog_smoke.py` — keine Aenderung erwartet
- `test_diversity_bandwechsel.py` — keine Aenderung erwartet (`reset()` unveraendert)

### Erwartete Tests-Anzahl
v0.90: 664 → +6 (#7) +5 (#8) = **675 Tests**.

---

## Reihenfolge / Atomare Commits

1. **C1 — #6 ROUNDS=3→2** (kleinste Aenderung, sofort messbar, kein Test-Update)
2. **C2 — Tests `test_dx_tune_adaptive_stop.py` (NEU)** — Test-First fuer #7
3. **C3 — #7 Implementation** (Adaptiv-Stop Phase 2 in `feed_cycle`)
4. **C4 — Tests `test_patterns.py` (Erweiterung)** — Test-First fuer #8
5. **C5 — #8 Implementation** (`record_measurement` + Properties)
6. **C6 — APP_VERSION 0.91 + 4-Datei-Update** (HISTORY, HANDOFF×2, CLAUDE×2, Memory)

---

## Risiken (offen fuer R1-Review)

### R1.1 — Schwellen-Tuning ohne Felddaten
4 dB / 50 % / 15 % sind Schaetzungen. Echtes Feldtest-Data fehlt fuer
Adaptiv-Stop-Genauigkeit. Lieber konservativ — aber wenn die Schwellen
zu hoch gesetzt sind, triggert Adaptiv-Stop nie und Block 2 bringt nur
#6 (-60 s).

**Frage R1:** Ist das Schwellen-Set konservativ genug? Gibt's R1-
Empfehlung aus Funk-Praxis fuer „klare ANT-Differenz"-Schwelle?

### R1.2 — FT4/FT2-Adaptiv-Stop fast wirkungslos
V2 entdeckt: bei FT4/FT2 mit 12/24 MEASURE_CYCLES haengt das fair
3:3-Pattern erst spaeter und Stop-Pre-Condition `len(m1)==len(m2)` ist
seltener erfuellt. Effektiv profitiert nur FT8.

**Frage R1:** Akzeptabel oder muss FT4/FT2 separat gehandhabt werden?
(Hobby-Use ist 99 % FT8 → KISS sagt: akzeptabel.)

### R1.3 — Adaptiv-Stop Phase 2 + Phase 3 = Akkumulierte Frueh-Stops
Wenn beide triggern, ist Pipeline minimal ~1:30 Min (Tunen 3 s + 4 Phase2-
Zyklen + 4 Phase3-Zyklen + Latenzen). Bei zu fruehem Stop koennte das
ratio in Phase 3 falsch sein → Hobby-Funker bekommt schlechte Diversity.

**Frage R1:** Sollte Phase 3 strenger sein als Phase 2 (z.B. 20 %
statt 15 %), weil Phase 3 das Mess-Ergebnis mit am laengsten produktiv
genutzt wird (60 Operate-Zyklen)?

### R1.4 — Kopplung mit Cache-Reuse-TODO
`project_diversity_cache_reuse.md` plant fuer Bandwechsel Wiederverwendung
des Phase-3-Ratios aus PresetStore. Wenn Adaptiv-Stop in Phase 3 zu frueh
greift, landet ein „kuerzer gemessenes" Ratio im Cache. Nach 2 h Cache-Reuse
wird mit weniger Messdaten gearbeitet.

**Frage R1:** Vorschlag: PresetStore-Save NUR nach vollen 6 Zyklen (= regulaerer Pfad), nicht bei Adaptiv-Stop? Oder ist das overengineering?

### R1.5 — Test-Coverage Edge-Cases
- Was passiert wenn Mike waehrend Phase 2/3 Cancel klickt? V2 sagt:
  Cancel hat Vorrang. Test fehlt aber.
- Was wenn `_phase_data` empty bei Stop-Check? Bug-Potenzial.

---

## Was V2 explizit NICHT macht (entgegen V1-Anker-Bias)

- ROUNDS=2 als Konstante in Settings konfigurierbar — overengineering
- Adaptiv-Stop-Schwellen aus Settings lesen — overengineering
- Phase-2-Adaptiv-Stop nach Schritt 2 (=halbe Runde) — zu wenig Daten
- ML-basierte Schwellen-Schaetzung — definitiv overengineering

---

## Auftrag fuer R1

Du bist Senior-Reviewer (Funk-Praxis + Code). Pruefe V2 hart:

1. Schwellen-Werte 4 dB / 50 % / 15 % — vernuenftig fuer Adaptiv-Stop?
   Oder Zahlen-Lottery? Konkret: was wuerdest du fuer Phase 2 / Phase 3
   nehmen, mit Begruendung aus Funk-Praxis.

2. FT4/FT2-Edge-Case (R1.2) — V2 sagt akzeptabel, KISS. Stimmst du zu
   oder muss separater Pfad?

3. Pre-Conditions Adaptiv-Stop (1, 2, 3 für Phase 2 + 1, 2, 3 für Phase 3) —
   vollstaendig oder fehlt was?

4. Cache-Reuse-Kopplung (R1.4) — Adaptiv-Stop-Ratios in Cache sichern oder nicht?

5. Test-Strategie — 11 neue Tests, FT4/FT2-Skalierung als 1 Test mit
   monkeypatch von MEASURE_CYCLES. Reicht oder mehr?

6. KISS-Bewertung: Properties (`_early_stop_at`, `_early_stop_min_per_ant`)
   vs harte Konstanten. V2 nutzt Properties wegen Modus-Override. Akzeptabel?

7. Reihenfolge atomare Commits — sinnvoll oder anders?

**Antwort-Format:** Strukturiert nach diesen 7 Punkten, knapp, mit Begruendung. KEINE Code-Vorschlaege — wir wollen Reviewer-Meinung, nicht Implementation.

8. Sonstiges was V2 uebersieht — gerne ergaenzen.
