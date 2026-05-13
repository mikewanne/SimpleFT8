# P5.OMNI-PATTERN-FIX-3 — V2 (Self-Review)

**Datum:** 2026-05-10
**Bezug:** `prompts/p5_omni_pattern_fix3_v1.md`
**Status:** V2 Self-Review fertig fuer R1 (DeepSeek-Reasoner).

---

## 0. Was V2 anders macht als V1

V1 ist solide aber hat 5 Luecken die V2 schliesst:

| L | Lücke in V1 | V2-Patch |
|---|---|---|
| L1 | Cycle-Start-Latency war nur ungefaehr beschrieben („0.05-0.5s GUI-Tick-Latency") — keine Code-Quelle. | V2 §1.1 mit `core/timing.py:76-90` Code-Beleg. **Tick-Schleife laeuft mit `time.sleep(0.1)` → mind. 0-100ms Tick-Latency PLUS Qt-Signal-Queue-Latency (50-300ms typisch beim GUI-Load).** |
| L2 | Drift-Guard-Trigger-Bedingung wurde nur ungefaehr angegeben. | V2 §1.2 mit konkreter Math: bei `cycle_pos > 0.4s` greift Drift-Guard sicher (overshoot=cycle_pos+0.8 > 0.3 trivial fuer cycle_pos > 0). Praktisch: greift fast IMMER bei OMNI (cycle_start kommt nicht atomar). |
| L3 | `:44 [O] Horche`-Quelle nur als „Hypothese D" formuliert. | V2 §1.3 verifiziert: `encoder.tx_started.emit(message, _tx_even, next_boundary)` (encoder.py:373) → `mw_qso._on_tx_started` (mw_qso.py:112) → `qso_panel.add_tx`. **Bei Drift-Guard-Verschiebung geht next_boundary auf :60 → `_tx_even=True (Even)` → `add_tx` mit `[E]`-Tag und `:60` Slot-Time.** Aber Mike sah `:44 [O]` (Odd) als „Horche" (nicht „Sende"). Das ist ein WIDERSPRUCH zur tx_started-Hypothese — also kommt `:44 [O] Horche` NICHT aus tx_started. Bleibt offen fuer R1. |
| L4 | Pending-Verfall-Logik nur skizziert. | V2 §3 ausgearbeitet mit konkretem Code + Test-Cases T8/T9. |
| L5 | R1-Prompt nicht final formuliert. | V2 §6 enthaelt den vollen R1-Prompt-Text als Vorlage. |

---

## 1. Verfeinerte Wurzel-Analyse Issue B

### 1.1 cycle_start-Latency (Code-Beleg)

`core/timing.py:76-90`:

```python
def _tick_loop(self):
    last_cycle = -1
    while self._running:
        now = self.utc_now()
        sic = now % self.cycle_duration
        cycle_num = int(now / self.cycle_duration)

        if cycle_num != last_cycle:
            last_cycle = cycle_num
            self._cycle_count += 1
            is_even = cycle_num % 2 == 0
            self.cycle_start.emit(self._cycle_count, is_even)

        self.cycle_tick.emit(sic, self.cycle_duration)
        time.sleep(0.1)
```

**Latency-Quellen:**

1. **Tick-Sleep-Granularity:** `time.sleep(0.1)` → bis zu 100ms zwischen
   `now % cycle_duration ≈ 0` und `cycle_num != last_cycle`-Detection.
2. **Qt-Signal-Routing:** Sender `cycle_start` ist im **Tick-Thread**
   (separate threading.Thread, daemon, gestartet in `start()`). Receiver
   `mw_cycle._on_cycle_start` ist im **GUI-Thread**. Qt waehlt
   `Qt.QueuedConnection` automatisch (Cross-Thread-Default) → Signal wird
   in die GUI-Event-Queue gestellt.
3. **GUI-Event-Loop-Latency:** je nach Render-/Paint-Load zur Slot-
   Boundary-Zeit kann Queue-Drain 50-300ms dauern.

**Summe:** typische cycle_start-Aufruf-Zeit beim GUI-Thread = **100-400ms
nach echter Slot-Boundary**. Worst-Case bei voller GUI-Last
(Diversity-Switch, Decoder-Render, RX-Panel-Update) noch mehr.

### 1.2 Drift-Guard-Math (definitiv)

`_tx_worker_inner` Z. 322-344:

```python
now = time.time()
silence_secs = max(0.0, (next_boundary + TARGET_TX_OFFSET) - now)
# = max(0, next_boundary - 0.8 - now)

if silence_secs < 0.1:
    overshoot = now - (next_boundary + TARGET_TX_OFFSET)
    # = now - (next_boundary - 0.8)

    if overshoot > 0.3:
        # → next_boundary += 2*15 (FT8) → silence_secs = ~29s
        ...
```

**Bei Pos-0-TX-E :30 mit cycle_start-Latency ~200ms:**

- `transmit()` Aufruf bei `t = :30.2`
- Worker startet, Encoder ~50-200ms → Z. 322 `now = :30.3`
- `next_boundary` aus `_next_slot_boundary()`:
  - `cycle_pos = 0.3 < 0.5` Threshold → `return cycle_num * 15 = :30`
  - Damit `next_boundary = :30`
- `silence_secs = max(0, :30 - 0.8 - :30.3) = max(0, -1.1) = 0`
- `silence_secs < 0.1` → True → Drift-Guard-Branch
- `overshoot = :30.3 - :29.2 = 1.1s > 0.3s` → **DRIFT-GUARD GREIFT**
- `next_boundary += 2*15 = 30 → :60`
- `silence_secs = max(0, :60 - 0.8 - :30.3) = 28.9s`
- `silence_samples = int(28.9 * 12000) = 346800` Zeros + 12.64s Audio
- `audio_full` ~41.54s
- `radio.send_audio` blockt ~41.5s ab :30.3
- **`_is_transmitting=False` erst bei ~:71.8**
- Pos 1 cycle_start :45 → busy. Pos 2 cycle_start :60 → busy. Pos 3
  cycle_start :75 → frei (RX-Slot). Pos 4 cycle_start :90 → frei (RX).

**ABER:** wenn Drift-Guard greift, sendet Encoder nach :60 — Mike sah aber
**Pos 0 TX-E bei :30** (nicht bei :60). Das ist ein **WIDERSPRUCH**.

### 1.3 Aufloesung des Widerspruchs

Drei Moeglichkeiten:

**(a) cycle_start-Latency war im Field-Test sehr klein (z.B. 50-100ms),
sodass `cycle_pos < 0.3s` und Drift-Guard NICHT greift.** Dann TX bei
echtem :30. Aber dann `_is_transmitting=False` bei ~:42.84 → Pos 1 :45 hat
2.16s Race-Window. **In Praxis 100% busy?** Erklaerung: PTT-Settle +
Audio-Buffer-Drain + Thread-Scheduling-Jitter koennten konsistent 2-5s
weiterlaufen. **Plausibel — V2-Annahme.**

**(b) Drift-Guard-print laeuft, aber Mike sah „Pos 0 TX-E bei :30" durch
einen anderen Pfad** (z.B. cycle-tick-Display). → Field-Logs zeigen aber
NUR `[OMNI-CQ] encoder.transmit busy` 3×, KEIN Drift-Guard-print
(`[TX] Drift-Vermeidung: overshoot=...`). **Das spricht GEGEN aktiven
Drift-Guard.**

**(c) Ein dritter Pfad blockt `_is_transmitting`-Reset.** Z.B.
`_replace_lock` halt, `request_replace`-Pfad, Audio-Buffer-Underrun. **Per
Code-Read unwahrscheinlich** — finally ist garantiert.

**V2-Konsens:** Variante **(a)** ist wahrscheinlichste Wurzel — kein
Drift-Guard, sondern reiner 12.64s Audio + PTT-Settle + Buffer-Drain.
Trotzdem ist Race-Window konsistent > 2s und Pos 1 immer busy.

**Wichtig:** Drift-Guard koennte trotzdem in einigen Slots greifen (es
gibt nur 3 busy-Lines im Log, also genau bei den 3 Pos-1-Versuchen). Wenn
Drift-Guard NIE greift, wird Worker bei :42.84 fertig + finally reset bei
:42.9-:43.0 → Race-Window :43-:45 = 2s Wartezeit. Wenn Hardware-Send-
Latency (FlexRadio Buffer-Drain) den finally bis :44.5 verschiebt → Pos 1
busy.

**FlexRadio TX-Buffer 1.3s ist die wahrscheinliche Quelle der Buffer-
Drain-Latency:** `radio.send_audio` blockt bis alle Audio-Pakete im Buffer
gepacht sind. Bei 1.3s Buffer-Tiefe + 12.64s Audio ist `send_audio` ~12.64s
+ epsilon. PTT off bei `send_audio.return`. Aber HF-Output laeuft noch
1.3s weiter (Buffer-Drain). PTT-Off-Sequenz im Radio kann zusaetzliche
Latenz haben. **`_is_transmitting=False` faellt eventuell tatsaechlich erst
bei :44.x oder :45.x.** Race-Window dann effektiv 0-1s — und in 100% der
Faelle busy.

→ **V2 stellt das als 3 R1-Fragen** (siehe §6).

### 1.4 Hypothese H2 (Pos 4 RX-E + `:44 [O] Horche`) verfeinert

**Pos 4 RX-E fehlt:** `_do_rx_slot(is_even=True)` bei Pos 4 muesste
`add_listening(time.time(), True)` triggern. Mike sah keinen Eintrag.

Moegliche Quellen:

1. **`_paused = True`:** wenn QSO einging zwischen Pos 0 und Pos 4. → Mike
   nutzte test ohne QSO (User-Start, dann manual_halt nach 1.5 Bloecken).
   Logs zeigen kein QSO. → Faellt weg.

2. **`_active = False`:** wenn `stop_omni_cq` zwischendurch lief. Logs:
   `User-Start ... 3× busy ... manual_halt`. Stop kam erst NACH den
   Symptom-Zeilen. → Faellt weg.

3. **Slot-Index-Off-by-one:** wenn `_advance_state` 2× pro on_cycle_start
   gerufen wurde, oder Pattern desynchronisiert. → Code-Read zeigt
   `_advance_state` ist als **letzter Aufruf** in `on_cycle_start` (Z. 183),
   1× pro Slot. → Faellt weg.

4. **Anzeige-Limit/Trimm:** `qso_panel._auto_trim_by_age(300)` (siehe
   p3_omni_pattern_fix2_v2.md L6) trimmt nur Eintraege > 5 Min alt. Bei
   1.5 Bloecken (~75s Daten) → kein Trim. → Faellt weg.

5. **`_advance_state`-Drift wegen busy-Skip:** Logs zeigen 3× busy. Der
   `_advance_state` LAEUFT trotzdem (V5-AC10). Aber das verschiebt NUR
   `_slot_index`, nicht den UTC-Slot. → Pattern bleibt mit UTC synchron.
   Pos 4 sollte trotzdem im naechsten 5-Slot-Block ankommen.

6. **R1-Frage-Kandidat:** Es gibt einen UNBEKANNTEN Pfad der `_paused` oder
   `_active` toggelt. Eventuell `mw_radio._enable_diversity` /
   `_disable_diversity` / Mode-Wechsel? **R1 verifizieren.**

**`:44 [O] Horche`-Quelle:** alle bekannten Pfade die `add_listening`
rufen sind:
- `main_window.py:760` aus `_on_omni_slot_action` (RX-Slot)
- `qso_panel.add_listening`-DIREKT-Aufruf existiert sonst nicht (grep)

Bei busy-Pos-1 wird `_on_omni_slot_action` mit `is_tx=True, target_even=False`
gerufen → if-Branch `if not is_tx:` = False → NICHT add_listening.

**ABER:** wartet — bei busy in `_do_tx_slot` wird `slot_action` GAR NICHT
emittet (nur log). Also kein `_on_omni_slot_action`-Aufruf. **Wer kennt
also `:44 [O] Horche`?**

**Verbleibende Hypothese H-X:** Mike hat das Display-Layout falsch
interpretiert ODER es gibt einen UI-Bug in `qso_panel.add_listening` der
einen Eintrag „verschluckt" und faelschlich an einer falschen Stelle
einfuegt. **R1-Frage-Kandidat.**

→ **V2 markiert das als „R1-zu-klaeren" und V3 muss bei AC-B7 explizit
einen Test fuer „Pos 4 RX-E ist im Display" haben.**

---

## 2. Loesungsoptionen verfeinert

### 2.1 Variante A — Encoder-Queue (PRIMARY)

V1 §4 Option A war zu vage. V2 schaerft:

**Problem-Analyse fuer Pending-Verfall:**

- Pending-Job `(message, tx_even, audio_freq_hz)` wurde bei Pos 1 :45
  gequeueet (ZEITPUNKT: cycle_start :45.0xx).
- Worker wird bei `:71-:74` mit aktuellem TX fertig (siehe §1.2/§1.3).
- Worker checkt Pending → ja → setzt `tx_even=False` (TX-O target).
- `_tx_worker_inner` ruft `_next_slot_boundary()` mit `tx_even=False`.
  - `now = :74.0`, `cycle_num = int(74/15) = 4`, `cycle_pos = 14.0 > 0.5`
  - `is_even = (4 % 2 == 0) = True`, `want_even = False` → mismatch
  - `next_num = 5`, `next_boundary = :75.0` (5 odd)
  - `(next_num % 2 == 0) != want_even` → `False != False` → True → return :75
- Worker schlaeft bis `:75 - 1.3 = :73.7`. Bereits in der Vergangenheit →
  Drift-Guard greift erneut → next_boundary = :75 + 30 = :105 (TX-O 105).
- TX bei :105 statt geplantem :45. **Pattern verschoben.**

→ **Pending-Verfall MUSS implementiert werden:**

```python
# In _tx_worker finally-Branch:
finally:
    self._is_transmitting = False
    self._audio_started = False
    # Pending-Check
    with self._replace_lock:
        pending = self._pending_tx
        self._pending_tx = None
    if pending is None:
        return
    pending_msg, pending_tx_even, pending_audio_hz = pending
    # Pending-Verfall: ist der Ziel-Slot noch erreichbar?
    if pending_tx_even is not None:
        _SLOT = {"FT8": 15.0, "FT4": 7.5, "FT2": 3.8}.get(self._mode, 15.0)
        # Naechster passender Slot per same logic wie _next_slot_boundary
        now = time.time()
        cycle_num = int(now / _SLOT)
        is_even = (cycle_num % 2 == 0)
        if is_even == pending_tx_even and (now % _SLOT) < 0.5:
            # Aktueller Slot passt — quasi-just-in-time
            target_slot = cycle_num * _SLOT
        else:
            # Naechster passender Slot
            next_num = cycle_num + 1
            target_slot = next_num * _SLOT
            if (next_num % 2 == 0) != pending_tx_even:
                target_slot += _SLOT
        # Verfall-Schwelle: target_slot < (urspruenglicher Aufruf-Zeit + 1 Slot)
        # Noch besser: pending hat ein "queued_at"-Timestamp.
        if target_slot - self._pending_queued_at > _SLOT * 1.5:
            # Pending ist > 1.5 Slots alt → verfaellt
            print(f"[Encoder] Pending TX verfallen (target={target_slot}, "
                  f"queued_at={self._pending_queued_at})")
            return
    # Re-trigger Worker mit pending
    self._is_transmitting = True
    self._abort_event.clear()
    with self._replace_lock:
        if pending_tx_even is not None: self.tx_even = pending_tx_even
        if pending_audio_hz is not None: self.audio_freq_hz = pending_audio_hz
    try:
        self._tx_worker_inner(pending_msg)
    finally:
        self._is_transmitting = False
        self._audio_started = False
```

**Trade-off:** Re-trigger-Logik ist ~20-30 Z. zusaetzlich. Tests T8 (success)
+ T9 (verfall) deckt das ab.

**Alternative (einfacher):** Pending-Verfall fest als „> 0.5 * cycle_duration"
nach Pending-Zeitpunkt. Bei FT8: 7.5s. Wenn Worker nicht innerhalb 7.5s
fertig wird, verfaellt Pending. Das vermeidet Drift-Guard im Pending-Pfad.

**Weiteres Problem:** wenn Worker fertig wird bei `:74` und Pending-Slot ist
`:75` (nur 1s in der Zukunft) → reicht das aus? `_tx_worker_inner` braucht
encode_message (~50-200ms) + Sleep bis `:75 - 1.3 = :73.7` (ist negativ →
sofort Drift-Guard). → **Pending sendet effektiv erst bei :75 + 30 = :105
(naechster passender Slot nach Drift-Guard).** Damit ist die ganze Pending-
Logik fragwuerdig: Encoder kommt nicht in 1.3s VOR Slot-Start mit
Pre-Encode an.

**Konsequenz:** Variante A LOEST das Pos-1-busy-Problem nur wenn der
Worker **mindestens 1.3s VOR Pos-1-Slot fertig wird**. Bei reiner 12.64s
Audio-Dauer ist Worker fertig bei `:30 + 12.64 = :42.64` + finally + reset
≈ `:43`. Pos 1 :45 - 1.3 = :43.7. **Bei :43 Pending-Re-Trigger laeuft :43,
schlaeft bis :43.7 ≈ 0.7s, dann TX. → Pos 1 erfolgreich.** Wenn aber
Buffer-Drain bis :44.5 dauert → Worker schlaeft bis :43.7 (negativ) → sofort
Drift-Guard → +30s → Pos 1 verfaellt → Block 2 Pos 0 :105 statt geplantem
:45.

**Fazit Variante A:** Solange `_is_transmitting=False` SPAETESTENS bei
:43.5 faellt (also < 1.5s nach Audio-Ende), funktioniert Pending. Bei
spaeterem Reset → Drift-Guard greift → Pattern bricht.

→ **R1 muss klaeren: Was ist die echte `_is_transmitting=False`-Latenz
bei FlexRadio FT8 12.64s Audio + PTT-Off-Sequenz?**

### 2.2 Variante B — Mid-Cycle-Pretrigger

**Kern:** OMNI ruft `encoder.transmit()` 1.3s vor naechstem Slot
(also bei `cycle_pos > 13.7s` bei FT8). Encoder hat dann genug Zeit fuer
encode_message + Sleep bis `:30 - 1.3 = :28.7`.

**Implementierung:**

```python
# core/omni_cq.py
@Slot(int, bool)
def on_cycle_start(self, cycle_num, is_even):
    # ... bestehender Code (Pattern-Decision fuer aktuellen Slot)

# NEU: separater Pre-Trigger-Hook fuer NAECHSTEN Slot
@Slot(float, float)
def on_cycle_tick(self, seconds_in_cycle, cycle_duration):
    if not self._active or self._paused:
        return
    # Vorbereitung 1.3s vor Slot-Boundary
    if seconds_in_cycle < cycle_duration - 1.3:
        return
    if self._pretriggered_for_slot == self._slot_index:
        return  # schon vorbereitet
    # peek_next: was ist NACH _advance_state?
    next_idx = (self._slot_index + 1) % 5
    next_block = self._block
    if next_idx == 0:
        next_block = 2 if self._block == 1 else 1
    next_is_tx = self._TX_PATTERN[next_idx]
    if not next_is_tx:
        self._pretriggered_for_slot = self._slot_index
        return
    # Pre-encode + start
    if next_block == 1:
        next_target_even = (next_idx == 0)
    else:
        next_target_even = (next_idx == 1)
    if self._cq_audio_hz is None:
        self._init_audio_freq()
    cq_msg = f"CQ {self._my_call} {self._my_grid}"
    ok = self._encoder.transmit(cq_msg, tx_even=next_target_even,
                                  audio_freq_hz=self._cq_audio_hz)
    self._pretriggered_for_slot = self._slot_index
    if ok:
        # Pos-1-TX wird im naechsten on_cycle_start KEIN encoder.transmit mehr
        # rufen — Skip via Flag
        self._tx_already_started_for_slot = next_idx
```

Dann in `on_cycle_start`:

```python
if is_tx and self._tx_already_started_for_slot == self._slot_index:
    # Pretrigger hat bereits gesendet
    self._do_tx_slot_post(target_even)  # nur counter + slot_action emit
    self._tx_already_started_for_slot = None
else:
    self._do_tx_slot(target_even)  # normaler Pfad
```

**Pro:**
- Encoder hat fest 1.3s Vorlauf, nie Drift-Guard.
- Pos 1 wird sicher bedient.

**Kontra:**
- ~50-80 Z. mehr Code in `omni_cq.py`.
- Verstoss gegen V3-§8 („cycle_tick-basierter Pretrigger ❌").
- Race wenn QSO startet mid-pretrigger → Pre-encoded TX laeuft trotz
  pause(). **Mitigation:** vor send-Audio nochmal `_paused`-Check.

**Komplexitaet:** mittel.

### 2.3 Varianten C/D — Spec-Aenderung

V1 hat das schon ausgearbeitet. V2 ergaenzt:

- Variante C ist trivial (1 Zeile Pattern), aber halbiert TX-Rate auf E
  (oder O) je nach Pattern. Mike will beide Paritaeten in einem Block.
- Variante D ist mittel-komplex und braucht neue Pos-zu-Paritaet-Logik.

**Beide brauchen Mike-Spec-Aenderung** → erst nach Mike-Freigabe.

### 2.4 Empfehlung an R1 + Mike

**V2 empfiehlt: Variante A (Encoder-Queue) MIT Pending-Verfall.**

**Falls Variante A nicht zuverlaessig wird** (R1-Diagnose: Buffer-Drain >
1s nach Audio-Ende), **Fallback auf Variante B** (Mid-Cycle-Pretrigger).

**Variante C/D nur wenn A+B beide scheitern oder Mike Spec aendern will.**

---

## 3. Pending-Verfall — finalisierte Code-Skizze (Variante A)

(Siehe §2.1 oben — vollstaendiger Code im V3 Plan.)

**Tests:**

```python
# tests/test_encoder_pending_v0962.py
def test_transmit_returns_true_when_busy_and_queues_pending():
    enc = make_encoder()
    enc._is_transmitting = True
    ok = enc.transmit("TEST", tx_even=False, audio_freq_hz=1500)
    assert ok is True
    assert enc._pending_tx == ("TEST", False, 1500)

def test_pending_consumed_after_finally():
    enc = make_encoder_with_real_worker()
    enc.transmit("TEST1", tx_even=True, audio_freq_hz=1500)
    enc.transmit("TEST2", tx_even=False, audio_freq_hz=1500)  # pending
    # Worker ist nach _tx_worker_inner fertig → finally consumed pending
    enc._tx_thread.join(timeout=2.0)
    assert enc._pending_tx is None

def test_pending_dropped_if_target_slot_in_past_more_than_1_5_slots():
    enc = make_encoder()
    enc._is_transmitting = True
    enc._pending_queued_at = time.time() - 30.0  # 30s alt
    enc.transmit("TEST", tx_even=False, audio_freq_hz=1500)
    # Pending wird bei finally NICHT re-triggert
    enc._is_transmitting = False
    enc._tx_worker.__wrapped__()  # call finally directly
    # Erwartung: log "Pending TX verfallen", _is_transmitting bleibt False
    assert not enc._is_transmitting
```

---

## 4. Issue A — Slot-Boundary-Display (Implementations-Skizze)

`ui/main_window.py:760` aktuell:

```python
if not is_tx:
    self.qso_panel.add_listening(time.time(), target_even)
```

Neu:

```python
if not is_tx:
    slot_dur = self.timer.cycle_duration  # 15.0 / 7.5 / 3.8
    ts = time.time()
    slot_start = (ts // slot_dur) * slot_dur
    self.qso_panel.add_listening(slot_start, target_even)
```

**Edge Cases:**

- `self.timer` immer initialisiert? `main_window.__init__` erstellt
  `self.timer = FT8Timer("FT8")` vor jeder OMNI-Aktivitaet. ✓
- Floating-Point-Praezision bei `(ts // slot_dur) * slot_dur` mit
  `slot_dur=3.8` (FT2)? Test mit Beispiel: `ts=100.5`, `100.5 // 3.8 =
  26.0`, `26.0 * 3.8 = 98.8`. Korrekt.
- Mode-Wechsel mid-OMNI: `self.timer.cycle_duration` wechselt automatisch
  via `set_mode` ✓.

**Tests:**

```python
def test_add_listening_uses_slot_boundary_ft8(monkeypatch):
    mw = make_main_window(mode="FT8")
    monkeypatch.setattr("ui.main_window.time.time", lambda: 16004.5)  # 04:26:44.5
    captured = []
    mw.qso_panel.add_listening = lambda ts, e: captured.append((ts, e))
    mw._on_omni_slot_action("B1 [2/4] RX-E", False, True)
    assert captured == [(15990.0, True)]  # 04:26:30 (16004.5 // 15 * 15)

@pytest.mark.parametrize("mode,slot_dur,now,expected", [
    ("FT8", 15.0, 16004.5, 15990.0),
    ("FT4", 7.5, 16004.5, 16004.0 - (16004.0 % 7.5)),  # = ...
    ("FT2", 3.8, 16004.5, ...),
])
def test_add_listening_slot_boundary_all_modes(mode, slot_dur, now, expected):
    ...
```

---

## 5. Akzeptanzkriterien (V1 §5 unveraendert)

V1 ACs B1-B7, A1-A3, Z1-Z4 bleiben gueltig. V2 ergaenzt nur:

- **AC-Z5:** Pending-Verfall-Logik darf KEIN Re-Trigger machen wenn
  `_active = False` (OMNI gestoppt zwischen Pos 1 und Worker-Finally).
  Test T10.
- **AC-Z6:** Encoder-Pending darf NICHT von Normal-CQ-Pfad genutzt werden
  (mw_qso `_on_send_message`). Pending-Pfad ist OMNI-only / `tx_even`-
  abhaengig. Test T11.

---

## 6. R1-Prompt (final)

**An R1 (DeepSeek-Reasoner) zu schicken via `tools/deepseek_review.py`:**

```bash
cat prompts/p5_omni_pattern_fix3_v2.md | \
  ./venv/bin/python3 tools/deepseek_review.py \
    core/encoder.py core/omni_cq.py core/timing.py \
    ui/main_window.py ui/mw_cycle.py ui/mw_qso.py ui/qso_panel.py \
    prompts/p4_omni_neubau_v5_signal_v3.md
```

**R1-Brief (im Prompt selbst):**

```markdown
# Auftrag an DeepSeek-Reasoner (R1)

Du bist Code-Reviewer fuer P5.OMNI-PATTERN-FIX-3 in SimpleFT8.
Das ist V2-Self-Review eines Plans der ein Encoder-Throughput-Race
in OMNI-CQ fixen soll.

**Deine Aufgabe:** kritisiere den V2-Plan, verifiziere die Hypothesen,
und gib KONKRETE Verbesserungsvorschlaege.

**WICHTIG — R1-Blindspot-Lesson aus P4-V5:** R1 hat in P4-V5 den
Encoder-Throughput-Race zwischen konsekutiven TX-Slots verpasst.
Bei P5 ist das Hauptthema. Dein expliziter Auftrag:

1. **Encoder-Throughput-Analyse:** Bei 12.64s FT8-Audio + PTT-Settle +
   FlexRadio-Buffer-Drain — wann faellt `_is_transmitting=False`
   relativ zur naechsten Slot-Boundary (15s nach Slot-Start)?
   Konkret: bei Slot-Start :30 — wann faellt False? Schaetzung in
   Sekunden mit Streuung.

2. **Drift-Guard-Verhalten:** `core/encoder.py:331-340` Drift-Guard
   greift wenn `silence_secs < 0.1` UND `overshoot > 0.3`. Bei
   GUI-Tick-Latency 100-400ms (siehe `core/timing.py:76-90`) — greift
   das systematisch oder nur bei OMNI's `_do_tx_slot`-Aufruf?

3. **Loesungsoptionen-Bewertung:** V2 §2 schlaegt 4 Varianten vor
   (A/B/C/D). Welche ist KISS-konform und Hobby-Tool-tauglich?
   Variante A (Encoder-Queue) ist Mike-Empfehlung — bewerte das im
   Licht der Pending-Verfall-Komplexitaet (§2.1, §3).

4. **V3-§8 Out-of-Scope (P4-V5) Verbote:** war der Verzicht auf
   Encoder-Queue + Mid-Cycle-Pretrigger gerechtfertigt? Soll es in P5
   gekippt werden?

5. **Hypothese H-Pos-4-RX-E-fehlt** (V2 §1.4): welche Pfade koennten
   `_do_rx_slot` bei Pos 4 (Block 1, RX-E :30 nach 4 Slots) im Display
   unterdruecken? Decoder-Race? `_paused`-Toggle? Ich finde keinen
   plausiblen Pfad — eventuell ein Display-Bug in
   `qso_panel.add_listening` selbst?

6. **Hypothese H-`:44 [O] Horche`-Quelle** (V2 §1.3): bei busy-Pos-1
   wird `slot_action` NICHT emittet. Wer kann dann das `add_listening`
   bei `:44 [O]` triggern? Ich finde nur main_window.py:760 als
   einzigen `add_listening`-Aufrufer — aber der wird bei busy-TX nicht
   aufgerufen.

7. **Pending-Verfall-Logik (V2 §3):** ist die `target_slot - queued_at
   > 1.5 * cycle_duration`-Schwelle korrekt? Edge-Case wenn Worker
   genau 1.5 Slots braucht? Race wenn `pending_queued_at` zwischen
   Pending-Setzen und finally-Lesen modifiziert wird?

8. **Test-Plan (V2 §3, §4):** sind die T8-T11-Tests ausreichend?
   Welche Race-Tests fehlen? Soll ich End-to-End mit echtem
   FT8Timer-Mock testen, oder reicht Direct-Aufruf von
   `on_cycle_start`?

**Datei-Beilagen** (Vollfiles):
- `core/encoder.py` (385 Z.) — transmit, _tx_worker, _tx_worker_inner, Drift-Guard
- `core/omni_cq.py` (258 Z.) — V5 signal-getriggert
- `core/timing.py` (91 Z.) — FT8Timer Tick-Loop
- `ui/main_window.py` (Issue A in :760, _on_omni_slot_action)
- `ui/mw_cycle.py` (OMNI-Hook in :586-590)
- `ui/mw_qso.py` (_on_tx_started, omni.pause-Trigger)
- `ui/qso_panel.py` (add_listening, add_tx)
- `prompts/p4_omni_neubau_v5_signal_v3.md` (V3-§8 Out-of-Scope-Liste)

**Bitte gib eine STRUKTURIERTE Antwort:**

- **§A — Encoder-Throughput-Diagnose** (R1-Frage 1+2)
- **§B — Loesungsoptionen-Bewertung** (R1-Frage 3+4)
- **§C — Hypothesen-Aufloesung** (R1-Frage 5+6)
- **§D — Pending-Verfall-Review** (R1-Frage 7)
- **§E — Test-Plan-Review** (R1-Frage 8)
- **§F — Empfehlung an Mike** (1-2 Zeilen)

Bitte KEINE Architektur-Pflicht-Vorschlaege fuer Out-of-Scope-Bereiche
(siehe V2 §8 / V1 §8) — Mike will Hobby-Funker-Tool, kein Contest-Tool.
```

---

## 7. Out-of-Scope (V1 §8 unveraendert)

V1 §8 unveraendert: Frequenz-Recheck, qso_state-Aenderungen, Listener-Pfad,
Diversity-Antennen-Switch, Auto-Hunt-Coupling, AP-Lite, OMNI-Stop-Reasons,
btn_omni_cq-UI bleiben out-of-scope.

---

## 8. APP_VERSION-Plan (V1 §9 unveraendert)

`v0.96.1 → v0.96.2` Patch-Bump.

---

## 9. Naechste Schritte

1. **R1 (DeepSeek-Reasoner)** mit dem `R1-Prompt` aus §6 + alle 8 Files
   (Vollfiles, KEIN Excerpt — Compact-Save-Lesson).
2. **R1-Findings einarbeiten → V3** (Compact-fest, Cold-Start-Test).
3. Mike-Freigabe.
4. Code-Phase.

---

**Ende V2.**
