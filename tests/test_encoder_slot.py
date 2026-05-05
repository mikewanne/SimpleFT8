"""Test fuer Encoder.tx_started-Signal-Migration (V3 Commit 5).

R1-Empfehlung: verifiziere dass das erweiterte Signal (str, bool, float)
korrekt emittiert und dass alle drei Werte beim Listener ankommen.
"""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication
from core.encoder import Encoder


def _ensure_app():
    return QApplication.instance() or QApplication([])


def test_tx_started_signal_signature():
    """tx_started ist Signal(str, bool, float)."""
    _ensure_app()
    enc = Encoder()
    # PySide6 Signal-Objekt hat keine direkte API zum Abfragen der Signatur,
    # aber wir koennen einen 3-Arg-Listener anschliessen und manuell emit.
    received = []
    enc.tx_started.connect(
        lambda msg, te, sst: received.append((msg, te, sst))
    )
    enc.tx_started.emit("CQ DA1MHH J031", True, 1730000100.0)
    assert len(received) == 1
    msg, te, sst = received[0]
    assert msg == "CQ DA1MHH J031"
    assert te is True
    assert sst == 1730000100.0


def test_tx_started_listener_gets_all_three_args():
    """Wenn ein Listener mit drei Args verbunden ist, kommen alle drei
    Werte korrekt typisiert an."""
    _ensure_app()
    enc = Encoder()

    captured = {}
    def slot(message, tx_even, slot_start_ts):
        captured["msg"] = message
        captured["even"] = tx_even
        captured["sst"] = slot_start_ts

    enc.tx_started.connect(slot)
    enc.tx_started.emit("test", False, 1730000115.0)

    assert captured["msg"] == "test"
    assert captured["even"] is False
    assert isinstance(captured["sst"], float)
    assert captured["sst"] == 1730000115.0
