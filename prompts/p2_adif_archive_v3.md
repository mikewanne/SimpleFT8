# P2.ADIF-ARCHIVE V3 — Final-Plan (Compact-fest, R1-freigegeben nach Nachbesserung)

**Stand:** 2026-05-08 nach v0.95.19.
**Workflow:** V1 → V2 → R1 (1 KRITISCH + 2 WICHTIG) → **V3** → Compact → Code.
**APP_VERSION:** unangetastet (Tool-only).
**Compact-fest:** Diese Datei enthaelt das vollstaendige Script + Tests.

---

## 1. R1-Findings adressiert

| # | Severity | R1-Finding | V3-Loesung |
|---|---|---|---|
| 1 | 🔴 KRITISCH | Korruptes existing Archiv → Plan muss Abbruch garantieren, nicht ueberschreiben | `try/except` um `parse_adif_file(archive_path)` — bei Fehler **abort** mit Klar-Meldung, KEIN Move/Delete der Quelle, KEIN os.replace. Existing Archiv bleibt unangetastet. |
| 2 | 🟡 WICHTIG | tmpfile MUSS auf gleichem Filesystem | `tempfile.NamedTemporaryFile(dir=target_dir, delete=False)` + `os.replace(tmp, archive)` — atomar nur bei gleichem FS. |
| 3 | 🟡 WICHTIG | Verifikations-Schritt vor Move | Nach `os.replace`: `parse_adif_file(archive_path)` re-lesen, Match-Keys gegen `expected_keys` pruefen. Bei Diskrepanz: KEIN Move. |
| 4 | 🔵 OPTIONAL | Tests 17 → 20 (Korrupte-Archiv-Tests + Verifikations-Tests + leere Felder) | 3 zusaetzliche Tests (siehe §6) |

**Test-Soll:** 955 → **975 erwartet (+20)**.

---

## 2. Vollstaendiges Script (Compact-fest)

