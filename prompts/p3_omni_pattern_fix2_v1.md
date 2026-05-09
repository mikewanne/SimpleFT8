# P3.OMNI-PATTERN-FIX-2 — V1 Diagnose-Plan

**Datum:** 2026-05-09 (Mike-Auftrag post v0.95.24 Field-Test)
**Vorgaenger:** P2.OMNI-PATTERN-FIX (v0.95.24, 4 Commits)
**Stand:** V1 — Diagnose + Loesungs-Skizze

---

## 0. Kontext (Mike-Field-Test 09.05. 11:55-12:00 UTC)

App v0.95.24 lief. Mike toggelte OMNI mehrfach weil Button-Label
keinen Aktiv-Status zeigt. Live-Logs (`~/.simpleft8/log_v0.95.24.log`)
zeigen 4 Probleme:

### Problem 1: GUI-Tick-Latency → Pretrigger zu spaet → Drift

```
[OMNI-Pretrigger] Pos 1 Block 1 target_even=False cycle_pos=14.89s
[TX] 09:54:13 Slot=EVEN Freq=1000Hz   ← Drift! Erwartet ODD
```

Mein Pretrigger-Check `if sic >= dur - 1.3` erwartet Tick zwischen
13.7s und ~14.2s. Aber Decoder am Slot-Ende blockiert GUI-Thread,
Tick kommt erst bei 14.89s rein. Encoder bekommt `_send_cq` → Sleep =
`(15.0 - 0.8) - 14.89 = -0.69s` → overshoot 0.69s > 0.3s → v0.80 Fix B
schiebt 2 Slots weiter → falsche Paritaet.

### Problem 2: Button-Label keinen Aktiv-Status

`btn_omni_cq` heisst statisch „OMNI CQ" — Mike kann nicht sehen ob
aktiv. Drueckt mehrfach aus Unsicherheit, was OMNI staendig stoppt
(`manual_halt`).

### Problem 3: User-Start-Toggle hat kein Drift-Schutz

`_on_btn_omni_cq_toggled(checked=True)` ruft synchron:
- `omni_tx.start_with_parity_for_next_slot(next_is_even)`
- `qso_sm.start_cq()` → `_send_cq()` → `send_message.emit(...)` →
  `mw_qso._on_send_message` → `encoder.transmit(...)`

Encoder berechnet `_next_slot_boundary()` JETZT. Wenn Mike mid-cycle
(cycle_pos=14.x s) toggelt → Encoder rechnet wie Pretrigger-Pfad → Drift.

### Problem 4: Keine Feedback-Zeile in RX-Slots

Mike sieht im QSO-Panel nur Sende-Zeilen. Bei stillen RX-Slots
(3 von 5 in OMNI-Pattern) keine Bestaetigung dass App lauft.
Mike-Wunsch: pro RX-Slot eine Zeile `09:48:45 [O] → Horche...`.

---

## 1. Wurzel-Analyse

### 1.1 Tick-Latency (Problem 1, KRITISCH)

`core/timing.py:_tick_loop`:
```python
while self._running:
    now = self.utc_now()
    sic = now % self.cycle_duration
    cycle_num = int(now / self.cycle_duration)
    if cycle_num != last_cycle:
        ...
        self.cycle_start.emit(self._cycle_count, is_even)
    self.cycle_tick.emit(sic, self.cycle_duration)
    time.sleep(0.1)
```

`cycle_tick` wird alle ~100ms emittet aus Worker-Thread. Slot via
Qt-AutoConnection → QueuedConnection (cross-thread) → Event-Queue im
GUI-Thread. Wenn GUI-Thread durch Decoder/UI-Update blockiert ist
(speziell am Slot-Ende = decode_complete + paint), staut sich die
Queue → 1.0s+ Latency moeglich.

**Konsequenz:** mein Pretrigger-Check trifft das schmale Fenster
[13.7, 14.2] s nicht zuverlaessig.

### 1.2 Button-Statik (Problem 2)

`ui/control_panel.py:965`:
```python
self.btn_omni_cq = QPushButton("OMNI CQ")
```

