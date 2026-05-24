"""P116 (24.05.2026, v0.98.01) — FIFO-Sliding-Window Stats-Cleanup.

Mike-Anforderung 24.05.: 90-Tage-Datum-Cleanup ersetzen durch FIFO pro
`(Modus, Band, Proto, Stunde)`-Bucket. Saisonale Anpassung +
Pause-Robustheit.

DeepSeek-Brainstorm-Konsens: N=30 pro Bucket (saisonal aktuell, n>=25
für CI-Signifikanz, ausreichende Daten-Tiefe je Stunde-Bucket).

Test-Coverage:
- T1: Bucket mit 25 Files → 0 gelöscht (< 30)
- T2: Bucket mit 30 Files → 0 gelöscht (= Grenze)
- T3: Bucket mit 50 Files → 20 gelöscht (jüngste 30 behalten)
- T3a: Behaltene 30 Files sind die jüngsten (R1-Empfehlung — explizite
  Sortier-Verifikation)
- T4: Mehrere Buckets unabhängig pruned
- T5: Stations/-Files separater Bucket, eigenes Pruning
- T6: Stations/-Files parallel zu Stunden-Files (identische Datums →
  identisches Pruning)
- T7: Antenna_QSO mit Datum-Cleanup (unverändert, 90 Tage)
- T8: Antenna_QSO wird NICHT vom Bucket-Pruning angefasst
- T9: Idempotent: 2. Aufruf macht nichts
- T10: Cache-Invalidierung wenn deleted > 0
- T11: Cache-NICHT-Invalidierung wenn deleted == 0
- T12: Non-existent dir returnt 0
- T13: Non-matching filenames bleiben
"""
from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import pytest

from core.stats_cleanup import (
    prune_stats_to_max_per_bucket,
    cleanup_antenna_qso_older_than_days,
    invalidate_bandpilot_cache_if_needed,
)


def _date_str(days_ago: int) -> str:
    return (datetime.utcnow() - timedelta(days=days_ago)).strftime("%Y-%m-%d")


# ── T1-T3a: FIFO-Pruning pro Bucket ─────────────────────────────────


def test_t1_bucket_under_limit_no_delete(tmp_path):
    """Bucket mit 25 Files → 0 gelöscht (< 30)."""
    sub = tmp_path / "Normal" / "20m" / "FT8"
    sub.mkdir(parents=True)
    for i in range(25):
        (sub / f"{_date_str(i)}_14.md").write_text(f"day {i}")
    deleted = prune_stats_to_max_per_bucket(tmp_path, max_per_bucket=30)
    assert deleted == 0
    assert len(list(sub.iterdir())) == 25


def test_t2_bucket_at_limit_no_delete(tmp_path):
    """Bucket mit exakt 30 Files → 0 gelöscht (Grenze)."""
    sub = tmp_path / "Normal" / "20m" / "FT8"
    sub.mkdir(parents=True)
    for i in range(30):
        (sub / f"{_date_str(i)}_14.md").write_text(f"day {i}")
    deleted = prune_stats_to_max_per_bucket(tmp_path, max_per_bucket=30)
    assert deleted == 0
    assert len(list(sub.iterdir())) == 30


def test_t3_bucket_over_limit_prunes_oldest(tmp_path):
    """Bucket mit 50 Files → 20 ältesten gelöscht, jüngste 30 behalten."""
    sub = tmp_path / "Normal" / "20m" / "FT8"
    sub.mkdir(parents=True)
    for i in range(50):
        (sub / f"{_date_str(i)}_14.md").write_text(f"day {i}")
    deleted = prune_stats_to_max_per_bucket(tmp_path, max_per_bucket=30)
    assert deleted == 20
    assert len(list(sub.iterdir())) == 30


def test_t3a_oldest_files_deleted_youngest_preserved(tmp_path):
    """R1-Empfehlung: explizit prüfen dass die JÜNGSTEN 30 behalten werden
    (Sortier-Verifikation, nicht nur Anzahl)."""
    sub = tmp_path / "Normal" / "20m" / "FT8"
    sub.mkdir(parents=True)
    # 50 Files mit days_ago=0 (heute) bis days_ago=49
    for i in range(50):
        (sub / f"{_date_str(i)}_14.md").write_text(f"day {i}")
    prune_stats_to_max_per_bucket(tmp_path, max_per_bucket=30)
    # Behaltene Datums: days_ago=0 bis 29 (jüngste)
    # Gelöschte: days_ago=30 bis 49 (älteste)
    remaining_dates = sorted([f.stem.split("_")[0] for f in sub.iterdir()])
    expected_dates = sorted([_date_str(i) for i in range(30)])
    assert remaining_dates == expected_dates, (
        f"Erwartet jüngste 30 Datums, bekommen: {remaining_dates[:3]}...")


