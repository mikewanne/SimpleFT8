# P54-FIX V3 — Final-Spec (post-R1)

## R1-Entscheidungen
- **F1 ROT** (`set_power` nach `_apply_rf_preset`): **angenommen**.
- **F2 ROT** (Cancel-Race): **angenommen**, `_tune_convergence_cancelled`-Flag.
- **F3 ROT** (`_tune_converged_rf` Init): **angenommen**, in `__init__`.
- **F4 ROT** (harte Save): **angenommen**, ist Mike's Kern-Spec.
- **F5 ORANGE** (Plausibilität rf ∈ [3, 50]): **angenommen**.
- **F6 ORANGE** (SWR-Check vor Phase B): **angenommen**.
- **F7 GELB** (Timer-Aufteilung): präzisiert in AC.
- **F8 GELB** (Krücke mit anchor_rf=0): bereits abgefangen.
- **F9 GELB** (Test `_tune_converged_rf is None`): in T-Liste.

## Akzeptanzkriterien V3

**AC1 — Helper `_tune_converge_to_target`**

Synchrone Closed-Loop-Convergenz mit `QEventLoop`:

```python
from PySide6.QtCore import QEventLoop, QTimer
from PySide6.QtWidgets import QApplication

def _tune_converge_to_target(self, target_w: int = 10,
                              max_iterations: int = 5,
                              iter_ms: int = 1000) -> int | None:
    """P54-FIX AC1: Closed-Loop bis FWDPWR ≈ target_w.

    Voraussetzung: TUNE läuft (radio.tune_on() + _tune_active=True),
    Phase A (Tuner-Match) ist fertig, SWR stabil.

    Returns konvergierter rfpower (1-100) oder None bei Fail/Cancel.
    """
    if not self.radio.ip:
        return None

    TOLERANCE_W = 1.0
    MIN_SAMPLES = 2
    self._tune_convergence_cancelled = False

    rf_current = 10  # Startwert (gleicher Slider wie Phase A)
    self.radio.set_rfpower_direct(rf_current)
    self._fwdpwr_samples.clear()

    # Initial-Sample-Phase: 1.5s sammeln vor erstem Adjust (V2-F8)
    self._wait_with_event_loop(1500)

    for iteration in range(max_iterations):
        # F2 ROT: Cancel-Flag prüfen
        if self._tune_convergence_cancelled:
            return None

        # Mindest-Sample-Count (V2-F8)
        if len(self._fwdpwr_samples) < MIN_SAMPLES:
            self._wait_with_event_loop(iter_ms)
            continue

        samples = list(self._fwdpwr_samples)
        self._fwdpwr_samples.clear()
        fwdpwr = sum(samples) / len(samples)

        if abs(fwdpwr - target_w) <= TOLERANCE_W:
            print(f"[P54-FIX] Convergenz: rf={rf_current} → FWDPWR≈{fwdpwr:.1f}W "
                  f"(Iter {iteration+1}/{max_iterations})")
            return rf_current

        # Proportionale Anpassung (analog _auto_adjust_tx_level)
        if fwdpwr > 0.5:
            estimated = int(rf_current * (target_w / fwdpwr))
            step = max(1, min(15, abs(estimated - rf_current)))
            if fwdpwr < target_w:
                rf_current = min(100, rf_current + step)
            else:
                rf_current = max(1, rf_current - step)
            self.radio.set_rfpower_direct(rf_current)
            print(f"[P54-FIX] Iter {iteration+1}: FWDPWR={fwdpwr:.1f}W "
                  f"target={target_w}W → rf={rf_current}")
            self._wait_with_event_loop(iter_ms)
        else:
            print(f"[P54-FIX] Iter {iteration+1}: FWDPWR≈0 — kein Signal")
            return None

    # Max-Iterations: best-effort letzten Wert
    print(f"[P54-FIX] Max-Iter erreicht — best-effort rf={rf_current}")
    return rf_current


def _wait_with_event_loop(self, ms: int):
    """Synchrones Warten mit aktivem Qt-Event-Loop (Meter-Updates kommen an)."""
    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()
```

