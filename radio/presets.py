"""Radio-Presets — Band-spezifische Verstärker- und Antennen-Einstellungen.

Ausgelagert aus FlexRadio für radio-agnostischen Zugriff (factory pattern).
"""

# Standard-Preamp-Gain pro Band (für FlexRadio rfgain-Befehl)
PREAMP_PRESETS: dict[str, int] = {
    "160m": 0,
    "80m":  0,
    "60m":  0,
    "40m": 10,
    "30m": 10,
    "20m": 10,
    "17m": 10,
    "15m": 20,
    "12m": 20,
    "10m": 20,
}
