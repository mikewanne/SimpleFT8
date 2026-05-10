# P22.PRESET-ATOMARITAET — V2 (nach Self-Review)

## Aenderungen V1 → V2

V1-Self-Review hat 15 Lessons identifiziert. V2 macht V1's Annahmen
praezise, schliesst Race-Lecks, klaert offene Designentscheidungen und
erweitert die Testbasis. Mike-Klaerungsfragen am Ende.

---

## 1. Symptom (unveraendert)

DX direkt nach App-Start: `MESSEN 0/6` haengt, Antennen-Switch greift
nicht, A2 sammelt nichts. Mike-Workaround: Normal → Standard →
Kalibrieren → laeuft. Half-State-File ist die Wurzel.

Mike-Diagnose 14:35:
> „wenn eine von beiden eintraegen verstaerkung und/oder diversity fehlt
> oder fehlerhaft ist und nur einer geladen werden kann kommt es
> vermutlich zu den fehler weil die app entweder beide oder keinen wert
> erwartet"

## 2. Wurzel-Bedingung im Code (verifiziert)

Zwei separate Schreibstellen ohne gemeinsamen Commit:

| Phase | Schreibstelle | Trigger |
|---|---|---|
| Phase 2 (Gain) | `ui/mw_radio.py:1203` `store.save_gain(...)` | DXTuneDialog akzeptiert |
| Phase 3 (Ratio) | `ui/mw_cycle.py:273` `_store.save_ratio(...)` | `phase: measure→operate`-Uebergang in `_evaluate` |

`_evaluate` (`core/diversity.py:536`) wird gerufen wenn:
- `_measure_step >= MEASURE_CYCLES` (regulaer, FT8: 8 Zyklen ≈ 2 Min)
- Adaptiv-Stop (`core/diversity.py:_check_early_stop`) — setzt
  `_was_early_stopped = True`

Bei Adaptiv-Stop wird `save_ratio` BEWUSST geskipped (mw_cycle.py:269+278,
v0.91 Cache-Schutz).

Wenn `_evaluate` nie gerufen wird (Antennen-Switch greift nicht,
`_measure_step` bleibt 0), bleibt `phase = "measure"` ewig. Half-State
auf Disk: nur `gain_*` gefuellt, kein `ratio_*`. Restart triggert
`_check_diversity_preset` Branch „gain fresh + ratio missing" → Auto-
Phase-3-Versuch → haengt wieder.

`_check_diversity_preset` (`ui/mw_radio.py:956-1013`) Dispatcher:

| gain | ratio | Aktion |
|---|---|---|
| stale | beliebig | DXTuneDialog (auto-start) |
| missing | beliebig | volle Pipeline |
| fresh | fresh | Cache-Reuse (Phase 3 skip) |
| **fresh** | **stale/missing** | **Auto-Ratio-Mess (Phase 3)** ← Half-State-Falle |

## 3. Backwards-Compat-Falle (V2-L1 — neu erkannt)

`core/preset_store.py:_migrate_timestamps_in_entry` (Z. 73-87) spiegelt
alten `timestamp` beim Load auf **beide** neue Felder
(`gain_timestamp` UND `ratio_timestamp`) — auch wenn nie ein Phase-3-
Mess durchlief. Folge: Ein altes File mit `{"timestamp": ..., "ant1_gain":
10}` (ohne `"ratio"`) wird als „beide Timestamps frisch" geladen, aber
`is_valid_ratio` returnt False weil `"ratio"`-Feld fehlt
(preset_store.py:139). Migration ist also robust.

ABER: Ein File mit `gain_*` neu geschrieben (Phase 2 done, Phase 3
haengt) hat `gain_timestamp` aber **kein** `ratio_timestamp` und kein
`ratio`. Heutige `is_valid_gain` returnt True. Heutige
`is_valid_ratio` returnt False. Genau die Half-State-Falle.

V2-Loesung: `is_valid_gain` zusaetzlich pruefen ob `ratio`-Feld
existiert. Wenn nicht, returnt False (Half-State-Reject). Die Atomic-
Commit-Logik garantiert: nach commit_with_ratio sind immer beide Felder
da. Vor commit_with_ratio sind beide weg.

## 4. Akzeptanzkriterien V2

A1. **Atomares Persist:** `gain_*` und `ratio_*` werden nur
    gemeinsam auf Disk geschrieben. Phase 2 alleine produziert keinen
    Disk-Eintrag — Wert lebt im Memory bis Phase 3 fertig ist.

