"""SimpleFT8 QSO Panel — Fenster 2: QSO-Verlauf + Logbuch mit Tabs."""

import time
from pathlib import Path
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTextEdit, QTabWidget,
)
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QFont, QTextCursor, QColor

from ui.logbook_widget import LogbookWidget


class QSOPanel(QWidget):
    """QSO-Verlaufsfenster mit Tabs: Live Log + Logbuch."""

    upload_qrz = Signal()  # QRZ.com Upload angefordert

    def __init__(self):
        super().__init__()
        self._setup_ui()
        self._qso_count = 0

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # EVEN/ODD Slot-Anzeige
        slot_row = QHBoxLayout()
        slot_row.setContentsMargins(2, 0, 2, 0)
        self._even_label = QLabel("EVEN")
        self._odd_label  = QLabel("ODD")
        for lbl in (self._even_label, self._odd_label):
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setFixedHeight(22)
            lbl.setFont(QFont("Menlo", 10, QFont.Weight.Bold))
        slot_row.addWidget(self._even_label)
        slot_row.addWidget(self._odd_label)
        layout.addLayout(slot_row)

        self._slot_timer = QTimer(self)
        self._slot_timer.timeout.connect(self._update_slot_display)
        self._slot_timer.start(500)
        self._update_slot_display()

        # Tab Widget
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #333;
                border-radius: 4px;
                background: #0d0d1a;
            }
            QTabBar::tab {
                background: #1a1a2e;
                color: #888;
                border: 1px solid #333;
                border-bottom: none;
                padding: 6px 20px;
                min-width: 80px;
                font-family: Menlo;
                font-size: 11px;
                font-weight: bold;
            }
            QTabBar::tab:selected {
                background: #0d0d1a;
                color: #00AAFF;
                border-bottom: 2px solid #00AAFF;
            }
            QTabBar::tab:hover {
                color: #CCCCCC;
            }
        """)

        # Tab 1: Live QSO Log
        live_tab = QWidget()
        live_layout = QVBoxLayout(live_tab)
        live_layout.setContentsMargins(0, 4, 0, 0)

        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setFont(QFont("Menlo", 12))
        self.log_view.setStyleSheet("""
            QTextEdit {
                background-color: #0d0d1a;
                color: #CCCCCC;
                border: none;
                padding: 6px;
                selection-background-color: #0066AA;
            }
        """)
        live_layout.addWidget(self.log_view)

        self.status_label = QLabel("Keine QSOs")
        self.status_label.setStyleSheet("color: #666; font-size: 11px; padding: 2px;")
        live_layout.addWidget(self.status_label)

        self.tabs.addTab(live_tab, "QSO")

        # Tab 2: Logbuch
        self.logbook = LogbookWidget()
        self.logbook.upload_requested.connect(self.upload_qrz.emit)
        self.tabs.addTab(self.logbook, "Logbuch")

        layout.addWidget(self.tabs)

    def add_tx(self, message: str):
        """Eigene gesendete Nachricht anzeigen."""
        now = time.time()
        slot_start = now - (now % 15.0)
        utc = time.strftime("%H:%M:%S", time.gmtime(slot_start))
        self._append_colored(f"{utc}  →  Sende   {message}", "#FFAA00")

    def add_rx(self, message: str):
        """Empfangene Antwort anzeigen."""
        now = time.time()
        slot_start = now - (now % 15.0)   # auf Slot-Grenze runden (15s Raster)
        utc = time.strftime("%H:%M:%S", time.gmtime(slot_start))
        self._append_colored(f"{utc}  ←  Empf.   {message}", "#44BBFF")

    def add_qso_complete(self, their_call: str):
        """QSO als abgeschlossen markieren."""
        self._qso_count += 1
        self._append_colored(f"       ✓ QSO mit {their_call} komplett", "#44FF44")
        self._append_colored("─" * 30, "#333333")
        self.status_label.setText(f"{self._qso_count} QSO(s) diese Session")

    def add_timeout(self, their_call: str):
        """Timeout anzeigen."""
        self._append_colored(f"       ✗ {their_call} — Timeout", "#FF4444")
        self._append_colored("─" * 30, "#333333")

    def add_info(self, text: str):
        """Info-Nachricht anzeigen."""
        self._append_colored(f"       {text}", "#666666")

    def _update_slot_display(self):
        """EVEN/ODD Label alle 500ms aktualisieren — zeigt aktuellen TX-Slot."""
        now = time.time()
        cycle_num = int(now / 15.0)
        is_even = (cycle_num % 2 == 0)
        active   = "#00FF88"   # hell grün = aktiver Slot
        inactive = "#333344"   # dunkel = inaktiver Slot
        txt_act  = "#000000"
        txt_inact= "#555566"
        if is_even:
            self._even_label.setStyleSheet(
                f"background:{active}; color:{txt_act}; border-radius:3px;")
            self._odd_label.setStyleSheet(
                f"background:{inactive}; color:{txt_inact}; border-radius:3px;")
        else:
            self._even_label.setStyleSheet(
                f"background:{inactive}; color:{txt_inact}; border-radius:3px;")
            self._odd_label.setStyleSheet(
                f"background:{active}; color:{txt_act}; border-radius:3px;")

    def _append_colored(self, text: str, color: str):
        cursor = self.log_view.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self.log_view.setTextCursor(cursor)
        self.log_view.setTextColor(QColor(color))
        self.log_view.append(text)
        # Auto-Scroll nach unten
        scrollbar = self.log_view.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
