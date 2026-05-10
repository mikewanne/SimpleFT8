# P22.PRESET-ATOMARITAET + P8.MESS-MODAL — V3 (Compact-fest, EINZIGE WAHRHEIT)

## Aenderungen V2 → V3 (nach R1 + Mike-Klaerung)

- **P8 (Mess-Modal) eingegliedert in P22** — Mike-Anweisung 10.05. nach
  R1: Wenn Antennenmessung laeuft, MUSS UI gesperrt sein (kein Bandwechsel,
  kein Modus, kein Hunt, kein CQ). Modal verhindert genau das.
- **Stall-Detector ENTFAELLT** — Mike: „Q1 ist nicht bestaetigt das es
  an der Antennenmessung lag. Hänger war bei QSO-Ende, nicht bei Mess.
  Mess hatte ein anderes Problem (nicht gestartet + nur eine Antenne)."
  Wir bauen keinen Fallback fuer ein Problem dessen Wurzel wir nicht
  diagnostiziert haben. Wenn das Symptom zurueckkommt → echte Diagnose.
- **R1-K1** angenommen: staged erst nach erfolgreichem `os.replace`
  entfernen (kein Daten-Verlust bei Disk-Fehler).
- **R1-K2** entfaellt teilweise: Modal verhindert Bandwechsel/Mode-Wechsel
  mid-Mess → kein discard_staged dort noetig. Nur App-Quit + Cancel-Button
  + Adaptiv-Stop-Branch.
- **R1-K3** angenommen: `commit_with_ratio`/`save_gain`/`save_ratio`
  fangen Disk-Exception + return False statt re-raise. Aufrufer loggt.
- **R1-K4** entfaellt: kein `_handle_phase3_stall` mehr (kein Stall-Detector).
- **R1-S1** angenommen: Code-Kommentar an `is_valid_gain`.
- **R1-S2** angenommen: T6/T7 als Spy-Pattern (Spy auf
  `store.stage_gain`), nicht E2E-Mock-heavy.
- **R1-S3** angenommen: QSO-mid-Phase-3 nicht relevant ohne Stall-Detector.
- **R1-S4** entfaellt mit Stall-Detector.
- **Q3** = (a) Adaptiv-Stop weiter ohne Persist (Mike + R1).

## 1. Wurzel-Bedingung im Code (verifiziert)

Zwei separate Schreibstellen, kein gemeinsamer Commit:

| Phase | Schreibstelle | Trigger |
|---|---|---|
| Phase 2 (Gain) | `ui/mw_radio.py:1203` `store.save_gain(...)` | DXTuneDialog akzeptiert |
| Phase 3 (Ratio) | `ui/mw_cycle.py:273` `_store.save_ratio(...)` | `phase: measure→operate` in `_evaluate` |

`_evaluate` wird gerufen wenn `_measure_step >= MEASURE_CYCLES` (FT8: 6
Zyklen ≈ 1.5 Min) oder bei Adaptiv-Stop (`_was_early_stopped = True`).

Wenn `_evaluate` nie laeuft (Antennen-Switch greift nicht,
`_measure_step` bleibt 0): `phase = "measure"` ewig, `save_ratio` nie.
Half-State auf Disk: nur `gain_*`. Restart triggert
`_check_diversity_preset` Branch „gain fresh + ratio missing" →
Auto-Phase-3-Versuch → haengt wieder.

`is_valid_gain` (`core/preset_store.py:125-131`) prueft NUR
`gain_timestamp`. Half-State sieht aus wie Full-State.

## 2. Loesung — zwei zusammenhaengende Bausteine

### Baustein A — Atomares Persist (P22)

- Phase 2 schreibt nicht mehr sofort auf Disk; Wert lebt im Memory-
  Buffer `_staged: dict[str, dict]` im PresetStore.
