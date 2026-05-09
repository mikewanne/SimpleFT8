# P2.OMNI-REDESIGN — V2 Prompt (Self-Review von V1)

**Datum:** 2026-05-09
**V1-Datei:** `prompts/p2_omni_redesign_v1.md`
**Source of Truth:** `prompts/omni_redesign_notes.md`
**Stand:** v0.95.22, Tests 1014 grün

---

## 0. V2 Self-Review-Lessons (frische KI-Rolle: was übersieht V1?)

### L1 ⛔ KRITISCH — Naive Vertauschung in `_send_cq()` fixt Bug NICHT

**V1 §6.1 sagt:**
```python
self.send_message.emit(msg)             # zuerst
self._set_state(QSOState.CQ_CALLING)    # danach
```

**Problem:** `send_message` ist via `connect(self._on_send_message)` ohne
explizite Connection-Type angeschlossen → `Qt.AutoConnection` → bei
gleichem Thread (qso_sm und mw_qso beide im GUI-Thread) wird das zu
`Qt.DirectConnection` → `emit()` läuft **synchron**, blockiert bis alle
Slots durchgelaufen sind, kehrt dann zurück.

Wenn Listener `_on_send_message` mit OMNI-RX-Slot-Filter `return` macht,
kehrt `emit()` ganz normal zurück und die nächste Zeile `_set_state(CQ_CALLING)`
**läuft trotzdem**. Der State wird also auf CQ_CALLING gesetzt → Bug bleibt
exakt wie vorher.

**Fix (in V2 verankert):** State-Wechsel an Listener-Erfolg koppeln. Drei
Varianten geprüft:

| Variante | Wie | Bewertung |
|---|---|---|
| **A.** State-Wechsel nach `tx_started.emit()` | `mw_qso._on_tx_started` setzt State wenn `message.startswith("CQ ")` | Clean, aber `tx_started` läuft im Encoder-Thread → QueuedConnection-Race |
| **B.** Flag-Pattern via Listener | Listener setzt `qso_sm._tx_was_skipped=True` bei skip; `_send_cq` checkt nach emit | KISS, minimal invasiv, dokumentiert |
| **C.** Listener setzt State direkt | `_on_send_message` ruft `qso_sm._set_state(CQ_CALLING)` nach `transmit()` auf | Coupling, aber Pattern ist im Code etabliert (`_on_try_replace_pending_tx`) |

**Mike-Wortlaut aus Notizen:** „erst `send_message.emit(msg)`, DANN
`_set_state(QSOState.CQ_CALLING)`. ⚠️ Race-Check Pflicht in V1 ... Falls
ja, Defense-in-Depth überlegen."

**V2-Entscheidung: Variante B (Flag-Pattern)** — am dichtesten an Mike's
Beschluss, KISS, kein Thread-Race, dokumentiert klar warum.

```python
# core/qso_state.py
def _send_cq(self):
    if self._pending_reply is not None:
        self._process_cq_reply()
        return
    msg = f"CQ {self.my_call} {self.my_grid}"
    self._dbg.log("TX", f"Sende: '{msg}'")
    # Listener-Skip-Flag — wird vom OMNI-Filter gesetzt wenn RX-Slot
    # → State bleibt unverändert (CQ_WAIT/IDLE) → on_cycle_end triggert
    # weiter → Loop läuft.
    self._omni_skip_state_change = False
    self.send_message.emit(msg)
    if not self._omni_skip_state_change:
        self._set_state(QSOState.CQ_CALLING)
```

```python
# ui/mw_qso.py _on_send_message
if self._omni_tx.active and message.startswith("CQ "):
    send_ok, target_even = self._omni_tx.should_tx()
    if not send_ok:
        # RX-Slot: TX skip + State-Wechsel skip
        self.qso_sm._omni_skip_state_change = True
        if hasattr(self.qso_sm, 'qso'):
            self.qso_sm.qso.calls_made = max(0, ...)
        return
    if target_even is not None:
        self.encoder.tx_even = target_even
```

