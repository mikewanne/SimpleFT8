# Fix D — `on_cycle_end()` Slot-Timing-Korrektur (Doppel-Report-Bug)

**Status:** V1 (Erstentwurf von Claude, vor Self-Review).
**Datum:** 2026-04-30.
**Vorgaenger:** v0.80 (commit `c190df7`) — TX-DT-Drift-Fix (A1+A2+A3+B+C+Race-Fix).
**Folge-Bug:** im Feldtest 30.04. nach v0.80-Release entdeckt.

---

## 0. Kontext und Vorgeschichte

v0.80 hat den **TX-DT-Drift im QSO-Retry-Fall** behoben. Vorher feuerte
der Retry-Trigger AM Mike-TX-Slot-Start (Encoder hatte 0s Vorlauf →
Drift-Guard zwang sofortiges Senden mit DT 0.6-0.8s am Empfaenger →
ueber WSJT-X-Decode-Schwelle 0.5s → 7 Real-QSOs gescheitert).

Fix A1 (commit `9101573`): Retry-Trigger feuert jetzt im **RX-Slot der
Gegenstation** (`timeout_cycles == 1` statt `== 2`) → Encoder hat
14s Vorlauf → DT konvergiert auf 0.0-0.1s ✓ (Icom-verifiziert 30.04.).

**ABER:** mit Fix A1 wurde ein **zweiter, latenter Bug** sichtbar:
`qso_sm.on_cycle_end()` laeuft in `mw_cycle.py:501` innerhalb von
`_on_cycle_start` (= **Slot-START**, Timer-Thread). Das heisst:
**zum Zeitpunkt des Retry-Triggers ist der RX-Slot noch nicht
dekodiert** — Decoder gibt erst bei T+13.5s im Slot Bescheid.

**Folge:** Mike triggert Retry BEVOR die Antwort der Gegenstation
gesehen wurde. Wenn die Antwort doch kommt (R+18 dekodiert kurz
spaeter), wird zwar `encoder.abort()` + neuer `transmit("...RR73")`
aufgerufen — aber der falsche Retry sitzt schon in der Encoder-Queue
mit `silence_secs ~ 14s`, abort kommt zu spaet, oder der neue
TX-Auftrag wird vom Drift-Guard verworfen.

**Symptom im Icom-Empfangs-Log (30.04. ~08:32-33):**

```
08:32:45 [O] Mike → "DA1TST DA1MHH -21"        (initial-call, korrekt)
08:33:00 [E] DA1TST → R+18                      (decoded ~T+29.5s)
08:33:15 [O] Mike → "DA1TST DA1MHH -21"        (DOPPEL-Report — BUG!)
08:33:30 [E] DA1TST → R+18                      (Wiederholung)
08:33:45 [O] Mike → "DA1TST DA1MHH RR73"       (endlich korrekt)
```

Mike haette nach Slot 33:00 mit RR73 antworten muessen, schickte aber
nochmal -21. Korrektes QSO-Pacing ist 4 Slots, hier waren es 6 Slots.

---

## 1. Root-Cause-Analyse

### 1.1 Aktuelle Reihenfolge im FT8-Slot

```
T_n+0       Slot N+1 startet
            └─ ui/mw_cycle.py:_on_cycle_start (Timer-Thread, gequeued zu GUI):
               ├─ Z.501: qso_sm.on_cycle_end()   ← BUG: hier laeuft Retry-Trigger
               │         └─ qso_state.py:314 timeout_cycles==1 → send_message.emit(retry-msg)
               │         └─ encoder.transmit(retry-msg) startet → schlaeft 14s
               ├─ Z.508: _omni_tx.advance(qso_active=...)
               └─ Z.510+: Diversity-Antennen-Wechsel (Hardware)

T_n+13.5    decoder.py:_decode_loop wacht auf (FT8: _SLOT - 1.5)
T_n+13.7    decoder.cycle_decoded.emit(messages)
T_n+13.75   ui/mw_cycle.py:_on_cycle_decoded (gequeued zu GUI):
            ├─ _assign_slot_parity / _update_dt_correction
            ├─ _handle_normal_mode(messages) oder _handle_diversity_operate
            │   └─ on_message_received(msg) → state-Wechsel WAIT_REPORT → TX_REPORT
            │   └─ send_message.emit("...RR73")
            │   └─ encoder.abort() + encoder.transmit("...RR73")  ← zu spaet, Retry sitzt schon im Queue
            ├─ _refresh_diversity_freq_view
            └─ _run_ap_lite_rescue / _run_auto_hunt

T_n+15      Slot N+2 startet (= Mike-TX-Slot)
            └─ Encoder schickt Retry "DA1TST DA1MHH -21" (Doppel!)
```

### 1.2 Warum schon mal funktionieren konnte (Stand vor v0.80)

Vor v0.80 trigger im Mike-TX-Slot direkt → Encoder hatte 0s Vorlauf →
"Slot-Rand sofort senden" → DT 0.6-0.8s → Decode-Failure am Empfaenger
→ Retry-Loop bis Mike's Initial-Call irgendwann "durchkam". Das hat
den Doppel-Report-Bug verschleiert.

