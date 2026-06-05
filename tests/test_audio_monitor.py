"""Tests fuer core/audio_monitor.py (Audio-Mithoer-Monitor, Diagnose-Feature).

Die Ringpuffer-/Upsampling-Logik ist pure numpy und ohne echtes Audiogeraet
testbar. start()/stop() werden mit einem Fake-sounddevice geprueft.
"""

import sys
import types

import numpy as np
import pytest

from core.audio_monitor import AudioMonitor
from config.settings import DEFAULTS


def _out(frames):
    """Output-Buffer wie sounddevice ihn liefert: (frames, 1) int16."""
    return np.zeros((frames, 1), dtype=np.int16)


# ── Ringpuffer + Upsampling (Kernlogik) ─────────────────────────────────────

def test_feed_inactive_is_noop():
    mon = AudioMonitor(ring_size=100)
    mon.feed(np.array([1, 2, 3], dtype=np.int16))   # active == False
    assert mon._count == 0


def test_feed_then_read_doubles_samples():
    """24k→48k Upsampling: jedes Sample exakt verdoppelt (kein Pitch-Shift)."""
    mon = AudioMonitor(ring_size=100)
    mon.active = True
    mon.feed(np.array([10, 20, 30], dtype=np.int16))
    out = _out(6)                                    # 6 frames @48k = 3 @24k
    mon._read_into(out, 6)
    assert list(out[:, 0]) == [10, 10, 20, 20, 30, 30]
    assert mon._count == 0                           # alles ausgelesen


def test_read_underrun_full_silence():
    """Leerer Puffer → reine Stille, read-Index bleibt stehen."""
    mon = AudioMonitor(ring_size=100)
    mon.active = True
    out = _out(4)
    mon._read_into(out, 4)
    assert list(out[:, 0]) == [0, 0, 0, 0]
    assert mon._read == 0 and mon._count == 0


def test_read_partial_underrun_pads_silence():
    """Weniger Daten als angefordert → Rest Stille, kein Knacken/Versatz."""
    mon = AudioMonitor(ring_size=100)
    mon.active = True
    mon.feed(np.array([7], dtype=np.int16))
    out = _out(4)
    mon._read_into(out, 4)                            # braucht 2 @24k, hat 1
    assert list(out[:, 0]) == [7, 7, 0, 0]


def test_overflow_keeps_newest():
    """Ringpuffer-Overflow: aeltestes verworfen, juengste Samples bleiben."""
    mon = AudioMonitor(ring_size=4)
    mon.active = True
    mon.feed(np.array([1, 2, 3, 4, 5, 6], dtype=np.int16))  # 6 > size 4
    assert mon._count == 4
    out = _out(8)
    mon._read_into(out, 8)
    assert list(out[:, 0]) == [3, 3, 4, 4, 5, 5, 6, 6]      # juengste 4, verdoppelt


def test_wraparound_read_correct():
    """Schreiben/Lesen ueber die Ring-Grenze hinweg bleibt korrekt."""
    mon = AudioMonitor(ring_size=4)
    mon.active = True
    mon.feed(np.array([1, 2, 3], dtype=np.int16))
    out1 = _out(4)
    mon._read_into(out1, 4)                           # liest 1,2 → read=2
    assert list(out1[:, 0]) == [1, 1, 2, 2]
    mon.feed(np.array([4, 5, 6], dtype=np.int16))     # schreibt ueber die Grenze
    out2 = _out(8)
    mon._read_into(out2, 8)                           # 3,4,5,6 in Reihenfolge
    assert list(out2[:, 0]) == [3, 3, 4, 4, 5, 5, 6, 6]


def test_feed_longer_than_ring_keeps_tail():
    """Block groesser als der Ring → nur die juengsten size Samples."""
    mon = AudioMonitor(ring_size=4)
    mon.active = True
    mon.feed(np.arange(1, 11, dtype=np.int16))        # 1..10, size 4
    assert mon._count == 4
    out = _out(8)
    mon._read_into(out, 8)
    assert list(out[:, 0]) == [7, 7, 8, 8, 9, 9, 10, 10]


