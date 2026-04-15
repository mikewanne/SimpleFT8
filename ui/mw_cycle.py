"""SimpleFT8 MainWindow — Zyklusverarbeitung + Diversity Akkumulation Mixin."""

from __future__ import annotations

import threading
import time
from typing import TYPE_CHECKING

from PySide6.QtCore import Slot

if TYPE_CHECKING:
    from .main_window import MainWindow

from core.qso_state import QSOState
from core.message import FT8Message
from core import ntp_time
from core.station_accumulator import accumulate_stations
from radio.presets import PREAMP_PRESETS


class CycleMixin:
    """Mixin fuer Zyklusverarbeitung — wird in MainWindow eingemischt.

    Enthaelt: _on_cycle_decoded (Diversity/Normal Akkumulation),
    _on_cycle_start (Antennenwechsel), on_message_decoded.
    """

    def _on_cycle_decoded(self, messages: list):
        """Ein kompletter FT8-Zyklus dekodiert."""
        if not self.rx_panel._rx_active:
            return
        # Slot-Parity: ft8lib dekodiert innerhalb des SELBEN Slots (< 0.3s)
        # → is_even_cycle() zeigt noch den aktuellen Slot, KEIN not nötig
        msg_was_even = self.timer.is_even_cycle()
        if messages:
            for m in messages:
                m._tx_even = msg_was_even
        count = len(messages) if messages else 0
        self.control_panel.update_decode_count(count)

        # DT-Korrektur aktualisieren + Anzeige
        if messages:
            dt_values = [m.dt for m in messages if hasattr(m, 'dt')]
            ntp_time.update_from_decoded(dt_values)
            corr = ntp_time.get_correction()
            n = ntp_time._last_sample_count
            if n > 0:
                self.control_panel.update_dt_correction(corr, n)
                self._update_statusbar()  # DT in Statusbar aktualisieren

        if self._rx_mode == "diversity":
            # Queue IMMER poppen — auch bei 0 Stationen!
            # Sonst geraet die Queue aus dem Takt wenn eine Antenne nichts empfaengt
            ant_queue = getattr(self, '_diversity_ant_queue', None)
            if ant_queue:
                ant, was_phase = ant_queue.popleft()
            else:
                ant, was_phase = "A1", "operate"

        # Messung aufzeichnen wenn wir in der Mess-Phase waren
        if self._rx_mode == "diversity" and was_phase == "measure":
            valid = [m for m in (messages or []) if m.snr is not None and m.snr > -20]
            score = sum(max(0.0, float(m.snr + 30)) for m in valid)
            station_count = len(valid)
            avg_snr = (sum(m.snr for m in valid) / station_count) if station_count else -30.0
            # DX-Score: Anzahl SCHWACHER Stationen (SNR < -10 dB)
            # Schwache Signale = DX (Australien -24dB zaehlt, Bochum +12dB nicht)
            weak_count = len([m for m in valid if m.snr < -10])
            with self._diversity_lock:
                self._diversity_ctrl.record_measurement(
                    ant, score,
                    station_count=station_count,
                    avg_snr=avg_snr,
                    dx_weak_count=weak_count,
                )
                # Stationsfrequenzen für CQ-Frequenzwahl erfassen
                for m in (messages or []):
                    if hasattr(m, 'freq_hz') and m.freq_hz:
                        self._diversity_ctrl.record_freq(m.freq_hz)
            self.control_panel.update_diversity_ratio(
                self._diversity_ctrl.ratio, self._diversity_ctrl.phase,
                measure_step=self._diversity_ctrl.measure_step,
                measure_total=self._diversity_ctrl.MEASURE_CYCLES,
                operate_cycles=self._diversity_ctrl.operate_cycles,
                operate_total=self._diversity_ctrl.OPERATE_CYCLES,
                scoring_mode=self._diversity_ctrl.scoring_mode,
            )
            # Messung abgeschlossen → CQ freigeben + Frequenz wählen
            if self._diversity_ctrl.phase == "operate":
                self._set_cq_locked(False)
                cq_freq = self._diversity_ctrl.get_free_cq_freq()
                if cq_freq:
                    self.encoder.audio_freq_hz = cq_freq
                    print(f"[Diversity] Einmessen fertig — CQ auf {cq_freq} Hz")
                else:
                    print("[Diversity] Einmessen fertig — CQ freigegeben")
                self.control_panel.update_freq_histogram(
                    self._diversity_ctrl.get_histogram_data()
                )

        if self._rx_mode == "diversity" and messages:
            # Diversity: gemeinsame Akkumulation mit Antennen-Info
            changed = accumulate_stations(
                self._diversity_stations, messages,
                self._active_qso_targets, antenna=ant)

            # Tabelle neu aufbauen wenn sich was geaendert hat
            if changed:
                self.rx_panel.table.setRowCount(0)
                for m in self._diversity_stations.values():
                    self.rx_panel.add_message(m)
                self.rx_panel.reapply_sort()
                a1_msgs = [m for m in self._diversity_stations.values()
                           if getattr(m, 'antenna', '').startswith('A1')]
                a2_msgs = [m for m in self._diversity_stations.values()
                           if getattr(m, 'antenna', '').startswith('A2')]
                a1_avg = sum(m.snr for m in a1_msgs) / len(a1_msgs) if a1_msgs else -30
                a2_avg = sum(m.snr for m in a2_msgs) / len(a2_msgs) if a2_msgs else -30
                self.control_panel.update_diversity_counts(
                    len(a1_msgs), len(a2_msgs), a1_avg, a2_avg,
                    scoring_mode=self._diversity_ctrl.scoring_mode)

            self.control_panel.update_decode_count(
                len(self._diversity_stations)
            )

        elif self._rx_mode == "normal" and messages:
            # Normal: gemeinsame Akkumulation ohne Antennen-Info
            changed = accumulate_stations(
                self._normal_stations, messages,
                self._active_qso_targets, antenna="")
            if changed:
                self.rx_panel.table.setRowCount(0)
                for m in self._normal_stations.values():
                    self.rx_panel.add_message(m)
                self.rx_panel.reapply_sort()
            self.control_panel.update_decode_count(len(self._normal_stations))
            if self._normal_stations:
                avg_snr = round(sum(m.snr for m in self._normal_stations.values()) / len(self._normal_stations))
                self.control_panel.update_snr(avg_snr)

        elif messages:
            # DX Tuning: nur aktueller Zyklus
            self.rx_panel.table.setRowCount(0)
            for msg in messages:
                self.rx_panel.add_message(msg)
            self.rx_panel.reapply_sort()

        # DX-Tune Dialog fuettern wenn aktiv
        if self._dx_tune_dialog is not None:
            self._dx_tune_dialog.feed_cycle(messages)

        # AP-Lite: Rescue bei QSO-Decode-Fail (WAIT_REPORT / WAIT_RR73)
        # Läuft nur wenn AP_LITE_ENABLED = True (Feldtest-Flag)
        if self._ap_lite.enabled and self.qso_sm.qso:
            _state = self.qso_sm.state
            if _state in (QSOState.WAIT_REPORT, QSOState.WAIT_RR73):
                _their = self.qso_sm.qso.their_call
                _freq = float(getattr(self.qso_sm.qso, 'freq_hz',
                                     self.encoder.audio_freq_hz) or self.encoder.audio_freq_hz)
                _qso_state_int = 1 if _state == QSOState.WAIT_REPORT else 2
                _partner_found = any(
                    getattr(m, 'caller', '') == _their for m in (messages or [])
                )
                if not _partner_found and self.decoder.last_pcm_12k is not None:
                    _pcm = self.decoder.last_pcm_12k
                    _slot_time = float(int(time.time() / 15.0) * 15)
                    # Rescue-Versuch (zweiter Fehler)
                    _result = self._ap_lite.try_rescue(
                        _pcm, _slot_time, _their, _freq, _qso_state_int,
                        own_callsign=self.settings.callsign,
                        own_locator=self.settings.locator,
                    )
                    if _result and _result.success:
                        self.qso_panel.add_info(
                            f"[AP-Lite] Gerettet: {_result.recovered_message} "
                            f"(score={_result.score:.2f})"
                        )
                        print(f"[AP-Lite] RESCUE: '{_result.recovered_message}' "
                              f"score={_result.score:.3f}")
                    else:
                        # Ersten Fehler merken für nächsten Rescue-Versuch
                        self._ap_lite.on_decode_failed(
                            _pcm, _slot_time, _their, _freq, _qso_state_int,
                            own_callsign=self.settings.callsign,
                            own_locator=self.settings.locator,
                            snr_estimate=float(getattr(self.qso_sm, '_last_snr', -10)),
                        )

        # Auto-Hunt: automatisch CQ-Stationen anrufen (verstecktes Feature)
        if self._auto_hunt.active:
            _idle = self.qso_sm.state in (QSOState.IDLE, QSOState.TIMEOUT)
            _candidate = self._auto_hunt.select_next(
                messages=messages or [],
                qso_idle=_idle,
                presence_ok=self.presence_can_tx(),
            )
            if _candidate:
                # Hunt-QSO starten (gleicher Weg wie manueller Klick)
                self._active_qso_targets.add(_candidate.call)
                self.rx_panel.set_active_call(_candidate.call)
                self.qso_sm.max_calls = 3
                # Even/Odd: sende im GEGENTEILIGEN Slot der Gegenstation
                if _candidate.tx_even is not None:
                    self.encoder.tx_even = not _candidate.tx_even
                else:
                    self.encoder.tx_even = None
                self.qso_sm.start_qso(
                    their_call=_candidate.call,
                    their_grid=_candidate.grid,
                    freq_hz=_candidate.freq_hz,
                )

    @Slot(float, float)
    def _on_cycle_tick(self, seconds_in_cycle: float, cycle_duration: float):
        if not self.rx_panel._rx_active:
            return
        self.control_panel.update_cycle_bar(seconds_in_cycle, cycle_duration)

    @Slot(int, bool)
    def _on_cycle_start(self, cycle_num: int, is_even: bool):
        # ── Anzeige zurücksetzen wenn kein TX ──────────────────
        if not self.encoder.is_transmitting:
            self.control_panel.update_tx_peak(0.0)

        # ── Auto TX Level Regelung ──────────────────────────────
        if self._fwdpwr_samples:
            self._auto_adjust_tx_level()

        self.qso_sm.on_cycle_end()

        # OMNI-TX: pro Zyklus voranschreiten (nach QSO-State-Update)
        _in_qso = self.qso_sm.state not in (
            QSOState.IDLE, QSOState.TIMEOUT,
            QSOState.CQ_CALLING, QSOState.CQ_WAIT,
        )
        self._omni_tx.advance(qso_active=_in_qso)

        # Diversity: Antenne umschalten bei jedem Zyklus (non-blocking)
        if self._rx_mode == "diversity" and self.radio.ip and self.rx_panel._rx_active:
            # BUG-1: TX-Schutz — waehrend TX keine Antenne umschalten!
            if self.encoder.is_transmitting:
                return

            with self._diversity_lock:  # BUG-2: Race Condition Guard
                # Queue: aktuelle Antenne + Phase merken BEVOR umgeschaltet wird.
                ant_queue = getattr(self, '_diversity_ant_queue', None)
                if ant_queue is not None:
                    ant_queue.append((self._diversity_current_ant, self._diversity_ctrl.phase))

                band = self.settings.band

                # Betriebszyklus zaehlen + ggf. neu messen
                if self._diversity_ctrl.phase == "operate":
                    self._diversity_ctrl.on_operate_cycle()
                    # Remeasure NUR wenn wirklich idle — CQ_CALLING/CQ_WAIT schützen!
                    qso_active = self.qso_sm.state not in (
                        QSOState.IDLE, QSOState.TIMEOUT,
                    ) or self.qso_sm.state in (
                        QSOState.CQ_CALLING, QSOState.CQ_WAIT,
                    )
                    if self._diversity_ctrl.should_remeasure(qso_active):
                        self._diversity_ctrl.start_measure()
                        self._set_cq_locked(True)
                        self.control_panel.update_diversity_ratio(
                            "50:50", "remeasure", 0,
                            self._diversity_ctrl.MEASURE_CYCLES,
                            scoring_mode=self._diversity_ctrl.scoring_mode)
                        print("[Diversity] Automatische Neueinmessung gestartet")

                self._diversity_current_ant = self._diversity_ctrl.choose()

                if self._diversity_current_ant == "A1":
                    gain = getattr(self, '_diversity_ant1_gain',
                                   PREAMP_PRESETS.get(band, 10))
                else:
                    gain = getattr(self, '_diversity_ant2_gain',
                                   PREAMP_PRESETS.get(band, 10) + 10)
                ant_cmd = "ANT1" if self._diversity_current_ant == "A1" else "ANT2"
                self.control_panel.update_diversity_ratio(
                    self._diversity_ctrl.ratio, self._diversity_ctrl.phase,
                    measure_step=self._diversity_ctrl.measure_step,
                    measure_total=self._diversity_ctrl.MEASURE_CYCLES,
                    operate_cycles=self._diversity_ctrl.operate_cycles,
                    operate_total=self._diversity_ctrl.OPERATE_CYCLES,
                    scoring_mode=self._diversity_ctrl.scoring_mode,
                )

            # BUG-3: ant_cmd + gain als Argumente, nicht als Closure
            def _switch(cmd=ant_cmd, g=gain):
                self.radio.set_rx_antenna(cmd)
                self.radio.set_rfgain(g)
            threading.Thread(target=_switch, daemon=True).start()

    def on_message_decoded(self, msg: FT8Message):
        """Vom Decoder — NUR fuer QSO-Logik, NICHT fuer Tabelle!"""
        if not self.rx_panel._rx_active:
            return
        self.control_panel.update_snr(msg.snr)
        self.qso_sm.set_last_snr(msg.snr)

        # RX zuerst anzeigen, dann verarbeiten (sonst erscheint TX-Antwort vor RX im Log)
        if msg.target == self.settings.callsign:
            self.qso_panel.add_rx(msg.raw)

        self.qso_sm.on_message_received(msg)
