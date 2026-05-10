Du bist Senior Python-Entwickler spezialisiert auf Amateurfunk-Software
und PySide6 (Signal statt pyqtSignal, Slot statt pyqtSlot). Das Projekt
ist ein Hobby-Funker-Tool für einen einzelnen Operator — NICHT Multi-Tenant.

Deine einzige Aufgabe: diesen Prompt kritisieren — NICHT das Problem lösen.
Strukturierte Liste: Lücken, Unklarheiten, Widersprüche, Verbesserungen.

KRITISCHE REGELN:
1. SCOPE-RESPEKT: Explizit als out-of-scope markiertes NICHT als Finding melden.
2. KISS VOR DEFENSIV: Komplexität nur wenn Wahrscheinlichkeit > 50%.
3. PROJEKT-BEZUG: Jedes Finding am konkreten Use-Case messen.
4. FORMAT: Tabelle Schwere | Finding | Datei:Zeile | Empfehlung.
   Severity: Bug (rot) / Risiko (orange) / Verbesserung (gelb) / Hinweis (grau).

Overengineering ist selbst ein Fehler den du benennen sollst.

---

# P4.OMNI-NEUBAU V5 — Signal-basierter Refactor (V2)

## Kontext (für die Review)

**Vorgeschichte heute:** P4.OMNI-NEUBAU v0.96.0 wurde nach 8 Commits
implementiert und ist code-fertig (1026 Tests grün). Field-Test mit
Mike (FlexRadio, real on-air) zeigt aber: das Pattern ist komplett
kaputt. Beobachtung 15:12 UTC:

```
15:12:00 [E] → Sende CQ DA1MHH JO31    (Pos 0 ✓)
15:12:13 [E] ← Horche                  (×3 alle gleicher Zeit)
15:12:13 [E] ← Horche                   ─ Pos 2/3/4 in einem Slot
15:12:13 [E] ← Horche                   ─ statt 3 verteilt über 45s
15:12:15 [O] → Sende CQ DA1MHH JO31    (Pos 1 — eigentlich erst Pos 1, OK)
15:12:28 [O] ← Horche ×3                (Block 2 Pos 2/3/4 wieder in einem Slot)
15:12:30 [E] → Sende CQ DA1MHH JO31    (Block 2 Pos 1)
```

**Bug-Wurzel im aktuellen Code (`core/omni_cq.py:302-336`):**
Worker-Loop ruft `_advance_state` direkt nach `emit`. Nächste Iteration
berechnet `_compute_next_boundary` mit `now` der noch VOR der gerade
verarbeiteten Boundary liegt → liefert dieselbe Boundary →
`sleep_dur ≤ 0` → emit sofort → Pos 2/3/4 rasen in einem Slot durch.
Tests waren grün weil `_block_worker_boundaries`-Mock genau diesen
Pfad blockiert hat (Worker schlief 100s, kritischer Pfad nie getriggert).

**Architektur-Korrektur (Mike-Vorschlag, validiert via Code-Read):**
Normal-CQ funktioniert seit v0.78 robust mit folgendem Pattern:
- `FT8Timer.cycle_start = Signal(int, bool)` emittet `(cycle_count, is_even)`
  jeden 15s-Slot (`core/timing.py:19,87`)
- `mw_cycle._on_cycle_start(cycle_num, is_even)` (`ui/mw_cycle.py:575`)
  ist der zentrale Slot-Trigger im GUI-Thread
- TX läuft via `encoder.transmit(message, *, tx_even, audio_freq_hz)`
  (atomare API seit C3, `core/encoder.py:189-212`)
- Encoder-Thread schedulet TX selbst auf den passenden UTC-Slot via
  `_next_slot_boundary` (`core/encoder.py:235-281`)

→ V5 nutzt genau diesen Pfad für OMNI-CQ. Kein eigener Worker-Thread,
keine eigenen Sleeps, keine `_compute_next_boundary`-Race.

---

## 1. Ziel

`core/omni_cq.py` von Worker-Thread auf signal-getriggertes Modul
refactorn. OMNI-CQ bleibt **eigenständig** (kein `qso_state.cq_mode`-Hack),
aber die Slot-Synchronisation kommt vom existing
`FT8Timer.cycle_start`-Signal — wie Normal-CQ es seit v0.78 nutzt.

