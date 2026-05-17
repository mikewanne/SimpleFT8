# P54 V2 — Self-Review (vor R1)

## V1-Halluzinations-Check ✓
Alle Methodennamen, Attribute, Zeilennummern verifiziert per grep.
Keine Halluzinationen.

## V2-Findings

### V2-F1 (KRITISCH) — RFPreset nach Auto-Tune nochmal laden
V1 AC3 sagt Hook NACH `_apply_rf_preset()`. Aber: nach erfolgreichem
Auto-Tune ist der 10-W-Stützpunkt **neu gespeichert** — der zuvor
geladene `_rfpower_current` ist noch der alte (oder 50% Default).

**Fix:** Im Auto-Tune-Success-Pfad `_apply_rf_preset()` ein **zweites
Mal** aufrufen NACH `rf_preset_store.save()`. Damit profitiert die
nächste TX-Konvergenz sofort vom frischen Stützpunkt.

### V2-F2 (Risiko) — `_tune_in_progress`-Cleanup bei Cancel
`_tune_in_progress=True` blockiert Watchdog. Wird erst in
`_tune_post_swr_check` auf False gesetzt. Wenn User Cancel klickt
oder Auto-Tune-Dialog Timeout-Backup feuert, läuft
`_tune_post_swr_check` evtl. nicht (Token rotiert via `_tune_stop`).

**Fix:** Cancel-Pfad muss `_tune_in_progress = False` explizit setzen.
Reihenfolge bei Cancel: `_tune_stop(None)` → `_tune_in_progress=False`
→ Dialog.reject().

### V2-F3 (KRITISCH) — Re-Entry-Schutz bei aktivem TUNE
`_on_band_changed` hat keinen Schutz wenn `_tune_active=True`.
Mike könnte während manuellem TUNE versehentlich das Band wechseln →
Auto-Tune würde mid-tune neu starten → State-Korruption.

**Fix:** Am Anfang von `_on_band_changed` (analog `_gain_measure_locked`
Z.389):
```python
if getattr(self, '_tune_active', False):
    print(f"[Bandwechsel ignoriert: TUNE laeuft, bleibe auf {self.settings.band}]")
    self.control_panel._set_band(self.settings.band)
    return
```

### V2-F4 (Risiko) — FWDPWR-Sample-Race
`_fwdpwr_samples` kann alte Werte aus vorherigem QSO enthalten wenn
`_apply_rf_preset` clearte aber TX zwischen Clear und Bandwechsel
lief. Bei Auto-Tune-Trigger könnten die ersten Samples alte QSO-
Werte sein.

**Fix:** Auto-Tune-Helper ruft `_fwdpwr_samples.clear()` **direkt**
vor `tune_on()`. Bestehender `_apply_rf_preset`-Clear (Z.480 in
`_on_band_changed`) bleibt — doppelt = nicht schädlich.

### V2-F5 (KRITISCH) — Signal-Routing AutoTuneDialog
V1 AC7 schlägt `auto_tune_finished` als neues Signal vor — wo lebt es?
Wenn auf `MainWindow` oder `mw_tx`, muss `_tune_post_swr_check` es nur
emittieren wenn Auto-Tune läuft (Flag `_auto_tune_running`).

**Fix:** Neue State-Variable `self._auto_tune_running: bool = False` in
`main_window.__init__`. Im Auto-Tune-Helper auf True, bei Success/Fail/
Cancel auf False zurück. `_tune_post_swr_check` emittiert
`auto_tune_finished` nur wenn Flag True. Signal auf `MainWindow` als
`Signal(bool, float, float)`.

### V2-F6 (Risiko) — `exec()` Modal in `_on_band_changed`
`QDialog.exec()` startet Sub-Event-Loop. Decoder-Thread läuft weiter
(eigener Thread), aber GUI-Signals werden gepoolt. Das ist OK — Timer
laufen, Meter-Updates kommen an, `_tune_post_swr_check` läuft.

ABER: andere Slots in der gleichen Klasse (z. B. `_on_meter_update`)
können während `exec()` re-entrant aufgerufen werden. Tests müssen
das nicht echt simulieren — Mock `exec()` returnt sofort, Logic-
Check via Direct-Call der Slots.

### V2-F7 (Verbesserung) — Helper statt Refactor
V1 AC4 schlägt `_on_tune_clicked` Refactor vor. **Abgelehnt** — zu
invasiv. Stattdessen: neuer Helper
`_start_auto_tune_for_band_change(band) -> bool` in `mw_tx.py`, der:
1. Setzt `self._auto_tune_running = True`.
2. Öffnet `AutoTuneDialog`.
3. Ruft die **gleichen** Steps wie `_on_tune_clicked(True)`-`if on:`-Block
   (TUNE_POWER_W=10, ANT1, set_rfpower_direct, tune_on, QTimer.singleShot).
4. Connect `auto_tune_finished` an Dialog-Slot.
5. `dialog.exec()` blockt bis Signal oder Cancel.
6. Bei Success: `_apply_rf_preset()` neu + return True.
7. Bei Fail/Cancel: QMessageBox.warning + return False.

Manueller TUNE-Pfad (`_on_tune_clicked`) bleibt unverändert — nur
der Save-Hook in `_tune_post_swr_check` ist gemeinsam.

### V2-F8 (Klärung) — `_swr_blocked_bands` Key-Format
P63 nutzt `band.upper()` im Set. Mein V1 AC3 macht `band.upper() in
self._swr_blocked_bands` — korrekt. ✓

### V2-F9 (Risiko) — App-Start ohne Radio
Beim App-Start ist `radio.ip=None`. `_on_band_changed` läuft (via
`_set_band` Init) → AC3 Check `if radio.ip` greift → silent skip.
Erster Bandwechsel **NACH** Connect triggert dann Auto-Tune.

Das ist OK, aber User sollte beim Connect-Modal-Close NICHT sofort
unerwartet ein 15-s-Auto-Tune sehen. Spec sagt: nur bei explizitem
User-Bandwechsel triggern. Beim Connect-Done läuft kein
`_on_band_changed`-Callback (verifiziert grep `_on_band_changed`-
Aufrufer — nur ControlPanel-Signal). ✓

### V2-F10 (Verbesserung) — Mike-Workflow
Mike will autonomen Workflow ohne Rückfragen. V2 deckt die offenen
Fragen ab — V3 kann mit R1-Findings direkt finalisiert werden.

## V2-Empfehlungen für V3
1. **AC3 ergänzen:** Re-Entry-Schutz `_tune_active` am Anfang von
   `_on_band_changed`.
2. **AC4 streichen:** Refactor `_on_tune_clicked` nicht nötig. Neuer
   Helper `_start_auto_tune_for_band_change`.
3. **AC6 erweitern:** `_apply_rf_preset()` nochmal aufrufen nach Save.
4. **AC7 präzisieren:** State-Var `_auto_tune_running` in MainWindow,
   Signal-Emit nur wenn True. Cleanup bei Cancel/Fail.
5. **AC11 erweitern:** Cancel-Pfad ruft `_tune_in_progress = False`
   und `_auto_tune_running = False` explizit.
6. **AC12 Tests:** T16 NEU — Re-Entry-Schutz `_tune_active` ignoriert
   Bandwechsel.
