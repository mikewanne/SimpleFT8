"""SimpleFT8 QRZ Upload Dialoge — Confirm-Phase.

P1.QRZ-UPLOAD-UI v0.95.14: Phase-1-Bestaetigung vor Bulk-Upload.
P1.QRZ-UPLOAD-UI-2 v0.95.15: QRZUploadDialog (Phase 2 non-modal Progress)
entfernt — Status laeuft jetzt in Titelleiste + Statusbar-Cancel-Widget
(siehe ui/mw_qso.py + ui/main_window.py).
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
)


_DLG_STYLE = """
QDialog, QWidget { background-color: #1a1a2e; }
QLabel { color: #CCCCCC; font-family: Menlo; font-size: 12px;
         background-color: #1a1a2e; }
QLabel#lbl_title { color: #88AACC; font-size: 14px;
                   font-weight: bold; padding-bottom: 6px; }
QPushButton {
    background-color: #2a2a3e; color: #CCCCCC;
    border: 1px solid #444; border-radius: 5px;
    font-family: Menlo; font-size: 12px;
    padding: 6px 16px; min-width: 100px;
}
QPushButton:hover { background-color: #3a3a5e; }
QPushButton#btn_primary { background-color: #1a3a6e; border-color: #4488cc; }
QPushButton#btn_primary:hover { background-color: #2a4a8e; }
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
            f"Status erscheint in der Titelleiste — du kannst weiterfunken."
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
