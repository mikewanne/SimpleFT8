"""P48 — DT-System aufraeumen + tunen (v0.97.13).

15 Tests fuer 4 Teile:
- A: Settings-Block radio_timing (tx_buffer_s + rx_hardware_offset_default_s)
- B: Cross-Modus-Fallback FT8 > FT4 > FT2 auf gleichem Band
- C: Hardware-Default als Kaltstart (statt 0.0)
- D: Schnell-Konvergenz bei >=10 Stationen mit kleiner Streuung

Wichtig: _is_initial = _saved.get(_mode_key()) is None (P48-Fix fuer R1-Bug).
Cross-Modus-Fallback und Hardware-Default zaehlen NICHT als eigene Messung.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest


# ── P48-A Settings ───────────────────────────────────────────────────────


def test_settings_has_radio_timing_defaults(tmp_path, monkeypatch):
    """Frische Settings hat tx_buffer_s=1.3 und rx_hardware_offset_default_s=0.26."""
    import config.settings as cs
    monkeypatch.setattr(cs, "CONFIG_FILE", tmp_path / "config.json")
    monkeypatch.setattr(cs, "CONFIG_DIR", tmp_path)

    s = cs.Settings()
    assert s.tx_buffer_s == 1.3
    assert s.rx_hardware_offset_default_s == 0.26


def test_settings_backward_compat_no_radio_timing_block(tmp_path, monkeypatch):
    """Alte config.json ohne radio_timing-Block laedt mit Property-Defaults."""
    cfg = tmp_path / "config.json"
    cfg.write_text(json.dumps({"callsign": "DA1MHH"}))
    import config.settings as cs
    monkeypatch.setattr(cs, "CONFIG_FILE", cfg)
    monkeypatch.setattr(cs, "CONFIG_DIR", tmp_path)

    s = cs.Settings()
    # Properties greifen auf Defaults zurueck, kein KeyError
    assert s.tx_buffer_s == 1.3
    assert s.rx_hardware_offset_default_s == 0.26


# ── Fixture fuer ntp_time-State ──────────────────────────────────────────


@pytest.fixture
def fresh_ntp(monkeypatch):
    """Frischer DT-Modul-State fuer deterministische Tests.

    _DT_FILE-Schutz kommt schon aus conftest.py.
    """
    import core.ntp_time as nt
    monkeypatch.setattr(nt, "_saved", {})
    monkeypatch.setattr(nt, "_correction", 0.0)
    monkeypatch.setattr(nt, "_hardware_default_offset", 0.0)
    monkeypatch.setattr(nt, "_last_logged_load", None)
    monkeypatch.setattr(nt, "_mode", "FT8")
    monkeypatch.setattr(nt, "_band", "20m")
    monkeypatch.setattr(nt, "_phase", "measure")
    monkeypatch.setattr(nt, "_is_initial", True)
    monkeypatch.setattr(nt, "_cycle_count", 0)
    monkeypatch.setattr(nt, "_measure_buffer", [])
    yield nt


# ── P48-C Hardware-Default ───────────────────────────────────────────────


def test_load_for_current_key_returns_hardware_default(fresh_ntp):
    """Keine eigenen, keine Geschwister-Werte → Hardware-Default."""
    nt = fresh_ntp
    nt._hardware_default_offset = 0.26
    assert nt._load_for_current_key() == 0.26


def test_hardware_default_setter():
    """set_hardware_default schreibt Modul-Var."""
    import core.ntp_time as nt
    nt.set_hardware_default(0.3)
    assert nt._hardware_default_offset == 0.3
    nt.set_hardware_default(0.0)  # reset


# ── P48-B Cross-Modus-Fallback ───────────────────────────────────────────


def test_cross_mode_ft2_prefers_ft8_over_ft4(fresh_ntp):
    """FT2 nimmt FT8 vor FT4 (FT8-Median solider per R1-Finding 4)."""
    nt = fresh_ntp
    nt._saved = {"FT8_30m": 0.27, "FT4_30m": 0.25}
    nt._mode = "FT2"
    nt._band = "30m"
    assert nt._load_for_current_key() == 0.27


def test_cross_mode_ft2_falls_back_to_ft4_when_no_ft8(fresh_ntp):
    """Wenn FT8 leer, FT2 → FT4."""
    nt = fresh_ntp
    nt._saved = {"FT4_30m": 0.25}
    nt._mode = "FT2"
    nt._band = "30m"
    assert nt._load_for_current_key() == 0.25


def test_cross_mode_ft4_uses_ft8(fresh_ntp):
    """FT4 nimmt FT8-Wert vom gleichen Band."""
    nt = fresh_ntp
    nt._saved = {"FT8_30m": 0.27}
    nt._mode = "FT4"
    nt._band = "30m"
    assert nt._load_for_current_key() == 0.27


def test_cross_mode_no_fallback_for_ft8(fresh_ntp):
    """FT8 ist Master — nutzt keinen FT4/FT2-Fallback."""
    nt = fresh_ntp
    nt._saved = {"FT4_30m": 0.27}
    nt._hardware_default_offset = 0.26
    nt._mode = "FT8"
    nt._band = "30m"
    # FT8 ignoriert FT4 als Fallback → Hardware-Default
    assert nt._load_for_current_key() == 0.26


def test_cross_mode_prefers_own_value(fresh_ntp):
    """Eigener gemessener Wert hat IMMER Vorrang vor Fallback."""
    nt = fresh_ntp
    nt._saved = {"FT2_30m": 0.29, "FT8_30m": 0.27}
    nt._hardware_default_offset = 0.26
    nt._mode = "FT2"
    nt._band = "30m"
    assert nt._load_for_current_key() == 0.29


# ── P48 _is_initial Bug-Fix (R1-Finding 1) ───────────────────────────────


def test_is_initial_true_with_hardware_default(fresh_ntp):
    """Mit Hardware-Default 0.26 geladen, aber _is_initial bleibt True
    (Bug-Fix R1-Finding 1: eigene Messung als Kriterium, nicht saved_val=0.0).
    """
    nt = fresh_ntp
    nt._hardware_default_offset = 0.26
    nt.set_mode("FT8", "20m")
    assert nt._is_initial is True, \
        "Hardware-Default-Wert geladen, aber als eigene Messung verkannt"
    assert nt._correction == 0.26


def test_is_initial_false_when_own_measurement_exists(fresh_ntp):
    """Eigener Wert vorhanden → _is_initial = False."""
    nt = fresh_ntp
    nt._saved = {"FT8_20m": 0.27}
    nt.set_mode("FT8", "20m")
    assert nt._is_initial is False
    assert nt._correction == 0.27


def test_is_initial_true_after_cross_mode_fallback(fresh_ntp):
    """Cross-Modus-Fallback liefert Wert, aber _is_initial bleibt True
    (kein eigener Wert auf Disk fuer diese Mode-Band-Kombi).
    """
    nt = fresh_ntp
    nt._saved = {"FT8_30m": 0.27}
    nt.set_mode("FT2", "30m")
    assert nt._is_initial is True, \
        "FT2 hat keinen eigenen Wert — _is_initial sollte True bleiben"
    assert nt._correction == 0.27  # Cross-Modus von FT8


# ── P48-D Schnell-Konvergenz ─────────────────────────────────────────────


def test_fast_convergence_with_hardware_default(fresh_ntp):
    """Realer Default-Pfad: Hardware-Default 0.26 + 12 Stationen mit kleiner
    Streuung → 1 Slot reicht (Fast-Path).
    """
    nt = fresh_ntp
    nt._hardware_default_offset = 0.26
    nt.set_mode("FT8", "20m")
    assert nt._is_initial is True

    # 12 Stationen mit DT ~0 (Korrektur passt schon ungefaehr)
    result = nt.update_from_decoded([0.0] * 12)

    # Fast-Path → phase wechselt nach 1 Slot auf "operate"
    assert result is True, "Sollte True (Mess-Phase abgeschlossen) liefern"
    assert nt._phase == "operate", f"Phase sollte 'operate' sein, war '{nt._phase}'"
    assert nt._cycle_count == 0  # nach Wechsel auf operate zurueckgesetzt


def test_fast_convergence_high_stdev_blocked(fresh_ntp):
    """Hohe Streuung → kein Fast-Path, wartet auf 2 Slots."""
    nt = fresh_ntp
    nt._hardware_default_offset = 0.26
    nt.set_mode("FT8", "20m")

    # 12 Stationen mit Stddev > 0.1 (alterniert 0.0/0.5)
    high_stdev_values = [0.0, 0.5] * 6
    result = nt.update_from_decoded(high_stdev_values)

    # 1. Slot ohne Fast-Path → noch keine Korrektur
    assert result is False, "1. Slot ohne Fast-Path sollte False liefern"
    assert nt._phase == "measure"
    assert nt._cycle_count == 1


def test_fast_convergence_few_stations_blocked(fresh_ntp):
    """Wenig Stationen (<10) → kein Fast-Path."""
    nt = fresh_ntp
    nt._hardware_default_offset = 0.26
    nt.set_mode("FT8", "20m")

    # 5 Stationen mit kleiner Streuung — aber unter Schwelle
    result = nt.update_from_decoded([0.0, 0.01, -0.01, 0.02, 0.0])

    # Kein Fast-Path (zu wenig Stationen) → 1. Slot bleibt in measure
    assert result is False
    assert nt._phase == "measure"
    assert nt._cycle_count == 1


# ── P48-A Encoder tx_buffer_s ────────────────────────────────────────────


def test_encoder_tx_offset_default_flex():
    """Encoder Default tx_buffer_s=1.3 → target_tx_offset_s = -0.8 (alter Wert)."""
    from core.encoder import Encoder
    enc = Encoder(1500)
    assert enc.target_tx_offset_s == pytest.approx(-0.8, abs=1e-9)


def test_encoder_tx_offset_custom_buffer():
    """Encoder mit IC-7300-Buffer 1.0s → target_tx_offset_s = -0.5."""
    from core.encoder import Encoder
    enc = Encoder(1500, tx_buffer_s=1.0)
    assert enc.target_tx_offset_s == pytest.approx(-0.5, abs=1e-9)
