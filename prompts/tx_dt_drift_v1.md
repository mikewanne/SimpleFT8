# V1 — TX-DT-Drift im QSO-Retry-Pfad (BLOCKER)

**Status:** V1 (Self-Review steht aus → V2 → R1 → V3)
**Priorität:** **BLOCKER** — Real-Funkbetrieb unmöglich, weil schwache
Stationen Mike's Folge-Reports nicht decodieren.
**Quelle:** Feldtest 2026-04-30, Icom-Verifikation auf 30m FT8

---

## 1. Symptom (Feldtest-Daten)

Empfangs-Verifikation am Icom (Referenz, kalibriert auf DT 0.0):

| TX-Typ | Beobachtete DT | Stichprobe |
|---|---|---|
| Folge-CQs (CQ_WAIT-Loop) | **0.0–0.1s** | 8/8 sauber |
| Erster Report nach RX-Antwort | **0.1s** | 2/2 sauber |
| RR73-TX nach R-Report | **0.1s** | 2/2 sauber |
| **Folge-Report (WAIT_REPORT-Retry)** | **0.6–0.8s** | **6/6 driftet** |
| **Erster CQ nach QSO-End/Timeout** | **0.6–0.8s** | **2/2 driftet** |

**Konsequenz:** FT8 Auto-Sequence-Decoder verwerfen Frames mit DT > 0.5s.
Schwache Stationen (Real-Funkbetrieb, nicht lokales Icom) hören Mike's
Folge-Reports nicht → keine R+xx Antwort → WAIT_REPORT-Timeout → 7 QSOs
hintereinander gescheitert. Nur lokaler Icom-Test funktioniert (starkes
Signal toleriert Drift).

**Negativ-Beweis:** Vor v0.74 (DT-Optimierung Modus+Band-spezifisch) ging es.
Bug entstand vermutlich beim Umbau auf `TARGET_TX_OFFSET = -0.8`.

---

## 2. Code-Pfad-Diagnose

### Erster Report (DT 0.1, sauber)
Ausgelöst durch `tx_finished`-Signal aus dem TX-Thread MID-CYCLE
(nach `send_audio()` ≈ slot+13.5s):

```
encoder._tx_worker_inner Z.249 tx_finished.emit()
  → mw_qso._on_tx_finished Z.207
  → qso_sm.on_message_sent Z.358
  → CQ_CALLING-Pfad: _process_cq_reply Z.167
  → send_message.emit(report_msg) Z.212
  → mw_qso._on_send_message Z.244 encoder.transmit(message)
  → encoder._next_slot_boundary Z.144 — hat 14s Vorlauf zum nächsten Mike-Slot
  → silence_secs ≈ 14s, Audio startet bei boundary-0.8s, RF bei boundary+0.5s
  → DT = 0.0–0.1 ✓
```

### Folge-CQ (DT 0.1, sauber)
Trigger AM SLOT-RAND, ABER im RX-Slot der Gegenstation:

```
core/timing.py:93 cycle_start.emit(N+1, is_even=False)  ← N+1 = RX-Slot
  → mw_cycle._on_cycle_start Z.492
  → qso_sm.on_cycle_end Z.501
  → CQ_WAIT-Pfad Z.282-289: timeout_cycles=1 → _send_cq Z.149
  → send_message.emit(cq_msg)
  → encoder.transmit
  → encoder._next_slot_boundary: tx_even=True (Mike), is_even=False → mismatch
    → Z.160 next_num = N+2 (Mike-Parität, match)
  → silence_secs ≈ 14s Vorlauf bis N+2 - 0.8s
  → DT = 0.0–0.1 ✓
```

### Folge-Report (DT 0.6–0.8, DRIFTET) — der Bug
Trigger AM SLOT-RAND, aber im **selben Slot** wie Mike sendet:

```
core/timing.py:93 cycle_start.emit(N+2, is_even=True)  ← N+2 = Mike-TX-Slot
  → mw_cycle._on_cycle_start Z.492
  → qso_sm.on_cycle_end Z.501
  → WAIT_REPORT-Pfad Z.291-312: timeout_cycles==2 → Retry
  → _set_state(TX_CALL) + send_message.emit(retry_msg) Z.305
  → encoder.transmit (~50ms später, jetzt bei N+2*15s + 0.15s)
  → encoder._next_slot_boundary: tx_even=True, is_even=True, cycle_pos=0.15 < 3.0
    → Z.158 return cycle_num*_SLOT = N+2*15s (current slot)
  → sleep_dur = (next_boundary + TARGET_TX_OFFSET) - now
              = (N+2*15 - 0.8) - (N+2*15 + 0.15) = -0.95s → kein Sleep
  → silence_secs = max(0, -0.95) = 0
  → encoder.py Z.205-216: silence_secs<0.1, overshoot=0.95 NICHT >5.0
    → "Slot-Rand: sofort senden" silence_secs=0.0
  → Audio startet bei now (slot+0.15)
  → RF nach 1.3s FlexRadio-Buffer-Drain bei slot+1.45
  → erwartet: slot+0.5 → DT = 1.45 - 0.5 = 0.95s — driftet ✗
```

### Erster CQ nach QSO-End (DT 0.6–0.8, DRIFTET) — gleiche Wurzel
`_resume_cq_if_needed` Z.338-352 ruft `_send_cq()` direkt aus
`on_cycle_end` heraus (Z.270, 279) — gleicher Slot-Rand-Trigger im
Mike-TX-Slot wie Folge-Report.

**Zusammenfassung Wurzel:** Trigger-Zeitpunkt für TX im selben Slot wo
gesendet werden soll. Encoder hat 0s Vorlauf. „Slot-Rand: sofort senden"-
Pfad in `encoder.py:204-216` springt mit overshoot 0.6–0.95s an, statt
zum nächsten passenden Slot weiterzuschalten.

---

## 3. Lösung — Hybrid A+B (Defense-in-Depth)

### Fix A — Trigger-Zeitpunkt korrigieren (`core/qso_state.py`)

**Ziel:** Retry-Trigger im RX-Slot der Gegenstation feuern (nicht im
Mike-TX-Slot). Encoder hat dann 14s Vorlauf zum nächsten Mike-Slot.
Retry-TX-Timing bleibt identisch zur jetzigen Logik (immer Slot N+2).

| Stelle | aktuell | neu | Kommentar |
|---|---|---|---|
| `qso_state.py:297` WAIT_REPORT | `if self.qso.timeout_cycles == 2:` | `== 1` | Trigger 1 Slot früher (RX-Slot) |
| `qso_state.py:313` WAIT_RR73 | (gleiche Schwelle in selbem Block) | `== 1` | analog |
| `qso_state.py:331` Total-Timeout | `>= self.qso.max_timeout` | unverändert | Final-Timeout bleibt |
| `qso_state.py:267` MAX_QSO_DURATION | unverändert | unverändert | 3-Min-Hard-Cap bleibt |
| `qso_state.py:339-352` `_resume_cq_if_needed` | `_send_cq()` direkt | unverändert (siehe Fix B) | Hier kann B greifen |

**Wichtig:** `timeout_cycles` zählt seit `WAIT_REPORT`-Eintritt. War vor
Fix `>= 2` (= 30s = 2 Slots). Nach Fix `>= 1` (= 15s = 1 Slot Wartezeit
bevor Retry getriggert wird, aber Retry-TX erst in N+2 = effektiv 30s
nach Original-TX wegen Encoder-Slot-Wahl).

### Fix B — Encoder-Drift-Guard (`core/encoder.py:204-216`)

**Ziel:** Safety-Net für jeden TX-Trigger der zukünftig falsch getimed
sein könnte. Verhindert dass „Slot-Rand: sofort senden" mit overshoot
> 0.3s Frames mit DT > 0.5s sendet.