**Defense-in-Depth:** `_omni_skip_state_change` wird bei jedem `_send_cq()`
auf False zurückgesetzt — kein Hänger zwischen verschiedenen Aufrufen.

---

### L2 ✅ EINGEARBEITET — `omni_tx.enable()` vs `start_with_parity_for_next_slot()`

**V1 unklar:** Soll `enable()` (alt) bleiben? Wer setzt initialen Block?

**V2-Klärung:**
- `enable()` wird durch `start_with_parity_for_next_slot(next_is_even: bool)`
  ersetzt — neue Methode kümmert sich um Block-Wahl + Slot-Init.
- `disable()` / `stop_omni_tx(reason)` bleibt unverändert.
- `_active`-Flag bleibt, wird in `start_with_parity_for_next_slot` gesetzt.

---

### L3 ⛔ WICHTIG — `is_paused()` Race + wer setzt Pause?

**V1 §6.3 sagt:** `mw_cycle._on_cycle_start` checkt `is_paused()` →
`advance()`. Aber wer setzt `pause()` und wann?

**V2-Klärung — Pause/Resume-Lifecycle:**

| Ereignis | Wer | Aktion |
|---|---|---|
| QSO startet via `_on_station_clicked` | mw_qso | `if _omni_tx.active: _omni_tx.pause()` BEVOR `start_qso(...)` |
| QSO startet via `_process_cq_reply` (CQ-Reply) | qso_state ruft `tx_slot_for_partner.emit` → mw_qso `_on_tx_slot_for_partner` | dort `if _omni_tx.active: _omni_tx.pause()` |
| QSO endet via `_on_qso_complete` | mw_qso | `if _omni_was_active_pre_qso: _omni_tx.start_with_parity_for_next_slot(...)` |
| QSO endet via `_on_qso_confirmed` (73 erhalten) | mw_qso | dito |
| QSO endet via `_on_qso_timeout` | mw_qso | dito |
| HALT via `_on_cancel` | mw_qso | `_omni_tx.stop_omni_tx("manual_halt")` (kein Resume) |

**Pre-QSO-Flag:** `MainWindow._omni_was_active_pre_qso: bool` —
wird in den 2 QSO-Start-Pfaden gesetzt (mw_qso), in den 3 QSO-End-Pfaden
geprüft (mw_qso). Reset nach Resume.

**Race-Frei?** `pause()` setzt nur `_paused=True`-Flag, `advance()` checkt
`_paused` — beide im GUI-Thread, kein Race.

---

### L4 🟡 EDGE-CASE — Klick exakt am Slot-Boundary

**V1 §6.4:** `next_is_even = not self.timer.is_even_cycle()`.

**Edge-Case:** Klick zwischen `t_slot_end - 0.1s` und `t_slot_end + 0.1s` —
welcher Slot ist „next"?

**V2-Klärung:** `is_even_cycle()` liefert den **aktuellen** Slot-Status zum
Aufruf-Zeitpunkt. „Next" = invertiert. Wenn Klick exakt am Boundary fällt:
- Vor Boundary: aktueller Slot z.B. Even, next = Odd → Block 2
- Nach Boundary: aktueller Slot Odd, next = Even → Block 1

Das ist konsistent mit dem realen Verhalten — die nächste TX-Möglichkeit
ist jeweils der nächste komplette Slot. Kein Special-Case nötig.

**Defense-in-Depth Test:** Mock `timer.is_even_cycle()` mit beiden
Werten, prüfe Block-Wahl.

---

### L5 ✅ EINGEARBEITET — „Alle Wege ins/aus QSO" konkretisiert (siehe L3)

V1 war zu vage. V2 listet die genauen Methoden in L3-Tabelle.

---

### L6 ⛔ WICHTIG — Caller-Queue + OMNI

**V1 erwähnt nicht:** Was passiert wenn während OMNI-RX-Slot eine CQ-Antwort
dekodiert wird?

**Code-Verifikation `core/qso_state.py:_process_cq_reply` Z.180-242:**
Antwort wird sofort verarbeitet → State wechselt zu `TX_REPORT` →
`send_message.emit(report)` → Listener prüft NICHT OMNI für non-CQ-Messages
(Z.306 `if message.startswith("CQ ")` — nur CQ wird gefiltert).

