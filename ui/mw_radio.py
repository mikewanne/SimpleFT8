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
        # Bundle J (v0.97.27): app_version mitgeben fuer Footer-Zeile.
        # Lazy-Import vermeidet Circular (mw_radio wird von main.py geladen).
        from main import APP_VERSION
        self._connect_dialog = ConnectStatusDialog(self, app_version=APP_VERSION)
        self.radio.connected.connect(
            self._connect_dialog.accept,
            Qt.ConnectionType.QueuedConnection,
        )

        # Auto-Connect im Hintergrund
        # P90: Worker-Thread als Instance-Var speichern, damit Cleanup
        # nach „ohne Radio weiter" auf sein Ende warten kann (join).
        self.control_panel.set_connection_status("searching")
        self._connect_thread = threading.Thread(
            target=self._connect_worker, daemon=True
        )
        self._connect_thread.start()

        # Modal blockiert GUI-Thread (WindowModal: Decoder/Signale laufen).
        # Returns wenn:
        #   - radio.connected feuert → dialog.accept() → exec() returned Accepted
        #   - User klickt "ohne Radio weiter" → reject() → Rejected
        #   - User klickt "Beenden" → QApplication.quit() → exec() returned
        self._connect_dialog.exec()

        # Cleanup nach exec()-Return
        was_user_cancelled = self._connect_dialog.was_cancelled
        try:
            self.radio.connected.disconnect(self._connect_dialog.accept)
        except (TypeError, RuntimeError):
            pass  # bereits disconnected oder Dialog tot

        # P82 (v0.97.55): „ohne Radio weiter" muss Connect IMMER überspringen,
        # auch wenn Worker erst NACH dem Klick erfolgreich connectet (Race).
        # Reine Slot-Disconnects reichen NICHT — `radio.connect()` macht
        # TCP-Setup unabhängig von Slots (`client gui`, `keepalive enable`,
        # Slice-Erstellung). Daher Flag-basierte Defensive in beiden Slots
        # `_on_radio_connected` und `_on_radio_disconnected` plus sofortiges
        # Disconnect falls Worker schon `_running=True` gesetzt hat.
        # Hardware-Risiko: ungewollter TX via Auto-Hunt/CQ/TUNE wenn App
        # gegen User-Willen connected war.
        if was_user_cancelled:
            self._demo_mode_forced = True
            # P90 (v0.97.60): Worker hart abbrechen BEVOR er Hardware
            # einrichtet (TCP/Panadapter/Slice/TX-Config). Reihenfolge
            # kritisch: abort_connect FIRST signalisiert dem laufenden
            # Worker den sofortigen Stopp, abort_reconnect verhindert
            # spaeteren Reconnect-Loop, disconnect raeumt halb-fertige
            # Sockets auf, join wartet auf Worker-Ende.
            try:
                self.radio.abort_connect()
            except Exception:
                pass
            self.radio.abort_reconnect()
            if getattr(self.radio, "_running", False):
                try:
                    self.radio.disconnect()
                except Exception:
                    pass
            # P90: Auf Worker-Ende warten (max 2s, sonst GUI-Hang).
            # Worker bricht im Normalfall in <0.1s ab (Check-Punkte
            # alle 1-2 Phasen), Timeout greift nur bei blockierendem
            # socket.connect() (max 5s).
            thread = getattr(self, "_connect_thread", None)
            if thread is not None and thread.is_alive():
                thread.join(timeout=2.0)
            self.control_panel.set_connection_status("disconnected")
            print("[P82] 'ohne Radio weiter' → Demo-Modus erzwungen")

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
        """Wird aufgerufen wenn FlexRadio verbunden ist.

        P82 (v0.97.55): User-Cancel-Override. Wenn Mike „ohne Radio weiter"
        geklickt hat während Worker noch lief, sofort wieder trennen —
        KEINE Hardware-Calls (`set_frequency`, `apply_ft8_preset`,
        `decoder.start`, `create_tx_stream`). Schützt vor ungewolltem TX.
        """
        if getattr(self, "_demo_mode_forced", False):
            print("[P82] Late-Connect nach User-Cancel → radio.disconnect()")
            try:
                self.radio.disconnect()
            except Exception:
                pass
            return
        self._reconnect_attempts = 0
        self.control_panel.set_connection_status("connected")
        # Gespeichertes Band + Frequenz setzen
        freq = self.settings.frequency_mhz
        band = self.settings.band
        self.radio.set_frequency(freq)
        self.radio.apply_ft8_preset(band=band)
        print(f"[FlexRadio] Band: {band}, Freq: {freq:.3f} MHz")
        self._update_statusbar()  # Statusbar sofort sichtbar nach Connect
        # P80 (v0.97.52): Normal-Gain aus unified _gain_store laden.
        # R1-F2 ROT: `is not None`-Check statt falsy — ant1_gain=0 ist
        # ein gueltiger (wenn auch unwahrscheinlicher) Wert.
        entry = self._gain_store.get(band)
        if entry is not None and entry.get("ant1_gain") is not None:
            gain = int(entry["ant1_gain"])
            label = "kalibriert" if entry.get("measured") else "Standard"
        else:
            gain = PREAMP_PRESETS.get(band, 10)
            label = "Standard"
        self.radio.set_rfgain(gain)
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
        # P53: SWR-Limit aus Settings an Radio propagieren
        self.radio.set_swr_limit(self.settings.get("swr_limit", 3.0))

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
            self._check_diversity_preset(band, pending_scoring)
        # P83 (v0.97.54): Gain-Status-Zeile initial nach Connect anzeigen.
        self._update_gain_status_display()

    def _on_radio_disconnected(self):
        """Verbindung verloren — unbegrenzt reconnecten mit Exponential Backoff.

        P82 (v0.97.55): Bei User-Cancel (`_demo_mode_forced=True`) KEIN
        Reconnect-Loop starten — Mike wollte Demo-Modus, kein automatisches
        Wiederverbinden bis App-Restart.
        """
        if getattr(self, "_demo_mode_forced", False):
            print("[P82] Disconnect nach User-Cancel → KEIN reconnect_forever")
            self.control_panel.set_connection_status("disconnected")
            return
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

    def _reset_psk_polling_on_change(self) -> None:
        """P10 (v0.97.15): sofortiger PSK-Re-Fetch nach Band/Modus-Wechsel.

        Zwei Pfade werden zuruckgesetzt:
        - Statusbar-Pfad (`_psk_worker`): `_psk_timer.start(0)` triggert
          sofortiges Fetch. `_psk_first_fetch` zurueck damit naechster
          Wechsel wieder den 2-Min-Schnellstart hat.
        - Karten-Pfad (`PSKReporterClient.reset_backoff`): falls Karte
          offen, Backoff zurueck auf base_s damit Karte ebenfalls
          sofort fetched.

        Defensiv `hasattr`-Check und try/except — Aufrufer-Sicherheit
        wenn Karte nie geoeffnet wurde oder Init-Reihenfolge anders.
        """
        if hasattr(self, '_psk_timer'):
            self._psk_first_fetch = True
            self._psk_timer.start(0)
        dlg = getattr(self, '_direction_map_dialog', None)
        if dlg is not None:
            canvas = getattr(dlg, '_map_canvas', None)
            client = getattr(canvas, '_psk_client', None) if canvas else None
            if client is not None:
                try:
                    # Final-R1 KP-1: Mode-Sync gegen veraltete Spot-Queries.
                    client.set_mode(self.settings.mode)
                    client.reset_backoff()
                except Exception as e:
                    print(f"[P10] PSK-Client-Update fehlgeschlagen: {e}")

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
        # P10 (v0.97.15): sofortiger PSK-Re-Fetch + Karten-Pfad-Reset.
        self._reset_psk_polling_on_change()
        self.timer.set_mode(mode)
        # CQ-Freq Dwell/Recalc-Intervall an neuen Modus anpassen
        self._diversity_ctrl.set_mode(mode)
        # Decoder + Encoder auf neues Protokoll umschalten
        self.decoder.set_protocol(mode)
        self.encoder.set_protocol(mode)
        self.qso_sm._mode = mode
        # P61 (v0.97.33): AutoHunt Mode-Awareness fuer Cooldown-Key
        # (call, band, mode) — selbe Station auf neuem Modus pickbar.
        if hasattr(self, "_auto_hunt"):
            self._auto_hunt.set_mode(mode)
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
            self._check_diversity_preset(band, scoring)
            return  # _check_diversity_preset ruft _update_statusbar auf
        # P80: Normal-Modus-Warnung wenn kein Gain-Preset fuer dieses Band.
        # Modus-Suffix (FT8/FT4/FT2) entfaellt — Hardware-Gain ist
        # modus-unabhaengig.
        if self.radio.ip:
            _gs = getattr(self, '_gain_store', None)
            if _gs and _gs.get(band) is None:
                self.statusBar().showMessage(
                    f"Kein Gain-Preset für {band} — bitte KALIBRIEREN", 6000
                )
        # P83 (v0.97.54): Gain-Status-Zeile aktualisieren (HTML-Format).
        self._update_gain_status_display()
        # P85 (v0.97.54): Win-Rate-Buffer leeren (FT-Mode-Wechsel = frische
        # Bedingungen → neuer Trend).
        self.control_panel.reset_win_rate_history()
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
        # P54 V2-F3: Re-Entry-Schutz waehrend aktivem TUNE (manuell oder
        # auto). Sonst koennte Bandwechsel mid-tune den State korrumpieren.
        if getattr(self, '_tune_active', False):
            current = self.settings.band
            _dlog("BAND", f"IGNORED — TUNE laeuft, bleibe auf {current}")
            print(f"[Bandwechsel ignoriert: TUNE laeuft, bleibe auf {current}]")
            self.control_panel._set_band(current)
            return
        # Race-Schutz: ausstehende TUNE-Callbacks ungueltig machen, sonst ruft
        # ein 5-Sek-Timer aus dem alten Band-Kontext _enable_diversity() fuer
        # das jetzt verlassene Band auf.
        self._tune_token = None
        self.settings.set("band", band)
        freq = self.settings.frequency_mhz
        self._has_sent_cq = False

        # P10 (v0.97.15): bei Bandwechsel sofortiger PSK-Re-Fetch
        # (Statusbar-Pfad) + Backoff-Reset im Karten-Pfad falls offen.
        # Statt bis zu 5 Min auf naechsten _psk_timer-Tick zu warten,
        # sieht User Bands-PSK-Daten sofort.
        self._reset_psk_polling_on_change()

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
        # P34-Stufe2: DiversityController nur noch Histogramm + Pattern-
        # Counter + CQ-Frequenz-Such. Reset bei Bandwechsel räumt alles
        # auf. Dynamic-Buffer wurde weiter oben schon geleert.
        radio_ready = bool(self.radio.ip)
        _dlog("BAND", f"_diversity_ctrl.reset() radio_ready={radio_ready}")
        self._diversity_ctrl.reset()
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
            # P34-Stufe2: Dynamic ist Default — immer „DYNAMISCH (live)"-
            # Anzeige. _enable_diversity wird gleich Phase auf operate +
            # 50:50 setzen.
            self.control_panel.update_diversity_ratio(
                "50:50",
                scoring_mode=getattr(self._diversity_ctrl, 'scoring_mode', 'normal'),
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
                    # P83 (v0.97.54): dx_info wird unten via Helper
                    # konsistent aktualisiert (HTML-Format mit Verfall).
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
        # P54 (v0.97.44): Auto-TUNE bei Bandwechsel — wenn Setting aktiv,
        # Radio verbunden, Band nicht SWR-blockiert und Tuner vorhanden.
        # Blockt mit modalem Dialog bis SWR-Good oder Timeout/Cancel.
        # Speichert RFPreset-Stuetzpunkt (P54b) bei Erfolg → _apply_rf_preset
        # wird im Post-Check ein zweites Mal aufgerufen damit der frische
        # 10-W-Wert sofort wirkt.
        #
        # P71 (v0.97.47) Bug 2: Zusätzliche Guards gegen ungewollten
        # App-Start-Trigger:
        # - `_initial_band_set` Flag (gesetzt in MainWindow.__init__,
        #   geclearted am Ende von __init__).
        # - RFPresetStore-Anker-Check: wenn 10W-Eintrag bereits existiert,
        #   ist Auto-Tune nicht nötig — Belt-and-suspenders gegen mögliche
        #   Bandpilot-Re-Trigger-Pfade die das Flag umgehen.
        _has_anchor = False
        try:
            mw = self._main_window if hasattr(self, "_main_window") else self
            _has_anchor = self.rf_preset_store.has_anchor(
                self.radio.radio_type, band, watt=10)
        except (AttributeError, Exception):
            _has_anchor = False
        if (self.settings.get("auto_tune_on_band_change", True)
                and self.radio.ip
                and band.upper() not in self._swr_blocked_bands
                and self.settings.get("tuner_present", True)
                and not getattr(self, "_initial_band_set", False)
                and not _has_anchor):
            _dlog("BAND", f"_start_auto_tune_for_band_change({band})")
            success = self._start_auto_tune_for_band_change(band)
            if not success:
                self.qso_panel.add_info(
                    f"⚠ Auto-TUNE {band.upper()} fehlgeschlagen oder abgebrochen")
        elif self.settings.get("auto_tune_on_band_change", True):
            # P71: nicht-getriggerter Auto-Tune sichtbar in Debug-Log machen
            _reason = (
                "initial_band_set" if getattr(self, "_initial_band_set", False)
                else "anchor_exists" if _has_anchor
                else "skip_other"
            )
            _dlog("BAND", f"Auto-TUNE skipped: reason={_reason}")
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
            scoring = getattr(self._diversity_ctrl, 'scoring_mode', 'normal')
            _dlog("BAND", f"_check_diversity_preset({band}, scoring={scoring})")
            self._check_diversity_preset(band, scoring)
            return  # _check_diversity_preset ruft _update_statusbar auf
        # P83 (v0.97.54): Gain-Status-Zeile aktualisieren (HTML-Format).
        self._update_gain_status_display()
        # P85 (v0.97.54): Win-Rate-Buffer leeren (frisches Band = frischer Trend).
        self.control_panel.reset_win_rate_history()
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
        # Bei RX-Mode-Wechsel aktive Power-Modi (OMNI, AUTO HUNT) stoppen
        if mode != old_mode:
            if hasattr(self, "_omni_cq") and self._omni_cq.is_active():
                self._omni_cq.stop("rx_mode_change")
            if hasattr(self, "_auto_hunt") and self._auto_hunt.active:
                self._auto_hunt.stop_auto_hunt("rx_mode_change")
            # Bundle I (v0.97.26): normalen CQ + armed-en Encoder-Slot
            # mit-stoppen — analog Bandwechsel-Pattern (siehe _on_band_changed).
            # Mike-Field-Test 14.05.: OMNI war an, Mode-Wechsel stoppte OMNI
            # visuell, aber ein verzögerter CQ-Slot wurde aus dem normalen
            # CQ-Pfad (qso_sm.cq_mode) noch gesendet. R1-V4-pro Finding 1:
            # encoder.abort() + ptt_off() ist nötig damit kein armed-er
            # Slot durchrutscht.
            if self.qso_sm.cq_mode or self.qso_sm.state != QSOState.IDLE:
                self.qso_sm.stop_cq()
                self.qso_sm.cancel()
                self.control_panel.set_cq_active(False)
            if self.encoder.is_transmitting:
                self.encoder.abort()
                if self.radio.ip:
                    self.radio.ptt_off()

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

        # Bundle E (v0.97.22): TX-Slot-Lock-Buttons sichtbar nur in Normal.
        # In Diversity: Buttons aus (Lock wirkt nur Normal), State in
        # Settings bleibt persistiert. Bei Wechsel zurück Normal: Buttons
        # aus Settings geladen.
        if hasattr(self, "qso_panel"):
            self.qso_panel.set_slot_buttons_visible(mode == "normal")
            if mode == "normal":
                self.qso_panel.set_tx_slot_lock_buttons(
                    self.settings.get_tx_slot_lock())

        # Neuen Modus aktivieren
        if mode == "normal":
            self._rx_mode = "normal"
            self._normal_stations = {}
            self._apply_normal_mode()
            self.control_panel._freq_hist.setVisible(False)
            self.control_panel.btn_diversity.setText("DIVERSITY")  # Reset Button-Text
        elif mode == "diversity":
            # Bundle H (v0.97.25): Bandpilot-Aware-Pfad bei Klick auf
            # DIVERSITY. off → Wahl-Dialog (heute), auto+rec → Toast +
            # auto-pick, auto+rec=None → Wahl-Dialog mit Mangel-Text,
            # manual+rec → Manual-Dialog, manual+rec=None → Mangel-Dialog.
            from datetime import datetime, timezone
            from core.mode_recommender import code_mode_to_scoring

            bp_mode = self.settings.get("bandpilot_mode", "off")
            band = self.settings.band
            utc_hour = datetime.now(timezone.utc).hour

            rec = None
            bp = getattr(self, "_bandpilot", None)
            if bp is not None and bp_mode in ("auto", "manual"):
                try:
                    rec = bp.recommend(
                        band, utc_hour, current_mode="normal",
                        allowed_modes=("diversity_normal", "diversity_dx"),
                    )
                except Exception as e:
                    print(f"[Bandpilot H-Path] Aggregations-Fehler: {e}")
                    rec = None

            # R1-S3: defensive no_change-Behandlung (sollte bei H eh
            # nicht vorkommen weil current=normal nie in allowed_modes)
            if rec is not None and rec.get("decision") == "no_change":
                rec = None

            scoring = None
            if bp_mode == "auto" and rec is not None:
                scoring = code_mode_to_scoring(rec["decision_mode"])
                self._show_bandpilot_auto_toast(band, utc_hour, rec)
            elif bp_mode == "manual" and rec is not None:
                chosen = self._show_bandpilot_manual_dialog(
                    band, utc_hour, rec, current=None,
                )
                if chosen is None:
                    self.control_panel.set_rx_mode("normal")
                    self._update_statusbar()
                    return
                scoring = code_mode_to_scoring(chosen)
            else:
                # off, oder (auto/manual + rec=None): dynamischer Wahl-Dialog
                intro_text = (
                    "Nicht genug Daten für Bandpilot — bitte selbst wählen:"
                    if bp_mode in ("auto", "manual")
                    else "Welchen Modus verwenden?"
                )
                scoring = self._show_diversity_choice_dialog(intro_text)
                if scoring is None:
                    self.control_panel.set_rx_mode("normal")
                    self._update_statusbar()
                    return

            self._activate_diversity_with_scoring(scoring)

        # Mode-Coupling-Update auch wenn _apply_normal_mode /
        # _enable_diversity nicht direkt durchgelaufen sind (early-return-Pfade)
        self._update_button_visibility()
        self._update_statusbar()

    def _show_diversity_choice_dialog(self, intro_text: str) -> str | None:
        """Bundle H (v0.97.25): Std/DX-Wahl-Dialog mit dynamischem Intro.

        Args:
            intro_text: Dialog-Titel-Text, je nach Bandpilot-Status
                („Welchen Modus verwenden?" bei off, „Nicht genug Daten
                — bitte selbst wählen" bei auto/manual ohne rec).

        Returns:
            ``"normal"`` (Standard-Scoring) | ``"dx"`` | ``None`` (Abbruch).

        R1-S1: WA_DeleteOnClose für saubere Speicherfreigabe.
        """
        from PySide6.QtWidgets import (
            QDialog, QVBoxLayout, QPushButton, QLabel, QFrame
        )
        _dlg = QDialog(self)
        _dlg.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
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
        _lbl = QLabel(intro_text)
        _lbl.setObjectName("lbl_mode_title")
        _lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        _lay.addWidget(_lbl)
        _btn_std = QPushButton("Diversity Standard")
        _btn_dx = QPushButton("Diversity DX")
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
        _btn_std.clicked.connect(
            lambda: (_result.__setitem__(0, "normal"), _dlg.accept()))
        _btn_dx.clicked.connect(
            lambda: (_result.__setitem__(0, "dx"), _dlg.accept()))
        _btn_cancel.clicked.connect(_dlg.reject)
        _dlg.exec()
        return _result[0]

    @Slot()
    def _on_diversity_subtoggle_requested(self):
        """Bundle G (v0.97.24): Toggle Std ↔ DX bei 2. Div-Klick.

        Wird vom control_panel emittiert wenn User im Diversity-Modus
        nochmal auf DIVERSITY klickt. Wechselt direkt zwischen
        scoring="normal" (Standard) und scoring="dx".

        Nur wirksam wenn Bandpilot=off (sonst entscheidet Bandpilot).
        Bei Pipeline-Lock / fehlender Radio-IP no-op.

        R1-K1+K2 (Bundle G): OMNI+Auto-Hunt werden gestoppt analog zu
        `_on_rx_mode_changed` Z.541-544 — verhindert Encoder-Konflikt
        wenn Toggle einen DXTuneDialog auslöst (fehlender Gain im
        Ziel-Store) und schützt vor get_free_cq_freq-Race auf leeres
        Stations-Histogramm nach _diversity_stations={}.
        """
        bp_mode = self.settings.get("bandpilot_mode", "off")
        if bp_mode != "off":
            return  # Auto/Manual: Bandpilot entscheidet, kein User-Toggle
        if getattr(self, '_gain_measure_locked', False):
            return  # Pipeline läuft
        if not self.radio.ip:
            return
        # R1-K1+K2: OMNI+Hunt stoppen vor Sub-Mode-Wechsel
        if hasattr(self, "_omni_cq") and self._omni_cq.is_active():
            self._omni_cq.stop("scoring_toggle")
        if hasattr(self, "_auto_hunt") and self._auto_hunt.active:
            self._auto_hunt.stop_auto_hunt("scoring_toggle")
        current = getattr(self._diversity_ctrl, 'scoring_mode', 'normal')
        new = "dx" if current == "normal" else "normal"
        self._activate_diversity_with_scoring(new)

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

        # P1.CACHE-SIMPLE: einheitliche Dispatch-Logik (Gain-Cache /
        # DXTuneDialog). _check_diversity_preset ruft am Ende
        # _enable_diversity → activate() der Dynamic-Pipeline.
        # P80: ft_mode-Parameter entfaellt (modus-unabhaengiger Gain).
        self._check_diversity_preset(band, scoring)

        # P34-Stufe2 (AK6): scoring_mode-Wechsel-Reset explicit. Buffer
        # leeren falls Dynamic schon laief (zB Modus-Wechsel
        # Standard→DX innerhalb Diversity).
        if (getattr(self, "_dynamic_ctrl", None) is not None
                and self._dynamic_ctrl.is_active()):
            self._dynamic_ctrl.reset()

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
            # P46 R1-F2: Doppelaufruf vermeiden. _disable_diversity setzt
            # selbst _rx_mode="normal" + _apply_normal_mode() +
            # control_panel.set_rx_mode("normal"). Nur UI-only Setter
            # (btn_diversity-Text, freq_hist) bleiben hier.
            if self._rx_mode == "diversity":
                self._disable_diversity()
            else:
                # Schon normal aber explicit Re-Sync (z.B. UI-Recovery)
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

        # P46 (12.05.2026): P35-Bug-E zurueckgenommen — Bandpilot
        # darf jetzt auch in Normal aktiv werden (3-Wege-Vergleich
        # Normal/Std/DX). Mike-Vision "ganz oder gar nicht".

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

        # P46 (12.05.2026): P35-Bug-E-Defensive zurueckgenommen — Normal
        # ist legitimer Bandpilot-Target wenn historische Daten zeigen.

        if not self.encoder.is_transmitting:
            # Sofort wechseln
            self._show_bandpilot_auto_toast(band, utc_hour, rec)
            self._set_rx_mode_direct(target)
            return True

        # TX laeuft → verzoegern bis tx_finished
        # P46 R1-F3: current zusaetzlich speichern fuer Konsistenz-Check
        # bei tx_finished (User koennte zwischenzeitlich manuell wechseln).
        self._show_bandpilot_auto_toast(band, utc_hour, rec)
        current = self._current_rx_mode_string()
        self._bandpilot_pending = (band, utc_hour, rec, target, current)
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

        Modus-Konsistenz-Pruefung (P46 R1-F3, 13.05.2026):
        Wenn User waehrend TX manuell den RX-Modus gewechselt hat
        (z.B. Diversity-Toggle), ist die pending-Empfehlung ebenfalls
        ungueltig — Mike's manuelle Wahl hat Vorrang.
        """
        pending = getattr(self, "_bandpilot_pending", None)
        if pending is None:
            return
        pending_band, _utc_hour, _rec, target, pending_current = pending
        self._bandpilot_pending = None
        # Aktuelles Band vs pending-Band: wenn unterschiedlich → verwerfen
        current_band = getattr(self.settings, "band", None)
        if current_band != pending_band:
            print(f"[Bandpilot] Pending fuer {pending_band} verworfen "
                  f"(aktuell: {current_band})")
            return
        # P46 R1-F3: aktueller Modus vs pending-Modus
        current_now = self._current_rx_mode_string()
        if current_now != pending_current:
            print(f"[Bandpilot] Pending verworfen — Modus zwischenzeitlich "
                  f"manuell geaendert ({pending_current} → {current_now})")
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

    def _enable_diversity(self, scoring_mode: str = "normal") -> None:
        """Diversity aktivieren: Antennenwechsel-Pattern + Dynamic-Pipeline.

        P34-Stufe2 (v0.97.19): einziger Pfad. Phase=operate sofort,
        Ratio=50:50 als Start, ``DynamicDiversityController`` übernimmt
        live nach 5+5 Slots (~75 s bei FT8).

        Deferred-Branch (R1-F1 KRITISCH): bei ``radio.ip is None`` nur
        ``_pending_diversity_init`` setzen + Ratio-Defaults, KEIN
        ``activate()``. Resume via ``_on_radio_connected`` →
        ``_check_diversity_preset`` triggert dann erneut.
        """
        self._diversity_in_operate = True  # P34-Stufe2: Phase ab sofort operate
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
        mode = self.settings.mode
        band = self.settings.band
        self._diversity_ctrl.scoring_mode = scoring_mode

        from core.debug_log import debug_log as _dlog
        _dlog("DIV-EN", f"_enable_diversity scoring={scoring_mode}")

        # R1-F1 KRITISCH: Deferred-Branch — Radio noch nicht verbunden.
        if not getattr(self.radio, 'ip', None):
            self._pending_diversity_init = scoring_mode
            self._diversity_ctrl.ratio = "50:50"
            self._diversity_ctrl.dominant = None
            self._set_cq_locked(False)
            self._set_gain_measure_lock(False)
            print(f"[Diversity] Radio nicht verbunden — Init aufgeschoben "
                  f"(scoring={scoring_mode})")
            _dlog("DIV-EN", f"Aufgeschoben scoring={scoring_mode}")
            # KEIN activate() im Deferred-Branch — Resume nach Connect macht's.
            return

        # Normal-Branch: Radio verbunden — Dynamic aktivieren.
        self._diversity_ctrl.reset()
        self._diversity_ctrl.ratio = "50:50"
        self._diversity_ctrl.dominant = None
        if getattr(self, "_dynamic_ctrl", None) is not None:
            self._dynamic_ctrl.reset()      # Buffer leer fuer fresh Start
            self._dynamic_ctrl.activate()   # AK4
        self._set_cq_locked(False)
        self._set_gain_measure_lock(False)
        # AK14: Setup-Operationen aus altem _handle_diversity_measure-
        # measure→operate-Uebergang sind hier — Phase ab sofort operate.
        self._stats_warmup_cycles = 6
        print(f"[Diversity] Phase=operate (Dynamic startet live) — "
              f"50:50 startet, Dynamic uebernimmt in ~75 s ({scoring_mode.upper()})")
        self.control_panel.update_diversity_ratio(
            "50:50",
            scoring_mode=scoring_mode,
            current_ant=getattr(self, "_diversity_current_ant", None),
        )
        self.control_panel.update_diversity_counts(0, 0)

        # P80: unified _gain_store, modus-unabhaengiger Gain.
        preset = self._gain_store.get(band)

        if preset and "ant1_gain" in preset:
            # Preset vorhanden: per-Antenne optimierte Gains laden + sofort ans Radio
            self._diversity_ant1_gain = preset["ant1_gain"]
            self._diversity_ant2_gain = preset["ant2_gain"]
            measured = preset.get("measured", "?")
            if self.radio.ip:
                self.radio.set_rx_antenna("ANT1")
                self.radio.set_rfgain(self._diversity_ant1_gain)
            print(
                f"[Diversity] Preset geladen: ANT1 G{self._diversity_ant1_gain}, "
                f"ANT2 G{self._diversity_ant2_gain} (gemessen {measured})"
            )
        else:
            # Kein Preset: Standard-Gains + Hinweis
            self._diversity_ant1_gain = PREAMP_PRESETS.get(band, 10)
            self._diversity_ant2_gain = PREAMP_PRESETS.get(band, 10) + 10
            print(f"[Diversity] AKTIV — Standard-Gains, kein Preset fuer {band}")

        # P83 (v0.97.54): dx_info ueber zentralen Helper aktualisieren.
        self._update_gain_status_display()
        # P85 (v0.97.54): Win-Rate-Buffer leeren (Diversity-Enable = frischer Start).
        self.control_panel.reset_win_rate_history()

        # Mode-Coupling Buttons aktualisieren (Diversity aktiv → Power-Buttons sichtbar)
        self._update_button_visibility()

    def _disable_diversity(self):
        """Diversity deaktivieren: zurueck auf ANT1."""
        # P34: Dynamic deaktivieren wenn Diversity aus → kein Vergleich moeglich
        if getattr(self, "_dynamic_ctrl", None) and self._dynamic_ctrl.is_active():
            self._dynamic_ctrl.deactivate()
        # P22 Final-R1 SOLLTE-2: staged-Daten beim Disable verwerfen.
        # P80: nur noch 1 Store.
        band = self.settings.band
        if hasattr(self._gain_store, 'discard_staged'):
            self._gain_store.discard_staged(band)
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
        # P83 (v0.97.54): dx_info zeigt nun auch im Normal-Mode den
        # Gain-Status mit Verfalls-Counter (statt leer).
        self._update_gain_status_display()
        # P85 (v0.97.54): Win-Rate-Buffer leeren (Diversity beendet).
        self.control_panel.reset_win_rate_history()
        self.control_panel.update_diversity_counts(0, 0)
        print("[Diversity] Deaktiviert")

    def _assess_gain(self, band: str) -> str:
        """P80: Gain-Cache-Status fuer band bewerten (modus-unabhaengig).

        Returns: "fresh" (< 6h + valid), "stale" (>= 6h, vorhanden),
                 "missing" (kein Eintrag).
        """
        store = self._gain_store
        if store.is_valid_gain(band):
            return "fresh"
        entry = store.get(band)
        if entry and "gain_timestamp" in entry:
            return "stale"
        return "missing"

    def _format_gain_status(self, band: str, rx_mode: str) -> str:
        """P83 (v0.97.54): HTML-Text fuer dx_info-Label.

        Format:
          fresh: `ANT1(G10) + ANT2(G20) · noch 4h` (Suffix farbig)
          stale: `ANT1(G10) + ANT2(G20) · Re-Mess faellig` (rot)
          missing: `nicht kalibriert · G10 (Std)` (grau)

        Werte-Teil immer dunkelgrau (#668877), Suffix farbcodiert nach
        verbleibender Zeit (gruen >2h, orange <=2h, rot <=1h).
        """
        entry = self._gain_store.get(band)
        default_g = PREAMP_PRESETS.get(band, 10)
        if not entry:
            return (
                f"<span style='color:#888;'>nicht kalibriert · "
                f"G{default_g} (Std)</span>"
            )
        ts = entry.get("gain_timestamp", 0.0)
        if not ts or ts <= 0:
            # Migration-Marker (ts=0.0) → behandeln wie missing.
            return (
                f"<span style='color:#888;'>nicht kalibriert · "
                f"G{default_g} (Std)</span>"
            )
        ant1_g = entry.get("ant1_gain", default_g)
        ant2_g = entry.get("ant2_gain", 0)
        ant2_cal = entry.get("ant2_calibrated", False)
        if rx_mode == "diversity" and ant2_cal:
            values = f"ANT1(G{ant1_g}) + ANT2(G{ant2_g})"
        else:
            values = f"ANT1(G{ant1_g})"
        age_s = time.time() - ts
        remaining_s = 6 * 3600 - age_s
        if remaining_s <= 0:
            # P86 (v0.97.56): KALIBRIEREN-Button ist Diversity-only.
            # Im Normal-Modus Hinweis ergänzen wo Mike kalibrieren kann.
            suffix_text = "· Re-Mess fällig"
            if rx_mode == "normal":
                suffix_text += " → DIVERSITY"
            return (
                f"<span style='color:#668877;'>{values}</span> "
                f"<span style='color:#FF3333;'>{suffix_text}</span>"
            )
        remaining_h = remaining_s / 3600
        h = max(1, round(remaining_h))
        if remaining_h > 2:
            color = "#44CC44"
        elif remaining_h > 1:
            color = "#FFAA00"
        else:
            color = "#FF3333"
        return (
            f"<span style='color:#668877;'>{values}</span> "
            f"<span style='color:{color};'>· noch {h}h</span>"
        )

    def _update_gain_status_display(self) -> None:
        """P83: dx_info-Label aktualisieren aus aktuellem Band+RX-Mode.

        Aktions-getriggert (KEIN extra Timer, Mike-Spec 19.05.2026).
        Aufruf-Stellen: set_band/set_mode-Handler, _enable_diversity,
        _disable_diversity, _on_dx_tune_accepted, _on_radio_connected.
        """
        band = self.settings.band
        rx_mode = self._rx_mode
        html = self._format_gain_status(band, rx_mode)
        self.control_panel.dx_info.setText(html)
        # Stylesheet auf font-size + family — Farbe kommt aus HTML-Spans.
        self.control_panel.dx_info.setStyleSheet(
            "font-size: 10px; font-family: Menlo;"
        )

    def _check_diversity_preset(self, band: str, scoring: str) -> None:
        """Preset-Check bei Band/Modus-Wechsel mit aktiver Diversity.

        P80 (v0.97.52): ft_mode raus — Gain ist band-spezifisch.
        scoring (standard/dx) bleibt fuer DynamicDiversityController.

        Logik:
        - Gain fresh + ant2_calibrated=True → ``_enable_diversity`` direkt
        - Gain stale/missing/ant2_uncalibrated → DXTuneDialog

        P63 (v0.97.36): Marker-Pre-Check oben — bei rotem Marker werden
        Gain-Mess-Pipeline + Diversity-Start blockiert.

        P80 R1-F1 ROT: ``ant2_calibrated``-Check verhindert dass Diversity
        mit Normal-only-Migration-Werten (ant2_gain=0) startet.
        """
        if not getattr(self, 'radio', None) or not self.radio.ip:
            return

        # P63 AC8: Marker-Pre-Check
        if band.upper() in self._swr_blocked_bands:
            self.qso_panel.add_info(
                f"⚠ Diversity blockiert — Band {band.upper()} SWR-Sperre. "
                "Manueller TUNE zum Freischalten.")
            self._update_statusbar()
            return

        store = self._gain_store
        entry = store.get(band)
        # P80 R1-F1 ROT: Diversity verlangt ant2_calibrated=True.
        ant2_cal = bool(entry and entry.get("ant2_calibrated") is True)
        gain_status = self._assess_gain(band)
        gain_fresh_for_div = (gain_status == "fresh") and ant2_cal

        from core.debug_log import debug_log as _dlog
        _dlog("DIV-CACHE", f"_check_diversity_preset {band} "
              f"scoring={scoring} -> gain={gain_status} ant2_cal={ant2_cal}")
        print(f"[Diversity] Cache-Status {band}: gain={gain_status} "
              f"ant2_cal={ant2_cal}")

        if gain_fresh_for_div:
            _dlog("DIV-CACHE", "BRANCH=gain_fresh_diversity -> direkt")
            print(f"[Diversity] {band}: Gain fresh + ant2_cal → Dynamic startet")
            self._enable_diversity(scoring_mode=scoring)
            self._update_statusbar()
            return

        # Gain stale / missing / ant2_uncalibrated → DXTuneDialog
        self._pending_dx_diversity = True
        self._pending_diversity_scoring = scoring
        _branch = ("ant2_uncalibrated" if gain_status == "fresh"
                   else f"gain_{gain_status}")
        _dlog("DIV-CACHE", f"BRANCH={_branch} -> DXTuneDialog")
        print(f"[Diversity] {band}: {_branch} → DXTuneDialog")
        # P62 (v0.97.35): 1s Pause zwischen TX-Stop und Gain-Mess-TUNE.
        # Mike-Feedback Field-Test P60-F6: ohne Pause wirkt der Uebergang
        # visuell wie „80W → 10W TUNE" statt sauberes „TX aus → neue
        # Messung". Lock greift SOFORT (sperrt UI), Statusbar zeigt
        # Hinweis, dann nach 1000ms eigentliche Tune-Pipeline. Race-Schutz
        # via existierenden `_gain_measure_locked`-Check in
        # `_on_band_changed`/`_on_mode_changed`/`_on_rx_mode_changed`.
        from PySide6.QtCore import QTimer
        self._set_gain_measure_lock(True)
        self.statusBar().showMessage(
            "TX gestoppt — Gain-Messung startet in 1s ...", 1500)
        # P80: gain_scoring aus dem scoring-Parameter ableiten (snr fuer dx,
        # stations fuer std/normal — analog _handle_dx_tuning).
        gain_scoring = "snr" if scoring == "dx" else "stations"
        QTimer.singleShot(
            1000,
            lambda: self._start_dx_tuning(scoring_mode=gain_scoring))
        self._update_statusbar()

    def _handle_dx_tuning(self):
        """KALIBRIEREN-Button: Diversity-Mess-Pipeline (Phase 2 + Phase 3).

        P86 (v0.97.56): Diversity-only Feature. Button ist im Normal-Mode
        hidden (siehe `_update_button_visibility`). Normal-Mode liest
        ANT1-Gain aus Unified Store (P80) — keine eigene Mess-Routine.
        Defensive Early-Return falls Methode direkt im Normal-Mode
        aufgerufen wird (z.B. via altem Code/Test).

        Pipeline:
        - Phase 2 (Gain-Messung 8 Zyklen, misst ANT1+ANT2, speichert mit
          `ant2_calibrated=True`).
        - Phase 3 (Ratio-Messung) — `_pending_dx_diversity=True` triggert
          nach Phase-2-Erfolg automatisch Phase 3 ueber den bestehenden
          `_on_dx_tune_accepted`-Pfad. `_evaluate` setzt am Ende
          `_last_measured_at = time.time()`.
        """
        if self._rx_mode != "diversity":
            # P86: Button sollte hidden sein. Defensive return gegen
            # direkten Methoden-Aufruf (Robustheit, Backwards-Compat).
            print("[P86] KALIBRIEREN im Normal-Mode ignoriert "
                  "(Button sollte hidden sein)")
            return
        scoring = getattr(self._diversity_ctrl, 'scoring_mode', 'normal')
        gain_scoring = "snr" if scoring == "dx" else "stations"
        self._pending_dx_diversity = True
        self._pending_diversity_scoring = scoring
        print(f"[Kalibrierung] Diversity-Pipeline ({scoring.upper()}): "
              f"Phase 2 Gain + Phase 3 Ratio")
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
        """Diversity Pipeline: TUNE (automatisch) → Gain-Messung → Einmessen.

        P63 (v0.97.36):
        - AC8: Marker-Pre-Check (blockiert Auto-Pipeline bei rotem Band)
        - AC9: Tuner=False → Auto-TUNE-Phase skip + Power-Reset (R1-F3)
        - AC11: Auto-TUNE-Fehler-Pfad ruft `_set_gain_measure_lock(False)`
          + setzt Marker (R1-F2)
        - AC13: explizites `set_tx_antenna("ANT1")` vor Auto-TUNE (HW-Pflicht)
        """
        import time as _time
        self._stats_warmup_cycles = 99999  # Blockiert bis nach Einmessen+Warmup
        self._gain_scoring_mode = scoring_mode
        from PySide6.QtCore import QTimer

        # P63 AC8: Marker-Pre-Check
        band = self.settings.band.upper()
        if band in self._swr_blocked_bands:
            self.qso_panel.add_info(
                f"⚠ Gain-Messung blockiert — Band {band} SWR-Sperre. "
                "Manueller TUNE zum Freischalten.")
            self._set_gain_measure_lock(False)
            return

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
        tuner_present = self.settings.get("tuner_present", True)

        # P63 AC9/AC13: Auto-TUNE nur wenn Radio verbunden UND Tuner an
        if self.radio.ip and tuner_present:
            self.radio.set_tx_antenna("ANT1")     # AC13 HW-Pflicht
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
                    # P63 AC11/R1-F2: Lock-Release + Marker-Set bei SWR-Fehler
                    self._set_gain_measure_lock(False)
                    if self.settings.get("tuner_present", True):
                        self._swr_blocked_bands.add(band)
                        print(f"[P63] Auto-TUNE-Fehler → Marker {band} gesetzt")
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
            # P63 AC9/R1-F3: Kein Radio ODER Tuner=NEIN → direkt Gain-Mess.
            # Power-Reset wenn Radio verbunden (sonst hängt User-veränderter
            # Power-Wert nach).
            if self.radio.ip:
                self.radio.set_power(self.settings.get("power_preset", 15))
            self._open_dx_tune_dialog()

    def _open_dx_tune_dialog(self):
        """DX Tune Dialog oeffnen — NICHT-MODAL, immer im Vordergrund, GUI gesperrt.

        P75 (v0.97.48): Wenn der Auto-TUNE bei Bandwechsel gerade
        erfolgreich war (SWR ≤ Limit), übergeben wir `prev_tune_swr` →
        DXTuneDialog zeigt Header-Banner als visueller Übergang
        Phase 1 (TUNE) → Phase 2 (Gain-Messung). Mike-Spec „ein Fenster
        was erst die aktion und das beenden anzeigt".
        """
        # Letzte Sicherheitspruefung: PTT definitiv AUS
        if self.radio.ip:
            self.radio.ptt_off()

        from ui.dx_tune_dialog import DXTuneDialog
        band = self.settings.band
        scoring = getattr(self, '_gain_scoring_mode', 'snr')

        # P75: Bei aktuell-gutem SWR nach Auto-Tune Banner anzeigen.
        # `_auto_tune_running` ist beim Eintritt schon False (Dialog-
        # Cleanup), aber `last_swr` ist frisch. swr_limit gibt
        # Threshold; bei stale/dead radio.ip → None.
        prev_swr: float | None = None
        try:
            swr_limit = self.settings.get("swr_limit", 3.0)
            if self.radio.ip and self.radio.last_swr is not None:
                if 0 < self.radio.last_swr <= swr_limit:
                    prev_swr = float(self.radio.last_swr)
        except (AttributeError, TypeError, ValueError):
            prev_swr = None

        dialog = DXTuneDialog(
            self.radio, band, scoring_mode=scoring,
            rx_mode=self._rx_mode, parent=self,
            prev_tune_swr=prev_swr,
        )
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

        P80 (v0.97.52): single-save in unified ``_gain_store`` —
        1 Eintrag pro Band, gilt fuer Normal + Diversity Std/DX +
        FT8/FT4/FT2. DXTuneDialog misst immer beide Antennen,
        ``ant2_calibrated=True``.
        """
        dialog = self._dx_tune_dialog
        if dialog is None:
            return
        r = dialog.get_results()
        band = self.settings.band
        ft_mode = self.settings.mode

        # P51-Erbe: Dialog liefert ggf. "standard"/"dx"-Sub-Keys (Stations-
        # vs SNR-Scoring). Hardware-Gain ist identisch — wir nehmen die
        # "standard"-Auswertung (Stations-Scoring, immer verfuegbar).
        # P80 R1-F3 ORANGE: bei Divergenz Log-Warnung fuer Field-Test-
        # Diagnose.
        has_dual = (
            isinstance(r.get("standard"), dict) and isinstance(r.get("dx"), dict)
        )
        if has_dual:
            std_data = r["standard"]
            dx_data = r["dx"]
            if (std_data.get("ant1_gain") != dx_data.get("ant1_gain")
                    or std_data.get("ant2_gain") != dx_data.get("ant2_gain")):
                print(f"[P80] WARN Std/DX-Gain-Divergenz fuer {band}: "
                      f"std=({std_data.get('ant1_gain')}/{std_data.get('ant2_gain')}) "
                      f"dx=({dx_data.get('ant1_gain')}/{dx_data.get('ant2_gain')}) "
                      f"→ nehme std-Werte")
            save_data = std_data
        else:
            print("[P80] Dialog ohne Dual-Result — Fallback auf Top-Level")
            save_data = r

        ok = self._gain_store.save_gain(
            band,
            rxant=save_data.get("best_ant", "ANT1"),
            ant1_gain=save_data.get("ant1_gain", save_data.get("best_gain", 0)),
            ant2_gain=save_data.get("ant2_gain", save_data.get("best_gain", 0)),
            ant1_avg=save_data.get("ant1_avg", 0.0),
            ant2_avg=save_data.get("ant2_avg", 0.0),
            ant2_calibrated=True,  # DXTuneDialog misst immer beide
        )
        if not ok:
            print(f"[P80] WARN save_gain returnt False fuer {band}")

        ant1_g = save_data.get("ant1_gain", save_data.get("best_gain", 0))
        ant2_g = save_data.get("ant2_gain", save_data.get("best_gain", 0))
        # Gains sofort anwenden
        self._diversity_ant1_gain = ant1_g
        self._diversity_ant2_gain = ant2_g
        self._dx_tune_dialog = None
        self._set_gain_measure_lock(False)

        self._log_gain_result(r, band, ft_mode)

        # P83 (v0.97.54): dx_info via zentralen Helper aktualisieren —
        # zeigt frische Messung mit „noch 6h" Verfallszeit.
        self._update_gain_status_display()

        # Normal-Modus (KALIBRIEREN-Button): ANT1-Gain anwenden.
        # P80: keine separate save_normal_preset-Persistenz mehr — der
        # save_gain-Call oben hat ant1_gain (und ant2_gain) bereits im
        # unified Store gespeichert. Spaeterer Wechsel auf Diversity nutzt
        # die ANT2-Werte direkt.
        if self._rx_mode == "normal":
            if self.radio.ip:
                self.radio.set_rx_antenna("ANT1")
                self.radio.set_tx_antenna("ANT1")
                self.radio.set_rfgain(ant1_g)
            self._stats_warmup_cycles = 6
            print(f"[Kalibrieren] Normal {band}: G{ant1_g}dB — 4 Zyklen Warmup")
            self._update_statusbar()
            self._show_calibration_done(band, ant1_g, None)
            return

        # Diversity nach Gain-Messung starten/neu initialisieren (einmalig).
        # P34-Stufe2: nur noch _enable_diversity — Dynamic startet live.
        if self._rx_mode == "diversity" and self.radio.ip:
            if getattr(self, '_pending_dx_diversity', False):
                self._pending_dx_diversity = False
                scoring = getattr(self, '_pending_diversity_scoring',
                                  getattr(self._diversity_ctrl, 'scoring_mode', 'normal'))
                self._pending_diversity_scoring = None
            else:
                scoring = getattr(self._diversity_ctrl, 'scoring_mode', 'normal')
            print(f"[Diversity] Post-Gain → Diversity starten ({scoring})")
            self._enable_diversity(scoring_mode=scoring)
            self._stats_warmup_cycles = 6
            print(f"[Diversity] Kalibrierung fertig → 4 Zyklen Warmup")

        self._update_statusbar()
        self._show_calibration_done(band, ant1_g, ant2_g)

    def _show_calibration_done(self, band: str, ant1_g: int, ant2_g: int | None):
        """P79 (v0.97.51): Kalibrierungs-Ergebnis als Live-Log-Zeile.

        Mike-Wunsch Field-Test 18.05.: kalibrierung gespeichert als info
        text auch qso fenster, separates info fenster weg, spart sekunden
        fluessigeren ablauf. Vorher 3s-Popup-Dialog mit Top-Hint — brach
        Workflow.

        Doppelte Anzeige (QSO-Log + Statusbar 3s) deckt R1-F6 ab: wenn
        User im Logbuch-Tab ist oder die Zeile durch `_auto_trim_by_age`
        (5min-Window) bereits weg ist, sieht er das Echo in der Statusbar.
        Non-blocking, kein Klick noetig.

        Synergie mit qso_panel.add_info Auto-Detect (P79 Patch 1): das
        fuehrende Haken-Symbol wird in Hellgruen (#44FF44) gerendert.
        """
        if ant2_g is not None:
            text = (f"✓ Kalibrierung {band} gespeichert. "
                    f"ANT1: {ant1_g} dB | ANT2: {ant2_g} dB")
        else:
            text = f"✓ Kalibrierung {band} gespeichert. ANT1: {ant1_g} dB"
        self.qso_panel.add_info(text)
        # R1-F6: Statusbar-Echo 3s — tab-uebergreifend sichtbar.
        try:
            self.statusBar().showMessage(text, 3000)
        except Exception:
            pass  # Statusbar evtl. nicht verfuegbar (Tests/Smoke)

    def _on_dx_tune_rejected(self):
        """DX Tuning abgebrochen — P1.CACHE-SIMPLE: Stale-Acceptance.

        Bei Cancel mit alten Werten weiterarbeiten (Risiko-Akzeptanz).
        Wenn alte Werte vorhanden: still laden ohne Neu-Messung — kein
        Endlos-Pipeline-Restart. Wenn nichts da: Diversity deaktivieren.
        """
        import time as _time
        self._dx_tune_dialog = None
        self._set_gain_measure_lock(False)
        # v0.94: Pending-Flags bei Cancel zuruecksetzen.
        self._pending_dx_diversity = False
        self._pending_diversity_scoring = None

        # Sicherheit: TX/Encoder definitiv stoppen
        if self.encoder.is_transmitting:
            self.encoder.abort()
        if self.radio.ip:
            self.radio.ptt_off()

        # P34-Stufe2: Cancel-Pfad — wenn Diversity aktiv bleiben soll,
        # starten wir live mit 50:50; Dynamic übernimmt nach ~75 s. Wenn
        # kein Gain-Eintrag vorhanden: Diversity deaktivieren.
        if self._rx_mode == "diversity" and self.radio.ip:
            scoring = getattr(self._diversity_ctrl, 'scoring_mode', 'normal')
            band = self.settings.band
            entry = self._gain_store.get(band)
            # P80 R1-F4 ORANGE: stale-Acceptance braucht ant2_calibrated=True.
            # ant2_calibrated=False (Migration aus normal_preset) → kein
            # Diversity-Resume, sonst startet's mit ant2_gain=0 (Hardware-
            # Fehlanwendung).
            if (entry is not None
                    and "gain_timestamp" in entry
                    and entry.get("ant2_calibrated") is True):
                print(f"[Diversity] Cancel → Stale-Acceptance: Gain bleibt, "
                      f"Dynamic startet live")
                self._enable_diversity(scoring_mode=scoring)
                self._stats_warmup_cycles = 6
            else:
                # Keine Diversity-Werte vorhanden → Diversity deaktivieren
                print(f"[Diversity] Cancel ohne ANT2-Kalibrierung → Diversity AUS")
                self._disable_diversity()
                self.control_panel.set_rx_mode("normal")
                self._stats_warmup_cycles = 6
        else:
            self._apply_normal_mode()
            self._stats_warmup_cycles = 6
        # P83 (v0.97.54): zentraler Helper.
        self._update_gain_status_display()
        self._update_statusbar()

    def _apply_dx_preset(self, preset: dict):
        """DX-Preset am Radio anwenden."""
        rxant = preset.get("rxant", "ANT1")
        gain = preset.get("gain", preset.get("ant1_gain", 10))
        self.radio.set_rx_antenna(rxant)
        self.radio.set_rfgain(gain)
        self.radio.set_tx_antenna("ANT1")
        # P83: zentraler Helper (statt manueller Text).
        self._update_gain_status_display()
        print(f"[DX] Preset geladen: {rxant}, Gain {gain}")

    def _apply_dx_preset_for_band(self, band: str):
        """DX-Preset fuer ein bestimmtes Band laden (P80: unified store)."""
        preset = self._gain_store.get(band)
        if preset:
            self._apply_dx_preset(preset)
        else:
            # P83: zentraler Helper zeigt „nicht kalibriert".
            self._update_gain_status_display()

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
        # P80 (v0.97.52): Normal-Gain aus unified _gain_store.
        # R1-F2 ROT: `is not None`-Check statt falsy — ant1_gain=0 ist
        # ein gueltiger Wert (wenn auch unwahrscheinlich).
        entry = self._gain_store.get(band)
        if entry is not None and entry.get("ant1_gain") is not None:
            gain = int(entry["ant1_gain"])
            measured_str = entry.get("measured", "")
        else:
            gain = PREAMP_PRESETS.get(band, 10)
            measured_str = ""

        # P83 (v0.97.54): dx_info-Anzeige ueber zentralen Helper —
        # zeigt jetzt im Normal-Mode `ANT1(G10) · noch Xh` mit
        # Verfalls-Counter + Farbcodierung statt alter „G10dB (kalibriert)".
        age_days = None
        if measured_str:
            import datetime
            try:
                measured_dt = datetime.datetime.strptime(measured_str, "%Y-%m-%d %H:%M")
                age_days = (datetime.datetime.now() - measured_dt).days
            except Exception:
                age_days = None
        self._update_gain_status_display()

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

        # Mode-Coupling Buttons aktualisieren (rx_mode jetzt sauber gesetzt)
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
            "Wechsle dazu kurz in DIVERSITY und klicke KALIBRIEREN."
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
