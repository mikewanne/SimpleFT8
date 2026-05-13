# CQ-Reply-Bug — Diagnose V3 (2026-05-05, finale Iteration vor R1)

**Status:** V3 = Self-Review-Round 2 ueber V2. V2 hatte: 3 Block-Stellen,
Caller-Queue, B2-Standardfall, „Manchmal"-Mechanik, Folgebug-Risiko,
GUI-Block-Punkte. V3 schaerft: Edge-Case-Klarstellungen, encoder.abort()-
Race, eindeutige Hauptwurzel-Aussage, praezisere R1-Auftraege.

V3 ist eigenstaendig (R1 braucht nur V3 + Code-Files).

---

## 1. Symptom (Field-Test 05:30-05:33 UTC, 2026-05-05)

FlexRadio (DA1MHH) im **CQ-Modus**, IC-7300 (DA1TST, EVEN) antwortet —
App **ignoriert die Antwort und sendet weiter CQ**.

```
05:27:30-05:28:15  QSO 1: DA1TST gearbeitet, RR73 + 73 → DA1TST in _worked_calls (Eintrag :28:00.x)

05:30:45 [O] → Sende CQ DA1MHH JO31
05:31:15 [O] → Sende CQ
05:31:30 [E] ← Empf. DA1MHH DA1TST JO31    ← IGNORIERT (Δ ≈ 224s vs. 300s Sperre)
05:31:45 [O] → Sende CQ                     (Soll: Report)
05:32:15 [O] → Sende CQ
05:32:30 [E] ← Empf. DA1MHH DA1TST JO31    ← IGNORIERT (Δ ≈ 270s)
05:32:45 [O] → Sende CQ
05:33:00 [E] ← Empf. DA1MHH DA1TST JO31    ← IGNORIERT (Δ ≈ 300s, strict `>`)
05:33:15 [O] → Sende CQ
```

**Mike's Aussage 2026-05-05:**
> „Manchmal klappt ein QSO, manchmal nicht. Tritt auch im echten Betrieb
> mit fremden Stationen auf. Es ist ein Bug, kein Feature."

> „Wenn eine bekannte Station uns ruft, hat das vlt sein Grund (kein 73
> erhalten). Wir haben bei Empfang einen Filter (Neue Stationen) — da
> werden bekannte ausgeblendet. Also rufen sehen wir nur unbekannte. Und
> wenn uns eine bekannte ruft, dann ueberlassen wir es dem Funker."

→ Mike's Position: Sperre = Overengineering. Filter im RX-Panel ist die
korrekte Stelle, nicht in der State-Machine.

---

## 2. Hauptwurzel — eindeutig identifiziert

**`_WORKED_BLOCK_SECS = 300` (5-Min-Sperre nach QSO) blockiert die
CQ-Reply-Verarbeitung an DREI Stellen:**

```
core/qso_state.py
  120:  self._WORKED_BLOCK_SECS = 300

  168-176:  def _is_worked_recently(self, callsign: str) -> bool:
              ts = self._worked_calls.get(callsign)
              if ts is None: return False
              if time.time() - ts > self._WORKED_BLOCK_SECS:   # strict `>`
                  del self._worked_calls[callsign]
                  return False
              return True

  441-443:  elif self.state == QSOState.TX_RR73:    # Eintrag-Stelle
              ...
              if self.qso.their_call:
                  self._worked_calls[self.qso.their_call] = time.time()

  Block #1 (480-482) — Hauptpfad on_message_received:
              if self._is_worked_recently(msg.caller):
                  print(f"[QSO] {msg.caller} ignoriert — kuerzlich gearbeitet ...")
                  return    # ← _pending_reply NICHT gesetzt

  Block #2 (191-193) — _process_cq_reply:
              if self._is_worked_recently(msg.caller):
                  print(f"[QSO] {msg.caller} ignoriert — kuerzlich gearbeitet (beendet ist beendet)")
                  return    # ← Reply abgebrochen

  Block #3 (470) — Caller-Queue-Eintrag (waehrend aktivem QSO):
              if (... and not self._is_worked_recently(msg.caller) ...):
                  self._caller_queue.append(msg)
              # → bekannte Station wird nicht in Warteliste aufgenommen
```

**Bei Fix muessen alle drei Stellen gleichzeitig adressiert werden** —
sonst halber Fix.

---

## 3. Code-Pfad-Trace — DA1TST-Test ms-genau

