# P2.OMNI-REDESIGN — V3 Plan (Compact-fest, R1-V2-Findings eingearbeitet)

**Datum:** 2026-05-09
**Vorgänger:** V1 (`p2_omni_redesign_v1.md`) → V2 (`p2_omni_redesign_v2.md`) → R1-V2-Review (`p2_omni_redesign_r1_v2.md`)
**Stand:** v0.95.22, Tests 1014 grün
**Source of Truth:** `prompts/omni_redesign_notes.md`

---

## 0. Compact-Brief — was V3 erreicht

OMNI-CQ-Loop stirbt nach 2 TX-Slots. Wurzel: `core/qso_state.py:177` setzt
`_set_state(CQ_CALLING)` BEVOR `send_message.emit()`. Bei OMNI-RX-Slot
filtert Listener TX weg, State wurde aber bereits umgeschaltet → State stuck
→ `on_cycle_end` greift nicht mehr → Loop tot.

**V3-Lösung (Variante B Flag-Pattern):** State-Wechsel kommt NACH `emit()`,
Listener kann via Flag `_omni_skip_state_change` den State-Wechsel
unterdrücken wenn TX wegen RX-Slot übersprungen wird.

**Plus Architektur-Refactor:**
- `block_cycles=80`-Counter komplett raus (Diversity-OPERATE_CYCLES-Überrest)
- Block-Switch automatisch bei `slot_index 4→0` Rollover
- Pause/Resume-Lifecycle für OMNI während QSO (4 Entry-Pfade, 3 Exit-Pfade)
- „Kein Slot verschwenden": nächster Slot Even → Block 1, Odd → Block 2
- Singleton-API saubergezogen (`block_cycles`-Param raus)

---

## 1. R1-V2 Findings — Bewertung & Entscheidung

### 1.1 ⛔ KRITISCH (annehmen)

**K1 — `_on_try_replace_pending_tx` ohne OMNI-Pause** (R1 §2)

Bestätigt durch Code-Verifikation `ui/mw_qso.py:727-778`: Slot setzt State zu
TX_REPORT (Z.771), startet QSO (Z.760-766), ruft aber **kein** `_omni_tx.pause()`
und setzt **nicht** `_omni_was_active_pre_qso=True`.

Folge: 4. QSO-Entry-Pfad bleibt während QSO mit OMNI aktiv → Slot-Filter
greift weiter (Reports starten nicht mit "CQ ", werden nicht gefiltert,
QSO läuft → das ist OK), ABER: am QSO-Ende wird `_omni_was_active_pre_qso`
geprüft → False → KEIN Resume. Inkonsistent zu den 3 anderen Entry-Pfaden.

**V3-Entscheidung:** Annehmen. Plus R1-Empfehlung KISS-Helper:

```python
# ui/mw_qso.py — neuer Helper (1× definiert, 4× aufgerufen)
def _pause_omni_if_active(self) -> None:
    """OMNI pausieren + Pre-QSO-Flag setzen wenn OMNI aktiv.
    DRY-Helper für alle 4 QSO-Entry-Pfade.
    """
    if self._omni_tx.active:
        self._omni_tx.pause()
        # _omni_was_active_pre_qso ist auf MainWindow → über self._main_window
        self._main_window._omni_was_active_pre_qso = True
```

Aufruf in:
1. `_on_station_clicked` (Hunt) — V2 hatte Inline
2. `_on_tx_slot_for_partner` (CQ-Reply) — V2 hatte Inline
3. `_on_try_replace_pending_tx` (P1.9 Replace) — **NEU in V3**
4. (kein 4. Pfad — Auto-Hunt nutzt `_on_station_clicked` indirekt)

**Hinweis zu Helper-Pfad:** Falls `_main_window`-Reference in mw_qso nicht
existiert, Pre-Flag direkt in mw_qso (Instanz-Attribut `self._omni_was_active_pre_qso`)
und MainWindow liest es via `self.mw_qso._omni_was_active_pre_qso`.
Implementation muss das im Plan-Mode entscheiden — KISS gewinnt (V2 hatte
es in MainWindow, das bleibt — Helper greift via Parent-Reference).

