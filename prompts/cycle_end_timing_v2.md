# Fix D — `on_cycle_end()` Slot-Timing-Korrektur (Doppel-Report-Bug) — V2

**Status:** V2 (nach Self-Review von V1, vor R1-Review).
**Datum:** 2026-04-30.
**Vorgaenger:** v0.80 (commit `c190df7`) — TX-DT-Drift-Fix.

---

## 0. Kontext und Vorgeschichte

v0.80 hat den **TX-DT-Drift im QSO-Retry-Fall** behoben (Fix A1+A2+A3+
B+C+Race-Fix). Vorher feuerte der Retry-Trigger AM Mike-TX-Slot-Start
(0s Vorlauf → DT 0.6-0.8s am Empfaenger → ueber WSJT-X-Decode-Schwelle
0.5s → 7 Real-QSOs gescheitert).

Fix A1 (commit `9101573`): Retry-Trigger feuert jetzt im **RX-Slot der
Gegenstation** (`timeout_cycles == 1` statt `== 2`) → Encoder hat
14s Vorlauf → DT konvergiert auf 0.0-0.1s ✓ (Icom-verifiziert 30.04.).

**ABER:** mit Fix A1 wurde ein **zweiter, latenter Bug** sichtbar:
`qso_sm.on_cycle_end()` laeuft in `mw_cycle.py:501` innerhalb von
`_on_cycle_start` (= **Slot-START**, Timer-getriggert). Das heisst:
**zum Zeitpunkt des Retry-Triggers ist der RX-Slot noch nicht
dekodiert** — Decoder gibt erst bei T+13.5s im Slot Bescheid.

**Folge:** Mike triggert Retry BEVOR die Antwort der Gegenstation
gesehen wurde. Die spaeter eintreffende Antwort (R+18) loest zwar einen
neuen `transmit("...RR73")` mit `encoder.abort()` aus — aber der
falsche Retry sitzt schon im Encoder-Sleep mit ~14s Vorlauf, abort
kommt zu spaet bzw. der RR73-TX kollidiert mit dem Slot-Pacing.

**Symptom im Icom-Empfangs-Log (30.04. ~08:32-33):**

```
08:32:45 [O] Mike → "DA1TST DA1MHH -21"        (initial-call, korrekt)
08:33:00 [E] DA1TST → R+18                      (decoded ~T+29.5s)
08:33:15 [O] Mike → "DA1TST DA1MHH -21"        (DOPPEL-Report — BUG!)
08:33:30 [E] DA1TST → R+18                      (Wiederholung)
08:33:45 [O] Mike → "DA1TST DA1MHH RR73"       (endlich korrekt)
```

Mike haette nach Slot 33:00 mit RR73 antworten muessen, schickte aber
nochmal -21. Korrektes QSO-Pacing: 4 Slots, hier waren es 6 Slots.

---

## 1. Root-Cause-Analyse

### 1.1 Aktuelle Reihenfolge im FT8-Slot

```
T_n+0       Slot N+1 startet
            └─ ui/mw_cycle.py:_on_cycle_start (Timer-Thread, gequeued zu GUI):
               ├─ Z.494: update_tx_peak(0.0)
               ├─ Z.498-499: _auto_adjust_tx_level
               ├─ Z.501: qso_sm.on_cycle_end()   ← BUG: Retry-Trigger feuert hier
               │         └─ qso_state.py:314 timeout_cycles==1 → send_message.emit(retry-msg)
               │         └─ encoder.transmit(retry-msg) → schlaeft 14s
               ├─ Z.508: _omni_tx.advance(qso_active=...)
               └─ Z.510+: Diversity-Antennen-Wechsel (Hardware)

T_n+13.5    decoder.py:_decode_loop wacht auf (FT8: _SLOT - 1.5)
T_n+13.7    decoder.cycle_decoded.emit(messages)
T_n+13.75   ui/mw_cycle.py:_on_cycle_decoded (gequeued zu GUI):
            ├─ Z.44: _assign_slot_parity
            ├─ Z.46: _update_dt_correction
            ├─ Z.55-60: _handle_diversity_operate / _handle_normal_mode / _handle_dx_tune_mode
            │   └─ on_message_received(R+18) → state WAIT_REPORT → TX_REPORT
            │   └─ send_message.emit("...RR73")
            │   └─ encoder.abort() + encoder.transmit("...RR73")  ← zu spaet
            ├─ Z.65-66: _refresh_diversity_freq_view
            ├─ Z.71: _run_ap_lite_rescue
            └─ Z.72: _run_auto_hunt

T_n+15      Slot N+2 startet (= Mike-TX-Slot)
            └─ Encoder schickt Retry "DA1TST DA1MHH -21" (Doppel!)
```