**Eine Methode** `OmniCQ.on_cycle_start(cycle_num: int, is_even: bool)`
entscheidet pro Slot:
- Pos 0/1 (TX): `encoder.transmit("CQ {call} {grid}", tx_even=...,
  audio_freq_hz=...)` — Encoder-Thread macht das Slot-Timing
- Pos 2/3/4 (RX): emit `slot_action` für „Horche..."-Anzeige
- `_slot_index` advancen, bei Rollover Block wechseln

---

## 2. Verbindliches Pattern (Mike-Spec 09.05.2026 spät)

```
Block 1 (Even-First):
  Pos 0: TX-E  (Slot N+0, even)
  Pos 1: TX-O  (Slot N+1, odd)
  Pos 2: RX-E  (Slot N+2, even — Horche)
  Pos 3: RX-O  (Slot N+3, odd — Horche)
  Pos 4: RX-E  (Slot N+4, even — Horche, extra Slot für sauberen Übergang)

Block 2 (Odd-First):
  Pos 0: TX-O
  Pos 1: TX-E
  Pos 2: RX-O
  Pos 3: RX-E
  Pos 4: RX-O

Wechsel: nach 5 Slots automatisch (slot_index 4 → 0).
Block 1 ↔ Block 2 permanent.
QSO-Resume: endet auf Even → Block 2, endet auf Odd → Block 1.
IMMER ab Pos 0.
```

---

## 3. Akzeptanzkriterien

### Pattern + Trigger

| AC | Kriterium |
|----|-----------|
| AC1 | Bei btn_omni_cq → `OmniCQ.start()` setzt `_active=True`, `_slot_index=0`, `_block=1`, `_cq_audio_hz=None`. Statusbar „Ω Even=0 Odd=0", Button-Label „OMNI CQ (aktiv)". |
| AC2 | Block 1 Pattern: Pos 0 TX-E, Pos 1 TX-O, Pos 2 RX-E, Pos 3 RX-O, Pos 4 RX-E. |
| AC3 | Block 2 Pattern: Pos 0 TX-O, Pos 1 TX-E, Pos 2 RX-O, Pos 3 RX-E, Pos 4 RX-O. |
| AC4 | Block-Rollover automatisch nach 5 Slots (`slot_index 4 → 0`): Block 1 ↔ Block 2. Permanent. |
| AC5 | **Toggle-Start (Klärungsfrage 1, siehe §8):** beim ersten Klick `_block=1` (Block 1 Even-First). Wenn aktueller UTC-Slot odd ist, encoder verzögert TX auf nächsten passenden Slot — 1 Slot Wartezeit OK (KISS). Alternativ: Block-Wahl nach `not is_even_cycle()` für minimale Wartezeit. |
| AC6 | Bei jedem `FT8Timer.cycle_start(cycle_num, is_even)` ruft die App `OmniCQ.on_cycle_start(cycle_num, is_even)` auf. Verbindung in `MainWindow.__init__` oder als Aufruf aus `mw_cycle._on_cycle_start`. |
| AC7 | OmniCQ nutzt `_slot_index` für Pattern-Entscheidung. `is_even` aus dem Signal wird NUR für RX-Slot-Anzeige (Horche [E]/[O]) verwendet, nicht für Pattern-Wahl. |
| AC8 | TX-Slot: `encoder.transmit("CQ DA1MHH JN58", tx_even=target_even, audio_freq_hz=cq_freq)`. Encoder-Thread schedulet auf passenden UTC-Slot (analog Normal-CQ-Pfad seit v0.78). |
| AC9 | RX-Slot: `slot_action.emit(label, is_tx=False, target_even=is_even)` — `is_even` aus dem Signal-Parameter (echter UTC-Slot). Kein `transmit`-Aufruf. |
| AC10 | Nach Aktion: `_slot_index = (_slot_index + 1) % 5`. Bei Rollover (slot_index → 0): `_block = 2 if _block==1 else 1`. |

### Encoder-Busy-Verhalten

