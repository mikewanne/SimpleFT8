# P5.OMNI-PATTERN-FIX-3 — V3 (Compact-fest, Mike-freigabe-bereit)

**Datum:** 2026-05-10
**Vorgaenger:** P4.OMNI-NEUBAU V5 (v0.96.1, Commits `0368427` C9 + `8244e37` C10)
**Plan-Files:** `diagnose.md`, `v1.md`, `v2.md`, `r1_prompt.md`, `r1.md`
**Status:** V3 fertig, wartet auf Mike-Freigabe → Compact → Code.

---

## 0. Compact-Hinweis fuer fresh-Instanz

Wenn du diesen Plan **nach einem Compact** liest, dann:

1. **Schritt 0 erneut durchfuehren** — alle file:line-Verweise in §1 mit
   `Read`/`Grep` gegen aktuellen Code verifizieren. Code kann sich
   geaendert haben (z.B. Zeilen-Verschiebung, Refactor).
2. **Memory neu laden:**
   - `project_p5_omni_pattern_fix3.md` (Trigger-File)
   - `project_omni_cq_spec.md` (Mike-Spec, verbindlich)
   - `feedback_test_critical_path_not_mock.md` (P4-Lesson)
   - `feedback_r1_encoder_busy_blindspot.md` (P5-Lesson, nicht wieder verpassen!)
   - `feedback_compact_save_cold_start_test.md` (Cold-Start-Pflicht)
   - `feedback_workflow_no_exceptions.md` (Workflow-Pflicht)
3. **R1-Output checken:** `prompts/p5_omni_pattern_fix3_r1.md` enthaelt
   die R1-Stellungnahme. KRITISCH-Findings sind in V3 §5 / §7 / §8
   eingearbeitet — bitte nochmal gegenchecken bevor Code beginnt.
4. **App-Status:** v0.96.1 lokal commited. KEIN Push seit v0.95.16. App
   ist gestoppt (Mike startet sie selbst fuer Field-Test).
5. **Tests-Stand:** **1020 gruen** (verifiziert). Nach P5: **~1029 erwartet**
   (9 neue Tests T1, T2N, T7, T8 [parametrize +2], T9-T13). KEINE Migration
   bestehender Tests notwendig — Cold-Start-Test bestaetigt.

## 0a. Cold-Start-Test Findings (vor Compact, 10.05.2026 ~08:30 UTC)

Diese 7 Findings wurden VOR Compact in V3 eingearbeitet (saved von
fresh-Instanz-Schmerzen):

- **F1 KRITISCH (K1):** Abort-Race im Pending-Loop — `_run_one_tx_pass`
  cleart `_abort_event` und setzt `_is_transmitting=True`. Wenn `abort()`
  zwischen Pass-1 und Pending-Re-Trigger feuert, geht abort verloren. **Fix
  in §4.1.3 Code-Diff: abort-Check vor Re-Trigger.**
- **F2 (W3):** **KEINE Migration bestehender Tests notwendig.** Bestehende
  Tests die `_is_transmitting=True` setzen (test_modules.py:710/2582/2648/
  2690/2823, test_p1_9_replace.py:37/49) rufen `_tx_worker_inner` direkt,
  nicht `transmit()` — Pending-Pfad nicht betroffen. Replace-Pfad-Test
  (test_modules.py:2778) macht `abort()` vor 2. transmit → kein Pending.
- **F3 (K2):** **Tests T2-T6 in V3 V2 waren redundant.** Existing Tests in
  `test_omni_cq_signal.py` decken Pos 0 (Z. 109), Pos 1 TX-O (Z. 122),
  Pos 2-4 RX-Pattern (Z. 140), Block-Rollover (Z. 160/195/208) bereits ab.
  V3 §7 Test-Plan reduziert auf 9 wirklich neue Tests.
- **F4 (K3):** `test_encoder_busy_no_counter_no_slot_action_but_advance`
  (test_omni_cq_signal.py:401) BLEIBT GRUEN — Mock setzt
  `transmit.return_value=False` explizit, OMNI's `if not ok: log`-Branch
  existiert weiter. Mit Variante A ist der Branch nur konzeptuell
  unerreichbar (echter Encoder returnt nie mehr False). **Aber das Mock-
  Setup zwingt False — Test prueft den existierenden else-Pfad in OMNI.**
  Neuer Test T2N ergaenzt: bei `transmit.return_value=True` (Pending-Mock)
  → counter+slot_action emit (Praxis-Pfad).
- **F5 (W4):** APP_VERSION ist in `main.py:16` (`APP_VERSION = "0.96.1"`).
  Bump auf `"0.96.2"`.
- **F6 (W2):** Code-Diff Insertion-Points praezisiert in §1 + §4 (Z. 77,
  Z. 178-212 ersetzen, Z. 214-233 ersetzen, neue Methoden danach).
- **F7 (W5):** Counter-Inkrement bei Pending-Verfall — akademischer
  Off-by-one. Akzeptiert (siehe AC-E1 Anmerkung + R8).

---

## 1. Schritt 0 — Code-Verifikation (Stand 10.05.2026)

