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
        self.settings.set("power_preset", power)
        self._power_target = power
        self._rfpower_current = 50  # Reset auf konservativen Start bei Power-Wechsel
        if self.radio.ip:
            self.radio.set_power(self._rfpower_current)

    @Slot(bool)
    def _on_tune_clicked(self, on: bool):
        if self.radio.ip:
            if on:
                self.radio.tune_on()
            else:
                self.radio.tune_off()

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

        # rfpower anwenden wenn geaendert
        if new_rfpower != self._rfpower_current:
            self._rfpower_current = new_rfpower
            self.radio.set_power(new_rfpower)

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
