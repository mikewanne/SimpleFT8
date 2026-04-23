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
        tx_started: (str) — TX begonnen
        tx_finished: () — TX abgeschlossen
        encoding_error: (str) — Fehler
    """

    tx_started = Signal(str)
    tx_finished = Signal()
    encoding_error = Signal(str)

    def __init__(self, audio_freq_hz: int = 1000):
        super().__init__()
        self.audio_freq_hz = audio_freq_hz
        self._radio = None
        self._decoder = None
        self._tx_thread = None
        self._is_transmitting = False
        self.tx_even = None  # None=nächster Slot, True=even, False=odd
        self._mode = "FT8"  # "FT8", "FT4", "FT2"

    def set_protocol(self, mode: str):
        """Protokoll wechseln."""
        self._mode = mode
        print(f"[Encoder] Protokoll: {mode}")

    @property
    def is_transmitting(self) -> bool:
        return self._is_transmitting

    def abort(self):
        """TX sofort abbrechen (Bandwechsel, Notaus)."""
        self._is_transmitting = False
        print("[Encoder] TX abgebrochen")

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

    def transmit(self, message: str):
        """FT8-Nachricht encoden und zum naechsten Zyklusbeginn senden."""
        if self._is_transmitting:
            print(f"[TX] SKIP (TX aktiv): '{message}'")
            return
        self._tx_thread = threading.Thread(
            target=self._tx_worker, args=(message,), daemon=True
        )
        self._tx_thread.start()

    def _tx_worker(self, message: str):
        """TX-Worker: Timing → PTT → Audio via VITA-49 → PTT off."""
        self._is_transmitting = True
        try:
            self._tx_worker_inner(message)
        finally:
            self._is_transmitting = False

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
            if is_even == want_even and cycle_pos < (_SLOT / 5):
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

        # 1. Audio SOFORT codieren — unabhaengig vom Timing, kein GIL-Problem
        audio_12k = self.encode_message(message)
        if audio_12k is None:
            return

        # Trailing Silence trimmen (FT8-Nutzsignal ist 12.64s, Rest ist stille)
        # slot+0.5 + 13.5s = slot+14.0s → 1.0s Puffer vor naechstem Slot
        if len(audio_12k) > TRIM_SAMPLES:
            audio_12k = audio_12k[:-TRIM_SAMPLES]

        # 2. Naechste passende Slot-Grenze berechnen
        next_boundary = self._next_slot_boundary()

        # 3. Bis zur Slot-Grenze schlafen (TARGET_TX_OFFSET=0.5 → sleep bis boundary,
        #    dann 0.5s Silence → TX startet bei boundary+0.5s = WSJT-X Protokoll)
        sleep_dur = (next_boundary + TARGET_TX_OFFSET - 0.5) - time.time()
        if sleep_dur > 0.001:
            time.sleep(sleep_dur)

        # Abort-Check: wurde TX während des Schlafs abgebrochen?
        if not self._is_transmitting:
            print("[Encoder] TX abgebrochen (während Warte-Phase)")
            return

        # 4. Silence-Padding berechnen (jetzt praezise, da nahe am Ziel)
        #    Stille absorbiert den restlichen Jitter des OS-Schedulers
        now = time.time()
        # TX-Timing: NUR der feste WSJT-X Protokoll-Offset (TARGET_TX_OFFSET=0.5s).
        # KEINE ntp_time Korrektur hier — die gilt nur fuer RX Audio-Buffer-Shift.
        silence_secs = max(0.0, (next_boundary + TARGET_TX_OFFSET) - now)

        # Kaltstart-Guard: nur springen wenn weit daneben (>5s), sonst sofort senden
        # Bei CQ-Resends ist silence≈0 normal (on_cycle_end feuert am Slot-Rand)
        if silence_secs < 0.1:
            overshoot = now - (next_boundary + TARGET_TX_OFFSET)
            if overshoot > 5.0:
                # Wirklich verschlafen (Kaltstart) → naechsten Slot nehmen
                _SLOT = {"FT8": 15.0, "FT4": 7.5, "FT2": 3.8}.get(self._mode, 15.0)
                next_boundary += (2 * _SLOT) if self.tx_even is not None else _SLOT
                silence_secs = max(0.0, (next_boundary + TARGET_TX_OFFSET) - time.time())
                print(f"[TX] Kaltstart-Guard: {overshoot:.1f}s daneben → Slot {next_boundary:.1f}")
            else:
                # Normaler CQ-Resend am Slot-Rand → sofort senden
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
            self._radio.ptt_on()

        self.tx_started.emit(message)

        # 7. Stream: FlexRadio Hardware-Clock uebernimmt das Pacing
        #    t_start = jetzt → jedes Paket bei t_start + n*5.33ms (absolut, kein Drift)
        if self._radio:
            self._radio.send_audio(audio_full, sample_rate=SAMPLE_RATE_FT8)

        # 8. PTT aus
        if self._radio:
            self._radio.ptt_off()

        self.tx_finished.emit()
