# Fix E — Decoder-Signal-Reihenfolge fuer korrekten Fix D — V1

**Status:** V1 (Erstentwurf, vor Self-Review).
**Datum:** 2026-04-30.
**Vorgaenger:** v0.81 (commit `267625d`) — Fix D (`on_decoder_finished`).

---

## 0. Kontext: Warum Fix D nicht wirkt

v0.81 Fix D sollte den Doppel-Report-Bug beheben durch Verschieben
des Retry-Triggers vom Slot-START in eine neue Methode
`on_decoder_finished()`, die im Slot-Ende-Pfad
(`mw_cycle._on_cycle_decoded`) NACH den Message-Handlern aufgerufen
wird.

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
    self.cycle_decoded.emit(messages)         # 1. emit  → _on_cycle_decoded
    for msg in messages:
        ...
        self.message_decoded.emit(msg)        # 2. emit  → on_message_decoded → on_message_received
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

**Idee:** Im Decoder ein zusaetzliches Signal `cycle_finished` einfuehren,
das NACH allen `message_decoded`-Emissions feuert. Der
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
    self.cycle_finished.emit()         # NEU — am Ende
else:
    self.cycle_decoded.emit([])
    self.cycle_finished.emit()         # NEU — auch bei leeren Slots
```

```python
# ui/mw_radio.py — geplant:
self.decoder.message_decoded.connect(self.on_message_decoded)
self.decoder.cycle_decoded.connect(self._on_cycle_decoded)
self.decoder.cycle_finished.connect(self._on_cycle_finished)   # NEU

# ui/mw_cycle.py — geplant:
@Slot()
def _on_cycle_finished(self):
    """Wird vom Decoder NACH allen message_decoded-Emissions aufgerufen.
    
    Reihenfolge im GUI-Thread (Qt-FIFO pro Sender=Decoder):
    1. _on_cycle_decoded(messages) — Aggregation, _assign_slot_parity
    2. Pro msg: on_message_decoded(msg) → on_message_received → state-Wechsel
    3. _on_cycle_finished() — qso_sm.on_decoder_finished sieht finalen state
    """
    if not self.rx_panel._rx_active:
        return
    self.qso_sm.on_decoder_finished()

# _on_cycle_decoded: Aufruf an on_decoder_finished ENTFERNEN
```

---

## 2. Akzeptanzkriterien

### A — Funktional (FT8)

A1. **Doppel-Report-Bug behoben:** Wenn Gegenstation in RX-Slot
    R-Report sendet, hat `on_message_received` State zu TX_REPORT
    gewechselt BEVOR `on_decoder_finished` Retry triggert. Verifikation:
    Real-QSO mit 2. Station auf Icom — 4-Slot-QSO-Pacing.

A2. **Retry-Pfad bleibt funktional:** Wenn Gegenstation NICHT
    antwortet, sendet Mike Retry mit DT 0.0-0.1s am Empfaenger.

A3. **`msg._tx_even`-Konsistenz:** `_assign_slot_parity` (in
    `_on_cycle_decoded`) setzt `m._tx_even` BEVOR `on_message_received`
    es liest (mw_qso.py:85, :423). Reihenfolge muss gewahrt bleiben.

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

### C — Robustheit

C1. **Empty-Slot-Fall:** `cycle_finished` wird AUCH bei leerem
    `messages` emittet. `on_decoder_finished` laeuft trotzdem (z.B.
    fuer Counter-Tick-Pfad — siehe Race mit on_cycle_end).

C2. **Decoder-Hang:** wenn Decoder skippt (busy/exception/leerer
    Audio-Buffer in decoder.py:190-203), wird `cycle_finished` NICHT
    emittet. `on_decoder_finished` laeuft nicht. Akzeptabel —
    Decoder-Hang ist Ausnahmesituation.

C3. **Pause-Modus:** `_on_cycle_finished` checkt `rx_panel._rx_active`
    wie `_on_cycle_decoded`. Bei Pause kein Counter-Fortschritt.

C4. **Tests:** alle 505 bestehenden Tests gruen. Mindestens 1 neuer
    Test fuer Reihenfolge-Garantie (Mock-basiert).

---

## 3. Code-Diff-Skizze

### 3.1 `core/decoder.py`

```python
# Klassen-Attribut hinzufuegen:
cycle_finished = Signal()  # NEU — emit nach allen message_decoded

# in _process_cycle nach dem Loop:
if messages:
    self.cycle_decoded.emit(messages)
    for msg in messages:
        ...
        self.message_decoded.emit(msg)
    self.cycle_finished.emit()        # +++ NEU
else:
    self.cycle_decoded.emit([])
    self.cycle_finished.emit()        # +++ NEU
```

### 3.2 `ui/mw_radio.py:55-57`

```python
self.decoder.message_decoded.connect(self.on_message_decoded)
self.decoder.cycle_decoded.connect(self._on_cycle_decoded)
self.decoder.cycle_finished.connect(self._on_cycle_finished)  # +++ NEU
```

### 3.3 `ui/mw_cycle.py:_on_cycle_decoded` — on_decoder_finished entfernen

```python
# Z.62-67 (Fix D von v0.81):
# v0.81 Fix D: Retry-Trigger NACH Message-Verarbeitung am Slot-Ende.
# ...
# self.qso_sm.on_decoder_finished()    ← ENTFERNEN

