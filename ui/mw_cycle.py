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


def _slot_from_utc(utc_str: str):
    """Even/Odd-Slot aus HHMMSS-String für FT2 (Periode 3.8s). None bei Fehler."""
    if not utc_str or len(utc_str) < 6:
        return None
    try:
        secs = int(utc_str[:2]) * 3600 + int(utc_str[2:4]) * 60 + int(utc_str[4:6])
        return (int(secs / 3.8) % 2) == 0
    except (ValueError, TypeError):
        return None


class CycleMixin:
    """Mixin fuer Zyklusverarbeitung — wird in MainWindow eingemischt.

    Enthaelt: _on_cycle_decoded (Diversity/Normal Akkumulation),
    _on_cycle_start (Antennenwechsel), on_message_decoded.
    """

    def _on_cycle_decoded(self, messages: list):
        """Ein kompletter FT8-Zyklus dekodiert."""
        if not self.rx_panel._rx_active:
            return

        self._assign_slot_parity(messages)
        self.control_panel.update_decode_count(len(messages) if messages else 0)
        self._update_dt_correction(messages)

        ant, was_phase = "A1", "operate"
        if self._rx_mode == "diversity":
            ant, was_phase = self._pop_diversity_queue()

        if self._rx_mode == "diversity" and was_phase == "measure":
            self._handle_diversity_measure(messages, ant)

        if self._rx_mode == "diversity" and messages:
            self._handle_diversity_operate(messages, ant)
        elif self._rx_mode == "normal":
            self._handle_normal_mode(messages)
        elif messages:
            self._handle_dx_tune_mode(messages)

        # Slot-synchroner Such-Trigger + Histogramm-Refresh JEDEN Slot
        # (unabhaengig von messages-Inhalt — _diversity_stations mit Aging ist
        # Quelle der Wahrheit). Das fixt P1 (Histogramm-Update Guard) gleich mit.
        if self._rx_mode == "diversity" and was_phase == "operate":
            self._refresh_diversity_freq_view()

        if self._dx_tune_dialog is not None:
            self._dx_tune_dialog.feed_cycle(messages)

        self._run_ap_lite_rescue(messages)
        self._run_auto_hunt(messages)

    def _refresh_diversity_freq_view(self):
        """Pro Slot: Histogramm refreshen + ggf. Such-Trigger.

        Slot-Counter (_search_slots_remaining) tickt bei jedem Aufruf. Wenn er
        0 erreicht → Suche aktiv ausgeloest. Sonst nur Histogramm-Update damit
        die UI-Bins live bleiben.

        QSO-Schutz: Bei aktivem QSO wird der Such-Counter pro Slot
        ZURUECKGESETZT (nicht dekrementiert) — damit nach QSO-Ende wieder
        volle ~60s Karenzzeit verfuegbar sind und kein Mid-QSO-Frequenz-
        sprung passiert.
        """
        qso_busy = self.qso_sm.state not in (
            QSOState.IDLE, QSOState.TIMEOUT,
            QSOState.CQ_CALLING, QSOState.CQ_WAIT,
        )
        with self._diversity_lock:
            self._diversity_ctrl.sync_from_stations(self._diversity_stations)
            if qso_busy:
                self._diversity_ctrl.reset_search_counter()
            else:
                if self._diversity_ctrl.tick_slot():
                    self._diversity_ctrl.update_proposed_freq(qso_active=False)
        self.control_panel.update_freq_histogram(
            self._diversity_ctrl.get_histogram_data())

    # ───────────────────────────────────────────────────────────────────
    # Helper-Methoden für _on_cycle_decoded — extrahiert für Lesbarkeit.
    # Reine 1:1-Auslagerung der Original-Blöcke, kein Verhaltenswechsel.
    # ───────────────────────────────────────────────────────────────────

    def _assign_slot_parity(self, messages):
        """Slot-Parity setzen.

        ft8lib dekodiert innerhalb des SELBEN Slots (< 0.3s) →
        is_even_cycle() zeigt noch den aktuellen Slot, KEIN not nötig.
        FT2: 3.75s Zyklen → Slot aus Nachricht-UTC berechnen (Timer-Drift zu gross).
        """
        if not messages:
            return
        msg_was_even = self.timer.is_even_cycle()
        mode = self.settings.mode
        for m in messages:
            if mode == "FT2":
                utc = getattr(m, '_utc_str', None) or getattr(m, '_utc_display', None)
                slot = _slot_from_utc(utc) if utc else None
                m._tx_even = slot if slot is not None else msg_was_even
            else:
                m._tx_even = msg_was_even

    def _update_dt_correction(self, messages):
        """DT-Korrektur aus dekodierten Nachrichten aktualisieren + Anzeige."""
        if not messages:
            return
        dt_values = [m.dt for m in messages if hasattr(m, 'dt')]
        ntp_time.update_from_decoded(dt_values)
        corr = ntp_time.get_correction()
        n = ntp_time._last_sample_count
        if n > 0:
            self.control_panel.update_dt_correction(corr, n)
            self._update_statusbar()  # DT in Statusbar aktualisieren

    def _pop_diversity_queue(self):
        """Antennen-Queue popleft → (ant, was_phase).

        Queue IMMER poppen — auch bei 0 Stationen! Sonst geraet die Queue aus
        dem Takt wenn eine Antenne nichts empfaengt.
        """
        ant_queue = getattr(self, '_diversity_ant_queue', None)
        if ant_queue:
            return ant_queue.popleft()
        return "A1", "operate"

    def _handle_diversity_measure(self, messages, ant):
        """Diversity-Mess-Phase: Messung aufzeichnen + Phase-Übergang.

        IMMER aufzeichnen — auch mit 0 Stationen! Sonst haengt die Messung
        bei Antennen die nichts empfangen (Bug #9: 4/8 haengt).
        """
        valid = [m for m in (messages or []) if m.snr is not None and m.snr > -20]
        station_count = len(valid)
        score = sum(max(0.0, float(m.snr + 30)) for m in valid) if valid else 0.0
        avg_snr = (sum(m.snr for m in valid) / station_count) if station_count else -30.0
        weak_count = len([m for m in valid if m.snr < -10])
        with self._diversity_lock:
            self._diversity_ctrl.record_measurement(
                ant, score,
                station_count=station_count,
                avg_snr=avg_snr,
                dx_weak_count=weak_count,
            )
            self._diversity_ctrl.sync_from_stations(self._diversity_stations)
            self._diversity_ctrl.update_proposed_freq()
        # Histogram LIVE aktualisieren (auch waehrend Messung)
        self.control_panel.update_freq_histogram(
            self._diversity_ctrl.get_histogram_data())
        self.control_panel.update_diversity_ratio(
            self._diversity_ctrl.ratio, self._diversity_ctrl.phase,
            measure_step=self._diversity_ctrl.measure_step,
            measure_total=self._diversity_ctrl.MEASURE_CYCLES,
            operate_cycles=self._diversity_ctrl.operate_cycles,
            operate_total=self._diversity_ctrl.OPERATE_CYCLES,
            scoring_mode=self._diversity_ctrl.scoring_mode,
        )
        # Einmessen abgeschlossen → nur beim Übergang measure→operate ausführen
        if self._diversity_ctrl.phase == "operate":
            if not getattr(self, '_diversity_in_operate', False):
                self._diversity_in_operate = True
                self._stats_warmup_cycles = 6
                print("[Stats] Einmessen fertig — 6 Zyklen Warmup bis Stats starten")
                self._set_cq_locked(False)
                # Ratio in PresetStore ergänzen (Timestamp von Gain-Messung bleibt)
                _scoring = getattr(self._diversity_ctrl, 'scoring_mode', 'normal')
                _store = getattr(self, '_dx_store', None) if _scoring == "dx" else getattr(self, '_standard_store', None)
                if _store:
                    _store.save_ratio(
                        self.settings.band, self.settings.mode,
                        ratio=self._diversity_ctrl.ratio,
                        dominant=self._diversity_ctrl.dominant,
                    )
                # Rückwärtskompatibilität
                self.settings.save_diversity_preset(
                    mode=self.settings.mode,
                    band=self.settings.band,
                    ratio=self._diversity_ctrl.ratio,
                    dominant=self._diversity_ctrl.dominant,
                )
                cq_freq = self._diversity_ctrl.get_free_cq_freq()
                if cq_freq:
                    self.encoder.audio_freq_hz = cq_freq
                    print(f"[Diversity] Einmessen fertig — CQ auf {cq_freq} Hz")
                else:
                    print("[Diversity] Einmessen fertig — CQ freigegeben")
                self.control_panel.update_freq_histogram(
                    self._diversity_ctrl.get_histogram_data()
                )
        elif self._diversity_ctrl.phase == "measure":
            self._diversity_in_operate = False

    def _handle_diversity_operate(self, messages, ant):
        """Diversity-Operate-Phase: Stationen akkumulieren + Stats-Logging."""
        qso_busy = self.qso_sm.state not in (
            QSOState.IDLE, QSOState.TIMEOUT,
            QSOState.CQ_CALLING, QSOState.CQ_WAIT,
        )

        # Diversity: gemeinsame Akkumulation mit Antennen-Info
        changed, comparisons = accumulate_stations(
            self._diversity_stations, messages,
            self._active_qso_targets, antenna=ant)

        # Histogramm + Freq-Suche kommen jetzt aus _refresh_diversity_freq_view
        # (laeuft slot-synchron in _on_cycle_decoded, unabhaengig von messages)

        # Stationen pro Antenne — immer berechnen (nicht nur bei changed)
        a1_msgs = [m for m in self._diversity_stations.values()
                   if getattr(m, 'antenna', '').startswith('A1')]
        a2_msgs = [m for m in self._diversity_stations.values()
                   if getattr(m, 'antenna', '').startswith('A2')]
        ant2_wins = sum(1 for m in self._diversity_stations.values()
                        if getattr(m, 'antenna', '').startswith('A2>'))
        ant1_wins = sum(1 for m in self._diversity_stations.values()
                        if getattr(m, 'antenna', '').startswith('A1>'))
        compared = ant1_wins + ant2_wins
        # DX: schwache Signale (-20 < SNR < -10) pro Antenne
        a1_weak = [m for m in a1_msgs if m.snr is not None and m.snr < -10]
        a2_weak = [m for m in a2_msgs if m.snr is not None and m.snr < -10]

        # Tabelle neu aufbauen wenn sich was geaendert hat
        if changed:
            self.rx_panel.table.setRowCount(0)
            for m in self._diversity_stations.values():
                self.rx_panel.add_message(m)
            self.rx_panel.reapply_sort()
            only_a1 = sum(1 for m in self._diversity_stations.values()
                          if getattr(m, 'antenna', '') == 'A1')
            only_a2 = sum(1 for m in self._diversity_stations.values()
                          if getattr(m, 'antenna', '') == 'A2')
            total = len(self._diversity_stations)
            pct = round(100 * ant2_wins / compared) if compared else 0
            print(f"[Diversity] {total} St. | A1>A2: {ant1_wins} | "
                  f"A2>A1: {ant2_wins} ({pct}%) | "
                  f"Nur A1: {only_a1} | Nur A2: {only_a2}")
            # Antenna Preference Store aktualisieren
            if hasattr(self, '_antenna_prefs'):
                self._antenna_prefs.update_from_stations(self._diversity_stations)

        # Counts immer aktualisieren — auch wenn changed=False (Modus-Wechsel fix)
        self.control_panel.update_diversity_counts(
            len(a1_msgs), len(a2_msgs),
            scoring_mode=self._diversity_ctrl.scoring_mode,
            ant2_wins=ant2_wins, total_compared=compared,
            a1_weak_count=len(a1_weak), a2_weak_count=len(a2_weak))

        self.control_panel.update_decode_count(
            len(self._diversity_stations)
        )

        # Statistik loggen — avg_snr + ant2_wins + SNR-Delta
        _delta_vals = [
            m._snr_a2 - m._snr_a1
            for m in self._diversity_stations.values()
            if getattr(m, 'antenna', '') in ('A1>2', 'A2>1')
            and getattr(m, '_snr_a2', None) is not None
            and getattr(m, '_snr_a1', None) is not None
        ]
        _snr_delta = sum(_delta_vals) / len(_delta_vals) if _delta_vals else 0.0
        _all_snrs = [m.snr for m in self._diversity_stations.values()
                     if m.snr is not None]
        _avg_snr = round(sum(_all_snrs) / len(_all_snrs)) if _all_snrs else -30
        _stats_logged = self._log_stats(len(self._diversity_stations), messages,
                                        avg_snr=_avg_snr, ant2_wins=ant2_wins, snr_delta=_snr_delta)
        if _stats_logged and comparisons:
            scoring = getattr(self._diversity_ctrl, 'scoring_mode', 'normal')
            self._stats_logger.log_station_comparisons(
                self.settings.band, self.settings.mode, scoring, comparisons)

    def _handle_normal_mode(self, messages):
        """Normal-Modus: gemeinsame Akkumulation ohne Antennen-Info + Stats."""
        if messages:
            changed, _ = accumulate_stations(
                self._normal_stations, messages,
                self._active_qso_targets, antenna="")
            if changed:
                self.rx_panel.table.setRowCount(0)
                for m in self._normal_stations.values():
                    self.rx_panel.add_message(m)
                self.rx_panel.reapply_sort()
            self._update_histogram(messages)
        self.control_panel.update_decode_count(len(self._normal_stations))
        avg_snr = -30
        if self._normal_stations:
            avg_snr = round(sum(m.snr for m in self._normal_stations.values()) / len(self._normal_stations))
            self.control_panel.update_snr(avg_snr)

        # Statistik loggen — auch bei leerem Zyklus (akkumulierter Stand)
        self._log_stats(len(self._normal_stations), messages or [], avg_snr=avg_snr)

    def _handle_dx_tune_mode(self, messages):
        """DX-Tuning-Modus: nur aktueller Zyklus, keine Akkumulation."""
        self.rx_panel.table.setRowCount(0)
        for msg in messages:
            self.rx_panel.add_message(msg)
        self.rx_panel.reapply_sort()

    def _run_ap_lite_rescue(self, messages):
        """AP-Lite Rescue bei QSO-Decode-Fail (WAIT_REPORT / WAIT_RR73).

        Läuft nur wenn AP_LITE_ENABLED = True (Feldtest-Flag).
        """
        if not (self._ap_lite.enabled and self.qso_sm.qso):
            return
        _state = self.qso_sm.state
        if _state not in (QSOState.WAIT_REPORT, QSOState.WAIT_RR73):
            return
        _their = self.qso_sm.qso.their_call
        _freq = float(getattr(self.qso_sm.qso, 'freq_hz',
                             self.encoder.audio_freq_hz) or self.encoder.audio_freq_hz)
        _qso_state_int = 1 if _state == QSOState.WAIT_REPORT else 2
        _partner_found = any(
            getattr(m, 'caller', '') == _their for m in (messages or [])
        )
        if _partner_found or self.decoder.last_pcm_12k is None:
            return
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

    def _run_auto_hunt(self, messages):
        """Auto-Hunt: automatisch CQ-Stationen anrufen (verstecktes Feature)."""
        if not self._auto_hunt.active:
            return
        _idle = self.qso_sm.state in (QSOState.IDLE, QSOState.TIMEOUT)
        _candidate = self._auto_hunt.select_next(
            messages=messages or [],
            qso_idle=_idle,
            presence_ok=self.presence_can_tx(),
        )
        if not _candidate:
            return
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

                # Smart Antenna: waehrend QSO auf beste Antenne forcieren
                _in_qso = self.qso_sm.state not in (
                    QSOState.IDLE, QSOState.TIMEOUT,
                    QSOState.CQ_CALLING, QSOState.CQ_WAIT,
                )
                pref_ant = None
                if _in_qso and self.qso_sm.qso.their_call and hasattr(self, '_antenna_prefs'):
                    pref_ant = self._antenna_prefs.get(self.qso_sm.qso.their_call)

                if pref_ant:
                    self._diversity_current_ant = pref_ant
                    if not getattr(self, '_pref_logged', False):
                        print(f"[Antenna] QSO mit {self.qso_sm.qso.their_call} "
                              f"→ Praeferenz {pref_ant} (besserer SNR)")
                        self._pref_logged = True
                else:
                    self._diversity_current_ant = self._diversity_ctrl.choose()
                    if getattr(self, '_pref_logged', False):
                        print(f"[Antenna] QSO beendet → zurueck zu Diversity-Rhythmus")
                        self._pref_logged = False

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

    def _update_histogram(self, messages):
        """Histogram + vorgeschlagene TX-Freq aktualisieren (Normal-Modus)."""
        # 1:1 aus aktuellem RX-Fenster (station_accumulator, inkl. Aging)
        self._diversity_ctrl.sync_from_stations(self._normal_stations)
        qso_busy = self.qso_sm.state not in (
            QSOState.IDLE, QSOState.TIMEOUT,
            QSOState.CQ_CALLING, QSOState.CQ_WAIT,
        )
        self._diversity_ctrl.update_proposed_freq(qso_active=qso_busy)
        self.control_panel.update_freq_histogram(
            self._diversity_ctrl.get_histogram_data())

    def _is_antenna_tuning_active(self) -> bool:
        """Prueft ob RF-Tuning, Radio-Suche oder Diversity-Einmessphase aktiv.

        Waehrend Einmessphase wird je Zyklus nur EINE Antenne gemessen —
        Stats waeren verfaelscht (fehlende Stationen der anderen Antenne).
        """
        if not getattr(self.radio, 'ip', None):
            return True
        if self._rx_mode == "dx_tuning":
            return True
        if (self._rx_mode == "diversity"
                and hasattr(self, '_diversity_ctrl')
                and self._diversity_ctrl is not None
                and self._diversity_ctrl.phase == "measure"):
            return True
        return False

    def _log_stats(self, station_count: int, messages, avg_snr: float = -30,
                   ant2_wins: int = 0, snr_delta: float = 0.0) -> bool:
        """Empfangsstatistik loggen — alle Modi, pausiert bei Tuning + Warmup.

        Returns True wenn wirklich geloggt wurde.
        """
        if not hasattr(self, '_stats_logger') or self._stats_logger is None:
            return False
        if not self.settings.get("stats_enabled", True):
            return False
        # Nur Kelemen-Baender aufzeichnen (10m/15m/20m)
        from core.diversity_cache import SUPPORTED_BANDS
        if self.settings.band not in SUPPORTED_BANDS:
            _lbl = getattr(self, '_stats_indicator', None)
            if _lbl:
                _lbl.setStyleSheet("color: #555; font-family: Menlo; font-size: 11px; padding: 0 6px;")
            return False
        # Warmup: N Zyklen nach Band-/Moduswechsel keine Stats (faire Baseline)
        if getattr(self, '_stats_warmup_cycles', 0) > 0:
            remaining = self._stats_warmup_cycles
            self._stats_warmup_cycles -= 1
            print(f"[Stats] Warmup — {remaining} Zyklen verbleibend (Band={self.settings.band})")
            _lbl = getattr(self, '_stats_indicator', None)
            if _lbl:
                _lbl.setStyleSheet("color: #555; font-family: Menlo; font-size: 11px; padding: 0 6px;")
            return False
        # Tuning aktiv → pausieren (keine verfaelschten Daten)
        if self._is_antenna_tuning_active():
            _lbl = getattr(self, '_stats_indicator', None)
            if _lbl:
                _lbl.setStyleSheet("color: #555; font-family: Menlo; font-size: 11px; padding: 0 6px;")
            return False
        # CQ oder aktives QSO → pausieren (nur 1 Slot RX, Statistik wäre verzerrt)
        # Robuster Check: State-Machine UND UI-Button — falls cq_mode durch Bug False ist
        _qsm = getattr(self, 'qso_sm', None)
        _cp = getattr(self, 'control_panel', None)
        _cq_btn = getattr(_cp, 'btn_cq', None) if _cp else None
        _cq_ui = _cq_btn is not None and _cq_btn.isChecked()
        if _qsm and (_cq_ui or _qsm.cq_mode or _qsm.state not in (QSOState.IDLE, QSOState.TIMEOUT)):
            return False
        from core.station_stats import get_active_protocol, get_active_reception_mode
        protocol = get_active_protocol(self.settings.mode)
        if protocol is None:
            return False
        scoring = getattr(self._diversity_ctrl, 'scoring_mode', 'normal')
        rx_mode_str = get_active_reception_mode(self._rx_mode, scoring)
        if rx_mode_str is None:
            return False
        self._stats_logger.log_cycle(
            station_count=station_count,
            avg_snr=avg_snr,
            band=self.settings.band,
            ft_mode=protocol,
            rx_mode=rx_mode_str,
            ant2_wins=ant2_wins if self._rx_mode == "diversity" else 0,
            snr_delta=snr_delta if self._rx_mode == "diversity" else 0.0,
        )
        # Indikator gruen: Daten wurden gerade geschrieben
        _lbl = getattr(self, '_stats_indicator', None)
        if _lbl:
            _lbl.setStyleSheet("color: #00CC44; font-family: Menlo; font-size: 11px; padding: 0 6px;")
        return True

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
