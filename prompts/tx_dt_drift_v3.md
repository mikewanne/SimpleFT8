# V3 — TX-DT-Drift im QSO-Retry-Pfad (BLOCKER) [R1-bestätigt]

**Status:** V3 (nach R1-Review von V2) → Mike-Freigabe → Plan-Mode → Implementation
**Vorgänger:** `prompts/tx_dt_drift_v2.md`
**R1-Bilanz:** 5 echte Findings akzeptiert, 2 Overengineering abgelehnt,
1 Code-Analyse-Halluzination identifiziert.
**Kritischstes R1-Finding:** Fix A2 in V2 war **unwirksam** — `time.sleep()`
ist nicht unterbrechbar, Worker schläft 14s bevor Abort-Check greift.

---

## 0. R1-Bilanz V2 → V3

### Akzeptiert (5 Findings)

| # | R1-Finding | V3-Lösung |
|---|---|---|
| **1** | **Race 2 — `time.sleep()` ist nicht unterbrechbar** → Fix A2 unwirksam, alter Retry-TX wird trotzdem gesendet wenn Antwort spät kommt | **NEU Fix A2:** `threading.Event` statt `time.sleep` in `_tx_worker_inner`. `abort()` ruft `event.set()` → sleep returnt sofort. **KRITISCH.** |
| 2 | `_next_slot_boundary` 3s-Schwelle ist zu großzügig | **NEU Fix C:** Schwelle `_SLOT/5` → `0.5s` (encoder.py:158) |
| 3 | Counter-Race-Schutz: `_set_state` setzt `timeout_cycles` nicht zurück | **NEU Fix A3:** explizit `qso.timeout_cycles = 0` in `_set_state` für WAIT_*-States, oder Defense-in-Depth-Audit aller Eintrittspfade |
| 4 | HALT-Akzeptanzkriterium fehlt | A9 NEU |
| 5 | Tests-Lücken (cycle_pos-Variationen, Counter-Race, Antwort-im-Retry-Slot) | Sektion 6: 3 neue Tests |

### Abgelehnt (2 Findings)

| # | R1-Empfehlung | Ablehnungsgrund |
|---|---|---|
| 1 | Auto-Kalibrierung TARGET_TX_OFFSET (Markierton + RX-Messung) | **Overengineering.** FlexRadio-Buffer 1.3s nachweislich konstant (HISTORY 23.04., 8 Zyklen 0.0s DT validiert auf 20m+40m). Mike's Setup fix. Phase-2-TODO falls Hardware-Wechsel. |
| 2 | `cycle_start` in `_on_cycle_decoded` integrieren (Race 1 fix) | **Architektur-Umbau, Risiko > Nutzen.** Race 1 wird mit Race-2-Fix entschärft (selbst bei umgekehrter Signal-Reihenfolge funktioniert encoder.abort jetzt korrekt). KISS. |

### Halluzination identifiziert (1)

| # | R1-Behauptung | Code-Realität |
|---|---|---|
| 1 | „`timeout_cycles` wird nirgendwo zurückgesetzt" | **Falsch.** Z.391 (`WAIT_REPORT`-Eintritt), Z.405 (`WAIT_RR73`-Eintritt), Z.320 (im Retry selbst) setzen ihn explizit. R1 hat den Code nicht 100% gelesen. **Aber:** R1's allgemeiner Punkt (Counter-Reset-Konsistenz fehlt für `_set_state`-Wechsel) wird als Defense-in-Depth aufgenommen. |

---

## 1. Symptom (Feldtest-Daten — unverändert)

| TX-Typ | Beobachtete DT | Stichprobe |
|---|---|---|
| Folge-CQs (CQ_WAIT-Loop) | **0.0–0.1s** | 8/8 sauber |
| Erster Report nach RX-Antwort | **0.1s** | 2/2 sauber |
| RR73-TX nach R-Report | **0.1s** | 2/2 sauber |
| **Folge-Report (WAIT_REPORT-Retry)** | **0.6–0.8s** | **6/6 driftet** |
| **Erster CQ nach QSO-End/Timeout** | **0.6–0.8s** | **2/2 driftet** |

