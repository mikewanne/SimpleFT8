"""Diagramm 1 — Stationsanzahl 20m: Normal vs Diversity Normal vs Diversity DX.

Aufruf: ./venv/bin/python3 tools/plot_20m_stations.py
Optionen:
  --date 2026-04-21   (Standard: heute)
  --out  plot.png     (Standard: zeigt Fenster)
"""
import re, glob, sys, os
from datetime import datetime
from collections import defaultdict

# Datum aus Args oder heute
date = "2026-04-21"
out_file = None
for i, arg in enumerate(sys.argv[1:]):
    if arg == "--date" and i+1 < len(sys.argv)-1:
        date = sys.argv[i+2]
    if arg == "--out" and i+1 < len(sys.argv)-1:
        out_file = sys.argv[i+2]

BASE = os.path.join(os.path.dirname(__file__), "..", "statistics")
date_short = date.replace("-", "")

MODES = {
    "Normal":       ("Normal",          "#4A90D9", "o", 1.0),
    "Div Standard": ("Diversity_Normal", "#F5A623", "s", 0.85),
    "Div DX":       ("Diversity_Dx",    "#7ED321", "^", 1.0),
}

def parse(path):
    rows = []
    try:
        with open(path) as f:
            for line in f:
                m = re.match(r'\| (\d{2}:\d{2}:\d{2}) \| (\d+) \|', line)
                if m:
                    t = datetime.strptime(f"{date} {m.group(1)}", "%Y-%m-%d %H:%M:%S")
                    rows.append((t, int(m.group(2))))
    except FileNotFoundError:
        pass
    return rows

import matplotlib
matplotlib.use("Agg" if out_file else "MacOSX")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

fig, ax = plt.subplots(figsize=(14, 6))
fig.patch.set_facecolor("#1a1a2e")
ax.set_facecolor("#12122a")

has_data = False
for label, (folder, color, marker, alpha) in MODES.items():
    pattern = f"{BASE}/{folder}/20m/FT8/{date[:7].replace('-','')[:4]}-{date[5:7]}-??_*.md"
    # Alle Dateien dieses Datums laden
    ymd = date  # z.B. 2026-04-21
    files = sorted(glob.glob(f"{BASE}/{folder}/20m/FT8/{ymd[:10]}_*.md"))
    rows = []
    for f in files:
        rows.extend(parse(f))
    if not rows:
        print(f"  {label}: keine Daten für {date}")
        continue
    rows.sort()
    times = [r[0] for r in rows]
    vals  = [r[1] for r in rows]
    ax.plot(times, vals, color=color, label=f"{label} (Ø {sum(vals)/len(vals):.1f} St.)",
            marker=marker, markersize=3, linewidth=1.2, alpha=alpha)
    # Gleitender Mittelwert (±5 Zyklen)
    n = 5
    smooth = [sum(vals[max(0,i-n):i+n+1])/len(vals[max(0,i-n):i+n+1]) for i in range(len(vals))]
    ax.plot(times, smooth, color=color, linewidth=2.5, alpha=0.5, linestyle="--")
    has_data = True

if not has_data:
    print(f"Keine 20m-Daten für {date} gefunden.")
    sys.exit(0)

ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
ax.xaxis.set_major_locator(mdates.MinuteLocator(byminute=[0,15,30,45]))
plt.xticks(rotation=30, color="#CCCCCC", fontsize=9)
plt.yticks(color="#CCCCCC", fontsize=9)
ax.set_xlabel("UTC", color="#CCCCCC", fontsize=11)
ax.set_ylabel("Stationen / Zyklus", color="#CCCCCC", fontsize=11)
ax.set_title(f"20m FT8 — Stationsanzahl {date}\nNormal vs Diversity Standard vs Diversity DX",
             color="white", fontsize=13, pad=12)
ax.grid(True, color="#333355", linewidth=0.5, alpha=0.7)
ax.spines[:].set_color("#444466")
legend = ax.legend(facecolor="#1a1a2e", edgecolor="#444466",
                   labelcolor="white", fontsize=10)
plt.tight_layout()

if out_file:
    plt.savefig(out_file, dpi=150, bbox_inches="tight", facecolor="#1a1a2e")
    print(f"Gespeichert: {out_file}")
else:
    plt.savefig(f"/tmp/plot_20m_stations_{date}.png", dpi=150,
                bbox_inches="tight", facecolor="#1a1a2e")
    print(f"Gespeichert: /tmp/plot_20m_stations_{date}.png")
    os.system(f"open /tmp/plot_20m_stations_{date}.png")
