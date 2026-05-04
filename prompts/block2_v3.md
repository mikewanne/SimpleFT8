# Block 2 — Kalibrier-Pipeline-Optimierung (V3 — Final)

## Was V3 anders/besser macht als V2

R1-Review (deepseek-reasoner, 2026-05-04) hat 4 kritische Findings geliefert:

1. **Cache-Reuse-Schutz (R1.4):** Adaptiv-Stop-Ratios duerfen NICHT in
   PresetStore.save_ratio gehen. Nur volle 6-Zyklen-Messungen persistieren.
   → V3: Flag `_was_early_stopped` in DiversityController, mw_cycle.py
   pruef vor `save_ratio()`.

2. **Monitoring-Log:** R1 empfiehlt delta_snr/delta_stations/rel_diff im
   Print-Log mit Timestamp damit spaeter Schwellen-Tuning moeglich. → V3:
   Logging mit ISO-Timestamp.

3. **FT4/FT2-Doku:** R1 will explizite Code-Kommentar warum nur FT8 von #8
   profitiert. → V3: Inline-Docstring im record_measurement.

4. **Cancel-Flag in DiversityController:** R1 sagt entweder einbauen oder
   dokumentieren. KISS sagt: nicht einbauen — der mw_cycle/mw_radio-Pfad
   ruft record_measurement bei Cancel sowieso nicht mehr auf (Phase wird
   ueber `set_phase()` reset). → V3: Inline-Kommentar im record_measurement
   dass Cancel-Schutz extern ist.

R1's „Go fuer Umsetzung" steht.

---

## Kontext (unveraendert aus V2)

SimpleFT8 v0.90 → v0.91. Pipeline ~4:31 → ~3:20 Min Ziel.

