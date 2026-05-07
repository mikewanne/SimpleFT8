# P1.LOCATOR-SLASH V1 — Slash-Call Lookup-Bugs in km/Country/Distance

**Stand:** 2026-05-07.
**Workflow:** **V1 (diese Datei)** → V2 (Self-Review) → R1 (DeepSeek) → V3 → Compact → Code.
**Auslöser:** DeepSeek-R1-Code-Review der km-Anzeige im RX-Panel (Mike-Pflicht-
Verifikation 07.05.) — 3 echte Bugs gefunden:
1. Falsche `lookup_call`-Extraktion bei Präfix-Slash (z.B. `EA8/DA1MHH`)
2. Mobile-Suffix-Inkonsistenz zwischen DB-set und DB-get
3. Gleicher Slash-Bug in `core/geo.py` `callsign_to_country` + `callsign_to_distance`

Mike-Entscheidung 07.05.: **Datenbank behalten** (Daten sind korrekt
gespeichert, nur Lookup-Pfad ist kaputt), nur Code fixen.

---

## 1. Symptome (Mike-Beobachtung post-DeepSeek-Review)

Bisher wurde im RX-Panel km-Spalte gezeigt:
- ✅ Bei CQ mit Grid: exakte km via `grid_distance`
- ⚠️ Bei Slash-Call **ohne** Mobile-Suffix (`EA8/DA1MHH`, `DL/EA1ABC`, etc.):
  → `lookup_call = max(parts, key=len)` → längster Teil → meist Basis-
  rufzeichen (z.B. `DA1MHH` statt `EA8/DA1MHH`)
  → DB-Lookup mit falschem Key → Treffer aus „Heim-DB-Eintrag" ODER
  Miss → Fallback auf Prefix-Schätzung mit falschem Country-Prefix
  (Heim statt DXCC-Aktivität)
- ⚠️ Bei Mobile-Suffix (`DA1MHH/P`):
  → rx_panel macht `lookup_call = parts[0]` = `DA1MHH`
  → DB hat aber `DA1MHH/P` (so wie Decoder/`_feed_locator_db` es
  gespeichert hat)
  → Lookup verpasst Eintrag → Fallback Prefix-Schätzung
  → Mike's Heim-DA1MHH wäre der „richtige" Treffer (selbe Person!) — nur
  kommt der gar nicht erst zum Lookup weil die DB-Keys unterschiedlich sind

---

## 2. Bug-Detail mit Datei:Zeile

### 🔴 Bug 1 — `ui/rx_panel.py:327-335` Slash-Call-Logik

```python
lookup_call = caller
if caller and "/" in caller:
    parts = caller.split("/")
    MOBILE_SUFFIXES = {"P", "M", "MM", "AM", "QRP", "PORTABLE", "MOBILE"}
    if parts[-1].upper() in MOBILE_SUFFIXES:
        lookup_call = parts[0]  # OK fuer DA1MHH/P → DA1MHH
    else:
        lookup_call = max(parts, key=len)  # ← BUG
```

**Falsch:** `EA8/DA1MHH` → `lookup_call = "DA1MHH"` (6 > 3 Zeichen).
**Konsequenzen:**
- DB-Lookup mit falschem Key
- Country-Fallback `callsign_to_country("DA1MHH")` → Deutschland statt EA8
- Prefix-Distanz-Fallback `callsign_to_distance("DA1MHH", ...)` → ~0 km
  statt ~3000 km

### 🔴 Bug 2 — DB-Set/Get Mobile-Suffix-Inkonsistenz

`core/locator_db.py:152-164` `set(call, locator, source)`:
- Speichert `call.upper()` ohne Normalisierung
- Wenn Decoder `DA1MHH/P` mit Locator-CQ-Decode liefert → DB-Eintrag
  unter Key `DA1MHH/P`

`core/locator_db.py:127-138` `get(call)`:
- Liest `call.upper()` ohne Normalisierung
- rx_panel.py macht `lookup_call = parts[0]` für Mobile → sucht nach
  `DA1MHH` (ohne `/P`)
- → DB-Eintrag wird verpasst

