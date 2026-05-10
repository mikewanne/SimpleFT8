# Final-R1: Code-Review P23.OMNI-COUNTER-EIGEN (v0.96.7)

## Auftrag

Du bekommst den **fertigen Code** der V3-Implementierung. Pruefe ob die
V3-Akzeptanzkriterien (V3 §3 A1-A14) korrekt umgesetzt sind, ob R1-K1/K2
+ S1-S3 sauber adressiert sind, und ob neue Issues entstanden sind.

## Code-Stand

**Version:** v0.96.7 lokal (noch nicht commited)
**Tests:** 1035 → 1049 grün (17 neue P23-Tests, 3 search_trigger-Tests gelöscht)

## Was umgesetzt wurde

### Counter-Refactor (`core/omni_cq.py`)
- `_OMNI_TARGETS = {"FT8": 10, "FT4": 20, "FT2": 40}` neu (~5 Min Wallclock)
- `_OMNI_DEFAULT_TARGET = 10` Fallback
- `_OMNI_FLIP_AFTER_SEARCHES` + `_search_trigger_count` + `on_search_trigger` weg
- `_cq_count` (UP) → `_cq_remaining` (DOWN) + `_cq_target`
- `cq_count` Property → `cq_remaining` + `cq_target`
- `start()`: target aus `timer.mode` einmalig
- `on_cycle_start`: dekrementieren + Auto-Flip-bei-0 + Reset auf TARGET +
  GENAU 1 Emit pro Slot
- `resume_after_qso()`: Reset auf TARGET + Emit
- `reset_counter_after_measure()`: NEU, no-op wenn nicht aktiv ODER paused

### Hook-Umbau (`ui/mw_cycle.py`)
- Z. ~163-166 `_omni_cq.on_search_trigger()` Hook WEG
- `_handle_diversity_measure` Phase=operate-Übergang (Z. ~324):
  `omni.reset_counter_after_measure()` NEU

### Display (`ui/qso_panel.py:add_tx`)
- Optional `omni_remaining: int | None = None` Parameter
- Suffix `  ↻{n}` direkt an `line` (KISS, nutzt existing `_append_two_color`/
  `_append_colored`, kein neuer Helper)

### TX-Handler (`ui/mw_qso.py:_on_tx_started`)
- Bei `omni.is_active() and not omni.is_paused()` → `omni.cq_remaining`
  durchreichen

### Statusbar (`ui/main_window.py`)
- `_on_omni_cq_count_changed` Param `count` → `remaining`
- `_update_statusbar`: `Ω CQ={cq_remaining} ({parity_str})`

### Test-Migration (`tests/test_omni_cq_signal.py`)
- 3 LOESCHEN: `test_on_search_trigger_*` (T8, T8b, T14)
- 6 ANPASSEN: `test_start_initial_state` (cq_count→cq_remaining=TARGET),
  T3 (matching → TARGET-1), T4 (non_matching → TARGET unverändert),
  T10 (resume → TARGET), T12 (stop → 0), busy_encoder
- Import `_OMNI_FLIP_AFTER_SEARCHES` → `_OMNI_TARGETS`

### Neue Tests (`tests/test_p23_omni_counter.py`)
17 Tests T1-T16 + 1 Bonus (siehe Liste).

## V3-Akzeptanzkriterien (V3 §3)

A1 Counter pro Modus | A2 Down-Count + Auto-Flip + 1 Emit |
A3 QSO-Reset | A4 Mess-Reset | A5 Bandwechsel/Modus stop (kein Code-Change) |
A6 on_search_trigger weg | A7 Display-Suffix | A8 Diversity unangetastet |
A9 Encoder unangetastet | A10 Pause-Verhalten | A11 Signal-Format unverändert
(2-arg) | A12 Statusbar | A13 defensive bool-Cast | A14 Tests-Migration vollständig

## Was du pruefen sollst

### A. Counter-Logik

