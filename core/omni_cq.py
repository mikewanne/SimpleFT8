"""SimpleFT8 OMNI-CQ — signal-basiert, GUI-Thread, kein Worker.

Architektur (P4.OMNI-NEUBAU V5, 09.05.2026):
- Eigenstaendiges Modul (KEIN qso_state.cq_mode-Hack).
- Slot-Synchronisation kommt vom existing FT8Timer.cycle_start-Signal
  (1x pro 15s-Slot bei FT8). on_cycle_start laeuft im GUI-Thread —
  kein eigener Thread, keine Sleep-Logik, keine Boundary-Berechnung.
- 5-Slot-Pattern (TX-TX-RX-RX-RX). Block 1 Even-First, Block 2 Odd-First.
- Toggle-Start: IMMER Block 1 (KISS). Rollover automatisch nach 5 Slots.
- Frequenz-Sticky: 1x am ersten TX setzen, fest bis stop().
- Bei eingehender Antwort: pause() — Uebergabe an qso_state.start_qso()
  laeuft via mw_cycle.on_message_decoded (C6, unveraendert).
- Block-Wahl nach QSO: endet auf Even -> Block 2, endet auf Odd -> Block 1.

Hardware-Garantie ANT1: OMNI emittet kein TX direkt. TX laeuft via
encoder.transmit(), welcher zentral radio.set_tx_antenna("ANT1") setzt.
Kein Extra-Check noetig.

Lessons-Learned (v0.96.0 Worker-Bug, 09.05.2026):
- Tests rufen on_cycle_start direkt auf — KEIN Worker-Mock, KEIN
  Sleep-Mock, KEIN Boundary-Mock. Wenn ein Mock genau die Logik
  ueberschreibt die der Test pruefen sollte, validiert er die Mock-
  Implementierung statt des echten Codes. Vor jedem Mock fragen:
  "Ersetzt dieser Mock den Pfad den der Test pruefen sollte?" — JA
  bedeutet Test wertlos.
"""
from __future__ import annotations

import logging

from PySide6.QtCore import QObject, Signal, Slot


logger = logging.getLogger(__name__)


