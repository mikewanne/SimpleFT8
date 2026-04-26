"""SimpleFT8 Antenna Preference — Beste Antenne pro Callsign merken.

Im Diversity-Modus vergleicht der Station Accumulator SNR von Ant1 vs Ant2.
Dieses Modul speichert die Praeferenz (Antenne + delta_db) pro Callsign und
steuert waehrend eines QSO die Hardware auf die beste Antenne.

Datenmodell (bewusst simpel):
    prefs[callsign] = {"best_ant": "A1"|"A2", "delta_db": float}

delta_db = snr_ant2 - snr_ant1 (positiv: A2 besser; negativ: A1 besser)

Keine Persistenz, kein Timeout, keine Daempfung: wenn eine Station gerade
empfangen wird, ist der Wert max. einen Zyklus alt — praeziser geht nicht.
Alter Eintrag wird bei jedem Dekodier-Zyklus einfach ueberschrieben.

Thread-Safety: alle Lese/Schreib-Operationen sind durch eine RLock geschuetzt.
Cycle-Loop schreibt aus dem Decoder-Thread, UI/Karten-Code liest aus dem GUI-Thread.
snapshot() liefert eine unabhaengige Kopie fuer Render-Pfade.
"""

import threading

# Hysterese: ab delta_db >= 1.0 auf A2 wechseln, sonst A1 als Default lassen.
# Verhindert Flattern zwischen A1/A2 bei fast gleichen Signalen.
# WICHTIG: >= statt >, damit delta=+1.0 (haeufiger Praxisfall) korrekt auf A2 wechselt.
# Asymmetrie ist gewollt: A1 ist Default-Antenne, daher braucht NUR A2 eine
# Schwelle. Bei delta < 1.0 ODER negativ bleibt A1 — das ist kein Bug, sondern
# bewusste Praeferenz fuer die TX-Antenne als Default.
HYSTERESIS_DB = 1.0


class AntennaPreferenceStore:
    """In-Memory Cache: beste Antenne pro Callsign + SNR-Delta.

    Wird aus dem station_accumulator-Ergebnis gefuettert (Messages haben
    _snr_a1, _snr_a2 nach A1<->A2 Vergleich).

    API:
        get(callsign)      -> "A1"/"A2"/None  (backward-compat, nutzt Hysterese)
        get_pref(callsign) -> dict{best_ant, delta_db} | None
        update_from_stations(stations) — aus diversity_stations fuettern
    """

    def __init__(self):
        self._prefs: dict[str, dict] = {}
        # RLock statt Lock: aktuell ruft keine Methode rekursiv eine andere lock-geschuetzte
        # Methode auf, ein einfacher Lock wuerde reichen. RLock ist defensiv gegen kuenftige
        # Erweiterungen (z.B. snapshot innerhalb einer Update-Loop). Performance-Hit ~10-20ns,
        # bei Cycle-Last (15s/7.5s/3.8s) und Karten-Render (≤10/s) irrelevant.
        self._lock = threading.RLock()

    def update_from_stations(self, stations: dict):
        """Eintraege aus den aktuell akkumulierten Stationen neu berechnen.

        Nur Stationen mit _snr_a1 UND _snr_a2 (echter A1<->A2 Vergleich) fliessen ein.
        Alten Eintrag jedesmal ueberschreiben — kein Merging, keine Glaettung.

        Args:
            stations: Dict {callsign: FT8Message} aus diversity_stations
        """
        with self._lock:
            for call, msg in stations.items():
                a1 = getattr(msg, '_snr_a1', None)
                a2 = getattr(msg, '_snr_a2', None)
                if a1 is None or a2 is None:
                    # Backward-compat: wenn nur das 'antenna'-Feld "A2>1" vorliegt,
                    # rekonstruiere die Praeferenz ohne delta_db (None = unbekannt).
                    ant = getattr(msg, 'antenna', '')
                    if '>' in ant and len(ant) >= 2:
                        best = ant[:2]
                        self._prefs[call] = {"best_ant": best, "delta_db": None}
                    continue
                delta = float(a2) - float(a1)
                if delta >= HYSTERESIS_DB:
                    best = "A2"
                else:
                    # Default A1 bei delta < Hysterese ODER A1 besser
                    best = "A1"
                self._prefs[call] = {"best_ant": best, "delta_db": delta}

    def get(self, callsign: str) -> str | None:
        """Beste Antenne fuer ein Callsign ("A1"/"A2"). None wenn unbekannt."""
        with self._lock:
            entry = self._prefs.get(callsign)
            return entry["best_ant"] if entry else None

    def get_pref(self, callsign: str) -> dict | None:
        """Volle Praeferenz: {best_ant, delta_db} oder None."""
        with self._lock:
            entry = self._prefs.get(callsign)
            if entry is None:
                return None
            return dict(entry)

    def get_delta_db(self, callsign: str) -> float | None:
        """Nur den SNR-Delta-Wert (A2 - A1) zurueckgeben. None wenn unbekannt."""
        with self._lock:
            entry = self._prefs.get(callsign)
            return entry["delta_db"] if entry else None

    def snapshot(self) -> dict[str, dict]:
        """Unabhaengige Kopie aller Praeferenzen fuer Render-/Read-Pfade.

        Mutationen am Snapshot beeinflussen den Store nicht und umgekehrt.
        Inner-Dicts werden flach kopiert — die Werte sind primitive (str/float/None),
        eine tiefere Kopie ist nicht noetig.
        """
        with self._lock:
            return {call: dict(entry) for call, entry in self._prefs.items()}

    @property
    def count(self) -> int:
        with self._lock:
            return len(self._prefs)

    def clear(self):
        with self._lock:
            self._prefs.clear()
