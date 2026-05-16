# P63 V3 — Finaler Plan nach R1 (DeepSeek-V4-pro)

**Basis:** V1 + V2 + R1
**Status:** Push-freigegeben (V3-Phase OK) — gemäß R1 §7
**Datum:** 2026-05-15 nachmittags
**Version:** v0.97.35 → v0.97.36

R1-Findings übernommen: F-R1-1 (kritisch Post-Tune-SWR-Race),
F-R1-2 (kritisch Auto-TUNE-Lock-Release), F-R1-3 (Risiko Power-Reset),
F-R1-4 (Risiko Button-State), F-R1-5 (kritisch Pending-Click),
F-R1-6 (Hinweis Token-OK), HW (ANT1-Pflicht explizit).

---

## 1. Akzeptanzkriterien (AC1-AC13, FINAL)

| # | Was |
|---|---|
| AC1 | `_on_swr_alarm` ruft `_set_gain_measure_lock(False)` im Stop-Block (Bug-Fix Mike-17m) |
| AC2 | `_on_swr_alarm` setzt `_swr_blocked_bands.add(band.upper())` wenn `tuner_present=True` |
| AC3 | Tuner=False: KEIN Marker-Set, Modal-Text „Antenne prüfen" |
| AC4 | `_tune_in_progress=True` während manuellem TUNE (von tune_on bis tune_off+2s-Frist); `_on_swr_alarm` returnt sofort |
| AC5 | Manueller TUNE: 10W fest (`set_rfpower_direct(10)`), Dauer aus Setting (15 oder 30), Auto-Stop via QTimer + Token |
| AC6 | Nach TUNE-Stop: 2s-Timer dann SWR ≤ Limit → Marker entfernt + Diversity-Resume via `_check_diversity_preset` falls aktiv (R1-F1) |
| AC7 | Nach TUNE-Stop: 2s-Timer dann SWR > Limit → Marker bleibt + Modal „Tuner konnte nicht matchen" (R1-F1) |
| AC8 | Pre-Check in 6 Pfaden: `_start_dx_tuning`, `_check_diversity_preset`, `_on_cq_clicked`, `_on_station_clicked`, `_on_btn_omni_cq_toggled`, `_on_btn_auto_hunt_toggled` |
| AC9 | Tuner=False: `_start_dx_tuning` überspringt Auto-TUNE-Phase (KISS-Else-Branch Z.1379-1381) + Power-Reset auf `power_preset` (R1-F3) |
| AC10 | `_swr_blocked_bands` in-memory, App-Restart leert (kein Persist) |
| AC11 | Auto-TUNE-Post-Check `_start_dx_tuning` Z.1366 setzt `_swr_blocked_bands.add(band)` wenn `tuner_present=True` + ruft `_set_gain_measure_lock(False)` (R1-F2) |
| AC12 | `_on_station_clicked` Pre-Check schützt auch **gegen Buffering**: bei TX-aktiv + Band rot → kein Buffer, return; und `_on_tx_finished` prüft Marker beim Verarbeiten des Buffers (R1-F5) |
| AC13 | `_start_dx_tuning` ruft explizit `radio.set_tx_antenna("ANT1")` vor Auto-TUNE (HW-Pflicht, R1-§4) |

## 2. Neue Settings (config/settings.py DEFAULTS)

```python
"tuner_present": True,           # bool
"tune_duration_s": 15,           # int, {15, 30}
```

Migration: alte Configs ohne diese Keys → Default via `get(default=...)`.

## 3. Neue State (ui/main_window.py Init Z.269-284)

```python
self._swr_blocked_bands: set[str] = set()
self._tune_in_progress: bool = False
self._tune_auto_stop_token = None  # Re-Entry-Schutz QTimer
self._tune_post_check_token = None # Re-Entry-Schutz 2s-Post-Check (AC6/7)
```

## 4. Detailed Changes (pro Datei)

### 4.1 `config/settings.py` (C1)

```python
# In DEFAULTS-Dict Z.49-74:
"tuner_present": True,
"tune_duration_s": 15,
```

### 4.2 `ui/settings_dialog.py` (C2)

In `_build_tab_ft8()` (Z.306), nach `stats_cb` (Z.316-322):