**Trade-off:** Strikte Trennung von `DA1MHH/P` und `DA1MHH` ist eigentlich
korrekt (Mobile-Operator kann an anderer Position sein als Heim).
**Aber:** rx_panel macht das Stripping einseitig → muss konsistent sein.

### 🔴 Bug 3 — `core/geo.py:557+` `callsign_to_distance` + `callsign_to_country`

Selber Bug wie Bug 1: bei nicht-mobile-Slash → `max(parts, key=len)` →
falsches Land + falsche Prefix-Distanz für `EA8/DA1MHH`-artige Calls.

---

## 3. Loesungs-Optionen (zu entscheiden in V2/R1)

### Option A — Strikte Trennung, KEIN Stripping in rx_panel.py

- `rx_panel.py`: bei Slash-Call ohne Mobile-Suffix → `lookup_call = caller`
  (kompletter String). Mobile-Suffix ebenfalls NICHT entfernen.
- `core/locator_db.py`: keine Aenderung
- `core/geo.py`: nur das `max(parts, key=len)` durch `caller`-as-is ersetzen
- **Vorteil:** Mobile-Position separat von Heim-Position. Funktechnisch
  korrekt (DA1MHH/P ist im Wald, DA1MHH zu Hause).
- **Nachteil:** wenn Mobile-Op-Position nie in DB war, kein Fallback auf
  Heim-Position → grobe Prefix-Schätzung trotz vorhandener Daten.

### Option B — Suffix-Stripping in DB-Layer

- `core/locator_db.py`: zentrale `_normalize_call()` in `set/get/get_position`
  — Mobile-Suffix entfernt, Slash-Praefixe behalten.
- `rx_panel.py`: bei Slash-Call ohne Mobile-Suffix → `lookup_call = caller`
  (komplett). Mobile-Suffix wird sowohl in rx_panel als auch DB entfernt
  → konsistent.
- `core/geo.py`: gleicher Fix wie Bug 1.
- **Vorteil:** Mobile-Calls finden Heim-Position als Fallback (DA1MHH/P-
  Decode → DB hat DA1MHH-Heim → Lookup findet das).
- **Nachteil:** Mobile-Position-Daten werden unter Heim-Key überschrieben
  oder umgekehrt (je nach Source-Priority).

### Option C — Hybrid (Stripping NUR im Lookup-Fallback)

- DB speichert `DA1MHH/P` strikt unter eigenem Key (Variante A für Set).
- `rx_panel.py` versucht ZUERST Lookup mit komplettem Key (`DA1MHH/P`),
  fallback auf gestrippten Key (`DA1MHH`) wenn miss.
- `geo.py` Fix wie Bug 1.
- **Vorteil:** Beide Welten — Mobile-Position bevorzugt, Heim als Fallback.
- **Nachteil:** Doppel-Lookup pro Slash-Call (kleiner Performance-Hit, in
  RX-Panel egal — pro Slot ~10-30 Decodes).

→ **V1-Vorschlag: Option C.** Funker-Realismus + Pragmatismus.
   V2/R1 sollen das schärfen.

---

## 4. Akzeptanzkriterien

1. **AC-1 Praefix-Slash** `EA8/DA1MHH` zeigt:
   - Country: EA8 (Kanaren) — nicht Deutschland
   - km: ~3000 km — nicht ~0 km
   - DB-Lookup findet Eintrag falls vorhanden, Fallback Prefix
2. **AC-2 Mobile-Suffix** `DA1MHH/P` zeigt:
   - Country: Deutschland (Basis-Call)
   - km: aus DB falls Mobile-Position bekannt, sonst Heim-Position als
     Fallback (Option C), sonst Prefix
3. **AC-3 Region-Suffix** `K1ABC/W2` zeigt:
   - Country: USA (Basis)
   - km: aus DB falls vorhanden (vermutlich `K1ABC` Heim), sonst Prefix
4. **AC-4 DB-Konsistenz:** `_feed_locator_db` speichert `m.caller`
   ohne Modifikation (so bleibt Source-Truth erhalten). `get_position`
   muss konsistent das finden was `_feed_locator_db` gespeichert hat.
