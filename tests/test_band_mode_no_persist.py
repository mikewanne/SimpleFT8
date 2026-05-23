"""2026-05-23: Band/Modus werden nicht mehr persistiert.

App startet immer mit DEFAULTS (20m FT8) — gespeicherte band/mode-
Werte im Settings-File werden ignoriert. save() schliesst sie aus.

Mike-Entscheidung 23.05.2026: bewusste UX-Vereinfachung. Verhindert
auch versehentliches Starten im (versteckten) FT2-Modus.
"""
import json

from config import settings as settings_module


def test_load_ignores_saved_band_and_mode(tmp_path, monkeypatch):
    """Saved band='40m'/mode='FT4' wird beim Load auf DEFAULTS gezwungen."""
    fake_config = tmp_path / "config.json"
    fake_config.write_text(json.dumps({
        "band": "40m",
        "mode": "FT4",
        "callsign": "TEST",  # andere Keys sollen erhalten bleiben
    }))
    monkeypatch.setattr(settings_module, "CONFIG_FILE", fake_config)

    s = settings_module.Settings()

    # Band/Modus auf DEFAULTS gezwungen, NICHT der saved Wert
    assert s.get("band") == settings_module.DEFAULTS["band"] == "20m"
    assert s.get("mode") == settings_module.DEFAULTS["mode"] == "FT8"
    # Andere persistierte Keys bleiben
    assert s.get("callsign") == "TEST"


def test_load_ignores_saved_ft2_specifically(tmp_path, monkeypatch):
    """Wichtiger Spezialfall: mode='FT2' im File darf die App nicht im
    versteckten FT2-Modus starten lassen."""
    fake_config = tmp_path / "config.json"
    fake_config.write_text(json.dumps({"band": "20m", "mode": "FT2"}))
    monkeypatch.setattr(settings_module, "CONFIG_FILE", fake_config)

    s = settings_module.Settings()

    # Trotz mode='FT2' im File → DEFAULT FT8
    assert s.get("mode") == "FT8"


def test_save_excludes_band_and_mode(tmp_path, monkeypatch):
    """save() darf band/mode nicht ins JSON schreiben."""
    fake_config = tmp_path / "config.json"
    monkeypatch.setattr(settings_module, "CONFIG_FILE", fake_config)

    s = settings_module.Settings()
    s.set("band", "40m")     # in-memory aendern (z.B. User-Bandwechsel)
    s.set("mode", "FT4")
    s.set("callsign", "DX9")  # ein normaler Key zur Kontrolle
    s.save()

    written = json.loads(fake_config.read_text())
    # band + mode duerfen NICHT persistiert sein
    assert "band" not in written
    assert "mode" not in written
    # andere Keys schon
    assert written.get("callsign") == "DX9"


def test_in_memory_band_mode_updates_still_work(tmp_path, monkeypatch):
    """settings.set('band'/'mode', ...) muss zur Laufzeit weiter wirken
    (nur Persistenz ist weg, nicht die in-memory Aktualitaet — das
    nutzen mw_radio.py:405 / :505 nach jedem Bandwechsel)."""
    fake_config = tmp_path / "config.json"
    monkeypatch.setattr(settings_module, "CONFIG_FILE", fake_config)

    s = settings_module.Settings()
    assert s.get("band") == "20m"  # Start-Default

    # Simuliert Mike-Bandwechsel zur Laufzeit
    s.set("band", "40m")
    s.set("mode", "FT4")

    # In-memory sofort aktuell — Decoder/Encoder/PSK-Reporter lesen das so
    assert s.get("band") == "40m"
    assert s.get("mode") == "FT4"
