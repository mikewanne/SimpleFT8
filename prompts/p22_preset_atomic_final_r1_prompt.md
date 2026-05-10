# Final-R1: Code-Review P22.PRESET-ATOMARITAET + P8.MESS-MODAL (v0.96.6)

## Auftrag

Du bekommst den **fertigen Code** der V3-Implementierung. Pruefe ob die
V3-Akzeptanzkriterien (V3 §3 A1-A14) korrekt umgesetzt sind, ob R1-K1/K2/K3
sauber adressiert sind, und ob neue Issues entstanden sind.

## Code-Stand

**Version:** v0.96.6 lokal (noch nicht commited)
**Tests:** 1019 → 1034 grün (15 neue Pipeline+Modal-Tests)

## Was umgesetzt wurde

### Baustein A — Atomares Persist
- `core/preset_store.py`:
  - `stage_gain` (Memory-Buffer, kein Disk)
  - `commit_with_ratio` (atomar Gain+Ratio, **R1-K1: staged.pop NACH erfolgreichem _save_locked**, in-memory Rollback bei Disk-Fehler)
  - `discard_staged` / `discard_all_staged` / `has_staged`
  - `is_valid_gain` Half-State-Reject (kein `ratio` → False)
  - `_save_locked` atomic via `tempfile.NamedTemporaryFile + os.fsync + os.replace`
  - `save_gain` / `save_ratio` Exception-Catch + Rollback + bool return (**R1-K3**)

### Baustein B — Mess-Modal
- `ui/mess_status_dialog.py` NEU:
  - `WindowModality.WindowModal` (NICHT ApplicationModal — Decoder-Signale müssen durchkommen)
  - Tick-Timer 500ms
  - Cancel-Button setzt `cancelled=True` und ruft `reject()`
  - `set_cycle_dur` Helper für FT8/FT4/FT2

### Pipeline-Anpassungen
- `ui/mw_radio.py`:
  - `_on_dx_tune_accepted` Pipeline-Pfad: `will_run_phase3 = (rx_mode == "diversity" and pending_ratio != "fresh")` → stage_gain. Sonst save_gain.
  - `_open_mess_status_dialog` (in `_enable_diversity` Phase=measure-Pfad)
  - `_on_mess_status_cancelled` (Cancel → discard staged + Diversity aus)
  - `_close_mess_status_dialog` (auto-close nach Phase=operate)
- `ui/mw_cycle.py`:
  - Z. ~273: `save_ratio` → `commit_with_ratio` mit `save_ratio`-Fallback
  - Adaptiv-Stop-Branch: `discard_staged` (kein Persist)
  - Modal auto-close nach `commit_with_ratio`
- `ui/main_window.py:closeEvent`:
  - Modal hart schliessen falls offen
  - `discard_all_staged` für beide Stores

### Stall-Detector NICHT gebaut
Mike-Klärung 10.05.: Q1 unbestätigt (Hänger war bei QSO-Ende = P12, nicht
bei Antennenmessung). Wurzel-Diagnose Antennen-Switch separat als P23.

## V3-Akzeptanzkriterien (siehe `prompts/p22_preset_atomic_v3.md` §3)

A1 atomares Persist | A2 Half-State-Reject | A3 Restart sauber |
A4 Disk-Fehler ohne Verlust | A5 Disk-Fehler ohne Crash |
A6 Atomic File Write | A7 Modal sperrt UI | A8 Modal auto-close |
A9 Cancel sauber | A10 App-Quit cleart | A11 Adaptiv-Stop ohne Persist |
A12 Diversity-Algo unangetastet | A13 Modal-Live-Updates |
A14 Cancel safe waehrend Mess

## Was du pruefen sollst

### A. R1-K1/K2/K3-Adressierung

A1. **R1-K1:** Staged.pop() ERST nach erfolgreichem `os.replace` —
    sauber umgesetzt? Code-Pfad in `commit_with_ratio` lesen, prüfen.
