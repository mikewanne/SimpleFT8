# P2.OMNI-PATTERN-FIX — V3 Compact-fest

**Datum:** 2026-05-09
**Vorgaenger:** V1 → V2 (16 Lessons + L17-Race) → R1-Review („Variante 2 Encoder-Queue empfohlen")
**Stand:** Mike-Freigabe ausstehend, dann Compact #4 → Code

---

## 0. Compact-Brief

OMNI-CQ-Pattern in v0.95.23 verschoben um +30s wegen Encoder-Drift-Schutz.
Mike's Field-Test 09.05. 08:34-08:37 UTC zeigt: TX nur in Pos 0 jedes
Blocks, Pos 1 / RX-Slots sind kollabiert.

**Wurzel:** `_send_cq` aus `on_cycle_end` am Slot-START → Encoder
`overshoot=0.8s > 0.3s` Drift → schiebt TX um 2 Slots.

**Loesung (R1-bestaetigt):**
1. **Encoder-Queue (Variante 2):** `transmit()` queut zweite Message
   statt SKIP — Worker sendet beide nacheinander.
2. **Mid-Cycle-Pretrigger (Option E):** OMNI plant TX fuer naechsten
   Slot mid-cycle (cycle_pos > dur-1.3s) → Encoder hat Sleep-Vorlauf,
   kein Drift.

**Atomare Commits:** 2 (Encoder-Queue + Pretrigger).

**Mike's Spec „kompletter Block-Start":** Bereits via `start_with_parity_
for_next_slot` (`_slot_index=0`) erfuellt. Keine zusaetzlichen Aenderungen
fuer diese Anforderung.

---

## 1. R1-V2-Findings — Bewertung

| R1-Finding | Status | V3-Aktion |
|---|---|---|
| L1-L16 alle korrekt | ✅ | unveraendert uebernehmen |
| L17 Race (Pretrigger vs aktuelle TX) | KRITISCH | Variante 2 Encoder-Queue |
| Variante 2 sauberste Loesung | ✅ ACK | implementieren |
| Variante 1 (enges Fenster) zu fragil | ✅ ACK | verworfen |
| Variante 3 (tx_finished-Trigger) zu komplex | ✅ ACK | verworfen |
| L6 Schutz via Flag | ✅ ACK | `_was_pretriggered` Flag in qso_sm |
| Encoder-Refactor: 2-Commit-Trennung | ✅ ACK | Commit 1=Queue, Commit 2=Pretrigger |
| Tests T1-T7 fuer Queue + Pretrigger | ✅ ACK | uebernehmen |
| Replace verdraengt Queue | ✅ ACK | abort + replace leeren `_pending_tx_message` |
| tx_finished nach JEDEM TX | ✅ ACK | bestehende Invariante (qso_state braucht es) |

---

## 2. Code-Aenderungen (Final)

### 2.1 `core/encoder.py` — Queue-Mechanismus (Commit 1)

**`__init__` ergaenzen:**
```python
self._pending_tx_message: str | None = None
# _queue_lock unnoetig wenn nur GUI-Thread in transmit() schreibt;
# Worker liest mit _replace_lock geschuetzt.
```

**`transmit()` erweitern:**
```python
def transmit(self, message: str):
    if (self._tx_thread is not None
            and self._tx_thread.is_alive()
            and threading.current_thread() is not self._tx_thread):
        self._tx_thread.join(timeout=0.5)
    if self._is_transmitting:
        # P2.OMNI-PATTERN-FIX (v0.95.24): Queue zweite Message statt SKIP.
        # Worker sendet sie nach aktuellem TX. Replace + abort verdraengen
        # die Queue (siehe abort() / Replace-Pfad).
        with self._replace_lock:
            self._pending_tx_message = message
        print(f"[TX] Queued (TX aktiv): '{message}'")
        return
    self._tx_thread = threading.Thread(
        target=self._tx_worker, args=(message,), daemon=True
    )
    self._tx_thread.start()
```

**`_tx_worker` erweitern (rekursiver TX-Loop fuer Queue):**
```python
def _tx_worker(self, message: str):
    self._is_transmitting = True
    self._abort_event.clear()
    self._audio_started = False
    with self._replace_lock:
        self._replace_message = None
        # Queue NICHT hier loeschen — kann sich ueberlappen mit aktuellem TX
    try:
        # Outer-Loop: nach erstem TX pruefe pending
        while True:
            self._tx_worker_inner(message)
            # tx_worker_inner setzt tx_finished.emit am Ende.
            # Pruefe pending fuer naechsten TX (Queue).
            with self._replace_lock:
                next_msg = self._pending_tx_message
                self._pending_tx_message = None
                # Reset fuer naechsten Inner-Run
                self._audio_started = False
                self._abort_event.clear()
            if next_msg is None:
                break
            message = next_msg
            print(f"[TX] Queued-TX naechster Slot: '{message}'")
    finally:
        self._is_transmitting = False
        self._audio_started = False
```

**`abort()` erweitern (Queue leeren):**
```python
def abort(self):
    self._is_transmitting = False
    self._abort_event.set()
    with self._replace_lock:
        self._pending_tx_message = None  # Queue verwerfen
    print("[Encoder] TX abgebrochen")
```

**Replace-Pfad in `_tx_worker_inner` (Sleep-Phase) Queue leeren:**
```python
if aborted:
    with self._replace_lock:
        if self._replace_message is not None:
            message = self._replace_message
            self._replace_message = None
            self._pending_tx_message = None  # NEU: Replace verdraengt Queue
            self._abort_event.clear()
            print(f"[Encoder] TX-Replace → '{message}'")
            continue
```

**Wichtig:** `tx_finished.emit()` bleibt in `_tx_worker_inner` am Ende
(qso_state.on_message_sent braucht das nach jedem TX). Outer-Loop in
`_tx_worker` wartet zwischen Inner-Runs nicht — der naechste
`_tx_worker_inner` ruft selbst Sleep auf (in Encoder _next_slot_boundary).

### 2.2 `core/omni_tx.py` — `peek_next` Methode (Commit 2)

```python
def peek_next(self) -> tuple:
    """Returnt (next_slot_index, next_block, target_even, is_tx)
    OHNE State-Mutation. Fuer Pretrigger-Logik.
    """
    next_slot_index = (self._slot_index + 1) % 5
    next_block = self.block
    if next_slot_index == 0:
        next_block = 2 if self.block == 1 else 1
    is_tx = _TX_PATTERN[next_slot_index]
    if not is_tx:
        return next_slot_index, next_block, None, False
    if next_block == 1:
        target_even = (next_slot_index == 0)
    else:
        target_even = (next_slot_index == 1)
    return next_slot_index, next_block, target_even, True
```

### 2.3 `ui/main_window.py` — `_omni_pretriggered` Flag-Init (Commit 2)

```python
# in _init_diversity_state ergaenzen:
self._omni_pretriggered: bool = False  # Mid-Cycle-Pretrigger Reentrancy-Schutz
```

### 2.4 `ui/mw_cycle.py` — Pretrigger in `_on_cycle_tick` (Commit 2)

**Modus-Konstanten:**
```python
# Modul-Top (mw_cycle.py)
# P2.OMNI-PATTERN-FIX: Pretrigger-Schwelle (sec) vor Slot-Ende.
# = slot_duration - PRETRIGGER_OFFSET. Encoder hat dann Sleep-Vorlauf
# > 0 → kein v0.80 Fix B Drift.
_OMNI_PRETRIGGER_OFFSET_S = 1.3  # FT8: 13.7s, FT4: 6.2s, FT2: 2.5s
```

**`_on_cycle_tick` erweitern:**
```python
@Slot(float, float)
def _on_cycle_tick(self, seconds_in_cycle: float, cycle_duration: float):
    if not self.rx_panel._rx_active:
        return
    self.control_panel.update_cycle_bar(seconds_in_cycle, cycle_duration)
    # P2.OMNI-PATTERN-FIX (v0.95.24): Mid-Cycle-Pretrigger fuer OMNI.
    self._omni_pretrigger_check(seconds_in_cycle, cycle_duration)

def _omni_pretrigger_check(self, sic: float, dur: float) -> None:
    """Mid-Cycle-Pretrigger: bei OMNI active + cq_mode + naechsten Slot
    TX-Pos plane TX vor Slot-Ende. Encoder hat dann Sleep-Vorlauf, kein
    v0.80 Drift-Schutz triggert. Pattern bleibt korrekt.
    """
    if self._omni_pretriggered:
        return
    if not self._omni_tx.active or self._omni_tx.is_paused():
        return
    if not self.qso_sm.cq_mode:
        return
    if self.qso_sm.state not in (QSOState.IDLE, QSOState.CQ_WAIT,
                                  QSOState.CQ_CALLING):
        return
    threshold = dur - _OMNI_PRETRIGGER_OFFSET_S
    if sic < threshold:
        return
    # Pretrigger ausfuehren — atomar via Flag
    self._omni_pretriggered = True
    next_idx, next_block, target_even, is_tx = self._omni_tx.peek_next()
    if not is_tx:
        # RX-Slot: nichts tun (kein _send_cq), Pattern-Slot wird durch
        # advance() im _on_cycle_start "gelaufen". Flag fuer Reentrancy-Schutz.
        return
    # TX-Slot: Encoder hat Vorlauf (sleep_dur > 0)
    self.encoder.tx_even = target_even
    # Pretrigger-Flag in qso_sm setzen damit on_cycle_end im naechsten
    # Slot KEIN doppeltes _send_cq triggert (R1 L6).
    self.qso_sm._was_pretriggered = True
    self.qso_sm._send_cq()
    print(f"[OMNI-Pretrigger] Pos {next_idx} Block {next_block} "
          f"target_even={target_even} cycle_pos={sic:.2f}s")
```

**`_on_cycle_start` Reset des Pretrigger-Flags:**
```python
@Slot(int, bool)
def _on_cycle_start(self, cycle_num: int, is_even: bool):
    # P2.OMNI-PATTERN-FIX: Pretrigger-Flag fuer naechsten Slot reset.
    self._omni_pretriggered = False
    # ... bestehender Code (TX-Peak, AutoLevel, on_cycle_end, advance, ...)
```

### 2.5 `core/qso_state.py` — `_was_pretriggered` Flag (Commit 2)

**`__init__` ergaenzen:**
```python
# P2.OMNI-PATTERN-FIX (v0.95.24): Pretrigger-Flag verhindert dass
# on_cycle_end ein zweites Mal _send_cq fuer denselben Slot triggert.
# Pretrigger setzt True, on_cycle_end checkt + reset.
self._was_pretriggered: bool = False
```

**`on_cycle_end` CQ_WAIT-Branch schuetzen:**
```python
if self.state == QSOState.CQ_WAIT:
    self.qso.timeout_cycles += 1
    if self.qso.timeout_cycles >= 1 and self.cq_mode:
        # P2.OMNI-PATTERN-FIX: Pretrigger laeuft mid-cycle, on_cycle_end
        # darf in OMNI-Pfad NICHT doppelt _send_cq triggern. Reset Flag
        # nach Check.
        if self._was_pretriggered:
            self._was_pretriggered = False
        else:
            self._send_cq()
    return
```

### 2.6 `ui/mw_qso.py` — `_on_send_message` Pretrigger-Bypass (Commit 2)

Aktuell setzt `_on_send_message` `encoder.tx_even` selbst via
`should_tx()`. Bei Pretrigger ist `tx_even` schon korrekt gesetzt.
Doppelte Logik vermeiden:

```python
@Slot(str)
def _on_send_message(self, message: str):
    if not self.presence_can_tx():
        print(f"[Presence] TX blockiert: '{message}'")
        return
    if message.startswith("CQ "):
        self._has_sent_cq = True
        if self._omni_tx.active:
            # P2.OMNI-PATTERN-FIX: Pretrigger-Pfad hat tx_even schon
            # gesetzt + naechsten-Slot-Pos validiert. Direkt transmit.
            # on_cycle_end-Pfad (kein Pretrigger) nutzt should_tx fuer
            # current-Slot-Filter (Initial-TX nach Toggle/Resume).
            if not getattr(self.qso_sm, '_was_pretriggered', False):
                send_ok, target_even = self._omni_tx.should_tx()
                if not send_ok:
                    self.qso_sm._omni_skip_state_change = True
                    print(f"[OMNI-TX] RX-Slot → skip CQ "
                          f"({self._omni_tx.slot_label})")
                    return
                if target_even is not None:
                    self.encoder.tx_even = target_even
                    parity_str = "Even" if target_even else "Odd"
                    print(f"[OMNI-TX] TX auf {parity_str} "
                          f"({self._omni_tx.slot_label})")
                    if target_even:
                        self._omni_tx.cq_even_count += 1
                    else:
                        self._omni_tx.cq_odd_count += 1
            else:
                # Pretrigger-Pfad: Counter trotzdem inkrementieren
                if self.encoder.tx_even is True:
                    self._omni_tx.cq_even_count += 1
                elif self.encoder.tx_even is False:
                    self._omni_tx.cq_odd_count += 1
    print(f"[TX] → '{message}' auf {self.encoder.audio_freq_hz} Hz")
    if self.encoder.is_transmitting:
        self.encoder.abort()
    self.encoder.transmit(message)
```

**Wichtig:** `_was_pretriggered` Flag wird in `qso_sm.on_cycle_end`
geresetet (siehe 2.5). NICHT hier in `_on_send_message`, sonst Race
mit on_cycle_end im NAECHSTEN Slot.

### 2.7 `ui/main_window.py` — `_on_cancel` HALT-Branch (Commit 2)

Pretrigger-Flag bei HALT zuruecksetzen damit naechste Aktivierung sauber
beginnt:
```python
@Slot()
def _on_cancel(self):
    # ... bestehende HALT-Logik
    # P2.OMNI-PATTERN-FIX: Pretrigger-Flag fuer sauberen Re-Start
    self._omni_pretriggered = False
```

---

## 3. Akzeptanzkriterien (V3 — 18 ACs, +3 zu V1)

| AC | Beschreibung | Verifikation |
|---|---|---|
| AC1 | Block 1: TX Even, TX Odd, RX, RX, RX in EXAKT diesen 5 Slots | Test T1 + Field-Test 5 Slots |
| AC2 | Block 2: TX Odd, TX Even, RX, RX, RX in EXAKT diesen 5 Slots | Test T2 + Field-Test 5 Slots |
| AC3 | Block-Rollover bei Pos 4→0: Block-Wechsel, neuer Block startet Pos 0 | Test T3 |
| AC4 | OMNI-Activate (Toggle): Pos 0 startet im naechsten verfuegbaren Slot | Test T4 + Field-Test |
| AC5 | OMNI-Resume nach QSO-Ende: Pos 0 startet im naechsten verfuegbaren Slot | Test T5 |
| AC6 | OMNI-Resume nach QSO-Timeout: Pos 0 startet im naechsten verfuegbaren Slot | Test T6 |
| AC7 | OMNI-HALT: KEIN Resume nach naechstem cycle | Test T7 (P1.OMNI-START Test bleibt) |
| AC8 | Encoder-Drift-Schutz (v0.80 Fix B) bleibt unveraendert | Code-Inspection — keine Aenderungen an Z.305-322 |
| AC9 | Field-Test: 10 Slots OMNI-Loop zeigt EXAKT erwartetes Pattern | Mike-Field-Test |
| AC10 | Stats: cq_even_count + cq_odd_count synchronisiert mit gesendeten TX | Test T8 |
| **AC11** | **Encoder-Queue: 2 transmit() hintereinander → beide TX gesendet** | **Test T9** |
| **AC12** | **Encoder-Queue + Replace: Replace verdraengt Queue** | **Test T10** |
| **AC13** | **Encoder-Queue + Abort: Queue wird geleert** | **Test T11** |
| **AC14** | **Pretrigger nur im Schwellen-Fenster (cycle_pos > dur-1.3)** | **Test T12** |
| **AC15** | **Pretrigger Reentrancy-Schutz: Flag verhindert Doppel-Trigger** | **Test T13** |
| AC16 | `_was_pretriggered` Flag verhindert on_cycle_end-Doppel-_send_cq | Test T14 |
| AC17 | RX-Slots im Pretrigger: kein _send_cq, kein TX | Test T15 |
| AC18 | Pretrigger respektiert paused/inactive OMNI | Test T16 |

---

## 4. Test-Strategie (V3 — 16 Tests in test_p2_omni_pattern_fix.py)

| # | Test | AC |
|---|---|---|
| T1 | `test_block_1_pattern_exact_slots` (E-TX, O-TX, E-RX, O-RX, E-RX) | AC1 |
| T2 | `test_block_2_pattern_exact_slots` (O-TX, E-TX, O-RX, E-RX, O-RX) | AC2 |
| T3 | `test_block_rollover_continues_pattern` | AC3 |
| T4 | `test_activate_starts_pos_0_next_slot` | AC4 |
| T5 | `test_resume_after_qso_starts_pos_0` | AC5 |
| T6 | `test_resume_after_timeout_starts_pos_0` | AC6 |
| T7 | (Bestehender P1.OMNI-START-Test bleibt) `test_halt_stops_omni_no_resume` | AC7 |
| T8 | `test_even_odd_counters_match_actual_tx` | AC10 |
| **T9** | `test_encoder_queue_second_transmit_during_active_tx` | AC11 |
| **T10** | `test_encoder_replace_clears_pending_queue` | AC12 |
| **T11** | `test_encoder_abort_clears_pending_queue` | AC13 |
| **T12** | `test_pretrigger_only_in_threshold_window` | AC14 |
| **T13** | `test_pretrigger_reentrancy_protection` | AC15 |
| T14 | `test_was_pretriggered_blocks_on_cycle_end_send_cq` | AC16 |
| T15 | `test_pretrigger_skips_rx_slots_no_send_cq` | AC17 |
| T16 | `test_pretrigger_skips_paused_omni` | AC18 |

**Erwartet Test-Count:** 1023 → 1039 (+16 NEU).

---

## 5. Risiken (V3)

| # | Risiko | Mitigation |
|---|---|---|
| R1 | Encoder-Queue + Replace + Abort 3-Wege-Race | Replace + Abort BEIDE leeren Queue (im _replace_lock geschuetzt) |
| R2 | tx_finished feuert nach jedem TX → qso_state Doppel-Triggers | Bestehende Invariante, keine Aenderung |
| R3 | Pretrigger-Schwelle dur-1.3s passt nicht fuer alle Modi | Konstante mode-aware berechnet, Test T12 deckt FT8/FT4/FT2 |
| R4 | cycle_tick Granularity 100ms missed Pretrigger-Fenster | 1.2s-Fenster bei FT8 = 12 Ticks → KISS-sicher |
| R5 | _was_pretriggered Flag-Lebenszeit (gesetzt von mw_cycle, reset von qso_state) | Klare Single-Set/Single-Reset-Konvention, Test T14 |
| R6 | Field-Test deckt Edge-Case auf den Tests nicht haben | Field-Test ist Pflicht — 10+ Slots OMNI-Loop |
| R7 | Encoder-Queue-Refactor bricht P1.9 Replace-Tests | Test T10 explizit fuer Koexistenz, vor Pretrigger-Commit |
| R8 | Stats-Counter cq_even/cq_odd inkonsistent zwischen Pretrigger und non-Pretrigger | Test T8, beide Pfade inkrementieren symmetrisch |

---

## 6. Atomare Commits (Plan)

| # | Commit | Files | Begruendung |
|---|---|---|---|
| 1 | `core/encoder.py` Queue-Mechanismus + Tests | core/encoder.py, tests/test_encoder_queue.py NEU | Foundation: Encoder unterstuetzt 2. TX (queued) |
| 2 | `core/omni_tx.py` peek_next + main_window/mw_cycle/mw_qso/qso_state Pretrigger | core/omni_tx.py, ui/main_window.py, ui/mw_cycle.py, ui/mw_qso.py, core/qso_state.py | Pretrigger-Logik nutzt Encoder-Queue |
| 3 | Tests + APP_VERSION + Doku | tests/test_p2_omni_pattern_fix.py NEU, main.py, HISTORY.md, HANDOFF.md, CLAUDE.md | 16 neue Tests + Version 0.95.24 + Doku-Update |

**Test-Count Erwartung:** 1023 → ~1039 (+16 NEU, abzueglich ggf. ~3
geloeschter alter Tests die durch Pretrigger obsolet werden).

---

## 7. Mike's Spec-Verifikation

**„kompletter Block bei jedem Start, nie mittendrin":**
- ✅ Toggle-Activate: `start_with_parity_for_next_slot` setzt
  `_slot_index=0` + Block je nach next-slot-Paritaet.
- ✅ QSO-End-Resume: `_maybe_resume_omni` ruft
  `start_with_parity_for_next_slot` mit aktueller next-slot-Paritaet.
- ✅ QSO-Timeout-Resume: gleicher Pfad ueber `_on_qso_timeout`.
- ✅ HALT: kein Resume (OMNI inaktiv, Pre-Flag invalidiert).
- ✅ Block-Rollover: bei `slot_index 4→0` automatisch (im `advance`),
  neuer Block startet sauber bei Pos 0.

**Pattern-Korrektheit (NEU in V3):**
- ✅ Pretrigger plant TX 1 Slot voraus → Encoder schlaeft regulaer →
  TARGET_TX_OFFSET respektiert → DT-Quality bleibt.
- ✅ RX-Slots werden NICHT mit TX gefuellt (Drift-Verschiebung weg).
- ✅ Block-Rhythmus 5-Slot-Pattern wird eingehalten.

---

## 8. Field-Test-Plan (V3)

Mike's Field-Test, bevor Push:

1. **Activate Test:** OMNI-Toggle aktivieren bei Slot N (Even/Odd egal).
   - Erste TX im naechsten verfuegbaren Slot.
   - Slot-Tag: korrekt (Even/Odd zur Slot-Paritaet).
2. **Pattern Block 1 / Block 2:**
   - Aktivieren so dass next_is_even=True → Block 1.
   - Erwartet: TX Even, TX Odd, RX, RX, RX in **5 aufeinanderfolgenden
     Slots**.
   - Aktivieren so dass next_is_even=False → Block 2.
   - Erwartet: TX Odd, TX Even, RX, RX, RX in **5 aufeinanderfolgenden
     Slots**.
3. **Block-Rollover:** Nach 5 Slots automatisch Block-Wechsel. Pattern
   des anderen Blocks startet ohne Luecke im naechsten Slot.
4. **10-Slot-Loop:** 2 volle Blocks (B1+B2 oder B2+B1). Pattern bleibt
   exakt — kein +30s Drift wie in v0.95.23.
5. **QSO-Reply mid-OMNI:** CQ-Reply einer Station → QSO normal →
   nach RR73 OMNI-Resume mit Pos 0 im naechsten verfuegbaren Slot.
   Block-Wahl per nachster-slot-Paritaet.
6. **Caller-Queue:** Mehrere Stationen rufen gleichzeitig → 1 QSO →
   nach QSO direkt naechstes QSO ohne OMNI-Resume.
7. **Toggle off:** Klick auf btn_omni_cq → OMNI stoppt, Pre-Flag reset.
8. **HALT:** mid-OMNI → alles stoppt, kein Resume.
9. **Bandwechsel:** OMNI stoppt automatisch, Pre-Flag reset.
10. **Mode-Wechsel:** OMNI stoppt automatisch.

---

## 9. Files-Anhang fuer Final-R1

`core/encoder.py` (Queue + Replace) +
`core/omni_tx.py` (peek_next) +
`core/qso_state.py` (_was_pretriggered) +
`ui/main_window.py` (_omni_pretriggered + HALT) +
`ui/mw_cycle.py` (Pretrigger-Check + Reset) +
`ui/mw_qso.py` (Pretrigger-Bypass in _on_send_message) +
`tests/test_encoder_queue.py` (NEU) +
`tests/test_p2_omni_pattern_fix.py` (NEU).

---

## 10. R1-Final-Befehl (nach Code)

```bash
cd "/Users/mikehammerer/Documents/KI N8N Projekte/FT8/SimpleFT8"
cat prompts/p2_omni_pattern_fix_v3.md | ./venv/bin/python3 tools/deepseek_review.py \
  core/encoder.py core/omni_tx.py core/qso_state.py \
  ui/main_window.py ui/mw_cycle.py ui/mw_qso.py \
  tests/test_encoder_queue.py tests/test_p2_omni_pattern_fix.py \
  > /tmp/r1_omni_pattern_final.txt
```

---

## 11. Naechste Schritte

1. **Mike-Freigabe V3** ⏳
2. **Compact #4** (vor Implementation, Kontext-Schoner)
3. **Implementation in 3 atomaren Commits:**
   - Commit 1: encoder.py Queue + Tests
   - Commit 2: omni_tx peek_next + main_window/mw_cycle/mw_qso/qso_state Pretrigger
   - Commit 3: 16 Tests + APP_VERSION 0.95.24 + Doku
4. **Final-R1 Code-Review**
5. **Field-Test mit Mike** (10+ Slots OMNI-Loop = Pattern-Beweis)
6. **Push** (mit v0.95.16-24 + P2-Tool + P3 zusammen)
