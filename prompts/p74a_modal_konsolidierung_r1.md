# R1 — P74-A Modal-Konsolidierung (Variante D-X Hybrid)

## Was ich will

Du bist Reviewer. Kein Code generieren. Nur Findings.

**Format:** Severity (🔴 ROT / 🟠 ORANGE / 🟡 GELB / 🟢 OK), Datei:Zeile,
Was, Warum, Vorschlag. Keep es knapp.

**Frist:** Liefere präzise — der Code wird DANACH geschrieben, nicht jetzt.

---

## Kontext

SimpleFT8 — Hobby-Funker-Tool, FT8 mit FlexRadio 8400M. Mike-Field-Test
18.05.2026: Bei Bandwechsel (30m) mit fehlendem Gain-Preset poppen
**3 Fenster** nacheinander:

1. AutoTuneDialog (modal, 15s) — `_start_auto_tune_for_band_change`
2. DXTuneDialog (non-modal, 2 Min) — `_start_dx_tuning`
3. Bei SWR-bad: QMessageBox.warning „SWR zu hoch"

Mike-Spec: „viele Fenster die aufploppen verwirren. Ein Fenster was erst
die Aktion und das Beenden anzeigt ist übersichtlicher."

**Aktueller Stand:** v0.97.93. Tests: 1744. Voller Workflow läuft
(V1 → V2 → **R1 hier** → V3 → Code).

## Bisherige Workflow-Phasen

- **V1 (Erstentwurf)**: AutoTuneDialog KOMPLETT löschen, DXTuneDialog
  mit State-Machine TUNE→GAIN_CYCLES→FINISHED erweitern.
- **V2 (Self-Review)**: 5 Findings gefunden (2🔴 3🟡). Wichtigster:
  TUNE und Gain-Mess in `_on_band_changed` sind **entkoppelt** — es
  gibt 4 Fälle (A/B/C/D), nicht nur „2-Fenster-Pipeline":

  | Fall | TUNE? | Gain-Mess? | Heutiges Verhalten |
  |---|---|---|---|
  | A | ✓ | ✗ | AutoTuneDialog (kein Problem) |
  | **B** | ✓ | ✓ + missing Preset | **AutoTuneDialog → DXTuneDialog (der Bug)** |
  | C | ✗ | ✓ + missing Preset | DXTuneDialog (evtl. SWR-bad-Modal) |
  | D | ✗ | ✗ | kein Dialog |

  → Korrektur: AutoTuneDialog **bleibt** für Fall A. Nur Fall B
  konsolidieren via DXTuneDialog-mit-TUNE-Phase. = **Variante D-X**.

## Variante D-X (Hybrid) — was ich bauen will

### Code-Änderungen

**`ui/dx_tune_dialog.py` (DXTuneDialog):**
- Neuer Constructor-Parameter: `with_tune_phase: bool = False`,
  `tune_duration_s: int = 15`, `mode: str = "FT8"`
- Neuer State `_state ∈ {'TUNE', 'GAIN_CYCLES', 'FINISHED'}`,
  initial 'TUNE' wenn `with_tune_phase=True`, sonst 'GAIN_CYCLES'
- Neues Klassen-Signal `auto_tune_done = Signal(bool, float, float)`
  (identische API wie AutoTuneDialog — Duck-typing-kompatibel mit
  bestehendem `_tune_post_swr_check`-Pfad in mw_tx.py:343/438/454)
- Neue Methoden:
  - `_start_tune_phase()`: ruft `parent._start_dialog_tune_sequence(self, band, mode, tune_duration_s)`, startet Tick-Timer + Backup-Timer
  - `_on_auto_tune_done(success, swr, avg_fwdpwr)` Slot:
    - Success → State='GAIN_CYCLES', UI-Wechsel, `_start_step()`
    - Fail → roter Banner „⚠ SWR x.x > Limit y", nach 1.5s `reject()`
  - `_on_tune_tick()`: 1s-Updates für TUNE-Phase (P76-B 2-Phasen-Label)
  - `_on_tune_backup_timeout()`: triggert `_on_auto_tune_done(False, 0.0, 0.0)`
- `feed_cycle()` State-Guard: `if self._state != 'GAIN_CYCLES': return`
- `_on_cancel()` State-aware:
  - TUNE → `parent._tune_convergence_cancelled=True`, `parent._tune_stop(None)`, `reject()`
  - GAIN_CYCLES → bestehender Pfad (Antenne ANT1, Gain 10)
- `_setup_ui()` zeigt State-spezifische Sub-UI (Spinner für TUNE, Progress für GAIN)
- Konstante `_TUNE_BACKUP_GRACE_S = 12` (analog AutoTuneDialog P71)

