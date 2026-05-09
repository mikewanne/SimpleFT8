# P2.OMNI-REDESIGN — Session-Context für Compact #3 (Pre-Implementation)

**Datum:** 2026-05-09
**Stand:** V3 fertig + Mike-Freigabe ✅, vor Compact #3
**Ziel:** Implementation nach Compact #3 starten — alle Vorarbeit gesichert.

---

## 1. Workflow-Stand

| Phase | Datei | Stand |
|---|---|---|
| V1 | `prompts/p2_omni_redesign_v1.md` | ✅ |
| V2 (Self-Review, 15 Lessons) | `prompts/p2_omni_redesign_v2.md` | ✅ |
| R1-Lauf-1 (initial, voll) | `prompts/p2_omni_redesign_r1_lauf1_full.md` | ✅ |
| R1-Lauf-2 (partiell, truncated) | `prompts/p2_omni_redesign_r1_lauf2_truncated.md` | ✅ |
| R1-V2 (DeepSeek-Reasoner, 304 Z.) | `prompts/p2_omni_redesign_r1_v2.md` | ✅ |
| V3 (Compact-fest, 15 ACs, 20 Tests, 7 Commits) | `prompts/p2_omni_redesign_v3.md` | ✅ |
| Mike-Freigabe V3 | — | ✅ 09.05.2026 |
| **Compact #3** | — | ⏳ als nächstes |
| Implementation (7 Commits) | — | ⏳ nach Compact #3 |
| Final-R1 nach Code | `/tmp/r1_omni_v3_final.txt` | ⏳ |
| Field-Test Mike | — | ⏳ |
| Push (mit v0.95.16-22 + P2-Tool + P3) | — | ⏳ |

---

## 2. Bug-Wurzel (verifiziert)

`core/qso_state.py:177` setzt State VOR `send_message.emit()`:

```python
def _send_cq(self):
    ...
    self._set_state(QSOState.CQ_CALLING)   # Z.177 — VORHER
    self.send_message.emit(msg)            # Z.178 — NACHHER
```

OMNI-Filter (`mw_qso._on_send_message`) returnt bei RX-Slot ohne TX → State
ist bereits CQ_CALLING → `on_cycle_end()` triggert nicht mehr → CQ-Loop tot.

**Plus 8 Tage latent seit v0.78** (30.04.2026) — durch P1.OMNI-START
(v0.95.22) wurde der Toggle aktiv, der Bug wurde sichtbar nach 2 TX-Slots.

---

## 3. R1-V2 Findings — Volle Auswertung

R1-Source: `prompts/p2_omni_redesign_r1_v2.md` (DeepSeek-Reasoner, 304 Zeilen)

### 3.1 ⛔ KRITISCH

**K1 — `_on_try_replace_pending_tx` ohne OMNI-Pause** ✅ ANGENOMMEN

R1-Befund: `ui/mw_qso.py:727-778` (P1.9 Replace-Pfad) startet QSO ohne
`_omni_tx.pause()`. Folge: 4. QSO-Entry-Pfad inkonsistent zu den anderen
3 → kein Resume-Trigger nach QSO-Ende.

**V3-Lösung:**
- Helper `_pause_omni_if_active()` (DRY für 3 Entry-Pfade)
- Helper `_maybe_resume_omni()` (DRY für 3 Exit-Pfade)
- 4. Aufruf des Pause-Helpers in `_on_try_replace_pending_tx`

### 3.2 🟡 SOLLTE

**S1 — `_resume_cq_if_needed` Timing → 1 ungefilterter CQ** ❌ VERWORFEN als R1-Halluzination

R1-Behauptung (Z.204): „qso_state ruft `_resume_cq_if_needed` direkt auf,
BEVOR mw_qso das Signal verarbeitet."

**Code-Beweis Gegenteil:**
- `ui/main_window.py:597-599`: `qso_*.connect(self._on_qso_*)` ohne
  ConnectionType → `Qt.AutoConnection` → bei gleichem GUI-Thread
  → `Qt.DirectConnection`
- `core/qso_state.py:306-307` (+ Z.313-314, 341-342, 371-372, 388-389,
  642-643): `qso_timeout.emit(call); self._resume_cq_if_needed()` →
  bei DirectConnection läuft mw_qso-Listener KOMPLETT in Z.306, kehrt
  zurück, DANN Z.307. mw_qso macht OMNI-Resume vor `_send_cq()`.