A2. **Half-State-Reject beim Load:** `is_valid_gain` returnt False
    fuer Eintraege ohne `ratio`-Feld (V2-L1). Sichert Backwards-Compat
    UND faengt jeden Half-State ab — auch File-System-Beschaedigung
    oder externe Edits.

A3. **Restart sauber:** Wenn Phase 3 zwischen Phase 2 und Disk-Write
    abbricht (Hang, Crash, App-Quit, Bandwechsel), liest naechster
    Restart `is_valid_gain == False` → `_check_diversity_preset` faellt
    in `gain missing`-Branch (volle Pipeline) statt Half-State-Branch.

A4. **Robustheit-Fallback:** Wenn Phase 3 nach `STALL_LIMIT_CYCLES`
    Zyklen kein `_measure_step`-Inkrement zeigt (echter Hang, nicht
    nur langsamer Fortschritt — V2-L6), greift Fallback. Fallback-
    Verhalten Mike-Frage Q1 (siehe §9).

A5. **Backwards-Compat:** Bestehende Files mit `_migrate_timestamps_in_entry`-
    geretteten Timestamps werden weiter geladen. Ist `ratio`-Feld da →
    fresh. Sonst → Half-State-Reject.

A6. **Diversity-Algorithmus unangetastet:** Mess-Algorithmus,
    Threshold, Median, Antennen-Switch — bleiben 1:1.

A7. **Lifecycle-Sicher:** `discard_staged` wird bei JEDEM Lifecycle-
    Event aufgerufen, das eine staged-Phase ungueltig macht (V2-L2).
    Liste in §6.

A8. **Adaptiv-Stop sauber:** Bei `_was_early_stopped == True` wird
    `discard_staged` aufgerufen statt `commit_with_ratio` (V2-L3).
    Erhaelt v0.91-Cache-Schutz: Adaptiv-Stop-Werte landen nicht im
    Cache. Mit Atomic-Pattern bleibt Memory dann auch sauber.

A9. **Atomic File Write:** `_save_locked` nutzt `tempfile.NamedTemporary
    File(dir=parent)` + `os.replace` (V2-L4). Verhindert korrupte JSON
    bei Mid-Write-Crash. Standard-Pattern aus P2.ADIF-ARCHIVE.

A10. **Stage/Commit-Konsistenz:** `stage_gain` immer parallel zu
     `_pending_dx_diversity = True` (V2-L8). Wenn nicht, assert + Log.

## 5. Loesungs-Architektur

### 5a. PresetStore-Erweiterung (`core/preset_store.py`)

```python
class PresetStore:
    def __init__(self, filename: str):
        ...
        # Neuer In-Memory-Buffer fuer staged-Eintraege.
        # Key = self._key(band, ft_mode), Value = dict mit gain-Feldern.
        self._staged: dict[str, dict] = {}

    def stage_gain(self, band, ft_mode, *, rxant, ant1_gain, ant2_gain,
                   ant1_avg=0.0, ant2_avg=0.0) -> None:
        """Phase-2-Werte in Memory parken. KEIN Disk-Write,
        KEIN gain_timestamp."""
        key = self._key(band, ft_mode)
        with self._lock:
            self._staged[key] = {
                "rxant":     rxant,
                "ant1_gain": int(ant1_gain),
                "ant2_gain": int(ant2_gain),
                "ant1_avg":  round(float(ant1_avg), 1),
                "ant2_avg":  round(float(ant2_avg), 1),
            }

    def commit_with_ratio(self, band, ft_mode, *, ratio, dominant) -> bool:
        """Phase-3-Erfolg: staged Gain + ratio atomar persistieren.
        Returns True wenn staged vorhanden, sonst False (Aufrufer-Fehler)."""
        key = self._key(band, ft_mode)
        now = time.time()
        with self._lock:
            staged = self._staged.pop(key, None)
            if staged is None:
                return False  # nichts zu committen → Aufrufer-Bug
            entry = dict(self._data.get(key) or {})
            entry.update(staged)
            entry["gain_timestamp"]  = now
            entry["ratio"]           = ratio
            entry["dominant"]        = dominant or "A1"
            entry["ratio_timestamp"] = now
            entry["measured"]        = time.strftime("%Y-%m-%d %H:%M")
            self._data[key] = entry
            self._save_locked()
        return True

    def discard_staged(self, band, ft_mode) -> bool:
        """Staged-Eintrag verwerfen. Returns True wenn etwas weg war."""
        key = self._key(band, ft_mode)
        with self._lock:
            return self._staged.pop(key, None) is not None

    def has_staged(self, band, ft_mode) -> bool:
        """Diagnostik / Test-Helper."""
        with self._lock:
            return self._key(band, ft_mode) in self._staged

    # is_valid_gain ergaenzt (V2-L1):
    def is_valid_gain(self, band, ft_mode) -> bool:
        with self._lock:
            entry = self._data.get(self._key(band, ft_mode))
        if not entry or "gain_timestamp" not in entry:
            return False
        if "ratio" not in entry:           # NEU: Half-State-Reject
            return False
        if (time.time() - entry["gain_timestamp"]) >= GAIN_VALIDITY_SECONDS:
            return False
        return True

    # _save_locked: tempfile + os.replace (V2-L4)
    def _save_locked(self) -> None:
        self._filepath.parent.mkdir(parents=True, exist_ok=True)
        tmp = tempfile.NamedTemporaryFile(
            mode="w", dir=str(self._filepath.parent),
            delete=False, prefix=".tmp_", suffix=".json")
        try:
            json.dump(self._data, tmp, indent=2)
            tmp.flush()
            os.fsync(tmp.fileno())
            tmp.close()
            os.replace(tmp.name, str(self._filepath))
        except Exception:
            try:
                os.unlink(tmp.name)
            except OSError:
                pass
            raise
```

