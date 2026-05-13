# V3 — Block 1 Kalibrierungs-Pipeline Optimierung (final, R1-reviewed)

## Stand
- V1 → V2 (Self-Review) → R1-Review (DeepSeek-R1, 2026-05-04) → V3.
- R1 hat 1 KRITISCHE Luecke gefunden (AC4: mw_radio.py:798 ueberschreibt
  Konstante) + mehrere uebersehene Code-Stellen (AC2: _start_tune_only,
  AC3: 6 statt 2 hardcoded "18"-Texte).
- V3 ist die korrigierte Endfassung.

## Hardware-Sicherheits-Check ✅
- TUNE bleibt auf ANT1 (`mw_radio.py:988` + `:1031` Statusbar-Texte).
- Diversity-Mess-Phase ist RX-only auf beiden Antennen.
- Keine TX-Pfad-Aenderungen durch Block 1.

---

## Akzeptanzkriterien — 5 atomare Commits

### AC1 — Skip-First-Cycle entfernen (#1, ~-15 s)

**Code-Stellen (`ui/dx_tune_dialog.py`):**
1. **Zeile 60** — Init entfernen:
   ```python
   self._skip_first = True  # ersten angebrochenen Zyklus ueberspringen
   ```
   → Zeile komplett loeschen.

2. **Zeile 215-219** — Logik in `feed_cycle()` entfernen:
   ```python
   if self._skip_first:
       self._skip_first = False
       self.detail_label.setText("Warte auf naechsten vollen Zyklus...")
       return
   ```
   → Block komplett loeschen.

**Verifikation:** `grep -n _skip_first ui/dx_tune_dialog.py` → 0 Treffer.

**Test-Pflicht:** `pytest tests/ -q` → 659 gruen. Falls Test
`_skip_first` direkt assertiert: anpassen oder loeschen.

**Risiko:** Mid-Slot-Start hat erste Zyklus-Daten teilweise. Bei 12 Zyklen
statistisch vernachlaessigbar.

---

### AC2 — TUNE 5 s → 3 s (#2, ~-2 s × 2 Pfade)

**Code-Stellen (`ui/mw_radio.py`):**

| # | Funktion | Zeile | Aenderung |
|---|---|---|---|
| 1 | `_start_tune_only()` | 964 | Docstring: `"Sendet 5s Carrier"` → `"Sendet 3s Carrier"` |
| 2 | `_start_tune_only()` | 969 | Docstring: `"waehrend der 5s ein Bandwechsel"` → `"waehrend der 3s"` |
| 3 | `_start_tune_only()` | 988 | Statusbar: `f"... fuer 5s ..."` → `f"... fuer 3s ..."` |
| 4 | `_start_tune_only()` | 1002 | `QTimer.singleShot(5000, _after_tune)` → `3000` |
| 5 | `_start_dx_tuning()` | 1031 | Statusbar: `f"... fuer 5s ..."` → `f"... fuer 3s ..."` |
| 6 | `_start_dx_tuning()` | 1053 | `QTimer.singleShot(5000, _after_tune)` → `3000` |

**Verifikation:**
- `grep -n "5000" ui/mw_radio.py` → die `_after_tune`-Treffer fallen weg
  (5000 in Bandpilot-Toast Z.675/720 bleibt — nicht relevant).
- `grep -n "fuer 5s" ui/mw_radio.py` → 0 Treffer.

**Test-Pflicht:** 659 gruen. Tests die `_start_dx_tuning` per Timer testen
gibt es laut Memory-Check nicht.

