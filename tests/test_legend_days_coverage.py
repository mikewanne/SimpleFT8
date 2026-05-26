"""Diagramm-Legende Tage-Coverage ehrlicher (Mike 24.05.2026).

Mike-Beobachtung: 15m FT8 Legende zeigt "5 Tage" obwohl er an 9 unique
Tagen gemessen hat. `max(n_days)` zeigt nur die beste Stunde — bei
Mike's neuem kurz-aber-häufig-Mess-Stil (P116-Strategie) auf
verschiedenen Stunden ist die Diskrepanz größer und wird irreführend.

Fix:
- Neuer Helper `_count_unique_days_total(hour_stats)` — Union der
  daily-Keys über alle Stunden
- Neuer Helper `_format_basis_entry` mit conditional Format:
  - n_d_total == n_d_max → alte Kompakt-Format
  - n_d_total > n_d_max → "9 Tage gesamt (max 5/Std) · N Messpunkte"
- Neuer Template `basis_entry_split` in TEXTS["de"] + TEXTS["en"]
- Toter Code `_n_days_label` entfernt

ACs:
- AC1: Helper liefert korrekte Union bei Multi-Stunden
- AC2: Helper liefert 0 bei leerem hour_stats
- AC3: Template basis_entry_split existiert (DE + EN) mit korrekten Keys
- AC4: Conditional Format: gleiche Coverage → alte Form
- AC5: Conditional Format: ungleiche Coverage → neue Form mit Klammer
- AC6: `_n_days_label` ist entfernt
- AC7: Source-Inspektion neue Aufrufer in beiden Plot-Funktionen
"""

from __future__ import annotations

import inspect


def _import_helpers():
    """Lazy import (umgeht main()-Side-Effects bei matplotlib-Import)."""
    from scripts import generate_plots
    return generate_plots


# ---------------------------------------------------------------------------
# T1-T2: _count_unique_days_total Helper
# ---------------------------------------------------------------------------


def test_t1_count_unique_days_total_basic():
    """T1: Union der daily-Keys über alle Stunden."""
    gp = _import_helpers()
    hour_stats = {
        10: {"daily": {"2026-05-01": [5], "2026-05-02": [3]}},
        11: {"daily": {"2026-05-02": [4], "2026-05-03": [6]}},
        12: {"daily": {"2026-05-01": [2], "2026-05-04": [7]}},
    }
    # Union: {01, 02, 03, 04} = 4
    assert gp._count_unique_days_total(hour_stats) == 4


def test_t2_count_unique_days_total_empty():
    """T2: Leeres hour_stats → 0."""
    gp = _import_helpers()
    assert gp._count_unique_days_total({}) == 0


def test_t2b_count_unique_days_total_no_daily_keys():
    """T2b: hour_stats ohne daily-Keys → 0 (Defensive)."""
    gp = _import_helpers()
    hour_stats = {
        10: {"cycles": [1, 2, 3]},  # kein "daily"
        11: {"cycles": [4]},
    }
    assert gp._count_unique_days_total(hour_stats) == 0


# ---------------------------------------------------------------------------
# T3-T4: Templates basis_entry_split DE + EN
# ---------------------------------------------------------------------------


def test_t3_basis_entry_split_de_exists():
    """T3: TEXTS['de']['basis_entry_split'] existiert mit allen Keys."""
    gp = _import_helpers()
    template = gp.TEXTS["de"].get("basis_entry_split")
    assert template is not None, "basis_entry_split DE muss existieren"
    # Alle benötigten Format-Keys vorhanden
    assert "{label}" in template
    assert "{n_d_total}" in template
    assert "{n_d_max}" in template
    assert "{n_c_fmt}" in template
    # Format-Test (würde KeyError bei fehlenden Keys werfen)
    result = template.format(label="Normal", n_d_total=9, n_d_max=5,
                             n_c_fmt="7,522")
    assert "9" in result
    assert "5" in result
    assert "Normal" in result


def test_t4_basis_entry_split_en_exists():
    """T4: TEXTS['en']['basis_entry_split'] existiert mit allen Keys."""
    gp = _import_helpers()
    template = gp.TEXTS["en"].get("basis_entry_split")
    assert template is not None, "basis_entry_split EN muss existieren"
    assert "{label}" in template
    assert "{n_d_total}" in template
    assert "{n_d_max}" in template
    assert "{n_c_fmt}" in template
    result = template.format(label="Normal", n_d_total=9, n_d_max=5,
                             n_c_fmt="7,522")
    assert "9" in result
    assert "5" in result


# ---------------------------------------------------------------------------
# T5-T6: _format_basis_entry Conditional Logik
# ---------------------------------------------------------------------------


