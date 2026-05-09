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

# P2.OMNI-PATTERN-FIX (v0.95.24): Mid-Cycle-Pretrigger-Schwelle.
# Encoder schlaeft bis next_boundary - 1.3s (TARGET_TX_OFFSET) und
# braucht von dort sleep_dur > 0 — sonst greift v0.80 Fix B Drift-
# Schutz und schiebt TX um 2 Slots. Wir triggern _send_cq mid-cycle
# bei cycle_pos > duration - PRETRIGGER_OFFSET → encoder hat sleep
# Vorlauf > 0. 1.3s = FlexRadio-TX-Buffer-Latenz (= |TARGET_TX_OFFSET|).
_OMNI_PRETRIGGER_OFFSET_S = 1.3


def compute_local_conditions(stations: dict) -> tuple[int, int, float]:
    """P1.19/P1.21: 5-Sterne-Empfang-Score aus Stations-Dict.

    Returnt (score 1-5, n_stations, median_snr_top_half).
    Score nur SNR-basiert (Mike's Funker-Logik: Anzahl ohne dB-Werte ist
    irrelevant — 50 Stationen bei -25 dB sind kein guter Empfang):
      5 ★: Median-SNR > -10 dB (sehr gut)
      4 ★: Median-SNR > -14 dB (gut)
      3 ★: Median-SNR > -18 dB (maessig)
      2 ★: Median-SNR > -22 dB (schlecht)
      1 ★: alles darunter (sehr schlecht / kein Signal)
    """
    if not stations:
        return 1, 0, -99.0
    snrs = sorted(
        [float(s.snr) for s in stations.values()
         if hasattr(s, 'snr') and s.snr is not None],
        reverse=True,
    )
    n = len(snrs)
    if n == 0:
        return 1, 0, -99.0
    top_half = snrs[:max(1, n // 2)]
    median = top_half[len(top_half) // 2] if top_half else -99.0
    if median > -10:
        return 5, n, median
    if median > -14:
        return 4, n, median
    if median > -18:
        return 3, n, median
    if median > -22:
        return 2, n, median
    return 1, n, median


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

        # v0.94: waehrend Phase 2 (DXTuneDialog) zaehlt die Hardware-Antenne
        # aus _schedule[_step], nicht das Diversity-Pattern. Sonst falsche
        # Antennen-Markierung im RX-Panel + accumulate_stations
        # (Mike's Screenshot 2026-05-05: CU2JX als A1 obwohl ANT2 G20 lief).
        ant = self._resolve_hardware_antenna(ant)

        # P3 v0.95.20: Audio-Dump fuer Debug/Forschung. Pull-Pattern aus
        # GUI-Thread → Antenne ist garantiert korrekt fuer den just-decoded
        # Slot (kein Race mit Decoder-Thread). Modus-Filter (nur FT8) im
        # Decoder.dump_last_slot. Default-Root: SimpleFT8/audio_dump/.
        if getattr(self, "_audio_dump_enabled", False):
            from core.audio_dump import DEFAULT_DUMP_ROOT
            ant_long = "ANT1" if ant == "A1" else "ANT2"
            self.decoder.dump_last_slot(
                ant_long, DEFAULT_DUMP_ROOT,
                getattr(self, "_audio_dump_max_files", 200),
            )

        if self._rx_mode == "diversity" and was_phase == "measure":
            self._handle_diversity_measure(messages, ant)

        if self._rx_mode == "diversity" and messages:
            self._handle_diversity_operate(messages, ant)
        elif self._rx_mode == "normal":
            self._handle_normal_mode(messages)
        elif messages:
            self._handle_dx_tune_mode(messages)

        # v0.82 Fix E: on_decoder_finished wird NICHT mehr hier aufgerufen.
        # Qt-FIFO sendet cycle_decoded VOR message_decoded → on_decoder_finished
        # liefe sonst VOR den State-Wechseln durch on_message_received
        # (Doppel-Report-Bug v0.81). Stattdessen haengt on_decoder_finished
        # am neuen `cycle_finished`-Decoder-Signal — siehe `_on_cycle_finished`.

        # Slot-synchroner Such-Trigger + Histogramm-Refresh JEDEN Slot
        # (unabhaengig von messages-Inhalt — _diversity_stations mit Aging ist
        # Quelle der Wahrheit). Das fixt P1 (Histogramm-Update Guard) gleich mit.
        if self._rx_mode == "diversity" and was_phase == "operate":
            self._refresh_diversity_freq_view()

        if self._dx_tune_dialog is not None:
            self._dx_tune_dialog.feed_cycle(messages)

        self._run_ap_lite_rescue(messages)
        self._run_auto_hunt(messages)

    @Slot()
    def _on_cycle_finished(self):
        """v0.82 Fix E — Slot-Ende-Hook NACH allen Decoder-Messages.

        Wird vom Decoder ueber das `cycle_finished`-Signal aufgerufen,
        NACHDEM alle message_decoded-Emissions verarbeitet sind. Damit
        laeuft `on_decoder_finished` nach den State-Wechseln durch
        on_message_received → Doppel-Report-Bug v0.81 verhindert.

        Reihenfolge im GUI-Thread (Qt-FIFO pro Sender=Decoder):
        1. _on_cycle_decoded(messages) — Aggregation, _assign_slot_parity
        2. Pro msg: on_message_decoded(msg) → on_message_received → state-Wechsel
        3. _on_cycle_finished() → on_decoder_finished sieht finalen state ✓
        """
        if not self.rx_panel._rx_active:
            return
        self.qso_sm.on_decoder_finished()

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
        """Slot-Parity respektieren — Decoder hat sie bereits gesetzt.

        Der Decoder setzt seit V3-Slot-Fix latenz-frei
        ``m._slot_start_ts`` und ``m._tx_even`` aus der Wake-Zeit. Diese
        Werte sind robust gegen Sleep-Drift, Audio-Buffer-Lag und
        Qt-Signal-Queue-Latenz.

        Fallback nur fuer Test-Mocks ohne echten Decoder oder fuer
        Messages aus alternativen Quellen (z.B. AP-Lite-Rescue).
        """
        if not messages:
            return
        fallback_even = self.timer.is_even_cycle()
        fallback_now = ntp_time.get_time()
        slot = self.timer.cycle_duration
        fallback_slot_start = int(fallback_now / slot) * slot
        for m in messages:
            if not hasattr(m, '_tx_even'):
                m._tx_even = fallback_even
            if not hasattr(m, '_slot_start_ts'):
                m._slot_start_ts = fallback_slot_start

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
        # Phase-Diff: erkennt measure→operate Uebergang fuer GUI-Lock-Aufhebung
        old_phase = self._diversity_ctrl.phase
        with self._diversity_lock:
            self._diversity_ctrl.record_measurement(
                ant, score,
                station_count=station_count,
                avg_snr=avg_snr,
                dx_weak_count=weak_count,
            )
            self._diversity_ctrl.sync_from_stations(self._diversity_stations)
            self._diversity_ctrl.update_proposed_freq()
        # GUI-Lock weg sobald Re-Measurement durch ist (8 Slots → _evaluate)
        if old_phase == "measure" and self._diversity_ctrl.phase == "operate":
            self._set_gain_measure_lock(False)
            self._set_cq_locked(False)
            print("[Diversity] Phase=operate — GUI-Lock aufgehoben")
        # Histogram LIVE aktualisieren (auch waehrend Messung)
        self.control_panel.update_freq_histogram(
            self._diversity_ctrl.get_histogram_data())
        self.control_panel.update_diversity_ratio(
            self._diversity_ctrl.ratio, self._diversity_ctrl.phase,
            measure_step=self._diversity_ctrl.measure_step,
            measure_total=self._diversity_ctrl.MEASURE_CYCLES,
            operate_seconds_remaining=self._diversity_ctrl.seconds_until_remeasure,
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
                # Cache-Schutz (v0.91 #8 R1.4): Adaptiv-Stop-Ratios NICHT persistieren —
                # weniger Messdaten → potenziell ungenauer, soll nicht ueber 6h Cache-
                # Validity hinweg verwendet werden.
                _early_stopped = getattr(self._diversity_ctrl, '_was_early_stopped', False)
                _scoring = getattr(self._diversity_ctrl, 'scoring_mode', 'normal')
                _store = getattr(self, '_dx_store', None) if _scoring == "dx" else getattr(self, '_standard_store', None)
                if _store and not _early_stopped:
                    _store.save_ratio(
                        self.settings.band, self.settings.mode,
                        ratio=self._diversity_ctrl.ratio,
                        dominant=self._diversity_ctrl.dominant,
                    )
                elif _early_stopped:
                    print("[mw_cycle] Adaptiv-Stop-Ratio NICHT gecached "
                          "(weniger Messdaten als regulaerer Pfad)")
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

    def _feed_locator_db(self, messages):
        """Decoder-Hook: pro is_grid-Message Locator in die Locator-DB pushen.

        Greift sowohl bei CQ ("CQ R9CA LO97" → R9CA/LO97) als auch bei
        Antworten mit Locator ("RA4ALY DL6YJB JO31" → DL6YJB/JO31).
        caller=field2 ist immer der Sender. Die DB priorisiert intern:
        cq_6 > psk_6 > qso_log_6 > _4-Varianten.
        """
        db = getattr(self, "locator_db", None)
        if db is None or not messages:
            return
        for m in messages:
            try:
                # is_grid ist Property (nicht callable) — kein () !
                # is_rr73 zuerst pruefen: 'RR73' matcht is_grid struktur-
                # gleich (Letter+Letter+Digit+Digit), ist aber Bestaetigung
                # nicht Locator.
                if m.is_grid and not m.is_rr73 and m.field3 != "73":
                    db.set(m.caller, m.field3, "cq")
            except AttributeError:
                continue

    def _feed_rx_history(self, messages, antenna: str = "") -> None:
        """Decoder-Hook: pro Decode einen RxEntry in den RX-History-Cache.

        None-safe: wenn rx_history_store noch nicht initialisiert (frueher
        Cycle waehrend App-Start), silent return — kein Crash.

        Pro Empfang ein Entry mit aktuellem Locator (falls msg ein Grid
        traegt) bzw None (wird beim Karten-Open via locator_db ergaenzt).
        Antenne wird durchgereicht: Diversity uebergibt 'A1'/'A2', Normal
        haengt 'A1' an (Mike-Konvention v0.70).
        """
        store = getattr(self, "rx_history_store", None)
        if store is None or not messages:
            return
        from core.rx_history import RxEntry
        import time as _t
        band = self.settings.band
        mode = self.settings.mode
        now = _t.time()
        for m in messages:
            try:
                if m.is_grid and not m.is_rr73 and m.field3 != "73":
                    loc = m.field3
                else:
                    loc = None
            except AttributeError:
                loc = None
            try:
                entry = RxEntry(
                    ts=now,
                    call=m.caller,
                    locator=loc,
                    snr=float(m.snr),
                    antenna=antenna or getattr(m, "antenna", "") or "",
                    freq_hz=int(m.freq_hz),
                )
            except (AttributeError, TypeError, ValueError):
                continue
            store.add_entry(band, mode, entry)

    def _handle_diversity_operate(self, messages, ant):
        """Diversity-Operate-Phase: Stationen akkumulieren + Stats-Logging."""
        self._feed_locator_db(messages)
        self._feed_rx_history(messages, antenna=ant)
        qso_busy = self.qso_sm.state not in (
            QSOState.IDLE, QSOState.TIMEOUT,
            QSOState.CQ_CALLING, QSOState.CQ_WAIT,
        )

        # Diversity: gemeinsame Akkumulation mit Antennen-Info
        changed, comparisons = accumulate_stations(
            self._diversity_stations, messages,
            self._active_qso_targets, antenna=ant,
            slot_duration_s=self.timer.cycle_duration)

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

        # Richtungs-Karten-Hook: Snapshot via Qt.QueuedConnection in GUI-Thread
        self._emit_map_snapshot_if_open()

    def _handle_normal_mode(self, messages):
        """Normal-Modus: gemeinsame Akkumulation + Stats. Ant-Spalte zeigt 'A1'
        (Normal-Modus laeuft immer ueber ANT1, siehe mw_radio._apply_normal_mode)."""
        self._feed_locator_db(messages)
        self._feed_rx_history(messages, antenna="A1")
        if messages:
            changed, _ = accumulate_stations(
                self._normal_stations, messages,
                self._active_qso_targets, antenna="A1",
                slot_duration_s=self.timer.cycle_duration)
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

        # P1.19: Sterne-Anzeige (immer aktualisieren, auch bei leerem Slot)
        stations = (self._diversity_stations
                    if self._rx_mode == "diversity"
                    else self._normal_stations)
        score, n_st, median = compute_local_conditions(stations)
        self.control_panel.update_local_conditions(score, n_st, median)

        # Richtungs-Karten-Hook: Snapshot via Qt.QueuedConnection in GUI-Thread
        self._emit_map_snapshot_if_open()

    def _handle_dx_tune_mode(self, messages):
        """DX-Tuning-Modus: nur aktueller Zyklus, keine Akkumulation.

        v0.79-Fix: Antenne vom aktiven dx_tune_dialog ablesen statt
        Default „A1" — Hardware schaltet zwischen ANT1/ANT2, das soll auch
        in der RX-Tabelle sichtbar sein.
        """
        current_ant = "A1"
        if self._dx_tune_dialog is not None:
            try:
                ant, _gain = self._dx_tune_dialog._schedule[
                    self._dx_tune_dialog._step]
                current_ant = ant
            except (IndexError, AttributeError):
                pass
        self.rx_panel.table.setRowCount(0)
        for msg in messages:
            msg.antenna = current_ant
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
            their_snr=_candidate.snr,  # P1.HUNT-SNR (v0.95.21)
        )

    @Slot(float, float)
    def _on_cycle_tick(self, seconds_in_cycle: float, cycle_duration: float):
        if not self.rx_panel._rx_active:
            return
        self.control_panel.update_cycle_bar(seconds_in_cycle, cycle_duration)
        # P2.OMNI-PATTERN-FIX (v0.95.24): Mid-Cycle-Pretrigger fuer OMNI.
        # Loest _send_cq fuer den NAECHSTEN Slot bei cycle_pos > dur-1.3s
        # aus, sodass Encoder Sleep-Vorlauf hat und kein v0.80 Drift-Schutz
        # triggert. Pattern bleibt korrekt.
        self._omni_pretrigger_check(seconds_in_cycle, cycle_duration)

    def _omni_pretrigger_fire_impl(self) -> None:
        """Pretrigger-Logik — gemeinsam fuer QTimer-Pfad UND
        Cycle-Tick-Fallback.

        P3.OMNI-PATTERN-FIX-2 (v0.95.25): Wird primaer vom QTimer
        ausgeloest (in main_window._on_cycle_start gestartet, exakt zur
        Schwelle dur-1.3s). Cycle-Tick-Pfad (_omni_pretrigger_check) ruft
        diese Methode als Fallback wenn QTimer ausnahmsweise nicht
        gefeuert hat.

        Idempotent ueber _omni_pretriggered-Flag — wer zuerst feuert,
        gewinnt; der andere returnt.

        Pre-Conds (alle Bedingungen muessen wahr sein):
        - Reentrancy-Flag _omni_pretriggered=False
        - OMNI active + nicht paused
        - cq_mode (sonst keine CQ-Loop)
        - state in IDLE/CQ_WAIT/CQ_CALLING (kein QSO laufend)
        """
        if self._omni_pretriggered:
            return
        if not self._omni_tx.active or self._omni_tx.is_paused():
            return
        if not self.qso_sm.cq_mode:
            return
        if self.qso_sm.state not in (QSOState.IDLE, QSOState.CQ_WAIT,
                                      QSOState.CQ_CALLING):
            return
        # Pretrigger ausfuehren (atomar via Flag)
        self._omni_pretriggered = True
        next_idx, next_block, target_even, is_tx = self._omni_tx.peek_next()
        if not is_tx:
            # RX-Slot: Pattern-Slot wird via advance() in _on_cycle_start
            # weitergerueckt, kein _send_cq. Flag bleibt True (verhindert
            # Re-Trigger im selben Cycle), wird in _on_cycle_start reset.
            return
        # TX-Slot: Encoder hat Sleep-Vorlauf (sleep_dur > 0)
        self.encoder.tx_even = target_even
        # Pretrigger-Flag in qso_sm setzen damit on_cycle_end im naechsten
        # Slot KEIN doppeltes _send_cq triggert (V3 §2.5).
        self.qso_sm._was_pretriggered = True
        self.qso_sm._send_cq()
        print(f"[OMNI-Pretrigger] Pos {next_idx} Block {next_block} "
              f"target_even={target_even}")

    def _omni_pretrigger_check(self, sic: float, dur: float) -> None:
        """Cycle-Tick-Fallback fuer OMNI-Pretrigger.

        P3.OMNI-PATTERN-FIX-2 (v0.95.25): PRIMAER laeuft Pretrigger via
        QTimer (in main_window._on_cycle_start gestartet, Qt.PreciseTimer
        garantiert ~50ms Genauigkeit). Dieser Cycle-Tick-Pfad ist
        Defense-in-Depth fuer den Fall dass QTimer aus irgendeinem
        Grund nicht gefeuert hat (extreme Eventloop-Verzoegerung,
        Bug in QTimer-Lifecycle).

        Fallback-Schwelle ist deshalb spaet (dur - 0.5s): wenn QTimer
        aktiv waere, hat er bei dur - 1.3s bereits gefeuert +
        _omni_pretriggered=True gesetzt → return. Dieser Pfad greift
        nur wenn das nicht passiert ist.
        """
        if self._omni_pretriggered:
            return  # QTimer hat schon gefeuert (Normalfall)
        if not self._omni_tx.active or self._omni_tx.is_paused():
            return
        if not self.qso_sm.cq_mode:
            return
        if self.qso_sm.state not in (QSOState.IDLE, QSOState.CQ_WAIT,
                                      QSOState.CQ_CALLING):
            return
        fallback_threshold = dur - 0.5  # Notfall-Schwelle
        if sic < fallback_threshold:
            return
        print(f"[OMNI-Pretrigger-FALLBACK] cycle_pos={sic:.2f}s — "
              f"QTimer hat NICHT gefeuert!")
        self._omni_pretrigger_fire_impl()

    @Slot(int, bool)
    def _on_cycle_start(self, cycle_num: int, is_even: bool):
        # P2.OMNI-PATTERN-FIX (v0.95.24): Pretrigger-Flag fuer naechsten
        # Cycle reset. Erstes _on_cycle_tick im neuen Slot kann dann
        # wieder pretriggern (sobald Schwelle erreicht).
        self._omni_pretriggered = False

        # P3.OMNI-PATTERN-FIX-2 (v0.95.25): QTimer fuer Mid-Cycle-Pretrigger.
        # Mathematik (V2 L2): Pretrigger soll bei cycle_pos = dur - 1.3s
        # feuern. Encoder berechnet sleep_dur = next_boundary +
        # TARGET_TX_OFFSET (-0.8) - 0.5 - now. Bei cycle_pos = dur - 1.3
        # ist sleep_dur = 0 — exakt an der Sicherheitsgrenze. Sicheres
        # Fenster fuer Pretrigger: [dur-1.3, dur-0.8] = 500ms breit.
        # Qt.PreciseTimer trifft das ~50ms genau (vs >1500ms bei
        # cycle_tick-Signal-Queue wenn Decoder GUI-Thread blockiert).
        # start() nach start() ersetzt alten Timeout (Restart-Semantik).
        if self._omni_tx.active and not self._omni_tx.is_paused():
            delay_ms = int((self.timer.cycle_duration -
                            _OMNI_PRETRIGGER_OFFSET_S) * 1000)
            self._omni_pretrigger_timer.start(delay_ms)

        # ── Anzeige zurücksetzen wenn kein TX ──────────────────
        if not self.encoder.is_transmitting:
            self.control_panel.update_tx_peak(0.0)

        # ── Auto TX Level Regelung ──────────────────────────────
        if self._fwdpwr_samples:
            self._auto_adjust_tx_level()

        self.qso_sm.on_cycle_end()

        # OMNI-TX: pro Zyklus voranschreiten (P2.OMNI-REDESIGN v4.0).
        # Wenn pausiert (QSO laeuft via _pause_omni_if_active): _slot_index
        # friert ein, kein advance. Block-Switch jetzt automatisch bei
        # rollover (slot_index 4→0) — kein 80-Counter mehr.
        if not self._omni_tx.is_paused():
            self._omni_tx.advance()

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

                # Betriebszyklus zaehlen + ggf. neu messen (v0.93: zeit-basiert)
                if self._diversity_ctrl.phase == "operate":
                    self._diversity_ctrl.on_operate_cycle()
                    # qso_active = echtes QSO laeuft (NICHT CQ-Ruf)
                    qso_active = self.qso_sm.state not in (
                        QSOState.IDLE, QSOState.TIMEOUT,
                        QSOState.CQ_CALLING, QSOState.CQ_WAIT,
                    )
                    # cq_active = CQ-Ruf laeuft (state ODER cq_mode-Flag)
                    cq_active = (
                        self.qso_sm.state in (QSOState.CQ_CALLING, QSOState.CQ_WAIT)
                        or getattr(self.qso_sm, 'cq_mode', False)
                    )
                    if self._diversity_ctrl.should_remeasure(qso_active, cq_active):
                        self._diversity_ctrl.start_measure()
                        self._set_cq_locked(True)
                        self.control_panel.update_diversity_ratio(
                            "50:50", "remeasure", 0,
                            self._diversity_ctrl.MEASURE_CYCLES,
                            scoring_mode=self._diversity_ctrl.scoring_mode)
                        print("[Diversity] Automatische Neueinmessung gestartet (1h-Frist abgelaufen)")

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
                    operate_seconds_remaining=self._diversity_ctrl.seconds_until_remeasure,
                    scoring_mode=self._diversity_ctrl.scoring_mode,
                )

            # BUG-3: ant_cmd + gain als Argumente, nicht als Closure
            def _switch(cmd=ant_cmd, g=gain):
                self.radio.set_rx_antenna(cmd)
                self.radio.set_rfgain(g)
            threading.Thread(target=_switch, daemon=True).start()

    def _update_histogram(self, messages):
        """Histogramm aktualisieren (Normal-Modus = Wasserfall-Ersatz).

        Im Normal-Modus laeuft KEINE automatische CQ-Frequenz-Suche
        (wie WSJT-X). Der User waehlt die TX-Frequenz manuell ueber
        Klick im Histogramm oder Spinbox. Hier nur Histogramm-Refresh
        damit der User sieht wo Lueck und Aktivitaet ist.
        """
        # 1:1 aus aktuellem RX-Fenster (station_accumulator, inkl. Aging)
        self._diversity_ctrl.sync_from_stations(self._normal_stations)
        # TX-Marker zeigt manuell gewaehlte Frequenz aus encoder
        hist_data = self._diversity_ctrl.get_histogram_data()
        hist_data['cq_freq'] = self.encoder.audio_freq_hz  # Marker = manuell
        self.control_panel.update_freq_histogram(hist_data)

    def _resolve_hardware_antenna(self, default_ant: str) -> str:
        """Liefert Antennen-Tag passend zur tatsaechlichen Hardware (v0.94).

        Im Normalfall: ``default_ant`` aus Diversity-Pop-Queue ("A1"/"A2").
        Bei aktivem DXTune-Dialog (Phase 2 Gain-Messung): Hardware-Antenne
        aus ``_schedule[_step]`` (z.B. "ANT2") → kurze Form "A2".

        Verhindert Mismatch zwischen Hardware-Antenne und Display/Stats:
        ``radio.set_rx_antenna()`` aus DXTuneDialog._start_step schaltet
        live, aber Diversity-Pattern liefert weiter "A1"/"A2" via
        ``choose()`` → Falsch-Markierung im RX-Panel.
        """
        dlg = getattr(self, '_dx_tune_dialog', None)
        if dlg is None:
            return default_ant
        try:
            ant_long, _gain = dlg._schedule[dlg._step]
        except (IndexError, AttributeError, TypeError):
            return default_ant
        return "A1" if ant_long == "ANT1" else "A2"

    def _is_antenna_tuning_active(self) -> bool:
        """Prueft ob RF-Tuning, Radio-Suche oder Diversity-Einmessphase aktiv.

        Waehrend Einmessphase wird je Zyklus nur EINE Antenne gemessen —
        Stats waeren verfaelscht (fehlende Stationen der anderen Antenne).

        v0.94 Bug-Fix: Phase 2 (DXTuneDialog) blockt Stats. Frueher wurde
        nur ``_rx_mode == "dx_tuning"`` geprueft — aber das wird im Code
        nirgendwo gesetzt. Folge bis v0.93: Stats wurden waehrend Phase 2
        weiter geloggt mit Diversity-Pattern-Antenne statt Hardware-
        Antenne (sichtbar im RX-Panel, ~0.3 % Daten-Bias).
        """
        if not getattr(self.radio, 'ip', None):
            return True
        if self._rx_mode == "dx_tuning":
            return True
        # v0.94: Phase 2 (Gain-Messung im DXTune-Dialog) blockt Stats
        if getattr(self, '_dx_tune_dialog', None) is not None:
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
        # Stats-Filter: aktive Liste der zu loggenden Baender (siehe
        # core/station_stats.py LOGGED_BANDS). Konsistent mit dem
        # eigentlichen Log-Filter in StationStats.log_cycle, damit der
        # _stats_indicator-Status korrekt ist (nicht gruen blinkt waehrend
        # log_cycle intern abbricht).
        from core.station_stats import StationStatsLogger
        if self.settings.band not in StationStatsLogger.LOGGED_BANDS:
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
            self.qso_panel.add_rx(
                msg.raw,
                tx_even=getattr(msg, '_tx_even', None),
                slot_start_ts=getattr(msg, '_slot_start_ts', None),
            )

        self.qso_sm.on_message_received(msg)
