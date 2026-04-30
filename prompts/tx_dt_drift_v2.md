# V2 — TX-DT-Drift im QSO-Retry-Pfad (BLOCKER) [Self-Review-Ergebnis]

**Status:** V2 (nach Self-Review von V1) → R1-Review-Auftrag
**Vorgänger:** `prompts/tx_dt_drift_v1.md`
**Self-Review-Findings:** 8 Lücken in V1 entdeckt, hier eingearbeitet.

---

## 0. Self-Review-Bilanz V1 → V2

| # | V1-Lücke | V2-Lösung |
|---|---|---|
| 1 | Race: spätes `cycle_decoded` (T+14.5) kollidiert mit Retry-Trigger (T+15) — Antwort kommt nach Retry-Schedule | Sektion 5a expanded, encoder.abort()-Hook in Lösung A |
| 2 | encoder.abort() bei state-change während encoder.sleep — fehlt komplett | NEU Sektion 3a (Fix A2) |
| 3 | Drift-Schwelle 0.3s war Bauchgefühl, keine Begründung | Sektion 3b: Headroom-Berechnung 0.5s WSJT-X − Audio-Latency − Sicherheits-Marge |
| 4 | `tx_even is None` Edge-Case nicht analysiert | Sektion 3b Tabelle expliziert beide Pfade |
| 5 | Tests deckten nur Happy-Path ab | Sektion 6 erweitert: 3 zusätzliche Race-/Edge-Tests |
| 6 | `WAIT_RR73`-Pfad teilt `rr73_retries` Counter (nicht `timeout_cycles`!) — Fix A muss das beachten | Sektion 3a: explizite Tabelle pro Counter |
| 7 | Rollback-Plan fehlte | Sektion 9 NEU |
| 8 | Logging-Format nicht spezifiziert | Sektion 7 NEU (Debug-Log-Struktur) |

---

## 1. Symptom (Feldtest-Daten — unverändert aus V1)

Empfangs-Verifikation am Icom (Referenz, kalibriert auf DT 0.0):

| TX-Typ | Beobachtete DT | Stichprobe |
|---|---|---|
| Folge-CQs (CQ_WAIT-Loop) | **0.0–0.1s** | 8/8 sauber |
| Erster Report nach RX-Antwort | **0.1s** | 2/2 sauber |
| RR73-TX nach R-Report | **0.1s** | 2/2 sauber |
| **Folge-Report (WAIT_REPORT-Retry)** | **0.6–0.8s** | **6/6 driftet** |
| **Erster CQ nach QSO-End/Timeout** | **0.6–0.8s** | **2/2 driftet** |

**Konsequenz:** FT8 Auto-Sequence-Decoder verwerfen Frames mit DT > 0.5s.
7 Real-QSOs hintereinander gescheitert, nur lokaler Icom-Test funktioniert.

**Negativ-Beweis:** Vor v0.74 ging es. Bug entstand vermutlich beim
Umbau auf `TARGET_TX_OFFSET = -0.8`.

---

## 2. Code-Pfad-Diagnose (kompakt — Details siehe V1 Sektion 2)

**Wurzel:** `on_cycle_end` Z.501 in `mw_cycle._on_cycle_start` triggert
`WAIT_REPORT`-Retry bei `timeout_cycles == 2` AM Anfang von Mike's TX-Slot
(N+2). Encoder hat 0s Vorlauf, „Slot-Rand: sofort senden"-Pfad
(`encoder.py:204-216`) sendet mit overshoot 0.95s → DT 0.95s.

**Folge-CQ ist sauber**, weil dort der Trigger bei `timeout_cycles == 1`
im RX-Slot der Gegenstation feuert (Z.287) → Encoder schedulet zu Slot
N+2 mit 14s Vorlauf.

---

## 3. Lösung — Hybrid A+B mit Race-Condition-Schutz

### Fix A1 — Trigger-Zeitpunkt korrigieren (`core/qso_state.py`)

**Ziel:** Retry-Trigger im RX-Slot der Gegenstation, nicht im Mike-TX-Slot.