**Kein ungefilterter CQ.** R1-Halluzination wegen falscher
Connection-Type-Annahme.

V3 dokumentiert diese DirectConnection-Annahme als Top-Kommentar in
`_resume_cq_if_needed` (R3-Risiko: künftige Multi-Thread-Refactors).

**S2 — `block_cycles`-Param komplett raus** ✅ ANGENOMMEN

V2 sagte „ignorieren oder Deprecation". V3 macht's klar:
- `core/omni_tx.py` Konstruktor: `OmniTX()` (kein Param)
- `OmniTX.get_instance()` (kein Param)
- Alle Aufrufer (siehe §6) auf parameterlosen Aufruf

**S3 — AC14 als Integrationstest** ✅ ANGENOMMEN

V3 §1.2 zeigt konkreten Test-Code mit echtem `qso_sm` + Listener-Mock.

### 3.3 🟢 KÖNNTE — Kosmetik (alle ANGENOMMEN)

- **L1:** Code-Kommentar an `_omni_skip_state_change` „GUI-Thread, kein Lock"
- **L8:** Code-Kommentar an `encoder.tx_even` „letzter Setter gewinnt — Design"
- **L13:** Docstring an `is_even_cycle()` „aktueller Zyklus, nicht nächster"

---

## 4. V3-Code-Änderungen — Kompakt-Übersicht

### `core/qso_state.py`
- `__init__`: `self._omni_skip_state_change: bool = False`
- `_send_cq()`: Flag-Pattern (siehe V3 §2.1)
- `_resume_cq_if_needed()`: S1-Doku-Top-Kommentar

### `core/omni_tx.py` — Hauptarbeit
**Raus:**
- `block_cycles`-Param aus `__init__`
- `block_cycles`-Param aus `get_instance` (Default 40 → 80 Inkonsistenz!)
- `_cycle_count`-Attribut (NUR omni_tx — ntp_time/timing bleiben!)
- `_pending_switch`-Attribut
- `qso_active`-Param aus `advance()`
- `enable()`-Methode

**Neu:**
- `start_with_parity_for_next_slot(next_is_even: bool)`
- `pause()` / `resume()` / `is_paused()`
- `advance()` ohne Args, Block-Switch automatisch bei rollover

### `core/encoder.py` + `core/timing.py`
Nur 1-Zeilen-Doku-Kommentare (L8, L13).

### `ui/mw_cycle.py`
`_on_cycle_start`: `if not _omni_tx.is_paused(): _omni_tx.advance()`

### `ui/main_window.py`
- `__init__`: `self._omni_was_active_pre_qso: bool = False`
- `_on_btn_omni_cq_toggled`: `start_with_parity_for_next_slot(next_is_even)` ersetzt `enable()` (Z.703)
- `_block_cycles = 80` Block + `get_instance(block_cycles=...)` Z.246-250 vereinfacht zu `get_instance()`
- `_on_omni_stopped`: unverändert aus P1.OMNI-START v0.95.22

### `ui/mw_qso.py`
- Helper `_pause_omni_if_active()` (DRY)
- Helper `_maybe_resume_omni()` (DRY)
- `_on_send_message`: Flag-Pattern (CQ-Pfad), `calls_made -= 1` raus
- `_on_station_clicked`: Helper-Aufruf
- `_on_tx_slot_for_partner`: Helper-Aufruf (nur wenn nicht courtesy)
- `_on_try_replace_pending_tx` (K1): Helper-Aufruf NEU
- `_on_qso_complete`/`_on_qso_confirmed`/`_on_qso_timeout`: `_maybe_resume_omni()` am Ende
- `_on_cancel`: bestehende HALT-Logik aus v0.95.22 bleibt

---

## 5. Mike's Designentscheidungen (chronologisch)

1. **09.05.2026 morgens:** Voller Refactor, kein Pflaster
2. **09.05.2026:** Block-Switch automatisch (slot_index 4→0), KEIN 80-Counter
3. **09.05.2026:** Während QSO pausiert OMNI (slot_index frozen)
4. **09.05.2026:** Block-Wahl bei Resume + Activate per next-slot-Parität
5. **09.05.2026:** 4-Sequencer-Architektur + shared QSO-Subroutine
6. **09.05.2026:** QSO ist heilig, nur HALT unterbricht
7. **09.05.2026:** OMNI bleibt Diversity-only (Mode-Wechsel zu Normal stoppt)
8. **09.05.2026 nach R1-V2:** „passt, bereite alles vor bis Compact #3"

