#!/usr/bin/env python3
"""Tests fuer core/locator_db.py.

Pure-Python-Logik (CRUD, Source-Priority, Persist-Roundtrip, Threading).
Kein Filesystem ausser tmp_path-Fixture.

Ausfuehren:
    cd SimpleFT8
    ./venv/bin/python3 -m pytest tests/test_locator_db.py -v
"""

import json
import os
import sys
import threading
import time
from pathlib import Path

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.locator_db import (
    LocatorDB,
    LocatorEntry,
    SOURCE_PRIORITY,
    SCHEMA_VERSION,
)


# ── Basics ────────────────────────────────────────────────

def test_set_and_get_basic(tmp_path: Path):
    db = LocatorDB(tmp_path / "loc.json")
    assert db.set("DA1MHH", "JO31qf", "cq") is True
    e = db.get("DA1MHH")
    assert e is not None
    assert e.locator == "JO31QF"
    assert e.source == "cq_6"
    assert e.prec_km == 5
    assert e.first_ts == e.last_ts


def test_get_position_returns_latlon(tmp_path: Path):
    db = LocatorDB(tmp_path / "loc.json")
    db.set("DA1MHH", "JO31qf", "cq")
    pos = db.get_position("DA1MHH")
    assert pos is not None
    lat, lon, prec_km = pos
    assert 49 < lat < 52
    assert 6 < lon < 9
    assert prec_km == 5


def test_get_unknown_returns_none(tmp_path: Path):
    db = LocatorDB(tmp_path / "loc.json")
    assert db.get("UNKNOWN") is None
    assert db.get_position("UNKNOWN") is None


def test_get_normalizes_to_uppercase(tmp_path: Path):
    db = LocatorDB(tmp_path / "loc.json")
    db.set("da1mhh", "jo31qf", "cq")
    assert db.get("DA1MHH") is not None
    assert db.get("da1mhh") is not None  # auch lowercase-input


# ── Source-Priority ────────────────────────────────────────

def test_priority_psk_does_not_overwrite_cq_6(tmp_path: Path):
    """DeepSeek-Tausch: cq_6 (600) > psk_6 (500) — eigene Decode vertrauenswuerdiger."""
    db = LocatorDB(tmp_path / "loc.json")
    db.set("DA1MHH", "JO31qf", "cq")
    assert db.set("DA1MHH", "JO31aa", "psk") is False
    e = db.get("DA1MHH")
    assert e.locator == "JO31QF"  # nicht ueberschrieben
    assert e.source == "cq_6"


def test_priority_4_does_not_overwrite_6(tmp_path: Path):
    """4-stellig kann 6-stellig nie ueberschreiben — egal welche Source."""
    db = LocatorDB(tmp_path / "loc.json")
    db.set("DA1MHH", "JO31qf", "psk")  # psk_6 (500)
    assert db.set("DA1MHH", "JO31", "cq") is False  # cq_4 (300) < psk_6 (500)
    e = db.get("DA1MHH")
    assert e.locator == "JO31QF"
    assert e.source == "psk_6"


def test_priority_6_overwrites_4(tmp_path: Path):
    """6-stellig kann 4-stellig ueberschreiben."""
    db = LocatorDB(tmp_path / "loc.json")
    db.set("DA1MHH", "JO31", "psk")  # psk_4 (200)
    assert db.set("DA1MHH", "JO31qf", "psk") is True  # psk_6 (500) > psk_4 (200)
    e = db.get("DA1MHH")
    assert e.locator == "JO31QF"
    assert e.source == "psk_6"
    assert e.prec_km == 5


def test_priority_qso_log_does_not_overwrite_cq(tmp_path: Path):
    db = LocatorDB(tmp_path / "loc.json")
    db.set("DA1MHH", "JO31qf", "cq")
    assert db.set("DA1MHH", "JO31xy", "qso_log") is False


# ── Validation ─────────────────────────────────────────────

