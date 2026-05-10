# P4.OMNI-NEUBAU V5 — Signal-basierter Refactor (V1)

**Datum:** 2026-05-09 spät
**Vorgeschichte:** P4.OMNI-NEUBAU v0.96.0 (Worker-Thread-Architektur) hat
beim Field-Test gezeigt dass das Pattern komplett kaputt ist:

- 15:12:00 [E] TX (Pos 0 ✓)
- 15:12:13 [E] Horche ×3 (Pos 2/3/4 alle in einem Slot)
- 15:12:15 [O] TX (Pos 1)
- 15:12:28 [O] Horche ×3
- 15:12:30 [E] TX

**Bug-Wurzel:** Worker-Loop ruft `_advance_state` direkt nach `emit`,
nächste Iteration berechnet `_compute_next_boundary` mit `now` der noch
VOR der gerade verarbeiteten Boundary liegt → liefert dieselbe Boundary
→ `sleep_dur ≤ 0` → emit sofort. So rasen Pos 2/3/4 in einem Slot durch.
Tests waren grün weil `_block_worker_boundaries`-Mock genau diesen
Pfad blockiert hat — Worker schlief 100s, kritischer Pfad nie getriggert.

**Architektur-Korrektur (Mike-Vorschlag):** kopiere wie Normal-CQ
funktioniert. Normal-CQ nutzt `FT8Timer.cycle_start`-Signal (1× pro
15s-Slot) und der Encoder-Thread schedulet TX selbst auf den richtigen
UTC-Slot. Kein eigener Worker, keine eigenen Sleeps, keine Race
zwischen Pattern und TX-Timing.

---

## 1. Ziel

`core/omni_cq.py` von Worker-Thread-Architektur auf Signal-getriggertes
Pattern-Modul refactorn. OMNI-CQ wird ein eigenständiges Modul (kein
qso_state.cq_mode-Hack), aber Slot-Synchronisation kommt vom existing
`FT8Timer.cycle_start`-Signal — wie Normal-CQ es seit v0.78 nutzt.

