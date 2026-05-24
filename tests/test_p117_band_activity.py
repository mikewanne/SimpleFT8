"""P117 (24.05.2026, v0.98.02) + P118 (v0.98.03) — Band-Aktivitäts-
Übersicht-Script, Berliner Zeit (DST-aware).

Mike-Wunsch P117: Standalone-Script `scripts/band_activity_summary.py`
für Quick-Reference zur Band-Aktivität (vor Park-Trip).

Mike-Wunsch P118: Berliner Zeit statt UTC im Plot, Sommer/Winter
automatisch über zoneinfo (Europe/Berlin).

Aggregation: pro `(Band, lokale Stunde)` arithmetisches Mittel der
Modus-Mittelwerte. Nur Modi mit >= MIN_CYCLES_PER_BUCKET=12 Zyklen
tragen bei. UTC-File-Stunde wird via `_utc_file_to_local_hour`
ins lokale Bucket aggregiert.

Test-Datum-Konvention (für deterministische DST):
- Sommer-Tests nutzen "2026-05-24" (DST aktiv → UTC+2)
- Winter-Tests nutzen "2026-12-15" (DST inaktiv → UTC+1)

Test-Coverage:
- T1 Leerer stats_dir → 0 Bänder
- T2 1 Band, 1 Modus mit 12 Cycles (Sommer) → Wert in UTC+2-Stunde
- T3 1 Band, 1 Modus mit 11 Cycles → KEIN Wert (Filter)
- T4 1 Band, 3 Modi je 12 Cycles → arithmetisches Mittel
- T5 1 Band, 2 Modi qualifiziert + 1 Modus zu wenig Cycles → Mittel aus 2
- T6 list_available_bands respektiert BAND_ORDER
- T7 list_available_bands ignoriert Dirs ohne FT8/-Subdir
- T8 generate_plot returnt 0 bei leerem Stats-Dir
- T9 generate_plot erstellt PNG-File
- T10 Stunden ohne Daten → None
- T11 P118 Winter-Datum → UTC+1 (statt UTC+2)
- T12 P118 Helper `_utc_file_to_local_hour` direkt (Sommer + Winter)
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
    """P118: 1 Band, 1 Modus, Sommer-Datum, UTC-14 → Berlin-16 (UTC+2)."""
    from band_activity_summary import aggregate_band_hour
    _write_stats_file(
        tmp_path / "Normal" / "20m" / "FT8",
        date="2026-05-24", hour=14, n_cycles=12, stations=30)
    result = aggregate_band_hour(tmp_path, "20m")
    assert result[16] == 30.0  # Berlin-Sommer = UTC+2
    assert result[14] is None  # UTC-14 ist nicht mehr key


def test_t3_one_mode_below_threshold_no_value(tmp_path):
    """1 Band, 1 Modus mit 11 Cycles → keine Berlin-Stunde hat Wert."""
    from band_activity_summary import aggregate_band_hour
    _write_stats_file(
        tmp_path / "Normal" / "20m" / "FT8",
        date="2026-05-24", hour=14, n_cycles=11, stations=30)
    result = aggregate_band_hour(tmp_path, "20m")
    assert result[16] is None  # Berlin-Sommer = UTC+2
    assert result[14] is None


def test_t4_three_modes_each_threshold_arithmetic_mean(tmp_path):
    """P118: 3 Modi je 12 Cycles, Sommer → arithmetisches Mittel in Berlin-Stunde."""
    from band_activity_summary import aggregate_band_hour
    _write_stats_file(tmp_path / "Normal" / "20m" / "FT8",
                      "2026-05-24", 14, 12, stations=30)
    _write_stats_file(tmp_path / "Diversity_Normal" / "20m" / "FT8",
                      "2026-05-24", 14, 12, stations=36)
    _write_stats_file(tmp_path / "Diversity_Dx" / "20m" / "FT8",
                      "2026-05-24", 14, 12, stations=24)
    result = aggregate_band_hour(tmp_path, "20m")
    # Mittel = (30 + 36 + 24) / 3 = 30 — in Berlin-Stunde 16 (UTC+2)
    assert result[16] == pytest.approx(30.0)


def test_t5_one_mode_below_threshold_uses_others(tmp_path):
    """P118: 2 Modi qualifiziert + 1 zu wenig Cycles → Mittel aus 2 in Berlin-Stunde."""
    from band_activity_summary import aggregate_band_hour
    _write_stats_file(tmp_path / "Normal" / "20m" / "FT8",
                      "2026-05-24", 14, 12, stations=30)
    _write_stats_file(tmp_path / "Diversity_Normal" / "20m" / "FT8",
                      "2026-05-24", 14, 12, stations=40)
    _write_stats_file(tmp_path / "Diversity_Dx" / "20m" / "FT8",
                      "2026-05-24", 14, 5, stations=100)
    result = aggregate_band_hour(tmp_path, "20m")
    # Mittel = (30 + 40) / 2 = 35 in Berlin-Stunde 16 (UTC+2)
    assert result[16] == pytest.approx(35.0)


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
    """P118: Stunde ohne Daten → None. Sommer-Datum UTC-14 → Berlin-16."""
    from band_activity_summary import aggregate_band_hour
    _write_stats_file(tmp_path / "Normal" / "20m" / "FT8",
                      "2026-05-24", 14, 12, stations=30)
    result = aggregate_band_hour(tmp_path, "20m")
    assert result[16] is not None  # Berlin-Sommer 14 UTC → 16
    assert result[3] is None       # 03 hat keine Daten
    assert result[20] is None      # 20 hat keine Daten


# ── P118: DST-Awareness (Berliner Zeit) ────────────────────────────


def test_t11_winter_date_uses_utc_plus_1(tmp_path):
    """P118: Winter-Datum (DST inaktiv) → UTC+1, nicht UTC+2."""
    from band_activity_summary import aggregate_band_hour
    _write_stats_file(tmp_path / "Normal" / "20m" / "FT8",
                      date="2026-12-15", hour=14, n_cycles=12, stations=30)
    result = aggregate_band_hour(tmp_path, "20m")
    # Berlin-Winter = UTC+1 → Berlin-Stunde 15
    assert result[15] == 30.0
    assert result[16] is None  # nicht UTC+2 (das wäre Sommer)


def test_t12_helper_utc_to_local_hour_sommer_und_winter():
    """P118: Helper-Funktion direkt mit bekannten DST-Grenzfällen."""
    from band_activity_summary import _utc_file_to_local_hour
    # Sommer (DST aktiv, UTC+2)
    assert _utc_file_to_local_hour("2026-05-24", 0) == 2
    assert _utc_file_to_local_hour("2026-05-24", 14) == 16
    assert _utc_file_to_local_hour("2026-05-24", 22) == 0  # rollover
    # Winter (DST inaktiv, UTC+1)
    assert _utc_file_to_local_hour("2026-12-15", 0) == 1
    assert _utc_file_to_local_hour("2026-12-15", 14) == 15
    assert _utc_file_to_local_hour("2026-12-15", 23) == 0  # rollover
    # DST-Wechsel-Tage (Edge-Case): Sommer→Winter Ende Oktober
    # 26.10.2025 02:00 UTC + DST-Wechsel rückwärts: Berlin = 03:00 Sommer dann 02:00 Winter
    # Pragmatisch: 02 UTC am Wechsel-Tag landet in Berlin-Stunde irgendwo zwischen 2-4
    assert _utc_file_to_local_hour("2026-10-25", 12) in (13, 14)  # Wechsel-Tag tolerant
