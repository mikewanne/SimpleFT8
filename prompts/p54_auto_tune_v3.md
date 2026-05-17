# P54 V3 — Final-Spec (post-R1)

## R1-Entscheidungen
- **F1 ROT** (`watt`-Schlüssel): **angenommen**. Speichere `watt=10`
  (nominale TUNE-Leistung), `rf=10` (Slider-Wert). FWDPWR nur
  Plausibilitäts-Check + Logging.
- **F2 ROT** (Doppel-Dialog): **angenommen**. `_tune_post_swr_check`
  unterdrückt QMessageBox.warning **wenn** `_auto_tune_running=True`.
  AutoTuneDialog übernimmt Fehler-Anzeige im Cancel-Pfad des Helpers.
- **F3 ORANGE** (Diversity-Resume): **angenommen**. Im Post-Check
  `_check_diversity_preset`-Call nur wenn nicht Auto-Tune-Mode.
- **F4 ORANGE** (Timeout-Cleanup): **angenommen**. AutoTuneDialog
  Timeout-Arm ruft `_tune_in_progress=False` UND `_auto_tune_running=False`
  über Helper-Slot.
- **F5 GELB** (Meter-Updates): **abgelehnt** — kein Fix nötig, GUI-Thread
  Re-Entry ist sauber.
- **F6 GELB** (Tests): **angenommen**. +5 Tests (Timeout, Cancel-Cleanup,
  Verbindungsverlust, Plausibilitäts-Grenzen exakt 2.0 und 80.0).

## Akzeptanzkriterien V3

**AC1** — `config/settings.py` DEFAULTS:
```python
"auto_tune_on_band_change": True,
```
`tune_duration_s` (P63) wird wiederverwendet.

**AC2** — `ui/auto_tune_dialog.py` NEU:
- `QDialog`, WindowModal, fixed-size 360×140.
- Titel-Label „🔧 Auto-Tune läuft".
- Spinner (rotierendes QLabel oder QProgressBar indeterminate).
- Status-Label „Band {band}: SWR {swr:.1f} | {sec}s".
- Cancel-Button rechts unten (klein, dezent).
- Signal `auto_tune_done(bool success, float swr, float avg_fwdpwr)`
  → von Helper getriggert.
- Backup-Timeout: `tune_duration_s + 5` s mit `_emit_timeout()`-Slot
  der `auto_tune_done(False, 0.0, 0.0)` emittiert + `reject()`.

**AC3** — Re-Entry-Schutz in `_on_band_changed` (V2-F3):
Am Anfang, nach `_gain_measure_locked`-Check, vor `_tune_token = None`:
```python
if getattr(self, '_tune_active', False):
    print(f"[Bandwechsel ignoriert: TUNE laeuft, bleibe auf {self.settings.band}]")
    self.control_panel._set_band(self.settings.band)
    return
```

**AC4** — Auto-Tune-Hook in `_on_band_changed`:
Position: NACH `_apply_rf_preset()` (Z.481), NACH `radio.set_frequency`
(Z.462), VOR `_maybe_apply_bandpilot` (Z.520).

```python
if (self.settings.get("auto_tune_on_band_change", True)
        and self.radio.ip
        and band.upper() not in self._swr_blocked_bands
        and self.settings.get("tuner_present", True)):
    self._start_auto_tune_for_band_change(band)
```

Bedingungen:
- Setting AN
- Radio verbunden
- Band nicht SWR-blockiert (Marker)
- Tuner vorhanden (`tuner_present`, P63)

**AC5** — Neuer Helper `_start_auto_tune_for_band_change(band: str) -> bool`
in `ui/mw_tx.py`:

