"""DiversityCache — 2-Stunden Cache für Diversity-Kalibrierungsdaten.

Speichert Tunen + Gain-Messung + Einmess-Ergebnisse pro Band+Modus.
Gültig 2 Stunden. Dialog bei erneutem Aktivieren: "X Min alt — weiter?"
"""

import time

SUPPORTED_BANDS = ["10m", "15m", "20m", "40m"]  # Kelemen + Polarisationsdiversität 40m
CACHE_VALIDITY_SECONDS = 2 * 3600        # 2 Stunden


class DiversityCache:
    """Cache für Diversity-Setup-Ergebnisse (Tunen, Gain, Einmessen)."""

    def __init__(self, settings):
        self._settings = settings

    def _key(self, band: str, scoring_mode: str) -> str:
        return f"diversity_cache_{band}_{scoring_mode}"

    def get_age_minutes(self, band: str, scoring_mode: str) -> int | None:
        """Alter des Cache-Eintrags in Minuten, oder None wenn kein Eintrag."""
        data = self._settings.get(self._key(band, scoring_mode), None)
        if not data or "timestamp" not in data:
            return None
        return int((time.time() - data["timestamp"]) / 60)

    def is_valid(self, band: str, scoring_mode: str) -> bool:
        """True wenn Cache vorhanden und < 2 Stunden alt."""
        age = self.get_age_minutes(band, scoring_mode)
        if age is None:
            return False
        return age * 60 < CACHE_VALIDITY_SECONDS

    def save(self, band: str, scoring_mode: str):
        """Aktuellen Zeitstempel speichern (Pipeline abgeschlossen)."""
        key = self._key(band, scoring_mode)
        entry = self._settings.get(key, {}) or {}
        entry["timestamp"] = time.time()
        self._settings.set(key, entry)
        self._settings.save()

    def clear(self, band: str, scoring_mode: str):
        """Cache-Eintrag löschen (erzwingt Neu-Messung)."""
        self._settings.set(self._key(band, scoring_mode), None)
        self._settings.save()
