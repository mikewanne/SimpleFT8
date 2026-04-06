"""SimpleFT8 Control Panel — Fenster 3: Steuerung und Status.

Dark Theme Redesign mit LED-Balance-Indikator.
"""

import time
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QSlider, QFrame, QGridLayout,
)
from PySide6.QtCore import Signal, Qt, QTimer
from PySide6.QtGui import QFont

from config.settings import BAND_FREQUENCIES

# ---------------------------------------------------------------------------
# Konstanten
# ---------------------------------------------------------------------------
_BG = "#16192b"
_TEXT = "#CCC"
_FONT = "Menlo"
_SEP_COLOR = "#333"
_MIN_WIDTH = 320

_LED_GREEN = "#00ee55"
_LED_BLUE = "#00aaff"

# Diversity Ratio Label Styles
_DIV_PCT_OFF    = ("background:rgba(255,255,255,0.04);color:#666;border:1px solid #333;"
                   "border-radius:3px;font-size:10px;font-family:Menlo;font-weight:bold;padding:1px 4px;")
_DIV_PCT_GREEN  = ("background:rgba(0,180,60,0.22);color:#00ee55;border:1px solid rgba(0,200,80,0.6);"
                   "border-radius:3px;font-size:10px;font-family:Menlo;font-weight:bold;padding:1px 4px;")
_DIV_PCT_RED    = ("background:rgba(200,50,50,0.22);color:#FF5555;border:1px solid rgba(220,60,60,0.6);"
                   "border-radius:3px;font-size:10px;font-family:Menlo;font-weight:bold;padding:1px 4px;")
_DIV_PCT_TEAL   = ("background:rgba(0,170,200,0.18);color:#00CCFF;border:1px solid rgba(0,180,210,0.5);"
                   "border-radius:3px;font-size:10px;font-family:Menlo;font-weight:bold;padding:1px 4px;")
_DIV_PCT_YELLOW = ("background:rgba(200,170,0,0.18);color:#FFCC00;border:1px solid rgba(210,180,0,0.5);"
                   "border-radius:3px;font-size:10px;font-family:Menlo;font-weight:bold;padding:1px 4px;")

# ---------------------------------------------------------------------------
# Glossy 3D Card Styles (DeepSeek-Design)
# ---------------------------------------------------------------------------
_BTN_BASE = """
    QPushButton {
        background-color: rgba(255,255,255,0.06);
        color: #BBB;
        border: 1px solid rgba(255,255,255,0.15);
        border-radius: 4px;
        font-family: Menlo;
        font-size: 11px;
        font-weight: bold;
        padding: 3px 8px;
        min-height: 22px;
    }
    QPushButton:checked {
        background-color: #0066AA;
        color: white;
        border-color: #00AAFF;
    }
    QPushButton:hover {
        background-color: rgba(255,255,255,0.12);
    }
"""

_CARD_SS_BLUE = """
QFrame#card {
    border: 2px solid #5588ff;
    border-radius: 8px;
}
""" + _BTN_BASE

_CARD_SS_GREEN = """
QFrame#card {
    border: 2px solid #33cc77;
    border-radius: 8px;
}
""" + _BTN_BASE

_CARD_SS_TEAL = """
QFrame#card {
    border: 2px solid #00aacc;
    border-radius: 8px;
}
""" + _BTN_BASE

_CARD_SS_ORANGE = """
QFrame#card {
    border: 2px solid #ee9922;
    border-radius: 8px;
}
""" + _BTN_BASE

# Legacy alias
_CARD_SS = _CARD_SS_BLUE