def test_set_rejects_invalid_locator(tmp_path: Path):
    db = LocatorDB(tmp_path / "loc.json")
    # core.geo.grid_to_latlon validiert Format (AA-RR, 00-99), nicht aber den
    # Wert-Bereich — grid_to_latlon("ZZ99") liefert eine sinnlose Position aber
    # crasht nicht. safe_locator_to_latlon filtert nur strukturell ungueltige.
    assert db.set("DA1MHH", "1234", "cq") is False        # alle digits
    assert db.set("DA1MHH", "ABCD", "cq") is False        # alle alpha
    assert db.set("DA1MHH", "", "cq") is False             # leer
    assert db.set("DA1MHH", "AB", "cq") is False           # zu kurz
    assert db.set("DA1MHH", None, "cq") is False           # None  # type: ignore[arg-type]
    assert db.get("DA1MHH") is None


def test_set_rejects_unknown_source(tmp_path: Path):
    db = LocatorDB(tmp_path / "loc.json")
    assert db.set("DA1MHH", "JO31qf", "qrz") is False
    assert db.set("DA1MHH", "JO31qf", "") is False


def test_set_rejects_empty_call(tmp_path: Path):
    db = LocatorDB(tmp_path / "loc.json")
    assert db.set("", "JO31qf", "cq") is False
    assert db.set(None, "JO31qf", "cq") is False  # type: ignore[arg-type]


# ── Timestamps ─────────────────────────────────────────────

def test_first_ts_never_changes(tmp_path: Path):
    db = LocatorDB(tmp_path / "loc.json")
    db.set("DA1MHH", "JO31", "cq")  # cq_4
    e1 = db.get("DA1MHH")
    first_ts_original = e1.first_ts
    time.sleep(0.01)
    db.set("DA1MHH", "JO31qf", "cq")  # cq_6 ueberschreibt cq_4
    e2 = db.get("DA1MHH")
    assert e2.first_ts == first_ts_original
    assert e2.last_ts > e1.last_ts


def test_same_priority_updates_last_ts_only(tmp_path: Path):
    db = LocatorDB(tmp_path / "loc.json")
    db.set("DA1MHH", "JO31qf", "cq")
    e1 = db.get("DA1MHH")
    time.sleep(0.01)
    db.set("DA1MHH", "JO31qf", "cq")  # gleicher Locator, gleiche Source
    e2 = db.get("DA1MHH")
    assert e2.last_ts > e1.last_ts
    assert e2.first_ts == e1.first_ts


# ── Persistenz ─────────────────────────────────────────────

def test_persist_and_reload(tmp_path: Path):
    path = tmp_path / "loc.json"
    db1 = LocatorDB(path)
    db1.set("DA1MHH", "JO31qf", "cq")
    db1.set("K1ABC", "FN42", "psk")
    db1.save()

    db2 = LocatorDB(path)
    db2.load()
    assert len(db2) == 2
    e = db2.get("DA1MHH")
    assert e.locator == "JO31QF"
    assert e.source == "cq_6"


def test_corrupted_json_returns_empty(tmp_path: Path):
    path = tmp_path / "loc.json"
    path.write_text("{ this is not valid json")
    db = LocatorDB(path)
    db.load()
    assert len(db) == 0
    # Trotzdem schreibbar nach load
    assert db.set("DA1MHH", "JO31qf", "cq") is True


def test_load_missing_file_no_crash(tmp_path: Path):
    db = LocatorDB(tmp_path / "does-not-exist.json")
    db.load()
    assert len(db) == 0


def test_atomic_write_no_partial_file(tmp_path: Path, monkeypatch):
    """Wenn json.dump crasht, darf die Ziel-Datei nicht halb geschrieben sein."""
    path = tmp_path / "loc.json"
    db = LocatorDB(path)
    db.set("DA1MHH", "JO31qf", "cq")
    db.save()
    original = path.read_text()

    # Simuliere Crash mitten im Write
    import json as json_mod
    real_dump = json_mod.dump

    def crashing_dump(*args, **kwargs):
        raise OSError("disk full")
    monkeypatch.setattr(json_mod, "dump", crashing_dump)

    db.set("K1ABC", "FN42", "psk")
    with pytest.raises(OSError):
        db.save()

    # Original-Datei muss unangetastet sein
    assert path.read_text() == original
    monkeypatch.setattr(json_mod, "dump", real_dump)


def test_save_creates_parent_dir(tmp_path: Path):
    deep_path = tmp_path / "nested" / "dirs" / "loc.json"
    db = LocatorDB(deep_path)
    db.set("DA1MHH", "JO31qf", "cq")
    db.save()
    assert deep_path.exists()