`update_omni_tx(active)` (Z.1627) aendert nur Ω-Symbol + Versions-
Label-Farbe — KEIN Button-Text-Update.

### 1.3 User-Start-Pfad (Problem 3)

`ui/main_window.py:_on_btn_omni_cq_toggled`:
```python
self._omni_tx.start_with_parity_for_next_slot(next_is_even)
self.qso_sm.start_cq()
```

`start_cq` ruft synchron `_send_cq`. Cycle-Position wird nicht geprueft.

### 1.4 RX-Slot-Stille (Problem 4)

`ui/mw_qso.py:_on_send_message` bei OMNI-RX-Slot:
```python
if not send_ok:
    self.qso_sm._omni_skip_state_change = True
    print(f"[OMNI-TX] RX-Slot → skip CQ ({self._omni_tx.slot_label})")
    return
```

`print` geht nur in stdout (terminal/log). QSO-Panel bekommt keine
Info. `qso_panel.add_info(...)` existiert (mw_qso nutzt es bei
QSO-Events), wird aber nicht im RX-Skip-Pfad gerufen.

---

## 2. Loesungs-Skizze (V1)

### 2.1 Pretrigger via QTimer.singleShot (Problem 1)

Statt `cycle_tick`-Schwellen-Check: in `_on_cycle_start` einen
QTimer.singleShot mit exact-delay einplanen.

```python
# ui/mw_cycle.py
@Slot(int, bool)
def _on_cycle_start(self, cycle_num, is_even):
    self._omni_pretriggered = False
    # ... bestehender Code
    # P3 NEU: Pretrigger zeitlich exakt planen
    if self._omni_tx.active and not self._omni_tx.is_paused():
        delay_ms = int((self.timer.cycle_duration -
                        _OMNI_PRETRIGGER_OFFSET_S) * 1000)
        # FT8: 15.0 - 1.3 = 13.7s = 13700ms
        # FT4: 7.5 - 1.3 = 6.2s
        # FT2: 3.8 - 1.3 = 2.5s
        QTimer.singleShot(delay_ms, self._omni_pretrigger_fire)

def _omni_pretrigger_fire(self):
    """QTimer-getriggerter Pretrigger — exact zur Schwelle."""
    if self._omni_pretriggered:
        return
    if not self._omni_tx.active or self._omni_tx.is_paused():
        return
    if not self.qso_sm.cq_mode:
        return
    if self.qso_sm.state not in (QSOState.IDLE, QSOState.CQ_WAIT,
                                  QSOState.CQ_CALLING):
        return
    # ... peek_next + tx_even setzen + _send_cq (wie bisher)
```

`_on_cycle_tick`-basierter Pretrigger entfaellt komplett.

**Vorteil:** QTimer in GUI-Thread garantiert exact-delay (max ~10ms
Drift bei Qt-Eventloop). Decoder-Blocking im selben Thread
verzoegert auch QTimer, aber dann sind WIR sicher dass nicht 1s
spaeter ist (QTimer hat hoehere Prio als emitted Signals).

**Detail:** falls Mode-Wechsel mid-cycle: alter QTimer feuert noch
einmal mit alter delay_ms, ist aber via Pre-Cond-Check (state,
active) trotzdem safe — feuert ins Leere.

### 2.2 Button-Label dynamisch (Problem 2)

`ui/control_panel.py:update_omni_tx(active)` ergaenzen:

```python
def update_omni_tx(self, active: bool) -> None:
    self._omni_active = active
    self._omni_symbol.setVisible(active)
    color = "#222" if active else "#333"
    self._version_label.setStyleSheet(...)
    # P3 NEU: Button-Label-Update
    text = "OMNI CQ (aktiv)" if active else "OMNI CQ"
    if hasattr(self, 'btn_omni_cq'):
        self.btn_omni_cq.setText(text)
```

Single-source-of-truth: Button-Label nur via update_omni_tx —
NICHT direkt im Toggle-Handler ueberschreiben.

### 2.3 User-Start mit Drift-Schutz (Problem 3)

Im `_on_btn_omni_cq_toggled` Pre-Check:

