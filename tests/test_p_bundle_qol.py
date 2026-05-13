"""Bundle A — P43 setproctitle + P20 Log-Rotation + P18 DT-Print-Dedup (v0.97.12).

T1 — setproctitle import-try in main.py (Source-Check Pattern analog P47).
T2 — dated_log_filename liefert datierten Pfad.
T3 — cleanup_old_main_logs respektiert keep_days und laesst Symlink/Archive in Ruhe.
T4 — setup_main_log archiviert vorhandene regulaere simpleft8.log dauerhaft.
T5 — setup_main_log ersetzt vorhandenen Symlink atomar auf heutige Datei.
T6 — setup_main_log fallback bei OSError im Symlink-Setup (kein Crash).
T7 — _log_load_dedup skipt identische (key, saved_val)-Aufrufe.
T8 — _log_load_dedup loggt bei Wertaenderung erneut.
"""
from __future__ import annotations

import os
import re
from datetime import datetime, timedelta
from pathlib import Path

import pytest


# ── P43 Source-Check ─────────────────────────────────────────────────────


def test_setproctitle_safe_when_missing():
    """main.py umschliesst setproctitle-Import mit try/except ImportError."""
    src = Path(__file__).parent.parent / "main.py"
    text = src.read_text()
    # Muster pruefen — try-Block + import + except ImportError
    assert "import setproctitle" in text, "setproctitle-Import fehlt"
    assert "except ImportError" in text, \
        "Import-Schutz (except ImportError) fehlt — App crasht ohne Modul"
    # Reihenfolge: import kommt VOR except
    import_idx = text.index("import setproctitle")
    except_idx = text.index("except ImportError")
    assert import_idx < except_idx, \
        "except ImportError muss NACH import setproctitle stehen"


# ── P20 Log-Rotation ─────────────────────────────────────────────────────


def test_dated_log_filename_format(tmp_path):
    from core.log_setup import dated_log_filename
    p = dated_log_filename(tmp_path, datetime(2026, 5, 13))
    assert p.name == "simpleft8-2026-05-13.log"
    assert p.parent == tmp_path


def test_cleanup_old_main_logs_keeps_recent(tmp_path):
    """Cleanup loescht > keep_days alte datierte Logs, behaelt Symlink + Archive."""
    from core.log_setup import cleanup_old_main_logs

    today = datetime.utcnow()
    recent = tmp_path / f"simpleft8-{today.strftime('%Y-%m-%d')}.log"
    five_days = tmp_path / f"simpleft8-{(today - timedelta(days=5)).strftime('%Y-%m-%d')}.log"
    thirty_days = tmp_path / f"simpleft8-{(today - timedelta(days=30)).strftime('%Y-%m-%d')}.log"
    for f in (recent, five_days, thirty_days):
        f.write_text("log")

    # Symlink simpleft8.log (sollte unberuehrt bleiben)
    symlink = tmp_path / "simpleft8.log"
    os.symlink(recent.name, symlink)

    # Archive-Unterordner (sollte unberuehrt bleiben)
    archive = tmp_path / "archive"
    archive.mkdir()
    archive_file = archive / "simpleft8-pre-rotation-2026-04-01.log"
    archive_file.write_text("alt")

    deleted = cleanup_old_main_logs(tmp_path, keep_days=7)

    assert deleted == 1, f"Erwartet 1 geloescht, war {deleted}"
    assert recent.exists()
    assert five_days.exists()
    assert not thirty_days.exists()
    assert symlink.is_symlink()  # Symlink unberuehrt
    assert archive_file.exists()  # Archive unberuehrt


