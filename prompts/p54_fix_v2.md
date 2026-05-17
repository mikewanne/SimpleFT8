# P54-FIX V2 — Self-Review (vor R1)

## V1-Halluzinations-Check ✓
- `_auto_adjust_tx_level` (Z.444), `_fwdpwr_samples`, `_apply_rf_preset`
  (Z.42), `_tune_post_swr_check` (Z.163), `_start_auto_tune_for_band_change`
  (Z.269), `_on_tune_clicked` (Z.66), `RFPresetStore.get_all` (Z.173),
  `RFPresetStore.load` (Z.105) — alle vorhanden, Zeilennummern verifiziert.
- `_tune_active`-Flag bereits in `_on_meter_update` für FWDPWR-Sampling
  berücksichtigt (P54-AC6).
- `set_rfpower_direct(value)` in `flexradio.py:909` setzt Slider direkt
  ohne `max_power_level`-Reset. Geeignet für Closed-Loop-Iterationen.

## V2-Findings

### V2-F1 (KRITISCH) — Cancel-Race während Convergenz

**Wurzel:** `_tune_converge_to_target` läuft synchron mit `QEventLoop.exec()`.
Wenn User währenddessen Cancel-Button im AutoTuneDialog klickt
(`_on_cancel_clicked` ruft `reject()`), bleibt die Convergenz-Schleife
in `_tune_converge_to_target` aktiv → Slider wird weiter angepasst →
inkonsistenter Hardware-State nach Cancel.

**Fix:** State-Flag `_tune_convergence_cancelled: bool = False` in
MainWindow. Cancel-Pfad setzt `True`. Convergenz-Schleife prüft am
Anfang jeder Iteration und returnt early. AutoTuneDialog `_on_cancel_clicked`
und `_on_backup_timeout` setzen das Flag.

```python
# Am Anfang jeder Iteration:
if getattr(self, "_tune_convergence_cancelled", False):
    return None  # Convergenz abgebrochen
```

### V2-F2 (Risiko) — QEventLoop + reentrant Slots

`QEventLoop.exec()` läuft Sub-Event-Loop, andere Slots können
re-entrant feuern (z.B. SWR-Alarm). Aber: `_tune_in_progress=True`
bypassed SWR-Watchdog (P63 AC4). Andere Slots: `_on_meter_update`
füllt nur `_fwdpwr_samples` — kein State-Konflikt.

**Akzeptiert:** kein Fix, aber Test T-Race muss reentrant SWR-Alarm
simulieren um Schutz zu verifizieren.

### V2-F3 (Risiko) — `_fwdpwr_samples` Konflikt zwischen Convergenz und Closed-Loop

Sowohl `_tune_converge_to_target` als auch `_auto_adjust_tx_level`
nutzen `_fwdpwr_samples`. Während TUNE läuft kein QSO-Closed-Loop
(`encoder.is_transmitting=False`). Nach TUNE-Ende `_tune_active=False`
→ Sampling stoppt automatisch. Kein Konflikt.

**Akzeptiert:** kein Fix.

### V2-F4 (Verbesserung) — Phase A vs. Phase B Timing

V1 sagt: Phase A = 2/3 von `tune_duration_s`, Phase B = 1/3. Bei
15s: 10s Match + 5s Convergenz.

Bei `tune_duration_s = 30`: 20s Match + 10s Convergenz. 10s Convergenz
ist genug für Max-Iterations (5×1s + Initial-Sample = 6s).

**Klarstellung in V3:** Phase B = `min(5s, tune_duration_s × 1/3)` →
bei 15s = 5s, bei 30s auch 5s (nicht 10s). 5s reicht für 5 Iterationen.

### V2-F5 (Risiko) — Convergenz mit FWDPWR=0 (Radio antwortet nicht)

Wenn `_fwdpwr_samples` nach 1s Initial-Wait leer ist, returnt
Convergenz None. `_tune_post_swr_check` muss damit umgehen:

