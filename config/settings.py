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

# Tune-Frequenzen: Nebenfrequenz -2 kHz (grob), stoert keine Weltfrequenz.
# FT2 nutzt den gleichen Offset wie FT8 des Bands.
TUNE_FREQS = {
    "80m_FT8": 3.571,   "80m_FT4": 3.573,
    "40m_FT8": 7.072,   "40m_FT4": 7.0455,
    "30m_FT8": 10.134,  "30m_FT4": 10.138,
    "20m_FT8": 14.072,  "20m_FT4": 14.078,
    "17m_FT8": 18.098,  "17m_FT4": 18.102,
    "15m_FT8": 21.072,  "15m_FT4": 21.138,
    "12m_FT8": 24.913,  "12m_FT4": 24.917,
    "10m_FT8": 28.072,  "10m_FT4": 28.178,
}


def get_tune_freq_mhz(band: str, mode: str) -> float | None:
    """Tune-Frequenz fuer Band+Modus. FT2 faellt auf FT8-Wert zurueck.

    Returns None wenn kein Offset-Wert hinterlegt (z.B. 60m).
    """
    m = mode.upper()
    if m == "FT2":
        m = "FT8"
    return TUNE_FREQS.get(f"{band}_{m}")

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
    "stats_enabled": True,           # Stations-Statistik pro Zyklus loggen
    "debug_console_visible": False,  # Debug-Konsole ein/ausblenden
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

    def get_dx_preset(self, band: str, mode: str = None) -> dict | None:
        """Standard-Gain-Preset laden. mode-spezifisch wenn vorhanden, sonst Band-Fallback."""
        presets = self._data.get("dx_presets", self._data.get("standard_presets", {}))
        if mode:
            specific = presets.get(f"{band}_{mode}")
            if specific is not None:
                return specific
        return presets.get(band)

    def get_gain_preset(self, band: str, mode: str = "standard", ft_mode: str = None) -> dict | None:
        """Gain-Preset laden. mode='standard'/'dx', ft_mode='FT8'/'FT4' fuer mode-spez. Key."""
        key = "dx_gain_presets" if mode == "dx" else "dx_presets"
        presets = self._data.get(key, {})
        if ft_mode:
            specific = presets.get(f"{band}_{ft_mode}")
            if specific is not None:
                return specific
        return presets.get(band)

    def get_normal_preset(self, band: str) -> dict:
        """Normal-Modus Gain-Preset — nie aus Diversity-Presets. Standard: PREAMP_PRESETS-Wert."""
        from radio.presets import PREAMP_PRESETS
        presets = self._data.get("normal_presets", {})
        if band in presets:
            return presets[band]
        return {"rxant": "ANT1", "gain": PREAMP_PRESETS.get(band, 10)}

    def save_normal_preset(self, band: str, gain: int, rxant: str = "ANT1"):
        """Normal-Modus Gain-Preset speichern (nach manueller Kalibrierung)."""
        import time
        if "normal_presets" not in self._data:
            self._data["normal_presets"] = {}
        self._data["normal_presets"][band] = {
            "rxant": rxant,
            "gain": gain,
            "measured": time.strftime("%Y-%m-%d %H:%M"),
        }
        self.save()

    def get_normal_tx_freq(self, band: str) -> int:
        """Manuell eingestellte TX-Frequenz pro Band fuer Normal-Modus.

        Wird bei Bandwechsel geladen und beim Klick im Histogramm /
        Spinbox-Aenderung gespeichert. Default 1500 Hz (WSJT-X-Default).
        """
        per_band = self._data.get("normal_tx_freq_per_band", {})
        return int(per_band.get(band, self._data.get("audio_freq_hz", 1500)))

    def save_normal_tx_freq(self, band: str, freq_hz: int):
        """TX-Frequenz fuer Band speichern (Normal-Modus, manuelle Auswahl)."""
        if "normal_tx_freq_per_band" not in self._data:
            self._data["normal_tx_freq_per_band"] = {}
        self._data["normal_tx_freq_per_band"][band] = int(freq_hz)
        self.save()

    def save_dx_preset(self, band: str, rxant: str, gain: int,
                       ant1_avg: float = 0, ant2_avg: float = 0,
                       ant1_gain: int = None, ant2_gain: int = None,
                       scoring: str = "standard", mode: str = None):
        """Gain-Preset speichern. scoring='standard' (Stationen) oder 'dx' (SNR).

        Standard → in 'dx_presets' (Legacy-Key, Rueckwaertskompatibel)
        DX → in 'dx_gain_presets' (neuer Key)
        mode → bei Angabe als band_mode-Key gespeichert (z.B. '20m_FT8')
        """
        import time
        key = "dx_gain_presets" if scoring in ("dx", "snr") else "dx_presets"
        if key not in self._data:
            self._data[key] = {}
        preset_key = f"{band}_{mode}" if mode else band
        self._data[key][preset_key] = {
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

    # ── TX-Power pro Band ─────────────────────────────────────────

    def save_tx_power(self, band: str, rfpower: int):
        """rfpower-Wert pro Band speichern (nach TX-Konvergenz)."""
        rp = self._data.setdefault("rfpower_per_band", {})
        rp[band] = int(rfpower)
        self.save()

    def get_tx_power(self, band: str, default: int = 50) -> int:
        """Gespeicherten rfpower-Wert für ein Band laden. Clamp 10-80%."""
        val = self._data.get("rfpower_per_band", {}).get(band)
        if val is None:
            return default
        return max(10, min(80, int(val)))

    # ── Diversity Presets (Ratio pro Modus+Band) ──────────────────

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
