# P4.OMNI-NEUBAU — V1 Plan

**Datum:** 2026-05-09 (Abend)
**Auslöser:** 4 Fehlversuche v0.95.22-25 (P1.OMNI-START → P2.OMNI-REDESIGN
→ P2.OMNI-PATTERN-FIX → P3.OMNI-PATTERN-FIX-2). Mike-Field-Test v0.95.25
zeigt: OMNI-Pattern völlig kaputt, 1 TX alle ~75 s, keine Block-Struktur
mehr erkennbar. Wurzel: OMNI in `qso_state.cq_mode`-Pfad reingehackt
(GUI-Tick / cycle_tick / QTimer alle abhängig vom GUI-Thread, der
während Decoder-Run blockiert).

**Vision (Mike, 09.05.2026 Abend):** OMNI-CQ ist **eigene Struktur**,
NICHT Variante des Normal-CQ-Modus. Eigenes Modul, eigener Worker-Thread
mit absolut-UTC-Slot-Boundaries (analog `core/encoder.py:_tx_worker`).
Bei eingehendem Anruf: Übergabe an gemeinsamen QSO-Pfad (gleiche
state-machine wie Normal-Modus / Hunt-Klick).

**Verbindliche Spec:** `memory/project_omni_cq_spec.md` (Mike-Dialog).

---

## 0. Schritt 0 — Code-Verifikation (erledigt)

### Existierende OMNI-Reste (alle aus v0.95.22-25, müssen raus oder umgebaut werden)

| File | Code | Was es tut | Schicksal |
|---|---|---|---|
| `core/omni_tx.py` | `OmniTX` Klasse (~250 Z) | Slot-Filter ohne Worker-Thread, externes Polling über `should_tx()` / `advance()` | **KOMPLETT RAUS** oder Pattern-Konstanten + Block-Wahl-Helper extrahieren. Kein Worker-Thread → unbrauchbar für Neubau. |
| `core/qso_state.py:177` `_send_cq` | `_omni_skip_state_change`-Flag-Pattern | Listener-skip bei OMNI-RX-Slot | **RAUS** (war Workaround für falsche Architektur) |
| `core/qso_state.py` `_was_pretriggered`-Flag | Pretrigger-Schutz on_cycle_end CQ_WAIT | Verhindert doppelten _send_cq | **RAUS** |
| `core/encoder.py` `_pending_tx_message` Queue + Outer-Loop in `_tx_worker` | OMNI-Pretrigger-Helper | Replace verdrängt Queue | **RAUS** (war OMNI-Pretrigger-spezifisch). Encoder zurück zu SKIP-bei-aktiv. |
| `ui/main_window.py:226-244` `_omni_was_active_pre_qso`, `_omni_pretriggered`, `_omni_pretrigger_timer` | QTimer + Flags | Pretrigger-Schedule | **RAUS** — kein QTimer mehr nötig |
| `ui/main_window.py:700-740` `_on_btn_omni_cq_toggled` | Button-Toggle ruft `start_with_parity_for_next_slot` + `qso_sm.start_cq()` | Aktivierung mischt OMNI mit Normal-CQ | **UMGEBAUT** — ruft `omni_cq.start()`, kein `qso_sm.start_cq()` |
| `ui/main_window.py:742-776` `_on_omni_stopped` | Stop-Reason-Cleanup | Resettet Pretrigger-Flags + Button-State | **VEREINFACHT** — nur Button + UI-Cleanup |
| `ui/mw_cycle.py:586-700` `_omni_pretrigger_*` | Pretrigger-Check + Fire-Impl + advance() | Cycle-Tick-getriebener OMNI | **KOMPLETT RAUS** — OMNI hat eigenen Worker-Thread |
| `ui/mw_qso.py:34-66` `_pause_omni_if_active`, `_maybe_resume_omni` | Pause/Resume Helpers | Bei QSO-Entry pausieren, bei QSO-Ende resumen mit Block-Wahl | **UMGEBAUT** auf neue OMNI-API (`omni_cq.pause()` / `omni_cq.resume_after_qso(last_qso_was_even)`) |
| `ui/mw_qso.py:340-410` OMNI-Bypass in `_on_send_message` | Slot-Filter-Logik im Send-Pfad | Skipt TX bei OMNI-RX-Slot | **RAUS** — OMNI ruft `encoder.transmit()` direkt, nicht über `send_message`-Signal |
| `ui/mw_qso.py:269` HALT-Branch | Stoppt OMNI bei manual_halt | OK | **BLEIBT** (anpassen API) |

### Existierende Hunt-Pipeline (BLEIBT — wird von OMNI mitgenutzt)

| Code | Funktion | Verwendung durch OMNI |
|---|---|---|
| `core/qso_state.py:270` `start_qso(call, grid, freq, their_snr)` | QSO mit Station starten — gleicher Eingang wie Hunt-Klick | OMNI ruft das bei eingehender CQ-Antwort auf |
| `core/qso_state.py:519` `on_message_received(msg)` | Hauptverarbeitung decoded messages | OMNI nutzt das NICHT direkt — eigener Listener-Pfad (siehe §4.5) |
| Hunt-States: WAIT_REPORT, WAIT_RR73, WAIT_73, TX_REPORT, TX_RR73, TX_73, TX_73_COURTESY, TX_CALL | State-Machine nach `start_qso` | OMNI delegiert komplett |
| `core/qso_state.py:163` `start_cq` / `:171` `stop_cq` | Normal-CQ Modus | **OMNI nutzt das NICHT** — `cq_mode` bleibt für Normal-CQ exclusive |

