#!/usr/bin/env python3
"""SimpleFT8 — Diversity-Daten CSV-Export

Liest alle Station-Vergleichs-MDs aus `statistics/Diversity_*/{band}/FT8/stations/`
und schreibt pro Band+Modus eine CSV-Datei nach `auswertung/`.

Use Case: Wissenschaftliche Auswertung (z.B. Pandas/Excel/R), Veroeffentlichung,
Antennen-Optimierungs-Analysen.

Aufruf:
    cd SimpleFT8 && ./venv/bin/python3 scripts/export_diversity_csv.py

Ausgabe:
    auswertung/diversity_data_20m_FT8_Diversity_Normal.csv
    auswertung/diversity_data_20m_FT8_Diversity_Dx.csv
    auswertung/diversity_data_40m_FT8_Diversity_Normal.csv
    auswertung/diversity_data_40m_FT8_Diversity_Dx.csv

CSV-Schema:
    date, time_utc, callsign, ant1_snr_db, ant2_snr_db, delta_db,
    band, mode, scoring_mode, antenna_winner

`antenna_winner` = "A2" wenn delta > 1.0 (Hysterese), sonst "A1".
"""
from __future__ import annotations

import csv
import re
import sys
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
STATS_DIR = BASE_DIR / "statistics"
OUTPUT_DIR = BASE_DIR / "auswertung"

# Welche Modi/Baender exportieren (kongruent zu station_stats.LOGGED_BANDS)
SCORING_MODES = ["Diversity_Normal", "Diversity_Dx"]
BANDS = ["20m", "40m"]
PROTOCOL = "FT8"

# Hysterese-Schwelle (gleicher Wert wie in core/antenna_pref.py)
HYSTERESIS_DB = 1.0

# Markdown-Tabellen-Zeile parsen:
# | 15:26:43 | 4X1YY | -25 | -18 | +7.0 |
ROW_RE = re.compile(
    r"^\|\s*(\d{2}:\d{2}:\d{2})\s*\|\s*(\S+)\s*\|\s*(-?\d+)\s*\|\s*(-?\d+)\s*\|\s*([+-]?[\d.]+)\s*\|"
)


def parse_md_file(fpath: Path, scoring_mode: str, band: str) -> list[dict]:
    """Eine Stations-Vergleichs-MD lesen → Liste von Row-Dicts."""
    rows: list[dict] = []
    date = fpath.stem[:10]  # 2026-04-25 aus 2026-04-25_15.md
    with open(fpath) as f:
        for line in f:
            m = ROW_RE.match(line)
            if not m:
                continue
            time_utc, call, a1_str, a2_str, delta_str = m.groups()
            try:
                a1 = int(a1_str)
                a2 = int(a2_str)
                delta = float(delta_str)
            except ValueError:
                continue
            winner = "A2" if delta >= HYSTERESIS_DB else "A1"
            rows.append({
                "date": date,
                "time_utc": time_utc,
                "callsign": call,
                "ant1_snr_db": a1,
                "ant2_snr_db": a2,
                "delta_db": delta,
                "band": band,
                "mode": PROTOCOL,
                "scoring_mode": scoring_mode,
                "antenna_winner": winner,
            })
    return rows


def export_combo(scoring_mode: str, band: str,
                 output_dir: Path = None) -> tuple[Path, int]:
    """Eine (scoring_mode, band)-Kombi exportieren. Returnt (path, row_count).

    Args:
        scoring_mode: "Diversity_Normal" oder "Diversity_Dx"
        band: "20m" oder "40m"
        output_dir: Ziel-Verzeichnis (Default: auswertung/)
    """
    if output_dir is None:
        output_dir = OUTPUT_DIR
    src_dir = STATS_DIR / scoring_mode / band / PROTOCOL / "stations"
    if not src_dir.exists():
        return None, 0
    rows: list[dict] = []
    for fpath in sorted(src_dir.glob("*.md")):
        rows.extend(parse_md_file(fpath, scoring_mode, band))
    if not rows:
        return None, 0
    out_path = output_dir / f"diversity_data_{band}_{PROTOCOL}_{scoring_mode}.csv"
    output_dir.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    return out_path, len(rows)


def export_all(output_dir: Path = None) -> tuple[int, int, list[Path]]:
    """Alle (band, scoring_mode)-Kombinationen exportieren.

    Returnt (files_written, total_rows, paths) — fuer UI-Feedback nutzbar.
    Wirft KEINE Exception bei fehlenden Daten — gibt einfach 0/0/[] zurueck.
    """
    if output_dir is None:
        output_dir = OUTPUT_DIR
    paths: list[Path] = []
    total_rows = 0
    files_written = 0
    if not STATS_DIR.exists():
        return 0, 0, []
    for band in BANDS:
        for scoring_mode in SCORING_MODES:
            out_path, n = export_combo(scoring_mode, band, output_dir)
            if n > 0 and out_path is not None:
                paths.append(out_path)
                total_rows += n
                files_written += 1
    return files_written, total_rows, paths


def main():
    print(f"{'='*60}")
    print("SimpleFT8 — Diversity-Daten CSV-Export")
    print(f"{'='*60}")
    if not STATS_DIR.exists():
        print(f"[!] Keine Daten in {STATS_DIR}")
        sys.exit(1)
    total_rows = 0
    files_written = 0
    for band in BANDS:
        for scoring_mode in SCORING_MODES:
            out_path, n = export_combo(scoring_mode, band)
            label = f"{band} {scoring_mode}"
            if n == 0:
                print(f"  -  {label:<35s} : keine Daten")
            else:
                rel = out_path.relative_to(BASE_DIR)
                print(f"  ✓  {label:<35s} : {n:>5d} Zeilen → {rel}")
                total_rows += n
                files_written += 1
    print(f"{'='*60}")
    print(f"Fertig: {files_written} CSV-Dateien, {total_rows} Datensaetze gesamt.")


if __name__ == "__main__":
    main()
