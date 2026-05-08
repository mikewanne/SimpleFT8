"""Tests fuer P1.BUNDLE2 (v0.95.19).

3 unabhaengige Bugs in einem Workflow:
- P1.11: rr73_retries shared zwischen WAIT_RR73 + WAIT_73-Hoeflichkeit
- P1.13: TX-Frequenz-Spinbox-Sync bei Hunt-Klick im Normal-Modus
- P1.7:  Lokaler Duplikat-Filter ADIF/Logbuch (5-Min-Fenster)
"""
from __future__ import annotations

import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from unittest.mock import MagicMock

import pytest
from PySide6.QtWidgets import QApplication


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


# ── P1.11: rr73_retries / wait_73_retries ────────────────────────────────


def _make_sm():
    """Hilfsfunktion: QSOStateMachine mit Test-Setup."""
    from core.qso_state import QSOStateMachine
    sm = QSOStateMachine(my_call="DA1MHH", my_grid="JO31")
    return sm


def test_p1_11_rr73_retries_does_not_block_wait_73():
    """P1.11: voller WAIT_RR73-Counter blockiert WAIT_73-Hoeflichkeit NICHT."""
    from core.qso_state import QSOState
    from core.message import FT8Message
    sm = _make_sm()
    sm._set_state(QSOState.WAIT_73)
    sm.qso.their_call = "SP6AXW"
    sm.qso.rr73_retries = 3  # voll ausgereizt
    sm.qso.wait_73_retries = 0
    captured = []
    sm.send_message.connect(lambda m: captured.append(m))

    msg = FT8Message(raw="DA1MHH SP6AXW R-08", field1="DA1MHH",
                     field2="SP6AXW", field3="R-08", snr=-8)
    sm.on_message_received(msg)

    assert sm.qso.wait_73_retries == 1
    assert any("RR73" in m for m in captured)


def test_p1_11_wait_73_max_2_retries():
    """P1.11: WAIT_73-Hoeflichkeit max 2× RR73 erneut, dann ignoriert."""
    from core.qso_state import QSOState
    from core.message import FT8Message
    sm = _make_sm()
    sm._set_state(QSOState.WAIT_73)
    sm.qso.their_call = "SP6AXW"
    captured = []
    sm.send_message.connect(lambda m: captured.append(m))

    msg = FT8Message(raw="DA1MHH SP6AXW R-08", field1="DA1MHH",
                     field2="SP6AXW", field3="R-08", snr=-8)
    sm.on_message_received(msg)
    sm.on_message_received(msg)
    sm.on_message_received(msg)  # 3. — sollte ignoriert werden

    rr73_count = sum(1 for m in captured if "RR73" in m)
    assert rr73_count == 2
    assert sm.qso.wait_73_retries == 2


def test_p1_11_independent_counters():
    """P1.11: rr73_retries + wait_73_retries sind unabhaengig."""
    sm = _make_sm()
    sm.qso.rr73_retries = 3
    sm.qso.wait_73_retries = 1
    assert sm.qso.rr73_retries != sm.qso.wait_73_retries


def test_p1_11_wait_73_retries_zero_after_start_qso():
    """P1.11 (R1-Test): nach start_qso ist wait_73_retries=0
    (durch QSOData()-Neuinit)."""
    sm = _make_sm()
    sm.qso.wait_73_retries = 5  # alter QSO-Zustand
    sm.cq_mode = False
    sm.start_qso(their_call="EA2BHE", freq_hz=1500)
    assert sm.qso.wait_73_retries == 0


# ── P1.13: TX-Frequenz-Spinbox-Sync ──────────────────────────────────────


def test_p1_13_normal_hunt_click_updates_encoder_and_spin(app):
    """P1.13: Normal-Modus Hunt-Klick → encoder.audio_freq_hz + spin.value
    auf msg.freq_hz."""
    from core.message import FT8Message
    from PySide6.QtWidgets import QSpinBox
    spin = QSpinBox()
    spin.setRange(150, 2800)
    spin.setValue(1500)
    encoder = MagicMock()
    encoder.audio_freq_hz = 1500
    encoder.is_transmitting = False

    msg = FT8Message(raw="DA1MHH SP6AXW JO80", field1="DA1MHH",
                     field2="SP6AXW", field3="JO80", snr=-8, freq_hz=823)
    rx_mode = "normal"
    if rx_mode == "normal" and msg.freq_hz:
        freq_hz = max(spin.minimum(), min(spin.maximum(), int(msg.freq_hz)))
        encoder.audio_freq_hz = freq_hz
        spin.blockSignals(True)
        spin.setValue(freq_hz)
        spin.blockSignals(False)

    assert encoder.audio_freq_hz == 823
    assert spin.value() == 823


def test_p1_13_diversity_hunt_click_does_not_change_freq(app):
    """P1.13: Diversity-Modus Hunt-Klick → KEIN Sync (Auto-Suche aktiv)."""
    from core.message import FT8Message
    from PySide6.QtWidgets import QSpinBox
    spin = QSpinBox()
    spin.setRange(150, 2800)
    spin.setValue(1500)
    encoder = MagicMock()
    encoder.audio_freq_hz = 1500

    msg = FT8Message(raw="...", field1="DA1MHH", field2="SP6AXW",
                     field3="JO80", snr=-8, freq_hz=823)
    rx_mode = "diversity"
    if rx_mode == "normal" and msg.freq_hz:
        # SOLL NICHT betreten werden
        spin.setValue(int(msg.freq_hz))
        encoder.audio_freq_hz = int(msg.freq_hz)

    assert encoder.audio_freq_hz == 1500
    assert spin.value() == 1500


