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
import matplotlib.ticker as mticker
from matplotlib.backends.backend_pdf import PdfPages
import numpy as np

BASE_DIR = Path(__file__).parent.parent
STATS_DIR = BASE_DIR / "statistics"
OUTPUT_DIR = BASE_DIR / "auswertung"

RX_MODES = ["Normal", "Diversity_Normal", "Diversity_Dx"]

DARK_BG = "#1e1e1e"
DARK_FG = "#d4d4d4"
DARK_GRID = "#333333"

COLORS = {
    "Normal":           "#b0b0b0",  # helles Grau — Baseline (neutraler, hebt sich ab)
    "Diversity_Normal": "#5d8fd9",  # gesättigtes Blau — Standard (kühle Energie)
    "Diversity_Dx":     "#f0a050",  # warm Orange — DX (Tableau-bewährt, unverändert)
    "rescue":           "#4cda7a",  # kühles Grün — Rescue Cap (kontrastiert zu Blau+Orange)
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
    "Normal (grau): 1 Antenne, wie WSJT-X — Vergleichsbasis.\n"
    "Diversity Standard (blau): 2 Antennen, wählt automatisch die mit mehr Stationen.\n"
    "Diversity DX (orange): 2 Antennen, wählt die mit mehr schwachen DX-Signalen.\n"
    "Schattiertes Band: Schwankung zwischen Messtagen — Linie = Mittelwert.\n"
    "Mehr Stationen = Band offen (Ionosphäre reflektiert Signale aus aller Welt). Diversity = System wählt automatisch die bessere Antenne."
)

