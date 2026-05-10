"""OMNI-CQ — Single-Slot-CQ-Modus mit Such-Counter-Paritaets-Wechsel.

P7.OMNI-SIMPLIFY (v0.96.4, 10.05.2026 Mike-Spec):
- Sendet CQ in EINER Slot-Paritaet (Even ODER Odd)
- Paritaet wird automatisch alle ~10 Min gewechselt (Such-Counter)
- Diversity-Re-Mess pausiert OMNI (kein TX waehrend Mess-Phase)
- Sticky Audio-Frequenz ueber Paritaets-Wechsel hinweg

Eigenstaendiges Modul (KEIN qso_state.cq_mode-Hack — Memory-Pflicht
feedback_omni_separate_architecture.md).

Lifecycle:
  start()                    -> _active=True, _cq_tx_even=None
  on_cycle_start(c, is_even) -> erster Aufruf: setzt _cq_tx_even=fresh_is_even
                                + _init_audio_freq, sendet im selben Slot.
                                Folgende Aufrufe: nur senden wenn fresh_is_even
                                matcht.
  on_search_trigger()        -> Counter ++; bei >= 10 -> flip_tx_parity()
  flip_tx_parity()           -> _cq_tx_even toggle (True<->False)
  pause() / resume_after_qso(...) -> Lifecycle (Resume nimmt last_was_even
                                     fuer API-Kompat, ignoriert Wert)
  stop(reason)               -> Reset alles
"""
from __future__ import annotations

import logging
import time
from PySide6.QtCore import QObject, Signal, Slot

logger = logging.getLogger(__name__)


# Wechsel-Schwelle: nach N Such-Triggern flip Paritaet.
# FT8: 60s/Such x 10 = 10 Min Wechsel-Intervall.
_OMNI_FLIP_AFTER_SEARCHES = 10