A1. `on_cycle_start` Auto-Flip-Pfad korrekt? Was wenn `_cq_remaining` mit
    `_cq_target = 1` startet (theoretisch wenn jemand `_cq_target` manuell
    setzt)? Edge-Case: dekrementieren auf 0 + flip, aber `_cq_target` ist
    immer noch 1 → Reset auf 1 → wieder 0 nach 1 TX → endloser Flip jeden Slot?
A2. `_get_target` heisst nur in `start()` — wirklich sicher dass Modus-
    Wechsel immer `stop` ruft? `mw_radio.py:212` ja, aber gibt es andere
    Pfade die `_timer.mode` ändern ohne stop zu rufen?
A3. `reset_counter_after_measure` no-op-Logik (paused) sinnvoll? Was wenn
    Mess endet WÄHREND OMNI paused (=QSO läuft)? Reset würde verlorengehen.
    Wird der Reset später beim resume_after_qso nachgeholt? Ja — resume
    setzt Counter auf TARGET. ✓ Aber: wenn Mess endet während pause,
    kommt resume später → Counter wird trotzdem reset. OK.

### B. Race / Threading

B1. `on_cycle_start` und `reset_counter_after_measure` beide aus GUI-
    Thread (Qt-Slots) → kein Lock nötig?
B2. Bei Auto-Flip in `on_cycle_start`: `flip_tx_parity()` emittiert
    `parity_flipped`. Direkt danach `cq_count_changed.emit`. Reihenfolge
    OK für UI?
B3. Was wenn pause() zwischen `_cq_remaining -= 1` und `cq_count_changed.
    emit` gerufen wird (theoretisch)? Counter-Wert konsistent?

### C. Display

C1. Suffix `  ↻N` — KISS-Variante OK? Suffix steht VOR ant_label-Block
    (in Hauptzeile drin). Visuell sinnvoll?
C2. `↻` Symbol U+21BB — Font-Risiko? Tests prüfen `↻7 in toPlainText()`.
C3. Counter im Statusbar wechselt von "1" direkt auf "TARGET" (Auto-Flip),
    nie auf "0". V3-A2 erfüllt — bestätigen.

### D. Tests

D1. T7 Spy-Pattern (R1-S1) — verifiziert wirklich „1 Emit pro Slot"?
    `len(captured) == TARGET` für TARGET TXs (10 Emits, nicht 11).
    Sauber?
D2. T15 prüft `not hasattr(OmniCQ, 'on_search_trigger')` UND `not hasattr
    (omni_mod, '_OMNI_FLIP_AFTER_SEARCHES')` — vollständig?
D3. T16/T16b Display-Tests verlassen sich auf `panel.log_view.toPlainText`
    — funktioniert das offscreen?

### E. Migration

E1. `tests/test_omni_cq_signal.py:test_pause_resume_preserves_parity`
    (T10) ANPASSEN: `_cq_remaining = 5` setzen + nach resume `cq_remaining
    == TARGET` (Reset-Verhalten). Tests grün → bestätigt.
E2. Bestehende UI-Code-Stellen die `omni.cq_count` lesen — alle gefunden
    und auf `cq_remaining` umgestellt?

### F. Was übersieht der Code

F1. Andere Stellen die `cq_count`/`_cq_count` referenzieren?
F2. Doku-Strings/Comments die noch alte Begriffe nutzen?
F3. Race wenn Mode-Wechsel via mw_radio.py:212 stop() ruft, aber stop()
    läuft mid-on_cycle_start? Oder ist on_cycle_start auch GUI-Thread?

## Form deiner Antwort

- **KRITISCH** (Bug, muss vor Push raus): Datei:Zeile + Begründung
- **SOLLTE** (Verbesserung empfohlen): konkret + Begründung
- **KOENNTE** (Optional)
- **Push-Empfehlung:** Push freigegeben | Push nach KRITISCH-Fix | Push blockiert

KISS-Bewertung am Ende.

---

## Files (Anhang)

`core/omni_cq.py`, `ui/mw_cycle.py`, `ui/qso_panel.py`, `ui/mw_qso.py`,
`ui/main_window.py`, `tests/test_omni_cq_signal.py`,
`tests/test_p23_omni_counter.py`