5. **AC-5 Country-Funktion:** `callsign_to_country("EA8/DA1MHH")` →
   Kanaren. `callsign_to_country("DA1MHH/P")` → Deutschland.
   `callsign_to_country("K1ABC/W2")` → USA.
6. **AC-6 Distance-Funktion:** `callsign_to_distance("EA8/DA1MHH", "JO31")`
   → ~3000 km. `callsign_to_distance("DA1MHH/P", "JO31")` → ~0 km.
7. **AC-7 Tests gruen:** alle bestehenden Tests + neue fuer Slash-Calls.
   Erwartung: 888 → ~898 gruen (+10 neu).
8. **AC-8 DB-Audit (optional):** `tools/locator_db_audit.py` listet
   Slash-Calls in DB + Doppel-Eintraege. Mike kann nach Field-Test
   manuell entscheiden ob Bereinigung noetig.
9. **AC-9 Field-Test:** Mike beobachtet bei naechster App-Session ob
   bekannte Slash-Calls (EA8-Aktivitäten, Mobile-Operator) jetzt korrekte
   km-Werte zeigen.
10. **AC-10 Karten-Code unbeeinflusst:** `direction_map_widget.py:1694`
    `_locator_db.set(rx_call, rx_loc, "psk")` darf NICHT beschaedigt
    werden. Karten-Layer muss weiter alle Stationen anzeigen.

---

## 5. Betroffene Module/Dateien

### 5.1 `ui/rx_panel.py` — `_populate_row` Slash-Logik

Zeilen 327-335. Vereinfachen + Doppel-Lookup-Strategie (Option C).

### 5.2 `core/locator_db.py` — KEINE Aenderung (V1-Vorschlag)

Falls Option C: Set bleibt strikt, Lookup-Pfad in rx_panel macht
Fallback. Falls Option B: zentrale Normalisierung.

### 5.3 `core/geo.py` — `callsign_to_country` + `callsign_to_distance`

Beide Funktionen `max(parts, key=len)` ersetzen. Bei Slash-Call:
- Mobile-Suffix → Basis-Call nehmen
- Sonst → Praefix-Teil nehmen wenn 2-3 Zeichen (Region-Praefix wie EA8,
  KH6, V31) — sonst kompletten Call

V2: konkrete Heuristik festlegen.

### 5.4 `tools/locator_db_audit.py` (NEU, optional)

Standalone-Script:
- Liest `~/.simpleft8/locator_cache.json`
- Listet alle Slash-Call-Eintraege gruppiert nach Basis-Call
- Findet Doppel-Eintraege (z.B. `DA1MHH` UND `DA1MHH/P` mit verschiedenen
  Locatoren)
- Output: Markdown-Tabelle fuer Mike-Review

### 5.5 `tests/test_p1_locator_slash.py` (NEU)

- `test_rx_panel_prefix_slash_lookup` — `EA8/DA1MHH` findet DB-Eintrag
- `test_rx_panel_mobile_suffix_lookup_fallback` — `DA1MHH/P` findet
  Mobile-Position falls da, sonst Heim-Fallback (Option C)
- `test_rx_panel_region_suffix_lookup` — `K1ABC/W2`
- `test_geo_callsign_to_country_slash_prefix` — `EA8/DA1MHH` → Kanaren
- `test_geo_callsign_to_distance_slash_prefix` — `EA8/DA1MHH` ~3000 km
- `test_geo_callsign_to_country_mobile` — `DA1MHH/P` → Deutschland
- `test_locator_db_unchanged_set_get` — Konsistenz-Test (was reingeht
  kommt raus)
- `test_locator_db_audit_finds_double_entries` (falls Audit-Script kommt)

→ **8-10 neue Tests.**

---

## 6. Randbedingungen / Kritische Punkte

- **Karten-Code (direction_map_widget.py)** nutzt `_locator_db.get_position`
  ebenfalls — muss nach Fix weiter funktionieren. Karten-Render-Pfad ist
  aus Decoder-Thread + GUI-Thread, RLock geschuetzt.
- **`_feed_locator_db`** in `mw_cycle.py:284` speichert `m.caller` direkt.
  Wenn Decoder den Slash-Call wie er gesendet wurde liefert, bleibt
  Source-of-Truth. Set-Pfad NICHT verändern (Mike-Entscheidung Option A
  fuer Set).