### 1.2 🟡 SOLLTE — Bewertung

**S1 — `_resume_cq_if_needed` Timing → 1 ungefilterter CQ** (R1 §6)

**ABLEHNEN als R1-Halluzination.**

R1-Behauptung: „qso_state ruft `_resume_cq_if_needed` direkt auf, BEVOR
mw_qso das Signal verarbeitet" (R1 Z.204).

**Code-Beweis Gegenteil:**
- `ui/main_window.py:597-599`:
  ```python
  self.qso_sm.qso_complete.connect(self._on_qso_complete)
  self.qso_sm.qso_confirmed.connect(self._on_qso_confirmed)
  self.qso_sm.qso_timeout.connect(self._on_qso_timeout)
  ```
  Keine explizite ConnectionType → `Qt.AutoConnection` → bei gleichem
  Thread (qso_sm und MainWindow beide GUI-Thread) → `Qt.DirectConnection`.
- `core/qso_state.py:306-307` (Pattern wiederholt sich Z.313-314, 341-342,
  371-372, 388-389, 642-643):
  ```python
  self.qso_timeout.emit(call)        # Z.306 — DirectConnection: SYNCHRON
  self._resume_cq_if_needed()         # Z.307 — läuft erst nach emit-Return
  ```

**Bei DirectConnection:** `emit()` in Z.306 läuft synchron → mw_qso._on_qso_timeout
läuft KOMPLETT (inkl. OMNI-Resume) → kehrt zurück → DANN Z.307
`_resume_cq_if_needed()` → `_send_cq()` → `emit("CQ ...")` → Listener hat OMNI
**bereits resumed** → Slot-Filter greift normal.

**Kein ungefilterter CQ.** R1's Concern entstand vermutlich aus der falschen
Annahme dass Signale per QueuedConnection laufen (was in Multi-Thread-Apps
typisch wäre, aber hier nicht).

**V3-Entscheidung:** S1 verwerfen. Doku-Hinweis im Code:
```python
# core/qso_state.py _resume_cq_if_needed (Top-Kommentar):
# WICHTIG: Aufrufer-Pattern ist immer "qso_*.emit() → _resume_cq_if_needed()".
# Bei DirectConnection (GUI-Thread) läuft mw_qso-Listener SYNCHRON in
# der emit-Zeile (inkl. OMNI-Resume) → _send_cq() in dieser Methode hat
# danach die korrekte OMNI-State-Sicht.
```

**S2 — Singleton `block_cycles`-Parameter komplett raus** (R1 §Weitere L12)

V2 sagte „Parameter ignorieren oder Deprecation". V3 macht's klar:

- `core/omni_tx.py`: Konstruktor-Signatur `OmniTX()` (kein Param mehr)
- `OmniTX.get_instance()` (kein Param mehr)
- Alle Aufrufer-Stellen müssen den Param weglassen

**V3-Code-Verifikations-Pflicht (Pre-Implementation):**
```bash
grep -rn "OmniTX.get_instance\|OmniTX(" \
  core/ ui/ tests/ --include="*.py" \
  | grep -v "^Binary file"
```
Alle Treffer in Implementation auf parameterlosen Aufruf migrieren.

**S3 — AC14-Test als Integrationstest** (R1 §5)

V2-Test `test_send_cq_with_omni_rx_slot_no_state_change` braucht:
- echten `qso_sm` (kein Mock — testen wir gerade)
- gemockten `omni_tx` mit `should_tx` returns `(False, None)`
- gemockte Listener-Kette (`_on_send_message` muss laufen, sonst Flag wird nie gesetzt)

