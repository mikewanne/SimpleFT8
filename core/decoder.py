"""SimpleFT8 Decoder — FT8-Dekodierung aus VITA-49 Audio-Stream.

Optimierungen:
- Spectral Whitening + DC-Remove (Prio 4)
- Signal Subtraction / Multi-Pass (Prio 1)
- Fenster-Sliding mit ±0.3s Offsets (Prio 5)
- Call-Tracking für AP-Hints (Prio 6)
- TX-Lücken-Tracking (Prio 8)
"""

import time
import threading
import numpy as np
from PySide6.QtCore import QObject, Signal

from PyFT8.receiver import (
    AudioIn, Candidate,
    SAMP_RATE, HPS, SYM_RATE, BPT,
    HOPS_PER_CYCLE, HOPS_PER_GRID,
    H0_RANGE, BASE_FREQ_IDXS, COSTAS,
)
from PyFT8.transmitter import pack_message, AudioOut
from PyFT8.time_utils import global_time_utils
from .osd_decoder import try_osd_decode
from .ap_decoder import try_ap_decode

# LDPC Tuning: Mehr Iterationen fuer schwache Signale (PyFT8 Default: 45, 12)
# 83 = mehr Kandidaten duerfen LDPC versuchen, 50 = mehr Iterationen
import PyFT8.receiver as _pyft8_rx
_pyft8_rx.LDPC_CONTROL = (83, 50)

from .message import FT8Message, parse_ft8_message


# FT8 Zyklus = 15s, bei 12kHz = 180000 Samples
CYCLE_SAMPLES_12K = int(15 * SAMP_RATE)  # 180000

# Signal Subtraction: mehr Passes = mehr schwache Signale unter starken finden
# WSJT-X: 3 Passes. Wir: 5 — iMac Pro hat genug CPU
MAX_SUBTRACT_PASSES = 5
# Nur subtrahieren wenn SNR mindestens so gut ist (dB)
SUBTRACT_MIN_SNR = -18

# Fenster-Sliding: Offsets in Samples (±0.3s @ 12kHz = ±3600 Samples)
SLIDE_OFFSETS = [0, 3600, -3600]

# Kandidaten: mehr als 100 auf vollem Band (Contest)
MAX_CANDIDATES = 200

# Frequenz-Offset-Suche: deaktiviert — Cosinus-Shift erzeugt Spiegelfrequenz
# Braucht Hilbert-Transform fuer sauberen Shift (TODO)
FREQ_OFFSETS_HZ = [0.0]