```python
# encoder.py Z.204-216 (NEU)
if silence_secs < 0.1:
    overshoot = now - (next_boundary + TARGET_TX_OFFSET)
    # FT8-Decode-Schwelle: DT > 0.5s wird verworfen.
    # overshoot > 0.3s ergibt RF-DT > 0.3s, nahe der Schwelle.
    # Lieber zum naechsten passenden Slot weiterschalten.
    if overshoot > 0.3:
        _SLOT = {"FT8": 15.0, "FT4": 7.5, "FT2": 3.8}.get(self._mode, 15.0)
        # tx_even gesetzt → 2 Slots (gleiche Paritaet) sonst 1 Slot
        next_boundary += (2 * _SLOT) if self.tx_even is not None else _SLOT
        silence_secs = max(0.0, (next_boundary + TARGET_TX_OFFSET) - time.time())
        print(f"[TX] Drift-Vermeidung: overshoot={overshoot:.2f}s "
              f"→ naechster Slot bei {next_boundary:.1f}")
    else:
        # Knapp am Ziel (overshoot < 0.3s, RF-DT < 0.5s) → sofort senden
        silence_secs = 0.0
        print(f"[TX] Slot-Rand: sofort senden (overshoot={overshoot:.2f}s)")
```

**Konsequenz:** Fix A löst den normalen Retry-Pfad sauber (kein 30s-
Verzögerungs-Cost). Fix B greift nur bei Edge-Cases die Fix A nicht
abdeckt (z.B. `_resume_cq_if_needed` beim QSO-Timeout, oder neue TX-
Trigger die später eingebaut werden).

---

## 4. Akzeptanzkriterien

### A1. DT-Stabilität im QSO
Alle TX-Frames im QSO-Modus (CQ, TX_CALL, TX_REPORT, TX_RR73, retries)
müssen am Empfänger DT < 0.3s zeigen. Verifikation am Icom über
mindestens 5 vollständige QSOs (CQ → Reply → Report → R-Report → RR73 →
73) ohne einen Frame > 0.3s.

### A2. Retry-Cadence WSJT-X-konform
Retry-Reports müssen 30s nach Original-Report bei der Gegenstation
ankommen (Slot N → Slot N+2). Verifikation: Logs prüfen
`[QSO] WAIT_REPORT Retry` Timestamps.

### A3. Total-Timeout unverändert
3-Min-Hard-Cap (`MAX_QSO_DURATION`) bleibt aktiv. Maximale Retry-Anzahl
(`MAX_STATION_CALLS`, `MAX_RR73_RETRIES`) unverändert.

### A4. Encoder-Drift-Guard greift NUR im Edge-Case
Bei normalem Betrieb (Fix A korrekt) feuert die `[TX] Drift-Vermeidung`-
Log-Zeile NIE. Sie taucht nur auf wenn ein TX-Trigger den Slot-Rand
verfehlt — dann sind die Frames trotzdem decode-fest.

### A5. Bestehende Tests grün
`./venv/bin/python3 -m pytest tests/ -q` → 493/493 passed.
Insbesondere `tests/test_modules.py:471, 482, 493, 1249` (`on_message_sent`-
Pfade) und Encoder-bezogene Tests müssen weiter passen oder angepasst werden.

### A6. Neue Tests
- `test_wait_report_retry_triggers_at_cycle_one`: parametrisierter Test
  dass `on_cycle_end()` mit `timeout_cycles == 1` einen Retry triggert.
- `test_wait_rr73_retry_triggers_at_cycle_one`: analog für `WAIT_RR73`.
- `test_encoder_drift_guard_advances_slot`: Mock-Slot-Boundary +
  künstlicher overshoot > 0.3 → next_boundary += 2*_SLOT bei
  `tx_even is not None`.
- `test_encoder_no_drift_below_threshold`: overshoot 0.2 → silence_secs=0
  (sofort senden), boundary unverändert.

---

## 5. R1-Review-Auftrag (V2 → R1)

R1 soll **NICHT** das Problem lösen, sondern den V2-Prompt kritisieren
auf:

### a) Race-Conditions
- Was passiert wenn ein decode-Event (RX-Antwort von Gegenstation)
  IM SELBEN Cycle wie der Retry-Trigger feuert? Konkret:
  Slot N+1 startet → `on_cycle_end()` → `timeout_cycles=1` → Retry-Trigger
  PARALLEL kommt die R+xx-Antwort der Gegenstation rein → Race?
- `on_cycle_end()` läuft im GUI-Thread (timing.py emit aus Tick-Thread,
  Qt.AutoConnection → QueuedConnection). `on_message_received` läuft
  ebenfalls im GUI-Thread. Beide Slots in qso_state.py — Race ausgeschlossen?
- Was passiert wenn `_pending_hunt_reply`/`_pending_rr73` zwischen
  Trigger und encoder.transmit() gesetzt wird?

