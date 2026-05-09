# P3.OMNI-PATTERN-FIX-2 — V2 Self-Review

**Datum:** 2026-05-09
**Vorgaenger:** V1 (`p3_omni_pattern_fix2_v1.md`)
**Stand:** V2 — kritischer Self-Review von V1, Code-Verifikation,
Lessons L1-L15

---

## 0. Wie ich V1 lese (frischer-KI-Modus)

V1 ist insgesamt schluessig. Stark sind die 4-Probleme-Diagnose,
die Wurzel-Analyse und der atomare-Commit-Plan. **Schwach** ist:

- Keine Code-Verifikation der QTimer-Details — Import fehlt, Lifecycle
  Argumentation duenn.
- `_OMNI_USER_START_GUARD_S = 1.5` vs `_OMNI_PRETRIGGER_OFFSET_S = 1.3`
  — magische Zahlen ohne Mathematik.
- Race-Conditions zwischen User-Toggle, Mode-Wechsel und QTimer-
  Lifetime sind nicht durchdacht.
- Test-Strategie zu duenn — QTimer-Tests sind notorisch flaky.
- `add_listening` bei laufendem QSO unklar (V1 §7.8 nur Frage).

V2 fuellt diese Luecken.

---

## 1. Lessons L1-L15

### L1 ⛔ KRITISCH — QTimer.singleShot kann auch verzoegert werden

V1 schreibt: „QTimer in GUI-Thread garantiert exact-delay (max ~10ms
Drift)". Das ist falsch. QTimer wird vom Qt-Eventloop bedient. Wenn
der Eventloop blockiert ist (z.B. durch `paintEvent`, langes Slot-
Handling, oder C-Library wie `ft8lib_decoder.decode`), wird auch
QTimer verzoegert — genauso wie Signal-Slots.

**Aber:** QTimer.singleShot mit `Qt.PreciseTimer` und ohne
zwischengeschaltete Signals ist immer noch deutlich praeziser als
ein Signal-Tick alle 100ms. **Empirisch typisch:** 0-50ms Drift bei
QTimer vs 0-1500ms bei Signal-Queue (im FT8-Decoder-Slot-Ende).

**V2-Aktion:** QTimer-Type explizit setzen:
```python
timer = QTimer(self)
timer.setSingleShot(True)
timer.setTimerType(Qt.PreciseTimer)
timer.timeout.connect(self._omni_pretrigger_fire)
timer.start(delay_ms)
```

Plus Defense-in-Depth: V2 behaelt `_on_cycle_tick`-Pretrigger als
Fallback (mit hoeherer Schwelle). Wenn QTimer aus irgendeinem Grund
nicht feuert, fallback bei `sic > dur - 0.7s` (zu spaet aber besser
als gar nicht).

### L2 ⛔ KRITISCH — Mathematik der Pretrigger-Schwelle

V1 nimmt `_OMNI_PRETRIGGER_OFFSET_S = 1.3` (gleich wie v0.95.24).
Encoder berechnet:
```python
sleep_dur = (next_boundary + TARGET_TX_OFFSET - 0.5) - time.time()
# TARGET_TX_OFFSET = -0.8
# = next_boundary - 1.3 - time.time()
```
Wenn Pretrigger bei `cycle_pos = dur - 1.3` feuert (jetzt = next_
boundary - 1.3), dann `sleep_dur = next_boundary - 1.3 - (next_
boundary - 1.3) = 0`. **Genau 0!** Encoder-`if sleep_dur > 0.001`
schlaegt nicht zu, faellt in `if silence_secs < 0.1`-Pfad mit
overshoot=0 (noch im sicheren Bereich da overshoot < 0.3).

**Aber:** wenn Pretrigger bei `dur - 1.2` feuert (100ms zu spaet),
ist `sleep_dur = -0.1` → silence_secs < 0.1 → overshoot = 0.1 →
unter 0.3-Schwelle → silence=0, sofort senden. Genau am Slot-Rand.
Das ist korrekt aber RF-DT haengt davon ab. RF-DT ~0.4s ist noch
ok (Decoder-Schwelle 0.5s).

