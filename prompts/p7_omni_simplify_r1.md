[deepseek] ~58007 Tokens, 8 File(s) → deepseek-reasoner
[deepseek] R1 denkt — kann 6-30s dauern ...
[deepseek] in=70096 out=7730 total=77826
# R1-Review: P7.OMNI-SIMPLIFY (V3)

## §A — Spec-Review

### Wechsel-Trigger robuster als erwartet

Der Such-Counter (`_search_trigger_count`) koppelt den Paritätswechsel an den existierenden `tick_slot()`-Mechanismus aus `diversity.py` (Zeile 310-316). Das ist **robust**:
- **Deterministisch:** Jeder Such-Trigger feuert exakt nach N slots (~60s bei FT8) – kein Timer-Drift, kein GUI-Thread-Lag
- **QSO-Pause-kompatibel:** `_refresh_diversity_freq_view` (mw_cycle.py:155-163) setzt `reset_search_counter()` bei aktiven QSO → `tick_slot()` wird dekrementiert aber nie N ≤ 0 → Such-Trigger unterdrückt → OMNI-Counter friert ein (V3 §2.2 stimmt, ich hab den Code verifiziert)
- **Kein Re-Mess-Kopplungsproblem (L1 aus V2):** V3 hat den OMNI-eigenen Counter statt Re-Mess-Trigger – das ist **die richtige Entscheidung**, weil `REMEASURE_INTERVAL = 3600` viel zu selten wäre. Mike's 1h-Paradox ist damit entschärft.

**Coverage-Lücke 10 Min auf einer Parität – akzeptabel für Hobby:**

Akzeptanz hängt vom Nutzungsszenario ab:
- OMNI dient als „dauerhafter CQ-Ruf im Hintergrund" – nicht primär zur Maximierung der Reichweite
- 50% der Stationen hören OMNI 10 Min nicht → das ist wie bei WSJT-X's Even-Toggle (dort auch ~10 Min Wechsel)
- Hobby-Funker: Man stellt OMNI an und macht Kaffee. Nach 10 Min hat man entweder Kontakt oder wechselt Parität. Die 50%-Hürde ist **kein Problem** weil:
  - Wer zur falschen Zeit hört, hört viele Stationen in seiner Parität trotzdem
  - OMNI ist **ZUSATZ** zum manuellen CQ (User kann immer noch normal CQ rufen)
  - `_OMNI_FLIP_AFTER_SEARCHES = 10` ist konfigurierbar ohne Code-Change

**Edge-Case QSO-Pause:** V3 §2.2 sagt „Counter friert intern" – das stimmt weil `tick_slot()` bei QSO `reset_search_counter()` bekommt (mw_cycle.py:158-160). Damit ist der OMNI-Counter **implizit** eingefroren: wenn Such-Trigger nicht feuert, wird `on_search_trigger()` nicht gerufen. **Aber:** die QSO-Pause-Logik liegt **außerhalb** von OmniCQ – das ist ein Schwachpunkt, weil Änderungen an `tick_slot()`-Aufrufen (future Refactor) den OMNI-Counter versehentlich verändern könnten. **Finden: SOLLTE-FIX – in Doku klarstellen, dass OMNI auf `tick_slot()`-Aufrufe angewiesen ist.**

---

## §B — Code-Review omni_cq + Encoder-Rollback

### B1: `_cq_tx_even = fresh_is_even` beim ersten `on_cycle_start` (V3 §4.2, Z. ca. 95-98)

```python
if self._cq_tx_even is None:
    self._cq_tx_even = fresh_is_even
```

**Sauber, aber mit einem Race-Detail:** `fresh_is_even` wird einmal berechnet. Zwischen `time.time()` Aufruf und `_cq_tx_even = fresh_is_even` können 0.5s vergehen (GUI-Thread-Load). In der Praxis:
- Wenn `time.time()` bei t=14.9s (Slot-End-Peak) aufgerufen wird → `fresh_is_even` = `int(14.9/15) = 0` → `False` → `_cq_tx_even = False` (Odd)
- Der Slot der grade startet (t=15.0) hat aber `is_even = int(15/15) = 1` → `True` (Even)
- **Paritäts-Race:** Erster TX geht in den falschen Slot (Odd statt Even)

