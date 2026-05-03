"""Tests fuer config/settings.py — v0.87 → v0.88 Bandpilot-Migration + atomic save.

Die Settings-Klasse nutzt globale CONFIG_FILE/CONFIG_DIR — Tests
monkeypatchen diese auf tmp_path, damit kein Test-Lauf die echte
~/.simpleft8/config.json ueberschreibt.
"""

import json

import pytest

import config.settings as settings_mod
from config.settings import Settings


@pytest.fixture
def isolated_settings(tmp_path, monkeypatch):
    """Settings auf tmp_path umbiegen — komplett isoliert von ~/.simpleft8."""
    monkeypatch.setattr(settings_mod, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(settings_mod, "CONFIG_FILE", tmp_path / "config.json")
    return tmp_path


# ── Migration ────────────────────────────────────────────────────────────────

def test_settings_migration_enabled_true_to_auto(isolated_settings):
    """V3-AK 32 #9: bandpilot_enabled=true → bandpilot_mode='auto'."""
    config_file = isolated_settings / "config.json"
    config_file.write_text(json.dumps({
        "callsign": "DA1MHH",
        "bandpilot_enabled": True,
        "bandpilot_diversity_pref": "dx",
    }))
    s = Settings()
    assert s.get("bandpilot_mode") == "auto"
    assert "bandpilot_enabled" not in s._data
    assert "bandpilot_diversity_pref" not in s._data


def test_settings_migration_enabled_false_to_off(isolated_settings):
    """V3-AK 32 #10: bandpilot_enabled=false → bandpilot_mode='off'."""
    config_file = isolated_settings / "config.json"
    config_file.write_text(json.dumps({
        "callsign": "DA1MHH",
        "bandpilot_enabled": False,
        "bandpilot_diversity_pref": "auto",
    }))
    s = Settings()
    assert s.get("bandpilot_mode") == "off"


def test_settings_migration_no_old_keys_keeps_default_off(isolated_settings):
    """Frische Config (nie Bandpilot gehabt) → DEFAULT 'off'."""
    config_file = isolated_settings / "config.json"
    config_file.write_text(json.dumps({"callsign": "DA1MHH"}))
    s = Settings()
    assert s.get("bandpilot_mode") == "off"


def test_settings_migration_idempotent(isolated_settings):
    """V3-AK 32 #11: Zweite Migration laesst bandpilot_mode unveraendert."""
    config_file = isolated_settings / "config.json"
    config_file.write_text(json.dumps({
        "bandpilot_mode": "manual",  # User hat schon migriert
    }))
    s = Settings()
    assert s.get("bandpilot_mode") == "manual"  # nicht ueberschrieben


def test_settings_migration_persists_to_disk(isolated_settings):
    """Migration ruft save() — neue Keys sind im JSON."""
    config_file = isolated_settings / "config.json"
    config_file.write_text(json.dumps({
        "bandpilot_enabled": True,
    }))
    Settings()  # triggert Migration + save
    saved = json.loads(config_file.read_text())
    assert saved["bandpilot_mode"] == "auto"
    assert "bandpilot_enabled" not in saved


def test_settings_migration_deletes_old_cache(isolated_settings, monkeypatch, tmp_path):
    """V3-AK 33: alter Cache bandpilot_summary.json wird beim Migrieren geloescht."""
    # Path.home()/.simpleft8 auf tmp_path/home umbiegen
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    fake_simpleft8 = fake_home / ".simpleft8"
    fake_simpleft8.mkdir()
    old_cache = fake_simpleft8 / "bandpilot_summary.json"
    old_cache.write_text('{"40m": {"ts": 1700000000, "summary": {}}}')

    monkeypatch.setattr("pathlib.Path.home", lambda: fake_home)

    config_file = isolated_settings / "config.json"
    config_file.write_text(json.dumps({"bandpilot_enabled": True}))
    Settings()  # triggert Migration

    assert not old_cache.exists()


# ── Atomic save ───────────────────────────────────────────────────────────────

def test_settings_save_atomic(isolated_settings):
    """V3-AK 32 #12 / V3-AK 29: save() schreibt erst .tmp, dann replace.

    Nach save() existiert KEINE .tmp-Datei mehr (replace hat sie geschoben).
    """
    s = Settings()
    s.set("callsign", "TESTCALL")
    s.save()
    config_file = isolated_settings / "config.json"
    assert config_file.exists()
    # .tmp-Datei wurde durch os.replace() geschoben
    assert not (isolated_settings / "config.tmp").exists()


def test_settings_save_creates_dir(tmp_path, monkeypatch):
    """save() erstellt CONFIG_DIR wenn fehlt."""
    new_dir = tmp_path / "fresh"
    monkeypatch.setattr(settings_mod, "CONFIG_DIR", new_dir)
    monkeypatch.setattr(settings_mod, "CONFIG_FILE", new_dir / "config.json")
    s = Settings()
    s.save()
    assert new_dir.exists()
    assert (new_dir / "config.json").exists()


def test_settings_save_persists_set_values(isolated_settings):
    """Roundtrip: set() + save() + Settings() liest die Werte zurueck."""
    s = Settings()
    s.set("callsign", "DL9XYZ")
    s.set("locator", "JN58")
    s.save()
    s2 = Settings()
    assert s2.get("callsign") == "DL9XYZ"
    assert s2.get("locator") == "JN58"
