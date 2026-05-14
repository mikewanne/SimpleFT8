"""P14 — DT-Werte-Symmetrie (v0.97.16).

10 Tests fuer:
- MAD-basierter Outlier-Filter (Hampel)
- DEADBAND-Reduktion 0.05 → 0.02 (R1-F1)
- Mike's Original-Daten-Sanity (R1-F2 Wurzel-Anker)
- Opt-in Debug-Logging (R1-F6)

Wichtig: T7 (Sanity) prueft den BISHERIGEN Algorithmus mit einfachem
Median — wenn dieser Test fehlschlaegt, ist ein anderer Bug in
update_from_decoded zu suchen (R1-F2-Anti-Symptom-Fix).
"""
from __future__ import annotations

import importlib
import statistics

import pytest


# Mike's RX-Panel-Screenshot 13.05.2026 ~07:30 UTC, sortiert.
# 11 negativ, 1 positiv (≥0.1), 8 nahe 0. Ausreisser bei -1.2 / -0.7 / -0.4 / +0.3.
MIKE_20_VALUES = [
    -1.2, -0.7, -0.7, -0.4, -0.3, -0.2, -0.1, -0.1, -0.1, -0.1,
    -0.1,  0.0,  0.0,  0.0,  0.0,  0.0,  0.0,  0.0,  0.0,  0.3,
]


@pytest.fixture
def fresh_ntp(monkeypatch):
    """Frischer DT-Modul-State."""
    import core.ntp_time as nt
    monkeypatch.setattr(nt, "_saved", {})
    monkeypatch.setattr(nt, "_correction", 0.0)
    monkeypatch.setattr(nt, "_hardware_default_offset", 0.0)
    monkeypatch.setattr(nt, "_last_logged_load", None)
    monkeypatch.setattr(nt, "_mode", "FT8")
    monkeypatch.setattr(nt, "_band", "20m")
    monkeypatch.setattr(nt, "_phase", "measure")
    monkeypatch.setattr(nt, "_is_initial", True)
    monkeypatch.setattr(nt, "_cycle_count", 0)
    monkeypatch.setattr(nt, "_measure_buffer", [])
    yield nt


# ── MAD-Filter Helper Unit-Tests ─────────────────────────────────────────


def test_mad_filter_mikes_20_values():
    """T1: Mike's 20 RX-DT-Werte → mind. 5 Outliers raus,
    filtered_median im DEADBAND ±0.02s.

    Erwartet (Hand-Rechnung):
    - median = -0.05, MAD = 0.05, threshold = 0.125
    - Outliers entfernt: -1.2, -0.7, -0.7, -0.4, -0.3, -0.2, +0.3 (= 7 Werte)
    - Uebrig: 13 Werte → Median = 0.0 (im Totband)
    """
    from core.ntp_time import _filter_outliers_mad
    filtered = _filter_outliers_mad(MIKE_20_VALUES)
    assert len(MIKE_20_VALUES) - len(filtered) >= 5, \
        f"Mindestens 5 Outliers erwartet, gefiltert: {len(MIKE_20_VALUES) - len(filtered)}"
    filtered_median = statistics.median(filtered)
    assert -0.02 <= filtered_median <= 0.02, \
        f"Filtered median sollte im Totband sein, war {filtered_median:+.3f}"


def test_mad_filter_n_below_threshold():
    """T2: Bei n<7 → Identity, kein Filter (FT4/FT2-Schutz)."""
    from core.ntp_time import _filter_outliers_mad
    values = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6]  # n=6
    assert _filter_outliers_mad(values) == values


def test_mad_filter_mad_zero():
    """T3: Alle Werte identisch → MAD=0 → Identity."""
    from core.ntp_time import _filter_outliers_mad
    values = [0.0] * 10
    assert _filter_outliers_mad(values) == values


def test_mad_filter_n10_one_outlier():
    """T4: Ein klarer Outlier wird entfernt (realistische FT8-Verteilung).

    Hinweis: bei perfekt-identischen Werten mit nur 1 Outlier ist MAD=0
    (median der absoluten Abweichungen ist 0 weil ≥50% identisch sind),
    dann greift _MAD_MIN_OUT-Notnagel → Identity. Real-FT8-Daten haben
    immer leichte Streuung, daher dieser realistische Test.
    """
    from core.ntp_time import _filter_outliers_mad
    # 9 Werte um 0 ±0.05 + 1 Outlier -1.0
    values = [-1.0, -0.05, -0.03, -0.01, 0.0, 0.01, 0.02, 0.03, 0.04, 0.05]
    filtered = _filter_outliers_mad(values)
    assert -1.0 not in filtered, \
        f"Outlier -1.0 sollte entfernt sein, gefiltert: {filtered}"
    # Median der gefilterten Werte sollte nahe 0 sein
    assert abs(statistics.median(filtered)) <= 0.03


def test_mad_filter_notnagel_min3():
    """T5: Notnagel-Schutz — Filter gibt nie weniger als _MAD_MIN_OUT (3)
    Werte zurueck. Schutz vor pathologischen Eingaben.

    Realistisch gesehen ist es bei Hampel-Filter mit k=2.5 schwer einen
    Fall zu konstruieren wo MAD>0 UND nach Filter <3 Werten uebrig sind
    — denn der Median der Abweichungen (MAD) waechst mit den Outliern
    selbst. Bei hoch-homogenen Daten greift typischerweise MAD=0 → Identity.

    Dieser Test deckt die Notnagel-Konstante (_MAD_MIN_OUT) ab und prueft
    dass len(result) >= 3 fuer eine konstruierte 9-Werte-Eingabe.
    """
    from core.ntp_time import _filter_outliers_mad
    values = [0.0, 10.0, 10.0, 10.0, 10.0, 10.0, 10.0, 10.0, 10.0]
    filtered = _filter_outliers_mad(values)
    assert len(filtered) >= 3, \
        f"Notnagel verletzt: Filter gab {len(filtered)} Werte zurueck"


