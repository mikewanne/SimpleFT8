#!/usr/bin/env python3
"""SimpleFT8 Auswertungs-Script — PNG-Diagramme aus statistics/ Markdown-Dateien.

Aufruf: python3 scripts/generate_plots.py
Output: auswertung/stationen_<band>_<proto>.png
        auswertung/diversity_<band>_<proto>.png

X-Achse: Stunde des Tages (00–23 UTC), gemittelt über alle Messtage.
Konfidenzband: Min–Max der Tages-Mittelwerte (Tag-zu-Tag-Variabilität).
"""

import re
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.colors as mc
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import numpy as np

BASE_DIR = Path(__file__).parent.parent
STATS_DIR = BASE_DIR / "statistics"
OUTPUT_DIR = BASE_DIR / "auswertung"

RX_MODES = ["Normal", "Diversity_Normal", "Diversity_Dx"]

DARK_BG = "#1e1e1e"
DARK_FG = "#d4d4d4"
DARK_GRID = "#333333"

COLORS = {
    "Normal":           "#aaaaaa",  # grau — Baseline, kein Diversity
    "Diversity_Normal": "#4e9af1",  # blau — Standard-Diversity
    "Diversity_Dx":     "#f0a050",  # orange — DX-Diversity
    "rescue":           "#44dd77",  # hell-grün — gerettete Stationen
}

_COL_MAP = {
    "zeit": "zeit",
    "stationen": "stationen",
    "ø snr": "avg_snr",
    "ant2 wins": "ant2_wins",
    "ø δsnr": "avg_delta_snr",
    "call": "call",
    "ant1 db": "ant1_db",
    "ant2 db": "ant2_db",
    "δ db": "delta_db",
    "gewinner": "gewinner",
    "saved": "saved",
}

# ── Erklärungstexte (rechtsbündig, mit \n strukturiert) ──────────────────────

EXPL_STATIONEN = (
    "Was sehe ich?\n"
    "  Jede Kurve = ein Empfangsmodus, Linie = Mittelwert aller Sitzungen zu dieser UTC-Stunde.\n"
    "  Schattiertes Band = Schwankung zwischen verschiedenen Messtagen.\n"
    "\n"
    "FT8 ist ein digitaler Funkmodus — er überträgt auch extrem schwache Signale über tausende Kilometer.\n"
    "Mehr Stationen = Band offen (Ionosphäre reflektiert gut). Diversity = System wählt\n"
    "automatisch die empfangsstärkere von zwei Antennen."
)

def _expl_diversity(band: str, protocol: str) -> str:
    return (
        "Was sehe ich?\n"
        "  Grau = Normal (1 Antenne)  |  Blau = Diversity Standard  |  Orange = Diversity DX.\n"
        "  Grüne Kappe oben = Stationen, die ANT1 allein NICHT dekodieren konnte (Signal unter −24 dB,\n"
        "  FT8-Decodierschwelle) — ANT2 hat sie gerettet. +N zeigt wie viele das pro Stunde waren.\n"
        "\n"
        "Die Modi wurden an verschiedenen Tagen gemessen. Da jede UTC-Stunde über viele Tage gemittelt\n"
        "wird (Mo 18:00, Di 18:00, ...), gleichen sich gute und schlechte Funkbedingungen für alle Modi\n"
        "statistisch aus — der Vergleich ist fair. Diversity DX optimiert gezielt auf schwache Signale.\n"
        "\n"
        f"Rohdaten: statistics/{{Modus}}/{band}/{protocol}/  ·  github.com/mikewanne/SimpleFT8"
    )


# ── Markdown-Parser ───────────────────────────────────────────────────────────

def _normalize_col(raw: str) -> str:
    key = raw.strip().lower()
    return _COL_MAP.get(key, key.replace(" ", "_"))