**AC2 — State-Variablen in `MainWindow.__init__`** (F3 ROT):

```python
# P54-FIX (v0.97.45):
self._tune_converged_rf: int | None = None  # Convergenz-Resultat
self._tune_convergence_cancelled: bool = False  # Cancel-Flag (F2)
```

**AC3 — TUNE-Sequenz mit Phase A + Phase B** (F6+F7):

In `_start_auto_tune_for_band_change` UND `_on_tune_clicked`:

```python
# Phase A: Tuner-Match (klassisch wie heute)
self._tune_in_progress = True
self._tune_active = True
self.radio.set_tx_antenna("ANT1")
self.radio.set_rfpower_direct(10)
self.radio.tune_on()

duration_s = self.settings.get("tune_duration_s", 15)
match_s = max(5, duration_s - 5)  # Phase A = duration - 5s, min 5s
# (F7: Phase B fix max 5s, Phase A = Rest)

# Synchron warten Phase A (im Auto-Tune-Pfad — manueller Pfad behält
# QTimer-Auto-Stop wie heute)
# Manueller Pfad: kein synchrones Warten, Phase B läuft in _tune_stop
# Auto-Tune-Pfad: Helper `_run_tune_phases(match_s)` synchron mit
# Event-Loop für AutoTuneDialog-Modal

# Nach Phase A: SWR-Check (F6)
swr_after_match = self.radio.last_swr
swr_limit = self.settings.get("swr_limit", 3.0)
if swr_after_match > swr_limit:
    print(f"[P54-FIX] Phase B SKIP — SWR {swr_after_match:.1f} > {swr_limit}")
    self._tune_converged_rf = None  # Fallback in Post-Check
else:
    # Phase B: Closed-Loop bis FWDPWR ≈ 10W
    self._tune_converged_rf = self._tune_converge_to_target(target_w=10)

# Danach normaler tune_stop-Pfad (tune_off → 2s → _tune_post_swr_check)
self._tune_stop(_token)
```

**Wichtig:** für **manuellen TUNE** ist die Architektur identisch —
nur ohne AutoTuneDialog. Helper `_run_tune_phases` wird in beiden
Pfaden aufgerufen.

**AC4 — `_tune_post_swr_check` mit konvergiertem Save** (F4 ROT + F5):

```python
def _tune_post_swr_check(self, token):
    if getattr(self, '_tune_post_check_token', None) is not token:
        return
    self._tune_in_progress = False
    is_auto = self._auto_tune_running
    dlg = self._auto_tune_dialog

    if not self.radio.ip:
        if is_auto and dlg:
            dlg.auto_tune_done.emit(False, 0.0, 0.0)
        return

    swr_now = self.radio.last_swr
    swr_limit = self.settings.get("swr_limit", 3.0)
    band = self.settings.band.upper()

    samples = list(self._fwdpwr_samples)
    self._fwdpwr_samples.clear()
    avg_fwdpwr = (sum(samples) / len(samples)) if samples else 0.0

    if swr_now <= swr_limit:
        was_blocked = band in self._swr_blocked_bands
        self._swr_blocked_bands.discard(band)

        # P54-FIX F4: konvergierter Wert statt hart 10
        rf_to_save = self._tune_converged_rf if self._tune_converged_rf is not None else 10

        # F5 ORANGE: Plausibilitäts-Check rf ∈ [3, 50] für 10W-Ziel
        if 3 <= rf_to_save <= 50:
            self.rf_preset_store.save(
                self.radio.radio_type, self.settings.band, 10, rf_to_save
            )
            print(f"[P54-FIX] RFPreset gespeichert: "
                  f"{self.settings.band}_10W → rf={rf_to_save} "
                  f"(SWR {swr_now:.1f}, FWDPWR avg {avg_fwdpwr:.1f}W)")
            # F1 ROT: _apply_rf_preset + Hardware-Sync
            self._apply_rf_preset()
            self.radio.set_power(self._rfpower_current)
        else:
            print(f"[P54-FIX] Stuetzpunkt verworfen: rf={rf_to_save} "
                  f"out of [3..50] — Hardware-Anomalie")

        # Reset für nächsten TUNE
        self._tune_converged_rf = None

        if was_blocked:
            self.qso_panel.add_info(f"✓ Band {band} freigegeben — SWR {swr_now:.1f}")
            if not is_auto and self._rx_mode == "diversity":
                scoring = getattr(self._diversity_ctrl, 'scoring_mode', 'normal')
                self._check_diversity_preset(self.settings.band, self.settings.mode, scoring)
        else:
            self.qso_panel.add_info(f"✓ TUNE OK — SWR {swr_now:.1f} (rf={rf_to_save})")

        if is_auto and dlg:
            dlg.auto_tune_done.emit(True, swr_now, avg_fwdpwr)
    else:
        # SWR-Bad: kein Save (wie bisher)
        self._tune_converged_rf = None
        if is_auto and dlg:
            dlg.auto_tune_done.emit(False, swr_now, avg_fwdpwr)
        else:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(
                self,
                "Tuner konnte nicht matchen",
                f"SWR weiter {swr_now:.1f} > Limit {swr_limit:.1f}.\n\n"
                "Antenne pruefen oder TUNE wiederholen."
            )
```

