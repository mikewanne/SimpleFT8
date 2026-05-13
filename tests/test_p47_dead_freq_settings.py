"""P47 — Tote Frequenz-Settings + Statusbar-Filter-Anzeige entfernt (v0.97.11).

Bug-Hintergrund:
- `audio_freq_hz` und `max_decode_freq` waren UI-Eingaben ohne Wirkung
  (Encoder wird vom CQ-Such-Algo ueberschrieben; decoder.max_freq wird
  nie zur Laufzeit aktualisiert).
- Statusbar-Anzeige "Filter: 100-4000 Hz" fuer FT2 war irrefuehrend
  (Decoder lief faktisch auf 3000 Hz).

Tests:
- T1: alte JSON-Configs mit toten Keys werden beim Settings.load() entfernt.
- T2: Settings-Instanz hat keine Property audio_freq_hz / max_decode_freq mehr.
- T3: get_normal_tx_freq Fallback ist hartkodierte 1500 Hz.
- T4: ui/main_window.py Source enthaelt _FILTERS / filter_str / "Filter:" nicht mehr.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest


def test_settings_load_drops_dead_keys(tmp_path, monkeypatch):
    """Alte config.json mit audio_freq_hz / max_decode_freq → Keys weg nach Load."""
    cfg = tmp_path / "config.json"
    cfg.write_text(json.dumps({
        "audio_freq_hz": 1700,
        "max_decode_freq": 4500,
        "callsign": "TESTCALL",
    }))
    import config.settings as cs
    monkeypatch.setattr(cs, "CONFIG_FILE", cfg)
    monkeypatch.setattr(cs, "CONFIG_DIR", tmp_path)

    s = cs.Settings()

    assert "audio_freq_hz" not in s._data
    assert "max_decode_freq" not in s._data
    # Andere Keys bleiben unangetastet
    assert s._data.get("callsign") == "TESTCALL"


def test_settings_no_audio_freq_property(tmp_path, monkeypatch):
    """Frische Settings-Instanz hat keine Properties audio_freq_hz / max_decode_freq."""
    import config.settings as cs
    cfg = tmp_path / "config.json"  # nicht existent → Defaults
    monkeypatch.setattr(cs, "CONFIG_FILE", cfg)
    monkeypatch.setattr(cs, "CONFIG_DIR", tmp_path)

    s = cs.Settings()

    assert not hasattr(s, "audio_freq_hz"), \
        "audio_freq_hz-Property haette in P47 entfernt sein muessen"
    assert not hasattr(s, "max_decode_freq"), \
        "max_decode_freq-Property haette in P47 entfernt sein muessen"


def test_get_normal_tx_freq_fallback_constant():
    """Ohne per-Band-Eintrag liefert get_normal_tx_freq hartkodierte 1500."""
    from config.settings import Settings
    s = Settings.__new__(Settings)
    s._data = {}
    assert s.get_normal_tx_freq("20m") == 1500
    assert s.get_normal_tx_freq("40m") == 1500
    assert s.get_normal_tx_freq("60m") == 1500


def test_get_normal_tx_freq_per_band_still_works():
    """Per-Band-Eintraege (normal_tx_freq_per_band) bleiben gueltig nach P47."""
    from config.settings import Settings
    s = Settings.__new__(Settings)
    s._data = {"normal_tx_freq_per_band": {"20m": 1234, "40m": 999}}
    assert s.get_normal_tx_freq("20m") == 1234
    assert s.get_normal_tx_freq("40m") == 999
    assert s.get_normal_tx_freq("80m") == 1500  # Fallback


def test_statusbar_source_no_filter_anzeige():
    """ui/main_window.py-Source enthaelt _FILTERS / filter_str nicht mehr.

    Bug-Schutz-Assertion: Statusbar-Filter-Anzeige war irrefuehrend
    (FT2 zeigte 100-4000 Hz, Decoder lief faktisch auf 3000 Hz).
    """
    src = Path(__file__).parent.parent / "ui" / "main_window.py"
    text = src.read_text()
    assert "_FILTERS = {" not in text, \
        "P47: _FILTERS-Dict in _update_statusbar haette entfernt sein muessen"
    assert "filter_str = _FILTERS" not in text, \
        "P47: filter_str-Berechnung haette entfernt sein muessen"
    assert "Filter: {filter_str} Hz" not in text, \
        "P47: 'Filter: ... Hz'-Segment im msg-String haette entfernt sein muessen"
