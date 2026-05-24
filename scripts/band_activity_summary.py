"""Band-Aktivitäts-Übersicht (P117, v0.98.02) — Standalone-Script.

Generiert Liniendiagramm aller Bänder × 24 UTC-Stunden für Mike's
Quick-Reference zur Band-Aktivität:
    „Vor dem Park-Trip wissen, wann welches Band typisch aktiv ist."

Aggregation pro `(Band, Stunde)`:
    1. Für jeden RX-Modus (Normal, Diversity_Normal, Diversity_Dx)
       den Pooled-Mean der Stationen pro Stunde berechnen.
    2. Modi mit < MIN_CYCLES_PER_BUCKET Zyklen für diese Stunde
       ausschließen (zu wenig Daten).
    3. Arithmetisches Mittel der verbleibenden Modus-Mittelwerte
       (durch ANZAHL vorhandener Modi, nicht stur durch 3 — Mike-Spec).

Der DX-Modus zieht den Mittelwert leicht nach unten (filtert SNR<-10),
aber das stört nicht — wir suchen relative Band-Aktivität, kein absolutes
Stationen-Maß. Wenn ein Band um 14 UTC voll ist, sehen ALLE Modi viele
Stationen.

Output:
    auswertung/bandaktivitaet.png   (DE)
    auswertung/en/band_activity.png (EN)

Standalone CLI (kein App-Eingriff, kein Hook in generate_plots.py):
    ./venv/bin/python3 scripts/band_activity_summary.py
oder über Shell-Wrapper im Root:
    ./banduebersicht.sh
"""
from __future__ import annotations

import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import matplotlib
matplotlib.use("Agg")  # headless, kein Display-Server nötig
import matplotlib.pyplot as plt


# ── Konstanten ──────────────────────────────────────────────────────

BASE_DIR = Path(__file__).parent.parent
STATS_DIR = BASE_DIR / "statistics"
OUTPUT_DE = BASE_DIR / "auswertung" / "bandaktivitaet.png"
OUTPUT_EN = BASE_DIR / "auswertung" / "en" / "band_activity.png"

RX_MODES = ["Normal", "Diversity_Normal", "Diversity_Dx"]

# P118 (v0.98.03): Lokale Zeitzone für X-Achse. Stats werden in UTC
# gespeichert, Plot zeigt Berliner Zeit (Sommer UTC+2, Winter UTC+1).
# DST-Wechsel automatisch über zoneinfo (tzdata aus /usr/share/zoneinfo
# auf macOS nativ verfügbar).
LOCAL_TZ = ZoneInfo("Europe/Berlin")

# R1-Feinjustierung (Mike-Field-Datenbasis): 12 Zyklen = ~3 Min Empfang.
# Höher (30) würde junge Bänder wie 15m mit nur 5-9 Tagen Datenbasis
# komplett aus dem Plot werfen. Niedrig genug für Sichtbarkeit, hoch
# genug gegen Einzel-Zyklus-Ausreißer.
MIN_CYCLES_PER_BUCKET = 12

# Tief → hoch sortiert (Mike-üblich)
BAND_ORDER = [
    "160m", "80m", "60m", "40m", "30m",
    "20m", "17m", "15m", "12m", "10m", "6m",
]

# Distinct Farben fürs Dark-Theme. 15m/12m sind nah beieinander aber
# auf dunklem Hintergrund noch unterscheidbar.
BAND_COLORS = {
    "160m": "#9b59b6",  # violett
    "80m":  "#3498db",  # blau
    "60m":  "#1abc9c",  # türkis
    "40m":  "#2ecc71",  # grün
    "30m":  "#f1c40f",  # gelb
    "20m":  "#e67e22",  # orange
    "17m":  "#e74c3c",  # rot
    "15m":  "#ec407a",  # pink
    "12m":  "#ab47bc",  # purple
    "10m":  "#26c6da",  # cyan
    "6m":   "#7e57c2",  # dunkellila
}

