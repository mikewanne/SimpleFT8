"""SimpleFT8 Decoder — FT8-Dekodierung via libft8simple.dylib (C, MIT).

Pipeline:
  VITA-49 Audio (24kHz)
    → Anti-Alias Tiefpass + Resample auf 12kHz
    → RMS Auto-Gain Control (-12 dBFS Ziel, ±3 dB Hysterese)
    → DC-Remove
    → Spectral Whitening (Overlap-Add FFT, Median)
    → Normalisierung (-18 dBFS RMS)
    → Fenster-Sliding (0 / +0.3s / -0.3s)
    → ft8s_decode() C-Bibliothek (Costas-Sync → LDPC 50it → CRC)
    → Signal Subtraction (bis MAX_SUBTRACT_PASSES Passes)
    → Ergebnis-Fusion + Deduplizierung
"""

import time
import threading
import numpy as np
from collections import deque
from PySide6.QtCore import QObject, Signal

from .ft8lib_decoder import get_ft8lib
from .message import FT8Message, parse_ft8_message


# ── Konstanten ────────────────────────────────────────────────────────────────

SAMP_RATE = 12000                         # ft8_lib Eingabe-Samplerate
CYCLE_SAMPLES_12K = int(15 * SAMP_RATE)   # 180 000 Samples pro 15s Slot

# Signal Subtraction — wird per set_quality() angepasst
MAX_SUBTRACT_PASSES = 5
SUBTRACT_MIN_SNR = -18

# Fenster-Sliding: Offsets in Samples (±0.3s @ 12kHz = ±3600 Samples)
SLIDE_OFFSETS = [0, 3600, -3600]

# Maximale Kandidaten pro Pass (fuer Logging)
MAX_CANDIDATES = 200

# ── RMS Auto-Gain Control ─────────────────────────────────────────────────────

# Ziel: -12 dBFS RMS  (= 0.251 float = 8225 bei int16 full-scale)
_AGC_TARGET_INT16: float = 8225.0
_AGC_ALPHA:        float = 0.02    # EMA-Glättung (langsam = kein Pumpen)
_AGC_HYSTERESIS:   float = 3.0    # ±3 dB Totband → keine Anpassung bei kleinen Schwankungen
_AGC_MAX_GAIN:     float = 4.0    # +12 dB maximal (Rausch-Grenze)
_AGC_MIN_GAIN:     float = 0.1    # -20 dB minimal (kein komplettes Abwürgen)


def _apply_agc(
    audio_int16: np.ndarray,
    gain_state: tuple,
) -> tuple[np.ndarray, tuple]:
    """RMS-basierter Auto-Gain-Control für FT8 Audio-Eingang.

    Platzierung: nach 12kHz Resample, VOR Spectral Whitening.
    Verhindert Übersteuerung des Decoders bei starken Signalsummen (40m abends).

    Args:
        audio_int16: 1D int16 Array @ 12kHz
        gain_state: (current_gain, ema_gain) — aus letztem Zyklus

    Returns:
        (audio_int16_processed, new_gain_state)
    """
    current_gain, ema_gain = gain_state

    audio_f = audio_int16.astype(np.float32)
    rms = float(np.sqrt(np.mean(audio_f ** 2)))
    rms = max(rms, 1.0)  # Stille nicht verstärken

    desired_gain = _AGC_TARGET_INT16 / rms

    # Hysterese: Gain nur anpassen wenn Abweichung > ±3 dB
    hyst = 10.0 ** (_AGC_HYSTERESIS / 20.0)  # ≈ 1.413
    ratio = desired_gain / ema_gain
    if 1.0 / hyst <= ratio <= hyst:
        desired_gain = ema_gain  # Im Totband — nicht ändern

    # EMA-Glättung des Gain-Faktors (verhindert Pumpen)
    ema_gain = _AGC_ALPHA * desired_gain + (1.0 - _AGC_ALPHA) * ema_gain
    ema_gain = float(np.clip(ema_gain, _AGC_MIN_GAIN, _AGC_MAX_GAIN))
    current_gain = ema_gain

    audio_out = np.clip(audio_f * current_gain, -32767, 32767).astype(np.int16)
    return audio_out, (current_gain, ema_gain)