def parse_md_table(filepath: Path) -> list[dict]:
    rows = []
    headers = None
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.rstrip()
            if not line.startswith("|"):
                if line.startswith("## "):
                    break
                continue
            parts = [p.strip() for p in line.split("|")]
            parts = [p for p in parts if p != ""]
            if not parts:
                continue
            if all(re.match(r"^[-:]+$", p) for p in parts):
                continue
            if headers is None:
                headers = [_normalize_col(p) for p in parts]
            else:
                row = {}
                for i, key in enumerate(headers):
                    row[key] = parts[i] if i < len(parts) else ""
                rows.append(row)
    return rows


def _to_float(val) -> float | None:
    try:
        return float(str(val).replace("+", ""))
    except (ValueError, AttributeError):
        return None


def _to_int(val) -> int | None:
    try:
        return int(val)
    except (ValueError, AttributeError):
        return None


def _file_hour(filepath: Path) -> int | None:
    try:
        return datetime.strptime(filepath.stem, "%Y-%m-%d_%H").hour
    except ValueError:
        return None


def _file_date(filepath: Path) -> str | None:
    try:
        return datetime.strptime(filepath.stem, "%Y-%m-%d_%H").strftime("%Y-%m-%d")
    except ValueError:
        return None


# ── Daten-Aggregation ─────────────────────────────────────────────────────────

def load_hourly_averages(stats_dir: Path, rx_mode: str, band: str,
                         protocol: str) -> dict[int, list[float]]:
    """Pro Stunde des Tages: Liste der Tagesmittelwerte (Stationen)."""
    mode_dir = stats_dir / rx_mode / band / protocol
    if not mode_dir.exists():
        return {}
    result: dict[int, list[float]] = defaultdict(list)
    for fp in sorted(mode_dir.glob("*.md")):
        h = _file_hour(fp)
        if h is None:
            continue
        rows = parse_md_table(fp)
        vals = [_to_int(r.get("stationen", "")) for r in rows]
        vals = [v for v in vals if v is not None]
        if vals:
            result[h].append(sum(vals) / len(vals))
    return dict(result)


def load_wins_averages(stats_dir: Path, band: str,
                       protocol: str) -> dict[int, list[float]]:
    """Ant2 Wins pro Stunde des Tages (Diversity_Dx)."""
    mode_dir = stats_dir / "Diversity_Dx" / band / protocol
    if not mode_dir.exists():
        return {}
    result: dict[int, list[float]] = defaultdict(list)
    for fp in sorted(mode_dir.glob("*.md")):
        h = _file_hour(fp)
        if h is None:
            continue
        rows = parse_md_table(fp)
        vals = [_to_int(r.get("ant2_wins", "")) for r in rows]
        vals = [v for v in vals if v is not None]
        if vals:
            result[h].append(sum(vals) / len(vals))
    return dict(result)


def load_rescue_by_hour(stats_dir: Path, mode: str, band: str,
                        protocol: str) -> dict[int, float]:
    """Rescue-Events pro Stunde des Tages, gemittelt über Messtage."""
    stations_dir = stats_dir / mode / band / protocol / "stations"
    if not stations_dir.exists():
        return {}
    per_day_hour: dict[tuple, int] = defaultdict(int)
    for fp in sorted(stations_dir.glob("*.md")):
        h = _file_hour(fp)
        d = _file_date(fp)
        if h is None or d is None:
            continue
        for row in parse_md_table(fp):
            a1 = _to_float(row.get("ant1_db", ""))
            a2 = _to_float(row.get("ant2_db", ""))
            if a1 is not None and a2 is not None and a1 <= -24 and a2 > -24:
                per_day_hour[(d, h)] += 1
    hour_totals: dict[int, list[int]] = defaultdict(list)
    for (d, h), count in per_day_hour.items():
        hour_totals[h].append(count)
    return {h: sum(v) / len(v) for h, v in hour_totals.items()}


