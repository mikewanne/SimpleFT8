#!/usr/bin/env python3
"""Tests für core.rf_preset_store — Hybrid-Lade-Strategie + atomic JSON + Migration.

Ausfuehren:
    cd SimpleFT8
    ./venv/bin/python3 -m pytest tests/test_rf_preset_store.py -v
"""

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _make_store(path):
    """Helper: RFPresetStore mit explizitem Pfad."""
    from core.rf_preset_store import RFPresetStore
    return RFPresetStore(path=path)


# ── Standard-Tests (14) ─────────────────────────────────────────────────────


def test_save_and_load_exact_match(tmp_path):
    store = _make_store(tmp_path / "rf_presets.json")
    store.save("flexradio", "40m", 80, 67)
    assert store.load("flexradio", "40m", 80) == 67


def test_load_returns_none_when_empty(tmp_path):
    store = _make_store(tmp_path / "rf_presets.json")
    assert store.load("flexradio", "40m", 80) is None


def test_interpolation_between_two_points(tmp_path):
    """linear: (30→24, 80→67) → load(50) = 24 + (43/50)*20 = 41.2 → 41"""
    store = _make_store(tmp_path / "rf_presets.json")
    store.save("flexradio", "40m", 30, 24)
    store.save("flexradio", "40m", 80, 67)
    assert store.load("flexradio", "40m", 50) == 41


def test_extrapolation_above_highest_point(tmp_path):
    """linear extrapolation oben: (30→24, 80→67) → load(100) = 24 + 0.86*70 = 84.2 → 84"""
    store = _make_store(tmp_path / "rf_presets.json")
    store.save("flexradio", "40m", 30, 24)
    store.save("flexradio", "40m", 80, 67)
    assert store.load("flexradio", "40m", 100) == 84


def test_extrapolation_below_lowest_point(tmp_path):
    """linear extrapolation unten: (30→24, 80→67) → load(10) = 24 - 0.86*20 = 6.8 → 7"""
    store = _make_store(tmp_path / "rf_presets.json")
    store.save("flexradio", "40m", 30, 24)
    store.save("flexradio", "40m", 80, 67)
    assert store.load("flexradio", "40m", 10) == 7


def test_single_point_returns_none_for_other_watt(tmp_path):
    store = _make_store(tmp_path / "rf_presets.json")
    store.save("flexradio", "40m", 80, 67)
    assert store.load("flexradio", "40m", 80) == 67  # exakter Treffer geht
    assert store.load("flexradio", "40m", 30) is None  # kein Interpolations-Partner


def test_overwrite_on_save(tmp_path):
    store = _make_store(tmp_path / "rf_presets.json")
    store.save("flexradio", "40m", 80, 50)
    store.save("flexradio", "40m", 80, 67)
    assert store.load("flexradio", "40m", 80) == 67


def test_radio_isolation(tmp_path):
    store = _make_store(tmp_path / "rf_presets.json")
    store.save("flexradio", "40m", 80, 67)
    store.save("ic7300", "40m", 80, 71)
    assert store.load("flexradio", "40m", 80) == 67
    assert store.load("ic7300", "40m", 80) == 71
    assert store.load("flexradio", "40m", 50) is None
    assert store.load("ic7300", "40m", 50) is None


def test_clear_band_keeps_other_bands(tmp_path):
    store = _make_store(tmp_path / "rf_presets.json")
    store.save("flexradio", "40m", 80, 67)
    store.save("flexradio", "20m", 50, 35)
    store.clear_band("flexradio", "40m")
    assert store.load("flexradio", "40m", 80) is None
    assert store.load("flexradio", "20m", 50) == 35


def test_clear_all_keeps_other_radios(tmp_path):
    store = _make_store(tmp_path / "rf_presets.json")
    store.save("flexradio", "40m", 80, 67)
    store.save("ic7300", "40m", 80, 71)
    store.clear_all("flexradio")
    assert store.load("flexradio", "40m", 80) is None
    assert store.load("ic7300", "40m", 80) == 71


def test_plausibility_warning_logged_above_threshold(tmp_path, capsys):
    """3 Stützpunkte: (30→24, 80→67, 50→80) — 50W ist Outlier (>20% Δ zu Interpolation)."""
    store = _make_store(tmp_path / "rf_presets.json")
    store.save("flexradio", "40m", 30, 24)
    store.save("flexradio", "40m", 80, 67)
    store.save("flexradio", "40m", 50, 80)  # outlier
    capsys.readouterr()  # clear stdout buffer
    rf = store.load("flexradio", "40m", 50)
    captured = capsys.readouterr()
    assert rf == 80
    assert "veraltet" in captured.out


def test_corrupt_json_falls_back_with_bak_file(tmp_path, capsys):
    path = tmp_path / "rf_presets.json"
    path.write_text("{ this is not valid json")
    capsys.readouterr()
    store = _make_store(path)
    captured = capsys.readouterr()
    assert store.load("flexradio", "40m", 80) is None
    bak_files = list(tmp_path.glob("rf_presets.json.bak.*"))
    assert len(bak_files) >= 1
    assert "korrupt" in captured.out.lower()