**`ui/mw_radio.py`:**
- Neuer Helper `_start_pipeline_for_band_change(band, scoring) -> bool`:
  - Setzt `_pending_dx_diversity=True`, `_pending_diversity_scoring=scoring`
  - Setzt `_set_gain_measure_lock(True)`
  - Öffnet DXTuneDialog mit `with_tune_phase=True`, `tune_duration_s=settings.get('tune_duration_s', 15)`, `mode=settings.mode`
  - `dialog.exec()` → modal blockt (analog `_start_auto_tune_for_band_change`)
  - Returnt True bei Accept, False bei Reject

- Neue Methode `_start_dialog_tune_sequence(dialog, band, mode, duration_s)`:
  - Setzt `_auto_tune_dialog=dialog`, `_auto_tune_running=True`
  - `_fwdpwr_samples.clear()`, `_tune_convergence_cancelled=False`
  - `_tune_in_progress=True`, `_tune_active=True`
  - `set_tx_antenna('ANT1')`, `set_rfpower_direct(10)`, `tune_on()`
  - `QTimer.singleShot(duration_s*1000, lambda: _tune_stop(token))`
  - (Analog `_start_auto_tune_for_band_change` Z.629-649, aber OHNE Dialog-Erstellung)

- `_on_band_changed` (Z.612-680): vor bestehender TUNE-Branch (Z.612) neuer Check für **Fall B**:
  ```python
  is_case_b = (
      self._rx_mode == "diversity"
      and self.settings.get("auto_tune_on_band_change", True)
      and self.settings.get("auto_gain_on_band_change", False)
      and self.radio.ip
      and band.upper() not in self._swr_blocked_bands
      and self.settings.get("tuner_present", True)
      and not getattr(self, "_initial_band_set", False)
      and self._assess_gain(band) != "fresh"  # missing/stale
  )
  if is_case_b:
      scoring = getattr(self._diversity_ctrl, 'scoring_mode', 'normal')
      success = self._start_pipeline_for_band_change(band, scoring)
      # SKIP _check_diversity_preset — Dialog hat alles erledigt
      if not success:
          self.qso_panel.add_info(f"⚠ Pipeline {band.upper()} abgebrochen")
          # Diversity-Modus auf Normal zurück
          self._on_rx_mode_changed("normal")
      return  # alle anderen Pfade unten skippen
  ```

- `_start_dx_tuning(scoring_mode, with_tune_phase=False)`:
  - Bei `with_tune_phase=True`: skippt Hardware-TUNE (Z.1690-1691, 1694) UND `QTimer.singleShot(3000, _after_tune)` (Z.1716). Behält RX-Cleanup (Z.1696-1698) — diese vor `_open_dx_tune_dialog` ziehen.
  - Direkt `_open_dx_tune_dialog(with_tune_phase=True)`
  - Bei `with_tune_phase=False`: bestehender Pfad (kein Change)

- `_open_dx_tune_dialog(with_tune_phase: bool = False)`:
  - Propagiert Parameter an DXTuneDialog
  - `prev_tune_swr=None` wenn `with_tune_phase=True` (P75-Banner überflüssig)

- `_handle_dx_tuning` (Z.1569 KALIBRIEREN-Button):
  - Ruft `_start_dx_tuning(scoring_mode=gain_scoring, with_tune_phase=self.settings.get('tuner_present', True))`

- `_check_diversity_preset` `auto_remess=True`-Branch (Z.1542-1567):
  - Ruft `_start_dx_tuning(scoring_mode=gain_scoring, with_tune_phase=self.settings.get('tuner_present', True))`
  - (Pfad wird nur noch von Fall C getriggert — Fall B umgeht ihn jetzt)

**SWR-bad-Modal in `_start_dx_tuning._after_tune` (mw_radio.py:1706-1711):**
- Bei `with_tune_phase=False` mit `tuner_present=True`: Modal läuft noch (Fall C-Pfad). Hier KANN bleiben oder weg — Mike-Spec sagt „bei SWR-bad: Modal wegfallen lassen, Info-Banner". Vorschlag: durch `qso_panel.add_info` ersetzen analog P79.

### Was unverändert bleibt

- `ui/auto_tune_dialog.py`: 0 Changes (AutoTuneDialog bleibt für Fall A)
- `_start_auto_tune_for_band_change`: 0 Changes (bleibt für Fall A)
- `_tune_post_swr_check` (mw_tx.py:308): 0 Changes (Duck-typing reicht)
- `_tune_converge_to_target`, `_tune_stop`, RFPreset-Save-Logik: 0 Changes
- Manueller TUNE-Button (Tuner-Test): 0 Changes
- Phase 3 (Ratio-Messung in `_on_dx_tune_accepted`): 0 Changes

## Bekannte Risiken/Fragen für R1