- **Source-Priority** `cq_6 > psk_6 > qso_log_6` darf nicht kippen.
- **Mobile-Operator-Praxis:** /P /M /MM /AM /QRP haben ECHTE eigene
  Position. Eintrag UNTER `/P`-Key behalten, NICHT mit Heim mergen.
- **Region-Suffix-Praxis:** /W2 /KH6 /VE3 ist Aufenthalts-Indikator,
  nicht Mobile. Behandlung in V2 schaerfen.
- **Backwards-Compat:** Bestehende DB-Eintraege (auch Slash-Calls die
  durch den Bug nie gefunden wurden) bleiben in der DB unveraendert. Nur
  der Lookup-Pfad findet sie jetzt korrekt.
- **Karten-Markierungs-Bug-Risiko:** wenn `EA8/DA1MHH` jetzt korrekt mit
  Kanaren-Position gefunden wird, könnte Karte das Pin verschoben anzeigen
  — gewollt!

---

## 7. Nicht im Scope (P2 oder spaeter)

- **DB-Bereinigung mit Loeschung** — Mike-Entscheidung 07.05.: nicht
  noetig, DB ist korrekt befuellt.
- **Karten-Refactor** — nur passive Verifikation in Field-Test.
- **Migration `_psk_worker` → `core/psk_reporter`** (offene TODO) — nicht
  in diesem Workflow.
- **Source-Priority-Erweiterung** (z.B. Mobile-Praefix in Priority) —
  Bedarf erst nach Field-Test.

---

## 8. Offene Fragen fuer V2/R1

1. **Option A/B/C:** welche Lookup-Strategie ist die richtige? V1
   empfiehlt C (Doppel-Lookup), aber das hat einen Performance-Kosten
   pro Slot. Lohnt sich das oder reicht A?
2. **`callsign_to_country` Slash-Fix:** wie genau heuristisch? Praefix
   2-3 Zeichen ist DXCC-Praefix? Was mit `KH6/W7XYZ` (KH6 ist DXCC,
   W7XYZ ist Heim-Call)?
3. **`callsign_to_distance` Slash-Fix:** dasselbe — Distanz nach EA8 oder
   nach Heim-Land?
4. **DB-Audit-Script:** brauchen wir das wirklich? Oder Field-Test reicht?
5. **Test-Datenbasis:** wie testen wir mit echter DB? Mock vs. tmp_path
   mit minimalem JSON-Cache?
6. **Performance:** Doppel-Lookup pro Slot (Option C) → bei 30 Decodes
   pro Slot 60 DB-Hits statt 30. Egal oder messen?
7. **Backwards-Compat-Risiko:** koennte ein anderer Code-Pfad (Karten,
   Statistik) den Bug aktuell „ausnutzen"? V2 grep.
8. **Mobile-Operator-Edge-Case:** wenn Heim und Mobile beide live → DB
   hat 2 Eintraege. rx_panel zeigt Mobile (Option C primary). Soll Mike
   die Wahl haben? V1 sagt nein (Decoder-Output ist Anzeige-Quelle).

---

## 9. Compact-Strategie

V1 ist Diagnose. V2 wird Self-Review mit konkreten Lessons. R1 reviewt
V2+V1 mit Code-Files dabei. V3 ist Compact-fest mit allen Diffs:
- `ui/rx_panel.py` Diff (Slash-Logik vereinfacht, Doppel-Lookup falls C)
- `core/geo.py` Diff (`callsign_to_country` + `callsign_to_distance`)
- `core/locator_db.py` Diff (nur falls Option B)
- `tests/test_p1_locator_slash.py` (NEU mit ~10 Tests)
- Optional `tools/locator_db_audit.py` (NEU)

Erwartete Test-Erweiterung: 888 → ~898 gruen.
APP_VERSION 0.95.15 → 0.95.16 (Bugfix-only, also Patch-Version).

Wenn Mike Option B will (DB-Layer-Fix), ist V3 etwas größer (4. File).

---

**Workflow-Status:** V1 fertig. Weiter mit V2 (Self-Review).
