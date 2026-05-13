# P4.OMNI-NEUBAU — V3 (Compact-fest)

**Datum:** 2026-05-09 (Abend, post-R1)
**Status:** R1 (DeepSeek-Reasoner, in=57386 / out=13346): 🟡 „Plan
braucht V3-Anpassungen" — 17/20 V2-Lessons ✅ bestätigt, **2 ⛔ KRITISCHE
neue Findings (R1+R2)** + 3 SOLLTE (R3-R5) eingearbeitet.
**Verbindliche Spec:** `memory/project_omni_cq_spec.md` (Mike-Dialog
09.05.2026 Abend). Diese V3 ist die einzige Wahrheit für Compact +
Code-Phase.

---

## 0. Schritt 0 — Code-Verifikation (komplett)

| Verifikation | Stand | Beleg |
|---|---|---|
| `core/omni_tx.py` Worker-loser Slot-Filter | KOMPLETT RAUS | core/omni_tx.py 252 Z. |
| `qso_state._omni_skip_state_change` Flag | RAUS | qso_state.py:177 `_send_cq` |
| `qso_state._was_pretriggered` Flag | RAUS | qso_state.py |
| `encoder._pending_tx_message` Queue | RAUS | encoder.py |
| `main_window._omni_pretrigger_timer` QTimer | RAUS | main_window.py:241-245 |
| `mw_cycle._omni_pretrigger_*` (Check + Fire-Impl) | RAUS | mw_cycle.py:586-700 |
| `mw_qso._on_send_message` OMNI-Bypass-Block | RAUS | mw_qso.py:340-410 |
| Hunt-Pfad `qso_state.start_qso(call,grid,freq,their_snr)` | BLEIBT | qso_state.py:270 |
| Hunt-State-Machine (WAIT_REPORT/RR73/73/COURTESY/etc.) | BLEIBT | qso_state.py |
| `qso_state.start_cq` / `stop_cq` / `_send_cq` (Normal-CQ exklusiv) | BLEIBT | qso_state.py:163,171,177 |
| `encoder.transmit(message)` | BEKOMMT atomare API (R1 V2-L2) | encoder.py:189 |
| `encoder._next_slot_boundary()` | BLEIBT (Vorbild) | encoder.py:254 |
| `encoder.request_replace` (P1.9-Fix) | BLEIBT | encoder.py:110 |
| `core/diversity.get_free_cq_freq` (Sticky-Gap) | BLEIBT | diversity.py:190 |
| `core/timing.FT8Timer` | BLEIBT | timing.py |
| `radio.set_tx_antenna("ANT1")` zentral in `Encoder.transmit` | BLEIBT | encoder.py:334 |
| **R1-Finding R2 verifiziert:** `mw_qso._on_station_clicked` setzt heute `encoder.tx_even = not their_even` VOR `start_qso(...)` | mw_qso.py:171-176 | OMNI-Listener-Pfad muss DASSELBE Pattern verwenden |

**R1-Verifikation Stand:** alle 5 R1-Findings (R1-R5) als KRITISCH/SOLLTE
in V3 §3+§7 eingearbeitet. Keine R1-Halluzination — R2 (encoder.tx_even
im Listener) ist Code-bewiesen.

---

## 0.5 — Code-Pfade verifiziert (KI-Cold-Start-Helper)

Diese Tabelle ist verbindlich für die Code-Phase. Jeder Eintrag wurde
gegen aktuellen Code geprüft (NICHT halluziniert):

| Was | Wo | Beleg |
|---|---|---|
| `MainWindow` Klassen-Definition (Mixin) | `ui/main_window.py:40` | `class MainWindow(QMainWindow, CycleMixin, QSOMixin, RadioMixin, TXMixin)` |
| `self.timer = FT8Timer(settings.mode)` | `ui/main_window.py:120` | (NICHT `self._timer`!) |
| `self.encoder = Encoder(settings.audio_freq_hz)` | `ui/main_window.py:122` | |
| `self._diversity_ctrl = DiversityController()` | `ui/main_window.py:218` | |
| `self.settings` (`.callsign`, `.locator`) | `ui/main_window.py:49` + `config/settings.py:129,133` | „my_grid" = `settings.locator` (Maidenhead) |
| `self._omni_was_active_pre_qso = False` | `ui/main_window.py:226` | Mixin-zugreifbar aus mw_cycle/mw_qso |
| `FT8Message.is_grid` / `.is_73` / `.is_rr73` | `core/message.py:64,68,72` | Properties (nicht Funktionen) |
| `FT8Message._tx_even` | gesetzt in `decoder._assign_slot_parity` | Final-R1 F-4: getattr-Fallback ist Defense-in-Depth |
| `FT8Message.target` / `.caller` / `.snr` / `.freq_hz` / `.grid_or_report` | `core/message.py` | bestehende Felder |
| `auto_hunt.start_auto_hunt(duration_sec)` / `.stop_auto_hunt(reason)` | `core/auto_hunt.py:114,139` | **`auto_hunt.cancel()` existiert NICHT** — V3-§3.3 nutzt `stop_auto_hunt("superseded")` |
| `auto_hunt.active` (boolean attribute) | `core/auto_hunt.py:128,156` | bestehend |
| `mw_radio._on_band_changed` | `ui/mw_radio.py:275` | Stop-Trigger einbauen |
| `mw_radio._on_mode_changed` | `ui/mw_radio.py:199` | Stop-Trigger einbauen |
| `mw_radio._on_rx_mode_changed` | `ui/mw_radio.py:392` | Stop-Trigger einbauen |
| `main_window._on_btn_auto_hunt_toggled` | `ui/main_window.py:782` | Auto-Hunt-Coupling (alte `_omni_tx.stop_omni_tx` durch `_omni_cq.stop`) |
| `main_window._on_presence_tick` (Totmann) | `ui/main_window.py:1128,1144` | Stop-Trigger `totmann_expired` |
| `qso_panel.add_listening(slot_start_ts: float, tx_even: bool)` | `ui/qso_panel.py:202` | seit v0.95.25, Parameter-Name `tx_even` = Slot-Parität (für E/O-Tag) |
| `timer.cycle_duration` (NICHT `cycle_durations[mode]`) | `core/timing.py:32,39` | float, modus-aware |
| `timer.is_even_cycle()` | `core/timing.py` | aktuelle Parität (NICHT next, V0.95.23 dokumentiert) |
| `existing _on_station_clicked Pattern` für `encoder.tx_even` Setter | `ui/mw_qso.py:171-176` | Vorbild für Listener + `_maybe_resume_omni` |
| `mw_qso._auto_hunt` (Attribut) | `ui/mw_qso.py:149,265,426,493` | bestehend |
| `_pending_station_click` Buffer-Pattern (P1.24) | `ui/main_window.py:209` + `ui/mw_qso.py` | OMNI greift NICHT in den Buffer ein — User-Klick während OMNI-TX wird gepuffert, nach TX-Ende `_on_station_clicked` läuft → ruft `_pause_omni_if_active` |