**AC5 — `_kruecken_skalierung` Helper + `_apply_rf_preset`-Integration**:

```python
def _kruecken_skalierung(self, band: str, target_w: int) -> int | None:
    """P54-FIX AC5: linear vom einzigen Stützpunkt mit -10% Sicherheit.

    Returns rfpower (1-100) oder None wenn keine Krücke möglich.
    """
    if not hasattr(self, 'rf_preset_store') or self.radio is None:
        return None
    radio_type = self.radio.radio_type
    all_presets = self.rf_preset_store.get_all(radio_type)
    band_data = all_presets.get(band, {})

    if len(band_data) != 1:
        return None  # 0 oder ≥2 Stützpunkte → andere Pfade

    anchor_watt, anchor = next(iter(band_data.items()))
    anchor_rf = anchor.get("rf", 0)
    if anchor_watt <= 0 or anchor_rf <= 0:
        return None

    estimated = anchor_rf * (target_w / anchor_watt) * 0.9
    krucke = max(1, min(100, int(round(estimated))))
    print(f"[RF-Preset] Krücke: {band}_{target_w}W → rf={krucke} "
          f"(Anker {anchor_watt}W=rf{anchor_rf}, linear×0.9)")
    return krucke


def _apply_rf_preset(self):
    if self.radio is None:
        self._rfpower_current = 50
        self._rfpower_converged = False
        self._was_converged = False
        return
    band = self.settings.band
    watts = getattr(self, "_power_target", None) or self.settings.get("power_preset", 10)

    saved = self.rf_preset_store.load(self.radio.radio_type, band, watts)
    if saved is not None:
        self._rfpower_current = saved
        print(f"[RF-Preset] geladen: {band}_{watts}W → rf={saved}")
    else:
        # P54-FIX AC5: Krücken-Skalierung wenn genau 1 Stützpunkt
        krucke = self._kruecken_skalierung(band, watts)
        if krucke is not None:
            self._rfpower_current = krucke
        else:
            self._rfpower_current = self.settings.get_tx_power(band, default=50)
            print(f"[RF-Preset] Default: {band}_{watts}W → rf={self._rfpower_current}")

    self._rfpower_converged = False
    self._was_converged = False
```

**AC6 — Cancel-Pfad in AutoTuneDialog** (F2 ROT):

`_on_cancel_clicked` und `_on_backup_timeout` setzen
`parent._tune_convergence_cancelled = True` **zusätzlich** zum
bestehenden `parent._tune_in_progress = False`.

**AC7 — Hardware-Pflicht**

- `set_tx_antenna("ANT1")` einmal in Phase A (vor `tune_on`).
- Phase B macht keine Antennen-Änderung.
- Slider-Clamp `1 ≤ rf ≤ 100` in jeder Iteration.

**AC8 — Tests `tests/test_p54_fix.py`** (18 Tests):

