#!/usr/bin/env python3
"""P169 Migrations-TROCKENLAUF — read-only Analyse von adif/.

Schreibt/löscht/verschiebt NICHTS. Inspiziert alle .adi-Dateien unter adif/,
schlägt pro Ordner ein Migrationsziel (importiert/neu/hochgeladen) vor, zeigt
welche Stationen NUR in nicht-geladenen Ordnern leben (sonst Verlust-Gefahr) und
zieht die Vorher-Bilanz für die spätere Diff-Verifikation.

Aufruf: ./venv/bin/python3 tools/analyze_adif_migration.py
"""
import sys
from pathlib import Path
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from log.adif import parse_adif_file  # noqa: E402

ADIF = Path("adif")

# Aktuell vom Filter-Index GELADENE Ordner (main_window.py:241-254):
#   cwd (=SimpleFT8/, keine .adi), adif/hochgeladen/, adif/_backup_qrz_export/
LOADED_DIRS = {"hochgeladen", "_backup_qrz_export"}

# Vorgeschlagenes Migrationsziel je Top-Level-Unterordner unter adif/.
#   importiert  = schon auf QRZ / historisch  → kein Re-Upload
#   hochgeladen = App-QSOs die bereits hochgeladen wurden
#   neu         = frische App-QSOs, evtl. noch hochzuladen
#   (skip)      = reiner Output, nicht als Quelle migrieren (aber auf Uniques prüfen)
PROPOSED = {
    "_backup_qrz_export": "importiert",
    "hochgeladen":        "hochgeladen",
    "repaired":           "importiert",   # historische, reparierte Logs
    "archiv":             "importiert",
    "archiv/_konsolidiert": "importiert",
    "exports":            "(skip-output)",
    "adif":               "(doppelt-verschachtelt → prüfen)",
    "adif/exports":       "(skip-output)",
    "<root>":             "neu",           # lose .adi direkt in adif/
}


def mode_of(rec):
    m = (rec.get("SUBMODE") or rec.get("MODE") or "").strip().upper()
    return m


def rel_folder(p: Path) -> str:
    r = p.relative_to(ADIF).parent
    return "<root>" if str(r) == "." else str(r)


def main():
    if not ADIF.is_dir():
        print(f"FEHLER: {ADIF.resolve()} existiert nicht (aus SimpleFT8/ starten).")
        return

    files = sorted(ADIF.rglob("*.adi"))
    print(f"=== TROCKENLAUF: {len(files)} .adi-Dateien unter {ADIF.resolve()} ===\n")

    per_folder = defaultdict(lambda: {"files": 0, "qsos": 0, "calls": set(),
                                      "cbm": set(), "modes": defaultdict(int),
                                      "dates": [], "nofield": 0})
    # globale Mengen für Bilanz
    all_cb = set()                  # (call, band) gesamt
    all_cbm = set()                 # (call, band, mode) gesamt
    loaded_cb = set()               # (call, band) in aktuell geladenen Ordnern
    cb_to_folders = defaultdict(set)  # (call,band) → in welchen Ordnern

    for f in files:
        folder = rel_folder(f)
        top = folder.split("/")[0]
        st = per_folder[folder]
        st["files"] += 1
        try:
            recs = parse_adif_file(f)
        except Exception as e:
            print(f"  ⚠ Parse-Fehler {f}: {e}")
            continue
        for rec in recs:
            call = (rec.get("CALL", "") or "").strip().upper().split("/")[0]
            band = (rec.get("BAND", "") or "").strip().upper()
            mode = mode_of(rec)
            date = (rec.get("QSO_DATE", "") or "").strip()
            st["qsos"] += 1
            if not call or not band:
                st["nofield"] += 1
                continue
            st["calls"].add(call)
            st["modes"][mode or "?"] += 1
            if date:
                st["dates"].append(date)
            cb = (call, band)
            cbm = (call, band, mode)
            st["cbm"].add(cbm)
            all_cb.add(cb)
            all_cbm.add(cbm)
            cb_to_folders[cb].add(folder)
            if top in LOADED_DIRS or folder in LOADED_DIRS:
                loaded_cb.add(cb)

    # Pro-Ordner-Report
    print(f"{'Ordner':<26}{'Dateien':>8}{'QSOs':>8}{'Calls':>8}  Ziel-Vorschlag   Datum-Spanne   Modi")
    print("-" * 110)
    for folder in sorted(per_folder):
        st = per_folder[folder]
        ziel = PROPOSED.get(folder, PROPOSED.get(folder.split("/")[0], "?"))
        dr = ""
        if st["dates"]:
            ds = sorted(st["dates"])
            dr = f"{ds[0]}–{ds[-1]}"
        modes = " ".join(f"{m}:{n}" for m, n in sorted(st["modes"].items(),
                                                       key=lambda x: -x[1]))
        nf = f"  (⚠{st['nofield']} ohne Call/Band)" if st["nofield"] else ""
        print(f"{folder:<26}{st['files']:>8}{st['qsos']:>8}{len(st['calls']):>8}"
              f"  {ziel:<16} {dr:<14} {modes}{nf}")

    # Bilanz
    print("\n=== BILANZ ===")
    all_calls = {c for c, _ in all_cb}
    loaded_calls = {c for c, _ in loaded_cb}
    print(f"unique Calls gesamt:            {len(all_calls)}")
    print(f"unique Calls aktuell geladen:   {len(loaded_calls)}")
    print(f"unique (Call,Band) gesamt:      {len(all_cb)}")
    print(f"unique (Call,Band,Mode) gesamt: {len(all_cbm)}  ← Index-Größe nach Mode-Erweiterung")

    # Calls die NUR in nicht-geladenen Ordnern leben (Verlust-Gefahr beim Löschen)
    only_unloaded_calls = all_calls - loaded_calls
    print(f"\n=== {len(only_unloaded_calls)} Calls leben NUR in NICHT-geladenen Ordnern "
          f"(gingen beim blinden Löschen verloren) ===")
    # zeige wo sie herkommen
    only_cb = {cb for cb in all_cb if cb[0] in only_unloaded_calls and cb not in loaded_cb}
    src_count = defaultdict(int)
    for cb in only_cb:
        for fol in cb_to_folders[cb]:
            top = fol.split("/")[0]
            if top not in LOADED_DIRS and fol not in LOADED_DIRS:
                src_count[fol] += 1
    for fol, n in sorted(src_count.items(), key=lambda x: -x[1]):
        print(f"   {n:>4} (Call,Band) nur aus: {fol}")
    sample = sorted(only_unloaded_calls)[:30]
    print(f"   Beispiel-Calls: {', '.join(sample)}{' …' if len(only_unloaded_calls) > 30 else ''}")

    # Re-Upload-Abschätzung: was bei Vorschlag in 'neu/' landet → Upload-Kandidaten
    neu_folders = [fol for fol in per_folder
                   if PROPOSED.get(fol, PROPOSED.get(fol.split("/")[0], "")) == "neu"]
    neu_qsos = sum(per_folder[fol]["qsos"] for fol in neu_folders)
    print(f"\n=== Vorschlag → 'neu/' (würden bei nächstem QRZ-Upload gesendet) ===")
    print(f"   Ordner: {neu_folders or '—'}")
    print(f"   QSOs in 'neu/': {neu_qsos}  (Rest → importiert/hochgeladen, KEIN Re-Upload)")

    print("\n(Read-only Trockenlauf — es wurde NICHTS geschrieben/verschoben/gelöscht.)")


if __name__ == "__main__":
    main()
