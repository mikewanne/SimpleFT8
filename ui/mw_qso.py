"""SimpleFT8 MainWindow — QSO-Steuerung, CQ, Station-Klick Mixin."""

from __future__ import annotations

import time
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, Slot

if TYPE_CHECKING:
    from .main_window import MainWindow

from core.qso_state import QSOState
from core.message import FT8Message


# P1.7 (v0.95.19): ADIF-Duplikat-Filter Zeit-Fenster (Sekunden).
# Mike's Spec 2026-05-05: < 5 Min nach RR73 erneut → kein doppelter Eintrag.
# Cache ist Session-lokal in MainWindow._recent_logged_calls (App-Restart
# loescht den State, ist gewollt — Mike will Reset bei manuellem Neustart).
# Cache-Wachstum: bei 18000 QSOs ~1-2 MB, kein Cleanup noetig (KISS).
_LOG_DEDUP_WINDOW_S = 300


class QSOMixin:
    """Mixin fuer QSO-Logik — wird in MainWindow eingemischt.

    Enthaelt: Station anklicken, CQ, QSO-State Callbacks, QRZ Upload.
    """

    # ── P4.OMNI-NEUBAU (v0.96.0): DRY-Helpers fuer Pause/Resume ──────────────

    def _pause_omni_if_active(self) -> None:
        """OMNI pausieren + Pre-QSO-Flag setzen wenn OMNI aktiv.

        Aufruf-Stellen (4 QSO-Entry-Pfade):
          1. _on_station_clicked (Hunt-Klick)
          2. _on_tx_slot_for_partner (CQ-Reply, nur nicht-courtesy)
          3. _on_try_replace_pending_tx (P1.9 Replace)
          4. mw_cycle.on_message_decoded (OMNI-Listener — Antwort an uns)

        Setzt _omni_was_active_pre_qso=True damit _maybe_resume_omni
        nach QSO-Ende sauber resumed. _slot_index friert während QSO ein.
        """
        if self._omni_cq.is_active() and not self._omni_cq.is_paused():
            self._omni_cq.pause()
            self._omni_was_active_pre_qso = True

    def _maybe_resume_omni(self) -> None:
        """OMNI nach QSO-Ende fortsetzen — nur wenn vorher aktiv. Bei
        Caller-Queue mit wartenden Anrufern: nächstes QSO direkt starten
        (OMNI bleibt pausiert, V2-L10 — kein qso_state.cq_mode-Pfad mehr).

        Aufruf-Stellen: _on_qso_complete (RR73), _on_qso_confirmed (73),
        _on_qso_timeout.

        Block-Wahl nach letztem QSO-Slot (Mike-Spec):
          - QSO endete auf Even → Block 2 (Odd-First)
          - QSO endete auf Odd  → Block 1 (Even-First)
        """
        if not getattr(self, '_omni_was_active_pre_qso', False):
            return
        # V2-L10: Caller-Queue selbst abarbeiten — OMNI hat kein qso_state.cq_mode
        # mehr, also greift _resume_cq_if_needed nicht.
        if self.qso_sm._caller_queue:
            next_msg = self.qso_sm._caller_queue.pop(0)
            self.qso_sm.queue_changed.emit(
                [m.caller for m in self.qso_sm._caller_queue])
            their_even = getattr(next_msg, '_tx_even', None)
            if their_even is not None:
                self.encoder.tx_even = not their_even
            else:
                self.encoder.tx_even = None
            # OMNI bleibt pausiert (idempotent — _omni_was_active_pre_qso bleibt
            # True bis ein QSO-Exit-Pfad ohne Caller-Queue greift).
            self.qso_sm.start_qso(
                their_call=next_msg.caller,
                their_grid=(next_msg.grid_or_report
                            if next_msg.is_grid else ""),
                freq_hz=next_msg.freq_hz,
                their_snr=next_msg.snr,
            )
            return
        # Queue leer → echtes Resume mit Block-Wahl nach letztem TX-Slot.
        last_qso_was_even = bool(getattr(self, '_last_qso_tx_even', True))
        self._omni_cq.resume_after_qso(last_qso_was_even)
        self._omni_was_active_pre_qso = False

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
        """TX begonnen — Nachricht ins QSO-Panel.

        tx_even/slot_start_ts vom Encoder durchgereicht — qso_panel zeigt
        damit den korrekten Slot-Tag/Zeitstempel der TX-Aktion.

        P23: bei aktivem OMNI-CQ wird der Down-Counter (`omni.cq_remaining`)
        durchgereicht und qso_panel haengt Suffix `↻N` an die TX-Zeile.
        """
        # 11.05.2026 P28: _has_sent_cq auch bei OMNI/Direkt-TX setzen.
        # OMNI ruft encoder.transmit() direkt (umgeht _on_send_message),
        # daher wurde _has_sent_cq nie True → PSK-Worker hat nie gefetcht.
        # tx_started feuert fuer JEDEN TX-Pfad (Normal-CQ, OMNI, manuell).
        if message.startswith("CQ "):
            self._has_sent_cq = True
        # P15 (10.05.2026 Mike-Field-Test): ANT-Label NICHT mehr bei Sende.
        # Hardware sendet IMMER ANT1 (verriegelt), Label hier waere irrefuehrend.
        # Label gehoert hinter Empf.-Eintrag (siehe mw_cycle.on_message_decoded).
        omni_remaining = None
        omni = getattr(self, '_omni_cq', None)
        if omni is not None and omni.is_active() and not omni.is_paused():
            omni_remaining = omni.cq_remaining
        self.qso_panel.add_tx(message, "",
                              tx_even=tx_even, slot_start_ts=slot_start_ts,
                              omni_remaining=omni_remaining)

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
        # P2.OMNI-REDESIGN v4.0 (v0.95.23): OMNI bei Hunt-QSO pausieren
        # (Entry-Pfad 1 von 3 — _slot_index friert ein bis _maybe_resume_omni).
        self._pause_omni_if_active()
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
            their_snr=msg.snr,  # P1.HUNT-SNR (v0.95.21)
        )
        # P1.13 (v0.95.19): Im Normal-Modus TX-Frequenz auf Station-Frequenz
        # nachziehen + Spinbox synchronisieren. Frequenz wird NICHT
        # persistiert (settings.save_normal_tx_freq) — Hunt-Klick ist
        # temporaer, bandbezogene Default-Frequenz bleibt erhalten.
        # Histogramm-Update bewusst weggelassen (KISS, R1-Empfehlung) —
        # Histogramm-Widget ist im Normal-Modus typisch nicht sichtbar,
        # Encoder + Spinbox-Sync reichen vollstaendig.
        if self._rx_mode == "normal" and msg.freq_hz:
            spin = self.control_panel._tx_freq_spin
            # Hardware-Range aus Spinbox-Properties (statt hardcoded
            # 150/2800) — bleibt automatisch konsistent bei Range-Aenderung.
            freq_hz = max(spin.minimum(), min(spin.maximum(), int(msg.freq_hz)))
            self.encoder.audio_freq_hz = freq_hz
            spin.blockSignals(True)
            spin.setValue(freq_hz)
            spin.blockSignals(False)
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
            self.qso_panel.status_label.setText(f"{count} QSO(s)")
            self.qso_panel.status_label.setStyleSheet("color: #666; font-size: 11px; padding: 2px;")
            self.qso_sm.stop_cq()
            self.control_panel.update_qso_counter(0)

    @Slot()
    def _on_advance(self):
        self.qso_sm.advance()

    @Slot()
    def _on_cancel(self):
        """HALT — stoppt ALLES: CQ, QSO, TX, Messung, OMNI, Auto-Hunt."""
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
        # OMNI ebenfalls stoppen — ohne diesen Branch bleibt OMNI aktiv
        # nach HALT, Inkonsistenz mit Button-State.
        if self._omni_cq.is_active():
            self._omni_cq.stop("manual_halt")
        # V2-L3: Slot-Tracking sauber resetten beim HALT.
        self._last_qso_tx_even = None
        self.qso_panel.add_info("HALT — alles gestoppt")
        self.statusBar().showMessage("HALT — CQ, QSO, TX, OMNI gestoppt", 5000)
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

        # P2.OMNI-REDESIGN v4.0 (v0.95.23): omni_tx.on_qso_started entfernt
        # (war Block-Counter-Reset). Pause/Resume erfolgt jetzt zentral
        # via _pause_omni_if_active in den 3 QSO-Entry-Pfaden.

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
        # V2-L3: letzten TX-Slot fuer OMNI-Block-Wahl nach QSO-Ende merken.
        # _last_qso_tx_even=True → naechstes Resume waehlt Block 2 (Odd-First).
        self._last_qso_tx_even = bool(self.encoder.tx_even)
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
        """FT8-Nachricht encoden und ueber FlexRadio senden.

        P4.OMNI-NEUBAU (v0.96.0): OMNI-Bypass-Block raus. OMNI hat seinen
        eigenen Worker-Thread (core/omni_cq.py) der direkt encoder.transmit()
        ruft — qso_state.send_message wird ausschliesslich vom Normal-CQ /
        Hunt-Pfad emittiert.
        """
        # Operator Presence Check (Totmannschalter, gesetzl. Pflicht DE).
        # Laufende QSOs werden IMMER zu Ende gefuehrt!
        if not self.presence_can_tx():
            print(f"[Presence] TX blockiert (Operator abwesend): '{message}'")
            return
        if message.startswith("CQ "):
            self._has_sent_cq = True
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
        """RR73 gesendet — ADIF schreiben (UI-Meldung kommt erst bei 73 oder Timeout).

        P1.7 (v0.95.19): Duplikat-Filter — wenn dieselbe Station auf
        gleichem Band innerhalb _LOG_DEDUP_WINDOW_S=300s schon geloggt
        wurde, ADIF/qso_log/Antennen-Stats ueberspringen.
        UI-Cleanup (active_qso, rx_panel, auto_hunt) laeuft IMMER —
        sonst Inkonsistenzen (R1-KRITISCH).

        11.05.2026 P28: strategische Debug-Punkte — Mike meldet "App
        haengt 1 Min nach QSO". Wir loggen jeden Step + Dauer.
        """
        # 11.05.2026 P28: Bisection-Debug-Punkte mit Wallclock-Timing
        from core.debug_log import debug_log as _dbg
        import time as _t
        _t0 = _t.time()
        _dbg("QSO-DONE", f"START call={qso_data.their_call}")

        # UI-Cleanup IMMER (vor Duplikat-Check) — R1-KRITISCH:
        self._active_qso_targets.discard(qso_data.their_call)
        self.rx_panel.set_active_call("")
        # Auto-Hunt: QSO erfolgreich → Pause, dann naechste Station
        if self._auto_hunt.active:
            self._auto_hunt.on_qso_complete(qso_data.their_call)
        _dbg("QSO-DONE", f"UI-cleanup done dt={_t.time()-_t0:.3f}s")

        # KEIN add_qso_complete hier — kommt in _on_qso_confirmed (nach 73 oder Timeout)

        band = self.settings.band.upper()
        freq = self.settings.frequency_mhz

        # P1.7 Duplikat-Check: (call, band)-Tupel-Key, beide UPPER (siehe
        # qso_log.py:23 add_qso normiert Band/Call gleich). Mode wird
        # bewusst NICHT in den Key aufgenommen — KISS, Mike's Mode-Wechsel
        # binnen 5 Min mit gleicher Station ist Hobby-Praxis quasi nie.
        now = time.time()
        call_key = qso_data.their_call.upper()
        dedup_key = (call_key, band)
        last = self._recent_logged_calls.get(dedup_key, 0.0)
        if now - last < _LOG_DEDUP_WINDOW_S:
            print(f"[QSO] DUPLIKAT-FILTER: {call_key}@{band} schon vor "
                  f"{int(now-last)}s geloggt → skip ADIF + qso_log + antenna_stats")
            self.qso_panel.add_info(
                f"{call_key} Duplikat ({int(now-last)}s) — kein ADIF-Eintrag")
            _dbg("QSO-DONE", f"DUPLIKAT skip — total dt={_t.time()-_t0:.3f}s")
            # P2.OMNI-REDESIGN v4.0: Resume-Versuch trotzdem (Symmetrie zu
            # Non-Duplikat-Pfad — UI-Cleanup lief schon, OMNI darf weiter).
            self._maybe_resume_omni()
            return  # KEIN log_qso, KEIN add_qso, KEIN log_antenna_qso
        self._recent_logged_calls[dedup_key] = now

        _t_step = _t.time()
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
        _dbg("QSO-DONE", f"adif.log_qso dt={_t.time()-_t_step:.3f}s")

        _t_step = _t.time()
        self.qso_log.add_qso(qso_data.their_call, band)
        _dbg("QSO-DONE", f"qso_log.add_qso dt={_t.time()-_t_step:.3f}s")

        # Antennen-Statistik pro QSO loggen — immer schreiben, "–" wenn kein Pref
        if hasattr(self, '_stats_logger') and self._stats_logger is not None:
            _t_step = _t.time()
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
            _dbg("QSO-DONE", f"log_antenna_qso dt={_t.time()-_t_step:.3f}s")

        # P2.OMNI-REDESIGN v4.0 (v0.95.23): OMNI nach RR73 fertig resumen
        # (Exit-Pfad 1 von 3). _maybe_resume_omni schuetzt sich selbst
        # via _omni_was_active_pre_qso und Caller-Queue-Check.
        _t_step = _t.time()
        self._maybe_resume_omni()
        _dbg("QSO-DONE", f"_maybe_resume_omni dt={_t.time()-_t_step:.3f}s")
        _dbg("QSO-DONE", f"END total dt={_t.time()-_t0:.3f}s")

    @Slot(object)
    def _on_qso_confirmed(self, qso_data):
        """73 empfangen — QSO wirklich komplett, ✓ anzeigen.

        11.05.2026 P28: Debug-Punkte mit Wallclock-Timing (Mike: "App
        haengt 1 Min nach QSO").
        """
        from core.debug_log import debug_log as _dbg
        import time as _t
        _t0 = _t.time()
        _dbg("QSO-CONF", f"START call={qso_data.their_call}")

        self.qso_panel.add_qso_complete(qso_data.their_call)
        _dbg("QSO-CONF", f"add_qso_complete dt={_t.time()-_t0:.3f}s")

        # Logbuch aktualisieren (neues QSO wurde in ADIF geschrieben)
        _t_step = _t.time()
        self.qso_panel.logbook.refresh()
        _dbg("QSO-CONF", f"logbook.refresh dt={_t.time()-_t_step:.3f}s")

        # P1.14 W6: Auto-Hunt nach erfolgreichem manuellem QSO freigeben
        if self._auto_hunt.active:
            self._auto_hunt.on_manual_qso_end()
        # CQ-Modus läuft weiter — visuell bestätigen
        if self.qso_sm.cq_mode:
            self.control_panel.set_cq_active(True)
            self.qso_panel.add_info("CQ-Modus läuft weiter...")
        # P2.OMNI-REDESIGN v4.0 (v0.95.23): OMNI nach 73-Empfang/WAIT_73-Timeout
        # /Courtesy-73-fertig resumen (Exit-Pfad 2 von 3).
        _t_step = _t.time()
        self._maybe_resume_omni()
        _dbg("QSO-CONF", f"_maybe_resume_omni dt={_t.time()-_t_step:.3f}s")
        _dbg("QSO-CONF", f"END total dt={_t.time()-_t0:.3f}s")

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
        """QRZ Bulk-Upload mit Title-Suffix + Statusbar-Cancel-Widget.

        P1.QRZ-UPLOAD-UI-2 v0.95.15: Progress in Titelleiste statt Dialog.
        Klick-Sperre 3-fach (R1-KP-2) bleibt: Flag → Button → submit.
        """
        from PySide6.QtWidgets import QDialog

        # Re-Entry-Check als FIRST line (defensive)
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

        # Filter: nur Records aus adif/ (NICHT adif/hochgeladen/) — AC-7
        all_records = self.qso_panel.logbook._all_records
        records = [
            r for r in all_records
            if "hochgeladen" not in r.get("_SOURCE_FILE", "").replace("\\", "/")
        ]
        if not records:
            self.statusBar().showMessage(
                "Keine QSOs zum Hochladen — alle bereits in adif/hochgeladen/.", 5000)
            return

        from ui.qrz_upload_dialogs import QRZConfirmDialog
        confirm = QRZConfirmDialog(len(records), parent=self)
        if confirm.exec() != QDialog.DialogCode.Accepted:
            return

        # KP-2 Reihenfolge: 1) Flag → 2) Button → 3) Worker
        self._qrz_bulk_active = True
        self._set_qrz_button_enabled(False)
        self._show_qrz_status_widget(True, len(records))

        from core.qrz_upload_worker import QRZUploadWorker
        client = self._get_qrz_client()
        self._qrz_worker = QRZUploadWorker(client, records, parent=self)
        self._qrz_worker.progress.connect(
            self._on_qrz_progress, Qt.ConnectionType.QueuedConnection)
        self._qrz_worker.finished.connect(
            self._on_qrz_bulk_finished, Qt.ConnectionType.QueuedConnection)
        self._qrz_worker.cooldown_tick.connect(
            self._on_qrz_cooldown_tick, Qt.ConnectionType.QueuedConnection)

        self._qrz_worker.start()
        print(f"[QRZ] Bulk-Upload gestartet ({len(records)} QSOs)")

    @Slot(int, int, int, int, int)
    def _on_qrz_progress(self, current: int, total: int,
                         ok: int, dup: int, fail: int) -> None:
        """Worker-Progress alle 10 QSOs → Title + Statusbar-Label."""
        pct = int((current / total) * 100) if total else 0
        self._qrz_title_suffix = f" — QRZ ↑ {current}/{total} ({pct}%)"
        self._update_window_title()
        if hasattr(self, '_qrz_status_label'):
            self._qrz_status_label.setText(f"QRZ ↑ {current}/{total} ({pct}%)")

    @Slot(int)
    def _on_qrz_cooldown_tick(self, seconds_left: int) -> None:
        """Worker meldet Cooldown-Sekunde — Statusbar zeigt Countdown."""
        if hasattr(self, '_qrz_status_label'):
            if seconds_left > 0:
                self._qrz_status_label.setText(
                    f"QRZ ↑ pausiert {seconds_left}s ...")
            else:
                self._qrz_status_label.setText("QRZ ↑ retrying...")

    @Slot(int, int, int, bool, int)
    def _on_qrz_bulk_finished(self, ok: int, dup: int, fail: int,
                              cancelled: bool, total_processed: int) -> None:
        """Worker-Finish — Title reset, Toast, File-Move."""
        # Title zuruecksetzen
        self._qrz_title_suffix = ""
        self._update_window_title()
        # Statusbar-Widget verbergen
        self._show_qrz_status_widget(False)
        # Toast 10s mit Endstand
        total_planned = (
            self._qrz_worker.total_records
            if getattr(self, '_qrz_worker', None) else 0
        )
        if cancelled:
            msg = (f"QRZ Upload abgebrochen bei {total_processed}/{total_planned}: "
                   f"{ok} neu, {dup} dup, {fail} fail")
        else:
            msg = f"QRZ Upload fertig: {ok} neu, {dup} dup, {fail} fail"
        self.statusBar().showMessage(msg, 10000)

        # File-Move
        if hasattr(self, '_qrz_worker') and self._qrz_worker:
            file_results = self._qrz_worker.file_results
            self._handle_qrz_file_results(file_results)
            self._qrz_worker.shutdown(wait=False)

        # State reset
        self._qrz_bulk_active = False
        self._set_qrz_button_enabled(True)
        self.qso_panel.logbook.refresh()
        print(f"[QRZ] Bulk-Upload beendet: {ok} neu, {dup} dup, {fail} fail "
              f"(cancelled={cancelled})")

    def _handle_qrz_file_results(self, file_results: dict) -> None:
        """Files mit fail==0 und expected==processed nach adif/hochgeladen/."""
        import shutil
        from pathlib import Path
        adif_dir = Path.cwd() / "adif"
        target_dir = adif_dir / "hochgeladen"
        try:
            target_dir.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            self.statusBar().showMessage(f"Fehler hochgeladen-Ordner: {e}", 8000)
            return
        moved = 0
        skipped = 0
        for src_path, counts in file_results.items():
            processed = counts["ok"] + counts["dup"] + counts["fail"]
            if counts["fail"] == 0 and processed == counts["expected"] and processed > 0:
                src = Path(src_path)
                if not src.is_file():
                    continue
                # Schutz: nur Files aus adif/ verschieben (nicht aus hochgeladen/)
                if "hochgeladen" in str(src).replace("\\", "/"):
                    continue
                dest = target_dir / src.name
                if dest.exists():
                    print(f"[QRZ] Move uebersprungen — Ziel existiert: {dest}")
                    self.statusBar().showMessage(
                        f"File-Move uebersprungen: {src.name} bereits in hochgeladen/", 5000)
                    skipped += 1
                    continue
                try:
                    shutil.move(str(src), str(dest))
                    moved += 1
                except OSError as e:
                    print(f"[QRZ] File-Move {src} fehlgeschlagen: {e}")
                    self.statusBar().showMessage(
                        f"File-Move fehlgeschlagen: {src.name} ({e})", 5000)
            else:
                skipped += 1
        if moved:
            print(f"[QRZ] {moved} Datei(en) nach adif/hochgeladen/ verschoben "
                  f"({skipped} bleiben wegen FAILs oder unvollstaendig)")

    def _show_qrz_status_widget(self, visible: bool, total: int = 0) -> None:
        """Statusbar-Cancel-Widget toggle."""
        if not hasattr(self, '_qrz_status_widget'):
            return
        self._qrz_status_widget.setVisible(visible)
        if visible:
            if hasattr(self, '_qrz_status_label'):
                self._qrz_status_label.setText(f"QRZ ↑ 0/{total} (0%)")
            if hasattr(self, '_qrz_status_cancel_btn'):
                self._qrz_status_cancel_btn.setEnabled(True)

    @Slot()
    def _on_qrz_status_cancel_clicked(self) -> None:
        """Klick auf Statusbar-✕ → Worker cancel."""
        if (hasattr(self, '_qrz_worker') and self._qrz_worker
                and getattr(self, '_qrz_bulk_active', False)):
            self._qrz_worker.cancel()
            if hasattr(self, '_qrz_status_cancel_btn'):
                self._qrz_status_cancel_btn.setEnabled(False)
            if hasattr(self, '_qrz_status_label'):
                self._qrz_status_label.setText("QRZ ↑ wird abgebrochen ...")

    def _update_window_title(self) -> None:
        """Zentrale Title-Update-Methode (R1: Hardcoding vermeiden)."""
        suffix = getattr(self, '_qrz_title_suffix', '')
        self.setWindowTitle(f"SimpleFT8 — {self.settings.callsign}{suffix}")

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
        # P2.OMNI-REDESIGN v4.0 (v0.95.23): OMNI nach Hunt/QSO-Timeout
        # resumen (Exit-Pfad 3 von 3).
        self._maybe_resume_omni()

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
        # P2.OMNI-REDESIGN v4.0 (v0.95.23): OMNI bei CQ-Reply pausieren
        # (Entry-Pfad 2 von 3). Bei Courtesy-73 NICHT pausieren — QSO ist
        # schon zu Ende, _maybe_resume_omni wurde via _on_qso_complete
        # bereits aufgerufen.
        if not is_courtesy:
            self._pause_omni_if_active()
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

        # P2.OMNI-REDESIGN v4.0 (v0.95.23) R1-V2 K1-Fix: OMNI bei Replace-Pfad
        # pausieren (Entry-Pfad 3 von 3). War bisher inkonsistent zu Hunt
        # + CQ-Reply — _omni_was_active_pre_qso wurde nie gesetzt → kein
        # Resume nach QSO-Ende.
        self._pause_omni_if_active()

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
