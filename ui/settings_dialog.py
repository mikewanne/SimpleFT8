"""SimpleFT8 Settings Dialog — Einstellungen bearbeiten und in config.json speichern."""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel,
    QLineEdit, QSpinBox, QDoubleSpinBox, QPushButton, QGroupBox,
    QComboBox, QMessageBox, QToolButton,
)
from PySide6.QtCore import Qt

from config.settings import Settings, DEFAULTS

# Info-Texte fuer die (i)-Buttons
_HINTS = {
    "callsign": "Dein Amateurfunk-Rufzeichen (z.B. DA1MHH).\nWird in allen FT8-Nachrichten verwendet.",
    "locator": "Maidenhead-Locator deines Standorts (4 oder 6 Zeichen).\nWird bei CQ und erstem Anruf mitgesendet.",
    "radio_ip": "IP-Adresse des FlexRadio. Leer = Auto-Discovery per Broadcast.\nNur aendern wenn mehrere Radios im Netzwerk.",
    "power": "HF-Sendeleistung in Watt.\nFuer FT8 reichen 20-50W fuer weltweiten Betrieb.",
    "tx_level": "Audio-Pegel zum Radio (100% = volles Signal).\nBei ALC-Ausschlag reduzieren.",
    "max_calls": "Wie oft eine Station maximal angerufen wird bevor Timeout.\n3 = schnell weiter, 7 = hartnäckig, 99 = quasi-endlos.",
    "swr_limit": "Bei SWR ueber diesem Wert wird TX sofort gestoppt.\nSchuetzt Endstufe und Antenne.",
    "tune_power": "Leistung beim TUNE-Vorgang (Antennentuner einstellen).\nMax 20W — hoehere Werte brauchen Bestaetigung.",
    "tx_freq": "Audio-Frequenz fuer TX im FT8-Fenster.\n1500 Hz = Standard (WSJT-X Default).\nBereich 1000-2000 Hz wird von allen Stationen dekodiert.\nUnter 800 Hz: wird von vielen Stationen ausgefiltert!",
    "max_decode": "Obere Grenze des Dekodier-Bereichs.\n3000 Hz = Standard. Hoeher = mehr Stationen aber mehr CPU.",
    "diversity_cycles": "Anzahl Betriebszyklen bis zur naechsten Antennen-Messung.\n80 ≈ 20 Min  |  160 ≈ 40 Min  |  240 ≈ 60 Min\nAntennen werden dann automatisch auf 50:50 zurueckgesetzt und neu vermessen.",
}


def _make_info_btn(hint: str) -> QToolButton:
    """Kleiner (i)-Button mit Tooltip."""
    btn = QToolButton()
    btn.setText("?")
    btn.setFixedSize(20, 20)
    btn.setStyleSheet("""
        QToolButton {
            background: #333; color: #888; border: 1px solid #555;
            border-radius: 10px; font-size: 11px; font-weight: bold;
        }
        QToolButton:hover { background: #444; color: #FFF; }
    """)
    btn.setToolTip(hint)
    btn.clicked.connect(lambda: QMessageBox.information(
        btn.window(), "Info", hint
    ))
    return btn


def _row_with_hint(widget, hint_key: str) -> QHBoxLayout:
    """Widget + (i)-Button in einer Zeile."""
    row = QHBoxLayout()
    row.addWidget(widget)
    if hint_key in _HINTS:
        row.addWidget(_make_info_btn(_HINTS[hint_key]))
    return row


