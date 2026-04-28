"""Tests fuer v0.74 Diversity-Bandwechsel-Bug-Fix.

Bug: Bei Bandwechsel mit aktiver Diversity wurde Ratio aus 2h-Cache
geladen — physikalisch falsch da Pattern band-spezifisch ist.

Fix: Ratio wird IMMER neu eingemessen. Gain bleibt gecacht (Hardware-
Eigenschaft des RX-Verstaerkers).

Tests:
- T_token_pattern: Race-Token-Logik (Lambda-Closure korrekt invalidiert)
- T_phase_diff: measure→operate Uebergang erkannt fuer GUI-Lock
- T_load_preset_removed: Regression-Schutz, load_preset() bleibt geloescht
"""

import pytest


def test_token_pattern_invalidates_old_callback():
    """Token-Pattern: Closure haelt _local_token; wenn obj._tune_token
    waehrend Lifetime auf None gesetzt wird, ist _local_token nicht mehr
    gleich obj._tune_token → Callback wird ignoriert.
    """
    class FakeMain:
        _tune_token = None

    obj = FakeMain()
    obj._tune_token = object()
    _local_token = obj._tune_token

    # Token gleich → Callback laeuft
    assert getattr(obj, '_tune_token', None) is _local_token

    # Bandwechsel-Simulation: Token wird genullt
    obj._tune_token = None
    assert getattr(obj, '_tune_token', None) is not _local_token

    # Bandwechsel mit neuem TUNE: neues Token, alter _local_token wird nie gleich
    obj._tune_token = object()
    assert getattr(obj, '_tune_token', None) is not _local_token


def test_phase_diff_detects_measure_to_operate_transition():
    """Phase-Diff in mw_cycle.py: erkennt measure→operate Uebergang.

    Reproduziert die Logik die in _handle_diversity_measure GUI-Lock loest.
    """
    from core.diversity import DiversityController
    dc = DiversityController()
    dc._phase = "measure"

    # 7 Messungen — bleibt measure
    for i in range(7):
        old_phase = dc.phase
        dc.record_measurement("A1" if i % 2 == 0 else "A2",
                              score=0.0, station_count=10)
        new_phase = dc.phase
        # Phase-Diff: kein Uebergang
        assert not (old_phase == "measure" and new_phase == "operate")

    # 8. Messung → Uebergang triggert
    old_phase = dc.phase
    dc.record_measurement("A2", score=0.0, station_count=10)
    new_phase = dc.phase
    assert old_phase == "measure"
    assert new_phase == "operate"
    # Phase-Diff erkennt Uebergang → GUI-Lock-Aufhebung wuerde getriggert
    assert old_phase == "measure" and new_phase == "operate"


def test_load_preset_removed_from_diversity_controller():
    """Regression: load_preset() darf nicht zurueckkommen.

    Wenn der Code zurueckkommt, lassen wir auch versehentlich den Bug-Pfad
    zurueck. Test dokumentiert diese bewusste Loesch-Entscheidung.
    """
    from core.diversity import DiversityController
    dc = DiversityController()
    assert not hasattr(dc, 'load_preset'), (
        "load_preset() wurde in v0.74 bewusst entfernt — Ratio darf NIE "
        "aus Cache geladen werden, weil Pattern band-spezifisch ist. "
        "Wenn diese Methode zurueckkommt, kommt auch der Bug zurueck."
    )


def test_reset_phase_is_measure_not_operate():
    """reset() setzt Phase=measure (Voraussetzung fuer Re-Measurement-Pfad)."""
    from core.diversity import DiversityController
    dc = DiversityController()
    dc._phase = "operate"  # Simuliere laufenden Betrieb
    dc.ratio = "30:70"
    dc.dominant = "A2"

    dc.reset()

    assert dc.phase == "measure"
    assert dc.ratio == "50:50"  # Default fuer neue Messung
    assert dc.dominant is None
    assert dc._measure_step == 0
    assert dc._measurements == {"A1": [], "A2": []}


def test_on_band_change_triggers_full_reset():
    """on_band_change() — bei Bandwechsel: Re-Measurement-Pfad startbereit."""
    from core.diversity import DiversityController
    dc = DiversityController()

    # Simuliere laufenden Betrieb auf altem Band
    dc._phase = "operate"
    dc.ratio = "30:70"
    dc.dominant = "A2"
    dc._operate_cycles = 42

    dc.on_band_change()

    # Nach Bandwechsel: bereit fuer Neueinmessung
    assert dc.phase == "measure"
    assert dc.ratio == "50:50"
    assert dc.dominant is None
    assert dc._operate_cycles == 0
