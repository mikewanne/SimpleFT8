"""SimpleFT8 — Diplome-Dialog.

Zeigt den Stand der vier Diplome (DXCC, WAC, WAS, WAZ): je gearbeitet und per
LoTW bestaetigt, mit Fortschrittsbalken. DXCC zusaetzlich mit der offiziellen
Marken-Staffelung (100/150/200/250/300/Honor Roll).

Reine Anzeige — die gesamte Logik liegt in `core.awards`. Bekommt eine
QSO-Record-Liste, berechnet einmalig beim Oeffnen und stellt das Ergebnis dar.
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QProgressBar, QPushButton, QScrollArea, QWidget,
)
from PySide6.QtCore import Qt

from core.awards import (
    compute_awards, dxcc_tier_status, AWARD_ORDER, AWARD_INFO,
)

_FONT = "Menlo"
_BG = "#0d0d1a"


class AwardsDialog(QDialog):
    """Modaler Diplome-Ueberblick."""

    def __init__(self, records, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Diplome")
        self.setMinimumWidth(440)
        self.setStyleSheet(
            f"QDialog {{ background: {_BG}; }} "
            f"QLabel {{ color: #DDD; font-family: {_FONT}; }}"
        )
        records = list(records or [])
        awards = compute_awards(records)
        self._build_ui(awards, len(records))

    # ------------------------------------------------------------------ UI

    def _build_ui(self, awards: dict, n_qsos: int):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(14, 12, 14, 12)
        outer.setSpacing(10)

        title = QLabel("\U0001F3C5  Diplome-Übersicht")
        title.setStyleSheet(
            f"color: #00CCAA; font-family: {_FONT}; font-size: 16px; "
            f"font-weight: bold;"
        )
        outer.addWidget(title)

        sub = QLabel(
            f"{n_qsos} QSOs ausgewertet (QRZ-Export DA1MHH & DO4MHH). "
            f"„gearbeitet“ = alle, „bestätigt“ = per LoTW. Frische QSOs "
            f"zählen erst nach erneutem QRZ-Export mit.")
        sub.setStyleSheet(f"color: #8899AA; font-family: {_FONT}; font-size: 10px;")
        sub.setWordWrap(True)
        outer.addWidget(sub)

        # Karten in einer ScrollArea (falls Fenster klein)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        body = QWidget()
        body.setStyleSheet("background: transparent;")
        col = QVBoxLayout(body)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(10)
        for key in AWARD_ORDER:
            col.addWidget(self._award_card(key, awards[key]))
        col.addStretch(1)
        scroll.setWidget(body)
        outer.addWidget(scroll, 1)

        # Schliessen
        row = QHBoxLayout()
        row.addStretch(1)
        btn = QPushButton("Schließen")
        btn.setFixedWidth(90)
        btn.setStyleSheet(
            f"QPushButton {{ background: rgba(0,100,180,0.3); color: #66AAEE; "
            f"border: 1px solid #336; border-radius: 3px; font-family: {_FONT}; "
            f"font-size: 11px; padding: 4px; }}"
            f"QPushButton:hover {{ background: rgba(0,120,200,0.4); }}"
        )
        btn.clicked.connect(self.accept)
        row.addWidget(btn)
        outer.addLayout(row)

    def _award_card(self, key: str, data: dict) -> QFrame:
        worked = len(data["worked"])
        confirmed = len(data["confirmed"])
        goal = data["goal"]
        achieved = worked >= goal

        card = QFrame()
        card.setStyleSheet(
            f"QFrame {{ background: #14142a; border: 1px solid "
            f"{'#2e6e4e' if achieved else '#2a2a44'}; border-radius: 6px; }}"
        )
        lay = QVBoxLayout(card)
        lay.setContentsMargins(12, 9, 12, 9)
        lay.setSpacing(5)

        # Kopfzeile: Name + Badge
        head = QHBoxLayout()
        name = QLabel(data["label"])
        name.setStyleSheet(
            f"color: #FFFFFF; font-family: {_FONT}; font-size: 14px; "
            f"font-weight: bold;")
        head.addWidget(name)
        head.addStretch(1)
        badge = QLabel("\U0001F3C5 erreicht" if achieved
                       else f"{worked} / {goal}")
        badge.setStyleSheet(
            f"color: {'#FFD24A' if achieved else '#AABBCC'}; "
            f"font-family: {_FONT}; font-size: 12px; font-weight: bold;")
        head.addWidget(badge)
        lay.addLayout(head)

        # Beschreibung
        desc = QLabel(AWARD_INFO.get(key, ""))
        desc.setStyleSheet(f"color: #8899AA; font-family: {_FONT}; font-size: 10px;")
        desc.setWordWrap(True)
        lay.addWidget(desc)

        # Fortschrittsbalken (gearbeitet)
        bar_max, bar_val = self._bar_range(key, worked, goal, data)
        bar = QProgressBar()
        bar.setRange(0, bar_max)
        bar.setValue(bar_val)
        bar.setTextVisible(False)
        bar.setFixedHeight(8)
        bar.setStyleSheet(
            f"QProgressBar {{ background: #0d0d1a; border: 1px solid #2a2a44; "
            f"border-radius: 4px; }} "
            f"QProgressBar::chunk {{ background: "
            f"{'#2ECC71' if achieved else '#3A8FD0'}; border-radius: 3px; }}")
        lay.addWidget(bar)

        # Zahlen-Zeile: gearbeitet / bestaetigt
        nums = QLabel(
            f"gearbeitet: <b>{worked}</b> / {goal}   "
            f"•   bestätigt (LoTW): <b>{confirmed}</b>")
        nums.setStyleSheet(f"color: #CCD3DD; font-family: {_FONT}; font-size: 11px;")
        lay.addWidget(nums)

        # DXCC: Marken-Staffelung
        if key == "DXCC":
            lay.addWidget(self._dxcc_tier_label(worked))

        return card

    @staticmethod
    def _bar_range(key, worked, goal, data):
        """Balken-Range. DXCC laeuft auf die naechste Marke zu, sonst auf das Ziel."""
        if key == "DXCC":
            cur, nxt = dxcc_tier_status(worked)
            if isinstance(nxt, int):
                return nxt, min(worked, nxt)
            # Honor Roll als naechstes oder erreicht
            target = data.get("honor_roll", goal)
            return target, min(worked, target)
        return goal, min(worked, goal)

    @staticmethod
    def _dxcc_tier_label(worked: int) -> QLabel:
        cur, nxt = dxcc_tier_status(worked)
        if cur is None:
            txt = f"Stufe: — (noch {100 - worked} bis zur Basis 100)"
        elif cur == "Honor Roll":
            txt = "Stufe: \U0001F3C6 Honor Roll erreicht"
        else:
            rest = (nxt - worked) if isinstance(nxt, int) else None
            nxt_txt = f"{nxt}" if isinstance(nxt, int) else "Honor Roll"
            extra = f" (noch {rest})" if rest is not None else ""
            txt = f"Stufe: {cur} erreicht • nächstes Ziel: {nxt_txt}{extra}"
        lbl = QLabel(txt)
        lbl.setStyleSheet(f"color: #FFD24A; font-family: {_FONT}; font-size: 10px;")
        return lbl