```python
# P63 — Tuner-Settings
self.tuner_present_cb = QCheckBox("Antennen-Tuner verwenden")
self.tuner_present_cb.setToolTip(
    "Aktiviert die Auto-TUNE-Phase vor der Gain-Messung\n"
    "und den manuellen TUNE-Button. Deaktivieren wenn\n"
    "Monoband-Antennen ohne Tuner (z.B. Dipol)."
)
form.addRow("", self.tuner_present_cb)

self.tune_duration_combo = QComboBox()
self.tune_duration_combo.addItem("15 s", 15)
self.tune_duration_combo.addItem("30 s", 30)
self.tune_duration_combo.setToolTip(
    "Maximale Dauer eines manuellen TUNE-Vorgangs.\n"
    "LDG AT-200 Pro schafft Full-Tune typisch in <15s,\n"
    "30s als Reserve für sehr unkonstante Antennen."
)
form.addRow("TUNE-Dauer (manuell):", self.tune_duration_combo)
```

Load (in `_load_settings` / `__init__` Z.564 ff):

```python
self.tuner_present_cb.setChecked(self.settings.get("tuner_present", True))
_dur = self.settings.get("tune_duration_s", 15)
self.tune_duration_combo.setCurrentIndex(0 if _dur == 15 else 1)
```

Save (`_save_and_close` Z.704):

```python
self.settings.set("tuner_present", self.tuner_present_cb.isChecked())
self.settings.set("tune_duration_s", self.tune_duration_combo.currentData())
```

Reset (Z.756):

```python
self.tuner_present_cb.setChecked(True)
self.tune_duration_combo.setCurrentIndex(0)
```

Live-Apply in `main_window._on_settings_clicked` nach `dialog.exec()`:

```python
self.control_panel.set_tuner_present(
    self.settings.get("tuner_present", True))
```

### 4.3 `ui/main_window.py` (C3)

Init-Block (neben Z.269-284):

```python
self._swr_blocked_bands: set[str] = set()
self._tune_in_progress: bool = False
self._tune_auto_stop_token = None
self._tune_post_check_token = None
```

`_on_btn_omni_cq_toggled` (Z.764) Pre-Check (R1-F4):

```python
def _on_btn_omni_cq_toggled(self, checked: bool):
    if checked and not self._omni_cq.is_active():
        # P63: Pre-Check vor allen anderen Checks
        band = self.settings.band.upper()
        if band in self._swr_blocked_bands:
            btn = self.control_panel.btn_omni_cq
            btn.blockSignals(True)
            btn.setChecked(False)
            btn.blockSignals(False)
            self.qso_panel.add_info(
                f"⚠ OMNI blockiert — Band {band} SWR-Sperre. "
                "Manueller TUNE zum Freischalten.")
            return
        # ... bestehender Code ...
```

`_on_btn_auto_hunt_toggled` (Z.854) analog — Pre-Check vor `start_auto_hunt`.

### 4.4 `ui/mw_tx.py` (C4, C7)

`_on_swr_alarm` (Z.124) erweitert:

```python
@Slot(float)
def _on_swr_alarm(self, swr: float):
    from PySide6.QtWidgets import QMessageBox
    from core.qso_state import QSOState

    # P63 AC4: Während manuellem TUNE komplett aus
    if getattr(self, "_tune_in_progress", False):
        return

    # Bestehender Pre-Check
    if not self.encoder.is_transmitting:
        self._swr_spike_count = 0
        return

    now = time.monotonic()
    if self._swr_spike_count == 0 or (now - self._swr_first_alarm_t) > 0.5:
        self._swr_spike_count = 1
        self._swr_first_alarm_t = now
        return

    self._swr_spike_count = 0
    limit = self.settings.get("swr_limit", 3.0)

    # Stop-Block (unverändert antennen-neutral)
    self.encoder.abort()
    if self.radio.ip:
        self.radio.ptt_off()
    if hasattr(self, "_pending_station_click"):
        self._pending_station_click = None
    if self.qso_sm.cq_mode or self.qso_sm.state != QSOState.IDLE:
        self.qso_sm.stop_cq()
        self.qso_sm.cancel()
        self.control_panel.set_cq_active(False)
    if hasattr(self, "_omni_cq") and self._omni_cq.is_active():
        self._omni_cq.stop("swr_block")
    if hasattr(self, "_auto_hunt") and self._auto_hunt.active:
        self._auto_hunt.stop_auto_hunt("swr_block")

    # AC1: Lock-Release-Bug-Fix
    self._set_gain_measure_lock(False)

    # AC2 / AC3: Marker-Set wenn Tuner vorhanden
    band = self.settings.band.upper()
    tuner = self.settings.get("tuner_present", True)
    if tuner:
        self._swr_blocked_bands.add(band)
        modal_title = "Band gesperrt — SWR zu hoch"
        modal_text = (
            f"Band {band} gesperrt — SWR {swr:.1f} > Limit {limit:.1f}.\n\n"
            "Bitte manuell durch TUNE-Vorgang freischalten."
        )
        panel_text = f"⚠ Band {band} gesperrt — SWR {swr:.1f}"
    else:
        modal_title = "SWR-Schutz ausgelöst"
        modal_text = (
            f"TX abgebrochen — SWR {swr:.1f} > Limit {limit:.1f}.\n\n"
            "Antenne prüfen."
        )
        panel_text = f"⚠ TX abgebrochen — SWR {swr:.1f}"

    self.qso_panel.add_info(panel_text)
    print(f"[P53/P63] SWR-Watchdog: TX gestoppt — "
          f"SWR {swr:.1f}, marker={tuner}, band={band}")

    QMessageBox.warning(self, modal_title, modal_text)
```

