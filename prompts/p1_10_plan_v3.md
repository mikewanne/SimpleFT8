# P1.10 Plan-V3 — FINAL Plan mit R1-Findings

**Stand:** 2026-05-05, basierend auf Plan-V2 + Plan-R1-Findings.
**Workflow-Phase:** Plan-V3 → Code-Implementation → Tests → Commits → Field-Test.
**Zielversion:** v0.95.3 → **v0.95.4**.
**Atomare Commits:** 1× Code+Tests + Workflow-Files + 1× Doku.

---

## 0. Plan-R1-Findings — Bewertung & Aktion

R1 fand 0 KRITISCH, 3 WICHTIG, 3 OPTIONAL.

| # | Finding | Severity | Aktion in Plan-V3 |
|---|---|---|---|
| F1 | `rr73_retries` shared zwischen WAIT_RR73 + WAIT_73 | 🟡 | **Bestehendes Issue** vor P1.10 — verifiziert (Z.346 + Z.589-590 inkrementieren denselben Counter). Nicht durch P1.10 verschärft. **Als Known Issue in TODO.md P1.11 dokumentieren** (nicht in diesem Workflow fixen — Scope-Creep) |
| F2 | Panel-Info „Antworte..." irreführend bei Courtesy-73 | 🟡 | **Übernommen:** D4 Reihenfolge ändern (`_set_state` VOR `tx_slot_for_partner.emit`), D5/D9 mw_qso `_on_tx_slot_for_partner` State-abhängig |
| F3 | Test für RR73 während TX_73_COURTESY fehlt | 🟡 | **Übernommen:** Test 12 in D7 |
| F4 | Debug-Output „CQ-Reply" bei Courtesy-73 | 🟢 | **Mit F2 zusammen gefixt** (state-abhängig Debug-Print) |
| F5 | R-Report-vor-73-Pfad in WAIT_73 ungetestet | 🟢 | **Übernommen:** Test 13 in D7 (defensiv) |
| F6 | Integration-Test Slot-Parität | 🟢 | **Verworfen** (R1 sagt selber „kann später") — Field-Test deckt das ab |

---

## 1. Übersicht der Änderungen (V3-FINAL)

| # | Datei | Stelle | Art | V2 | V3 |
|---|---|---|---|---|---|
| D1 | `core/qso_state.py` | Z.49-62 | Enum | +1 | +1 |
| D2 | `core/qso_state.py` | Z.70-82 | Dataclass | +1 | +1 |
| D8 | `core/qso_state.py` | Z.269-272 | 3-Min-Timeout-Liste | +1 Wort | +1 Wort |
| D3 | `core/qso_state.py` | Z.430-436 | on_message_sent | +6 | +6 |
| D4 | `core/qso_state.py` | Z.582-586 | WAIT_73-Hauptlogik | -3 / +18 | **-3 / +19 (Reihenfolge angepasst)** |
| D5 | `ui/mw_qso.py` | Z.200-204 | is_tx-Set | +1 Eintrag | +1 Eintrag |
| **D9** | `ui/mw_qso.py` | Z.425-435 | **NEU `_on_tx_slot_for_partner` state-abhängig** | — | **+5 Zeilen** |
| D6 | `main.py` | APP_VERSION | Bump | -1/+1 | -1/+1 |
| D7 | `tests/test_p1_10_courtesy_73.py` | NEU | Tests | +210 (11 Tests) | **+250 (13 Tests)** |
| **Gesamt** | | | | 5 mod + 1 neu | **5 mod + 1 neu** (D9 = mw_qso, gleiche Datei wie D5) |

## 2. Code-Diffs (V3-FINAL)

### D1, D2, D8, D3, D5, D6 — unverändert aus Plan-V2

(siehe `prompts/p1_10_plan_v2.md` §2)

### D4 — `core/qso_state.py:582-586` Reihenfolge angepasst (V3 F2)

**Vorher (Plan-V2 Stand):**
```python
if self.state == QSOState.WAIT_73:
    if msg.is_73 or msg.is_rr73:
        print(f"[QSO] 73 von {msg.caller} empfangen — QSO bestätigt!")
        if not self.qso.courtesy_73_sent:
            self.qso.courtesy_73_sent = True
            tx_msg = f"{self.qso.their_call} {self.my_call} 73"
            self._dbg.log("TX", f"Courtesy-73 für {msg.caller}: '{tx_msg}'")
            self.tx_slot_for_partner.emit(msg)            # State noch WAIT_73
            self._set_state(QSOState.TX_73_COURTESY)
            self.send_message.emit(tx_msg)
```

**Nachher (V3 — F2 Reihenfolge gefixt):**
```python
if self.state == QSOState.WAIT_73:
    if msg.is_73 or msg.is_rr73:
        print(f"[QSO] 73 von {msg.caller} empfangen — QSO bestätigt!")
        if not self.qso.courtesy_73_sent:
            # P1.10 Fix (v0.95.4): einmaliges Hoeflichkeits-73 zurueck.
            # IC-7300 wartet auf abschliessendes 73 in seiner Auto-Sequence
            # (sonst sendet er 5x weiter 73). Andere FT8-Apps (WSJT-X, JTDX)
            # senden es als Standard.
            self.qso.courtesy_73_sent = True
            tx_msg = f"{self.qso.their_call} {self.my_call} 73"
            self._dbg.log("TX", f"Courtesy-73 für {msg.caller}: '{tx_msg}'")
            # State VOR Slot-Signal setzen, damit _on_tx_slot_for_partner
            # in mw_qso state-abhaengig zwischen CQ-Reply und Courtesy-73
            # unterscheiden kann (Plan-R1 F2: Panel-Info nicht "Antworte...").
            self._set_state(QSOState.TX_73_COURTESY)
            # Slot-Paritaet defensiv auf Gegentakt (R1 KP1 + Plan-R1 F2):
            self.tx_slot_for_partner.emit(msg)
            self.send_message.emit(tx_msg)
            # qso_confirmed.emit + _resume_cq_if_needed in on_message_sent
            # fuer TX_73_COURTESY (Z.430+, Diff D3).
        else:
            # Hypothetischer Doppelschutz
            self.qso_confirmed.emit(self.qso)
            self._resume_cq_if_needed()
    elif msg.is_r_report and msg.caller == self.qso.their_call:
        # ... unverändert (Z.587-596)
    return
```

### D9 — `ui/mw_qso.py:425-435` `_on_tx_slot_for_partner` state-abhängig (NEU V3 F2 + F4)

**Vorher:**
```python
@Slot(object)
def _on_tx_slot_for_partner(self, msg):
    """CQ-Reply empfangen: Encoder-Slot auf Gegentakt der Station setzen."""
    their_even = getattr(msg, '_tx_even', None)
    if their_even is not None:
        self.encoder.tx_even = not their_even
        slot_str = "ODD" if their_even else "EVEN"
        print(f"[TX] CQ-Reply {msg.caller}: sie={('EVEN' if their_even else 'ODD')} → wir={slot_str}")
    # Antennen-Praeferenz anzeigen, falls vorhanden
    label = self._antenna_pref_label(msg.caller)
    if label:
        self.qso_panel.add_info(f"Antworte {msg.caller}{label}")
```

**Nachher (V3 — Plan-R1 F2 + F4):**
```python
@Slot(object)
def _on_tx_slot_for_partner(self, msg):
    """CQ-Reply ODER Courtesy-73: Encoder-Slot auf Gegentakt der Station setzen.

    P1.10 (v0.95.4): wird jetzt auch fuer Courtesy-73 in WAIT_73 verwendet.
    State-abhaengig zwischen 'CQ-Reply' und 'Courtesy-73 Slot' unterscheiden.
    """
    their_even = getattr(msg, '_tx_even', None)
    is_courtesy = self.qso_sm.state == QSOState.TX_73_COURTESY
    if their_even is not None:
        self.encoder.tx_even = not their_even
        slot_str = "ODD" if their_even else "EVEN"
        kind = "Courtesy-73" if is_courtesy else "CQ-Reply"
        print(f"[TX] {kind} {msg.caller}: sie={('EVEN' if their_even else 'ODD')} → wir={slot_str}")
    # Antennen-Praeferenz-Panel-Info nur bei CQ-Reply, nicht bei Courtesy-73
    # (bei Courtesy-73 ist QSO bereits abgeschlossen — "Antworte..." waere irrefuehrend)
    if not is_courtesy:
        label = self._antenna_pref_label(msg.caller)
        if label:
            self.qso_panel.add_info(f"Antworte {msg.caller}{label}")
```

## 3. Test-Datei (V3-FINAL, 13 Tests)

Tests 1-11 unverändert aus Plan-V2. **NEU in V3:**

### Test 12 — RR73 während TX_73_COURTESY (Plan-R1 F3)

```python
def test_second_rr73_in_tx_73_courtesy_state_falls_through():
    """P1.10 (R1 F3): RR73 waehrend TX_73_COURTESY → kein Trigger,
    State unveraendert. Symmetrisch zu Test 10 (73 in TX_73_COURTESY)."""
    _ensure_app()
    sm = QSOStateMachine("DA1MHH", "JO31")
    _setup_wait_73_state(sm)

    sent = []
    sm.send_message.connect(sent.append)

    # Erstes 73 → Courtesy-73 + TX_73_COURTESY
    sm.on_message_received(_make_73_msg())
    assert sm.state == QSOState.TX_73_COURTESY
    initial_sent = len(sent)

    # RR73 waehrend TX_73_COURTESY
    sm.on_message_received(_make_rr73_msg())

    # Kein zusaetzlicher Send, State bleibt TX_73_COURTESY
    assert len(sent) == initial_sent
    assert sm.state == QSOState.TX_73_COURTESY
```

### Test 13 — R-Report-vor-73 in WAIT_73 nach P1.10 (Plan-R1 F5)

```python
def test_wait_73_with_r_report_before_73_unchanged():
    """P1.10 (R1 F5): WAIT_73 + R-Report (Hoeflichkeits-Pfad) bleibt
    unveraendert nach P1.10. Courtesy-73 wird NICHT getriggert weil
    is_r_report nicht is_73."""
    _ensure_app()
    sm = QSOStateMachine("DA1MHH", "JO31")
    _setup_wait_73_state(sm)

    sent = []
    sm.send_message.connect(sent.append)

    # R-Report (z.B. R-15) → Hoeflichkeits-RR73-Retry-Pfad (Z.587-596)
    r_report_msg = FT8Message(
        raw="DA1MHH DA1TST R-15",
        field1="DA1MHH",
        field2="DA1TST",
        field3="R-15",
        snr=-15,
        freq_hz=1500,
    )
    sm.on_message_received(r_report_msg)

    # Erwartet: RR73-Retry, NICHT Courtesy-73
    assert len(sent) == 1
    assert sent[0] == "DA1TST DA1MHH RR73"
    assert sm.qso.rr73_retries == 1
    # courtesy_73_sent bleibt False (Pfad nicht durchlaufen)
    assert sm.qso.courtesy_73_sent is False
    # State bleibt WAIT_73 (Hoeflichkeits-Retry setzt KEIN _set_state)
    assert sm.state == QSOState.WAIT_73
```

### Test-Liste FINAL (13 Tests)

1. WAIT_73 + 73 → Courtesy-73, State=TX_73_COURTESY
2. WAIT_73 + RR73 → ebenfalls Courtesy-73
3. Counter-Schutz: nur 1× Courtesy-73 pro QSO
4. on_message_sent in TX_73_COURTESY + cq_mode=True → CQ_CALLING
5. on_message_sent in TX_73_COURTESY + cq_mode=False + _was_cq=False → IDLE
6. qso_complete.emit feuert genau 1× pro QSO
7. qso_confirmed.emit feuert genau 1× nach Courtesy-73-Send
8. WAIT_73-Timeout 3 Slots ohne 73 → unverändert
9. Slot-Parität via Signal (R1 KP1)
10. Doppel-73 in TX_73_COURTESY → fällt durch
11. Vorwärtssprung WAIT_REPORT+RR73 → kein Doppel-ADIF (defensiv)
12. **(Plan-R1 F3):** RR73 während TX_73_COURTESY → fällt durch
13. **(Plan-R1 F5):** R-Report-Hoeflichkeit-Pfad in WAIT_73 unverändert

## 4. Implementierungs-Reihenfolge (V3-FINAL)

1. App stoppen — laufende v0.95.3 (alle Instanzen `pgrep -f "python.*main.py"` killen)
2. **D1 + D2 + D8** in `core/qso_state.py` (Enum, Dataclass, Timeout-Liste)
3. **D3** in `core/qso_state.py` (on_message_sent neuer Branch)
4. **D4** in `core/qso_state.py` (WAIT_73-Hauptlogik mit V3 Reihenfolge)
5. **D5** in `ui/mw_qso.py` (is_tx-Set)
6. **D9** in `ui/mw_qso.py` (`_on_tx_slot_for_partner` state-abhängig)
7. **D6** in `main.py` (APP_VERSION → 0.95.4)
8. **D7** Test-Datei `tests/test_p1_10_courtesy_73.py` (13 Tests)
9. Tests laufen: `./venv/bin/python3 -m pytest tests/ -q` → erwartet **777** passed (764 + 13)
10. App neu starten v0.95.4 (kurz prüfen)
11. **Atomarer Commit 1** Code+Tests+prompts/p1_10_*.md
12. **Doku-Commit 2** HISTORY/HANDOFF/CLAUDE/TODO/Memory

## 5. Verifikations-Checks (V3-FINAL)

- [ ] `./venv/bin/python3 -m pytest tests/ -q` → **777 passed** (764 + 13)
- [ ] `./venv/bin/python3 -m pytest tests/test_p1_10_courtesy_73.py -v` → 13 passed
- [ ] `./venv/bin/python3 -m pytest tests/test_qso_state.py -q` → unverändert grün
- [ ] `git status`: 5 modified + 1 new test + ~10 prompts/-Files
- [ ] `git diff core/qso_state.py` zeigt 5 Hunks (D1, D2, D8, D3, D4)
- [ ] `git diff ui/mw_qso.py` zeigt 2 Hunks (D5, D9)
- [ ] App startet ohne Fehler: kurzer `python3 -c "import main"`-Test
- [ ] APP_VERSION-Konsistenz: `grep "0.95.4" main.py` → 1 match
- [ ] grep `TX_73_COURTESY` über Code: D1 + D3 + D4 + D5 + D9 = 5 Vorkommen + Tests

## 6. Commit-Plan (V3-FINAL)

### Commit 1: Code + Tests + Workflow-Files

**Betroffene Files:**
- `core/qso_state.py` (D1, D2, D8, D3, D4 — 5 Hunks)
- `ui/mw_qso.py` (D5, D9 — 2 Hunks)
- `main.py` (D6 Version)
- `tests/test_p1_10_courtesy_73.py` (NEU, 13 Tests)
- `prompts/p1_10_v1.md`, `p1_10_v2.md`, `p1_10_v3.md`, `p1_10_r1.md`,
  `p1_10_plan_v1.md`, `p1_10_plan_v2.md`, `p1_10_plan_v3.md`,
  `p1_10_plan_r1.md`, `p1_10_compact_notes.md`, `p1_10_r1_raw.md`

**Commit-Message:**
```
feat(qso): P1.10 Courtesy-73 nach 73-Empfang in WAIT_73 (v0.95.4)

Wurzel: IC-7300 (DA1TST) Auto-Sequence wartet auf abschliessendes
Hoeflichkeits-73 von uns. SimpleFT8 sendet bisher kein Courtesy-73 →
IC-7300 retried 5x in Folgeslots bevor er aufgibt. Andere FT8-Apps
(WSJT-X, JTDX, MSHV) senden es als Standard. Field-Test 11:24-:29
UTC mit DA1TST 2x reproduziert.

Fix:
- core/qso_state.py: neuer State TX_73_COURTESY, neues Feld
  qso.courtesy_73_sent (max 1x pro QSO), neuer Branch in on_message_sent
  fuer TX_73_COURTESY (qso_confirmed + _resume_cq_if_needed),
  WAIT_73-Hauptlogik geaendert: bei 73/RR73-Empfang einmaliges
  Courtesy-73 senden + Slot-Paritaet via tx_slot_for_partner.emit
  (R1 KP1, _set_state vor emit fuer state-abhaengiges UI),
  TX_73_COURTESY in 3-Min-QSO-Timeout-Ausschluss-Liste (defensiv,
  Plan-V2-L1)
- ui/mw_qso.py: is_tx-Set erweitert um TX_73_COURTESY,
  _on_tx_slot_for_partner state-abhaengig (CQ-Reply vs Courtesy-73,
  Panel-Info nur bei CQ-Reply, Plan-R1 F2 + F4)
- main.py: APP_VERSION 0.95.3 -> 0.95.4
- tests/test_p1_10_courtesy_73.py: 13 neue Tests

Voller V1->V2(8 V1-Luecken)->R1(4 KP + 3 Findings)->V3 Diagnose-Workflow
+ Plan-V1->V2(6 Plan-V1-Luecken, D8 hinzugefuegt)->R1(3 wichtige + 3
optionale Findings)->V3 Plan-Workflow.

Tests 764 -> 777 gruen (+13).
Field-Test bei Mike ausstehend (DA1TST IC-7300, 30m FT8).

Known Issue (Plan-R1 F1, NICHT durch P1.10 verschaerft): rr73_retries
shared zwischen WAIT_RR73 + WAIT_73-Hoeflichkeits-Pfad. Wenn QSO viele
WAIT_RR73-Retries hatte, bleibt fuer WAIT_73 nichts uebrig. Als P1.11
in TODO.md.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
```

### Commit 2: Doku

**Betroffene Files:**
- `HISTORY.md` (anhängen)
- `HANDOFF.md` (beide Pfade — SimpleFT8/ + FT8/)
- `CLAUDE.md` (beide Pfade)
- `TODO.md` (P1.10 → ✅, P1.11 NEU für rr73_retries)
- `~/.claude-account1/projects/.../memory/MEMORY.md` (Index)
- `~/.claude-account1/projects/.../memory/project_v0954_courtesy_73_solution.md` (NEU)
- `~/.claude-account1/projects/.../memory/feedback_plan_v2_must_check_timeout_lists.md` (NEU)

**Commit-Message:**
```
docs: v0.95.4 P1.10 Courtesy-73 Stand
- HISTORY.md neuer Eintrag
- HANDOFF.md beide Pfade Stand v0.95.4
- CLAUDE.md beide Pfade Aktueller Stand
- TODO.md P1.10 als ✅, P1.11 (rr73_retries-Counter-Trennung) NEU
- Memory: project_v0954_courtesy_73_solution +
  feedback_plan_v2_must_check_timeout_lists

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
```

## 7. Risiken & Mitigation (V3-FINAL)

| Risiko | Mitigation |
|---|---|
| FT8Message-Pattern in Tests | Verifiziert: field1=target, field2=caller, field3=value |
| Slot-Parität-Test ohne mw_qso-Loop | Test 9 prüft Signal-Emission, Field-Test deckt End-to-End |
| 3-Min-Timeout während TX_73_COURTESY | **D8** schliesst defensiv ab |
| Doppel-ADIF in TX_73_COURTESY | D3 emittet KEIN qso_complete in TX_73_COURTESY-Branch (Test 6) |
| Slot-Parität ohne msg._tx_even | mw_qso `_on_tx_slot_for_partner` hat None-Fallback |
| Cycle-Signal-Reihenfolge | Unverändert (P1.9-Lesson) |
| App-Restart vs Mike's Statistik | App stoppen vor Code-Ändern, neu starten erst nach Commit |
| Panel-Info-Verwirrung Courtesy-73 | **D9 + D4-Reihenfolge** löst es state-abhängig |

## 8. Out-of-Scope / Known Issues (V3 NEU)

- **P1.11 (NEU):** `rr73_retries`-Counter shared zwischen WAIT_RR73 + WAIT_73
  (Plan-R1 F1). Bestehender Bug, nicht durch P1.10 verschärft. Eigener
  Workflow nach P1.10 Field-Test.
- P1.8 (`_last_snr` vs `msg.snr`)
- P1.7 (Doppel-ADIF-Lokalfilter)
- P1.6 (Versionsnummer-Display)

## 9. Workflow-Status (V3-FINAL)

| Phase | Status |
|---|---|
| Diagnose-V1→V2→R1→V3 | ✅ |
| Plan-V1 | ✅ |
| Plan-V2 (6 V1-Lücken) | ✅ |
| Plan-R1 (3 W + 3 O Findings) | ✅ `prompts/p1_10_plan_r1.md` |
| **Plan-V3** | ✅ **DIESE DATEI** (F1 als Known Issue, F2+F4 zusammen, F3+F5 als Tests, F6 verworfen) |
| Code-Implementation | 🔴 nächster Schritt |
| Tests + Verifikation | 🔴 |
| Atomare Commits | 🔴 |
| Field-Test Mike | 🔴 |

---

**Plan-V3 Ende. Mike's Freigabe „lass uns loslegen" → autonom durchziehen
bis Field-Test-Hinweis. Code-Implementation startet jetzt.**
