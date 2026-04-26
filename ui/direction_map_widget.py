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

from PySide6.QtCore import Qt, QTimer, QPointF, QSize, Signal, Slot
from PySide6.QtGui import (
    QBrush, QColor, QFont, QPainter, QPen, QPixmap, QPolygonF,
)
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QFrame, QHBoxLayout, QLabel,
    QPushButton, QSizePolicy, QSpinBox, QVBoxLayout, QWidget,
)

from core.direction_pattern import (
    SECTOR_COUNT, SECTOR_WIDTH_DEG, SectorBucket, StationPoint,
    aggregate_sectors, is_mobile,
)
from core.geo import (
    azimuthal_equidistant_project, distance_km, safe_locator_to_latlon,
)


# ── Layout-Konstanten ─────────────────────────────────────

COLOR_BG = "#0A0A14"
COLOR_BG_CENTER = "#0A1030"      # Aurora-Mitte: leichtes Blau
COLOR_COAST_HALO = "#00FFAA"     # Cyan-Halo aussen
COLOR_COAST_CORE = "#88FFCC"     # Cyan hell innen
COLOR_RINGS = "#1F2A3A"          # leicht blaeulich statt nur grau
COLOR_COMPASS = "#88AACC"        # blau-cyan statt grau
COLOR_SECTOR_LINES = "#1A2030"
COLOR_USER = "#FFE600"           # Neon-Gelb
COLOR_USER_GLOW = "#FFFFAA"      # Halo um den Diamanten
COLOR_HINT = "#7788AA"

RX_COLOR_ANT1 = QColor("#4488FF")
RX_COLOR_ANT2 = QColor("#00CCAA")
RX_COLOR_RESCUE = QColor("#44FF44")
RX_COLOR_DEFAULT = QColor("#888888")
TX_COLOR_LOW = QColor("#884400")    # ~-25 dB
TX_COLOR_HIGH = QColor("#FFEE00")   # ~+5 dB
SECTOR_ALPHA = 100  # 0..255 (~0.4)
STATION_MIN_PX = 3
STATION_MAX_PX = 8
STATION_SNR_MIN = -25.0
STATION_SNR_MAX = 5.0

DISTANCE_RINGS_KM = (3000, 6000, 9000, 12000, 15000)
COMPASS_LABELS = ("N", "NE", "E", "SE", "S", "SW", "W", "NW")
RESIZE_DEBOUNCE_MS = 200
MAX_DISTANCE_KM = 18000.0
MAP_RADIUS_FRACTION = 0.45  # Anteil der min(width,height) als Karten-Radius
ZOOM_MIN = 0.3
ZOOM_MAX = 6.0
ZOOM_FACTOR = 1.15  # pro Mausrad-Notch
ROTATE_DEBOUNCE_MS = 30  # Background-Pixmap-Throttle waehrend Drag

DEFAULT_DIALOG_SIZE = QSize(720, 720)
DIALOG_MIN_SIZE = QSize(500, 500)


# ── Locator-Cache ─────────────────────────────────────────

class LocatorCache:
    """Merkt sich pro Callsign den zuletzt gesehenen Locator.

    FT8-Nachrichten enthalten den Locator nur in CQ-Nachrichten ("CQ DA1MHH JO31").
    Direkte QSO-Nachrichten haben Report/RR73/73 statt Locator. Dieser Cache
    sammelt Locators ueber die Session, damit Stationen die wir aktuell hoeren
    (aber nicht in CQ) trotzdem auf der Karte landen wenn sie frueher CQ riefen.

    Keine Persistenz, keine Limits — typischerweise weniger als 1000 Calls pro
    Session, selbst auf 40m am Abend.
    """

    def __init__(self):
        self._cache: dict[str, str] = {}

    def update(self, call: str, locator: str) -> None:
        """Locator merken. Leere oder ungueltige Werte werden silent geskippt."""
        if not call or not locator:
            return
        # Nur 4 oder 6-stellige Locators akzeptieren
        if not (len(locator) >= 4 and locator[0].isalpha() and locator[1].isalpha()
                and locator[2].isdigit() and locator[3].isdigit()):
            return
        self._cache[call.upper()] = locator

    def get(self, call: str) -> str | None:
        if not call:
            return None
        return self._cache.get(call.upper())

    def __len__(self) -> int:
        return len(self._cache)

    def clear(self) -> None:
        self._cache.clear()