Pro `cycle_start`-Event entscheidet `OmniCQ.on_cycle_start(cycle_num,
is_even)`:
- Pattern-Position 0/1: TX (`encoder.transmit` mit korrekter Parität)
- Pattern-Position 2/3/4: RX (nur Anzeige „Horche…")
- `_slot_index` advancen, bei Rollover Block wechseln

---

## 2. Akzeptanzkriterien

### Pattern (verbindlich, Mike-Spec 09.05.2026 abend)

| AC | Kriterium |
|----|-----------|
| AC1 | Bei btn_omni_cq → `OmniCQ.start()` setzt `_slot_index=0`, `_block=1`, `_active=True`. Statusbar „Ω Even=0 Odd=0", Button-Label „OMNI CQ (aktiv)". |
| AC2 | `Block 1` Pattern: Pos 0 TX-E, Pos 1 TX-O, Pos 2 RX-E, Pos 3 RX-O, Pos 4 RX-E. |
| AC3 | `Block 2` Pattern: Pos 0 TX-O, Pos 1 TX-E, Pos 2 RX-O, Pos 3 RX-E, Pos 4 RX-O. |
| AC4 | Block-Rollover automatisch nach 5 Slots (`slot_index 4 → 0`): Block 1 ↔ Block 2. |
| AC5 | Beim Toggle-Start IMMER Block 1 (Even-First). Erste Position ist Pos 0 in Block 1. |

### Slot-Trigger

| AC | Kriterium |
|----|-----------|
| AC6 | Bei jedem `FT8Timer.cycle_start(cycle_num, is_even)` ruft die App `OmniCQ.on_cycle_start(cycle_num, is_even)` auf. |
| AC7 | OmniCQ schaut nur auf `_slot_index` (Pattern-State), NICHT auf `is_even` (UTC-Parität) — Pattern entscheidet, nicht der UTC-Takt. |
| AC8 | Bei TX-Slot ruft OmniCQ `encoder.transmit("CQ {call} {grid}", tx_even=target_even, audio_freq_hz=cq_freq)`. Encoder-Thread schedulet TX selbst auf den passenden UTC-Slot (analog Normal-CQ-Pfad seit v0.78). |
| AC9 | Bei RX-Slot emittet OmniCQ `slot_action(label, False, is_even)` — `is_even` ist der echte UTC-Slot vom Timer-Signal. Kein TX-Aufruf. |
| AC10 | Nach Aktion: `_slot_index = (_slot_index + 1) % 5`. Bei Rollover (slot_index → 0): `_block = 2 if _block==1 else 1`. |

### Frequenz

| AC | Kriterium |
|----|-----------|
| AC11 | Erste TX-Position holt `_cq_audio_hz` aus `diversity.get_free_cq_freq()`. Fallback 1500 Hz wenn None. |
| AC12 | Frequenz ist „sticky" — bleibt, solange OMNI läuft (V5-KISS: kein Recheck-Counter, kein Histogramm-Recheck). Wenn nicht aktiv: zurück auf None. |
| AC13 | Während QSO: keine Frequenz-Änderung (OMNI ist pausiert). |

### QSO-Übergabe

| AC | Kriterium |
|----|-----------|
| AC14 | Listener `mw_cycle.on_message_decoded` (existing): wenn `_omni_cq.is_active() and not _omni_cq.is_paused() and msg.target == my_call and not msg.is_73 and not msg.is_rr73` → `_pause_omni_if_active()` + `encoder.tx_even = not msg._tx_even` + `qso_sm.start_qso(...)`. **Bleibt unverändert** — ist schon korrekt seit C6. |
| AC15 | `_pause_omni_if_active` setzt `_paused=True` (kein Thread mehr → einfacher Flag-Set). `_maybe_resume_omni` ruft `_omni_cq.resume_after_qso(last_qso_was_even)`. **Helper bleiben**, nur OmniCQ.pause/resume_after_qso werden vereinfacht. |
| AC16 | `resume_after_qso(last_was_even)`: Block-Wahl — endet Even → Block 2, endet Odd → Block 1. Slot-Index → 0. Caller-Queue-Pop bleibt im `_maybe_resume_omni`-Helper (mw_qso.py). |

### Stop-Trigger

| AC | Kriterium |
|----|-----------|
| AC17 | `stop(reason)` setzt `_active=False`, `_paused=False`, `_slot_index=0`, `_block=1`, `_cq_audio_hz=None`. Emittet `omni_stopped(reason)`. |
| AC18 | Stop-Reasons (alle bleiben aus C7): `manual_halt`, `band_change`, `mode_change`, `rx_mode_change`, `totmann_expired`, `superseded`, `easter_egg_off`. Trigger-Stellen unverändert (mw_radio.py, main_window.py). |

### Hardware

| AC | Kriterium |
|----|-----------|
| AC19 | OMNI emittet keinen TX direkt — geht über `encoder.transmit()`, der zentral `radio.set_tx_antenna("ANT1")` setzt. |

### Tests

| AC | Kriterium |
|----|-----------|
| AC20 | `tests/test_omni_cq_signal.py` NEU: Pattern-Tests rufen `on_cycle_start` direkt auf, Mock-Encoder verifiziert `transmit`-Calls + kwargs. KEIN Worker-Mock, KEIN Sleep-Mock. |
| AC21 | Mindestens 20 Unit-Tests: Block 1/2 Pattern, Rollover, Pause/Resume, Stop alle Reasons, Frequenz-Init+Sticky, kein TX bei RX-Pos, encoder.tx_even kwarg korrekt. |
| AC22 | `tests/test_omni_cq_integration.py` (existing C6) bleibt — wird auf neue OmniCQ-API migriert wo nötig. |

---

## 3. Betroffene Module/Dateien

### NEU geschrieben

- `core/omni_cq.py` — kompletter Refactor (~80-120 Zeilen statt 337). Worker-Thread + sleep-Logik raus, `on_cycle_start`-Methode rein.

### Verbindung (kleine Änderung)

- `ui/main_window.py:621-622` — bestehender Connect: `self.timer.cycle_start.connect(self._on_cycle_start)`. Nach Init: zusätzlich `self.timer.cycle_start.connect(self._omni_cq.on_cycle_start)`. ODER: `_on_cycle_start` in mw_cycle ruft `self._omni_cq.on_cycle_start(cycle_num, is_even)` mit auf. Variante 2 ist kompakter.

### Tests

- `tests/test_omni_cq_worker.py` — UMBENENNEN zu `tests/test_omni_cq_signal.py`, KOMPLETT neu (37 Tests waren auf Worker-Mock — diese sind alle obsolet).
- `tests/test_omni_cq_integration.py` (14 Tests, C6) — Migrationen wo Worker-Lifecycle geprüft wird (FakeMW.start spawnt jetzt keinen Thread). Größtenteils können bleiben.

### UNVERÄNDERT

- `core/encoder.py` — atomare `transmit`-API (C3) bleibt
- `core/qso_state.py` — kein cq_mode-Hack
- `ui/mw_cycle.py` — Listener-Pfad in `on_message_decoded` (C6) bleibt; im `_on_cycle_start` wird der OmniCQ-Trigger ergänzt
- `ui/mw_qso.py` — `_pause_omni_if_active` / `_maybe_resume_omni` Helper (C6) bleiben
- `ui/mw_radio.py` — Stop-Trigger (C7) bleiben
- Alle existing Signal-Connections in MainWindow (C6) bleiben

---

## 4. Randbedingungen

### Threading

- **`cycle_start` läuft im GUI-Thread** (FT8Timer-Thread emittet, Qt.QueuedConnection ins MainWindow). `OmniCQ.on_cycle_start` wird also im GUI-Thread ausgeführt — kein Lock nötig für Pattern-State.
- **`encoder.transmit` ist thread-safe** (atomarer API mit `_replace_lock`). Aufruf aus GUI-Thread OK.
- **OmniCQ State (slot_index, block, audio_hz)**: nur GUI-Thread liest/schreibt → kein Lock nötig.
- **Pause/Resume aus mw_qso**: GUI-Thread → kein Lock nötig.

### Decoder-Blockade-Risiko

- `cycle_start`-Signal kann durch GUI-Thread-Blockade (Decoder) verzögert kommen.
- Wenn `cycle_start` für Slot 15:12:00 erst bei 15:12:01 ankommt: encoder.transmit wird verzögert aufgerufen. Encoder berechnet `_next_slot_boundary`:
  - cycle_pos=1.0 → > 0.5 → encoder nimmt **nächsten** passenden Slot statt aktuellen.
  - Folge: 1 Pattern-Position übersprungen, aber Block-Pattern bleibt intern konsistent (slot_index advanced trotzdem).
- **Akzeptabel für Hobby-Tool:** Normal-CQ hat dasselbe Risiko seit v0.78, funktioniert. KISS.

### Hardware ANT1

- Vor jedem TX-Trigger setzt `encoder.transmit` zentral `radio.set_tx_antenna("ANT1")`. OMNI emittet keinen TX direkt.

### KISS

- Kein Frequenz-Recheck-Counter (V5 Sticky bleibt einfach: 1× am Anfang setzen, dann fest bis Stop).
- Kein 80-Cycles-Counter (Block-Rollover automatisch bei `slot_index 4 → 0`).
- Keine Pre-Block-State-Checks (CQ_WAIT etc.) — Toggle erlaubt nur in IDLE/CQ_WAIT (UX-Hilfe, bleibt aus aktuellem Code).

---

## 5. Nicht im Scope

- ❌ Änderungen an `core/encoder.py` — atomare API ist fertig (C3)
- ❌ Änderungen an `core/qso_state.py` — kein cq_mode-Hack
- ❌ Änderungen am Listener-Pfad in `mw_cycle.on_message_decoded` (C6 ist korrekt)
- ❌ Änderungen am Hunt-Pfad — `qso_state.start_qso` bleibt
- ❌ Frequenz-Recheck / Sticky-Gap-Algo zur Laufzeit (V5: 1× am Start, dann fest)
- ❌ 80-Cycles-Counter / Block-Cycle-Counter (war alte Spec, Mike: Block-Rollover bei slot_index 4→0)
- ❌ `cycle_tick`-basierter Pretrigger (war v0.95.24/25 Versuch, ist obsolet)

---

## 6. Testbarkeit

### Unit-Tests `tests/test_omni_cq_signal.py` (NEU, ~20 Tests)

| # | Test |
|---|------|
| T1 | `test_initial_state_inactive` |
| T2 | `test_start_initializes_block1_pos0` |
| T3 | `test_block1_pos0_is_tx_even` (parametrize) — `on_cycle_start` ruft `encoder.transmit(tx_even=True, audio_freq_hz=1500)` |
| T4 | `test_block1_pos1_is_tx_odd` |
| T5 | `test_block1_pos2_3_4_no_tx_emit_horche` |
| T6 | `test_block1_rollover_to_block2_pos0_is_tx_odd` |
| T7 | `test_block2_pos1_is_tx_even` |
| T8 | `test_block2_rollover_back_to_block1` |
| T9 | `test_block_alternation_permanent` (10 Slots → Block 1 → 2 → 1 → 2) |
| T10 | `test_pause_freezes_state` |
| T11 | `test_resume_after_qso_even_chooses_block2_pos0` |
| T12 | `test_resume_after_qso_odd_chooses_block1_pos0` |
| T13 | `test_stop_resets_state` (parametrize alle 7 reasons) |
| T14 | `test_freq_init_from_diversity` |
| T15 | `test_freq_fallback_1500_when_none` |
| T16 | `test_freq_sticky_during_omni` (5 cycle_starts → encoder.transmit mit selber Frequenz) |
| T17 | `test_freq_reset_on_stop` |
| T18 | `test_no_tx_when_paused` |
| T19 | `test_no_tx_when_inactive` |
| T20 | `test_encoder_busy_no_state_advance` (transmit returnt False → counter nicht inkrementiert, slot_index advanced trotzdem damit Pattern weiterläuft) |

### Integration-Tests `tests/test_omni_cq_integration.py` (existing 14 Tests aus C6)

Migrationen wo nötig (Worker-Lifecycle-Tests → Signal-Aufrufe). Größtenteils unverändert, da OmniCQ-API (start, stop, pause, resume_after_qso, is_active, is_paused) gleich bleibt.

### Field-Test (Mike, vor Push)

- 10-Slot-Loop: Pattern korrekt, KEIN Drift wie v0.96.0
- Block-Wechsel automatisch nach 5 Slots
- CQ-Antwort: OMNI pausiert, QSO startet, nach RR73 Resume mit Block-Wahl
- Stop-Trigger: Bandwechsel, Modus-Wechsel, RX-Mode-Wechsel, manual_halt, totmann

---

## 7. Vorteile gegenüber v0.96.0 Worker-Thread

| Aspekt | v0.96.0 (kaputt) | V5 (signal-basiert) |
|--------|------------------|---------------------|
| Slot-Sync | eigene Worker-Sleeps | `cycle_start`-Signal vom Timer |
| TX-Timing | eigene Boundary-Berechnung | Encoder-Thread (wie Normal-CQ) |
| Code-Größe | ~340 Zeilen | ~80-120 Zeilen |
| Threads | eigener OmniCQWorker | keiner |
| Race-Risiko | hoch (sleep_dur=0 Bug) | minimal (alles im GUI-Thread) |
| Testbarkeit | Worker-Mock (kritischer Pfad versteckt) | direkter Method-Call |
| Decoder-Blockade-Risiko | Worker robust | wie Normal-CQ (akzeptabel) |

---

## 8. Mike-Freigabe-Punkte

- Pattern verbindlich: Block 1 = TX-E, TX-O, RX-E, RX-O, RX-E ✓
- Block 2 = TX-O, TX-E, RX-O, RX-E, RX-O ✓
- Beim Toggle-Start: immer Block 1 (Even-First) — bestätigen
- Frequenz V5 KISS: 1× am Start setzen, dann fest, kein Recheck — bestätigen (Mike's Original-Spec sagte „Bleibt fest. Kein Versatz, kein Springen.")
- Block-Rollover: automatisch nach 5 Slots (kein 80-Cycles-Counter) — bestätigen
- Bei QSO-Ende: Block-Wahl nach last_was_even — bestätigen

---

**Ende V1.**
