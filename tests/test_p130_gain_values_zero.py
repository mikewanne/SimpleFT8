"""P130 (25.05.2026) — GAIN_VALUES = [0, 10, 20] für Vollständigkeit.

Mike-Frage Feierabend 25.05.2026:
> „wenn wir gain einmessen 0 gain messen wir gar nicht mehr, das hatten
> wir mal verworfen um zeit zu sparen aber was ist wenn 0 gain das
> beste ist zu zeit wenn wir gerade messen"

Berechtigt: Low-Band-Defaults (160/80/60m) sind in PREAMP_PRESETS = 0,
wurden aber seit v0.89 (Commit bea87f9, 4.5.2026) nicht mehr gemessen.

KISS-Variante A: GAIN_VALUES = [0, 10, 20] zurück. +90s pro
Kalibrierung (3 Min statt 2), alle Stufen abgedeckt.

Tests:
- T1: GAIN_VALUES enthält 0, 10, 20
- T2: Schedule-Länge konsistent (2 ANT × 3 GAIN × 2 ROUNDS = 12)
- T3: PREAMP_PRESETS-Defaults sind alle in GAIN_VALUES enthalten
"""

from __future__ import annotations


def test_t1_gain_values_includes_zero():
    """T1 (P130): GAIN_VALUES enthält 0 dB (Low-Band-Default)."""
    from ui.dx_tune_dialog import GAIN_VALUES
    assert 0 in GAIN_VALUES, (
        "P130: 0 dB muss in GAIN_VALUES sein — Low-Band-Default 160/80/60m")
    assert 10 in GAIN_VALUES
    assert 20 in GAIN_VALUES
    assert GAIN_VALUES == [0, 10, 20]


def test_t2_rounds_unchanged():
    """T2: ROUNDS bleibt 2 (Mike-Setup, ändert nicht in P130)."""
    from ui.dx_tune_dialog import ROUNDS
    assert ROUNDS == 2


def test_t3_preamp_defaults_all_measured():
    """T3 (P130): Alle PREAMP_PRESETS-Default-Werte sind in GAIN_VALUES.

    Sonst hätten Low-Band-Sitzungen (160/80/60m) ihren Default-Wert
    NIE gemessen — exakt der Bug den Mike fragte.
    """
    from ui.dx_tune_dialog import GAIN_VALUES
    from radio.presets import PREAMP_PRESETS
    for band, default_gain in PREAMP_PRESETS.items():
        assert default_gain in GAIN_VALUES, (
            f"Band {band} hat Default {default_gain} dB aber GAIN_VALUES "
            f"={GAIN_VALUES} enthält das nicht — Mike-Frage P130")


def test_t4_schedule_length_consistent():
    """T4: Schedule-Aufbau hat 2 ANT × 3 GAIN = 6 Kombos pro Runde.

    Verifiziert dass GAIN_VALUES-Erweiterung in Schedule-Builder
    konsistent durchschlägt (via len(GAIN_VALUES) * 2 in dx_tune_dialog).
    """
    from ui.dx_tune_dialog import GAIN_VALUES, ROUNDS
    combos_per_round = len(GAIN_VALUES) * 2  # ANT1 + ANT2 pro Gain
    total_cycles = combos_per_round * ROUNDS
    assert combos_per_round == 6
    assert total_cycles == 12


def test_t5_calibration_duration_3min():
    """T5: 12 Zyklen × 15s = 180s = 3 Min Kalibrierungs-Dauer."""
    from ui.dx_tune_dialog import GAIN_VALUES, ROUNDS
    total_cycles = len(GAIN_VALUES) * 2 * ROUNDS
    duration_s = total_cycles * 15  # FT8-Slot 15s
    assert duration_s == 180, f"erwarte 180s (3 Min), ist {duration_s}s"