A2. **R1-K2:** Modal sperrt Bandwechsel/Mode-Wechsel — Mike-Klärung,
    daher `discard_staged` bei `_on_band_changed`/`_on_mode_changed`
    NICHT nötig. Sind die Pfade trotzdem irgendwo offen die zum
    Half-State führen könnten? Z.B. `_disable_diversity` oder Settings-
    Reload?
A3. **R1-K3:** Alle Schreibmethoden returnen bool, kein re-raise. Wirklich
    alle? Auch indirekte Pfade (`migrate_from_settings`, `save_gain` aus
    Normal-Mode, `save_ratio` aus Settings-Bw-Compat)?

### B. V3-Akzeptanzkriterien

B1. A1-A14 — wirklich alle erfüllt? Welche fehlen oder sind nur teilweise?
B2. **A14 (Cancel safe):** Was passiert wenn Cancel gerade in dem Moment
    gedrückt wird wo `commit_with_ratio` läuft? Race?

### C. Modal-Lifecycle Race-Conditions

C1. Was passiert wenn Mess sehr schnell durchläuft (~Adaptiv-Stop) und
    `phase=operate` triggert BEVOR Modal ganz offen ist? Wird `_close_mess_status_dialog`
    sauber? `getattr(self, '_mess_status_dialog', None)` defensive aber sicher?
C2. Was wenn Cancel gleichzeitig mit auto-close kommt? `cancelled` Flag-Sequenz.
C3. App-Quit (`closeEvent`) während Modal offen — wird `dlg.reject()` sauber?
    Tick-Timer gestoppt?

### D. Pipeline-Branch-Logik

D1. `_on_dx_tune_accepted` will_run_phase3-Logik korrekt? Edge-Cases
    bei `_pending_ratio_status`-Werten ('fresh'/'stale'/'missing'/None)?
D2. `_pending_dx_diversity = True` Setzung in stage-Branch — wird das
    spaeter im _enable_diversity-Pfad korrekt zurückgesetzt? Konflikt
    mit existierender Logik (mw_radio.py:1280-1287)?
D3. Cache-Reuse-Pfad (mw_radio.py:1259-1278): `pending_ratio == "fresh"`
    → `save_gain` direkt — Sicher dass Cache-Reuse keine Phase 3 mehr
    triggert?

### E. Tests

E1. Decken die 15 P22-Tests + 13 PresetStore-Tests die kritischen Pfade ab?
E2. Sind die Spy-Tests (T9-T11) wirklich Spy oder verkappt mock-heavy?
E3. Halluziniere nichts — wenn du behauptest „Test X fehlt", verweise
    konkret auf Datei:Zeile wo der ungeprüfte Code-Pfad ist.

### F. Was übersieht der Code

F1. Andere Half-State-Pfade die nicht durch P22 erfasst sind?
F2. Settings-Bw-Compat (`settings.save_diversity_preset` in mw_cycle.py)
    schreibt sofort — könnte das ein Half-State-Vektor sein?
F3. `_apply_dx_preset` in mw_radio.py:1402 — liest aus PresetStore.
    Was wenn dort gerade staged-Daten vorhanden sind statt persistente?

## Form deiner Antwort

- **KRITISCH** (Bug, muss vor Push raus): Datei:Zeile + Begründung
- **SOLLTE** (Verbesserung empfohlen): konkret + Begründung
- **KOENNTE** (Optional)
- **Push-Empfehlung:** Push freigegeben | Push nach KRITISCH-Fix | Push blockiert

KISS-Bewertung am Ende.

---

## Files (Anhang)

`core/preset_store.py`, `ui/mess_status_dialog.py`, `ui/mw_radio.py`,
`ui/mw_cycle.py`, `ui/main_window.py`, `tests/test_preset_store.py`,
`tests/test_p22_preset_atomic.py`