### Existierende Helper (BLEIBT — werden wiederverwendet)

| Code | Funktion | Verwendung |
|---|---|---|
| `core/encoder.py:254` `_next_slot_boundary()` | UTC-absolute Slot-Boundary mit `tx_even`-Filter | **VORBILD** für OMNI-Worker-Sleep-Math |
| `core/encoder.py:189` `transmit(message)` | TX-API, thread-safe | OMNI ruft direkt auf (statt über `send_message`-Signal) |
| `core/encoder.py:25` `TARGET_TX_OFFSET = -0.8` | FlexRadio-TX-Buffer-Kompensation | OMNI braucht das NICHT direkt — Encoder kümmert sich, OMNI muss nur früh genug `transmit()` aufrufen |
| `core/timing.py:CYCLE_DURATIONS` | `{FT8:15.0, FT4:7.5, FT2:3.8}` | OMNI-Worker liest das |
| `core/diversity.py:190` `get_free_cq_freq()` | Sticky-Gap-Algo, returnt CQ-Frequenz | OMNI ruft das alle 4 Blöcke auf |
| `core/diversity.py:144` `_measure_gap_around(bin_idx)` | Refresht `_current_gap_width_hz` nach Sticky-Hit | wird intern von `get_free_cq_freq` aufgerufen |
| `radio.set_tx_antenna("ANT1")` zentral in `Encoder.transmit()` | Hardware-Garantie ANT1 | OMNI braucht keinen Extra-Check |

### Stand am Ende von Schritt 0

- ✅ Existing OMNI-Code lokalisiert (~10 Stellen, alle aus v0.95.22-25)
- ✅ Encoder-Worker-Pattern verstanden (Vorbild für OMNI-Worker)
- ✅ Hunt-Pipeline-Eingang identifiziert (`start_qso`)
- ✅ CQ-Frequenz-Sticky-Algo lokalisiert (`diversity.get_free_cq_freq`)
- ✅ Hardware-Garantie ANT1 zentral abgesichert
- ✅ Memory-Spec liegt unter `memory/project_omni_cq_spec.md`

---

## 1. Konzept (kurz)

5-Slot-Pattern, eigener Worker-Thread, sticky Audiofrequenz, Übergabe an
Hunt-Pipeline bei Antwort. Spec siehe Memory.

```
Block 1 (Even-First):  TX-E  TX-O  RX-E  RX-O  RX-E
Block 2 (Odd-First):   TX-O  TX-E  RX-O  RX-E  RX-O

Wechsel: automatisch nach 5 Slots (slot_index 4 → 0). Block 1 → 2 → 1 → 2 ...
Nach QSO: Block-Wahl nach letztem QSO-Slot. QSO endet auf Even → Block 2.
          QSO endet auf Odd → Block 1. IMMER ab Pos 0.
App-Start: nächsten freien Slot prüfen → passenden Block ab Pos 0.
```

**Frequenz:**
- Initial beim Start: `diversity.get_free_cq_freq()` (Sticky-Gap-Algo)
- Bleibt fest während Block läuft
- Bleibt fest während QSO läuft
- Alle **4 Blöcke (~5 Min)** Re-Check via `get_free_cq_freq()` —
  Algo entscheidet selbst (Sticky bleibt wenn frei, wechselt wenn voll)

**Übergabe an Hunt-Pipeline:**
- OMNI-Worker dekodiert nicht selbst — er HÖRT nur in RX-Slots
- Bei eingehender Antwort an unsere CQ → Listener (mw_qso oder mw_cycle)
  erkennt „Antwort an mich" (`msg.target == my_call`)
- Listener ruft: `omni_cq.pause()` + `qso_state.start_qso(msg.caller, ...)` 
- Nach QSO: Listener ruft `omni_cq.resume_after_qso(last_qso_was_even)`

---

## 2. Neues Modul `core/omni_cq.py`

### 2.1 Klassen-Aufbau

```python
class OmniCQ(QObject):
    """OMNI-CQ Worker — eigene Slot-getaktete CQ-Pipeline.

    Sendet CQ abwechselnd auf Even+Odd in 5-Slot-Pattern (TX-TX-RX-RX-RX).
    Eigener Worker-Thread mit absolut-UTC-Boundaries — kein cycle_tick,
    kein QTimer, kein GUI-Thread-Polling.

    Bei eingehender Antwort: pause() + Übergabe an qso_state.start_qso().
    Nach QSO-Ende: resume_after_qso(last_qso_was_even) wählt passenden
    Block + startet ab Pos 0.
    """

    # Signals (alle GUI-thread-safe via Qt.AutoConnection)
    omni_started = Signal()                  # OMNI ist live
    omni_stopped = Signal(str)               # reason: manual_halt | band_change
                                              # | mode_change | totmann_expired
    slot_action = Signal(str, bool, bool)    # (label, is_tx, target_even)
                                              # — für QSO-Panel "Horche..."/"CQ"
    cq_freq_changed = Signal(int)            # neue Audiofrequenz (Hz)
    counter_changed = Signal(int, int)       # (cq_even_count, cq_odd_count)
                                              # — für Statusbar Ω

    # Konstanten
    _TX_PATTERN = (True, True, False, False, False)   # 5 Slots
    _BLOCKS_PER_FREQ_RECHECK = 4                       # alle 4 Blöcke (~5 Min FT8)
    _OMNI_TX_PRELEAD_S = 1.5                           # Worker wakes 1.5s vor Boundary

    def __init__(
        self,
        encoder,                  # core.encoder.Encoder
        diversity_ctrl,           # core.diversity.DiversityController
        timer,                    # core.timing.FT8Timer
        my_call: str,
        my_grid: str,
    ):
        super().__init__()
        self._encoder = encoder
        self._diversity = diversity_ctrl
        self._timer = timer
        self._my_call = my_call
        self._my_grid = my_grid

        # Lifecycle
        self._thread: threading.Thread | None = None
        self._running = False
        self._stop_event = threading.Event()  # cancelable sleep
        self._lock = threading.RLock()        # State-Mutation

        # Pattern-State
        self._slot_index = 0       # 0..4
        self._block = 1            # 1=Even-First, 2=Odd-First
        self._block_count = 0      # für Frequenz-Recheck (alle 4 Blöcke)

        # Pause-State (während QSO)
        self._paused = False

        # Counters (für Statusbar)
        self._cq_even_count = 0
        self._cq_odd_count = 0

        # Audiofrequenz (sticky, gesetzt beim ersten TX)
        self._cq_audio_hz: int | None = None

    # ── Public API ──────────────────────────────────────────────────
    def start(self) -> None: ...
    def stop(self, reason: str) -> None: ...
    def pause(self) -> None: ...
    def resume_after_qso(self, last_qso_was_even: bool) -> None: ...
    def is_active(self) -> bool: ...
    def is_paused(self) -> bool: ...

    # ── Internal: Worker-Loop ───────────────────────────────────────
    def _worker_loop(self) -> None: ...
    def _next_slot_action(self) -> tuple[bool, bool]: ...   # (is_tx, target_even)
    def _maybe_recheck_freq(self) -> None: ...
    def _slot_label(self, is_tx: bool, target_even: bool) -> str: ...
```

