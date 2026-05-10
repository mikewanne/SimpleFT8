#!/usr/bin/env python3
"""Tests fuer core.preset_store — v0.93 zwei Timestamps + Migration.

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


# ── Save-Tests: getrennte Timestamps ────────────────────────────────────────


def test_save_gain_sets_gain_timestamp_only(store_factory):
    """save_gain() setzt gain_timestamp, NICHT ratio_timestamp."""
    store = store_factory()
    store.save_gain("40m", "FT8", rxant="ANT1",
                    ant1_gain=10, ant2_gain=20,
                    ant1_avg=-8.0, ant2_avg=-10.0)
    entry = store.get("40m", "FT8")
    assert entry is not None
    assert "gain_timestamp" in entry
    assert "ratio_timestamp" not in entry


def test_save_ratio_sets_ratio_timestamp_only(store_factory):
    """save_ratio() setzt ratio_timestamp, NICHT gain_timestamp."""
    store = store_factory()
    store.save_ratio("40m", "FT8", ratio="70:30", dominant="A1")
    entry = store.get("40m", "FT8")
    assert entry is not None
    assert "ratio_timestamp" in entry
    assert "gain_timestamp" not in entry
    assert entry["ratio"] == "70:30"
    assert entry["dominant"] == "A1"


def test_save_gain_then_ratio_keeps_both_timestamps(store_factory):
    """Nacheinander save_gain + save_ratio: beide Timestamps gesetzt."""
    store = store_factory()
    store.save_gain("40m", "FT8", rxant="ANT1",
                    ant1_gain=10, ant2_gain=20)
    store.save_ratio("40m", "FT8", ratio="70:30", dominant="A1")
    entry = store.get("40m", "FT8")
    assert "gain_timestamp" in entry
    assert "ratio_timestamp" in entry
    assert entry["ant1_gain"] == 10
    assert entry["ratio"] == "70:30"


def test_save_ratio_does_not_refresh_gain_timestamp(store_factory):
    """Re-Save von ratio darf gain_timestamp NICHT verändern."""
    store = store_factory()
    store.save_gain("40m", "FT8", rxant="ANT1",
                    ant1_gain=10, ant2_gain=20)
    gain_ts_before = store.get("40m", "FT8")["gain_timestamp"]
    time.sleep(0.01)
    store.save_ratio("40m", "FT8", ratio="50:50", dominant=None)
    gain_ts_after = store.get("40m", "FT8")["gain_timestamp"]
    assert gain_ts_before == gain_ts_after


# ── is_valid_gain Tests ─────────────────────────────────────────────────────


def test_is_valid_gain_within_6h_window(store_factory):
    """Vollstaendiger Eintrag (gain + ratio) → is_valid_gain True
    innerhalb 6h. P22: Half-State (gain ohne ratio) wird separat
    abgelehnt — siehe `test_is_valid_gain_rejects_half_state`."""
    store = store_factory()
    store.save_gain("40m", "FT8", rxant="ANT1",
                    ant1_gain=10, ant2_gain=20)
    store.save_ratio("40m", "FT8", ratio="70:30", dominant="A1")
    assert store.is_valid_gain("40m", "FT8") is True


def test_is_valid_gain_after_6h_returns_false(store_factory, monkeypatch):
    store = store_factory()
    store.save_gain("40m", "FT8", rxant="ANT1",
                    ant1_gain=10, ant2_gain=20)
    store.save_ratio("40m", "FT8", ratio="70:30", dominant="A1")
    # Timestamp manuell auf > 6h zurückdatieren
    entry = store.get("40m", "FT8")
    entry["gain_timestamp"] = time.time() - 6 * 3600 - 60  # 6h + 1 Min alt
    assert store.is_valid_gain("40m", "FT8") is False


def test_is_valid_gain_returns_false_when_only_ratio_saved(store_factory):
    """Nur Ratio gespeichert → kein gain_timestamp → is_valid_gain=False."""
    store = store_factory()
    store.save_ratio("40m", "FT8", ratio="70:30", dominant="A1")
    assert store.is_valid_gain("40m", "FT8") is False


def test_is_valid_gain_returns_false_when_no_entry(store_factory):
    store = store_factory()
    assert store.is_valid_gain("40m", "FT8") is False


# ── is_valid_ratio Tests ────────────────────────────────────────────────────


def test_is_valid_ratio_within_1h_window(store_factory):
    store = store_factory()
    store.save_ratio("40m", "FT8", ratio="70:30", dominant="A1")
    assert store.is_valid_ratio("40m", "FT8") is True


def test_is_valid_ratio_after_1h_returns_false(store_factory):
    store = store_factory()
    store.save_ratio("40m", "FT8", ratio="70:30", dominant="A1")
    entry = store.get("40m", "FT8")
    entry["ratio_timestamp"] = time.time() - 3600 - 60  # 1h + 1 Min alt
    assert store.is_valid_ratio("40m", "FT8") is False


def test_is_valid_ratio_returns_false_when_only_gain_saved(store_factory):
    """Nur Gain gespeichert → kein ratio_timestamp → is_valid_ratio=False."""
    store = store_factory()
    store.save_gain("40m", "FT8", rxant="ANT1",
                    ant1_gain=10, ant2_gain=20)
    assert store.is_valid_ratio("40m", "FT8") is False


def test_is_valid_ratio_returns_false_when_no_entry(store_factory):
    store = store_factory()
    assert store.is_valid_ratio("40m", "FT8") is False


# ── Migration Tests ─────────────────────────────────────────────────────────


def test_migration_old_timestamp_to_both_fields(tmp_path, monkeypatch):
    """v0.92 → v0.93: alter 'timestamp' → gain_timestamp + ratio_timestamp."""
    from core import preset_store as ps_mod
    monkeypatch.setattr(ps_mod, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(ps_mod, "CALIB_DIR", tmp_path / "kalibrierung")

    # Alten v0.92-Cache vorher anlegen
    calib_dir = tmp_path / "kalibrierung"
    calib_dir.mkdir(parents=True, exist_ok=True)
    old_ts = time.time() - 1800  # 30 Min alt
    old_data = {
        "40m_FT8": {
            "rxant":     "ANT1",
            "ant1_gain": 10, "ant2_gain": 20,
            "ant1_avg":  -8.5, "ant2_avg": -10.2,
            "ratio":     "70:30",
            "dominant":  "A1",
            "timestamp": old_ts,
            "measured":  "2026-05-04 13:45",
        }
    }
    (calib_dir / "presets_standard.json").write_text(json.dumps(old_data))

    # Beim Load muss Migration laufen
    store = ps_mod.PresetStore("presets_standard.json")
    entry = store.get("40m", "FT8")
    assert entry["gain_timestamp"] == old_ts
    assert entry["ratio_timestamp"] == old_ts
    # Alter timestamp-Key bleibt drin (Backwards-Compat-Read)
    assert entry["timestamp"] == old_ts


def test_migration_idempotent_when_already_new_format(tmp_path, monkeypatch):
    """Wenn gain_timestamp schon existiert: Migration tut nichts."""
    from core import preset_store as ps_mod
    monkeypatch.setattr(ps_mod, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(ps_mod, "CALIB_DIR", tmp_path / "kalibrierung")

    calib_dir = tmp_path / "kalibrierung"
    calib_dir.mkdir(parents=True, exist_ok=True)
    gain_ts  = time.time() - 1800
    ratio_ts = time.time() - 600  # 10 Min alt
    new_data = {
        "40m_FT8": {
            "rxant":           "ANT1",
            "ant1_gain":       10, "ant2_gain": 20,
            "ratio":           "70:30",
            "dominant":        "A1",
            "gain_timestamp":  gain_ts,
            "ratio_timestamp": ratio_ts,
        }
    }
    (calib_dir / "presets_standard.json").write_text(json.dumps(new_data))

    store = ps_mod.PresetStore("presets_standard.json")
    entry = store.get("40m", "FT8")
    assert entry["gain_timestamp"] == gain_ts
    assert entry["ratio_timestamp"] == ratio_ts


def test_migrated_entry_passes_validity_checks(tmp_path, monkeypatch):
    """Nach Migration: is_valid_gain + is_valid_ratio funktionieren korrekt."""
    from core import preset_store as ps_mod
    monkeypatch.setattr(ps_mod, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(ps_mod, "CALIB_DIR", tmp_path / "kalibrierung")

    calib_dir = tmp_path / "kalibrierung"
    calib_dir.mkdir(parents=True, exist_ok=True)
    # Eintrag 30 Min alt → gain valid (6h-Frist), ratio valid (1h-Frist)
    fresh_ts = time.time() - 1800
    (calib_dir / "presets_standard.json").write_text(json.dumps({
        "40m_FT8": {"ratio": "70:30", "dominant": "A1", "timestamp": fresh_ts,
                    "ant1_gain": 10, "ant2_gain": 20}
    }))
    store = ps_mod.PresetStore("presets_standard.json")
    assert store.is_valid_gain("40m", "FT8") is True
    assert store.is_valid_ratio("40m", "FT8") is True

    # 2-Stunden alt: gain valid, ratio NICHT
    old_ts = time.time() - 2 * 3600
    (calib_dir / "presets_dx.json").write_text(json.dumps({
        "20m_FT8": {"ratio": "30:70", "dominant": "A2", "timestamp": old_ts,
                    "ant1_gain": 5, "ant2_gain": 15}
    }))
    store2 = ps_mod.PresetStore("presets_dx.json")
    assert store2.is_valid_gain("20m", "FT8") is True
    assert store2.is_valid_ratio("20m", "FT8") is False


# ── Backwards-Compat (v0.92-API) ────────────────────────────────────────────


def test_legacy_is_valid_aliases_to_gain(store_factory):
    """Alte is_valid()-API delegt auf is_valid_gain() (kein Verhaltensbruch).
    P22: vollstaendiger Eintrag noetig (gain + ratio)."""
    store = store_factory()
    store.save_gain("40m", "FT8", rxant="ANT1",
                    ant1_gain=10, ant2_gain=20)
    store.save_ratio("40m", "FT8", ratio="70:30", dominant="A1")
    assert store.is_valid("40m", "FT8") is True
    assert store.is_valid("40m", "FT8") == store.is_valid_gain("40m", "FT8")


def test_legacy_get_age_minutes_aliases_to_gain(store_factory):
    """Alte get_age_minutes()-API delegt auf get_gain_age_minutes()."""
    store = store_factory()
    store.save_gain("40m", "FT8", rxant="ANT1",
                    ant1_gain=10, ant2_gain=20)
    # P22: get_gain_age_minutes prueft nur gain_timestamp (nicht ratio),
    # bleibt also auch bei Half-State funktionsfaehig.
    legacy_age = store.get_age_minutes("40m", "FT8")
    new_age    = store.get_gain_age_minutes("40m", "FT8")
    assert legacy_age == new_age
    assert legacy_age is not None


# ── P22 Half-State-Reject + Stage/Commit/Discard + Atomic Write ─────────────


def test_is_valid_gain_rejects_half_state(store_factory):
    """P22-A2: Eintrag mit gain_* aber ohne `ratio` → is_valid_gain False.
    Schuetzt vor Endlos-Phase-3-Versuchen nach Hang."""
    store = store_factory()
    store.save_gain("40m", "FT8", rxant="ANT1",
                    ant1_gain=10, ant2_gain=20)
    # Kein save_ratio — Half-State
    assert store.is_valid_gain("40m", "FT8") is False


def test_stage_gain_no_disk_write(store_factory, tmp_path):
    """P22-A1 / T1: stage_gain schreibt nichts in die JSON-Datei."""
    store = store_factory()
    store.stage_gain("40m", "FT8", rxant="ANT1",
                     ant1_gain=10, ant2_gain=20)
    file = tmp_path / "kalibrierung" / "presets_standard.json"
    assert not file.exists()
    assert store.has_staged("40m", "FT8") is True
    assert store.get("40m", "FT8") is None  # nicht im persistenten _data


def test_commit_with_ratio_writes_atomic(store_factory, tmp_path):
    """P22-A1 / T2: commit_with_ratio schreibt staged + ratio gemeinsam,
    Datei enthaelt beide Timestamps und staged ist danach leer."""
    store = store_factory()
    store.stage_gain("40m", "FT8", rxant="ANT1",
                     ant1_gain=10, ant2_gain=20,
                     ant1_avg=-8.5, ant2_avg=-10.2)
    ok = store.commit_with_ratio("40m", "FT8",
                                 ratio="70:30", dominant="A1")
    assert ok is True
    # File geschrieben
    file = tmp_path / "kalibrierung" / "presets_standard.json"
    assert file.exists()
    data = json.loads(file.read_text())
    entry = data["40m_FT8"]
    assert "gain_timestamp" in entry
    assert "ratio_timestamp" in entry
    assert entry["ratio"] == "70:30"
    assert entry["dominant"] == "A1"
    assert entry["ant1_gain"] == 10
    assert entry["ant2_gain"] == 20
    # Staged leer
    assert store.has_staged("40m", "FT8") is False


def test_commit_without_stage_returns_false(store_factory):
    """P22 / T3: commit_with_ratio ohne vorheriges stage_gain → False,
    keine Disk-Aenderung."""
    store = store_factory()
    ok = store.commit_with_ratio("40m", "FT8",
                                 ratio="70:30", dominant="A1")
    assert ok is False
    assert store.get("40m", "FT8") is None


def test_commit_with_ratio_disk_error_keeps_staged(store_factory, monkeypatch):
    """P22-A4 / T4 (R1-K1): Disk-Error beim Commit → staged bleibt
    erhalten, in-memory _data wird zurueckgerollt, returnt False."""
    store = store_factory()
    store.stage_gain("40m", "FT8", rxant="ANT1",
                     ant1_gain=10, ant2_gain=20)

    def boom():
        raise OSError("Disk full")

    monkeypatch.setattr(store, "_save_locked", boom)
    ok = store.commit_with_ratio("40m", "FT8",
                                 ratio="70:30", dominant="A1")
    assert ok is False
    assert store.has_staged("40m", "FT8") is True   # staged bleibt
    assert store.get("40m", "FT8") is None          # in-memory rolled back


def test_discard_staged_clears_memory(store_factory):
    """P22 / T5: discard_staged entfernt den Eintrag, has_staged False."""
    store = store_factory()
    store.stage_gain("40m", "FT8", rxant="ANT1",
                     ant1_gain=10, ant2_gain=20)
    assert store.discard_staged("40m", "FT8") is True
    assert store.has_staged("40m", "FT8") is False
    # Zweiter Aufruf returnt False (nichts mehr da)
    assert store.discard_staged("40m", "FT8") is False


def test_discard_all_staged_clears_all(store_factory):
    """P22 / T5b: discard_all_staged cleart alle Eintraege, returnt Anzahl."""
    store = store_factory()
    store.stage_gain("40m", "FT8", rxant="ANT1",
                     ant1_gain=10, ant2_gain=20)
    store.stage_gain("20m", "FT8", rxant="ANT1",
                     ant1_gain=15, ant2_gain=25)
    assert store.discard_all_staged() == 2
    assert store.has_staged("40m", "FT8") is False
    assert store.has_staged("20m", "FT8") is False


def test_save_gain_returns_false_on_disk_error(store_factory, monkeypatch):
    """P22-A5 / T7 (R1-K3): Disk-Error in save_gain → returnt False
    statt Exception. App crasht nicht."""
    store = store_factory()

    def boom():
        raise OSError("Permission denied")

    monkeypatch.setattr(store, "_save_locked", boom)
    ok = store.save_gain("40m", "FT8", rxant="ANT1",
                         ant1_gain=10, ant2_gain=20)
    assert ok is False
    # in-memory wurde zurueckgerollt
    assert store.get("40m", "FT8") is None


def test_save_ratio_returns_false_on_disk_error(store_factory, monkeypatch):
    """P22 / T7b: gleiche Behandlung fuer save_ratio."""
    store = store_factory()

    def boom():
        raise OSError("Permission denied")

    monkeypatch.setattr(store, "_save_locked", boom)
    ok = store.save_ratio("40m", "FT8", ratio="50:50", dominant="A1")
    assert ok is False


def test_save_locked_atomic_uses_tempfile(store_factory, tmp_path, monkeypatch):
    """P22-A6 / T8: Mid-Write-Crash hinterlaesst kein korruptes Ziel-File.

    Mock os.replace raise → tempfile soll geloescht werden, Ziel-File
    soll nicht angefasst worden sein."""
    store = store_factory()
    # Vorher gueltigen Stand schreiben (= Ziel-File existiert)
    store.save_gain("40m", "FT8", rxant="ANT1",
                    ant1_gain=10, ant2_gain=20)
    store.save_ratio("40m", "FT8", ratio="70:30", dominant="A1")
    target = tmp_path / "kalibrierung" / "presets_standard.json"
    original = target.read_bytes()

    # Naechster Write soll an os.replace scheitern
    from core import preset_store as ps_mod
    real_replace = ps_mod.os.replace
    monkeypatch.setattr(ps_mod.os, "replace",
                        lambda *a, **kw: (_ for _ in ()).throw(OSError("simulated")))
    ok = store.save_gain("40m", "FT8", rxant="ANT2",
                         ant1_gain=99, ant2_gain=99)
    assert ok is False
    # Ziel-File unveraendert
    assert target.read_bytes() == original
    # Keine .tmp_-Datei zurueckgeblieben
    leftover = list((tmp_path / "kalibrierung").glob(".tmp_*"))
    assert leftover == []


def test_multi_band_stage_independent(store_factory):
    """P22 / T18: 40m_FT8 und 20m_FT8 staged parallel, getrennt
    commit/discard."""
    store = store_factory()
    store.stage_gain("40m", "FT8", rxant="ANT1",
                     ant1_gain=10, ant2_gain=20)
    store.stage_gain("20m", "FT8", rxant="ANT1",
                     ant1_gain=15, ant2_gain=25)
    assert store.has_staged("40m", "FT8") is True
    assert store.has_staged("20m", "FT8") is True
    # Commit nur 40m
    assert store.commit_with_ratio("40m", "FT8",
                                   ratio="70:30", dominant="A1") is True
    assert store.has_staged("40m", "FT8") is False
    assert store.has_staged("20m", "FT8") is True
    # Discard 20m
    assert store.discard_staged("20m", "FT8") is True
    assert store.has_staged("20m", "FT8") is False


# ── Persistenz ───────────────────────────────────────────────────────────────


def test_persistence_across_instances(store_factory):
    """save → neue Instanz lädt → beide Timestamps sichtbar."""
    store = store_factory()
    store.save_gain("40m", "FT8", rxant="ANT1",
                    ant1_gain=10, ant2_gain=20)
    store.save_ratio("40m", "FT8", ratio="70:30", dominant="A1")

    store2 = store_factory()
    entry = store2.get("40m", "FT8")
    assert entry is not None
    assert "gain_timestamp" in entry
    assert "ratio_timestamp" in entry
    assert store2.is_valid_gain("40m", "FT8") is True
    assert store2.is_valid_ratio("40m", "FT8") is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
