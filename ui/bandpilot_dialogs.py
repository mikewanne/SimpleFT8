"""Bandpilot Toast + Manuell-Dialog (v0.88).

- ``BandpilotAutoToast``: 3s self-closing QDialog mittig auf Bildschirm.
  Zeigt alle 3 Modi-Werte mit Top-1 in gruen + ●-Marker fuer aktuellen.
- ``BandpilotManualDialog``: 3 Buttons mit 1/2/3-Markern, Top-1 gruen.
  Returnt gewaehlten Code-Modus oder ``None`` (Abbruch).

Beide non-modal, ``WA_DeleteOnClose``, ``Frameless | Tool``-Flags
(kein Taskbar-Eintrag, parent-relative Position).
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

from core.mode_recommender import USER_LABEL


_TOAST_STYLE = """
QDialog {
    background-color: #1a1a2e;
    border: 2px solid #4488cc;
    border-radius: 8px;
}
QLabel { color: #CCCCCC; font-family: Menlo; font-size: 13px; }
QLabel#title  { color: #88AACC; font-size: 14px; font-weight: bold; }
QLabel#chosen { color: #4ade80; font-weight: bold; }
QLabel#row_top1   { color: #4ade80; font-weight: bold; }
QLabel#row_neutral { color: #CCCCCC; }
QPushButton#close_btn {
    background: transparent; color: #888;
    border: none; font-size: 16px; padding: 0 4px;
}
QPushButton#close_btn:hover { color: #FFF; }
"""


_MANUAL_STYLE = """
QDialog { background-color: #1a1a2e; border: 1px solid #444; }
QLabel  { color: #CCCCCC; font-family: Menlo; font-size: 13px; }
QLabel#title    { color: #88AACC; font-size: 14px; font-weight: bold;
                  padding-bottom: 4px; }
QLabel#hint     { color: #888; font-size: 11px; padding-top: 6px; }
QLabel#row_top1 { color: #4ade80; font-weight: bold; }
QPushButton {
    background-color: #2a2a3e; color: #CCCCCC;
    border: 1px solid #444; border-radius: 5px;
    font-family: Menlo; font-size: 13px;
    padding: 8px 16px; min-width: 160px;
}
QPushButton:hover { background-color: #3a3a5e; }
QPushButton#btn_top1 {
    background-color: #1e4030; color: #4ade80;
    border-color: #4ade80;
}
QPushButton#btn_top1:hover { background-color: #2a5040; }
QPushButton#btn_cancel {
    background-color: #1a1a1a; color: #888; border-color: #333;
}
QPushButton#btn_cancel:hover { background-color: #2a2a2a; color: #AAA; }
"""


class BandpilotAutoToast(QDialog):
    """3-Sekunden Self-Close-Toast mit Modus-Wahl-Anzeige (Auto-Modus)."""

    def __init__(self, parent: QWidget | None, band: str, utc_hour: int,
                 rec: dict):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint |
                            Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setStyleSheet(_TOAST_STYLE)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 14, 20, 14)
        layout.setSpacing(6)

        # Header-Zeile mit Titel + Schliessen-Knopf
        header = QHBoxLayout()
        title = QLabel(f"Bandpilot — {band} {utc_hour:02d} UTC")
        title.setObjectName("title")
        header.addWidget(title, stretch=1)
        close_btn = QPushButton("×")
        close_btn.setObjectName("close_btn")
        close_btn.setFixedSize(20, 20)
        close_btn.clicked.connect(self.close)
        header.addWidget(close_btn)
        layout.addLayout(header)

        chosen_label = USER_LABEL.get(rec["decision_mode"], rec["decision_mode"])
        chosen = QLabel(f"{chosen_label} gewaehlt "
                        f"({rec['top1_mean']:.1f} Sta./Slot)")
        chosen.setObjectName("chosen")
        layout.addWidget(chosen)

        # Ranking — alle 3 Modi mit Top-1 hervorgehoben
        for idx, (mode_code, mean) in enumerate(rec["ranking"]):
            row = QLabel(f"{idx + 1}. {USER_LABEL.get(mode_code, mode_code)}: "
                         f"{mean:.1f}")
            row.setObjectName("row_top1" if idx == 0 else "row_neutral")
            layout.addWidget(row)

        # Self-close nach 5 Sekunden (Mike-Feedback 04.05.: 3s zu kurz)
        QTimer.singleShot(5000, self._safe_close)

    def _safe_close(self):
        """Robust gegen bereits-geschlossen (User-Klick auf [×] vorher)."""
        try:
            self.close()
        except RuntimeError:
            pass  # Qt-Object schon weg

    def showEvent(self, event):  # noqa: N802 (Qt-Override)
        """Beim Anzeigen: zentrieren auf Parent-Geometrie."""
        super().showEvent(event)
        parent = self.parent()
        if parent is not None and isinstance(parent, QWidget):
            pgeo = parent.geometry()
            x = pgeo.x() + (pgeo.width() - self.width()) // 2
            y = pgeo.y() + (pgeo.height() - self.height()) // 2
            self.move(x, y)


class BandpilotManualDialog(QDialog):
    """Manuell-Dialog: 3 Buttons (1/2/3-Marker, Top-1 gruen) + Abbruch.

    Returnt Code-Modus-String via ``self.chosen`` nach exec(). ``None``
    bei Abbruch.
    """

    def __init__(self, parent: QWidget | None, band: str, utc_hour: int,
                 rec: dict, current: str):
        super().__init__(parent)
        self.setWindowTitle("Bandpilot — Empfehlung")
        self.setStyleSheet(_MANUAL_STYLE)
        self.chosen: str | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 18, 24, 18)
        layout.setSpacing(8)

        title = QLabel(f"{band} {utc_hour:02d} UTC")
        title.setObjectName("title")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        intro = QLabel("Genug Daten fuer Vergleich vorhanden:")
        intro.setAlignment(Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(intro)

        # Werte-Anzeige (ueber Buttons) — Ranking 1./2./3.
        for idx, (mode_code, mean) in enumerate(rec["ranking"]):
            label = USER_LABEL.get(mode_code, mode_code)
            marker = "●" if mode_code == current else " "
            lbl = QLabel(f"  {marker}  {idx + 1}. {label:<22} "
                         f"{mean:>6.1f} Sta./Slot")
            if idx == 0:
                lbl.setObjectName("row_top1")
            layout.addWidget(lbl)

        hint = QLabel(f"●  = aktueller Modus ({USER_LABEL.get(current, current)})")
        hint.setObjectName("hint")
        layout.addWidget(hint)

        # 3 Buttons fuer direkte Modus-Wahl + Abbruch
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        for mode_code, mean in rec["ranking"]:
            btn = QPushButton(USER_LABEL.get(mode_code, mode_code))
            if mode_code == rec["top1"]:
                btn.setObjectName("btn_top1")
            btn.clicked.connect(lambda _checked=False, m=mode_code:
                                 self._select(m))
            btn_row.addWidget(btn)
        layout.addLayout(btn_row)

        cancel_btn = QPushButton("Abbruch")
        cancel_btn.setObjectName("btn_cancel")
        cancel_btn.clicked.connect(self.reject)
        layout.addWidget(cancel_btn)

    def _select(self, mode_code: str):
        self.chosen = mode_code
        self.accept()
