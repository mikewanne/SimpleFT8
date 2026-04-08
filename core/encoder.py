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

    def encode_message(self, message: str) -> np.ndarray | None:
        """FT8-Nachricht in Audio-Signal umwandeln (12kHz int16)."""
        try:
            parts = message.strip().split()
            if len(parts) != 3:
                self.encoding_error.emit(f"Ungueltige Nachricht: {message}")
                return None

            audio = get_ft8lib().encode(message.strip(), freq_hz=float(self.audio_freq_hz))
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

    def _tx_worker_inner(self, message: str):
        # FESTE TX-Frequenz — NICHT bei jedem TX ändern!
        # Bug: find_free_frequency() wechselt die Frequenz zwischen CQ und Report.
        # DK0KG wartet auf CQ-Frequenz; Report kommt auf anderer Freq → unsichtbar.
        tx_freq = self.audio_freq_hz
        print(f"[TX] Frequenz: {tx_freq} Hz → '{message}'")

        # Audio erzeugen (12kHz int16)
        audio_12k = self.encode_message(message)
        if audio_12k is None:
            return

        # Trailing Silence trimmen: TX muss mindestens 0.4s VOR dem naechsten Slot enden.
        # ft8s_encode erzeugt 180000 Samples (15.0s); mit 0.2s Start-Delay + 0.1s PTT-Settle
        # wuerde TX bei slot+15.3s enden = 0.3s IN den naechsten Slot → ICOM-RX geblockt.
        # Loesung: letzte 0.7s (8400 Samples) abschneiden (das ist trailing silence).
        # Ergebnis: PTT-off bei slot+0.2+0.1+14.3 = slot+14.6s → 0.4s Puffer fuer T/R-Switching.
        TRIM_SAMPLES = int(0.7 * SAMPLE_RATE_FT8)   # 8400 @ 12kHz
        if len(audio_12k) > TRIM_SAMPLES:
            audio_12k = audio_12k[:-TRIM_SAMPLES]

        # Warte auf richtigen Zyklusbeginn (Even/Odd Slot)
        now = time.time()
        cycle_pos = now % 15.0
        cycle_num = int(now / 15.0)
        is_even = cycle_num % 2 == 0

        if self.tx_even is not None:
            # Bestimmter Slot gefordert (Hunt: Gegenteil der Gegenstation)
            want_even = self.tx_even
            if is_even == want_even and cycle_pos <= 1.0:
                # Richtig — am Anfang des gewünschten Slots
                time.sleep(max(0, 0.2 - cycle_pos))
            else:
                # Warten bis zum nächsten passenden Slot
                wait = 15.0 - cycle_pos  # bis nächste Grenze
                next_even = (cycle_num + 1) % 2 == 0
                if next_even != want_even:
                    wait += 15.0  # einen Slot überspringen
                wait += 0.2
                print(f"[TX] Slot-Korrektur: warte {wait:.1f}s auf {'EVEN' if want_even else 'ODD'}")
                time.sleep(wait)
        else:
            # Kein Slot-Vorgabe (CQ: nächster Slot)
            if cycle_pos > 1.0:
                wait = 15.0 - cycle_pos + 0.2
                time.sleep(wait)
            elif cycle_pos < 0.2:
                time.sleep(0.2 - cycle_pos)

        # PTT an — mit Timing-Log
        tx_time = time.time()
        tx_cycle = int(tx_time / 15.0)
        tx_slot = "EVEN" if tx_cycle % 2 == 0 else "ODD"
        utc = time.strftime("%H:%M:%S", time.gmtime(tx_time))
        print(f"[TX] {utc} Slot={tx_slot} Freq={self.audio_freq_hz}Hz → '{message}'")

        if self._radio:
            self._radio.ptt_on()
            time.sleep(0.1)

        self.tx_started.emit(message)

        # Audio via VITA-49 senden (radio.send_audio macht Resampling + Pacing)
        if self._radio:
            self._radio.send_audio(audio_12k, sample_rate=SAMPLE_RATE_FT8)

        # PTT aus (kein extra Sleep — trailing silence im Audio gibt genug Puffer)
        if self._radio:
            self._radio.ptt_off()

        self.tx_finished.emit()
