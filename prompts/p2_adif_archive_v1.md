# P2.ADIF-ARCHIVE V1 — Standalone Helper-Script (Diagnose)

**Stand:** 2026-05-08 nach v0.95.19.
**Ziel:** `tools/adif_archive.py` schreiben — konsolidiert Tagesdateien aus
`adif/hochgeladen/` in Jahresarchive `adif/archiv/YYYY.adi`.
**Vorgaenger:** v0.95.15 (P1.QRZ-UPLOAD-UI-2) hat File-Move nach
`adif/hochgeladen/` eingefuehrt — Tagesdateien stapeln sich dort.
**APP_VERSION-Ziel:** unangetastet (Tool-only, keine App-Aenderung).

---

## 1. Mike-Anforderung (07.05.2026)

> „`tools/adif_archive.py` schreiben — konsolidiert Tagesdateien aus
> `adif/hochgeladen/` in Jahresarchive `archiv/2024.adi`/`2025.adi`.
> Separater Workflow nach v0.95.15-Field-Test (klein genug ohne Compact)."

Use-Case:
- Nach Bulk-Upload an QRZ.com werden erfolgreich hochgeladene
  Tagesdateien (`SimpleFT8_LOG_YYYYMMDD.adi`) per `shutil.move` nach
  `adif/hochgeladen/` verschoben (v0.95.15).
- Ueber Wochen/Monate sammeln sich dort viele Tagesdateien.
- Mike will sie pro Kalenderjahr in EINE Datei zusammenfassen — bessere
  Uebersicht, weniger File-Bloat.

---

## 2. Symptom / Status quo

Aktuell: nach erfolgreichem QRZ-Bulk-Upload landet die Tagesdatei in
`adif/hochgeladen/SimpleFT8_LOG_YYYYMMDD.adi` und bleibt dort dauerhaft.
Verzeichnis-Stand 08.05.: existiert noch nicht (kein Bulk-Upload bisher
nach v0.95.15-Field-Test). Nach Push + Mike-Field-Test wird es sich
fuellen.

Datei-Format: ADIF 3.1.7 (gleicher Header wie `log/adif.py:9-14`).
Records: pro QSO ein `<EOR>`-terminierter Block.

---

## 3. Anforderungen

### 3.1 Funktional

1. **Quelle:** Default `adif/hochgeladen/*.adi`, ueberschreibbar via
   `--source`-Argument.
2. **Ziel:** Default `adif/archiv/YYYY.adi`, ueberschreibbar via
   `--target`-Argument. Pro QSO_DATE-Jahr eine Datei.
3. **Konsolidierung:** Records aus Quell-Datei parsen, nach QSO_DATE-Jahr
   gruppieren, in passende Jahres-Archiv-Datei anhaengen.
4. **Header:** Wenn Jahres-Archiv neu erstellt wird, ADIF-Header schreiben.
   Sonst nur Records anhaengen (vor `<EOR>`-Endungen).
5. **Idempotenz:** Wenn eine Quell-Datei schon archiviert wurde
   (z.B. Mike laesst Script nochmal laufen), KEINE doppelten Records.
   Mechanismus: Match-Key `(CALL, QSO_DATE, TIME_ON)` (gleich wie
   `log/adif.py:75-78` `delete_qso`-Identifikation).
6. **Quell-Datei nach Konsolidierung:** drei Optionen, Mike entscheidet:
   - **(a) Loeschen** — saubererer Workflow, aber unwiederbringlich
   - **(b) Verschieben nach `adif/archiv/_archiviert/`** — sicher,
     aber Verzeichnis-Bloat
   - **(c) Behalten** — Default, manuelles Loeschen durch Mike
7. **Dry-Run-Mode:** `--dry-run` zeigt was passieren WUERDE, ohne
   Aenderungen zu schreiben.
8. **CLI-Output:** klar lesbar — Anzahl Quell-Dateien, Records pro Jahr,
   Duplikate, geschriebene Dateien.

### 3.2 Nicht-Funktional

- **Hardware-frei:** keine Radio-Abhaengigkeit, kein Qt, nur `pathlib`
  + `re` + bestehender `parse_adif_file`-Helper aus `log/adif.py`.
- **Standalone:** lauffaehig via `./venv/bin/python3 tools/adif_archive.py`,
  KEIN Bestandteil der App-Runtime.
- **Idempotent:** mehrfache Ausfuehrung darf keinen Schaden anrichten.
- **Performant:** O(n) — keine quadratischen Schleifen (Lesson aus
  v0.95.18 Bug-A `delete_qso` O(n²)→O(n)).

---

## 4. Akzeptanzkriterien

- AC-1.1: Skript laeuft via `./venv/bin/python3 tools/adif_archive.py`
  ohne Fehler bei leerem `adif/hochgeladen/`-Verzeichnis (no-op).