| File:Line | Symbol | Aktueller Stand |
|---|---|---|
| `core/encoder.py:25` | `TARGET_TX_OFFSET = -0.8` | FlexRadio TX-Buffer 1.3s. Audio startet bei `boundary - 0.8s` → RF bei `boundary + 0.5s` → DT≈0. |
| `core/encoder.py:55` | `self._is_transmitting = False` | Konstruktor — initial False. |
| `core/encoder.py:75-77` | `_audio_started`, `_replace_message`, `_replace_lock` | P1.9-Replace-Mechanik (orthogonal zu Pending). **Pending-Tx wird DIESEN Lock mit-nutzen.** |
| `core/encoder.py:178-212` | `transmit(message, *, tx_even, audio_freq_hz)` | Atomare API. **Z. 197-200:** alter Thread per `_tx_thread.join(timeout=0.5)` gewartet. **Z. 201-203:** `with self._replace_lock: if self._is_transmitting: return False`. **Hier wird die Pending-Logik eingebaut.** |
| `core/encoder.py:214-233` | `_tx_worker(message)` | **Z. 222** `_is_transmitting = True` (auserhalb Lock). **Z. 232 finally** `_is_transmitting = False`. **Hier wird der Pending-Re-Trigger eingebaut.** |
| `core/encoder.py:264-385` | `_tx_worker_inner(message)` | Drift-Guard Z. 331-340 unveraendert lassen — Pending-Mechanik laeuft auf der naechsten Iteration durch. Z. 308 `if not self._is_transmitting: return` fängt abort() im Sleep — bei Pending-Re-Trigger stehen wir wieder auf `_is_transmitting=True` (im Re-Trigger). |
| `core/omni_cq.py:60` | `_TX_PATTERN = (True, True, False, False, False)` | Unveraendert. |
| `core/omni_cq.py:168-183` | `on_cycle_start(@Slot int, bool)` | Unveraendert — `_do_tx_slot` und `_do_rx_slot` werden nicht angefasst. |
| `core/omni_cq.py:203-229` | `_do_tx_slot(target_even)` | Z. 214-216 ruft `encoder.transmit(cq_msg, tx_even=target_even, audio_freq_hz=...)`. **Mit Variante A returnt das jetzt True wenn Pending gequeueet wurde.** Pos 1 emit klappt. |
| `core/timing.py:76-90` | `FT8Timer._tick_loop()` | Tick-Sleep 100ms + Qt-Queued-Connection → cycle_start kommt 100-400ms NACH echter Slot-Boundary beim GUI-Thread. |
| `ui/main_window.py:760` | `self.qso_panel.add_listening(time.time(), target_even)` | **HIER Issue A Fix.** |
| `ui/mw_cycle.py:586-590` | OMNI-Hook nach `qso_sm.on_cycle_end()` | Unveraendert. |
| `ui/mw_qso.py:112-129` | `_on_tx_started(message, tx_even, slot_start_ts)` → `qso_panel.add_tx(...)` | Unveraendert. Display-Anzeige fuer TX-Slots geht ueber `encoder.tx_started`-Signal mit `slot_start_ts = next_boundary` aus encoder.py:373 (post-Drift-Guard, falls greift). |
| `ui/qso_panel.py:202-214` | `add_listening(slot_start_ts, tx_even)` | Erwartet bereits `slot_start_ts` als float. NUR Aufrufer in `main_window.py:760` muss umgestellt werden. |

**App-Status:** Tests `1020 gruen` (v0.96.1). v0.95.16-0.96.1 + P2-Tool
lokal commited, **kein Push seit v0.95.16**. App gestoppt.

---

## 2. Symptome (Field-Test 10.05.2026 ~06:30 UTC)

### Issue B — Pattern halb tot (kritisch)

```
04:26:30 [E] → Sende    CQ DA1MHH JO31    ← Pos 0 Block 1 TX-E ✓
04:26:44 [O] ← Horche   ...                 ← Pos 1 SOLLTE TX-O sein
04:26:59 [E] ← Horche   ...                 ← Pos 2 Block 1 RX-E ✓
04:27:14 [O] ← Horche   ...                 ← Pos 3 Block 1 RX-O ✓
                                             ← Pos 4 Block 1 RX-E FEHLT
04:27:45 [O] → Sende    CQ DA1MHH JO31    ← Block 2 Pos 0 TX-O ✓
04:27:59 [E] ← Horche   ...                 ← Pos 1 SOLLTE TX-E sein
```

**Log (`~/.simpleft8/simpleft8.log` Z. 719920-720109):**
```
[OMNI-CQ] User-Start
[OMNI-CQ] CQ-Audiofrequenz: 475 Hz
[OMNI-CQ] encoder.transmit busy -> Slot B1 [1/4] TX-O uebersprungen
[OMNI-CQ] encoder.transmit busy -> Slot B2 [1/4] TX-E uebersprungen
[OMNI-CQ] encoder.transmit busy -> Slot B1 [1/4] TX-O uebersprungen
[OMNI-CQ-UI] Stop (manual_halt)
```

→ **3× Pos 1 busy hintereinander, deterministisch reproduzierbar.**

### Issue A — Display-Zeit ist Wall-Time (kosmetisch)

`04:26:44` statt `04:26:45` (FT8 Slot-Boundary).

---

## 3. Wurzel-Analyse (R1-bestaetigt)

### 3.1 Encoder-Throughput-Race (Hauptursache)

R1's Diagnose (`prompts/p5_omni_pattern_fix3_r1.md` §A):

- FT8 12.64s Audio + 1.3s FlexRadio-Buffer-Drain + PTT-Off + Thread-Jitter
- `_is_transmitting=False` faellt bei **`:42.8-:44.5`** (12.8-14.5s nach Slot-Start)
- Pos 1 Slot bei `:45.0` → Race-Window `0.5-2.2s`
- In Praxis (FlexRadio Buffer-Drain + Jitter): **Window oft < 1s** → 100% busy

R1's H-D2: Drift-Guard greift bei OMNI **nicht** (cycle_start kommt fruh
genug). Der Bug ist **rein das Audio-Drain-Window** zwischen Pos 0 TX-Ende
und Pos 1 cycle_start.

### 3.2 Pos 4 RX-E fehlt + `:44 [O] Horche` — R1's Diagnose

R1 vermutet **Display-Bug durch Wall-Time** (`time.time()` statt
Slot-Boundary). Wenn `add_listening` 0.5-1s nach Slot-Boundary aufgerufen
wird, zeigt der Eintrag eine „verschobene" Zeit. Mike erwartet `:30`,
sieht `:31` oder so → wirkt wie „fehlt".

→ **Issue A Fix loest beide Phaenomene mit** (Slot-Boundary statt
Wall-Time).

→ AC-B7 verifiziert das (siehe §5).

### 3.3 V3-§8 Out-of-Scope (P4-V5) — Kippung