**Folge:** Reports werden IMMER gesendet, unabhängig von OMNI-Pattern-Slot.
Das ist korrekt — wer auf OMNI-CQ antwortet, soll Report bekommen.

**ABER:** das QSO startet damit. Wer ruft `_omni_tx.pause()` auf?
- `tx_slot_for_partner.emit(msg)` (qso_state Z.212) → `_on_tx_slot_for_partner`
  (mw_qso Z.706) — dort muss `_omni_tx.pause()` ergänzt werden.

**V2-Ergänzung:** in `_on_tx_slot_for_partner` (alle CQ-Reply-Pfade):
```python
if self._omni_tx.active and not is_courtesy:
    self._omni_was_active_pre_qso = True
    self._omni_tx.pause()
```

Plus: `_caller_queue` bleibt unverändert. Wenn QSO endet und Queue nicht
leer → `_resume_cq_if_needed()` ruft `_process_cq_reply()` für nächsten
Anrufer → neues QSO → OMNI-Pause bleibt aktiv (war ja noch nicht resumed).

**Resume-Trigger nur an QSO-ENDE wenn Queue leer.** Sonst nächstes QSO
direkt anschließen, OMNI bleibt pausiert.

---

### L7 🟡 KÖNNTE — Auto-Hunt-Konflikt

**V1 §6.4:** `if self._auto_hunt.active: stop_auto_hunt("superseded")`.

**Edge-Case:** OMNI-Activate während Auto-Hunt gerade in selbem Slot
einen Klick simuliert hat (User-Klick-Pfad parallel).

**V2-Klärung:** OMNI-Toggle und Auto-Hunt-Toggle sind beide UI-Slots im
GUI-Thread → keine Parallelität. Sequence: Mike klickt OMNI → `_on_btn_omni_cq_toggled`
läuft → `_auto_hunt.stop_auto_hunt("superseded")` läuft synchron → fertig
→ dann `_omni_tx.start_with_parity...`. Kein Race.

**Status: ✅ ACK** (V1 ist korrekt, kein Fix nötig).

---

### L8 ⛔ WICHTIG — `encoder.tx_even` doppelter Setter

**V1 unklar:** Encoder.tx_even wird gesetzt in:
1. `_on_send_message` (Z.320) wenn `_omni_tx.should_tx()` `target_even` liefert
2. `start_with_parity_for_next_slot` setzt `_block` + `_slot_index=0`, aber
   NICHT `encoder.tx_even` direkt
3. `_on_tx_slot_for_partner` (Z.715) setzt es bei Reply

**V2-Klärung:** Setter-Pfad bleibt EXAKT bei `_on_send_message` für CQ-Pfad.
`start_with_parity_for_next_slot` initialisiert nur den OMNI-internen State.
Wenn dann `_send_cq()` läuft, ruft Listener `should_tx()` → liest
`PATTERN[block][slot_index]` → setzt `encoder.tx_even` korrekt.

**Vorteil:** Single Source of Truth für `encoder.tx_even` bleibt der
Listener — keine doppelten Setter, keine Race.

---

### L9 ⛔ WICHTIG — Block-Switch-Test ohne Echtzeit

**V1 §8 fordert:** `test_block_switch_on_rollover`.

**Problem:** Wie testen wenn `advance()` Slot-Index inkrementiert,
Block-Switch erst bei `slot_index 4 → 0`?

**V2-Lösung:**
```python
def test_block_switch_on_rollover():
    omni = OmniTX()
    omni.start_with_parity_for_next_slot(next_is_even=True)  # Block 1, slot=0
    assert omni._block == 1
    for _ in range(4):
        omni.advance()  # 0→1→2→3→4
    assert omni._block == 1   # noch Block 1
    omni.advance()  # 4→0 → rollover → Block 2
    assert omni._block == 2
    assert omni._slot_index == 0
```

Kein Echtzeit nötig — `advance()` rein arithmetisch.

