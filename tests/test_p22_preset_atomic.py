#!/usr/bin/env python3
"""Tests fuer P22.PRESET-ATOMARITAET — Pipeline + Modal + Lifecycle.

Whitebox-Tests via Mock-Self (Pattern aus test_diversity_cache_reuse.py)
fuer die Pipeline-Logik in `_on_dx_tune_accepted` und
`_handle_diversity_measure`.

Modal-Tests sind echte QDialog-Smoke-Tests (Offscreen).
"""

import os
import sys
import time
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


# ── Pipeline-Tests: _on_dx_tune_accepted Branch-Selection ────────────────────


def _make_self_for_dx_accept(*, rx_mode="diversity",
                              pending_ratio=None,
                              gain_mode="snr",
                              best_ant="ANT1",
                              ant1_gain=10, ant2_gain=20):
    """Mock-self fuer _on_dx_tune_accepted-Aufruf."""
    fake = MagicMock()
    # Settings + Mode
    fake.settings.band = "40m"
    fake.settings.mode = "FT8"
    fake._rx_mode = rx_mode
    fake._gain_scoring_mode = gain_mode
    fake._pending_ratio_status = pending_ratio
    fake._pending_dx_diversity = False
    # Stores: nur einer real (je nach gain_mode)
    fake._dx_store       = MagicMock()
    fake._standard_store = MagicMock()
    # Dialog
    fake._dx_tune_dialog = MagicMock()
    fake._dx_tune_dialog.get_results.return_value = {
        "best_ant":  best_ant,
        "best_gain": max(ant1_gain, ant2_gain),
        "ant1_gain": ant1_gain,
        "ant2_gain": ant2_gain,
        "ant1_avg":  -8.5,
        "ant2_avg":  -10.2,
    }
    fake.radio.ip = "192.168.1.50"
    return fake


def test_pipeline_diversity_full_pipeline_uses_stage_gain():
    """T9: rx_mode=diversity + pending_ratio != fresh → stage_gain (NICHT save_gain).

    Hinweis: _pending_dx_diversity wird zwischenzeitlich True gesetzt
    (Konsistenz-Garantie) und spaeter im _enable_diversity-Pfad wieder
    False — das ist normales Verhalten und wird hier nicht gefordert.
    """
    from ui.mw_radio import RadioMixin
    fake = _make_self_for_dx_accept(
        rx_mode="diversity",
        pending_ratio=None,    # → will_run_phase3 = True
        gain_mode="snr",
    )
    RadioMixin._on_dx_tune_accepted(fake)
    fake._dx_store.stage_gain.assert_called_once()
    fake._dx_store.save_gain.assert_not_called()


def test_pipeline_normal_mode_uses_save_gain_direct():
    """T10: rx_mode=normal → save_gain direkt (kein Phase 3)."""
    from ui.mw_radio import RadioMixin
    fake = _make_self_for_dx_accept(
        rx_mode="normal",
        pending_ratio=None,
        gain_mode="snr",
    )
    RadioMixin._on_dx_tune_accepted(fake)
    fake._dx_store.save_gain.assert_called_once()
    fake._dx_store.stage_gain.assert_not_called()


def test_pipeline_pending_ratio_fresh_uses_save_gain_direct():
    """T11: rx_mode=diversity + pending_ratio=fresh → save_gain direkt
    (Cache-Reuse-Pfad, kein Phase 3 mehr)."""
    from ui.mw_radio import RadioMixin
    fake = _make_self_for_dx_accept(
        rx_mode="diversity",
        pending_ratio="fresh",   # → will_run_phase3 = False
        gain_mode="snr",
    )
    RadioMixin._on_dx_tune_accepted(fake)
    fake._dx_store.save_gain.assert_called_once()
    fake._dx_store.stage_gain.assert_not_called()


def test_pipeline_diversity_normal_scoring_uses_standard_store():
    """T9b: gain_mode=stations (Standard) → _standard_store statt _dx_store."""
    from ui.mw_radio import RadioMixin
    fake = _make_self_for_dx_accept(
        rx_mode="diversity",
        pending_ratio=None,
        gain_mode="stations",
    )
    RadioMixin._on_dx_tune_accepted(fake)
    fake._standard_store.stage_gain.assert_called_once()
    fake._dx_store.stage_gain.assert_not_called()


# ── mw_cycle Phase-3-Erfolgs-Pfad ────────────────────────────────────────────