### 1.2 Saubere Loesung

`qso_sm.on_cycle_end()` aus `_on_cycle_start` entfernen und in
`_on_cycle_decoded` einfuegen — **konkret zwischen den
Message-Handlern und den State-lesenden Aufrufen** (`auto_hunt`,
`ap_lite_rescue`):

```
_on_cycle_decoded:
  1. _assign_slot_parity / _update_dt_correction
  2. _handle_normal_mode / _handle_diversity_operate (→ on_message_received → state-Transition)
  3. qso_sm.on_cycle_end()              ← NEU: hier
  4. _refresh_diversity_freq_view
  5. _run_ap_lite_rescue
  6. _run_auto_hunt
```

**Begruendung der Position (3) zwischen (2) und (4-6):**
- Nach (2): State ist durch Decoder-Messages aktualisiert (R+18 →
  WAIT_REPORT → TX_REPORT). on_cycle_end sieht den korrekten State und
  triggert KEIN Doppel-Retry.
- Vor (4-6): `_refresh_diversity_freq_view` und `auto_hunt` lesen
  `qso_sm.state` — sie sollen den voll-aktualisierten State NACH dem
  Counter-Tick sehen (analog zum heutigen Verhalten, wo on_cycle_end
  vor _on_cycle_decoded laufen wuerde).

---

## 2. Akzeptanzkriterien

### A — Funktional (FT8)

A1. **Doppel-Report-Bug behoben:** Wenn DA1TST in Slot N+1 mit R-Report
    antwortet, sendet Mike in Slot N+2 RR73 (nicht nochmal -21).
    Verifikation: Real-QSO mit 2. Station auf Icom-Empfaenger,
    4-Slot-QSO-Pacing dokumentiert.

A2. **Retry-Pfad bleibt funktional:** Wenn DA1TST in Slot N+1 NICHT
    antwortet, sendet Mike in Slot N+2 (oder N+4 via Drift-Guard) den
    Retry "DA1TST DA1MHH -21" mit DT 0.0-0.1s am Empfaenger.

A3. **CQ-Pfad bleibt funktional:** `CQ_WAIT` triggert weiterhin neuen
    CQ nach 1 RX-Slot ohne Reply.

A4. **3-Min-Gesamttimeout verschoben um max 1 Slot:** feuert nun am
    Slot-ENDE statt am naechsten Slot-START. Macht ~13.5s spaeteren
    Trigger-Zeitpunkt — akzeptabel (Mike's Use-Case ist Hobby-Funk,
    keine 1-Sekunden-Praezision-Anforderung).

### B — Side-Effect-frei

B1. **`_omni_tx.advance(qso_active=...)`** bleibt in `_on_cycle_start`
    (Z.508). Liest `qso_sm.state` weiterhin am Slot-Start —
    semantisch konsistent: `advance` schaut "wie sieht's am Anfang
    des neuen Slots aus" (= nach allen Updates des vorigen Slots).

B2. **Diversity-Antennen-Wechsel** bleibt in `_on_cycle_start` (Z.510+).
    Hardware-Trigger gehoert zum Slot-START.

B3. **TX-Anzeige-Reset** und **Auto-TX-Level-Regelung** bleiben in
    `_on_cycle_start` (Z.494-499). Sie sind UI-State-Reset, nicht
    QSO-Logik.

