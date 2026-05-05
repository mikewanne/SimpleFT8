# P1.10 Plan-V2 — Self-Review von Plan-V1 (frische KI)

**Stand:** 2026-05-05, Plan-V1-Review als frische KI.
**Workflow-Phase:** Plan-V1 → **Plan-V2** (diese Datei) → Plan-R1 → Plan-V3.
**Ergebnis:** 6 V1-Lücken geschlossen, 1 zusätzlicher Diff (D8) hinzugefügt,
2 Tests verschärft.

---

## 0. Self-Review-Befund (Plan-V1 → Plan-V2)

| # | Plan-V1-Lücke | Plan-V2-Korrektur |
|---|---|---|
| L1 | 3-Min-QSO-Timeout Z.269-272 enthält TX_73_COURTESY nicht in Ausschluss-Liste | **Neuer Diff D8** — TX_73_COURTESY hinzufügen (defensiv, Slot dauert ~13s aber QSO faktisch fertig) |
| L2 | `_was_cq`-Setzung in Test 5 + Test 11 nicht explizit dokumentiert | Test-Setup-Helper erweitert + Kommentare präzisiert |
| L3 | Test 9 prüft Slot-Parität-Signal, aber NICHT mw_qso-Listener-Effekt — Unit-Test-Architektur-Hinweis fehlt | Risiko-Tabelle erweitert + Test-Doku |
| L4 | Reihenfolge in `on_message_received` — Z.494-496 garantiert caller-Check vor Z.582-597 — fehlt im Plan | §4-Notiz hinzugefügt |
| L5 | prompts/-Files (Workflow-Artefakte) im Doku-Commit nicht erwähnt | Commit-Plan ergänzt |
| L6 | Memory-Update fehlt explizit (Lesson R1-KP1 Slot-Parität-Defensive als wiederverwendbares Pattern) | §6 Memory-Pflicht hinzugefügt |

---

## 1. Übersicht der Änderungen (V2-Stand)

| # | Datei | Stelle | Art | V1 | V2 |
|---|---|---|---|---|---|
| D1 | `core/qso_state.py` | Z.49-62 | Enum | +1 | +1 |
| D2 | `core/qso_state.py` | Z.70-82 | Dataclass | +1 | +1 |
| D3 | `core/qso_state.py` | Z.430-436 | on_message_sent | +6 | +6 |
| D4 | `core/qso_state.py` | Z.582-586 | WAIT_73-Hauptlogik | -3 / +18 | -3 / +18 |
| **D8** | `core/qso_state.py` | Z.269-272 | **NEU** 3-Min-Timeout Ausschluss | — | **+1 Wort** |
| D5 | `ui/mw_qso.py` | Z.200-204 | is_tx-Set | +1 Eintrag | +1 Eintrag |
| D6 | `main.py` | APP_VERSION | Bump | -1/+1 | -1/+1 |
| D7 | `tests/test_p1_10_courtesy_73.py` | NEU | 11 Tests | +200 | +210 (kommentiert) |
| **Gesamt** | | | | **5 mod + 1 neu** | **5 mod + 1 neu** (D8 ist gleiche Datei wie D1-D4) |

## 2. Code-Diffs (V2-Stand, alle 8 Diffs)

### D1, D2, D3, D5, D6, D7 — unverändert aus Plan-V1

(siehe `prompts/p1_10_plan_v1.md` §2)

### D4 — `core/qso_state.py:582-586` (unverändert aus V1)

(siehe Plan-V1 §2 D4)

### D8 — `core/qso_state.py:269-272` 3-Min-Timeout Ausschluss (NEU in V2)

**Vorher:**
```python
def on_cycle_end(self):
    # Gesamt-QSO Timeout (3 Min) — egal welcher State
    if (self.state not in (QSOState.IDLE, QSOState.CQ_CALLING, QSOState.CQ_WAIT,
                           QSOState.TIMEOUT, QSOState.WAIT_73)
            and self.qso.start_time > 0
            and time.time() - self.qso.start_time > MAX_QSO_DURATION):
        ...
```

**Nachher:**
```python
def on_cycle_end(self):
    # Gesamt-QSO Timeout (3 Min) — egal welcher State
    if (self.state not in (QSOState.IDLE, QSOState.CQ_CALLING, QSOState.CQ_WAIT,
                           QSOState.TIMEOUT, QSOState.WAIT_73,
                           QSOState.TX_73_COURTESY)  # P1.10: Courtesy-73 zu Ende fuehren
            and self.qso.start_time > 0
            and time.time() - self.qso.start_time > MAX_QSO_DURATION):
        ...
```