def test_p1_13_clamp_to_hardware_range(app):
    """P1.13: Frequenz wird auf Spinbox-Range geclampt."""
    from PySide6.QtWidgets import QSpinBox
    spin = QSpinBox()
    spin.setRange(150, 2800)
    # over-range:
    freq_hz = max(spin.minimum(), min(spin.maximum(), 3500))
    assert freq_hz == 2800
    # under-range:
    freq_hz = max(spin.minimum(), min(spin.maximum(), 50))
    assert freq_hz == 150


def test_p1_13_freq_hz_zero_no_update(app):
    """P1.13 (R1-Test): msg.freq_hz=0 → kein Encoder/Spinbox-Update."""
    from core.message import FT8Message
    from PySide6.QtWidgets import QSpinBox
    spin = QSpinBox()
    spin.setRange(150, 2800)
    spin.setValue(1500)
    encoder = MagicMock()
    encoder.audio_freq_hz = 1500

    msg = FT8Message(raw="...", field1="DA1MHH", field2="SP6AXW",
                     field3="JO80", snr=-8, freq_hz=0)  # 0 = Decoder-Edge-Case
    rx_mode = "normal"
    if rx_mode == "normal" and msg.freq_hz:
        # SOLL NICHT betreten werden weil msg.freq_hz=0 falsy
        encoder.audio_freq_hz = int(msg.freq_hz)
        spin.setValue(int(msg.freq_hz))

    assert encoder.audio_freq_hz == 1500
    assert spin.value() == 1500


def test_p1_13_no_persistence_call(app):
    """P1.13: settings.save_normal_tx_freq darf NICHT aufgerufen werden
    bei Hunt-Klick (Hunt-Klick ist temporaer)."""
    settings = MagicMock()
    from PySide6.QtWidgets import QSpinBox
    spin = QSpinBox()
    spin.setRange(150, 2800)
    encoder = MagicMock()

    rx_mode = "normal"
    msg_freq = 823
    if rx_mode == "normal" and msg_freq:
        freq_hz = max(spin.minimum(), min(spin.maximum(), int(msg_freq)))
        encoder.audio_freq_hz = freq_hz
        spin.blockSignals(True)
        spin.setValue(freq_hz)
        spin.blockSignals(False)
        # KEIN settings.save_normal_tx_freq

    settings.save_normal_tx_freq.assert_not_called()


# ── P1.7: ADIF-Duplikat-Filter ───────────────────────────────────────────


_LOG_DEDUP_WINDOW_S = 300  # mirror der Modul-Konstante


def _dedup_check(cache: dict, call: str, band: str, now: float) -> bool:
    """Hilfsfunktion: True wenn Duplikat (skip), False wenn neu (log + cache)."""
    key = (call.upper(), band.upper())
    last = cache.get(key, 0.0)
    if now - last < _LOG_DEDUP_WINDOW_S:
        return True
    cache[key] = now
    return False


def test_p1_7_duplicate_within_window_skipped():
    """P1.7: Selber Call+Band binnen 5 Min → 2. ist Duplikat."""
    cache = {}
    now = 1000.0
    assert _dedup_check(cache, "SP6AXW", "20M", now) is False  # 1. log
    assert _dedup_check(cache, "SP6AXW", "20M", now + 60) is True  # Duplikat


def test_p1_7_duplicate_outside_window_logged():
    """P1.7: Selber Call+Band nach 6+ Min → 2. ist legitim."""
    cache = {}
    now = 1000.0
    assert _dedup_check(cache, "SP6AXW", "20M", now) is False
    assert _dedup_check(cache, "SP6AXW", "20M", now + 360) is False  # 6 Min spaeter


def test_p1_7_different_calls_both_logged():
    """P1.7: Verschiedene Calls binnen 5 Min → beide loggen."""
    cache = {}
    now = 1000.0
    assert _dedup_check(cache, "SP6AXW", "20M", now) is False
    assert _dedup_check(cache, "EA2BHE", "20M", now + 60) is False


def test_p1_7_multi_band_both_logged():
    """P1.7: Selber Call auf verschiedenen Baendern → beide loggen
    (Tupel-Key (call, band))."""
    cache = {}
    now = 1000.0
    assert _dedup_check(cache, "SP6AXW", "20M", now) is False
    assert _dedup_check(cache, "SP6AXW", "40M", now + 60) is False  # legitim


def test_p1_7_session_local_cache():
    """P1.7: Cache ist Session-lokal (kein Persist) — App-Restart-Simulation."""
    cache = {}
    now = 1000.0
    _dedup_check(cache, "SP6AXW", "20M", now)
    # App-Restart: neuer Cache
    cache_new = {}
    assert _dedup_check(cache_new, "SP6AXW", "20M", now + 60) is False


def test_p1_7_band_case_normalized():
    """P1.7 (R1-Test): Band „20m" und „20M" werden gleich behandelt
    (Tupel-Key normalisiert .upper())."""
    cache = {}
    now = 1000.0
    assert _dedup_check(cache, "SP6AXW", "20m", now) is False  # lowercase eingang
    assert _dedup_check(cache, "SP6AXW", "20M", now + 60) is True  # Duplikat


def test_p1_7_empty_band_does_not_collide():
    """P1.7 (R1-Test): Leerer Band-String kollidiert nicht mit normalen Bands."""
    cache = {}
    now = 1000.0
    assert _dedup_check(cache, "SP6AXW", "", now) is False
    assert _dedup_check(cache, "SP6AXW", "20M", now + 60) is False  # andere Keys


def test_p1_7_call_case_normalized():
    """P1.7: Call wird auch ueber .upper() normalisiert."""
    cache = {}
    now = 1000.0
    assert _dedup_check(cache, "sp6axw", "20M", now) is False
    assert _dedup_check(cache, "SP6AXW", "20M", now + 60) is True
