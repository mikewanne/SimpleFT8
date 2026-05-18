#!/usr/bin/env python3
"""Tests fuer core.preset_store — P80 (v0.97.52) Unified Gain-Store.

API: ``band``-only (kein FT-Modus mehr), ``ant2_calibrated``-Feld.

Ausfuehren:
    cd SimpleFT8
    ./venv/bin/python3 -m pytest tests/test_preset_store.py -v
"""

import json
import os
import sys
import time

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture
def store_factory(tmp_path, monkeypatch):
    """PresetStore-Factory die ueber tmp_path isoliert.

    Pflicht: SETTINGS_PATH umlenken (sonst greift Migration auf echte
    Settings-Datei zu). CALIB_DIR ebenfalls.
    """
    from core import preset_store as ps_mod
    monkeypatch.setattr(ps_mod, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(ps_mod, "CALIB_DIR", tmp_path / "kalibrierung")
    monkeypatch.setattr(ps_mod, "SETTINGS_PATH", tmp_path / "settings.json")

    def _factory(filename: str = "presets.json"):
        return ps_mod.PresetStore(filename)
    return _factory


# ── Save-Tests ────────────────────────────────────────────────────────────


def test_save_gain_sets_gain_timestamp_and_ant2_calibrated(store_factory):
    """save_gain() setzt gain_timestamp + ant2_calibrated."""
    store = store_factory()
    store.save_gain("40m", rxant="ANT1",
                    ant1_gain=10, ant2_gain=20,
                    ant1_avg=-8.0, ant2_avg=-10.0)
    entry = store.get("40m")
    assert entry is not None
    assert "gain_timestamp" in entry
    assert entry["ant1_gain"] == 10
    assert entry["ant2_gain"] == 20
    assert entry["ant2_calibrated"] is True  # Default


def test_save_gain_with_ant2_calibrated_false(store_factory):
    """ant2_calibrated=False (Normal-only) wird respektiert."""
    store = store_factory()
    store.save_gain("40m", rxant="ANT1",
                    ant1_gain=10, ant2_gain=0,
                    ant2_calibrated=False)
    entry = store.get("40m")
    assert entry["ant2_calibrated"] is False


def test_save_gain_returns_false_on_disk_error(store_factory, monkeypatch):
    store = store_factory()
    monkeypatch.setattr(
        store, "_save_locked",
        lambda: (_ for _ in ()).throw(OSError("disk full"))
    )
    ok = store.save_gain("40m", rxant="ANT1",
                         ant1_gain=10, ant2_gain=20)
    assert ok is False


# ── Validity ───────────────────────────────────────────────────────────────


def test_is_valid_gain_within_6h_window(store_factory):
    store = store_factory()
    store.save_gain("40m", rxant="ANT1", ant1_gain=10, ant2_gain=20)
    assert store.is_valid_gain("40m") is True


def test_is_valid_gain_after_6h_returns_false(store_factory):
    from core import preset_store as ps_mod
    store = store_factory()
    store.save_gain("40m", rxant="ANT1", ant1_gain=10, ant2_gain=20)
    entry = store._data["40m"]
    entry["gain_timestamp"] -= (ps_mod.GAIN_VALIDITY_SECONDS + 1)
    assert store.is_valid_gain("40m") is False


def test_is_valid_gain_returns_false_when_no_entry(store_factory):
    store = store_factory()
    assert store.is_valid_gain("40m") is False


def test_is_valid_gain_false_when_timestamp_zero(store_factory):
    """P80 R1-F7: ts=0.0 ist Migration-Marker → is_valid_gain=False."""
    store = store_factory()
    store.save_gain("40m", rxant="ANT1", ant1_gain=10, ant2_gain=20)
    # Manuell auf 0.0 setzen wie nach Migration aus normal_preset
    # ohne parsbares measured
    store._data["40m"]["gain_timestamp"] = 0.0
    assert store.is_valid_gain("40m") is False


def test_legacy_is_valid_aliases_to_gain(store_factory):
    store = store_factory()
    store.save_gain("40m", rxant="ANT1", ant1_gain=10, ant2_gain=20)
    assert store.is_valid("40m") is True


def test_legacy_get_age_minutes_aliases_to_gain(store_factory):
    store = store_factory()
    store.save_gain("40m", rxant="ANT1", ant1_gain=10, ant2_gain=20)
    age_legacy = store.get_age_minutes("40m")
    age_new = store.get_gain_age_minutes("40m")
    assert age_legacy == age_new


# ── Stage / Commit / Discard (P80: band-only) ─────────────────────────────


def test_stage_gain_no_disk_write(store_factory, tmp_path):
    store = store_factory()
    store.stage_gain("40m", rxant="ANT1", ant1_gain=10, ant2_gain=20)
    expected = tmp_path / "kalibrierung" / "presets.json"
    assert not expected.exists()
    assert store.has_staged("40m") is True


def test_commit_gain_writes_atomic(store_factory, tmp_path):
    store = store_factory()
    store.stage_gain("40m", rxant="ANT1", ant1_gain=10, ant2_gain=20)
    ok = store.commit_gain("40m")
    assert ok is True
    assert store.has_staged("40m") is False
    expected = tmp_path / "kalibrierung" / "presets.json"
    assert expected.exists()
    data = json.loads(expected.read_text())
    assert data["40m"]["ant1_gain"] == 10
    assert data["40m"]["ant2_calibrated"] is True


def test_commit_without_stage_returns_false(store_factory):
    store = store_factory()
    ok = store.commit_gain("40m")
    assert ok is False


def test_commit_gain_disk_error_keeps_staged(store_factory, monkeypatch):
    store = store_factory()
    store.stage_gain("40m", rxant="ANT1", ant1_gain=10, ant2_gain=20)
    monkeypatch.setattr(
        store, "_save_locked",
        lambda: (_ for _ in ()).throw(OSError("disk full"))
    )
    ok = store.commit_gain("40m")
    assert ok is False
    assert store.has_staged("40m") is True


def test_discard_staged_clears_memory(store_factory):
    store = store_factory()
    store.stage_gain("40m", rxant="ANT1", ant1_gain=10, ant2_gain=20)
    removed = store.discard_staged("40m")
    assert removed is True
    assert store.has_staged("40m") is False


def test_discard_all_staged_clears_all(store_factory):
    store = store_factory()
    store.stage_gain("40m", rxant="ANT1", ant1_gain=10, ant2_gain=20)
    store.stage_gain("20m", rxant="ANT1", ant1_gain=15, ant2_gain=25)
    n = store.discard_all_staged()
    assert n == 2


def test_multi_band_stage_independent(store_factory):
    store = store_factory()
    store.stage_gain("40m", rxant="ANT1", ant1_gain=10, ant2_gain=20)
    store.stage_gain("20m", rxant="ANT1", ant1_gain=15, ant2_gain=25)
    store.discard_staged("40m")
    assert store.has_staged("40m") is False
    assert store.has_staged("20m") is True


def test_persistence_across_instances(tmp_path, monkeypatch):
    from core import preset_store as ps_mod
    monkeypatch.setattr(ps_mod, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(ps_mod, "CALIB_DIR", tmp_path / "kalibrierung")
    monkeypatch.setattr(ps_mod, "SETTINGS_PATH", tmp_path / "settings.json")

    store1 = ps_mod.PresetStore()
    store1.save_gain("40m", rxant="ANT1", ant1_gain=10, ant2_gain=20)
    store2 = ps_mod.PresetStore()
    assert store2.is_valid_gain("40m") is True


# ── P34-Stufe2 / P80: alte API ist weg ────────────────────────────────────


def test_no_save_ratio_method(store_factory):
    store = store_factory()
    assert not hasattr(store, 'save_ratio')


def test_no_is_valid_ratio_method(store_factory):
    store = store_factory()
    assert not hasattr(store, 'is_valid_ratio')


def test_no_commit_with_ratio_method(store_factory):
    store = store_factory()
    assert not hasattr(store, 'commit_with_ratio')


def test_no_get_ratio_age_minutes(store_factory):
    store = store_factory()
    assert not hasattr(store, 'get_ratio_age_minutes')


def test_no_ft_mode_in_save_gain_signature():
    """P80: save_gain hat KEIN ft_mode-Parameter mehr."""
    import inspect
    from core.preset_store import PresetStore
    sig = inspect.signature(PresetStore.save_gain)
    assert "ft_mode" not in sig.parameters
    assert "band" in sig.parameters


def test_no_ft_mode_in_is_valid_gain_signature():
    import inspect
    from core.preset_store import PresetStore
    sig = inspect.signature(PresetStore.is_valid_gain)
    assert "ft_mode" not in sig.parameters
    assert "band" in sig.parameters
