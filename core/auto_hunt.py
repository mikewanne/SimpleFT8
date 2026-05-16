"""SimpleFT8 Auto-Hunt — Automatisches Anrufen von CQ-Stationen.

INTERN / VERSTECKT — Keine oeffentliche Dokumentation!

Sichtbarkeit: Mode-gekoppelt — Button btn_auto_hunt ist nur im
Diversity-Modus sichtbar (siehe MainWindow._update_button_visibility).
Deaktivierung: HALT-Button oder Mode-Wechsel nach Normal.

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

from PySide6.QtCore import QObject, QTimer, Signal

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

# P61 (v0.97.33): Recent-QSO-Cooldown — verhindert dass Auto-Hunt eine
# Station unmittelbar nach abgeschlossenem QSO (oder unmittelbar nach
# Pick durch Auto-Hunt selbst) erneut waehlt. Key (call, band, mode),
# Cooldown 5 Min analog ADIF-Dedup `_LOG_DEDUP_WINDOW_S=300` aus P1.7.
_RECENT_QSO_COOLDOWN_S = 300


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


class AutoHunt(QObject):
    """Auto-Hunt Controller — waehlt und ruft CQ-Stationen automatisch an.

    Erbt von QObject damit Signal-Emit (Commit 4: auto_hunt_stopped) sauber
    funktioniert und Qt-Lifecycle (deleteLater etc.) greift.

    Verwendung (sichtbar im Diversity-Modus):
        auto = AutoHunt(qso_log, band)
        # Nach jedem Decode-Zyklus:
        candidate = auto.select_next(messages, current_state)
        if candidate:
            start_qso(candidate)  # Bestehendes Hunt-QSO starten
    """

    # ─────────────────────────────────────────────────────────────────────────
    # Qt-Signal: wird bei JEDEM stop_auto_hunt(reason) emittiert.
    # Reasons: "timer_expired", "manual_halt", "band_change",
    #          "mode_change", "rx_mode_change", "totmann_expired", "superseded"
    # ─────────────────────────────────────────────────────────────────────────
    auto_hunt_stopped = Signal(str)

    def __init__(self):
        super().__init__()
        self.active: bool = False
        self._qso_log: Optional[QSOLog] = None
        self._band: str = "20m"
        self._mode: str = "FT8"     # P61: Mode-Awareness fuer Cooldown-Key
        # Anruf-Fehlversuch-Cooldown (5 Min Sperre nach on_qso_timeout):
        self._cooldown: dict[str, float] = {}
        # P61 (v0.97.33): Recent-QSO-Cooldown nach Pick/Abschluss.
        # Schluessel: (base_call, band, mode), Wert: time.time().
        # Robust gegen Race (Decoder-cycle_decoded vs Encoder-tx_finished)
        # und gegen Hypothese A (adif.log_qso wirft Exception → qso_log
        # bleibt stale).
        self._recent_qso: dict[tuple[str, str, str], float] = {}
        self._manual_override: bool = False     # Manueller Klick → pausieren
        self._current_target: Optional[str] = None
        # Slot-Affinitaet — bevorzugt Kandidaten mit gleichem tx_even:
        self._last_tx_even: Optional[bool] = None
        # Zeit-beschraenkte Session (10-Min-Hard-Stop):
        self._hunt_session_start: float = 0.0
        self._auto_hunt_timer = QTimer(self)
        self._auto_hunt_timer.setSingleShot(True)
        self._auto_hunt_timer.timeout.connect(self._on_timer_expired)

    def set_qso_log(self, qso_log: "QSOLog"):
        """QSO-Log fuer Worked-Before setzen."""
        self._qso_log = qso_log

    def set_band(self, band: str):
        """Band setzen (fuer Worked-On-Band Check)."""
        self._band = band

    def set_mode(self, mode: str):
        """P61: Aktueller FT-Modus fuer Cooldown-Key. Wird bei Mode-Wechsel
        gerufen — z.B. wenn User von FT8 auf FT4 wechselt soll selbe
        Station auf neuem Modus sofort wieder anrufbar sein."""
        self._mode = (mode or "FT8").upper()

    def mark_pick(self, call: str):
        """P61: Pick-Zeitpunkt-Cooldown setzen. Verhindert dass Auto-Hunt
        eine Station, die gerade angerufen wurde, sofort wieder pickt —
        auch wenn `qso_log.add_qso` aus irgendeinem Grund nicht synchron
        laeuft (Race zwischen tx_finished und cycle_decoded, oder
        Exception in adif.log_qso).

        Wird in 2 Pfaden aufgerufen:
        1. `mw_cycle._run_auto_hunt` direkt nach erfolgreichem
           `select_next` (PRIMAERER Pfad, P61-Wirkung)
        2. `on_qso_complete` als redundante Sicherung (manuelle QSOs)
        """
        if not call:
            return
        base = call.strip().upper().split("/")[0]
        key = (base, self._band.upper(), self._mode.upper())
        self._recent_qso[key] = time.time()

    # ─────────────────────────────────────────────────────────────────────────
    # Session-Lifecycle (zeit-beschraenkter Auto-Hunt-Modus)
    # ─────────────────────────────────────────────────────────────────────────

    def start_auto_hunt(self, duration_sec: int = 600):
        """Eine zeit-beschraenkte Auto-Hunt-Session starten.

        Maus/Tastatur-Aktivitaet beeinflusst diesen Timer NICHT (Bot-Tarn-Schutz).
        Doppelklick-Schutz: bei aktiver Session wird der alte Timer gestoppt
        und ein neuer gestartet (Idempotenz).

        Args:
            duration_sec: Sessiondauer in Sekunden. Default 600 = 10 Min.
        """
        # Doppelklick-Schutz: laufenden Timer stoppen, clean state
        if self.active:
            self._auto_hunt_timer.stop()

        self.active = True
        self._manual_override = False
        self._current_target = None
        self._cooldown.clear()
        self._last_tx_even = None
        self._hunt_session_start = time.time()
        self._auto_hunt_timer.setInterval(duration_sec * 1000)
        self._auto_hunt_timer.start()
        logger.info(f"[Auto-Hunt] Start (duration={duration_sec}s)")
        print(f"[Auto-Hunt] Aktiviert — laeuft {duration_sec // 60} Min")

    def stop_auto_hunt(self, reason: str):
        """Auto-Hunt-Session beenden. Emittiert auto_hunt_stopped(reason).

        Reasons:
            timer_expired   — 10-Min-Hard-Stop abgelaufen
            manual_halt     — User klickte HALT-Button
            band_change     — Band wurde gewechselt
            mode_change     — FT8/FT4/FT2 wurde gewechselt
            rx_mode_change  — Normal↔Diversity wurde gewechselt
            totmann_expired — Operator-Presence (15 Min) abgelaufen
            superseded      — anderer Power-Modus (z.B. OMNI) gestartet

        Cleanup-Logik (reason-basiert):
            timer_expired/manual_halt/band_change/mode_change/rx_mode_change/superseded:
                _cooldown.clear() + _last_tx_even = None
            totmann_expired:
                _cooldown UND _last_tx_even bleiben (User soll fortsetzen)
        """
        self.active = False
        self._current_target = None
        self._auto_hunt_timer.stop()

        if reason != "totmann_expired":
            self._cooldown.clear()
            self._last_tx_even = None

        logger.info(f"[Auto-Hunt] Stop (reason={reason})")
        print(f"[Auto-Hunt] Gestoppt — {reason}")
        self.auto_hunt_stopped.emit(reason)

    def _on_timer_expired(self):
        """Wird vom QTimer aufgerufen wenn die 10 Min abgelaufen sind."""
        self.stop_auto_hunt("timer_expired")

    def seconds_remaining(self) -> int:
        """Restzeit der laufenden Session in Sekunden, 0 wenn nicht aktiv."""
        if not self.active:
            return 0
        remaining_ms = self._auto_hunt_timer.remainingTime()
        if remaining_ms <= 0:
            return 0
        return remaining_ms // 1000

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

        # CQ-Stationen filtern
        now = time.time()
        candidates: List[_HuntCandidate] = []

        for msg in (messages or []):
            if not getattr(msg, 'is_cq', False):
                continue
            call = msg.caller
            if not call:
                continue

            # P61 (v0.97.33): Recent-QSO-Cooldown (Pick + Abschluss).
            # VOR Fail-Cooldown — wir wollen lieber gar nicht anrufen
            # statt nach Fehler weiter zu versuchen.
            base = call.strip().upper().split("/")[0]
            key = (base, self._band.upper(), self._mode.upper())
            last_qso = self._recent_qso.get(key, 0)
            if now - last_qso < _RECENT_QSO_COOLDOWN_S:
                continue
            elif last_qso > 0:
                # Lazy-Cleanup: abgelaufener Eintrag (R1-F4)
                del self._recent_qso[key]

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

        # Slot-Affinitaet: bei laufender Session bevorzugt gleiches tx_even,
        # Fallback auf alle Kandidaten wenn keiner mit gleichem Slot.
        if self._last_tx_even is not None:
            same_slot = [c for c in candidates if c.tx_even == self._last_tx_even]
            if same_slot:
                candidates = same_slot

        # Scoring
        for c in candidates:
            c.score = self._score(c)

        # Beste Station (hoechster Score)
        candidates.sort(key=lambda c: c.score, reverse=True)
        best = candidates[0]

        if best.score <= 0:
            return None

        # Race-Condition-Sicherung: zwischen Anfangs-Check und Return koennte
        # _auto_hunt_timer abgelaufen sein. Mike's 10-Min-Hard-Cap ist ethisch
        # gesetzt — kein "letztes QSO" nach Ablauf.
        if not self.active:
            return None

        self._current_target = best.call
        self._last_tx_even = best.tx_even  # Slot-Affinitaet fuer naechsten Zyklus
        print(f"[Auto-Hunt] Ausgewaehlt: {best.call} "
              f"(SNR={best.snr}, Score={best.score:.1f}, slot={best.tx_even})")
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
        """QSO erfolgreich beendet → naechster Slot kann neue Station waehlen.

        P61 (v0.97.33): Recent-QSO-Cooldown setzen — redundante Sicherung
        zum Pick-Zeitpunkt-Cooldown in `mw_cycle._run_auto_hunt`. Deckt
        manuelle QSO-Pfade (User klickt selbst auf Station im RX-Panel
        und schliesst QSO ab) — dort gibt's keinen Pick durch select_next,
        also setzt nur dieser Pfad den Cooldown.
        """
        self._current_target = None
        # Cooldown entfernen (erfolgreich)
        self._cooldown.pop(call, None)
        # P61: Recent-QSO-Cooldown (5 Min) — verhindert Re-Pick durch
        # Auto-Hunt-Auto-Logik. Manuelle Klicks gehen weiterhin durch
        # (eigener Pfad in `_on_station_clicked`).
        self.mark_pick(call)
        print(f"[Auto-Hunt] QSO mit {call} fertig — Recent-Cooldown gesetzt")

    def on_qso_timeout(self, call: str):
        """QSO fehlgeschlagen (Timeout) → Cooldown setzen."""
        self._current_target = None
        self._cooldown[call] = time.time()
        print(f"[Auto-Hunt] Timeout {call} — {_COOLDOWN_SECS // 60} Min Cooldown")

    def on_manual_qso_start(self):
        """Operator hat manuell eine Station angeklickt → Auto-Hunt pausieren."""
        self._manual_override = True
        self._current_target = None
        print("[Auto-Hunt] Manueller QSO-Start — Auto-Hunt pausiert")

    def on_manual_qso_end(self):
        """Manuelles QSO beendet → Auto-Hunt wieder freigeben."""
        self._manual_override = False
        print("[Auto-Hunt] Manuelles QSO beendet — Auto-Hunt wird fortgesetzt")

    def on_band_change(self):
        """Bandwechsel → Auto-Hunt-Session beenden + Cooldowns loeschen.

        Delegiert an stop_auto_hunt("band_change") fuer zentralisierte
        Cleanup-Logik und Signal-Emit.
        """
        self.stop_auto_hunt("band_change")
