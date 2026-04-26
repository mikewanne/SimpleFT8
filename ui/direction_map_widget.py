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
    _COUNTRY_COORDS, _PREFIX_MAP,
    azimuthal_equidistant_project, distance_km, orthographic_project,
    safe_locator_to_latlon,
)


# ── Layout-Konstanten ─────────────────────────────────────

COLOR_BG = "#0A0A14"
COLOR_BG_CENTER = "#0A1030"      # Aurora-Mitte: leichtes Blau
COLOR_LAND_FILL = "#5A4A2C"      # warmes Sepia/Bronze fuer Land
COLOR_LAND_FILL_HIGH = "#8B6F47" # heller fuer Mitten-Highlight
COLOR_COAST_HALO = "#00FFAA"     # Cyan-Halo aussen
COLOR_COAST_CORE = "#88FFCC"     # Cyan hell innen
COLOR_RINGS = "#1F2A3A"          # leicht blaeulich statt nur grau
COLOR_COMPASS = "#88AACC"        # blau-cyan statt grau
COLOR_SECTOR_LINES = "#1A2030"
COLOR_USER = "#FFE600"           # Neon-Gelb
COLOR_USER_GLOW = "#FFFFAA"      # Halo um den Diamanten
COLOR_HINT = "#7788AA"

RX_COLOR_ANT1 = QColor("#00BFFF")    # Neon-Blau
RX_COLOR_ANT2 = QColor("#00FFCC")    # Neon-Cyan
RX_COLOR_RESCUE = QColor("#39FF14")  # Neon-Gruen (Rescue-Punch)
RX_COLOR_DEFAULT = QColor("#AAAACC")
TX_COLOR_LOW = QColor("#884400")     # ~-25 dB → dunkles Orange
TX_COLOR_HIGH = QColor("#FFEE00")    # ~+5 dB  → Hellgelb
SECTOR_ALPHA = 100  # 0..255 (~0.4)
HEATMAP_COLOR_LOW = QColor("#2D004F")    # dunkles Violett (1 Station)
HEATMAP_COLOR_HIGH = QColor("#FF6B00")   # Neon-Orange (≥10 Stationen)
HEATMAP_MIN_RADIUS_PX = 10.0
HEATMAP_MAX_RADIUS_PX = 40.0
HEATMAP_MAX_COUNT = 10  # ab 10 Stations sat. Farbe
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
GLOBE_SENSITIVITY_DEG_PER_PX = 0.35  # 1 px Mausbewegung @ zoom=1

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

# ── Quaternion-Math fuer 3D-Globus-Rotation ───────────────
#
# Mike's Wunsch: Erde rotiert um die Achse, JO31 bleibt am Bildschirm-Center.
# Variante: Welt-Punkte werden durch Quaternion-Rotation um eine Achse durch
# JO31 transformiert BEVOR sie azimuthal-equidistant-projeziert werden.
# Da JO31 selbst auf der Achse liegt, bleibt es invariant → fix in der Mitte.

def _quat_from_axis_angle(ax: float, ay: float, az: float,
                          angle_rad: float) -> tuple[float, float, float, float]:
    """Einheitsquaternion (w, x, y, z) fuer Rotation um Achse (ax,ay,az) um angle_rad."""
    norm = math.sqrt(ax * ax + ay * ay + az * az)
    if norm < 1e-12:
        return (1.0, 0.0, 0.0, 0.0)
    ax /= norm; ay /= norm; az /= norm
    s = math.sin(angle_rad / 2.0)
    return (math.cos(angle_rad / 2.0), ax * s, ay * s, az * s)


def _quat_mul(q1: tuple, q2: tuple) -> tuple[float, float, float, float]:
    """Hamilton-Produkt q1 * q2 (q2 wird zuerst angewendet)."""
    a, b, c, d = q1
    e, f, g, h = q2
    return (
        a * e - b * f - c * g - d * h,
        a * f + b * e + c * h - d * g,
        a * g - b * h + c * e + d * f,
        a * h + b * g - c * f + d * e,
    )


