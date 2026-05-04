# Block 2 — Kalibrier-Pipeline-Optimierung (V1)

## Kontext

SimpleFT8 v0.90, 04.05.2026. Block 1 (v0.89) hat Pipeline 6:50 → ~4:31 Min
gebracht. Block 2 soll auf typisch ~3:20 Min runter (-52 % Gesamt-Block-1+2).

Pipeline-Phasen aktuell:
- **Tunen** (TUNE-Button, ANT1, 3 s)
- **Phase 2 — Gain-Messung** via `dx_tune_dialog.DXTuneDialog` —
  Schedule = 12 Zyklen × 15 s = 3:00 Min (3 Runden × 2 Gain × 2 ANT)
- **Phase 3 — Diversity-Einmessung** via `core/diversity.py` Mess-Phase —
  6 Zyklen × 15 s = 1:30 Min (Pattern A1A1A2A2A1A2 fair 3:3 seit v0.90)
- **Operate** (60 Zyklen ≈ 15 Min, dann Re-Measure)

Phase 2 + 3 = ~4:30 Min Wartezeit fuer Mike vor jedem Bandwechsel /
neuem Modus / Cache-Miss.

## 3 Optimierungen (alle „mittel"-Risk)

| # | Was | Wo | Aktuell | Neu | Ersparnis |
|---|---|---|---|---|---|
| 6 | N=3 → N=2 pro Kombi | `ui/dx_tune_dialog.py:23` `ROUNDS = 3` | 3 Runden = 12 Zyklen = 3:00 Min | 2 Runden = 8 Zyklen = 2:00 Min | **-60 s** |
| 7 | Adaptiv-Stop Phase 2 nach Runde 1 | `ui/dx_tune_dialog.py` (neue Logik in `feed_cycle`) | immer 2 Runden (nach #6) | Stop nach Runde 1 (4 Schritte) wenn Δ > 4 dB SNR ODER > 50 % Stationen | **-30 bis -60 s** |
| 8 | Adaptiv-Stop Phase 3 nach 4 Zyklen | `core/diversity.py` `record_measurement` | immer 6 Zyklen | Stop nach 4 Zyklen wenn rel-Δ > 15 % (= ~2× THRESHOLD=8 %) | **-30 s** |

**Erwartete Pipeline:**
- Best-Case (alles greift): ~2:30 Min (-63 %)
- Typisch: ~3:20 Min (-52 %)
- Worst-Case (Diff zu klein → kein Adaptiv-Stop): ~4:30 Min (-33 %)

## Code-Referenzen (verifiziert 04.05.2026)

### dx_tune_dialog.py
```
Z. 22:  GAIN_VALUES = [10, 20]
Z. 23:  ROUNDS = 3                   # ← Optimierung #6
Z. 26:  def _build_interleaved_schedule() -> list:
        # Schedule: 4 Schritte/Runde = ANT1@10, ANT2@10, ANT1@20, ANT2@20
        # alternierend (Round 0: ANT1 first, Round 1: ANT2 first, ...)
Z. 211: def feed_cycle(self, messages: list):
        # Pro Mess-Zyklus aufgerufen, sammelt SNR-Werte in _phase_data[(ant,gain)]
        # _step += 1 → naechster Schritt
Z. 240: def _detect_overload(...): bool
Z. 257: def _top5_avg(self, key) -> float | None:
Z. 271: def _station_count(self, key) -> int:
Z. 276: def _finish(self):
        # Bestimmt besten Gain pro Antenne via score (use_snr ? top5_avg : station_count)
        # Setzt _results dict, speichert via PresetStore
```

### core/diversity.py
```
Z. 26:  MEASURE_CYCLES = 6
Z. 27:  OPERATE_CYCLES = 60
Z. 28:  THRESHOLD = 0.08
Z. 86:  def choose(self) -> str:
Z. 88:    return ("A1","A1","A2","A2","A1","A2")[self._measure_step % 6]
Z. 360: def record_measurement(self, ant, score, station_count, avg_snr, dx_weak_count):
Z. 384:   if self._measure_step >= self.MEASURE_CYCLES: self._evaluate()
                                                      # ← Optimierung #8 hier einklinken
Z. 421: def _evaluate(self):
Z. 428:   s1 = statistics.median(m1)  # benoetigt mind. 1 Wert
Z. 429:   s2 = statistics.median(m2)
Z. 432:   diff = abs(s1 - s2) / peak  # rel. Differenz
```

### mw_radio.py — Modus-abhaengige Override
```
Z. 798: self._diversity_ctrl.MEASURE_CYCLES = 6 * _MULT.get(mode, 1)
        # _MULT = {"FT8": 1, "FT4": 2, "FT2": 4} → FT8: 6, FT4: 12, FT2: 24
        # Adaptiv-Stop muss DIESEN Wert respektieren, nicht hardcoded 6
```

## Akzeptanzkriterien

### AC1 — #6 ROUNDS=3 → 2
- `ui/dx_tune_dialog.py:23` ROUNDS = 2
- Hint-Text Z. 6 Docstring + Z. 23 Inline-Kommentar + Z. 92 UI-Hint
  („12 Zyklen interleaved" → „8 Zyklen interleaved")
- Schedule = 8 Eintraege (`len(_build_interleaved_schedule())==8`)
- Progress-Format Z. 117 unveraendert (`%v / {len(self._schedule)}`)
- Bestehende Tests gruen (`tests/test_dx_tune*.py` falls existent)
- Pipeline Phase 2: 3:00 → 2:00 Min messbar

### AC2 — #7 Adaptiv-Stop Phase 2
- Nach Runde 1 (= Schritt 4 erreicht, also 4 Eintraege im _schedule
  abgearbeitet) im `feed_cycle`-Pfad pruefen:
  - Δ_SNR  = |top5_avg(ANT1, best_gain) − top5_avg(ANT2, best_gain)|
  - Δ_STAT = |stations(ANT1, best_gain) − stations(ANT2, best_gain)| / max(stations) × 100 %
  - Wenn Δ_SNR ≥ 4 dB ODER Δ_STAT ≥ 50 %  → `_finish()` direkt
- best_gain pro Antenne nach Runde 1 = der Gain der den hoeheren
  score liefert (use_snr ? top5_avg : station_count) — gleiche Logik wie `_finish()`
- Kein Adaptiv-Stop wenn Daten-Probleme:
  - Overload-Marker in einem der 4 (ant,gain)-Buckets → kein Stop
  - station_count < 5 in einem Bucket → kein Stop (zu wenig Daten)
- Print-Log: `[DX-Tune] Adaptiv-Stop nach Runde 1 — Δ_SNR=X dB, Δ_STAT=Y %`
- Bei Stop: `_finish()` waehlt korrekten Gain ueber bisherige _phase_data
- Tests:
  - Klare Differenz (ANT1 viel staerker) → Stop nach Schritt 4, Pipeline ~ -60 s
  - Faire Verhaeltnisse (Δ klein) → kein Stop, normale 8 Schritte
  - Overload in einem Bucket → kein Stop trotz Δ-Treffer

### AC3 — #8 Adaptiv-Stop Phase 3
- In `core/diversity.py` `record_measurement` nach 4 Messungen pruefen:
  - 2 A1-Werte + 2 A2-Werte (Pattern A1A1A2A2 nach 4 Schritten)
  - rel_diff = |median(A1) − median(A2)| / max(median)  
  - Wenn rel_diff ≥ 0.15 (15 %, knapp 2× THRESHOLD=8 %) → `_evaluate()` direkt
- Constant: `EARLY_STOP_THRESHOLD = 0.15` (Klassenkonstante neben THRESHOLD)
- Frueh-Stop laeuft NUR wenn:
  - measure_step == 4 (genau 4 Werte gesammelt)
  - len(m1) == 2 UND len(m2) == 2 (sanity check)
  - peak > 1.0 (gleiche Bedingung wie regulaeres _evaluate)
- Print-Log: `[Diversity] Adaptiv-Stop nach 4 Zyklen — rel_diff=X%, ratio=Y`
- Modus-aware Override: aktuell `MEASURE_CYCLES = 6 × _MULT[mode]`
  - FT8: 6 → Stop nach 4 (-30 s)
  - FT4: 12 → analog Stop nach 8 (Faktor 2/3)
  - FT2: 24 → analog Stop nach 16
  - **Lieber:** Stop-Schwelle relativ definieren — `EARLY_STOP_AT = MEASURE_CYCLES * 2 // 3`
  - Damit FT8: 4, FT4: 8, FT2: 16 — proportional skaliert
- Tests:
  - Klare A1-Dominanz → Stop nach 4, ratio=70:30
  - Klare A2-Dominanz → Stop nach 4, ratio=30:70
  - Faire 50:50 → kein Stop, normale 6 Zyklen
  - Edge: rel_diff = exakt 0.15 → Stop (>= statt >)

## Reihenfolge / Atomare Commits

1. **Commit 1 — #6 ROUNDS=3→2** (kleinste Aenderung, sofort messbar)
2. **Commit 2 — Tests fuer #7** (Stop-Logik + Edge-Cases) — Test-First
3. **Commit 3 — #7 Implementation** (Adaptiv-Stop Phase 2)
4. **Commit 4 — Tests fuer #8** (Stop-Logik + Modus-Skalierung)
5. **Commit 5 — #8 Implementation** (Adaptiv-Stop Phase 3)
6. **Commit 6 — APP_VERSION 0.91 + 4-Datei-Update**

## Risiken (offen fuer V2)

1. **Schwellen-Tuning:** 4 dB / 50 % / 15 % sind Schaetzungen. Ohne
   Feldtest nicht garantiert optimal. Lieber konservativ (schwer trigger-
   bar) als zu aggressiv (falsche Frueh-Stops).
2. **Modus-Skalierung #8:** FT4/FT2-Stop-Trigger nach `2*MEASURE_CYCLES//3`
   nicht durch Datenlage validiert (alle Statistiken kommen von FT8).
3. **Overload-Handling #7:** Was ist „Overload-Marker"? `_has_overload(key)`
   pruefte ob `None` in `_phase_data[key]`. Wenn nur 1/4 Buckets Overload
   hat: trotzdem Stop oder nicht?
4. **#7 + #8 koppeln?** Wenn #7 Phase 2 frueh stoppt, ist die ANT-Hierarchie
   fast schon klar. Macht es dann Sinn Phase 3 trotzdem voll zu laufen?
   Antwort wahrscheinlich: ja — Phase 2 misst Gain pro ANT, Phase 3 misst
   Diversity-Verhaeltnis (anderes Ziel).
5. **Tests-Anzahl:** v0.90 stand bei 664. Block 2 fuegt grob +6-10 Tests dazu
   (3 Stop-Cases × 2 Phasen + Edge-Cases). Ziel: ~672-674 gruene Tests.

## Erwartete Tests-Erhoehung

```
+ tests/test_dx_tune_adaptive_stop.py (NEU)
  - test_phase2_stop_on_snr_diff
  - test_phase2_stop_on_station_diff
  - test_phase2_no_stop_on_fair
  - test_phase2_no_stop_on_overload
+ tests/test_diversity.py (Erweiterung)
  - test_phase3_stop_on_a1_dominant
  - test_phase3_stop_on_a2_dominant
  - test_phase3_no_stop_on_fair
  - test_phase3_modes_scaling (FT4/FT2 Schwellen)
```

## Was ist NICHT Teil von Block 2

- ROUNDS auf 1 reduzieren — zu wenig Daten fuer robusten Median
- THRESHOLD von 8 % auf andere Schwelle aendern — orthogonal zu Adaptiv-Stop
- Cache-Reuse beim Bandwechsel — eigener TODO (`project_diversity_cache_reuse.md`)
- OPERATE_CYCLES = 60 erhoehen — eigene Diskussion, nach Block-2-Feldtest
- Bandwechsel-Race in mw_radio.py — separater Workflow

## Trigger-Saetze fuer Mike

- „Block 2 starten" → diesen Workflow durchziehen (V1 → V2 → R1 → V3 → Plan → Code)
- „Block 2 abbrechen" → falls V3 zu unsicher
