"""SimpleFT8 Direction Map Widget — Azimuthal-Equidistant-Karte mit RX/TX-Toggle.

Non-modaler QDialog, der eine Welt-Karte mit User-Locator als Center anzeigt.
Zwei Modi:
- EMPFANG: wo hoere ich Stationen (Live aus mw_cycle, Antenna-Pref-Farbcode)
- SENDEN:  wo wurde ich gehoert (PSK-Reporter, Internet)

Architektur:
- DirectionMapDialog: QDialog Container mit Toggle-Buttons, Filter, Status-Label
- MapCanvas:           QWidget Subclass, paintEvent mit QPixmap-Cache fuer
                       statisches Background (Coastlines, Ringe, Compass)

Pure-Python-Logik (Coastline-Loading, Layout-Konstanten) ist als Klassen-Methoden
oder Modul-Funktionen organisiert, damit sie ohne QApplication testbar sind.

Die Live-Daten-Hooks (update_rx_stations, update_tx_spots) werden in
Schritten 7/8 angeschlossen. Diese Datei legt nur die UI-Struktur an.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, QPointF, QSize
from PySide6.QtGui import (
    QBrush, QColor, QFont, QPainter, QPen, QPixmap, QPolygonF,
)
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QFrame, QHBoxLayout, QLabel,
    QPushButton, QSizePolicy, QSpinBox, QVBoxLayout, QWidget,
)

from core.direction_pattern import (
    SECTOR_COUNT, SECTOR_WIDTH_DEG, SectorBucket, StationPoint, aggregate_sectors,
)
from core.geo import azimuthal_equidistant_project, safe_locator_to_latlon


# ── Layout-Konstanten ─────────────────────────────────────

COLOR_BG = "#0A0A14"
COLOR_COAST = "#666666"
COLOR_RINGS = "#333333"
COLOR_COMPASS = "#888888"
COLOR_SECTOR_LINES = "#222222"
COLOR_USER = "#FFCC00"
COLOR_HINT = "#888888"

DISTANCE_RINGS_KM = (3000, 6000, 9000, 12000, 15000)
COMPASS_LABELS = ("N", "NE", "E", "SE", "S", "SW", "W", "NW")
RESIZE_DEBOUNCE_MS = 200
MAX_DISTANCE_KM = 18000.0
MAP_RADIUS_FRACTION = 0.45  # Anteil der min(width,height) als Karten-Radius

DEFAULT_DIALOG_SIZE = QSize(720, 720)
DIALOG_MIN_SIZE = QSize(500, 500)


# ── Asset-Loader ──────────────────────────────────────────

def load_coastlines() -> list[list[tuple[float, float]]]:
    """Coastlines aus assets/ne_110m_land_antimeridian_split.geojson laden.

    Returnt Liste von LineStrings (jeder = Liste von (lon, lat)). Bei jedem
    Fehler (Datei fehlt, Korruption) leere Liste — Karte rendert dann ohne
    Coastlines, aber stuerzt nicht ab.
    """
    try:
        asset_path = (
            Path(__file__).parent.parent / "assets" /
            "ne_110m_land_antimeridian_split.geojson"
        )
        with open(asset_path) as f:
            data = json.load(f)
        return [[(pt[0], pt[1]) for pt in line] for line in data.get("lines", [])]
    except (OSError, json.JSONDecodeError, KeyError, TypeError):
        return []


# ── MapCanvas — Karten-Bereich ────────────────────────────

class MapCanvas(QWidget):
    """Karten-Canvas mit paintEvent.

    Statisches Background (Coastlines + Ringe + Compass + Sektorlinien) wird
    in QPixmap gecached und nur bei Locator-Wechsel oder Resize neu gerendert.
    Live-Layer (Sektor-Wedges, Stations-Punkte, User-Marker) jeden paintEvent.
    """

    def __init__(self, my_locator: str = "", parent: QWidget | None = None):
        super().__init__(parent)
        self._my_locator = my_locator
        self._my_pos = safe_locator_to_latlon(my_locator)
        self._coastlines = load_coastlines()
        self._bg_pixmap: QPixmap | None = None
        self._stations: list[StationPoint] = []
        self._sectors: list[SectorBucket] = []
        self._mode = "rx"  # "rx" oder "tx"

        self.setMinimumSize(300, 300)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        # Resize-Debounce: bei mehrfachem Resize nur einmal Background rebuilden
        self._resize_timer = QTimer(self)
        self._resize_timer.setSingleShot(True)
        self._resize_timer.timeout.connect(self._invalidate_background)

    # ── Public API ────────────────────────────────────────

    def set_locator(self, locator: str) -> None:
        if locator == self._my_locator:
            return
        self._my_locator = locator
        self._my_pos = safe_locator_to_latlon(locator)
        self._sectors = []
        self._invalidate_background()

    def set_mode(self, mode: str) -> None:
        if mode not in ("rx", "tx"):
            return
        self._mode = mode
        self.update()

    def update_stations(self, stations: list[StationPoint]) -> None:
        """Live-Update vom RX-Hook oder TX-Polling.

        WICHTIG: muss aus dem GUI-Thread aufgerufen werden, sonst racet die
        Mutation von _stations/_sectors mit dem laufenden paintEvent. Wenn
        der Aufrufer in einem Worker-Thread laeuft (Decoder, PSK-Polling),
        muss er via Qt-Signal/Slot mit Qt.QueuedConnection in den GUI-Thread
        marshallen — siehe Schritt 7 (mw_cycle-Hook ueber pyqtSignal).
        """
        self._stations = list(stations)
        if self._my_pos:
            self._sectors = aggregate_sectors(
                self._stations, self._my_pos[0], self._my_pos[1]
            )
        else:
            self._sectors = []
        self.update()

    def has_locator(self) -> bool:
        return self._my_pos is not None

    # ── Geometrie ─────────────────────────────────────────

    def _center_px(self) -> tuple[int, int]:
        return self.width() // 2, self.height() // 2

    def _radius_px(self) -> float:
        return min(self.width(), self.height()) * MAP_RADIUS_FRACTION

    def _project(self, lat: float, lon: float) -> tuple[float, float] | None:
        """Lat/Lon → Pixel-Offset (dx, dy) vom Karten-Center."""
        if not self._my_pos:
            return None
        return azimuthal_equidistant_project(
            self._my_pos[0], self._my_pos[1], lat, lon,
            radius_px=self._radius_px(), max_distance_km=MAX_DISTANCE_KM,
        )

    # ── Resize ────────────────────────────────────────────

    def resizeEvent(self, event):  # noqa: N802 (Qt-Naming)
        self._bg_pixmap = None
        self._resize_timer.start(RESIZE_DEBOUNCE_MS)
        super().resizeEvent(event)

    def _invalidate_background(self) -> None:
        self._bg_pixmap = None
        self.update()

    # ── paintEvent ────────────────────────────────────────

    def paintEvent(self, event):  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        if not self._my_pos:
            self._paint_no_locator(painter)
            return

        if self._bg_pixmap is None or self._bg_pixmap.size() != self.size():
            self._bg_pixmap = self._build_background_pixmap()
        painter.drawPixmap(0, 0, self._bg_pixmap)
        # Live-Layer kommt in Schritt 7 (RX-Wedges + Stations) und Schritt 8 (TX)
        self._paint_user_marker(painter)

    def _paint_no_locator(self, painter: QPainter) -> None:
        painter.fillRect(self.rect(), QColor(COLOR_BG))
        painter.setPen(QColor(COLOR_HINT))
        painter.setFont(QFont("Menlo", 13))
        painter.drawText(
            self.rect(), Qt.AlignCenter,
            "Bitte gueltigen Locator\nin den Einstellungen setzen."
        )

    # ── Background-Pixmap ─────────────────────────────────

    def _build_background_pixmap(self) -> QPixmap:
        pix = QPixmap(self.size())
        pix.fill(QColor(COLOR_BG))
        painter = QPainter(pix)
        painter.setRenderHint(QPainter.Antialiasing)
        try:
            self._paint_coastlines(painter)
            self._paint_distance_rings(painter)
            self._paint_compass(painter)
            self._paint_sector_lines(painter)
        finally:
            painter.end()
        return pix

    def _paint_coastlines(self, painter: QPainter) -> None:
        if not self._coastlines:
            return
        cx, cy = self._center_px()
        pen = QPen(QColor(COLOR_COAST))
        pen.setWidthF(0.7)
        painter.setPen(pen)
        for line in self._coastlines:
            poly = QPolygonF()
            for lon, lat in line:
                projected = self._project(lat, lon)
                if projected is None:
                    # Projektion abgeschnitten (Antipode-Bereich) → Linie
                    # bis hier zeichnen, dann neu starten
                    if poly.size() >= 2:
                        painter.drawPolyline(poly)
                    poly = QPolygonF()
                    continue
                dx, dy = projected
                poly.append(QPointF(cx + dx, cy + dy))
            if poly.size() >= 2:
                painter.drawPolyline(poly)

    def _paint_distance_rings(self, painter: QPainter) -> None:
        cx, cy = self._center_px()
        radius = self._radius_px()
        pen = QPen(QColor(COLOR_RINGS))
        pen.setStyle(Qt.DashLine)
        pen.setWidthF(0.8)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        for km in DISTANCE_RINGS_KM:
            r = radius * (km / MAX_DISTANCE_KM)
            painter.drawEllipse(QPointF(cx, cy), r, r)

    def _paint_sector_lines(self, painter: QPainter) -> None:
        cx, cy = self._center_px()
        radius = self._radius_px()
        pen = QPen(QColor(COLOR_SECTOR_LINES))
        pen.setWidthF(0.5)
        painter.setPen(pen)
        for i in range(SECTOR_COUNT):
            angle_deg = i * SECTOR_WIDTH_DEG - SECTOR_WIDTH_DEG / 2.0
            rad = math.radians(angle_deg)
            x = cx + radius * math.sin(rad)
            y = cy - radius * math.cos(rad)
            painter.drawLine(QPointF(cx, cy), QPointF(x, y))

    def _paint_compass(self, painter: QPainter) -> None:
        cx, cy = self._center_px()
        radius = self._radius_px()
        painter.setPen(QColor(COLOR_COMPASS))
        painter.setFont(QFont("Menlo", 10, QFont.Bold))
        # 8 Compass-Punkte, jeweils 45°
        for i, label in enumerate(COMPASS_LABELS):
            angle_deg = i * 45.0
            rad = math.radians(angle_deg)
            x = cx + (radius + 14) * math.sin(rad)
            y = cy - (radius + 14) * math.cos(rad)
            # Text mittig um (x,y) ausrichten
            metrics = painter.fontMetrics()
            tw = metrics.horizontalAdvance(label)
            th = metrics.height()
            painter.drawText(
                QPointF(x - tw / 2.0, y + th / 4.0), label
            )

    # ── User-Marker (Diamant im Zentrum) ──────────────────

    def _paint_user_marker(self, painter: QPainter) -> None:
        cx, cy = self._center_px()
        painter.setPen(QPen(QColor(COLOR_USER), 1.5))
        painter.setBrush(QBrush(QColor(COLOR_USER)))
        size = 6
        diamond = QPolygonF([
            QPointF(cx, cy - size),
            QPointF(cx + size, cy),
            QPointF(cx, cy + size),
            QPointF(cx - size, cy),
        ])
        painter.drawPolygon(diamond)
        # Locator-Label rechts vom Marker
        painter.setFont(QFont("Menlo", 9))
        painter.setBrush(Qt.NoBrush)
        painter.setPen(QColor("#FFCC00"))
        painter.drawText(QPointF(cx + size + 4, cy + 3), self._my_locator)


# ── DirectionMapDialog — Container ────────────────────────

class DirectionMapDialog(QDialog):
    """Container-Dialog mit Toggle, Filter, Status, eingebettetem MapCanvas."""

    def __init__(
        self,
        my_locator: str = "",
        default_mode: str = "rx",
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.setWindowTitle("Richtungs-Karte")
        self.setModal(False)  # Decoder-Signale muessen durchkommen
        self.setMinimumSize(DIALOG_MIN_SIZE)
        self.resize(DEFAULT_DIALOG_SIZE)

        self._mode = default_mode if default_mode in ("rx", "tx") else "rx"
        self._setup_ui(my_locator)
        self._sync_toggle_state()

    def _setup_ui(self, my_locator: str) -> None:
        self.setStyleSheet("""
            QDialog { background-color: #16192b; }
            QLabel { background-color: transparent; color: #CCC; }
            QPushButton {
                background-color: #2a2e44; color: #DDD; border: 1px solid #444;
                padding: 6px 16px; border-radius: 3px; font-weight: bold;
            }
            QPushButton:checked {
                background-color: #4488AA; color: white; border: 1px solid #66AACC;
            }
            QComboBox, QSpinBox {
                background-color: #1f2235; color: #DDD; border: 1px solid #444;
                padding: 3px 6px;
            }
            QCheckBox { color: #CCC; }
        """)

        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(12, 10, 12, 10)

        # ── Toggle-Bar ────────────────────────────────────
        toggle_row = QHBoxLayout()
        self.btn_rx = QPushButton("EMPFANG")
        self.btn_rx.setCheckable(True)
        self.btn_rx.setToolTip("Stationen die ICH dekodiert habe (Live, kein Internet).")
        self.btn_rx.clicked.connect(lambda: self._on_mode_toggled("rx"))
        self.btn_tx = QPushButton("SENDEN")
        self.btn_tx.setCheckable(True)
        self.btn_tx.setToolTip("Stationen die MICH dekodiert haben (PSK-Reporter, Internet).")
        self.btn_tx.clicked.connect(lambda: self._on_mode_toggled("tx"))
        toggle_row.addWidget(self.btn_rx)
        toggle_row.addWidget(self.btn_tx)
        toggle_row.addStretch()
        layout.addLayout(toggle_row)

        # ── Karten-Canvas ─────────────────────────────────
        self.canvas = MapCanvas(my_locator=my_locator)
        layout.addWidget(self.canvas, stretch=1)

        # ── Filter-Bar ────────────────────────────────────
        filter_row = QHBoxLayout()
        filter_row.addWidget(QLabel("Zeit:"))
        self.window_combo = QComboBox()
        for label, val in [("10 Min", 10), ("30 Min", 30), ("60 Min", 60), ("3 Std", 180)]:
            self.window_combo.addItem(label, val)
        self.window_combo.setCurrentIndex(2)  # 60 Min default
        filter_row.addWidget(self.window_combo)

        filter_row.addSpacing(16)
        filter_row.addWidget(QLabel("Band:"))
        self.band_combo = QComboBox()
        self.band_combo.addItem("Aktuelles", "current")
        self.band_combo.addItem("Alle", "all")
        filter_row.addWidget(self.band_combo)

        filter_row.addSpacing(16)
        self.cb_show_stations = QCheckBox("Stationen")
        self.cb_show_stations.setChecked(True)
        self.cb_show_stations.toggled.connect(lambda _: self.canvas.update())
        self.cb_show_sectors = QCheckBox("Sektoren")
        self.cb_show_sectors.setChecked(True)
        self.cb_show_sectors.toggled.connect(lambda _: self.canvas.update())
        filter_row.addWidget(self.cb_show_stations)
        filter_row.addWidget(self.cb_show_sectors)
        filter_row.addStretch()
        layout.addLayout(filter_row)

        # ── Status-Label ──────────────────────────────────
        self.status_label = QLabel("Bereit.")
        self.status_label.setStyleSheet("color: #889; padding: 2px 4px;")
        layout.addWidget(self.status_label)

    # ── Toggle-Logik ──────────────────────────────────────

    def _on_mode_toggled(self, mode: str) -> None:
        # Doppel-Klick auf aktiven Mode: einfach State-Sync und Status refreshen.
        # checkable QPushButton wuerde sonst aktiven Button uncheck'en.
        self._mode = mode
        self._sync_toggle_state()
        self.canvas.set_mode(mode)
        if mode == "rx":
            self.set_status("EMPFANG: warte auf Live-Daten …")
        else:
            self.set_status("SENDEN: PSK-Reporter wird in Schritt 8 angeschlossen.")

    def _sync_toggle_state(self) -> None:
        self.btn_rx.setChecked(self._mode == "rx")
        self.btn_tx.setChecked(self._mode == "tx")

    # ── Public API fuer Live-Daten (Schritt 7+8) ─────────

    def update_rx_stations(self, stations: list[StationPoint]) -> None:
        """Wird vom mw_cycle-Hook aus dem Decoder-Thread gerufen.
        Aufrufer marshallt ggf. via Qt-Signal in den GUI-Thread."""
        if self._mode == "rx":
            self.canvas.update_stations(stations)
            self.set_status(f"EMPFANG: {len(stations)} Stationen.")

    def update_tx_spots(self, stations: list[StationPoint]) -> None:
        """Wird vom PSKReporterClient-Callback aufgerufen."""
        if self._mode == "tx":
            self.canvas.update_stations(stations)
            self.set_status(f"SENDEN: {len(stations)} Reception-Reports.")

    def set_status(self, text: str) -> None:
        self.status_label.setText(text)

    def set_locator(self, locator: str) -> None:
        self.canvas.set_locator(locator)

    @property
    def mode(self) -> str:
        return self._mode

    # ── Window-Status ─────────────────────────────────────

    @property
    def time_window_min(self) -> int:
        return int(self.window_combo.currentData() or 60)

    @property
    def band_filter(self) -> str:
        return str(self.band_combo.currentData() or "current")
