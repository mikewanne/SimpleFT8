# Bandpilot Stunden-Logik — V3 (final fuer Mike-Freigabe, Stand 2026-05-04)

## Zweck

V3 konsolidiert V1 (Mike-Konsens) + V2 (Self-Review) + R1-Review-Findings.
V3 ist die finale Spec fuer Plan-Mode + 13 atomare Commits. Mike-Freigabe
durch Triggern der naechsten Phase ("ja, leg los" oder Aequivalent).

## Workflow-Status

| Schritt | Status |
|---|---|
| Code-Verifikation (mode_recommender.py, mw_radio.py, settings_dialog.py, settings.py, tests) | ✅ |
| V1 (Konzept-Final 2026-05-04) | ✅ |
| V2 (Self-Review 25 neue AKs) | ✅ |
| R1-Review (DeepSeek-R1, 5 KRITISCH + 3 OPTIONAL) | ✅ |
| Schritt 2.5: R1-Findings gegen Code verifizieren | ✅ (alle 5 kritischen valid) |
| V3 (dieses Dokument) | ✅ |
| Mike-Freigabe | ⏳ |
| Plan-Mode + 13 Commits | ⏳ |

---

## V1+V2 Zusammenfassung (kompakt)

V1 fixiert das Konzept: drei direkte Stunden-Werte (N/Std/DX) ohne
Aggregation, Settings `bandpilot_mode` ∈ `{off, auto, manual}`,
Auto = max-Pick mit Toleranz, Manuell = Dialog nur wenn Top-1 != aktuell,
Stille bei zu wenig Daten via Statusbar, TX-Schutz, MD-Datei pro Band.

V2 praezisiert Toleranz-Regel (gegen aktuellen Mean, nicht Top-2),
recommend_for_hour-Signatur, Hourly-Cache, MD-Format,
Settings-Migration, Edge-Cases (dx_tuning, Multi-Monitor, schnelle
Bandwechsel), Encoding-Konvention, Modul-Ort `core/bandpilot_md.py`,
9 Kandidat-A-Tests loeschen + 11 neue, Phase-Reihenfolge.

R1 hat V1+V2 reviewt und 5 kritische Luecken gefunden (siehe
"R1-Findings" unten).

---

## R1-Findings — alle aufgenommen in V3

### 🔴 KRITISCH (5 Findings, alle gegen Code verifiziert)

#### R1-1: `Settings.save()` nicht atomar (Race-Condition-Risiko)

**Verifiziert:** `config/settings.py:90-93`:
```python
def save(self):
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, "w") as f:
        json.dump(self._data, f, indent=2)
```

Direkter Overwrite. Bei parallelem Schreiben (Settings-Dialog Save +
Migration in load()) Race moeglich.

**V3-AK 29:** `Settings.save()` muss atomar werden — analog zu
`BandpilotSummaryCache._save()`:
```python
def save(self):
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    tmp = CONFIG_FILE.with_suffix(".tmp")
    with open(tmp, "w") as f:
        json.dump(self._data, f, indent=2)
    os.replace(tmp, CONFIG_FILE)
```

**Phase:** 3 (Settings-Migration), als Vorab-Refactor.

#### R1-2: Alte `bandpilot_diversity_pref`-Referenz in `mw_radio.py`

**Verifiziert:** `ui/mw_radio.py:640-641`:
```python
self._bandpilot.diversity_pref = self.settings.get(
    "bandpilot_diversity_pref", "auto"
)
```

Nach v0.88-Migration ist `bandpilot_diversity_pref` weg. Default `"auto"`
greift, aber semantisch tot — Code-Pfad muss komplett neu (alte
`Bandpilot`-Klasse mit `diversity_pref`-Attribut wird durch neuen
`HourlyBandpilot` ersetzt).

**V3-AK 30:** Im Phase-5-Refactor wird die komplette
`_maybe_apply_bandpilot`-Methode neu gebaut. Die `Bandpilot`-Klasse
in `core/mode_recommender.py` wird **geloescht** oder durch neue
Klasse `HourlyBandpilot` ersetzt. `diversity_pref`-Attribut faellt weg.

**Phase:** 5 (mw_radio-Refactor) und 1 (mode_recommender-Refactor).

