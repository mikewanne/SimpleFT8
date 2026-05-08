"""Tests fuer core/audio_dump.py + Decoder.dump_last_slot.

P3.AUDIO-DUMP-DEBUG (v0.95.20). Hardware-frei. Kein Qt fuer Helper-Tests;
Decoder-Integration testet die Pull-Pattern-Methode ohne Audio-Pipeline.
"""
from __future__ import annotations

import os
import sys
import wave
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from core.audio_dump import (  # noqa: E402
    atomic_write_wav, build_dump_path, enforce_fifo_cap,
)


def _make_audio(samples: int = 1000, value: int = 1000) -> np.ndarray:
    return np.full(samples, value, dtype=np.int16)


# ── Helper-Tests: atomic_write_wav ────────────────────────────────────────


def test_atomic_write_wav_basic(tmp_path):
    path = tmp_path / "2026.wav"
    atomic_write_wav(path, _make_audio(2400), sample_rate=24000)
    assert path.exists()
    with wave.open(str(path), "rb") as wf:
        assert wf.getnchannels() == 1
        assert wf.getsampwidth() == 2
        assert wf.getframerate() == 24000
        assert wf.getnframes() == 2400


def test_atomic_write_wav_replaces_existing(tmp_path):
    path = tmp_path / "old.wav"
    atomic_write_wav(path, _make_audio(100, value=500))
    original_size = path.stat().st_size
    atomic_write_wav(path, _make_audio(2000, value=1000))
    assert path.stat().st_size > original_size


def test_atomic_write_wav_no_partial_on_crash(tmp_path, monkeypatch):
    path = tmp_path / "crash.wav"
    atomic_write_wav(path, _make_audio(100, value=500))
    original_bytes = path.read_bytes()

    def fail_replace(*a, **kw):
        raise OSError("simulated")
    monkeypatch.setattr(os, "replace", fail_replace)

    with pytest.raises(OSError):
        atomic_write_wav(path, _make_audio(200, value=1000))
    # Original muss intakt sein
    assert path.read_bytes() == original_bytes
    # Tmpfile aufgeraeumt
    tmps = list(tmp_path.glob(".crash.wav.*.tmp"))
    assert len(tmps) == 0


def test_atomic_write_wav_creates_parent_dir(tmp_path):
    path = tmp_path / "new_subdir" / "file.wav"
    atomic_write_wav(path, _make_audio(100))
    assert path.exists()


# ── Helper-Tests: enforce_fifo_cap ────────────────────────────────────────


def test_fifo_cap_no_op_under_limit(tmp_path):
    sub = tmp_path / "20m_FT8"
    sub.mkdir()
    for i in range(50):
        (sub / f"file_{i:03d}.wav").write_bytes(b"x")
    deleted = enforce_fifo_cap(tmp_path, max_files=200)
    assert deleted == 0
    assert len(list(sub.glob("*.wav"))) == 50


def test_fifo_cap_deletes_oldest(tmp_path):
    sub = tmp_path / "20m_FT8"
    sub.mkdir()
    for i in range(5):
        f = sub / f"file_{i:03d}.wav"
        f.write_bytes(b"x")
        os.utime(f, (1_000_000 + i, 1_000_000 + i))
    deleted = enforce_fifo_cap(tmp_path, max_files=3)
    assert deleted == 2
    remaining = sorted(sub.glob("*.wav"))
    assert remaining == [
        sub / "file_002.wav",
        sub / "file_003.wav",
        sub / "file_004.wav",
    ]


def test_fifo_cap_global_across_band_dirs(tmp_path):
    s20 = tmp_path / "20m_FT8"
    s40 = tmp_path / "40m_FT8"
    s20.mkdir()
    s40.mkdir()
    for i in range(100):
        f = s20 / f"a_{i:03d}.wav"
        f.write_bytes(b"x")
        os.utime(f, (1000 + i, 1000 + i))
    for i in range(101):
        f = s40 / f"b_{i:03d}.wav"
        f.write_bytes(b"x")
        os.utime(f, (2000 + i, 2000 + i))
    # Cap 200 → 1 muss raus, das aelteste = a_000.wav (mtime 1000)
    deleted = enforce_fifo_cap(tmp_path, max_files=200)
    assert deleted == 1
    assert not (s20 / "a_000.wav").exists()
    assert (s20 / "a_001.wav").exists()
    assert (s40 / "b_100.wav").exists()