**V3-Test-Strategie:**
```python
# tests/test_p2_omni_redesign.py
def test_send_cq_with_omni_rx_slot_no_state_change():
    """K1-Bug-Beweis: bei OMNI-RX-Slot bleibt State auf CQ_WAIT (nicht CQ_CALLING)."""
    sm = QSOStateMachine(my_call="DA1MHH", my_grid="JN58")
    sm.cq_mode = True

    # Listener emuliert mw_qso._on_send_message bei OMNI-RX-Skip
    def listener(message):
        if message.startswith("CQ "):
            sm._omni_skip_state_change = True  # Flag setzen analog Real-Listener

    sm.send_message.connect(listener)
    sm._set_state(QSOState.CQ_WAIT)

    sm._send_cq()

    assert sm.state != QSOState.CQ_CALLING
    assert sm.state == QSOState.CQ_WAIT  # vor-Wert bleibt
    assert sm._omni_skip_state_change is True  # Flag wurde gesetzt
```

Plus AC13-Test (Flag-Reset zwischen Aufrufen):
```python
def test_omni_skip_state_change_flag_resets():
    """Flag muss bei jedem _send_cq() neu auf False gesetzt werden."""
    sm = QSOStateMachine(my_call="DA1MHH", my_grid="JN58")
    sm.cq_mode = True
    sm._omni_skip_state_change = True  # Vorzustand: True

    # Listener emuliert TX-Slot (kein Skip)
    sm.send_message.connect(lambda m: None)
    sm._set_state(QSOState.CQ_WAIT)

    sm._send_cq()

    assert sm._omni_skip_state_change is False  # zurückgesetzt
    assert sm.state == QSOState.CQ_CALLING       # State-Wechsel hat stattgefunden
```

### 1.3 🟢 KÖNNTE (annehmen — KISS-Kommentare)

**L1 (R1 §1):** Code-Kommentar in `core/qso_state.py _send_cq()`:
```python
# _omni_skip_state_change: Flag wird nur im GUI-Thread (qso_sm) gesetzt
# und gelesen. Listener läuft via DirectConnection synchron im selben
# Thread → kein Lock nötig.
```

**L8 (R1 §3):** Code-Kommentar in `core/encoder.py` an `tx_even`-Property:
```python
# tx_even: wird vor jedem TX gesetzt (CQ-Pfad in _on_send_message,
# Hunt-Pfad in _on_station_clicked, Reply-Pfad in _on_tx_slot_for_partner,
# Replace-Pfad in _on_try_replace_pending_tx). Letzter Setter gewinnt —
# das ist Design-bedingt, jeder Pfad setzt für seinen TX die korrekte
# Parität.
```

**L13 (R1 §4):** Docstring in `core/timing.py is_even_cycle()`:
```python
def is_even_cycle(self) -> bool:
    """True wenn der AKTUELL laufende Zyklus gerade Parität hat.

    NICHT der nächste Zyklus. Für „nächster Slot ist even?" Aufrufer
    invertiert: `next_is_even = not timer.is_even_cycle()`.
    """
    return self.current_cycle_number() % 2 == 0
```

---

## 2. V3-Code-Änderungen (vollständig)

### 2.1 `core/qso_state.py`

```python
# __init__ ergänzen:
self._omni_skip_state_change: bool = False

# _send_cq() — Flag-Pattern (V2 §2.2 unverändert, plus L1-Kommentar):
def _send_cq(self):
    if self._pending_reply is not None:
        self._process_cq_reply()
        return
    msg = f"CQ {self.my_call} {self.my_grid}"
    self._dbg.log("TX", f"Sende: '{msg}'")
    # _omni_skip_state_change: Flag wird nur im GUI-Thread gesetzt/gelesen.
    # Listener läuft via DirectConnection synchron → kein Lock nötig.
    self._omni_skip_state_change = False
    self.send_message.emit(msg)
    if not self._omni_skip_state_change:
        self._set_state(QSOState.CQ_CALLING)
```