```python
#!/usr/bin/env python3
"""tools/adif_archive.py — konsolidiert Tagesdateien zu Jahresarchiven.

Use-Case: nach v0.95.15 werden hochgeladene QSO-Tagesdateien per
shutil.move nach adif/hochgeladen/ verschoben. Dieses Script
konsolidiert sie zu adif/archiv/YYYY.adi (pro Kalenderjahr eine Datei).

Aufruf:
    ./venv/bin/python3 tools/adif_archive.py
        [--source PATH]      # Default: adif/hochgeladen
        [--target PATH]      # Default: adif/archiv
        [--pattern GLOB]     # Default: SimpleFT8_LOG_*.adi
        [--dry-run]          # Nichts schreiben, nur Plan
        [--yes]              # Confirm-Prompt ueberspringen
        [--delete-source]    # Quell-Dateien LOESCHEN statt verschieben

Sicherheits-Garantien:
- Idempotent: Match-Key (CALL, QSO_DATE, TIME_ON) verhindert Duplikate
- Atomic-Write: tmpfile + os.replace (gleiches Filesystem garantiert)
- Datenintegritaet: bei korruptem existing Archiv → Abbruch, nichts schreiben
- Verifikation: nach Schreiben re-lesen + Match-Key-Check
- Default: Quelle wird VERSCHOBEN nach _konsolidiert/ (nicht geloescht)
"""
from __future__ import annotations

import argparse
import os
import sys
import tempfile
from collections import defaultdict
from pathlib import Path
from typing import Iterable

# Bestehender Helper aus log/adif.py wiederverwenden
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from log.adif import parse_adif_file, ADIF_HEADER  # noqa: E402


def _record_key(rec: dict) -> tuple[str, str, str]:
    """Eindeutiger Match-Key fuer Idempotenz (gleich wie delete_qso)."""
    return (rec.get("CALL", ""), rec.get("QSO_DATE", ""),
            rec.get("TIME_ON", ""))


def _record_year(rec: dict) -> str | None:
    """QSO_DATE → Jahr als String. None wenn Datum fehlt/korrupt."""
    date = rec.get("QSO_DATE", "")
    if len(date) >= 4 and date[:4].isdigit():
        return date[:4]
    return None


def _record_to_adif(rec: dict) -> str:
    """Record-Dict zurueck zu ADIF-String. Interne Felder (Underscore-
    Prefix) werden ausgelassen. Reihenfolge wie im Quell-Block."""
    parts = []
    for k, v in rec.items():
        if k.startswith("_"):
            continue
        # Leere Werte sind ADIF-konform (`<CALL:0>`), bleiben drin
        parts.append(f"<{k}:{len(v)}>{v}")
    return "".join(parts) + "<EOR>\n"


def _atomic_write_archive(archive_path: Path, header: str,
                            records: list[dict]) -> None:
    """Atomar in Archiv-Datei schreiben.

    Pattern: NamedTemporaryFile auf gleichem FS (= target_dir) +
    os.replace. POSIX-Garantie: nach replace ist entweder die alte
    oder die neue Datei sichtbar, nie ein zerrissener Zustand.
    """
    target_dir = archive_path.parent
    target_dir.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(
        dir=target_dir, prefix=f".{archive_path.name}.", suffix=".tmp"
    )
    try:
        with os.fdopen(fd, "w") as f:
            f.write(header)
            for rec in records:
                f.write(_record_to_adif(rec))
        os.replace(tmp_path, archive_path)
    except Exception:
        # Bei Crash: tmpfile aufraeumen (existing Archiv bleibt heil)
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def consolidate(source_dir: Path, target_dir: Path,
                  pattern: str = "SimpleFT8_LOG_*.adi",
                  dry_run: bool = False,
                  delete_source: bool = False) -> dict:
    """Hauptlogik. Returnt Summary-Dict mit ausfuehrlichen Status-Daten.

    Sicherheit:
    - Korruptes existing Archiv → KompletAbort (R1-KRITISCH).
    - Verifikations-Schritt nach Schreiben → bei Diskrepanz kein Move.
    """
    summary: dict = {
        "processed_files": 0,
        "skipped_duplicates": 0,
        "written_per_year": defaultdict(int),
        "moved_files": [],
        "deleted_files": [],
        "errors": [],
    }

    if not source_dir.exists():
        summary["errors"].append(f"Quelle existiert nicht: {source_dir}")
        return summary

    # Quell-Dateien per striktem Glob-Pattern (QRZ-Exports ignoriert)
    source_files = sorted(source_dir.glob(pattern))
    if not source_files:
        return summary

    konsolidiert_dir = target_dir / "_konsolidiert"

    for src_file in source_files:
        try:
            source_records = parse_adif_file(src_file)
        except Exception as e:
            summary["errors"].append(f"{src_file.name}: parse error {e}")
            continue
        summary["processed_files"] += 1

        # Pro Jahr gruppieren
        per_year: dict[str, list[dict]] = defaultdict(list)
        for rec in source_records:
            year = _record_year(rec)
            if year:
                per_year[year].append(rec)

        # Pro Jahr sicher mergen
        all_years_ok = True
        for year, recs in per_year.items():
            archive_path = target_dir / f"{year}.adi"

            # R1-KRITISCH: Existing Archiv lesen — bei Fehler ABORT
            existing_records: list[dict] = []
            if archive_path.exists():
                try:
                    existing_records = parse_adif_file(archive_path)
                except Exception as e:
                    summary["errors"].append(
                        f"KRITISCH: existing Archiv {archive_path.name} "
                        f"unlesbar ({e}) — KEINE Aenderung"
                    )
                    all_years_ok = False
                    continue

            existing_keys = {_record_key(r) for r in existing_records}
            new_recs = [r for r in recs
                        if _record_key(r) not in existing_keys]
            duplicate_count = len(recs) - len(new_recs)
            summary["skipped_duplicates"] += duplicate_count

            if not new_recs:
                # Nichts zu schreiben — Quelle ist schon vollstaendig drin
                continue

            summary["written_per_year"][year] += len(new_recs)

            if dry_run:
                continue

            # Atomic-Write: header + existing + new (R1-WICHTIG: tmpfile
            # auf gleichem FS via dir=target_dir)
            merged = existing_records + new_recs
            try:
                _atomic_write_archive(archive_path, ADIF_HEADER, merged)
            except Exception as e:
                summary["errors"].append(
                    f"Schreib-Fehler {archive_path.name}: {e}"
                )
                all_years_ok = False
                continue

            # R1-WICHTIG: Verifikations-Schritt — nach Schreiben re-lesen
            # und Match-Keys pruefen
            try:
                post_records = parse_adif_file(archive_path)
            except Exception as e:
                summary["errors"].append(
                    f"Verifikation fehlgeschlagen {archive_path.name}: {e}"
                )
                all_years_ok = False
                continue
            post_keys = {_record_key(r) for r in post_records}
            expected_keys = {_record_key(r) for r in merged}
            missing = expected_keys - post_keys
            if missing:
                summary["errors"].append(
                    f"Verifikations-Diskrepanz {archive_path.name}: "
                    f"{len(missing)} Records fehlen — KEIN Move/Delete"
                )
                all_years_ok = False

        # Quelle nur behandeln wenn ALLE Jahres-Archive sauber waren
        if not dry_run and all_years_ok:
            if delete_source:
                src_file.unlink()
                summary["deleted_files"].append(str(src_file))
            else:
                konsolidiert_dir.mkdir(parents=True, exist_ok=True)
                dest = konsolidiert_dir / src_file.name
                # Kollision vermeiden: bei Re-Run kann dest schon existieren
                if dest.exists():
                    dest = konsolidiert_dir / f"{src_file.stem}_dup{src_file.suffix}"
                src_file.rename(dest)
                summary["moved_files"].append(str(dest))

    return summary


def _format_summary(summary: dict, dry_run: bool, delete_source: bool) -> str:
    """Lesbares CLI-Output-Format (V2 L10 Spec)."""
    lines = []
    if summary["errors"]:
        lines.append("⚠ FEHLER:")
        for e in summary["errors"]:
            lines.append(f"  - {e}")
        lines.append("")

    lines.append(f"Verarbeitet: {summary['processed_files']} Quell-Dateien")
    if summary["skipped_duplicates"]:
        lines.append(f"Duplikate uebersprungen: {summary['skipped_duplicates']}")

    if summary["written_per_year"]:
        lines.append("Geschrieben pro Jahr:")
        for year in sorted(summary["written_per_year"]):
            count = summary["written_per_year"][year]
            lines.append(f"  {year}.adi: +{count} Records")
    else:
        lines.append("Keine neuen Records (alles bereits archiviert).")

    if not dry_run:
        if delete_source and summary["deleted_files"]:
            lines.append(f"Quell-Dateien geloescht: {len(summary['deleted_files'])}")
        elif summary["moved_files"]:
            lines.append(
                f"Quell-Dateien verschoben nach _konsolidiert/: "
                f"{len(summary['moved_files'])}"
            )

    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--source", type=Path,
                          default=Path("adif/hochgeladen"),
                          help="Quell-Verzeichnis (Default: adif/hochgeladen)")
    parser.add_argument("--target", type=Path,
                          default=Path("adif/archiv"),
                          help="Ziel-Verzeichnis (Default: adif/archiv)")
    parser.add_argument("--pattern", type=str,
                          default="SimpleFT8_LOG_*.adi",
                          help="Glob-Pattern (Default: SimpleFT8_LOG_*.adi)")
    parser.add_argument("--dry-run", action="store_true",
                          help="Nichts schreiben, nur Plan-Summary")
    parser.add_argument("--yes", action="store_true",
                          help="Confirm-Prompt ueberspringen")
    parser.add_argument("--delete-source", action="store_true",
                          help="Quell-Dateien LOESCHEN statt verschieben")
    args = parser.parse_args(argv)

    # Phase 1: Dry-Run um Plan auszugeben
    plan = consolidate(args.source, args.target,
                          pattern=args.pattern, dry_run=True)
    print("ADIF-Archive — Plan")
    print(f"Quelle: {args.source} (Pattern: {args.pattern})")
    print(f"Ziel:   {args.target}")
    print()
    print(_format_summary(plan, dry_run=True, delete_source=args.delete_source))
    print()

    if args.dry_run:
        return 0 if not plan["errors"] else 1

    if not plan["written_per_year"] and not plan["errors"]:
        print("Nichts zu tun.")
        return 0

    if plan["errors"]:
        print("⚠ Fehler im Plan — Abbruch.")
        return 1

    # Phase 2: Bestaetigung
    if not args.yes:
        try:
            answer = input("Fortfahren? [y/N]: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            answer = ""
        if answer != "y":
            print("Abgebrochen.")
            return 0

    # Phase 3: Real-Run
    real = consolidate(args.source, args.target,
                          pattern=args.pattern, dry_run=False,
                          delete_source=args.delete_source)
    print()
    print("ADIF-Archive — Ergebnis")
    print(_format_summary(real, dry_run=False, delete_source=args.delete_source))
    return 0 if not real["errors"] else 1


if __name__ == "__main__":
    sys.exit(main())
```

