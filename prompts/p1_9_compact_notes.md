# Compact-Notes — Stand vor P1.9-Plan-Workflow (2026-05-05)

Diese Datei sichert den Konversations-Kontext vor `/compact` damit der
naechste Session-Start sauber den P1.9-Plan-Workflow starten kann.

---

## Aktueller Stand: v0.95.2 (deployed, Commit `43dd062` + `c604188`)

P1.5-Fix komplett — 5-Min-Sperre `_WORKED_BLOCK_SECS = 300` + 3 Block-
Stellen + Methode `_is_worked_recently` + `_worked_calls` dict komplett
aus `core/qso_state.py` entfernt. -22 Zeilen, +0 Code. Tests 756 → 759
gruen. Field-Test bestaetigt: 4 QSOs in Folge, Warteliste funktioniert.

Mike's Funker-Philosophie: bekannte Stationen duerfen wieder anrufen,
Filter „Neue Stationen" im RX-Panel ist die korrekte Stelle (Anzeige-
Pfad), nicht die State-Machine.

App laeuft (PID 64268).

---

## P1.9 — First-Reply-Lost-Bug (Diagnose abgeschlossen, Plan ausstehend)

### Symptom — Field-Test 09:39, 09:47, 09:55, 10:05 UTC (4× heute)

```
:05:30 [E] → CQ DA1MHH JO31      (FlexRadio EVEN)
:05:45 [O] ← DA1MHH DA1TST JO31  (DA1TST ruft, ODD)
:06:00 [E] → CQ DA1MHH JO31      ← BUG: noch CQ statt Report
:06:15 [O] ← DA1MHH DA1TST JO31  (DA1TST wiederholt)
:06:30 [E] → DA1TST DA1MHH -21   ← Report 1 Slot zu spaet
```

Mike: *„den kann ich gut immer wieder nachstellen das hilft bei debuggen"*
→ reproduzierbar, nicht zufaellig.

### Wurzel — Decoder-Encoder-Timing-Race

- **Encoder** wakes `next_boundary - 1.3s` (zwingend, FlexRadio TX-Buffer 1.3s)
- **Decoder** wakes `slot + 13.5s`, ready `slot + 14.0-16.0s` (decode 0.5-3s)
- **Encoder ist 0.2-3.0s VOR Decoder fertig** → CQ-Audio bereits in
  `send_audio` (BLOCKING in `radio/flexradio.py:1057-1085`) wenn
  `_pending_reply` gesetzt wird → 1 Slot Verzoegerung systematisch.

### **WICHTIGE Klarstellung aus V3:** Option C alleine fixt den Bug NICHT

Encoder hat die CQ-Message bereits in lokaler Variable des TX-Worker-
Threads. State-Update in `qso_state` aendert nichts an laufender
`encoder.transmit(CQ#B)`. **Nur Kombination C + A** loest den Bug.

### Fix — Kombination C + A (R1-bestaetigt, 1 atomarer Commit)

**Schritt 1 — Option C: `_WAKE_OFFSETS["FT8"] = 1.5 → 2.5`**

`core/decoder.py:138`:
```python
# VORHER:
_WAKE_OFFSETS = {"FT8": 1.5, "FT4": 0.5, "FT2": 0.3}
# NACHHER:
_WAKE_OFFSETS = {"FT8": 2.5, "FT4": 0.5, "FT2": 0.3}
```

Decoder wakes 1s frueher → ready 0.5-2.5s VOR Encoder-Wake.

**R1-Bewertung:** SNR-Effekt **<0.1 dB**, da FT8-Signal bei `slot+13.14s`
endet (12.64s Signal + 0.5s Start-Offset) und Hanning-Fenster den Rand
bereits dampft. Praktisch verlustfrei.

**Schritt 2 — Option A: Encoder-Replace API**

Neue Encoder-Felder (`core/encoder.py.__init__`):
```python
self._audio_started = False
self._replace_message: str | None = None
self._replace_lock = threading.Lock()
```

Neue Methode `request_replace`:
```python
def request_replace(self, message: str) -> bool:
    """Try to replace pending TX with new message during sleep phase.
    Returns True if successful, False if too late (audio started or no TX).
    """
    with self._replace_lock:
        if not self._is_transmitting:    # R1-Add: is_transmitting-Guard
            return False
        if self._audio_started:
            return False
        self._replace_message = message
        self._abort_event.set()  # wake worker from sleep
        return True
```