def snapshot_to_station_points(
    snapshot: dict,
    locator_cache: LocatorCache,
    band: str = "",
) -> list[StationPoint]:
    """Snapshot-Dict aus mw_cycle in StationPoint-Liste umwandeln.

    Snapshot-Format (aus mw_cycle._build_map_snapshot):
        {call: {"snr": float, "freq_hz": int, "antenna": str,
                "snr_a1": float|None, "snr_a2": float|None,
                "ts": float, "locator": str|None}}

    Stationen ohne Locator (nicht im Cache, kein Locator im Snapshot) werden
    silent geskippt — die Karte zeigt nur Stationen mit bekannter Position.
    Mobile-Calls (/P, /MM, /AM, /QRP, /M) werden ausgefiltert.

    Antenna-Klassifikation:
        - snr_a1 ≤ -24 UND snr_a2 > -24 → "rescue" (ANT2 rettet schwachen ANT1)
        - sonst antenna-Feld direkt aus Snapshot ("A1"/"A2"/leer)
    """
    points: list[StationPoint] = []
    for call, data in snapshot.items():
        if is_mobile(call):
            continue

        # Locator-Lookup: erst Snapshot, dann Cache
        loc = data.get("locator") or locator_cache.get(call)
        if loc:
            locator_cache.update(call, loc)  # Snapshot-Locator merken

        if not loc:
            continue

        latlon = safe_locator_to_latlon(loc)
        if latlon is None:
            continue
        lat, lon = latlon

        # Rescue-Klassifikation
        snr_a1 = data.get("snr_a1")
        snr_a2 = data.get("snr_a2")
        antenna = data.get("antenna", "")
        if (snr_a1 is not None and snr_a2 is not None
                and snr_a1 <= -24.0 and snr_a2 > -24.0):
            antenna = "rescue"

        points.append(StationPoint(
            call=call,
            locator=loc,
            lat=lat,
            lon=lon,
            snr=float(data.get("snr", -30.0)),
            antenna=antenna,
            timestamp=float(data.get("ts", 0.0)),
            band=band,
        ))
    return points


# ── Asset-Loader ──────────────────────────────────────────

