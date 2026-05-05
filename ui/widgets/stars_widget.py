"""StarsConditionWidget — 5-Sterne-Anzeige fuer lokale Conditions.

Theme: aktive Sterne in Neon-Cyan #00DDFF, inaktive in dezentem Grau #555.
"""
from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel


class StarsConditionWidget(QWidget):
    _STAR_ACTIVE_STYLE = (
        "color: #00DDFF; font-size: 14px; "
        "font-family: Menlo; padding: 0 1px;"
    )
    _STAR_INACTIVE_STYLE = (
        "color: #555; font-size: 14px; "
        "font-family: Menlo; padding: 0 1px;"
    )

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self._stars: list[QLabel] = []
        for _ in range(5):
            lbl = QLabel("★")
            lbl.setStyleSheet(self._STAR_INACTIVE_STYLE)
            self._stars.append(lbl)
            layout.addWidget(lbl)
        layout.addStretch()
        self.set_score(1, "0 Stationen")

    def set_score(self, score: int, tooltip: str = "") -> None:
        score = max(1, min(5, int(score)))
        for i, lbl in enumerate(self._stars):
            if i < score:
                lbl.setStyleSheet(self._STAR_ACTIVE_STYLE)
            else:
                lbl.setStyleSheet(self._STAR_INACTIVE_STYLE)
        self.setToolTip(tooltip)