### 1.3 Saubere Loesung

`qso_sm.on_cycle_end()` ans **Ende von `_on_cycle_decoded`** verschieben
— also NACH `on_message_received`-Verarbeitung des Slots. Dann:

- Slot N+1 RX-Slot der Gegenstation
- Decoder dekodiert bei T+13.5
- on_message_received(R+18) → state WAIT_REPORT → TX_REPORT → emit("...RR73")
- on_cycle_end laeuft am Ende → state ist TX_REPORT → KEIN Retry-Trigger
- Encoder schickt RR73 im Slot N+2 (Mike-TX) ✓

Wenn KEIN R+18 kommt:
- on_cycle_end laeuft → state == WAIT_REPORT → timeout_cycles=1 → Retry-Trigger
- Encoder hat ~1.5s Vorlauf zum Slot N+2 (FT8: 15 - 0.8 - 13.7 = 0.5s,
  oder Drift-Guard schickt zu Slot N+4 mit 15.5s Vorlauf)

---

## 2. Akzeptanzkriterien

### A — Funktional (FT8)

A1. **Doppel-Report-Bug behoben:** Wenn DA1TST in Slot N+1 mit R-Report
    antwortet, sendet Mike in Slot N+2 RR73 (nicht nochmal -21).
    Verifikation: Real-QSO mit 2. Station auf Icom-Empfaenger, 4-Slot-
    QSO-Pacing dokumentiert.

A2. **Retry-Pfad bleibt funktional:** Wenn DA1TST in Slot N+1 NICHT
    antwortet, sendet Mike in Slot N+2 (oder N+4 via Drift-Guard) den
    Retry "DA1TST DA1MHH -21" mit DT 0.0-0.1s am Empfaenger.

A3. **CQ-Pfad bleibt funktional:** `CQ_WAIT` triggert weiterhin neuen
    CQ nach 1 RX-Slot ohne Reply.

A4. **3-Min-Gesamttimeout** (qso_state.py:275-284) feuert bei laufendem
    QSO weiterhin (jetzt 1 Slot spaeter — akzeptabel).

### B — Side-Effect-frei

B1. **`_omni_tx.advance(qso_active=...)`** bleibt in `_on_cycle_start`
    (Z.508). Liest qso_state JETZT vom konsistenten Slot-Ende-Stand
    (vorher: direkt nach on_cycle_end im selben Block).

B2. **Diversity-Antennen-Wechsel** bleibt in `_on_cycle_start` (Z.510+).
    Hardware-Trigger gehoert zum Slot-START.

B3. **TX-Anzeige-Reset** (`update_tx_peak(0.0)`) und
    **Auto-TX-Level-Regelung** (`_auto_adjust_tx_level`) bleiben in
    `_on_cycle_start` (Z.494-499).

### C — Robustheit

C1. **Decoder-Hang akzeptiert:** Wenn `cycle_decoded` einen Slot lang
    nicht emittet wird (busy / exception / leerer Audio-Buffer), laeuft
    on_cycle_end fuer diesen Slot nicht. State bleibt eingefroren.
    Im naechsten Slot mit erfolgreicher Emission laeuft on_cycle_end.
    Counter inkrementiert um 1 statt 2 (Slot ueberspringen). Akzeptabel
    — Decoder-Hang ist eine Ausnahmesituation.

C2. **Pause-Modus** (`if not self.rx_panel._rx_active: return` in
    `_on_cycle_decoded` Z.41-42) verhindert weiterhin
    Slot-Fortschritt — aber jetzt friert auch on_cycle_end ein. Das
    ist gewollt: bei Pause kein QSO-Counter-Tick.

C3. **Tests:** alle 502 bestehenden Tests gruen. Mindestens 1 neuer
    Test: `test_on_cycle_end_runs_after_decoder_messages` — verifiziert
    dass on_cycle_end NACH on_message_received aufgerufen wird.

---

## 3. Vorgeschlagene Aenderung (Code-Diff-Skizze)

### 3.1 `ui/mw_cycle.py:_on_cycle_decoded` — am ENDE einfuegen

```python
# Z.71-72 derzeit:
self._run_ap_lite_rescue(messages)
self._run_auto_hunt(messages)
# +++ NEU: ans ENDE einfuegen:
self.qso_sm.on_cycle_end()
```

### 3.2 `ui/mw_cycle.py:_on_cycle_start` — Z.501 entfernen

```python
@Slot(int, bool)
def _on_cycle_start(self, cycle_num: int, is_even: bool):
    if not self.encoder.is_transmitting:
        self.control_panel.update_tx_peak(0.0)

    if self._fwdpwr_samples:
        self._auto_adjust_tx_level()

    # --- ENTFERNT (jetzt in _on_cycle_decoded am Ende):
    # self.qso_sm.on_cycle_end()

    _in_qso = self.qso_sm.state not in (
        QSOState.IDLE, QSOState.TIMEOUT,
        QSOState.CQ_CALLING, QSOState.CQ_WAIT,
    )
    self._omni_tx.advance(qso_active=_in_qso)

    # ... Diversity-Antennen-Wechsel bleibt unveraendert ...
```

