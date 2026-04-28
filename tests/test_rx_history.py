"""Tests fuer core/rx_history.py — persistenter RX-Empfangs-Cache."""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from core.rx_history import (
    RX_HISTORY_TTL_S, RxEntry, RxHistoryStore, SCHEMA_VERSION,
)


def _entry(call="DK4ABC", ts: float | None = None, **kwargs) -> RxEntry:
    """Bequemer Test-Helper. Default-Felder abdecken."""
    if ts is None:
        ts = time.time()
    defaults = dict(
        ts=ts, call=call, locator="JO40", snr=-12.0,
        antenna="A1", freq_hz=14_074_500,
    )
    defaults.update(kwargs)
    return RxEntry(**defaults)


def test_add_entry_creates_band_mode_pair(tmp_path):
    s = RxHistoryStore(base_dir=tmp_path)
    s.add_entry("40m", "FT8", _entry())
    entries = s.get_band_entries("40m")
    assert len(entries) == 1
    assert entries[0].call == "DK4ABC"


def test_add_entry_marks_dirty(tmp_path):
    s = RxHistoryStore(base_dir=tmp_path)
    assert ("40m", "FT8") not in s._dirty
    s.add_entry("40m", "FT8", _entry())
    assert ("40m", "FT8") in s._dirty


def test_get_band_entries_merges_3_modes(tmp_path):
    s = RxHistoryStore(base_dir=tmp_path)
    s.add_entry("40m", "FT8", _entry(call="A1", ts=time.time() - 30))
    s.add_entry("40m", "FT4", _entry(call="A2", ts=time.time() - 20))
    s.add_entry("40m", "FT2", _entry(call="A3", ts=time.time() - 10))
    s.add_entry("20m", "FT8", _entry(call="OTHER", ts=time.time() - 5))
    entries = s.get_band_entries("40m")
    calls = {e.call for e in entries}
    assert calls == {"A1", "A2", "A3"}  # 20m wurde nicht gemerged


def test_get_band_entries_filters_old_entries(tmp_path):
    s = RxHistoryStore(base_dir=tmp_path)
    now = time.time()
    s.add_entry("40m", "FT8", _entry(call="OLD", ts=now - RX_HISTORY_TTL_S - 100))
    s.add_entry("40m", "FT8", _entry(call="NEW", ts=now - 30))
    entries = s.get_band_entries("40m")
    assert {e.call for e in entries} == {"NEW"}


def test_get_band_entries_empty_band(tmp_path):
    s = RxHistoryStore(base_dir=tmp_path)
    assert s.get_band_entries("40m") == []
    assert s.get_band_entries("") == []


def test_save_writes_atomic_tmp_replace(tmp_path):
    s = RxHistoryStore(base_dir=tmp_path)
    s.add_entry("40m", "FT8", _entry())
    written = s.save()
    assert written == 1
    out = tmp_path / "40m_FT8.json"
    assert out.exists()
    # .tmp darf nicht uebrigbleiben
    assert not (tmp_path / "40m_FT8.tmp").exists()


def test_save_only_dirty_files(tmp_path):
    s = RxHistoryStore(base_dir=tmp_path)
    s.add_entry("40m", "FT8", _entry())
    s.add_entry("20m", "FT8", _entry(call="X"))
    assert s.save() == 2
    # Zweiter Save ohne neue Aenderungen — 0 dirty
    assert s.save() == 0


def test_save_handles_oserror_gracefully(tmp_path, monkeypatch):
    s = RxHistoryStore(base_dir=tmp_path)
    s.add_entry("40m", "FT8", _entry())
    # mkdir patchen das OSError wirft → save returnt 0, kein Crash
    def _raise(*_a, **_kw):
        raise OSError("disk full simulated")
    monkeypatch.setattr(Path, "mkdir", _raise)
    assert s.save() == 0
    # dirty bleibt → naechster Save versucht erneut
    assert ("40m", "FT8") in s._dirty


def test_load_all_filters_old_entries(tmp_path):
    # Erst speichern
    s1 = RxHistoryStore(base_dir=tmp_path)
    now = time.time()
    s1.add_entry("40m", "FT8", _entry(call="OLD", ts=now - RX_HISTORY_TTL_S - 100))
    s1.add_entry("40m", "FT8", _entry(call="NEW", ts=now - 30))
    # Save laeuft eh durch cleanup → OLD-Entry geht raus
    s1.save()

    # Frische Instanz laedt
    s2 = RxHistoryStore(base_dir=tmp_path)
    loaded = s2.load_all()
    assert loaded == 1  # nur NEW
    entries = s2.get_band_entries("40m")
    assert {e.call for e in entries} == {"NEW"}


def test_load_all_skips_corrupted_or_wrong_version(tmp_path):
    # Corrupted JSON + falsches Schema
    (tmp_path / "40m_FT8.json").write_text("{not valid json")
    (tmp_path / "20m_FT8.json").write_text(
        '{"version": 99, "band": "20m", "mode": "FT8", "entries": []}'
    )
    # Korrekte Datei
    valid = (tmp_path / "30m_FT8.json")
    valid.write_text(
        '{"version": ' + str(SCHEMA_VERSION)
        + ', "band": "30m", "mode": "FT8", "entries": ['
        + '{"ts": ' + str(time.time())
        + ', "call": "OK", "locator": "JO31", "snr": -10.0,'
        + '"antenna": "A1", "freq_hz": 10136000}'
        + ']}'
    )

    s = RxHistoryStore(base_dir=tmp_path)
    loaded = s.load_all()
    assert loaded == 1
    entries = s.get_band_entries("30m")
    assert len(entries) == 1 and entries[0].call == "OK"