### 2.2 Worker-Loop (Pseudo-Code)

```python
def _worker_loop(self):
    SLOT = self._timer.CYCLE_DURATIONS[self._timer.mode]
    PRELEAD = self._OMNI_TX_PRELEAD_S   # 1.5s

    while self._running:
        # 1. Pattern-Slot bestimmen (TX/RX, Parität)
        is_tx, target_even = self._next_slot_action()

        # 2. Nächste passende Slot-Boundary (UTC-absolute)
        #    is_tx=True  → boundary mit gewünschter Parität (target_even)
        #    is_tx=False → einfach nächste Boundary (RX hört auf jeder)
        next_boundary = self._compute_next_boundary(target_even if is_tx else None)

        # 3. Sleep bis (boundary - PRELEAD), cancelable über _stop_event
        sleep_dur = (next_boundary - PRELEAD) - time.time()
        if sleep_dur > 0:
            stopped = self._stop_event.wait(timeout=sleep_dur)
            if stopped:
                return  # stop() oder pause() wurde aufgerufen

        # 4. Während wir geschlafen haben — pausiert oder gestoppt?
        with self._lock:
            if not self._running:
                return
            if self._paused:
                # QSO läuft — Worker schläft bis resume_after_qso() ihn weckt.
                # resume_after_qso() ruft start() neu mit Block-Wahl + slot_index=0.
                return

        # 5. Slot-Aktion ausführen
        if is_tx:
            # Sticky-Frequenz beim ersten TX setzen
            if self._cq_audio_hz is None:
                self._cq_audio_hz = self._diversity.get_free_cq_freq() or 1500
                self.cq_freq_changed.emit(self._cq_audio_hz)

            # Encoder-Parameter setzen + transmit (thread-safe)
            self._encoder.audio_freq_hz = self._cq_audio_hz
            self._encoder.tx_even = target_even
            cq_msg = f"CQ {self._my_call} {self._my_grid}"
            self._encoder.transmit(cq_msg)

            # Counter
            with self._lock:
                if target_even:
                    self._cq_even_count += 1
                else:
                    self._cq_odd_count += 1
            self.counter_changed.emit(self._cq_even_count, self._cq_odd_count)
            self.slot_action.emit(self._slot_label(True, target_even), True, target_even)
        else:
            # RX-Slot — nichts zu tun, Decoder läuft eh.
            # Nur Signal für QSO-Panel (Mike's Wunsch v0.95.25: „Horche..."-Anzeige)
            self.slot_action.emit(self._slot_label(False, target_even), False, False)

        # 6. State weiterschieben
        with self._lock:
            self._slot_index = (self._slot_index + 1) % 5
            if self._slot_index == 0:
                self._block = 2 if self._block == 1 else 1
                self._block_count += 1
                self._maybe_recheck_freq()  # alle 4 Blöcke

        # 7. Sleep kurz bis nach Slot-Boundary, dann nächster Loop-Durchgang
        # (verhindert dass wir den selben Slot zweimal ausführen)
        time.sleep(0.5)
```

### 2.3 `_compute_next_boundary(target_even: bool | None)`

```python
def _compute_next_boundary(self, target_even: bool | None) -> float:
    """Nächste UTC-Slot-Boundary, ggf. mit Parität-Filter.
    Analog core/encoder.py:_next_slot_boundary, aber pro Aufruf neu berechnet
    (kein State im Worker — Boundary-Math ist stateless)."""
    SLOT = self._timer.CYCLE_DURATIONS[self._timer.mode]
    now = time.time()
    cycle_num = int(now / SLOT)
    cycle_pos = now % SLOT
    is_even = (cycle_num % 2 == 0)

    if target_even is None:
        # RX-Slot: einfach nächste Boundary
        return float((cycle_num + 1) * SLOT)

    # TX-Slot mit Parität
    if is_even == target_even and cycle_pos < 0.5:
        # Aktueller Slot passt + wir sind ganz früh dran
        return float(cycle_num * SLOT)
    next_num = cycle_num + 1
    next_boundary = float(next_num * SLOT)
    if (next_num % 2 == 0) != target_even:
        next_boundary += SLOT
    return next_boundary
```

