"""P10 PSK-Backoff-Reset (v0.97.15, Mai 2026).

Vorher (Bug): PSK-Reporter-Polling ging bei Server-Errors in
exponentielles Backoff bis 60 Min. Nach Recovery sah User stundenlang
keine PSK-Daten.

Jetzt:
- BACKOFF_MAX_S 3600 -> 600 (10 Min Cap).
- _Backoff thread-safe via threading.Lock (KP-2).
- PSKReporterClient.reset_backoff() public — Trigger bei Bandwechsel.
"""
from __future__ import annotations

import threading

from core import psk_reporter as _psk


def test_backoff_max_s_is_600():
    """T1: BACKOFF_MAX_S = 600 (10 Min), kein 3600 mehr."""
    assert _psk.BACKOFF_MAX_S == 600, (
        f"BACKOFF_MAX_S sollte 600 sein, ist {_psk.BACKOFF_MAX_S}"
    )


def test_backoff_reset_and_fail_sequenz():
    """T2: reset + fail funktionieren sequenziell wie bisher."""
    b = _psk._Backoff(base_s=120.0)
    assert b.current_s == 120.0
    b.fail()
    assert b.current_s == 180.0  # 120 * 1.5
    b.fail()
    assert b.current_s == 270.0  # 180 * 1.5
    b.reset()
    assert b.current_s == 120.0


def test_backoff_fail_capped_at_max():
    """T3: fail capped bei BACKOFF_MAX_S (600s)."""
    b = _psk._Backoff(base_s=120.0)
    # 120 -> 180 -> 270 -> 405 -> 600 (gekappt)
    for _ in range(20):
        b.fail()
    assert b.current_s == 600.0


def test_backoff_thread_safety_reset_during_fail():
    """T4 (R1-KP-2): Lock verhindert Race wenn reset() mid-fail() feuert.

    100 Threads die abwechselnd fail() und reset() rufen. Endwert
    muss entweder base_s (nach reset) oder >= base_s (nach fail) sein
    — nie ein gemischter ungueltiger Wert.
    """
    b = _psk._Backoff(base_s=100.0)

    def worker_fail():
        for _ in range(100):
            b.fail()

    def worker_reset():
        for _ in range(100):
            b.reset()

    threads = (
        [threading.Thread(target=worker_fail) for _ in range(5)]
        + [threading.Thread(target=worker_reset) for _ in range(5)]
    )
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # Final muss valid sein (zwischen base_s und max_s)
    assert 100.0 <= b.current_s <= 600.0, (
        f"Race-Ergebnis ungueltig: current_s={b.current_s}"
    )


def test_psk_reporter_client_has_reset_backoff_method():
    """T5: public reset_backoff() ist auf PSKReporterClient verfuegbar."""
    c = _psk.PSKReporterClient(callsign="DA1MHH", poll_interval_s=120)
    assert hasattr(c, "reset_backoff"), (
        "PSKReporterClient muss reset_backoff() haben"
    )
    # Fail einmal damit _backoff hochgeht
    c._backoff.fail()
    assert c._backoff.current_s > 120
    c.reset_backoff()
    assert c._backoff.current_s == 120, (
        "reset_backoff muss current_s auf base_s zuruecksetzen"
    )


def test_backoff_has_lock_attribute():
    """Bug-Schutz Source-Level: _Backoff hat _lock-Attribut."""
    b = _psk._Backoff(base_s=120.0)
    assert hasattr(b, "_lock"), "_Backoff muss thread-safe sein (KP-2)"
    # Sicherstellen dass _lock ein Lock-Objekt ist
    assert hasattr(b._lock, "acquire"), "_lock muss threading.Lock sein"


def test_set_mode_updates_internal_mode():
    """Final-R1 KP-1: PSKReporterClient.set_mode aktualisiert _mode."""
    c = _psk.PSKReporterClient(callsign="DA1MHH", mode="FT8")
    assert c._mode == "FT8"
    c.set_mode("FT4")
    assert c._mode == "FT4"
    # Case-insensitive Input
    c.set_mode("ft2")
    assert c._mode == "FT2"
    # Same-Mode-Aufruf ist no-op (idempotent)
    c.set_mode("FT2")
    assert c._mode == "FT2"
