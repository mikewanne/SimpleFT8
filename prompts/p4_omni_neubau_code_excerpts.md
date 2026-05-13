# Code-Auszuege fuer R1 — nur OMNI-relevante Methoden

## core/timing.py (komplett, klein)
```python
"""SimpleFT8 Timing — UTC-Takt und Fenster-Synchronisation."""

import time
import threading
from PySide6.QtCore import QObject, Signal
from core import ntp_time


class FT8Timer(QObject):
    """Verwaltet FT8/FT4 Timing-Zyklen.

    Signals:
        cycle_tick: Emitted jede 100ms mit (seconds_in_cycle, cycle_duration)
        cycle_start: Emitted am Anfang eines neuen Zyklus mit (cycle_number, is_even)
        tx_window: Emitted wenn TX-Fenster beginnt
    """

    cycle_tick = Signal(float, float)   # (seconds_in_cycle, cycle_duration)
    cycle_start = Signal(int, bool)     # (cycle_number, is_even)
    tx_window = Signal()

    # Zyklusdauer pro Modus (aus Protocol Profiles)
    CYCLE_DURATIONS = {
        "FT8": 15.0,
        "FT4": 7.5,
        "FT2": 3.8,   # Decodium: 2.47s Signal + 1.33s Pause
    }

    def __init__(self, mode: str = "FT8"):
        super().__init__()
        self.mode = mode
        self.cycle_duration = self.CYCLE_DURATIONS[mode]
        self._running = False
        self._thread = None
        self._cycle_count = 0

    def set_mode(self, mode: str):
        self.mode = mode
        self.cycle_duration = self.CYCLE_DURATIONS[mode]

    def utc_now(self) -> float:
        """Aktuelle UTC-Zeit mit DT-Korrektur."""
        return ntp_time.get_time()

    def seconds_in_cycle(self) -> float:
        """Sekunden seit Beginn des aktuellen Zyklus."""
        return self.utc_now() % self.cycle_duration

    def seconds_until_next_cycle(self) -> float:
        """Sekunden bis zum nächsten Zyklus-Start."""
        return self.cycle_duration - self.seconds_in_cycle()

    def current_cycle_number(self) -> int:
        """Aktueller Zyklus seit Epoch."""
        return int(self.utc_now() / self.cycle_duration)

    def is_even_cycle(self) -> bool:
        """True wenn der AKTUELL laufende Zyklus gerade Parität hat.

        NICHT der nächste Zyklus. Aufrufer die wissen wollen ob der
        nächste Slot Even ist (z.B. OMNI-Block-Wahl, CQ-Slot-Setter)
        invertieren: ``next_is_even = not timer.is_even_cycle()``.
        """
        return self.current_cycle_number() % 2 == 0

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._tick_loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False

    def _tick_loop(self):
        last_cycle = -1
        while self._running:
            now = self.utc_now()
            sic = now % self.cycle_duration
            cycle_num = int(now / self.cycle_duration)

            if cycle_num != last_cycle:
                last_cycle = cycle_num
                self._cycle_count += 1
                is_even = cycle_num % 2 == 0
                self.cycle_start.emit(self._cycle_count, is_even)

            self.cycle_tick.emit(sic, self.cycle_duration)
            time.sleep(0.1)
```

## core/encoder.py — TX-Worker + transmit + Slot-Boundary (Vorbild fuer OMNI-Worker)
```python
"""SimpleFT8 Encoder — FT8-Nachrichten in Audio umwandeln und senden.

TX-Audio wird ueber VITA-49 UDP direkt an das FlexRadio gesendet.
Kein SmartSDR, kein DAX-Treiber, kein virtuelles Audio-Device noetig.
"""

import time
import threading
import numpy as np
from PySide6.QtCore import QObject, Signal

from .ft8lib_decoder import get_ft8lib


SAMPLE_RATE_FT8 = 12000

# TX-Timing: Fester WSJT-X Protokoll-Offset (0.5s = TX startet bei t=0.5s im Slot).
# Die DT-Korrektur (ntp_time) gilt NUR fuer RX (Audio-Buffer-Shift im Decoder).
# TX hat keine Decoder-Buffer-Verzoegerung — die 0.77s RX-Korrektur darf hier
# nicht abgezogen werden, sonst sendet TX 0.67s zu frueh.
# TX-Timing: WSJT-X Protokoll-Offset (0.5s) minus FlexRadio TX-VITA-49-Buffer-Latenz (1.3s).
# FlexRadio puffert eingehende TX-Samples 1.3s bevor sie als RF rausgehen (konstant gemessen).
# -0.8 = 0.5 (Protokoll) - 1.3 (Hardware-Buffer)
# → Audio startet bei boundary-0.8s → RF bei boundary+0.5s → DT≈0
TARGET_TX_OFFSET = -0.8
# Trailing Silence trimmen: FT8-Nutzsignal ist 12.64s, Rest ist Stille.
# slot+0.5 + 13.5s = slot+14.0s → 1.0s Puffer vor naechstem Slot (sicher)
TRIM_SAMPLES = int(1.5 * SAMPLE_RATE_FT8)   # 18000 Samples @ 12kHz


class Encoder(QObject):
    """Erzeugt FT8-Audio und sendet es zum richtigen Zeitpunkt.

    TX-Pfad: FT8 encode → VITA-49 float32 stereo 48kHz → FlexRadio UDP

    Signals:
        tx_started: (str, bool, float) — TX begonnen mit
            (message, tx_even, slot_start_ts). slot_start_ts ist der
            Slot-Start in UTC-Sekunden. Ermoeglicht qso_panel.add_tx
            korrekte Slot-Anzeige unabhaengig von Signal-Latenz.
        tx_finished: () — TX abgeschlossen
        encoding_error: (str) — Fehler
    """

    tx_started = Signal(str, bool, float)
    tx_finished = Signal()
    encoding_error = Signal(str)

    def __init__(self, audio_freq_hz: int = 1000):
        super().__init__()
    def set_protocol(self, mode: str):
        """Protokoll wechseln."""
        self._mode = mode
        print(f"[Encoder] Protokoll: {mode}")

    @property
    def is_transmitting(self) -> bool:
        return self._is_transmitting

    def abort(self):
        """TX sofort abbrechen (Bandwechsel, Notaus, State-Change).

        v0.80 Fix A2: setzt zusaetzlich _abort_event, damit der TX-Worker
        aus seinem Slot-Wait-Sleep aufwacht. Ohne Event bleibt der Worker
        bis zu 14s im time.sleep haengen und sendet veraltete Messages.

        P2.OMNI-PATTERN-FIX (v0.95.24): leert die Queue. Abort ist
        Notaus-Semantik — wartende TX-Slots werden verworfen.
        """
        self._is_transmitting = False
        self._abort_event.set()
        with self._replace_lock:
            self._pending_tx_message = None
        print("[Encoder] TX abgebrochen")

    def request_replace(self, message: str) -> bool:
        """P1.9 Fix (v0.95.3): laufenden TX mit neuer Message ersetzen
        waehrend Sleep-Phase (vor send_audio).

        Returns True wenn Replace eingereiht wurde, False wenn zu spaet
        (Audio bereits gestartet) oder kein TX laeuft.

        Race-Sicherheit: Lock + is_transmitting-Guard + atomare
        _audio_started-Pruefung verhindern Replace nach send_audio-Start.

        Aufrufer (mw_qso._on_try_replace_pending_tx) muss tx_even VOR
        diesem Aufruf setzen, damit der aufgeweckte Worker
        _next_slot_boundary() mit korrektem Wert aufruft.
        """
        with self._replace_lock:
            if not self._is_transmitting:
                return False
            if self._audio_started:
                return False
            self._replace_message = message
            self._abort_event.set()
            return True

    def set_radio(self, radio):
        self._radio = radio

    def transmit(self, message: str):
        """FT8-Nachricht encoden und zum naechsten Zyklusbeginn senden.

        P2.OMNI-PATTERN-FIX (v0.95.24): Bei bereits laufendem TX wird die
        Message in die Queue gelegt statt verworfen. Worker-Loop sendet sie
        nach Abschluss des aktuellen TX. Replace + Abort verdraengen die
        Queue (siehe abort() / Replace-Pfad in _tx_worker_inner).
        """
        # v0.80 Race-Fix (R1-Final-Review): alten TX-Thread sauber beenden,
        # bevor neuer startet. Sonst kann das finally des alten Threads
        # _is_transmitting=False setzen NACHDEM der neue Thread True gesetzt
        # hat → State desynchronisiert, weitere abort()-Aufrufe wirkungslos.
        # Race-Window: zwischen abort() und neuem transmit() laeuft das
        # finally des alten Workers asynchron.
        if (self._tx_thread is not None
                and self._tx_thread.is_alive()
                and threading.current_thread() is not self._tx_thread):
            self._tx_thread.join(timeout=0.5)
        if self._is_transmitting:
            with self._replace_lock:
                self._pending_tx_message = message
            print(f"[TX] Queued (TX aktiv): '{message}'")
            return
        self._tx_thread = threading.Thread(
            target=self._tx_worker, args=(message,), daemon=True
        )
        self._tx_thread.start()

    def _tx_worker(self, message: str):
        """TX-Worker: Timing → PTT → Audio via VITA-49 → PTT off.

        P2.OMNI-PATTERN-FIX (v0.95.24): rekursiver Outer-Loop fuer Queue.
        Nach Abschluss eines TX wird _pending_tx_message geprueft. Falls
        gesetzt, laeuft naechster TX im selben Worker (kein Thread-
        Restart). _is_transmitting bleibt waehrend des gesamten Loops
        True, damit weitere transmit()-Aufrufe weiter queuen koennen.
        """
        self._is_transmitting = True
        # v0.80 Fix A2: Event vor jedem TX zuruecksetzen
        self._abort_event.clear()
        # P1.9 Fix (v0.95.3): Replace-State pro TX-Zyklus zuruecksetzen.
        self._audio_started = False
        with self._replace_lock:
            self._replace_message = None
            # Queue NICHT hier loeschen — kann zwischen transmit-Aufruf
            # und Worker-Start gesetzt worden sein.
        try:
            while True:
                self._tx_worker_inner(message)
                # tx_worker_inner emittet tx_finished am Ende.
                # Pruefe Queue fuer naechsten TX-Durchlauf.
                with self._replace_lock:
                    next_msg = self._pending_tx_message
                    self._pending_tx_message = None
                    # Reset fuer naechsten Inner-Run
                    self._audio_started = False
                    self._abort_event.clear()
                if next_msg is None:
                    break
                message = next_msg
                print(f"[TX] Queued-TX naechster Slot: '{message}'")
        finally:
            self._is_transmitting = False
            self._audio_started = False

    def _next_slot_boundary(self) -> float:
        """Naechste passende Slot-Grenze als Unix-Timestamp.

        Gibt den Slot-Start zurueck auf den wir TX-Parity haben.
        Liefert stets einen Zeitpunkt in der Zukunft (oder sehr nah dran).
        """
        _SLOT = {"FT8": 15.0, "FT4": 7.5, "FT2": 3.8}.get(self._mode, 15.0)
        now = time.time()
        cycle_num = int(now / _SLOT)
        cycle_pos = now % _SLOT
        is_even = (cycle_num % 2 == 0)

        if self.tx_even is not None:
            want_even = self.tx_even
            # v0.80 Fix C: Schwelle 0.5s statt _SLOT/5 (= 3.0s bei FT8).
            # Nur wenn TX-Trigger EXAKT am Slot-Start feuert (< 0.5s nach
            # boundary), darf der aktuelle Slot gewaehlt werden. Frueher
            # konnte ein Mid-Slot-Trigger faelschlich den aktuellen Slot
            # nehmen → Drift (R1-Review der V2).
            if is_even == want_even and cycle_pos < 0.5:
                return float(cycle_num * _SLOT)
            next_num = cycle_num + 1
            next_boundary = float(next_num * _SLOT)
            if (next_num % 2 == 0) != want_even:
                next_boundary += _SLOT
            return next_boundary
        else:
            return float((cycle_num + 1) * _SLOT)

    def _tx_worker_inner(self, message: str):
        # FESTE TX-Frequenz
        print(f"[TX] Frequenz: {self.audio_freq_hz} Hz → '{message}'")

        # P1.9 Fix (v0.95.3): Loop ermoeglicht Re-Encode bei Replace-Request
        # waehrend Sleep. Decoder wakes 1s frueher (decoder.py:138 _WAKE_OFFSETS
        # FT8 = 2.5), Slot-Handler in mw_qso ruft request_replace() auf,
        # Worker wacht aus Sleep auf, sieht _replace_message != None,
        # re-encodiert mit Report-Message → Report im SELBEN Slot wo CQ
        # scheduled war.
        while True:
            # 1. Audio codieren (re-codiert nach Replace mit neuer Message)
            audio_12k = self.encode_message(message)
            if audio_12k is None:
                # V2 FINDING-F: tx_finished MUSS feuern damit qso_state
                # nicht in TX_REPORT haengt. Invariant: jeder TX-Versuch
                # endet mit tx_finished.
                self.tx_finished.emit()
                return
            # Trailing Silence trimmen (FT8-Nutzsignal ist 12.64s, Rest stille)
            if len(audio_12k) > TRIM_SAMPLES:
                audio_12k = audio_12k[:-TRIM_SAMPLES]

            # 2. Naechste passende Slot-Grenze berechnen
            next_boundary = self._next_slot_boundary()

            # 3. Sleep bis Slot-Grenze. _abort_event weckt auf bei abort()
            #    ODER bei request_replace() (P1.9).
            sleep_dur = (next_boundary + TARGET_TX_OFFSET - 0.5) - time.time()
            if sleep_dur > 0.001:
                aborted = self._abort_event.wait(timeout=sleep_dur)
                if aborted:
                    # P1.9: Replace eingereiht? → re-encode + neuer Loop-Durchgang
                    with self._replace_lock:
                        if self._replace_message is not None:
                            message = self._replace_message
                            self._replace_message = None
                            # P2.OMNI-PATTERN-FIX: Replace verdraengt Queue.
                            # Wenn die State-Machine den aktuellen TX
                            # ersetzt, ist auch der gequeute "naechste" TX
                            # obsolet (Plan-Wechsel).
                            self._pending_tx_message = None
                            self._abort_event.clear()
                            print(f"[Encoder] TX-Replace → '{message}'")
                            continue
                    print("[Encoder] TX abgebrochen (während Warte-Phase)")
                    return

            # Abort-Check ohne Sleep (sleep_dur <= 0.001)
            if not self._is_transmitting:
                print("[Encoder] TX abgebrochen (vor Sleep)")
                return

            # 4. Audio-Start vorbereiten — point of no return.
            # _audio_started=True UNTER Lock setzen, damit ein gleichzeitig
            # laufendes request_replace() entweder noch erfolgreich ist
            # oder sauber False zurueckgibt. Kein Mid-State.
            with self._replace_lock:
                self._audio_started = True
            break  # raus aus dem while-Loop, weiter mit Audio-Send

        # 4. Silence-Padding berechnen (jetzt praezise, da nahe am Ziel)
        #    Stille absorbiert den restlichen Jitter des OS-Schedulers
        now = time.time()
        # TX-Timing: NUR der feste WSJT-X Protokoll-Offset (TARGET_TX_OFFSET=0.5s).
        # KEINE ntp_time Korrektur hier — die gilt nur fuer RX Audio-Buffer-Shift.
        silence_secs = max(0.0, (next_boundary + TARGET_TX_OFFSET) - now)

        # v0.80 Fix B: Drift-Guard. Schwelle 0.3s = WSJT-X-Decode-Schwelle 0.5s
        # minus 0.1s Audio-Encoding-Latency minus 0.1s Sicherheits-Marge.
        # Bei overshoot > 0.3s: lieber zum naechsten passenden Slot weiterschalten
        # als veralteten DT zu senden (vorher 5.0s-Schwelle erlaubte DT bis 0.95s).
        if silence_secs < 0.1:
            overshoot = now - (next_boundary + TARGET_TX_OFFSET)
            if overshoot > 0.3:
                # Drift-Risiko zu hoch → naechsten passenden Slot nehmen.
                # tx_even gesetzt → 2 Slots (gleiche Paritaet) sonst 1 Slot.
                _SLOT = {"FT8": 15.0, "FT4": 7.5, "FT2": 3.8}.get(self._mode, 15.0)
                next_boundary += (2 * _SLOT) if self.tx_even is not None else _SLOT
                silence_secs = max(0.0, (next_boundary + TARGET_TX_OFFSET) - time.time())
                print(f"[TX] Drift-Vermeidung: overshoot={overshoot:.2f}s "
                      f"→ Slot {next_boundary:.1f}")
            else:
                # Knapp am Ziel (overshoot < 0.3s, RF-DT < 0.5s) → sofort senden
                silence_secs = 0.0
                print(f"[TX] Slot-Rand: sofort senden (overshoot={overshoot:.2f}s)")

        silence_samples = int(silence_secs * SAMPLE_RATE_FT8)

        # 5. [Stille] + [FT8-Signal] als einen Block zusammenbauen
        audio_full = np.concatenate([
            np.zeros(silence_samples, dtype=np.int16),
            audio_12k,
        ])

        # Timing-Log
        tx_time = time.time()
        tx_slot = "EVEN" if int(tx_time / 15.0) % 2 == 0 else "ODD"
        utc = time.strftime("%H:%M:%S", time.gmtime(tx_time))
        print(f"[TX] {utc} Slot={tx_slot} Freq={self.audio_freq_hz}Hz → '{message}' "
              f"| Stille={silence_secs:.3f}s | Signal={len(audio_12k)/SAMPLE_RATE_FT8:.2f}s")

        # 6. PTT an — Stille gibt 0.3-0.5s PTT-Settle-Zeit
        if self._radio:
            self._radio.set_tx_antenna("ANT1")
            self._radio.ptt_on()

        # Slot-Quelle fuer qso_panel.add_tx: NICHT time.time() benutzen!
        # ptt_on() laeuft 1.3s VOR next_boundary (Stille-Padding davor).
        # floor(time.time()/slot)*slot wuerde damit auf den VORHERIGEN
        # Slot zeigen (Bug aus v0.95). Korrekt ist next_boundary — das ist
        # der echte Ziel-TX-Slot-Anfang in dem das FT8-Signal hochgeht.
        _slot_dur = {"FT8": 15.0, "FT4": 7.5, "FT2": 3.8}.get(self._mode, 15.0)
        _tx_even = int(next_boundary / _slot_dur) % 2 == 0
        self.tx_started.emit(message, _tx_even, next_boundary)

        # 7. Stream: FlexRadio Hardware-Clock uebernimmt das Pacing
        #    t_start = jetzt → jedes Paket bei t_start + n*5.33ms (absolut, kein Drift)
        if self._radio:
            self._radio.send_audio(audio_full, sample_rate=SAMPLE_RATE_FT8)

        # 8. PTT aus
        if self._radio:
            self._radio.ptt_off()

        self.tx_finished.emit()
```

