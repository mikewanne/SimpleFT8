#!/usr/bin/env python3
"""SimpleFT8 Luecken-Liste — welche Stunden-Band-Modus-Slots noch zu duenn sind.

Generiert LUECKEN.md mit allen Slots die unter dem 5-Tage-Ziel liegen
(0, 1 oder 2 Mess-Tage), sortiert nach:
1. Tag-Anzahl (0 zuerst, dann 1, dann 2)
2. Berliner Uhrzeit (00:00 → 23:59)

Aufruf: `./venv/bin/python3 tools/luecken.py`
"""

from __future__ import annotations

import glob
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATS = ROOT / "statistics"
OUT = ROOT / "LUECKEN.md"

BANDS = ["40m", "20m"]  # 30m raus seit v0.63-Filter (nur Alt-Daten)
MODES = [
    ("Normal", "Normal"),
    ("Diversity_Normal", "Diversity Std"),
    ("Diversity_Dx", "Diversity DX"),
]
MAX_DAYS = 2  # nur Slots mit ≤ MAX_DAYS Mess-Tagen anzeigen


def utc_to_berlin(utc_h: int) -> int:
    """UTC -> Berliner Zeit (Sommerzeit CEST = UTC+2)."""
    return (utc_h + 2) % 24


def count_files(mode_dir: str, band: str, utc_h: int) -> int:
    """Anzahl YYYY-MM-DD_HH.md Files fuer (mode, band, hour)."""
    pattern = f"{STATS}/{mode_dir}/{band}/FT8/*_{utc_h:02d}.md"
    return len(glob.glob(pattern))


def main() -> None:
    entries: list[tuple[int, int, int, str, str]] = []
    for utc_h in range(24):
        berlin_h = utc_to_berlin(utc_h)
        for band in BANDS:
            for mode_dir, mode_label in MODES:
                n = count_files(mode_dir, band, utc_h)
                if n <= MAX_DAYS:
                    entries.append((n, berlin_h, utc_h, band, mode_label))

    # Sortier: zuerst nach Tag-Anzahl (0 zuerst), dann Berliner Uhrzeit
    entries.sort(key=lambda x: (x[0], x[1]))

    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines: list[str] = []
    lines.append("# SimpleFT8 — Luecken-Liste (5-Tage-Ziel)\n\n")
    lines.append(f"Generiert: {now}\n\n")
    lines.append("Sortiert: erst nach Mess-Tagen (0 zuerst), dann nach Berliner Uhrzeit.\n")
    lines.append("Ziel: 5 Tage flaechendeckend pro Stunde-Band-Modus-Slot.\n\n")
    lines.append("**Bands:** nur 40m + 20m (30m seit v0.63 nicht mehr aktiv geloggt).\n")
    lines.append("**Anzeige-Limit:** Slots mit 0/1/2 Tagen (ab 3 Tagen okay genug).\n\n")
    lines.append("---\n\n")

    # Gruppen-Counts vorab berechnen
    from collections import Counter
    group_counts = Counter(e[0] for e in entries)

    last_n = -1
    n_total = 0
    for n, b_h, u_h, band, mode in entries:
        if n != last_n:
            tagew = "Tag" if n == 1 else "Tage"
            lines.append(f"\n## {n} {tagew} erfasst — {group_counts[n]} Slots\n\n")
            last_n = n
        tagew = "Tag " if n == 1 else "Tage"
        lines.append(
            f"    {b_h:02d}:00 Berlin (={u_h:02d} UTC)  "
            f"{band:<4}  {mode:<14}  {n} {tagew}\n"
        )
        n_total += 1

    OUT.write_text("".join(lines))
    print(f"✓ {OUT.relative_to(ROOT)} geschrieben — {n_total} Luecken-Slots.")


if __name__ == "__main__":
    main()
