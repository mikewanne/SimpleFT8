# P2.ADIF-ARCHIVE V2 — Self-Review (Rolle: frische KI prueft V1)

**Auftrag:** V1 kritisch lesen, Luecken/Mehrdeutigkeiten benennen, V3-Plan
schaerfen. **NICHT** das Problem loesen, sondern den Plan verbessern.

---

## Lessons aus V1

### L1 — V1 §3.1 Punkt 6 „Quell-Datei behandeln" zu unverbindlich

V1 nennt 3 Optionen (a/b/c) ohne klare Entscheidung. Hobby-Tool-Praxis:
**Default-Verhalten muss feststehen** sonst wird's unklar.

**Entscheidung V2:** **Option (b) — Verschieben nach
`adif/archiv/_konsolidiert/SimpleFT8_LOG_YYYYMMDD.adi`**.
Begruendung:
- (a) Loeschen ist unwiederbringlich → Risiko bei Idempotenz-Bug
- (c) Behalten → `adif/hochgeladen/` waechst monoton, Mike's Workflow
  bleibt unklar (was ist „neu"?)
- (b) Sicher (Original bleibt physisch da), gleichzeitig wird
  `adif/hochgeladen/` regelmaessig leer → Bulk-Status sauber pruefbar

`--delete-source` Flag bleibt als opt-in fuer fortgeschrittene User.
Default `--archive-source` (Verschieben).

### L2 — V1 ueberlaesst CLI-Format zu vage

V1 §5 Implementations-Skizze hat `parser.add_argument` fuer 4 Flags,
aber nicht klar was bei Aufruf ohne Argumente passiert. Mike-UX-
Praxis: lieber **interaktiv** mit Confirm-Prompt vor irreversibler
Aktion.

**V2-Schaerfung:** Default-Verhalten ohne Argumente:
1. Quelle scannen, Plan-Summary ausgeben
2. Wenn nichts zu tun → exit 0 + Hinweis
3. Wenn was zu tun → `--dry-run` empfehlen ODER `[y/N]`-Prompt

`--yes` Flag fuer Skript-Automation (kein Prompt). Default mit Prompt.

### L3 — V1 fragt §7.2 nach Archiv-Pfad — V2 entscheidet

V1 §7.2 fragt: `adif/archiv/` oder anderswo?

**V2-Entscheidung:** `adif/archiv/YYYY.adi` — bleibt unter `adif/`,
neben `adif/hochgeladen/`. Konsistent mit Verzeichnis-Struktur in
CLAUDE.md (alle ADIF-Dateien unter `adif/`).

### L4 — Match-Key V1 §7.3 — V2 bleibt bei (CALL, QSO_DATE, TIME_ON)

Mike's Hobby-Praxis: gleiches Call gleiche Sekunde anderes Band ist
unrealistisch (FT8-Slot 15s, Mike sendet auf einem Band gleichzeitig).
KISS: 3-Tupel reicht.

V2 stoesst aber auf einen Edge-Case: **doppelte ADIF-Eintraege im
selben Logbuch** (z.B. wenn lokaler Duplikat-Filter P1.7 fehlschlaegt
und 2 Eintraege geschrieben werden). Match-Key wuerde sie als
identisch behandeln und nur den ersten ins Archiv schreiben — beide
sind dann konsolidiert auf einen. **DAS IST OKAY** — Konsolidierung
soll Duplikate eliminieren.

### L5 — V1 §3.1 Punkt 4 „Header bei neuer Jahres-Datei"

V1 sagt: Wenn Jahres-Archiv neu erstellt wird, ADIF-Header schreiben.
Sonst nur Records anhaengen vor `<EOR>`-Endungen.

**V2-Verifikation:** ADIF-Header endet mit `<EOH>`, dann folgen die
Record-Bloecke. „Anhaengen" bedeutet: einfach Records ohne `<EOH>`
hinten dranschreiben. KEIN „vor `<EOR>`-Endungen einfuegen" — das
waere Insertion-Order, fragil.

**V2-Schaerfung:** V1 Implementations-Skizze hat schon das richtige
Pattern (`archive_path.open("a")` Append-Mode), aber Kommentar in
V1 §3.1 Punkt 4 ist missverstaendlich. → V3 klar formulieren:
„An Datei-Ende anhaengen, KEIN Insertion-in-Mitte".

### L6 — V1 §7.7 QRZ-Exports — Filter-Pattern explizit

V1 fragt ob `da1mhh.410638.YYYYMMDDHHMMSS.adi` (QRZ-Originale) auch
konsolidiert werden sollen. NEIN — das sind Mike's eigene QRZ-Backups,
sollen unangetastet bleiben.

**V2-Schaerfung:** Source-Glob-Pattern strikt:
`SimpleFT8_LOG_*.adi` statt `*.adi`. So werden QRZ-Exports automatisch
ignoriert. Dokumentieren in V3 als bewusste Design-Entscheidung.

ABER: Was wenn Mike `--source ein-anderer-pfad/` setzt mit gemischten
Dateien? → Glob-Filter im Script trotzdem anwenden (sicher), oder als
Default-Pattern. **V2-Entscheidung:** `--pattern "SimpleFT8_LOG_*.adi"`
als optional Argument, Default ist genau dieses Pattern.

### L7 — V1 fehlt Atomare-Schreib-Garantie

ADIF-Datei schreiben muss atomar sein (Lesson aus v0.95.18: O(n²)
Bug bei `delete_qso`, plus generelle Datei-Integritaet-Praxis).
V1 §5 nutzt `archive_path.open("a")` direkt — wenn Mike Strg+C
mittendrin drueckt, ist die Archiv-Datei kaputt.

**V2-Schaerfung:** Pro Quell-Datei einen tmpfile-Write + atomic-rename:
1. Existing Archiv lesen → existing_records
2. Mergen mit new_recs
3. Komplett in `<archive>.tmp` schreiben (Header + alle Records)
4. `os.replace(<archive>.tmp, <archive>)` — atomic POSIX-Rename

Das ist O(n) per Lauf statt O(1)-Append, aber bei <100k Records
total irrelevant (< 10MB). Sicherheit > Mikro-Performance.

### L8 — V1 Tests-Soll: 10 reicht NICHT fuer Robustheit

V1 listet 10 Tests. V2 schaetzt mehr Edge-Cases:
- `test_atomic_write_no_partial_file_on_crash` (Strg+C-Simulation)
- `test_archive_record_order_preserved` (Reihenfolge stabil)
- `test_glob_pattern_filters_qrz_exports` (L6)
- `test_archive_source_to_konsolidiert` (L1 Move-Verhalten)
- `test_yes_flag_no_prompt` (L2 CLI-UX)

**V2-Tests-Soll:** **15 Tests** statt 10.

### L9 — V1 fehlt Konkurrenz-Sicherheit

Was wenn 2 Instanzen von `adif_archive.py` gleichzeitig laufen
(Mike startet 2× per Versehen)? Beide lesen existing_keys, beide
schreiben ihren Anteil → Race-Condition, Datenkorruption moeglich.

**V2-Schaerfung:** Lockfile-Mechanismus
(`adif/archiv/.archive.lock` mit fcntl.flock — analog zu
v0.95.5 Single-Instance-Lock). Zweite Instanz fail-fast mit
klarer Fehlermeldung.

ALTERNATIVE (KISS): Akzeptieren dass Mike nicht 2× gleichzeitig
startet (Hobby-Tool, 1-User-Workflow). Tmpfile-Atomic-Write (L7)
verhindert Korruption ohnehin → bei race-Condition gewinnt der
spaetere Lauf, kein Datenverlust.

**V2-Entscheidung:** KISS — Lockfile NICHT noetig. L7 Atomic-Write
reicht. In V3 als bewusste Design-Entscheidung dokumentieren
(„Mike-Praxis: 1-User-Tool, kein Cron-Auto-Run").

### L10 — V1 fehlt CLI-Output-Format

V1 §3.1 Punkt 8 sagt „klar lesbar" ohne Beispiel. Konkret:

```
$ ./venv/bin/python3 tools/adif_archive.py
ADIF-Archive — Konsolidierung
Quelle:  adif/hochgeladen/  (3 Dateien gefunden)
Ziel:    adif/archiv/

Plan:
  SimpleFT8_LOG_20260301.adi → 2026.adi  (47 neue Records)
  SimpleFT8_LOG_20260302.adi → 2026.adi  (52 neue, 1 duplikat)
  SimpleFT8_LOG_20251231.adi → 2025.adi + 2026.adi  (3 + 12 Records)

Quell-Dateien werden nach adif/archiv/_konsolidiert/ verschoben.

Fortfahren? [y/N]: _
```

**V2-Schaerfung:** Format in V3 als Spec festhalten.

### L11 — V1 §6 Tests — Helper-Tests fehlen

V1 listet Test 8 (`test_record_key_uniqueness`) + Test 9
(`test_record_year_extraction`). Aber `_record_to_adif` (Re-Encoder)
ist auch nicht-trivial:
- Was wenn Wert leer? `<CALL:0>` valide?
- Was wenn Underscore-Felder gemischt?

**V2-Test-Ergaenzung:**
- `test_record_to_adif_empty_value`
- `test_record_to_adif_skips_internal_fields`

→ Tests-Soll noch hoeher: **17 Tests**.

### L12 — Datenintegritaets-Check

Bevor Quell-Datei verschoben wird, sollte Verifikation laufen:
**alle Records aus Quelle sind im Archiv enthalten** (vergleich
Match-Keys vor + nach). Sonst: nicht verschieben, error melden.

**V2-Schaerfung:** Verifikations-Schritt VOR Move/Delete:
```
post_keys = read_existing_archive_keys(archive_path)
expected_keys = set(_record_key(r) for r in source_records)
missing = expected_keys - post_keys
if missing:
    # NICHT verschieben, error werfen
```

### L13 — V1 fehlt Append-Idempotenz fuer Existing-Archiv

V1 sagt: bestehendes Archiv lesen → existing_keys → nur neue schreiben.
Aber V1 §5 macht das via `archive_path.open("a")` Append. Das ist OK
fuer __neue Records__, aber wenn die Quelle Records enthaelt die
schon im Archiv sind aus FRUEHEREM Lauf, werden sie korrekt geskippt.

**V2-Verifikation:** Logik in V1 §5 ist korrekt — `existing_keys`
wird VOR `new_recs`-Filterung gelesen. Skip-Order also OK.

ABER: Wenn V2-L7 atomic-write angewendet wird, MUSS man aus dem
Existing-Archiv ALLES in den neuen Tmpfile uebernehmen (nicht nur
Append). Sonst gehen alte Records verloren.

**V2-Schaerfung:** Atomic-Write-Reihenfolge:
1. existing_records = parse_adif_file(archive_path) (alles!)
2. existing_keys = set(_record_key(r) for r in existing_records)
3. new_recs = [r for r in source_records if _record_key(r) not in existing_keys]
4. tmpfile schreiben: HEADER + existing_records + new_recs
5. os.replace(tmpfile, archive_path)

### L14 — V1 hat keine Lessons-Learned-Sektion

Bisherige Workflows haben Lessons-Learned-Vorschlaege fuer Memory
(z.B. P1.BUNDLE2 V3 §7).

**V2-Schaerfung:** V3 muss enthalten:
- Lesson: standalone-Tools brauchen Atomic-Write + Idempotenz from-the-start
- Lesson: KISS schlaegt Lockfile bei 1-User-Hobby-Workflows
- Lesson: ADIF-Konsolidierung Pattern (existing-load + merge + atomic-replace)

### L15 — V1 erwaehnt nicht: tools/ ist nicht im sys.path

V1 §5 hat `sys.path.insert(0, str(Path(__file__).parent.parent))` —
gut. V2 verifiziert: `tools/`-Scripts brauchen das. Andere Tools
(`tools/deepseek_review.py`, `tools/refresh_stats.sh`,
`tools/slot_lueckenliste.py`) als Vorbild — Konvention im Projekt.

→ Bestaetigt, kein Aenderungs-Bedarf.

---

## V2-Antworten auf V1's offene Fragen (§7)

1. **Quell-Datei nach Konsolidierung:** Verschieben nach
   `adif/archiv/_konsolidiert/` (Option b, L1).
2. **Archiv-Verzeichnis:** `adif/archiv/YYYY.adi` (L3).
3. **Match-Key:** `(CALL, QSO_DATE, TIME_ON)` reicht (L4).
4. **Auto-Run vs Manual:** Manual via CLI, kein Cron (L9 KISS).
5. **App-Integration:** Reines CLI, keine Settings-Button (KISS).
6. **`_record_to_adif`-Reihenfolge:** Egal (ADIF-Spec) — V3 dokumentieren.
7. **QRZ-Exports:** NICHT konsolidieren, Glob-Pattern strikt
   `SimpleFT8_LOG_*.adi` (L6).

---

## V2-Schaerfungen fuer V3

| Punkt | V1 | V2 |
|---|---|---|
| Quell-Datei-Verhalten | 3 Optionen offen | Verschieben Default (L1) |
| CLI-UX | nur Flags | Confirm-Prompt + `--yes`-Flag (L2) |
| Atomic-Write | nicht erwaehnt | Tmpfile + os.replace (L7) |
| Glob-Pattern | unbestimmt | `SimpleFT8_LOG_*.adi` strikt (L6) |
| Tests-Zahl | 10 | 17 |
| Verifikations-Schritt | fehlt | Match-Key-Check vor Move (L12) |
| CLI-Output-Format | „klar lesbar" | konkrete Spec (L10) |
| Lockfile | unbestimmt | NICHT noetig, KISS (L9) |

---

## V3-Pflicht-Punkte

V3 muss enthalten:
- Komplettes Script-File (Compact-fest, alle Funktionen)
- 17 Tests konkret
- CLI-Output-Format-Spec
- Atomic-Write-Pattern (existing-load + merge + tmpfile + os.replace)
- Verifikations-Schritt vor Move
- Glob-Pattern strikt
- Lessons-Learned-Vorschlaege fuer Memory

---

**V2-Ende. R1-Plan-Review folgt.**
