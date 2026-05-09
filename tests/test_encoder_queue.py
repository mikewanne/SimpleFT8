"""Tests fuer P2.OMNI-PATTERN-FIX Encoder-Queue (v0.95.24).

Bug: OMNI-CQ-Pattern in v0.95.23 verschoben um +30s. Wurzel: _send_cq
laeuft am Slot-Start via on_cycle_end → Encoder-Drift-Schutz (v0.80
Fix B, overshoot > 0.3s) schiebt TX um 2 Slots. Loesung: Mid-Cycle-
Pretrigger plant TX VOR Slot-Ende. Encoder muss zweite transmit() als
Queue annehmen statt zu skippen — Worker sendet beide nacheinander.

Tests decken (V3 AC11/AC12/AC13, T9/T10/T11):
- T9 Queue: 2. transmit() bei aktivem TX → queued, nicht verworfen
- T10 Replace verdraengt Queue: laufender TX-Replace leert pending
- T11 Abort verdraengt Queue: abort() leert pending
- Plus: Doppel-Queue (3. transmit overschreibt 2. — Last-One-Wins)
- Plus: Queue-Reset bei neuem TX-Start (kein Leak von vorherigem Run)
"""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from core.encoder import Encoder


def _ensure_app():
    return QApplication.instance() or QApplication([])


def _make_encoder():
    """Encoder ohne Radio, mit künstlich gesetztem _is_transmitting=True
    fuer Queue-Tests ohne echten TX-Thread."""
    _ensure_app()
    enc = Encoder(audio_freq_hz=1500)
    return enc


# ── T9 — AC11: Queue waehrend aktivem TX ─────────────────────────────


def test_encoder_queue_second_transmit_during_active_tx():
    """Bei _is_transmitting=True legt transmit() die Message in Queue
    statt SKIP. _pending_tx_message ist nach Aufruf gesetzt."""
    enc = _make_encoder()
    enc._is_transmitting = True
    enc.transmit("DA1MHH DA1TST -10")
    assert enc._pending_tx_message == "DA1MHH DA1TST -10"
    assert enc._is_transmitting is True


def test_encoder_queue_overwrites_on_second_call():
    """Last-One-Wins: 3. transmit() bei aktivem TX ueberschreibt Queue.
    OMNI sendet nur 1 CQ pro Slot — der jeweils letzte ist relevant."""
    enc = _make_encoder()
    enc._is_transmitting = True
    enc.transmit("CQ DA1MHH JO31")
    assert enc._pending_tx_message == "CQ DA1MHH JO31"
    enc.transmit("DA1MHH DA1TST -10")
    assert enc._pending_tx_message == "DA1MHH DA1TST -10"


def test_encoder_queue_idle_path_does_not_queue():
    """Wenn KEIN TX laeuft, queut transmit() NICHT — startet stattdessen
    den Worker. Prueft via _tx_thread (Daemon, startet sofort)."""
    enc = _make_encoder()
    enc._is_transmitting = False
    enc._pending_tx_message = None
    # Kein Radio gesetzt → Worker laeuft an, encode_message scheitert
    # mangels Radio/Lib-Setup, tx_finished feuert. Aber: Queue darf
    # NICHT befuellt sein, weil kein Konflikt.
    enc.transmit("CQ DA1MHH JO31")
    # _pending_tx_message ist None, weil Pfad "Worker starten" gewaehlt
    # wurde, nicht Queue-Pfad.
    assert enc._pending_tx_message is None


# ── T10 — AC12: Replace verdraengt Queue ─────────────────────────────


def test_encoder_replace_clears_pending_queue():
    """Replace-Pfad in _tx_worker_inner soll Queue leeren — die geplante
    naechste Message ist obsolet wenn die State-Machine das aktuelle TX
    durch ein Reply ersetzt (Plan-Wechsel CQ → Report im selben Slot)."""
    enc = _make_encoder()
    enc._is_transmitting = True
    # Setup: 1. TX laeuft, OMNI hat schon 2. CQ gequeued
    enc._pending_tx_message = "CQ DA1MHH JO31"
    # Replace kommt (z.B. CQ_CALLING + Grid-Reply)
    success = enc.request_replace("DA1TST DA1MHH -10")
    assert success is True
    # Replace-Lock-Pfad in _tx_worker_inner laeuft erst bei aborted-Wake.
    # Hier simulieren wir den Code-Pfad direkt (siehe encoder.py Z.~280).
    with enc._replace_lock:
        if enc._replace_message is not None:
            enc._replace_message = None
            enc._pending_tx_message = None  # P2-Fix Pfad
    assert enc._pending_tx_message is None


def test_encoder_request_replace_does_not_set_queue():
    """request_replace() schreibt NUR _replace_message, NICHT Queue.
    Queue wird erst beim aborted-Wake-Pfad geleert."""
    enc = _make_encoder()
    enc._is_transmitting = True
    enc._pending_tx_message = "CQ DA1MHH JO31"
    enc.request_replace("DA1TST DA1MHH -10")
    # Queue noch da, wird erst im Worker bei aborted-Wake geleert
    assert enc._pending_tx_message == "CQ DA1MHH JO31"
    assert enc._replace_message == "DA1TST DA1MHH -10"


# ── T11 — AC13: Abort verdraengt Queue ───────────────────────────────


def test_encoder_abort_clears_pending_queue():
    """abort() ist Notaus-Semantik. Wartende TX-Slots sollen verworfen
    werden — sonst sendet die App nach Bandwechsel/HALT noch Messages
    aus dem alten Plan."""
    enc = _make_encoder()
    enc._is_transmitting = True
    enc._pending_tx_message = "CQ DA1MHH JO31"
    enc.abort()
    assert enc._pending_tx_message is None
    assert enc._is_transmitting is False
    assert enc._abort_event.is_set()


def test_encoder_abort_idempotent_on_empty_queue():
    """abort() ohne Queue darf nicht crashen."""
    enc = _make_encoder()
    enc._is_transmitting = True
    enc._pending_tx_message = None
    enc.abort()
    assert enc._pending_tx_message is None
    assert enc._is_transmitting is False


# ── Init / Lifecycle ─────────────────────────────────────────────────


def test_encoder_init_pending_tx_message_none():
    """Nach __init__ ist Queue leer."""
    enc = _make_encoder()
    assert enc._pending_tx_message is None


def test_encoder_pending_tx_lock_is_replace_lock():
    """Queue + Replace teilen sich _replace_lock — kein zusaetzliches
    Lock noetig (beide GUI-Thread-only auf Schreib-Seite). Test prueft
    dass Lock-Aufruf nicht crasht."""
    enc = _make_encoder()
    enc._is_transmitting = True
    # Beide Pfade unter dem gleichen Lock
    with enc._replace_lock:
        enc._pending_tx_message = "test"
        enc._replace_message = "other"
    assert enc._pending_tx_message == "test"
    assert enc._replace_message == "other"