- T1: `_tune_converge_to_target` mit linearem Radio (FWDPWR ≈ rfpower)
  → konvergiert bei rf=10.
- T2: Off-Band-Verlust (FWDPWR=7W bei rf=10) → konvergiert auf rf≈14.
- T3: FWDPWR > Ziel → reduziert rf.
- T4: Max-Iterations → returnt letzten Wert (best-effort).
- T5: Kein FWDPWR-Sample → returnt None.
- T6: Cancel-Flag während Schleife → returnt None.
- T7: Phase B mit SWR > Limit → skip, `_tune_converged_rf = None`.
- T8: `_tune_post_swr_check` mit konvergiertem rf → save mit echtem Wert.
- T9: `_tune_post_swr_check` mit `_tune_converged_rf=None` → save mit
  Fallback 10 (Backward-Compat, F9).
- T10: `_tune_post_swr_check` mit rf < 3 → kein save (Plausibilität F5).
- T11: `_tune_post_swr_check` mit rf > 50 → kein save (Plausibilität F5).
- T12: `_tune_post_swr_check` ruft `radio.set_power` nach `_apply_rf_preset`
  (F1 ROT).
- T13: `_kruecken_skalierung` mit 1 Stützpunkt → linear × 0.9.
- T14: `_kruecken_skalierung` mit 0 Stützpunkten → None.
- T15: `_kruecken_skalierung` mit 2+ Stützpunkten → None
  (Hybrid übernimmt).
- T16: `_kruecken_skalierung` mit anchor_rf=0 → None.
- T17: `_apply_rf_preset` nutzt Krücke wenn Store None.
- T18: `_tune_converged_rf` in `__init__` als None initialisiert (F3 ROT).

## Atomare Commits

- C1: Backup `Appsicherungen/2026-05-16_v0.97.44_vor_p54fix/`.
- C2: `ui/main_window.py` State-Vars `_tune_converged_rf`,
  `_tune_convergence_cancelled` (F3).
- C3: `ui/mw_tx.py` Helper `_tune_converge_to_target` + `_wait_with_event_loop`.
- C4: `ui/mw_tx.py` Helper `_kruecken_skalierung` + `_apply_rf_preset`
  erweitert.
- C5: `ui/mw_tx.py` `_tune_post_swr_check` Save mit konvergiertem Wert +
  Plausibilität + set_power (F1, F4, F5).
- C6: `ui/mw_tx.py` `_start_auto_tune_for_band_change` + `_on_tune_clicked`
  mit Phase A + SWR-Check + Phase B (F6, F7).
- C7: `ui/auto_tune_dialog.py` Cancel-Flag-Set (F2).
- C8: `tests/test_p54_fix.py` 18 Tests.
- C9: `main.py` APP_VERSION 0.97.44 → 0.97.45.
- C10: HISTORY+HANDOFF+CLAUDE+Memory.

## Field-Test (Mike, mit Radio)

- F1: TUNE auf 40m resonant → Convergenz erreicht echten rf-Wert
  (z.B. 11-14), Tabelle zeigt korrekten Wert.
- F2: TUNE auf 17m mit SWR 2,5:1 (nach Match) → Convergenz auf höheren
  rf-Wert (z.B. 16-22), Tabelle zeigt das.
- F3: Phase A misslingt (SWR weiter > 3) → Phase B SKIP, kein Save,
  Marker bleibt.
- F4: Erstes QSO 50W nach P54-FIX → Krücke greift, Slider z.B. 63.
  Closed-Loop konvergiert + speichert echten 50W-Wert.
- F5: Settings-Tabelle nach mehreren Sessions → echte band-spezifische
  Werte (10W-Anker + höhere Watt-Werte aus QSO-Convergenz).
- F6: Cancel-Button während TUNE → Schleife bricht ab, kein Save,
  Hardware in sauberem State.
- F7: Convergenz mit Hardware-Fehler (FWDPWR=0) → Fallback rf=10, kein
  Crash.
- F8: Manueller TUNE → identische Phase A + B + Save-Logik wie Auto-Tune.
