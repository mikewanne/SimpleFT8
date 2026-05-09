"""SimpleFT8 OMNI-CQ — eigenstaendige Slot-getaktete CQ-Pipeline.

Architektur (P4.OMNI-NEUBAU, 09.05.2026):
- Eigenes Modul mit Worker-Thread und absolut-UTC-Slot-Boundaries.
- 5-Slot-Pattern (TX-TX-RX-RX-RX), Block 1 Even-First, Block 2 Odd-First.
- Sticky CQ-Audiofrequenz (`diversity.get_free_cq_freq()`), Recheck alle
  4 Bloecke (~5 Min bei FT8).
- Kein cycle_tick / kein QTimer / kein qso_state.cq_mode-Hack.
- Bei eingehender Antwort: pause() + Uebergabe an qso_state.start_qso()
  ueber den existierenden Hunt-Pfad.
- Block-Wahl nach QSO: endet auf Even -> Block 2, endet auf Odd -> Block 1.

Hardware-Garantie ANT1: OMNI emittet kein TX direkt. TX laeuft via
`encoder.transmit()`, welcher zentral `radio.set_tx_antenna("ANT1")`
setzt. Kein Extra-Check noetig.
"""
from __future__ import annotations

import threading
import time
import logging

from PySide6.QtCore import QObject, Signal


logger = logging.getLogger(__name__)


