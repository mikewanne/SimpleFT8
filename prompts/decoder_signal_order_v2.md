# Fix E — Decoder-Signal-Reihenfolge fuer korrekten Fix D — V2

**Status:** V2 (nach Self-Review von V1, vor R1-Review).
**Datum:** 2026-04-30.
**Vorgaenger:** v0.81 (commit `267625d`) — Fix D (`on_decoder_finished`).

---

## 0. Kontext: Warum Fix D nicht wirkt

v0.81 Fix D sollte den Doppel-Report-Bug beheben durch Verschieben
des Retry-Triggers vom Slot-START in `on_decoder_finished()`, das
im Slot-Ende-Pfad (`mw_cycle._on_cycle_decoded`) NACH den
Message-Handlern aufgerufen wird.

**Annahme V3 (FALSCH):** "`_handle_normal_mode` ruft
`on_message_received` direkt → State wird gewechselt VOR
`on_decoder_finished`."

**Realitaet:** `on_message_received` wird NICHT in
`_handle_normal_mode` aufgerufen, sondern ueber das SEPARATE
`message_decoded`-Signal des Decoders, das ERST NACH `cycle_decoded`
emittet wird:

```python
# core/decoder.py:282-296 (aktuell):
if messages:
    self.cycle_decoded.emit(messages)        # 1. emit  → _on_cycle_decoded
    for msg in messages:
        ...
        self.message_decoded.emit(msg)       # 2. emit  → on_message_decoded → on_message_received
else:
    self.cycle_decoded.emit([])
```

Qt-Queue-FIFO pro Sender (Decoder→MainWindow): `_on_cycle_decoded`
laeuft KOMPLETT durch (inkl. mein `on_decoder_finished`), BEVOR die
einzelnen `on_message_decoded`-Aufrufe verarbeitet werden.

**Konsequenz:** Der Retry-Trigger feuert vor dem State-Wechsel. Bug
bleibt bestehen.

**Beweis im Log (30.04. 09:54:13):**
```
09:53:59 WAIT auf DA1TST (WAIT_RR73, Zyklus 1/5)
09:54:13 RETRY WAIT_RR73 → emit("DA1TST DA1MHH -23")    ← Retry feuert ZUERST
09:54:13 STATE WAIT_RR73 → TX_REPORT
09:54:13 RX Von DA1TST: 'DA1MHH DA1TST R+19'             ← message processing NACH Retry
09:54:13 R-Report waehrend TX_REPORT gemerkt: R+19 → wird RR73
```

---

## 1. Loesung: Neues Signal `cycle_finished` am Decoder

**Idee:** Im Decoder ein zusaetzliches Signal `cycle_finished`
einfuehren, das NACH allen `message_decoded`-Emissions feuert. Der
`on_decoder_finished()`-Aufruf haengt an diesem neuen Signal — damit
laeuft er garantiert NACH den Message-Verarbeitungen.

```python
# core/decoder.py — geplant:
cycle_decoded = Signal(list)
message_decoded = Signal(object)
cycle_finished = Signal()        # NEU

# in _process_cycle:
if messages:
    self.cycle_decoded.emit(messages)
    for msg in messages:
        ...
        self.message_decoded.emit(msg)
    self.cycle_finished.emit()   # NEU — am Ende
else:
    self.cycle_decoded.emit([])
    self.cycle_finished.emit()   # NEU — auch bei leeren Slots
```

```python
# ui/mw_radio.py — geplant:
self.decoder.message_decoded.connect(self.on_message_decoded)
self.decoder.cycle_decoded.connect(self._on_cycle_decoded)
self.decoder.cycle_finished.connect(self._on_cycle_finished)   # NEU

# ui/mw_cycle.py — geplant:
@Slot()
def _on_cycle_finished(self):
    """Wird vom Decoder NACH allen message_decoded-Emissions aufgerufen."""
    if not self.rx_panel._rx_active:
        return
    self.qso_sm.on_decoder_finished()

# In _on_cycle_decoded: Aufruf an on_decoder_finished ENTFERNEN
```

---

## 2. Akzeptanzkriterien

### A — Funktional (FT8)

A1. **Doppel-Report-Bug behoben:** Wenn Gegenstation in RX-Slot
    R-Report sendet, hat `on_message_received` State zu TX_REPORT
    gewechselt BEVOR `on_decoder_finished` Retry triggert.
    Verifikation: Real-QSO mit 2. Station auf Icom — 4-Slot-QSO-
    Pacing.

A2. **Retry-Pfad bleibt funktional:** Wenn Gegenstation NICHT
    antwortet, sendet Mike Retry mit DT 0.0-0.1s am Empfaenger.