`_on_tune_clicked` (Z.65) Neuschnitt:

```python
@Slot(bool)
def _on_tune_clicked(self, on: bool):
    if not self.radio.ip:
        return
    from PySide6.QtCore import QTimer
    from config.settings import get_tune_freq_mhz

    if on:
        # P63 AC5: 10W fest, Dauer aus Setting
        TUNE_POWER_W = 10
        duration_s = self.settings.get("tune_duration_s", 15)
        if duration_s not in (15, 30):
            duration_s = 15

        # AC4: Watchdog-Bypass VOR tune_on
        self._tune_in_progress = True

        # Tune-Frequenz (Side-Band)
        tune_freq = get_tune_freq_mhz(self.settings.band, self.settings.mode)
        self._tune_active = True
        if tune_freq is not None:
            self._tune_freq_mhz = tune_freq
            self.radio.set_frequency(tune_freq)
        else:
            self._tune_freq_mhz = self.settings.frequency_mhz

        self.radio.set_tx_antenna("ANT1")     # HW-Pflicht
        self.radio.set_rfpower_direct(TUNE_POWER_W)
        self.radio.tune_on()
        self._update_statusbar()
        self.statusBar().showMessage(
            f"TUNEN — {TUNE_POWER_W}W auf ANT1 für {duration_s}s ...", 0)
        display_freq = tune_freq if tune_freq is not None else self.settings.frequency_mhz
        self.control_panel.set_freq_display(display_freq, tune_active=True)
        print(f"[P63] Manueller TUNE — {TUNE_POWER_W}W {duration_s}s")

        # Auto-Stop nach Dauer mit Token
        self._tune_auto_stop_token = object()
        _token = self._tune_auto_stop_token
        QTimer.singleShot(
            duration_s * 1000,
            lambda: self._tune_stop(_token))
    else:
        # User-Toggle off → unbedingt stop
        self._tune_stop(None)


def _tune_stop(self, token):
    """Tune beenden + 2s-Post-Check für SWR-Auswertung (AC6/AC7).

    token=None → unbedingt (User-Toggle), sonst Token-Vergleich.
    """
    if token is not None and getattr(self, '_tune_auto_stop_token', None) is not token:
        return  # neuer TUNE-Click hat Token gewechselt
    if not self._tune_active:
        return  # schon gestoppt

    from PySide6.QtCore import QTimer

    # tune_off + VFO zurück
    self.radio.tune_off()
    self._tune_active = False
    self._tune_freq_mhz = None
    work_freq = self.settings.frequency_mhz
    self.radio.set_frequency(work_freq)
    self.radio.set_power(self.settings.get("power_preset", 15))
    self._update_statusbar()
    self.control_panel.set_freq_display(work_freq, tune_active=False)

    # AC4 erweitert: _tune_in_progress bleibt TRUE noch 2s
    # (Watchdog soll aktive Pre-PTT-Glitches NICHT als TUNE-Stop sehen).
    # Erst nach 2s Beruhigungszeit wird SWR ausgewertet und Watchdog
    # scharf gestellt.
    self.statusBar().showMessage(
        "TUNE beendet — prüfe SWR (2 s) ...", 2000)

    # Re-Entry-Schutz für Post-Check
    self._tune_post_check_token = object()
    _post = self._tune_post_check_token

    QTimer.singleShot(
        2000,
        lambda: self._tune_post_swr_check(_post))


def _tune_post_swr_check(self, token):
    """R1-F1: 2s nach tune_off SWR auswerten.

    - SWR ≤ Limit → Marker discard + Diversity-Resume (falls Diversity)
    - SWR > Limit → Modal „Tuner konnte nicht matchen", Marker bleibt
    """
    if getattr(self, '_tune_post_check_token', None) is not token:
        return  # neuer TUNE hat token rotiert

    # Watchdog wieder scharf
    self._tune_in_progress = False

    if not self.radio.ip:
        return

    swr_now = self.radio.last_swr
    swr_limit = self.settings.get("swr_limit", 3.0)
    band = self.settings.band.upper()

    from PySide6.QtWidgets import QMessageBox

    if swr_now <= swr_limit:
        was_blocked = band in self._swr_blocked_bands
        self._swr_blocked_bands.discard(band)
        if was_blocked:
            self.qso_panel.add_info(
                f"✓ Band {band} freigegeben — SWR {swr_now:.1f}")
            print(f"[P63] Marker freigegeben — {band} SWR {swr_now:.1f}")
            # AC6: Diversity-Resume
            if self._rx_mode == "diversity":
                scoring = getattr(self._diversity_ctrl, 'scoring_mode', 'normal')
                ft_mode = self.settings.mode
                self._check_diversity_preset(self.settings.band, ft_mode, scoring)
        else:
            self.qso_panel.add_info(f"✓ TUNE OK — SWR {swr_now:.1f}")
    else:
        # AC7: Marker bleibt rot
        QMessageBox.warning(
            self,
            "Tuner konnte nicht matchen",
            f"SWR weiter {swr_now:.1f} > Limit {swr_limit:.1f}.\n\n"
            "Antenne prüfen oder TUNE wiederholen."
        )
    print(f"[P63] Post-TUNE — SWR {swr_now:.1f}, Limit {swr_limit:.1f}")
```