def test_save_uses_schema_version(tmp_path: Path):
    path = tmp_path / "loc.json"
    db = LocatorDB(path)
    db.set("DA1MHH", "JO31qf", "cq")
    db.save()
    raw = json.loads(path.read_text())
    assert raw["version"] == SCHEMA_VERSION
    assert "calls" in raw


# ── Threading ──────────────────────────────────────────────

def test_concurrent_writes_no_corruption(tmp_path: Path):
    """5 Threads x 50 sets → keine Race-Condition, alle Eintraege sauber."""
    db = LocatorDB(tmp_path / "loc.json")
    locators = ["JO31", "JO40", "FN42", "EM48", "RR99"]

    def worker(thread_id: int):
        for i in range(50):
            call = f"T{thread_id}C{i:02d}"
            loc = locators[i % len(locators)]
            db.set(call, loc, "cq")

    threads = [threading.Thread(target=worker, args=(t,)) for t in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(db) == 5 * 50
    # Stichprobe: jeder Eintrag valide
    snap = db.snapshot()
    for call, data in snap.items():
        assert data["source"].startswith("cq_")
        assert data["prec_km"] in (5, 110)


# ── Slash-Calls ────────────────────────────────────────────

def test_slash_p_treated_as_stationary(tmp_path: Path):
    """/P (portable) → gleiche Priority und prec_km wie ohne Suffix."""
    db = LocatorDB(tmp_path / "loc.json")
    db.set("DA1MHH/P", "JO31qf", "cq")
    e = db.get("DA1MHH/P")
    assert e is not None
    assert e.prec_km == 5  # nicht aufgepumpt


def test_slash_mm_higher_imprecision(tmp_path: Path):
    """/MM (maritime mobile) → prec_km x 1.5."""
    db = LocatorDB(tmp_path / "loc.json")
    db.set("K1ABC/MM", "FN42", "cq")  # cq_4 = 110 km
    e = db.get("K1ABC/MM")
    assert e is not None
    # 110 * 1.5 = 165
    assert e.prec_km == 165


def test_slash_am_higher_imprecision(tmp_path: Path):
    db = LocatorDB(tmp_path / "loc.json")
    db.set("K1ABC/AM", "FN42qf", "cq")  # cq_6 = 5 km
    e = db.get("K1ABC/AM")
    # 5 * 1.5 = 7.5 → round to 8
    assert e.prec_km == 8


# ── Bulk-Import ────────────────────────────────────────────

def test_bulk_import_adif_no_duplicates(tmp_path: Path):
    """Doppelte CALL+GRIDSQUARE-Eintraege fuehren zu einem DB-Eintrag."""
    adif = tmp_path / "test.adi"
    adif.write_text(
        "Header text\n<EOH>\n"
        "<CALL:6>DA1MHH <QSO_DATE:8>20260101 <TIME_ON:6>120000 "
        "<GRIDSQUARE:6>JO31qf <BAND:3>20m <MODE:3>FT8 <EOR>\n"
        "<CALL:6>DA1MHH <QSO_DATE:8>20260102 <TIME_ON:6>130000 "
        "<GRIDSQUARE:6>JO31qf <BAND:3>20m <MODE:3>FT8 <EOR>\n"
        "<CALL:5>K1ABC <QSO_DATE:8>20260101 <TIME_ON:6>140000 "
        "<GRIDSQUARE:4>FN42 <BAND:3>20m <MODE:3>FT8 <EOR>\n"
    )
    db = LocatorDB(tmp_path / "loc.json")
    n = db.bulk_import_adif(adif)
    assert n >= 2  # zwei unique calls
    assert len(db) == 2
    assert db.get("DA1MHH").source == "qso_log_6"
    assert db.get("K1ABC").source == "qso_log_4"


def test_bulk_import_missing_file_returns_zero(tmp_path: Path):
    db = LocatorDB(tmp_path / "loc.json")
    assert db.bulk_import_adif(tmp_path / "nope.adi") == 0


# ── Diagnostik ─────────────────────────────────────────────

def test_average_precision_km(tmp_path: Path):
    db = LocatorDB(tmp_path / "loc.json")
    assert db.average_precision_km() == 0.0
    db.set("A", "JO31qf", "cq")  # 5
    db.set("B", "FN42", "cq")    # 110
    avg = db.average_precision_km()
    assert avg == pytest.approx((5 + 110) / 2)