**Konsequenz:** Auto-Sequence-Decoder verwerfen Frames mit DT > 0.5s.
7 Real-QSOs hintereinander gescheitert.

---

## 2. Code-Pfad-Diagnose (kompakt — Details V1 Sektion 2)

**Wurzel:** `on_cycle_end` Z.501 in `mw_cycle._on_cycle_start` triggert
`WAIT_REPORT`-Retry bei `timeout_cycles == 2` AM Anfang von Mike's TX-Slot.
Encoder hat 0s Vorlauf, „Slot-Rand: sofort senden" feuert mit overshoot
0.95s → DT 0.95s.

---

## 3. Lösung — Hybrid mit cancelable sleep (Fix A1+A2+A3+B+C)

### Fix A1 — Trigger-Zeitpunkt korrigieren (`core/qso_state.py`)

| Stelle | Counter | aktuell | neu |
|---|---|---|---|
| `qso_state.py:297` `WAIT_REPORT` | `qso.timeout_cycles` | `== 2` | `== 1` |
| `qso_state.py:313` `WAIT_RR73` | `qso.timeout_cycles` | `== 2` | `== 1` |

Retry-TX-Timing bleibt (Encoder schedulet zu Slot N+2 weil Trigger im
RX-Slot N+1 feuert → 14s Vorlauf).

### Fix A2 — Cancelable sleep (`core/encoder.py`) — KRITISCH

**Problem (R1):** `time.sleep(14s)` ist nicht unterbrechbar. Wenn während
sleep `abort()` aufgerufen wird, wartet Worker 14s, dann erst Abort-Check.
→ alter Retry-TX wird trotzdem gesendet, obwohl State bereits gewechselt
ist (z.B. zu TX_RR73 nach später RX-Antwort).

**Lösung:** `threading.Event` statt `time.sleep`.

```python
# encoder.py — neue Member
def __init__(self, audio_freq_hz: int = 1000):
    super().__init__()
    ...
    self._abort_event = threading.Event()  # NEU

def abort(self):
    """TX sofort abbrechen (Bandwechsel, Notaus, state-change)."""
    self._is_transmitting = False
    self._abort_event.set()  # NEU: weckt sleep auf
    print("[Encoder] TX abgebrochen")

def _tx_worker(self, message: str):
    self._is_transmitting = True
    self._abort_event.clear()  # NEU: Reset bei jedem TX-Start
    try:
        self._tx_worker_inner(message)
    finally:
        self._is_transmitting = False
```

```python
# encoder.py:185-194 — neuer Sleep-Pfad
sleep_dur = (next_boundary + TARGET_TX_OFFSET - 0.5) - time.time()
if sleep_dur > 0.001:
    aborted = self._abort_event.wait(timeout=sleep_dur)
    if aborted:
        print("[Encoder] TX abgebrochen (während Warte-Phase)")
        return

# Doppel-Check (sleep_dur war <= 0.001)
if not self._is_transmitting:
    print("[Encoder] TX abgebrochen (vor Sleep)")
    return
```

### Fix A3 — Counter-Reset-Konsistenz (`core/qso_state.py`)

**Audit ALLER state-Eintrittspfade in WAIT_REPORT, WAIT_RR73, CQ_WAIT,
WAIT_73:**

| Eintrittspunkt | Counter-Reset | Status |
|---|---|---|
| Z.365 `_set_state(CQ_WAIT)` + Z.366 | ✅ explizit `timeout_cycles=0` | OK |
| Z.391 `_set_state(WAIT_REPORT)` | ✅ Z.391 nachfolgend `timeout_cycles=0` | OK |
| Z.405 `_set_state(WAIT_RR73)` | ✅ Z.405 nachfolgend `timeout_cycles=0` | OK |
| Z.320 (Retry-Block) `_set_state(TX_REPORT)` | ✅ Z.320 nachfolgend `timeout_cycles=0` | OK |
| Z.415 `_set_state(WAIT_73)` | ✅ Z.416 `timeout_cycles=0` | OK |

