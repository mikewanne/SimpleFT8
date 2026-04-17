"""SimpleFT8 ADIF Writer + Parser — QSO-Export und -Import im ADIF 3.1.7 Format."""

import re
import time
from pathlib import Path
from typing import Dict, List


ADIF_HEADER = """SimpleFT8 ADIF Export
<ADIF_VER:5>3.1.7
<PROGRAMID:9>SimpleFT8
<PROGRAMVERSION:3>1.0
<EOH>
"""


def _field(name: str, value: str) -> str:
    """Ein ADIF-Feld formatieren."""
    return f"<{name.upper()}:{len(value)}>{value}"


def parse_adif_file(path: Path) -> List[Dict[str, str]]:
    """ADIF-Datei parsen → Liste von Dicts mit Feldnamen als Keys."""
    text = path.read_text(errors="replace")
    # Header ueberspringen (alles vor <EOH>)
    eoh = text.upper().find("<EOH>")
    if eoh >= 0:
        text = text[eoh + 5:]

    records = []
    _FIELD_RE = re.compile(r"<(\w+):(\d+)(?::\w+)?>", re.IGNORECASE)
    for block in re.split(r"<EOR>", text, flags=re.IGNORECASE):
        if not block.strip():
            continue
        record = {}
        for m in _FIELD_RE.finditer(block):
            name = m.group(1).upper()
            length = int(m.group(2))
            value_start = m.end()
            record[name] = block[value_start:value_start + length].strip()
        if record:
            record["_SOURCE_FILE"] = str(path)  # Quelldatei merken fuer Loeschen
            records.append(record)
    return records


def delete_qso(record: Dict[str, str]) -> bool:
    """QSO-Record aus der ADIF-Datei loeschen. Gibt True zurueck wenn erfolgreich."""
    source = record.get("_SOURCE_FILE")
    if not source:
        return False
    path = Path(source)
    if not path.exists():
        return False

    # Identifikation: CALL + QSO_DATE + TIME_ON (eindeutig genug)
    match_call = record.get("CALL", "")
    match_date = record.get("QSO_DATE", "")
    match_time = record.get("TIME_ON", "")

    text = path.read_text(errors="replace")
    eoh_pos = text.upper().find("<EOH>")
    header = text[:eoh_pos + 5] if eoh_pos >= 0 else ""
    body = text[eoh_pos + 5:] if eoh_pos >= 0 else text

    _FIELD_RE = re.compile(r"<(\w+):(\d+)(?::\w+)?>", re.IGNORECASE)
    blocks = re.split(r"(<EOR>)", body, flags=re.IGNORECASE)

    # blocks: [block0, "<EOR>", block1, "<EOR>", ...]
    new_body = ""
    i = 0
    deleted = False
    while i < len(blocks):
        block = blocks[i]
        eor = blocks[i + 1] if i + 1 < len(blocks) else ""
        i += 2

        if not block.strip():
            continue

        # Record aus Block parsen
        rec = {}
        for m in _FIELD_RE.finditer(block):
            name = m.group(1).upper()
            length = int(m.group(2))
            rec[name] = block[m.end():m.end() + length].strip()

        if (not deleted
                and rec.get("CALL") == match_call
                and rec.get("QSO_DATE") == match_date
                and rec.get("TIME_ON") == match_time):
            deleted = True  # diesen Record ueberspringen
        else:
            new_body += block + eor

    if deleted:
        path.write_text(header + new_body)
    return deleted


def parse_all_adif_files(directory: Path) -> List[Dict[str, str]]:
    """Alle ADIF-Dateien in einem Verzeichnis laden, nach Datum sortiert."""
    all_records = []
    for adi_file in sorted(directory.glob("*.adi")):
        all_records.extend(parse_adif_file(adi_file))
    # Nach Datum+Zeit sortieren (neueste zuerst)
    all_records.sort(
        key=lambda r: r.get("QSO_DATE", "") + r.get("TIME_ON", ""),
        reverse=True,
    )
    return all_records


