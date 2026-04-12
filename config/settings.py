"""SimpleFT8 Settings — Laden/Speichern der Konfiguration."""

import json
import os
from pathlib import Path

CONFIG_DIR = Path.home() / ".simpleft8"
CONFIG_FILE = CONFIG_DIR / "config.json"

# Standard-FT8/FT4-Frequenzen pro Band
BAND_FREQUENCIES = {
    "80m": {"ft8": 3.573, "ft4": 3.575},
    "60m": {"ft8": 5.357, "ft4": 5.357},
    "40m": {"ft8": 7.074, "ft4": 7.047},
    "30m": {"ft8": 10.136, "ft4": 10.140},
    "20m": {"ft8": 14.074, "ft4": 14.080},
    "17m": {"ft8": 18.100, "ft4": 18.104},
    "15m": {"ft8": 21.074, "ft4": 21.140},
    "12m": {"ft8": 24.915, "ft4": 24.919},
    "10m": {"ft8": 28.074, "ft4": 28.180},
}

DEFAULTS = {
    "callsign": "DA1MHH",
    "locator": "JO31",
    "power_watts": 50,
    "audio_input": "",
    "audio_output": "",
    "flexradio_ip": "",
    "flexradio_port": 4992,
    "band": "20m",
    "mode": "FT8",
    "auto_mode": False,
    "audio_freq_hz": 1500,
    "max_decode_freq": 3000,
    "max_calls": 99,
    "tune_power": 10,
    "diversity_operate_cycles": 80,  # 80/160/240 — Betriebszyklen bis Neueinmessung
    "radio_type": "flex",            # "flex" = FlexRadio SmartSDR, "ic7300" = CI-V (zukünftig)
}


class Settings:
    """Verwaltet SimpleFT8-Konfiguration in ~/.simpleft8/config.json."""

    def __init__(self):
        self._data = dict(DEFAULTS)
        self.load()

    def load(self):
        if CONFIG_FILE.exists():
            try:
                with open(CONFIG_FILE, "r") as f:
                    saved = json.load(f)
                self._data.update(saved)
            except (json.JSONDecodeError, IOError):
                pass

    def save(self):
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        with open(CONFIG_FILE, "w") as f:
            json.dump(self._data, f, indent=2)

    def get(self, key, default=None):
        return self._data.get(key, default)

    def set(self, key, value):
        self._data[key] = value

    @property
    def callsign(self):
        return self._data["callsign"]

    @property
    def locator(self):
        return self._data["locator"]

    @property
    def power_watts(self):
        return self._data["power_watts"]

    @property
    def band(self):
        return self._data["band"]

    @property
    def mode(self):
        return self._data["mode"]

    @property
    def frequency_mhz(self):
        """Aktuelle Frequenz basierend auf Band und Modus."""
        band = self._data["band"]
        mode = self._data["mode"].lower()
        return BAND_FREQUENCIES.get(band, {}).get(mode, 14.074)

    @property
    def audio_freq_hz(self):
        return self._data["audio_freq_hz"]

    @property
    def max_decode_freq(self):
        return self._data["max_decode_freq"]

    # ── DX Presets ──────────────────────────────────────────────

    def get_dx_preset(self, band: str) -> dict | None:
        """DX-Preset fuer ein Band laden. None wenn keins gespeichert."""
        presets = self._data.get("dx_presets", {})
        return presets.get(band)

    def save_dx_preset(self, band: str, rxant: str, gain: int,
                       ant1_avg: float = 0, ant2_avg: float = 0,
                       ant1_gain: int = None, ant2_gain: int = None):
        """DX-Preset fuer ein Band speichern.

        Neu: ant1_gain/ant2_gain separat (fuer Diversity).
        rxant/gain bleiben fuer Rueckwaertskompatibilitaet erhalten.
        """
        import time
        if "dx_presets" not in self._data:
            self._data["dx_presets"] = {}
        self._data["dx_presets"][band] = {
            "rxant": rxant,
            "gain": gain,
            "ant1_gain": ant1_gain if ant1_gain is not None else gain,
            "ant2_gain": ant2_gain if ant2_gain is not None else gain,
            "ant1_avg": round(ant1_avg, 1),
            "ant2_avg": round(ant2_avg, 1),
            "measured": time.strftime("%Y-%m-%d %H:%M"),
        }
        self.save()