`_tx_worker_inner` Loop-Umbau (Pseudo-Code):
```python
def _tx_worker_inner(self, message: str):
    while True:
        # encode
        audio_12k = self.encode_message(message)
        if audio_12k is None: return
        if len(audio_12k) > TRIM_SAMPLES:
            audio_12k = audio_12k[:-TRIM_SAMPLES]

        # next_boundary + sleep
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
                        continue   # re-loop mit neuer message
                return  # plain abort

        # Audio-Start (point of no return)
        with self._replace_lock:
            self._audio_started = True

        # ... silence + send_audio + ptt_off + tx_finished ...
        break
```

`_tx_worker` cleanup:
```python
def _tx_worker(self, message: str):
    self._is_transmitting = True
    self._abort_event.clear()
    self._audio_started = False        # NEU
    with self._replace_lock:
        self._replace_message = None    # NEU
    try:
        self._tx_worker_inner(message)
    finally:
        self._is_transmitting = False
        self._audio_started = False
```

**Schritt 3 — State-Machine Signal + Defense-in-Depth**

`core/qso_state.py`:
```python
# class signal (NEU)
try_replace_pending_tx = Signal(object)   # msg

# in on_message_received bei state=CQ_CALLING + Grid/Report:
self._pending_reply = msg
if self.state in (QSOState.IDLE, QSOState.CQ_WAIT):
    self._process_cq_reply()
elif self.state == QSOState.CQ_CALLING:
    self.try_replace_pending_tx.emit(msg)   # NEU
return

# R1-Defense-in-Depth in _send_cq (Z. 160-166):
def _send_cq(self):
    if self._pending_reply is not None:
        print(f"[QSO] _send_cq: pending {self._pending_reply.caller} → process statt CQ")
        self._process_cq_reply()
        return
    self._pending_reply = None
    msg = f"CQ {self.my_call} {self.my_grid}"
    ...
```

**Schritt 4 — mw_qso Slot-Handler**

`ui/mw_qso.py`:
```python
# in __init__ oder setUp connect:
self.qso_sm.try_replace_pending_tx.connect(self._on_try_replace_pending_tx)

@Slot(object)
def _on_try_replace_pending_tx(self, msg):
    """CQ-Reply waehrend CQ_CALLING: versuche TX-Replace im Encoder-Sleep."""
    if not msg.is_grid:
        return  # nur Grid-Replies haben sofortigen Report
    report = f"{msg.snr:+03d}" if msg.snr > -30 else "-10"
    tx_msg = f"{msg.caller} {self.qso_sm.my_call} {report}"
    if self.encoder.request_replace(tx_msg):
        # Replace erfolgreich → state direkt zu TX_REPORT
        self.qso_sm._pending_reply = None
        from core.qso_state import QSOData, QSOState
        self.qso_sm.qso = QSOData(
            their_call=msg.caller,
            their_grid=msg.grid_or_report if msg.is_grid else "",
            freq_hz=msg.freq_hz,
            start_time=time.time(),
        )
        self.qso_sm._set_state(QSOState.TX_REPORT)
        their_even = getattr(msg, '_tx_even', None)
        if their_even is not None:
            self.encoder.tx_even = not their_even
```

### Tests (3 neu, R1-skizziert)

```python
def test_replace_pending_tx_during_cq(encoder, qso_sm, decoder_msg):
    """Replace gelingt waehrend Encoder-Sleep."""
    qso_sm.state = QSOState.CQ_CALLING
    qso_sm.cq_mode = True
    encoder._is_transmitting = True
    encoder._audio_started = False
    qso_sm.on_message_received(decoder_msg)
    assert qso_sm._pending_reply is decoder_msg
    success = encoder.request_replace("DA1TST DA1MHH -10")
    assert success is True
    assert encoder._replace_message == "DA1TST DA1MHH -10"
    assert encoder._abort_event.is_set()

def test_replace_too_late_after_audio_start(encoder):
    encoder._is_transmitting = True
    encoder._audio_started = True
    success = encoder.request_replace("...")
    assert success is False
    assert encoder._replace_message is None

def test_replace_no_tx(encoder):
    encoder._is_transmitting = False
    success = encoder.request_replace("...")
    assert success is False
```