**Risiko:** Externer Tuner moeglicherweise zu kurz. Mike-Setup =
FlexRadio mit interner Tuner — sicher. **TODO fuer IC-7300-Fork
(CLAUDE.md TODO #7):** dort eigene Konstante mit hoeherem Wert.

---

### AC3 — GAIN_VALUES 3 → 2 (#3, ~-90 s)

**Entscheidung:** KISS-Variante — keine dynamische Fallback-Logik bei
Overload. User klickt manuell „Neu einmessen" wenn er Overload bekommt.

**Code-Stellen (`ui/dx_tune_dialog.py`):**

| # | Zeile | Aenderung |
|---|---|---|
| 1 | 4 | Modul-Docstring: `"18 Zyklen interleaved: ANT1@0 → ANT2@0 → ANT1@10 → ANT2@10 → ANT1@20 → ANT2@20"` → `"12 Zyklen interleaved: ANT1@10 → ANT2@10 → ANT1@20 → ANT2@20"` |
| 2 | 5 | Modul-Docstring: `"× 3 Runden = 4,5 Minuten"` → `"× 3 Runden = 3 Minuten"` |
| 3 | 22 | `GAIN_VALUES = [0, 10, 20]` → `GAIN_VALUES = [10, 20]` |
| 4 | 23 | Inline-Kommentar: `# 3 Runden × 6 Kombos = 18 Zyklen × 15s = 4,5 Min` → `# 3 Runden × 4 Kombos = 12 Zyklen × 15s = 3 Min` |
| 5 | 40 | `return schedule  # 18 Eintraege` → `# 12 Eintraege` |
| 6 | 55 | `self._schedule = _build_interleaved_schedule()  # 18 Schritte` → `# 12 Schritte` |
| 7 | 93 | UI-Hint Z.93-94: `"18 Zyklen ... ca. 4,5 Minuten"` → `"12 Zyklen ... ca. 3 Minuten"` |
| 8 | 282 | Methoden-Docstring: `"""Alle 18 Zyklen fertig"""` → `"""Alle 12 Zyklen fertig"""` |

**Bereits dynamisch (kein Bruch):**
- Z.200 `pos_in_round = self._step % (len(GAIN_VALUES) * 2) + 1` ✅
- Z.205 `f"Schritt {self._step + 1}/{len(self._schedule)}"` ✅
- Z.206 `f"({pos_in_round}/{len(GAIN_VALUES) * 2})"` ✅

**Verifikation:** `grep -n "\b18\b\|4,5 Min" ui/dx_tune_dialog.py` →
0 Treffer.

**Test-Pflicht:** 659 gruen. Falls Test `len(schedule) == 18` oder
`GAIN_VALUES == [0, 10, 20]` direkt assertiert: anpassen.

**Risiko:** Bei Mike-Setup (Kelemen-Dipol resonant 20m, Regenrinne
RX-only) Uebersteuerung bei 10 dB unwahrscheinlich. Falls beide Antennen
Overload → User sieht „kein passender Gain" und muss neu einmessen mit
anderem Setup.

---

### AC4 — Phase 3 MEASURE_CYCLES 8 → 6 (#4, ~-30 s) ⛔ KRITISCH

**R1-Finding:** Konstante in `core/diversity.py` wird in
`mw_radio.py:798` zur Laufzeit ueberschrieben — Aenderung an Konstante
allein hat **0 Wirkung**. Beide Stellen muessen synchron geaendert werden.

**Code-Stellen:**

| # | Datei | Zeile | Aenderung |
|---|---|---|---|
| 1 | `core/diversity.py` | 19 | Docstring: `"MESS-PHASE  (8 Zyklen): 4×A1 + 4×A2 messen"` → `"MESS-PHASE  (6 Zyklen): 3×A1 + 3×A2 messen"` |
| 2 | `core/diversity.py` | 26 | `MEASURE_CYCLES = 8   # 4×A1 + 4×A2 (~2 Min Fenster, je even+odd pro Antenne)` → `MEASURE_CYCLES = 6   # 3×A1 + 3×A2 (~1,5 Min Fenster, je even+odd pro Antenne)` |
| 3 | `ui/mw_radio.py` | 798 | `self._diversity_ctrl.MEASURE_CYCLES = 8 * _MULT.get(mode, 1)` → `6 * _MULT.get(mode, 1)` |

**Test-Anpassung (`tests/test_modules.py:2374-2388`):**

```python
def test_diversity_phase_transition_after_8_measurements():
    """Nach MEASURE_CYCLES (8) Messungen → automatisch zu phase=operate."""
    ...
    for i in range(7):  ...
    assert dc.phase == "measure", f"Nach 7 Messungen: phase={dc.phase}"
    dc.record_measurement("A2", ...)
    assert dc.phase == "operate"
```

→ **Aenderung:**
- Funktionsname: `..._after_8_measurements` → `..._after_6_measurements`
- Docstring: `"(8) Messungen"` → `"(6) Messungen"`
- `range(7)` → `range(5)`
- Assert-Message: `"Nach 7"` → `"Nach 5"`

**Verifikation:**
- `grep -n "MEASURE_CYCLES = 8\|= 8 \* _MULT" ` → 0 Treffer.
- `grep -n "8 Messungen\|after_8" tests/` → 0 Treffer.

**Test-Pflicht:** 659 gruen.

**Risiko:** Median ueber 3 statt 4 Werte pro Antenne — bei N=3 weniger
robust gegen einzelne Ausreisser. 8%-Schwelle ist aber grosszuegig — ein
Ausreisser kippt Schwelle nicht. Akzeptabel.

---

### AC5 — Cache 2 h → 6 h (#5, weniger Pipeline-Laeufe)

**Code-Stelle:**
- `core/preset_store.py:19` — `VALIDITY_SECONDS = 2 * 3600  # 2 Stunden`
  → `VALIDITY_SECONDS = 6 * 3600  # 6 Stunden`

**Verifikation:** `grep -n VALIDITY_SECONDS core/ tests/` → keine Tests
mit hardcoded `7200`.

**Test-Pflicht:** 659 gruen.

**Risiko:** Tag→Nacht-Bandoeffnungs-Wechsel — 6 h-alter Wert nicht mehr
optimal. Hobby-Use akzeptabel, User kann jederzeit „Neu einmessen".

---

## Atomare Commits (5 Stueck, in dieser Reihenfolge)

| # | Commit | Risk |
|---|---|---|
| C1 | `chore: Skip-First-Cycle in DX-Tune-Dialog entfernen (Block 1 #1)` | minimal |
| C2 | `chore: TUNE 5s → 3s in mw_radio (Block 1 #2)` | gering |
| C3 | `chore: Gain-Stufen 3 → 2 — Default [10, 20] (Block 1 #3)` | mittel |
| C4 | `chore: Phase 3 MEASURE_CYCLES 8 → 6 (Block 1 #4)` | mittel |
| C5 | `chore: Preset-Cache 2h → 6h (Block 1 #5)` | minimal |

**Pflicht zwischen Commits:** `pytest tests/ -q` 659 gruen. Bei Bruch
STOP, V3-Annahme pruefen.

## Erwartete Ersparnis Block 1
- Phase 1 (TUNE): 5 → 3 s = -2 s
- Skip-First: 15 s → 0 s = -15 s
- Phase 2 (DX-Tune-Dialog): 270 → 180 s = -90 s
- Phase 3 (Diversity-Einmessen): 120 → 90 s = -30 s
- Cache 6 h: kein direkter Pipeline-Effekt, aber weniger Laeufe pro Tag

**Pipeline 6:50 → ~4:35 (-2:15 Min, -33 %).**

## Rollback
- Pro Commit: `git revert <commit>`.
- Komplett: `git checkout v0.88.1`.

## Datei-Update-Pflicht nach Block 1 (Mike-Anweisung 01.05.)
1. **HISTORY.md** — `## 2026-05-04 v0.89 — Kalibrier-Pipeline Block 1`
2. **HANDOFF.md** in BEIDEN Verzeichnissen.
3. **CLAUDE.md** Header in BEIDEN Verzeichnissen (`Aktueller Stand` +
   Test-Count, falls geaendert).
4. **`main.py` `APP_VERSION`** auf `"0.89"`.
5. **Memory** ggf. aktualisieren falls Lessons aus Block 1.
6. **Plan-Datei** `prompts/kalibrier_optimierung_plan.md` — Block 1
   abhaken, Block 2 als naechstes markieren.
