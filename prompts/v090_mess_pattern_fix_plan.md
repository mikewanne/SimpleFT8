# v0.90 — Mess-Pattern-Bug Fix (Plan, Stand 2026-05-04)

## Status
- BUG identifiziert (R1-Audit 2026-05-04, siehe `prompts/v090_audit_r1.md`)
- Workflow noch NICHT gestartet — V1→V2→R1→V3 nach Mike-Trigger
- Trigger Mike: „v0.90 starten" oder „Mess-Pattern-Fix starten"

## Problem (KRITISCH 🔴)

**Datei:** `core/diversity.py:86` (innerhalb `def choose()`)

```python
if self._phase == "measure":
    # Messung: A2,A1,A1,A2 (6-Slot nahtlos, beide Paritaeten)
    return ("A2","A1","A1","A2","A1","A1")[self._measure_step % 6]
```

Das Pattern ``("A2","A1","A1","A2","A1","A1")`` enthaelt:
- Slot 0: A2
- Slot 1: A1
- Slot 2: A1
- Slot 3: A2
- Slot 4: A1
- Slot 5: A1

= **4× A1 + 2× A2** auf 6 Slots = identisch mit OPERATE-70:30-Pattern.

## Auswirkung

- Bei ``MEASURE_CYCLES = 6`` (Block 1): Median ueber 4 ANT1-Werte vs.
  Median ueber **nur 2** ANT2-Werte → ANT2 strukturell unter-gemessen.
- Bei ``MEASURE_CYCLES = 8`` (vor Block 1): 5:3 — auch unfair.
- Diversity-Ratio bevorzugt ANT1 systematisch → 8%-Schwelle haeufiger
  ANT1-Win → Pattern 70:30 ANT1 dominant.
- **Erklaert teilweise Mike's Beobachtung 4% ANT2-Win-Rate auf 40m.**
- Statistik-Implikation: alle bisherigen Diversity-Daten haben
  strukturellen Mess-Bias. KEIN Wegwerfen — Pooled-Mean +88%/+124%
  bleibt valide weil ANT2 trotz Bias signifikant beitraegt. Aber
  faire Messung wird wahrscheinlich noch hoeheren Win-Rate zeigen.

## Doku-Inkonsistenz

- ``core/diversity.py:7``: „Auswertung: Median ueber 4 Zyklen pro Antenne"
- ``core/diversity.py:19`` (nach Block 1): „MESS-PHASE (6 Zyklen): 3×A1 + 3×A2 messen"
- Code-Pattern: 4×A1 + 2×A2

→ Doku spezifiziert was der Code NICHT tut. Bug seit Phase 3 in
diversity.py existiert (vor v0.36 oder so).

## Fix-Optionen

### Option A — Pattern auf 3:3 alternating

```python
return ("A1","A2","A1","A2","A1","A2")[self._measure_step % 6]
```

- 3 ANT1 + 3 ANT2 auf 6 Slots ✅ fair
- ABER: jede Antenne sieht nur 1 Paritaet (A1 immer Even, A2 immer Odd)
  oder umgekehrt — Even+Odd-Symmetrie verloren
- Pro: einfach, 1-Zeilen-Fix
- Con: Even/Odd-Bias — wenn Bandbedingungen Even/Odd-asymmetrisch sind
  (haeufig bei FT8 Pile-Up-Effekten), wird ANT1 oder ANT2 zufaellig
  bevorzugt

### Option B — Pattern 4:4 + ``MEASURE_CYCLES = 8`` zurück

```python
return ("A1","A1","A2","A2","A1","A1","A2","A2")[self._measure_step % 8]
```

Plus ``MEASURE_CYCLES = 8`` und ``mw_radio.py:798: 8 * _MULT``.

- 4 ANT1 + 4 ANT2 auf 8 Slots ✅ fair
- Beide Antennen sehen Even+Odd ✅
- Pro: konsistent mit Original-Doku „Median ueber 4 Zyklen pro Antenne"
- Con: rollt Block 1 #4 (-30 s Ersparnis) zurueck — Pipeline geht
  von 4:31 wieder hoch auf ~5:01

### Option C — Pattern 3:3 mit Doppel-Slots (Kompromiss)

```python
return ("A1","A1","A2","A2","A1","A2")[self._measure_step % 6]
```

- 3 A1 + 3 A2 ✅ fair
- A1 hat Even+Odd-Paar (Slot 0-1), A2 hat Even+Odd-Paar (Slot 2-3),
  Singletons 4+5 mit gemischten Paritaeten
- Pro: 6 Slots bleiben (Block-1-Ersparnis bleibt), beide Antennen
  bekommen mind. einen Even+Odd-Paar
- Con: leichte Asymmetrie in Singleton-Slots (akzeptabel)

## Empfehlung Default-V1

**Option C** als Default — fair, behaelt Block-1-Ersparnis, beide
Antennen bekommen Even+Odd-Paar. Falls R1 Option B begruendet besser
findet, eskalieren.

## V1-Akzeptanzkriterien (Skizze)

### AC1 — Mess-Pattern fix

- ``core/diversity.py:86`` Pattern-Aenderung
- ``core/diversity.py:7+19`` Doku-Aktualisierung
- Falls Option B: ``core/diversity.py:26`` ``MEASURE_CYCLES = 8``
  + ``ui/mw_radio.py:798`` ``8 * _MULT``

### AC2 — Tests

- ``tests/test_modules.py::test_diversity_phase_transition_after_6_measurements``
  ggf. anpassen (bei Option B auf 8 zurueck)
- Neuer Test: ``test_diversity_measure_pattern_balanced`` — verifiziert
  ueber alle slots des Pattern dass A1-Count == A2-Count (innerhalb 1)
- Neuer Test: ``test_diversity_measure_pattern_parities`` — verifiziert
  dass beide Antennen mind. 1 Slot in Even+Odd-Konfig haben

### AC3 — Statistik-Disclaimer

- ``HISTORY.md`` v0.90-Eintrag erwaehnt explizit dass alle
  Diversity-Daten vor v0.90 Mess-Bias hatten
- ``auswertung/`` PDFs ggf. mit Hinweis-Footer „Daten vor v0.90 mit
  Mess-Bias 4:2 statt 3:3 — Pooled-Mean valide, absolute Werte
  konservativ"

## Nicht in v0.90

- 🟡 Bandwechsel-Race (R1-Verdacht): erst nach v0.90 verifizieren —
  separater Mini-Bug-Fix wenn Race echt ist.

## Workflow

1. Mike Trigger „v0.90 starten"
2. Code-Verifikation diversity.py:86 + Test-Lage
3. V1 entwerfen mit Option-C-Default
4. V2 Self-Review
5. R1-Review (Pattern-Math + Test-Vorschlaege)
6. V3 Mike-Freigabe
7. Plan-Mode + atomare Commits
8. APP_VERSION 0.89 → 0.90 + HISTORY/HANDOFF/CLAUDE/Memory updates

## Snapshot vor v0.90

- v0.89 ist letzter sauberer Snapshot (5 atomare Commits Block 1)
- Tag setzen ``v0.89.0`` falls Mike Push-frei wuenscht
- Rollback bei Problemen: ``git checkout v0.89.0``

## Verwandte Dateien

- ``prompts/v090_audit_prompt.md`` (R1-Audit-Auftrag)
- ``prompts/v090_audit_r1.md`` (R1-Antwort 2026-05-04)
- ``prompts/kalibrier_optimierung_plan.md`` (Block-Plan, fuer Block 2 Verweis)
- Memory ``project_v090_mess_pattern_bug.md``