| UTC | Thread | Aktion | State |
|---|---|---|---|
| :31:14.2 | Encoder-Worker (CQ#2) | wake | CQ_CALLING |
| :31:14.7-:31:27.7 | Encoder-Worker | send_audio (BLOCKING, Pacing 5.33ms/Pkt) | CQ_CALLING |
| :31:27.7 | Encoder-Worker | ptt_off, **tx_finished emit** (Sender=Encoder) | CQ_CALLING |
| :31:27.7+ε | GUI | on_message_sent: CQ_CALLING + None → **CQ_WAIT, tc=0** | → CQ_WAIT |
| :31:30.0 | Timer | cycle_start emit (Sender=Timer) | — |
| :31:30.0+ε | GUI | on_cycle_end: CQ_WAIT, tc=1, cq_mode=True → **`_send_cq()`** → CQ_CALLING, **`_pending_reply=None`**, encoder.transmit("CQ ...") | → CQ_CALLING |
| :31:30.0+ε | Encoder-Worker (CQ#3) | startet, sleep bis :31:44.2 | CQ_CALLING |
| :31:43.5 | Decoder | wake (Slot+13.5), forks `_process_cycle` thread | CQ_CALLING |
| :31:44.5± | Decoder-Worker | decode fertig, emit cycle_decoded → message_decoded(DA1TST) → cycle_finished (Sender=Decoder, FIFO garantiert) | CQ_CALLING |
| :31:44.5+ε | GUI | on_message_decoded(DA1TST) → **on_message_received** | CQ_CALLING |
| | | qso_state.py:477-482 — state ✓, target ✓, is_grid ✓, **`_is_worked_recently("DA1TST")` → True** (Δ=224s) → **return** | _pending_reply bleibt None |
| :31:44.2 | Encoder-Worker | ptt_on, audio :31:44.7-:31:57.7 | CQ_CALLING |
| :31:45.0 | Timer | cycle_start → on_cycle_end: CQ_CALLING, kein match | CQ_CALLING |
| :31:57.7 | Encoder-Worker | tx_finished emit | CQ_CALLING |
| :31:57.7+ε | GUI | on_message_sent: CQ_CALLING + None → **CQ_WAIT** | → CQ_WAIT |
| :32:00.0 | Timer | on_cycle_end: CQ_WAIT, tc=1 → **`_send_cq()`** → CQ_CALLING, encoder.transmit | → CQ_CALLING |
| :32:14.7 | RF | **CQ raus statt Report** ← Bug-Beweis | |

**Loop wiederholt sich** — :32:30/:33:00-Slots geblockt, ab Δ > 300s
faellt die Sperre.

---

## 4. Hypothesen — bestaetigt / verworfen

### A — `_WORKED_BLOCK_SECS = 300` blockiert (BESTAETIGT, Hauptwurzel)

Code-Beweis: 3 Stellen oben.
Mike-Philosophie-Konflikt: Funker-Entscheidung > App-Block.

### A.1 — Caller-Queue-Pfad (BESTAETIGT, sekundaer)

`qso_state.py:121, 463-474, 470` — bekannte Station ruft uns waehrend
aktivem QSO → wird wegen `not _is_worked_recently` NICHT in Warteliste
aufgenommen → wird nach QSO-Ende nicht beantwortet.

### B — Race tx_finished vs message_decoded (NICHT die Wurzel)

V2-Korrektur bestaetigt: B2 (tx_finished VOR message_decoded) ist
**Standardfall**, weil:
- Encoder Audio endet bei Slot+12.7s (silence_pad ~0.7s + signal 13.5s
  trimmed → real ~13.4s, Audio-Ende ist boundary - 0.8 + ~13.4 =
  boundary + 12.6s, also Slot+12.6 ≈ Slot+12.7s)
- Decoder fertig bei Slot+13.5+~0.5-1.0s decode = Slot+14.0-14.5s
- → tx_finished ~1.5s VOR message_decoded.

In beiden Pfaden (B1: msg vor tx, B2: tx vor msg) wuerde — **wenn
Hypothese A nicht greifen wuerde** — der Reply korrekt verarbeitet:
- B1: state=CQ_CALLING → _pending_reply=msg, dann on_message_sent →
  _process_cq_reply → state=TX_REPORT
- B2: state=CQ_WAIT → _pending_reply=msg + direct _process_cq_reply →
  state=TX_REPORT

**Race ist also IRRELEVANT fuer den DA1TST-Bug** — Hypothese A
greift in beiden Reihenfolgen. R1 verifiziere.

### C — `_send_cq()` clearet _pending_reply (NICHT die Wurzel)

`qso_state.py:160-166, 297-299`. Edge-Case-Pruefung:

`_send_cq` wird in `on_cycle_end` (CQ_WAIT-Branch) gerufen. Wenn
state=CQ_WAIT mit pending=msg, kann _send_cq pending nullen.

**Kann das ohne Hypothese A passieren?**

Pfad-Versuch:
- :Slot-2 [TX] CQ#n laeuft (state=CQ_CALLING)
- :Slot-1 tx_finished → CQ_WAIT, tc=0
- :Slot-0 cycle_start → on_cycle_end: CQ_WAIT, tc=1, _send_cq → CQ_CALLING, pending=None
- :Slot-0 message_decoded (NACH cycle_start dispatched, weil decoder
  ~14.5s spaeter emit'd, also ~14.5s ueber dem tx_finished — aber
  cycle_start ist :Slot-0 mit nur ms-Latenz)
  
Hier wird Decoder fertig WAEHREND TX-Audio CQ#(n+1) laeuft, nicht im
Slot-START-Moment. Also ist der :Slot-0-cycle_start VOR message_decoded
in der Queue. **Kein C-Race.**

→ Edge-Case nur wenn message_decoded im seltenen Fall VOR cycle_start
des naechsten Slots liegt — physikalisch unwahrscheinlich (Decoder ist
~14.5s nach Slot-Start, naechstes cycle_start ist 15s nach Slot-Start →
0.5s Differenz).

**Verworfen fuer DA1TST-Test.** R1 verifiziere.

### D — `>= 1` zu aggressiv (verworfen)

`qso_state.py:298` `if self.qso.timeout_cycles >= 1`. Entspricht
WSJT-X-Standard (CQ jeden zweiten Slot). Nicht der Bug.

### E — Slot-Mismatch (verworfen)

CQ-Slot ODD und Reply-Slot ODD sind gleich (DA1TST EVEN → wir = not EVEN
= ODD). Kein Bug-Faktor.

### F — `is_grid` 4-char (verworfen)

`message.py:72-78`. JO31 = Letter+Letter+Digit+Digit ✓ → is_grid=True.

### G — Test-Coverage-Luecke (Auslöser-Faktor, kein Bug)

`tests/test_modules.py:372-410` testet nur den `CQ_WAIT`-Pfad ohne
worked_recently-Sperre. Kein Test-Case fuer:
- state=CQ_CALLING + worked_recently
- Caller-Queue-Block bei worked_recently
- Race-Pfad mit pending durch on_message_sent verarbeitet

### H — Auto-Hunt-Interferenz (verworfen fuer Field-Test)

`mw_cycle.py:487-512` — nur aktiv bei `_auto_hunt.active`. Im Field-Test
nicht relevant.

### I (NEU in V3) — encoder.abort()-Race (Edge-Case, kein Bug fuer aktuelles Symptom)

`mw_qso.py:252-254`:
```python
if self.encoder.is_transmitting:
    self.encoder.abort()
self.encoder.transmit(message)
```

`abort()` (encoder.py:72-81) setzt `_is_transmitting=False` +
`_abort_event.set()`. Aber wenn TX bereits in `send_audio` (BLOCKING,
packet-pacing) ist, stoppt abort send_audio NICHT — Audio laeuft bis
Ende.

`transmit()` (encoder.py:139-157) joint alten Thread mit timeout=0.5s.
Wenn alter Thread > 0.5s noch im send_audio: parallele TX-Threads.

**Wann passiert das?** _process_cq_reply triggert send_message →
_on_send_message → encoder.transmit. _process_cq_reply laeuft NUR von:
- `on_message_sent` (NACH tx_finished, also TX nicht mehr aktiv)
- `on_message_received` bei state=CQ_WAIT/IDLE (kein TX aktiv)
- `_resume_cq_if_needed` Caller-Queue-Pop (kein TX aktiv)

→ **encoder.abort()-Race kann nicht auftreten im CQ-Reply-Pfad.** R1
verifiziere durch grep `_process_cq_reply`-Aufrufer.

---

## 5. „Manchmal klappt manchmal nicht"-Mechanik

| Situation | Verhalten |
|---|---|
| Erste Station ruft (kein Eintrag in _worked_calls) | **klappt** |
| Selbe Station < 5 Min spaeter (RR73 evtl. nicht angekommen) | **klappt nicht** — gesperrt |
| Andere Station, erste war 5 Min vorher | **klappt** |
| Selbe Station > 5 Min spaeter | **klappt** — Sperre abgelaufen |

Mike's „im echten Betrieb mit fremden Stationen": DX-Pileups → schwacher
Pfad → unser RR73 kommt evtl. nicht an → Station wiederholt Grid →
Sperre blockt weil wir innerhalb 5 Min ein „QSO" (TX_RR73) gebucht haben.

---

## 6. Folgebug-Risiko nach Fix von Hypothese A

**Risiko 1: Doppel-ADIF-Eintrag**
- Station ruft 30s nach unserem RR73 erneut → wir antworten → zweites
  QSO gebucht → ADIF haette zwei Eintraege fuer denselben Call binnen
  Minuten.
- Mitigation: Funker-Entscheidung (Mike's Philosophie). Logbuch manuell
  bereinigbar. QRZ-Uploader filtert oft Duplikate.

**Risiko 2: Endlos-Schleife wenn Station nie 73 sendet**
- Wir RR73, Station kein RR73 erhalten → Grid → wir Report → ... endlos
- Real-Welt-Schutz: nach 2-3 Versuchen gibt der Funker auf, oder QSB
  beendet die Verbindung.
- WSJT-X hat aehnlichen Mechanismus nicht → nicht blockierend.

**Risiko 3: Stats-Bias**
- `_worked_calls` wird ausschliesslich in qso_state genutzt. Stats-
  Logger (`mw_cycle._log_stats`) benutzt es nicht.
- → kein Stats-Effekt. R1 verifiziere via grep `_worked_calls`.

---

## 7. Mike's Philosophie-Fit

CLAUDE.md „Projekt-Philosophie":
- Hobby-Funker-Tool, kein Contest
- Funker entscheidet, App nicht
- Einfache Bedienung > Vollstaendigkeit

→ 5-Min-Sperre `_WORKED_BLOCK_SECS = 300` ist genau die Art „App weiss
es besser"-Mechanik die Mike ablehnt.

Architektonisch korrekte Stelle fuer „bekannte Stationen ausblenden":
- RX-Panel-Filter „Neue Stationen" (existiert laut Mike)
- → blendet bekannte aus dem ANZEIGE-Pfad aus, nicht aus dem REPLY-Pfad.

---

## 8. Auftrag an R1 (DeepSeek-Reasoner)

R1 erhaelt: V3 + qso_state.py + mw_qso.py + mw_cycle.py + encoder.py
+ decoder.py + message.py + tests/test_modules.py.

**Konkrete Pruefauftraege:**

1. **Block-Stellen-Vollstaendigkeit:**
   `grep -n "_is_worked_recently" core/qso_state.py` — sind es exakt 3
   Aufruf-Stellen (Z. 191, 470, 480) plus die Definition (Z. 168)?
   Gibt es `_worked_calls`-Manipulationen die V3 uebersieht?

2. **Trace-Verifikation:**
   Stimmt der ms-Trace in Section 3 mit dem Code? Insbesondere:
   - `_send_cq()` wird wirklich nicht in CQ_CALLING-Branch von
     on_cycle_end (qso_state.py:273-318) aufgerufen?
   - on_message_sent (Z. 388-396) verarbeitet pending vor CQ_WAIT-Switch?
   - Decoder.cycle_decoded wird VOR message_decoded emit'd (decoder.py:
     257-273)?

3. **Race-Realismus B2:**
   Ist die zeitliche Aussage „tx_finished ~1.5s VOR message_decoded"
   korrekt? Verifiziere via:
   - encoder.py:209-210 Trim 1.5s (FT8)
   - encoder.py:237-256 Drift-Guard, silence_secs Berechnung
   - decoder.py:138-150 _WAKE_OFFSETS und _decode_loop sleep

4. **Folgebug-Risiko (Section 6):**
   - Verifiziere dass `_worked_calls` nur in qso_state.py genutzt wird
     (`grep -rn "_worked_calls" .` ueber gesamtes Repo).
   - Gibt es einen technischen Pfad-Schutz vs. Endlos-Schleife den V3
     uebersieht (z.B. ADIF-Duplikat-Check, Logbuch-Skip)?

5. **Mike's Philosophie-Fit:**
   - Existiert „Neue Stationen"-Filter in `ui/rx_panel.py` oder
     `ui/control_panel.py`? Wie heisst er, was filtert er?
   - Ist die Aussage „blendet bekannte aus dem Anzeige-Pfad aus, nicht
     aus dem Reply-Pfad" technisch tragfaehig?

6. **Test-Cases:**
   Welche minimalen pytest-Funktionen wuerden den Bug exposen? V3
   schlaegt vor (nicht Loesung, nur Test-Coverage):
   - `test_cq_reply_blocked_by_worked_recently` — _worked_calls gesetzt,
     state=CQ_CALLING + msg empfangen → erwartet: _pending_reply=None
   - `test_cq_reply_during_tx_to_pending_then_processed` — state=
     CQ_CALLING + msg → _pending_reply=msg, dann on_message_sent →
     state=TX_REPORT
   - `test_caller_queue_blocks_known_station` — state=TX_REPORT, msg
     von gesperrter Station → nicht in Warteliste

7. **Hauptwurzel-Bestaetigung:**
   Ist Hypothese A wirklich die EINZIGE Wurzel fuer Mike's Symptom?
   Oder gibt es einen zweiten Pfad fuer „fremde Stationen" der
   unabhaengig vom 300s-Timer einen CQ-Reply ignorieren kann?

8. **Zusatzfrage:** in `_resume_cq_if_needed` (qso_state.py:368-385)
   wird Caller-Queue gepoppt und _pending_reply gesetzt + 
   _process_cq_reply gerufen. Block #2 (Z. 191-193) greift dann.
   Ist Caller-Queue-Pop also DOPPELT durch Block #3 (Caller-Queue-Add)
   und Block #2 (_process_cq_reply) gegen worked_recently abgesichert?
   Falls ja: redundant aber konsistent. Falls nein: Edge-Case.

**Antworten bitte mit:**
- bestaetigt / widerlegt pro Pruefauftrag
- konkrete Datei:Zeile-Referenzen fuer neue Befunde / Halluzinations-
  Korrekturen
- KEINE Loesung, kein Code-Diff. Reine Analyse-Ergaenzung.

---

## 9. Anhang — Code-Stellen Quick-Reference

| Datei:Zeile | Funktion / Variable |
|---|---|
| `core/qso_state.py:120` | `_WORKED_BLOCK_SECS = 300` |
| `core/qso_state.py:121` | `_caller_queue: list = []` |
| `core/qso_state.py:154-158` | `stop_cq()` |
| `core/qso_state.py:160-166` | `_send_cq()` — clearet _pending_reply |
| `core/qso_state.py:168-176` | `_is_worked_recently()` (strict `>`) |
| `core/qso_state.py:178-238` | `_process_cq_reply()` |
| `core/qso_state.py:191-193` | **Block #2** |
| `core/qso_state.py:213-215` | tx_slot_for_partner.emit |
| `core/qso_state.py:273-318` | `on_cycle_end` |
| `core/qso_state.py:298-299` | `>= 1` CQ_WAIT-Trigger |
| `core/qso_state.py:320-366` | `on_decoder_finished` |
| `core/qso_state.py:368-385` | `_resume_cq_if_needed` |
| `core/qso_state.py:388-446` | `on_message_sent` |
| `core/qso_state.py:441-443` | `_worked_calls[their_call] = time.time()` |
| `core/qso_state.py:450-491` | `on_message_received` |
| `core/qso_state.py:463-474` | Caller-Queue-Pfad |
| `core/qso_state.py:470` | **Block #3** (Caller-Queue) |
| `core/qso_state.py:477-491` | CQ-Reply-Hauptpfad |
| `core/qso_state.py:480-482` | **Block #1** (Hauptpfad) |
| `core/qso_state.py:488-489` | direct _process_cq_reply (CQ_WAIT/IDLE) |
| `core/qso_state.py:624-632` | `cancel()` (HALT) |
| `ui/mw_qso.py:131-134` | `_on_cq_clicked` — encoder.tx_even |
| `ui/mw_qso.py:151-166` | `_on_cancel` (HALT) |
| `ui/mw_qso.py:168-209` | `_on_state_changed` (heavy) |
| `ui/mw_qso.py:211-214` | `_on_tx_finished` |
| `ui/mw_qso.py:217-254` | `_on_send_message` (encoder.abort + transmit) |
| `ui/mw_qso.py:425-435` | `_on_tx_slot_for_partner` |
| `ui/mw_cycle.py:28-72` | `_on_cycle_decoded` |
| `ui/mw_cycle.py:75-91` | `_on_cycle_finished` |
| `ui/mw_cycle.py:520-615` | `_on_cycle_start` |
| `ui/mw_cycle.py:746-761` | `on_message_decoded` |
| `core/decoder.py:127-179` | `_decode_loop` |
| `core/decoder.py:251-273` | Signal-Reihenfolge |
| `core/encoder.py:72-81` | `abort()` |
| `core/encoder.py:139-157` | `transmit()` (join, _is_transmitting check) |
| `core/encoder.py:159-296` | `_tx_worker_inner` |
| `core/encoder.py:296` | `tx_finished.emit()` |
| `core/message.py:72-78` | `is_grid` |
| `radio/flexradio.py:1010-1088` | `send_audio` (BLOCKING) |
| `tests/test_modules.py:372-410` | `test_qso_cq_flow` (CQ_WAIT-Pfad nur) |

**V3 Ende. R1-Pruefung mit Code-Files folgt.**
