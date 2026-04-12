"""SimpleFT8 MainWindow — QSO-Steuerung, CQ, Station-Klick Mixin."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import Slot

if TYPE_CHECKING:
    from .main_window import MainWindow

from core.qso_state import QSOState
from core.message import FT8Message


class QSOMixin:
    """Mixin fuer QSO-Logik — wird in MainWindow eingemischt.

    Enthaelt: Station anklicken, CQ, QSO-State Callbacks, QRZ Upload.
    """

    @Slot(object)
    def _on_station_clicked(self, msg: FT8Message):
        """User hat eine Station in der Empfangsliste angeklickt."""
        if self.encoder.is_transmitting:
            print(f"[QSO] TX aktiv — Klick ignoriert, warte auf TX-Ende")
            return
        # CQ-Modus beenden wenn aktiv
        if self.qso_sm.cq_mode:
            self.qso_sm.stop_cq()
            self.control_panel.set_cq_active(False)
        self._active_qso_targets.add(msg.caller)  # 150s Aging fuer angerufene Station
        self.rx_panel.set_active_call(msg.caller)  # Zeile im RX-Panel hervorheben
        self.qso_panel.add_info(f"Rufe {msg.caller}...")
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

    def _on_country_filter_changed(self, country_filter: list):
        """Länder-Filter in Settings speichern."""
        self.settings.set("country_filter", country_filter)
        self.settings.save()

    @Slot()
    def _on_cq_clicked(self):
        if self.control_panel.btn_cq.isChecked():
            # CQ: immer auf festem Slot senden (aktueller Gegenteil-Slot)
            # So antworten Stationen konsistent im anderen Slot
            self.encoder.tx_even = not self.timer.is_even_cycle()
            slot = "EVEN" if self.encoder.tx_even else "ODD"
            print(f"[CQ] Fester TX-Slot: {slot}")
            self.qso_panel.add_info("CQ-Modus gestartet")
            self.qso_sm.start_cq()
        else:
            count = self.qso_sm.cq_qso_count
            self.qso_panel.add_info(f"CQ-Modus gestoppt ({count} QSOs)")
            self.qso_sm.stop_cq()
            self.control_panel.update_qso_counter(0)

    @Slot()
    def _on_advance(self):
        self.qso_sm.advance()

    @Slot()
    def _on_cancel(self):
        """HALT — stoppt ALLES: CQ, QSO, TX, Messung."""
        self._active_qso_targets.clear()
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
        self.control_panel.btn_advance.setEnabled(
            state in (QSOState.WAIT_REPORT, QSOState.WAIT_RR73)
            and not self.qso_sm.cq_mode
        )
        self.control_panel.btn_cancel.setEnabled(
            in_qso or state in (QSOState.CQ_CALLING, QSOState.CQ_WAIT)
        )

        is_tx = state in (
            QSOState.TX_CALL, QSOState.TX_REPORT,
            QSOState.TX_RR73, QSOState.CQ_CALLING,
        )
        self.control_panel.set_tx_active(is_tx)

        if self.qso_sm.cq_mode:
            self.control_panel.update_qso_counter(self.qso_sm.cq_qso_count)
            # CQ-Button aktiv halten wenn CQ-Modus laeuft (auch nach QSO-Resume)
            if state in (QSOState.CQ_CALLING, QSOState.CQ_WAIT):
                self.control_panel.set_cq_active(True)

    def _on_tx_finished(self):
        """TX abgeschlossen — PTT aus, zurueck zu RX."""
        self.control_panel.set_tx_active(False)
        self.qso_sm.on_message_sent()

    @Slot(str)
    def _on_send_message(self, message: str):
        """FT8-Nachricht encoden und ueber FlexRadio senden."""
        if message.startswith("CQ "):
            self._has_sent_cq = True
            # OMNI-TX: CQ-Slot überspringen wenn Muster es vorgibt.
            # QSO-Schutz: nur CQ-Nachrichten unterdrücken — QSO-Nachrichten IMMER senden!
            if self._omni_tx.active and not self._omni_tx.should_tx():
                print(f"[OMNI-TX] Skip CQ (Slot: {self._omni_tx.slot_label})")
                return
        self.encoder.transmit(message)  # add_tx() wird via tx_started Signal aufgerufen

    @Slot(object)
    def _on_qso_complete(self, qso_data):
        """RR73 gesendet — ADIF schreiben. ✓ erst bei _on_qso_confirmed."""
        self._active_qso_targets.discard(qso_data.their_call)
        self.rx_panel.set_active_call("")

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

    @Slot(object)
    def _on_qso_confirmed(self, qso_data):
        """73 empfangen — QSO wirklich komplett, ✓ anzeigen."""
        self.qso_panel.add_qso_complete(qso_data.their_call)
        # Logbuch aktualisieren (neues QSO wurde in ADIF geschrieben)
        self.qso_panel.logbook.refresh()

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
        """Einzelnes QSO an QRZ.com hochladen (non-blocking)."""
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
        """Alle QSOs an QRZ.com hochladen (non-blocking)."""
        api_key = self.settings.get("qrz_api_key", "")
        if not api_key:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "QRZ.com",
                "Kein QRZ API Key konfiguriert.\n"
                "Bitte in ~/.simpleft8/config.json eintragen:\n"
                '"qrz_api_key": "XXXX-XXXX-XXXX-XXXX"')
            return

        records = self.qso_panel.logbook._all_records
        if not records:
            self.statusBar().showMessage("Keine QSOs zum Hochladen.", 5000)
            return

        from concurrent.futures import ThreadPoolExecutor
        if not hasattr(self, '_qrz_pool'):
            self._qrz_pool = ThreadPoolExecutor(max_workers=1)
        client = self._get_qrz_client()
        self.statusBar().showMessage(f"QRZ Upload: {len(records)} QSOs...", 30000)

        def _do_bulk():
            ok, fail, dup = 0, 0, 0
            for rec in records:
                result = client.upload_qso_from_dict(rec)
                s = result.get("RESULT", "FAIL")
                if s == "OK": ok += 1
                elif "duplicate" in result.get("REASON", "").lower(): dup += 1
                else: fail += 1
            return f"QRZ Upload: {ok} neu, {dup} Duplikate, {fail} Fehler"

        future = self._qrz_pool.submit(_do_bulk)
        future.add_done_callback(
            lambda f: self.statusBar().showMessage(f.result(), 10000)
            if not f.exception() else None
        )
        print(f"[QRZ] Upload gestartet ({len(records)} QSOs)")

    @Slot(str)
    def _on_qso_timeout(self, their_call: str):
        self._active_qso_targets.discard(their_call)
        self.rx_panel.set_active_call("")
        self.qso_panel.add_timeout(their_call)
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
        """CQ-Reply empfangen: Encoder-Slot auf Gegentakt der Station setzen."""
        their_even = getattr(msg, '_tx_even', None)
        if their_even is not None:
            self.encoder.tx_even = not their_even
            slot_str = "ODD" if their_even else "EVEN"
            print(f"[TX] CQ-Reply {msg.caller}: sie={('EVEN' if their_even else 'ODD')} → wir={slot_str}")