### 2.4 `_next_slot_action()`

```python
def _next_slot_action(self) -> tuple[bool, bool]:
    """(is_tx, target_even) für aktuellen _slot_index + _block.
    Wird VOR dem Sleep aufgerufen, damit wir die richtige Boundary wählen."""
    with self._lock:
        is_tx = self._TX_PATTERN[self._slot_index]
        if not is_tx:
            return False, False  # Parität egal bei RX

        # Block 1 (Even-First):  Pos 0=Even-TX, Pos 1=Odd-TX
        # Block 2 (Odd-First):   Pos 0=Odd-TX,  Pos 1=Even-TX
        if self._block == 1:
            target_even = (self._slot_index == 0)
        else:
            target_even = (self._slot_index == 1)
        return True, target_even
```

### 2.5 `start()` / `stop()` / `pause()` / `resume_after_qso()`

```python
def start(self, next_is_even: bool | None = None) -> None:
    """OMNI starten. next_is_even bestimmt Block (App-Start oder Resume).
    None = wird intern aus timing.is_even_cycle berechnet."""
    with self._lock:
        if self._running:
            return  # idempotent

        if next_is_even is None:
            # is_even_cycle returnt aktuelle Parität → next ist invertiert
            next_is_even = not self._timer.is_even_cycle()

        self._block = 1 if next_is_even else 2
        self._slot_index = 0
        self._block_count = 0
        self._cq_even_count = 0
        self._cq_odd_count = 0
        self._paused = False
        self._cq_audio_hz = None  # wird beim ersten TX gesetzt
        self._stop_event.clear()
        self._running = True

    self._thread = threading.Thread(target=self._worker_loop, daemon=True)
    self._thread.start()
    self.omni_started.emit()
    logger.info(f"[OMNI-CQ] Start (next_is_even={next_is_even} → Block {self._block})")

def stop(self, reason: str) -> None:
    """OMNI sofort beenden. Worker-Thread läuft aus (max 0.5s)."""
    with self._lock:
        if not self._running:
            return
        self._running = False
        self._paused = False
    self._stop_event.set()
    if self._thread is not None:
        self._thread.join(timeout=2.0)
        self._thread = None
    self.omni_stopped.emit(reason)
    logger.info(f"[OMNI-CQ] Stop (reason={reason})")

def pause(self) -> None:
    """OMNI pausieren (QSO startet). Worker läuft aus, _slot_index friert ein."""
    with self._lock:
        if not self._running:
            return
        self._paused = True
    self._stop_event.set()  # Worker aus Sleep wecken → er sieht _paused=True → return
    if self._thread is not None:
        self._thread.join(timeout=2.0)
        self._thread = None
    logger.info("[OMNI-CQ] Pause (QSO läuft)")

def resume_after_qso(self, last_qso_was_even: bool) -> None:
    """Nach QSO-Ende neu starten — Block-Wahl nach letztem QSO-Slot.
    Mike-Spec: QSO endet auf Even → Block 2 (Odd-First). Endet auf Odd → Block 1.
    Logik: nächster freier Slot ist gegenüberliegend zum letzten QSO-Slot →
    der Block beginnt dort mit TX."""
    with self._lock:
        if not self._paused:
            return  # nicht pausiert (oder schon gestoppt) → nichts zu tun
        self._paused = False
    # Block-Wahl: gegenüberliegend zu last_qso_was_even
    next_is_even = not last_qso_was_even
    self.start(next_is_even=next_is_even)
    logger.info(f"[OMNI-CQ] Resume after QSO (last_was_even={last_qso_was_even} "
                 f"→ next_is_even={next_is_even} → Block {self._block})")
```

### 2.6 `_maybe_recheck_freq()`

```python
def _maybe_recheck_freq(self) -> None:
    """Alle _BLOCKS_PER_FREQ_RECHECK Blöcke prüft Sticky-Gap-Algo."""
    if self._block_count % self._BLOCKS_PER_FREQ_RECHECK != 0:
        return
    new_freq = self._diversity.get_free_cq_freq()
    if new_freq is None:
        return
    if new_freq != self._cq_audio_hz:
        logger.info(f"[OMNI-CQ] Freq-Switch {self._cq_audio_hz} → {new_freq} Hz "
                     f"(nach {self._block_count} Blöcken)")
        self._cq_audio_hz = new_freq
        self.cq_freq_changed.emit(new_freq)
    # else: Sticky → bleibt
```

---

## 3. Schnittstellen

### 3.1 `ui/main_window.py`

