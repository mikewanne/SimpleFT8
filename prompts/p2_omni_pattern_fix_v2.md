# P2.OMNI-PATTERN-FIX — V2 Self-Review

**Datum:** 2026-05-09
**Vorgaenger:** V1 (`p2_omni_pattern_fix_v1.md`)
**Stand:** Self-Review nach Code-Verifikation Z.265-322 in `core/encoder.py`.

---

## 0. V1-Auswertung — Was V1 richtig hat

✅ Wurzel-Hypothese (Encoder-Drift-Schutz vs OMNI-Slot-Start) ist korrekt.
✅ Berechnung overshoot = 0.8s bei `_send_cq` am cycle_pos=0.0X bestaetigt.
✅ Mike's Spec „kompletter Block-Start" korrekt erfasst (AC4-AC7).
✅ Drei Loesungsoptionen identifiziert (A=PreSlot, E=Hybrid, weitere
   Optionen B/C/D verworfen mit Begruendung).
✅ Erste TX (08:34:45) korrekt diagnostiziert als Toggle-Pfad mit
   Slot-Vorlauf (cycle_pos > 0.5s → kein Drift).

## 0.1 Was V1 uebersehen hat — 16 Lessons

### L1 — Sleep-Phase-Pfad checken (KRITISCH)

V1 hat den `sleep_dur > 0.001`-Pfad kurz erwaehnt aber nicht
durchgerechnet. Konkret:
```python
sleep_dur = (next_boundary + TARGET_TX_OFFSET - 0.5) - time.time()
```

Bei Mid-Cycle-Trigger (cycle_pos = 13.5s im aktuellen Slot):
- next_boundary = next slot = current_cycle_start + 15.0
- TARGET_TX_OFFSET = -0.8
- sleep_dur = (next + (-0.8) - 0.5) - now
- now = current_cycle_start + 13.5
- next - now = 1.5s
- sleep_dur = 1.5 - 0.8 - 0.5 = 0.2s > 0.001 → Encoder schlaeft 0.2s

Bei cycle_pos = 13.0s: sleep_dur = 2.0 - 1.3 = 0.7s.
Bei cycle_pos = 14.0s: sleep_dur = 1.0 - 1.3 = -0.3s → kein Sleep,
silence_secs Pfad → overshoot kritisch.

**Praktische Schwelle:** cycle_pos < 13.7s (FT8) → sicher Sleep, kein
Drift. Schwelle muss konservativ sein (CycleTick-Granularity 100ms).

### L2 — Pretrigger braucht Doppel-Trigger-Schutz

cycle_tick laeuft 10x/Sek. Pretrigger bei cycle_pos > 13.5 darf nur
EINMAL pro Slot triggern (sonst encoder.transmit mehrfach mit selber
Message).

**Schutz:** Flag `_omni_pretriggered: bool = False` auf MainWindow.
Bei cycle_start zuruecksetzen, bei Pretrigger setzen.

### L3 — _send_cq aus on_cycle_end weiterhin noetig

Bei Normal-CQ (kein OMNI): _send_cq laeuft aus on_cycle_end mit
state=CQ_WAIT, timeout_cycles>=1. Encoder hat tx_even FIX gesetzt
(von `_on_cq_clicked` einmalig) → next_boundary findet matching slot
→ kein Drift.

**Konsequenz:** Pretrigger NUR fuer OMNI-Pfad. Normal-CQ bleibt
unveraendert in on_cycle_end-Pfad.

### L4 — Initial-OMNI-Activate (Toggle) braucht KEINEN Pretrigger

Mike-Klick auf btn_omni_cq → `_on_btn_omni_cq_toggled` → `start_cq()`
→ `_send_cq()` SOFORT (mid-cycle). Encoder berechnet next_boundary
mit Slot-Vorlauf. Funktioniert wie bisher (08:34:45-Beweis).

**Keine Aenderung am Toggle-Pfad noetig.**

### L5 — cycle_pos-Schwelle pro Modus berechnen