def _interpolate_color(
    c_low: QColor, c_high: QColor,
    value: float, v_min: float, v_max: float, alpha: int = 255,
) -> QColor:
    """Linear zwischen c_low (bei v_min) und c_high (bei v_max) interpolieren."""
    if v_max == v_min:
        return QColor(c_high)
    frac = (value - v_min) / (v_max - v_min)
    frac = max(0.0, min(1.0, frac))
    r = c_low.red() + frac * (c_high.red() - c_low.red())
    g = c_low.green() + frac * (c_high.green() - c_low.green())
    b = c_low.blue() + frac * (c_high.blue() - c_low.blue())
    return QColor(int(r), int(g), int(b), alpha)


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
        self._show_sectors = True
        self._show_stations = True

        # Zoom + Rotation State
        self._zoom = 1.0  # 1.0 = MAX_DISTANCE_KM (ganze Welt), >1 = Zoom rein
        self._rotation_deg = 0.0  # 0 = Norden oben, im Uhrzeigersinn
        self._drag_start_pos: QPointF | None = None
        self._drag_start_rotation: float = 0.0

        self.setMinimumSize(300, 300)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setMouseTracking(False)
        self.setCursor(Qt.OpenHandCursor)

        # Resize-Debounce: bei mehrfachem Resize nur einmal Background rebuilden
        self._resize_timer = QTimer(self)
        self._resize_timer.setSingleShot(True)
        self._resize_timer.timeout.connect(self._invalidate_background)
        # Rotation-Debounce: waehrend Drag nicht bei jedem mouseMoveEvent
        # das Background-Pixmap rebuilden (zu teuer mit 5143 Coastline-Punkten)
        self._rotation_timer = QTimer(self)
        self._rotation_timer.setSingleShot(True)
        self._rotation_timer.timeout.connect(self._invalidate_background)

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

    def _effective_max_km(self) -> float:
        """Skaliert MAX_DISTANCE_KM mit dem Zoom-Faktor.
        zoom=1 → 18000 km Rand, zoom=2 → 9000 km Rand (näher heran)."""
        return MAX_DISTANCE_KM / self._zoom

    def _project(self, lat: float, lon: float) -> tuple[float, float] | None:
        """Lat/Lon → Pixel-Offset (dx, dy) vom Karten-Center.
        Beruecksichtigt Karten-Rotation (alle Punkte werden um den Center
        gegen den Uhrzeigersinn um rotation_deg gedreht — entspricht
        einem Bearing-Offset)."""
        if not self._my_pos:
            return None
        p = azimuthal_equidistant_project(
            self._my_pos[0], self._my_pos[1], lat, lon,
            radius_px=self._radius_px(),
            max_distance_km=self._effective_max_km(),
        )
        if p is None:
            return None
        if self._rotation_deg == 0.0:
            return p
        # 2D-Rotation um Center (Pixel-Koord-System: y nach unten,
        # daher Vorzeichen für mathematischen CCW-Sinn drehen)
        rad = math.radians(self._rotation_deg)
        cos_r, sin_r = math.cos(rad), math.sin(rad)
        x, y = p
        return (x * cos_r - y * sin_r, x * sin_r + y * cos_r)

    # ── Resize ────────────────────────────────────────────

    def resizeEvent(self, event):  # noqa: N802 (Qt-Naming)
        self._bg_pixmap = None
        self._resize_timer.start(RESIZE_DEBOUNCE_MS)
        super().resizeEvent(event)

    def _invalidate_background(self) -> None:
        self._bg_pixmap = None
        self.update()

    # ── Zoom (Mausrad) ────────────────────────────────────

    def wheelEvent(self, event):  # noqa: N802
        delta = event.angleDelta().y()
        if delta == 0:
            return
        factor = ZOOM_FACTOR if delta > 0 else 1.0 / ZOOM_FACTOR
        new_zoom = self._zoom * factor
        new_zoom = max(ZOOM_MIN, min(ZOOM_MAX, new_zoom))
        if abs(new_zoom - self._zoom) < 1e-6:
            return
        self._zoom = new_zoom
        self._invalidate_background()
        event.accept()

    # ── Drag-to-rotate (linke Maustaste halten + bewegen) ─

    def mousePressEvent(self, event):  # noqa: N802
        if event.button() == Qt.LeftButton and self._my_pos:
            self._drag_start_pos = event.position()
            self._drag_start_rotation = self._rotation_deg
            self.setCursor(Qt.ClosedHandCursor)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):  # noqa: N802
        if self._drag_start_pos is None:
            return super().mouseMoveEvent(event)
        cx, cy = self._center_px()
        dx0 = self._drag_start_pos.x() - cx
        dy0 = self._drag_start_pos.y() - cy
        dx1 = event.position().x() - cx
        dy1 = event.position().y() - cy
        # Winkel zwischen Maus-Vektoren relativ zum Center.
        # atan2(x, -y): 0=oben(N), 90=rechts(E), 180=unten(S), -90=links(W)
        a0 = math.degrees(math.atan2(dx0, -dy0))
        a1 = math.degrees(math.atan2(dx1, -dy1))
        delta = a1 - a0
        self._rotation_deg = (self._drag_start_rotation + delta) % 360.0
        # Live-Update der Karte; Background-Pixmap-Rebuild via Throttle
        if not self._rotation_timer.isActive():
            self._rotation_timer.start(ROTATE_DEBOUNCE_MS)
        self.update()
        event.accept()

    def mouseReleaseEvent(self, event):  # noqa: N802
        if event.button() == Qt.LeftButton and self._drag_start_pos is not None:
            self._drag_start_pos = None
            self.setCursor(Qt.OpenHandCursor)
            self._invalidate_background()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def reset_view(self) -> None:
        """Zoom auf 1.0, Rotation auf 0° zuruecksetzen."""
        self._zoom = 1.0
        self._rotation_deg = 0.0
        self._invalidate_background()

    def mouseDoubleClickEvent(self, event):  # noqa: N802
        """Doppelklick auf die Karte → reset zu Norden oben + voller Zoom."""
        if event.button() == Qt.LeftButton:
            self.reset_view()
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

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
        # Live-Layer (Schritt 7): Sektor-Wedges → Punkte → User-Marker
        if self._show_sectors:
            self._paint_sector_wedges(painter)
        if self._show_stations:
            self._paint_stations(painter)
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
            self._paint_aurora(painter)
            self._paint_coastlines(painter)
            self._paint_distance_rings(painter)
            self._paint_compass(painter)
            self._paint_sector_lines(painter)
        finally:
            painter.end()
        return pix

    def _paint_aurora(self, painter: QPainter) -> None:
        """Subtiler RadialGradient von leicht-blau in der Mitte zu fast-schwarz aussen.
        Bricht die Monotonie des Hintergrunds ohne Daten zu ueberlagern."""
        from PySide6.QtGui import QRadialGradient
        cx, cy = self._center_px()
        radius = max(self.width(), self.height())
        grad = QRadialGradient(QPointF(cx, cy), radius)
        # Mitte: dezent blaues Glow, Rand: voll dunkel
        center_color = QColor(COLOR_BG_CENTER)
        center_color.setAlpha(140)
        edge_color = QColor(COLOR_BG)
        edge_color.setAlpha(0)
        grad.setColorAt(0.0, center_color)
        grad.setColorAt(0.55, QColor(COLOR_BG_CENTER) if False else QColor(20, 25, 50, 60))
        grad.setColorAt(1.0, edge_color)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(grad))
        painter.drawRect(0, 0, self.width(), self.height())

    def _paint_coastlines(self, painter: QPainter) -> None:
        """Glowing Coastlines: erst breiter Halo (Cyan, Alpha 0.18), dann
        schmaler Core (Cyan-Hell, Alpha 0.7) — Dual-Stroke ohne teuren Blur-Filter."""
        if not self._coastlines:
            return
        cx, cy = self._center_px()
        # Polygone projezieren — pro Linie einmal, beide Strokes verwenden gleiche Polys
        polys: list[QPolygonF] = []
        for line in self._coastlines:
            poly = QPolygonF()
            for lon, lat in line:
                projected = self._project(lat, lon)
                if projected is None:
                    if poly.size() >= 2:
                        polys.append(poly)
                    poly = QPolygonF()
                    continue
                dx, dy = projected
                poly.append(QPointF(cx + dx, cy + dy))
            if poly.size() >= 2:
                polys.append(poly)
        # Pass 1: Halo (breit, transparent)
        halo_color = QColor(COLOR_COAST_HALO)
        halo_color.setAlpha(40)
        halo_pen = QPen(halo_color)
        halo_pen.setWidthF(2.5)
        halo_pen.setCapStyle(Qt.RoundCap)
        halo_pen.setJoinStyle(Qt.RoundJoin)
        painter.setPen(halo_pen)
        for p in polys:
            painter.drawPolyline(p)
        # Pass 2: Core (schmal, hell)
        core_color = QColor(COLOR_COAST_CORE)
        core_color.setAlpha(180)
        core_pen = QPen(core_color)
        core_pen.setWidthF(0.7)
        painter.setPen(core_pen)
        for p in polys:
            painter.drawPolyline(p)

    def _paint_distance_rings(self, painter: QPainter) -> None:
        cx, cy = self._center_px()
        radius = self._radius_px()
        max_km = self._effective_max_km()
        pen = QPen(QColor(COLOR_RINGS))
        pen.setStyle(Qt.DashLine)
        pen.setWidthF(0.8)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        for km in DISTANCE_RINGS_KM:
            if km > max_km:
                continue  # Ring liegt ausserhalb des sichtbaren Bereichs
            r = radius * (km / max_km)
            painter.drawEllipse(QPointF(cx, cy), r, r)

    def _paint_sector_lines(self, painter: QPainter) -> None:
        cx, cy = self._center_px()
        radius = self._radius_px()
        pen = QPen(QColor(COLOR_SECTOR_LINES))
        pen.setWidthF(0.5)
        painter.setPen(pen)
        for i in range(SECTOR_COUNT):
            angle_deg = i * SECTOR_WIDTH_DEG - SECTOR_WIDTH_DEG / 2.0 + self._rotation_deg
            rad = math.radians(angle_deg)
            x = cx + radius * math.sin(rad)
            y = cy - radius * math.cos(rad)
            painter.drawLine(QPointF(cx, cy), QPointF(x, y))

    def _paint_compass(self, painter: QPainter) -> None:
        cx, cy = self._center_px()
        radius = self._radius_px()
        painter.setPen(QColor(COLOR_COMPASS))
        painter.setFont(QFont("Menlo", 10, QFont.Bold))
        # 8 Compass-Punkte, jeweils 45° — Position rotiert mit Karte,
        # Text bleibt aufrecht (lesbar)
        for i, label in enumerate(COMPASS_LABELS):
            angle_deg = i * 45.0 + self._rotation_deg
            rad = math.radians(angle_deg)
            x = cx + (radius + 14) * math.sin(rad)
            y = cy - (radius + 14) * math.cos(rad)
            metrics = painter.fontMetrics()
            tw = metrics.horizontalAdvance(label)
            th = metrics.height()
            painter.drawText(
                QPointF(x - tw / 2.0, y + th / 4.0), label
            )

    # ── Layer-Toggles ─────────────────────────────────────

    def set_show_sectors(self, on: bool) -> None:
        self._show_sectors = bool(on)
        self.update()

    def set_show_stations(self, on: bool) -> None:
        self._show_stations = bool(on)
        self.update()

    # ── Live-Layer: Sektor-Wedges ─────────────────────────

    def _paint_sector_wedges(self, painter: QPainter) -> None:
        if not self._sectors:
            return
        cx, cy = self._center_px()
        radius = self._radius_px()
        # max count fuer relative Wedge-Laenge
        max_count = max((b.count for b in self._sectors), default=0)
        if max_count == 0:
            return

        for b in self._sectors:
            if b.count == 0:
                continue
            # Wedge-Radius proportional zur unique-Calls-Anzahl im Sektor
            r = radius * 0.95 * (b.count / max_count)
            # Sektor-Mitte Bearing: index * 22.5° + Karten-Rotation
            mid_deg = b.index * SECTOR_WIDTH_DEG + self._rotation_deg
            # QPainter.drawPie erwartet startAngle in 1/16°, gemessen ab 3-Uhr (Osten)
            # Konvertierung: Karten-Norden (0°) = Qt-90°, Karten-Osten (90°) = Qt-0°
            qt_start_deg = 90.0 - mid_deg - SECTOR_WIDTH_DEG / 2.0
            qt_span_deg = SECTOR_WIDTH_DEG
            color = self._sector_color(b)
            painter.setPen(Qt.NoPen)
            painter.setBrush(QBrush(color))
            painter.drawPie(
                int(cx - r), int(cy - r), int(2 * r), int(2 * r),
                int(qt_start_deg * 16), int(qt_span_deg * 16),
            )

    def _sector_color(self, bucket: SectorBucket) -> QColor:
        """Sektor-Farbton aus Antenna-Counter mischen (RX-Modus).

        TX-Modus: einheitlich orange/gelb je nach max-SNR im Sektor.
        """
        a = SECTOR_ALPHA
        if self._mode == "tx":
            # SNR-Skala mappen → Farbe
            snr = bucket.avg_snr
            return _interpolate_color(TX_COLOR_LOW, TX_COLOR_HIGH, snr,
                                      STATION_SNR_MIN, STATION_SNR_MAX, a)
        # RX-Modus: ANT1 vs ANT2 vs Rescue
        n_a1 = bucket.ant1_count
        n_a2 = bucket.ant2_count
        n_rescue = bucket.rescue_count
        total = n_a1 + n_a2 + n_rescue
        if total == 0:
            c = QColor(RX_COLOR_DEFAULT)
            c.setAlpha(a)
            return c
        # gewichteter Mix
        r = (RX_COLOR_ANT1.red() * n_a1 + RX_COLOR_ANT2.red() * n_a2
             + RX_COLOR_RESCUE.red() * n_rescue) / total
        g = (RX_COLOR_ANT1.green() * n_a1 + RX_COLOR_ANT2.green() * n_a2
             + RX_COLOR_RESCUE.green() * n_rescue) / total
        bl = (RX_COLOR_ANT1.blue() * n_a1 + RX_COLOR_ANT2.blue() * n_a2
              + RX_COLOR_RESCUE.blue() * n_rescue) / total
        return QColor(int(r), int(g), int(bl), a)

    # ── Live-Layer: Stations-Punkte ───────────────────────

    def _paint_stations(self, painter: QPainter) -> None:
        if not self._stations:
            return
        cx, cy = self._center_px()
        # Aufrufer hat schon dedupliziert, aber sicherheitshalber pro Call nur 1×
        seen: set[str] = set()
        for s in self._stations:
            if s.call in seen:
                continue
            seen.add(s.call)
            projected = self._project(s.lat, s.lon)
            if projected is None:
                continue
            dx, dy = projected
            x = cx + dx
            y = cy + dy
            color = self._station_color(s)
            size = self._station_size(s.snr)
            painter.setPen(QPen(color.darker(150), 0.5))
            painter.setBrush(QBrush(color))
            painter.drawEllipse(QPointF(x, y), size, size)

    def _station_color(self, s: StationPoint) -> QColor:
        if self._mode == "tx":
            return _interpolate_color(
                TX_COLOR_LOW, TX_COLOR_HIGH, s.snr,
                STATION_SNR_MIN, STATION_SNR_MAX, alpha=255,
            )
        # RX
        if s.antenna == "rescue":
            return QColor(RX_COLOR_RESCUE)
        if s.antenna == "A2":
            return QColor(RX_COLOR_ANT2)
        if s.antenna == "A1":
            return QColor(RX_COLOR_ANT1)
        return QColor(RX_COLOR_DEFAULT)

    @staticmethod
    def _station_size(snr: float) -> float:
        # Linear: -25 dB → 3px, +5 dB → 8px
        if snr <= STATION_SNR_MIN:
            return STATION_MIN_PX
        if snr >= STATION_SNR_MAX:
            return STATION_MAX_PX
        frac = (snr - STATION_SNR_MIN) / (STATION_SNR_MAX - STATION_SNR_MIN)
        return STATION_MIN_PX + frac * (STATION_MAX_PX - STATION_MIN_PX)

    # ── User-Marker (Diamant im Zentrum) ──────────────────

    def _paint_user_marker(self, painter: QPainter) -> None:
        cx, cy = self._center_px()
        # Halo-Layer: weicher gelber RadialGradient unter dem Diamanten
        from PySide6.QtGui import QRadialGradient
        halo_grad = QRadialGradient(QPointF(cx, cy), 14)
        halo_color = QColor(COLOR_USER_GLOW)
        halo_color.setAlpha(120)
        halo_grad.setColorAt(0.0, halo_color)
        halo_grad.setColorAt(1.0, QColor(255, 230, 0, 0))
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(halo_grad))
        painter.drawEllipse(QPointF(cx, cy), 14, 14)
        # Diamant
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
        # Innerer weisser Kern fuer Tiefe
        painter.setBrush(QBrush(QColor("#FFFFFF")))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(QPointF(cx, cy), 2, 2)
        # Locator-Label rechts vom Marker
        painter.setFont(QFont("Menlo", 9, QFont.Bold))
        painter.setBrush(Qt.NoBrush)
        painter.setPen(QColor(COLOR_USER))
        painter.drawText(QPointF(cx + size + 6, cy + 3), self._my_locator)


