"""SimpleFT8 QRZ Upload Dialoge — Confirm + Progress.

P1.QRZ-UPLOAD-UI v0.95.14: Phase-1-Bestaetigung + Phase-2-Progress.
Mike-Anforderung 07.05.: sichtbares Status-Fenster, weiterfunken
moeglich (non-modal), nur EINE Upload-Instanz.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal, QTimer, Slot
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QProgressBar,
)


_DLG_STYLE = """
QDialog, QWidget { background-color: #1a1a2e; }
QLabel { color: #CCCCCC; font-family: Menlo; font-size: 12px;
         background-color: #1a1a2e; }
QLabel#lbl_title { color: #88AACC; font-size: 14px;
                   font-weight: bold; padding-bottom: 6px; }
QLabel#lbl_counter { color: #88CCAA; font-size: 12px; padding: 2px 0; }
QLabel#lbl_finished { color: #00CC66; font-size: 13px; font-weight: bold; }
QLabel#lbl_cancelled { color: #CCAA44; font-size: 13px; font-weight: bold; }
QPushButton {
    background-color: #2a2a3e; color: #CCCCCC;
    border: 1px solid #444; border-radius: 5px;
    font-family: Menlo; font-size: 12px;
    padding: 6px 16px; min-width: 100px;
}
QPushButton:hover { background-color: #3a3a5e; }
QPushButton#btn_primary { background-color: #1a3a6e; border-color: #4488cc; }
QPushButton#btn_primary:hover { background-color: #2a4a8e; }
QProgressBar {
    background-color: #2a2a3e; border: 1px solid #444; border-radius: 3px;
    text-align: center; color: #CCCCCC; font-family: Menlo; font-size: 11px;
    height: 20px;
}
QProgressBar::chunk {
    background-color: #4488cc; border-radius: 3px;
}
"""


class QRZConfirmDialog(QDialog):
    """Phase 1: Bestaetigung vor Bulk-Upload.

    User-Choice via accepted/rejected. Default = Hochladen (Enter-Key).
    """

    def __init__(self, total: int, parent=None):
        super().__init__(parent)
        self.setWindowTitle("QRZ.com Upload")
        self.setStyleSheet(_DLG_STYLE)
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 16)
        layout.setSpacing(12)

        lbl_title = QLabel("QRZ.com Upload starten?")
        lbl_title.setObjectName("lbl_title")
        lbl_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(lbl_title)

        lbl_msg = QLabel(
            f"<b>{total}</b> QSOs werden an QRZ.com Logbook gesendet.<br><br>"
            f"Duplikate werden serverseitig erkannt und uebersprungen.<br>"
            f"Bei <b>{total}</b> QSOs dauert der Upload ca. "
            f"<b>{max(1, total // 300)}</b> Minuten.<br><br>"
            f"Du kannst weiterfunken — der Upload laeuft im Hintergrund."
        )
        lbl_msg.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_msg.setWordWrap(True)
        layout.addWidget(lbl_msg)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(12)
        self.btn_cancel = QPushButton("Abbrechen")
        self.btn_upload = QPushButton("Hochladen")
        self.btn_upload.setObjectName("btn_primary")
        self.btn_upload.setDefault(True)
        self.btn_cancel.clicked.connect(self.reject)
        self.btn_upload.clicked.connect(self.accept)
        btn_row.addWidget(self.btn_cancel)
        btn_row.addWidget(self.btn_upload)
        layout.addLayout(btn_row)


class QRZUploadDialog(QDialog):
    """Phase 2: Non-modal Progress-Dialog mit Cancel.

    Signals:
        cancel_clicked: User klickt Abbrechen waehrend Upload laeuft.

    Slots:
        update_progress: Worker emittet alle 10 QSOs.
        set_finished: Worker meldet Endergebnis (Auto-Close 10s).
    """

    cancel_clicked = Signal()

    def __init__(self, total: int, parent=None):
        super().__init__(parent)
        self._total = total
        self.setWindowTitle("QRZ.com Upload")
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
        self.setStyleSheet(_DLG_STYLE)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 16)
        layout.setSpacing(10)

        self.lbl_title = QLabel("QRZ.com Upload laeuft ...")
        self.lbl_title.setObjectName("lbl_title")
        layout.addWidget(self.lbl_title)

        self.lbl_progress = QLabel(f"0 von {total} QSOs (0%)")
        layout.addWidget(self.lbl_progress)

        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(total)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        layout.addWidget(self.progress_bar)

        self.lbl_counter = QLabel("Neu: 0   Duplikate: 0   Fehler: 0")
        self.lbl_counter.setObjectName("lbl_counter")
        layout.addWidget(self.lbl_counter)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self.btn_cancel = QPushButton("Abbrechen")
        self.btn_cancel.clicked.connect(self._on_cancel_clicked)
        btn_row.addWidget(self.btn_cancel)
        self.btn_close = QPushButton("Schliessen")
        self.btn_close.setObjectName("btn_primary")
        self.btn_close.hide()
        self.btn_close.clicked.connect(self.accept)
        btn_row.addWidget(self.btn_close)
        layout.addLayout(btn_row)

        self._auto_close_timer = QTimer(self)
        self._auto_close_timer.setSingleShot(True)
        self._auto_close_timer.timeout.connect(self.accept)

    @Slot(int, int, int, int, int)
    def update_progress(self, current: int, total: int,
                        ok: int, dup: int, fail: int) -> None:
        """Worker-Update (alle 10 QSOs via Qt.QueuedConnection)."""
        pct = int((current / total) * 100) if total else 0
        self.lbl_progress.setText(f"{current} von {total} QSOs ({pct}%)")
        self.progress_bar.setValue(current)
        self.lbl_counter.setText(
            f"Neu: {ok}   Duplikate: {dup}   Fehler: {fail}")

    @Slot(int, int, int, bool, int)
    def set_finished(self, ok: int, dup: int, fail: int,
                     cancelled: bool, total_processed: int) -> None:
        """Worker-Ende — Title + Auto-Close 10s + Schliessen-Button."""
        if cancelled:
            self.lbl_title.setText("QRZ.com Upload abgebrochen")
            self.lbl_title.setObjectName("lbl_cancelled")
        else:
            self.lbl_title.setText("QRZ.com Upload fertig")
            self.lbl_title.setObjectName("lbl_finished")
        self.lbl_title.setStyleSheet(_DLG_STYLE)

        self.lbl_progress.setText(
            f"{total_processed} von {self._total} QSOs verarbeitet")
        self.lbl_counter.setText(
            f"Neu: {ok}   Duplikate: {dup}   Fehler: {fail}")
        self.btn_cancel.hide()
        self.btn_close.show()

        self._auto_close_timer.start(10000)
        self.raise_()
        self.activateWindow()

    def _on_cancel_clicked(self) -> None:
        """User-Klick → Signal emit, Button disable, warten."""
        self.btn_cancel.setEnabled(False)
        self.lbl_title.setText("QRZ.com Upload wird abgebrochen ...")
        self.cancel_clicked.emit()