class _ModeBandCard(QFrame):
    """Kachel 1 (blau) — Modus (FT8/FT4) + Band-Auswahl."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("card")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(_CARD_SS_BLUE)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 10, 10, 10)
        lay.setSpacing(8)

        # ── Modus-Zeile ──────────────────────────────────────────
        row_m = QHBoxLayout()
        row_m.setSpacing(6)
        lbl_modus = QLabel("Modus")
        lbl_modus.setFixedWidth(42)
        row_m.addWidget(lbl_modus)
        self.btn_ft8 = QPushButton("FT8")
        self.btn_ft8.setCheckable(True)
        self.btn_ft8.setChecked(True)
        self.btn_ft8.setFixedHeight(28)
        self.btn_ft4 = QPushButton("FT4")
        self.btn_ft4.setCheckable(True)
        self.btn_ft4.setFixedHeight(28)
        row_m.addWidget(self.btn_ft8)
        row_m.addWidget(self.btn_ft4)
        row_m.addStretch()
        lay.addLayout(row_m)

        # ── Band-Grid (Label links, alle Buttons gleich breit) ────
        self.band_buttons = {}
        grid = QGridLayout()
        grid.setSpacing(4)
        grid.setContentsMargins(0, 0, 0, 0)

        lbl_band = QLabel("Band")
        lbl_band.setFixedWidth(42)
        grid.addWidget(lbl_band, 0, 0)

        bands_row1 = ["10m", "12m", "15m", "17m", "20m"]
        bands_row2 = ["30m", "40m", "60m", "80m"]

        for col, b in enumerate(bands_row1):
            btn = QPushButton(b)
            btn.setCheckable(True)
            btn.setChecked(b == "20m")
            btn.setFixedHeight(28)
            self.band_buttons[b] = btn
            grid.addWidget(btn, 0, col + 1)

        for col, b in enumerate(bands_row2):
            btn = QPushButton(b)
            btn.setCheckable(True)
            btn.setFixedHeight(28)
            self.band_buttons[b] = btn
            grid.addWidget(btn, 1, col + 1)  # ab Spalte 1 = unter 10m

        # Alle Button-Spalten (1-5) gleich breit strecken
        for col in range(1, 6):
            grid.setColumnStretch(col, 1)

        lay.addLayout(grid)


def _sep_line() -> QFrame:
    """Dünne Trennlinie innerhalb einer Kachel."""
    line = QFrame()
    line.setFrameShape(QFrame.Shape.HLine)
    line.setFixedHeight(1)
    line.setStyleSheet("background: rgba(255,255,255,0.08); border: none;")
    return line


class _AntenneCard(QFrame):
    """Kachel 2 (grün) — ANTENNE alleine (NORMAL/DIVERSITY/EINMESSEN + LED)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("card")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(_CARD_SS_GREEN)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 8, 10, 8)
        lay.setSpacing(5)

        lbl_ant = QLabel("ANTENNE")
        lbl_ant.setStyleSheet(f"color: #55BBAA; font-size: 10px; font-family: {_FONT}; font-weight: bold;")
        lay.addWidget(lbl_ant)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(4)
        self.btn_normal = QPushButton("NORMAL")
        self.btn_normal.setFixedHeight(28)
        self.btn_diversity = QPushButton("DIVERSITY")
        self.btn_diversity.setFixedHeight(28)
        self.btn_einmessen = QPushButton("EINMESSEN")
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
        lay.addLayout(btn_row)

        self.dx_info = QLabel("")
        self.dx_info.setStyleSheet(f"color: #668877; font-size: 10px; font-family: {_FONT};")
        lay.addWidget(self.dx_info)

        # Diversity Ratio Display
        self._div_widget = QWidget()
        div_lay = QVBoxLayout(self._div_widget)
        div_lay.setContentsMargins(0, 2, 0, 2)
        div_lay.setSpacing(2)
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
        self._phase_label = QLabel("")
        self._phase_label.setStyleSheet(
            f"color:#FFCC00;font-size:9px;font-family:{_FONT};font-style:italic;"
        )
        self._phase_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        div_lay.addWidget(self._phase_label)
        self._div_widget.setVisible(False)
        lay.addWidget(self._div_widget)