---

### L10 🟡 KÖNNTE — `calls_made`-Decrement im Filter

**V1 §6.6:** „obsolet aber als Defense-in-Depth behalten".

**V2-Anti-Liste-Check:** Anti #3 sagt „Mehrere Code-Pfade die das gleiche
tun". Der Decrement war Pflaster für CQ-Loop-Tod (jetzt durch L1 obsolet).

**V2-Entscheidung: RAUS.** Defense-in-Depth gilt nicht für nicht mehr
benötigte Logik. Wenn Loop-Bug zurückkommt: wir wollen das WISSEN, nicht
verstecken.

```python
# ui/mw_qso.py _on_send_message
if not send_ok:
    self.qso_sm._omni_skip_state_change = True
    print(f"[OMNI-TX] RX-Slot → skip CQ ({self._omni_tx.slot_label})")
    return
# (KEIN calls_made -= 1 mehr — war v0.95.22-Pflaster, durch L1-Fix obsolet)
```

---

### L11 ⛔ WICHTIG — `_resume_cq_if_needed` + OMNI-Resume

**V1 unklar:** Wer ruft `start_with_parity_for_next_slot()` auf wenn
QSO über `_resume_cq_if_needed()` endet (Hunt-Timeout-Pfad,
qso_state.py:392-408)?

**Code:**
```python
def _resume_cq_if_needed(self):
    if self.cq_mode or self._was_cq:
        self.cq_mode = True
        ...
        if self._caller_queue:
            ...
            self._process_cq_reply()
        else:
            self._send_cq()
    else:
        self._set_state(QSOState.IDLE)
```

**Problem:** wenn OMNI vor QSO aktiv war, müsste hier OMNI-Resume passieren.
Aber `qso_state.py` weiß nichts von OMNI (saubere Trennung).

**V2-Lösung:** OMNI-Resume passiert in mw_qso (nicht qso_state). Trigger:

| QSO-End-Pfad | mw_qso-Slot | OMNI-Resume |
|---|---|---|
| `qso_complete` (RR73 gesendet) | `_on_qso_complete` | ja, am Ende der Methode |
| `qso_confirmed` (73 erhalten) | `_on_qso_confirmed` | ja, am Ende der Methode |
| `qso_timeout` | `_on_qso_timeout` | ja, am Ende der Methode |

Alle drei werden vom `qso_state` per Signal emittiert. mw_qso-Listener
prüft `_omni_was_active_pre_qso` und ruft `start_with_parity_for_next_slot`.

```python
# ui/mw_qso.py _on_qso_complete (Beispiel)
# ... (existing cleanup) ...
if self._omni_was_active_pre_qso:
    next_is_even = not self.timer.is_even_cycle()
    self._omni_tx.start_with_parity_for_next_slot(next_is_even)
    # qso_sm.start_cq() ist redundant (resume_cq_if_needed hat das schon
    # gemacht falls _was_cq=True war), aber idempotent — kein Schaden
    self._omni_was_active_pre_qso = False  # Reset
```

---

### L12 ✅ EINGEARBEITET — Singleton-Pattern omni_tx

**V1 erwähnt:** `get_instance(block_cycles=40)` Inkonsistenz.

**V2-Klärung:** durch Refactor `block_cycles` raus → Singleton-Konstruktor
ohne Parameter. Falls `get_instance(...)` mit Parametern aufgerufen wird:
ignorieren oder Deprecation. Code-grep ergibt:

```python
# Alle Aufrufer von get_instance prüfen — falls block_cycles/operate_cycles
# noch übergeben wird: aus dem Aufruf entfernen (V3 muss diese Stellen
# explizit auflisten).
```

**V3-Pflicht:** alle Aufrufer von `OmniTX.get_instance(...)` enumerieren.

---

### L13 ⛔ WICHTIG — `is_even_cycle` Verifikation

**V1 §6.4:** nutzt `self.timer.is_even_cycle()`.

**V2-Pflicht:** existiert die Methode? Wenn ja, was liefert sie zum Klick-
Zeitpunkt — den **gerade laufenden** oder den **nächsten** Slot?

