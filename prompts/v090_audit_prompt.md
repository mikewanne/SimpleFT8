# Audit-Auftrag — Gain-Messung (Phase 2) + Diversity-Einmessen (Phase 3)

## Rolle für DeepSeek-R1

Du bist Senior-Reviewer. Schaue **nur nach offensichtlichen Fehlern**:
Race-Conditions, Off-by-One-Bugs, falsche Branches, stale State,
NoneType-AttributeErrors, Threading-Probleme, falsche Schwellenwerte,
inkonsistente Annahmen zwischen Modulen.

**KEINE Architektur-Verbesserungs-Vorschläge.** Keine „könnte man besser
machen". Nur **„hier ist ein Fehler"** oder **„hier ist ein Verdacht".**

Wenn alles sauber: sag „keine offensichtlichen Fehler gefunden" und gut.

Antworte auf Deutsch, strukturiert pro Modul.

## Kontext (Stand 2026-05-04, v0.89)

Pipeline beim Klick auf „Diversity Standard"/„Diversity DX":

**Phase 2 — Gain-Messung (12 Zyklen, ~3 Min):**
- `ui/dx_tune_dialog.py` mit `_build_interleaved_schedule()`
- `GAIN_VALUES = [10, 20]`, `ROUNDS = 3` → 2 ANT × 2 GAIN × 3 Runden = 12 Eintraege
- Pro Zyklus: `messages[].snr` sammeln, Top-5-Schnitt, Overload-Check
- Modus DX (`scoring_mode="snr"`): bestes Top-5-SNR pro Antenne
- Modus Standard (`scoring_mode="stations"`): meiste Stationen pro Antenne
- Per-Antenne-Gewinner (Gain) → `_on_dx_tune_accepted` speichert in PresetStore
- Block-1-relevant: `_skip_first` wurde gerade entfernt — erster Zyklus
  wird nicht mehr ignoriert.

**Phase 3 — Diversity-Einmessen (6 Zyklen, ~1:30 Min):**
- `core/diversity.py` `DiversityController`
- `MEASURE_CYCLES = 6` (3×A1 + 3×A2 nach Block 1, vorher 8 = 4×A1 + 4×A2)
- Pattern in operate (Standard):
  `_PAT_70_A1 = ("A1","A1","A2","A1","A1","A2")` und Spiegelbild `_PAT_70_A2`
- Mess-Phase: alternating A1/A2 Zyklen — Median ueber Werte pro Antenne
- Schwelle 8 % relative Differenz → 70:30 oder 50:50
- Mindestens `MIN_MEASURE_STATIONS = 5` Stationen pro Zyklus damit Wert
  als „gueltig" gilt
- DX-Score: `dx_weak_count` (Stationen mit SNR < -10 dB)
- `MEASURE_CYCLES` wird in `ui/mw_radio.py:798` zur Laufzeit auf
  `6 * _MULT.get(mode, 1)` gesetzt (Modus-skaliert: FT8=1, FT4=2, FT2=4)

**Cycle-Handling:** `ui/mw_cycle.py` aggregiert pro Zyklus + dispatched
zu `_handle_diversity_measure` / `_handle_diversity_operate` /
`_handle_normal_mode`.

## Schwellenwerte / Konstanten zum Pruefen

- `DiversityController.MEASURE_CYCLES = 6`
- `DiversityController.OPERATE_CYCLES = 60`
- `DiversityController.THRESHOLD = 0.08` (8%)
- `DiversityController.MIN_MEASURE_STATIONS = 5`
- `dx_tune_dialog.GAIN_VALUES = [10, 20]`
- `dx_tune_dialog.ROUNDS = 3`
- DX-Score-Threshold: SNR < -10 dB
- Mode-Multiplikatoren `_MULT = {"FT8": 1, "FT4": 2, "FT2": 4}`

## Was du NICHT pruefen sollst

- Code-Style, Naming, Doku-Vollstaendigkeit
- KISS-Bewertung, „koennte man eleganter loesen"
- Tests / Test-Coverage
- Performance-Optimierungen
- UX/UI-Verbesserungen

## Was du pruefen sollst

Pro Modul:

1. **`ui/dx_tune_dialog.py`** — Phase-2-Gain-Messung
   - Schedule-Erzeugung korrekt? Reihenfolge ANT/Gain stimmt mit Round-Even/Odd?
   - Overload-Check-Logik korrekt? `_detect_overload` Schwellen plausibel?
   - `_finish` waehlt richtige Gewinner-Gain?
   - Race: Was wenn Dialog mid-Slot-cancelled wird?
   - feed_cycle: nach Block-1-Aenderung (Skip-First raus) — bricht etwas?

2. **`core/diversity.py`** — Phase-3-Diversity-Controller
   - Mess-Pattern alternating wirklich fair? Bei MEASURE_CYCLES=6 → 3×A1 + 3×A2?
   - Median-Logik fuer Standard vs DX korrekt?
   - 8%-Schwelle: relativ-zu-was-Berechnung?
   - Phase-Uebergang measure→operate: timing korrekt?
   - Threading: `_hist_lock` deckt alle Race-Pfade ab?
   - `record_measurement` in falscher Phase → No-Op?

3. **`ui/mw_cycle.py`** — Cycle-Dispatch
   - `_handle_diversity_measure`: triggert phase-Uebergang sauber?
   - `_handle_diversity_operate`: erkennt operate→measure-Rueckfall (nach 60 Zyklen)?
   - `_diversity_in_operate` Transition-Guard greift korrekt nach Block-1-Aenderungen?

4. **`ui/mw_radio.py`** (nur `_enable_diversity` + Diversity-Init-Pfad)
   - `MEASURE_CYCLES = 6 * _MULT` — synchron mit `core/diversity.py:26`?
   - Race: Bandwechsel waehrend Phase 3 → bricht Mess-Phase sauber ab?
   - Preset-Loading: korrekte Gain-Werte ans Radio?

## Format der Antwort

Strukturiere wie:

```
## ui/dx_tune_dialog.py
- (kein Befund) ODER:
- 🔴 BUG: <Stelle> - <Beschreibung>
- 🟡 VERDACHT: <Stelle> - <warum verdaechtig>

## core/diversity.py
- ...

## ui/mw_cycle.py
- ...

## ui/mw_radio.py
- ...

## Cross-Cutting
- ...
```

Knapp, sachlich, deutsch.