DARK_BG = "#1e1e1e"
DARK_FG = "#d4d4d4"
DARK_GRID = "#333333"

# Stats-File-Format: `| HH:MM:SS | Stations | ... |` (3 oder 5 Spalten).
# Regex matched die ersten 2 Spalten (Zeit + Stations) — egal welcher Modus.
ROW_RE = re.compile(r"^\|\s*(\d{2}):\d{2}:\d{2}\s*\|\s*(\d+)\s*\|")
# Dateinamen-Format: YYYY-MM-DD_HH.md
FILE_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})_(\d{2})\.md$")


# ── Aggregation ─────────────────────────────────────────────────────


def _utc_file_to_local_hour(date_str: str, utc_hour: int) -> int:
    """P118 (v0.98.03): UTC-Stunde aus Dateiname → lokale Berliner Stunde.

    DST-aware via zoneinfo. Stats-Files heißen `YYYY-MM-DD_HH.md` wo
    HH die UTC-Stunde ist. Berliner Stunde hängt vom Datum ab (Sommer
    UTC+2, Winter UTC+1).

    Edge-Case DST-Wechsel-Tag (2/Jahr): Cycles innerhalb einer File
    landen alle in derselben lokalen Stunde (Stunden-Start als
    Repräsentation). Statistisch irrelevant (0.5% Daten).

    Args:
        date_str: "YYYY-MM-DD" aus Dateiname.
        utc_hour: UTC-Stunde 0-23 aus Dateiname.

    Returns:
        Lokale Berliner Stunde 0-23.
    """
    year, month, day = map(int, date_str.split("-"))
    dt_utc = datetime(year, month, day, utc_hour, tzinfo=timezone.utc)
    return dt_utc.astimezone(LOCAL_TZ).hour


def aggregate_band_hour(stats_dir: Path, band: str) -> dict[int, float | None]:
    """Pro Band: dict[hour] → mittlere Stationen über vorhandene Modi.

    Stunden in BERLINER ZEIT (P118 v0.98.03, DST-aware). UTC-File-
    Stunden werden via `_utc_file_to_local_hour` ins lokale Bucket
    aggregiert.

    Mittelung-Strategie:
        Pro Modus → Pooled-Mean Stationen über alle Tage je lokale Stunde.
        Pro lokale Stunde → arithmetisches Mittel der Modi-Mittelwerte
        (nur Modi mit >= MIN_CYCLES_PER_BUCKET Zyklen für diese Stunde).
        Wenn 0 Modi qualifizieren → None (Lücke im Plot).

    Args:
        stats_dir: Pfad zu `<repo>/statistics`.
        band: Band-Name wie "20m", "40m", etc.

    Returns:
        dict[local_hour_int] → float | None
    """
    # mode -> local_hour -> (sum_stations, n_cycles)
    per_mode_hour: dict[str, dict[int, tuple[int, int]]] = {}
    for mode in RX_MODES:
        mode_dir = stats_dir / mode / band / "FT8"
        if not mode_dir.exists():
            continue
        per_mode_hour[mode] = {}
        for f in mode_dir.glob("*.md"):
            fm = FILE_RE.match(f.name)
            if not fm:
                continue
            date_str = fm.group(1)
            utc_hour = int(fm.group(2))
            try:
                local_hour = _utc_file_to_local_hour(date_str, utc_hour)
            except (ValueError, OverflowError):
                continue  # defekter Dateiname, überspringen
            try:
                content = f.read_text(encoding="utf-8")
            except OSError:
                continue
            for line in content.splitlines():
                rm = ROW_RE.match(line)
                if rm:
                    sum_st, n_cyc = per_mode_hour[mode].get(local_hour, (0, 0))
                    per_mode_hour[mode][local_hour] = (
                        sum_st + int(rm.group(2)), n_cyc + 1)

    result: dict[int, float | None] = {}
    for hour in range(24):
        mode_means: list[float] = []
        for mode in RX_MODES:
            mh = per_mode_hour.get(mode, {})
            if hour not in mh:
                continue
            sum_st, n_cyc = mh[hour]
            if n_cyc < MIN_CYCLES_PER_BUCKET:
                continue
            mode_means.append(sum_st / n_cyc)
        result[hour] = (
            sum(mode_means) / len(mode_means) if mode_means else None)
    return result


