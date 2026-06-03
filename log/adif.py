"""SimpleFT8 ADIF Writer + Parser — QSO-Export und -Import im ADIF 3.1.7 Format."""

import os
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


def _strip_r_prefix(rst) -> str:
    """Strippt fuehrendes R-Praefix aus FT8-Reports (ADIF-Compliance).

    P1.BUNDLE Bug-B (v0.95.18): FT8-Sequence-Layer schreibt bei der
    Antwort `R{snr:+03d}` (z.B. „R-22" = „Roger, dein Report ist -22").
    Im ADIF-Logbuch ist das jedoch nicht spec-konform — RST_RCVD bei
    digitalen Modi soll nur das SNR enthalten (z.B. „-22", „+05").
    QRZ.com-Validator wirft R-Prefix-Records raus → Bulk-Upload-Burst.

    Idempotent: ohne R-Prefix oder nicht-FT8-Format unveraendert.
    """
    if not rst:
        return ""
    rst = str(rst).strip()
    if len(rst) >= 2 and rst[0].upper() == "R" and rst[1] in "+-":
        return rst[1:]
    return rst


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
    # P1.BUNDLE Bug-A (v0.95.18): list.append + "".join statt += in Loop
    # → O(n²) → O(n). Bei 12 MB ADIF mit 10K Records: 5-10 s → < 200 ms.
    new_parts = []
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
            new_parts.append(block + eor)

    if deleted:
        path.write_text(header + "".join(new_parts))
    return deleted


def merge_adif_files(src: Path, dest: Path) -> tuple[int, int]:
    """P170: QSO-Records aus ``src`` an die bestehende ``dest`` ANHÄNGEN.

    Aufgerufen vom Upload-Move (``mw_qso._handle_qrz_file_results``), wenn in
    ``adif/erfasst/hochgeladen/`` schon eine GLEICHNAMIGE Tagesdatei liegt
    (gleicher Dateiname, andere QSOs derselben Session — z.B. Vormittag schon
    hochgeladen, Nachmittag frisch gefunkt). Statt den Move zu überspringen
    (→ Stau in ``neu/``) werden die neuen Records gemergt. Mike-Wahl 03.06.2026.

    Datensicherheit (höchste Prio — ``dest`` enthält bereits hochgeladene QSOs):
    - **Dedup** per ``(CALL, QSO_DATE, TIME_ON)`` — identischer Key wie
      ``export_all_records`` — gegen die in ``dest`` vorhandenen UND innerhalb
      von ``src`` (kein Doppelt-Anhängen, idempotent bei Re-Run).
    - ``dest`` wird **byte-erhaltend** beibehalten (nur angehängt, NICHT neu
      serialisiert); der ``src``-Header (alles vor ``<EOH>``) wird verworfen.
    - Nur Blöcke mit ``CALL`` werden übernommen (App-QSOs haben immer CALL).
    - **Atomar:** neuer Inhalt → Temp-Datei → ``os.replace``.
    - **Striktes utf-8-Lesen** + ``<EOH>``-Validierung von ``dest``: kaputte
      Bytes oder eine nicht-ADIF-``dest`` werfen eine Exception, die der Aufrufer
      abfängt → BEIDE Dateien bleiben stehen, kein Datenverlust.

    Returns ``(appended, skipped_dup)``. ``dest`` muss existieren.
    """
    _FIELD_RE = re.compile(r"<(\w+):(\d+)(?::\w+)?>", re.IGNORECASE)

    def _records(text: str):
        """(rec_dict, originaltext_block) je QSO-Block nach <EOH>. Header weg."""
        eoh = text.upper().find("<EOH>")
        body = text[eoh + 5:] if eoh >= 0 else text
        parts = re.split(r"(<EOR>)", body, flags=re.IGNORECASE)
        i = 0
        while i < len(parts):
            block = parts[i]
            eor = parts[i + 1] if i + 1 < len(parts) else ""
            i += 2
            if not block.strip():
                continue
            rec = {}
            for m in _FIELD_RE.finditer(block):
                rec[m.group(1).upper()] = block[m.end():m.end() + int(m.group(2))].strip()
            yield rec, block + eor

    # dest strikt + BYTE-ERHALTEND lesen (newline="" → keine Newline-Übersetzung,
    # auch auf Windows; striktes utf-8 wirft bei kaputten Bytes → Aufrufer skippt).
    with open(dest, "r", encoding="utf-8", newline="") as f:
        dest_text = f.read()
    if "<EOH>" not in dest_text.upper():
        raise ValueError(f"{dest.name}: kein <EOH> — keine gültige ADIF, Merge abgebrochen")

    # Bestehende Keys direkt aus dest_text (kein zweiter Datei-Read).
    seen: set[tuple] = set()
    for rec, _ in _records(dest_text):
        call = rec.get("CALL", "")
        if call:
            seen.add((call, rec.get("QSO_DATE", ""), rec.get("TIME_ON", "")))

    with open(src, "r", encoding="utf-8", newline="") as f:
        src_text = f.read()

    append_parts: list[str] = []
    appended = skipped = 0
    for rec, raw in _records(src_text):
        call = rec.get("CALL", "")
        if not call:
            continue  # Header-Rest / Müll — App-QSOs haben immer CALL
        key = (call, rec.get("QSO_DATE", ""), rec.get("TIME_ON", ""))
        if key in seen:
            skipped += 1
            continue
        seen.add(key)
        append_parts.append(raw)  # Originaltext byte-erhaltend
        appended += 1

    if append_parts:
        new_content = dest_text
        if not new_content.endswith("\n"):
            new_content += "\n"
        new_content += "".join(append_parts)
        tmp = dest.with_name(dest.name + ".tmp")
        with open(tmp, "w", encoding="utf-8", newline="") as f:
            f.write(new_content)
        os.replace(str(tmp), str(dest))
    return appended, skipped