class OmniCQ(QObject):
    """OMNI-CQ State-Machine, signal-getriggert.

    Aufrufer-Pfad: FT8Timer.cycle_start -> mw_cycle._on_cycle_start ->
    OmniCQ.on_cycle_start(cycle_num, is_even).

    Signals:
        omni_started: () — Start ausgeloest (vor erstem cycle_start).
        omni_stopped: (str) — Stop-Reason ("manual_halt", "band_change", ...).
        slot_action: (str, bool, bool) — (label, is_tx, target_even).
            target_even bei TX-Slots = Pattern-Paritaet, bei RX-Slots = echte
            UTC-Slot-Paritaet (is_even aus dem Signal-Parameter).
        cq_freq_changed: (int) — neue CQ-Audiofrequenz in Hz (1x am Start).
        counter_changed: (int, int) — (cq_even, cq_odd) bei TX-Erfolg.
    """

    omni_started = Signal()
    omni_stopped = Signal(str)
    slot_action = Signal(str, bool, bool)
    cq_freq_changed = Signal(int)
    counter_changed = Signal(int, int)

    # 5-Slot-Pattern (TX-TX-RX-RX-RX). Block 1 Even-First / Block 2 Odd-First.
    _TX_PATTERN = (True, True, False, False, False)
    _FALLBACK_AUDIO_HZ = 1500   # AC12: wenn diversity.get_free_cq_freq()=None

    def __init__(self, encoder, diversity_ctrl, timer,
                 my_call: str, my_grid: str):
        super().__init__()
        self._encoder = encoder
        self._diversity = diversity_ctrl
        self._timer = timer            # nur fuer API-Kompat (Tests/Init)
        self._my_call = my_call
        self._my_grid = my_grid

        self._active = False
        self._paused = False
        self._slot_index = 0
        self._block = 1                # 1=Even-First, 2=Odd-First
        self._cq_audio_hz: int | None = None
        self._cq_even_count = 0
        self._cq_odd_count = 0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def start(self) -> None:
        """OMNI starten — IMMER Block 1 (AC5, KISS).

        Idempotent: bei _active=True ist der Aufruf no-op (AC1).
        """
        if self._active:
            return
        self._active = True
        self._paused = False
        self._slot_index = 0
        self._block = 1
        self._cq_audio_hz = None
        self._cq_even_count = 0
        self._cq_odd_count = 0
        self.omni_started.emit()
        logger.info("[OMNI-CQ] Start (Block 1)")

    def stop(self, reason: str) -> None:
        """OMNI stoppen + voller State-Reset.

        Idempotent (AC20): bei _active=False ist der Aufruf no-op.
        """
        if not self._active:
            return
        self._active = False
        self._paused = False
        self._slot_index = 0
        self._block = 1
        self._cq_audio_hz = None
        self._cq_even_count = 0
        self._cq_odd_count = 0
        self.omni_stopped.emit(reason)
        logger.info("[OMNI-CQ] Stop (%s)", reason)

    def pause(self) -> None:
        """Pause — _slot_index friert ein, _active bleibt True (AC17).

        Idempotent: bei nicht-active oder bereits-paused no-op.
        """
        if not self._active or self._paused:
            return
        self._paused = True
        logger.info("[OMNI-CQ] Pause (QSO laeuft)")

    def resume_after_qso(self, last_was_even: bool) -> None:
        """Nach QSO-Ende fortsetzen — Block-Wahl anhand letztem QSO-Slot.

        Mike-Spec / AC18: endet auf Even -> Block 2, endet auf Odd -> Block 1.
        Beide starten ab Pos 0. cq_audio_hz BLEIBT (AC14).

        Pre-Check: wenn nicht pausiert no-op + log warning. Schuetzt vor
        falschem Aufruf nach stop().
        """
        if not self._paused:
            logger.warning(
                "[OMNI-CQ] resume_after_qso aufgerufen ohne pause — ignoriert"
            )
            return
        self._block = 2 if last_was_even else 1
        self._slot_index = 0
        self._paused = False
        logger.info("[OMNI-CQ] Resume (last_even=%s -> Block %d)",
                    last_was_even, self._block)

    def is_active(self) -> bool:
        return self._active

    def is_paused(self) -> bool:
        return self._paused

    @property
    def cq_even_count(self) -> int:
        return self._cq_even_count

    @property
    def cq_odd_count(self) -> int:
        return self._cq_odd_count

    @property
    def cq_audio_hz(self) -> int | None:
        return self._cq_audio_hz

    # ------------------------------------------------------------------
    # Cycle-Start Hook (vom mw_cycle._on_cycle_start gerufen)
    # ------------------------------------------------------------------
    @Slot(int, bool)
    def on_cycle_start(self, cycle_num: int, is_even: bool) -> None:
        """Pro Slot 1x — entscheidet TX/RX, advanced State.

        Defense-in-Depth-Guard (AC7): no-op wenn nicht aktiv oder pausiert.
        Pattern-Entscheidung basiert auf _slot_index — is_even (echte
        UTC-Slot-Paritaet) wird nur fuer RX-Anzeige genutzt.
        """
        if not self._active or self._paused:
            return
        is_tx, target_even = self._next_slot_action()
        if is_tx:
            self._do_tx_slot(target_even)
        else:
            self._do_rx_slot(is_even)
        self._advance_state()

    # ------------------------------------------------------------------
    # Internal — testbar einzeln
    # ------------------------------------------------------------------
    def _next_slot_action(self) -> tuple[bool, bool]:
        """Liefert (is_tx, target_even) fuer den AKTUELLEN _slot_index.

        target_even ist nur fuer TX-Slots semantisch — Block 1 Pos 0=Even,
        Pos 1=Odd; Block 2 Pos 0=Odd, Pos 1=Even.
        """
        is_tx = self._TX_PATTERN[self._slot_index]
        if not is_tx:
            return False, False
        if self._block == 1:
            target_even = (self._slot_index == 0)
        else:
            target_even = (self._slot_index == 1)
        return True, target_even

    def _do_tx_slot(self, target_even: bool) -> None:
        """TX-Slot ausfuehren — encoder.transmit() atomar mit kwargs.

        AC8: Reihenfolge bei Erfolg: counter_changed.emit -> slot_action.emit.
        AC11: Bei encoder-busy (False) keine Counter-Inkrement, keine
        slot_action — nur log warning. _slot_index advanced trotzdem
        (AC10, _advance_state ist Aufruferseite).
        """
        if self._cq_audio_hz is None:
            self._init_audio_freq()
        cq_msg = f"CQ {self._my_call} {self._my_grid}"
        ok = self._encoder.transmit(
            cq_msg, tx_even=target_even, audio_freq_hz=self._cq_audio_hz,
        )
        label = self._slot_label(True, target_even)
        if ok:
            if target_even:
                self._cq_even_count += 1
            else:
                self._cq_odd_count += 1
            self.counter_changed.emit(self._cq_even_count, self._cq_odd_count)
            self.slot_action.emit(label, True, target_even)
        else:
            logger.warning(
                "[OMNI-CQ] encoder.transmit busy -> Slot %s uebersprungen",
                label,
            )

    def _do_rx_slot(self, is_even: bool) -> None:
        """RX-Slot — slot_action mit echter UTC-Slot-Paritaet emittieren."""
        label = self._slot_label(False, is_even)
        self.slot_action.emit(label, False, is_even)

    def _advance_state(self) -> None:
        """Ein Slot weiter — bei Pos 4 Rollover auf 0 + Block-Wechsel."""
        self._slot_index = (self._slot_index + 1) % 5
        if self._slot_index == 0:
            self._block = 2 if self._block == 1 else 1

    def _init_audio_freq(self) -> None:
        """Sticky-Frequenz beim ersten TX setzen (AC12). Fallback 1500 Hz."""
        freq = self._diversity.get_free_cq_freq()
        if freq is None:
            logger.warning(
                "[OMNI-CQ] get_free_cq_freq=None -> Fallback %d Hz",
                self._FALLBACK_AUDIO_HZ,
            )
            freq = self._FALLBACK_AUDIO_HZ
        self._cq_audio_hz = int(freq)
        self.cq_freq_changed.emit(self._cq_audio_hz)

    def _slot_label(self, is_tx: bool, target_even: bool) -> str:
        parity = "E" if target_even else "O"
        kind = "TX" if is_tx else "RX"
        return f"B{self._block} [{self._slot_index}/4] {kind}-{parity}"
