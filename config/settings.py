"""SimpleFT8 Settings — Laden/Speichern der Konfiguration."""

import json
import os
from pathlib import Path

CONFIG_DIR = Path.home() / ".simpleft8"
CONFIG_FILE = CONFIG_DIR / "config.json"

# Standard-FT8/FT4/FT2-Frequenzen pro Band
# FT2: Community-Frequenzen (DXZone/Decodium), Stand April 2026
# HINWEIS: FT2-Decoder noch NICHT Decodium-kompatibel (8-GFSK noetig, wir haben 4-GFSK)
BAND_FREQUENCIES = {
    "80m": {"ft8": 3.573, "ft4": 3.575, "ft2": 3.578},
    "60m": {"ft8": 5.357, "ft4": 5.357, "ft2": 5.360},
    "40m": {"ft8": 7.074, "ft4": 7.047, "ft2": 7.052},
    "30m": {"ft8": 10.136, "ft4": 10.140, "ft2": 10.144},
    "20m": {"ft8": 14.074, "ft4": 14.080, "ft2": 14.084},
    "17m": {"ft8": 18.100, "ft4": 18.104, "ft2": 18.108},
    "15m": {"ft8": 21.074, "ft4": 21.140, "ft2": 21.144},
    "12m": {"ft8": 24.915, "ft4": 24.919, "ft2": 24.923},
    "10m": {"ft8": 28.074, "ft4": 28.180, "ft2": 28.184},
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
    "language": "de",                # "de" = Deutsch, "en" = English (Hilfe-Texte + Docs)
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

    # ── Gain Presets (getrennt: Standard + DX) ───────────────────

    def get_dx_preset(self, band: str) -> dict | None:
        """Standard-Gain-Preset laden (Scoring: Stationsanzahl). Rueckwaertskompatibel."""
        # Legacy: "dx_presets" Key (vor v0.40 hiess es so)
        presets = self._data.get("dx_presets", self._data.get("standard_presets", {}))
        return presets.get(band)

    def get_gain_preset(self, band: str, mode: str = "standard") -> dict | None:
        """Gain-Preset laden. mode='standard' oder 'dx'."""
        key = "dx_gain_presets" if mode == "dx" else "dx_presets"
        presets = self._data.get(key, {})
        return presets.get(band)

    def save_dx_preset(self, band: str, rxant: str, gain: int,
                       ant1_avg: float = 0, ant2_avg: float = 0,
                       ant1_gain: int = None, ant2_gain: int = None,
                       scoring: str = "standard"):
        """Gain-Preset speichern. scoring='standard' (Stationen) oder 'dx' (SNR).

        Standard → in 'dx_presets' (Legacy-Key, Rueckwaertskompatibel)
        DX → in 'dx_gain_presets' (neuer Key)
        """
        import time
        key = "dx_gain_presets" if scoring == "dx" else "dx_presets"
        if key not in self._data:
            self._data[key] = {}
        self._data[key][band] = {
            "rxant": rxant,
            "gain": gain,
            "ant1_gain": ant1_gain if ant1_gain is not None else gain,
            "ant2_gain": ant2_gain if ant2_gain is not None else gain,
            "ant1_avg": round(ant1_avg, 1),
            "ant2_avg": round(ant2_avg, 1),
            "measured": time.strftime("%Y-%m-%d %H:%M"),
            "scoring": scoring,
        }
        self.save()

    # ── Diversity Presets (Ratio pro Modus+Band) ──────────────────

    def get_diversity_preset(self, mode: str, band: str) -> dict | None:
        """Diversity-Preset laden. Key: 'FT8_20m' etc."""
        presets = self._data.get("diversity_presets", {})
        return presets.get(f"{mode}_{band}")

    def save_diversity_preset(self, mode: str, band: str,
                              ratio: str, dominant: str | None):
        """Diversity-Ergebnis speichern (nach jeder erfolgreichen Messung)."""
        import time
        if "diversity_presets" not in self._data:
            self._data["diversity_presets"] = {}
        self._data["diversity_presets"][f"{mode}_{band}"] = {
            "ratio": ratio,
            "dominant": dominant,
            "measured": time.strftime("%Y-%m-%d %H:%M"),
        }
        self.save()