Bei `dur - 0.8` (500ms zu spaet): overshoot = 0.5 > 0.3 → 2-Slot-Skip.

**Konsequenz:** sicheres Fenster fuer Pretrigger ist [dur - 1.3, dur - 0.8].
500ms breit. Bei QTimer-Drift unter 50ms easy zu treffen.

V2-Aktion: Konstante zu **`_OMNI_PRETRIGGER_OFFSET_S = 1.3`**
beibehalten. Plus Doku im Code mit dieser Mathematik.

### L3 ⛔ KRITISCH — User-Start-Guard Mathematik

V1 nimmt `_OMNI_USER_START_GUARD_S = 1.5`. Logik: bei `cycle_pos > dur - 1.5`
delayen bis naechster Slot. Sicherheit: encoder muss sleep_dur > 0
haben → `cycle_pos < dur - 1.3`. 1.5 gibt 200ms Reserve.

**Aber:** das ist die FALSCHE Logik. User-Toggle ON ruft
`_send_cq` der `next_boundary` berechnet. `next_boundary` ist NICHT
der aktuelle Slot-Anfang + dur, sondern wirklich der naechste Slot
mit passender Paritaet (kann auch 2 Slots weiter sein).

Encoder-Code (`_next_slot_boundary`):
```python
if self.tx_even is not None:
    want_even = self.tx_even
    if is_even == want_even and cycle_pos < 0.5:
        return float(cycle_num * _SLOT)  # aktueller Slot
    next_num = cycle_num + 1
    next_boundary = float(next_num * _SLOT)
    if (next_num % 2 == 0) != want_even:
        next_boundary += _SLOT
    return next_boundary
```

Bei User-Start mit `tx_even=False` (Block 2 Pos 0):
- Cycle-Position egal → `next_boundary = (cycle_num + 1 oder 2) * SLOT`
- Encoder wartet bis dort, sendet sauber.
- Drift kann nur eintreten wenn cycle_pos > next_boundary - 1.3 = dur - 1.3
  (im aktuellen Slot, der Encoder schon verworfen hat zu Gunsten des
  naechsten Slots).

**Ueberraschung:** User-Toggle hat eigentlich KEIN Drift-Problem,
weil Encoder den naechsten Slot waehlt! Mein V1-Befund Problem 3
ist **falsch diagnostiziert**.

**Tatsaechliches Problem:** Im Log:
```
[OMNI-TX] User-Start (next_is_even=True)
[TX] Drift-Vermeidung: overshoot=0.35s → Slot 1778320470.0
[TX] 09:53:59 Slot=ODD
```

**Hier ist `tx_even=True`** (Block 1, Pos 0 = Even gewollt). Aber
Slot=ODD. Wie kann das sein?

`is_even` der CURRENT cycle_num. Wenn aktueller Slot Even ist und
cycle_pos < 0.5, dann selber Slot (current cycle_num * SLOT). Aber
cycle_pos ist 14.x s (Mike toggelt mid-cycle, kurz vor Slot-Ende).
→ next_num = cycle_num + 1 → Odd-Slot. tx_even=True wollte Even →
next_boundary += SLOT → Even-Slot. Boundary ist `(cycle_num + 2) * SLOT`.

`silence_secs` = `next_boundary - 0.8 - now`. now ist bei cycle_pos=14.5,
also `cycle_num*SLOT + 14.5`. next_boundary = `(cycle_num+2)*SLOT`.
silence = `2*SLOT - 0.8 - 14.5 = 30 - 0.8 - 14.5 = 14.7s`. Da
`silence > 0.1` → kein overshoot, kein Drift. Encoder sendet
sauber 14.7s spaeter.

ABER im Log sehe ich: `[TX] Drift-Vermeidung: overshoot=0.35s → Slot 1778320470.0`.

