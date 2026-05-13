# CQ-Reply-Bug — Diagnose V1 (2026-05-05)

**Status:** V1 = Analyse-Prompt fuer V2 / R1. KEINE Loesung — nur Symptom-
Trace, Code-Pfade, Hypothesen mit Datei:Zeile-Evidenz. R1 soll pruefen ob
die Analyse vollstaendig ist und welche Hypothese die Haupt-Wurzel ist.

---

## 1. Symptom (Field-Test 05:30-05:33 UTC, 2026-05-05)

FlexRadio (DA1MHH, eigene App) im **CQ-Modus**. Icom IC-7300 (DA1TST,
manuell auf EVEN gestellt) antwortet auf den CQ. Die App **ignoriert die
Antwort und sendet weiter CQ** statt Report.

```
05:30:45 [O] → Sende CQ DA1MHH JO31      (wir, ODD-Slot)
05:31:15 [O] → Sende CQ DA1MHH JO31      (wir, ODD-Slot)
05:31:30 [E] ← Empf. DA1MHH DA1TST JO31  (DA1TST antwortet, EVEN-Slot)  ← IGNORIERT
05:31:45 [O] → Sende CQ DA1MHH JO31      (Sollte Report sein!)
05:32:15 [O] → Sende CQ                  (immer noch CQ)
05:32:30 [E] ← Empf. DA1MHH DA1TST JO31  ← IGNORIERT
05:32:45 [O] → Sende CQ
05:33:00 [E] ← Empf. DA1MHH DA1TST JO31  ← IGNORIERT
05:33:15 [O] → Sende CQ
```

**Erwartet:** im :31:45-Slot (oder spaetestens :32:15) sollte der Report
`DA1TST DA1MHH +XX` raus. Stattdessen: weiter CQ.

**Wichtig — Mike's Aussage (2026-05-05):**
> „Das ist seit langem ein Problem. Manchmal klappt ein QSO, manchmal nicht.
> Tritt auch im echten Betrieb mit fremden Stationen auf. Es ist ein Bug,
> kein Feature."

→ Bug muss systemisch sein, nicht nur DA1TST-spezifisch.

**Vorhergehende QSO-Sequenz** (Kontext fuer _worked_calls-Eintrag):
```
05:27:30 [E] → Sende DA1TST DA1MHH -21
05:27:45 [O] ← Empf. DA1MHH DA1TST R+18
05:28:00 [E] → Sende DA1TST DA1MHH RR73   ← TX_RR73 → DA1TST in _worked_calls
05:28:15 [O] ← Empf. DA1MHH DA1TST 73
```

→ DA1TST ist seit `:28:00` in `_worked_calls` registriert (5-Min-Sperre
laeuft bis `:33:00` UTC).

---

## 2. System-Setup

- FlexRadio = DA1MHH = unsere App (CQ-Caller, ANT1)
- IC-7300 = DA1TST = Gegenstation (manuell, EVEN-Slot)
- Beide auf 40m FT8
- ANT2 = nur RX (NIE TX, Hardware-Schaden)

---

## 3. Architektur-Uebersicht (3 Threads + Qt-Queue)

Drei nebenlaeufige Threads emittieren Qt-Signals an den GUI-Thread:

| Thread | Wake-Zeit | Emittiert | Sender |
|---|---|---|---|
| Decoder (`core/decoder.py:127-179`) | Slot+13.5s (FT8) | `cycle_decoded`, `message_decoded`, `cycle_finished` | Decoder-Instanz |
| Encoder-TX-Worker (`core/encoder.py:159-296`) | Boundary-0.8s | `tx_started`, `tx_finished` | Encoder-Instanz |
| Timer (`ui/mw_cycle.py:520-615`) | Slot-START (boundary) | `cycle_start` → `on_cycle_end` | Timer |

**Qt-Signal-Reihenfolge-Garantien:**
- Pro Sender: FIFO. cycle_decoded → message_decoded → cycle_finished sind
  garantiert in dieser Reihenfolge (alle vom Decoder).
- **Zwischen verschiedenen Sendern: KEINE Reihenfolgegarantie.**
  → message_decoded (Decoder) und tx_finished (Encoder) koennen in
  beliebiger Reihenfolge im GUI-Event-Loop dispatched werden.

**Signal-Verbindungen** (relevante Slots):
- `Decoder.message_decoded` → `mw_cycle.on_message_decoded` →
  `qso_sm.on_message_received(msg)`
