# P54 V1 — Auto-Tune bei Bandwechsel + RFPreset-Stützpunkt-Kalibrierung

## Ziel

Zwei Bausteine als gemeinsames Bundle:

**P54a — Auto-Tune bei Bandwechsel:** Nach jedem Bandwechsel öffnet ein
Modal mit Spinner, das automatisch 10 W TUNE auf ANT1 ausführt und
schließt sich bei SWR-Good. Schaltbar per Setting.

**P54b — RFPreset-Stützpunkt durch TUNE:** Während TUNE wird FWDPWR
gemessen. Bei SWR-Good wird `rf_preset_store.save(radio, band, watts=round(avg_fwdpwr), rf=10)`
aufgerufen — egal ob Auto- oder manueller TUNE. Damit hat **jedes Band
nach erstem TUNE einen 10-Slider-Stützpunkt** für die RF-Hybrid-Logik.

## Begründung (Mike)

„wir machen ja einen tune bei jedem bandwechsel — dann können wir doch
das auch gleich als 10W für das band speichern als ausgangsleistungs-
korrekturwert? egal wechsel band wir haben immer schon den 10wattwert".

Vorteil:
- Nach Bandwechsel kein Hochtasten von 50 % Default mehr — RFPresetStore
  hat sofort einen Stützpunkt.
- Lineare Interpolation funktioniert ab 2. Stützpunkt (typisch nach
  erstem QSO bei höherer Watt-Zahl).
- Nutzt **bestehende** `core/rf_preset_store.py`-Infrastruktur — kein
  neuer Store.

## Architektur

### Code-Verifikation (Pflicht)
- `ui/mw_radio.py:380` `_on_band_changed` — vor `_check_diversity_preset`
  Hook einfügen (Z.522).
- `ui/mw_tx.py:66` `_on_tune_clicked` — manueller TUNE-Pfad, Token-Pattern
  + 2 s Post-Check existent.
- `ui/mw_tx.py:163` `_tune_post_swr_check` — SWR-Good-Branch ist der Save-
  Hook (Z.187).
- `ui/mw_tx.py:421` `_on_meter_update` — FWDPWR-Sampling läuft heute nur
  bei `encoder.is_transmitting`; muss erweitert werden auf `_tune_active`.
- `core/rf_preset_store.py:184` `save(radio, band, watt, rf)` — fertig
  nutzbar.
- `config/settings.py:79-80` `tuner_present` + `tune_duration_s` —
  P54-Setting daneben einfügen.
- `ui/settings_dialog.py:324-329` — Tab „FT8 & Diversity" Tuner-Block —
  Toggle daneben einfügen.

### AC1 — Settings
`config/settings.py` DEFAULTS:
```python
"auto_tune_on_band_change": True,
```
- `tune_duration_s` wird **wiederverwendet** (15/30 s), kein
  zusätzliches Setting. KISS.

### AC2 — `ui/auto_tune_dialog.py` NEU
- WindowModal `QDialog`, fixed-size 360×140, dunkles Theme analog
  ConnectStatusDialog.
- Inhalt:
  - Titel-Label „🔧 Auto-Tune läuft" (16 pt, hell)
  - Spinner (rotierendes QLabel mit Pixmap oder simpler QProgressBar
    indeterminate — wie ConnectStatusDialog)
  - Status-Label „Band {band}: SWR {swr:.1f} …"
  - Sekunden-Countdown
  - Cancel-Button (klein, dezent rechts unten)
- Signal `tune_finished(bool success, float swr, float avg_fwdpwr)`.
- Auto-Close-Logik via `_tune_finished_slot()` (vom Caller emittiert).
- Cancel-Button → `reject()` → Caller behandelt als „abgebrochen".

### AC3 — Hook in `_on_band_changed`
In `ui/mw_radio.py:_on_band_changed`, **NACH** `_apply_rf_preset()` (Z.481)
und **VOR** `_maybe_apply_bandpilot` (Z.520):

```python
if (self.settings.get("auto_tune_on_band_change", True)
        and self.radio.ip
        and band.upper() not in self._swr_blocked_bands):
    self._run_auto_tune_on_band_change(band)
```

Neuer Helper `_run_auto_tune_on_band_change` in `ui/mw_tx.py` (oder
direkt in `mw_radio.py`):
1. Öffne `AutoTuneDialog` (non-modal, aber blockt event-loop via
   `exec()` ist OK — Bandwechsel-Logik soll sowieso warten).
