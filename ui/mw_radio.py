"""SimpleFT8 MainWindow — Radio-Verbindung, Band, Diversity, DX-Tuning Mixin."""

from __future__ import annotations

import threading
import time
from collections import deque
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

        # Encoder
        self.encoder.set_radio(self.radio)
        self.encoder.set_decoder(self.decoder)
        self.encoder.tx_started.connect(
            lambda msg: self.control_panel.set_tx_active(True)
        )
        self.encoder.tx_started.connect(
            lambda msg: self.qso_panel.add_tx(msg),
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
        # DX-Preset ANT1-Gain silent laden wenn vorhanden
        preset = self.settings.get_dx_preset(band)
        if preset and "ant1_gain" in preset:
            self.radio.set_rfgain(preset['ant1_gain'])
            self.statusBar().showMessage(
                f"Preset {band} geladen: ANT1 G{preset['ant1_gain']} dB", 4000
            )
            print(f"[FlexRadio] Preset {band}: ANT1 G{preset['ant1_gain']} dB")
        # Leistung: konservativer Start bei 50%, Regelung regelt auf Zielwatt ein
        power_preset = self.settings.get("power_preset", 10)
        self._rfpower_current = 50
        self.radio.set_power(self._rfpower_current)
        self.control_panel.set_power_preset(power_preset)
        # TX Audio-Drive (mic_level) setzen — steuert wieviel Leistung die PA tatsaechlich abgibt
        tx_level = min(75, self.settings.get("tx_level", 75))  # max 75%
        self.radio.set_tx_level(tx_level / 100.0)
        self.control_panel.tx_level_bar.setValue(tx_level)
        self.control_panel.tx_level_label.setText(f"TX-Pegel: {tx_level}%")
        self.decoder.set_quality(self._rx_mode)  # Qualität vom aktiven Modus abhängig
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
        self.control_panel.update_decode_count(0)
        self.control_panel.set_rx_active(active)
        # Rotes Banner im Fenster wenn RX deaktiviert
        self._rx_warning_label.setVisible(not active)

    @Slot(str)
    def _on_mode_changed(self, mode: str):
        self.settings.set("mode", mode)
        self.timer.set_mode(mode)
        # Decoder + Encoder auf neues Protokoll umschalten
        self.decoder.set_protocol(mode)
        self.encoder.set_protocol(mode)
        self.qso_sm._mode = mode
        # Even/Odd Anzeige: Slot-Dauer fuer QSO-Panel
        _DURATIONS = {"FT8": 15.0, "FT4": 7.5, "FT2": 3.8}
        self.qso_panel._cycle_duration = _DURATIONS.get(mode, 15.0)
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
            self.control_panel.freq_label.setText(f"{freq:.3f} MHz")
            print(f"[Mode] {mode} auf {band}: {freq:.3f} MHz")
        # RX-Filter pro Modus: FT2 braucht breiteren Filter (150 Hz Signalbreite)
        _FILTERS = {"FT8": (100, 3100), "FT4": (100, 3100), "FT2": (100, 4000)}
        flo, fhi = _FILTERS.get(mode, (100, 3100))
        if self.radio.ip:
            self.radio.set_rx_filter(flo, fhi)
        # DT-Korrektur: gespeicherten Wert fuer neuen Modus laden
        from core import ntp_time
        ntp_time.set_mode(mode)
        self._update_statusbar()

    @Slot(str)
    def _on_band_changed(self, band: str):
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
                self._apply_dx_preset_for_band(band)
            else:
                self._apply_normal_mode()
        # Per-Band TX Level laden (Auto-Regelung speichert pro Band)
        band_levels = self.settings.get("tx_levels_per_band", {})
        saved_level = min(75, band_levels.get(band, 75))  # max 75% (Clipschutz-Anker)
        self.radio.set_tx_level(saved_level / 100.0)
        self.control_panel.tx_level_bar.setValue(saved_level)
        self.control_panel.tx_level_label.setText(f"TX-Pegel: {saved_level}%")
        self._fwdpwr_samples.clear()   # Alte Messwerte verwerfen
        self._rfpower_current = 50    # Reset auf konservativen Start bei Bandwechsel
        self._update_statusbar()

    @Slot(str)
    def _on_rx_mode_changed(self, mode: str):
        """RX-Modus umschalten (nur 'normal' oder 'diversity')."""
        if not self.radio.ip:
            self.control_panel.set_rx_mode("normal")
            return

        old_mode = self._rx_mode

        # Alten Modus sauber beenden + Liste immer leeren bei Wechsel
        if old_mode == "diversity":
            self._disable_diversity()
        self.rx_panel.table.setRowCount(0)
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
            # Info-Dialog (einmalig)
            _show_info_once(self, "diversity", "Diversity Modus",
                "Diversity vergleicht zwei Antennen und waehlt die bessere.\n\n"
                "Standard: Zaehlt alle dekodierten Stationen.\n"
                "Die Antenne die mehr Stationen hoert gewinnt.\n"
                "Ideal fuer CQ-Betrieb mit vielen QSOs.\n\n"
                "DX: Zaehlt nur schwache Stationen (SNR < -10 dB).\n"
                "Entfernte DX-Stationen kommen schwach rein (z.B. -24 dB).\n"
                "Die Antenne die mehr DX-Stationen hoert gewinnt.\n\n"
                "Messdauer: 8 Zyklen (~2 Min).\n"
                "Ergebnis: bessere Antenne 70:30 oder gleichmaessig 50:50.",
                self.settings)
            # Scoring-Modus waehlen
            dlg = QMessageBox(self)
            dlg.setWindowTitle("Diversity — Modus waehlen")
            dlg.setText("Welchen Scoring-Modus verwenden?")
            btn_normal_m = dlg.addButton("Standard", QMessageBox.ButtonRole.AcceptRole)
            btn_dx       = dlg.addButton("DX", QMessageBox.ButtonRole.AcceptRole)
            btn_cancel   = dlg.addButton("Abbrechen", QMessageBox.ButtonRole.RejectRole)
            dlg.exec()
            if dlg.clickedButton() == btn_cancel:
                self.control_panel.set_rx_mode("normal")
                self._update_statusbar()
                return
            scoring = "dx" if dlg.clickedButton() == btn_dx else "normal"
            self._rx_mode = "diversity"
            self._diversity_stations = {}
            label = "DIVERSITY DX" if scoring == "dx" else "DIVERSITY"
            self.control_panel.btn_diversity.setText(label)

            if scoring == "dx":
                # DX-Modus: Gain-Preset pruefen, ggf. automatisch messen
                band = self.settings.band
                dx_preset = self.settings.get_gain_preset(band, mode="dx")
                if dx_preset:
                    # Gespeichertes DX-Preset anwenden → direkt Diversity starten
                    self._apply_dx_preset(dx_preset)
                    print(f"[DX] Preset geladen: {band} Gain={dx_preset.get('gain')} dB")
                    self._enable_diversity(scoring_mode="dx")
                else:
                    # Kein DX-Preset → automatische Gain-Messung starten (nach SNR)
                    _show_info_once(self, "dx_auto_gain", "DX Gain-Messung",
                        "DX-Modus: Gain-Messung startet automatisch.\n\n"
                        "Im DX-Betrieb zaehlt Empfindlichkeit (SNR) statt\n"
                        "Stationsanzahl. Die Messung findet den optimalen\n"
                        "Preamp-Wert fuer schwache DX-Signale.\n\n"
                        "Ergebnis wird gespeichert — beim naechsten Mal\n"
                        "wird das DX-Preset direkt geladen.",
                        self.settings)
                    print(f"[DX] Kein Preset fuer {band} — starte Gain-Messung (SNR)")
                    self._pending_dx_diversity = True
                    self._start_dx_tuning(scoring_mode="snr")
            else:
                # Standard: direkt Diversity starten
                self._enable_diversity(scoring_mode="normal")

        self._update_statusbar()

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
        self._diversity_stations = {}
        self._diversity_current_ant = "A1"
        self._diversity_ant_queue = deque()  # (ant, phase) Tupel
        # Settings-Wert × Modus-Multiplikator (gleiche ZEIT fuer alle Modi)
        mode = self.settings.mode
        _MULT = {"FT8": 1, "FT4": 2, "FT2": 4}
        base = self.settings.get("diversity_operate_cycles", 60)
        self._diversity_ctrl.OPERATE_CYCLES = base * _MULT.get(mode, 1)
        self._diversity_ctrl.MEASURE_CYCLES = 8 * _MULT.get(mode, 1)
        self._diversity_ctrl.scoring_mode = scoring_mode

        # Gespeichertes Preset laden? → sofort Betrieb statt Messung
        mode = self.settings.mode
        band = self.settings.band
        preset = self.settings.get_diversity_preset(mode, band)
        if preset:
            self._diversity_ctrl.load_preset(preset)
            self._diversity_ctrl.OPERATE_CYCLES = base * _MULT.get(mode, 1)
            self._diversity_ctrl.MEASURE_CYCLES = 8 * _MULT.get(mode, 1)
            print(f"[Diversity] Preset {mode}_{band}: {preset['ratio']} — Betrieb sofort")
            self.control_panel.update_diversity_ratio(
                self._diversity_ctrl.ratio, "operate",
                operate_cycles=0,
                operate_total=self._diversity_ctrl.OPERATE_CYCLES,
                scoring_mode=scoring_mode)
            self.control_panel.update_diversity_counts(0, 0)
        else:
            # Kein Preset → normal einmessen
            self._diversity_ctrl.reset()
            self._set_cq_locked(True)
            print(f"[Diversity] Kein Preset — starte Messung ({scoring_mode.upper()})")
            self.control_panel.update_diversity_ratio("50:50", "measure", 0,
                                                      self._diversity_ctrl.MEASURE_CYCLES,
                                                      scoring_mode=scoring_mode)
            self.control_panel.update_diversity_counts(0, 0)

        band = self.settings.band
        preset = self.settings.get_dx_preset(band)

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
            # Hinweis nur wenn kein Preset existiert (nicht wenn veraltet)
            if not preset:
                from PySide6.QtCore import QTimer
                QTimer.singleShot(
                    500,
                    lambda: QMessageBox.information(
                        self, "Kein DX Preset",
                        f"Kein Antennen-Preset fuer {band}.\n\n"
                        f"Tipp: Mit DX TUNING einmessen → optimale Preamp-Werte\n"
                        f"fuer ANT1 und ANT2 separat finden.\n\n"
                        f"Standard-Gains werden verwendet:\n"
                        f"  ANT1: {self._diversity_ant1_gain} dB\n"
                        f"  ANT2: {self._diversity_ant2_gain} dB",
                    )
                )
            print(f"[Diversity] AKTIV — Standard-Gains, kein Preset fuer {band}")

    def _disable_diversity(self):
        """Diversity deaktivieren: zurueck auf ANT1."""
        self._diversity_stations = {}
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
        print("[Diversity] Manuelle Neueinmessung gestartet")
        self._diversity_ctrl.start_measure()
        self._set_cq_locked(True)
        self.control_panel.update_diversity_ratio(
            "50:50", "measure", 0,
            self._diversity_ctrl.MEASURE_CYCLES,
            scoring_mode=self._diversity_ctrl.scoring_mode)

    def _handle_dx_tuning(self):
        """DX-Tuning Modus: Preset laden oder Messung starten."""
        _show_info_once(self, "gain_messung", "Gain-Messung",
            "Die Gain-Messung ermittelt optimale Preamp-Werte\n"
            "fuer jede Antenne auf dem aktuellen Band.\n\n"
            "Die Werte werden pro Band gespeichert und beim\n"
            "naechsten Start automatisch geladen.\n\n"
            "Bei DX-Verkehr oder wechselnden Bedingungen\n"
            "sollte die Messung taeglich wiederholt werden.",
            self.settings)
        band = self.settings.band
        preset = self.settings.get_dx_preset(band)

        if preset:
            self._apply_dx_preset(preset)
            msg = QMessageBox(self)
            msg.setWindowTitle("DX Preset")
            msg.setIcon(QMessageBox.Icon.Information)
            msg.setText(
                f"DX Preset fuer {band} geladen:\n\n"
                f"  RX-Antenne:  {preset['rxant']}\n"
                f"  RF-Gain:     {preset['gain']} dB\n"
                f"  Gemessen:    {preset.get('measured', '?')}\n\n"
                f"TX bleibt auf ANT1."
            )
            msg.setStyleSheet(self._msgbox_style())
            msg.addButton("OK", QMessageBox.ButtonRole.AcceptRole)
            btn_new = msg.addButton(
                "Neu messen", QMessageBox.ButtonRole.ActionRole
            )
            msg.exec()
            if msg.clickedButton() == btn_new:
                self._start_dx_tuning(scoring_mode="stations")
        else:
            msg = QMessageBox(self)
            msg.setWindowTitle("Gain-Messung")
            msg.setIcon(QMessageBox.Icon.Question)
            msg.setText(
                f"Kein DX Preset fuer {band}.\n\n"
                f"DX Tuning starten?\n"
                f"(Messung dauert ca. 3-5 Minuten)"
            )
            msg.setStyleSheet(self._msgbox_style())
            btn_start = msg.addButton(
                "Tuning starten", QMessageBox.ButtonRole.AcceptRole
            )
            msg.addButton("Abbrechen", QMessageBox.ButtonRole.RejectRole)
            msg.exec()
            if msg.clickedButton() == btn_start:
                self._start_dx_tuning()
            else:
                pass  # GAIN-MESSUNG abgebrochen — Modus unveraendert lassen

    def _start_dx_tuning(self, scoring_mode: str = "snr"):
        """DX Tune Dialog — optional TUNE-Schritt + SWR-Pruefung vor Gain-Messung."""
        self._gain_scoring_mode = scoring_mode
        from PySide6.QtWidgets import QMessageBox
        from PySide6.QtCore import QTimer

        tune_power = self.settings.get("tune_power", 10)
        swr_limit  = self.settings.get("swr_limit", 3.0)

        # TUNE anbieten (Antennentuner einstellen bevor Messung startet)
        msg = QMessageBox(self)
        msg.setWindowTitle("Vor der Gain-Messung: TUNE")
        msg.setIcon(QMessageBox.Icon.Question)
        msg.setText(
            f"Vor der Gain-Messung den Tuner einstellen?\n\n"
            f"TUNE sendet {tune_power}W auf ANT1 fuer 5 Sekunden.\n"
            f"Bei SWR > {swr_limit:.1f} wird Gain-Messung abgebrochen."
        )
        msg.setStyleSheet(self._msgbox_style())
        btn_tune  = msg.addButton("Tunen + Messen", QMessageBox.ButtonRole.AcceptRole)
        btn_skip  = msg.addButton("Direkt messen",  QMessageBox.ButtonRole.ActionRole)
        btn_abort = msg.addButton("Abbrechen",      QMessageBox.ButtonRole.RejectRole)
        msg.exec()

        if msg.clickedButton() == btn_abort:
            self._on_rx_mode_changed("normal")
            return

        if msg.clickedButton() == btn_tune and self.radio.ip:
            # TX-Leistung auf Tune-Wert setzen, TUNE starten
            self.radio.set_rfpower_direct(tune_power)
            self.radio.tune_on()

            def _after_tune():
                self.radio.tune_off()
                self.radio.set_power(self.settings.get("power_preset", 15))
                # Buffer leeren: AT hat RX-Impedanz geändert → alte Daten ungültig
                self._normal_stations = {}
                self._diversity_stations = {}
                self.rx_panel.table.setRowCount(0)
                # SWR pruefen
                swr = self.radio.last_swr
                if swr > swr_limit:
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
            # Direkt Gain-Messung ohne TUNE
            self._open_dx_tune_dialog()

    def _open_dx_tune_dialog(self):
        """DX Tune Dialog oeffnen — NICHT-MODAL, immer im Vordergrund, GUI gesperrt."""
        from ui.dx_tune_dialog import DXTuneDialog
        band = self.settings.band
        scoring = getattr(self, '_gain_scoring_mode', 'snr')
        dialog = DXTuneDialog(self.radio, band, scoring_mode=scoring, parent=self)
        self._dx_tune_dialog = dialog

        # Immer im Vordergrund halten (verschwindet nicht hinter der GUI)
        dialog.setWindowFlags(dialog.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)

        # GUI sperren waehrend Gain-Messung (kein Band/Modus-Wechsel, kein CQ)
        self._set_gain_measure_lock(True)

        dialog.accepted.connect(self._on_dx_tune_accepted)
        dialog.rejected.connect(self._on_dx_tune_rejected)
        dialog.show()

    def _set_gain_measure_lock(self, locked: bool):
        """GUI sperren/entsperren waehrend Gain-Messung."""
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
        if locked:
            self.statusBar().showMessage("GAIN-MESSUNG AKTIV — Bedienung gesperrt", 0)

    def _on_dx_tune_accepted(self):
        """DX Tuning erfolgreich — Preset speichern."""
        dialog = self._dx_tune_dialog
        if dialog is None:
            return
        r = dialog.get_results()
        band = self.settings.band
        scoring = getattr(self, '_gain_scoring_mode', 'snr')
        self.settings.save_dx_preset(
            band=band,
            rxant=r.get("best_ant", "ANT1"),
            gain=r.get("best_gain", 0),
            ant1_avg=r.get("ant1_avg", 0.0),
            ant2_avg=r.get("ant2_avg", 0.0),
            ant1_gain=r.get("ant1_gain", r.get("best_gain", 0)),
            ant2_gain=r.get("ant2_gain", r.get("best_gain", 0)),
            scoring=scoring,
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

        # DX-Diversity: nach Gain-Messung automatisch Diversity starten
        if getattr(self, '_pending_dx_diversity', False):
            self._pending_dx_diversity = False
            print(f"[DX] Gain-Messung fertig → starte Diversity DX")
            self._enable_diversity(scoring_mode="dx")
        self._update_statusbar()

    def _on_dx_tune_rejected(self):
        """DX Tuning abgebrochen — zurueck auf Normal."""
        self._dx_tune_dialog = None
        self._set_gain_measure_lock(False)
        self._apply_normal_mode()
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
        preset = self.settings.get_dx_preset(band)
        if preset:
            self._apply_dx_preset(preset)
        else:
            self.control_panel.dx_info.setText("kein Preset")

    def _apply_normal_mode(self):
        """Normal-Modus: beste RX-Antenne aus DX-Preset (falls vorhanden), TX immer ANT1."""
        band = self.settings.band

        preset = self.settings.get_dx_preset(band)
        if preset:
            rxant = preset.get("rxant", "ANT1")
            gain  = preset.get("gain", PREAMP_PRESETS.get(band, 10))
            # Alter des Presets berechnen
            import datetime
            measured_str = preset.get("measured", "")
            age_days = None
            try:
                measured_dt = datetime.datetime.strptime(measured_str, "%Y-%m-%d %H:%M")
                age_days = (datetime.datetime.now() - measured_dt).days
            except Exception:
                pass
            if age_days is not None and age_days > 7:
                self.control_panel.dx_info.setText(f"RX:{rxant} G{gain}dB ({age_days}d alt!)")
                self.control_panel.dx_info.setStyleSheet("color: #FFA500;")
            else:
                self.control_panel.dx_info.setText(f"RX:{rxant} G{gain}dB")
                self.control_panel.dx_info.setStyleSheet("")
            print(f"[DX] Normal-Modus: RX={rxant} TX=ANT1, Gain {gain} (Preset, {age_days}d alt)")
        else:
            rxant = "ANT1"
            gain  = PREAMP_PRESETS.get(band, 10)
            self.control_panel.dx_info.setText("Kein Preset")
            self.control_panel.dx_info.setStyleSheet("color: #888888;")
            print(f"[DX] Normal-Modus: ANT1, Gain {gain} (kein Preset)")

        self.radio.set_rx_antenna(rxant)
        self.radio.set_tx_antenna("ANT1")
        self.radio.set_rfgain(gain)