def _aggregate(hour_vals: dict[int, list[float]]) -> dict[int, dict]:
    result = {}
    for hour, vals in sorted(hour_vals.items()):
        result[hour] = {
            "mean": sum(vals) / len(vals),
            "min": min(vals),
            "max": max(vals),
            "n_days": len(vals),
        }
    return result


def _hours_x(agg: dict[int, dict]):
    if not agg:
        return [], [], [], []
    lo, hi = min(agg), max(agg)
    xs = list(range(lo, hi + 1))
    NaN = float("nan")
    means = [agg[h]["mean"] if h in agg else NaN for h in xs]
    mins  = [agg[h]["min"]  if h in agg else NaN for h in xs]
    maxs  = [agg[h]["max"]  if h in agg else NaN for h in xs]
    return xs, means, mins, maxs


def _n_days_label(agg: dict[int, dict]) -> str:
    if not agg:
        return ""
    n = max(v["n_days"] for v in agg.values())
    return f"Basis: {n} Messtag{'e' if n > 1 else ''}"


# ── Gradient-Balken ───────────────────────────────────────────────────────────

def _gradient_bars(ax, x_positions, heights, width: float,
                   top_color: str, label: str | None = None,
                   alpha: float = 1.0, zorder: int = 2) -> mpatches.Patch | None:
    """Zeichnet Balken mit vertikalem Farbverlauf (BG → top_color)."""
    cmap = mc.LinearSegmentedColormap.from_list("g", [DARK_BG, top_color])
    gradient = np.linspace(0, 1, 256).reshape(256, 1)

    for x, h in zip(x_positions, heights):
        if h is None or h <= 0.001:
            continue
        ax.imshow(
            gradient, aspect="auto", origin="lower",
            extent=[x - width / 2, x + width / 2, 0, h],
            cmap=cmap, zorder=zorder, alpha=alpha,
        )

    if label:
        return mpatches.Patch(facecolor=top_color, alpha=0.85, label=label)
    return None


def _draw_rescue_caps(ax, x_positions, station_vals, rescue_vals,
                      bar_w: float, max_val: float) -> bool:
    """Grüne Rescue-Kappen oben auf Diversity-Balken + +N Labels."""
    drawn = False
    for xi, sv, rv in zip(x_positions, station_vals, rescue_vals):
        if rv < 0.5 or sv < 0.5:
            continue
        base = max(0.0, sv - rv)
        ax.bar(xi, rv, bottom=base, width=bar_w,
               color="#44dd77", alpha=0.92, zorder=3, linewidth=0)
        ax.text(xi, sv + max_val * 0.016, f"+{rv:.0f}",
                ha="center", va="bottom", fontsize=7,
                color="#55ee88", fontweight="bold", zorder=5)
        drawn = True
    return drawn


# ── Achsen-Setup ──────────────────────────────────────────────────────────────

def _setup_dark_ax(ax):
    ax.set_facecolor(DARK_BG)
    ax.tick_params(colors=DARK_FG, labelsize=8)
    ax.xaxis.label.set_color(DARK_FG)
    ax.yaxis.label.set_color(DARK_FG)
    ax.title.set_color(DARK_FG)
    for spine in ax.spines.values():
        spine.set_color(DARK_GRID)
    ax.grid(True, color=DARK_GRID, linewidth=0.5, alpha=0.6, zorder=0)


def _hour_ticks_line(ax, xs: list[int]):
    ax.set_xticks(list(range(0, 24)))
    ax.set_xticklabels(
        [f"{h:02d}:00" for h in range(24)],
        fontsize=7, color=DARK_FG, rotation=45, ha="right",
    )
    if xs:
        ax.set_xlim(max(0, min(xs) - 0.5), min(23, max(xs) + 0.5))


def _hour_ticks_bar(ax, x_pos: list[int], hours: list[int]):
    ax.set_xticks(x_pos)
    ax.set_xticklabels(
        [f"{h:02d}:00" for h in hours],
        fontsize=8, color=DARK_FG, rotation=45, ha="right",
    )


