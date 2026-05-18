"""Smoke-Tests fuer _show_calibration_done.

P79 (v0.97.51): Modal-Dialog komplett entfernt. Diese 3 Tests sind
obsolet — die ehemaligen Dialog-Properties (3000ms-Timer, kein OK-Button,
non-modal) sind durch „kein Dialog ueberhaupt" abgeloest. Die neue
Source-Level-Test-Coverage liegt in `test_p79_ui_bundle.py` (T9-T11).

Hier bleibt nur die Fix-G-Coverage fuer DXTuneDialog erhalten.
"""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QDialog, QPushButton, QLabel,
)


def _ensure_app():
    return QApplication.instance() or QApplication([])


def test_calibration_done_no_dialog_p79():
    """P79: _show_calibration_done erstellt KEINEN QDialog mehr.

    Ersetzt die alten 3 Smoke-Tests (Timer/Button/Modal) — Mike-Wunsch
    18.05.: „seperates info fenster modual weg". Loesung jetzt:
    add_info-Zeile + Statusbar-Echo, kein Dialog.
    """
    _ensure_app()

    from ui.mw_radio import RadioMixin
    from unittest.mock import MagicMock

    mw = QMainWindow()
    mw.qso_panel = MagicMock()
    # statusBar() von QMainWindow ist real verfuegbar — kein Mock noetig
    RadioMixin._show_calibration_done(mw, "20m", 20, 0)

    # KEIN QDialog darf erzeugt worden sein
    dialogs = mw.findChildren(QDialog)
    assert len(dialogs) == 0, (
        f"P79: Dialog-Erzeugung verboten, gefunden: {len(dialogs)}"
    )

    # qso_panel.add_info MUSS aufgerufen worden sein
    mw.qso_panel.add_info.assert_called_once()
    args = mw.qso_panel.add_info.call_args[0]
    assert args[0].startswith("✓ Kalibrierung 20m gespeichert.")


# ── Fix G v0.86 — Falscher Kalibrierungstext im Normal-Modus ─────────────────

def test_dxtune_mode_label_normal_modus():
    """Fix G: DXTuneDialog mit rx_mode='normal' → Titel 'Gain-Messung', kein 'Diversity'."""
    _ensure_app()

    from ui.dx_tune_dialog import DXTuneDialog

    class _FakeRadio:
        ip = ""
        def set_rx_antenna(self, ant): pass
        def set_rfgain(self, g): pass
        def set_tx_antenna(self, ant): pass
        def ptt_off(self): pass

    dlg = DXTuneDialog(_FakeRadio(), "20m", scoring_mode="stations", rx_mode="normal")
    assert dlg._get_mode_label() == "Gain-Messung"
    assert "Gain-Messung" in dlg.windowTitle()
    assert "Diversity" not in dlg.windowTitle()
    dlg.deleteLater()


def test_dxtune_mode_label_diversity_modus():
    """Fix G: DXTuneDialog mit rx_mode='diversity' → 'Diversity Standard' oder 'Diversity DX'."""
    _ensure_app()

    from ui.dx_tune_dialog import DXTuneDialog

    class _FakeRadio:
        ip = ""
        def set_rx_antenna(self, ant): pass
        def set_rfgain(self, g): pass
        def set_tx_antenna(self, ant): pass
        def ptt_off(self): pass

    dlg_std = DXTuneDialog(_FakeRadio(), "40m", scoring_mode="stations", rx_mode="diversity")
    assert dlg_std._get_mode_label() == "Diversity Standard"
    assert "Diversity Standard" in dlg_std.windowTitle()
    dlg_std.deleteLater()

    dlg_dx = DXTuneDialog(_FakeRadio(), "40m", scoring_mode="snr", rx_mode="diversity")
    assert dlg_dx._get_mode_label() == "Diversity DX"
    assert "Diversity DX" in dlg_dx.windowTitle()
    dlg_dx.deleteLater()