### 3.3 Tests

```python
def test_on_cycle_end_runs_after_decoder_messages(qt_app):
    """Fix D: on_cycle_end darf erst NACH on_message_received feuern."""
    # mock qso_sm.on_message_received + on_cycle_end mit call-order tracking
    # _on_cycle_decoded([msg]) aufrufen
    # assert: on_message_received call vor on_cycle_end call
```

---

## 4. Frage an R1 (Reviewer)

R1, bitte pruefe:

**P1 (KRITISCH):** Gibt es einen Pfad, in dem `_on_cycle_decoded` NICHT
laeuft, aber `on_cycle_end` laufen MUESSTE? Decoder-Skip wegen
`_decode_busy` (decoder.py:191) — wir akzeptieren 1 Slot Verzoegerung.
Decoder-Exception (Z.298): emit faellt aus, on_cycle_end ueberspringt.
Ist das tragbar oder muss ein Notfall-Tick im Timer-Pfad bleiben?

**P2 (Encoder-Vorlauf bei FT4/FT2):** Decoder-Wake-Time ist
`_SLOT - _WAKE_OFFSETS` (decoder.py:180):
- FT8: 15 - 1.5 = 13.5 → Vorlauf nach Fix: ~1.3s (oder Drift-Guard skip auf +2 Slots = 16s)
- FT4: 7.5 - 0.5 = 7.0 → Vorlauf: ~0.5s (oder Drift-Guard skip = 8s)
- FT2: 3.8 - 0.3 = 3.5 → Vorlauf: ~0.3s (oder Drift-Guard skip = 4s)

Frage: ist ~0.3-0.5s Vorlauf bei FT4/FT2 ausreichend, oder triggert
Drift-Guard hier IMMER und Retry kommt erst 2 Slots spaeter? Mike hat
den Bug auf FT8 beobachtet, aber Fix muss FT4/FT2 nicht brechen.

**P3 (Race-Condition im naechsten `_on_cycle_start`):** Wenn
`_on_cycle_decoded` extrem spaet im Slot laeuft (z.B. T_n+14.9s wegen
GUI-Thread-Last), und Slot N+2 startet bei T_n+15.0 mit
`_on_cycle_start` (advance / Antenne) — kann es passieren, dass
`_on_cycle_start(N+2)` VOR `_on_cycle_decoded(N+1)` zur Ausfuehrung
kommt (beide Qt-queued)? Wenn ja: `_omni_tx.advance` liest
veralteten qso_state. Mitigation: Qt-Queued-Connection garantiert
FIFO-Reihenfolge pro Receiver — aber `_on_cycle_start` haengt am
`timer.cycle_start`, `_on_cycle_decoded` am `decoder.cycle_decoded` —
das sind ZWEI verschiedene Sender, FIFO gilt also nicht ueber Sender
hinweg.

**P4 (auto_hunt / ap_lite_rescue Reihenfolge):** Beide Aufrufe stehen
heute VOR dem geplanten on_cycle_end-Aufruf am Ende von
`_on_cycle_decoded`. Beide lesen `qso_sm.state`. Ist das OK oder
muessen sie auch nach on_cycle_end laufen?

**P5 (Pause-Edge-Case):** `_on_cycle_decoded` returnt early bei Pause
(Z.41-42). Heute laeuft on_cycle_end bei Pause trotzdem (vom Timer).
Mit Fix D nicht mehr. Wenn QSO laeuft + Mike pausiert + dann unpause:
faellt timeout_cycles um die Pause-Slots zurueck? Akzeptabel oder Bug?

**P6 (Test-Coverage):** Welcher Mini-Test deckt den Fix kompakt ab,
ohne die ganze Cycle-Pipeline zu mocken?

---

## 5. Out-of-Scope

- FT4/FT2-Decoder-Wake-Time-Tuning (separat falls noetig).
- Notfall-Tick im Timer falls Decoder dauerhaft haengt — derzeit
  akzeptiert.
- Refactor von `_on_cycle_start` / `_on_cycle_decoded` zu einem
  konsolidierten `_on_slot_processed`-Slot — erst wenn Bedarf da ist.

---

## 6. Aufwandsschaetzung

| Schritt | h |
|---|---|
| Code-Aenderung (2 Files, ~5 Zeilen) | 0.5 |
| Test schreiben | 1.0 |
| Real-QSO-Test mit 2. Station auf Icom | 0.5 |
| HISTORY.md + commit | 0.5 |
| Final-R1-Codereview | 0.5 |
| **Gesamt** | **~3 h** |

---

## 7. Migration / Backwards-compat

- `qso_state.py` API unveraendert.
- `mw_cycle.py` interne Aenderung — keine externe API.
- Keine Settings-File-Aenderung.
- Bestehende Test-Suite muss gruen bleiben (502 Tests).