R1 §B: Encoder-Queue-Verbot **kippen** (begruendet durch Field-Test-
Evidence). Andere Verbote bleiben (Frequenz-Recheck, qso_state-Aenderungen,
Listener-Pfad, Diversity, Auto-Hunt, AP-Lite).

---

## 4. Loesung — Variante A (Encoder-Queue mit Pending-Verfall)

### 4.1 Code-Diff `core/encoder.py`

#### 4.1.1 Konstruktor (`__init__`, ~Z. 75-77)

```python
# bestehend:
self._audio_started = False
self._replace_message: str | None = None
self._replace_lock = threading.Lock()

# NEU dazu:
# P5.OMNI-PATTERN-FIX-3 (v0.96.2): Pending-TX-Queue fuer OMNI-konsekutive
# TX-Slots. Wenn transmit() bei laufendem TX gerufen wird (Pos 1 nach Pos 0
# bei FT8 immer der Fall — Audio-Drain 12.8-14.5s, Pos 1 bei :45 hat oft
# < 1s Race-Window), wird der naechste Job gequeueet statt return False.
# Worker-Finally konsumiert Pending direkt → naechster TX startet ohne
# neuen Thread-Schwung.
# _pending_tx: Tupel (message, tx_even, audio_freq_hz) oder None.
# _pending_queued_at: Wall-Time-Timestamp der Pending-Einreihung — fuer
#                     Verfall-Schwelle (1.5 * cycle_duration, R1-bestaetigt).
# Beide unter _replace_lock geschuetzt (R1-KRITISCH gegen Race).
self._pending_tx: tuple[str, bool | None, int | None] | None = None
self._pending_queued_at: float = 0.0
```

#### 4.1.2 `transmit()` (~Z. 178-212)

```python
def transmit(self, message: str, *,
             tx_even: bool | None = None,
             audio_freq_hz: int | None = None) -> bool:
    """FT8-Nachricht encoden und zum naechsten Zyklusbeginn senden.

    Atomare API (P4.OMNI-NEUBAU C3): tx_even und audio_freq_hz werden
    UNTER Lock gesetzt, dann startet der Worker. Verhindert Race wenn
    zwei Aufrufer parallel transmit() rufen oder Setter und Start
    nicht atomar koppeln (Encoder-Worker liest tx_even in
    _next_slot_boundary).

    Returns True wenn Worker gestartet ODER Pending gequeueet wurde
    (P5.OMNI-PATTERN-FIX-3: Pending-Konsum im Worker-Finally bedient
    den naechsten Slot-TX). Bestehende Aufrufer ohne kwargs
    (mw_qso._on_send_message) ignorieren das Return — Verhalten
    kompatibel.

    Pending-Verhalten:
    - Aufruf bei laufendem TX → Pending-Queue
    - Worker-finally checkt Pending → konsumiert wenn Ziel-Slot noch
      erreichbar (target_slot - queued_at < 1.5 * cycle_duration)
    - Sonst Pending-Verfall mit Log-Warning
    """
    # v0.80 Race-Fix (R1-Final-Review): alten TX-Thread sauber beenden,
    # bevor neuer startet. Sonst kann das finally des alten Threads
    # _is_transmitting=False setzen NACHDEM der neue Thread True gesetzt
    # hat → State desynchronisiert, weitere abort()-Aufrufe wirkungslos.
    if (self._tx_thread is not None
            and self._tx_thread.is_alive()
            and threading.current_thread() is not self._tx_thread):
        self._tx_thread.join(timeout=0.5)
    with self._replace_lock:
        if self._is_transmitting:
            # P5.OMNI-PATTERN-FIX-3: statt return False → Pending queuen.
            # Wenn bereits Pending vorhanden, ueberschreiben (letzter
            # Aufrufer gewinnt — analog tx_even-Setter "letzter setzt").
            self._pending_tx = (message, tx_even, audio_freq_hz)
            self._pending_queued_at = time.time()
            return True
        if tx_even is not None:
            self.tx_even = tx_even
        if audio_freq_hz is not None:
            self.audio_freq_hz = audio_freq_hz
    self._tx_thread = threading.Thread(
        target=self._tx_worker, args=(message,), daemon=True
    )
    self._tx_thread.start()
    return True
```

#### 4.1.3 `_tx_worker()` (Z. 214-233 ERSETZEN, neue Methoden danach einfuegen)

