"""SimpleFT8 MainWindow — TX-Regelung, Meter, SWR Mixin."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from PySide6.QtCore import Slot

if TYPE_CHECKING:
    from .main_window import MainWindow


class TXMixin:
    """Mixin fuer TX-Leistungsregelung — wird in MainWindow eingemischt.

    Enthaelt: Auto TX Level, Meter-Updates, SWR-Alarm, Power/Tune.
    """

    @Slot(int)
    def _on_power_changed(self, power: int):
        # 1. Race-Schutz: alte (band, watts)-Konvergenz speichern bevor sie verloren geht
        if self._rfpower_converged and not self._was_converged and self.radio is not None:
            old_watts = getattr(self, "_power_target", None)
            if old_watts:
                self.rf_preset_store.save(
                    self.radio.radio_type,
                    self.settings.band,
                    old_watts,
                    self._rfpower_current,
                )
                self._was_converged = True
        # 2. neuen Watt-Wert übernehmen
        self.settings.set("power_preset", power)
        self._power_target = power
        # 3. Preset für neuen Wert laden (oder Settings-Default)
        self._apply_rf_preset()
        # 4. Radio aktualisieren
        if self.radio.ip:
            self.radio.set_power(self._rfpower_current)

    def _apply_rf_preset(self):
        """Lädt RF-Preset für aktuelle (radio, band, watts) — None → Settings-Default.
        Setzt _rfpower_converged + _was_converged zurück (neuer Konvergenz-Zyklus).
        """
        if self.radio is None:
            self._rfpower_current = 50
            self._rfpower_converged = False
            self._was_converged = False
            return
        band = self.settings.band
        # `or`-Fallback nicht — `_power_target=0` wäre falsy aber semantisch invalid
        watts = getattr(self, "_power_target", None)
        if watts is None:
            watts = self.settings.get("power_preset", 10)
        saved = self.rf_preset_store.load(self.radio.radio_type, band, watts)
        if saved is not None:
            self._rfpower_current = saved
            print(f"[RF-Preset] geladen: {band}_{watts}W → rf={saved}")
        else:
            self._rfpower_current = self.settings.get_tx_power(band, default=50)
        self._rfpower_converged = False
        self._was_converged = False

    @Slot(bool)
    def _on_tune_clicked(self, on: bool):
        """Manueller TUNE-Toggle.

        P63 (v0.97.36): 10W fest, Dauer aus `tune_duration_s`-Setting
        (15 oder 30 s). Watchdog wird via `_tune_in_progress=True`
        bypasst. Nach Stop folgt 2s-Beruhigungs-Timer und SWR-Auswertung
        (`_tune_post_swr_check`) — bei SWR≤Limit wird der Band-Marker
        freigegeben + Diversity automatisch fortgesetzt.
        """
        if not self.radio.ip:
            return
        from PySide6.QtCore import QTimer
        from config.settings import get_tune_freq_mhz

        if on:
            # P63 AC5: 10W FEST (unabhängig von tune_power-Setting),
            # Dauer aus Setting mit Whitelist {15, 30}.
            TUNE_POWER_W = 10
            duration_s = self.settings.get("tune_duration_s", 15)
            if duration_s not in (15, 30):
                duration_s = 15

            # P63 AC4: Watchdog-Bypass VOR tune_on
            self._tune_in_progress = True

            # Tune-Frequenz aus TUNE_FREQS-Map (band+mode)
            tune_freq = get_tune_freq_mhz(self.settings.band, self.settings.mode)
            # _tune_active VOR set_frequency (verhindert Race mit Radio-Callback)
            self._tune_active = True
            if tune_freq is not None:
                self._tune_freq_mhz = tune_freq
                self.radio.set_frequency(tune_freq)
                print(f"[Tune] VFO temporaer auf {tune_freq * 1000:.3f} kHz "
                      f"({self.settings.band}/{self.settings.mode})")
            else:
                self._tune_freq_mhz = self.settings.frequency_mhz
                print(f"[Tune] Kein Offset-Wert fuer {self.settings.band}/{self.settings.mode} "
                      f"— tune auf Arbeitsfrequenz")

            self.radio.set_tx_antenna("ANT1")
            self.radio.set_rfpower_direct(TUNE_POWER_W)
            self.radio.tune_on()
            self._update_statusbar()
            self.statusBar().showMessage(
                f"TUNEN — {TUNE_POWER_W}W auf ANT1 für {duration_s}s ...", 0)
            display_freq = tune_freq if tune_freq is not None else self.settings.frequency_mhz
            self.control_panel.set_freq_display(display_freq, tune_active=True)
            print(f"[P63] Manueller TUNE — {TUNE_POWER_W}W {duration_s}s")

            # Auto-Stop nach Dauer mit Token-Re-Entry-Schutz
            self._tune_auto_stop_token = object()
            _token = self._tune_auto_stop_token
            QTimer.singleShot(
                duration_s * 1000,
                lambda: self._tune_stop(_token))
        else:
            # User-Toggle off → unbedingt stop (token=None)
            self._tune_stop(None)

    def _tune_stop(self, token):
        """TUNE beenden + 2s-Post-Check-Timer für SWR-Auswertung.

        P63 (v0.97.36) AC6/AC7 + R1-F1:
        - token=None → unbedingt (User-Toggle off)
        - token nicht aktuell → no-op (alter Auto-Stop nach neuem TUNE)
        - Sonst: tune_off + VFO+Power-Zurück + 2s-Timer für SWR-Check.
          Watchdog bleibt 2s bypassed (Beruhigungszeit gegen Pre-PTT-
          Glitches).
        """
        if token is not None and getattr(self, '_tune_auto_stop_token', None) is not token:
            return  # neuer TUNE-Click hat Token gewechselt
        if not self._tune_active:
            return  # schon manuell gestoppt

        from PySide6.QtCore import QTimer

        # tune_off + VFO+Power zurück
        self.radio.tune_off()
        self._tune_active = False
        self._tune_freq_mhz = None
        work_freq = self.settings.frequency_mhz
        self.radio.set_frequency(work_freq)
        self.radio.set_power(self.settings.get("power_preset", 15))
        self._update_statusbar()
        self.control_panel.set_freq_display(work_freq, tune_active=False)
        print(f"[Tune] VFO zurueck auf {work_freq * 1000:.3f} kHz")

        self.statusBar().showMessage(
            "TUNE beendet — prüfe SWR (2 s) ...", 2000)

        # P63 R1-F1: Post-Check-Token + 2s-Timer
        self._tune_post_check_token = object()
        _post = self._tune_post_check_token
        QTimer.singleShot(
            2000,
            lambda: self._tune_post_swr_check(_post))

    def _tune_post_swr_check(self, token):
        """P63 (v0.97.36) AC6/AC7 + R1-F1: 2s nach tune_off SWR auswerten.

        - SWR ≤ Limit → Marker discard + Diversity-Resume falls aktiv
        - SWR > Limit → Modal „Tuner konnte nicht matchen", Marker bleibt

        Watchdog wird hier wieder scharf gestellt (`_tune_in_progress=False`).
        Token-Pattern schützt vor Race bei schnellem Re-Tune.
        """
        if getattr(self, '_tune_post_check_token', None) is not token:
            return  # neuer TUNE-Click hat Token rotiert

        # Watchdog wieder scharf
        self._tune_in_progress = False

        if not self.radio.ip:
            return

        swr_now = self.radio.last_swr
        swr_limit = self.settings.get("swr_limit", 3.0)
        band = self.settings.band.upper()

        from PySide6.QtWidgets import QMessageBox

        if swr_now <= swr_limit:
            was_blocked = band in self._swr_blocked_bands
            self._swr_blocked_bands.discard(band)
            if was_blocked:
                self.qso_panel.add_info(
                    f"✓ Band {band} freigegeben — SWR {swr_now:.1f}")
                print(f"[P63] Marker freigegeben — {band} SWR {swr_now:.1f}")
                # AC6: Diversity automatisch fortsetzen (P62-Pause greift dann)
                if self._rx_mode == "diversity":
                    scoring = getattr(self._diversity_ctrl, 'scoring_mode', 'normal')
                    ft_mode = self.settings.mode
                    self._check_diversity_preset(self.settings.band, ft_mode, scoring)
            else:
                self.qso_panel.add_info(f"✓ TUNE OK — SWR {swr_now:.1f}")
        else:
            # AC7: Marker bleibt rot
            QMessageBox.warning(
                self,
                "Tuner konnte nicht matchen",
                f"SWR weiter {swr_now:.1f} > Limit {swr_limit:.1f}.\n\n"
                "Antenne prüfen oder TUNE wiederholen."
            )
        print(f"[P63] Post-TUNE — SWR {swr_now:.1f}, Limit {swr_limit:.1f}")

    def _abort_active_tx(self) -> None:
        """P60 (v0.97.32): TX sofort abbrechen + gepufferten Click verwerfen.

        Used by: User-Stop-Toggle (OMNI/Auto-Hunt/Normal-CQ) + HALT.
        NICHT used by: SWR-Watchdog (eigener Spike-Schutz-Flow),
        Bandwechsel/Mode-Wechsel (eigene Cleanup-Sequenzen mit
        zusätzlichen State-Stops).

        Antennen-neutral (kein set_tx_antenna — ANT1-Pflicht).
        No-op wenn encoder.is_transmitting=False (idempotent).
        ptt_off nur wenn radio.ip truthy (kein Crash bei disconnect).

        R1-V4-pro-F1: setzt _pending_station_click = None damit kein
        gepufferter Klick (Station-Click während TX) nach Stop ein
        ungewünschtes QSO startet. HALT-Pfad macht das bereits in
        _on_cancel — neue User-Stop-Pfade brauchen es auch.
        """
        if self.encoder.is_transmitting:
            self.encoder.abort()
            if self.radio.ip:
                self.radio.ptt_off()
        # F1 ROT: gepufferten Station-Klick verwerfen (post-stop QSO verhindern)
        if hasattr(self, "_pending_station_click"):
            self._pending_station_click = None

    @Slot(float)
    def _on_swr_alarm(self, swr: float):
        """P53: Live-SWR-Watchdog während TX.

        Feuert bei jedem VITA-49-Meter-Update wenn SWR ≥ Limit und
        FlexRadio._is_transmitting=True (radio/flexradio.py:1388). Auch
        von ptt_on() Pre-Check (Z.957) bevor TX überhaupt startet.

        Stop-Block läuft nur bei 2 aufeinanderfolgenden Alarms innerhalb
        500 ms (Spike-Schutz gegen PTT-on-Glitch) UND laufendem TX
        (encoder.is_transmitting=True).

        P63 (v0.97.36):
        - AC1: nach Stop _set_gain_measure_lock(False) (Bug-Fix
          Mike-17m: Lock hing nach Watchdog → UI dauerblockiert).
        - AC2/AC3: bei tuner_present=True Band-Marker setzen + Modal
          „Band gesperrt — bitte TUNE"; sonst klassisches „Antenne
          prüfen"-Modal ohne Marker.
        - AC4: Während manuellem TUNE komplett bypassed (early return).
        """
        from PySide6.QtWidgets import QMessageBox
        from core.qso_state import QSOState

        # P63 AC4: Während manuellem TUNE Watchdog komplett aus.
        if getattr(self, "_tune_in_progress", False):
            return

        # AC3: Pre-TX-Alarm aus ptt_on() ignorieren — kein laufender TX
        if not self.encoder.is_transmitting:
            self._swr_spike_count = 0
            return

        now = time.monotonic()

        # 1. Alarm ODER altes Fenster (> 500 ms) → neu starten
        if self._swr_spike_count == 0 or (now - self._swr_first_alarm_t) > 0.5:
            self._swr_spike_count = 1
            self._swr_first_alarm_t = now
            return

        # 2. Alarm innerhalb 500 ms — Stop auslösen
        # AC4(1): Reset SOFORT, gegen 3. Alarm noch in der Qt-Queue
        self._swr_spike_count = 0
        limit = self.settings.get("swr_limit", 3.0)

        # AC4(2)-(7): Stop-Block antennen-neutral (ANT1 bleibt ANT1)
        self.encoder.abort()
        if self.radio.ip:
            self.radio.ptt_off()
        # P60-F3 (v0.97.32): gepufferten Station-Click verwerfen
        # (verhindert ungewünschtes QSO nach SWR-Abbruch)
        if hasattr(self, "_pending_station_click"):
            self._pending_station_click = None
        if self.qso_sm.cq_mode or self.qso_sm.state != QSOState.IDLE:
            self.qso_sm.stop_cq()
            self.qso_sm.cancel()
            self.control_panel.set_cq_active(False)
        if hasattr(self, "_omni_cq") and self._omni_cq.is_active():
            self._omni_cq.stop("swr_block")
        if hasattr(self, "_auto_hunt") and self._auto_hunt.active:
            self._auto_hunt.stop_auto_hunt("swr_block")

        # P63 AC1: Lock-Release-Bug-Fix.
        # Vorher: _gain_measure_locked hing True wenn Watchdog während
        # Auto-TUNE/Gain-Mess feuerte → UI dauerblockiert.
        self._set_gain_measure_lock(False)

        # P63 AC2/AC3: Marker-Set bei tuner_present=True
        band = self.settings.band.upper()
        tuner = self.settings.get("tuner_present", True)
        if tuner:
            self._swr_blocked_bands.add(band)
            modal_title = "Band gesperrt — SWR zu hoch"
            modal_text = (
                f"Band {band} gesperrt — SWR {swr:.1f} > Limit {limit:.1f}.\n\n"
                "Bitte manuell durch TUNE-Vorgang freischalten."
            )
            panel_text = f"⚠ Band {band} gesperrt — SWR {swr:.1f}"
        else:
            modal_title = "SWR-Schutz ausgelöst"
            modal_text = (
                f"TX abgebrochen — SWR {swr:.1f} > Limit {limit:.1f}.\n\n"
                "Antenne prüfen."
            )
            panel_text = f"⚠ TX abgebrochen — SWR {swr:.1f}"

        # AC7: Panel-Eintrag VOR Modal (Modal blockiert Event-Loop)
        self.qso_panel.add_info(panel_text)

        print(f"[P53/P63] SWR-Watchdog: TX gestoppt — "
              f"SWR {swr:.1f} >= Limit {limit:.1f}, "
              f"marker={'set' if tuner else 'skip'} band={band}")

        # AC6: Modal
        QMessageBox.warning(self, modal_title, modal_text)

    def _auto_adjust_tx_level(self):
        """Zweistufige TX-Regelung (kein PI-Controller):
        Primaer:   rfpower → Ziel-Wattzahl (via FWDPWR-Feedback)
        Sekundaer: audio_level bei 0.75 halten (Clipschutz-Anker)
        Clipschutz: raw_peak >= 0.75 → audio NICHT erhoehen, rfpower hoch."""
        if not self._fwdpwr_samples:
            return
        samples = self._fwdpwr_samples[2:] if len(self._fwdpwr_samples) > 4 else self._fwdpwr_samples
        fwdpwr = sum(samples) / len(samples)
        self._fwdpwr_samples.clear()

        target = self._power_target
        if target <= 0 or fwdpwr < 0:
            return

        current_audio = self.radio.tx_audio_level
        raw_peak = self.radio.tx_raw_peak

        CLIP_LIMIT  = 0.75  # Audio-Ziel + Clipschutz-Grenze (max audio_level)
        AUDIO_STEP  = 0.05  # Schritt pro Zyklus (langsam = stabil)
        RF_STEP_MAX = 20    # Max rfpower-Sprung pro Zyklus (proportionale Regelung)

        new_audio   = current_audio
        new_rfpower = self._rfpower_current

        # Schritt 1: audio sofort auf CLIP_LIMIT begrenzen (nicht schrittweise!)
        if current_audio > CLIP_LIMIT:
            new_audio = CLIP_LIMIT

        # Schritt 2: Wattzahl-Regelung via rfpower (unabhaengig von raw_peak!)
        if fwdpwr < target * 0.95:
            # Audio kann erhoeht werden wenn: unter Limit UND raw_peak niedrig genug
            if new_audio < CLIP_LIMIT and raw_peak < CLIP_LIMIT:
                new_audio = min(CLIP_LIMIT, new_audio + AUDIO_STEP)
            else:
                # Audio am Limit ODER raw_peak zu hoch → rfpower erhoehen
                # Proportionale Schaetzung: rfpower * (target/fwdpwr), max +20 pro Zyklus
                if fwdpwr > 2:
                    estimated = int(self._rfpower_current * (target / fwdpwr))
                    step = max(5, min(RF_STEP_MAX, estimated - self._rfpower_current))
                else:
                    step = 10  # Kein Messwert → konservativer Sprung
                new_rfpower = min(100, self._rfpower_current + step)
        elif fwdpwr > target * 1.05:
            # Zu viele Watts: proportional reduzieren (symmetrisch zur Erhoehung)
            if fwdpwr > 2 and target > 0:
                estimated = int(self._rfpower_current * (target / fwdpwr))
                step = max(5, min(RF_STEP_MAX, self._rfpower_current - estimated))
            else:
                step = 5
            new_rfpower = max(10, self._rfpower_current - step)

        # rfpower anwenden wenn geaendert; bei Stabilität einmalig pro (band, watts) speichern
        if new_rfpower != self._rfpower_current:
            self._rfpower_current = new_rfpower
            self.radio.set_power(new_rfpower)
            self._rfpower_converged = False
            self._was_converged = False
        elif not self._was_converged:
            # Konvergenz erkannt: 1× speichern pro (band, watts)-Zyklus
            self._rfpower_converged = True
            self._was_converged = True
            band = self.settings.band
            watts = self._power_target
            self.rf_preset_store.save(
                self.radio.radio_type, band, watts, self._rfpower_current
            )
            self.settings.save_tx_power(band, self._rfpower_current)  # backward-compat

        # Audio anwenden wenn Aenderung > 1%
        if abs(new_audio - current_audio) >= 0.01:
            self.radio.set_tx_level(new_audio)
            slider_val = int(new_audio * 100)
            self.control_panel.tx_level_bar.setValue(slider_val)
            self.control_panel.tx_level_label.setText(f"TX-Pegel: {slider_val}%")
            band = self.settings.band
            band_levels = self.settings.get("tx_levels_per_band", {})
            band_levels[band] = slider_val
            self.settings.set("tx_levels_per_band", band_levels)

        # Anzeige immer aktualisieren
        self.control_panel.update_tx_peak(raw_peak if raw_peak > 0.01 else current_audio)
        self.control_panel.update_rfpower(self._rfpower_current)

        print(f"[AutoTX] {self.settings.band}: {fwdpwr:.0f}W/{target}W "
              f"raw={raw_peak:.2f} audio {current_audio:.2f}→{new_audio:.2f} "
              f"rfpower {new_rfpower}%")

    @Slot(str, float)
    def _on_meter_update(self, name: str, value: float):
        if name == "FWDPWR":
            self.control_panel.update_watt(value)
            if self.encoder.is_transmitting and value > 1:
                self._fwdpwr_samples.append(value)
                # Live-Update Clipschutz + TX-Pegel + RF waehrend TX
                raw_peak = self.radio.tx_raw_peak
                self.control_panel.update_tx_peak(raw_peak if raw_peak > 0.01 else value)
                audio_pct = int(self.radio.tx_audio_level * 100)
                self.control_panel.tx_level_label.setText(f"TX-Pegel: {audio_pct}%")
                self.control_panel.update_rfpower(self._rfpower_current)
            elif not self.encoder.is_transmitting:
                # TX inaktiv → Anzeige zuruecksetzen
                self.control_panel.update_tx_peak(0.0)
        elif name == "SWR":
            self.control_panel.update_swr(value)
        elif name == "ALC":
            self.control_panel.update_alc(value)
