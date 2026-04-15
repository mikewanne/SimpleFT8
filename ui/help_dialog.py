"""SimpleFT8 Hilfe-Dialog — zeigt Feature-Dokumentation aus docs/explained/."""

from pathlib import Path
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QListWidget, QTextBrowser,
    QLabel, QComboBox, QPushButton,
)
from PySide6.QtCore import Qt


# Feature-Liste: (Anzeige-Name DE, Anzeige-Name EN, Datei-Basis)
_FEATURES = [
    ("Signalverarbeitung", "Signal Processing", "signal-processing"),
    ("DT-Zeitkorrektur", "DT Time Correction", "dt-correction"),
    ("AP-Lite Rettung", "AP-Lite Rescue", "ap-lite"),
    ("Propagation-Anzeige", "Propagation Indicators", "propagation-indicators"),
    ("Operator-Praesenz", "Operator Presence", "operator-presence"),
]

_DOCS_DIR = Path(__file__).parent.parent / "docs" / "explained"


class HelpDialog(QDialog):
    """Feature-Hilfe mit Sprachauswahl (DE/EN)."""

    def __init__(self, parent=None, language: str = "de"):
        super().__init__(parent)
        self._lang = language
        self.setWindowTitle("SimpleFT8 — Hilfe / Help")
        self.setMinimumSize(800, 500)
        self.setStyleSheet("""
            QDialog { background: #0e0e18; }
            QListWidget { background: #12121e; color: #CCC; border: 1px solid #333;
                font-size: 13px; font-family: Menlo; }
            QListWidget::item { padding: 6px; }
            QListWidget::item:selected { background: #1a3a5a; color: #FFF; }
            QTextBrowser { background: #0a0a14; color: #CCC; border: 1px solid #333;
                font-size: 12px; font-family: Menlo; }
            QLabel { color: #AAA; font-size: 11px; }
            QComboBox { background: #222; color: #CCC; border: 1px solid #444;
                padding: 4px 8px; font-size: 12px; }
        """)

        layout = QVBoxLayout(self)

        # Sprach-Auswahl oben
        top = QHBoxLayout()
        top.addWidget(QLabel("Sprache / Language:"))
        self._lang_combo = QComboBox()
        self._lang_combo.addItems(["Deutsch", "English"])
        self._lang_combo.setCurrentIndex(0 if language == "de" else 1)
        self._lang_combo.currentIndexChanged.connect(self._on_lang_changed)
        top.addWidget(self._lang_combo)
        top.addStretch()
        layout.addLayout(top)

        # Inhalt: Liste links, Text rechts
        content = QHBoxLayout()
        self._list = QListWidget()
        self._list.setFixedWidth(220)
        self._list.currentRowChanged.connect(self._on_feature_selected)
        content.addWidget(self._list)

        self._browser = QTextBrowser()
        self._browser.setOpenExternalLinks(True)
        content.addWidget(self._browser, 1)
        layout.addLayout(content)

        self._populate_list()
        if self._list.count() > 0:
            self._list.setCurrentRow(0)

    def _populate_list(self):
        self._list.clear()
        idx = 0 if self._lang == "de" else 1
        for names in _FEATURES:
            self._list.addItem(names[idx])

    def _on_lang_changed(self, index: int):
        self._lang = "de" if index == 0 else "en"
        row = self._list.currentRow()
        self._populate_list()
        self._list.setCurrentRow(max(0, row))

    def _on_feature_selected(self, row: int):
        if row < 0 or row >= len(_FEATURES):
            return
        base = _FEATURES[row][2]
        suffix = "_de.md" if self._lang == "de" else ".md"
        path = _DOCS_DIR / f"{base}{suffix}"
        if path.exists():
            self._browser.setMarkdown(path.read_text(errors="replace"))
        else:
            self._browser.setText(f"Datei nicht gefunden: {path.name}")