```python
# _resume_cq_if_needed — neuer Top-Kommentar (S1-Doku):
def _resume_cq_if_needed(self):
    """Nach Timeout/Hunt: CQ wieder aufnehmen wenn vorher CQ-Modus aktiv war.

    WICHTIG (V3 S1-Doku): Aufrufer-Pattern ist immer
    'qso_*.emit() → _resume_cq_if_needed()'. Bei DirectConnection
    (GUI-Thread) läuft mw_qso-Listener SYNCHRON in der emit-Zeile
    (inkl. OMNI-Resume) → _send_cq() in dieser Methode hat danach die
    korrekte OMNI-State-Sicht (kein ungefilterter CQ).
    """
    ...  # Body unverändert
```

### 2.2 `core/omni_tx.py`

**Raus:**
- `block_cycles`-Param aus `__init__`
- `block_cycles`-Param aus `get_instance`
- `_cycle_count`-Attribut
- `_pending_switch`-Attribut (falls vorhanden)
- `qso_active`-Param aus `advance()`
- `enable()`-Methode (durch `start_with_parity_for_next_slot` ersetzt)

**Neu:**
```python
def start_with_parity_for_next_slot(self, next_is_even: bool) -> None:
    """OMNI aktivieren mit Block-Wahl basierend auf Parität des nächsten Slots.

    next_is_even=True  → Block 1 (E-TX, O-TX, E-RX, O-RX, E-RX) startet bei Even-TX
    next_is_even=False → Block 2 (O-TX, E-TX, O-RX, E-RX, O-RX) startet bei Odd-TX
    """
    self._block = 1 if next_is_even else 2
    self._slot_index = 0
    self._active = True
    self._paused = False

def pause(self) -> None:
    """OMNI während QSO pausieren — _slot_index friert ein."""
    self._paused = True

def resume(self) -> None:
    """OMNI nach QSO fortsetzen — _slot_index läuft weiter."""
    self._paused = False

def is_paused(self) -> bool:
    return self._paused

def advance(self) -> None:
    """Slot-Index inkrementieren. Bei rollover (4→0) Block-Switch automatisch.

    Aufrufer (mw_cycle._on_cycle_start) muss vor advance() prüfen:
      if not omni_tx.is_paused(): omni_tx.advance()
    """
    if not self._active:
        return
    self._slot_index = (self._slot_index + 1) % 5
    if self._slot_index == 0:
        # Rollover → Block-Switch
        self._block = 2 if self._block == 1 else 1
```

**Unverändert:**
- `should_tx()` (Pattern-Mapping)
- `disable()` / `stop_omni_tx(reason)`
- `active`-Property
- `slot_label`

### 2.3 `core/encoder.py`

L8-Kommentar an `tx_even`-Property hinzufügen (siehe §1.3).

### 2.4 `core/timing.py`

L13-Docstring an `is_even_cycle()` (siehe §1.3).

### 2.5 `ui/mw_cycle.py`

```python
# _on_cycle_start — advance ohne qso_active-Param + Pause-Check:
def _on_cycle_start(self) -> None:
    ...  # bestehender Code
    if not self._omni_tx.is_paused():
        self._omni_tx.advance()
```

### 2.6 `ui/main_window.py`

```python
# __init__ — neue Instanz-Variable:
self._omni_was_active_pre_qso: bool = False

# _on_btn_omni_cq_toggled — start_with_parity_for_next_slot statt enable():
@Slot(bool)
def _on_btn_omni_cq_toggled(self, checked: bool) -> None:
    if checked:
        # ... bestehender Pre-Block (Mode-Check, Auto-Hunt-Stop) ...
        next_is_even = not self.timer.is_even_cycle()
        self._omni_tx.start_with_parity_for_next_slot(next_is_even)
        self.qso_sm.start_cq()
    else:
        self._omni_tx.stop_omni_tx("manual_halt")

# _on_omni_stopped — unverändert (idempotent stop_cq + _was_cq=False):
@Slot(str)
def _on_omni_stopped(self, reason: str) -> None:
    self.qso_sm.stop_cq()
    self.qso_sm._was_cq = False
    self.btn_omni_cq.setChecked(False)
```

### 2.7 `ui/mw_qso.py` (Hauptänderungen)

