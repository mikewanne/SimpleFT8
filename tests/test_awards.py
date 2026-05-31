"""Tests fuer core/awards.py — Diplome-Berechnung (DXCC/WAC/WAS/WAZ).

Deckt ab: distinct-Zaehlung, LoTW-Bestaetigungs-Filter, US-State-Validierung
(AK/HI rein, Ausland/N/A raus), CQ-Zonen-Range, AN nicht in WAC, '01'-vs-'1'-
Normalisierung, robuste Behandlung fehlender/leerer Felder, DXCC-Marken-Staffel.
"""

from core.awards import (
    compute_awards,
    dxcc_tier_status,
    US_STATES,
    WAC_CONTINENTS,
    DXCC_TIERS,
    DXCC_HONOR_ROLL,
)


def _rec(**kw):
    """Mini-Helper: ADIF-Record mit GROSS-Keys."""
    return {k.upper(): v for k, v in kw.items()}


# ---------------------------------------------------------------- Grundzaehlung

def test_dxcc_distinct_worked_and_confirmed():
    recs = [
        _rec(DXCC="230", LOTW_QSL_RCVD="Y"),   # DE bestaetigt
        _rec(DXCC="230", LOTW_QSL_RCVD="N"),   # DE nochmal, nicht best.
        _rec(DXCC="291", LOTW_QSL_RCVD="Y"),   # USA bestaetigt
        _rec(DXCC="291"),                       # USA nochmal, kein LoTW-Feld
        _rec(DXCC="14"),                        # nicht bestaetigt
    ]
    a = compute_awards(recs)["DXCC"]
    assert a["worked"] == {230, 291, 14}
    assert a["confirmed"] == {230, 291}
    assert a["goal"] == 100


def test_confirmed_is_subset_of_worked():
    recs = [_rec(DXCC="100", LOTW_QSL_RCVD="Y"), _rec(CONT="EU", LOTW_QSL_RCVD="Y")]
    res = compute_awards(recs)
    for a in res.values():
        assert a["confirmed"] <= a["worked"]


def test_only_lotw_y_counts_as_confirmed():
    # APP_QRZLOG_STATUS=C darf NICHT als bestaetigt zaehlen.
    recs = [
        _rec(DXCC="230", APP_QRZLOG_STATUS="C"),
        _rec(DXCC="291", LOTW_QSL_RCVD="N"),
        _rec(DXCC="1", LOTW_QSL_RCVD="y"),   # klein-y toleriert
    ]
    a = compute_awards(recs)["DXCC"]
    assert a["worked"] == {230, 291, 1}
    assert a["confirmed"] == {1}


# ------------------------------------------------------------------------- WAC

def test_wac_six_continents_antarctica_excluded():
    recs = [
        _rec(CONT="EU"), _rec(CONT="NA"), _rec(CONT="SA"),
        _rec(CONT="AF"), _rec(CONT="AS"), _rec(CONT="OC"),
        _rec(CONT="AN"),       # Antarktis zaehlt NICHT fuer WAC
        _rec(CONT="eu"),       # Gross/Klein
        _rec(CONT=""),         # leer
    ]
    a = compute_awards(recs)["WAC"]
    assert a["worked"] == WAC_CONTINENTS
    assert "AN" not in a["worked"]
    assert len(a["worked"]) == 6


# ------------------------------------------------------------------------- WAS

def test_was_only_valid_us_states():
    recs = [
        _rec(STATE="CA"), _rec(STATE="NY"),
        _rec(STATE="AK"), _rec(STATE="HI"),   # eigene DXCC, aber WAS-States
        _rec(STATE="N/A"),                     # Muell
        _rec(STATE="ON"),                      # kanadische Provinz -> raus
        _rec(STATE=""), _rec(),                # leer / fehlend
        _rec(STATE="ca"),                      # Gross/Klein
    ]
    a = compute_awards(recs)["WAS"]
    assert a["worked"] == {"CA", "NY", "AK", "HI"}
    assert a["goal"] == 50


def test_all_us_states_present_in_constant():
    assert len(US_STATES) == 50


# ------------------------------------------------------------------------- WAZ

def test_waz_zone_range_and_normalization():
    recs = [
        _rec(CQZ="14"), _rec(CQZ="14"),    # Duplikat
        _rec(CQZ="01"), _rec(CQZ="1"),     # '01' und '1' -> eine Zone
        _rec(CQZ="40"),                    # Grenze ok
        _rec(CQZ="41"),                    # ausserhalb -> raus
        _rec(CQZ="0"),                     # ungueltig
        _rec(CQZ=""), _rec(),              # leer / fehlend
    ]
    a = compute_awards(recs)["WAZ"]
    assert a["worked"] == {14, 1, 40}
    assert a["goal"] == 40


# ---------------------------------------------------------- Robustheit / leer

def test_empty_input():
    res = compute_awards([])
    for key in ("DXCC", "WAC", "WAS", "WAZ"):
        assert res[key]["worked"] == set()
        assert res[key]["confirmed"] == set()


def test_non_dict_records_ignored():
    res = compute_awards([None, "x", 42, _rec(DXCC="230")])
    assert res["DXCC"]["worked"] == {230}


def test_missing_and_garbage_fields_robust():
    recs = [
        _rec(DXCC="abc"), _rec(DXCC="-5"), _rec(DXCC=" "),
        _rec(CQZ="xx"), _rec(STATE=123),
    ]
    res = compute_awards(recs)
    assert res["DXCC"]["worked"] == set()
    assert res["WAZ"]["worked"] == set()
    assert res["WAS"]["worked"] == set()


# ----------------------------------------------------------- DXCC-Staffelung

def test_dxcc_tier_status_below_basic():
    cur, nxt = dxcc_tier_status(73)
    assert cur is None
    assert nxt == 100


def test_dxcc_tier_status_mid():
    cur, nxt = dxcc_tier_status(210)
    assert cur == 200
    assert nxt == 250


def test_dxcc_tier_status_exact_marker():
    cur, nxt = dxcc_tier_status(300)
    assert cur == 300
    assert nxt == "Honor Roll"


def test_dxcc_tier_status_honor_roll():
    cur, nxt = dxcc_tier_status(335)
    assert cur == "Honor Roll"
    assert nxt is None


def test_dxcc_tiers_constant_sorted():
    assert list(DXCC_TIERS) == sorted(DXCC_TIERS)
    assert DXCC_TIERS[0] == 100
    assert DXCC_HONOR_ROLL > DXCC_TIERS[-1]


# --------------------------------------------------- Mehrfach-Felder / Real

def test_combined_pool_dedupes_across_calls():
    # Simuliert DA1MHH + DO4MHH: dieselbe Entity unter beiden Calls -> 1x.
    recs = [
        _rec(CALL="W1AW", DXCC="291", STATION_CALLSIGN="DA1MHH"),
        _rec(CALL="K1XX", DXCC="291", STATION_CALLSIGN="DO4MHH"),
    ]
    a = compute_awards(recs)["DXCC"]
    assert a["worked"] == {291}
