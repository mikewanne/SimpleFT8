# P63 V1 — SWR-Block per Band-Marker + Tuner-Settings + Lock-Release

**Datum:** 2026-05-15 (Compact-fest)
**Version:** v0.97.35 → v0.97.36 (geplant)
**Status-vorher:** Tests 1306 grün

---

## 1. Trigger & Hintergrund

Mike-Field-Test 15.05.2026 nachmittags 17m-Band:

- Bandwechsel 20m→17m in Diversity → Auto-Gain-Mess startet → TUNE
  10W → 17m-Antenne nicht resonant → SWR > 2.5 → SWR-Watchdog (P53)
  greift → Modal kommt → Fenster auf Display 2 (Remote-Setup, für Mike
  unsichtbar) → nach OK weiter:
  - **TUNE-Button GESPERRT** (Bug: `_gain_measure_locked` hängt `True`,
    weil `_on_swr_alarm` Lock NICHT zurücksetzt).
  - **OMNI CQ + Auto-Hunt KLICKBAR** (würden sofort wieder SWR-Alarm
    auslösen).
  - **Mike braucht TUNE manuell zur Diagnostik**, aber alle Auto-Pfade
    müssten gesperrt sein bis Antenne ok.

## 2. Mike-Spec O-Ton (verbindlich)

> „wenn abruch war weil swr zu hoch, meldung Band gesperrt Swr zu hoch
> bitte manuell überprüfen und durch tune vorgang freischalten meldung
> modal mit ok zu bestätigen. wenn tune dann wert gibt swr gut.
> einmessung fals nicht vorhanden starten. wenn vorhanden normaler
> ablauf, marker in memory. 10 watt fest tuner aktivierbar oder nicht
> auch gut"

Plus 15.05. Klärung: TUNE-Dauer manuell {15s, 30s} konfigurierbar,
10W fest (LDG AT-200 Pro Standard), Marker pro Band in-memory ohne
Persist, Watchdog während manuellem TUNE deaktiviert.

## 3. Architektur-Kern

### 3.1 Neue Settings (config/settings.py DEFAULTS, Z.49-74)

| Key | Typ | Default | Werte |
|---|---|---|---|
| `tuner_present` | bool | `True` | Checkbox „Antennen-Tuner verwenden" |
| `tune_duration_s` | int | `15` | ComboBox „TUNE-Dauer (manuell)" {15, 30} s |

Migration: alte Configs ohne diese Keys nehmen Default (`get` mit Default).
Keine `_migrate_*`-Funktion nötig (Settings hat schon defensives Pattern).

### 3.2 Neue State-Variable (ui/main_window.py)

```python
# Init-Block neben Z.269-284:
self._swr_blocked_bands: set[str] = set()
self._tune_in_progress: bool = False   # Watchdog-Bypass während manuellem TUNE
```

- `_swr_blocked_bands`: in-memory (kein Persist über App-Restart, Mike-Spec).
- Schlüssel: uppercase Band-String (`"17M"`, `"20M"`, etc.). Mode-unabhängig
  weil Antennen-Hardware mode-unabhängig.

### 3.3 Verhalten — `tuner_present=True` (Default)

#### A. SWR-Watchdog greift (ui/mw_tx.py:_on_swr_alarm Z.123-184)

Heute (v0.97.35):

```python
# Stop-Block läuft, dann:
self.qso_panel.add_info(f"⚠ TX abgebrochen — SWR {swr:.1f}")
QMessageBox.warning(self, "SWR-Schutz ausgelöst", f"TX abgebrochen — SWR ...")
```

P63-Änderung (nach Stop-Block, vor add_info):

```python
# AC1 — Lock-Release-Bug-Fix (HÄNGT HEUTE):
self._set_gain_measure_lock(False)

# AC2 — Marker-Set wenn Tuner verfügbar:
band = self.settings.band.upper()
if self.settings.get("tuner_present", True):
    self._swr_blocked_bands.add(band)
    msg_text = (
        f"Band {band} gesperrt — SWR {swr:.1f} > Limit.\n\n"
        "Bitte manuell durch TUNE-Vorgang freischalten."
    )
else:
    # Tuner=NEIN: kein Marker, einfach Stop+Modal
    msg_text = (
        f"TX abgebrochen — SWR {swr:.1f} > Limit.\n\n"
        "Antenne prüfen."
    )

self.qso_panel.add_info(f"⚠ {msg_text.splitlines()[0]}")
QMessageBox.warning(self, "SWR-Schutz ausgelöst", msg_text)
```

