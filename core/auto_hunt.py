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

from .message import looks_like_callsign
from .geo import callsign_to_country, callsign_to_distance

if TYPE_CHECKING:
    from core.message import FT8Message
    from log.qso_log import QSOLog

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# DX-Scoring (P165) — Seltenheit > Land-auf-Band-neu > Distanz > SNR > Slot.
# Lexikografische Tupel-Rangordnung (kleiner = hoehere Prioritaet), KEIN
# additives Gewichte-Tuning mehr. Fachlich begruendet: FT8 ist ein Schwach-
# signal-DX-Modus (dekodiert bis ~-24 dB unter dem Rauschen) — die seltene,
# weite, schwache Station ist die Perle, KEIN Ausschlussgrund (Mike 02.06.2026).
# ─────────────────────────────────────────────────────────────────────────────

# SNR-Boden statt Mindest-SNR: FT8 dekodiert bis ~-24 dB; -26 dB ist ein
# Sicherheitspuffer gegen Geister-/Rausch-Decodes. Schwache Signale sind der
# SINN des Modus (DX-Jagd) — frueher schnitt _MIN_SNR=-21 genau die Perlen ab.
SNR_FLOOR = -26

# Seltenheit fuer unaufloesbares Land ("?") oder fehlendes QSO-Log: neutral
# (Mitte), damit ein unbekannter/garbage Call NICHT faelschlich als ATNO-Perle
# (Klasse 0) ganz nach oben rutscht — aber auch nicht ganz nach unten faellt
# (koennte ein exotischer Sonderpraefix sein).
_RARITY_UNKNOWN = 2

_MAX_ATTEMPTS  = 3      # Max Anrufversuche pro Station
_COOLDOWN_SECS = 300    # 5 Minuten Cooldown nach fehlgeschlagenem Anruf
_PAUSE_CYCLES  = 1      # Zyklen Pause nach QSO-Ende bevor naechste Station


def country_rarity_class(count: int) -> int:
    """QSO-Count mit einem Land → persoenliche Seltenheits-Klasse (0..4).

    Kleiner = seltener = hoehere Prioritaet. Die Grenzen bilden die DX-Jagd-
    Psychologie ab: 1-5 = Erinnerungs-QSOs, 6-20 = halb gefuellt, >100 =
    Massenbetrieb. Der Bereich >100 wird bewusst zusammengefasst — ob 200 oder
    4000 QSOs spielt fuer die Prioritaet keine Rolle (beides "Allerweltsland").
    """
    if count <= 0:
        return 0   # ATNO — nie gearbeitet (groesste Perle)
    if count <= 5:
        return 1   # extrem selten
    if count <= 20:
        return 2   # selten
    if count <= 100:
        return 3   # gelegentlich
    return 4       # Allerweltsland

# P61 (v0.97.33): Recent-QSO-Cooldown — verhindert dass Auto-Hunt eine
# Station unmittelbar nach abgeschlossenem QSO (oder unmittelbar nach
# Pick durch Auto-Hunt selbst) erneut waehlt. Key (call, band, mode).
# P94 (v0.97.66): 5 Min → 30 Min für Konsistenz mit Quick-73-Fenster
# (`ui/mw_cycle.py:_QUICK73_WINDOW_S`). Hard-Cap-Timer (10 Min Laufzeit)
# bleibt unverändert — Bot-Tarn-Schutz wahren.
_RECENT_QSO_COOLDOWN_S = 1800


@dataclass
class _HuntCandidate:
    """Interne Repraesentation einer CQ-Station."""
    call: str
    grid: str
    snr: int
    freq_hz: int
    first_seen: float      # Unix-Timestamp
    tx_even: Optional[bool] = None  # Slot-Parity der Station


