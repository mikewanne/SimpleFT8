"""SimpleFT8 Control Panel — Fenster 3: Steuerung und Status."""

import time
import threading
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QSlider, QButtonGroup, QFrame, QLineEdit,
)
from PySide6.QtCore import Signal, Qt, QTimer
from PySide6.QtGui import QFont

from config.settings import BAND_FREQUENCIES


class ControlPanel(QWidget):
    """Control-Fenster — Modus, Band, Frequenz, Power, Status.

    Signals:
        mode_changed: (str) — "FT8" oder "FT4"
        band_changed: (str) — z.B. "20m"
        power_changed: (int) — Leistung in Prozent (0-100)
        auto_toggled: (bool) — Auto-Modus an/aus
        advance_clicked: () — Nächster QSO-Schritt (manuell)
        cancel_clicked: () — QSO abbrechen
        cq_clicked: () — CQ-Modus starten/stoppen
    """

    mode_changed = Signal(str)
    band_changed = Signal(str)
    power_changed = Signal(int)
    auto_toggled = Signal(bool)
    advance_clicked = Signal()
    cancel_clicked = Signal()
    cq_clicked = Signal()
    tune_clicked = Signal(bool)
    dx_preset_changed = Signal(str)
    tx_level_changed = Signal(int)
    preamp_changed = Signal(bool)  # Legacy, nicht mehr genutzt
    rx_mode_changed = Signal(str)  # "normal", "diversity", "dx_tuning"
    settings_clicked = Signal()

    _RX_MODES = ["normal", "diversity", "dx_tuning"]
    _RX_LABELS = {"normal": "NORMAL", "diversity": "DIVERSITY", "dx_tuning": "DX TUNING"}
    _RX_COLORS = {
        "normal": "background: #222; color: #AAA; border-color: #555;",
        "diversity": "background: #003344; color: #00CCFF; border-color: #00AADD;",
        "dx_tuning": "background: #662200; color: #FF8844; border-color: #FF8844;",
    }

    def __init__(self):
        super().__init__()
        self._current_mode = "FT8"
        self._current_band = "20m"
        self._auto_mode = False
        self._rx_mode_idx = 0
        self._setup_ui()
        self._start_clock()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(4)

        header = QLabel("CONTROL")
        header.setStyleSheet(
            "color: #00AAFF; font-weight: bold; font-size: 13px; padding: 2px;"
        )
        layout.addWidget(header)

        # --- Modus ---
        mode_row = QHBoxLayout()
        mode_row.setSpacing(2)
        self.btn_ft8 = self._band_btn("FT8", checked=True)
        self.btn_ft4 = self._band_btn("FT4")
        self.btn_ft8.clicked.connect(lambda: self._set_mode("FT8"))
        self.btn_ft4.clicked.connect(lambda: self._set_mode("FT4"))
        mode_row.addWidget(self.btn_ft8)
        mode_row.addWidget(self.btn_ft4)
        layout.addLayout(mode_row)

        # --- Band (kompakt) ---
        layout.addWidget(self._section_label("Band"))
        bands_row1 = QHBoxLayout()
        bands_row1.setSpacing(2)
        bands_row2 = QHBoxLayout()
        bands_row2.setSpacing(2)
        self.band_buttons = {}
        bands = ["10m", "12m", "15m", "17m", "20m", "30m", "40m", "60m", "80m"]
        for i, band in enumerate(bands):
            btn = self._band_btn(band, checked=(band == "20m"))
            btn.clicked.connect(lambda checked, b=band: self._set_band(b))
            self.band_buttons[band] = btn
            if i < 5:
                bands_row1.addWidget(btn)
            else:
                bands_row2.addWidget(btn)
        layout.addLayout(bands_row1)
        layout.addLayout(bands_row2)

        # --- RX Modus: NORMAL / DIVERSITY / DX TUNING ---
        dx_row = QHBoxLayout()
        dx_row.setSpacing(6)
        self.btn_dx = QPushButton("NORMAL")
        self.btn_dx.setFixedHeight(28)
        self.btn_dx.setStyleSheet("""
            QPushButton {
                background: #222; color: #AAA; border: 1px solid #555;
                border-radius: 4px; font-size: 12px; font-weight: bold;
                padding: 0 16px;
            }
            QPushButton:hover { background: #333; }
        """)
        self.btn_dx.clicked.connect(self._on_dx_toggled)
        dx_row.addWidget(self.btn_dx)
        self.dx_info = QLabel("")
        self.dx_info.setStyleSheet("color: #888; font-size: 10px; font-family: Menlo;")
        dx_row.addWidget(self.dx_info)
        dx_row.addStretch()
        layout.addLayout(dx_row)

        # --- PSK Reichweite ---
        self.psk_label = QLabel("PSK: —")
        self.psk_label.setStyleSheet(
            "color: #888; font-family: Menlo; font-size: 10px; padding: 2px;"
        )
        self.psk_label.setWordWrap(True)
        layout.addWidget(self.psk_label)

        psk_row = QHBoxLayout()
        psk_row.setSpacing(2)
        self.btn_psk_map = QPushButton("Map")
        self.btn_psk_map.setFixedHeight(22)
        self.btn_psk_map.setFixedWidth(40)
        self.btn_psk_map.setStyleSheet("""
            QPushButton { background: #333; color: #00AAFF; border: 1px solid #00AAFF;
                border-radius: 2px; font-size: 10px; }
            QPushButton:hover { background: #004466; }
        """)
        self.btn_psk_map.clicked.connect(self._open_psk_map)
        psk_row.addWidget(self.btn_psk_map)
        psk_row.addStretch()
        layout.addLayout(psk_row)

        # --- Frequenz ---
        self.freq_label = QLabel("14.074 MHz")
        self.freq_label.setStyleSheet(
            "color: #FFD700; font-size: 15px; font-weight: bold; "
            "font-family: Menlo; padding: 2px;"
        )
        self.freq_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.freq_label)

        # --- Power + Tune ---
        power_row = QHBoxLayout()
        power_row.setSpacing(4)
        self.power_slider = QSlider(Qt.Orientation.Horizontal)
        self.power_slider.setRange(0, 100)
        self.power_slider.setValue(50)
        self.power_slider.setFixedHeight(18)
        self.power_slider.setStyleSheet("""
            QSlider::groove:horizontal { background: #333; height: 4px; border-radius: 2px; }
            QSlider::handle:horizontal { background: #00AAFF; width: 14px; margin: -5px 0; border-radius: 7px; }
            QSlider::sub-page:horizontal { background: #0066AA; border-radius: 2px; }
        """)
        self.power_label = QLabel("50W")
        self.power_label.setStyleSheet("color: #CCC; font-family: Menlo; font-size: 11px;")
        self.power_slider.valueChanged.connect(self._on_power_changed)
        power_row.addWidget(self.power_slider)
        power_row.addWidget(self.power_label)
        layout.addLayout(power_row)

        tune_meter_row = QHBoxLayout()
        tune_meter_row.setSpacing(4)
        self.btn_tune = QPushButton("TUNE")
        self.btn_tune.setCheckable(True)
        self.btn_tune.setFixedHeight(24)
        self.btn_tune.setFixedWidth(60)
        self.btn_tune.setStyleSheet("""
            QPushButton { background: #333; color: #FFD700; border: 1px solid #FFD700;
                border-radius: 3px; font-weight: bold; font-family: Menlo; font-size: 10px; }
            QPushButton:checked { background: #665500; }
        """)
        self.btn_tune.clicked.connect(self._on_tune_clicked)
        self.watt_label = QLabel("0 W")
        self.watt_label.setStyleSheet("color: #FFD700; font-family: Menlo; font-size: 12px; font-weight: bold;")
        self.swr_label = QLabel("SWR —")
        self.swr_label.setStyleSheet("color: #44FF44; font-family: Menlo; font-size: 12px; font-weight: bold;")
        self.alc_label = QLabel("ALC —")
        self.alc_label.setStyleSheet("color: #888; font-family: Menlo; font-size: 11px;")
        tune_meter_row.addWidget(self.btn_tune)
        tune_meter_row.addWidget(self.watt_label)
        tune_meter_row.addWidget(self.swr_label)
        layout.addLayout(tune_meter_row)
        layout.addWidget(self.alc_label)

        # --- TX Level ---
        tx_level_row = QHBoxLayout()
        tx_level_row.setSpacing(4)
        tx_lvl_label = QLabel("TX Lvl")
        tx_lvl_label.setStyleSheet("color: #888; font-family: Menlo; font-size: 10px;")
        self.tx_level_slider = QSlider(Qt.Orientation.Horizontal)
        self.tx_level_slider.setRange(0, 100)
        self.tx_level_slider.setValue(100)
        self.tx_level_slider.setFixedHeight(16)
        self.tx_level_slider.setStyleSheet("""
            QSlider::groove:horizontal { background: #333; height: 3px; border-radius: 1px; }
            QSlider::handle:horizontal { background: #FF8800; width: 12px; margin: -4px 0; border-radius: 6px; }
            QSlider::sub-page:horizontal { background: #884400; border-radius: 1px; }
        """)
        self.tx_level_label = QLabel("100%")
        self.tx_level_label.setStyleSheet("color: #CCC; font-family: Menlo; font-size: 10px;")
        self.tx_level_slider.valueChanged.connect(self._on_tx_level_changed)
        tx_level_row.addWidget(tx_lvl_label)
        tx_level_row.addWidget(self.tx_level_slider)
        tx_level_row.addWidget(self.tx_level_label)
        layout.addLayout(tx_level_row)

        # --- RX/TX + AUTO ---
        layout.addWidget(self._separator())
        rxtx_row = QHBoxLayout()
        rxtx_row.setSpacing(4)
        self.rx_indicator = QLabel("● RX")
        self.rx_indicator.setStyleSheet("color: #44FF44; font-size: 13px; font-weight: bold; font-family: Menlo;")
        self.tx_indicator = QLabel("○ TX")
        self.tx_indicator.setStyleSheet("color: #666; font-size: 13px; font-weight: bold; font-family: Menlo;")
        self.btn_auto = QPushButton("AUTO")
        self.btn_auto.setCheckable(True)
        self.btn_auto.setFixedHeight(24)
        self.btn_auto.setStyleSheet("""
            QPushButton { background: #333; color: #FF4444; border: 1px solid #FF4444;
                border-radius: 3px; padding: 2px 8px; font-weight: bold; font-family: Menlo; font-size: 10px; }
            QPushButton:checked { background: #004400; color: #44FF44; border-color: #44FF44; }
        """)
        self.btn_auto.clicked.connect(self._on_auto_toggled)
        rxtx_row.addWidget(self.rx_indicator)
        rxtx_row.addWidget(self.tx_indicator)
        rxtx_row.addStretch()
        rxtx_row.addWidget(self.btn_auto)
        layout.addLayout(rxtx_row)

        # --- CQ Rufen ---
        self.btn_cq = QPushButton("CQ RUFEN")
        self.btn_cq.setCheckable(True)
        self.btn_cq.setFixedHeight(32)
        self.btn_cq.setStyleSheet("""
            QPushButton { background: #8B0000; color: white; border: 1px solid #FF4444;
                border-radius: 3px; font-size: 13px; font-weight: bold; font-family: Menlo; }
            QPushButton:checked { background: #CC0000; color: #FFD700; border-color: #FFD700; }
            QPushButton:hover { background: #AA0000; }
        """)
        self.btn_cq.clicked.connect(self._on_cq_clicked)
        layout.addWidget(self.btn_cq)

        self.qso_counter_label = QLabel("")
        self.qso_counter_label.setStyleSheet(
            "color: #44FF44; font-family: Menlo; font-size: 13px; "
            "font-weight: bold; padding: 2px;"
        )
        self.qso_counter_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.qso_counter_label)

        # --- Weiter / Abbrechen ---
        layout.addWidget(self._separator())
        self.btn_advance = QPushButton("Weiter →")
        self.btn_advance.setStyleSheet("""
            QPushButton {
                background-color: #006600;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px;
                font-size: 13px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #008800; }
            QPushButton:disabled { background-color: #333; color: #666; }
        """)
        self.btn_advance.setEnabled(False)
        self.btn_advance.clicked.connect(self.advance_clicked.emit)
        layout.addWidget(self.btn_advance)

        self.btn_cancel = QPushButton("Abbrechen")
        self.btn_cancel.setStyleSheet("""
            QPushButton {
                background-color: #660000;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 6px;
                font-size: 12px;
            }
            QPushButton:hover { background-color: #880000; }
            QPushButton:disabled { background-color: #333; color: #666; }
        """)
        self.btn_cancel.setEnabled(False)
        self.btn_cancel.clicked.connect(self.cancel_clicked.emit)
        layout.addWidget(self.btn_cancel)

        # --- Info ---
        layout.addWidget(self._separator())

        # Verbindungsstatus
        self.connection_label = QLabel("RADIO: Suche...")
        self.connection_label.setStyleSheet(
            "color: #FFD700; font-family: Menlo; font-size: 12px; font-weight: bold;"
        )
        layout.addWidget(self.connection_label)

        # Decode-Counter
        self.decode_label = QLabel("Decode: —")
        self.decode_label.setStyleSheet("color: #CCC; font-family: Menlo; font-size: 12px;")
        layout.addWidget(self.decode_label)

        self.snr_label = QLabel("SNR:  — dB")
        self.snr_label.setStyleSheet("color: #CCC; font-family: Menlo; font-size: 12px;")
        layout.addWidget(self.snr_label)

        self.utc_label = QLabel("UTC:  --:--:--")
        self.utc_label.setStyleSheet("color: #CCC; font-family: Menlo; font-size: 12px;")
        layout.addWidget(self.utc_label)

        self.state_label = QLabel("Status: IDLE")
        self.state_label.setStyleSheet("color: #888; font-family: Menlo; font-size: 11px;")
        layout.addWidget(self.state_label)

        # --- Takt-Balken ---
        self.cycle_bar = QLabel("")
        self.cycle_bar.setStyleSheet(
            "background-color: #1a1a2e; border: 1px solid #333; "
            "border-radius: 3px; padding: 2px;"
        )
        self.cycle_bar.setFixedHeight(20)
        layout.addWidget(self.cycle_bar)

        # --- Settings Button ---
        layout.addWidget(self._separator())
        self.btn_settings = QPushButton("Einstellungen")
        self.btn_settings.setFixedHeight(26)
        self.btn_settings.setStyleSheet("""
            QPushButton { background: #333; color: #AAA; border: 1px solid #555;
                border-radius: 3px; font-size: 11px; }
            QPushButton:hover { background: #444; color: #FFF; }
        """)
        self.btn_settings.clicked.connect(self.settings_clicked.emit)
        layout.addWidget(self.btn_settings)

        layout.addStretch()

    def _section_label(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet("color: #888; font-size: 11px; padding-top: 4px;")
        return lbl

    def _separator(self) -> QFrame:
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet("color: #333;")
        return line

    def _band_btn(self, text: str, checked: bool = False) -> QPushButton:
        """Kompakter Band-Button (schmaler als Standard)."""
        btn = QPushButton(text)
        btn.setCheckable(True)
        btn.setChecked(checked)
        btn.setFixedHeight(26)
        btn.setStyleSheet("""
            QPushButton {
                background-color: #2a2a3e;
                color: #AAA;
                border: 1px solid #444;
                border-radius: 3px;
                padding: 2px 4px;
                font-family: Menlo;
                font-size: 11px;
                min-width: 32px;
            }
            QPushButton:checked {
                background-color: #0066AA;
                color: white;
                border-color: #00AAFF;
            }
            QPushButton:hover { background-color: #333; }
        """)
        return btn

    def _toggle_btn(self, text: str, checked: bool = False) -> QPushButton:
        btn = QPushButton(text)
        btn.setCheckable(True)
        btn.setChecked(checked)
        btn.setStyleSheet("""
            QPushButton {
                background-color: #333;
                color: #CCC;
                border: 1px solid #555;
                border-radius: 3px;
                padding: 4px 8px;
                font-family: Menlo;
                font-size: 12px;
            }
            QPushButton:checked {
                background-color: #0066AA;
                color: white;
                border-color: #00AAFF;
            }
        """)
        return btn

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

    def _on_dx_toggled(self):
        """Zyklisch durch RX-Modi schalten: NORMAL → DIVERSITY → DX TUNING → NORMAL."""
        self._rx_mode_idx = (self._rx_mode_idx + 1) % 3
        mode = self._RX_MODES[self._rx_mode_idx]
        self.btn_dx.setText(self._RX_LABELS[mode])
        style_base = (
            "QPushButton {{ {colors} border-radius: 4px; "
            "font-size: 12px; font-weight: bold; padding: 0 16px; "
            "border-width: 1px; border-style: solid; }}"
            "QPushButton:hover {{ background: #333; }}"
        )
        self.btn_dx.setStyleSheet(
            style_base.format(colors=self._RX_COLORS[mode])
        )
        if mode == "normal":
            self.dx_info.setText("")
        self.rx_mode_changed.emit(mode)

    def set_rx_mode(self, mode: str):
        """RX-Modus programmatisch setzen (ohne Signal auszuloesen)."""
        try:
            self._rx_mode_idx = self._RX_MODES.index(mode)
        except ValueError:
            self._rx_mode_idx = 0
            mode = "normal"
        self.btn_dx.setText(self._RX_LABELS[mode])
        style_base = (
            "QPushButton {{ {colors} border-radius: 4px; "
            "font-size: 12px; font-weight: bold; padding: 0 16px; "
            "border-width: 1px; border-style: solid; }}"
            "QPushButton:hover {{ background: #333; }}"
        )
        self.btn_dx.setStyleSheet(
            style_base.format(colors=self._RX_COLORS[mode])
        )

    def _open_psk_map(self):
        """PSKReporter im Browser oeffnen mit eigenem Call."""
        import webbrowser
        webbrowser.open("https://pskreporter.info/pskmap.html?callsign=DA1MHH")

    def update_psk_stats(self, spots: int, avg_km: int, max_km: int,
                          max_call: str, max_country: str,
                          n_km: int, e_km: int, s_km: int, w_km: int):
        """PSKReporter-Statistik aktualisieren."""
        if spots == 0:
            self.psk_label.setText("PSK: keine Spots")
            self.psk_label.setStyleSheet(
                "color: #666; font-family: Menlo; font-size: 10px; padding: 2px;"
            )
            return
        text = (f"PSK: {spots} Spots | Ø {avg_km:,}km | Max: {max_km:,}km\n"
                f"N:{n_km:,} O:{e_km:,} S:{s_km:,} W:{w_km:,}\n"
                f"{max_call} ({max_country})")
        self.psk_label.setText(text)
        self.psk_label.setStyleSheet(
            "color: #44FF44; font-family: Menlo; font-size: 10px; padding: 2px;"
        )

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
            color = "#44FF44"  # gruen
        elif swr < 2.5:
            color = "#FFD700"  # gelb
        else:
            color = "#FF4444"  # rot
        self.swr_label.setText(f"SWR {swr:.1f}")
        self.swr_label.setStyleSheet(
            f"color: {color}; font-family: Menlo; font-size: 14px; font-weight: bold;"
        )

    def update_alc(self, alc: float):
        """ALC-Meter aktualisieren mit Farbcodierung.

        FlexRadio ALC:
        - 0 dB = kein Eingriff (Signal unter ALC-Schwelle)
        - > 0 dB = ALC komprimiert (SCHLECHT fuer FT8!)
        - Optimal: TX Lvl so einstellen dass ALC gerade NICHT ausschlaegt
        """
        if alc > 5:
            color = "#FF4444"  # ROT — stark uebersteuert!
            label = f"ALC {alc:.0f} dB HOCH!"
        elif alc > 0:
            color = "#FFD700"  # GELB — ALC greift ein, etwas zurueckdrehen
            label = f"ALC {alc:.0f} dB"
        else:
            color = "#44FF44"  # GRUEN — kein ALC, optimal
            label = f"ALC {alc:.0f} dB"
        self.alc_label.setText(label)
        self.alc_label.setStyleSheet(
            f"color: {color}; font-family: Menlo; font-size: 11px;"
        )

    def _on_auto_toggled(self):
        self._auto_mode = self.btn_auto.isChecked()
        self.btn_auto.setText("ON" if self._auto_mode else "OFF")
        self.auto_toggled.emit(self._auto_mode)

    def _on_cq_clicked(self):
        self.cq_clicked.emit()
        if self.btn_cq.isChecked():
            self.btn_cq.setText("CQ AKTIV ■")
        else:
            self.btn_cq.setText("CQ RUFEN")

    def update_qso_counter(self, count: int):
        if count > 0:
            self.qso_counter_label.setText(f"({count}) QSOs bearbeitet")
        else:
            self.qso_counter_label.setText("")

    def set_cq_active(self, active: bool):
        self.btn_cq.setChecked(active)
        self.btn_cq.setText("CQ AKTIV ■" if active else "CQ RUFEN")

    def set_tx_active(self, active: bool):
        if active:
            self.tx_indicator.setStyleSheet(
                "color: #FF4444; font-size: 16px; font-weight: bold; font-family: Menlo;"
            )
            self.rx_indicator.setStyleSheet(
                "color: #666; font-size: 16px; font-weight: bold; font-family: Menlo;"
            )
        else:
            self.rx_indicator.setStyleSheet(
                "color: #44FF44; font-size: 16px; font-weight: bold; font-family: Menlo;"
            )
            self.tx_indicator.setStyleSheet(
                "color: #666; font-size: 16px; font-weight: bold; font-family: Menlo;"
            )

    def update_snr(self, snr: int):
        self.snr_label.setText(f"SNR:  {snr:+d} dB")

    def update_state(self, state_name: str):
        self.state_label.setText(f"Status: {state_name}")

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
            f"color: {color}; font-family: Menlo; font-size: 12px; font-weight: bold;"
        )

    def update_decode_count(self, count: int):
        """Anzahl dekodierter Stationen im letzten Zyklus."""
        if count > 0:
            self.decode_label.setText(f"Decode: {count} Station{'en' if count != 1 else ''}")
            self.decode_label.setStyleSheet(
                "color: #44FF44; font-family: Menlo; font-size: 12px;"
            )
        else:
            self.decode_label.setText("Decode: —")
            self.decode_label.setStyleSheet(
                "color: #666; font-family: Menlo; font-size: 12px;"
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
            f"font-family: Menlo; font-size: 11px;"
        )

    def _start_clock(self):
        self._clock_timer = QTimer(self)
        self._clock_timer.timeout.connect(self._update_clock)
        self._clock_timer.start(1000)

    def _update_clock(self):
        utc = time.strftime("%H:%M:%S", time.gmtime())
        self.utc_label.setText(f"UTC:  {utc}")
