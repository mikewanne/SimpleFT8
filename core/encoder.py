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
        self.audio_freq_hz = audio_freq_hz
        self._radio = None
        self._decoder = None
        self._tx_thread = None
        self._is_transmitting = False
        # tx_even: None=nächster Slot, True=even, False=odd.
        # Wird vor jedem TX gesetzt — CQ-Pfad in _on_send_message,
        # Hunt-Pfad in _on_station_clicked, Reply-Pfad in
        # _on_tx_slot_for_partner, Replace-Pfad in
        # _on_try_replace_pending_tx. Letzter Setter gewinnt — das ist
        # Design-bedingt, jeder Pfad setzt für seinen TX die korrekte
        # Parität. Auto-Hunt nutzt _on_station_clicked indirekt.
        self.tx_even = None
        self._mode = "FT8"  # "FT8", "FT4", "FT2"
        # v0.80 Fix A2: cancelable sleep. abort() weckt _tx_worker_inner
        # aus dem Slot-Wait-Sleep auf — sonst schlaeft er bis zu 14s und
        # sendet veraltete Messages nach State-Change.
        self._abort_event = threading.Event()
        # P1.9 Fix (v0.95.3): Replace-Mechanik fuer CQ → Report im selben Slot.
        # _audio_started: True ab dem Moment wo send_audio gleich startet
        #                 (point-of-no-return — kein Replace mehr moeglich).
        # _replace_message: neue Message die request_replace() einreiht.
        # _replace_lock: schuetzt _audio_started + _replace_message gegen
        #                Race zwischen request_replace() und Worker-Wake.
        self._audio_started = False
        self._replace_message: str | None = None
        self._replace_lock = threading.Lock()

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
        """
        self._is_transmitting = False
        self._abort_event.set()
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

    def set_decoder(self, decoder):
        self._decoder = decoder

    def find_free_frequency(self) -> int:
        if not self._decoder or not self._decoder.occupied_freqs:
            return self.audio_freq_hz
        occupied = self._decoder.occupied_freqs
        for candidate in range(1500, 2700, 50):
            if all(abs(candidate - f) >= 100 for f in occupied):
                return candidate
        # Fallback: ab 800 Hz suchen wenn oben voll
        for candidate in range(800, 1500, 50):
            if all(abs(candidate - f) >= 100 for f in occupied):
                return candidate
        return self.audio_freq_hz

    def generate_reference_wave(self, msg: str, freq_hz: float,
                                sample_rate: int = 12000) -> np.ndarray | None:
        """FT8-Referenz-Welle für AP-Lite Korrelation (float32, normalisiert, 12kHz).

        Args:
            msg: FT8-Nachricht z.B. "DA1MHH DK5ON RR73"
            freq_hz: Audio-Frequenz des Signals (Hz)
            sample_rate: Ziel-Samplerate (Standard 12kHz)

        Returns:
            float32 Array [-1.0 .. +1.0], oder None bei Fehler.
        """
        try:
            audio_int16 = get_ft8lib().encode(msg.strip(), freq_hz=float(freq_hz))
            if audio_int16 is None:
                return None
            return audio_int16.astype(np.float32) / 32767.0
        except Exception:
            return None

    def encode_message(self, message: str) -> np.ndarray | None:
        """FT8-Nachricht in Audio-Signal umwandeln (12kHz int16)."""
        try:
            parts = message.strip().split()
            if len(parts) != 3:
                self.encoding_error.emit(f"Ungueltige Nachricht: {message}")
                return None

            audio = get_ft8lib().encode(message.strip(), freq_hz=float(self.audio_freq_hz),
                                       mode=self._mode)
            if audio is None:
                self.encoding_error.emit(f"Encoding fehlgeschlagen: {message}")
            return audio
        except Exception as e:
            self.encoding_error.emit(f"Encoder-Fehler: {e}")
            return None

    def transmit(self, message: str, *,
                 tx_even: bool | None = None,
                 audio_freq_hz: int | None = None) -> bool:
        """FT8-Nachricht encoden und zum naechsten Zyklusbeginn senden.

        Atomare API (P4.OMNI-NEUBAU C3): tx_even und audio_freq_hz werden
        UNTER Lock gesetzt, dann startet der Worker. Verhindert Race wenn
        zwei Aufrufer parallel transmit() rufen oder Setter und Start
        nicht atomar koppeln (Encoder-Worker liest tx_even in
        _next_slot_boundary).

        Returns True wenn Worker gestartet, False wenn TX bereits laeuft.
        Bestehende Aufrufer ohne kwargs (mw_qso._on_send_message) ignorieren
        das Return — Verhalten kompatibel.
        """
        # v0.80 Race-Fix (R1-Final-Review): alten TX-Thread sauber beenden,
        # bevor neuer startet. Sonst kann das finally des alten Threads
        # _is_transmitting=False setzen NACHDEM der neue Thread True gesetzt
        # hat → State desynchronisiert, weitere abort()-Aufrufe wirkungslos.
        if (self._tx_thread is not None
                and self._tx_thread.is_alive()
                and threading.current_thread() is not self._tx_thread):
            self._tx_thread.join(timeout=0.5)
        with self._replace_lock:
            if self._is_transmitting:
                return False
            if tx_even is not None:
                self.tx_even = tx_even
            if audio_freq_hz is not None:
                self.audio_freq_hz = audio_freq_hz
        self._tx_thread = threading.Thread(
            target=self._tx_worker, args=(message,), daemon=True
        )
        self._tx_thread.start()
        return True

    def _tx_worker(self, message: str):
        """TX-Worker: Timing → PTT → Audio via VITA-49 → PTT off.

        Single-Pass (P4.OMNI-NEUBAU C3): vorher gab es einen rekursiven
        Outer-Loop mit _pending_tx_message-Queue. OMNI verwendet jetzt
        seinen eigenen Worker (core/omni_cq.py) und braucht keine
        Encoder-Queue mehr. P1.9 Replace-Pfad bleibt im Inner.
        """
        self._is_transmitting = True
        # v0.80 Fix A2: Event vor jedem TX zuruecksetzen.
        self._abort_event.clear()
        # P1.9 Fix (v0.95.3): Replace-State pro TX-Zyklus zuruecksetzen.
        self._audio_started = False
        with self._replace_lock:
            self._replace_message = None
        try:
            self._tx_worker_inner(message)
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