`save_gain` und `save_ratio` bleiben fuer Normal-Mode + Backwards-Compat
+ Tests. Werden im Diversity-Pipeline-Pfad **nicht** mehr genutzt.

### 5b. Pipeline-Anpassung (`ui/mw_radio.py`)

`_on_dx_tune_accepted` (Z. 1191):

```
if rx_mode == "normal":
    store.save_gain(...)            # unveraendert: kein Phase-3-Anschluss
    return

# rx_mode == "diversity":
if pending_ratio == "fresh":
    store.save_gain(...)            # Gain stale, Ratio fresh → kein Stage
    cache_reuse → return

# Diversity volle Pipeline (pending_dx_diversity True ODER gain stale):
store.stage_gain(...)               # NEU: nur Memory, kein Disk
_pending_dx_diversity = True        # garantiert (V2-L8 Konsistenz)
_enable_diversity → Phase 3 startet
```

### 5c. Phase-3-Erfolgs-Pfad (`ui/mw_cycle.py:259-280`)

```
old: _store.save_ratio(band, mode, ratio, dominant)
new:
    if _early_stopped:
        _store.discard_staged(band, mode)       # V2-L3 Cache-Schutz bleibt
        # bestehende Logik: Adaptiv-Stop log
    else:
        ok = _store.commit_with_ratio(band, mode, ratio=..., dominant=...)
        if not ok:
            print("[Diversity] commit_with_ratio: kein staged → Bug?")
            # Fallback: alter save_ratio damit nicht ganz verloren
            _store.save_ratio(band, mode, ratio=..., dominant=...)
```

### 5d. Phase-3-Stall-Detector (`core/diversity.py` + `ui/mw_cycle.py`)

V2-L6 Praezisierung: NICHT „N Zyklen seit Mess-Start" sondern „N
aufeinanderfolgende Zyklen ohne `_measure_step`-Inkrement".

In `core/diversity.py`:

```python
class DiversityController:
    STALL_LIMIT_CYCLES = 12   # ~3 Min FT8, ~1.5 Min FT4

    def __init__(...):
        ...
        self._stall_counter = 0
        self._last_measure_step_seen = 0

    def tick_stall_check(self) -> bool:
        """In jedem mw_cycle._on_cycle_decoded waehrend phase=='measure'
        aufrufen. Returns True wenn Stall-Limit ueberschritten — Aufrufer
        triggert Fallback."""
        if self.phase != "measure":
            self._stall_counter = 0
            return False
        if self._measure_step != self._last_measure_step_seen:
            self._last_measure_step_seen = self._measure_step
            self._stall_counter = 0
            return False
        self._stall_counter += 1
        return self._stall_counter >= self.STALL_LIMIT_CYCLES

    def reset(self):
        ...
        self._stall_counter = 0
        self._last_measure_step_seen = 0
```

In `ui/mw_cycle.py:_on_cycle_decoded` (nach `record_measurement`-Block):

