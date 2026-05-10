"""SimpleFT8 Debug-Log — strategische Diagnose-Eintraege fuer Bug-Hunt.

Mike-Spec 10.05.2026 (P21):
- 1 Datei pro Tag: ~/.simpleft8/debug_YYYY-MM-DD.log
- Beim App-Start: alle debug_*.log älter als gestern löschen
- Toggle in Settings „Debug-Log schreiben" (an/aus)
- No-op wenn deaktiviert (kein Disk-Write, keine Performance-Kosten)

Verwendung: an strategischen Code-Stellen (Bandwechsel, Antennen-Switch,
Phase-Übergänge) `debug_log("KAT", "msg")` aufrufen. Wenn Bug auftritt:
Log lesen → Eintrag X da → Code lief bis dahin. Eintrag X fehlt → Bug
VOR Stelle X. Klassisches Bisection-Debugging.

Format: `HH:MM:SS.mmm [KAT] message`
Beispiel: `14:35:42.123 [ANT] cmd=ANT2 gain=10dB`
"""
from __future__ import annotations

import os
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path

LOG_DIR = Path.home() / ".simpleft8"

_enabled: bool = False
_lock = threading.Lock()


def set_enabled(enabled: bool) -> None:
    """Aktivieren/Deaktivieren. No-op-Pfad wenn False."""
    global _enabled
    with _lock:
        _enabled = bool(enabled)
    if enabled:
        debug_log("DEBUG", f"Debug-Log aktiviert (Datei {_current_path().name})")


def is_enabled() -> bool:
    with _lock:
        return _enabled


def _current_path() -> Path:
    """Heutige Log-Datei: debug_YYYY-MM-DD.log (UTC fuer Konsistenz mit FT8)."""
    today = datetime.utcnow().strftime("%Y-%m-%d")
    return LOG_DIR / f"debug_{today}.log"


def debug_log(category: str, message: str) -> None:
    """Strategischer Debug-Eintrag.

    No-op wenn Debug-Log deaktiviert. Bei Disk-Fehler: silent skip,
    kein Crash.

    Args:
        category: Kurzer Tag (z.B. "ANT", "BAND", "DIV", "OMNI")
        message: freier Text
    """
    if not _enabled:
        return
    try:
        with _lock:
            if not _enabled:  # double-check after lock
                return
            ts = datetime.utcnow().strftime("%H:%M:%S")
            ms = int((time.time() % 1) * 1000)
            line = f"{ts}.{ms:03d} [{category}] {message}\n"
            LOG_DIR.mkdir(parents=True, exist_ok=True)
            with _current_path().open("a", encoding="utf-8") as f:
                f.write(line)
    except Exception:
        pass  # silent — Debug darf NIE App crashen


def cleanup_old_files(keep_days: int = 1) -> int:
    """Alte debug_*.log-Dateien loeschen.

    Mike-Spec: Tagesdatei + Vortag bleiben (keep_days=1 default).
    Returns Anzahl geloeschter Dateien.
    """
    if not LOG_DIR.exists():
        return 0
    cutoff = datetime.utcnow() - timedelta(days=keep_days)
    deleted = 0
    for f in LOG_DIR.glob("debug_*.log"):
        try:
            stem = f.stem  # "debug_2026-05-09"
            date_str = stem.replace("debug_", "")
            file_date = datetime.strptime(date_str, "%Y-%m-%d")
            if file_date < cutoff.replace(hour=0, minute=0, second=0, microsecond=0):
                f.unlink()
                deleted += 1
        except (ValueError, OSError):
            continue
    return deleted
