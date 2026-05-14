# Bundle G Final-R1 Review

Code fertig. Bitte Final-Review.

## Stand

- **Tests:** 1183 (Bundle F) → **1194 grün** (+11: V3 prognostizierte +10,
  zusätzliches T7b für Normal-Click-Negativ-Fall)
- **Backup:** `Appsicherungen/2026-05-14_v0.97.23_vor_bundle_g/`
- **APP_VERSION:** 0.97.23 → 0.97.24 (folgt im Doku-Commit)

## Patches

### C1 — `ui/control_panel.py` (Signal + Toggle-Branch)

```python
rx_mode_changed = Signal(str)
diversity_subtoggle_requested = Signal()  # Bundle G

def _on_rx_mode_clicked(self, mode: str):
    if mode == self._current_rx_mode:
        if mode == "diversity":
            self.diversity_subtoggle_requested.emit()
        return
    ...
```

Plus btn_diversity Tooltip:
„Klick im Normal-Modus: Auswahl Standard/DX. Erneuter Klick im
Diversity-Modus: wechselt zwischen Standard und DX (nur bei
Bandpilot=Aus)."

### C2 — `ui/mw_radio.py` (Slot)

```python
@Slot()
def _on_diversity_subtoggle_requested(self):
    bp_mode = self.settings.get("bandpilot_mode", "off")
    if bp_mode != "off":
        return
    if getattr(self, '_gain_measure_locked', False):
        return
    if not self.radio.ip:
        return
    # R1-K1+K2: OMNI+Hunt stoppen vor Sub-Mode-Wechsel
    if hasattr(self, "_omni_cq") and self._omni_cq.is_active():
        self._omni_cq.stop("scoring_toggle")
    if hasattr(self, "_auto_hunt") and self._auto_hunt.active:
        self._auto_hunt.stop_auto_hunt("scoring_toggle")
    current = getattr(self._diversity_ctrl, 'scoring_mode', 'normal')
    new = "dx" if current == "normal" else "normal"
    self._activate_diversity_with_scoring(new)
```

### C3 — `ui/main_window.py` (Signal-Connect)

```python
self.control_panel.diversity_subtoggle_requested.connect(
    self._on_diversity_subtoggle_requested)
```

### C4 — `tests/test_bundle_g.py` (11 Tests, 10 V3-AC + T7b Bonus)

- T1: Toggle Std → DX bei bp=off
- T2: Toggle DX → Std bei bp=off
- T3: bp=auto → no-op
- T4: bp=manual → no-op
- T5: gain_locked → no-op
- T6: radio.ip=None → no-op
- T7: Signal-Emit aus control_panel bei 2. Div-Klick
- **T7b (Bonus):** 2. Normal-Klick emit'd KEIN Signal
- T8: ECHTER DiversityController scoring_mode Toggle
- T9: OMNI-Stop bei Toggle
- T10: Auto-Hunt-Stop bei Toggle

## R1-Findings Status

- **K1 (DXTuneDialog-Race):** ÜBERNOMMEN — OMNI+Hunt-Stop im Slot
- **K2 (OMNI bei Toggle ohne Dialog):** ÜBERNOMMEN (gleicher Stop-Pfad)
- **S1 (Manual-Mode Doku):** ÜBERNOMMEN via Tooltip
- **S2 (Integration-Test):** ÜBERNOMMEN als T8
- **K3 (Helper-Refactor):** ABGELEHNT KISS (nur 2 Aufrufer)
- **K-Field F8/F9:** ÜBERNOMMEN in HISTORY/HANDOFF
- **K-Naming:** ABGELEHNT (`diversity_subtoggle_requested` bleibt)

## Bitte Final-R1-Antwort

1. „Push freigegeben" oder „Re-Review"?
2. Kritische Punkte übersehen?
3. Anti-Pattern eingeschlichen (besonders Tests)?