#### B. TX-Auto-Pfade — Pre-Check auf Marker

**Stellen die VOR einem Auto-TX-Start abfragen müssen:**

1. **ui/mw_radio.py:_check_diversity_preset (Z.1213, Top der Methode):**
   ```python
   band = self.settings.band.upper()
   if band in self._swr_blocked_bands:
       self.qso_panel.add_info(
           f"⚠ Diversity blockiert — Band {band} hat SWR-Sperre. "
           "Manueller TUNE zum Freischalten."
       )
       self._update_statusbar()
       return
   ```

2. **ui/mw_radio.py:_start_dx_tuning (Z.1329):** wird von
   `_check_diversity_preset` aufgerufen, dort schon abgefangen. Plus
   KALIBRIEREN-Button-Pfad (`_handle_dx_tuning`) — selber Pre-Check Top.

3. **ui/mw_qso.py:_on_cq_clicked (Z.275):**
   ```python
   band = self.settings.band.upper()
   if band in self._swr_blocked_bands:
       self.qso_panel.add_info(
           f"⚠ CQ blockiert — Band {band} SWR-Sperre."
       )
       self.control_panel.set_cq_active(False)  # Button-Toggle zurück
       return
   ```

4. **ui/mw_qso.py:_on_station_clicked (Z.143):**
   ```python
   band = self.settings.band.upper()
   if band in self._swr_blocked_bands:
       self.qso_panel.add_info(
           f"⚠ Anruf blockiert — Band {band} SWR-Sperre."
       )
       return
   ```

5. **core/auto_hunt.py:select_next (Z.224):** Constructor-Injection
   pattern. AutoHunt bekommt im `__init__` Referenz auf Set:

   ```python
   # In __init__:
   self._blocked_bands_ref: Optional[set[str]] = None

   # Setter (von MainWindow gerufen):
   def set_blocked_bands_ref(self, ref: set[str]) -> None:
       self._blocked_bands_ref = ref

   # In select_next Top:
   if self._blocked_bands_ref is not None:
       if self._band.upper() in self._blocked_bands_ref:
           return None  # silent skip
   ```

   Plus `mw_radio._run_auto_hunt` macht einen Info-Eintrag wenn skip
   stattfand (alle 30 Slots = 1 pro Minute, sonst Spam).

6. **core/omni_cq.py:on_cycle_start:** vor TX-Slot-Trigger Pre-Check
   analog (silent skip, kein Auto-Stop — OMNI bleibt aktiv-armed bis
   User toggelt).

#### C. Manueller TUNE (ui/mw_tx.py:_on_tune_clicked Z.65-96)

**Heute:** `radio.tune_on()` + `tune_off()` ohne Dauer-Begrenzung,
Watchdog aktiv, kein Post-SWR-Check.

**P63-Neuschnitt:**