```python
def _start_auto_tune_for_band_change(self, band: str) -> bool:
    """Auto-Tune nach Bandwechsel — modaler Dialog + 10W Tune + Save.

    Returns True bei Erfolg (SWR-good + Stuetzpunkt gespeichert),
    False bei Fail/Cancel/Timeout.
    """
    from ui.auto_tune_dialog import AutoTuneDialog
    from PySide6.QtCore import QTimer
    from config.settings import get_tune_freq_mhz

    duration_s = self.settings.get("tune_duration_s", 15)
    if duration_s not in (15, 30):
        duration_s = 15

    dialog = AutoTuneDialog(self, band=band, duration_s=duration_s)
    self._auto_tune_dialog = dialog  # für Signal-Routing
    self._auto_tune_running = True
    self._fwdpwr_samples.clear()  # V2-F4: alte Samples raus

    # Auto-Tune-Sequence (analog _on_tune_clicked)
    self._tune_in_progress = True
    tune_freq = get_tune_freq_mhz(band, self.settings.mode)
    self._tune_active = True
    if tune_freq is not None:
        self._tune_freq_mhz = tune_freq
        self.radio.set_frequency(tune_freq)
    else:
        self._tune_freq_mhz = self.settings.frequency_mhz
    self.radio.set_tx_antenna("ANT1")  # AC11 Hardware-Pflicht
    self.radio.set_rfpower_direct(10)
    self.radio.tune_on()
    print(f"[P54a] Auto-TUNE {band} 10W {duration_s}s")

    # Auto-Stop nach Dauer
    self._tune_auto_stop_token = object()
    _token = self._tune_auto_stop_token
    QTimer.singleShot(duration_s * 1000, lambda: self._tune_stop(_token))

    # dialog.exec() blockt bis auto_tune_done-Signal oder Cancel
    result = dialog.exec()
    self._auto_tune_running = False
    self._auto_tune_dialog = None
    return result == dialog.DialogCode.Accepted
```

**AC6** — FWDPWR-Sampling während TUNE (V1 AC5 + V2-F4):
In `_on_meter_update` FWDPWR-Branch:
```python
if name == "FWDPWR":
    self.control_panel.update_watt(value)
    if value > 1 and (self.encoder.is_transmitting or self._tune_active):
        self._fwdpwr_samples.append(value)
    # bestehender Block (Audio-Anzeige etc.) bleibt — encoder-only
    if self.encoder.is_transmitting and value > 1:
        raw_peak = self.radio.tx_raw_peak
        self.control_panel.update_tx_peak(...)
        ...
```

**AC7** — `_tune_post_swr_check` erweitern (R1-F1+F2+F3):
```python
def _tune_post_swr_check(self, token):
    if getattr(self, '_tune_post_check_token', None) is not token:
        return
    self._tune_in_progress = False
    if not self.radio.ip:
        # Auto-Tune: emit fail
        if self._auto_tune_running and self._auto_tune_dialog:
            self._auto_tune_dialog.auto_tune_done.emit(False, 0.0, 0.0)
        return

    swr_now = self.radio.last_swr
    swr_limit = self.settings.get("swr_limit", 3.0)
    band = self.settings.band.upper()

    # FWDPWR-Snapshot (P54b)
    samples = self._fwdpwr_samples[:]
    self._fwdpwr_samples.clear()
    avg_fwdpwr = (sum(samples) / len(samples)) if samples else 0.0

    is_auto = self._auto_tune_running  # F2: Mode-Switch fuer Dialog-Routing

    if swr_now <= swr_limit:
        was_blocked = band in self._swr_blocked_bands
        self._swr_blocked_bands.discard(band)

        # P54b: RFPreset-Stuetzpunkt bei plausiblem FWDPWR (R1-F1)
        if 2.0 < avg_fwdpwr < 80.0:
            self.rf_preset_store.save(
                self.radio.radio_type, self.settings.band, 10, 10
            )
            print(f"[P54b] RFPreset-Stuetzpunkt: {self.settings.band}_10W "
                  f"→ rf=10 (TUNE-FWDPWR avg {avg_fwdpwr:.1f}W)")
            # F1: _apply_rf_preset neu damit aktuelle Convergenz davon profitiert
            self._apply_rf_preset()
        elif samples:
            print(f"[P54b] Stuetzpunkt verworfen: FWDPWR avg {avg_fwdpwr:.1f}W "
                  f"out of [2..80]")

        if was_blocked:
            self.qso_panel.add_info(f"✓ Band {band} freigegeben — SWR {swr_now:.1f}")
            # F3: Diversity-Resume nur wenn NICHT Auto-Tune (Bandwechsel-Logik
            # macht das selbst)
            if not is_auto and self._rx_mode == "diversity":
                scoring = getattr(self._diversity_ctrl, 'scoring_mode', 'normal')
                ft_mode = self.settings.mode
                self._check_diversity_preset(self.settings.band, ft_mode, scoring)
        else:
            self.qso_panel.add_info(f"✓ TUNE OK — SWR {swr_now:.1f}")

        # F2: Signal-Routing fuer Auto-Tune (keine MessageBox)
        if is_auto and self._auto_tune_dialog:
            self._auto_tune_dialog.auto_tune_done.emit(True, swr_now, avg_fwdpwr)
    else:
        # AC7 P63: Marker bleibt rot
        if is_auto and self._auto_tune_dialog:
            # F2: Auto-Tune-Pfad — Dialog zeigt Fehler, kein QMessageBox
            self._auto_tune_dialog.auto_tune_done.emit(False, swr_now, avg_fwdpwr)
        else:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(
                self,
                "Tuner konnte nicht matchen",
                f"SWR weiter {swr_now:.1f} > Limit {swr_limit:.1f}.\n\n"
                "Antenne pruefen oder TUNE wiederholen."
            )
    print(f"[P63] Post-TUNE — SWR {swr_now:.1f}, Limit {swr_limit:.1f}")
```