def test_setup_main_log_archives_existing_file(tmp_path):
    """Bestehende regulaere simpleft8.log wird einmalig nach archive/ verschoben."""
    from core.log_setup import setup_main_log

    legacy = tmp_path / "simpleft8.log"
    legacy.write_text("Mike's Historie ueber Wochen")

    path, handle = setup_main_log(tmp_path)
    handle.close()

    # archive/ angelegt
    archive_dir = tmp_path / "archive"
    assert archive_dir.is_dir()

    # Pre-Rotation-Datei mit Mike's Historie da
    today = datetime.utcnow().strftime("%Y-%m-%d")
    archived = archive_dir / f"simpleft8-pre-rotation-{today}.log"
    assert archived.exists()
    assert archived.read_text() == "Mike's Historie ueber Wochen"

    # simpleft8.log ist jetzt Symlink auf heutige datierte Datei
    symlink = tmp_path / "simpleft8.log"
    assert symlink.is_symlink()
    target_name = os.readlink(symlink)
    assert re.match(r"^simpleft8-\d{4}-\d{2}-\d{2}\.log$", target_name)


def test_setup_main_log_replaces_existing_symlink(tmp_path):
    """Bestehender Symlink wird atomar auf heutige Datei umgebogen."""
    from core.log_setup import setup_main_log

    old_dated = tmp_path / "simpleft8-2026-05-10.log"
    old_dated.write_text("alter Log-Content")
    os.symlink(old_dated.name, tmp_path / "simpleft8.log")

    path, handle = setup_main_log(tmp_path)
    handle.close()

    # Alte datierte Datei bleibt
    assert old_dated.exists()
    assert old_dated.read_text() == "alter Log-Content"

    # Symlink zeigt auf heutige Datei (nicht mehr auf 2026-05-10)
    symlink = tmp_path / "simpleft8.log"
    assert symlink.is_symlink()
    target_name = os.readlink(symlink)
    today = datetime.utcnow().strftime("%Y-%m-%d")
    assert target_name == f"simpleft8-{today}.log"


def test_setup_main_log_fallback_on_symlink_error(tmp_path, monkeypatch):
    """OSError im os.symlink → Fallback ohne Crash, Path zeigt auf datierte Datei."""
    import core.log_setup as ls

    def fake_symlink(*a, **kw):
        raise OSError("EPERM (simulated)")

    monkeypatch.setattr(ls.os, "symlink", fake_symlink)

    # Soll nicht crashen
    path, handle = ls.setup_main_log(tmp_path)
    try:
        # Datei wurde trotzdem geoeffnet (datierte Datei)
        assert path.exists()
        assert path.name.startswith("simpleft8-")
        # Symlink wurde NICHT erstellt
        assert not (tmp_path / "simpleft8.log").exists()
    finally:
        if hasattr(handle, "close"):
            try:
                handle.close()
            except Exception:
                pass


# ── P18 DT-Print-Dedup ───────────────────────────────────────────────────


@pytest.fixture
def reset_ntp(monkeypatch):
    """Frischer DT-Modul-State fuer deterministische Tests."""
    import core.ntp_time as nt
    monkeypatch.setattr(nt, "_last_logged_load", None)
    monkeypatch.setattr(nt, "_saved", {})
    monkeypatch.setattr(nt, "_correction", 0.0)
    yield nt


def test_dt_dedup_skips_repeat(reset_ntp, capsys):
    """Zweimaliger set_mode mit gleichem Wert → nur 1× print."""
    nt = reset_ntp
    nt._saved["FT8_20m"] = 0.65

    nt.set_mode("FT8", "20m")
    nt.set_mode("FT8", "20m")

    captured = capsys.readouterr().out
    matches = re.findall(
        r"\[DT-Korr\] FT8_20m: Gespeicherter Wert \+0\.650s geladen",
        captured,
    )
    assert len(matches) == 1, \
        f"Erwartet 1 print, war {len(matches)}.\nOutput:\n{captured}"


def test_dt_dedup_logs_on_change(reset_ntp, capsys):
    """Wechsel auf andere Modus+Band-Kombi → erneut print (Cache invalidiert)."""
    nt = reset_ntp
    nt._saved["FT8_20m"] = 0.65
    nt._saved["FT4_40m"] = 0.42

    nt.set_mode("FT8", "20m")
    nt.set_mode("FT4", "40m")

    captured = capsys.readouterr().out
    assert "[DT-Korr] FT8_20m: Gespeicherter Wert +0.650s" in captured
    assert "[DT-Korr] FT4_40m: Gespeicherter Wert +0.420s" in captured