---

## 3. Tests (NEU `tests/test_adif_archive.py` — 20 Tests)

```python
"""Tests fuer tools/adif_archive.py — Konsolidierung Tagesdateien zu
Jahresarchiven. Hardware-frei, kein Qt noetig.
"""
from __future__ import annotations

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
    assert summary["processed_files"] == 1
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
    """R1-WICHTIG: Wenn Verifikation fehlt → KEIN Move."""
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
        # 2. Aufruf (Verifikation nach Schreiben) → leere Liste zurueck
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
    """Bei Re-Run mit gleicher Quelldatei → _dup-Suffix verhindert Overwrite."""
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
```

**Wichtig:** Imports am File-Top brauchen `import os` (fuer monkeypatch in
`test_atomic_write_no_partial_on_crash` und `test_corrupt_existing_archive_aborts`).
V3-Code-Tests fuegen `import os` zum File-Top hinzu.

---

## 4. Implementations-Reihenfolge (nach Compact)

1. **Files lesen** (Verifikation):
   - `prompts/p2_adif_archive_v3.md` (diese Datei)
   - `log/adif.py:1-63` (ADIF_HEADER, parse_adif_file)
   - `tools/deepseek_review.py` als Vorbild fuer tools/-Script-Struktur
2. **NEU `tools/adif_archive.py`** — komplettes Script aus §2 anwenden.
3. **NEU `tests/test_adif_archive.py`** — 20 Tests aus §3 anwenden.
4. **Smoke-Test:** `./venv/bin/python3 tools/adif_archive.py --dry-run` —
   Skript laeuft ohne Crash bei leerem `adif/hochgeladen/`.
