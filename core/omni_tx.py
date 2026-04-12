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

Block-Wechsel nach block_cycles Zyklen (default: diversity_cycles // 2).
Bei QSO-Start: Zähler zurücksetzen (aktueller Block läuft weiter).

TODO: KOMPLETT DEAKTIVIERT — scharfschalten erst nach Feldtest!
      Aktivierung nur via Easter Egg (Klick auf Versionsnummer in GUI).
"""

from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# FEATURE FLAG — NIEMALS True setzen ohne explizite Aktivierung via Easter Egg
OMNI_TX_ENABLED: bool = False
# ─────────────────────────────────────────────────────────────────────────────

# 5-Slot-Muster: True=TX, False=RX
# Gilt für beide Blöcke — der Unterschied ist nur die Startparität (even/odd)
_TX_PATTERN = [True, True, False, False, False]


class OmniTX:
    """OMNI-TX Controller — Slot-Rotation für Even+Odd CQ.

    Verwendung (wenn aktiviert):
        omni = OmniTX(block_cycles=40)
        # Zu Beginn jedes Zyklus:
        if omni.active and not omni.should_tx():
            skip_tx_this_cycle()
        omni.advance(qso_active=qso_sm.is_busy())
    """

    def __init__(self, block_cycles: int = 40):
        """
        Args:
            block_cycles: Zyklen pro Block vor dem Wechsel.
                          Empfohlen: settings.diversity_operate_cycles // 2
                          Default 40 = halbe Standard-Diversity (80 // 2)
        """
        self.active: bool = False       # True erst nach Easter-Egg-Aktivierung
        self.block: int = 1             # Aktueller Block (1 oder 2)
        self.block_cycles: int = max(10, block_cycles)
        self._cycle_count: int = 0      # Zyklen im aktuellen Block
        self._slot_index: int = 0       # Position im 5-Slot-Muster (0-4)

    # ─────────────────────────────────────────────────────────────────────────
    # Haupt-API
    # ─────────────────────────────────────────────────────────────────────────

    def should_tx(self) -> bool:
        """True wenn dieser Slot gesendet werden soll.

        Gibt True zurück wenn OMNI-TX deaktiviert (= normaler Betrieb).
        Gibt False zurück wenn dieser Slot ein Hörslot ist.
        """
        if not self.active:
            return True  # Deaktiviert → normaler Betrieb, immer TX
        return _TX_PATTERN[self._slot_index]

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
    # Aktivierung (nur via Easter Egg)
    # ─────────────────────────────────────────────────────────────────────────

    def enable(self) -> None:
        """OMNI-TX aktivieren. Nur via Easter-Egg aufrufen!"""
        self.active = True
        self._cycle_count = 0
        self._slot_index = 0
        self.block = 1
        logger.info("[OMNI-TX] Aktiviert — Even+Odd Slot-Rotation")

    def disable(self) -> None:
        """OMNI-TX deaktivieren. Zurück zu normalem CQ-Betrieb."""
        self.active = False
        self._cycle_count = 0
        self._slot_index = 0
        logger.info("[OMNI-TX] Deaktiviert — normaler Betrieb")

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
        old_block = self.block
        self.block = 2 if self.block == 1 else 1
        self._cycle_count = 0
        # Slot-Index auf Anfang neuen Blocks (Position 0 = sauberer Start)
        self._slot_index = 0
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