def _quat_rotate(q: tuple, p: tuple[float, float, float]) -> tuple[float, float, float]:
    """Rotiert Vektor p durch Quaternion q (q * p_quat * q_conj, vereinfacht)."""
    qw, qx, qy, qz = q
    px, py, pz = p
    tx = 2.0 * (qy * pz - qz * py)
    ty = 2.0 * (qz * px - qx * pz)
    tz = 2.0 * (qx * py - qy * px)
    cx = qy * tz - qz * ty
    cy = qz * tx - qx * tz
    cz = qx * ty - qy * tx
    return (px + qw * tx + cx, py + qw * ty + cy, pz + qw * tz + cz)


def _latlon_to_xyz(lat_deg: float, lon_deg: float) -> tuple[float, float, float]:
    lat = math.radians(lat_deg)
    lon = math.radians(lon_deg)
    cl = math.cos(lat)
    return (cl * math.cos(lon), cl * math.sin(lon), math.sin(lat))


def _xyz_to_latlon(x: float, y: float, z: float) -> tuple[float, float]:
    z_clamped = max(-1.0, min(1.0, z))
    return (math.degrees(math.asin(z_clamped)), math.degrees(math.atan2(y, x)))


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
    """Coastline-LineStrings aus dem Asset (fuer Outline-Render)."""
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


