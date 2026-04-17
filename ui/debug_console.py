"""SimpleFT8 Debug-Konsole — stdout/stderr im UI anzeigen.

Ein-/ausblendbar via Ctrl+D. Einstellung wird gespeichert.
Copy-Button fuer Zwischenablage, Clear-Button zum Leeren.
"""

import sys
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, QPushButton
from PySide6.QtGui import QFont, QTextCursor
from PySide6.QtCore import QObject, Signal


class _ConsoleWriter(QObject):
    """Leitet sys.stdout/stderr in die Debug-Konsole um UND behaelt die Original-Ausgabe."""
    text_written = Signal(str)

    def __init__(self, original_stream):
        super().__init__()
        self._original = original_stream

    def write(self, text):
        if text.strip():
            self.text_written.emit(text)
        if self._original:
            self._original.write(text)

    def flush(self):
        if self._original:
            self._original.flush()


class DebugConsoleWidget(QWidget):
    """Debug-Konsole mit Copy + Clear Buttons."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        # Toolbar
        toolbar = QHBoxLayout()
        toolbar.setContentsMargins(2, 2, 2, 0)

        from PySide6.QtWidgets import QLabel
        lbl = QLabel("DEBUG")
        lbl.setStyleSheet("color: #FF8800; font-family: Menlo; font-size: 10px; font-weight: bold;")
        toolbar.addWidget(lbl)
        toolbar.addStretch()

        self.btn_copy = QPushButton("Copy")
        self.btn_copy.setFixedSize(50, 20)
        self.btn_copy.setStyleSheet(
            "QPushButton { background: #333; color: #AAA; border: 1px solid #555; "
            "border-radius: 3px; font-size: 10px; font-family: Menlo; }"
            "QPushButton:hover { background: #444; color: #FFF; }"
        )
        self.btn_copy.clicked.connect(self._on_copy)
        toolbar.addWidget(self.btn_copy)

        self.btn_clear = QPushButton("Clear")
        self.btn_clear.setFixedSize(50, 20)
        self.btn_clear.setStyleSheet(
            "QPushButton { background: #333; color: #AAA; border: 1px solid #555; "
            "border-radius: 3px; font-size: 10px; font-family: Menlo; }"
            "QPushButton:hover { background: #444; color: #FFF; }"
        )
        self.btn_clear.clicked.connect(self._on_clear)
        toolbar.addWidget(self.btn_clear)

        layout.addLayout(toolbar)

        # Text-Anzeige (QPlainTextEdit fuer setMaximumBlockCount)
        from PySide6.QtWidgets import QPlainTextEdit
        self.text_edit = QPlainTextEdit()
        self.text_edit.setReadOnly(True)
        self.text_edit.setFont(QFont("Menlo", 9))
        self.text_edit.setStyleSheet(
            "QPlainTextEdit { background: #0a0a14; color: #88AA88; border: 1px solid #222; "
            "border-radius: 3px; }"
        )
        self.text_edit.setMaximumBlockCount(500)
        layout.addWidget(self.text_edit)

        # stdout + stderr umleiten
        self._stdout_writer = _ConsoleWriter(sys.stdout)
        self._stderr_writer = _ConsoleWriter(sys.stderr)
        self._stdout_writer.text_written.connect(self._append_text)
        self._stderr_writer.text_written.connect(self._append_error)
        sys.stdout = self._stdout_writer
        sys.stderr = self._stderr_writer

    def _append_text(self, text: str):
        self.text_edit.appendPlainText(text)

    def _append_error(self, text: str):
        self.text_edit.appendPlainText(f"[ERR] {text}")

    def _on_copy(self):
        from PySide6.QtWidgets import QApplication
        QApplication.clipboard().setText(self.text_edit.toPlainText())

    def _on_clear(self):
        self.text_edit.clear()

    def restore_streams(self):
        """Original stdout/stderr wiederherstellen."""
        sys.stdout = self._stdout_writer._original
        sys.stderr = self._stderr_writer._original
