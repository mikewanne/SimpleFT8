# Bundle G — V3 (Final Plan, Compact-fest)

**Basis:** V1 + V2 + R1 (8/10, 2 KRITISCH + 2 SOLLTE + 2 KÖNNTE)
**Datum:** 2026-05-14 vormittags

## R1-Findings Übernahme

| Finding | Status | Aktion |
|---|---|---|
| **K1 (DXTuneDialog-Race):** OMNI/Hunt laufen während Dialog → Encoder-Konflikt | **ÜBERNOMMEN** | Beim Toggle OMNI+Auto-Hunt explizit stoppen wie bei `_on_rx_mode_changed` Z.541-544 |
| **K2 (OMNI bei Toggle ohne Dialog):** `_diversity_stations={}` → Race | **ÜBERNOMMEN** | Selbe Stop-Logik abdeckt das (OMNI gestoppt = kein get_free_cq_freq-Race) |
| S1 (Manual-Mode Dokumentation) | ÜBERNOMMEN | Tooltip auf btn_diversity ergänzen |
| S2 (Integration-Test) | ÜBERNOMMEN | T8 mit echtem DiversityController |
| K3 (Code-Duplikation `_can_change_rx_mode()`) | ABGELEHNT KISS | Nur 2 Aufrufer, Helper-Extraktion premature |
| K-Field (F8 CQ + F9 Hunt) | ÜBERNOMMEN | Field-Test erweitert |
| K-Naming | ABGELEHNT | `diversity_subtoggle_requested` bleibt |

## Acceptance Criteria (10 ACs)

### Code

**AC1 (`ui/control_panel.py`):**
- Neues Signal `diversity_subtoggle_requested = Signal()` in Klasse-
  Header (analog zu `rx_mode_changed`).
- `_on_rx_mode_clicked` (Z.1487+) erweitern:
  ```python
  if mode == self._current_rx_mode:
      if mode == "diversity":
          self.diversity_subtoggle_requested.emit()
      return
  ```

**AC2 (`ui/mw_radio.py`) NEU Slot:**
```python
@Slot()
def _on_diversity_subtoggle_requested(self):
    """Bundle G: Toggle Std ↔ DX bei wiederholtem Div-Klick.

    Nur wirksam bei Bandpilot=off + Radio verbunden + nicht
    gain_locked. OMNI+Auto-Hunt werden gestoppt (R1-K1+K2:
    DXTuneDialog-Race + Encoder-Konflikt-Schutz).
    """
    bp_mode = self.settings.get("bandpilot_mode", "off")
    if bp_mode != "off":
        return
    if getattr(self, '_gain_measure_locked', False):
        return
    if not self.radio.ip:
        return
    # R1-K1+K2: OMNI+Hunt stoppen wie bei _on_rx_mode_changed
    if hasattr(self, "_omni_cq") and self._omni_cq.is_active():
        self._omni_cq.stop("scoring_toggle")
    if hasattr(self, "_auto_hunt") and self._auto_hunt.active:
        self._auto_hunt.stop_auto_hunt("scoring_toggle")
    current = getattr(self._diversity_ctrl, 'scoring_mode', 'normal')
    new = "dx" if current == "normal" else "normal"
    self._activate_diversity_with_scoring(new)
```

**AC3 (`ui/main_window.py`):** Signal-Connect:
```python
self.control_panel.diversity_subtoggle_requested.connect(
    self._on_diversity_subtoggle_requested)
```

**AC4 (Tooltip-Ergänzung):** `btn_diversity.setToolTip(...)` erweitern
um Hinweis „Erneuter Klick wechselt zwischen Standard und DX (nur bei
Bandpilot=Aus)".

### Tests `tests/test_bundle_g.py` NEU

- **T1:** Toggle Std → DX bei bp=off, alle Guards OK →
  `_activate_diversity_with_scoring("dx")` gerufen, OMNI gestoppt
- **T2:** Toggle DX → Std bei bp=off → `_activate_diversity_with_scoring("normal")`
- **T3:** Toggle bei bp=auto → no-op
- **T4:** Toggle bei bp=manual → no-op
- **T5:** Toggle bei `_gain_measure_locked=True` → no-op
- **T6:** Toggle ohne `radio.ip` → no-op
- **T7:** Signal `diversity_subtoggle_requested` aus
  control_panel._on_rx_mode_clicked emit'd (signal-spy)
- **T8:** Integration mit ECHTEM `DiversityController` →
  `scoring_mode`-Property wechselt von „normal" zu „dx" und zurück
  (Memory-Lesson `feedback_test_critical_path_not_mock.md`)
- **T9:** OMNI aktiv + Toggle → `omni_cq.stop("scoring_toggle")` gerufen
- **T10:** Auto-Hunt aktiv + Toggle → `auto_hunt.stop_auto_hunt(...)` gerufen

### Backup

**AC5:** `Appsicherungen/2026-05-14_v0.97.23_vor_bundle_g/` mit
`ui/control_panel.py`, `ui/mw_radio.py`, `ui/main_window.py`.

### Commits

**AC6 (C1):** `ui/control_panel.py` Signal + Toggle-Branch
**AC7 (C2):** `ui/mw_radio.py` Slot + OMNI/Hunt-Stop
**AC8 (C3):** `ui/main_window.py` Connect + btn_diversity Tooltip
**AC9 (C4):** `tests/test_bundle_g.py` NEU (10 Tests)
**AC10 (C5):** APP_VERSION → 0.97.24 + HISTORY + HANDOFF + CLAUDE +
Memory + Plan-Files

## Test-Bilanz

- Vor Bundle G: 1183 grün
- +10 Bundle G Tests
- **Erwartung: ~1193 grün**

## Field-Test F1-F9

| # | Test | Erwartung |
|---|---|---|
| F1 | Normal → Klick DIVERSITY → Dialog Std/DX | Dialog erscheint (heute) |
| F2 | Div Std → Klick DIVERSITY → **direkt DX** | Kein Dialog, Label „DIVERSITY DX" |
| F3 | Div DX → Klick DIVERSITY → **direkt Standard** | Kein Dialog, Label „DIVERSITY" |
| F4 | Bandpilot=Auto + Div-Klick im Div | Kein Toggle, no-op |
| F5 | Bandpilot=Manual + Div-Klick im Div | Kein Toggle, no-op |
| F6 | OMNI-CQ aktiv + Toggle | OMNI gestoppt |
| F7 | Auto-Hunt aktiv + Toggle | Hunt gestoppt |
| F8 (NEU R1) | CQ aktiv + Toggle | CQ läuft weiter (kein OMNI) — Stations-Reset OK |
| F9 (NEU R1) | Während Gain-Mess Toggle-Klick | Toggle blockiert |

## V3 Compact-Sicherung

Verifiziert gegen Code:
- `control_panel.py:1487-1502` `_on_rx_mode_clicked`
- `mw_radio.py:522-720` `_on_rx_mode_changed` + Pattern
- `mw_radio.py:641-700` `_activate_diversity_with_scoring`
- `core/diversity.py:82-94` `scoring_mode` ∈ {„normal", „dx"}
- `mw_radio.py:541-544` OMNI/Hunt-Stop-Pattern bei Mode-Wechsel
- `config/settings.py:67` `bandpilot_mode` ∈ {„off", „auto", „manual"}
