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

# LDPC Tuning — wird per set_quality() angepasst:
# NORMAL (schnell): (50, 25) — jeder 15s Zyklus, Stationen ab ~-15 dB
# DIVERSITY (tief): (83, 50) — jeder 2. Zyklus, Perlen bis -24 dB
import PyFT8.receiver as _pyft8_rx
_pyft8_rx.LDPC_CONTROL = (83, 50)  # Default: tief (wird bei Modus-Wechsel geaendert)

from .message import FT8Message, parse_ft8_message


# FT8 Zyklus = 15s, bei 12kHz = 180000 Samples
CYCLE_SAMPLES_12K = int(15 * SAMP_RATE)  # 180000

# Signal Subtraction Passes — wird per set_quality() angepasst
MAX_SUBTRACT_PASSES = 5
# Nur subtrahieren wenn SNR mindestens so gut ist (dB)
SUBTRACT_MIN_SNR = -18

# Fenster-Sliding: Offsets in Samples (±0.3s @ 12kHz = ±3600 Samples)
SLIDE_OFFSETS = [0, 3600, -3600]

# Kandidaten — wird per set_quality() angepasst:
# NORMAL: 80 (schnell), DIVERSITY: 200 (DX-Tiefe)
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
        # DeepSeek: deque statt set → Reihenfolge erhalten (aktuellste zuerst)
        from collections import deque
        self.recent_calls: deque = deque(maxlen=200)
        self.occupied_freqs = []
        self.input_sample_rate = 24000
        self._prev_audio_12k = None  # Vorheriger Zyklus fuer Akkumulierung
        self.priority_call: str = ""  # QSO-Partner (hoechste AP-Prioritaet)
        # LLR-Parameter-Sets: als Instanz-Variable damit set_quality() sie anpassen kann
        self._llr_params_sweep = [(3.3, 3.7), (2.5, 5.0)]  # Default: beide (Diversity)
        self._osd_max_cands = 20   # OSD: max Kandidaten (per set_quality anpassbar)
        self._osd_max_depth = 1    # OSD: max Tiefe (depth=2 = 62ms/Kand → zu langsam)

    def start(self):
        self._running = True
        self._decode_thread = threading.Thread(
            target=self._decode_loop, daemon=True
        )
        self._decode_thread.start()

    def stop(self):
        self._running = False

    def set_quality(self, mode: str):
        """Decode-Qualitaet anpassen: 'normal' = schnell, 'diversity' = tief.

        normal:    LDPC(50,25), 3 Passes, volle Kandidaten → jeden Zyklus
        diversity: LDPC(83,50), 5 Passes, volle Kandidaten → DX-Perlen
        Geschwindigkeit kommt von vectorisierter Costas-Sync (279x), nicht von Qualitaetsreduzierung.
        """
        global MAX_SUBTRACT_PASSES, MAX_CANDIDATES
        if mode == "normal":
            _pyft8_rx.LDPC_CONTROL = (50, 25)
            MAX_SUBTRACT_PASSES = 5
            MAX_CANDIDATES = 200
            self._llr_params_sweep = [(3.3, 3.7), (2.5, 5.0)]
            self._osd_max_cands = 10   # OSD: wenige Kandidaten, schnell
            self._osd_max_depth = 1   # depth=2 zu langsam (62ms/Kand)
            print(f"[Decoder] Qualitaet: NORMAL (200 Kand, 2 LLR, 5 Passes, OSD-10/d1)")
        else:
            _pyft8_rx.LDPC_CONTROL = (83, 50)
            MAX_SUBTRACT_PASSES = 7
            MAX_CANDIDATES = 200
            self._llr_params_sweep = [(3.3, 3.7), (2.5, 5.0)]
            self._osd_max_cands = 20   # DX: mehr OSD-Kandidaten
            self._osd_max_depth = 1   # depth=1 reicht, depth=2 kostet 3x mehr
            print(f"[Decoder] Qualitaet: DIVERSITY (200 Kand, 2 LLR, 7 Passes, OSD-20/d1)")

    def feed_audio(self, samples_int16: np.ndarray):
        with self._buffer_lock:
            self._audio_buffer_24k.append(samples_int16.copy())

    def _decode_loop(self):
        """Scheduling loop: feuert alle 15s, spawnt Decode-Thread wenn nicht busy."""
        self._decode_busy = False
        self._decode_busy_lock = threading.Lock()

        while self._running:
            try:
                now = time.time()
                cycle_pos = now % 15.0
                if cycle_pos < 13.5:
                    wait = 13.5 - cycle_pos
                else:
                    wait = 15.0 - cycle_pos + 13.5
                time.sleep(wait)

                # Vorherigen Decode noch aktiv? → Zyklus ueberspringen, Puffer behalten
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

    def _process_cycle(self, chunks):
        """Decode-Arbeit in eigenem Thread — blockiert den Scheduling-Loop nicht."""
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

            # Samplerate: mit reduced_bw_dax=1 ist es 24kHz
            self.input_sample_rate = 24000
            # Anti-Alias Resampling 24k → 12k (Sinc+Hamming Filter)
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

            t_pre = time.time()
            audio_12k = _preprocess_audio(audio_12k)
            t_decode = time.time()
            peak_12k = np.max(np.abs(audio_12k))
            print(f"[Decoder] Preprocessing: {t_decode - t_pre:.2f}s, Peak={peak_12k}")
            messages = self._decode_with_subtraction(audio_12k)
            t_done = time.time()

            print(f"[Decoder] {len(messages)} Stationen dekodiert — Gesamt: {t_done - t_start:.2f}s (Pre: {t_decode - t_pre:.2f}s, LDPC: {t_done - t_decode:.2f}s)")

            if messages:
                self.cycle_decoded.emit(messages)
                my = getattr(self, '_my_call', '')
                for msg in messages:
                    # Roh-Log: Nachrichten an uns oder von QSO-Partner hervorheben
                    is_to_me = my and hasattr(msg, 'target') and msg.target == my
                    is_partner = (hasattr(self, 'priority_call') and self.priority_call and
                                  hasattr(msg, 'caller') and msg.caller == self.priority_call)
                    if is_to_me or is_partner:
                        tag = ">>> AN UNS" if is_to_me else "QSO-Partner"
                        print(f"[RX] {msg.raw} | snr={msg.snr} freq={msg.freq_hz} [{tag}]")
                    self.message_decoded.emit(msg)
            else:
                # Auch leere Ergebnisse emittieren damit GUI aktualisiert
                self.cycle_decoded.emit([])

        except Exception as e:
            import traceback
            print(f"[Decoder] FEHLER Decode-Thread: {e}")
            traceback.print_exc()
        finally:
            with self._decode_busy_lock:
                self._decode_busy = False

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

        # Frequenzen und Calls tracken (deque: aktuellste zuerst via appendleft)
        occupied = []
        for msg in all_messages:
            occupied.append(msg.freq_hz)
            if msg.caller and msg.caller not in self.recent_calls:
                self.recent_calls.appendleft(msg.caller)
            if msg.target and msg.target not in self.recent_calls:
                self.recent_calls.appendleft(msg.target)

        self.occupied_freqs = sorted(occupied)

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

    # LLR Parameter-Sets: (scale, clip) — als Instanzvariable in __init__ (per set_quality aenderbar)
    # Default gesetzt in __init__: self._llr_params_sweep

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

        # Costas Sync-Suche VECTORIZED (279x schneller als Python-Triple-Loop)
        # Statt: for f0 × for h0 × for 7-costas → numpy outer-product lookup
        f0_arr = np.array(list(f0_range), dtype=np.int32)

        # Alle freq_idxs fuer alle f0 auf einmal: (n_f0, 16)
        base_freq_np = np.array(BASE_FREQ_IDXS, dtype=np.int32)
        freq_idxs_all = f0_arr[:, None] + base_freq_np[None, :]
        # Nur gueltige f0 (max freq_idx < nFreqs)
        valid_f0 = np.max(freq_idxs_all, axis=1) < audio_in.nFreqs
        f0_arr = f0_arr[valid_f0]
        freq_idxs_all = freq_idxs_all[valid_f0]

        # Costas-Frequenz-Indizes: (n_f0, 7)
        costas_np = np.array(COSTAS, dtype=np.int32)
        costas_freq_idxs = freq_idxs_all[:, costas_np]

        # h0-Werte und Hop-Indizes: (n_h0, 7)
        h0_max = min(H0_RANGE[1], n_hops - costas_nhops)
        h0_arr = np.arange(H0_RANGE[0], h0_max, dtype=np.int32)
        hop_offsets = np.arange(7, dtype=np.int32) * HPS
        hop_idxs_all = h0_arr[:, None] + hop_offsets[None, :]
        valid_h0 = np.all(hop_idxs_all < audio_in.dBgrid_main.shape[0], axis=1)
        hop_idxs_all = hop_idxs_all[valid_h0]
        h0_arr = h0_arr[valid_h0]

        # Score-Matrix (n_h0, n_f0): fuer jedes Costas-Symbol addieren
        scores = np.zeros((len(h0_arr), len(f0_arr)), dtype=np.float32)
        for ci in range(7):
            scores += audio_in.dBgrid_main[hop_idxs_all[:, ci]][:, costas_freq_idxs[:, ci]]

        # Bestes h0 pro f0
        best_h0_idx = np.argmax(scores, axis=0)
        best_scores_arr = scores[best_h0_idx, np.arange(len(f0_arr))]
        best_h0_arr = h0_arr[best_h0_idx]

        cand_data = [
            (int(f0), int(h0), float(sc), int(f0 * df), h0 / (HPS * SYM_RATE) - 2.2)
            for f0, h0, sc in zip(f0_arr, best_h0_arr, best_scores_arr)
        ]

        cand_data.sort(key=lambda x: x[2], reverse=True)

        messages = []
        signals = []
        seen_local = set()

        # Multi-Parameter-Sweep: verschiedene LLR-Skalierungen
        failed_for_osd = []  # Fehlgeschlagene BP-Kandidaten fuer OSD

        for target_params in self._llr_params_sweep:
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

        # AP + OSD Fallback (DeepSeek: priority_call fuer aktiven QSO-Partner)
        if failed_for_osd:
            my_call = self.my_call if hasattr(self, 'my_call') else "DA1MHH"
            # priority_call an den Anfang der recent_calls Liste stellen
            p_call = getattr(self, 'priority_call', '')
            ap_calls = self.recent_calls
            if p_call and p_call not in ap_calls:
                from collections import deque as _deque
                ap_calls = _deque([p_call], maxlen=201)
                ap_calls.extend(self.recent_calls)
            elif p_call:
                # Schon drin — ans Ende damit appendleft-Reihenfolge erhalten bleibt
                pass
            for llr, snr, fHz, dt in failed_for_osd[:self._osd_max_cands]:
                decoded_msg = None
                try:
                    decoded_msg = try_ap_decode(
                        llr, my_call=my_call,
                        recent_calls=ap_calls,
                        priority_call=p_call or None,
                    )
                    if not decoded_msg:
                        decoded_msg = try_osd_decode(llr, max_depth=self._osd_max_depth)
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

    # 2. Spectral Whitening (Overlap-Add, gleitender Median pro FFT-Frame)
    # Vectorisiert: Batch-FFT statt Python-Loop — deutlich schneller auf M1/M4
    n_fft = 2048
    hop_size = n_fft // 2
    n_frames = (len(audio) - n_fft) // hop_size
    if n_frames > 0:
        from numpy.lib.stride_tricks import sliding_window_view
        window = np.hanning(n_fft).astype(np.float32)
        kernel = 31
        pad_k = kernel // 2

        # Alle Frames auf einmal extrahieren: (n_frames, n_fft)
        all_frames = sliding_window_view(audio, n_fft)[::hop_size][:n_frames] * window

        # Batch-FFT: eine C-Ebene-Operation statt 175 Python-Aufrufe
        all_spectra = np.fft.rfft(all_frames, axis=1)          # (n_frames, n_fft//2+1)
        all_magnitudes = np.abs(all_spectra)

        # Noise-Floor: sliding median entlang Frequenz-Achse fuer alle Frames gleichzeitig
        mag_padded = np.pad(all_magnitudes, ((0, 0), (pad_k, pad_k)), mode="reflect")
        freq_windows = sliding_window_view(mag_padded, kernel, axis=1)  # (n_frames, n_freq, kernel)
        noise_floor_all = np.median(freq_windows, axis=2)       # (n_frames, n_freq)
        noise_floor_all = np.maximum(noise_floor_all, 1e-6)

        # Whitening: alle Frames auf einmal
        whitened_all = all_spectra * np.minimum(1.0 / noise_floor_all, 100.0)

        # Batch-IFFT: (n_frames, n_fft)
        frames_out = np.fft.irfft(whitened_all, n=n_fft, axis=1) * window

        # Overlap-Add via np.add.at (kein Python-Loop)
        output = np.zeros_like(audio)
        weights = np.zeros_like(audio)
        frame_starts = np.arange(n_frames) * hop_size
        indices = (frame_starts[:, None] + np.arange(n_fft)[None, :]).ravel()
        np.add.at(output, indices, frames_out.ravel())
        np.add.at(weights, indices, np.tile(window ** 2, n_frames))

        weights = np.maximum(weights, 1e-6)
        audio = output / weights

    # 3. RMS-Normalisierung auf -18 dBFS (statt Peak-basiert!)
    # RMS ist robuster als Peak — erhaelt Verhaeltnis stark/schwach
    # WICHTIG: Nach Whitening sind Werte winzig (~0.001) da irfft intern durch N=2048 teilt.
    # Threshold muss klein genug sein um auch post-whitening Werte zu erwischen.
    rms = np.sqrt(np.mean(audio ** 2))
    if rms > 1e-6:
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
