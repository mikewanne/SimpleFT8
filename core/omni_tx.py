"""OMNI-TX v4.0 — Automatische Slot-Rotation für maximale CQ-Reichweite.

Konzept:
  Normales CQ erreicht nur 50% aller aktiven Operatoren pro Zyklus
  (jeder hört nur den entgegengesetzten Slot zu seinem TX-Slot).
  OMNI-TX wechselt zwischen Even- und Odd-CQ → beide Hörergruppen erreicht.

  Sendeanteil: 2 von 5 Slots = 40% (normaler Betrieb: 50%)
  OMNI-TX sendet also 20% WENIGER als normaler CQ-Betrieb.
  Trotzdem ~20-30% mehr CQ-Antworten durch doppelte Hörerbasis.

5-Slot-Muster (wiederholt sich):
  Position 0: TX  ← Even oder Odd je nach Block
  Position 1: TX  ← entgegengesetzte Paritaet
  Position 2: RX
  Position 3: RX
  Position 4: RX  ← extra Hörslot für sauberen Übergang

Block 1: E-TX, O-TX, E-RX, O-RX, E-RX
Block 2: O-TX, E-TX, O-RX, E-RX, O-RX

Block-Switch v4.0 (P2.OMNI-REDESIGN):
  Automatisch bei rollover (slot_index 4→0). Kein 80-Zyklen-Counter mehr
  (war Diversity-OPERATE_CYCLES-Überrest aus v0.78).

Pause/Resume v4.0:
  Während QSO friert _slot_index ein (pause). Nach QSO ruft mw_qso
  start_with_parity_for_next_slot(next_is_even) — Block neu gewählt damit
  kein Slot verschwendet wird ("kein Slot verschwenden":
  next_is_even → Block 1, sonst Block 2).
"""

from __future__ import annotations

import logging
from typing import Optional

from PySide6.QtCore import QObject, Signal

logger = logging.getLogger(__name__)

# 5-Slot-Muster: True=TX, False=RX
# Gilt für beide Blöcke — der Unterschied ist nur die Startparität (even/odd)
_TX_PATTERN = [True, True, False, False, False]