def parse_all_adif_files(directory: Path, recursive: bool = False) -> List[Dict[str, str]]:
    """Alle ADIF-Dateien in einem Verzeichnis laden, nach Datum sortiert.

    recursive=True (P169): auch Unterordner (für ``adif/erfasst/``).
    """
    all_records = []
    globber = directory.rglob if recursive else directory.glob
    for adi_file in sorted(globber("*.adi")):
        all_records.extend(parse_adif_file(adi_file))
    # Nach Datum+Zeit sortieren (neueste zuerst)
    all_records.sort(
        key=lambda r: r.get("QSO_DATE", "") + r.get("TIME_ON", ""),
        reverse=True,
    )
    return all_records


def export_all_records(adif_directory: Path) -> tuple[Path, int]:
    """P107 (v0.97.84): Alle ADIF-Tages-Files zu 1 Bulk-Export-File zusammenfassen.

    Mike-Wunsch 21.05.2026: ein Knopf der „alle bisherigen QSOs zu einer
    Datei für QRZ-Upload" macht. KISS — kein Datum-Range, kein File-Dialog.

    Output: `adif/exports/SimpleFT8_ALL_YYYYMMDD.adi` (Datum=heute UTC).
    Records werden chronologisch (älteste zuerst) sortiert für intuitiven
    Upload-Verlauf.

    Args:
        adif_directory: Pfad zum SimpleFT8-Hauptverzeichnis (enthält
            `adif/` Unterordner).

    Returns:
        (output_path, record_count). Wenn keine Records: count=0,
        Datei wird trotzdem mit Header geschrieben.
    """
    # P169: Quelle = adif/erfasst/ rekursiv. Nur App-Logs (SimpleFT8_LOG_*.adi)
    # — die importierte QRZ-Historie (andere Dateinamen) bleibt aussen vor, sonst
    # würde der Bulk-Export die 18k Fremd-QSOs mit re-exportieren.
    erfasst_dir = Path(adif_directory) / "adif" / "erfasst"
    out_dir = Path(adif_directory) / "adif" / "exports"
    out_dir.mkdir(parents=True, exist_ok=True)

    date_str = time.strftime("%Y%m%d", time.gmtime())
    out_path = out_dir / f"SimpleFT8_ALL_{date_str}.adi"

    seen_keys: set[tuple] = set()
    records: list[Dict[str, str]] = []
    if erfasst_dir.exists():
        for adi_file in sorted(erfasst_dir.rglob("SimpleFT8_LOG_*.adi")):
            for rec in parse_adif_file(adi_file):
                # Dedup: (CALL, QSO_DATE, TIME_ON) als Key
                key = (rec.get("CALL", ""), rec.get("QSO_DATE", ""),
                       rec.get("TIME_ON", ""))
                if key in seen_keys:
                    continue
                seen_keys.add(key)
                records.append(rec)
    # Chronologisch (älteste zuerst) sortieren
    records.sort(key=lambda r: r.get("QSO_DATE", "") + r.get("TIME_ON", ""))

    with out_path.open("w", encoding="ascii") as f:
        f.write(ADIF_HEADER)
        for rec in records:
            f.write(_rewrite_minimal(rec))
    return out_path, len(records)