class AdifWriter:
    """Schreibt QSO-Einträge als ADIF-Datei (Append-Modus)."""

    def __init__(self, directory: str | Path | None = None):
        if directory is None:
            directory = Path.cwd()
        # ADIF-Dateien in adif/ Unterordner
        self.directory = Path(directory) / "adif"
        self.directory.mkdir(parents=True, exist_ok=True)

    def _logfile_path(self) -> Path:
        date_str = time.strftime("%Y%m%d", time.gmtime())
        return self.directory / f"SimpleFT8_LOG_{date_str}.adi"

    def _ensure_header(self, path: Path):
        if not path.exists():
            with open(path, "w") as f:
                f.write(ADIF_HEADER)

    def log_qso(
        self,
        call: str,
        band: str,
        freq_mhz: float,
        mode: str,
        rst_sent: str,
        rst_rcvd: str,
        gridsquare: str,
        my_gridsquare: str,
        my_callsign: str,
        tx_power: int,
        time_on: float | None = None,
    ):
        """Ein abgeschlossenes QSO als ADIF-Record anhängen.

        Args:
            call: Rufzeichen der Gegenstation
            band: Band (z.B. "20M")
            freq_mhz: Frequenz in MHz
            mode: FT8/FT4/FT2
            rst_sent: Gesendeter SNR-Rapport
            rst_rcvd: Empfangener SNR-Rapport
            gridsquare: Locator der Gegenstation
            my_gridsquare: Eigener Locator
            my_callsign: Eigenes Rufzeichen
            tx_power: Sendeleistung in Watt
            time_on: Unix-Timestamp des QSO-Beginns (default: jetzt)
        """
        if time_on is None:
            time_on = time.time()

        t = time.gmtime(time_on)

        # FT4: MODE=MFSK + SUBMODE=FT4 (ADIF-Standard, QRZ/LoTW kompatibel)
        mode_upper = mode.upper()
        if mode_upper == "FT4":
            adif_mode = "MFSK"
            adif_submode = "FT4"
        elif mode_upper == "FT2":
            adif_mode = "MFSK"
            adif_submode = "FT2"
        else:
            adif_mode = mode_upper
            adif_submode = ""

        # TIME_OFF = TIME_ON + 15 Sekunden (1 FT8-Zyklus)
        t_off = time.gmtime(time_on + 15)

        fields = [
            _field("CALL", call),
            _field("QSO_DATE", time.strftime("%Y%m%d", t)),
            _field("TIME_ON", time.strftime("%H%M%S", t)),
            _field("TIME_OFF", time.strftime("%H%M%S", t_off)),
            _field("BAND", band.upper()),
            _field("FREQ", f"{freq_mhz:.6f}"),
            _field("MODE", adif_mode),
        ]
        if adif_submode:
            fields.append(_field("SUBMODE", adif_submode))
        fields += [
            _field("RST_SENT", str(rst_sent)),
            _field("RST_RCVD", str(rst_rcvd)),
            _field("OPERATOR", my_callsign.upper()),
            _field("STATION_CALLSIGN", my_callsign.upper()),
            _field("MY_GRIDSQUARE", my_gridsquare.upper()),
            _field("TX_PWR", str(tx_power)),
            _field("QSL_SENT", "N"),
            _field("QSL_RCVD", "N"),
            _field("MY_DXCC", "230"),
            _field("MY_COUNTRY", "Germany"),
            _field("MY_CQ_ZONE", "14"),
            _field("MY_ITU_ZONE", "28"),
            _field("COMMENT", "SimpleFT8 v1.0"),
        ]
        # Optionale Felder nur wenn vorhanden
        if gridsquare:
            fields.insert(8, _field("GRIDSQUARE", gridsquare.upper()))

        record = " ".join(fields) + " <EOR>\n"

        path = self._logfile_path()
        self._ensure_header(path)
        with open(path, "a") as f:
            f.write(record)

        return path
