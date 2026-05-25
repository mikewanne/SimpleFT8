"""P1.19/P1.21/P120: compute_local_conditions Logik-Tests.

P120 (25.05.2026) — FT8-realistische Schwellen (R1-Option-B):
  5 ★: median > -13 dB | 4 ★: > -18 | 3 ★: > -21 | 2 ★: > -22 | 1 ★: sonst

Alte Schwellen waren aus SSB/CW-Denke (-10/-14/-18/-22). FT8-Decoder
läuft bis ~-24 dB, Stationen >-10 dB sind außergewöhnlich stark.
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
    """P120: Median > -13 dB → 5 Sterne (sehr gut, selten)."""
    from ui.mw_cycle import compute_local_conditions
    stations = {f"call{i}": _Station(-8) for i in range(10)}
    score, n, median = compute_local_conditions(stations)
    assert score == 5
    assert median == -8.0


def test_local_conditions_4_stars():
    """P120: Median bei -14 dB → 4 Sterne (>-18, nicht >-13).

    Alte Schwelle: -14 wäre 4★ (>-14) → 3★ (>-18). Mike's Field-Beobachtung
    25.05.: -17 muss 4★ sein → 4★-Schwelle ist jetzt > -18.
    """
    from ui.mw_cycle import compute_local_conditions
    stations = {f"call{i}": _Station(-14) for i in range(10)}
    score, _, _ = compute_local_conditions(stations)
    assert score == 4


def test_local_conditions_3_stars():
    """P120: Median bei -19 dB → 3 Sterne (>-21, nicht >-18)."""
    from ui.mw_cycle import compute_local_conditions
    stations = {f"call{i}": _Station(-19) for i in range(10)}
    score, _, _ = compute_local_conditions(stations)
    assert score == 3


def test_local_conditions_2_stars_weak():
    """P120: Median bei -21.5 dB → 2 Sterne (>-22, nicht >-21).

    2★-Range ist schmal (zwischen -21 exklusiv und -22 inklusiv) — bewusst
    so, weil FT8-SNR meist ganzzahlig ist und -22 dB die Decoder-Grenze
    markiert. R1-Hinweis: schmal aber akzeptabel.
    """
    from ui.mw_cycle import compute_local_conditions
    stations = {f"call{i}": _Station(-21.5) for i in range(10)}
    score, _, _ = compute_local_conditions(stations)
    assert score == 2


def test_local_conditions_1_star_very_weak():
    """Median bei -25 dB → 1 Stern (Decoder-Grenze unterschritten)."""
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


# ---------------------------------------------------------------------------
# P120 — neue Tests (Mike-Field-Test + Grenzfälle)
# ---------------------------------------------------------------------------


def test_p120_mike_field_test_minus17_is_4_stars():
    """P120 (25.05.2026): Mike's Field-Beobachtung — 15m FT8 Median -17 dB
    muss 4★ ergeben (war vorher 3★ mit alter Schwelle >-18).

    Mike-Worte: „-17 dB ist in FT8 ein normal-guter Pegel". Mit neuer
    4★-Schwelle >-18 erfüllt sich Mike's Intent (-17 > -18 = True → 4★).
    """
    from ui.mw_cycle import compute_local_conditions
    stations = {f"call{i}": _Station(-17) for i in range(10)}
    score, n, median = compute_local_conditions(stations)
    assert score == 4, f"Mike-Field -17 dB muss 4★ ergeben, war {score}★"
    assert median == -17.0


def test_p120_threshold_boundary_5_to_4():
    """P120: Grenze 5★/4★ bei -13 dB.

    -13 > -13 = False → fällt auf 4★. -12.5 > -13 = True → 5★.
    """
    from ui.mw_cycle import compute_local_conditions
    # Genau -13: fällt durch 5★-Schwelle, landet bei 4★
    stations_at_threshold = {f"call{i}": _Station(-13) for i in range(10)}
    score, _, _ = compute_local_conditions(stations_at_threshold)
    assert score == 4, "-13 dB ist NICHT > -13 → 4★"
    # Knapp drüber: 5★
    stations_above = {f"call{i}": _Station(-12.5) for i in range(10)}
    score, _, _ = compute_local_conditions(stations_above)
    assert score == 5


def test_p120_threshold_boundary_4_to_3():
    """P120: Grenze 4★/3★ bei -18 dB."""
    from ui.mw_cycle import compute_local_conditions
    stations_at = {f"call{i}": _Station(-18) for i in range(10)}
    score, _, _ = compute_local_conditions(stations_at)
    assert score == 3, "-18 dB ist NICHT > -18 → 3★"


def test_p120_threshold_boundary_3_to_2():
    """P120: Grenze 3★/2★ bei -21 dB."""
    from ui.mw_cycle import compute_local_conditions
    stations_at = {f"call{i}": _Station(-21) for i in range(10)}
    score, _, _ = compute_local_conditions(stations_at)
    assert score == 2, "-21 dB ist NICHT > -21 → 2★"


def test_p120_threshold_boundary_2_to_1():
    """P120: Grenze 2★/1★ bei -22 dB (Decoder-Grenze)."""
    from ui.mw_cycle import compute_local_conditions
    stations_at = {f"call{i}": _Station(-22) for i in range(10)}
    score, _, _ = compute_local_conditions(stations_at)
    assert score == 1, "-22 dB ist NICHT > -22 → 1★"