#### R1-3: `recommend_for_hour` — `current_mode` nicht in Summary

**V2-AK 13** definiert nur den Fall "current_mode is None" (dx_tuning).
R1 weist auf den Fall hin: `current_mode` ist gueltig, aber fuer die
Stunde gibt es in dem Modus keine Daten (z.B. user funkt heute zum
ersten Mal um 03 UTC und der aktuelle Modus war Diversity DX → keine
Diversity_Dx-Daten in 03-UTC-Bucket).

`current_mean` waere `None` → Toleranz-Vergleich `current_mean >= ...`
crasht.

**V3-AK 31:** `recommend_for_hour` prueft am Anfang:
```python
modes_in_hour = summary.get(hour, {})
if not modes_in_hour:
    return None  # keine Daten in dieser Stunde
for mode in ("normal", "diversity_normal", "diversity_dx"):
    entry = modes_in_hour.get(mode, {})
    if (entry.get("days", 0) < MIN_DAYS_HOUR or
        entry.get("cycles", 0) < MIN_CYCLES_HOUR or
        entry.get("mean") is None):
        return None
# Hier garantiert: alle 3 Modi haben gueltige Means
```

Damit ist auch `current_mean` immer gueltig wenn die Funktion ueberhaupt
ein dict returnt. Stille bei zu wenig Daten = klar.

**Phase:** 1 (mode_recommender-Refactor).

#### R1-4: Tests fehlen ueber V2-Liste hinaus

**V2-AK 24** listet 11 neue Tests. R1 ergaenzt:
- E2E mit mock'd `_set_rx_mode_direct` (prueft Aufruf bei Auto)
- Toast-Test (QDialog wird erstellt? Schliesst nach 3s?)
- Manuell-Dialog-Test (nur bei Top-1 != current)
- Stille-Test (zu wenig Daten → kein Dialog/Toast)
- Pingpong-Schutz-Test (5%-Regel greift)
- TX-Schutz-Test (wartet auf `tx_finished`)
- Hourly-Schwellen-Test (`MIN_DAYS_HOUR=3`, `MIN_CYCLES_HOUR=20`)

**V3-AK 32:** Test-Liste auf insgesamt **18 neue Tests** erweitert
(11 V2 + 7 R1):

| # | Datei | Test |
|---|---|---|
| 1 | test_mode_recommender.py | test_aggregate_stats_by_hour_three_days_three_modes |
| 2 | test_mode_recommender.py | test_recommend_for_hour_normal_top1_no_change |
| 3 | test_mode_recommender.py | test_recommend_for_hour_diversity_dx_top1_switch |
| 4 | test_mode_recommender.py | test_recommend_for_hour_tolerance_5pct_keeps_current |
| 5 | test_mode_recommender.py | test_recommend_for_hour_tolerance_1station_keeps_current |
| 6 | test_mode_recommender.py | test_recommend_for_hour_insufficient_one_mode_returns_none |
| 7 | test_mode_recommender.py | test_recommend_for_hour_current_mode_no_data_returns_none |
| 8 | test_mode_recommender.py | test_recommend_for_hour_hourly_thresholds (MIN_DAYS_HOUR + MIN_CYCLES_HOUR) |
| 9 | test_settings_migration.py (neu) | test_settings_migration_enabled_true_to_auto |
| 10 | test_settings_migration.py | test_settings_migration_enabled_false_to_off |
| 11 | test_settings_migration.py | test_settings_migration_idempotent |
| 12 | test_settings_migration.py | test_settings_save_atomic |
| 13 | test_bandpilot_md.py (neu) | test_bandpilot_md_generates_24_rows |
| 14 | test_bandpilot_md.py | test_bandpilot_md_handles_missing_data_gracefully |
| 15 | test_mw_radio_bandpilot.py (neu, Smoke) | test_maybe_apply_bandpilot_auto_calls_set_rx_mode_direct |
| 16 | test_mw_radio_bandpilot.py | test_maybe_apply_bandpilot_manual_dialog_only_when_top1_diff |
| 17 | test_mw_radio_bandpilot.py | test_maybe_apply_bandpilot_silent_when_insufficient_data |
| 18 | test_mw_radio_bandpilot.py | test_maybe_apply_bandpilot_skips_during_dx_tuning |

