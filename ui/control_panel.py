"""SimpleFT8 Control Panel — Fenster 3: Steuerung und Status.

Dark Theme Redesign mit LED-Balance-Indikator.
"""

import time
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QSlider, QFrame, QGridLayout, QButtonGroup, QProgressBar, QSpinBox,
)

# Qt-Konstante (in PySide6 nicht direkt exportiert) — entspricht 2^24 - 1.
# Wird als „kein Limit"-Reset für setMaximumHeight() benutzt.
_QWIDGETSIZE_MAX = 16_777_215
from typing import Optional
from PySide6.QtCore import Signal, Qt, QTimer, Property, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import QFont, QPainter, QColor, QPen, QBrush, QCursor

from config.settings import BAND_FREQUENCIES
from main import APP_VERSION
from ui.widgets.stars_widget import StarsConditionWidget
from ui.styles import (
    BG as _BG, TEXT as _TEXT, FONT as _FONT, SEP_COLOR as _SEP_COLOR,
    MIN_WIDTH as _MIN_WIDTH, LED_GREEN as _LED_GREEN, LED_BLUE as _LED_BLUE,
    DIV_PCT_OFF as _DIV_PCT_OFF, DIV_PCT_GREEN as _DIV_PCT_GREEN,
    DIV_PCT_RED as _DIV_PCT_RED, DIV_PCT_TEAL as _DIV_PCT_TEAL,
    DIV_PCT_YELLOW as _DIV_PCT_YELLOW,
    BTN_BASE as _BTN_BASE,
    CARD_BLUE as _CARD_SS_BLUE, CARD_GREEN as _CARD_SS_GREEN,
    CARD_TEAL as _CARD_SS_TEAL, CARD_ORANGE as _CARD_SS_ORANGE,
    CARD_DEFAULT as _CARD_SS,
)