### 4.5 `ui/mw_radio.py` (C5)

`_check_diversity_preset` (Z.1213) am Top:

```python
def _check_diversity_preset(self, band: str, ft_mode: str, scoring: str) -> None:
    if not getattr(self, 'radio', None) or not self.radio.ip:
        return
    # P63: Marker-Pre-Check
    if band.upper() in self._swr_blocked_bands:
        self.qso_panel.add_info(
            f"⚠ Diversity blockiert — Band {band.upper()} SWR-Sperre. "
            "Manueller TUNE zum Freischalten.")
        self._update_statusbar()
        return
    # ... bestehender Code unverändert ...
```

`_start_dx_tuning` (Z.1329) Pre-Check + ANT1 + Tuner-Skip + Lock-Release-Fix:

```python
def _start_dx_tuning(self, scoring_mode: str = "snr"):
    import time as _time
    self._stats_warmup_cycles = 99999
    self._gain_scoring_mode = scoring_mode
    from PySide6.QtCore import QTimer

    # P63: Marker-Pre-Check
    band = self.settings.band.upper()
    if band in self._swr_blocked_bands:
        self.qso_panel.add_info(
            f"⚠ Gain-Messung blockiert — Band {band} SWR-Sperre.")
        self._set_gain_measure_lock(False)
        return

    self._set_gain_measure_lock(True)

    # SICHERHEIT: TX SOFORT stoppen
    if self.qso_sm.cq_mode:
        self.qso_sm.stop_cq()
        self.control_panel.set_cq_active(False)
    if self.qso_sm.state != QSOState.IDLE:
        self.qso_sm.cancel()
    if self.encoder.is_transmitting:
        self.encoder.abort()
        if self.radio.ip:
            self.radio.ptt_off()

    tune_power = self.settings.get("tune_power", 10)
    swr_limit  = self.settings.get("swr_limit", 3.0)
    tuner_present = self.settings.get("tuner_present", True)

    # AC9 + AC13: ANT1 + Auto-TUNE nur wenn Radio verbunden UND Tuner an
    if self.radio.ip and tuner_present:
        self.radio.set_tx_antenna("ANT1")     # R1-§4 HW-Pflicht
        self.statusBar().showMessage(
            f"TUNEN — {tune_power}W auf ANT1 fuer 3s ...", 0)
        self.radio.set_rfpower_direct(tune_power)
        self.radio.tune_on()

        def _after_tune():
            self.radio.tune_off()
            self.radio.set_power(self.settings.get("power_preset", 15))
            self._normal_stations = {}
            self._diversity_stations = {}
            self.rx_panel.table.setRowCount(0)
            swr = self.radio.last_swr
            if swr > swr_limit:
                # R1-F2 + AC11: Lock-Release + Marker-Set bei SWR-Fehler
                self._set_gain_measure_lock(False)
                if self.settings.get("tuner_present", True):
                    self._swr_blocked_bands.add(band)
                    print(f"[P63] Auto-TUNE-Fehler → Marker {band} gesetzt")
                from PySide6.QtWidgets import QMessageBox
                QMessageBox.warning(
                    self, "SWR zu hoch",
                    f"SWR {swr:.1f} > {swr_limit:.1f} — Gain-Messung abgebrochen.\n"
                    f"Antenne/Tuner pruefen!"
                )
                self._on_rx_mode_changed("normal")
                return
            self._open_dx_tune_dialog()

        QTimer.singleShot(3000, _after_tune)
    else:
        # R1-F3 + AC9: Kein Radio ODER Tuner=NEIN → direkt Gain-Mess
        # Power-Reset auf sicheren Wert wenn Radio verbunden
        if self.radio.ip:
            self.radio.set_power(self.settings.get("power_preset", 15))
        self._open_dx_tune_dialog()
```