| AC | Kriterium |
|----|-----------|
| AC11 | Wenn `encoder.transmit(...)` False returnt (TX schon laufend): Counter NICHT inkrementieren, kein `slot_action.emit`, log warning, aber `_slot_index` advanced trotzdem (Pattern bleibt synchron). |

### Frequenz

| AC | Kriterium |
|----|-----------|
| AC12 | Beim ersten TX-Slot in einem aktiven OMNI-Lauf: `_cq_audio_hz = diversity.get_free_cq_freq()`. Fallback 1500 Hz wenn None. Emit `cq_freq_changed`. |
| AC13 | **Frequenz-Sticky (Klärungsfrage 2):** V5-KISS = 1× am Anfang setzen, dann fest bis Stop. Kein Recheck-Counter, kein Histogramm-Recheck zur Laufzeit. Mike-Original-Spec: „Bleibt fest. Kein Versatz, kein Springen." |
| AC14 | Bei `resume_after_qso(...)`: `_cq_audio_hz` BEHALTEN (während Pause nicht resetten). Frequenz wechselt nur durch `stop()` + neuer `start()`. |
| AC15 | Bei `stop(...)`: `_cq_audio_hz = None`. |

### QSO-Übergabe

| AC | Kriterium |
|----|-----------|
| AC16 | Listener `mw_cycle.on_message_decoded` bleibt UNVERÄNDERT (C6-korrekt): wenn `_omni_cq.is_active() and not _omni_cq.is_paused() and msg.target == my_call and not msg.is_73 and not msg.is_rr73` → `_pause_omni_if_active()` + `encoder.tx_even = not msg._tx_even` + `qso_sm.start_qso(...)`. |
| AC17 | `pause()` setzt `_paused=True` (kein Thread mehr — einfacher Flag-Set). `on_cycle_start` während `_paused` → no-op (return early). |
| AC18 | `resume_after_qso(last_was_even)`: Block-Wahl — `last_was_even=True` → `_block=2`, sonst `_block=1`. `_slot_index=0`. `_paused=False`. `_active=True` falls noch nicht. `_cq_audio_hz` BLEIBT (AC14). |
| AC19 | Caller-Queue bleibt im `_maybe_resume_omni`-Helper in `mw_qso.py` (C6-Code unverändert). |

### Stop-Trigger

| AC | Kriterium |
|----|-----------|
| AC20 | `stop(reason)`: `_active=False`, `_paused=False`, `_slot_index=0`, `_block=1`, `_cq_audio_hz=None`, `_cq_even_count=0`, `_cq_odd_count=0`. Emittet `omni_stopped(reason)`. Idempotent (zweiter Aufruf no-op). |
| AC21 | Stop-Reasons (alle bleiben aus C7): `manual_halt`, `band_change`, `mode_change`, `rx_mode_change`, `totmann_expired`, `superseded`, `easter_egg_off`, `test_cleanup`. Trigger-Stellen unverändert (`mw_radio.py`, `main_window.py`). |

### Signals (API-Compat zu C6 main_window-Slots)

| AC | Kriterium |
|----|-----------|
| AC22 | `omni_started = Signal()` — emittet beim `start()`. |
| AC23 | `omni_stopped = Signal(str)` — emittet beim `stop(reason)`. |
| AC24 | `slot_action = Signal(str, bool, bool)` — `(label, is_tx, target_even)`. Bei TX und RX. |
| AC25 | `cq_freq_changed = Signal(int)` — emittet beim ersten TX-Slot wenn Frequenz initialisiert wird. |
| AC26 | `counter_changed = Signal(int, int)` — `(cq_even, cq_odd)`. Bei TX-Erfolg. |

### Hardware

| AC | Kriterium |
|----|-----------|
| AC27 | OMNI emittet keinen TX direkt — geht über `encoder.transmit()`, der zentral `radio.set_tx_antenna("ANT1")` setzt (`core/encoder.py:334`). Kein Extra-Check nötig. |

### Tests