| Stelle | Counter | aktuell | neu |
|---|---|---|---|
| `qso_state.py:297` `WAIT_REPORT` | `qso.timeout_cycles` | `== 2` | `== 1` |
| `qso_state.py:313` `WAIT_RR73` | `qso.timeout_cycles` (gleicher Block) | `== 2` | `== 1` |
| `qso_state.py:315` `WAIT_RR73` retry-counter | `qso.rr73_retries` (eigener!) | `<= MAX_RR73_RETRIES` | unverändert |
| `qso_state.py:299` `WAIT_REPORT` retry-counter | `qso.calls_made` < `station_limit` | unverändert | unverändert |
| `qso_state.py:331` Final-Timeout | `>= qso.max_timeout` | unverändert | unverändert |
| `qso_state.py:267` `MAX_QSO_DURATION` | unverändert | unverändert | 3-Min-Hard-Cap bleibt |

**Wichtig:** `qso.timeout_cycles` zählt seit State-Eintritt. `rr73_retries`
und `calls_made` sind UNABHÄNGIGE Counter die Anzahl-Limits durchsetzen.
Fix A1 ändert NUR `timeout_cycles`-Schwelle, nicht die Anzahl-Limits.

### Fix A2 — Encoder-Abort bei State-Change während sleep

**Problem:** Wenn Retry mit 14s Vorlauf scheduled ist und in dieser Zeit
eine Antwort der Gegenstation reinkommt (state-change zu TX_RR73 oder
WAIT_RR73), läuft Encoder weiter und sendet veraltete Message.

**Aktuell schon vorhanden (encoder.py:65-68):**
```python
def abort(self):
    self._is_transmitting = False
```
+ encoder.py Z.191-194: Abort-Check während Wait-Phase.
+ Z.66 Kommentar: „Bandwechsel, Notaus".

**Aufrufer-Audit:**
```
grep encoder.abort() / self.encoder.abort()
  → ui/mw_radio.py:1001 (_on_dx_tune_rejected)
  → ui/mw_radio.py:??? (band-change?)
  → KEIN Aufruf bei state-change in qso_state
```

**Lösung Fix A2:** In `qso_state.py` bei state-changes die einen
laufenden encoder.transmit ungültig machen, ein neues Signal
`abort_pending_tx` emittieren. mw_qso connectet auf encoder.abort().

Stellen die emit brauchen:
- `on_message_received` Z.477-548 in `WAIT_REPORT/TX_CALL/TX_REPORT`
  bei pending RR73/73/R-Report-Vorwärts-Sprung
- _process_cq_reply (greift schon)? — mid-cycle, encoder ist nicht im sleep

**Alternative simpler:** mw_qso vor encoder.transmit() prüft ob bereits
ein TX scheduled ist und ruft encoder.abort() falls state-Wechsel
stattfand. Macht Z.244 zu:
```python
if self.encoder.is_transmitting:
    self.encoder.abort()  # alte gescheduled abort
self.encoder.transmit(message)
```

→ Mike entscheidet zwischen Signal- oder Inline-Variante. Empfehlung:
**Inline** (KISS, keine neue Signal-Verbindung).

### Fix B — Encoder-Drift-Guard (`core/encoder.py:204-216`)

**Schwellen-Begründung 0.3s:**
- WSJT-X-Decode-Schwelle: DT > 0.5s wird verworfen
- Audio-Encoding-Latency: 50-100ms
- FlexRadio-Buffer-Drain ist *konstant* 1.3s (laut HISTORY/Mike Validierung)
- → 0.5s Headroom − 0.1s Encoding − 0.1s Sicherheits-Marge = **0.3s** max overshoot
- Bei overshoot > 0.3s: empfangene DT könnte ≥ 0.4s werden → riskant
- 0.3s konservativ, lieber zum nächsten Slot springen

**Slot-Skip-Logik:**

| `tx_even` | Skip-Schritt | Warum |
|---|---|---|
| `is not None` | `+ 2*_SLOT` | Parity-Erhalt (gleicher Slot) |
| `is None` | `+ _SLOT` | Keine Parity-Bindung |