---

## 6. Pre-Implementation Code-Verifikationen (09.05.2026)

### 6.1 `OmniTX(block_cycles=...)` Aufrufer-Inventar

**Production-Code:**
- `core/omni_tx.py:44` (Doku-String-Beispiel)
- `core/omni_tx.py:57` (`__init__(self, block_cycles: int = 80)`)
- `core/omni_tx.py:67` (`self.block_cycles: int = max(10, block_cycles)`)
- `core/omni_tx.py:228-232` (`get_instance(block_cycles: int = 40)` ⚠️ Inkonsistent zu __init__-Default 80!)
- `ui/main_window.py:246-250` (`_block_cycles = 80; get_instance(block_cycles=_block_cycles)`)
- `ui/main_window.py:703` (`self._omni_tx.enable()` — durch start_with_parity_for_next_slot ersetzen)

**Test-Code (zu migrieren):**
- `tests/test_omni_tx.py`: 9 Konstruktor-Aufrufe + 9× `enable()` — **GANZE DATEI Migration**
- `tests/test_p1_omni_start.py`: 1 Konstruktor + 6× `enable()` — Migration einfach
- `tests/test_modules.py`: 7 Konstruktor + 5× `enable()` (Z.65-111 + Z.1526-1550) — partielle Migration
- `tests/test_patterns.py`: 4 Konstruktor + 4× `enable()` (Z.305-347) — Migration

### 6.2 `_cycle_count` Disambiguation
- `core/omni_tx.py`: 5 Treffer → ALLE RAUS
- `core/ntp_time.py`: 9 Treffer → BLEIBEN (NTP-Zähler, NICHT OMNI!)
- `core/timing.py`: 3 Treffer → BLEIBEN (Timing-Zähler, NICHT OMNI!)
- `tests/test_modules.py:655,672,1364`: NTP-bezogen, BLEIBEN

### 6.3 `_pending_switch` ist OMNI-only
Sicher zu entfernen aus `core/omni_tx.py` + `tests/test_omni_tx.py` + `tests/test_modules.py:1526-1550`.

### 6.4 `is_even_cycle` Aufrufer
- `core/timing.py:57` (Definition) — Docstring L13 erweitern
- `ui/mw_cycle.py:184` (`fallback_even`) — bleibt
- `ui/mw_qso.py:193,310` (User-CQ + ?) — bleibt
- `tests/test_slot_display.py:91,133` (Mock + Test) — bleibt
- `tests/test_auto_hunt_extended.py:237` (Doku-Kommentar) — bleibt
- **NEU V3:** `_on_btn_omni_cq_toggled` + `_maybe_resume_omni` nutzen es

---

## 7. Implementation-Plan (7 atomare Commits)

| # | Commit-Titel | Files | Begründung |
|---|---|---|---|
| 1 | `OMNI-Redesign: core/omni_tx.py Refactor` | `core/omni_tx.py` | Neue API ohne block_cycles, start_with_parity_for_next_slot, pause/resume |
| 2 | `OMNI-Redesign: qso_state.py Flag-Pattern` | `core/qso_state.py` | _send_cq State-Wechsel nach emit + Flag, _resume_cq_if_needed Doku |
| 3 | `OMNI-Redesign: Doku-Kommentare timing/encoder` | `core/timing.py`, `core/encoder.py` | L8/L13 Kosmetik |
| 4 | `OMNI-Redesign: mw_qso.py Helper + 3 Entry- + 3 Exit-Pfade` | `ui/mw_qso.py` | DRY-Helpers, K1-Fix, Flag-Pattern Listener |
| 5 | `OMNI-Redesign: main_window/mw_cycle Anpassungen` | `ui/main_window.py`, `ui/mw_cycle.py` | _omni_was_active_pre_qso, _on_btn_omni_cq_toggled, Pause-Check |
| 6 | `OMNI-Redesign: Tests migrieren + neue Tests` | 5 Test-Files | API-Migration + 20 neue Tests in test_p2_omni_redesign.py |
| 7 | `OMNI-Redesign: APP_VERSION 0.95.23 + Doku` | `main.py`, HISTORY.md, HANDOFF.md, CLAUDE.md | Version-Bump + 4-Datei-Update |

