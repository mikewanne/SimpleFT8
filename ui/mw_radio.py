"""SimpleFT8 MainWindow — Radio-Verbindung, Band, Diversity, DX-Tuning Mixin."""

from __future__ import annotations

import threading
import time
from collections import deque
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, Slot
from PySide6.QtWidgets import QMessageBox, QCheckBox

if TYPE_CHECKING:
    from .main_window import MainWindow


def _show_info_once(parent, key: str, title: str, text: str, settings) -> bool:
    """Info-Dialog mit 'Nicht mehr anzeigen' Checkbox. Gibt True zurueck wenn angezeigt."""
    if settings.get(f"hide_info_{key}", False):
        return False
    dlg = QMessageBox(parent)
    dlg.setWindowTitle(title)
    dlg.setIcon(QMessageBox.Icon.Information)
    dlg.setText(text)
    cb = QCheckBox("Beim naechsten Mal nicht mehr anzeigen")
    dlg.setCheckBox(cb)
    dlg.addButton(QMessageBox.StandardButton.Ok)
    dlg.exec()
    if cb.isChecked():
        settings.set(f"hide_info_{key}", True)
        settings.save()
    return True

from radio.presets import PREAMP_PRESETS
from core.qso_state import QSOState


class RadioMixin:
    """Mixin fuer Radio-Steuerung — wird in MainWindow eingemischt.

    Enthaelt: Verbindung, Reconnect, Bandwechsel, Diversity, DX-Tuning.
    Alle self.xxx Zugriffe funktionieren weil self = MainWindow Instanz.
    """

    def _start_radio(self):
        """FlexRadio verbinden und Decoder starten (mit Auto-Retry)."""
        # Audio-Callback + Signals verbinden
        self.radio.on_audio_callback = self.decoder.feed_audio
        self.radio.error.connect(lambda msg: print(f"[Radio] {msg}"))
        self.radio.connected.connect(self._on_radio_connected)
        self.radio.disconnected.connect(self._on_radio_disconnected)

        # Decoder-Signals
        self.decoder.message_decoded.connect(self.on_message_decoded)
        self.decoder.cycle_decoded.connect(self._on_cycle_decoded)
        # v0.82 Fix E: cycle_finished feuert NACH allen message_decoded
        # → on_decoder_finished sieht den finalen state nach
        # on_message_received (Doppel-Report-Fix).
        self.decoder.cycle_finished.connect(self._on_cycle_finished)

        # Encoder
        self.encoder.set_radio(self.radio)
        self.encoder.set_decoder(self.decoder)
        self.encoder.tx_started.connect(
            lambda msg: self.control_panel.set_tx_active(True)
        )
        self.encoder.tx_started.connect(
            self._on_tx_started,
            Qt.ConnectionType.QueuedConnection,
        )
        self.encoder.tx_finished.connect(self._on_tx_finished)

        # Auto-Connect im Hintergrund
        self.control_panel.set_connection_status("searching")
        threading.Thread(
            target=self._connect_worker, daemon=True
        ).start()

    def _connect_worker(self):
        """Verbindung im Hintergrund herstellen."""
        ok = self.radio.auto_connect(max_retries=10, retry_delay=3.0)
        if not ok:
            self.control_panel.set_connection_status("disconnected")

    def _on_radio_connected(self):
        """Wird aufgerufen wenn FlexRadio verbunden ist."""
        self._reconnect_attempts = 0
        self.control_panel.set_connection_status("connected")
        # Gespeichertes Band + Frequenz setzen
        freq = self.settings.frequency_mhz
        band = self.settings.band
        self.radio.set_frequency(freq)
        self.radio.apply_ft8_preset(band=band)
        print(f"[FlexRadio] Band: {band}, Freq: {freq:.3f} MHz")
        self._update_statusbar()  # Statusbar sofort sichtbar nach Connect
        # Normal-Preset laden (eigener Key, nie aus Diversity-Presets)
        normal_preset = self.settings.get_normal_preset(band)
        gain = normal_preset.get("gain", PREAMP_PRESETS.get(band, 10))
        self.radio.set_rfgain(gain)
        label = "kalibriert" if normal_preset.get("measured") else "Standard"
        self.statusBar().showMessage(f"Normal Preset {band}: G{gain}dB ({label})", 4000)
        print(f"[FlexRadio] Normal Preset {band}: G{gain}dB ({label})")
        # Leistung: RF-Preset laden (oder Settings-Default falls noch nichts gespeichert)
        power_preset = self.settings.get("power_preset", 10)
        self._power_target = power_preset
        self._apply_rf_preset()
        self.radio.set_power(self._rfpower_current)
        self.control_panel.set_power_preset(power_preset)
        # TX Audio-Drive (mic_level) setzen — steuert wieviel Leistung die PA tatsaechlich abgibt
        tx_level = min(75, self.settings.get("tx_level", 75))  # max 75%
        self.radio.set_tx_level(tx_level / 100.0)
        self.control_panel.tx_level_bar.setValue(tx_level)
        self.control_panel.tx_level_label.setText(f"TX-Pegel: {tx_level}%")
        self.decoder.set_quality(self._rx_mode)  # Qualität vom aktiven Modus abhängig
        # DT-Korrektur initialisieren mit aktuellem Modus+Band
        mode = self.settings.get("mode", "FT8")
        from core import ntp_time as _ntp
        _ntp.set_mode(mode, band)
        # CQ-Freq Dwell/Recalc-Intervall fuer aktuellen Modus
        self._diversity_ctrl.set_mode(mode)
        self.decoder.start()
        self.radio.create_tx_stream()
        # Meter an GUI koppeln
        self.radio.meter_update.connect(self._on_meter_update)
        self.radio.swr_alarm.connect(self._on_swr_alarm)

    def _on_radio_disconnected(self):
        """Verbindung verloren — unbegrenzt reconnecten mit Exponential Backoff."""
        self.control_panel.set_connection_status("disconnected")
        self.decoder.stop()
        self._reconnect_attempts += 1
        self._reconnect_countdown = 0

        # QTimer im GUI-Thread erstellen (darf NICHT im Worker-Thread sein)
        from PySide6.QtCore import QTimer
        if not hasattr(self, '_countdown_timer'):
            self._countdown_timer = QTimer(self)
            self._countdown_timer.timeout.connect(self._on_countdown_tick)
        self._countdown_timer.start(1000)

        self.control_panel.set_connection_status("reconnecting")
        threading.Thread(target=self._reconnect_worker, daemon=True).start()

    def _on_countdown_tick(self):
        """Countdown-Anzeige im GUI-Thread aktualisieren."""
        secs = self._reconnect_countdown
        if secs > 0:
            self.control_panel.connection_label.setText(
                f"RADIO: Reconnect in {secs}s..."
            )
            self.control_panel.connection_label.setStyleSheet(
                "color: #FFD700; font-family: Menlo; font-size: 12px; font-weight: bold;"
            )

    def _reconnect_worker(self):
        """Reconnect-Schleife im Hintergrund (Exponential Backoff, unbegrenzt)."""
        def _on_waiting(secs_remaining: int):
            # Thread-safe: nur primitiven int setzen, QTimer liest ihn
            self._reconnect_countdown = secs_remaining

        ok = self.radio.reconnect_forever(on_waiting=_on_waiting)
        self._reconnect_countdown = 0

        # Timer stoppen (Thread-sicher via invokeMethod)
        from PySide6.QtCore import QMetaObject, Qt
        if hasattr(self, '_countdown_timer'):
            QMetaObject.invokeMethod(
                self._countdown_timer, "stop",
                Qt.ConnectionType.QueuedConnection,
            )

        if not ok:
            self.control_panel.set_connection_status("disconnected")

    @Slot(bool)
    def _on_rx_panel_toggled(self, active: bool):
        """RX ON/OFF vom Panel — bei OFF sofort auf ANT1 und Diversity-Stop."""
        if not active and self._rx_mode == "diversity" and self.radio.ip:
            band = self.settings.band
            gain = PREAMP_PRESETS.get(band, 10)
            def _reset_ant():
                self.radio.set_rx_antenna("ANT1")
                self.radio.set_rfgain(gain)
            threading.Thread(target=_reset_ant, daemon=True).start()
            with self._diversity_lock:
                self._diversity_current_ant = "A1"
        # RX-Liste + QSO-Panel leeren bei RX ON/OFF (Antennen-Wechsel oder Neustart)
        self.rx_panel.table.setRowCount(0)
        self._diversity_stations = {}
        self._normal_stations = {}
        self.qso_panel.log_view.clear()
        self.control_panel.update_decode_count(0)
        self.control_panel.set_rx_active(active)
        # Rotes Banner im Fenster wenn RX deaktiviert
        self._rx_warning_label.setVisible(not active)

    @Slot(str)
    def _on_mode_changed(self, mode: str):
        # v0.75/v0.78: aktive Power-Modi bei FT-Mode-Wechsel (FT8/FT4/FT2) stoppen
        if hasattr(self, "_auto_hunt") and self._auto_hunt.active:
            self._auto_hunt.stop_auto_hunt("ft_mode_change")
        if hasattr(self, "_omni_tx") and self._omni_tx.active:
            self._omni_tx.stop_omni_tx("ft_mode_change")
        self.settings.set("mode", mode)
        self.timer.set_mode(mode)
        # CQ-Freq Dwell/Recalc-Intervall an neuen Modus anpassen
        self._diversity_ctrl.set_mode(mode)
        # Decoder + Encoder auf neues Protokoll umschalten
        self.decoder.set_protocol(mode)
        self.encoder.set_protocol(mode)
        self.qso_sm._mode = mode
        # Even/Odd Anzeige: Slot-Dauer fuer QSO-Panel
        _DURATIONS = {"FT8": 15.0, "FT4": 7.5, "FT2": 3.8}
        self.qso_panel._cycle_duration = _DURATIONS.get(mode, 15.0)
        # Warmup: 6 Zyklen keine Stats nach Protokollwechsel
        self._stats_warmup_cycles = 6
        # RX-Liste + QSO-Panel leeren bei Mode-Wechsel (neuer Modus = neuer Kontext)
        self.rx_panel.table.setRowCount(0)
        self._diversity_stations = {}
        self._normal_stations = {}
        self.control_panel.update_decode_count(0)
        self.qso_panel.log_view.clear()
        self.qso_panel.status_label.setText(f"Modus: {mode}")
        # PSK-Reporter zuruecksetzen bei Moduswechsel
        self.control_panel.psk_label.setText("PSK:  —")
        # CQ stoppen bei Mode-Wechsel
        if self.qso_sm.cq_mode:
            self.qso_sm.stop_cq()
            self.control_panel.set_cq_active(False)
        # Frequenz fuer neuen Modus setzen (FT4 hat andere Dial-Frequenzen)
        from core.protocol import BAND_FREQUENCIES
        band = self.settings.band
        mode_freqs = BAND_FREQUENCIES.get(mode, {})
        if band in mode_freqs and self.radio.ip:
            freq = mode_freqs[band]
            self.radio.set_frequency(freq)
            self.control_panel.set_freq_display(freq, tune_active=False)
            print(f"[Mode] {mode} auf {band}: {freq:.3f} MHz")
        # RX-Filter pro Modus: FT2 braucht breiteren Filter (150 Hz Signalbreite)
        _FILTERS = {"FT8": (100, 3100), "FT4": (100, 3100), "FT2": (100, 4000)}
        flo, fhi = _FILTERS.get(mode, (100, 3100))
        if self.radio.ip:
            self.radio.set_rx_filter(flo, fhi)
        # DT-Korrektur: gespeicherten Wert fuer neuen Modus+Band laden
        from core import ntp_time
        ntp_time.set_mode(mode, band)
        # Diversity: Preset-Check mit Dialog + ggf. Pipeline
        if self._rx_mode == "diversity":
            scoring = getattr(self._diversity_ctrl, 'scoring_mode', 'normal')
            self._check_diversity_preset(band, mode, scoring)
            return  # _check_diversity_preset ruft _update_statusbar auf
        # Normal-Modus: Warnung wenn kein mode-spezifisches Gain-Preset vorhanden
        if self.radio.ip:
            _std_store = getattr(self, '_standard_store', None)
            if _std_store and _std_store.get(band, mode) is None:
                self.statusBar().showMessage(
                    f"Kein Gain-Preset für {band}/{mode} — bitte KALIBRIEREN", 6000
                )
                self.control_panel.dx_info.setText(f"Kein Preset ({mode})")
                self.control_panel.dx_info.setStyleSheet("color: #FF6600;")
        self._update_statusbar()

    @Slot(str)
    def _on_band_changed(self, band: str):
        # Race-Schutz: ausstehende TUNE-Callbacks ungueltig machen, sonst ruft
        # ein 5-Sek-Timer aus dem alten Band-Kontext _enable_diversity() fuer
        # das jetzt verlassene Band auf.
        self._tune_token = None
        self.settings.set("band", band)
        freq = self.settings.frequency_mhz
        self._has_sent_cq = False

        # ── BANDWECHSEL STOPPT ALLES ──────────────────────────
        # CQ-Modus sofort stoppen
        if self.qso_sm.cq_mode or self.qso_sm.state != QSOState.IDLE:
            self.qso_sm.stop_cq()
            self.qso_sm.cancel()
            self.control_panel.set_cq_active(False)
        # TX stoppen falls gerade gesendet wird
        if self.encoder.is_transmitting:
            self.encoder.abort()
            if self.radio.ip:
                self.radio.ptt_off()
        # QSO-Panel (Live Log) leeren — neues Band = neuer Kontext
        self.qso_panel.log_view.clear()
        self.qso_panel.status_label.setText("Bandwechsel")

        # Warmup: 60s keine Stats nach Bandwechsel
        import time as _time
        self._stats_warmup_cycles = 6

        # Empfangsliste komplett leeren bei Bandwechsel
        self.rx_panel.table.setRowCount(0)
        self._diversity_stations = {}
        self._normal_stations = {}
        self.control_panel.update_decode_count(0)
        # Diversity Controller bei Bandwechsel: Neueinmessung + Histogram leeren
        self._diversity_ctrl.on_band_change()
        self.control_panel.update_freq_histogram(
            self._diversity_ctrl.get_histogram_data())
        # Auto-Hunt: Cooldowns loeschen bei Bandwechsel
        if self._auto_hunt.active:
            self._auto_hunt.set_band(band)
            self._auto_hunt.on_band_change()
        # v0.78: OMNI-TX bei Bandwechsel stoppen
        if hasattr(self, "_omni_tx") and self._omni_tx.active:
            self._omni_tx.stop_omni_tx("band_change")
        if self._rx_mode == "diversity":
            self.control_panel.update_diversity_ratio("50:50", "measure", 0,
                                                      self._diversity_ctrl.MEASURE_CYCLES)
            self.control_panel.update_diversity_counts(0, 0)
        if self.radio.ip:
            self.radio.set_frequency(freq)
            self.radio.apply_ft8_preset(band=band)
            if self._rx_mode == "diversity":
                # Diversity: 2. Slice auch umtunen + Preset anpassen
                if self.radio.has_secondary_slice():
                    gain_b = PREAMP_PRESETS.get(band, 10) + 10
                    self.radio.set_rfgain_secondary(gain_b)
                    self.control_panel.dx_info.setText(
                        f"ANT1+ANT2 (Gain {gain_b})"
                    )
            elif self._rx_mode == "normal":
                self._apply_normal_mode()
        # Per-Band TX Level laden (Auto-Regelung speichert pro Band)
        band_levels = self.settings.get("tx_levels_per_band", {})
        saved_level = min(75, band_levels.get(band, 75))  # max 75% (Clipschutz-Anker)
        self.radio.set_tx_level(saved_level / 100.0)
        self.control_panel.tx_level_bar.setValue(saved_level)
        self.control_panel.tx_level_label.setText(f"TX-Pegel: {saved_level}%")
        self._fwdpwr_samples.clear()   # Alte Messwerte verwerfen
        self._apply_rf_preset()  # lädt aus RFPresetStore (mit Hybrid-Strategie) oder Settings-Default
        if self.radio.ip:
            self.radio.set_power(self._rfpower_current)
        # DT-Korrektur: gespeicherten Wert fuer neues Band laden
        from core import ntp_time as _ntp
        _ntp.set_band(band)
        # PSK-Reporter: alte Band-Daten löschen + Timer neu starten (2 Min Delay)
        self.control_panel.psk_label.setText("PSK:  —")
        _psk_t = getattr(self, '_psk_timer', None)
        if _psk_t:
            _psk_t.stop()
            self._psk_first_fetch = True
            _psk_t.setInterval(120000)
            _psk_t.start()
        # Propagations-Balken sofort fuer neues Band aktualisieren
        # (sonst 60s Lag bis zum naechsten Polling-Tick → Pulsier-Animation
        # wuerde am alten Band haengen)
        self._update_propagation_ui()
        # Karten-Dialog (falls offen): RX-History des neuen Bandes nachladen
        # (v0.73). Zeigt sofort die letzten 60 Min Empfangsdaten.
        if self._direction_map_dialog is not None:
            self._reload_rx_history_on_map(band)

        # v0.87 Bandpilot: ggf. RX-Modus auf Empfehlung wechseln.
        # Wenn er aktiv geworden ist, hat _set_rx_mode_direct bereits den
        # passenden Preset-Dialog gefahren — Standard-Diversity-Preset-Pfad
        # ueberspringen, sonst doppelter Dialog.
        bandpilot_acted = self._maybe_apply_bandpilot(band)

        # Diversity: Preset-Check mit Dialog + ggf. Pipeline
        if not bandpilot_acted and self._rx_mode == "diversity":
            ft_mode = self.settings.get("mode", "FT8")
            scoring = getattr(self._diversity_ctrl, 'scoring_mode', 'normal')
            self._check_diversity_preset(band, ft_mode, scoring)
            return  # _check_diversity_preset ruft _update_statusbar auf
        self._update_statusbar()

    @Slot(str)
    def _on_rx_mode_changed(self, mode: str):
        """RX-Modus umschalten (nur 'normal' oder 'diversity')."""
        if not self.radio.ip:
            self.control_panel.set_rx_mode("normal")
            return

        old_mode = self._rx_mode
        # v0.78: bei RX-Mode-Wechsel Easter-Egg-Override und aktive Power-Modi stoppen
        if mode != old_mode:
            if hasattr(self, "_omni_tx") and self._omni_tx.active:
                self._omni_tx.stop_omni_tx("rx_mode_change")
            if hasattr(self, "_auto_hunt") and self._auto_hunt.active:
                self._auto_hunt.stop_auto_hunt("rx_mode_change")
            self._easter_egg_active = False

        # Warmup: 60s keine Stats nach Moduswechsel
        import time as _time
        self._stats_warmup_cycles = 6

        # Alten Modus sauber beenden + Liste immer leeren bei Wechsel
        if old_mode == "diversity":
            self._disable_diversity()
        self.rx_panel.table.setRowCount(0)
        self.qso_panel.log_view.clear()
        self.control_panel.update_decode_count(0)

        # Decode-Qualitaet automatisch: normal=schnell, diversity=tief
        self.decoder.set_quality(mode)

        # Neuen Modus aktivieren
        if mode == "normal":
            self._rx_mode = "normal"
            self._normal_stations = {}
            self._apply_normal_mode()
            self.control_panel._freq_hist.setVisible(False)
            self.control_panel.btn_diversity.setText("DIVERSITY")  # Reset Button-Text
        elif mode == "diversity":
            # Scoring-Modus waehlen — vertikaler Custom-Dialog
            from PySide6.QtWidgets import QDialog, QVBoxLayout, QPushButton, QLabel, QFrame
            _dlg = QDialog(self)
            _dlg.setWindowTitle("Diversity — Modus waehlen")
            _dlg.setStyleSheet("""
                QDialog { background-color: #1a1a2e; }
                QLabel  { color: #CCCCCC; font-family: Menlo; font-size: 13px;
                          padding: 8px 0 12px 0; }
                QLabel#lbl_mode_title {
                    color: #88AACC; background-color: #1a1a2e;
                    padding: 10px 0px; border-radius: 4px;
                    qproperty-alignment: AlignCenter;
                }
                QPushButton {
                    background-color: #2a2a3e; color: #CCCCCC;
                    border: 1px solid #444; border-radius: 5px;
                    font-family: Menlo; font-size: 13px;
                    padding: 10px 20px; min-width: 220px;
                }
                QPushButton:hover { background-color: #3a3a5e; }
                QPushButton#btn_cancel {
                    background-color: #1a1a1a; color: #888;
                    border: 1px solid #333;
                }
                QPushButton#btn_cancel:hover { background-color: #2a2a2a; color: #AAA; }
            """)
            _lay = QVBoxLayout(_dlg)
            _lay.setContentsMargins(24, 16, 24, 16)
            _lay.setSpacing(8)
            _lbl = QLabel("Welchen Modus verwenden?")
            _lbl.setObjectName("lbl_mode_title")
            _lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            _lay.addWidget(_lbl)
            _btn_std = QPushButton("Diversity Standard")
            _btn_dx  = QPushButton("Diversity DX")
            _lay.addWidget(_btn_std)
            _lay.addWidget(_btn_dx)
            _sep = QFrame()
            _sep.setFrameShape(QFrame.Shape.HLine)
            _sep.setStyleSheet("color: #333; margin: 4px 0;")
            _lay.addWidget(_sep)
            _btn_cancel = QPushButton("Abbruch")
            _btn_cancel.setObjectName("btn_cancel")
            _lay.addWidget(_btn_cancel)
            _result = [None]
            _btn_std.clicked.connect(lambda: (_result.__setitem__(0, "normal"), _dlg.accept()))
            _btn_dx.clicked.connect(lambda:  (_result.__setitem__(0, "dx"),     _dlg.accept()))
            _btn_cancel.clicked.connect(_dlg.reject)
            _dlg.exec()
            if _result[0] is None:
                self.control_panel.set_rx_mode("normal")
                self._update_statusbar()
                return
            scoring = _result[0]
            self._activate_diversity_with_scoring(scoring)

        # v0.78: Defensive — Mode-Coupling-Update auch wenn _apply_normal_mode /
        # _enable_diversity nicht direkt durchgelaufen sind (early-return-Pfade)
        if hasattr(self, "_easter_egg_active"):
            self._update_button_visibility()
        self._update_statusbar()

    def _activate_diversity_with_scoring(self, scoring: str):
        """Diversity aktivieren mit explizitem scoring ('normal'|'dx').

        Wird sowohl aus dem Standard/DX-Dialog (User-Klick auf btn_diversity)
        als auch vom Bandpilot (programmatisch via _set_rx_mode_direct)
        aufgerufen — kein Code-Duplikat zwischen beiden Pfaden.

        Pruefung: Preset-Store auf 2h-Frist → Dialog "Weiter/Neu messen".
        Bei "Weiter" → _enable_diversity. Bei "Neu" oder fehlend Preset →
        volle Pipeline (Tunen → Gain → Einmessen).
        """
        self._rx_mode = "diversity"
        self._diversity_stations = {}
        label = "DIVERSITY DX" if scoring == "dx" else "DIVERSITY"
        self.control_panel.btn_diversity.setText(label)

        # Preset-Store pruefen — 2h-Frist pro Band+FTMode
        band = self.settings.band
        ft_mode = self.settings.mode
        store = getattr(self, '_dx_store', None) if scoring == "dx" else getattr(self, '_standard_store', None)
        if store and store.is_valid(band, ft_mode):
            age = store.get_age_minutes(band, ft_mode)
            mode_label = "Diversity DX" if scoring == "dx" else "Diversity Standard"
            from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel
            _dlg = QDialog(self)
            _dlg.setWindowTitle("Diversity Setup")
            _dlg.setStyleSheet("""
                QDialog, QWidget { background-color: #1a1a2e; }
                QLabel { color: #CCCCCC; font-family: Menlo; font-size: 13px; background-color: #1a1a2e; }
                QLabel#lbl_title { color: #88AACC; font-size: 14px; font-weight: bold; padding-bottom: 4px; }
                QPushButton {
                    background-color: #2a2a3e; color: #CCCCCC;
                    border: 1px solid #444; border-radius: 5px;
                    font-family: Menlo; font-size: 13px;
                    padding: 8px 20px; min-width: 120px;
                }
                QPushButton:hover { background-color: #3a3a5e; }
                QPushButton#btn_weiter { background-color: #1a3a6e; border-color: #4488cc; }
                QPushButton#btn_weiter:hover { background-color: #2a4a8e; }
            """)
            _lay = QVBoxLayout(_dlg)
            _lay.setContentsMargins(24, 20, 24, 20)
            _lay.setSpacing(10)
            lbl_title = QLabel(f"{band} {ft_mode} — {mode_label}")
            lbl_title.setObjectName("lbl_title")
            lbl_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl_msg = QLabel(f"Kalibrierungsdaten vorhanden ({age} Min. alt).\nWeiter oder neu messen?")
            lbl_msg.setAlignment(Qt.AlignmentFlag.AlignCenter)
            _lay.addWidget(lbl_title)
            _lay.addWidget(lbl_msg)
            _btn_row = QHBoxLayout()
            _btn_row.setSpacing(12)
            btn_new  = QPushButton("Neu messen")
            btn_use  = QPushButton("Weiter")
            btn_use.setObjectName("btn_weiter")
            _btn_row.addWidget(btn_new)
            _btn_row.addWidget(btn_use)
            _lay.addLayout(_btn_row)
            _choice = [False]
            btn_use.clicked.connect(lambda: (_choice.__setitem__(0, True), _dlg.accept()))
            btn_new.clicked.connect(lambda: _dlg.accept())
            _dlg.exec()
            if _choice[0]:
                print(f"[Diversity] Preset gueltig ({age} Min.) — ueberspringe Pipeline")
                self._enable_diversity(scoring_mode=scoring)
                return

        # Volle Pipeline: Tunen → Gain-Messung → Einmessen
        gain_scoring = "snr" if scoring == "dx" else "stations"
        print(f"[Diversity] Starte Pipeline ({scoring.upper()}, Gain: {gain_scoring})")
        self._pending_dx_diversity = True
        self._pending_diversity_scoring = scoring
        self._start_dx_tuning(scoring_mode=gain_scoring)

    # ── Bandpilot ────────────────────────────────────────────────────────────

    def _current_rx_mode_string(self) -> str | None:
        """Aktueller RX-Modus als Bandpilot-String.

        Returns: 'normal' | 'diversity_normal' | 'diversity_dx' | None
                 (None bei dx_tuning).
        """
        if self._rx_mode == "normal":
            return "normal"
        if self._rx_mode == "diversity":
            scoring = getattr(self._diversity_ctrl, "scoring_mode", "normal")
            return "diversity_dx" if scoring == "dx" else "diversity_normal"
        return None

    def _bandpilot_label(self, target: str) -> str:
        """Bandpilot-Empfehlungs-String → User-friendly Label."""
        return {
            "normal":           "Normal",
            "diversity_normal": "Diversity Standard",
            "diversity_dx":     "Diversity DX",
        }.get(target, target)

    def _set_rx_mode_direct(self, target: str):
        """Programmatischer RX-Modus-Wechsel — umgeht den Standard/DX-Dialog.

        Wird vom Bandpilot aufgerufen wenn aufgrund der Statistik ein
        bestimmter Modus empfohlen wird.

        Args:
            target: 'normal' | 'diversity_normal' | 'diversity_dx'.
        """
        current = self._current_rx_mode_string()
        if current == target:
            return  # nichts zu tun

        if target == "normal":
            if self._rx_mode == "diversity":
                self._disable_diversity()
            self._rx_mode = "normal"
            self._apply_normal_mode()
            self.control_panel.set_rx_mode("normal")
            self.control_panel.btn_diversity.setText("DIVERSITY")
            self.control_panel._freq_hist.setVisible(False)
        elif target in ("diversity_normal", "diversity_dx"):
            scoring = "normal" if target == "diversity_normal" else "dx"
            if self._rx_mode == "diversity":
                # Modus-Wechsel innerhalb Diversity (Standard ↔ DX)
                self._disable_diversity()
            self.control_panel.set_rx_mode("diversity")
            self._activate_diversity_with_scoring(scoring)

        if hasattr(self, "_easter_egg_active"):
            self._update_button_visibility()
        self._update_statusbar()

    def _maybe_apply_bandpilot(self, band: str) -> bool:
        """Bandpilot-Empfehlung fuer Band+aktuelle UTC-Stunde anwenden.

        Returns:
            True wenn ein Modus-Wechsel angefordert wurde (Caller skippt
            den normalen Diversity-Preset-Check). False sonst.

        Verhalten je ``bandpilot_mode``:
            - ``"off"``: gar nichts.
            - ``"auto"``: bei ``decision == "switch"`` wird Toast gezeigt
              + ``_set_rx_mode_direct(decision_mode)`` aufgerufen.
            - ``"manual"``: bei ``top1 != current_mode`` Manuell-Dialog,
              sonst stillschweigend bestaetigt.
        """
        from datetime import datetime, timezone

        if not hasattr(self, "_bandpilot"):
            return False  # Init-Schutz (sollte nicht passieren)

        bp_mode = self.settings.get("bandpilot_mode", "off")
        if bp_mode == "off":
            return False

        current = self._current_rx_mode_string()
        if current is None:
            # dx_tuning laeuft → Bandpilot still
            return False

        utc_hour = datetime.now(timezone.utc).hour

        try:
            rec = self._bandpilot.recommend(band, utc_hour, current)
        except Exception as e:
            print(f"[Bandpilot] Aggregations-Fehler: {e}")
            return False

        if rec is None:
            self._show_bandpilot_insufficient_data(band, utc_hour)
            return False

        if bp_mode == "auto":
            return self._apply_bandpilot_auto(band, utc_hour, rec)
        if bp_mode == "manual":
            return self._apply_bandpilot_manual(band, utc_hour, rec, current)
        return False

    def _apply_bandpilot_auto(
        self, band: str, utc_hour: int, rec: dict,
    ) -> bool:
        """Auto-Modus: Toast zeigen, bei switch Modus wechseln.

        TX-Schutz (V3-AK 7): Wenn encoder gerade transmittet, Modus-
        Wechsel bis ``tx_finished`` verzoegern.
        """
        if rec["decision"] == "no_change":
            return False
        target = rec["decision_mode"]

        if not self.encoder.is_transmitting:
            # Sofort wechseln
            self._show_bandpilot_auto_toast(band, utc_hour, rec)
            self._set_rx_mode_direct(target)
            return True

        # TX laeuft → verzoegern bis tx_finished
        self._show_bandpilot_auto_toast(band, utc_hour, rec)
        self._bandpilot_pending = (band, utc_hour, rec, target)
        if not getattr(self, "_bandpilot_tx_connected", False):
            self.encoder.tx_finished.connect(self._on_bandpilot_tx_finished)
            self._bandpilot_tx_connected = True
        sb = self.statusBar() if hasattr(self, "statusBar") else None
        if sb is not None:
            from core.mode_recommender import USER_LABEL
            label = USER_LABEL.get(target, target)
            sb.showMessage(
                f"Bandpilot wechselt zu {label} nach TX-Ende", 5000)
        return True

    def _on_bandpilot_tx_finished(self):
        """tx_finished-Hook: gespeicherten Bandpilot-Wechsel ausfuehren."""
        pending = getattr(self, "_bandpilot_pending", None)
        if pending is None:
            return
        _band, _utc_hour, _rec, target = pending
        self._bandpilot_pending = None
        self._set_rx_mode_direct(target)
        sb = self.statusBar() if hasattr(self, "statusBar") else None
        if sb is not None:
            sb.showMessage("Bandpilot: Modus angewendet", 1500)

    def _apply_bandpilot_manual(
        self, band: str, utc_hour: int, rec: dict, current: str,
    ) -> bool:
        """Manuell-Modus: Dialog NUR wenn Top-1 != aktueller Modus."""
        if rec["top1"] == current:
            return False  # stillschweigend bestaetigt
        chosen = self._show_bandpilot_manual_dialog(band, utc_hour, rec, current)
        if chosen is None or chosen == current:
            return False
        self._set_rx_mode_direct(chosen)
        return True

    def _show_bandpilot_insufficient_data(self, band: str, utc_hour: int):
        """Statusbar-Hinweis 5s — V3-AK 6 / Phase 8."""
        sb = self.statusBar() if hasattr(self, "statusBar") else None
        if sb is not None:
            sb.showMessage(
                f"Bandpilot: nicht genug Daten fuer {band} um {utc_hour:02d} UTC",
                5000,
            )

    def _show_bandpilot_auto_toast(self, band: str, utc_hour: int, rec: dict):
        """3-Sekunden Self-Close-Toast mit Modus-Wahl (V3-AK 4 + 20 + 21)."""
        from ui.bandpilot_dialogs import BandpilotAutoToast
        # V3-AK 21: schnelle Bandwechsel — alten Toast schliessen
        old = getattr(self, "_bandpilot_active_toast", None)
        if old is not None:
            try:
                old.close()
            except RuntimeError:
                pass  # Qt-Object schon weg
        toast = BandpilotAutoToast(self, band, utc_hour, rec)
        self._bandpilot_active_toast = toast
        toast.show()

    def _show_bandpilot_manual_dialog(
        self, band: str, utc_hour: int, rec: dict, current: str,
    ) -> str | None:
        """Manuell-Dialog mit 3 Buttons (V3-AK 5 + 21).

        Returns: gewaehlter Code-Modus oder ``None`` (Abbruch / unveraendert).
        """
        from ui.bandpilot_dialogs import BandpilotManualDialog
        # V3-AK 21: schnelle Bandwechsel — alten Dialog schliessen
        old = getattr(self, "_bandpilot_active_dialog", None)
        if old is not None:
            try:
                old.close()
            except RuntimeError:
                pass
        dlg = BandpilotManualDialog(self, band, utc_hour, rec, current)
        self._bandpilot_active_dialog = dlg
        result = dlg.exec()
        from PySide6.QtWidgets import QDialog
        if result == QDialog.DialogCode.Accepted:
            return dlg.chosen
        return None

    def _set_cq_locked(self, locked: bool):
        """CQ + Hunt sperren waehrend Diversity-Einmessen.

        Beide Slots (Even+Odd) werden fuer Messung gebraucht!
        Hunt wuerde TX in einen Mess-Slot schieben → Messung kaputt.
        """
        self.control_panel.btn_cq.setEnabled(not locked)
        self.control_panel.btn_advance.setEnabled(not locked)
        self.control_panel.btn_cancel.setEnabled(not locked)
        # Hunt blockieren: RX-Tabelle Klicks ignorieren
        self._diversity_measuring = locked
        self.rx_panel.table.setEnabled(not locked)
        if locked:
            self.control_panel.btn_cq.setText("EINMESSEN  ⏳")
            if self.qso_sm.cq_mode:
                self.qso_sm.stop_cq()
                self.control_panel.set_cq_active(False)
                self.qso_panel.add_info("CQ gestoppt — Einmessen aktiv")
        else:
            self.control_panel.btn_cq.setText("CQ RUFEN")
            self.rx_panel.table.setEnabled(True)

    def _enable_diversity(self, scoring_mode: str = "normal"):
        """Diversity aktivieren: Antenne pro Zyklus wechseln, Stationen akkumulieren."""
        self._diversity_in_operate = False  # Transition-Guard zurücksetzen
        # RX-Liste + QSO-Panel leeren bei Antennen-Modus-Wechsel
        self.rx_panel.table.setRowCount(0)
        self._diversity_stations = {}
        self._normal_stations = {}
        self.qso_panel.log_view.clear()
        self.control_panel.update_decode_count(0)
        self._diversity_current_ant = "A1"
        self._diversity_ant_queue = deque()  # (ant, phase) Tupel
        # Settings-Wert × Modus-Multiplikator (gleiche ZEIT fuer alle Modi)
        mode = self.settings.mode
        _MULT = {"FT8": 1, "FT4": 2, "FT2": 4}
        base = self.settings.get("diversity_operate_cycles", 60)
        self._diversity_ctrl.OPERATE_CYCLES = base * _MULT.get(mode, 1)
        self._diversity_ctrl.MEASURE_CYCLES = 8 * _MULT.get(mode, 1)
        self._diversity_ctrl.scoring_mode = scoring_mode

        # Gespeichertes Preset laden (ein Eintrag enthält Gain + Ratio)
        mode = self.settings.mode
        band = self.settings.band
        store = getattr(self, '_dx_store', None) if scoring_mode == "dx" else getattr(self, '_standard_store', None)
        preset = store.get(band, mode) if store else None

        # Ratio NIE aus Cache laden — Pattern ist band-spezifisch (ANT1 hat
        # je nach Band ganz andere Resonanz-Eigenschaften). Cache-"Weiter" gilt
        # NUR fuer Gain (Hardware-Eigenschaft des RX-Verstaerkers).
        # Ratio wird IMMER neu gemessen — 8 Slots Phase=measure, dann _evaluate.
        self._diversity_ctrl.reset()
        self._set_cq_locked(True)
        self._set_gain_measure_lock(True)
        print(f"[Diversity] Phase=measure — Ratio wird neu eingemessen ({scoring_mode.upper()})")
        self.control_panel.update_diversity_ratio(
            "50:50", "measure", 0,
            self._diversity_ctrl.MEASURE_CYCLES,
            scoring_mode=scoring_mode)
        self.control_panel.update_diversity_counts(0, 0)

        ft_mode = mode  # bereits oben gesetzt

        if preset and "ant1_gain" in preset:
            # Preset vorhanden: per-Antenne optimierte Gains laden + sofort ans Radio
            self._diversity_ant1_gain = preset["ant1_gain"]
            self._diversity_ant2_gain = preset["ant2_gain"]
            measured = preset.get("measured", "?")
            if self.radio.ip:
                self.radio.set_rx_antenna("ANT1")
                self.radio.set_rfgain(self._diversity_ant1_gain)
            self.control_panel.dx_info.setText(
                f"ANT1(G{self._diversity_ant1_gain}) + "
                f"ANT2(G{self._diversity_ant2_gain})"
            )
            print(
                f"[Diversity] Preset geladen: ANT1 G{self._diversity_ant1_gain}, "
                f"ANT2 G{self._diversity_ant2_gain} (gemessen {measured})"
            )
        else:
            # Kein Preset: Standard-Gains + Hinweis
            self._diversity_ant1_gain = PREAMP_PRESETS.get(band, 10)
            self._diversity_ant2_gain = PREAMP_PRESETS.get(band, 10) + 10
            self.control_panel.dx_info.setText(
                f"ANT1(G{self._diversity_ant1_gain}) + "
                f"ANT2(G{self._diversity_ant2_gain})"
            )
            print(f"[Diversity] AKTIV — Standard-Gains, kein Preset fuer {band}")

        # v0.78: Mode-Coupling Buttons aktualisieren (Diversity aktiv → Power-Buttons sichtbar)
        if hasattr(self, "_easter_egg_active"):
            self._update_button_visibility()

    def _disable_diversity(self):
        """Diversity deaktivieren: zurueck auf ANT1."""
        # RX-Liste + QSO-Panel leeren bei Antennen-Modus-Wechsel
        self.rx_panel.table.setRowCount(0)
        self._diversity_stations = {}
        self._normal_stations = {}
        self.qso_panel.log_view.clear()
        self.control_panel.update_decode_count(0)
        self._diversity_ctrl.reset()
        self._rx_mode = "normal"
        self._apply_normal_mode()
        self.control_panel.set_rx_mode("normal")
        self.control_panel.dx_info.setText("")
        self.control_panel.update_diversity_counts(0, 0)
        print("[Diversity] Deaktiviert")

    def _on_diversity_remeasure(self):
        """NEU-Button: Diversity sofort neu einmessen (erzwungen)."""
        if self._rx_mode != "diversity":
            return
        import time as _time
        self._stats_warmup_cycles = 99999  # Blockiert bis nach Einmessen+Warmup
        print("[Diversity] Manuelle Neueinmessung gestartet")
        self._diversity_ctrl.start_measure()
        self._set_cq_locked(True)
        self.control_panel.update_diversity_ratio(
            "50:50", "measure", 0,
            self._diversity_ctrl.MEASURE_CYCLES,
            scoring_mode=self._diversity_ctrl.scoring_mode)

    def _check_diversity_preset(self, band: str, ft_mode: str, scoring: str) -> None:
        """Preset-Check bei Band/Modus-Wechsel mit aktiver Diversity.

        is_valid + < 2h → Dialog (Weiter / Neu messen).
        Kein Preset oder abgelaufen → sofort Pipeline starten.
        """
        if not getattr(self, 'radio', None) or not self.radio.ip:
            return
        store = (getattr(self, '_dx_store', None) if scoring == "dx"
                 else getattr(self, '_standard_store', None))
        if store and store.is_valid(band, ft_mode):
            age = store.get_age_minutes(band, ft_mode)
            mode_label = "Diversity DX" if scoring == "dx" else "Diversity Standard"
            from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel
            _dlg = QDialog(self)
            _dlg.setWindowTitle("Diversity Setup")
            _dlg.setStyleSheet("""
                QDialog, QWidget { background-color: #1a1a2e; }
                QLabel { color: #CCCCCC; font-family: Menlo; font-size: 13px; background-color: #1a1a2e; }
                QLabel#lbl_title { color: #88AACC; font-size: 14px; font-weight: bold; padding-bottom: 4px; }
                QPushButton {
                    background-color: #2a2a3e; color: #CCCCCC;
                    border: 1px solid #444; border-radius: 5px;
                    font-family: Menlo; font-size: 13px;
                    padding: 8px 20px; min-width: 120px;
                }
                QPushButton:hover { background-color: #3a3a5e; }
                QPushButton#btn_weiter { background-color: #1a3a6e; border-color: #4488cc; }
                QPushButton#btn_weiter:hover { background-color: #2a4a8e; }
            """)
            _lay = QVBoxLayout(_dlg)
            _lay.setContentsMargins(24, 20, 24, 20)
            _lay.setSpacing(10)
            lbl_title = QLabel(f"{band} {ft_mode} — {mode_label}")
            lbl_title.setObjectName("lbl_title")
            lbl_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl_msg = QLabel(
                f"Gain-Kalibrierung vorhanden ({age} Min. alt).\n"
                f"\"Weiter\" = Gain uebernehmen, Ratio wird neu eingemessen (5s TUNE).\n"
                f"\"Neu messen\" = Gain + Ratio komplett neu."
            )
            lbl_msg.setAlignment(Qt.AlignmentFlag.AlignCenter)
            _lay.addWidget(lbl_title)
            _lay.addWidget(lbl_msg)
            _btn_row = QHBoxLayout()
            _btn_row.setSpacing(12)
            btn_new = QPushButton("Neu messen")
            btn_use = QPushButton("Weiter")
            btn_use.setObjectName("btn_weiter")
            _btn_row.addWidget(btn_new)
            _btn_row.addWidget(btn_use)
            _lay.addLayout(_btn_row)
            _choice = [False]
            btn_use.clicked.connect(lambda: (_choice.__setitem__(0, True), _dlg.accept()))
            btn_new.clicked.connect(lambda: _dlg.accept())
            _dlg.exec()
            if _choice[0]:
                print(f"[Diversity] {band}/{ft_mode}: Gain ({age} Min.) uebernommen, Ratio neu, TUNE laeuft")
                # TUNE zuerst (ANT1 abgleichen falls off-band), danach _enable_diversity
                # mit reset() → Phase=measure → 8 Slots Re-Measurement
                self._start_tune_only(
                    after_tune_callback=lambda: self._enable_diversity(scoring_mode=scoring)
                )
                self._update_statusbar()
                return
        # Kein Preset, abgelaufen oder "Neu messen" → volle Pipeline
        gain_scoring = "snr" if scoring == "dx" else "stations"
        print(f"[Diversity] {band}/{ft_mode}: kein/abgelaufenes Preset → Pipeline")
        self._pending_dx_diversity = True
        self._pending_diversity_scoring = scoring
        self._start_dx_tuning(scoring_mode=gain_scoring)

    def _handle_dx_tuning(self):
        """KALIBRIEREN-Button: Tunen + Gain-Messung fuer aktuelles Band, immer ueberschreiben."""
        scoring = getattr(self._diversity_ctrl, 'scoring_mode', 'normal')
        gain_scoring = "snr" if scoring == "dx" else "stations"
        self._start_dx_tuning(scoring_mode=gain_scoring)

    def _start_tune_only(self, after_tune_callback=None) -> None:
        """TUNE allein — fuer Bandwechsel mit Cache-"Weiter"-Pfad.

        Sendet 5s Carrier auf der aktuellen Frequenz auf ANT1, damit ein
        externer/interner Tuner sich auf die Band-Last einstimmen kann.
        Danach wird `after_tune_callback` (z.B. `_enable_diversity`) gerufen.

        Race-Schutz: `self._tune_token` wird neu gesetzt. Wenn waehrend der
        5s ein Bandwechsel passiert (`_on_band_changed` setzt das Token auf
        None), wird der `_after_tune` Callback ignoriert und `_enable_diversity`
        nicht mehr fuer das alte Band gerufen.

        Offline-Schutz: Wenn `radio.ip` waehrend TUNE leer wird, kein Crash —
        `_after_tune` skippt `tune_off()`/Callback.
        """
        if not self.radio.ip:
            if after_tune_callback:
                after_tune_callback()
            return

        from PySide6.QtCore import QTimer

        self._tune_token = object()
        _token = self._tune_token
        tune_power = self.settings.get("tune_power", 10)

        self.statusBar().showMessage(
            f"TUNEN — {tune_power}W auf ANT1 fuer 5s ...", 0)
        self.radio.set_rfpower_direct(tune_power)
        self.radio.tune_on()

        def _after_tune():
            if getattr(self, '_tune_token', None) is not _token:
                return  # Bandwechsel waehrend TUNE — Callback ungueltig
            if not self.radio.ip:
                return  # Radio offline gegangen — kein crash
            self.radio.tune_off()
            self.radio.set_power(self.settings.get("power_preset", 15))
            if after_tune_callback:
                after_tune_callback()

        QTimer.singleShot(5000, _after_tune)

    def _start_dx_tuning(self, scoring_mode: str = "snr"):
        """Diversity Pipeline: TUNE (automatisch) → Gain-Messung → Einmessen."""
        import time as _time
        self._stats_warmup_cycles = 99999  # Blockiert bis nach Einmessen+Warmup
        self._gain_scoring_mode = scoring_mode
        from PySide6.QtCore import QTimer

        # GUI sofort sperren — bleibt bis Einmessen fertig
        self._set_gain_measure_lock(True)

        # SICHERHEIT: TX SOFORT stoppen
        if self.qso_sm.cq_mode:
            self.qso_sm.stop_cq()
            self.control_panel.set_cq_active(False)
        if self.qso_sm.state != QSOState.IDLE:
            self.qso_sm.cancel()
        if self.encoder.is_transmitting:
            self.encoder.abort()
            if self.radio.ip:
                self.radio.ptt_off()

        tune_power = self.settings.get("tune_power", 10)
        swr_limit  = self.settings.get("swr_limit", 3.0)

        # TUNE automatisch — immer, keine Auswahl
        if self.radio.ip:
            self.statusBar().showMessage(
                f"TUNEN — {tune_power}W auf ANT1 fuer 5s ...", 0)
            self.radio.set_rfpower_direct(tune_power)
            self.radio.tune_on()

            def _after_tune():
                self.radio.tune_off()
                self.radio.set_power(self.settings.get("power_preset", 15))
                self._normal_stations = {}
                self._diversity_stations = {}
                self.rx_panel.table.setRowCount(0)
                swr = self.radio.last_swr
                if swr > swr_limit:
                    from PySide6.QtWidgets import QMessageBox
                    QMessageBox.warning(
                        self, "SWR zu hoch",
                        f"SWR {swr:.1f} > {swr_limit:.1f} — Gain-Messung abgebrochen.\n"
                        f"Antenne/Tuner pruefen!"
                    )
                    self._on_rx_mode_changed("normal")
                    return
                self._open_dx_tune_dialog()

            QTimer.singleShot(5000, _after_tune)
        else:
            # Kein Radio → direkt Gain-Messung
            self._open_dx_tune_dialog()

    def _open_dx_tune_dialog(self):
        """DX Tune Dialog oeffnen — NICHT-MODAL, immer im Vordergrund, GUI gesperrt."""
        # Letzte Sicherheitspruefung: PTT definitiv AUS
        if self.radio.ip:
            self.radio.ptt_off()

        from ui.dx_tune_dialog import DXTuneDialog
        band = self.settings.band
        scoring = getattr(self, '_gain_scoring_mode', 'snr')
        dialog = DXTuneDialog(self.radio, band, scoring_mode=scoring, rx_mode=self._rx_mode, parent=self)
        self._dx_tune_dialog = dialog

        # Immer im Vordergrund halten (verschwindet nicht hinter der GUI)
        dialog.setWindowFlags(dialog.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)

        # GUI sperren waehrend Gain-Messung (kein Band/Modus-Wechsel, kein CQ)
        self._set_gain_measure_lock(True)

        dialog.accepted.connect(self._on_dx_tune_accepted)
        dialog.rejected.connect(self._on_dx_tune_rejected)
        dialog.show()

    def _set_gain_measure_lock(self, locked: bool):
        """GUI sperren/entsperren waehrend Diversity-Pipeline (Tune+Gain+Einmessen)."""
        # Mode-Buttons sperren
        self.control_panel.btn_ft8.setEnabled(not locked)
        self.control_panel.btn_ft4.setEnabled(not locked)
        self.control_panel.btn_ft2.setEnabled(not locked)
        # Band-Buttons sperren
        for btn in self.control_panel.band_buttons.values():
            btn.setEnabled(not locked)
        # CQ + QSO-Buttons sperren
        self.control_panel.btn_cq.setEnabled(not locked)
        self.control_panel.btn_advance.setEnabled(not locked)
        self.control_panel.btn_cancel.setEnabled(not locked)
        # Normal/Diversity sperren
        self.control_panel.btn_normal.setEnabled(not locked)
        self.control_panel.btn_diversity.setEnabled(not locked)
        # TUNE + GAIN-MESSUNG sperren
        if hasattr(self.control_panel, 'btn_tune'):
            self.control_panel.btn_tune.setEnabled(not locked)
        if hasattr(self.control_panel, 'btn_einmessen'):
            self.control_panel.btn_einmessen.setEnabled(not locked)
        if locked:
            if getattr(self, '_rx_mode', 'normal') == 'normal':
                self.statusBar().showMessage("GAIN-MESSUNG AKTIV — Bedienung gesperrt", 0)
            else:
                self.statusBar().showMessage("DIVERSITY SETUP AKTIV — Bedienung gesperrt", 0)

    def _on_dx_tune_accepted(self):
        """DX Tuning erfolgreich — Preset speichern."""
        dialog = self._dx_tune_dialog
        if dialog is None:
            return
        r = dialog.get_results()
        band = self.settings.band
        ft_mode = self.settings.mode
        gain_mode = getattr(self, '_gain_scoring_mode', 'snr')
        div_scoring = "dx" if gain_mode == "snr" else "normal"
        store = getattr(self, '_dx_store', None) if div_scoring == "dx" else getattr(self, '_standard_store', None)
        if store:
            store.save_gain(
                band, ft_mode,
                rxant=r.get("best_ant", "ANT1"),
                ant1_gain=r.get("ant1_gain", r.get("best_gain", 0)),
                ant2_gain=r.get("ant2_gain", r.get("best_gain", 0)),
                ant1_avg=r.get("ant1_avg", 0.0),
                ant2_avg=r.get("ant2_avg", 0.0),
            )
        # Rückwärtskompatibilität: auch in Settings speichern (für alten Code)
        scoring = gain_mode
        self.settings.save_dx_preset(
            band=band,
            rxant=r.get("best_ant", "ANT1"),
            gain=r.get("best_gain", 0),
            ant1_avg=r.get("ant1_avg", 0.0),
            ant2_avg=r.get("ant2_avg", 0.0),
            ant1_gain=r.get("ant1_gain", r.get("best_gain", 0)),
            ant2_gain=r.get("ant2_gain", r.get("best_gain", 0)),
            scoring=scoring,
            mode=ft_mode,
        )
        ant1_g = r.get("ant1_gain", r.get("best_gain", 0))
        ant2_g = r.get("ant2_gain", r.get("best_gain", 0))
        self.control_panel.dx_info.setText(
            f"ANT1(G{ant1_g}) + ANT2(G{ant2_g})"
        )
        # Gains sofort anwenden
        self._diversity_ant1_gain = ant1_g
        self._diversity_ant2_gain = ant2_g
        self._dx_tune_dialog = None
        self._set_gain_measure_lock(False)

        self._log_gain_result(r, band, ft_mode)

        # Normal-Modus (KALIBRIEREN-Button): in normal_presets speichern, ANT1-Gain anwenden
        if self._rx_mode == "normal":
            import time as _time
            ant1_g = r.get("ant1_gain", r.get("best_gain", 0))
            self.settings.save_normal_preset(band=band, gain=ant1_g, rxant="ANT1")
            if self.radio.ip:
                self.radio.set_rx_antenna("ANT1")
                self.radio.set_tx_antenna("ANT1")
                self.radio.set_rfgain(ant1_g)
            self.control_panel.dx_info.setText(f"G{ant1_g}dB (kalibriert)")
            self.control_panel.dx_info.setStyleSheet("")
            self._stats_warmup_cycles = 6
            print(f"[Kalibrieren] Normal Preset {band}: G{ant1_g}dB — 4 Zyklen Warmup")
            self._update_statusbar()
            self._show_calibration_done(band, ant1_g, None)
            return

        # Diversity nach Gain-Messung starten/neu initialisieren (einmalig)
        if self._rx_mode == "diversity" and self.radio.ip:
            if getattr(self, '_pending_dx_diversity', False):
                self._pending_dx_diversity = False
                scoring = getattr(self, '_pending_diversity_scoring',
                                  getattr(self._diversity_ctrl, 'scoring_mode', 'normal'))
            else:
                scoring = getattr(self._diversity_ctrl, 'scoring_mode', 'normal')
            print(f"[Diversity] Post-Gain → Diversity starten ({scoring})")
            self._enable_diversity(scoring_mode=scoring)
            self._stats_warmup_cycles = 6
            print(f"[Diversity] Kalibrierung fertig → 4 Zyklen Warmup")

        self._update_statusbar()
        self._show_calibration_done(band, ant1_g, ant2_g)

    def _show_calibration_done(self, band: str, ant1_g: int, ant2_g: int | None):
        """Auto-Close-Info-Popup 'Kalibrierung abgeschlossen' — 3s, kein OK.

        v0.83 Fix F: non-modal + Auto-Close, Mike kann waehrend der 3s
        weiterarbeiten. WindowStaysOnTopHint + raise_+activateWindow
        verhindern Hinten-Wandern (v0.79-Problem).

        v0.79 (vorher): Modal + exec() weil non-modal hinter Hauptfenster
        verschwand. Mit raise_+activateWindow + StaysOnTopHint sollte das
        nicht mehr passieren. Esc schliesst Dialog vorzeitig (Qt-Default).
        """
        from PySide6.QtCore import Qt as _Qt, QTimer as _QTimer
        from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel
        dlg = QDialog(self)
        dlg.setWindowTitle("Kalibrierung abgeschlossen")
        dlg.setWindowFlag(_Qt.WindowType.WindowStaysOnTopHint, True)
        dlg.setStyleSheet(
            "QDialog, QWidget { background-color: #16192b; }"
        )
        lay = QVBoxLayout(dlg)
        lay.setContentsMargins(24, 20, 24, 16)
        lay.setSpacing(10)

        lbl_title = QLabel(f"✓  Kalibrierung {band} gespeichert.")
        lbl_title.setStyleSheet(
            "color: #00CC66; font-family: Menlo; font-size: 13px; font-weight: bold;"
        )
        lay.addWidget(lbl_title)

        if ant2_g is not None:
            lbl_info = QLabel(f"ANT1: {ant1_g} dB  |  ANT2: {ant2_g} dB")
        else:
            lbl_info = QLabel(f"ANT1: {ant1_g} dB")
        lbl_info.setStyleSheet(
            "color: #AAAACC; font-family: Menlo; font-size: 12px; padding: 4px 0;"
        )
        lay.addWidget(lbl_info)

        # Auto-Close nach 3s. Timer Child von dlg → wird mit dlg
        # zerstoert (z.B. App-Close), kein Race auf gestorbenen
        # Python-Wrapper (R1-Final-Review-Fix).
        _close_timer = _QTimer(dlg)
        _close_timer.setSingleShot(True)
        _close_timer.timeout.connect(dlg.accept)
        _close_timer.start(3000)

        # show() statt exec() = non-modal. raise_+activateWindow gegen
        # Hinten-Wandern (R1-P1: macOS Spaces-Edge-Cases akzeptiert).
        dlg.show()
        dlg.raise_()
        dlg.activateWindow()

    def _on_dx_tune_rejected(self):
        """DX Tuning abgebrochen — zurueck auf Normal/Diversity."""
        self._dx_tune_dialog = None
        self._set_gain_measure_lock(False)

        # Sicherheit: TX/Encoder definitiv stoppen
        if self.encoder.is_transmitting:
            self.encoder.abort()
        if self.radio.ip:
            self.radio.ptt_off()

        # Wenn Diversity aktiv war, KOMPLETT neu initialisieren
        if self._rx_mode == "diversity" and self.radio.ip:
            scoring = getattr(self._diversity_ctrl, 'scoring_mode', 'normal')
            print(f"[Diversity] Gain abgebrochen → Diversity neu initialisieren ({scoring})")
            self._enable_diversity(scoring_mode=scoring)
            self._stats_warmup_cycles = 6
        else:
            self._apply_normal_mode()
            self._stats_warmup_cycles = 6
        self.control_panel.dx_info.setText("")
        self._update_statusbar()

    def _apply_dx_preset(self, preset: dict):
        """DX-Preset am Radio anwenden."""
        rxant = preset.get("rxant", "ANT1")
        gain = preset.get("gain", 10)
        self.radio.set_rx_antenna(rxant)
        self.radio.set_rfgain(gain)
        self.radio.set_tx_antenna("ANT1")
        self.control_panel.dx_info.setText(f"{rxant}, Gain {gain} dB")
        print(f"[DX] Preset geladen: {rxant}, Gain {gain}")

    def _apply_dx_preset_for_band(self, band: str):
        """DX-Preset fuer ein bestimmtes Band laden (nach Bandwechsel)."""
        ft_mode = self.settings.mode
        scoring = getattr(self._diversity_ctrl, 'scoring_mode', 'normal')
        store = getattr(self, '_dx_store', None) if scoring == "dx" else getattr(self, '_standard_store', None)
        preset = store.get(band, ft_mode) if store else None
        if preset:
            self._apply_dx_preset(preset)
        else:
            self.control_panel.dx_info.setText("kein Preset")

    @Slot(int)
    def _on_normal_tx_freq_clicked(self, freq_hz: int):
        """Klick im Histogramm (Normal-Modus) → TX-Frequenz setzen."""
        self._set_normal_tx_freq(freq_hz, source="click")

    @Slot(int)
    def _on_normal_tx_freq_spin_changed(self, freq_hz: int):
        """Spinbox-Wert geaendert (Normal-Modus) → TX-Frequenz setzen."""
        self._set_normal_tx_freq(freq_hz, source="spin")

    def _set_normal_tx_freq(self, freq_hz: int, source: str = "click"):
        """Manuelle TX-Frequenz im Normal-Modus uebernehmen.

        Wird sowohl von Klick im Histogramm als auch Spinbox-Aenderung
        getriggert. Synchronisiert beide UIs, encoder.audio_freq_hz und
        die Persistenz pro Band.
        """
        if self._rx_mode != "normal":
            return  # Im Diversity-Modus ignorieren (Auto-Suche aktiv)
        freq_hz = int(freq_hz)
        # Spinbox synchron halten (ohne Endlos-Loop dank blockSignals)
        spin = self.control_panel._tx_freq_spin
        if source != "spin":
            spin.blockSignals(True)
            spin.setValue(freq_hz)
            spin.blockSignals(False)
        # Encoder + Histogramm-Marker
        self.encoder.audio_freq_hz = freq_hz
        hist_data = self._diversity_ctrl.get_histogram_data()
        hist_data['cq_freq'] = freq_hz
        self.control_panel.update_freq_histogram(hist_data)
        # Persistenz pro Band
        self.settings.save_normal_tx_freq(self.settings.band, freq_hz)
        print(f"[Normal] TX-Freq manuell auf {freq_hz} Hz ({source})")

    def _apply_normal_mode(self):
        """Normal-Modus: eigenes Normal-Preset (NIEMALS Diversity-Preset), TX immer ANT1."""
        band = self.settings.band
        # Manuelle TX-Frequenz fuer dieses Band laden (per default 1500 Hz)
        tx_freq = self.settings.get_normal_tx_freq(band)
        self.encoder.audio_freq_hz = tx_freq
        spin = self.control_panel._tx_freq_spin
        spin.blockSignals(True)
        spin.setValue(tx_freq)
        spin.blockSignals(False)
        preset = self.settings.get_normal_preset(band)
        gain = preset.get("gain", PREAMP_PRESETS.get(band, 10))
        measured_str = preset.get("measured", "")

        age_days = None
        if measured_str:
            import datetime
            try:
                measured_dt = datetime.datetime.strptime(measured_str, "%Y-%m-%d %H:%M")
                age_days = (datetime.datetime.now() - measured_dt).days
                if age_days > 7:
                    self.control_panel.dx_info.setText(f"G{gain}dB ({age_days}d alt!)")
                    self.control_panel.dx_info.setStyleSheet("color: #FFA500;")
                else:
                    self.control_panel.dx_info.setText(f"G{gain}dB (kalibriert)")
                    self.control_panel.dx_info.setStyleSheet("")
            except Exception:
                self.control_panel.dx_info.setText(f"G{gain}dB (kalibriert)")
                self.control_panel.dx_info.setStyleSheet("")
        else:
            self.control_panel.dx_info.setText(f"G{gain}dB (Standard)")
            self.control_panel.dx_info.setStyleSheet("color: #888888;")

        if self.radio.ip:
            self.radio.set_rx_antenna("ANT1")
            self.radio.set_tx_antenna("ANT1")
            self.radio.set_rfgain(gain)
        print(f"[Normal] ANT1, Gain {gain} dB ({'kalibriert' if measured_str else 'Standard'})")

        # Info-Box bei sehr alter Kalibrierung (>30 Tage) — pro Band einmal pro Session
        if age_days is not None and age_days > 30:
            warned = getattr(self, '_normal_preset_warned_bands', None)
            if warned is not None and band not in warned:
                warned.add(band)
                self._show_normal_preset_age_info(band, age_days, measured_str)

        # v0.78: Mode-Coupling Buttons aktualisieren (rx_mode jetzt sauber gesetzt)
        if hasattr(self, "_easter_egg_active"):
            self._update_button_visibility()

    def _show_normal_preset_age_info(self, band: str, age_days: int, measured_str: str):
        """Info-Dialog: Normal-Preset >30 Tage alt — KALIBRIEREN-Button empfohlen."""
        from PySide6.QtWidgets import QMessageBox
        msg = QMessageBox(self)
        msg.setWindowTitle("Kalibrierung empfohlen")
        msg.setIcon(QMessageBox.Icon.Information)
        msg.setText(
            f"Normal-Modus {band}: letzte Kalibrierung vor {age_days} Tagen "
            f"({measured_str})."
        )
        msg.setInformativeText(
            "Eine neue Einmessung wird empfohlen.\n"
            "Klicke dazu im Kontroll-Panel auf den KALIBRIEREN-Button."
        )
        msg.setStandardButtons(QMessageBox.StandardButton.Ok)
        msg.setStyleSheet("""
            QMessageBox { background-color: #1a1a2e; }
            QLabel { color: #CCCCCC; font-family: Menlo; font-size: 13px; }
            QPushButton {
                background-color: #2a2a3e; color: #CCCCCC;
                border: 1px solid #444; border-radius: 5px;
                font-family: Menlo; font-size: 13px;
                padding: 6px 18px; min-width: 80px;
            }
            QPushButton:hover { background-color: #3a3a5e; }
        """)
        msg.exec()

    def _log_gain_result(self, r: dict, band: str, ft_mode: str) -> None:
        """Append-only Logging jeder erfolgreichen Gain-Messung in
        ~/.simpleft8/gain_log.md — fuer spaetere Drift-Analyse ueber Wochen."""
        import time as _time
        log_path = Path.home() / ".simpleft8" / "gain_log.md"
        utc = _time.strftime("%Y-%m-%d %H:%M UTC", _time.gmtime())
        gain_mode = getattr(self, '_gain_scoring_mode', 'snr')
        rx_mode   = getattr(self, '_rx_mode', 'normal')
        mode_label = (
            f"{rx_mode.capitalize()} / "
            f"{'DX-Scoring' if gain_mode == 'snr' else 'Standard'}"
        )
        lines = [
            f"\n## {utc} — {band} {ft_mode} — {mode_label}",
            f"- ANT1-Gain: {r.get('ant1_gain', '?')} dB  "
            f"ANT2-Gain: {r.get('ant2_gain', '?')} dB",
            f"- Beste Antenne: {r.get('best_ant', '?')}  "
            f"(best_gain={r.get('best_gain', '?')} dB)",
            f"- ANT1-Ø SNR: {r.get('ant1_avg', 0.0):.1f} dB  "
            f"ANT2-Ø SNR: {r.get('ant2_avg', 0.0):.1f} dB",
        ]
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write("\n".join(lines) + "\n")
        print(f"[Gain-Log] {band} {ft_mode}: "
              f"ANT1={r.get('ant1_gain')} ANT2={r.get('ant2_gain')} "
              f"→ {r.get('best_ant')} — gain_log.md")
