#!/usr/bin/env python3
"""Tests fuer P51 (v0.97.28) — Gain-Messung vereinheitlichen.

1 Messung (8 Zyklen Rohdaten) → 2 Auswertungen (Standard zaehlt Stationen,
DX zaehlt SNR) → beide Stores atomar gespeichert.

T1   _finish produziert beide Sub-Saetze (standard + dx)
T2   Top-Level spiegelt aktiven scoring_mode (Backwards-Compat)
T3   Std vs DX waehlen unterschiedlichen Gain bei divergenten Daten
T4   _on_dx_tune_accepted Dual-Save bei has_dual=True
T5   _on_dx_tune_accepted Fallback bei has_dual=False (R1-F4 Anti-Korruption)
T6   Beide Stores valid nach erfolgreichem Doppel-Save
T7   settings.save_dx_preset wird NICHT mehr gerufen (R1-F6)
T8   Backward-Compat Top-Level-Keys vorhanden
T9   Helper _best_for returnt dict mit gain+avg+count
"""

import os
import sys
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def _make_dialog(qapp, scoring_mode="snr"):
    """DXTuneDialog-Instanz fuer Tests. Radio-Mock, kein UI."""
    from ui.dx_tune_dialog import DXTuneDialog
    radio = MagicMock()
    radio.set_rx_antenna = MagicMock()
    radio.set_rfgain = MagicMock()
    radio.set_tx_antenna = MagicMock()
    dlg = DXTuneDialog(radio, "20m", scoring_mode=scoring_mode, rx_mode="diversity")
    return dlg


def _fill_diverging_phase_data(dlg):
    """Synthetisches _phase_data wo Std (=Stationen) und DX (=SNR) unterschied-
    liche Gain-Optima haben.

    ANT1 Gain 10: viele Stationen, schwacher SNR  → Std waehlt G10, DX waehlt G20
    ANT1 Gain 20: wenig Stationen, starker SNR
    """
    dlg._phase_data = {
        ("ANT1", 10): [-15.0, -14.0, -13.0, -12.0, -11.0, -10.0, -9.0, -8.0],  # 8 St., Top-5 avg ~-10
        ("ANT1", 20): [+5.0, +6.0, +7.0],                                       # 3 St., Top-5 avg ~+6
        ("ANT2", 10): [-12.0, -11.0, -10.0, -9.0, -8.0],                       # 5 St., Top-5 avg ~-10
        ("ANT2", 20): [+8.0, +9.0],                                             # 2 St., Top-5 avg ~+8.5
    }


# ── T1: Both sub-results ─────────────────────────────────────────────


def test_t1_finish_produces_both_results(qapp):
    """_finish baut self._results mit 'standard' + 'dx' Sub-Keys."""
    dlg = _make_dialog(qapp, scoring_mode="snr")
    try:
        _fill_diverging_phase_data(dlg)
        # _finish ruft set_rx_antenna etc. — Mock-Radio ist sicher
        with patch.object(dlg, "accept"):
            dlg._finish()
        r = dlg.get_results()
        assert "standard" in r, f"'standard' fehlt: {list(r.keys())}"
        assert "dx" in r, f"'dx' fehlt: {list(r.keys())}"
        for key in ("ant1_gain", "ant2_gain", "ant1_avg", "ant2_avg",
                    "best_ant", "best_gain"):
            assert key in r["standard"], f"std fehlt {key}"
            assert key in r["dx"], f"dx fehlt {key}"
    finally:
        dlg.deleteLater()


# ── T2: Top-Level spiegelt scoring_mode ──────────────────────────────


def test_t2_toplevel_mirrors_scoring_mode_dx(qapp):
    """scoring_mode='snr' → Top-Level == r['dx']."""
    dlg = _make_dialog(qapp, scoring_mode="snr")
    try:
        _fill_diverging_phase_data(dlg)
        with patch.object(dlg, "accept"):
            dlg._finish()
        r = dlg.get_results()
        assert r["ant1_gain"] == r["dx"]["ant1_gain"]
        assert r["best_ant"] == r["dx"]["best_ant"]
    finally:
        dlg.deleteLater()


def test_t2b_toplevel_mirrors_scoring_mode_standard(qapp):
    """scoring_mode='stations' → Top-Level == r['standard']."""
    dlg = _make_dialog(qapp, scoring_mode="stations")
    try:
        _fill_diverging_phase_data(dlg)
        with patch.object(dlg, "accept"):
            dlg._finish()
        r = dlg.get_results()
        assert r["ant1_gain"] == r["standard"]["ant1_gain"]
        assert r["best_ant"] == r["standard"]["best_ant"]
    finally:
        dlg.deleteLater()


# ── T3: Divergenz Std vs DX ──────────────────────────────────────────


def test_t3_divergent_optima(qapp):
    """Bei divergenten Daten waehlen Std und DX unterschiedlichen Gain."""
    dlg = _make_dialog(qapp, scoring_mode="snr")
    try:
        _fill_diverging_phase_data(dlg)
        with patch.object(dlg, "accept"):
            dlg._finish()
        r = dlg.get_results()
        # ANT1: Std waehlt 10 (mehr Stationen), DX waehlt 20 (besserer SNR)
        assert r["standard"]["ant1_gain"] == 10, (
            f"Std-ANT1 erwartet 10, got {r['standard']['ant1_gain']}"
        )
        assert r["dx"]["ant1_gain"] == 20, (
            f"DX-ANT1 erwartet 20, got {r['dx']['ant1_gain']}"
        )
    finally:
        dlg.deleteLater()


