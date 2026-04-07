"""SimpleFT8 Logbook Widget — QSO-Tabelle mit Suche und DXCC-Zaehler."""

from pathlib import Path
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QLineEdit, QHeaderView,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont

from log.adif import parse_all_adif_files

_FONT = "Menlo"
_BG = "#0d0d1a"

# Spalten-Definition: (ADIF-Key, Header-Text, Breite)
_COLUMNS = [
    ("_DATETIME",  "Datum",        68),
    ("CALL",       "Call",         75),
    ("BAND",       "Band",        40),
    ("MODE",       "Mode",        38),
    ("_COUNTRY",   "Land",        90),
    ("_KM",        "km",          50),
]

# Einfache Prefix → Land Zuordnung (Subset)
_PREFIX_COUNTRY = {
    "DA": "Germany", "DB": "Germany", "DC": "Germany", "DD": "Germany",
    "DE": "Germany", "DF": "Germany", "DG": "Germany", "DH": "Germany",
    "DK": "Germany", "DL": "Germany", "DJ": "Germany", "DM": "Germany",
    "F": "France", "G": "England", "I": "Italy", "EA": "Spain",
    "PA": "Netherlands", "ON": "Belgium", "OE": "Austria", "HB": "Switzerland",
    "OK": "Czech Rep.", "SP": "Poland", "HA": "Hungary", "YO": "Romania",
    "LZ": "Bulgaria", "UR": "Ukraine", "UA": "Russia", "OH": "Finland",
    "SM": "Sweden", "LA": "Norway", "OZ": "Denmark", "K": "USA", "W": "USA",
    "N": "USA", "VE": "Canada", "JA": "Japan", "VK": "Australia",
    "ZL": "New Zealand", "PY": "Brazil", "LU": "Argentina",
}


def _guess_country(call: str) -> str:
    """Land aus Callsign-Prefix raten."""
    call = call.upper().strip()
    # Versuche 2-Zeichen, dann 1-Zeichen Prefix
    for length in (2, 1):
        prefix = call[:length]
        if prefix in _PREFIX_COUNTRY:
            return _PREFIX_COUNTRY[prefix]
    return ""


def _format_datetime(record: dict) -> str:
    """QSO_DATE + TIME_ON in kompaktes deutsches Format: DD.MM.YY HH:MM"""
    d = record.get("QSO_DATE", "")
    t = record.get("TIME_ON", "")
    if len(d) == 8:
        return f"{d[6:8]}.{d[4:6]}.{d[2:4]}"
    return d


def _estimate_km(grid: str) -> str:
    """Entfernung von JO31 (DA1MHH) zu Grid in km schaetzen."""
    if not grid or len(grid) < 4:
        return ""
    try:
        import math
        def grid_to_latlon(g):
            g = g.upper()
            lon = (ord(g[0]) - ord('A')) * 20 - 180 + (int(g[2]) * 2) + 1
            lat = (ord(g[1]) - ord('A')) * 10 - 90 + int(g[3]) + 0.5
            return lat, lon
        lat1, lon1 = grid_to_latlon("JO31")  # DA1MHH
        lat2, lon2 = grid_to_latlon(grid)
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
        return str(int(6371 * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))))
    except Exception:
        return ""