**Begründung:** TX_73_COURTESY dauert ~13s (1 FT8-Slot). Wenn 3-Min-Timeout
während TX_73_COURTESY feuert: `_set_state(TIMEOUT)` + `qso_timeout.emit` +
`_resume_cq_if_needed`, aber der Encoder sendet noch das Courtesy-73. Nach
`tx_finished` käme `on_message_sent` mit state=TIMEOUT → kein Branch greift,
`qso_confirmed.emit` feuert NIE → UI hängt im „warte 73"-Zustand.

R1-Bewertung 6.3 sagt „extrem unwahrscheinlich" — aber defensiv-billig
(1 Wort) und schließt edge case komplett.

**Trace-Validierung (Field-Test 11:22-:24):**
- 11:22:15 RX r-report → 11:22:30 RR73 (start_time gesetzt)
- 11:24:00 RR73 (Hoeflichkeits-Retry)
- 11:24:15 73 empfangen (1m45s nach start_time)
- → Courtesy-73 :24:30 (1m60s nach start_time)
- → Far below 3-Min, normaler Fall sicher.

Edge case: extrem langsame QSOs mit Hoeflichkeit-Retries und
Slot-Verschiebungen könnten >3 Min erreichen. D8 deckt das ab.

## 3. Test-Datei (V2-Stand)

### Test-Helper erweitert (Doku + Defensive)

```python
def _setup_wait_73_state(sm: QSOStateMachine, their_call="DA1TST",
                         their_grid="JN66", cq_mode=True, was_cq=False):
    """SM in WAIT_73 versetzen mit aktivem QSO.

    Args:
        cq_mode: True fuer CQ-Modus-Tests, False fuer Hunt-Modus.
        was_cq: True wenn vorher CQ-Modus aktiv war (fuer _resume_cq-Pfade).
    """
    sm.cq_mode = cq_mode
    sm._was_cq = was_cq
    sm.qso = QSOData(
        their_call=their_call,
        their_grid=their_grid,
        freq_hz=1500,
        start_time=1700000000.0,
        timeout_cycles=0,
    )
    sm._set_state(QSOState.WAIT_73)
```

### Test 5 verschärft (V2)

```python
def test_tx_73_courtesy_finished_without_cq_mode_goes_idle():
    """P1.10: on_message_sent in TX_73_COURTESY + cq_mode=False + _was_cq=False
    → qso_confirmed + State=IDLE.

    Wichtig: BEIDE flags muessen False sein, sonst _resume_cq_if_needed
    interpretiert _was_cq als 'CQ-Modus war aktiv → CQ resumieren'.
    """
    _ensure_app()
    sm = QSOStateMachine("DA1MHH", "JO31")
    _setup_wait_73_state(sm, cq_mode=False, was_cq=False)
    sm.qso.courtesy_73_sent = True
    sm._set_state(QSOState.TX_73_COURTESY)

    confirmed = []
    sm.qso_confirmed.connect(confirmed.append)

    sm.on_message_sent()

    assert len(confirmed) == 1
    assert sm.state == QSOState.IDLE
```

### Test 11 verschärft (V2)

```python
def test_forward_jump_wait_report_rr73_no_double_adif():
    """P1.10: Vorwaertssprung WAIT_REPORT + RR73 → TX_RR73 sendet '73' + ADIF.
    Spaetere 73-Empfang in WAIT_73 → Courtesy-73 (ADIF NICHT erneut).
    Sicherheit gegen Doppel-ADIF auch bei Sprung-Pfad.

    Hunt-Modus (cq_mode=False) damit qso_confirmed _resume_cq=False
    → State=IDLE statt CQ_CALLING (kein Test-Stoerer).
    """
    _ensure_app()
    sm = QSOStateMachine("DA1MHH", "JO31")
    sm.cq_mode = False
    sm._was_cq = False
    sm.qso = QSOData(
        their_call="DA1TST",
        their_grid="JN66",
        freq_hz=1500,
        start_time=1700000000.0,
    )
    sm._set_state(QSOState.WAIT_REPORT)

    completes = []
    sm.qso_complete.connect(completes.append)

    # Vorwaertssprung: RR73 in WAIT_REPORT → TX_RR73 + sende '73'
    rr73 = _make_rr73_msg()
    sm.on_message_received(rr73)
    assert sm.state == QSOState.TX_RR73

    # TX_RR73 fertig → qso_complete (= ADIF)
    sm.on_message_sent()
    assert len(completes) == 1
    assert sm.state == QSOState.WAIT_73

    # In WAIT_73 — 73 → Courtesy-73-Pfad
    sm.on_message_received(_make_73_msg())
    assert sm.state == QSOState.TX_73_COURTESY

    # Courtesy-73 fertig → qso_confirmed, KEIN zweites qso_complete
    sm.on_message_sent()
    assert len(completes) == 1
```