```python
def _tx_worker(self, message: str):
    """TX-Worker: Timing → PTT → Audio via VITA-49 → PTT off.

    P5.OMNI-PATTERN-FIX-3 (v0.96.2): Pending-Konsum im Loop nach
    Single-Pass. Wenn Pending gequeueet wurde waehrend Worker lief,
    wird er hier direkt re-getriggert (kein neuer Thread). Verfall
    wenn Ziel-Slot > 1.5 * cycle_duration in der Vergangenheit.

    Abort-Schutz: vor Re-Trigger Pruefung _abort_event.is_set() —
    sonst wuerde _run_one_tx_pass den abort cleared (F1-KRITISCH-Fix).
    """
    # Ausgelagerte Single-Pass-Logik
    self._run_one_tx_pass(message)

    # P5.OMNI-PATTERN-FIX-3: Pending-Konsum-Loop
    # Eigene Iteration statt Rekursion → Stack-sicher bei mehreren
    # konsekutiven Pendings (theoretisch nur 1 erwartet, aber sicher).
    while True:
        with self._replace_lock:
            pending = self._pending_tx
            queued_at = self._pending_queued_at
            self._pending_tx = None
            self._pending_queued_at = 0.0
        if pending is None:
            return
        # F1-KRITISCH-Fix: abort-Check VOR Re-Trigger.
        # _run_one_tx_pass cleart _abort_event und setzt
        # _is_transmitting=True — wuerde abort() ueberschreiben.
        # Wenn abort() zwischen Pass-1 und Pending-Konsum gefeuert hat,
        # MUESSEN wir hier rausspringen ohne Re-Trigger.
        if self._abort_event.is_set():
            print("[Encoder] Pending verworfen (abort waehrend Loop)")
            return
        msg, p_tx_even, p_audio_hz = pending
        # Verfall-Schwelle: ist Ziel-Slot noch erreichbar?
        # _SLOT in Sekunden. Bei FT8 = 15s, Schwelle = 22.5s.
        _SLOT = {"FT8": 15.0, "FT4": 7.5, "FT2": 3.8}.get(self._mode, 15.0)
        target_slot = self._compute_target_slot(p_tx_even, _SLOT)
        if target_slot - queued_at > _SLOT * 1.5:
            print(f"[Encoder] Pending TX verfallen "
                  f"(target={target_slot:.1f}, queued_at={queued_at:.1f}, "
                  f"diff={target_slot - queued_at:.1f}s > {_SLOT * 1.5:.1f}s)")
            return
        # Re-Trigger: Setter unter Lock, dann _run_one_tx_pass
        with self._replace_lock:
            if p_tx_even is not None:
                self.tx_even = p_tx_even
            if p_audio_hz is not None:
                self.audio_freq_hz = p_audio_hz
        self._run_one_tx_pass(msg)
        # Loop pruft erneut auf Pending (sehr seltener Fall — z.B.
        # 3+ konsekutive transmit-Aufrufe waehrend Worker laeuft).

def _run_one_tx_pass(self, message: str) -> None:
    """Single-Pass TX (vorher inline in _tx_worker).

    P5.OMNI-PATTERN-FIX-3: ausgelagert damit Pending-Konsum im
    _tx_worker-Loop denselben Pfad nutzt.
    """
    self._is_transmitting = True
    # v0.80 Fix A2: Event vor jedem TX zuruecksetzen.
    self._abort_event.clear()
    # P1.9 Fix (v0.95.3): Replace-State pro TX-Zyklus zuruecksetzen.
    self._audio_started = False
    with self._replace_lock:
        self._replace_message = None
    try:
        self._tx_worker_inner(message)
    finally:
        self._is_transmitting = False
        self._audio_started = False

def _compute_target_slot(self, tx_even: bool | None, slot_dur: float) -> float:
    """Naechster passender Slot-Start als Wall-Time.

    Spiegelt _next_slot_boundary, aber _SLOT extern uebergeben.
    Liefert immer einen Slot-Start in der Zukunft (oder current Slot
    wenn cycle_pos < 0.5s). Bei tx_even=None: naechster beliebiger Slot.
    """
    now = time.time()
    cycle_num = int(now / slot_dur)
    cycle_pos = now % slot_dur
    is_even = (cycle_num % 2 == 0)
    if tx_even is None:
        # Naechster beliebiger Slot
        if cycle_pos < 0.5:
            return float(cycle_num * slot_dur)
        return float((cycle_num + 1) * slot_dur)
    if is_even == tx_even and cycle_pos < 0.5:
        return float(cycle_num * slot_dur)
    next_num = cycle_num + 1
    next_boundary = float(next_num * slot_dur)
    if (next_num % 2 == 0) != tx_even:
        next_boundary += slot_dur
    return next_boundary
```

**Note zur Architektur:** `_run_one_tx_pass` ist eine Refactoring-
Extraktion, der Inhalt ist 1:1 das was vorher im `_tx_worker` stand
(Z. 222-233). Damit wird der Pending-Loop sauber implementiert ohne
Rekursion.

### 4.2 Issue A Fix `ui/main_window.py:760`

```python
# bestehend:
@Slot(str, bool, bool)
def _on_omni_slot_action(self, label: str, is_tx: bool, target_even: bool):
    if not is_tx:
        self.qso_panel.add_listening(time.time(), target_even)

# NEU:
@Slot(str, bool, bool)
def _on_omni_slot_action(self, label: str, is_tx: bool, target_even: bool):
    if not is_tx:
        # P5.OMNI-PATTERN-FIX-3 (v0.96.2): Slot-Boundary statt Wall-Time.
        # GUI-Latency / Qt-Queue koennen 100-400ms nach echter Slot-
        # Boundary einschlagen → time.time() wuerde z.B. 04:26:30.4 zeigen.
        # floor(now / cycle_duration) * cycle_duration gibt :30.0 sauber.
        slot_dur = self.timer.cycle_duration
        ts = time.time()
        slot_start = (ts // slot_dur) * slot_dur
        self.qso_panel.add_listening(slot_start, target_even)
```

**Edge Case:** `self.timer` ist immer initialisiert (constructor, vor
OMNI-Aktivierung). Bei Mode-Wechsel mid-OMNI wird `cycle_duration` per
`set_mode` aktualisiert. ✓

---

## 5. Akzeptanzkriterien

### Issue B (Encoder-Race-Fix)

| AC | Kriterium | Test |
|---|---|---|
| AC-B1 | Pos 1 (TX nach TX) sendet IMMER. `encoder.transmit` returnt bei busy nun `True` (Pending-Queue). | T1 |
| AC-B2 | `slot_action`-Emit fuer Pos 1 TX feuert (Pattern-Anzeige korrekt im qso_panel). | T2 |
| AC-B3 | Pattern Block 1 EXAKT (in qso_panel-Logbuch ueber 5 Slots): TX-E, TX-O, RX-E, RX-O, RX-E. | T3 + Field-Test |
| AC-B4 | Pattern Block 2 EXAKT: TX-O, TX-E, RX-O, RX-E, RX-O. | T4 + Field-Test |
| AC-B5 | Auto-Rollover Block 1 ↔ Block 2 nach 5 Slots. | T5 |
| AC-B6 | 10-Slot-Loop in qso_panel ohne Luecke, ohne Drift, ohne busy-Skips im Log. | Field-Test (Mike) |
| AC-B7 | Pos 4 RX-E (Block 1) wird IMMER im qso_panel angezeigt — durch Issue-A-Fix loest sich die "fehlt"-Beobachtung mit. | T6 |

### Issue A (Display-Slot-Boundary)

