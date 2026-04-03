"""SimpleFT8 QSO Panel — Fenster 2: QSO-Verlauf der aktuellen Session."""

import time
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QTextEdit
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QTextCursor, QColor


class QSOPanel(QWidget):
    """QSO-Verlaufsfenster — chronologische Anzeige aller eigenen QSOs."""

    def __init__(self):
        super().__init__()
        self._setup_ui()
        self._qso_count = 0

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        header = QLabel("QSO VERLAUF")
        header.setStyleSheet(
            "color: #00AAFF; font-weight: bold; font-size: 14px; padding: 4px;"
        )
        layout.addWidget(header)

        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setFont(QFont("Menlo", 12))
        self.log_view.setStyleSheet("""
            QTextEdit {
                background-color: #0d0d1a;
                color: #CCCCCC;
                border: 1px solid #333;
                border-radius: 4px;
                padding: 6px;
                selection-background-color: #0066AA;
            }
        """)
        layout.addWidget(self.log_view)

        self.status_label = QLabel("Keine QSOs")
        self.status_label.setStyleSheet("color: #666; font-size: 11px; padding: 2px;")
        layout.addWidget(self.status_label)

    def add_tx(self, message: str):
        """Eigene gesendete Nachricht anzeigen."""
        utc = time.strftime("%H:%M", time.gmtime())
        self._append_colored(f"{utc} → {message}", "#FFAA00")

    def add_rx(self, message: str):
        """Empfangene Antwort anzeigen."""
        utc = time.strftime("%H:%M", time.gmtime())
        self._append_colored(f"{utc} ← {message}", "#44BBFF")

    def add_qso_complete(self, their_call: str):
        """QSO als abgeschlossen markieren."""
        self._qso_count += 1
        self._append_colored(f"       ✓ QSO mit {their_call} komplett", "#44FF44")
        self._append_colored("─" * 30, "#333333")
        self.status_label.setText(f"{self._qso_count} QSO(s) diese Session")

    def add_timeout(self, their_call: str):
        """Timeout anzeigen."""
        self._append_colored(f"       ✗ {their_call} — Timeout", "#FF4444")
        self._append_colored("─" * 30, "#333333")

    def add_info(self, text: str):
        """Info-Nachricht anzeigen."""
        self._append_colored(f"       {text}", "#666666")

    def _append_colored(self, text: str, color: str):
        cursor = self.log_view.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self.log_view.setTextCursor(cursor)
        self.log_view.setTextColor(QColor(color))
        self.log_view.append(text)
        # Auto-Scroll nach unten
        scrollbar = self.log_view.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
