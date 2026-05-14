"""OMNI-CQ — Single-Slot-CQ-Modus mit eigenem Down-Counter.

P23.OMNI-COUNTER-EIGEN (v0.96.7, 10.05.2026 Mike-Spec):
- Sendet CQ in EINER Slot-Paritaet (Even ODER Odd)
- Eigener Down-Counter pro Modus (FT8=10, FT4=20, FT2=40 = ~5 Min)
- Counter dekrementiert nach jedem TX. Bei 0: flip + Reset auf TARGET
- QSO eingehend / Antennen-Mess fertig: Counter Reset auf TARGET
- Bandwechsel + Modus-Wechsel: OMNI stoppt
- KEIN Coupling mehr zu Diversity-Such-Counter (vor v0.96.7)

Eigenstaendiges Modul (KEIN qso_state.cq_mode-Hack — Memory-Pflicht
feedback_omni_separate_architecture.md).

Lifecycle:
  start()                    -> _active=True, _cq_tx_even=None,
                                _cq_target/remaining aus timer.mode
  on_cycle_start(c, is_even) -> erster Aufruf: setzt _cq_tx_even=fresh_is_even
                                + _init_audio_freq, sendet im selben Slot.
                                Folgende Aufrufe: nur senden wenn fresh_is_even
                                matcht. Erfolgreicher TX: remaining--, bei 0 flip.
  flip_tx_parity()           -> _cq_tx_even toggle (True<->False)
  pause() / resume_after_qso(...) -> resume setzt remaining=target zurueck
  reset_counter_after_measure()    -> aus mw_cycle bei measure->operate
  stop(reason)               -> Reset alles
"""
from __future__ import annotations

import logging
import time
from PySide6.QtCore import QObject, Signal, Slot

logger = logging.getLogger(__name__)


# Counter pro Modus — alle ~5 Min Wallclock pro Paritaet.
# FT8: 15s slot * 2 (alternierend) * 10 = 300s = 5 Min
# FT4:  7.5s     * 2                * 20 = 300s = 5 Min
# FT2:  3.8s     * 2                * 40 = 304s = 5 Min
_OMNI_TARGETS = {"FT8": 10, "FT4": 20, "FT2": 40}
_OMNI_DEFAULT_TARGET = 10  # Fallback fuer unbekannte Modi