Pingpong-Schutz und TX-Schutz Tests sind durch #4 + #5 (Toleranz) und
durch #15 (E2E Auto-Verhalten mit TX-Mock) abgedeckt — keine separaten
Tests noetig.

**Phase:** 11 (Tests final).

#### R1-5: Alter Cache `~/.simpleft8/bandpilot_summary.json`

**Verifiziert:** Datei existiert (1191 Bytes, 02.05.2026 14:50).

V0.88 nutzt neuen Cache `bandpilot_hourly.json`. Alter bleibt sonst
liegen → Verwirrung in spaeteren Versionen.

**V3-AK 33:** Settings-Migration (Phase 3) raeumt den alten Cache:
```python
def _migrate_bandpilot_settings_v088(self):
    if "bandpilot_mode" in self._data:
        return
    # ... bandpilot_enabled / diversity_pref handling ...
    # Alten Cache löschen falls vorhanden
    old_cache = Path.home() / ".simpleft8" / "bandpilot_summary.json"
    if old_cache.exists():
        try:
            old_cache.unlink()
        except OSError:
            pass  # nicht kritisch
    self.save()
```

**Phase:** 3 (Settings-Migration).

### 🟡 OPTIONAL (3 Findings, alle aufgenommen)

#### R1-6: README Migrations-Hinweis

**V3-AK 34:** README.md bekommt im Bandpilot-Abschnitt einen Hinweis-Block
fuer Bestands-User:
```markdown
> **v0.87 → v0.88 Update:** Bandpilot wechselt vom globalen Aggregat
> (S+D)/2 zur stunden-genauen Empfehlung. Bestehende Settings werden
> automatisch migriert (`bandpilot_enabled=true` → `mode="auto"`).
```

**Phase:** 9 (Doku) oder 10 (README).

#### R1-7: 13 Commits statt 11

**V3-AK 35:** Phase-Plan auf **13 atomare Commits** erweitert:

| # | Phase | Inhalt |
|---|---|---|
| 1 | mode_recommender Refactor | aggregate_stats_by_hour + recommend_for_hour + Toleranz-Helper + Tests #1-#8 |
| 2 | core/bandpilot_md.py | write_bandpilot_md + Tests #13-#14 |
| 3 | Settings Migration + Atomicity | _migrate_bandpilot_settings_v088 + atomic save() + alter Cache loeschen + Tests #9-#12 |
| 4 | Settings-Dialog Combo-Update | bandpilot_mode-Combo statt Checkbox+Pref-Combo |
| 5a | mw_radio: Override-Set raus + diversity_pref-Cleanup | _bandpilot_overridden_bands + _bandpilot_setting_mode raus, alte Bandpilot-Klasse-Referenzen entfernen |
| 5b | mw_radio: _maybe_apply_bandpilot neu | mit Stunden-Logik + Tests #15-#18 |
| 6 | Toast-Dialog (Auto) | QDialog mit Frameless+Tool, parent-zentriert, 3s self-close |
| 7 | Manuell-Dialog | mit 1/2/3-Markern, Top-1 gruen, ●-Marker fuer aktuell |
| 8 | TX-Schutz + Statusbar | tx_finished-Verifikation/Polling-Fallback, statusBar.showMessage(text, 5000) |
| 9 | App-Start-Hook | _init_bandpilot_recommendations in _init_optional_features |
| 10 | Doku DE+EN | docs/explained/bandpilot_de.md + bandpilot.md komplett neu |
| 11 | README + HISTORY-Stub + APP_VERSION 0.88 | inkl. Migrations-Hinweis |
| 12 | Final-R1-Codereview | nach pytest-grün |
| 13 | HISTORY/HANDOFF/CLAUDE/Memory + Push + GitHub-Release v0.88 | Mike-Triggered |

#### R1-8: Alter `BandpilotSummaryCache` aufraeumen

**V3-AK 36:** Klasse `BandpilotSummaryCache` in
`core/mode_recommender.py` wird **geloescht** und durch neue Klasse
`HourlyBandpilot` ersetzt (mit anderem Cache-Key + neuer
recommend_for_hour-Logik).

Alte Funktionen `aggregate_stats()` und `recommend()` werden ebenfalls
geloescht (komplett ersetzt durch `aggregate_stats_by_hour()` und
`recommend_for_hour()`).

