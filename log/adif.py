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
    # Jeder Record endet mit <EOR>
    _FIELD_RE = re.compile(r"<(\w+):(\d+)(?::\w+)?>", re.IGNORECASE)
    for block in re.split(r"<EOR>", text, flags=re.IGNORECASE):
        if not block.strip():
            continue
        record = {}
        pos = 0
        for m in _FIELD_RE.finditer(block):
            name = m.group(1).upper()
            length = int(m.group(2))
            value_start = m.end()
            record[name] = block[value_start:value_start + length].strip()
        if record:
            records.append(record)
    return records


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
        self.directory = Path(directory)
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

        fields = [
            _field("CALL", call),
            _field("QSO_DATE", time.strftime("%Y%m%d", t)),
            _field("TIME_ON", time.strftime("%H%M%S", t)),
            _field("BAND", band.upper()),
            _field("FREQ", f"{freq_mhz:.6f}"),
            _field("MODE", mode.upper()),
            _field("RST_SENT", str(rst_sent)),
            _field("RST_RCVD", str(rst_rcvd)),
            _field("GRIDSQUARE", gridsquare.upper()),
            _field("MY_GRIDSQUARE", my_gridsquare.upper()),
            _field("STATION_CALLSIGN", my_callsign.upper()),
            _field("TX_PWR", str(tx_power)),
            _field("COMMENT", "SimpleFT8 v1.0"),
        ]

        record = " ".join(fields) + " <EOR>\n"

        path = self._logfile_path()
        self._ensure_header(path)
        with open(path, "a") as f:
            f.write(record)

        return path