**Code (encoder.py Z.204-216, NEU):**
```python
if silence_secs < 0.1:
    overshoot = now - (next_boundary + TARGET_TX_OFFSET)
    # Drift-Schwelle 0.3s (Headroom: 0.5 WSJT-X - 0.1 Encoding - 0.1 Marge).
    # Drueber: lieber zum naechsten passenden Slot weiterschalten.
    if overshoot > 0.3:
        _SLOT = {"FT8": 15.0, "FT4": 7.5, "FT2": 3.8}.get(self._mode, 15.0)
        next_boundary += (2 * _SLOT) if self.tx_even is not None else _SLOT
        silence_secs = max(0.0, (next_boundary + TARGET_TX_OFFSET) - time.time())
        print(f"[TX] Drift-Vermeidung: overshoot={overshoot:.2f}s "
              f"→ Slot {next_boundary:.1f}")
    else:
        # Knapp am Ziel (overshoot < 0.3s) → sofort senden
        silence_secs = 0.0
        print(f"[TX] Slot-Rand: sofort senden (overshoot={overshoot:.2f}s)")
```

---

## 4. Akzeptanzkriterien (erweitert)

### A1. DT-Stabilität im QSO
Alle TX-Frames im QSO-Modus DT < 0.3s am Empfänger. Verifikation am
Icom über mind. 5 vollständige QSOs ohne Frame > 0.3s.

### A2. Retry-Cadence WSJT-X-konform
Retry-Reports kommen 30s nach Original (Slot N → Slot N+2).
Verifikation: Logs `[QSO] WAIT_REPORT Retry` Timestamps prüfen.

### A3. Total-Timeout unverändert
3-Min-Hard-Cap aktiv. `MAX_STATION_CALLS`, `MAX_RR73_RETRIES` unverändert.

### A4. Drift-Guard nur bei Edge-Case
`[TX] Drift-Vermeidung`-Log nur bei TX-Triggern die Fix A nicht abdeckt.
Im normalen Betrieb NIE.

### A5. Encoder-Abort bei State-Change
Wenn während encoder.sleep eine Antwort den State wechselt, alter TX
wird abgebrochen, neuer TX (mit korrektem Message) scheduled.
Verifikation: Test-Szenario `WAIT_REPORT` → spätes RR73 → encoder.abort
+ TX_73-Schedule.

### A6. Bestehende Tests grün
`./venv/bin/python3 -m pytest tests/ -q` → 493/493 + neue.
Insbesondere `tests/test_modules.py:471, 482, 493, 1249` prüfen
(`on_message_sent`-Pfade).

### A7. Neue Tests (siehe Sektion 6)

### A8. Real-Funkbetrieb verifiziert
Mind. 3 echte (nicht-lokal) QSOs ohne Timeout. **Kern-Akzeptanzkriterium.**

---

## 5. R1-Review-Auftrag (V2 → R1)

R1 soll den V2-Prompt **kritisieren und konkret verbessern** —
NICHT das Problem direkt lösen. Fokus auf:

### a) Race-Conditions (PRIO 1)

**Race 1: cycle_decoded vs cycle_start**
- Decoder emittiert `cycle_decoded` bei ~T+14.5s (slot+14.5)
- tick_loop emittiert `cycle_start` bei T+15.0 (= slot N+1 start)
- Beide laufen über Qt-Signal → GUI-Thread → Event-Loop sequentiell.
- **Frage R1:** Kann die Reihenfolge bei CPU-Last umkehren? Falls ja:
  was passiert wenn `on_cycle_end` BEVOR der RX-Antwort-Verarbeitung läuft?
- Sub-Frage: Decoder läuft als QObject in Thread → Qt.AutoConnection
  liefert `Qt.QueuedConnection`. Garantie der Reihenfolge in Event-Loop?

**Race 2: Decode-Lag → Retry-Trigger feuert vor Antwort-Verarbeitung**
- Slot N: Mike sendet TX_CALL
- Slot N+1: WAIT_REPORT, IQ4JO antwortet
- T+14.5 cycle_decoded → on_message_received verarbeitet R-Antwort
- ABER bei Decode-Lag (CPU-Last): cycle_decoded erst T+15.5 (= 0.5s nach
  cycle_start für N+2)
