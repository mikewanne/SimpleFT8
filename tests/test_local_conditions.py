"""P1.19/P1.21: compute_local_conditions Logik-Tests.

Score-Algorithmus rein SNR-basiert (Mike-Funker-Logik):
  5 ★: median > -10 dB    | 4 ★: > -14 | 3 ★: > -18 | 2 ★: > -22 | 1 ★: sonst
"""


class _Station:
    def __init__(self, snr):
        self.snr = snr


def test_local_conditions_empty_dict():
    from ui.mw_cycle import compute_local_conditions
    score, n, median = compute_local_conditions({})
    assert score == 1
    assert n == 0
    assert median == -99.0


def test_local_conditions_no_snr_attr():
    from ui.mw_cycle import compute_local_conditions

    class NoSNR:
        pass

    stations = {f"call{i}": NoSNR() for i in range(5)}
    score, n, _ = compute_local_conditions(stations)
    assert score == 1
    assert n == 0


def test_local_conditions_5_stars_strong_snr():
    """Median > -10 dB → 5 Sterne, unabhaengig von Stationsanzahl."""
    from ui.mw_cycle import compute_local_conditions
    stations = {f"call{i}": _Station(-8) for i in range(10)}
    score, n, median = compute_local_conditions(stations)
    assert score == 5
    assert median == -8.0


def test_local_conditions_4_stars():
    """Median bei -12 dB → 4 Sterne (>-14, nicht >-10)."""
    from ui.mw_cycle import compute_local_conditions
    stations = {f"call{i}": _Station(-12) for i in range(10)}
    score, _, _ = compute_local_conditions(stations)
    assert score == 4


def test_local_conditions_3_stars():
    """Median bei -16 dB → 3 Sterne."""
    from ui.mw_cycle import compute_local_conditions
    stations = {f"call{i}": _Station(-16) for i in range(10)}
    score, _, _ = compute_local_conditions(stations)
    assert score == 3


def test_local_conditions_2_stars_weak():
    """Median bei -20 dB → 2 Sterne."""
    from ui.mw_cycle import compute_local_conditions
    stations = {f"call{i}": _Station(-20) for i in range(10)}
    score, _, _ = compute_local_conditions(stations)
    assert score == 2


def test_local_conditions_1_star_very_weak():
    """Median bei -25 dB → 1 Stern."""
    from ui.mw_cycle import compute_local_conditions
    stations = {f"call{i}": _Station(-25) for i in range(2)}
    score, n, _ = compute_local_conditions(stations)
    assert score == 1
    assert n == 2


def test_local_conditions_mike_field_test_48_stations_weak():
    """Mike-Befund 06.05. 02:28 UTC: 48 Stationen alle bei -25 dB
    duerfen NICHT 5 Sterne ergeben (war P1.21-Bug mit `or`)."""
    from ui.mw_cycle import compute_local_conditions
    stations = {f"call{i}": _Station(-25) for i in range(48)}
    score, n, _ = compute_local_conditions(stations)
    assert score == 1, "48 Stationen × -25 dB → 1 Stern (nicht 5)"
    assert n == 48