**Befund:** Bestehender Code IST konsistent — R1's Halluzination bestätigt.
**Defense-in-Depth-Maßnahme V3:** In `_set_state(new_state)` zentral
prüfen + setzen, falls Future-Code einen Eintrittspfad ohne
expliziten Reset einbaut:

```python
def _set_state(self, new_state):
    self.state = new_state
    # Defense: wenn Wartezustand erreicht, Counter zentral resetten.
    # Bestehende explizite Resets bleiben (no-op bei Doppel-Reset).
    if new_state in (QSOState.WAIT_REPORT, QSOState.WAIT_RR73,
                     QSOState.WAIT_73, QSOState.CQ_WAIT):
        if self.qso:
            self.qso.timeout_cycles = 0
```

### Fix B — Encoder-Drift-Guard (`core/encoder.py:204-216`)

**Schwelle 0.3s** (Headroom: 0.5s WSJT-X − 0.1s Encoding − 0.1s Marge).

```python
if silence_secs < 0.1:
    overshoot = now - (next_boundary + TARGET_TX_OFFSET)
    if overshoot > 0.3:
        _SLOT = {"FT8": 15.0, "FT4": 7.5, "FT2": 3.8}.get(self._mode, 15.0)
        next_boundary += (2 * _SLOT) if self.tx_even is not None else _SLOT
        silence_secs = max(0.0, (next_boundary + TARGET_TX_OFFSET) - time.time())
        print(f"[TX] Drift-Vermeidung: overshoot={overshoot:.2f}s "
              f"→ Slot {next_boundary:.1f}")
    else:
        silence_secs = 0.0
        print(f"[TX] Slot-Rand: sofort senden (overshoot={overshoot:.2f}s)")
```

### Fix C — `_next_slot_boundary` Schwelle (`core/encoder.py:158`)

**Problem (R1):** `cycle_pos < (_SLOT/5)` = 3s bei FT8 ist zu großzügig.
Bei Mid-Slot-Triggern (z.B. CQ-Ruf nach Timeout bei `cycle_pos = 7s`)
wird der falsche Slot gewählt.

**Lösung:** Schwelle 3s → 0.5s. Nur wenn TX-Trigger AM SLOT-START feuert,
darf der aktuelle Slot gewählt werden.

```python
# encoder.py:156-167 (NEU)
if self.tx_even is not None:
    want_even = self.tx_even
    # Nur wenn EXAKT am Slot-Start (< 0.5s nach boundary): aktueller Slot
    if is_even == want_even and cycle_pos < 0.5:
        return float(cycle_num * _SLOT)
    # Sonst: naechster passender Slot
    next_num = cycle_num + 1
    next_boundary = float(next_num * _SLOT)
    if (next_num % 2 == 0) != want_even:
        next_boundary += _SLOT
    return next_boundary
else:
    return float((cycle_num + 1) * _SLOT)
```

---

## 4. Akzeptanzkriterien

### A1. DT-Stabilität im QSO
Alle TX-Frames im QSO-Modus DT < 0.3s am Empfänger. Verifikation am Icom
über mind. 5 vollständige QSOs ohne Frame > 0.3s.

### A2. Retry-Cadence WSJT-X-konform
Retry-Reports kommen 30s nach Original (Slot N → Slot N+2).

### A3. Total-Timeout unverändert
3-Min-Hard-Cap aktiv. `MAX_STATION_CALLS`, `MAX_RR73_RETRIES` unverändert.

### A4. Drift-Guard nur bei Edge-Case
`[TX] Drift-Vermeidung`-Log nur bei TX-Triggern die Fix A nicht abdeckt.