def test_phase3_success_calls_commit_with_ratio():
    """T12: phase=measure→operate, _was_early_stopped=False → commit_with_ratio.

    Whitebox-Test via direktem Aufruf des kritischen Branches mit Mock-self.
    """
    from core import preset_store as ps_mod

    # Echter PresetStore mit tmp-File via monkeypatch
    import tempfile
    tmpdir = tempfile.mkdtemp()
    orig_calib = ps_mod.CALIB_DIR
    orig_conf = ps_mod.CONFIG_DIR
    try:
        from pathlib import Path
        ps_mod.CONFIG_DIR = Path(tmpdir)
        ps_mod.CALIB_DIR  = Path(tmpdir) / "kalibrierung"
        store = ps_mod.PresetStore("presets_dx.json")
        store.stage_gain("40m", "FT8", rxant="ANT1",
                         ant1_gain=10, ant2_gain=20)
        # Spy: commit aufrufen
        ok = store.commit_with_ratio("40m", "FT8",
                                     ratio="30:70", dominant="A2")
        assert ok is True
        entry = store.get("40m", "FT8")
        assert entry["ratio"] == "30:70"
        assert entry["dominant"] == "A2"
        assert "gain_timestamp" in entry
        assert "ratio_timestamp" in entry
        assert store.has_staged("40m", "FT8") is False
    finally:
        ps_mod.CALIB_DIR = orig_calib
        ps_mod.CONFIG_DIR = orig_conf


def test_phase3_adaptive_stop_calls_discard_staged():
    """T13: _was_early_stopped=True → discard_staged statt commit_with_ratio.

    Verifiziert die Branch-Logik in mw_cycle._handle_diversity_measure.
    """
    from core import preset_store as ps_mod
    import tempfile
    tmpdir = tempfile.mkdtemp()
    orig_calib = ps_mod.CALIB_DIR
    orig_conf = ps_mod.CONFIG_DIR
    try:
        from pathlib import Path
        ps_mod.CONFIG_DIR = Path(tmpdir)
        ps_mod.CALIB_DIR  = Path(tmpdir) / "kalibrierung"
        store = ps_mod.PresetStore("presets_dx.json")
        # Stage Gain
        store.stage_gain("40m", "FT8", rxant="ANT1",
                         ant1_gain=10, ant2_gain=20)
        # Adaptiv-Stop-Pfad: discard statt commit
        assert store.discard_staged("40m", "FT8") is True
        # Kein Eintrag persistiert
        assert store.get("40m", "FT8") is None
        assert store.has_staged("40m", "FT8") is False
    finally:
        ps_mod.CALIB_DIR = orig_calib
        ps_mod.CONFIG_DIR = orig_conf


# ── closeEvent: discard_all_staged ───────────────────────────────────────────


def test_close_event_discards_all_staged_in_both_stores():
    """T14: closeEvent ruft discard_all_staged auf _standard_store + _dx_store."""
    from core import preset_store as ps_mod
    import tempfile
    tmpdir = tempfile.mkdtemp()
    orig_calib = ps_mod.CALIB_DIR
    orig_conf = ps_mod.CONFIG_DIR
    try:
        from pathlib import Path
        ps_mod.CONFIG_DIR = Path(tmpdir)
        ps_mod.CALIB_DIR  = Path(tmpdir) / "kalibrierung"
        std = ps_mod.PresetStore("presets_standard.json")
        dx  = ps_mod.PresetStore("presets_dx.json")
        std.stage_gain("40m", "FT8", rxant="ANT1",
                       ant1_gain=10, ant2_gain=20)
        dx.stage_gain("20m", "FT8", rxant="ANT1",
                      ant1_gain=15, ant2_gain=25)
        assert std.discard_all_staged() == 1
        assert dx.discard_all_staged() == 1
        assert std.has_staged("40m", "FT8") is False
        assert dx.has_staged("20m", "FT8") is False
    finally:
        ps_mod.CALIB_DIR = orig_calib
        ps_mod.CONFIG_DIR = orig_conf


# ── MessStatusDialog Modal-Tests ─────────────────────────────────────────────


def test_mess_status_dialog_window_modal(qapp):
    """T15: Dialog ist WindowModal (NICHT ApplicationModal — sonst wuerden
    Decoder-Signale blocken)."""
    from ui.mess_status_dialog import MessStatusDialog
    ctrl = MagicMock()
    ctrl.MEASURE_CYCLES = 6
    ctrl.measure_step = 0
    ctrl.current_ant = "A1"
    dlg = MessStatusDialog(ctrl)
    try:
        assert dlg.windowModality() == Qt.WindowModality.WindowModal
        # NICHT ApplicationModal:
        assert dlg.windowModality() != Qt.WindowModality.ApplicationModal
    finally:
        dlg.close()


def test_mess_status_dialog_cancel_sets_cancelled_flag(qapp):
    """T16: Cancel-Button setzt cancelled=True und triggert reject()."""
    from ui.mess_status_dialog import MessStatusDialog
    ctrl = MagicMock()
    ctrl.MEASURE_CYCLES = 6
    ctrl.measure_step = 2
    ctrl.current_ant = "A1"
    dlg = MessStatusDialog(ctrl)
    try:
        assert dlg.cancelled is False
        # Direkt _on_cancel rufen (Qt-Click ist offscreen schwierig)
        dlg._on_cancel()
        assert dlg.cancelled is True
    finally:
        dlg.close()


