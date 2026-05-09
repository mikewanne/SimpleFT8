# P2.OMNI-REDESIGN — Vollständiger Session-Kontext (Compact-fest)

**Datum:** 2026-05-09
**Session-ID:** 7ef701a4-609c-4b40-b4f9-620690f1924c
**Zweck:** Komplette Sicherung ALLER Erkenntnisse, Code-Verifikationen,
Mike-Entscheidungen vor Compact #2. Kein Detail soll verloren gehen.

---

## 1. Datei-Inventar (alles in `prompts/`)

| Datei | Inhalt | Größe |
|---|---|---|
| `omni_redesign_notes.md` | Source of Truth, 14 Sektionen, Compact-fest | 12.8 KB |
| `p2_omni_redesign_v1.md` | V1 — initialer Plan-Entwurf | 18.9 KB |
| `p2_omni_redesign_v2.md` | V2 — Self-Review mit L1-L15 Lessons | 21.4 KB |
| `p2_omni_redesign_r1_lauf1_full.md` | 1. R1-Lauf, vollständig erhalten | 5.7 KB |
| `p2_omni_redesign_r1_lauf2_truncated.md` | 2. R1-Lauf, truncated 1051 Bytes | 1.1 KB |
| `p2_omni_sequencer_v1.md` | Vorgänger-Plan (verworfen, hier zur Doku) | 4.7 KB |

Plus alte v0.78-OMNI-Dateien:
- `omni_v1.md`, `omni_v2.md`, `omni_v3.md` (April 2026, v0.78 Implementierung)
- `p1_omni_start_v1/v2/v3.md` (Mai 2026, v0.95.22 Toggle-Bug)

---

## 2. Bug-Diagnose (verifiziert)

### 2.1 Symptom (Mike-Field-Test 09.05.2026)

Klick auf `btn_omni_cq` → CQ wird gesendet → sofort Antwort erhalten →
**falsch**, denn im OMNI-Pattern Block 1 ist Slot 1 (nach Even-TX) ein
**zweites TX-CQ auf Odd**, kein RX.

Pattern Block 1: `Even-TX, Odd-TX, Even-RX, Odd-RX, Even-RX`

### 2.2 Root Cause (Code-verifiziert)

**Datei:** `core/qso_state.py`
**Zeilen:** 164-178

```python
def _send_cq(self):
    """CQ-Ruf senden."""
    if self._pending_reply is not None:
        print(f"[QSO] _send_cq: pending {self._pending_reply.caller} "
              f"→ process statt CQ")
        self._process_cq_reply()
        return
    self._pending_reply = None  # Alte Antwort verwerfen
    msg = f"CQ {self.my_call} {self.my_grid}"
    self._dbg.log("TX", f"Sende: '{msg}'")
    self._set_state(QSOState.CQ_CALLING)   # ← Z.177 BUG: State VOR emit
    self.send_message.emit(msg)             # ← Z.178
```

**Listener-Pfad:** `ui/main_window.py:596`
```python
self.qso_sm.send_message.connect(self._on_send_message)
# ohne explizite Connection-Type → Qt.AutoConnection
# beide im GUI-Thread → wird zu Qt.DirectConnection → emit() SYNCHRON
```

**Listener:** `ui/mw_qso.py:299-336` `_on_send_message`
```python
@Slot(str)
def _on_send_message(self, message: str):
    if not self.presence_can_tx():
        return
    if message.startswith("CQ "):
        self._has_sent_cq = True
        if self._omni_tx.active:
            is_even = self.timer.is_even_cycle()
            send_ok, target_even = self._omni_tx.should_tx()
            if not send_ok:
                # RX-Slot: CQ NICHT senden
                print(f"[OMNI-TX] RX-Slot → skip CQ ...")
                if hasattr(self.qso_sm, 'qso') and hasattr(self.qso_sm.qso, 'calls_made'):
                    self.qso_sm.qso.calls_made = max(0, self.qso_sm.qso.calls_made - 1)
                return  # ← early return, transmit() läuft NICHT
            # ... (nur bei TX-Slot weiter)
            if target_even is not None:
                self.encoder.tx_even = target_even
    if self.encoder.is_transmitting:
        self.encoder.abort()
    self.encoder.transmit(message)  # ← nur hier echter TX
```