**Nochmal Code lesen:**
```python
silence_secs = max(0.0, (next_boundary + TARGET_TX_OFFSET) - now)
if silence_secs < 0.1:
    overshoot = now - (next_boundary + TARGET_TX_OFFSET)
    if overshoot > 0.3:
        ...
```

Bei silence=14.7 ist silence > 0.1 → kein Drift-Branch! Der
Drift-Branch laeuft nur bei silence_secs < 0.1.

Also: das `overshoot=0.35` muss aus dem PRETRIGGER-Pfad kommen.
Tatsaechlich im Log direkt davor:
```
[OMNI-Pretrigger] Pos 1 Block 1 target_even=False cycle_pos=14.89s
[TX] 09:54:13 Slot=EVEN Freq=1000Hz
```

Pretrigger bei 14.89s → `sleep_dur = 15.0 - 1.3 - 14.89 = -1.19s` →
silence_secs < 0.1 (negative) → overshoot = 1.19 > 0.3 → DRIFT-Branch.

Encoder: `next_boundary += 2 * SLOT = +30s`. Slot=EVEN (next +30 = +2 Slots gleiche Paritaet).

**V2-FAZIT:** Problem 3 in V1 ist falsch — User-Start hat KEIN
Problem (encoder waehlt naechsten Slot mit silence_secs > 14s).
**Echtes Problem ist nur Problem 1** (Tick-Latency macht
Pretrigger zu spaet).

V2 verwirft 2.3 (`_OMNI_USER_START_GUARD_S`) komplett. Spart
Komplexitaet + Test.

### L4 ⛔ KRITISCH — QTimer-Lifecycle: Instanz-Timer fuer Cancel

V1 §7.1 fragt: persistenz oder pro-Cycle neu? V2-Antwort: **persistenz**
mit Instanz-Variable, aber single-shot semantically.

```python
# ui/main_window.py oder mw_cycle.py
self._omni_pretrigger_timer = QTimer(self)
self._omni_pretrigger_timer.setSingleShot(True)
self._omni_pretrigger_timer.setTimerType(Qt.PreciseTimer)
self._omni_pretrigger_timer.timeout.connect(self._omni_pretrigger_fire)
```

In `_on_cycle_start`:
```python
delay_ms = int((self.timer.cycle_duration -
                _OMNI_PRETRIGGER_OFFSET_S) * 1000)
self._omni_pretrigger_timer.start(delay_ms)  # restart bei Active-Run
```

In `_on_omni_stopped` und `_on_cancel`:
```python
self._omni_pretrigger_timer.stop()  # cancellt pending timer
```

`QTimer.stop()` ist idempotent. `start()` setzt zurueck (existing
timer wird neu gestartet — gewollt: Cycle-Restart cancelt alten und
plant neuen Pretrigger).

### L5 ✅ Cycle-Tick-Pretrigger als Fallback behalten

V1 §7.4 fragt: Cycle-Tick-Pretrigger entfernen? V2-Antwort:
**behalten** als Defense-in-Depth, aber Schwelle anpassen damit es
nur greift wenn QTimer ausnahmsweise nicht gefeuert hat.

```python
def _omni_pretrigger_check(self, sic, dur):
    # PRIMAER laeuft Pretrigger via QTimer. Dieser Pfad ist
    # Defense-in-Depth fuer den Fall dass QTimer aus irgendeinem
    # Grund nicht gefeuert hat. Schwelle hoeher (dur - 0.5) statt
    # dur - 1.3 — wenn QTimer aktiv waere haette er bei dur - 1.3
    # gefeuert + _omni_pretriggered=True gesetzt.
    if self._omni_pretriggered:
        return  # QTimer hat schon gefeuert
    threshold = dur - 0.5  # Notfall-Schwelle
    if sic < threshold:
        return
    # ... rest
    print(f"[OMNI-Pretrigger-FALLBACK] cycle_pos={sic:.2f}s — "
          f"QTimer hat NICHT gefeuert!")
```

