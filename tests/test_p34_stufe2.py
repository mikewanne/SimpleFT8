"""Tests fuer P34-Stufe2 (v0.97.19) — Statik-Ratio-Pipeline entfernt.

Sicherstellen dass die Statik-API nicht versehentlich wieder reinkommt
und die neue Dynamic-Default-Logik funktioniert.
"""

import os
import sys
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


# ── T1-T4: Statik-API ist weg ──────────────────────────────────────────


def test_no_measure_phase_constants():
    """T1: DiversityController hat kein MEASURE_CYCLES / EARLY_STOP_* mehr."""
    from core.diversity import DiversityController
    dc = DiversityController()
    assert not hasattr(dc, 'MEASURE_CYCLES')
    assert not hasattr(dc, 'EARLY_STOP_FRACTION')
    assert not hasattr(dc, 'EARLY_STOP_THRESHOLD')
    assert not hasattr(dc, 'REMEASURE_INTERVAL_SECONDS')
    assert not hasattr(dc, '_measurements')
    assert not hasattr(dc, '_measure_step')
    assert not hasattr(dc, '_phase')
    assert not hasattr(dc, '_last_measured_at')
    assert not hasattr(dc, '_was_early_stopped')


def test_no_should_remeasure():
    """T2: should_remeasure Methode existiert nicht mehr."""
    from core.diversity import DiversityController
    dc = DiversityController()
    assert not hasattr(dc, 'should_remeasure')


def test_no_record_measurement_evaluate_etc():
    """T3: record_measurement, _evaluate, _check_phase3_early_stop,
    can_measure, on_band_change, start_measure, on_operate_cycle
    von Statik-Mess-Pipeline alle weg.
    """
    from core.diversity import DiversityController
    dc = DiversityController()
    assert not hasattr(dc, 'record_measurement')
    assert not hasattr(dc, '_evaluate')
    assert not hasattr(dc, '_check_phase3_early_stop')
    assert not hasattr(dc, 'can_measure')
    assert not hasattr(dc, 'on_band_change')
    assert not hasattr(dc, 'start_measure')
    # on_operate_cycle bleibt — inkrementiert Pattern-Counter
    assert hasattr(dc, 'on_operate_cycle')


def test_no_phase_property():
    """T4: phase / measure_step / operate_cycles / seconds_until_remeasure
    / dynamic_active Properties weg.
    """
    from core.diversity import DiversityController
    dc = DiversityController()
    assert not hasattr(dc, 'phase')
    assert not hasattr(dc, 'measure_step')
    assert not hasattr(dc, 'operate_cycles')
    assert not hasattr(dc, 'seconds_until_remeasure')
    assert not hasattr(dc, 'dynamic_active')


# ── T5-T6: Dynamic-Default bei Diversity-Mode ────────────────────────


def test_no_dynamic_diversity_enabled():
    """T5: Settings.dynamic_diversity_enabled Property entfernt."""
    from config.settings import Settings
    s = Settings()
    assert not hasattr(s, 'dynamic_diversity_enabled')


def test_no_save_diversity_preset():
    """T6: Settings.save_diversity_preset + get_diversity_preset weg."""
    from config.settings import Settings
    s = Settings()
    assert not hasattr(s, 'save_diversity_preset')
    assert not hasattr(s, 'get_diversity_preset')


# ── T7-T8: PresetStore Ratio-API weg ────────────────────────────────