### Workflow-Plan fuer naechste Session

1. **Plan-V1** schreiben — `prompts/cq_first_reply_lost_fix_plan_v1.md` mit
   konkreten Code-Diffs, atomare Commit-Aufteilung (R1: **1 Commit**),
   Test-Coverage, Risiko-Analyse, Doku-Updates.
2. **Plan-V2** Self-Review.
3. **Plan-V3** nochmal frische KI.
4. **Plan-R1** mit DeepSeek + Code-Files.
5. **Plan-V3-final** + Mike-Freigabe.
6. **Code-Implementation** — 1 Commit alle 4 Code-Aenderungen + Tests + Doku-Commit.
7. **Field-Test** Mike: DA1TST-Szenario, Report sollte im SELBEN Slot kommen.

### Diagnose-Files (alle in `prompts/`)

- `cq_first_reply_lost_v1.md` — initiale Analyse, 4 Optionen
- `cq_first_reply_lost_v2.md` — Self-Review, Decode-Time-Realismus, Pfad B2 nie erreichbar nachgewiesen
- `cq_first_reply_lost_v3.md` — finale Klarstellung: Option C alleine reicht NICHT, C+A noetig
- R1-Antwort in Konversations-Kontext (alle 6 Pruefauftraege bestaetigt mit 3 Verbesserungen):
  1. SNR-Effekt von Wake-Offset 2.5 ist <0.1 dB (FT8-Spec, Hanning-Fenster)
  2. Race-Sicherheit von Encoder-Replace OK mit `is_transmitting`-Guard
  3. State-Machine-Trennung sauber via `try_replace_pending_tx`-Signal
  4. Tests-Skizzen (3 pytest-Tests)
  5. `_send_cq()`-Pending-Check als Defense-in-Depth empfohlen
  6. **1 Commit** empfohlen (C alleine fixt nicht)

---

## P1.10 — Icom-73-Loop (separater Workflow nach P1.9)

Field-Test 09:55-09:59 zeigte: nach unserem RR73 + 73-Empfang sendet
DA1TST IC-7300 weiter 73 (Auto-Sequence). Wir senden bereits CQ.

**Hypothese:** Icom-Auto-Sequence wartet auf Hoeflichkeits-73 zurueck.
WSJT-X-optional. Wir koennten nach 73-Empfang ein einzelnes 73 senden
(Counter max 1x).

→ Voller V1→V2→R1→V3 nach P1.9-Abschluss.

---

## Bekannte Fallen — wichtig fuer P1.9-Implementierung

- `core/encoder.py:151-153` — `transmit()` returnt SKIP wenn
  `_is_transmitting=True`. Bei `request_replace` umgehen, da der Worker
  weiterlaeuft (kein neuer transmit, sondern Loop).
- `core/encoder.py:222` — `_abort_event.wait(timeout=sleep_dur)` returnt
  True wenn aborted. Worker muss prüfen ob `_replace_message is not None`
  vor `return`, sonst plain abort (return).
- `radio/flexradio.py:1057-1085` `send_audio` ist BLOCKING. Kein Abort
  während Audio. Punkt-of-no-return ist `_audio_started = True`
  unmittelbar vor send_audio.
- `core/qso_state.py:160-166` `_send_cq()` setzt `_pending_reply = None`
  beim Eintritt. Defense-in-Depth-Check muss VOR der None-Setzung kommen.
- Tests: existing `test_qso_known_station_can_call_again` aus P1.5 darf
  nicht brechen.

---

## Memory-Pflicht nach P1.9-Erledigung

- HISTORY.md → v0.95.3 Eintrag
- HANDOFF.md (beide Pfade) Stand v0.95.3
- CLAUDE.md (beide Pfade) Aktueller Stand
- TODO.md → P1.9 als ✅
- Memory ggf. neu (R1-Workflow-Disziplin nach Race-Diagnose)

---

## Hardware (unveraendert)

- FlexRadio = DA1MHH (100W ANT1-Kelemen, ANT2-Regenrinne nur RX)
- IC-7300 = DA1TST (Test-Setup, manuell EVEN/ODD)
- 30m FT8 Field-Test heute

---

**Compact-Notes Ende. Naechster Session-Start: HANDOFF.md → TODO.md
P1.9 → diese Datei lesen → Plan-V1 schreiben.**
