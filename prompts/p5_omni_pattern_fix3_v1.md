# P5.OMNI-PATTERN-FIX-3 — V1 (Erstentwurf)

**Datum:** 2026-05-10
**Vorgaenger:** P4.OMNI-NEUBAU V5 (v0.96.1, Commits `0368427` C9 + `8244e37` C10)
**Diagnose-File:** `prompts/p5_omni_pattern_fix3_diagnose.md`
**Status:** V1 fertig fuer V2 (Self-Review).

---

## 0. Ziel und Scope

OMNI-CQ Pattern in v0.96.1 ist halb tot:

- **Issue B (kritisch):** Pos 1 (TX-nach-TX) wird IMMER von `encoder.transmit()`
  mit `False` (busy) abgewiesen. Pattern-Haelfte verloren.
- **Issue A (kosmetisch):** Display-Zeit der RX-Slots ist `time.time()` statt
  Slot-Boundary `:00`/`:15`/`:30`/`:45`.

**Ziel:** beides in EINEM Workflow / EINEM Patch beheben. APP_VERSION
`v0.96.1 → v0.96.2` (Patch-Bump, kein neues Feature).

**Out-of-Scope** (ausdruecklich nicht-Teil von P5, siehe §8):

- Frequenz-Recheck-Logik
- qso_state-State-Maschinen-Aenderungen
- Listener-Pfad in `mw_cycle.on_message_decoded`
- Diversity-Antennen-Switch
- Auto-Hunt-Coupling

---

## 1. Schritt 0 — Code-Verifikation (VERIFIZIERT 10.05.2026)

### 1.1 `core/encoder.py`