```python
if self._diversity_ctrl.tick_stall_check():
    self._handle_phase3_stall(band, ft_mode, scoring)
```

`_handle_phase3_stall` ist Mike-Frage Q1 abhaengig.

### 5e. Lifecycle-Cleanup (V2-L2)

`discard_staged(band, ft_mode)` wird zusaetzlich gerufen in:

| Ort | Trigger | Was |
|---|---|---|
| `_disable_diversity` (mw_radio.py:904) | RX-Mode wechselt von diversity → normal | Aktuelles band+mode |
| `_on_band_changed` | Bandwechsel | Altes Band + ft_mode |
| `_on_mode_changed` | FT-Modus-Wechsel | Band + alter ft_mode |
| `closeEvent` (main_window.py) | App-Quit | Alle staged Eintraege im store |

App-Quit cleart staged → keine Geister-Eintraege beim naechsten Start.

## 6. Files & Aenderungen

| Datei | Aenderung |
|---|---|
| `core/preset_store.py` | + `stage_gain`, `commit_with_ratio`, `discard_staged`, `has_staged` + `is_valid_gain` Half-State-Reject + `_save_locked` atomic write |
| `core/diversity.py` | + `STALL_LIMIT_CYCLES`, `_stall_counter`, `_last_measure_step_seen`, `tick_stall_check`, Reset in `reset` |
| `ui/mw_radio.py` | Z. 1203 Diversity-Pfad: `save_gain` → `stage_gain` + `_pending_dx_diversity = True` Garantie |
| `ui/mw_radio.py` | + `discard_staged`-Aufrufe in `_disable_diversity`, `_on_band_changed`, `_on_mode_changed` |
| `ui/mw_radio.py` | + `_handle_phase3_stall` (Mike-Q1 abhaengig) |
| `ui/mw_cycle.py` | Z. 273 `save_ratio` → `commit_with_ratio` + Adaptiv-Stop-Branch ruft `discard_staged` |
| `ui/mw_cycle.py` | + `tick_stall_check`-Hook nach `record_measurement` |
| `ui/main_window.py` | + `closeEvent` cleart `_standard_store._staged` + `_dx_store._staged` |
| `tests/test_preset_store.py` | + 5 Tests (T1-T5) |
| `tests/test_p22_preset_atomic.py` | NEU: T6-T11 (E2E-Pipeline + Race + Stall) |
| `HISTORY.md` | Versions-Eintrag |
| `HANDOFF.md` | Stand-Update |
| `MEMORY.md` | Lesson-Eintrag „Atomic-Persist-Pattern" |

## 7. Tests V2

| # | Name | Was geprueft |
|---|---|---|
| T1 | `test_stage_gain_no_disk_write` | `stage_gain` schreibt nicht ins File |
| T2 | `test_commit_with_ratio_writes_atomic` | beide Timestamps + ratio + dominant gesetzt, File aktualisiert |
| T3 | `test_commit_without_stage_returns_false` | `commit_with_ratio` ohne stage → False, kein Schreiben |
| T4 | `test_discard_staged_clears_memory` | `discard_staged` cleart, `has_staged` False danach |
| T5 | `test_is_valid_gain_rejects_half_state` | File mit `gain_*` ohne `ratio` → `is_valid_gain == False` (V2-L1) |
| T6 | `test_pipeline_diversity_uses_stage_then_commit` | E2E `_on_dx_tune_accepted` Diversity-Pfad ruft stage |
| T7 | `test_pipeline_normal_uses_save_gain_direct` | Normal-Mode ruft weiter `save_gain` direkt |
| T8 | `test_disable_diversity_discards_staged` | RX-Mode-Wechsel cleart staged |
| T9 | `test_band_change_during_phase3_discards_staged` | Race: Bandwechsel mid-Phase-3 → staged weg (V2-L9) |
| T10 | `test_adaptive_stop_discards_staged` | `_was_early_stopped == True` → discard, kein Commit (V2-L3) |
| T11 | `test_stall_detector_triggers_fallback` | 12 Zyklen ohne `_measure_step`-Inkrement → `tick_stall_check` returnt True |
| T12 | `test_close_event_clears_all_staged` | App-Quit cleart staged in beiden Stores |
| T13 | `test_save_locked_atomic_uses_tempfile` | Mid-Write-Crash hinterlaesst kein korruptes File (mock os.replace) |
| T14 | `test_multi_band_stage_independent` | 40m_FT8 + 20m_FT8 staged parallel, getrennt commit/discard |

