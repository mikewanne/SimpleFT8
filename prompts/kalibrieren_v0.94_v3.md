# v0.94 Implementations-Plan (V2-Self-Review + V3-Synthese)

## V2-Findings (was V1 übersehen hat)

### Finding 1: Cancel-Pfad bei KALIBRIEREN-Erweiterung
Wenn `_handle_dx_tuning` aufgerufen wird mit `_pending_dx_diversity = True`
und der User in der DXTune-Pipeline "Abbrechen" klickt → `_on_dx_tune_cancelled`
muss `_pending_dx_diversity = False` setzen, sonst läuft beim nächsten
Trigger ungewollt Phase 3.

### Finding 2: Reihenfolge `_on_cycle_decoded`
RX-Panel-Fix muss VOR den modus-spezifischen Handlern greifen:
```python
if self._dx_tune_dialog is not None:
    self._handle_dx_tune_mode(messages)  # zeigt Hardware-Antenne
    if self._dx_tune_dialog is not None:
        self._dx_tune_dialog.feed_cycle(messages)  # bucht in _phase_data
    # Stats-Logging übersprungen via _is_antenna_tuning_active()
    return
# Sonst Standard-Pfade...
```
Aktuell läuft `feed_cycle` UND `_handle_diversity_operate` parallel.
Mit early-return ist nur DXTune-Pfad aktiv während Phase 2.

ABER: `_handle_diversity_operate` macht auch wichtige Dinge wie
`_feed_locator_db`, `_feed_rx_history`, `accumulate_stations`. Wenn wir
das skippen, fehlen Locators/RX-History für 2 Min.

**Entscheidung:** NICHT early-return. Stattdessen:
- `_is_antenna_tuning_active` blockt Stats-Schreiben (Bug A behoben)
- `_handle_dx_tune_mode` läuft NICHT parallel zu `_handle_diversity_operate`
  (sonst doppelte msg.antenna-Zuweisung)
- Stattdessen: `_handle_diversity_operate` MIT korrekter Hardware-Antenne
  aus `_schedule[_step]` aufrufen wenn Dialog aktiv

→ **Saubere Lösung:** in `_on_cycle_decoded` Helper `_get_active_antenna()`
der wenn Dialog aktiv die Hardware-Antenne aus `_schedule[_step]` liest,
sonst `_pop_diversity_queue()` Wert. Dann `_handle_diversity_operate`
mit dieser Antenne aufrufen.

### Finding 3: Tests-Strategie
- **Stats-Pause Phase 2:** Whitebox-Test `_is_antenna_tuning_active`
  mit `_dx_tune_dialog = MagicMock()` → returns True
- **KALIBRIEREN-Erweiterung:** Whitebox `_handle_dx_tuning` mit
  `_rx_mode = "diversity"` → setzt `_pending_dx_diversity = True`
- **RX-Panel-Antenne:** Whitebox `_on_cycle_decoded` mit
  `_dx_tune_dialog = MagicMock()` → `accumulate_stations` mit ANT-Form

### Finding 4: `_handle_dx_tune_mode` Robustheit
Aktuelle Logik liest `_schedule[_step]` mit try/except IndexError. Wenn
`_step >= len(_schedule)` (Phase 2 fertig, Dialog noch nicht geschlossen)
→ default "A1" — aber das ist falsch wenn Dialog gerade noch sichtbar
ist. KISS: try/except bleibt, default "A1" akzeptabel da Dialog gleich
schließt.

### Finding 5: `_pending_dx_diversity` Lifecycle
Aktuell wird das Flag in `_activate_diversity_with_scoring` gesetzt
(Z.566) und verwendet in `_on_dx_tune_accepted` für Phase-3-Trigger.
Mike's Erweiterung in `_handle_dx_tuning` setzt das Flag identisch —
gleicher Mechanismus, kein neues Feld nötig. ✅

---

## V3 — Atomare Commits