**Code-Verifikation pre-V3 (Schritt 0):** grep `is_even_cycle` in `core/timing.py`
→ Methode finden + Doku lesen + Test-Code prüfen.

**Falls Methode anders heißt:** auf `core.timing`-API mappen (V2 darf das
noch unscharf lassen, V3 muss exakt sein).

---

### L14 🟡 KÖNNTE — Reentrancy bei mehrfachem Toggle

**V1 §6.4:** wenn Mike OMNI 2× schnell hintereinander klickt — was passiert?

Sequence:
1. Klick 1: `_on_btn_omni_cq_toggled(True)` → OMNI startet
2. Klick 2: `_on_btn_omni_cq_toggled(False)` → `_omni_tx.stop_omni_tx("manual_halt")`
3. `omni_stopped`-Signal → `_on_omni_stopped` → CQ-Loop stop, Button-Off

Race? GUI-Thread, alle Slots synchron → kein Race. ✅ ACK.

---

### L15 ⛔ TESTS-LÜCKE — Caller-Queue + OMNI-Pause

**V1 §8 fehlt:** Test für L6-Szenario (CQ-Antwort während OMNI aktiv).

**V2-Ergänzung:**
```python
def test_omni_pause_on_cq_reply():
    # OMNI aktiv, CQ-Antwort kommt → _omni_tx.pause() wird aufgerufen
    ...

def test_omni_resume_after_qso_with_caller_queue():
    # OMNI war aktiv, QSO endet, Queue nicht leer → KEIN OMNI-Resume,
    # nächstes QSO startet sofort
    ...

def test_omni_resume_after_qso_empty_queue():
    # OMNI war aktiv, QSO endet, Queue leer → OMNI-Resume mit korrekter Parität
    ...
```

---

## 1. Auftrag an DeepSeek (R1) — unverändert von V1

(siehe V1 §1 — exakt gleicher Auftrag)

---

## 2. Aktualisierte Architektur-Sicht (V2)

### 2.1 Bug-Wurzel (verifiziert L1)

`core/qso_state.py:177` setzt State VOR `send_message.emit()`. Bei OMNI-RX-Slot
filtert Listener TX weg, aber State wurde bereits umgesetzt → State stuck
in CQ_CALLING → on_cycle_end greift nicht mehr → Loop tot.

### 2.2 Fix (V2-präzisiert: Variante B Flag-Pattern)

```python
# core/qso_state.py
def _send_cq(self):
    if self._pending_reply is not None:
        self._process_cq_reply()
        return
    msg = f"CQ {self.my_call} {self.my_grid}"
    self._dbg.log("TX", f"Sende: '{msg}'")
    self._omni_skip_state_change = False     # NEU
    self.send_message.emit(msg)               # synchron, Listener läuft
    if not self._omni_skip_state_change:      # nur wenn TX wirklich lief
        self._set_state(QSOState.CQ_CALLING)
```

```python
# ui/mw_qso.py _on_send_message
if message.startswith("CQ "):
    if self._omni_tx.active:
        send_ok, target_even = self._omni_tx.should_tx()
        if not send_ok:
            self.qso_sm._omni_skip_state_change = True   # NEU
            print(f"[OMNI-TX] RX-Slot → skip CQ ({self._omni_tx.slot_label})")
            return                                        # KEIN calls_made-- mehr
        if target_even is not None:
            self.encoder.tx_even = target_even
```

### 2.3 OMNI-Pattern + Block-Switch (unverändert von V1)

```
Block 1: E-TX, O-TX, E-RX, O-RX, E-RX
Block 2: O-TX, E-TX, O-RX, E-RX, O-RX
```

Auto-Switch bei `slot_index 4 → 0`. Kein 80er-Counter.

### 2.4 OMNI-Pause/Resume-Lifecycle (siehe L3, L6, L11)

