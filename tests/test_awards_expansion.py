"""Tests fuer die Diplome-Erweiterung (v0.98.53): WAE, WPX, DXCC-Band-Tiefe
(Challenge + 5-Band-DXCC) und die Sichtbarkeits-Persistenz (core/awards_prefs).

WPX-Slash-Logik ist gegen echte Calls aus dem QRZ-Export validiert
(OE/DL6CGU -> OE0, N1UL/3 -> N3, F5OYA/P -> F5) — genau die Faelle, bei denen
ein naiver "erster ziffernhaltiger Teil"-Ansatz scheitern wuerde.
"""

import json

import pytest

from core.awards import (
    compute_awards,
    wpx_prefix,
    five_band_status,
    AWARD_ORDER,
    AWARD_INFO,
    WAE_GOAL,
    WPX_GOAL,
    CHALLENGE_BANDS,
    FIVE_BAND_BANDS,
    FIVE_BAND_GOAL,
)
import core.awards_prefs as awards_prefs


def _rec(**kw):
    """ADIF-Record mit GROSS-Keys (wie der QRZ-Parser sie liefert)."""
    return {k.upper(): v for k, v in kw.items()}


# ============================================================ WPX-Praefix-Parser

def test_wpx_normal_calls():
    assert wpx_prefix("DA1MHH") == "DA1"
    assert wpx_prefix("9A7W") == "9A7"
    assert wpx_prefix("K5ZD") == "K5"
    assert wpx_prefix("2E0ABC") == "2E0"
    assert wpx_prefix("OH8X") == "OH8"
    assert wpx_prefix("UN9FF") == "UN9"


def test_wpx_lowercase_and_brackets():
    assert wpx_prefix("da1mhh") == "DA1"
    assert wpx_prefix("<DA1MHH>") == "DA1"
    assert wpx_prefix("  9a7w  ") == "9A7"


def test_wpx_mobile_suffix_stripped():
    assert wpx_prefix("F5OYA/P") == "F5"
    assert wpx_prefix("S51PV/QRP") == "S51"
    assert wpx_prefix("YO4RYU/MM") == "YO4"
    assert wpx_prefix("UR5ZEP/A") == "UR5"
    assert wpx_prefix("DL9ZAL/QRPP") == "DL9"


def test_wpx_prefix_slash_location_in_front():
    # Standort-Praefix vorn; ohne Ziffer -> WPX-Regel "0" anhaengen.
    assert wpx_prefix("OE/DL6CGU") == "OE0"
    assert wpx_prefix("EK/RX3DPK") == "EK0"
    assert wpx_prefix("UN/OH7O") == "UN0"
    # Standort-Praefix mit Ziffer bleibt wie er ist.
    assert wpx_prefix("SV9/DL1MTB") == "SV9"
    assert wpx_prefix("IK3/UY7LA") == "IK3"
    assert wpx_prefix("TC0/YO5OED") == "TC0"
    assert wpx_prefix("YS3/PY8WW") == "YS3"


def test_wpx_region_digit_override():
    assert wpx_prefix("N1UL/3") == "N3"
    assert wpx_prefix("N1UL/2") == "N2"
    assert wpx_prefix("RA0QK/8") == "RA8"
    assert wpx_prefix("UA3UBV/1") == "UA1"


def test_wpx_invalid_inputs():
    assert wpx_prefix("") is None
    assert wpx_prefix(None) is None
    assert wpx_prefix("/") is None
    assert wpx_prefix("/P") is None


def test_wpx_tolerates_spaces_around_slash():
    # Defensive Haertung (Final-R1 🟡): Leerzeichen um den Slash nicht verlieren.
    assert wpx_prefix("DA1MHH /P") == "DA1"
    assert wpx_prefix("OE / DL6CGU") == "OE0"


def test_wpx_in_compute_awards_dedups():
    recs = [
        _rec(CALL="DA1MHH", LOTW_QSL_RCVD="Y"),
        _rec(CALL="DA1XYZ", LOTW_QSL_RCVD="N"),   # auch DA1 -> Praefix dedupliziert
        _rec(CALL="9A7W", LOTW_QSL_RCVD="Y"),
        _rec(CALL="OE/DL6CGU"),                    # -> OE0
    ]
    wpx = compute_awards(recs)["WPX"]
    assert wpx["worked"] == {"DA1", "9A7", "OE0"}
    assert wpx["confirmed"] == {"DA1", "9A7"}
    assert wpx["goal"] == WPX_GOAL