## 8. Was V2 NICHT macht

- KEIN Refactor des Diversity-Mess-Algorithmus.
- KEINE Aenderung an `is_valid_ratio`-Signatur.
- KEINE neue UI-Komponente — nur evtl. Statusbar-Marker (Q1-abhaengig).
- KEIN Anfassen der Legacy-Settings-Pfade `settings.save_dx_preset` /
  `settings.save_diversity_preset` (V2-L5). Die schreiben weiterhin
  sofort, sind aber Bw-Compat-Restwert ohne Lese-Logik in der App.
- KEIN Unwind von P17/P19 — die sind RESOLVED, P22 ist prophylaktisch.

## 9. Mike-Klaerungsfragen

**Q1 — Phase-3-Stall-Fallback-Verhalten:**
Was soll passieren wenn `tick_stall_check` True returnt (12 Zyklen
ohne Mess-Fortschritt)?

a) **Default 50:50 + commit:** App geht in operate mit faked Ratio.
   Mike sieht Histogramm (50:50) und weiss „komisch, war das nicht
   30:70?". Statusbar-Marker `[Default-Ratio Stall]` 60s.

b) **Disable-Diversity-Fallback:** App schaltet auf Normal (ANT1) zurueck
   + Toast „Diversity-Mess hing — zurueck auf ANT1. Bitte neu kalibrieren.".
   Mike muss aktiv neu starten.

c) **Hard-Stop:** App bleibt in measure-Phase haengen wie heute, aber mit
   Toast „Diversity-Mess haengt seit 3 Min — moeglicherweise Antennen-
   Hardware-Problem". Kein Auto-Heilen.

V2-Vorschlag: **(b) Disable-Diversity** — sauberer, kein Fake-Wert,
Mike behaelt Kontrolle. (a) ist gefaehrlich weil 50:50 mit dominanter
Antenne ein Diversity-Schaden-Pattern erzeugt.

**Q2 — Bandwechsel mid-Phase-3:**
Was passiert mit staged-Gain wenn Mike mid-Phase-3 Band wechselt?

a) **Discard sofort:** Bei Rueckkehr zu altem Band muss Phase 2 + 3 neu
   laufen. Mike-Annoyance bei haeufigem Bandwechsel.

b) **Keep staged:** Beim Rueckkehren wird staged Gain weiter genutzt + nur
   Phase 3 neu. Memory waechst, aber Performance besser.

V2-Vorschlag: **(a) Discard** — KISS, kein Memory-Wachstum, kein
Stale-Risk. Bandwechsel mid-Mess ist Edge-Case.

**Q3 — Adaptiv-Stop weiter ohne Persist?**
Heute wird `save_ratio` bei `_was_early_stopped` geskipped (v0.91 Cache-
Schutz). V2-A8 sagt: discard_staged statt commit. Folge: Adaptiv-Stop-
Werte landen nicht auf Disk → Restart kalibriert von vorn.

Ist das so richtig? Oder soll Adaptiv-Stop weiter committen, weil sonst
Mike-Test-Sessions oft komplett neu kalibrieren muessen?

V2-Vorschlag: **alter Behavior beibehalten** (kein Persist bei
Adaptiv-Stop). Wenn Mike das stoert, separater P-Eintrag.

## 10. Aufwand

V2 schaetzt: ~3-4h V2→R1→V3+Code+14 Tests + 30 Min Doku.

## 11. Atomare Commits geplant

- C1: `core/preset_store.py` (`stage_gain`/`commit_with_ratio`/`discard_staged`/`has_staged` + `is_valid_gain` Reject + atomic `_save_locked`)
- C2: `tests/test_preset_store.py` (T1-T5 erweitern, Bestehende Tests anpassen wenn noetig)
- C3: `core/diversity.py` (STALL_LIMIT_CYCLES + tick_stall_check + reset)
- C4: `ui/mw_radio.py` (stage_gain + lifecycle-discard + _handle_phase3_stall)
- C5: `ui/mw_cycle.py` (commit_with_ratio + tick_stall_check-Hook + Adaptiv-Stop discard)
- C6: `ui/main_window.py` (closeEvent staged-Cleanup)
- C7: `tests/test_p22_preset_atomic.py` (T6-T14 NEU, E2E + Race + Stall)
- C8: `main.py` APP_VERSION + HISTORY/HANDOFF/MEMORY-Update
