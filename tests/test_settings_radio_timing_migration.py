"""P121 — Settings load() Migration für radio_timing-Block.

Wenn config.json den Block exakt mit P48-Defaults (1.3, 0.26) enthält,
wird er auf {} reduziert damit spätere Radio-Default-Änderungen greifen.
User-Overrides bleiben aber erhalten.
"""
from __future__ import annotations

import json
import pytest


def _make_config(tmp_path, content: dict, monkeypatch):
    """Helper: temporäre config.json schreiben + Settings-Modul patchen."""
    cfg = tmp_path / "config.json"
    cfg.write_text(json.dumps(content))
    import config.settings as cs
    monkeypatch.setattr(cs, "CONFIG_FILE", cfg)
    monkeypatch.setattr(cs, "CONFIG_DIR", tmp_path)
    return cs


def test_legacy_p48_defaults_popped(tmp_path, monkeypatch):
    """radio_timing == FlexRadio-Legacy-Defaults → leerer Dict nach load()."""
    cs = _make_config(tmp_path, {
        "callsign": "DA1MHH",
        "radio_timing": {"tx_buffer_s": 1.3, "rx_hardware_offset_default_s": 0.26},
    }, monkeypatch)

    s = cs.Settings()
    assert s._data["radio_timing"] == {}
    assert s.get_user_tx_buffer_override() is None
    assert s.get_user_rx_hardware_offset_override() is None


def test_user_override_value_kept(tmp_path, monkeypatch):
    """Wert abweichend von Legacy-Default → bleibt als User-Override erhalten."""
    cs = _make_config(tmp_path, {
        "callsign": "DA1MHH",
        "radio_timing": {"tx_buffer_s": 1.5, "rx_hardware_offset_default_s": 0.26},
    }, monkeypatch)

    s = cs.Settings()
    assert s._data["radio_timing"]["tx_buffer_s"] == 1.5
    assert s.get_user_tx_buffer_override() == 1.5
    assert s.get_user_rx_hardware_offset_override() == 0.26


def test_unknown_extra_key_keeps_block(tmp_path, monkeypatch):
    """Zusätzlicher Key im Block → Block bleibt komplett (User wollte was)."""
    cs = _make_config(tmp_path, {
        "callsign": "DA1MHH",
        "radio_timing": {
            "tx_buffer_s": 1.3,
            "rx_hardware_offset_default_s": 0.26,
            "experimental_jitter_s": 0.05,
        },
    }, monkeypatch)

    s = cs.Settings()
    # Block bleibt erhalten — wir kennen 'experimental_jitter_s' nicht
    assert "experimental_jitter_s" in s._data["radio_timing"]
    # Aber wir behandeln tx_buffer_s nicht als Override-Wert (1.3 == Default)
    # → das ist okay, der Aufrufer bekommt 1.3 zurück und das ist == Radio-Default
    assert s.get_user_tx_buffer_override() == 1.3


def test_empty_block_no_overrides(tmp_path, monkeypatch):
    """Leerer Block → keine Overrides."""
    cs = _make_config(tmp_path, {
        "callsign": "DA1MHH",
        "radio_timing": {},
    }, monkeypatch)

    s = cs.Settings()
    assert s.get_user_tx_buffer_override() is None
    assert s.get_user_rx_hardware_offset_override() is None


def test_missing_block_no_overrides(tmp_path, monkeypatch):
    """Kein radio_timing-Key in config → leerer Default-Dict + None overrides."""
    cs = _make_config(tmp_path, {"callsign": "DA1MHH"}, monkeypatch)

    s = cs.Settings()
    assert s._data.get("radio_timing") == {}
    assert s.get_user_tx_buffer_override() is None
    assert s.get_user_rx_hardware_offset_override() is None
