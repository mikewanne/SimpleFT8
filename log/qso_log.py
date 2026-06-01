"""SimpleFT8 QSO Log — ADIF laden, Worked-Before tracking."""

from pathlib import Path
from log.adif import parse_adif_file
from core.geo import callsign_to_country


class QSOLog:
    """Verwaltet gearbeitete Stationen fuer Worked-Before Filter.

    P165: Zusaetzlich pro Land (DXCC-Kuerzel via core.geo) ein QSO-Zaehler
    (`_country_count`) und ein Land-Band-Set (`_country_band`) fuer das
    Auto-Hunt-DX-Scoring — persoenliche Seltenheit + Land-auf-Band-neu.
    """

    def __init__(self):
        self._worked: set[str] = set()
        self._worked_band: set[tuple] = set()
        self._country_count: dict[str, int] = {}
        self._country_band: set[tuple[str, str]] = set()
        self._count = 0

    def load_adif(self, path: Path) -> int:
        """Eine ADIF-Datei laden. Gibt Anzahl geladener QSOs zurueck."""
        records = parse_adif_file(path)
        for rec in records:
            call = rec.get("CALL", "").strip().upper()
            if not call:
                continue
            # Portable-Suffixe entfernen fuer Lookup
            base_call = call.split("/")[0] if "/" in call else call
            self._worked.add(base_call)
            band = rec.get("BAND", "").strip().upper()
            if band:
                self._worked_band.add((base_call, band))
            # P165: Land-Statistik. callsign_to_country handhabt Slash-Calls
            # selbst (DXCC-Token), daher der VOLLE Call (konsistent mit dem
            # Live-Lookup in core/auto_hunt._compute_priority).
            country = callsign_to_country(call)
            self._country_count[country] = self._country_count.get(country, 0) + 1
            if band:
                self._country_band.add((country, band))
            self._count += 1
        return len(records)

    def load_directory(self, directory: Path) -> int:
        """Alle *.adi Dateien in einem Verzeichnis laden."""
        total = 0
        if not directory.exists():
            return 0
        for adi_file in sorted(directory.glob("*.adi")):
            n = self.load_adif(adi_file)
            if n > 0:
                print(f"[QSOLog] {adi_file.name}: {n} QSOs geladen")
            total += n
        return total

    def add_qso(self, call: str, band: str = ""):
        """Neues QSO zur Laufzeit hinzufuegen."""
        base_call = call.strip().upper().split("/")[0]
        self._worked.add(base_call)
        if band:
            self._worked_band.add((base_call, band.upper()))
        # P165: Land-Statistik live mitfuehren (voller Call, s. load_adif).
        country = callsign_to_country(call.strip().upper())
        self._country_count[country] = self._country_count.get(country, 0) + 1
        if band:
            self._country_band.add((country, band.upper()))
        self._count += 1

    def is_worked(self, call: str) -> bool:
        """Wurde dieses Callsign schon mal gearbeitet?"""
        base_call = call.strip().upper().split("/")[0]
        return base_call in self._worked

    def is_worked_on_band(self, call: str, band: str) -> bool:
        """Wurde dieses Callsign auf diesem Band schon gearbeitet?"""
        base_call = call.strip().upper().split("/")[0]
        return (base_call, band.upper()) in self._worked_band

    def get_country_count(self, country: str) -> int:
        """P165: Anzahl QSOs mit diesem Land (DXCC-Kuerzel via core.geo).

        0 = nie gearbeitet (ATNO) — groesste DX-Perle.
        """
        return self._country_count.get(country, 0)

    def is_country_worked_on_band(self, country: str, band: str) -> bool:
        """P165: Wurde dieses LAND auf diesem Band schon gearbeitet?

        Land-Ebene (nicht Call-Ebene): fuer die DXCC-Band-Jagd — ein Land das
        man auf einem Band noch nie hatte ist eine eigene Perle.
        """
        return (country, band.upper()) in self._country_band

    def worked_count(self) -> int:
        """Anzahl unique Calls."""
        return len(self._worked)

    def qso_count(self) -> int:
        """Gesamtzahl QSOs."""
        return self._count
