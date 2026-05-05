# First-Reply-Lost-Bug — Diagnose V1 (P1.9, 2026-05-05)

**Status:** V1 = Analyse-Prompt. Bug #1 vom Field-Test 09:55-10:06 UTC.
P1.5-Fix (5-Min-Sperre raus) wirkt — `_pending_reply` wird gesetzt. Aber
**1 Slot Verzoegerung** beim ersten Reply: zwischen DA1TST-Empfang und
unserem Report sendet die App eine ueberfluessige CQ.

Bug #2 (Icom sendet weiter 73 nach RR73) ist **separater Workflow**
(P1.10) — V1 fokussiert ausschliesslich Bug #1.

---

## 1. Symptom — Field-Test 10:03-10:06 UTC (3. Reproduktion heute)

```
10:03:30 [E] → CQ DA1MHH JO31      (FlexRadio EVEN)
10:04:00 [E] → CQ DA1MHH JO31
10:04:30 [E] → CQ DA1MHH JO31
10:05:00 [E] → CQ DA1MHH JO31
10:05:30 [E] → CQ DA1MHH JO31
10:05:45 [O] ← DA1MHH DA1TST JO31  ← DA1TST ruft auf ODD
10:06:00 [E] → CQ DA1MHH JO31      ← BUG: noch CQ statt Report
                Antworte DA1TST (ANT1)
10:06:15 [O] ← DA1MHH DA1TST JO31  ← DA1TST wiederholt
10:06:30 [E] → DA1TST DA1MHH -21   ← Report erst 1 Slot zu spaet
```

**Reproduzierbar 3× heute:**
- 09:39 (vorher), 09:47, 10:05 — **immer** 1 Slot Verzoegerung beim ersten Reply.

Mike's Aussage: *„am anfang wird immer die erste antwort ignoriert"*.

---

## 2. Root-Cause-Hypothese: Decoder-Encoder-Timing-Race

**FlexRadio TX-Pipeline** (encoder.py:220-237):
- Sleep bis `next_boundary - 1.3s` (= boundary - 0.8 - 0.5)
- Audio-Stream-Submit ab dann (BLOCKING `send_audio` mit packet-pacing
  5.33ms/Pkt, dauert real ~14s bis Audio-Ende)
- RF-Output ab `boundary + 0.5s` (FlexRadio TX-Buffer 1.3s konstant)

**Decoder-Pipeline** (decoder.py:127-179):
- Wakes `slot + 13.5s` (FT8 _WAKE_OFFSET = 1.5s vor Slot-Ende)
- `_process_cycle` Thread: Preprocessing + LDPC ~0.5-1.5s
- `message_decoded` emit ab `slot + 14.0s` (Decode-Time variabel)

**Konkurrenz im :05:45-Slot:**

| UTC | Thread | Aktion |
|---|---|---|
| :05:45.0 | Timer | `cycle_start` → `_on_cycle_start` → `qso_sm.on_cycle_end()`: state=CQ_WAIT, tc=1, cq_mode=True → **`_send_cq()`** → state=CQ_CALLING, `_pending_reply=None`, `encoder.transmit("CQ DA1MHH JO31")` |
| :05:45.0+ε | Encoder-Worker | startet, sleep bis `:06:00 - 1.3 = :05:58.7` |
| :05:58.5 | Decoder | wakes für :05:45-slot (slot + 13.5), `_process_cycle` thread |
| :05:58.7 | **Encoder-Worker** | wakes aus sleep, **beginnt `send_audio`** (BLOCKING, 14s) — Audio-Stream-Submit lockt sich bei 5.33ms/Pkt |
| :05:59.0–:06:00.0 | Decoder-Worker | decode fertig, emit `cycle_decoded` → `message_decoded(DA1TST)` → `cycle_finished` |
| :05:59.x | GUI-Thread | dispatched `message_decoded` → `on_message_received(DA1TST)`: state=CQ_CALLING → **`_pending_reply=msg`** ✓ (P1.5-Fix wirkt) |
| **NICHT REVERSIBEL:** Encoder ist in send_audio, kein Abort moeglich |
| :06:12.7 | Encoder-Worker | `send_audio` fertig, ptt_off, `tx_finished.emit()` |
| :06:12.7+ε | GUI | `on_message_sent`: state=CQ_CALLING + `_pending_reply=msg` → `_process_cq_reply` → state=TX_REPORT, `send_message.emit("DA1TST DA1MHH -21")` → `encoder.transmit(report)` |
| :06:13 | Encoder-Worker (neu) | next EVEN boundary mit overshoot (Drift-Guard +30s) → `:06:30` |
| :06:30 | RF | Report TX |

**Fazit:** Encoder wakes **0.2s VOR** Decoder-Ready (wenn Decoder schnell)
oder **bis zu 1.3s VOR** (wenn Decoder langsam mit AP-Lite/viele Stationen).
Audio-Submit startet bei :05:58.7, ist BLOCKING, kein Abort moeglich.
`_pending_reply` wird zwar gesetzt, aber der CQ-TX laeuft schon → kommt
1 Slot zu spaet zur Verarbeitung.