**Helper (DRY für 3 Entry-Pfade):**
```python
def _pause_omni_if_active(self) -> None:
    """K1-Helper: OMNI pausieren + Pre-QSO-Flag setzen wenn OMNI aktiv.
    Aufruf-Stellen: _on_station_clicked, _on_tx_slot_for_partner,
    _on_try_replace_pending_tx.
    """
    if self._omni_tx.active:
        self._omni_tx.pause()
        self._main_window._omni_was_active_pre_qso = True
```

**`_on_send_message` (Flag-Pattern):**
```python
@Slot(str)
def _on_send_message(self, message: str) -> None:
    if message.startswith("CQ "):
        if self._omni_tx.active:
            send_ok, target_even = self._omni_tx.should_tx()
            if not send_ok:
                # RX-Slot: TX skip + State-Wechsel skip
                self.qso_sm._omni_skip_state_change = True
                print(f"[OMNI-TX] RX-Slot → skip CQ ({self._omni_tx.slot_label})")
                return  # KEIN calls_made-- mehr (V2 L10)
            if target_even is not None:
                self.encoder.tx_even = target_even
    # ... bestehender Encoder-Transmit-Pfad
```

**`_on_station_clicked` (Hunt-Pfad — Helper-Aufruf):**
```python
def _on_station_clicked(self, msg) -> None:
    self._pause_omni_if_active()  # K1-Helper
    # ... bestehender Code
```

**`_on_tx_slot_for_partner` (CQ-Reply-Pfad — Helper-Aufruf):**
```python
def _on_tx_slot_for_partner(self, msg, is_courtesy: bool = False) -> None:
    if not is_courtesy:
        self._pause_omni_if_active()  # K1-Helper
    # ... bestehender Code
```

**`_on_try_replace_pending_tx` (P1.9 Replace-Pfad — NEU mit Helper, K1-Fix):**
```python
@Slot(object)
def _on_try_replace_pending_tx(self, msg) -> None:
    if not msg.is_grid:
        return
    # K1: OMNI während Replace-QSO pausieren
    self._pause_omni_if_active()
    # ... bestehender Code (request_replace, State-Wechsel etc.)
```

**`_on_qso_complete` / `_on_qso_confirmed` / `_on_qso_timeout` (Resume-Pfade):**
```python
def _on_qso_complete(self, qso) -> None:
    # ... bestehender Code (ADIF, Cleanup) ...
    self._maybe_resume_omni()  # NEU am Ende

def _on_qso_confirmed(self, qso) -> None:
    # ... bestehender Code ...
    self._maybe_resume_omni()  # NEU am Ende

def _on_qso_timeout(self, call: str) -> None:
    # ... bestehender Code ...
    self._maybe_resume_omni()  # NEU am Ende

def _maybe_resume_omni(self) -> None:
    """Resume-Helper: OMNI nur fortsetzen wenn vor QSO aktiv UND
    Caller-Queue leer (sonst startet nächstes QSO sofort).
    """
    if not self._main_window._omni_was_active_pre_qso:
        return
    if self.qso_sm._caller_queue:
        return  # nächstes QSO direkt anschließen, OMNI bleibt pausiert
    next_is_even = not self.timer.is_even_cycle()
    self._omni_tx.start_with_parity_for_next_slot(next_is_even)
    self._main_window._omni_was_active_pre_qso = False  # Reset
```

**`_on_cancel` (HALT — bestehende Logik aus v0.95.22 bleibt):**
```python
def _on_cancel(self) -> None:
    # bestehender Code aus P1.OMNI-START v0.95.22 — HALT stoppt OMNI
    if self._omni_tx.active:
        self._omni_tx.stop_omni_tx("manual_halt")
    # ... rest bestehender Code
```

---

## 3. Akzeptanzkriterien (V3 — 15 ACs)

V1 §7 hatte AC1-AC11. V2 ergänzte AC12-14. V3 ergänzt AC15:

