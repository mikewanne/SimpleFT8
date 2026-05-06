"""StarsConditionWidget — 5-Sterne-Anzeige fuer Empfangs-Conditions.

Theme: aktive Sterne in Gold #FFD700 (Konsistenz mit RADIO-Label im
STATUS-Block), inaktive in #555. Eng zusammenstehend via RichText/HTML
in einer einzigen QLabel (statt 5 separater Labels).
"""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel


class StarsConditionWidget(QLabel):
    """5-Sterne-Anzeige als single QLabel mit RichText.

    Aktive Sterne in Gold (#FFD700), inaktive in #555. Sterne sitzen direkt
    nebeneinander weil sie als Zeichen in einem String liegen.
    """

    _ACTIVE_COLOR = "#FFD700"
    _INACTIVE_COLOR = "#555"

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTextFormat(Qt.TextFormat.RichText)
        self.setStyleSheet(
            "padding: 0; margin: 0; background: transparent; "
            "font-size: 13px; font-family: Menlo;"
        )
        self.setContentsMargins(0, 0, 0, 0)
        self.set_score(1, "0 Stationen")

    def set_score(self, score: int, tooltip: str = "") -> None:
        score = max(1, min(5, int(score)))
        active = f'<span style="color:{self._ACTIVE_COLOR};">{"★" * score}</span>'
        inactive = f'<span style="color:{self._INACTIVE_COLOR};">{"★" * (5 - score)}</span>'
        self.setText(active + inactive)
        self.setToolTip(tooltip)
