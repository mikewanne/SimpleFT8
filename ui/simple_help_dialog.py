"""SimpleFT8 SimpleHelpDialog — Einheitlicher Help-Dialog mit Scrollbar.

Bundle J (v0.97.27): Ersetzt QMessageBox.information / QMessageBox-Help-Aufrufe.
QMessageBox ist nicht resizable + kein Scrollbar → langer Markdown wurde
abgeschnitten (Mike-Screenshot 14.05.2026). SimpleHelpDialog ist resizable,
hat QTextBrowser mit automatischem Scrollbar.

Mike-Designentscheidung (TODO J-Punkt 2): Konsistenz > Optimum-pro-Dialog —
auch kurze Hints landen im 700×600-Fenster mit Weißraum.

Aufruf:
    from ui.simple_help_dialog import show_simple_help
    show_simple_help(parent, "Titel", "Text", markdown=False)
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QTextBrowser,
)


_STYLE = """
QDialog { background-color: #1a1a2e; color: #CCC; }
QTextBrowser {
    background-color: #14142a;
    color: #CCC;
    border: 1px solid #333;
    border-radius: 4px;
    padding: 8px;
    font-family: -apple-system, "SF Pro Text", sans-serif;
    font-size: 12pt;
}
QPushButton {
    background: #0066AA; color: white; border: none;
    border-radius: 3px; padding: 8px 16px; font-weight: bold;
}
QPushButton:hover { background: #0088CC; }
QScrollBar:vertical {
    background: #222; border: none; width: 12px;
}
QScrollBar::handle:vertical {
    background: #444; border-radius: 3px; min-height: 30px;
}
QScrollBar::handle:vertical:hover { background: #555; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
"""


class SimpleHelpDialog(QDialog):
    """Resizable Help-Dialog mit QTextBrowser (Markdown-faehig)."""

    def __init__(self, parent=None, title: str = "Hilfe",
                 text: str = "", *, markdown: bool = False):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumSize(700, 600)
        self.setWindowModality(Qt.WindowModality.WindowModal)
        self.setStyleSheet(_STYLE)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 12)
        layout.setSpacing(10)

        self._browser = QTextBrowser()
        self._browser.setOpenExternalLinks(True)
        if markdown:
            self._browser.setMarkdown(text)
        else:
            self._browser.setPlainText(text)
        layout.addWidget(self._browser, 1)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self._btn_close = QPushButton("Schließen")
        self._btn_close.clicked.connect(self.accept)
        btn_row.addWidget(self._btn_close)
        layout.addLayout(btn_row)


def show_simple_help(parent, title: str, text: str,
                     *, markdown: bool = False) -> None:
    """Einheitlicher Aufruf-Helper. Blockierender modaler exec.

    Konsistenz vor Weissraum-Optimum: auch kurze Hints landen im
    700x600-Dialog mit App-Theme.
    """
    dlg = SimpleHelpDialog(parent, title=title, text=text, markdown=markdown)
    dlg.exec()
