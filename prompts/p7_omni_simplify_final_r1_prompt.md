# Final-R1-Review — P7.OMNI-SIMPLIFY (v0.96.4)

Du bist DeepSeek-Reasoner (R1). Reviewer fuer den fertig committeten
Code von **P7.OMNI-SIMPLIFY** in SimpleFT8.

## Kontext

Mike-Spec 10.05.2026: Diversity ist UNANTASTBAR. P5 (Pending-Queue) und
P6 (Pair-Audio) verbiegten Encoder/Diversity. P7 aendert Pattern statt
Encoder/Diversity:

- OMNI = Single-Slot-CQ in EINER Paritaet
- Wechsel ueber existierenden Diversity-Such-Counter alle ~10 Min
- Mess-Phase-Schutz: kein TX waehrend Diversity-Mess

## 6 atomare Commits

| C | Commit | Files | Effekt |
|---|---|---|---|
| C1 | `ac254a5` encoder.py P5+P6 zurueckrollen | core/encoder.py | -272 Zeilen |
| C2 | `3f98caf` omni_cq.py radikal vereinfachen | core/omni_cq.py | -59 Zeilen (305 -> 246) |
| C3 | `741f526` mw_cycle Such-Trigger-Hook | ui/mw_cycle.py | +5 Zeilen |
| C4 | `332c9f8` main_window Signal+Statusbar | ui/main_window.py | +29/-21 Zeilen |
| C5 | `956ef61` Tests T1-T14 + alte raus | tests/* | -524 Zeilen netto |
| C6 | `3111cfe` APP_VERSION 0.96.3 -> 0.96.4 | main.py:16 | 1 Zeile |

**Tests-Bilanz:** 1024 -> 1008 gruen (+3 Bonus ueber V3-Plan).

## Deine Aufgabe (Push-Bewertung)

Pruefe ob der Code **merge-bereit** ist. Konkret:

### 1. P5+P6-Rueckrollung in `core/encoder.py` (KRITISCH)

- Sind alle Pending/Pair-Reste sauber raus?
- Bleiben P1.9-Replace-Mechanik + abort + _next_slot_boundary intakt?
- transmit() returnt False bei busy (vor v0.96.2 Verhalten)?

### 2. `core/omni_cq.py` Single-Slot-Implementation (KRITISCH)

- Fresh-Compute is_even aus time.time() korrekt? (V2-L9 / R1-SF-2)
- Mess-Phase-Skip korrekt? (V2-L12)
- on_search_trigger Defense-in-Depth `_paused`-Check drin? (R1-SF-1)
- flip_tx_parity no-op bei _cq_tx_even=None? (AC7)
- Stop reset alle States?
- Race zwischen on_cycle_start und on_search_trigger? (R1 hat in V3-Review gesagt: kein Lock noetig weil GUI-Thread)

### 3. `ui/mw_cycle.py` Hook (KRITISCH)

- Hook-Stelle nach `tick_slot() == True` im `_diversity_lock`-Block?
- hasattr-Guard fuer Test-Setups?
- Pausiert bei QSO automatisch via `reset_search_counter()`?

### 4. `ui/main_window.py` UI (SOLLTE)

- Signal-Connect `cq_count_changed` + `parity_flipped` korrekt?
- Statusbar `Ω CQ=X (E/O/—)` korrekt?
- _on_omni_slot_action ist no-op (P7-Verhalten)?

### 5. Tests (SOLLTE)

- Alle 14 ACs durch T1-T14 + Bonus-Tests abgedeckt?
- KEIN Worker/Sleep/Boundary-Mock?
- Edge-Cases: pause + flip, stop + on_search_trigger, busy-encoder?

### 6. Out-of-Scope-Compliance (SOLLTE)

V3 §9 verbietet:
- ❌ Diversity-Logik aendern
- ❌ should_remeasure / start_measure / tick_slot Logik
- ❌ Normal-CQ-Pfad
- ❌ P8 (Mess-Status-Dialog)
- ❌ Re-Mess-Intervall

Wurde was davon angefasst?

### 7. Hardware-Garantie ANT1 (KRITISCH)

OMNI ruft `encoder.transmit(...)` ohne explizite Antennen-Setzung —
greift `_tx_worker_inner` weiter `radio.set_tx_antenna("ANT1")` zentral?

## Format

Strukturiert in 5 Sektionen:

- **§A — Encoder-Rueckrollung** (Aufgabe 1)
- **§B — omni_cq + Hook + UI** (Aufgabe 2+3+4)
- **§C — Tests + Compliance** (Aufgabe 5+6)
- **§D — Hardware ANT1** (Aufgabe 7)
- **§E — Empfehlung** (KRITISCH/SOLLTE-FIX/KOENNTE pro Finding +
  finale Zeile „Push freigegeben" ODER „Push blockiert weil X")

## KISS-Gebot

SimpleFT8 ist Hobby-Tool. Keine Komplexitaets-Vorschlaege ausser
KRITISCH fuer Korrektheit. Mike-Spec: Diversity unantastbar.

## Beigefuegte Files

- `core/encoder.py` (nach C1)
- `core/omni_cq.py` (nach C2)
- `core/diversity.py` (NICHT angefasst, fuer Verifikation)
- `ui/mw_cycle.py` (nach C3)
- `ui/main_window.py` (nach C4)
- `tests/test_omni_cq_signal.py` (nach C5)
- `tests/test_omni_cq_integration.py` (nach C5)
- `prompts/p7_omni_simplify_v3.md` (Spec)

---

**Dein Output landet in `prompts/p7_omni_simplify_final_r1.md`.**
