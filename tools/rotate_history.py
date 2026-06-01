#!/usr/bin/env python3
"""Rotiert HISTORY.md: behaelt die KEEP neuesten Versions-Eintraege in HISTORY.md,
archiviert alle aelteren nach history/HISTORY_archiv_NN.md.

Sicherheit:
  * Byte-genaue Verifikation — die Menge der Eintrags-Bloecke (unveraendert) muss
    vor und nach der Rotation identisch sein, sonst Abbruch OHNE zu schreiben.
  * Backup der alten HISTORY.md vor jedem Schreiben.
  * Dry-Run ist Default; echtes Schreiben nur mit --apply.

Aufruf:
  ./venv/bin/python3 tools/rotate_history.py            # DRY-RUN (zeigt nur)
  ./venv/bin/python3 tools/rotate_history.py --apply     # fuehrt Rotation aus

Eintrags-Erkennung: jede Zeile '## YYYY-MM-DD vX.YY.ZZ — ...' startet einen Eintrag.
Unter-Ueberschriften (## ...) innerhalb eines Eintrags zaehlen NICHT als Grenze.
"""
import re
import sys
import shutil
from datetime import date
from pathlib import Path

KEEP = 30          # neueste Versionen, die in HISTORY.md bleiben
MIN_BATCH = 10     # erst rotieren, wenn mind. so viele Eintraege ueberhaengen

ROOT = Path(__file__).resolve().parent.parent
HISTORY = ROOT / "HISTORY.md"
ARCHIVE_DIR = ROOT / "history"

# Versions-Header: '## 2026-05-31 v0.98.49 — ...'
ENTRY_RE = re.compile(r"^## (20\d\d-\d\d-\d\d) v(\d+)\.(\d+)(?:\.(\d+))?\b")


def parse(lines):
    starts = [i for i, ln in enumerate(lines) if ENTRY_RE.match(ln)]
    if not starts:
        sys.exit("FEHLER: keine Versions-Eintraege ('## YYYY-MM-DD vX.Y.Z') gefunden.")
    head = lines[:starts[0]]
    entries = []
    for k, s in enumerate(starts):
        e = starts[k + 1] if k + 1 < len(starts) else len(lines)
        m = ENTRY_RE.match(lines[s])
        entries.append({
            "ver": (int(m.group(2)), int(m.group(3)), int(m.group(4) or 0)),
            "date": m.group(1),
            "header": lines[s].rstrip("\n"),
            "text": "".join(lines[s:e]),
        })
    return head, entries


def next_archive_path():
    ARCHIVE_DIR.mkdir(exist_ok=True)
    existing = sorted(ARCHIVE_DIR.glob("HISTORY_archiv_*.md"))
    n = 1
    if existing:
        nums = [int(re.search(r"_(\d+)\.md$", p.name).group(1)) for p in existing
                if re.search(r"_(\d+)\.md$", p.name)]
        n = (max(nums) + 1) if nums else 1
    return ARCHIVE_DIR / f"HISTORY_archiv_{n:02d}.md"


def vstr(v):
    return "v%d.%d.%d" % v


def main():
    apply = "--apply" in sys.argv
    raw = HISTORY.read_text(encoding="utf-8")
    lines = raw.splitlines(keepends=True)
    head, entries = parse(lines)

    # absteigend nach Version (stabil -> Duplikate behalten Datei-Reihenfolge)
    order = sorted(range(len(entries)), key=lambda i: entries[i]["ver"], reverse=True)
    ordered = [entries[i] for i in order]
    active = ordered[:KEEP]
    archive = ordered[KEEP:]

    # ---- VERIFIKATION 1: kein Eintrag verloren / veraendert ----
    before = sorted(e["text"] for e in entries)
    after = sorted(e["text"] for e in (active + archive))
    assert before == after, "VERIFIKATION FEHLGESCHLAGEN: Eintragsmenge veraendert!"
    assert len(active) + len(archive) == len(entries)

    def chars(items):
        return sum(len(e["text"]) for e in items)

    print("HISTORY.md: %d Eintraege, %d chars gesamt" % (len(entries), len(raw)))
    print("  aktiv  (KEEP=%d): %d Eintraege | %s .. %s | %d chars"
          % (KEEP, len(active), vstr(active[-1]["ver"]), vstr(active[0]["ver"]), chars(active)))
    print("  Archiv:           %d Eintraege | %s .. %s | %d chars"
          % (len(archive), vstr(archive[-1]["ver"]) if archive else "-",
             vstr(archive[0]["ver"]) if archive else "-", chars(archive)))
    print("  Kopf: %d Zeilen" % len(head))

    if len(archive) < MIN_BATCH:
        print("\nNichts zu tun: nur %d Eintraege ueber KEEP (Schwelle MIN_BATCH=%d)."
              % (len(archive), MIN_BATCH))
        return

    if not apply:
        print("\n[DRY-RUN] Nichts geschrieben. Zum Ausfuehren: --apply")
        return

    today = date.today().isoformat()
    arch_path = next_archive_path()
    arch_no = re.search(r"_(\d+)\.md$", arch_path.name).group(1)

    # ---- Archiv-Datei schreiben ----
    arch_head = (
        "# SimpleFT8 — Aenderungshistorie (Archiv %s)\n\n"
        "Aus HISTORY.md rotiert am %s. Enthaelt die Versionen %s .. %s.\n"
        "Nur zum Nachschlagen (grep) — die aktive Historie steht in ../HISTORY.md.\n\n"
        % (arch_no, today, vstr(archive[-1]["ver"]), vstr(archive[0]["ver"]))
    )
    arch_path.write_text(arch_head + "".join(e["text"] for e in archive), encoding="utf-8")

    # ---- neue HISTORY.md schreiben (Backup vorher) ----
    backup = HISTORY.with_suffix(".md.bak-%s" % today)
    shutil.copy2(HISTORY, backup)
    rot_note = (
        "> **Rotation:** Diese Datei fuehrt nur die letzten %d Versionen. Aeltere Eintraege\n"
        "> stehen in `history/HISTORY_archiv_NN.md` (grep dort, falls eine alte Version\n"
        "> gesucht wird). Rotiert mit `tools/rotate_history.py`. Zuletzt: %s.\n\n"
        % (KEEP, today)
    )
    HISTORY.write_text("".join(head) + rot_note + "".join(e["text"] for e in active),
                       encoding="utf-8")

    # ---- VERIFIKATION 2: zurueckgelesene Bloecke == Original ----
    check = []
    for f in [HISTORY] + sorted(ARCHIVE_DIR.glob("HISTORY_archiv_*.md")):
        _, ents = parse(f.read_text(encoding="utf-8").splitlines(keepends=True))
        check.extend(e["text"] for e in ents)
    assert sorted(check) == before, \
        "NACH-VERIFIKATION FEHLGESCHLAGEN — Backup unter %s, NICHT vertrauen!" % backup

    print("\n[APPLY] OK.")
    print("  Backup:  %s" % backup.name)
    print("  Archiv:  history/%s (%d Eintraege)" % (arch_path.name, len(archive)))
    print("  HISTORY.md: %d Eintraege, %d chars" % (len(active), HISTORY.stat().st_size))
    print("  Nach-Verifikation: alle %d Eintraege erhalten." % len(before))


if __name__ == "__main__":
    main()
