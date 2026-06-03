"""Tests fuer den modus-abhaengigen DT-Versatz (_MODE_DELTA, 03.06.2026).

Field-Diagnose: FT8 braucht ~+0.29s Korrektur, FT4 effektiv ~0 (Versatz ~-0.30).
`get_correction()` liefert jetzt `_correction + _MODE_DELTA[_mode]` — eine Quelle
fuer RX-Decode-Shift, TX-Timing und Anzeige.

monkeypatch setzt die Modul-Globals und rollt sie nach jedem Test zurueck →
kein State-Leak in andere Tests.
"""

import time as _time

import pytest

import core.ntp_time as ntp


def test_mode_delta_constants():
    assert ntp._MODE_DELTA["FT8"] == 0.0
    assert ntp._MODE_DELTA["FT4"] == -0.30
    assert ntp._MODE_DELTA["FT2"] == 0.0


def test_ft8_correction_equals_base(monkeypatch):
    """FT8 ist die Lern-Basis (Delta 0) → effektive Korrektur == _correction."""
    monkeypatch.setattr(ntp, "_correction", 0.29)
    monkeypatch.setattr(ntp, "_mode", "FT8")
    assert ntp.get_correction() == pytest.approx(0.29)


def test_ft4_correction_has_delta(monkeypatch):
    """FT4 bekommt den festen Versatz -0.30 → effektiv ~0 (zentriert)."""
    monkeypatch.setattr(ntp, "_correction", 0.29)
    monkeypatch.setattr(ntp, "_mode", "FT4")
    assert ntp.get_correction() == pytest.approx(0.29 - 0.30)


def test_unknown_mode_falls_back_to_base(monkeypatch):
    """Unbekannter Modus → Delta-Default 0 (kein KeyError, kein Versatz)."""
    monkeypatch.setattr(ntp, "_correction", 0.29)
    monkeypatch.setattr(ntp, "_mode", "CW")
    assert ntp.get_correction() == pytest.approx(0.29)


def test_get_time_uses_effective_correction(monkeypatch):
    """get_time() (TX-Timing) muss den Modus-Delta beruecksichtigen."""
    monkeypatch.setattr(ntp, "_correction", 0.29)
    monkeypatch.setattr(_time, "time", lambda: 1000.0)
    monkeypatch.setattr(ntp, "_mode", "FT8")
    assert ntp.get_time() == pytest.approx(1000.29)
    monkeypatch.setattr(ntp, "_mode", "FT4")
    assert ntp.get_time() == pytest.approx(1000.0 + 0.29 - 0.30)


def test_rx_shift_difference_between_modes(monkeypatch):
    """Der RX-Decode-Shift (= get_correction * SAMP_RATE) unterscheidet FT8/FT4
    um exakt den Delta → FT4-Fenster 0.30s weniger verschoben."""
    monkeypatch.setattr(ntp, "_correction", 0.29)
    monkeypatch.setattr(ntp, "_mode", "FT8")
    corr_ft8 = ntp.get_correction()
    monkeypatch.setattr(ntp, "_mode", "FT4")
    corr_ft4 = ntp.get_correction()
    assert (corr_ft8 - corr_ft4) == pytest.approx(0.30)


def test_status_text_shows_effective_value(monkeypatch):
    """Statusleiste zeigt die EFFEKTIVE Korrektur des aktuellen Modus."""
    monkeypatch.setattr(ntp, "_correction", 0.29)
    monkeypatch.setattr(ntp, "_mode", "FT4")
    monkeypatch.setattr(ntp, "_last_sample_count", 5)
    txt = ntp.get_status_text()
    assert "-0.01" in txt          # 0.29 - 0.30 = -0.01


def test_ft8_unchanged_status(monkeypatch):
    """Auf FT8 bleibt die Anzeige identisch zum Basiswert (keine Regression)."""
    monkeypatch.setattr(ntp, "_correction", 0.29)
    monkeypatch.setattr(ntp, "_mode", "FT8")
    monkeypatch.setattr(ntp, "_last_sample_count", 11)
    txt = ntp.get_status_text()
    assert "+0.29" in txt
