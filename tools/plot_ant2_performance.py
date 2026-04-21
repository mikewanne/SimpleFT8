"""Diagramm 2 — ANT2 Performance: Win-Rate % + Ø ΔSNR pro Stunde.

Zeigt stündlich:
  - Balken: Ant2 Win-Rate % (wie oft ANT2 besser als ANT1)
  - Linie:  Ø ΔSNR wenn A2 gewinnt (wie viel dB besser)
  - Linie:  Ø ΔSNR gesamt (A2-A1 über alle verglichenen Stationen)

Aufruf: ./venv/bin/python3 tools/plot_ant2_performance.py
Optionen:
  --band 20m          (Standard: 20m, auch 40m möglich)
  --date 2026-04-21
  --out  plot.png
"""
import re, glob, sys, os
from datetime import datetime
from collections import defaultdict

band = "20m"
date = "2026-04-21"
out_file = None
args = sys.argv[1:]
for i, arg in enumerate(args):
    if arg == "--band" and i+1 < len(args): band = args[i+1]
    if arg == "--date" and i+1 < len(args): date = args[i+1]
    if arg == "--out"  and i+1 < len(args): out_file = args[i+1]

BASE = os.path.join(os.path.dirname(__file__), "..", "statistics")

MODES = {
    "Div Standard": ("Diversity_Normal", "#F5A623"),
    "Div DX":       ("Diversity_Dx",    "#7ED321"),
}

def parse_div(path):
    rows = []
    try:
        with open(path) as f:
            for line in f:
                m = re.match(r'\| (\d{2}:\d{2}:\d{2}) \| (\d+) \| (-?\d+) \| (\d+) \| ([+-]\d+\.\d+) \|', line)
                if m:
                    rows.append({
                        "h":    int(m.group(1)[:2]),
                        "st":   int(m.group(2)),
                        "ant2w":int(m.group(4)),
                        "dsnr": float(m.group(5)),
                    })
    except FileNotFoundError:
        pass
    return rows

import matplotlib
matplotlib.use("Agg" if out_file else "MacOSX")
import matplotlib.pyplot as plt
import numpy as np

fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 9), sharex=False)
fig.patch.set_facecolor("#1a1a2e")
for ax in (ax1, ax2):
    ax.set_facecolor("#12122a")
    ax.grid(True, color="#333355", linewidth=0.5, alpha=0.7)
    ax.spines[:].set_color("#444466")

has_data = False
bar_width = 0.35
offsets = {"Div Standard": -0.18, "Div DX": +0.18}

for label, (folder, color) in MODES.items():
    files = sorted(glob.glob(f"{BASE}/{folder}/{band}/FT8/{date}_*.md"))
    # auch alle Dateien mit diesem Datum (mehrstündige Sessions)
    ymd = date[:10]
    files = sorted(glob.glob(f"{BASE}/{folder}/{band}/FT8/{ymd}_*.md"))
    rows = []
    for f in files:
        rows.extend(parse_div(f))
    if not rows:
        print(f"  {label}: keine Daten für {date} {band}")
        continue

    by_hour = defaultdict(list)
    for r in rows:
        by_hour[r["h"]].append(r)

    hours = sorted(by_hour.keys())
    win_rates   = []
    dsnr_all    = []   # Ø ΔSNR aller verglichenen Zyklen
    dsnr_when_a2= []   # Ø ΔSNR nur wenn A2 gewann (positiv)

    for h in hours:
        hr = by_hour[h]
        wins = sum(r["ant2w"] for r in hr)
        total= sum(r["st"]    for r in hr)
        win_rates.append(wins/total*100 if total else 0)

        ds_all = [r["dsnr"] for r in hr if r["dsnr"] != 0.0]
        dsnr_all.append(sum(ds_all)/len(ds_all) if ds_all else 0)

        ds_pos = [r["dsnr"] for r in hr if r["dsnr"] > 0]
        dsnr_when_a2.append(sum(ds_pos)/len(ds_pos) if ds_pos else 0)

    x = np.array(hours) + offsets[label]
    off = offsets[label]

    # Diagramm 1: Win-Rate Balken
    ax1.bar(x, win_rates, width=bar_width, color=color, alpha=0.8,
            label=f"{label}", zorder=3)
    for xi, v in zip(x, win_rates):
        ax1.text(xi, v+0.5, f"{v:.0f}%", ha="center", va="bottom",
                 color=color, fontsize=8, fontweight="bold")

    # Diagramm 2: ΔSNR Linien
    hx = np.array(hours)
    ax2.plot(hx, dsnr_all, color=color, marker="o", linewidth=2,
             markersize=6, label=f"{label} — Ø ΔSNR gesamt")
    ax2.plot(hx, dsnr_when_a2, color=color, marker="^", linewidth=1.5,
             markersize=6, linestyle="--", alpha=0.7,
             label=f"{label} — Ø ΔSNR wenn A2 gewinnt")
    for xi, v in zip(hx, dsnr_all):
        ax2.text(xi, v-0.08, f"{v:+.1f}", ha="center", va="top",
                 color=color, fontsize=8)
    has_data = True

if not has_data:
    print(f"Keine Diversity-Daten für {date} {band} gefunden.")
    sys.exit(0)

# Achsen Diagramm 1
ax1.axhline(y=50, color="#FF6B6B", linewidth=1, linestyle=":", alpha=0.5)
ax1.set_ylabel("ANT2 Win-Rate %\n(Anteil Stationen wo ANT2 > ANT1)", color="#CCCCCC", fontsize=10)
ax1.set_title(f"{band} FT8 — ANT2 Performance {date}\nOben: Wie oft ANT2 besser  |  Unten: Um wieviel dB",
              color="white", fontsize=13, pad=10)
ax1.legend(facecolor="#1a1a2e", edgecolor="#444466", labelcolor="white", fontsize=10)
ax1.set_ylim(0, 65)
ax1.yaxis.set_tick_params(labelcolor="#CCCCCC")

# Achsen Diagramm 2
ax2.axhline(y=0, color="#888888", linewidth=1.2, linestyle="-", alpha=0.8)
ax2.set_xlabel("Stunde (UTC)", color="#CCCCCC", fontsize=11)
ax2.set_ylabel("Ø ΔSNR (A2 − A1) in dB\npositiv = A2 besser", color="#CCCCCC", fontsize=10)
ax2.legend(facecolor="#1a1a2e", edgecolor="#444466", labelcolor="white", fontsize=9)
ax2.yaxis.set_tick_params(labelcolor="#CCCCCC")
ax2.xaxis.set_tick_params(labelcolor="#CCCCCC")

# X-Ticks für beide
all_hours = sorted(set(
    h for folder, _ in MODES.values()
    for f in glob.glob(f"{BASE}/{folder}/{band}/FT8/{date}_*.md")
    for r in parse_div(f)
    for h in [r["h"]]
))
if all_hours:
    for ax in (ax1, ax2):
        ax.set_xticks(all_hours)
        ax.set_xticklabels([f"{h:02d}:xx" for h in all_hours],
                           color="#CCCCCC", fontsize=9)

plt.tight_layout(h_pad=2)

if out_file:
    plt.savefig(out_file, dpi=150, bbox_inches="tight", facecolor="#1a1a2e")
    print(f"Gespeichert: {out_file}")
else:
    plt.savefig(f"/tmp/plot_ant2_{band}_{date}.png", dpi=150,
                bbox_inches="tight", facecolor="#1a1a2e")
    print(f"Gespeichert: /tmp/plot_ant2_{band}_{date}.png")
    os.system(f"open /tmp/plot_ant2_{band}_{date}.png")