def _footer(fig, text: str):
    fig.text(
        0.01, 0.01, text,
        ha="left", va="bottom",
        fontsize=8, color="#aaaaaa",
        linespacing=1.6,
        transform=fig.transFigure,
    )


# ── Diagramm 1: Stationen über 24h ───────────────────────────────────────────

def create_stations_diagram(band: str, protocol: str):
    fig, ax = plt.subplots(figsize=(14, 6.5), facecolor=DARK_BG)
    _setup_dark_ax(ax)

    has_data = False
    all_xs: list[int] = []
    n_days_set: set[str] = set()

    for rx_mode in RX_MODES:
        hour_vals = load_hourly_averages(STATS_DIR, rx_mode, band, protocol)
        if not hour_vals:
            continue
        agg = _aggregate(hour_vals)
        xs, means, mins, maxs = _hours_x(agg)
        if not xs:
            continue
        all_xs.extend(xs)
        n_days_set.add(_n_days_label(agg))

        color = COLORS[rx_mode]
        label = rx_mode.replace("_", " ")
        ax.plot(xs, means, color=color, label=label, linewidth=2.5, zorder=3)
        ax.fill_between(xs, mins, maxs, color=color, alpha=0.15, zorder=2)
        has_data = True

    if not has_data:
        plt.close(fig)
        return

    _hour_ticks_line(ax, all_xs)
    ax.set_xlabel("Stunde (UTC)", color=DARK_FG, labelpad=6)
    ax.set_ylabel("Ø Stationen / 15s-Zyklus", color=DARK_FG)
    basis = " · ".join(sorted(n_days_set))
    ax.set_title(
        f"Empfangene Stationen — {band} {protocol}   ({basis})",
        color=DARK_FG, fontsize=13, pad=10,
    )
    leg = ax.legend(facecolor="#2a2a2a", edgecolor=DARK_GRID, framealpha=0.9)
    for t in leg.get_texts():
        t.set_color(DARK_FG)

    _footer(fig, EXPL_STATIONEN)
    plt.tight_layout()
    plt.subplots_adjust(bottom=0.30, right=0.98)

    out = OUTPUT_DIR / f"stationen_{band}_{protocol}.png"
    fig.savefig(out, dpi=150, bbox_inches="tight", facecolor=DARK_BG)
    plt.close(fig)
    print(f"  ✓ {out.name}")


# ── Diagramm 2: 3-Modus Vergleich (Normal | Diversity Standard | Diversity DX) ─

_MODE_ORDER  = ["Normal", "Diversity_Normal", "Diversity_Dx"]
_MODE_LABELS = {
    "Normal":           "Normal (1 Antenne)",
    "Diversity_Normal": "Diversity Standard",
    "Diversity_Dx":     "Diversity DX",
}
_MODE_OFFSETS = {"Normal": -0.27, "Diversity_Normal": 0.0, "Diversity_Dx": +0.27}


