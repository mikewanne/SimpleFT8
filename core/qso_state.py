"""SimpleFT8 QSO State Machine — Zustandsmaschine für QSO-Ablauf.

Unterstützt zwei Modi:
1. HUNT: Operator klickt Station an → QSO manuell/auto durchführen
2. CQ:   Operator drückt CQ → ruft CQ, beantwortet automatisch
"""

import time
from enum import Enum, auto
from dataclasses import dataclass
from PySide6.QtCore import QObject, Signal

from .message import FT8Message


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
    LOGGING = auto()        # QSO abgeschlossen
    TIMEOUT = auto()        # Keine Antwort


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
    max_calls: int = 3     # Maximale Anrufversuche (aus Settings)


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
    qso_complete = Signal(object)
    qso_timeout = Signal(str)

    def __init__(self, my_call: str, my_grid: str):
        super().__init__()
        self.my_call = my_call
        self.my_grid = my_grid
        self.state = QSOState.IDLE
        self.qso = QSOData()
        self.auto_mode = False
        self.cq_mode = False        # CQ-Modus aktiv
        self.cq_qso_count = 0       # Zähler: bearbeitete QSOs in CQ-Session
        self._last_snr = -10        # Letzter empfangener SNR (für Report)
        self.max_calls = 3          # Maximale Anrufversuche (aus Settings)

    def _set_state(self, new_state: QSOState):
        self.state = new_state
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
        self._set_state(QSOState.CQ_CALLING)
        self.send_message.emit(msg)

    def _process_cq_reply(self):
        """Gemerkte CQ-Antwort verarbeiten (nach TX-Ende)."""
        msg = self._pending_reply
        if msg is None:
            return
        self._pending_reply = None

        self.qso = QSOData(
            their_call=msg.caller,
            their_grid=msg.grid_or_report if msg.is_grid else "",
            their_snr=msg.grid_or_report if msg.is_report else "",
            freq_hz=msg.freq_hz,
            start_time=time.time(),
        )

        if msg.is_grid:
            report = f"{self._last_snr:+03d}" if self._last_snr > -30 else "-10"
            self.qso.our_snr = report
            tx_msg = f"{msg.caller} {self.my_call} {report}"
            print(f"[QSO] Antworte {msg.caller} mit Report '{tx_msg}'")
            self._set_state(QSOState.TX_REPORT)
            self.send_message.emit(tx_msg)
        elif msg.is_report:
            self.qso.their_snr = msg.grid_or_report
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

        msg = f"{their_call} {self.my_call} {self.my_grid}"
        print(f"[QSO] START: Rufe {their_call} auf {freq_hz}Hz → sende '{msg}' (max {self.max_calls} Versuche)")
        self._set_state(QSOState.TX_CALL)
        self.send_message.emit(msg)

    # ── Zyklusende (Timeout-Überwachung) ────────────────────────

    def on_cycle_end(self):
        if self.state == QSOState.CQ_WAIT:
            # Im CQ-Modus: nach 2 Zyklen ohne Antwort nochmal CQ
            self.qso.timeout_cycles += 1
            if self.qso.timeout_cycles >= 2 and self.cq_mode:
                self._send_cq()
            return

        if self.state in (QSOState.WAIT_REPORT, QSOState.WAIT_RR73):
            self.qso.timeout_cycles += 1
            print(f"[QSO] Warte auf {self.qso.their_call} "
                  f"({self.state.name}, Zyklus {self.qso.timeout_cycles}/{self.qso.max_timeout})")

            # Nach 2 Zyklen ohne Antwort: Call nochmal senden (wie WSJT-X)
            if self.state == QSOState.WAIT_REPORT and self.qso.timeout_cycles == 2:
                if self.qso.calls_made < self.qso.max_calls:
                    self.qso.calls_made += 1
                    retry_msg = f"{self.qso.their_call} {self.my_call} {self.my_grid}"
                    print(f"[QSO] Retry {self.qso.calls_made}/{self.qso.max_calls}: '{retry_msg}'")
                    self._set_state(QSOState.TX_CALL)
                    self.send_message.emit(retry_msg)
                else:
                    call = self.qso.their_call
                    print(f"[QSO] Max Versuche ({self.qso.max_calls}) erreicht — TIMEOUT {call}")
                    self._set_state(QSOState.TIMEOUT)
                    self.qso_timeout.emit(call)
                    if self.cq_mode or getattr(self, '_was_cq', False):
                        self.cq_mode = True
                        self._send_cq()
                    else:
                        self._set_state(QSOState.IDLE)
                return

            if self.qso.timeout_cycles >= self.qso.max_timeout:
                call = self.qso.their_call
                print(f"[QSO] TIMEOUT: {call} hat nicht geantwortet nach {self.qso.max_timeout} Zyklen")
                self._set_state(QSOState.TIMEOUT)
                self.qso_timeout.emit(call)
                if self.cq_mode or getattr(self, '_was_cq', False):
                    self.cq_mode = True
                    self._send_cq()
                else:
                    self._set_state(QSOState.IDLE)

    # ── TX abgeschlossen ────────────────────────────────────────

    def on_message_sent(self):
        if self.state == QSOState.CQ_CALLING:
            # CQ TX fertig — Antwort wartend?
            if getattr(self, '_pending_reply', None):
                print("[QSO] CQ fertig — verarbeite gemerkte Antwort")
                self._process_cq_reply()
                return
            self._set_state(QSOState.CQ_WAIT)
            self.qso.timeout_cycles = 0
        elif self.state == QSOState.TX_CALL:
            self._set_state(QSOState.WAIT_REPORT)
            self.qso.timeout_cycles = 0
        elif self.state == QSOState.TX_REPORT:
            self._set_state(QSOState.WAIT_RR73)
            self.qso.timeout_cycles = 0
        elif self.state == QSOState.TX_RR73:
            self._set_state(QSOState.LOGGING)
            self.qso_complete.emit(self.qso)
            self.cq_qso_count += 1
            # Im CQ-Modus: sofort nächstes CQ
            if self.cq_mode:
                self._send_cq()
            else:
                self._set_state(QSOState.IDLE)

    # ── Nachricht empfangen ─────────────────────────────────────

    def on_message_received(self, msg: FT8Message):
        # Alle Nachrichten an uns loggen (fuer Debugging)
        if msg.target == self.my_call:
            print(f"[QSO] Empfangen: '{msg.raw}' | State={self.state.name} "
                  f"| Erwartet von={self.qso.their_call or '?'} "
                  f"| is_report={msg.is_report} is_rr73={msg.is_rr73} is_grid={msg.is_grid}")
        # ── Jemand ruft UNS (CQ-Modus, oder im IDLE) ──
        if self.state in (QSOState.IDLE, QSOState.CQ_WAIT, QSOState.CQ_CALLING) and msg.target == self.my_call:
            if msg.is_grid or msg.is_report:
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

        if self.state == QSOState.WAIT_REPORT:
            if msg.is_report:
                self.qso.their_snr = msg.grid_or_report
                if self.auto_mode or self.cq_mode:
                    self.advance()
                return

            if msg.is_grid:
                # Wiederholt Grid → unser Call kam nicht an, nochmal senden
                self.qso.timeout_cycles = 0
                tx_msg = f"{self.qso.their_call} {self.my_call} {self.my_grid}"
                self.send_message.emit(tx_msg)
                return

        if self.state == QSOState.WAIT_RR73:
            if msg.is_rr73 or msg.is_73:
                if self.auto_mode or self.cq_mode:
                    self.advance()
                return
            if msg.is_report:
                # Gegenstation wiederholt Report → hat unseren nicht gehoert, nochmal senden
                self.qso.timeout_cycles = 0
                report = self.qso.our_snr or f"R{self._last_snr:+d}"
                tx_msg = f"{self.qso.their_call} {self.my_call} {report}"
                print(f"[QSO] Retry Report: '{tx_msg}' (Gegenstation wiederholt)")
                self._set_state(QSOState.TX_REPORT)
                self.send_message.emit(tx_msg)
                return

    # ── Manueller Schritt ───────────────────────────────────────

    def advance(self):
        if self.state == QSOState.WAIT_REPORT and self.qso.their_snr:
            report = f"{self._last_snr:+03d}" if self._last_snr > -30 else "-10"
            self.qso.our_snr = report
            msg = f"{self.qso.their_call} {self.my_call} {report}"
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
