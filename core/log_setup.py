"""Tages-Rotation fuer simpleft8.log (P20 v0.97.12).

Eintritts-API: ``setup_main_log()`` liefert ``(path, file_handle)``.
Pattern in ``main.py``:

    from core.log_setup import setup_main_log
    _log_path, _log_file = setup_main_log()

Layout:

    ~/.simpleft8/
    +- simpleft8.log                          (Symlink → heutige Datei)
    +- simpleft8-2026-05-13.log               (heute, append)
    +- simpleft8-2026-05-12.log               (gestern)
    +- ...
    +- archive/
       +- simpleft8-pre-rotation-2026-05-13.log  (Mike's Historie, dauerhaft)

Verhalten:

- Cleanup beim App-Start: alle ``simpleft8-YYYY-MM-DD.log`` aelter als
  ``keep_days`` (default 7) werden geloescht.
- ``archive/`` wird NIE angeruehrt (Mike's Historie ist dauerhaft).
- Bestehende reguläre ``simpleft8.log`` (kein Symlink) wird einmalig
  nach ``archive/simpleft8-pre-rotation-YYYY-MM-DD.log`` verschoben.
- Symlink-Setup atomar via ``os.symlink`` + ``os.replace``; bei
  OSError Fallback auf direkten Open ohne Symlink.
- Gesamt-Try/Except in ``setup_main_log``: bei jedem unerwarteten
  Fehler Fallback auf alten Pfad (``simpleft8.log`` ohne Rotation).
"""
from __future__ import annotations

import os
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path


_DATED_PATTERN = re.compile(r"^simpleft8-(\d{4}-\d{2}-\d{2})\.log$")


def dated_log_filename(log_dir: Path, date: datetime | None = None) -> Path:
    """Pfad zu ``simpleft8-YYYY-MM-DD.log`` fuer das gegebene UTC-Datum.

    ``date=None`` → heute (UTC).
    """
    if date is None:
        date = datetime.utcnow()
    return Path(log_dir) / f"simpleft8-{date.strftime('%Y-%m-%d')}.log"


def cleanup_old_main_logs(log_dir: Path, keep_days: int = 7) -> int:
    """Loescht datierte simpleft8-Logs aelter als ``keep_days`` (UTC).

    Beruehrt NUR ``simpleft8-YYYY-MM-DD.log``-Dateien direkt in
    ``log_dir`` — der ``archive/``-Unterordner und der Symlink
    ``simpleft8.log`` bleiben unangetastet.

    Returns Anzahl geloeschter Dateien. Fail-silent pro Datei.
    """
    log_dir = Path(log_dir)
    if not log_dir.exists():
        return 0
    cutoff = (datetime.utcnow() - timedelta(days=keep_days)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    deleted = 0
    for f in log_dir.iterdir():
        try:
            m = _DATED_PATTERN.match(f.name)
            if not m:
                continue
            file_date = datetime.strptime(m.group(1), "%Y-%m-%d")
            if file_date < cutoff:
                f.unlink()
                deleted += 1
        except (ValueError, OSError):
            continue
    return deleted


def _archive_legacy_logfile(log_dir: Path) -> None:
    """Wenn ``simpleft8.log`` als regulaere Datei (kein Symlink) existiert,
    nach ``archive/simpleft8-pre-rotation-YYYY-MM-DD.log`` verschieben.

    Dauerhaft — wird vom Cleanup NICHT angefasst. KISS, fail-silent.
    """
    legacy = log_dir / "simpleft8.log"
    if not legacy.exists() or legacy.is_symlink():
        return
    archive_dir = log_dir / "archive"
    try:
        archive_dir.mkdir(parents=True, exist_ok=True)
        today = datetime.utcnow().strftime("%Y-%m-%d")
        target = archive_dir / f"simpleft8-pre-rotation-{today}.log"
        # Falls heute schon archiviert wurde: Counter-Suffix
        counter = 1
        while target.exists():
            target = archive_dir / f"simpleft8-pre-rotation-{today}-{counter}.log"
            counter += 1
        legacy.replace(target)
    except OSError as e:
        print(f"[log_setup] Archiv-Verschiebung fehlgeschlagen: {e}",
              file=sys.__stderr__)


def _setup_symlink(log_dir: Path, target: Path) -> bool:
    """Symlink ``simpleft8.log`` -> ``target`` atomar setzen.

    Bestehender Symlink wird ersetzt; bestehende regulaere Datei
    (sollte nach _archive_legacy_logfile nicht mehr vorkommen) bleibt
    unberuehrt (return False).

    Returns True bei Erfolg, False bei OSError.
    """
    symlink_path = log_dir / "simpleft8.log"
    if symlink_path.exists() and not symlink_path.is_symlink():
        # Sollte nach Archive-Schritt nicht passieren — defensiv abbrechen.
        return False
    tmp_link = log_dir / "simpleft8.log.tmp"
    try:
        # Stale tmp-Link von vorigem Abbruch entfernen
        if tmp_link.is_symlink() or tmp_link.exists():
            tmp_link.unlink()
        os.symlink(target.name, tmp_link)  # relativer Link, robuster
        os.replace(tmp_link, symlink_path)
        return True
    except OSError:
        # Aufraeumen + Fallback
        try:
            if tmp_link.is_symlink() or tmp_link.exists():
                tmp_link.unlink()
        except OSError:
            pass
        return False


def setup_main_log(log_dir: Path | None = None,
                   keep_days: int = 7) -> tuple[Path, "object"]:
    """Eintritts-API: Cleanup + Archivierung + Symlink + Datei-Open.

    Returns ``(path, file_handle)``. Auf Fehlerpfad: Fallback auf
    ``simpleft8.log`` direkt im append-mode (kein Symlink, kein
    Rotation), App laeuft normal weiter.
    """
    if log_dir is None:
        log_dir = Path.home() / ".simpleft8"

    log_dir = Path(log_dir)
    fallback_path = log_dir / "simpleft8.log"

    try:
        log_dir.mkdir(parents=True, exist_ok=True)
        cleanup_old_main_logs(log_dir, keep_days=keep_days)
        _archive_legacy_logfile(log_dir)

        today_path = dated_log_filename(log_dir)
        symlink_ok = _setup_symlink(log_dir, today_path)

        # Datei oeffnen (datiert, append, line-buffered)
        handle = open(today_path, "a", buffering=1)
        # Wenn Symlink fehlschlug, Mike sieht die datierte Datei direkt
        # — dokumentieren via stderr (einmalig).
        if not symlink_ok:
            print(f"[log_setup] Symlink-Setup fehlgeschlagen — Log nur "
                  f"direkt unter {today_path.name} verfuegbar.",
                  file=sys.__stderr__)
        return today_path, handle
    except OSError as e:
        # Worst-Case-Fallback: alter Pfad ohne Rotation
        print(f"[log_setup] Rotation fehlgeschlagen ({e}) — Fallback "
              f"auf alten Pfad ohne Rotation.", file=sys.__stderr__)
        try:
            handle = open(fallback_path, "a", buffering=1)
            return fallback_path, handle
        except OSError as e2:
            # Wenn auch das fehlschlaegt: kein File-Log, App laeuft trotzdem.
            print(f"[log_setup] File-Log komplett deaktiviert ({e2}).",
                  file=sys.__stderr__)
            return fallback_path, sys.__stdout__