---

## 8. Test-Strategie — 20 NEUE Tests

Datei: `tests/test_p2_omni_redesign.py`

| # | Test | Deckung |
|---|---|---|
| T1 | `test_block_1_pattern` | AC1 |
| T2 | `test_block_2_pattern` | AC2 |
| T3 | `test_block_switch_on_rollover` | AC3 |
| T4 | `test_start_with_parity_next_even_block_1` | AC10 |
| T5 | `test_start_with_parity_next_odd_block_2` | AC10 |
| T6 | `test_pause_freezes_slot_index` | AC4 |
| T7 | `test_resume_after_pause` | AC5 |
| T8 | `test_advance_skipped_when_paused` | AC4 |
| T9 | `test_send_cq_with_omni_rx_slot_no_state_change` | **AC14 K1-Beweis** |
| T10 | `test_omni_skip_state_change_flag_resets` | AC13 |
| T11 | `test_omni_pause_on_station_clicked` | Hunt-Entry |
| T12 | `test_omni_pause_on_cq_reply_via_tx_slot_for_partner` | CQ-Reply-Entry |
| T13 | **`test_omni_pause_on_try_replace_pending_tx`** | **AC15 K1-NEU** |
| T14 | `test_omni_resume_after_qso_complete_empty_queue` | AC5 |
| T15 | `test_omni_resume_after_qso_confirmed_empty_queue` | AC5 |
| T16 | `test_omni_resume_after_qso_timeout_empty_queue` | AC5 |
| T17 | `test_omni_no_resume_with_caller_queue_pending` | AC12 |
| T18 | `test_halt_stops_omni_no_resume` | AC7 |
| T19 | `test_block_cycles_constant_removed` | AC11 |
| T20 | `test_get_instance_no_block_cycles_param` | S2 Singleton-API |

**Test-Count Erwartung:** 1014 → 1034 (+20 NEU). Plus Migration der ~25 alten OMNI-Tests in test_omni_tx/test_p1_omni_start/test_modules/test_patterns.

---

## 9. R1-Final-Befehl (nach Implementation)

```bash
cd "/Users/mikehammerer/Documents/KI N8N Projekte/FT8/SimpleFT8"
cat prompts/p2_omni_redesign_v3.md | ./venv/bin/python3 tools/deepseek_review.py \
  core/omni_tx.py core/qso_state.py core/timing.py core/encoder.py \
  ui/main_window.py ui/mw_qso.py ui/mw_cycle.py \
  tests/test_p2_omni_redesign.py \
  > /tmp/r1_omni_v3_final.txt
```

---

## 10. Trigger-Phrasen für nach Compact #3

- **„weiter mit OMNI-Redesign Code"** → V3 lesen → Plan-Mode → 7 atomare Commits
- **„OMNI-Redesign Final-R1"** → R1-Befehl §9 ausführen
- **„OMNI-Redesign Field-Test"** → Mike-Field-Test mit FlexRadio, OMNI-CQ-Loop > 5 Slots beweist Bug-Fix

---

## 11. Risikoliste

| # | Risiko | Mitigation |
|---|---|---|
| R1 | Helper `_pause_omni_if_active()` Pfad zu `_main_window`-Reference | Plan-Mode entscheidet — Pre-Flag in mw_qso oder MainWindow |
| R2 | DirectConnection-Annahme bricht in künftigem Multi-Thread-Refactor | L1-Kommentar dokumentiert Annahme |
| R3 | Bestehende OMNI-Tests die `enable()`/`block_cycles` mocken brechen | Commit 6 migriert vor Tests-Run |
| R4 | OMNI-Toggle 2× schnell hintereinander (Reentrancy) | V2 L14: GUI-Thread synchron, kein Race |
| R5 | Field-Test deckt 5. Entry-Pfad auf | Final-R1 + Mike-Field-Test |
| R6 | `_caller_queue` füllt sich während QSO endet | V2 L6: GUI-Thread synchron |
| R7 | `start_with_parity_for_next_slot` aus Resume während OMNI noch nicht ganz pausiert | Idempotent: `_active=True`+`_paused=False` setzt sauber neu |

