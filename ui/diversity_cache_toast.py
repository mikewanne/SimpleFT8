"""DiversityCacheToast — 5-s-Self-Close-Hinweis bei Cache-Reuse (v0.93).

Wird beim Bandwechsel oder Diversity-Aktivierung gezeigt, wenn das
Diversity-Ratio aus dem PresetStore-Cache geladen wurde (statt Phase 3
neu zu messen). Non-modal, ohne User-Interaktion erforderlich.

Style + Pattern uebernommen von ``ui/bandpilot_dialogs.py``.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


_TOAST_STYLE = """
QDialog {
    background-color: #1a1a2e;
    border: 2px solid #4488cc;
    border-radius: 8px;
}
QLabel { color: #CCCCCC; font-family: Menlo; font-size: 13px; }
QLabel#title  { color: #88AACC; font-size: 14px; font-weight: bold; }
QLabel#chosen { color: #4ade80; font-weight: bold; }
QLabel#info   { color: #CCCCCC; }
QPushButton#close_btn {
    background: transparent; color: #888;
    border: none; font-size: 16px; padding: 0 4px;
}
QPushButton#close_btn:hover { color: #FFF; }
"""


class DiversityCacheToast(QDialog):
    """5-Sekunden Self-Close-Toast bei Diversity-Cache-Reuse."""

    def __init__(self, parent: QWidget | None, band: str, ft_mode: str,
                 scoring_label: str, ratio: str, dominant: str | None,
                 age_minutes: int):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint |
                            Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setStyleSheet(_TOAST_STYLE)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 14, 20, 14)
        layout.setSpacing(6)

        # Header — Titel + Schliessen-Knopf
        header = QHBoxLayout()
        title = QLabel(f"{band} {ft_mode} — {scoring_label}")
        title.setObjectName("title")
        header.addWidget(title, stretch=1)
        close_btn = QPushButton("×")
        close_btn.setObjectName("close_btn")
        close_btn.setFixedSize(20, 20)
        close_btn.clicked.connect(self.close)
        header.addWidget(close_btn)
        layout.addLayout(header)

        chosen = QLabel(f"Aus Cache uebernommen — {ratio}"
                        + (f" (dominant: {dominant})" if dominant else ""))
        chosen.setObjectName("chosen")
        layout.addWidget(chosen)

        info = QLabel(f"vor {age_minutes} Min. gemessen — Phase 3 uebersprungen")
        info.setObjectName("info")
        layout.addWidget(info)

        # Self-close nach 5 Sekunden (Mike-Vorgabe)
        QTimer.singleShot(5000, self._safe_close)

    def _safe_close(self):
        """Robust gegen bereits-geschlossen (User-Klick auf [×])."""
        try:
            self.close()
        except RuntimeError:
            pass

    def showEvent(self, event):  # noqa: N802 (Qt-Override)
        """Beim Anzeigen: zentrieren auf Parent."""
        super().showEvent(event)
        parent = self.parent()
        if parent is not None and isinstance(parent, QWidget):
            pgeo = parent.geometry()
            x = pgeo.x() + (pgeo.width() - self.width()) // 2
            y = pgeo.y() + (pgeo.height() - self.height()) // 2
            self.move(x, y)