```python
# __init__
self._omni_cq = OmniCQ(
    encoder=self.encoder,
    diversity_ctrl=self._diversity_ctrl,
    timer=self._timer,
    my_call=self.my_call,
    my_grid=self.my_grid,
)
# Signals
self._omni_cq.omni_stopped.connect(self._on_omni_stopped)
self._omni_cq.cq_freq_changed.connect(self._on_omni_freq_changed)
self._omni_cq.counter_changed.connect(self._on_omni_counter_changed)
self._omni_cq.slot_action.connect(self._on_omni_slot_action)
# Button
self.control_panel.btn_omni_cq.toggled.connect(self._on_btn_omni_cq_toggled)


def _on_btn_omni_cq_toggled(self, checked: bool):
    if checked and not self._omni_cq.is_active():
        # KEIN qso_sm.start_cq() — OMNI ist eigenständig.
        self._omni_cq.start()  # next_is_even wird intern berechnet
        self.control_panel.update_omni_tx(True)
    elif not checked and self._omni_cq.is_active():
        self._omni_cq.stop("manual_halt")


def _on_omni_stopped(self, reason: str):
    # Cleanup: Button + UI. KEIN qso_sm.stop_cq() — OMNI nutzt cq_mode nie.
    self.control_panel.btn_omni_cq.blockSignals(True)
    self.control_panel.btn_omni_cq.setChecked(False)
    self.control_panel.btn_omni_cq.blockSignals(False)
    self.control_panel.update_omni_tx(False)


# Stop-Trigger (analog Auto-Hunt v0.75)
# - Bandwechsel: mw_radio._on_band_changed
# - Mode-Wechsel: mw_radio._on_mode_changed
# - RX-Mode-Wechsel: mw_radio._on_rx_mode_changed
# - Totmann-Expired: main_window._on_presence_tick

# Statusbar Ω
def _on_omni_counter_changed(self, even: int, odd: int):
    # _update_statusbar liest counter aus
    self._update_statusbar()
```

### 3.2 `ui/mw_qso.py`

OMNI-Übergabe-Pfad bei eingehender CQ-Antwort. **Wichtige Frage:** wie
erkennt mw_qso dass eine Decoded-Message eine Antwort an UNS während OMNI
ist? — Antwort: derselbe Pfad wie heute, nur ohne `cq_mode`.

```python
# In on_message_received-Pfad (qso_state.py):
# Heute:  if self.cq_mode and msg.target == my_call: _pending_reply = msg
# Neu:    if (self.cq_mode OR omni_cq.is_active()) and msg.target == my_call:
#             _pending_reply = msg

# Damit qso_state nichts von OMNI weiss, machen wir die Erkennung in
# mw_qso ueber den message_decoded-Listener:
def _on_message_decoded(self, msg):
    # Existing Path: qso_state.on_message_received → _pending_reply gesetzt wenn cq_mode

    # NEU: bei OMNI aktiv + Antwort an uns → an Hunt-Pipeline geben
    if self._omni_cq.is_active() and not self._omni_cq.is_paused():
        if msg.target == self.my_call and not msg.is_73 and not msg.is_rr73:
            self._omni_cq.pause()
            self.qso_sm.start_qso(
                their_call=msg.caller,
                their_grid=msg.grid_or_report if msg.is_grid else "",
                freq_hz=msg.freq_hz,
                their_snr=msg.snr,
            )
            # Hunt-State-Machine übernimmt — TX-Slot-Parität setzt sie selbst
            # via tx_slot_for_partner-Signal.
```

**Pause/Resume-Helpers (umgebaut):**

```python
def _pause_omni_if_active(self) -> None:
    """Wird gerufen aus 3 Entry-Pfaden (Hunt-Klick, CQ-Reply via _process_cq_reply, Replace)."""
    if self._omni_cq.is_active() and not self._omni_cq.is_paused():
        self._omni_cq.pause()
        self._omni_was_active_pre_qso = True

def _maybe_resume_omni(self) -> None:
    """Wird gerufen aus 3 Exit-Pfaden (qso_complete, qso_confirmed, qso_timeout)."""
    if not getattr(self, '_omni_was_active_pre_qso', False):
        return
    # Caller-Queue hat Vorrang — wenn nach QSO direkt nächste Station, dann
    # bleibt _omni_was_active_pre_qso=True und neuer QSO ruft _pause_omni_if_active.
    if self.qso_sm._caller_queue:
        return
    last_qso_was_even = self._last_qso_tx_even  # gemerkt aus encoder.tx_even bei QSO-Ende
    self._omni_cq.resume_after_qso(last_qso_was_even)
    self._omni_was_active_pre_qso = False
```

**HALT-Branch (`_on_cancel`):**
```python
if self._omni_cq.is_active():
    self._omni_cq.stop("manual_halt")
self._omni_was_active_pre_qso = False
```

### 3.3 `ui/mw_cycle.py`

**KOMPLETT RAUS:** alle `_omni_pretrigger_*`, `_OMNI_PRETRIGGER_OFFSET_S`,
`omni_tx.advance()` in `_on_cycle_start`, `_omni_tx.is_paused`-Check.
OMNI hat eigenen Worker, mw_cycle muss nichts mehr triggern.

### 3.4 `core/qso_state.py`

**Klein anpassen:** `_omni_skip_state_change`-Flag-Pattern in `_send_cq`
RAUS, `_was_pretriggered`-Flag RAUS, on_cycle_end CQ_WAIT-Schutz RAUS.
Zurück zu Zustand vor v0.95.22 (P1.OMNI-START).

### 3.5 `core/encoder.py`

**Klein anpassen:** `_pending_tx_message`-Queue + Outer-Loop in `_tx_worker`
RAUS. `transmit()` zurück zu SKIP-bei-aktiv. Replace-Pfad (`request_replace`)
BLEIBT (war P1.9-Fix für CQ-Reply, nicht OMNI-spezifisch).

---

## 4. Akzeptanzkriterien (ACs)

### Funktional

- **AC1** Klick auf btn_omni_cq → OMNI startet, Button-Label
  „OMNI CQ (aktiv)", Ω-Symbol in Statusbar.
- **AC2** Block-Wahl beim Start: nächster Slot Even → Block 1 (TX-E TX-O ...).
  Nächster Slot Odd → Block 2 (TX-O TX-E ...).