- `Decoder.cycle_finished` → `mw_cycle._on_cycle_finished` →
  `qso_sm.on_decoder_finished()`
- `Encoder.tx_finished` → `mw_qso._on_tx_finished` →
  `qso_sm.on_message_sent()`
- `Timer.cycle_start` → `mw_cycle._on_cycle_start` →
  `qso_sm.on_cycle_end()` (lauft am Slot-START)

---

## 4. Code-Pfad-Trace — Field-Test :31:14 bis :32:15 (ms-genau)

| UTC | Thread | Aktion | State (Soll) |
|---|---|---|---|
| :31:14.2 | Encoder-Worker (alt) | wake, ptt_on, audio start fuer :31:15-CQ | CQ_CALLING |
| :31:27.7 | Encoder-Worker (alt) | send_audio fertig (blocking, packet-pacing), ptt_off, **tx_finished emit** | CQ_CALLING |
| :31:27.7+ | GUI-Thread | Qt-Queue → `_on_tx_finished` → `qso_sm.on_message_sent()` | CQ_CALLING → **CQ_WAIT** (kein _pending_reply) |
| :31:30.0 | Timer | `cycle_start` → `_on_cycle_start` → `qso_sm.on_cycle_end()` | CQ_WAIT, tc=0 → tc+=1=1, `cq_mode=True` → **`_send_cq()`** → CQ_CALLING, **`_pending_reply=None`**, encoder.transmit("CQ ...") |
| :31:30.0 | Encoder-Worker (neu) | startet, sleep bis next-boundary-0.8 = :31:44.2 | CQ_CALLING |
| :31:43.5 | Decoder | wake (Slot+13.5), `_process_cycle` Thread startet | CQ_CALLING |
| :31:44.5± | Decoder-Process | decode fertig (~1s), emit `cycle_decoded(msgs)` → `message_decoded(DA1TST)` → `cycle_finished` | CQ_CALLING |
| :31:44.5+ | GUI-Thread | message_decoded dispatched → `on_message_received(DA1TST)` | CQ_CALLING |
| | | `state in (IDLE, CQ_WAIT, CQ_CALLING)` ✓, `msg.target == my_call` ✓, `msg.is_grid` ✓ | |
| | | **CHECK** `_is_worked_recently("DA1TST")`: ts=:28:00, now=:31:44, delta=224s < 300s → **return True** | CQ_CALLING |
| | | → `return` BEVOR `_pending_reply = msg` (qso_state.py:480-482) | **`_pending_reply` bleibt None** |
| :31:44.2 | Encoder-Worker | wake, ptt_on, audio :31:44.7 - :31:57.7 | CQ_CALLING |
| :31:57.7 | Encoder-Worker | tx_finished emit | CQ_CALLING |
| :31:57.7+ | GUI-Thread | `on_message_sent()`: state=CQ_CALLING, `_pending_reply=None` → **CQ_WAIT**, tc=0 | CQ_CALLING → CQ_WAIT |
| :32:00.0 | Timer | `on_cycle_end`: CQ_WAIT, tc=1, → **`_send_cq()`** → CQ_CALLING, encoder.transmit("CQ ...") | CQ_CALLING |
| :32:14.2 | Encoder-Worker | wake fuer :32:15-CQ |  |
| :32:14.7 | RF | **CQ raus statt Report** ← Bug-Beweis | |

**→ Field-Test-Symptom 100% reproduziert durch `_is_worked_recently`-Check
in `qso_state.py:480-482`.**

---

## 5. Hypothesen-Liste (mit Code-Evidenz)

### Hypothese A — `_WORKED_BLOCK_SECS = 300` blockiert CQ-Reply (HAUPT-WURZEL fuer DA1TST-Test)

**Code-Evidenz:**
- `core/qso_state.py:120` — `self._WORKED_BLOCK_SECS = 300`  (5 Min)
- `core/qso_state.py:168-176` — `_is_worked_recently(callsign)`:
  ```python
  ts = self._worked_calls.get(callsign)
  if ts is None: return False
  if time.time() - ts > self._WORKED_BLOCK_SECS:
      del self._worked_calls[callsign]
      return False
  return True
  ```
- `core/qso_state.py:441-443` — Eintrag in TX_RR73-Branch von `on_message_sent`:
  ```python
  elif self.state == QSOState.TX_RR73:
      self.qso_complete.emit(self.qso)
      self.cq_qso_count += 1
      if self.qso.their_call:
          self._worked_calls[self.qso.their_call] = time.time()
  ```