def test_no_preset_ratio_methods(tmp_path, monkeypatch):
    """T7: PresetStore hat kein commit_with_ratio, save_ratio,
    is_valid_ratio, get_ratio_age_minutes.
    """
    from core import preset_store as ps_mod
    monkeypatch.setattr(ps_mod, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(ps_mod, "CALIB_DIR", tmp_path / "kalibrierung")
    store = ps_mod.PresetStore("presets_standard.json")
    assert not hasattr(store, 'commit_with_ratio')
    assert not hasattr(store, 'save_ratio')
    assert not hasattr(store, 'is_valid_ratio')
    assert not hasattr(store, 'get_ratio_age_minutes')


def test_commit_gain_replaces_commit_with_ratio(tmp_path, monkeypatch):
    """T8: commit_gain (P34-Stufe2-API) persistiert staged Gain ohne Ratio."""
    from core import preset_store as ps_mod
    monkeypatch.setattr(ps_mod, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(ps_mod, "CALIB_DIR", tmp_path / "kalibrierung")
    store = ps_mod.PresetStore("presets_standard.json")
    store.stage_gain("40m", "FT8", rxant="ANT1",
                     ant1_gain=10, ant2_gain=20)
    assert store.commit_gain("40m", "FT8") is True
    entry = store.get("40m", "FT8")
    assert "gain_timestamp" in entry
    # Kein Ratio-Feld (Stufe2)
    assert "ratio" not in entry


# ── T9: mess_status_dialog Modul ist weg ───────────────────────────────


def test_no_mess_status_dialog_module():
    """T9: ui.mess_status_dialog Modul wurde geloescht."""
    with pytest.raises(ImportError):
        import ui.mess_status_dialog  # noqa: F401


# ── T10-T11: MainWindow-API ────────────────────────────────────────────


def test_no_apply_dynamic_toggle_in_mainwindow():
    """T10: MainWindow._apply_dynamic_toggle entfernt."""
    from ui.main_window import MainWindow
    assert not hasattr(MainWindow, '_apply_dynamic_toggle')


def test_no_handle_diversity_measure_in_mainwindow():
    """T11: _handle_diversity_measure (im CycleMixin) entfernt."""
    from ui.mw_cycle import CycleMixin
    assert not hasattr(CycleMixin, '_handle_diversity_measure')


# ── T12: choose() liefert nur Operate-Pattern ──────────────────────────


def test_choose_returns_operate_pattern_only():
    """T12: choose() liefert 50:50 / 70:30 / 30:70 Pattern (kein measure)."""
    from core.diversity import DiversityController
    dc = DiversityController()
    dc.ratio = "70:30"
    dc._operate_cycles = 0
    # 6-Slot-Pattern
    assert dc.choose() == "A1"
    dc._operate_cycles = 1
    assert dc.choose() == "A1"
    dc._operate_cycles = 2
    assert dc.choose() == "A2"  # 4xA1 / 2xA2


# ── T13-T14: _enable_diversity + Deferred-Init (R1-F1) ─────────────────


def test_enable_diversity_deferred_when_no_radio():
    """T13 (R1-F1): radio.ip=None → _pending_diversity_init gesetzt, KEIN
    _dynamic_ctrl.activate() aufgerufen.
    """
    from ui.mw_radio import RadioMixin

    fake_self = MagicMock()
    fake_self.radio = MagicMock()
    fake_self.radio.ip = None  # KEIN Radio
    fake_self.settings = MagicMock()
    fake_self.settings.band = "40m"
    fake_self.settings.mode = "FT8"
    fake_self.rx_panel = MagicMock()
    fake_self.rx_panel.table = MagicMock()
    fake_self._diversity_lock = MagicMock()
    fake_self._diversity_lock.__enter__ = MagicMock(return_value=None)
    fake_self._diversity_lock.__exit__ = MagicMock(return_value=False)
    fake_self._diversity_ctrl = MagicMock()
    fake_self._dynamic_ctrl = MagicMock()
    fake_self.qso_panel = MagicMock()
    fake_self.control_panel = MagicMock()

    RadioMixin._enable_diversity(fake_self, "normal")

    assert fake_self._pending_diversity_init == "normal"
    fake_self._dynamic_ctrl.activate.assert_not_called()


def test_enable_diversity_activates_dynamic_when_radio_connected():
    """T14: radio.ip gesetzt → Dynamic.activate() wird aufgerufen."""
    from ui.mw_radio import RadioMixin

    fake_self = MagicMock()
    fake_self.radio = MagicMock()
    fake_self.radio.ip = "192.168.1.10"
    fake_self.settings = MagicMock()
    fake_self.settings.band = "40m"
    fake_self.settings.mode = "FT8"
    fake_self.rx_panel = MagicMock()
    fake_self.rx_panel.table = MagicMock()
    fake_self._diversity_lock = MagicMock()
    fake_self._diversity_lock.__enter__ = MagicMock(return_value=None)
    fake_self._diversity_lock.__exit__ = MagicMock(return_value=False)
    fake_self._diversity_ctrl = MagicMock()
    fake_self._dynamic_ctrl = MagicMock()
    fake_self.qso_panel = MagicMock()
    fake_self.control_panel = MagicMock()

    RadioMixin._enable_diversity(fake_self, "dx")

    fake_self._dynamic_ctrl.reset.assert_called_once()
    fake_self._dynamic_ctrl.activate.assert_called_once()


def test_disable_diversity_deactivates_dynamic():
    """T15: _disable_diversity ruft _dynamic_ctrl.deactivate()."""
    from ui.mw_radio import RadioMixin

    fake_self = MagicMock()
    fake_self.settings = MagicMock()
    fake_self.settings.band = "40m"
    fake_self.settings.mode = "FT8"
    fake_self.rx_panel = MagicMock()
    fake_self.rx_panel.table = MagicMock()
    fake_self._diversity_ctrl = MagicMock()
    fake_self._dynamic_ctrl = MagicMock()
    fake_self._dynamic_ctrl.is_active = MagicMock(return_value=True)
    fake_self.qso_panel = MagicMock()
    fake_self.control_panel = MagicMock()
    fake_self._standard_store = None
    fake_self._dx_store = None

    RadioMixin._disable_diversity(fake_self)

    fake_self._dynamic_ctrl.deactivate.assert_called_once()