# ── T4-T5: Mehrere Buckets ─────────────────────────────────────────


def test_t4_multiple_buckets_independent(tmp_path):
    """Mehrere Buckets werden unabhängig gepruned."""
    # Bucket 1: 20m Normal Stunde 14 — 35 Files
    sub1 = tmp_path / "Normal" / "20m" / "FT8"
    sub1.mkdir(parents=True)
    for i in range(35):
        (sub1 / f"{_date_str(i)}_14.md").write_text("x")
    # Bucket 2: 40m Diversity_Normal Stunde 18 — 50 Files
    sub2 = tmp_path / "Diversity_Normal" / "40m" / "FT8"
    sub2.mkdir(parents=True)
    for i in range(50):
        (sub2 / f"{_date_str(i)}_18.md").write_text("y")
    # Bucket 3: 20m Normal Stunde 06 — 10 Files (unter Limit)
    for i in range(10):
        (sub1 / f"{_date_str(i)}_06.md").write_text("z")

    deleted = prune_stats_to_max_per_bucket(tmp_path, max_per_bucket=30)
    # Bucket 1: 35-30 = 5, Bucket 2: 50-30 = 20, Bucket 3: 0
    assert deleted == 25
    # Stunde-14 Bucket1: 30 übrig
    assert sum(1 for f in sub1.iterdir() if "_14.md" in f.name) == 30
    # Stunde-06 Bucket1: 10 übrig
    assert sum(1 for f in sub1.iterdir() if "_06.md" in f.name) == 10
    # Bucket 2: 30 übrig
    assert sum(1 for f in sub2.iterdir()) == 30


def test_t5_stations_subdir_is_own_bucket(tmp_path):
    """Stations/-Files sind eigener Bucket (parallel zu Stunden-Files)."""
    main_dir = tmp_path / "Diversity_Normal" / "40m" / "FT8"
    stations_dir = main_dir / "stations"
    main_dir.mkdir(parents=True)
    stations_dir.mkdir()
    # 35 Files im Haupt-Bucket
    for i in range(35):
        (main_dir / f"{_date_str(i)}_18.md").write_text("main")
    # 50 Files im Stations-Bucket — separat
    for i in range(50):
        (stations_dir / f"{_date_str(i)}_18.md").write_text("stations")

    deleted = prune_stats_to_max_per_bucket(tmp_path, max_per_bucket=30)
    # Haupt: 5, Stations: 20 → total 25
    assert deleted == 25
    assert sum(1 for f in main_dir.iterdir() if f.is_file()) == 30
    assert sum(1 for f in stations_dir.iterdir()) == 30


def test_t6_stations_files_parallel_consistent_pruning(tmp_path):
    """Parallel geschriebene Stations + Stunden-Files (identische Datums)
    → identisches Pruning-Ergebnis ohne explizite Kopplung."""
    main_dir = tmp_path / "Diversity_Normal" / "40m" / "FT8"
    stations_dir = main_dir / "stations"
    main_dir.mkdir(parents=True)
    stations_dir.mkdir()
    # 50 Files in BEIDEN Buckets mit gleichen Datums
    for i in range(50):
        (main_dir / f"{_date_str(i)}_18.md").write_text("main")
        (stations_dir / f"{_date_str(i)}_18.md").write_text("stations")
    prune_stats_to_max_per_bucket(tmp_path, max_per_bucket=30)

    # Beide Buckets sollten jüngste 30 Datums haben → IDENTISCH
    main_dates = sorted([f.stem.split("_")[0] for f in main_dir.iterdir()
                         if f.is_file()])
    stat_dates = sorted([f.stem.split("_")[0] for f in stations_dir.iterdir()])
    assert main_dates == stat_dates
    assert len(main_dates) == 30


# ── T7-T8: Antenna_QSO separater Pfad ──────────────────────────────


