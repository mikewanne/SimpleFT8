"""SimpleFT8 Auto-Hunt — Automatisches Anrufen von CQ-Stationen.

INTERN / VERSTECKT — Keine oeffentliche Dokumentation!

Aktivierung: Zusammen mit OMNI-TX via Easter Egg (Klick Versionsnummer).
Deaktivierung: Gleicher Klick oder HALT-Button.

Funktionsweise:
  1. Nach jedem Decode-Zyklus: CQ-Stationen erkennen
  2. Beste Station per Scoring waehlen (Neue > Seltene DXCC > SNR)
  3. Automatisch anrufen (max 3 Versuche, dann naechste)
  4. Nach QSO-Ende: 1 Zyklus Pause, dann naechste Station

Sicherheiten:
  - Totmannschalter MUSS aktiv sein (presence_can_tx)
  - Manueller Station-Klick → Auto-Hunt sofort pausiert
  - HALT → alles aus
  - Nur wenn QSO-State = IDLE oder CQ_WAIT
"""

from __future__ import annotations

import time
import logging
from dataclasses import dataclass
from typing import Optional, List, TYPE_CHECKING

if TYPE_CHECKING:
    from core.message import FT8Message
    from log.qso_log import QSOLog

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Scoring-Gewichte (nicht konfigurierbar — fest)
# ─────────────────────────────────────────────────────────────────────────────

_W_NEW_STATION = 3.0    # Noch nie gearbeitet → hoechste Prioritaet
_W_NEW_BAND    = 2.0    # Gearbeitet, aber nicht auf diesem Band
_W_SNR         = 0.1    # Leichte Praeferenz fuer staerkere Signale
_W_AGE         = 0.05   # Aeltere CQs leicht bevorzugt (Fairness)

# Grenzen
_MIN_SNR       = -21    # Unter -21 dB lohnt sich der Versuch nicht
_MAX_ATTEMPTS  = 3      # Max Anrufversuche pro Station
_COOLDOWN_SECS = 300    # 5 Minuten Cooldown nach fehlgeschlagenem Anruf
_PAUSE_CYCLES  = 1      # Zyklen Pause nach QSO-Ende bevor naechste Station


@dataclass
class _HuntCandidate:
    """Interne Repraesentation einer CQ-Station."""
    call: str
    grid: str
    snr: int
    freq_hz: int
    first_seen: float      # Unix-Timestamp
    score: float = 0.0
    tx_even: Optional[bool] = None  # Slot-Parity der Station


