"""P48/P171 — DT-System.

- A: Settings-Block radio_timing (tx_buffer_s + rx_hardware_offset_default_s)
- P171: EIN globaler Korrekturwert (gelernt nur aus FT8, von allen Modi/Baendern
  genutzt). Seed via Hardware-Default; Mode-/Band-Wechsel behaelt den Wert;
  FT4/FT2 schreiben nie; Migration alt-per-(Modus,Band) → Median der FT8-Werte.
- D: Schnell-Konvergenz bei >=10 Stationen mit kleiner Streuung (FT8).

P171 (03.06.2026) ersetzte den frueheren per-(Modus,Band)-Speicher +
Cross-Modus-Fallback (P48-B) durch einen Globalwert.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest


# ── P48-A Settings ───────────────────────────────────────────────────────


def test_settings_radio_timing_empty_by_default(tmp_path, monkeypatch):
    """P121 (2026-05-25): Defaults kommen vom Radio, nicht aus Settings.

    radio_timing-Block ist standardmäßig leer. Settings liefert None für
    User-Overrides (Aufrufer fällt auf radio.tx_buffer_s zurück).
    Hardware-Konstanten 1.3/0.26 sind jetzt in FlexRadio.tx_buffer_s
    bzw. FlexRadio.rx_hardware_offset_default_s.
    """
    import config.settings as cs
    monkeypatch.setattr(cs, "CONFIG_FILE", tmp_path / "config.json")
    monkeypatch.setattr(cs, "CONFIG_DIR", tmp_path)

    s = cs.Settings()
    assert s.get_user_tx_buffer_override() is None
    assert s.get_user_rx_hardware_offset_override() is None

    # FlexRadio-Klasse liefert die ehemaligen Settings-Defaults:
    from radio.flexradio import FlexRadio
    assert FlexRadio.tx_buffer_s == 1.3
    assert FlexRadio.rx_hardware_offset_default_s == 0.26


def test_settings_backward_compat_no_radio_timing_block(tmp_path, monkeypatch):
    """Alte config.json ohne radio_timing-Block: keine User-Overrides aktiv."""
    cfg = tmp_path / "config.json"
    cfg.write_text(json.dumps({"callsign": "DA1MHH"}))
    import config.settings as cs
    monkeypatch.setattr(cs, "CONFIG_FILE", cfg)
    monkeypatch.setattr(cs, "CONFIG_DIR", tmp_path)

    s = cs.Settings()
    # Kein User-Override → None → Aufrufer nutzt Radio-Default
    assert s.get_user_tx_buffer_override() is None
    assert s.get_user_rx_hardware_offset_override() is None


# ── Fixture fuer ntp_time-State ──────────────────────────────────────────


@pytest.fixture
def fresh_ntp(monkeypatch):
    """Frischer DT-Modul-State fuer deterministische Tests (P171 Globalwert).

    _DT_FILE-Schutz kommt schon aus conftest.py.
    """
    import core.ntp_time as nt
    monkeypatch.setattr(nt, "_correction", 0.0)
    monkeypatch.setattr(nt, "_hardware_default_offset", 0.0)
    monkeypatch.setattr(nt, "_mode", "FT8")
    monkeypatch.setattr(nt, "_band", "20m")
    monkeypatch.setattr(nt, "_phase", "measure")
    monkeypatch.setattr(nt, "_is_initial", True)
    monkeypatch.setattr(nt, "_cycle_count", 0)
    monkeypatch.setattr(nt, "_measure_buffer", [])
    yield nt


# ── P171 Seed (Hardware-Default) ──────────────────────────────────────────


def test_hardware_default_seeds_when_empty(fresh_ntp):
    """set_hardware_default seedet _correction, wenn global noch leer."""
    nt = fresh_ntp
    nt.set_hardware_default(0.26)
    assert nt._hardware_default_offset == 0.26
    assert nt._correction == 0.26
    assert nt._is_initial is True   # Seed zaehlt nicht als eigene Messung


def test_hardware_default_does_not_override_measured(fresh_ntp):
    """Seed greift NICHT, wenn schon ein gemessener/migrierter Wert da ist."""
    nt = fresh_ntp
    nt._correction = 0.27
    nt._is_initial = False
    nt.set_hardware_default(0.26)
    assert nt._correction == 0.27


# ── P171 Globalwert bleibt ueber Mode-/Band-Wechsel ───────────────────────


def test_set_mode_keeps_global_correction(fresh_ntp):
    """Kern P171: Umschalten auf FT4/FT2 behaelt den (FT8-)Korrekturwert."""
    nt = fresh_ntp
    nt._correction = 0.26
    nt._is_initial = False
    nt.set_mode("FT4", "20m")
    assert nt._correction == 0.26 and nt._is_initial is False
    nt.set_mode("FT2", "40m")
    assert nt._correction == 0.26
    nt.set_band("15m")
    assert nt._correction == 0.26


def test_ft4_ft2_do_not_write(fresh_ntp):
    """FT4/FT2: update_from_decoded ist No-op (kein Lernen/Schreiben)."""
    nt = fresh_ntp
    nt._correction = 0.26
    nt._is_initial = False
    nt.set_mode("FT4", "20m")
    assert nt.update_from_decoded([0.5] * 10) is False
    assert nt._correction == 0.26
    nt.set_mode("FT2", "20m")
    assert nt.update_from_decoded([0.5] * 10) is False
    assert nt._correction == 0.26


def test_ft8_learns_and_persists(fresh_ntp):
    """FT8 misst weiterhin (Erstkorrektur) und schreibt das neue Format."""
    import json
    nt = fresh_ntp
    nt.set_mode("FT8", "20m")
    nt._is_initial = True
    nt.update_from_decoded([0.5] * 5)
    nt.update_from_decoded([0.5] * 5)   # 2 Slots → Erstkorrektur
    assert abs(nt._correction - 0.5) < 0.05
    assert nt._is_initial is False
    data = json.loads(nt._DT_FILE.read_text())
    assert "dt_correction_s" in data


# ── P171 Migration alt→global ─────────────────────────────────────────────


def test_migration_old_format_to_global_median(fresh_ntp, tmp_path, monkeypatch):
    """Alte per-(Modus,Band)-json → globaler Wert = Median der FT8-Werte;
    FT4/FT2-Ausreisser (FT4_20m=0.045) werden verworfen."""
    import json
    nt = fresh_ntp
    f = tmp_path / "old_dt.json"
    f.write_text(json.dumps({
        "FT8_20m": 0.27, "FT8_40m": 0.30, "FT8_30m": 0.24,
        "FT4_20m": 0.045, "FT2_20m": 0.246,
    }))
    monkeypatch.setattr(nt, "_DT_FILE", f)
    nt._load_saved()
    assert nt._correction == 0.27   # Median(0.27,0.30,0.24); 0.045 ignoriert
    assert nt._is_initial is False


def test_new_format_loaded(fresh_ntp, tmp_path, monkeypatch):
    """Neues Single-Value-Format wird direkt geladen."""
    import json
    nt = fresh_ntp
    f = tmp_path / "new_dt.json"
    f.write_text(json.dumps({"dt_correction_s": 0.255}))
    monkeypatch.setattr(nt, "_DT_FILE", f)
    nt._load_saved()
    assert nt._correction == 0.255
    assert nt._is_initial is False


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
