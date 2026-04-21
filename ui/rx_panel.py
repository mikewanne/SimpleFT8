"""SimpleFT8 RX Panel — QTableWidget-basierte Empfangsliste mit auto-resize."""

import time

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTableWidget,
    QTableWidgetItem, QPushButton, QHeaderView, QAbstractItemView, QMenu,
    QFrame, QSizePolicy,
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
COL_ANT = 7
COL_SLOT = 8
COL_COUNT = 9

_FONT = QFont("Menlo", 11)
_FONT_SEP = QFont("Menlo", 9)

_COLOR_CQ = QColor("#FF4444")
_COLOR_DIRECTED = QColor("#FFD700")
_COLOR_DONE = QColor("#44FF44")
_COLOR_NORMAL = QColor("#CCCCCC")
_COLOR_SEP = QColor("#444444")
_COLOR_ACTIVE_CALL_BG = QColor("#2A1500")   # Dunkles Amber: aktiv angerufene Station
_COLOR_ANSWER_ME_BG  = QColor("#2A1F00")   # Dunkles Amber: eigenes Callsign angesprochen

_MAX_CYCLES = 3  # Nur die letzten 3 Zyklen anzeigen


class RXPanel(QWidget):
    """Empfangsfenster — QTableWidget mit auto-resize Spalten.

    Signals:
        station_clicked: (FT8Message)
    """

    station_clicked = Signal(object)
    rx_toggled = Signal(bool)  # True=RX ON, False=RX OFF
    country_filter_changed = Signal(list)  # gefilterte Länder (für Settings)

    def __init__(self, my_call: str = "DA1MHH", my_grid: str = "JO31",
                 country_filter: list = None):
        super().__init__()
        self._my_call = my_call
        self._my_grid = my_grid
        self._cycle_message_count = 0
        self._sort_mode = "time"
        self._rx_active = True
        self._country_filter: set = set(country_filter or [])
        self._ant_filter: int = 0  # 0=alle, 1=A1, 2=A2
        self._active_call: str = ""  # Callsign der gerade aktiv angerufenen Station
        self._qso_log = None  # QSOLog fuer Worked-Before Filter
        self._hidden_cols: set = set()
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(2)

        # ── Control Row: EMPFANG | RX ON/OFF | separator | CQ | Land ──
        header_row = QHBoxLayout()
        header_row.setSpacing(4)

        lbl = QLabel("EMPFANG")
        lbl.setStyleSheet("color: #00AAFF; font-weight: bold; font-size: 13px;")
        header_row.addWidget(lbl)

        self.btn_rx = QPushButton("RX ON")
        self.btn_rx.setCheckable(True)
        self.btn_rx.setChecked(True)
        self.btn_rx.setFixedHeight(20)
        self.btn_rx.setFixedWidth(52)
        self.btn_rx.setStyleSheet("""
            QPushButton { background:#004400; color:#44FF44; border:1px solid #44FF44;
                border-radius:2px; font-size:10px; font-weight:bold; }
            QPushButton:checked { background:#004400; color:#44FF44; border-color:#44FF44; }
            QPushButton:!checked { background:#440000; color:#FF4444; border-color:#FF4444; }
        """)
        self.btn_rx.clicked.connect(self._on_rx_toggled)
        header_row.addWidget(self.btn_rx)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setFixedWidth(1)
        sep.setStyleSheet("background:#555; margin:3px 2px;")
        header_row.addWidget(sep)

        _FILTER_STYLE = """
            QPushButton { background:#222; color:#888; border:1px solid #444;
                border-radius:2px; font-size:10px; font-weight:bold; }
            QPushButton:checked { background:#883300; color:#FFFFFF; border-color:#FF6622; }
            QPushButton:hover { background:#333; color:#CCC; }
        """

        self.btn_cq_filter = QPushButton("CQ")
        self.btn_cq_filter.setCheckable(True)
        self.btn_cq_filter.setChecked(False)
        self.btn_cq_filter.setFixedHeight(20)
        self.btn_cq_filter.setFixedWidth(36)
        self.btn_cq_filter.setToolTip("Nur CQ-Rufe anzeigen")
        self.btn_cq_filter.setStyleSheet(_FILTER_STYLE)
        self.btn_cq_filter.clicked.connect(self._on_cq_filter_toggled)
        header_row.addWidget(self.btn_cq_filter)

        self.btn_land_filter = QPushButton("Land")
        self.btn_land_filter.setCheckable(True)
        self.btn_land_filter.setChecked(bool(self._country_filter))
        self.btn_land_filter.setFixedHeight(20)
        self.btn_land_filter.setFixedWidth(40)
        self.btn_land_filter.setToolTip("Länder ausblenden")
        self.btn_land_filter.setStyleSheet(_FILTER_STYLE)
        self.btn_land_filter.clicked.connect(self._on_land_filter_clicked)
        header_row.addWidget(self.btn_land_filter)

        # Ant-Filter Button (3 Zustände: Alle → A1 → A2)
        self.btn_ant_filter = QPushButton("Ant")
        self.btn_ant_filter.setFixedHeight(20)
        self.btn_ant_filter.setFixedWidth(36)
        self.btn_ant_filter.setToolTip("Filter: Alle / ANT1 / ANT2")
        self.btn_ant_filter.setStyleSheet(_FILTER_STYLE)
        self.btn_ant_filter.clicked.connect(self._on_ant_filter_clicked)
        header_row.addWidget(self.btn_ant_filter)

        # NEW-Filter: nur ungearbeitete Stationen
        self.btn_new_filter = QPushButton("NEW")
        self.btn_new_filter.setCheckable(True)
        self.btn_new_filter.setChecked(False)
        self.btn_new_filter.setFixedHeight(20)
        self.btn_new_filter.setFixedWidth(40)
        self.btn_new_filter.setToolTip("Nur neue Stationen (schon gearbeitete ausblenden)")
        self.btn_new_filter.setStyleSheet(_FILTER_STYLE)
        self.btn_new_filter.clicked.connect(self._apply_filters)
        header_row.addWidget(self.btn_new_filter)

        header_row.addStretch()
        layout.addLayout(header_row)

        # ── QTableWidget mit nativem QHeaderView (100% Alignment-sicher) ──
        self.table = QTableWidget(0, COL_COUNT)
        # Führende/Nachfolgende Spaces justieren Textposition pro Spalte:
        # links-ausgerichtet + vorangestelltes Leerzeichen = nach rechts
        # rechts-ausgerichtet + nachgestelltes Leerzeichen = nach links
        self.table.setHorizontalHeaderLabels(
            [" UTC", "dB ", "DT ", "Freq ", " Land", "km ", " Message", "    Ant", "Slot"]
        )
        hdr = self.table.horizontalHeader()
        hdr.setSectionsClickable(True)
        hdr.setSortIndicatorShown(False)
        hdr.setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        hdr.setCursor(Qt.CursorShape.PointingHandCursor)
        hdr.sectionClicked.connect(self._on_header_clicked)
        hdr.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        hdr.customContextMenuRequested.connect(self._on_header_context_menu)

        # Alle Spaltenköpfe: einheitliche Farbe + explizite Vertikal-Ausrichtung
        for col in range(COL_COUNT):
            item = self.table.horizontalHeaderItem(col)
            if item:
                item.setForeground(QColor("#AAA"))
                if col in (COL_DB, COL_DT, COL_FREQ, COL_KM):
                    item.setTextAlignment(
                        Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                else:
                    item.setTextAlignment(
                        Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setShowGrid(False)

        _WIDTHS = {
            COL_UTC: 66, COL_DB: 40, COL_DT: 46, COL_FREQ: 50,
            COL_LAND: 100, COL_KM: 58, COL_ANT: 52, COL_SLOT: 32,
        }
        for col in range(COL_COUNT):
            if col == COL_MSG:
                hdr.setSectionResizeMode(col, QHeaderView.ResizeMode.Stretch)
            else:
                hdr.setSectionResizeMode(col, QHeaderView.ResizeMode.Interactive)
                self.table.setColumnWidth(col, _WIDTHS.get(col, 60))

        self.table.setStyleSheet("""
            QTableWidget {
                background-color: #0d0d1a; border: 1px solid #333; border-radius: 3px;
                gridline-color: transparent; font-family: Menlo; font-size: 11pt;
            }
            QTableWidget::item { padding: 1px 4px; border-bottom: 1px solid #1a1a2e; }
            QTableWidget::item:selected { background-color: #0066AA; }
            QTableWidget::item:hover { background-color: #1a1a3e; }
            QHeaderView::section {
                background-color: #1e2035;
                border: none; border-right: 1px solid #2a2a3e; border-bottom: 2px solid #444;
                padding: 2px 4px; font-family: Menlo; font-size: 10px;
            }
            QHeaderView::section:hover { background-color: #252540; }
        """)
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

    def set_qso_log(self, qso_log):
        """QSOLog setzen fuer Worked-Before Filter."""
        self._qso_log = qso_log

    def set_active_call(self, callsign: str):
        """Aktiv angerufene Station hervorheben (amber Hintergrund + bold)."""
        self._active_call = callsign or ""
        self._apply_active_highlight()

    def _apply_active_highlight(self):
        """Alle Zeilen: Hintergrund fuer _active_call + Answer-Me setzen, Rest loeschen."""
        empty_bg = QColor()
        for row in range(self.table.rowCount()):
            utc_item = self.table.item(row, COL_UTC)
            if utc_item is None:
                continue
            msg = utc_item.data(Qt.ItemDataRole.UserRole)
            if msg is None:
                continue
            is_active = bool(self._active_call and
                             getattr(msg, 'caller', '') == self._active_call)
            is_answer_me = bool(self._my_call and
                                getattr(msg, 'target', '') == self._my_call)
            if is_active:
                bg = _COLOR_ACTIVE_CALL_BG
            elif is_answer_me:
                bg = _COLOR_ANSWER_ME_BG
            else:
                bg = empty_bg
            for col in range(COL_COUNT):
                item = self.table.item(row, col)
                if item:
                    item.setBackground(bg)
                    f = item.font()
                    f.setBold(is_active)
                    item.setFont(f)

    def add_message(self, msg: FT8Message):
        """Neue dekodierte Nachricht hinzufuegen."""
        if not self._rx_active:
            return
        utc_new = getattr(msg, '_utc_display', None) or getattr(msg, '_utc_str', None) or time.strftime("%H%M%S", time.gmtime())
        # Sorted insert: absteigende UTC-Reihenfolge (neueste oben), HHMMSS-Stringvergleich
        insert_pos = self.table.rowCount()
        for row in range(self.table.rowCount()):
            item = self.table.item(row, COL_UTC)
            if item is None:
                insert_pos = row
                break
            if utc_new > item.text():
                insert_pos = row
                break
        self.table.insertRow(insert_pos)
        self._populate_row(insert_pos, msg)
        # Highlight direkt setzen wenn diese Station aktiv angerufen wird
        if self._active_call and getattr(msg, 'caller', '') == self._active_call:
            for col in range(COL_COUNT):
                item = self.table.item(insert_pos, col)
                if item:
                    item.setBackground(_COLOR_ACTIVE_CALL_BG)
                    f = item.font()
                    f.setBold(True)
                    item.setFont(f)
        self._cycle_message_count += 1
        self.table.setRowHidden(insert_pos, self._row_should_hide(insert_pos))

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
        # Portable/Mobile Suffix entfernen fuer Country-Lookup: ON3MOH/P → ON3MOH
        # Ausnahme: Sonderpraefixe wie EA8/DA1MHH → EA8 ist das Land
        lookup_call = caller
        if caller and "/" in caller:
            parts = caller.split("/")
            # Mobil-Suffixe: P, M, MM, AM, QRP, portable → Basisrufzeichen nutzen
            MOBILE_SUFFIXES = {"P", "M", "MM", "AM", "QRP", "PORTABLE", "MOBILE"}
            if parts[-1].upper() in MOBILE_SUFFIXES:
                lookup_call = parts[0]
            # Sonstige Schraegstrich-Calls: laengeres Teil ist meist das Rufzeichen
            else:
                lookup_call = max(parts, key=len)

        if lookup_call and lookup_call != "<....>":
            country = callsign_to_country(lookup_call)

        dist_km = 0
        dist_approx = False
        # 1. Bei CQ: Grid des Callers → exakte Entfernung
        if msg.is_cq and msg.is_grid and self._my_grid:
            km = grid_distance(self._my_grid, msg.grid_or_report)
            dist_km = km if km is not None else 0
        # 2. Sonst: Ungefaehre Entfernung aus Callsign-Prefix
        if dist_km == 0 and lookup_call and lookup_call != "<....>" and self._my_grid:
            km = callsign_to_distance(lookup_call, self._my_grid)
            if km is not None:
                dist_km = km
                dist_approx = True

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

        # UTC: _utc_display zeigt wann sich der Inhalt zuletzt geaendert hat
        # (nicht wann zuletzt dekodiert — das waere bei Diversity immer "jetzt")
        utc = getattr(msg, '_utc_display', None) or getattr(msg, '_utc_str', None) or time.strftime("%H%M%S", time.gmtime())

        # SNR
        snr_str = f"{msg.snr:+d}" if msg.snr != -30 else "?"

        # DT
        dt_str = (f"{msg.dt:+.1f}" if abs(msg.dt) < 10
                  else f"{msg.dt:.0f}")

        # Freq
        freq_str = str(msg.freq_hz)

        # km
        if dist_km > 0:
            prefix = "~" if dist_approx else ""
            if dist_km >= 10000:
                km_str = f"{prefix}{dist_km // 1000}k"
            else:
                km_str = f"{prefix}{dist_km}"
        else:
            km_str = "-"

        # Message + Antennen-Markierung
        if msg.is_cq:
            msg_text = f"CQ {msg.caller} {msg.grid_or_report}"
        else:
            msg_text = msg.raw
        # Antenne als eigene Spalte
        ant_str = getattr(msg, 'antenna', '') or ""

        # Even/Odd Slot
        tx_even = getattr(msg, '_tx_even', None)
        slot_str = "E" if tx_even else ("O" if tx_even is False else "")

        # Zellen setzen
        values = [utc, snr_str, dt_str, freq_str, country, km_str, msg_text, ant_str, slot_str]
        for col, text in enumerate(values):
            item = QTableWidgetItem(text)
            item.setFont(_FONT)
            item.setForeground(color)
            # Numerische Spalten rechts ausrichten
            if col in (COL_DB, COL_DT, COL_FREQ, COL_KM, COL_ANT):
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

        # Answer-Me: Hintergrund wenn eigenes Callsign direkt angesprochen
        if directed_to_us:
            for col in range(COL_COUNT):
                it = self.table.item(row, col)
                if it:
                    it.setBackground(_COLOR_ANSWER_ME_BG)

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
        self.rx_toggled.emit(self._rx_active)

    def _on_header_clicked(self, col: int):
        """Klick auf nativen Spaltenkopf → sortieren + Farbe aktualisieren."""
        _COL_TO_SORT = {COL_UTC: "time", COL_DB: "snr", COL_LAND: "country", COL_KM: "dist"}
        if col in _COL_TO_SORT:
            self._set_sort(_COL_TO_SORT[col])
            self._update_sort_colors()

    def _on_header_context_menu(self, pos):
        """Rechtsklick auf Spaltenkopf: Spalten ein-/ausblenden."""
        _TOGGLEABLE = [
            (COL_UTC, "UTC"), (COL_DB, "dB"), (COL_DT, "DT"), (COL_FREQ, "Freq"),
            (COL_LAND, "Land"), (COL_KM, "km"), (COL_ANT, "Ant"), (COL_SLOT, "Slot"),
        ]
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu { background: #1a1a2e; color: #CCC; border: 1px solid #444; }
            QMenu::item { padding: 4px 20px 4px 28px; }
            QMenu::item:selected { background: #0066AA; }
            QMenu::item:checked { color: #00AAFF; }
            QMenu::indicator { width: 14px; height: 14px; }
        """)
        for col, label in _TOGGLEABLE:
            action = menu.addAction(label)
            action.setCheckable(True)
            action.setChecked(col not in self._hidden_cols)
            action.triggered.connect(
                lambda checked, c=col: self._toggle_column(c, not checked)
            )
        menu.exec(self.table.horizontalHeader().mapToGlobal(pos))

    def _toggle_column(self, col: int, hide: bool):
        """Spalte ein-/ausblenden und Zustand merken."""
        if hide:
            self._hidden_cols.add(col)
        else:
            self._hidden_cols.discard(col)
        self.table.setColumnHidden(col, hide)

    def _update_sort_colors(self):
        """Aktive Sortierung im Spaltenkopf markieren (Farbe + ▾)."""
        _COL_TO_SORT = {COL_UTC: "time", COL_DB: "snr", COL_LAND: "country", COL_KM: "dist"}
        _LABELS = {COL_UTC: " UTC", COL_DB: "dB ", COL_DT: "DT ", COL_FREQ: "Freq ",
                   COL_LAND: " Land", COL_KM: "km ", COL_MSG: " Message", COL_ANT: "    Ant",
                   COL_SLOT: "Slot"}
        for col in range(COL_COUNT):
            item = self.table.horizontalHeaderItem(col)
            if item is None:
                continue
            label = _LABELS.get(col, "")
            if _COL_TO_SORT.get(col) == self._sort_mode:
                item.setText(f"{label}▾")
                item.setForeground(QColor("#00AAFF"))
            else:
                item.setText(label)
                item.setForeground(QColor("#AAA"))
            # Ausrichtung nach jedem Text-Update explizit neu setzen
            if col in (COL_DB, COL_DT, COL_FREQ, COL_KM):
                item.setTextAlignment(
                    Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            else:
                item.setTextAlignment(
                    Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

    def _on_ant_filter_clicked(self):
        """Ant-Filter: Alle → A1 → A2 → Alle"""
        self._ant_filter = (self._ant_filter + 1) % 3
        texts  = ["Ant", "A1 ▾", "A2 ▾"]
        styles = [
            "QPushButton{background:#222;color:#888;border:1px solid #444;border-radius:2px;font-size:10px;font-weight:bold;}QPushButton:hover{background:#333;color:#CCC;}",
            "QPushButton{background:#003366;color:#00AAFF;border:1px solid #0066AA;border-radius:2px;font-size:10px;font-weight:bold;}",
            "QPushButton{background:#664400;color:#FFCC00;border:1px solid #FFAA00;border-radius:2px;font-size:10px;font-weight:bold;}",
        ]
        self.btn_ant_filter.setText(texts[self._ant_filter])
        self.btn_ant_filter.setStyleSheet(styles[self._ant_filter])
        self._apply_filters()

    def reapply_sort(self):
        """Aktuelle Sortierung erneut anwenden (nach Tabellen-Rebuild)."""
        if self._sort_mode != "time":
            self._set_sort(self._sort_mode)

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
        elif mode == "time":
            messages.sort(key=lambda x: getattr(x[0], '_utc_display', None) or getattr(x[0], '_utc_str', None) or '', reverse=True)

        # Tabelle neu aufbauen
        self.table.setRowCount(0)
        for msg, _, _ in messages:
            row = self.table.rowCount()
            self.table.insertRow(row)
            self._populate_row(row, msg)
            self.table.setRowHidden(row, self._row_should_hide(row))
        # Highlight nach Rebuild wieder anwenden
        self._apply_active_highlight()

    def _on_cq_filter_toggled(self):
        """CQ-Filter: nur CQ-Rufe anzeigen oder alle."""
        self._apply_filters()

    def _on_land_filter_clicked(self):
        """Land-Button: Menü anzeigen."""
        self._show_country_menu()
        # Checked-State korrigieren (click toggled es, wir wollen Filter-State)
        self.btn_land_filter.setChecked(bool(self._country_filter))

    def _show_country_menu(self):
        """QMenu mit allen aktuellen Ländern als Checkboxen."""
        # Alle Länder aus Tabelle sammeln
        current = set()
        for row in range(self.table.rowCount()):
            item = self.table.item(row, COL_UTC)
            if item:
                country = item.data(Qt.ItemDataRole.UserRole + 1)
                if country and country != "?":
                    current.add(country)
        # Auch gespeicherte Filter-Länder anzeigen (evtl. gerade nicht empfangen)
        all_countries = sorted(current | self._country_filter)
        if not all_countries:
            return
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu { background: #1a1a2e; color: #CCC; border: 1px solid #444; }
            QMenu::item { padding: 4px 20px 4px 28px; }
            QMenu::item:selected { background: #0066AA; }
            QMenu::item:checked { color: #FF6622; }
            QMenu::indicator { width: 14px; height: 14px; }
        """)
        for country in all_countries:
            action = menu.addAction(country)
            action.setCheckable(True)
            action.setChecked(country in self._country_filter)
            action.triggered.connect(
                lambda checked, c=country: self._toggle_country(c, checked)
            )
        if self._country_filter:
            menu.addSeparator()
            clear = menu.addAction("Alle zeigen (Filter löschen)")
            clear.triggered.connect(self._clear_country_filter)
        menu.exec(self.btn_land_filter.mapToGlobal(
            self.btn_land_filter.rect().bottomLeft()
        ))

    def _toggle_country(self, country: str, checked: bool):
        """Land in Filter aufnehmen (checked=True) oder entfernen."""
        if checked:
            self._country_filter.add(country)
        else:
            self._country_filter.discard(country)
        self.btn_land_filter.setChecked(bool(self._country_filter))
        self._apply_filters()
        self.country_filter_changed.emit(list(self._country_filter))

    def _clear_country_filter(self):
        """Alle Länder-Filter entfernen."""
        self._country_filter.clear()
        self.btn_land_filter.setChecked(False)
        self._apply_filters()
        self.country_filter_changed.emit([])

    def _row_should_hide(self, row: int) -> bool:
        """True wenn Zeile durch CQ-, Länder- oder Ant-Filter ausgeblendet werden soll."""
        item = self.table.item(row, COL_UTC)
        if item is None:
            return False
        msg = item.data(Qt.ItemDataRole.UserRole)
        if msg is None:
            return False  # Separator immer sichtbar
        if self.btn_cq_filter.isChecked() and not msg.is_cq:
            return True
        if self._country_filter:
            country = item.data(Qt.ItemDataRole.UserRole + 1) or "?"
            if country in self._country_filter:
                return True
        if self._ant_filter > 0:
            ant = getattr(msg, 'antenna', '') or ''
            if self._ant_filter == 1 and not ant.startswith('A1'):
                return True
            if self._ant_filter == 2 and not ant.startswith('A2'):
                return True
        # NEW-Filter: schon gearbeitete ausblenden
        if self.btn_new_filter.isChecked() and self._qso_log is not None:
            caller = getattr(msg, 'caller', '')
            if caller and self._qso_log.is_worked(caller):
                return True
        return False

    def _apply_filters(self):
        """Alle aktiven Filter auf die Tabelle anwenden."""
        for row in range(self.table.rowCount()):
            self.table.setRowHidden(row, self._row_should_hide(row))

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