---

## 3. Code-Stellen (mit Datei:Zeile)

### Auslöser
- `core/qso_state.py:273-300` `on_cycle_end()` — Slot-START-Pfad. Bei
  `state=CQ_WAIT` triggert `_send_cq()` SOFORT (Z. 297-299):
  ```python
  if self.state == QSOState.CQ_WAIT:
      self.qso.timeout_cycles += 1
      if self.qso.timeout_cycles >= 1 and self.cq_mode:
          self._send_cq()
  ```
  → `encoder.transmit(CQ)` wird zu Slot-START gerufen, BEVOR der vorige
  Slot dekodiert ist.

### Encoder-Sleep
- `core/encoder.py:218-222`:
  ```python
  sleep_dur = (next_boundary + TARGET_TX_OFFSET - 0.5) - time.time()
  if sleep_dur > 0.001:
      aborted = self._abort_event.wait(timeout=sleep_dur)
  ```
  Sleeps until `next_boundary - 1.3s`. Dann sofort `send_audio` (BLOCKING).

### send_audio BLOCKING
- `radio/flexradio.py:1057-1085` — packet-pacing Loop, kein Abort-Check.

### Decoder-Wake
- `core/decoder.py:127-179` `_decode_loop()`:
  ```python
  _WAKE_OFFSETS = {"FT8": 1.5, "FT4": 0.5, "FT2": 0.3}
  _WAKE = _SLOT - _WAKE_OFFSETS.get(self._mode, 1.5)
  ```
  FT8 wakes at slot+13.5. Decode time ~0.5-1.5s → ready slot+14-15.

### _pending_reply-Setzung
- `core/qso_state.py:480-486` `on_message_received()` — bei
  state=CQ_CALLING wird `_pending_reply=msg` gesetzt, aber NICHT direkt
  verarbeitet (warten auf TX-Ende).

### tx_finished → _process_cq_reply
- `ui/mw_qso.py:211-214` `_on_tx_finished` → `qso_sm.on_message_sent()`
- `core/qso_state.py:388-396` `on_message_sent()`: bei state=CQ_CALLING +
  pending → `_process_cq_reply` → state=TX_REPORT, send_message.

---

## 4. Loesungs-Optionen (3 Pfade)

### Option A — Pre-Audio-Replace im Encoder (empfohlen)

Encoder bekommt `request_replace(message)`-Methode. Wenn Replace vor
`send_audio`-Start kommt, ersetzt der Worker die Message und re-scheduled
fuer den naechsten passenden Slot.

**Effektivitaet:** funktioniert nur wenn Decoder VOR `:05:58.7` (Encoder-
Wake) fertig ist. Bei FT8 ~30-50% der Faelle (decode time variabel).
**Bei den restlichen Faellen bleibt 1 Slot Verzoegerung** — aber dann
wuerden wir die unnoetige CQ zumindest abbrechen.

Code-Sketch:
```python
# encoder.py
def request_replace(self, message: str) -> bool:
    """Try to replace pending TX with new message.
    Returns True if successful (sleep phase), False if too late (audio).
    """
    if self._is_transmitting and not self._audio_started:
        with self._replace_lock:
            self._replace_message = message
            self._abort_event.set()
        return True
    return False
```

```python
# qso_state.py — neue Logik in on_message_received bei CQ_CALLING
self._pending_reply = msg
if msg.is_grid:
    report = f"{msg.snr:+03d}" if msg.snr > -30 else "-10"
    tx_msg = f"{msg.caller} {self.my_call} {report}"
    if hasattr(self.encoder, 'request_replace') and self.encoder.request_replace(tx_msg):
        # Replace successful → state direkt zu TX_REPORT
        self._set_state(QSOState.TX_REPORT)
        self.qso = QSOData(...)
        return
    # else: fallback auf bestehende Logik (warten auf tx_finished)
```

**Vorteile:** minimal invasiv, sauber wenn timing passt.
**Nachteile:** funktioniert nur fallweise.

### Option B — `_send_cq()` von Slot-START zu Slot-ENDE verschieben

Verschiebe den `_send_cq()`-Call aus `on_cycle_end` (Slot-START) in
`on_decoder_finished` (Slot-Ende ~slot+14.5).

**Effekt:** _pending_reply wird BEFORE _send_cq verarbeitet — keine
unnoetige CQ.

**Nachteil:** wenn no pending → `_send_cq()` ruft encoder.transmit bei
~slot+14.5. Encoder berechnet next_boundary für TX. now=:05:59.5
(slot+14.5 von :05:45-slot). Want EVEN. next EVEN boundary = :06:00,
sleep_dur = :06:00 - 1.3 - :05:59.5 = -0.8s. Negative → Drift-Guard:
overshoot=0.5s>0.3s → +30s → :06:30. **CQ wuerde :06:30 senden.**