class SettingsDialog(QDialog):
    """Einstellungs-Dialog fuer SimpleFT8."""

    def __init__(self, settings: Settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.setWindowTitle("SimpleFT8 — Einstellungen")
        self.setMinimumWidth(420)
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
            QPushButton#reset { background: #553300; }
            QPushButton#reset:hover { background: #774400; }
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
        form1.addRow("Rufzeichen:", _row_with_hint(self.callsign, "callsign"))
        form1.addRow("Locator:", _row_with_hint(self.locator, "locator"))
        layout.addWidget(station)

        # --- Radio ---
        radio = QGroupBox("FlexRadio")
        form2 = QFormLayout(radio)
        self.radio_ip = QLineEdit()
        self.radio_ip.setPlaceholderText("Auto-Discovery")
        form2.addRow("IP Adresse:", _row_with_hint(self.radio_ip, "radio_ip"))
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
        self.max_calls_combo = QComboBox()
        self.max_calls_combo.addItems(["3", "5", "7", "99"])
        form3.addRow("Sendeleistung:", _row_with_hint(self.power, "power"))
        form3.addRow("TX Audio-Pegel:", _row_with_hint(self.tx_level, "tx_level"))
        form3.addRow("Anrufversuche:", _row_with_hint(self.max_calls_combo, "max_calls"))
        layout.addWidget(tx)

        # --- Schutz ---
        protect = QGroupBox("Schutz")
        form4 = QFormLayout(protect)
        self.swr_limit = QDoubleSpinBox()
        self.swr_limit.setRange(1.5, 10.0)
        self.swr_limit.setSingleStep(0.5)
        self.swr_limit.setDecimals(1)
        form4.addRow("SWR-Limit:", _row_with_hint(self.swr_limit, "swr_limit"))

        # Tune-Leistung: 3 feste Werte, max 20W (kein Schutz-Risiko)
        tune_row = QHBoxLayout()
        self._tune_btns = {}
        self._current_tune_power = 10
        for w in (5, 10, 20):
            btn = QPushButton(f"{w}W")
            btn.setCheckable(True)
            btn.setFixedWidth(52)
            btn.setStyleSheet("""
                QPushButton { background:#222; color:#888; border:1px solid #444;
                    border-radius:3px; padding:4px 8px; }
                QPushButton:checked { background:#0066AA; color:white; border-color:#0088CC; }
                QPushButton:hover { background:#333; color:#CCC; }
            """)
            btn.clicked.connect(lambda _, watt=w: self._on_tune_power_clicked(watt))
            tune_row.addWidget(btn)
            self._tune_btns[w] = btn
        tune_row.addWidget(_make_info_btn(_HINTS["tune_power"]))
        tune_row.addStretch()
        form4.addRow("Tune-Leistung:", tune_row)
        layout.addWidget(protect)

        # --- FT8 ---
        ft8 = QGroupBox("FT8")
        form5 = QFormLayout(ft8)
        self.audio_freq = QSpinBox()
        self.audio_freq.setRange(800, 2800)
        self.audio_freq.setSuffix(" Hz")
        self.audio_freq.setSingleStep(50)
        self.max_decode_freq = QSpinBox()
        self.max_decode_freq.setRange(1000, 5000)
        self.max_decode_freq.setSuffix(" Hz")
        form5.addRow("TX Audio-Frequenz:", _row_with_hint(self.audio_freq, "tx_freq"))
        form5.addRow("Max. Decode-Frequenz:", _row_with_hint(self.max_decode_freq, "max_decode"))
        layout.addWidget(ft8)

        # --- Diversity ---
        diversity = QGroupBox("Diversity")
        form6 = QFormLayout(diversity)
        self.diversity_cycles = QComboBox()
        self.diversity_cycles.addItems(["80", "160", "240"])
        form6.addRow("Neueinmessung nach:", _row_with_hint(self.diversity_cycles, "diversity_cycles"))
        layout.addWidget(diversity)

        # --- Buttons ---
        btn_row = QHBoxLayout()
        btn_reset = QPushButton("Grundeinstellungen")
        btn_reset.setObjectName("reset")
        btn_reset.setToolTip("Alle Werte auf Werkseinstellungen zuruecksetzen")
        btn_reset.clicked.connect(self._reset_defaults)
        btn_save = QPushButton("Speichern")
        btn_save.clicked.connect(self._save_and_close)
        btn_cancel = QPushButton("Abbrechen")
        btn_cancel.setObjectName("cancel")
        btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(btn_reset)
        btn_row.addStretch()
        btn_row.addWidget(btn_cancel)
        btn_row.addWidget(btn_save)
        layout.addLayout(btn_row)

    def _on_tune_power_clicked(self, watt: int):
        current = self._current_tune_power
        if watt > current:
            msg = QMessageBox(self)
            msg.setWindowTitle("Tune-Leistung")
            msg.setIcon(QMessageBox.Icon.Warning)
            msg.setText(f"Tune-Leistung auf {watt}W erhoehen?\n\nHohere Leistung kann Antenne/Tuner beschaedigen.")
            msg.setStyleSheet("QMessageBox { background:#1a1a2e; color:#CCC; }")
            btn_yes = msg.addButton("Ja", QMessageBox.ButtonRole.AcceptRole)
            msg.addButton("Nein", QMessageBox.ButtonRole.RejectRole)
            msg.exec()
            if msg.clickedButton() != btn_yes:
                # Revert button state
                self._tune_btns[watt].setChecked(False)
                self._tune_btns[current].setChecked(True)
                return
        self._current_tune_power = watt
        for w, btn in self._tune_btns.items():
            btn.setChecked(w == watt)

    def _load_values(self):
        self.callsign.setText(self.settings.callsign)
        self.locator.setText(self.settings.locator)
        self.radio_ip.setText(self.settings.get("flexradio_ip", ""))
        self.power.setValue(self.settings.power_watts)
        self.tx_level.setValue(self.settings.get("tx_level", 100))
        mc = self.settings.get("max_calls", 3)
        self.max_calls_combo.setCurrentIndex({3: 0, 5: 1, 7: 2, 99: 3}.get(mc, 0))
        self.swr_limit.setValue(self.settings.get("swr_limit", 3.0))
        self.audio_freq.setValue(self.settings.get("audio_freq_hz", 1500))
        self.max_decode_freq.setValue(self.settings.max_decode_freq)
        # Diversity-Zyklen
        dc = self.settings.get("diversity_operate_cycles", 80)
        self.diversity_cycles.setCurrentIndex({80: 0, 160: 1, 240: 2}.get(dc, 0))
        # Tune-Leistung
        tp = self.settings.get("tune_power", 10)
        self._current_tune_power = tp
        for w, btn in self._tune_btns.items():
            btn.setChecked(w == tp)

    def _save_and_close(self):
        self.settings.set("callsign", self.callsign.text().upper().strip())
        self.settings.set("locator", self.locator.text().upper().strip())
        self.settings.set("flexradio_ip", self.radio_ip.text().strip())
        self.settings.set("power_watts", self.power.value())
        self.settings.set("tx_level", self.tx_level.value())
        self.settings.set("max_calls", int(self.max_calls_combo.currentText()))
        self.settings.set("swr_limit", self.swr_limit.value())
        self.settings.set("tune_power", self._current_tune_power)
        self.settings.set("audio_freq_hz", self.audio_freq.value())
        self.settings.set("max_decode_freq", self.max_decode_freq.value())
        self.settings.set("diversity_operate_cycles", int(self.diversity_cycles.currentText()))
        self.settings.save()
        self.accept()

    def _reset_defaults(self):
        """Alle Werte auf Grundeinstellungen zuruecksetzen."""
        msg = QMessageBox(self)
        msg.setWindowTitle("Grundeinstellungen")
        msg.setIcon(QMessageBox.Icon.Question)
        msg.setText("Alle Einstellungen auf Werkseinstellungen zuruecksetzen?\n\n"
                    "Rufzeichen und Locator bleiben erhalten.")
        msg.setStyleSheet("QMessageBox { background:#1a1a2e; color:#CCC; }")
        btn_yes = msg.addButton("Zuruecksetzen", QMessageBox.ButtonRole.AcceptRole)
        msg.addButton("Abbrechen", QMessageBox.ButtonRole.RejectRole)
        msg.exec()
        if msg.clickedButton() != btn_yes:
            return
        # Werte auf Defaults setzen (Rufzeichen/Locator behalten)
        self.power.setValue(DEFAULTS.get("power_watts", 50))
        self.tx_level.setValue(100)
        self.max_calls_combo.setCurrentIndex(3)  # 99
        self.swr_limit.setValue(3.0)
        self.audio_freq.setValue(1500)
        self.max_decode_freq.setValue(DEFAULTS.get("max_decode_freq", 3000))
        self._current_tune_power = 10
        for w, btn in self._tune_btns.items():
            btn.setChecked(w == 10)
        self.diversity_cycles.setCurrentIndex(0)  # 80 Zyklen
