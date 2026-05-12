"""Tests fuer P41 — audio_streaming-Flag im Encoder.

Bug 12.05.2026: encoder.is_transmitting blieb waehrend OMNI-CQ
durchgaengig True (Worker-Setup-/Sleep-Phase zaehlte mit), blockte
Antennen-Switch in mw_cycle.py ueber 20 Slots in Folge.

Fix: feinerer Flag is_audio_streaming — True NUR von ptt_on bis
ptt_off (deckt FlexRadio-Buffer-Latenz mit ab, Antennen-Switch in
Slot-Setup-Phasen sicher moeglich).

Test-Strategie (R1-Empfehlung): _tx_worker_inner mit Mock-Radio
laufen lassen + Flag-Zustaende um die einzelnen Phasen pruefen.
"""
from __future__ import annotations

import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import sys
import time
import threading
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
from PySide6.QtWidgets import QApplication

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from core.encoder import Encoder  # noqa: E402


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


# ─── Statische Property-Tests ──────────────────────────────────────────

def test_is_audio_streaming_false_at_init(app):
    """T1: Bei frischem Encoder ist is_audio_streaming False."""
    enc = Encoder()
    assert enc.is_audio_streaming is False


def test_is_audio_streaming_is_property(app):
    """T2: is_audio_streaming ist eine Property (Read-Only)."""
    enc = Encoder()
    # Read funktioniert
    assert enc.is_audio_streaming is False
    # Write auf Property gibt AttributeError
    with pytest.raises(AttributeError):
        enc.is_audio_streaming = True


def test_is_audio_streaming_independent_from_is_transmitting(app):
    """T3: is_audio_streaming und is_transmitting sind getrennte Flags.

    Wichtig: is_transmitting (alt) blieb waehrend ganzem Worker-Lauf
    True. is_audio_streaming (neu) ist NUR waehrend Audio-Streaming
    True. Bei Init beide False.
    """
    enc = Encoder()
    assert enc.is_transmitting is False
    assert enc.is_audio_streaming is False


# ─── TX-Worker-Lifecycle Tests ────────────────────────────────────────

def _make_mock_radio():
    """Mock-Radio fuer Encoder mit ptt_on/ptt_off/send_audio."""
    radio = MagicMock()
    radio.ptt_on = MagicMock()
    radio.ptt_off = MagicMock()
    radio.send_audio = MagicMock()
    radio.set_tx_antenna = MagicMock()
    return radio


def test_audio_streaming_true_during_send_audio(app):
    """T4: is_audio_streaming ist True waehrend Radio.send_audio() laeuft."""
    enc = Encoder()
    enc._radio = _make_mock_radio()

    captured = {"during_send_audio": None}

    def fake_send_audio(*args, **kwargs):
        # Beim Aufruf von send_audio sollte Flag True sein
        captured["during_send_audio"] = enc.is_audio_streaming

    enc._radio.send_audio = MagicMock(side_effect=fake_send_audio)

    # Worker direkt aufrufen (ohne Thread). _tx_worker setzt normal
    # _is_transmitting=True, beim Direkt-Aufruf von _tx_worker_inner
    # muss das manuell gesetzt sein (sonst returnt Z.302 vor Audio).
    enc._is_transmitting = True
    fake_audio = np.zeros(12000 * 14, dtype=np.int16)
    with patch.object(enc, "encode_message", return_value=fake_audio):
        # _next_slot_boundary auf 0 setzen (kein Sleep)
        with patch.object(enc, "_next_slot_boundary", return_value=time.time() - 10):
            enc._tx_worker_inner("CQ DA1MHH JO31")

    assert captured["during_send_audio"] is True, \
        f"Flag muss waehrend send_audio True sein, war: {captured['during_send_audio']}"


def test_audio_streaming_false_after_worker_completes(app):
    """T5: Nach _tx_worker_inner ist Flag wieder False (ptt_off Pfad)."""
    enc = Encoder()
    enc._radio = _make_mock_radio()
    fake_audio = np.zeros(12000 * 14, dtype=np.int16)

    enc._is_transmitting = True
    with patch.object(enc, "encode_message", return_value=fake_audio):
        with patch.object(enc, "_next_slot_boundary", return_value=time.time() - 10):
            enc._tx_worker_inner("CQ DA1MHH JO31")

    assert enc.is_audio_streaming is False


def test_audio_streaming_false_after_encoding_error(app):
    """T6: Bei Encoding-Error (audio_12k=None) wird Flag NIE True."""
    enc = Encoder()
    enc._radio = _make_mock_radio()

    with patch.object(enc, "encode_message", return_value=None):
        enc._tx_worker_inner("INVALID")

    # Flag wurde nie auf True gesetzt (Worker returnt vor ptt_on)
    assert enc.is_audio_streaming is False
    # send_audio darf nicht aufgerufen worden sein
    enc._radio.send_audio.assert_not_called()


def test_audio_streaming_reset_by_worker_finally_safety_net(app):
    """T7: _tx_worker finally setzt Flag zurueck (Safety-Net bei Exception).

    Simuliert Exception waehrend send_audio. Flag wurde gesetzt vorher,
    Exception fliegt, finally muss Flag wieder False setzen.
    """
    enc = Encoder()
    enc._radio = _make_mock_radio()
    enc._radio.send_audio = MagicMock(side_effect=RuntimeError("FlexRadio gone"))
    fake_audio = np.zeros(12000 * 14, dtype=np.int16)

    with patch.object(enc, "encode_message", return_value=fake_audio):
        with patch.object(enc, "_next_slot_boundary", return_value=time.time() - 10):
            # _tx_worker wrappt _tx_worker_inner mit finally
            try:
                enc._tx_worker("CQ DA1MHH JO31")
            except RuntimeError:
                pass  # erwartet

    assert enc.is_audio_streaming is False, \
        "Safety-Net im finally muss Flag auch bei Exception zuruecksetzen"


def test_abort_does_not_touch_audio_streaming(app):
    """T8 (R1-KRITISCH): abort() darf is_audio_streaming NICHT anfassen.

    Wenn abort() Flag manuell auf False setzen wuerde, aber Worker noch
    laeuft (send_audio blockt), wuerde naechster _on_cycle_start einen
    Antennen-Switch ausloesen waehrend Audio noch im FlexRadio-Buffer
    streamt. is_audio_streaming muss NUR vom Worker selbst verwaltet
    werden.
    """
    enc = Encoder()
    enc._audio_streaming = True  # simuliere laufendes Streaming
    enc._is_transmitting = True

    enc.abort()

    # is_transmitting wird von abort gesetzt (alte Logik) — OK
    assert enc.is_transmitting is False
    # is_audio_streaming bleibt UNVERAENDERT — abort lasst es in Ruhe
    assert enc.is_audio_streaming is True, \
        "abort() darf is_audio_streaming nicht manipulieren " \
        "(Worker-finally setzt es nach ptt_off zurueck)"