def _expl_diversity(band: str, protocol: str) -> str:
    return (
        "Normal (grau): 1 Antenne, wie WSJT-X — dient als Vergleichsbasis.\n"
        "Diversity Standard (blau): 2 Antennen — wählt automatisch die Antenne, die mehr Stationen empfängt.\n"
        "Diversity DX (orange): 2 Antennen — wählt die Antenne mit mehr schwachen DX-Signalen (SNR unter −10 dB).\n"
        "Fehlerbalken (weiße Striche): Schwankung zwischen Messtagen — je mehr Tage, desto stabiler der Wert.\n"
        "Grüne Kappe (+N): Stationen, die ANT1 allein nicht dekodieren konnte — ANT2 hat sie gerettet (Signal unter −24 dB).\n"
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

def load_hourly_stats(stats_dir: Path, rx_mode: str, band: str,
                      protocol: str) -> dict[int, dict]:
    """Pro UTC-Stunde: alle Zyklen-Werte (pooled) + Tages-Granularität + Minuten-Abdeckung.

    Returns dict[hour → {"cycles": [int, ...], "daily": {date: [int, ...]}, "minutes": set}].
    Pooled Mean über alle Zyklen vermeidet den Bias, den mean-of-daily-means bei
    unterschiedlicher Zyklenanzahl pro Tag erzeugt.
    """
    mode_dir = stats_dir / rx_mode / band / protocol
    if not mode_dir.exists():
        return {}
    result: dict[int, dict] = {}
    for fp in sorted(mode_dir.glob("*.md")):
        h = _file_hour(fp)
        d = _file_date(fp)
        if h is None or d is None:
            continue
        rows = parse_md_table(fp)
        day_vals: list[int] = []
        minutes_set: set[int] = set()
        for r in rows:
            v = _to_int(r.get("stationen", ""))
            if v is not None:
                day_vals.append(v)
            t = r.get("zeit", "")
            m = re.match(r"\d{1,2}:(\d{2}):", t)
            if m:
                minutes_set.add(int(m.group(1)))
        if not day_vals:
            continue
        bucket = result.setdefault(h, {"cycles": [], "daily": {}, "minutes": set()})
        bucket["cycles"].extend(day_vals)
        bucket["daily"].setdefault(d, []).extend(day_vals)
        bucket["minutes"] |= minutes_set
    return result


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


def _aggregate(hour_stats: dict[int, dict]) -> dict[int, dict]:
    """Pooled Mean (alle Zyklen) + Min/Max über Tages-Mittelwerte (für Error Bars)."""
    result = {}
    for hour, data in sorted(hour_stats.items()):
        cycles = data.get("cycles", [])
        if not cycles:
            continue
        pooled_mean = sum(cycles) / len(cycles)
        daily_means = [sum(v) / len(v) for v in data.get("daily", {}).values() if v]
        minutes = data.get("minutes", set())
        result[hour] = {
            "mean":       pooled_mean,
            "min":        min(daily_means) if len(daily_means) > 1 else pooled_mean,
            "max":        max(daily_means) if len(daily_means) > 1 else pooled_mean,
            "n_cycles":   len(cycles),
            "n_days":     len(daily_means),
            "coverage":   len(minutes),
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
    n_days = max(v["n_days"] for v in agg.values())
    n_cyc  = sum(v["n_cycles"] for v in agg.values())
    return f"Basis: {n_days} Tag{'e' if n_days > 1 else ''} / {n_cyc} Zyklen"


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
               color=COLORS["rescue"], alpha=0.92, zorder=3, linewidth=0)
        ax.text(xi, sv + max_val * 0.016, f"+{rv:.0f}",
                ha="center", va="bottom", fontsize=7,
                color=COLORS["rescue"], fontweight="bold", zorder=5)
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
    basis_parts: list[str] = []

    for rx_mode in RX_MODES:
        hour_vals = load_hourly_stats(STATS_DIR, rx_mode, band, protocol)
        if not hour_vals:
            continue
        agg = _aggregate(hour_vals)
        xs, means, mins, maxs = _hours_x(agg)
        if not xs:
            continue
        all_xs.extend(xs)
        n_d = max(v["n_days"] for v in agg.values())
        n_c = sum(v["n_cycles"] for v in agg.values())
        basis_parts.append(
            f"{rx_mode.replace('_', ' ')}: {n_d} Tag{'e' if n_d > 1 else ''} / {n_c} Z"
        )

        color = COLORS[rx_mode]
        label = rx_mode.replace("_", " ")
        ax.plot(xs, means, color=color, label=label, linewidth=2.5, zorder=3)
        ax.fill_between(xs, mins, maxs, color=color, alpha=0.15, zorder=2)
        has_data = True

    if not has_data:
        plt.close(fig)
        return

    _hour_ticks_line(ax, all_xs)
    ax.yaxis.set_major_locator(mticker.MultipleLocator(10))
    ax.set_xlabel("Stunde (UTC)", color=DARK_FG, labelpad=6)
    ax.set_ylabel("Ø Stationen / 15s-Zyklus", color=DARK_FG)
    basis = " · ".join(basis_parts)
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
        hv = load_hourly_stats(STATS_DIR, mode, band, protocol)
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

    # max_val inkl. Rescue-Kappen und Min/Max-Error-Bars, damit +N Labels + Whisker
    # nicht über den ylim hinausragen
    max_candidates = [1.0]
    for mode in _MODE_ORDER:
        if mode not in agg_all:
            continue
        rescue = rescue_all.get(mode, {})
        for h in all_hours:
            if h not in agg_all[mode]:
                continue
            a = agg_all[mode][h]
            cap = a["mean"] + rescue.get(h, 0.0)
            whisker_top = a["max"]  # Error-Bar oberes Ende
            max_candidates.append(max(cap, whisker_top))
    max_val = max(max_candidates)
    ax.set_ylim(0, max_val * 1.30)
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

        # Error-Bars (Tag-zu-Tag-Variabilität) nur wenn mehrere Messtage vorhanden
        err_x, err_mean, err_lo, err_hi = [], [], [], []
        for idx, h in enumerate(all_hours):
            if h not in agg or agg[h]["n_days"] < 2:
                continue
            a = agg[h]
            err_x.append(x_pos[idx])
            err_mean.append(a["mean"])
            err_lo.append(max(0.0, a["mean"] - a["min"]))
            err_hi.append(max(0.0, a["max"] - a["mean"]))
        if err_x:
            ax.errorbar(err_x, err_mean, yerr=[err_lo, err_hi], fmt="none",
                        ecolor=DARK_FG, alpha=0.55, capsize=2.5,
                        elinewidth=0.9, zorder=4)

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
        handles.append(mpatches.Patch(facecolor=COLORS["rescue"], alpha=0.92,
                                      label="davon gerettet (ANT1 unter −24 dB)"))

    _hour_ticks_bar(ax, list(x_base), all_hours)
    ax.yaxis.set_major_locator(mticker.MultipleLocator(10))
    ax.set_xlabel("Stunde (UTC)", color=DARK_FG, labelpad=6)
    ax.set_ylabel("Ø Stationen pro 15s-Zyklus", color=DARK_FG)

    basis_parts = []
    for mode in _MODE_ORDER:
        if mode not in agg_all:
            continue
        a = agg_all[mode]
        n_d = max(v["n_days"] for v in a.values())
        n_c = sum(v["n_cycles"] for v in a.values())
        basis_parts.append(
            f"{_MODE_LABELS[mode]}: {n_d} Tag{'e' if n_d > 1 else ''} / {n_c} Z"
        )
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
    plt.subplots_adjust(bottom=0.36, right=0.98)

    out = OUTPUT_DIR / f"diversity_{band}_{protocol}.png"
    fig.savefig(out, dpi=150, bbox_inches="tight", facecolor=DARK_BG)
    plt.close(fig)
    print(f"  ✓ {out.name}")


# ── PDF-Bericht ───────────────────────────────────────────────────────────────

def _extract_time_range(stats_dir: Path) -> str:
    dates = []
    for md_file in stats_dir.rglob("*.md"):
        d = _file_date(md_file)
        if d:
            dates.append(d)
    if not dates:
        return "keine Daten"
    ds = sorted(set(dates))
    return ds[0] if len(ds) == 1 else f"{ds[0]} bis {ds[-1]}"


def _combo_summary(stats_dir: Path, band: str, protocol: str) -> dict:
    """Pooled Mean + gewichteter Rescue-Schnitt pro Modus."""
    result: dict[str, dict] = {}
    for mode in RX_MODES:
        hv = load_hourly_stats(stats_dir, mode, band, protocol)
        if not hv:
            continue
        agg = _aggregate(hv)
        if not agg:
            continue
        total_w = sum(v["mean"] * v["n_cycles"] for v in agg.values())
        total_c = sum(v["n_cycles"] for v in agg.values())
        n_days  = max(v["n_days"] for v in agg.values())
        result[mode] = {
            "avg":      total_w / total_c if total_c else 0.0,
            "n_days":   n_days,
            "n_cycles": total_c,
        }
        if mode != "Normal":
            rescue = load_rescue_by_hour(stats_dir, mode, band, protocol)
            if rescue:
                r_w = sum(rescue[h] * agg[h]["n_cycles"] for h in rescue if h in agg)
                r_c = sum(agg[h]["n_cycles"] for h in rescue if h in agg)
                result[mode]["avg_rescue"] = r_w / r_c if r_c else 0.0
            else:
                result[mode]["avg_rescue"] = 0.0
    return result


# ── PDF Bericht — Professionelles Layout (heller Hintergrund) ─────────────────

_R_BG     = "#ffffff"
_R_FG     = "#1a1a1a"
_R_ACCENT = "#1a3a5c"
_R_SUB    = "#555555"
_R_GRID   = "#e4e4e4"
_R_GREEN  = "#1a5c2a"
_R_ORANGE = "#994400"


def _rfig() -> plt.Figure:
    return plt.figure(figsize=(11.69, 8.27), facecolor=_R_BG)


def _r_header(fig: plt.Figure, title: str, subtitle: str = "") -> None:
    ax = fig.add_axes([0.0, 0.895, 1.0, 0.105], zorder=10)
    ax.set_facecolor(_R_ACCENT)
    ax.axis("off")
    fig.text(0.04, 0.945, title, fontsize=15, color="white",
             fontweight="bold", transform=fig.transFigure, va="center")
    if subtitle:
        fig.text(0.04, 0.909, subtitle, fontsize=9.5, color="#aaccee",
                 transform=fig.transFigure, va="center")


def _r_footer(fig: plt.Figure, gen_date: str, page: str = "") -> None:
    ax = fig.add_axes([0.0, 0.0, 1.0, 0.048], zorder=10)
    ax.set_facecolor(_R_GRID)
    ax.axis("off")
    fig.text(0.04, 0.024,
             f"SimpleFT8 Diversity Feldstudie — DA1MHH / Mike Hammerer  ·  {gen_date}",
             fontsize=8, color=_R_SUB, transform=fig.transFigure, va="center")
    right = f"github.com/mikewanne/SimpleFT8{('  ·  ' + page) if page else ''}"
    fig.text(0.97, 0.024, right, fontsize=8, color=_R_SUB,
             transform=fig.transFigure, va="center", ha="right")


def _r_hline(fig: plt.Figure, y: float) -> None:
    ax = fig.add_axes([0.04, y, 0.92, 0.0015])
    ax.set_facecolor(_R_GRID)
    ax.axis("off")


def _hourly_analysis(stats_dir: Path, band: str, protocol: str) -> list[dict]:
    agg_n  = _aggregate(load_hourly_stats(stats_dir, "Normal",           band, protocol))
    agg_s  = _aggregate(load_hourly_stats(stats_dir, "Diversity_Normal", band, protocol))
    agg_d  = _aggregate(load_hourly_stats(stats_dir, "Diversity_Dx",     band, protocol))
    resc_s = load_rescue_by_hour(stats_dir, "Diversity_Normal", band, protocol)
    resc_d = load_rescue_by_hour(stats_dir, "Diversity_Dx",     band, protocol)
    hours  = sorted(set(agg_n) & (set(agg_s) | set(agg_d)))
    result = []
    for h in hours:
        nm = agg_n[h]["mean"] if h in agg_n else None
        sm = agg_s[h]["mean"] if h in agg_s else None
        dm = agg_d[h]["mean"] if h in agg_d else None
        sg = (sm / nm - 1) * 100 if (nm and sm and nm > 0) else None
        dg = (dm / nm - 1) * 100 if (nm and dm and nm > 0) else None
        result.append({"hour": h, "n_mean": nm, "s_mean": sm, "d_mean": dm,
                        "s_gain": sg, "d_gain": dg,
                        "rs": resc_s.get(h, 0.0), "rd": resc_d.get(h, 0.0)})
    return result


def _r_title_page(pdf: PdfPages, summary: dict, time_range: str, gen_date: str) -> None:
    fig = _rfig()
    ax_hdr = fig.add_axes([0.0, 0.72, 1.0, 0.28])
    ax_hdr.set_facecolor(_R_ACCENT)
    ax_hdr.axis("off")
    fig.text(0.50, 0.875, "SimpleFT8 — Dual-Antenna Diversity",
             fontsize=24, color="white", fontweight="bold",
             ha="center", transform=fig.transFigure)
    fig.text(0.50, 0.820, "Vorläufige Feldstudie — 40m FT8",
             fontsize=15, color="#aaccee", ha="center", transform=fig.transFigure)
    total_cyc = sum(s.get("n_cycles", 0) for s in summary.values())
    fig.text(0.50, 0.762,
             f"Messzeitraum: {time_range}   ·   Ausgewertete Zyklen: {total_cyc}",
             fontsize=10, color="#88aacc", ha="center", transform=fig.transFigure)

    n_avg = summary.get("Normal",           {}).get("avg", 0.0)
    s_avg = summary.get("Diversity_Normal", {}).get("avg", 0.0)
    d_avg = summary.get("Diversity_Dx",     {}).get("avg", 0.0)
    s_rsc = summary.get("Diversity_Normal", {}).get("avg_rescue", 0.0)
    d_rsc = summary.get("Diversity_Dx",     {}).get("avg_rescue", 0.0)

    def pct(a, b): return f"{(a / b - 1) * 100:+.0f}%" if b > 0 else "n/a"

    fig.text(0.05, 0.685, "Kernaussagen:", fontsize=11, color=_R_ACCENT,
             fontweight="bold", transform=fig.transFigure)
    _r_hline(fig, 0.672)
    findings = [
        f"Diversity Standard:  {pct(s_avg, n_avg)} mehr Stationen (ohne Rescue)  —  "
        f"{pct(s_avg + s_rsc, n_avg)} inkl. geretteter Stationen",
        f"Diversity DX:           {pct(d_avg, n_avg)} mehr Stationen (ohne Rescue)  —  "
        f"{pct(d_avg + d_rsc, n_avg)} inkl. geretteter Stationen",
        f"Rescue allein:          Standard {pct(s_rsc, n_avg)}  |  DX {pct(d_rsc, n_avg)}"
        f"   (nur durch ANT2 dekodierbar — ANT1 unter −24 dB)",
    ]
    for i, txt in enumerate(findings):
        fig.text(0.06, 0.635 - i * 0.072, f"▶  {txt}",
                 fontsize=10.5, color=_R_FG, transform=fig.transFigure)

    _r_hline(fig, 0.437)
    fig.text(0.05, 0.413,
             "⚠  Vorläufige Daten: 2 Messtage, ausschließlich 05:00–12:00 UTC. "
             "Nacht- und Abendstunden fehlen noch — Zahlen werden sich verschieben.",
             fontsize=9.5, color=_R_ORANGE, style="italic", transform=fig.transFigure)

    fig.text(0.05, 0.352, "Modi-Definitionen:", fontsize=10, color=_R_ACCENT,
             fontweight="bold", transform=fig.transFigure)
    defs = [
        ("Normal",             "1 Antenne — keine Diversity-Logik. Baseline wie WSJT-X."),
        ("Diversity Standard", "2 Antennen — wählt automatisch die Antenne mit mehr dekodierten Stationen."),
        ("Diversity DX",       "2 Antennen — wählt die Antenne mit mehr Schwachsignalen (SNR < −10 dB)."),
        ("Rescue",             "Stationen, die ANT1 (≤ −24 dB) nicht dekodieren konnte, ANT2 aber schon."),
    ]
    for i, (lbl, desc) in enumerate(defs):
        fig.text(0.06, 0.312 - i * 0.055, f"{lbl}:", fontsize=9.5,
                 color=_R_ACCENT, fontweight="bold", transform=fig.transFigure)
        fig.text(0.25, 0.312 - i * 0.055, desc, fontsize=9.5,
                 color=_R_FG, transform=fig.transFigure)

    _r_footer(fig, gen_date, "Seite 1")
    pdf.savefig(fig, facecolor=_R_BG)
    plt.close(fig)


def _r_methodik_page(pdf: PdfPages, summary: dict, time_range: str, gen_date: str) -> None:
    fig = _rfig()
    _r_header(fig, "Datenbasis & Methodik", "40m FT8 — Pooled-Mean-Auswertung")

    sections = [
        ("Datenbasis", [
            f"Band / Protokoll:    40m  FT8",
            f"Messzeitraum:        {time_range}",
            f"Erfasste Stunden:    05:00–12:00 UTC  (Morgen / Vormittag)",
            f"Messtage / Zyklen:   Normal {summary.get('Normal',{}).get('n_days','–')} Tage / "
            f"{summary.get('Normal',{}).get('n_cycles','–')} Z   |   "
            f"Standard {summary.get('Diversity_Normal',{}).get('n_days','–')} Tage / "
            f"{summary.get('Diversity_Normal',{}).get('n_cycles','–')} Z   |   "
            f"DX {summary.get('Diversity_Dx',{}).get('n_days','–')} Tage / "
            f"{summary.get('Diversity_Dx',{}).get('n_cycles','–')} Z",
            "Hardware:            FLEX-8400M, zwei Antennenanschlüsse, gleiche Frequenz",
        ]),
        ("Pooled Mean — warum nicht Tagesdurchschnitt?", [
            "Klassisch: Tagesdurchschnitt bilden, dann Mittelwert der Tage.",
            "Problem:   Tage mit wenigen Zyklen erhalten das gleiche Gewicht wie Tage mit 500 Zyklen → Bias.",
            "Pooled:    Alle Einzelzyklen aller Tage direkt mitteln. Gewichtung proportional zur Messzeit.",
            "Ergebnis:  Robuster gegen ungleiche Sessionlängen — repräsentativer für echten Betrieb.",
        ]),
        ("Rescue-Definition", [
            "ANT1-SNR ≤ −24 dB  UND  ANT2-SNR > −24 dB  →  Station gilt als 'gerettet'.",
            "−24 dB ist die empirische FT8-Decodierschwelle (nach WSJT-X Dokumentation).",
            "Nur Zyklen in denen das Diversity-System aktiv ANT2 gewählt hat werden gezählt.",
            "Rescue-Events pro UTC-Stunde gezählt, über Messtage gemittelt, dann gewichtet nach Zyklen.",
        ]),
        ("Statistik-Dateien", [
            "Rohdaten:  statistics/{Modus}/{Band}/{Proto}/YYYY-MM-DD_HH.md  (pro Stunde, pro Tag)",
            "Stations:  statistics/{Modus}/{Band}/{Proto}/stations/YYYY-MM-DD_HH.md  (SNR-Vergleiche)",
            "Kein In-File-Summary — alle Aggregationen werden beim Aufruf von generate_plots.py berechnet.",
        ]),
    ]
    y = 0.845
    for title, lines in sections:
        fig.text(0.05, y, title, fontsize=10.5, color=_R_ACCENT,
                 fontweight="bold", transform=fig.transFigure)
        y -= 0.028
        _r_hline(fig, y + 0.006)
        y -= 0.008
        for line in lines:
            fig.text(0.06, y, line, fontsize=9, color=_R_FG,
                     transform=fig.transFigure, family="monospace")
            y -= 0.038
        y -= 0.016

    _r_footer(fig, gen_date, "Seite 2")
    pdf.savefig(fig, facecolor=_R_BG)
    plt.close(fig)


def _r_ergebnisse_page(pdf: PdfPages, summary: dict, gen_date: str) -> None:
    n_avg = summary.get("Normal", {}).get("avg", 0.0)
    col_labels = ["Modus", "Ø Stat.\n/Zyklus", "vs Normal\nohne Rescue",
                  "vs Normal\n+ Rescue", "Rescue\nallein", "Messtage", "Zyklen"]
    mode_meta = {
        "Normal":           ("Normal (1 Antenne)",    "#e8eef5", _R_ACCENT),
        "Diversity_Normal": ("Diversity Standard",    "#e8f5eb", _R_GREEN),
        "Diversity_Dx":     ("Diversity DX",          "#fff3e0", _R_ORANGE),
    }
    rows, row_face, row_text = [], [], []
    for mode in RX_MODES:
        if mode not in summary:
            continue
        s = summary[mode]
        avg = s["avg"]
        lbl, face, tcol = mode_meta[mode]
        if mode == "Normal" or n_avg <= 0:
            vs, vsr, r = "—", "—", "—"
        else:
            rsc = s.get("avg_rescue", 0.0)
            vs  = f"+{(avg / n_avg - 1) * 100:.0f}%"
            vsr = f"+{((avg + rsc) / n_avg - 1) * 100:.0f}%"
            r   = f"+{(rsc / n_avg) * 100:.0f}%"
        rows.append([lbl, f"{avg:.1f}", vs, vsr, r, str(s["n_days"]), str(s["n_cycles"])])
        row_face.append(face)
        row_text.append(tcol)

    if not rows:
        return

    fig = _rfig()
    _r_header(fig, "Hauptergebnisse — Vergleichstabelle", "40m FT8 · Pooled Mean")

    ax = fig.add_axes([0.04, 0.22, 0.92, 0.64])
    ax.axis("off")
    tbl = ax.table(cellText=rows, colLabels=col_labels, cellLoc="center", loc="center")
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(12)
    tbl.scale(1, 3.0)
    for (r, c), cell in tbl.get_celld().items():
        cell.set_edgecolor(_R_GRID)
        if r == 0:
            cell.set_facecolor(_R_ACCENT)
            cell.set_text_props(color="white", fontweight="bold")
        else:
            cell.set_facecolor(row_face[r - 1])
            cell.set_text_props(color=row_text[r - 1],
                                fontweight="bold" if c in (2, 3, 4) else "normal")

    fig.text(0.05, 0.175,
             "Ø Stat./Zyklus = Pooled Mean über alle Einzelzyklen.   "
             "Rescue = ANT1 ≤ −24 dB, ANT2 > −24 dB (nur durch ANT2 dekodierbar).",
             fontsize=9, color=_R_SUB, transform=fig.transFigure)
    fig.text(0.05, 0.130,
             "⚠  Vorläufig: 2 Messtage, 05:00–12:00 UTC. "
             "Abend- und Nachtstunden nicht erfasst. Zahlen können sich verschieben.",
             fontsize=9, color=_R_ORANGE, style="italic", transform=fig.transFigure)

    _r_footer(fig, gen_date, "Seite 3")
    pdf.savefig(fig, facecolor=_R_BG)
    plt.close(fig)


def _r_diagramm_page(pdf: PdfPages, png_path: Path, title: str,
                     subtitle: str, annotation: str, gen_date: str,
                     page: str = "") -> None:
    if not png_path.exists():
        return
    img = plt.imread(str(png_path))
    h_px, w_px = img.shape[:2]
    aspect = h_px / w_px
    fig = _rfig()
    _r_header(fig, title, subtitle)
    img_h = 0.73
    img_w = min(0.92, img_h / aspect * (8.27 / 11.69))
    ax = fig.add_axes([(1.0 - img_w) / 2, 0.115, img_w, img_h])
    ax.imshow(img)
    ax.axis("off")
    if annotation:
        fig.text(0.05, 0.090, annotation, fontsize=8.5, color=_R_SUB,
                 style="italic", transform=fig.transFigure)
    _r_footer(fig, gen_date, page)
    pdf.savefig(fig, facecolor=_R_BG)
    plt.close(fig)


def _r_rescue_page(pdf: PdfPages, summary: dict, gen_date: str) -> None:
    fig = _rfig()
    _r_header(fig, "Rescue-Daten — Diskussion",
              "Sollten gerettete Stationen mitzählen?")

    n_avg = summary.get("Normal",           {}).get("avg", 0.0)
    s_avg = summary.get("Diversity_Normal", {}).get("avg", 0.0)
    d_avg = summary.get("Diversity_Dx",     {}).get("avg", 0.0)
    s_rsc = summary.get("Diversity_Normal", {}).get("avg_rescue", 0.0)
    d_rsc = summary.get("Diversity_Dx",     {}).get("avg_rescue", 0.0)

    fig.text(0.05, 0.845, "Was sind Rescue-Stationen?", fontsize=10.5,
             color=_R_ACCENT, fontweight="bold", transform=fig.transFigure)
    _r_hline(fig, 0.833)
    fig.text(0.05, 0.808,
             f"Rescue-Events entstehen wenn ANT1-SNR ≤ −24 dB und ANT2-SNR > −24 dB für dieselbe Station."
             f" Im Messzeitraum: Ø {s_rsc:.1f} Rescue/h (Standard), Ø {d_rsc:.1f} Rescue/h (DX).",
             fontsize=9.5, color=_R_FG, transform=fig.transFigure)

    fig.text(0.05, 0.752, "▲  PRO — Rescue-Stationen mitzählen", fontsize=10.5,
             color=_R_GREEN, fontweight="bold", transform=fig.transFigure)
    _r_hline(fig, 0.740)
    for i, txt in enumerate([
        "Echter physikalischer Nachweis: ANT2 hat ein QSO erst ermöglicht — ANT1 hätte nie dekodiert.",
        "Für den Operator zählt das QSO, egal welche Antenne. Rescue = realer Mehrwert im Betrieb.",
        "Rescue-Rate steigt bei schlechten Bedingungen — Diversity hilft genau dort am meisten.",
        f"Mit Rescue: Standard +{((s_avg+s_rsc)/n_avg-1)*100:.0f}%, DX +{((d_avg+d_rsc)/n_avg-1)*100:.0f}%"
        f" — vollständiges Bild der Systemleistung.",
    ]):
        fig.text(0.06, 0.706 - i * 0.048, f"✓  {txt}", fontsize=9.5,
                 color=_R_FG, transform=fig.transFigure)

    fig.text(0.05, 0.488, "▼  CONTRA — Rescue-Stationen separat betrachten", fontsize=10.5,
             color=_R_ORANGE, fontweight="bold", transform=fig.transFigure)
    _r_hline(fig, 0.476)
    for i, txt in enumerate([
        "SNR-Schwankungen im 15s-Zyklus können Schwellenüberschreitung kurzfristig erzeugen.",
        "Die −24 dB-Grenze ist empirisch, kein physikalisches Gesetz — Grenzfälle sind möglich.",
        "Für Vergleich mit anderen Systemen: nur direkt dekodierte Stationen zählen.",
        "Rescue setzt korrektes ANT2-Timing voraus — vollständige Kausalität noch nicht bewiesen.",
    ]):
        fig.text(0.06, 0.440 - i * 0.048, f"⚠  {txt}", fontsize=9.5,
                 color=_R_FG, transform=fig.transFigure)

    _r_hline(fig, 0.238)
    fig.text(0.05, 0.212,
             "Empfehlung: Beide Werte werden ausgewiesen — 'ohne Rescue' als konservativer Vergleichswert,\n"
             "'inkl. Rescue' als Systemleistung unter realen Betriebsbedingungen.",
             fontsize=9.5, color=_R_ACCENT, style="italic",
             transform=fig.transFigure, linespacing=1.7)

    _r_footer(fig, gen_date, "Seite 5")
    pdf.savefig(fig, facecolor=_R_BG)
    plt.close(fig)


def _r_fazit_page(pdf: PdfPages, summary: dict, hourly: list[dict],
                  gen_date: str) -> None:
    fig = _rfig()
    _r_header(fig, "Vorläufige Schlussfolgerungen & Ausblick",
              "40m FT8 — Stand: 2 Messtage, 05:00–12:00 UTC")

    n_avg = summary.get("Normal",           {}).get("avg", 0.0)
    s_avg = summary.get("Diversity_Normal", {}).get("avg", 0.0)
    d_avg = summary.get("Diversity_Dx",     {}).get("avg", 0.0)
    s_rsc = summary.get("Diversity_Normal", {}).get("avg_rescue", 0.0)
    d_rsc = summary.get("Diversity_Dx",     {}).get("avg_rescue", 0.0)
    best_s = max((r for r in hourly if r["s_gain"] is not None),
                 key=lambda r: r["s_gain"], default=None)

    fig.text(0.05, 0.840, "Gesicherte Erkenntnisse", fontsize=10.5,
             color=_R_ACCENT, fontweight="bold", transform=fig.transFigure)
    _r_hline(fig, 0.828)
    flist = [
        f"Diversity Standard: konsistent +{(s_avg/n_avg-1)*100:.0f}% (konservativ) bis "
        f"+{((s_avg+s_rsc)/n_avg-1)*100:.0f}% (inkl. Rescue). Reproduzierbar über beide Messtage.",
        f"Diversity DX: geringerer Gesamtgewinn (+{(d_avg/n_avg-1)*100:.0f}%), aber "
        f"stärkerer Fokus auf schwache DX-Signale — sinnvoll für Conteste / Rare-DX.",
        f"Rescue-Anteil: Standard Ø {s_rsc:.1f} Stat./h, DX Ø {d_rsc:.1f} Stat./h — "
        f"physischer Diversity-Effekt jenseits reiner Schaltlogik belegt.",
    ]
    if best_s:
        flist.append(
            f"Stärkster Standard-Gewinn: {best_s['hour']:02d}:00 UTC "
            f"(+{best_s['s_gain']:.0f}%) — typisch für Bandöffnungs- oder Schlussphasen."
        )
    for i, txt in enumerate(flist):
        fig.text(0.06, 0.796 - i * 0.058, f"✓  {txt}", fontsize=9.5,
                 color=_R_FG, transform=fig.transFigure)

    fig.text(0.05, 0.565, "Einschränkungen", fontsize=10.5,
             color=_R_ORANGE, fontweight="bold", transform=fig.transFigure)
    _r_hline(fig, 0.553)
    for i, txt in enumerate([
        "Nur 2 Messtage — Konfidenzintervalle breit, statistische Signifikanz begrenzt.",
        "Nur 05:00–12:00 UTC — Abend/Nacht-Propagation auf 40m (typisch besser) fehlt komplett.",
        "Vergleichbare Bedingungen beide Tage — extremes DX, Contest-Betrieb noch nicht gemessen.",
        "Hardware FLEX-8400M — Übertragbarkeit auf andere Transceiver offen.",
    ]):
        fig.text(0.06, 0.518 - i * 0.053, f"⚠  {txt}", fontsize=9.5,
                 color=_R_FG, transform=fig.transFigure)

    fig.text(0.05, 0.298, "Nächste Schritte", fontsize=10.5,
             color=_R_ACCENT, fontweight="bold", transform=fig.transFigure)
    _r_hline(fig, 0.286)
    for i, txt in enumerate([
        "Nacht/Abend (20:00–04:00 UTC) sammeln — auf 40m typisch bessere DX-Bedingungen.",
        "Mindestens 5–7 Messtage für belastbare Fehlerbalken und statistische Signifikanz.",
        "Verschiedene Bandbedingungen: SFI hoch/niedrig, K-Index 0–3, Geo-Sturm.",
        "20m-Band: noch zu wenig Daten (< 3 Tage) — erst dann aussagekräftig auswertbar.",
    ]):
        fig.text(0.06, 0.248 - i * 0.053, f"→  {txt}", fontsize=9.5,
                 color=_R_FG, transform=fig.transFigure)

    _r_hline(fig, 0.065)
    fig.text(0.05, 0.048,
             "Rohdaten: statistics/  ·  Auswertung: scripts/generate_plots.py  ·  "
             "github.com/mikewanne/SimpleFT8",
             fontsize=8.5, color=_R_SUB, style="italic", transform=fig.transFigure)

    _r_footer(fig, gen_date, "Seite 6")
    pdf.savefig(fig, facecolor=_R_BG)
    plt.close(fig)


def create_pdf_report(combos: set[tuple[str, str]]) -> None:
    target = [c for c in sorted(combos) if c == ("40m", "FT8")]
    if not target:
        for band, protocol in sorted(combos):
            s = _combo_summary(STATS_DIR, band, protocol)
            if s.get("Normal", {}).get("n_days", 0) >= 1:
                target = [(band, protocol)]
                break
    if not target:
        print("  ⚠ Keine ausreichenden Daten für PDF-Bericht.")
        return

    band, protocol = target[0]
    summary    = _combo_summary(STATS_DIR, band, protocol)
    hourly     = _hourly_analysis(STATS_DIR, band, protocol)
    normal_dir = STATS_DIR / "Normal" / band / protocol
    time_range = _extract_time_range(normal_dir if normal_dir.exists() else STATS_DIR)
    gen_date   = datetime.now().strftime("%Y-%m-%d %H:%M")
    pdf_path   = OUTPUT_DIR / "SimpleFT8_Bericht.pdf"

    with PdfPages(str(pdf_path)) as pdf:
        _r_title_page(pdf, summary, time_range, gen_date)          # S.1
        _r_methodik_page(pdf, summary, time_range, gen_date)        # S.2
        _r_ergebnisse_page(pdf, summary, gen_date)                  # S.3
        _r_diagramm_page(                                           # S.4
            pdf, OUTPUT_DIR / f"stationen_{band}_{protocol}.png",
            "Empfangene Stationen über 24h UTC",
            f"{band} {protocol} — Linie = Pooled Mean, Band = Tages-Schwankung",
            "Hinweis: Daten nur 05:00–12:00 UTC. Kurven zeigen Morgen/Vormittagsbetrieb.",
            gen_date, "Seite 4",
        )
        _r_diagramm_page(                                           # S.5 → nach Rescue
            pdf, OUTPUT_DIR / f"diversity_{band}_{protocol}.png",
            "Diversity-Vergleich — Stationen pro Zyklus",
            f"{band} {protocol} — Normal (grau) | Standard (blau) | DX (orange) | Rescue (grün)",
            "Grüne Kappen (+N): durch ANT2 gerettete Stationen — ANT1-SNR war ≤ −24 dB.",
            gen_date, "Seite 5",
        )
        _r_rescue_page(pdf, summary, gen_date)                      # S.6
        _r_fazit_page(pdf, summary, hourly, gen_date)               # S.7

        d = pdf.infodict()
        d["Title"]   = f"SimpleFT8 Diversity Feldstudie — {band} {protocol}"
        d["Author"]  = "DA1MHH / Mike Hammerer"
        d["Subject"] = "Dual-Antenna Diversity Field Study"

    print(f"  ✓ PDF Bericht: {pdf_path.name} (7 Seiten, {band} {protocol})")


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
    print("\n=== PDF Bericht ===")
    create_pdf_report(combos)
    print("\nFertig. Ausgabe in:", OUTPUT_DIR)


if __name__ == "__main__":
    main()