| AC | Beschreibung |
|---|---|
| AC1 | Block 1: E-TX, O-TX, E-RX, O-RX, E-RX (slot 0..4) |
| AC2 | Block 2: O-TX, E-TX, O-RX, E-RX, O-RX (slot 0..4) |
| AC3 | `advance()` rollover 4→0 wechselt Block automatisch |
| AC4 | OMNI pausiert während QSO (alle 4 Entry-Pfade) — `is_paused()=True` |
| AC5 | OMNI resumed nach QSO mit korrekter Parität (next_is_even) |
| AC6 | OMNI resumed NICHT wenn Caller-Queue nicht leer |
| AC7 | HALT (`_on_cancel`) stoppt OMNI ohne Resume |
| AC8 | Mode-Wechsel zu Normal stoppt OMNI |
| AC9 | Band-Wechsel stoppt OMNI |
| AC10 | OMNI-Toggle aus Diversity zeigt Button (sichtbar) |
| AC11 | `block_cycles=80` ist aus dem Code raus (kein Counter mehr) |
| AC12 | Caller-Queue + OMNI: QSO endet, Queue nicht leer → nächstes QSO startet sofort, OMNI bleibt pausiert |
| AC13 | `_omni_skip_state_change`-Flag: bei 2× CQ-Aufruf hintereinander ist Flag nach 1. Aufruf wieder False (kein Hänger) |
| AC14 | State-Beweis bei OMNI-RX-Slot: nach `_send_cq()` mit Listener-Skip ist `qso_sm.state == CQ_WAIT` (oder vor-Wert), nicht `CQ_CALLING` |
| **AC15 (NEU V3)** | **K1-Beweis:** P1.9 Replace-Pfad (`_on_try_replace_pending_tx`) ruft `_omni_tx.pause()` und setzt `_omni_was_active_pre_qso=True` wenn OMNI aktiv |

---

## 4. Test-Strategie (V3 — 20 Tests)

V2 hatte 19 Tests. V3 ergänzt 1 Test für K1:

| # | Test | Datei |
|---|---|---|
| T1 | `test_block_1_pattern` (E-TX, O-TX, E-RX, O-RX, E-RX) | tests/test_p2_omni_redesign.py |
| T2 | `test_block_2_pattern` (O-TX, E-TX, O-RX, E-RX, O-RX) | dito |
| T3 | `test_block_switch_on_rollover` (slot 4→0 → Block-Switch) | dito |
| T4 | `test_start_with_parity_next_even_block_1` | dito |
| T5 | `test_start_with_parity_next_odd_block_2` | dito |
| T6 | `test_pause_freezes_slot_index` | dito |
| T7 | `test_resume_after_pause` | dito |
| T8 | `test_advance_skipped_when_paused` (mw_cycle Pre-Check) | dito |
| T9 | `test_send_cq_with_omni_rx_slot_no_state_change` (AC14) | dito |
| T10 | `test_omni_skip_state_change_flag_resets` (AC13) | dito |
| T11 | `test_omni_pause_on_station_clicked` (Hunt-Entry) | dito |
| T12 | `test_omni_pause_on_cq_reply_via_tx_slot_for_partner` (CQ-Reply-Entry) | dito |
| **T13** | **`test_omni_pause_on_try_replace_pending_tx` (AC15, K1-NEU)** | **dito** |
| T14 | `test_omni_resume_after_qso_complete_empty_queue` | dito |
| T15 | `test_omni_resume_after_qso_confirmed_empty_queue` | dito |
| T16 | `test_omni_resume_after_qso_timeout_empty_queue` | dito |
| T17 | `test_omni_no_resume_with_caller_queue_pending` (AC12) | dito |
| T18 | `test_halt_stops_omni_no_resume` (AC7) | dito |
| T19 | `test_block_cycles_constant_removed` (AC11 — grep-Check oder Constant-Test) | dito |
| T20 | `test_get_instance_no_block_cycles_param` (S2 — Singleton-API) | dito |

**Erwartet:** Tests 1014 → 1034 (+20 NEU).

**Verifikations-Tests anpassen (falls vorhanden):**
- Bestehende OMNI-Tests die `enable()` oder `block_cycles` referenzieren →
  auf neue API migrieren oder löschen (V3-Code-Verifikations-Pflicht §2.2).