### A5. Encoder-Abort wirksam (R1-kritisch)
Wenn während encoder.sleep `abort()` gerufen wird:
- Worker bricht **innerhalb 100ms** ab (nicht nach 14s)
- PTT bleibt aus, kein Audio gesendet
- Verifikation: Test mit Mock-State-Wechsel während `sleep_dur=10s`,
  abort() → Worker returnt vor Audio-Send.

### A6. Bestehende Tests grün
493/493 + neue.

### A7. Neue Tests (siehe Sektion 6)

### A8. Real-Funkbetrieb verifiziert
Mind. 3 echte QSOs ohne Timeout. **Kern-Erfolgskriterium.**

### A9. HALT bricht laufenden Retry ab (R1)
Wenn Mike HALT drückt während encoder im sleep für Retry-TX ist:
- TX wird sofort gestoppt
- PTT aus
- Kein weiteres TX-Frame
- Test: Mock-Sleep, HALT-Trigger, prüfe `tx_started.emit` wurde NICHT gerufen.

### A10. Counter-Reset bei state-change (R1 Defense)
Bei `_set_state(WAIT_*)` ist `timeout_cycles` auf 0. Auch wenn vor
state-change ein Wert > 0 stand. Verifikation: Test
`test_set_state_resets_counter`.

---

## 5. R1-Review der V2 — Schlüssel-Erkenntnisse (zur Erinnerung für V3-Implementation)

R1 hat 3 Race-Conditions analysiert. Wichtigste:

**Race 2 (KRITISCH, jetzt gefixt durch A2):** Worker im `time.sleep(14s)`,
abort() setzt nur Flag, sleep läuft trotzdem 14s durch, Audio wird
gesendet. → V3 Fix A2 mit `threading.Event.wait()` macht sleep cancelable.

**Race 1 (entschärft):** `cycle_decoded` vs `cycle_start` Reihenfolge —
mit Fix A2 ist auch der Worst-Case (Reihenfolge umgekehrt) sauber, weil
encoder jetzt korrekt aborts. Architektur-Umbau abgelehnt.

**Race 3 (gefixt durch C):** `_next_slot_boundary` 3s-Schwelle zu
großzügig → 0.5s.

---

## 6. Implementierungs-Reihenfolge (sobald V3 freigegeben)

```
Commit 1: feat(qso_state): retry-trigger im RX-Slot statt Mike-Slot (Fix A1)
  - qso_state.py:297, 313 timeout_cycles == 2 → == 1
  - 2 neue Tests:
    - test_wait_report_retry_at_cycle_one
    - test_wait_rr73_retry_at_cycle_one

Commit 2: fix(encoder): cancelable sleep via threading.Event (Fix A2 — KRITISCH)
  - encoder.py: _abort_event Member + clear in _tx_worker + set in abort()
  - encoder.py:185-194 time.sleep → _abort_event.wait(timeout=sleep_dur)
  - mw_qso.py:244 vor encoder.transmit() check + abort()
  - 2 neue Tests:
    - test_abort_during_sleep_returns_within_100ms
    - test_state_change_during_encoder_sleep_aborts_pending_tx

Commit 3: fix(qso_state): Counter-Reset zentral in _set_state (Fix A3)
  - qso_state.py _set_state: bei WAIT_*/CQ_WAIT timeout_cycles=0
  - 1 neuer Test: test_set_state_resets_counter_for_wait_states

Commit 4: feat(encoder): drift-guard fuer Slot-Rand-TX (Fix B)
  - encoder.py:204-216 Schwelle 5.0 → 0.3 + Slot-Skip-Logik
  - 2 neue Tests:
    - test_encoder_drift_guard_advances_slot
    - test_encoder_no_drift_below_threshold

Commit 5: fix(encoder): _next_slot_boundary Schwelle 0.5s (Fix C)
  - encoder.py:158 cycle_pos < (_SLOT/5) → < 0.5
  - 1 neuer Test: test_next_slot_boundary_strict_threshold

Commit 6: chore(release): v0.80 — TX-DT-Drift QSO-Retry-Fix (BLOCKER)
  - HISTORY.md mit Workflow-Reflexion (V1→V2→R1→V3, Bilanz)
  - CLAUDE.md Header v0.79 → v0.80
  - main.py APP_VERSION
```

