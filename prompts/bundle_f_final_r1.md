# Bundle F Final-R1 Review

Code ist fertig (V1→V2→R1→V3 → Code). Bitte Final-Review.

## Stand

- **Tests:** 1179 (Bundle E) → 1183 grün (T5 in test_omni_cq_signal raus,
  +5 in neuem test_bundle_f.py, +0 in test_p23/p45/p34_elif)
- **Backup:** `Appsicherungen/2026-05-14_v0.97.22_vor_bundle_f/`
- **APP_VERSION:** 0.97.22 → 0.97.23

## Patches

### C1 — `core/omni_cq.py` (Phase-Check raus)

```python
# VORHER (Z.228-235):
        if not self._active or self._paused:
            return

        # V2-L12: kein Senden waehrend Diversity-Mess-Phase
        if self._diversity.phase != "operate":
            return

        # V2-L9 Fresh-Compute is_even — robust gegen Signal-Latenz

# NACHHER:
        if not self._active or self._paused:
            return

        # V2-L9 Fresh-Compute is_even — robust gegen Signal-Latenz
```

### C2 — Tests + test_bundle_f.py + test_bundle_d.py Farbe

- `tests/test_omni_cq_signal.py`: `diversity_phase`-Param raus,
  `diversity.phase = ...`-Setter raus, T5
  (`test_skips_during_diversity_measure_phase`) komplett gelöscht
- `tests/test_p23_omni_counter.py`: gleicher Param + Setter raus
- `tests/test_p45_omni_stats_guard.py`: `obj._diversity_ctrl.phase
  = "operate"` Zeile raus
- `tests/test_p34_elif_chain_intact.py`: `s._diversity_ctrl.phase =
  "operate"` Zeile raus
- `tests/test_bundle_d.py:212`: Assertion `#FF66CC` → `#FFAA00`,
  Docstring Magenta → Orange
- `tests/test_bundle_f.py` NEU mit 5 Tests:
  - T1: DiversityController hat KEIN phase-Attribut (Bug-Schutz)
  - T2: OmniCQ.on_cycle_start ruft transmit ohne phase-Zugriff
    (mit ECHTEM DiversityController, nicht MagicMock — Lesson
    `feedback_test_critical_path_not_mock.md`)
  - T3: ControlPanel hat KEIN cycle_bar-Attribut
  - T4: ControlPanel hat KEIN update_cycle_bar-Methode
  - T5: _slot_progress_bar nutzt #FFAA00 für Odd (+ kein #FF66CC)

### C3 — cycle_bar weg (`ui/control_panel.py` + `ui/mw_cycle.py`)

- `control_panel.py:1150-1156`: cycle_bar Definition + addWidget raus,
  ersetzt durch `lay.addSpacing(4)` (R1-SOLLTE-2 Layout-Schutz)
- `control_panel.py:1332`: cycle_bar-Alias raus
- `control_panel.py:1947-1957`: update_cycle_bar Methode raus
- `mw_cycle.py:_on_cycle_tick`: Caller raus, Method bleibt mit
  return-no-op + Kommentar (verhindert dass Signal-Verbindung bricht)

### C4 — `ui/main_window.py` Magenta → Orange

- Z.486 Klassen-Kommentar: „Cyan (Even) / Magenta (Odd)" → „Cyan
  (Even) / Orange (Odd)"
- Z.495 Tooltip: gleicher Ersatz
- Z.1253 Docstring: „Magenta `#FF66CC` (Odd)" → „Orange `#FFAA00` (Odd)"
- Z.1269 chunk-Konstante: `"#FF66CC"` → `"#FFAA00"`, Kommentar
  „cyan / magenta" → „cyan / orange (Bundle F)"

## R1-SOLLTE-Findings Status

- **R1-SOLLTE-1 (DXTune-Race):** ABGELEHNT — R1 hatte
  `_gain_measure_locked` auf DiversityController halluziniert (sitzt
  nur in mw_radio.py). `getattr` würde immer False zurückgeben →
  Pseudo-Schutz. KISS-Position: DXTuneDialog ist modal, User kann
  OMNI nicht währenddessen starten. Falls Race empirisch auftaucht:
  separater Fix mit echter Synchronisation.
- **R1-SOLLTE-2 (Layout):** ÜBERNOMMEN via `lay.addSpacing(4)` als
  Ersatz für entfernte cycle_bar-Höhe (~18px → 4px reicht, Trennlinie
  klebt nicht direkt am state_label).
- **R1-SOLLTE-3 (Field-Test):** ÜBERNOMMEN in V3 — Field-Test F5
  durch QSO-Interaktion ersetzt.

## Bitte Final-R1-Antwort

1. „Push freigegeben" oder „Re-Review nötig"?
2. Kritische Punkte (KP) übersehen?
3. Anti-Pattern eingeschlichen?
4. SOLLTE-1-Ablehnung mit „Halluzinations-Diagnose" akzeptabel?
