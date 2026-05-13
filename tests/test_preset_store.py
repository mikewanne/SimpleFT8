#!/usr/bin/env python3
"""Tests fuer core.preset_store — P34-Stufe2 (v0.97.19).

Nur Gain-API (Ratio-API wurde mit Stufe2 entfernt — Dynamic uebernimmt
Verhaeltnis-Bestimmung live).

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
    """PresetStore-Factory die ueber tmp_path isoliert."""
    from core import preset_store as ps_mod
    monkeypatch.setattr(ps_mod, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(ps_mod, "CALIB_DIR", tmp_path / "kalibrierung")

    def _factory(filename: str = "presets_standard.json"):
        return ps_mod.PresetStore(filename)
    return _factory


# ── Save-Tests ────────────────────────────────────────────────────────────


def test_save_gain_sets_gain_timestamp_only(store_factory):
    """save_gain() setzt gain_timestamp. Ratio-Felder existieren nicht mehr."""
    store = store_factory()
    store.save_gain("40m", "FT8", rxant="ANT1",
                    ant1_gain=10, ant2_gain=20,
                    ant1_avg=-8.0, ant2_avg=-10.0)
    entry = store.get("40m", "FT8")
    assert entry is not None
    assert "gain_timestamp" in entry
    assert entry["ant1_gain"] == 10
    assert entry["ant2_gain"] == 20


def test_save_gain_returns_false_on_disk_error(store_factory, monkeypatch):
    store = store_factory()
    monkeypatch.setattr(
        store, "_save_locked",
        lambda: (_ for _ in ()).throw(OSError("disk full"))
    )
    ok = store.save_gain("40m", "FT8", rxant="ANT1",
                         ant1_gain=10, ant2_gain=20,
                         ant1_avg=-8.0, ant2_avg=-10.0)
    assert ok is False


# ── Validity ───────────────────────────────────────────────────────────────


def test_is_valid_gain_within_6h_window(store_factory):
    store = store_factory()
    store.save_gain("40m", "FT8", rxant="ANT1",
                    ant1_gain=10, ant2_gain=20)
    assert store.is_valid_gain("40m", "FT8") is True


def test_is_valid_gain_after_6h_returns_false(store_factory, monkeypatch):
    from core import preset_store as ps_mod
    store = store_factory()
    store.save_gain("40m", "FT8", rxant="ANT1",
                    ant1_gain=10, ant2_gain=20)
    # 6h+1s zurueckdatieren
    entry = store._data[store._key("40m", "FT8")]
    entry["gain_timestamp"] -= (ps_mod.GAIN_VALIDITY_SECONDS + 1)
    assert store.is_valid_gain("40m", "FT8") is False


def test_is_valid_gain_returns_false_when_no_entry(store_factory):
    store = store_factory()
    assert store.is_valid_gain("40m", "FT8") is False


def test_legacy_is_valid_aliases_to_gain(store_factory):
    store = store_factory()
    store.save_gain("40m", "FT8", rxant="ANT1",
                    ant1_gain=10, ant2_gain=20)
    assert store.is_valid("40m", "FT8") is True


def test_legacy_get_age_minutes_aliases_to_gain(store_factory):
    store = store_factory()
    store.save_gain("40m", "FT8", rxant="ANT1",
                    ant1_gain=10, ant2_gain=20)
    age_legacy = store.get_age_minutes("40m", "FT8")
    age_new    = store.get_gain_age_minutes("40m", "FT8")
    assert age_legacy == age_new


# ── Migration: alter 'timestamp' → 'gain_timestamp' ──────────────────────


def test_migration_old_timestamp_to_gain_timestamp(tmp_path, monkeypatch):
    """Alter 'timestamp'-Schluessel wird auf 'gain_timestamp' gespiegelt."""
    from core import preset_store as ps_mod
    monkeypatch.setattr(ps_mod, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(ps_mod, "CALIB_DIR", tmp_path / "kalibrierung")
    (tmp_path / "kalibrierung").mkdir(parents=True, exist_ok=True)

    old_ts = time.time() - 100
    data = {
        "40m_FT8": {
            "ant1_gain": 10,
            "ant2_gain": 20,
            "rxant": "ANT1",
            "timestamp": old_ts,
            "measured": "2026-05-13 12:00",
        }
    }
    (tmp_path / "kalibrierung" / "presets_standard.json").write_text(
        json.dumps(data))

    store = ps_mod.PresetStore("presets_standard.json")
    entry = store.get("40m", "FT8")
    assert entry["gain_timestamp"] == old_ts


def test_migration_idempotent_when_already_new_format(tmp_path, monkeypatch):
    from core import preset_store as ps_mod
    monkeypatch.setattr(ps_mod, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(ps_mod, "CALIB_DIR", tmp_path / "kalibrierung")
    (tmp_path / "kalibrierung").mkdir(parents=True, exist_ok=True)

    new_ts = time.time() - 50
    data = {
        "40m_FT8": {
            "ant1_gain": 10,
            "ant2_gain": 20,
            "rxant": "ANT1",
            "gain_timestamp": new_ts,
            "measured": "2026-05-13 12:00",
        }
    }
    (tmp_path / "kalibrierung" / "presets_standard.json").write_text(
        json.dumps(data))

    store = ps_mod.PresetStore("presets_standard.json")
    entry = store.get("40m", "FT8")
    # Migration ist no-op wenn schon migriert
    assert entry["gain_timestamp"] == new_ts


# ── Stage / Commit / Discard (P34-Stufe2: commit_gain statt commit_with_ratio) ──


def test_stage_gain_no_disk_write(store_factory, tmp_path):
    store = store_factory()
    store.stage_gain("40m", "FT8", rxant="ANT1",
                     ant1_gain=10, ant2_gain=20)
    # Disk-File darf NICHT existieren
    expected = tmp_path / "kalibrierung" / "presets_standard.json"
    assert not expected.exists()
    # Staged-Eintrag aber drin
    assert store.has_staged("40m", "FT8") is True


def test_commit_gain_writes_atomic(store_factory, tmp_path):
    store = store_factory()
    store.stage_gain("40m", "FT8", rxant="ANT1",
                     ant1_gain=10, ant2_gain=20)
    ok = store.commit_gain("40m", "FT8")
    assert ok is True
    # Staged ist weg
    assert store.has_staged("40m", "FT8") is False
    # Disk-File existiert + enthaelt Gain
    expected = tmp_path / "kalibrierung" / "presets_standard.json"
    assert expected.exists()
    data = json.loads(expected.read_text())
    assert data["40m_FT8"]["ant1_gain"] == 10


def test_commit_without_stage_returns_false(store_factory):
    store = store_factory()
    ok = store.commit_gain("40m", "FT8")
    assert ok is False


def test_commit_gain_disk_error_keeps_staged(store_factory, monkeypatch):
    store = store_factory()
    store.stage_gain("40m", "FT8", rxant="ANT1",
                     ant1_gain=10, ant2_gain=20)
    monkeypatch.setattr(
        store, "_save_locked",
        lambda: (_ for _ in ()).throw(OSError("disk full"))
    )
    ok = store.commit_gain("40m", "FT8")
    assert ok is False
    # Staged bleibt fuer Retry
    assert store.has_staged("40m", "FT8") is True


def test_discard_staged_clears_memory(store_factory):
    store = store_factory()
    store.stage_gain("40m", "FT8", rxant="ANT1",
                     ant1_gain=10, ant2_gain=20)
    removed = store.discard_staged("40m", "FT8")
    assert removed is True
    assert store.has_staged("40m", "FT8") is False


def test_discard_all_staged_clears_all(store_factory):
    store = store_factory()
    store.stage_gain("40m", "FT8", rxant="ANT1",
                     ant1_gain=10, ant2_gain=20)
    store.stage_gain("20m", "FT8", rxant="ANT1",
                     ant1_gain=15, ant2_gain=25)
    n = store.discard_all_staged()
    assert n == 2


def test_multi_band_stage_independent(store_factory):
    store = store_factory()
    store.stage_gain("40m", "FT8", rxant="ANT1",
                     ant1_gain=10, ant2_gain=20)
    store.stage_gain("20m", "FT8", rxant="ANT1",
                     ant1_gain=15, ant2_gain=25)
    store.discard_staged("40m", "FT8")
    # 20m staged bleibt
    assert store.has_staged("40m", "FT8") is False
    assert store.has_staged("20m", "FT8") is True


def test_persistence_across_instances(tmp_path, monkeypatch):
    from core import preset_store as ps_mod
    monkeypatch.setattr(ps_mod, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(ps_mod, "CALIB_DIR", tmp_path / "kalibrierung")

    store1 = ps_mod.PresetStore("presets_standard.json")
    store1.save_gain("40m", "FT8", rxant="ANT1",
                     ant1_gain=10, ant2_gain=20)
    store2 = ps_mod.PresetStore("presets_standard.json")
    assert store2.is_valid_gain("40m", "FT8") is True


# ── P34-Stufe2: alte API ist weg ──────────────────────────────────────────


def test_no_save_ratio_method(store_factory):
    """P34-Stufe2: save_ratio entfernt — Ratio wird nicht mehr persistiert."""
    store = store_factory()
    assert not hasattr(store, 'save_ratio')


def test_no_is_valid_ratio_method(store_factory):
    """P34-Stufe2: is_valid_ratio entfernt."""
    store = store_factory()
    assert not hasattr(store, 'is_valid_ratio')


def test_no_commit_with_ratio_method(store_factory):
    """P34-Stufe2: commit_with_ratio entfernt (→ commit_gain)."""
    store = store_factory()
    assert not hasattr(store, 'commit_with_ratio')


def test_no_get_ratio_age_minutes(store_factory):
    """P34-Stufe2: get_ratio_age_minutes entfernt."""
    store = store_factory()
    assert not hasattr(store, 'get_ratio_age_minutes')