- Bei T+15.0: cycle_start → on_cycle_end → Fix A: counter==1 → Retry
- Bei T+15.5: cycle_decoded → on_message_received → R-Antwort kommt
  zu spät, encoder ist bereits im sleep für RetryTX in N+2
- Mike sendet REPORT-Retry obwohl Antwort da → Aborted? Nein, encoder
  läuft weiter im sleep → Retry-TX wird gesendet → kollidiert mit
  Mike's eigener TX_RR73-State?
- **Frage R1:** Reicht Fix A2 (encoder.abort vor neuem transmit)?
  Oder braucht es früheren Decoder-Drain?

**Race 3: tick_loop 100ms Polling-Intervall**
- timing.py:96 `time.sleep(0.1)` → cycle_start kann bis 100ms verspätet
  feuern.
- Wenn Verspätung 100ms ist: Trigger bei T+15.1, cycle_pos=0.1.
- Bei tx_even-Match → next_boundary=current → encoder schedulet zu Slot
  N+1 (RX-Slot der Gegenstation)? FALSCH! Der RX-Slot ist nicht Mike's
  Slot, dort darf Mike NICHT senden.
- **Frage R1:** Garantiert Z.158 `cycle_pos < (_SLOT/5)` (= 3s) immer
  korrekte Slot-Wahl, oder kann Race in Slot-Mitte falsch entscheiden?

### b) Edge-Cases im Counter

**Counter-Race: timeout_cycles=0 → 1**
- `_set_state(WAIT_REPORT)` Z.391 setzt `timeout_cycles=0`
- Direkt danach kommt cycle_start für N+1 → counter=1 → Fix A trigger
- Aber state-change und cycle_start sind beide GUI-Thread, sequentiell
- Garantie: state-change ist VOR cycle_start (state-change passiert
  in `on_message_sent`, das via `tx_finished`-Signal aus TX-Thread
  kommt — könnte das ZUR SLOT-GRENZE feuern und nach cycle_start landen?)

**TX-Thread-Lifecycle:**
- encoder.send_audio() blockiert bis Audio gesendet (~13.5s)
- Danach ptt_off (Z.247) und tx_finished.emit (Z.249)
- Kann blockierendes send_audio bis slot+14.5 oder länger dauern?
- → on_message_sent feuert dann nach cycle_start für N+1
- **Frage R1:** Wann genau feuert tx_finished? Welche Garantie für
  Reihenfolge mit cycle_start?

**TX_REPORT direkt von _process_cq_reply (initialer TX, nicht Retry):**
- _process_cq_reply Z.211 `_set_state(TX_REPORT)` + send_message.emit
- Counter timeout_cycles ist auf welchem Wert? Wird nach state-Wechsel
  zu TX_REPORT nicht expliziet auf 0 gesetzt — nur in _set_state-Helper?

### c) FlexRadio-Buffer-Verhalten

- `TARGET_TX_OFFSET = -0.8` basiert auf konstantem 1.3s Buffer.
- Validiert in HISTORY (DT-Optimierung 23.04.) — aber unter welchen
  Bedingungen? Cold-Start, Warm-Start, nach langer Pause?
- **Frage R1:** Kann der Buffer bei Cold-Start (nach 30s+ Pause) länger
  sein? Sollte Fix B die 0.3s-Schwelle dynamisch anpassen?

### d) Slot-Boundary-Semantik

- `_next_slot_boundary` Z.144: bei `cycle_pos < _SLOT/5` (= 3s bei FT8)
  → CURRENT slot.
- 3s Toleranz ist großzügig. WSJT-X-Protokoll-Start ist bei +0.5s.
- **Frage R1:** Sollte die Schwelle enger sein (z.B. 0.5s)? Bei welchen
  TX-Triggern feuert sie aktuell?

### e) Test-Strategie

- Wie mocked man `time.time()` für encoder-Tests sauber? `freezegun`?
  `unittest.mock.patch`? Inline-Variable?
- Wie testet man Race zwischen `on_cycle_end` und `on_message_received`?
  → Synchroner Test mit `qso_state` direkt (keine Qt-Signals)?

