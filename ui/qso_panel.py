"""SimpleFT8 QSO Panel — Fenster 2: QSO-Verlauf + Logbuch mit Tabs."""

import time
from pathlib import Path
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTextEdit,
    QPushButton, QStackedWidget, QSizePolicy,
)
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QFont, QTextCursor, QColor, QTextCharFormat

from ui.logbook_widget import LogbookWidget


# Signal wie von QTabWidget — Mixin sendet Index-Wechsel
class QSOPanel(QWidget):
    """QSO-Verlaufsfenster mit Tabs: Live Log + Logbuch."""

    upload_qrz = Signal()  # QRZ.com Upload angefordert

    def __init__(self):
        super().__init__()
        self._setup_ui()
        self._qso_count = 0
        # P1.16: zeitbasiertes Rolling-Window — Block-Timestamps parallel zu log_view-Blocks
        self._block_timestamps: list[float] = []
        self._cleanup_timer = QTimer(self)
        self._cleanup_timer.setInterval(30_000)  # 30s
        self._cleanup_timer.timeout.connect(self._auto_trim_by_age)
        self._cleanup_timer.start()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # ── Kopf-Zeile: links EVEN/ODD | rechts QSO/Logbuch-Tabs ──
        head_row = QHBoxLayout()
        head_row.setContentsMargins(2, 0, 2, 0)
        head_row.setSpacing(8)

        # Links: EVEN/ODD
        slot_container = QWidget()
        slot_container.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        slot_row = QHBoxLayout(slot_container)
        slot_row.setContentsMargins(0, 0, 0, 0)
        slot_row.setSpacing(4)
        self._even_label = QLabel("EVEN")
        self._odd_label  = QLabel("ODD")
        for lbl in (self._even_label, self._odd_label):
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setFixedHeight(22)
            lbl.setFont(QFont("Menlo", 10, QFont.Weight.Bold))
            lbl.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        slot_row.addWidget(self._even_label)
        slot_row.addWidget(self._odd_label)

        # Rechts: QSO/Logbuch Tab-Buttons
        tabs_container = QWidget()
        tabs_container.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        tabs_row = QHBoxLayout(tabs_container)
        tabs_row.setContentsMargins(0, 0, 0, 0)
        tabs_row.setSpacing(0)
        self._btn_tab_qso = QPushButton("QSO")
        self._btn_tab_log = QPushButton("Logbuch")
        for btn in (self._btn_tab_qso, self._btn_tab_log):
            btn.setCheckable(True)
            btn.setFixedHeight(22)
            btn.setFont(QFont("Menlo", 10, QFont.Weight.Bold))
            btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_tab_qso.setChecked(True)
        self._apply_tab_button_style()
        self._btn_tab_qso.clicked.connect(lambda: self._set_tab_index(0))
        self._btn_tab_log.clicked.connect(lambda: self._set_tab_index(1))
        tabs_row.addWidget(self._btn_tab_qso)
        tabs_row.addWidget(self._btn_tab_log)

        head_row.addWidget(slot_container, 1)
        head_row.addWidget(tabs_container, 1)
        layout.addLayout(head_row)

        self._slot_timer = QTimer(self)
        self._slot_timer.timeout.connect(self._update_slot_display)
        self._slot_timer.start(500)
        self._update_slot_display()

        # ── Inhalt: QStackedWidget ersetzt QTabWidget ──
        self.tabs = QStackedWidget()
        self.tabs.setStyleSheet(
            "QStackedWidget { border: 1px solid #333; border-radius: 4px; "
            "background: #0d0d1a; }"
        )
        # currentChanged → damit _on_qso_tab_changed im Main Window weiter funktioniert
        self.tabs.currentChanged.connect(self._on_tab_changed_internal)

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

        self.tabs.addWidget(live_tab)

        # Tab 2: Logbuch
        self.logbook = LogbookWidget()
        self.logbook.upload_requested.connect(self.upload_qrz.emit)
        self.tabs.addWidget(self.logbook)

        layout.addWidget(self.tabs)

    # Kompatibilitaet mit QTabWidget API (main_window.py ruft tabs.currentChanged)
    def _on_tab_changed_internal(self, index: int):
        self._btn_tab_qso.setChecked(index == 0)
        self._btn_tab_log.setChecked(index == 1)
        self._apply_tab_button_style()

    def _set_tab_index(self, index: int):
        self.tabs.setCurrentIndex(index)

    def _apply_tab_button_style(self):
        active_ss = (
            "QPushButton { background: #0d0d1a; color: #00AAFF; "
            "border: 1px solid #333; border-bottom: 2px solid #00AAFF; "
            "font-family: Menlo; font-size: 11px; font-weight: bold; }"
        )
        inactive_ss = (
            "QPushButton { background: #1a1a2e; color: #888; "
            "border: 1px solid #333; "
            "font-family: Menlo; font-size: 11px; font-weight: bold; }"
            "QPushButton:hover { color: #CCCCCC; }"
        )
        self._btn_tab_qso.setStyleSheet(active_ss if self._btn_tab_qso.isChecked() else inactive_ss)
        self._btn_tab_log.setStyleSheet(active_ss if self._btn_tab_log.isChecked() else inactive_ss)

    def _slot_tag(self) -> str:
        """Aktuellen Slot als Tag: [E] oder [O]."""
        now = time.time()
        slot = getattr(self, '_cycle_duration', 15.0)
        return "[E]" if int(now / slot) % 2 == 0 else "[O]"

    def add_tx(self, message: str, ant_label: str = "",
               tx_even: bool | None = None,
               slot_start_ts: float | None = None,
               omni_remaining: int | None = None):
        """Eigene gesendete Nachricht — IMMER ins Log (Mike-Wunsch v0.78:
        keine Sammelanzeige, alle CQ-Rufe einzeln untereinander sichtbar).

        tx_even/slot_start_ts: bevorzugte Slot-Quelle (vom Encoder
        durchgereicht, latenz-frei). Fallback fuer Tests/alte Caller:
        time.time() zur Aufruf-Zeit.

        omni_remaining: P23 — wenn nicht None: Suffix `  ↻{n}` direkt an
        die Hauptzeile anhaengen (in Hauptfarbe). ant_label kommt danach
        in seiner grauen Akzentfarbe wie heute.
        """
        if slot_start_ts is None or tx_even is None:
            now = time.time()
            slot = getattr(self, '_cycle_duration', 15.0)
            slot_start_ts = now - (now % slot)
            tx_even = int(slot_start_ts / slot) % 2 == 0
        utc = time.strftime("%H:%M:%S", time.gmtime(slot_start_ts))
        tag = "[E]" if tx_even else "[O]"
        # 11.05.2026 Mike: Spalten schmaler — 1 Leerzeichen statt mehrerer.
        line = f"{utc} {tag} → Sende {message}"
        if omni_remaining is not None:
            line = f"{line} ↻{omni_remaining}"
        if ant_label:
            self._append_two_color(line, "#FFAA00", f" {ant_label}", "#888888")
        else:
            self._append_colored(line, "#FFAA00")
        # P1.16: _auto_trim_by_age laeuft via QTimer alle 30s, kein expliziter Aufruf hier

    def add_rx(self, message: str,
               tx_even: bool | None = None,
               slot_start_ts: float | None = None,
               ant_label: str = ""):
        """Empfangene Antwort anzeigen.

        tx_even/slot_start_ts: bevorzugte Slot-Quelle (Decoder-gesetzt
        ueber msg._tx_even / msg._slot_start_ts). Fallback fuer Tests/
        alte Caller: time.time() zur Aufruf-Zeit (kann durch Decoder-
        Latenz im Folge-Slot landen — nur fuer Mocks akzeptabel).

        ant_label: P15 (10.05.2026 Mike-Field-Test) — '(ANT2 ↑X.X dB)'
        zeigt welche Antenne RX gewann. Hinter Empf.-Eintrag in Grau.
        TX-Hardware sendet IMMER ANT1 (verriegelt) — Label gehoert NUR
        zum RX-Eintrag.
        """
        if slot_start_ts is None or tx_even is None:
            now = time.time()
            slot = getattr(self, '_cycle_duration', 15.0)
            slot_start_ts = now - (now % slot)
            tx_even = int(slot_start_ts / slot) % 2 == 0
        utc = time.strftime("%H:%M:%S", time.gmtime(slot_start_ts))
        tag = "[E]" if tx_even else "[O]"
        line = f"{utc} {tag} ← Empf. {message}"
        if ant_label:
            self._append_two_color(line, "#44BBFF", f" {ant_label}", "#888888")
        else:
            self._append_colored(line, "#44BBFF")

    def add_listening(self, slot_start_ts: float, tx_even: bool):
        """OMNI RX-Slot-Anzeige (Mike-Wunsch P3.OMNI-PATTERN-FIX-2 v0.95.25).

        Lebenszeichen in stillen RX-Slots — Mike sieht dass App lauft
        auch wenn keine Stationen decodiert wurden. Aufgerufen aus
        mw_qso._on_send_message bei OMNI-RX-Slot-Skip.

        Format wie add_rx: 'HH:MM:SS [E/O] ←  Horche  …' in Grau (#666).
        Spam-begrenzt durch _auto_trim_by_age (5min Window).
        """
        utc = time.strftime("%H:%M:%S", time.gmtime(slot_start_ts))
        tag = "[E]" if tx_even else "[O]"
        self._append_colored(f"{utc} {tag} ← Horche …", "#666666")

    def add_qso_complete(self, their_call: str):
        """QSO als abgeschlossen markieren."""
        self._qso_count += 1
        self._append_colored(f"       ✓ QSO mit {their_call} komplett", "#44FF44")
        self._append_colored("─" * 30, "#333333")
        # Reset Style nach moeglicher Live-QSO-Anzeige (war gruen, fett).
        self.status_label.setText(f"{self._qso_count} QSO(s) diese Session")
        self.status_label.setStyleSheet("color: #666; font-size: 11px; padding: 2px;")

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
        # P1.16: Timestamp parallel zu Block fuer 5-Min-Rolling-Window
        self._block_timestamps.append(time.time())
        # Auto-Scroll nach unten
        scrollbar = self.log_view.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def _append_two_color(self, text1: str, color1: str, text2: str, color2: str):
        cursor = self.log_view.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self.log_view.setTextCursor(cursor)
        self.log_view.setTextColor(QColor(color1))
        self.log_view.append(text1)
        # P1.16: Timestamp — _append_two_color erzeugt EINEN Block (append=Block, insertText=im-Block)
        self._block_timestamps.append(time.time())
        cursor = self.log_view.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        fmt = QTextCharFormat()
        fmt.setForeground(QColor(color2))
        cursor.insertText(text2, fmt)
        self.log_view.setTextCursor(cursor)
        scrollbar = self.log_view.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def _auto_trim_by_age(self, max_age_s: float = 300.0):
        """P1.16: Eintraege aelter als max_age_s (default 5 Min) entfernen.

        Defensiv gegen externe `clear()` (R1-KP2): synct Liste mit blockCount.
        Mindest-Schwelle 5 verhindert Flackern bei kleinen Mengen.
        """
        doc = self.log_view.document()
        block_count = doc.blockCount()
        # KP2 Resync: falls extern geleert oder Liste-out-of-sync
        if len(self._block_timestamps) > block_count:
            self._block_timestamps = self._block_timestamps[-block_count:]

        now = time.time()
        cutoff = now - max_age_s
        n_old = sum(1 for ts in self._block_timestamps if ts < cutoff)
        if n_old < 5:  # Mindest-Schwelle gegen Flackern
            return

        # Scroll-Position merken
        scrollbar = self.log_view.verticalScrollBar()
        was_at_bottom = scrollbar.value() >= scrollbar.maximum() - 5

        cursor = QTextCursor(doc)
        cursor.movePosition(QTextCursor.MoveOperation.Start)
        for _ in range(n_old):
            cursor.movePosition(
                QTextCursor.MoveOperation.Down,
                QTextCursor.MoveMode.KeepAnchor)
        cursor.removeSelectedText()
        cursor.deleteChar()

        self._block_timestamps = self._block_timestamps[n_old:]

        if was_at_bottom:
            scrollbar.setValue(scrollbar.maximum())