| File:Line | Symbol | Aktueller Stand |
|---|---|---|
| `core/encoder.py:178-212` | `transmit(message, *, tx_even, audio_freq_hz)` | atomare API, Worker-Start unter `_replace_lock`. Z. 197-200: alter Thread per `join(timeout=0.5)` gewartet. Z. 202-203: `if self._is_transmitting: return False`. |
| `core/encoder.py:214-233` | `_tx_worker(message)` | Z. 222 `_is_transmitting = True` (NICHT unter Lock). Z. 232 finally `_is_transmitting = False`. |
| `core/encoder.py:264-385` | `_tx_worker_inner(message)` | Z. 288 `next_boundary = _next_slot_boundary()`. Z. 292 `sleep_dur = (next_boundary + TARGET_TX_OFFSET - 0.5) - time.time()`. **Drift-Guard Z. 331-340:** wenn `silence_secs < 0.1` UND `overshoot > 0.3` → `next_boundary += 2*15s = 30s` (bei FT8) → silence_samples = 30s zeros werden in audio_full eingefuegt → Worker blockt 30s+12.64s = **bis ~next_boundary - 1.3s + 13s spaeter** (also tatsaechlich grob 30s laenger als „normaler" TX). |
| `core/encoder.py:25` | `TARGET_TX_OFFSET = -0.8` | FlexRadio TX-Buffer 1.3s. PTT/Audio startet bei `next_boundary - 0.8s`. |
| `core/encoder.py:235-262` | `_next_slot_boundary()` | Bei `tx_even` gesetzt + `cycle_pos < 0.5s` → aktueller Slot. Sonst naechster passender Slot. |

### 1.2 `core/omni_cq.py` (V5, signal-getriggert)

| File:Line | Symbol | Aktueller Stand |
|---|---|---|
| `core/omni_cq.py:60` | `_TX_PATTERN = (True, True, False, False, False)` | 5-Slot-Pattern TX-TX-RX-RX-RX. |
| `core/omni_cq.py:168-183` | `on_cycle_start(@Slot int, bool)` | GUI-Thread, Defense-in-Depth-Guard, Pattern-Entscheidung per `_slot_index`. |
| `core/omni_cq.py:188-201` | `_next_slot_action()` | Block 1: Pos 0 → target_even=True, Pos 1 → False. Block 2: Pos 0 → False, Pos 1 → True. |
| `core/omni_cq.py:203-229` | `_do_tx_slot(target_even)` | `encoder.transmit(cq_msg, tx_even=target_even, audio_freq_hz=...)`. **Bei `not ok` (busy): nur `logger.warning`, KEIN `slot_action.emit`, KEIN counter_changed.** _advance_state laeuft trotzdem (Aufruferseite). |
| `core/omni_cq.py:231-234` | `_do_rx_slot(is_even)` | `slot_action.emit(label, False, is_even)` mit echter UTC-Slot-Paritaet. |
| `core/omni_cq.py:236-240` | `_advance_state()` | `_slot_index = (slot_index + 1) % 5`. Bei 0 → Block-Wechsel 1↔2. |

### 1.3 `ui/main_window.py:760` (Issue A)

```python
@Slot(str, bool, bool)
def _on_omni_slot_action(self, label, is_tx, target_even):
    if not is_tx:
        self.qso_panel.add_listening(time.time(), target_even)
```

→ `time.time()` ist Wall-Time zur cycle_start-Aufruf-Zeit (kann z.B. `:44.x`
sein wenn cycle_start fuer den `:45`-Slot kommt).

### 1.4 `ui/mw_cycle.py:586-590`

```python
self.qso_sm.on_cycle_end()

# P4.OMNI-NEUBAU V5 (10.05.2026): signal-getriggerter OMNI-CQ
if hasattr(self, '_omni_cq'):
    self._omni_cq.on_cycle_start(cycle_num, is_even)
```

→ OMNI-Hook **nach** `qso_sm.on_cycle_end()` und **vor** Diversity-Block
(Z. 593+). KEIN `if encoder.is_transmitting: return`-Early-Return davor.

**Diagnose-File §0.5 sagte Z. 587-594, korrekt ist Z. 586-590.** V1
korrigiert das.

### 1.5 `ui/qso_panel.py:202-214`

```python
def add_listening(self, slot_start_ts: float, tx_even: bool):
    utc = time.strftime("%H:%M:%S", time.gmtime(slot_start_ts))
    tag = "[E]" if tx_even else "[O]"
    self._append_colored(f"{utc} {tag} ←  Horche  …", "#666666")
```

**Wichtig:** Funktion erwartet bereits einen `slot_start_ts` als float.
Issue-A-Fix muss nur den **Aufrufer** in `main_window.py:760` umstellen.

### 1.6 `prompts/p4_omni_neubau_v5_signal_v3.md` §8 Out-of-Scope

```
- ❌ cycle_tick-basierter Pretrigger / QTimer
- ❌ Encoder-Queue für OMNI
- ❌ Aenderungen an core/encoder.py
- ❌ Frequenz-Recheck zur Laufzeit
```

→ V5 hat damit den Race architektonisch eingebaut (Begruendung: KISS).
**P5 muss diese Liste UEBERDENKEN.**

### 1.7 Live-Logs (`~/.simpleft8/simpleft8.log`)

Letzter Field-Test (Zeilen 719920-720109):

```
[OMNI-CQ] User-Start
[OMNI-CQ] CQ-Audiofrequenz: 475 Hz
[OMNI-CQ] encoder.transmit busy -> Slot B1 [1/4] TX-O uebersprungen
[OMNI-CQ] encoder.transmit busy -> Slot B2 [1/4] TX-E uebersprungen
[OMNI-CQ] encoder.transmit busy -> Slot B1 [1/4] TX-O uebersprungen
[OMNI-CQ-UI] Stop (manual_halt)
```

→ **3× Pos 1 busy hintereinander** in einem Field-Test. Vorherige
Iteration (Zeilen 718169-718194): 3× `encoder.transmit returnt False
(busy) -> Slot verloren`. Bug ist deterministisch reproduzierbar.

---

## 2. Symptome (Field-Test 10.05.2026 ~06:30 UTC)

### Issue B — Pattern halb tot (kritisch)

`qso_panel`-Aufzeichnung beim ersten 10-Slot-Loop nach btn_omni_cq:

```
04:26:30 [E] → Sende    CQ DA1MHH JO31    ← Pos 0 Block 1 TX-E ✓
04:26:44 [O] ← Horche   ...                 ← Pos 1 SOLLTE TX-O sein, ist aber Horche
04:26:59 [E] ← Horche   ...                 ← Pos 2 Block 1 RX-E ✓
04:27:14 [O] ← Horche   ...                 ← Pos 3 Block 1 RX-O ✓
                                             ← Pos 4 Block 1 RX-E FEHLT KOMPLETT
04:27:45 [O] → Sende    CQ DA1MHH JO31    ← Block 2 Pos 0 TX-O ✓
04:27:59 [E] ← Horche   ...                 ← Pos 1 SOLLTE TX-E sein, ist aber Horche
```

**Beobachtung 1 (Hauptsymptom):** Pos 1 wird statt TX als „Horche" angezeigt.
Da `_do_tx_slot` bei `not ok` weder `slot_action` emit NOCH `add_listening`
triggert, MUSS die `[O] Horche`-Zeile aus einem **anderen Pfad** kommen — oder
das Slot-Pattern ist um 1 Position desynchronisiert (siehe Hypothese H2).

**Beobachtung 2 (Sekundaersymptom):** Pos 4 RX-E (Slot bei `:30` von Block 1)
fehlt komplett im Display. Erwartet waere `04:27:30 [E] ← Horche …`.

### Issue A — Display-Zeit ist Wall-Time statt Slot-Boundary (kosmetisch)

`04:26:44` statt `04:26:45`. Erwartet: `floor(time.time()/cycle_duration) *
cycle_duration` → bei FT8 immer `:00`/`:15`/`:30`/`:45`.

---

## 3. Wurzel-Analyse Issue B

### 3.1 Encoder-Throughput-Race (Hauptursache)

**FT8-Slot 15s, TARGET_TX_OFFSET=-0.8, FlexRadio TX-Buffer 1.3s:**

| t | Encoder-Zustand | OMNI-Aktion |
|---|---|---|
| `:30.0xx` | cycle_start fuer Pos 0 TX-E | `_do_tx_slot(True)` ruft `encoder.transmit(tx_even=True)`. `_is_transmitting=False` → True gesetzt, Thread startet. **Returnt True ✓.** Pattern-emit Pos 0. |
| `:30.0xx-:30.2xx` | Worker startet, `encode_message` (~50-200ms) | — |
| `:30.2xx` | Worker bei Z. 322 `now=:30.2`, `silence_secs = max(0, :30-0.8 - :30.2) = 0` → < 0.1 → Drift-Guard pruefen | — |
| `:30.2xx` | `overshoot = :30.2 - :29.2 = 1.0s > 0.3s` → **Drift-Guard greift** → `next_boundary = :30 + 2*15 = :60` (naechster passender Even-Slot), `silence_secs = max(0, :60-0.8 - :30.2) = 29.0s`. Print: „Drift-Vermeidung: overshoot=1.00s → Slot 60.0". | — |
| `:30.2xx` | `silence_samples = int(29.0 * 12000) = 348000` zeros + 12.64s audio_12k → audio_full ~41.64s | — |
| `:30.2xx-:42.84` | `radio.send_audio(audio_full, sample_rate=12000)` blockt fuer Audio-Pacing | — |
| **WICHTIG:** Audio dauert tatsaechlich `(348000 + len(audio_12k)) / 12000` Sekunden. Bei FT8 Signal `12.64s` → audio_full ~41.64s → send_audio blockt ~41.64s ab `:30.2`. | | |
| `:30.2 + 41.64 ≈ :72` | PTT off, `tx_finished.emit()`, finally `_is_transmitting = False` | — |
| `:45.0xx` | cycle_start Pos 1 TX-O — Encoder noch True (busy bis ~:72) | `transmit(...)` Z. 202 → `if self._is_transmitting: return False` → **Slot verloren.** |
| `:60.0xx` | cycle_start Pos 2 RX-E — Encoder noch True (busy bis ~:72) | `_do_rx_slot(is_even=True)` → `slot_action.emit(..., False, True)` → `add_listening(:60.0xx, True)` ✓ |
| `:75.0xx` | cycle_start Pos 3 RX-O — Encoder noch True knapp (busy bis ~:72), aber nur `is_transmitting`-Check fuer TX-Slots | `_do_rx_slot(is_even=False)` → emit ✓ |
| `:90.0xx` | cycle_start Pos 4 RX-E | `_do_rx_slot(is_even=True)` → emit ✓ |
| `:105.0xx` | cycle_start Block 2 Pos 0 TX-O — Encoder False seit ~:72 (mehr als 30s frei) | `transmit(tx_even=False)` ✓ |
| `:120.0xx` | cycle_start Block 2 Pos 1 TX-E — Encoder vermutlich noch busy von Block-2-Pos-0-TX | `transmit(tx_even=True)` → busy → verloren. Gleicher Bug. |

**Damit ist Issue B (Pos 1 immer busy) erklaert.** Die Wurzel ist die
Kombination aus zwei Effekten:

1. **cycle_start-Latency:** GUI-Thread reagiert nicht exakt bei `:30.0`,
   sondern bei `:30.0xx` (typisch 0.05-0.5s GUI-Tick-Latency). `cycle_pos
   < 0.5s` Threshold im `_next_slot_boundary` (Z. 254) lae sst aktuellen
   Slot zu, aber `_tx_worker_inner` hat dann `silence_secs ≈ 0`.
2. **Drift-Guard:** `_tx_worker_inner` Z. 331-340 erkennt overshoot > 0.3s
   und schiebt `next_boundary` um 2 Slots (FT8: +30s) → Worker blockt
   30+12.64s ≈ 42.64s ab `transmit()`-Start.

**Konsequenz:** `_is_transmitting=False` faellt bei FT8 erst ~42s nach
Pos-0-Start → Pos 1 immer busy, Pos 2 evtl. auch knapp busy bei
Worst-Case-cycle_start-Latency.

### 3.2 Hypothese H1 — Issue B alternative Erklaerung

Wenn cycle_start exakt bei `:30.0` feuert (kein GUI-Latency), greift der
Drift-Guard nicht (overshoot < 0.3s), `silence_secs = 0`, Worker sendet
12.64s Audio + PTT-Settle. `_is_transmitting=False` bei ~`:42.84-:43`.
Pos 1 cycle_start `:45.0xx` → in **0-2s Race-Window** je nachdem ob
Encoder-finally durch ist.

**In Praxis:** beides spielt sich ab. Drift-Guard verschaerft das Problem,
aber selbst ohne Drift-Guard ist `:42.84-:45.0xx` ein knappes Fenster.
Field-Test-Logs zeigen 100% Pos-1-Busy → Drift-Guard ist vermutlich der
Hauptfaktor. **R1 muss das verifizieren** (siehe §10).

### 3.3 Hypothese H2 — Pos 4 RX-E + `:44 [O] Horche` Sekundaersymptome

**Mike's Display zeigt `:44 [O] Horche` bei Pos 1.** Aber `_do_tx_slot` bei
busy emittet KEIN `slot_action`. WO kommt der Eintrag her?

**Moegliche Erklaerung A — verzaehlt:** Mike hat die Slots optisch falsch
zugeordnet. `:44` koennte Pos 0 von Block 2 sein (15+15+14=44) — aber
Block 1 hat 5 Slots, also ist Block 2 Pos 0 erst bei `:30+15*5=:105`. Passt
nicht.

**Moegliche Erklaerung B — Decoder-add_rx-Bug:** `qso_panel.add_rx`
(Z. 188-200) hat einen Fallback der `slot_start_ts=None` zu „aktueller Slot"
runden kann. Wenn ein Decoder-Empfang um `:44` reinkommt mit
`slot_start_ts=None`, koennte das als „Empf. ..." angezeigt werden — aber
Mike sah „Horche", nicht „Empf.". Faellt also weg.

**Moegliche Erklaerung C — Display-Trim:** `qso_panel._auto_trim_by_age`
(5min) entfernt Zeilen am Anfang. Aber das wuerde Eintraege NICHT in der
Mitte verschieben. Faellt weg.

**Wahrscheinlichste Erklaerung D — Pattern-Beobachtung um 1 verschoben:**
Mike hat das `:44 [O] Horche` als Pos 1 interpretiert, weil er die
nicht-vorhandene Pos-1-TX-Zeile vermisst hat. Was er als „Pos 2/3/4" sieht
(`:59`/`:14`/fehlt) ist tatsaechlich „Pos 2/3/4". Das `:44 [O]` ist
**eine andere Quelle** — moeglich:

  - Encoder-`tx_started.emit(message, _tx_even=False, next_boundary=...)`
    bei Drift-Guard-Verschiebung des Pos-0-TX → `qso_panel.add_tx` koennte
    bei einem Drift-verschobenen Slot eine Anzeige in einer falschen Zeile
    triggern. → **MUSS in V2 verifiziert werden** durch Code-Read von
    `_on_tx_started` und `qso_panel.add_tx`.

**Pos 4 RX-E fehlt:** Wenn cycle_start bei `:30` fuer Pos 4 gefeuert hat,
sollte `_do_rx_slot(is_even=True)` → `slot_action.emit(..., False, True)`
laufen. Wenn das fehlt: Hat **on_cycle_start nicht gefeuert** ODER
**_active wurde False/_paused wurde True**.

  - **on_cycle_start nicht gefeuert:** unmoeglich — FT8Timer feuert
    deterministisch.
  - **_paused = True:** kann passieren wenn ein Decode reinkommt der
    qso_state in einen QSO-State versetzt → mw_cycle pausiert OMNI. ABER
    Mike hat keinen QSO erwaehnt. → R1 verifizieren.
  - **Spam-Rate-Limit?** `qso_panel._auto_trim_by_age` 5-min trimt nur
    alte Eintraege, nicht aktuelle. Faellt weg.

→ **V2 + R1 muessen diese Hypothesen schaerfen.** V1 dokumentiert sie
als offene Punkte.

### 3.4 Encoder-Throughput-Problem ist V5-Architektur-Choice

V3 §8 Out-of-Scope (P4-V5) hat explizit verboten:

```
❌ cycle_tick-basierter Pretrigger / QTimer
❌ Encoder-Queue für OMNI
❌ Aenderungen an core/encoder.py
❌ Frequenz-Recheck zur Laufzeit
```

P2.OMNI-PATTERN-FIX (v0.95.24, Commits `6a86764` + `337e4ca`) hatte genau
diese 2 Bausteine implementiert (Encoder-Queue + Mid-Cycle-Pretrigger via
cycle_tick) und damit das Pattern stabil. P3.OMNI-PATTERN-FIX-2 (v0.95.25,
Commit `ee3ac9a`) hat es auf QTimer-Pretrigger erweitert.

P4.OMNI-NEUBAU C3 (`1d76457`) hat die Encoder-Queue wieder rausgemacht.
P4.OMNI-NEUBAU C5 (`b58c5df`) hat den Mid-Cycle-Pretrigger entfernt.

→ **V5-KISS-Verzicht hat den Race zurueckgebracht.** Die V3-§8-Liste muss
in P5 ueberdacht werden.

---

## 4. Loesungsoptionen (4, R1 zur Bewertung)

### Option A — Encoder-Queue zurueckbringen (Mike-Empfehlung)

**Kern:** `core/encoder.transmit()` nimmt einen pending-Job an, wenn
`_is_transmitting=True`. Worker-Thread checkt am Ende ob Pending vorliegt
→ startet sofort den naechsten TX-Job.

**Implementierung-Skizze:**

```python
# core/encoder.py
def transmit(self, message, *, tx_even=None, audio_freq_hz=None) -> bool:
    if (self._tx_thread is not None and self._tx_thread.is_alive()
            and threading.current_thread() is not self._tx_thread):
        self._tx_thread.join(timeout=0.5)
    with self._replace_lock:
        if self._is_transmitting:
            # NEU: Queue statt return False
            self._pending_tx = (message, tx_even, audio_freq_hz)
            return True   # Aufrufer denkt es laeuft → Pattern-Emit klappt
        if tx_even is not None: self.tx_even = tx_even
        if audio_freq_hz is not None: self.audio_freq_hz = audio_freq_hz
    self._tx_thread = threading.Thread(target=self._tx_worker, args=(message,), daemon=True)
    self._tx_thread.start()
    return True

def _tx_worker(self, message):
    self._is_transmitting = True
    self._abort_event.clear()
    try:
        self._tx_worker_inner(message)
    finally:
        # NEU: Pending-Check im finally — Worker startet sofort den naechsten Job
        with self._replace_lock:
            pending = self._pending_tx
            self._pending_tx = None
        if pending:
            msg, tx_even, audio_freq = pending
            with self._replace_lock:
                if tx_even is not None: self.tx_even = tx_even
                if audio_freq is not None: self.audio_freq_hz = audio_freq
            # Direkt rekursiv weiterlaufen — kein neuer Thread
            self._is_transmitting = True
            self._abort_event.clear()
            try:
                self._tx_worker_inner(msg)
            finally:
                self._is_transmitting = False
                self._audio_started = False
        else:
            self._is_transmitting = False
            self._audio_started = False
```

**Pro:**
- Wenig OMNI-Code (kein cycle_tick, kein QTimer).
- Alle TX-Slots werden bedient.
- Aufrufer-API unveraendert (Returnt True, OMNI's `_do_tx_slot` emit ohne Code-Aenderung).

**Kontra:**
- Verstoss gegen V3-§8-Liste („Encoder-Queue ❌").
- **Ist der gequeueete TX-Slot noch valide?** Wenn Pos 0 bei :30 startet
  und bis :72 laeuft, dann ist Pos 1 (`tx_even=False`, target slot `:45`)
  zum Pending-Start-Zeitpunkt :72 bereits vorbei. `_next_slot_boundary` mit
  `tx_even=False` liefert dann den naechsten Odd-Slot `:75`. → TX-O wird
  bei `:75` gesendet, NICHT `:45`. **Pattern-Drift!**
- Loesung: Pending-Job verfaellt wenn `next_boundary > now + slot`
  (Slot ist schon vorbei). → Quasi `return False` aus dem Pending-Pfad.
  Erfordert Logik die in `_tx_worker_inner` noch nicht existiert.

**Komplexitaet:** ~30-50 Z. in `core/encoder.py`, neue Tests fuer Pending-
Verfall, Race-Tests fuer parallele transmit()-Calls.

### Option B — Mid-Cycle-Pretrigger zurueckbringen

**Kern:** OMNI ruft `encoder.transmit()` nicht beim cycle_start des
TX-Slots, sondern **1.3-1.5s VOR cycle_start** des TX-Slots. Worker hat
dann genug Vorlaufzeit fuer encode_message + Sleep bis next_boundary.

**Implementierung-Skizze:**

```python
# core/omni_cq.py
def on_cycle_start(self, cycle_num, is_even):
    if not self._active or self._paused: return
    is_tx, target_even = self._next_slot_action()
    # NEU: Pretrigger fuer den NAECHSTEN Slot 1.3s vor seiner Boundary
    next_is_tx, next_target_even = self._peek_next_slot_action()
    if next_is_tx:
        # Hier 1.3s warten via QTimer.singleShot, dann encoder.transmit
        # ABER: das ist QTimer / cycle_tick / Pretrigger — V3-§8-Verbot
        ...
```

**Pro:**
- Encoder hat genug Zeit (1.3s Vorlauf).
- Slot ist deterministisch korrekt.

**Kontra:**
- Verstoss gegen V3-§8-Liste („cycle_tick-basierter Pretrigger / QTimer ❌").
- Kompliziert: braucht `peek_next_slot_action()` ohne State-Mutation +
  neuen Timer-Mechanismus.
- Race wenn Pretrigger-Timer feuert nachdem ein QSO startet (paused-Race).

**Komplexitaet:** ~50-80 Z. in `core/omni_cq.py` + neue Tests.

### Option C — Pattern auf 1 TX/Block reduzieren

**Kern:** `_TX_PATTERN = (True, False, False)` (3-Slot-Pattern, 1 TX), oder
weiterhin 5-Slot aber `(True, False, False, False, False)`. Block-Wechsel
nach jedem Block. → Pos 1 ist NIE TX → kein Encoder-Race.

**Pro:**
- Kein Encoder-Race moeglich.
- Trivial: 1 Zeile in `omni_cq.py`.
- Kein Verstoss gegen V3-§8-Liste.

**Kontra:**
- **Aendert Mike-Spec** (`project_omni_cq_spec.md` § „5-Slot-Pattern" mit
  TX-TX-RX-RX-RX). **Mike-Freigabe noetig.**
- Halbiert die TX-Rate → halbiert die CQ-Reichweite.
- Die Begruendung der 5-Slot-Spec war: „beide Paritaeten in einem
  Block bedienen, dann lange RX-Phase". Bei 1-TX-Pattern braucht es 2
  Blocks fuer beide Paritaeten → Block-Wechsel-Logik aendert sich.

**Komplexitaet:** ~5 Z. in `core/omni_cq.py`, Tests anpassen.

### Option D — Pos 1 TX um 1 Slot verschieben

**Kern:** `_TX_PATTERN = (True, False, True, False, False)` Block 1 →
Pos 0 TX-E, Pos 1 RX-O, Pos 2 TX-E (oder anders, je nach
Paritaets-Logik), Pos 3-4 RX. Zwischen TX 1 und TX 2 liegt 1 RX-Slot
(15s) → Encoder hat Zeit.

**Pro:**
- Encoder-Race vermieden ohne Encoder-Aenderung.
- Beide TX-Paritaeten weiterhin in einem Block.

**Kontra:**
- **Aendert Mike-Spec.**
- Block 1 deckt nur 1× E ab (Pos 0 + Pos 2 sind beide E?). Paritaet-Logik
  muss neu durchdacht werden — die `_next_slot_action` Pattern-Matching
  in `omni_cq.py:188-201` muss umgebaut werden.
- Hat das gleiche Problem fuer Pos 2 wenn ein QSO bei Pos 0 lief und
  Worker noch laeuft.
- TX-CQ-Frequenz waere mehr Zeit auseinander → niedrigere Antwort-Rate
  pro Block.

**Komplexitaet:** ~15-25 Z. in `core/omni_cq.py` (Pattern + Pos-zu-Paritaet-
Mapping), Tests stark anpassen.

### Empfehlung an Mike (V1-Vorschlag)

**Variante A (Encoder-Queue) ist KISS-konform und loest Issue B sauber
ohne Mike-Spec zu aendern.** Die V3-§8-Verbot-Liste war eine bewusste
Entscheidung damals — aber im Licht des Field-Tests muss sie ueberdacht
werden. R1 soll explizit Stellung dazu nehmen.

**Risiko bei A:** Pending-Verfall-Logik (Slot bereits vorbei). V2 muss
das beim Implementations-Skeleton genauer ausarbeiten.

---

## 5. Akzeptanzkriterien

### Issue B (Encoder-Race-Fix)

| AC | Kriterium | Test |
|---|---|---|
| AC-B1 | Pos 1 (TX nach TX) sendet IMMER. `encoder.transmit` wird nicht mit `False` abgewiesen. | T1 (mock encoder, simuliere `_is_transmitting=True` → erwarte dass V5+Loesung das verhindert ODER der Pending-Pfad emit triggert). |
| AC-B2 | `slot_action`-Emit fuer Pos 1 TX feuert (Pattern-Anzeige korrekt). | T2 |
| AC-B3 | Pattern Block 1 EXAKT: TX-E, TX-O, RX-E, RX-O, RX-E (5 Eintraege pro Block). | T3 (E2E mit echtem Cycle-Loop) |
| AC-B4 | Pattern Block 2 EXAKT: TX-O, TX-E, RX-O, RX-E, RX-O. | T4 |
| AC-B5 | Auto-Rollover Block 1 ↔ Block 2 nach 5 Slots. | T5 |
| AC-B6 | 10-Slot-Loop in `qso_panel` ohne Luecke, ohne Drift, ohne busy-Skips. | Field-Test (Mike) |
| AC-B7 | Pos 4 RX-E (Block 1) wird IMMER im qso_panel angezeigt. | T6 (Hypothese H2 verifizieren) |

### Issue A (Display-Slot-Boundary)

| AC | Kriterium | Test |
|---|---|---|
| AC-A1 | `add_listening`-Zeit zeigt Slot-Boundary `:00`/`:15`/`:30`/`:45` bei FT8. | T7 (mock `time.time()` → `04:26:44.5`, erwarte `add_listening` mit `ts=04:26:30` bei `cycle_duration=15`). |
| AC-A2 | Bei FT4 (7.5s) und FT2 (3.8s): Slot-Boundary entsprechend `cycle_duration` gerundet. | T8 (parametrize FT4/FT2). |
| AC-A3 | Korrekte `cycle_duration`-Quelle: `self.timer.cycle_duration` (nicht hardcoded). | Code-Review. |

### Querschnitt

| AC | Kriterium | Test |
|---|---|---|
| AC-Z1 | Hardware-Garantie ANT1 unveraendert (encoder.transmit setzt zentral). | Code-Read encoder.py (kein Diff am `set_tx_antenna`-Call). |
| AC-Z2 | Tests: alle 1020 weiter gruen, neue Tests fuer Issue B + A. | `pytest tests/ -q` |
| AC-Z3 | Keine Aenderung an Out-of-Scope-Bereichen (siehe §8). | Code-Review per `git diff --stat`. |
| AC-Z4 | APP_VERSION 0.96.1 → 0.96.2. | `git log -p main.py` |

---

## 6. Hypothesen-Verifikation (Schritt vor Code-Phase)

V2 / R1 muss klaeren:

1. **H-Drift-Guard:** Greift der Drift-Guard bei Pos-0-TX bei FT8 in Praxis?
   Wie hoch ist die typische `cycle_pos` zum cycle_start-Zeitpunkt? Wenn
   `cycle_pos < 0.3s` (z.B. weil GUI-Tick-Latency < 0.3s) → kein
   Drift-Guard, normaler 12.64s-TX → `_is_transmitting=False` bei ~`:43`.
   Pos 1 cycle_start `:45.0xx` → Race-Window 1-2s.
2. **H-Race-Window:** Wenn KEIN Drift-Guard greift: Wie zuverlaessig faellt
   `_is_transmitting=False` vor `:45.0xx`? Field-Test zeigt 100% busy →
   Race-Window-Bias muss hart sein (>1s), oder Drift-Guard greift in fast
   allen cycle_start-Aufrufen.
3. **H-Pos-4-Display:** Warum fehlt Pos 4 RX-E im qso_panel? `_paused`
   gesetzt durch QSO-State? Decoder-Latency? `_auto_trim_by_age`?
4. **H-`:44 [O] Horche`-Quelle:** Welcher Pfad emittiert dieses
   add_listening? Eventuell `tx_started` mit verschobenem next_boundary
   triggert `qso_panel.add_tx` falsch — V2 muss das via Code-Read
   pruefen.

V2 muss diese Hypothesen aufloesen oder zumindest klar an R1 weitergeben.

---

## 7. Test-Plan (Skizze, in V3 final)

### Unit-Tests (signal-getriggert, kein Mock des kritischen Pfads)

| ID | Name | AC |
|---|---|---|
| T1 | `test_pos1_tx_succeeds_when_encoder_busy_at_cycle_start` | AC-B1, AC-B2 |
| T2 | `test_omni_block1_pattern_5_slots_exact` (parametrize Pos 0-4) | AC-B3 |
| T3 | `test_omni_block2_pattern_5_slots_exact` | AC-B4 |
| T4 | `test_block_rollover_after_pos4` | AC-B5 |
| T5 | `test_pos4_rx_e_always_emitted` (Hypothese H-Pos-4) | AC-B7 |
| T6 | `test_add_listening_uses_slot_boundary_ft8` (Mock `time.time()` 04:26:44.5 → erwartet ts=04:26:30) | AC-A1 |
| T7 | `test_add_listening_uses_slot_boundary_ft4_ft2` (parametrize) | AC-A2 |
| T8 | `test_encoder_pending_tx_consumed_after_finally` (nur fuer Variante A) | AC-B1 implementation |
| T9 | `test_encoder_pending_tx_dropped_if_slot_passed` (nur fuer Variante A) | Pending-Verfall-Logik |

### E2E-Test (`test_omni_cq_integration.py` erweitern)

| ID | Name | AC |
|---|---|---|
| E1 | `test_omni_10_slot_loop_no_busy_skips` (echte FT8Timer-Mock + echter Encoder-Stub) | AC-B1 bis AC-B6 |

### Field-Test (Mike, V3 §6)

10-Slot-Loop sauber, Block 1 + Block 2 EXAKT, kein busy-Log, alle Display-
Zeiten auf `:00`/`:15`/`:30`/`:45`.

---

## 8. Out-of-Scope (kein Scope-Creep!)

- ❌ Frequenz-Recheck-Logik (V5-KISS bleibt)
- ❌ qso_state-State-Maschinen-Aenderungen
- ❌ Listener-Pfad in `mw_cycle.on_message_decoded`
- ❌ Diversity-Antennen-Switch
- ❌ Auto-Hunt-Coupling
- ❌ AP-Lite, OMNI-Stop-Reasons, btn_omni_cq-UI, Easter-Egg-Toggle (alles unveraendert)

P5 ist NUR: TX-Throughput-Race fixen + Display-Slot-Boundary.

---

## 9. APP_VERSION-Plan

`v0.96.1 → v0.96.2` (Patch-Bump: Race-Fix + Display-Korrektur, kein
neues Feature).

`main.py` Konstante `APP_VERSION = "0.96.2"`.

---

## 10. R1-Fragen (V2 → R1, V3 mit Stellungnahmen)

**Pflicht-Frage (R1-Blindspot-Lesson, `feedback_r1_encoder_busy_blindspot.md`):**

> „Kann der Encoder bei zwei konsekutiven TX-Slots ohne Race-Pause die
> Audio rechtzeitig fertigrendern? Wann setzt `_is_transmitting=False`
> relativ zum naechsten cycle_start? Greift `transmit()` ggf. zu
> `return False`? Wie verhaelt sich der Drift-Guard
> (`core/encoder.py:331-340`) bei Pos-0-TX wenn cycle_start mit
> `cycle_pos > 0.3s` Latency feuert?"

**Spezifische R1-Fragen P5:**

1. **Drift-Guard Realitaet:** Greift `_tx_worker_inner` Drift-Guard
   (Z. 331-340) systematisch bei OMNI's `_do_tx_slot` weil cycle_start im
   GUI-Thread Latency hat? Wenn ja → `_is_transmitting` bleibt 30+12.64s
   True → ALLE Pos 1 TX und auch Pos 2 RX (bei Worst-Case) werden
   blockiert. Loesung?
2. **Variante A Pending-Verfall:** Wie sauber kann ein gequeueeter Pending-
   TX-Job „verfallen" wenn der target Slot bereits vorbei ist? Threshold
   `next_boundary > now + slot/2`? `> now + 0.3s`? Welche `tx_even`-Logik?
3. **V3-§8 Out-of-Scope-Liste:** War das Verbot gerechtfertigt im Licht von
   Issue B? Welche der 4 Optionen ist KISS-konform unter Beruecksichtigung
   der Mike-Spec (5-Slot-Pattern, beide Paritaeten in einem Block)?
4. **Pos 4 RX-E fehlt — Hypothese:** Welcher Pfad koennte `_do_rx_slot`
   bei Pos 4 unterdruecken? `_paused`? Race im `_advance_state`?
   `Qt.QueuedConnection`-Race?
5. **`:44 [O] Horche`-Quelle:** Wenn `_do_tx_slot` bei busy KEIN
   `slot_action` emittet — wer emittet dann das `add_listening` bei
   `:44`? Encoder-`tx_started.emit` mit verschobenem next_boundary?
6. **Slot-Boundary-Display (Issue A):** Ist `floor(time.time() /
   self.timer.cycle_duration) * self.timer.cycle_duration` der saubere
   Weg? Was passiert wenn `self.timer` noch nicht initialisiert ist
   (RX-AUS-Branch)?
7. **Test-Plan:** Reichen die 9 Unit-Tests + 1 E2E? Welche Race-Tests
   fehlen?

---

## 11. Risiko-Bewertung (in V2 / R1 schaerfen)

| ID | Risiko | Mitigation |
|---|---|---|
| R1 | Variante A Pending-Verfall faengt nicht alle Edge-Cases (Slot bereits vorbei). | V2 implementiert Pending-Verfall-Logik mit Test T9. |
| R2 | Encoder-Aenderung verletzt Normal-CQ-Pfad (mw_qso `_on_send_message` wird mehrfach gerufen). | Test gegen Normal-CQ-Pfad: Pending wird gar nicht gequeueet weil Normal-CQ nur 1 TX pro 2-Slot-Periode macht. |
| R3 | Pattern-Drift wenn Pending-Job auf falschen Slot trifft. | Pending-Verfall greift; falls nicht → Drift erkennbar im Log. |
| R4 | Issue A Slot-Boundary-Rundung bei Mode-Wechsel (FT8→FT4 mitten im OMNI). | `cycle_duration` aus `self.timer` gelesen → automatisch korrekt. Test T7 parametrize. |

---

## 12. Plan-Files V1-V3 Pfad

- ✅ `prompts/p5_omni_pattern_fix3_diagnose.md` (Diagnose)
- ✅ `prompts/p5_omni_pattern_fix3_v1.md` (DIESE DATEI)
- 🔜 `prompts/p5_omni_pattern_fix3_v2.md` (Self-Review)
- 🔜 `prompts/p5_omni_pattern_fix3_r1.md` (R1-Output)
- 🔜 `prompts/p5_omni_pattern_fix3_v3.md` (Compact-fest, einzige Wahrheit)

---

## 13. Naechste Schritte

1. **V2 Self-Review** — Lesson-Liste aus V1 sammeln, Hypothesen H1-H4
   praezisieren, Pending-Verfall-Code-Skizze ausarbeiten.
2. **R1 (DeepSeek-Reasoner)** mit V2 + alle 4 Vollfiles + p4_v3.md.
3. **V3 Compact-fest** — Cold-Start-Test (jeder file:line per grep).
4. Mike-Freigabe.
5. Code-Phase.

---

**Ende V1.**