class _RadioCard(QFrame):
    """Kachel 3 (türkis) — RADIO Controls (PSK, Freq, Power, TUNE, ALC, TX)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("card")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(_CARD_SS_TEAL)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 8, 10, 8)
        lay.setSpacing(5)

        lbl_radio = QLabel("RADIO")
        lbl_radio.setStyleSheet(f"color: #00aacc; font-size: 10px; font-family: {_FONT}; font-weight: bold;")
        lay.addWidget(lbl_radio)

        # PSK
        self.psk_label = QLabel("PSK: —")
        self.psk_label.setStyleSheet(f"color: #557766; font-family: {_FONT}; font-size: 10px;")
        self.psk_label.setWordWrap(True)
        lay.addWidget(self.psk_label)

        psk_row = QHBoxLayout()
        psk_row.setSpacing(2)
        self.btn_psk_map = QPushButton("Map")
        self.btn_psk_map.setFixedHeight(22)
        self.btn_psk_map.setFixedWidth(40)
        self.btn_psk_map.setStyleSheet(
            "QPushButton { background: rgba(0,150,100,0.2); color: #00CCAA; "
            "border: 1px solid rgba(0,180,130,0.4); border-radius: 2px; font-size: 10px; }"
            "QPushButton:hover { background: rgba(0,170,120,0.3); }"
        )
        psk_row.addWidget(self.btn_psk_map)
        psk_row.addStretch()
        lay.addLayout(psk_row)

        # Frequenz
        self.freq_label = QLabel("14.074 MHz")
        self.freq_label.setStyleSheet(
            f"color: #FFD700; font-size: 14pt; font-weight: bold; "
            f"font-family: {_FONT}; padding: 2px;"
        )
        self.freq_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(self.freq_label)

        # Power Slider
        power_row = QHBoxLayout()
        power_row.setSpacing(4)
        self.power_slider = QSlider(Qt.Orientation.Horizontal)
        self.power_slider.setRange(0, 100)
        self.power_slider.setValue(50)
        self.power_slider.setFixedHeight(18)
        self.power_slider.setStyleSheet(
            "QSlider::groove:horizontal { background: rgba(255,255,255,0.1); height: 4px; border-radius: 2px; }"
            "QSlider::handle:horizontal { background: #00CCAA; width: 14px; margin: -5px 0; border-radius: 7px; }"
            "QSlider::sub-page:horizontal { background: rgba(0,180,140,0.5); border-radius: 2px; }"
        )
        self.power_label = QLabel("50W")
        self.power_label.setStyleSheet(f"color: {_TEXT}; font-family: {_FONT}; font-size: 11px;")
        power_row.addWidget(self.power_slider)
        power_row.addWidget(self.power_label)
        lay.addLayout(power_row)

        # TUNE + Watt + SWR
        tune_row = QHBoxLayout()
        tune_row.setSpacing(4)
        self.btn_tune = QPushButton("TUNE")
        self.btn_tune.setCheckable(True)
        self.btn_tune.setFixedHeight(24)
        self.btn_tune.setFixedWidth(60)
        self.btn_tune.setStyleSheet(
            f"QPushButton {{ background: rgba(180,150,0,0.2); color: #FFD700; "
            f"border: 1px solid rgba(220,180,0,0.5); border-radius: 3px; "
            f"font-weight: bold; font-family: {_FONT}; font-size: 10px; }}"
            f"QPushButton:checked {{ background: rgba(180,150,0,0.4); }}"
        )
        self.watt_label = QLabel("0 W")
        self.watt_label.setStyleSheet(f"color: #FFD700; font-family: {_FONT}; font-size: 12px; font-weight: bold;")
        self.swr_label = QLabel("SWR —")
        self.swr_label.setStyleSheet(f"color: #44FF44; font-family: {_FONT}; font-size: 12px; font-weight: bold;")
        tune_row.addWidget(self.btn_tune)
        tune_row.addWidget(self.watt_label)
        tune_row.addWidget(self.swr_label)
        lay.addLayout(tune_row)

        # ALC
        self.alc_label = QLabel("ALC —")
        self.alc_label.setStyleSheet(f"color: #557766; font-family: {_FONT}; font-size: 11px;")
        lay.addWidget(self.alc_label)

        # TX Level
        tx_row = QHBoxLayout()
        tx_row.setSpacing(4)
        tx_lbl = QLabel("TX Lvl")
        tx_lbl.setStyleSheet(f"color: #557766; font-family: {_FONT}; font-size: 10px;")
        self.tx_level_slider = QSlider(Qt.Orientation.Horizontal)
        self.tx_level_slider.setRange(0, 100)
        self.tx_level_slider.setValue(100)
        self.tx_level_slider.setFixedHeight(16)
        self.tx_level_slider.setStyleSheet(
            "QSlider::groove:horizontal { background: rgba(255,255,255,0.1); height: 3px; border-radius: 1px; }"
            "QSlider::handle:horizontal { background: #FF8800; width: 12px; margin: -4px 0; border-radius: 6px; }"
            "QSlider::sub-page:horizontal { background: rgba(220,120,0,0.5); border-radius: 1px; }"
        )
        self.tx_level_label = QLabel("100%")
        self.tx_level_label.setStyleSheet(f"color: {_TEXT}; font-family: {_FONT}; font-size: 10px;")
        tx_row.addWidget(tx_lbl)
        tx_row.addWidget(self.tx_level_slider)
        tx_row.addWidget(self.tx_level_label)
        lay.addLayout(tx_row)


class _QSOStatusCard(QFrame):
    """Kachel 3 (orange) — QSO + STATUS + Settings."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("card")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(_CARD_SS_ORANGE)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(6, 4, 6, 4)
        lay.setSpacing(2)

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

        self.btn_cq = QPushButton("CQ RUFEN")
        self.btn_cq.setCheckable(True)
        self.btn_cq.setFixedHeight(26)
        self.btn_cq.setStyleSheet(
            f"QPushButton {{ background: rgba(140,0,0,0.5); color: white; "
            f"border: 1px solid rgba(220,60,60,0.6); border-radius: 5px; "
            f"font-size: 12px; font-weight: bold; font-family: {_FONT}; }}"
            f"QPushButton:checked {{ background: rgba(200,0,0,0.7); color: #FFD700; "
            f"border-color: rgba(255,180,0,0.7); }}"
            f"QPushButton:hover {{ background: rgba(180,0,0,0.6); }}"
        )
        lay.addWidget(self.btn_cq)

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
        self.btn_advance = QPushButton("Weiter →")
        self.btn_advance.setFixedHeight(22)
        self.btn_advance.setStyleSheet(
            "QPushButton { background: rgba(0,100,0,0.35); color: #88CC88; "
            "border: 1px solid rgba(0,150,0,0.4); border-radius: 4px; "
            "padding: 2px; font-size: 11px; font-weight: bold; }"
            "QPushButton:hover { background: rgba(0,130,0,0.45); }"
            "QPushButton:disabled { background: rgba(255,255,255,0.04); color: #444; border-color: #333; }"
        )
        self.btn_advance.setEnabled(False)
        self.btn_cancel = QPushButton("Abbrechen")
        self.btn_cancel.setFixedHeight(22)
        self.btn_cancel.setStyleSheet(
            "QPushButton { background: rgba(100,0,0,0.35); color: #CC6666; "
            "border: 1px solid rgba(150,0,0,0.4); border-radius: 4px; padding: 2px; font-size: 11px; }"
            "QPushButton:hover { background: rgba(130,0,0,0.45); }"
            "QPushButton:disabled { background: rgba(255,255,255,0.04); color: #444; border-color: #333; }"
        )
        self.btn_cancel.setEnabled(False)
        adv_row.addWidget(self.btn_advance)
        adv_row.addWidget(self.btn_cancel)
        lay.addLayout(adv_row)

        lay.addWidget(_sep_line())

        # ── STATUS ────────────────────────────────────────────────
        lbl_status = QLabel("STATUS")
        lbl_status.setStyleSheet(f"color: #CC9944; font-size: 10px; font-family: {_FONT}; font-weight: bold;")
        lay.addWidget(lbl_status)

        self.connection_label = QLabel("RADIO: Suche...")
        self.connection_label.setStyleSheet(
            f"color: #FFD700; font-family: {_FONT}; font-size: 11px; font-weight: bold;"
        )
        lay.addWidget(self.connection_label)

        self.decode_label = QLabel("Decode: —")
        self.decode_label.setStyleSheet(f"color: {_TEXT}; font-family: {_FONT}; font-size: 11px;")
        lay.addWidget(self.decode_label)

        # SNR + UTC in einer Zeile
        snr_utc_row = QHBoxLayout()
        snr_utc_row.setSpacing(8)
        self.snr_label = QLabel("SNR: — dB")
        self.snr_label.setStyleSheet(f"color: {_TEXT}; font-family: {_FONT}; font-size: 11px;")
        self.utc_label = QLabel("UTC: --:--:--")
        self.utc_label.setStyleSheet(f"color: {_TEXT}; font-family: {_FONT}; font-size: 11px;")
        snr_utc_row.addWidget(self.snr_label)
        snr_utc_row.addStretch()
        snr_utc_row.addWidget(self.utc_label)
        lay.addLayout(snr_utc_row)

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
    rx_mode_changed = Signal(str)
    settings_clicked = Signal()
    einmessen_clicked = Signal()

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
        self.btn_ft8 = mb_card.btn_ft8
        self.btn_ft4 = mb_card.btn_ft4
        self.band_buttons = mb_card.band_buttons
        mb_card.btn_ft8.clicked.connect(lambda: self._set_mode("FT8"))
        mb_card.btn_ft4.clicked.connect(lambda: self._set_mode("FT4"))
        for band, btn in mb_card.band_buttons.items():
            btn.clicked.connect(lambda checked, b=band: self._set_band(b))
        layout.addWidget(mb_card)

        # ── Kachel 2: ANTENNE (grün) ─────────────────────────────────────
        ant_card = _AntenneCard(self)
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
        self.btn_normal.setStyleSheet(self._rx_btn_style(self._RX_STYLE_ACTIVE))
        self.btn_diversity.setStyleSheet(self._rx_btn_style(self._RX_STYLE_INACTIVE))
        self.btn_normal.clicked.connect(lambda: self._on_rx_mode_clicked("normal"))
        self.btn_diversity.clicked.connect(lambda: self._on_rx_mode_clicked("diversity"))
        self.btn_einmessen.clicked.connect(self.einmessen_clicked.emit)
        layout.addWidget(ant_card)

        # ── Kachel 3: RADIO (türkis) ─────────────────────────────────────
        radio_card = _RadioCard(self)
        self.psk_label = radio_card.psk_label
        self.btn_psk_map = radio_card.btn_psk_map
        self.btn_psk_map.clicked.connect(self._open_psk_map)
        self.freq_label = radio_card.freq_label
        self.power_slider = radio_card.power_slider
        self.power_label = radio_card.power_label
        self.power_slider.valueChanged.connect(self._on_power_changed)
        self.btn_tune = radio_card.btn_tune
        self.btn_tune.clicked.connect(self._on_tune_clicked)
        self.watt_label = radio_card.watt_label
        self.swr_label = radio_card.swr_label
        self.alc_label = radio_card.alc_label
        self.tx_level_slider = radio_card.tx_level_slider
        self.tx_level_label = radio_card.tx_level_label
        self.tx_level_slider.valueChanged.connect(self._on_tx_level_changed)
        layout.addWidget(radio_card)

        # ── Kachel 3: QSO + STATUS (orange) ─────────────────────────────
        qso_card = _QSOStatusCard(self)
        self.rx_indicator = qso_card.rx_indicator
        self.tx_indicator = qso_card.tx_indicator
        self.btn_cq = qso_card.btn_cq
        self.btn_cq.clicked.connect(self._on_cq_clicked)
        self.qso_counter_label = qso_card.qso_counter_label
        self.btn_advance = qso_card.btn_advance
        self.btn_advance.clicked.connect(self.advance_clicked.emit)
        self.btn_cancel = qso_card.btn_cancel
        self.btn_cancel.clicked.connect(self.cancel_clicked.emit)
        self.connection_label = qso_card.connection_label
        self.decode_label = qso_card.decode_label
        self.snr_label = qso_card.snr_label
        self.utc_label = qso_card.utc_label
        self.state_label = qso_card.state_label
        self.cycle_bar = qso_card.cycle_bar
        self.btn_settings = qso_card.btn_settings
        self.btn_settings.clicked.connect(self.settings_clicked.emit)
        layout.addWidget(qso_card)

        layout.addStretch()

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
        self._update_frequency()
        self.mode_changed.emit(mode)

    def _set_band(self, band: str):
        self._current_band = band
        for b, btn in self.band_buttons.items():
            btn.setChecked(b == band)
        self._update_frequency()
        self.band_changed.emit(band)

    def _update_frequency(self):
        mode_key = self._current_mode.lower()
        freq = BAND_FREQUENCIES.get(self._current_band, {}).get(mode_key, 0)
        self.freq_label.setText(f"{freq:.3f} MHz")

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
        is_div = (mode == "diversity")
        self._div_widget.setVisible(is_div)
        if not is_div:
            self.dx_info.setText("")
        self.rx_mode_changed.emit(mode)

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
        is_div = (mode == "diversity")
        self._div_widget.setVisible(is_div)

    # =====================================================================
    # Diversity Ratio Display
    # =====================================================================
    def update_diversity_ratio(self, ratio: str, phase: str,
                               measure_step: int = 0, measure_total: int = 4):
        """Diversity-Anzeige aktualisieren.

        ratio: '70:30' | '30:70' | '50:50'
        phase: 'measure' | 'operate'
        measure_step: abgeschlossene Messschritte (0..measure_total)
        """
        for lbl in self._a1_pct.values():
            lbl.setStyleSheet(_DIV_PCT_OFF)
        for lbl in self._a2_pct.values():
            lbl.setStyleSheet(_DIV_PCT_OFF)

        if phase == "measure":
            step_txt = f"{measure_step}/{measure_total}" if measure_step > 0 else f"0/{measure_total}"
            self._phase_label.setText(f"● MESSEN {step_txt}")
            self._a1_pct["50%"].setStyleSheet(_DIV_PCT_YELLOW)
            self._a2_pct["50%"].setStyleSheet(_DIV_PCT_YELLOW)
        else:
            self._phase_label.setText("")
            if ratio == "70:30":
                self._a1_pct["70%"].setStyleSheet(_DIV_PCT_GREEN)
                self._a2_pct["30%"].setStyleSheet(_DIV_PCT_RED)
            elif ratio == "30:70":
                self._a1_pct["30%"].setStyleSheet(_DIV_PCT_RED)
                self._a2_pct["70%"].setStyleSheet(_DIV_PCT_GREEN)
            else:  # 50:50
                self._a1_pct["50%"].setStyleSheet(_DIV_PCT_TEAL)
                self._a2_pct["50%"].setStyleSheet(_DIV_PCT_TEAL)

    def update_diversity_counts(self, a1_count: int, a2_count: int):
        """Stationsanzahl pro Antenne im Diversity-Panel anzeigen."""
        if a1_count == 0 and a2_count == 0:
            self._a1_count_label.setText("")
            self._a2_count_label.setText("")
        else:
            self._a1_count_label.setText(f"{a1_count} St.")
            self._a2_count_label.setText(f"{a2_count} St.")

    # =====================================================================
    # PSK Reporter
    # =====================================================================
    def _open_psk_map(self):
        """PSKReporter im Browser oeffnen mit eigenem Call."""
        import webbrowser
        webbrowser.open(
            f"https://pskreporter.info/pskmap.html?callsign={self._callsign}"
        )

    def update_psk_stats(self, spots: int, avg_km: int, max_km: int,
                          max_call: str, max_country: str,
                          n_km: int, e_km: int, s_km: int, w_km: int):
        """PSKReporter-Statistik aktualisieren."""
        if spots == 0:
            self.psk_label.setText("PSK: keine Spots")
            self.psk_label.setStyleSheet(
                f"color: #666; font-family: {_FONT}; font-size: 10px; padding: 2px;"
            )
            return
        text = (f"PSK: {spots} Spots | Ø {avg_km:,}km | Max: {max_km:,}km\n"
                f"N:{n_km:,} O:{e_km:,} S:{s_km:,} W:{w_km:,}\n"
                f"{max_call} ({max_country})")
        self.psk_label.setText(text)
        self.psk_label.setStyleSheet(
            f"color: #44FF44; font-family: {_FONT}; font-size: 10px; padding: 2px;"
        )

    # =====================================================================
    # Power / TX Level / Tune
    # =====================================================================
    def _on_power_changed(self, value: int):
        self.power_label.setText(f"{value}W")
        self.power_changed.emit(value)

    def _on_tx_level_changed(self, value: int):
        self.tx_level_label.setText(f"{value}%")
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
        """ALC-Meter aktualisieren mit Farbcodierung.

        FlexRadio ALC:
        - 0 dB = kein Eingriff (Signal unter ALC-Schwelle)
        - > 0 dB = ALC komprimiert (SCHLECHT fuer FT8!)
        """
        if alc > 5:
            color = "#FF4444"
            label = f"ALC {alc:.0f} dB HOCH!"
        elif alc > 0:
            color = "#FFD700"
            label = f"ALC {alc:.0f} dB"
        else:
            color = "#44FF44"
            label = f"ALC {alc:.0f} dB"
        self.alc_label.setText(label)
        self.alc_label.setStyleSheet(
            f"color: {color}; font-family: {_FONT}; font-size: 11px;"
        )

    # =====================================================================
    # QSO Controls
    # =====================================================================
    def _on_cq_clicked(self):
        self.cq_clicked.emit()
        if self.btn_cq.isChecked():
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
        self.snr_label.setText(f"SNR:  {snr:+d} dB")

    def update_state(self, state_name: str):
        self.state_label.setText(f"Status: {state_name}")

    def set_rx_active(self, enabled: bool):
        """EINMESSEN + DIVERSITY sperren wenn RX aus ist."""
        self.btn_einmessen.setEnabled(enabled)
        self.btn_diversity.setEnabled(enabled)
        if not enabled:
            self.btn_einmessen.setToolTip("RX einschalten um einzumessen")
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
        label = labels.get(status, f"RADIO: {status}")
        self.connection_label.setText(label)
        self.connection_label.setStyleSheet(
            f"color: {color}; font-family: {_FONT}; font-size: 12px; font-weight: bold;"
        )
        connected = (status == "connected")
        for btn in [self.btn_tune, self.btn_cq, self.btn_diversity,
                    self.btn_einmessen, self.btn_normal]:
            btn.setEnabled(connected)

    def update_decode_count(self, count: int):
        """Anzahl dekodierter Stationen im letzten Zyklus."""
        if count > 0:
            self.decode_label.setText(f"Decode: {count} Station{'en' if count != 1 else ''}")
            self.decode_label.setStyleSheet(
                f"color: #44FF44; font-family: {_FONT}; font-size: 12px;"
            )
        else:
            self.decode_label.setText("Decode: —")
            self.decode_label.setStyleSheet(
                f"color: #666; font-family: {_FONT}; font-size: 12px;"
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