B4. **`_run_ap_lite_rescue` / `_run_auto_hunt`** lesen State NACH
    `on_cycle_end`. Heutiges Verhalten:
    `auto_hunt` sieht `state` direkt nach Counter-Tick + Message-
    Verarbeitung. Mit Fix D semantisch identisch (jetzt im selben
    Slot-Decoder-Pfad statt Slot-Start-Cluster).

### C — Robustheit

C1. **Decoder-Hang akzeptiert:** Wenn `cycle_decoded` einen Slot lang
    nicht emittet wird (busy / exception / leerer Audio-Buffer), laeuft
    on_cycle_end fuer diesen Slot nicht. State bleibt eingefroren.
    Counter inkrementiert um 1 statt 2 (Slot ueberspringen). Akzeptabel
    — Decoder-Hang ist Ausnahmesituation. **Wichtig:** der gesamte
    QSO-Lifecycle (3-Min-Timeout, Retry-Counter) tickt im Decoder-Pfad
    — wenn Decoder permanent haengt, hilft auch ein Timer-Fallback
    nicht (App ist defekt). Daher kein Notfall-Tick im Timer-Pfad.

C2. **Pause-Modus** (`if not self.rx_panel._rx_active: return` in
    `_on_cycle_decoded` Z.41-42) friert Slot-Fortschritt + on_cycle_end
    ein. **Verhaltens-VERBESSERUNG**: Heute laeuft 3-Min-Timeout
    waehrend Pause weiter (Timer-getriggert) → QSO terminiert obwohl
    Mike pausiert hat. Mit Fix D: Pause friert auch Timeouts ein
    (= sauberer Pause-Semantik).

C3. **Tests:** alle 502 bestehenden Tests gruen. Mindestens 1 neuer
    Test: `test_cycle_end_runs_after_message_processing` —
    verifiziert dass `on_cycle_end` NACH `on_message_received`
    aufgerufen wird (konkret: Mock-Sequenz in einem
    `_on_cycle_decoded([msg])`-Aufruf).

C4. **Existierende v0.80-Tests bleiben gruen:**
    - `test_wait_report_retry_at_cycle_one`
    - `test_wait_rr73_retry_at_cycle_one`
    - `test_state_change_during_encoder_sleep_aborts_pending_tx`
    - `test_set_state_resets_counter_for_wait_states`
    Wenn einer von ihnen scheitert: Fix D bricht den ueberlagerten
    DT-Drift-Fix → STOP, Plan revidieren.

---

## 3. Vorgeschlagene Aenderung (Code-Diff-Skizze)

### 3.1 `ui/mw_cycle.py:_on_cycle_decoded` — Z.60-72 anpassen

```python
@Slot(list)
def _on_cycle_decoded(self, messages: list):
    """Ein kompletter FT8-Zyklus dekodiert."""
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

    # +++ NEU (Fix D): on_cycle_end NACH Message-Handlern, VOR State-lesenden Aufrufen
    self.qso_sm.on_cycle_end()
    # +++ Ende NEU

    if self._rx_mode == "diversity" and was_phase == "operate":
        self._refresh_diversity_freq_view()

    if self._dx_tune_dialog is not None:
        self._dx_tune_dialog.feed_cycle(messages)

    self._run_ap_lite_rescue(messages)
    self._run_auto_hunt(messages)
```

### 3.2 `ui/mw_cycle.py:_on_cycle_start` — Z.501 entfernen

```python
@Slot(int, bool)
def _on_cycle_start(self, cycle_num: int, is_even: bool):
    if not self.encoder.is_transmitting:
        self.control_panel.update_tx_peak(0.0)

    if self._fwdpwr_samples:
        self._auto_adjust_tx_level()

    # --- ENTFERNT (jetzt in _on_cycle_decoded):
    # self.qso_sm.on_cycle_end()

    _in_qso = self.qso_sm.state not in (
        QSOState.IDLE, QSOState.TIMEOUT,
        QSOState.CQ_CALLING, QSOState.CQ_WAIT,
    )
    self._omni_tx.advance(qso_active=_in_qso)

    # ... Diversity-Antennen-Wechsel bleibt unveraendert ...
```

