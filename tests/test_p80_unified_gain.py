"""P80 (v0.97.52) — Unified Gain Store Tests.

Coverage:
- Migration: jüngster-wins, ant2_calibrated-Markierung, normal_presets,
  Idempotenz, korrupte JSON.
- API: band-only, ant2_calibrated, ts=0.0-Marker.
- Aufrufer-Verträge: _check_diversity_preset prüft ant2_calibrated,
  _on_dx_tune_accepted single-save, _apply_normal_mode robust fallback.
"""

from __future__ import annotations

import inspect
import json
import os
import re
import time
from pathlib import Path
from unittest.mock import MagicMock

import pytest


# ── Helper ──────────────────────────────────────────────────────────


@pytest.fixture
def isolated_tmp(tmp_path, monkeypatch):
    from core import preset_store as ps_mod
    monkeypatch.setattr(ps_mod, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(ps_mod, "CALIB_DIR", tmp_path / "kalibrierung")
    monkeypatch.setattr(ps_mod, "SETTINGS_PATH", tmp_path / "settings.json")
    return ps_mod, tmp_path


# ── Migration ───────────────────────────────────────────────────────


def test_migration_youngest_wins_across_legacy_files(isolated_tmp):
    """Pro Band: MAX(gain_timestamp) wins über alle Quellen."""
    ps_mod, tmp_path = isolated_tmp
    calib = tmp_path / "kalibrierung"
    calib.mkdir(parents=True)
    older = time.time() - 3600
    newer = time.time() - 60
    # std hat 20m mit OLDER, dx hat 20m mit NEWER
    (calib / "presets_standard.json").write_text(json.dumps({
        "20m_FT8": {"ant1_gain": 5, "ant2_gain": 8, "gain_timestamp": older,
                    "measured": "alt", "rxant": "ANT1"}
    }))
    (calib / "presets_dx.json").write_text(json.dumps({
        "20m_FT8": {"ant1_gain": 15, "ant2_gain": 25, "gain_timestamp": newer,
                    "measured": "neu", "rxant": "ANT1"}
    }))
    n = ps_mod.migrate_legacy_files()
    assert n == 1
    data = json.loads((calib / "presets.json").read_text())
    assert data["20m"]["ant1_gain"] == 15  # newer wins
    assert data["20m"]["ant2_gain"] == 25
    assert data["20m"]["ant2_calibrated"] is True


def test_migration_normal_preset_sets_ant2_uncalibrated(isolated_tmp):
    """normal_presets-Migration setzt ant2_gain=0 + ant2_calibrated=False."""
    ps_mod, tmp_path = isolated_tmp
    (tmp_path / "settings.json").write_text(json.dumps({
        "normal_presets": {
            "30m": {"gain": 12, "rxant": "ANT1", "measured": "2026-05-18 10:00"}
        }
    }))
    n = ps_mod.migrate_legacy_files()
    assert n == 1
    data = json.loads((tmp_path / "kalibrierung" / "presets.json").read_text())
    assert data["30m"]["ant1_gain"] == 12
    assert data["30m"]["ant2_gain"] == 0
    assert data["30m"]["ant2_calibrated"] is False


def test_migration_idempotent(isolated_tmp):
    """2. Aufruf = no-op."""
    ps_mod, tmp_path = isolated_tmp
    calib = tmp_path / "kalibrierung"
    calib.mkdir(parents=True)
    (calib / "presets_standard.json").write_text(json.dumps({
        "20m_FT8": {"ant1_gain": 10, "ant2_gain": 20,
                    "gain_timestamp": time.time(),
                    "measured": "?", "rxant": "ANT1"}
    }))
    n1 = ps_mod.migrate_legacy_files()
    n2 = ps_mod.migrate_legacy_files()
    assert n1 == 1
    assert n2 == 0  # idempotent


def test_migration_robust_against_corrupt_json(isolated_tmp):
    """Korrupte JSON-Files werden uebersprungen, kein Crash."""
    ps_mod, tmp_path = isolated_tmp
    calib = tmp_path / "kalibrierung"
    calib.mkdir(parents=True)
    (calib / "presets_standard.json").write_text("{ this is not json ]")
    (calib / "presets_dx.json").write_text(json.dumps({
        "40m_FT8": {"ant1_gain": 10, "ant2_gain": 20,
                    "gain_timestamp": time.time(),
                    "measured": "?", "rxant": "ANT1"}
    }))
    n = ps_mod.migrate_legacy_files()
    # Standard skip, DX migriert
    assert n == 1
    data = json.loads((calib / "presets.json").read_text())
    assert "40m" in data


def test_migration_empty_when_no_files(isolated_tmp):
    """Keine Quellen vorhanden → presets.json wird NICHT geschrieben."""
    ps_mod, tmp_path = isolated_tmp
    n = ps_mod.migrate_legacy_files()
    assert n == 0
    assert not (tmp_path / "kalibrierung" / "presets.json").exists()


def test_migration_normal_preset_unparseable_date_gets_ts_zero(isolated_tmp):
    """normal_preset ohne parsbares measured → ts=0.0 → spaeter is_valid_gain=False."""
    ps_mod, tmp_path = isolated_tmp
    (tmp_path / "settings.json").write_text(json.dumps({
        "normal_presets": {
            "60m": {"gain": 10, "rxant": "ANT1", "measured": "GARBAGE"}
        }
    }))
    ps_mod.migrate_legacy_files()
    data = json.loads((tmp_path / "kalibrierung" / "presets.json").read_text())
    assert data["60m"]["gain_timestamp"] == 0.0
    # Store laden → is_valid_gain False wegen ts=0.0
    store = ps_mod.PresetStore()
    assert store.is_valid_gain("60m") is False


# ── API ─────────────────────────────────────────────────────────────


def test_no_ft_mode_in_assess_gain_signature():
    """mw_radio._assess_gain hat nur band-Parameter."""
    from ui.mw_radio import RadioMixin
    sig = inspect.signature(RadioMixin._assess_gain)
    params = list(sig.parameters.keys())
    assert params == ["self", "band"]


def test_no_ft_mode_in_check_diversity_preset_signature():
    from ui.mw_radio import RadioMixin
    sig = inspect.signature(RadioMixin._check_diversity_preset)
    params = list(sig.parameters.keys())
    assert params == ["self", "band", "scoring"]


def test_no_get_diversity_store_method():
    """P80: _get_diversity_store entfaellt."""
    from ui.mw_radio import RadioMixin
    assert not hasattr(RadioMixin, "_get_diversity_store")


# ── _check_diversity_preset prüft ant2_calibrated (R1-F1 ROT) ───────


def test_check_diversity_preset_blocks_when_ant2_uncalibrated(monkeypatch):
    """R1-F1 ROT: Diversity-Wechsel mit ant2_calibrated=False löst
    Re-Mess aus (DXTuneDialog), NICHT direkten _enable_diversity-Call."""
    from ui.mw_radio import RadioMixin

    obj = MagicMock()
    obj.radio.ip = "192.168.1.100"
    obj._swr_blocked_bands = set()
    obj._enable_diversity = MagicMock()
    obj._start_dx_tuning = MagicMock()
    obj._set_gain_measure_lock = MagicMock()
    obj._update_statusbar = MagicMock()
    obj.statusBar = MagicMock()
    obj.statusBar.return_value.showMessage = MagicMock()
    obj.qso_panel = MagicMock()
    obj._pending_dx_diversity = False
    obj._pending_diversity_scoring = None
    obj._diversity_ctrl = MagicMock()

    # Store hat fresh-Eintrag ABER ant2_calibrated=False
    obj._gain_store = MagicMock()
    obj._gain_store.get = MagicMock(return_value={
        "gain_timestamp": time.time(),
        "ant2_calibrated": False,  # Normal-only-Migration
    })
    obj._gain_store.is_valid_gain = MagicMock(return_value=True)  # fresh
    obj._assess_gain = lambda b: RadioMixin._assess_gain(obj, b)

    # QTimer.singleShot mocken (sofortige Ausführung)
    def fake_ss(msec, cb):
        cb()
    monkeypatch.setattr("PySide6.QtCore.QTimer.singleShot", fake_ss)

    RadioMixin._check_diversity_preset(obj, "30m", "normal")

    # KRITISCH: kein direkter Enable, sondern DXTuneDialog
    obj._enable_diversity.assert_not_called()
    obj._start_dx_tuning.assert_called_once()


def test_check_diversity_preset_proceeds_when_ant2_calibrated_true(monkeypatch):
    """Spiegelbild: fresh + ant2_calibrated=True → _enable_diversity direkt."""
    from ui.mw_radio import RadioMixin

    obj = MagicMock()
    obj.radio.ip = "192.168.1.100"
    obj._swr_blocked_bands = set()
    obj._enable_diversity = MagicMock()
    obj._start_dx_tuning = MagicMock()
    obj._update_statusbar = MagicMock()
    obj.qso_panel = MagicMock()
    obj._diversity_ctrl = MagicMock()
    obj._gain_store = MagicMock()
    obj._gain_store.get = MagicMock(return_value={
        "gain_timestamp": time.time(),
        "ant2_calibrated": True,
    })
    obj._gain_store.is_valid_gain = MagicMock(return_value=True)
    obj._assess_gain = lambda b: RadioMixin._assess_gain(obj, b)

    RadioMixin._check_diversity_preset(obj, "30m", "normal")

    obj._enable_diversity.assert_called_once_with(scoring_mode="normal")
    obj._start_dx_tuning.assert_not_called()


# ── _apply_normal_mode robuster Fallback (R1-F2 ROT) ────────────────


def test_apply_normal_mode_uses_ant1_gain_zero_not_default():
    """R1-F2 ROT: `is not None`-Check statt falsy — ant1_gain=0 ist gueltig."""
    src = (Path(__file__).parent.parent / "ui" / "mw_radio.py").read_text()
    # Methoden-Source extrahieren
    m = re.search(
        r"    def _apply_normal_mode\([^)]*\)[^\n]*:.*?(?=\n    def )",
        src, flags=re.DOTALL)
    assert m, "_apply_normal_mode nicht gefunden"
    body = m.group(0)
    # `is not None`-Check pflicht (statt falsy)
    assert 'ant1_gain") is not None' in body, (
        "P80 R1-F2: `is not None`-Check fehlt"
    )


# ── _on_dx_tune_accepted single-save (R1-F3 ORANGE) ─────────────────


def test_on_dx_tune_accepted_no_dual_store_save():
    """P80: nur 1 save_gain-Call im single-save-Pfad — kein _standard/_dx_store."""
    src = (Path(__file__).parent.parent / "ui" / "mw_radio.py").read_text()
    m = re.search(
        r"    def _on_dx_tune_accepted\([^)]*\)[^\n]*:.*?(?=\n    def )",
        src, flags=re.DOTALL)
    assert m
    body = m.group(0)
    # Keine alten Store-Verweise
    assert "_standard_store.save_gain" not in body
    assert "_dx_store.save_gain" not in body
    # Pflicht: _gain_store.save_gain
    assert "_gain_store.save_gain" in body
    # Pflicht: ant2_calibrated=True
    assert "ant2_calibrated=True" in body


def test_on_dx_tune_accepted_logs_std_dx_divergence():
    """R1-F3 ORANGE: Log-Warning bei Std/DX-Divergenz."""
    src = (Path(__file__).parent.parent / "ui" / "mw_radio.py").read_text()
    m = re.search(
        r"    def _on_dx_tune_accepted\([^)]*\)[^\n]*:.*?(?=\n    def )",
        src, flags=re.DOTALL)
    body = m.group(0)
    assert "Std/DX-Gain-Divergenz" in body


# ── settings.normal_presets gepoppt ─────────────────────────────────


def test_settings_load_pops_normal_presets(tmp_path, monkeypatch):
    from config import settings as st_mod
    monkeypatch.setattr(st_mod, "CONFIG_FILE", tmp_path / "settings.json")
    # File mit normal_presets schreiben
    (tmp_path / "settings.json").write_text(json.dumps({
        "callsign": "DA1MHH",
        "locator": "JN58HM",
        "band": "20m",
        "mode": "FT8",
        "normal_presets": {"20m": {"gain": 12, "rxant": "ANT1"}},
    }))
    s = st_mod.Settings()
    s.load()
    assert "normal_presets" not in s._data


def test_settings_get_normal_preset_deprecated_returns_empty():
    """P80: get_normal_preset ist Stub, returnt leeres dict."""
    from config.settings import Settings
    s = Settings()
    assert s.get_normal_preset("20m") == {}


def test_settings_save_normal_preset_deprecated_noop():
    """P80: save_normal_preset ist no-op."""
    from config.settings import Settings
    s = Settings()
    s.save_normal_preset("20m", gain=15)
    # Kein normal_presets-Eintrag in _data
    assert "normal_presets" not in s._data


# ── Test-Bonus ──────────────────────────────────────────────────────


def test_app_version_p80():
    import main
    # Bundle M bumpt weiter auf 0.97.54
    assert main.APP_VERSION == "0.97.54"


def test_main_window_uses_unified_gain_store():
    """Source-Level: main_window initialisiert _gain_store, nicht _standard/_dx."""
    src = (Path(__file__).parent.parent / "ui" / "main_window.py").read_text()
    assert "self._gain_store = PresetStore()" in src
    assert "self._standard_store = PresetStore(" not in src
    assert "self._dx_store = PresetStore(" not in src