### f) Fehlende Akzeptanzkriterien

- Nicht abgedeckt: was wenn Antwort EXAKT im Slot N+2 (= Mike's Retry-
  Slot) kommt? Reihenfolge encoder-sleep vs cycle_start?

---

## 6. Implementierungs-Reihenfolge (sobald V3 freigegeben)

```
Commit 1: feat(qso_state): retry-trigger im RX-Slot statt Mike-Slot (Fix A1)
  - qso_state.py:297, 313 timeout_cycles == 2 → == 1
  - 2 neue Tests:
    - test_wait_report_retry_at_cycle_one
    - test_wait_rr73_retry_at_cycle_one

Commit 2: fix(encoder): abort pending TX bei state-change (Fix A2)
  - mw_qso.py:244 vor encoder.transmit() check + abort
  - 1 neuer Test:
    - test_state_change_during_encoder_sleep_aborts_pending_tx

Commit 3: feat(encoder): drift-guard fuer Slot-Rand-TX (Fix B)
  - encoder.py:204-216 Schwelle 5.0 → 0.3 + Slot-Skip-Logik
  - 2 neue Tests:
    - test_encoder_drift_guard_advances_slot
    - test_encoder_no_drift_below_threshold

Commit 4: chore(release): v0.80 — TX-DT-Drift QSO-Retry-Fix (BLOCKER)
  - HISTORY.md mit Workflow-Reflexion
  - CLAUDE.md Header v0.79 → v0.80
  - main.py APP_VERSION
```

---

## 7. Logging-Strategie

Neue Debug-Logs für Feldtest-Verifikation:

```
[QSO] WAIT_REPORT Trigger im RX-Slot (cycle 1) — Retry geplant
[QSO] WAIT_RR73 Trigger im RX-Slot (cycle 1) — Retry geplant
[TX] Drift-Vermeidung: overshoot=0.45s → Slot 1745923500.0
[Encoder] Abort: state-change während sleep
```

Format-Regel: `[Modul] Aktion: Detail` — konsistent mit bestehender
Codebase (encoder.py: `[TX]` / `[Encoder]`, qso_state.py: `[QSO]`).

---

## 8. Out-of-Scope (Phase 2)

- TARGET_TX_OFFSET pro Station messen
- IC-7300 Fork (anderer TX-Buffer)
- Konfigurierbare Drift-Schwelle (`0.3` als Konstante bleibt)
- TX-Drift-Telemetrie/Histogramm im UI
- Decoder-Lag-Adaption (Drain vor cycle_start)

---

## 9. Rollback-Plan

Wenn Real-QSO-Test (A8) nach Fix scheitert:

1. **Sofort:** `git revert <commit-1>..<commit-3>` → zurück auf v0.79
2. **Verifikation:** App-Start, Tests grün, Real-QSO 1× zur Bestätigung
3. **Diagnose:** Welcher Commit hat Probleme gemacht? Bisect.
4. **Re-Plan:** V3 anpassen, neue R1-Runde, neue Implementation.

**Schutz:** Vor Commit 1 Backup `Appsicherungen/2026-04-30_vor_dt_fix/`
(volle Code-Kopie, 1.2 GB).

---

## 10. Verifikation am Ende (vor Commit 4)

1. `./venv/bin/python3 -m pytest tests/ -q` → 493 + 5 neue = 498 grün
2. App-Start, manueller Test:
   - 5 CQs sauber bei DT 0.0–0.1 (Icom-Verifikation)
   - QSO mit DA1TST: alle TX-Frames DT < 0.3s
   - 1× WAIT_REPORT-Retry herbeiführen → DT < 0.3s
3. **Real-Station-Test: 3 echte QSOs ohne Timeout (= Kern-Erfolgskriterium)**
4. Final-R1-Review der geänderten Files via `tools/deepseek_review.py`
5. Lessons-Learned-Notiz in HISTORY.md

---

**Workflow-Erinnerung:** V1 → V2 (DIES) → R1-Review → V3 → Mike-Freigabe
→ Plan-Mode → 4 atomare Commits → Final-R1 → Lessons-Learned.
