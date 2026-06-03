"""SimpleFT8 Audio-Monitor — RX-Audio zum Mithören auf den Lautsprecher.

DIAGNOSE-Werkzeug (Mike 2026-06-03): Das empfangene Funk-Audio (24 kHz mono
int16, wie es der Decoder bekommt) wird optional auf das Standard-Ausgabe-
geraet gelegt. Zweck: hoerbar pruefen, ob auf der Frequenz Betrieb ist —
Gezwitscher im Ohr, aber leere Empfangsliste = Decode-Problem, nicht leeres
Band.

Architektur (DeepSeek-R1-gehaertet):
- KEIN Eingriff in den Decoder. Gespeist via `feed()` vom selben RX-Audio,
  das auch der Decoder bekommt (Wrapper in `mw_radio._on_rx_audio`).
- `feed()` laeuft im VITA-49-Empfangsthread (= Decode-Timing-Thread) und MUSS
  nicht-blockierend sein: nur ein kurzer Lock + Kopie in einen VORALLOKIERTEN
  numpy-Ringpuffer (GC-frei, kein deque-Allokations-Druck).
- Ausgabe ueber sounddevice-OutputStream-CALLBACK (eigener PortAudio-Thread,
  entkoppelt vom Empfangs-/GUI-Thread).
- Ausgabe FEST 48 kHz (24-kHz-Quelle x2 verdoppelt, kein Pitch-Shift) — 24 kHz
  ist auf macOS/CoreAudio nicht ueberall nativ, 48 kHz laeuft ueberall.
- Reiner RX-Ausgang. KEIN TX, ANT1/ANT2 unberuehrt.
"""

import threading

import numpy as np

# Quelle 24 kHz, Ausgabe 48 kHz (x2). Ringpuffer in QUELL-Samples (24 kHz).
_SOURCE_RATE = 24000
_OUTPUT_RATE = 48000
_RING_SECONDS = 2.0
_RING_SIZE = int(_SOURCE_RATE * _RING_SECONDS)   # 48000 Samples Headroom
_BLOCKSIZE_48K = 2400                            # gerade → frames//2 exakt; 50 ms


class AudioMonitor:
    """Optionaler RX-Audio-Mithoer-Ausgang. Thread-sicher, nicht-blockierend.

    `active` ist ein einfaches bool (atomar lesbar via CPython-GIL) — `feed`
    liest es lockfrei; `start`/`stop` (GUI-Thread) setzen es. Der Ringpuffer
    ist Lock-geschuetzt (feed = Empfangsthread schreibt, Callback = PortAudio-
    Thread liest).
    """

    def __init__(self, ring_size: int = _RING_SIZE):
        self._buf = np.zeros(ring_size, dtype=np.int16)
        self._size = ring_size
        self._write = 0
        self._read = 0
        self._count = 0
        self._lock = threading.Lock()
        self._stream = None
        self.active = False

    # ── Speisung (Empfangsthread — MUSS nicht-blockierend bleiben) ──────────
    def feed(self, samples_int16: np.ndarray):
        """Neue RX-Samples (24 kHz int16) in den Ringpuffer. No-op wenn inaktiv.

        Laeuft im VITA-49-Empfangsthread. Nur kurzer Lock + Kopie, kein
        Blockieren, keine Allokation (vorallokierter Puffer).
        """
        if not self.active:
            return
        n = len(samples_int16)
        if n == 0:
            return
        src = samples_int16
        if n > self._size:
            src = samples_int16[-self._size:]    # nur juengste, Rest sinnlos
            n = self._size
        with self._lock:
            w = self._write
            end = w + n
            if end <= self._size:
                self._buf[w:end] = src
            else:
                first = self._size - w
                self._buf[w:] = src[:first]
                self._buf[:n - first] = src[first:]
            self._write = end % self._size
            self._count += n
            if self._count > self._size:
                # Overflow: aeltestes verworfen, read folgt write.
                self._read = self._write
                self._count = self._size

    # ── Auslesen (PortAudio-Callback-Thread) ────────────────────────────────
    def _read_into(self, outdata, frames: int):
        """Fuellt outdata (frames @48 kHz) aus dem 24-kHz-Ringpuffer (x2).

        Underrun → mit Stille auffuellen; read-Index NIE ueber write hinaus
        (kein Versatz nach TX-Pausen, DeepSeek-🟠).
        """
        need = frames // 2                       # 24-kHz-Samples fuer frames @48k
        with self._lock:
            n = min(need, self._count)
            chunk = self._pop_locked(n)
        valid = n * 2
        if n:
            outdata[0:valid:2, 0] = chunk
            outdata[1:valid:2, 0] = chunk
        if valid < frames:
            outdata[valid:, 0] = 0               # Underrun → Stille

    def _pop_locked(self, n: int) -> np.ndarray:
        """n Samples ab read lesen (Lock muss gehalten sein). Advance read."""
        if n == 0:
            return np.empty(0, dtype=np.int16)
        r = self._read
        end = r + n
        if end <= self._size:
            out = self._buf[r:end].copy()
        else:
            first = self._size - r
            out = np.concatenate((self._buf[r:], self._buf[:n - first]))
        self._read = end % self._size
        self._count -= n
        return out

    def _sd_callback(self, outdata, frames, time_info, status):
        try:
            self._read_into(outdata, frames)
        except Exception:
            outdata[:] = 0                       # nie den Audio-Thread crashen

    # ── Lifecycle (GUI-Thread) ──────────────────────────────────────────────
    def start(self):
        """OutputStream oeffnen + starten. Wirft bei Fehler (Aufrufer rollt
        den Toggle zurueck). Idempotent (No-op wenn schon aktiv)."""
        if self.active:
            return
        import sounddevice as sd                 # lazy → Import-Fehler abfangbar
        with self._lock:                          # Puffer leeren fuer sauberen Start
            self._write = self._read = self._count = 0
        stream = sd.OutputStream(
            samplerate=_OUTPUT_RATE, channels=1, dtype="int16",
            blocksize=_BLOCKSIZE_48K, callback=self._sd_callback,
        )
        stream.start()
        self._stream = stream
        self.active = True

    def stop(self):
        """Stream stoppen + schliessen. Robust, idempotent."""
        self.active = False
        stream, self._stream = self._stream, None
        if stream is not None:
            try:
                stream.stop()
                stream.close()
            except Exception:
                pass