| Pfad | Aktion |
|---|---|
| QSO start (alle 4 Wege) | `_omni_tx.pause()` + `_omni_was_active_pre_qso=True` |
| QSO end + Queue nicht leer | KEIN Resume (nächstes QSO direkt) |
| QSO end + Queue leer | `_omni_tx.start_with_parity_for_next_slot(...)` + `_was_active_pre_qso=False` |
| HALT | `_omni_tx.stop_omni_tx("manual_halt")` (kein Resume) |
| Mode/Band-Wechsel | `_omni_tx.stop_omni_tx("mode_change"/"band_change")` (kein Resume) |

### 2.5 4-Sequencer-Architektur (unverändert von V1)

Plan A/B/C/D + shared QSO-Subroutine. Wechsel: sofort wenn idle, pending
wenn QSO. Nur HALT bricht laufende QSOs.

---

## 3. Code-Änderungen (V2-präzisiert)

### 3.1 `core/qso_state.py`
- `_send_cq()`: Flag-Pattern (siehe 2.2)
- `__init__`: `self._omni_skip_state_change = False` initialisieren

### 3.2 `core/omni_tx.py`
**Raus:** `block_cycles`-Param, `_cycle_count`, `_pending_switch`,
`qso_active`-Param in `advance()`, `enable()`-Methode.

**Neu:**
- `start_with_parity_for_next_slot(next_is_even: bool)`
- `pause()` / `resume()` / `is_paused()`
- `advance()` ohne Args, Block-Switch bei rollover

**Unverändert:** `should_tx()` (Pattern-Mapping), `disable()`, `stop_omni_tx()`,
`active`-Property, `slot_label`.

### 3.3 `ui/mw_cycle.py`
- `_on_cycle_start`: `if not _omni_tx.is_paused(): _omni_tx.advance()`
  (statt `advance(qso_active=...)`)

### 3.4 `ui/main_window.py`
- `_on_btn_omni_cq_toggled`: `start_with_parity_for_next_slot(next_is_even)`
  ersetzt `enable()`
- `_omni_was_active_pre_qso: bool = False` als Instance-Variable
- `_on_omni_stopped`: unverändert (idempotent stop_cq + `_was_cq=False`)

### 3.5 `ui/mw_qso.py`
- `_on_send_message`: Flag-Pattern (2.2), `calls_made -=1` raus
- `_on_station_clicked`: `if _omni_tx.active: _omni_tx.pause(); _omni_was_active_pre_qso=True`
- `_on_tx_slot_for_partner`: dito (CQ-Reply-Pfad)
- `_on_qso_complete` / `_on_qso_confirmed` / `_on_qso_timeout`: am Ende
  OMNI-Resume via `start_with_parity_for_next_slot` wenn `_omni_was_active_pre_qso`
  UND `_caller_queue` leer

### 3.6 `core/timing.py` (Verifikations-Schritt)
- Pre-V3: `is_even_cycle()`-Existenz prüfen, falls anders → mappen

---

## 4. Akzeptanzkriterien (V2-erweitert)

(V1 §7 AC1-AC11 bleiben)

**AC12 (NEU):** Caller-Queue + OMNI: QSO endet, Queue nicht leer →
nächstes QSO startet sofort (`_process_cq_reply` über `_resume_cq_if_needed`),
OMNI bleibt pausiert.

**AC13 (NEU):** `_omni_skip_state_change`-Flag: bei 2× CQ-Aufruf hintereinander
ist Flag nach 1. Aufruf wieder False (kein Hänger).

**AC14 (NEU):** State-Beweis bei OMNI-RX-Slot: nach `_send_cq()` ist
`qso_sm.state == CQ_WAIT` (oder vor-Wert), nicht `CQ_CALLING`.

---

## 5. Test-Strategie (V2-erweitert)

(V1 §8 Tests bleiben)

**Zusätzlich (4 Tests):**
- `test_omni_skip_state_change_flag_resets`
- `test_send_cq_with_omni_rx_slot_no_state_change`
- `test_omni_pause_on_cq_reply_via_tx_slot_for_partner`
- `test_omni_resume_only_when_caller_queue_empty`

**Geschätzt: ~19 Tests gesamt (statt V1: 15).**

---

## 6. Anti-Liste (V2-erweitert)

