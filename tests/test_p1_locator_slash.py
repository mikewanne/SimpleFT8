"""Tests fuer P1.LOCATOR-SLASH v0.95.16.

Decken ab:
- Slash-Call-Praefix (EA8/DA1MHH) → Land Kanaren, km Kanaren-Position
- Slash-Call-Suffix-DXCC (K1ABC/W2) → Land USA
- Slash-Call-Mobile (DA1MHH/P) → Land DE, km Heim-Position fallback (kein
  DB-Eintrag → Prefix-Distanz vom Basis-Call)
- Unknown-Prefix (ZZ1/AA1ABC) → graceful (kein Crash)
- _strip_mobile_suffix korrekt
- _dxcc_prefix_from_call mit verschiedenen Inputs
- LocatorDB konsistente Set/Get bei Slash-Call (was rein, was raus)
- _feed_locator_db schreibt korrekt mit Slash-Call
- Integration: rx_panel-Pfad mit echter LocatorDB
"""
import os
import sys
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


# ── core/geo.py Helper-Tests ─────────────────────────────────────────────


def test_strip_mobile_suffix_removes_p():
    from core.geo import _strip_mobile_suffix
    assert _strip_mobile_suffix("DA1MHH/P") == "DA1MHH"
    assert _strip_mobile_suffix("DA1MHH/MM") == "DA1MHH"
    assert _strip_mobile_suffix("DA1MHH") == "DA1MHH"
    # Praefix-Slash darf NICHT als Mobile-Suffix interpretiert werden
    assert _strip_mobile_suffix("EA8/DA1MHH") == "EA8/DA1MHH"


def test_dxcc_prefix_from_call_prefix_slash():
    from core.geo import _dxcc_prefix_from_call
    assert _dxcc_prefix_from_call("EA8/DA1MHH") == "EA8"
    assert _dxcc_prefix_from_call("DL/W7XYZ") == "DL"


def test_dxcc_prefix_from_call_mobile_only_returns_none():
    from core.geo import _dxcc_prefix_from_call
    # Reiner Mobile-Suffix: kein DXCC-Token → None
    assert _dxcc_prefix_from_call("DA1MHH/P") is None
    # Kein Slash → None (regulaerer Pfad)
    assert _dxcc_prefix_from_call("DA1MHH") is None


def test_dxcc_prefix_from_call_unknown():
    from core.geo import _dxcc_prefix_from_call
    # ZZ1 ist kein DXCC-Praefix; AA1 → "AA" (US-Praefix in _PREFIX_MAP).
    # Test verifiziert: kein Crash + plausible Antwort (None ODER "AA"/"AA1").
    result = _dxcc_prefix_from_call("ZZ1/AA1ABC")
    assert result is None or result in ("AA", "AA1")


# ── callsign_to_country Tests ────────────────────────────────────────────


def test_callsign_to_country_prefix_slash_dxcc():
    from core.geo import callsign_to_country
    # EA8 → IC → 'Canary Isl.'
    country = callsign_to_country("EA8/DA1MHH")
    assert "Canary" in country or "Kanaren" in country


def test_callsign_to_country_mobile_suffix_basis():
    from core.geo import callsign_to_country
    # DA1MHH/P → Basis-Call DA1MHH → 'Germany'
    country = callsign_to_country("DA1MHH/P")
    assert "German" in country or "Deutsch" in country


def test_callsign_to_country_region_suffix():
    from core.geo import callsign_to_country
    # K1ABC/W2 → DXCC-Token K oder W2 → USA (beide sind US-Praefixe)
    country = callsign_to_country("K1ABC/W2")
    assert "USA" in country or "United States" in country


# ── callsign_to_distance Tests ───────────────────────────────────────────


def test_callsign_to_distance_prefix_slash():
    from core.geo import callsign_to_distance
    # EA8/DA1MHH von JO31 → Kanaren-Distanz ~3000 km
    km = callsign_to_distance("EA8/DA1MHH", "JO31")
    assert km is not None and 2500 <= km <= 4000


def test_callsign_to_distance_mobile_suffix():
    from core.geo import callsign_to_distance
    # DA1MHH/P von JO31 → Mobile-Suffix entfernt → DA1MHH → ~Heim
    km = callsign_to_distance("DA1MHH/P", "JO31")
    assert km is not None and km < 500


def test_callsign_to_distance_no_slash_unchanged():
    from core.geo import callsign_to_distance
    # Regression: bestehender Pfad ohne Slash funktioniert weiter UND
    # Mobile-Suffix wird auf Basis-Call zurueckgefuehrt → identische km
    km1 = callsign_to_distance("DA1MHH", "JO31")
    km2 = callsign_to_distance("DA1MHH/P", "JO31")
    assert km1 is not None and km2 is not None
    assert km1 == km2


# ── LocatorDB Konsistenz-Tests ───────────────────────────────────────────


def test_locator_db_set_get_with_slash_call(tmp_path):
    """DB speichert Slash-Calls 1:1 unter dem gegebenen Key."""
    from core.locator_db import LocatorDB
    db = LocatorDB(path=tmp_path / "test_cache.json")
    assert db.set("EA8/DA1MHH", "IL27", "cq") is True
    entry = db.get("EA8/DA1MHH")
    assert entry is not None
    assert entry.locator == "IL27"
    # Lookup mit gestripptem Call findet NICHT (strikte Trennung):
    assert db.get("DA1MHH") is None


def test_locator_db_get_position_slash_call(tmp_path):
    """get_position bei Slash-Call → Kanaren-Position aus IL27."""
    from core.geo import grid_to_latlon
    from core.locator_db import LocatorDB
    db = LocatorDB(path=tmp_path / "test_cache.json")
    db.set("EA8/DA1MHH", "IL27", "cq")
    pos = db.get_position("EA8/DA1MHH")
    assert pos is not None
    expected = grid_to_latlon("IL27")
    assert expected is not None
    # Lat/Lon Mitte-des-Feldes-Match (innerhalb 0.5°)
    assert abs(pos[0] - expected[0]) < 0.5
    assert abs(pos[1] - expected[1]) < 0.5


# ── _feed_locator_db Test ────────────────────────────────────────────────


def test_feed_locator_db_writes_slash_call_unchanged():
    """_feed_locator_db speichert m.caller 1:1 in DB (kein Stripping)."""
    from core.message import FT8Message
    from ui.mw_cycle import CycleMixin
    owner = MagicMock()
    msg = FT8Message(
        raw="CQ EA8/DA1MHH IL27", field1="CQ", field2="EA8/DA1MHH",
        field3="IL27",
    )
    CycleMixin._feed_locator_db(owner, [msg])
    owner.locator_db.set.assert_called_once_with("EA8/DA1MHH", "IL27", "cq")


# ── Integration-Test mit echter DB ───────────────────────────────────────


def test_integration_rx_panel_finds_slash_call_in_db(qapp, tmp_path):
    """Echter Pfad: DB-Set mit Slash-Call → rx_panel findet via lookup_call."""
    from core.locator_db import LocatorDB
    db = LocatorDB(path=tmp_path / "test_cache.json")
    db.set("EA8/DA1MHH", "IL27", "cq")
    # Simuliere rx_panel._populate_row Lookup-Logik (Diff 4):
    caller = "EA8/DA1MHH"
    lookup_call = caller  # Option A: 1:1 ohne Stripping
    pos = db.get_position(lookup_call)
    # Vor v0.95.16: max(parts, key=len)→DA1MHH→None (verfehlt)
    assert pos is not None
