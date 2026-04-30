# Fix D — Aufgespaltene Slot-End-Verarbeitung (Doppel-Report-Bug) — V3

**Status:** V3 (nach R1-Review von V2, vor Mike-Freigabe).
**Datum:** 2026-04-30.
**Vorgaenger:** v0.80 (commit `c190df7`) — TX-DT-Drift-Fix.

---

## 0. Kontext

v0.80 hat den TX-DT-Drift-Bug behoben (Fix A1 zog Retry-Trigger 1 Slot
nach vorne). Damit wurde ein zweiter latenter Bug sichtbar:
**Doppel-Report im QSO-Verlauf**, weil `on_cycle_end()` heute am
Slot-START laeuft (Timer-getriggert) — also BEVOR der Decoder die
Antwort der Gegenstation sehen konnte.

Symptom (Icom-Empfangs-Log 30.04. 08:32-33):
```
08:32:45 [O] Mike → "DA1TST DA1MHH -21"        (initial-call)
08:33:00 [E] DA1TST → R+18                      (Antwort, decoded ~T+29.5s)
08:33:15 [O] Mike → "DA1TST DA1MHH -21"        (DOPPEL — BUG!)
08:33:45 [O] Mike → "DA1TST DA1MHH RR73"       (endlich)
```

---

## 1. R1-Review-Bilanz V2 → V3

R1-Review (deepseek-reasoner) hat 2 kritische Findings ergeben:

### R1-P6 (BLOCKER, eigeninitiativ): CQ_WAIT-Regression

V2-Plan ("on_cycle_end komplett ans Slot-Ende verschieben") wuerde
**CQ_WAIT-Trigger** brechen, wenn `_decode_loop` skipt
(`decoder.py:190-203` busy/empty buffer, oder Z.296-298 Exception).
Im aktuellen Code laeuft on_cycle_end Timer-getriggert auch bei
Decoder-Hang weiter — `CQ_WAIT → re-CQ` tickt weiter. Mit V2-Plan:
CQ-Ruf bleibt stehen bis Decoder wieder dekodiert.

R1-Empfehlung: **Aufspaltung** — nur den Retry-Pfad
(WAIT_REPORT/WAIT_RR73 mit `timeout_cycles == 1`) ans Slot-Ende
verschieben, der Rest bleibt am Slot-START.

### R1-P1 (zugehoerig): Decoder-Hang friert Counter ein

Aus dem gleichen Grund: V2-Plan friert auch 3-Min-Gesamttimeout und
WAIT_73-Tick ein, wenn Decoder haengt. R1: nicht tragbar.

→ Auch durch Aufspaltung geloest.

### R1-P2 (TRADEOFF, akzeptiert): FT4/FT2 Drift-Guard

R1: bei FT4/FT2 wahrscheinlich +1 oder +2 Slots Verzoegerung des
Retry. Akzeptabel, weil Gegenstation mehrere Slots wartet. Keine
Code-Aenderung. Dokumentieren.

### R1-P3 (TRADEOFF, akzeptiert): cross-sender Race-Condition

Theoretisch moeglich aber praktisch sehr selten (Decoder typ. <3s,
Slot 15s). Falls Logs spaeter Races zeigen: `_omni_tx.advance` ins
Slot-Ende verschieben. Aktuell keine Aenderung.

### R1-P4 (akzeptiert): auto_hunt-Reihenfolge

Mit Aufspaltung laeuft on_cycle_end weiterhin am Slot-Start,
ANT auto_hunt am Slot-Ende. Reihenfolge wie heute, kein Konflikt.

### R1-P5 (Test-Strategie)

R1: Mock-basierter Test ohne MainWindow moeglich.
`unittest.mock.MagicMock` fuer qso_sm, direkter Aufruf von
`_on_cycle_decoded`, call-order via Mock-Container.

→ V3 nimmt das auf in Sektion 3.3.

---

## 2. Loesung (R1-Aufspaltung)

### 2.1 Was bleibt im Slot-START (`mw_cycle.py:_on_cycle_start`)

