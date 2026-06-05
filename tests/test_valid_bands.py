"""OPT-64: `_valid_bands(raw)` — gemeinsamer Band-Validierungs-Helfer für
`get_enabled_bands` + `set_enabled_bands` (config/settings.py, DRY/K4).

Filtert auf Strings die in BAND_FREQUENCIES sind, dedupliziert (Reihenfolge des
ersten Auftretens erhalten). Bei nicht-Liste ODER leerem Ergebnis → Default
(alle Bänder). Verhaltensgleich zu den beiden vorherigen Inline-Blöcken.
"""
from config.settings import _valid_bands, BAND_FREQUENCIES

ALL = list(BAND_FREQUENCIES.keys())


# ── nicht-Liste / leer / nur-Garbage → Default ────────────────────────

def test_none_returns_default():
    assert _valid_bands(None) == ALL


def test_non_list_returns_default():
    # String / int sind keine Liste → Default (Variante A: kein Crash)
    assert _valid_bands("20m") == ALL
    assert _valid_bands(42) == ALL


def test_empty_list_returns_default():
    assert _valid_bands([]) == ALL


def test_only_garbage_returns_default():
    # Liste MIT Garbage-Elementen (kein str / nicht in BAND_FREQUENCIES)
    assert _valid_bands(["junk", None, 42, "999m"]) == ALL


# ── gültige Eingaben ──────────────────────────────────────────────────

def test_valid_subset_preserves_order():
    # Reihenfolge des ersten Auftretens erhalten (NICHT nach BAND_FREQUENCIES sortiert)
    assert _valid_bands(["10m", "80m", "20m"]) == ["10m", "80m", "20m"]


def test_dedup_keeps_first_occurrence():
    assert _valid_bands(["20m", "40m", "20m", "40m"]) == ["20m", "40m"]


def test_mixed_valid_and_garbage_filters_garbage():
    assert _valid_bands(["20m", "junk", None, "40m", 7]) == ["20m", "40m"]


def test_all_bands_roundtrip():
    assert _valid_bands(ALL) == ALL

# Die Integration get_/set_enabled_bands → echtes Settings-Objekt deckt
# test_p50_bands_visibility.py ab (T1-T3, T11 etc.) — hier nur die reine Funktion.