Vorteil: KISS, kein verlorener Slot wenn QTimer mal patzt. Plus
Log-Marker damit Mike erkennt wenn QTimer-Logik versagt.

### L6 ✅ add_listening Spam-Risiko: bewerten

V1 §7.3 fragt: `add_listening` bei jedem RX-Slot oder nur wenn keine
Stationen? V2-Antwort: **bei jedem**, weil:
- Mike-Wunsch ist Lebenszeichen-Anzeige
- Konsistenz: mal-da, mal-nicht-da verwirrt
- 5-Min-Trim greift bereits via `_auto_trim_by_age` (`max_age_s=300`)

3 von 5 Slots * 4 slots/min = 12 RX-Lines/min = 60 in 5min. Vor Trim.
Plus normale add_tx + add_rx Decode-Lines. Insgesamt ~200 Zeilen
Live-View — handhabbar mit `_auto_trim_by_age`.

### L7 ✅ add_listening waehrend QSO

V1 §7.8: bei laufendem QSO ist OMNI pausiert (`is_paused()=True`).
`should_tx()` gibt `(True, None)` zurueck (active=True aber kein
RX-Slot-Skip). Tatsaechlich: pause() setzt nur `_paused=True`,
should_tx() prueft `if not self.active: return True, None`. Pause
hat kein eigenes Should-TX-Branch.

**Verifiziert via Code (`omni_tx.py:should_tx`):**
```python
if not self.active:
    return True, None
if not _TX_PATTERN[self._slot_index]:
    return False, None  # RX-Slot — egal ob paused
```

Bei pause() bleibt `should_tx` aktiv und zeigt RX/TX nach
`_slot_index` (der friert ein bei pause). Aber: bei pause wird
`advance` skipped → _slot_index bleibt fix → RX/TX bleibt fix.

Im QSO-Pfad ist cq_mode meistens False (QSO laeuft, kein CQ
geplant) → mw_qso_send_message-Filter greift sowieso nicht
(message ist `DA1TST DA1MHH ...`, kein CQ).

**V2-Action:** `add_listening` nur bei `message.startswith("CQ ")`
+ RX-Slot. Im QSO-Pfad nicht. Bereits jetzt der Fall durch `if
message.startswith("CQ "):` in `_on_send_message`.

### L8 ⛔ KRITISCH — Mode-Wechsel + active QTimer

V1 §7.6: Mode-Wechsel ruft `omni_tx.stop_omni_tx("ft_mode_change")`
in `mw_radio.py:212`. → emittet `omni_stopped("ft_mode_change")` →
`_on_omni_stopped`-Slot in main_window. **V2-Action:** Im
`_on_omni_stopped` zusaetzlich `self._omni_pretrigger_timer.stop()`.

Symmetrie: `_on_cancel` HALT-Pfad, `_on_btn_omni_cq_toggled(False)`,
und alle 3 mw_radio-Stops gehen alle ueber `omni_stopped`-Signal →
ein zentraler `stop()`-Aufruf reicht.

### L9 ⛔ KRITISCH — Test-Strategie QTimer

QTimer-Tests sind notorisch flaky in pytest-qt. V2-Strategie:

**T1 (Schedule-Test):** mock `QTimer.start()`. Erfasse delay_ms.
Ohne echtes Feuern.
```python
from unittest.mock import patch
with patch.object(self._omni_pretrigger_timer, 'start') as m:
    self._on_cycle_start(...)
    m.assert_called_once_with(13700)  # FT8: 15.0 - 1.3
```

**T2 (Fire-Test):** direkter Methoden-Aufruf `_omni_pretrigger_fire()`
ohne QTimer. Pre-Conds setzen + asserten dass `_send_cq` lief.

**T9 (Stop-Test):** mock `QTimer.stop()`. _on_omni_stopped emittieren.
Erfasse Aufruf.