- **AC3** 5-Slot-Pattern korrekt: 2 TX gefolgt von 3 RX, danach Block-Wechsel
  (slot_index 4 → 0). Block 1 → Block 2 → Block 1 → Block 2 ... permanent.
- **AC4** OMNI-TX läuft auf **fester Audiofrequenz** während gesamter
  Block-Sequenz. Erste Frequenz beim Start aus `diversity.get_free_cq_freq()`.
- **AC5** Frequenz-Recheck alle **4 Blöcke** (~5 Min FT8). Sticky bleibt
  wenn frei, wechselt nur wenn Algo neue Frequenz vorschlägt.
- **AC6** Während laufendem QSO: NIEMALS Frequenz-Wechsel.
- **AC7** Eingehende Antwort an unsere CQ → OMNI pausiert
  (`omni_cq.pause()`), Hunt-Pipeline übernimmt via `qso_state.start_qso(...)`.
  QSO läuft im Even/Odd-Rhythmus der Antwort.
- **AC8** Nach QSO-Ende: `omni_cq.resume_after_qso(last_qso_was_even)` —
  Block-Wahl nach letztem QSO-Slot:
  - QSO endete auf Even → Block 2 (Odd-First) ab Pos 0
  - QSO endete auf Odd → Block 1 (Even-First) ab Pos 0
- **AC9** OMNI startet IMMER ab Pos 0 — nie mittendrin, nie halber Block.
- **AC10** Caller-Queue hat Vorrang: nach QSO-Ende, wenn `_caller_queue`
  nicht leer → kein OMNI-Resume, nächster QSO startet, danach erst OMNI.
- **AC11** Stop-Bedingungen: `manual_halt`, `band_change`, `mode_change`,
  `rx_mode_change`, `totmann_expired` — alle sofort, OMNI-Worker-Thread
  läuft aus, Button-Label „OMNI CQ", Ω verschwindet.
- **AC12** Kein `qso_state.cq_mode` während OMNI aktiv. `cq_mode` bleibt
  exklusiv für Normal-CQ. Bestätigung: grep `cq_mode = True` darf NIRGENDS
  innerhalb der OMNI-Pfade auftreten.
- **AC13** Hardware-Garantie: alle TX gehen über `Encoder.transmit()` →
  `radio.set_tx_antenna("ANT1")` zentral. Kein Extra-Check nötig.
- **AC14** App-Restart während OMNI aktiv: OMNI startet inactive (kein
  State-Persist).
- **AC15** Mike-Field-Test: 10-Slot-Loop ohne Pattern-Drift, ohne fehlende
  TX-Slots, ohne falsche Block-Wahl.

### Architektur (Mike's Anforderung)

- **AC16** Eigenes Modul `core/omni_cq.py`. KEIN Code-Sharing mit
  `qso_state.cq_mode`-Pfad.
- **AC17** Eigener Worker-Thread mit absolut-UTC-Boundaries. KEIN
  `cycle_tick`-Polling, KEIN `QTimer`, KEIN GUI-Thread-Abhängigkeit für
  Slot-Timing.
- **AC18** Übergabe an Hunt-Pipeline über `qso_state.start_qso(...)` —
  gleicher Eingang wie Hunt-Klick.

---

## 5. Test-Plan (Schätzung +20 Tests)

### Unit-Tests `tests/test_omni_cq_worker.py` (NEU)

| # | Test | Verifiziert |
|---|---|---|
| T1 | `test_initial_state_inactive` | OmniCQ nach __init__ inactive, slot_index=0, block=1 |
| T2 | `test_start_with_next_is_even_block1` | start(True) → block=1, slot_index=0, active=True |
| T3 | `test_start_with_next_is_odd_block2` | start(False) → block=2, slot_index=0 |
| T4 | `test_next_slot_action_block1` | Pos 0/1/2/3/4 → (TX,E)(TX,O)(RX,*)(RX,*)(RX,*) |
| T5 | `test_next_slot_action_block2` | Pos 0/1/2/3/4 → (TX,O)(TX,E)(RX,*)(RX,*)(RX,*) |
| T6 | `test_block_rollover_after_5_slots` | nach 5 advance → block 1→2 |
| T7 | `test_resume_after_qso_even_chooses_block2` | resume(True) → block=2 |
| T8 | `test_resume_after_qso_odd_chooses_block1` | resume(False) → block=1 |
| T9 | `test_resume_starts_from_pos_0_always` | resume(*) → slot_index=0 |
| T10 | `test_pause_freezes_state` | pause() → _paused=True, Worker-Thread tot |
| T11 | `test_stop_cleans_state` | stop("manual_halt") → active=False, slot=0 |
| T12 | `test_freq_recheck_every_4_blocks` | block_count 4 → get_free_cq_freq() called |
| T13 | `test_freq_sticky_when_unchanged` | get_free_cq_freq returnt gleichen Wert → kein Emit |
| T14 | `test_freq_changes_when_diversity_returns_new` | neuer Wert → emit + state-update |
| T15 | `test_compute_next_boundary_target_even` | Math: even-Slot in Zukunft |
| T16 | `test_compute_next_boundary_target_odd` | Math: odd-Slot in Zukunft |
| T17 | `test_compute_next_boundary_rx_no_filter` | target_even=None → einfach next |

### Integration-Tests `tests/test_omni_cq_integration.py` (NEU)