class OmniCQ(QObject):
    """Single-Slot-CQ mit Such-Counter-Wechsel.

    Signals:
        omni_started: () — bei start()
        omni_stopped: (reason: str)
        slot_action: (label: str, is_tx: bool, target_even: bool)
                     P7: emit nur bei TX-Slot (kein RX-Branch mehr)
        cq_freq_changed: (audio_hz: int)
        cq_count_changed: (count: int, current_tx_even: bool)
        parity_flipped: (new_tx_even: bool) — bei flip_tx_parity()
    """

    omni_started = Signal()
    omni_stopped = Signal(str)
    slot_action = Signal(str, bool, bool)
    cq_freq_changed = Signal(int)
    cq_count_changed = Signal(int, bool)
    parity_flipped = Signal(bool)

    _FALLBACK_AUDIO_HZ = 1500

    def __init__(self, encoder, diversity_ctrl, timer,
                 my_call: str, my_grid: str):
        super().__init__()
        self._encoder = encoder
        self._diversity = diversity_ctrl
        self._timer = timer
        self._my_call = my_call
        self._my_grid = my_grid

        self._active = False
        self._paused = False
        self._cq_audio_hz: int | None = None
        self._cq_tx_even: bool | None = None
        self._cq_count = 0
        self._search_trigger_count = 0

    # ── Public API ────────────────────────────────────────────────────

    def start(self) -> None:
        """OMNI starten — _cq_tx_even bleibt None bis erster on_cycle_start."""
        if self._active:
            return
        self._active = True
        self._paused = False
        self._cq_audio_hz = None
        self._cq_tx_even = None
        self._cq_count = 0
        self._search_trigger_count = 0
        self.omni_started.emit()
        logger.info("[OMNI-CQ] Start")

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
        logger.info("[OMNI-CQ] Stop (%s)", reason)

    def pause(self) -> None:
        if not self._active or self._paused:
            return
        self._paused = True
        logger.info("[OMNI-CQ] Pause (QSO laeuft)")

    def resume_after_qso(self, last_was_even: bool | None = None) -> None:
        """API-Kompat (Pos-Param ignoriert in P7).

        last_was_even-Block-Wahl entfaellt — _cq_tx_even bleibt unveraendert.
        Sync ueber echte Re-Mess (via on_search_trigger), NICHT ueber Resume.
        """
        if not self._paused:
            logger.warning(
                "[OMNI-CQ] resume_after_qso ohne pause — ignoriert"
            )
            return
        self._paused = False
        parity_str = "E" if self._cq_tx_even else "O"
        logger.info("[OMNI-CQ] Resume (Paritaet bleibt %s)", parity_str)

    def is_active(self) -> bool:
        return self._active

    def is_paused(self) -> bool:
        return self._paused

    @property
    def cq_count(self) -> int:
        return self._cq_count

    @property
    def cq_tx_even(self) -> bool | None:
        return self._cq_tx_even

    @property
    def cq_audio_hz(self) -> int | None:
        return self._cq_audio_hz

    # ── Cycle-Hook (vom mw_cycle._on_cycle_start) ────────────────────

    @Slot(int, bool)
    def on_cycle_start(self, cycle_num: int, is_even: bool) -> None:
        """Pro Slot 1x — entscheidet ob OMNI sendet.

        R1-SF-2 / V2-L9: cycle_num UND is_even Parameter werden IGNORIERT.
        Paritaet wird FRESH aus time.time() berechnet (Robustheit gegen
        Signal-Latenz, im P6-Field-Test 14s Latenz beobachtet -> falsche
        Paritaet via signal). Parameter bleiben in der Signatur fuer
        Qt-Slot-Kompat (`@Slot(int, bool)` bindet an cycle_start signal).
        """
        if not self._active or self._paused:
            return

        # V2-L12: kein Senden waehrend Diversity-Mess-Phase
        if self._diversity.phase != "operate":
            return

        # V2-L9 Fresh-Compute is_even — robust gegen Signal-Latenz
        slot_dur = self._timer.cycle_duration
        fresh_is_even = (int(time.time() / slot_dur) % 2 == 0)

        # Erster Aufruf: Paritaet aus aktuellem Slot waehlen
        if self._cq_tx_even is None:
            self._cq_tx_even = fresh_is_even

        # Frequenz initialisieren wenn noch nicht (sticky)
        if self._cq_audio_hz is None:
            self._init_audio_freq()

        # Nur senden wenn aktueller Slot die richtige Paritaet hat
        if fresh_is_even != self._cq_tx_even:
            return

        cq_msg = f"CQ {self._my_call} {self._my_grid}"
        ok = self._encoder.transmit(
            cq_msg, tx_even=self._cq_tx_even,
            audio_freq_hz=self._cq_audio_hz,
        )
        if ok:
            self._cq_count += 1
            self.cq_count_changed.emit(self._cq_count, self._cq_tx_even)
            label = self._slot_label(True, self._cq_tx_even)
            self.slot_action.emit(label, True, self._cq_tx_even)
        else:
            label = self._slot_label(True, self._cq_tx_even)
            logger.warning(
                "[OMNI-CQ] encoder busy -> Slot %s uebersprungen", label
            )

    # ── Such-Counter-Hook (vom mw_cycle._refresh_diversity_freq_view) ─

    def on_search_trigger(self) -> None:
        """Diversity Such-Trigger gefeuert — Counter ++.

        Bei _OMNI_FLIP_AFTER_SEARCHES (=10) Triggern: flip_tx_parity().

        R1-SF-1 Defense-in-Depth: prueft auch _paused (existing mw_cycle
        TX-Schutz greift bereits via reset_search_counter, aber zukuenftige
        Hook-Aenderungen sollen den Counter nicht versehentlich waehrend
        QSO inkrementieren).
        """
        if not self._active or self._paused:
            return
        self._search_trigger_count += 1
        if self._search_trigger_count >= _OMNI_FLIP_AFTER_SEARCHES:
            self._search_trigger_count = 0
            self.flip_tx_parity()

    def flip_tx_parity(self) -> None:
        """Paritaets-Wechsel — toggle _cq_tx_even.

        Public fuer Tests + manueller Trigger (zukuenftig UI-Button).
        No-op wenn nicht aktiv oder _cq_tx_even noch None (vor erstem
        on_cycle_start).
        """
        if not self._active:
            return
        if self._cq_tx_even is None:
            return
        self._cq_tx_even = not self._cq_tx_even
        self.parity_flipped.emit(self._cq_tx_even)
        parity_str = "Even" if self._cq_tx_even else "Odd"
        logger.info("[OMNI-CQ] Paritaets-Wechsel auf %s", parity_str)

    # ── Internal ──────────────────────────────────────────────────────

    def _init_audio_freq(self) -> None:
        """Sticky-Frequenz beim ersten TX setzen. Fallback _FALLBACK_AUDIO_HZ."""
        freq = self._diversity.get_free_cq_freq()
        if freq is None:
            logger.warning(
                "[OMNI-CQ] get_free_cq_freq=None -> Fallback %d Hz",
                self._FALLBACK_AUDIO_HZ,
            )
            freq = self._FALLBACK_AUDIO_HZ
        self._cq_audio_hz = int(freq)
        self.cq_freq_changed.emit(self._cq_audio_hz)
        logger.info("[OMNI-CQ] CQ-Audiofrequenz: %d Hz", self._cq_audio_hz)

    def _slot_label(self, is_tx: bool, target_even: bool) -> str:
        parity = "E" if target_even else "O"
        kind = "TX" if is_tx else "RX"
        return f"{kind}-{parity}"