So bleibt Test-Suite deterministisch + schnell.

### L10 ✅ Doppel-User-Toggle — kein Problem mehr

V1 §7.5: Mike klickt mehrfach. V2-FAZIT: durch Mike's Button-Label
(Problem 2 Fix) erkennt er Aktiv-Status. Plus QTimer-Stop bei
Toggle-Off cancelt pending QTimer. Kein Doppel-Trigger-Race.

### L11 ✅ KISS-Bewertung User-Start-Delay-Replay (V1 §7.5)

Da L3 zeigt User-Start hat KEIN Drift-Problem, faellt das ganze
Delay-Replay-Konstrukt weg. Spart Komplexitaet + Test + Race-Risk.

### L12 ⛔ Race-Doku — was passiert wenn QTimer firet WAEHREND
on_cycle_start des naechsten Slots laeuft?

Edge-Case: Slot-Boundary (15.0s exakt). `_on_cycle_start` startet
neuen Timer mit delay=13700ms. Ist alter Timer noch pending? Sollte
nicht, weil:
- Alter Timer war geplant fuer Cycle-Pos 13.7 in altem Slot
- Bei aktuellen Slot-Pos 0 (neuer Cycle) ist der alte Timer schon
  gefeuert oder gerade am Feuern.
- `start()` nach `start()` cancelt alten und startet neu.

Aber: race wenn QTimer.timeout() im Eventloop liegt + neuer Cycle-
Start ueberholt? V2-Antwort: `_omni_pretriggered`-Flag in
`_on_cycle_start` reset → erstes Aufruf von `_omni_pretrigger_fire`
greift. Wenn alter pending Timer feuert, sieht er Flag=False, ruft
peek_next im NEUEN Cycle-Kontext → korrekt.

**KEIN Bug**, aber Doku im Code.

### L13 ✅ add_listening Format-Konsistenz

V1 schlaegt vor: `09:48:45 [O] ←  Horche  …`. Das passt zum
bestehenden Format (`add_rx`: `09:48:45 [O] ←  Empf.   ...`).
Konsistent. V2 keep.

Farbe: `#666666` (grau), wie `add_info`. Damit es sich nicht
aufdraengt aber noch sichtbar ist.

### L14 ⛔ Initial-CQ bei User-Toggle — wer ruft was zuerst?

`_on_btn_omni_cq_toggled(True)`:
1. `omni_tx.start_with_parity_for_next_slot(next_is_even)` →
   active=True, `_slot_index=0`, block je nach Paritaet
2. `qso_sm.start_cq()` → cq_mode=True, `_send_cq()` synchron
3. `_send_cq` → `send_message.emit(msg)` → `mw_qso._on_send_message`
4. mw_qso prueft `omni_tx.active` → True → `should_tx()` →
   Pos 0 ist TX → `target_even` setzen → `encoder.transmit(...)`

**Problem:** `should_tx()` schaut `_slot_index=0`. Bei Block 1 ist
Pos 0 = Even. Wenn Mike toggelt im Even-Slot kurz vor Slot-Ende,
ist next_is_even=False → Block 2 → Pos 0 = Odd. should_tx returnt
target_even=False (Odd). Encoder waehlt next Odd-Slot. Soweit ok.

ABER: wenn cycle_pos = 14.5 (Mike toggelt sehr spaet), feuert auch
der QTimer (delay 13700ms = 13.7s) in JETZT — Wait, Timer wurde im
`_on_cycle_start` des AKTUELLEN Slots gestartet. cycle_pos ist seit
Cycle-Start vergangen. Wenn Toggle bei cycle_pos=14.5 → Timer feuert
seit ~0.8s in der Vergangenheit → Timer hat schon gefeuert (beim
Aufschlagen von cycle_pos=13.7).