def list_available_bands(stats_dir: Path) -> list[str]:
    """Bänder mit irgendwelchen Stats-Daten (egal welcher Modus).

    Sortierung: BAND_ORDER first (tief → hoch), unbekannte am Ende
    alphabetisch.
    """
    found: set[str] = set()
    for mode in RX_MODES:
        mode_path = stats_dir / mode
        if not mode_path.is_dir():
            continue
        for band_dir in mode_path.iterdir():
            if band_dir.is_dir() and (band_dir / "FT8").is_dir():
                found.add(band_dir.name)
    ordered = [b for b in BAND_ORDER if b in found]
    unknown = sorted(found - set(BAND_ORDER))
    return ordered + unknown


# ── Plot ────────────────────────────────────────────────────────────


def generate_plot(stats_dir: Path, output: Path, lang: str = "de") -> int:
    """Generiert Liniendiagramm und schreibt PNG.

    Returns: Anzahl Bänder mit darstellbaren Daten (>= 1 Stunde
    qualifiziert).
    """
    bands = list_available_bands(stats_dir)
    if not bands:
        print(f"[BandActivity] Keine Stats-Daten in {stats_dir} — kein Output")
        return 0

    if lang == "de":
        title = ("Band-Aktivität nach Berliner Stunde "
                 "(Ø Stationen, alle RX-Modi)")
        xlabel = "Stunde (Berlin)"
        ylabel = "Ø Stationen / 15s-Zyklus"
    else:
        title = ("Band activity by Berlin hour "
                 "(avg stations, all RX modes)")
        xlabel = "Hour (Berlin)"
        ylabel = "Avg stations / 15s cycle"

    fig, ax = plt.subplots(figsize=(12, 6), facecolor=DARK_BG)
    ax.set_facecolor(DARK_BG)

    n_plotted = 0
    for band in bands:
        per_hour = aggregate_band_hour(stats_dir, band)
        x_y = [(h, v) for h, v in sorted(per_hour.items()) if v is not None]
        if not x_y:
            continue
        xs, ys = zip(*x_y)
        ax.plot(xs, ys, marker="o", linewidth=2, markersize=6,
                color=BAND_COLORS.get(band, "#aaaaaa"), label=band)
        n_plotted += 1

    ax.set_title(title, color=DARK_FG, fontsize=14, pad=12)
    ax.set_xlabel(xlabel, color=DARK_FG, fontsize=11)
    ax.set_ylabel(ylabel, color=DARK_FG, fontsize=11)
    ax.set_xticks(range(0, 24))
    ax.set_xlim(-0.5, 23.5)
    ax.tick_params(colors=DARK_FG, labelsize=9)
    ax.grid(True, linestyle="--", linewidth=0.5,
            color=DARK_GRID, alpha=0.6)
    if n_plotted:
        ax.legend(loc="upper left", facecolor=DARK_BG,
                  edgecolor=DARK_GRID, labelcolor=DARK_FG,
                  fontsize=10, ncol=2)
    for spine in ax.spines.values():
        spine.set_color(DARK_GRID)

    output.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(output, dpi=120, facecolor=DARK_BG)
    plt.close(fig)
    print(f"[BandActivity] {n_plotted} Bänder geplottet → {output}")
    return n_plotted


# ── Entry-Point ─────────────────────────────────────────────────────


def main() -> int:
    n_de = generate_plot(STATS_DIR, OUTPUT_DE, "de")
    n_en = generate_plot(STATS_DIR, OUTPUT_EN, "en")
    return 0 if (n_de > 0 and n_en > 0) else 1


if __name__ == "__main__":
    sys.exit(main())