## core/qso_state.py — start_cq, stop_cq, _send_cq, _process_cq_reply, start_qso, on_message_received, _resume_cq_if_needed, on_message_sent, on_decoder_finished, on_cycle_end
```python
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
    TX_73_COURTESY = auto() # P1.10 Fix (v0.95.4): Hoeflichkeits-73 nach 73-Empfang
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
    wait_73_retries: int = 0  # P1.11 (v0.95.19): Retries fuer WAIT_73-Hoeflichkeit (R-Report-Wiederholung), entkoppelt von rr73_retries
    courtesy_73_sent: bool = False  # P1.10 Fix (v0.95.4): max 1x pro QSO


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
    # P1.9 Fix (v0.95.3): CQ-Reply waehrend CQ_CALLING → mw_qso versucht
    # Encoder-Replace im Sleep-Phase damit Report im SELBEN Slot rausgeht.
    try_replace_pending_tx = Signal(object)

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
        self._caller_queue: list = []   # Warteliste: Stationen die während QSO gerufen haben
        # P2.OMNI-REDESIGN v4.0 (v0.95.23): Flag-Pattern fuer OMNI-RX-Slot.
        # Listener (mw_qso._on_send_message) setzt True wenn TX wegen
        # OMNI-RX-Slot geskippt wird → _send_cq macht KEINEN State-Wechsel
        # zu CQ_CALLING. Vermeidet stuck-State der den CQ-Loop killt
        # (Bug v0.78-v0.95.22: State CQ_CALLING blockierte on_cycle_end-Re-CQ).
        self._omni_skip_state_change: bool = False
        # P2.OMNI-PATTERN-FIX (v0.95.24): Pretrigger-Flag.
        # Wird von mw_cycle._omni_pretrigger_check gesetzt VOR _send_cq.
        # on_cycle_end (am Slot-Start) prueft + reset es: bei True KEIN
        # zweites _send_cq (sonst Doppel-TX im selben Slot).
        # Lebenszyklus: gesetzt von mw_cycle (GUI-Thread), reset von
        # qso_state (GUI-Thread) — kein Lock noetig.
        self._was_pretriggered: bool = False

    def _set_state(self, new_state: QSOState):
        old = self.state.name
        self.state = new_state
        # v0.80 Fix A3: Defense-in-Depth gegen Counter-Race.
        # Bei Eintritt in einen Wartezustand muss timeout_cycles auf 0
        # stehen — sonst feuert ein nachfolgender on_cycle_end() sofort
        # einen Retry, obwohl noch kein Zyklus abgewartet wurde.
        # Bestehende explizite Resets in on_message_sent bleiben (no-op
        # bei Doppel-Reset), aber R1-Review hat darauf hingewiesen dass
        # _set_state das selbst nicht garantierte. KISS: zentral hier.
        if new_state in (QSOState.WAIT_REPORT, QSOState.WAIT_RR73,
                         QSOState.WAIT_73, QSOState.CQ_WAIT):
            if self.qso is not None:
                self.qso.timeout_cycles = 0
        self._dbg.log("STATE", f"{old} → {new_state.name}")
        self.state_changed.emit(new_state)

    def set_last_snr(self, snr: int):
        """Aktuellen SNR-Wert vom Decoder übernehmen."""
        self._last_snr = snr

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
        """CQ-Ruf senden.

        P2.OMNI-REDESIGN v4.0 (v0.95.23) Flag-Pattern: State-Wechsel zu
        CQ_CALLING kommt NACH emit(). Listener (mw_qso._on_send_message)
        kann via _omni_skip_state_change=True signalisieren dass TX wegen
        OMNI-RX-Slot geskippt wurde — dann bleibt der State auf vor-Wert
        (CQ_WAIT/IDLE), on_cycle_end() triggert weiterhin den Re-CQ.
        """
        # P1.9 Defense-in-Depth (v0.95.3): falls _pending_reply bereits
        # gesetzt ist (Race: Replace-Request kam zu spaet aber Reply ist
        # gemerkt), direkt Reply verarbeiten statt nochmal CQ zu senden.
        if self._pending_reply is not None:
            print(f"[QSO] _send_cq: pending {self._pending_reply.caller} "
                  f"→ process statt CQ")
            self._process_cq_reply()
            return
        msg = f"CQ {self.my_call} {self.my_grid}"
        self._dbg.log("TX", f"Sende: '{msg}'")
        # _omni_skip_state_change: Flag wird nur im GUI-Thread (qso_sm) gesetzt
        # und gelesen. Listener läuft via DirectConnection synchron im selben
        # Thread → kein Lock nötig.
        self._omni_skip_state_change = False
        self.send_message.emit(msg)
        if not self._omni_skip_state_change:
            self._set_state(QSOState.CQ_CALLING)

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
            # P1.BUNDLE Bug-C / P1.8 (v0.95.18): msg.snr ist der SNR der
            # spezifischen anrufenden Station. _last_snr wuerde vom letzten
            # on_message_decoded-Aufruf im Slot ueberschrieben (kann andere
            # Station sein) → falscher Report.
            snr = msg.snr
            report = f"{snr:+03d}" if snr > -30 else "-10"
            self.qso.our_snr = report
            tx_msg = f"{msg.caller} {self.my_call} {report}"
            self._dbg.log("TX", f"Sende Report: '{tx_msg}' (SNR={snr})")
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
                # P1.BUNDLE Bug-C / P1.8 (v0.95.18): siehe oben — msg.snr.
                snr = msg.snr
                report = f"R{snr:+03d}" if snr > -30 else "R-10"
                self.qso.our_snr = report
                tx_msg = f"{msg.caller} {self.my_call} {report}"
                print(f"[QSO] Antworte {msg.caller} mit R-Report '{tx_msg}'")
                self._set_state(QSOState.TX_REPORT)
                self.send_message.emit(tx_msg)

    # ── Hunt-Modus (Station anklicken) ──────────────────────────

    def start_qso(self, their_call: str, their_grid: str = "",
                   freq_hz: int = 0, their_snr: int | None = None):
        """QSO mit angeklickter Station starten. Bricht laufendes QSO ab.

        P1.HUNT-SNR (v0.95.21): their_snr ist station-spezifischer SNR
        aus FT8Message — verhindert dass _last_snr (vom letzten Decoder-
        Iterator-Schritt im Slot) den Report dominiert. Backward-compat:
        None → fallback auf _last_snr (alte Tests).
        """
        # P1.14 KP1: Reset bei JEDEM Nicht-IDLE-State (auch CQ_WAIT, da
        # dort _pending_reply gesetzt sein kann)
        if self.state != QSOState.IDLE:
            # Laufendes QSO abbrechen → neues starten
            old = self.qso.their_call if self.qso else "?"
            print(f"[QSO] Abbruch {old} → starte neu mit {their_call}")
            # P1.14 KP1: Pendings explizit resetten (sonst Geister-Eintraege
            # mit alter their_call im naechsten Slot)
            self._pending_reply = None
            self._pending_hunt_reply = None
            self._pending_rr73 = None
            # _caller_queue BEHALTEN (Option B — Mike will durchgaengig
            # CQ-Antworter abarbeiten nach manuellem Hunt)
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
        # P1.HUNT-SNR (v0.95.21): explizite their_snr > _last_snr-Fallback.
        # Verhindert dass im selben Slot decodierte andere Stationen
        # _last_snr ueberschreiben und falsche Reports erzeugen.
        snr = their_snr if their_snr is not None else self._last_snr
        report = f"{snr:+03d}" if snr > -30 else "-10"
        self.qso.our_snr = report
        msg = f"{their_call} {self.my_call} {report}"
        self._dbg.log("START", f"Hunt: {their_call} auf {freq_hz}Hz, max {self.max_calls} Versuche")
        self._dbg.log("TX", f"Sende: '{msg}' (SNR={snr})")
        self._set_state(QSOState.TX_CALL)
        self.send_message.emit(msg)

    # ── Zyklusende (Timeout-Überwachung) ────────────────────────

    def on_cycle_end(self):
        # Gesamt-QSO Timeout (3 Min) — egal welcher State
        if (self.state not in (QSOState.IDLE, QSOState.CQ_CALLING, QSOState.CQ_WAIT,
                               QSOState.TIMEOUT, QSOState.WAIT_73,
                               QSOState.TX_73_COURTESY)  # P1.10: Courtesy-73 zu Ende fuehren
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
                # P2.OMNI-PATTERN-FIX (v0.95.24): Pretrigger lief mid-cycle
                # bereits → Slot ist schon „verbraucht". Flag reset, kein
                # zweites _send_cq (sonst Doppel-TX im selben Slot).
                if self._was_pretriggered:
                    self._was_pretriggered = False
                else:
                    self._send_cq()
            return

        if self.state in (QSOState.WAIT_REPORT, QSOState.WAIT_RR73):
            self.qso.timeout_cycles += 1
            self._dbg.log("WAIT", f"Warte auf {self.qso.their_call} "
                         f"({self.state.name}, Zyklus {self.qso.timeout_cycles}/{self.qso.max_timeout})")

            # v0.81 Fix D: Retry-Trigger ist nicht mehr hier. Er feuert in
            # on_decoder_finished() am Slot-ENDE — also NACH der Decoder-
            # Verarbeitung — damit eine eingehende Antwort der Gegenstation
            # (R+18, RR73) den State vorher wechseln kann und der Doppel-
            # Report-Bug nicht mehr auftritt.

            if self.qso.timeout_cycles >= self.qso.max_timeout:
                call = self.qso.their_call
                print(f"[QSO] TIMEOUT: {call} hat nicht geantwortet nach {self.qso.max_timeout} Zyklen")
                self._set_state(QSOState.TIMEOUT)
                self.qso_timeout.emit(call)
                self._resume_cq_if_needed()

    def on_decoder_finished(self):
        """v0.81 Fix D — Retry-Trigger NACH Decoder-Verarbeitung.

        Wird im Slot-Ende-Pfad (`mw_cycle._on_cycle_decoded`) NACH den
        Message-Handlern aufgerufen. Triggert Retry fuer WAIT_REPORT/
        WAIT_RR73 nur wenn die Gegenstation in diesem RX-Slot NICHT
        geantwortet hat. Wenn sie geantwortet hat, hat
        on_message_received bereits den State gewechselt → kein Retry.

        Vor Fix D lief der Retry in on_cycle_end() am Slot-START — also
        BEVOR der Decoder die Antwort sehen konnte → Doppel-Report-Bug.
        """
        if self.qso is None:
            return

        if self.state == QSOState.WAIT_REPORT and self.qso.timeout_cycles == 1:
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

        if self.state == QSOState.WAIT_RR73 and self.qso.timeout_cycles == 1:
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

    def _resume_cq_if_needed(self):
        """Nach Timeout/Hunt: CQ wieder aufnehmen wenn vorher CQ-Modus aktiv war.
        Wenn Warteliste nicht leer: direkt nächste Station antworten.

        WICHTIG (P2.OMNI-REDESIGN v4.0 S1-Doku): Aufrufer-Pattern ist
        immer 'qso_*.emit() → _resume_cq_if_needed()'. main_window.py:597-599
        verbindet die qso_complete/qso_confirmed/qso_timeout-Slots ohne
        explizite ConnectionType → Qt.AutoConnection → bei gleichem
        GUI-Thread → Qt.DirectConnection → emit() läuft synchron.
        mw_qso-Listener (inkl. OMNI-Resume via _maybe_resume_omni) läuft
        komplett bevor diese Methode _send_cq() aufruft → der CQ wird
        dann durch den OMNI-Slot-Filter korrekt gefiltert. Kein
        ungefilterter CQ. Bei künftigem Multi-Thread-Refactor explizit
        prüfen (siehe V3 R1-V2 Halluzination-Discussion S1).
        """
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
            # Warte noch auf 73 von Gegenstation (max 2 Zyklen)
            self._set_state(QSOState.WAIT_73)
            self.qso.timeout_cycles = 0
        elif self.state == QSOState.TX_73_COURTESY:
            # P1.10 Fix (v0.95.4): Courtesy-73 fertig gesendet.
            # qso_complete wurde bereits in TX_RR73 (oben) gefeuert — hier nur
            # qso_confirmed (UI „QSO ✓") + CQ resumen.
            self._dbg.log("TX", "Courtesy-73 fertig → qso_confirmed + resume_cq")
            self.qso_confirmed.emit(self.qso)
            self._resume_cq_if_needed()

    # ── Nachricht empfangen ─────────────────────────────────────

    def on_message_received(self, msg: FT8Message):
        # Alle Nachrichten an uns loggen (fuer Debugging)
    def advance(self):
        if self.state == QSOState.WAIT_REPORT and self.qso.their_snr:
            # P1.HUNT-SNR (v0.95.21): qso.our_snr wurde in start_qso bereits
            # mit station-spezifischem SNR gesetzt. R-Praefix wird hier hinzu-
            # gefuegt. Fallback _last_snr nur wenn our_snr leer (Edge-Case).
            if self.qso.our_snr:
                base = self.qso.our_snr.lstrip("R")  # ist heute ohne R
                report = f"R{base}"
            else:
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

        elif self.state == QSOState.WAIT_73:
            # P1.FORCESEND (v0.95.12): manuelles 73 wenn Gegenstation
            # kein 73 schickt. WAIT_73 = "QSO schon geloggt" (qso_complete
            # wurde in TX_RR73 emittiert), wir senden Hoeflichkeits-73.
            # Final-R1 Race-Schutz: Auto-Pfad (on_message_received) koennte
            # courtesy_73_sent bereits gesetzt haben — idempotent return.
            if self.qso.courtesy_73_sent:
                self._dbg.log("TX", "advance() Force-73: 73 schon gesendet, ignoriert")
                return
            # Flag VOR send (R1 KP-3, asynchron-Schutz).
            self.qso.courtesy_73_sent = True
            msg = f"{self.qso.their_call} {self.my_call} 73"
            self._dbg.log("TX", f"advance() Force-73: '{msg}'")
            self._set_state(QSOState.TX_73_COURTESY)
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
```