### 4.6 `ui/mw_qso.py` (C6 — Pre-Checks + Pending-Click-Schutz)

`_on_station_clicked` (Z.143) erweitert:

```python
def _on_station_clicked(self, msg: FT8Message):
    band = self.settings.band.upper()

    # P63 AC8 + AC12 R1-F5: Marker-Pre-Check inkl. Buffer-Schutz
    if band in self._swr_blocked_bands:
        if self.encoder.is_transmitting:
            self.statusBar().showMessage(
                f"TX läuft — {msg.caller} blockiert (Band {band} SWR-Sperre)",
                3000)
        else:
            self.qso_panel.add_info(
                f"⚠ Anruf {msg.caller} blockiert — Band {band} SWR-Sperre.")
        return  # KEIN Buffer, kein State-Mutate

    # ... bestehender Code unverändert ...
```

`_on_tx_finished` Pending-Klick-Auswertung (R1-F5 §2): falls
gebufferter Klick existiert, vor `_on_station_clicked(buffered)`
nochmal Marker prüfen:

```python
# Heutige Stelle (mw_qso.py Z.407-412):
if self._pending_station_click is not None:
    buffered = self._pending_station_click
    self._pending_station_click = None
    # P63 AC12: nochmal Marker-Check (Band-Wechsel zwischen Buffer
    # und tx_finished theoretisch möglich)
    if self.settings.band.upper() in self._swr_blocked_bands:
        self.qso_panel.add_info(
            f"⚠ Gepufferter Klick verworfen — "
            f"Band {self.settings.band.upper()} SWR-Sperre")
        return
    self._on_station_clicked(buffered)
```

`_on_cq_clicked` (Z.275) Pre-Check:

```python
def _on_cq_clicked(self):
    if self.control_panel.btn_cq.isChecked():
        # P63: Marker-Pre-Check
        band = self.settings.band.upper()
        if band in self._swr_blocked_bands:
            self.qso_panel.add_info(
                f"⚠ CQ blockiert — Band {band} SWR-Sperre.")
            self.control_panel.set_cq_active(False)
            return
        # ... bestehender Code ...
```

### 4.7 `core/auto_hunt.py` (C6 implizit über Toggle-Handler)

**Keine Änderung in `core/auto_hunt.py` notwendig** (R1-F4 KISS):
Pre-Check sitzt in `_on_btn_auto_hunt_toggled` (main_window.py Z.854).
AutoHunt ist eh nur startbar via Toggle.

Falls Auto-Hunt während laufender Session ein Band wechselt: heute
gibt es Stop-Logik `stop_auto_hunt("band_change")` (siehe Memory). Wenn
auf neuem Band Marker rot ist, kann User Auto-Hunt nicht neu starten —
Pre-Check im Toggle blockt.

### 4.8 `core/omni_cq.py` (kein Change nötig)