**Bug-Ablauf:**
1. `_send_cq()` setzt State auf `CQ_CALLING` (Z.177)
2. `_send_cq()` emittiert `send_message` (Z.178)
3. `_on_send_message` läuft synchron, prüft OMNI-Slot
4. Bei OMNI-RX-Slot: early return ohne `transmit()`
5. `tx_finished` feuert nie → `on_message_sent()` wird nie aufgerufen
6. State bleibt `CQ_CALLING` (statt `CQ_WAIT`)
7. `on_cycle_end()` (Z.317-324) prüft `if state == QSOState.CQ_WAIT` → false
8. `_send_cq()` wird nie wieder aufgerufen → **OMNI-Loop tot**

---

## 3. Mike's Designentscheidungen (chronologisch, mit Datum)

### 3.1 09.05.2026 — Voller Refactor, kein Pflaster

**Mike:** „ich mache doch jetzt kein pflaster"
**Konsequenz:** Nicht nur `_send_cq()` patchen, sondern OMNI-Architektur
komplett überarbeiten.

### 3.2 09.05.2026 — block_cycles=80 raus

**Mike:** „wir messen nichts mehr nach 80 zyclen wir messen diverity nach
einer stunde"
**Verifikation:** v0.93 (HISTORY 04.05.2026) hat `OPERATE_CYCLES`-Konstante
durch `REMEASURE_INTERVAL_SECONDS=3600` (zeitbasiert) ersetzt. Der
`block_cycles=80`-Default in `core/omni_tx.py` war Überrest.
**Konsequenz:** Block-Switch automatisch jeden 5-Slot-Cycle, kein Counter.

### 3.3 09.05.2026 — Korrektes OMNI-Pattern

**Mike:** „even,odd senden — even,odd,even hören und dann umgekehrt"
**Pattern:**
```
Block 1: Even-TX, Odd-TX, Even-RX, Odd-RX, Even-RX
Block 2: Odd-TX,  Even-TX, Odd-RX,  Even-RX, Odd-RX
```

### 3.4 09.05.2026 — „Kein Slot verschwenden"

**Mike:** „logik wir verschewenden keinen slot, wenn das qso auf even
beendet wurde warum soll ich dann auf odd nicht machen und auch even
wieder anfangen dann kann ich auf odd anfangen und verliere keine 15
sekunden"
**Konsequenz:** Bei Activate + post-QSO-Resume:
- Nächster Slot Even → Block 1 (Pos 0=Even-TX)
- Nächster Slot Odd → Block 2 (Pos 0=Odd-TX)

### 3.5 09.05.2026 — 4-Sequencer-Architektur

**Mike:** „haben wir wie besprochen ein programmteil für omni für normal
für huntmodus für stationrufen?"
**Architektur:** Plan A (Normal-CQ) + Plan B (OMNI-CQ) + Plan C (Auto-Hunt)
+ Plan D (Manual) + shared QSO-Subroutine.

### 3.6 09.05.2026 — Nur HALT bricht QSO

**Mike:** „es kann nicht während des qso duchlaufen ich muss sobald ein
qso startet den normalen ablauf machen"
**Konsequenz:** OMNI pausiert bei QSO-Start (slot_index frozen), QSO nutzt
shared Subroutine, nach QSO-Ende: OMNI-Resume mit korrekter Parität.

### 3.7 09.05.2026 — Option B (Root Cause heilen)

**Mike:** „b sehe ich auch so"
**Bedeutung:** State-Wechsel in `_send_cq()` erst NACH `send_message.emit()`,
KEIN `auto_cq_enabled`-Flag.
**ABER:** V2-L1 hat enthüllt — naive Vertauschung funktioniert nicht
(siehe §4).

### 3.8 09.05.2026 — Plan-Reihenfolge

