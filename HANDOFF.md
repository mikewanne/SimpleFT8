# HANDOFF — SimpleFT8 — 2026-04-27 (v0.67)

## Heute erledigt — Locator-DB Feature + GitHub-Push (v0.66 + v0.67)

**v0.67 — Persistenter Locator-Cache (LocatorDB)** — 6 atomare Commits, alle gruen.

KISS-Prinzip nach DeepSeek-Plan-V3 (V2 hatte 26-Buchstaben-Splitting, LRU,
Write-Ahead-Log — alles raus). Eine JSON-Datei `~/.simpleft8/locator_cache.json`,
in-memory waehrend Laufzeit, save() bei App-Close.

1. `4b9ba64` — `core/locator_db.py` neues Modul + 26 Tests (DeepSeek-codereviewed,
   `encoding="utf-8"` Fix uebernommen)
2. `6dcb275` — Hooks in `mw_cycle._handle_normal_mode` + `_handle_diversity_operate`
   und `direction_map_widget._on_psk_spots_received`
3. `38a1990` — ADIF-Bulk-Import beim App-Start aus `<cwd>/adif/` + adif_import_path
4. `265a918` — `direction_map_widget`: Karte nutzt LocatorDB + prec_km-Feld an
   StationPoint, Country-Fallback dimmt auf 50% Alpha, Disclaimer reduziert auf
   "Ø Genauigkeit: X km"
5. `57beb00` — `rx_panel`: km-Spalte zieht aus DB vor Country-Fallback (kein
   `~`-Praefix wenn Locator irgendwann mal in CQ/PSK gesehen wurde)
6. `f397ec9` — Doku: APP_VERSION 0.66 → 0.67, HISTORY.md, CLAUDE.md

**Bilanz:**
- **361 → 407 Tests** (+46), alle gruen
- **DeepSeek-Codereview** vor Modul-Commit (encoding="utf-8" einziger konkreter Fix)
- **5 Hooks** verbinden Decoder + PSK + ADIF + Karte + rx_panel mit der DB

## Push + GitHub-Updates (Mike-Freigabe)

Mike hat freigegeben: **38 Commits** lokal seit letztem Push → `git push origin main`.

Zusaetzliche README-/Doku-Arbeit auf Mike-Anfrage (kein Version-Bump):
- Statistik-PDFs frisch generiert (DE+EN)
- **Antennen-Bezeichnung korrigiert:** Kelemen DP-201510 ist Trap-Dipol
  (Sperrkreisdipol), KEIN Faecher-Dipol. Recherche bestaetigt — Quellen:
  WiMo (Hersteller), Funktechnik Dathe, Funkshop, DX Engineering.
  Korrektur in `scripts/generate_plots.py`, `README.md` (DE+EN),
  PDF-Berichte regeneriert.
- **WSJT-X-Vergleichstabellen entfernt** — Hobby-Funker-Philosophie:
  - DE+EN Tabellen weg, ersetzt durch lockeren Hobby-Funker-Text
    ("Feierabend-Funk" / "after-work operator")
  - DeepSeek-Umformulierung, Mike-validiert
  - WSJT-X bleibt nur als Acknowledgment (Hommage)
- **Test-Counts + Versionsnummern:** 159/162 → 407, v0.26 → v0.67
- Karte (v0.66) + Locator-DB (v0.67) als neue Features in der Tested-Liste

**Push insgesamt:** v0.66 (Karte) + v0.67 (LocatorDB) + Stats + README → online.
GitHub: https://github.com/mikewanne/SimpleFT8

## Architektur-Ueberblick (LocatorDB)

```
Decoder-Thread                        GUI-Thread / App-Lifecycle
─────────────                         ─────────────────────────
mw_cycle._handle_*                    main_window.__init__
  ├── accumulate_stations               └── locator_db.load()
  └── _feed_locator_db ──────┐
                             │        main_window.closeEvent
PSK-Worker (daemon)          │          └── locator_db.save() (atomar)
  └── _on_psk_spots_received │
        └── db.set("psk")    │        rx_panel._on_message
                             ▼          └── db.get_position(call) → exakte km
                       LocatorDB
                       (RLock)         direction_map_widget.snapshot_to_*
                             ▲          └── db.get_position(call) → Karte
qso_log_init                 │
  └── bulk_import_adif ──────┘
```