A3. **`msg._tx_even`-Konsistenz:** `_assign_slot_parity` (in
    `_on_cycle_decoded`) setzt `m._tx_even` BEVOR
    `on_message_received` es liest (mw_qso.py:85, :423). Reihenfolge
    weiter gewahrt — `cycle_decoded` bleibt VOR `message_decoded`.

A4. **CQ_WAIT bleibt in `on_cycle_end`** (Slot-START). Decoder-
    unabhaengig, weiter funktional auch bei Decoder-Hang.

A5. **3-Min-Gesamttimeout bleibt in `on_cycle_end`** (Slot-START).
    Decoder-unabhaengig.

### B — Side-Effect-frei

B1. **`_handle_normal_mode` / `_handle_diversity_operate`** — laufen
    weiterhin in `_on_cycle_decoded` BEFORE message_decoded. Akku-
    Logik unveraendert.

B2. **`_run_auto_hunt` / `_run_ap_lite_rescue`** — laufen weiterhin
    in `_on_cycle_decoded`, also VOR `on_message_received`. State-
    Read ist toleriert (sie filtern eh auf IDLE/TIMEOUT, was nicht
    durch Decoder-Messages gewechselt wird).

B3. **`_omni_tx.advance` und Diversity-Antennen-Wechsel** —
    unveraendert in `_on_cycle_start` (Slot-START).

B4. **`_dx_tune_dialog.feed_cycle(messages)`** — laeuft weiterhin in
    `_on_cycle_decoded`. Liest messages-Liste, kein State-Read.
    Reihenfolge unkritisch.

### C — Robustheit

C1. **Empty-Slot-Fall:** `cycle_finished` wird AUCH bei leerem
    `messages` emittet (Z.296 else-Branch). `on_decoder_finished`
    laeuft trotzdem — wichtig fuer korrekten on_cycle_end-Tick beim
    Folge-Slot.

C2. **Decoder-Hang:** wenn Decoder skippt (busy/exception/leerer
    Audio-Buffer in decoder.py:190-203, oder Exception in Z.298),
    wird `cycle_finished` NICHT emittet. `on_decoder_finished`
    laeuft nicht. Akzeptabel — Decoder-Hang ist Ausnahme. Fix D's
    Aufspaltung sorgt dafuer dass CQ_WAIT/Gesamttimeout/Counter
    weiterticken.

C3. **`_process_cycle`-Exception MITTEN drin:** wenn z.B. zwischen
    `cycle_decoded.emit` und der `for msg`-Loop eine Exception
    fliegt, wird `cycle_finished` NICHT emittet. `_decode_busy`-
    Flag wird im except-Pfad zurueckgesetzt → naechster Slot laeuft
    normal weiter.
    Mitigation OPTIONAL: `try/finally` um den Loop, mit
    `cycle_finished.emit()` im finally. Aber das wuerde
    `on_decoder_finished` auch bei kaputten Slots aufrufen — heikel
    weil state moeglicherweise inkonsistent. **Entscheidung V2:**
    keine try/finally — bei Exception Slot ueberspringen ist
    sicherer als Halb-State-Tick.

C4. **Pause-Modus:** `_on_cycle_finished` checkt
    `rx_panel._rx_active` analog `_on_cycle_decoded`. Bei Pause kein
    Counter-Fortschritt durch `on_decoder_finished`.

C5. **Race cycle_start(N+1) vs cycle_finished(N):** beide aus
    DIFFERENT Sendern (Timer-Thread vs Decoder-Thread). Qt-FIFO
    gilt nur PRO Sender. Theoretisch kann
    `_on_cycle_start(N+1)` VOR `_on_cycle_finished(N)` zur
    Ausfuehrung kommen, wenn Decoder sehr spaet im Slot N
    dispatched.
    - Konsequenz: `_omni_tx.advance` (Z.508) liest qso_state
      VOR `on_decoder_finished` von Slot N → stale state.
    - Heute schon der Fall (Fix D V3 hatte das in P3 dokumentiert).
    - Akzeptiert — Decoder-Latenz typ. <1s, Slot 15s, Race-Window
      sehr klein.

C6. **Tests:**
    - alle 505 bestehenden Tests gruen (Fix-D-Tests testen
      `on_decoder_finished` isoliert, unabhaengig vom Aufruf-Pfad).
    - 1 neuer Test: verifiziert dass `_process_cycle` die 3 Signale
      in der richtigen Reihenfolge emittet (cycle_decoded →
      message_decoded[*] → cycle_finished).

---

## 3. Code-Diff-Skizze

### 3.1 `core/decoder.py`