def test_fifo_cap_ignores_non_wav(tmp_path):
    sub = tmp_path / "20m_FT8"
    sub.mkdir()
    for i in range(5):
        (sub / f"x_{i}.wav").write_bytes(b"x")
    (sub / ".x_0.wav.abc.tmp").write_bytes(b"x")
    (sub / "readme.txt").write_bytes(b"x")
    deleted = enforce_fifo_cap(tmp_path, max_files=3)
    assert deleted == 2
    assert (sub / ".x_0.wav.abc.tmp").exists()
    assert (sub / "readme.txt").exists()


def test_fifo_cap_handles_unlink_error(tmp_path, monkeypatch):
    sub = tmp_path / "20m_FT8"
    sub.mkdir()
    for i in range(5):
        f = sub / f"f_{i}.wav"
        f.write_bytes(b"x")
        os.utime(f, (1_000_000 + i, 1_000_000 + i))

    real_unlink = Path.unlink
    call_count = [0]
    def flaky_unlink(self, *a, **kw):
        call_count[0] += 1
        if call_count[0] == 1:
            raise OSError("locked")
        return real_unlink(self, *a, **kw)
    monkeypatch.setattr(Path, "unlink", flaky_unlink)

    deleted = enforce_fifo_cap(tmp_path, max_files=3)
    assert deleted == 1


# ── Helper-Tests: build_dump_path ────────────────────────────────────────


def test_build_dump_path_basic(tmp_path):
    path = build_dump_path(tmp_path, "40m", "FT8", 1714824000.0, "ANT1")
    assert path.parent == tmp_path / "40m_FT8"
    assert path.name.endswith("_ANT1.wav")
    assert "FT8" in str(path.parent)


def test_build_dump_path_collision_v2_suffix(tmp_path):
    sub = tmp_path / "20m_FT8"
    sub.mkdir()
    path1 = build_dump_path(tmp_path, "20m", "FT8", 1714824000.0, "ANT2")
    path1.write_bytes(b"x")
    path2 = build_dump_path(tmp_path, "20m", "FT8", 1714824000.0, "ANT2")
    assert path2 != path1
    assert "_v2" in path2.name


def test_build_dump_path_timestamp_format(tmp_path):
    # 2026-05-08 14:23:00 UTC = 1778250180.0
    path = build_dump_path(tmp_path, "40m", "FT8", 1778250180.0, "ANT1")
    assert "2026-05-08_14-23-00" in path.name


# ── Decoder-Integration: Pull-Pattern dump_last_slot ─────────────────────


def test_decoder_dump_skips_non_ft8(tmp_path):
    """Decoder.dump_last_slot returnt False wenn Modus != FT8."""
    from core.decoder import Decoder
    d = Decoder(mode="FT4")
    d.last_audio_24k = _make_audio(2400)
    d.last_slot_start_utc = 1714824000.0
    d._band = "40m"
    result = d.dump_last_slot("ANT1", tmp_path, max_files=200)
    assert result is False
    assert list(tmp_path.glob("**/*.wav")) == []


def test_decoder_dump_writes_wav_in_ft8(tmp_path):
    """Decoder.dump_last_slot schreibt WAV bei FT8 + buffer != None."""
    from core.decoder import Decoder
    d = Decoder(mode="FT8")
    d.last_audio_24k = _make_audio(24000 * 13)  # ~13 s
    d.last_slot_start_utc = 1778250180.0
    d._band = "40m"
    result = d.dump_last_slot("ANT1", tmp_path, max_files=200)
    assert result is True
    wavs = list(tmp_path.glob("**/*.wav"))
    assert len(wavs) == 1
    assert "40m_FT8" in str(wavs[0])
    assert "_ANT1.wav" in wavs[0].name
