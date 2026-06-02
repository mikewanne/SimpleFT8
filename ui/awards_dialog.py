"""SimpleFT8 — Diplome-Dialog.

Zeigt den Stand der Diplome (DXCC, WAE, WPX, WAC, WAS, WAZ): je gearbeitet und
per LoTW bestaetigt, mit Fortschrittsbalken. DXCC zusaetzlich mit der offiziellen
Marken-Staffelung (100/150/200/250/300/Honor Roll), dem DXCC-Challenge-Zaehler
(Entity-Band-Slots, Ziel 1000) und einer kompakten 5-Band-DXCC-Statuszeile.

Jede Karte laesst sich per 👁-Button ausblenden; ausgeblendete Diplome wandern in
einen Bereich unten und lassen sich per Klick wieder einblenden. Die Auswahl wird
ueber `core.awards_prefs` persistiert (eigene JSON, kein Settings-Durchreichen).

Reine Anzeige — die gesamte Diplom-Logik liegt in `core.awards`. Bekommt eine
QSO-Record-Liste, berechnet einmalig beim Oeffnen und stellt das Ergebnis dar.
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QProgressBar, QPushButton, QScrollArea, QWidget,
)
from PySide6.QtCore import Qt

from core.awards import (
    compute_awards, dxcc_tier_status, five_band_status,
    AWARD_ORDER, AWARD_INFO, DXCC_CHALLENGE_GOAL,
)
import core.awards_prefs as awards_prefs

_FONT = "Menlo"
_BG = "#0d0d1a"


class AwardsDialog(QDialog):
    """Modaler Diplome-Ueberblick mit Ein-/Ausblenden."""

    def __init__(self, records, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Diplome")
        self.setMinimumWidth(460)
        self.setStyleSheet(
            f"QDialog {{ background: {_BG}; }} "
            f"QLabel {{ color: #DDD; font-family: {_FONT}; }}"
        )
        records = list(records or [])
        self._awards = compute_awards(records)
        self._hidden = awards_prefs.load_hidden()
        self._cards = {}
        self._build_ui(self._awards, len(records))
        self._apply_visibility()

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
            card = self._award_card(key, awards[key])
            self._cards[key] = card
            col.addWidget(card)

        # Klappbereich fuer ausgeblendete Diplome
        col.addWidget(self._build_hidden_area())
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

    def _build_hidden_area(self) -> QWidget:
        """Bereich unten: Header + Reihe klickbarer „wieder einblenden“-Buttons."""
        wrap = QWidget()
        wrap.setStyleSheet("background: transparent;")
        lay = QVBoxLayout(wrap)
        lay.setContentsMargins(2, 0, 2, 0)
        lay.setSpacing(4)

        self._hidden_header = QLabel("▸ Ausgeblendet (0)")
        self._hidden_header.setStyleSheet(
            f"color: #8899AA; font-family: {_FONT}; font-size: 10px;")
        lay.addWidget(self._hidden_header)

        self._hidden_row = QHBoxLayout()
        self._hidden_row.setContentsMargins(0, 0, 0, 0)
        self._hidden_row.setSpacing(6)
        lay.addLayout(self._hidden_row)
        return wrap

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

        # Kopfzeile: Name + Badge + Auge
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
        head.addWidget(self._eye_button(key))
        lay.addLayout(head)

        # Beschreibung
        desc = QLabel(AWARD_INFO.get(key, ""))
        desc.setStyleSheet(f"color: #8899AA; font-family: {_FONT}; font-size: 10px;")
        desc.setWordWrap(True)
        lay.addWidget(desc)

        # Fortschrittsbalken (gearbeitet)
        bar_max, bar_val = self._bar_range(key, worked, goal, data)
        lay.addWidget(self._progress_bar(bar_max, bar_val, achieved))

        # Zahlen-Zeile: gearbeitet / bestaetigt
        nums = QLabel(
            f"gearbeitet: <b>{worked}</b> / {goal}   "
            f"•   bestätigt (LoTW): <b>{confirmed}</b>")
        nums.setStyleSheet(f"color: #CCD3DD; font-family: {_FONT}; font-size: 11px;")
        lay.addWidget(nums)

        # DXCC: Marken-Staffelung + Challenge + 5-Band-DXCC
        if key == "DXCC":
            lay.addWidget(self._dxcc_tier_label(worked))
            lay.addWidget(self._dxcc_challenge_widget(data))
            lay.addWidget(self._five_band_label(data))

        return card

    # ------------------------------------------------------------- Bausteine

    def _eye_button(self, key: str) -> QPushButton:
        btn = QPushButton("\U0001F441")   # 👁
        btn.setToolTip(f"{key} ausblenden")
        btn.setFixedSize(24, 22)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setStyleSheet(
            f"QPushButton {{ background: transparent; border: none; "
            f"font-size: 12px; padding: 0px; }}"
            f"QPushButton:hover {{ background: rgba(255,255,255,0.08); "
            f"border-radius: 3px; }}"
        )
        btn.clicked.connect(lambda _=False, k=key: self._hide_award(k))
        return btn

    @staticmethod
    def _progress_bar(bar_max, bar_val, achieved) -> QProgressBar:
        bar = QProgressBar()
        bar.setRange(0, max(1, bar_max))
        bar.setValue(bar_val)
        bar.setTextVisible(False)
        bar.setFixedHeight(8)
        bar.setStyleSheet(
            f"QProgressBar {{ background: #0d0d1a; border: 1px solid #2a2a44; "
            f"border-radius: 4px; }} "
            f"QProgressBar::chunk {{ background: "
            f"{'#2ECC71' if achieved else '#3A8FD0'}; border-radius: 3px; }}")
        return bar

    def _dxcc_challenge_widget(self, data: dict) -> QWidget:
        """DXCC-Challenge: Entity-Band-Slots (Ziel 1000), eigener Balken."""
        n = len(data.get("challenge", ()))
        goal = DXCC_CHALLENGE_GOAL
        wrap = QWidget()
        wrap.setStyleSheet("background: transparent;")
        lay = QVBoxLayout(wrap)
        lay.setContentsMargins(0, 2, 0, 0)
        lay.setSpacing(3)
        lbl = QLabel(f"DXCC Challenge: <b>{n}</b> / {goal} Band-Slots")
        lbl.setStyleSheet(f"color: #9AD0FF; font-family: {_FONT}; font-size: 10px;")
        lay.addWidget(lbl)
        lay.addWidget(self._progress_bar(goal, min(n, goal), n >= goal))
        return wrap

    def _five_band_label(self, data: dict) -> QLabel:
        """Kompakte 5-Band-DXCC-Zeile: 80✓ 40✓ 20• 15✓ 10• (✓ ab 100 Entities)."""
        parts = []
        for band, cnt, reached in five_band_status(data.get("five_band", {})):
            short = band[:-1] if band.endswith("M") else band
            mark = "✓" if reached else "·"   # ✓ / ·
            parts.append(f"{short}{mark}")
        lbl = QLabel("5-Band-DXCC: " + "  ".join(parts))
        lbl.setStyleSheet(f"color: #8FB8A0; font-family: {_FONT}; font-size: 10px;")
        lbl.setToolTip("✓ = 100 Länder auf diesem Band gearbeitet "
                       "(80/40/20/15/10 m). Offizielle Diplome verlangen "
                       "LoTW-Bestätigung.")
        return lbl

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

    # ---------------------------------------------------------- Sichtbarkeit

    def _hide_award(self, key: str):
        self._hidden.add(key)
        awards_prefs.save_hidden(self._hidden)
        self._apply_visibility()

    def _show_award(self, key: str):
        self._hidden.discard(key)
        awards_prefs.save_hidden(self._hidden)
        self._apply_visibility()

    def _apply_visibility(self):
        """Karten ein-/ausblenden + Klappbereich neu aufbauen."""
        for key, card in self._cards.items():
            card.setVisible(key not in self._hidden)

        self._clear_layout(self._hidden_row)
        hidden_keys = [k for k in AWARD_ORDER if k in self._hidden]
        self._hidden_header.setText(f"▸ Ausgeblendet ({len(hidden_keys)})")
        for key in hidden_keys:
            b = QPushButton(f"{key}  ✛")
            b.setToolTip(f"{key} wieder einblenden")
            b.setCursor(Qt.PointingHandCursor)
            b.setStyleSheet(
                f"QPushButton {{ background: rgba(80,90,120,0.25); color: #AABBCC; "
                f"border: 1px solid #2a2a44; border-radius: 3px; "
                f"font-family: {_FONT}; font-size: 10px; padding: 2px 7px; }}"
                f"QPushButton:hover {{ background: rgba(0,120,200,0.35); "
                f"color: #DDEEFF; }}"
            )
            b.clicked.connect(lambda _=False, k=key: self._show_award(k))
            self._hidden_row.addWidget(b)
        self._hidden_row.addStretch(1)

    @staticmethod
    def _clear_layout(layout):
        """Alle Items aus einem Layout entfernen (Widgets via deleteLater)."""
        while layout.count():
            item = layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
