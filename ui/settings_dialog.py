"""SimpleFT8 Settings Dialog — Einstellungen bearbeiten und in config.json speichern."""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel,
    QLineEdit, QSpinBox, QDoubleSpinBox, QPushButton, QGroupBox,
    QComboBox,
)
from PySide6.QtCore import Qt

from config.settings import Settings


class SettingsDialog(QDialog):
    """Einstellungs-Dialog fuer SimpleFT8."""

    def __init__(self, settings: Settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.setWindowTitle("SimpleFT8 — Einstellungen")
        self.setMinimumWidth(400)
        self.setStyleSheet("""
            QDialog { background-color: #1a1a2e; color: #CCC; }
            QGroupBox { color: #00AAFF; border: 1px solid #333;
                border-radius: 4px; margin-top: 8px; padding-top: 16px; }
            QGroupBox::title { padding: 0 8px; }
            QLabel { color: #CCC; }
            QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {
                background: #222; color: #FFF; border: 1px solid #444;
                border-radius: 3px; padding: 4px; }
            QPushButton { background: #0066AA; color: white; border: none;
                border-radius: 3px; padding: 8px 16px; font-weight: bold; }
            QPushButton:hover { background: #0088CC; }
            QPushButton#cancel { background: #333; }
        """)
        self._setup_ui()
        self._load_values()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # --- Station ---
        station = QGroupBox("Station")
        form1 = QFormLayout(station)
        self.callsign = QLineEdit()
        self.locator = QLineEdit()
        self.locator.setMaxLength(6)
        form1.addRow("Rufzeichen:", self.callsign)
        form1.addRow("Locator:", self.locator)
        layout.addWidget(station)

        # --- Radio ---
        radio = QGroupBox("FlexRadio")
        form2 = QFormLayout(radio)
        self.radio_ip = QLineEdit()
        self.radio_ip.setPlaceholderText("Auto-Discovery")
        form2.addRow("IP Adresse:", self.radio_ip)
        layout.addWidget(radio)

        # --- TX ---
        tx = QGroupBox("Senden")
        form3 = QFormLayout(tx)
        self.power = QSpinBox()
        self.power.setRange(1, 100)
        self.power.setSuffix(" W")
        self.tx_level = QSpinBox()
        self.tx_level.setRange(1, 100)
        self.tx_level.setSuffix(" %")
        self.tx_level.setToolTip("TX Audio-Pegel (100% = volles Signal)")
        form3.addRow("Sendeleistung:", self.power)
        form3.addRow("TX Audio-Pegel:", self.tx_level)
        layout.addWidget(tx)

        # --- Schutz ---
        protect = QGroupBox("Schutz")
        form4 = QFormLayout(protect)
        self.swr_limit = QDoubleSpinBox()
        self.swr_limit.setRange(1.5, 10.0)
        self.swr_limit.setSingleStep(0.5)
        self.swr_limit.setDecimals(1)
        self.swr_limit.setToolTip("Bei SWR ueber diesem Wert wird TX sofort gestoppt")
        form4.addRow("SWR-Limit:", self.swr_limit)
        layout.addWidget(protect)

        # --- FT8 ---
        ft8 = QGroupBox("FT8 Decoder")
        form5 = QFormLayout(ft8)
        self.audio_freq = QSpinBox()
        self.audio_freq.setRange(200, 2800)
        self.audio_freq.setSuffix(" Hz")
        self.max_decode_freq = QSpinBox()
        self.max_decode_freq.setRange(1000, 5000)
        self.max_decode_freq.setSuffix(" Hz")
        form5.addRow("TX Audio-Frequenz:", self.audio_freq)
        form5.addRow("Max. Decode-Frequenz:", self.max_decode_freq)
        layout.addWidget(ft8)

        # --- Buttons ---
        btn_row = QHBoxLayout()
        btn_save = QPushButton("Speichern")
        btn_save.clicked.connect(self._save_and_close)
        btn_cancel = QPushButton("Abbrechen")
        btn_cancel.setObjectName("cancel")
        btn_cancel.clicked.connect(self.reject)
        btn_row.addStretch()
        btn_row.addWidget(btn_cancel)
        btn_row.addWidget(btn_save)
        layout.addLayout(btn_row)

    def _load_values(self):
        self.callsign.setText(self.settings.callsign)
        self.locator.setText(self.settings.locator)
        self.radio_ip.setText(self.settings.get("flexradio_ip", ""))
        self.power.setValue(self.settings.power_watts)
        self.tx_level.setValue(self.settings.get("tx_level", 100))
        self.swr_limit.setValue(self.settings.get("swr_limit", 3.0))
        self.audio_freq.setValue(self.settings.audio_freq_hz)
        self.max_decode_freq.setValue(self.settings.max_decode_freq)

    def _save_and_close(self):
        self.settings.set("callsign", self.callsign.text().upper().strip())
        self.settings.set("locator", self.locator.text().upper().strip())
        self.settings.set("flexradio_ip", self.radio_ip.text().strip())
        self.settings.set("power_watts", self.power.value())
        self.settings.set("tx_level", self.tx_level.value())
        self.settings.set("swr_limit", self.swr_limit.value())
        self.settings.set("audio_freq_hz", self.audio_freq.value())
        self.settings.set("max_decode_freq", self.max_decode_freq.value())
        self.settings.save()
        self.accept()