- AC-1.2: Bei 5 Tagesdateien aus 2026 → `adif/archiv/2026.adi` mit
  allen Records, Header korrekt.
- AC-1.3: Tagesdatei mit QSOs aus 2 Kalenderjahren (Mitternacht-Uebergang)
  → 2 Archiv-Dateien, jeweils nur passende Records.
- AC-1.4: Zweiter Lauf mit denselben Tagesdateien → keine doppelten
  Records, keine Aenderung der Archiv-Datei (idempotent).
- AC-1.5: `--dry-run` schreibt keine Datei, gibt Plan-Summary aus.
- AC-1.6: Bei korrupter Quell-Datei: Fehler ausgeben, andere Dateien
  weiter verarbeiten (keine Crash).
- AC-1.7: ADIF-Header in Archiv-Datei nur EINMAL (nicht pro Lauf neu
  prepended).

---

## 5. Implementations-Skizze

```python
#!/usr/bin/env python3
"""tools/adif_archive.py — konsolidiert Tagesdateien zu Jahresarchiven.

Use-Case: nach v0.95.15 werden hochgeladene QSO-Tagesdateien nach
adif/hochgeladen/ verschoben. Dieses Script konsolidiert sie zu
adif/archiv/YYYY.adi (pro Kalenderjahr eine Datei).

Aufruf:
    ./venv/bin/python3 tools/adif_archive.py [--source PATH] [--target PATH]
                                              [--dry-run] [--delete-source]

Idempotent: Match-Key (CALL, QSO_DATE, TIME_ON) verhindert Duplikate.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from collections import defaultdict

# Bestehender Helper aus log/adif.py wiederverwenden
sys.path.insert(0, str(Path(__file__).parent.parent))
from log.adif import parse_adif_file, ADIF_HEADER


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
    """Record-Dict zurueck zu ADIF-String konvertieren.

    Interne Felder (mit Underscore-Prefix wie _SOURCE_FILE) werden
    ausgelassen. Reihenfolge wie im Quell-Block.
    """
    parts = []
    for k, v in rec.items():
        if k.startswith("_"):
            continue
        parts.append(f"<{k}:{len(v)}>{v}")
    return "".join(parts) + "<EOR>\n"


def _read_existing_archive_keys(archive_path: Path) -> set:
    """Match-Keys aller bereits archivierten Records lesen."""
    if not archive_path.exists():
        return set()
    return {_record_key(r) for r in parse_adif_file(archive_path)}


def consolidate(source_dir: Path, target_dir: Path,
                 dry_run: bool = False,
                 delete_source: bool = False) -> dict:
    """Hauptlogik. Returnt Summary-Dict."""
    if not source_dir.exists():
        return {"error": f"Quelle existiert nicht: {source_dir}"}

    target_dir.mkdir(parents=True, exist_ok=True)
    summary = {"processed_files": 0, "skipped_duplicates": 0,
               "written_per_year": defaultdict(int), "errors": []}

    for src_file in sorted(source_dir.glob("*.adi")):
        try:
            records = parse_adif_file(src_file)
        except Exception as e:
            summary["errors"].append(f"{src_file.name}: {e}")
            continue
        summary["processed_files"] += 1

        # Pro Jahr gruppieren
        per_year = defaultdict(list)
        for rec in records:
            year = _record_year(rec)
            if year:
                per_year[year].append(rec)

        # Pro Jahr in Archiv-Datei mergen
        for year, recs in per_year.items():
            archive_path = target_dir / f"{year}.adi"
            existing_keys = _read_existing_archive_keys(archive_path)
            new_recs = [r for r in recs
                        if _record_key(r) not in existing_keys]
            summary["skipped_duplicates"] += len(recs) - len(new_recs)
            summary["written_per_year"][year] += len(new_recs)

            if dry_run or not new_recs:
                continue

            # Schreiben — Header nur wenn neue Datei
            if not archive_path.exists():
                archive_path.write_text(ADIF_HEADER)
            with archive_path.open("a") as f:
                for rec in new_recs:
                    f.write(_record_to_adif(rec))

        # Quelle behandeln
        if delete_source and not dry_run:
            src_file.unlink()

    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path,
                        default=Path("adif/hochgeladen"),
                        help="Quell-Verzeichnis (Default: adif/hochgeladen)")
    parser.add_argument("--target", type=Path,
                        default=Path("adif/archiv"),
                        help="Ziel-Verzeichnis (Default: adif/archiv)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Nichts schreiben, nur Plan ausgeben")
    parser.add_argument("--delete-source", action="store_true",
                        help="Quell-Dateien nach Konsolidierung loeschen")
    args = parser.parse_args()

    summary = consolidate(args.source, args.target,
                          dry_run=args.dry_run,
                          delete_source=args.delete_source)
    # ... Summary-Output (TBD V2)
```

