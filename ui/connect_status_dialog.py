"""SimpleFT8 ConnectStatusDialog — Modal beim App-Start waehrend
FlexRadio gesucht / verbunden wird.

P26 (10.05.2026): User soll wissen was die App tut, und einen Bypass
haben falls Radio nicht da ist (Test/Debug, Radio aus, 200km weg).

WindowModal damit Qt-Event-Loop weiterlaeuft (Decoder, Reconnect-Logik).
Auto-Close bei `connected`-Signal vom Aufrufer (mw_radio) connectet.
Cancel: "ohne Radio weiter" (Demo-Modus) oder "Beenden" (App schliesst).

Cross-thread Signals:
    attempt_changed(int, int)  — Worker meldet Versuch X von Y
    failed_signal()            — Worker meldet alle Versuche durch

Beide via Qt-AutoConnection — Worker-Thread emittet, Slot laeuft im
GUI-Thread (Qt erkennt Cross-Thread → QueuedConnection).
"""

from pathlib import Path

from PySide6.QtCore import Qt, QTimer, Signal, Slot
from PySide6.QtGui import QFont, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)


def _load_radio_tower_pixmap(size: int = 44) -> QPixmap:
    """Lucide radio-tower SVG → QPixmap. Bei Fehlern leere Pixmap."""
    icon_path = Path(__file__).parent / "icons" / "radio_tower.svg"
    if not icon_path.exists():
        return QPixmap()
    try:
        from PySide6.QtSvg import QSvgRenderer
        from PySide6.QtGui import QPainter
        renderer = QSvgRenderer(str(icon_path))
        if not renderer.isValid():
            return QPixmap()
        pm = QPixmap(size, size)
        pm.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pm)
        renderer.render(painter)
        painter.end()
        return pm
    except Exception:
        return QPixmap()