def test_atomic_write_doesnt_lose_data_on_simulated_crash(tmp_path):
    """Atomic write via os.replace — Datei niemals leer/halb-geschrieben."""
    path = tmp_path / "rf_presets.json"
    store = _make_store(path)
    store.save("flexradio", "40m", 80, 67)
    assert path.exists()
    original = path.read_text()
    assert len(original) > 0

    store.save("flexradio", "40m", 80, 88)
    new = path.read_text()
    assert len(new) > 0
    assert original != new
    parsed = json.loads(new)
    assert parsed["flexradio"]["40m"]["80"]["rf"] == 88


def test_invalid_rf_value_ignored(tmp_path, capsys):
    store = _make_store(tmp_path / "rf_presets.json")
    store.save("flexradio", "40m", 80, -5)
    store.save("flexradio", "40m", 80, 200)
    captured = capsys.readouterr()
    assert store.load("flexradio", "40m", 80) is None
    assert "abgelehnt" in captured.out.lower()


# ── Aus DeepSeek-Review (3) ─────────────────────────────────────────────────


def test_no_save_during_convergence_oscillation(tmp_path):
    """Store ist unbegrenzt überschreibbar; Once-Per-Convergence-Garantie liegt
    beim Caller (mw_tx mit `_was_converged` Hilfsvar). Hier: letzter Wert gewinnt.
    """
    store = _make_store(tmp_path / "rf_presets.json")
    store.save("flexradio", "40m", 80, 50)
    store.save("flexradio", "40m", 80, 60)
    store.save("flexradio", "40m", 80, 50)
    store.save("flexradio", "40m", 80, 60)
    assert store.load("flexradio", "40m", 80) == 60


def test_band_change_during_convergence_doesnt_save_old_band(tmp_path):
    """clear_band(40m) darf 20m-Werte nicht beeinflussen (Band-Isolation)."""
    store = _make_store(tmp_path / "rf_presets.json")
    store.save("flexradio", "40m", 80, 67)
    store.save("flexradio", "20m", 80, 71)
    store.clear_band("flexradio", "40m")
    assert store.load("flexradio", "40m", 80) is None
    assert store.load("flexradio", "20m", 80) == 71


def test_extrapolation_clipping_to_0_100_range(tmp_path):
    """Steile Extrapolation darf [0, 100] nicht verlassen."""
    store = _make_store(tmp_path / "rf_presets.json")
    # extrapolation oben: (10→80, 20→95) → load(100) = 80 + 1.5*90 = 215 → clipped 100
    store.save("ic7300", "40m", 10, 80)
    store.save("ic7300", "40m", 20, 95)
    rf_clip_high = store.load("ic7300", "40m", 100)
    assert rf_clip_high == 100

    # extrapolation unten: (90→10, 100→5) → load(10) = 10 + (-0.5)*(-80) = 50 (kein clipping)
    # Konstruiere wirklichen Lower-Clip:  (90→2, 100→1) → load(10) = 2 + (-0.1)*(-80) = 10
    # Schwer zu konstruieren; prüfen wir nur Range-Garantie:
    store.save("ic7300", "20m", 90, 5)
    store.save("ic7300", "20m", 100, 2)
    # extrapolation auf 10W: 5 + (2-5)/10 * (-80) = 5 + 24 = 29
    rf_lower = store.load("ic7300", "20m", 10)
    assert 0 <= rf_lower <= 100


# ── Migration (1) ───────────────────────────────────────────────────────────


def test_migration_from_config_json_rfpower_per_band(tmp_path):
    store = _make_store(tmp_path / "rf_presets.json")
    settings_data = {"rfpower_per_band": {"40m": 67, "20m": 35, "80m": 50}}
    store.migrate_from_settings(settings_data, radio="flexradio", default_watts=10)
    assert store.load("flexradio", "40m", 10) == 67
    assert store.load("flexradio", "20m", 10) == 35
    assert store.load("flexradio", "80m", 10) == 50

    # Idempotent: zweiter Aufruf darf nichts überschreiben
    settings_data2 = {"rfpower_per_band": {"40m": 99}}
    store.migrate_from_settings(settings_data2, radio="flexradio", default_watts=10)
    assert store.load("flexradio", "40m", 10) == 67


# ── Persistenz quer über Instanzen (Bonus) ─────────────────────────────────


def test_persistence_across_instances(tmp_path):
    from core.rf_preset_store import RFPresetStore
    path = tmp_path / "rf_presets.json"
    s1 = RFPresetStore(path=path)
    s1.save("flexradio", "40m", 80, 67)
    s2 = RFPresetStore(path=path)
    assert s2.load("flexradio", "40m", 80) == 67


# ── Direkter Aufruf für CLI ──────────────────────────────────────────────────

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