### 3.3 Tests

Konkretes Test-File: `tests/test_modules.py` (502 Tests, Fix D 503).

```python
def test_on_cycle_end_runs_after_message_handler(monkeypatch, qt_app):
    """Fix D: on_cycle_end darf erst NACH on_message_received feuern.

    Verhindert Doppel-Report: Wenn R+18 im RX-Slot dekodiert wird,
    transitioniert qso_state von WAIT_REPORT zu TX_REPORT VOR dem
    Retry-Trigger. on_cycle_end sieht TX_REPORT → kein Retry.
    """
    # Setup: MainWindow + Mock-Decoder, qso_sm in WAIT_REPORT
    # Aufzeichnen der Call-Order via Mock-Wrapper:
    call_order = []
    orig_omr = qso_sm.on_message_received
    orig_oce = qso_sm.on_cycle_end
    qso_sm.on_message_received = lambda m: (call_order.append("omr"), orig_omr(m))[1]
    qso_sm.on_cycle_end = lambda: (call_order.append("oce"), orig_oce())[0]

    fake_msg = make_r_report_msg(...)
    mw_cycle._on_cycle_decoded([fake_msg])

    assert "omr" in call_order
    assert "oce" in call_order
    assert call_order.index("omr") < call_order.index("oce"), \
        "on_cycle_end darf nicht VOR on_message_received laufen"
```

---

## 4. Frage an R1 (Reviewer)

R1, bitte pruefe konkret:

**P1 (KRITISCH — Decoder-Hang):** Wenn `_decode_loop` skippt (busy /
exception / `chunks==[]`), wird `cycle_decoded` NICHT emittet
(decoder.py:191/199/298). Mit Fix D laeuft on_cycle_end dann nicht.
- Heute (v0.80): on_cycle_end laeuft Timer-getriggert → 3-Min-Timeout
  und Retry-Counter ticken weiter, auch bei Decoder-Hang.
- Mit Fix D: alles eingefroren bis Decoder wieder healthy.

Frage: ist das tragbar? Mike's Position: Decoder-Hang = Ausnahme,
QSO-Hang ist akzeptabel. Sieht R1 das anders?

**P2 (Encoder-Vorlauf bei FT4/FT2):** Decoder-Wake-Time ist
`_SLOT - _WAKE_OFFSETS` (decoder.py:180):
- FT8: 15 - 1.5 = 13.5 → Vorlauf nach Fix: ~1.3s (Drift-Guard schickt zu N+4 mit 16s Vorlauf wenn Slot-Rand-Risiko)
- FT4: 7.5 - 0.5 = 7.0 → Vorlauf: ~0.5s → Drift-Guard wahrscheinlich aktiv → Retry +2 Slots
- FT2: 3.8 - 0.3 = 3.5 → Vorlauf: ~0.3s → Drift-Guard fast sicher aktiv → Retry +2 Slots

Frage: ist das ein echtes Problem oder nur kosmetisch (Retry kommt
1 Slot spaeter)? Mike's Bug ist FT8-spezifisch beobachtet, FT4/FT2
sind weniger genutzt. Fix darf sie aber nicht brechen.

**P3 (Race-Condition zwischen `cycle_start` und `cycle_decoded`):** Beide
sind Qt-Signal-emit aus DIFFERENT Senders (Timer-Thread vs
Decoder-Thread). Qt-Queued-Connection garantiert FIFO PRO Sender, NICHT
ueber Sender hinweg. Kann `_on_cycle_start(N+2)` VOR
`_on_cycle_decoded(N+1)` zur Ausfuehrung kommen, wenn `_on_cycle_decoded`
sehr spaet im Slot dispatched wird (z.B. T_n+14.95s)?
- Falls JA: `_omni_tx.advance` (Z.508) liest Stale-State (vor
  on_cycle_end-Tick).