`qso_sm.on_cycle_end()` BLEIBT in Z.501. Diese Methode behandelt:
- 3-Min-Gesamttimeout (qso_state.py:275-284)
- WAIT_73-Tick (Z.285-291)
- CQ_WAIT-Trigger (Z.293-300)
- Counter-Inkrement fuer WAIT_REPORT/WAIT_RR73 (Z.303)
- Max-Timeout-Check (Z.348-353)

**Diese Funktionen sollen Decoder-unabhaengig weitertickern**,
damit auch bei Decoder-Hang/leerem Audio-Buffer der QSO-Lifecycle
weiterlaeuft.

**ENTFERNT** wird nur der Retry-Trigger-Pfad (Z.314-346, der
`if self.qso.timeout_cycles == 1: ... self.send_message.emit(...)`-
Block). Der wandert in eine NEUE Methode `on_decoder_finished()`.

### 2.2 Was kommt ins Slot-ENDE (`mw_cycle.py:_on_cycle_decoded`)

Neue Methode `qso_sm.on_decoder_finished()` wird im
`_on_cycle_decoded` NACH den Message-Handlern aufgerufen. Sie
triggert NUR den Retry-Pfad fuer WAIT_REPORT/WAIT_RR73:

```python
def on_decoder_finished(self):
    """Wird nach jedem Decoder-Lauf am Slot-Ende aufgerufen.

    Triggert Retry fuer WAIT_REPORT/WAIT_RR73, wenn die Gegenstation
    in diesem Slot NICHT geantwortet hat (timeout_cycles == 1, gesetzt
    durch on_cycle_end am Slot-Start). Wenn die Antwort dekodiert
    wurde, hat on_message_received bereits state-gewechselt → kein
    Retry-Trigger.
    """
    if self.state == QSOState.WAIT_REPORT and self.qso.timeout_cycles == 1:
        # Retry-Logik aus on_cycle_end:Z.314-329 hierher kopiert
        ...
    elif self.state == QSOState.WAIT_RR73 and self.qso.timeout_cycles == 1:
        # Retry-Logik aus on_cycle_end:Z.330-346 hierher kopiert
        ...
```

Die `on_cycle_end` ihrerseits laesst den Counter-Inkrement
(`timeout_cycles += 1`) drin, aber den Retry-Trigger-Block raus.

### 2.3 Sequenz nach Fix D

```
T_n+0       Slot N+1 startet (RX-Slot der Gegenstation)
            └─ _on_cycle_start (Timer):
               ├─ qso_sm.on_cycle_end():
               │  └─ state==WAIT_REPORT → timeout_cycles += 1 (= 1)
               │  └─ KEIN Retry-Trigger mehr hier
               └─ _omni_tx.advance / Diversity-Antennen-Wechsel

T_n+13.5    Decoder wacht auf
T_n+13.7    decoder.cycle_decoded.emit(messages)

T_n+13.75   _on_cycle_decoded (Decoder-Pfad):
            ├─ _handle_normal_mode / _handle_diversity_operate:
            │   └─ on_message_received(R+18) → state WAIT_REPORT → TX_REPORT
            │   └─ encoder.transmit("...RR73")
            ├─ qso_sm.on_decoder_finished():           ← NEU
            │   └─ state ist TX_REPORT → KEIN Retry-Trigger ✓
            ├─ _refresh_diversity_freq_view
            ├─ _run_ap_lite_rescue
            └─ _run_auto_hunt

T_n+15      Slot N+2 startet (Mike-TX-Slot)
            └─ Encoder schickt RR73 (kein Doppel-Report) ✓
```

Wenn KEIN R+18 ankommt:
```
T_n+13.75   on_decoder_finished():
            └─ state ist WAIT_REPORT, timeout_cycles == 1 → Retry-Trigger
            └─ encoder.transmit("DA1TST DA1MHH -21")  → 1.3s Vorlauf zu Slot N+2
```

Wenn Decoder-Hang in Slot N+1:
```
T_n+0       on_cycle_end → timeout_cycles=1
T_n+15      Slot N+2 startet
            └─ on_cycle_end → timeout_cycles=2
            └─ KEIN Retry-Trigger weil on_decoder_finished nicht lief
            (akzeptabel — bei Decoder-Hang ist QSO sowieso kompromittiert)

CQ_WAIT bei Decoder-Hang:
T_n+0       Slot N+1 → on_cycle_end → CQ_WAIT-Trigger feuert ✓
            (Decoder-unabhaengig, weil im Timer-Pfad)
```