| Mode | Slot | TARGET_TX_OFFSET | Sleep-Marge | Schwellen-Fenster |
|---|---|---|---|---|
| FT8 | 15.0s | -0.8 | -0.5 | cycle_pos 13.0-13.7s |
| FT4 | 7.5s | -0.8 | -0.5 | cycle_pos 5.5-6.2s |
| FT2 | 3.8s | -0.8 | -0.5 | cycle_pos 1.8-2.5s |

Berechnung: `slot_duration - 1.3s - sicherheit (0.5s)` bis
`slot_duration - 1.3s` (knapp vor Slot-Ende).

KISS: Konstante `_OMNI_PRETRIGGER_OFFSET = 1.3s vor Slot-Ende` →
`pretrigger_at = slot_duration - 1.3s` (knapp vor Drift-Schwelle).
Plus Mindestabstand 0.5s zwischen Slot-Start und Pretrigger
(verhindert Race mit on_cycle_start).

### L6 — Race mit on_cycle_end

Pretrigger bei cycle_pos=13.5s schedult TX fuer nachsten Slot
(boundary+15s wenn current+15s = next boundary).
Bei cycle_pos=15.0 (next slot start) laeuft on_cycle_end. State ist
CQ_CALLING (nach Pretrigger _set_state). on_cycle_end macht NICHTS
weil state != CQ_WAIT.

ABER: nach TX-Ende laeuft on_message_sent → state=CQ_WAIT,
timeout_cycles=0. Bei naechstem cycle_start: timeout_cycles=1 →
_send_cq triggert WIEDER (alte Logik).

**Loesung:** Bei OMNI-Pfad in `qso_state.py:on_cycle_end` den
CQ_WAIT-Branch NICHT triggern (skipt _send_cq fuer OMNI). Dafuer
neuer Mechanismus: `_omni_active`-Flag im qso_sm oder Pruefung in
mw_qso ob OMNI active.

ALTERNATIV: on_cycle_end `_send_cq` BLEIBT, aber Pretrigger nutzt
`_omni_skip_state_change`-Flag-Mechanik um State CQ_CALLING zu
vermeiden — Encoder hat schon TX gestartet, on_cycle_end-_send_cq
blockt am encoder.is_transmitting (skipt). Hmm das ist tricky.

**Sauberste Loesung:** OMNI laeuft Pretrigger-Pfad. on_cycle_end
prueft ob OMNI active und in dem Fall skipt CQ_WAIT-Branch.
Implementation: in on_cycle_end vor CQ_WAIT-Branch checken
ob `self._omni_active_callback` (von mw_qso gesetzt) returnt True →
skip.

Oder einfach: Pretrigger setzt `qso_sm._was_pretriggered=True`,
on_cycle_end prueft Flag → skip + reset Flag.

### L7 — Pretrigger-Reentrancy zwischen Modes