class FrequencyHistogramWidget(QWidget):
    """50-Hz-Bin Frequenz-Histogramm: belegte Frequenzen + freie Lücke + CQ-Marker.

    Im Normal-Modus klickbar: User klickt ins Histogramm um die TX-Frequenz
    manuell zu setzen (wie WSJT-X). Im Diversity-Modus laeuft die Auto-Suche,
    Klicks sind dort deaktiviert (kein Mouse-Tracking, Standard-Cursor).
    """

    FREQ_MIN = 150
    FREQ_MAX = 2800
    BIN_HZ   = 50

    # Signal: User hat ins Histogramm geklickt → gewuenschte TX-Freq in Hz
    tx_freq_clicked = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(50)
        self.setMinimumWidth(200)
        self._bins: dict       = {}
        self._cq_freq          = None
        self._tx_freq          = None   # Aktuelle TX-Freq (Hunt oder CQ)
        self._gap_start_hz     = None
        self._gap_end_hz       = None
        self._clickable        = False  # True nur im Normal-Modus
        # Letzte Anzeige-Range fuer Klick→Hz-Konvertierung (paintEvent setzt)
        self._last_freq_lo     = self.FREQ_MIN
        self._last_freq_hi     = self.FREQ_MAX

    def update_data(self, data: dict):
        """Daten aus DiversityController.get_histogram_data() übernehmen."""
        self._bins         = data.get('bins', {})
        self._cq_freq      = data.get('cq_freq')
        self._gap_start_hz = data.get('gap_start_hz')
        self._gap_end_hz   = data.get('gap_end_hz')
        self.update()

    def set_tx_freq(self, freq_hz: int | None):
        """Aktuelle TX-Frequenz setzen (Hunt-Mode oder manuelle Auswahl)."""
        self._tx_freq = freq_hz
        self.update()

    def set_clickable(self, clickable: bool):
        """Klick-Modus an/aus. Im Normal-Modus an (manuelle TX-Freq-Auswahl),
        im Diversity-Modus aus (Auto-Suche)."""
        self._clickable = clickable
        if clickable:
            self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            self.setToolTip("Klicken um TX-Frequenz manuell zu setzen")
        else:
            self.setCursor(QCursor(Qt.CursorShape.ArrowCursor))
            self.setToolTip("")

    def mousePressEvent(self, event):  # noqa: N802
        """Klick: x-Koordinate → TX-Frequenz in Hz, auf Bin-Breite gerundet."""
        if not self._clickable or event.button() != Qt.MouseButton.LeftButton:
            return super().mousePressEvent(event)
        w = max(1, self.width())
        x = max(0, min(w, event.position().x()))
        freq_rng = max(1, self._last_freq_hi - self._last_freq_lo)
        hz = int(self._last_freq_lo + (x / w) * freq_rng)
        # Auf Bin-Breite runden (50 Hz Raster, wie WSJT-X)
        hz = int(round(hz / self.BIN_HZ) * self.BIN_HZ)
        # Auf Hardware-Grenzen begrenzen
        hz = max(self.FREQ_MIN, min(self.FREQ_MAX, hz))
        self.tx_freq_clicked.emit(hz)
        super().mousePressEvent(event)

    def paintEvent(self, event):  # noqa: N802
        if not self._bins and self._cq_freq is None:
            return

        painter = QPainter(self)
        w, h     = self.width(), self.height()
        label_h  = 12
        bar_h    = h - label_h

        # Dynamischer Bereich: Zoom auf die Aktivitaet
        if self._bins:
            min_idx = min(self._bins.keys())
            max_idx = max(self._bins.keys())
            freq_lo = max(100, min_idx * self.BIN_HZ - 100)
            freq_hi = min(2800, max_idx * self.BIN_HZ + 200)
            # TX-Marker muss auch reinpassen
            show_freq = self._tx_freq or self._cq_freq
            if show_freq:
                freq_lo = min(freq_lo, show_freq - 50)
                freq_hi = max(freq_hi, show_freq + 50)
            # Mindestbreite 500 Hz
            if freq_hi - freq_lo < 500:
                center = (freq_lo + freq_hi) // 2
                freq_lo, freq_hi = center - 250, center + 250
        else:
            freq_lo, freq_hi = self.FREQ_MIN, self.FREQ_MAX

        # Range merken fuer Klick→Hz-Konvertierung in mousePressEvent
        self._last_freq_lo = freq_lo
        self._last_freq_hi = freq_hi
        freq_rng = max(1, freq_hi - freq_lo)

        def fx(hz: float) -> int:
            return int((hz - freq_lo) / freq_rng * w)

        # Hintergrund
        painter.fillRect(0, 0, w, bar_h, QColor("#0a0a14"))

        # Horizontale Referenz-Linien (33% / 66%)
        painter.setPen(QPen(QColor("#1c1c2a"), 1))
        for pct in (0.33, 0.66):
            y = int(bar_h * (1.0 - pct))
            painter.drawLine(0, y, w, y)

        # Bins (grau → orange → rot je Belegungsgrad)
        if self._bins:
            max_c   = max(self._bins.values(), default=1)
            bin_px  = max(2, int(self.BIN_HZ / freq_rng * w))
            for idx, cnt in self._bins.items():
                hz = idx * self.BIN_HZ
                if not (freq_lo <= hz <= freq_hi):
                    continue
                x     = fx(hz)
                ratio = cnt / max_c
                bh    = max(2, int(ratio * (bar_h - 1)))
                if ratio < 0.5:
                    r = int(80  + 175 * ratio * 2)
                    g = int(70  * (1 - ratio * 2))
                    b = 20
                else:
                    r = 255
                    g = int(60 * (1 - (ratio - 0.5) * 2))
                    b = 0
                painter.fillRect(x, bar_h - bh, bin_px, bh, QColor(r, g, b))

        # TX-Marker: gelb = CQ/vorgeschlagen, cyan = Hunt-Antwort
        marker_freq = self._tx_freq or self._cq_freq
        marker_color = "#FFD700" if not (self._tx_freq and not self._cq_freq) else "#00CED1"
        if marker_freq and freq_lo <= marker_freq <= freq_hi:
            x = fx(marker_freq)
            # Halbdurchsichtiger Glow-Streifen (auffaelliger)
            glow = QColor(marker_color)
            glow.setAlpha(50)
            painter.fillRect(x - 3, 0, 7, bar_h, glow)
            # Leuchtende Markierungslinie (4px breit)
            painter.setPen(QPen(QColor(marker_color), 4))
            painter.drawLine(x, 0, x, bar_h - 1)

        # Trennlinie Balken / Label
        painter.setPen(QPen(QColor("#222"), 1))
        painter.drawLine(0, bar_h, w, bar_h)

        # Dynamische Labels
        painter.setFont(QFont("Menlo", 7))
        painter.setPen(QColor("#555"))
        painter.drawText(1, h - 1, f"{freq_lo}")
        painter.drawText(w - 35, h - 1, f"{freq_hi}Hz")

        if marker_freq:
            x   = fx(marker_freq)
            lbl = f"TX {marker_freq}Hz"
            fm  = painter.fontMetrics()
            lw  = fm.horizontalAdvance(lbl)
            tx  = max(0, min(w - lw, x - lw // 2))
            painter.setPen(QColor(marker_color))
            painter.drawText(tx, h - 1, lbl)

        painter.end()


class _PulseBar(QWidget):
    """4 px hoher Farbbalken mit animierbarer color-Property.

    Ersetzt QFrame+setStyleSheet fuer Propagations-Balken: erlaubt
    QPropertyAnimation auf der `color`-Property (Cross-Fade in v0.69+).
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(4)
        self._color = QColor("#555555")

    def get_color(self) -> QColor:
        return self._color

    def set_color(self, c: QColor) -> None:
        self._color = c
        self.update()

    color = Property(QColor, get_color, set_color)

    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setBrush(QBrush(self._color))
        p.setPen(Qt.NoPen)
        p.drawRoundedRect(self.rect(), 2, 2)


class _ModeBandCard(QFrame):
    """Kachel 1 (blau) — Modus (FT8/FT4) + Band-Auswahl.

    P1.COLLAPSE-RADIO-MODEBAND (v0.95.17): Body ist einklappbar via
    Toggle-Button im Header. State persistiert in Settings, wird vom
    MainWindow geladen.
    """

    collapse_changed = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("card")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(_CARD_SS_BLUE)

        # Pulsier-State pro Band: {band: {"state": (cond_now, cond_60, fast),
        # "anim": QPropertyAnimation}} — leer wenn statisch.
        self._pulse: dict = {}

        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 10, 10, 10)
        lay.setSpacing(8)

        # ── Header-Row: Toggle-Button + MODUS+BAND-Label ─────────────────
        header_row = QHBoxLayout()
        header_row.setContentsMargins(0, 0, 0, 0)
        header_row.setSpacing(6)

        self.toggle_btn = QPushButton("▼")
        self.toggle_btn.setFixedSize(20, 20)
        self.toggle_btn.setFlat(True)
        self.toggle_btn.setStyleSheet(
            "QPushButton { background: transparent; color: #7799FF; "
            "border: none; font-size: 11px; font-weight: bold; padding: 0; }"
            "QPushButton:hover { color: #99BBFF; }"
        )
        self.toggle_btn.setToolTip("Modus+Band-Kachel ein-/ausklappen")
        self.toggle_btn.clicked.connect(self._toggle_collapsed)
        header_row.addWidget(self.toggle_btn)

        lbl_mb = QLabel("MODUS+BAND")
        lbl_mb.setStyleSheet(
            f"color: #7799FF; font-size: 10px; font-family: {_FONT}; font-weight: bold;"
        )
        header_row.addWidget(lbl_mb)
        header_row.addStretch()
        lay.addLayout(header_row)

        # ── Body-Container (einklappbar) ─────────────────────────────────
        self._body_widget = QWidget()
        body_lay = QVBoxLayout(self._body_widget)
        body_lay.setContentsMargins(0, 0, 0, 0)
        body_lay.setSpacing(0)

        # ── Alles in einem Grid → exakte Spalten-Ausrichtung ─────
        # Spalten: 0=Label(fix), 1=FT8, 2=FT4, 3=10m/15m, 4=12m/17m, 5=20m
        # Freq-Frame: Zeile 0, Spalten 3-5 (gleiche Breite wie 15m+17m+20m)
        self.band_buttons = {}
        grid = QGridLayout()
        grid.setSpacing(4)
        grid.setContentsMargins(0, 0, 0, 0)

        # Zeile 0: Modus + FT8/FT4 + Freq-Box
        lbl_modus = QLabel("Modus")
        lbl_modus.setFixedWidth(42)
        grid.addWidget(lbl_modus, 0, 0)
        self.btn_ft8 = QPushButton("FT8")
        self.btn_ft8.setCheckable(True)
        self.btn_ft8.setChecked(True)
        self.btn_ft8.setFixedHeight(28)
        self.btn_ft4 = QPushButton("FT4")
        self.btn_ft4.setCheckable(True)
        self.btn_ft4.setFixedHeight(28)
        self.btn_ft2 = QPushButton("FT2")
        self.btn_ft2.setCheckable(True)
        self.btn_ft2.setFixedHeight(28)
        grid.addWidget(self.btn_ft8, 0, 1)
        grid.addWidget(self.btn_ft4, 0, 2)
        grid.addWidget(self.btn_ft2, 0, 3)

        freq_frame = QFrame()
        freq_frame.setStyleSheet(
            "QFrame { border: 1px solid rgba(120,160,255,0.65); "
            "border-radius: 4px; background: rgba(0,0,0,0.3); }"
        )
        freq_frame.setFixedHeight(30)
        freq_lay = QHBoxLayout(freq_frame)
        freq_lay.setContentsMargins(6, 0, 6, 0)
        self.freq_label = QLabel("14074.000 kHz")
        self.freq_label.setStyleSheet(
            f"color: #00CC66; font-size: 13pt; font-weight: bold; "
            f"font-family: {_FONT}; border: none; background: transparent;"
        )
        self.freq_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        freq_lay.addWidget(self.freq_label)
        grid.addWidget(freq_frame, 0, 4, 1, 3)  # span 3 Spalten (= 15m + 17m + 20m)

        # Zeile 1: Band + 10m 12m 15m 17m 20m
        lbl_band = QLabel("Band")
        lbl_band.setFixedWidth(42)
        grid.addWidget(lbl_band, 1, 0)
        self.prop_bars: dict = {}
        bands_row1 = ["10m", "12m", "15m", "17m", "20m"]
        for col, b in enumerate(bands_row1):
            btn = QPushButton(b)
            btn.setCheckable(True)
            btn.setChecked(b == "20m")
            btn.setFixedHeight(28)
            self.band_buttons[b] = btn
            grid.addWidget(btn, 1, col + 1)
            bar = _PulseBar()
            bar.setVisible(False)
            self.prop_bars[b] = bar
            grid.addWidget(bar, 2, col + 1)

        # Zeile 3: 30m 40m 60m 80m (ab Spalte 1, Zeile 2→3 wegen Prop-Bars)
        bands_row2 = ["30m", "40m", "60m", "80m"]
        for col, b in enumerate(bands_row2):
            btn = QPushButton(b)
            btn.setCheckable(True)
            btn.setFixedHeight(28)
            self.band_buttons[b] = btn
            grid.addWidget(btn, 3, col + 1)
            bar = _PulseBar()
            bar.setVisible(False)
            self.prop_bars[b] = bar
            grid.addWidget(bar, 4, col + 1)

        # Alle Button-Spalten (1-5) gleich breit strecken
        for col in range(1, 6):
            grid.setColumnStretch(col, 1)
        # Prop-Bar-Zeilen minimal halten
        grid.setRowMinimumHeight(2, 4)
        grid.setRowMinimumHeight(4, 4)

        body_lay.addLayout(grid)

        # P50 (v0.97.20): Sichtbarkeit pro Band — Default alle aktiv.
        # set_visible_bands() schaltet hier um.
        self._band_visible: dict = {b: True for b in self.band_buttons}

        # ── Body-Container an Card-Layout anhaengen ──────────────────────
        lay.addWidget(self._body_widget)

    # ── Collapse-API ─────────────────────────────────────────────────────
    def set_collapsed(self, collapsed: bool) -> None:
        """Body aus-/einklappen. Setzt Toggle-Icon + MaximumHeight.

        Programm-API — emitiert KEIN collapse_changed-Signal (Init-Loop-
        Schutz). User-Klick geht ueber _toggle_collapsed.
        """
        self._body_widget.setVisible(not collapsed)
        self.toggle_btn.setText("▶" if collapsed else "▼")
        if collapsed:
            self.setMaximumHeight(36)
        else:
            self.setMaximumHeight(_QWIDGETSIZE_MAX)

    def is_collapsed(self) -> bool:
        return not self._body_widget.isVisible()

    def _toggle_collapsed(self) -> None:
        """Slot fuer Toggle-Button-Klick. Persistenz ueber Signal."""
        self.set_collapsed(not self.is_collapsed())
        self.collapse_changed.emit(self.is_collapsed())

    def set_visible_bands(self, bands: list, current_band: str | None = None) -> None:
        """P50 (v0.97.20): Welche Band-Buttons sind sichtbar?

        Versteckt Buttons + Prop-Bars für nicht-enthaltene Bänder.
        F1-Guarantee: ``current_band`` (falls gesetzt) bleibt immer
        sichtbar — auch wenn nicht in ``bands``. F2: Prop-Bars werden
        mitversteckt; `update_propagation()` respektiert die neue
        ``self._band_visible``-Map und blendet versteckte Bands nicht ein.

        Args:
            bands: Liste der sichtbaren Band-Strings (z.B. ["20m", "40m"]).
            current_band: Aktuelles Band — bleibt sichtbar (F1).
        """
        visible = set(bands)
        if current_band:
            visible.add(current_band)
        for b, btn in self.band_buttons.items():
            is_v = b in visible
            self._band_visible[b] = is_v
            btn.setVisible(is_v)
            bar = self.prop_bars.get(b)
            if bar is not None and not is_v:
                bar.setVisible(False)
                self._stop_pulse(b)

    def update_propagation(self, conditions: dict,
                           active_band: Optional[str] = None) -> None:
        """Propagations-Balken aktualisieren.

        conditions=None/leer → alle ausblenden.
        active_band: Wenn fuer dieses Band ein 60-min-Trend ansteht
        (cond_now != cond_60), pulsiert sein Balken weich zwischen den
        beiden Farben. Andere Baender bleiben statisch.
        """
        from core import propagation

        _COLORS = {
            "good": "#00CC00",
            "fair": "#FFAA00",
            "poor": "#CC0000",
            "grey": "#555555",
        }

        for band, bar in self.prop_bars.items():
            # P50: Versteckte Bänder bleiben unsichtbar — Propagation-Update darf
            # nicht heimlich die Bar wieder einblenden.
            if not self._band_visible.get(band, True):
                bar.setVisible(False)
                self._stop_pulse(band)
                continue
            if not conditions:
                bar.setVisible(False)
                self._stop_pulse(band)
                continue
            cond_now = conditions.get(band)
            if cond_now is None:
                bar.setVisible(False)
                self._stop_pulse(band)
                continue
            bar.setVisible(True)

            # nicht aktives Band oder unsichere Daten → statisch
            if band != active_band or cond_now == "grey":
                bar.set_color(QColor(_COLORS.get(cond_now, "#555555")))
                self._stop_pulse(band)
                continue

            # aktives Band — Trend pruefen
            cond_30_dict = propagation.get_conditions_at(30) or {}
            cond_60_dict = propagation.get_conditions_at(60) or {}
            cond_30 = cond_30_dict.get(band, cond_now)
            cond_60 = cond_60_dict.get(band, cond_now)

            if cond_now == cond_60 or cond_60 == "grey":
                bar.set_color(QColor(_COLORS[cond_now]))
                self._stop_pulse(band)
                continue

            fast = (cond_30 != cond_now and cond_30 == cond_60)
            new_state = (cond_now, cond_60, fast)
            if self._pulse.get(band, {}).get("state") == new_state:
                continue  # Animation laeuft bereits → kein Restart-Flacker

            self._stop_pulse(band)
            self._start_pulse(band, _COLORS[cond_now], _COLORS[cond_60], fast)
            self._pulse[band]["state"] = new_state

    def _start_pulse(self, band: str, hex_a: str, hex_b: str, fast: bool) -> None:
        """Endlose Cross-Fade-Animation a→b→a auf prop_bars[band]."""
        bar = self.prop_bars[band]
        fade = 500 if fast else 1000
        hold = 1500 if fast else 3000
        total = (hold + fade) * 2
        a = QColor(hex_a)
        b = QColor(hex_b)
        anim = QPropertyAnimation(bar, b"color", self)
        anim.setDuration(total)
        anim.setLoopCount(-1)
        anim.setEasingCurve(QEasingCurve.InOutSine)
        anim.setKeyValueAt(0.0, a)
        anim.setKeyValueAt(hold / total, a)
        anim.setKeyValueAt((hold + fade) / total, b)
        anim.setKeyValueAt((hold + fade + hold) / total, b)
        anim.setKeyValueAt(1.0, a)
        anim.start()
        self._pulse[band] = {"state": None, "anim": anim}

    def _stop_pulse(self, band: str) -> None:
        """Animation stoppen + entry aufraeumen (idempotent)."""
        entry = self._pulse.pop(band, None)
        if entry and entry.get("anim"):
            entry["anim"].stop()
            entry["anim"].deleteLater()


def _sep_line() -> QFrame:
    """Dünne Trennlinie innerhalb einer Kachel."""
    line = QFrame()
    line.setFrameShape(QFrame.Shape.HLine)
    line.setFixedHeight(1)
    line.setStyleSheet("background: rgba(255,255,255,0.08); border: none;")
    return line


class _AntenneCard(QFrame):
    """Kachel 2 (grün) — ANTENNE alleine (NORMAL/DIVERSITY/EINMESSEN + LED).

    P1.ANTENNE-COLLAPSE (v0.95.11): Body ist einklappbar via Toggle-Button
    im Header. State persistiert in Settings, wird vom MainWindow geladen.
    """

    collapse_changed = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("card")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(_CARD_SS_GREEN)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 8, 10, 8)
        lay.setSpacing(5)

        # ── Header-Row: Toggle-Button + ANTENNE-Label ─────────────────────
        header_row = QHBoxLayout()
        header_row.setContentsMargins(0, 0, 0, 0)
        header_row.setSpacing(6)

        self.toggle_btn = QPushButton("▼")
        self.toggle_btn.setFixedSize(20, 20)
        self.toggle_btn.setFlat(True)
        self.toggle_btn.setStyleSheet(
            "QPushButton { background: transparent; color: #55BBAA; "
            "border: none; font-size: 11px; font-weight: bold; padding: 0; }"
            "QPushButton:hover { color: #88EECC; }"
        )
        self.toggle_btn.setToolTip("Antennen-Kachel ein-/ausklappen")
        self.toggle_btn.clicked.connect(self._toggle_collapsed)
        header_row.addWidget(self.toggle_btn)

        lbl_ant = QLabel("ANTENNE")
        lbl_ant.setStyleSheet(f"color: #55BBAA; font-size: 10px; font-family: {_FONT}; font-weight: bold;")
        header_row.addWidget(lbl_ant)
        header_row.addStretch()
        lay.addLayout(header_row)

        # ── Body-Container (einklappbar) ──────────────────────────────────
        self._body_widget = QWidget()
        body_lay = QVBoxLayout(self._body_widget)
        body_lay.setContentsMargins(0, 0, 0, 0)  # KP-8: keine doppelten Margins
        body_lay.setSpacing(5)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(4)
        self.btn_normal = QPushButton("NORMAL")
        self.btn_normal.setFixedHeight(28)
        self.btn_diversity = QPushButton("DIVERSITY")
        self.btn_diversity.setFixedHeight(28)
        self.btn_einmessen = QPushButton("KALIBRIEREN")
        self.btn_einmessen.setFixedHeight(28)
        self.btn_einmessen.setStyleSheet(
            "QPushButton { background: rgba(60,140,60,0.25); color: #88CC88; "
            "border: 1px solid rgba(80,180,80,0.4); border-radius: 4px; "
            "font-size: 11px; font-weight: bold; padding: 0 10px; }"
            "QPushButton:hover { background: rgba(80,160,80,0.35); }"
        )
        btn_row.addWidget(self.btn_normal)
        btn_row.addWidget(self.btn_diversity)
        btn_row.addWidget(self.btn_einmessen)
        body_lay.addLayout(btn_row)

        self.dx_info = QLabel("")
        self.dx_info.setStyleSheet(f"color: #668877; font-size: 10px; font-family: {_FONT};")
        body_lay.addWidget(self.dx_info)

        # Diversity Ratio Display
        self._div_widget = QWidget()
        div_lay = QVBoxLayout(self._div_widget)
        div_lay.setContentsMargins(0, 0, 0, 2)
        div_lay.setSpacing(1)
        ratio_row = QHBoxLayout()
        ratio_row.setSpacing(3)
        lbl_a1 = QLabel("ANT1")
        lbl_a1.setStyleSheet(f"color:{_LED_GREEN};font-size:10px;font-family:{_FONT};font-weight:bold;")
        ratio_row.addWidget(lbl_a1)
        ratio_row.addSpacing(4)
        self._a1_pct = {}
        for pct in ("70%", "50%", "30%"):
            lbl = QLabel(pct)
            lbl.setMinimumWidth(30)
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet(_DIV_PCT_OFF)
            ratio_row.addWidget(lbl)
            self._a1_pct[pct] = lbl
        ratio_row.addSpacing(6)
        self._a1_count_label = QLabel("")
        self._a1_count_label.setStyleSheet(
            f"color:{_LED_GREEN};font-size:9px;font-family:{_FONT};font-weight:bold;"
        )
        self._a1_count_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        ratio_row.addWidget(self._a1_count_label)
        self._a2_count_label = QLabel("")
        self._a2_count_label.setStyleSheet(
            f"color:{_LED_BLUE};font-size:9px;font-family:{_FONT};font-weight:bold;"
        )
        self._a2_count_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        ratio_row.addWidget(self._a2_count_label)
        ratio_row.addSpacing(6)
        self._a2_pct = {}
        for pct in ("30%", "50%", "70%"):
            lbl = QLabel(pct)
            lbl.setMinimumWidth(30)
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet(_DIV_PCT_OFF)
            ratio_row.addWidget(lbl)
            self._a2_pct[pct] = lbl
        ratio_row.addSpacing(4)
        lbl_a2 = QLabel("ANT2")
        lbl_a2.setStyleSheet(f"color:{_LED_BLUE};font-size:10px;font-family:{_FONT};font-weight:bold;")
        ratio_row.addWidget(lbl_a2)
        div_lay.addLayout(ratio_row)
        phase_row = QHBoxLayout()
        phase_row.setContentsMargins(0, 0, 0, 0)
        self._phase_label = QLabel("")
        self._phase_label.setStyleSheet(
            f"color:#FFCC00;font-size:9px;font-family:{_FONT};font-style:italic;"
        )
        self._phase_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        phase_row.addWidget(self._phase_label)
        div_lay.addLayout(phase_row)
        self._div_widget.setVisible(False)
        body_lay.addWidget(self._div_widget)

        # Frequenz-Histogramm (nur nach Einmessen sichtbar)
        self._freq_hist = FrequencyHistogramWidget(self)
        self._freq_hist.setVisible(False)
        body_lay.addWidget(self._freq_hist)

        # TX-Freq Manuell-Eingabe (nur Normal-Modus sichtbar) — Spinbox + Pfeile
        # Klick im Histogramm uebernimmt Wert hier rein, User kann manuell feintunen.
        self._tx_freq_row = QWidget()
        _tx_lay = QHBoxLayout(self._tx_freq_row)
        _tx_lay.setContentsMargins(2, 2, 2, 2)
        _tx_lay.setSpacing(6)
        _tx_lbl = QLabel("TX-Freq:")
        _tx_lbl.setStyleSheet(f"color:#CCCCCC;font-family:{_FONT};font-size:10px;")
        _tx_lay.addWidget(_tx_lbl)
        self._tx_freq_spin = QSpinBox()
        self._tx_freq_spin.setRange(150, 2800)
        self._tx_freq_spin.setSingleStep(50)
        self._tx_freq_spin.setValue(1500)
        self._tx_freq_spin.setSuffix(" Hz")
        self._tx_freq_spin.setFixedWidth(110)
        self._tx_freq_spin.setStyleSheet(
            f"QSpinBox {{ background:#0a0a14; color:#FFD700; "
            f"border:1px solid #444; border-radius:3px; padding:2px 4px; "
            f"font-family:{_FONT}; font-size:11px; font-weight:bold; }}"
            # P1.22: Spinbox-Pfeile deutlich sichtbar (waren nur 2 gelbe Punkte)
            "QSpinBox::up-button { "
            "subcontrol-origin: border; subcontrol-position: top right; "
            "width: 20px; background: #2a2a3a; border-left: 1px solid #555; "
            "border-top-right-radius: 3px; "
            "} "
            "QSpinBox::down-button { "
            "subcontrol-origin: border; subcontrol-position: bottom right; "
            "width: 20px; background: #2a2a3a; border-left: 1px solid #555; "
            "border-bottom-right-radius: 3px; "
            "} "
            "QSpinBox::up-button:hover, QSpinBox::down-button:hover { "
            "background: #3a3a5a; "
            "} "
            "QSpinBox::up-arrow { width: 10px; height: 10px; } "
            "QSpinBox::down-arrow { width: 10px; height: 10px; } "
        )
        _tx_lay.addWidget(self._tx_freq_spin)
        _tx_lay.addStretch()
        self._tx_freq_row.setVisible(False)
        body_lay.addWidget(self._tx_freq_row)

        # CQ-Freq Countdown: Label + Balken in einer Zeile (horizontal)
        cq_row_layout = QHBoxLayout()
        cq_row_layout.setContentsMargins(2, 1, 2, 1)
        cq_row_layout.setSpacing(6)
        self._cq_freq_lbl = QLabel("Prüfe nächste freie TX Frequenz in: -- Sek.")
        self._cq_freq_lbl.setStyleSheet(
            f"color:#882222;font-size:9px;font-family:{_FONT};font-style:italic;"
        )
        cq_row_layout.addWidget(self._cq_freq_lbl)
        self._cq_freq_bar = QProgressBar()
        self._cq_freq_bar.setRange(0, 60)
        self._cq_freq_bar.setValue(60)
        self._cq_freq_bar.setTextVisible(False)
        self._cq_freq_bar.setFixedHeight(6)
        self._cq_freq_bar.setStyleSheet(
            "QProgressBar { border: none; border-radius: 2px; background: #1a1010; }"
            "QProgressBar::chunk { background: #882222; border-radius: 2px; }"
        )
        cq_row_layout.addWidget(self._cq_freq_bar, stretch=1)
        self._cq_row = QWidget()
        self._cq_row.setLayout(cq_row_layout)
        self._cq_row.setVisible(False)
        body_lay.addWidget(self._cq_row)

        # ── Body-Container an Card-Layout anhängen ────────────────────────
        lay.addWidget(self._body_widget)

    # ── Collapse-API ─────────────────────────────────────────────────────
    def set_collapsed(self, collapsed: bool) -> None:
        """Body aus-/einklappen. Setzt Toggle-Icon + MaximumHeight.

        Programm-API — emitiert KEIN collapse_changed-Signal (Init-Loop-
        Schutz). User-Klick geht über _toggle_collapsed.
        """
        self._body_widget.setVisible(not collapsed)
        self.toggle_btn.setText("▶" if collapsed else "▼")
        if collapsed:
            self.setMaximumHeight(36)  # Header-Höhe + Margins
        else:
            self.setMaximumHeight(_QWIDGETSIZE_MAX)

    def is_collapsed(self) -> bool:
        return not self._body_widget.isVisible()

    def _toggle_collapsed(self) -> None:
        """Slot für Toggle-Button-Klick. Persistenz über Signal."""
        self.set_collapsed(not self.is_collapsed())
        self.collapse_changed.emit(self.is_collapsed())


class _RadioCard(QFrame):
    """Kachel 3 (türkis) — RADIO Controls (PSK, Freq, Power, TUNE, ALC, TX).

    P1.COLLAPSE-RADIO-MODEBAND (v0.95.17): Body ist einklappbar via
    Toggle-Button im Header. State persistiert in Settings, wird vom
    MainWindow geladen.
    """

    collapse_changed = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("card")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(_CARD_SS_TEAL)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 8, 10, 8)
        lay.setSpacing(5)

        # ── Header-Row: Toggle-Button + RADIO-Label ──────────────────────
        header_row = QHBoxLayout()
        header_row.setContentsMargins(0, 0, 0, 0)
        header_row.setSpacing(6)

        self.toggle_btn = QPushButton("▼")
        self.toggle_btn.setFixedSize(20, 20)
        self.toggle_btn.setFlat(True)
        self.toggle_btn.setStyleSheet(
            "QPushButton { background: transparent; color: #00aacc; "
            "border: none; font-size: 11px; font-weight: bold; padding: 0; }"
            "QPushButton:hover { color: #44CCEE; }"
        )
        self.toggle_btn.setToolTip("Radio-Kachel ein-/ausklappen")
        self.toggle_btn.clicked.connect(self._toggle_collapsed)
        header_row.addWidget(self.toggle_btn)

        lbl_radio = QLabel("RADIO")
        lbl_radio.setStyleSheet(
            f"color: #00aacc; font-size: 10px; font-family: {_FONT}; font-weight: bold;"
        )
        header_row.addWidget(lbl_radio)
        header_row.addStretch()
        lay.addLayout(header_row)

        # ── Body-Container (einklappbar) ─────────────────────────────────
        self._body_widget = QWidget()
        body_lay = QVBoxLayout(self._body_widget)
        body_lay.setContentsMargins(0, 0, 0, 0)
        body_lay.setSpacing(5)

        _SEP_SS = "background: #445544; max-height: 1px; min-height: 1px;"

        # ── Sektion 1: PSK Info + Map ─────────────────────────
        psk_frame = QFrame()
        psk_frame.setStyleSheet(
            "QFrame { background: rgba(255,255,255,0.02); border: 1px solid #3a3a4a; "
            "border-radius: 3px; }")
        psk_inner = QHBoxLayout(psk_frame)
        psk_inner.setContentsMargins(6, 4, 4, 4)
        psk_inner.setSpacing(4)
        self.psk_label = QLabel("PSK:  —")
        self.psk_label.setStyleSheet(f"color: #00CC88; font-family: {_FONT}; font-size: 10px; border: none;")
        self.psk_label.setWordWrap(True)
        self.psk_label.setMinimumHeight(16)
        self.btn_psk_map = QPushButton("Map")
        self.btn_psk_map.setFixedHeight(22)
        self.btn_psk_map.setFixedWidth(40)
        self.btn_psk_map.setStyleSheet(
            "QPushButton { background: rgba(0,150,100,0.2); color: #00CCAA; "
            "border: 1px solid rgba(0,180,130,0.4); border-radius: 2px; font-size: 10px; }"
            "QPushButton:hover { background: rgba(0,170,120,0.3); }"
        )
        psk_inner.addWidget(self.psk_label, 1)
        psk_inner.addWidget(self.btn_psk_map, 0, Qt.AlignmentFlag.AlignTop)
        body_lay.addWidget(psk_frame)

        # ── Sektion 2: Power Buttons ──────────────────────────
        _PRESETS = [
            (10,  "#007733", "#00BB55"), (20,  "#00AA44", "#00FF66"),
            (30,  "#22AA44", "#44EE66"), (40,  "#668800", "#99CC00"),
            (50,  "#AA8800", "#DDCC00"), (60,  "#CC7700", "#FFAA00"),
            (70,  "#CC7700", "#FFAA00"), (80,  "#CC4400", "#FF6622"),
            (90,  "#CC2222", "#FF4444"), (100, "#AA0000", "#FF2222"),
        ]
        self.power_buttons = {}
        self._power_btn_group = QButtonGroup(self)
        self._power_btn_group.setExclusive(True)
        power_row = QHBoxLayout()
        power_row.setSpacing(1)
        for watts, active_bg, active_border in _PRESETS:
            btn = QPushButton(f"{watts}")
            btn.setCheckable(True)
            btn.setFixedHeight(22)
            btn.setStyleSheet(
                f"QPushButton {{ background: rgba(40,40,40,0.8); color: #999; "
                f"border: 1px solid #444; border-radius: 2px; "
                f"font-size: 9px; font-family: {_FONT}; font-weight: bold; padding: 0 1px; }}"
                f"QPushButton:checked {{ background: {active_bg}; color: white; border-color: {active_border}; }}"
                f"QPushButton:hover {{ background: rgba(60,60,60,0.8); color: #CCC; }}"
            )
            self.power_buttons[watts] = btn
            self._power_btn_group.addButton(btn)
            power_row.addWidget(btn)
        body_lay.addLayout(power_row)

        # ── Sektion 3: TX Status (gerahmt) ────────────────────
        from PySide6.QtWidgets import QProgressBar
        tx_frame = QFrame()
        tx_frame.setStyleSheet(
            "QFrame { border: 1px solid #446644; border-radius: 4px; "
            "background: rgba(0,60,30,0.08); }"
        )
        tx_lay = QVBoxLayout(tx_frame)
        tx_lay.setContentsMargins(6, 5, 6, 5)
        tx_lay.setSpacing(4)

        # Zeile 1: Antennensignal — Clipschutz | TX-Pegel | RF
        _lbl_ss = (f"font-family: {_FONT}; font-size: 10px; "
                   f"border: 1px solid #333; border-radius: 2px; padding: 1px 4px;")
        signal_row = QHBoxLayout()
        signal_row.setSpacing(6)
        self.peak_label = QLabel("Clipschutz —")
        self.peak_label.setFixedWidth(100)
        self.peak_label.setStyleSheet(f"color: #557766; " + _lbl_ss)
        self.tx_level_label = QLabel("TX-Pegel: 75%")
        self.tx_level_label.setFixedWidth(90)
        self.tx_level_label.setStyleSheet(f"color: #AAAACC; " + _lbl_ss)
        self.rf_power_label = QLabel("RF: —")
        self.rf_power_label.setFixedWidth(70)
        self.rf_power_label.setStyleSheet(f"color: #FFAA44; " + _lbl_ss)
        # tx_level_bar bleibt als Dummy erhalten (wird intern noch referenziert)
        self.tx_level_bar = QProgressBar()
        self.tx_level_bar.setVisible(False)
        signal_row.addWidget(self.peak_label)
        signal_row.addStretch()
        signal_row.addWidget(self.tx_level_label)
        signal_row.addStretch()
        signal_row.addWidget(self.rf_power_label)
        tx_lay.addLayout(signal_row)

        # Zeile 2: Ausgangsleistung — [TUNE] --- [Watt  SWR]
        output_row = QHBoxLayout()
        output_row.setSpacing(8)
        # TUNE als deutlich erkennbarer Button (raised, heller Hintergrund)
        self.btn_tune = QPushButton("TUNE")
        self.btn_tune.setCheckable(True)
        self.btn_tune.setFixedHeight(28)
        self.btn_tune.setFixedWidth(60)
        self.btn_tune.setStyleSheet(
            f"QPushButton {{ background: #2a2a00; color: #FFD700; "
            f"border: 2px solid #998800; border-radius: 5px; "
            f"font-weight: bold; font-family: {_FONT}; font-size: 11px; "
            f"padding: 2px 6px; }}"
            f"QPushButton:hover {{ background: #444400; border-color: #FFD700; color: #FFFF00; }}"
            f"QPushButton:pressed {{ background: #666600; }}"
            f"QPushButton:checked {{ background: #998800; color: #000; border-color: #FFD700; }}"
        )
        # Watt + SWR direkt nebeneinander (Anzeigen, kein Button)
        self.watt_label = QLabel("0 W")
        self.watt_label.setFixedHeight(28)
        self.watt_label.setStyleSheet(
            f"color: #FFD700; font-family: {_FONT}; font-size: 14px; font-weight: bold; border: none;")
        self.swr_label = QLabel("SWR —")
        self.swr_label.setFixedWidth(75)
        self.swr_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.swr_label.setStyleSheet(
            f"color: #44FF44; font-family: {_FONT}; font-size: 10px; "
            f"font-weight: bold; border: 1px solid #333; border-radius: 2px; padding: 1px 4px;")
        output_row.addWidget(self.btn_tune)
        output_row.addStretch()          # Abstand zwischen TUNE und Anzeigen
        output_row.addWidget(self.watt_label)
        output_row.addSpacing(8)
        output_row.addWidget(self.swr_label)
        tx_lay.addLayout(output_row)

        body_lay.addWidget(tx_frame)

        # ── Body-Container an Card-Layout anhaengen ──────────────────────
        lay.addWidget(self._body_widget)

    # ── Collapse-API ─────────────────────────────────────────────────────
    def set_collapsed(self, collapsed: bool) -> None:
        """Body aus-/einklappen. Setzt Toggle-Icon + MaximumHeight.

        Programm-API — emitiert KEIN collapse_changed-Signal (Init-Loop-
        Schutz). User-Klick geht ueber _toggle_collapsed.
        """
        self._body_widget.setVisible(not collapsed)
        self.toggle_btn.setText("▶" if collapsed else "▼")
        if collapsed:
            self.setMaximumHeight(36)
        else:
            self.setMaximumHeight(_QWIDGETSIZE_MAX)

    def is_collapsed(self) -> bool:
        return not self._body_widget.isVisible()

    def _toggle_collapsed(self) -> None:
        """Slot fuer Toggle-Button-Klick. Persistenz ueber Signal."""
        self.set_collapsed(not self.is_collapsed())
        self.collapse_changed.emit(self.is_collapsed())


class _QSOStatusCard(QFrame):
    """Kachel 3 (orange) — QSO + STATUS + Settings."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("card")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(_CARD_SS_ORANGE)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(6, 10, 6, 4)
        lay.setSpacing(3)

        # ── QSO ──────────────────────────────────────────────────
        lbl_qso = QLabel("QSO")
        lbl_qso.setStyleSheet(f"color: #CC9944; font-size: 10px; font-family: {_FONT}; font-weight: bold;")
        lay.addWidget(lbl_qso)

        rxtx_row = QHBoxLayout()
        rxtx_row.setSpacing(4)
        self.rx_indicator = QLabel("● RX")
        self.rx_indicator.setStyleSheet(f"color: #44FF44; font-size: 12px; font-weight: bold; font-family: {_FONT};")
        self.tx_indicator = QLabel("○ TX")
        self.tx_indicator.setStyleSheet(f"color: #666; font-size: 12px; font-weight: bold; font-family: {_FONT};")
        rxtx_row.addWidget(self.rx_indicator)
        rxtx_row.addWidget(self.tx_indicator)
        rxtx_row.addStretch()
        lay.addLayout(rxtx_row)

        # 3-Button-Layout (v0.75): CQ RUFEN immer sichtbar, OMNI CQ + AUTO HUNT
        # nur via Easter-Egg-Toggle (Klick auf Versionsnummer). TUNE-Button ist
        # SEPARAT und gehoert NICHT zur QButtonGroup — eigene setEnabled-Steuerung.
        _mode_btn_style = (
            f"QPushButton {{ background: rgba(120,0,0,0.45); color: #CC8888; "
            f"border: 1px solid rgba(180,50,50,0.5); border-radius: 5px; "
            f"font-size: 12px; font-weight: bold; font-family: {_FONT}; }}"
            f"QPushButton:checked {{ background: rgba(200,0,0,0.7); color: #FFD700; "
            f"border-color: rgba(255,180,0,0.7); }}"
            f"QPushButton:hover {{ background: rgba(140,0,0,0.5); color: white; }}"
            f"QPushButton:disabled {{ background: #2a2a2a; color: #666666; "
            f"border: 1px solid #444444; }}"
        )

        self.btn_cq = QPushButton("CQ RUFEN")
        self.btn_cq.setCheckable(True)
        self.btn_cq.setFixedHeight(26)
        self.btn_cq.setStyleSheet(_mode_btn_style)

        self.btn_omni_cq = QPushButton("OMNI CQ")
        self.btn_omni_cq.setCheckable(True)
        self.btn_omni_cq.setFixedHeight(26)
        # 11.05.2026 Mike: OMNI-CQ inaktiv = dunkelrot, aktiv = grün.
        # Eigener Style, damit Mike auf einen Blick sieht ob OMNI an ist.
        _omni_btn_style = (
            f"QPushButton {{ background: rgba(80,0,0,0.55); color: #AA6666; "
            f"border: 1px solid rgba(150,40,40,0.5); border-radius: 5px; "
            f"font-size: 12px; font-weight: bold; font-family: {_FONT}; }}"
            f"QPushButton:checked {{ background: rgba(0,150,0,0.75); color: #FFFFFF; "
            f"border-color: rgba(0,220,0,0.75); }}"
            f"QPushButton:hover {{ background: rgba(110,20,20,0.6); color: #DDD; }}"
            f"QPushButton:checked:hover {{ background: rgba(0,180,0,0.85); color: #FFFFFF; }}"
            f"QPushButton:disabled {{ background: #2a2a2a; color: #666666; "
            f"border: 1px solid #444444; }}"
        )
        self.btn_omni_cq.setStyleSheet(_omni_btn_style)
        self.btn_omni_cq.hide()  # nur via Easter-Egg sichtbar

        self.btn_auto_hunt = QPushButton("AUTO HUNT")
        self.btn_auto_hunt.setCheckable(True)
        self.btn_auto_hunt.setFixedHeight(26)
        self.btn_auto_hunt.setStyleSheet(_mode_btn_style)
        self.btn_auto_hunt.hide()  # nur via Easter-Egg sichtbar

        # Mutually exclusive zwischen OMNI ↔ Auto-Hunt: in main_window.py
        # _on_btn_omni_cq_toggled + _on_btn_auto_hunt_toggled mit "superseded"-
        # Reason. setExclusive(False) damit jeder Button durch Re-Klick
        # DESELEKTIERT werden kann (Qt-Default bei exclusive=True verhindert
        # das — Bug v0.75: CQ-Toggle stuck on, Stats silent blockiert).
        # btn_cq und Diversity-Buttons nie gleichzeitig sichtbar (mode-coupled).
        self.mode_button_group = QButtonGroup(self)
        self.mode_button_group.setExclusive(False)
        self.mode_button_group.addButton(self.btn_cq)
        self.mode_button_group.addButton(self.btn_omni_cq)
        self.mode_button_group.addButton(self.btn_auto_hunt)

        mode_row = QHBoxLayout()
        mode_row.setSpacing(4)
        mode_row.addWidget(self.btn_cq)
        mode_row.addWidget(self.btn_omni_cq)
        mode_row.addWidget(self.btn_auto_hunt)
        lay.addLayout(mode_row)

        # Operator Presence Balken (Totmannschalter)
        # Fest 15 Min, nicht konfigurierbar, gesetzliche Pflicht (DE)
        self.presence_bar = QProgressBar()
        self.presence_bar.setRange(0, 900)  # 900 Sekunden = 15 Min
        self.presence_bar.setValue(900)
        self.presence_bar.setFixedHeight(4)
        self.presence_bar.setTextVisible(False)
        self.presence_bar.setStyleSheet("""
            QProgressBar { background: #1a1a1a; border: none; border-radius: 1px; }
            QProgressBar::chunk { background: #00AA00; border-radius: 1px; }
        """)
        self.presence_bar.setToolTip("Operator Presence — 15 Min Timeout")
        lay.addWidget(self.presence_bar)

        self.qso_counter_label = QLabel("")
        self.qso_counter_label.setStyleSheet(
            f"color: #88CC66; font-family: {_FONT}; font-size: 10px; font-weight: bold;"
        )
        self.qso_counter_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.qso_counter_label.setVisible(False)
        lay.addWidget(self.qso_counter_label)

        # Weiter + Abbrechen nebeneinander
        adv_row = QHBoxLayout()
        adv_row.setSpacing(4)
        self.btn_advance = QPushButton("QSO Finish")
        self.btn_advance.setFixedHeight(22)
        self.btn_advance.setStyleSheet(
            "QPushButton { background: rgba(0,100,0,0.35); color: #88CC88; "
            "border: 1px solid rgba(0,150,0,0.4); border-radius: 4px; "
            "padding: 2px; font-size: 11px; font-weight: bold; }"
            "QPushButton:hover { background: rgba(0,130,0,0.45); }"
            "QPushButton:disabled { background: #2a2a2a; color: #666666; border-color: #444444; }"
        )
        self.btn_advance.setToolTip(
            "Sendet manuell den nächsten QSO-Schritt "
            "(R+Report / RR73 / 73 — je nach Phase). "
            "Nutze bei stuck-Gegenstation."
        )
        self.btn_advance.setEnabled(False)
        self.btn_cancel = QPushButton("HALT")
        self.btn_cancel.setFixedHeight(22)
        self.btn_cancel.setStyleSheet(
            f"QPushButton {{ background: rgba(180,0,0,0.4); color: #FF4444; "
            f"border: 1px solid rgba(220,40,40,0.6); border-radius: 4px; padding: 2px; "
            f"font-size: 11px; font-weight: bold; font-family: {_FONT}; }}"
            f"QPushButton:hover {{ background: rgba(220,0,0,0.6); color: #FF6666; }}"
            f"QPushButton:disabled {{ background: #2a2a2a; color: #666666; border: 1px solid #444444; }}"
        )
        adv_row.addWidget(self.btn_advance)
        adv_row.addWidget(self.btn_cancel)
        lay.addLayout(adv_row)

        lay.addWidget(_sep_line())

        # ── STATUS ────────────────────────────────────────────────
        lbl_status = QLabel("STATUS")
        # P1.22: minimal groesser fuer Lesbarkeit
        lbl_status.setStyleSheet(f"color: #CC9944; font-size: 11px; font-family: {_FONT}; font-weight: bold;")
        lay.addWidget(lbl_status)

        # P1.23: RADIO/Decode/Empfangsqualitaet einheitlich 10px (matcht Status
        # darunter, wirkt vertikal enger ohne Layout-Eingriff).
        self.connection_label = QLabel()
        self.connection_label.setTextFormat(Qt.TextFormat.RichText)
        self.connection_label.setStyleSheet(
            f"font-family: {_FONT}; font-size: 10px;"
        )
        self.connection_label.setText(
            f'<span style="color:{_TEXT};">RADIO: </span>'
            f'<span style="color:#888;">Suche...</span>'
        )
        lay.addWidget(self.connection_label)

        self.decode_label = QLabel()
        self.decode_label.setTextFormat(Qt.TextFormat.RichText)
        self.decode_label.setStyleSheet(
            f"font-family: {_FONT}; font-size: 10px;"
        )
        self.decode_label.setText(
            f'<span style="color:{_TEXT};">Decode: </span>'
            f'<span style="color:#666;">—</span>'
        )
        lay.addWidget(self.decode_label)

        # P1.19/P1.21/P1.22/P1.23: `Lokale Empfangsqualität: ★★★☆☆` + UTC rechts
        snr_utc_row = QHBoxLayout()
        snr_utc_row.setSpacing(4)
        self._empfang_label = QLabel("Lokale Empfangsqualität: ")
        self._empfang_label.setStyleSheet(
            f"color: {_TEXT}; font-family: {_FONT}; font-size: 10px;"
        )
        self.conditions_widget = StarsConditionWidget()
        self.utc_label = QLabel("UTC: --:--:--")
        self.utc_label.setStyleSheet(f"color: {_TEXT}; font-family: {_FONT}; font-size: 10px;")
        snr_utc_row.addWidget(self._empfang_label)
        snr_utc_row.addWidget(self.conditions_widget)
        snr_utc_row.addStretch()
        snr_utc_row.addWidget(self.utc_label)
        lay.addLayout(snr_utc_row)

        self._last_state = "IDLE"
        self.state_label = QLabel("Status: IDLE")
        self.state_label.setStyleSheet(f"color: #776644; font-family: {_FONT}; font-size: 10px;")
        lay.addWidget(self.state_label)

        self.cycle_bar = QLabel("")
        self.cycle_bar.setStyleSheet(
            "background: rgba(255,255,255,0.04); border: 1px solid rgba(255,170,50,0.2); "
            "border-radius: 3px; padding: 2px;"
        )
        self.cycle_bar.setFixedHeight(18)
        lay.addWidget(self.cycle_bar)

        lay.addWidget(_sep_line())

        # ── Settings ──────────────────────────────────────────────
        self.btn_settings = QPushButton("Einstellungen")
        self.btn_settings.setFixedHeight(24)
        self.btn_settings.setStyleSheet(
            "QPushButton { background: rgba(255,255,255,0.06); color: #AA8844; "
            "border: 1px solid rgba(180,130,50,0.3); border-radius: 3px; font-size: 11px; }"
            "QPushButton:hover { background: rgba(255,255,255,0.1); color: #FFBB66; }"
        )
        lay.addWidget(self.btn_settings)


class ControlPanel(QWidget):
    """Control-Fenster — Modus, Band, Frequenz, Power, Status.

    Signals:
        mode_changed: (str) — "FT8" oder "FT4"
        band_changed: (str) — z.B. "20m"
        power_changed: (int) — Leistung in Prozent (0-100)
        auto_toggled: (bool) — Auto-Modus an/aus
        advance_clicked: () — Naechster QSO-Schritt (manuell)
        cancel_clicked: () — QSO abbrechen
        cq_clicked: () — CQ-Modus starten/stoppen
        tune_clicked: (bool)
        tx_level_changed: (int)
        rx_mode_changed: (str) — "normal", "diversity"
        settings_clicked: ()
        bias_changed: (str) — Diversity-Bias Preset
        einmessen_clicked: ()
    """

    # ── Signals ──────────────────────────────────────────────────────────
    mode_changed = Signal(str)
    band_changed = Signal(str)
    power_changed = Signal(int)
    advance_clicked = Signal()
    cancel_clicked = Signal()
    cq_clicked = Signal()
    tune_clicked = Signal(bool)
    dx_preset_changed = Signal(str)
    tx_level_changed = Signal(int)
    preamp_changed = Signal(bool)           # Legacy, nicht mehr genutzt
    easter_egg_toggle_clicked = Signal()   # Easter Egg: Klick auf Versionsnummer
    rx_mode_changed = Signal(str)
    settings_clicked = Signal()
    einmessen_clicked = Signal()
    map_clicked = Signal()  # Map-Button im PSK-Frame → MainWindow.open_direction_map
    antenne_collapse_changed = Signal(bool)  # P1.ANTENNE-COLLAPSE → MainWindow
    modeband_collapse_changed = Signal(bool)  # P1.COLLAPSE-RADIO-MODEBAND → MainWindow
    radio_collapse_changed = Signal(bool)     # P1.COLLAPSE-RADIO-MODEBAND → MainWindow

    # ── Klassen-Konstanten ───────────────────────────────────────────────
    _RX_MODES = ["normal", "diversity"]
    _RX_STYLE_ACTIVE = "background: #0055AA; color: white; border-color: #0077CC; font-weight: bold;"
    _RX_STYLE_INACTIVE = "background: #222; color: #AAA; border-color: #555;"
    _RX_STYLE_DIVERSITY_ACTIVE = "background: #003344; color: #00CCFF; border-color: #00AADD; font-weight: bold;"


    # =====================================================================
    # Init
    # =====================================================================
    def __init__(self, callsign: str = "DA1MHH"):
        super().__init__()
        self._current_mode = "FT8"
        self._current_band = "20m"
        self._rx_mode_idx = 0
        self._callsign = callsign
        self._current_rx_mode = "normal"
        self.setMinimumWidth(_MIN_WIDTH)
        self.setAutoFillBackground(True)
        self.setStyleSheet("ControlPanel { background-color: #06060c; color: #CCC; font-family: Menlo; }")
        self._setup_ui()
        # Initial: Normal-Modus → Histogramm klickbar, Spinbox sichtbar.
        # _apply_rx_mode_visibility braucht _setup_ui (UI-Elemente muessen existieren).
        self._apply_rx_mode_visibility(is_div=False)
        self._start_clock()

    # =====================================================================
    # UI Setup
    # =====================================================================
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # ── Kachel 1: MODUS + BAND (blau) ───────────────────────────────
        mb_card = _ModeBandCard(self)
        self._mode_band_card = mb_card          # für update_propagation
        self._modeband_card = mb_card  # P1.COLLAPSE-RADIO-MODEBAND: expose for MainWindow init
        self.btn_ft8 = mb_card.btn_ft8
        self.btn_ft4 = mb_card.btn_ft4
        self.btn_ft2 = mb_card.btn_ft2
        self.band_buttons = mb_card.band_buttons
        self.freq_label = mb_card.freq_label
        mb_card.btn_ft8.clicked.connect(lambda: self._set_mode("FT8"))
        mb_card.btn_ft4.clicked.connect(lambda: self._set_mode("FT4"))
        mb_card.btn_ft2.clicked.connect(lambda: self._set_mode("FT2"))
        for band, btn in mb_card.band_buttons.items():
            btn.clicked.connect(lambda checked, b=band: self._set_band(b))
        # P1.COLLAPSE-RADIO-MODEBAND: Toggle-Signal forwarden
        mb_card.collapse_changed.connect(self.modeband_collapse_changed.emit)
        layout.addWidget(mb_card)

        # ── Kachel 2: ANTENNE (grün) ─────────────────────────────────────
        ant_card = _AntenneCard(self)
        self._ant_card = ant_card  # KP-7: Expose für MainWindow-Collapse-Init
        self.btn_normal = ant_card.btn_normal
        self.btn_diversity = ant_card.btn_diversity
        self.btn_einmessen = ant_card.btn_einmessen
        self.dx_info = ant_card.dx_info
        self._div_widget = ant_card._div_widget
        self._a1_pct = ant_card._a1_pct
        self._a2_pct = ant_card._a2_pct
        self._phase_label = ant_card._phase_label
        self._a1_count_label = ant_card._a1_count_label
        self._a2_count_label = ant_card._a2_count_label
        self._freq_hist = ant_card._freq_hist
        self._cq_freq_lbl = ant_card._cq_freq_lbl
        self._cq_freq_bar = ant_card._cq_freq_bar
        self._cq_row = ant_card._cq_row
        # Manuelle TX-Freq-Eingabe (Normal-Modus)
        self._tx_freq_row = ant_card._tx_freq_row
        self._tx_freq_spin = ant_card._tx_freq_spin
        self.btn_normal.setStyleSheet(self._rx_btn_style(self._RX_STYLE_ACTIVE))
        self.btn_diversity.setStyleSheet(self._rx_btn_style(self._RX_STYLE_INACTIVE))
        self.btn_normal.clicked.connect(lambda: self._on_rx_mode_clicked("normal"))
        self.btn_diversity.clicked.connect(lambda: self._on_rx_mode_clicked("diversity"))
        self.btn_einmessen.clicked.connect(self.einmessen_clicked.emit)
        # P1.ANTENNE-COLLAPSE: Toggle-Signal forwarden für Settings-Persistenz
        ant_card.collapse_changed.connect(self.antenne_collapse_changed.emit)
        layout.addWidget(ant_card)

        # ── Kachel 3: RADIO (türkis) ─────────────────────────────────────
        radio_card = _RadioCard(self)
        self._radio_card = radio_card  # P1.COLLAPSE-RADIO-MODEBAND: expose for MainWindow init
        self.psk_label = radio_card.psk_label
        self.btn_psk_map = radio_card.btn_psk_map
        self.btn_psk_map.clicked.connect(self._open_psk_map)
        self.power_buttons = radio_card.power_buttons
        for watts, btn in self.power_buttons.items():
            btn.clicked.connect(lambda checked, w=watts: self._on_power_preset_clicked(w))
        # Default: 10W vorselektieren
        self.power_buttons[10].setChecked(True)
        self.btn_tune = radio_card.btn_tune
        self.btn_tune.clicked.connect(self._on_tune_clicked)
        self.watt_label = radio_card.watt_label
        self.swr_label = radio_card.swr_label
        self.peak_label = radio_card.peak_label
        self.tx_level_bar = radio_card.tx_level_bar
        self.tx_level_label = radio_card.tx_level_label
        self.rf_power_label = radio_card.rf_power_label
        # P1.COLLAPSE-RADIO-MODEBAND: Toggle-Signal forwarden
        radio_card.collapse_changed.connect(self.radio_collapse_changed.emit)
        layout.addWidget(radio_card)

        # ── Kachel 3: QSO + STATUS (orange) ─────────────────────────────
        qso_card = _QSOStatusCard(self)
        self.rx_indicator = qso_card.rx_indicator
        self.tx_indicator = qso_card.tx_indicator
        self.btn_cq = qso_card.btn_cq
        self.btn_cq.clicked.connect(self._on_cq_clicked)
        # v0.75: 3-Button-Layout — btn_omni_cq + btn_auto_hunt + ButtonGroup
        self.btn_omni_cq = qso_card.btn_omni_cq
        self.btn_auto_hunt = qso_card.btn_auto_hunt
        self.mode_button_group = qso_card.mode_button_group
        self.presence_bar = qso_card.presence_bar
        self.qso_counter_label = qso_card.qso_counter_label
        self.btn_advance = qso_card.btn_advance
        self.btn_advance.clicked.connect(self.advance_clicked.emit)
        self.btn_cancel = qso_card.btn_cancel
        self.btn_cancel.clicked.connect(self.cancel_clicked.emit)
        self.connection_label = qso_card.connection_label
        self.decode_label = qso_card.decode_label
        self.conditions_widget = qso_card.conditions_widget
        self.utc_label = qso_card.utc_label
        self.state_label = qso_card.state_label
        self._last_state = "IDLE"
        self.cycle_bar = qso_card.cycle_bar
        self.btn_settings = qso_card.btn_settings
        self.btn_settings.clicked.connect(self.settings_clicked.emit)
        layout.addWidget(qso_card)

        layout.addStretch()

        # ── Easter Egg: Versionsnummer (OMNI-TX Aktivierung) ────────────
        self._version_row = QHBoxLayout()
        self._version_row.setContentsMargins(0, 0, 4, 2)
        self._omni_active = False
        self._omni_symbol = QLabel("Ω")
        self._omni_symbol.setStyleSheet(
            f"color: #AA44FF; font-family: {_FONT}; font-size: 11px; "
            "padding: 0 3px; background: transparent; border: none;"
        )
        self._omni_symbol.setVisible(False)
        self._version_label = QLabel(f"SimpleFT8 v{APP_VERSION}")
        self._version_label.setStyleSheet(
            f"color: #666; font-family: {_FONT}; font-size: 10px; "
            "border: none; background: transparent;"
        )
        self._version_label.setCursor(Qt.CursorShape.PointingHandCursor)
        self._version_label.mousePressEvent = lambda e: self.easter_egg_toggle_clicked.emit()
        self._version_row.addStretch()
        self._version_row.addWidget(self._omni_symbol)
        self._version_row.addWidget(self._version_label)
        layout.addLayout(self._version_row)

    # =====================================================================
    # Helper: UI-Bausteine
    # =====================================================================
    def _group_label(self, text: str) -> QLabel:
        """Gruppenueberschrift — klein, gedimmt."""
        lbl = QLabel(text)
        lbl.setStyleSheet(
            f"color: #5588AA; font-size: 10px; font-family: {_FONT}; "
            f"font-weight: bold; padding-top: 2px; padding-bottom: 0px;"
        )
        return lbl

    def _separator(self) -> QFrame:
        """1px Trennlinie in #333."""
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFixedHeight(1)
        line.setStyleSheet(f"background: {_SEP_COLOR}; border: none;")
        return line

    def _band_btn(self, text: str, checked: bool = False) -> QPushButton:
        """Kompakter Band-Button."""
        btn = QPushButton(text)
        btn.setCheckable(True)
        btn.setChecked(checked)
        btn.setFixedHeight(22)
        btn.setStyleSheet(f"""
            QPushButton {{
                background-color: #2a2a3e; color: #AAA; border: 1px solid #444;
                border-radius: 3px; padding: 1px 2px; font-family: {_FONT};
                font-size: 10px; min-width: 24px;
            }}
            QPushButton:checked {{
                background-color: #0066AA; color: white; border-color: #00AAFF;
            }}
            QPushButton:hover {{ background-color: #333; }}
        """)
        return btn

    def _toggle_btn(self, text: str, checked: bool = False, width: int = 0) -> QPushButton:
        """Toggle-Button fuer Modus (FT8/FT4)."""
        btn = QPushButton(text)
        btn.setCheckable(True)
        btn.setChecked(checked)
        btn.setFixedHeight(24)
        if width:
            btn.setFixedWidth(width)
        btn.setStyleSheet(f"""
            QPushButton {{
                background-color: #2a2a3e; color: #AAA; border: 1px solid #444;
                border-radius: 4px; padding: 2px 8px; font-family: {_FONT};
                font-size: 11px; font-weight: bold;
            }}
            QPushButton:checked {{
                background-color: #0066AA; color: white; border-color: #00AAFF;
            }}
            QPushButton:hover {{ background-color: #333; }}
        """)
        return btn

    @staticmethod
    def _rx_btn_style(colors: str) -> str:
        """StyleSheet fuer NORMAL/DIVERSITY Buttons."""
        return (
            f"QPushButton {{ {colors} border-radius: 4px; font-size: 12px; "
            f"font-weight: bold; padding: 0 10px; border-width: 1px; border-style: solid; "
            f"min-height: 28px; }}"
            f"QPushButton:hover {{ background: #333; }}"
        )


    # =====================================================================
    # Modus / Band
    # =====================================================================
    def _set_mode(self, mode: str):
        self._current_mode = mode
        self.btn_ft8.setChecked(mode == "FT8")
        self.btn_ft4.setChecked(mode == "FT4")
        self.btn_ft2.setChecked(mode == "FT2")
        self._update_frequency()
        self.mode_changed.emit(mode)

    def _set_band(self, band: str):
        self._current_band = band
        for b, btn in self.band_buttons.items():
            btn.setChecked(b == band)
        # P50 (R1-F1): das aktuelle Band muss sichtbar sein, auch wenn
        # ein externer Aufrufer (Bandpilot, Auto-Hunt, Settings-Apply)
        # gerade ein vorher deaktiviertes Band gesetzt hat.
        if not self._mode_band_card._band_visible.get(band, True):
            self._mode_band_card._band_visible[band] = True
            btn = self.band_buttons.get(band)
            if btn is not None:
                btn.setVisible(True)
        self._update_frequency()
        self.band_changed.emit(band)

    def set_visible_bands(self, bands: list) -> None:
        """P50 (v0.97.20): Public-API für sichtbare Band-Buttons.

        Delegiert an ``_ModeBandCard.set_visible_bands`` mit
        ``current_band``-Guarantee (R1-F1). Caller (MainWindow) ruft
        nach Settings-Load und nach Settings-Apply.
        """
        self._mode_band_card.set_visible_bands(bands, current_band=self._current_band)

    def _update_frequency(self):
        mode_key = self._current_mode.lower()
        freq = BAND_FREQUENCIES.get(self._current_band, {}).get(mode_key, 0)
        self.set_freq_display(freq, tune_active=False)

    def set_freq_display(self, freq_mhz: float, tune_active: bool = False):
        """Frequenzanzeige + Farbe nach Betriebszustand.
        tune_active=True  → Gelb (#FFD700) + Tune-Freq
        tune_active=False → Grün (#00CC66) + Arbeitsfreq
        """
        color = "#FFD700" if tune_active else "#00CC66"
        self.freq_label.setStyleSheet(
            f"color: {color}; font-size: 13pt; font-weight: bold; "
            f"font-family: {_FONT}; border: none; background: transparent;"
        )
        self.freq_label.setText(f"{freq_mhz * 1000:.3f} kHz")

    # =====================================================================
    # RX Modus (Antenne)
    # =====================================================================
    def _on_rx_mode_clicked(self, mode: str):
        """NORMAL oder DIVERSITY Button geklickt."""
        if mode == self._current_rx_mode:
            return
        if mode == "normal":
            self.btn_normal.setStyleSheet(self._rx_btn_style(self._RX_STYLE_ACTIVE))
            self.btn_diversity.setStyleSheet(self._rx_btn_style(self._RX_STYLE_INACTIVE))
            self.dx_info.setText("")
        else:
            self.btn_normal.setStyleSheet(self._rx_btn_style(self._RX_STYLE_INACTIVE))
            self.btn_diversity.setStyleSheet(self._rx_btn_style(self._RX_STYLE_DIVERSITY_ACTIVE))
        self._current_rx_mode = mode
        self._apply_rx_mode_visibility(mode == "diversity")
        if mode != "diversity":
            self.dx_info.setText("")
        self.rx_mode_changed.emit(mode)

    def _apply_rx_mode_visibility(self, is_div: bool):
        """UI-Elemente fuer den jeweiligen Modus ein-/ausblenden.

        Diversity: Diversity-Widget + CQ-Auto-Suche-Countdown sichtbar.
        Normal:    TX-Freq-Spinbox sichtbar, Histogramm klickbar (manuelle
                   Frequenz-Wahl wie WSJT-X).
        """
        self._div_widget.setVisible(is_div)
        self._tx_freq_row.setVisible(not is_div)
        self._freq_hist.set_clickable(not is_div)
        self._cq_row.setVisible(is_div)

    def set_rx_mode(self, mode: str):
        """RX-Modus programmatisch setzen (ohne Signal auszuloesen)."""
        if mode not in self._RX_MODES:
            mode = "normal"
        if mode == self._current_rx_mode:
            return
        if mode == "normal":
            self.btn_normal.setStyleSheet(self._rx_btn_style(self._RX_STYLE_ACTIVE))
            self.btn_diversity.setStyleSheet(self._rx_btn_style(self._RX_STYLE_INACTIVE))
        else:
            self.btn_normal.setStyleSheet(self._rx_btn_style(self._RX_STYLE_INACTIVE))
            self.btn_diversity.setStyleSheet(self._rx_btn_style(self._RX_STYLE_DIVERSITY_ACTIVE))
        self._current_rx_mode = mode
        self._apply_rx_mode_visibility(mode == "diversity")

    # =====================================================================
    # Diversity Ratio Display
    # =====================================================================
    def update_diversity_ratio(self, ratio: str,
                               *,
                               scoring_mode: str = "normal",
                               current_ant: str | None = None,
                               **_ignored_legacy):
        """Diversity-Anzeige aktualisieren.

        P34-Stufe2 (v0.97.19): vereinfachte Signatur. Phase ist immer
        "operate" (Statik-Pipeline raus), Anzeige ist immer
        "● DYNAMISCH (live)".

        ratio: '70:30' | '30:70' | '50:50'
        scoring_mode: 'normal' (Standard) | 'dx' (DX) — nur Info
        current_ant: aktive RX-Antenne ("A1"/"A2") fuer Label-Suffix

        Backwards-Compat: ``**_ignored_legacy`` schluckt alte Parameter
        (phase, measure_step, measure_total, operate_seconds_remaining,
        is_dynamic, operate_cycles, operate_total) — Tests koennten sie
        noch uebergeben.
        """
        for lbl in self._a1_pct.values():
            lbl.setStyleSheet(_DIV_PCT_OFF)
        for lbl in self._a2_pct.values():
            lbl.setStyleSheet(_DIV_PCT_OFF)

        # P37: aktive RX-Antenne hinter Label, dezent
        ant_suffix = ""
        if current_ant == "A1":
            ant_suffix = " — RX Ant1"
        elif current_ant == "A2":
            ant_suffix = " — RX Ant2"
        self._phase_label.setText(f"● DYNAMISCH (live){ant_suffix}")
        self._phase_label.setStyleSheet(
            f"color:#3399CC;font-size:9px;font-family:{_FONT};"
            "font-weight:bold;"
        )

        if ratio == "70:30":
            self._a1_pct["70%"].setStyleSheet(_DIV_PCT_GREEN)
            self._a2_pct["30%"].setStyleSheet(_DIV_PCT_RED)
        elif ratio == "30:70":
            self._a1_pct["30%"].setStyleSheet(_DIV_PCT_RED)
            self._a2_pct["70%"].setStyleSheet(_DIV_PCT_GREEN)
        else:  # 50:50
            self._a1_pct["50%"].setStyleSheet(_DIV_PCT_TEAL)
            self._a2_pct["50%"].setStyleSheet(_DIV_PCT_TEAL)

    def update_remeasure_countdown(self, seconds: int) -> None:
        """P34-Stufe2: No-Op — Re-Mess-Countdown entfaellt (Dynamic ist live)."""
        return

    def update_diversity_counts(self, a1_count: int, a2_count: int,
                                a1_avg_snr: float = None, a2_avg_snr: float = None,
                                scoring_mode: str = "normal",
                                ant2_wins: int = 0, total_compared: int = 0,
                                a1_weak_count: int = 0, a2_weak_count: int = 0):
        """Diversity-Counts pro Antenne.

        Standard: 'X St.' pro Antenne. DX: 'X DX' (schwache Signale -20..-10 dB).
        """
        if a1_count == 0 and a2_count == 0:
            self._a1_count_label.setText("--")
            self._a2_count_label.setText("  --")
        elif scoring_mode == "dx":
            a1_txt = f"{a1_weak_count:02d} DX" if a1_weak_count is not None else "--"
            a2_txt = f"  {a2_weak_count:02d} DX" if a2_weak_count is not None else "  --"
            self._a1_count_label.setText(a1_txt)
            self._a2_count_label.setText(a2_txt)
        else:
            self._a1_count_label.setText(f"{a1_count} St.")
            self._a2_count_label.setText(f"{a2_count} St.")

    def update_freq_histogram(self, data: dict):
        """Frequenz-Histogramm aktualisieren und anzeigen.

        Im Normal-Modus IMMER sichtbar (Wasserfall-Ersatz, auch ohne Daten),
        im Diversity-Modus erst nach erstem Daten-Update (wie bisher)."""
        self._freq_hist.update_data(data)
        if self._current_rx_mode != "diversity":
            self._freq_hist.setVisible(True)
        elif data.get('bins') or data.get('cq_freq'):
            self._freq_hist.setVisible(True)

    def update_cq_freq_countdown(self, remaining_s: int) -> None:
        """CQ-Frequenz Countdown-Balken aktualisieren (0-60 Sekunden, slot-synchron)."""
        if remaining_s <= 15:
            color_txt = "#FF5555"
            bar_color = "#FF5555"
        elif remaining_s <= 30:
            color_txt = "#CC3333"
            bar_color = "#CC3333"
        else:
            color_txt = "#882222"
            bar_color = "#882222"
        self._cq_freq_lbl.setText(f"Prüfe nächste freie TX Frequenz in: {remaining_s} Sek.")
        self._cq_freq_lbl.setStyleSheet(
            f"color:{color_txt};font-size:9px;font-family:{_FONT};font-style:italic;"
        )
        self._cq_freq_bar.setValue(remaining_s)
        self._cq_freq_bar.setStyleSheet(
            "QProgressBar { border: none; border-radius: 2px; background: #1a1010; }"
            f"QProgressBar::chunk {{ background: {bar_color}; border-radius: 2px; }}"
        )
        # CQ-Auto-Suche-Anzeige nur im Diversity-Modus relevant
        self._cq_row.setVisible(self._current_rx_mode == "diversity")

    def set_cq_countdown_visible(self, visible: bool) -> None:
        """CQ-Freq-Countdown-Zeile ein-/ausblenden."""
        self._cq_row.setVisible(visible)

    def update_presence(self, remaining_secs: int) -> None:
        """Operator Presence Balken aktualisieren (0-900 Sekunden)."""
        self.presence_bar.setValue(max(0, remaining_secs))
        # Farbe: grün > 5min, gelb > 2min, rot <= 2min
        if remaining_secs > 300:
            color = "#00AA00"
        elif remaining_secs > 120:
            color = "#CCAA00"
        else:
            color = "#CC0000"
        self.presence_bar.setStyleSheet(
            f"QProgressBar {{ background: #1a1a1a; border: none; border-radius: 1px; }}"
            f"QProgressBar::chunk {{ background: {color}; border-radius: 1px; }}"
        )

    def update_omni_tx(self, active: bool) -> None:
        """Ω-Symbol + Button-Text ein-/ausblenden je nach OMNI-TX Status.

        P3.OMNI-PATTERN-FIX-2 (v0.95.25): Button-Label dynamisch.
        Mike-Wunsch 09.05.2026: ohne Aktiv-Status-Anzeige klickt er
        mehrfach aus Unsicherheit → manual_halt-Spam.
        """
        self._omni_active = active
        self._omni_symbol.setVisible(active)
        color = "#222" if active else "#333"
        self._version_label.setStyleSheet(
            f"color: {color}; font-family: {_FONT}; font-size: 10px; "
            "border: none; background: transparent;"
        )
        if hasattr(self, 'btn_omni_cq'):
            self.btn_omni_cq.setText(
                "OMNI CQ (aktiv)" if active else "OMNI CQ"
            )

    def update_propagation(self, conditions, active_band: Optional[str] = None) -> None:
        """Propagations-Balken unter Band-Buttons aktualisieren.

        Args:
            conditions: Dict {'80m': 'good', ...} oder None (→ Balken ausblenden).
            active_band: Aktuelles Band — Trend-Pulsieren nur auf diesem.
        """
        self._mode_band_card.update_propagation(conditions or {}, active_band)

    # =====================================================================
    # PSK Reporter
    # =====================================================================
    def _open_psk_map(self):
        """Richtungs-Karte (intern) oeffnen via MainWindow-Signal.
        Frueher: Browser-Link zu pskreporter.info — abgeloest durch v0.66 Karte.
        """
        self.map_clicked.emit()

    def update_psk_stats(self, spots: int, avg_km: int, max_km: int,
                          max_call: str, max_country: str,
                          n_km: int, e_km: int, s_km: int, w_km: int,
                          band: str = "", fetch_time: str = ""):
        """PSKReporter-Statistik aktualisieren."""
        header = "PSK"
        if band:
            header += f" {band}"
        if fetch_time:
            header += f" | {fetch_time} UTC"
        if spots == 0:
            self.psk_label.setText(f"{header}: keine Spots")
            self.psk_label.setStyleSheet(
                f"color: #666; font-family: {_FONT}; font-size: 10px; padding: 2px;"
            )
            return
        text = (f"{header}: {spots} Spots | Ø {avg_km:,}km | Max: {max_km:,}km\n"
                f"N:{n_km:,} O:{e_km:,} S:{s_km:,} W:{w_km:,}\n"
                f"{max_call} ({max_country})")
        self.psk_label.setText(text)
        self.psk_label.setStyleSheet(
            f"color: #44FF44; font-family: {_FONT}; font-size: 10px; padding: 2px;"
        )

    # =====================================================================
    # Power / TX Level / Tune
    # =====================================================================
    def _on_power_preset_clicked(self, watts: int):
        self.power_changed.emit(watts)

    def set_power_preset(self, watts: int):
        """Preset-Button programmatisch selektieren (ohne Signal)."""
        # Naechsten verfuegbaren Wert finden
        available = sorted(self.power_buttons.keys())
        best = min(available, key=lambda w: abs(w - watts))
        self.power_buttons[best].setChecked(True)

    def _on_tx_level_changed(self, value: int):
        self.tx_level_label.setText(f"TX-Pegel: {value}%")
        self.tx_level_changed.emit(value)

    def _on_tune_clicked(self):
        self.tune_clicked.emit(self.btn_tune.isChecked())

    def update_watt(self, watts: float):
        self.watt_label.setText(f"{watts:.0f} W")

    def update_swr(self, swr: float):
        if swr < 1.5:
            color = "#44FF44"
        elif swr < 2.5:
            color = "#FFD700"
        else:
            color = "#FF4444"
        self.swr_label.setText(f"SWR {swr:.1f}")
        self.swr_label.setStyleSheet(
            f"color: {color}; font-family: {_FONT}; font-size: 14px; font-weight: bold;"
        )

    def update_alc(self, alc: float):
        """ALC-Meter aktualisieren (nur intern, nicht mehr angezeigt)."""
        pass

    def update_tx_peak(self, peak: float):
        """Audio-Peak-Level anzeigen. peak=0.0-x.x (1.0 = Clipping)."""
        if peak > 1.0:
            color = "#FF4444"
            label = f"Clipschutz {peak:.0%} CLIP!"
        elif peak > 0.90:
            color = "#FFD700"
            label = f"Clipschutz {peak:.0%}"
        elif peak > 0.01:
            color = "#44FF44"
            label = f"Clipschutz {peak:.0%}"
        else:
            color = "#557766"
            label = "Clipschutz —"
        self.peak_label.setText(label)
        self.peak_label.setStyleSheet(
            f"color: {color}; font-family: {_FONT}; font-size: 10px; "
            f"border: 1px solid #333; border-radius: 2px; padding: 1px 4px;"
        )

    def update_rfpower(self, rfpower: int):
        """RF-Power-Anzeige aktualisieren (0-100%)."""
        if rfpower <= 0:
            self.rf_power_label.setText("RF: —")
            color = "#555555"
        elif rfpower >= 90:
            self.rf_power_label.setText(f"RF: {rfpower}%")
            color = "#FF6644"
        elif rfpower >= 70:
            self.rf_power_label.setText(f"RF: {rfpower}%")
            color = "#FFAA44"
        else:
            self.rf_power_label.setText(f"RF: {rfpower}%")
            color = "#AAAACC"
        self.rf_power_label.setStyleSheet(
            f"color: {color}; font-family: {_FONT}; font-size: 10px; "
            f"border: 1px solid #333; border-radius: 2px; padding: 1px 4px;"
        )

    # =====================================================================
    # QSO Controls
    # =====================================================================
    def _on_cq_clicked(self):
        self.cq_clicked.emit()
        if self._omni_active:
            self.btn_cq.setText("OMNI CQ ■" if self.btn_cq.isChecked() else "OMNI CQ")
        elif self.btn_cq.isChecked():
            self.btn_cq.setText("CQ AKTIV ■")
        else:
            self.btn_cq.setText("CQ RUFEN")

    def update_qso_counter(self, count: int):
        if count > 0:
            self.qso_counter_label.setText(f"({count}) QSOs bearbeitet")
            self.qso_counter_label.setVisible(True)
        else:
            self.qso_counter_label.setVisible(False)

    def set_cq_active(self, active: bool):
        self.btn_cq.setChecked(active)
        if self._omni_active:
            self.btn_cq.setText("OMNI CQ ■" if active else "OMNI CQ")
        else:
            self.btn_cq.setText("CQ AKTIV ■" if active else "CQ RUFEN")

    def set_tx_active(self, active: bool):
        if active:
            self.tx_indicator.setStyleSheet(
                f"color: #FF4444; font-size: 16px; font-weight: bold; font-family: {_FONT};"
            )
            self.rx_indicator.setStyleSheet(
                f"color: #666; font-size: 16px; font-weight: bold; font-family: {_FONT};"
            )
        else:
            self.rx_indicator.setStyleSheet(
                f"color: #44FF44; font-size: 16px; font-weight: bold; font-family: {_FONT};"
            )
            self.tx_indicator.setStyleSheet(
                f"color: #666; font-size: 16px; font-weight: bold; font-family: {_FONT};"
            )


    # =====================================================================
    # Status / Info
    # =====================================================================
    def update_snr(self, snr: int):
        """No-Op (P1.19). Sterne-Anzeige nutzt update_local_conditions."""
        pass

    def update_local_conditions(self, score: int, n_stations: int, median_snr: float):
        """P1.19: 5-Sterne-Anzeige fuer lokale Conditions aktualisieren."""
        if median_snr <= -98:
            tooltip = f"{n_stations} Stationen (kein Signal)"
        else:
            tooltip = f"{n_stations} Stationen, Median {median_snr:+.0f} dB"
        self.conditions_widget.set_score(score, tooltip)

    def update_state(self, state_name: str):
        self._last_state = state_name
        self.state_label.setText(f"Status: {state_name}")

    def set_advance_label(self, state) -> None:
        """P1.FORCESEND (v0.95.12): btn_advance Label dynamisch je nach State.

        Mike's Hobby-UX: Button macht klar was gesendet wird.
        KISS: kompakt ohne Verb (Button-Klick-Kontext impliziert "senden").
        Default „QSO Finish" macht den Button-Zweck auch im IDLE klar
        (Mike-Feedback 07.05.: „Weiter →" nichtssagend).
        """
        from core.qso_state import QSOState
        labels = {
            QSOState.WAIT_REPORT: "R+Report",
            QSOState.WAIT_RR73: "RR73",
            QSOState.WAIT_73: "73",
        }
        self.btn_advance.setText(labels.get(state, "QSO Finish"))

    def set_rx_active(self, enabled: bool):
        """GAIN-MESSUNG + DIVERSITY sperren wenn RX aus ist."""
        self.btn_einmessen.setEnabled(enabled)
        self.btn_diversity.setEnabled(enabled)
        if not enabled:
            self.btn_einmessen.setToolTip("RX einschalten fuer Gain-Messung")
            self.btn_diversity.setToolTip("RX einschalten um Diversity zu nutzen")
        else:
            self.btn_einmessen.setToolTip("")
            self.btn_diversity.setToolTip("")

    def set_connection_status(self, status: str):
        """Verbindungsstatus anzeigen: 'connected', 'disconnected', 'searching', 'reconnecting'."""
        colors = {
            "connected": "#44FF44",
            "disconnected": "#FF4444",
            "searching": "#FFD700",
            "reconnecting": "#FFD700",
        }
        labels = {
            "connected": "RADIO: Verbunden",
            "disconnected": "RADIO: Getrennt",
            "searching": "RADIO: Suche...",
            "reconnecting": "RADIO: Reconnect...",
        }
        color = colors.get(status, "#888")
        label_text = labels.get(status, f"RADIO: {status}")
        # P1.22: RichText mit einheitlich grauem Label + farbigem Wert
        if ": " in label_text:
            prefix, value = label_text.split(": ", 1)
            self.connection_label.setText(
                f'<span style="color:{_TEXT};">{prefix}: </span>'
                f'<span style="color:{color};">{value}</span>'
            )
        else:
            self.connection_label.setText(
                f'<span style="color:{color};">{label_text}</span>'
            )
        connected = (status == "connected")
        for btn in [self.btn_tune, self.btn_cq, self.btn_diversity,
                    self.btn_einmessen, self.btn_normal]:
            btn.setEnabled(connected)

    def update_dt_correction(self, correction: float, sample_count: int):
        """DT-Korrektur Anzeige im State-Label (dezent)."""
        if sample_count > 0:
            self.state_label.setText(
                f"Status: {self._last_state}  |  DT: {correction:+.2f}s (n={sample_count})"
            )
        # _last_state wird in update_state gesetzt

    def update_decode_count(self, count: int):
        """Anzahl dekodierter Stationen im letzten Zyklus.
        P1.22: RichText mit einheitlich grauem Label + farbigem Wert.
        """
        if count > 0:
            value = f"{count} Station{'en' if count != 1 else ''}"
            self.decode_label.setText(
                f'<span style="color:{_TEXT};">Decode: </span>'
                f'<span style="color:#44FF44;">{value}</span>'
            )
        else:
            self.decode_label.setText(
                f'<span style="color:{_TEXT};">Decode: </span>'
                f'<span style="color:#666;">—</span>'
            )

    def update_cycle_bar(self, seconds_in_cycle: float, cycle_duration: float):
        progress = seconds_in_cycle / cycle_duration
        filled = int(progress * 20)
        bar = "█" * filled + "░" * (20 - filled)
        remaining = cycle_duration - seconds_in_cycle
        self.cycle_bar.setText(f" {bar} {remaining:.0f}s")
        self.cycle_bar.setStyleSheet(
            f"background-color: #1a1a2e; border: 1px solid #333; "
            f"border-radius: 3px; padding: 2px; color: #{'FF4444' if progress > 0.8 else '00AAFF'}; "
            f"font-family: {_FONT}; font-size: 11px;"
        )

    # =====================================================================
    # Clock
    # =====================================================================
    def _start_clock(self):
        self._clock_timer = QTimer(self)
        self._clock_timer.timeout.connect(self._update_clock)
        self._clock_timer.start(1000)

    def _update_clock(self):
        utc = time.strftime("%H:%M:%S", time.gmtime())
        self.utc_label.setText(f"UTC:  {utc}")
