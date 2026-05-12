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
        """FlexRadio verbinden und Decoder starten (mit Auto-Retry).

        P26 (10.05.2026): Modal-Dialog waehrend Connect-Versuch.
        Aufgerufen via QTimer.singleShot(0, ...) aus MainWindow.__init__,
        damit Hauptfenster zuerst sichtbar ist (Modal poppt darueber).
        """
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
            lambda msg, te, sst: self.control_panel.set_tx_active(True)
        )
        self.encoder.tx_started.connect(
            self._on_tx_started,
            Qt.ConnectionType.QueuedConnection,
        )
        self.encoder.tx_finished.connect(self._on_tx_finished)

        # P26: Modal-Dialog VOR Worker-Thread aufbauen + signal-connect.
        # connect VOR thread.start() damit auch sehr-schnelle Connects
        # sauber landen (Qt: accept() vor exec() → exec returned sofort).
        from ui.connect_status_dialog import ConnectStatusDialog
        self._connect_dialog = ConnectStatusDialog(self)
        self.radio.connected.connect(
            self._connect_dialog.accept,
            Qt.ConnectionType.QueuedConnection,
        )

        # Auto-Connect im Hintergrund
        self.control_panel.set_connection_status("searching")
        threading.Thread(
            target=self._connect_worker, daemon=True
        ).start()

        # Modal blockiert GUI-Thread (WindowModal: Decoder/Signale laufen).
        # Returns wenn:
        #   - radio.connected feuert → dialog.accept() → exec() returned Accepted
        #   - User klickt "ohne Radio weiter" → reject() → Rejected
        #   - User klickt "Beenden" → QApplication.quit() → exec() returned
        self._connect_dialog.exec()

        # Cleanup nach exec()-Return
        try:
            self.radio.connected.disconnect(self._connect_dialog.accept)
        except (TypeError, RuntimeError):
            pass  # bereits disconnected oder Dialog tot
        self._connect_dialog = None

    def _connect_worker(self):
        """Verbindung im Hintergrund herstellen mit Modal-Updates."""
        # K1-Fix R1: lokale Referenz (atomarer Read), Worker hat eigenen
        # Snapshot. Auch wenn _connect_dialog spaeter auf None gesetzt wird,
        # bleibt unsere Referenz gueltig — Crash-Schutz via try/except.
        dlg = self._connect_dialog

        def on_attempt(attempt: int, max_attempts: int) -> None:
            if dlg is not None:
                try:
                    dlg.attempt_changed.emit(attempt, max_attempts)
                except RuntimeError:
                    pass  # Dialog destroyed (User klickte "weiter"/"Beenden")

        ok = self.radio.auto_connect(
            max_retries=10, retry_delay=3.0, on_attempt=on_attempt
        )
        if not ok:
            self.control_panel.set_connection_status("disconnected")
            if dlg is not None:
                try:
                    dlg.failed_signal.emit()
                except RuntimeError:
                    pass

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

        # P35 Bug A Resume (AK7 idempotent, R1-Q7 voller Pfad):
        # Falls _enable_diversity vor Radio-Connect aufgeschoben wurde,
        # jetzt nachholen — aber via _check_diversity_preset (nicht
        # _enable_diversity direkt) damit Gain-Cache + DXTuneDialog-
        # Pfade korrekt durchlaufen werden.
        pending_scoring = getattr(self, "_pending_diversity_init", None)
        if pending_scoring is not None:
            self._pending_diversity_init = None  # AK7: vor Aufruf reset
            print(f"[Diversity] Radio verbunden — aufgeschobene Init "
                  f"(scoring={pending_scoring})")
            from core.debug_log import debug_log as _dlog
            _dlog("DIV-EN", f"Resume scoring={pending_scoring}")
            self._check_diversity_preset(band, mode, pending_scoring)

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
        # Pipeline-Lock-Schutz (v0.92 R1-Audit): blockiert auch programmatische
        # Pfade. Mode-Wechsel triggert `_check_diversity_preset` das
        # asynchron Tune+Gain-Messung starten kann waehrend laufende Pipeline.
        if getattr(self, '_gain_measure_locked', False):
            current = self.settings.mode
            print(f"[Mode-Wechsel ignoriert: Pipeline laeuft, bleibe auf {current}]")
            self.control_panel._set_mode(current)
            return
        # v0.75/v0.78: aktive Power-Modi bei FT-Mode-Wechsel (FT8/FT4/FT2) stoppen
        if hasattr(self, "_auto_hunt") and self._auto_hunt.active:
            self._auto_hunt.stop_auto_hunt("ft_mode_change")
        if hasattr(self, "_omni_cq") and self._omni_cq.is_active():
            self._omni_cq.stop("mode_change")
        # P34: Dynamic-Buffer leeren bei Modus-Wechsel (AK10)
        if getattr(self, "_dynamic_ctrl", None) and self._dynamic_ctrl.is_active():
            self._dynamic_ctrl.reset()
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
        # P1.22: `Modus: FT8` Label entfernt — redundant zur Statusbar unten.
        # status_label-Widget bleibt fuer QSO-Counter / CQ-Anzeige verfuegbar.
        self.qso_panel.status_label.setText("")
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
        # P21 Debug-Log: Bandwechsel-Anfang
        from core.debug_log import debug_log as _dlog
        _dlog("BAND", f"_on_band_changed -> {band} (alt: {self.settings.band}, "
              f"rx_mode={getattr(self, '_rx_mode', '?')})")
        # Pipeline-Lock-Schutz (v0.92 R1-Audit): blockiert auch programmatische
        # Pfade die UI-Button-Disable umgehen wuerden. Ohne diese Pruefung
        # konnte `reset()` in `_diversity_ctrl.on_band_change()` den Phase-
        # Check in `record_measurement` aushebeln → Daten-Leck zwischen Baendern.
        if getattr(self, '_gain_measure_locked', False):
            current = self.settings.band
            _dlog("BAND", f"IGNORED — pipeline locked, bleibe auf {current}")
            print(f"[Bandwechsel ignoriert: Pipeline laeuft, bleibe auf {current}]")
            self.control_panel._set_band(current)  # UI-Sync zurueck
            return
        # Race-Schutz: ausstehende TUNE-Callbacks ungueltig machen, sonst ruft
        # ein 5-Sek-Timer aus dem alten Band-Kontext _enable_diversity() fuer
        # das jetzt verlassene Band auf.
        self._tune_token = None
        self.settings.set("band", band)
        freq = self.settings.frequency_mhz
        self._has_sent_cq = False

        # P34: Dynamic-Buffer leeren bei Bandwechsel (AK10)
        if getattr(self, "_dynamic_ctrl", None) and self._dynamic_ctrl.is_active():
            self._dynamic_ctrl.reset()

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
        # P21-Fix (Mike 10.05.): on_band_change() startet Mess. Wenn Radio
        # noch nicht verbunden, wird der Antennen-Switch im Decoder-Cycle
        # geskipped (radio.ip=False) und _handle_diversity_measure macht
        # ebenfalls nichts (siehe mw_cycle.py P21-Fix). Sobald Radio
        # verbindet, laeuft die Mess automatisch beim naechsten Slot an.
        radio_ready = bool(self.radio.ip)
        # P35 Bug D (Mike Field-Test 11.05.): on_band_change() nur rufen wenn
        # Diversity-Modus aktiv UND Radio verbunden. Sonst „messen 0/6"-
        # Anzeige haengt weil niemand misst (rx_mode=normal oder radio fehlt).
        # Bei App-Start triggert Settings-Restore _on_band_changed mit
        # rx_mode=normal+radio.ip=None → ohne Schutz endlose Mess-Anzeige.
        if self._rx_mode == "diversity" and radio_ready:
            _dlog("BAND", f"_diversity_ctrl.on_band_change() radio_ready={radio_ready} "
                  f"-> startet Mess (6 Zyklen)")
            self._diversity_ctrl.on_band_change()
        else:
            # Phase=operate als Default damit UI nicht „messen" zeigt.
            _dlog("BAND", f"_diversity_ctrl.on_band_change() SKIP "
                  f"(rx_mode={self._rx_mode}, radio_ready={radio_ready})")
            self._diversity_ctrl._phase = "operate"
        self.control_panel.update_freq_histogram(
            self._diversity_ctrl.get_histogram_data())
        # Auto-Hunt: Cooldowns loeschen bei Bandwechsel
        if self._auto_hunt.active:
            self._auto_hunt.set_band(band)
            self._auto_hunt.on_band_change()
        # OMNI bei Bandwechsel stoppen
        if hasattr(self, "_omni_cq") and self._omni_cq.is_active():
            self._omni_cq.stop("band_change")
        if self._rx_mode == "diversity":
            # P34: bei Dynamic AN nicht „MESSEN 0/6" sondern blaue DYNAMISCH-
            # Anzeige (Phase wird gleich von _enable_diversity auf operate gesetzt).
            _is_dyn = (getattr(self, "_dynamic_ctrl", None) is not None
                       and self._dynamic_ctrl.is_active())
            _phase = "operate" if _is_dyn else "measure"
            self.control_panel.update_diversity_ratio(
                "50:50", _phase, 0,
                self._diversity_ctrl.MEASURE_CYCLES,
                is_dynamic=_is_dyn,
            )
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
        # P3 v0.95.20: Decoder-Band fuer audio_dump-Filename aktualisieren
        self.decoder.set_band(band)
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
        # P35 Bug E (Mike-Diagnose 11.05.): Bei App-Start ist radio.ip=None.
        # Bandpilot-Auto-Switch ohne Radio fuehrt zu inkonsistentem State
        # (rx_mode=diversity gesetzt, aber _check_diversity_preset returnt
        # sofort → Init nicht durchgefuehrt → "MESSEN 0/6" haengt). Bei
        # radio.ip=None Bandpilot ueberspringen — Mike entscheidet manuell
        # nach Radio-Connect.
        if not self.radio.ip:
            _dlog("BAND", "Bandpilot SKIP — radio nicht verbunden, bleibe Normal")
            bandpilot_acted = False
        else:
            bandpilot_acted = self._maybe_apply_bandpilot(band)

        # Diversity: Preset-Check mit Dialog + ggf. Pipeline
        if not bandpilot_acted and self._rx_mode == "diversity":
            ft_mode = self.settings.get("mode", "FT8")
            scoring = getattr(self._diversity_ctrl, 'scoring_mode', 'normal')
            _dlog("BAND", f"_check_diversity_preset({band}, {ft_mode}, scoring={scoring})")
            self._check_diversity_preset(band, ft_mode, scoring)
            return  # _check_diversity_preset ruft _update_statusbar auf
        self._update_statusbar()

    @Slot(str)
    def _on_rx_mode_changed(self, mode: str):
        """RX-Modus umschalten (nur 'normal' oder 'diversity')."""
        # Pipeline-Lock-Schutz (v0.92 R1-Audit): RX-Mode-Wechsel ruft
        # `_disable_diversity` / `_activate_diversity_with_scoring` und kann
        # damit eine laufende Diversity-Messung mid-pipeline beenden.
        if getattr(self, '_gain_measure_locked', False):
            current = getattr(self, '_rx_mode', 'normal')
            print(f"[RX-Mode-Wechsel ignoriert: Pipeline laeuft, bleibe auf {current}]")
            if hasattr(self.control_panel, 'set_rx_mode'):
                self.control_panel.set_rx_mode(current)
            return
        if not self.radio.ip:
            self.control_panel.set_rx_mode("normal")
            return

        old_mode = self._rx_mode
        # v0.78: bei RX-Mode-Wechsel Easter-Egg-Override und aktive Power-Modi stoppen
        if mode != old_mode:
            if hasattr(self, "_omni_cq") and self._omni_cq.is_active():
                self._omni_cq.stop("rx_mode_change")
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

        P1.CACHE-SIMPLE (v0.95.13): Wahl-Dialog "Weiter/Neu messen" raus.
        Cache-Status-Dispatch via ``_check_diversity_preset`` analog zum
        Bandwechsel-Pfad. Mike-Vision: keine Modal-Wahl-Dialoge fuer
        Routine-Aktionen.

        P35 Bug B5 (Mike Q3, 11.05.): Wenn Settings-Toggle "Dynamic AN"
        aktiv ist, wird Dynamic am Ende automatisch (re-)aktiviert.
        Mike-Wunsch: Toggle ueberlebt Mode-Wechsel durch die ganze Session.
        activate() respektiert dabei Cache-Ratio (AK5 — kein 50:50-Reset
        wenn Cache 70:30 etc. geladen wurde).
        """
        self._rx_mode = "diversity"
        self._diversity_stations = {}
        label = "DIVERSITY DX" if scoring == "dx" else "DIVERSITY"
        self.control_panel.btn_diversity.setText(label)

        band = self.settings.band
        ft_mode = self.settings.mode

        # P1.CACHE-SIMPLE: einheitliche Dispatch-Logik
        # (Cache-Reuse / Auto-Messung / DXTuneDialog / volle Pipeline).
        self._check_diversity_preset(band, ft_mode, scoring)

        # P35 Bug B5: Settings-Toggle Auto-Reactivate.
        # Wenn Mike den Dynamic-Toggle in der Session AN hatte (auch
        # vor diesem Mode-Wechsel), Dynamic auto-reactivieren.
        # activate() respektiert Cache-Ratio (AK5).
        if (getattr(self.settings, 'dynamic_diversity_enabled', False)
                and getattr(self, "_dynamic_ctrl", None) is not None
                and not self._dynamic_ctrl.is_active()):
            print("[Dynamic] Auto-Reactivate nach Mode-Wechsel "
                  "(Settings-Toggle AN)")
            self._apply_dynamic_toggle(True)

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

        # P35 Bug E (Mike-Diagnose 11.05.): Bandpilot ueberschreibt
        # Mike's manuelle Normal-Entscheidung NIE. Bandpilot's Aufgabe ist
        # NUR zwischen Diversity-Standard und Diversity-DX zu waehlen —
        # ob Mike ueberhaupt Diversity will, entscheidet Mike selbst.
        if current == "normal":
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

        # P35 Bug E: Bandpilot empfiehlt NIE Normal. Defensive — sollte
        # durch Recommender-Logik schon abgedeckt sein, aber falls dort
        # Normal als Top-1 erscheint (z.B. wenige Diversity-Daten):
        # Mike-Regel "Normal ist Mike's Entscheidung" enforced.
        if target == "normal":
            return False

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
        """tx_finished-Hook: gespeicherten Bandpilot-Wechsel ausfuehren.

        Band-Konsistenz-Pruefung (R1-Final-Finding 04.05.2026):
        Wenn User waehrend TX das Band gewechselt hat, ist die pending-
        Empfehlung ungueltig (sie galt fuer das alte Band). In dem Fall
        wird die Empfehlung verworfen, kein Wechsel.
        """
        pending = getattr(self, "_bandpilot_pending", None)
        if pending is None:
            return
        pending_band, _utc_hour, _rec, target = pending
        self._bandpilot_pending = None
        # Aktuelles Band vs pending-Band: wenn unterschiedlich → verwerfen
        current_band = getattr(self.settings, "band", None)
        if current_band != pending_band:
            print(f"[Bandpilot] Pending fuer {pending_band} verworfen "
                  f"(aktuell: {current_band})")
            return
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

    def _enable_diversity(self, scoring_mode: str = "normal", *,
                          cached_ratio: str | None = None,
                          cached_dominant: str | None = None,
                          cached_age_seconds: float = 0.0):
        """Diversity aktivieren: Antenne pro Zyklus wechseln, Stationen akkumulieren.

        v0.93 Cache-Reuse: wenn ``cached_ratio`` gesetzt → Phase=operate
        statt =measure, ratio/dominant aus Cache, Pipeline-Lock NICHT setzen
        (Phase 3 wird komplett uebersprungen).
        """
        self._diversity_in_operate = False  # Transition-Guard zurücksetzen
        # RX-Liste + QSO-Panel leeren bei Antennen-Modus-Wechsel
        self.rx_panel.table.setRowCount(0)
        self._diversity_stations = {}
        self._normal_stations = {}
        self.qso_panel.log_view.clear()
        self.control_panel.update_decode_count(0)
        # P35 Final-R1: Queue + current_ant unter Lock (Decoder-Thread popped
        # parallel in mw_cycle._on_cycle_decoded mit _diversity_lock).
        with self._diversity_lock:
            self._diversity_current_ant = "A1"
            self._diversity_ant_queue = deque()  # (ant, phase) Tupel
        # MEASURE_CYCLES × Modus-Multiplikator (gleiche Mess-Zeit fuer alle Modi).
        # OPERATE_CYCLES ist seit v0.93 zeit-basiert (1h-Frist) — kein
        # Settings/Modus-Skalierung mehr noetig.
        mode = self.settings.mode
        _MULT = {"FT8": 1, "FT4": 2, "FT2": 4}
        self._diversity_ctrl.MEASURE_CYCLES = 6 * _MULT.get(mode, 1)
        self._diversity_ctrl.scoring_mode = scoring_mode

        # Gespeichertes Preset laden (ein Eintrag enthält Gain + Ratio)
        mode = self.settings.mode
        band = self.settings.band
        store = getattr(self, '_dx_store', None) if scoring_mode == "dx" else getattr(self, '_standard_store', None)
        preset = store.get(band, mode) if store else None

        # v0.93: Cache-Reuse vs Standard-Pfad
        # - cached_ratio gesetzt → Phase=operate, kein Lock, kein Phase 3.
        # - sonst → Standard-Pfad (Lock VOR reset, Phase=measure).
        from core.debug_log import debug_log as _dlog
        _dlog("DIV-EN", f"_enable_diversity scoring={scoring_mode} "
              f"cached_ratio={cached_ratio} (Pfad: "
              f"{'CACHE-REUSE' if cached_ratio else 'PHASE-MEASURE'})")
        # P35 Bug A (Mike Field-Test 11.05.): Wenn Radio noch nicht verbunden,
        # Init aufschieben — sonst haengt Statik-Mess (record_measurement
        # wird in mw_cycle bei radio.ip=None geskippt, step bleibt 0,
        # Queue fuellt sich mit (A1, "measure")-Eintraegen).
        if not getattr(self.radio, 'ip', None):
            self._pending_diversity_init = scoring_mode
            # Phase=operate damit Mess-Phase nicht haengt; Ratio 50:50 als
            # Fallback bis Radio kommt + Resume die echte Pipeline triggert.
            self._diversity_ctrl._phase = "operate"
            self._diversity_ctrl.ratio = "50:50"
            self._diversity_ctrl.dominant = None
            import time as _time
            self._diversity_ctrl._last_measured_at = _time.time()
            self._set_cq_locked(False)
            self._set_gain_measure_lock(False)
            print(f"[Diversity] Radio nicht verbunden — Init aufgeschoben "
                  f"(scoring={scoring_mode})")
            _dlog("DIV-EN", f"Aufgeschoben scoring={scoring_mode}")
            return

        # P34 Bug-Fix (Mike Field-Test 11.05.): Wenn Dynamic-Toggle AN ist und
        # User in Diversity wechselt, soll KEINE 90-Sek-Statik-Mess starten —
        # Dynamic uebernimmt nach ~3 Min selbst. Pruefen vor Cache-Pfad damit
        # auch ohne Cache keine Mess-Phase laeuft.
        dynamic_active = (getattr(self, "_dynamic_ctrl", None) is not None
                          and self._dynamic_ctrl.is_active())

        if dynamic_active:
            # Dynamic-Pfad: Phase=operate sofort, 50:50 als Start, kein Lock,
            # kein Modal. Dynamic sammelt Slot-fuer-Slot, in ~3 Min uebernimmt
            # es das Verhaeltnis. Buffer wird zur Sicherheit geleert.
            import time as _time
            self._diversity_ctrl.reset()
            self._diversity_ctrl.ratio = "50:50"
            self._diversity_ctrl.dominant = None
            self._diversity_ctrl._phase = "operate"
            self._diversity_ctrl._last_measured_at = _time.time()
            self._dynamic_ctrl.reset()  # Buffer leer fuer fresh Start
            self._set_cq_locked(False)
            self._set_gain_measure_lock(False)
            print(f"[Diversity] Phase=operate (Dynamic-Toggle AN) — "
                  f"50:50 startet, Dynamic uebernimmt in ~3 Min ({scoring_mode.upper()})")
            self.control_panel.update_diversity_ratio(
                "50:50", "operate",
                operate_seconds_remaining=0,
                scoring_mode=scoring_mode,
                is_dynamic=True,
                # P40: RX-Antennen-Suffix sofort beim Aktivieren zeigen
                current_ant=getattr(self, "_diversity_current_ant", None),
            )
        elif cached_ratio is not None:
            # Cache-Reuse: kein Lock, Phase direkt operate
            self._diversity_ctrl.reset()
            self._diversity_ctrl.ratio    = cached_ratio
            self._diversity_ctrl.dominant = cached_dominant or ("A1" if cached_ratio == "70:30" else None)
            self._diversity_ctrl._phase   = "operate"
            import time as _time
            self._diversity_ctrl._last_measured_at = _time.time() - cached_age_seconds
            self._set_cq_locked(False)
            self._set_gain_measure_lock(False)
            print(f"[Diversity] Phase=operate (Cache-Reuse) — {cached_ratio} "
                  f"({scoring_mode.upper()})")
            self.control_panel.update_diversity_ratio(
                cached_ratio, "operate", 0,
                self._diversity_ctrl.MEASURE_CYCLES,
                scoring_mode=scoring_mode)
        else:
            # Ratio NIE aus Cache laden — Pattern ist band-spezifisch (ANT1 hat
            # je nach Band ganz andere Resonanz-Eigenschaften). Standard-Pfad:
            # Phase=measure, 6 Slots, dann _evaluate.
            # Reihenfolge: Lock VOR reset (v0.92 R1-Audit Befund 3) — sonst
            # Race-Window in dem laufende Slots ins frische
            # `_measurements`-Bucket schreiben koennten.
            self._set_cq_locked(True)
            self._set_gain_measure_lock(True)
            self._diversity_ctrl.reset()
            print(f"[Diversity] Phase=measure — Ratio wird neu eingemessen ({scoring_mode.upper()})")
            self.control_panel.update_diversity_ratio(
                "50:50", "measure", 0,
                self._diversity_ctrl.MEASURE_CYCLES,
                scoring_mode=scoring_mode)
            # P22 / P8: Modal oeffnen (sperrt UI waehrend Mess-Phase).
            self._open_mess_status_dialog()
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

    def _try_diversity_cache_reuse(self, band: str, ft_mode: str,
                                   scoring: str) -> bool:
        """Pruefen ob Ratio-Cache < 1h alt ist und ggf. anwenden.

        P1.CACHE-SIMPLE (v0.95.13): Gain-Check entfernt — Ratio und Gain
        komplett entkoppelt. Bei frischer Ratio wird geladen, auch wenn
        Gain abgelaufen ist. Gain-Refresh wird vom Caller (z.B.
        ``_check_diversity_preset``) separat behandelt.

        Bei Erfolg: ``_enable_diversity`` aufrufen, Phase=operate setzen,
        ratio + dominant aus Cache, ``_last_measured_at`` passend setzen.
        Returnt True → Aufrufer ueberspringt Pipeline/Dialog.
        """
        store = self._get_diversity_store(scoring)
        if not store:
            return False
        if not store.is_valid_ratio(band, ft_mode):
            return False
        entry = store.get(band, ft_mode)
        ratio = entry.get("ratio")
        dominant = entry.get("dominant")
        if not ratio:
            return False
        age_min = store.get_ratio_age_minutes(band, ft_mode) or 0
        age_sec = age_min * 60

        print(f"[Diversity] Cache-Reuse {band}/{ft_mode}: {ratio} "
              f"(dominant: {dominant or 'A1'}, vor {age_min} Min.) — Phase 3 skip")

        self._enable_diversity(
            scoring_mode=scoring,
            cached_ratio=ratio,
            cached_dominant=dominant,
            cached_age_seconds=age_sec,
        )
        # P1.CACHE-TOAST-WEG (v0.95.13): Toast bei Cache-Reuse entfernt —
        # Mike-Feedback 07.05.: "wenn Wert noch gültig ist, warum schreiben
        # dass er gültig ist? Wie 'Computer fährt runter — OK?'". Aktuelle
        # Werte stehen sowieso im Diversity-Display der Antennen-Kachel.
        return True

    # ── P22 / P8: Mess-Modal-Lifecycle ───────────────────────────────────

    def _open_mess_status_dialog(self):
        """P22 / P8: Modal oeffnet sich zu Beginn von Phase 3 (Antennen-
        vergleich). WindowModal sperrt Hauptfenster, laesst Event-Loop
        laufen (Decoder-Signale kommen weiter durch).

        Wird aus `_enable_diversity` (Phase=measure-Pfad) gerufen.
        Schliesst sich automatisch via `mw_cycle._handle_diversity_measure`
        beim Phase-Wechsel measure→operate.
        """
        if getattr(self, '_mess_status_dialog', None):
            return  # schon offen
        try:
            from ui.mess_status_dialog import MessStatusDialog
            from core.timing import UTCSyncTimer
            cycle_s = UTCSyncTimer.CYCLE_DURATIONS.get(self.settings.mode, 15.0)
            dlg = MessStatusDialog(self._diversity_ctrl, parent=self)
            dlg.set_cycle_dur(cycle_s)
            dlg.rejected.connect(self._on_mess_status_cancelled)
            self._mess_status_dialog = dlg
            dlg.show()  # NICHT exec — exec wuerde Event-Loop blocken
            print("[Diversity] Mess-Modal geoeffnet (UI gesperrt)")
        except Exception as exc:
            print(f"[Diversity] Mess-Modal Fehler: {exc}")
            self._mess_status_dialog = None

    def _on_mess_status_cancelled(self):
        """Cancel-Button im Mess-Modal: discard staged + Diversity aus.

        Wird ueber das `rejected`-Signal des Dialogs getriggert. Wenn das
        Modal automatisch geschlossen wurde (accept aus mw_cycle), kommt
        `rejected` nicht — diese Methode laeuft also nur bei echtem Cancel.
        """
        dlg = getattr(self, '_mess_status_dialog', None)
        self._mess_status_dialog = None
        if not dlg or not dlg.cancelled:
            return  # auto-close → kein Cleanup-Pfad
        print("[Diversity] Mess vom User abgebrochen — Cleanup")
        band, ft_mode = self.settings.band, self.settings.mode
        for store in (getattr(self, '_standard_store', None),
                      getattr(self, '_dx_store', None)):
            if store:
                store.discard_staged(band, ft_mode)
        # Diversity-Pipeline-Flags ruecksetzen damit kein Geister-State bleibt
        self._pending_dx_diversity = False
        self._pending_ratio_status = None
        self._pending_diversity_init = None  # P35 Bug A
        self._disable_diversity()

    def _close_mess_status_dialog(self):
        """Auto-Close fuer Phase-Wechsel measure→operate.

        Wird aus mw_cycle._handle_diversity_measure gerufen sobald
        commit_with_ratio (oder Adaptiv-Stop) durch ist.

        Final-R1 KOENNTE-1: Tick-Timer vor accept() stoppen damit kein
        Spaet-Tick auf zerstoertes Widget zugreift.
        """
        dlg = getattr(self, '_mess_status_dialog', None)
        if not dlg:
            return
        self._mess_status_dialog = None
        try:
            if hasattr(dlg, '_tick_timer'):
                dlg._tick_timer.stop()
        except Exception:
            pass
        try:
            dlg.accept()  # schliesst ohne `cancelled` Flag → kein Cleanup
        except Exception:
            pass

    def _disable_diversity(self):
        """Diversity deaktivieren: zurueck auf ANT1."""
        # P34: Dynamic deaktivieren wenn Diversity aus → kein Vergleich moeglich
        if getattr(self, "_dynamic_ctrl", None) and self._dynamic_ctrl.is_active():
            self._dynamic_ctrl.deactivate()
        # P22 Final-R1 SOLLTE-2: staged-Daten beim Disable verwerfen, damit
        # Memory bei Re-Activate nicht mit alten Half-State-Werten startet.
        band, ft_mode = self.settings.band, self.settings.mode
        for store in (getattr(self, '_standard_store', None),
                      getattr(self, '_dx_store', None)):
            if store and hasattr(store, 'discard_staged'):
                store.discard_staged(band, ft_mode)
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

    def _get_diversity_store(self, scoring: str):
        """P1.CACHE-SIMPLE Helper: PresetStore je nach scoring-Modus."""
        return (getattr(self, '_dx_store', None) if scoring == "dx"
                else getattr(self, '_standard_store', None))

    def _assess_ratio(self, band: str, ft_mode: str, scoring: str) -> str:
        """P1.CACHE-SIMPLE: Ratio-Cache-Status fuer band+mode bewerten.

        Returns: "fresh" (< 60 Min), "stale" (>= 60 Min, vorhanden),
        "missing" (kein Eintrag oder kein ratio-Feld).
        """
        store = self._get_diversity_store(scoring)
        if not store:
            return "missing"
        if store.is_valid_ratio(band, ft_mode):
            return "fresh"
        entry = store.get(band, ft_mode)
        if entry and entry.get("ratio"):
            return "stale"
        return "missing"

    def _assess_gain(self, band: str, ft_mode: str, scoring: str) -> str:
        """P1.CACHE-SIMPLE: Gain-Cache-Status fuer band+mode bewerten.

        Returns: "fresh" (< 6h), "stale" (>= 6h, vorhanden), "missing".
        """
        store = self._get_diversity_store(scoring)
        if not store:
            return "missing"
        if store.is_valid_gain(band, ft_mode):
            return "fresh"
        entry = store.get(band, ft_mode)
        if entry and "gain_timestamp" in entry:
            return "stale"
        return "missing"

    def _check_diversity_preset(self, band: str, ft_mode: str, scoring: str) -> None:
        """Preset-Check bei Band/Modus-Wechsel mit aktiver Diversity.

        P1.CACHE-SIMPLE (v0.95.13): Diversity- und Gain-Cache komplett
        entkoppelt. Keine Modal-Wahl-Dialoge mehr fuer Routine-Aktionen.

        Logik:
        - Gain stale  → DXTuneDialog (auto-start, nur Abbruch). Wenn Ratio
                        fresh: nach Gain-OK Cache-Reuse statt Phase 3.
        - Gain missing → volle Pipeline (Gain + Ratio).
        - Gain fresh + Ratio fresh → Cache-Reuse (still, kein Toast).
        - Gain fresh + Ratio stale/missing → stille Auto-Ratio-Messung.
        """
        if not getattr(self, 'radio', None) or not self.radio.ip:
            return

        # P1.CACHE-SIMPLE: zentrales Reset des Pending-States als erste
        # Aktion — verhindert Leak von vorherigen Bandwechseln/Exceptions.
        self._pending_ratio_status = None

        ratio_status = self._assess_ratio(band, ft_mode, scoring)
        gain_status = self._assess_gain(band, ft_mode, scoring)
        from core.debug_log import debug_log as _dlog
        _dlog("DIV-CACHE", f"_check_diversity_preset {band}/{ft_mode} "
              f"scoring={scoring} -> ratio={ratio_status} gain={gain_status}")
        print(f"[Diversity] Cache-Status {band}/{ft_mode}: "
              f"ratio={ratio_status}, gain={gain_status}")

        if gain_status == "stale":
            # Gain abgelaufen → DXTuneDialog (auto-start, nur Abbruch).
            # Pending-Ratio-Status fuer _on_dx_tune_accepted merken.
            self._pending_ratio_status = ratio_status
            self._pending_diversity_scoring = scoring
            gain_scoring = "snr" if scoring == "dx" else "stations"
            _dlog("DIV-CACHE", "BRANCH=gain_stale -> DXTuneDialog (volle Pipeline)")
            print(f"[Diversity] {band}/{ft_mode}: Gain stale → DXTuneDialog")
            self._start_dx_tuning(scoring_mode=gain_scoring)
            self._update_statusbar()
            return

        if gain_status == "missing":
            # Komplett unkalibriert → volle Pipeline (Gain + Ratio).
            gain_scoring = "snr" if scoring == "dx" else "stations"
            _dlog("DIV-CACHE", "BRANCH=gain_missing -> volle Pipeline (Gain+Ratio)")
            print(f"[Diversity] {band}/{ft_mode}: Gain missing → volle Pipeline")
            self._pending_dx_diversity = True
            self._pending_diversity_scoring = scoring
            self._start_dx_tuning(scoring_mode=gain_scoring)
            return

        # gain_status == "fresh":
        if ratio_status == "fresh":
            # Beides frisch → Cache-Reuse (still, kein Toast).
            _dlog("DIV-CACHE", "BRANCH=both_fresh -> Cache-Reuse (kein Mess)")
            if self._try_diversity_cache_reuse(band, ft_mode, scoring):
                self._update_statusbar()
            return

        # Ratio stale/missing, Gain fresh → stille Auto-Ratio-Messung.
        # _enable_diversity startet Phase=measure → Phase 3 laeuft automatisch.
        _dlog("DIV-CACHE", f"BRANCH=ratio_{ratio_status}_gain_fresh "
              f"-> Auto-Phase-3-Mess")
        print(f"[Diversity] {band}/{ft_mode}: Ratio {ratio_status} mit Gain "
              f"fresh → automatische Ratio-Messung (Phase 3)")
        self._enable_diversity(scoring_mode=scoring)
        self._update_statusbar()

    def _handle_dx_tuning(self):
        """KALIBRIEREN-Button: komplette Pipeline je nach RX-Modus (v0.94).

        - **Normal:** nur Phase 2 (Gain-Messung) — Status quo.
          Speichert Gain im PresetStore Standard, kein Phase-3-Flag gesetzt.
        - **Diversity Standard/DX:** Phase 2 (Gain) + Phase 3 (Ratio-Messung)
          + Cache + Timer-Reset. ``_pending_dx_diversity = True`` triggert
          nach Phase-2-Erfolg automatisch Phase 3 ueber den bestehenden
          ``_on_dx_tune_accepted``-Pfad. ``_evaluate`` setzt am Ende
          ``_last_measured_at = time.time()`` (= Timer-Reset auf 0/1h-Frist
          startet von vorn).
        """
        scoring = getattr(self._diversity_ctrl, 'scoring_mode', 'normal')
        gain_scoring = "snr" if scoring == "dx" else "stations"
        if self._rx_mode == "diversity":
            self._pending_dx_diversity = True
            self._pending_diversity_scoring = scoring
            print(f"[Kalibrierung] Diversity-Pipeline ({scoring.upper()}): "
                  f"Phase 2 Gain + Phase 3 Ratio")
        else:
            print("[Kalibrierung] Normal-Modus: nur Phase 2 Gain")
        self._start_dx_tuning(scoring_mode=gain_scoring)

    def _start_tune_only(self, after_tune_callback=None) -> None:
        """TUNE allein — fuer Bandwechsel mit Cache-"Weiter"-Pfad.

        Sendet 3s Carrier auf der aktuellen Frequenz auf ANT1, damit ein
        externer/interner Tuner sich auf die Band-Last einstimmen kann.
        Danach wird `after_tune_callback` (z.B. `_enable_diversity`) gerufen.

        Race-Schutz: `self._tune_token` wird neu gesetzt. Wenn waehrend der
        3s ein Bandwechsel passiert (`_on_band_changed` setzt das Token auf
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
            f"TUNEN — {tune_power}W auf ANT1 fuer 3s ...", 0)
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

        QTimer.singleShot(3000, _after_tune)

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
                f"TUNEN — {tune_power}W auf ANT1 fuer 3s ...", 0)
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

            QTimer.singleShot(3000, _after_tune)
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
        """GUI sperren/entsperren waehrend Diversity-Pipeline (Tune+Gain+Einmessen).

        Setzt zusaetzlich `_gain_measure_locked`-Flag (v0.92 R1-Audit) das von
        `_on_band_changed`/`_on_mode_changed`/`_on_rx_mode_changed` als Frueh-
        Return-Trigger geprueft wird. Sperrt damit auch programmatische Pfade,
        nicht nur User-Klicks.
        """
        self._gain_measure_locked = locked
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
        """DX Tuning erfolgreich — Preset speichern.

        P22 (10.05.2026): Pipeline-Pfad entscheidet ob save_gain (sofort
        Disk) oder stage_gain (Memory, commit nach Phase 3) genutzt wird.
        - Normal-Mode → save_gain (kein Phase 3 geplant)
        - Diversity + pending_ratio == "fresh" → save_gain (Cache-Reuse,
          Phase 3 wird übersprungen)
        - Diversity + volle Pipeline → stage_gain (commit_with_ratio
          folgt aus mw_cycle._handle_diversity_measure nach Phase 3)
        """
        dialog = self._dx_tune_dialog
        if dialog is None:
            return
        r = dialog.get_results()
        band = self.settings.band
        ft_mode = self.settings.mode
        gain_mode = getattr(self, '_gain_scoring_mode', 'snr')
        div_scoring = "dx" if gain_mode == "snr" else "normal"
        store = getattr(self, '_dx_store', None) if div_scoring == "dx" else getattr(self, '_standard_store', None)

        # P22: Pipeline-Pfad bestimmen BEVOR wir schreiben.
        # will_run_phase3 = True → stage_gain (Memory), False → save_gain (Disk).
        _pending_ratio = getattr(self, '_pending_ratio_status', None)
        will_run_phase3 = (
            self._rx_mode == "diversity"
            and _pending_ratio != "fresh"
        )
        if store:
            if will_run_phase3:
                store.stage_gain(
                    band, ft_mode,
                    rxant=r.get("best_ant", "ANT1"),
                    ant1_gain=r.get("ant1_gain", r.get("best_gain", 0)),
                    ant2_gain=r.get("ant2_gain", r.get("best_gain", 0)),
                    ant1_avg=r.get("ant1_avg", 0.0),
                    ant2_avg=r.get("ant2_avg", 0.0),
                )
                # V3-A10 Konsistenz: stage_gain immer parallel zu
                # _pending_dx_diversity = True (commit folgt aus mw_cycle).
                self._pending_dx_diversity = True
            else:
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
            # P1.CACHE-SIMPLE (v0.95.13): Wenn Gain stale war (DXTuneDialog
            # via _check_diversity_preset) und Ratio fresh → Ratio aus Cache
            # uebernehmen statt Phase 3 erneut zu fahren.
            pending_ratio = getattr(self, '_pending_ratio_status', None)
            self._pending_ratio_status = None  # immer reset
            if pending_ratio == "fresh":
                self._pending_dx_diversity = False
                scoring = getattr(self, '_pending_diversity_scoring',
                                  getattr(self._diversity_ctrl, 'scoring_mode', 'normal'))
                self._pending_diversity_scoring = None
                print(f"[Diversity] Gain neu OK → Ratio aus Cache (Phase 3 skip)")
                if self._try_diversity_cache_reuse(band, ft_mode, scoring):
                    self._stats_warmup_cycles = 6
                    self._update_statusbar()
                    self._show_calibration_done(band, ant1_g, ant2_g)
                    return
                # Fallback: Cache-Reuse failt unerwartet → Phase 3 als Sicherheitsnetz
                print(f"[Diversity] Cache-Reuse failed unexpectedly → Phase 3 fallback")
                self._enable_diversity(scoring_mode=scoring)
                self._stats_warmup_cycles = 6
                self._update_statusbar()
                self._show_calibration_done(band, ant1_g, ant2_g)
                return

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
        """DX Tuning abgebrochen — P1.CACHE-SIMPLE: Stale-Acceptance.

        Bei Cancel mit alten Werten weiterarbeiten (Risiko-Akzeptanz).
        Wenn alte Werte vorhanden: still laden ohne Neu-Messung — kein
        Endlos-Pipeline-Restart. Wenn nichts da: Diversity deaktivieren.
        """
        import time as _time
        self._dx_tune_dialog = None
        self._set_gain_measure_lock(False)
        # v0.94: Pending-Flags bei Cancel zuruecksetzen — sonst startet
        # Phase 3 beim naechsten Diversity-Aktivieren ungewollt.
        self._pending_dx_diversity = False
        self._pending_diversity_scoring = None
        self._pending_ratio_status = None  # P1.CACHE-SIMPLE

        # Sicherheit: TX/Encoder definitiv stoppen
        if self.encoder.is_transmitting:
            self.encoder.abort()
        if self.radio.ip:
            self.radio.ptt_off()

        # P1.CACHE-SIMPLE: Stale-Acceptance — alte Werte laden statt
        # Pipeline neu zu starten (Endlos-Schleife verhindern).
        if self._rx_mode == "diversity" and self.radio.ip:
            scoring = getattr(self._diversity_ctrl, 'scoring_mode', 'normal')
            band = self.settings.band
            ft_mode = self.settings.mode
            store = self._get_diversity_store(scoring)
            entry = store.get(band, ft_mode) if store else None
            if entry and entry.get("ratio"):
                ratio = entry["ratio"]
                dominant = entry.get("dominant")
                ratio_age_sec = (_time.time()
                                 - entry.get("ratio_timestamp", _time.time()))
                print(f"[Diversity] Cancel → Stale-Acceptance: lade {ratio} "
                      f"(Alter ignoriert)")
                self._enable_diversity(
                    scoring_mode=scoring,
                    cached_ratio=ratio,
                    cached_dominant=dominant,
                    cached_age_seconds=ratio_age_sec,
                )
                self._stats_warmup_cycles = 6
            else:
                # Keine Werte vorhanden → Diversity deaktivieren
                print(f"[Diversity] Cancel ohne Werte → Diversity AUS")
                self._disable_diversity()
                self.control_panel.set_rx_mode("normal")
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