2. Setze `_tune_in_progress = True` (Watchdog-Bypass).
3. Trigger `_on_tune_clicked(True)`-äquivalenten Pfad mit
   `auto_tune_mode=True`-Flag, damit `_tune_post_swr_check` weiß dass es
   ein Auto-Tune ist (für Dialog-Close-Signal).
4. Dialog wartet auf `tune_finished`-Signal aus `_tune_post_swr_check`.
5. Bei Cancel: `_tune_stop(None)` und Dialog schließen.

### AC4 — `_on_tune_clicked` Refactor
- Gemeinsamer Code von Auto+Manuell in Helper `_start_tune(duration_s,
  on_finished_callback=None)` extrahieren.
- Manueller TUNE-Klick: ruft `_start_tune(duration_s)` ohne Callback.
- Auto-Tune-Pfad: ruft `_start_tune(duration_s, callback=dialog.finished_slot)`.

### AC5 — FWDPWR-Sampling während TUNE
In `ui/mw_tx.py:_on_meter_update`:
```python
if name == "FWDPWR":
    self.control_panel.update_watt(value)
    # P54b: Sampling während TUNE oder TX
    if value > 1 and (self.encoder.is_transmitting or self._tune_active):
        self._fwdpwr_samples.append(value)
```
Bestehende `encoder.is_transmitting`-Branches bleiben unverändert
(Audio-Anzeige etc.).

### AC6 — `_tune_post_swr_check` Save-Hook
Im SWR-Good-Branch (Z.187), **nach** `_swr_blocked_bands.discard(band)`:
```python
# P54b: RFPreset-Stützpunkt speichern (10-Slider gibt avg FWDPWR Watt)
samples = self._fwdpwr_samples[:]  # Snapshot
self._fwdpwr_samples.clear()
if samples:
    avg = sum(samples) / len(samples)
    if 2 < avg < 80:  # Plausibilität (10 W nominal, +Tuner-Verluste)
        watt = max(1, min(80, round(avg)))
        self.rf_preset_store.save(
            self.radio.radio_type, band, watt, 10
        )
        print(f"[P54b] RFPreset-Stützpunkt: {band}_{watt}W → rf=10 "
              f"(TUNE-FWDPWR avg {avg:.1f})")
```
Bei SWR-Bad: kein Save (alte Stützpunkte bleiben).

### AC7 — AutoTuneDialog: Signal-Routing
- `_tune_post_swr_check` emittiert `auto_tune_finished(bool success,
  float swr, float avg_fwdpwr)` **nur wenn** Auto-Tune-Pfad aktiv (Flag
  `self._auto_tune_running`).
- AutoTuneDialog connecten an dieses Signal, `accept()` bei success,
  `reject()` bei !success oder Cancel.

### AC8 — Auto-Tune-Fail-Pfad
- Timeout: AutoTuneDialog setzt eigenen QTimer auf
  `tune_duration_s + 5 s` (Sicherheits-Buffer); bei Ablauf
  `reject()` + Caller behandelt als Fail.
- SWR-Bad: `_tune_post_swr_check` setzt Marker (existiert in P63),
  emittiert `auto_tune_finished(False, swr, 0)` → Dialog reject.
- Caller (`_run_auto_tune_on_band_change`) zeigt `QMessageBox.warning`
  „Auto-Tune fehlgeschlagen — Antenne prüfen".
- TX bleibt durch Marker blockiert (P63-Logik).

### AC9 — Mode-Wechsel
Kein Auto-Tune bei FT8↔FT4↔FT2 — `_on_mode_changed` greift nicht in
Auto-Tune-Pfad ein. Hardware ist gleich (Slider=10 → ~10 W egal welcher
FT-Mode).

### AC10 — Convergenz nutzt Stützpunkt
`_apply_rf_preset` nutzt **bereits** `rf_preset_store.load(radio, band,
watts)`. Mit dem neuen 10-W-Stützpunkt:
- Erstnutzung 10 W → exakter Treffer, `rf=10` als Startwert.
- 50 W (kein Stützpunkt): 1 Punkt → kein Interpolation → Default 50
  (wie heute).
- Nach 1. QSO mit 50 W (Closed-Loop konvergiert): 2 Stützpunkte → 100 W
  würde interpoliert.

### AC11 — Hardware-Pflicht
- TUNE ruft `set_tx_antenna("ANT1")` (existiert in `_on_tune_clicked`
  Z.105).
- Auto-Tune-Pfad muss dies **ebenfalls** explizit aufrufen — Re-Use des
  Helpers garantiert es.