```python
class FT8Decoder(QObject):
    cycle_decoded = Signal(list)
    message_decoded = Signal(object)
    cycle_finished = Signal()        # +++ NEU

    # ... in _process_cycle, NACH dem Loop:
    if messages:
        self.cycle_decoded.emit(messages)
        for msg in messages:
            ...
            self.message_decoded.emit(msg)
        self.cycle_finished.emit()    # +++ NEU
    else:
        self.cycle_decoded.emit([])
        self.cycle_finished.emit()    # +++ NEU
```

### 3.2 `ui/mw_radio.py:55-57`

```python
self.decoder.message_decoded.connect(self.on_message_decoded)
self.decoder.cycle_decoded.connect(self._on_cycle_decoded)
self.decoder.cycle_finished.connect(self._on_cycle_finished)  # +++ NEU
```

### 3.3 `ui/mw_cycle.py:_on_cycle_decoded` — on_decoder_finished entfernen

Z.62-67 (Fix D von v0.81) komplett entfernen:

```python
# ENTFERNT:
# v0.81 Fix D: Retry-Trigger NACH Message-Verarbeitung am Slot-Ende.
# self.qso_sm.on_decoder_finished()
```

Replace mit Kommentar der den neuen Pfad erklaert.

### 3.4 `ui/mw_cycle.py` — neue Methode `_on_cycle_finished`

```python
@Slot()
def _on_cycle_finished(self):
    """v0.82 Fix E — Slot-Ende-Hook NACH allen Decoder-Messages.

    Wird vom Decoder ueber das `cycle_finished`-Signal aufgerufen,
    NACHDEM alle message_decoded-Emissions verarbeitet sind. Damit
    laeuft `on_decoder_finished` nach den State-Wechseln durch
    on_message_received → Doppel-Report-Bug verhindert.

    Reihenfolge im GUI-Thread (Qt-FIFO pro Sender=Decoder):
    1. _on_cycle_decoded(messages) — Aggregation, _assign_slot_parity
    2. Pro msg: on_message_decoded(msg) → on_message_received → state-Wechsel
    3. _on_cycle_finished() → on_decoder_finished sieht finalen state ✓
    """
    if not self.rx_panel._rx_active:
        return
    self.qso_sm.on_decoder_finished()
```

### 3.5 Tests — `tests/test_modules.py`

Neuer Test (Reihenfolge-Garantie ueber `_process_cycle` ist schwer
zu mocken — daher pure Signal-Reihenfolge testen via direkter
emit-Aufrufe in einer FT8Decoder-Instanz):

```python
def test_decoder_signal_order_cycle_finished_last():
    """Fix E: cycle_finished feuert NACH cycle_decoded und message_decoded.

    Reihenfolge ist die Garantie hinter Fix D: on_decoder_finished
    sieht den finalen state nach allen on_message_received-Calls.
    """
    from PySide6.QtCore import QCoreApplication
    from core.decoder import FT8Decoder, FT8Message
    import sys

    app = QCoreApplication.instance() or QCoreApplication(sys.argv)
    decoder = FT8Decoder.__new__(FT8Decoder)
    # __init__ skippen weil ft8lib nicht noetig
    from PySide6.QtCore import QObject
    QObject.__init__(decoder)

    call_order = []
    decoder.cycle_decoded.connect(lambda msgs: call_order.append(("cyc", len(msgs))))
    decoder.message_decoded.connect(lambda m: call_order.append(("msg", m.raw)))
    decoder.cycle_finished.connect(lambda: call_order.append(("done",)))

    fake_msgs = [
        FT8Message(raw="CQ DA1MHH JO31", caller="DA1MHH", target="CQ",
                   grid="JO31", snr=-10, freq_hz=1500, dt=0.1),
        FT8Message(raw="CQ K1JT FN42", caller="K1JT", target="CQ",
                   grid="FN42", snr=-12, freq_hz=1700, dt=0.0),
    ]

    # Manuell die Decoder-Sequenz nachstellen wie in _process_cycle
    decoder.cycle_decoded.emit(fake_msgs)
    for m in fake_msgs:
        decoder.message_decoded.emit(m)
    decoder.cycle_finished.emit()

    app.processEvents()  # Slots ausfuehren

    assert call_order == [
        ("cyc", 2),
        ("msg", "CQ DA1MHH JO31"),
        ("msg", "CQ K1JT FN42"),
        ("done",),
    ], f"Falsche Reihenfolge: {call_order}"
```

---

## 4. Frage an R1 (Reviewer)