## core/diversity.py — get_free_cq_freq + Sticky-Gap Konstanten
```python
"""SimpleFT8 Diversity Controller — periodische Antennen-Messung + CQ-Frequenzwahl.

Score-basierte Messung (v0.93):
  Pro Slot wird ``sum(snr+30)`` ueber alle dekodierten Stationen akkumuliert.
  Kontinuierliche Werte → Median liefert auch bei duenner Decoder-Dichte
  (z.B. FT2 mit 1-2 Stationen pro Slot) statistische Aufloesung.

  Der ``scoring_mode`` ("normal"/"dx") bestimmt aktuell nur die Sammlungs-
  strategie der Aufrufer (Standard sammelt alle Stationen, DX nur SNR<-10);
  intern wird in beiden Modi der gleiche Score gemessen.

Auswertung: Median ueber Slot-Scores (6-Slot fair 3:3), Schwelle 8 % rel.
Differenz → 70:30 bzw. 30:70, sonst 50:50.
"""

import statistics
import time
from typing import Optional


class DiversityController:
    """Periodische Antennen-Messung fuer Diversity-Modus.

    Ablauf:
    - MESS-PHASE  (6 Zyklen): 3×A1 + 3×A2 messen
    - BETRIEB     (60 Zyklen ≈ 15 Min): 70:30 oder 50:50
    - Nach 60 Zyklen ohne aktives QSO → neu messen
    Scoring: Modus-abhaengig (Normal=Stationsanzahl, DX=Top-5-SNR)
    Schwelle: 8% relative Differenz → 50:50, sonst 70:30
    """

    MEASURE_CYCLES = 6   # 3×A1 + 3×A2 (~1,5 Min Fenster, je even+odd pro Antenne)
    THRESHOLD = 0.08     # 8% relative Differenz fuer Antennen-Entscheidung
    # Score-Mindest-Peak: unter dem Wert (sehr schwacher Empfang) wird auf
    # 50:50 zurueckgefallen statt zwischen knappen Differenzen zu entscheiden.
    # 5.0 entspricht ~1 Station bei SNR -25 oder ~0.3 Stationen bei SNR -10.
    MIN_PEAK_SCORE = 5.0
    # Adaptiv-Stop Phase 3 (v0.91 Block 2 #8)
    EARLY_STOP_FRACTION = 2 / 3   # nach 2/3 von MEASURE_CYCLES pruefen
    EARLY_STOP_THRESHOLD = 0.15   # 15% rel. Differenz, ~2× THRESHOLD=8%
    # Such-Periode SLOT-SYNCHRON: pro Modus N Slots = ~60s (DeepSeek/Internet-Konsens)
    _SEARCH_INTERVAL_SLOTS = {"FT8": 4, "FT4": 8, "FT2": 16}
    _CYCLE_S = {"FT8": 15.0, "FT4": 7.5, "FT2": 3.8}
    # 67:33 Pattern (6 Slots, endlos nahtlos wiederholbar)
    # A2 bekommt abwechselnd Even+Odd durch Einzelslots an Pos 2+5
    # Max 2 hintereinander, kein Sprung am Loop-Uebergang
    _PAT_70_A1 = ("A1","A1","A2","A1","A1","A2")  # 4×A1, 2×A2 = 67:33
    _PAT_70_A2 = ("A2","A2","A1","A2","A2","A1")  # 4×A2, 2×A1 = 67:33

    def __init__(self, scoring_mode: str = "normal"):
        """
        self._mode = mode
        self._search_slots_remaining = self._SEARCH_INTERVAL_SLOTS.get(mode, 4)

    def _measure_gap_around(self, bin_idx: int) -> int:
        """Breite der freien Luecke um bin_idx im aktuellen dynamischen Suchbereich.

        Wird nach Sticky-Treffer aufgerufen, damit _current_gap_width_hz die
        echte aktuelle Lueck-Breite reflektiert (nicht den Wert von der
        urspruenglichen Auswahl). Sonst wird die +50Hz-Schwelle gegen einen
        veralteten Referenzwert verglichen.

        Bounds = aktiver Bereich +/- SEARCH_MARGIN_BINS (gleiche Logik wie
        get_free_cq_freq), gefallback auf abs_min/max wenn Histogramm leer.
        """
        if not self._freq_histogram:
            return 0
        occupied_bins = list(self._freq_histogram.keys())
        abs_min = self.FREQ_MIN_HZ // self.FREQ_BIN_HZ
        abs_max = self.FREQ_MAX_HZ // self.FREQ_BIN_HZ
        min_bin = max(abs_min, min(occupied_bins) - self.SEARCH_MARGIN_BINS)
        max_bin = min(abs_max, max(occupied_bins) + self.SEARCH_MARGIN_BINS)
        if (bin_idx in self._freq_histogram
                or bin_idx < min_bin or bin_idx > max_bin):
            return 0
        left = bin_idx
        while left - 1 >= min_bin and (left - 1) not in self._freq_histogram:
            left -= 1
        right = bin_idx
        while right + 1 <= max_bin and (right + 1) not in self._freq_histogram:
            right += 1
        return (right - left + 1) * self.FREQ_BIN_HZ

    def _score_gap(self, gap_start_bin: int, gap_len_bins: int, median_bin: int) -> float:
        """Score: hoeher = besser. Auswahl per max(score), Tiebreak per Distance zum Median.

        Lueckenbreite dominiert (1 Hz = 1 Punkt), Stationen direkt im TX-Bin kosten 100 Hz
        pro Station (schlimmste Kollision), Nachbarn in +/-1 Bin kosten 50 Hz, Nachbarn in
        +/-2 Bins kosten 25 Hz. Median-Distance ist NUR Tiebreaker (0.01).
        Bei Notfall-Lueck mit max_count>=1 erlaubt → n_self bestraft Treffer im TX-Bin.
        """
        gap_width_hz = gap_len_bins * self.FREQ_BIN_HZ
        center_bin = gap_start_bin + gap_len_bins // 2
        n_self = self._freq_histogram.get(center_bin, 0)
        n_close = sum(self._freq_histogram.get(center_bin + d, 0) for d in (-1, +1))
        n_near = sum(self._freq_histogram.get(center_bin + d, 0) for d in (-2, +2))
        neighbor_penalty_hz = 100 * n_self + 50 * n_close + 25 * n_near
        median_distance_hz = abs(center_bin - median_bin) * self.FREQ_BIN_HZ
        return gap_width_hz - neighbor_penalty_hz - 0.01 * median_distance_hz

    def get_free_cq_freq(self) -> Optional[int]:
        """Freie CQ-Frequenz im DYNAMISCHEN Suchbereich min..max der Stationen.

        Suchbereich = min(stationen)..max(stationen) +/- SEARCH_MARGIN_BINS.
        Begründung: TX gehört dort hin wo Stationen tatsaechlich zuhoeren —
        also in den belegten Aktivitätsbereich, nicht ans stille Bandende.

        GRADUELLE LUECKEN-TOLERANZ: probiert erst 150 Hz Mindestbreite, dann
        100 Hz, dann 50 Hz. So wird bei vollem Band trotzdem die beste
        verfuegbare Position gewaehlt statt auf alter (jetzt voller) Freq
        haengen zu bleiben. Erst wenn kein einziger freier Bin existiert → None.
        """
        hist_copy = dict(self._freq_histogram)
        if not hist_copy:
            # Kein RX-Verkehr → keine Auswahl moeglich (Aufrufer behaelt aktuelle Freq)
            return None

        # Such-Range dynamisch aus aktivem Bereich + Margin
        occupied_bins = list(hist_copy.keys())
        abs_min = self.FREQ_MIN_HZ // self.FREQ_BIN_HZ
        abs_max = self.FREQ_MAX_HZ // self.FREQ_BIN_HZ
        min_bin = max(abs_min, min(occupied_bins) - self.SEARCH_MARGIN_BINS)
        max_bin = min(abs_max, max(occupied_bins) + self.SEARCH_MARGIN_BINS)

        # Median ueber alle aktiven Stationen (Suchbereich-Filter unnötig, alle drin)
        all_freqs = []
        for bin_idx, count in hist_copy.items():
            freq = bin_idx * self.FREQ_BIN_HZ + self.FREQ_BIN_HZ // 2
            all_freqs.extend([freq] * count)
        median_freq = statistics.median(all_freqs)
        median_bin = int(median_freq // self.FREQ_BIN_HZ)

        # Stufenweise Lueck-Toleranz fuer volles Band:
        # (max_count_per_bin, min_gap_bins)
        # Stufe 1-3: nur echte Leerstellen (count=0), Breite reduziert
        # Stufe 4-5: schwach belegte Bins (count<=1) als Lueck akzeptieren
        # Score bestraft Stationen im eigenen Bereich, daher landet TX trotzdem
        # auf der ruhigsten Position
        SEARCH_STAGES = [(0, 3), (0, 2), (0, 1), (1, 3), (1, 2)]
        gaps = []
        used_max_count, used_min_bins = 0, 0
        for try_max_count, try_min_bins in SEARCH_STAGES:
            gaps = []
            current_gap_start = None
            current_gap_len = 0
            for b in range(min_bin, max_bin + 1):
                if hist_copy.get(b, 0) <= try_max_count:
                    if current_gap_start is None:
                        current_gap_start = b
                    current_gap_len += 1
                else:
                    if current_gap_len >= try_min_bins:
                        gaps.append((current_gap_start, current_gap_len))
                    current_gap_start = None
                    current_gap_len = 0
            if current_gap_len >= try_min_bins:
                gaps.append((current_gap_start, current_gap_len))
            if gaps:
                used_max_count, used_min_bins = try_max_count, try_min_bins
                break

        if not gaps:
            # Selbst mit Toleranz keine Lueck → Band wirklich dicht
            return None

        if used_max_count > 0 or used_min_bins < 3:
            print(f"[CQ-Freq] Band voll → Notfall-Toleranz: "
                  f"max {used_max_count} Stat./Bin, min {used_min_bins*self.FREQ_BIN_HZ} Hz Breite")

        # Score-basierte Auswahl (max statt min)
        best_gap = max(gaps, key=lambda g: self._score_gap(g[0], g[1], median_bin))
```