ABER: `_omni_pretriggered=False` ist ja vom alten Cycle, weil OMNI
bei cycle_start NOCH NICHT aktiv war. Im `_on_cycle_start` setzt
mein Code:
```python
self._omni_pretriggered = False
if self._omni_tx.active and not self._omni_tx.is_paused():
    timer.start(...)
```

War OMNI im aktuellen Cycle-Start nicht aktiv → kein Timer-Start.
Dann toggelt Mike → kein QTimer pending → kein Pretrigger im
aktuellen Slot. Encoder waehlt next Slot via tx_even-Logik (silence_
secs > 14 → kein Drift). **Funktioniert!**

V2-Aktion: nichts noetig. L11 ist konsistent verifiziert.

### L15 ⛔ KRITISCH — Toggle-Off via QTimer waehrend QTimer pending

Mike toggelt OMNI ON. QTimer pending fuer cycle_pos=13.7. Mike
toggelt OFF bei cycle_pos=10. → `_on_btn_omni_cq_toggled(False)` →
`omni_tx.stop_omni_tx("manual_halt")` → emittet `omni_stopped` →
`_on_omni_stopped` → `qso_sm.stop_cq()` + `omni_pretrigger_timer.stop()`.

QTimer wird canceled BEVOR er feuert. Korrekt.

Aber Race wenn QTimer firet IM SELBEN Eventloop-Run wie
`stop_omni_tx`? Qt-Eventloop verarbeitet Events seriell — sollte
nicht moeglich sein. V2 markiert das als „Architektur-Annahme,
durch Qt-Eventloop-Garantie geschuetzt".

---

## 2. Neue Akzeptanzkriterien (V2)

V1 hatte 12 ACs. V2 ergaenzt:

| AC neu | Beschreibung |
|---|---|
| AC13 | Cycle-Tick-Fallback: `_omni_pretrigger_check` greift bei `sic > dur - 0.5s` UND `_omni_pretriggered=False` (= QTimer nicht gefeuert) |
| AC14 | Mode-Wechsel ruft `omni_pretrigger_timer.stop()` (via `_on_omni_stopped`) |
| AC15 | Band-Wechsel ruft `omni_pretrigger_timer.stop()` |
| AC16 | RX-Mode-Wechsel ruft `omni_pretrigger_timer.stop()` |
| AC17 | Doppelter `_on_cycle_start` (start nach start) verwirft alten QTimer |

**Verworfen aus V1:**
- AC6 (User-Start-Delay) — L3 zeigt User-Start hat kein Drift-Problem
- AC7 (User-Start-Sofort-Start) — gleicher Grund

Damit V2 = 10 ACs (AC1-AC5 + AC8-AC12 + AC13-AC17), 15 total.

---

## 3. Test-Strategie V2

| # | Test | AC |
|---|---|---|
| T1 | `test_pretrigger_qtimer_scheduled_in_cycle_start` (mock start) | AC1 |
| T2 | `test_pretrigger_qtimer_fire_calls_send_cq` (direkter fire-Aufruf) | AC2 |
| T3 | `test_update_omni_tx_sets_button_text` | AC3-AC5 |
| T4 | (geloescht — User-Start-Delay verworfen) | — |
| T5 | (geloescht — gleicher Grund) | — |
| T6 | `test_rx_slot_skip_calls_add_listening` | AC8 |
| T7 | `test_add_listening_format` | AC9 |
| T8 | `test_pretrigger_fallback_via_cycle_tick` | AC13 |
| T9 | `test_omni_stop_calls_timer_stop` | AC11/AC14 |
| T10 | `test_cycle_start_restarts_pending_timer` | AC17 |
| T11 | `test_inactive_omni_does_not_start_timer` | AC1 |
| T12 | `test_paused_omni_does_not_start_timer` | AC1 |

10 Tests. Erwartet: 1048 → 1058.

---

## 4. Risiken (V2 ueberarbeitet)

