"""Smoke-Tests fuer _show_calibration_done Auto-Close (Fix F v0.83).

Prueft:
- QTimer.singleShot wird mit 3000ms aufgerufen (Auto-Close-Mechanik).
- Dialog hat KEINEN OK-Button mehr.
- Dialog ist non-modal (setModal nicht True gesetzt).
"""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from unittest.mock import patch

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QDialog, QPushButton, QLabel,
)


def _ensure_app():
    return QApplication.instance() or QApplication([])


def test_calibration_done_uses_singleshot_3000ms():
    """Fix F: QTimer.singleShot wird mit 3000ms aufgerufen."""
    _ensure_app()

    captured = {"ms": None, "callback": None}

    def fake_singleshot(ms, callback):
        captured["ms"] = ms
        captured["callback"] = callback

    from ui.mw_radio import RadioMixin

    mw = QMainWindow()
    with patch.object(QTimer, "singleShot", staticmethod(fake_singleshot)):
        RadioMixin._show_calibration_done(mw,"20m", 20, 0)

    assert captured["ms"] == 3000, (
        f"singleShot muss 3000ms haben, war {captured['ms']}"
    )
    assert captured["callback"] is not None, "callback muss gebunden sein"


def test_calibration_done_no_ok_button():
    """Fix F: Dialog hat KEINEN OK-Button mehr (kein QPushButton im Dialog)."""
    _ensure_app()

    from ui.mw_radio import RadioMixin

    mw = QMainWindow()
    with patch.object(QTimer, "singleShot"):
        RadioMixin._show_calibration_done(mw,"40m", 15, None)

    dialogs = mw.findChildren(QDialog)
    assert dialogs, "Mindestens 1 Dialog erstellt"
    dlg = dialogs[-1]

    buttons = dlg.findChildren(QPushButton)
    assert len(buttons) == 0, (
        f"Kein OK-Button erlaubt (gefunden: {len(buttons)})"
    )

    # Sicherstellen dass die Labels noch da sind
    labels = dlg.findChildren(QLabel)
    assert len(labels) >= 2, (
        f"Erwartet >= 2 Labels (Titel + Info), gefunden: {len(labels)}"
    )

    dlg.deleteLater()


def test_calibration_done_non_modal():
    """Fix F: Dialog ist NICHT modal (setModal nie auf True gesetzt)."""
    _ensure_app()

    from ui.mw_radio import RadioMixin

    mw = QMainWindow()
    with patch.object(QTimer, "singleShot"):
        RadioMixin._show_calibration_done(mw,"20m", 20, 0)

    dialogs = mw.findChildren(QDialog)
    assert dialogs, "Mindestens 1 Dialog erstellt"
    dlg = dialogs[-1]

    assert not dlg.isModal(), (
        "Dialog darf nicht modal sein — Mike soll weiterarbeiten koennen"
    )

    dlg.deleteLater()