- Mitigation falls noetig: in `_on_cycle_start` ein Flag setzen
  `_pending_cycle_end = (cycle_num)`, in `_on_cycle_decoded` checken
  und nachholen falls noetig?

R1, ist das paranoid (~50ms Race-Window pro Slot, in ms-Bereich)
oder ein echtes Risiko?

**P4 (Reihenfolge-Konsistenz mit ap_lite/auto_hunt):** Die neue
Position von `on_cycle_end` ist ZWISCHEN `_handle_normal_mode` und
`_run_ap_lite_rescue/_run_auto_hunt`. Sind die letzten beiden
state-sensitiv? Konkret:
- `auto_hunt._select_next` liest `qso_sm.state` (nur active wenn IDLE/TIMEOUT)
- `_run_ap_lite_rescue` liest `priority_call` und `qso_sm.qso` (kein State-Switch)

R1, ist das sicher oder muss `auto_hunt` _vor_ on_cycle_end laufen
(weil auto_hunt das Hunten startet wenn Timeout passiert ist —
on_cycle_end koennte gerade TIMEOUT setzen)?

**P5 (Testbarkeit):** Wie kompakt kann der Test sein, ohne `MainWindow`
+ `Decoder` + `Settings` + `Radio` zu instanziieren? Idealerweise:
ein direkter Test der `_on_cycle_decoded`-Methode mit gemocktem
`qso_sm`. R1, hast du einen Mock-Pattern-Vorschlag fuer die bestehende
`tests/test_modules.py` (Qt-Smoke-Setup mit `QT_QPA_PLATFORM=offscreen`)?

---

## 5. Out-of-Scope

- FT4/FT2-Decoder-Wake-Time-Tuning (separat falls noetig).
- Notfall-Tick im Timer falls Decoder dauerhaft haengt — derzeit
  akzeptiert.
- Refactor von `_on_cycle_start` / `_on_cycle_decoded` zu einem
  konsolidierten `_on_slot_processed`-Slot — erst wenn Bedarf da ist.
- Versionsbump v0.80 → v0.81 (Bugfix, kein Feature) als Teil von
  Schritt 5b in WORKFLOW.

---

## 6. Aufwandsschaetzung

| Schritt | h |
|---|---|
| Code-Aenderung (2 Files, ~5 Zeilen) | 0.5 |
| Test schreiben | 1.0 |
| Real-QSO-Test mit 2. Station auf Icom | 0.5 |
| HISTORY.md + commit | 0.5 |
| Final-R1-Codereview | 0.5 |
| **Gesamt** | **~3 h** |

---

## 7. Migration / Backwards-compat

- `qso_state.py` API unveraendert.
- `mw_cycle.py` interne Aenderung — keine externe API.
- Keine Settings-File-Aenderung.
- Bestehende Test-Suite muss gruen bleiben (502 Tests → 503 mit
  neuem Order-Test).

---

## 8. V1 → V2 Self-Review-Diff

Aenderungen gegenueber V1:

1. **Position der on_cycle_end-Einfuegung praezisiert:** nicht "ans
   Ende" sondern explizit ZWISCHEN `_handle_normal_mode` und
   `_refresh_diversity_freq_view` (Sektion 1.2 + 3.1).
2. **Pause-Edge-Case** (V1 P5): jetzt als Verhaltens-VERBESSERUNG
   ausgewiesen (Sektion C2), nicht "akzeptabel".
3. **3-Min-Gesamttimeout-Latenz** (V1 A4): explizit erlaeutert
   (~13.5s Verschiebung, Hobby-Funk-Kontext akzeptabel).
4. **R1-Frage P4** neu: `auto_hunt`-Reihenfolge-Konsistenz.
5. **Test-Datei** (Sektion 3.3): konkret `tests/test_modules.py`
   statt nur "ein neuer Test".
6. **C4 neu:** Liste der bestehenden v0.80-Tests, die gruen bleiben
   muessen (Regression-Indikator).