## core/omni_tx.py (komplett — alte Slot-Filter-Klasse, wird ersetzt)
```python
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

    def peek_next(self) -> tuple:
        """Schaut den nächsten Slot voraus OHNE State-Mutation.

        P2.OMNI-PATTERN-FIX (v0.95.24): Mid-Cycle-Pretrigger braucht zu
        wissen welche Paritaet/Block der naechste Slot haben wird, bevor
        advance() den State weiterbewegt. Returnt das was advance() +
        should_tx() in 1 Slot zurueckliefern wuerden.

        Returns:
            (next_slot_index, next_block, target_even, is_tx)
            - is_tx=False  → RX-Slot, target_even ist None
            - is_tx=True   → TX-Slot, target_even ist True/False (Even/Odd)
        """
        next_slot_index = (self._slot_index + 1) % 5
        next_block = self.block
        if next_slot_index == 0:
            # Rollover → Block wechselt
            next_block = 2 if self.block == 1 else 1
        is_tx = _TX_PATTERN[next_slot_index]
        if not is_tx:
            return next_slot_index, next_block, None, False
        # TX-Slot: Paritaet bestimmen (analog should_tx)
        if next_block == 1:
            target_even = (next_slot_index == 0)
        else:
            target_even = (next_slot_index == 1)
        return next_slot_index, next_block, target_even, True

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
```