- Marker (P63) bleibt für SWR-Block-Bänder respektiert.

### AC12 — Tests `tests/test_p54_auto_tune.py`
- T1: Setting `auto_tune_on_band_change` Default True.
- T2: `tune_duration_s` Whitelist {15, 30} (Regression aus P63).
- T3: `_on_band_changed` mit Setting=False → kein Dialog.
- T4: `_on_band_changed` mit `radio.ip=None` → silent skip.
- T5: `_on_band_changed` mit `band in _swr_blocked_bands` → Skip
  (Marker bleibt).
- T6: `_on_band_changed` mit allen Bedingungen erfüllt → Dialog öffnet.
- T7: `_tune_post_swr_check` mit valid FWDPWR (z. B. 9.5) → save für
  10 W-Stützpunkt mit rf=10.
- T8: `_tune_post_swr_check` mit unplausiblem FWDPWR (1.5 oder 90) →
  kein save.
- T9: `_tune_post_swr_check` SWR-Bad → kein save.
- T10: Manueller TUNE (User-Klick) speichert Stützpunkt (idempotent).
- T11: FWDPWR-Sampling während `_tune_active` aktiv.
- T12: Auto-Tune-Erfolg → AutoTuneDialog close + Bandwechsel-Logik
  weiter.
- T13: Auto-Tune-Fail → AutoTuneDialog close + Warning + Marker bleibt.
- T14: AutoTuneDialog Cancel → Reject + Marker bleibt.
- T15: Hardware-Pflicht — explicit `set_tx_antenna("ANT1")` im Auto-
  Tune-Pfad.

### AC13 — Settings-Dialog
Tab „FT8 & Diversity", neben `tuner_present_cb` und
`tune_duration_combo`:
```python
self.auto_tune_band_cb = QCheckBox("Auto-Tune bei Bandwechsel")
self.auto_tune_band_cb.setToolTip(
    "Nach jedem Bandwechsel automatisch TUNE durchführen (10 W, Dauer wie manueller TUNE).\n"
    "Speichert RF-Stützpunkt für sofortige Sendeleistungs-Kalibrierung.")
form.addRow("", self.auto_tune_band_cb)
```

## Aus Scope
- `tune_calibration.json` als separate Datei — **abgelehnt**. Wir
  nutzen `rf_presets.json` über `RFPresetStore`.
- Bei Mode-Wechsel: kein Auto-Tune.
- Bei Normal↔Diversity-Wechsel: kein Auto-Tune.
- Manuelle TUNE-Wiederholung wenn Auto-Tune fehlschlägt: User-trigger
  (kein Auto-Retry).

## Atomare Commits
- C1: Backup `Appsicherungen/2026-05-16_v0.97.43_vor_p54/`.
- C2: `config/settings.py` DEFAULTS-Eintrag.
- C3: `ui/settings_dialog.py` Toggle einbauen (Tab „FT8 & Diversity").
- C4: `ui/auto_tune_dialog.py` NEU.
- C5: `ui/mw_tx.py` FWDPWR-Sampling während TUNE + Save-Hook in
  `_tune_post_swr_check` + Helper `_start_tune` extrahiert.
- C6: `ui/mw_radio.py` Hook in `_on_band_changed`.
- C7: `tests/test_p54_auto_tune.py` NEU (15 Tests).
- C8: `main.py` APP_VERSION 0.97.43 → 0.97.44.
- C9: HISTORY+HANDOFF+CLAUDE+Memory.

## Field-Test (Mike, mit Radio)
- F1: Bandwechsel 20m→40m → Dialog öffnet → 15 s TUNE → Dialog schließt
  bei SWR-Good. RFPreset für 40m_10W gespeichert.
- F2: Bandwechsel auf SWR-blockiertes Band → Dialog öffnet NICHT
  (Marker respektiert).
- F3: Bandwechsel mit Antennen-Mismatch → Dialog Timeout → Warning +
  Marker.
- F4: Bandwechsel mit `auto_tune_on_band_change=False` → kein Dialog.
- F5: Mode-Wechsel FT8↔FT4 → kein Auto-Tune (Hardware-Eigenschaft).
- F6: Nach Bandwechsel: TX-Power-Convergenz startet ab `rf=10` statt 50.
  Sichtbar: schnellere Konvergenz im ersten QSO-Slot.
- F7: Cancel-Button im Dialog → Tuner stoppt, Marker bleibt, kein Save.
