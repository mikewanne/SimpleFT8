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


def _pdf_title_page(pdf: PdfPages, time_range: str, gen_date: str) -> None:
    fig = plt.figure(figsize=(11.69, 8.27), facecolor=DARK_BG)
    kw = dict(ha="center", transform=fig.transFigure)
    fig.text(0.5, 0.82, "SimpleFT8 — Diversity Auswertungsbericht",
             fontsize=22, color=DARK_FG, fontweight="bold", **kw)
    fig.text(0.5, 0.72,
             f"Generiert: {gen_date}   ·   Messzeitraum: {time_range}",
             fontsize=13, color="#aaaaaa", **kw)
    fig.text(0.5, 0.55,
             "Normal          = 1 Antenne, keine Diversity-Logik — Baseline wie WSJT-X\n"
             "Div. Standard  = 2 Antennen, wählt die Antenne mit mehr Stationen\n"
             "Div. DX           = 2 Antennen, wählt die Antenne mit mehr Schwachsignalen (SNR < −10 dB)\n"
             "Rescue            = Stationen die ANT1 nicht dekodierte (≤ −24 dB), aber ANT2 schon",
             fontsize=11, color=DARK_FG, linespacing=2.3, **kw)
    fig.text(0.5, 0.14,
             "Daten werden laufend erfasst — Bericht aktualisiert sich automatisch mit jeder neuen Session.\n"
             "github.com/mikewanne/SimpleFT8  ·  DA1MHH / Mike Hammerer",
             fontsize=9, color="#888888", style="italic", linespacing=1.8, **kw)
    pdf.savefig(fig, facecolor=DARK_BG)
    plt.close(fig)


def _pdf_summary_page(pdf: PdfPages, band: str, protocol: str, summary: dict) -> None:
    normal_avg = summary.get("Normal", {}).get("avg", 0.0)
    mode_labels = {
        "Normal":           "Normal (1 Antenne)",
        "Diversity_Normal": "Diversity Standard",
        "Diversity_Dx":     "Diversity DX",
    }
    row_bg = {
        "Normal":           "#242424",
        "Diversity_Normal": "#162040",
        "Diversity_Dx":     "#251408",
    }
    col_labels = ["Modus", "Ø Stat./Zyklus", "vs Normal", "vs Normal\n+ Rescue", "Rescue\nallein", "Tage", "Zyklen"]
    rows: list[list[str]] = []
    row_colors: list[str] = []
    for mode in RX_MODES:
        if mode not in summary:
            continue
        s = summary[mode]
        avg = s["avg"]
        if mode == "Normal" or normal_avg <= 0:
            vs_str, vsr_str, r_str = "—", "—", "—"
        else:
            rescue = s.get("avg_rescue", 0.0)
            vs_str  = f"+{(avg / normal_avg - 1) * 100:.0f}%"
            vsr_str = f"+{((avg + rescue) / normal_avg - 1) * 100:.0f}%"
            r_str   = f"+{(rescue / normal_avg) * 100:.0f}%"
        rows.append([mode_labels[mode], f"{avg:.1f}", vs_str, vsr_str,
                     r_str, str(s["n_days"]), str(s["n_cycles"])])
        row_colors.append(row_bg[mode])

    if not rows:
        return

    fig = plt.figure(figsize=(11.69, 8.27), facecolor=DARK_BG)
    fig.text(0.5, 0.92, f"Zusammenfassung — {band} {protocol}",
             ha="center", fontsize=18, color=DARK_FG, fontweight="bold",
             transform=fig.transFigure)

    ax = fig.add_axes([0.04, 0.28, 0.92, 0.58])
    ax.axis("off")
    tbl = ax.table(cellText=rows, colLabels=col_labels, cellLoc="center", loc="center")
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(11)
    tbl.scale(1, 2.6)
    for (r, c), cell in tbl.get_celld().items():
        cell.set_edgecolor(DARK_GRID)
        if r == 0:
            cell.set_facecolor("#1a3a5c")
            cell.set_text_props(color=DARK_FG, fontweight="bold")
        else:
            cell.set_facecolor(row_colors[r - 1])
            cell.set_text_props(color=DARK_FG)

    fig.text(0.5, 0.13,
             "Ø Stat./Zyklus = Pooled Mean (gewichteter Mittelwert über alle Zyklen und Stunden)\n"
             "Rescue = Stationen, die ANT1 nicht dekodieren konnte (≤ −24 dB), ANT2 jedoch schon\n"
             "Mehr Messtage → stabilere Werte und engere Konfidenzintervalle",
             ha="center", fontsize=9, color="#aaaaaa", linespacing=1.8,
             transform=fig.transFigure)
    pdf.savefig(fig, facecolor=DARK_BG)
    plt.close(fig)


def _pdf_embed_png(pdf: PdfPages, png_path: Path) -> None:
    if not png_path.exists():
        return
    img = plt.imread(str(png_path))
    fig = plt.figure(figsize=(11.69, 8.27), facecolor=DARK_BG)
    ax = fig.add_axes([0.01, 0.01, 0.98, 0.98])
    ax.imshow(img)
    ax.axis("off")
    pdf.savefig(fig, facecolor=DARK_BG)
    plt.close(fig)


def create_pdf_report(combos: set[tuple[str, str]]) -> None:
    pdf_path   = OUTPUT_DIR / "SimpleFT8_Bericht.pdf"
    time_range = _extract_time_range(STATS_DIR)
    gen_date   = datetime.now().strftime("%Y-%m-%d %H:%M")

    with PdfPages(str(pdf_path)) as pdf:
        _pdf_title_page(pdf, time_range, gen_date)
        for band, protocol in sorted(combos):
            summary = _combo_summary(STATS_DIR, band, protocol)
            if not summary:
                continue
            _pdf_summary_page(pdf, band, protocol, summary)
            for diag_type in ("stationen", "diversity"):
                _pdf_embed_png(pdf, OUTPUT_DIR / f"{diag_type}_{band}_{protocol}.png")
        d = pdf.infodict()
        d["Title"]   = "SimpleFT8 Diversity Auswertungsbericht"
        d["Author"]  = "DA1MHH / Mike Hammerer"
        d["Subject"] = "Diversity Antenna Analysis"

    print(f"  ✓ PDF Bericht: {pdf_path.name}")


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
