"""Tests fuer config/settings.py:_validate_types (OPT-53, Robustheit).

Eine von Hand verkorkste config.json (falsche Typen) darf die App nicht in
Folgefehler laufen lassen — abweichende Typen fallen auf den DEFAULTS-Wert
zurueck. Settings nutzt globale CONFIG_FILE/CONFIG_DIR; Tests biegen sie auf
tmp_path um, damit Mikes echte ~/.simpleft8/config.json unberuehrt bleibt.
"""

import json

import pytest

import config.settings as settings_mod
from config.settings import Settings, DEFAULTS


@pytest.fixture
def isolated_settings(tmp_path, monkeypatch):
    monkeypatch.setattr(settings_mod, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(settings_mod, "CONFIG_FILE", tmp_path / "config.json")
    return tmp_path


def _write_config(isolated, payload):
    (isolated / "config.json").write_text(json.dumps(payload))


def test_str_field_wrong_type_resets(isolated_settings):
    """callsign als Zahl → Default-String."""
    _write_config(isolated_settings, {"callsign": 12345})
    s = Settings()
    assert s.get("callsign") == DEFAULTS["callsign"]


def test_int_field_wrong_type_resets(isolated_settings):
    """max_calls als String → Default-Int."""
    _write_config(isolated_settings, {"max_calls": "fuenf"})
    s = Settings()
    assert s.get("max_calls") == DEFAULTS["max_calls"]


def test_bool_int_trap_port_true_resets(isolated_settings):
    """DIE FALLE: flexradio_port=true (bool) MUSS auf den int-Default zurueck.

    Mutationsbeweis fuer `type() is type()` statt isinstance: weil
    isinstance(True, int) == True, wuerde isinstance den bool durchlassen und
    dieser Test broeche. Genau das fangen wir ab.
    """
    _write_config(isolated_settings, {"flexradio_port": True})
    s = Settings()
    assert s.get("flexradio_port") == DEFAULTS["flexradio_port"]
    assert type(s.get("flexradio_port")) is int


def test_bool_field_int_resets(isolated_settings):
    """auto_mode=1 (int) → bool-Default (type(1) is bool == False)."""
    _write_config(isolated_settings, {"auto_mode": 1})
    s = Settings()
    assert s.get("auto_mode") is DEFAULTS["auto_mode"]


def test_dict_field_list_resets(isolated_settings):
    """radio_timing als Liste → leeres dict (Default)."""
    _write_config(isolated_settings, {"radio_timing": [1, 2, 3]})
    s = Settings()
    assert s.get("radio_timing") == DEFAULTS["radio_timing"]


def test_none_value_resets(isolated_settings):
    """callsign: null (None) → Default (type(None) is str == False)."""
    _write_config(isolated_settings, {"callsign": None})
    s = Settings()
    assert s.get("callsign") == DEFAULTS["callsign"]


def test_correct_config_unchanged(isolated_settings):
    """Korrekte Typen → 0 Aenderung (kein Reset im Normalbetrieb).

    band/mode bewusst ausgelassen — die werden ohnehin per Migration auf
    DEFAULTS erzwungen (2026-05-23) und sind kein _validate_types-Fall.
    tune_duration_s=10 ist Whitelist-konform (bleibt).
    """
    payload = {
        "callsign": "DL1ABC",
        "locator": "JN58",
        "flexradio_port": 5000,
        "max_calls": 3,
        "auto_mode": True,
        "radio_type": "ic7300",
        "tuner_present": False,
        "tune_duration_s": 10,
        "radio_timing": {"tx_buffer_s": 1.5},
    }
    _write_config(isolated_settings, payload)
    s = Settings()
    for key, val in payload.items():
        assert s.get(key) == val, f"{key} wurde faelschlich veraendert"


def test_dynamic_keys_preserved(isolated_settings):
    """Keys ausserhalb DEFAULTS (enabled_bands, presets …) bleiben unberuehrt —
    auch wenn gleichzeitig ein DEFAULTS-Feld einen falschen Typ hat."""
    _write_config(isolated_settings, {
        "enabled_bands": ["20m", "40m"],          # nicht in DEFAULTS
        "tx_slot_lock": {"20m": True},            # nicht in DEFAULTS
        "callsign": 999,                          # DEFAULTS-Feld, falscher Typ
    })
    s = Settings()
    assert s.get("enabled_bands") == ["20m", "40m"]   # erhalten
    assert s.get("tx_slot_lock") == {"20m": True}     # erhalten
    assert s.get("callsign") == DEFAULTS["callsign"]  # resettet


def test_all_defaults_are_basic_types(isolated_settings):
    """Vertrag: _validate_types geht davon aus, dass DEFAULTS-Werte einen
    eindeutigen Basistyp haben (str/int/bool/dict, kein float). Bricht jemand
    den Vertrag (z.B. float-Default), faellt das hier auf."""
    allowed = (str, int, bool, dict)
    for key, val in DEFAULTS.items():
        assert isinstance(val, allowed) and not isinstance(val, float), (
            f"DEFAULTS['{key}'] hat unerwarteten Typ {type(val).__name__}")