Begruendung: Backwards-Compat-Brueche im Setup-Refactor sind klar
markiert (v0.87 → v0.88 Major-Update). Keine Schatten-API liegen lassen.

**Phase:** 1 (mode_recommender-Refactor).

---

## Konsolidierte Akzeptanzkriterien V3 (alle AKs)

V3 hat **36 Akzeptanzkriterien** insgesamt:
- AK 1-11: V1 (Mike-Konsens)
- AK 12-28: V2 (Self-Review-Praezisierungen)
- AK 29-36: R1-Findings (kritisch + optional)

Vollstaendige AK-Liste in Anhang A unten.

---

## Was V3 explizit NICHT mehr aendert

- 11 V1-AKs bleiben kanonisch (mit V2-Praezisierungen).
- 7-Punkte-Konsens-Snapshot mit Mike bleibt unangetastet.
- Versionsbump v0.87.1 → v0.88.
- Out-of-Scope-Liste bleibt:
  - Default-Modus pro Band
  - Band-Empfehlung (Wechsel auf besseres Band)
  - 10-Min-Hysterese (erst wenn Pingpong im Feld)
  - Manueller Bandpilot-Dialog-Button
  - Color-Symbol-Pattern (nur Zahlen-Marker)

## Migrations-Aspekte (zusammengefasst)

1. `bandpilot_enabled=false` → `bandpilot_mode="off"`
2. `bandpilot_enabled=true` → `bandpilot_mode="auto"`
3. `bandpilot_diversity_pref` wird verworfen (alle Varianten)
4. Alter Cache `bandpilot_summary.json` wird geloescht
5. `Settings.save()` wird atomar (tmp+replace) — auch fuer Nicht-Bandpilot-Pfade
6. `BandpilotSummaryCache`-Klasse + alte API-Funktionen geloescht

---

## Risiken + Mitigations

| Risiko | Mitigation |
|---|---|
| `tx_finished`-Signal existiert nicht im Encoder | Phase 8: grep + ggf. Signal hinzufuegen, Fallback QTimer-Polling |
| Settings.save()-Atomicity bricht Code der nicht-atomares Verhalten erwartet | Sehr unwahrscheinlich — `os.replace` ist auf POSIX und macOS atomar; bestehender Code arbeitet eh mit save+load-Cycle |
| Phase 5 mw_radio-Refactor hat Cycle-Loop-Effekte | Test-Suite muss nach Phase 5 komplett gruen sein, sonst Phase 6 nicht starten |
| Manuell-Dialog blockiert UI bei langsamer Pipeline | Dialog non-modal mit timeout-fallback (User kann zwischendurch das Band wieder wechseln, alter Dialog wird geschlossen — V2-AK 21) |
| MIN_DAYS_HOUR=3 zu streng → 6 Monate kein 03-UTC-Vergleich | Realistisch: Mike funkt eh selten um 03 UTC. Falls Bedarf: spaeter MIN_DAYS_HOUR pro Stunde dynamisch (out of scope V1) |

---

## Naechster Schritt

V3 ist fertig. Mike-Freigabe einholen:

> "Wenn V3 OK ist → Plan-Mode oeffnen, Plan-Datei mit den 13 Phasen
> erstellen. Erst danach Code."

Bei Anpassungswuensch: V3 patchen, dann Plan.

---

## Anhang A: Vollstaendige AK-Liste

### V1-AKs (1-11) — Mike-Konsens 2026-05-04

1. Drei direkte Stunden-Werte aus Statistik (KEINE Aggregation)
2. Markdown-Empfehlungs-Datei pro Band (`auswertung/Bandpilot-<band>-FT8.md`)
3. Settings-Combo `bandpilot_mode` ∈ {off, auto, manual}
4. AUTO-Modus: max-Pick mit Toleranz, 3s-Toast mittig
5. MANUELL-Modus: Dialog nur wenn Top-1 != aktueller Modus, R1-smart
6. Stille bei zu wenig Daten: Statusbar-Hinweis 5s
7. TX-Schutz: Modus-Wechsel verzoegern bis tx_finished
8. Pingpong-Schutz: nur 5%-Toleranz, Hysterese spaeter
9. Datenbasis-Schwellen: MIN_DAYS_HOUR=3, MIN_CYCLES_HOUR=20
10. Mind. 6 neue Tests + 2 Smoke-Tests (V3 → 18 Tests)
11. Doku-Komplett-Update DE+EN