---

## 3. Akzeptanzkriterien

### A — Funktional (FT8)

A1. **Doppel-Report-Bug behoben:** Wenn DA1TST in Slot N+1 mit R-Report
    antwortet, sendet Mike in Slot N+2 RR73. Verifikation: Real-QSO
    mit 2. Station auf Icom-Empfaenger.

A2. **Retry-Pfad bleibt funktional:** Wenn DA1TST in Slot N+1 NICHT
    antwortet, sendet Mike in Slot N+2 (oder N+4 via Drift-Guard) den
    Retry mit DT 0.0-0.1s am Empfaenger.

A3. **CQ_WAIT bleibt funktional auch bei Decoder-Hang:** CQ-Re-call
    feuert weiterhin im Timer-Pfad.

A4. **3-Min-Gesamttimeout bleibt funktional auch bei Decoder-Hang.**

A5. **WAIT_73-Tick bleibt funktional auch bei Decoder-Hang.**

### B — Side-Effect-frei

B1. `_omni_tx.advance` (mw_cycle.py:508): unveraendert (liest qso_state
    nach on_cycle_end im Slot-Start — wie heute).

B2. Diversity-Antennen-Wechsel (mw_cycle.py:510+): unveraendert.

B3. `_run_ap_lite_rescue` / `_run_auto_hunt`: unveraendert. Sie laufen
    weiterhin am Slot-Ende NACH Decoder, NACH on_decoder_finished.

### C — Robustheit

C1. **Decoder-Hang akzeptiert** fuer Retry-Pfad (auf 1-2 Slots
    Verzoegerung). CQ_WAIT, Gesamttimeout, WAIT_73 weiterhin
    funktional via Timer-Pfad.

C2. **Pause-Modus** friert nur den Retry-Pfad ein (im Decoder-Pfad).
    Timer-Pfad-Funktionen laufen weiterhin (CQ_WAIT, Gesamttimeout) —
    KONSISTENT mit aktuellem Verhalten.

C3. **Tests:**
    - Bestehende 502 Tests gruen (insb. die v0.80-Tests
      `test_wait_report_retry_at_cycle_one`,
      `test_wait_rr73_retry_at_cycle_one`,
      `test_state_change_during_encoder_sleep_aborts_pending_tx`,
      `test_set_state_resets_counter_for_wait_states`).
    - 2 neue Tests:
      a) `test_on_decoder_finished_triggers_retry_when_no_reply`
      b) `test_on_decoder_finished_skips_retry_when_state_already_advanced`

---

## 4. Code-Diff-Skizze

### 4.1 `core/qso_state.py:on_cycle_end` — Retry-Block entfernen

```python
def on_cycle_end(self):
    # Gesamt-QSO Timeout (3 Min) — UNCHANGED
    if (self.state not in (...) and ...):
        ...
        return

    # WAIT_73 Tick — UNCHANGED
    if self.state == QSOState.WAIT_73:
        ...
        return

    # CQ_WAIT Tick — UNCHANGED
    if self.state == QSOState.CQ_WAIT:
        ...
        return

    if self.state in (QSOState.WAIT_REPORT, QSOState.WAIT_RR73):
        self.qso.timeout_cycles += 1
        self._dbg.log("WAIT", f"...")

        # +++ ENTFERNT: Retry-Trigger-Block (Z.314-346) wandert nach
        # +++ on_decoder_finished()

        # Max-Timeout-Check BLEIBT
        if self.qso.timeout_cycles >= self.qso.max_timeout:
            ...
```

### 4.2 `core/qso_state.py:on_decoder_finished` — NEUE Methode