**AC8** — AutoTuneDialog Cancel-/Timeout-Pfad (F4):
- Cancel-Button → `_on_cancel_clicked()`:
  ```python
  parent._tune_stop(None)
  parent._tune_in_progress = False  # F4: explicit cleanup
  self.reject()
  ```
- Backup-Timeout (`tune_duration_s + 5 s`) → `_on_timeout()`:
  ```python
  parent._tune_in_progress = False  # F4
  self.auto_tune_done.emit(False, 0.0, 0.0)  # selbst-trigger
  ```
- `auto_tune_done`-Slot im Dialog:
  ```python
  def _on_auto_tune_done(self, success: bool, swr: float, avg_fwdpwr: float):
      if success:
          self.accept()
      else:
          msg = (f"Auto-Tune fehlgeschlagen — SWR {swr:.1f}"
                 if swr > 0 else "Auto-Tune Timeout")
          # Status-Label setzen, 2s warten, dann reject
          self.status_label.setText(msg)
          QTimer.singleShot(2000, self.reject)
  ```

**AC9** — Caller-Verhalten nach Helper-Return:
```python
# in _on_band_changed:
success = self._start_auto_tune_for_band_change(band)
if not success:
    # Optional QMessageBox.warning oder add_info
    self.qso_panel.add_info(f"⚠ Auto-Tune {band}: fehlgeschlagen")
# Bandwechsel-Logik laeuft normal weiter (Bandpilot, Diversity-Preset)
```

**AC10** — Settings-Dialog Toggle in Tab „FT8 & Diversity":
neben `tuner_present_cb`:
```python
self.auto_tune_band_cb = QCheckBox("Auto-Tune bei Bandwechsel")
self.auto_tune_band_cb.setToolTip(
    "Nach jedem Bandwechsel automatisch TUNE (10 W, Dauer aus Setting)\n"
    "speichert RF-Stuetzpunkt fuer schnelle Sendeleistungs-Kalibrierung.")
form.addRow("", self.auto_tune_band_cb)
```
Load/Save/Reset analog `tuner_present_cb`.

**AC11** — Hardware-Pflicht ANT1:
`set_tx_antenna("ANT1")` explizit im Helper VOR `tune_on()` (AC5).