# ── DirectionMapDialog — Container ────────────────────────

class DirectionMapDialog(QDialog):
    """Container-Dialog mit Toggle, Filter, Status, eingebettetem MapCanvas."""

    # Cross-Thread-Signal fuer PSK-Spots: Worker-Thread → GUI-Thread.
    _psk_spots_signal = Signal(list)
    _psk_error_signal = Signal(str)

    def __init__(
        self,
        my_locator: str = "",
        default_mode: str = "rx",
        callsign: str = "",
        mode: str = "FT8",
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.setWindowTitle("Richtungs-Karte")
        self.setModal(False)  # Decoder-Signale muessen durchkommen
        # Always-on-top als eigenes Tool-Fenster — bleibt sichtbar bis Mike es schliesst,
        # auch wenn er das Hauptfenster wieder fokussiert.
        self.setWindowFlag(Qt.Tool, True)
        self.setWindowFlag(Qt.WindowStaysOnTopHint, True)
        self.setMinimumSize(DIALOG_MIN_SIZE)
        # Geometrie aus Parent-Settings restaurieren falls vorhanden
        restored = False
        if parent is not None and hasattr(parent, "settings"):
            geom_hex = parent.settings.get("direction_map_geometry", "")
            if geom_hex:
                try:
                    self.restoreGeometry(bytes.fromhex(geom_hex))
                    restored = True
                except (ValueError, TypeError):
                    pass
        if not restored:
            self.resize(DEFAULT_DIALOG_SIZE)

        self._my_locator = my_locator
        self._callsign = callsign
        self._ft_mode = mode
        self._mode = default_mode if default_mode in ("rx", "tx") else "rx"
        self._psk_client = None  # type: ignore[var-annotated]
        self._tx_locator_cache = LocatorCache()

        self._setup_ui(my_locator)
        self._sync_toggle_state()

        # Worker → GUI-Thread Marshalling
        self._psk_spots_signal.connect(self._on_psk_spots_received,
                                        Qt.QueuedConnection)
        self._psk_error_signal.connect(self._on_psk_error,
                                        Qt.QueuedConnection)

        # Wenn TX als Default: direkt Polling starten
        if self._mode == "tx":
            self._start_tx_polling()

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
        self.cb_show_stations.toggled.connect(self.canvas.set_show_stations)
        self.cb_show_sectors = QCheckBox("Sektoren")
        self.cb_show_sectors.setChecked(True)
        self.cb_show_sectors.toggled.connect(self.canvas.set_show_sectors)
        filter_row.addWidget(self.cb_show_stations)
        filter_row.addWidget(self.cb_show_sectors)
        filter_row.addStretch()
        layout.addLayout(filter_row)

        # ── Status-Label + Bedienhinweis ─────────────────
        self.status_label = QLabel("Bereit. Mausrad = Zoom, ziehen = drehen, Doppelklick = Reset.")
        self.status_label.setStyleSheet("color: #889; padding: 2px 4px;")
        layout.addWidget(self.status_label)

    # ── Toggle-Logik ──────────────────────────────────────

    def _on_mode_toggled(self, mode: str) -> None:
        # Doppel-Klick auf aktiven Mode: einfach State-Sync und Status refreshen.
        # checkable QPushButton wuerde sonst aktiven Button uncheck'en.
        prev = self._mode
        self._mode = mode
        self._sync_toggle_state()
        self.canvas.set_mode(mode)
        # Beim Wechsel das andere Datenset sofort wegraeumen, sonst zeigt
        # die Karte alte RX-Daten waehrend TX-Polling laeuft (verwirrend).
        if prev != mode:
            self.canvas.update_stations([])
        if mode == "rx":
            self.set_status("EMPFANG: warte auf Live-Daten …")
            self._stop_tx_polling()
        else:
            self.set_status("SENDEN: starte PSK-Reporter Polling …")
            self._start_tx_polling()

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
        """Wird vom PSKReporterClient-Callback aufgerufen.

        Aufrufer muss aus dem GUI-Thread kommen (oder via _psk_spots_signal
        marshallen wie _start_tx_polling es tut)."""
        if self._mode == "tx":
            self.canvas.update_stations(stations)
            self.set_status(f"SENDEN: {len(stations)} Reception-Reports.")

    # ── TX-Modus: PSK-Reporter Polling ────────────────────

    def set_callsign(self, callsign: str, mode: str = "FT8") -> None:
        """Wird vor open_direction_map vom MainWindow aufgerufen."""
        self._callsign = callsign
        self._ft_mode = mode

    def _start_tx_polling(self) -> None:
        if not self._callsign:
            self.set_status("SENDEN: kein Callsign in Einstellungen — Polling deaktiviert.")
            return
        if self._psk_client is not None and self._psk_client.is_running:
            return
        from core.psk_reporter import PSKReporterClient
        if self._psk_client is None:
            self._psk_client = PSKReporterClient(
                callsign=self._callsign, mode=self._ft_mode,
            )
        # Cache zuerst zeigen (sofort, ohne API-Wartezeit)
        self._render_cached_spots()
        self._psk_client.start_polling(
            on_spots=lambda spots: self._psk_spots_signal.emit(spots),
            on_error=lambda e: self._psk_error_signal.emit(str(e)),
            window_min=self.time_window_min,
        )
        self.set_status("SENDEN: PSK-Reporter Polling laeuft …")

    def _stop_tx_polling(self) -> None:
        if self._psk_client is not None and self._psk_client.is_running:
            self._psk_client.stop(timeout_s=2.0)

    def _render_cached_spots(self) -> None:
        """Beim Wechsel zu TX: gecachte Spots SOFORT zeigen, ohne API zu warten."""
        if self._psk_client is None:
            return
        spots = self._psk_client.cached_spots()
        if not spots:
            return
        points = self._spots_to_station_points(spots)
        if self._mode == "tx":
            self.canvas.update_stations(points)
            self.set_status(f"SENDEN: {len(points)} Reports aus Cache, neue API-Abfrage laeuft …")

    @Slot(list)
    def _on_psk_spots_received(self, spots: list) -> None:
        """GUI-Thread: PSK-Reporter Spots → StationPoints → Karte."""
        if self._mode != "tx":
            return  # User hat zu RX gewechselt, ignorieren
        points = self._spots_to_station_points(spots)
        self.canvas.update_stations(points)
        self.set_status(f"SENDEN: {len(points)} Reports von {len(spots)} Spots.")

    @Slot(str)
    def _on_psk_error(self, msg: str) -> None:
        if self._mode != "tx":
            return
        # Verkuerztes Error-Label, kein Stack-Trace
        short = msg if len(msg) < 60 else msg[:57] + "…"
        self.set_status(f"SENDEN: PSK-Reporter offline — {short}")

    def _spots_to_station_points(self, spots: list) -> list[StationPoint]:
        """PSK-Spots in StationPoints konvertieren (Locator → Lat/Lon).

        normalize_call strippt /P /MM /QRP — danach ist is_mobile() immer False.
        Im TX-Pfad ist Mobile-Filter ueberfluessig: die PSK-API liefert pro Spot
        einen eigenen Locator, anders als der RX-Pfad wo CQ-Locator erst aus
        dem Stream lernen.
        """
        from core.psk_reporter import normalize_call
        points: list[StationPoint] = []
        seen: set[str] = set()
        for s in spots:
            call = normalize_call(s.rx_call)
            if not call or call in seen:
                continue
            self._tx_locator_cache.update(call, s.rx_locator)
            loc = self._tx_locator_cache.get(call)
            if not loc:
                continue
            latlon = safe_locator_to_latlon(loc)
            if latlon is None:
                continue
            seen.add(call)
            points.append(StationPoint(
                call=call,
                locator=loc,
                lat=latlon[0],
                lon=latlon[1],
                snr=float(s.snr_db) if s.snr_db is not None else -30.0,
                antenna="",  # TX hat keine Antennen-Info
                timestamp=float(s.timestamp),
            ))
        return points

    def closeEvent(self, event):  # noqa: N802
        # Polling sauber stoppen, sonst laeuft daemon-Thread weiter
        self._stop_tx_polling()
        # Geometrie persistieren ueber MainWindow.settings
        parent = self.parent()
        if parent is not None and hasattr(parent, "settings"):
            try:
                parent.settings.set(
                    "direction_map_geometry",
                    bytes(self.saveGeometry()).hex()
                )
                parent.settings.set("direction_map_default_mode", self._mode)
            except Exception:
                pass
        super().closeEvent(event)

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
