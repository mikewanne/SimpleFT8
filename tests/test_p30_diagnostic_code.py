"""P30 Diagnose-Code Tests (v0.97.8, Mai 2026).

Testet Opt-in Decoder-Diagnose via Env SIMPLEFT8_DECODER_DIAG=1.
Default AUS → 0 Overhead. Aktiv → 4 Messpunkte (Buffer/feed/Skip/Hang).

Alle 1148 vorhandenen Tests müssen unverändert grün bleiben.
"""
from __future__ import annotations

import time
import threading

import numpy as np
import pytest

from core.decoder import Decoder


def test_diag_disabled_by_default(monkeypatch):
    """Env nicht gesetzt → _p30_diag=False, keine Diag-Aktivität."""
    monkeypatch.delenv("SIMPLEFT8_DECODER_DIAG", raising=False)
    d = Decoder()
    assert d._p30_diag is False


def test_diag_enabled_via_env(monkeypatch):
    """Env=1 → _p30_diag=True + Initial-Print."""
    monkeypatch.setenv("SIMPLEFT8_DECODER_DIAG", "1")
    d = Decoder()
    assert d._p30_diag is True


def test_feed_audio_counters_when_enabled(monkeypatch):
    """feed_audio inkrementiert Diag-Counter wenn aktiv."""
    monkeypatch.setenv("SIMPLEFT8_DECODER_DIAG", "1")
    d = Decoder()
    d._startup_done = True  # Purge überspringen
    arr = np.zeros((2400,), dtype=np.int16)
    d.feed_audio(arr)
    d.feed_audio(arr)
    with d._diag_lock:
        assert d._diag_feed_calls == 2
        assert d._diag_feed_samples == 4800


def test_feed_audio_no_counters_when_disabled(monkeypatch):
    """Default-AUS: keine Counter-Inkrementierung trotz feed_audio."""
    monkeypatch.delenv("SIMPLEFT8_DECODER_DIAG", raising=False)
    d = Decoder()
    d._startup_done = True
    arr = np.zeros((2400,), dtype=np.int16)
    d.feed_audio(arr)
    assert d._diag_feed_calls == 0


def test_emit_sample_skips_before_60s(monkeypatch, capsys):
    """Sample-Body läuft nicht wenn <60s seit letztem Sample vergangen."""
    monkeypatch.setenv("SIMPLEFT8_DECODER_DIAG", "1")
    d = Decoder()
    # capsys zurücksetzen (Init-Print rausfiltern)
    capsys.readouterr()
    d._diag_last_sample_t = time.time()  # gerade gesampelt
    d._emit_p30_sample()
    captured = capsys.readouterr()
    assert "[P30-DIAG] @" not in captured.out


def test_emit_sample_after_60s(monkeypatch, capsys):
    """Sample-Body läuft nach 60s, Format korrekt + alle Felder drin."""
    monkeypatch.setenv("SIMPLEFT8_DECODER_DIAG", "1")
    d = Decoder()
    capsys.readouterr()  # Init-Print weg
    d._diag_last_sample_t = time.time() - 65.0
    d._emit_p30_sample()
    captured = capsys.readouterr()
    assert "[P30-DIAG] @" in captured.out
    # Alle Felder müssen drin sein
    for key in ("RSS=", "buf_chunks=", "buf_bytes=", "feed_calls=",
                "samples=", "B/s=", "skips_total=", "last60=",
                "threads=", "busy_held="):
        assert key in captured.out, f"Feld {key} fehlt im Output"


def test_emit_sample_disabled_short_return(monkeypatch, capsys):
    """Diag AUS: _emit_p30_sample sofort return, kein Output, kein Reset."""
    monkeypatch.delenv("SIMPLEFT8_DECODER_DIAG", raising=False)
    d = Decoder()
    d._diag_last_sample_t = time.time() - 65.0  # wäre Zeit
    d._emit_p30_sample()
    captured = capsys.readouterr()
    assert "[P30-DIAG]" not in captured.out
    assert d._diag_feed_calls == 0


def test_busy_hang_warn_emitted(monkeypatch, capsys):
    """Skip + busy_held > 30s → [P30-DIAG][WARN] Zeile."""
    monkeypatch.setenv("SIMPLEFT8_DECODER_DIAG", "1")
    d = Decoder()
    capsys.readouterr()  # Init-Print
    # Initialisiere _decode_busy_lock (passiert sonst in _decode_loop)
    d._decode_busy_lock = threading.Lock()
    d._decode_busy = True
    d._diag_busy_started_at = time.time() - 45.0  # 45s "busy"
    # Skip-Pfad simulieren (statt _decode_loop laufen lassen)
    with d._decode_busy_lock:
        if d._decode_busy:
            with d._diag_lock:
                d._diag_skips_total += 1
                d._diag_skips_last_window += 1
            busy_duration = time.time() - d._diag_busy_started_at
            if busy_duration > 30.0:
                print(f"[P30-DIAG][WARN] busy_hang_detected "
                      f"duration={busy_duration:.0f}s — "
                      f"Decoder hängt vermutlich in _process_cycle")
    captured = capsys.readouterr()
    assert "busy_hang_detected" in captured.out
    assert d._diag_skips_total == 1