# WSJT-X-Minimal-Whitelist — P106-Bugfix (Mike-Field-Test 21.05.).
# Nur Felder die QRZ.com sicher matcht + nicht-blockierend interpretiert.
# Alte ADIF-Felder die wir NICHT wollen werden silent gedroppt.
_MINIMAL_FIELDS = (
    "CALL", "QSO_DATE", "TIME_ON", "TIME_OFF",
    "BAND", "FREQ", "MODE", "SUBMODE",
    "RST_SENT", "RST_RCVD",
    "GRIDSQUARE", "MY_GRIDSQUARE",
    "STATION_CALLSIGN", "TX_PWR",
)


def _rewrite_minimal(rec: Dict[str, str]) -> str:
    """P107 (v0.97.84): Record im WSJT-X-Minimal-Format aus Dict bauen.

    Filtert Felder die seit v0.24 reingeschrieben wurden aber laut
    Verdacht QRZ-Auto-Confirm blockieren (COMMENT, QSL_*, MY_DXCC...).
    Plus R-Prefix-Strip für RST-Felder (Bug-B v0.95.18 retroaktiv).
    """
    parts = []
    for name in _MINIMAL_FIELDS:
        val = rec.get(name, "")
        if not val:
            continue
        if name in ("RST_SENT", "RST_RCVD"):
            val = _strip_r_prefix(val)
        # STATION_CALLSIGN-Fallback: alte ADIFs hatten evtl. nur OPERATOR
        if name == "STATION_CALLSIGN" and not val:
            val = rec.get("OPERATOR", "")
        parts.append(_field(name, val.upper() if name in (
            "CALL", "BAND", "MODE", "SUBMODE", "GRIDSQUARE",
            "MY_GRIDSQUARE", "STATION_CALLSIGN") else val))
    return " ".join(parts) + " <EOR>\n"


class AdifWriter:
    """Schreibt QSO-Einträge als ADIF-Datei (Append-Modus)."""

    def __init__(self, directory: str | Path | None = None):
        if directory is None:
            directory = Path.cwd()
        # P169: frische QSOs nach adif/erfasst/neu/ (einzige Worked-Quelle,
        # rekursiv gelesen; "neu" = noch nicht zu QRZ hochgeladen).
        self.directory = Path(directory) / "adif" / "erfasst" / "neu"
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

        # P106 (v0.97.83) — Mike-Field-Test 21.05.2026: QRZ-Confirmed-Quote
        # fiel ab 29.03. von ~30% auf 0%. SmartSDR-Vergleich + Mike's
        # Beobachtung „COMMENT-Feld in QRZ leer" → Verdacht: zu viele/falsche
        # Felder lassen QRZ-Match-Logik fehlschlagen.
        # Fix: WSJT-X-Minimal-Format (Industry-Standard FT8).
        # Entfernt gegenüber v0.24:
        #   COMMENT (Programmname statt User-Notiz),
        #   OPERATOR (redundant zu STATION_CALLSIGN),
        #   QSL_SENT, QSL_RCVD (verwirren QRZ-Auto-Confirm laut Verdacht),
        #   MY_DXCC, MY_COUNTRY, MY_CQ_ZONE, MY_ITU_ZONE (User-Profil-Daten,
        #   QRZ kennt diese aus dem Account).
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
            _field("RST_SENT", _strip_r_prefix(rst_sent)),
            _field("RST_RCVD", _strip_r_prefix(rst_rcvd)),
        ]
        if gridsquare:
            fields.append(_field("GRIDSQUARE", gridsquare.upper()))
        fields += [
            _field("MY_GRIDSQUARE", my_gridsquare.upper()),
            _field("STATION_CALLSIGN", my_callsign.upper()),
            _field("TX_PWR", str(tx_power)),
        ]

        record = " ".join(fields) + " <EOR>\n"

        path = self._logfile_path()
        self._ensure_header(path)
        with open(path, "a") as f:
            f.write(record)

        return path