5. **Tests laufen:** `955 → 975 erwartet gruen` (+20).
6. **Final-R1-Codereview:**
   ```bash
   echo "Reviewe tools/adif_archive.py final-Code (P2.ADIF-ARCHIVE).
   3 Sicherheits-Garantien: Idempotenz, Atomic-Write, Verifikation vor
   Move. R1-KRITISCH-Befund (korruptes existing Archiv) adressiert via
   try/except + Abort. R1-WICHTIG (tmpfile FS) via tempfile.mkstemp(dir=...)." | \
   ./venv/bin/python3 tools/deepseek_review.py \
   tools/adif_archive.py tests/test_adif_archive.py log/adif.py
   ```
7. **Atomare Commits — 1 Code + 1 Doku:**
   - Code: `P2.ADIF-ARCHIVE: Standalone-Tool tools/adif_archive.py + 20 Tests`
   - Doku: `docs (P2.ADIF-ARCHIVE): HISTORY+HANDOFF+CLAUDE+TODO+Memory`
8. **Doku-Updates** (HISTORY beide Pfade, HANDOFF beide, CLAUDE beide, Memory).
9. **KEIN Push noetig** — Mike kann es lokal nutzen, Push zusammen mit
   v0.95.16-19 + ggf. weiteren Bundles.