```python
@Slot(bool)
def _on_tune_clicked(self, on: bool):
    if not self.radio.ip:
        return
    from PySide6.QtCore import QTimer
    from config.settings import get_tune_freq_mhz
    if on:
        # === START TUNE ===
        # AC4: Watchdog-Bypass setzen VOR tune_on
        self._tune_in_progress = True
        # 10W fest (Mike-Spec) — UNABHÄNGIG von settings.tune_power
        TUNE_POWER_W = 10
        # Dauer aus Setting
        duration_s = self.settings.get("tune_duration_s", 15)
        duration_s = 15 if duration_s not in (15, 30) else duration_s

        tune_freq = get_tune_freq_mhz(self.settings.band, self.settings.mode)
        self._tune_active = True
        if tune_freq is not None:
            self._tune_freq_mhz = tune_freq
            self.radio.set_frequency(tune_freq)
        else:
            self._tune_freq_mhz = self.settings.frequency_mhz

        # ANT1 + 10W + tune_on
        self.radio.set_tx_antenna("ANT1")
        self.radio.set_rfpower_direct(TUNE_POWER_W)
        self.radio.tune_on()
        self._update_statusbar()
        self.statusBar().showMessage(
            f"TUNEN — {TUNE_POWER_W}W auf ANT1 für {duration_s}s ...", 0)
        self.control_panel.set_freq_display(
            tune_freq if tune_freq is not None else self.settings.frequency_mhz,
            tune_active=True)
        print(f"[Tune] Manuell — {TUNE_POWER_W}W {duration_s}s")

        # Auto-Stop nach Dauer
        self._tune_auto_stop_token = object()
        _token = self._tune_auto_stop_token
        QTimer.singleShot(
            duration_s * 1000,
            lambda: self._tune_auto_stop_after(_token))
    else:
        # === STOP TUNE (manuell vom User) ===
        self._tune_auto_stop_after(None)  # token=None ⇒ unbedingt stop


def _tune_auto_stop_after(self, token):
    """Tune-Stop + Post-SWR-Check + Marker-Logik."""
    if token is not None and getattr(self, '_tune_auto_stop_token', None) is not token:
        return  # neuer TUNE-Click hat token gewechselt
    if not self._tune_active:
        return  # schon manuell gestoppt
    # tune_off
    self.radio.tune_off()
    self._tune_active = False
    self._tune_freq_mhz = None
    work_freq = self.settings.frequency_mhz
    self.radio.set_frequency(work_freq)
    # Power zurück auf Settings
    self.radio.set_power(self.settings.get("power_preset", 15))
    # UI
    self._update_statusbar()
    self.control_panel.set_freq_display(work_freq, tune_active=False)
    # Watchdog wieder aktiv
    self._tune_in_progress = False

    # Post-SWR-Check: aktueller Wert aus Control-Panel-Meter ablesen
    swr_now = self.control_panel.last_swr() or 1.0  # last_swr Helper (s.u.)
    swr_limit = self.settings.get("swr_limit", 3.0)
    band = self.settings.band.upper()

    from PySide6.QtWidgets import QMessageBox

    if swr_now <= swr_limit:
        # AC6: SWR ok → Marker freigeben + Diversity-Resume falls aktiv
        was_blocked = band in self._swr_blocked_bands
        self._swr_blocked_bands.discard(band)
        if was_blocked:
            self.qso_panel.add_info(f"✓ Band {band} freigegeben — SWR {swr_now:.1f}")
            print(f"[P63] Marker freigegeben — {band} SWR {swr_now:.1f}")
            # Falls Diversity aktiv: _check_diversity_preset triggert
            # automatisch Gain-Mess (fehlend) oder Diversity-Start (frisch).
            if self._rx_mode == "diversity":
                scoring = getattr(self._diversity_ctrl, 'scoring_mode', 'normal')
                ft_mode = self.settings.mode
                self._check_diversity_preset(self.settings.band, ft_mode, scoring)
    else:
        # AC7: SWR weiter zu hoch → Marker bleibt + Modal
        QMessageBox.warning(
            self,
            "Tuner konnte nicht matchen",
            f"SWR weiter {swr_now:.1f} > Limit {swr_limit:.1f}.\n"
            "Antenne prüfen."
        )
    print(f"[Tune] Stop — SWR {swr_now:.1f}, Limit {swr_limit:.1f}")
```

#### D. Watchdog-Bypass während manuellem TUNE

In `_on_swr_alarm` (Z.124) GANZ OBEN nach `is_transmitting`-Check:

```python
# AC4: Während manuellem TUNE komplett aus
if getattr(self, "_tune_in_progress", False):
    return
```

### 3.4 Verhalten — `tuner_present=False` (Monoband-Operator)

- **Gain-Mess-Pipeline (`_start_dx_tuning` Z.1329):** TUNE-Phase
  übersprungen. Z.1354-1380 nur ausführen wenn `tuner_present=True`:

  ```python
  if self.radio.ip and self.settings.get("tuner_present", True):
      # ... TUNE-Sequenz ...
  else:
      # Direkt zur Gain-Mess-Phase ohne TUNE
      self._proceed_to_gain_measure()
  ```

  *(Helper `_proceed_to_gain_measure` ist der Code-Block AB Z.1380
  raus-refactored — V3 prüft ob das schon ein Helper ist oder neu nötig.)*

