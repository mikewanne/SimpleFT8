"""SimpleFT8 ft8lib ctypes Wrapper — Schnittstelle zu libft8simple.dylib.

Laedt die kompilierte C-Bibliothek und stellt zwei Python-freundliche
Methoden bereit:
    decode()  — int16 Audio @ 12kHz → Liste von Decode-Ergebnissen
    encode()  — Nachrichtentext + Frequenz → int16 Audio @ 12kHz
"""

import ctypes
import sys
from pathlib import Path

import numpy as np


def _find_lib() -> Path:
    """libft8simple.dylib finden — neben main.py oder im PyInstaller-Bundle."""
    if getattr(sys, "frozen", False):
        base = Path(sys._MEIPASS)
    else:
        base = Path(__file__).parent.parent   # SimpleFT8/

    for p in [
        base / "libft8simple.dylib",
        base / "ft8_lib" / "libft8simple.dylib",
    ]:
        if p.exists():
            return p

    raise FileNotFoundError(
        f"libft8simple.dylib nicht gefunden. Gesucht in: {base}"
    )


class _Ft8sResult(ctypes.Structure):
    """Spiegelt ft8s_result_t aus libft8simple.c (fixes Speicher-Layout)."""

    _fields_ = [
        ("message",     ctypes.c_char * 35),
        ("freq_hz",     ctypes.c_float),
        ("dt",          ctypes.c_float),
        ("snr",         ctypes.c_int),
        ("ldpc_errors", ctypes.c_int),
    ]


class Ft8Lib:
    """ctypes Interface zu libft8simple.dylib.

    Singleton — die Bibliothek wird nur einmal geladen. Thread-safe fuer
    lesende Operationen; die interne Callsign-Hashtable ist nicht kritisch.
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            obj = super().__new__(cls)
            obj._loaded = False
            cls._instance = obj
        return cls._instance

    def __init__(self):
        if self._loaded:
            return
        lib_path = _find_lib()
        self._lib = ctypes.CDLL(str(lib_path))
        self._setup_prototypes()
        self._loaded = True
        print(f"[Ft8Lib] Geladen: {lib_path}")

    def _setup_prototypes(self):
        # int ft8s_decode(const int16_t*, int, float, int, ft8s_result_t*, int)
        self._lib.ft8s_decode.restype = ctypes.c_int
        self._lib.ft8s_decode.argtypes = [
            ctypes.POINTER(ctypes.c_int16),   # samples
            ctypes.c_int,                      # n_samples
            ctypes.c_float,                    # max_freq_hz
            ctypes.c_int,                      # num_passes
            ctypes.POINTER(_Ft8sResult),       # results
            ctypes.c_int,                      # max_results
        ]
        # int ft8s_encode(const char*, float, int16_t*, int)
        self._lib.ft8s_encode.restype = ctypes.c_int
        self._lib.ft8s_encode.argtypes = [
            ctypes.c_char_p,                   # message_text
            ctypes.c_float,                    # freq_hz
            ctypes.POINTER(ctypes.c_int16),    # out_samples
            ctypes.c_int,                      # max_samples
        ]

    def decode(
        self,
        audio_int16: np.ndarray,
        max_freq_hz: float = 3000.0,
        num_passes: int = 5,
        max_results: int = 200,
    ) -> list[dict]:
        """int16 PCM @ 12kHz → Liste von Decode-Ergebnissen.

        Jedes Ergebnis: {"message": str, "freq_hz": float, "dt": float,
                         "snr": int, "ldpc_errors": int}
        """
        audio = np.ascontiguousarray(audio_int16, dtype=np.int16)
        results = (_Ft8sResult * max_results)()

        n_found = self._lib.ft8s_decode(
            audio.ctypes.data_as(ctypes.POINTER(ctypes.c_int16)),
            ctypes.c_int(len(audio)),
            ctypes.c_float(max_freq_hz),
            ctypes.c_int(num_passes),
            results,
            ctypes.c_int(max_results),
        )

        return [
            {
                "message":     results[i].message.decode("ascii", errors="replace").strip(),
                "freq_hz":     float(results[i].freq_hz),
                "dt":          float(results[i].dt),
                "snr":         int(results[i].snr),
                "ldpc_errors": int(results[i].ldpc_errors),
            }
            for i in range(max(0, n_found))
        ]

    def encode(self, message_text: str, freq_hz: float = 1000.0) -> np.ndarray | None:
        """Nachrichtentext → int16 PCM @ 12kHz.

        Gibt None zurueck wenn der Text ungueltig ist oder die Bibliothek
        einen Fehler meldet.
        """
        max_samples = 200_000
        out_buf = (ctypes.c_int16 * max_samples)()

        n_written = self._lib.ft8s_encode(
            message_text.encode("ascii"),
            ctypes.c_float(freq_hz),
            out_buf,
            ctypes.c_int(max_samples),
        )

        if n_written < 0:
            return None
        return np.frombuffer(out_buf, dtype=np.int16, count=n_written).copy()


def get_ft8lib() -> Ft8Lib:
    """Globalen Ft8Lib Singleton laden (lazy-init)."""
    return Ft8Lib()
