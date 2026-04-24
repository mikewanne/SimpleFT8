"""SimpleFT8 QSO State Machine — Zustandsmaschine für QSO-Ablauf.

Unterstützt zwei Modi:
1. HUNT: Operator klickt Station an → QSO manuell/auto durchführen
2. CQ:   Operator drückt CQ → ruft CQ, beantwortet automatisch
"""

import time
from enum import Enum, auto
from dataclasses import dataclass
from pathlib import Path
from PySide6.QtCore import QObject, Signal

from .message import FT8Message


class QSODebugLog:
    """Detailliertes QSO-Logging — wird bei jedem neuen QSO ueberschrieben."""

    def __init__(self, path: str = "qso_debug.log"):
        self._path = Path(path)
        self._lines = []

    def reset(self, their_call: str):
        """Neues QSO startet — altes Log ueberschreiben."""
        self._lines = [
            f"{'='*60}",
            f"QSO DEBUG LOG — {their_call}",
            f"Start: {time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime())} UTC",
            f"{'='*60}",
        ]
        self._flush()

    def log(self, category: str, message: str):
        """Eintrag loggen: [UTC] [KATEGORIE] Nachricht"""
        utc = time.strftime("%H:%M:%S", time.gmtime())
        line = f"[{utc}] [{category:>8}] {message}"
        self._lines.append(line)
        print(f"[QSO-DBG] {line}")
        self._flush()

    def _flush(self):
        try:
            self._path.write_text("\n".join(self._lines) + "\n")
        except Exception:
            pass


class QSOState(Enum):
    IDLE = auto()
    # --- CQ-Modus ---
    CQ_CALLING = auto()     # Sende "CQ DA1MHH JO31"
    CQ_WAIT = auto()        # Warte auf Anrufer
    # --- QSO-Sequenz (Hunt + CQ) ---
    TX_CALL = auto()        # Sende "DA1MHH DX5ABC JO31" (Hunt)
    WAIT_REPORT = auto()    # Warte auf Rapport
    TX_REPORT = auto()      # Sende Rapport
    WAIT_RR73 = auto()      # Warte auf RR73
    TX_RR73 = auto()        # Sende RR73
    WAIT_73 = auto()        # Warte auf 73 (QSO schon geloggt)
    LOGGING = auto()        # QSO abgeschlossen (legacy, nicht mehr genutzt)
    TIMEOUT = auto()        # Keine Antwort


MAX_QSO_DURATION = 180  # Gesamt-QSO Timeout: 3 Minuten
MAX_STATION_CALLS = 7   # Max Anrufe auf eine Station (hart)
MAX_RR73_RETRIES = 3    # Max Retries in WAIT_RR73


@dataclass
class QSOData:
    their_call: str = ""
    their_grid: str = ""
    their_snr: str = ""
    our_snr: str = ""
    freq_hz: int = 0
    start_time: float = 0.0
    timeout_cycles: int = 0
    max_timeout: int = 5
    calls_made: int = 0    # Wie oft haben wir bereits gesendet
    max_calls: int = 3     # Maximale CQ-Rufe (aus Settings)
    rr73_retries: int = 0  # Retries speziell fuer WAIT_RR73


