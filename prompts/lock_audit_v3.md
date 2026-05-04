# Lock-Coverage-Audit (V3 — Final + Implementierungsplan)

## R1-Findings (zusammengefasst)

### KRITISCH (Must-Have, alle adressiert)

| # | Befund | R1-Schweregrad |
|---|---|---|
| 1 | Bandwechsel-Race durch Phase-Check-Bypass via `reset()` | **KRITISCH** (bestätigt) |
| 2 | Mode-Wechsel-Race (asynchrone Pipeline-Trigger) | mittel |
| 3 | Race-Window in `_enable_diversity` (Lock spaet) | mittel |
| 4 | **NEU: `_on_rx_mode_changed` braucht auch Lock-Check** | mittel |

### Nicht relevant (R1 explizit begruendet)

- **Geister-Slots in Operate** — Phase-Check filtert korrekt, station_accumulator ist beabsichtigt
- **R1's btn_rx-Vorschlag** — Code-Verifikation: kein btn_rx in `control_panel.py`. R1-Halluzination.
- **Bandpilot-Pending** — Optional, fuer Hobby-Use unnoetig (KISS)

## V3-Aenderungen vs V2

1. R1 entdeckte `_on_rx_mode_changed` als 3. ungeschuetzten Handler → in V3 mit drin
2. R1's `btn_rx` ignoriert (existiert nicht — V4-Auswertung)
3. V3 explizit gegen Bandpilot-Pending (KISS)
4. V3 als Plan-Datei (nicht mehr Auftrag)

## Implementierungsplan (atomare Commits)

### Commit 1: feat(lock): Pipeline-Lock bulletproof

**Datei:** `ui/mw_radio.py`

**Aenderungen:**

1. `_set_gain_measure_lock(self, locked: bool)` (Z.1080) — Flag setzen
   ```python
   def _set_gain_measure_lock(self, locked: bool):
       self._gain_measure_locked = locked  # NEU: einzige Quelle der Wahrheit
       # ... rest unveraendert
   ```

2. `_on_band_changed(self, band: str)` (Z.265) — Frueh-Return
   ```python
   @Slot(str)
   def _on_band_changed(self, band: str):
       if getattr(self, '_gain_measure_locked', False):
           current = self.settings.band
           print(f"[Bandwechsel ignoriert: Pipeline laeuft, bleibe auf {current}]")
           self.control_panel._set_band(current)  # UI-Sync zurueck
           return
       # ... rest unveraendert
   ```

3. `_on_mode_changed(self, mode: str)` (Z.199) — Frueh-Return
   ```python
   @Slot(str)
   def _on_mode_changed(self, mode: str):
       if getattr(self, '_gain_measure_locked', False):
           current = self.settings.mode
           print(f"[Mode-Wechsel ignoriert: Pipeline laeuft, bleibe auf {current}]")
           self.control_panel._set_mode(current)
           return
       # ... rest unveraendert
   ```

4. `_on_rx_mode_changed(self, mode: str)` (Z.371) — Frueh-Return
   ```python
   @Slot(str)
   def _on_rx_mode_changed(self, mode: str):
       if getattr(self, '_gain_measure_locked', False):
           current = getattr(self, '_rx_mode', 'normal')
           print(f"[RX-Mode-Wechsel ignoriert: Pipeline laeuft, bleibe auf {current}]")
           # UI-Sync: zurueck auf aktuellen Modus
           if hasattr(self.control_panel, 'set_rx_mode'):
               self.control_panel.set_rx_mode(current)
           return
       # ... rest unveraendert
   ```

5. `_enable_diversity` (Z.811-813) — Reihenfolge umkehren (Befund 3)
   ```python
   # ALT:
   # self._diversity_ctrl.reset()        # Z.811
   # self._set_cq_locked(True)
   # self._set_gain_measure_lock(True)   # Z.813

   # NEU:
   self._set_cq_locked(True)
   self._set_gain_measure_lock(True)   # Lock VOR Reset
   self._diversity_ctrl.reset()
   ```

**Tests neu (`tests/test_lock_coverage.py`):**

```python
def test_lock_flag_set_when_locked()
    # _set_gain_measure_lock(True) → _gain_measure_locked == True
    
def test_lock_flag_cleared_when_unlocked()
    # _set_gain_measure_lock(False) → _gain_measure_locked == False

def test_band_change_blocked_during_lock()
    # _gain_measure_locked=True, _on_band_changed("20m") → settings.band unchanged
    
def test_mode_change_blocked_during_lock()
    # _gain_measure_locked=True, _on_mode_changed("FT4") → settings.mode unchanged

def test_rx_mode_change_blocked_during_lock()
    # _gain_measure_locked=True, _on_rx_mode_changed("normal") → _rx_mode unchanged

def test_band_change_passes_when_unlocked()
    # _gain_measure_locked=False, _on_band_changed("20m") → settings.band == "20m"

def test_enable_diversity_lock_before_reset()
    # _enable_diversity ruft Lock vor reset → kein Race-Window
    # (Verifikation via Mock-Reihenfolge)
```

**Tests-Erwartung:** 675 → 682 (+7).

### Commit 2: docs: v0.92 Release-Sync — Pipeline-Lock-Audit

- main.py: APP_VERSION 0.91 → 0.92
- HISTORY.md: v0.92-Eintrag mit Audit-Trace
- HANDOFF.md (×2): Bandwechsel-Race als ✅ ERLEDIGT
- CLAUDE.md (×2): Aktueller Stand v0.92, Test-Count 682
- TODO.md: Race-Punkt entfernt
- Memory: Bandwechsel-Race-Memory aufloesen, Lesson hinzufuegen

## Reihenfolge

1. Pre-Flight: 675 Tests gruen (verifizieren)
2. Commit 1: Code + Tests in einem atomaren Commit (v0.90/v0.91-Konvention)
3. Commit 2: Doku-Sync v0.92

## Was V3 NICHT macht

- Bandpilot-Pending-Mechanismus (R1 optional, KISS sagt nein)
- btn_rx-Schutz (R1 spekuliert, existiert nicht)
- Token-Pattern (R1's Original-Vorschlag — durch Lock-Coverage hinfaellig)
- Andere Code-Abschnitte refactoren

## Status

- V1: ✅
- V2: ✅
- R1: ✅
- V3: ✅
- **Code:** als naechster Schritt (Mike autonom autorisiert)
