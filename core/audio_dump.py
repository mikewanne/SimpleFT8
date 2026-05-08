"""core/audio_dump.py — Roh-Audio-Slot-Dump fuer Debug/Forschung (P3, v0.95.20).

Use-Cases:
- AP-Lite-Decode-Replay (Bug-Diagnose ohne Live-Funkbetrieb)
- ANT1/ANT2-Spektrum-Vergleich offline (Inspectrum/Audacity)
- Decoder-Verbesserungen gegen reale Aufnahmen

Pattern:
- Atomic-Write via tempfile.mkstemp(dir=) + os.replace (P2.ADIF-ARCHIVE-Konsistenz)
- FIFO-Cleanup via mtime-Sort, global ueber alle band_mode-Sub-Dirs
- WAV: mono int16 24 kHz (Decoder-Original-Format vor Resample)
"""
from __future__ import annotations

import os
import tempfile
import time as _time
import wave
from pathlib import Path

import numpy as np


# Projekt-Root (relativ zu dieser Datei): SimpleFT8/
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DUMP_ROOT = _PROJECT_ROOT / "audio_dump"


def atomic_write_wav(path: Path, audio_int16: np.ndarray,
                     sample_rate: int = 24000) -> None:
    """WAV mono 16-bit atomar schreiben.

    Atomic-Pattern: tmpfile auf gleichem FS via tempfile.mkstemp(dir=)
    + os.replace. Bei Crash mid-write: kein zerrissenes WAV, tmpfile
    wird im except aufgeraeumt.
    """
    target_dir = path.parent
    target_dir.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(
        dir=target_dir, prefix=f".{path.name}.", suffix=".tmp"
    )
    os.close(fd)
    try:
        with wave.open(tmp_path, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)  # int16
            wf.setframerate(sample_rate)
            wf.writeframes(audio_int16.astype(np.int16).tobytes())
        os.replace(tmp_path, path)
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def enforce_fifo_cap(audio_dump_root: Path, max_files: int) -> int:
    """Aelteste WAV-Files loeschen wenn Anzahl > max_files.

    Returnt Anzahl geloeschter Files (fuer Tests).
    Globaler Cap ueber alle Sub-Verzeichnisse zusammen.
    Beruecksichtigt nur `*.wav` (nicht `.tmp` oder andere).
    """
    audio_dump_root = Path(audio_dump_root)
    if not audio_dump_root.exists():
        return 0
    all_wavs = sorted(
        audio_dump_root.glob("**/*.wav"),
        key=lambda p: p.stat().st_mtime,
    )
    overflow = len(all_wavs) - max_files
    if overflow <= 0:
        return 0
    deleted = 0
    for p in all_wavs[:overflow]:
        try:
            p.unlink()
            deleted += 1
        except OSError:
            pass  # File-Lock o.ae., naechster Lauf raeumt nach
    return deleted


def build_dump_path(root: Path, band: str, mode: str,
                    slot_start_utc: float, ant: str) -> Path:
    """Baut Filename aus Komponenten + Kollisions-Suffix.

    Format: root/{band}_{mode}/{YYYY-MM-DD_HH-MM-SS}_{ant}.wav
    Bei Kollision: _v2-Suffix (Edge-Case NTP-Sprung / Decoder-Restart).
    """
    root = Path(root)
    ts = _time.strftime("%Y-%m-%d_%H-%M-%S",
                        _time.gmtime(slot_start_utc))
    sub_dir = root / f"{band}_{mode}"
    path = sub_dir / f"{ts}_{ant}.wav"
    if path.exists():
        path = sub_dir / f"{ts}_{ant}_v2.wav"
    return path