### Test 9 Doku verschärft (V2)

```python
def test_courtesy_73_slot_parity_via_signal():
    """P1.10: tx_slot_for_partner.emit(msg) wird mit dem 73-msg gefeuert,
    damit mw_qso encoder.tx_even = not msg._tx_even setzt.

    Hinweis: Dieser Unit-Test prueft NUR die Signal-Emission.
    Der Effekt auf encoder.tx_even wird in Integration durch mw_qso
    `_on_tx_slot_for_partner` (mw_qso.py:425-429) angewendet.
    Field-Test bestaetigt korrekten EVEN-Slot fuer Courtesy-73.
    """
    _ensure_app()
    sm = QSOStateMachine("DA1MHH", "JO31")
    _setup_wait_73_state(sm)

    slot_msgs = []
    sm.tx_slot_for_partner.connect(slot_msgs.append)

    msg = _make_73_msg(tx_even=False)
    sm.on_message_received(msg)

    assert len(slot_msgs) == 1
    assert slot_msgs[0] is msg
    assert getattr(slot_msgs[0], "_tx_even", None) is False
```

## 4. Reihenfolge-Garantie in `on_message_received` (V2-Notiz)

`qso_state.py:494-496` garantiert dass WAIT_73-Pfad nur mit korrektem Caller
läuft:

```python
# ── Absender muss Gegenstation sein ──
if self.state not in (QSOState.IDLE, QSOState.CQ_WAIT, QSOState.CQ_CALLING):
    if msg.caller != self.qso.their_call:
        return
```

→ Im WAIT_73-Pfad (Z.582-597) ist `msg.caller == self.qso.their_call`
bereits sichergestellt. Kein zusätzlicher Caller-Check in D4 nötig.

## 5. Implementierungs-Reihenfolge (V2-Stand)

1. App stoppen — laufende v0.95.3 PID 80961
2. D1 + D2 + **D8** + D3 (qso_state.py: Enum + Dataclass + Timeout-Liste + on_message_sent)
3. D4 (qso_state.py: WAIT_73-Hauptlogik)
4. D5 (mw_qso.py: is_tx-Set)
5. D6 (main.py: APP_VERSION 0.95.3 → 0.95.4)
6. D7 (tests/test_p1_10_courtesy_73.py: 11 Tests, V2-verschärft)
7. Tests laufen: `./venv/bin/python3 -m pytest tests/ -q` → erwartet 775 passed
8. App neu starten v0.95.4 (kurz ohne Fehler)
9. Atomarer Commit Code+Tests + prompts/p1_10_*.md
10. Doku-Commit HISTORY/HANDOFF/CLAUDE/TODO/Memory

## 6. Memory-Pflicht (V2 NEU)

Nach erfolgreicher Implementierung neue Memory-Dateien:

- **Wenn Field-Test ✅:** `project_v0954_courtesy_73_solution.md` — wie für
  P1.9. Beschreibt Pattern: „Auto-Sequence-Bug der Gegenstation lösen durch
  einmaligen Höflichkeits-Send + Counter pro QSO-Objekt + neuer State + R1-
  KP1 Slot-Parität-Defensive via Signal".
- **Lesson Plan-Workflow:** `feedback_plan_v2_must_check_timeout_lists.md` —
  bei jedem neuen State: prüfen ob 3-Min-Timeout-Ausschluss-Liste angepasst
  werden muss. (V1 hatte das verpasst, V2 hat es gefangen.)

## 7. Verifikations-Checks (V2-Stand)

- [ ] `./venv/bin/python3 -m pytest tests/ -q` → 775 passed (764 + 11)
- [ ] `./venv/bin/python3 -m pytest tests/test_p1_10_courtesy_73.py -v` → 11 passed
- [ ] `./venv/bin/python3 -m pytest tests/test_qso_state.py -q` → unverändert
- [ ] `git status` zeigt: 5 modified (`core/qso_state.py`, `ui/mw_qso.py`,
      `main.py`) + 1 new (`tests/test_p1_10_courtesy_73.py`) + prompts/-Files