class Decoder(QObject):
    """FT8 Decoder mit Signal Subtraction und Fenster-Sliding.

    Signals:
        message_decoded: (FT8Message) — einzelne dekodierte Nachricht
        cycle_decoded: (list[FT8Message]) — alle Nachrichten eines Zyklus
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
        self.recent_calls = set()
        self.occupied_freqs = []
        self.input_sample_rate = 24000
        self._prev_audio_12k = None  # Vorheriger Zyklus fuer Akkumulierung

    def start(self):
        self._running = True
        self._decode_thread = threading.Thread(
            target=self._decode_loop, daemon=True
        )
        self._decode_thread.start()

    def stop(self):
        self._running = False

    def feed_audio(self, samples_int16: np.ndarray):
        with self._buffer_lock:
            self._audio_buffer_24k.append(samples_int16.copy())

    def _decode_loop(self):
        while self._running:
            now = time.time()
            cycle_pos = now % 15.0
            if cycle_pos < 13.5:
                wait = 13.5 - cycle_pos
            else:
                wait = 15.0 - cycle_pos + 13.5
            time.sleep(wait)

            with self._buffer_lock:
                chunks = self._audio_buffer_24k
                self._audio_buffer_24k = []

            if not chunks:
                continue

            audio_raw = np.concatenate(chunks)

            # Noise-Floor-basierte Normalisierung (statt Peak-basiert!)
            # Median der Absolutwerte = robuster Noise-Floor-Schaetzer
            # Skaliere so dass Noise-Floor bei ~300 liegt → Signale bei 1000-10000
            # Erhalt das Verhaeltnis stark/schwach korrekt
            audio_f = audio_raw.astype(np.float32)
            noise_floor = np.median(np.abs(audio_f))
            if noise_floor > 1.0:
                target_noise = 300.0
                audio_raw = np.clip(
                    audio_f * (target_noise / noise_floor), -32767, 32767
                ).astype(np.int16)

            # Samplerate: mit reduced_bw_dax=1 ist es 24kHz
            self.input_sample_rate = 24000
            # Anti-Alias Resampling 24k → 12k (Sinc+Hamming Filter)
            audio_12k = _resample_to_12k(audio_raw, source_rate=24000)

            if len(audio_12k) > CYCLE_SAMPLES_12K:
                audio_12k = audio_12k[-CYCLE_SAMPLES_12K:]
            elif len(audio_12k) < CYCLE_SAMPLES_12K // 2:
                continue
            else:
                audio_12k = np.pad(
                    audio_12k, (0, max(0, CYCLE_SAMPLES_12K - len(audio_12k)))
                )

            audio_12k = _preprocess_audio(audio_12k)
            messages = self._decode_with_subtraction(audio_12k)

            # TODO: Spektrum-Akkumulierung spaeter einbauen
            # (2. Decode-Pass mit kombiniertem Audio war zu CPU-intensiv
            #  und hat Keepalive-Thread blockiert → Disconnect)

            if messages:
                self.cycle_decoded.emit(messages)
                for msg in messages:
                    self.message_decoded.emit(msg)

    # ── Multi-Pass mit Signal Subtraction ────────────────────────

    def _decode_with_subtraction(self, audio_12k: np.ndarray) -> list[FT8Message]:
        """Multi-Pass Decode: Dekodieren → Signal subtrahieren → nochmal."""
        all_messages = []
        seen = set()
        audio_work = audio_12k.astype(np.float32)

        for pass_num in range(MAX_SUBTRACT_PASSES):
            # Decode-Pass (mit Fenster-Sliding)
            new_msgs, decoded_signals = self._decode_pass(
                audio_work.astype(np.int16), seen
            )

            if not new_msgs:
                break

            all_messages.extend(new_msgs)
            for msg in new_msgs:
                seen.add(" ".join(msg.raw.split()))

            if pass_num >= MAX_SUBTRACT_PASSES - 1:
                break

            # Signal Subtraction: dekodierte Signale vom Audio abziehen
            subtracted = 0
            for sig in decoded_signals:
                if sig["snr"] >= SUBTRACT_MIN_SNR:
                    reconstructed = _reconstruct_signal(
                        sig["message"], sig["freq_hz"], sig["dt"]
                    )
                    if reconstructed is not None:
                        # Signal an richtiger Position subtrahieren
                        offset = max(0, int((sig["dt"] + 0.5) * SAMP_RATE))
                        end = min(len(audio_work), offset + len(reconstructed))
                        rlen = end - offset
                        if rlen > 0:
                            audio_work[offset:end] -= reconstructed[:rlen]
                            subtracted += 1

            if subtracted == 0:
                break

        # Frequenzen und Calls tracken
        occupied = []
        for msg in all_messages:
            occupied.append(msg.freq_hz)
            if msg.caller:
                self.recent_calls.add(msg.caller)
            if msg.target:
                self.recent_calls.add(msg.target)

        self.occupied_freqs = sorted(occupied)
        if len(self.recent_calls) > 200:
            self.recent_calls = set(list(self.recent_calls)[-200:])

        return all_messages

    # ── Decode-Pass mit Fenster-Sliding ──────────────────────────

    def _decode_pass(self, audio_12k: np.ndarray, already_seen: set
                     ) -> tuple[list[FT8Message], list[dict]]:
        """Ein Decode-Pass mit Fenster-Sliding + Frequenz-Offset-Suche."""
        all_msgs = []
        all_signals = []
        seen_this_pass = set()

        for offset in SLIDE_OFFSETS:
            # Audio mit Zeitoffset verschieben
            if offset > 0:
                shifted = np.pad(audio_12k[offset:], (0, offset))
            elif offset < 0:
                shifted = np.pad(audio_12k[:offset], (-offset, 0))
            else:
                shifted = audio_12k

            for freq_shift in FREQ_OFFSETS_HZ:
                # Audio um freq_shift Hz verschieben
                if abs(freq_shift) > 0.01:
                    shifted_f = _freq_shift(shifted, freq_shift)
                else:
                    shifted_f = shifted

                msgs, signals = self._single_decode(
                    shifted_f, already_seen | seen_this_pass
                )

                for msg, sig in zip(msgs, signals):
                    msg_key = " ".join(msg.raw.split())
                    if msg_key not in seen_this_pass:
                        seen_this_pass.add(msg_key)
                        # dt + freq korrigieren
                        msg.dt += offset / SAMP_RATE
                        sig["dt"] += offset / SAMP_RATE
                        if abs(freq_shift) > 0.01:
                            msg.freq_hz = int(msg.freq_hz - freq_shift)
                            sig["freq_hz"] = int(sig["freq_hz"] - freq_shift)
                        all_msgs.append(msg)
                        all_signals.append(sig)

        return all_msgs, all_signals

    # ── Einzelner Decode (Kern-Algorithmus) ──────────────────────

    # LLR Parameter-Sets: (scale, clip) — verschiedene Schwellen fuer verschiedene Signalstaerken
    LLR_PARAMS_SWEEP = [
        (3.3, 3.7),   # Standard (PyFT8 Default)
        (2.5, 5.0),   # Aggressiver — besser fuer schwache Signale
    ]

    def _single_decode(self, audio_12k: np.ndarray, already_seen: set
                       ) -> tuple[list[FT8Message], list[dict]]:
        """Einzelner Decode-Durchgang mit Multi-Parameter-Sweep."""
        audio_in = AudioIn(self.max_freq)
        samples_per_hop = int(SAMP_RATE / (SYM_RATE * HPS))
        audio_float = audio_12k.astype(np.float32)
        n_hops = min(len(audio_float) // samples_per_hop, audio_in.hops_per_grid)

        # dBgrid aufbauen (teuer — nur einmal!)
        for i in range(n_hops):
            chunk = audio_float[i * samples_per_hop:(i + 1) * samples_per_hop]
            audio_in._callback(chunk.astype(np.int16).tobytes(), None, None, None)

        df = self.max_freq / (audio_in.nFreqs - 1)
        f0_range = range(
            int(200 / df),
            min(audio_in.nFreqs - 8 * BPT, int(self.max_freq / df))
        )

        cyclestart = global_time_utils.cyclestart(time.time())
        costas_nhops = 7 * HPS

        # Costas Sync-Suche (einmal fuer alle Parameter-Sets)
        cand_data = []
        for f0_idx in f0_range:
            freq_idxs = f0_idx + BASE_FREQ_IDXS
            if max(freq_idxs) >= audio_in.nFreqs:
                continue

            best_score = -999
            best_h0 = 0
            for h0 in range(H0_RANGE[0], min(H0_RANGE[1], n_hops - costas_nhops)):
                score = 0
                for ci, cv in enumerate(COSTAS):
                    hop = h0 + ci * HPS
                    if hop < audio_in.dBgrid_main.shape[0]:
                        fidx = freq_idxs[cv]
                        if fidx < audio_in.nFreqs:
                            score += audio_in.dBgrid_main[hop, fidx]
                if score > best_score:
                    best_score = score
                    best_h0 = h0

            cand_data.append((f0_idx, best_h0, best_score, int(f0_idx * df),
                              best_h0 / (HPS * SYM_RATE) - 2.2))  # -0.7 Basis + 1.5s Korrektur (geeicht an SDR-Control)

        cand_data.sort(key=lambda x: x[2], reverse=True)

        messages = []
        signals = []
        seen_local = set()

        # Multi-Parameter-Sweep: verschiedene LLR-Skalierungen
        failed_for_osd = []  # Fehlgeschlagene BP-Kandidaten fuer OSD

        for target_params in self.LLR_PARAMS_SWEEP:
            for f0_idx, h0_idx, sync_score, fHz, dt in cand_data[:MAX_CANDIDATES]:
                try:
                    c = Candidate(cyclestart=cyclestart, f0_idx=f0_idx)
                    c.h0_idx = h0_idx
                    c.sync_score = sync_score
                    c.fHz = fHz
                    c.dt = dt
                    c.demap(audio_in.dBgrid_main, target_params=target_params)
                    c.decode()
                    if c.msg:
                        msg_key = " ".join(c.msg.split())
                        if msg_key in already_seen or msg_key in seen_local:
                            continue
                        seen_local.add(msg_key)
                        msg = parse_ft8_message(
                            c.msg, snr=c.snr, freq_hz=c.fHz, dt=c.dt
                        )
                        messages.append(msg)
                        signals.append({
                            "message": msg_key,
                            "freq_hz": c.fHz,
                            "snr": c.snr,
                            "dt": c.dt,
                        })
                    elif hasattr(c, 'llr') and len(c.llr) == 174:
                        # BP gescheitert — LLR fuer OSD merken
                        failed_for_osd.append((c.llr.copy(), c.snr, fHz, dt))
                except Exception:
                    continue

        # AP + OSD Fallback
        if failed_for_osd:
            my_call = self.my_call if hasattr(self, 'my_call') else "DA1MHH"
            for llr, snr, fHz, dt in failed_for_osd[:30]:
                decoded_msg = None
                try:
                    decoded_msg = try_ap_decode(
                        llr, my_call=my_call,
                        recent_calls=self.recent_calls,
                    )
                    if not decoded_msg:
                        decoded_msg = try_osd_decode(llr, max_depth=1)
                except Exception:
                    continue
                if decoded_msg:
                    msg_key = " ".join(decoded_msg.split())
                    if msg_key in already_seen or msg_key in seen_local:
                        continue
                    seen_local.add(msg_key)
                    msg = parse_ft8_message(
                        decoded_msg, snr=snr, freq_hz=fHz, dt=dt
                    )
                    messages.append(msg)
                    signals.append({
                        "message": msg_key,
                        "freq_hz": fHz,
                        "snr": snr,
                        "dt": dt,
                    })

        return messages, signals


# ── Signal Subtraction: Rekonstruktion ───────────────────────

_audio_out = AudioOut()


def _reconstruct_signal(message_str: str, freq_hz: int,
                         dt: float) -> np.ndarray | None:
    """FT8-Signal aus dekodierter Nachricht rekonstruieren.

    Erzeugt das exakte Audio-Signal das subtrahiert werden kann.
    """
    parts = message_str.strip().split()
    if len(parts) != 3:
        return None

    try:
        symbols = pack_message(parts[0], parts[1], parts[2])
        if symbols is None or len(symbols) != 79:
            return None

        audio_int16 = _audio_out.create_ft8_wave(
            symbols, fs=SAMP_RATE, f_base=float(freq_hz)
        )
        return audio_int16.astype(np.float32)

    except Exception:
        return None


# ── Frequenz-Shift fuer Sub-Bin-Suche ──────────────────────

def _freq_shift(audio_int16: np.ndarray, shift_hz: float,
                sample_rate: int = SAMP_RATE) -> np.ndarray:
    """Audio um shift_hz verschieben per Cosinus-Multiplikation."""
    t = np.arange(len(audio_int16), dtype=np.float32) / sample_rate
    shifted = audio_int16.astype(np.float32) * np.cos(
        2 * np.pi * shift_hz * t
    )
    return np.clip(shifted, -32767, 32767).astype(np.int16)


# ── Audio-Vorverarbeitung ────────────────────────────────────

def _preprocess_audio(audio_int16: np.ndarray) -> np.ndarray:
    """DC-Remove, Spectral Whitening, Normalisierung."""
    audio = audio_int16.astype(np.float32)

    # 1. DC-Offset entfernen
    audio -= np.mean(audio)

    # 2. Spectral Whitening (vektorisiert für Performance)
    n_fft = 2048
    hop_size = n_fft // 2
    n_frames = (len(audio) - n_fft) // hop_size
    if n_frames > 0:
        window = np.hanning(n_fft).astype(np.float32)
        output = np.zeros_like(audio)
        weights = np.zeros_like(audio)
        kernel = 31
        pad_k = kernel // 2

        for i in range(n_frames):
            start = i * hop_size
            frame = audio[start:start + n_fft] * window
            spectrum = np.fft.rfft(frame)
            magnitude = np.abs(spectrum)

            # Vektorisierter gleitender Median (schneller als Loop)
            mag_padded = np.pad(magnitude, pad_k, mode="reflect")
            # Stride-Trick für Sliding-Window Median
            shape = (len(magnitude), kernel)
            strides = (mag_padded.strides[0], mag_padded.strides[0])
            windows = np.lib.stride_tricks.as_strided(
                mag_padded, shape=shape, strides=strides
            )
            noise_floor = np.median(windows, axis=1)

            noise_floor = np.maximum(noise_floor, 1e-6)
            whitened = spectrum * np.minimum(1.0 / noise_floor, 100.0)

            frame_out = np.fft.irfft(whitened, n=n_fft)
            output[start:start + n_fft] += frame_out * window
            weights[start:start + n_fft] += window ** 2

        weights = np.maximum(weights, 1e-6)
        audio = output / weights

    # 3. RMS-Normalisierung auf -18 dBFS (statt Peak-basiert!)
    # RMS ist robuster als Peak — erhaelt Verhaeltnis stark/schwach
    rms = np.sqrt(np.mean(audio ** 2))
    if rms > 0.1:
        target_rms = 32767 * 10 ** (-18 / 20)  # ~4125
        audio = audio * (target_rms / rms)

    return np.clip(audio, -32767, 32767).astype(np.int16)


# ── Resampling mit Anti-Alias-Filter ────────────────────────

def _resample_to_12k(audio: np.ndarray, source_rate: int) -> np.ndarray:
    """Resample von source_rate auf 12kHz mit Anti-Alias-Tiefpass.

    Verhindert Aliasing das bei einfacher Dezimierung schwache Signale
    zerstoert. Bringt ~30-50% mehr dekodierte Stationen.
    """
    if source_rate == 12000:
        return audio

    ratio = source_rate // 12000  # 2 (24kHz) oder 4 (48kHz)
    audio_f = audio.astype(np.float32)

    # Anti-Alias Tiefpass: Sinc-Filter mit Hamming-Fenster
    # Cutoff bei 6kHz (Nyquist von 12kHz), Ordnung 63
    n_taps = 63
    n = np.arange(n_taps) - (n_taps - 1) / 2
    fc = 6000.0 / source_rate  # Normierte Cutoff-Frequenz
    # Sinc-Funktion
    with np.errstate(divide="ignore", invalid="ignore"):
        h = np.where(n == 0, 2 * fc, np.sin(2 * np.pi * fc * n) / (np.pi * n))
    # Hamming-Fenster
    h *= np.hamming(n_taps)
    # Normalisieren
    h = (h / np.sum(h)).astype(np.float32)

    # Filtern
    filtered = np.convolve(audio_f, h, mode="same")

    # Dezimieren
    return filtered[::ratio].astype(audio.dtype)