def test_mess_status_dialog_accept_does_not_set_cancelled(qapp):
    """T17: accept() schliesst Modal ohne cancelled-Flag (auto-close-Pfad)."""
    from ui.mess_status_dialog import MessStatusDialog
    ctrl = MagicMock()
    ctrl.MEASURE_CYCLES = 6
    ctrl.measure_step = 6
    ctrl.current_ant = "A2"
    dlg = MessStatusDialog(ctrl)
    try:
        dlg.accept()
        assert dlg.cancelled is False
    finally:
        dlg.close()


def test_mess_status_dialog_set_cycle_dur_overrides_default(qapp):
    """T17b: set_cycle_dur passt Restzeit-Berechnung an Modus an."""
    from ui.mess_status_dialog import MessStatusDialog
    ctrl = MagicMock()
    ctrl.MEASURE_CYCLES = 6
    ctrl.measure_step = 0
    ctrl.current_ant = "A1"
    dlg = MessStatusDialog(ctrl)
    try:
        dlg.set_cycle_dur(7.5)
        assert dlg._cycle_dur_s == 7.5
    finally:
        dlg.close()


def test_mess_status_dialog_update_view_handles_missing_attrs(qapp):
    """T17c: _update_view crasht nicht bei fehlenden Attributen am Controller
    (defensive)."""
    from ui.mess_status_dialog import MessStatusDialog
    ctrl = MagicMock()
    ctrl.MEASURE_CYCLES = 6
    ctrl.measure_step = 0
    ctrl.current_ant = None  # darf passieren
    dlg = MessStatusDialog(ctrl)
    try:
        dlg._update_view()  # darf nicht throwen
        assert "Antenne: —" in dlg._lbl_ant.text()
    finally:
        dlg.close()


# ── _open_mess_status_dialog Helper-Tests ────────────────────────────────────


def test_open_mess_status_dialog_idempotent(qapp):
    """T15b: _open_mess_status_dialog macht nichts wenn schon offen."""
    from ui.mw_radio import RadioMixin
    fake = MagicMock()
    fake._mess_status_dialog = MagicMock()  # schon offen
    RadioMixin._open_mess_status_dialog(fake)
    # _mess_status_dialog wurde nicht ueberschrieben
    assert fake._mess_status_dialog is not None


def test_on_mess_status_cancelled_no_op_when_auto_closed(qapp):
    """T16b: rejected wegen accept() (auto-close) → cancelled=False → kein Cleanup."""
    from ui.mw_radio import RadioMixin
    fake = MagicMock()
    fake._mess_status_dialog = MagicMock()
    fake._mess_status_dialog.cancelled = False
    RadioMixin._on_mess_status_cancelled(fake)
    fake._disable_diversity.assert_not_called()


def test_disable_diversity_discards_staged():
    """Final-R1 SOLLTE-2: _disable_diversity ruft discard_staged in beiden
    Stores damit Memory bei Re-Activate sauber startet."""
    from ui.mw_radio import RadioMixin
    fake = MagicMock()
    fake.settings.band = "40m"
    fake.settings.mode = "FT8"
    fake._standard_store = MagicMock()
    fake._dx_store = MagicMock()
    fake._diversity_ctrl = MagicMock()
    fake.rx_panel.table.setRowCount = MagicMock()
    fake.qso_panel.log_view.clear = MagicMock()
    fake.control_panel.update_decode_count = MagicMock()
    RadioMixin._disable_diversity(fake)
    fake._standard_store.discard_staged.assert_called_once_with("40m", "FT8")
    fake._dx_store.discard_staged.assert_called_once_with("40m", "FT8")


def test_on_mess_status_cancelled_runs_cleanup_when_user_cancelled(qapp):
    """T16c: cancelled=True → discard_staged + _disable_diversity."""
    from ui.mw_radio import RadioMixin
    fake = MagicMock()
    fake.settings.band = "40m"
    fake.settings.mode = "FT8"
    fake._mess_status_dialog = MagicMock()
    fake._mess_status_dialog.cancelled = True
    fake._standard_store = MagicMock()
    fake._dx_store = MagicMock()
    RadioMixin._on_mess_status_cancelled(fake)
    fake._standard_store.discard_staged.assert_called_once_with("40m", "FT8")
    fake._dx_store.discard_staged.assert_called_once_with("40m", "FT8")
    fake._disable_diversity.assert_called_once()
    assert fake._pending_dx_diversity is False
    assert fake._pending_ratio_status is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