class OmniCQ(QObject):
    """OMNI-CQ Worker-Thread mit eigener 5-Slot-State-Machine.

    Signals:
        omni_started: () — Worker gestartet.
        omni_stopped: (str) — Stop-Reason ("manual_halt", "band_change", ...).
        slot_action: (str, bool, bool) — (label, is_tx, target_even). target_even
            ist bei TX-Slots die Pattern-Parität; bei RX-Slots die echte
            UTC-Slot-Parität (per `timer.is_even_cycle()` bestimmt).
        cq_freq_changed: (int) — neue CQ-Audiofrequenz in Hz.
        counter_changed: (int, int) — (cq_even, cq_odd).
    """

    omni_started = Signal()
    omni_stopped = Signal(str)
    slot_action = Signal(str, bool, bool)
    cq_freq_changed = Signal(int)
    counter_changed = Signal(int, int)

    # 5-Slot-Pattern (TX-TX-RX-RX-RX). Block 1 Even-First / Block 2 Odd-First.
    _TX_PATTERN = (True, True, False, False, False)
    _BLOCKS_PER_FREQ_RECHECK = 4   # ~5 Min bei FT8 (Mike-Spec)
    # Encoder wacht 1.3s vor Boundary, Worker 2.0s vor Boundary -> 0.7s Marge
    # gegen GUI-Tick-Latency / OS-Scheduling (R1 R1 in V3).
    _OMNI_TX_PRELEAD_S = 2.0
    _FALLBACK_AUDIO_HZ = 1500       # V2-L4: wenn diversity.get_free_cq_freq()=None

    def __init__(self, encoder, diversity_ctrl, timer,
                 my_call: str, my_grid: str):
        super().__init__()
        self._encoder = encoder
        self._diversity = diversity_ctrl
        self._timer = timer
        self._my_call = my_call
        self._my_grid = my_grid

        # Lifecycle
        self._thread: threading.Thread | None = None
        self._running = False
        self._paused = False
        self._stop_event = threading.Event()
        self._lock = threading.RLock()

        # Pattern-State
        self._slot_index = 0
        self._block = 1               # 1=Even-First, 2=Odd-First
        self._block_count = 0         # fuer Frequenz-Recheck

        # Counters
        self._cq_even_count = 0
        self._cq_odd_count = 0

        # Audiofrequenz (sticky bis Recheck oder Kollision)
        self._cq_audio_hz: int | None = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def start(self, next_is_even: bool | None = None) -> None:
        """OMNI starten. next_is_even bestimmt Block; None = automatisch
        anhand `timer.is_even_cycle()` (aktuelle Paritaet)."""
        with self._lock:
            if self._running:
                return
            if next_is_even is None:
                # is_even_cycle ist aktueller Slot -> next ist invertiert.
                next_is_even = not self._timer.is_even_cycle()
            self._block = 1 if next_is_even else 2
            self._slot_index = 0
            self._block_count = 0
            self._cq_even_count = 0
            self._cq_odd_count = 0
            self._cq_audio_hz = None
            self._paused = False
            self._stop_event.clear()
            self._running = True
        self._thread = threading.Thread(
            target=self._worker_loop, daemon=True, name="OmniCQWorker"
        )
        self._thread.start()
        self.omni_started.emit()
        logger.info("[OMNI-CQ] Start (next_even=%s -> Block %d)",
                    next_is_even, self._block)

    def stop(self, reason: str) -> None:
        """OMNI stoppen. Worker terminiert sofort."""
        with self._lock:
            if not self._running:
                return
            self._running = False
            self._paused = False
        self._stop_event.set()
        thread = self._thread
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=2.0)
        self._thread = None
        self.omni_stopped.emit(reason)
        logger.info("[OMNI-CQ] Stop (%s)", reason)

    def pause(self) -> None:
        """OMNI pausiert (QSO startet). Worker terminiert, _slot_index friert."""
        with self._lock:
            if not self._running:
                return
            if self._paused:
                return
            self._paused = True
        self._stop_event.set()
        thread = self._thread
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=2.0)
        self._thread = None
        self._stop_event.clear()  # bereit fuer resume_after_qso
        logger.info("[OMNI-CQ] Pause (QSO laeuft)")

    def resume_after_qso(self, last_qso_was_even: bool) -> None:
        """Nach QSO neu starten — Block-Wahl nach letztem QSO-Slot.

        Mike-Spec: endet auf Even -> Block 2, endet auf Odd -> Block 1.
        Beide Faelle starten ab Pos 0.
        """
        with self._lock:
            if not self._paused:
                return
            # R1 R3: alten Worker joinen falls noch lebt (defense-in-depth).
            old = self._thread
            if old is not None and old.is_alive():
                old.join(timeout=2.0)
            self._thread = None
            self._paused = False
            self._running = False  # damit start() sauber wieder hochfaehrt
        next_is_even = not last_qso_was_even
        self.start(next_is_even=next_is_even)
        logger.info("[OMNI-CQ] Resume (last_even=%s -> next_even=%s)",
                    last_qso_was_even, next_is_even)

    def is_active(self) -> bool:
        with self._lock:
            return self._running

    def is_paused(self) -> bool:
        with self._lock:
            return self._paused

    @property
    def cq_even_count(self) -> int:
        with self._lock:
            return self._cq_even_count

    @property
    def cq_odd_count(self) -> int:
        with self._lock:
            return self._cq_odd_count

    @property
    def cq_audio_hz(self) -> int | None:
        with self._lock:
            return self._cq_audio_hz

    # ------------------------------------------------------------------
    # Internal — testbar einzeln
    # ------------------------------------------------------------------
    def _next_slot_action(self) -> tuple[bool, bool]:
        """Liefert (is_tx, target_even) fuer den AKTUELLEN _slot_index.

        target_even ist nur fuer TX-Slots semantisch — Block 1 Pos 0 = Even,
        Pos 1 = Odd; Block 2 Pos 0 = Odd, Pos 1 = Even.
        """
        with self._lock:
            is_tx = self._TX_PATTERN[self._slot_index]
            if not is_tx:
                return False, False
            if self._block == 1:
                target_even = (self._slot_index == 0)
            else:
                target_even = (self._slot_index == 1)
            return True, target_even

    def _compute_next_boundary(self, target_even: bool | None) -> float:
        """Naechste UTC-Slot-Boundary, mit optionalem Paritaet-Filter."""
        slot = self._timer.cycle_duration
        now = time.time()
        cycle_num = int(now / slot)
        if target_even is None:
            return float((cycle_num + 1) * slot)
        next_num = cycle_num + 1
        next_boundary = float(next_num * slot)
        if (next_num % 2 == 0) != target_even:
            next_boundary += slot
        return next_boundary

    def _slot_label(self, is_tx: bool, target_even: bool) -> str:
        parity = "E" if target_even else "O"
        kind = "TX" if is_tx else "RX"
        return f"B{self._block} [{self._slot_index}/4] {kind}-{parity}"

    def _advance_state(self) -> None:
        """Ein Slot weiter — bei Pos 4 Rollover auf 0, Block-Wechsel,
        Block-Counter inkrementieren, Frequenz-Recheck triggern."""
        with self._lock:
            self._slot_index = (self._slot_index + 1) % 5
            if self._slot_index == 0:
                self._block = 2 if self._block == 1 else 1
                self._block_count += 1
                self._maybe_recheck_freq()

    def _maybe_recheck_freq(self) -> None:
        """Alle _BLOCKS_PER_FREQ_RECHECK Bloecke Sticky-Gap-Algo pruefen.

        Aufrufer haelt _lock bereits — Methode liest/schreibt _block_count
        und _cq_audio_hz unter dem RLock (rekursiv ok).
        """
        if self._block_count == 0:
            return
        if self._block_count % self._BLOCKS_PER_FREQ_RECHECK != 0:
            return
        new_freq = self._diversity.get_free_cq_freq()
        if new_freq is None:
            return
        if new_freq != self._cq_audio_hz:
            logger.info("[OMNI-CQ] Freq %s -> %s Hz (Block %d)",
                        self._cq_audio_hz, new_freq, self._block_count)
            self._cq_audio_hz = new_freq
            self.cq_freq_changed.emit(int(new_freq))

    def _ensure_audio_freq(self) -> int:
        """Sticky-Frequenz beim ersten TX setzen. Fallback 1500 Hz."""
        with self._lock:
            if self._cq_audio_hz is not None:
                return self._cq_audio_hz
        freq = self._diversity.get_free_cq_freq()
        if freq is None:
            logger.warning(
                "[OMNI-CQ] get_free_cq_freq=None -> Fallback %d Hz",
                self._FALLBACK_AUDIO_HZ,
            )
            freq = self._FALLBACK_AUDIO_HZ
        with self._lock:
            self._cq_audio_hz = int(freq)
            value = self._cq_audio_hz
        self.cq_freq_changed.emit(value)
        return value

    def _do_tx_slot(self, target_even: bool) -> None:
        """TX-Slot ausfuehren — encoder.transmit() atomar mit kwargs."""
        freq = self._ensure_audio_freq()
        cq_msg = f"CQ {self._my_call} {self._my_grid}"
        ok = self._encoder.transmit(
            cq_msg, tx_even=target_even, audio_freq_hz=freq,
        )
        if ok:
            with self._lock:
                if target_even:
                    self._cq_even_count += 1
                else:
                    self._cq_odd_count += 1
                even = self._cq_even_count
                odd = self._cq_odd_count
            self.counter_changed.emit(even, odd)
            self.slot_action.emit(self._slot_label(True, target_even),
                                  True, target_even)
        else:
            logger.warning(
                "[OMNI-CQ] encoder.transmit returnt False (busy) -> Slot verloren"
            )

    def _do_rx_slot(self) -> None:
        """RX-Slot — slot_action mit echter UTC-Slot-Paritaet emittieren."""
        actual_even = bool(self._timer.is_even_cycle())
        self.slot_action.emit(
            self._slot_label(False, actual_even), False, actual_even,
        )

    def _worker_loop(self) -> None:
        """Worker — pro Iteration ein Slot. Stoppt sofort bei stop()/pause()."""
        prelead = self._OMNI_TX_PRELEAD_S
        while True:
            with self._lock:
                if not self._running:
                    return
                if self._paused:
                    return
            is_tx, target_even = self._next_slot_action()

            # Boundary: TX braucht Paritaet, RX nimmt die naechste.
            next_boundary = self._compute_next_boundary(
                target_even if is_tx else None
            )
            sleep_dur = (next_boundary - prelead) - time.time()
            if sleep_dur > 0:
                # V2-L13: cancelable sleep statt time.sleep — stop()/pause()
                # weckt sofort auf.
                if self._stop_event.wait(timeout=sleep_dur):
                    return

            # Re-check nach Sleep — stop()/pause() koennten gefeuert haben.
            with self._lock:
                if not self._running:
                    return
                if self._paused:
                    return

            if is_tx:
                self._do_tx_slot(target_even)
            else:
                self._do_rx_slot()

            self._advance_state()
