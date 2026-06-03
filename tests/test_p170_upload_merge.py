"""P170 — merge_adif_files: bei Upload-Move gleichnamige Tagesdateien mergen.

Deckt ab: dedupliziertes Anhängen, Byte-Erhalt der dest-Records, Atomarität
(kein .tmp-Rest), Idempotenz, Schutz bei ungültiger dest (kein <EOH> → raise),
CALL-lose Blöcke werden verworfen, src-Header wird nicht mit-übernommen.
"""
from pathlib import Path

import pytest

from log.adif import merge_adif_files, parse_adif_file


def _qso(call, time_on, date="20260504"):
    return (f"<call:{len(call)}>{call} <qso_date:8>{date} "
            f"<time_on:6>{time_on} <band:3>20m <mode:3>FT8 <eor>\n")


def _write(path: Path, *qsos):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("<adif_ver:5>3.1.7<eoh>\n" + "".join(qsos))


def test_merge_appends_new_and_dedups(tmp_path):
    dest = tmp_path / "dest.adi"
    src = tmp_path / "src.adi"
    _write(dest, _qso("AA1AA", "120000"))
    _write(src, _qso("AA1AA", "120000"), _qso("BB2BB", "123000"))  # 1 dup, 1 neu

    appended, dup = merge_adif_files(src, dest)

    assert (appended, dup) == (1, 1)
    calls = {r["CALL"] for r in parse_adif_file(dest)}
    assert calls == {"AA1AA", "BB2BB"}
    assert len(parse_adif_file(dest)) == 2          # AA1AA nicht doppelt


def test_merge_preserves_dest_bytes(tmp_path):
    """Die bestehenden dest-Bytes bleiben exakt erhalten (nur Anhang)."""
    dest = tmp_path / "dest.adi"
    src = tmp_path / "src.adi"
    _write(dest, _qso("AA1AA", "120000"))
    original = dest.read_bytes()
    _write(src, _qso("BB2BB", "123000"))

    merge_adif_files(src, dest)

    after = dest.read_bytes()
    assert after.startswith(original)               # Original-Bytes 1:1 vorangestellt
    assert b"BB2BB" in after[len(original):]          # Neues nur angehängt


def test_merge_preserves_crlf_dest(tmp_path):
    """CRLF-Zeilenenden in dest werden NICHT auf LF übersetzt (newline='')."""
    dest = tmp_path / "dest.adi"
    src = tmp_path / "src.adi"
    # dest mit CRLF schreiben (byte-exakt vorgeben)
    dest.write_bytes(
        b"<adif_ver:5>3.1.7<eoh>\r\n"
        b"<call:5>AA1AA <qso_date:8>20260504 <time_on:6>120000 "
        b"<band:3>20m <mode:3>FT8 <eor>\r\n")
    original = dest.read_bytes()
    _write(src, _qso("BB2BB", "123000"))

    merge_adif_files(src, dest)

    after = dest.read_bytes()
    assert after.startswith(original)               # CRLF-Bytes unverändert
    assert b"\r\n<call:5>AA1AA" in after            # CR nicht verschluckt


def test_merge_atomic_no_tmp_leftover(tmp_path):
    dest = tmp_path / "dest.adi"
    src = tmp_path / "src.adi"
    _write(dest, _qso("AA1AA", "120000"))
    _write(src, _qso("BB2BB", "123000"))

    merge_adif_files(src, dest)

    assert not (tmp_path / "dest.adi.tmp").exists()
    assert list(tmp_path.glob("*.tmp")) == []


def test_merge_idempotent(tmp_path):
    dest = tmp_path / "dest.adi"
    src = tmp_path / "src.adi"
    _write(dest, _qso("AA1AA", "120000"))
    _write(src, _qso("BB2BB", "123000"))

    merge_adif_files(src, dest)
    appended2, dup2 = merge_adif_files(src, dest)   # zweiter Lauf

    assert appended2 == 0 and dup2 == 1             # nichts doppelt
    assert len(parse_adif_file(dest)) == 2


def test_merge_invalid_dest_raises(tmp_path):
    """dest ohne <EOH> → ValueError (Aufrufer lässt beide Dateien stehen)."""
    dest = tmp_path / "dest.adi"
    src = tmp_path / "src.adi"
    dest.write_text("kaputt, kein header")
    _write(src, _qso("BB2BB", "123000"))

    with pytest.raises(ValueError):
        merge_adif_files(src, dest)
    # dest unangetastet
    assert dest.read_text() == "kaputt, kein header"


def test_merge_skips_callless_blocks(tmp_path):
    """Blöcke ohne CALL (Header-Rest/Müll) werden nicht angehängt."""
    dest = tmp_path / "dest.adi"
    src = tmp_path / "src.adi"
    _write(dest, _qso("AA1AA", "120000"))
    # src enthält einen CALL-losen Block + ein echtes QSO
    src.write_text("<adif_ver:5>3.1.7<eoh>\n"
                   "<band:3>20m <mode:3>FT8 <eor>\n"        # kein CALL
                   + _qso("BB2BB", "123000"))

    appended, _ = merge_adif_files(src, dest)

    assert appended == 1
    assert {r["CALL"] for r in parse_adif_file(dest)} == {"AA1AA", "BB2BB"}


def test_merge_no_double_eoh(tmp_path):
    """src-Header (<EOH>) landet NICHT in dest — nur ein Header im Ergebnis."""
    dest = tmp_path / "dest.adi"
    src = tmp_path / "src.adi"
    _write(dest, _qso("AA1AA", "120000"))
    _write(src, _qso("BB2BB", "123000"))

    merge_adif_files(src, dest)

    assert dest.read_text().upper().count("<EOH>") == 1
