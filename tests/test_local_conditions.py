"""P1.19: compute_local_conditions Logik-Tests."""


class _Station:
    def __init__(self, snr):
        self.snr = snr


def test_local_conditions_empty_dict():
    from ui.mw_cycle import compute_local_conditions
    score, n, median = compute_local_conditions({})
    assert score == 1
    assert n == 0
    assert median == -99.0


def test_local_conditions_31_stations_strong():
    from ui.mw_cycle import compute_local_conditions
    stations = {f"call{i}": _Station(-10) for i in range(31)}
    score, n, _ = compute_local_conditions(stations)
    assert score == 5
    assert n == 31


def test_local_conditions_2_stations_weak():
    from ui.mw_cycle import compute_local_conditions
    stations = {f"call{i}": _Station(-25) for i in range(2)}
    score, n, _ = compute_local_conditions(stations)
    assert score == 1
    assert n == 2


def test_local_conditions_8_stations_borderline():
    from ui.mw_cycle import compute_local_conditions
    stations = {f"call{i}": _Station(-19) for i in range(8)}
    score, n, _ = compute_local_conditions(stations)
    assert score == 3  # n >= 8 trigger
    assert n == 8


def test_local_conditions_no_snr_attr():
    from ui.mw_cycle import compute_local_conditions

    class NoSNR:
        pass

    stations = {f"call{i}": NoSNR() for i in range(5)}
    score, n, _ = compute_local_conditions(stations)
    assert score == 1
    assert n == 0