```python
def on_decoder_finished(self):
    """Aufgerufen am Slot-Ende NACH Decoder-Verarbeitung.

    Triggert Retry fuer WAIT_REPORT/WAIT_RR73, wenn die Gegenstation
    in diesem RX-Slot NICHT geantwortet hat. Wenn sie geantwortet
    hat, hat on_message_received bereits den State gewechselt →
    kein Retry-Trigger.

    Hintergrund: Vor Fix D lief der Retry-Trigger in on_cycle_end()
    am Slot-START — also BEVOR der Decoder die Antwort sehen konnte
    (Doppel-Report-Bug).
    """
    if self.state == QSOState.WAIT_REPORT and self.qso.timeout_cycles == 1:
        station_limit = min(self.qso.max_calls, MAX_STATION_CALLS)
        if self.qso.calls_made < station_limit:
            self.qso.calls_made += 1
            retry_msg = f"{self.qso.their_call} {self.my_call} {self.qso.our_snr or '-10'}"
            self._dbg.log("RETRY", f"WAIT_REPORT Retry {self.qso.calls_made}/{station_limit}: '{retry_msg}'")
            self._set_state(QSOState.TX_CALL)
            self.send_message.emit(retry_msg)
        else:
            call = self.qso.their_call
            self._dbg.log("TIMEOUT", f"Max Versuche ({station_limit}) erreicht")
            self._set_state(QSOState.TIMEOUT)
            self.qso_timeout.emit(call)
            self._resume_cq_if_needed()
    elif self.state == QSOState.WAIT_RR73 and self.qso.timeout_cycles == 1:
        self.qso.rr73_retries += 1
        if self.qso.rr73_retries <= MAX_RR73_RETRIES:
            report = self.qso.our_snr or f"R{self._last_snr:+03d}"
            retry_msg = f"{self.qso.their_call} {self.my_call} {report}"
            self._dbg.log("RETRY", f"WAIT_RR73 Retry {self.qso.rr73_retries}/{MAX_RR73_RETRIES}: '{retry_msg}'")
            self.qso.timeout_cycles = 0
            self._set_state(QSOState.TX_REPORT)
            self.send_message.emit(retry_msg)
        else:
            call = self.qso.their_call
            self._dbg.log("TIMEOUT", f"WAIT_RR73 max Retries ({self.qso.max_calls}) erreicht")
            self._set_state(QSOState.TIMEOUT)
            self.qso_timeout.emit(call)
            self._resume_cq_if_needed()
```

### 4.3 `ui/mw_cycle.py:_on_cycle_decoded` — neuen Aufruf einfuegen

```python
@Slot(list)
def _on_cycle_decoded(self, messages: list):
    if not self.rx_panel._rx_active:
        return

    self._assign_slot_parity(messages)
    self.control_panel.update_decode_count(len(messages) if messages else 0)
    self._update_dt_correction(messages)

    ant, was_phase = "A1", "operate"
    if self._rx_mode == "diversity":
        ant, was_phase = self._pop_diversity_queue()

    if self._rx_mode == "diversity" and was_phase == "measure":
        self._handle_diversity_measure(messages, ant)

    if self._rx_mode == "diversity" and messages:
        self._handle_diversity_operate(messages, ant)
    elif self._rx_mode == "normal":
        self._handle_normal_mode(messages)
    elif messages:
        self._handle_dx_tune_mode(messages)

    # +++ NEU (Fix D): Retry-Trigger NACH Message-Verarbeitung
    self.qso_sm.on_decoder_finished()
    # +++ Ende NEU

    if self._rx_mode == "diversity" and was_phase == "operate":
        self._refresh_diversity_freq_view()

    if self._dx_tune_dialog is not None:
        self._dx_tune_dialog.feed_cycle(messages)

    self._run_ap_lite_rescue(messages)
    self._run_auto_hunt(messages)
```

### 4.4 `ui/mw_cycle.py:_on_cycle_start` — UNVERAENDERT

`qso_sm.on_cycle_end()` bleibt in Z.501. Counter-Inkrement und
CQ_WAIT/Gesamttimeout-Trigger laufen weiter am Slot-Start.

### 4.5 Tests — `tests/test_modules.py`

