"""Tests fuer P1.9 First-Reply-Lost-Fix (v0.95.3).

Bug: Decoder-Encoder-Race fuehrte zu 1-Slot-Verzoegerung beim ersten Reply
auf eine CQ. CQ-Audio war bereits in send_audio (BLOCKING) wenn
_pending_reply gesetzt wurde → Report 1 Slot zu spaet.

Fix-Kombination: Decoder-Wake 1.5 → 2.5 (slot+12.5 statt slot+13.5) +
Encoder request_replace API + Worker-Loop fuer Re-Encode + State-Machine
Trigger-Signal + Defense-in-Depth in _send_cq.

Tests decken:
1-3: Encoder request_replace API (Erfolg, zu spaet, kein TX)
4: Defense-in-Depth in _send_cq
5: try_replace_pending_tx Signal-Trigger bei CQ_CALLING + Grid
"""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from core.encoder import Encoder
from core.qso_state import QSOStateMachine, QSOState
from core.message import FT8Message


def _ensure_app():
    return QApplication.instance() or QApplication([])


# ── Encoder request_replace API ──────────────────────────────────────


def test_encoder_request_replace_during_sleep():
    """P1.9: Replace setzt _replace_message + weckt Worker via abort_event."""
    _ensure_app()
    enc = Encoder(audio_freq_hz=1500)
    enc._is_transmitting = True
    enc._audio_started = False
    success = enc.request_replace("DA1TST DA1MHH -10")
    assert success is True
    assert enc._replace_message == "DA1TST DA1MHH -10"
    assert enc._abort_event.is_set()


def test_encoder_request_replace_too_late():
    """P1.9: Replace nach _audio_started=True wird abgelehnt."""
    _ensure_app()
    enc = Encoder(audio_freq_hz=1500)
    enc._is_transmitting = True
    enc._audio_started = True
    success = enc.request_replace("DA1TST DA1MHH -10")
    assert success is False
    assert enc._replace_message is None


def test_encoder_request_replace_no_tx():
    """P1.9: Replace ohne laufenden TX → False."""
    _ensure_app()
    enc = Encoder(audio_freq_hz=1500)
    enc._is_transmitting = False
    success = enc.request_replace("DA1TST DA1MHH -10")
    assert success is False
    assert enc._replace_message is None


# ── State-Machine Defense-in-Depth + Trigger ─────────────────────────


def _make_grid_msg(caller="DA1TST", target="DA1MHH", grid="JN66",
                   snr=-15, freq=1500):
    """FT8Message mit Grid-Reply an target."""
    return FT8Message(
        raw=f"{target} {caller} {grid}",
        field1=target,
        field2=caller,
        field3=grid,
        snr=snr,
        freq_hz=freq,
    )


def test_send_cq_with_pending_reply_processes_instead():
    """P1.9 Defense-in-Depth: _send_cq mit pending Reply → process statt CQ."""
    _ensure_app()
    sm = QSOStateMachine("DA1MHH", "JO31")
    sm.cq_mode = True
    msg = _make_grid_msg()
    sm._pending_reply = msg
    captured = []
    sm.send_message.connect(captured.append)
    sm._send_cq()
    # Erwartet: Report-TX (DA1TST DA1MHH ...), nicht CQ
    assert len(captured) == 1
    assert "DA1TST DA1MHH" in captured[0]
    assert not captured[0].startswith("CQ ")
    assert sm._pending_reply is None
    assert sm.state == QSOState.TX_REPORT


def test_cq_calling_grid_reply_emits_try_replace():
    """P1.9: CQ_CALLING + Grid-Reply → try_replace_pending_tx Signal."""
    _ensure_app()
    sm = QSOStateMachine("DA1MHH", "JO31")
    sm.cq_mode = True
    sm._set_state(QSOState.CQ_CALLING)
    captured = []
    sm.try_replace_pending_tx.connect(captured.append)
    msg = _make_grid_msg()
    sm.on_message_received(msg)
    assert len(captured) == 1
    assert captured[0] is msg
    # _pending_reply bleibt gesetzt — Fallback auf on_message_sent wenn
    # Replace zu spaet kommt.
    assert sm._pending_reply is msg
