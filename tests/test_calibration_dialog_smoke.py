"""Smoke-Tests fuer _show_calibration_done Auto-Close (Fix F v0.83).

Prueft:
- QTimer wird mit 3000ms als Child von dlg gestartet
  (R1-Final-Review-Fix: kein parentless singleShot).
- Dialog hat KEINEN OK-Button mehr.
- Dialog ist non-modal (setModal nicht True gesetzt).
"""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QDialog, QPushButton, QLabel,
)


def _ensure_app():
    return QApplication.instance() or QApplication([])


def test_calibration_done_starts_3000ms_timer():
    """Fix F: QTimer mit 3000ms wird auf dlg als Parent gestartet.

    R1-Final-Review-Fix: Timer ist Child von dlg (nicht parentless
    singleShot statics) damit App-Close den Timer mit dlg zerstoert
    und kein Crash auf gestorbenem Python-Wrapper passiert.
    """
    _ensure_app()

    from ui.mw_radio import RadioMixin

    mw = QMainWindow()
    RadioMixin._show_calibration_done(mw, "20m", 20, 0)

    dialogs = mw.findChildren(QDialog)
    assert dialogs, "Mindestens 1 Dialog erstellt"
    dlg = dialogs[-1]

    timers = dlg.findChildren(QTimer)
    assert timers, "QTimer muss als Child von dlg vorhanden sein"
    timer = timers[0]
    assert timer.isSingleShot(), "Timer muss singleShot sein"
    assert timer.interval() == 3000, (
        f"Timer-Interval muss 3000ms sein, war {timer.interval()}"
    )
    assert timer.isActive(), "Timer muss aktiv sein nach show()"

    timer.stop()
    dlg.deleteLater()


def test_calibration_done_no_ok_button():
    """Fix F: Dialog hat KEINEN OK-Button mehr."""
    _ensure_app()

    from ui.mw_radio import RadioMixin

    mw = QMainWindow()
    RadioMixin._show_calibration_done(mw, "40m", 15, None)

    dialogs = mw.findChildren(QDialog)
    assert dialogs, "Mindestens 1 Dialog erstellt"
    dlg = dialogs[-1]

    buttons = dlg.findChildren(QPushButton)
    assert len(buttons) == 0, (
        f"Kein OK-Button erlaubt (gefunden: {len(buttons)})"
    )

    labels = dlg.findChildren(QLabel)
    assert len(labels) >= 2, (
        f"Erwartet >= 2 Labels (Titel + Info), gefunden: {len(labels)}"
    )

    # Timer stoppen und dlg cleanen
    for t in dlg.findChildren(QTimer):
        t.stop()
    dlg.deleteLater()


def test_calibration_done_non_modal():
    """Fix F: Dialog ist NICHT modal (Mike kann weiterarbeiten)."""
    _ensure_app()

    from ui.mw_radio import RadioMixin

    mw = QMainWindow()
    RadioMixin._show_calibration_done(mw, "20m", 20, 0)

    dialogs = mw.findChildren(QDialog)
    assert dialogs, "Mindestens 1 Dialog erstellt"
    dlg = dialogs[-1]

    assert not dlg.isModal(), (
        "Dialog darf nicht modal sein — Mike soll weiterarbeiten koennen"
    )

    for t in dlg.findChildren(QTimer):
        t.stop()
    dlg.deleteLater()


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