### b) Edge-Cases im Retry-Counter
- Aktueller `WAIT_REPORT`-Counter zählt Z.292 in jedem `on_cycle_end`-
  Aufruf hoch. Bei `== 1` triggern: erster `on_cycle_end` nach State-
  Wechsel zu `WAIT_REPORT` setzt counter=1 und triggert → ist das schon
  zu früh? (Z.B. wenn TX gerade fertig ist und sofort der nächste
  cycle_start kommt).
- Welche Garantie haben wir dass `on_message_sent` BEVOR dem nächsten
  `on_cycle_end` läuft?

### c) FlexRadio-Buffer-Verhalten
- `TARGET_TX_OFFSET = -0.8` basiert auf einem konstanten 1.3s TX-Buffer.
  Ist der Buffer wirklich konstant oder schwankt er bei Cold-Starts?
- Falls schwankend: Fix B 0.3-Schwelle könnte zu eng sein. Vorschlag?

### d) Encoder-Slot-Boundary-Semantik
- `_next_slot_boundary` Z.144: bei `tx_even is not None` und
  Parity-Match + cycle_pos < `_SLOT/5` → CURRENT slot.
  - 1/5 = 20% des Slots = 3.0s bei FT8.
  - Ist das ok? Oder sollte nur cycle_pos < 0.5s (vor dem WSJT-X-
    Protokoll-Start bei +0.5s) als „aktueller Slot OK" zählen?

### e) Test-Vollständigkeit
- Decken die 4 vorgeschlagenen Tests alle Pfade ab?
- Welche Mock-Strategie für `time.time()` in encoder-Tests?

### f) Fehlende oder unklare Akzeptanzkriterien
- Was übersieht V1?

---

## 6. Implementierungs-Reihenfolge (sobald V3 freigegeben)

```
Commit 1: feat(qso_state): retry-trigger im RX-Slot statt Mike-Slot (Fix A)
  - qso_state.py:297, 313 timeout_cycles == 2 → == 1
  - 2 neue Tests test_wait_report_retry_at_cycle_one,
    test_wait_rr73_retry_at_cycle_one
  - Bestehende Tests anpassen (test_modules.py prüfen)

Commit 2: feat(encoder): drift-guard fuer Slot-Rand-TX (Fix B)
  - encoder.py:204-216 Threshold 5.0 → 0.3 + Slot-Skip-Logik
  - 2 neue Tests test_encoder_drift_guard_advances_slot,
    test_encoder_no_drift_below_threshold

Commit 3: chore(release): v0.80 — TX-DT-Drift QSO-Retry-Fix (BLOCKER)
  - HISTORY.md Eintrag mit Workflow-Reflexion
  - CLAUDE.md Header v0.79 → v0.80, Test-Count Update
  - main.py APP_VERSION
```

---

## 7. Out-of-Scope (Phase 2 / nicht jetzt)

- TARGET_TX_OFFSET pro Station messen (encoder._station_dt_offset)
- IC-7300 Fork (anderer TX-Buffer)
- Konfigurierbare Drift-Schwelle (`0.3` als Konstante)
- TX-Drift-Telemetrie/Histogramm im UI

---

## 8. Verifikation am Ende (vor Commit 3)

1. `./venv/bin/python3 -m pytest tests/ -q` → 493 + 4 neue = 497 grün
2. App-Start, manueller QSO-Test:
   - CQ-Modus: 5 CQs sauber bei DT 0.0–0.1 (Icom-Verifikation)
   - QSO mit DA1TST: alle TX-Frames DT < 0.3s
   - 1× WAIT_REPORT-Retry herbeiführen (Icom Auto-Sequence kurz
     deaktivieren, Mike sendet Report, Retry kommt nach 30s) → DT < 0.3s
3. Real-Station-Test: 3 echte QSOs (nicht-lokal) komplettieren ohne
   Timeout-Fehler. **Wenn das klappt, ist der Bug tot.**
4. R1-Final-Review der geänderten Files via `tools/deepseek_review.py`

---

**Workflow-Erinnerung:** V1 → Self-Review → V2 → R1-Review → V3 →
Mike-Freigabe → Plan-Mode → 3 atomare Commits → Final-R1 → Lessons-Learned.