# ===================================================================== WAE (Europa)

def test_wae_counts_only_european_dxcc():
    recs = [
        _rec(DXCC="230", CONT="EU", LOTW_QSL_RCVD="Y"),   # DE  -> zaehlt
        _rec(DXCC="263", CONT="EU", LOTW_QSL_RCVD="N"),   # NL  -> zaehlt (nicht best.)
        _rec(DXCC="291", CONT="NA", LOTW_QSL_RCVD="Y"),   # USA -> NICHT EU
        _rec(DXCC="339", CONT="AS", LOTW_QSL_RCVD="Y"),   # JP  -> NICHT EU
        _rec(DXCC="230", CONT="EU", LOTW_QSL_RCVD="Y"),   # DE nochmal -> dedupliziert
    ]
    wae = compute_awards(recs)["WAE"]
    assert wae["worked"] == {230, 263}
    assert wae["confirmed"] == {230}
    assert wae["goal"] == WAE_GOAL


def test_wae_ignores_eu_without_dxcc():
    # CONT=EU aber keine DXCC-Nummer -> kann nicht gezaehlt werden.
    recs = [_rec(CONT="EU", LOTW_QSL_RCVD="Y")]
    assert compute_awards(recs)["WAE"]["worked"] == set()


# ======================================================== DXCC Challenge / 5-Band

def test_dxcc_challenge_counts_entity_band_slots():
    recs = [
        _rec(DXCC="230", BAND="20M"),
        _rec(DXCC="230", BAND="40M"),   # gleiches Land, anderes Band -> 2. Slot
        _rec(DXCC="230", BAND="20M"),   # Duplikat -> kein neuer Slot
        _rec(DXCC="291", BAND="20M"),
    ]
    challenge = compute_awards(recs)["DXCC"]["challenge"]
    assert challenge == {(230, "20M"), (230, "40M"), (291, "20M")}


def test_dxcc_challenge_excludes_non_hf_bands():
    # 60 m und 2 m zaehlen NICHT fuer DXCC Challenge.
    recs = [
        _rec(DXCC="230", BAND="60M"),
        _rec(DXCC="230", BAND="2M"),
        _rec(DXCC="230", BAND="20M"),
    ]
    challenge = compute_awards(recs)["DXCC"]["challenge"]
    assert challenge == {(230, "20M")}
    assert "60M" not in CHALLENGE_BANDS
    assert "2M" not in CHALLENGE_BANDS


def test_dxcc_band_case_insensitive():
    # Band-Casing im Export ist gemischt ("20m" / "20M").
    recs = [_rec(DXCC="230", BAND="20m"), _rec(DXCC="291", BAND="20M")]
    challenge = compute_awards(recs)["DXCC"]["challenge"]
    assert challenge == {(230, "20M"), (291, "20M")}


def test_five_band_buckets_and_status():
    recs = []
    # 80m: 100 Entities -> erreicht; 20m: 3 Entities -> nicht erreicht
    for e in range(1, 101):
        recs.append(_rec(DXCC=str(e), BAND="80M"))
    for e in range(1, 4):
        recs.append(_rec(DXCC=str(e), BAND="20M"))
    five = compute_awards(recs)["DXCC"]["five_band"]
    assert len(five["80M"]) == 100
    assert len(five["20M"]) == 3
    status = dict((b, (n, r)) for b, n, r in five_band_status(five))
    assert status["80M"] == (100, True)
    assert status["20M"] == (3, False)
    assert status["40M"] == (0, False)   # nie gearbeitet
    assert FIVE_BAND_GOAL == 100
    assert FIVE_BAND_BANDS == ("80M", "40M", "20M", "15M", "10M")


# ============================================================ Award-Reihenfolge/Info

def test_award_order_includes_new_awards():
    assert AWARD_ORDER == ("DXCC", "WAE", "WPX", "WAC", "WAS", "WAZ")
    for key in AWARD_ORDER:
        assert key in AWARD_INFO and AWARD_INFO[key]


def test_wae_info_is_honest_about_approximation():
    # Ehrlichkeits-Regel: WAE-Tooltip muss als Naeherung gekennzeichnet sein.
    info = AWARD_INFO["WAE"].lower()
    assert "naeherung" in info or "näherung" in info