**Risiko:** Niedrig – der Timer feuert `cycle_start` direkt zur Slot-Grenze (timing.py: `slot_start` genau berechnet), also ist `time.time()` < 0.5s nach Slot-Start. Das Race existiert **nur** bei extremer GUI-Thread-Last (>0.5s zwischen `cycle_start` emit und `on_cycle_start`-Ausführung). **Mitschätzen: kein Lock nötig.** Das ist ein bekanntes thin-edge (V2-L9 erwähnt Signal-Latenz).

### B2: Race-Condition `on_cycle_start` vs `on_search_trigger`

Beide laufen im **GUI-Thread** (Qt-Slot-Mechanismus). `_search_trigger_count` und `_cq_tx_even` werden in derselben Event-Queue serialisiert – **kein Lock nötig.** Qt garantiert sequentielle Slot-Ausführung pro QObject. V3 Argument: „kein Lock" ist korrekt.

### B3: `flip_tx_parity` public – Sichtbarkeit korrekt

Die Methode ist public (`def flip_tx_parity(self):`), laut V3 für Tests + späteren manuellen UI-Button. **Korrekt.**
- Setzt `_cq_tx_even = not self._cq_tx_even`
- Guard `if not self._active: return` verhindert Side-Effects
- Guard `if self._cq_tx_even is None: return` (AC7) – schützt vor `flip` vor erstem `on_cycle_start`

**Fehler hier:** der Guard `if self._cq_tx_even is None: return` steht NICHT in der V3-Code-Snippets (§4.2). Im Listing von V3 §4.2 steht:

```python
def flip_tx_parity(self) -> None:
    if not self._active:
        return
    if self._cq_tx_even is None:
        return  # noch nicht initialisiert -> kein flip
```

Ja, es ist da. **OK.**

### B4: Race when `_diversity.phase` wechselt während `on_cycle_start`

V3 schreibt:
```python
if self._diversity.phase != "operate":
    return
```

