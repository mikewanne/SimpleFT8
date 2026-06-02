#!/usr/bin/env python3
"""P169 ADIF-Migration → adif/erfasst/{neu,hochgeladen,importiert}/.

Konsolidiert alle verstreuten .adi-Dateien in EINE rekursiv gelesene Quelle
`adif/erfasst/`. Klassifikation (Mike-Freigabe, Variante A):
  adif/ (lose, frische App-QSOs)            → erfasst/neu/
  adif/hochgeladen/                         → erfasst/hochgeladen/
  adif/{_backup_qrz_export,repaired,archiv,archiv/_konsolidiert,exports,adif/...}
                                            → erfasst/importiert/

SICHERHEIT (copy → HASH-verify → delete) — nach DeepSeek-R1 gehärtet:
  1. Backup-ZIP des Original-adif/ (OHNE erfasst/) nach Appsicherungen/.
  2. SHA256 jeder Quell-.adi.
  3. KOPIEREN, content-addressed: ist der Hash schon in erfasst/ → ÜBERSPRINGEN
     (idempotent + dedupt identische Dateien, Re-Run-sicher). Sonst kopieren,
     Namens-Konflikt → Hash-Präfix.
  4. VERIFIKATION byte-genau: JEDER Quell-Hash MUSS in erfasst/ vorhanden sein
     (parse-unabhängig — fängt auch unterschiedliche QSOs mit gleicher (Call,Band)).
     → Abweichung: ABBRUCH, NICHTS gelöscht.
  5. NUR verifizierte .adi EINZELN löschen (kein rmtree → Nicht-ADIF-Dateien wie
     adif_stdout.log bleiben + werden gemeldet). Danach leere Ordner entfernen.

Modi: --dry-run (default, ändert nichts) | --apply
Aufruf (aus SimpleFT8/): ./venv/bin/python3 tools/migrate_adif_erfasst.py [--apply]
"""
import argparse
import hashlib
import shutil
import sys
import zipfile
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

ADIF = Path("adif")
ERFASST = ADIF / "erfasst"
BACKUP_DIR = Path("Appsicherungen")

CLASSIFY = {
    "<root>": "neu",
    "hochgeladen": "hochgeladen",
    "_backup_qrz_export": "importiert",
    "repaired": "importiert",
    "archiv": "importiert",
    "archiv/_konsolidiert": "importiert",
    "exports": "importiert",
}


