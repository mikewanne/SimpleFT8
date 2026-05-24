"""P117 (24.05.2026, v0.98.02) — Band-Aktivitäts-Übersicht-Script.

Mike-Wunsch: Standalone-Script `scripts/band_activity_summary.py` für
Quick-Reference zur Band-Aktivität (vor Park-Trip).

Aggregation: pro `(Band, Stunde)` arithmetisches Mittel der Modus-
Mittelwerte. Nur Modi mit >= MIN_CYCLES_PER_BUCKET=12 Zyklen für
die jeweilige Stunde tragen bei.

Test-Coverage:
- T1 Leerer stats_dir → 0 Bänder
- T2 1 Band, 1 Modus mit 12 Cycles → 1 Stunde mit Wert
- T3 1 Band, 1 Modus mit 11 Cycles → KEIN Wert (Filter)
- T4 1 Band, 3 Modi je 12 Cycles → arithmetisches Mittel
- T5 1 Band, 2 Modi qualifiziert + 1 Modus zu wenig Cycles → Mittel aus 2
- T6 list_available_bands respektiert BAND_ORDER
- T7 list_available_bands ignoriert Dirs ohne FT8/-Subdir
- T8 generate_plot returnt 0 bei leerem Stats-Dir
- T9 generate_plot erstellt PNG-File
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Script-Pfad zum Python-Path hinzufügen damit `scripts.band_activity_summary`
# importierbar ist (es ist KEIN echtes Modul mit __init__.py)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))


def _write_stats_file(directory: Path, date: str, hour: int,
                      n_cycles: int, stations: int = 20):
    """Hilfsfunktion: schreibt eine Stats-MD-Datei mit n_cycles Zeilen."""
    directory.mkdir(parents=True, exist_ok=True)
    f = directory / f"{date}_{hour:02d}.md"
    lines = ["| Zeit | Stationen | Ø SNR |", "|------|-----------|-------|"]
    for i in range(n_cycles):
        lines.append(f"| {hour:02d}:{i % 60:02d}:13 | {stations} | -15 |")
    f.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return f


# ── T1-T5: Aggregation ────────────────────────────────────────────


def test_t1_empty_stats_no_bands(tmp_path):
    """Leerer Stats-Dir → list_available_bands gibt [] zurück."""
    from band_activity_summary import list_available_bands
    assert list_available_bands(tmp_path) == []


def test_t2_one_mode_threshold_exact_yields_value(tmp_path):
    """1 Band, 1 Modus mit exakt 12 Cycles → Stunde hat Wert (= station-count)."""
    from band_activity_summary import aggregate_band_hour
    _write_stats_file(
        tmp_path / "Normal" / "20m" / "FT8",
        date="2026-05-24", hour=14, n_cycles=12, stations=30)
    result = aggregate_band_hour(tmp_path, "20m")
    assert result[14] == 30.0  # Mittel aus 1 Modus = 30


def test_t3_one_mode_below_threshold_no_value(tmp_path):
    """1 Band, 1 Modus mit 11 Cycles → Stunde 14 hat None (Filter greift)."""
    from band_activity_summary import aggregate_band_hour
    _write_stats_file(
        tmp_path / "Normal" / "20m" / "FT8",
        date="2026-05-24", hour=14, n_cycles=11, stations=30)
    result = aggregate_band_hour(tmp_path, "20m")
    assert result[14] is None


def test_t4_three_modes_each_threshold_arithmetic_mean(tmp_path):
    """3 Modi je 12 Cycles mit unterschiedlichen Stationen → arithmetisches
    Mittel der Modus-Means."""
    from band_activity_summary import aggregate_band_hour
    # Normal: 30 Stationen/Cycle
    _write_stats_file(tmp_path / "Normal" / "20m" / "FT8",
                      "2026-05-24", 14, 12, stations=30)
    # Diversity_Normal: 36
    _write_stats_file(tmp_path / "Diversity_Normal" / "20m" / "FT8",
                      "2026-05-24", 14, 12, stations=36)
    # Diversity_Dx: 24 (DX filtert SNR<-10)
    _write_stats_file(tmp_path / "Diversity_Dx" / "20m" / "FT8",
                      "2026-05-24", 14, 12, stations=24)
    result = aggregate_band_hour(tmp_path, "20m")
    # Mittel = (30 + 36 + 24) / 3 = 30
    assert result[14] == pytest.approx(30.0)


def test_t5_one_mode_below_threshold_uses_others(tmp_path):
    """2 Modi qualifiziert + 1 Modus zu wenig Cycles → Mittel aus 2 Modi
    (Mike-Spec: durch ANZAHL vorhandener Modi, nicht stur durch 3)."""
    from band_activity_summary import aggregate_band_hour
    _write_stats_file(tmp_path / "Normal" / "20m" / "FT8",
                      "2026-05-24", 14, 12, stations=30)
    _write_stats_file(tmp_path / "Diversity_Normal" / "20m" / "FT8",
                      "2026-05-24", 14, 12, stations=40)
    # DX nur 5 Cycles → Filter greift, DX wird ignoriert
    _write_stats_file(tmp_path / "Diversity_Dx" / "20m" / "FT8",
                      "2026-05-24", 14, 5, stations=100)  # Wert egal
    result = aggregate_band_hour(tmp_path, "20m")
    # Mittel = (30 + 40) / 2 = 35 (DX ignoriert)
    assert result[14] == pytest.approx(35.0)


# ── T6-T7: Bänder-Liste + Sortierung ────────────────────────────


def test_t6_band_order_respected(tmp_path):
    """list_available_bands sortiert nach BAND_ORDER (tief → hoch)."""
    from band_activity_summary import list_available_bands
    # Anlegen in zufälliger Reihenfolge
    for band in ["20m", "40m", "15m", "80m"]:
        _write_stats_file(tmp_path / "Normal" / band / "FT8",
                          "2026-05-24", 14, 12)
    bands = list_available_bands(tmp_path)
    # BAND_ORDER: 80m vor 40m vor 20m vor 15m
    assert bands == ["80m", "40m", "20m", "15m"]


def test_t7_ignores_dirs_without_ft8_subdir(tmp_path):
    """Band-Verzeichnis ohne FT8/-Subdir wird ignoriert (nicht alle Mode-
    Pfade haben FT4/FT2-Daten)."""
    from band_activity_summary import list_available_bands
    # 20m hat FT8/, 17m nur FT4/ (kein FT8)
    _write_stats_file(tmp_path / "Normal" / "20m" / "FT8",
                      "2026-05-24", 14, 12)
    (tmp_path / "Normal" / "17m" / "FT4").mkdir(parents=True)
    bands = list_available_bands(tmp_path)
    assert "20m" in bands
    assert "17m" not in bands


# ── T8-T9: Plot-Generation ─────────────────────────────────────────


def test_t8_generate_plot_zero_when_no_data(tmp_path):
    """generate_plot returnt 0 bei leerem Stats-Dir."""
    from band_activity_summary import generate_plot
    output = tmp_path / "out.png"
    n = generate_plot(tmp_path / "empty_stats", output, "de")
    assert n == 0
    assert not output.exists()  # kein PNG bei 0 Daten


def test_t9_generate_plot_writes_png_when_data_present(tmp_path):
    """generate_plot erstellt PNG-File mit korrektem Header."""
    from band_activity_summary import generate_plot
    _write_stats_file(tmp_path / "Normal" / "20m" / "FT8",
                      "2026-05-24", 14, 20, stations=42)
    output = tmp_path / "test.png"
    n = generate_plot(tmp_path, output, "de")
    assert n == 1
    assert output.exists()
    # PNG-Header-Check (magic bytes)
    assert output.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"


# ── T10: Edge — Stunde komplett ohne Daten ──────────────────────


def test_t10_hour_with_no_data_yields_none(tmp_path):
    """Stunde ohne Daten in irgendeinem Modus → None im Result."""
    from band_activity_summary import aggregate_band_hour
    _write_stats_file(tmp_path / "Normal" / "20m" / "FT8",
                      "2026-05-24", 14, 12, stations=30)
    result = aggregate_band_hour(tmp_path, "20m")
    assert result[14] is not None  # 14 hat Daten
    assert result[3] is None       # 03 nicht
    assert result[20] is None      # 20 nicht
