"""SimpleFT8 MainWindow — QSO-Steuerung, CQ, Station-Klick Mixin."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, Slot

if TYPE_CHECKING:
    from .main_window import MainWindow

from core.qso_state import QSOState
from core.message import FT8Message


class QSOMixin:
    """Mixin fuer QSO-Logik — wird in MainWindow eingemischt.

    Enthaelt: Station anklicken, CQ, QSO-State Callbacks, QRZ Upload.
    """

    def _antenna_pref_label(self, call: str) -> str:
        """Vereinheitlichtes Format fuer alle Anzeigen:
          - Normal-Modus oder ANT1 als beste Antenne → ' (ANT1)'
          - Diversity + ANT2 ist Hysterese-Schwelle besser → ' (ANT2 ↑X.X dB)'
        Pfeil ↑ = Diversity bringt messbaren Gewinn.
        """
        if self._rx_mode == "normal":
            return " (ANT1)"
        if not hasattr(self, '_antenna_prefs'):
            return ""
        pref = self._antenna_prefs.get_pref(call)
        if not pref:
            return ""
        if pref["best_ant"] == "A1":
            return " (ANT1)"
        # ANT2 wurde gewaehlt → Hysterese-Schwelle ueberschritten = echter Gewinn
        delta = pref.get("delta_db")
        if delta is None:
            return " (ANT2)"
        return f" (ANT2 ↑{abs(delta):.1f} dB)"

    @Slot(str, bool, float)
    def _on_tx_started(self, message: str, tx_even: bool, slot_start_ts: float):
        """TX begonnen — Nachricht mit einheitlichem Antennen-Label ins QSO-Panel.

        Verwendet `_antenna_pref_label` damit Format identisch zu Rufe...-Eintrag
        und Statusbar ist (verhindert Verwirrung wie z.B. 'ANT1 Δ1.0dB').

        tx_even/slot_start_ts vom Encoder durchgereicht — qso_panel zeigt
        damit den korrekten Slot-Tag/Zeitstempel der TX-Aktion.
        """
        ant_label = ""
        if not message.startswith("CQ "):
            if hasattr(self, 'qso_sm') and self.qso_sm.qso:
                call = self.qso_sm.qso.their_call
                if call:
                    # _antenna_pref_label liefert " (ANT...)" → fuehrendes Leerzeichen
                    # entfernen, qso_panel.add_tx setzt eigene Trennspaces.
                    ant_label = self._antenna_pref_label(call).lstrip()
        self.qso_panel.add_tx(message, ant_label,
                              tx_even=tx_even, slot_start_ts=slot_start_ts)

    @Slot(object)
    def _on_station_clicked(self, msg: FT8Message):
        """User hat eine Station in der Empfangsliste angeklickt."""
        if self.encoder.is_transmitting:
            # P1.24: Klick waehrend TX wird gebuffert + sofort State-Cleanup
            # (CQ stoppen ODER laufendes Hunt-QSO abbrechen). Aktueller TX-
            # Audio-Slot laeuft durch (kann nicht ohne RF-Click abgebrochen
            # werden), aber im naechsten Slot wird die Station angerufen.
            # Vorher: silent skip → Mike's CQ lief weiter, Klick verpufft.
            print(f"[QSO] TX aktiv — Klick {msg.caller} gebuffert "
                  f"(state={self.qso_sm.state.name})")
            if self.qso_sm.cq_mode:
                self.qso_sm.stop_cq()
                self.control_panel.set_cq_active(False)
            elif self.qso_sm.state not in (QSOState.IDLE, QSOState.TIMEOUT,
                                            QSOState.CQ_CALLING,
                                            QSOState.CQ_WAIT):
                # Hunt-QSO laeuft → abbrechen damit on_message_sent nicht
                # in WAIT_REPORT/RR73 wechselt
                self.qso_sm.cancel()
            self._pending_station_click = msg
            self.statusBar().showMessage(
                f"TX läuft — {msg.caller} wird im nächsten Slot gerufen",
                3000)
            return
        if getattr(self, '_diversity_measuring', False):
            print(f"[QSO] Einmessen aktiv — Hunt blockiert")
            return
        # CQ-Modus beenden wenn aktiv — _was_cq VOR stop_cq() sichern!
        # stop_cq() setzt cq_mode=False; start_qso() würde dann _was_cq=False speichern
        # → _resume_cq_if_needed() würde CQ nach QSO NICHT wiederaufnehmen (Bug)
        _cq_was_active = self.qso_sm.cq_mode
        if _cq_was_active:
            self.qso_sm.stop_cq()
            self.control_panel.set_cq_active(False)
        # Auto-Hunt pausieren bei manuellem Klick
        if self._auto_hunt.active:
            self._auto_hunt.on_manual_qso_start()
        # P1.14 KP3: alte their_call aus _active_qso_targets entfernen
        # (sonst Set-Bloat bei haeufigen Wechseln)
        old_call = self.qso_sm.qso.their_call if self.qso_sm.qso else None
        if old_call:
            self._active_qso_targets.discard(old_call)
        self._active_qso_targets.add(msg.caller)  # 150s Aging fuer angerufene Station
        self.rx_panel.set_active_call(msg.caller)  # Zeile im RX-Panel hervorheben
        # P1.14 KP2: wenn Station bereits in Caller-Queue gewartet hat, aus
        # Queue entfernen damit sie nicht doppelt kontaktiert wird (sonst
        # Doppel-QSO-Risiko nach Resume)
        if any(m.caller == msg.caller for m in self.qso_sm._caller_queue):
            self.qso_sm._caller_queue = [
                m for m in self.qso_sm._caller_queue
                if m.caller != msg.caller
            ]
            self.qso_sm.queue_changed.emit(
                [m.caller for m in self.qso_sm._caller_queue])
        self.qso_panel.add_info(f"Rufe {msg.caller}...{self._antenna_pref_label(msg.caller)}")
        self.qso_sm.max_calls = self.settings.get("max_calls", 3)
        # Even/Odd: sende im GEGENTEILIGEN Slot der Gegenstation
        their_even = getattr(msg, '_tx_even', None)
        if their_even is not None:
            self.encoder.tx_even = not their_even
            print(f"[TX] Slot: Gegenstation={'EVEN' if their_even else 'ODD'} → wir={'ODD' if their_even else 'EVEN'}")
        else:
            self.encoder.tx_even = None  # Fallback: nächster Slot
        self.qso_sm.start_qso(
            their_call=msg.caller,
            their_grid=msg.grid_or_report if msg.is_grid else "",
            freq_hz=msg.freq_hz,
        )
        # P1.14 KP6 (Plan-V2-Entscheidung): Workaround BEHALTEN. Saubere
        # Integration in start_qso ist nicht moeglich weil stop_cq() vor
        # start_qso() laufen MUSS — _was_cq waere dort schon False.
        if _cq_was_active:
            self.qso_sm._was_cq = True

    def _on_country_filter_changed(self, country_filter: list):
        """Länder-Filter in Settings speichern."""
        self.settings.set("country_filter", country_filter)
        self.settings.save()

    @Slot()
    def _on_cq_clicked(self):
        if self.control_panel.btn_cq.isChecked():
            # Laufendes Hunt-QSO abbrechen bevor CQ startet!
            if self.qso_sm.state not in (QSOState.IDLE, QSOState.TIMEOUT,
                                          QSOState.CQ_CALLING, QSOState.CQ_WAIT):
                self.qso_sm.cancel()
                self._active_qso_targets.clear()
                self.rx_panel.set_active_call("")
                print("[CQ] Hunt-QSO abgebrochen → CQ starten")
            # CQ-Frequenz: nur Diversity nutzt Auto-Suche; Normal-Modus = WSJT-X-Standard,
            # User waehlt manuell ueber Klick/Spinbox (encoder.audio_freq_hz schon gesetzt).
            if self._rx_mode == "diversity":
                cq_freq = self._diversity_ctrl.get_free_cq_freq()
                if cq_freq and cq_freq != self.encoder.audio_freq_hz:
                    self.encoder.audio_freq_hz = cq_freq
                    print(f"[CQ] TX-Frequenz auf {cq_freq} Hz (aus Auto-Suche)")
                    self.control_panel.update_freq_histogram(
                        self._diversity_ctrl.get_histogram_data())
            else:
                print(f"[CQ] Normal-Modus → manuelle TX-Frequenz {self.encoder.audio_freq_hz} Hz")
            # CQ: immer auf festem Slot senden (aktueller Gegenteil-Slot)
            self.encoder.tx_even = not self.timer.is_even_cycle()
            slot = "EVEN" if self.encoder.tx_even else "ODD"
            print(f"[CQ] Fester TX-Slot: {slot}")
            self.qso_panel.add_info("CQ-Modus gestartet")
            self.qso_sm.start_cq()
        else:
            count = self.qso_sm.cq_qso_count
            self.qso_panel.add_info(f"CQ-Modus gestoppt ({count} QSOs)")
            self.qso_panel._cq_count = 0
            self.qso_panel.status_label.setText(f"{count} QSO(s)")
            self.qso_panel.status_label.setStyleSheet("color: #666; font-size: 11px; padding: 2px;")
            self.qso_sm.stop_cq()
            self.control_panel.update_qso_counter(0)

    @Slot()
    def _on_advance(self):
        self.qso_sm.advance()

    @Slot()
    def _on_cancel(self):
        """HALT — stoppt ALLES: CQ, QSO, TX, Messung."""
        self._active_qso_targets.clear()
        self._pending_station_click = None  # P1.24: gepufferten Klick verwerfen
        self.rx_panel.set_active_call("")
        # TX sofort stoppen
        if self.encoder.is_transmitting:
            self.encoder.abort()
            if self.radio.ip:
                self.radio.ptt_off()
        # CQ + QSO stoppen
        self.qso_sm.stop_cq()
        self.qso_sm.cancel()
        self.control_panel.set_cq_active(False)
        # P1.14 W6: Auto-Hunt freigeben (sonst dauerhaft pausiert nach HALT)
        if self._auto_hunt.active:
            self._auto_hunt.on_manual_qso_end()
        self.qso_panel.add_info("HALT — alles gestoppt")
        self.statusBar().showMessage("HALT — CQ, QSO, TX gestoppt", 5000)
        print("[HALT] Alles gestoppt")

    @Slot(object)
    def _on_state_changed(self, state: QSOState):
        name = state.name
        self.control_panel.update_state(name)
        # AP-Prioritaet: aktiver QSO-Partner bekommt hoechste AP-Hint-Prioritaet
        if state not in (QSOState.IDLE, QSOState.TIMEOUT):
            self.decoder.priority_call = (
                self.qso_sm.qso.their_call if self.qso_sm.qso else ""
            )
        else:
            self.decoder.priority_call = ""

        # OMNI-TX: Bei QSO-Start Zähler zurücksetzen (Block beibehalten)
        if state == QSOState.TX_CALL:
            self._omni_tx.on_qso_started()

        # AP-Lite: Buffer löschen wenn QSO endet oder neu startet
        if state in (QSOState.IDLE, QSOState.TIMEOUT, QSOState.TX_CALL):
            self._ap_lite.clear()

        in_qso = state not in (
            QSOState.IDLE, QSOState.TIMEOUT,
            QSOState.CQ_CALLING, QSOState.CQ_WAIT,
        )
        # P1.FORCESEND (v0.95.12): Label dynamisch + WAIT_73 in Enabled-Liste
        # + Diversity-Lock zusätzlich prüfen (R1-Empfehlung Defense-in-Depth).
        diversity_locked = getattr(self, "_diversity_measuring", False)
        self.control_panel.set_advance_label(state)
        self.control_panel.btn_advance.setEnabled(
            state in (QSOState.WAIT_REPORT, QSOState.WAIT_RR73, QSOState.WAIT_73)
            and not self.qso_sm.cq_mode
            and not diversity_locked
        )
        self.control_panel.btn_cancel.setEnabled(
            in_qso or state in (QSOState.CQ_CALLING, QSOState.CQ_WAIT)
        )

        is_tx = state in (
            QSOState.TX_CALL, QSOState.TX_REPORT,
            QSOState.TX_RR73, QSOState.TX_73_COURTESY,
            QSOState.CQ_CALLING,
        )
        self.control_panel.set_tx_active(is_tx)

        if self.qso_sm.cq_mode:
            self.control_panel.update_qso_counter(self.qso_sm.cq_qso_count)
            # CQ-Button immer aktiv wenn cq_mode=True — auch während QSO-Sequenz
            self.control_panel.set_cq_active(True)

    def _on_tx_finished(self):
        """TX abgeschlossen — PTT aus, zurueck zu RX."""
        self.control_panel.set_tx_active(False)
        self.qso_sm.on_message_sent()
        # P1.24: gepufferter Station-Klick aus TX-Phase jetzt nachholen
        # (is_transmitting ist hier False, state-Cleanup ist im
        # _on_station_clicked-TX-Pfad bereits passiert)
        if self._pending_station_click is not None:
            buffered = self._pending_station_click
            self._pending_station_click = None
            print(f"[QSO] TX fertig — Buffered Klick {buffered.caller} jetzt anrufen")
            self._on_station_clicked(buffered)

    @Slot(str)
    def _on_send_message(self, message: str):
        """FT8-Nachricht encoden und ueber FlexRadio senden."""
        # Operator Presence Check (Totmannschalter, gesetzl. Pflicht DE)
        # Laufende QSOs werden IMMER zu Ende gefuehrt!
        if not self.presence_can_tx():
            print(f"[Presence] TX blockiert (Operator abwesend): '{message}'")
            return
        if message.startswith("CQ "):
            self._has_sent_cq = True
            # OMNI-TX: CQ-Slot-Steuerung mit Even/Odd Paritaet
            if self._omni_tx.active:
                is_even = self.timer.is_even_cycle()
                send_ok, target_even = self._omni_tx.should_tx()
                if not send_ok:
                    # RX-Slot: CQ NICHT senden, aber QSO SM NICHT als Fehlversuch zaehlen
                    print(f"[OMNI-TX] RX-Slot → skip CQ ({self._omni_tx.slot_label})")
                    if hasattr(self.qso_sm, 'qso') and hasattr(self.qso_sm.qso, 'calls_made'):
                        self.qso_sm.qso.calls_made = max(0, self.qso_sm.qso.calls_made - 1)
                    return
                # TX-Slot: Encoder auf richtige Paritaet setzen
                if target_even is not None:
                    self.encoder.tx_even = target_even
                    parity_str = "Even" if target_even else "Odd"
                    print(f"[OMNI-TX] TX auf {parity_str} ({self._omni_tx.slot_label})")
                # Even/Odd Zaehler
                actual_even = target_even if target_even is not None else is_even
                if actual_even:
                    self._omni_tx.cq_even_count += 1
                else:
                    self._omni_tx.cq_odd_count += 1
        print(f"[TX] → '{message}' auf {self.encoder.audio_freq_hz} Hz")
        # v0.80 Fix A2: wenn bereits ein TX gescheduled ist (z.B. alter
        # Retry-TX im Sleep), erst abbrechen. Sonst werden zwei TX-Worker
        # parallel laufen und der alte sendet eine veraltete Message
        # nachdem der State sich geaendert hat.
        if self.encoder.is_transmitting:
            self.encoder.abort()
        self.encoder.transmit(message)  # add_tx() wird via tx_started Signal aufgerufen

    @Slot(object)
    def _on_qso_complete(self, qso_data):
        """RR73 gesendet — ADIF schreiben (UI-Meldung kommt erst bei 73 oder Timeout)."""
        self._active_qso_targets.discard(qso_data.their_call)
        self.rx_panel.set_active_call("")
        # Auto-Hunt: QSO erfolgreich → Pause, dann naechste Station
        if self._auto_hunt.active:
            self._auto_hunt.on_qso_complete(qso_data.their_call)

        # KEIN add_qso_complete hier — kommt in _on_qso_confirmed (nach 73 oder Timeout)

        band = self.settings.band.upper()
        freq = self.settings.frequency_mhz

        self.adif.log_qso(
            call=qso_data.their_call,
            band=band,
            freq_mhz=freq,
            mode=self.settings.mode,
            rst_sent=qso_data.our_snr or "-10",
            rst_rcvd=qso_data.their_snr or "-10",
            gridsquare=qso_data.their_grid or "",
            my_gridsquare=self.settings.locator,
            my_callsign=self.settings.callsign,
            tx_power=self.settings.power_watts,
            time_on=qso_data.start_time,
        )
        self.qso_log.add_qso(qso_data.their_call, band)

        # Antennen-Statistik pro QSO loggen — immer schreiben, "–" wenn kein Pref
        if hasattr(self, '_stats_logger') and self._stats_logger is not None:
            pref = None
            if self._rx_mode == "diversity" and hasattr(self, '_antenna_prefs'):
                pref = self._antenna_prefs.get_pref(qso_data.their_call)
            self._stats_logger.log_antenna_qso(
                call=qso_data.their_call,
                band=self.settings.band,
                ft_mode=self.settings.mode,
                best_ant=pref["best_ant"] if pref else None,
                delta_db=pref["delta_db"] if pref else None,
            )

    @Slot(object)
    def _on_qso_confirmed(self, qso_data):
        """73 empfangen — QSO wirklich komplett, ✓ anzeigen."""
        self.qso_panel.add_qso_complete(qso_data.their_call)
        # Logbuch aktualisieren (neues QSO wurde in ADIF geschrieben)
        self.qso_panel.logbook.refresh()
        # P1.14 W6: Auto-Hunt nach erfolgreichem manuellem QSO freigeben
        if self._auto_hunt.active:
            self._auto_hunt.on_manual_qso_end()
        # CQ-Modus läuft weiter — visuell bestätigen
        if self.qso_sm.cq_mode:
            self.control_panel.set_cq_active(True)
            self.qso_panel.add_info("CQ-Modus läuft weiter...")

    def _get_qrz_client(self):
        """QRZ Client lazy initialisieren."""
        if self._qrz_client is None:
            from log.qrz import QRZClient
            self._qrz_client = QRZClient(
                api_key=self.settings.get("qrz_api_key", ""),
                username=self.settings.get("qrz_username", ""),
                password=self.settings.get("qrz_password", ""),
            )
        return self._qrz_client

    def _on_logbook_qso_clicked(self, record: dict):
        """Logbuch-Eintrag angeklickt → Detail Overlay zeigen + QRZ Lookup (non-blocking)."""
        self._detail_overlay.load_qso(record)
        self._right_stack.setCurrentIndex(1)

        # QRZ Lookup in Background Thread (blockiert nicht die GUI)
        call = record.get("CALL", "")
        if call:
            from concurrent.futures import ThreadPoolExecutor
            if not hasattr(self, '_qrz_pool'):
                self._qrz_pool = ThreadPoolExecutor(max_workers=1)
            client = self._get_qrz_client()
            if client.username:
                future = self._qrz_pool.submit(client.lookup_callsign, call)
                future.add_done_callback(
                    lambda f: self._detail_overlay.set_qrz_info(f.result())
                    if not f.exception() else None
                )
            else:
                self._detail_overlay.qrz_status.setText("QRZ: kein Login konfiguriert")

    def _qrz_upload_single(self, record: dict):
        """Einzelnes QSO an QRZ.com hochladen (non-blocking).

        P1.QRZ-UPLOAD-UI v0.95.14 (R1-KP-1): Bei aktivem Bulk-Upload
        skippen — sonst Race im geteilten ThreadPool.
        """
        if getattr(self, '_qrz_bulk_active', False):
            call = record.get("CALL", "?")
            print(f"[QRZ] Auto-Upload {call} uebersprungen — Bulk-Upload laeuft")
            return

        from concurrent.futures import ThreadPoolExecutor
        if not hasattr(self, '_qrz_pool'):
            self._qrz_pool = ThreadPoolExecutor(max_workers=1)
        client = self._get_qrz_client()

        def _do_upload():
            result = client.upload_qso_from_dict(record)
            status = result.get("RESULT", "FAIL")
            call = record.get("CALL", "?")
            if status == "OK":
                return f"QRZ Upload OK: {call}"
            return f"QRZ Fehler: {result.get('REASON', 'unbekannt')}"

        future = self._qrz_pool.submit(_do_upload)
        future.add_done_callback(
            lambda f: self.statusBar().showMessage(f.result(), 5000)
            if not f.exception() else None
        )

    def _on_qrz_upload(self):
        """QRZ Bulk-Upload mit Confirm-Dialog + Progress-Dialog.

        P1.QRZ-UPLOAD-UI v0.95.14: Phase 1 Confirm → Phase 2 Progress (non-modal).
        Klick-Sperre 3-fach (R1-KP-2): Flag → Button → submit-Reihenfolge.
        """
        from PySide6.QtWidgets import QDialog

        # KP-2: Re-Entry-Check als FIRST line (defensive)
        if getattr(self, '_qrz_bulk_active', False):
            print("[QRZ] Re-Entry-Schutz: Bulk laeuft schon, Klick ignoriert")
            return

        api_key = self.settings.get("qrz_api_key", "")
        if not api_key:
            from ui.qrz_upload_dialogs import _DLG_STYLE
            from PySide6.QtWidgets import QVBoxLayout, QLabel, QPushButton
            dlg = QDialog(self)
            dlg.setWindowTitle("QRZ.com")
            dlg.setStyleSheet(_DLG_STYLE)
            lay = QVBoxLayout(dlg)
            lay.setContentsMargins(24, 20, 24, 16)
            lbl = QLabel(
                "Kein QRZ API Key konfiguriert.\n\n"
                "Bitte in ~/.simpleft8/config.json eintragen:\n"
                '"qrz_api_key": "XXXX-XXXX-XXXX-XXXX"'
            )
            lay.addWidget(lbl)
            btn = QPushButton("OK")
            btn.setObjectName("btn_primary")
            btn.clicked.connect(dlg.accept)
            lay.addWidget(btn)
            dlg.exec()
            return

        records = self.qso_panel.logbook._all_records
        if not records:
            self.statusBar().showMessage("Keine QSOs zum Hochladen.", 5000)
            return

        from ui.qrz_upload_dialogs import QRZConfirmDialog, QRZUploadDialog
        confirm = QRZConfirmDialog(len(records), parent=self)
        if confirm.exec() != QDialog.DialogCode.Accepted:
            return

        # KP-2 Reihenfolge: 1) Flag → 2) Button → 3) Worker starten
        self._qrz_bulk_active = True
        self._set_qrz_button_enabled(False)

        self._qrz_dialog = QRZUploadDialog(len(records), parent=self)
        self._qrz_dialog.setWindowFlag(Qt.WindowType.Window, True)

        from core.qrz_upload_worker import QRZUploadWorker
        client = self._get_qrz_client()
        self._qrz_worker = QRZUploadWorker(client, records, parent=self)
        self._qrz_worker.progress.connect(
            self._qrz_dialog.update_progress, Qt.ConnectionType.QueuedConnection)
        self._qrz_worker.finished.connect(
            self._on_qrz_bulk_finished, Qt.ConnectionType.QueuedConnection)
        self._qrz_dialog.cancel_clicked.connect(self._qrz_worker.cancel)
        self._qrz_dialog.show()
        self._qrz_dialog.raise_()
        self._qrz_dialog.activateWindow()

        self._qrz_worker.start()
        print(f"[QRZ] Bulk-Upload gestartet ({len(records)} QSOs)")

    @Slot(int, int, int, bool, int)
    def _on_qrz_bulk_finished(self, ok: int, dup: int, fail: int,
                              cancelled: bool, total_processed: int) -> None:
        """Worker-Finish — Dialog updaten, Flag/Button reset."""
        if hasattr(self, '_qrz_dialog') and self._qrz_dialog:
            self._qrz_dialog.set_finished(ok, dup, fail, cancelled, total_processed)
        self._qrz_bulk_active = False
        self._set_qrz_button_enabled(True)
        if hasattr(self, '_qrz_worker') and self._qrz_worker:
            self._qrz_worker.shutdown(wait=False)
        # Logbuch refreshen damit neue QSOs (falls vorher per Auto-Upload geadded)
        # auch sichtbar sind (kosmetisch — Bulk lädt bestehende QSOs hoch).
        self.qso_panel.logbook.refresh()
        print(f"[QRZ] Bulk-Upload beendet: {ok} neu, {dup} dup, {fail} fail "
              f"(cancelled={cancelled})")

    def _set_qrz_button_enabled(self, enabled: bool) -> None:
        """Logbook-QRZ-Button enable/disable — Single-Instance-Schutz (R1-KP-2)."""
        try:
            self.qso_panel.logbook.set_qrz_button_enabled(enabled)
        except AttributeError:
            pass

    @Slot(str)
    def _on_qso_timeout(self, their_call: str):
        self._active_qso_targets.discard(their_call)
        self.rx_panel.set_active_call("")
        self.qso_panel.add_timeout(their_call)
        # Auto-Hunt: Timeout → Cooldown setzen, naechste Station
        if self._auto_hunt.active:
            self._auto_hunt.on_qso_timeout(their_call)
            # P1.14 W6: _manual_override zuruecksetzen (sonst pausiert
            # Auto-Hunt nach Klick → Timeout dauerhaft)
            self._auto_hunt.on_manual_qso_end()
        # CQ-Button aktiv halten wenn CQ-Modus laeuft
        if self.qso_sm.cq_mode:
            self.control_panel.set_cq_active(True)

    @Slot(list)
    def _on_caller_queue_changed(self, queue: list):
        """Warteliste geändert — im QSO-Panel anzeigen."""
        if queue:
            calls = ", ".join(queue)
            self.qso_panel.add_info(f"⏳ Warteliste: {calls}")
            self.control_panel.update_qso_counter(self.qso_sm.cq_qso_count)
        else:
            if self.qso_sm.cq_mode:
                self.qso_panel.add_info("Warteliste leer")

    @Slot(object)
    def _on_tx_slot_for_partner(self, msg):
        """CQ-Reply ODER Courtesy-73: Encoder-Slot auf Gegentakt der Station setzen.

        P1.10 (v0.95.4): wird jetzt auch fuer Courtesy-73 in WAIT_73 verwendet.
        State-abhaengig zwischen 'CQ-Reply' und 'Courtesy-73 Slot' unterscheiden.
        """
        their_even = getattr(msg, '_tx_even', None)
        is_courtesy = self.qso_sm.state == QSOState.TX_73_COURTESY
        if their_even is not None:
            self.encoder.tx_even = not their_even
            slot_str = "ODD" if their_even else "EVEN"
            kind = "Courtesy-73" if is_courtesy else "CQ-Reply"
            print(f"[TX] {kind} {msg.caller}: sie={('EVEN' if their_even else 'ODD')} → wir={slot_str}")
        # Antennen-Praeferenz-Panel-Info nur bei CQ-Reply, nicht bei Courtesy-73
        # (bei Courtesy-73 ist QSO bereits abgeschlossen — "Antworte..." waere irrefuehrend)
        if not is_courtesy:
            label = self._antenna_pref_label(msg.caller)
            if label:
                self.qso_panel.add_info(f"Antworte {msg.caller}{label}")

    @Slot(object)
    def _on_try_replace_pending_tx(self, msg):
        """P1.9 (v0.95.3): CQ-Reply waehrend CQ_CALLING → Encoder-Replace
        versuchen. Wenn erfolgreich: state direkt zu TX_REPORT, Encoder
        sendet Report im selben Slot statt erst nach CQ-Ende.
        Wenn zu spaet (Audio bereits gestartet): kein State-Wechsel,
        on_message_sent verarbeitet pending nach TX-Ende (Status quo).
        """
        import time as _time
        from core.qso_state import QSOData, QSOState

        # Nur Grid-Replies haben sofortigen Report (R+Report waere zu spaet
        # im QSO-Flow; das verarbeitet weiterhin _process_cq_reply nach TX).
        if not msg.is_grid:
            return

        # Report-Format identisch zu _process_cq_reply (qso_state.py:201)
        snr = self.qso_sm._last_snr
        report = f"{snr:+03d}" if snr > -30 else "-10"
        tx_msg = f"{msg.caller} {self.qso_sm.my_call} {report}"

        # V2 FINDING-D: tx_even MUSS vor request_replace gesetzt werden,
        # damit der Worker beim Wake _next_slot_boundary() mit korrektem
        # Wert aufruft. Race-Vermeidung.
        their_even = getattr(msg, '_tx_even', None)
        if their_even is not None:
            self.encoder.tx_even = not their_even

        if not self.encoder.request_replace(tx_msg):
            return  # zu spaet — Status quo Pfad uebernimmt

        # Replace eingereiht → State analog _process_cq_reply
        self.qso_sm._pending_reply = None
        self.qso_sm._was_cq = True  # V2 FINDING-A: CQ-Resume nach QSO
        self.qso_sm.qso = QSOData(
            their_call=msg.caller,
            their_grid=msg.grid_or_report if msg.is_grid else "",
            freq_hz=msg.freq_hz,
            start_time=_time.time(),
            our_snr=report,
        )
        # V2 FINDING-B: Debug-Log analog _process_cq_reply
        self.qso_sm._dbg.reset(msg.caller)
        self.qso_sm._dbg.log("RX", f"P1.9 Replace: CQ-Antwort von {msg.caller}: '{msg.raw}'")
        self.qso_sm._dbg.log("TX", f"Sende Report: '{tx_msg}' (SNR={snr})")
        self.qso_sm._set_state(QSOState.TX_REPORT)
        # V2 FINDING-C: QSO-Panel-Anzeige analog _on_tx_slot_for_partner
        label = self._antenna_pref_label(msg.caller)
        if label:
            self.qso_panel.add_info(f"Antworte {msg.caller}{label}")
        # ACHTUNG: KEIN send_message.emit — Encoder hat die Message bereits
        # ueber _replace_message bekommen.
        print(f"[QSO] P1.9 Replace OK: CQ → '{tx_msg}'")

    def _on_qso_tab_changed(self, index: int):
        """Tab-Wechsel im QSO-Panel: Detail-Overlay schliessen wenn nicht mehr im Logbuch."""
        if index == 0:  # QSO-Tab (nicht Logbuch)
            self._right_stack.setCurrentIndex(0)

    def _on_logbook_delete(self, record: dict):
        """QSO aus Logbuch loeschen (via Detail-Overlay Delete-Button)."""
        from log.adif import delete_qso
        call = record.get("CALL", "?")
        ok = delete_qso(record)
        if ok:
            print(f"[Logbuch] QSO mit {call} geloescht")
            self.qso_panel.logbook.refresh()
            self._right_stack.setCurrentIndex(0)  # Overlay schliessen
        else:
            print(f"[Logbuch] FEHLER: QSO mit {call} nicht gefunden zum Loeschen")
            self.statusBar().showMessage(f"Fehler: QSO {call} nicht geloescht", 5000)
