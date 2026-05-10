# Final-R1-Review — P5.OMNI-PATTERN-FIX-3 (v0.96.2)

Du bist DeepSeek-Reasoner (R1). Reviewer fuer den fertig committeten
Code von **P5.OMNI-PATTERN-FIX-3** in SimpleFT8 (Hobby-Funker-Tool).

## Kontext (kurz)

Field-Test 10.05.2026 nach v0.96.1 (P4-V5 Signal-Refactor) zeigte 2 Issues:

- **Issue B (kritisch):** Pos 1 (TX nach TX) im OMNI-5-Slot-Pattern
  TX-TX-RX-RX-RX war IMMER encoder-busy (3× im Log reproduziert).
- **Issue A (kosmetisch):** RX-Display zeigte Wall-Time `time.time()`
  statt UTC-Slot-Boundary `:00`/`:15`/`:30`/`:45`.

**Wurzel B (R1-bestaetigt im V2-Review):** FT8 12.64s Audio + 1.3s
FlexRadio-Buffer-Drain + PTT-Off + Jitter → `_is_transmitting=False`
faellt :42.8-:44.5. Pos 1 cycle_start :45 hat oft <1s Race-Window.

**Loesung Variante A (R1-Empfehlung im V2-Review):** Encoder-Pending-Queue
mit Verfall-Schwelle `1.5 * cycle_duration`. `_pending_tx +
_pending_queued_at` UNTER `_replace_lock` (R1-KRITISCH gegen Race).

**Cold-Start-Test entdeckte F1-KRITISCH (vor Code):** abort-Race im
Pending-Loop. `_run_one_tx_pass` cleart `_abort_event` und setzt
`_is_transmitting=True` — wuerde abort() ueberschreiben. Fix:
`if self._abort_event.is_set(): return` VOR Re-Trigger.

## Was geschah (5 atomare Commits)

| # | Commit | Files |
|---|---|---|
| C1 | `229e98c` Pending-Queue + Verfall + Abort-Schutz | `core/encoder.py` |
| C2 | `96f5714` Tests T1, T9-T13 (8 Tests inkl. Stress + Code-Inspect) | `tests/test_encoder_pending.py` (NEU) |
| C3 | `333411a` Slot-Boundary in `add_listening` (Issue A) | `ui/main_window.py` |
| C4 | `955aeb0` Tests T7, T8 (parametrize) + T2N (Pending-Counter) | `tests/test_main_window_slot_boundary.py` (NEU) + `tests/test_omni_cq_signal.py` (erweitert) |
| C5 | `31f2f41` APP_VERSION 0.96.1 → 0.96.2 | `main.py:16` |

**Tests-Bilanz:** 1020 → 1034 gruen (+14, V3 prognostizierte ~1029).

## Deine Aufgabe (eng fokussiert)

Pruefe ob der Code **merge-bereit** ist. Konkret:

### 1. Pending-Loop in `core/encoder.py` (KRITISCH)

Ist die Loop in `_tx_worker` racefrei + abort-sicher?

- `_pending_tx` UND `_pending_queued_at` werden UNTER `_replace_lock`
  gesetzt + gelesen — siehe `transmit()` Z. ~218-228 + `_tx_worker` Z. ~246-251.
- `if self._abort_event.is_set(): return` direkt VOR Re-Trigger — F1-Fix.
- `_run_one_tx_pass` als ausgelagerter Single-Pass (1:1 was vorher
  inline im `_tx_worker` stand).
- `_compute_target_slot` spiegelt `_next_slot_boundary`-Logik mit
  externen `slot_dur`.

Suche nach:
- Race zwischen `transmit()` und `_tx_worker`-Loop
- abort-Verlust trotz F1-Fix
- TOCTOU im Pending-Pop (Lock-Boundary korrekt?)
- Verfall-Schwelle `1.5 * cycle_duration` — passt sie?
- Stack/Loop-Korrektheit bei Multi-Pendings

### 2. Slot-Boundary-Fix in `ui/main_window.py:760-770` (KOSMETISCH)

Ist die Berechnung `(now // slot_dur) * slot_dur` korrekt fuer alle
Modi (FT8 15s, FT4 7.5s, FT2 3.8s)? Floating-Point-Falle (z.B. 3.8 ist
binaer-ungenau)?

### 3. Tests (`tests/test_encoder_pending.py` + `test_main_window_slot_boundary.py`)

- T11a Code-Inspektion robust gegen Refactor?
- T11b Stress-Test deterministisch oder flaky-Risiko?
- T13 prueft wirklich Abort-Pfad (nicht Verfall-Pfad)?
- T7/T8 nutzt `(now // slot_dur) * slot_dur` korrekt fuer FT2 (3.8s
  binaer)?
- T2N komplementaer zu existing Z. 401 (Mock-True vs Mock-False)?

### 4. Out-of-Scope (Compliance)

V3 §9 verbietet:
- ❌ Frequenz-Recheck zur Laufzeit
- ❌ qso_state-Aenderungen
- ❌ Listener-Pfad in `mw_cycle.on_message_decoded`
- ❌ Diversity-Antennen-Switch
- ❌ Auto-Hunt-Coupling
- ❌ AP-Lite, OMNI-Stop-Reasons, btn_omni_cq-UI

Wurde was davon angefasst? `git diff` der 5 Commits.

### 5. Hardware-Garantie ANT1

`encoder.transmit` setzt zentral `radio.set_tx_antenna("ANT1")` in
`_tx_worker_inner` Z. 363. Pending-Pfad nutzt `_run_one_tx_pass` →
`_tx_worker_inner` → ANT1-Setter laeuft trotzdem. Bestaetige.

## Format

Strukturiert in 5 Sektionen:

- **§A — Pending-Loop Race/Abort/TOCTOU** (Aufgabe 1)
- **§B — Slot-Boundary-Fix** (Aufgabe 2)
- **§C — Test-Robustheit** (Aufgabe 3)
- **§D — Out-of-Scope-Compliance + ANT1** (Aufgabe 4+5)
- **§E — Empfehlung** (KRITISCH/SOLLTE-FIX/KOENNTE — pro Finding +
  Code-Snippet wenn KRITISCH; finale Zeile „Push freigegeben" ODER
  „Push blockiert weil X")

## KISS-Gebot

SimpleFT8 ist Hobby-Tool, nicht Contest-Tool. Keine Komplexitaets-
Vorschlaege (Multi-Threading-Refactor, neue Module, neue Abstraktionen)
ausser sie sind KRITISCH fuer Korrektheit.

## Beigefuegte Files

- `core/encoder.py` (komplett)
- `ui/main_window.py` (komplett)
- `tests/test_encoder_pending.py` (komplett, NEU)
- `tests/test_main_window_slot_boundary.py` (komplett, NEU)
- `tests/test_omni_cq_signal.py` (komplett, T2N am Ende)
- `prompts/p5_omni_pattern_fix3_v3.md` (V3-Plan)

Lies V3 zuerst, dann den Code, dann antworte.

---

**Dein Output landet in `prompts/p5_omni_pattern_fix3_final_r1.md`.**