**R-RACE-1 — Bandwechsel während Dialog-State TUNE:**
Bestehender `_tune_token`-Schutz in mw_tx.py greift. Dialog muss
ggf. `reject()` machen. Reicht das oder brauchen wir aktive
Token-Invalidierung im Dialog?

**R-RACE-2 — User klickt Cancel während `_tune_converge_to_target` läuft:**
Sub-Event-Loop läuft im Hintergrund. `_tune_convergence_cancelled`-Flag
greift, aber muss vom Dialog-Cancel gesetzt werden BEVOR `_tune_stop`.
Reihenfolge: cancel-Flag SETZEN → tune_stop. Korrekt?

**R-RACE-3 — `_on_auto_tune_done(True)` → State 'GAIN_CYCLES' → erster
Decoder-Cycle während UI-Update:**
Reihenfolge: `_start_step()` vor UI-Wechsel. Race möglich oder
synchron im selben Qt-Slot sicher?

**R-DISCONNECT — Radio disconnect während State TUNE:**
`_tune_post_swr_check` macht Fail-Pfad bei `radio.ip=False` (mw_tx.py:
338-348). Dialog kriegt `auto_tune_done.emit(False, 0.0, 0.0)`. AC4
greift → Banner. Reicht das?

**R-DUCK-TYPING — `_auto_tune_dialog` kann DXTuneDialog ODER AutoTuneDialog
sein:**
mw_tx.py:343/438/454 emittiert `dlg.auto_tune_done.emit(...)`. Beide
Dialogs haben dasselbe Signal-Klassenattribut → kompatibel. Saubere
Lösung oder besser explizite Protocol-Klasse?

**R-PIPELINE-FAIL-PFAD — wenn Pipeline fail (Cancel oder SWR-bad):**
Heute: `_on_band_changed` würde nach AutoTuneDialog-Fail trotzdem in
`_check_diversity_preset` weitergehen. Neu im Fall B: bei Fail
`_on_rx_mode_changed("normal")`. Reicht das oder gibt's Edge-Cases
(z.B. wenn `_rx_mode` schon „normal" war)?

**R-LOCK-RELEASE — `_set_gain_measure_lock(True)` im Helper:**
Wer setzt es wieder auf False bei Fail? Bei Success läuft
`_on_dx_tune_accepted` → `_set_gain_measure_lock(False)` (Z.1861).
Bei Reject läuft `_on_dx_tune_rejected` — checkt Code ob Lock dort
released wird?

**R-BACKUP-TIMER — DXTuneDialog hat KEINEN Backup-Timer heute:**
Phase 2 läuft 8 Cycles × 15s = 2 Min ohne Watchdog. Wenn Decoder
hängt, hängt Dialog. Beim TUNE-Phase-Backup-Timer: `tune_duration_s
+ 12s` Grace (analog AutoTuneDialog). Sollten wir Phase 2 auch
einen Backup-Timer geben? Out-of-Scope für P74-A?

## Code-Files anbei

- `ui/dx_tune_dialog.py` (549 LOC)
- `ui/auto_tune_dialog.py` (244 LOC — Referenz für State TUNE)
- `ui/mw_radio.py` (relevante Abschnitte: _on_band_changed,
  _check_diversity_preset, _start_dx_tuning, _open_dx_tune_dialog,
  _handle_dx_tuning, _set_gain_measure_lock, _on_dx_tune_accepted,
  _on_dx_tune_rejected)
- `ui/mw_tx.py` (relevante Abschnitte: _tune_post_swr_check,
  _start_auto_tune_for_band_change, _tune_converge_to_target)

## Was du prüfen sollst

1. **Architektur**: Variante D-X (Hybrid) vs reines D (alles in
   DXTuneDialog, AutoTuneDialog weg). Mike-Spec konform? Bessere
   Alternative?
2. **Race-Conditions**: R-RACE-1, R-RACE-2, R-RACE-3 — übersehe ich
   Edge-Cases?
3. **State-Machine im Dialog**: TUNE→GAIN_CYCLES→FINISHED sauber? Gibt
   es weitere States die wir brauchen (z.B. TUNE_FAIL, CANCELLED)?
4. **Duck-Typing für `_auto_tune_dialog`**: ok für Hobby-Projekt oder
   Protocol-Klasse Pflicht?
5. **Lock-Release-Pfade**: Hänger möglich wenn Reject ohne Release?
6. **Backup-Timer Phase 2**: P74-A oder separate Aufgabe?
7. **Versteckte Annahmen**: Was übersehe ich? Welche Settings/Flags/
   Pfade fehlen?

Kritisch sein. KISS bewerten. Mike ist Hobby-Funker, kein Software-
Architekt — Code soll wartbar bleiben.
