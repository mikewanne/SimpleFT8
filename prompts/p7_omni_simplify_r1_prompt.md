# Auftrag an DeepSeek-Reasoner (R1) — P7.OMNI-SIMPLIFY

Du bist Code-Reviewer fuer **P7.OMNI-SIMPLIFY** in SimpleFT8.

## Kontext (kurz)

SimpleFT8 ist ein Hobby-Funker-Tool (KEIN Contest-Tool) fuer FT8/FT4/FT2.
v0.96.3 (P6.OMNI-DOUBLE-AUDIO) hat das OMNI-Pos-1-Race-Problem versucht zu loesen
durch Audio-Concatenation (2 TX zu einem PTT-Cycle). **Field-Test 10.05.2026 zeigte:**

- **Diversity wird waehrend OMNI-Pair-TX (27.6s) blockiert** (`mw_cycle.py:595` TX-Schutz)
- Mike-Beobachtung: „nur eine Antenne" — **Diversity-Antennen-Switching effektiv tot waehrend OMNI**
- Mike-Spec ist klar: **Diversity ist UNANTASTBAR**, das ist der Kern-USP

## Mike's neue Idee (P7)

**OMNI = Single-Slot-CQ in EINER Paritaet, Wechsel ueber existierenden Such-Counter.**

- OMNI sendet CQ in EINER Paritaet (Even ODER Odd) — wie WSJT-X mit Even-Toggle
- Wechsel-Trigger: Diversity hat einen **Such-Trigger** (`_search_slots_remaining`) der alle ~60s
  feuert (FT8: 4 Slots × 15s). Pausiert bei QSO automatisch (existing).
- OMNI haengt Counter: 10× Such-Trigger → flip Paritaets-Wechsel → ~10 Min Wechsel-Intervall
- Diversity-Re-Mess (90s alle 1h): OMNI sendet **nicht** waehrend (saubere Mess-Phase)
- Frequenz sticky ueber Paritaets-Wechsel hinweg

## Vorgeschichte

- **P5 (v0.96.2):** Encoder-Pending-Queue. Field-Test: Pending-Verfall (29.8s > 22.5s) → Pos 1 nie gesendet. Pattern halb tot.
- **P6 (v0.96.3):** Pair-Audio (2 TX zu 1 PTT-Cycle). Field-Test: Pos 0 + Pos 1 senden korrekt, aber Diversity blockiert 28s.
- Beide Workarounds verbiegen Encoder/Diversity um TX-TX-konsekutiv zu retten.
- **P7:** Pattern aendern statt Encoder/Diversity verbiegen.

## Plan-Files

- `prompts/p7_omni_simplify_v1.md` — V1 (initialer Plan)
- `prompts/p7_omni_simplify_v2.md` — V2 (Self-Review, 12 Lessons)
- `prompts/p7_omni_simplify_v3.md` — **V3 Compact-fest, EINZIGE WAHRHEIT fuer Code**

V3 ist die Hauptquelle. Lies V3 zuerst, dann V2-Lessons, dann den Code.

## Deine konkreten Aufgaben

### 1. Spec-Bewertung (Pflicht)

V3 §2 beschreibt die neue Spec. Pruefe:

- Ist „Wechsel alle 10 Min via Such-Counter" ein robuster Trigger?
- Coverage-Luecke: 10 Min auf einer Paritaet = 50% Stationen hoeren OMNI 10 Min nicht. Akzeptabel fuer Hobby-Funker?
- Edge-Cases mit QSO-Pause des Such-Counters (existing in mw_cycle.py:158)

### 2. Architektur-Review `core/omni_cq.py` (Pflicht)

V3 §4.2 enthaelt die KOMPLETTE neue omni_cq.py (~210 Zeilen). Pruefe:

- Ist `_cq_tx_even = fresh_is_even` beim ersten on_cycle_start sauber?
- Race-Condition: GUI-Thread ruft `on_cycle_start` UND `on_search_trigger`. Beide modifizieren `_search_trigger_count` und `_cq_tx_even`. Brauchen wir ein Lock?
- `flip_tx_parity` ist public — vorgesehen fuer manuellen UI-Trigger spaeter. Ist die Sichtbarkeit korrekt?
- Was wenn `_diversity.phase` mid-on_cycle_start auf "measure" wechselt (Race)?
- Counter-Reset bei stop() korrekt?

### 3. Encoder-Rueckrollung (Pflicht)

V3 §4.1 rollt `core/encoder.py` zurueck auf vor v0.96.2:
- transmit_pair, _tx_pair_worker, _tx_pair_inner WEG
- _pending_tx, _pending_queued_at, Pending-Loop in _tx_worker WEG
- _run_one_tx_pass, _compute_target_slot WEG

Pruefe:

- Bestehende Aufrufer (mw_qso `_on_send_message`, OMNI's `transmit()`) bleiben kompatibel?
- P1.9-Replace-Mechanik (`request_replace`, `_replace_message`, `_replace_lock`) UNVERAENDERT?
- `_next_slot_boundary` bleibt drin und wird genutzt?
- Tests die `_is_transmitting=True` direkt setzen (test_modules.py Z. 710/2582/2648/2690/2823, test_p1_9_replace.py Z. 37/49) bleiben gruen?

### 4. mw_cycle Hook (Pflicht)

V3 §4.3 fuegt `_omni_cq.on_search_trigger()` direkt nach `tick_slot() == True` ein.

- Ist der Hook-Punkt korrekt (innerhalb `_diversity_lock`)?
- Was wenn `_omni_cq` nicht aktiv ist? Counter zaehlt trotzdem? V3 sagt OMNI-Methode `on_search_trigger` no-op wenn `not _active` — ok.
- Was wenn `tick_slot()` False returnt aber `_search_trigger_count` schon > 0? Bleibt einfach stehen bis naechster Trigger — ist OK, oder?

### 5. Out-of-Scope-Compliance (Pflicht)

V3 §9 verbietet:
- ❌ Diversity-Logik aendern
- ❌ should_remeasure / start_measure / tick_slot Logik
- ❌ Normal-CQ-Pfad
- ❌ P8 (Mess-Status-Dialog)
- ❌ Re-Mess-Intervall

Wurde was davon angefasst im Diff?

### 6. Test-Plan-Review (Pflicht)

V3 §7 schreibt 13 neue Tests (T1-T13) + DELETE test_encoder_pending.py + REWRITE test_omni_cq_signal.py. Pruefe:

- Decken T1-T13 alle Akzeptanzkriterien AC1-AC19 ab?
- Lesson `feedback_test_critical_path_not_mock.md` eingehalten? (kein Worker/Sleep/Boundary-Mock)
- Welche Edge-Case-Tests fehlen? (z.B. flip waehrend pause? on_search_trigger waehrend stop?)

### 7. Robustheit-Review (Pflicht)

V2-L9 schlaegt vor: `is_even` FRESH neu berechnen aus `time.time()` in `on_cycle_start`. V3 baut das ein.

Begruendung: P6-Field-Test zeigte 14s-Latenz im signal-target_even — vermutlich GUI-Thread-Last. Quick-Fix in main_window war Fresh-Compute.

Pruefe:
- Ist Fresh-Compute robust gegen NTP-Drift, DST-Wechsel, Clock-Jumps?
- Was wenn `time.time()` und Diversity's `is_even` widerspruechlich sind?
- Macht der Fresh-Compute den ursprunglichen `is_even`-Parameter obsolet?

### 8. Risiken (Pflicht)

V3 §12 listet R1-R8. Pruefe ob fehlend:

- Risiko: Ist `_cq_tx_even=None` Initial-State sicher gegen Race wenn flip_tx_parity vor erstem on_cycle_start gerufen wird? V3 hat AC7 (no-op).
- Risiko: Encoder-Rueckrollung könnte Drift-Guard-Verhalten in `_tx_worker_inner` aendern?
- Risiko: Was wenn Mike OMNI startet waehrend Diversity gerade in measure-Phase ist? V3 sagt no-op.

## Format deiner Antwort

Strukturiert in 6 Sektionen:

- **§A — Spec-Review** (Aufgabe 1)
- **§B — Code-Review omni_cq + Encoder-Rollback** (Aufgabe 2+3)
- **§C — Hook-Stelle + Out-of-Scope** (Aufgabe 4+5)
- **§D — Test-Plan-Review** (Aufgabe 6)
- **§E — Robustheit + Risiken** (Aufgabe 7+8)
- **§F — Empfehlung** (KRITISCH/SOLLTE-FIX/KOENNTE pro Finding + Snippet wenn KRITISCH; finale Zeile „V3 freigegeben fuer Code" ODER „V3 blockiert weil X")

## KISS-Gebot

SimpleFT8 ist Hobby-Tool. Keine Komplexitaets-Vorschlaege (Multi-Threading-Refactor,
neue Module, neue Abstraktionen) ausser sie sind KRITISCH fuer Korrektheit.
Mike-Spec: Diversity unantastbar.

## Beigefuegte Files

- `core/encoder.py` (aktueller v0.96.3-Stand mit P5+P6, wird zurueckgerollt)
- `core/omni_cq.py` (aktueller v0.96.3-Stand mit Pair-Logik, wird komplett neu)
- `core/diversity.py` (NICHT angefasst, nur fuer Such-Trigger-Verifikation)
- `ui/mw_cycle.py` (Hook-Stelle Z. 160)
- `ui/main_window.py` (Signal-Connect + Statusbar)
- `prompts/p7_omni_simplify_v1.md`
- `prompts/p7_omni_simplify_v2.md`
- `prompts/p7_omni_simplify_v3.md` (Hauptquelle)

Lies V3 zuerst, dann den Code.

---

**Dein Output landet in `prompts/p7_omni_simplify_r1.md`.**