- Phase 3 erfolgreich → atomar `gain_*` + `ratio_*` zusammen schreiben.
- Phase 3 abgebrochen/Cancel/App-Quit → staged verwerfen, kein Disk-Write.
- Restart liest `is_valid_gain == False` fuer alle Eintraege ohne
  `ratio`-Feld → faellt sauber in `gain missing`-Pfad (volle Pipeline).

### Baustein B — Mess-Modal (P8)

- Sobald `_enable_diversity()` Phase 3 startet → Modal-Dialog
  (`MessStatusDialog`) oeffnet sich.
- WindowModality `WindowModal` — sperrt Input am Hauptfenster, laesst
  aber Qt-Event-Loop laufen (Decoder-Signale werden weiter zugestellt).
- Inhalt: Titel, aktuelle Antenne (A1/A2), Slot-Counter („3 von 6"),
  Restzeit, Cancel-Button.
- Schliesst automatisch beim Phase-Wechsel `measure → operate` (also
  nach erfolgreichem `commit_with_ratio` ODER nach Adaptiv-Stop).
- Cancel-Button: bricht Mess ab → `discard_staged` →
  `_disable_diversity()` zurueck auf Normal-Modus.
- Verhindert in der Mess-Phase: Bandwechsel, Mode-Wechsel, Hunt-Klick,
  CQ-Klick — alles greift erst wieder wenn Modal geschlossen.

## 3. Akzeptanzkriterien

A1. **Atomares Persist:** `gain_*` und `ratio_*` werden nur gemeinsam
    auf Disk geschrieben. Phase 2 alleine produziert keinen Disk-Eintrag.

A2. **Half-State-Reject beim Load:** `is_valid_gain` returnt False fuer
    Eintraege ohne `ratio`-Feld.

A3. **Restart sauber:** Wenn Phase 3 zwischen Phase 2 und Disk-Write
    abbricht (Crash, App-Quit, Cancel), liest naechster Restart
    `is_valid_gain == False` → volle Pipeline.

A4. **Disk-Fehler ohne Daten-Verlust (R1-K1):** Bei
    `_save_locked`-Exception bleibt staged-Eintrag im Memory.
    `commit_with_ratio` returnt False, App crasht nicht.

A5. **Disk-Fehler ohne App-Crash (R1-K3):** Alle Schreibmethoden
    fangen Exception, loggen, returnen False. Kein re-raise in den GUI-
    Thread.

A6. **Atomic File Write:** `_save_locked` nutzt `tempfile.NamedTemporary
    File(dir=parent)` + `os.replace`. Verhindert korrupte JSON bei
    Mid-Write-Crash.

A7. **Mess-Modal sperrt UI:** Waehrend Phase 3 ist Hauptfenster nicht
    klickbar (Bandwechsel, Mode-Wechsel, Hunt, CQ alle gesperrt).
    Decoder laeuft weiter (WindowModal, nicht ApplicationModal).

A8. **Modal schliesst bei Phase-Wechsel:** Sobald
    `_diversity_ctrl.phase == "operate"` (nach `_evaluate`), schliesst
    Modal automatisch.

A9. **Cancel-Button im Modal:** discard_staged + Diversity-Disable +
    Modal schliessen. Kein Half-State, sauberes Aufraeumen.

A10. **App-Quit waehrend Mess:** `closeEvent` cleart alle staged
     Eintraege in beiden Stores. Modal hat keinen Effekt darauf
     (closeEvent kommt vom Hauptfenster bzw. Cmd-Q).

A11. **Adaptiv-Stop bleibt ohne Persist (Q3 a):** Bei
     `_was_early_stopped == True` ruft `mw_cycle.py:_handle_diversity_measure`
     weiter `discard_staged` (kein Commit) — wie bisher kein Cache-
     Eintrag fuer Adaptiv-Stop.

A12. **Diversity-Algorithmus unangetastet:** Mess-Algorithmus,
     Threshold, Median, Antennen-Switch — bleiben 1:1.

A13. **Mess-Modal-Live-Updates:** Modal zeigt aktuelle Antenne (von
     `_diversity_ctrl.current_ant`), Slot-Counter
     (`_diversity_ctrl.measure_step / MEASURE_CYCLES`), Restzeit
     (`(MEASURE_CYCLES - measure_step) * cycle_dur`). Updates ueber
     QTimer 1s.

A14. **Cancel-Button beendet Encoder/CQ vorher:** Cancel waehrend
     Mess-Phase ist sicher: Phase 3 ist read-only fuer Encoder. Modal-
     Cancel ruft `_disable_diversity()` was bereits sauber zurueckraeumt.

## 4. Architektur

### 4a. PresetStore-Erweiterung (`core/preset_store.py`)

```python
# Neue Imports
import os, tempfile

class PresetStore:
    def __init__(self, filename: str):
        ...
        self._staged: dict[str, dict] = {}   # NEU: Memory-Buffer

    # ── NEU: Stage / Commit / Discard ────────────────────────────────

    def stage_gain(self, band, ft_mode, *, rxant, ant1_gain, ant2_gain,
                   ant1_avg=0.0, ant2_avg=0.0) -> None:
        """Phase-2-Werte in Memory parken. KEIN Disk-Write."""
        key = self._key(band, ft_mode)
        with self._lock:
            self._staged[key] = {
                "rxant":     rxant,
                "ant1_gain": int(ant1_gain),
                "ant2_gain": int(ant2_gain),
                "ant1_avg":  round(float(ant1_avg), 1),
                "ant2_avg":  round(float(ant2_avg), 1),
            }

    def commit_with_ratio(self, band, ft_mode, *, ratio, dominant) -> bool:
        """Phase-3-Erfolg: staged Gain + ratio atomar persistieren.

        R1-K1: staged wird erst nach erfolgreichem _save_locked entfernt,
        damit bei Disk-Fehler nichts verloren geht.
        R1-K3: Disk-Exception wird gefangen, returnt False statt re-raise.
        """
        key = self._key(band, ft_mode)
        now = time.time()
        with self._lock:
            staged = self._staged.get(key)
            if staged is None:
                return False  # nichts zu committen → Aufrufer-Bug
            # Kopie bauen, NICHT pop'en bevor Disk-Write fertig ist
            entry = dict(self._data.get(key) or {})
            entry.update(staged)
            entry["gain_timestamp"]  = now
            entry["ratio"]           = ratio
            entry["dominant"]        = dominant or "A1"
            entry["ratio_timestamp"] = now
            entry["measured"]        = time.strftime("%Y-%m-%d %H:%M")
            old_entry = self._data.get(key)
            self._data[key] = entry
            try:
                self._save_locked()
            except Exception as exc:
                # Rollback: in-memory entry zuruecksetzen, staged bleibt
                if old_entry is None:
                    self._data.pop(key, None)
                else:
                    self._data[key] = old_entry
                print(f"[PresetStore] commit_with_ratio Disk-Fehler "
                      f"{key}: {exc}. Staged bleibt erhalten.")
                return False
            # Erst nach Erfolg staged entfernen
            self._staged.pop(key, None)
        return True

    def discard_staged(self, band, ft_mode) -> bool:
        """Staged-Eintrag verwerfen. Returns True wenn etwas weg war."""
        key = self._key(band, ft_mode)
        with self._lock:
            return self._staged.pop(key, None) is not None

    def discard_all_staged(self) -> int:
        """App-Quit: alles wegraeumen. Returns Anzahl entfernter Keys."""
        with self._lock:
            n = len(self._staged)
            self._staged.clear()
            return n

    def has_staged(self, band, ft_mode) -> bool:
        with self._lock:
            return self._key(band, ft_mode) in self._staged

    # ── ANGEPASST: is_valid_gain Half-State-Reject ───────────────────

    def is_valid_gain(self, band, ft_mode) -> bool:
        """True wenn Gain-Kalibrierung vorhanden UND < 6h alt UND ratio
        existiert. Half-State (gain ohne ratio) wird abgelehnt.

        R1-S1: Diese Methode ist fuer Diversity-Stores gedacht. Normal-
        Mode-Presets (Settings.normal_presets) nutzen separate Logik.
        """
        with self._lock:
            entry = self._data.get(self._key(band, ft_mode))
        if not entry or "gain_timestamp" not in entry:
            return False
        if "ratio" not in entry:                    # NEU: Half-State raus
            return False
        if (time.time() - entry["gain_timestamp"]) >= GAIN_VALIDITY_SECONDS:
            return False
        return True

    # ── ANGEPASST: _save_locked atomic + Exception-Handling ──────────

    def _save_locked(self) -> None:
        """Atomic Write via tempfile + os.replace.

        Bei Exception: tempfile aufraeumen, Exception re-raise (Aufrufer
        muss fangen). save_gain/save_ratio wickeln das dann ab (return
        False statt re-raise nach oben).
        """
        self._filepath.parent.mkdir(parents=True, exist_ok=True)
        tmp = tempfile.NamedTemporaryFile(
            mode="w", dir=str(self._filepath.parent),
            delete=False, prefix=".tmp_", suffix=".json")
        try:
            json.dump(self._data, tmp, indent=2)
            tmp.flush()
            os.fsync(tmp.fileno())
            tmp.close()
            os.replace(tmp.name, str(self._filepath))
        except Exception:
            try:
                tmp.close()
            except Exception:
                pass
            try:
                os.unlink(tmp.name)
            except OSError:
                pass
            raise

    # ── save_gain / save_ratio: Exception-Handling (R1-K3) ────────────

    def save_gain(self, band, ft_mode, *, ...) -> bool:
        # bestehende Logik, aber:
        try:
            self._save_locked()
        except Exception as exc:
            print(f"[PresetStore] save_gain Disk-Fehler: {exc}")
            return False
        return True

    def save_ratio(self, band, ft_mode, *, ...) -> bool:
        # gleiche Behandlung, returnt jetzt bool
        ...
```

### 4b. Pipeline-Anpassung (`ui/mw_radio.py`)

`_on_dx_tune_accepted` (Z. 1191) Diversity-Pfad:

```
if rx_mode == "normal":
    store.save_gain(...)            # unveraendert: kein Phase-3-Anschluss
    return

# rx_mode == "diversity":
if pending_ratio == "fresh":
    # Gain stale war + Ratio frisch im Cache → Cache-Reuse, kein Stage
    store.save_gain(...)            # direkter Disk-Write (kein Phase-3 mehr)
    cache_reuse → return

# Volle Pipeline (pending_dx_diversity ODER vorher gain stale ohne fresh ratio):
store.stage_gain(...)               # NUR Memory, kein Disk
_pending_dx_diversity = True        # Konsistenz-Garantie
_enable_diversity → Phase 3 startet → Modal oeffnet
```

### 4c. Phase-3-Erfolgs-Pfad (`ui/mw_cycle.py:259-280`)

```python
if self._diversity_ctrl.phase == "operate":
    if not getattr(self, '_diversity_in_operate', False):
        self._diversity_in_operate = True
        ...
        _early_stopped = getattr(self._diversity_ctrl, '_was_early_stopped', False)
        _scoring = getattr(self._diversity_ctrl, 'scoring_mode', 'normal')
        _store = (getattr(self, '_dx_store', None) if _scoring == "dx"
                  else getattr(self, '_standard_store', None))

        if _store and not _early_stopped:
            ok = _store.commit_with_ratio(
                self.settings.band, self.settings.mode,
                ratio=self._diversity_ctrl.ratio,
                dominant=self._diversity_ctrl.dominant,
            )
            if not ok:
                # Fallback: Disk-Fehler oder kein staged → alter save_ratio
                # damit Cache nicht ganz verloren geht
                print("[mw_cycle] commit_with_ratio failed → "
                      "save_ratio Fallback")
                _store.save_ratio(
                    self.settings.band, self.settings.mode,
                    ratio=self._diversity_ctrl.ratio,
                    dominant=self._diversity_ctrl.dominant,
                )
        elif _early_stopped:
            # A11: Adaptiv-Stop = kein Persist (v0.91 Cache-Schutz)
            if _store:
                _store.discard_staged(self.settings.band, self.settings.mode)
            print("[mw_cycle] Adaptiv-Stop-Ratio NICHT gecached "
                  "(weniger Messdaten als regulaerer Pfad)")

        # Bestehender Settings-Bw-Compat-Schreiber bleibt unangetastet
        self.settings.save_diversity_preset(...)
        ...
        # NEU: Mess-Modal schliessen wenn offen
        if hasattr(self, '_mess_status_dialog') and self._mess_status_dialog:
            self._mess_status_dialog.accept()
            self._mess_status_dialog = None
```

### 4d. Mess-Modal (`ui/mess_status_dialog.py` NEU)

```python
"""SimpleFT8 MessStatusDialog — Modal waehrend Diversity-Antennen-Mess.

Sperrt UI (WindowModal) damit Mike nicht mid-Mess Bandwechsel/Mode-
Wechsel macht. Laesst Qt-Event-Loop laufen → Decoder-Signale kommen
weiter durch.

Schliesst sich:
- automatisch wenn Phase = operate (mw_cycle ruft .accept())
- per Cancel-Button (Aufrufer cancelt Mess + raeumt staged auf)
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QProgressBar,
    QPushButton, QFrame,
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont


class MessStatusDialog(QDialog):
    def __init__(self, diversity_ctrl, parent=None):
        super().__init__(parent)
        self._ctrl = diversity_ctrl
        self._cancelled = False

        self.setWindowTitle("Diversity-Antennen werden eingemessen")
        self.setFixedSize(440, 240)
        self.setModal(True)
        self.setWindowModality(Qt.WindowModality.WindowModal)
        # ApplicationModal wuerde Decoder-Signale blocken — verboten!

        self._setup_ui()
        self._tick_timer = QTimer(self)
        self._tick_timer.timeout.connect(self._update_view)
        self._tick_timer.start(500)
        self._update_view()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        title = QLabel("Antennen-Vergleich laeuft")
        title.setStyleSheet("color:#7CC; font-size:14pt; font-weight:bold")
        layout.addWidget(title)
        self._lbl_ant = QLabel("Antenne: —")
        self._lbl_step = QLabel("Schritt: 0 / 6")
        self._lbl_remaining = QLabel("Restzeit: —")
        for w in (self._lbl_ant, self._lbl_step, self._lbl_remaining):
            w.setStyleSheet("color:#CCC; font-size:11pt")
            layout.addWidget(w)
        self._progress = QProgressBar()
        self._progress.setRange(0, max(1, self._ctrl.MEASURE_CYCLES))
        layout.addWidget(self._progress)
        hint = QLabel("Bitte waehrend der Messung keine Bedienung —\n"
                      "App schliesst dieses Fenster automatisch.")
        hint.setStyleSheet("color:#888; font-size:9pt; font-style:italic")
        layout.addWidget(hint)
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self._btn_cancel = QPushButton("Messung abbrechen")
        self._btn_cancel.clicked.connect(self._on_cancel)
        btn_row.addWidget(self._btn_cancel)
        layout.addLayout(btn_row)

    def _update_view(self):
        try:
            ant = getattr(self._ctrl, 'current_ant', None) or "—"
            step = self._ctrl.measure_step
            total = self._ctrl.MEASURE_CYCLES
            remaining_cycles = max(0, total - step)
            # Cycle-Dauer aus Modus ableiten — uebergeben oder hardcoded 15s
            cycle_dur = getattr(self, '_cycle_dur_s', 15.0)
            remaining_s = int(remaining_cycles * cycle_dur)
            self._lbl_ant.setText(f"Antenne: {ant}")
            self._lbl_step.setText(f"Schritt: {step} / {total}")
            self._lbl_remaining.setText(f"Restzeit: ~{remaining_s}s")
            self._progress.setValue(step)
        except Exception as exc:
            print(f"[MessStatusDialog] update_view Fehler: {exc}")

    def set_cycle_dur(self, sec: float):
        self._cycle_dur_s = float(sec)

    def _on_cancel(self):
        self._cancelled = True
        self.reject()

    @property
    def cancelled(self) -> bool:
        return self._cancelled

    def closeEvent(self, ev):
        try:
            self._tick_timer.stop()
        except Exception:
            pass
        super().closeEvent(ev)
```

### 4e. Modal-Lifecycle (`ui/mw_radio.py` + `ui/mw_cycle.py`)

`mw_radio.py` Helper hinzufuegen:

```python
def _open_mess_status_dialog(self):
    """Oeffnet Mess-Modal sobald Phase 3 startet."""
    if getattr(self, '_mess_status_dialog', None):
        return  # schon offen
    from ui.mess_status_dialog import MessStatusDialog
    dlg = MessStatusDialog(self._diversity_ctrl, parent=self)
    cycle_s = self._cycle_seconds_for_mode(self.settings.mode)
    dlg.set_cycle_dur(cycle_s)
    dlg.rejected.connect(self._on_mess_status_cancelled)
    self._mess_status_dialog = dlg
    dlg.show()  # NICHT exec — exec wuerde Event-Loop blocken

def _on_mess_status_cancelled(self):
    """Cancel-Button im Mess-Modal: discard + Diversity aus."""
    dlg = self._mess_status_dialog
    self._mess_status_dialog = None
    if not dlg or not dlg.cancelled:
        return  # auto-close (operate-Phase) → kein Cancel-Pfad
    print("[Diversity] Mess vom User abgebrochen — Cleanup")
    band, mode = self.settings.band, self.settings.mode
    for store in (getattr(self, '_standard_store', None),
                  getattr(self, '_dx_store', None)):
        if store:
            store.discard_staged(band, mode)
    self._disable_diversity()
```

`_enable_diversity` (mw_radio.py — Zeile suchen): Nach
`self._diversity_ctrl.start_measure(...)` Helper-Aufruf einfuegen:

```python
self._open_mess_status_dialog()
```

`mw_cycle.py:259+` (siehe 4c): nach `commit_with_ratio` Modal schliessen
via `self._mess_status_dialog.accept()`.

### 4f. App-Quit (`ui/main_window.py:closeEvent`)

```python
def closeEvent(self, event):
    # NEU: Staged Eintraege verwerfen (kein Half-State auf Disk)
    for store in (getattr(self, '_standard_store', None),
                  getattr(self, '_dx_store', None)):
        if store:
            n = store.discard_all_staged()
            if n:
                print(f"[App-Quit] {n} staged Preset-Eintrag(e) verworfen")
    # bestehende Logik
    ...
```

## 5. Files & Aenderungen

| Datei | Aenderung |
|---|---|
| `core/preset_store.py` | + `stage_gain`, `commit_with_ratio`, `discard_staged`, `discard_all_staged`, `has_staged` + `is_valid_gain` Half-State-Reject + atomic `_save_locked` + `save_gain`/`save_ratio` Exception-Catch |
| `ui/mess_status_dialog.py` | NEU — `MessStatusDialog` (WindowModal, Tick-Timer, Cancel-Button) |
| `ui/mw_radio.py` | Z. 1203 Diversity-Pfad: `save_gain` → `stage_gain` + `_pending_dx_diversity = True` Garantie. + `_open_mess_status_dialog`, `_on_mess_status_cancelled`. + Modal-Open in `_enable_diversity`. |
| `ui/mw_cycle.py` | Z. 273 `save_ratio` → `commit_with_ratio` + Adaptiv-Stop-Branch ruft `discard_staged` + Modal-Schliessen nach commit. |
| `ui/main_window.py` | `closeEvent` cleart staged in beiden Stores. |
| `tests/test_preset_store.py` | + 5 Tests (T1-T5) |
| `tests/test_p22_preset_atomic.py` | NEU: T6-T11 (Pipeline + Modal + Exception) |
| `main.py` | APP_VERSION 0.96.4 → 0.96.5 |
| `HISTORY.md` | Versions-Eintrag |
| `HANDOFF.md` | Stand-Update |
| Memory | `feedback_atomic_persist_pattern.md` Lesson |

## 6. Tests V3

| # | Name | Was geprueft |
|---|---|---|
| T1 | `test_stage_gain_no_disk_write` | `stage_gain` schreibt nichts ins File |
| T2 | `test_commit_with_ratio_writes_atomic` | beide Timestamps + ratio + dominant gesetzt + File aktualisiert + staged danach leer |
| T3 | `test_commit_without_stage_returns_false` | `commit_with_ratio` ohne stage → False, nichts geschrieben |
| T4 | `test_commit_with_ratio_disk_error_keeps_staged` | mock `_save_locked` raise → returnt False, staged bleibt, in-memory rollback (R1-K1) |
| T5 | `test_discard_staged_clears_memory` | nach `discard_staged` ist `has_staged` False |
| T6 | `test_is_valid_gain_rejects_half_state` | File mit `gain_*` ohne `ratio` → `is_valid_gain == False` |
| T7 | `test_save_gain_returns_false_on_disk_error` | mock save raise → returnt False, kein App-Crash (R1-K3) |
| T8 | `test_save_locked_atomic_uses_tempfile` | mock `os.replace` raise → tempfile geloescht, ZielFile nicht angefasst |
| T9 | `test_pipeline_diversity_uses_stage_then_commit` | Spy auf `store.stage_gain` in `_on_dx_tune_accepted` Diversity-Pfad |
| T10 | `test_pipeline_normal_uses_save_gain_direct` | Normal-Mode ruft `save_gain` direkt (kein staged) |
| T11 | `test_pipeline_pending_ratio_fresh_uses_save_gain_direct` | Cache-Reuse-Pfad ruft `save_gain` direkt (kein staged) |
| T12 | `test_phase3_success_calls_commit_with_ratio` | Spy auf `store.commit_with_ratio` im phase=operate-Uebergang |
| T13 | `test_phase3_adaptive_stop_calls_discard_staged` | `_was_early_stopped == True` → `discard_staged` statt `commit` |
| T14 | `test_close_event_discards_all_staged` | `closeEvent` cleart staged in beiden Stores |
| T15 | `test_mess_status_dialog_window_modal` | `MessStatusDialog.windowModality() == WindowModal` (NICHT ApplicationModal) |
| T16 | `test_mess_status_dialog_cancel_emits_rejected` | Cancel-Button → `rejected` Signal + `cancelled == True` |
| T17 | `test_mess_status_dialog_auto_close_on_operate` | accept() schliesst Modal ohne `cancelled` Flag |
| T18 | `test_multi_band_stage_independent` | 40m_FT8 + 20m_FT8 staged parallel, getrennt commit/discard |

T9/T10/T11/T12/T13: **Spy-Pattern** (R1-S2) — Spy auf `store.X`-Methoden,
nicht E2E-Mock-heavy.

## 7. Atomare Commits geplant

- **C1** `core/preset_store.py` — `stage_gain`/`commit_with_ratio`/
  `discard_staged`/`discard_all_staged`/`has_staged` + `is_valid_gain`
  Reject + atomic `_save_locked` + Exception-Catch in `save_gain`/
  `save_ratio`. Alle alten Methoden bleiben bestehen.
- **C2** `tests/test_preset_store.py` — T1-T8 (Unit-Tests des Stores)
- **C3** `ui/mess_status_dialog.py` — NEU MessStatusDialog Modul
- **C4** `ui/mw_radio.py` — `_on_dx_tune_accepted` Diversity-Pfad auf
  `stage_gain` + `_open_mess_status_dialog` + `_on_mess_status_cancelled`
  + Modal-Open in `_enable_diversity`
- **C5** `ui/mw_cycle.py` — `commit_with_ratio` + Adaptiv-Stop discard +
  Modal-Schliessen
- **C6** `ui/main_window.py` — `closeEvent` staged-Cleanup
- **C7** `tests/test_p22_preset_atomic.py` — T9-T18 (NEU, E2E-Spy +
  Modal + Pipeline)
- **C8** `main.py` APP_VERSION → 0.96.5 + HISTORY/HANDOFF/Memory-
  Updates

## 8. Field-Test (5 Punkte) nach Code-Fertigstellung

**F1.** App-Start in Diversity DX. Erwartung: Modal oeffnet sich,
zeigt Antenne + Schritt + Restzeit, Hauptfenster gesperrt
(Bandwechsel-Klick = kein Effekt).

**F2.** Mess laeuft sauber durch (6 Schritte FT8). Erwartung: Modal
schliesst sich automatisch nach `phase=operate`. File enthaelt
`gain_*` UND `ratio_*` mit gleichem Timestamp.

**F3.** Mid-Mess Cancel-Button klicken. Erwartung: Modal weg,
Diversity disabled, App auf Normal-Mode zurueck. File: kein neuer
Eintrag (alter Stand bleibt).

**F4.** Mid-Mess Cmd-Q. Erwartung: App quit, beim naechsten Start
ist `is_valid_gain == False` (Half-State weg), `_check_diversity_preset`
geht in `gain missing`-Branch (volle Pipeline).

**F5.** Disk-Permission-Fehler simulieren (chmod 000 auf
`~/.simpleft8/kalibrierung/`). App startet, Diversity-Mess laeuft, beim
Commit kommt Fehler. Erwartung: App crasht NICHT, Log-Eintrag, Modal
schliesst sich (Phase=operate erreicht), staged bleibt im Memory.

## 9. Was V3 NICHT macht

- KEIN Stall-Detector (Q1 unbestaetigt — Mike-Wurzel-Diagnose pending).
- KEIN `_handle_phase3_stall` (entfaellt mit Stall-Detector).
- KEIN `discard_staged` bei `_on_band_changed`/`_on_mode_changed`
  (Modal verhindert das).
- KEIN Refactor des Diversity-Mess-Algorithmus.
- KEIN Anfassen der Legacy-Settings-Pfade
  (`settings.save_dx_preset` / `settings.save_diversity_preset`).
- KEIN Auto-Resume-Logik (Cancel = User-Entscheidung, manueller
  Restart noetig).

## 10. Aufwand

V3 schaetzt: ~3h Code + 30 Min Tests-Schreiben + 30 Min Doku.

## 11. Mike-Freigabe

- [ ] Q1 = NICHT bauen (Stall-Detector raus) — Mike bestaetigt 10.05.
- [ ] Q2 = Mess-Modal sperrt UI (P8 + P22 zusammen) — Mike bestaetigt
- [ ] Q3 = Adaptiv-Stop weiter ohne Persist — Mike bestaetigt
- [ ] V3-Plan bereit fuer Plan-Mode + Code

Mike-Anmerkung: Q1-Wurzel separate Diagnose-Aufgabe (Antennen-Switch
greift nicht beim Mess-Start in DX). Sollte als P23 in TODO landen
sobald V3 fertig.