```python
if checked and not self._omni_tx.active:
    # ... bestehender Pre-Block-Check (state)
    cycle_pos = self.timer.seconds_in_cycle()
    cycle_dur = self.timer.cycle_duration
    if cycle_pos > cycle_dur - _OMNI_USER_START_GUARD_S:
        # zu nah am Slot-Ende → delayen bis naechster Slot
        delay_ms = int((cycle_dur - cycle_pos + 0.1) * 1000)
        # +0.1s als Sicherheit dass wir wirklich im naechsten Slot sind
        QTimer.singleShot(delay_ms, lambda: self._on_btn_omni_cq_toggled(True))
        # Re-Aufruf hat dann cycle_pos < Schwelle → echter Start
        return
    # ... echter Start
```

`_OMNI_USER_START_GUARD_S = 1.5` (etwas mehr als TX-Buffer 1.3, damit
Encoder garantiert sleep_dur > 0 hat).

### 2.4 RX-Slot „Horche..."-Anzeige (Problem 4)

Neue Methode in `ui/qso_panel.py`:

```python
def add_listening(self, slot_start_ts: float, tx_even: bool):
    """OMNI RX-Slot-Anzeige (Mike-Wunsch v0.95.25)."""
    utc = time.strftime("%H:%M:%S", time.gmtime(slot_start_ts))
    tag = "[E]" if tx_even else "[O]"
    self._append_colored(f"{utc} {tag} ←  Horche  …", "#666666")
```

Aufruf in `mw_qso._on_send_message` RX-Slot-Pfad:

```python
if not send_ok:
    self.qso_sm._omni_skip_state_change = True
    print(f"[OMNI-TX] RX-Slot → skip CQ ({self._omni_tx.slot_label})")
    # P3 NEU: QSO-Panel-Anzeige
    now = time.time()
    slot_dur = self.timer.cycle_duration
    slot_start = now - (now % slot_dur)
    is_even = int(slot_start / slot_dur) % 2 == 0
    self.qso_panel.add_listening(slot_start, is_even)
    return
```

---

## 3. Akzeptanzkriterien (V1, 12 ACs)

| AC | Beschreibung | Verifikation |
|---|---|---|
| AC1 | Pretrigger feuert genau bei `dur - 1.3 ± 50ms` | T1 mit QTimer-Mock |
| AC2 | Pretrigger funktioniert bei Decoder-Blocking (simuliertem GUI-Thread-Block) | T2 mit Sleep-Mock |
| AC3 | Button-Text aktiv: „OMNI CQ (aktiv)" | T3 + Field-Test |
| AC4 | Button-Text inaktiv: „OMNI CQ" | T3 + Field-Test |
| AC5 | Button-Text wird via `update_omni_tx` synchron mit Ω-Symbol gesetzt | T3 |
| AC6 | User-Toggle bei `cycle_pos > dur - 1.5s` delayed bis naechster Slot | T4 mit timer-Mock |
| AC7 | User-Toggle bei `cycle_pos < dur - 1.5s` startet sofort | T5 |
| AC8 | RX-Slot-Skip ruft `qso_panel.add_listening(slot_start, tx_even)` | T6 |
| AC9 | `add_listening` schreibt Zeile mit Format `HH:MM:SS [E/O] ← Horche …` | T7 |
| AC10 | Pretrigger entfernt aus `_on_cycle_tick` (kein Doppel-Trigger) | Code-Inspection + T8 |
| AC11 | OMNI-Stop reset `_omni_pretriggered` UND killt pending QTimer (kein Late-Fire) | T9 |
| AC12 | Field-Test: 10-Slot-Loop zeigt EXAKT erwartetes Pattern (Block 1 + Block 2) | Mike-Field-Test |

---

## 4. Test-Strategie (V1, ~10 neue Tests in `test_p3_omni_pattern_fix2.py`)

