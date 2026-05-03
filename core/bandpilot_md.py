"""Bandpilot MD-Generator — `auswertung/Bandpilot-<band>-FT8.md`.

24-Zeilen-Tabelle (UTC 00..23) mit pro-Stunden-Werten der drei
RX-Modi (Normal / Diversity Standard / Diversity DX) plus Top-1.
Kein Live-Feed — wird beim App-Start einmal generiert (und beim
``scripts/generate_plots.py``-Lauf mitgezogen).

Mike+R1 Konsens 2026-05-04 (V3-AK 15):
- Format pro Zelle: ``<Tage>·<Mean mit 1 Nachkomma>``
- Leere Zelle: ``—`` (Em-Dash) wenn 0 Tage in dem Modus in dieser Stunde
- Top-1: User-Label (``Normal`` / ``Diversity Standard`` / ``Diversity DX``)
- Bei zu wenig Daten in einem oder mehreren Modi: ``_zu wenig Daten_``
- Sprache: nur DE
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from core.mode_recommender import (
    CODE_MODES,
    MIN_CYCLES_HOUR,
    MIN_DAYS_HOUR,
    USER_LABEL,
    aggregate_stats_by_hour,
)


def _format_cell(entry: dict | None) -> str:
    """Eine Tabellenzelle: ``<Tage>·<Mean>`` oder ``—``."""
    if not entry or entry.get("days", 0) == 0 or entry.get("mean") is None:
        return "—"
    return f"{entry['days']}·{entry['mean']:.1f}"


def _top1_label(modes_in_hour: dict[str, dict]) -> str:
    """Top-1-Spalte: User-Label oder ``_zu wenig Daten_``.

    Schwellenpruefung pro Modus identisch zu ``recommend_for_hour``:
    alle drei Modi muessen MIN_DAYS_HOUR + MIN_CYCLES_HOUR + valide mean
    erfuellen — sonst ``_zu wenig Daten_``.
    """
    means: dict[str, float] = {}
    for code in CODE_MODES:
        entry = modes_in_hour.get(code, {})
        if (entry.get("days", 0) < MIN_DAYS_HOUR or
                entry.get("cycles", 0) < MIN_CYCLES_HOUR or
                entry.get("mean") is None):
            return "_zu wenig Daten_"
        means[code] = entry["mean"]

    top_code = max(means, key=means.get)
    return USER_LABEL[top_code]


def _build_md(band: str, ft_mode: str, summary: dict[int, dict[str, dict]]) -> str:
    """MD-Inhalt aufbauen — 24-Zeilen-Tabelle plus Header.

    Falls ``summary`` leer ist: Hinweis-Zeile statt Tabelle (V3-AK 16).
    """
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    lines: list[str] = [
        f"# Bandpilot Empfehlung — {band} {ft_mode}",
        "",
        f"Stand: {today} (UTC, App-Start). "
        f"Quelle: `statistics/<Mode>/{band}/{ft_mode}/`.",
        "",
    ]

    if not summary:
        lines.append("_Keine Statistik-Daten vorhanden — bitte FT8-Sessions "
                     "laufen lassen._")
        lines.append("")
        return "\n".join(lines)

    lines.extend([
        f"Schwellen pro Stunde: ≥ {MIN_DAYS_HOUR} Messtage UND "
        f"≥ {MIN_CYCLES_HOUR} Slots pro Modus.",
        "",
        "| UTC | Normal | Div Standard | Div DX | Top-1 |",
        "|---:|---:|---:|---:|:---|",
    ])

    for hour in range(24):
        modes = summary.get(hour, {})
        n_cell = _format_cell(modes.get("normal"))
        s_cell = _format_cell(modes.get("diversity_normal"))
        d_cell = _format_cell(modes.get("diversity_dx"))
        top1 = _top1_label(modes) if modes else "_zu wenig Daten_"
        lines.append(f"| {hour:02d} | {n_cell} | {s_cell} | {d_cell} | {top1} |")

    lines.append("")
    return "\n".join(lines)


def write_bandpilot_md(
    stats_dir: Path,
    output_dir: Path,
    band: str,
    ft_mode: str = "FT8",
) -> Path:
    """MD-Empfehlungs-Datei fuer (band, ft_mode) erzeugen.

    Args:
        stats_dir: Pfad zu ``statistics/`` (App-Root-relativ).
        output_dir: Pfad zu ``auswertung/`` (Ziel-Verzeichnis).
        band: ``"40m"``, ``"20m"`` etc.
        ft_mode: Aktuell nur ``"FT8"`` (Stats-Logger filtert).

    Returns: Pfad zur erzeugten Datei (``Bandpilot-<band>-<ft_mode>.md``).
    """
    summary = aggregate_stats_by_hour(stats_dir, band, protocol=ft_mode)
    md = _build_md(band, ft_mode, summary)

    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / f"Bandpilot-{band}-{ft_mode}.md"
    out_path.write_text(md, encoding="utf-8")
    return out_path