Phase 2 (`dx_tune_dialog.py`): 12 Zyklen × 15 s = 3:00 Min →  
8 Zyklen × 15 s = 2:00 Min (#6) +  
optional Stop nach 4 Zyklen = 1:00 Min (#7).

Phase 3 (`core/diversity.py`): 6 Zyklen × 15 s = 1:30 Min →  
optional Stop nach 4 Zyklen = 1:00 Min (#8).

---

## 3 Optimierungen (final)

| # | Was | Wo | Aktuell | Neu | Ersparnis |
|---|---|---|---|---|---|
| 6 | ROUNDS=3→2 | `ui/dx_tune_dialog.py:23` | 3 Runden = 12 Zyklen | 2 Runden = 8 Zyklen | **-60 s** |
| 7 | Adaptiv-Stop Phase 2 | `ui/dx_tune_dialog.py:feed_cycle` | immer 8 Zyklen | Stop nach 4 wenn Δ_SNR≥4dB ODER Δ_STAT≥50% | **-30 bis -60 s** |
| 8 | Adaptiv-Stop Phase 3 | `core/diversity.py:record_measurement` | immer 6 Zyklen | Stop nach 4 wenn rel_diff≥15% | **-30 s** |

**Erwartete Pipeline:**
- Best-Case: ~2:30 Min (-63 %)
- Typisch: ~3:20 Min (-52 %)
- Worst-Case: ~4:30 Min (-33 %)

---

## Code-Referenzen (verifiziert 04.05.2026)

```
ui/dx_tune_dialog.py
  Z. 22:  GAIN_VALUES = [10, 20]
  Z. 23:  ROUNDS = 3                                    # ← #6
  Z. 26:  def _build_interleaved_schedule() -> list:
  Z. 211: def feed_cycle(self, messages: list):        # ← #7 hier
  Z. 240: def _detect_overload(messages) -> bool
  Z. 257: def _top5_avg(self, key) -> float | None
  Z. 271: def _station_count(self, key) -> int
  Z. 276: def _finish(self):                            # ← bei Stop direkt
  
core/diversity.py
  Z. 26:  MEASURE_CYCLES = 6                            # mode-override per mw_radio.py:798
  Z. 28:  THRESHOLD = 0.08
  Z. 86:  def choose(self):
  Z. 360: def record_measurement(...):                  # ← #8 hier
  Z. 384:   if self._measure_step >= self.MEASURE_CYCLES: self._evaluate()
  Z. 421: def _evaluate(self):
  
ui/mw_radio.py
  Z. 798: self._diversity_ctrl.MEASURE_CYCLES = 6 * _MULT.get(mode, 1)
  
ui/mw_cycle.py
  ~Z. 220: self._diversity_ctrl.save_ratio(...)         # ← Cache-Save-Punkt fuer R1.4
```

---

## Akzeptanzkriterien (final)

### AC1 — #6 ROUNDS=3 → 2 (UNIT-TESTBAR)

- `ui/dx_tune_dialog.py:23` `ROUNDS = 2`
- 5 Hint-Texte synchron updaten:
  - Z. 6 Docstring: „12 Zyklen interleaved" → „8 Zyklen interleaved"
  - Z. 23 Inline-Kommentar: „3 Runden × 4 Kombos = 12 Zyklen × 15s = 3 Min" → „2 Runden × 4 Kombos = 8 Zyklen × 15s = 2 Min"
  - Z. 92 UI-Hint: „12 Zyklen interleaved" → „8 Zyklen interleaved"
  - Z. 93 UI-Hint: „ca. 3 Minuten" → „ca. 2 Minuten"
  - Z. 201 step_label: `"Runde {round_num}/3"` → `"Runde {round_num}/2"`
- Verifikation: `len(_build_interleaved_schedule()) == 8`
- Pipeline Phase 2: 3:00 → 2:00 Min (FELD-TEST AC)

### AC2 — #7 Adaptiv-Stop Phase 2 (UNIT + FIELD-TESTBAR)

**Trigger-Ort:** `feed_cycle()` nach `self._step += 1`, **vor** `self._start_step()`.

**Pre-Conditions (ALLE erfuellen, sonst kein Stop):**

```python
def _check_phase2_early_stop(self) -> bool:
    """Adaptiv-Stop-Pruefung nach Runde 1 (Schritt 4).
    
    Greift NUR wenn Antennen-Verhaeltnis nach 1 Runde schon klar ist.
    Sonst regulaerer Pfad bis Schritt 8 (Runde 2). 
    Spart in optimalem Fall ~60 s Pipeline.
    """
    if self._step != 4:
        return False
    if self._cancelled:
        return False
    
    keys = [(ant, gain) for ant in ("ANT1", "ANT2") for gain in GAIN_VALUES]
    
    # Pre-Condition 1: Alle 4 Buckets non-empty + non-overload
    for k in keys:
        if not self._phase_data.get(k):
            return False
        if self._has_overload(k):
            return False
    
    # Pre-Condition 2: Min 5 Stationen pro Bucket (= MIN_MEASURE_STATIONS)
    for k in keys:
        if self._station_count(k) < 5:
            return False
    
    # Best Gain pro Antenne (gleiche Logik wie _finish)
    use_snr = (self.scoring_mode == "snr")
    def best_for(ant):
        best_g, best_s = GAIN_VALUES[0], None
        for gain in GAIN_VALUES:
            score = self._top5_avg((ant, gain)) if use_snr else self._station_count((ant, gain))
            if best_s is None or (score is not None and score > best_s):
                best_s, best_g = score, gain
        return best_g
    
    ant1_g, ant2_g = best_for("ANT1"), best_for("ANT2")
    a1_snr = self._top5_avg(("ANT1", ant1_g))
    a2_snr = self._top5_avg(("ANT2", ant2_g))
    a1_n = self._station_count(("ANT1", ant1_g))
    a2_n = self._station_count(("ANT2", ant2_g))
    
    delta_snr = abs((a1_snr or -30) - (a2_snr or -30))
    peak_n = max(a1_n, a2_n)
    delta_pct = abs(a1_n - a2_n) / peak_n if peak_n > 0 else 0.0
    
    stop = (delta_snr >= 4.0) or (delta_pct >= 0.50)
    
    # R1-Empfehlung: Monitoring-Log fuer Schwellen-Tuning
    import time
    ts = time.strftime("%H:%M:%S")
    if stop:
        print(f"[{ts}] [DX-Tune] Adaptiv-Stop nach Runde 1 — "
              f"Δ_SNR={delta_snr:.1f}dB Δ_STAT={delta_pct:.0%} → Stop, ~60s gespart")
    else:
        print(f"[{ts}] [DX-Tune] Adaptiv-Stop-Check nach Runde 1 — "
              f"Δ_SNR={delta_snr:.1f}dB Δ_STAT={delta_pct:.0%} → weiter")
    
    return stop
```

**Integration in `feed_cycle()`:**
```python
self._step += 1
if self._check_phase2_early_stop():
    self._finish()
    return
self._start_step()
```

**Schwellen-Werte (R1 bestaetigt):**
- 4 dB SNR (= 2× typische Slot-Streuung)
- 50 % Stationen
- Konservativ — lieber kein Stop als falscher Stop

### AC3 — #8 Adaptiv-Stop Phase 3 (UNIT + FIELD-TESTBAR)

**Trigger-Ort:** `record_measurement()` nach `_measure_step += 1`,
**vor** `if self._measure_step >= self.MEASURE_CYCLES`.

**Klassen-Konstanten + Properties:**

```python
class DiversityController:
    # ... bestehende Konstanten ...
    EARLY_STOP_FRACTION = 2 / 3          # nach 2/3 von MEASURE_CYCLES pruefen
    EARLY_STOP_THRESHOLD = 0.15          # 15% rel. Differenz, ~2× THRESHOLD=8%
    
    @property
    def _early_stop_at(self) -> int:
        """Step ab dem Frueh-Stop geprueft wird (2/3 von MEASURE_CYCLES).
        FT8: 4, FT4: 8, FT2: 16. NUR bei FT8 sinnvoll wirksam wegen
        Pattern-Periode 6 (siehe FT4/FT2-Hinweis in record_measurement).
        """
        return int(self.MEASURE_CYCLES * self.EARLY_STOP_FRACTION)
```

**Implementation:**

```python
def record_measurement(self, ant: str, score: float,
                       station_count: int = 0, avg_snr: float = -30.0,
                       dx_weak_count: int = 0):
    """... bestehende Doku ...
    
    Adaptiv-Stop (v0.91): Nach 2/3 der Mess-Phase pruefen ob rel_diff
    bereits klar (>=15%). Spart ~30s bei eindeutigen Verhaeltnissen.
    
    Cancel-Schutz: record_measurement wird vom mw_cycle/mw_radio-Pfad
    bei Cancel/Phase-Wechsel nicht mehr aufgerufen (Phase=operate gesetzt).
    Daher kein internes _cancelled-Flag noetig.
    
    FT4/FT2-Hinweis: Mess-Pattern hat Periode 6. Bei FT4 (MEASURE_CYCLES=12,
    early_stop_at=8) ergibt sich 5:3 Verteilung statt balanciert — Pre-
    Condition len(m1)==len(m2) verhindert Stop. Effektiv profitiert nur
    FT8 von #8. Akzeptabel da Hobby-Use 99% FT8.
    """
    if self._phase != "measure":
        return
    
    # Score speichern (unveraendert)
    if self._scoring_mode == "dx":
        self._measurements[ant].append(float(dx_weak_count))
    else:
        self._measurements[ant].append(float(station_count))
    self._measure_step += 1
    
    # Adaptiv-Stop Phase 3 (#8)
    if (self._measure_step == self._early_stop_at
            and len(self._measurements["A1"]) == len(self._measurements["A2"])
            and len(self._measurements["A1"]) >= 2):
        if self._check_phase3_early_stop():
            return  # _evaluate wurde in _check aufgerufen
    
    # Regulaerer Pfad
    if self._measure_step >= self.MEASURE_CYCLES:
        self._evaluate()


def _check_phase3_early_stop(self) -> bool:
    """Pruefen ob rel-Differenz >=15% nach 2/3 der Mess-Phase.
    
    Cache-Schutz (R1.4): Setzt _was_early_stopped=True. mw_cycle.py darf
    save_ratio() bei diesem Flag NICHT aufrufen — Adaptiv-Stop-Ratios
    sollen nicht persistiert werden weil sie auf weniger Messdaten
    basieren.
    """
    m1 = self._measurements["A1"]
    m2 = self._measurements["A2"]
    s1 = statistics.median(m1)
    s2 = statistics.median(m2)
    peak = max(s1, s2)
    if peak <= 1.0:
        return False
    
    rel_diff = abs(s1 - s2) / peak
    
    import time
    ts = time.strftime("%H:%M:%S")
    
    if rel_diff < self.EARLY_STOP_THRESHOLD:
        print(f"[{ts}] [Diversity] Adaptiv-Stop-Check nach {self._measure_step} Zyklen — "
              f"rel_diff={rel_diff:.1%} < {self.EARLY_STOP_THRESHOLD:.0%} → weiter")
        return False
    
    # Stop! _evaluate triggern + Flag setzen
    print(f"[{ts}] [Diversity] Adaptiv-Stop nach {self._measure_step} Zyklen — "
          f"rel_diff={rel_diff:.1%} >= {self.EARLY_STOP_THRESHOLD:.0%}, ~30s gespart, NICHT gecached")
    self._was_early_stopped = True
    self._evaluate()
    return True
```

**Reset-Logik:** `_was_early_stopped = False` in `reset()` und `start_measure()`.

**Cache-Schutz in mw_cycle.py (R1.4):**

```python
# Bei _evaluate() wurde _phase auf "operate" gesetzt → save_ratio Trigger
# Pruefen vor save_ratio:
if not self._diversity_ctrl._was_early_stopped:
    preset_store.save_ratio(band, ft_mode, ratio, dominant)
else:
    print(f"[mw_cycle] Adaptiv-Stop-Ratio NICHT gecached (rel_diff klar genug, "
          f"aber weniger Messdaten als regulaerer Pfad)")
```

---

## Test-Strategie

### NEU: `tests/test_dx_tune_adaptive_stop.py` (~6 Tests)

```python
def test_phase2_stop_on_clear_snr_diff()
    # 4 Buckets gefuettert, ANT1 deutlich besser → Stop
    
def test_phase2_stop_on_clear_station_diff()
    # ANT1=20 St., ANT2=8 St. → Δ_pct=60% → Stop
    
def test_phase2_no_stop_on_fair_metrics()
    # Δ klein → kein Stop, regulaer 8 Schritte
    
def test_phase2_no_stop_on_overload()
    # 1 Bucket Overload → kein Stop trotz Δ klar
    
def test_phase2_no_stop_on_low_station_count()
    # Alle Buckets nur 3 Stationen → kein Stop
    
def test_phase2_stop_calls_finish()
    # Nach Stop: _finished=True, _results befuellt
```

### ERWEITERUNG: `tests/test_patterns.py` (~5 Tests nach v0.90-Tests)

```python
def test_phase3_early_stop_on_a1_dominant()
    # m1=[20,18], m2=[5,4] → rel=15/20=0.75 → Stop, ratio=70:30, _was_early_stopped=True
    
def test_phase3_early_stop_on_a2_dominant()
    # m1=[5,4], m2=[20,18] → ratio=30:70
    
def test_phase3_no_early_stop_on_fair()
    # m1=[10,11], m2=[10,9] → rel<15% → kein Stop
    
def test_phase3_no_early_stop_on_unbalanced_counts_ft4()
    # MEASURE_CYCLES=12, nach 8 Schritten: len(m1)!=len(m2) → kein Stop
    # monkeypatch: dc.MEASURE_CYCLES = 12
    
def test_phase3_was_early_stopped_flag_resets_on_band_change()
    # Stop → _was_early_stopped=True → on_band_change → False
```

### Tests-Anzahl
v0.90: 664 → 664 + 6 + 5 = **675 gruene Tests** (Ziel).

---

## Reihenfolge atomare Commits (R1 bestaetigt)

1. **C1** — `ROUNDS=3→2` (5 Hint-Text-Updates) — sofort messbar, kein Test
2. **C2** — Tests `test_dx_tune_adaptive_stop.py` (6 Tests) — Test-First
3. **C3** — `_check_phase2_early_stop()` Implementation
4. **C4** — Tests `test_patterns.py` Erweiterung (5 Tests) — Test-First
5. **C5** — `_check_phase3_early_stop()` + Cache-Schutz mw_cycle.py
6. **C6** — APP_VERSION 0.91 + 4-Datei-Update + Doku-Sync (CLAUDE.md×2 + HANDOFF.md×2 + HISTORY.md + Memory)

---

## Pre-Flight Checks vor C1

```bash
cd "/Users/mikehammerer/Documents/KI N8N Projekte/FT8/SimpleFT8"
./venv/bin/python3 -m pytest tests/ -q | tail -5
# erwartet: 664 passed (v0.90 Stand)
git status
# erwartet: clean (oder nur prompts/ neu)
```

---

## Was V3 explizit NICHT macht

- DiversityController._cancelled-Flag (R1: dokumentieren statt implementieren)
- Settings-konfigurierbare Schwellen (overengineering)
- Phase-2-Stop nach Schritt 2 (zu wenig Daten)
- E2E-Test fuer Phase 2 + Phase 3 Zusammenspiel (R1: nicht zwingend, KISS)
- Grenzwert-Tests bei 3.9/4.0 dB (R1: aufwaendig, durch >=-Logik abgedeckt)

---

## Status

- V1: ✅ entworfen
- V2: ✅ Self-Review (6 Findings)
- R1: ✅ Review komplett (4 kritische + 4 minor Findings, alle adressiert)
- V3: ✅ Final
- **Plan-Mode:** als naechster Schritt
- **Mike-Freigabe:** autonom (Mike hat „autonom ohne weitere Interaktion" autorisiert in vorheriger Session)

---

## Implementierungsplan (final, atomar, freigabe-fertig)

### C1 — `ROUNDS=3 → 2`
**Datei:** `ui/dx_tune_dialog.py`  
**Aenderungen:** 6 Stellen (Z.6 Docstring, Z.23 Konstante+Kommentar, Z.92 Hint, Z.93 Hint, Z.201 step_label, ROUNDS-Wert)  
**Tests:** Bestehende Tests laufen lassen → 664 gruen.

### C2 — Tests `test_dx_tune_adaptive_stop.py` NEU
**Datei:** `tests/test_dx_tune_adaptive_stop.py` (NEU)  
**6 Tests** wie oben. Erwartung: 5/6 fail (Code fehlt noch), 1/6 pass (Mocking only).

### C3 — `_check_phase2_early_stop()`
**Datei:** `ui/dx_tune_dialog.py`  
**Aenderung:** Neue Methode + Integration in `feed_cycle()` (3 Zeilen)  
**Tests:** Alle 6 + bestehende → 670 gruen.

### C4 — Tests `test_patterns.py` (Erweiterung)
**Datei:** `tests/test_patterns.py`  
**5 Tests** nach den v0.90-Tests. Erwartung: 4/5 fail.

### C5 — `_check_phase3_early_stop()` + Cache-Schutz
**Datei:** `core/diversity.py`  
**Aenderungen:**
- 2 Klassen-Konstanten (`EARLY_STOP_FRACTION`, `EARLY_STOP_THRESHOLD`)
- 1 Property (`_early_stop_at`)
- 1 Instanz-Attribut (`_was_early_stopped` in `reset()` + `start_measure()`)
- 1 Methode (`_check_phase3_early_stop()`)
- record_measurement-Erweiterung (4 Zeilen)
- on_band_change resetiert _was_early_stopped (via reset())

**Datei:** `ui/mw_cycle.py`  
**Aenderung:** Vor `save_ratio` Aufruf `if not self._diversity_ctrl._was_early_stopped`-Check (3 Zeilen)

**Tests:** Alle 11 + bestehende → 675 gruen.

### C6 — APP_VERSION + Doku
**Dateien:**
- `main.py`: APP_VERSION „0.90" → „0.91"
- `HISTORY.md`: neuer Eintrag „2026-05-04 v0.91 — Block 2 Adaptiv-Stops"
- `HANDOFF.md` (×2): aktueller Stand v0.91 + Test-Count 675
- `CLAUDE.md` (×2): Aktueller Stand v0.91
- Memory `project_kalibrier_optimierung.md`: Block 2 ✅ ERLEDIGT

---

## Trigger-Phrases (Mike post-V3)

- „Plan jetzt umsetzen" → C1-C6 ausfuehren
- „V3 ist gut" → wie oben
- „andere Schwellen" → V3 anpassen, nochmal R1
- „doch erst Field-Test Block 1" → V3 parken
