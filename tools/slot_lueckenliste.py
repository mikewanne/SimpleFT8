#!/usr/bin/env python3
"""SimpleFT8 — Slot-Lueckenliste fuer auswertung/Slot-Lueckenliste.md.

Anders als tools/luecken.py (LUECKEN.md, nur Slots <=2 Tage):
- Listet ALLE 216 Slots (24h x 3 Baender x 3 Modi)
- Gruppiert nach Tag-Anzahl (0,1,2,3,4,5,6+ Tage)
- Quelle: statistics/<Modus>/<Band>/FT8/YYYY-MM-DD_HH.md (unique Tage)

Aufruf: ./venv/bin/python3 tools/slot_lueckenliste.py
"""

from __future__ import annotations

import re
from collections import defaultdict
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATS = ROOT / "statistics"
OUT = ROOT / "auswertung" / "Slot-Lueckenliste.md"

BANDS = ["40m", "30m", "20m"]
MODES = [
    ("Normal", "Normal"),
    ("Diversity_Normal", "Diversity Std"),
    ("Diversity_Dx", "Diversity DX"),
]
GOAL_DAYS = 5

_FILE_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})_(\d{2})\.md$")


def utc_to_berlin(utc_h: int) -> int:
    """UTC -> Berliner Zeit (Sommerzeit CEST = UTC+2)."""
    return (utc_h + 2) % 24


def count_unique_days(mode_dir: str, band: str, utc_h: int) -> int:
    """Anzahl unique Messtage fuer (mode, band, hour) — ignoriert Spotlight-Duplikate."""
    target = STATS / mode_dir / band / "FT8"
    if not target.is_dir():
        return 0
    days = set()
    for f in target.iterdir():
        m = _FILE_RE.match(f.name)
        if not m:
            continue
        day, h = m.group(1), int(m.group(2))
        if h == utc_h:
            days.add(day)
    return len(days)


def main() -> None:
    by_count: dict[int, list[tuple[int, int, str, str]]] = defaultdict(list)
    total = 0

    for utc_h in range(24):
        berlin_h = utc_to_berlin(utc_h)
        for band in BANDS:
            for mode_dir, mode_label in MODES:
                n = count_unique_days(mode_dir, band, utc_h)
                by_count[n].append((berlin_h, utc_h, band, mode_label))
                total += 1

    # Sortierung pro Bucket: nach Berlin-Stunde, dann Band-Reihenfolge, dann Modus
    band_idx = {b: i for i, b in enumerate(BANDS)}
    mode_idx = {m[1]: i for i, m in enumerate(MODES)}
    for k in by_count:
        by_count[k].sort(key=lambda x: (x[0], band_idx[x[2]], mode_idx[x[3]]))

    counts = sorted(by_count.keys())
    today = date.today().isoformat()

    lines: list[str] = []
    lines.append(f"# Slot-Lückenliste (Stand {today})\n")
    lines.append("Pro (Berlin-Stunde, Band, Modus) erfasst: Anzahl unique Tage mit Daten.")
    lines.append("Berlin = UTC+2 (Sommerzeit). Bänder: 40m/30m/20m FT8 nur (Statistik-Filter v0.63).")
    lines.append("Modi: Normal / Diversity Std / Diversity DX.\n")
    lines.append(f"**Ziel:** {GOAL_DAYS} Tage flächendeckend pro Slot (siehe `feedback_statistics_strategy.md`).\n")
    lines.append("---\n")

    # Verteilung
    lines.append("## Verteilung\n")
    lines.append("| Tage | Slots | Anteil | Status |")
    lines.append("|---|---|---|---|")
    for k in counts:
        n = len(by_count[k])
        pct = round(100 * n / total)
        if k == 0:
            status = "komplett leer"
        elif k < 3:
            status = "dünn"
        elif k < GOAL_DAYS - 1:
            status = "mittel"
        elif k < GOAL_DAYS:
            status = "nahe Ziel"
        elif k == GOAL_DAYS:
            status = "**Ziel erreicht**"
        else:
            status = "über Ziel"
        lines.append(f"| {k} | {n} | {pct} % | {status} |")
    lines.append(f"| **Gesamt** | **{total}** | 100 % | (24h × 3 Bänder × 3 Modi) |\n")
    goal_reached = sum(len(by_count[k]) for k in counts if k >= GOAL_DAYS)
    lines.append(f"**Ziel-Erreicht: {goal_reached}/{total} Slots = {goal_reached*100/total:.1f} %.**\n")
    lines.append("---\n")

    # Pro Bucket
    for k in counts:
        entries = by_count[k]
        if k == 0:
            head = f"## 0 Tage erfasst — {len(entries)} Slots (Priorität 1)"
        elif k == 1:
            head = f"## 1 Tag erfasst — {len(entries)} Slots"
        elif k == GOAL_DAYS:
            head = f"## {k} Tage erfasst — {len(entries)} Slots (Ziel erreicht ✓)"
        elif k > GOAL_DAYS:
            head = f"## {k} Tage erfasst — {len(entries)} Slot{'s' if len(entries) != 1 else ''}"
        elif k == GOAL_DAYS - 1:
            head = f"## {k} Tage erfasst — {len(entries)} Slots (nahe Ziel)"
        else:
            head = f"## {k} Tage erfasst — {len(entries)} Slots"
        lines.append(head + "\n")
        lines.append("```")
        for berlin_h, utc_h, band, mode_label in entries:
            tag_str = f"{k} Tag" if k == 1 else f"{k} Tage"
            lines.append(
                f"{berlin_h:02d}:00 Berlin (={utc_h:02d} UTC)  {band:4s}  "
                f"{mode_label:<14s}  {tag_str}"
            )
        lines.append("```\n")
        lines.append("---\n")

    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"OK: {OUT} ({total} Slots, Ziel-Erreicht {goal_reached})")


if __name__ == "__main__":
    main()