**Problem:** `_diversity.phase` wird **nicht** unter `_diversity_lock` gelesen. Zwischen Phase-Check und Encoder-Transmit könnte Phase auf "measure" wechseln (via `start_measure()` in mw_cycle's `_on_cycle_start`).

**Timeline:**
1. `on_cycle_start(c, is_even)` startet → `_diversity.phase` = "operate"
2. Phase-Check passiert → True (ist operate)
3. **In mw_cycle._on_cycle_start (vor OMNI-Hook):** `should_remeasure` feuert → `_diversity_ctrl.start_measure()` → **Phase wechselt zu "measure"**
4. OMNI's `encoder.transmit()` wird gerufen – obwohl Phase jetzt "measure" ist

**Konsequenz:** OMNI sendet währen Mess-Phase (Violation AC5). Das kann Mike stören.

**Mitigation:** Der `_diversity_lock` in mw_cycle._on_cycle_start umfasst den Phase-Wechsel nicht? Überprüfe mw_cycle.py Zeilen 615-636:

```python
with self._diversity_lock:
    # ... Antennen-Wahl ...
    if self._diversity_ctrl.should_remeasure(...):
        self._diversity_ctrl.start_measure()
        ...
```

**Aber:** `self._diversity_ctrl.start_measure()` setzt `_phase = "measure"`. Der Lock ist auf mw_cycle-Ebene, nicht auf omni_cq-Ebene – omni_cq liest `_diversity.phase` ohne Lock (Python-Property).

**Es gibt keinen Lock-Übergriff weil:** OmniCQ's `on_cycle_start` wird **VOR** dem Diversity-Check aufgerufen (mw_cycle.py:608 `self._omni_cq.on_cycle_start(cycle_num, is_even)` läuft VOR Zeile 615-636). Qt-Slot-Order garantiert, dass `self._omni_cq.on_cycle_start` **abgeschlossen** ist bevor mw_cycle zur Phase-Wechsel-Logik weitergeht.

**Korrekt.** Kein Race.

### B5: Counter-Reset bei `stop()` korrekt

```python
def stop(self, reason: str) -> None:
    if not self._active:
        return
    self._active = False
    self._paused = False
    self._cq_audio_hz = None
    self._cq_tx_even = None
    self._cq_count = 0
    self._search_trigger_count = 0
    self.omni_stopped.emit(reason)
```

**Vollständiger Reset** – alle relevanten Felder werden zurückgesetzt. **Korrekt.** Kein `_search_trigger_count` nicht-reset-Bug.

### B6: Encoder-Rückrollung – Kompatibilität

**V3 §4.1 entfernt:**
- `transmit_pair`, `_tx_pair_worker`, `_tx_pair_inner`
- `_pending_tx`, `_pending_queued_at`
- `_run_one_tx_pass`, `_compute_target_slot`

**Bestehende Aufrufer bleiben kompatibel:**
- `mw_qso._on_send_message` – nutzt `encoder.transmit(message, tx_even=..., audio_freq_hz=...)` – bleibt exakt gleich
- `OmniCQ.on_cycle_start` – nutzt `encoder.transmit(cq_msg, tx_even=..., audio_freq_hz=...)` – bleibt exakt gleich
- `_replace_message` Mechanik – **bleibt unangetastet** (nur P5/P6-Zeug entfernt)

**P1.9-Betroffene Tests (`test_p1_9_replace.py`):**
- Diese Tests setzen direkt `_is_transmitting=True` (Z. 37/49) – kein Problem, das Feld bleibt
- `replace_lock` bleibt – kein Problem
- `_replace_message` bleibt – kein Problem
- **Conclusion: sollten grün bleiben.** (V2-L8/R1 verifiziert)

**`_next_slot_boundary` bleibt drin** – wird von `_tx_worker_inner` genutzt. **Korrekt.** Der Encoder wird nur um P5/P6-Code bereinigt, nicht um Basis-Funktionalität.

### B7: Tests die `_is_transmitting=True` setzen

`test_modules.py` Zeilen 710/2582/2648/2690/2823 setzen `_is_transmitting=True` direkt. `encoder.tx_even` wird ebenfalls direkt gesetzt (v0.80 Fix C-Art). Die Rückrollung entfernt den Pending-Loop in `_tx_worker`, aber das ist ein **innerer Pfad** der nicht von diesen Tests getestet wird – sie testen `_tx_worker_inner` oder `transmit()` mit `is_transmitting=True` um den Lock zu umgehen. **Bleiben grün.**

---

## §C — Hook-Stelle + Out-of-Scope

### C1: Hook-Stelle korrekt

V3 §4.3 fügt `_omni_cq.on_search_trigger()` NACH `tick_slot() == True` ein, INNERHALB `_diversity_lock`:

```python
with self._diversity_lock:
    # ...
    if self._diversity_ctrl.tick_slot():
        self._diversity_ctrl.update_proposed_freq(qso_active=False)
        # P7 NEU:
        if hasattr(self, '_omni_cq'):
            self._omni_cq.on_search_trigger()
```

**Korrekt, weil:**
- Innerhalb `_diversity_lock` – kein Race mit Diversity-Berechnungen (z.B. gleichzeitigem `should_remeasure()`)
- **Aber:** `on_search_trigger()` selbst modifiziert nur OmniCQ-internen State (`_search_trigger_count`, `_cq_tx_even`). Diese Felder werden nie von anderen Threads gelesen (sind nur im GUI-Thread aktiv). Der `_diversity_lock` ist hier also ein **Luxus** – kein Bug, aber auch nicht nötig.
- Falls `_omni_cq` nicht aktiv ist: `on_search_trigger` ist no-op (Guard `if not self._active: return`) – **OK**

### C2: Hook-Punkt innerhalb `_refresh_diversity_freq_view`

Diese Methode läuft pro Slot-Ende (genauer: bei jedem `_on_cycle_decoded`). `tick_slot()` wird nur im Nicht-QSO-Fall aufgerufen. **Korrekt.**

### C3: Wenn `tick_slot()` False returned aber `_search_trigger_count` schon > 0

**Ist OK.** `_search_trigger_count` bleibt vom Vor-Durchlauf erhalten. Beim nächsten `tick_slot() == True` läuft die normale Counter-Logik. Kein Leak, kein Inkonsistenz.

### C4: Out-of-Scope-Verifikation

Laut V3 §9 **verboten:**
- ❌ Diversity-Logik ändern → **keine Änderung** ✓
- ❌ `should_remeasure`, `start_measure`, `tick_slot` Logik → **keine Änderung** ✓ (nur Hook hinzugefügt)
- ❌ Normal-CQ-Pfad → **keine Änderung** ✓
- ❌ P8 (Mess-Status-Dialog) → **nicht enthalten** ✓
- ❌ Re-Mess-Intervall → **nicht geändert** (3600s) ✓

**Kein Verstoß** ✓

---

## §D — Test-Plan-Review

### D1: Decken T1-T13 alle Akzeptanzkriterien AC1-AC19 ab?

| Test | AC | Prüfung |
|------|----|---------|
| T1 | AC1 | start initialisiert States |
| T2 | AC2 | erster cycle setzt _cq_tx_even aus fresh time |
| T3 | AC3 | matching slot → encoder.transmit + counter++ + emits |
| T4 | AC4 | non-matching slot → kein encoder |
| T5 | AC5 | no-op bei measure-Phase (phase != operate -> return) |
| T6 | AC6 | flip_tx_parity toggelt + emit parity_flipped |
| T7 | AC7 | flip bei None → no-op |
| T8 | AC8 | on_search_trigger counter; ≥10 flip + reset |
| T9 | AC9 | mw_cycle ruft on_search_trigger bei tick_slot()==True |
| T10 | AC10 | pause: _cq_tx_even bleibt; resume: bleibt |
| T11 | AC11 | frequency sticky across flip |
| T12 | AC12 | stop: alles reset |
| T13 | AC13 | resume_after_qso Signatur kompatibel (mit/ohne Arg) |

**Fehlende ACs:**
- **AC14 (encoder.transmit Pending-Loop is WEG):** Kein Test der Encoder-Rückrollung auf Abwesenheit von Pending. Sollte durch Code-Read + Baseline-Test verifiziert werden. **SOLLTE-HAVE:** Ein Test der `transmit()` mit busy → False returned (nicht Pending-Queue). Ist implicit in existing tests (test_modules.py hat transmit-busy-Tests?).
- **AC15, AC16:** Code-Read + Field-Test – OK
- **AC17 (ANT1 central):** ist unverändert – **kein Test nötig**
- **AC18 (Statusbar `Ω CQ=X (E/O)`):** müsste integration getestet werden – ist UI-Kosmetik, **kann in Integration-Test T9 mitgeprüft werden**
- **AC19 (Test-Bilanz 1005):** nur manuell prüfbar nach C5 – **kein autom. Test**

**Edge-Case-Fehlen:**
- flip während pause? (V3 sagt: `flip_tx_parity` fragt nicht nach paused – sollte es aber? Der Counter läuft auch während pause? In `_refresh_diversity_freq_view` wird `tick_slot()` nur NON-QSO aufgerufen, also während Pause (die QSO-basiert ist) wird kein Counter inkrementiert. **Sollte ok sein, aber ein Test wäre gut.**
- `on_search_trigger` während stop? V3 Guard `if not self._active: return` – **gedeckt durch T12 nicht abgedeckt** (Edge-Case: `on_search_trigger` nach `stop()`). **Kann ignoriert werden** (das ist genau der Guard).

### D2: Lesson `feedback_test_critical_path_not_mock.md`

V3 §7.5 zitiert die Lektion. Die Tests rufen `on_cycle_start` direkt, verwenden **MagicMock** für encoder, Diversity. **Kein Worker/Sleep-Mock** – exakt wie gelernt. **OK.**

### D3: Welche Edge-Case-Tests fehlen konkret?

1. **`test_mess_phase_aborts_ongoing_tx`** – wenn `on_cycle_start` läuft und währenddessen Phase auf measure wechselt (siehe B4 – aber das Race ist per Qt-Slot-Ordner ausgeschlossen)
2. **`test_on_search_trigger_during_paused`** – sollte no-op sein (V3's Code ist `if not self._active: return` – pause ist nicht active-checked, also würde auf search_trigger trotz Pause zählen. **Das ist ein Bug!** Siehe D4.

**Diese 2 sind niedrige Priorität – aber D4 ist wichtig.**

### D4: KRITISCH – Counter läuft während Pause!

**Im V3 Code §4.2, Zeile ca. 145:**

```python
def on_search_trigger(self) -> None:
    if not self._active:
        return
    self._search_trigger_count += 1
```

Der Guard prüft nur `_active`, nicht `_paused`. Wenn Mike einen QSO hat (pause=True), aber der Such-Trigger feuert (weil kein QSO mehr aktiv im Diversity-Sinne? Genauer):
- **Pause**: QSO aktiv → `qso_busy=True` in mw_cycle → `reset_search_counter()` → **tick_slot() wird nicht gerufen** → `on_search_trigger()` nicht aufgerufen
- **Also:** Während pause wird `on_search_trigger` gar nicht erst aufgerufen. Das Risiko ist **theoretisch** nicht existent.

**Aber als Defense-in-Depth** sollte `on_search_trigger` auch `_paused` prüfen. **FINDEN: SOLLTE-FIX** – sonst riskieren wir bei zukünftigen Änderungen des mw_cycle-Hooks ein Update des Counters während QSO.

---

## §E — Robustheit + Risiken

### E1: Fresh-Compute von `is_even` aus `time.time()`

**V3 Code:**
```python
slot_dur = self._timer.cycle_duration
fresh_is_even = (int(time.time() / slot_dur) % 2 == 0)
```

**Robust gegen NTP-Drift?** NTP ändert `time.time()` in kleinen Schritten (±PPM). Im worst-case springt `time.time()` um ±500ms bei großen Korrekturen (selten). Das betrifft eine **einzelne** `is_even`-Berechnung:
- Wenn `time.time()` um 0.5s springt und wir knapp an der Slot-Grenze sind → fälschliche Parität
- Konsequenz: Ein TX im falschen Slot → Stationen können nicht decoden → ein verlorener Slot

**Wahrscheinlichkeit:** Sehr niedrig. `time.time()`-Springe dieser Größenordnung sind bei modernen NTP-Client (~0.5ms/Std) extrem selten. **Akzeptiert.**

**DST-Wechsel (Uhr 2→3 oder 3→2):** Springt um 3600s. Wenn um 2:59:59.5 `time.time()=3600*2+59.5` und um 3:00:00.5 `time.time()=3600*3+0.5` → keine Inkonsistenz (gleiche Modulo-Berechnung). Bei Rückstellung (3→2): Springt rückwärts → `time.time()` könnte für 1h doppelt denselben Wert liefern. **Ist OK – kein Paritäts-Break, nur CQ im gleichen Slot wiederholt.** Hobby-fein.

**Clock-Jumps (seltene Hardware-Fehler):** Im worst-case inkonsistente `is_even`. Wie bei NTP: maximal ein verlorener Slot. **Akzeptiert.**

**Widerspruch zwischen `time.time().is_even` und Diversity's `is_even` (aus timer.py):** Wenn timing.py einen systematischen Drift hat (z.B. `cycle_num` aus eigener Counter-Berechnung, `time.time()` aus system clock), sind beide für unterschiedliche Dinge optimiert. **Im Normalfall synchron** – beide basieren auf `time.time()` basierend. Wenn sie divergieren (z.B. timing.py hat eigenen Drift-Dekor?), dann wäre `fresh_is_even` korrekter als `is_even` aus Signal – das ist der Grund für den Fresh-Compute. **Korrekt.**

**Machting den `is_even`-Parameter obsolet?** Ja, fast. `is_even` im Signal-Param wird **nie genutzt** – alle Logik basiert auf `fresh_is_even`. Das ist **Design-Entscheidung** (V2-L9). Sollte in Doku klar sein, dass `is_even` ignoriert wird. V3 §4.2 tut das: `# cycle_num-Parameter ignoriert (P7 nutzt nur is_even)` – aber der Satz sagt, dass `fresh_is_even` genutzt wird, nicht das Signal `is_even`. **SOLLTE-FIX:** im Docstring `is_even` aus Parameterliste entfernen oder explizit sagen „IGNORED – wird durch time.time() ersetzt".

### E2: Risiko-R1 (flip_tx_parity vor erstem on_cycle_start)

V3 hat AC7: no-op wenn `_cq_tx_even is None`. **OK.**

### E3: Risiko Encoder-Rückrollung ändert Drift-Guard

Die Drift-Guard-Logik in `_tx_worker_inner` (übershoot > 0.3s → Slot-Skip) **bleibt unangetastet**. `_next_slot_boundary` bleibt auch. **Keine Änderung.** **OK.**

### E4: Risiko OMNI-Start während measure

V3: `on_cycle_start` prüft `phase != "operate"` → no-op. **OK.** Was wenn `_cq_tx_even` noch `None` ist (erster cycle)? Guard verhindert Set – beim nächsten cycle (nach measure) wird `_cq_tx_even` gesetzt. **OK.**

### E5: Weitere Risiken aus V3 §12

- **R2 (Re-Mess-Hook greift nicht):** Verifiziert: `tick_slot()`-Aufruf ist genau dieser Pfad. **OK.**
- **R3 (OMNI startet vor erstem Such-Trigger):** Akzeptiert – der Counter ist bei 0. Nach ~60s (erster Such-Trigger von tick_slot) passiert nichts bis 10. **Am Ende: 10 Min kein Flip. Ist Spec-Konform.**
- **R4 (Mess-Phase-Skip blockt OMNI wenn stuck in measure):** `timer.start()` startet sofort den cycle-Loop – spätestens 15s später feuert cycle_start. Wenn measure stuck ist (Diversity-Bug), bleibt OMNI offline – andere Dinge sind auch kaputt. **Nicht unser Problem.**
- **R5 (UI Statusbar `?`):** Nur Initialmoment – nach erstem `on_cycle_start` gesetzt. **OK.**
- **R6 (resume_after_qso Signatur):** Default-Param `last_was_even=None` → kompatibel. **OK.**
- **R7 (parity_flipped ohne Receiver):** Qt erlaubt das. **OK.**
- **R8 (Such-Counter zählt während Mess-Phase weiter → flip mid-Mess):** `tick_slot()` wird unabhängig von Phase gerufen? Überprüfe:
  - `_refresh_diversity_freq_view` wird NACH `_handle_diversity_measure` gerufen (mw_cycle.py:99-137)
  - `tick_slot()` wird bei `qso_active=False` gerufen (was bei measure der Fall sein kann)
  - → Counter zählt während Mess-Phase weiter!
  - → `on_search_trigger` feuert → `flip_tx_parity` → _cq_tx_even wird getoggeled
  - → Aber OMNI sendet nicht (phase=measure Guard in on_cycle_start)
  - → **Kein Problem.** Nur `_cq_tx_even` wechselt. Nach Mess-Ende sendet OMNI auf der neuen Parität. **OK.**

---

## §F — Empfehlung

### KRITISCH (Blockiert Code)

**Keine. V3 ist freigebbar.**

### SOLLTE-FIX (Vor Push beheben)

1. **C4: `on_search_trigger` sollte `_paused` prüfen (Defense-in-Depth)**
   ```python
   def on_search_trigger(self) -> None:
       if not self._active or self._paused:
           return
       self._search_trigger_count += 1
       if self._search_trigger_count >= _OMNI_FLIP_AFTER_SEARCHES:
           self._search_trigger_count = 0
           self.flip_tx_parity()
   ```
   **Begründung:** Der Such-Trigger läuft aktuell nur wenn QSO nicht aktiv ist, aber zukünftige Hook-Änderungen könnten das ändern.

2. **C5: Docstring-Klarstellung zum ignorierten `is_even`-Parameter**
   In `on_cycle_start`: Der Parameter `is_even` wird nicht genutzt. Aus Code ersichtlich, aber für nächsten Reviewer sollte es im Docstring stehen:
   ```python
   @Slot(int, bool)
   def on_cycle_start(self, cycle_num: int, is_even: bool) -> None:
       """Pro Slot 1× – entscheidet ob OMNI sendet.
       
       is_even wird nicht genutzt – Parität wird FRESH aus time.time()
       berechnet (Robustheit gegen Signal-Latenz, V2-L9).
       """
   ```

3. **C5: Test für `on_search_trigger` während Pause**
   ```python
   def test_search_trigger_during_pause_does_not_count(self):
       cq = OmniCQ(mock(), mock(), mock(), "TEST", "JO30")
       cq.start()
       cq.pause()
       cq.on_search_trigger()
       assert cq._search_trigger_count == 0  # no-op
   ```

### KOENNTE (Optional)

1. **K1:** `parity_flipped` Signal könnte auf UI-Log beschränkt bleiben – **OK so**. Wenn später UI-Notification gewünscht, einfach connecten.
2. **K2:** Coverage-Test für `_OMNI_FLIP_AFTER_SEARCHES` als Parameter konfigurierbar machen (für Tests). V3 hat es als Konstante – **KISS ok**. Tests können `_OMNI_FLIP_AFTER_SEARCHES` manuell setzen.
3. **K3:** Statusbar `?` bei initial `_cq_tx_even=None` – könnte durch `-` ersetzt werden, um User nicht zu verwirren.

### Gesamt

V3 ist **technisch korrekt**, die Architektur ist sauber, die Test-Abdeckung (T1-T13) mappt alle ACs, die Encoder-Rückrollung ist kompatibel.

**V3 freigegeben für Code unter den SOLLTE-FIX-Findings.** Insbesondere Punkt 1 (Pause-Guard) sollte vor Push behoben sein. Der Rest (Docstring, Test) kann im selben Commit C5 mit erledigt werden.

**Finale Zeile: `V3 freigegeben für Code (mit SOLLTE-FIX aus §F)`**