---

## 5. Anti-Liste (V3)

V2 §6 bleibt. V3 ergänzt nichts.

❌ **NICHT machen:**
- `calls_made -= 1` im OMNI-Filter behalten (war Pflaster, durch Flag-Pattern obsolet)
- State-Wechsel auf CQ_CALLING wenn Listener TX skipped
- Doppelte Setter für `encoder.tx_even` (Listener bleibt Single Source pro Pfad)
- `block_cycles=80` als Param behalten (unaufgeräumt, Migration unklar)
- `_resume_cq_if_needed` mit OMNI-Wissen anreichern (saubere Trennung qso_state vs OMNI)
- Tests mit Dummy-Mock für `omni_tx` der `should_tx` nicht wirklich filtert (AC14-Beweis dann wertlos)
- 3D-Globe für OMNI-Slot-Visualisierung (Hobby-Tool, KISS, Out-of-Scope)

---

## 6. Mike-Designentscheidungen (unverändert)

- **Option B:** Root Cause heilen (Flag-Pattern), kein Pflaster
- **Block-Switch automatisch:** bei `slot_index 4→0` rollover, KEIN 80-Counter
- **„Kein Slot verschwenden":** Block-Wahl per next-slot-Parität
- **4-Sequencer-Architektur:** Plan A/B/C/D + shared QSO-Subroutine
- **QSO ist heilig:** nur HALT unterbricht
- **OMNI Diversity-only:** Mode-Wechsel zu Normal stoppt automatisch

---

## 7. V2 → V3 Diff-Zusammenfassung

