"""Tests fuer core/bandpilot_md.py — MD-Generator fuer Bandpilot-Empfehlungen."""

from pathlib import Path

import pytest

from core.bandpilot_md import _build_md, _format_cell, _top1_label, write_bandpilot_md
from core.mode_recommender import MIN_CYCLES_HOUR, MIN_DAYS_HOUR


# ── _format_cell ──────────────────────────────────────────────────────────────

def test_format_cell_with_data():
    assert _format_cell({"days": 5, "cycles": 100, "mean": 45.234}) == "5·45.2"


def test_format_cell_zero_days():
    assert _format_cell({"days": 0, "cycles": 0, "mean": None}) == "—"


def test_format_cell_none():
    assert _format_cell(None) == "—"
    assert _format_cell({}) == "—"


# ── _top1_label ────────────────────────────────────────────────────────────────

def test_top1_label_diversity_dx_wins():
    modes = {
        "normal":           {"days": MIN_DAYS_HOUR, "cycles": MIN_CYCLES_HOUR,
                              "mean": 10.0},
        "diversity_normal": {"days": MIN_DAYS_HOUR, "cycles": MIN_CYCLES_HOUR,
                              "mean": 15.0},
        "diversity_dx":     {"days": MIN_DAYS_HOUR, "cycles": MIN_CYCLES_HOUR,
                              "mean": 20.0},
    }
    assert _top1_label(modes) == "Diversity DX"


def test_top1_label_normal_wins():
    modes = {
        "normal":           {"days": MIN_DAYS_HOUR, "cycles": MIN_CYCLES_HOUR,
                              "mean": 50.0},
        "diversity_normal": {"days": MIN_DAYS_HOUR, "cycles": MIN_CYCLES_HOUR,
                              "mean": 15.0},
        "diversity_dx":     {"days": MIN_DAYS_HOUR, "cycles": MIN_CYCLES_HOUR,
                              "mean": 20.0},
    }
    assert _top1_label(modes) == "Normal"


def test_top1_label_insufficient_returns_placeholder():
    modes = {
        "normal":           {"days": MIN_DAYS_HOUR - 1,
                              "cycles": MIN_CYCLES_HOUR, "mean": 10.0},
        "diversity_normal": {"days": MIN_DAYS_HOUR,
                              "cycles": MIN_CYCLES_HOUR, "mean": 15.0},
        "diversity_dx":     {"days": MIN_DAYS_HOUR,
                              "cycles": MIN_CYCLES_HOUR, "mean": 20.0},
    }
    assert _top1_label(modes) == "_zu wenig Daten_"


def test_top1_label_empty_returns_placeholder():
    assert _top1_label({}) == "_zu wenig Daten_"


# ── _build_md ─────────────────────────────────────────────────────────────────

def test_build_md_24_rows_when_summary_present():
    """V3-AK 32 #13: 24 UTC-Zeilen erzeugt."""
    summary = {
        12: {
            "normal":           {"days": MIN_DAYS_HOUR,
                                  "cycles": MIN_CYCLES_HOUR, "mean": 10.0},
            "diversity_normal": {"days": MIN_DAYS_HOUR,
                                  "cycles": MIN_CYCLES_HOUR, "mean": 20.0},
            "diversity_dx":     {"days": MIN_DAYS_HOUR,
                                  "cycles": MIN_CYCLES_HOUR, "mean": 15.0},
        }
    }
    md = _build_md("40m", "FT8", summary)
    # 24 Tabellen-Zeilen plus Header — Zaehle die UTC-Zeilen-Markers
    utc_lines = [line for line in md.splitlines() if line.startswith("| ") and
                 not line.startswith("| UTC ") and not line.startswith("|---")]
    assert len(utc_lines) == 24


def test_build_md_handles_empty_summary_gracefully():
    """V3-AK 32 #14 / V3-AK 16: leeres Summary → Hinweis-Zeile, keine Tabelle."""
    md = _build_md("40m", "FT8", {})
    assert "Keine Statistik-Daten vorhanden" in md
    assert "| UTC |" not in md  # keine Tabelle


def test_build_md_includes_header_and_band():
    summary = {}
    md = _build_md("40m", "FT8", summary)
    assert "# Bandpilot Empfehlung — 40m FT8" in md


