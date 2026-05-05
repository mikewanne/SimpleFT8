# First-Reply-Lost-Bug — Diagnose V3 (final, vor R1)

**Status:** V3 = nochmal frische-KI ueber V2. Schaerft die Loesungs-
Empfehlung — V2 hatte Optionen A, B, C, D, E nebeneinander mit
unklarer Praeferenz. V3 zeigt: **Option C ALLEIN reicht NICHT**,
weil Encoder die geplante CQ trotzdem im sleep haelt. Nur die
**Kombination C + A** loest den Bug zuverlaessig.

V3 ist eigenstaendig (R1 braucht nur V3 + Code).

---

## 1. Symptom (unveraendert, 4× heute reproduziert)

```
:05:30 [E] → CQ
:05:45 [O] ← DA1MHH DA1TST JO31     ← DA1TST ruft
:06:00 [E] → CQ                      ← BUG: noch CQ statt Report
:06:15 [O] ← DA1MHH DA1TST JO31      ← Wiederholung
:06:30 [E] → DA1TST DA1MHH -21       ← Report 1 Slot zu spaet
```

Mike: *„den kann ich gut immer wieder nachstellen"* → Race ist
**reproduzierbar**, nicht zufaellig.

---

## 2. Architektur-Komponenten — Timing-Constraints

| Komponente | Wake | FT8-Konstante |
|---|---|---|
| Encoder | `next_boundary - 1.3s` | TARGET_TX_OFFSET = -0.8s, sleep-padding 0.5s, FlexRadio TX-buffer 1.3s |
| Decoder | `slot + 13.5s` | _WAKE_OFFSET = 1.5s |
| Timer (cycle_start) | Slot-Boundary +/- 100ms | tick 0.1s |
| Decode-Time | 0.5-3.0s | 5-Pass Subtraction × 3 SLIDE_OFFSETS |

**Race-Berechnung (FT8, dichte Stationen):**
- Decoder wakes :05:58.5 (slot+13.5 fuer :05:45-Slot)
- Decoder ready :05:59.0-:06:01.5 (decode-time variabel)
- Encoder wakes :05:58.7 (next_boundary :06:00 - 1.3)
- Encoder send_audio start :05:58.7+ε (BLOCKING, kein Abort)

**→ Encoder ist 0.2-3.0s VOR Decoder fertig.** Reproduzierbar wenn
Stations-Dichte hoch.

---

## 3. Bug-Pfad ms-genau (V3 unveraendert)

