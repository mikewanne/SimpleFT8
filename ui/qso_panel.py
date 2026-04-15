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

    def _slot_tag(self) -> str:
        """Aktuellen Slot als Tag: [E] oder [O]."""
        now = time.time()
        slot = getattr(self, '_cycle_duration', 15.0)
        return "[E]" if int(now / slot) % 2 == 0 else "[O]"

    def add_tx(self, message: str):
        """Eigene gesendete Nachricht anzeigen. CQ-Wiederholungen zusammenfassen."""
        now = time.time()
        slot = getattr(self, '_cycle_duration', 15.0)
        slot_start = now - (now % slot)
        utc = time.strftime("%H:%M:%S", time.gmtime(slot_start))
        tag = self._slot_tag()
        is_cq = message.startswith("CQ ")

        if is_cq:
            self._cq_count = getattr(self, '_cq_count', 0) + 1
            if self._cq_count > 2:
                doc = self.log_view.document()
                cursor = QTextCursor(doc)
                cursor.movePosition(QTextCursor.MoveOperation.End)
                cursor.movePosition(QTextCursor.MoveOperation.StartOfBlock, QTextCursor.MoveMode.KeepAnchor)
                cursor.removeSelectedText()
                cursor.deletePreviousChar()
                self._append_colored(f"{utc} {tag} →  CQ ×{self._cq_count}", "#886600")
                return
            self._append_colored(f"{utc} {tag} →  Sende   {message}", "#FFAA00")
        else:
            self._cq_count = 0
            self._append_colored(f"{utc} {tag} →  Sende   {message}", "#FFAA00")
        self._auto_trim()

    def add_rx(self, message: str):
        """Empfangene Antwort anzeigen."""
        self._cq_count = 0
        now = time.time()
        slot = getattr(self, '_cycle_duration', 15.0)
        slot_start = now - (now % slot)
        utc = time.strftime("%H:%M:%S", time.gmtime(slot_start))
        tag = self._slot_tag()
        self._append_colored(f"{utc} {tag} ←  Empf.   {message}", "#44BBFF")

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
        # Modus-abhaengige Slot-Dauer (FT8=15, FT4=7.5, FT2=3.8)
        slot = getattr(self, '_cycle_duration', 15.0)
        cycle_num = int(now / slot)
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

    def _auto_trim(self, max_lines: int = 40):
        """QSO-Log auf ~40 Zeilen begrenzen (~3 Min Traffic)."""
        doc = self.log_view.document()
        excess = doc.blockCount() - max_lines
        if excess > 5:
            cursor = QTextCursor(doc)
            cursor.movePosition(QTextCursor.MoveOperation.Start)
            for _ in range(excess):
                cursor.movePosition(QTextCursor.MoveOperation.Down, QTextCursor.MoveMode.KeepAnchor)
            cursor.removeSelectedText()
            cursor.deleteChar()