| AC | Kriterium | Test |
|---|---|---|
| AC-A1 | `add_listening`-Zeit zeigt Slot-Boundary `:00`/`:15`/`:30`/`:45` bei FT8. | T7 |
| AC-A2 | Bei FT4 (7.5s): Slot-Boundary jede 7.5s. Bei FT2 (3.8s): jede 3.8s. | T8 (parametrize) |
| AC-A3 | `cycle_duration`-Quelle: `self.timer.cycle_duration` (nicht hardcoded). | Code-Read |

### Encoder-Pending (Variante A Implementation)

| AC | Kriterium | Test |
|---|---|---|
| AC-E1 | `transmit()` returnt `True` wenn `_is_transmitting=True`, statt `False`. **Akademische Anmerkung:** OMNI's `_do_tx_slot` inkrementiert counter+slot_action SOFORT bei `ok==True`, unabhaengig davon ob Pending letztlich konsumiert wird. Bei seltenem Pending-Verfall ist counter um 1 zu hoch (akzeptiert, siehe R8). | T1 |
| AC-E2 | Pending-Tupel `(message, tx_even, audio_freq_hz)` korrekt gequeueet, `_pending_queued_at = time.time()` UNTER `_replace_lock`. | T1 |
| AC-E3 | Pending wird im Worker-Loop konsumiert wenn Ziel-Slot in `<= 1.5 * cycle_duration` erreichbar. | T9 |
| AC-E4 | Pending verfaellt wenn `target_slot - queued_at > 1.5 * cycle_duration`. Log-Warning. | T10 |
| AC-E5 | `_pending_tx` und `_pending_queued_at` werden UNTER `_replace_lock` gesetzt UND gelesen (R1-KRITISCH F1). | T11 (Race) |
| AC-E6 | Pending-Pfad ist re-entrant-sicher (mehrere Pendings hintereinander → Loop, nicht Rekursion). | T12 |
| AC-E7 | Wenn `abort()` ZWISCHEN Pass-1 und Pending-Re-Trigger gerufen wird, bricht Worker SOFORT ab (vor Re-Trigger via `_abort_event.is_set()`-Check), Pending wird verworfen mit Log-Warning, KEIN `_run_one_tx_pass` mehr. **F1-KRITISCH:** ohne diesen Check wuerde `_run_one_tx_pass` `_abort_event.clear()` + `_is_transmitting=True` setzen und damit abort() ueberschreiben. | T13 |

### Querschnitt

| AC | Kriterium | Test |
|---|---|---|
| AC-Z1 | Hardware-Garantie ANT1 unveraendert (encoder.transmit setzt zentral via radio.set_tx_antenna in `_tx_worker_inner` Z. 363). | Code-Read |
| AC-Z2 | Tests: alle 1020 weiter gruen. Erwartet: ~1031-1033 (13 neue Tests T1-T13). | `pytest tests/ -q` |
| AC-Z3 | Keine Aenderung an Out-of-Scope-Bereichen (siehe §10). | `git diff --stat` |
| AC-Z4 | APP_VERSION 0.96.1 → 0.96.2. | `git log -p main.py` |
| AC-Z5 | Pending wird NICHT re-triggert wenn `omni._active=False` zwischen Pending-Setzen und Worker-Finally. **Wichtig:** OMNI's `stop()` setzt `_active=False`, aber das hat KEINEN direkten Pfad zu Encoder-Pending — Encoder weiß nichts von OMNI. **Korrekt:** Pending wird im Encoder-Finally trotzdem konsumiert. Issue ist akademisch — wenn OMNI gestoppt wird, gibt es trotzdem 1× zusaetzlichen TX, der dann als verlorene RF in den Aether geht. **Akzeptiert** — alternativ koennte OMNI's `stop()` `encoder.cancel_pending()` rufen. **V3 entscheidet:** kein cancel_pending in P5 (KISS, Edge-Case-Akademisch). Mike kann das in P6 nachschieben wenn relevant. | Doku |
| AC-Z6 | Pending-Mechanismus wird NICHT von Normal-CQ-Pfad ausgenutzt (Normal-CQ macht nur 1 TX pro 2-Slot-Periode → kein Race-Trigger). | Code-Read mw_qso._on_send_message |

---

## 6. Field-Test-Plan (Mike, post-Compact)

| F | Test | Erwartung |
|---|---|---|
| F1 | App starten, Diversity aktiv, OMNI toggeln. | OMNI-Start-Log + CQ-Audiofreq-Set. |
| F2 | 10-Slot-Loop beobachten (2 vollstaendige Bloecke). | qso_panel zeigt: Block 1 TX-E :30, TX-O :45, RX-E :60, RX-O :75, RX-E :90, dann Block 2 TX-O :105, TX-E :120, RX-O :135, RX-E :150, RX-O :165. **Alle 10 Eintraege auf Slot-Boundaries.** |
| F3 | Log checken `~/.simpleft8/simpleft8.log`. | KEIN `encoder.transmit busy -> ...`-Log. KEIN `Pending TX verfallen`. |
| F4 | OMNI stoppen (manual_halt). | Stop-Log + Reset State. |
| F5 | OMNI nochmal starten, Bandwechsel mid-OMNI auf 20m FT8. | OMNI stoppt automatisch (band_change). Erneut starten → laeuft sauber. |
| F6 | OMNI starten, Modus auf FT4 wechseln. | OMNI stoppt (mode_change wenn auf Normal-Modus, sonst egal). Bei Diversity FT4 → OMNI sollte sauber mit FT4-Pattern laufen (7.5s Slots, Slot-Boundary `:30/:37.5/:45/:52.5`). |
| F7 | OMNI starten, eingehende Antwort auf CQ. | OMNI pausiert. QSO laeuft via qso_state. Nach QSO: OMNI resumed mit Block-Wahl (siehe Spec). |

**Bestanden wenn:** F1+F2+F3 sauber laufen ohne busy-Logs. F4-F7 sind
Regressionstests fuer bestehende OMNI-Mechanik (sollten unveraendert
funktionieren).

---

## 7. Test-Plan (Unit + Integration)

### Wirklich NEUE Tests (9 Stueck)