### V2-AKs (12-28) — Self-Review-Praezisierungen

12. Toleranz gegen aktuellen Mean, nicht Top-2 (KORRIGIERT V1-AK 4)
13. recommend_for_hour returnt strukturiertes dict (None, top1, ranking, decision, decision_mode)
14. Lazy-Aggregation pro Band + JSON-Cache (`bandpilot_hourly.json`, TTL 24h)
15. MD-Datei nur DE, Format `Tage·Mean`, `—` bei leer
16. Robustheit bei fehlendem Stats-Dir
17. Settings-Migration idempotent, alte Keys raus (`pop()`)
18. Bandpilot reagiert NUR bei Bandwechsel (kein Stunden-Tick)
19. Defensiv: bei dx_tuning skippen (current_mode=None)
20. Toast/Dialog parent-relative + WA_DeleteOnClose + Frameless+Tool
21. Schnelle Bandwechsel: alten Toast/Dialog vor neuem schliessen
22. Encoding-Konvention fixiert (Settings vs Code vs UI vs Stats-Dir)
23. MD-Generator in `core/bandpilot_md.py` (NICHT `tools/`)
24. Alte Kandidat-A-Tests loeschen + neue Tests
25. `tx_finished`-Signal verifizieren in Phase 8
26. Phase 4 (Settings-Dialog) VOR Phase 5 (mw_radio-Logik)
27. HISTORY.md v0.88-Eintrag erwaehnt v0.87-Replacement explizit
28. `bandpilot_mode`-Existenz = Migrations-Marker (kein extra Key)

### R1-AKs (29-36) — DeepSeek-R1-Findings

29. `Settings.save()` atomar (tmp+replace)
30. Alte `bandpilot_diversity_pref`-Refs in mw_radio.py entfernen
31. recommend_for_hour: Datenbasis-Check VOR Toleranz-Vergleich
32. Test-Liste auf 18 Tests erweitert (V2's 11 + R1's 7)
33. Alter Cache `bandpilot_summary.json` bei Migration loeschen
34. README Migrations-Hinweis fuer Bestands-User
35. 13 atomare Commits (V2's 11 + Splits)
36. `BandpilotSummaryCache` + alte API-Funktionen komplett loeschen

---

## Anhang B: Datei-Inventar nach v0.88

### Neue Dateien
- `core/bandpilot_md.py` (~80 Zeilen, MD-Generator)
- `tests/test_bandpilot_md.py` (Tests #13-#14)
- `tests/test_settings_migration.py` (Tests #9-#12)
- `tests/test_mw_radio_bandpilot.py` (Tests #15-#18)
- `auswertung/Bandpilot-20m-FT8.md` (App-Start-generiert)
- `auswertung/Bandpilot-40m-FT8.md` (App-Start-generiert)
- `~/.simpleft8/bandpilot_hourly.json` (neuer Cache, App-managed)
- `prompts/bandpilot_stundenlogik_v3.md` (dieses Dokument)

### Geloeschte Dateien
- `~/.simpleft8/bandpilot_summary.json` (Migration-Cleanup)

### Massiv aktualisierte Dateien
- `core/mode_recommender.py` (alte API komplett ersetzt)
- `ui/mw_radio.py` (`_maybe_apply_bandpilot` neu, Override-Set raus)
- `ui/settings_dialog.py` (Combo-Update)
- `config/settings.py` (DEFAULTS + Migration + atomic save)
- `tests/test_mode_recommender.py` (9 Tests raus, 8 neue)
- `docs/explained/bandpilot_de.md` (komplett neu)
- `docs/explained/bandpilot.md` (komplett neu)
- `README.md` (Bandpilot-Sektion + Migrations-Hinweis)
- `HISTORY.md` (v0.88-Entry)
- `HANDOFF.md` (in beiden Pfaden)
- `CLAUDE.md` (Header in beiden Pfaden)
- `MEMORY.md` (Index-Update)

### App-Version
- `main.py:APP_VERSION` von `"0.87.1"` auf `"0.88"`