### Commit 1: Stats-Bug Phase 2 fixen
**File:** `ui/mw_cycle.py:633-648`
```python
def _is_antenna_tuning_active(self) -> bool:
    if not getattr(self.radio, 'ip', None):
        return True
    if self._rx_mode == "dx_tuning":
        return True
    # v0.94 Bug-Fix: Phase 2 (DXTuneDialog) blockt Stats
    if getattr(self, '_dx_tune_dialog', None) is not None:
        return True
    if (self._rx_mode == "diversity"
            and hasattr(self, '_diversity_ctrl')
            and self._diversity_ctrl is not None
            and self._diversity_ctrl.phase == "measure"):
        return True
    return False
```
**Tests:** +2 in test_modules.py (Phase 2 blockt Stats, Phase 2 weg → entblockt)

### Commit 2: RX-Panel zeigt Hardware-Antenne in Phase 2
**File:** `ui/mw_cycle.py` `_on_cycle_decoded` + `_handle_diversity_operate`
**Strategie:** Helper `_get_active_antenna(diversity_pop_ant)` der bei
aktivem Dialog Hardware-Antenne aus `_schedule[_step]` liest und in das
RX-Panel/`accumulate_stations`-Format ("A1"/"A2") konvertiert.
```python
def _get_active_antenna(self, default_ant: str) -> str:
    if self._dx_tune_dialog is not None:
        try:
            ant, _gain = self._dx_tune_dialog._schedule[
                self._dx_tune_dialog._step]
            return "A1" if ant == "ANT1" else "A2"
        except (IndexError, AttributeError):
            pass
    return default_ant
```
Dann in `_on_cycle_decoded` wenn diversity: `ant = self._get_active_antenna(ant)`
**Tests:** +2 in test_phase2_antenna_display.py (NEU)

### Commit 3: KALIBRIEREN-Button RX-Modus-spezifisch
**File:** `ui/mw_radio.py:1079-1083` `_handle_dx_tuning`
```python
def _handle_dx_tuning(self):
    """KALIBRIEREN-Button: Pipeline je nach RX-Modus.

    - Normal: nur Phase 2 (Gain).
    - Diversity Standard/DX: Phase 2 + Phase 3 + Cache + Timer-Reset.
    """
    if self._rx_mode == "diversity":
        scoring = getattr(self._diversity_ctrl, 'scoring_mode', 'normal')
        gain_scoring = "snr" if scoring == "dx" else "stations"
        self._pending_dx_diversity = True
        self._pending_diversity_scoring = scoring
        self._start_dx_tuning(scoring_mode=gain_scoring)
    else:
        # Normal: nur Phase 2
        self._start_dx_tuning(scoring_mode="stations")
```
**Plus Cancel-Pfad:** `_on_dx_tune_cancelled` (wenn existent) setzt
`_pending_dx_diversity = False`. Wenn nicht existent: pruefen wo
`_dx_tune_dialog.cancel` behandelt wird.
**Tests:** +3 Whitebox via MagicMock-self

### Commit 4: Doku-Sync v0.94
- main.py 0.93 → 0.94
- HISTORY.md v0.94-Eintrag
- HANDOFF.md beide Pfade
- CLAUDE.md beide Pfade
- Memory v0.94 + Cleanup v0.93-Memory

---

## Akzeptanzkriterien

1. ✅ `_is_antenna_tuning_active()` returns True wenn DXTuneDialog aktiv
2. ✅ Stats werden während Phase 2 NICHT in `statistics/` geschrieben
3. ✅ RX-Panel zeigt während Phase 2 Hardware-Antenne (ANT1/ANT2 als
   "A1"/"A2") aus `_schedule[_step]`
4. ✅ KALIBRIEREN im Diversity-Modus startet Phase 2 + Phase 3
5. ✅ KALIBRIEREN im Normal-Modus startet nur Phase 2
6. ✅ Cancel in Phase 2 setzt `_pending_dx_diversity = False`
7. ✅ Tests +7-8 grün, Suite 729 → ~737

## Erwarteter Aufwand
~45 Min: 4 Commits + Tests + Doku-Sync.