class OmniCQ(QObject):
    """Single-Slot-CQ mit Such-Counter-Wechsel.

    Signals:
        omni_started: () — bei start()
        omni_stopped: (reason: str)
        slot_action: (label: str, is_tx: bool, target_even: bool)
                     P7: emit nur bei TX-Slot (kein RX-Branch mehr)
        cq_freq_changed: (audio_hz: int)
        cq_count_changed: (remaining: int, current_tx_even: bool)
                          P23: remaining ist DOWN-Counter (zaehlt von TARGET
                          nach 1 → flip → wieder TARGET). 1 Emit pro Slot.
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
        # P23: eigener Down-Counter (statt _cq_count UP + _search_trigger_count)
        self._cq_remaining = 0
        self._cq_target = _OMNI_DEFAULT_TARGET
        # P31 (11.05.2026 Mike-Field-Test): Display-Wert PRE-decrement, fuer
        # qso_panel + Statusbar. Mike-Erwartung: ↻10 fuer ersten Slot, ↻1
        # fuer letzten, ↻10 fuer ersten Slot der naechsten Paritaet. Aktueller
        # _cq_remaining ist POST-decrement (intern).
        self._cq_remaining_display = 0
        self._cq_tx_even_display: bool | None = None

    # ── Public API ────────────────────────────────────────────────────

    def start(self) -> None:
        """OMNI starten — _cq_tx_even bleibt None bis erster on_cycle_start.

        P23: _cq_target wird einmalig aus timer.mode abgeleitet
        (Modus-Wechsel ruft separat stop, daher kein Refresh-Bedarf).
        """
        if self._active:
            return
        self._active = True
        self._paused = False
        self._cq_audio_hz = None
        self._cq_tx_even = None
        mode = getattr(self._timer, 'mode', 'FT8')
        self._cq_target = _OMNI_TARGETS.get(mode, _OMNI_DEFAULT_TARGET)
        self._cq_remaining = self._cq_target
        self._cq_remaining_display = self._cq_target  # P31
        self.omni_started.emit()
        logger.info("[OMNI-CQ] Start (Modus %s, Counter %d)",
                    mode, self._cq_target)

    def stop(self, reason: str) -> None:
        if not self._active:
            return
        self._active = False
        self._paused = False
        self._cq_audio_hz = None
        self._cq_tx_even = None
        self._cq_remaining = 0
        self._cq_remaining_display = 0  # P31
        self._cq_tx_even_display = None
        self._cq_target = _OMNI_DEFAULT_TARGET
        self.omni_stopped.emit(reason)
        logger.info("[OMNI-CQ] Stop (%s)", reason)

    def pause(self) -> None:
        if not self._active or self._paused:
            return
        self._paused = True
        logger.info("[OMNI-CQ] Pause (QSO laeuft)")

    def resume_after_qso(self, last_was_even: bool | None = None) -> None:
        """Resume nach QSO — P23: Counter zurueck auf TARGET.

        Mike-Spec: „wenn QSO funktioniert, neuer Slot startet bei TARGET".
        last_was_even-Param ist Pos-Param fuer API-Kompat (ignoriert).
        """
        if not self._paused:
            logger.warning(
                "[OMNI-CQ] resume_after_qso ohne pause — ignoriert"
            )
            return
        self._paused = False
        # P23-A3: Counter Reset auf TARGET (positiv-Verstaerkung "guter Slot")
        self._cq_remaining = self._cq_target
        self._cq_remaining_display = self._cq_target  # P31
        self._cq_tx_even_display = self._cq_tx_even
        parity_str = "E" if self._cq_tx_even else "O"
        logger.info("[OMNI-CQ] Resume (Counter %d, Paritaet %s)",
                    self._cq_remaining, parity_str)
        self.cq_count_changed.emit(
            self._cq_remaining,
            bool(self._cq_tx_even) if self._cq_tx_even is not None else False,
        )

    def reset_counter_after_measure(self) -> None:
        """P23-A4: nach Antennen-Mess Counter zurueck auf TARGET.

        Wird aus mw_cycle bei Phase-Uebergang measure->operate gerufen.
        No-op wenn nicht aktiv ODER pausiert (paused-Pfad reset macht
        resume_after_qso selbst). No-op wenn remaining bereits == target.
        """
        if not self._active or self._paused:
            return
        if self._cq_remaining == self._cq_target:
            return  # nichts zu tun
        self._cq_remaining = self._cq_target
        self._cq_remaining_display = self._cq_target  # P31
        self._cq_tx_even_display = self._cq_tx_even
        self.cq_count_changed.emit(
            self._cq_remaining,
            bool(self._cq_tx_even) if self._cq_tx_even is not None else False,
        )
        logger.info("[OMNI-CQ] Counter reset nach Mess (auf %d)",
                    self._cq_remaining)

    def is_active(self) -> bool:
        return self._active

    def is_paused(self) -> bool:
        return self._paused

    @property
    def cq_remaining(self) -> int:
        """P23: Down-Counter, INTERN — post-decrement Wert fuer naechsten Slot."""
        return self._cq_remaining

    @property
    def cq_remaining_display(self) -> int:
        """P31 (11.05.2026): Display-Wert fuer qso_panel + Statusbar.

        Pre-decrement Wert des AKTUELLEN TX-Slots. Mike-Erwartung:
        ↻10 fuer ersten Slot in Paritaet, ↻9, ..., ↻1, dann nach Flip
        ↻10 in neuer Paritaet.
        """
        return self._cq_remaining_display

    @property
    def cq_tx_even_display(self) -> bool | None:
        """P31: Paritaet zur DISPLAY-Zeit (vor Flip)."""
        return self._cq_tx_even_display

    @property
    def cq_target(self) -> int:
        """P23: Counter-Maximalwert pro Paritaet (modus-abhaengig)."""
        return self._cq_target

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
            # P31 (11.05.2026 Mike-Field-Test): DISPLAY-Snapshot VOR Decrement+Flip.
            # Mike-Erwartung: ↻10 fuer ersten Slot, ↻9 ... ↻1, dann Flip → ↻10
            # in neuer Paritaet. Decrement passiert sofort danach (intern), aber
            # qso_panel + Statusbar lesen den Display-Wert (pre-decrement).
            self._cq_remaining_display = self._cq_remaining
            self._cq_tx_even_display = self._cq_tx_even
            # P23-A2: dekrementieren, ggf. Auto-Flip + Reset (interner Counter).
            self._cq_remaining -= 1
            if self._cq_remaining == 0:
                self.flip_tx_parity()
                self._cq_remaining = self._cq_target
            self.cq_count_changed.emit(
                self._cq_remaining_display, bool(self._cq_tx_even_display)
            )
            label = self._slot_label(True, self._cq_tx_even_display)
            self.slot_action.emit(label, True, self._cq_tx_even_display)
        else:
            label = self._slot_label(True, self._cq_tx_even)
            logger.warning(
                "[OMNI-CQ] encoder busy -> Slot %s uebersprungen", label
            )

    # ── (P23: on_search_trigger entfernt — Counter ist jetzt OMNI-eigen) ─

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