| V2 § | V3-Änderung | Grund |
|---|---|---|
| §3.5 | `_on_try_replace_pending_tx` bekommt `_pause_omni_if_active()` | R1-K1 (4. Entry-Pfad) |
| §3.5 | DRY-Helper `_pause_omni_if_active()` für 3 Entry-Pfade | R1-Empfehlung KISS |
| §3.5 | DRY-Helper `_maybe_resume_omni()` für 3 Exit-Pfade | KISS-Konsistenz mit Pause-Helper |
| §3.2 | `block_cycles`-Param explizit raus aus `__init__` + `get_instance` | R1-S2 (klarer als „ignorieren") |
| §3.6 | L13-Docstring an `is_even_cycle()` | R1-S3 Kosmetik |
| §3.3 | L8-Kommentar an `encoder.tx_even` | R1-S3 Kosmetik |
| §3.1 | L1-Kommentar an `_omni_skip_state_change` + `_resume_cq_if_needed` | R1-S3 Kosmetik + S1-Doku |
| §4 | +AC15 (K1-Beweis) | R1-K1 |
| §5 | +T13 (`test_omni_pause_on_try_replace_pending_tx`) | R1-K1 |
| §5 | +T20 (`test_get_instance_no_block_cycles_param`) | R1-S2 |
| — | S1 als R1-Halluzination dokumentiert (DirectConnection-Beweis) | Code-Verifikation `main_window.py:597-599` |

---

## 8. Verifikations-Schritte vor Implementation

1. **Code-grep `OmniTX.get_instance|OmniTX(`** — alle Aufrufer enumerieren,
   sicherstellen dass `block_cycles`-Migration vollständig
2. **Code-grep `enable\(` in omni_tx-Pfad** — alte Aufrufer auf
   `start_with_parity_for_next_slot` migrieren
3. **Code-grep `block_cycles|_cycle_count|_pending_switch`** — Reste finden
4. **Code-grep `is_even_cycle`** — Aufrufer in mw_qso/main_window prüfen
5. **Bestehende OMNI-Tests:** `tests/test_*omni*.py` Liste durchgehen,
   API-Migrationen anpassen

---

## 9. Files-Anhang (für Final-R1 nach Code)

`core/omni_tx.py` + `core/qso_state.py` + `core/timing.py` + `core/encoder.py`
+ `ui/main_window.py` + `ui/mw_qso.py` + `ui/mw_cycle.py` + neue Tests in
`tests/test_p2_omni_redesign.py`.

---

## 10. Was NICHT im Scope

V1 §10 + V2 §9 bleibt.

❌ Encoder.transmit-Refactor (Encoder-API bleibt)
❌ `tx_started`-Signal-Migration (Variante A wurde verworfen — Thread-Race)
❌ Threading-Modell-Änderungen
❌ OMNI-Visualisierung (Slot-Pattern als UI-Kachel) — separates Feature
❌ Statistik-Logging für OMNI-Slot-Effizienz — Hobby-Tool, Out-of-Scope

---

## 11. Risikoliste (V3)

| # | Risiko | Mitigation |
|---|---|---|
| R1 | `_pause_omni_if_active()` Helper-Pfad hat falsche `_main_window`-Reference | Plan-Mode entscheidet: Pre-Flag in mw_qso oder MainWindow. Test T11/T12/T13 deckt beide Pfade ab |
| R2 | DirectConnection-Annahme bricht in Zukunft (Multi-Thread-Refactor) | L1-Kommentar dokumentiert die Annahme. Bei Refactor explizit prüfen |
| R3 | Bestehende Tests die `enable()` oder `block_cycles` mocken brechen | §8.5 Verifikation zwingt Migration vor Tests-Run |
| R4 | OMNI-Toggle 2× schnell hintereinander (Reentrancy) | V2 L14 als ✅ ACK, GUI-Thread synchron |
| R5 | Field-Test deckt einen 5. Entry-Pfad auf den V3 nicht abdeckt | Final-R1 Code-Review nach Implementation, Mike-Field-Test |
| R6 | `_caller_queue` wird gefüllt während QSO endet (Race) | V2 L6 als ✅ — Filter im _on_send_message ist GUI-Thread synchron |
| R7 | `start_with_parity_for_next_slot` aus Resume-Pfad während OMNI noch nicht ganz pausiert war | Idempotent: `_active=True` + `_paused=False` setzt sauber neu |

---

## 12. Nächste Schritte

1. **Mike-Freigabe V3** ✅/❌
2. **Compact #3** (vor Implementation, Kontext-Schoner)
3. **Implementation in atomaren Commits:**
   - Commit 1: `core/omni_tx.py` Refactor (block_cycles raus, neue API)
   - Commit 2: `core/qso_state.py` Flag-Pattern + Doku
   - Commit 3: `core/timing.py` + `core/encoder.py` Doku-Kommentare
   - Commit 4: `ui/mw_qso.py` Helper + 3 Entry-Pfade + 3 Exit-Pfade
   - Commit 5: `ui/main_window.py` + `ui/mw_cycle.py` Anpassungen
   - Commit 6: Tests (`tests/test_p2_omni_redesign.py`)
   - Commit 7: APP_VERSION 0.95.22 → 0.95.23 + Doku (HISTORY/HANDOFF/CLAUDE/Memory)
4. **Final-R1 Code-Review** (selber R1-Befehl wie V2)
5. **Field-Test mit Mike** (FlexRadio, live OMNI-CQ-Loop > 5 Slots)
6. **Push** (zusammen mit v0.95.16-22 + P2-Tool + P3)

---

## 13. R1-Befehl für Final-R1 nach Implementation

```bash
cd "/Users/mikehammerer/Documents/KI N8N Projekte/FT8/SimpleFT8"
cat prompts/p2_omni_redesign_v3.md | ./venv/bin/python3 tools/deepseek_review.py \
  core/omni_tx.py core/qso_state.py core/timing.py core/encoder.py \
  ui/main_window.py ui/mw_qso.py ui/mw_cycle.py \
  tests/test_p2_omni_redesign.py \
  > /tmp/r1_omni_v3_final.txt
```

---

## 14. Trigger-Phrasen für nach Compact #3

- „weiter mit OMNI-Redesign Code" → V3 lesen → Plan-Mode → atomare Commits
- „OMNI-Redesign Final-R1" → R1-Befehl §13 ausführen