10. **Lessons-Learned**.

---

## 5. Akzeptanz-Checkliste (final)

```
- [ ] tools/adif_archive.py NEU mit allen Sicherheits-Garantien
- [ ] R1-KRITISCH adressiert: korruptes existing Archiv → Abort
- [ ] R1-WICHTIG adressiert: tmpfile auf gleichem FS via dir=
- [ ] R1-WICHTIG adressiert: Verifikations-Schritt nach Schreiben
- [ ] Glob-Pattern strikt SimpleFT8_LOG_*.adi (Default)
- [ ] CLI: --source --target --pattern --dry-run --yes --delete-source
- [ ] Default-Verhalten: Verschieben nach _konsolidiert/ (nicht loeschen)
- [ ] Confirm-Prompt + --yes-Flag fuer Automation
- [ ] tests/test_adif_archive.py NEU mit 20 Tests
- [ ] Smoke-Test ohne hochgeladen/-Verzeichnis: no-op exit 0
- [ ] Tests gesamt: 955 → 975 gruen
- [ ] Final-R1 ohne KP-Findings
- [ ] HISTORY/HANDOFF/CLAUDE updated (beide Pfade)
- [ ] 1 Code-Commit + 1 Doku-Commit
- [ ] Memory-File ✅
```

---

## 6. Risiken & Notbremse

- **Datenverlust durch Idempotenz-Bug:** Default Move (nicht Delete) +
  Verifikations-Schritt sind 2 Schutzmechanismen. R1-KRITISCH-Pfad
  fuer korruptes Archiv → Abort statt Schreiben.
- **Race-Condition (App schreibt waehrend Tool laeuft):** Doku-Hinweis
  „App schliessen vor Tool-Run" reicht (KISS, Hobby-1-User-Workflow).
- **`_konsolidiert/`-Verzeichnis-Bloat:** Mike loescht manuell wenn er
  sich sicher ist. Doku-Hinweis im Tool-Help-Text.
- **Quell-Pattern zu strikt:** `--pattern` als Override fuer Edge-Cases.

---

## 7. Lessons-Learned-Vorschlaege

1. **Standalone-Tools:** Atomic-Write (`tempfile.mkstemp(dir=)` +
   `os.replace`) + Verifikations-Schritt ist Pflicht-Pattern bei
   Datei-Konsolidierung.
2. **R1-Verdienst:** „Korruptes existing-Archiv" ist Edge-Case den Mike
   und ich beide uebersehen haetten. Ohne R1-Plan-Review waere Datenverlust
   moeglich gewesen.
3. **KISS bei Hobby-Tools:** Lockfile-Mechanismus war ueberlegt + verworfen
   (V2 L9). Atomic-Write reicht — 1-User-Workflow.

Memory-Vorschlaege:
- `feedback_atomic_write_pattern.md` — bei jedem File-Konsolidierungs-
  Tool: tmpfile + os.replace + Verifikation. Korruptes existing-File
  → Abort, nicht ueberschreiben.

---

## 8. Field-Test-Plan

**Hardware-frei** — kein Funkbetrieb noetig:
1. Smoke-Test: `--dry-run` mit leerem `adif/hochgeladen/` → exit 0.
2. Smoke-Test: `--dry-run` mit existierenden Tagesdateien → Plan-Ausgabe.
3. Real-Test: 1 echte Tagesdatei (Mike's eigene Daten) →
   Archiv erstellt, Quell-Datei in `_konsolidiert/`.
4. Idempotenz-Test: 2. Lauf mit gleichem Inhalt → keine Duplikate.

**Freigabe-Kriterium:** alle 4 Smoke-Tests OK + Mike's „passt".

---

**V3-Ende. Bereit fuer Compact + Code.**