```python
def test_on_decoder_finished_triggers_retry_when_no_reply():
    """Fix D: bei state==WAIT_REPORT und timeout_cycles==1, ohne
    on_message_received aufzurufen, soll on_decoder_finished den
    Retry triggern."""
    qso_sm = QSOStateMachine(my_call="DA1MHH")
    # QSO in WAIT_REPORT mit timeout_cycles=1 setzen
    qso_sm.start_qso(...)
    qso_sm._set_state(QSOState.WAIT_REPORT)
    qso_sm.qso.timeout_cycles = 1
    qso_sm.qso.calls_made = 0

    sent = []
    qso_sm.send_message.connect(lambda m: sent.append(m))

    qso_sm.on_decoder_finished()

    assert qso_sm.state == QSOState.TX_CALL
    assert qso_sm.qso.calls_made == 1
    assert len(sent) == 1


def test_on_decoder_finished_skips_retry_when_state_advanced():
    """Fix D: wenn on_message_received state bereits zu TX_REPORT
    geaendert hat, darf on_decoder_finished KEINEN Retry triggern."""
    qso_sm = QSOStateMachine(my_call="DA1MHH")
    qso_sm.start_qso(...)
    qso_sm._set_state(QSOState.TX_REPORT)  # State schon weiter
    qso_sm.qso.timeout_cycles = 1

    sent = []
    qso_sm.send_message.connect(lambda m: sent.append(m))

    qso_sm.on_decoder_finished()

    assert qso_sm.state == QSOState.TX_REPORT  # unveraendert
    assert len(sent) == 0  # kein Retry
```

Beide Tests sind **pure Unit-Tests** auf qso_state — kein
MainWindow-Setup, keine Qt-offscreen-Konfig. Schnell und stabil.

---

## 5. Out-of-Scope

- FT4/FT2-Drift-Guard-Schwelle anpassen (R1-P2 akzeptiert).
- Race-Condition cross-sender mitigation (R1-P3 akzeptiert).
- Refactor on_cycle_end → on_slot_start_tick (kosmetisch, kann
  spaeter).
- Versionsbump v0.80 → v0.81 (Bugfix-only).

---

## 6. Aufwandsschaetzung

| Schritt | h |
|---|---|
| Code-Aenderung (qso_state.py + mw_cycle.py, ~30 Zeilen) | 0.7 |
| 2 Unit-Tests | 1.0 |
| Real-QSO-Test mit 2. Station auf Icom | 0.5 |
| HISTORY.md + commit | 0.3 |
| Final-R1-Codereview | 0.5 |
| **Gesamt** | **~3 h** |

---

## 7. Migration / Backwards-compat

- `qso_state.py`: NEUE Methode `on_decoder_finished()` (additiv).
  `on_cycle_end()` Logik geaendert (Retry-Block entfernt) — interne
  API bleibt gleich.
- `mw_cycle.py`: zwei Aenderungen, ~3 Zeilen Diff.
- Keine Settings-Datei-Aenderung.
- Bestehende v0.80-Tests muessen gruen bleiben (`timeout_cycles == 1`-
  Tests testen nun `on_decoder_finished` statt `on_cycle_end` — Tests
  muessen entsprechend angepasst werden, BLEIBEN aber im 1-Cycle-
  Schema von v0.80).

---

## 8. V2 → V3 Diff (R1-Findings eingearbeitet)

| Finding | V2-Annahme | V3-Loesung |
|---|---|---|
| R1-P6 CQ_WAIT-Regression | "on_cycle_end komplett ans Slot-Ende" | Aufspaltung: NUR Retry-Pfad ans Slot-Ende |
| R1-P1 Decoder-Hang | "akzeptabel" | Decoder-unabhaengige Funktionen bleiben am Slot-START |
| R1-P2 FT4/FT2 Drift-Guard | offen | akzeptiert, dokumentiert |
| R1-P3 cross-sender Race | offen | akzeptiert, dokumentiert |
| R1-P4 auto_hunt-Reihenfolge | offen | unveraendert (keine Aenderung an auto_hunt-Pfad) |
| R1-P5 Test-Strategie | grob skizziert | konkrete pure-Unit-Tests in 4.5 |

---

**Mike: V3 freigegeben?** Bei OK → Plan-Mode → atomare Commits.
