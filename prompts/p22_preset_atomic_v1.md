# P22.PRESET-ATOMARITAET — V1 (initialer Entwurf)

## 1. Symptom

Bei App-Start direkt in **Diversity DX** haengt die Antennenvergleichs-
Messung (Phase 2) bei `MESSEN 0/6` — kein Antennen-Switch, A2 sammelt nichts:

```
[Diversity] 48 St. | A1>A2: 0 | A2>A1: 0 (0%) | Nur A1: 48 | Nur A2: 0
```

Workaround Mike: Normal → Diversity Standard → Kalibrieren → laeuft. Dann
ist die `presets_dx.json` heute erstmals sauber durchgelaufen und seitdem
funktionieren alle Mode-Wechsel. ABER: das File hatte **vorher** ueber
Tage einen Half-State (Verstaerker-Wert frisch, Ratio fehlt) — der
triggert bei jedem Restart wieder den Versuch Phase 2 zu starten.

Mike-Diagnose 14:35 (Compact-Quelle):
> „wenn eine von beiden eintraegen verstaerkung und/oder diversity fehlt
> oder fehlerhaft ist und nur einer geladen werden kann kommt es
> vermutlich zu den fehler weil die app entweder beide oder keinen wert
> erwartet"

## 2. Wurzel-Bedingung im Code

Zwei separate Schreibstellen, **kein gemeinsamer Commit**:

| Phase | Wer ruft | Wo | Wann gespeichert |
|---|---|---|---|
| Phase 2 (Verstaerker, „Gain") | `_on_dx_tune_accepted` | `ui/mw_radio.py:1203` `store.save_gain(...)` | **Sofort** beim Akzeptieren des DXTuneDialog |
| Phase 3 (Antennenvergleich, „Ratio") | `_evaluate`-Pfad nach Mess | `ui/mw_cycle.py:273` `_store.save_ratio(...)` | **Nur** wenn Mess sauber durchlief und nicht abgebrochen wurde |

Verifikation in `core/preset_store.py`:
- `save_gain` (171-191) setzt `gain_timestamp = time.time()` + `_save_locked()`
- `save_ratio` (193-206) setzt `ratio_timestamp = time.time()` + `_save_locked()`
- `is_valid_gain` (125-131) und `is_valid_ratio` (133-141) sind voellig
  unabhaengig — kein Cross-Check.

Dispatcher `ui/mw_radio.py:_check_diversity_preset` (956-1013) hat einen
4-Wege-Branch:

| gain | ratio | Aktion |
|---|---|---|
| stale | beliebig | DXTuneDialog (auto-start) |
| missing | beliebig | volle Pipeline |
| fresh | fresh | Cache-Reuse (Phase 3 skip) |
| **fresh** | **stale/missing** | **Auto-Ratio-Mess (Phase 3)** ← Half-State-Falle |

Der letzte Branch (Z. 1008-1012) ist die Endlos-Schleife: Wenn Phase 3
hängt (z.B. Antennen-Switch greift nicht), wird nichts gespeichert,
Restart liest dasselbe Half-State-File, Branch trifft wieder zu, Phase 3
hängt wieder.

## 3. Akzeptanzkriterien (was V1 garantieren muss)

A1. **Atomares Persist:** `gain_timestamp` und `ratio_timestamp` werden
    nur **gemeinsam** auf Disk geschrieben. Phase 2 alleine produziert
    keinen Disk-Eintrag mehr — der Wert lebt bis Phase 3 fertig ist nur
    im RAM.

A2. **Restart sauber:** Wenn Phase 3 zwischen Phase 2 und Disk-Write
    abbricht (Hang, Crash, App-Quit, Bandwechsel), liest der naechste
    Restart `is_valid_gain == False` und `is_valid_ratio == False` →
    `_check_diversity_preset` faellt in den `gain missing`-Branch (volle
    Pipeline) statt in den Half-State-Branch.

A3. **Robustheit-Fallback:** Wenn Phase 3 nach `MAX_PHASE3_CYCLES`
    Zyklen (oder Wallclock-Timeout) keinen brauchbaren Ratio-Wert
    liefert (z.B. `MESSEN 0/6` ohne Fortschritt), schreibt der Code
    explizit Default `50:50` mit `dominant="A1"` + frischem
    `ratio_timestamp` → atomares Speichern + Markierung „Fallback
    angewandt" im Log. App geht damit in operate, statt endlos in
    measure zu kleben.

A4. **Backwards-Compat:** Bestehende `presets_dx.json` /
    `presets_standard.json` mit altem Format (gain ohne ratio) werden
    beim Load weiter erkannt — aber `is_valid_gain` returnt für solche
    Half-State-Eintraege **False**, damit der Restart sie ignoriert und
    Phase 2 von vorn beginnt.

A5. **Diversity unangetastet:** Mess-Algorithmus, Threshold, Median,
    Antennen-Switch-Logik bleiben 1:1 wie vorher — nur der Speicher-
    Pfad und der Restart-Pfad aendern sich.

## 4. Loesungs-Skizze (Mike-Option 3 — atomar + Fallback)

### 4a. Atomares Speichern

Neue Methoden in `core/preset_store.py`:

- `stage_gain(band, ft_mode, **fields)` — speichert in In-Memory-Buffer
  `self._staged: dict[str, dict] = {}`, **kein** Disk-Write, **kein**
  `gain_timestamp`-Set.
- `commit_with_ratio(band, ft_mode, *, ratio, dominant)` — schreibt
  staged Gain + Ratio zusammen mit beiden Timestamps in einem
  `_save_locked()`-Call.
- `discard_staged(band, ft_mode)` — Memory-Cleanup bei Abbruch.

`save_gain` bleibt fuer Normal-Mode (Phase 2 nur, kein Phase 3) und
Tests.

### 4b. Pipeline-Anpassung

`ui/mw_radio.py:_on_dx_tune_accepted` (Z. 1203):
- Bei `_pending_dx_diversity == True` (Diversity-Pfad): **stage_gain**
  statt `save_gain`.
- Bei Normal-Mode (kein Phase 3 geplant): weiter `save_gain` direkt.

`ui/mw_cycle.py:273` `_store.save_ratio(...)`:
- Ersetzen durch `_store.commit_with_ratio(...)`.

`ui/mw_radio.py:_disable_diversity` / Bandwechsel / Mode-Wechsel:
- `discard_staged(band, ft_mode)` falls staged-Eintrag vorhanden.

### 4c. Robustheit-Fallback

In `core/diversity.py` oder `ui/mw_cycle.py` Phase-3-Loop:
- Counter `_phase3_attempt_cycles` (z.B. ≤ 12 Zyklen ≈ 3 Min).
- Wenn nach Counter-Ueberschreitung kein Mess-Fortschritt
  (`measure_step == 0`): Fallback `commit_with_ratio(ratio="50:50",
  dominant="A1")` + Log `[Diversity] Phase 3 Timeout — Default 50:50
  gespeichert`.

## 5. Tests

T1. `test_stage_gain_no_disk_write` — `stage_gain` aendert
    `~/.simpleft8/kalibrierung/presets_dx.json` **nicht**.
T2. `test_commit_with_ratio_writes_both` — `commit_with_ratio` setzt
    beide Timestamps und schreibt File.
T3. `test_discard_staged_clears_memory` — nach `discard_staged` ist
    `is_valid_gain == False`.
T4. `test_half_state_rejected_on_load` — File mit `gain_timestamp`
    aber ohne `ratio_timestamp` liefert `is_valid_gain == False`
    (Backwards-Compat).
T5. `test_phase3_timeout_writes_default_ratio` — Mock Phase 3 hängt
    bei `measure_step == 0` über 12 Zyklen → Default `50:50`
    geschrieben + Log-Eintrag.
T6. `test_pipeline_diversity_uses_stage_then_commit` — End-to-End
    `_on_dx_tune_accepted` ruft stage statt save bei Diversity-Pfad.
T7. `test_pipeline_normal_uses_save_gain_direct` — Normal-Mode-
    Kalibrieren ruft weiter `save_gain` (atomar nicht noetig).
T8. `test_disable_diversity_discards_staged` — `_disable_diversity`
    cleart staged Eintrag.

## 6. Offene Fragen / Trade-offs

Q1. Sollen wir das Half-State-Reject in A4 hart machen
    (`is_valid_gain == False` wenn `ratio_timestamp` fehlt)? Oder weich
    (eigener Status `half`, der nur im Code Action triggert aber alte
    Workflows nicht bricht)? V1-Vorschlag: hart — KISS, sauberer
    Restart.

Q2. Phase-3-Fallback-Schwelle: 12 Zyklen (3 Min) oder Wallclock
    (90s + 60s Puffer)? V1-Vorschlag: Zyklen-basiert weil Phase 3
    laufzeit-abhaengig vom Modus ist (FT8/FT4/FT2).

Q3. Default-Ratio im Fallback: `50:50` oder ehemaliger gespeicherter
    Wert? V1-Vorschlag: `50:50` neutral — wenn der alte Wert verlaesslich
    waere, haetten wir ihn nicht ueberschreiben muessen.

Q4. Soll der Fallback einen sichtbaren Hinweis im UI machen (Toast oder
    Statusbar-Text), damit Mike den Phase-3-Hang merkt? V1-Vorschlag:
    ja — Statusbar-Marker `[Default-Ratio]` für 60s.

## 7. Was V1 NICHT macht

- KEIN Refactor des Mess-Algorithmus.
- KEINE Aenderung an `is_valid_gain`/`is_valid_ratio`-Signaturen
  (nur am Inhalt).
- KEINE neue UI-Komponente — nur Statusbar-Marker.
- KEIN Unwind von P17/P19 — die sind RESOLVED, dieser Fix ist
  prophylaktisch fuer das naechste Mal dass Phase 3 hängt.

## 8. Aufwand

V1 schaetzt: ~3h V1→V2→R1→V3+Code+Tests + 30 Min Doku.

## 9. Files die geaendert werden

- `core/preset_store.py` — neue Methoden `stage_gain`,
  `commit_with_ratio`, `discard_staged` + Half-State-Reject in `_load`.
- `ui/mw_radio.py` Z. 1203 — `save_gain` → `stage_gain` im Diversity-
  Pfad.
- `ui/mw_cycle.py` Z. 273 — `save_ratio` → `commit_with_ratio`.
- `ui/mw_cycle.py` (Phase-3-Loop) — Timeout-Counter + Default-Fallback.
- `tests/test_preset_store.py` — T1-T5 erweitern.
- `tests/test_p22_preset_atomic.py` (NEU) — T6-T8.
- `HISTORY.md` + `HANDOFF.md` + `MEMORY.md` Updates.