**AC12** — Tests (20 in `tests/test_p54_auto_tune.py`):
- T1: Setting `auto_tune_on_band_change` Default True.
- T2: `tune_duration_s` Whitelist {15, 30}.
- T3: `_on_band_changed` mit Setting=False → kein Auto-Tune-Helper-Call.
- T4: `_on_band_changed` mit `radio.ip=None` → silent skip.
- T5: `_on_band_changed` mit `band in _swr_blocked_bands` → skip.
- T6: `_on_band_changed` mit `tuner_present=False` → skip.
- T7: `_on_band_changed` mit allen Bedingungen erfüllt → Helper-Call.
- T8: `_tune_post_swr_check` mit valid FWDPWR (avg=9.5) + SWR-good →
  `rf_preset_store.save(radio, band, 10, 10)` (R1-F1 Schlüssel-Check!).
- T9: `_tune_post_swr_check` mit FWDPWR avg<2 → kein save (Plausibilität).
- T10: `_tune_post_swr_check` mit FWDPWR avg≥80 → kein save (R1-F6 Grenze).
- T11: `_tune_post_swr_check` SWR-bad → kein save (R1-F1).
- T12: Manueller TUNE (User-Klick) speichert ebenfalls.
- T13: FWDPWR-Sampling auch während `_tune_active` (nicht nur encoder).
- T14: `_tune_post_swr_check` Auto-Tune-Mode + SWR-good → emit
  `auto_tune_done(True, swr, avg)`, KEINE QMessageBox (R1-F2).
- T15: `_tune_post_swr_check` Auto-Tune-Mode + SWR-bad → emit
  `auto_tune_done(False, swr, avg)`, KEINE QMessageBox (R1-F2).
- T16: `_tune_post_swr_check` Auto-Tune-Mode + SWR-good → KEIN
  `_check_diversity_preset`-Call (R1-F3).
- T17: AutoTuneDialog Cancel → `_tune_in_progress=False` (R1-F4).
- T18: AutoTuneDialog Timeout-Backup nach `tune_duration_s + 5`s
  → emit fail (R1-F6).
- T19: `_on_band_changed` mit `_tune_active=True` → ignored
  (V2-F3 Re-Entry-Schutz).
- T20: Auto-Tune-Erfolg → `_apply_rf_preset()` wird **erneut** gerufen
  nach Save (V2-F1).
- T21: Verbindungsverlust während Auto-Tune (`radio.ip=None` in
  Post-Check) → silent fail (R1-F6).
- T22: Plausibilitäts-Grenze exakt 2.0 → kein save (Grenze
  inklusive `2.0 < avg`).
- T23: Plausibilitäts-Grenze exakt 80.0 → kein save (Grenze
  `avg < 80.0`).

## Atomare Commits
- C1: Backup `Appsicherungen/2026-05-16_v0.97.43_vor_p54/`.
- C2: `config/settings.py` DEFAULTS-Eintrag.
- C3: `ui/settings_dialog.py` Toggle einbauen.
- C4: `ui/auto_tune_dialog.py` NEU.
- C5: `ui/mw_tx.py` FWDPWR-Sampling + `_tune_post_swr_check`-Erweiterung
  + Helper `_start_auto_tune_for_band_change`.
- C6: `ui/mw_radio.py` Hook in `_on_band_changed` + Re-Entry-Schutz.
- C7: `tests/test_p54_auto_tune.py` (23 Tests).
- C8: `main.py` APP_VERSION 0.97.43 → 0.97.44.
- C9: HISTORY+HANDOFF+CLAUDE+Memory.

## Field-Test (Mike, mit Radio)
- F1: Bandwechsel 20m→40m → Dialog 15 s → close bei SWR-good. Preset
  gespeichert (Console-Log).
- F2: Bandwechsel auf SWR-Block-Band → kein Dialog.
- F3: Bandwechsel mit Antennen-Mismatch → Dialog → Timeout/Fail →
  Marker setzt, Status „fehlgeschlagen", kein Crash.
- F4: Setting `auto_tune_on_band_change=False` → kein Dialog.
- F5: Mode-Wechsel FT8↔FT4 → kein Auto-Tune.
- F6: Erstes QSO nach Auto-Tune startet schneller (rf=10 als Startwert
  statt 50% Default).
- F7: Cancel-Button → Dialog schließt, Marker bleibt, kein Save.
- F8: Manueller TUNE → speichert ebenfalls Stützpunkt (Console-Log).