# ===================================================== Sichtbarkeits-Persistenz

def test_awards_prefs_default_empty(tmp_path, monkeypatch):
    monkeypatch.setattr(awards_prefs, "_FILE", tmp_path / "vis.json")
    assert awards_prefs.load_hidden() == set()


def test_awards_prefs_roundtrip(tmp_path, monkeypatch):
    f = tmp_path / "vis.json"
    monkeypatch.setattr(awards_prefs, "_FILE", f)
    awards_prefs.save_hidden({"WAC", "WAS"})
    assert awards_prefs.load_hidden() == {"WAC", "WAS"}
    # Ueberschreiben mit weniger
    awards_prefs.save_hidden({"WAC"})
    assert awards_prefs.load_hidden() == {"WAC"}
    # Leeren
    awards_prefs.save_hidden(set())
    assert awards_prefs.load_hidden() == set()


def test_awards_prefs_corrupt_file_is_safe(tmp_path, monkeypatch):
    f = tmp_path / "vis.json"
    monkeypatch.setattr(awards_prefs, "_FILE", f)
    f.write_text("{ not valid json")
    assert awards_prefs.load_hidden() == set()
    # auch falscher Typ (dict statt list) -> leer
    f.write_text(json.dumps({"a": 1}))
    assert awards_prefs.load_hidden() == set()


def test_awards_prefs_save_creates_dir(tmp_path, monkeypatch):
    nested = tmp_path / "sub" / "dir" / "vis.json"
    monkeypatch.setattr(awards_prefs, "_FILE", nested)
    awards_prefs.save_hidden({"DXCC"})
    assert nested.exists()
    assert awards_prefs.load_hidden() == {"DXCC"}


# ===================================================== AwardsDialog (GUI-Smoke)

@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def _sample_records():
    return [
        _rec(CALL="DA1MHH", DXCC="230", CONT="EU", CQZ="14", BAND="20M",
             LOTW_QSL_RCVD="Y"),
        _rec(CALL="K5ZD", DXCC="291", CONT="NA", CQZ="5", STATE="MA", BAND="40M",
             LOTW_QSL_RCVD="Y"),
        _rec(CALL="JA1XYZ", DXCC="339", CONT="AS", CQZ="25", BAND="15M"),
    ]


def test_dialog_builds_all_cards(qapp, tmp_path, monkeypatch):
    monkeypatch.setattr(awards_prefs, "_FILE", tmp_path / "vis.json")
    from ui.awards_dialog import AwardsDialog
    dlg = AwardsDialog(_sample_records())
    # Alle sechs Karten existieren und sind initial sichtbar.
    assert set(dlg._cards.keys()) == set(AWARD_ORDER)
    for key in AWARD_ORDER:
        assert dlg._cards[key].isVisibleTo(dlg)
    dlg.deleteLater()


def test_dialog_hide_persists_and_hides_card(qapp, tmp_path, monkeypatch):
    monkeypatch.setattr(awards_prefs, "_FILE", tmp_path / "vis.json")
    from ui.awards_dialog import AwardsDialog
    dlg = AwardsDialog(_sample_records())
    dlg._hide_award("WAS")
    assert not dlg._cards["WAS"].isVisibleTo(dlg)
    # persistiert
    assert awards_prefs.load_hidden() == {"WAS"}
    # ein frisch geoeffneter Dialog uebernimmt den Zustand
    dlg2 = AwardsDialog(_sample_records())
    assert "WAS" in dlg2._hidden
    assert not dlg2._cards["WAS"].isVisibleTo(dlg2)
    dlg.deleteLater()
    dlg2.deleteLater()


def test_dialog_show_again_restores_card(qapp, tmp_path, monkeypatch):
    monkeypatch.setattr(awards_prefs, "_FILE", tmp_path / "vis.json")
    from ui.awards_dialog import AwardsDialog
    dlg = AwardsDialog(_sample_records())
    dlg._hide_award("WPX")
    assert not dlg._cards["WPX"].isVisibleTo(dlg)
    dlg._show_award("WPX")
    assert dlg._cards["WPX"].isVisibleTo(dlg)
    assert awards_prefs.load_hidden() == set()
    dlg.deleteLater()