- `core/qso_state.py:477-482` — Block-Pfad in `on_message_received`:
  ```python
  if self.state in (QSOState.IDLE, QSOState.CQ_WAIT, QSOState.CQ_CALLING) and msg.target == self.my_call:
      if msg.is_grid or msg.is_report:
          if self._is_worked_recently(msg.caller):
              print(f"[QSO] {msg.caller} ignoriert — kuerzlich gearbeitet ...")
              return                          # ← _pending_reply NICHT gesetzt
          self._pending_reply = msg
          ...
  ```
- Zweiter Block-Pfad in `_process_cq_reply` (qso_state.py:191-193):
  Falls _pending_reply doch durchrutscht (Warteliste-Pfad), wird beim
  Verarbeiten nochmal blockiert.

**Effekt:** Stationen mit denen wir innerhalb der letzten 5 Min ein QSO
abgeschlossen haben (TX_RR73), koennen uns nicht erneut anrufen — die
App ignoriert sie still.

**Mike's Position (2026-05-05):**
> „Wenn eine bekannte Station uns ruft, hat das vlt sein Grund (kein 73
> erhalten). Wir haben bei Empfang einen Filter (Neue Stationen) — da
> werden bekannte ausgeblendet. Also rufen sehen wir nur unbekannte. Und
> wenn uns eine bekannte ruft, dann ueberlassen wir es dem Funker ob er
> antworten moechte oder nicht."