---

## 7. Tests — Vollständige Liste (8 neu)

```
1. test_wait_report_retry_at_cycle_one (Fix A1)
2. test_wait_rr73_retry_at_cycle_one (Fix A1)
3. test_abort_during_sleep_returns_within_100ms (Fix A2 — R1 KRITISCH)
4. test_state_change_during_encoder_sleep_aborts_pending_tx (Fix A2)
5. test_set_state_resets_counter_for_wait_states (Fix A3)
6. test_encoder_drift_guard_advances_slot (Fix B)
7. test_encoder_no_drift_below_threshold (Fix B)
8. test_next_slot_boundary_strict_threshold (Fix C)
```

**Mock-Strategie:**
- `time.time()`: `unittest.mock.patch` mit Side-Effect-Liste
- `threading.Event`: real (kein Mock — Test mit kurzen Timeouts < 100ms)
- Encoder-Tests: kein FlexRadio-Connect, `_radio = None`, Audio wird
  intern erzeugt aber nicht gesendet.

---

## 8. Logging-Strategie

```
[QSO] WAIT_REPORT Retry at cycle 1 — TX in next Mike slot
[QSO] WAIT_RR73 Retry at cycle 1 — TX in next Mike slot
[Encoder] Abort: sleep interrupted by abort_event
[Encoder] State-change pending — abort old TX, schedule new
[TX] Drift-Vermeidung: overshoot=0.45s → Slot 1745923500.0
[TX] Slot-Rand: sofort senden (overshoot=0.12s)
```

---

## 9. Out-of-Scope (Phase 2)

- TARGET_TX_OFFSET dynamisch messen (R1-Vorschlag, abgelehnt für V3)
- IC-7300 Fork (anderer TX-Buffer, separater PR)
- `cycle_start` ↔ `cycle_decoded` Architektur-Umbau (R1-Vorschlag, abgelehnt)
- Konfigurierbare Drift-Schwelle 0.3s (Konstante bleibt)
- TX-Drift-Telemetrie/Histogramm im UI

---

## 10. Rollback-Plan

Wenn Real-QSO-Test (A8) scheitert:
1. **Sofort:** `git revert <commit-1>..<commit-5>` → zurück auf v0.79
2. Verifikation: App-Start, Tests grün, 1 Real-QSO
3. Diagnose: Bisect welcher Commit schuldig ist
4. Re-Plan: V4, neue R1-Runde, neue Implementation

**Schutz:** Vor Commit 1 Backup
`Appsicherungen/2026-04-30_vor_dt_drift_fix/` (volle Code-Kopie).

---

## 11. Verifikation am Ende (vor Commit 6)

1. `./venv/bin/python3 -m pytest tests/ -q` → 493 + 8 neue = 501 grün
2. App-Start, manueller Test:
   - 5 CQs sauber bei DT 0.0–0.1 (Icom-Verifikation)
   - QSO mit DA1TST: alle TX-Frames DT < 0.3s
   - 1× WAIT_REPORT-Retry herbeiführen → DT < 0.3s
   - HALT während laufender Retry-Sleep → TX bricht innerhalb 100ms ab
3. **Real-Station-Test: 3 echte QSOs ohne Timeout (Kern-Erfolgskriterium)**
4. Final-R1-Review der geänderten Files via `tools/deepseek_review.py`
5. Lessons-Learned-Notiz in HISTORY.md

---

**Workflow:** V1 → V2 (Self-Review) → R1-Review → V3 (DIES) →
**Mike-Freigabe ⬅️** → Plan-Mode → 6 atomare Commits → Final-R1 →
Lessons-Learned.

**Mike-Entscheidung erbeten:**
1. V3 freigegeben? (oder Findings ändern?)
2. Backup vor Commit 1 ja/nein?
3. Plan-Mode jetzt oder nach Pause?