| # | Test | AC |
|---|---|---|
| T1 | `test_pretrigger_qtimer_singleshot_scheduled_in_cycle_start` | AC1 |
| T2 | `test_pretrigger_qtimer_fires_independent_of_cycle_tick` | AC2 |
| T3 | `test_update_omni_tx_sets_button_text` | AC3-AC5 |
| T4 | `test_user_toggle_late_in_cycle_delays_start` | AC6 |
| T5 | `test_user_toggle_early_in_cycle_starts_immediately` | AC7 |
| T6 | `test_rx_slot_skip_calls_add_listening` | AC8 |
| T7 | `test_add_listening_format` | AC9 |
| T8 | `test_pretrigger_only_via_qtimer_not_cycle_tick` | AC10 |
| T9 | `test_omni_stop_clears_pending_qtimer` | AC11 |
| T10 | `test_qtimer_singleshot_deactivates_on_omni_stop` | AC11 |

**Erwartet:** 1048 → 1058 (+10).

---

## 5. Risiken (V1)

| # | Risiko | Mitigation |
|---|---|---|
| R1 | QTimer.singleShot kann von Late-Decoder ebenfalls verzoegert werden | Ist deutlich praeziser als Signal-Queue, max ~10-50ms statt 1000ms+ |
| R2 | Mode-Wechsel mid-cycle laesst alten QTimer feuern | Pre-Cond-Check (active+state) faengt das ab — feuert ins Leere |
| R3 | OMNI-Stop laesst pending QTimer weiter laufen | Stop-Reason-Slot setzt Flag das pending-Fire blockiert |
| R4 | User-Start-Delay-QTimer + manueller Stop = inkonsistenter State | QTimer-Lambda prueft `omni.active` vor Re-Trigger |
| R5 | `add_listening`-Spam bei langem OMNI-Run (3 von 5 Slots ueber 1h = 1080 Zeilen) | `_auto_trim_by_age` greift bereits (5-Min-Window in P1.16) |
| R6 | Field-Test deckt Race auf der unter Test nicht reproduzierbar ist | Field-Test ist Pflicht — 10+ Slots OMNI-Loop |

---

## 6. Atomare Commits (Plan)

| # | Commit | Files |
|---|---|---|
| 1 | Pretrigger via QTimer + Cycle-Tick-Pretrigger entfernt | `ui/mw_cycle.py`, `tests/test_p3_omni_pattern_fix2.py` (NEU, T1-T2, T8) |
| 2 | Button-Label dynamisch | `ui/control_panel.py`, Tests T3 |
| 3 | User-Start Drift-Schutz + RX-Slot Horche-Anzeige + APP_VERSION + Doku | `ui/main_window.py`, `ui/mw_qso.py`, `ui/qso_panel.py`, `main.py`, HISTORY/HANDOFF/CLAUDE/Memory |

---

## 7. Offene Fragen fuer V2

1. **QTimer-Lifecycle:** persistent als Instanz-Variable
   (`self._omni_pretrigger_timer`) oder pro `_on_cycle_start` neu? V2
   muss klaeren — persistenz waere sauberer fuer Stop-Cancel.
2. **`_OMNI_USER_START_GUARD_S = 1.5`** vs `_OMNI_PRETRIGGER_OFFSET_S = 1.3`:
   warum unterschiedlich? V2 Mathematik mit Encoder-Sleep verifizieren.
3. **`add_listening`-Spam:** Mike will alle RX-Slots sehen, oder nur
   wenn keine Stationen decodiert? Default: alle (sonst inkonsistent).
4. **Cycle-Tick-Pretrigger entfernen ODER als Fallback lassen?** V1
   Plan: entfernen. V2 pruefen ob Defense-in-Depth besser.
5. **User-Start-Delay-Replay:** Lambda re-triggert via
   `_on_btn_omni_cq_toggled(True)` rekursiv. Race wenn User mehrfach
   klickt waehrend QTimer pending? V2 klaeren.
6. **Mode-Wechsel + active QTimer:** wer cancelt? V2 klaeren.
7. **Test-Mock-Strategie:** QTimer in Tests zuverlaessig mockbar?
   Qt-`pytest-qt` oder direkter Aufruf von `_omni_pretrigger_fire`
   ohne QTimer? V2.
8. **`add_listening` waehrend QSO?** OMNI ist dann pausiert →
   `should_tx` returnt (True, None) → kein RX-Slot-Skip → kein
   `add_listening`. Korrekt? V2 verifizieren.