(V1 §9 bleibt)

**Zusätzlich:**
- ❌ `calls_made -= 1` im OMNI-Filter behalten (war Pflaster, jetzt obsolet)
- ❌ State-Wechsel auf CQ_CALLING wenn Listener TX skipped
- ❌ Doppelte Setter für `encoder.tx_even` (Listener bleibt Single Source)

---

## 7. R1-Pflicht-Prüfaufträge (V2)

R1 muss explizit prüfen:

1. **L1 Race-Lösung:** Ist Variante B (Flag-Pattern) wirklich Race-frei?
   Kann der Flag zwischen verschiedenen `_send_cq`-Aufrufen verschmieren?
2. **L3/L6/L11 Pause/Resume-Vollständigkeit:** Sind alle QSO-Entry/Exit-Pfade
   abgedeckt? Fehlt einer?
3. **L8 Single Source of Truth:** Ist `encoder.tx_even` wirklich nur an
   einer Stelle gesetzt im OMNI-Pfad?
4. **L13 timing-API:** existiert `is_even_cycle()`? (R1 darf das verifizieren
   wenn `core/timing.py` mitgesendet wird)
5. **AC11/AC14 Bug-Beweis:** ist der Test wirklich aussagekräftig dass der
   Bug gefixt ist?
6. **`_resume_cq_if_needed` + OMNI:** macht es Sinn dass `_was_cq` weiterhin
   in `_resume_cq_if_needed` triggert obwohl OMNI separat resumed wird?
   Doppel-CQ?
7. **Encoder-Thread-Safety:** wenn `_omni_skip_state_change` von GUI-Thread
   gesetzt und GUI-Thread gelesen wird (alles synchron) — kein Lock nötig?
8. **Test für DirectConnection-Verhalten:** wie testen dass `emit()`
   tatsächlich synchron läuft?

---

## 8. Files-Anhang (unverändert von V1)

`core/omni_tx.py` + `core/qso_state.py` + `core/timing.py` + `core/encoder.py`
+ `ui/main_window.py` + `ui/mw_qso.py` + `ui/mw_cycle.py` — alle vollständig.

---

## 9. Was NICHT im Scope (V2 ergänzt)

(V1 §10 bleibt)

**Zusätzlich:**
- ❌ Encoder.transmit-Refactor (Encoder-API bleibt)
- ❌ `tx_started`-Signal-Migration (Variante A wurde verworfen)
- ❌ Threading-Modell-Änderungen

---

## 10. Mike-Designentscheidungen (unverändert)

- Option B (Root Cause heilen) — präzisiert in L1
- Block-Switch automatisch — V2 unverändert
- „Kein Slot verschwenden" — V2 unverändert
- 4-Sequencer + 1 Shared Sub — V2 unverändert
- Nur HALT unterbricht — V2 unverändert
- OMNI Diversity-only — V2 unverändert

---

## 11. V1→V2 Diff-Zusammenfassung

| V1 §  | V2-Änderung | Grund |
|---|---|---|
| §6.1 | Flag-Pattern statt naive Vertauschung | DirectConnection-Race (L1) |
| §6.2 | `enable()` raus, `start_with_parity...` rein | Klärung (L2) |
| §6.3 | `is_paused()` + Pause/Resume-Lifecycle definiert | (L3) |
| §6.4 | Edge-Case `is_even_cycle` dokumentiert | (L4) |
| §6.5 | „Alle Wege" konkret definiert | (L5) |
| §6.6 | `calls_made -= 1` raus | (L10) |
| §7 | +AC12-14 (Queue, Flag, Bug-Beweis) | (L6, L11) |
| §8 | +4 Tests (Flag, Skip-State, Pause, Queue-Resume) | (L15) |

---

## 12. Nächste Schritte

1. R1-Review mit V2 (`tools/deepseek_review.py`, R1-Default)
2. R1-Findings → V3 (Compact-fest)
3. Mike-Freigabe V3
4. Compact #2
5. Implementation (atomare Commits)
6. Final-R1-Review nach Code
7. Field-Test