→ Eine ganze CQ ausgelassen. Schlechter als A.

**Verworfen.**

### Option C — Decoder-Wake nach vorne ziehen (`_WAKE_OFFSET = 2.5`)

Decoder wakes at slot+12.5 statt slot+13.5. Decode finish ~slot+13.5.
Encoder wake at next_slot-1.3 = slot+13.7. Decoder 0.2s frueher fertig.

**Vorteile:** verlaesslicher als A, keine API-Aenderung.
**Nachteile:**
- Decoder verliert 1s Audio (FT8 Signal ist 12.64s, mit slot+12.5 wake
  liegt das Signal nicht komplett im Buffer). Decode-Qualitaet faellt
  potentiell ab.
- Andere Modi (FT4, FT2) muessten neu kalibriert werden.

**Risiko:** Stations-Anzahl in Stats faellt → 5-Min-Solar-Studie waere
nicht mehr vergleichbar.

### Option D — FlexRadio TX-Buffer reduzieren (1.3s → 0.5s)

Wenn FlexRadio den TX-Buffer kuerzer erlaubt, koennte Encoder spaeter
wake (z.B. boundary-0.5 statt boundary-1.3). Dann waere Decoder
zuverlaessig vor Encoder fertig.

**Nachteil:** TARGET_TX_OFFSET=-0.8s wurde von Mike empirisch ueber
Wochen gemessen und validiert. Reduktion = TX-DT-Drift-Risiko.

**Verworfen.**

---

## 5. Empfehlung V1

**Option A** (Pre-Audio-Replace) — minimal-invasiv, funktioniert in den
zeitlich guenstigen Faellen. Wenn timing nicht passt, fallback auf
bestehende Logik (1 Slot Verzoegerung).

**Plus:** Telemetrie-Log bauen — zaehlt wie oft Replace erfolgreich vs.
zu spaet. Mike kann ueber 1 Tag messen, wie oft der Bug tatsaechlich
greift.

---

## 6. Auftrag an V2 / R1

1. **Trace-Verifikation:** stimmt die Ms-Analyse? Insbesondere:
   - `cycle_start`-Timer feuert wirklich am Slot-Start (Boundary +/- ms)?
   - Encoder.send_audio ist wirklich BLOCKING ohne Abort-Check
     (flexradio.py:1057-1085)?
   - Decoder _WAKE_OFFSETS-Werte stimmen mit Field-Test ueberein
     (decode-time-Variation 0.5-1.5s)?

2. **Option A Architektur-Bewertung:**
   - Ist `request_replace()` API sauber? Welche Edge-Cases (Race im
     `_replace_lock`, multiple replace requests in einem TX-Zyklus)?
   - `_audio_started`-Flag: wo setzen (vor/nach send_audio? vor/nach
     ptt_on?)?
   - Threading: encoder.transmit ist daemon thread. request_replace
     wird aus GUI-Thread gerufen. Lock-Semantik?

3. **Option C als Alternative:** kann Decoder-Wake-Offset bei FT8 von
   1.5 auf 2.5 ohne Decode-Quality-Verlust? FT8-Signal ist 12.64s, also
   technisch reicht slot+12.5 fuer Decode.
   - Was sagt ft8_lib zu unvollstaendigen Buffern?
   - Risiko: AP-Lite-Pfad verliert mehr Decodes?

4. **Praxis-Daten:** in Field-Test :39 :47 :55 :05 — alle 4 Faelle 1
   Slot Verzoegerung. Aber Mike hatte vorher gesagt „manchmal klappt
   manchmal nicht". Was sind die guten Faelle? 0 Stationen im Slot,
   Decode in 0.3s? Oder ein anderer Pfad in der State-Machine?

5. **Hauptfrage:** ist die Architektur-Reorganisation den Aufwand wert?
   Oder ist das ein inhaerenter FlexRadio-Buffer-Effekt den man als
   „Hardware-Eigenschaft" akzeptiert (1 Slot Verzoegerung)?

   Mike's Position 2026-05-05: *„sieht immer noch nach einen problem
   aus"* — Mike sieht das als Bug, nicht als inhaerent.

---

## 7. Was V1 NICHT macht

- Keine Loesung implementieren — nur Analyse + Optionen.
- Kein Code-Diff. Mike entscheidet ueber Loesungs-Pfad.
- Bug #2 (Icom-73-Loop) ist separater Workflow (P1.10).

---

## 8. Hardware-Setup

- FlexRadio = DA1MHH (100W ANT1, Mike's Hauptstation, EVEN heute)
- IC-7300 = DA1TST (Mike's Test, ODD)
- 30m FT8

---

**V1 Ende. V2 = frische-KI Self-Review. Dann V3, R1, Mike-Vorlage.**