def test_t7_antenna_qso_old_files_deleted(tmp_path):
    """Antenna_QSO mit Datum-Cleanup (90 Tage, BLEIBT)."""
    qso_dir = tmp_path / "antenna_qso"
    qso_dir.mkdir()
    old = qso_dir / f"{_date_str(120)}.md"
    new = qso_dir / f"{_date_str(30)}.md"
    old.write_text("old")
    new.write_text("new")
    deleted = cleanup_antenna_qso_older_than_days(tmp_path, days=90)
    assert deleted == 1
    assert not old.exists()
    assert new.exists()


def test_t8_antenna_qso_not_touched_by_bucket_prune(tmp_path):
    """prune_stats_to_max_per_bucket lässt antenna_qso komplett unangetastet."""
    qso_dir = tmp_path / "antenna_qso"
    qso_dir.mkdir()
    # 50 alte Files (200 Tage alt)
    for i in range(50):
        (qso_dir / f"{_date_str(200 + i)}.md").write_text("old")
    deleted = prune_stats_to_max_per_bucket(tmp_path, max_per_bucket=30)
    assert deleted == 0, (
        "Bucket-Prune darf antenna_qso NICHT anfassen — "
        "ist Tages-Format, separate Funktion")
    assert len(list(qso_dir.iterdir())) == 50


# ── T9: Idempotenz ────────────────────────────────────────────────


def test_t9_idempotent(tmp_path):
    """2. Aufruf nach Pruning → 0 weitere Löschungen."""
    sub = tmp_path / "Normal" / "20m" / "FT8"
    sub.mkdir(parents=True)
    for i in range(50):
        (sub / f"{_date_str(i)}_14.md").write_text("x")
    first = prune_stats_to_max_per_bucket(tmp_path, max_per_bucket=30)
    second = prune_stats_to_max_per_bucket(tmp_path, max_per_bucket=30)
    assert first == 20
    assert second == 0


# ── T10-T11: Cache-Invalidierung ──────────────────────────────────


def test_t10_cache_invalidated_when_deleted_gt_zero(tmp_path, monkeypatch):
    """Bandpilot-Cache-File wird gelöscht wenn was gepruned wurde."""
    fake_home = tmp_path / "fake_home"
    fake_home.mkdir()
    monkeypatch.setattr(Path, "home", lambda: fake_home)
    cache_dir = fake_home / ".simpleft8"
    cache_dir.mkdir()
    cache_file = cache_dir / "bandpilot_hourly.json"
    cache_file.write_text('{"40m": {"ts": 123, "summary": {}}}')

    invalidate_bandpilot_cache_if_needed(deleted_count=5)
    assert not cache_file.exists()


def test_t11_cache_not_touched_when_deleted_zero(tmp_path, monkeypatch):
    """Cache-File bleibt unangetastet wenn nichts gepruned wurde."""
    fake_home = tmp_path / "fake_home"
    fake_home.mkdir()
    monkeypatch.setattr(Path, "home", lambda: fake_home)
    cache_dir = fake_home / ".simpleft8"
    cache_dir.mkdir()
    cache_file = cache_dir / "bandpilot_hourly.json"
    cache_file.write_text('{"40m": {"ts": 123, "summary": {}}}')

    invalidate_bandpilot_cache_if_needed(deleted_count=0)
    assert cache_file.exists()


# ── T12-T13: Robustheit ──────────────────────────────────────────


def test_t12_nonexistent_dir_returns_zero(tmp_path):
    """Cleanup auf nicht-existentem Verzeichnis returnt 0."""
    result = prune_stats_to_max_per_bucket(tmp_path / "does_not_exist",
                                            max_per_bucket=30)
    assert result == 0


def test_t13_non_matching_filenames_kept(tmp_path):
    """Files mit nicht passenden Namen werden ignoriert (regex-miss)."""
    sub = tmp_path / "Normal" / "20m" / "FT8"
    sub.mkdir(parents=True)
    keepers = [
        sub / "notes.md",
        sub / "summary.md",
        sub / "README.md",
        sub / "2024-01-XX_12.md",   # bad day
    ]
    for f in keepers:
        f.write_text("keep")
    # Plus 50 valide Files
    for i in range(50):
        (sub / f"{_date_str(i)}_14.md").write_text("x")

    deleted = prune_stats_to_max_per_bucket(tmp_path, max_per_bucket=30)
    assert deleted == 20  # nur die validen werden gepruned
    for f in keepers:
        assert f.exists(), f"{f.name} sollte erhalten bleiben"