## ui/mw_cycle.py — on_message_decoded, _on_cycle_start, _on_cycle_decoded, _omni_pretrigger_*
```python
"""SimpleFT8 MainWindow — Zyklusverarbeitung + Diversity Akkumulation Mixin."""

from __future__ import annotations

import threading
import time
from typing import TYPE_CHECKING

from PySide6.QtCore import Slot

if TYPE_CHECKING:
    from .main_window import MainWindow

from core.qso_state import QSOState
from core.message import FT8Message
from core import ntp_time
from core.station_accumulator import accumulate_stations
from radio.presets import PREAMP_PRESETS

# P2.OMNI-PATTERN-FIX (v0.95.24): Mid-Cycle-Pretrigger-Schwelle.
# Encoder schlaeft bis next_boundary - 1.3s (TARGET_TX_OFFSET) und
# braucht von dort sleep_dur > 0 — sonst greift v0.80 Fix B Drift-
# Schutz und schiebt TX um 2 Slots. Wir triggern _send_cq mid-cycle
# bei cycle_pos > duration - PRETRIGGER_OFFSET → encoder hat sleep
# Vorlauf > 0. 1.3s = FlexRadio-TX-Buffer-Latenz (= |TARGET_TX_OFFSET|).
_OMNI_PRETRIGGER_OFFSET_S = 1.3


def compute_local_conditions(stations: dict) -> tuple[int, int, float]:
    """P1.19/P1.21: 5-Sterne-Empfang-Score aus Stations-Dict.
        return 2, n, median
    return 1, n, median


class CycleMixin:
    """Mixin fuer Zyklusverarbeitung — wird in MainWindow eingemischt.

    Enthaelt: _on_cycle_decoded (Diversity/Normal Akkumulation),
    _on_cycle_start (Antennenwechsel), on_message_decoded.
    """

    def _on_cycle_decoded(self, messages: list):
        """Ein kompletter FT8-Zyklus dekodiert."""
        if not self.rx_panel._rx_active:
            return

        self._assign_slot_parity(messages)
        self.control_panel.update_decode_count(len(messages) if messages else 0)
        self._update_dt_correction(messages)

        ant, was_phase = "A1", "operate"
        if self._rx_mode == "diversity":
            ant, was_phase = self._pop_diversity_queue()

        # v0.94: waehrend Phase 2 (DXTuneDialog) zaehlt die Hardware-Antenne
        # aus _schedule[_step], nicht das Diversity-Pattern. Sonst falsche
        # Antennen-Markierung im RX-Panel + accumulate_stations
        # (Mike's Screenshot 2026-05-05: CU2JX als A1 obwohl ANT2 G20 lief).
        ant = self._resolve_hardware_antenna(ant)

        # P3 v0.95.20: Audio-Dump fuer Debug/Forschung. Pull-Pattern aus
        # GUI-Thread → Antenne ist garantiert korrekt fuer den just-decoded
        # Slot (kein Race mit Decoder-Thread). Modus-Filter (nur FT8) im
        # Decoder.dump_last_slot. Default-Root: SimpleFT8/audio_dump/.
        if getattr(self, "_audio_dump_enabled", False):
            from core.audio_dump import DEFAULT_DUMP_ROOT
            ant_long = "ANT1" if ant == "A1" else "ANT2"
            self.decoder.dump_last_slot(
                ant_long, DEFAULT_DUMP_ROOT,
                getattr(self, "_audio_dump_max_files", 200),
            )

        if self._rx_mode == "diversity" and was_phase == "measure":
            self._handle_diversity_measure(messages, ant)

        if self._rx_mode == "diversity" and messages:
            self._handle_diversity_operate(messages, ant)
        elif self._rx_mode == "normal":
            self._handle_normal_mode(messages)
        elif messages:
            self._handle_dx_tune_mode(messages)

        # v0.82 Fix E: on_decoder_finished wird NICHT mehr hier aufgerufen.
        # Qt-FIFO sendet cycle_decoded VOR message_decoded → on_decoder_finished
        # liefe sonst VOR den State-Wechseln durch on_message_received
        # (Doppel-Report-Bug v0.81). Stattdessen haengt on_decoder_finished
        # am neuen `cycle_finished`-Decoder-Signal — siehe `_on_cycle_finished`.

        # Slot-synchroner Such-Trigger + Histogramm-Refresh JEDEN Slot
        # (unabhaengig von messages-Inhalt — _diversity_stations mit Aging ist
        # Quelle der Wahrheit). Das fixt P1 (Histogramm-Update Guard) gleich mit.
        if self._rx_mode == "diversity" and was_phase == "operate":
            self._refresh_diversity_freq_view()

        if self._dx_tune_dialog is not None:
            self._dx_tune_dialog.feed_cycle(messages)

        self._run_ap_lite_rescue(messages)
        self._run_auto_hunt(messages)

    @Slot()
    def _on_cycle_finished(self):
        """v0.82 Fix E — Slot-Ende-Hook NACH allen Decoder-Messages.

        Wird vom Decoder ueber das `cycle_finished`-Signal aufgerufen,
        NACHDEM alle message_decoded-Emissions verarbeitet sind. Damit
        laeuft `on_decoder_finished` nach den State-Wechseln durch
        on_message_received → Doppel-Report-Bug v0.81 verhindert.

        Reihenfolge im GUI-Thread (Qt-FIFO pro Sender=Decoder):
        1. _on_cycle_decoded(messages) — Aggregation, _assign_slot_parity
        2. Pro msg: on_message_decoded(msg) → on_message_received → state-Wechsel
        3. _on_cycle_finished() → on_decoder_finished sieht finalen state ✓
        """
        if not self.rx_panel._rx_active:
            return
        self.qso_sm.on_decoder_finished()

    def _refresh_diversity_freq_view(self):
        """Pro Slot: Histogramm refreshen + ggf. Such-Trigger.

        Slot-Counter (_search_slots_remaining) tickt bei jedem Aufruf. Wenn er
        0 erreicht → Suche aktiv ausgeloest. Sonst nur Histogramm-Update damit
        die UI-Bins live bleiben.

        QSO-Schutz: Bei aktivem QSO wird der Such-Counter pro Slot
        ZURUECKGESETZT (nicht dekrementiert) — damit nach QSO-Ende wieder
        volle ~60s Karenzzeit verfuegbar sind und kein Mid-QSO-Frequenz-
        sprung passiert.
        """
        qso_busy = self.qso_sm.state not in (
            QSOState.IDLE, QSOState.TIMEOUT,
            QSOState.CQ_CALLING, QSOState.CQ_WAIT,
        )
        with self._diversity_lock:
            self._diversity_ctrl.sync_from_stations(self._diversity_stations)
            if qso_busy:
                self._diversity_ctrl.reset_search_counter()
            else:
                if self._diversity_ctrl.tick_slot():
                    self._diversity_ctrl.update_proposed_freq(qso_active=False)
        self.control_panel.update_freq_histogram(
            self._diversity_ctrl.get_histogram_data())

    # ───────────────────────────────────────────────────────────────────
    # Helper-Methoden für _on_cycle_decoded — extrahiert für Lesbarkeit.
    # Reine 1:1-Auslagerung der Original-Blöcke, kein Verhaltenswechsel.
    # ───────────────────────────────────────────────────────────────────

    def _assign_slot_parity(self, messages):
        """Slot-Parity respektieren — Decoder hat sie bereits gesetzt.

        # Histogramm + Freq-Suche kommen jetzt aus _refresh_diversity_freq_view
        # (laeuft slot-synchron in _on_cycle_decoded, unabhaengig von messages)

        # Stationen pro Antenne — immer berechnen (nicht nur bei changed)
        a1_msgs = [m for m in self._diversity_stations.values()
                   if getattr(m, 'antenna', '').startswith('A1')]
        a2_msgs = [m for m in self._diversity_stations.values()
                   if getattr(m, 'antenna', '').startswith('A2')]
        ant2_wins = sum(1 for m in self._diversity_stations.values()
                        if getattr(m, 'antenna', '').startswith('A2>'))
        ant1_wins = sum(1 for m in self._diversity_stations.values()
                        if getattr(m, 'antenna', '').startswith('A1>'))
        compared = ant1_wins + ant2_wins
        # DX: schwache Signale (-20 < SNR < -10) pro Antenne
        a1_weak = [m for m in a1_msgs if m.snr is not None and m.snr < -10]
        a2_weak = [m for m in a2_msgs if m.snr is not None and m.snr < -10]

        # Tabelle neu aufbauen wenn sich was geaendert hat
        if changed:
            self.rx_panel.table.setRowCount(0)
            for m in self._diversity_stations.values():
                self.rx_panel.add_message(m)
            self.rx_panel.reapply_sort()
            only_a1 = sum(1 for m in self._diversity_stations.values()
                          if getattr(m, 'antenna', '') == 'A1')
            only_a2 = sum(1 for m in self._diversity_stations.values()
                          if getattr(m, 'antenna', '') == 'A2')
            total = len(self._diversity_stations)
            pct = round(100 * ant2_wins / compared) if compared else 0
            print(f"[Diversity] {total} St. | A1>A2: {ant1_wins} | "
                  f"A2>A1: {ant2_wins} ({pct}%) | "
                  f"Nur A1: {only_a1} | Nur A2: {only_a2}")
            # Antenna Preference Store aktualisieren
            if hasattr(self, '_antenna_prefs'):
                self._antenna_prefs.update_from_stations(self._diversity_stations)

        # Counts immer aktualisieren — auch wenn changed=False (Modus-Wechsel fix)
        self.control_panel.update_diversity_counts(
            len(a1_msgs), len(a2_msgs),
            scoring_mode=self._diversity_ctrl.scoring_mode,
            return
        self.control_panel.update_cycle_bar(seconds_in_cycle, cycle_duration)
        # P2.OMNI-PATTERN-FIX (v0.95.24): Mid-Cycle-Pretrigger fuer OMNI.
        # Loest _send_cq fuer den NAECHSTEN Slot bei cycle_pos > dur-1.3s
        # aus, sodass Encoder Sleep-Vorlauf hat und kein v0.80 Drift-Schutz
        # triggert. Pattern bleibt korrekt.
        self._omni_pretrigger_check(seconds_in_cycle, cycle_duration)

    def _omni_pretrigger_fire_impl(self) -> None:
        """Pretrigger-Logik — gemeinsam fuer QTimer-Pfad UND
        Cycle-Tick-Fallback.

        P3.OMNI-PATTERN-FIX-2 (v0.95.25): Wird primaer vom QTimer
        ausgeloest (in main_window._on_cycle_start gestartet, exakt zur
        Schwelle dur-1.3s). Cycle-Tick-Pfad (_omni_pretrigger_check) ruft
        diese Methode als Fallback wenn QTimer ausnahmsweise nicht
        gefeuert hat.

        Idempotent ueber _omni_pretriggered-Flag — wer zuerst feuert,
        gewinnt; der andere returnt.

        Pre-Conds (alle Bedingungen muessen wahr sein):
        - Reentrancy-Flag _omni_pretriggered=False
        - OMNI active + nicht paused
        - cq_mode (sonst keine CQ-Loop)
        - state in IDLE/CQ_WAIT/CQ_CALLING (kein QSO laufend)
        """
        if self._omni_pretriggered:
            return
        if not self._omni_tx.active or self._omni_tx.is_paused():
            return
        if not self.qso_sm.cq_mode:
            return
        if self.qso_sm.state not in (QSOState.IDLE, QSOState.CQ_WAIT,
                                      QSOState.CQ_CALLING):
            return
        # Pretrigger ausfuehren (atomar via Flag)
        self._omni_pretriggered = True
        next_idx, next_block, target_even, is_tx = self._omni_tx.peek_next()
        if not is_tx:
            # RX-Slot: Pattern-Slot wird via advance() in _on_cycle_start
            # weitergerueckt, kein _send_cq. Flag bleibt True (verhindert
            # Re-Trigger im selben Cycle), wird in _on_cycle_start reset.
            return
        # TX-Slot: Encoder hat Sleep-Vorlauf (sleep_dur > 0)
        self.encoder.tx_even = target_even
        # Pretrigger-Flag in qso_sm setzen damit on_cycle_end im naechsten
        # Slot KEIN doppeltes _send_cq triggert (V3 §2.5).
        self.qso_sm._was_pretriggered = True
        self.qso_sm._send_cq()
        print(f"[OMNI-Pretrigger] Pos {next_idx} Block {next_block} "
              f"target_even={target_even}")

    def _omni_pretrigger_check(self, sic: float, dur: float) -> None:
        """Cycle-Tick-Fallback fuer OMNI-Pretrigger.

        P3.OMNI-PATTERN-FIX-2 (v0.95.25): PRIMAER laeuft Pretrigger via
        QTimer (in main_window._on_cycle_start gestartet, Qt.PreciseTimer
        garantiert ~50ms Genauigkeit). Dieser Cycle-Tick-Pfad ist
        Defense-in-Depth fuer den Fall dass QTimer aus irgendeinem
        Grund nicht gefeuert hat (extreme Eventloop-Verzoegerung,
        Bug in QTimer-Lifecycle).

        Fallback-Schwelle ist deshalb spaet (dur - 0.5s): wenn QTimer
        aktiv waere, hat er bei dur - 1.3s bereits gefeuert +
        _omni_pretriggered=True gesetzt → return. Dieser Pfad greift
        nur wenn das nicht passiert ist.
        """
        if self._omni_pretriggered:
            return  # QTimer hat schon gefeuert (Normalfall)
        if not self._omni_tx.active or self._omni_tx.is_paused():
            return
        if not self.qso_sm.cq_mode:
            return
        if self.qso_sm.state not in (QSOState.IDLE, QSOState.CQ_WAIT,
                                      QSOState.CQ_CALLING):
            return
        fallback_threshold = dur - 0.5  # Notfall-Schwelle
        if sic < fallback_threshold:
            return
        print(f"[OMNI-Pretrigger-FALLBACK] cycle_pos={sic:.2f}s — "
              f"QTimer hat NICHT gefeuert!")
        self._omni_pretrigger_fire_impl()

    @Slot(int, bool)
    def _on_cycle_start(self, cycle_num: int, is_even: bool):
        # P2.OMNI-PATTERN-FIX (v0.95.24): Pretrigger-Flag fuer naechsten
        # Cycle reset. Erstes _on_cycle_tick im neuen Slot kann dann
        # wieder pretriggern (sobald Schwelle erreicht).
        self._omni_pretriggered = False

        # P3.OMNI-PATTERN-FIX-2 (v0.95.25): QTimer fuer Mid-Cycle-Pretrigger.
        # Mathematik (V2 L2): Pretrigger soll bei cycle_pos = dur - 1.3s
        # feuern. Encoder berechnet sleep_dur = next_boundary +
        # TARGET_TX_OFFSET (-0.8) - 0.5 - now. Bei cycle_pos = dur - 1.3
        # ist sleep_dur = 0 — exakt an der Sicherheitsgrenze. Sicheres
        # Fenster fuer Pretrigger: [dur-1.3, dur-0.8] = 500ms breit.
        # Qt.PreciseTimer trifft das ~50ms genau (vs >1500ms bei
        # cycle_tick-Signal-Queue wenn Decoder GUI-Thread blockiert).
        # start() nach start() ersetzt alten Timeout (Restart-Semantik).
        if self._omni_tx.active and not self._omni_tx.is_paused():
            delay_ms = int((self.timer.cycle_duration -
                            _OMNI_PRETRIGGER_OFFSET_S) * 1000)
            self._omni_pretrigger_timer.start(delay_ms)

        # ── Anzeige zurücksetzen wenn kein TX ──────────────────
        if not self.encoder.is_transmitting:
            self.control_panel.update_tx_peak(0.0)

        # ── Auto TX Level Regelung ──────────────────────────────
        if self._fwdpwr_samples:
            self._auto_adjust_tx_level()

        self.qso_sm.on_cycle_end()

        # OMNI-TX: pro Zyklus voranschreiten (P2.OMNI-REDESIGN v4.0).
        # Wenn pausiert (QSO laeuft via _pause_omni_if_active): _slot_index
        # friert ein, kein advance. Block-Switch jetzt automatisch bei
        # rollover (slot_index 4→0) — kein 80-Counter mehr.
        if not self._omni_tx.is_paused():
            self._omni_tx.advance()

        # Diversity: Antenne umschalten bei jedem Zyklus (non-blocking)
        if self._rx_mode == "diversity" and self.radio.ip and self.rx_panel._rx_active:
            # BUG-1: TX-Schutz — waehrend TX keine Antenne umschalten!
            if self.encoder.is_transmitting:
                return

            with self._diversity_lock:  # BUG-2: Race Condition Guard
                # Queue: aktuelle Antenne + Phase merken BEVOR umgeschaltet wird.
                ant_queue = getattr(self, '_diversity_ant_queue', None)
                if ant_queue is not None:
                    ant_queue.append((self._diversity_current_ant, self._diversity_ctrl.phase))

                band = self.settings.band

                # Betriebszyklus zaehlen + ggf. neu messen (v0.93: zeit-basiert)
                if self._diversity_ctrl.phase == "operate":
                    self._diversity_ctrl.on_operate_cycle()
                    # qso_active = echtes QSO laeuft (NICHT CQ-Ruf)
                    qso_active = self.qso_sm.state not in (
            ant2_wins=ant2_wins if self._rx_mode == "diversity" else 0,
            snr_delta=snr_delta if self._rx_mode == "diversity" else 0.0,
        )
        # Indikator gruen: Daten wurden gerade geschrieben
        _lbl = getattr(self, '_stats_indicator', None)
        if _lbl:
            _lbl.setStyleSheet("color: #00CC44; font-family: Menlo; font-size: 11px; padding: 0 6px;")
        return True

    def on_message_decoded(self, msg: FT8Message):
        """Vom Decoder — NUR fuer QSO-Logik, NICHT fuer Tabelle!"""
        if not self.rx_panel._rx_active:
            return
        self.control_panel.update_snr(msg.snr)
        self.qso_sm.set_last_snr(msg.snr)

        # RX zuerst anzeigen, dann verarbeiten (sonst erscheint TX-Antwort vor RX im Log)
        if msg.target == self.settings.callsign:
            self.qso_panel.add_rx(
                msg.raw,
                tx_even=getattr(msg, '_tx_even', None),
                slot_start_ts=getattr(msg, '_slot_start_ts', None),
            )

        self.qso_sm.on_message_received(msg)
```