class AutoHunt:
    """Auto-Hunt Controller — waehlt und ruft CQ-Stationen automatisch an.

    Verwendung (wenn aktiviert via Easter Egg):
        auto = AutoHunt(qso_log, band)
        # Nach jedem Decode-Zyklus:
        candidate = auto.select_next(messages, current_state)
        if candidate:
            start_qso(candidate)  # Bestehendes Hunt-QSO starten
    """

    def __init__(self):
        self.active: bool = False
        self._qso_log: Optional[QSOLog] = None
        self._band: str = "20m"
        self._cooldown: dict[str, float] = {}  # call → timestamp (letzer Fehlversuch)
        self._pause_remaining: int = 0          # Zyklen Pause nach QSO
        self._manual_override: bool = False     # Manueller Klick → pausieren
        self._current_target: Optional[str] = None  # Aktuell angerufene Station

    def set_qso_log(self, qso_log: "QSOLog"):
        """QSO-Log fuer Worked-Before setzen."""
        self._qso_log = qso_log

    def set_band(self, band: str):
        """Band setzen (fuer Worked-On-Band Check)."""
        self._band = band

    # ─────────────────────────────────────────────────────────────────────────
    # Aktivierung (zusammen mit OMNI-TX)
    # ─────────────────────────────────────────────────────────────────────────

    def enable(self):
        """Auto-Hunt aktivieren."""
        self.active = True
        self._manual_override = False
        self._pause_remaining = 0
        self._current_target = None
        self._cooldown.clear()
        logger.info("[Auto-Hunt] Aktiviert")
        print("[Auto-Hunt] Aktiviert — automatisches Anrufen von CQ-Stationen")

    def disable(self):
        """Auto-Hunt deaktivieren."""
        self.active = False
        self._current_target = None
        self._manual_override = False
        logger.info("[Auto-Hunt] Deaktiviert")
        print("[Auto-Hunt] Deaktiviert")

    # ─────────────────────────────────────────────────────────────────────────
    # Kern-Logik: Station auswaehlen
    # ─────────────────────────────────────────────────────────────────────────

    def select_next(
        self,
        messages: list,
        qso_idle: bool,
        presence_ok: bool,
    ) -> Optional[_HuntCandidate]:
        """Naechste CQ-Station zum Anrufen auswaehlen.

        Args:
            messages: Dekodierte FT8-Nachrichten dieses Zyklus
            qso_idle: True wenn QSO State Machine im IDLE ist
            presence_ok: True wenn Totmannschalter aktiv (Operator anwesend)

        Returns:
            HuntCandidate oder None wenn nichts zu tun.
        """
        if not self.active:
            return None
        if not presence_ok:
            return None
        if not qso_idle:
            return None
        if self._manual_override:
            return None

        # Pause nach QSO-Ende
        if self._pause_remaining > 0:
            self._pause_remaining -= 1
            return None

        # CQ-Stationen filtern
        now = time.time()
        candidates: List[_HuntCandidate] = []

        for msg in (messages or []):
            if not getattr(msg, 'is_cq', False):
                continue
            call = msg.caller
            if not call:
                continue

            # Cooldown: kuerzlich fehlgeschlagen → ueberspringen
            last_fail = self._cooldown.get(call, 0)
            if now - last_fail < _COOLDOWN_SECS:
                continue

            # SNR-Minimum
            snr = msg.snr if msg.snr is not None else -30
            if snr < _MIN_SNR:
                continue

            grid = msg.grid_or_report if getattr(msg, 'is_grid', False) else ""
            tx_even = getattr(msg, '_tx_even', None)

            candidates.append(_HuntCandidate(
                call=call,
                grid=grid,
                snr=snr,
                freq_hz=msg.freq_hz,
                first_seen=now,
                tx_even=tx_even,
            ))

        if not candidates:
            return None

        # Scoring
        for c in candidates:
            c.score = self._score(c)

        # Beste Station (hoechster Score)
        candidates.sort(key=lambda c: c.score, reverse=True)
        best = candidates[0]

        if best.score <= 0:
            return None

        self._current_target = best.call
        print(f"[Auto-Hunt] Ausgewaehlt: {best.call} "
              f"(SNR={best.snr}, Score={best.score:.1f})")
        return best

    def _score(self, c: _HuntCandidate) -> float:
        """Prioritaets-Score berechnen."""
        score = 0.0

        # Noch nie gearbeitet → hoechste Prioritaet
        if self._qso_log:
            if not self._qso_log.is_worked(c.call):
                score += _W_NEW_STATION
            elif not self._qso_log.is_worked_on_band(c.call, self._band):
                score += _W_NEW_BAND
            # Schon auf diesem Band gearbeitet → Score 0 (ueberspringen)
            else:
                return 0.0
        else:
            # Kein QSO-Log → alle gleich behandeln
            score += _W_NEW_STATION

        # SNR-Bonus (normalisiert: -21 dB → 0, +10 dB → 3.1)
        score += _W_SNR * max(0, c.snr + 21)

        return score

    # ─────────────────────────────────────────────────────────────────────────
    # Events
    # ─────────────────────────────────────────────────────────────────────────

    def on_qso_complete(self, call: str):
        """QSO erfolgreich beendet → Pause einlegen, dann weiter."""
        self._current_target = None
        self._pause_remaining = _PAUSE_CYCLES
        # Cooldown entfernen (erfolgreich)
        self._cooldown.pop(call, None)
        print(f"[Auto-Hunt] QSO mit {call} fertig — {_PAUSE_CYCLES} Zyklen Pause")

    def on_qso_timeout(self, call: str):
        """QSO fehlgeschlagen (Timeout) → Cooldown setzen."""
        self._current_target = None
        self._cooldown[call] = time.time()
        self._pause_remaining = 0  # Sofort naechste versuchen
        print(f"[Auto-Hunt] Timeout {call} — {_COOLDOWN_SECS // 60} Min Cooldown")

    def on_manual_qso_start(self):
        """Operator hat manuell eine Station angeklickt → Auto-Hunt pausieren."""
        self._manual_override = True
        self._current_target = None
        print("[Auto-Hunt] Manueller QSO-Start — Auto-Hunt pausiert")

    def on_manual_qso_end(self):
        """Manuelles QSO beendet → Auto-Hunt wieder freigeben."""
        self._manual_override = False
        self._pause_remaining = _PAUSE_CYCLES
        print("[Auto-Hunt] Manuelles QSO beendet — Auto-Hunt wird fortgesetzt")

    def on_band_change(self):
        """Bandwechsel → Cooldowns loeschen."""
        self._cooldown.clear()
        self._current_target = None
        self._pause_remaining = 0