def test_build_md_top1_label_in_row():
    summary = {
        13: {
            "normal":           {"days": MIN_DAYS_HOUR,
                                  "cycles": MIN_CYCLES_HOUR, "mean": 10.0},
            "diversity_normal": {"days": MIN_DAYS_HOUR,
                                  "cycles": MIN_CYCLES_HOUR, "mean": 15.0},
            "diversity_dx":     {"days": MIN_DAYS_HOUR,
                                  "cycles": MIN_CYCLES_HOUR, "mean": 50.0},
        }
    }
    md = _build_md("40m", "FT8", summary)
    # Zeile 13 muss "Diversity DX" als Top-1 enthalten
    lines = md.splitlines()
    row_13 = [line for line in lines if line.startswith("| 13 |")]
    assert len(row_13) == 1
    assert "Diversity DX" in row_13[0]


# ── write_bandpilot_md ─────────────────────────────────────────────────────────

NORMAL_HEADER = (
    "# Statistik 2026-04-21 12:00-12:59 UTC | FT8 | 40m | Normal\n\n"
    "| Zeit | Stationen | Ø SNR |\n"
    "|------|-----------|-------|\n"
)
DIV_HEADER = (
    "# Statistik 2026-04-21 12:00-12:59 UTC | FT8 | 40m | Diversity_Normal\n\n"
    "| Zeit | Stationen | Ø SNR | Ant2 Wins | Ø ΔSNR |\n"
    "|------|-----------|-------|-----------|--------|\n"
)


def _write_normal(path: Path, counts: list[int]):
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [NORMAL_HEADER]
    for i, c in enumerate(counts):
        lines.append(f"| 12:{i:02d}:00 | {c} | -20 |\n")
    path.write_text("".join(lines), encoding="utf-8")


def _write_div(path: Path, counts: list[int]):
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [DIV_HEADER]
    for i, c in enumerate(counts):
        lines.append(f"| 12:{i:02d}:00 | {c} | -20 | 2 | -1.5 |\n")
    path.write_text("".join(lines), encoding="utf-8")


def test_write_bandpilot_md_creates_file_with_data(tmp_path):
    """V3-AK 32 #13: End-to-End — schreibt Datei mit 24-Zeilen-Tabelle."""
    stats = tmp_path / "stats"
    output = tmp_path / "auswertung"
    for d in ("2026-04-21", "2026-04-22", "2026-04-23"):
        _write_normal(stats / "Normal" / "40m" / "FT8" / f"{d}_12.md", [10] * 30)
        _write_div(stats / "Diversity_Normal" / "40m" / "FT8" / f"{d}_12.md", [20] * 30)
        _write_div(stats / "Diversity_Dx" / "40m" / "FT8" / f"{d}_12.md", [15] * 30)

    out_path = write_bandpilot_md(stats, output, "40m")
    assert out_path.exists()
    assert out_path.name == "Bandpilot-40m-FT8.md"
    content = out_path.read_text(encoding="utf-8")
    assert "# Bandpilot Empfehlung — 40m FT8" in content
    # Stunde 12 muss "Diversity Standard" als Top-1 zeigen (20 > 15 > 10)
    row_12 = [line for line in content.splitlines() if line.startswith("| 12 |")]
    assert len(row_12) == 1
    assert "Diversity Standard" in row_12[0]


def test_write_bandpilot_md_handles_missing_stats_gracefully(tmp_path):
    """V3-AK 32 #14: kein Stats-Verzeichnis → Hinweis-Datei, kein Crash."""
    stats = tmp_path / "stats"  # existiert nicht
    output = tmp_path / "auswertung"
    out_path = write_bandpilot_md(stats, output, "40m")
    assert out_path.exists()
    content = out_path.read_text(encoding="utf-8")
    assert "Keine Statistik-Daten vorhanden" in content


def test_write_bandpilot_md_creates_output_dir(tmp_path):
    """write_bandpilot_md erstellt output_dir wenn fehlt."""
    stats = tmp_path / "stats"
    output = tmp_path / "non_existent" / "auswertung"
    out_path = write_bandpilot_md(stats, output, "40m")
    assert out_path.parent.exists()
    assert out_path.exists()
