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
        if not self.radio.ip:
            return
        from config.settings import get_tune_freq_mhz
        if on:
            tune_freq = get_tune_freq_mhz(self.settings.band, self.settings.mode)
            # _tune_active VOR set_frequency setzen (verhindert Race mit Radio-Callback)
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
            self.radio.tune_on()
            self._update_statusbar()
            display_freq = tune_freq if tune_freq is not None else self.settings.frequency_mhz
            self.control_panel.set_freq_display(display_freq, tune_active=True)
        else:
            self.radio.tune_off()
            self._tune_active = False
            self._tune_freq_mhz = None
            work_freq = self.settings.frequency_mhz
            self.radio.set_frequency(work_freq)
            self._update_statusbar()
            self.control_panel.set_freq_display(work_freq, tune_active=False)
            print(f"[Tune] VFO zurueck auf {work_freq * 1000:.3f} kHz")

    @Slot(float)
    def _on_swr_alarm(self, swr: float):
        now = time.time()
        if now - getattr(self, '_last_swr_alarm', 0) < 10:
            return  # Cooldown: max 1 Alarm pro 10s
        self._last_swr_alarm = now
        self.statusBar().showMessage(f"SWR ALARM: {swr:.1f} — TX gestoppt! Tuner/Antenne pruefen.", 10000)
        print(f"[SWR] Alarm: {swr:.1f} — TX gestoppt")

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