**Konsequenz für V3-Diffs:** Konstruktor-Parameter `OmniCQ(timer=self.timer, ...)` (NICHT `self._timer`). Auto-Hunt-Stop ist `stop_auto_hunt("superseded")` (NICHT `cancel()`). Slot-Parität bei RX-Anzeige = `timer.is_even_cycle()`.

---

## 1. Konzept (verbindlich, aus Spec)

5-Slot-Pattern mit eigenem Worker-Thread, sticky Audiofrequenz, Übergabe
an Hunt-Pipeline bei Antwort.

```
Block 1 (Even-First):  TX-E  TX-O  RX-E  RX-O  RX-E
Block 2 (Odd-First):   TX-O  TX-E  RX-O  RX-E  RX-O

Wechsel: nach 5 Slots automatisch (slot_index 4 → 0). Block 1 ↔ Block 2.
Nach QSO: QSO endet auf Even → Block 2. Endet auf Odd → Block 1.
          IMMER ab Pos 0.
App-Start: nächster Slot Even → Block 1. Odd → Block 2.
```

**Frequenz:** initial `diversity.get_free_cq_freq()` (Sticky-Gap), bleibt
während Block + QSO. Recheck **alle 4 Blöcke** (Mike-Spec, R1-L5
„TEILWEISE" akzeptiert — Spec-konform). Mit FT8 = 5 Min, FT4 = 2:30, FT2
= 1:15 (FT4/FT2 Edge-Cases akzeptiert, Hobby-Use 99 % FT8).

**Übergabe an Hunt-Pipeline:**
- OMNI dekodiert nicht selbst — hört in RX-Slots
- Listener `mw_cycle.on_message_decoded` erkennt „Antwort an mich"
  (`msg.target == my_call`)
- Listener: `omni_cq.pause()` + **`encoder.tx_even = not msg._tx_even`**
  (R1 R2!) + `qso_state.start_qso(...)` (gleicher Eingang wie Hunt-Klick)
- Nach QSO: `omni_cq.resume_after_qso(last_qso_was_even)`

---

## 2. Neues Modul `core/omni_cq.py`

### 2.1 Klassen-Skelett

```python
import threading
import time
import logging
from PySide6.QtCore import QObject, Signal

logger = logging.getLogger(__name__)


class OmniCQ(QObject):
    """OMNI-CQ Worker — eigene Slot-getaktete CQ-Pipeline (P4.OMNI-NEUBAU).

    5-Slot-Pattern (TX-TX-RX-RX-RX). Eigener Worker-Thread mit
    absolut-UTC-Boundaries. KEIN cycle_tick / KEIN QTimer / KEIN
    GUI-Thread-Polling. Bei eingehender Antwort: pause() + Übergabe
    an qso_state.start_qso(). Nach QSO: resume_after_qso(last_was_even).
    """

    # ── Signals ─────────────────────────────────────────────────────
    omni_started = Signal()
    omni_stopped = Signal(str)              # reason
    slot_action = Signal(str, bool, bool)   # (label, is_tx, target_even)
    cq_freq_changed = Signal(int)           # neue Audiofrequenz (Hz)
    counter_changed = Signal(int, int)      # (cq_even, cq_odd)

    # ── Konstanten ──────────────────────────────────────────────────
    _TX_PATTERN = (True, True, False, False, False)  # 5 Slots
    _BLOCKS_PER_FREQ_RECHECK = 4                      # Mike-Spec
    _OMNI_TX_PRELEAD_S = 2.0                          # R1 R1: 1.5→2.0 (0.7s Marge)
    _FALLBACK_AUDIO_HZ = 1500                         # V2-L4

    def __init__(self, encoder, diversity_ctrl, timer, my_call: str, my_grid: str):
        super().__init__()
        self._encoder = encoder
        self._diversity = diversity_ctrl
        self._timer = timer
        self._my_call = my_call
        self._my_grid = my_grid

        # Lifecycle
        self._thread: threading.Thread | None = None
        self._running = False
        self._stop_event = threading.Event()
        self._lock = threading.RLock()

        # Pattern-State
        self._slot_index = 0       # 0..4
        self._block = 1            # 1=Even-First, 2=Odd-First
        self._block_count = 0      # für Frequenz-Recheck

        # Pause-State
        self._paused = False

        # Counters
        self._cq_even_count = 0
        self._cq_odd_count = 0

        # Audiofrequenz (sticky)
        self._cq_audio_hz: int | None = None

    # ── Public API ──────────────────────────────────────────────────
    def start(self, next_is_even: bool | None = None) -> None: ...
    def stop(self, reason: str) -> None: ...
    def pause(self) -> None: ...
    def resume_after_qso(self, last_qso_was_even: bool) -> None: ...
    def is_active(self) -> bool: ...
    def is_paused(self) -> bool: ...

    # ── Internal ────────────────────────────────────────────────────
    def _worker_loop(self) -> None: ...
    def _next_slot_action(self) -> tuple[bool, bool]: ...
    def _compute_next_boundary(self, target_even: bool | None) -> float: ...
    def _maybe_recheck_freq(self) -> None: ...
    def _slot_label(self, is_tx: bool, target_even: bool) -> str: ...
```

### 2.2 Worker-Loop

```python
def _worker_loop(self) -> None:
    PRELEAD = self._OMNI_TX_PRELEAD_S  # 2.0s (R1 R1)
    while True:
        with self._lock:
            if not self._running:
                return
            if self._paused:
                return  # Worker beendet sich. resume_after_qso startet neu.

        is_tx, target_even = self._next_slot_action()

        # Boundary: TX braucht Parität, RX einfach next
        next_boundary = self._compute_next_boundary(target_even if is_tx else None)
        sleep_dur = (next_boundary - PRELEAD) - time.time()

        # V2-L13: cancelable sleep statt time.sleep
        if sleep_dur > 0:
            if self._stop_event.wait(timeout=sleep_dur):
                return  # stop() oder pause() rief

        # Re-Check nach Sleep
        with self._lock:
            if not self._running:
                return
            if self._paused:
                return

        # Slot-Aktion
        if is_tx:
            # Sticky-Frequenz beim ersten TX
            if self._cq_audio_hz is None:
                freq = self._diversity.get_free_cq_freq()
                if freq is None:
                    freq = self._FALLBACK_AUDIO_HZ
                    logger.warning("[OMNI-CQ] get_free_cq_freq=None → Fallback 1500 Hz")
                self._cq_audio_hz = freq
                self.cq_freq_changed.emit(freq)

            cq_msg = f"CQ {self._my_call} {self._my_grid}"
            # V2-L2: atomare API. R1 bestätigt: einfache GIL-Atomic ist OK,
            # aber atomare API macht Code sauberer.
            ok = self._encoder.transmit(
                cq_msg,
                tx_even=target_even,
                audio_freq_hz=self._cq_audio_hz,
            )
            if ok:
                with self._lock:
                    if target_even:
                        self._cq_even_count += 1
                    else:
                        self._cq_odd_count += 1
                self.counter_changed.emit(self._cq_even_count, self._cq_odd_count)
                self.slot_action.emit(self._slot_label(True, target_even), True, target_even)
            else:
                logger.warning("[OMNI-CQ] encoder.transmit returnt False (busy) — Slot verloren")
        else:
            # RX-Slot: V2-L8 — slot_action emittieren mit ECHTER Slot-Parität
            # (Anzeige). qso_panel.add_listening(ts, tx_even) erwartet die
            # echte UTC-Slot-Parität für [E]/[O]-Tag, NICHT die Pattern-
            # interne Variable. Quelle: timer.is_even_cycle() ist direkt vor
            # Slot-Boundary noch der vorherige Slot — wir emittieren nach
            # Boundary-Erreichen, also gibt is_even_cycle() den aktuellen
            # (RX-)Slot zurück.
            actual_even = self._timer.is_even_cycle()
            self.slot_action.emit(
                self._slot_label(False, actual_even), False, actual_even,
            )

        # State-Advance + Block-Rollover + Frequenz-Recheck
        with self._lock:
            self._slot_index = (self._slot_index + 1) % 5
            if self._slot_index == 0:
                self._block = 2 if self._block == 1 else 1
                self._block_count += 1
                self._maybe_recheck_freq()
        # KEIN time.sleep am Ende — _compute_next_boundary findet die nächste
        # Boundary korrekt (V2-L13 Ergänzung).
```

### 2.3 `_compute_next_boundary(target_even)`

```python
def _compute_next_boundary(self, target_even: bool | None) -> float:
    """Nächste UTC-Slot-Boundary, ggf. mit Parität-Filter."""
    SLOT = self._timer.cycle_duration  # 15.0/7.5/3.8s je Mode
    now = time.time()
    cycle_num = int(now / SLOT)
    cycle_pos = now % SLOT
    # Aktueller Slot zu Ende → nächster Slot ist (cycle_num + 1)
    if target_even is None:
        # RX: nächste Boundary egal welche Parität
        return float((cycle_num + 1) * SLOT)
    # TX mit Parität: nächste Boundary die zur Parität passt
    next_num = cycle_num + 1
    next_boundary = float(next_num * SLOT)
    if (next_num % 2 == 0) != target_even:
        next_boundary += SLOT
    return next_boundary
```

### 2.4 `_next_slot_action()`

```python
def _next_slot_action(self) -> tuple[bool, bool]:
    with self._lock:
        is_tx = self._TX_PATTERN[self._slot_index]
        if not is_tx:
            return False, False  # Parität egal
        # Block 1 Pos 0=E, Pos 1=O. Block 2 Pos 0=O, Pos 1=E.
        if self._block == 1:
            target_even = (self._slot_index == 0)
        else:
            target_even = (self._slot_index == 1)
        return True, target_even
```

### 2.5 `start()` / `stop()` / `pause()` / `resume_after_qso()`

```python
def start(self, next_is_even: bool | None = None) -> None:
    """OMNI starten. next_is_even bestimmt Block. None = automatisch."""
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
        self._cq_audio_hz = None
        self._stop_event.clear()
        self._running = True
    self._thread = threading.Thread(target=self._worker_loop, daemon=True)
    self._thread.start()
    self.omni_started.emit()
    logger.info(f"[OMNI-CQ] Start (next_even={next_is_even} → Block {self._block})")


def stop(self, reason: str) -> None:
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
    logger.info(f"[OMNI-CQ] Stop ({reason})")


def pause(self) -> None:
    """OMNI pausiert (QSO startet). Worker terminiert, _slot_index friert."""
    with self._lock:
        if not self._running:
            return
        if self._paused:
            return
        self._paused = True
    self._stop_event.set()
    if self._thread is not None:
        self._thread.join(timeout=2.0)
        self._thread = None
    self._stop_event.clear()  # für resume_after_qso bereit
    logger.info("[OMNI-CQ] Pause (QSO läuft)")


def resume_after_qso(self, last_qso_was_even: bool) -> None:
    """Nach QSO neu starten — Block-Wahl nach letztem QSO-Slot.
    Mike-Spec: endet auf Even → Block 2. Endet auf Odd → Block 1."""
    with self._lock:
        if not self._paused:
            return
        # R1 R3: alten Worker joinen falls noch lebt (defense-in-depth)
        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=2.0)
            self._thread = None
        self._paused = False
        self._running = False  # Reset für sauberen start()
    # Block-Wahl: gegenüberliegend zu last_qso_was_even
    next_is_even = not last_qso_was_even
    self.start(next_is_even=next_is_even)
    logger.info(f"[OMNI-CQ] Resume (last_even={last_qso_was_even} → next_even={next_is_even})")


def is_active(self) -> bool:
    with self._lock:
        return self._running

def is_paused(self) -> bool:
    with self._lock:
        return self._paused
```

### 2.6 `_maybe_recheck_freq()`

```python
def _maybe_recheck_freq(self) -> None:
    """Alle _BLOCKS_PER_FREQ_RECHECK (4) Blöcke Sticky-Gap-Algo prüfen."""
    if self._block_count == 0 or self._block_count % self._BLOCKS_PER_FREQ_RECHECK != 0:
        return
    new_freq = self._diversity.get_free_cq_freq()
    if new_freq is None:
        return  # kein Histogramm — sticky bleibt
    if new_freq != self._cq_audio_hz:
        logger.info(f"[OMNI-CQ] Freq {self._cq_audio_hz} → {new_freq} Hz (Block {self._block_count})")
        self._cq_audio_hz = new_freq
        self.cq_freq_changed.emit(new_freq)
```

### 2.7 `_slot_label()`

```python
def _slot_label(self, is_tx: bool, target_even: bool) -> str:
    parity = "E" if target_even else "O"
    kind = "TX" if is_tx else "RX"
    return f"B{self._block} [{self._slot_index}/4] {kind}-{parity}"
```

---

## 3. Schnittstellen-Diffs (Compact-fest)

### 3.1 `core/encoder.py` — atomare `transmit`-API (V2-L2)

```python
# encoder.py:189 (transmit) — ATOMAR mit optionalen Setter-Params
def transmit(
    self,
    message: str,
    *,
    tx_even: bool | None = None,
    audio_freq_hz: int | None = None,
) -> bool:
    """Atomic transmit — setzt tx_even + audio_freq_hz UNTER Lock,
    dann startet Worker. Returnt True wenn akzeptiert, False wenn busy.

    Backward-compat: bestehende Aufrufer ohne kwargs unverändert.
    """
    with self._tx_lock:
        if self._is_transmitting:
            return False  # SKIP
        if tx_even is not None:
            self.tx_even = tx_even
        if audio_freq_hz is not None:
            self.audio_freq_hz = audio_freq_hz
        # ... bestehender Worker-Start
    return True
```

**Zusätzlich raus aus `core/encoder.py`** (P2.OMNI-PATTERN-FIX-Reste):
- `_pending_tx_message`-Queue
- Outer-Loop in `_tx_worker` (zurück zu single-pass)
- `request_replace`-Pfad bleibt (P1.9-Fix CQ-Reply)

### 3.2 `core/qso_state.py` — Rückbau OMNI-Reste

```python
# RAUS:
# - _omni_skip_state_change-Flag-Init + alle Aufrufe
# - _was_pretriggered-Flag + on_cycle_end CQ_WAIT-Schutz
# Zurück zu Zustand vor v0.95.22 (P1.OMNI-START).
```

### 3.3 `ui/main_window.py` — OMNI-Init + Toggle + Stop-Trigger

```python
# __init__: ersetze omni_tx-Block (Z.273-278) durch
# (HINWEIS: muss NACH self.encoder/self.timer/self._diversity_ctrl-Init
#  stehen — also ab Z.~280, nicht früher):
from core.omni_cq import OmniCQ
self._omni_cq = OmniCQ(
    encoder=self.encoder,             # main_window.py:122
    diversity_ctrl=self._diversity_ctrl,  # main_window.py:218
    timer=self.timer,                 # main_window.py:120 (NICHT _timer!)
    my_call=self.settings.callsign,   # config/settings.py:129
    my_grid=self.settings.locator,    # config/settings.py:133 (Funker-Grid = Locator)
)
self._omni_cq.omni_stopped.connect(self._on_omni_stopped)
self._omni_cq.cq_freq_changed.connect(self._on_omni_freq_changed)
self._omni_cq.counter_changed.connect(self._on_omni_counter_changed)
self._omni_cq.slot_action.connect(self._on_omni_slot_action)
self.control_panel.btn_omni_cq.toggled.connect(self._on_btn_omni_cq_toggled)

# RAUS aus __init__:
# - _omni_tx Block (Z.273-278)
# - _omni_pretriggered (Z.232) RAUS
# - _omni_pretrigger_timer + .timeout.connect (Z.241-245) RAUS
# - _omni_was_active_pre_qso BLEIBT (Z.226, Init=False, OK)

# _on_btn_omni_cq_toggled neu (Z.700-740 Rewrite):
def _on_btn_omni_cq_toggled(self, checked: bool):
    if checked and not self._omni_cq.is_active():
        # Auto-Hunt gegenseitig stoppen (V2-L9, AC11c)
        if self._auto_hunt.active:
            self._auto_hunt.stop_auto_hunt("superseded")  # NICHT cancel() — existiert nicht!
        self._omni_cq.start()  # next_is_even auto
        self.control_panel.update_omni_tx(True)
    elif not checked and self._omni_cq.is_active():
        self._omni_cq.stop("manual_halt")

# _on_omni_stopped neu (Z.742-776 Rewrite, R1 R4!):
def _on_omni_stopped(self, reason: str):
    btn = self.control_panel.btn_omni_cq
    btn.blockSignals(True)
    btn.setChecked(False)
    btn.blockSignals(False)
    # R1 R4 KRITISCH: explizit reset, sonst Caller-Queue-QSO nach Stop
    # könnte fälschlich OMNI resumen via _maybe_resume_omni
    self._omni_was_active_pre_qso = False
    self._last_qso_tx_even = None  # Defense-in-Depth (V2-L3)
    self.control_panel.update_omni_tx(False)
    self._update_statusbar()
    print(f"[OMNI-CQ] gestoppt (reason={reason})")

# _on_omni_freq_changed (NEU):
def _on_omni_freq_changed(self, freq_hz: int):
    """OMNI hat neue CQ-Audiofrequenz gewählt (Sticky-Gap-Algo).
    Statusbar-Update + Log."""
    print(f"[OMNI-CQ] CQ-Audiofrequenz: {freq_hz} Hz")
    self._update_statusbar()  # Anzeige falls UI hier was zeigt

# _on_omni_counter_changed (NEU):
def _on_omni_counter_changed(self, even: int, odd: int):
    """Statusbar Ω Even=X Odd=Y aktualisieren (existing _update_statusbar
    liest Counter aus self._omni_cq direkt, deshalb hier nur trigger)."""
    self._update_statusbar()

# _on_omni_slot_action (NEU, V2-L8 + Mike v0.95.25):
def _on_omni_slot_action(self, label: str, is_tx: bool, target_even: bool):
    """OMNI-Worker emittet Slot-Action — RX-Slots als „Horche..." anzeigen.
    TX-Slots laufen schon über cycle_decoded → add_tx im qso_panel."""
    if not is_tx:
        # add_listening(slot_start_ts, tx_even) — Parameter ist Slot-Parität für E/O-Tag
        import time as _time
        self.qso_panel.add_listening(_time.time(), target_even)

# _update_statusbar — Ω-Anzeige migrieren (existing Z.1004-1006):
# ALT: if getattr(self, '_omni_tx', None) and self._omni_tx.active:
#          omni_str = f"  Ω Even={self._omni_tx.cq_even_count} Odd={self._omni_tx.cq_odd_count}"
# NEU: if self._omni_cq.is_active():
#          omni_str = f"  Ω Even={self._omni_cq._cq_even_count} Odd={self._omni_cq._cq_odd_count}"
# (private-Attribut-Zugriff OK weil same Process; alternativ public Property
#  auf OmniCQ ergänzen)

# Stop-Trigger (Code-Stellen mit Zeilen):
# - mw_radio._on_band_changed Z.275: am Anfang `if self._omni_cq.is_active(): self._omni_cq.stop("band_change")`
# - mw_radio._on_mode_changed Z.199: am Anfang `if self._omni_cq.is_active(): self._omni_cq.stop("mode_change")`
# - mw_radio._on_rx_mode_changed Z.392: am Anfang `if self._omni_cq.is_active(): self._omni_cq.stop("rx_mode_change")`
# - main_window._on_presence_tick Z.1128 ersetze (Z.1144) `_omni_tx.stop_omni_tx("totmann_expired")` durch `self._omni_cq.stop("totmann_expired")`

# Auto-Hunt-Coupling V2-L9 — main_window._on_btn_auto_hunt_toggled (Z.782 existing):
# ALT (Z.788-789):
#     if self._omni_tx.active:
#         self._omni_tx.stop_omni_tx("superseded")
# NEU:
#     if self._omni_cq.is_active():
#         self._omni_cq.stop("superseded")
```

### 3.4 `ui/mw_qso.py` — Pause/Resume + Listener-Verschiebung + HALT

```python
# _pause_omni_if_active (Z.34) — API-Migration omni_tx → omni_cq:
def _pause_omni_if_active(self) -> None:
    if self._omni_cq.is_active() and not self._omni_cq.is_paused():
        self._omni_cq.pause()
        self._omni_was_active_pre_qso = True

# _maybe_resume_omni (Z.49) — Caller-Queue Pop+start_qso (V2-L10!):
def _maybe_resume_omni(self) -> None:
    if not getattr(self, '_omni_was_active_pre_qso', False):
        return
    # V2-L10: Bei OMNI ist cq_mode=False → qso_state._resume_cq_if_needed
    # arbeitet die Caller-Queue NICHT ab. mw_qso übernimmt das selbst.
    if self.qso_sm._caller_queue:
        next_msg = self.qso_sm._caller_queue.pop(0)
        self.qso_sm.queue_changed.emit(
            [m.caller for m in self.qso_sm._caller_queue])
        # Slot-Parität für Antwort setzen (R1 R2 äquivalent zu Hunt-Klick)
        their_even = getattr(next_msg, '_tx_even', None)
        if their_even is not None:
            self.encoder.tx_even = not their_even
        else:
            self.encoder.tx_even = None
        # OMNI bleibt pausiert (idempotent — _omni_was_active_pre_qso bleibt True)
        # Nach diesem QSO greift _maybe_resume_omni erneut.
        self.qso_sm.start_qso(
            their_call=next_msg.caller,
            their_grid=next_msg.grid_or_report if next_msg.is_grid else "",
            freq_hz=next_msg.freq_hz,
            their_snr=next_msg.snr,
        )
        return
    # Queue leer → echtes Resume mit Block-Wahl
    last_qso_was_even = bool(getattr(self, '_last_qso_tx_even', True))
    self._omni_cq.resume_after_qso(last_qso_was_even)
    self._omni_was_active_pre_qso = False

# _on_tx_finished (Z.328) — V2-L3 _last_qso_tx_even merken:
def _on_tx_finished(self):
    # ... bestehender Code
    self._last_qso_tx_even = bool(self.encoder.tx_even)

# _on_send_message (Z.342) — OMNI-Bypass-Block KOMPLETT RAUS
# (Z.340-410 mit if self._omni_tx.active... wegmachen)

# _on_cancel HALT (Z.250):
def _on_cancel(self):
    # ... bestehender Code (CQ + QSO + Auto-Hunt)
    if self._omni_cq.is_active():
        self._omni_cq.stop("manual_halt")
    self._omni_was_active_pre_qso = False
    self._last_qso_tx_even = None
    # ...
```

### 3.5 `ui/mw_cycle.py` — Listener-Pfad (R1 R2!) + Pretrigger RAUS

```python
# on_message_decoded (Z.909) — OMNI-Antwort-Check VOR qso_sm.on_message_received:
def on_message_decoded(self, msg: FT8Message):
    if not self.rx_panel._rx_active:
        return
    self.control_panel.update_snr(msg.snr)
    self.qso_sm.set_last_snr(msg.snr)
    if msg.target == self.settings.callsign:
        self.qso_panel.add_rx(...)  # bestehend

    # P4.OMNI-NEUBAU: Listener-Pfad VOR qso_sm.on_message_received
    # - aktiviert nur wenn OMNI live + nicht pausiert
    # - reagiert nur auf direkte CQ-Antworten an uns (kein 73, kein RR73)
    if (self._omni_cq.is_active() and not self._omni_cq.is_paused()
            and msg.target == self.settings.callsign
            and not msg.is_73 and not msg.is_rr73):
        self._omni_cq.pause()
        # R1 R2 KRITISCH: encoder.tx_even auf Gegenparität setzen
        # (analog zu Hunt-Klick mw_qso.py:171-176, sonst sendet Hunt
        #  auf falschem Slot)
        their_even = getattr(msg, '_tx_even', None)
        if their_even is not None:
            self.encoder.tx_even = not their_even
        else:
            self.encoder.tx_even = None
        self.qso_sm.start_qso(
            their_call=msg.caller,
            their_grid=msg.grid_or_report if msg.is_grid else "",
            freq_hz=msg.freq_hz,
            their_snr=msg.snr,
        )
        # _omni_was_active_pre_qso wird in _pause_omni_if_active gesetzt;
        # hier explizit weil wir nicht über mw_qso laufen:
        self._omni_was_active_pre_qso = True  # Attr lebt in main_window
        # NICHT mehr qso_sm.on_message_received — start_qso konsumiert
        return

    self.qso_sm.on_message_received(msg)

# _omni_pretrigger_check + _omni_pretrigger_fire_impl + Aufruf in
# _on_cycle_decoded + Aufruf in _on_cycle_start: ALLE RAUS (Z.586-700)
# _on_cycle_start: omni_tx.advance() RAUS (Z.700)
```

### 3.6 OMNI-RX-Slot „Horche..."-Anzeige (V2-L8)

Bereits in §3.3 oben unter `_on_omni_slot_action` spezifiziert (mit
`time.time()` als slot_start_ts und `target_even` aus Worker-Signal,
das via `timer.is_even_cycle()` die echte UTC-Slot-Parität trägt).
`add_listening`-Signatur: `(slot_start_ts: float, tx_even: bool)`
— Parameter-Name ist `tx_even`, semantisch = Slot-Parität für E/O-Tag
(qso_panel.py:202, seit v0.95.25).

### 3.7 Listener-Pfad: encoder.audio_freq_hz NICHT setzen

**Wichtig (KISS):** Der Listener-Pfad in `mw_cycle.on_message_decoded`
setzt NUR `encoder.tx_even`, NICHT `encoder.audio_freq_hz`. Encoder
behält OMNI's letzten `_cq_audio_hz`-Wert (vom letzten OMNI-TX). Damit
läuft die Hunt-Pipeline auf der gleichen Audiofrequenz wie OMNI gerade
gesendet hat — Mike-Spec konform: „QSO bleibt auf gleicher Frequenz".

Gleiches gilt für `_maybe_resume_omni` Caller-Queue-Pop-Pfad (§3.4):
nur `encoder.tx_even`, KEIN `audio_freq_hz`.

---

## 4. Akzeptanzkriterien (final)

### Funktional

- **AC1** Klick btn_omni_cq → OMNI startet, Label „OMNI CQ (aktiv)", Ω in Statusbar.
- **AC2** Block-Wahl Start: nächster Slot Even → Block 1 (TX-E TX-O ...). Odd → Block 2.
- **AC3** 5-Slot-Pattern: 2 TX → 3 RX → Block-Wechsel (slot_index 4→0). Block 1↔2 permanent.
- **AC4** OMNI-TX auf fester Audiofrequenz Block-lang. Initial aus `diversity.get_free_cq_freq()`.
- **AC4b** Fallback **1500 Hz** + Log-Warning wenn `get_free_cq_freq()` returnt None (V2-L4).
- **AC5** Frequenz-Recheck alle 4 Blöcke (Mike-Spec). Sticky bleibt wenn frei, wechselt wenn voll.
- **AC6** Während QSO: NIEMALS Frequenz-Wechsel (Worker pausiert).
- **AC7** Antwort an uns → OMNI pausiert + `encoder.tx_even = not msg._tx_even` + `qso_state.start_qso(...)`. **R1 R2!**
- **AC8** Nach QSO: `omni_cq.resume_after_qso(last_qso_was_even)` mit Block-Wahl:
  - QSO endete auf Even → Block 2 (Odd-First) ab Pos 0
  - QSO endete auf Odd → Block 1 (Even-First) ab Pos 0
- **AC9** OMNI startet IMMER ab Pos 0 — nie mittendrin.
- **AC10** Caller-Queue Vorrang: nicht leer → mw_qso pop-Pfad mit `start_qso` direkt + Slot-Parität setzen, OMNI bleibt pausiert. **V2-L10!**
- **AC10b** `_on_qso_timeout` ruft `_maybe_resume_omni` mit `last_qso_tx_even` aus encoder (Edge-Case dokumentiert, V2-L3).
- **AC11** Stop-Bedingungen: `manual_halt`, `band_change`, `mode_change`, `rx_mode_change`, `totmann_expired` — alle sofort, Worker terminiert.
- **AC11b** RX-Slots werden im QSO-Panel als „Horche..." angezeigt (V2-L8 + Mike v0.95.25 Wunsch).
- **AC11c** Auto-Hunt + OMNI gegenseitig exklusiv: `_on_btn_omni_cq_toggled(True)` stoppt Auto-Hunt; `_on_btn_auto_hunt_toggled(True)` stoppt OMNI mit reason `superseded` (V2-L9).
- **AC12** Kein `qso_state.cq_mode = True` während OMNI. `cq_mode` exklusiv für Normal-CQ.
- **AC13** Hardware-Garantie: alle TX über `Encoder.transmit()` → ANT1 zentral.
- **AC14** App-Start: OMNI immer inactive (kein Settings-Persist, V2-L20).
- **AC15** `encoder.transmit` atomare API (`tx_even=`, `audio_freq_hz=` optional, V2-L2).

### R1-Findings

- **AC-R1** `_OMNI_TX_PRELEAD_S = 2.0` (von 1.5 erhöht, 0.7s Marge zu Encoder-Wake bei 1.3s).
- **AC-R2** Listener `mw_cycle.on_message_decoded` setzt `encoder.tx_even` VOR `start_qso` analog Hunt-Klick (mw_qso.py:171-176).
- **AC-R3** `resume_after_qso` joint alten Worker (defense-in-depth).
- **AC-R4** `_on_omni_stopped` setzt `_omni_was_active_pre_qso = False` explizit.
- **AC-R5** 2 Antworten in 1 RX-Slot: erste startet QSO, zweite ignoriert (akzeptabel, dokumentiert).

### Final-R1 nicht-blockierende Hinweise (in Code-Phase mitnehmen)

- **F-1** `getattr(msg, '_tx_even', None)`-Pattern in §3.4 + §3.5 ist
  bereits Defense-in-Depth. `_tx_even` wird im Decoder via
  `_assign_slot_parity` immer gesetzt (verifiziert) — Fallback `None`
  → `encoder.tx_even = None` ist die saubere „nächster Slot egal"-Semantik.
- **F-2** `encoder.tx_even` direkt-Setzen in Listener + `_maybe_resume_omni`
  ist unter GIL atomic + symmetrisch zu existierendem Hunt-Klick (mw_qso:173).
  Kein Race in der Praxis. Konsequente atomare API später (separater Refactor).
- **F-3** Edge-Case-Tests für **Bandwechsel-mid-TX** + **Caller-Queue-nach-OMNI-Stop**
  (sollte NICHT resumen) für Field-Test notiert — nicht in C2/C6 Test-Plan
  weil verhalten-akzeptiert + Field-Test verifizierbar.
- **F-4** `FT8Message._tx_even`-Garantie bleibt undokumentiert in Code-Doku
  (nice-to-have-Kommentar-Ergänzung in `core/message.py` während C6).

### Architektur

- **AC16** Eigenes Modul `core/omni_cq.py`. KEIN Code-Sharing mit `qso_state.cq_mode`.
- **AC17** Eigener Worker-Thread mit absolut-UTC-Boundaries. KEIN cycle_tick / KEIN QTimer.
- **AC18** Übergabe an Hunt via `qso_state.start_qso(...)` — gleicher Eingang wie Hunt-Klick.

---

## 5. Test-Plan (final, ~27 neue + 2 R1-ergänzt = 29 neu, -81 alte raus)

### Unit-Tests `tests/test_omni_cq_worker.py` (NEU)

| # | Test | AC |
|---|---|---|
| T1 | `test_initial_state_inactive` | AC14 |
| T2 | `test_start_with_next_is_even_block1` | AC2 |
| T3 | `test_start_with_next_is_odd_block2` | AC2 |
| T4 | `test_next_slot_action_block1_pattern` (parametrize 0..4) | AC3 |
| T5 | `test_next_slot_action_block2_pattern` (parametrize 0..4) | AC3 |
| T6 | `test_block_rollover_after_5_slots` | AC3 |
| T7 | `test_resume_after_qso_even_chooses_block2` | AC8 |
| T8 | `test_resume_after_qso_odd_chooses_block1` | AC8 |
| T9 | `test_resume_starts_from_pos_0_always` | AC9 |
| T10 | `test_pause_freezes_state` | AC7 |
| T11 | `test_stop_cleans_state` (parametrize alle 5 reasons) | AC11 |
| T12 | `test_freq_recheck_every_4_blocks` | AC5 |
| T13 | `test_freq_sticky_when_unchanged` | AC5 |
| T14 | `test_freq_changes_when_diversity_returns_new` | AC5 |
| T15 | `test_freq_fallback_when_diversity_returns_none` | AC4b |
| T16 | `test_compute_next_boundary_target_even` (parametrize) | (Math) |
| T17 | `test_compute_next_boundary_rx_no_filter` | (Math) |
| T18 | `test_atomic_transmit_api_tx_even_kwarg` | AC15 (R1) |
| T19 | `test_atomic_transmit_api_audio_freq_kwarg` | AC15 (R1) |
| T20 | `test_resume_joins_old_worker` | AC-R3 |

### Integration-Tests `tests/test_omni_cq_integration.py` (NEU)

| # | Test | AC |
|---|---|---|
| I1 | `test_toggle_button_starts_omni` | AC1 |
| I2 | `test_toggle_button_stops_omni_manual_halt` | AC11 |
| I3 | `test_band_change_stops_omni` | AC11 |
| I4 | `test_mode_change_stops_omni` | AC11 |
| I5 | `test_rx_mode_diversity_to_normal_stops_omni` | AC11 |
| I6 | `test_listener_pauses_omni_and_sets_tx_even` | AC7 + AC-R2 |
| I7 | `test_qso_complete_resumes_omni_with_block_choice` | AC8 |
| I8 | `test_caller_queue_pops_via_mw_qso_keeps_omni_paused` | AC10 |
| I9 | `test_no_cq_mode_during_omni` | AC12 |
| I10 | `test_halt_stops_omni_and_clears_pre_qso_flag` | AC11 + AC-R4 |
| I11 | `test_auto_hunt_toggle_stops_omni_superseded` | AC11c |
| I12 | `test_omni_toggle_stops_auto_hunt` | AC11c |
| I13 | `test_rx_slot_emits_horche_to_qso_panel` | AC11b |
| I14 | `test_omni_stopped_resets_was_active_pre_qso_flag` | AC-R4 |

### Migration: alte OMNI-Tests RAUS (V2-L11)

- `tests/test_p1_omni_start.py` — RAUS (~11 Tests)
- `tests/test_p2_omni_redesign.py` — RAUS (~20 Tests)
- `tests/test_p2_omni_pattern_fix.py` — RAUS (~16 Tests)
- `tests/test_p3_omni_pattern_fix2.py` — RAUS (~21 Tests)
- `tests/test_omni_tx.py` — RAUS (~4 Tests)
- `tests/test_encoder_queue.py` — RAUS (~9 Tests)

**Test-Bilanz:** -81 alte, +29 neue (20 unit + 14 integration - 5 doppelte parametrize) → netto **-52**.
**Erwartet: 1069 → ~1017 Tests grün.**

---

## 6. Field-Test-Plan (Mike, vor Push)

**Vorbedingungen:**
- App auf Stand v0.96.0 (nach allen 8 Commits, alle Tests grün)
- IC-7300 / DA1TST als Test-Gegenstation oder echte CQ-Antworten warten
- 40m oder 20m FT8 (Hobby-Use 99 % FT8)
- Diversity-Modus aktiv (Vorbedingung für btn_omni_cq Sichtbarkeit)
- ANT1 als TX-Antenne verifiziert (HW-Garantie)

| # | Aktion | Erwartet | AC |
|---|---|---|---|
| F1 | Diversity_Std + btn_omni_cq → Ω in Statusbar | „OMNI CQ (aktiv)", Even=0/Odd=0 | AC1 |
| F2 | 10-Slot-Loop, **kein Pattern-Drift** ggü v0.95.25 | 4 TX (2× Block 1, 2× Block 2), 6 RX | AC3 |
| F3 | Block 1: TX [E], TX [O], RX [E], RX [O], RX [E] | exakt diese Reihenfolge im QSO-Panel | AC3 |
| F4 | Block 2: TX [O], TX [E], RX [O], RX [E], RX [O] | exakt diese Reihenfolge | AC3 |
| F5 | CQ-Antwort mid-OMNI: Pause + QSO + RR73 | Hunt läuft Slot-paritäts-konform | AC7+AC-R2 |
| F6 | QSO endet auf Even → Resume mit Block 2 (TX-O zuerst) | nächster TX [O], Pos 0 | AC8 |
| F7 | QSO endet auf Odd → Resume mit Block 1 (TX-E zuerst) | nächster TX [E], Pos 0 | AC8 |
| F8 | btn_omni_cq erneut → Stop, Ω weg | reason `manual_halt` im Log | AC11 |
| F9 | Bandwechsel mid-OMNI → Stop | reason `band_change`, laufender TX läuft Slot zu Ende | AC11 + R10 |
| F10 | Mode Diversity → Normal → Stop | reason `mode_change` | AC11 |
| F11 | 15 min ohne Eingabe + ohne QSO → Totmann-Stop | reason `totmann_expired` | AC11 |
| F12 | 4 Blöcke Wartezeit → Log-Eintrag „Sticky" oder „Switch" | logger.info Zeile mit Hz-Werten | AC5 |
| F13 | RX-Slots im QSO-Panel als „Horche..." sichtbar | Format `HH:MM:SS [E/O] ←  Horche  …` Grau | AC11b |
| F14 | btn_auto_hunt klicken während OMNI aktiv → OMNI stoppt mit `superseded` | Ω verschwindet, Auto-Hunt läuft | AC11c |
| F15 | btn_omni_cq klicken während Auto-Hunt aktiv → Auto-Hunt stoppt | Auto-Hunt-Indikator weg, Ω erscheint | AC11c |
| F16 | 2 Antworten in 1 RX-Slot (Even+Odd gleichzeitig dekodiert) | erste startet QSO, zweite ignoriert (V3 R5 dokumentiert) | AC-R5 |
| F17 | Caller-Queue: während QSO läuft, 2. Anrufer kommt → nach QSO direkt 2. QSO, danach OMNI-Resume | Ω bleibt aus während 2. QSO | AC10 |

---

## 7. Risiken / Edge-Cases (R1-R5 dokumentiert)

| # | Risiko | Schweregrad | Mitigation |
|---|---|---|---|
| **R1** | OS-Scheduling-Delay > 0.2s Marge → Pattern-Drift | ⛔ behoben | `_OMNI_TX_PRELEAD_S = 2.0` (0.7s Marge zu Encoder-Wake 1.3s) |
| **R2** | Listener vergisst `encoder.tx_even` vor `start_qso` → Hunt-Pfad sendet auf falschem Slot | ⛔ behoben | mw_cycle.on_message_decoded setzt `not msg._tx_even` analog mw_qso:171-176 |
| **R3** | `resume_after_qso` während alter Worker noch lebt → Doppel-Worker | ⚠️ behoben | `resume_after_qso` joint alten Worker vor `start()` |
| **R4** | `_omni_was_active_pre_qso` bleibt True nach Stop → Caller-Queue-QSO triggert fälschlich Resume | ⚠️ behoben | `_on_omni_stopped` setzt explizit False |
| **R5** | 2 Antworten in 1 RX-Slot — zweite ignoriert | dokumentiert | Hobby-Tool-Kompromiss (akzeptabel). AC-R5 + Field-Test-Beobachtung. |
| R6 | Worker-Race pause+stop gleichzeitig | OK | RLock + 2.0s Join-Timeout, idempotent Guards |
| R7 | Encoder belegt bei OMNI-TX-Trigger | OK | encoder.transmit thread-safe + SKIP. OMNI verliert 1 Slot → Log-Warning |
| R8 | Decoder noch nicht ready bei OMNI-TX-Wake | OK | Worker wakes 2.0s vor Boundary, Decoder ready bei boundary-0.5s. 1.5s Marge |
| R9 | App-Crash + State-Persist | OK | OMNI startet immer inactive (AC14) |
| R10 | Bandwechsel mid-OMNI-TX | OK | Encoder-TX läuft Slot zu Ende, dann Stop (V2-L16) |
| R11 | Hardware ANT2 für TX | OK | encoder.transmit erzwingt ANT1, OMNI emittet kein TX direkt |

---

## 8. BLEIBT vs RAUS (final)

### NEU
- `core/omni_cq.py` (~350 Z.)
- `tests/test_omni_cq_worker.py` (20 Tests)
- `tests/test_omni_cq_integration.py` (14 Tests)

### UMGEBAUT
- `core/encoder.py` — `transmit` atomare API (kwargs), Queue+Outer-Loop raus
- `core/qso_state.py` — `_omni_skip_state_change`, `_was_pretriggered`, on_cycle_end OMNI-Schutz raus
- `ui/main_window.py` — OmniCQ-Init, `_on_btn_omni_cq_toggled`, `_on_omni_stopped` (R1 R4), `_on_omni_slot_action` NEU
- `ui/mw_qso.py` — `_pause_omni_if_active` API, `_maybe_resume_omni` Caller-Queue-Pop (V2-L10), `_on_tx_finished` `_last_qso_tx_even` merken, `_on_send_message` OMNI-Bypass raus, `_on_cancel` HALT API
- `ui/mw_cycle.py` — `on_message_decoded` Listener-Pfad (R1 R2), `_omni_pretrigger_*` raus, `_on_cycle_start` `omni_tx.advance` raus
- `ui/mw_radio.py` — Stop-Trigger-Aufrufe `omni_tx` → `omni_cq`

### KOMPLETT GELÖSCHT
- `core/omni_tx.py`
- `tests/test_p1_omni_start.py`
- `tests/test_p2_omni_redesign.py`
- `tests/test_p2_omni_pattern_fix.py`
- `tests/test_p3_omni_pattern_fix2.py`
- `tests/test_omni_tx.py`
- `tests/test_encoder_queue.py`

### BLEIBT UNVERÄNDERT
- `core/qso_state.start_qso/start_cq/stop_cq/_send_cq` (Hunt + Normal-CQ exklusiv)
- `core/encoder._next_slot_boundary` (Vorbild) + `request_replace` (P1.9)
- `core/diversity.get_free_cq_freq`
- `core/timing.FT8Timer`
- Hunt-State-Machine

---

## 9. Atomare Commits (V2-L18 + R1-Bestätigung)

| C# | Inhalt | Files | Tests grün? |
|---|---|---|---|
| **C1** | Migration alte OMNI-Tests RAUS (~81 Tests) | 6 Test-Files gelöscht | ✅ ja, weniger Tests |
| **C2** | NEU `core/omni_cq.py` + 20 Unit-Tests | omni_cq.py, test_omni_cq_worker.py | ✅ ja, neue Tests grün |
| **C3** | Atomare `encoder.transmit` API + `_pending_tx_message`-Queue raus | core/encoder.py | ✅ ja |
| **C4** | Rückbau `core/qso_state.py` (`_omni_skip_state_change` + `_was_pretriggered` raus) | core/qso_state.py | ✅ ja |
| **C5** | Rückbau `ui/mw_cycle.py` (`_omni_pretrigger_*` + `omni_tx.advance` raus) | ui/mw_cycle.py | ✅ ja |
| **C6** | Anschluss `main_window.py` + `mw_qso.py` (OMNI-Init, Toggle, Listener-Pfad, Pause/Resume, HALT, Caller-Queue) + 14 Integration-Tests | main_window, mw_qso, mw_cycle (Listener), test_omni_cq_integration.py | ✅ ja |
| **C7** | Stop-Trigger `mw_radio.py` (band/mode/rx_mode) + main_window (Auto-Hunt-Coupling Z.788-789 + `_on_presence_tick` Z.1144) | ui/mw_radio.py, ui/main_window.py | ✅ ja |
| **C8** | Löschen `core/omni_tx.py` + APP_VERSION 0.95.25 → 0.96.0 + Doku (HISTORY+HANDOFF+CLAUDE+Memory) | core/omni_tx.py gelöscht, main.py, Doku | ✅ ja |

8 atomare Commits (V2-L18 hatte 7, +1 für `core/omni_tx.py`-Löschung sauber separat).

### 9.1 Code-Phase-Helper (KI-Cold-Start)

**Test-Aufruf nach jedem Commit:**
```bash
cd "/Users/mikehammerer/Documents/KI N8N Projekte/FT8/SimpleFT8"
QT_QPA_PLATFORM=offscreen ./venv/bin/python3 -m pytest tests/ -q
```
Erwartung: alle Tests grün. Falls rot → STOPP, analyse, Fix, dann Commit.

**Mock-Strategie für `tests/test_omni_cq_worker.py` (Unit):**
- `encoder` = `unittest.mock.MagicMock()` mit `.transmit.return_value = True` und `.tx_even`, `.audio_freq_hz` als Attribute
- `diversity_ctrl` = `MagicMock()` mit `.get_free_cq_freq.return_value = 1500` (Default) — pro Test überschreiben
- `timer` = `MagicMock(spec=FT8Timer)` mit `.cycle_duration = 15.0`, `.is_even_cycle.return_value = False` (Default)
- Worker-Lifecycle: `omni.start()` startet Thread → in Tests via `time.sleep(0.05)` warten oder `omni._thread.join(timeout=0.1)` nach `omni.stop()`
- Slot-Boundary-Math testbar via `omni._compute_next_boundary(target_even)` direkt aufrufen mit gemocktem `time.time()` (monkeypatch oder freezegun)

**Mock-Strategie für `tests/test_omni_cq_integration.py`:**
- pytest-qt `qtbot` für MainWindow-Setup (existing pattern in tests/test_p3_omni_pattern_fix2.py)
- `MainWindow(...)` init + `omni._omni_cq` ist real, encoder/timer/diversity gemockt
- Toggle-Tests: `qtbot.mouseClick(window.control_panel.btn_omni_cq, Qt.LeftButton)` oder `btn.toggled.emit(True)`

**Commit-Message-Template (CLAUDE.md-konform):**
```
P4.OMNI-NEUBAU C{N}: {Kurztitel}

{1-3 Zeilen Begründung — was, warum, R1-/V2-Referenz wenn relevant}

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
```
Beispiel C2: „P4.OMNI-NEUBAU C2: NEU core/omni_cq.py + 20 Unit-Tests"

**Doku-Update-Strategie:**
- C1-C7: KEINE Doku-Updates während des Refactors (verhindert Konflikt-Commits)
- C8: ALLE Doku-Updates konsolidiert:
  - HISTORY.md: `## 2026-05-XX v0.96.0 — P4.OMNI-NEUBAU` Eintrag (alle 8 Commits + Test-Bilanz + Field-Test-Status)
  - HANDOFF.md (BEIDE Pfade laut CLAUDE.md): SimpleFT8/HANDOFF.md + FT8/HANDOFF.md → aktueller Stand v0.96.0, nächster Schritt = Field-Test
  - CLAUDE.md: `Aktueller Stand` Header + Test-Count
  - Memory: dieses File `project_p4_omni_neubau.md` als ✅ erledigt umtaggen + Lesson aus Code-Phase wenn überraschende Findings

**App-Sicherung vor C1 (optional):** `Appsicherungen/2026-05-XX_vor_p4_omni_neubau/` wäre sauber, aber tägliches SSD-Backup (05:00, CLAUDE.md) deckt das ab. Bei Bedarf manuell triggern.

**Push-Bedingung:** ⛔ KEIN `git push` vor Mike-Field-Test grün. CLAUDE.md: „`git push`... nur nach expliziter Anfrage von Mike."

---

## 10. APP_VERSION

`v0.95.25 → v0.96.0` (Minor-Bump: Architektur-Refactor + neues Feature).
Datei: `main.py` Z.~7-10 erste Konstante nach Imports — `APP_VERSION = "0.96.0"`.

---

## 11. Workflow-Status

- ✅ Schritt 0 — Code-Verifikation
- ✅ V1
- ✅ V2 (20 Lessons L1-L20)
- ✅ R1 (DeepSeek-Reasoner: 17/20 ✅, 2 ⛔ + 3 ⚠️ Findings R1-R5)
- ✅ V3 (dieses Dokument — Compact-fest)
- ✅ Final-R1 (`prompts/p4_omni_neubau_final_r1.md`: „implementierungsreif", 0 KP, 4 nicht-blockierende Hinweise F-1...F-4 oben)
- ✅ Mike-Freigabe (09.05.2026 Abend)
- ⏳ Compact (Trigger nach Compact: **„p4 weiter"** → KI lädt Memory `project_p4_omni_neubau.md` + V3 + Final-R1 → Code-Phase startet mit C1)
- ⏳ Code (8 atomare Commits, V3 §9)
- ⏳ Field-Test (Mike, V3 §6 13-Punkte-Plan)
- ⏳ Doku (HISTORY+HANDOFF+CLAUDE+Memory) + Push

---

**Ende V3.**