R1, du bist Senior-Reviewer fuer einen Bugfix in einem PySide6-FT8-
Funkclient. Der Plan steht oben. Code-Files sind angehaengt
(decoder.py, mw_radio.py, mw_cycle.py, qso_state.py, mw_qso.py).
Du sollst KEINEN Code schreiben, nur reviewen.

Antwort fuer JEDE der 6 Fragen kurz mit JA/NEIN/TRADEOFF + Datei:Zeile:

**P1 (Decoder-Hang):** Wenn `_decode_loop` skippt
(decoder.py:190-203 busy/empty buffer, oder Z.298 Exception), wird
`cycle_finished` NICHT emittet. `on_decoder_finished` laeuft nicht.
Tragbar oder Notfall-Tick noetig?

**P2 (Race message_decoded vs cycle_finished):** Beide aus DEM
SELBEN Sender (Decoder, ein `_process_cycle`-Thread zur Zeit wegen
`_decode_busy`-Lock decoder.py:189-202). Qt-FIFO ist pro Sender
garantiert. Ist die Reihenfolge cycle_decoded → message_decoded[*] →
cycle_finished sicher unter ALLEN Bedingungen?

**P3 (`_assign_slot_parity` Konsistenz):** `mw_qso.py:85` und `:423`
lesen `msg._tx_even`. Das wird in `_on_cycle_decoded._assign_slot_parity`
gesetzt — also VOR `on_message_received` (cycle_decoded vor
message_decoded). Mit Fix E unveraendert. Bestaetigen?

**P4 (Race cycle_start(N+1) vs cycle_finished(N)):** unterschiedliche
Sender (Timer vs Decoder). Theoretisch kann
`_on_cycle_start(N+1)` (Slot N+1 Start) VOR
`_on_cycle_finished(N)` zur Ausfuehrung kommen, wenn Decoder spaet
ist. `_omni_tx.advance` (Z.508) liest dann stale qso_state. Ist
das praktisch ein Problem?

**P5 (`try/finally` um Decoder-Emit-Sequenz?):** Aktuell V2 sagt
NEIN — Exception → cycle_finished skip → akzeptabel. R1, siehst du
einen Pfad der `try/finally` rechtfertigt?

**P6 (eigeninitiativ):** Wenn dir noch was auffaellt — z.B. ob ein
Existing-Pfad in mw_qso.py oder qso_state.py mit Fix E anders
verhaelt — nenn es.

---

## 5. Out-of-Scope

- Refactor zu konsolidiertem `cycle_processed`-Signal (3 Signale →
  1). Architekturaenderung, nicht in diesem Fix.
- Versionsbump v0.81 → v0.82 (Bugfix-only, nicht Feature).
- HANDOFF.md / CLAUDE.md Update: in Fix-E-Release-Commit zusammen
  mit HISTORY.md.

---

## 6. Aufwandsschaetzung

| Schritt | h |
|---|---|
| Code-Aenderung (3 Files: decoder.py, mw_radio.py, mw_cycle.py — ~10 Zeilen) | 0.5 |
| 1 Reihenfolge-Test | 1.0 |
| Real-QSO-Test mit 2. Station | 0.5 |
| HISTORY.md + atomare Commits | 0.5 |
| Final-R1-Codereview | 0.5 |
| **Gesamt** | **~3 h** |

---

## 7. Migration / Backwards-compat

- `decoder.py` API erweitert (additiv: neues Signal, kein Bruch).
- `mw_radio.py` 1 neue Connect-Zeile.
- `mw_cycle.py`: 1 Zeile entfernt + 1 neue Methode (additiv).
- Keine Settings-File-Aenderung.
- Bestehende Fix-D-Tests bleiben gruen.

---

## 8. V1 → V2 Self-Review-Diff

1. **A4/A5 explizit** — CQ_WAIT und 3-Min-Gesamttimeout bleiben in
   on_cycle_end (Decoder-unabhaengig, kein Bruch).
2. **B4 neu** — `_dx_tune_dialog.feed_cycle` als unkritisch
   dokumentiert.
3. **C3 neu** — `_process_cycle`-Exception MITTEN drin: Entscheidung
   gegen `try/finally` mit Begruendung.
4. **C5 neu** — Race cycle_start(N+1) vs cycle_finished(N) als
   bekannten Tradeoff dokumentiert (war in V3-Fix-D auch P3,
   konsistent uebernommen).
5. **Test konkret** — Decoder direkt mit `__new__`+`QObject.__init__`
   instanziieren, ft8lib-Bypass. App via `QCoreApplication`
   bereitstellen, `processEvents()` aufrufen.
6. **R1-Frage P5 neu** — `try/finally`-Frage explizit gestellt.
