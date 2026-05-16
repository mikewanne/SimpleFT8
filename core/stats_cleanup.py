"""90-Tage-Rolling-Window fuer statistics/ (P52, v0.97.41).

Bei App-Start werden Stats-Dateien aelter als ``days`` (Default 90)
geloescht — analog ``core/log_setup.cleanup_old_main_logs`` aber
rekursiv durch alle Modus/Band/Protokoll-Unterverzeichnisse.

Pattern (zwei Formate parallel):
    statistics/<Modus>/<Band>/<Proto>/YYYY-MM-DD_HH.md            # Stunden-Stats
    statistics/<Modus>/<Band>/<Proto>/stations/YYYY-MM-DD_HH.md   # Rescue-Files (Diversity-only)
    statistics/antenna_qso/YYYY-MM-DD.md                          # Antennen-QSO-Log (Tages-Format)

Cutoff: UTC-Datum aus Dateiname (NICHT mtime — Backup/Restore-robust,
weil Restore die mtime ändert aber das Datum im Dateinamen unverändert bleibt).

Fail-silent pro Datei (OSError, ValueError). Idempotent.

Aufruf in ``main.py`` beim App-Start vor Qt-Init:

    from core.stats_cleanup import cleanup_stats_older_than_days
    try:
        deleted = cleanup_stats_older_than_days(stats_dir, days=90)
        if deleted:
            print(f"[Stats-Cleanup] {deleted} Dateien >90 Tage geloescht")
    except Exception as e:
        print(f"[Stats-Cleanup] Fehler ignoriert: {e}")
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta
from pathlib import Path


_DATED_HOUR = re.compile(r"^(\d{4}-\d{2}-\d{2})_\d{2}\.md$")
_DATED_DAY = re.compile(r"^(\d{4}-\d{2}-\d{2})\.md$")


def cleanup_stats_older_than_days(
    stats_dir: Path, days: int = 90
) -> int:
    """Loescht Stats-Files aelter als ``days`` Tage (UTC).

    Berücksichtigt zwei Dateinamen-Pattern:
        ``YYYY-MM-DD_HH.md`` — Stunden-basiert (Haupt-Stats + Rescue)
        ``YYYY-MM-DD.md``    — Tages-basiert (antenna_qso)

    Rekursiver Walk durch alle Unterverzeichnisse. Cutoff aus
    Dateinamen-Datum (NICHT mtime).

    Returns Anzahl geloeschter Dateien. Fail-silent pro Datei.
    """
    stats_dir = Path(stats_dir)
    if not stats_dir.exists():
        return 0
    cutoff = (datetime.utcnow() - timedelta(days=days)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    deleted = 0
    for f in stats_dir.rglob("*.md"):
        try:
            m = _DATED_HOUR.match(f.name) or _DATED_DAY.match(f.name)
            if not m:
                continue
            file_date = datetime.strptime(m.group(1), "%Y-%m-%d")
            if file_date < cutoff:
                f.unlink()
                deleted += 1
        except (ValueError, OSError):
            continue
    return deleted