class Decoder(QObject):
    """FT8 Decoder mit Signal Subtraction und Fenster-Sliding.

    Signals:
        message_decoded: (FT8Message) — einzelne dekodierte Nachricht
        cycle_decoded:   (list[FT8Message]) — alle Nachrichten eines Zyklus
    """

    message_decoded = Signal(object)
    cycle_decoded = Signal(list)

    def __init__(self, max_freq: int = 3000, my_call: str = "DA1MHH"):
        super().__init__()
        self.max_freq = max_freq
        self.my_call = my_call
        self._running = False
        self._audio_buffer_24k = []
        self._buffer_lock = threading.Lock()
        self._decode_thread = None
        self.recent_calls: deque = deque(maxlen=200)
        self.occupied_freqs = []
        self.input_sample_rate = 24000
        self.priority_call: str = ""   # QSO-Partner fuer Prioritaets-Logging
        self.last_pcm_12k: np.ndarray | None = None  # AP-Lite: letzter 12kHz float32 Buffer
        self._agc_state: tuple = (1.0, 1.0)           # RMS-AGC: (current_gain, ema_gain)
        self._startup_samples: int = 0                 # Startup-Purge: erste 2s verwerfen
        self._startup_done: bool = False

    def start(self):
        self._running = True
        self._decode_thread = threading.Thread(
            target=self._decode_loop, daemon=True
        )
        self._decode_thread.start()

    def stop(self):
        self._running = False

    def set_quality(self, mode: str):
        """Decode-Qualitaet anpassen: 'normal' = schnell, 'diversity' = tief."""
        global MAX_SUBTRACT_PASSES, MAX_CANDIDATES
        if mode == "normal":
            MAX_SUBTRACT_PASSES = 3
            MAX_CANDIDATES = 200
            print("[Decoder] Qualitaet: NORMAL (3 Passes, ft8lib C)")
        else:
            MAX_SUBTRACT_PASSES = 5
            MAX_CANDIDATES = 200
            print("[Decoder] Qualitaet: DIVERSITY (5 Passes, ft8lib C)")

    def feed_audio(self, samples_int16: np.ndarray):
        # Startup-Purge: erste 2s Audio verwerfen (Verbindungs-Müll)
        if not self._startup_done:
            self._startup_samples += len(samples_int16)
            if self._startup_samples < 48000:  # 2s @ 24kHz
                return
            self._startup_done = True
            print(f"[Decoder] Startup-Purge: {self._startup_samples} Samples verworfen")
        with self._buffer_lock:
            self._audio_buffer_24k.append(samples_int16.copy())

    # ── Scheduling Loop ───────────────────────────────────────────────────────

    def _decode_loop(self):
        """Wacht auf 13.5s in jedem Slot, startet dann den Decode-Thread."""
        self._decode_busy = False
        self._decode_busy_lock = threading.Lock()

        while self._running:
            try:
                now = time.time()
                cycle_pos = now % 15.0
                # 13.5: Standard-Aufwachzeit. DT-Korrektur regelt den Rest via Buffer-Shift.
                _WAKE_TIME = 13.5
                if cycle_pos < _WAKE_TIME:
                    wait = _WAKE_TIME - cycle_pos
                else:
                    wait = 15.0 - cycle_pos + _WAKE_TIME
                time.sleep(wait)

                with self._decode_busy_lock:
                    if self._decode_busy:
                        print(f"[Decoder] Skip Zyklus {int(time.time()/15)}: vorheriger Decode laeuft noch")
                        continue
                    self._decode_busy = True

                with self._buffer_lock:
                    chunks = self._audio_buffer_24k
                    self._audio_buffer_24k = []

                if not chunks:
                    print(f"[Decoder] Zyklus {int(time.time()/15)}: kein Audio")
                    with self._decode_busy_lock:
                        self._decode_busy = False
                    continue

                threading.Thread(
                    target=self._process_cycle,
                    args=(chunks,),
                    daemon=True,
                ).start()

            except Exception as e:
                import traceback
                print(f"[Decoder] FEHLER Scheduling: {e}")
                traceback.print_exc()
                with self._decode_busy_lock:
                    self._decode_busy = False

    # ── Cycle Processing ──────────────────────────────────────────────────────

    def _process_cycle(self, chunks):
        """Preprocessing + Decode in eigenem Thread."""
        t_start = time.time()
        try:
            audio_raw = np.concatenate(chunks)
            peak_raw = np.max(np.abs(audio_raw))
            noise_pre = np.median(np.abs(audio_raw.astype(np.float32)))
            print(f"[Decoder] Zyklus: {len(audio_raw)} Samples, Peak={peak_raw}, NoiseFloor={noise_pre:.0f}")

            # Noise-Floor-basierte Normalisierung
            audio_f = audio_raw.astype(np.float32)
            noise_floor = np.median(np.abs(audio_f))
            if noise_floor > 1.0:
                target_noise = 300.0
                audio_raw = np.clip(
                    audio_f * (target_noise / noise_floor), -32767, 32767
                ).astype(np.int16)

            # Anti-Alias Resampling 24k → 12k
            audio_12k = _resample_to_12k(audio_raw, source_rate=24000)

            if len(audio_12k) > CYCLE_SAMPLES_12K:
                audio_12k = audio_12k[-CYCLE_SAMPLES_12K:]
            elif len(audio_12k) < CYCLE_SAMPLES_12K // 2:
                print(f"[Decoder] Zu wenig Audio: {len(audio_12k)} < {CYCLE_SAMPLES_12K // 2}")
                return
            else:
                audio_12k = np.pad(
                    audio_12k, (0, max(0, CYCLE_SAMPLES_12K - len(audio_12k)))
                )

            # DT-Korrektur: Audio-Buffer verschieben (nicht Sleep-Zeit!)
            # Positive Korrektur = Signale zu spät im Buffer → vorne abschneiden
            from core import ntp_time
            _dt_shift = ntp_time.get_correction()
            _shift_samples = int(_dt_shift * SAMP_RATE)
            if abs(_shift_samples) > 100 and abs(_shift_samples) < CYCLE_SAMPLES_12K // 3:
                if _shift_samples > 0:
                    # Signal kommt zu spät → vorne abschneiden, hinten padden
                    audio_12k = np.pad(audio_12k[_shift_samples:], (0, _shift_samples))
                else:
                    # Signal kommt zu früh → hinten abschneiden, vorne padden
                    audio_12k = np.pad(audio_12k[:_shift_samples], (-_shift_samples, 0))

            # RMS Auto-Gain Control — DEAKTIVIERT
            # audio_12k, self._agc_state = _apply_agc(audio_12k, self._agc_state)

            t_pre = time.time()
            audio_12k = _preprocess_audio(audio_12k)
            t_decode = time.time()
            peak_12k = np.max(np.abs(audio_12k))
            print(f"[Decoder] Preprocessing: {t_decode - t_pre:.2f}s, Peak={peak_12k}")

            # AP-Lite: verarbeiteten Buffer merken (float32, normalisiert)
            self.last_pcm_12k = audio_12k.astype(np.float32) / 32767.0

            messages = self._decode_with_subtraction(audio_12k)
            t_done = time.time()

            print(f"[Decoder] {len(messages)} Stationen — Gesamt: {t_done - t_start:.2f}s "
                  f"(Pre: {t_decode - t_pre:.2f}s, Decode: {t_done - t_decode:.2f}s)")

            if messages:
                self.cycle_decoded.emit(messages)
                for msg in messages:
                    is_to_me = self.my_call and msg.target == self.my_call
                    is_partner = (self.priority_call and
                                  msg.caller == self.priority_call)
                    if is_to_me or is_partner:
                        _now = time.time()
                        _slot = "EVEN" if int(_now / 15.0) % 2 == 0 else "ODD"
                        _utc = time.strftime("%H:%M:%S", time.gmtime(_now))
                        tag = ">>> AN UNS" if is_to_me else "QSO-Partner"
                        print(f"[RX] {_utc} Slot={_slot} | {msg.raw} | snr={msg.snr} freq={msg.freq_hz} [{tag}]")
                    self.message_decoded.emit(msg)
            else:
                self.cycle_decoded.emit([])

        except Exception as e:
            import traceback
            print(f"[Decoder] FEHLER Decode-Thread: {e}")
            traceback.print_exc()
        finally:
            with self._decode_busy_lock:
                self._decode_busy = False

    # ── Multi-Pass Signal Subtraction ─────────────────────────────────────────

    def _decode_with_subtraction(self, audio_12k: np.ndarray) -> list[FT8Message]:
        """Multi-Pass Decode: Dekodieren → Signal subtrahieren → nochmal."""
        lib = get_ft8lib()
        all_messages: list[FT8Message] = []
        seen: set[str] = set()
        audio_work = audio_12k.astype(np.float32)

        for pass_num in range(MAX_SUBTRACT_PASSES):
            # ── Decode mit Fenster-Sliding ─────────────────────────────────
            raw_results: list[dict] = []

            for offset_samples in SLIDE_OFFSETS:
                shifted = _apply_offset(audio_work, offset_samples)
                results = lib.decode(
                    shifted.astype(np.int16),
                    max_freq_hz=float(self.max_freq),
                    num_passes=1,          # 1 C-Pass, Python verwaltet Passes
                    max_results=MAX_CANDIDATES,
                )
                for r in results:
                    key = " ".join(r["message"].split())
                    if key and key not in seen:
                        # dt korrigieren:
                        # 1) Offset-Verschiebung rueckgaengig machen (Window-Sliding)
                        # 2) Buffer-Offset: Decode-Loop wacht bei 13.5s in Slot auf →
                        #    Buffer startet 1.5s VOR Slot-Start → alle DT um +1.5 zu hoch
                        DT_BUFFER_OFFSET = 1.5  # 15.0 - _WAKE_TIME (13.5)
                        raw_results.append({
                            **r,
                            "dt": r["dt"] + offset_samples / SAMP_RATE - DT_BUFFER_OFFSET,
                            "freq_hz": r["freq_hz"],
                        })

            if not raw_results:
                break

            # Deduplizieren (erste Occurrence = beste Timing-Schaetzung behalten)
            new_msgs: list[tuple[FT8Message, dict]] = []
            for r in raw_results:
                key = " ".join(r["message"].split())
                if key not in seen:
                    seen.add(key)
                    msg = parse_ft8_message(
                        r["message"],
                        snr=r["snr"],
                        freq_hz=int(r["freq_hz"]),
                        dt=r["dt"],
                    )
                    new_msgs.append((msg, r))

            if not new_msgs:
                break

            all_messages.extend(msg for msg, _ in new_msgs)

            if pass_num >= MAX_SUBTRACT_PASSES - 1:
                break

            # ── Signal Subtraction ─────────────────────────────────────────
            subtracted = 0
            for msg, r in new_msgs:
                if r["snr"] >= SUBTRACT_MIN_SNR:
                    reconstructed = _reconstruct_signal(
                        r["message"], r["freq_hz"], r["dt"]
                    )
                    if reconstructed is not None:
                        offset = max(0, int((r["dt"] + 0.5) * SAMP_RATE))
                        end = min(len(audio_work), offset + len(reconstructed))
                        rlen = end - offset
                        if rlen > 0:
                            audio_work[offset:end] -= reconstructed[:rlen]
                            subtracted += 1

            if subtracted == 0:
                break

        # ── Drift-Kompensation: Extra-Passes mit linearer Frequenzkorrektur ────
        # Billige QRP-Stationen driften 0.5-5 Hz ueber 15s.
        # Wir probieren verschiedene Drift-Raten auf dem Residual-Audio.
        from .drift import generate_drift_variants
        drift_new = 0
        for drift_rate, drift_audio in generate_drift_variants(audio_work.astype(np.int16)):
            drift_results = lib.decode(
                drift_audio,
                max_freq_hz=float(self.max_freq),
                num_passes=1,
                max_results=MAX_CANDIDATES,
            )
            for r in drift_results:
                key = " ".join(r["message"].split())
                if key and key not in seen:
                    seen.add(key)
                    DT_BUFFER_OFFSET = 1.5
                    msg = parse_ft8_message(
                        r["message"],
                        snr=r["snr"],
                        freq_hz=int(r["freq_hz"]),
                        dt=r["dt"] - DT_BUFFER_OFFSET,
                    )
                    all_messages.append(msg)
                    drift_new += 1
        if drift_new:
            print(f"[Drift] +{drift_new} Stationen durch Drift-Kompensation")

        # Frequenzen und Calls tracken
        occupied = []
        for msg in all_messages:
            occupied.append(msg.freq_hz)
            if msg.caller and msg.caller not in self.recent_calls:
                self.recent_calls.appendleft(msg.caller)
            if msg.target and msg.target not in self.recent_calls:
                self.recent_calls.appendleft(msg.target)
        self.occupied_freqs = sorted(occupied)

        return all_messages