def test_t5_format_basis_entry_equal_coverage_uses_compact_form():
    """T5: n_d_total == n_d_max → alte Kompakt-Format (1 Tage-Wert)."""
    gp = _import_helpers()
    label = gp._format_basis_entry(
        gp.TEXTS["de"], "Normal", n_d_max=5, n_c_fmt="1.000", n_d_total=5)
    # Alte Form: "Normal\n5 Tage · 1.000 Messpunkte"
    assert "5 Tage" in label
    assert "gesamt" not in label, (
        "Bei gleicher Coverage darf 'gesamt' nicht erscheinen (KISS)")
    assert "max" not in label.lower() or "/Std" not in label


def test_t5b_format_basis_entry_equal_coverage_singular():
    """T5b: n_d_total == n_d_max == 1 → singular '1 Tag' (kein Suffix)."""
    gp = _import_helpers()
    label = gp._format_basis_entry(
        gp.TEXTS["de"], "Normal", n_d_max=1, n_c_fmt="100", n_d_total=1)
    assert "1 Tag" in label
    assert "1 Tage" not in label  # kein Plural-Suffix


def test_t6_format_basis_entry_split_coverage_uses_extended_form():
    """T6: n_d_total > n_d_max → erweiterte Form mit Klammer.

    Mike-Beispiel: 9 unique Tage gesamt, max 5 pro Stunde.
    """
    gp = _import_helpers()
    label = gp._format_basis_entry(
        gp.TEXTS["de"], "Normal", n_d_max=5, n_c_fmt="7.522", n_d_total=9)
    assert "9" in label
    assert "5" in label
    assert "gesamt" in label
    assert "/Std" in label or "Std)" in label
    # Sollte Mike-Format ähnlich sein
    assert "Tage gesamt" in label
    assert "(max 5/Std)" in label


def test_t6b_format_basis_entry_split_en():
    """T6b: EN-Variante mit "days total" / "max ... /hour"."""
    gp = _import_helpers()
    label = gp._format_basis_entry(
        gp.TEXTS["en"], "Normal", n_d_max=5, n_c_fmt="7,522", n_d_total=9)
    assert "9 days total" in label
    assert "max 5/hour" in label


# ---------------------------------------------------------------------------
# T7: Toter Code _n_days_label entfernt
# ---------------------------------------------------------------------------


def test_t7_dead_code_n_days_label_removed():
    """T7: _n_days_label (alt, ungenutzt, hatte KeyError-Bug) entfernt."""
    gp = _import_helpers()
    assert not hasattr(gp, "_n_days_label"), (
        "_n_days_label sollte entfernt sein — war toter Code mit "
        "KeyError-Bug (nutzte n_c= statt n_c_fmt=)")


# ---------------------------------------------------------------------------
# T8: Aufrufer in beiden Plot-Funktionen nutzen neuen Helper
# ---------------------------------------------------------------------------


def test_t8_create_stations_diagram_uses_new_helper():
    """T8: create_stations_diagram ruft _format_basis_entry."""
    gp = _import_helpers()
    source = inspect.getsource(gp.create_stations_diagram)
    assert "_format_basis_entry" in source, (
        "create_stations_diagram muss _format_basis_entry nutzen "
        "(neue conditional Format-Logik)")
    assert "_count_unique_days_total" in source, (
        "create_stations_diagram muss _count_unique_days_total nutzen")


def test_t9_create_diversity_diagram_uses_new_helper():
    """T9: create_diversity_diagram ruft _format_basis_entry."""
    gp = _import_helpers()
    source = inspect.getsource(gp.create_diversity_diagram)
    assert "_format_basis_entry" in source, (
        "create_diversity_diagram muss _format_basis_entry nutzen")
    assert "_count_unique_days_total" in source
    # hour_vals_all wird aufgehoben damit Helper sie nutzen kann
    assert "hour_vals_all" in source


# ---------------------------------------------------------------------------
# T10: End-to-end Format-String-Konsistenz
# ---------------------------------------------------------------------------


def test_t10_old_basis_entry_keys_unchanged():
    """T10: Alter basis_entry-Template bleibt unverändert (Pattern-
    Konsistenz für equal-coverage-Pfad)."""
    gp = _import_helpers()
    de = gp.TEXTS["de"]["basis_entry"]
    en = gp.TEXTS["en"]["basis_entry"]
    # Alte Format-Keys
    for tpl in [de, en]:
        assert "{label}" in tpl
        assert "{n_d}" in tpl
        assert "{pl}" in tpl
        assert "{n_c_fmt}" in tpl