def load_landmasses() -> list[list[tuple[float, float]]]:
    """Land-Polygone (geschlossene Aussenringe) fuer Globus-Land-Fill."""
    try:
        asset_path = (
            Path(__file__).parent.parent / "assets" /
            "ne_110m_land_antimeridian_split.geojson"
        )
        with open(asset_path) as f:
            data = json.load(f)
        return [[(pt[0], pt[1]) for pt in poly] for poly in data.get("polygons", [])]
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
        self._landmasses = load_landmasses()
        self._bg_pixmap: QPixmap | None = None
        self._stations: list[StationPoint] = []
        self._sectors: list[SectorBucket] = []
        self._mode = "rx"  # "rx" oder "tx"
        self._show_sectors = True
        self._show_stations = True

        # Zoom + 3D-Globus State (Orthographic-Projektion)
        self._zoom = 1.0  # 1.0 = Globus fuellt min(width,height)*RADIUS_FRACTION
        # Beobachter-Position auf Erdkugel (View-Center). Globus dreht sich
        # um seine Polar-Achse → Lon aendert sich. Beobachter kippt → Lat aendert sich.
        # Initial: schaut JO31 direkt an.
        self._view_lat: float = self._my_pos[0] if self._my_pos else 0.0
        self._view_lon: float = self._my_pos[1] if self._my_pos else 0.0
        self._drag_start_pos: QPointF | None = None
        self._drag_start_view_lat: float = self._view_lat
        self._drag_start_view_lon: float = self._view_lon

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
        # Bei neuem Locator: View auf den neuen User-Locator zentrieren
        if self._my_pos:
            self._view_lat, self._view_lon = self._my_pos
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
        """Globus-Radius in Pixeln, skaliert mit Zoom."""
        return min(self.width(), self.height()) * MAP_RADIUS_FRACTION * self._zoom

    def _project(self, lat: float, lon: float) -> tuple[float, float] | None:
        """Orthographische Projektion: Erd-Ansicht von außen wie 3D-Globus.
        Returnt None für Punkte auf der Rückseite der Kugel."""
        if not self._my_pos:
            return None
        return orthographic_project(
            self._view_lat, self._view_lon, lat, lon,
            radius_px=self._radius_px(),
        )

    def _user_screen_pos(self) -> tuple[float, float] | None:
        """User-Locator auf dem Globus. None wenn auf Rueckseite."""
        if not self._my_pos:
            return None
        projected = self._project(self._my_pos[0], self._my_pos[1])
        if projected is None:
            return None
        cx, cy = self._center_px()
        return (cx + projected[0], cy + projected[1])

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

    # ── Drag-to-rotate: Globus dreht um polare + horizontale Achse ─

    def mousePressEvent(self, event):  # noqa: N802
        if event.button() == Qt.LeftButton and self._my_pos:
            self._drag_start_pos = event.position()
            self._drag_start_view_lat = self._view_lat
            self._drag_start_view_lon = self._view_lon
            self.setCursor(Qt.ClosedHandCursor)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):  # noqa: N802
        if self._drag_start_pos is None or not self._my_pos:
            return super().mouseMoveEvent(event)
        dx_px = event.position().x() - self._drag_start_pos.x()
        dy_px = event.position().y() - self._drag_start_pos.y()
        sens = GLOBE_SENSITIVITY_DEG_PER_PX / self._zoom
        # Maus rechts → Globus rotiert nach rechts (wir gucken auf eine
        # westlichere Stelle, view_lon nimmt ab). Inhalt folgt Maus.
        new_lon_raw = self._drag_start_view_lon - dx_px * sens
        new_lon = ((new_lon_raw + 180.0) % 360.0) - 180.0
        # Maus runter → Globus kippt nach unten (wir gucken auf eine
        # noerdlichere Stelle, view_lat nimmt zu). Bis ±85° (Pol-Singularitaet).
        new_lat_raw = self._drag_start_view_lat + dy_px * sens
        new_lat = max(-85.0, min(85.0, new_lat_raw))
        if (abs(new_lat - self._view_lat) < 0.01
                and abs(new_lon - self._view_lon) < 0.01):
            return
        self._view_lat = new_lat
        self._view_lon = new_lon
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
        """Zoom auf 1.0, Beobachter zurueck auf JO31."""
        self._zoom = 1.0
        if self._my_pos:
            self._view_lat, self._view_lon = self._my_pos
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
        # Live-Layer (Globus-Vordergrund). Distance-Rings + Sektor-Linien
        # entfallen beim Globus — Pixel-Kreise um den User stimmen nicht
        # mit der Sphaere ueberein, das gab Striche durch die Laender.
        # Die Sektor-Wedges (kleine Pies) bleiben — die sind kompakt am User.
        if self._show_stations:
            self._paint_country_heatmap(painter)
        if self._show_sectors:
            self._paint_sector_wedges(painter)
        if self._show_stations:
            self._paint_connection_lines(painter)
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
            self._paint_globe_disk(painter)
            self._paint_landmasses(painter)
            self._paint_coastlines(painter)
            self._paint_compass(painter)
        finally:
            painter.end()
        return pix

    def _paint_landmasses(self, painter: QPainter) -> None:
        """Land-Polygone als gefuellte Flaechen — gibt dem Globus den klassischen
        Look mit Land/Wasser-Unterscheidung.

        Polygone die teilweise auf der Rueckseite liegen werden am Hemisphaeren-
        Rand abgeschnitten (Bisektion zwischen letztem sichtbaren und erstem
        unsichtbaren Punkt). Sub-Polygone werden separat gefuellt."""
        if not self._landmasses:
            return
        cx, cy = self._center_px()
        globe_r = self._radius_px()
        painter.save()
        from PySide6.QtGui import QPainterPath
        clip = QPainterPath()
        clip.addEllipse(QPointF(cx, cy), globe_r, globe_r)
        painter.setClipPath(clip)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(QColor(COLOR_LAND_FILL)))

        for poly in self._landmasses:
            sub_polys = self._clip_polygon_to_hemisphere(poly)
            for sub in sub_polys:
                if len(sub) >= 3:
                    points = [QPointF(cx + dx, cy + dy) for dx, dy in sub]
                    painter.drawPolygon(QPolygonF(points))
        painter.restore()

    def _clip_polygon_to_hemisphere(
        self, poly: list[tuple[float, float]]
    ) -> list[list[tuple[float, float]]]:
        """Schneidet ein Polygon am Hemisphaeren-Rand. Returnt Liste von
        Sub-Polygonen in Pixel-Offset-Koordinaten (dx, dy vom Center).

        Bei Uebergang sichtbar↔unsichtbar wird via Bisektion in lat/lon-Space
        ein Punkt am Rand der sichtbaren Hemisphaere eingefuegt — so wirkt
        das Polygon korrekt am Rand abgeschnitten."""
        if len(poly) < 3:
            return []

        # Pro Punkt: (sichtbar, projection oder None)
        states: list[tuple[bool, tuple[float, float] | None]] = []
        for lon, lat in poly:
            p = self._project(lat, lon)
            states.append((p is not None, p))

        sub_polys: list[list[tuple[float, float]]] = []
        current: list[tuple[float, float]] = []
        n = len(poly)
        for i in range(n):
            vis, p = states[i]
            prev_vis, prev_p = states[i - 1]
            if vis and prev_vis:
                current.append(p)  # type: ignore[arg-type]
            elif vis and not prev_vis:
                # Eintritt — interpolierter Rand-Punkt + aktueller Punkt
                edge = self._horizon_crossing(poly[i - 1], poly[i])
                if edge is not None:
                    current.append(edge)
                current.append(p)  # type: ignore[arg-type]
            elif not vis and prev_vis:
                # Austritt — interpolierter Rand-Punkt, dann Sub-Polygon abschliessen
                edge = self._horizon_crossing(poly[i - 1], poly[i])
                if edge is not None:
                    current.append(edge)
                if len(current) >= 3:
                    sub_polys.append(current)
                current = []
            # else: beide unsichtbar — skip
        if len(current) >= 3:
            sub_polys.append(current)
        return sub_polys

    def _horizon_crossing(
        self, p1: tuple[float, float], p2: tuple[float, float],
    ) -> tuple[float, float] | None:
        """Findet via Bisektion in lat/lon-Space den Punkt zwischen p1 und p2
        am Rand der sichtbaren Hemisphaere (cos_c == 0). Returnt projezierte
        Pixel-Offset-Koordinaten."""
        lon1, lat1 = p1
        lon2, lat2 = p2
        # Bisektion: lo ist sichtbar (oder unbekannt), hi ist unsichtbar
        # Bestimmen welche Seite welche ist
        v1 = self._project(lat1, lon1)
        v2 = self._project(lat2, lon2)
        if v1 is not None and v2 is None:
            lo, hi = 0.0, 1.0
        elif v1 is None and v2 is not None:
            lo, hi = 1.0, 0.0
        else:
            return None  # nicht erwartet — beide gleich
        for _ in range(12):  # 12 Iterationen → ~0.025% Genauigkeit
            mid = (lo + hi) / 2.0
            lat_m = lat1 + mid * (lat2 - lat1)
            lon_m = lon1 + mid * (lon2 - lon1)
            p = self._project(lat_m, lon_m)
            if p is not None:
                lo = mid
            else:
                hi = mid
        # Letzter sichtbarer Punkt
        lat_m = lat1 + lo * (lat2 - lat1)
        lon_m = lon1 + lo * (lon2 - lon1)
        return self._project(lat_m, lon_m)

    def _paint_globe_disk(self, painter: QPainter) -> None:
        """Die sichtbare Halbkugel als gefuellten Kreis: Ozean-Blau mit
        leichtem Gradient von Mitte (heller) zu Rand (dunkler) — gibt der
        Erde ihre 3D-Wirkung wie auf einem Globus-Foto."""
        from PySide6.QtGui import QRadialGradient
        cx, cy = self._center_px()
        r = self._radius_px()
        grad = QRadialGradient(QPointF(cx - r * 0.2, cy - r * 0.25), r * 1.2)
        # Hellere Mitte (Reflexion), dunkler zum Rand (Tiefe)
        grad.setColorAt(0.0, QColor(40, 70, 130, 220))
        grad.setColorAt(0.6, QColor(20, 40, 90, 220))
        grad.setColorAt(1.0, QColor(8, 15, 35, 220))
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(grad))
        painter.drawEllipse(QPointF(cx, cy), r, r)
        # Daruem ein duenner Highlight-Ring (Atmospheric Limb)
        painter.setBrush(Qt.NoBrush)
        pen = QPen(QColor(120, 180, 255, 100))
        pen.setWidthF(1.2)
        painter.setPen(pen)
        painter.drawEllipse(QPointF(cx, cy), r + 0.5, r + 0.5)

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

    def _paint_user_distance_rings(self, painter: QPainter) -> None:
        """Distance-Rings am User-Marker. Nur wenn User auf sichtbarer Hemisphaere.
        Pixel-Skala: 1° Großkreis ≈ pi*radius/180 px (Naeherung am User-Punkt)."""
        user_pos = self._user_screen_pos()
        if user_pos is None:
            return
        ux, uy = user_pos
        globe_r = self._radius_px()
        # Erdumfang: 40075 km = 360°. 1° = 111.32 km.
        # Auf der Globus-Sphaere: 1° entspricht globe_r * pi/180 Pixeln (am Punkt selbst).
        pen = QPen(QColor(COLOR_RINGS))
        pen.setStyle(Qt.DashLine)
        pen.setWidthF(0.8)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        # Clip auf Globus-Disk (Distanzring darf nicht ueber den Globus-Rand)
        cx, cy = self._center_px()
        painter.save()
        from PySide6.QtGui import QPainterPath
        clip = QPainterPath()
        clip.addEllipse(QPointF(cx, cy), globe_r, globe_r)
        painter.setClipPath(clip)
        for km in DISTANCE_RINGS_KM:
            # km auf Sphaere → Bogen-Winkel in rad → Pixel auf Tangentialebene
            ang_rad = (km / 6371.0)  # Erdradius
            r_px = globe_r * math.sin(ang_rad)  # Orthographic: Sehnen-Projektion
            if r_px > globe_r * 1.2:
                continue
            painter.drawEllipse(QPointF(ux, uy), r_px, r_px)
        painter.restore()

    def _paint_user_sector_lines(self, painter: QPainter) -> None:
        """Sektor-Linien um den User. Nur wenn User auf sichtbarer Hemisphaere."""
        user_pos = self._user_screen_pos()
        if user_pos is None:
            return
        ux, uy = user_pos
        globe_r = self._radius_px()
        # Sektoren als kurze Linien (15% des Globus-Radius, sonst Verzerrung)
        line_len = globe_r * 0.15
        pen = QPen(QColor(COLOR_SECTOR_LINES))
        pen.setWidthF(0.5)
        painter.setPen(pen)
        cx, cy = self._center_px()
        painter.save()
        from PySide6.QtGui import QPainterPath
        clip = QPainterPath()
        clip.addEllipse(QPointF(cx, cy), globe_r, globe_r)
        painter.setClipPath(clip)
        for i in range(SECTOR_COUNT):
            angle_deg = i * SECTOR_WIDTH_DEG - SECTOR_WIDTH_DEG / 2.0
            rad = math.radians(angle_deg)
            x = ux + line_len * math.sin(rad)
            y = uy - line_len * math.cos(rad)
            painter.drawLine(QPointF(ux, uy), QPointF(x, y))
        painter.restore()

    def _paint_compass(self, painter: QPainter) -> None:
        # Compass bleibt am Bildschirm-Center: zeigt N/E/S/W relative zur
        # View-Center-Projektion. Bei Globus-Pan ist Norden weiterhin oben am
        # Bildschirm — aber die Sektor-Wedges (User-zentriert) wandern mit dem User.
        cx, cy = self._center_px()
        radius = self._radius_px()
        painter.setPen(QColor(COLOR_COMPASS))
        painter.setFont(QFont("Menlo", 10, QFont.Bold))
        for i, label in enumerate(COMPASS_LABELS):
            angle_deg = i * 45.0
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
        user_pos = self._user_screen_pos()
        if user_pos is None:
            return  # User auf Globus-Rueckseite
        ux, uy = user_pos
        globe_r = self._radius_px()
        # Wedges sind klein gehalten (max 30% Globus-Radius), bleiben in der
        # Globus-Disk damit es nicht ueber den Rand klatscht.
        max_wedge_r = globe_r * 0.30
        max_count = max((b.count for b in self._sectors), default=0)
        if max_count == 0:
            return
        cx, cy = self._center_px()
        painter.save()
        from PySide6.QtGui import QPainterPath
        clip = QPainterPath()
        clip.addEllipse(QPointF(cx, cy), globe_r, globe_r)
        painter.setClipPath(clip)
        for b in self._sectors:
            if b.count == 0:
                continue
            r = max_wedge_r * (b.count / max_count)
            mid_deg = b.index * SECTOR_WIDTH_DEG
            qt_start_deg = 90.0 - mid_deg - SECTOR_WIDTH_DEG / 2.0
            qt_span_deg = SECTOR_WIDTH_DEG
            color = self._sector_color(b)
            painter.setPen(Qt.NoPen)
            painter.setBrush(QBrush(color))
            painter.drawPie(
                int(ux - r), int(uy - r), int(2 * r), int(2 * r),
                int(qt_start_deg * 16), int(qt_span_deg * 16),
            )
        painter.restore()

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

    # ── Live-Layer: Country-Heatmap ───────────────────────

    def _paint_country_heatmap(self, painter: QPainter) -> None:
        """Pro Land mit aktiven Stations: RadialGradient-Glow an den Country-
        Koordinaten. Groesse + Farbe nach Stations-Anzahl pro Land. Nutzt
        _COUNTRY_COORDS aus core/geo (Hauptstadt-Position pro Land).
        """
        if not self._stations:
            return
        # Aktivitaet pro Country-Code aggregieren (call → prefix → country)
        counts: dict[str, int] = {}
        seen: set[str] = set()
        for s in self._stations:
            if s.call in seen:
                continue
            seen.add(s.call)
            country = self._call_to_country(s.call)
            if not country or country not in _COUNTRY_COORDS:
                continue
            counts[country] = counts.get(country, 0) + 1
        if not counts:
            return

        from PySide6.QtGui import QRadialGradient
        cx, cy = self._center_px()
        painter.setPen(Qt.NoPen)
        for country, count in counts.items():
            lat, lon = _COUNTRY_COORDS[country]
            projected = self._project(lat, lon)
            if projected is None:
                continue
            dx, dy = projected
            x = cx + dx
            y = cy + dy
            # Skala: 1..HEATMAP_MAX_COUNT auf 0..1 mappen
            frac = min(1.0, count / HEATMAP_MAX_COUNT)
            radius = HEATMAP_MIN_RADIUS_PX + frac * (HEATMAP_MAX_RADIUS_PX - HEATMAP_MIN_RADIUS_PX)
            color = self._heatmap_color(frac)
            grad = QRadialGradient(QPointF(x, y), radius)
            inner = QColor(color)
            inner.setAlpha(int(60 + frac * 80))  # 60..140
            grad.setColorAt(0.0, inner)
            edge = QColor(color)
            edge.setAlpha(0)
            grad.setColorAt(1.0, edge)
            painter.setBrush(QBrush(grad))
            painter.drawEllipse(QPointF(x, y), radius, radius)

    @staticmethod
    def _call_to_country(call: str) -> str | None:
        """Callsign → 2-/3-Letter Country-Code via _PREFIX_MAP."""
        if not call:
            return None
        c = call.upper().strip().lstrip("<").rstrip(">")
        if "/" in c:
            parts = c.split("/")
            c = max(parts, key=len)
        for plen in (3, 2, 1):
            prefix = c[:plen]
            if prefix in _PREFIX_MAP:
                return _PREFIX_MAP[prefix]
        return None

    @staticmethod
    def _heatmap_color(frac: float) -> QColor:
        """Lerp zwischen HEATMAP_COLOR_LOW (frac=0) und HEATMAP_COLOR_HIGH (frac=1)."""
        f = max(0.0, min(1.0, frac))
        r = HEATMAP_COLOR_LOW.red() + f * (HEATMAP_COLOR_HIGH.red() - HEATMAP_COLOR_LOW.red())
        g = HEATMAP_COLOR_LOW.green() + f * (HEATMAP_COLOR_HIGH.green() - HEATMAP_COLOR_LOW.green())
        b = HEATMAP_COLOR_LOW.blue() + f * (HEATMAP_COLOR_HIGH.blue() - HEATMAP_COLOR_LOW.blue())
        return QColor(int(r), int(g), int(b))

    # ── Live-Layer: Connection Lines (Spider-Web) ─────────

    def _paint_connection_lines(self, painter: QPainter) -> None:
        """Linien vom User-Locator (am Bildschirm) zu jeder Station. Bei Globus-
        Pan landet der User-Locator nicht mehr im Center — die Lines starten
        immer am User."""
        if not self._stations:
            return
        user_pos = self._user_screen_pos()
        if user_pos is None:
            return  # User aus Sicht-Bereich gerollt
        cx, cy = self._center_px()
        center = QPointF(*user_pos)
        seen: set[str] = set()
        # Pen pro Pass setzen reduziert state-changes — wir sortieren hier nicht,
        # bei <200 Punkten ist setPen pro Linie billig genug
        for s in self._stations:
            if s.call in seen:
                continue
            seen.add(s.call)
            projected = self._project(s.lat, s.lon)
            if projected is None:
                continue
            dx, dy = projected
            color = QColor(self._station_color(s))
            # Alpha nach SNR-Stufe: 90..200 (starke Stationen praegnanter)
            snr = s.snr
            if snr <= STATION_SNR_MIN:
                alpha = 70
            elif snr >= STATION_SNR_MAX:
                alpha = 200
            else:
                frac = (snr - STATION_SNR_MIN) / (STATION_SNR_MAX - STATION_SNR_MIN)
                alpha = int(70 + frac * 130)
            color.setAlpha(alpha)
            pen = QPen(color)
            # Linienstaerke ebenfalls SNR-skaliert (0.4..1.6 px)
            pen.setWidthF(0.4 + (alpha / 200.0) * 1.2)
            painter.setPen(pen)
            painter.drawLine(center, QPointF(cx + dx, cy + dy))

    # ── Live-Layer: Stations-Punkte ───────────────────────

    def _paint_stations(self, painter: QPainter) -> None:
        """Stationen als Leuchtkugeln: RadialGradient hell→Farbe, plus 1px Outer-Ring."""
        if not self._stations:
            return
        from PySide6.QtGui import QRadialGradient
        cx, cy = self._center_px()
        seen: set[str] = set()
        painter.setPen(Qt.NoPen)  # Gradient-Kugeln, kein harter Stroke
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
            # Outer-Halo Glow (zusaetzliche 2px aussen, sehr transparent)
            halo = QColor(color)
            halo.setAlpha(60)
            painter.setBrush(QBrush(halo))
            painter.drawEllipse(QPointF(x, y), size + 2.0, size + 2.0)
            # Hauptkugel: RadialGradient hell→Farbe → "Leuchtkugel"
            grad = QRadialGradient(QPointF(x, y), size)
            light = QColor(255, 255, 255, 220)
            grad.setColorAt(0.0, light)
            mid = QColor(color)
            mid.setAlpha(220)
            grad.setColorAt(0.4, mid)
            edge = QColor(color)
            edge.setAlpha(150)
            grad.setColorAt(1.0, edge)
            painter.setBrush(QBrush(grad))
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
        user_pos = self._user_screen_pos()
        if user_pos is None:
            return  # User durch Pan ausserhalb der Sicht
        cx, cy = user_pos
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
        # Always-on-top als eigenstaendiges Fenster (Qt.Tool versagt auf macOS:
        # bei Fokus-Verlust verschwindet es; Qt.Window mit StaysOnTopHint ist
        # zuverlaessig, behaelt minimize/maximize Buttons).
        self.setWindowFlags(
            Qt.Window
            | Qt.WindowStaysOnTopHint
            | Qt.CustomizeWindowHint
            | Qt.WindowTitleHint
            | Qt.WindowCloseButtonHint
            | Qt.WindowMinMaxButtonsHint
        )
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
        self.status_label = QLabel("Bereit. Mausrad = Zoom, ziehen = Globus drehen, Doppelklick = Reset.")
        self.status_label.setStyleSheet("color: #889; padding: 2px 4px;")
        layout.addWidget(self.status_label)
        # Disclaimer: Lokalisierungs-Genauigkeit
        self.disclaimer_label = QLabel(
            "ℹ Stations-Position basiert auf 4-stelligem Maidenhead-Locator (Genauigkeit "
            "~110 km) bzw. Country-Coords wenn kein Locator bekannt — Punkte koennen "
            "im Wasser landen oder leicht abweichen. Praezisere Lokalisierung folgt."
        )
        self.disclaimer_label.setWordWrap(True)
        self.disclaimer_label.setStyleSheet(
            "color: #667; padding: 2px 4px; font-size: 10px; font-style: italic;"
        )
        layout.addWidget(self.disclaimer_label)

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
