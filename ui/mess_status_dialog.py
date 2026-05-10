"""SimpleFT8 MessStatusDialog — Modal waehrend Diversity-Antennen-Mess.

P22 / P8 (10.05.2026): Sperrt Hauptfenster waehrend Phase 3 (Antennen-
vergleich) damit Mike nicht mid-Mess Bandwechsel/Modus/Hunt/CQ ausloest.
Nutzt WindowModal (NICHT ApplicationModal) damit der Qt-Event-Loop
weiter laeuft und Decoder-Signale durchkommen — sonst koennte die
Messung gar nicht laufen.

Schliesst sich:
- automatisch beim Phase-Wechsel measure → operate
  (Aufrufer ruft `accept()` aus mw_cycle._handle_diversity_measure)
- per Cancel-Button (Aufrufer hoert auf `rejected` und raeumt staged
  + Diversity auf, siehe mw_radio._on_mess_status_cancelled)
"""

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
)


class MessStatusDialog(QDialog):
    """Modaler Status-Dialog waehrend Diversity-Antennen-Messung."""

    def __init__(self, diversity_ctrl, parent=None):
        super().__init__(parent)
        self._ctrl = diversity_ctrl
        self._cancelled = False
        self._cycle_dur_s = 15.0  # Default FT8, ueber set_cycle_dur ueberschreibbar

        self.setWindowTitle("Diversity-Antennen werden eingemessen")
        self.setFixedSize(440, 260)
        self.setModal(True)
        self.setWindowModality(Qt.WindowModality.WindowModal)
        # ApplicationModal wuerde Decoder-Signale blocken — verboten!
        # WindowModal blockiert nur Input am Parent, Event-Loop laeuft.

        self._setup_ui()
        self._tick_timer = QTimer(self)
        self._tick_timer.timeout.connect(self._update_view)
        self._tick_timer.start(500)
        self._update_view()

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
            QPushButton:hover  { background-color: #3a4060; }
            QProgressBar {
                background-color: #1a1d2f;
                border: 1px solid #333;
                border-radius: 2px;
                text-align: center;
                color: #BBB;
            }
            QProgressBar::chunk { background-color: #4a90c2; }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 16)
        layout.setSpacing(10)

        title = QLabel("Antennen-Vergleich laeuft")
        title.setFont(QFont("", 13, QFont.Weight.Bold))
        title.setStyleSheet("color: #7CC; background-color: transparent;")
        layout.addWidget(title)

        self._lbl_ant       = QLabel("Antenne: —")
        self._lbl_step      = QLabel("Schritt: 0 / 6")
        self._lbl_remaining = QLabel("Restzeit: —")
        for w in (self._lbl_ant, self._lbl_step, self._lbl_remaining):
            w.setFont(QFont("Menlo", 11))
            layout.addWidget(w)

        self._progress = QProgressBar()
        self._progress.setRange(0, max(1, getattr(self._ctrl, "MEASURE_CYCLES", 6)))
        layout.addWidget(self._progress)

        hint = QLabel(
            "Bitte waehrend der Messung keine Bedienung —\n"
            "App schliesst dieses Fenster automatisch."
        )
        hint.setStyleSheet(
            "color: #888; font-size: 9pt; font-style: italic; "
            "background-color: transparent;"
        )
        layout.addWidget(hint)

        layout.addStretch()

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self._btn_cancel = QPushButton("Messung abbrechen")
        self._btn_cancel.clicked.connect(self._on_cancel)
        btn_row.addWidget(self._btn_cancel)
        layout.addLayout(btn_row)

    # ── Live-Update ─────────────────────────────────────────────────────────

    def _update_view(self):
        try:
            ant   = getattr(self._ctrl, "current_ant", None) or "—"
            step  = int(getattr(self._ctrl, "measure_step", 0))
            total = int(getattr(self._ctrl, "MEASURE_CYCLES", 6))
            remaining_cycles = max(0, total - step)
            remaining_s = int(remaining_cycles * self._cycle_dur_s)
            self._lbl_ant.setText(f"Antenne: {ant}")
            self._lbl_step.setText(f"Schritt: {step} / {total}")
            self._lbl_remaining.setText(f"Restzeit: ~{remaining_s}s")
            self._progress.setValue(step)
        except Exception as exc:
            print(f"[MessStatusDialog] update_view Fehler: {exc}")

    # ── Public API ──────────────────────────────────────────────────────────

    def set_cycle_dur(self, sec: float) -> None:
        """Slot-Dauer aus aktuellem Modus uebergeben (FT8=15, FT4=7.5, FT2=3.8)."""
        self._cycle_dur_s = float(sec)

    @property
    def cancelled(self) -> bool:
        """True wenn Cancel-Button gedrueckt wurde (vs. auto-close via accept)."""
        return self._cancelled

    # ── Internal ────────────────────────────────────────────────────────────

    def _on_cancel(self):
        self._cancelled = True
        self.reject()

    def closeEvent(self, ev):
        try:
            self._tick_timer.stop()
        except Exception:
            pass
        super().closeEvent(ev)