- **TUNE-Button:** Hidden in `control_panel.py` Z.892-897. Hide-Logik
  in `_update_button_visibility` (Z.984-Bereich):

  ```python
  # P63: TUNE-Button nur sichtbar wenn tuner_present=True
  self.btn_tune.setVisible(self._tuner_present)
  ```

  Plus neue ControlPanel-Method `set_tuner_present(value: bool)`,
  gerufen von MainWindow beim Settings-Save.

- **SWR-Watchdog:** wie bisher, aber `_swr_blocked_bands.add` skip
  (siehe AC2 oben).

### 3.5 Helper: `ControlPanel.last_swr()`

Brauchen wir damit `_tune_auto_stop_after` den letzten SWR-Wert lesen
kann. ControlPanel speichert SWR aus `update_swr(value)` heute schon
für Display — neuer getter:

```python
# In ControlPanel:
def __init__(self, ...):
    ...
    self._last_swr_value: float = 1.0  # neu

def update_swr(self, value: float) -> None:
    self._last_swr_value = value
    # ... bestehender Display-Code ...

def last_swr(self) -> float:
    return self._last_swr_value
```

## 4. Settings-Dialog UI (ui/settings_dialog.py:_build_tab_ft8 Z.306)

Im Tab „FT8 & Diversity", oberhalb des Bandpilot-Blocks (Z.327 ff):

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

Plus Load (Z.564-Bereich):

```python
self.tuner_present_cb.setChecked(self.settings.get("tuner_present", True))
_dur = self.settings.get("tune_duration_s", 15)
_idx = 0 if _dur == 15 else 1
self.tune_duration_combo.setCurrentIndex(_idx)
```

Plus Save (Z.704 `_save_and_close`):

```python
self.settings.set("tuner_present", self.tuner_present_cb.isChecked())
self.settings.set("tune_duration_s", self.tune_duration_combo.currentData())
```

Plus Reset (Z.756):

```python
self.tuner_present_cb.setChecked(True)
self.tune_duration_combo.setCurrentIndex(0)
```

Plus Live-Apply nach `dialog.exec()` in `_on_settings_clicked`:

```python
# ControlPanel-Button-Sichtbarkeit live aktualisieren
self.control_panel.set_tuner_present(self.settings.get("tuner_present", True))
```

## 5. AC-Kriterien (Acceptance-Criteria)

| # | Was |
|---|---|
| AC1 | `_on_swr_alarm` ruft `_set_gain_measure_lock(False)` im Stop-Block (Bug-Fix) |
| AC2 | `_on_swr_alarm` setzt `_swr_blocked_bands.add(band.upper())` wenn `tuner_present=True` |
| AC3 | Tuner=False: KEIN Marker-Set, Modal-Text „Antenne prüfen" statt „bitte TUNE" |
| AC4 | `_tune_in_progress=True` während manuellem TUNE; `_on_swr_alarm` returnt sofort |
| AC5 | Manueller TUNE: 10W fest (`set_rfpower_direct(10)`), Dauer aus Setting (15 oder 30), Auto-Stop via QTimer |
| AC6 | Nach TUNE-Stop: SWR ≤ Limit → Marker entfernt + Diversity-Resume via `_check_diversity_preset` falls aktiv |
| AC7 | Nach TUNE-Stop: SWR > Limit → Marker bleibt + Modal „Tuner konnte nicht matchen" |
| AC8 | Pre-Check in 6 TX-Auto-Pfaden: `_check_diversity_preset`, `_handle_dx_tuning`, `_on_cq_clicked`, `_on_station_clicked`, `AutoHunt.select_next`, `omni_cq.on_cycle_start` |
| AC9 | Tuner=False: `_start_dx_tuning` überspringt TUNE-Phase, TUNE-Button hidden |
| AC10 | `_swr_blocked_bands` in-memory, App-Restart leert (kein Persist) |

