"""OMNI-TX v3.2 — Automatische Slot-Rotation für maximale CQ-Reichweite.

Konzept:
  Normales CQ erreicht nur 50% aller aktiven Operatoren pro Zyklus
  (jeder hört nur den entgegengesetzten Slot zu seinem TX-Slot).
  OMNI-TX wechselt zwischen Even- und Odd-CQ → beide Hörergruppen erreicht.

  Sendeanteil: 2 von 5 Slots = 40% (normaler Betrieb: 50%)
  OMNI-TX sendet also 20% WENIGER als normaler CQ-Betrieb.
  Trotzdem ~20-30% mehr CQ-Antworten durch doppelte Hörerbasis.

5-Slot-Muster (wiederholt sich):
  Position 0: TX  ← Even oder Odd je nach Startparität
  Position 1: TX  ← entgegengesetzter Slot
  Position 2: RX
  Position 3: RX
  Position 4: RX  ← extra Hörslot für sauberen Übergang

Block-Wechsel nach block_cycles Zyklen (Plan v3.2 Default: 80).
Bei QSO-Start: Zähler zurücksetzen (aktueller Block läuft weiter).
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
        omni = OmniTX(block_cycles=80)
        # Zu Beginn jedes Zyklus:
        if omni.active and not omni.should_tx():
            skip_tx_this_cycle()
        omni.advance(qso_active=qso_sm.is_busy())
    """

    # Qt-Signal: wird bei JEDEM stop_omni_tx(reason) emittiert.
    # Reasons: "manual_halt", "band_change", "ft_mode_change",
    #          "rx_mode_change", "totmann_expired", "easter_egg_off",
    #          "superseded"
    omni_stopped = Signal(str)

    def __init__(self, block_cycles: int = 80):
        """
        Args:
            block_cycles: Zyklen pro Block vor dem Wechsel.
                          Plan v3.2: 80 (entspricht diversity_operate_cycles Default).
        """
        super().__init__()
        self.active: bool = False
        self.block: int = 1             # Aktueller Block (1 oder 2)
        self.block_cycles: int = max(10, block_cycles)
        self._cycle_count: int = 0      # Zyklen im aktuellen Block
        self._slot_index: int = 0       # Position im 5-Slot-Muster (0-4)
        self._pending_switch: bool = False  # Block-Wechsel angefordert, wartet auf Pos 0
        self.cq_even_count: int = 0     # Zaehler: CQ auf Even gesendet
        self.cq_odd_count: int = 0      # Zaehler: CQ auf Odd gesendet

    # ─────────────────────────────────────────────────────────────────────────
    # Haupt-API
    # ─────────────────────────────────────────────────────────────────────────

    def should_tx(self, is_even: bool = True) -> tuple:
        """Prueft ob dieser Slot gesendet werden soll + Ziel-Paritaet.

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
            target_even = (self._slot_index == 0)  # Pos 0=Even, Pos 1=Odd
        else:
            target_even = (self._slot_index == 1)  # Pos 0=Odd, Pos 1=Even

        return True, target_even

    def advance(self, qso_active: bool = False) -> None:
        """Nächsten Zyklus voranschreiten.

        Muss EINMAL pro FT8-Zyklus aufgerufen werden (nach Dekodierung).

        Args:
            qso_active: True wenn gerade ein QSO läuft.
                        Bei True: Zähler wird NICHT erhöht (aktueller Block bleibt).
        """
        if not self.active:
            return
        self._slot_index = (self._slot_index + 1) % 5
        # Pending Switch: Block-Wechsel wurde angefordert aber war nicht an Muster-Grenze
        if self._pending_switch and self._slot_index == 0:
            self._do_switch_block()
            return
        if not qso_active:
            self._cycle_count += 1
            if self._cycle_count >= self.block_cycles:
                self._switch_block()

    def on_qso_started(self) -> None:
        """QSO begann → Zähler zurücksetzen, Block beibehalten.

        Begründung: der Slot läuft gerade gut, nicht unnötig wechseln.
        Durch unterschiedliche QSO-Häufigkeit entsteht natürliche
        Variabilität in den Block-Längen.
        """
        if not self.active:
            return
        self._cycle_count = 0
        logger.debug(f"[OMNI-TX] QSO begonnen → Zähler reset (Block {self.block})")

    # ─────────────────────────────────────────────────────────────────────────
    # Aktivierung / Stop
    # ─────────────────────────────────────────────────────────────────────────

    def enable(self) -> None:
        """OMNI-TX aktivieren — Slot-Index, Block, Counter und Pending-Switch zuruecksetzen."""
        self.active = True
        self._cycle_count = 0
        self._slot_index = 0
        self._pending_switch = False
        self.block = 1
        logger.info("[OMNI-TX] Aktiviert — Even+Odd Slot-Rotation")

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

        Cleanup ist immer identisch: active=False, slot_index=0, cycle_count=0,
        _pending_switch=False (Bug-Fix: sonst springt Block nach Re-enable() sofort).
        """
        self.active = False
        self._slot_index = 0
        self._cycle_count = 0
        self._pending_switch = False
        logger.info(f"[OMNI-TX] Stop (reason={reason})")
        self.omni_stopped.emit(reason)

    def disable(self) -> None:
        """Backwards-compat Thin-Wrapper. Bestehende Aufrufer (Easter-Egg-Disable
        in main_window.py:546-548) bleiben funktional, neuer Pfad geht ueber
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
        return f"B{self.block} [{self._slot_index}/4] {action}"

    @property
    def cycles_until_block_switch(self) -> int:
        """Verbleibende Zyklen bis zum nächsten Block-Wechsel."""
        return max(0, self.block_cycles - self._cycle_count)

    # ─────────────────────────────────────────────────────────────────────────
    # Intern
    # ─────────────────────────────────────────────────────────────────────────

    def _switch_block(self) -> None:
        """Block-Wechsel anfordern — wird an naechster Muster-Grenze (Position 0) ausgefuehrt."""
        if self._slot_index == 0:
            self._do_switch_block()
        else:
            self._pending_switch = True
            logger.debug(f"[OMNI-TX] Block-Wechsel angefordert, warte auf Muster-Grenze "
                         f"(aktuell Position {self._slot_index})")

    def _do_switch_block(self) -> None:
        """Block tatsaechlich wechseln (nur an Position 0)."""
        old_block = self.block
        self.block = 2 if self.block == 1 else 1
        self._cycle_count = 0
        self._pending_switch = False
        logger.info(f"[OMNI-TX] Block {old_block} → Block {self.block} "
                    f"(nach {self.block_cycles} Zyklen)")


# ─────────────────────────────────────────────────────────────────────────────
# Singleton (wird in main_window.py initialisiert)
# ─────────────────────────────────────────────────────────────────────────────

_instance: Optional[OmniTX] = None


def get_instance(block_cycles: int = 40) -> OmniTX:
    """Singleton-Accessor. block_cycles beim ersten Aufruf übergeben."""
    global _instance
    if _instance is None:
        _instance = OmniTX(block_cycles=block_cycles)
    return _instance