| # | Risiko | Mitigation |
|---|---|---|
| R1 | QTimer-Drift > 50ms im worst case | Cycle-Tick-Fallback bei `dur - 0.5s` |
| R2 | Multiple Stop-Reasons pruefen alle pretrigger_timer.stop | zentral via `omni_stopped`-Signal |
| R3 | QTimer-Zombie nach App-Restart | stop() im closeEvent |
| R4 | add_listening Spam in langem OMNI-Run | `_auto_trim_by_age` (5min) greift |
| R5 | Race: Toggle-On exakt am Slot-Boundary | Pretrigger fuer naechsten Cycle wird erst im NEUEN _on_cycle_start gestartet — sauber |
| R6 | Field-Test Edge-Case nicht getestbar | 10+ Slots OMNI-Loop |

---

## 5. Atomare Commits (V2)

| # | Commit | Files |
|---|---|---|
| 1 | QTimer-Pretrigger + Cycle-Tick-Fallback | `ui/main_window.py` (Timer-Init+Stop-Connect), `ui/mw_cycle.py` (Timer-Start+Fire-Methode), Tests T1-T2, T8-T12 |
| 2 | Button-Label dynamisch | `ui/control_panel.py` (update_omni_tx Text-Setter), Test T3 |
| 3 | RX-Slot Horche-Anzeige + APP_VERSION + Doku | `ui/qso_panel.py` (add_listening NEU), `ui/mw_qso.py` (Aufruf), `main.py` 0.95.24 → 0.95.25, HISTORY/HANDOFF/CLAUDE/Memory |

3 Commits + 1 Doku.

---

## 6. Offene Fragen fuer R1

1. **L1-L2 Mathematik-Pruefung:** Encoder `sleep_dur` mit
   TARGET_TX_OFFSET = -0.8 → V2-Schluss „sicheres Fenster
   [dur-1.3, dur-0.8]". R1 verifiziert?
2. **L3 User-Start kein Drift-Problem:** R1 bestaetigt encoder
   `_next_slot_boundary`-Logik?
3. **L4 QTimer-Lifecycle:** instance-variable + start() = Restart-
   Semantik korrekt? Race mit timeout-Connect bei mehrfachem Connect?
4. **L5 Cycle-Tick-Fallback:** Defense-in-Depth oder unnoetige
   Komplexitaet?
5. **L8 Mode-Wechsel:** `omni_stopped`-Signal-Subskription reicht
   fuer alle Stop-Reasons (manual_halt, ft_mode_change, band_change,
   rx_mode_change, totmann_expired, easter_egg_off, superseded)?
6. **L9 Test-Strategie:** Mock vs Echter QTimer in pytest-qt?
7. **L13 add_listening Format:** Mike-Konsistenz pruefen?
8. **L15 Stop-Race:** Qt-Eventloop-Garantie ausreichend?

---

## 7. Verbleibende Verifikations-Punkte fuer V3

V2 hat folgende Code-Punkte verifiziert:
- ✅ `core/timing.py:_tick_loop` — alle 100ms emit, Worker-Thread
- ✅ `ui/control_panel.py:965` — `btn_omni_cq` static text
- ✅ `ui/control_panel.py:1627` — `update_omni_tx`-Signatur
- ✅ `ui/qso_panel.py:155-200` — add_tx/add_rx Format
- ✅ `ui/qso_panel.py:271` — `_auto_trim_by_age(max_age_s=300)`
- ✅ `ui/mw_radio.py:210/212/327/411` — Stop-Reasons via `omni_stopped`
- ✅ `core/encoder.py:266-322` — silence_secs/overshoot Mathematik
- ✅ `core/omni_tx.py:should_tx` — pause-Verhalten
- ✅ `core/omni_tx.py:omni_stopped`-Signal — alle Stop-Reasons

V3 muss nochmal verifizieren:
- QTimer-Import + Init-Pfad (`Qt.PreciseTimer` Konstante)
- Test-Mocking pytest-qt-spezifisch
- closeEvent-Behandlung (App-Stop)