| # | Test | Verifiziert |
|---|---|---|
| I1 | `test_toggle_button_starts_omni` | btn_omni_cq.toggled(True) → omni_cq.is_active() |
| I2 | `test_toggle_button_stops_omni` | toggled(False) → stop("manual_halt") |
| I3 | `test_band_change_stops_omni` | mw_radio._on_band_changed → omni_cq.stop("band_change") |
| I4 | `test_mode_change_stops_omni` | _on_mode_changed → stop("mode_change") |
| I5 | `test_rx_mode_diversity_to_normal_stops_omni` | rx_mode_change → stop |
| I6 | `test_qso_pauses_omni` | mw_qso _on_message_decoded → answer for me → pause |
| I7 | `test_qso_complete_resumes_omni` | _on_qso_complete → resume_after_qso |
| I8 | `test_caller_queue_blocks_resume` | queue not empty → kein resume |
| I9 | `test_no_cq_mode_during_omni` | omni_cq aktiv → qso_sm.cq_mode == False |
| I10 | `test_halt_stops_omni` | _on_cancel → stop("manual_halt") |

### Migration-Tests (existing OMNI-Tests RAUS oder umstellen)

- `tests/test_p1_omni_start.py` — RAUS (war Toggle-Migration v0.95.22)
- `tests/test_p2_omni_redesign.py` — RAUS (Slot-Filter-API alt)
- `tests/test_p2_omni_pattern_fix.py` — RAUS (Encoder-Queue + Pretrigger alt)
- `tests/test_p3_omni_pattern_fix2.py` — RAUS (QTimer alt)
- `tests/test_omni_tx.py` — RAUS oder reduzieren (wenn Pattern-Konstanten wiederverwendet)
- `tests/test_encoder_queue.py` — RAUS (Encoder-Queue war OMNI-spezifisch)

**Test-Bilanz:** -50 alte Tests, +27 neue → netto -23 Tests.
1069 → ~1046 Tests.

---

## 6. Field-Test-Plan (Mike, vor Push)

| # | Aktion | Erwartet |
|---|---|---|
| F1 | Diversity_Std → btn_omni_cq klicken | Button „OMNI CQ (aktiv)", Ω in Statusbar |
| F2 | 10-Slot-Loop laufen lassen | 4 TX (2× Block 1, 2× Block 2), 6 RX. Pattern-Drift = 0. |
| F3 | Block 1: TX [E], TX [O], RX [E], RX [O], RX [E] | exakt diese Reihenfolge im QSO-Panel |
| F4 | Block 2: TX [O], TX [E], RX [O], RX [E], RX [O] | exakt diese Reihenfolge |
| F5 | Eingehende CQ-Antwort mid-OMNI | OMNI pausiert, QSO läuft normal, RR73 |
| F6 | Nach QSO endete auf Even | Resume mit Block 2 (TX [O] zuerst), Pos 0 |
| F7 | Nach QSO endete auf Odd | Resume mit Block 1 (TX [E] zuerst), Pos 0 |
| F8 | btn_omni_cq erneut klicken | Stop, Button-Label zurück, Ω weg |
| F9 | Bandwechsel mid-OMNI | Stop, Status zeigt Reason |
| F10 | Mode-Wechsel Diversity → Normal | Stop, btn_omni_cq verschwindet |
| F11 | 5+ Min ohne Maus + ohne QSO | Totmann-Stop |
| F12 | Frequenz-Recheck nach 4 Blöcken (~5 Min) | Log zeigt entweder „Sticky" oder „Switch" |

---

## 7. Risiken / Edge-Cases

| # | Risiko | Mitigation |
|---|---|---|
| R1 | Worker-Thread-Race bei pause + stop gleichzeitig | RLock + 2.0s Join-Timeout, idempotent |
| R2 | Encoder belegt bei OMNI-TX-Trigger (Race) | encoder.transmit() ist thread-safe (lock-protected). SKIP bei busy ist OK — OMNI verliert max 1 Slot. |
| R3 | Decoder noch nicht fertig bei OMNI-TX-Wake | Worker wakes 1.5s vor Boundary, Decoder ready bei `boundary - 0.5s` (FT8 _WAKE_OFFSETS=2.5). 1.0s Marge. |
| R4 | Resume mit `_caller_queue` Race | `_maybe_resume_omni` checkt Queue NACH `_omni_was_active_pre_qso` — wenn Queue nicht leer, kein Resume. Caller-Queue triggert eigenen QSO, der wieder `_pause_omni_if_active` aufruft → bleibt pausiert. |
| R5 | Frequenz-Recheck während QSO | `_maybe_recheck_freq` läuft NUR bei block_count++ → block_count++ läuft NUR bei slot_index 4→0 → läuft NUR im Worker-Loop → Worker-Loop terminiert bei pause(). Garantiert kein Recheck während QSO. |
| R6 | App-Crash + OMNI-State-Persist | OMNI startet immer inactive. Settings persistiert OMNI-State NICHT. |
| R7 | mw_qso `_last_qso_tx_even` falsch gesetzt | Wert wird in `_on_tx_finished` aus `encoder.tx_even` gemerkt, in `_on_qso_complete` an `resume_after_qso` übergeben. Tests T7+T8 schützen. |
| R8 | Listener-Pfad „Antwort an mich" — wo gehört das hin? | mw_qso `_on_message_decoded` ist der zentrale Listener. OMNI-Check kommt VOR `qso_state.on_message_received`. |
| R9 | OMNI vs Auto-Hunt mutually-exclusive | btn-Group bereits mutex (control_panel.py:774-802 QButtonGroup). Plus: Auto-Hunt-Start ruft `omni_cq.stop("superseded")` falls aktiv. |
| R10 | Hardware-Wechsel zu ANT2 für TX | Encoder.transmit erzwingt ANT1. OMNI emittet kein TX direkt. Bestätigt §4.13. |

---