| AC | Kriterium |
|----|-----------|
| AC28 | `tests/test_omni_cq_signal.py` NEU (~20 Tests): rufen `on_cycle_start(cycle_num, is_even)` direkt auf, Mock-Encoder verifiziert `transmit`-Calls + kwargs. **KEIN Worker-Mock, KEIN Sleep-Mock, KEIN Boundary-Mock.** Lessons-Learned aus heute: `_block_worker_boundaries` hat den kritischen Pfad versteckt. |
| AC29 | `tests/test_omni_cq_worker.py` (37 Tests, v0.96.0 obsolet) → KOMPLETT ENTFERNEN. Worker-spezifische Mocks haben kein Pendant in V5. |
| AC30 | `tests/test_omni_cq_integration.py` (14 Tests aus C6) — bleibt soweit möglich. Tests die `_block_worker_boundaries` aufrufen → Mock-Hilfe entfernen, da nicht mehr nötig (kein Thread). |

---

## 4. Betroffene Module/Dateien

### NEU geschrieben

- **`core/omni_cq.py`** — kompletter Refactor (~80-120 Zeilen statt 337).
  - Worker-Thread + sleep-Logik raus (`_thread`, `_stop_event`, `_worker_loop`, `_compute_next_boundary`, `_OMNI_TX_PRELEAD_S`, `_lock`)
  - Pattern-Logik bleibt (`_TX_PATTERN`, `_next_slot_action`, `_advance_state`, `_block`, `_slot_index`)
  - `start()`, `stop()`, `pause()`, `resume_after_qso()`, `is_active()`, `is_paused()` API bleibt (für C6-Slots in main_window)
  - NEU: `on_cycle_start(cycle_num: int, is_even: bool)` als Slot
  - Properties `cq_even_count`, `cq_odd_count`, `cq_audio_hz` bleiben

### Verbindung (kleine Änderung)

- **`ui/mw_cycle.py:575` `_on_cycle_start`** — am Ende ergänzen:
  ```python
  if self._omni_cq.is_active() and not self._omni_cq.is_paused():
      self._omni_cq.on_cycle_start(cycle_num, is_even)
  ```
  (Active-Check spart unnötige Aufrufe, ist optional weil OmniCQ selbst auch returnt.)

### Tests

- **`tests/test_omni_cq_worker.py`** — LÖSCHEN (37 Tests obsolet — Worker weg).
- **`tests/test_omni_cq_signal.py`** — NEU (~20 Tests, siehe §6).
- **`tests/test_omni_cq_integration.py`** — Migrationen wo `_block_worker_boundaries` aufgerufen wird (Helper rauswerfen).

### UNVERÄNDERT (wichtig — kein Sekundär-Schaden)

- `core/encoder.py` — atomare `transmit`-API (C3) bleibt.
- `core/qso_state.py` — kein `cq_mode`-Hack, Hunt-Pfad unverändert.
- `ui/mw_cycle.on_message_decoded` Listener-Pfad (C6) unverändert.
- `ui/mw_qso.py` — `_pause_omni_if_active` / `_maybe_resume_omni` Helper (C6) unverändert. Caller-Queue-Pop unverändert.
- `ui/main_window.py` — OmniCQ-Init + 4 Signal-Slots (C6) unverändert. `_on_omni_stopped` (R4-Reset) unverändert.
- `ui/mw_radio.py` — Stop-Trigger (C7) unverändert.

---

## 5. Randbedingungen

### Threading

- `cycle_start`-Signal wird vom FT8Timer-Thread emittet, mit `Qt.QueuedConnection` (Default für Cross-Thread) ans GUI-Thread Slot zugestellt.
- `OmniCQ.on_cycle_start` läuft im **GUI-Thread** — kein Lock nötig für Pattern-State.
- `encoder.transmit` ist thread-safe (atomare API mit `_replace_lock` aus C3). Aufruf aus GUI-Thread OK.
- `pause()`, `resume_after_qso()`, `stop()` aus mw_qso/main_window/mw_radio kommen alle aus dem GUI-Thread → kein Lock nötig.

### Decoder-Blockade-Risiko