## ui/mw_qso.py — _pause_omni, _maybe_resume_omni, _on_send_message, _on_cancel HALT, _on_qso_*, _on_state_changed, _on_tx_finished
```python
"""SimpleFT8 MainWindow — QSO-Steuerung, CQ, Station-Klick Mixin."""

from __future__ import annotations

import time
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, Slot

if TYPE_CHECKING:
    from .main_window import MainWindow

from core.qso_state import QSOState
from core.message import FT8Message


# P1.7 (v0.95.19): ADIF-Duplikat-Filter Zeit-Fenster (Sekunden).
# Mike's Spec 2026-05-05: < 5 Min nach RR73 erneut → kein doppelter Eintrag.
# Cache ist Session-lokal in MainWindow._recent_logged_calls (App-Restart
# loescht den State, ist gewollt — Mike will Reset bei manuellem Neustart).
# Cache-Wachstum: bei 18000 QSOs ~1-2 MB, kein Cleanup noetig (KISS).
_LOG_DEDUP_WINDOW_S = 300


class QSOMixin:
    """Mixin fuer QSO-Logik — wird in MainWindow eingemischt.

    Enthaelt: Station anklicken, CQ, QSO-State Callbacks, QRZ Upload.
    """
    """


    # ── P2.OMNI-REDESIGN v4.0 (v0.95.23): DRY-Helpers fuer Pause/Resume ─────
    # ── P2.OMNI-REDESIGN v4.0 (v0.95.23): DRY-Helpers fuer Pause/Resume ─────


    def _pause_omni_if_active(self) -> None:
    def _pause_omni_if_active(self) -> None:
        """OMNI pausieren + Pre-QSO-Flag setzen wenn OMNI aktiv.
        """OMNI pausieren + Pre-QSO-Flag setzen wenn OMNI aktiv.


        Aufruf-Stellen (3 QSO-Entry-Pfade — alle zentral hier wegen K1):
        Aufruf-Stellen (3 QSO-Entry-Pfade — alle zentral hier wegen K1):
          1. _on_station_clicked (Hunt-Klick)
          1. _on_station_clicked (Hunt-Klick)
          2. _on_tx_slot_for_partner (CQ-Reply, nur nicht-courtesy)
          2. _on_tx_slot_for_partner (CQ-Reply, nur nicht-courtesy)
          3. _on_try_replace_pending_tx (P1.9 Replace, R1-V2 K1-Fix)
          3. _on_try_replace_pending_tx (P1.9 Replace, R1-V2 K1-Fix)


        Setzt _omni_was_active_pre_qso=True damit _maybe_resume_omni
        Setzt _omni_was_active_pre_qso=True damit _maybe_resume_omni
        nach QSO-Ende sauber resumed. _slot_index friert während QSO ein.
        nach QSO-Ende sauber resumed. _slot_index friert während QSO ein.
        """
        """
        if self._omni_tx.active:
        if self._omni_tx.active:
            self._omni_tx.pause()
            self._omni_tx.pause()
            self._omni_was_active_pre_qso = True
            self._omni_was_active_pre_qso = True


    def _maybe_resume_omni(self) -> None:
    def _maybe_resume_omni(self) -> None:
        """OMNI nach QSO-Ende fortsetzen — nur wenn vorher aktiv und
        """OMNI nach QSO-Ende fortsetzen — nur wenn vorher aktiv und
        Caller-Queue leer. Aufruf-Stellen: _on_qso_complete (RR73 fertig),
        Caller-Queue leer. Aufruf-Stellen: _on_qso_complete (RR73 fertig),
        _on_qso_confirmed (73 empfangen), _on_qso_timeout.
        _on_qso_confirmed (73 empfangen), _on_qso_timeout.


        „Kein Slot verschwenden" (Mike 09.05.2026): Block-Wahl per nächster
        „Kein Slot verschwenden" (Mike 09.05.2026): Block-Wahl per nächster
        Slot-Parität — next_is_even → Block 1, sonst Block 2.
        Slot-Parität — next_is_even → Block 1, sonst Block 2.


        Bei nicht-leerer Caller-Queue bleibt OMNI pausiert — _resume_cq_if_needed
        Bei nicht-leerer Caller-Queue bleibt OMNI pausiert — _resume_cq_if_needed
        startet das nächste QSO direkt, dort greift wieder _pause_omni_if_active.
        startet das nächste QSO direkt, dort greift wieder _pause_omni_if_active.
        """
        """
        if not getattr(self, '_omni_was_active_pre_qso', False):
        if not getattr(self, '_omni_was_active_pre_qso', False):
            return
            return
        if self.qso_sm._caller_queue:
        if self.qso_sm._caller_queue:
            return  # nächstes QSO direkt anschliessen, OMNI bleibt pausiert
            return  # nächstes QSO direkt anschliessen, OMNI bleibt pausiert
        next_is_even = not self.timer.is_even_cycle()
        next_is_even = not self.timer.is_even_cycle()
        self._omni_tx.start_with_parity_for_next_slot(next_is_even)
        self._omni_tx.start_with_parity_for_next_slot(next_is_even)
        self._omni_was_active_pre_qso = False
        self._omni_was_active_pre_qso = False


    def _antenna_pref_label(self, call: str) -> str:
    def _antenna_pref_label(self, call: str) -> str:
        """Vereinheitlichtes Format fuer alle Anzeigen:
        """Vereinheitlichtes Format fuer alle Anzeigen:
          - Normal-Modus oder ANT1 als beste Antenne → ' (ANT1)'
          - Normal-Modus oder ANT1 als beste Antenne → ' (ANT1)'
          - Diversity + ANT2 ist Hysterese-Schwelle besser → ' (ANT2 ↑X.X dB)'
          - Diversity + ANT2 ist Hysterese-Schwelle besser → ' (ANT2 ↑X.X dB)'
        Pfeil ↑ = Diversity bringt messbaren Gewinn.
        Pfeil ↑ = Diversity bringt messbaren Gewinn.
        """
        """
        if self._rx_mode == "normal":
        if self._rx_mode == "normal":
            return " (ANT1)"
            return " (ANT1)"
        if not hasattr(self, '_antenna_prefs'):
            return ""
        pref = self._antenna_prefs.get_pref(call)
        if not pref:
            return ""
            self._pending_station_click = msg
            self.statusBar().showMessage(
                f"TX läuft — {msg.caller} wird im nächsten Slot gerufen",
                3000)
            return
        if getattr(self, '_diversity_measuring', False):
            print(f"[QSO] Einmessen aktiv — Hunt blockiert")
            return
        # P2.OMNI-REDESIGN v4.0 (v0.95.23): OMNI bei Hunt-QSO pausieren
        # (Entry-Pfad 1 von 3 — _slot_index friert ein bis _maybe_resume_omni).
        self._pause_omni_if_active()
        # CQ-Modus beenden wenn aktiv — _was_cq VOR stop_cq() sichern!
        # stop_cq() setzt cq_mode=False; start_qso() würde dann _was_cq=False speichern
        # → _resume_cq_if_needed() würde CQ nach QSO NICHT wiederaufnehmen (Bug)
        _cq_was_active = self.qso_sm.cq_mode
        if _cq_was_active:
            self.qso_sm.stop_cq()
            self.control_panel.set_cq_active(False)
        # Auto-Hunt pausieren bei manuellem Klick
        if self._auto_hunt.active:
            self._auto_hunt.on_manual_qso_start()
        # P1.14 KP3: alte their_call aus _active_qso_targets entfernen
        # (sonst Set-Bloat bei haeufigen Wechseln)
        old_call = self.qso_sm.qso.their_call if self.qso_sm.qso else None
        if old_call:
            self._active_qso_targets.discard(old_call)
        self._active_qso_targets.add(msg.caller)  # 150s Aging fuer angerufene Station
        self.rx_panel.set_active_call(msg.caller)  # Zeile im RX-Panel hervorheben
        # P1.14 KP2: wenn Station bereits in Caller-Queue gewartet hat, aus
        # Queue entfernen damit sie nicht doppelt kontaktiert wird (sonst
        # Doppel-QSO-Risiko nach Resume)
        # Integration in start_qso ist nicht moeglich weil stop_cq() vor
        # start_qso() laufen MUSS — _was_cq waere dort schon False.
        if _cq_was_active:
            self.qso_sm._was_cq = True

    def _on_country_filter_changed(self, country_filter: list):
        """Länder-Filter in Settings speichern."""
        self.settings.set("country_filter", country_filter)
        self.settings.save()

    @Slot()
    def _on_cq_clicked(self):
        if self.control_panel.btn_cq.isChecked():
            # Laufendes Hunt-QSO abbrechen bevor CQ startet!
            if self.qso_sm.state not in (QSOState.IDLE, QSOState.TIMEOUT,
                                          QSOState.CQ_CALLING, QSOState.CQ_WAIT):
                self.qso_sm.cancel()
                self._active_qso_targets.clear()
                self.rx_panel.set_active_call("")
                print("[CQ] Hunt-QSO abgebrochen → CQ starten")
            # CQ-Frequenz: nur Diversity nutzt Auto-Suche; Normal-Modus = WSJT-X-Standard,
            # User waehlt manuell ueber Klick/Spinbox (encoder.audio_freq_hz schon gesetzt).
            if self._rx_mode == "diversity":
                cq_freq = self._diversity_ctrl.get_free_cq_freq()
                if cq_freq and cq_freq != self.encoder.audio_freq_hz:
                    self.encoder.audio_freq_hz = cq_freq
                    print(f"[CQ] TX-Frequenz auf {cq_freq} Hz (aus Auto-Suche)")
                    self.control_panel.update_freq_histogram(
                        self._diversity_ctrl.get_histogram_data())
            else:
                print(f"[CQ] Normal-Modus → manuelle TX-Frequenz {self.encoder.audio_freq_hz} Hz")
            # CQ: immer auf festem Slot senden (aktueller Gegenteil-Slot)
            self.encoder.tx_even = not self.timer.is_even_cycle()
            slot = "EVEN" if self.encoder.tx_even else "ODD"
            print(f"[CQ] Fester TX-Slot: {slot}")
            self.qso_panel.add_info("CQ-Modus gestartet")
            self.qso_sm.start_cq()
        else:
            count = self.qso_sm.cq_qso_count
            self.qso_panel.add_info(f"CQ-Modus gestoppt ({count} QSOs)")
            self.qso_panel.status_label.setText(f"{count} QSO(s)")
            self.qso_panel.status_label.setStyleSheet("color: #666; font-size: 11px; padding: 2px;")
            self.qso_sm.stop_cq()
            self.control_panel.update_qso_counter(0)

    @Slot()
    def _on_advance(self):
        self.qso_sm.advance()

    @Slot()
    def _on_cancel(self):
        """HALT — stoppt ALLES: CQ, QSO, TX, Messung, OMNI, Auto-Hunt."""
        self._active_qso_targets.clear()
        self._pending_station_click = None  # P1.24: gepufferten Klick verwerfen
        self.rx_panel.set_active_call("")
        # TX sofort stoppen
        if self.encoder.is_transmitting:
            self.encoder.abort()
            if self.radio.ip:
                self.radio.ptt_off()
        # CQ + QSO stoppen
        self.qso_sm.stop_cq()
        self.qso_sm.cancel()
        self.control_panel.set_cq_active(False)
        # P1.14 W6: Auto-Hunt freigeben (sonst dauerhaft pausiert nach HALT)
        if self._auto_hunt.active:
            self._auto_hunt.on_manual_qso_end()
        # P1.OMNI-START (v0.95.22): OMNI ebenfalls stoppen — ohne diesen Branch
        # blieb omni_tx.active=True nach HALT, Inkonsistenz mit Button-State.
        if self._omni_tx.active:
            self._omni_tx.stop_omni_tx("manual_halt")
        # P2.OMNI-PATTERN-FIX (v0.95.24): Pretrigger-Flags fuer sauberen
        # Re-Start invalidieren. _on_omni_stopped resettet self._omni_pretriggered
        # bereits — hier defensiv zusaetzlich qso_sm._was_pretriggered.
        self.qso_sm._was_pretriggered = False
        self.qso_panel.add_info("HALT — alles gestoppt")
        self.statusBar().showMessage("HALT — CQ, QSO, TX, OMNI gestoppt", 5000)
        print("[HALT] Alles gestoppt")

    @Slot(object)
    def _on_state_changed(self, state: QSOState):
        name = state.name
        self.control_panel.update_state(name)
        # AP-Prioritaet: aktiver QSO-Partner bekommt hoechste AP-Hint-Prioritaet
        if state not in (QSOState.IDLE, QSOState.TIMEOUT):
            self.decoder.priority_call = (
                self.qso_sm.qso.their_call if self.qso_sm.qso else ""
            )
        else:
            self.decoder.priority_call = ""

        )
        self.control_panel.set_tx_active(is_tx)

        if self.qso_sm.cq_mode:
            self.control_panel.update_qso_counter(self.qso_sm.cq_qso_count)
            # CQ-Button immer aktiv wenn cq_mode=True — auch während QSO-Sequenz
            self.control_panel.set_cq_active(True)

    def _on_tx_finished(self):
        """TX abgeschlossen — PTT aus, zurueck zu RX."""
        self.control_panel.set_tx_active(False)
        self.qso_sm.on_message_sent()
        # P1.24: gepufferter Station-Klick aus TX-Phase jetzt nachholen
        # (is_transmitting ist hier False, state-Cleanup ist im
        # _on_station_clicked-TX-Pfad bereits passiert)
        if self._pending_station_click is not None:
            buffered = self._pending_station_click
            self._pending_station_click = None
            print(f"[QSO] TX fertig — Buffered Klick {buffered.caller} jetzt anrufen")
            self._on_station_clicked(buffered)

    @Slot(str)
    def _on_send_message(self, message: str):
        """FT8-Nachricht encoden und ueber FlexRadio senden.

        P2.OMNI-REDESIGN v4.0 (v0.95.23): Flag-Pattern fuer OMNI-RX-Slot.
        Vorher wurde calls_made-- als Pflaster benutzt, aber State blieb auf
        CQ_CALLING haengen → on_cycle_end greift nicht mehr → CQ-Loop tot.
        Jetzt setzt RX-Slot _omni_skip_state_change=True; qso_state._send_cq
        ueberspringt dann den State-Wechsel, on_cycle_end re-CQ greift.
        """
        # Operator Presence Check (Totmannschalter, gesetzl. Pflicht DE)
        # Laufende QSOs werden IMMER zu Ende gefuehrt!
        if not self.presence_can_tx():
            print(f"[Presence] TX blockiert (Operator abwesend): '{message}'")
            return
        if message.startswith("CQ "):
            self._has_sent_cq = True
            # OMNI-TX: CQ-Slot-Steuerung mit Even/Odd Paritaet (Flag-Pattern v4.0)
            if self._omni_tx.active:
                # P2.OMNI-PATTERN-FIX (v0.95.24): Pretrigger-Pfad hat
                # tx_even bereits gesetzt + naechsten-Slot-Pos validiert via
                # peek_next + _was_pretriggered=True. should_tx wuerde hier
                # auf den AKTUELLEN Slot pruefen — der ist aber schon
                # vorbei. Daher Pretrigger-Bypass: Counter inkrementieren,
                # State-Wechsel passiert wie gewohnt.
                if getattr(self.qso_sm, '_was_pretriggered', False):
                    if self.encoder.tx_even is True:
                        self._omni_tx.cq_even_count += 1
                    elif self.encoder.tx_even is False:
                        self._omni_tx.cq_odd_count += 1
                    print(f"[OMNI-TX] Pretrigger-TX "
                          f"({self._omni_tx.slot_label}, naechster Slot)")
                else:
                    # Klassischer Pfad (Toggle-Initial-CQ, Resume-Initial-CQ):
                    # _send_cq wurde aus on_cycle_end heraus aufgerufen,
                    # should_tx-Filter prueft current-Slot-Pos.
                    send_ok, target_even = self._omni_tx.should_tx()
                    if not send_ok:
                        # RX-Slot: TX skip + State-Wechsel-Skip via Flag
                        self.qso_sm._omni_skip_state_change = True
                        print(f"[OMNI-TX] RX-Slot → skip CQ "
                              f"({self._omni_tx.slot_label})")
                        # P3.OMNI-PATTERN-FIX-2 (v0.95.25): RX-Slot-Anzeige
                        # im QSO-Panel — Lebenszeichen wenn nichts gesendet
                        # wird. Mike-Wunsch: er soll sehen dass App laeuft.
                        now = time.time()
                        slot_dur = self.timer.cycle_duration
                        slot_start = now - (now % slot_dur)
                        is_even = int(slot_start / slot_dur) % 2 == 0
                        self.qso_panel.add_listening(slot_start, is_even)
                        return
                    # TX-Slot: Encoder auf richtige Paritaet setzen
                    if target_even is not None:
                        self.encoder.tx_even = target_even
                        parity_str = "Even" if target_even else "Odd"
                        print(f"[OMNI-TX] TX auf {parity_str} "
                              f"({self._omni_tx.slot_label})")
                        # Statusbar-Counter (Even/Odd-Verteilung)
                        if target_even:
                            self._omni_tx.cq_even_count += 1
                        else:
                            self._omni_tx.cq_odd_count += 1
        print(f"[TX] → '{message}' auf {self.encoder.audio_freq_hz} Hz")
        # v0.80 Fix A2: wenn bereits ein TX gescheduled ist (z.B. alter
        # Retry-TX im Sleep), erst abbrechen. Sonst werden zwei TX-Worker
        # parallel laufen und der alte sendet eine veraltete Message
        # nachdem der State sich geaendert hat.
        if self.encoder.is_transmitting:
            self.encoder.abort()
        self.encoder.transmit(message)  # add_tx() wird via tx_started Signal aufgerufen

    @Slot(object)
    def _on_qso_complete(self, qso_data):
        """RR73 gesendet — ADIF schreiben (UI-Meldung kommt erst bei 73 oder Timeout).

        P1.7 (v0.95.19): Duplikat-Filter — wenn dieselbe Station auf
        gleichem Band innerhalb _LOG_DEDUP_WINDOW_S=300s schon geloggt
        wurde, ADIF/qso_log/Antennen-Stats ueberspringen.
        UI-Cleanup (active_qso, rx_panel, auto_hunt) laeuft IMMER —
        sonst Inkonsistenzen (R1-KRITISCH).
        """
        # UI-Cleanup IMMER (vor Duplikat-Check) — R1-KRITISCH:
        self._active_qso_targets.discard(qso_data.their_call)
        self.rx_panel.set_active_call("")
        # Auto-Hunt: QSO erfolgreich → Pause, dann naechste Station
        if self._auto_hunt.active:
            self._auto_hunt.on_qso_complete(qso_data.their_call)

        # KEIN add_qso_complete hier — kommt in _on_qso_confirmed (nach 73 oder Timeout)

        band = self.settings.band.upper()
        freq = self.settings.frequency_mhz

        # P1.7 Duplikat-Check: (call, band)-Tupel-Key, beide UPPER (siehe
        # qso_log.py:23 add_qso normiert Band/Call gleich). Mode wird
        # bewusst NICHT in den Key aufgenommen — KISS, Mike's Mode-Wechsel
        # binnen 5 Min mit gleicher Station ist Hobby-Praxis quasi nie.
        now = time.time()
        call_key = qso_data.their_call.upper()
        dedup_key = (call_key, band)
        last = self._recent_logged_calls.get(dedup_key, 0.0)
        if now - last < _LOG_DEDUP_WINDOW_S:
            print(f"[QSO] DUPLIKAT-FILTER: {call_key}@{band} schon vor "
                  f"{int(now-last)}s geloggt → skip ADIF + qso_log + antenna_stats")
            self.qso_panel.add_info(
                f"{call_key} Duplikat ({int(now-last)}s) — kein ADIF-Eintrag")
            # P2.OMNI-REDESIGN v4.0: Resume-Versuch trotzdem (Symmetrie zu
            # Non-Duplikat-Pfad — UI-Cleanup lief schon, OMNI darf weiter).
            self._maybe_resume_omni()
            return  # KEIN log_qso, KEIN add_qso, KEIN log_antenna_qso
        self._recent_logged_calls[dedup_key] = now

        self.adif.log_qso(
            call=qso_data.their_call,
            band=band,
            freq_mhz=freq,
            mode=self.settings.mode,
            rst_sent=qso_data.our_snr or "-10",
            rst_rcvd=qso_data.their_snr or "-10",
            gridsquare=qso_data.their_grid or "",
            my_gridsquare=self.settings.locator,
            my_callsign=self.settings.callsign,
            tx_power=self.settings.power_watts,
            time_on=qso_data.start_time,
        )
        self.qso_log.add_qso(qso_data.their_call, band)

        # Antennen-Statistik pro QSO loggen — immer schreiben, "–" wenn kein Pref
        if hasattr(self, '_stats_logger') and self._stats_logger is not None:
            pref = None
            if self._rx_mode == "diversity" and hasattr(self, '_antenna_prefs'):
                pref = self._antenna_prefs.get_pref(qso_data.their_call)
            self._stats_logger.log_antenna_qso(
                call=qso_data.their_call,
                band=self.settings.band,
                ft_mode=self.settings.mode,
                best_ant=pref["best_ant"] if pref else None,
                delta_db=pref["delta_db"] if pref else None,
            )

        # P2.OMNI-REDESIGN v4.0 (v0.95.23): OMNI nach RR73 fertig resumen
        # (Exit-Pfad 1 von 3). _maybe_resume_omni schuetzt sich selbst
        # via _omni_was_active_pre_qso und Caller-Queue-Check.
        self._maybe_resume_omni()

    @Slot(object)
    def _on_qso_confirmed(self, qso_data):
        """73 empfangen — QSO wirklich komplett, ✓ anzeigen."""
        self.qso_panel.add_qso_complete(qso_data.their_call)
        # Logbuch aktualisieren (neues QSO wurde in ADIF geschrieben)
        self.qso_panel.logbook.refresh()
        # P1.14 W6: Auto-Hunt nach erfolgreichem manuellem QSO freigeben
        if self._auto_hunt.active:
            self._auto_hunt.on_manual_qso_end()
        # CQ-Modus läuft weiter — visuell bestätigen
        if self.qso_sm.cq_mode:
            self.control_panel.set_cq_active(True)
            self.qso_panel.add_info("CQ-Modus läuft weiter...")
        # P2.OMNI-REDESIGN v4.0 (v0.95.23): OMNI nach 73-Empfang/WAIT_73-Timeout
        # /Courtesy-73-fertig resumen (Exit-Pfad 2 von 3).
        self._maybe_resume_omni()

    def _get_qrz_client(self):
        """QRZ Client lazy initialisieren."""
        if self._qrz_client is None:
            self.qso_panel.logbook.set_qrz_button_enabled(enabled)
        except AttributeError:
            pass

    @Slot(str)
    def _on_qso_timeout(self, their_call: str):
        self._active_qso_targets.discard(their_call)
        self.rx_panel.set_active_call("")
        self.qso_panel.add_timeout(their_call)
        # Auto-Hunt: Timeout → Cooldown setzen, naechste Station
        if self._auto_hunt.active:
            self._auto_hunt.on_qso_timeout(their_call)
            # P1.14 W6: _manual_override zuruecksetzen (sonst pausiert
            # Auto-Hunt nach Klick → Timeout dauerhaft)
            self._auto_hunt.on_manual_qso_end()
        # CQ-Button aktiv halten wenn CQ-Modus laeuft
        if self.qso_sm.cq_mode:
            self.control_panel.set_cq_active(True)
        # P2.OMNI-REDESIGN v4.0 (v0.95.23): OMNI nach Hunt/QSO-Timeout
        # resumen (Exit-Pfad 3 von 3).
        self._maybe_resume_omni()

    @Slot(list)
    def _on_caller_queue_changed(self, queue: list):
        """Warteliste geändert — im QSO-Panel anzeigen."""
        if queue:
            calls = ", ".join(queue)
            self.qso_panel.add_info(f"⏳ Warteliste: {calls}")
            self.control_panel.update_qso_counter(self.qso_sm.cq_qso_count)
        else:
            if self.qso_sm.cq_mode:
```