class OmniTX(QObject):
    """OMNI-TX Controller — Slot-Rotation für Even+Odd CQ.

    Erbt von QObject damit Signal-Emit (omni_stopped) sauber funktioniert
    und Qt-Lifecycle (deleteLater etc.) greift.

    Verwendung:
        omni = OmniTX()
        omni.start_with_parity_for_next_slot(next_is_even=True)
        # Pro Zyklus (mw_cycle._on_cycle_start):
        if not omni.is_paused():
            omni.advance()
        # Im TX-Pfad (mw_qso._on_send_message):
        send_ok, target_even = omni.should_tx()
    """

    # Qt-Signal: wird bei JEDEM stop_omni_tx(reason) emittiert.
    # Reasons: "manual_halt", "band_change", "ft_mode_change",
    #          "rx_mode_change", "totmann_expired", "easter_egg_off",
    #          "superseded"
    omni_stopped = Signal(str)

    def __init__(self):
        super().__init__()
        self.active: bool = False
        self.block: int = 1             # Aktueller Block (1 oder 2)
        self._slot_index: int = 0       # Position im 5-Slot-Muster (0-4)
        self._paused: bool = False      # QSO-Pause: _slot_index friert ein
        self.cq_even_count: int = 0     # Zaehler: CQ auf Even gesendet (Statusbar)
        self.cq_odd_count: int = 0      # Zaehler: CQ auf Odd gesendet (Statusbar)

    # ─────────────────────────────────────────────────────────────────────────
    # Haupt-API
    # ─────────────────────────────────────────────────────────────────────────

    def should_tx(self) -> tuple:
        """Prueft ob dieser Slot gesendet werden soll + Ziel-Paritaet.

        Die Paritaet wird ausschliesslich aus _slot_index + block bestimmt —
        der Aufrufer muss seinen aktuellen Even/Odd-State NICHT uebergeben.

        Returns:
            (should_send, target_is_even)
            - (True, True): Sende auf Even
            - (True, False): Sende auf Odd
            - (True, None): Normaler Betrieb (OMNI deaktiviert)
            - (False, None): RX-Slot, nicht senden
        """
        if not self.active:
            return True, None  # Deaktiviert → normaler Betrieb

        if not _TX_PATTERN[self._slot_index]:
            return False, None  # RX-Slot

        # TX-Slot: Paritaet bestimmen basierend auf Block + Position
        # Block 1: Even first → Pos 0=Even, Pos 1=Odd
        # Block 2: Odd first  → Pos 0=Odd,  Pos 1=Even
        if self.block == 1:
            target_even = (self._slot_index == 0)
        else:
            target_even = (self._slot_index == 1)

        return True, target_even

    def advance(self) -> None:
        """Nächsten Slot voranschreiten (5-Slot-Muster).

        Muss EINMAL pro FT8-Zyklus aufgerufen werden (mw_cycle._on_cycle_start).
        Aufrufer muss vorher is_paused() prüfen — pausiertes OMNI hält den
        Slot-Index fest, damit nach QSO-Ende sauber resumed wird.

        Block-Switch v4.0: automatisch bei rollover slot_index 4→0.
        """
        if not self.active:
            return
        self._slot_index = (self._slot_index + 1) % 5
        if self._slot_index == 0:
            old_block = self.block
            self.block = 2 if self.block == 1 else 1
            logger.info(f"[OMNI-TX] Block-Rollover {old_block} → {self.block}")

    # ─────────────────────────────────────────────────────────────────────────
    # Aktivierung / Pause / Stop (P2.OMNI-REDESIGN v4.0)
    # ─────────────────────────────────────────────────────────────────────────

    def start_with_parity_for_next_slot(self, next_is_even: bool) -> None:
        """OMNI aktivieren mit Block-Wahl basierend auf Parität des nächsten Slots.

        „Kein Slot verschwenden": Mike's Designentscheidung 09.05.2026.
        next_is_even=True  → Block 1 (E-TX, O-TX, ...) → erste TX auf Even
        next_is_even=False → Block 2 (O-TX, E-TX, ...) → erste TX auf Odd

        Idempotent: kann auch aus Resume-Pfad aufgerufen werden während
        active=True — überschreibt Block + Slot-Index sauber neu.
        """
        self.block = 1 if next_is_even else 2
        self._slot_index = 0
        self.active = True
        self._paused = False
        logger.info(
            f"[OMNI-TX] Start (next_is_even={next_is_even} → Block {self.block})"
        )

    def pause(self) -> None:
        """OMNI während QSO pausieren — _slot_index friert ein.

        QSO ist heilig (Mike 09.05.2026): nur HALT unterbricht. Pause
        verhindert dass advance() während QSO weiterläuft, danach wird
        per start_with_parity_for_next_slot neu gestartet.
        """
        self._paused = True

    def resume(self) -> None:
        """OMNI nach QSO fortsetzen — _slot_index läuft weiter.

        Nicht direkt nach QSO-Ende verwendet — mw_qso ruft stattdessen
        start_with_parity_for_next_slot mit aktueller Parität auf, damit
        kein Slot verschwendet wird. resume() bleibt für Symmetrie/Tests.
        """
        self._paused = False

    def is_paused(self) -> bool:
        """True wenn OMNI pausiert ist (QSO läuft)."""
        return self._paused

    def stop_omni_tx(self, reason: str) -> None:
        """OMNI-TX-Session beenden. Emittiert omni_stopped(reason).

        Reasons (siehe v0.78 Plan v3.2):
            manual_halt       — User klickte btn_omni_cq erneut
            band_change       — Band wurde gewechselt
            ft_mode_change    — FT-Modus (FT8/FT4/FT2) wurde gewechselt
            rx_mode_change    — RX-Modus diversity→normal
            totmann_expired   — Operator-Presence (15 Min) abgelaufen
            easter_egg_off    — Easter-Egg deaktiviert waehrend OMNI aktiv
            superseded        — Anderer Mode-Button (Auto-Hunt) wurde gestartet

        Cleanup ist immer identisch: active=False, slot_index=0, _paused=False.
        """
        self.active = False
        self._slot_index = 0
        self._paused = False
        logger.info(f"[OMNI-TX] Stop (reason={reason})")
        self.omni_stopped.emit(reason)

    def disable(self) -> None:
        """Backwards-compat Thin-Wrapper. Bestehende Aufrufer (Easter-Egg-Disable
        in main_window.py:642) bleiben funktional, neuer Pfad geht ueber
        stop_omni_tx(reason)."""
        self.stop_omni_tx("easter_egg_off")

    # ─────────────────────────────────────────────────────────────────────────
    # Status / Debug
    # ─────────────────────────────────────────────────────────────────────────

    @property
    def slot_label(self) -> str:
        """Kurzbeschreibung des aktuellen Slots (für Debug/Logging)."""
        if not self.active:
            return "normal"
        action = "TX" if _TX_PATTERN[self._slot_index] else "RX"
        suffix = " PAUSED" if self._paused else ""
        return f"B{self.block} [{self._slot_index}/4] {action}{suffix}"


# ─────────────────────────────────────────────────────────────────────────────
# Singleton (wird in main_window.py initialisiert)
# ─────────────────────────────────────────────────────────────────────────────

_instance: Optional[OmniTX] = None


def get_instance() -> OmniTX:
    """Singleton-Accessor. P2.OMNI-REDESIGN v4.0: kein block_cycles-Param mehr."""
    global _instance
    if _instance is None:
        _instance = OmniTX()
    return _instance