# Stattdessen wird on_decoder_finished in _on_cycle_finished aufgerufen
# (Fix E v0.82, ueber neues Decoder-Signal cycle_finished)
```

### 3.4 `ui/mw_cycle.py` — neue Methode `_on_cycle_finished`

```python
@Slot()
def _on_cycle_finished(self):
    """v0.82 Fix E — wird vom Decoder NACH allen message_decoded-Emissions
    aufgerufen.

    Hintergrund: Fix D v0.81 lief on_decoder_finished am Ende von
    _on_cycle_decoded — ABER Qt-FIFO sendet cycle_decoded VOR
    message_decoded, also lief on_decoder_finished VOR den State-
    Wechseln durch on_message_received. Doppel-Report-Bug blieb
    bestehen.

    Mit cycle_finished (separates Signal) ist die Reihenfolge:
    1. _on_cycle_decoded — Aggregation + _assign_slot_parity
    2. Pro msg: on_message_decoded → on_message_received (state-Wechsel)
    3. _on_cycle_finished → on_decoder_finished (sieht finalen state)
    """
    if not self.rx_panel._rx_active:
        return
    self.qso_sm.on_decoder_finished()
```

### 3.5 Tests — `tests/test_modules.py`

```python
def test_decoder_emits_cycle_finished_after_messages(qt_app):
    """Fix E: cycle_finished feuert NACH message_decoded.
    
    Verifikation der Signal-Reihenfolge im Decoder."""
    from core.decoder import FT8Decoder
    decoder = FT8Decoder(...)
    
    call_order = []
    decoder.message_decoded.connect(lambda m: call_order.append(("msg", m.raw)))
    decoder.cycle_finished.connect(lambda: call_order.append(("done",)))
    
    fake_msgs = [make_msg("CQ DA1MHH JO31"), make_msg("CQ K1JT FN42")]
    # _process_cycle direkt mit fake messages aufrufen oder via mock-emit
    
    decoder.cycle_decoded.emit(fake_msgs)
    for m in fake_msgs:
        decoder.message_decoded.emit(m)
    decoder.cycle_finished.emit()
    
    # Assert Reihenfolge
    assert call_order == [
        ("msg", "CQ DA1MHH JO31"),
        ("msg", "CQ K1JT FN42"),
        ("done",),
    ]
```

---

## 4. Frage an R1 (Reviewer)

R1, bitte pruefe konkret:

**P1 (Decoder-Hang):** Wenn `_decode_loop` skippt
(decoder.py:190-203 busy/empty buffer, oder Z.298 Exception), wird
`cycle_finished` NICHT emittet. `on_decoder_finished` laeuft nicht.
Ist das tragbar wie Fix D Z.C1 oder muss ein Notfall-Tick rein?

**P2 (Race-Condition message_decoded vs cycle_finished):** Beide
kommen aus DEM SELBEN Sender (Decoder). Qt FIFO PRO Sender ist
garantiert. Kann es trotzdem ein Problem geben (z.B. wenn
`_process_cycle` in einem Thread laeuft, und ein zweiter
`_process_cycle`-Thread parallel startet)? `_decode_busy`-Lock in
decoder.py:189-202 verhindert das eigentlich. Bestaetigen.

**P3 (Reihenfolge in `_on_cycle_decoded`):** Mit Fix E laufen
`_run_auto_hunt` und `_run_ap_lite_rescue` weiterhin VOR
`on_message_received`. Heute war das auch so (cycle_decoded vor
message_decoded). Reihenfolge unveraendert — aber R1, ist das
ueberhaupt sinnvoll? auto_hunt liest qso_sm.state und erwartet
IDLE/TIMEOUT. Wenn der aktuelle Slot ein State-Wechsel zu TIMEOUT
macht (max_timeout), wuerde auto_hunt das erst im NAECHSTEN Slot
sehen — heute bereits so. Akzeptabel.

**P4 (`_assign_slot_parity` muss vor `on_message_received` laufen):**
`mw_qso.py:85` und `:423` lesen `msg._tx_even`. Das wird in
`_on_cycle_decoded._assign_slot_parity` gesetzt — also VOR
`on_message_received` (wegen Reihenfolge cycle_decoded → message_decoded).
Nach Fix E unveraendert — `cycle_decoded` bleibt VOR
`message_decoded`. R1, bestaetige dass `_tx_even` weiterhin gesetzt
ist wenn `on_message_received` es liest.

**P5 (Test-Strategie):** Wie kompakt kann der Reihenfolge-Test sein?
Decoder-Klasse direkt instanziieren oder Mock?

**P6 (eigeninitiativ):** Wenn dir noch was auffaellt — nenn es.

---

## 5. Out-of-Scope

- Refactor zu konsolidiertem `cycle_processed`-Signal (heute
  cycle_decoded + cycle_finished + per-msg message_decoded — koennte
  zu einem einzigen "cycle_processed"-Signal mit messages-Liste
  werden, mw_cycle wuerde alles in einer Methode machen). Architektur-
  aenderung, KISS-violiert in diesem Fix-Kontext.
- Versionsbump v0.81 → v0.82.

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
- Bestehende Fix-D-Tests bleiben gruen (testen `on_decoder_finished`
  isoliert, unabhaengig vom Aufruf-Pfad).
