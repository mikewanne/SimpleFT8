"""P106 — ADIF-Reparatur für QRZ-Re-Upload.

Mike-Field-Beobachtung 21.05.2026: ab 05.04.2026 keine QRZ-Confirmed mehr.
Davor (28.-29.03.) wurden fast alle QSOs bestätigt. v0.24 (17.04.) fügte
ADIF-Felder hinzu — Verdacht aber unklar welcher exakt der Verursacher ist.

Dieses Script schreibt alle ADIFs ab 05.04. in das EXAKT funktionierende
ALT-FORMAT vor v0.24 um:
  - CALL, QSO_DATE, TIME_ON, BAND, FREQ, MODE
  - RST_SENT, RST_RCVD (mit R-Strip wie Bug-B v0.95.18)
  - GRIDSQUARE (immer, ggf. leer), MY_GRIDSQUARE
  - STATION_CALLSIGN, TX_PWR
  - COMMENT „SimpleFT8 v1.0"
  - FT4/FT2-Submode-Logik wie v0.24

NICHT geschrieben (= entfernt gegenüber v0.24+):
  - TIME_OFF, OPERATOR
  - QSL_SENT, QSL_RCVD
  - MY_DXCC, MY_COUNTRY, MY_CQ_ZONE, MY_ITU_ZONE

Mike-Workflow:
  1. Skript ausführen: ./venv/bin/python3 tools/adif_repair.py
  2. Repariete ADIFs landen in adif/repaired/
  3. Bei QRZ: alte QSOs ab 05.04. manuell löschen
  4. Repariete ADIFs neu hochladen
  5. Quote sollte zurück auf ~30-50% Confirmed gehen

Hinweise:
  - Originale ADIFs bleiben unangetastet (nur Read).
  - Script ist idempotent — kann mehrfach ausgeführt werden.
"""
from __future__ import annotations

import re
import sys
from datetime import date
from pathlib import Path

# Pfad-Setup damit `log.adif` importiert werden kann
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from log.adif import _field, _strip_r_prefix, parse_adif_file, ADIF_HEADER


# Schnittpunkt: Mike-Field-Test 21.05.: letzter bestätigter QSO am 28.03.,
# ab 29.03. keine Bestätigung mehr.
CUTOFF_DATE = "20260329"

SRC_DIRS = [
    Path(__file__).resolve().parent.parent / "adif",
    Path(__file__).resolve().parent.parent / "adif" / "archiv" / "_konsolidiert",
]
OUT_DIR = Path(__file__).resolve().parent.parent / "adif" / "repaired"


def _build_record_old_format(rec: dict[str, str]) -> str:
    """Baut einen Record im alten v0.23-Format (vor v0.24).

    Quelle: log/adif.py:log_qso wie es vor commit 045d5d4 (17.04.2026) war.
    """
    call = rec.get("CALL", "")
    qso_date = rec.get("QSO_DATE", "")
    time_on = rec.get("TIME_ON", "")
    band = rec.get("BAND", "").upper()
    freq = rec.get("FREQ", "")
    mode = rec.get("MODE", "").upper()
    submode = rec.get("SUBMODE", "").upper()
    rst_sent = _strip_r_prefix(rec.get("RST_SENT", ""))
    rst_rcvd = _strip_r_prefix(rec.get("RST_RCVD", ""))
    gridsquare = rec.get("GRIDSQUARE", "").upper()
    my_gridsquare = rec.get("MY_GRIDSQUARE", "").upper()
    station_callsign = rec.get("STATION_CALLSIGN", rec.get("OPERATOR", "")).upper()
    tx_pwr = rec.get("TX_PWR", "")

    # P106 (v0.97.83): WSJT-X-Minimal-Format — garantiert QRZ-kompatibel.
    # Mike-Beobachtung 21.05.: COMMENT war „SimpleFT8 v1.0" (Programmname),
    # nicht QSO-Notiz wie SmartSDR es nutzt („QRP" etc.). QRZ ignoriert
    # vermutlich Records mit unsinnigem COMMENT oder filtert sie.
    # Sicherer: COMMENT ganz weglassen (WSJT-X tut das auch).
    fields = [
        _field("CALL", call),
        _field("QSO_DATE", qso_date),
        _field("TIME_ON", time_on),
        _field("BAND", band),
        _field("FREQ", freq),
        _field("MODE", mode),
    ]
    if submode:
        fields.append(_field("SUBMODE", submode))
    fields += [
        _field("RST_SENT", rst_sent),
        _field("RST_RCVD", rst_rcvd),
    ]
    if gridsquare:
        fields.append(_field("GRIDSQUARE", gridsquare))
    fields += [
        _field("MY_GRIDSQUARE", my_gridsquare),
        _field("STATION_CALLSIGN", station_callsign),
        _field("TX_PWR", str(tx_pwr)),
    ]
    # KEIN COMMENT, KEIN OPERATOR, KEIN QSL_*, KEIN MY_DXCC/COUNTRY/...
    return " ".join(fields) + " <EOR>\n"


def _file_date_from_name(path: Path) -> str | None:
    """Extrahiert YYYYMMDD aus „SimpleFT8_LOG_YYYYMMDD.adi"."""
    m = re.match(r"SimpleFT8_LOG_(\d{8})", path.stem)
    return m.group(1) if m else None


def repair_files(dry_run: bool = False) -> dict:
    """Repariert alle ADIFs ab CUTOFF_DATE.

    Returns dict mit Statistik {files_in, files_out, records_total}.
    """
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    files_in = 0
    files_out = 0
    records_total = 0

    src_files: list[Path] = []
    for d in SRC_DIRS:
        if d.exists():
            src_files.extend(sorted(d.glob("SimpleFT8_LOG_*.adi")))

    for src in src_files:
        file_date = _file_date_from_name(src)
        if file_date is None or file_date < CUTOFF_DATE:
            continue
        files_in += 1
        records = parse_adif_file(src)
        if not records:
            continue
        repaired_records = [_build_record_old_format(r) for r in records]
        records_total += len(repaired_records)

        out_name = f"REPAIRED_{src.name}"
        out_path = OUT_DIR / out_name
        if dry_run:
            print(f"[DRY] {src.name} → {out_path.relative_to(OUT_DIR.parent.parent)} "
                  f"({len(repaired_records)} Records)")
        else:
            with open(out_path, "w", encoding="ascii") as f:
                f.write(ADIF_HEADER)
                f.writelines(repaired_records)
            print(f"  ✓ {src.name} → {out_path.name} ({len(repaired_records)} Records)")
        files_out += 1

    return {"files_in": files_in, "files_out": files_out, "records_total": records_total}


if __name__ == "__main__":
    dry = "--dry-run" in sys.argv
    print("=" * 70)
    print(f"ADIF-Reparatur — Cutoff {CUTOFF_DATE} (v0.23 ALT-Format)")
    print(f"Output: {OUT_DIR}")
    print("=" * 70)
    stats = repair_files(dry_run=dry)
    print("=" * 70)
    print(f"Fertig: {stats['files_in']} ADIFs gelesen, "
          f"{stats['files_out']} repariert, "
          f"{stats['records_total']} QSO-Records insgesamt.")
    if not dry:
        print(f"\nUpload-Hinweis: alte QSOs ab {CUTOFF_DATE} bei QRZ.com "
              "manuell löschen, dann die Dateien aus adif/repaired/ "
              "neu hochladen.")
