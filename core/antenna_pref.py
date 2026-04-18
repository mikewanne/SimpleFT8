"""SimpleFT8 Antenna Preference — Beste Antenne pro Callsign merken.

Im Diversity-Modus vergleicht der Station Accumulator SNR von Ant1 vs Ant2.
Dieses Modul speichert die Praeferenz und steuert waehrend eines QSO
die Hardware auf die beste Antenne.

Feature-Konzept und Logik-Design: DL2YMR
"""


class AntennaPreferenceStore:
    """In-Memory Cache: beste Antenne pro Callsign (Sitzungs-basiert).

    Wird aus dem station_accumulator "A2>1" / "A1>2" Format gefuettert.
    Waehrend eines QSO wird die Hardware auf die gespeicherte Praeferenz gesetzt.
    """

    def __init__(self):
        self._prefs: dict[str, str] = {}  # {callsign: "A1" oder "A2"}

    def update_from_stations(self, stations: dict):
        """Alle Stationen mit Antennen-Vergleich in den Store uebernehmen.

        Args:
            stations: Dict {callsign: FT8Message} aus diversity_stations
        """
        for call, msg in stations.items():
            ant = getattr(msg, 'antenna', '')
            if '>' in ant:
                # "A2>1" → A2 ist besser, "A1>2" → A1 ist besser
                self._prefs[call] = ant[:2]

    def get(self, callsign: str) -> str | None:
        """Beste Antenne fuer ein Callsign. None wenn unbekannt."""
        return self._prefs.get(callsign)

    @property
    def count(self) -> int:
        return len(self._prefs)

    def clear(self):
        self._prefs.clear()
