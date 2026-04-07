"""SimpleFT8 QSO Log — ADIF laden, Worked-Before tracking."""

from pathlib import Path
from log.adif import parse_adif_file


class QSOLog:
    """Verwaltet gearbeitete Stationen fuer Worked-Before Filter."""

    def __init__(self):
        self._worked: set[str] = set()
        self._worked_band: set[tuple] = set()
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
        self._count += 1

    def is_worked(self, call: str) -> bool:
        """Wurde dieses Callsign schon mal gearbeitet?"""
        base_call = call.strip().upper().split("/")[0]
        return base_call in self._worked

    def is_worked_on_band(self, call: str, band: str) -> bool:
        """Wurde dieses Callsign auf diesem Band schon gearbeitet?"""
        base_call = call.strip().upper().split("/")[0]
        return (base_call, band.upper()) in self._worked_band

    def worked_count(self) -> int:
        """Anzahl unique Calls."""
        return len(self._worked)

    def qso_count(self) -> int:
        """Gesamtzahl QSOs."""
        return self._count