## 6. Code-Plan (11 atomare Commits)

| # | Datei | Was |
|---|---|---|
| C1 | `config/settings.py` | DEFAULTS: `tuner_present=True`, `tune_duration_s=15` |
| C2 | `ui/settings_dialog.py` | Tab-FT8 UI + Load + Save + Reset + Hint-Texte |
| C3 | `ui/main_window.py` | `_swr_blocked_bands: set[str] = set()` + `_tune_in_progress=False` Init |
| C4 | `ui/mw_tx.py:_on_swr_alarm` | Lock-Release + Marker-Set + neues Modal + AC4 Watchdog-Bypass |
| C5 | `ui/mw_radio.py` | Marker-Pre-Check in `_check_diversity_preset` + `_handle_dx_tuning` + Tuner=False-Branch in `_start_dx_tuning` |
| C6 | `ui/mw_qso.py` + `core/auto_hunt.py` + `core/omni_cq.py` | Marker-Pre-Check in 4 Pfaden + `set_blocked_bands_ref`-Injection |
| C7 | `ui/mw_tx.py:_on_tune_clicked` + `_tune_auto_stop_after` | 10W fest, Dauer-Setting, Auto-Stop, Post-SWR-Check, Marker-Clear |
| C8 | `ui/control_panel.py` | TUNE-Button-Hide + `set_tuner_present` + `last_swr` Helper |
| C9 | `tests/test_p63_swr_block_marker.py` NEU | T1-T15 (siehe §7) |
| C10 | `main.py` | APP_VERSION 0.97.35 → 0.97.36 + `Appsicherungen/2026-05-15_v0.97.35_vor_p63/` |
| C11 | Doku | HISTORY/HANDOFF/CLAUDE/Memory/TODO/MEMORY.md |

## 7. Tests T1-T15

| # | Test | Was geprüft |
|---|---|---|
| T1 | `test_p63_swr_alarm_releases_lock` | `_on_swr_alarm` setzt `_gain_measure_locked=False` |
| T2 | `test_p63_swr_alarm_sets_marker_when_tuner` | `tuner_present=True` → `_swr_blocked_bands.add(band.upper())` |
| T3 | `test_p63_swr_alarm_no_marker_when_no_tuner` | `tuner_present=False` → Set bleibt leer |
| T4 | `test_p63_marker_blocks_omni` | OMNI auf rotem Band → `add_info` + skip |
| T5 | `test_p63_marker_blocks_auto_hunt_select_next` | `select_next` returnt None |
| T6 | `test_p63_marker_blocks_normal_cq` | `_on_cq_clicked` skipt + `set_cq_active(False)` |
| T7 | `test_p63_marker_blocks_diversity_preset` | `_check_diversity_preset` early-return |
| T8 | `test_p63_manual_tune_allowed_on_red_band` | `_on_tune_clicked(True)` läuft durch (kein Pre-Check) |
| T9 | `test_p63_tune_uses_10w_fixed` | `set_rfpower_direct` mit 10 aufgerufen unabhängig von `tune_power`-Setting |
| T10 | `test_p63_tune_duration_15_30` | Setting 15 → QTimer 15000ms, Setting 30 → 30000ms |
| T11 | `test_p63_tune_in_progress_bypasses_watchdog` | `_tune_in_progress=True` → `_on_swr_alarm` returnt sofort |
| T12 | `test_p63_post_tune_good_clears_marker` | SWR<Limit → `discard(band)` + Diversity-Resume gerufen |
| T13 | `test_p63_post_tune_bad_keeps_marker` | SWR>Limit → Set behält Eintrag + Modal |
| T14 | `test_p63_no_tuner_skips_auto_tune` | `tuner_present=False` → `_start_dx_tuning` ruft NICHT `tune_on` |
| T15 | `test_p63_no_tuner_hides_button` | `set_tuner_present(False)` → `btn_tune.isVisible() == False` |

## 8. Aus Scope (NICHT bauen)