OMNI-Toggle ist in `main_window._on_btn_omni_cq_toggled` (Z.764), dort
Pre-Check. OMNI selbst wird via `stop("swr_block")` schon im
`_on_swr_alarm` gestoppt. **Keine Änderung in `core/omni_cq.py`.**

### 4.9 `ui/control_panel.py` (C8)

In `_update_button_visibility` (Z.984-Bereich) TUNE-Button-Visibility:

```python
# P63: TUNE-Button nur sichtbar wenn tuner_present=True
self.btn_tune.setVisible(getattr(self, '_tuner_present', True))
```

Plus neue Methode:

```python
def set_tuner_present(self, value: bool) -> None:
    """P63: TUNE-Button-Sichtbarkeit live setzen (vom MainWindow nach
    Settings-Save gerufen)."""
    self._tuner_present = bool(value)
    self.btn_tune.setVisible(self._tuner_present)
```

Plus Init im Konstruktor (vor `_update_button_visibility`):

```python
self._tuner_present = True   # Default, von MainWindow überschrieben
```

In `__init__` von MainWindow nach `_set_band(...)` aber vor
`_update_button_visibility()`:

```python
# P63: Tuner-Setting an ControlPanel propagieren
self.control_panel.set_tuner_present(
    self.settings.get("tuner_present", True))
```

## 5. Test-Liste (T1-T15 + T18-T20, 18 Tests)

| # | Test | Was geprüft |
|---|---|---|
| T1 | `test_p63_swr_alarm_releases_lock` | AC1: `_gain_measure_locked=False` nach Alarm |
| T2 | `test_p63_swr_alarm_sets_marker_when_tuner` | AC2: `_swr_blocked_bands.add(band.upper())` bei tuner_present=True |
| T3 | `test_p63_swr_alarm_no_marker_when_no_tuner` | AC3: Set bleibt leer bei tuner_present=False |
| T4 | `test_p63_marker_blocks_omni_toggle` | AC8: OMNI-Toggle pre-check + Button-State-Reset |
| T5 | `test_p63_marker_blocks_auto_hunt_toggle` | AC8: Auto-Hunt-Toggle pre-check |
| T6 | `test_p63_marker_blocks_normal_cq` | AC8: `_on_cq_clicked` pre-check + `set_cq_active(False)` |
| T7 | `test_p63_marker_blocks_diversity_preset` | AC8: `_check_diversity_preset` early-return |
| T8 | `test_p63_manual_tune_allowed_on_red_band` | `_on_tune_clicked(True)` läuft durch (kein Pre-Check) |
| T9 | `test_p63_tune_uses_10w_fixed` | AC5: `set_rfpower_direct(10)` unabhängig von `tune_power` |
| T10 | `test_p63_tune_duration_15_30` | AC5: Setting 15 → QTimer 15000, 30 → 30000 |
| T11 | `test_p63_tune_in_progress_bypasses_watchdog` | AC4: `_tune_in_progress=True` → SWR-Alarm returnt |
| T12 | `test_p63_post_tune_good_clears_marker` | AC6: SWR≤Limit → `discard(band)` + Diversity-Resume |
| T13 | `test_p63_post_tune_bad_keeps_marker` | AC7: SWR>Limit → Modal + Marker bleibt |
| T14 | `test_p63_no_tuner_skips_auto_tune` | AC9: tuner_present=False → kein `tune_on` in `_start_dx_tuning` |
| T15 | `test_p63_no_tuner_hides_button` | `set_tuner_present(False)` → `btn_tune.isVisible()==False` |
| T18 | `test_p63_post_tune_uses_2s_timer` | R1-F1: QTimer.singleShot(2000, ...) für Post-Check |
| T19 | `test_p63_auto_tune_failure_sets_marker_and_releases_lock` | R1-F2 (AC11): SWR>Limit nach Auto-TUNE → Marker+`set_gain_measure_lock(False)` |
| T20 | `test_p63_no_tuner_resets_power_in_skip_branch` | R1-F3 (AC9): tuner_present=False ruft `radio.set_power(power_preset)` |

Implementierung: Mocks für `radio.last_swr`, `radio.tune_on/off`,
`encoder.is_transmitting` via Stub-Klasse `_StubRadio` analog
existierender P53/P60-Tests.

## 6. Code-Plan (FINAL 11 Commits)

