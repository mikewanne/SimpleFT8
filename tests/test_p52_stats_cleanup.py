"""P52 (v0.97.41) — Stats-Toggle raus + 90-Tage-Rolling-Window-Cleanup.

T1: Hour-Pattern, alte Datei wird gelöscht.
T2: Day-Pattern (antenna_qso), alte Datei gelöscht.
T3: Junge Datei (<90 Tage) bleibt.
T4: Nicht-passende Dateinamen bleiben.
T5: Rekursiver Walk durch stations/-Unterverzeichnis.
T6: Nicht-existentes Verzeichnis returnt 0.
T7: Settings-Migration — stats_enabled wird gepoppt.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from core.stats_cleanup import cleanup_stats_older_than_days


def _utc_now() -> datetime:
    return datetime.utcnow()


def _date_str(days_ago: int) -> str:
    return (_utc_now() - timedelta(days=days_ago)).strftime("%Y-%m-%d")


# ── T1 — Hour-Pattern, alte Datei gelöscht ──────────────────────────────


def test_t1_hour_pattern_old_file_deleted(tmp_path):
    """Stunden-Stats älter als 90 Tage wird gelöscht."""
    sub = tmp_path / "Normal" / "40m" / "FT8"
    sub.mkdir(parents=True)
    old = sub / f"{_date_str(100)}_12.md"
    new = sub / f"{_date_str(1)}_12.md"
    old.write_text("old")
    new.write_text("new")

    deleted = cleanup_stats_older_than_days(tmp_path, days=90)

    assert deleted == 1
    assert not old.exists()
    assert new.exists()


# ── T2 — Day-Pattern (antenna_qso) ──────────────────────────────────────


def test_t2_day_pattern_old_file_deleted(tmp_path):
    """Tages-Datei (antenna_qso) älter als 90 Tage wird gelöscht."""
    qso_dir = tmp_path / "antenna_qso"
    qso_dir.mkdir(parents=True)
    old = qso_dir / f"{_date_str(120)}.md"
    new = qso_dir / f"{_date_str(5)}.md"
    old.write_text("old qso")
    new.write_text("new qso")

    deleted = cleanup_stats_older_than_days(tmp_path, days=90)

    assert deleted == 1
    assert not old.exists()
    assert new.exists()


# ── T3 — Junge Datei bleibt ─────────────────────────────────────────────


def test_t3_young_file_kept(tmp_path):
    """Datei mit Datum < 90 Tage bleibt unangetastet."""
    sub = tmp_path / "Diversity_Dx" / "20m" / "FT8"
    sub.mkdir(parents=True)
    young = sub / f"{_date_str(30)}_18.md"
    young.write_text("young")

    deleted = cleanup_stats_older_than_days(tmp_path, days=90)

    assert deleted == 0
    assert young.exists()


# ── T4 — Nicht-passende Dateinamen ──────────────────────────────────────


def test_t4_non_matching_filenames_kept(tmp_path):
    """Dateien die nicht dem Pattern entsprechen werden ignoriert."""
    sub = tmp_path / "Normal" / "40m" / "FT8"
    sub.mkdir(parents=True)
    keepers = [
        sub / "notes.md",
        sub / "summary.md",
        sub / "README.md",
        sub / "2024-01-XX_12.md",   # bad day
        sub / "2024-13-01_12.md",   # bad month (matches regex, fails strptime → skipped silently)
    ]
    for f in keepers:
        f.write_text("keeper")

    deleted = cleanup_stats_older_than_days(tmp_path, days=90)

    assert deleted == 0
    for f in keepers:
        assert f.exists(), f"{f.name} sollte erhalten bleiben"


# ── T5 — Rekursiv durch stations/-Unterverzeichnis ──────────────────────


def test_t5_recursive_walk_stations_subdir(tmp_path):
    """Rescue-Files unter stations/ werden auch erfasst."""
    sub = tmp_path / "Diversity_Dx" / "40m" / "FT8" / "stations"
    sub.mkdir(parents=True)
    old = sub / f"{_date_str(150)}_06.md"
    new = sub / f"{_date_str(10)}_06.md"
    old.write_text("old rescue")
    new.write_text("new rescue")

    deleted = cleanup_stats_older_than_days(tmp_path, days=90)

    assert deleted == 1
    assert not old.exists()
    assert new.exists()


# ── T6 — Nicht-existentes Verzeichnis ───────────────────────────────────


def test_t6_nonexistent_dir_returns_zero(tmp_path):
    """Cleanup auf nicht-existentem Verzeichnis returnt 0 ohne Exception."""
    nonexistent = tmp_path / "does_not_exist"
    assert not nonexistent.exists()

    result = cleanup_stats_older_than_days(nonexistent, days=90)

    assert result == 0


# ── T7 — Settings-Migration: stats_enabled wird gepoppt ─────────────────


def test_t7_settings_migration_pops_stats_enabled(tmp_path, monkeypatch):
    """Alter Config-Key `stats_enabled` wird beim Load idempotent gepoppt
    (analog P47 audio_freq_hz/max_decode_freq)."""
    # Settings-File mit altem Key vortäuschen
    fake_config = tmp_path / "config.json"
    fake_config.write_text(json.dumps({
        "band": "40m",
        "mode": "FT8",
        "stats_enabled": False,
    }))

    # CONFIG_FILE in config.settings auf unsere fake-Datei umlenken
    from config import settings as settings_module
    monkeypatch.setattr(settings_module, "CONFIG_FILE", fake_config)

    s = settings_module.Settings()  # ruft load() im Konstruktor
    # stats_enabled muss gepoppt sein
    assert "stats_enabled" not in s._data
    # andere Keys bleiben
    assert s.get("band") == "40m"


# ── T8 — Cleanup-Funktion ist idempotent ────────────────────────────────


def test_t8_cleanup_idempotent(tmp_path):
    """Zweiter Cleanup-Lauf returnt 0 (alle alten Files schon weg)."""
    sub = tmp_path / "Normal" / "40m" / "FT8"
    sub.mkdir(parents=True)
    old = sub / f"{_date_str(200)}_00.md"
    old.write_text("old")

    first = cleanup_stats_older_than_days(tmp_path, days=90)
    second = cleanup_stats_older_than_days(tmp_path, days=90)

    assert first == 1
    assert second == 0
    assert not old.exists()