## ui/main_window.py — OMNI-Init, _on_btn_omni_cq_toggled, _on_omni_stopped, _on_presence_tick, OMNI-Stop-Trigger
```python
"""SimpleFT8 Main Window — 3-Fenster-Layout mit QSplitter.

Kernlogik ist in 4 Mixins aufgeteilt:
  - CycleMixin  (mw_cycle.py)  — Zyklusverarbeitung, Diversity Akkumulation
  - QSOMixin    (mw_qso.py)    — QSO-Steuerung, CQ, Station-Klick, QRZ
  - RadioMixin  (mw_radio.py)  — Radio-Verbindung, Band, Diversity, DX-Tuning
  - TXMixin     (mw_tx.py)     — TX-Regelung, Meter, SWR
"""

import math
import threading
from pathlib import Path

from PySide6.QtWidgets import (
    QMainWindow, QSplitter, QWidget, QVBoxLayout,
    QMessageBox, QScrollArea, QLabel,
)
from PySide6.QtCore import Qt, Slot, Signal, QTimer

from config.settings import Settings, BAND_FREQUENCIES
from core.timing import FT8Timer
from core.qso_state import QSOStateMachine, QSOState
from core.encoder import Encoder
from core.decoder import Decoder
from core.message import FT8Message
from core.diversity import DiversityController
from log.adif import AdifWriter
from radio.radio_factory import create_radio
from .rx_panel import RXPanel
from .qso_panel import QSOPanel
        self._pending_station_click = None  # P1.24: Klick waehrend TX → Buffer fuer naechsten Slot
        self._recent_logged_calls: dict[tuple[str, str], float] = {}  # P1.7 (v0.95.19): ADIF-Dedup (call, band) → ts
        # P2.OMNI-REDESIGN v4.0 (v0.95.23): True wenn OMNI VOR aktuellem QSO
        # aktiv war — _maybe_resume_omni resumed dann nach QSO-Ende.
        # Gesetzt von _pause_omni_if_active in 3 Entry-Pfaden, geloescht
        # bei Resume oder bei OMNI-HALT/Stop.
        self._omni_was_active_pre_qso: bool = False
        # P2.OMNI-PATTERN-FIX (v0.95.24): Pretrigger-Reentrancy-Schutz.
        # Verhindert dass _on_cycle_tick den Pretrigger im selben Cycle
        # mehrfach ausloest (cycle_tick feuert ~10 Hz, Schwellen-Fenster
        # ist 1.3s breit → ~13 Ticks). Reset in _on_cycle_start (neuer
        # Slot) + _on_cancel (HALT) + _on_omni_stopped.
        self._omni_pretriggered: bool = False
        # P3.OMNI-PATTERN-FIX-2 (v0.95.25): QTimer fuer Mid-Cycle-Pretrigger.
        # Wurzel: cycle_tick wird von Decoder-Blocking um >1s verzoegert →
        # Pretrigger zu spaet → v0.80 Drift-Schutz schiebt 2 Slots → Pattern
        # verschoben. Loesung: QTimer.singleShot mit Qt.PreciseTimer im GUI-
        # Thread (typisch 0-50ms Drift). cycle_tick-basierter Pretrigger
        # bleibt als Fallback (Schwelle dur-0.5s).
        # Restart-Semantik: start() nach start() ersetzt alten Timeout.
        # Stop-Reason-zentral: omni_stopped → _on_omni_stopped → timer.stop().
        self._omni_pretrigger_timer = QTimer(self)
        self._omni_pretrigger_timer.setSingleShot(True)
        self._omni_pretrigger_timer.setTimerType(Qt.TimerType.PreciseTimer)
        self._omni_pretrigger_timer.timeout.connect(
            self._omni_pretrigger_fire_impl)
        # P3 v0.95.20: Audio-Dump-Settings (in mw_cycle._on_cycle_decoded gelesen)
        self._audio_dump_enabled = self.settings.get("audio_dump_enabled", False)
        self._audio_dump_max_files = self.settings.get("audio_dump_max_files", 200)
        self._diversity_lock = threading.Lock()  # Race Condition Guard
        self._tune_active = False
        self._tune_freq_mhz = None

    def _init_power_state(self):
        """Auto TX Level Regelung (zweistufig: rfpower primär, audio sekundär)."""
        from core.rf_preset_store import RFPresetStore
        self._power_target = self.settings.get("power_preset", 10)  # Watt-Ziel vom Button
        self._fwdpwr_samples = []   # FWDPWR Messwerte waehrend TX
        self._rfpower_current = 50  # Aktuell gesetzter rfpower-Wert (0-100)
        self._rfpower_converged = False  # True wenn rfpower stabil
        self._was_converged = False  # True wenn aktuelle Konvergenz schon gespeichert
        self.rf_preset_store = RFPresetStore()
        # Migration aus altem rfpower_per_band-Eintrag (idempotent)
        self.rf_preset_store.migrate_from_settings(
            self.settings._data, radio="flexradio", default_watts=self._power_target
        )

    def _init_optional_features(self):
        """OMNI-TX (Easter Egg, Feldtest), Auto-Hunt, AP-Lite — alle deaktiviert by default."""
        # OMNI-TX: Initialisieren (deaktiviert), Easter Egg verbinden
        # P2.OMNI-REDESIGN v4.0 (v0.95.23): block_cycles-Counter weg
        # (war Diversity-OPERATE_CYCLES-Überrest). Block-Switch jetzt
        # automatisch bei slot_index 4→0 Rollover.
        from core import omni_tx as _omni
        self._omni_tx = _omni.get_instance()
        # v0.78: Signal omni_stopped(reason) → UI raeumt auf
        self._omni_tx.omni_stopped.connect(self._on_omni_stopped)
        # v0.78: Button-Klick → start/stop_omni_tx
        self.control_panel.btn_omni_cq.toggled.connect(self._on_btn_omni_cq_toggled)
        self.control_panel.easter_egg_toggle_clicked.connect(self._on_easter_egg_toggle)

        # Auto-Hunt: Initialisieren (deaktiviert, zusammen mit OMNI-TX)
        from core.auto_hunt import AutoHunt
        self._auto_hunt = AutoHunt()
        self._auto_hunt.set_qso_log(self.qso_log)
        self._auto_hunt.set_band(self.settings.band)

        # v0.75 Auto-Hunt UI-Lifecycle
        self._easter_egg_active: bool = False
        self._auto_hunt_cooldown_seconds: int = 0
        # 1s-Polling fuer Live-Countdown waehrend aktiver Session
        from PySide6.QtGui import QCursor
        _PRESENCE_TIMEOUT = 900  # 15 Minuten in Sekunden
        self._presence_remaining = _PRESENCE_TIMEOUT
        self._presence_timeout = _PRESENCE_TIMEOUT
        self._presence_expired = False
        self._presence_timer = QTimer(self)
        self._presence_timer.timeout.connect(self._on_presence_tick)
        self._presence_timer.start(1000)  # Jede Sekunde
        # Presence-Reset: Maus-Polling (alle 500ms QCursor.pos() pruefen)
        self._presence_last_mouse_pos = QCursor.pos()
        self._presence_poll_timer = QTimer(self)
        self._presence_poll_timer.timeout.connect(self._poll_mouse_activity)
        self._presence_poll_timer.start(500)

    def _init_cq_countdown_timer(self):
        """CQ-Freq Countdown: sekündlich aktualisieren (unabhängig vom Decode-Zyklus)."""
        from PySide6.QtCore import QTimer
        self._cq_countdown_timer = QTimer(self)
        self._cq_countdown_timer.timeout.connect(self._tick_cq_countdown)
        self._cq_countdown_timer.start(1000)

        self.rx_panel.country_filter_changed.connect(self._on_country_filter_changed)

        # Control Panel
        self.control_panel.mode_changed.connect(self._on_mode_changed)
        self.control_panel.band_changed.connect(self._on_band_changed)
        self.control_panel.power_changed.connect(self._on_power_changed)
        self.control_panel.advance_clicked.connect(self._on_advance)
        self.control_panel.cancel_clicked.connect(self._on_cancel)
        self.control_panel.cq_clicked.connect(self._on_cq_clicked)
        self.control_panel.tune_clicked.connect(self._on_tune_clicked)
        self.control_panel.rx_mode_changed.connect(self._on_rx_mode_changed)
        self.control_panel.einmessen_clicked.connect(self._handle_dx_tuning)
        self.control_panel.settings_clicked.connect(self._on_settings_clicked)
        self.control_panel.map_clicked.connect(lambda: self.open_direction_map())
        # Manuelle TX-Frequenz im Normal-Modus: Klick im Histogramm + Spinbox
        self.control_panel._freq_hist.tx_freq_clicked.connect(self._on_normal_tx_freq_clicked)
        self.control_panel._tx_freq_spin.valueChanged.connect(self._on_normal_tx_freq_spin_changed)

        # QSO State Machine
        self.qso_sm.state_changed.connect(self._on_state_changed)
        self.qso_sm.send_message.connect(self._on_send_message)
        self._easter_egg_active = not self._easter_egg_active
        if not self._easter_egg_active:
            # Aktive Modi sauber stoppen — Signal-Slots kuemmern sich um UI-Cleanup
            if self._auto_hunt.active:
                self._auto_hunt.stop_auto_hunt("easter_egg_off")
            if self._omni_tx.active:
                self._omni_tx.disable()  # → omni_stopped("easter_egg_off") → _on_omni_stopped
            # R1-Fix: 5s UI-Cooldown abbrechen wenn Button versteckt wird —
            # sonst inkonsistenter Button-State bei naechster Easter-Egg-Aktivierung
            if self._auto_hunt_cooldown_timer.isActive():
                self._auto_hunt_cooldown_timer.stop()
                self.control_panel.btn_auto_hunt.setEnabled(True)
                self.control_panel.btn_auto_hunt.setText("AUTO HUNT")
                self._auto_hunt_cooldown_seconds = 0
        self._update_button_visibility()
        print(f"[Easter-Egg] Override {'aktiv' if self._easter_egg_active else 'inaktiv'}")
        self._update_statusbar()

    # ── Mode-Coupling Buttons (v0.78) ────────────────────────────

    def _update_button_visibility(self):
        """3-Button-Layout mode-abhaengig + Easter-Egg-Override.

        Plan v0.78:
        - RX-Mode "normal":     nur btn_cq sichtbar
        - RX-Mode "diversity":  btn_omni_cq + btn_auto_hunt sichtbar, btn_cq versteckt
        - Easter-Egg-Override:  in "normal" zusaetzlich alle Power-User-Buttons sichtbar

        Wird gerufen nach Init, RX-Mode-Wechsel und Easter-Egg-Toggle.
        """
        rx_mode = getattr(self, "_rx_mode", "normal")
        is_diversity = (rx_mode == "diversity")
        show_power_buttons = is_diversity or self._easter_egg_active
        self.control_panel.btn_omni_cq.setHidden(not show_power_buttons)
        self.control_panel.btn_auto_hunt.setHidden(not show_power_buttons)
        # btn_cq: in Diversity unsichtbar, sonst sichtbar
        self.control_panel.btn_cq.setHidden(is_diversity)

    # ── OMNI-TX UI-Lifecycle (v0.78) ─────────────────────────────

    def _on_btn_omni_cq_toggled(self, checked: bool):
        """User-Klick auf btn_omni_cq: enable + start CQ-Loop / stop CQ-Loop.

        P1.OMNI-START (v0.95.22): Aktiviert ZUSAETZLICH den CQ-Loop in qso_state,
        sonst greift OMNI-Slot-Filter nie. Mutually-exclusive: laufender Auto-Hunt
        wird via "superseded" gestoppt.

        Bei aktivem QSO (state nicht in IDLE/CQ_WAIT, also QSO laeuft):
        Toggle blockieren mit Statusbar-Hinweis. Sonst haette Mike einen
        aktivierten Button ohne Wirkung (start_cq macht silent no-op).
        """
        if checked and not self._omni_tx.active:
            # P1.OMNI-START: nur wenn kein QSO laeuft. start_cq() selbst akzeptiert
            # state in (IDLE, CQ_WAIT). Konsistent dazu blockieren wir alle anderen.
            if self.qso_sm.state not in (QSOState.IDLE, QSOState.CQ_WAIT):
                btn = self.control_panel.btn_omni_cq
                btn.blockSignals(True)
                btn.setChecked(False)
                btn.blockSignals(False)
                self.statusBar().showMessage(
                    "OMNI-CQ nur startbar wenn kein aktives QSO laeuft "
                    "— erst laufendes QSO beenden",
                    4000,
                )
                return
            if self._auto_hunt.active:
                self._auto_hunt.stop_auto_hunt("superseded")
            # P2.OMNI-REDESIGN v4.0 (v0.95.23): start_with_parity_for_next_slot
            # statt enable() — „kein Slot verschwenden": next_is_even → Block 1,
            # sonst Block 2 (Mike's Designentscheidung 09.05.2026).
            next_is_even = not self.timer.is_even_cycle()
            self._omni_tx.start_with_parity_for_next_slot(next_is_even)
            # P1.OMNI-START: CQ-Loop in qso_state aktivieren —
            # OMNI-Filter in _on_send_message greift erst wenn jemand
            # send_message("CQ ...") emittet. start_cq() macht genau das.
            self.qso_sm.start_cq()
            self.control_panel.update_omni_tx(True)
            self._update_statusbar()
            print(f"[OMNI-TX] User-Start (next_is_even={next_is_even})")
        elif not checked and self._omni_tx.active:
            self._omni_tx.stop_omni_tx("manual_halt")

    def _on_omni_stopped(self, reason: str):
        """Slot fuer omni_stopped(reason): Button-State + Statusbar zuruecksetzen.

        P1.OMNI-START (v0.95.22): ALLE Stop-Reasons stoppen den CQ-Loop in
        qso_state — sonst bleibt cq_mode=True haengen waehrend OMNI nicht
        mehr lauft. Plus _was_cq=False (R1-SOLLTE): bei Stop-while-QSO soll
        nach QSO-Ende KEIN regulaeres CQ resumen — Mike hat OMNI bewusst
        gestoppt.

        Im Gegensatz zu Auto-Hunt KEIN UI-Reflexions-Cooldown — OMNI ist passiver,
        kein Bot-Tarn-Schutz noetig.
        """
        btn = self.control_panel.btn_omni_cq
        btn.blockSignals(True)
        btn.setChecked(False)
        btn.blockSignals(False)
        # P1.OMNI-START: CQ-Loop stoppen (idempotent — stop_cq macht nix wenn cq_mode=False)
        if self.qso_sm.cq_mode:
            self.qso_sm.stop_cq()
        # P1.OMNI-START R1-SOLLTE: bei Stop-while-QSO _was_cq invalidieren
        # damit _resume_cq_if_needed nach QSO-Ende kein regulaeres CQ startet.
        self.qso_sm._was_cq = False
        # P2.OMNI-REDESIGN v4.0 (v0.95.23): Pre-QSO-Flag invalidieren —
        # bei Stop wahrend QSO soll _maybe_resume_omni nach QSO-Ende
        # KEIN OMNI resumen (Mike hat OMNI bewusst gestoppt).
        self._omni_was_active_pre_qso = False
        # P2.OMNI-PATTERN-FIX (v0.95.24): Pretrigger-Flag reset, sonst
        # bleibt bei Re-Start (Toggle off→on) ein veralteter Trigger.
        self._omni_pretriggered = False
        # P3.OMNI-PATTERN-FIX-2 (v0.95.25): pending QTimer cancelen — alle
        # Stop-Reasons (manual_halt, ft_mode_change, band_change,
        # rx_mode_change, totmann_expired, easter_egg_off, superseded)
        # laufen ueber omni_stopped → dieser Slot. stop() ist idempotent.
        self._omni_pretrigger_timer.stop()
        self.control_panel.update_omni_tx(False)
        self._update_statusbar()
        print(f"[OMNI-TX-UI] Stop ({reason})")

    # ── Auto-Hunt UI-Lifecycle (v0.75) ───────────────────────────

    def _on_btn_auto_hunt_toggled(self, checked: bool):
        """User-Klick auf btn_auto_hunt: start/stop_auto_hunt.

        Mutually-exclusive: laufendes OMNI-TX wird via "superseded" gestoppt.
        """
        if checked and not self._auto_hunt.active:
            if self._omni_tx.active:
                self._omni_tx.stop_omni_tx("superseded")
            self._auto_hunt.start_auto_hunt(600)
            "normal": "Normal",
            "diversity": "DIVERSITY",
        }
        mode_str = mode_labels.get(self._rx_mode, "Normal")
        if getattr(self, '_omni_tx', None) and self._omni_tx.active:
            omni_str = (f"  Ω Even={self._omni_tx.cq_even_count} "
                        f"Odd={self._omni_tx.cq_odd_count}")
        else:
            omni_str = ""
        # DT-Korrektur Status — nur DT-Label gruen, Statusbar bleibt grau
        from core import ntp_time
        dt_phase = ntp_time._phase
        if ntp_time._correction == 0.0 and ntp_time._is_initial:
            dt_text, dt_color = "DT: —", "#888"
        elif dt_phase == "measure":
            dt_text, dt_color = "DT: Korrektur", "#00DD66"
                self.control_panel.set_cq_active(True)
                print("[Presence] CQ automatisch wieder aufgenommen")

    def _on_presence_tick(self):
        """Jede Sekunde: Countdown herunterzaehlen."""
        if self._presence_remaining > 0:
            self._presence_remaining -= 1

        self.control_panel.update_presence(self._presence_remaining)

        if self._presence_remaining <= 0 and not self._presence_expired:
            self._presence_expired = True
            print("[Presence] TIMEOUT — Operator nicht anwesend, CQ wird gestoppt")
            # Auto-Hunt sofort stoppen (Defense-in-Depth zur 10-Min-Hard-Cap).
            # Reason "totmann_expired": Cooldowns + _last_tx_even bleiben,
            # damit User bei Wiederkehr explizit fortsetzen kann (Pflicht-Restart).
            if self._auto_hunt.active:
                self._auto_hunt.stop_auto_hunt("totmann_expired")
            # v0.78: OMNI-TX bei Totmann-Expire stoppen (analog Auto-Hunt)
            if self._omni_tx.active:
                self._omni_tx.stop_omni_tx("totmann_expired")
            # CQ stoppen (aber laufendes QSO zu Ende fuehren!)
            if self.qso_sm.cq_mode:
                # Nur CQ stoppen wenn KEIN aktives QSO laeuft
                if self.qso_sm.state in (QSOState.CQ_CALLING, QSOState.CQ_WAIT,
                                          QSOState.IDLE, QSOState.TIMEOUT):
                    self.qso_sm.stop_cq()
                    self.control_panel.set_cq_active(False)
                    self.qso_panel.add_info(
                        "Operator Presence abgelaufen — CQ gestoppt. "
                        "Maus bewegen oder Taste druecken zum Fortsetzen."
```