| # | Datei | Was |
|---|---|---|
| C1 | `config/settings.py` | DEFAULTS: `tuner_present=True`, `tune_duration_s=15` |
| C2 | `ui/settings_dialog.py` | Tab-FT8 UI + Load + Save + Reset + Tooltips |
| C3 | `ui/main_window.py` | Init `_swr_blocked_bands`/`_tune_in_progress`/Tokens + 2 Toggle-Handler Pre-Checks |
| C4 | `ui/mw_tx.py:_on_swr_alarm` | AC1 Lock-Release + AC2/AC3 Marker + AC4 Bypass-Check |
| C5 | `ui/mw_radio.py` | Pre-Checks `_check_diversity_preset` + `_start_dx_tuning` + Auto-TUNE-Fehler-Fix (AC11) + Tuner=False-Skip (AC9) + ANT1 (AC13) |
| C6 | `ui/mw_qso.py` | Pre-Checks `_on_station_clicked` + `_on_cq_clicked` + Pending-Click-Schutz (AC12) |
| C7 | `ui/mw_tx.py:_on_tune_clicked` + `_tune_stop` + `_tune_post_swr_check` | AC4/5/6/7: 10W, Dauer, Token, 2s Post-Check |
| C8 | `ui/control_panel.py` | `set_tuner_present` + TUNE-Button-Hide-Hook |
| C9 | `tests/test_p63_swr_block_marker.py` NEU | T1-T15 + T18-T20 (18 Tests) |
| C10 | `main.py` | APP_VERSION 0.97.35 → 0.97.36 |
| C11 | Doku | HISTORY/HANDOFF/CLAUDE/Memory/TODO/MEMORY.md |

## 7. Field-Tests F1-F10 (für Mike nach Push)

| # | Was |
|---|---|
| F1 | 17m-Band: SWR-Alarm → Modal „Band gesperrt — bitte TUNE", OK-Button klar |
| F2 | Nach Modal: TUNE-Button KLICKBAR, OMNI/Hunt/Normal-CQ alle BLOCKIERT mit `add_info` |
| F3 | Manueller TUNE 15s mit 10W läuft durch, Auto-Stop nach 15s, „TUNE beendet — prüfe SWR (2s)..." |
| F4 | TUNE-Erfolg auf 17m → Marker grün (`✓ Band 17M freigegeben`), Gain-Mess startet automatisch (P62-Pause) |
| F5 | TUNE-Misserfolg → Modal „Tuner konnte nicht matchen", Marker bleibt rot |
| F6 | Settings „Tuner=NEIN": TUNE-Button hidden, Gain-Mess ohne Auto-TUNE |
| F7 | Settings „Tuner=NEIN": SWR-Alarm = Modal + Stop, KEIN Marker |
| F8 | Settings „TUNE-Dauer 30s": manueller TUNE läuft 30s |
| F9 | Marker pro Band: 17m rot, dann 20m wechseln → läuft normal |
| F10 | App-Restart: alle Marker weg |

## 8. Aus Scope (klar NEIN)

- Marker-Persist über App-Restart
- Power-Variation 5W/7W
- 45s TUNE-Option
- Watchdog mit dynamischem Threshold
- TUNE-Counter / Statistik
- Manueller Marker-Override via Settings-Button

## 9. Konfidenz-Check Final

| Bereich | Konfidenz |
|---|---|
| Settings-API + UI | HOCH |
| Lock-Release-Bug-Fix (AC1) | HOCH (1 Zeile) |
| Marker-Set Watchdog (AC2/AC3) | HOCH |
| 6 Pre-Checks | HOCH (R1 hat alle 6 Stellen bestätigt) |
| 2s Post-Tune-SWR-Check | MITTEL (Timing 2000ms — F-R1-1 Empfehlung) |
| Auto-TUNE-Fehler-Pfad (AC11) | HOCH (R1-F2) |
| Tuner=False Skip + Power-Reset (AC9) | HOCH (R1-F3) |
| ANT1-Pflicht im _start_dx_tuning (AC13) | HOCH (HW-Sicherheit) |
| Pending-Click-Schutz (AC12) | MITTEL (R1-F5, 2 Stellen patchen) |

## 10. Workflow nach V3 (jetzt)

→ 11 atomare Commits (C1-C11)
→ Tests T1-T18 grün (1306 → 1324)
→ Final-R1 DeepSeek-V4-pro
→ Doku
→ Field-Test-Plan für Mike

Push pending bis Final-R1-OK + Mike-Field-Test F1-F10 ✓.