| UTC | Aktion |
|---|---|
| :05:43.3 | tx_finished für :05:30-CQ → CQ_WAIT, tc=0 |
| :05:45.0 | Timer cycle_start → on_cycle_end: CQ_WAIT, tc=1 → **`_send_cq()`** → CQ_CALLING, encoder.transmit(CQ#B) |
| :05:45.0+ε | Encoder-Worker (CQ#B) sleep bis :05:58.7 |
| :05:58.5 | Decoder wakes (:05:45-slot decode) |
| :05:58.7 | Encoder-Worker wakes, **send_audio start (BLOCKING)** |
| :05:59.5 | Decoder fertig, message_decoded(DA1TST) emit |
| :05:59.5+ε | GUI: on_message_received → state=CQ_CALLING, **_pending_reply=msg** |
| **NICHT REVERSIBEL:** Encoder in send_audio, kein Abort | |
| :06:12.7 | tx_finished → on_message_sent: CQ_CALLING + pending → `_process_cq_reply` → state=TX_REPORT, encoder.transmit(report) |
| :06:30 | RF: Report TX (Drift-Guard hat +30s gesprungen) |

---

## 4. **WICHTIG: Option C ALLEIN reicht NICHT** (V3-Klarstellung)

V2 hatte Option C (`_WAKE_OFFSET = 2.5`, slot+12.5 wake) als plausible
Loesung diskutiert. **V3 zeigt: Option C alleine fixt den Bug nicht.**

**Warum nicht:**

Mit `_WAKE_OFFSET = 2.5`:
- Decoder wakes slot+12.5 = :05:57.5
- Decoder ready (1.0s decode): :05:58.5
- Encoder wakes :05:58.7 (unveraendert)

Decoder ist **0.2s vor Encoder fertig**. Aber:
- :05:58.5 message_decoded dispatched → on_message_received: state=CQ_CALLING → **_pending_reply=msg**
- :05:58.7 Encoder-Worker wakes aus sleep, **beginnt send_audio mit CQ#B (alte Message)**

**Encoder schlaeft mit der CQ#B-Message in der lokalen Variable!** Das
`_pending_reply=msg`-Update in qso_state aendert nichts an der laufenden
encoder.transmit(CQ#B). Audio wird mit CQ raus.

**→ Decoder-frueher-wake hilft nichts ohne Mechanismus zum Encoder-
Abort.**

V3-Verification: schaue `core/encoder.py:159-296` `_tx_worker`. Worker
nimmt `message: str` im Konstruktor. Keine Methode zum Aendern dieser
Message nach Thread-Start.

---

## 5. **DER FIX: Option C + Option A (Kombination)**

### Schritt 1 — Option C: `_WAKE_OFFSET = 2.5` (FT8 nur)

`core/decoder.py:138`:
```python
# VORHER:
_WAKE_OFFSETS = {"FT8": 1.5, "FT4": 0.5, "FT2": 0.3}
# NACHHER:
_WAKE_OFFSETS = {"FT8": 2.5, "FT4": 0.5, "FT2": 0.3}
```

Decoder wakes 1s frueher → ready 0.5-2.5s VOR Encoder-Wake.

**Audio-Buffer-Vollstaendigkeit:** FT8-Signal slot+0.5 bis slot+13.14
(12.64s). Buffer enthaelt slot+0 bis slot+12.5 = 12.5s. Letzte
0.64s Signal-Ende fehlt.

LDPC + Costas-Sync sind redundant — ~95% der Decodes fallen damit
nicht aus. SNR-Schwelle verschiebt sich um vermutlich -0.3 bis -0.8 dB.

**Stats-Risiko:** ~0.5-1% weniger Decodes bei schwachen Signalen.
Akzeptabel fuer Mike's Stats-Sammlung.

### Schritt 2 — Option A: Encoder-Replace im Sleep-Phase

**Encoder-API-Erweiterung** in `core/encoder.py`:

```python
def __init__(self, ...):
    ...
    self._audio_started = False
    self._replace_message: str | None = None
    self._replace_lock = threading.Lock()

def request_replace(self, message: str) -> bool:
    """Try to replace pending TX with new message during sleep phase.
    Returns True if successful, False if too late (audio already started).
    """
    with self._replace_lock:
        if not self._is_transmitting:
            return False  # nichts zu replacen
        if self._audio_started:
            return False  # zu spaet
        self._replace_message = message
        self._abort_event.set()  # wake worker from sleep
        return True
```

**Encoder-Worker-Erweiterung** in `_tx_worker_inner`:

```python
def _tx_worker_inner(self, message: str):
    # ... encoding ...

    while True:  # NEU: loop fuer Replace
        # 1. Sleep bis next_boundary - 1.3
        next_boundary = self._next_slot_boundary()
        sleep_dur = (next_boundary + TARGET_TX_OFFSET - 0.5) - time.time()
        if sleep_dur > 0.001:
            aborted = self._abort_event.wait(timeout=sleep_dur)
            if aborted:
                with self._replace_lock:
                    if self._replace_message is not None:
                        message = self._replace_message
                        self._replace_message = None
                        self._abort_event.clear()
                        # Re-encode mit neuer Message
                        audio_12k = self.encode_message(message)
                        if audio_12k is None:
                            return
                        if len(audio_12k) > TRIM_SAMPLES:
                            audio_12k = audio_12k[:-TRIM_SAMPLES]
                        continue  # Schleifen-Restart, neuer next_boundary
                    return  # Plain abort, no replace

        # 2. Audio-Start (point of no return)
        with self._replace_lock:
            self._audio_started = True
        # ... PTT, send_audio, ptt_off, tx_finished ...
        break  # Loop ende
```

**State-Machine-Erweiterung** in `core/qso_state.py:477-491`
(`on_message_received`):

```python
if self.state in (QSOState.IDLE, QSOState.CQ_WAIT, QSOState.CQ_CALLING) and msg.target == self.my_call:
    if msg.is_grid or msg.is_report:
        self._pending_reply = msg
        if self.state in (QSOState.IDLE, QSOState.CQ_WAIT):
            self._process_cq_reply()
        elif self.state == QSOState.CQ_CALLING:
            # NEU: try to replace pending CQ TX with report
            self.try_replace_pending_tx.emit(msg)  # neues Signal
        return
```

**Connect** in `ui/mw_qso.py`:

```python
self.qso_sm.try_replace_pending_tx.connect(self._on_try_replace_pending_tx)

@Slot(object)
def _on_try_replace_pending_tx(self, msg: FT8Message):
    """CQ-Reply waehrend CQ_CALLING: versuche TX-Replace."""
    if not msg.is_grid:  # nur Grid-Replies haben sofortigen Report
        return
    report = f"{msg.snr:+03d}" if msg.snr > -30 else "-10"
    tx_msg = f"{msg.caller} {self.qso_sm.my_call} {report}"
    if self.encoder.request_replace(tx_msg):
        # Replace erfolgreich → state direkt zu TX_REPORT
        self.qso_sm._pending_reply = None  # bereits verarbeitet
        self.qso_sm._set_state(QSOState.TX_REPORT)
        # qso-Daten setzen analog _process_cq_reply
        self.qso_sm.qso = QSOData(
            their_call=msg.caller,
            their_grid=msg.grid_or_report if msg.is_grid else "",
            freq_hz=msg.freq_hz,
            start_time=time.time(),
        )
        # encoder.tx_even setzen
        their_even = getattr(msg, '_tx_even', None)
        if their_even is not None:
            self.encoder.tx_even = not their_even
```

### Schritt 3 — Reset `_audio_started` und `_replace_message` zwischen TX

In `_tx_worker`:
```python
def _tx_worker(self, message: str):
    self._is_transmitting = True
    self._abort_event.clear()
    self._audio_started = False  # NEU
    with self._replace_lock:
        self._replace_message = None  # NEU
    try:
        self._tx_worker_inner(message)
    finally:
        self._is_transmitting = False
        self._audio_started = False
```

---

## 6. Erwartete Wirkung

**Vorher (Bug-Pfad):**
- :05:45 _send_cq → CQ_CALLING, encoder.transmit(CQ#B), worker sleep
- :05:58.5 Decoder ready, message_decoded
- :05:58.7 Encoder wake, **CQ#B audio start**
- → Report :06:30 (1 Slot Delay)

**Nachher (Fix-Pfad):**
- :05:45 _send_cq → CQ_CALLING, encoder.transmit(CQ#B), worker sleep
- :05:57.5 Decoder wakes (frueher durch Option C)
- :05:58.5 Decoder ready, message_decoded(DA1TST) emit
- :05:58.5+ε on_message_received: state=CQ_CALLING → try_replace_pending_tx.emit(msg)
- :05:58.5+ε' mw_qso._on_try_replace_pending_tx: encoder.request_replace(report)
- Encoder.request_replace: _audio_started=False → set _replace_message, abort_event.set()
- :05:58.5+ε'' Encoder-Worker (CQ#B) wakes from sleep, sieht _replace_message → re-encode mit Report-Message
- :05:58.5+ε''' Worker re-iterates loop: next_boundary = :06:00 (already correct), sleep_dur = :05:58.7 - :05:58.5 = 0.2s
- :05:58.7 Worker wakes wieder, audio start mit Report-Message
- :05:59.2 Audio first packet
- :06:00.5 RF Report TX
- → **Report :06:00 (kein Delay)** ✓

**Failure-Pfade (akzeptabel):**
- Decoder zu langsam (decode > 1.0s, ready > slot+13.5): Encoder wake war :05:58.7, audio bereits gestartet, request_replace returnt False → Status quo (1 Slot Delay).
- Decoder finished BEVOR transmit() (FT8 leeres Band): pending wird normal in CQ_WAIT-direct-Pfad verarbeitet → kein Delay.

---

## 7. Risiko-Analyse

| Risiko | Wahrscheinlichkeit | Mitigation |
|---|---|---|
| Decode-Quality-Verlust durch Wake-Offset 2.5 | mittel | Field-Test 1 Tag, Stats-Vergleich vor/nach |
| Race im _replace_lock (wenn 2 replace-Requests in 1 TX-Zyklus) | sehr gering | Lock + Set-Once-Logik |
| Encoder-Worker im Audio-Start-Race (request_replace zwischen Sleep-Wake und _audio_started=True) | gering | _replace_lock umfasst Audio-Start-Setzung |
| Re-Encode-Failure (encode_message returnt None) | sehr gering | Fallback: return aus Worker (kein TX) |
| Tests brechen | mittel | Neue Tests fuer Replace-Pfad noetig |

---

## 8. Auftrag an R1

V3 fokussiert auf 6 Pruefauftraege:

1. **Option C `_WAKE_OFFSET = 2.5` Trade-Off:** ist 12.5s FT8-Audio
   ausreichend fuer LDPC-Decode? Was sagt ft8_lib bei FT8-Signal mit
   0.64s Schwanz fehlend? SNR-Schwellwert-Verschiebung quantifizierbar?

2. **Encoder-Replace-Mechanik:** ist die `request_replace` API sauber?
   Sind die Race-Conditions (sleep-wake, _audio_started, _replace_lock)
   alle behandelt? Welche Edge-Case fehlt?

3. **State-Machine-Erweiterung:** ist `try_replace_pending_tx`-Signal-
   Pfad sauber? Sollte `_pending_reply = None` und State-Wechsel zu
   TX_REPORT IM qso_state oder IN mw_qso passieren? V3-Vorschlag
   trennt Verantwortung — sauber oder unsauber?

4. **Welche Tests:** wie wuerde ein pytest-Test fuer den Replace-Pfad
   aussehen? Decoder-Mock + Encoder-Mock + Timing-Simulation?

5. **`_send_cq()`-Reihenfolge:** sollte zusaetzlich der `_send_cq()`
   in `on_cycle_end` einen Check `if self._pending_reply is not None:
   return` bekommen? Oder reicht die Replace-Mechanik?

6. **Atomare Aufteilung:** sollte das in 1 oder 2 Commits gehen?
   - Option: Commit 1 = Option C (Decoder wake), Commit 2 = Option A
     (Replace-Mechanik). Klar getrennte Verantwortung.
   - Option: 1 Commit wenn beide zusammen den Fix ergeben.

---

## 9. Was V3 NICHT macht

- Keine Tests-Beispiele schreiben
- Kein Code-Diff, nur Sketch
- Bug #2 (Icom-73-Loop) ist separater Workflow

---

**V3 Ende. R1-Pruefung mit Code-Files folgt.**