```python
rf_to_save = (self._tune_converged_rf
              if self._tune_converged_rf is not None
              else 10)  # Fallback hart
```

**Klarstellung in V3:** `_tune_converged_rf` ist `Optional[int]`, wird
in `_tune_stop` oder `_tune_converge_to_target` gesetzt, in
`_tune_post_swr_check` ausgelesen.

### V2-F6 (KRITISCH) — Krücken-Skalierung darf nicht für 10W feuern

`_apply_rf_preset` ruft `_kruecken_skalierung(band, watts)` wenn
`load()` None returnt. ABER: nach TUNE haben wir einen exakten
10W-Stützpunkt → `load(band, 10W)` returnt direkt → Krücke wird gar
nicht erreicht. ✓

Edge-Case: was wenn Mike auf `_power_target = 10W` setzt aber kein
10W-Stützpunkt vorhanden (z.B. Krücke aus altem Wert)? `load()` returnt
None → Krücke greift → linear vom einzigen Stützpunkt. Sinnvoll.

**Akzeptiert.**

### V2-F7 (Verbesserung) — Krücken-Skalierung-Logging

V1 hat print mit `linear x0.9`-Annotation. Klarstellung in V3: auch
Anker-Watt + Anker-RF im Log damit Mike die Berechnung nachvollziehen
kann:

```python
print(f"[RF-Preset] Krücke: {band}_{watts}W → rf={krucke} "
      f"(Anker {anchor_watt}W=rf{anchor_rf}, linear×0.9)")
```

### V2-F8 (Risiko) — Convergenz konvergiert auf falschen Wert

Wenn FWDPWR-Sampling während Phase B nur ein Sample hat (Meter-Update
langsam), könnte Mittelwert volatil sein → Convergenz schwingt
ein-zwei Iterationen unnötig.

**Mitigation:** Initial-Sample-Phase 1.5s statt 1s (wir warten initial
etwas länger um >2 Samples zu sammeln). Mindest-Sample-Count vor
erstem Adjust = 2.

**Klarstellung in V3:** Inkludieren.

### V2-F9 (KRITISCH) — `set_power` nach Convergenz NÖTIG

Wie beim P54-Final-R1-ROT-Bug: nach Convergenz wird `_rfpower_current`
nicht durch unsere Hardware-State synchronisiert. `_apply_rf_preset`
wird in `_tune_post_swr_check` AC3-Bestand bereits aufgerufen — dort
muss `set_power` folgen (existiert bereits aus P54-Final-R1).

**Verifizieren:** in `_tune_post_swr_check` ist nach
`_apply_rf_preset()` ein `radio.set_power(_rfpower_current)`-Call.
Source-Check.

### V2-F10 (Verbesserung) — Test T-Race + T-Cancel ergänzen

V1 hat T1-T14. Ergänzen:
- T15: Cancel während Convergenz → Schleife bricht ab, `_tune_converged_rf
  = None`, `_tune_post_swr_check` speichert Fallback rf=10.
- T16: Re-entrant SWR-Alarm während Convergenz (sollte via
  `_tune_in_progress` bypassed sein).

## V2-Empfehlungen für V3

1. AC1 erweitern: Cancel-Flag-Check am Anfang jeder Iteration (V2-F1).
2. AC1 ändern: Initial-Sample-Phase = 1.5s, Mindest-Sample-Count = 2
   (V2-F8).
3. AC3 präzisieren: `_tune_converged_rf` State-Var, Optional[int]
   (V2-F5).
4. AC4 Log-Format erweitern (V2-F7).
5. AC5 verifizieren `set_power`-Aufruf in `_tune_post_swr_check`
   (V2-F9).
6. AC8 Tests +2: T15 Cancel-Race, T16 SWR-Watchdog-Bypass-Check
   (V2-F10).
7. Phase B = max 5s (nicht 1/3 von duration_s, V2-F4).
