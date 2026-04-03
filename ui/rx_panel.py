"""SimpleFT8 RX Panel — QTableWidget-basierte Empfangsliste mit auto-resize."""

import time

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTableWidget,
    QTableWidgetItem, QPushButton, QHeaderView, QAbstractItemView,
)
from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QColor, QFont

from core.message import FT8Message
from core.geo import callsign_to_country, grid_distance, callsign_to_distance

# Spalten-Index-Konstanten
COL_UTC = 0
COL_DB = 1
COL_DT = 2
COL_FREQ = 3
COL_LAND = 4
COL_KM = 5
COL_MSG = 6
COL_COUNT = 7

_FONT = QFont("Menlo", 11)
_FONT_SEP = QFont("Menlo", 9)

_COLOR_CQ = QColor("#FF4444")
_COLOR_DIRECTED = QColor("#FFD700")
_COLOR_DONE = QColor("#44FF44")
_COLOR_NORMAL = QColor("#CCCCCC")
_COLOR_SEP = QColor("#444444")

_MAX_CYCLES = 3  # Nur die letzten 3 Zyklen anzeigen


class RXPanel(QWidget):
    """Empfangsfenster — QTableWidget mit auto-resize Spalten.

    Signals:
        station_clicked: (FT8Message)
    """

    station_clicked = Signal(object)

    def __init__(self, my_call: str = "DA1MHH", my_grid: str = "JO31"):
        super().__init__()
        self._my_call = my_call
        self._my_grid = my_grid
        self._cycle_message_count = 0
        self._sort_mode = "time"
        self._rx_active = True
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(2)

        # Header mit EMPFANG-Label + Sort-Buttons
        header_row = QHBoxLayout()
        header = QLabel("EMPFANG")
        header.setStyleSheet(
            "color: #00AAFF; font-weight: bold; font-size: 13px;"
        )
        header_row.addWidget(header)

        # RX ON/OFF Button
        self.btn_rx = QPushButton("RX ON")
        self.btn_rx.setCheckable(True)
        self.btn_rx.setChecked(True)
        self.btn_rx.setFixedHeight(20)
        self.btn_rx.setFixedWidth(52)
        self.btn_rx.setStyleSheet("""
            QPushButton {
                background: #004400; color: #44FF44; border: 1px solid #44FF44;
                border-radius: 2px; font-size: 10px; font-weight: bold;
            }
            QPushButton:checked {
                background: #004400; color: #44FF44; border-color: #44FF44;
            }
            QPushButton:!checked {
                background: #440000; color: #FF4444; border-color: #FF4444;
            }
        """)
        self.btn_rx.clicked.connect(self._on_rx_toggled)
        header_row.addWidget(self.btn_rx)

        header_row.addStretch()

        sort_label = QLabel("Sort:")
        sort_label.setStyleSheet("color: #666; font-size: 10px;")
        header_row.addWidget(sort_label)
        for mode, label in [("time", "Zeit"), ("snr", "dB"),
                             ("dist", "km"), ("country", "Land")]:
            btn = QPushButton(label)
            btn.setFixedHeight(20)
            btn.setStyleSheet("""
                QPushButton {
                    background: #222; color: #888; border: 1px solid #444;
                    border-radius: 2px; padding: 0 6px; font-size: 10px;
                }
                QPushButton:hover { background: #333; color: #CCC; }
            """)
            btn.clicked.connect(lambda _, m=mode: self._set_sort(m))
            header_row.addWidget(btn)

        layout.addLayout(header_row)

        # QTableWidget
        self.table = QTableWidget(0, COL_COUNT)
        self.table.setHorizontalHeaderLabels(
            ["UTC", "dB", "DT", "Freq", "Land", "km", "Message"]
        )
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.table.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        self.table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.table.setShowGrid(False)

        # Spaltenbreiten: alle ResizeToContents, Message -> Stretch
        hdr = self.table.horizontalHeader()
        for col in range(COL_COUNT):
            if col == COL_MSG:
                hdr.setSectionResizeMode(
                    col, QHeaderView.ResizeMode.Stretch
                )
            else:
                hdr.setSectionResizeMode(
                    col, QHeaderView.ResizeMode.ResizeToContents
                )
        hdr.setDefaultAlignment(Qt.AlignmentFlag.AlignLeft)

        # Dark-Theme Styling
        self.table.setStyleSheet("""
            QTableWidget {
                background-color: #0d0d1a;
                border: 1px solid #333;
                border-radius: 3px;
                gridline-color: transparent;
                font-family: Menlo;
                font-size: 11pt;
            }
            QTableWidget::item {
                padding: 1px 4px;
                border-bottom: 1px solid #1a1a2e;
            }
            QTableWidget::item:selected {
                background-color: #0066AA;
            }
            QTableWidget::item:hover {
                background-color: #1a1a3e;
            }
            QHeaderView::section {
                background-color: #1a1a2e;
                color: #666;
                border: none;
                border-bottom: 1px solid #333;
                padding: 2px 4px;
                font-family: Menlo;
                font-size: 10px;
            }
        """)

        # Zeilenhoehe kompakt
        self.table.verticalHeader().setDefaultSectionSize(22)

        self.table.cellDoubleClicked.connect(self._on_cell_double_clicked)
        self.table.currentCellChanged.connect(self._on_selection_changed)
        layout.addWidget(self.table)

        # Antworten-Button
        self.btn_answer = QPushButton("Antworten")
        self.btn_answer.setFixedHeight(28)
        self.btn_answer.setStyleSheet("""
            QPushButton {
                background-color: #0066AA; color: white; border: none;
                border-radius: 3px; font-size: 12px; font-weight: bold;
            }
            QPushButton:hover { background-color: #0088CC; }
            QPushButton:disabled { background-color: #222; color: #555; }
        """)
        self.btn_answer.setEnabled(False)
        self.btn_answer.clicked.connect(self._on_answer_clicked)
        layout.addWidget(self.btn_answer)

    # ── Oeffentliche API (Interface bleibt gleich) ────────────

    def add_message(self, msg: FT8Message):
        """Neue dekodierte Nachricht hinzufuegen."""
        if not self._rx_active:
            return
        self.table.insertRow(0)
        self._populate_row(0, msg)
        self._cycle_message_count += 1

    def add_cycle_separator(self, count: int):
        """Neuer Zyklus: ALLES LOESCHEN, nur aktuelle Stationen zeigen.

        Alter Zyklus ist weg — komplett. Wenn eine Station noch da ist,
        taucht sie im naechsten Zyklus wieder auf.
        """
        if not self._rx_active:
            return
        # ALLES loeschen — nur aktueller Zyklus wird angezeigt
        self.table.setRowCount(0)
        self._cycle_message_count = 0

    # ── Zeilen befuellen ──────────────────────────────────────

    def _populate_row(self, row: int, msg: FT8Message):
        """Eine Tabellenzeile mit FT8Message-Daten befuellen."""
        # Extras berechnen
        country = "?"
        caller = msg.caller
        if caller and caller != "<....>":
            country = callsign_to_country(caller)

        dist_km = 0
        # 1. Bei CQ: Grid des Callers → exakte Entfernung
        if msg.is_cq and msg.is_grid and self._my_grid:
            km = grid_distance(self._my_grid, msg.grid_or_report)
            dist_km = km if km is not None else 0
        # 2. Sonst: Ungefaehre Entfernung aus Callsign-Prefix
        if dist_km == 0 and caller and caller != "<....>" and self._my_grid:
            km = callsign_to_distance(caller, self._my_grid)
            dist_km = km if km is not None else 0

        # Farbe bestimmen
        directed_to_us = msg.target == self._my_call and self._my_call
        if msg.is_cq:
            color = _COLOR_CQ
        elif directed_to_us:
            color = _COLOR_DIRECTED
        elif msg.is_rr73 or msg.is_73:
            color = _COLOR_DONE
        else:
            color = _COLOR_NORMAL

        # UTC: gespeicherte Zeit nutzen wenn vorhanden (Diversity)
        utc = getattr(msg, '_utc_str', None) or time.strftime("%H%M%S", time.gmtime())

        # SNR
        snr_str = f"{msg.snr:+d}" if msg.snr != -30 else "?"

        # DT
        dt_str = (f"{msg.dt:+.1f}" if abs(msg.dt) < 10
                  else f"{msg.dt:.0f}")

        # Freq
        freq_str = str(msg.freq_hz)

        # km
        if dist_km > 0:
            if dist_km >= 10000:
                km_str = f"{dist_km // 1000}k"
            else:
                km_str = str(dist_km)
        else:
            km_str = "-"

        # Message + Antennen-Markierung
        if msg.is_cq:
            msg_text = f"CQ {msg.caller} {msg.grid_or_report}"
        else:
            msg_text = msg.raw
        # Diversity-Markierung anhaengen wenn vorhanden
        ant = getattr(msg, 'antenna', '')
        if ant:
            msg_text = f"{msg_text}  [{ant}]"

        # Zellen setzen
        values = [utc, snr_str, dt_str, freq_str, country, km_str, msg_text]
        for col, text in enumerate(values):
            item = QTableWidgetItem(text)
            item.setFont(_FONT)
            item.setForeground(color)
            # Numerische Spalten rechts ausrichten
            if col in (COL_DB, COL_DT, COL_FREQ, COL_KM):
                item.setTextAlignment(
                    Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                )
            else:
                item.setTextAlignment(
                    Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
                )
            self.table.setItem(row, col, item)

        # Metadaten an Zeile 0 (UTC-Zelle) haengen fuer spaeteres Auslesen
        utc_item = self.table.item(row, COL_UTC)
        utc_item.setData(Qt.ItemDataRole.UserRole, msg)
        utc_item.setData(Qt.ItemDataRole.UserRole + 1, country)
        utc_item.setData(Qt.ItemDataRole.UserRole + 2, dist_km)

    def _populate_separator_row(self, row: int, count: int):
        """Zyklus-Trenner-Zeile einfuegen."""
        utc = time.strftime("%H:%M:%S", time.gmtime())
        if count > 0:
            sep_text = (f"--- {utc} -- {count} "
                        f"Station{'en' if count != 1 else ''} "
                        f"{'---' * 10}")
        else:
            sep_text = f"--- {utc} -- keine Stationen {'---' * 9}"

        # Separator ueber alle Spalten: Text nur in erster Zelle,
        # aber Span ueber alle Spalten
        self.table.setSpan(row, 0, 1, COL_COUNT)

        item = QTableWidgetItem(sep_text)
        item.setFont(_FONT_SEP)
        item.setForeground(_COLOR_SEP)
        item.setFlags(Qt.ItemFlag.NoItemFlags)
        item.setData(Qt.ItemDataRole.UserRole, None)  # Kein FT8Message
        self.table.setItem(row, 0, item)

    # ── Sortierung ────────────────────────────────────────────

    def _on_rx_toggled(self):
        """RX ein/ausschalten. Bei Einschalten: Tabelle leeren."""
        self._rx_active = self.btn_rx.isChecked()
        if self._rx_active:
            self.btn_rx.setText("RX ON")
            self.table.setRowCount(0)
            self._cycle_message_count = 0
        else:
            self.btn_rx.setText("RX OFF")

    def _set_sort(self, mode: str):
        """Tabelle nach Kriterium sortieren."""
        self._sort_mode = mode

        # Alle Station-Zeilen sammeln (keine Separator-Zeilen)
        messages = []
        for r in range(self.table.rowCount()):
            utc_item = self.table.item(r, COL_UTC)
            if utc_item is None:
                continue
            msg = utc_item.data(Qt.ItemDataRole.UserRole)
            if msg is None:
                continue  # Separator
            country = utc_item.data(Qt.ItemDataRole.UserRole + 1) or "?"
            dist_km = utc_item.data(Qt.ItemDataRole.UserRole + 2) or 0
            messages.append((msg, country, dist_km))

        if not messages:
            return

        if mode == "snr":
            messages.sort(key=lambda x: x[0].snr, reverse=True)
        elif mode == "dist":
            messages.sort(key=lambda x: -x[2])
        elif mode == "country":
            messages.sort(key=lambda x: x[1])
        # "time" = Originalreihenfolge (neueste zuerst, bereits so)

        # Tabelle neu aufbauen
        self.table.setRowCount(0)
        for msg, _, _ in messages:
            row = self.table.rowCount()
            self.table.insertRow(row)
            self._populate_row(row, msg)

    # ── Events ────────────────────────────────────────────────

    def _on_cell_double_clicked(self, row: int, _col: int):
        utc_item = self.table.item(row, COL_UTC)
        if utc_item is None:
            return
        msg = utc_item.data(Qt.ItemDataRole.UserRole)
        if msg is not None:
            self.station_clicked.emit(msg)

    def _on_selection_changed(self, row: int, _col: int, _prev_row: int,
                              _prev_col: int):
        if row < 0:
            self.btn_answer.setEnabled(False)
            return
        utc_item = self.table.item(row, COL_UTC)
        if utc_item is None:
            self.btn_answer.setEnabled(False)
            return
        msg = utc_item.data(Qt.ItemDataRole.UserRole)
        self.btn_answer.setEnabled(
            msg is not None and msg.is_cq
        )

    def _on_answer_clicked(self):
        row = self.table.currentRow()
        if row < 0:
            return
        utc_item = self.table.item(row, COL_UTC)
        if utc_item is None:
            return
        msg = utc_item.data(Qt.ItemDataRole.UserRole)
        if msg is not None:
            self.station_clicked.emit(msg)