# ── DEADBAND-Konstante ───────────────────────────────────────────────────


def test_deadband_constant_002():
    """T6: DEADBAND wurde von 0.05 auf 0.02 reduziert (R1-F1)."""
    from core.ntp_time import DEADBAND
    assert DEADBAND == 0.02


# ── R1-F2 Sanity-Anker (Wurzel-Test) ─────────────────────────────────────


def test_simple_median_mikes_data_converges_to_020(fresh_ntp, monkeypatch):
    """T7: R1-F2 SANITY-ANKER — Verifikation dass der bisherige Algorithmus
    grundsaetzlich KONVERGIERT.

    Setup: _correction=0.27, _is_initial=False, 2 MEASURE-Slots mit Mike's
    20 Werten (Median -0.1). Erwartung: avg_median = -0.1, delta = -0.07,
    Endkorrektur = 0.20 ± 0.01.

    WICHTIG: Dieser Test bypasst den MAD-Filter (Identity) um den
    BISHERIGEN Algorithmus zu pruefen. Wenn dieser Test fail wird,
    ist ein bisher unbekannter Bug in update_from_decoded zu finden,
    BEVOR MAD-Filter irgendwas korrigiert (R1-F2-Anti-Symptom-Fix).
    """
    nt = fresh_ntp
    nt._correction = 0.27
    nt._is_initial = False
    nt._phase = "measure"
    nt._cycle_count = 0
    nt._measure_buffer = []

    # MAD-Filter zu Identity stuben (testet rohen Algorithmus)
    monkeypatch.setattr(nt, "_filter_outliers_mad", lambda values, k=2.5: list(values))

    # 1. MEASURE-Slot
    result1 = nt.update_from_decoded(MIKE_20_VALUES)
    assert result1 is False, "1. Slot sollte False (noch sammeln)"
    assert nt._phase == "measure"

    # 2. MEASURE-Slot
    result2 = nt.update_from_decoded(MIKE_20_VALUES)
    assert result2 is True, "2. Slot sollte True (Korrektur applied)"

    # Erwartung: avg_median = -0.1, delta = -0.1 × 0.7 = -0.07
    # → _correction = 0.27 - 0.07 = 0.20
    assert nt._correction == pytest.approx(0.20, abs=0.01), \
        f"Korrektur sollte ~0.20 sein, war {nt._correction:+.4f}"


# ── MAD-Filter im update_from_decoded Pfad ───────────────────────────────


def test_mad_filter_mikes_data_no_update(fresh_ntp):
    """T8: Mit aktivem MAD-Filter bleibt Korrektur unveraendert (Mike's
    Daten ergeben filtered_median ~0 → im Totband → kein Update)."""
    nt = fresh_ntp
    nt._correction = 0.27
    nt._is_initial = False
    nt._phase = "measure"
    nt._cycle_count = 0
    nt._measure_buffer = []

    # 1. Slot
    nt.update_from_decoded(MIKE_20_VALUES)
    # 2. Slot
    nt.update_from_decoded(MIKE_20_VALUES)
    # MAD-Filter hat Outliers entfernt, Median ~0, im Totband → kein Update
    assert nt._correction == pytest.approx(0.27, abs=0.005), \
        f"Korrektur sollte unveraendert bleiben, war {nt._correction:+.4f}"


# ── Debug-Logging Opt-In ─────────────────────────────────────────────────


def test_debug_log_opt_in(monkeypatch, capsys, fresh_ntp):
    """T9: Bei SIMPLEFT8_DT_DEBUG=1 schreibt update_from_decoded eine
    [DT-DBG]-Zeile pro Slot."""
    import core.ntp_time as nt
    monkeypatch.setattr(nt, "_DT_DEBUG", True)
    nt._correction = 0.27
    nt._is_initial = False
    nt._phase = "measure"
    nt._cycle_count = 0
    nt._measure_buffer = []

    nt.update_from_decoded(MIKE_20_VALUES)
    captured = capsys.readouterr()
    assert "[DT-DBG]" in captured.out, \
        f"Debug-Zeile erwartet, captured: {captured.out!r}"
    assert "raw=" in captured.out
    assert "filt=" in captured.out


def test_debug_log_default_off(monkeypatch, capsys, fresh_ntp):
    """T10: Default _DT_DEBUG=False → keine [DT-DBG]-Zeile.

    Final-R1-HINWEIS: monkeypatch.delenv schuetzt vor Env-Var-Leak aus
    der Test-Shell.
    """
    monkeypatch.delenv("SIMPLEFT8_DT_DEBUG", raising=False)
    import core.ntp_time as nt
    monkeypatch.setattr(nt, "_DT_DEBUG", False)
    nt._correction = 0.27
    nt._is_initial = False
    nt._phase = "measure"
    nt._cycle_count = 0
    nt._measure_buffer = []

    nt.update_from_decoded(MIKE_20_VALUES)
    captured = capsys.readouterr()
    assert "[DT-DBG]" not in captured.out, \
        f"Debug-Zeile sollte NICHT erscheinen, captured: {captured.out!r}"
