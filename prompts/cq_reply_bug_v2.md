# CQ-Reply-Bug — Diagnose V2 (2026-05-05, Self-Review von V1)

**Status:** V2 = Self-Review von V1 als „frische KI". V1 hatte 7
Hypothesen, einen Code-Pfad-Trace und Mike's Philosophie-Bezug. V2
ergaenzt: Caller-Queue-Pfad (fehlte), doppelte Block-Logik in
`_process_cq_reply` (zu schwach), „manchmal klappt manchmal nicht"-
Mechanik (Mike's Aussage explizit erklaert), Folgebug-Risiko nach Fix,
GUI-Thread-Block-Punkte als Race-Verstaerker.

KEINE Loesung — nur erweiterte Analyse fuer V3/R1-Pruefung.

---

## 1. Symptom (unveraendert aus V1)

Field-Test 05:30-05:33 UTC, 2026-05-05. FlexRadio (DA1MHH, eigene App)
im **CQ-Modus**. Icom IC-7300 (DA1TST, manuell EVEN) antwortet auf den
CQ. App **ignoriert die Antwort und sendet weiter CQ** statt Report.

```
05:27:30 [E] → Sende DA1TST DA1MHH -21         ← Vor-QSO Phase 1
05:27:45 [O] ← Empf. DA1MHH DA1TST R+18
05:28:00 [E] → Sende DA1TST DA1MHH RR73        ← TX_RR73 → DA1TST in _worked_calls
05:28:15 [O] ← Empf. DA1MHH DA1TST 73          ← QSO 1 fertig

05:30:45 [O] → Sende CQ DA1MHH JO31            ← Bug-Setup beginnt
05:31:15 [O] → Sende CQ DA1MHH JO31
05:31:30 [E] ← Empf. DA1MHH DA1TST JO31        ← IGNORIERT (delta 210s)
05:31:45 [O] → Sende CQ DA1MHH JO31            ← Sollte Report sein
05:32:15 [O] → Sende CQ
05:32:30 [E] ← Empf. DA1MHH DA1TST JO31        ← IGNORIERT (delta 270s)
05:32:45 [O] → Sende CQ
05:33:00 [E] ← Empf. DA1MHH DA1TST JO31        ← IGNORIERT (delta 300s — Grenzfall!)
05:33:15 [O] → Sende CQ
```

**Wichtig — bisher nicht beachtet:** Im `:33:00`-Slot ist delta exakt
**300.0s** (300.x mit Sub-Sekunden-Drift). `_is_worked_recently` prueft
`time.time() - ts > self._WORKED_BLOCK_SECS` (strict `>`, qso_state.py:
173). Bei delta < 300.0 oder == 300.0 → noch geblockt. Bei delta > 300.0
→ Block weg. Field-Test zeigt :33:00 IGNORIERT → delta minimal unter
oder gleich 300s. Mike's vor-QSO RR73 hat seinen `_worked_calls[DA1TST]`-
Eintrag bei (vermutlich) `:28:00.x` plus on_message_sent-Latenz; daher
delta `:33:00.x - :28:00.x` ≈ 300.0±ε.

**Mike's Aussage 2026-05-05:**
> „Manchmal klappt ein QSO, manchmal nicht. Tritt auch im echten Betrieb
> mit fremden Stationen auf."

V2 erklaert das jetzt explizit (Section 7 — „Manchmal-klappt-manchmal-
nicht-Mechanik").

---

## 2. System-Setup (unveraendert)

- FlexRadio = DA1MHH = unsere App (CQ-Caller, ANT1)
- IC-7300 = DA1TST = Gegenstation (manuell EVEN)
- Beide auf 40m FT8
- ANT2 = nur RX (Hardware-Schutz)

---

## 3. Architektur — 4 Threads + GUI-Event-Loop

V1 hatte 3 Threads. Korrekt sind **4** (GUI-Thread + 3 Background):

| Thread | Wake-Zeit (FT8) | Emittiert | Sender |
|---|---|---|---|
| Decoder (`core/decoder.py:127-179`) | Slot+13.5s | `cycle_decoded`, `message_decoded` (n×), `cycle_finished` | `Decoder` Instanz |
| Decoder-Worker (`_process_cycle`) | ad hoc | (selbe Signale) | `Decoder` (gleicher Sender) |
| Encoder-TX-Worker (`core/encoder.py:159-296`) | Boundary-0.8s | `tx_started`, `tx_finished` | `Encoder` Instanz |
| Timer (`core/timing.py`) | Slot-START + cycle_tick | `cycle_start` (boundary), `cycle_tick` | `Timer` Instanz |
| GUI-Thread | (event-loop) | dispatched alle Slots | (Konsument) |

**Qt-Garantien:**
- Pro Sender: FIFO. cycle_decoded → message_decoded(n×) → cycle_finished
  ist garantiert (alle vom Decoder).
- **Zwischen verschiedenen Sendern: KEINE Reihenfolge.**
- emit-Reihenfolge in der GUI-Queue = chronologische Aufruf-Reihenfolge
  → bei kollidierenden emits aus 3 Threads (Decoder + Encoder + Timer)
  ist die Dispatch-Reihenfolge der **Aufruf-Reihenfolge im realen Zeit-
  ablauf** ungefaehr gleich, aber nicht garantiert.

**Signal-Verbindungen (komplette Liste, Quelle: mw_qso.py + mw_cycle.py
+ ihre __init__-Pfade in `ui/main_window.py`):**

| Signal | Slot | Effekt |
|---|---|---|
| `Decoder.cycle_decoded` | `mw_cycle._on_cycle_decoded` | Tabellen-Update, Diversity-Akku, Stats, **GUI-block-Risiko** |
| `Decoder.message_decoded` | `mw_cycle.on_message_decoded` | → `qso_sm.on_message_received(msg)` |
| `Decoder.cycle_finished` | `mw_cycle._on_cycle_finished` | → `qso_sm.on_decoder_finished()` |
| `Encoder.tx_started` | `mw_qso._on_tx_started` | qso_panel.add_tx, Antennen-Label |
| `Encoder.tx_started` | (Lambda mw_radio) | `control_panel.set_tx_active(True)` |
| `Encoder.tx_finished` | `mw_qso._on_tx_finished` | → `qso_sm.on_message_sent()` |
| `Timer.cycle_start` | `mw_cycle._on_cycle_start` | → `qso_sm.on_cycle_end()`, Antennen-Switch (Diversity), `_omni_tx.advance` |
| `Timer.cycle_tick` | `mw_cycle._on_cycle_tick` | UI-Bar-Update |

**GUI-Thread-Block-Punkte (V1 nicht erwaehnt):**

`mw_cycle._on_cycle_decoded` (laeuft VOR `on_message_decoded` weil
cycle_decoded VOR message_decoded emit'd wird) macht:
- `_assign_slot_parity` (schnell)
- `_update_dt_correction` (schnell)
- `_handle_diversity_measure` (mit `_diversity_lock`-Akquise)
- `_handle_diversity_operate` (Tabelle-Redraw, accumulate_stations,
  histogramm-update, _stats_logger.log_cycle, _emit_map_snapshot)
- `_run_ap_lite_rescue` (kann lange dauern wenn AP-Lite enabled)
- `_run_auto_hunt` (entscheidet ueber Hunt-Start)
- `_dx_tune_dialog.feed_cycle` (wenn aktiv)

→ Diese Verarbeitung kann bei vielen Stationen + AP-Lite enabled
**Sekunden** dauern. Waehrenddessen warten message_decoded, tx_finished,
cycle_start in der GUI-Queue. **Race-Verstaerker**.

Zudem `on_state_changed` (mw_qso.py:168-209) wird bei jedem
`_set_state`-Aufruf gefeuert — touch'd btn_cq, btn_advance, btn_cancel,
control_panel.set_tx_active, _omni_tx.on_qso_started, _ap_lite.clear,
decoder.priority_call. Mehrere setStyleSheet/setEnabled. Direkt-
verbunden, also synchron.

---

## 4. Code-Pfad-Trace — DA1TST-Test ms-genau (V1 mit Korrekturen)

| UTC | Thread | Aktion | State |
|---|---|---|---|
| :31:14.2 | Encoder-Worker (CQ#2) | wake, ptt_on, audio start :31:14.7 | CQ_CALLING |
| :31:27.7 | Encoder-Worker | send_audio fertig, ptt_off, **tx_finished emit** | CQ_CALLING |
| :31:27.7+ε | GUI-Thread | dispatched → `on_message_sent`: state=CQ_CALLING + _pending_reply=None → **CQ_WAIT, tc=0** | CQ_CALLING → CQ_WAIT |
| :31:30.0 | Timer | `cycle_start.emit` (Slot-Boundary :31:30) | — |
| :31:30.0+ε | GUI-Thread | dispatched → `_on_cycle_start` → `qso_sm.on_cycle_end()`: state=CQ_WAIT, tc=0+1=1, `cq_mode=True` → **`_send_cq()`** → state=CQ_CALLING, **`_pending_reply=None`**, `send_message.emit("CQ DA1MHH JO31")` → `mw_qso._on_send_message` → `encoder.transmit("CQ ...")` | CQ_WAIT → CQ_CALLING |
| :31:30.0+ε | Encoder-Worker (CQ#3) | startet daemon Thread, sleep bis next_boundary-0.8 (für ODD) = :31:44.2 | CQ_CALLING |
| :31:43.5 | Decoder-Loop | wake (Slot+13.5), forks `_process_cycle` daemon thread fuer :31:30-Slot-Audio | CQ_CALLING |
| :31:43.5–:31:44.5 | Decoder-Worker | preprocessing + LDPC-Decode + Subtraction | CQ_CALLING |
| :31:44.5± | Decoder-Worker | dekodet "DA1MHH DA1TST JO31", emit cycle_decoded → message_decoded(DA1TST) → cycle_finished | CQ_CALLING |
| :31:44.5+ε | GUI-Thread | dispatched cycle_decoded → `_on_cycle_decoded` (heavy work, sub-sekunden) | — |
| :31:44.5+ε' | GUI-Thread | dispatched message_decoded → `on_message_decoded` → `qso_sm.on_message_received(msg_DA1TST)` | CQ_CALLING |
| | | qso_state.py:459-461: state in (IDLE, CQ_WAIT, CQ_CALLING) UND msg.is_grid (kein RR73/73) → kein log-warning, kein return | |
| | | qso_state.py:465-474: NICHT in `_caller_queue`-Pfad (state=CQ_CALLING ist NICHT „QSO-aktiv") | |
| | | qso_state.py:477-491: state CQ_CALLING ✓, msg.target == DA1MHH ✓, msg.is_grid ✓ | |
| | | qso_state.py:480-482: **`_is_worked_recently("DA1TST")`** — `_worked_calls["DA1TST"] = :28:00.x`, delta `:31:44.5 - :28:00.x = ~224s` < 300s → **return True** | CQ_CALLING |
| | | → **`return` BEVOR `_pending_reply = msg`** (qso_state.py:482) | _pending_reply bleibt None |
| | | print: `"[QSO] DA1TST ignoriert — kuerzlich gearbeitet (beendet ist beendet)"` | |
| :31:44.5+ε'' | GUI-Thread | dispatched cycle_finished → `_on_cycle_finished` → `qso_sm.on_decoder_finished()` | CQ_CALLING (ist nicht WAIT_REPORT/WAIT_RR73 → kein Effekt) |
| :31:44.2 | Encoder-Worker (CQ#3) | wake aus sleep | CQ_CALLING |
| :31:44.2+ | Encoder-Worker | ptt_on, audio start :31:44.7 | CQ_CALLING |
| :31:45.0 | Timer | cycle_start.emit (Slot :31:45) → on_cycle_end: state=CQ_CALLING (kein match → no action) | CQ_CALLING |
| :31:57.7 | Encoder-Worker | send_audio fertig, ptt_off, **tx_finished emit** | CQ_CALLING |
| :31:57.7+ε | GUI-Thread | dispatched → `on_message_sent`: state=CQ_CALLING + _pending_reply=None → **CQ_WAIT, tc=0** | CQ_CALLING → CQ_WAIT |
| :32:00.0 | Timer | cycle_start → on_cycle_end: CQ_WAIT, tc=0+1=1 → **`_send_cq()`** → CQ_CALLING, encoder.transmit("CQ ...") | CQ_CALLING |
| :32:14.7 | RF | **CQ raus (Bug-Beweis)** | |

**Zyklus wiederholt sich** — bei jedem `:32:30`, `:33:00`, ... wird
DA1TST erneut empfangen, jeweils geblockt durch _is_worked_recently
(delta wachst um 30s pro Iteration). Bei delta > 300s (etwa :33:00.x mit
small drift, oder spaetestens :33:30) faellt die Sperre — DA1TST wird
ab dann verarbeitet.

**→ Field-Test 100% reproduziert.** Hauptwurzel: Hypothese A.

---

## 5. Hypothesen-Liste — neu sortiert nach Wahrscheinlichkeit

### Hypothese A (BESTAETIGT — Hauptwurzel) — `_WORKED_BLOCK_SECS = 300` blockiert CQ-Reply

**Code-Evidenz unveraendert aus V1.** Beweise:

1. `core/qso_state.py:120` — Konstante `_WORKED_BLOCK_SECS = 300`
2. `core/qso_state.py:168-176` — `_is_worked_recently` (strict `>`)
3. `core/qso_state.py:441-443` — Eintrag in TX_RR73-Branch
4. `core/qso_state.py:480-482` — Block in `on_message_received` (Hauptpfad)
5. `core/qso_state.py:191-193` — **Block in `_process_cq_reply`** (zweite Stelle):
   ```python
   if self._is_worked_recently(msg.caller):
       print(f"[QSO] {msg.caller} ignoriert — kuerzlich gearbeitet (beendet ist beendet)")
       return
   ```
6. `core/qso_state.py:470` — Block in Caller-Queue-Pfad (dritte Stelle):
   ```python
   if (self.cq_mode
           and self.state not in (QSOState.IDLE, QSOState.CQ_WAIT, QSOState.CQ_CALLING)
           and msg.target == self.my_call
           and (msg.is_grid or msg.is_report)
           and msg.caller != self.qso.their_call
           and not self._is_worked_recently(msg.caller)
           and not any(q.caller == msg.caller for q in self._caller_queue)):
       self._caller_queue.append(msg)
   ```

**→ DREI Stellen mit `_is_worked_recently`-Check.** Bei Fix muessen alle
drei adressiert werden, sonst halber Fix.

**Wahrscheinlichkeit:** 100% fuer DA1TST-Test. **Erklaert auch fremde
Stationen** wenn sie innerhalb 5 Min zweimal anrufen — siehe Section 7.

**Folgebug-Risiko nach Fix:** siehe Section 8.

**Mike's Position 2026-05-05 (unveraendert):**
> „Wenn eine bekannte Station uns ruft, hat das vlt sein Grund (kein 73
> erhalten). Ueberlassen wir es dem Funker."

→ Sperre = Overengineering, widerspricht CLAUDE.md „Projekt-Philosophie".

### Hypothese A.1 (NEU in V2) — Caller-Queue mit identischem Block

`core/qso_state.py:121, 463-474`:
```python
self._caller_queue: list = []   # Warteliste

# in on_message_received:
if (self.cq_mode
        and self.state not in (QSOState.IDLE, QSOState.CQ_WAIT, QSOState.CQ_CALLING)
        and msg.target == self.my_call
        and (msg.is_grid or msg.is_report)
        and msg.caller != self.qso.their_call
        and not self._is_worked_recently(msg.caller)            # ← Block #3
        and not any(q.caller == msg.caller for q in self._caller_queue)):
    self._caller_queue.append(msg)
```

Caller-Queue ist die zweite Quelle fuer CQ-Replies — **waehrend aktivem
QSO** rufen weitere Stationen uns an. Nach `_resume_cq_if_needed`
(Z. 368-382) wird Pop und `_process_cq_reply()` ausgeloest. Auch hier
greift im `_process_cq_reply` (Z. 191-193) der Block.

→ Eine bekannte Station die uns waehrend eines anderen QSO ruft, wird
gar nicht erst in die Warteliste aufgenommen. Sie wird auch nicht
beantwortet.

**Wahrscheinlichkeit:** Pfad existiert und funktioniert wie Hauptpfad,
gleicher Bug. Wird selten getriggert weil meist erst nach QSO-Ende
gerufen wird.

### Hypothese B — Race tx_finished vs message_decoded (Realismus-Bewertung)

V1 hatte das offen. V2 schaerft:

**B1 (message_decoded VOR tx_finished, Standardfall):**
- Decoder fertig: Slot+13.5+~0.5-1.0s decode = Slot+14.0-14.5s
- Encoder TX endet: Slot-Boundary -0.8 + Audio-Dauer (~13s) = Slot+12.2s
  ABER das ist fuer den TX im aktuellen Slot. Der TX dessen tx_finished
  hier zaehlt ist der vom **vorigen** Slot — endet also Slot-2.8s ≈
  Slot-Anfang + ~12.2s, das ist VOR Slot+13.5.
- → tx_finished kommt typisch ~1.5s VOR message_decoded (B2-Pfad).

**Korrektur V1**: B2 ist nicht „theoretisch moeglich", sondern **der
Standardfall**. tx_finished kommt regelmaessig VOR message_decoded.

**B2-Folge (state=CQ_WAIT durch on_message_sent → direct
_process_cq_reply via on_message_received):**
- on_message_received: state=CQ_WAIT → _pending_reply=msg
- Z. 488-489: state in (IDLE, CQ_WAIT) → `_process_cq_reply()` direkt
- Z. 191-193 in _process_cq_reply: _is_worked_recently → return
- → Bug greift auch hier.

**Race ist fuer den Bug irrelevant**, weil Hypothese A in beiden Pfaden
greift.

**Aber**: ohne Hypothese A (nach Fix) waere der Race wieder relevant —
siehe Hypothese C.

**Multi-Modus:** Bei FT4 (7.5s slot) und FT2 (3.8s slot) ist der Zeit-
Buffer enger. Aber: tx_finished kommt immer noch VOR message_decoded
weil Encoder Audio-Trim 1.5s (FT8) bzw kuerzere Werte hat. Race-Pfad-
Verteilung bleibt aehnlich.

### Hypothese C — `_send_cq()` clearet `_pending_reply` zwischen Set und Process

V1 hatte Pfad B2+C als Risiko. V2 schaerft:

**Wann passiert das?**
Pfad: state=CQ_CALLING → on_message_received setzt `_pending_reply=msg`
→ tx_finished kommt → `on_message_sent` setzt CQ_WAIT (kein pending,
weil pending wurde gerade nochmal überschrieben?)

ABER: in `on_message_sent` Z. 388-396:
```python
def on_message_sent(self):
    if self.state == QSOState.CQ_CALLING:
        if self._pending_reply:                  # checkt VOR CQ_WAIT-Switch
            print("[QSO] CQ fertig — verarbeite gemerkte Antwort")
            self._process_cq_reply()
            return
        self._set_state(QSOState.CQ_WAIT)
        self.qso.timeout_cycles = 0
```

Wenn `_pending_reply` gesetzt ist → `_process_cq_reply` direkt. Wenn
None → CQ_WAIT.

**Race-Risiko C: Slot-START Timer feuert ZWISCHEN
`_pending_reply=msg`-set (in on_message_received) und der Verarbeitung
in on_message_sent.**

Im GUI-Thread sind alle Slots seriell. Wenn message_decoded und
cycle_start beide in der Queue sind, werden sie in emit-Reihenfolge
verarbeitet. Wenn message_decoded zuerst gepostet wurde (Decoder Slot+
13.5+~1s) und cycle_start spaeter (Slot+15.0 = Boundary), wird
message_decoded zuerst dispatched.

ABER: cycle_start fuer den **naechsten** Slot kommt zwischen den TX-
Slots:
- :31:30.0 cycle_start → on_cycle_end (vor TX :31:45 Audio start :31:44.7)
- :31:45.0 cycle_start → on_cycle_end (waehrend TX-Audio laeuft)
- :32:00.0 cycle_start → on_cycle_end (nach TX-Ende :31:57.7)

**Realismus-Pfad C ohne worked_recently (fremde Station, hypothetisch
nach Fix von Hypothese A):**
- :31:14-:31:27 TX :31:15-CQ
- :31:27.7 tx_finished → on_message_sent: CQ_CALLING + None → CQ_WAIT, tc=0
- :31:30.0 on_cycle_end: CQ_WAIT, tc=1, `_send_cq()` → CQ_CALLING,
  `_pending_reply=None`, encoder.transmit("CQ ...")
- :31:43.5 Decoder wakes
- :31:44.5 message_decoded → on_message_received: CQ_CALLING →
  `_pending_reply=msg`, return
- :31:44.2-:31:57.7 TX-Audio :31:45-CQ
- :31:57.7 tx_finished → on_message_sent: CQ_CALLING + msg → 
  `_process_cq_reply()` → state=TX_REPORT, send_message(report)
- :32:00.0 cycle_start → on_cycle_end: state=TX_REPORT, **kein Match**
  in den CQ_WAIT/WAIT_REPORT/WAIT_RR73-Branches → no action ✓
- → :32:15 Report TX (sofern encoder.tx_even nach
  `tx_slot_for_partner.emit` korrekt = ODD)

**→ Pfad C ist HARMLOS solange Hypothese A nicht greift.** state=CQ_WAIT
wird durch _process_cq_reply ueberschrieben bevor naechstes
on_cycle_end laufen kann.

**Aber Edge-Case:** wenn `_process_cq_reply` BEVOR der Slot-START-Timer
laeuft, aber die Station ein anderes Slot-Parity hat als wir → encoder
wartet 2 Slots → sehr knapp.

V1's Pfad B2+C-Hypothese (`_send_cq` zwischen Set und Process) scheint
**nicht der Bug**. R1 sollte das verifizieren.

### Hypothese D — `on_cycle_end` `>= 1` zu aggressiv (verworfen für DA1TST)

`core/qso_state.py:298`: `if self.qso.timeout_cycles >= 1 and self.cq_mode`.

`>= 1` heisst: 1 voller RX-Slot warten, dann CQ. Das ist Standard-WSJT-X
Verhalten (CQ jeden zweiten Slot). NICHT zu aggressiv.

V1 hatte das spekulativ angedeutet — V2 verwirft.

### Hypothese E — Slot-Mismatch (verworfen)

V1 zeigte schon: Slot-Werte stimmen ueberein. Verworfen.

### Hypothese F — `is_grid` Strict 4-char (verworfen für DA1TST-Test)

`message.py:72-78`: 4-char Letter+Letter+Digit+Digit.

`JO31` = `J`, `O`, `3`, `1` → alle Bedingungen ✓ → is_grid=True. Im
Field-Test erfuellt. → **kein Bug-Faktor fuer DA1TST.**

Edge-Case fuer 6-char-Locator (`JO31QQ`) bleibt offen, aber FT8-Standard
sendet 4-char. Verworfen fuer aktuellen Bug.

### Hypothese G — Test-Coverage-Luecke (kein Bug, Auslöser-Faktor)

`tests/test_modules.py:372-410` (`test_qso_cq_flow`) testet **nur**
folgenden Pfad:

```python
sm.start_cq()                  # State=CQ_CALLING
sm.on_message_sent()           # → CQ_WAIT
msg = ...                       # frische Station, NICHT in _worked_calls
sm.on_message_received(msg)    # → TX_REPORT
```

**Was fehlt:**
1. Test mit `_worked_calls[their_call] = time.time()` gesetzt vor
   `on_message_received` → erwartet: WIRD blockiert (Hypothese A).
2. Test fuer state=CQ_CALLING + message_decoded waehrend TX laeuft →
   sollte `_pending_reply` setzen, dann `on_message_sent` verarbeitet.
3. Test fuer Caller-Queue-Pfad (state=TX_REPORT, andere Station ruft
   uns) mit/ohne worked_recently.

**Konsequenz:** Bug konnte sich seit Wochen halten, weil keine Test-
Reproduktion ihn aufzeigt. Test-Suite zeigt 756 ✓ — aber das bedeutet
NICHT dass der CQ-Reply-Pfad gegen Sperre robust ist.

### Hypothese H (NEU in V2) — Auto-Hunt-Interferenz (gering)

`mw_cycle.py:487-512` — `_run_auto_hunt`:
```python
def _run_auto_hunt(self, messages):
    if not self._auto_hunt.active:
        return
    _idle = self.qso_sm.state in (QSOState.IDLE, QSOState.TIMEOUT)
    _candidate = self._auto_hunt.select_next(...)
    if not _candidate:
        return
    ...
    self.qso_sm.start_qso(_candidate.call, ...)
```

Wenn Auto-Hunt aktiv ist und state=IDLE/TIMEOUT → Hunt-QSO startet.
Aber im CQ-Modus ist state typischerweise CQ_CALLING/CQ_WAIT → Auto-Hunt
greift nicht.

`_auto_hunt.active` wird nur explizit gesetzt — im Field-Test war
Auto-Hunt vermutlich aus.

→ **Nicht relevant fuer DA1TST-Test.** R1 pruefe ob Auto-Hunt-Pfade in
anderen Symptom-Berichten relevant sein koennen.

---

## 6. Architekturdiagramm

```
[Decoder-Thread]                  [GUI-Event-Loop]                [Encoder-Worker]
slot+13.5 wake                                                    boundary-0.8 wake
  │                                                                  │
  ├ _process_cycle (Thread)                                          ├ ptt_on
  │   ├ decode                                                       ├ send_audio (BLOCKING)
  │   ├ emit cycle_decoded ───→  _on_cycle_decoded (heavy)            │   pacing 5.33ms/pkt
  │   ├ emit message_decoded ──→ on_message_decoded                  │
  │   │                            └ qso_sm.on_message_received      │
  │   │                                ├ Block A (Z. 480-482) ◄──┐   │
  │   │                                └ _pending_reply=msg      │   │
  │   └ emit cycle_finished ──→ _on_cycle_finished               │   │
  │                                └ qso_sm.on_decoder_finished  │   │
  │                                                              │   ├ ptt_off
                                                                  │   ├ emit tx_finished ───┐
[Timer-Thread]                                                    │                          │
boundary wake                                                     │                          │
  └ emit cycle_start ──────────→ _on_cycle_start                  │                          │
                                   └ qso_sm.on_cycle_end          │                          │
                                       ├ CQ_WAIT-Branch:          │                          │
                                       └   _send_cq() ◄───────────┘                          │
                                                                                              │
                                  _on_tx_finished ◄─────────────────────────────────────────┘
                                       └ qso_sm.on_message_sent
                                           ├ CQ_CALLING + pending → _process_cq_reply
                                           │   └ Block A (Z. 191-193) ◄── (zweite Stelle)
                                           └ CQ_CALLING + None → CQ_WAIT
```

---

## 7. „Manchmal klappt manchmal nicht"-Mechanik (NEU in V2)

Mike's Aussage erklaert sich aus der `_worked_calls`-Sperre:

| Situation | Verhalten |
|---|---|
| Erste Station ruft uns | **klappt** — kein _worked_calls-Eintrag |
| Selbe Station 5 Min später (Mike sendet RR73, Gegenstation kein 73) | **klappt nicht** — gesperrt bis +300s |
| Andere Station + erste war 5 Min vorher | **klappt** (andere Station nicht in _worked_calls) |
| Selbe Station 6 Min später | **klappt** — Sperre abgelaufen, aus _worked_calls geloescht |

→ Das „manchmal" = abhaengig davon ob die antwortende Station in den
letzten 5 Min ein QSO mit uns gemacht hat. Mike's Wort „im echten
Betrieb mit fremden Stationen" deckt sich damit, weil DX-Pileups oft
dieselben Stationen mehrmals rufen (kein 73 erhalten, schwacher Pfad,
QSB).

---

## 8. Folgebug-Risiko nach Fix von Hypothese A (NEU in V2)

Wenn `_WORKED_BLOCK_SECS` raus oder auf 0 gesetzt wird:

**1. Doppelte ADIF-Eintraege:**
- Station X → QSO → RR73 → ADIF-Eintrag
- Station X ruft 30s spaeter erneut → wir antworten (kein Block) →
  zweites QSO → zweiter ADIF-Eintrag
- ADIF-Datei haette zwei Eintraege fuer X innerhalb weniger Minuten
- QRZ-Uploader filtern oft Duplikate, aber nicht alle

**Mitigation-Optionen** (zu pruefen in Plan, nicht in V2):
- Optional: Statt Block, Warning-Log (Funker entscheidet)
- Optional: Funker bekommt Notification „X hat sich gerade nochmal
  gemeldet — antworten?" (Mike's „Funker-Entscheidung"-Prinzip)
- Default: nichts machen, ADIF-Datei kann manuell bereinigt werden

**2. Endlos-Schleife wenn Station nie 73 sendet:**
- Wir senden RR73, Station hat unser RR73 nicht → wiederholt Grid
- Wir antworten mit Report (neues QSO startet) → senden RR73
- Station hat wieder kein RR73 → wiederholt Grid
- ... endlos

**Real-Welt-Schutz:**
- Nach 5 Min ist die Station typischerweise weg (QSB, Funker geht weg)
- WSJT-X hat aehnliche Logik nicht → praktisch kein Problem
- Beide Stationen mit Funker dahinter → der gibt nach 2-3 Versuchen auf

→ **Kein blockierender Folgebug**, aber Plan-Phase muss UI-Hinweis
ueberlegen (Mike's Filter-Idee aus dem RX-Panel).

**3. Stats-Risiko: gering.**
- _worked_calls wird nur in TX_RR73-Pfad gesetzt
- Stats-Logger nutzt _worked_calls nicht
- → kein Stats-Effekt

---

## 9. Was V2 NICHT macht

- Keine Loesung. Keine Implementierungs-Vorschlaege.
- Keine `git diff`-Vorlagen. Reine Diagnose + erweiterte Hypothesen.
- V3 = nochmal frische KI; R1 = DeepSeek-Reasoner-Pruefung.

---

## 10. Auftrag an V3 / R1

Bitte pruefen:

1. **Vollstaendigkeits-Check:** Gibt es Pfade die V2 immer noch
   uebersieht? Insbesondere:
   - `cancel()` (qso_state.py:624-632) — clearet _pending_reply.
     Wann wird das aufgerufen ausser HALT? `mw_qso._on_cancel`? Nur
     UI-Trigger?
   - `_resume_cq_if_needed` Pfade (qso_state.py:368-382). Nach Timeout/
     Hunt-Ende. Loescht das _pending_reply unbeabsichtigt?
   - `stop_cq` (qso_state.py:154-158) — was passiert wenn cq_mode=False
     mid-Reply gesetzt wird? `_process_cq_reply` Z. 186-188 prueft das,
     also gilt cq_mode-Disable als „Reply aufgeben".

2. **Code-Evidenz-Verifikation:** Stimmen alle Datei:Zeile-Referenzen
   in V2 gegen aktuellen Code-Stand (v0.95.1, commit `04388ef`)?
   Insbesondere die drei `_is_worked_recently`-Stellen
   (qso_state.py:480, 191, 470) — gibt es noch eine vierte?

3. **Race-Realismus B2:** V2 sagt B2 ist Standardfall (tx_finished
   typisch ~1.5s VOR message_decoded). Stimmt das? Bei FT4/FT2 anders?
   Bei AP-Lite enabled (decode dauert laenger)?

4. **Folgebug-Risiko (Section 8):** Stimmen die Argumente? Ist die
   Endlos-Schleifen-Mitigation wirklich „beide Funker geben auf"?
   Oder gibt's einen technischen Pfad-Schutz den V2 uebersieht?

5. **Mike's Philosophie-Check:** Architektonisch korrekt — Filter im
   RX-Panel statt State-Machine? Das ist Mike's Aussage; R1 pruefe ob
   sie technisch tragfaehig ist (z.B. ob „Neue Stationen"-Filter
   tatsaechlich existiert in `ui/rx_panel.py` und `ui/control_panel.py`).

6. **Test-Coverage:** Welche minimalen Test-Faelle sollten den Bug
   exposen? (V2 listet 3 Test-Faelle in Hypothese G — sind das die
   richtigen?)

7. **Stats-Effekt:** wirklich kein Risiko? `_worked_calls` wird
   nirgendwo ausser im qso_state genutzt — verifiziere via grep
   `_worked_calls` ueber gesamten Code.

Antworten bitte mit:
- bestaetigt / widerlegt pro Hypothese
- konkreten Datei:Zeile-Referenzen fuer neue Befunde
- KEINE Loesung — nur Analyse-Ergaenzung. Loesung kommt nach V3 in
  separatem Plan-Workflow.

---

## 11. Anhang — Quick-Reference (erweitert vs. V1)

| Datei:Zeile | Funktion / Variable |
|---|---|
| `core/qso_state.py:120` | `_WORKED_BLOCK_SECS = 300` |
| `core/qso_state.py:121` | `_caller_queue: list = []` (Warteliste) |
| `core/qso_state.py:154-158` | `stop_cq()` — cq_mode=False, → IDLE |
| `core/qso_state.py:160-166` | `_send_cq()` — clearet `_pending_reply=None` |
| `core/qso_state.py:168-176` | `_is_worked_recently()` — strict `>` |
| `core/qso_state.py:178-238` | `_process_cq_reply()` |
| `core/qso_state.py:191-193` | `_is_worked_recently`-Block #2 |
| `core/qso_state.py:273-318` | `on_cycle_end` — Slot-START |
| `core/qso_state.py:320-366` | `on_decoder_finished` — Slot-ENDE |
| `core/qso_state.py:368-385` | `_resume_cq_if_needed` (Caller-Queue-Pop) |
| `core/qso_state.py:388-446` | `on_message_sent` — TX-Ende |
| `core/qso_state.py:441-443` | `_worked_calls[their_call] = time.time()` |
| `core/qso_state.py:450-491` | `on_message_received` — RX-Pfad |
| `core/qso_state.py:463-474` | Caller-Queue-Pfad |
| `core/qso_state.py:470` | `_is_worked_recently`-Block #3 (Caller-Queue) |
| `core/qso_state.py:477-491` | CQ-Reply-Block (Hauptpfad) |
| `core/qso_state.py:480-482` | `_is_worked_recently`-Block #1 |
| `core/qso_state.py:624-632` | `cancel()` — clearet _pending_reply |
| `ui/mw_qso.py:131-134` | `_on_cq_clicked` — encoder.tx_even |
| `ui/mw_qso.py:151-166` | `_on_cancel` (HALT) → cancel + stop_cq |
| `ui/mw_qso.py:168-209` | `_on_state_changed` (heavy GUI-update) |
| `ui/mw_qso.py:211-214` | `_on_tx_finished` → `on_message_sent` |
| `ui/mw_qso.py:425-435` | `_on_tx_slot_for_partner` |
| `ui/mw_cycle.py:28-72` | `_on_cycle_decoded` (heavy work) |
| `ui/mw_cycle.py:75-91` | `_on_cycle_finished` → `on_decoder_finished` |
| `ui/mw_cycle.py:520-615` | `_on_cycle_start` → `on_cycle_end` |
| `ui/mw_cycle.py:746-761` | `on_message_decoded` → `on_message_received` |
| `core/decoder.py:127-179` | `_decode_loop` |
| `core/decoder.py:251-273` | Signal-emit-Reihenfolge |
| `core/encoder.py:159-296` | `_tx_worker_inner` |
| `core/encoder.py:296` | `tx_finished.emit()` |
| `core/message.py:72-78` | `is_grid` (4-char strict) |
| `radio/flexradio.py:1010-1088` | `send_audio` (BLOCKING) |
| `tests/test_modules.py:372-410` | `test_qso_cq_flow` (NUR CQ_WAIT-Pfad) |

**V2 Ende. V3 = nochmal frische KI mit V2 Zeile fuer Zeile. Erst dann R1.**