## 8. Was BLEIBT vs was RAUS muss (Zusammenfassung)

### NEU
- `core/omni_cq.py` (~350 Z, neue Datei)
- `tests/test_omni_cq_worker.py` (~17 Tests)
- `tests/test_omni_cq_integration.py` (~10 Tests)

### UMGEBAUT
- `ui/main_window.py` — `_on_btn_omni_cq_toggled` neu (kein qso_sm.start_cq), `_on_omni_stopped` vereinfacht, OMNI-Connections umgestellt
- `ui/mw_qso.py` — Pause/Resume-Helpers neu API, `_on_message_decoded` OMNI-Antwort-Check, OMNI-Bypass in `_on_send_message` raus, HALT-Branch neu API
- `ui/mw_cycle.py` — alle `_omni_pretrigger_*` raus, `omni_tx.advance` raus
- `core/qso_state.py` — `_omni_skip_state_change`, `_was_pretriggered`, on_cycle_end CQ_WAIT-OMNI-Schutz alle raus
- `core/encoder.py` — `_pending_tx_message` Queue + Outer-Loop raus, transmit zurück zu SKIP-bei-aktiv

### KOMPLETT GELÖSCHT
- `core/omni_tx.py` (alte Slot-Filter-Klasse, Worker-loser Ansatz unbrauchbar)
- `tests/test_p1_omni_start.py`
- `tests/test_p2_omni_redesign.py`
- `tests/test_p2_omni_pattern_fix.py`
- `tests/test_p3_omni_pattern_fix2.py`
- `tests/test_omni_tx.py`
- `tests/test_encoder_queue.py`

### BLEIBT UNVERÄNDERT
- `core/qso_state.start_qso`-Pfad (Hunt-Pipeline)
- `core/qso_state.start_cq` / `stop_cq` / `_send_cq` (für Normal-CQ exklusiv)
- `core/encoder.request_replace` (P1.9-Fix CQ-Reply, nicht OMNI)
- `core/diversity.get_free_cq_freq` (sticky-Gap-Algo)
- `core/timing.FT8Timer`
- Hunt-State-Machine komplett

---

## 9. Atomare Commits (Vorschlag)

| # | Commit | Inhalt |
|---|---|---|
| C1 | `core/omni_cq.py + tests` | Neues Modul + 17 Unit-Tests |
| C2 | `Rückbau qso_state + encoder` | OMNI-Reste raus aus core/ (kein OMNI-Verhalten weil `core/omni_cq.py` noch nicht angeschlossen) |
| C3 | `Rückbau ui/mw_cycle.py` | _omni_pretrigger_* raus |
| C4 | `Anschluss ui/main_window.py + mw_qso.py` | OmniCQ initialisiert + Signals + Pause/Resume umgestellt |
| C5 | `Stop-Trigger mw_radio.py + main_window` | band_change, mode_change, rx_mode_change, totmann_expired |
| C6 | `Migration Tests` | Alte OMNI-Tests gelöscht, Integration-Tests hinzugefügt |
| C7 | `APP_VERSION 0.95.25 → 0.96.0 + Doku` | HISTORY + HANDOFF + CLAUDE + Memory |

---

## 10. APP_VERSION

`v0.95.25 → v0.96.0` (Major-Bump weil Architektur-Refactor).

---

## 11. Offene Fragen für V2 / R1

1. **Frequenz-Recheck-Intervall:** 4 Blöcke (~5 Min) ist Start. Field-Test
   muss zeigen ob das gut ist oder ob 6/8 Blöcke besser sind. **V2-Klärung.**
2. **OMNI-RX-Slot Listener:** OMNI-Worker emittet `slot_action`-Signal mit
   „Horche..."-Label. mw_qso registriert das fürs QSO-Panel. **V2-Verifikation.**
3. **`_last_qso_tx_even` woher?** Aus `encoder.tx_even` bei `_on_tx_finished`?
   Oder aus `_pending_tx_msg.tx_even`? **V2-Code-Verifikation.**
4. **Decoder-Drift bei OMNI-TX:** Encoder.transmit aus Worker-Thread
   bei `boundary - 1.5s`. Encoder schläft selbst bis `boundary - 1.3s`,
   sendet. Decoder ist bei `boundary - 0.5s` ready. **R1-Race-Analyse.**
5. **mw_qso `_on_message_decoded`** — gibt es das überhaupt oder läuft
   das über `qso_state.on_message_received`? **V2-Code-Verifikation.**
6. **`encoder.tx_even` Race:** OMNI setzt `encoder.tx_even` direkt vor
   `transmit()`. Wenn Encoder gerade noch im vorherigen TX ist, sieht der
   alte TX den neuen tx_even-Wert? **R1-Race-Analyse.** Mitigation: API
   `transmit(msg, tx_even=...)` als Atomik.
7. **Start-Sequenz beim allerersten OMNI-Start:** `_cq_audio_hz=None` →
   wird beim ersten TX gesetzt. Aber WAS wenn `diversity.get_free_cq_freq()`
   None returnt (kein freier Slot)? Fallback 1500 Hz? **V2-Klärung.**

---

## 12. Workflow-Status

- ✅ Schritt 0 — Code-Verifikation
- ✅ V1 (dieses Dokument)
- ⏳ V2 — Self-Review als „neue KI"
- ⏳ R1 — DeepSeek-Reasoner
- ⏳ V3 — Compact-fest
- ⏳ Mike-Freigabe
- ⏳ Compact
- ⏳ Code (atomare Commits)
- ⏳ Final-R1
- ⏳ Field-Test
- ⏳ Doku + Push

---

**Ende V1.**