**Mike:** „ja so machen wir es genau so beste vorraussetzungen schaffen"
(zur Antwort: sichern → Compact #1 → V1→V2→R1→V3 → Mike-Freigabe →
Compact #2 → Implementation)
**Konsequenz:** Volle Workflow-Disziplin trotz Architektur-Komplexität.

---

## 4. V2-L1 KRITISCH-Befund (DirectConnection Race-Check)

### 4.1 Was V1 vorgeschlagen hat (NAIV, würde NICHT funktionieren)

```python
# core/qso_state.py _send_cq
self.send_message.emit(msg)              # zuerst
self._set_state(QSOState.CQ_CALLING)     # danach
```

### 4.2 Warum es nicht funktioniert

**Qt-Connection-Mechanik:**
- `connect(self._on_send_message)` → ohne Type-Argument → `Qt.AutoConnection`
- Bei gleichem Thread (qso_sm + mw_qso beide GUI) → `Qt.DirectConnection`
- `emit()` läuft **synchron**: ruft alle verbundenen Slots auf, blockiert
  bis alle returnen, kehrt dann zurück
- Egal ob Listener `return` macht oder nicht — `emit()` kehrt zurück, und
  dann läuft die nächste Code-Zeile

**Folge:** `_set_state(CQ_CALLING)` läuft IMMER nach `emit()`, auch wenn
Listener TX skipped → Bug bleibt exakt wie zuvor.

### 4.3 V2-Lösung: Flag-Pattern (Variante B)

```python
# core/qso_state.py _send_cq (V2-Version)
def _send_cq(self):
    if self._pending_reply is not None:
        self._process_cq_reply()
        return
    msg = f"CQ {self.my_call} {self.my_grid}"
    self._dbg.log("TX", f"Sende: '{msg}'")
    self._omni_skip_state_change = False     # NEU: Flag reset
    self.send_message.emit(msg)               # Listener läuft synchron
    if not self._omni_skip_state_change:      # NEU: Flag check
        self._set_state(QSOState.CQ_CALLING)
```

```python
# ui/mw_qso.py _on_send_message (V2-Version)
if message.startswith("CQ "):
    if self._omni_tx.active:
        send_ok, target_even = self._omni_tx.should_tx()
        if not send_ok:
            # RX-Slot: TX skip + State-Wechsel skip
            self.qso_sm._omni_skip_state_change = True   # NEU
            print(f"[OMNI-TX] RX-Slot → skip CQ")
            return                                        # KEIN calls_made-- mehr
        if target_even is not None:
            self.encoder.tx_even = target_even
```

### 4.4 Verworfene Alternativen

**Variante A: State-Wechsel via `tx_started`-Listener**
- `tx_started.emit` läuft im Encoder-Thread (`core/encoder.py:344`)
- Listener via `Qt.AutoConnection` würde QueuedConnection → asynchron
- Race mit on_cycle_end-Trigger im GUI-Thread möglich
- Verworfen wegen Thread-Komplexität

**Variante C: Listener setzt State direkt**
- `_on_send_message` ruft `qso_sm._set_state(CQ_CALLING)` nach `transmit()`
- Coupling zwischen UI-Layer und State-Machine
- Pattern existiert (Z.771 `_on_try_replace_pending_tx`), aber unschön
- Verworfen wegen Architektur-Sauberkeit

**Variante B (gewählt) Vorteile:**
- Minimal invasiv (1 Flag, 2 Stellen)
- Race-frei (synchron im GUI-Thread)
- Dichtest an Mike's Wortlaut „erst emit, dann _set_state"
- Defense-in-Depth (Flag wird bei jedem Aufruf reset)

---

## 5. Code-Verifikationen (alle gelesen)

### 5.1 `core/qso_state.py` (~700 Zeilen)
- Z.49-63: `QSOState`-Enum (IDLE, CQ_CALLING, CQ_WAIT, TX_CALL,
  WAIT_REPORT, TX_REPORT, WAIT_RR73, TX_RR73, WAIT_73, TX_73_COURTESY,
  LOGGING, TIMEOUT)
- Z.71-85: `QSOData`-Dataclass (their_call, their_grid, their_snr,
  our_snr, freq_hz, start_time, timeout_cycles, max_timeout, calls_made,
  max_calls, rr73_retries, wait_73_retries, courtesy_73_sent)
- Z.98-108: Signals (state_changed, send_message, qso_complete,
  qso_confirmed, qso_timeout, tx_slot_for_partner, caller_queued,
  queue_changed, try_replace_pending_tx)
- Z.144-146: `set_last_snr` — aus mw_cycle.py:793 pro Decoder-Message
- Z.150-156: `start_cq` — Pre-Cond `state in (IDLE, CQ_WAIT)`, ruft `_send_cq`
- Z.158-162: `stop_cq` — `cq_mode=False` + State auf IDLE wenn aktuell CQ
- **Z.164-178:** `_send_cq` — **Bug-Lokation**, Defense-in-Depth Z.169-173
  für `_pending_reply`
- Z.180-242: `_process_cq_reply` — Z.214 `snr = msg.snr` (P1.8 Fix)
- Z.246-292: `start_qso` — Hunt-Pfad mit `their_snr=msg.snr` (P1.HUNT-SNR)
- Z.296-308: `on_cycle_end` — 3-Min-Gesamttimeout
- **Z.317-324:** `on_cycle_end` CQ_WAIT-Branch — `if state == QSOState.CQ_WAIT
  and timeout_cycles >= 1 and cq_mode: _send_cq()` — der Pfad der bei Bug
  nicht mehr greift
- Z.344-390: `on_decoder_finished` — WAIT_REPORT/WAIT_RR73 Retry
- **Z.392-408:** `_resume_cq_if_needed` — ruft `_send_cq()` auf (würde mit
  Option A `auto_cq_enabled`-Flag konfligieren — Option B löst das auch)
- Z.412-... `on_message_sent` — State-Wechsel nach TX-Ende

### 5.2 `core/omni_tx.py` (~250 Zeilen)
- Z.78-105: `should_tx()` — `(should_send, target_is_even)` aus Pattern-Tabelle
- Z.107-126: `advance(qso_active=False)` — `_slot_index += 1 % 5`,
  `_cycle_count`, Block-Switch bei `_cycle_count >= block_cycles`
- Z.108: `block_cycles = 80` Default — **Mike will raus**
- Singleton-Inkonsistenz: `get_instance(block_cycles=40)` vs Default 80
  (Mike-Codereview)

### 5.3 `ui/mw_qso.py` (~800 Zeilen)
- **Z.54-72:** `_on_tx_started(message, tx_even, slot_start_ts)` — wird
  vom Encoder gerufen NACH `ptt_on()`, BEVOR Audio-Stream
- Z.75-... `_on_station_clicked` — Hunt-Klick-Pfad (P1.13 + P1.14)
- **Z.299-336:** `_on_send_message` — OMNI-Filter
- Z.706-724: `_on_tx_slot_for_partner(msg)` — CQ-Reply-Pfad,
  `encoder.tx_even = not their_even`
- **Z.727-778:** `_on_try_replace_pending_tx(msg)` — P1.9 Pattern,
  ruft `qso_sm._set_state(QSOState.TX_REPORT)` direkt auf

### 5.4 `ui/main_window.py` (~1500 Zeilen)
- **Z.596:** `self.qso_sm.send_message.connect(self._on_send_message)`
- **Z.680-712:** `_on_btn_omni_cq_toggled(checked)` — P1.OMNI-START-Logik
- **Z.714-738:** `_on_omni_stopped(reason)` — idempotent stop_cq +
  `_was_cq=False`

### 5.5 `core/encoder.py` (Auszug)
- Z.45: `tx_started = Signal(str, bool, float)`
- **Z.344:** `self.tx_started.emit(message, _tx_even, next_boundary)` —
  läuft im `_tx_worker_inner`-Thread
- Z.355: `self.tx_finished.emit()`

### 5.6 `ui/mw_radio.py`
- Z.65-69: `tx_started.connect(...)` und `_on_tx_started`-Connect

### 5.7 NICHT geprüft (V3-Pflicht)
- `core/timing.py` — `is_even_cycle()` Existenz + Semantik
- `ui/mw_cycle.py` — Pre-Cond-Check für `_omni_tx.advance(qso_active=...)`
- Aufrufer von `OmniTX.get_instance(...)` — Singleton-Konsistenz

---

## 6. R1-Lauf 1 (vollständig erhalten — `p2_omni_redesign_r1_lauf1_full.md`)

### Findings angenommen:
- **BUG-1:** `should_tx()` MUSS vor `advance()` (advance inkrementiert sofort)
- **BUG-2:** AC7-Scope-Widerspruch (Block-Wechsel out-of-scope) → AC raus
- **RISK-3:** `omni_drive_cq()` cq_mode-Guard
- **HINT-2:** `_omni_target_even`-Reset bei `_pending_reply`-Pfad

### Findings abgelehnt:
- RISK-2 (Sequenzgrafik) → Doku-Kommentar reicht
- IMPROVEMENT-1 (start_cq mit target_even) → Mike will klare Trennung
- HINT-1 (Files-Größe) → war bewusst

### Findings offen → in V2 als Mike-Entscheidung:
- **RISK-1:** Root Cause heilen statt Flag → **Mike: Option B**

---

## 7. R1-Lauf 2 (truncated, 1051 Bytes — `p2_omni_redesign_r1_lauf2_truncated.md`)

Nur **BUG-3** erhalten:
- `_resume_cq_if_needed` ruft `_send_cq()` auf → bei Option A würde Flag
  blockieren → tot. **Bei Option B (Mike-Entscheidung) entfällt das.**

Truncation: `out=8000` Tokens, aber nur ~1000 Zeichen gespeichert.
**Mitigation:** R1 nach Compact #2 komplett neu reviewen.

---

## 8. R1-Befehl für nach Compact #2

```bash
cd "/Users/mikehammerer/Documents/KI N8N Projekte/FT8/SimpleFT8"
cat prompts/p2_omni_redesign_v2.md | ./venv/bin/python3 tools/deepseek_review.py \
  core/omni_tx.py \
  core/qso_state.py \
  core/timing.py \
  core/encoder.py \
  ui/main_window.py \
  ui/mw_qso.py \
  ui/mw_cycle.py \
  > /tmp/r1_omni_v2.txt
```

**Wichtig:** ALLE Files vollständig anhängen
(Lesson `feedback_deepseek_partial_files_hallucination.md`).

**Falls Truncation wieder auftritt** (`out=8000` Tokens erreicht):
- Output kürzen / aufteilen
- Nochmal mit selektiveren Files
- ODER: V3 ohne komplette R1-Findings, nur mit Lauf-1 (vollständig)

---

## 9. V2-L1-L15 Lessons (vollständige Tabelle)

| Nr. | Lesson | Schwere | V2-Lösung |
|---|---|---|---|
| L1 | Naive emit/_set_state-Vertauschung fixt Bug NICHT | ⛔ KRITISCH | Flag-Pattern `_omni_skip_state_change` |
| L2 | `enable()` vs `start_with_parity_for_next_slot()` | ✅ EINGEARBEITET | enable raus, neue Methode rein |
| L3 | `is_paused()` + Pause/Resume-Lifecycle | ⛔ WICHTIG | 6-Pfad-Tabelle (Start + Ende + HALT) |
| L4 | Klick exakt am Slot-Boundary | 🟡 EDGE | `is_even_cycle()` invertiert reicht |
| L5 | „Alle Wege ins/aus QSO" konkretisiert | ✅ | siehe L3-Tabelle |
| L6 | Caller-Queue + OMNI | ⛔ WICHTIG | Pause in `_on_tx_slot_for_partner`, Resume nur bei leerer Queue |
| L7 | Auto-Hunt-Konflikt | 🟡 KÖNNTE | Sequence im GUI-Thread → kein Race ✅ ACK |
| L8 | `encoder.tx_even` doppelter Setter | ⛔ WICHTIG | Single Source bleibt Listener |
| L9 | Block-Switch-Test ohne Echtzeit | ⛔ WICHTIG | rein arithmetisch via 5× advance() |
| L10 | `calls_made-=1`-Decrement | 🟡 KÖNNTE | RAUS (war Pflaster, jetzt obsolet) |
| L11 | `_resume_cq_if_needed` + OMNI-Resume | ⛔ WICHTIG | OMNI-Resume in mw_qso, nicht qso_state |
| L12 | Singleton-Pattern omni_tx | ✅ EINGEARBEITET | block_cycles aus Konstruktor |
| L13 | `is_even_cycle()` Verifikation | ⛔ WICHTIG | V3-Pflicht: grep + Doku lesen |
| L14 | Reentrancy bei Mehrfach-Toggle | 🟡 KÖNNTE | GUI-Thread synchron → kein Race ✅ ACK |
| L15 | Caller-Queue + OMNI Tests-Lücke | ⛔ TESTS | +3 Tests in V2 §5 ergänzt |

---

## 10. Geplante Code-Änderungen (Files-Liste)

### `core/qso_state.py`
- `__init__`: `self._omni_skip_state_change = False` Initial
- `_send_cq()`: Flag-Pattern (V2 §2.2)

### `core/omni_tx.py` (Refactor)
**Raus:** `block_cycles`-Param, `_cycle_count`, `_pending_switch`,
`qso_active`-Param in `advance()`, `enable()`-Methode.

**Neu:**
- `start_with_parity_for_next_slot(next_is_even: bool)` — Block-Wahl + Init
- `pause()` / `resume()` / `is_paused()` — QSO-Pause-Lifecycle
- `advance()` ohne Args, Block-Switch auto bei rollover

**Unverändert:** `should_tx()`, `disable()`, `stop_omni_tx()`, `active`,
`slot_label`.

### `ui/mw_cycle.py`
- `_on_cycle_start`: `if not _omni_tx.is_paused(): _omni_tx.advance()`
  (statt `advance(qso_active=...)`)

### `ui/main_window.py`
- `_on_btn_omni_cq_toggled`: `start_with_parity_for_next_slot(next_is_even)`
- `_omni_was_active_pre_qso: bool = False` Instance-Var
- `_on_omni_stopped`: unverändert

### `ui/mw_qso.py`
- `_on_send_message`: Flag-Pattern, `calls_made-=1` raus
- `_on_station_clicked`: `_omni_tx.pause()` + `_omni_was_active_pre_qso=True`
- `_on_tx_slot_for_partner`: dito (CQ-Reply-Pfad)
- `_on_qso_complete`/`_on_qso_confirmed`/`_on_qso_timeout`: am Ende
  OMNI-Resume wenn Pre-QSO-aktiv UND Queue leer

---

## 11. Akzeptanzkriterien (V2 — vollständige Liste)

| AC | Beschreibung |
|---|---|
| AC1 | OMNI-Activate während Even → Block 1, erster CQ im nächsten Even |
| AC2 | OMNI-Activate während Odd → Block 2, erster CQ im nächsten Odd |
| AC3 | Pattern-Verlauf 10 Slots: E-TX, O-TX, E-RX, O-RX, E-RX, O-TX, E-TX, O-RX, E-RX, O-RX |
| AC4 | Block-Switch automatisch nach jedem 5-Slot-Cycle (kein 80-Counter) |
| AC5 | QSO startet während OMNI Pos 2 → `_omni_tx.pause()` aufgerufen, slot_index/block frozen |
| AC6 | QSO endet auf Even-TX → next slot Odd → Block 2 |
| AC7 | QSO endet auf Odd-TX → next slot Even → Block 1 |
| AC8 | HALT während OMNI → OMNI gestoppt, CQ stop, _was_cq=False |
| AC9 | Mode-Wechsel → OMNI gestoppt |
| AC10 | Band-Wechsel → OMNI gestoppt |
| AC11 | Bug-Beweis: OMNI RX-Slot skipped → State bleibt CQ_WAIT, kein CQ_CALLING-Hänger |
| AC12 | Caller-Queue: QSO endet, Queue nicht leer → nächstes QSO sofort, OMNI bleibt pause |
| AC13 | `_omni_skip_state_change`-Flag bei 2× CQ resetted |
| AC14 | State-Beweis bei OMNI-RX-Slot: nach `_send_cq()` ist State CQ_WAIT |

---

## 12. Tests (V2 — 19 geplant)

**Block-Logik (5):** test_block1_pattern_correct, test_block2_pattern_correct,
test_block_switch_on_rollover, test_no_block_cycles_counter, test_advance_no_qso_active_param

**Activate / „Kein Slot verschwenden" (3):** test_activate_next_even_starts_block1,
test_activate_next_odd_starts_block2, test_activate_resets_slot_index_to_0

**QSO-Pause/Resume (4):** test_pause_freezes_slot_and_block,
test_resume_picks_block_by_next_slot_parity, test_resume_after_even_tx_qso_starts_block2_for_odd_next,
test_resume_after_odd_tx_qso_starts_block1_for_even_next

**Root-Cause-Fix (3):** test_send_cq_emits_before_state_change,
test_omni_rx_slot_skips_state_stays_cq_wait, test_omni_loop_runs_through_full_pattern

**Stop-Conditions (2):** test_halt_stops_omni_and_cq, test_mode_change_stops_omni

**V2-Ergänzungen (4):** test_omni_skip_state_change_flag_resets,
test_send_cq_with_omni_rx_slot_no_state_change, test_omni_pause_on_cq_reply_via_tx_slot_for_partner,
test_omni_resume_only_when_caller_queue_empty

---

## 13. Workflow-Stand (genau)

```
[X] Compact #1 abgeschlossen
[X] Notizen-Sicherung omni_redesign_notes.md
[X] Race-Check Code-Verifikation
[X] V1: prompts/p2_omni_redesign_v1.md
[X] V2: prompts/p2_omni_redesign_v2.md (mit L1 KRITISCH gelöst)
[X] R1-Lauf-1 + R1-Lauf-2 in prompts/ gesichert
[X] Memory project_omni_redesign.md aktualisiert
[X] MEMORY.md Index aktualisiert
[X] DIESER session_context.md geschrieben
[ ] Compact #2 ← JETZT
[ ] R1-Review von V2 (Befehl §8)
[ ] V3 schreiben (Compact-fest)
[ ] Mike-Freigabe V3
[ ] Compact #3
[ ] Implementation (atomare Commits, ~6 Files)
[ ] Final-R1 Code-Review
[ ] Field-Test Mike (FlexRadio + Live-OMNI)
[ ] Push (gemeinsam mit v0.95.16-22 + P2-Tool + P3)
```

---

## 14. Risiko-Liste (was schiefgehen könnte)

1. **R1 halluziniert wieder Lücken** wenn Files unvollständig — Mitigation:
   ALLE Files vollständig, expliziter Hinweis im Prompt
2. **R1 truncated** (wie Lauf 2) — Mitigation: `out=8000` reicht, falls
   nicht: Prompt teilen
3. **`is_even_cycle()` existiert nicht** mit dieser Semantik — Mitigation:
   V3 muss das vor Implementation klären (grep core/timing.py)
4. **Singleton-Aufrufer** mit `block_cycles=...` werden übersehen —
   Mitigation: V3-Pflicht-grep
5. **Field-Test scheitert** weil ein Pfad übersehen — Mitigation: 14 ACs
   alle vor Push gegen Code prüfen
6. **`_resume_cq_if_needed` doppelt** mit OMNI-Resume — Mitigation:
   idempotent designed, Test deckt das ab
7. **Pause/Resume-Race** wenn Decoder-Thread vs GUI-Thread — Mitigation:
   alles im GUI-Thread, kein Lock nötig

---

## 15. Trigger-Phrasen für post-Compact

**Nach Compact #2 — direkt R1 starten:**
- „weiter mit OMNI-Redesign R1"
- „R1 schicken"
- „deepseek-Review starten"

**Nach Compact #2 — V3 ohne R1 (falls R1 wieder truncated):**
- „V3 ohne R1"
- „V3 nur aus Lauf 1 + V2"

**Falls Sackgasse / Mike will ändern:**
- Notizen `omni_redesign_notes.md` ist Source of Truth — komplett neu
  starten ist OK
- Git-Tag `pre-omni-redesign` als Backup-Punkt

---

## 16. Mike-Zitate Volltext (chronologisch, archiviert)

1. „ich mache doch jetzt kein pflaster"
2. „eieieieiei, ich dachte wir wäre hier schnell duch also ersteinmal wir
   messen nichts mehr nach 80 zyclen wir messen diverity nach einer stunde"
3. „nein lass uns das erst klären wir hatten 80 zyklen voer als einmessung
   jetzt haben wir eine stunde"
4. „es wechselt kein muster omni senden wechselt von alleine das muster bei
   jedeen sende duchgang wie oft noch even, odd senden - even.odd,even
   empfangen dann neuer turnus odd,even senden - odd,even,odd empfangen"
5. „jaaaaa, du siehst doch das er von alleine wechselt und das wir keine
   leeren slots haben und das sie gleichmässig sich von alleine verteilen
   block1 - wechsel block2 - wechsel block1 - wechsel block2 - wechsel"
6. „es kann nicht während des qso duchlaufen ich muss sobald ein qso startet
   den normalen ablauf machen, ach mann wa sstellst du dich jetzt so doof
   an .. verstehst du es nicht was meinst du block läuft immer duch auch
   wenn qso, nein du musst natürlich auf den passenden slot antworten wenn
   qso auf even antwortet müssen wir odd anworten oder iumgekehr"
7. „junge entweder bin ich bescheuert oder du drückst dich falsch aus.
   was machen wir wenn wir omni rufen, klaären wir in ruhe den ablauf."
8. „soll ich das jetzt 100000000 millionen mal schreiben ich bekomme blitze
   ,...nochmallllll even,odd senden even,oddd ,even hören und dann umgekehrt"
9. „was machen wir wenn dann beim empfangen eine antwort kommt? altttobelli...
   wie antworten wir dann haben wir wie besprochen ein programmteil für
   omni für normal für huntmodus für stationrufen?"
10. „jaaaa, und dann brauch omni auch nur neu getartet werden wenn das qso
    im even endet starten wir omni im odd block wird das qo im odd beendet
    starten wir im even block.."
11. „nein logik wir verschewenden keinen slot, wenn das qso auf even beendet
    wurde warum soll ich dann auf odd nicht machen und auch even wieder
    anfangen dann kann ich auf odd anfangen und verliere keine 15 sekunden"
12. „was hast du mit fairniss ß"
13. „du machst mir bei dieser session echt sorgen das es in die hose geht .-(
    okay der ablauf steht hast du fragen?"
14. „ich denke das ist egal wenn es nicht zuviel aufwannd ist natürlich aus
    effiziensgründen den nächsten freien block direkt. wäre ja quatsch den
    zu verscheneke. aber das ist frage aufwand nutzen verhäldniss."
15. „nein dann haben wir es, jetzt frage. möchtest du die ergkentnisse und
    aufgaben erstmal sichern dann compact dann konpletten workflow bis
    deepseek dann nochmal kompakt und dann umsetzung oder wie willst du es
    machen"
16. „ja so machen wir es genau so beste vorraussetzungen schaffen"
17. „b sehe ich auch so" (Option B Bestätigung)
18. „okay compact1 abgeschlossen starten wir den deepseek workflow"
19. „kontext ist voll sollen wir hier einen compact achen und du sicherst
    dir alles? oder erst deepseek fragen schicken?"
20. „sichere doch alles nicht nur da wichtigeste, auf der ssd ist doch
    genug platz und wenn wir vor der änderung nochmal einen copact machen
    wie du es aber meinst es am besten ist du bist die ki nicht ich"

---

**Ende des Session-Kontexts. Bereit für Compact #2.**
