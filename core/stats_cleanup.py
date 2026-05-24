"""FIFO-Sliding-Window fuer statistics/ (P116, v0.98.01).

Loest P52 (90-Tage-Datum-Cleanup) ab. Mike-Anforderung 24.05.2026:
saisonale Anpassung der Antennen-Performance (ANT2 = Regenrinne,
Sommer trocken vs. Winter nass) ohne Datenverlust bei langer Funk-
pause. FIFO pro `(Modus, Band, Proto, Stunde)`-Bucket — die juengsten
N Tage je Bucket bleiben erhalten, aelteste werden verdraengt sobald
neue Daten kommen.

Pattern (drei Formate):
    statistics/<Modus>/<Band>/<Proto>/YYYY-MM-DD_HH.md            # FIFO pro Bucket
    statistics/<Modus>/<Band>/<Proto>/stations/YYYY-MM-DD_HH.md   # FIFO pro Bucket
    statistics/antenna_qso/YYYY-MM-DD.md                          # 90-Tage-Datum (BLEIBT)

Default N=30 (DeepSeek-Brainstorm-Konsens): saisonal aktuell (~1 Monat
fuer komplette Aktualisierung bei taeglichem Funken), statistisch
ausreichend (n>=25 fuer Bootstrap-CI), Pause-robust (Daten bleiben
auch nach 6 Monaten Pause).

Antenna_QSO bleibt 90-Tage-Datum-basiert (Tages-Aggregat, passt nicht
zu Stunden-Bucket-Schema).

Bandpilot-Cache wird invalidiert wenn Files geloescht wurden (DeepSeek-
Hinweis R1-Brainstorm: sonst zeigt UI alte Cache-Daten der nicht mehr
existierenden Files).

Aufruf in ``main.py`` beim App-Start vor Qt-Init:

    from core.stats_cleanup import (
        prune_stats_to_max_per_bucket,
        cleanup_antenna_qso_older_than_days,
        invalidate_bandpilot_cache_if_needed,
    )
    deleted = prune_stats_to_max_per_bucket(stats_dir, max_per_bucket=30)
    deleted_qso = cleanup_antenna_qso_older_than_days(stats_dir, days=90)
    invalidate_bandpilot_cache_if_needed(deleted)
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta
from pathlib import Path


_DATED_HOUR = re.compile(r"^(\d{4}-\d{2}-\d{2})_(\d{2})\.md$")
_DATED_DAY = re.compile(r"^(\d{4}-\d{2}-\d{2})\.md$")


def prune_stats_to_max_per_bucket(
    stats_dir: Path, max_per_bucket: int = 30
) -> int:
    """FIFO pro `(Modus, Band, Proto, Stunde)`-Bucket: juengste N Tage behalten.

    Bucket-Key: ``(str(relative_parent_path), hour_str)``. Stations/-Files
    sind eigene Buckets (parallel geschrieben → identische Datums-Liste →
    identisches Pruning-Ergebnis ohne explizite Kopplung).

    Antenna_QSO-Files (Tages-Format) werden ignoriert — separate Funktion
    `cleanup_antenna_qso_older_than_days`.

    Args:
        stats_dir: Pfad zu ``<repo>/statistics``.
        max_per_bucket: Anzahl juengster Tage je Bucket. Default 30.

    Returns:
        Anzahl geloeschter Dateien.
    """
    stats_dir = Path(stats_dir)
    if not stats_dir.exists():
        return 0

    # Bucket-Sammler: (bucket_dir_str, hour_str) -> [(date_str, path), ...]
    buckets: dict[tuple, list[tuple[str, Path]]] = {}
    for f in stats_dir.rglob("*.md"):
        if "antenna_qso" in f.parts:
            continue
        m = _DATED_HOUR.match(f.name)
        if not m:
            continue
        relative = f.relative_to(stats_dir)
        bucket_key = (str(relative.parent), m.group(2))
        buckets.setdefault(bucket_key, []).append((m.group(1), f))

    deleted = 0
    for entries in buckets.values():
        if len(entries) <= max_per_bucket:
            continue
        # Sort: aelteste zuerst, jüngste am Ende
        entries.sort(key=lambda x: x[0])
        # Loesche alles ausser den juengsten N
        for _, f in entries[:-max_per_bucket]:
            try:
                f.unlink()
                deleted += 1
            except OSError:
                continue
    return deleted


def cleanup_antenna_qso_older_than_days(
    stats_dir: Path, days: int = 90
) -> int:
    """Antenna_QSO-Tages-Files: Datum-basierter Cleanup (BLEIBT 90 Tage).

    Antenna_QSO ist Tages-Aggregat (1 File = 1 Tag, kein Stunden-Bucket).
    Schiebe-Register-Schema waere hier nicht sinnvoll — Datum-Cleanup
    bleibt natuerlich.

    Args:
        stats_dir: Pfad zu ``<repo>/statistics``.
        days: Cutoff in Tagen. Default 90.

    Returns:
        Anzahl geloeschter Dateien.
    """
    stats_dir = Path(stats_dir)
    antenna_qso = stats_dir / "antenna_qso"
    if not antenna_qso.exists():
        return 0
    cutoff = (datetime.utcnow() - timedelta(days=days)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    deleted = 0
    for f in antenna_qso.rglob("*.md"):
        try:
            m = _DATED_DAY.match(f.name)
            if not m:
                continue
            file_date = datetime.strptime(m.group(1), "%Y-%m-%d")
            if file_date < cutoff:
                f.unlink()
                deleted += 1
        except (ValueError, OSError):
            continue
    return deleted


def invalidate_bandpilot_cache_if_needed(deleted_count: int) -> None:
    """Bandpilot-Cache invalidieren wenn Files geloescht wurden.

    Verhindert dass UI veraltete Aggregate aus dem persistenten Cache
    zeigt nachdem Source-Files via FIFO-Pruning entfernt wurden. KISS:
    Cache-File komplett loeschen, naechster Bandpilot-Aufruf re-aggregiert
    alle Baender (Bruchteil einer Sekunde).

    No-op wenn nichts geloescht wurde (kein unnoetiger File-Touch).
    """
    if deleted_count == 0:
        return
    cache_path = Path.home() / ".simpleft8" / "bandpilot_hourly.json"
    try:
        if cache_path.exists():
            cache_path.unlink()
    except OSError:
        pass  # Fail-silent, Bandpilot soll nie crashen