- `cycle_start`-Signal kann durch GUI-Thread-Blockade (Decoder ~0.1-1s) in der Event-Queue verzögert ankommen.
- Wenn `cycle_start` für Slot N erst bei `now = N*SLOT + 1.0` ankommt:
  - `encoder.transmit(tx_even=True)` wird gerufen, encoder berechnet `_next_slot_boundary`:
    - `cycle_pos=1.0 > 0.5` → encoder nimmt **nächsten** passenden Slot.
    - Folge: 1 Pos im Pattern „skipped" auf späteren Slot.
- **Akzeptabel KISS:** Normal-CQ hat dasselbe Risiko seit v0.78, funktioniert. Bei Hobby-Use selten relevant.
- Mitigation falls relevant: Mike-Klärungsfrage 3 — `cycle_pos`-Check in `on_cycle_start`, bei zu spät Pos überspringen oder Logging.

### Hardware ANT1

- Vor jedem TX-Trigger setzt `encoder.transmit` zentral `radio.set_tx_antenna("ANT1")`. OMNI emittet keinen TX direkt.

### KISS

- Kein Frequenz-Recheck-Counter (V5: 1× am Start, dann fest).
- Kein 80-Cycles-Counter (Block-Rollover automatisch bei `slot_index 4 → 0`).
- Kein cycle_tick-basierter Pretrigger (war v0.95.24/25 obsoleter Versuch).
- Kein Worker-Thread.

---

## 6. Test-Plan

### Unit-Tests `tests/test_omni_cq_signal.py` (NEU, 20 Tests)

| # | Test | AC |
|---|------|----|
| T1 | `test_initial_state_inactive` | AC1 |
| T2 | `test_start_initializes_block1_pos0` | AC1, AC5 |
| T3 | `test_block1_pos0_calls_encoder_transmit_tx_even` | AC2, AC8 |
| T4 | `test_block1_pos1_calls_encoder_transmit_tx_odd` | AC2, AC8 |
| T5 | `test_block1_pos2_3_4_no_transmit_emits_horche` | AC2, AC9 |
| T6 | `test_block1_pos4_rollover_to_block2_pos0_tx_odd` | AC3, AC4, AC10 |
| T7 | `test_block2_pos1_tx_even` | AC3 |
| T8 | `test_block2_rollover_back_to_block1` | AC4 |
| T9 | `test_block_alternation_permanent_10_slots` | AC4 |
| T10 | `test_pause_freezes_state` | AC17 |
| T11 | `test_on_cycle_start_during_pause_no_op` | AC17 |
| T12 | `test_resume_after_qso_even_chooses_block2_pos0` | AC18 |
| T13 | `test_resume_after_qso_odd_chooses_block1_pos0` | AC18 |
| T14 | `test_stop_resets_full_state` (parametrize 7 reasons) | AC20, AC21 |
| T15 | `test_freq_init_from_diversity_first_tx` | AC12 |
| T16 | `test_freq_fallback_1500_when_diversity_none` | AC12 |
| T17 | `test_freq_sticky_during_omni_5_cycles` | AC13 |
| T18 | `test_freq_kept_during_pause_resume` | AC14 |
| T19 | `test_encoder_busy_no_counter_increment_but_advance` | AC11 |
| T20 | `test_signals_emitted_correctly` (omni_started/stopped/slot_action/cq_freq_changed/counter_changed) | AC22-26 |

**Test-Pattern:**
```python
def test_block1_pos0_calls_encoder_transmit_tx_even(app):
    omni, encoder, *_ = _make_omni()
    omni.start()
    omni.on_cycle_start(cycle_num=100, is_even=True)
    encoder.transmit.assert_called_once_with(
        "CQ DA1MHH JN58", tx_even=True, audio_freq_hz=1500
    )
    assert omni._slot_index == 1
```

**KEIN `_block_worker_boundaries`. KEIN Thread-Mock. Tests rufen `on_cycle_start` direkt auf.**

### Integration-Tests `tests/test_omni_cq_integration.py` (existing 14, leicht migriert)

C6-Tests bleiben weitgehend, nur `_block_worker_boundaries`-Aufrufe werden gestrichen (kein Worker mehr). Methoden-API von OmniCQ bleibt gleich.

### Field-Test (Mike, vor Push)