| ID | Name | File | AC | Beschreibung |
|---|---|---|---|---|
| T1 | `test_transmit_returns_true_when_busy_and_queues_pending` | tests/test_encoder_pending.py NEU | AC-B1, AC-E1, AC-E2 | `enc._is_transmitting=True`, `enc.transmit("TEST", tx_even=False, audio_freq_hz=475)` → assert `ok==True`, `enc._pending_tx == ("TEST", False, 475)`, `enc._pending_queued_at` gesetzt unter Lock. |
| T2N | `test_omni_pos1_counter_and_slot_action_when_pending_returns_true` | tests/test_omni_cq_signal.py ERWEITERN | AC-B1, AC-B2 | Mock-Encoder mit `transmit.return_value=True` (Pending-Pfad). OMNI `on_cycle_start` fuer Pos 1 (slot_index=1, Block 1, target_even=False) → erwarte `counter_changed.emit(0, 1)` UND `slot_action.emit(label, True, False)`. **Komplementaer zu existing Z. 401 Test (der Mock-False prueft).** |
| T7 | `test_add_listening_uses_slot_boundary_ft8` | tests/test_main_window_slot_boundary.py NEU | AC-A1 | Mock `time.time()=16004.5` (04:26:44.5), Mode=FT8 → erwarte `add_listening(15990.0, target_even)`. |
| T8 | `test_add_listening_uses_slot_boundary_all_modes` (parametrize FT4 + FT2) | tests/test_main_window_slot_boundary.py NEU | AC-A2 | FT4 (7.5s): time=16004.5 → expected = floor(16004.5/7.5)*7.5 = 16002.0. FT2 (3.8s): floor(16004.5/3.8)*3.8 = 15998.6. (parametrize → +2 Tests effektiv) |
| T9 | `test_pending_consumed_after_finally_when_target_slot_reachable` | tests/test_encoder_pending.py NEU | AC-E3 | Real-Worker mit `encode_message`-Mock + `radio`-Mock. Direkt nach `transmit("FIRST")` (Worker laeuft) ein zweites `transmit("SECOND", tx_even=...)` (Pending). `_tx_thread.join(timeout=2.0)` → assert `_pending_tx is None` UND `radio.send_audio` 2× gerufen. |
| T10 | `test_pending_dropped_if_target_slot_in_past_more_than_1_5_slots` | tests/test_encoder_pending.py NEU | AC-E4 | Direkter Test der Verfall-Schwelle: setze `enc._pending_tx = ("MSG", False, 1500)`, `enc._pending_queued_at = time.time() - 30.0`. Rufe Pending-Konsum-Pfad auf (z.B. via `_tx_worker_inner`-Helper-Mock). Erwarte print "Pending TX verfallen", kein zweites `_run_one_tx_pass`. |
| T11 | `test_pending_queued_at_set_under_lock` (F1-KRITISCH Race) | tests/test_encoder_pending.py NEU | AC-E5 | Zwei Threads rufen `transmit()` parallel mit `_is_transmitting=True`. Pruefe: `_pending_tx` und `_pending_queued_at` werden konsistent gesetzt (kein None/0.0-Mix). Test koennt nicht-deterministisch sein → mehrere Wiederholungen ODER threading-monkeypatch. |
| T12 | `test_pending_loop_handles_multiple_consecutive_pendings` | tests/test_encoder_pending.py NEU | AC-E6 | 3× konsekutive `transmit()` waehrend Worker laeuft (jeder ueberschreibt Pending → letzter gewinnt). Loop konsumiert nur den letzten, kein Stack-Overflow. Verifiziere durch `radio.send_audio.call_count == 2`. |
| T13 | `test_abort_during_pending_breaks_loop` (F1-KRITISCH) | tests/test_encoder_pending.py NEU | AC-E7 | Pending gequeueet, dann `enc.abort()` (setzt `_abort_event` + `_is_transmitting=False`) BEVOR Worker Pending konsumiert. Erwarte: Pending-Loop sieht `_abort_event.is_set()` → print "Pending verworfen (abort waehrend Loop)" → return. KEIN zweiter `_run_one_tx_pass`. |

### Existing Tests die GRUEN BLEIBEN (KEINE Migration noetig)

Cold-Start-Test (F2 + F3 + F4) hat bestaetigt:

- **Pattern-Coverage existing:** `tests/test_omni_cq_signal.py` Z. 109
  (Pos 0 TX-E), Z. 122 (Pos 1 TX-O), Z. 140 (Pos 2-4 RX inkl. Pos 4
  RX-E), Z. 160 (Block 1→2 Rollover), Z. 180 (Block 2 Pos 1 TX-E),
  Z. 195 (Block 2→1 Rollover), Z. 208 (15-Slot-Alternation). **Alle
  bleiben gruen.**
- **Existing busy-Test bleibt gruen:** Z. 401
  `test_encoder_busy_no_counter_no_slot_action_but_advance` setzt Mock
  `transmit.return_value=False` explizit. OMNI's `if not ok: log`-Branch
  existiert weiter — Test prueft den else-Pfad. Mit Variante A ist
  echter Encoder-False unmoeglich, aber Mock-False trifft trotzdem den
  Code-Pfad. **T2N ergaenzt komplementaer den Pending-Pfad.**
- **Encoder-Tests die `_is_transmitting=True` setzen** (test_modules.py
  Z. 710/2582/2648/2690/2823, test_p1_9_replace.py Z. 37/49) rufen
  `_tx_worker_inner` direkt — **Pending-Pfad nicht betroffen.**
- **Replace-Pfad-Test** (test_modules.py:2778-2799) macht `abort()` vor
  zweitem `transmit()` → `_is_transmitting=False` → **kein Pending,
  neuer Thread direkt.** Bleibt gruen.

### Erwartete Test-Bilanz

**1020 → ~1029 gruen** (+9 Tests effektiv: T1, T2N, T7, T8 als parametrize
+2, T9, T10, T11, T12, T13 = 9 effektive Test-Funktionen).

Falls Cold-Start-Test post-Compact zeigt dass T2N als parametrize gebaut
wird → +1-2 mehr. Toleranz ±2.

---

## 8. Atomare Commits-Plan (6 Commits)