→ Sperre ist **Overengineering** und widerspricht Mike's Hobby-Funker-
Philosophie (CLAUDE.md „Projekt-Philosophie"). Filter „Neue Stationen"
im RX-Panel ist die korrekte Stelle, nicht die State-Machine.

### Hypothese B — Race tx_finished vs message_decoded (verschiedene Qt-Sender)

Decoder emittet `message_decoded`, Encoder emittet `tx_finished`. Qt
garantiert FIFO **nur pro Sender** — zwischen verschiedenen Sendern keine
Reihenfolge.

**Pfad B1 (message_decoded VOR tx_finished, normalerweise so):**
- Decoder wakes :31:43.5, emit message_decoded ~ :31:44.5
- Encoder TX endet :31:57.7, emit tx_finished
- GUI dispatched message_decoded zuerst (Decoder ist 13s frueher fertig)
- on_message_received: state=CQ_CALLING → _pending_reply=msg
- Spaeter on_message_sent: state=CQ_CALLING + _pending_reply=msg →
  _process_cq_reply → state=TX_REPORT, send_message.emit(report)

**Pfad B2 (tx_finished VOR message_decoded, theoretisch moeglich):**
- on_message_sent: state=CQ_CALLING + _pending_reply=None → CQ_WAIT, tc=0
- on_message_received: state=CQ_WAIT → _pending_reply=msg + direct
  _process_cq_reply (Z. 488-489)
- → state=TX_REPORT, send_message.emit(report)

**Beide Pfade enden in TX_REPORT** — vorausgesetzt _is_worked_recently
nicht greift und msg.is_grid stimmt. → Race ist **nicht die Wurzel**,
solange die anderen Pre-Conds passen.

**Aber:** wenn der GUI-Thread blockiert ist (z.B. lange UI-Updates,
dx_tune_dialog.feed_cycle, ap_lite.try_rescue, station_accumulator-
Tabelle redraw, Locator-DB-Hooks in mw_cycle.py:249-309) koennten
Signal-Dispatches verzoegert werden.

**R1 pruefe:** Gibt es einen Pfad in dem `_send_cq()` (qso_state.py:160-
166, clearet `_pending_reply = None`) ZWISCHEN dem `_pending_reply=msg`
in `on_message_received` und der Verarbeitung in `on_message_sent` /
direct `_process_cq_reply` gerufen wird?

### Hypothese C — `_send_cq()` cleared `_pending_reply` (qso_state.py:162)

**Code-Evidenz:**
- `core/qso_state.py:160-166`:
  ```python
  def _send_cq(self):
      self._pending_reply = None  # Alte Antwort verwerfen
      msg = f"CQ {self.my_call} {self.my_grid}"
      ...
      self._set_state(QSOState.CQ_CALLING)
      self.send_message.emit(msg)
  ```
- Aufrufer von `_send_cq`:
  1. `start_cq()` (Z. 152) — User-Click
  2. `on_cycle_end` (Z. 297-299) — CQ_WAIT-Branch nach 1 RX-Zyklus
  3. `_resume_cq_if_needed` (Z. 380-382) — nach Timeout / Hunt

**Edge-Case:** Wenn ein neuer Slot beginnt waehrend `_pending_reply`
gesetzt ist und state=CQ_WAIT (Race B2 erfuellt), laeuft `on_cycle_end`
am Slot-START → tc+=1 → `_send_cq()` → `_pending_reply=None`. Dann
process_cq_reply wuerde zu spaet kommen und kein pending finden.

**Zeitliche Voraussetzung:** Slot-START Timer-Signal (~Boundary 0±20ms)
muss VOR dem direct `_process_cq_reply()` aus `on_message_received`
laufen. Beide laufen im GUI-Thread, also seriell — die Reihenfolge im
Qt-Event-Loop entscheidet.

**Trace fuer fremde Station, NICHT in _worked_calls, Race B2 + C:**
- :31:43.5 Decoder wakes
- :31:44.5 message_decoded emit (Decoder-Sender)
- :31:57.7 tx_finished emit (Encoder-Sender)
- GUI Pfad-B2 angenommen: tx_finished VOR message_decoded:
  - `on_message_sent`: CQ_CALLING + _pending_reply=None → CQ_WAIT, tc=0
- :32:00.0 Timer → `cycle_start` → `_on_cycle_start` → `on_cycle_end`:
  CQ_WAIT, tc+=1=1, `_send_cq()` → CQ_CALLING, _pending_reply=None,
  encoder.transmit(CQ)
- danach erst dispatched message_decoded:
  on_message_received: state=CQ_CALLING → _pending_reply=msg
- :32:13.7+ Encoder-Worker fuer :32:15-CQ schon scheduled, sendet CQ
- :32:14 etc. tx_finished → on_message_sent → CQ_CALLING + pending=msg
  → _process_cq_reply → state=TX_REPORT, send_message.emit(report)
- → Report rauscht im :32:30-Slot? Aber :32:30 ist EVEN, wir wollen ODD
  → encoder waehlt :32:45 [O]

Aber Field-Test zeigt :32:45 [O] = CQ. → entweder Race B2 trifft nicht
zu, oder es gibt einen weiteren Pfad.

**R1 pruefe:** ist die zeitliche Reihenfolge (tx_finished vor Slot-Start-
Timer) realistisch? Qt's Event-Loop dispatched in welcher Reihenfolge
wenn beide Signale waehrend des aktuellen Slot-Endes aufgelaufen sind?

### Hypothese D — `on_cycle_end` (Slot-START) re-triggert `_send_cq()` zu aggressiv

**Code-Evidenz:**
- `core/qso_state.py:293-300`:
  ```python
  if self.state == QSOState.CQ_WAIT:
      self.qso.timeout_cycles += 1
      if self.qso.timeout_cycles >= 1 and self.cq_mode:
          self._send_cq()
      return
  ```

**Beobachtung:** `>= 1` heisst: SOFORT im naechsten Slot nach CQ_WAIT-
Eintritt wird ein neuer CQ rausgejagt. Es gibt **kein "warte erst auf
Antwort, bevor du wieder CQ rufst"-Window**.

Das ist im Test-Setup (DA1TST sendet :30, antwortet :31:30) eng. Wenn
CQ-Slot-Anchor :15/:45 ist und DA1TST EVEN auf :30 sendet, schliesst
`on_cycle_end` :30 die CQ_WAIT-Periode bereits → :45 schon wieder CQ.

**Effekt fuer Race-Pfad B2 + C:** der :32:00 Slot-Start-Timer reisst die
state auf CQ_CALLING und nullt _pending_reply VOR dem message_decoded-
Dispatch.

**Frage an R1:** ist `>= 1` zu aggressiv? Sollte `>= 2` (= mindestens 1
voller RX-Zyklus zum Lauschen) sein? Aber dann waeren CQ-Calls nur alle
30s = nicht gut fuer FT8.

### Hypothese E — Slot-Mismatch durch encoder.tx_even

**Code-Evidenz:**
- `core/encoder.py:181-196` — `_next_slot_boundary()` mit `tx_even`-Logik
- `ui/mw_qso.py:131-134` — `_on_cq_clicked`: `self.encoder.tx_even = not
  self.timer.is_even_cycle()` setzt CQ-Slot fest
- `ui/mw_qso.py:425-435` — `_on_tx_slot_for_partner`: `encoder.tx_even =
  not their_even` setzt Reply-Slot

Im Field-Test: wir auf ODD (`encoder.tx_even = False`), DA1TST auf EVEN.
Beim Reply-Pfad muesste `_on_tx_slot_for_partner` `encoder.tx_even` auf
False setzen (gegenteilig zu DA1TST EVEN = True). DAS IST DER
GLEICHE WERT wie der CQ-Slot!

→ **Slot-Aenderung ist kein Bug-Faktor** in diesem konkreten Test (CQ und
Reply beide ODD). In anderen Konstellationen (DA1TST auf ODD → wir EVEN
fuer Reply) waere es relevant — Mike's spaeterer Test mit Icom auf ODD
zeigte aber das Symptom auch dort.

### Hypothese F — `is_grid` Strict-Format zu eng

**Code-Evidenz:**
- `core/message.py:72-78`:
  ```python
  @property
  def is_grid(self) -> bool:
      g = self.field3
      if len(g) != 4:
          return False
      return (g[0].isalpha() and g[1].isalpha() and
              g[2].isdigit() and g[3].isdigit())
  ```

Akzeptiert NUR 4-char Locators mit Format Letter+Letter+Digit+Digit.
**6-char Locators (`JO31QQ`) werden NICHT als Grid erkannt** — wenn ein
Operator JO31QQ sendet (FT8 unterstuetzt das technisch), is_grid=False
→ on_message_received Z. 478 schlaegt fehl (`is_grid or is_report`) →
kein _pending_reply.

**Wahrscheinlichkeit:** gering — FT8 packt Locator-Calls meist als
4-char (Standard-Protokoll). Aber Edge-Case bei manchen Stationen.

### Hypothese G — Test-Coverage-Luecke (kein Bug, aber Auslöser)

`tests/test_modules.py:372-410` (`test_qso_cq_flow`) testet nur den
Pfad **CQ_WAIT → message_decoded** (TX-Ende kommt zuerst). Der Pfad
**CQ_CALLING → message_decoded waehrend TX laeuft → on_message_sent
verarbeitet pending** ist NICHT getestet. Auch der `_is_worked_recently`-
Block bei aktiver CQ-Sperre ist nicht abgedeckt.

→ Der Bug konnte sich seit Wochen halten weil keine Test-Reproduktion
existierte.

---

## 6. Mike's Funker-Philosophie (CLAUDE.md „Projekt-Philosophie")

> SimpleFT8 ist ein Hobby-Funker-Tool. Einfache Bedienung > Vollstaendigkeit.
> Lieber 3 gut funktionierende Features als 30 die Mike erst lernen muss.
> UX-Prinzip: Funker entscheidet, App nicht.

→ Die 5-Min-Sperre `_WORKED_BLOCK_SECS = 300` ist genau die Art von
„App-weiss-es-besser"-Mechanik die Mike ablehnt.

**Architektonisch korrekte Stelle fuer „bekannte Stationen ausblenden":**
- RX-Panel-Filter „Neue Stationen" (existiert bereits laut Mike)
- → blendet bekannte aus dem **Anzeige**-Pfad aus, NICHT aus dem
  **Reply**-Pfad
- Wenn eine bekannte Station es trotzdem in den Reply-Pfad schafft (sie
  ruft uns explizit an), hat sie meist einen Grund:
  1. Unser RR73 nicht angekommen (CRC-Fail, QSB) → wiederholt Grid
  2. 73 wurde bei uns nicht korrekt verarbeitet → Station haengt im QSO
  3. Operator-Wahl (manuelle CQ-Antwort)

→ **Funker-Entscheidung**, nicht App-Block.

---

## 7. Was V1 NICHT macht

- Keine Loesung. Keine Implementierungs-Vorschlaege.
- Keine Codeaenderung. Reine Diagnose + Hypothesen.
- Keine Empfehlung welche Hypothese zu fixen ist — V3/Mike entscheiden.

---

## 8. Auftrag an V2 / R1 (frische KI)

Bitte pruefen:

1. **Hypothesen-Vollstaendigkeit:** Habe ich Pfade uebersehen?
   - Insbesondere: gibt es einen Pfad in dem `_pending_reply` gesetzt
     wird, dann aber durch `_send_cq()` oder `cancel()` oder
     `stop_cq()` geloescht wird BEVOR `_process_cq_reply()` zugreift?
   - Gibt es Pfade durch `_caller_queue` (Warteliste, qso_state.py:121,
     465-474, 374-380) die das Symptom erzeugen koennten?
   - Gibt es Auto-Hunt-Pfade (`ui/mw_cycle.py:487-512`) die parallel
     interferieren?

2. **Code-Evidenz-Verifikation:** Stimmen die Datei:Zeile-Referenzen?
   Greppe die Behauptungen gegen den aktuellen Code-Stand (post-v0.95.1,
   commit `04388ef`).

3. **Race-Realismus:** Wie wahrscheinlich ist Pfad B2 (tx_finished VOR
   message_decoded)? Decoder ist ~13s frueher fertig als Encoder.
   Worst-Case-Szenarien?

4. **Haupt-Wurzel-Identifikation:** Welche Hypothese ist
   - definitiv aktiv (DA1TST-Test): A
   - moeglich fuer „fremde Stationen" (Mike's Aussage): B/C/D/F
   - architektonisch falsch (Mike's Philosophie): A

5. **Stats-Risiko / Folgewirkungen:** Wenn Hypothese A entfernt wird
   (`_WORKED_BLOCK_SECS = 0` oder Mechanik raus), gibt es Test-
   Brueche oder Folgebugs (z.B. Endlos-Schleife wenn Station nach
   eigenem RR73 sofort wieder mit Grid ruft)?

6. **Mike's Philosophie-Fit:** stimmt die architektonische Bewertung
   (Filter im RX-Panel ist die richtige Stelle, State-Machine soll
   nicht filtern)?

Antworten bitte mit:
- bestaetigt / widerlegt pro Hypothese
- konkreten Datei:Zeile-Referenzen fuer neue Befunde
- KEINE Loesung — nur Analyse-Ergaenzung. Loesung kommt nach V3 in
  separatem Plan-Workflow.

---

## 9. Anhang — relevante Code-Stellen (Quick-Reference)

| Datei:Zeile | Funktion / Variable |
|---|---|
| `core/qso_state.py:120` | `_WORKED_BLOCK_SECS = 300` |
| `core/qso_state.py:160-166` | `_send_cq()` — clearet `_pending_reply=None` |
| `core/qso_state.py:168-176` | `_is_worked_recently()` |
| `core/qso_state.py:178-238` | `_process_cq_reply()` |
| `core/qso_state.py:273-318` | `on_cycle_end` — Slot-START-Pfad |
| `core/qso_state.py:320-366` | `on_decoder_finished` — Slot-ENDE-Pfad |
| `core/qso_state.py:388-446` | `on_message_sent` — TX-Ende-Pfad |
| `core/qso_state.py:441-443` | `_worked_calls[their_call] = time.time()` |
| `core/qso_state.py:450-491` | `on_message_received` — RX-Pfad |
| `core/qso_state.py:477-491` | CQ-Reply-Block (Hauptpfad) |
| `ui/mw_qso.py:131-134` | `_on_cq_clicked` setzt `encoder.tx_even` |
| `ui/mw_qso.py:211-214` | `_on_tx_finished` → `qso_sm.on_message_sent` |
| `ui/mw_qso.py:425-435` | `_on_tx_slot_for_partner` |
| `ui/mw_cycle.py:75-91` | `_on_cycle_finished` → `on_decoder_finished` |
| `ui/mw_cycle.py:520-615` | `_on_cycle_start` → `on_cycle_end` |
| `ui/mw_cycle.py:746-761` | `on_message_decoded` → `on_message_received` |
| `core/decoder.py:127-179` | `_decode_loop` (Decoder-Thread) |
| `core/decoder.py:251-273` | Signal-Reihenfolge cycle_decoded → message_decoded → cycle_finished |
| `core/encoder.py:159-296` | `_tx_worker_inner` (Encoder-Thread) |
| `core/encoder.py:296` | `tx_finished.emit()` (nach send_audio + ptt_off) |
| `core/message.py:72-78` | `is_grid` (4-char Letter+Letter+Digit+Digit) |
| `radio/flexradio.py:1010-1088` | `send_audio` (BLOCKING, packet-pacing) |
| `tests/test_modules.py:372-410` | `test_qso_cq_flow` (NUR CQ_WAIT-Pfad) |

---

**V1 Ende. V2 = frische-KI Self-Review (eigene Iteration). V3 = nochmal
frische KI. Erst dann R1-Pruefung mit allen Code-Files.**
