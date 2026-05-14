# Bundle G — V1 (Plan-Entwurf)

**Datum:** 2026-05-14 vormittags nach Bundle F-Push
**Trigger:** Mike-Wunsch Direktwechsel zwischen Diversity Std und DX
(Bandpilot=Aus). Logik-Korrektur gegenüber V1-TODO-Entwurf.

## Mike-Spec

**Bandpilot=Aus, Toggle-Logik bei wiederholtem Klick auf DIVERSITY:**

| Aktueller Modus | Klick | Aktion |
|---|---|---|
| Normal | NORMAL | no-op |
| Normal | DIVERSITY | **Dialog Std/DX** (heute bereits implementiert) |
| Div Standard | DIVERSITY | **direkt → Div DX** (Toggle, kein Dialog) |
| Div DX | DIVERSITY | **direkt → Div Standard** (Toggle, kein Dialog) |
| Div (egal) | NORMAL | → Normal (heute schon) |

**Bandpilot=Auto:** keine Änderung in `_on_rx_mode_clicked` (Bandpilot
entscheidet via `_apply_bandpilot_auto`). Klick auf DIVERSITY während
Auto = einfach `mode_changed` emit wie heute, Bandpilot-Logik greift.

## Architektur

### control_panel.py

`_on_rx_mode_clicked` (Z.1487+):
```python
def _on_rx_mode_clicked(self, mode: str):
    # Bundle G: wenn schon im Diversity-Modus + erneuter Div-Klick
    # → Sub-Mode-Toggle requesten (mw_radio entscheidet je nach
    # Bandpilot-Mode + aktuellem scoring)
    if mode == self._current_rx_mode:
        if mode == "diversity":
            self.diversity_subtoggle_requested.emit()
        return
    # ... bisherige Logik unverändert
```

Neues Signal: `diversity_subtoggle_requested = Signal()` (keine
Parameter — mw_radio holt Kontext selbst).

### mw_radio.py

Neuer Slot `_on_diversity_subtoggle_requested`:
```python
@Slot()
def _on_diversity_subtoggle_requested(self):
    """Bundle G: Toggle Std ↔ DX bei wiederholtem Div-Klick.

    Nur wirksam wenn Bandpilot=off (sonst entscheidet Bandpilot).
    Pipeline-Lock + Radio-Check wie bei _on_rx_mode_changed.
    """
    bp_mode = self.settings.get("bandpilot_mode", "off")
    if bp_mode != "off":
        return  # Bandpilot=Auto entscheidet, kein User-Toggle
    if getattr(self, '_gain_measure_locked', False):
        return  # Pipeline läuft, ignorieren
    if not self.radio.ip:
        return
    current = getattr(self._diversity_ctrl, 'scoring_mode', 'normal')
    new = "dx" if current == "normal" else "normal"
    self._activate_diversity_with_scoring(new)
```

Connect in `main_window.py`:
```python
self.control_panel.diversity_subtoggle_requested.connect(
    self._on_diversity_subtoggle_requested)
```

## Tests (geplant)

`tests/test_bundle_g.py`:
- T1: Klick auf Diversity während Std + Bandpilot=off → Slot ruft
  `_activate_diversity_with_scoring("dx")`
- T2: Klick auf Diversity während DX + Bandpilot=off → ruft
  `_activate_diversity_with_scoring("normal")` (scoring="normal" =
  Standard, scoring="dx" = DX — Naming aus Code-Base)
- T3: Klick auf Diversity während Std + Bandpilot=auto → kein Toggle
- T4: Klick auf Diversity während Std + radio.ip=None → kein Toggle
- T5: Klick auf Diversity während Std + Gain-Mess läuft → kein Toggle
- T6: Klick auf Normal während Div → bisheriger Pfad
  (`rx_mode_changed.emit("normal")`)
- T7: Signal-Emit-Verifikation aus control_panel

## Edge-Cases

- **Bandpilot pending Toast offen während Toggle:** Bandpilot cancelt
  sich selbst via existierende `_on_bandpilot_tx_finished`-Logik
  (Bundle E R1-F3 pending-Tupel 5-elementig mit current).
- **OMNI-CQ aktiv:** beim Toggle in `_activate_diversity_with_scoring`
  läuft `_on_rx_mode_changed`-Logik nicht direkt — OMNI bleibt aktiv,
  aber Pipeline-Reset über Cache-Check kann Mess auslösen. Sollte ich
  hier eigene OMNI-Stop-Logik einbauen? **R1-Frage.**
- **Bandwechsel mid-Toggle:** unwahrscheinlich (User klickt nicht
  gleichzeitig Band+Div), aber Race möglich. **R1-Frage.**

## Atomare Commits

| C | Datei | Inhalt |
|---|---|---|
| C1 | `ui/control_panel.py` | Signal + Toggle-Branch in `_on_rx_mode_clicked` |
| C2 | `ui/mw_radio.py` | `_on_diversity_subtoggle_requested`-Slot |
| C3 | `ui/main_window.py` | Signal-Connect |
| C4 | `tests/test_bundle_g.py` NEU | 7 Tests |
| C5 | APP_VERSION 0.97.23 → 0.97.24 + HISTORY/HANDOFF/CLAUDE + Plan-Files |

## Test-Bilanz

- Vor Bundle G: 1183 grün
- +7 Bundle G
- Erwartung: **~1190 grün**

## R1-Fragen (V2)

- Q1: Soll Toggle OMNI-CQ stoppen wie bei normalem RX-Mode-Wechsel
  (`_on_rx_mode_changed` Z.541)? Oder weiterlaufen lassen (Sub-Mode-
  Wechsel ist „weicher" als Modus-Wechsel)?
- Q2: Auto-Hunt analog wie bei OMNI?
- Q3: `_activate_diversity_with_scoring` durchläuft den ganzen
  Cache-Dispatch (`_check_diversity_preset`) — bei frischem Gain in
  DX-Store nach Toggle keine Mess nötig. Aber falls Gain in DX-Store
  fehlt: DXTuneDialog. Mike sieht das als Feature („mess wenn nötig")
  oder Bug („wollte schnell wechseln")? **Wahrscheinlich Feature
  weil Mike's W2 explizit Gain-Sharing fordert — würde W2 lösen.**
- Q4: Signal-Naming `diversity_subtoggle_requested` OK oder besser
  `diversity_scoring_toggle_requested`?
- Q5: Field-Test-Liste?

## Field-Test (V3)

- F1: Normal → Klick DIVERSITY → Dialog Std/DX → Wahl Std →
  Diversity Std aktiv (heute schon, Regression-Schutz)
- F2: Div Std → Klick DIVERSITY → **direkt → DX** ohne Dialog
- F3: Div DX → Klick DIVERSITY → **direkt → Standard** ohne Dialog
- F4: Bandpilot=Auto + Div-Klick → kein Toggle (Bandpilot kontrolliert)
- F5: Während Gain-Mess Div-Klick → ignoriert