V3 §6 17-Punkte-Plan F1-F17 unverändert:
- 10-Slot-Loop: Pattern korrekt, KEIN Drift wie v0.96.0
- Block-Wechsel automatisch nach 5 Slots
- CQ-Antwort: OMNI pausiert, QSO startet, nach RR73 Resume mit Block-Wahl
- Stop-Trigger: alle 7 Reasons

---

## 7. Nicht im Scope

- ❌ Änderungen an `core/encoder.py` (atomare API ist fertig, C3)
- ❌ Änderungen an `core/qso_state.py` (kein `cq_mode`-Hack)
- ❌ Änderungen am Listener-Pfad in `mw_cycle.on_message_decoded` (C6 ist korrekt)
- ❌ Änderungen am Hunt-Pfad — `qso_state.start_qso` bleibt
- ❌ Frequenz-Recheck zur Laufzeit (V5: 1× am Start, dann fest)
- ❌ 80-Cycles-Counter (war alte Spec, Mike: Block-Rollover bei slot_index 4→0)
- ❌ `cycle_tick`-basierter Pretrigger (obsolet)
- ❌ QTimer-Pretrigger (war v0.95.25 Versuch, obsolet)
- ❌ Encoder-Queue für OMNI (war P2.OMNI-PATTERN-FIX, in C3 entfernt)

---

## 8. Mike-Klärungsfragen (DeepSeek soll dazu Stellung nehmen)

### Klärung 1: Toggle-Start Block-Wahl

**Variante A (V5 default):** beim Klick IMMER Block 1. Wenn aktueller
UTC-Slot odd ist, encoder verzögert TX-E auf nächsten passenden Slot
(1 Slot Wartezeit).

**Variante B (v0.96.0 verhalten):** Block-Wahl nach
`next_is_even = not is_even_cycle()` — Block 1 wenn nächster Slot even,
Block 2 wenn odd. Keine Wartezeit.

Mike's letzte Aussage: „beim Toggle IMMER Block 1". → Variante A bevorzugt.

### Klärung 2: Frequenz-Sticky

**Variante A (V5 KISS):** `_cq_audio_hz` 1× am Start setzen, dann fest
bis Stop. Auch über pause/resume hinweg gleich. Kein Recheck.

**Variante B (Mike's Sub-Spec 09.05.):** Sticky-Gap mit Recheck alle
4 Blöcke (~5 Min). Frequenz wechselt wenn Histogramm Kollision meldet.

Mike's Original-Spec sagt „Bleibt fest. Kein Versatz." → Variante A
bevorzugt KISS.

### Klärung 3: Decoder-Blockade-Schutz

**Variante A (KISS):** `on_cycle_start` immer ausführen, encoder schiebt
TX bei Verzögerung 1 Slot weiter. Akzeptierter Edge-Case.

**Variante B (Defense):** in `on_cycle_start` `cycle_pos = time.time() %
SLOT` prüfen, bei `cycle_pos > 0.3s` Slot überspringen + log warning.

Risiko-Wahrscheinlichkeit: gering (Decoder blockiert selten >1s,
Normal-CQ toleriert es seit v0.78). → Variante A bevorzugt KISS.

---

## 9. Vorteile gegenüber v0.96.0 Worker-Thread

| Aspekt | v0.96.0 (kaputt) | V5 (signal) |
|--------|------------------|-------------|
| Slot-Sync | eigene Worker-Sleeps | `cycle_start`-Signal vom Timer |
| TX-Timing | eigene Boundary-Berechnung | Encoder-Thread (wie Normal-CQ) |
| Code-Größe | ~340 Zeilen | ~80-120 Zeilen |
| Threads | eigener `OmniCQWorker` | keiner |
| Race-Risiko | hoch (sleep_dur=0 Bug) | minimal (alles GUI-Thread) |
| Testbarkeit | Worker-Mock versteckt kritischen Pfad | direkter Method-Call testet WAS passiert |
| Decoder-Blockade-Risiko | Worker robust, aber buggy | wie Normal-CQ (akzeptabel) |

---

**Ende V2.**

Ich erwarte: Tabelle Schwere | Finding | Datei:Zeile | Empfehlung.
Plus Stellungnahme zu den 3 Klärungsfragen in §8.