def _sha256(f: Path) -> str:
    h = hashlib.sha256()
    with open(f, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _key_for(f: Path) -> str:
    """Klassifikations-Key relativ zu adif/. '<root>' = lose .adi in adif/."""
    rel = f.relative_to(ADIF).parent
    return "<root>" if str(rel) == "." else str(rel)


def _target_for(key: str) -> str:
    # adif/adif/... (doppelt verschachtelt) + alles Unbekannte → importiert (sicher).
    if key == "adif" or key.startswith("adif/"):
        return "importiert"
    return CLASSIFY.get(key, CLASSIFY.get(key.split("/")[0], "importiert"))


def _source_files() -> list[Path]:
    """Alle .adi unter adif/ AUSSER bereits in erfasst/."""
    return [f for f in sorted(ADIF.rglob("*.adi"))
            if "erfasst" not in f.relative_to(ADIF).parts]


def _erfasst_hashes() -> set[str]:
    return {_sha256(f) for f in ERFASST.rglob("*.adi")} if ERFASST.is_dir() else set()


def _non_adi_in_sources(files) -> list[Path]:
    """Nicht-.adi-Dateien in den Quell-Ordnern (würden bei rmtree sterben)."""
    src_dirs = {f.parent for f in files}
    out = []
    for d in src_dirs:
        for x in d.iterdir():
            if x.is_file() and x.suffix.lower() != ".adi":
                out.append(x)
    return sorted(out)


def dry_run():
    if not ADIF.is_dir():
        print(f"FEHLER: {ADIF.resolve()} fehlt (aus SimpleFT8/ starten).")
        return 1
    files = _source_files()
    plan = defaultdict(list)
    for f in files:
        plan[_target_for(_key_for(f))].append(f)
    print(f"=== TROCKENLAUF — {len(files)} Quell-.adi → erfasst/ ===\n")
    for target in ("neu", "hochgeladen", "importiert"):
        fs = plan.get(target, [])
        srcs = sorted({_key_for(f) for f in fs})
        print(f"  erfasst/{target}/  ← {len(fs)} Dateien  (aus: {', '.join(srcs) or '—'})")
    non_adi = _non_adi_in_sources(files)
    if non_adi:
        print(f"\n  ⚠ {len(non_adi)} Nicht-ADIF-Datei(en) bleiben unangetastet:")
        for x in non_adi:
            print(f"       {x}")
    print("\n(Trockenlauf — nichts geändert. Mit --apply ausführen.)")
    return 0


def apply():
    if not ADIF.is_dir():
        print(f"FEHLER: {ADIF.resolve()} fehlt (aus SimpleFT8/ starten).")
        return 1

    files = _source_files()
    src_hash = {f: _sha256(f) for f in files}
    print(f"[1/5] Quelle: {len(files)} .adi, {len(set(src_hash.values()))} eindeutige Inhalte.")

    # 1. Backup-ZIP des Original-adif/ OHNE erfasst/
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    backup = BACKUP_DIR / f"adif_backup_pre_p169_{ts}.zip"
    n_backed = 0
    with zipfile.ZipFile(backup, "w", zipfile.ZIP_DEFLATED) as z:
        for f in ADIF.rglob("*"):
            if f.is_file() and "erfasst" not in f.relative_to(ADIF).parts:
                z.write(f, f.relative_to(ADIF.parent))
                n_backed += 1
    print(f"[2/5] Backup (ohne erfasst/): {backup} — {n_backed} Dateien, "
          f"{backup.stat().st_size} Bytes")
    # Sicherheit: das Backup MUSS mindestens alle Quell-.adi enthalten
    # (datei-basiert statt Byte-Größe — kleine echte Datasets sind legitim).
    if n_backed < len(files):
        print(f"❌ ABBRUCH: Backup unvollständig ({n_backed} < {len(files)} .adi). "
              "Nichts geändert.")
        return 1

    # 2. Kopieren content-addressed (idempotent + dedup)
    for sub in ("neu", "hochgeladen", "importiert"):
        (ERFASST / sub).mkdir(parents=True, exist_ok=True)
    have = _erfasst_hashes()
    copied = defaultdict(int)
    skipped = 0
    for f in files:
        h = src_hash[f]
        if h in have:
            skipped += 1
            continue
        target = _target_for(_key_for(f))
        dest = ERFASST / target / f.name
        n = 0
        while dest.exists():
            n += 1
            dest = ERFASST / target / f"{h[:12]}_{n}_{f.name}"
        shutil.copy2(f, dest)
        have.add(h)
        copied[target] += 1
    print(f"[3/5] Kopiert: {dict(copied)}  (übersprungen, schon vorhanden: {skipped})")

    # 3. VERIFIKATION byte-genau: jeder Quell-Hash muss in erfasst/ sein
    erfasst_hashes = _erfasst_hashes()
    missing = [f for f in files if src_hash[f] not in erfasst_hashes]
    if missing:
        print(f"❌ [4/5] ABBRUCH: {len(missing)} Quelldatei(en) NICHT in erfasst/! "
              f"NICHTS gelöscht.")
        for f in missing[:10]:
            print(f"       fehlt: {f}")
        print(f"   erfasst/ kann gelöscht + neu versucht werden. Backup: {backup}")
        return 1
    print(f"✓ [4/5] Verifikation OK: alle {len(files)} Quelldateien byte-genau in erfasst/.")

    # 4. NUR verifizierte .adi einzeln löschen (kein rmtree)
    deleted, errors = 0, []
    for f in files:
        try:
            f.unlink()
            deleted += 1
        except Exception as e:
            errors.append((f, str(e)))
    # leere Ordner bottom-up entfernen — NUR Ordner STRIKT unter adif/ (nie adif/
    # selbst, nie adif/.. = cwd, nie erfasst/). Nicht-ADIF + nicht-leere bleiben.
    candidate_dirs = set()
    for f in files:
        p = f.parent
        while p != ADIF and p != ADIF.parent:
            if "erfasst" not in p.relative_to(ADIF).parts:
                candidate_dirs.add(p)
            p = p.parent
    for d in sorted(candidate_dirs, key=lambda p: -len(p.parts)):
        try:
            if d.is_dir() and not any(d.iterdir()):
                d.rmdir()
        except Exception:
            pass
    leftover = []
    for d in {f.parent for f in files}:
        if d.is_dir():
            leftover += [x for x in d.iterdir() if x.is_file()]
    print(f"✓ [5/5] {deleted} .adi gelöscht. Quelle jetzt: {ERFASST}/ (rekursiv).")
    if errors:
        print(f"   ⚠ {len(errors)} Löschfehler: {errors[:5]}")
    if leftover:
        print(f"   ⚠ Belassen (kein ADIF / nicht leer): {sorted(set(str(x) for x in leftover))}")
    return 0


def main():
    ap = argparse.ArgumentParser(description="P169 ADIF → erfasst/ Migration")
    ap.add_argument("--apply", action="store_true", help="ausführen (sonst Trockenlauf)")
    args = ap.parse_args()
    sys.exit(apply() if args.apply else dry_run())


if __name__ == "__main__":
    main()
