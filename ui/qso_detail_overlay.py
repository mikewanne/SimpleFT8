"""SimpleFT8 QSO Detail Overlay — zeigt QSO-Details + QRZ Lookup beim Klick im Logbuch."""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
    QPushButton, QLineEdit, QTextEdit, QFrame, QScrollArea,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QPixmap

_FONT = "Menlo"
_BG = "#111118"


class QSODetailOverlay(QWidget):
    """Overlay das ueber die rechte Seite gleitet und QSO-Details zeigt."""

    save_requested = Signal(dict)
    upload_requested = Signal(dict)
    delete_requested = Signal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"background: {_BG};")
        self._qso_data = {}
        self._setup_ui()
        self.hide()

    def _setup_ui(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; }")

        container = QWidget()
        lay = QVBoxLayout(container)
        lay.setContentsMargins(10, 8, 10, 8)
        lay.setSpacing(6)

        # Header + Close Button
        header_row = QHBoxLayout()
        lbl = QLabel("QSO DETAILS")
        lbl.setStyleSheet(f"color: #00AAFF; font-family: {_FONT}; font-size: 13px; font-weight: bold;")
        self.btn_close = QPushButton("X")
        self.btn_close.setFixedSize(24, 24)
        self.btn_close.setStyleSheet(
            f"QPushButton {{ background: rgba(200,50,50,0.3); color: #FF6666; "
            f"border: 1px solid #663333; border-radius: 12px; font-weight: bold; font-size: 12px; }}"
            f"QPushButton:hover {{ background: rgba(200,50,50,0.5); }}"
        )
        self.btn_close.clicked.connect(self.hide)
        header_row.addWidget(lbl)
        header_row.addStretch()
        header_row.addWidget(self.btn_close)
        lay.addLayout(header_row)

        # ── Station Info (von QRZ) ────────────────────────────
        station_frame = QFrame()
        station_frame.setStyleSheet(
            "QFrame { border: 1px solid #3a3a4a; border-radius: 4px; "
            "background: rgba(0,40,80,0.1); }"
        )
        station_lay = QVBoxLayout(station_frame)
        station_lay.setContentsMargins(8, 6, 8, 6)
        station_lay.setSpacing(2)

        self.call_label = QLabel("—")
        self.call_label.setStyleSheet(
            f"color: #00CCFF; font-family: {_FONT}; font-size: 18px; font-weight: bold; border: none;")
        station_lay.addWidget(self.call_label)

        self.name_label = QLabel("")
        self.name_label.setStyleSheet(f"color: #CCCCCC; font-family: {_FONT}; font-size: 12px; border: none;")
        station_lay.addWidget(self.name_label)

        self.qth_label = QLabel("")
        self.qth_label.setStyleSheet(f"color: #88CC88; font-family: {_FONT}; font-size: 11px; border: none;")
        self.qth_label.setWordWrap(True)
        station_lay.addWidget(self.qth_label)

        self.qrz_status = QLabel("")
        self.qrz_status.setStyleSheet(f"color: #666; font-family: {_FONT}; font-size: 9px; border: none;")
        station_lay.addWidget(self.qrz_status)

        lay.addWidget(station_frame)

        # ── QSO Daten (editierbar) ────────────────────────────
        qso_frame = QFrame()
        qso_frame.setStyleSheet(
            "QFrame { border: 1px solid #3a3a3a; border-radius: 4px; "
            "background: rgba(255,255,255,0.02); }"
        )
        grid = QGridLayout(qso_frame)
        grid.setContentsMargins(8, 6, 8, 6)
        grid.setSpacing(4)

        _lbl_ss = f"color: #888; font-family: {_FONT}; font-size: 10px; border: none;"
        _edit_ss = (f"QLineEdit {{ background: #1a1a2a; color: #CCC; border: 1px solid #444; "
                    f"border-radius: 2px; padding: 2px 4px; font-family: {_FONT}; font-size: 11px; }}")

        fields = [
            ("Datum:", "date"), ("Zeit:", "time"), ("Band:", "band"),
            ("Freq:", "freq"), ("Mode:", "mode"), ("RST Sent:", "rst_sent"),
            ("RST Rcvd:", "rst_rcvd"), ("Grid:", "grid"), ("Power:", "power"),
        ]
        self._edits = {}
        for i, (label_text, key) in enumerate(fields):
            lbl = QLabel(label_text)
            lbl.setStyleSheet(_lbl_ss)
            edit = QLineEdit()
            edit.setStyleSheet(_edit_ss)
            edit.setFixedHeight(22)
            row = i // 2
            col = (i % 2) * 2
            grid.addWidget(lbl, row, col)
            grid.addWidget(edit, row, col + 1)
            self._edits[key] = edit

        # Kommentar (ganze Breite)
        row_comment = len(fields) // 2 + 1
        lbl_c = QLabel("Kommentar:")
        lbl_c.setStyleSheet(_lbl_ss)
        grid.addWidget(lbl_c, row_comment, 0)
        self.comment_edit = QLineEdit()
        self.comment_edit.setStyleSheet(_edit_ss)
        self.comment_edit.setFixedHeight(22)
        grid.addWidget(self.comment_edit, row_comment, 1, 1, 3)

        lay.addWidget(qso_frame)

        # ── Buttons ───────────────────────────────────────────
        btn_row = QHBoxLayout()
        btn_row.setSpacing(6)

        btn_save = QPushButton("Speichern")
        btn_save.setStyleSheet(
            f"QPushButton {{ background: rgba(0,120,60,0.3); color: #44CC88; "
            f"border: 1px solid #336; border-radius: 3px; padding: 4px 12px; "
            f"font-family: {_FONT}; font-weight: bold; }}"
            f"QPushButton:hover {{ background: rgba(0,150,80,0.4); }}"
        )
        btn_save.clicked.connect(self._on_save)

        btn_qrz = QPushButton("QRZ Upload")
        btn_qrz.setStyleSheet(
            f"QPushButton {{ background: rgba(0,80,160,0.3); color: #4488CC; "
            f"border: 1px solid #336; border-radius: 3px; padding: 4px 12px; "
            f"font-family: {_FONT}; font-weight: bold; }}"
            f"QPushButton:hover {{ background: rgba(0,100,180,0.4); }}"
        )
        btn_qrz.clicked.connect(self._on_upload)

        btn_delete = QPushButton("Löschen")
        btn_delete.setStyleSheet(
            f"QPushButton {{ background: rgba(160,30,30,0.3); color: #CC4444; "
            f"border: 1px solid #633; border-radius: 3px; padding: 4px 12px; "
            f"font-family: {_FONT}; font-weight: bold; }}"
            f"QPushButton:hover {{ background: rgba(180,40,40,0.5); }}"
        )
        btn_delete.clicked.connect(self._on_delete)

        btn_row.addWidget(btn_save)
        btn_row.addWidget(btn_qrz)
        btn_row.addStretch()
        btn_row.addWidget(btn_delete)
        lay.addLayout(btn_row)
        lay.addStretch()

        scroll.setWidget(container)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

    def load_qso(self, record: dict):
        """QSO-Daten in die Felder laden."""
        self._qso_data = record
        d = record.get("QSO_DATE", "")
        t = record.get("TIME_ON", "")
        date_str = f"{d[6:8]}.{d[4:6]}.{d[:4]}" if len(d) == 8 else d
        time_str = f"{t[:2]}:{t[2:4]}" if len(t) >= 4 else t

        self._edits["date"].setText(date_str)
        self._edits["time"].setText(time_str)
        self._edits["band"].setText(record.get("BAND", ""))
        self._edits["freq"].setText(record.get("FREQ", ""))
        self._edits["mode"].setText(record.get("MODE", ""))
        self._edits["rst_sent"].setText(record.get("RST_SENT", ""))
        self._edits["rst_rcvd"].setText(record.get("RST_RCVD", ""))
        self._edits["grid"].setText(record.get("GRIDSQUARE", ""))
        self._edits["power"].setText(record.get("TX_PWR", ""))
        self.comment_edit.setText(record.get("COMMENT", ""))

        call = record.get("CALL", "—")
        self.call_label.setText(call)
        self.name_label.setText("")
        self.qth_label.setText("")
        self.qrz_status.setText("QRZ Lookup...")
        self.show()

    def set_qrz_info(self, info: dict):
        """QRZ Lookup-Ergebnis anzeigen."""
        if not info:
            self.qrz_status.setText("QRZ: nicht gefunden")
            return
        fname = info.get("fname", "")
        name = info.get("name", "")
        full_name = f"{fname} {name}".strip()
        self.name_label.setText(full_name)

        country = info.get("country", "")
        grid = info.get("grid", "")
        qth = info.get("addr2", "")
        parts = [p for p in [qth, country, grid] if p]
        self.qth_label.setText(" | ".join(parts))
        self.qrz_status.setText(f"DXCC: {info.get('dxcc', '?')} | CQ: {info.get('cqzone', '?')} | ITU: {info.get('ituzone', '?')}")

    def _on_save(self):
        self.save_requested.emit(self._qso_data)

    def _on_upload(self):
        self.upload_requested.emit(self._qso_data)

    def _on_delete(self):
        self.delete_requested.emit(self._qso_data)