- [ ] `git diff core/qso_state.py` zeigt 5 Hunks (D1, D2, D8, D3, D4)
- [ ] App startet ohne Fehler: `./venv/bin/python3 -c "import main"`
- [ ] APP_VERSION-Konsistenz: `grep '0.95.4' main.py CLAUDE.md HANDOFF.md HISTORY.md`

## 8. Commit-Plan (V2-Stand)

### Commit 1: Code + Tests + Workflow-Files (atomar)
```
feat(qso): P1.10 Courtesy-73 nach 73-Empfang in WAIT_73 (v0.95.4)

[Plan-V1-Body unverändert + V2-Defensive D8 erwähnen]
- Defensive: TX_73_COURTESY in 3-Min-QSO-Timeout-Ausschluss (Z.269-272)
  schliesst hypothetisches edge case (R1 6.3, Plan-V2-L1).

Voller V1→V2(8 V1-Luecken)→R1(4 KP + 3 Findings)→V3 Diagnose-Workflow
+ Plan-V1→V2(6 Plan-V1-Luecken)→R1→V3-Workflow. Tests 764 → 775 gruen.
```

Files in Commit 1:
- core/qso_state.py
- ui/mw_qso.py
- main.py
- tests/test_p1_10_courtesy_73.py (NEU)
- prompts/p1_10_v1.md (NEU)
- prompts/p1_10_v2.md (NEU)
- prompts/p1_10_v3.md (NEU)
- prompts/p1_10_r1.md (NEU)
- prompts/p1_10_plan_v1.md (NEU)
- prompts/p1_10_plan_v2.md (NEU)
- prompts/p1_10_plan_r1.md (NEU, kommt aus R1-Schritt)
- prompts/p1_10_plan_v3.md (NEU, kommt aus V3-Schritt)
- prompts/p1_10_compact_notes.md (existiert seit pre-Compact)

### Commit 2: Doku
```
docs: v0.95.4 P1.10 Courtesy-73 Stand
- HISTORY.md neuer Eintrag mit Plan-V2-Verbesserung (D8)
- HANDOFF.md beide Pfade Stand v0.95.4
- CLAUDE.md beide Pfade Aktueller Stand
- TODO.md P1.10 als ✅
- Memory: project_v0954_courtesy_73_solution.md +
  feedback_plan_v2_must_check_timeout_lists.md
```

## 9. Risiken & Mitigation (V2-erweitert)

| Risiko | Mitigation |
|---|---|
| Test-Pattern FT8Message anders als erwartet | Verifiziert: field1=target, field2=caller, field3=value (core/message.py:7-78) |
| Slot-Paritaet-Test ohne mw_qso-Loop | Test 9 prueft NUR Signal-Emission, Field-Test prueft End-to-End |
| 3-Min-Timeout während TX_73_COURTESY | **D8 schliesst defensiv ab** (V2 Self-Review-Fund) |
| Doppel-ADIF in TX_73_COURTESY | D3 emittet KEIN qso_complete in TX_73_COURTESY-Branch (Test 6) |
| Slot-Parität ohne msg._tx_even | mw_qso `_on_tx_slot_for_partner` hat None-Fallback (mw_qso.py:425-429) |
| Cycle-Signal-Reihenfolge cycle_decoded → message_decoded → cycle_finished | Unverändert (P1.9-Lesson, kein Fix in P1.10) |
| App-Restart-Konflikt mit Mike's Statistik | App stoppen vor Code-Ändern, neu starten erst nach Commit |

## 10. Workflow-Status (V2)

| Phase | Status |
|---|---|
| Diagnose-V1→V2→R1→V3 | ✅ |
| Plan-V1 | ✅ `prompts/p1_10_plan_v1.md` |
| **Plan-V2** | ✅ **DIESE DATEI** (6 V1-Lücken geschlossen, D8 hinzugefügt) |
| Plan-R1 DeepSeek | 🔴 nächster Schritt |
| Plan-V3 | 🔴 |
| Code-Implementation | 🔴 |
| Tests + Verifikation | 🔴 |
| Atomare Commits | 🔴 |
| Field-Test Mike | 🔴 |

---

**Plan-V2 Ende. Nächster Schritt: Plan-V2 + 3 Code-Files an DeepSeek-Reasoner.**
