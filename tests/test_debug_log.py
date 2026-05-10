"""Tests fuer P21.DEBUG-LOG — strategische Diagnose-Eintraege.

Mike-Spec 10.05.2026: 1 Datei pro Tag, älter als gestern wird beim
App-Start geloescht. Toggle in Settings, no-op wenn deaktiviert.
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta
from pathlib import Path

import pytest


@pytest.fixture
def isolated_log_dir(tmp_path, monkeypatch):
    """LOG_DIR auf tmp_path umbiegen + Modul-Globals sauber."""
    from core import debug_log as dbg
    monkeypatch.setattr(dbg, "LOG_DIR", tmp_path)
    # Globals zuruecksetzen damit Tests sich nicht beeinflussen
    monkeypatch.setattr(dbg, "_enabled", False, raising=False)
    return tmp_path


def test_disabled_no_file_created(isolated_log_dir):
    """Wenn deaktiviert: kein Schreiben, keine Datei."""
    from core.debug_log import debug_log
    debug_log("ANT", "test message")
    files = list(isolated_log_dir.glob("debug_*.log"))
    assert files == []


def test_enabled_writes_to_today_file(isolated_log_dir):
    """Wenn aktiviert: Eintrag landet in debug_YYYY-MM-DD.log."""
    from core.debug_log import debug_log, set_enabled
    set_enabled(True)
    debug_log("ANT", "cmd=ANT2 gain=10dB")
    set_enabled(False)
    today = datetime.utcnow().strftime("%Y-%m-%d")
    target = isolated_log_dir / f"debug_{today}.log"
    assert target.exists()
    content = target.read_text(encoding="utf-8")
    assert "[ANT] cmd=ANT2 gain=10dB" in content


def test_set_enabled_writes_activation_marker(isolated_log_dir):
    """set_enabled(True) selbst schreibt einen Marker."""
    from core.debug_log import set_enabled
    set_enabled(True)
    set_enabled(False)
    today = datetime.utcnow().strftime("%Y-%m-%d")
    target = isolated_log_dir / f"debug_{today}.log"
    assert target.exists()
    content = target.read_text(encoding="utf-8")
    assert "[DEBUG] Debug-Log aktiviert" in content


def test_cleanup_removes_old_files_keeps_recent(isolated_log_dir):
    """cleanup_old_files loescht alte, behaelt heutige + gestern."""
    from core.debug_log import cleanup_old_files
    today = datetime.utcnow().strftime("%Y-%m-%d")
    yesterday = (datetime.utcnow() - timedelta(days=1)).strftime("%Y-%m-%d")
    old = (datetime.utcnow() - timedelta(days=5)).strftime("%Y-%m-%d")
    very_old = (datetime.utcnow() - timedelta(days=30)).strftime("%Y-%m-%d")

    for date in (today, yesterday, old, very_old):
        (isolated_log_dir / f"debug_{date}.log").write_text("dummy", encoding="utf-8")

    deleted = cleanup_old_files(keep_days=1)
    assert deleted == 2  # alt + sehr_alt geloescht
    assert (isolated_log_dir / f"debug_{today}.log").exists()
    assert (isolated_log_dir / f"debug_{yesterday}.log").exists()
    assert not (isolated_log_dir / f"debug_{old}.log").exists()
    assert not (isolated_log_dir / f"debug_{very_old}.log").exists()


def test_cleanup_skips_unparseable_files(isolated_log_dir):
    """Dateien mit komischem Namen werden ignoriert (nicht geloescht)."""
    from core.debug_log import cleanup_old_files
    (isolated_log_dir / "debug_garbled.log").write_text("dummy", encoding="utf-8")
    (isolated_log_dir / "debug_2024-XX-YY.log").write_text("dummy", encoding="utf-8")
    deleted = cleanup_old_files(keep_days=1)
    assert deleted == 0
    assert (isolated_log_dir / "debug_garbled.log").exists()


def test_cleanup_empty_dir_returns_zero(isolated_log_dir):
    """Leeres Verzeichnis: 0 geloescht, kein Crash."""
    from core.debug_log import cleanup_old_files
    assert cleanup_old_files() == 0


def test_disk_error_does_not_crash(isolated_log_dir, monkeypatch):
    """Wenn Disk-Fehler: silent skip, kein App-Crash."""
    from core.debug_log import debug_log, set_enabled
    set_enabled(True)
    # Simuliere Disk-Voll: Path.open raise
    real_open = Path.open
    def boom(self, *a, **kw):
        if "debug_" in self.name:
            raise OSError("Disk full")
        return real_open(self, *a, **kw)
    monkeypatch.setattr(Path, "open", boom)
    # darf nicht throwen
    debug_log("ANT", "test")
    set_enabled(False)