| # | Commit | Files | Tests |
|---|---|---|---|
| C1 | `core/encoder.py: Pending-TX-Queue + Verfall + Abort-Schutz (P5)` | core/encoder.py | — |
| C2 | `tests/test_encoder_pending.py: Variante-A-Coverage (T1, T9-T13)` | tests/test_encoder_pending.py NEU | T1, T9, T10, T11, T12, T13 (6 Tests) |
| C3 | `ui/main_window.py: Slot-Boundary in add_listening (Issue A)` | ui/main_window.py | — |
| C4 | `tests/test_main_window_slot_boundary.py + tests/test_omni_cq_signal.py: T7+T8 (Issue A) + T2N (Pending-Counter)` | tests/test_main_window_slot_boundary.py NEU + tests/test_omni_cq_signal.py ERWEITERN | T7, T8 (parametrize +2), T2N (3 effektive Tests) |
| C5 | `main.py: APP_VERSION 0.96.1 → 0.96.2` | main.py:16 | — |
| C6 | `Doku: HISTORY + HANDOFF + CLAUDE + TODO + Memory` | HISTORY.md, HANDOFF.md, CLAUDE.md (Header), TODO.md, memory/project_p5_omni_pattern_fix3.md, MEMORY.md | — |

**Atomare Trennung:** C1+C2 isoliert testbar (encoder unit). C3+C4 isoliert
testbar (main_window unit + OMNI-Integration). C5 isoliert (Versions-Bump).
C6 reine Doku.

**Reihenfolge:** C1 → C2 → grun-Check → C3 → C4 → grun-Check → C5 → C6.

**Pre-Code-Pflicht (vor C1):**
1. `git status` / `git log --oneline | head -5` — Ausgangsstand verifizieren
2. Tests-Baseline: `QT_QPA_PLATFORM=offscreen ./venv/bin/python3 -m pytest tests/ -q` → 1020 erwartet
3. Wenn Baseline abweicht → STOP, Mike fragen

**Falls Final-R1 nach Code Findings hat:** zusaetzliche Fix-Commits
zwischen C5 und C6 (C5a, C5b, ...).

---

## 9. Out-of-Scope (kein Scope-Creep!)

- ❌ Frequenz-Recheck-Logik (V5-KISS bleibt)
- ❌ qso_state-State-Maschinen-Aenderungen
- ❌ Listener-Pfad in `mw_cycle.on_message_decoded`
- ❌ Diversity-Antennen-Switch
- ❌ Auto-Hunt-Coupling
- ❌ AP-Lite, OMNI-Stop-Reasons, btn_omni_cq-UI, Easter-Egg-Toggle (alles unveraendert)
- ❌ `omni.cancel_pending()` zur Stop-Synchronisation (AC-Z5 Edge-Case akademisch — bei P6 falls Mike Bedarf hat)

P5 ist NUR: TX-Throughput-Race fixen + Display-Slot-Boundary.

---

## 10. APP_VERSION-Plan

`v0.96.1 → v0.96.2` (Patch-Bump: Race-Fix + Display-Korrektur, kein
neues Feature).

`main.py` Konstante `APP_VERSION = "0.96.2"`.

---

## 11. Doku-Update Plan (C8)

### `HISTORY.md`

Eintrag am Ende:

```markdown
## 2026-05-10 v0.96.2 — P5.OMNI-PATTERN-FIX-3: Encoder-Pending-Queue + Slot-Boundary-Display

**Auslöser:** Field-Test 10.05.2026 ~06:30 UTC (v0.96.1) zeigte 2 Issues:
- Issue B (kritisch): Pos 1 (TX-nach-TX) IMMER busy (3× im Log
  reproduziert), Pattern halb tot.
- Issue A (kosmetisch): `add_listening`-Zeit zeigt Wall-Time
  (`time.time()`) statt UTC-Slot-Boundary.

**Wurzel Issue B (R1-bestaetigt):** FT8 12.64s Audio + 1.3s
FlexRadio-Buffer-Drain + PTT-Off + Thread-Jitter → `_is_transmitting=False`
faellt bei `:42.8-:44.5`. Pos 1 cycle_start :45 hat Race-Window 0-2s,
in Praxis < 1s → 100% busy.

**Loesung Variante A (R1-Empfehlung):** Encoder-Queue mit Pending-Verfall.
`transmit()` queut Pending statt `return False`. Worker-Finally konsumiert
Pending direkt. Verfall-Schwelle `1.5 * cycle_duration` (FT8: 22.5s).
`_pending_tx` + `_pending_queued_at` UNTER `_replace_lock` (R1-KRITISCH
gegen Race).

**Loesung Issue A:** `main_window.py:760` `add_listening(time.time(), ...)`
→ `add_listening((time.time() // cycle_dur) * cycle_dur, ...)`. Loest
gleichzeitig die Phaenomene "Pos 4 RX-E fehlt" und ":44 [O] Horche"
durch korrekte Slot-Boundary-Anzeige.

**Workflow:** V1 → V2 (Self-Review) → R1 (DeepSeek-Reasoner) → V3
(Compact-fest) → Mike-Freigabe → Code → Final-R1 → Field-Test. Plan-Files:
`prompts/p5_omni_pattern_fix3_*`.

**Atomare Commits:** C1 (encoder.py), C2 (test_encoder_pending.py), C3
(main_window.py), C4 (test_main_window_slot_boundary.py), C5/C6 (OMNI-
Tests), C7 (APP_VERSION), C8 (Doku).

**Tests:** 1020 → ~1031-1033 gruen (13 neue Tests T1-T13).

**APP_VERSION:** v0.96.1 → v0.96.2. Push pending bis Mike-Freigabe nach
Field-Test.

**R1-Blindspot-Lesson aktiviert:** Bei TX-TX-Konsekutiv-Plaenen MUSS R1
explizit nach Encoder-Throughput gefragt werden. Bei P4-V5 hatte R1 das
verpasst → Field-Test-Bug. P5-Prompt hat die Pflicht-Frage explizit
enthalten — R1 hat den Race korrekt diagnostiziert.
```

### `HANDOFF.md`

Stand-Block ersetzen mit:

```markdown
## Stand 2026-05-10 ~XX:YY UTC: P5.OMNI-PATTERN-FIX-3 ERLEDIGT, Field-Test pending

**Code:** v0.96.2 lokal commited (C1-C8). Push pending bis Mike-Freigabe.
**Tests:** ~1031-1033 gruen (13 neue T1-T13).
**Field-Test:** 7-Punkte-Plan (V3 §6) ausstehend, Mike startet App selbst.
**App:** gestoppt.
```

### `CLAUDE.md` (Header `Aktueller Stand`-Zeile)

```
**Aktueller Stand:** v0.96.2 P5.OMNI-PATTERN-FIX-3 — Encoder-Pending-Queue
+ Slot-Boundary-Display, Code fertig, Field-Test pending (10.05.2026).
Tests ~1031-1033 gruen.
```

### `TODO.md`

P5-Block raus, Field-Test als TOP. Push-Block aktualisiert.

### Memory-Updates

- `MEMORY.md`: P5-Eintrag von "AKTIV" auf "✅ ERLEDIGT — Field-Test pending"
- `project_p5_omni_pattern_fix3.md`: Status auf "Code fertig, Field-Test
  pending" + Final-Commit-Hashes nachreichen.

---

## 12. Naechste Schritte (post Mike-Freigabe)

1. **Compact** (Cold-Start-Test: jeder file:line in §1 + §4 per `Read`/`Grep`
   gegen aktuellen Code verifizieren).
2. **Code-Phase** in atomaren Commits C1-C8.
3. **Tests gruen-Check** nach jedem Code-Commit.
4. **Final-R1-Review** mit allen Diff-Files (R1 prueft Code).
5. **Field-Test mit Mike** (V3 §6, 7 Punkte).
6. **Doku-Update** (C8).
7. **Push** wenn Mike OK gibt — v0.95.16-0.96.2 + P2-Tool zusammen.

---

## 13. Risiko-Bewertung

| ID | Risiko | Wahrscheinlichkeit | Mitigation |
|---|---|---|---|
| R1 | Pending-Verfall schwellt aus (Worker > 1.5 Slots wegen Drift-Guard im Pending-Pfad). | Niedrig (R1 §D verifiziert, Audio + Drain < 14.5s, Schwelle 22.5s). | Falls Field-Test zeigt: Schwelle auf `2.0 * cycle_duration` (30s FT8) erhoehen. |
| R2 | `_pending_queued_at` Race trotz Lock. | Sehr niedrig (R1 + F1-Code-Diff explizit verifiziert). | T11-Test schuetzt. |
| R3 | OMNI-Stop waehrend Pending → 1× extra TX. | Mittel (akademisch — Mike merkt es nicht). | AC-Z5 dokumentiert. P6 falls relevant. |
| R4 | Issue A `cycle_duration` ist 0 oder None bei early init. | Sehr niedrig (`self.timer = FT8Timer(settings.mode)` in main_window.py:121 vor OMNI). | Code-Read verifiziert (Cold-Start-Test). |
| R5 | ~~Bestehende encoder-Tests brechen.~~ **F2-Cold-Start: KEINE Migration noetig.** Bestehende Tests rufen `_tx_worker_inner` direkt + Replace-Pfad macht `abort()` vor 2. transmit. | Niedrig | Tests-Baseline-Check vor C1, falls unerwartete Brueche → STOP. |
| R6 | Variante A loest Pos 1 doch nicht — Worker > 1.5s nach Pos 0 Audio. | Niedrig (R1 §D Edge-Case-Analyse zeigt funktioniert). | Field-Test, falls fehlschlaegt → Variante B (Mid-Cycle-Pretrigger) als Fallback. |
| R7 | Falls H-Pos-4-RX-E + H-`:44 [O] Horche` doch NICHT durch Issue-A-Fix geloest werden → AC-B7 Test schlaegt fehl. | Mittel (R1's Display-Bug-Hypothese ist plausibel aber unverifiziert). | Field-Test verifiziert. Falls F2/F6 zeigen Pos 4 fehlt weiter: Folge-Workflow P6 fuer den UI-Bug. |
| R8 | Counter-Inkrement bei Pending-Verfall: OMNI's `_do_tx_slot` inkrementiert counter+slot_action SOFORT bei `ok==True`, auch wenn Pending letztlich verfaellt. counter zeigt 1 zu viel. | Niedrig (Pending-Verfall ist Edge-Case bei Drift-Guard im Pending-Pfad — selten). | Akademisch akzeptiert, in V3 §5 AC-E1 Anmerkung. P6 falls Mike das stoert. Alternative: counter erst bei `tx_started.emit` inkrementieren (komplex, KISS-verletzend). |
| R9 | F1-Abort-Race-Fix uebersehen. | Niedrig (in V3 §4.1.3 explizit eingebaut + T13 testet). | Code-Review C1 muss `if self._abort_event.is_set(): return` im Pending-Loop verifizieren. |

---

## 14. Plan-Files Verzeichnis

- ✅ `prompts/p5_omni_pattern_fix3_diagnose.md` (Diagnose, 06:41)
- ✅ `prompts/p5_omni_pattern_fix3_v1.md` (V1)
- ✅ `prompts/p5_omni_pattern_fix3_v2.md` (V2 Self-Review)
- ✅ `prompts/p5_omni_pattern_fix3_r1_prompt.md` (R1-Brief)
- ✅ `prompts/p5_omni_pattern_fix3_r1.md` (R1-Output, 7K Tokens)
- ✅ `prompts/p5_omni_pattern_fix3_v3.md` (DIESE DATEI, Compact-fest)
- 🔜 `prompts/p5_omni_pattern_fix3_final_r1_prompt.md` (Final-R1-Brief, post-Code)
- 🔜 `prompts/p5_omni_pattern_fix3_final_r1.md` (Final-R1-Output)

---

**Ende V3. Wartet auf Mike-Freigabe.**
