"""OPT-63: `_resolve_station_position()` — gemeinsamer Locator-Auflösungs-Helfer
für `snapshot_to_station_points` + `entries_to_station_points` (DRY, K3).

Reihenfolge: locator_db.get_position (persistent, mit prec_km) → fallback_loc →
safe_locator_to_latlon. cache wird NUR bei Fallback-Treffer aktualisiert (nicht
bei DB-Treffer). Verhaltensgleich zu den beiden vorherigen Inline-Blöcken.
"""
from ui.direction_map_widget import _resolve_station_position, LocatorCache


class _Entry:
    def __init__(self, locator):
        self.locator = locator


class _FakeDB:
    """call -> (lat, lon, prec_km) für get_position; call -> locator für get()."""
    def __init__(self, positions=None, entries=None):
        self._positions = positions or {}
        self._entries = entries or {}

    def get_position(self, call):
        return self._positions.get(call)

    def get(self, call):
        return _Entry(self._entries[call]) if call in self._entries else None


# ── DB-Pfad (priorisiert) ─────────────────────────────────────────────

def test_db_hit_returns_db_position_and_no_cache_update():
    db = _FakeDB(positions={"A": (51.0, 7.0, 5)}, entries={"A": "JO31AB"})
    cache = LocatorCache()
    res = _resolve_station_position("A", "JO99", locator_db=db, locator_cache=cache)
    assert res == (51.0, 7.0, 5, "JO31AB")
    # DB-Treffer aktualisiert den Session-Cache NICHT (verhaltensgleich)
    assert cache.get("A") is None


def test_db_hit_with_missing_entry_yields_empty_loc():
    db = _FakeDB(positions={"A": (1.0, 2.0, 5)}, entries={})  # get_position trifft, get()=None
    res = _resolve_station_position("A", "JO31", locator_db=db)
    assert res == (1.0, 2.0, 5, "")


def test_db_given_but_no_position_falls_through_to_fallback():
    db = _FakeDB(positions={}, entries={})  # kein DB-Treffer
    cache = LocatorCache()
    res = _resolve_station_position("A", "JO31", locator_db=db, locator_cache=cache)
    assert res is not None
    lat, lon, prec, loc = res
    assert loc == "JO31" and prec == 110
    assert cache.get("A") == "JO31"  # Fallback-Treffer → cache aktualisiert


# ── Fallback-Pfad ─────────────────────────────────────────────────────

def test_fallback_4digit_prec_110_and_caches():
    cache = LocatorCache()
    res = _resolve_station_position("A", "JO31", locator_cache=cache)
    assert res is not None
    lat, lon, prec, loc = res
    assert prec == 110 and loc == "JO31"
    assert cache.get("A") == "JO31"


def test_fallback_6digit_prec_5():
    res = _resolve_station_position("A", "JO31AB", locator_cache=LocatorCache())
    assert res is not None
    assert res[2] == 5  # 6-stellig → 5 km


def test_fallback_without_cache_no_crash():
    """entries-Aufrufer übergibt keinen Cache → muss gefahrlos funktionieren."""
    res = _resolve_station_position("A", "JO31", locator_db=None, locator_cache=None)
    assert res is not None and res[3] == "JO31"


# ── Nicht auflösbar → None ────────────────────────────────────────────

def test_no_fallback_locator_returns_none():
    assert _resolve_station_position("A", None) is None
    assert _resolve_station_position("A", "") is None


def test_invalid_fallback_locator_returns_none():
    # '1234' ist kein gültiger Maidenhead → safe_locator_to_latlon = None
    assert _resolve_station_position("A", "1234") is None