# ── Signal Subtraction: Rekonstruktion ───────────────────────────────────────

def _reconstruct_signal(message_str: str, freq_hz: float,
                         dt: float) -> np.ndarray | None:
    """FT8-Signal aus Nachrichtentext rekonstruieren (fuer Subtraktion)."""
    parts = message_str.strip().split()
    if len(parts) != 3:
        return None
    try:
        audio = get_ft8lib().encode(message_str.strip(), freq_hz=float(freq_hz))
        return audio.astype(np.float32) if audio is not None else None
    except Exception:
        return None


# ── Fenster-Sliding Hilfsfunktion ────────────────────────────────────────────

def _apply_offset(audio: np.ndarray, offset_samples: int) -> np.ndarray:
    """Audio um offset_samples verschieben (positive = vorne abschneiden)."""
    if offset_samples > 0:
        return np.pad(audio[offset_samples:], (0, offset_samples))
    elif offset_samples < 0:
        return np.pad(audio[:offset_samples], (-offset_samples, 0))
    return audio


# ── Audio-Vorverarbeitung ─────────────────────────────────────────────────────

def _preprocess_audio(audio_int16: np.ndarray) -> np.ndarray:
    """DC-Remove, Spectral Whitening, Normalisierung."""
    audio = audio_int16.astype(np.float32)

    # 1. DC-Offset entfernen
    audio -= np.mean(audio)

    # 2. Spectral Whitening (Overlap-Add, gleitender Median pro FFT-Frame)
    n_fft = 2048
    hop_size = n_fft // 2
    n_frames = (len(audio) - n_fft) // hop_size
    if n_frames > 0:
        from numpy.lib.stride_tricks import sliding_window_view
        window = np.hanning(n_fft).astype(np.float32)
        kernel = 31
        pad_k = kernel // 2

        all_frames = sliding_window_view(audio, n_fft)[::hop_size][:n_frames] * window
        all_spectra = np.fft.rfft(all_frames, axis=1)
        all_magnitudes = np.abs(all_spectra)

        mag_padded = np.pad(all_magnitudes, ((0, 0), (pad_k, pad_k)), mode="reflect")
        freq_windows = sliding_window_view(mag_padded, kernel, axis=1)
        noise_floor_all = np.median(freq_windows, axis=2)
        noise_floor_all = np.maximum(noise_floor_all, 1e-6)

        whitened_all = all_spectra * np.minimum(1.0 / noise_floor_all, 100.0)
        frames_out = np.fft.irfft(whitened_all, n=n_fft, axis=1) * window

        output = np.zeros_like(audio)
        weights = np.zeros_like(audio)
        frame_starts = np.arange(n_frames) * hop_size
        indices = (frame_starts[:, None] + np.arange(n_fft)[None, :]).ravel()
        np.add.at(output, indices, frames_out.ravel())
        np.add.at(weights, indices, np.tile(window ** 2, n_frames))

        weights = np.maximum(weights, 1e-6)
        audio = output / weights

    # 3. RMS-Normalisierung auf -18 dBFS
    rms = np.sqrt(np.mean(audio ** 2))
    if rms > 1e-6:
        target_rms = 32767 * 10 ** (-18 / 20)
        audio = audio * (target_rms / rms)

    return np.clip(audio, -32767, 32767).astype(np.int16)


# ── Resampling mit Anti-Alias-Filter ─────────────────────────────────────────

def _resample_to_12k(audio: np.ndarray, source_rate: int) -> np.ndarray:
    """Resample von source_rate auf 12kHz mit Anti-Alias-Tiefpass."""
    if source_rate == 12000:
        return audio

    ratio = source_rate // 12000
    audio_f = audio.astype(np.float32)

    n_taps = 63
    n = np.arange(n_taps) - (n_taps - 1) / 2
    fc = 6000.0 / source_rate
    with np.errstate(divide="ignore", invalid="ignore"):
        h = np.where(n == 0, 2 * fc, np.sin(2 * np.pi * fc * n) / (np.pi * n))
    h *= np.hamming(n_taps)
    h = (h / np.sum(h)).astype(np.float32)

    filtered = np.convolve(audio_f, h, mode="same")
    return filtered[::ratio].astype(audio.dtype)
