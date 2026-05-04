# R1-Review-Auftrag — v0.90 Mess-Pattern-Bug-Fix V2

## Rolle

Du bist Senior-Reviewer fuer einen V2-Prompt. **Kritisier den Plan, nicht
das Problem.** Konkret: was uebersieht V2? Was ist mehrdeutig? Welche
Akzeptanzkriterien fehlen? Welche Tests fingen den Bug nicht? Wo droht
Folge-Schaden?

**KEIN Rewrite des Prompts.** Stichpunkte, deutsch, knapp.

## Kontext

SimpleFT8 v0.89 (Pipeline-Optimierung Block 1 erledigt). Bug seit
Phase 3 (vor v0.36) in `core/diversity.py:86`: Mess-Pattern
`("A2","A1","A1","A2","A1","A1")` ergibt **4× A1 + 2× A2** auf 6 Slots
statt fairem 3:3 → ANT2 strukturell unter-gemessen → 8 %-Schwelle
bevorzugt ANT1-Ratio. Mike's Beobachtung 4 % ANT2-Win-Rate auf 40 m
wird teilweise davon erklaert.

**V2-Fix:** Pattern → `("A1","A1","A2","A2","A1","A2")` (Plan-Datei
„Empfehlung Default-V1": Option C). 3:3 fair, beide Antennen mit
zusammenhaengendem Even+Odd-Paar (A1: Slots 0-1, A2: Slots 2-3),
Singletons 4 + 5.

V2 enthaelt 6 Akzeptanzkriterien:
- AC1 Pattern-Fix (1 Zeile + Kommentar)
- AC2 Doku-Updates (Z.7, Z.79-83, Z.403 Block-1-Doku-Bug mitfixt)
- AC3 Tests (2 neue: `test_measure_ratio_balanced` + `test_measure_seamless_loop`)
- AC4 APP_VERSION 0.89 → 0.90
- AC5 4-Datei-Update (HISTORY+HANDOFF+CLAUDE+Memory)
- AC6 Tests gruen vor Commit (661 erwartet)

## Pruefe folgendes

### 1. Pattern-Math

- Ist `("A1","A1","A2","A2","A1","A2")` wirklich fair 3:3?
- Beide Antennen Even+Odd? (A1 in 0,1,4 = even/odd/even; A2 in 2,3,5 = even/odd/odd)
- Loop-Uebergang Pos 5 (A2) → Pos 0 (A1) — nahtlos?
- Max consecutive 2? (A1A1 oder A2A2)
- Singleton-Asymmetrie (A1=Slot4=even, A2=Slot5=odd) — bringt das einen
  versteckten Bias?
- Alternative Patterns die noch besser waeren (Even+Odd-Symmetrie)?

### 2. Test-Vorschlaege

- Reichen die 2 neuen Tests um den Bug zu fangen UND Regression zu schuetzen?
- Was fehlt? Fairer Median-Test (Statistik-End-to-End)?
- Sollte ein Test pruefen dass beide Antennen mind. 1 Even+Odd-Paar zusammenhaengend bekommen?
- Sollte ein Test gegen ALTE Pattern-String regression-schuetzen?

### 3. Risiken (was V2 uebersieht)

- Ist die Pattern-Aenderung wirklich isoliert oder beeinflusst sie anderen Code?
  - `record_measurement` nutzt _measure_step + ant — beide bleiben gleich?
  - `_evaluate` Median ueber `m1`/`m2` Listen — beide haben jetzt 3 Werte
    statt 4+2 → robuster gegen Ausreisser?
  - Cycle-Dispatch in `mw_cycle._handle_diversity_measure` — pattern-agnostisch?
- 🟡 R1's bisheriger Bandwechsel-Race-Verdacht (`mw_radio.py` _on_band_changed):
  ist V2's Out-of-Scope-Begruendung sauber? Gehoert das doch in v0.90?
- Statistik-Disclaimer in HISTORY ausreichend? Sollten Pre-v0.90 PDFs/MDs
  nachtraeglich annotiert werden?

### 4. Doku-Findings

- `Z.7` Block-1-Doku-Bug („4 Zyklen") — sollten andere Doku-Stellen auch
  geprueft werden? (HISTORY/HANDOFF/CLAUDE)
- Block-1 Commit-Message `3a4de56` sagte „4×A1+4×A2 → 3×A1+3×A2" — Bug
  war damals schon da, niemand hat's gemerkt.

### 5. Workflow-Disziplin

- V2 sagt 2 atomare Commits geplant. Reicht das? Sollte Doku-Update
  separater Commit sein? Memory-Update separat?

## Antwort-Format

```
## Pattern-Math
- (kein Befund) ODER:
- 🔴 KRITISCH: <Stelle> - <Grund>
- 🟡 EMPFEHLUNG: <Stelle> - <Begruendung>

## Test-Vorschlaege
...

## Risiken
...

## Doku-Findings
...

## Workflow
...

## Cross-Cutting
...
```
