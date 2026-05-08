"""Tests fuer tools/adif_archive.py — Konsolidierung Tagesdateien zu
Jahresarchiven. Hardware-frei, kein Qt noetig.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
from adif_archive import (  # noqa: E402
    _record_key, _record_year, _record_to_adif, _atomic_write_archive,
    consolidate, main,
)
from log.adif import ADIF_HEADER  # noqa: E402


def _write_adif(path: Path, records: list[dict]) -> None:
    """Helper: schreibt Records als ADIF-Datei."""
    parts = [ADIF_HEADER]
    for r in records:
        for k, v in r.items():
            parts.append(f"<{k}:{len(v)}>{v}")
        parts.append("<EOR>\n")
    path.write_text("".join(parts))


def _make_record(call="DA1MHH", date="20260301", time_on="120000",
                  band="20M", mode="FT8") -> dict:
    return {"CALL": call, "QSO_DATE": date, "TIME_ON": time_on,
             "BAND": band, "MODE": mode}


# ── Helper-Tests ─────────────────────────────────────────────────────────


def test_record_key_uniqueness():
    a = _make_record(call="A", date="20260101", time_on="120000")
    b = _make_record(call="B", date="20260101", time_on="120000")
    assert _record_key(a) != _record_key(b)
    c = _make_record(call="A", date="20260101", time_on="120000")
    assert _record_key(a) == _record_key(c)


def test_record_year_extraction():
    assert _record_year(_make_record(date="20260301")) == "2026"
    assert _record_year(_make_record(date="")) is None
    assert _record_year(_make_record(date="abc")) is None
    assert _record_year(_make_record(date="20")) is None


def test_record_to_adif_basic():
    rec = _make_record()
    s = _record_to_adif(rec)
    assert "<CALL:6>DA1MHH" in s
    assert "<EOR>" in s


def test_record_to_adif_skips_internal_fields():
    rec = _make_record()
    rec["_SOURCE_FILE"] = "/tmp/foo.adi"
    s = _record_to_adif(rec)
    assert "_SOURCE_FILE" not in s


def test_record_to_adif_empty_value():
    rec = _make_record()
    rec["GRIDSQUARE"] = ""
    s = _record_to_adif(rec)
    assert "<GRIDSQUARE:0>" in s


def test_record_to_adif_none_value_safe():
    """Final-R1 SOLLTE: None-Wert darf nicht crashen."""
    rec = _make_record()
    rec["GRIDSQUARE"] = None  # Parser-Bug-Simulation
    s = _record_to_adif(rec)
    assert "<GRIDSQUARE:0>" in s


# ── Konsolidierungs-Tests ────────────────────────────────────────────────


def test_empty_source_dir(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    tgt = tmp_path / "tgt"
    summary = consolidate(src, tgt)
    assert summary["processed_files"] == 0
    assert not summary["written_per_year"]
    assert not summary["errors"]


def test_single_year_consolidation(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    tgt = tmp_path / "tgt"
    _write_adif(src / "SimpleFT8_LOG_20260301.adi",
                  [_make_record(call="DA1MHH", date="20260301", time_on="120000"),
                   _make_record(call="EA2BHE", date="20260301", time_on="120100")])
    summary = consolidate(src, tgt)
    archive = tgt / "2026.adi"
    assert archive.exists()
    assert summary["written_per_year"]["2026"] == 2
    text = archive.read_text()
    assert text.startswith(ADIF_HEADER)
    assert "DA1MHH" in text
    assert "EA2BHE" in text


def test_multi_year_split(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    tgt = tmp_path / "tgt"
    _write_adif(src / "SimpleFT8_LOG_20260101.adi",
                  [_make_record(date="20251231", time_on="235900"),
                   _make_record(date="20260101", time_on="000100")])
    summary = consolidate(src, tgt)
    assert (tgt / "2025.adi").exists()
    assert (tgt / "2026.adi").exists()
    assert summary["written_per_year"]["2025"] == 1
    assert summary["written_per_year"]["2026"] == 1


def test_idempotent_second_run(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    tgt = tmp_path / "tgt"
    _write_adif(src / "SimpleFT8_LOG_20260301.adi",
                  [_make_record()])
    consolidate(src, tgt)
    # Zweiter Lauf — Quell-Datei noch da (im _konsolidiert/), neuer Lauf
    # mit gleicher Datei (manuell zurueckkopiert)
    src2 = tmp_path / "src2"
    src2.mkdir()
    _write_adif(src2 / "SimpleFT8_LOG_20260301.adi",
                  [_make_record()])
    summary = consolidate(src2, tgt)
    assert summary["skipped_duplicates"] == 1
    assert summary["written_per_year"].get("2026", 0) == 0


def test_dry_run_no_write(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    tgt = tmp_path / "tgt"
    _write_adif(src / "SimpleFT8_LOG_20260301.adi",
                  [_make_record()])
    summary = consolidate(src, tgt, dry_run=True)
    assert not (tgt / "2026.adi").exists()
    assert summary["written_per_year"]["2026"] == 1
    # Quelle wurde NICHT verschoben
    assert (src / "SimpleFT8_LOG_20260301.adi").exists()


def test_default_archive_source_to_konsolidiert(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    tgt = tmp_path / "tgt"
    f = src / "SimpleFT8_LOG_20260301.adi"
    _write_adif(f, [_make_record()])
    consolidate(src, tgt)
    assert not f.exists()
    assert (tgt / "_konsolidiert" / "SimpleFT8_LOG_20260301.adi").exists()


def test_delete_source_flag(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    tgt = tmp_path / "tgt"
    f = src / "SimpleFT8_LOG_20260301.adi"
    _write_adif(f, [_make_record()])
    consolidate(src, tgt, delete_source=True)
    assert not f.exists()
    assert not (tgt / "_konsolidiert").exists()


def test_glob_pattern_filters_non_matching(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    tgt = tmp_path / "tgt"
    # QRZ-Export-Format — soll ignoriert werden
    _write_adif(src / "da1mhh.410638.20260422132325.adi",
                  [_make_record(call="QRZ_REC")])
    _write_adif(src / "SimpleFT8_LOG_20260301.adi",
                  [_make_record(call="SIMPLEFT8")])
    summary = consolidate(src, tgt)
    archive = tgt / "2026.adi"
    text = archive.read_text()
    assert "SIMPLEFT8" in text
    assert "QRZ_REC" not in text
    # QRZ-Datei bleibt liegen
    assert (src / "da1mhh.410638.20260422132325.adi").exists()


def test_corrupt_source_file_skipped(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    tgt = tmp_path / "tgt"
    (src / "SimpleFT8_LOG_20260301.adi").write_bytes(b"\xff\xfe garbage")
    _write_adif(src / "SimpleFT8_LOG_20260302.adi",
                  [_make_record()])
    summary = consolidate(src, tgt)
    # Eine Datei verarbeitet, eine im Fehler-Bucket
    assert summary["processed_files"] >= 1
    # Korrupte Datei nicht zwingend in errors (wenn parser durchlaeuft mit 0 Records)
    # Wichtig: gute Datei wurde verarbeitet
    assert summary["written_per_year"]["2026"] >= 1


def test_archive_header_only_once(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    tgt = tmp_path / "tgt"
    _write_adif(src / "SimpleFT8_LOG_20260301.adi",
                  [_make_record(time_on="120000")])
    consolidate(src, tgt)
    src2 = tmp_path / "src2"
    src2.mkdir()
    _write_adif(src2 / "SimpleFT8_LOG_20260302.adi",
                  [_make_record(time_on="130000")])
    consolidate(src2, tgt)
    text = (tgt / "2026.adi").read_text()
    # Header-Magic darf nur EINMAL vorkommen
    assert text.count("<EOH>") == 1


def test_atomic_write_basic(tmp_path):
    archive = tmp_path / "2026.adi"
    _atomic_write_archive(archive, ADIF_HEADER, [_make_record()])
    assert archive.exists()
    assert "DA1MHH" in archive.read_text()


def test_atomic_write_no_partial_on_crash(tmp_path, monkeypatch):
    """Wenn os.replace fehlschlaegt, bleibt existing Datei unangetastet."""
    archive = tmp_path / "2026.adi"
    _atomic_write_archive(archive, ADIF_HEADER, [_make_record(call="ORIG")])
    original_text = archive.read_text()

    def fail_replace(*a, **kw):
        raise OSError("simulated crash")
    monkeypatch.setattr(os, "replace", fail_replace)

    try:
        _atomic_write_archive(archive, ADIF_HEADER,
                                [_make_record(call="WOULD_LOSE")])
    except OSError:
        pass
    # Original muss intakt sein
    assert archive.read_text() == original_text
    assert "ORIG" in archive.read_text()
    # Tmpfile wurde aufgeraeumt
    tmps = list(tmp_path.glob(".2026.adi.*.tmp"))
    assert len(tmps) == 0


def test_corrupt_existing_archive_aborts(tmp_path, monkeypatch):
    """R1-KRITISCH: Wenn existing Archiv unlesbar ist, KEIN Move/Schreiben."""
    src = tmp_path / "src"
    src.mkdir()
    tgt = tmp_path / "tgt"
    tgt.mkdir()
    f = src / "SimpleFT8_LOG_20260301.adi"
    _write_adif(f, [_make_record()])
    archive = tgt / "2026.adi"
    archive.write_bytes(b"\xff\xfe corrupt header")

    # Patch parse_adif_file um Exception zu werfen NUR fuer das Archiv
    import adif_archive
    real_parse = adif_archive.parse_adif_file

    def selective_fail(path):
        if path == archive:
            raise ValueError("corrupt")
        return real_parse(path)
    monkeypatch.setattr(adif_archive, "parse_adif_file", selective_fail)

    summary = consolidate(src, tgt)
    # Quelle DARF NICHT verschoben sein
    assert f.exists()
    # Fehler im Summary
    assert any("KRITISCH" in e for e in summary["errors"])


def test_verification_diskrepanz_no_move(tmp_path, monkeypatch):
    """R1-WICHTIG: Wenn Verifikation fehlt -> KEIN Move."""
    src = tmp_path / "src"
    src.mkdir()
    tgt = tmp_path / "tgt"
    f = src / "SimpleFT8_LOG_20260301.adi"
    _write_adif(f, [_make_record()])

    import adif_archive
    real_parse = adif_archive.parse_adif_file
    call_count = [0]

    def mock_parse(path):
        call_count[0] += 1
        # 2. Aufruf (Verifikation nach Schreiben) -> leere Liste zurueck
        if call_count[0] >= 2 and "2026.adi" in str(path):
            return []
        return real_parse(path)
    monkeypatch.setattr(adif_archive, "parse_adif_file", mock_parse)

    summary = consolidate(src, tgt)
    # Quelle darf NICHT verschoben sein
    assert f.exists()
    # Fehler im Summary
    assert any("Verifikation" in e or "Diskrepanz" in e
                for e in summary["errors"])


def test_record_with_missing_year_skipped(tmp_path):
    """Record ohne QSO_DATE wird stillschweigend uebersprungen."""
    src = tmp_path / "src"
    src.mkdir()
    tgt = tmp_path / "tgt"
    f = src / "SimpleFT8_LOG_20260301.adi"
    _write_adif(f, [_make_record(date=""),
                     _make_record(date="20260301", time_on="120100")])
    summary = consolidate(src, tgt)
    # Nur 1 Record (mit Datum) wurde geschrieben
    assert summary["written_per_year"]["2026"] == 1


def test_main_dry_run_returns_zero(tmp_path, capsys, monkeypatch):
    """CLI-Test: --dry-run gibt 0 zurueck bei sauberem Plan."""
    src = tmp_path / "src"
    src.mkdir()
    tgt = tmp_path / "tgt"
    _write_adif(src / "SimpleFT8_LOG_20260301.adi",
                  [_make_record()])
    rc = main(["--source", str(src), "--target", str(tgt), "--dry-run"])
    assert rc == 0
    captured = capsys.readouterr()
    assert "Plan" in captured.out
    # Nichts wurde wirklich geschrieben
    assert not (tgt / "2026.adi").exists()


def test_main_yes_flag_no_prompt(tmp_path, capsys):
    """CLI-Test: --yes ueberspringt Confirm-Prompt."""
    src = tmp_path / "src"
    src.mkdir()
    tgt = tmp_path / "tgt"
    _write_adif(src / "SimpleFT8_LOG_20260301.adi",
                  [_make_record()])
    rc = main(["--source", str(src), "--target", str(tgt), "--yes"])
    assert rc == 0
    assert (tgt / "2026.adi").exists()


def test_konsolidiert_dest_collision(tmp_path):
    """Bei Re-Run mit gleicher Quelldatei -> _dup-Suffix verhindert Overwrite."""
    src = tmp_path / "src"
    src.mkdir()
    tgt = tmp_path / "tgt"
    konsolidiert = tgt / "_konsolidiert"
    konsolidiert.mkdir(parents=True)
    # Pre-existing file im _konsolidiert/ (Vorgaenger-Run-Ueberbleibsel)
    (konsolidiert / "SimpleFT8_LOG_20260301.adi").write_text("OLD")

    f = src / "SimpleFT8_LOG_20260301.adi"
    _write_adif(f, [_make_record()])
    consolidate(src, tgt)
    # Quelle wurde verschoben — alter Datei mit _dup-Suffix
    assert not f.exists()
    assert (konsolidiert / "SimpleFT8_LOG_20260301_dup.adi").exists()
    # Original ueberschrieben? NEIN — alte ist intakt
    assert (konsolidiert / "SimpleFT8_LOG_20260301.adi").read_text() == "OLD"