# ── T4/T5: mw_radio _on_dx_tune_accepted ─────────────────────────────


def _make_mw_self_for_accepted(has_dual=True):
    """P80: 1 unified _gain_store statt 2."""
    self = MagicMock()
    self.settings.band = "20m"
    self.settings.mode = "FT8"
    self._gain_scoring_mode = "snr"
    self._rx_mode = "diversity"
    # P80: 1 Store
    self._gain_store = MagicMock()
    self._gain_store.save_gain = MagicMock(return_value=True)
    self.radio.ip = ""  # kein Normal-Pfad-Trigger
    # Dialog-Mock
    self._dx_tune_dialog = MagicMock()
    if has_dual:
        self._dx_tune_dialog.get_results.return_value = {
            "standard": {
                "ant1_gain": 10, "ant2_gain": 10,
                "ant1_avg": -5.0, "ant2_avg": -4.0,
                "best_ant": "ANT2", "best_gain": 10,
            },
            "dx": {
                "ant1_gain": 20, "ant2_gain": 20,
                "ant1_avg": 6.0, "ant2_avg": 8.0,
                "best_ant": "ANT2", "best_gain": 20,
            },
            # Top-Level Spiegel (aktiv = snr → dx)
            "ant1_gain": 20, "ant2_gain": 20,
            "ant1_avg": 6.0, "ant2_avg": 8.0,
            "best_ant": "ANT2", "best_gain": 20,
        }
    else:
        # Alter Dialog-Stil ohne sub-keys
        self._dx_tune_dialog.get_results.return_value = {
            "ant1_gain": 15, "ant2_gain": 15,
            "ant1_avg": 0.0, "ant2_avg": 0.0,
            "best_ant": "ANT1", "best_gain": 15,
        }
    return self


def test_t4_dual_save_both_stores(qapp):
    """P80: has_dual=True → single-save in _gain_store mit std-Werten
    (R1-F3: stds Stations-Scoring ist immer verfuegbar).
    """
    from ui.mw_radio import RadioMixin
    self = _make_mw_self_for_accepted(has_dual=True)
    RadioMixin._on_dx_tune_accepted(self)
    assert self._gain_store.save_gain.called
    args, kwargs = self._gain_store.save_gain.call_args
    # P80: std-Werte (Stations-Scoring) werden gespeichert
    assert kwargs["ant1_gain"] == 10  # std-Wert (nicht 20=dx)
    assert kwargs["ant2_gain"] == 10
    assert kwargs["ant1_avg"] == -5.0
    assert kwargs["ant2_calibrated"] is True


def test_t5_fallback_single_save_no_corruption(qapp):
    """P80: has_dual=False → save mit Top-Level-Werten."""
    from ui.mw_radio import RadioMixin
    self = _make_mw_self_for_accepted(has_dual=False)
    RadioMixin._on_dx_tune_accepted(self)
    assert self._gain_store.save_gain.called
    args, kwargs = self._gain_store.save_gain.call_args
    assert kwargs["ant1_gain"] == 15


def test_t6_both_stores_called_with_correct_band_mode(qapp):
    """P80: save_gain bekommt band only (kein ft_mode)."""
    from ui.mw_radio import RadioMixin
    self = _make_mw_self_for_accepted(has_dual=True)
    RadioMixin._on_dx_tune_accepted(self)
    args, kwargs = self._gain_store.save_gain.call_args
    assert args == ("20m",)  # nur band


# ── T7: save_dx_preset NICHT mehr gerufen (R1-F6) ────────────────────


def test_t7_settings_save_dx_preset_not_called(qapp):
    """R1-F6: settings.save_dx_preset ist tote API → keine Aufrufe mehr."""
    from ui.mw_radio import RadioMixin
    self = _make_mw_self_for_accepted(has_dual=True)
    RadioMixin._on_dx_tune_accepted(self)
    assert not self.settings.save_dx_preset.called, (
        "settings.save_dx_preset wurde gerufen — sollte tote API sein (R1-F6)"
    )


# ── T8: Backwards-Compat Top-Level-Keys ──────────────────────────────


def test_t8_backwards_compat_toplevel_keys(qapp):
    """get_results() hat weiter Top-Level-Keys fuer alten Code."""
    dlg = _make_dialog(qapp, scoring_mode="snr")
    try:
        _fill_diverging_phase_data(dlg)
        with patch.object(dlg, "accept"):
            dlg._finish()
        r = dlg.get_results()
        for key in ("ant1_gain", "ant2_gain", "ant1_avg", "ant2_avg",
                    "best_ant", "best_gain"):
            assert key in r, f"Top-Level-Key {key} fehlt — Backwards-Compat broken"
    finally:
        dlg.deleteLater()


# ── T9: Helper _best_for returnt dict ────────────────────────────────


def test_t9_best_for_returns_dict(qapp):
    """Helper _best_for liefert dict mit gain/avg/count fuer Display."""
    dlg = _make_dialog(qapp, scoring_mode="snr")
    try:
        _fill_diverging_phase_data(dlg)
        result_std = dlg._best_for("ANT1", use_snr=False)
        result_dx  = dlg._best_for("ANT1", use_snr=True)
        for r in (result_std, result_dx):
            assert isinstance(r, dict)
            assert "gain" in r
            assert "avg" in r
            assert "count" in r
        # Std waehlt Gain 10 (mehr Stationen)
        assert result_std["gain"] == 10
        # DX waehlt Gain 20 (besserer SNR)
        assert result_dx["gain"] == 20
    finally:
        dlg.deleteLater()
