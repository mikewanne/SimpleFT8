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
- Datenintegritaet: bei korruptem existing Archiv -> Abbruch, nichts schreiben
- Verifikation: nach Schreiben re-lesen + Match-Key-Check
- Default: Quelle wird VERSCHOBEN nach _konsolidiert/ (nicht geloescht)

NICHT fuer parallele Ausfuehrung ausgelegt. Bei zwei gleichzeitigen
Instanzen kann es zu Lost-Update kommen (KISS-Entscheidung,
1-User-Hobby-Workflow). Mike soll App schliessen vor Tool-Run.
"""
from __future__ import annotations

import argparse
import os
import sys
import tempfile
from collections import defaultdict
from pathlib import Path

# Bestehender Helper aus log/adif.py wiederverwenden
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from log.adif import parse_adif_file, ADIF_HEADER  # noqa: E402


def _record_key(rec: dict) -> tuple[str, str, str]:
    """Eindeutiger Match-Key fuer Idempotenz (gleich wie delete_qso)."""
    return (rec.get("CALL", ""), rec.get("QSO_DATE", ""),
            rec.get("TIME_ON", ""))


def _record_year(rec: dict) -> str | None:
    """QSO_DATE -> Jahr als String. None wenn Datum fehlt/korrupt."""
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
        # None-Schutz (Final-R1 SOLLTE): Parser koennte None liefern,
        # str() fixt das. Leere Werte sind ADIF-konform (`<CALL:0>`).
        v = str(v) if v is not None else ""
        parts.append(f"<{k}:{len(v)}>{v}")
    return "".join(parts) + "<EOR>\n"


def _atomic_write_archive(archive_path: Path, header: str,
                            records: list[dict]) -> None:
    """Atomar in Archiv-Datei schreiben.

    Pattern: tempfile.mkstemp auf gleichem FS (= target_dir) +
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
    - Korruptes existing Archiv -> KomplettAbort (R1-KRITISCH).
    - Verifikations-Schritt nach Schreiben -> bei Diskrepanz kein Move.
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