# P122 (2026-05-25): Reasons die bei aktivem QSO bis QSO-Ende deferiert
# werden. Alle anderen Reasons (manual_halt, swr_block, band_change,
# ft_mode_change, rx_mode_change, scoring_toggle, superseded) greifen
# sofort — Hardware-Safety oder Kontext-Wechsel.
_DEFER_REASONS = frozenset({
    "timer_expired",        # 10-Min-Hard-Cap
    "mouse_inactive_5min",  # 5-Min-Maus-Inaktivität (P67)
    "totmann_expired",      # 15-Min Operator-Presence
})


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

    # P169 Phase 2: Transparenz — feuert (entprellt) wenn ALLE decodierten,
    # sonst rufbaren CQ-Stationen auf dem aktuellen Band+Mode schon gearbeitet
    # sind. Args: (band, mode, n). main_window zeigt eine Info im QSO-Log.
    all_worked = Signal(str, str, int)

    def __init__(self, is_qso_active_callback=None):
        """
        Args:
            is_qso_active_callback: Optionaler Callback `() -> bool` der True
                liefert wenn QSO im aktiven Ruf-State (WAIT_REPORT, TX_CALL etc.)
                ist. P122: bei aktivem QSO werden 3 Stop-Reasons deferiert bis
                QSO-Ende. Default None → Fallback `lambda: False` (= nie
                deferieren, Backward-Compat für Tests/Legacy-Konstruktion).
        """
        super().__init__()
        self.active: bool = False
        # P122: Defer-Mechanik
        self._is_qso_active_callback = is_qso_active_callback or (lambda: False)
        self._pending_stop_reason: Optional[str] = None
        self._qso_log: Optional[QSOLog] = None
        self._band: str = "20m"
        self._mode: str = "FT8"     # P61: Mode-Awareness fuer Cooldown-Key
        self._my_grid: str = ""     # P165: eigener Locator fuer DX-Distanz
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
        # P169 Phase 2: Entprell-Flag fuer die „alle gearbeitet"-Transparenz-
        # Meldung. Reset NUR bei start_auto_hunt / set_band / set_mode (NICHT
        # pro Pick — sonst Meldung nach jedem QSO auf voll-gearbeitetem Band).
        self._all_worked_reported: bool = False
        # P164 (30.05.2026): Einschub-Merker entfernt — lebt jetzt als
        # `_qso_pending_insert` in MainWindow (vom Auto-Hunt entkoppelt).
        # P165: _last_tx_even ist jetzt der LETZTE Tiebreaker im DX-Scoring
        # (frueher ein harter Vorfilter). Bei laufender Session leicht
        # bevorzugt — eine seltene/weite Perle schlaegt den Slot-Vorzug.
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
        """Band setzen (fuer Worked-On-Band Check).

        P169 Phase 2: wird bei JEDEM Bandwechsel gerufen (auch bei inaktivem
        Auto-Hunt) → `_band` ist nie veraltet. Entprell-Flag der „alle
        gearbeitet"-Meldung zuruecksetzen (neuer Kontext)."""
        self._band = band
        self._all_worked_reported = False

    def set_mode(self, mode: str):
        """P61: Aktueller FT-Modus fuer Cooldown-Key. Wird bei Mode-Wechsel
        gerufen — z.B. wenn User von FT8 auf FT4 wechselt soll selbe
        Station auf neuem Modus sofort wieder anrufbar sein.

        P169 Phase 2: zusaetzlich Worked-On-Band-Mode-Check + Entprell-Flag der
        „alle gearbeitet"-Meldung zuruecksetzen (neuer Kontext)."""
        self._mode = (mode or "FT8").upper()
        self._all_worked_reported = False

    def set_my_grid(self, grid: str):
        """P165: eigenen Locator fuer die Distanz-Berechnung im DX-Scoring.

        Ohne Grid liefert callsign_to_distance None → Distanz faellt im Tupel
        auf 0 zurueck (kein Distanz-Vorzug, Seltenheit entscheidet allein).
        """
        self._my_grid = (grid or "").strip()

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
        # P139 (26.05.2026): MARK_PICK loggen fuer Diagnose
        try:
            from .debug_log import debug_log
            debug_log("HUNT", f"MARK_PICK call={call}")
        except Exception:
            pass
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
        # P169 Phase 2: frischer Kontext → Transparenz-Meldung wieder zulassen.
        self._all_worked_reported = False
        self._hunt_session_start = time.time()
        self._auto_hunt_timer.setInterval(duration_sec * 1000)
        self._auto_hunt_timer.start()
        logger.info(f"[Auto-Hunt] Start (duration={duration_sec}s)")
        print(f"[Auto-Hunt] Aktiviert — laeuft {duration_sec // 60} Min")
        # P139 (26.05.2026): Event-Log fuer Auto-Hunt-Delay-Diagnose
        try:
            from .debug_log import debug_log
            debug_log("HUNT", f"START band={self._band} mode={self._mode} "
                              f"duration={duration_sec}s")
        except Exception:
            pass  # debug_log darf NIE crashen

    def stop_auto_hunt(self, reason: str):
        """Auto-Hunt-Session beenden. Emittiert auto_hunt_stopped(reason).

        Reasons:
            timer_expired      — 10-Min-Hard-Stop abgelaufen  [DEFER]
            mouse_inactive_5min — 5 Min ohne Mausbewegung      [DEFER]
            totmann_expired    — Operator-Presence (15 Min)    [DEFER]
            manual_halt        — User klickte HALT-Button       [SOFORT]
            band_change        — Band wurde gewechselt          [SOFORT]
            mode_change/ft_mode_change — Modus gewechselt       [SOFORT]
            rx_mode_change     — Normal↔Diversity gewechselt    [SOFORT]
            scoring_toggle     — Std↔DX gewechselt              [SOFORT]
            superseded         — anderer Modus (z.B. OMNI)      [SOFORT]
            swr_block          — SWR-Watchdog (Hardware-Safety) [SOFORT]

        P122 (2026-05-25) Defer-Mechanik:
            Bei DEFER-Reasons UND aktivem QSO (is_qso_active_callback()=True)
            wird _pending_stop_reason gesetzt, KEIN active=False, KEIN Signal.
            main_window ruft flush_pending_stop() bei QSO-Ende auf → echter
            Stop läuft dann durch (Defer-Check schlägt fehl da QSO idle).

        Cleanup-Logik (reason-basiert):
            timer_expired/manual_halt/band_change/mode_change/rx_mode_change/
            superseded/mouse_inactive_5min:
                _cooldown.clear() + _last_tx_even = None
            totmann_expired:
                _cooldown UND _last_tx_even bleiben (User soll fortsetzen)
        """
        # P122 R1-F3: Defensive Idempotenz — wenn bereits inaktiv UND kein
        # Pending, ist nichts zu tun (verhindert doppelte Signal-Emission).
        if not self.active and self._pending_stop_reason is None:
            return

        # P139 R1-F1 ORANGE: STOP-Reason VOR Defer-Check loggen damit
        # deferierte Stops nicht unsichtbar bleiben.
        try:
            from .debug_log import debug_log
            will_defer = (reason in _DEFER_REASONS
                          and self._is_qso_active_callback())
            suffix = " [DEFERRED]" if will_defer else ""
            debug_log("HUNT", f"STOP reason={reason}{suffix}")
        except Exception:
            pass

        # P122: Defer für 3 Stop-Reasons wenn QSO aktiv.
        if reason in _DEFER_REASONS and self._is_qso_active_callback():
            if self._pending_stop_reason is None:
                self._pending_stop_reason = reason
                logger.info(f"[Auto-Hunt] Stop deferiert (reason={reason}, "
                            "QSO läuft — wird bei QSO-Ende ausgeführt)")
                print(f"[Auto-Hunt] Stop deferiert ({reason}) — QSO läuft")
            else:
                # FIFO: erster Defer-Reason gewinnt (chronologisch)
                logger.info(f"[Auto-Hunt] Stop {reason} verworfen — "
                            f"{self._pending_stop_reason} ist schon pending")
            return  # KEIN active=False, KEIN Signal-Emit

        # Sofortiger Stop (alle anderen Reasons ODER QSO idle).
        # P122: Pending-Reset bei sofortigem Stop — HALT/Band/SWR überschreibt
        # einen evtl. gesetzten Defer-Reason.
        self._pending_stop_reason = None

        self.active = False
        self._current_target = None
        self._auto_hunt_timer.stop()
        # P164 (30.05.2026): Einschub-Merker `_qso_pending_insert` lebt in
        # MainWindow und wird dort beim Auto-Hunt-Stop NICHT genullt (ein
        # manuell vorgemerktes B soll einen Auto-Hunt-Stop überleben). Cleanup
        # nur via HALT/Band/Mode/RX/Konsum.

        if reason != "totmann_expired":
            self._cooldown.clear()
            self._last_tx_even = None

        logger.info(f"[Auto-Hunt] Stop (reason={reason})")
        print(f"[Auto-Hunt] Gestoppt — {reason}")
        self.auto_hunt_stopped.emit(reason)

    def flush_pending_stop(self):
        """P122 (2026-05-25): Wird von main_window bei QSO-Ende gerufen.

        Wenn ein Defer-Reason pending ist, jetzt echten Stop durchführen
        (Defer-Check schlägt fehl da Callback nun False liefert / QSO idle).
        No-op wenn nichts pending.

        Aufrufer:
            _on_qso_confirmed_visual — QSO ✓ komplett
            _on_qso_timeout          — QSO ✗ Timeout
            _on_cancel               — HALT-Pfad
        """
        if self._pending_stop_reason is None:
            return
        reason = self._pending_stop_reason
        self._pending_stop_reason = None
        # Rekursiver Aufruf → Defer-Check fällt durch (QSO idle), echter Stop.
        self.stop_auto_hunt(reason)

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
        # P139 (26.05.2026): Auto-Hunt Event-Logging fuer Delay-Diagnose
        try:
            from .debug_log import debug_log as _hlog
        except Exception:
            _hlog = lambda *a, **kw: None  # noqa: E731

        _hlog("HUNT", f"SELECT_NEXT msgs={len(messages or [])} "
                     f"qso_idle={qso_idle} presence={presence_ok} "
                     f"active={self.active} override={self._manual_override}")

        if not self.active:
            _hlog("HUNT", "EARLY_RETURN reason=not_active")
            return None
        if not presence_ok:
            _hlog("HUNT", "EARLY_RETURN reason=not_presence")
            return None
        if not qso_idle:
            _hlog("HUNT", "EARLY_RETURN reason=not_qso_idle")
            return None
        if self._manual_override:
            _hlog("HUNT", "EARLY_RETURN reason=manual_override")
            return None

        # CQ-Stationen filtern
        now = time.time()
        candidates: List[_HuntCandidate] = []

        for msg in (messages or []):
            if not getattr(msg, 'is_cq', False):
                continue
            call = msg.caller
            if not call:
                _hlog("HUNT", "SKIP reason=empty_call")
                continue

            # P136 (26.05.2026 Mike-Field-Bug "JA"): Call-Validation als
            # Defense-in-Depth. Parser-Fix in message.py greift normalerweise
            # ab, aber falls eine fehlgeparste Pseudo-Call durchrutscht
            # (Direction-Marker, Keyword), nicht anrufen.
            # Slash-tolerant: laengstes Segment pruefen (DA1MHH/P → DA1MHH).
            base = max(call.split("/"), key=len) if "/" in call else call
            if not looks_like_callsign(base):
                _hlog("HUNT", f"SKIP call={call} reason=not_callsign")
                continue

            # P61 (v0.97.33): Recent-QSO-Cooldown (Pick + Abschluss).
            # VOR Fail-Cooldown — wir wollen lieber gar nicht anrufen
            # statt nach Fehler weiter zu versuchen.
            base = call.strip().upper().split("/")[0]
            key = (base, self._band.upper(), self._mode.upper())
            last_qso = self._recent_qso.get(key, 0)
            if now - last_qso < _RECENT_QSO_COOLDOWN_S:
                _hlog("HUNT", f"SKIP call={call} reason=recent_qso_cooldown "
                              f"age={int(now - last_qso)}s")
                continue
            elif last_qso > 0:
                # Lazy-Cleanup: abgelaufener Eintrag (R1-F4)
                del self._recent_qso[key]

            # Cooldown: kuerzlich fehlgeschlagen → ueberspringen
            last_fail = self._cooldown.get(call, 0)
            if now - last_fail < _COOLDOWN_SECS:
                _hlog("HUNT", f"SKIP call={call} reason=fail_cooldown "
                              f"age={int(now - last_fail)}s")
                continue

            # P165: SNR-Boden statt Mindest-SNR. Schwache DX-Signale sind die
            # Perlen — nur klare Rausch-/Geister-Decodes (< -26 dB) raus.
            snr = msg.snr if msg.snr is not None else -30
            if snr < SNR_FLOOR:
                _hlog("HUNT", f"SKIP call={call} reason=below_floor snr={snr}")
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

        _hlog("HUNT", f"CANDIDATES n={len(candidates)}")
        if not candidates:
            _hlog("HUNT", "NO_CANDIDATE reason=empty_list")
            return None

        # P165/P169 Phase 2: schon gearbeitete STATION (dieser Call) auf diesem
        # Band UND in diesem Mode raus — keine Dublette. Mode-genau: dieselbe
        # Station auf 20m FT8 gearbeitet bleibt auf 20m FT4 ein gueltiges Ziel.
        # Eine ANDERE Station aus demselben (seltenen) Land bleibt Kandidat.
        n_before_worked = len(candidates)
        if self._qso_log is not None:
            candidates = [c for c in candidates
                          if not self._qso_log.is_worked_on_band_mode(
                              c.call, self._band, self._mode)]
        if not candidates:
            _hlog("HUNT", "NO_CANDIDATE reason=all_worked_on_band")
            # P169 Phase 2: Transparenz. Es gab rufbare CQ-Stationen, aber alle
            # sind auf Band+Mode schon gearbeitet → einmal (entprellt) melden,
            # damit der stille Auto-Hunt nicht raetselhaft wirkt.
            if n_before_worked > 0 and not self._all_worked_reported:
                self._all_worked_reported = True
                self.all_worked.emit(self._band, self._mode, n_before_worked)
            return None

        # P165: DX-Scoring als lexikografische Tupel-Rangordnung (kleiner =
        # hoehere Prioritaet). Seltenheit > Land-auf-Band-neu > Distanz > SNR >
        # Slot. Tupel mitfuehren fuers Logging.
        scored = sorted(((self._compute_priority(c), c) for c in candidates),
                        key=lambda t: t[0])
        best_prio, best = scored[0]

        # Race-Condition-Sicherung: zwischen Anfangs-Check und Return koennte
        # _auto_hunt_timer abgelaufen sein. Mike's 10-Min-Hard-Cap ist ethisch
        # gesetzt — kein "letztes QSO" nach Ablauf.
        if not self.active:
            _hlog("HUNT", "NO_CANDIDATE reason=race_inactive_before_return")
            return None

        self._current_target = best.call
        self._last_tx_even = best.tx_even  # Slot-Tiebreaker fuer naechsten Zyklus
        print(f"[Auto-Hunt] Ausgewaehlt: {best.call} "
              f"(SNR={best.snr}, Prio={best_prio}, slot={best.tx_even})")
        _hlog("HUNT", f"PICKED call={best.call} prio={best_prio} "
                      f"snr={best.snr} tx_even={best.tx_even} freq={best.freq_hz}")
        return best

    def _compute_priority(self, c: _HuntCandidate) -> tuple:
        """DX-Scoring als lexikografisches Tupel (kleiner = hoehere Prioritaet).

        Reihenfolge (P165):
          1. R         persoenliche Land-Seltenheit (0 ATNO .. 4 Allerwelt)
          2. band_new  0 = Land auf diesem Band neu (Perle), 1 = schon gehabt
          3. -dist     Distanz (weiter = kleiner = besser; Tiebreaker bei gleich R)
          4. -snr      Signalstaerke (staerker = kleiner; nur Fein-Tiebreaker)
          5. slot      0 = gleicher TX-Slot wie laufende Session, 1 = anders

        Persoenliche Seltenheit ist das LEITMASS, Distanz nur Tiebreaker unter
        gleicher Seltenheit — sonst schluege das weite-aber-haeufige USA das
        nahe-aber-seltene San Marino. SNR ist KEIN K.o.-Kriterium mehr.
        """
        country = callsign_to_country(c.call)
        if self._qso_log is not None and country and country != "?":
            r = country_rarity_class(self._qso_log.get_country_count(country))
            band_new = 0 if not self._qso_log.is_country_worked_on_band(
                country, self._band) else 1
        else:
            # Kein Log oder unaufloesbares Land: neutral, NIE als ATNO-Perle.
            r = _RARITY_UNKNOWN
            band_new = 1
        dist = callsign_to_distance(c.call, self._my_grid) if self._my_grid else None
        dist = dist if dist is not None else 0
        slot = 0 if (self._last_tx_even is not None
                     and c.tx_even == self._last_tx_even) else 1
        return (r, band_new, -dist, -c.snr, slot)

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

    def clear_current_target(self):
        """P144 (27.05.2026): _current_target zurücksetzen OHNE Cooldown.

        Genutzt vom P144-Busy-Station-Filter (ui/mw_cycle.py): wenn das
        Auto-Hunt-Target gerade an Fremd-Call sendet, brechen wir ab und
        überspringen — Target soll für späteren Pick verfügbar bleiben,
        deshalb kein `mark_pick` und kein `_cooldown`-Eintrag.

        Unterschied zu `on_qso_complete` (setzt P61-Recent-Cooldown 5 Min)
        und `on_qso_timeout` (setzt 5-Min-Cooldown). Hier nur State-Reset.
        """
        self._current_target = None

    # P164 (30.05.2026): set_pending_insert/take_pending_insert ENTFERNT.
    # Der Einschub-Merker lebt jetzt als `_qso_pending_insert` in MainWindow
    # (vom Auto-Hunt entkoppelt, funktioniert auch ohne laufende Session).

    def on_band_change(self):
        """Bandwechsel → Auto-Hunt-Session beenden + Cooldowns loeschen.

        Delegiert an stop_auto_hunt("band_change") fuer zentralisierte
        Cleanup-Logik und Signal-Emit.
        """
        self.stop_auto_hunt("band_change")
