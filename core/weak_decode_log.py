"""SimpleFT8 Weak-Decode-Log — schwache Decodes (SNR <= -21 dB) sammeln.

Mike-Wunsch 28.05.2026 (P152): Nach P150 (kMin_score 10->4) sehen wir mehr
tiefe Decodes. Es gibt KEINE Vorher-Werte zum Vergleich. Also ab jetzt jeden
schwachen Decode in eine eigene Liste schreiben → empirischer Beweis ob der
Decoder-Fix tiefe Stationen bringt (Falkland-Klasse, DXpeditionen).

Unterschied zu core/debug_log.py:
- ALWAYS-ON (kein Toggle) — Mike will keine Settings, die Liste füllt sich
  einfach
- Eigene Tagesdatei ~/.simpleft8/weak_decodes_YYYY-MM-DD.log (UTC)
- keep_days=7 (Trend über mehrere Tage, nicht nur Diagnose-Tag)

Format: `HH:MM:SS | +/-NN dB | <raw> | NNNN Hz | band mode`
Beispiel: `14:23:01 | -24 dB | DL1ABC OE5XYZ -15 | 1234 Hz | 20m FT8`
"""
from __future__ import annotations

import threading
from datetime import datetime, timedelta
from pathlib import Path

LOG_DIR = Path.home() / ".simpleft8"

# SNR <= dieser Wert wird geloggt. -21 dB = alte Decoder-Grenze (vor P150),
# alles darunter ist die "neue" Zone die kMin_score=4 erschließt.
WEAK_SNR_THRESHOLD = -21

_lock = threading.Lock()


def _current_path() -> Path:
    """Heutige Datei: weak_decodes_YYYY-MM-DD.log (UTC, konsistent mit FT8)."""
    today = datetime.utcnow().strftime("%Y-%m-%d")
    return LOG_DIR / f"weak_decodes_{today}.log"


def log_weak_decodes(entries, band: str, mode: str) -> None:
    """Mehrere schwache Decodes eines Slots in EINEM File-Append schreiben.

    Batched (R1-V4-pro-Empfehlung): ein open() pro Slot statt pro Decode —
    konstante I/O-Last auch bei Pile-up. Always-on, silent-fail.

    Args:
        entries: Liste von (snr, msg_text, freq_hz)-Tupeln (snr <= Threshold,
            Filterung macht der Aufrufer).
        band: aktuelles Band (z.B. "20m").
        mode: aktueller Modus (z.B. "FT8").
    """
    if not entries:
        return
    try:
        ts = datetime.utcnow().strftime("%H:%M:%S")
        lines = []
        for snr, msg_text, freq_hz in entries:
            lines.append(
                f"{ts} | {int(snr):+d} dB | {msg_text} | "
                f"{int(freq_hz)} Hz | {band} {mode}\n"
            )
        with _lock:
            LOG_DIR.mkdir(parents=True, exist_ok=True)
            with _current_path().open("a", encoding="utf-8") as f:
                f.writelines(lines)
    except Exception:
        pass  # silent — Logging darf NIE die App crashen


def cleanup_old_files(keep_days: int = 7) -> int:
    """Alte weak_decodes_*.log löschen (Default 7 Tage für Trend-Sicht).

    Returns Anzahl gelöschter Dateien.
    """
    if not LOG_DIR.exists():
        return 0
    cutoff = datetime.utcnow() - timedelta(days=keep_days)
    cutoff = cutoff.replace(hour=0, minute=0, second=0, microsecond=0)
    deleted = 0
    for f in LOG_DIR.glob("weak_decodes_*.log"):
        try:
            date_str = f.stem.replace("weak_decodes_", "")
            file_date = datetime.strptime(date_str, "%Y-%m-%d")
            if file_date < cutoff:
                f.unlink()
                deleted += 1
        except (ValueError, OSError):
            continue
    return deleted
