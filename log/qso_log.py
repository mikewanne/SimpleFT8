"""SimpleFT8 QSO Log — ADIF laden, Worked-Before tracking."""

from pathlib import Path


def parse_adif_file(path: Path) -> list[dict]:
    """ADIF-Datei parsen. Gibt Liste von Dicts mit Tag→Wert zurueck."""
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except (OSError, IOError):
        return []

    # Header ueberspringen (alles vor <EOH>)
    eoh = text.upper().find("<EOH>")
    if eoh >= 0:
        text = text[eoh + 5:]

    records = []
    # Records splitten bei <EOR>
    for block in text.upper().split("<EOR>"):
        record = {}
        pos = 0
        while pos < len(block):
            # Naechstes <TAG:LEN> finden
            start = block.find("<", pos)
            if start < 0:
                break
            end = block.find(">", start)
            if end < 0:
                break
            tag_spec = block[start + 1:end]
            if ":" in tag_spec:
                parts = tag_spec.split(":")
                tag = parts[0].strip()
                try:
                    length = int(parts[1].strip())
                except ValueError:
                    pos = end + 1
                    continue
                value = text[eoh + 5:] if False else block[end + 1:end + 1 + length] if end + 1 + length <= len(block) else ""
                # Original-Case aus der Datei holen
                orig_start = start - (len(text) - len(block) - 5 if eoh >= 0 else 0)
                value = block[end + 1:end + 1 + length].strip()
                record[tag] = value
                pos = end + 1 + length
            else:
                pos = end + 1
        if "CALL" in record:
            records.append(record)
    return records


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