- Marker-Persist über App-Restart (Mike-Spec: in-memory)
- Power-Variation 5W/7W beim TUNE (LDG: 10W ist Standard)
- 45s TUNE-Option (LDG: max 15s Full-Tune)
- Watchdog mit dynamischem Threshold während TUNE
- TUNE-Counter / Statistik
- Manueller Marker-Override via Settings („Marker zurücksetzen"-Button)

## 9. Field-Tests F1-F10 (für Mike nach Push)

| # | Was |
|---|---|
| F1 | SWR-Alarm bei 17m: Modal kommt sauber, Text „Band gesperrt — bitte TUNE" |
| F2 | Nach Modal: TUNE-Button klickbar, OMNI/Hunt blockiert mit Info |
| F3 | Manueller TUNE 15s 10W läuft durch, Auto-Stop nach 15s |
| F4 | TUNE-Erfolg auf 17m → Marker grün → Gain-Mess startet automatisch (mit P62-Pause) |
| F5 | TUNE-Misserfolg → Modal „Tuner konnte nicht matchen", Marker bleibt rot |
| F6 | Settings „Tuner=NEIN": TUNE-Button hidden, Gain-Mess ohne Auto-TUNE |
| F7 | Settings „Tuner=NEIN": SWR-Alarm = Modal + Stop, KEIN Marker |
| F8 | Settings „TUNE-Dauer 30s": manueller TUNE läuft 30s |
| F9 | Marker pro Band: 17m rot, 20m wechseln → läuft normal |
| F10 | App-Restart: alle Marker weg |

## 10. Risiken & Open Points

1. **`select_next`-Injection** — saubere Lösung wäre `blocked_bands_ref`
   als optionalen Constructor-Parameter. AutoHunt wird in `main_window.py`
   instanziiert → wir setzen `_blocked_bands_ref` nach `__init__`.
   V3-Punkt: prüfen ob das die richtige Stelle ist oder ob's einen
   factory-Pattern gibt der das eleganter macht.

2. **`omni_cq.py`-Pre-Check** — OMNI ist eigenes Modul (P7), Pre-Check
   in `on_cycle_start` (signal-getriggert). Selbe Injection-Logik wie
   AutoHunt? ODER: einfacher Helper `MainWindow._is_band_blocked()` der
   von beiden gerufen wird (KISS). V3 entscheidet.

3. **`_start_dx_tuning` Refactor** — Z.1329-1400+ hat verschachtelten
   Code für TUNE-Sequenz. Wenn `tuner_present=False`, müssen wir den
   ganzen `tune_on/QTimer/tune_off`-Block überspringen UND direkt zur
   Gain-Mess-Phase springen. Risiko: dort wird Power gesetzt + nach Tune
   zurück gestellt. Bei Skip muss Power-State sauber bleiben.

4. **`_handle_dx_tuning` (KALIBRIEREN-Button) Z.1263:** ruft auch
   `_start_dx_tuning`. Pre-Check muss dort auch rein (sonst kann User
   via Settings-Dialog umgehen).

5. **Concurrency:** `_swr_blocked_bands` wird aus Qt-Slot-Threads
   modifiziert (alle Pfade sind GUI-Thread). KISS = `set[str]` ohne
   Lock (Python GIL atomar für `add`/`discard`/`in`).

6. **R1-Spezial-Frage:** soll `_tune_in_progress` auch in `_handle_dx_tuning`
   (KALIBRIEREN) und `_start_dx_tuning` (Auto-TUNE) gesetzt werden?
   Heute fehlt das — also läuft Watchdog dort. Aber: in der Auto-TUNE-
   Phase (P62 1s Pause + tune_on 3s) ist explizit TX aktiv mit 10W,
   wenn SWR>Limit dort = legitimer Stop. Diskussions-Punkt.

## 11. Workflow nach V1

→ V2 Self-Review (Code-Realität-Check, Halluzinations-Check)
→ R1 DeepSeek-V4-pro mit 8 Touch-Files
→ V3 finalisieren (R1-Findings einbauen)
→ Backup
→ C1-C11 atomar
→ Tests T1-T15 grün (1306 → ~1321)
→ Final-R1
→ Doku (HISTORY/HANDOFF/CLAUDE/Memory/TODO/MEMORY.md)
→ Test-Plan für Mike (F1-F10)