---

## 6. Tests (geplant: ~10)

1. `test_empty_source_dir` — leeres `hochgeladen/` → no-op.
2. `test_single_year_consolidation` — 3 Tagesdateien aus 2026 →
   1 Archiv `2026.adi` mit allen Records + Header.
3. `test_multi_year_split` — 1 Tagesdatei mit Records aus 2025 + 2026
   (Mitternacht-Uebergang) → 2 Archive.
4. `test_idempotent_second_run` — derselbe Lauf 2× → keine Duplikate.
5. `test_dry_run_no_write` — `--dry-run` → keine Datei geaendert,
   Summary korrekt.
6. `test_delete_source_flag` — `--delete-source` → Quell-Dateien weg.
7. `test_corrupt_source_file_skipped` — eine Datei kaputt, andere
   verarbeitet, Fehler in Summary.
8. `test_record_key_uniqueness` — Helper-Test, gleiche (CALL, DATE,
   TIME_ON) collision.
9. `test_record_year_extraction` — `_record_year` mit Edge-Cases
   (leeres Datum, kurzes Datum, korruptes Datum).
10. `test_archive_header_only_once` — 2× Lauf → Header nur einmal in
    Archiv-Datei.

---

## 7. Offene Fragen fuer V2

1. **Quell-Datei nach Konsolidierung — Default-Verhalten?** Behalten
   (Option c, Mike loescht manuell) oder Verschieben in
   `adif/archiv/_archiviert/` (Option b, sicher) — V2 entscheidet.
2. **Archiv-Verzeichnis-Pfad:** `adif/archiv/` (TODO-Wortwahl) oder
   anderswo? Mike's TODO sagt „archiv/2024.adi" — relativ zum
   SimpleFT8-Root? Klaeren.
3. **Idempotenz-Match-Key:** Reicht `(CALL, QSO_DATE, TIME_ON)` oder
   sollte BAND/MODE auch rein (Multi-QSO mit gleicher Station gleicher
   Sekunde unterschiedliches Band)? Realistisch sehr selten.
4. **Auto-Run vs Manual:** Soll das Script per Cronjob/Settings-Button
   automatisch laufen oder nur on-demand? Mike's TODO sagt „separater
   Workflow", impliziert manuell. → V2 bestaetigt.
5. **App-Integration:** Settings-Button „Archiv konsolidieren" oder
   reines CLI? KISS spricht fuer CLI-only.
6. **`_record_to_adif` Konsistenz:** Quell-Records verlieren beim
   Re-Schreiben evtl. ihre exakte Feld-Reihenfolge — relevant?
   ADIF-Spec sagt: Reihenfolge irrelevant. → V2 bestaetigt.
7. **QRZ-Exports im `adif/`-Wurzel:** Dateien wie
   `da1mhh.410638.20260422132325.adi` (QRZ-Originale). Sollen die
   auch konsolidiert werden? Wahrscheinlich NICHT (Mike's eigene
   Backups, sollten unangetastet bleiben). → V2 bestaetigt.

---

## 8. Workflow-Bewertung

**Trigger fuer vollen V1→V2→R1→V3-Workflow:**
- ✅ Beruehrt mehrere Logik-Schichten (Parse, Group, Idempotenz, IO,
  CLI, Tests)
- ✅ Persistence/IO neu beteiligt (Read + Append + optional Move/Delete)
- ✅ Standalone-Modul → Architektur-Klaerung sinnvoll
- ✅ ≥2 unabhaengige Akzeptanzkriterien (7 ACs)
- ✅ Mike-Compact-Wunsch zwischen Plan und Code

**Tests-Erwartung:** 955 → ~965 (+10 in `tests/test_adif_archive.py`).

**Atomare Commits:** 1 Code-Commit (Tool + Tests) + 1 Doku-Commit
(HISTORY/HANDOFF/CLAUDE/TODO + memory update).

---

## 9. Risiken

- **Datenverlust bei `--delete-source`:** Wenn Idempotenz-Logik bricht,
  Records weg ohne Backup. → Mitigation: Default `delete_source=False`,
  klares Confirmation-Prompt.
- **ADIF-Format-Varianten:** Manche Tools schreiben `<eor>` lowercase,
  manche mit Linebreaks. `parse_adif_file` ist case-insensitive,
  sollte robust sein. Verifikation in V2.
- **Race-Condition mit App:** Wenn App gleichzeitig in
  `adif/hochgeladen/` schreibt waehrend Script laeuft. → Mitigation:
  KISS: Mike laesst Script nur laufen wenn App zu ist (Doku-Hinweis).

---

**V1-Ende. V2-Self-Review folgt.**