class LogbookWidget(QWidget):
    """Logbuch-Tabelle mit Suche und DXCC-Zaehler."""

    upload_requested = Signal()  # Fuer QRZ.com Upload
    qso_clicked = Signal(dict)   # QSO-Eintrag angeklickt → Detail-Overlay

    def __init__(self, adif_directory: Path = None):
        super().__init__()
        self._adif_dir = adif_directory or Path.cwd()
        self._all_records = []
        self._filtered_records = []
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # Toolbar: Suche + DXCC + Upload
        toolbar = QHBoxLayout()
        toolbar.setSpacing(6)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Suche: Call, Band, Land...")
        self.search_input.setStyleSheet(
            f"QLineEdit {{ background: #1a1a2a; color: #CCC; border: 1px solid #444; "
            f"border-radius: 3px; padding: 3px 6px; font-family: {_FONT}; font-size: 11px; }}"
        )
        self.search_input.textChanged.connect(self._on_filter_changed)
        toolbar.addWidget(self.search_input, 1)

        self.dxcc_label = QLabel("DXCC: 0")
        self.dxcc_label.setStyleSheet(
            f"color: #00CCAA; font-family: {_FONT}; font-size: 11px; font-weight: bold; "
            f"border: 1px solid #336; border-radius: 3px; padding: 2px 6px;"
        )
        toolbar.addWidget(self.dxcc_label)

        self.qso_count_label = QLabel("0 QSOs")
        self.qso_count_label.setStyleSheet(
            f"color: #AAAACC; font-family: {_FONT}; font-size: 11px; "
            f"border: 1px solid #336; border-radius: 3px; padding: 2px 6px;"
        )
        toolbar.addWidget(self.qso_count_label)

        btn_upload = QPushButton("QRZ")
        btn_upload.setFixedWidth(40)
        btn_upload.setStyleSheet(
            f"QPushButton {{ background: rgba(0,100,180,0.3); color: #4488CC; "
            f"border: 1px solid #336; border-radius: 3px; font-family: {_FONT}; "
            f"font-size: 10px; font-weight: bold; }}"
            f"QPushButton:hover {{ background: rgba(0,120,200,0.4); color: #66AAEE; }}"
        )
        btn_upload.clicked.connect(self.upload_requested.emit)
        toolbar.addWidget(btn_upload)

        layout.addLayout(toolbar)

        # Tabelle
        self.table = QTableWidget()
        self.table.setColumnCount(len(_COLUMNS))
        self.table.setHorizontalHeaderLabels([c[1] for c in _COLUMNS])
        self.table.setFont(QFont(_FONT, 11))
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(22)
        self.table.setSortingEnabled(True)

        # Spaltenbreiten
        header = self.table.horizontalHeader()
        for i, (_, _, width) in enumerate(_COLUMNS):
            self.table.setColumnWidth(i, width)
        header.setStretchLastSection(True)

        self.table.setStyleSheet(f"""
            QTableWidget {{
                background-color: {_BG};
                color: #CCCCCC;
                border: 1px solid #333;
                border-radius: 4px;
                gridline-color: #222;
                font-family: {_FONT};
                font-size: 11px;
            }}
            QTableWidget::item {{
                padding: 2px 4px;
            }}
            QTableWidget::item:selected {{
                background-color: #003366;
                color: white;
            }}
            QHeaderView::section {{
                background-color: #1a1a2e;
                color: #888;
                border: 1px solid #333;
                padding: 3px;
                font-size: 10px;
                font-weight: bold;
            }}
            QTableWidget::item:alternate {{
                background-color: rgba(255,255,255,0.02);
            }}
        """)

        self.table.cellClicked.connect(self._on_row_clicked)
        layout.addWidget(self.table)

    def load_adif(self, directory: Path = None):
        """Alle ADIF-Dateien laden und Tabelle fuellen."""
        if directory:
            self._adif_dir = directory
        self._all_records = parse_all_adif_files(self._adif_dir)
        self._populate_table(self._all_records)
        self._update_counters()

    def refresh(self):
        """ADIF neu laden (z.B. nach neuem QSO)."""
        self.load_adif()

    def _populate_table(self, records):
        """Tabelle mit Records fuellen."""
        self._filtered_records = records
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(records))

        for row, rec in enumerate(records):
            for col, (key, _, _) in enumerate(_COLUMNS):
                if key == "_DATETIME":
                    value = _format_datetime(rec)
                elif key == "_COUNTRY":
                    value = _guess_country(rec.get("CALL", ""))
                elif key == "_KM":
                    value = _estimate_km(rec.get("GRIDSQUARE", ""))
                else:
                    value = rec.get(key, "")

                item = QTableWidgetItem(value)
                item.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)

                # Record als UserRole im ersten Item speichern (fuer Klick nach Sortierung)
                if col == 0:
                    item.setData(Qt.ItemDataRole.UserRole, rec)

                # Farbcodierung
                if key == "CALL":
                    item.setForeground(QColor("#00CCFF"))
                elif key == "BAND":
                    item.setForeground(QColor("#FFAA00"))
                elif key == "_COUNTRY":
                    item.setForeground(QColor("#88CC88"))
                elif key == "_KM":
                    item.setForeground(QColor("#AAAACC"))
                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

                self.table.setItem(row, col, item)

        self.table.setSortingEnabled(True)

    def _update_counters(self):
        """DXCC und QSO Zaehler aktualisieren."""
        countries = set()
        calls = set()
        for rec in self._all_records:
            call = rec.get("CALL", "")
            country = _guess_country(call)
            if country:
                countries.add(country)
            if call:
                calls.add(call)
        self.dxcc_label.setText(f"DXCC: {len(countries)}")
        self.qso_count_label.setText(f"{len(self._all_records)} QSOs")

    def _on_filter_changed(self, text: str):
        """Tabelle nach Suchbegriff filtern."""
        if not text.strip():
            self._populate_table(self._all_records)
            return
        text = text.upper()
        filtered = [
            r for r in self._all_records
            if (text in r.get("CALL", "").upper()
                or text in r.get("BAND", "").upper()
                or text in _guess_country(r.get("CALL", "")).upper()
                or text in r.get("GRIDSQUARE", "").upper())
        ]
        self._populate_table(filtered)

    def _on_row_clicked(self, row: int, col: int):
        """Zeile angeklickt → QSO-Daten aus UserRole lesen (sortier-sicher)."""
        item = self.table.item(row, 0)
        if item:
            rec = item.data(Qt.ItemDataRole.UserRole)
            if rec:
                self.qso_clicked.emit(rec)