class QSOStateMachine(QObject):
    """QSO-Ablauf mit CQ-Modus.

    Signals:
        state_changed: (QSOState)
        send_message: (str) — FT8-Nachricht zum Senden
        qso_complete: (QSOData)
        qso_timeout: (str)
    """

    state_changed = Signal(object)
    send_message = Signal(str)
    qso_complete = Signal(object)   # RR73 gesendet → ADIF loggen
    qso_confirmed = Signal(object)  # 73 empfangen → ✓ anzeigen
    qso_timeout = Signal(str)
    tx_slot_for_partner = Signal(object)  # CQ-Reply: msg mit _tx_even → Encoder soll Gegentakt setzen
    caller_queued = Signal(str)     # Station zur Warteliste hinzugefügt (call)
    queue_changed = Signal(list)    # Warteliste geändert → UI aktualisieren

    def __init__(self, my_call: str, my_grid: str):
        super().__init__()
        self.my_call = my_call
        self.my_grid = my_grid
        self.state = QSOState.IDLE
        self.qso = QSOData()
        self.cq_mode = False        # CQ-Modus aktiv
        self.cq_qso_count = 0       # Zähler: bearbeitete QSOs in CQ-Session
        self._last_snr = -10        # Letzter empfangener SNR (für Report)
        self.max_calls = 3          # Maximale Anrufversuche (aus Settings)
        self._pending_reply = None      # Gemerkter CQ-Anrufer (während TX)
        self._pending_hunt_reply = None # Gemerkter Hunt-Report (während TX)
        self._pending_rr73 = None       # Gemerktes RR73 (waehrend TX_REPORT)
        self._was_cq = False            # CQ-Modus vor Hunt-Start
        self._dbg = QSODebugLog()       # QSO Debug Logger
        self._worked_calls: dict = {}   # {callsign: timestamp} — gesperrte Calls nach QSO
        self._WORKED_BLOCK_SECS = 300   # 5 Minuten Sperre nach QSO
        self._caller_queue: list = []   # Warteliste: Stationen die während QSO gerufen haben

    def _set_state(self, new_state: QSOState):
        old = self.state.name
        self.state = new_state
        self._dbg.log("STATE", f"{old} → {new_state.name}")
        self.state_changed.emit(new_state)

    def set_last_snr(self, snr: int):
        """Aktuellen SNR-Wert vom Decoder übernehmen."""
        self._last_snr = snr

    # ── CQ-Modus ────────────────────────────────────────────────

    def start_cq(self):
        """CQ-Modus starten — ruft CQ und beantwortet automatisch."""
        if self.state not in (QSOState.IDLE, QSOState.CQ_WAIT):
            return
        self.cq_mode = True
        self.cq_qso_count = 0
        self._send_cq()

    def stop_cq(self):
        """CQ-Modus beenden."""
        self.cq_mode = False
        if self.state in (QSOState.CQ_CALLING, QSOState.CQ_WAIT):
            self._set_state(QSOState.IDLE)

    def _send_cq(self):
        """CQ-Ruf senden."""
        self._pending_reply = None  # Alte Antwort verwerfen
        msg = f"CQ {self.my_call} {self.my_grid}"
        self._dbg.log("TX", f"Sende: '{msg}'")
        self._set_state(QSOState.CQ_CALLING)
        self.send_message.emit(msg)

    def _is_worked_recently(self, callsign: str) -> bool:
        """True wenn diese Station in den letzten _WORKED_BLOCK_SECS gearbeitet wurde."""
        ts = self._worked_calls.get(callsign)
        if ts is None:
            return False
        if time.time() - ts > self._WORKED_BLOCK_SECS:
            del self._worked_calls[callsign]
            return False
        return True

    def _process_cq_reply(self):
        """Gemerkte CQ-Antwort verarbeiten (nach TX-Ende)."""
        msg = self._pending_reply
        if msg is None:
            return
        self._pending_reply = None

        # Kein CQ-Reply verarbeiten wenn CQ-Modus nicht aktiv (z.B. nach HALT)
        if not self.cq_mode:
            print(f"[QSO] {msg.caller} ignoriert — CQ-Modus nicht aktiv")
            return

        # Kein neues QSO mit kuerzlich gearbeiteter Station
        if self._is_worked_recently(msg.caller):
            print(f"[QSO] {msg.caller} ignoriert — kuerzlich gearbeitet (beendet ist beendet)")
            return

        # 73/RR73 als CQ-Antwort ignorieren (Gegenstation steckt in Schleife)
        if msg.is_73 or msg.is_rr73:
            print(f"[QSO] {msg.caller} sendet 73/RR73 als CQ-Antwort — ignoriert")
            return

        self._was_cq = True  # CQ war aktiv (cq_mode=True hier garantiert)
        self._dbg.reset(msg.caller)
        self._dbg.log("RX", f"CQ-Antwort von {msg.caller}: '{msg.raw}' "
                       f"grid={msg.is_grid} report={msg.is_report} r_report={msg.is_r_report}")

        self.qso = QSOData(
            their_call=msg.caller,
            their_grid=msg.grid_or_report if msg.is_grid else "",
            their_snr=msg.grid_or_report if msg.is_report else "",
            freq_hz=msg.freq_hz,
            start_time=time.time(),
        )

        # Slot-Korrektur: Antwort immer im GEGENTAKT der anfragenden Station senden
        # main_window setzt encoder.tx_even = not their_even
        self.tx_slot_for_partner.emit(msg)

        if msg.is_grid:
            report = f"{self._last_snr:+03d}" if self._last_snr > -30 else "-10"
            self.qso.our_snr = report
            tx_msg = f"{msg.caller} {self.my_call} {report}"
            self._dbg.log("TX", f"Sende Report: '{tx_msg}' (SNR={self._last_snr})")
            self._set_state(QSOState.TX_REPORT)
            self.send_message.emit(tx_msg)
        elif msg.is_report:
            self.qso.their_snr = msg.grid_or_report
            if msg.is_r_report:
                # R-prefix = sie haben uns schon bestätigt → RR73 senden (kein Report mehr!)
                tx_msg = f"{msg.caller} {self.my_call} RR73"
                print(f"[QSO] Antworte {msg.caller} mit RR73 (R-Report erhalten)")
                self._set_state(QSOState.TX_RR73)
                self.send_message.emit(tx_msg)
            else:
                report = f"R{self._last_snr:+03d}" if self._last_snr > -30 else "R-10"
                self.qso.our_snr = report
                tx_msg = f"{msg.caller} {self.my_call} {report}"
                print(f"[QSO] Antworte {msg.caller} mit R-Report '{tx_msg}'")
                self._set_state(QSOState.TX_REPORT)
                self.send_message.emit(tx_msg)

    # ── Hunt-Modus (Station anklicken) ──────────────────────────

    def start_qso(self, their_call: str, their_grid: str = "",
                   freq_hz: int = 0):
        """QSO mit angeklickter Station starten. Bricht laufendes QSO ab."""
        if self.state not in (QSOState.IDLE, QSOState.CQ_WAIT):
            # Laufendes QSO abbrechen → neues starten
            old = self.qso.their_call if self.qso else "?"
            print(f"[QSO] Abbruch {old} → starte neu mit {their_call}")
            self._set_state(QSOState.IDLE)

        self._was_cq = self.cq_mode  # CQ-Modus merken fuer Resume nach Timeout

        self.qso = QSOData(
            their_call=their_call,
            their_grid=their_grid,
            freq_hz=freq_hz,
            start_time=time.time(),
            calls_made=1,
            max_calls=self.max_calls,
        )

        self._dbg.reset(their_call)
        report = f"{self._last_snr:+03d}" if self._last_snr > -30 else "-10"
        self.qso.our_snr = report
        msg = f"{their_call} {self.my_call} {report}"
        self._dbg.log("START", f"Hunt: {their_call} auf {freq_hz}Hz, max {self.max_calls} Versuche")
        self._dbg.log("TX", f"Sende: '{msg}' (SNR={self._last_snr})")
        self._set_state(QSOState.TX_CALL)
        self.send_message.emit(msg)

    # ── Zyklusende (Timeout-Überwachung) ────────────────────────

    def on_cycle_end(self):
        # Gesamt-QSO Timeout (3 Min) — egal welcher State
        if (self.state not in (QSOState.IDLE, QSOState.CQ_CALLING, QSOState.CQ_WAIT,
                               QSOState.TIMEOUT, QSOState.WAIT_73)
                and self.qso.start_time > 0
                and time.time() - self.qso.start_time > MAX_QSO_DURATION):
            call = self.qso.their_call
            self._dbg.log("TIMEOUT", f"Gesamt-Timeout 3 Min fuer {call}")
            self._set_state(QSOState.TIMEOUT)
            self.qso_timeout.emit(call)
            self._resume_cq_if_needed()
            return
        if self.state == QSOState.WAIT_73:
            self.qso.timeout_cycles += 1
            if self.qso.timeout_cycles >= 3:
                print(f"[QSO] WAIT_73 Timeout — kein 73 empfangen, QSO trotzdem komplett")
                self.qso_confirmed.emit(self.qso)
                self._resume_cq_if_needed()
            return

        if self.state == QSOState.CQ_WAIT:
            # Im CQ-Modus: nach 1 RX-Zyklus ohne Antwort nochmal CQ
            # Funktioniert fuer alle Modi gleich (Even/Odd Alternation):
            # TX-Slot → RX-Slot (1 Zyklus warten) → TX-Slot
            self.qso.timeout_cycles += 1
            if self.qso.timeout_cycles >= 1 and self.cq_mode:
                self._send_cq()
            return

        if self.state in (QSOState.WAIT_REPORT, QSOState.WAIT_RR73):
            self.qso.timeout_cycles += 1
            self._dbg.log("WAIT", f"Warte auf {self.qso.their_call} "
                         f"({self.state.name}, Zyklus {self.qso.timeout_cycles}/{self.qso.max_timeout})")

            # Nach 2 Zyklen ohne Antwort: nochmal senden (wie WSJT-X, ~30s)
            if self.qso.timeout_cycles == 2:
                if self.state == QSOState.WAIT_REPORT:
                    station_limit = min(self.qso.max_calls, MAX_STATION_CALLS)
                    if self.qso.calls_made < station_limit:
                        self.qso.calls_made += 1
                        retry_msg = f"{self.qso.their_call} {self.my_call} {self.qso.our_snr or '-10'}"
                        self._dbg.log("RETRY", f"WAIT_REPORT Retry {self.qso.calls_made}/{station_limit}: '{retry_msg}'")
                        self._set_state(QSOState.TX_CALL)
                        self.send_message.emit(retry_msg)
                    else:
                        call = self.qso.their_call
                        self._dbg.log("TIMEOUT", f"Max Versuche ({station_limit}) erreicht")
                        self._set_state(QSOState.TIMEOUT)
                        self.qso_timeout.emit(call)
                        self._resume_cq_if_needed()
                    return
                elif self.state == QSOState.WAIT_RR73:
                    # Report nochmal senden — eigener Counter, max 3
                    self.qso.rr73_retries += 1
                    if self.qso.rr73_retries <= MAX_RR73_RETRIES:
                        report = self.qso.our_snr or f"R{self._last_snr:+03d}"
                        retry_msg = f"{self.qso.their_call} {self.my_call} {report}"
                        self._dbg.log("RETRY", f"WAIT_RR73 Retry {self.qso.rr73_retries}/{MAX_RR73_RETRIES}: '{retry_msg}'")
                        self.qso.timeout_cycles = 0
                        self._set_state(QSOState.TX_REPORT)
                        self.send_message.emit(retry_msg)
                    else:
                        call = self.qso.their_call
                        self._dbg.log("TIMEOUT", f"WAIT_RR73 max Retries ({self.qso.max_calls}) erreicht")
                        self._set_state(QSOState.TIMEOUT)
                        self.qso_timeout.emit(call)
                        self._resume_cq_if_needed()
                    return

            if self.qso.timeout_cycles >= self.qso.max_timeout:
                call = self.qso.their_call
                print(f"[QSO] TIMEOUT: {call} hat nicht geantwortet nach {self.qso.max_timeout} Zyklen")
                self._set_state(QSOState.TIMEOUT)
                self.qso_timeout.emit(call)
                self._resume_cq_if_needed()

    def _resume_cq_if_needed(self):
        """Nach Timeout/Hunt: CQ wieder aufnehmen wenn vorher CQ-Modus aktiv war.
        Wenn Warteliste nicht leer: direkt nächste Station antworten."""
        if self.cq_mode or self._was_cq:
            self.cq_mode = True
            self.qso.timeout_cycles = 0
            # Warteliste prüfen: direkt antworten statt CQ senden
            if self._caller_queue:
                next_msg = self._caller_queue.pop(0)
                self.queue_changed.emit([m.caller for m in self._caller_queue])
                print(f"[QSO] Warteliste: antworte {next_msg.caller} (noch {len(self._caller_queue)} wartend)")
                self._pending_reply = next_msg
                self._process_cq_reply()
            else:
                self._send_cq()
        else:
            self._set_state(QSOState.IDLE)

    # ── TX abgeschlossen ────────────────────────────────────────

    def on_message_sent(self):
        if self.state == QSOState.CQ_CALLING:
            # CQ TX fertig — Antwort wartend?
            if self._pending_reply:
                print("[QSO] CQ fertig — verarbeite gemerkte Antwort")
                self._process_cq_reply()
                return
            self._set_state(QSOState.CQ_WAIT)
            self.qso.timeout_cycles = 0
        elif self.state == QSOState.TX_CALL:
            # Hunt: Antwort während TX gemerkt?
            pending = self._pending_hunt_reply
            if pending:
                self._pending_hunt_reply = None
                self._set_state(QSOState.WAIT_REPORT)
                print(f"[QSO] TX fertig — verarbeite Hunt-Antwort: '{pending.raw}'")
                if pending.is_rr73 or pending.is_73:
                    # Vorwaerts-Sprung: RR73/73 waehrend TX_CALL → sende 73 (WSJT-X konform)
                    self._dbg.log("TX", f"Pending RR73/73 von {pending.caller} → TX_73")
                    tx_msg = f"{self.qso.their_call} {self.my_call} 73"
                    self._set_state(QSOState.TX_RR73)
                    self.send_message.emit(tx_msg)
                elif pending.is_r_report:
                    self.qso.their_snr = pending.grid_or_report
                    self._dbg.log("TX", f"Pending R-Report → TX_RR73")
                    tx_msg = f"{self.qso.their_call} {self.my_call} RR73"
                    self._set_state(QSOState.TX_RR73)
                    self.send_message.emit(tx_msg)
                else:
                    self.qso.their_snr = pending.grid_or_report
                    self.advance()
                return
            self._set_state(QSOState.WAIT_REPORT)
            self.qso.timeout_cycles = 0
        elif self.state == QSOState.TX_REPORT:
            # RR73 waehrend TX empfangen? → direkt abschliessen
            pending = self._pending_rr73
            if pending:
                self._pending_rr73 = None
                if pending.is_r_report:
                    self.qso.their_snr = pending.grid_or_report
                self._dbg.log("TX", f"TX_REPORT fertig — pending RR73 von {pending.caller} → sende RR73")
                tx_msg = f"{self.qso.their_call} {self.my_call} RR73"
                self._set_state(QSOState.TX_RR73)
                self.send_message.emit(tx_msg)
                return
            self._set_state(QSOState.WAIT_RR73)
            self.qso.timeout_cycles = 0
        elif self.state == QSOState.TX_RR73:
            # ADIF sofort loggen (RR73 oder 73 gesendet = QSO von unserer Seite bestaetigt)
            self.qso_complete.emit(self.qso)
            self.cq_qso_count += 1
            # Call sperren: kein neues QSO mit dieser Station fuer 5 Minuten
            if self.qso.their_call:
                self._worked_calls[self.qso.their_call] = time.time()
                print(f"[QSO] {self.qso.their_call} gesperrt fuer {self._WORKED_BLOCK_SECS}s")
            # Warte noch auf 73 von Gegenstation (max 2 Zyklen)
            self._set_state(QSOState.WAIT_73)
            self.qso.timeout_cycles = 0

    # ── Nachricht empfangen ─────────────────────────────────────

    def on_message_received(self, msg: FT8Message):
        # Alle Nachrichten an uns loggen (fuer Debugging)
        if msg.target == self.my_call:
            self._dbg.log("RX", f"Von {msg.caller}: '{msg.raw}' | State={self.state.name} "
                          f"| Erwartet={self.qso.their_call or '?'} "
                          f"| report={msg.is_report} r_rpt={msg.is_r_report} "
                          f"rr73={msg.is_rr73} 73={msg.is_73} grid={msg.is_grid}")
        # ── RR73/73 von vorherigem QSO nach Timeout (Station hat doch noch geantwortet) ──
        # Ignorieren, aber CQ-Flow NICHT unterbrechen (kein return!)
        if self.state in (QSOState.IDLE, QSOState.CQ_WAIT, QSOState.CQ_CALLING) and msg.target == self.my_call:
            if msg.is_rr73 or msg.is_73:
                self._dbg.log("RX", f"RR73/73 von {msg.caller} nach Timeout/CQ — ignoriert")

        # ── Warteliste: Neue CQ-Anrufer während aktivem QSO ──
        # Grid ODER Report akzeptieren (vorher nur Grid → EA3FHP-Bug)
        if (self.cq_mode
                and self.state not in (QSOState.IDLE, QSOState.CQ_WAIT, QSOState.CQ_CALLING)
                and msg.target == self.my_call
                and (msg.is_grid or msg.is_report)
                and msg.caller != self.qso.their_call
                and not self._is_worked_recently(msg.caller)
                and not any(q.caller == msg.caller for q in self._caller_queue)):
            self._caller_queue.append(msg)
            self.queue_changed.emit([m.caller for m in self._caller_queue])
            print(f"[QSO] {msg.caller} → Warteliste ({len(self._caller_queue)} wartend)")

        # ── Jemand ruft UNS (CQ-Modus, oder im IDLE) ──
        if self.state in (QSOState.IDLE, QSOState.CQ_WAIT, QSOState.CQ_CALLING) and msg.target == self.my_call:
            if msg.is_grid or msg.is_report:
                # Beendet ist beendet: kuerzlich gearbeitete Stationen ignorieren
                if self._is_worked_recently(msg.caller):
                    print(f"[QSO] {msg.caller} ignoriert — kuerzlich gearbeitet (beendet ist beendet)")
                    return
                # Antwort merken — wird in on_message_sent() verarbeitet
                # (falls CQ TX noch laeuft, darf JETZT nicht gesendet werden!)
                self._pending_reply = msg
                print(f"[QSO] Antwort von {msg.caller} gemerkt (State={self.state.name})")
                # Wenn CQ_WAIT oder IDLE: sofort verarbeiten (TX ist frei)
                if self.state in (QSOState.IDLE, QSOState.CQ_WAIT):
                    self._process_cq_reply()
                # Bei CQ_CALLING: on_message_sent() verarbeitet es nach TX-Ende
                return

        # ── CQ_WAIT Timeout: nochmal CQ rufen ──
        if self.state == QSOState.CQ_WAIT and self.cq_mode:
            # Kein Anruf für uns — on_cycle_end handhabt den Timeout
            pass

        # ── Nur Nachrichten an uns ──
        if msg.target != self.my_call:
            return

        # ── Absender muss Gegenstation sein ──
        if self.state not in (QSOState.IDLE, QSOState.CQ_WAIT, QSOState.CQ_CALLING):
            if msg.caller != self.qso.their_call:
                return

        if self.state in (QSOState.WAIT_REPORT, QSOState.TX_CALL):
            # Vorwaerts-Springen: RR73/73 direkt empfangen → ueberspringt TX_REPORT + WAIT_RR73
            if msg.is_rr73 or msg.is_73:
                if self.state == QSOState.TX_CALL:
                    # Waehrend TX merken
                    self._pending_hunt_reply = msg
                    self._dbg.log("RX", f"RR73/73 waehrend TX_CALL gemerkt von {msg.caller} → wird TX_RR73")
                    return
                # WAIT_REPORT + RR73/73 → sende 73 (WSJT-X konform, Station hat alles empfangen)
                self._dbg.log("RX", f"Vorwaerts-Sprung: RR73/73 in WAIT_REPORT → TX_73")
                tx_msg = f"{self.qso.their_call} {self.my_call} 73"
                self._set_state(QSOState.TX_RR73)
                self.send_message.emit(tx_msg)
                return

            if msg.is_report:
                self.qso.their_snr = msg.grid_or_report
                if self.state == QSOState.TX_CALL:
                    # Antwort kam während TX — merken für nach TX
                    self._pending_hunt_reply = msg
                    print(f"[QSO] Hunt-Antwort gemerkt: {msg.grid_or_report} (TX aktiv)")
                    return
                if msg.is_r_report:
                    # R-Report = Gegenstation hat uns empfangen → direkt RR73
                    print(f"[QSO] R-Report in WAIT_REPORT: {msg.grid_or_report} → sende RR73")
                    tx_msg = f"{self.qso.their_call} {self.my_call} RR73"
                    self._set_state(QSOState.TX_RR73)
                    self.send_message.emit(tx_msg)
                else:
                    self.advance()  # plain report → sende R-Report zurück
                return

            if msg.is_grid:
                # Wiederholt Grid → unser Call kam nicht an, nochmal senden
                self.qso.timeout_cycles = 0
                tx_msg = f"{self.qso.their_call} {self.my_call} {self.qso.our_snr or '-10'}"
                self.send_message.emit(tx_msg)
                return

        # RR73/73/R-Report waehrend TX_REPORT merken (Gegenstation antwortet schneller als wir fertig sind)
        if self.state == QSOState.TX_REPORT:
            if msg.is_rr73 or msg.is_73:
                self._pending_rr73 = msg
                self._dbg.log("RX", f"RR73 waehrend TX_REPORT gemerkt von {msg.caller}")
                return
            if msg.is_r_report:
                # R-Report = Bestaetigung! Auch als pending merken → nach TX senden wir RR73
                self._pending_rr73 = msg
                self._dbg.log("RX", f"R-Report waehrend TX_REPORT gemerkt: {msg.grid_or_report} → wird RR73")
                return
            if msg.is_report:
                # Plain report waehrend wir senden → ignorieren
                self._dbg.log("RX", f"Report waehrend TX_REPORT ignoriert: {msg.grid_or_report}")
                return

        if self.state == QSOState.WAIT_RR73:
            if msg.is_rr73 or msg.is_73:
                self.advance()
                return
            if msg.is_r_report:
                # R+Report (z.B. R+19, R-07) = Bestätigung + Report → wie RR73 behandeln
                self.qso.their_snr = msg.grid_or_report
                print(f"[QSO] R-Report empfangen: {msg.grid_or_report} → sende RR73")
                self.advance()
                return
            if msg.is_report:
                # Report OHNE R-Prefix → Gegenstation wiederholt, nochmal senden
                self.qso.timeout_cycles = 0
                report = self.qso.our_snr or f"R{self._last_snr:+03d}"
                tx_msg = f"{self.qso.their_call} {self.my_call} {report}"
                print(f"[QSO] Retry Report: '{tx_msg}' (Gegenstation wiederholt)")
                self._set_state(QSOState.TX_REPORT)
                self.send_message.emit(tx_msg)
                return
            if msg.is_grid:
                # Gegenstation hat unseren Report nicht empfangen → nochmal senden
                self.qso.timeout_cycles = 0
                report = self.qso.our_snr or f"{self._last_snr:+03d}"
                tx_msg = f"{self.qso.their_call} {self.my_call} {report}"
                print(f"[QSO] Grid in WAIT_RR73 (unser Report nicht angekommen) → sende erneut: '{tx_msg}'")
                self._set_state(QSOState.TX_REPORT)
                self.send_message.emit(tx_msg)
                return

        if self.state == QSOState.WAIT_73:
            if msg.is_73 or msg.is_rr73:
                print(f"[QSO] 73 von {msg.caller} empfangen — QSO bestätigt!")
                self.qso_confirmed.emit(self.qso)
                self._resume_cq_if_needed()
            elif msg.is_r_report and msg.caller == self.qso.their_call:
                # Hoeflichkeit: Station hat unser RR73 nicht empfangen → nochmal senden (max 2x)
                if self.qso.rr73_retries < 2:
                    self.qso.rr73_retries += 1
                    tx_msg = f"{self.qso.their_call} {self.my_call} RR73"
                    print(f"[QSO] Hoeflichkeit: {msg.caller} wiederholt R-Report → sende RR73 erneut "
                          f"({self.qso.rr73_retries}/2)")
                    self.send_message.emit(tx_msg)
                else:
                    print(f"[QSO] {msg.caller} wiederholt R-Report — max Retries erreicht, ignoriert")
            return

    # ── Manueller Schritt ───────────────────────────────────────

    def advance(self):
        if self.state == QSOState.WAIT_REPORT and self.qso.their_snr:
            report = f"R{self._last_snr:+03d}" if self._last_snr > -30 else "R-10"
            self.qso.our_snr = report
            msg = f"{self.qso.their_call} {self.my_call} {report}"
            self._dbg.log("TX", f"advance() R-Report: '{msg}'")
            self._set_state(QSOState.TX_REPORT)
            self.send_message.emit(msg)

        elif self.state == QSOState.WAIT_RR73:
            msg = f"{self.qso.their_call} {self.my_call} RR73"
            self._set_state(QSOState.TX_RR73)
            self.send_message.emit(msg)

    def cancel(self):
        self.cq_mode = False
        self._set_state(QSOState.IDLE)
        self.qso = QSOData()
        self._pending_reply = None
        self._pending_hunt_reply = None
        self._pending_rr73 = None
        self._caller_queue.clear()
        self.queue_changed.emit([])