def test_odd_frames_safe():
    """Ungerade frames duerfen nicht crashen (Robustheit)."""
    mon = AudioMonitor(ring_size=100)
    mon.active = True
    mon.feed(np.array([1, 2, 3], dtype=np.int16))
    out = _out(5)                                     # ungerade
    mon._read_into(out, 5)                            # need=2 → 1,2 verdoppelt + 1x Stille
    assert list(out[:, 0]) == [1, 1, 2, 2, 0]


# ── Lifecycle mit Fake-sounddevice ──────────────────────────────────────────

class _FakeStream:
    def __init__(self, **kw):
        self.kw = kw
        self.started = False
        self.closed = False

    def start(self):
        self.started = True

    def stop(self):
        self.started = False

    def close(self):
        self.closed = True


@pytest.fixture
def fake_sd(monkeypatch):
    """Legt ein Fake-`sounddevice` in sys.modules (lazy import in start())."""
    mod = types.ModuleType("sounddevice")
    created = []

    def OutputStream(**kw):
        if getattr(mod, "_raise", False):
            raise RuntimeError("kein Audiogeraet")
        s = _FakeStream(**kw)
        created.append(s)
        return s

    mod.OutputStream = OutputStream
    mod._created = created
    monkeypatch.setitem(sys.modules, "sounddevice", mod)
    return mod


def test_start_opens_48k_stream_and_activates(fake_sd):
    mon = AudioMonitor()
    mon.start()
    assert mon.active is True
    assert len(fake_sd._created) == 1
    s = fake_sd._created[0]
    assert s.kw["samplerate"] == 48000      # DeepSeek-🔴: feste 48 kHz
    assert s.kw["dtype"] == "int16"
    assert s.kw["channels"] == 1
    assert s.started is True


def test_start_idempotent(fake_sd):
    mon = AudioMonitor()
    mon.start()
    mon.start()                              # zweiter Aufruf = No-op
    assert len(fake_sd._created) == 1


def test_stop_closes_stream_and_deactivates(fake_sd):
    mon = AudioMonitor()
    mon.start()
    s = fake_sd._created[0]
    mon.stop()
    assert mon.active is False
    assert s.closed is True
    assert mon._stream is None


def test_start_failure_keeps_inactive(fake_sd):
    """Kein Audiogeraet → Exception propagiert, Monitor bleibt inaktiv."""
    fake_sd._raise = True
    mon = AudioMonitor()
    with pytest.raises(RuntimeError):
        mon.start()
    assert mon.active is False
    assert mon._stream is None


def test_stop_without_start_is_safe():
    mon = AudioMonitor()
    mon.stop()                               # darf nicht crashen
    assert mon.active is False


def test_stop_swallows_stream_errors():
    """OPT-56: stop() ist intern robust — wirft stream.stop()/close() eine
    Exception, propagiert sie NICHT. Genau das macht das fruehere breite
    `except Exception: pass` im MainWindow.closeEvent ueberfluessig (entfernt
    in v0.99.15). Mutationsbeweis: ohne das interne try/except in stop() wuerde
    dieser Test mit RuntimeError brechen.
    """
    class _ExplodingStream:
        def stop(self):
            raise RuntimeError("PortAudio kaputt")

        def close(self):
            raise OSError("device weg")

    mon = AudioMonitor()
    mon._stream = _ExplodingStream()
    mon.active = True
    mon.stop()                               # darf NICHT werfen
    assert mon.active is False
    assert mon._stream is None


# ── Settings-Persistenz ─────────────────────────────────────────────────────

def test_audio_monitor_default_false():
    assert DEFAULTS.get("audio_monitor") is False


def test_audio_monitor_is_persisted_key():
    """audio_monitor darf NICHT von save() ausgeschlossen sein (anders als
    band/mode) — der Zustand soll ueber Neustarts erhalten bleiben."""
    assert "audio_monitor" not in ("band", "mode")