---

## 12. Was V3 NICHT macht (bewusst Out-of-Scope)

- ❌ Encoder.transmit-Refactor
- ❌ `tx_started`-Signal-Migration (Variante A — Thread-Race)
- ❌ Threading-Modell-Änderungen
- ❌ OMNI-Visualisierung (Slot-Pattern als UI-Kachel) — separates Feature
- ❌ Statistik-Logging für OMNI-Slot-Effizienz — Hobby-Tool, OoS

---

## 13. Wichtigste Mike-Zitate (chronologisch)

- 09.05. morgens: „Voller Refactor, kein Pflaster"
- 09.05.: „Block-Switch automatisch wenn slot 4→0 — kein 80-Counter"
- 09.05.: „Block 1 wenn next slot Even, Block 2 wenn next slot Odd"
- 09.05.: „4-Sequencer-Architektur: Normal-CQ, OMNI-CQ, Auto-Hunt, Manual + shared QSO-Subroutine"
- 09.05.: „QSO ist heilig — nur HALT unterbricht"
- 09.05. (nach R1-V2): „ja passt bereite alles bitte vor bis compact 3"
- 09.05. (auf Frage „durchgegangen"): „du hast mich heute so verunsichert deshalb muss ich alles 100 mal hinterfragen"

---

## 14. Files-Inventar (alle OMNI-Redesign-Dateien)

**Plan-Files (`prompts/`):**
- `p2_omni_redesign_v1.md` — initialer Plan
- `p2_omni_redesign_v2.md` — Self-Review mit 15 Lessons
- `p2_omni_redesign_r1_lauf1_full.md` — R1-Lauf 1 (initial, voll)
- `p2_omni_redesign_r1_lauf2_truncated.md` — R1-Lauf 2 (partiell)
- `p2_omni_redesign_r1_v2.md` — R1-V2-Review (304 Z., DeepSeek-Reasoner)
- `p2_omni_redesign_v3.md` — finaler Plan (Mike-freigegeben)
- `p2_omni_redesign_session_context.md` — Pre-Compact-#2 Context (V1+V2)
- **`p2_omni_redesign_session_context_v3.md` — DIESE DATEI (Pre-Compact-#3)**
- `omni_redesign_notes.md` — Source of Truth (Volltext-Notizen)

**Memory:**
- `project_omni_redesign.md` — Status-Snapshot (vor jedem Compact aktualisiert)

**Code-Files (zu ändern):**
- `core/omni_tx.py` (Refactor — Commit 1)
- `core/qso_state.py` (Flag-Pattern — Commit 2)
- `core/timing.py` (Doku — Commit 3)
- `core/encoder.py` (Doku — Commit 3)
- `ui/main_window.py` (Anpassungen — Commit 5)
- `ui/mw_cycle.py` (Pause-Check — Commit 5)
- `ui/mw_qso.py` (Helper + Pfade — Commit 4)
- `tests/test_p2_omni_redesign.py` (NEU — Commit 6)
- `tests/test_omni_tx.py` (Migration — Commit 6)
- `tests/test_p1_omni_start.py` (Migration — Commit 6)
- `tests/test_modules.py` (partielle Migration — Commit 6)
- `tests/test_patterns.py` (partielle Migration — Commit 6)
- `main.py` (APP_VERSION — Commit 7)
- `HISTORY.md`, `HANDOFF.md`, `CLAUDE.md` (4-Datei-Update — Commit 7)

---

## 15. Status-Bestätigung — Bereit für Compact #3

✅ V3 Mike-freigegeben
✅ Memory aktualisiert (`project_omni_redesign.md`)
✅ Code-Verifikationen (`OmniTX(...)`, `block_cycles`, `_cycle_count`, `_pending_switch`, `enable()`, `is_even_cycle`)
✅ Test-Migration-Aufwand erfasst
✅ 7-Commit-Plan steht
✅ R1-Final-Befehl steht
✅ Trigger-Phrasen für nach Compact #3 dokumentiert
✅ Diese Session-Context-Datei vollständig

**Compact #3 kann starten. Nach Compact: „weiter mit OMNI-Redesign Code".**