## Offen / Naechste Schritte (priorisiert)

1. **Karten-Live-Test im Feld** (durch Mike) — wie viele Stationen sind nach
   einer Stunde Funken praezise lokalisiert (prec_km <= 5)? Wieviele bleiben
   Country-Fallback (transparente Punkte)? Disclaimer "Ø Genauigkeit: X km"
   plausibel?

2. **rx_panel km-Spalte beobachten** — exakte km ohne `~`-Praefix bei DB-
   Treffern, mit `~` bei Country-Fallback. Wenn DA1MHH oft mit JO31 gesehen
   wird, sollte das nach App-Restart sofort exakt sein (qso_log_4 → 110 km
   default, aber durch CQ-Decode wahrscheinlich schnell auf cq_4/cq_6).

3. **Naechste Features (TODO.md):**
   - **B) Band-Indikatoren live mit PSK-Reporter** — 1-2 Tage. Foundation
     `core/psk_reporter.py` steht. Brauchen `fetch_global_activity()` und
     pulsierende Balken bei steigendem Trend.
   - **C) Richtungs-Keulen TX-Pattern-Karte** — 2-3 Tage, USP-Killer.
   - **D) ANT2 RX-Rescue-Keulen** — 1-2 Tage zusaetzlich auf C aufsetzbar.

4. **Migration `main_window._psk_worker` → `core/psk_reporter`** —
   Konsolidierung des bestehenden PSK-Workers. Separater Refactor-Commit.

5. **Bug beobachten:** TX-Frequenz Normal-Modus manchmal ohne Histogramm-
   Marker — noch nicht reproduzierbar.

6. **Cleanup-Idee:** `LocatorCache` (in `direction_map_widget.py:96–131`)
   bleibt vorerst als Fallback. Wenn alle Codepfade migriert sind, kann
   die Klasse + Loader-Funktion komplett raus (~30 Zeilen Reduktion).

## Warnungen & Fallen

- **Locator-DB bei App-Crash:** Save passiert nur bei `closeEvent`. Wenn die
  App crasht, gehen Decodes der Session verloren. Akzeptiert — neue Session
  laedt sie wieder rein. KEIN periodisches Auto-Save eingebaut (Hobby-Funker-
  Konsens).

- **6-stellig wird nie durch 4-stellig ueberschrieben** (Source-Priority).
  Wenn ein Call einmal mit cq_6 in der DB ist, kann ihn auch ein psk_4 nicht
  verdraengen — nur ein psk_6 oder cq_6 mit anderem Locator.

- **`LocatorDB.get()` returnt eine Kopie** — Caller-Mutation aendert die DB
  nicht. Wer Original-Referenz haben will: `_calls` direkt (nicht empfohlen).

- **`_locator_db.set()` kann False zurueckgeben** — bei (a) ungueltigem
  Locator (nicht durch `safe_locator_to_latlon` validierbar), (b) niedrigerer
  Priority als bestehender Eintrag, (c) leerem Call.

- **`bulk_import_directory()` laeuft synchron im Init-Thread** — bei 1000
  ADIF-Records ~300 ms, kein UI-Freeze. Bei groesseren Logs (10k+) ggf.
  Loading-Splash anzeigen.

## Test-Suite Status

```
./venv/bin/python3 -m pytest tests/ -q
407 passed in ~7s
```

Neu seit v0.66:
- `tests/test_locator_db.py` (28 Tests: CRUD, Source-Priority, Persist,
  Threading-Stress, Slash-Calls, ADIF-Bulk-Import)

## Letzter bekannter guter Zustand

- **Branch:** main, gepusht
- **HEAD:** `0a5061a` docs: README v0.67 — Hobby-Funker-Umformulierung
- **Tag:** kein neuer Tag heute (Mike entscheidet wann)
- **Tests:** 407/407 gruen
- **App-Start:** OK (`./venv/bin/python3 main.py`)
- **JSON-Cache:** wird beim ersten Close angelegt
  (`~/.simpleft8/locator_cache.json`)

---

Morgen: `cd SimpleFT8` → `claude1` → laedt automatisch alle Memories + CLAUDE.md.