class ConnectStatusDialog(QDialog):
    """Modaler Status-Dialog waehrend FlexRadio-Connect."""

    attempt_changed = Signal(int, int)
    failed_signal = Signal()

    def __init__(self, parent=None, app_version: str = ""):
        super().__init__(parent)
        self._dots_state = 0
        self._failed = False
        # Bundle J (v0.97.27): Footer-Version aus main.APP_VERSION mitgeben.
        self._app_version = app_version

        self.setWindowTitle("FlexRadio wird verbunden")
        # 11.05.2026: 20% kleiner (Mike-Field-Test).
        # Bundle J: 176→196 fuer Footer-Zeile.
        self.setFixedSize(352, 196)
        self.setModal(True)
        self.setWindowModality(Qt.WindowModality.WindowModal)
        # ApplicationModal wuerde Decoder-Signale blocken — verboten.
        # WindowModal blockiert nur Input am Parent, Event-Loop laeuft.

        self._setup_ui()

        self._tick_timer = QTimer(self)
        self._tick_timer.timeout.connect(self._tick_dots)
        self._tick_timer.start(500)
        self._tick_dots()  # initialer Punkt

        # Cross-thread Signal/Slot Wiring
        self.attempt_changed.connect(self.set_attempt)
        self.failed_signal.connect(self.set_failed)

    # ── UI ──────────────────────────────────────────────────────────────────

    def _setup_ui(self):
        self.setStyleSheet("""
            QDialog { background-color: #16192b; }
            QLabel  { background-color: transparent; color: #CCC; }
            QPushButton {
                background-color: #2a2f4a;
                color: #DDD;
                border: 1px solid #444;
                padding: 6px 14px;
                border-radius: 3px;
            }
            QPushButton:hover { background-color: #3a4060; }
            QPushButton#weiterLink {
                background: transparent;
                border: none;
                color: #6a99c4;
                text-decoration: underline;
                padding: 0;
                text-align: left;
            }
            QPushButton#weiterLink:hover { color: #99c4e3; }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 16)
        layout.setSpacing(10)

        # 11.05.2026 Mike: Funkmast-Icon links vom Title/Spinner.
        # Lucide radio-tower SVG, ISC/MIT-Lizenz. KISS: HBox mit Icon + VBox.
        top_row = QHBoxLayout()
        top_row.setSpacing(12)
        self._icon_label = QLabel()
        pm = _load_radio_tower_pixmap(size=44)
        if not pm.isNull():
            self._icon_label.setPixmap(pm)
        self._icon_label.setFixedSize(48, 48)
        self._icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        top_row.addWidget(self._icon_label, 0, Qt.AlignmentFlag.AlignTop)

        text_col = QVBoxLayout()
        text_col.setSpacing(6)
        title = QLabel("FlexRadio wird verbunden")
        title.setFont(QFont("", 13, QFont.Weight.Bold))
        title.setStyleSheet("color: #7CC; background-color: transparent;")
        text_col.addWidget(title)

        self._spinner_label = QLabel(".")
        self._spinner_label.setFont(QFont("Menlo", 18, QFont.Weight.Bold))
        self._spinner_label.setStyleSheet("color: #7CC;")
        self._spinner_label.setFixedHeight(28)
        text_col.addWidget(self._spinner_label)

        top_row.addLayout(text_col, 1)
        layout.addLayout(top_row)

        # 11.05.2026 Mike-Field-Test: Versuch-Counter raus, Spinner reicht.
        # Label bleibt im Code als Failed-State-Anzeige (sonst nur ein ✗).
        self._attempt_label = QLabel("")
        self._attempt_label.setFont(QFont("Menlo", 11))
        self._attempt_label.setVisible(False)
        layout.addWidget(self._attempt_label)

        layout.addStretch()

        btn_row = QHBoxLayout()
        self._btn_weiter = QPushButton("ohne Radio weiter")
        self._btn_weiter.setObjectName("weiterLink")
        self._btn_weiter.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_weiter.clicked.connect(self._on_continue_without_radio)
        btn_row.addWidget(self._btn_weiter)

        btn_row.addStretch()

        self._btn_quit = QPushButton("Beenden")
        self._btn_quit.clicked.connect(self._on_quit)
        btn_row.addWidget(self._btn_quit)
        layout.addLayout(btn_row)

        # Bundle J (v0.97.27): Footer-Zeile unten rechts mit Version + MIT.
        # 5-7 Sek waehrend Connect-Phase sichtbar — User sieht Version + Lizenz.
        version_text = self._app_version or "?"
        self._footer_label = QLabel(f"SimpleFT8 v{version_text} · MIT License")
        self._footer_label.setStyleSheet(
            "color: #666; font-size: 9pt; background-color: transparent;"
        )
        layout.addWidget(self._footer_label, 0, Qt.AlignmentFlag.AlignRight)

    # ── Animation + Status ─────────────────────────────────────────────────

    @Slot()
    def _tick_dots(self):
        self._dots_state = (self._dots_state + 1) % 3
        self._spinner_label.setText("." * (self._dots_state + 1))

    @Slot(int, int)
    def set_attempt(self, attempt: int, max_attempts: int) -> None:
        """Versuchs-Counter — 11.05.2026 Mike: Anzeige raus, Slot no-op.

        Worker emittet weiterhin (API-Kompatibilitaet, kein Code-Loesch
        in mw_radio noetig). Slot tut bewusst nichts. Failed-State
        kommt ueber set_failed.
        """
        # no-op
        return

    @Slot()
    def set_failed(self) -> None:
        """Worker meldet: alle Versuche durch, kein Connect."""
        self._failed = True
        try:
            self._tick_timer.stop()
        except Exception:
            pass
        self._spinner_label.setText("✗")
        self._spinner_label.setStyleSheet("color: #c44;")
        self._attempt_label.setText(
            "Verbindung fehlgeschlagen — Radio aus oder nicht erreichbar"
        )
        self._attempt_label.setVisible(True)

    # ── Buttons ────────────────────────────────────────────────────────────

    def _on_continue_without_radio(self):
        """User-Bypass: App startet ohne Radio (Demo-Modus)."""
        self.reject()

    def _on_quit(self):
        """User-Quit: App schliesst sauber."""
        QApplication.quit()
        self.reject()  # falls quit() Event-Loop noch nicht beendet hat

    # ── Lifecycle ──────────────────────────────────────────────────────────

    def closeEvent(self, ev):
        try:
            self._tick_timer.stop()
        except Exception:
            pass
        super().closeEvent(ev)