def create_diversity_diagram(band: str, protocol: str):
    bar_w = 0.22

    agg_all: dict[str, dict] = {}
    rescue_all: dict[str, dict] = {}
    for mode in _MODE_ORDER:
        hv = load_hourly_averages(STATS_DIR, mode, band, protocol)
        if hv:
            agg_all[mode] = _aggregate(hv)
        if mode != "Normal":
            r = load_rescue_by_hour(STATS_DIR, mode, band, protocol)
            if r:
                rescue_all[mode] = r

    if not agg_all:
        return

    all_hours = sorted(set().union(*[set(a.keys()) for a in agg_all.values()]))
    n = len(all_hours)
    if n == 0:
        return

    x_base = np.arange(n, dtype=float)

    fig, ax = plt.subplots(figsize=(16, 6.5), facecolor=DARK_BG)
    _setup_dark_ax(ax)

    max_val = max(
        (agg[h]["mean"] for agg in agg_all.values() for h in all_hours if h in agg),
        default=1.0,
    )
    ax.set_ylim(0, max_val * 1.28)
    ax.set_xlim(-0.6, n - 0.4)

    handles = []
    for mode in _MODE_ORDER:
        if mode not in agg_all:
            continue
        agg = agg_all[mode]
        x_pos = x_base + _MODE_OFFSETS[mode]
        heights = [agg[h]["mean"] if h in agg else 0.0 for h in all_hours]
        patch = _gradient_bars(ax, x_pos, heights, bar_w,
                               COLORS[mode], label=_MODE_LABELS[mode], zorder=2)
        if patch:
            handles.append(patch)

    any_rescue = False
    for mode in ["Diversity_Normal", "Diversity_Dx"]:
        if mode not in agg_all:
            continue
        agg = agg_all[mode]
        rescue = rescue_all.get(mode, {})
        x_pos = x_base + _MODE_OFFSETS[mode]
        sv_list = [agg[h]["mean"] if h in agg else 0.0 for h in all_hours]
        rv_list  = [rescue.get(h, 0.0) for h in all_hours]
        if _draw_rescue_caps(ax, x_pos, sv_list, rv_list, bar_w, max_val):
            any_rescue = True

    if any_rescue:
        handles.append(mpatches.Patch(facecolor="#44dd77", alpha=0.92,
                                      label="davon gerettet (ANT1 unter −24 dB)"))

    _hour_ticks_bar(ax, list(x_base), all_hours)
    ax.set_xlabel("Stunde (UTC)", color=DARK_FG, labelpad=6)
    ax.set_ylabel("Ø Stationen pro 15s-Zyklus", color=DARK_FG)

    basis_parts = []
    for mode in _MODE_ORDER:
        if mode not in agg_all:
            continue
        n_d = max(v["n_days"] for v in agg_all[mode].values())
        basis_parts.append(f"{_MODE_LABELS[mode]}: {n_d} Tag{'e' if n_d > 1 else ''}")
    basis = " · ".join(basis_parts)

    ax.set_title(
        f"Empfang im Vergleich — {band} {protocol}   ({basis})",
        color=DARK_FG, fontsize=13, pad=10,
    )

    leg = ax.legend(handles=handles, facecolor="#2a2a2a",
                    edgecolor=DARK_GRID, framealpha=0.9, loc="upper left")
    for t in leg.get_texts():
        t.set_color(DARK_FG)

    _footer(fig, _expl_diversity(band, protocol))
    plt.tight_layout()
    plt.subplots_adjust(bottom=0.32, right=0.98)

    out = OUTPUT_DIR / f"diversity_{band}_{protocol}.png"
    fig.savefig(out, dpi=150, bbox_inches="tight", facecolor=DARK_BG)
    plt.close(fig)
    print(f"  ✓ {out.name}")


# ── Haupt ─────────────────────────────────────────────────────────────────────

def discover_bands_protocols() -> set[tuple[str, str]]:
    combos: set[tuple[str, str]] = set()
    if not STATS_DIR.exists():
        return combos
    for mode_dir in STATS_DIR.iterdir():
        if not mode_dir.is_dir() or mode_dir.name not in RX_MODES:
            continue
        for band_dir in mode_dir.iterdir():
            if not band_dir.is_dir():
                continue
            for proto_dir in band_dir.iterdir():
                if proto_dir.is_dir() and proto_dir.name != "stations":
                    combos.add((band_dir.name, proto_dir.name))
    return combos


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    combos = discover_bands_protocols()
    if not combos:
        print(f"Keine Daten in {STATS_DIR}.")
        sys.exit(0)
    for band, protocol in sorted(combos):
        print(f"\n=== {band} / {protocol} ===")
        create_stations_diagram(band, protocol)
        create_diversity_diagram(band, protocol)
    print("\nFertig. Diagramme in:", OUTPUT_DIR)


if __name__ == "__main__":
    main()
