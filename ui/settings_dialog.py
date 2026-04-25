"""SimpleFT8 Settings Dialog — Einstellungen bearbeiten und in config.json speichern."""

import time

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel,
    QLineEdit, QSpinBox, QDoubleSpinBox, QPushButton, QGroupBox,
    QComboBox, QMessageBox, QToolButton,
    QTableWidget, QTableWidgetItem, QHeaderView,
)
from PySide6.QtCore import Qt, QTimer

from config.settings import Settings, DEFAULTS
from ui.styles import MSGBOX_STYLE

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
        self.setMinimumWidth(620)
        self.setStyleSheet("""
            QDialog { background-color: #1a1a2e; color: #CCC; }
            QGroupBox { color: #00AAFF; border: 1px solid #333;
                border-radius: 4px; margin-top: 8px; padding-top: 16px; }
            QGroupBox::title { padding: 0 8px; }
            QLabel { color: #CCC; }
            QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {
                background: #222; color: #FFF; border: 1px solid #444;
                border-radius: 3px; padding: 4px; min-width: 100px; }
            QComboBox { min-width: 140px; }
            QComboBox::drop-down { width: 24px; }
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
        layout.setSpacing(10)

        # ── Oberer Bereich: 2 Spalten ─────────────────────────────────
        top = QHBoxLayout()
        top.setSpacing(14)

        # LINKE SPALTE: Station & Hardware
        left = QVBoxLayout()
        station = QGroupBox("Station & Hardware")
        form1 = QFormLayout(station)
        self.callsign = QLineEdit()
        self.locator = QLineEdit()
        self.locator.setMaxLength(6)
        self.radio_ip = QLineEdit()
        self.radio_ip.setPlaceholderText("Auto-Discovery")
        form1.addRow("Rufzeichen:", _row_with_hint(self.callsign, "callsign"))
        form1.addRow("Locator:", _row_with_hint(self.locator, "locator"))
        form1.addRow("IP Adresse:", _row_with_hint(self.radio_ip, "radio_ip"))
        left.addWidget(station)
        left.addStretch()
        top.addLayout(left)

        # RECHTE SPALTE: TX & Schutz
        right = QVBoxLayout()
        tx = QGroupBox("TX & Schutz")
        form2 = QFormLayout(tx)
        self.power = QSpinBox()
        self.power.setRange(1, 100)
        self.power.setSuffix(" W")
        self.tx_level = QSpinBox()
        self.tx_level.setRange(1, 100)
        self.tx_level.setSuffix(" %")
        self.max_calls_combo = QComboBox()
        self.max_calls_combo.addItems(["3", "5", "7", "99"])
        self.swr_limit = QDoubleSpinBox()
        self.swr_limit.setRange(1.5, 10.0)
        self.swr_limit.setSingleStep(0.5)
        self.swr_limit.setDecimals(1)
        form2.addRow("Sendeleistung:", _row_with_hint(self.power, "power"))
        form2.addRow("TX Audio-Pegel:", _row_with_hint(self.tx_level, "tx_level"))
        form2.addRow("Anrufversuche:", _row_with_hint(self.max_calls_combo, "max_calls"))
        form2.addRow("SWR-Limit:", _row_with_hint(self.swr_limit, "swr_limit"))
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
        form2.addRow("Tune-Leistung:", tune_row)
        right.addWidget(tx)
        right.addStretch()
        top.addLayout(right)
        layout.addLayout(top)

        # ── RF-Power-Presets (pro Band+Watt, pro Radio) ──────────────
        rf_box = QGroupBox("RF-Presets pro Band+Watt")
        rf_layout = QVBoxLayout(rf_box)
        self._rf_info_label = QLabel("Aktives Radio: —")
        self._rf_info_label.setStyleSheet("color: #888; padding: 0 0 4px 0;")
        rf_layout.addWidget(self._rf_info_label)

        self.rf_table = QTableWidget(0, 4)
        self.rf_table.setHorizontalHeaderLabels(
            ["Band", "Watt", "RF (0-100)", "Letzte Speicherung"]
        )
        self.rf_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self.rf_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.rf_table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        self.rf_table.verticalHeader().setVisible(False)
        self.rf_table.setStyleSheet(
            "QTableWidget { background:#1a1a2e; color:#CCC; gridline-color:#333; }"
            "QHeaderView::section { background:#222; color:#00AAFF; "
            "padding:4px; border:1px solid #333; }"
        )
        self.rf_table.setMaximumHeight(140)
        rf_layout.addWidget(self.rf_table)

        rf_btn_row = QHBoxLayout()
        rf_btn_row.addWidget(QLabel("Band:"))
        self._rf_band_combo = QComboBox()
        self._rf_band_combo.setMinimumWidth(80)
        rf_btn_row.addWidget(self._rf_band_combo)
        self.btn_rf_clear_band = QPushButton("Band löschen")
        self.btn_rf_clear_band.setObjectName("reset")
        self.btn_rf_clear_band.clicked.connect(self._on_rf_clear_band)
        rf_btn_row.addWidget(self.btn_rf_clear_band)
        rf_btn_row.addStretch()
        self.btn_rf_clear_all = QPushButton("Alle löschen")
        self.btn_rf_clear_all.setObjectName("reset")
        self.btn_rf_clear_all.clicked.connect(self._on_rf_clear_all)
        rf_btn_row.addWidget(self.btn_rf_clear_all)
        rf_layout.addLayout(rf_btn_row)

        layout.addWidget(rf_box)

        # TX-Status-Polling (1 s) → Reset-Buttons disabled wenn TX aktiv
        self._tx_status_timer = QTimer(self)
        self._tx_status_timer.timeout.connect(self._update_rf_buttons_tx_state)
        self._tx_status_timer.start(1000)

        # ── Unterer Bereich: volle Breite — FT8 & Antennen ───────────
        ft8 = QGroupBox("FT8 & Antennen")
        form3 = QFormLayout(ft8)
        self.audio_freq = QSpinBox()
        self.audio_freq.setRange(800, 2800)
        self.audio_freq.setSuffix(" Hz")
        self.audio_freq.setSingleStep(50)
        self.max_decode_freq = QSpinBox()
        self.max_decode_freq.setRange(1000, 5000)
        self.max_decode_freq.setSuffix(" Hz")
        self.diversity_cycles = QComboBox()
        self.diversity_cycles.addItems(["80", "160", "240"])
        self.language_combo = QComboBox()
        self.language_combo.addItems(["Deutsch", "English"])
        form3.addRow("TX Audio-Frequenz:", _row_with_hint(self.audio_freq, "tx_freq"))
        form3.addRow("Max. Decode-Frequenz:", _row_with_hint(self.max_decode_freq, "max_decode"))
        form3.addRow("Neueinmessung nach:", _row_with_hint(self.diversity_cycles, "diversity_cycles"))
        form3.addRow("Sprache / Language:", self.language_combo)
        from PySide6.QtWidgets import QCheckBox
        self.stats_cb = QCheckBox("Statistik-Erfassung aktivieren")
        self.stats_cb.setToolTip(
            "Loggt pro Zyklus die Anzahl empfangener Stationen, SNR und Band.\n"
            "Normal + Diversity (Normal/DX) — pausiert bei Antennen-Tuning.\n"
            "Daten in statistics/<Modus>/<Band>/<Protokoll>/ (Markdown).\n"
            "Deaktiviert = kein Hintergrund-Logging, null Overhead.")
        form3.addRow("", self.stats_cb)
        self.debug_console_cb = QCheckBox("Debug-Konsole anzeigen")
        self.debug_console_cb.setToolTip("Zeigt alle Programmausgaben im unteren Fensterbereich (auch via Ctrl+D)")
        form3.addRow("", self.debug_console_cb)
        layout.addWidget(ft8)

        # ── Buttons ───────────────────────────────────────────────────
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
            msg.setStyleSheet(MSGBOX_STYLE)
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
        # Sprache
        lang = self.settings.get("language", "de")
        self.language_combo.setCurrentIndex(0 if lang == "de" else 1)
        # Tune-Leistung
        tp = self.settings.get("tune_power", 10)
        self._current_tune_power = tp
        for w, btn in self._tune_btns.items():
            btn.setChecked(w == tp)
        # Statistik + Debug-Konsole
        self.stats_cb.setChecked(self.settings.get("stats_enabled", True))
        self.debug_console_cb.setChecked(self.settings.get("debug_console_visible", False))
        # RF-Presets-Tabelle initial befüllen
        self._refresh_rf_table()
        self._update_rf_buttons_tx_state()

    # ── RF-Presets ────────────────────────────────────────────────

    def _get_rf_preset_store(self):
        parent = self.parent()
        if parent is None or not hasattr(parent, "rf_preset_store"):
            return None
        return parent.rf_preset_store

    def _get_radio_type(self) -> str:
        parent = self.parent()
        if parent is None or not hasattr(parent, "radio") or parent.radio is None:
            return "unknown"
        return getattr(parent.radio, "radio_type", "unknown")

    def _is_tx_active(self) -> bool:
        parent = self.parent()
        if parent is None or not hasattr(parent, "encoder") or parent.encoder is None:
            return False
        return bool(getattr(parent.encoder, "is_transmitting", False))

    def _refresh_rf_table(self):
        store = self._get_rf_preset_store()
        radio_type = self._get_radio_type()
        self._rf_info_label.setText(f"Aktives Radio: {radio_type}")
        self.rf_table.setRowCount(0)
        self._rf_band_combo.clear()
        if store is None:
            return
        presets = store.get_all(radio_type)
        if not presets:
            return
        self._rf_band_combo.addItems(sorted(presets.keys()))
        rows = []
        for band, watts_dict in presets.items():
            for watt, entry in watts_dict.items():
                ts = entry.get("ts", 0) or 0
                ts_str = (
                    time.strftime("%d.%m. %H:%M", time.localtime(ts)) if ts else "—"
                )
                rows.append((band, int(watt), int(entry["rf"]), ts_str))
        rows.sort(key=lambda r: (r[0], r[1]))
        self.rf_table.setRowCount(len(rows))
        for i, (band, watt, rf, ts_str) in enumerate(rows):
            self.rf_table.setItem(i, 0, QTableWidgetItem(band))
            self.rf_table.setItem(i, 1, QTableWidgetItem(f"{watt} W"))
            self.rf_table.setItem(i, 2, QTableWidgetItem(str(rf)))
            self.rf_table.setItem(i, 3, QTableWidgetItem(ts_str))

    def _update_rf_buttons_tx_state(self):
        tx_active = self._is_tx_active()
        self.btn_rf_clear_band.setEnabled(not tx_active)
        self.btn_rf_clear_all.setEnabled(not tx_active)
        tip = "Während aktivem TX nicht verfügbar" if tx_active else ""
        self.btn_rf_clear_band.setToolTip(tip)
        self.btn_rf_clear_all.setToolTip(tip)

    def _on_rf_clear_band(self):
        band = self._rf_band_combo.currentText()
        if not band:
            return
        msg = QMessageBox(self)
        msg.setWindowTitle("RF-Preset löschen")
        msg.setIcon(QMessageBox.Icon.Question)
        msg.setText(
            f"RF-Presets für {band} wirklich löschen?\n\n"
            "Closed-Loop muss bei nächster TX-Aktivierung neu von Null hochtasten."
        )
        msg.setStyleSheet(MSGBOX_STYLE)
        btn_yes = msg.addButton("Löschen", QMessageBox.ButtonRole.DestructiveRole)
        msg.addButton("Abbrechen", QMessageBox.ButtonRole.RejectRole)
        msg.exec()
        if msg.clickedButton() != btn_yes:
            return
        store = self._get_rf_preset_store()
        radio_type = self._get_radio_type()
        if store and radio_type and radio_type != "unknown":
            store.clear_band(radio_type, band)
            self._refresh_rf_table()

    def _on_rf_clear_all(self):
        radio_type = self._get_radio_type()
        msg = QMessageBox(self)
        msg.setWindowTitle("Alle RF-Presets löschen")
        msg.setIcon(QMessageBox.Icon.Warning)
        msg.setText(
            f"Alle RF-Presets für {radio_type} wirklich löschen?\n\n"
            "Closed-Loop muss bei nächster TX-Aktivierung neu von Null hochtasten."
        )
        msg.setStyleSheet(MSGBOX_STYLE)
        btn_yes = msg.addButton("Alle löschen", QMessageBox.ButtonRole.DestructiveRole)
        msg.addButton("Abbrechen", QMessageBox.ButtonRole.RejectRole)
        msg.exec()
        if msg.clickedButton() != btn_yes:
            return
        store = self._get_rf_preset_store()
        if store and radio_type and radio_type != "unknown":
            store.clear_all(radio_type)
            self._refresh_rf_table()

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
        self.settings.set("language", "de" if self.language_combo.currentIndex() == 0 else "en")
        self.settings.set("stats_enabled", self.stats_cb.isChecked())
        self.settings.set("debug_console_visible", self.debug_console_cb.isChecked())
        self.settings.save()
        self.accept()

    def _reset_defaults(self):
        """Alle Werte auf Grundeinstellungen zuruecksetzen."""
        msg = QMessageBox(self)
        msg.setWindowTitle("Grundeinstellungen")
        msg.setIcon(QMessageBox.Icon.Question)
        msg.setText("Alle Einstellungen auf Werkseinstellungen zuruecksetzen?\n\n"
                    "Rufzeichen und Locator bleiben erhalten.")
        msg.setStyleSheet(MSGBOX_STYLE)
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
