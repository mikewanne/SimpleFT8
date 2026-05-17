"""Druckt fertige Markdown-Tabellen-Zeilen mit CI fuer README-Update.

Aufruf:
    ./venv/bin/python3 scripts/print_ci_for_readme.py [BAND ...]

Beispiel:
    ./venv/bin/python3 scripts/print_ci_for_readme.py 40m 20m 30m

Wenn keine Baender angegeben: alle drei (40m, 20m, 30m).

Ausgabe pro Band: Modus | Pooled Mean | vs Normal | 95%-CI | Days | Cycles
- direkt copy-paste-faehig in README-Tabellen.
"""

from __future__ import annotations

import sys
from pathlib import Path


def main(bands: list[str]) -> int:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from bootstrap_ci import compute_mode_comparison_ci, format_ci_short
    from generate_plots import _combo_summary_fair, load_hourly_stats

    stats_dir = Path(__file__).resolve().parent.parent / "statistics"
    protocol = "FT8"

    for band in bands:
        fair = _combo_summary_fair(stats_dir, band, protocol)
        if not fair:
            print(f"## {band} {protocol} — keine Daten\n")
            continue

        try:
            ci_map = compute_mode_comparison_ci(
                stats_dir, band, protocol,
                load_hourly_stats_fn=load_hourly_stats,
            )
        except Exception as e:
            print(f"## {band} {protocol} — CI-Fehler: {e}\n")
            ci_map = {}

        print(f"## {band} {protocol}\n")
        print(
            "| Mode | Stations/15s (Pooled Mean) | vs Normal | 95%-CI "
            "| Days | Cycles |"
        )
        print("|------|:---:|:---:|:---:|:---:|:---:|")

        mode_label = {
            "Normal": "Normal",
            "Diversity_Normal": "Diversity Standard",
            "Diversity_Dx": "Diversity DX",
        }
        order = ["Normal", "Diversity_Normal", "Diversity_Dx"]
        for mode in order:
            if mode not in fair:
                continue
            s = fair[mode]
            avg = s["avg"]
            n_ref = s.get("n_avg_common", 0.0)
            if mode == "Normal" or n_ref <= 0:
                vs = "—"
                ci = "—"
            else:
                pt_pct = (avg / n_ref - 1) * 100
                sign = "+" if pt_pct >= 0 else ""
                vs = f"**{sign}{pt_pct:.0f}%**"
                if mode in ci_map:
                    ci = format_ci_short(*ci_map[mode])
                else:
                    ci = "n/a"
            n_days = s.get("n_days", "—")
            n_cyc = s.get("n_cycles", 0)
            print(
                f"| {mode_label[mode]} | {avg:.1f} | {vs} | {ci} "
                f"| {n_days} | {n_cyc:,} |"
            )
        print()

    return 0


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        args = ["40m", "20m", "30m"]
    sys.exit(main(args))