Was wenn Mike Mode-Wechsel waehrend Pretrigger? Pretrigger laeuft im
Mid-Cycle des alten Modes, bei Mode-Wechsel: omni_tx.stop_omni_tx
(„ft_mode_change") → omni.active=False. Aber Encoder hat schon
transmit() mit alter Message — TX laeuft im naechsten Slot des NEUEN
Modes. Slot-Boundary unterscheidet sich!

**Schutz:** stop_omni_tx triggert encoder.abort() im selben Pfad.
Aktuell: stop_omni_tx setzt active=False, emitted omni_stopped.
mw_qso._on_send_message-Hook wuerde naechsten _send_cq cancellieren,
aber transmit-in-flight ist schon raus.

KISS: Mode-Wechsel ist seltener Edge-Case. Aktueller TX wird
abgebrochen via UI (band/mode-changed → cancel), nicht critical.

### L8 — Encoder Single-TX-Schutz greift

`encoder.transmit()` Z.180-189: bei is_transmitting → print SKIP,
return. Also doppel-transmit (Pretrigger + on_cycle_end fallback)
ist sicher — nur erster transmit aktiv.

### L9 — `_omni_skip_state_change`-Flag funktioniert weiter

Pretrigger laeuft auch bei RX-Slots (Pos 2,3,4). Wenn naechster Slot
ein RX-Slot: should_tx returnt (False, None). mw_qso._on_send_message
setzt qso_sm._omni_skip_state_change=True, return. _send_cq sieht
Flag → kein State-Wechsel zu CQ_CALLING. State bleibt CQ_WAIT.
on_cycle_end im naechsten Slot: state=CQ_WAIT, timeout_cycles+=1
... aber jetzt PRETRIGGER ueberschreibt das wieder.

**Wichtig:** Pretrigger MUSS bei jedem Slot laufen (auch RX-Slots),
sonst Pattern bricht.

### L10 — _send_cq Pre-Cond-Check

`qso_sm._send_cq` checkt `_pending_reply` und delegiert ggf. zu
`_process_cq_reply`. Bei Pretrigger im RX-Slot wuerde `_pending_reply`
gesetzt sein (von letzter cycle's RX-Decode), aber wir wollen
RX-Slot nicht TXen. _process_cq_reply wuerde TX_REPORT triggern.

**Schutz:** Pretrigger checkt ZUERST `should_tx()` und triggert _send_cq
NUR wenn TX-Slot. Bei RX-Slot setzt Pretrigger nur das Flag und
setzt KEIN _send_cq aus.

Alternatives: bei RX-Slot wird gar nichts getan. State bleibt
CQ_WAIT. Wenn _pending_reply (CQ-Reply) angekommen, in
_process_cq_reply geht Reply → start QSO → OMNI pause via
_pause_omni_if_active.

OK Pretrigger fuer RX-Slot = NO-OP (kein _send_cq). Nur bei TX-Slot
triggert Pretrigger.

ABER: dann muss die _slot_index trotzdem advanced werden! Sonst bleibt
es bei Pos 0 fuer immer.

**Reihenfolge:**
1. Pretrigger checkt cycle_pos in Pretrigger-Fenster + flag != True
2. Setzt flag = True
3. Berechnet next_pos = (omni._slot_index + 1) % 5
4. Berechnet next_block (mit Rollover-Logik)
5. Berechnet target_even fuer next_pos
6. Wenn Pattern[next_pos] = TX:
   - encoder.tx_even = target_even
   - _send_cq()
7. (Pos-advance erfolgt hier NICHT — der naechste cycle_start
   advanced die Position)

Hmm das ist gefuehlt komisch. Vielleicht:

**Alternative Reihenfolge:**
1. Pretrigger checkt
2. Setzt flag = True
3. omni.peek_next_pos() → returnt Tupel (next_pos, will_be_block,
   target_even, is_tx)
4. Wenn is_tx:
   - encoder.tx_even = target_even
   - _send_cq()
5. Beim NAECHSTEN cycle_start: omni.advance() — _slot_index += 1
   sauber

**Best Practice:** Pretrigger berechnet OHNE State-Mutation.

### L11 — Auto-Hunt-Konflikt minimal

Auto-Hunt ruft `start_qso()` direkt — kein _send_cq. Plus Auto-Hunt
ist mit OMNI mutually-exclusive (siehe v0.95.22 Toggle-Logic). Also
kein Konflikt.

### L12 — P1.9 Encoder-Replace-Logik

Bei Pretrigger laeuft encoder.transmit. Sleep-Phase wartet 0.7s.
Wenn _pending_reply mid-Sleep ankommt, qso_state.try_replace_pending_tx
emittet → mw_qso._on_try_replace_pending_tx → encoder.request_replace.

Konflikt? `request_replace` checkt is_transmitting+nicht audio_started
→ True → _replace_message gesetzt → Encoder-Worker wacht aus Sleep
auf, re-encodet mit Reply-Message statt CQ → TX im selben Slot.

Funktioniert weiter. Plus: in _on_try_replace_pending_tx wird
`_pause_omni_if_active` gerufen → omni.pause() → naechster
Pretrigger-Lauf checkt is_paused() → kein Trigger. ✅

### L13 — Erster Pretrigger nach Activate

Mike-Klick toggle:
- start_with_parity_for_next_slot → _slot_index=0, active=True, paused=False
- start_cq → _send_cq → encoder.transmit → TX im current oder next slot

Naechster cycle_tick laeuft. cycle_pos < Pretrigger-Schwelle → kein
Trigger. Bei cycle_pos > Schwelle → Pretrigger checkt next_pos = 1,
Pattern[1] = TX → encoder.transmit. encoder.is_transmitting (vom
ersten TX) → SKIP. Hmm, dann wird Pos 1 nicht gesendet.

**Problem:** Erster TX dauert 12.64s. Wenn Slot-Duration 15s:
TX-Audio fertig bei cycle_pos = 12.64 + Stille (0.5s vor Slot-Start).
Sagen wir TX laeuft cycle_pos=-0.5 bis cycle_pos=12.14. tx_finished
bei 12.14. is_transmitting = False bei 12.14.

Pretrigger-Schwelle 13.0s → bei 13.0s ist is_transmitting=False →
encoder.transmit() OK. Pos 1 kann gesendet werden im naechsten Slot.

OK wenn Schwelle nach TX-Ende liegt — sollte passen.

### L14 — Encoder.transmit thread-collision

Bei Pretrigger pos=N (TX), encoder.transmit() startet Thread-1.
Bei cycle_start pos=N+1, kein on_cycle_end-_send_cq (geschuetzt
durch Flag). Aber mid-Sleep der Thread-1 → naechster Pretrigger
pos=N+1 bei pos=13.5s läuft → encoder.transmit() startet Thread-2?

`encoder.transmit` checkt is_transmitting. Thread-1 ist mid-Sleep,
is_transmitting=True → Thread-2 SKIP.

Ist das richtig? Wir WOLLEN ja Thread-2 (Pos 1 TX). Aber Thread-1
ist noch nicht fertig.

Hmm das ist ein Problem. Bei Block 1 Pos 0 (TX Even) Pretrigger
läuft Slot N. Thread-1 wartet bis next_boundary (Slot N+1) = TX im
Slot N+1. Encoder läuft TX bei Slot N+1.

Bei Pretrigger Slot N+1 (current N+1, cycle_pos=13.5): wir wollen
Pos 1 TX im Slot N+2. encoder.transmit() würde aber SKIP weil
Thread-1 noch transmittet (Audio läuft 12.64s bis cycle_pos=12.14
im Slot N+1).

Wait — cycle_pos im Slot N+1 ist 13.5s, aber TX-Audio endet bei
cycle_pos=12.14 (in Slot N+1). Also is_transmitting=False bei 13.5.
encoder.transmit() startet Thread-2. ✓

Nochmal Mike's Pattern Block 1: TX, TX, RX, RX, RX (jede 15s):
- Slot 0 (pos=0-15): TX-Audio läuft pos=-0.5 bis 12.14 (dann
  tx_finished, is_transmitting=False)
- Slot 0 Pretrigger bei pos=13.5: encoder NICHT transmittet → OK,
  transmit() startet Thread-2 für Slot 1 TX
- Slot 1 (pos=0-15): TX-Audio läuft pos=-0.5 bis 12.14
- Slot 1 Pretrigger bei pos=13.5: encoder NICHT transmittet → 
  triggert für Slot 2 — aber Slot 2 = RX!

Wait Block 1: Pos 0=TX Even, Pos 1=TX Odd, Pos 2=RX, Pos 3=RX, Pos 4=RX.

- Slot 0 Pretrigger bei pos=13.5: triggert für Pos 1 (TX) → Thread-2
- Slot 1 Pretrigger bei pos=13.5: triggert für Pos 2 (RX) → keine
  encoder.transmit, nur Pattern-Skip
- Slot 2 Pretrigger bei pos=13.5: triggert für Pos 3 (RX) → keine
  encoder.transmit, Pattern-Skip
- Slot 3 Pretrigger bei pos=13.5: triggert für Pos 4 (RX) → keine
  encoder.transmit, Pattern-Skip
- Slot 4 Pretrigger bei pos=13.5: triggert für Pos 0 BLOCK 2
  (Rollover) → Block 2 Pos 0 = TX Odd → encoder.transmit für Slot 5

OK Pattern stimmt.

### L15 — Block-Switch-Logik im Pretrigger

OMNI's `advance()` macht aktuell Block-Switch automatisch bei
slot_index 4→0. Wenn wir advance() aus on_cycle_start weiter
benutzen (keine Aenderung), und Pretrigger nur peek (no advance),
dann passiert Block-Switch sauber bei slot_index Rollover.

Aber Pretrigger braucht NEXT-Pos und NEXT-Block. Wenn current
slot_index=4 (RX-Pos 4), next slot_index=0 (Pattern[0]=TX), next
Block=switch.

`omni.peek_next()` Methode:
```python
def peek_next(self) -> tuple[int, int, bool, bool]:
    """Returnt (next_slot_index, next_block, target_even, is_tx)
    OHNE State-Mutation.
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

### L16 — Pretrigger-Skip wenn omni paused/inactive

Bei pause (QSO laeuft) oder inactive (kein OMNI) → Pretrigger NO-OP.

```python
def _omni_pretrigger(self):
    if not self._omni_tx.active or self._omni_tx.is_paused():
        return
    if self._omni_pretriggered:
        return  # schon dieser Slot gemacht
    # ...
```

Reset bei cycle_start: `self._omni_pretriggered = False`.

---

## 1. Verfeinerter Plan (Option E — Hybrid Mid-Cycle Pretrigger)

### 1.1 Architektur

**Pretrigger-Flow:**
1. `mw_cycle._on_cycle_tick(seconds_in_cycle, cycle_duration)` (10x/s)
2. Pruefe: `seconds_in_cycle > _OMNI_PRETRIGGER_OFFSET[mode]` AND
   `not self._omni_pretriggered` AND
   `self._omni_tx.active` AND
   `not self._omni_tx.is_paused()`
3. Setze `self._omni_pretriggered = True`
4. `next_idx, next_block, target_even, is_tx = omni.peek_next()`
5. Wenn `is_tx`:
   - `encoder.tx_even = target_even`
   - `qso_sm._send_cq()` (state-aware: laeuft nur wenn cq_mode + state in IDLE/CQ_WAIT/CQ_CALLING)
   - Encoder transmittet im naechsten Slot mit korrekter Paritaet
6. Wenn NOT is_tx (RX-Slot):
   - Nichts tun. State bleibt CQ_WAIT.
   - on_cycle_end-_send_cq darf NICHT triggern (siehe 1.2)

**Slot-Start:**
1. `mw_cycle._on_cycle_start(cycle_num, is_even)`
2. Reset: `self._omni_pretriggered = False`
3. `qso_sm.on_cycle_end()` — wenn OMNI active: skipt CQ_WAIT-Branch
4. `if not _omni_tx.is_paused(): _omni_tx.advance()` — _slot_index++

### 1.2 qso_state on_cycle_end Schutz

Aktueller Code:
```python
if self.state == QSOState.CQ_WAIT:
    self.qso.timeout_cycles += 1
    if self.qso.timeout_cycles >= 1 and self.cq_mode:
        self._send_cq()
    return
```

Aenderung: bei OMNI active KEIN _send_cq.
```python
if self.state == QSOState.CQ_WAIT:
    self.qso.timeout_cycles += 1
    if self.qso.timeout_cycles >= 1 and self.cq_mode:
        # P2.OMNI-PATTERN-FIX: bei OMNI laeuft _send_cq aus Pretrigger
        # (mw_cycle._on_cycle_tick), nicht hier — sonst Drift.
        if not (self._omni_active_callback and self._omni_active_callback()):
            self._send_cq()
    return
```

Callback-Mechanismus: qso_sm braucht Zugriff auf omni-State. Saubere
Loesung: callback-Setter:
```python
# qso_state.py __init__:
self._omni_active_callback = None

# main_window setup:
qso_sm.set_omni_active_callback(lambda: self._omni_tx.active and not self._omni_tx.is_paused())
```

### 1.3 omni_tx.peek_next neue Methode

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

### 1.4 mw_cycle._on_cycle_tick erweitern

```python
@Slot(float, float)
def _on_cycle_tick(self, seconds_in_cycle: float, cycle_duration: float):
    if not self.rx_panel._rx_active:
        return
    self.control_panel.update_cycle_bar(seconds_in_cycle, cycle_duration)
    # P2.OMNI-PATTERN-FIX: Mid-Cycle-Pretrigger
    self._omni_pretrigger_check(seconds_in_cycle, cycle_duration)

def _omni_pretrigger_check(self, sic, dur):
    if self._omni_pretriggered:
        return
    if not self._omni_tx.active or self._omni_tx.is_paused():
        return
    if not self.qso_sm.cq_mode:
        return
    if self.qso_sm.state not in (QSOState.IDLE, QSOState.CQ_WAIT,
                                  QSOState.CQ_CALLING):
        return
    # Schwelle abhaengig von slot_duration
    threshold = dur - 1.3  # FT8: 13.7s, FT4: 6.2s, FT2: 2.5s
    if sic < threshold:
        return
    # Pretrigger ausfuehren
    self._omni_pretriggered = True
    next_idx, next_block, target_even, is_tx = self._omni_tx.peek_next()
    if not is_tx:
        return  # naechster Slot ist RX, kein TX
    self.encoder.tx_even = target_even
    self.qso_sm._send_cq()  # triggert send_message → mw_qso._on_send_message
    print(f"[OMNI-Pretrigger] Pos {next_idx} Block {next_block} "
          f"target_even={target_even} cycle_pos={sic:.1f}s")

@Slot(int, bool)
def _on_cycle_start(self, cycle_num, is_even):
    self._omni_pretriggered = False  # Reset fuer neuen Slot
    # ... rest unveraendert
```

### 1.5 qso_state._send_cq darf state=CQ_CALLING setzen oder skippen

Aktueller Code (post v0.95.23):
```python
def _send_cq(self):
    ...
    self._omni_skip_state_change = False
    self.send_message.emit(msg)
    if not self._omni_skip_state_change:
        self._set_state(QSOState.CQ_CALLING)
```

Bei Pretrigger (TX-Slot): mw_qso._on_send_message setzt nicht
_omni_skip_state_change → Flag bleibt False → _set_state(CQ_CALLING).
✅ Pattern-richtig.

Bei Pretrigger (RX-Slot): wir rufen _send_cq gar NICHT auf
(`if not is_tx: return`). State bleibt CQ_WAIT. ✅

Bei Mike-Klick toggle (Initial-TX): start_cq → _send_cq → CQ_CALLING.
Encoder hat Slot-Vorlauf, kein Drift. ✅

### 1.6 mw_qso._on_send_message bleibt unveraendert

Flag-Pattern ist weiterhin korrekt. Pretrigger schickt _send_cq nur
bei TX-Slots → mw_qso._on_send_message setzt encoder.tx_even (war
schon vorher gesetzt durch Pretrigger), encoder.transmit. Slot-
Filter-Pruefung in _on_send_message ist redundant (Pretrigger filtert
schon), aber unschaedlich.

Nein wait — Pretrigger setzt encoder.tx_even in mw_cycle, Pretrigger
ruft dann qso_sm._send_cq → emit → mw_qso._on_send_message. Dort
wird ggf. encoder.tx_even ueberschrieben:
```python
if self._omni_tx.active:
    send_ok, target_even = self._omni_tx.should_tx()
    ...
```

ABER `should_tx` nutzt `_slot_index` AKTUELL (current slot, nicht
next). Das ist falsch fuer Pretrigger (we want NEXT).

**Wichtig:** Pretrigger ruft _send_cq direkt nachdem encoder.tx_even
schon richtig gesetzt ist. Dann mw_qso._on_send_message darf nicht
NOCHMAL setzen, sonst falsch.

**Loesung:** mw_qso._on_send_message Pruefung im Pretrigger-Pfad
abschalten via Flag, oder: Pretrigger nutzt direkt encoder.transmit
ohne ueber qso_sm._send_cq zu gehen.

**Alternativer cleaner Ansatz:** Pretrigger ruft direkt
encoder.transmit("CQ ...") und setzt qso_sm._set_state(CQ_CALLING) +
qso_sm._dbg.log. Dann wird `mw_qso._on_send_message` NICHT
aufgerufen (kein send_message-Emit). Aber dann fehlt presence-check,
print etc.

**Saubere Loesung:** Pretrigger setzt Flag `_omni_pretrigger_active=True`
auf qso_sm. mw_qso._on_send_message checkt Flag:
- Wenn True: Pretrigger hat schon tx_even gesetzt → KEIN should_tx-Check
- Wenn False: normaler OMNI-Filter mit should_tx-Check

Reihenfolge:
1. Pretrigger: `qso_sm._omni_pretrigger_active = True; encoder.tx_even = target_even`
2. Pretrigger: `qso_sm._send_cq()` → emit
3. mw_qso._on_send_message: checkt _omni_pretrigger_active → skipt should_tx-Block
4. encoder.transmit() → TX im naechsten Slot
5. mw_qso._on_send_message returnt → qso_sm._send_cq returnt
6. Pretrigger: `qso_sm._omni_pretrigger_active = False`

OK das ist KISS-Lösung.

### 1.7 Field-Test-Erwartung nach Fix

```
08:34:32  Mike-Klick (Slot 08:34:30 [E], cycle_pos=2.0):
          - omni.start_with_parity_for_next_slot(False) → Block 2, _slot_index=0
          - qso_sm.start_cq() → _send_cq() → emit → mw_qso._on_send_message
          - omni.active, NICHT pretrigger → should_tx() Pos 0 = (True, False)
          - encoder.tx_even=False, transmit()
          - Encoder: cycle_pos=2.0 > 0.5 OR is_even=True != want_even=False
          - next_num=cycle_num+1=Odd → next_boundary=08:34:45 (Odd) ✓
          - sleep_dur = 08:34:45 - 0.8 - 0.5 - 08:34:32 = 11.7s ✓
          - TX bei 08:34:45 [O]

08:34:43.5 (Slot 08:34:30 cycle_pos=13.5s):
          - Pretrigger checkt: omni.active && !paused && cq_mode
          - peek_next() → Pos 1 Block 2 → (1, 2, True, True) — TX Even
          - encoder.tx_even=True (ueberschreibt False von 08:34:32)
          - qso_sm._send_cq() → encoder.transmit() — ABER is_transmitting!
          - encoder SKIP (Thread-1 noch in Sleep)

Hmm Problem!
```

**Problem L17 — Doppelt-encoder.transmit Race:**

Bei Pretrigger im Slot N (current TX läuft) → transmit() für Slot
N+1 fails (is_transmitting=True). Pos N+1 wird nicht gesendet.

**Loesungsidee A:** Pretrigger erst nach TX-Ende. TX dauert max
13.14s (12.64 Audio + 0.5 silence). Bei FT8 (15s slot): TX endet
bei cycle_pos=13.14. Pretrigger-Schwelle 13.5s → TX schon fertig.

Aber overlap-Toleranz nur 0.36s — bei langsamen Systemen kritisch.

**Loesungsidee B:** Encoder unterstuetzt 2 TX-Threads serialisiert
(queue). transmit() reiht ein, naechster startet wenn vorheriger
fertig.

Ist das vernuenftig? Aktuell: 1 Thread, transmit() SKIP wenn
laufend. Refactor zu Queue ist groesserer Eingriff.

**Loesungsidee C:** Pretrigger erst wenn !is_transmitting. Pruefen
in cycle_tick. Falls TX laeuft bei Schwelle, warten 100ms (naechster
tick) — Pretrigger spaeter. Aber dann verschiebt sich das Pretrigger-
Fenster — kann ueber Slot-Ende rutschen.

**Loesungsidee D:** Pretrigger schedult FUER NACH Encoder-Ende.
Konkret: bei cycle_pos=13.5 ist Encoder noch TXend (Audio bis
13.14). Wir warten 0.4s mehr.

```python
threshold_a = dur - 1.86  # nach Audio-Ende, 0.5s puffer
threshold_b = dur - 1.0   # vor Drift
if not (threshold_a < sic < threshold_b):
    return
```

Aber Audio-Ende ist nicht exakt — encoder.tx_finished feuert
asynchron via Qt-Signal. Race.

**Loesungsidee E (saubersten):** encoder.transmit() schedult
FUER ZUKUENFTIGEN SLOT auch wenn aktueller TX noch laeuft. Eigene
Sleep-Logik im Worker — wartet sowieso bis next_boundary, also
kann jetzt schon scheduled werden.

Heute aber SKIP wenn is_transmitting. Refactor: queue mit max 1
pending TX. Naechster Worker-Lauf nutzt pending message.

Hmm das ist ein Encoder-Refactor das ueber Pattern-Fix hinaus geht.

**KISS-Loesung F (nochmal):** Pretrigger-Schwelle: cycle_pos
zwischen `dur - 1.0` und `dur - 0.5` (bei FT8: 14.0-14.5s).
Encoder ist bei pos=13.5 fertig (Audio bis 13.14). Bei pos=14.0
ist 0.86s Puffer.
Aber sleep_dur = next - 0.8 - 0.5 - now = 1.0 - 1.3 = -0.3s →
KEIN Sleep, geht in silence_secs-Pfad → drift > 0.3 → +30s ZURUECK
zum alten Bug.

Pretrigger-Schwelle muss zwischen pos=13.14 (TX fertig) und
pos=13.7 (sleep_dur > 0) liegen → 0.56s Fenster. Bei cycle_tick
10Hz → Pretrigger trifft ein bei pos=13.2-13.6s. Da gibts einen
Sweet-Spot.

Aber sehr eng. Bei pos=13.5 (Mitte): is_transmitting? Audio fertig
bei pos≈13.14, Encoder feuert tx_finished signal, asynchron geht es
in Qt-Queue, irgendwann processed → is_transmitting=False bei
pos≈13.2-13.4 (je nach Latenz).

Bei pos=13.5 ist is_transmitting wahrscheinlich False. Aber nicht
garantiert.

**Race-Schutz noetig.**

### L17 entscheidend — Encoder Single-TX vs Pattern-Folge

Dies ist der schwierigste Punkt im Plan. Pre-Emergency: Mike will
Pattern-Korrektheit. Aktuell: Encoder serialisiert TX (1 zur Zeit).

**Vorschlag:** encoder.transmit erweitern, dass 1 zusaetzliche
„pending" TX-Message gequeued wird. Neuer Worker laeuft NACH
aktuellem fertig.

```python
def transmit(self, message):
    if self._is_transmitting:
        # Statt SKIP: pending queue
        self._pending_tx_message = message
        return
    self._tx_thread = threading.Thread(target=self._tx_worker, args=(message,))
    self._tx_thread.start()

def _tx_worker(self, message):
    self._is_transmitting = True
    self._abort_event.clear()
    try:
        self._tx_worker_inner(message)
        # Nach erstem TX: Check pending
        while self._pending_tx_message:
            next_msg = self._pending_tx_message
            self._pending_tx_message = None
            self._tx_worker_inner(next_msg)
    finally:
        self._is_transmitting = False
```

Aber das ist Encoder-Refactor. Risk: Race mit P1.9 replace,
Test-Brüche.

**Architektur-Entscheidung muss DeepSeek-R1 vorgelegt werden.**

---

## 2. Offene Fragen fuer R1

1. Ist Mid-Cycle-Pretrigger (Option E) der richtige Pfad oder gibt es
   eine elegantere Loesung?
2. Wie wird Race „Pretrigger vs aktueller TX-Thread" gelöst?
   - Variante 1: Pretrigger-Schwelle eng (13.5-13.7s) und auf
     fast-Audio-Ende vertrauen
   - Variante 2: Encoder-Queue mit pending-Message
   - Variante 3: anderer Trigger-Mechanismus (z.B. tx_finished-Signal
     triggert Pretrigger fuer nachsten Slot)
3. Mike's Spec „kompletter Block-Start" ist via
   `start_with_parity_for_next_slot` (`_slot_index=0`) erfuellt — gibt
   es weitere Edge-Cases (z.B. cancel mid-pretrigger)?
4. Pretrigger-Skip bei RX-Slots korrekt (kein _send_cq) — oder
   muessen wir trotzdem state-progress signalisieren?
5. cycle_tick-Granularity 100ms vs Pretrigger-Fenster 200-500ms —
   genug Sicherheit?

---

## 3. R1-Auftrag fuer V2-Phase

Siehe V1 §10. Plus:
- Pruefe L1-L17 auf Halluzinationen / Luecken
- Bewerte Variante 1/2/3 fuer Race-Schutz (Pretrigger vs current TX)
- Bewerte ob Encoder-Refactor (Variante 2) sicher mit P1.9 Replace
  und v0.80 Drift-Schutz koexistiert
- Schlage Test-Strategie fuer Race-Variante vor
