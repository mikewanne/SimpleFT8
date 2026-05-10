# P23.OMNI-COUNTER-EIGEN — V2 (nach Self-Review)

## Aenderungen V1 → V2 (8 Lessons)

V1-Self-Review hat 15 Punkte gefunden, davon 8 fuer V2 relevant
(restliche 7 waren Detail-Verifikation, in V1 schon korrekt). V2 macht
KISS-Optimierungen + Migrations-Plan praeziser.

- **L1: `_get_target` nur einmal in `start()`** — Modus kann waehrend
  OMNI nicht wechseln (mw_radio.py:212 ruft `stop("mode_change")`).
  Resume + reset_after_measure nutzen `self._cq_target` statt neu zu
  lesen. Spart Code, verhindert versehentliche Modus-Refresh-Logik.

- **L2: Auto-Flip kein doppel-emit** — V1 emittierte `cq_count_changed`
  zweimal (remaining=0 → flip → remaining=TARGET). UI haette „0" fuer
  Millisekunden gesehen. KISS: nur ein emit am Ende.

- **L3: T12+T15 redundant** — wenn `on_search_trigger`-Methode nicht
  existiert, kann mw_cycle sie nicht aufrufen. T12 (`hasattr(omni,
  'on_search_trigger') == False`) reicht. T15 raus.

- **L4: Signal-Format minimal `(remaining, tx_even)`** — UI zeigt nur
  remaining im Statusbar, target ist Konstante. Tests die target
  brauchen koennen `omni.cq_target` Property abfragen. Kein Need fuer
  3-Arg-Signal.

- **L5: Display-Suffix ANS ENDE** — Mike-Original-Format war
  `13:30:45 [O] →  Sende   CQ DA1MHH JO31` und „ergaenzen". Counter
  geht ans Ende, NACH ant_label.
  Final: `13:30:45 [O] →  Sende   CQ DA1MHH JO31   (ANT2)  ↻10`

- **L6: Migration der bestehenden Tests detailliert** — 2 Tests in
  `test_omni_cq_signal.py:96, 355` lauschen `cq_count_changed` mit
  2-Arg-Lambda. Format aendert sich nicht (siehe L4) → diese Tests
  bleiben! Aber alle `on_search_trigger`-Tests muessen weg/umfunktioniert.

- **L7: Field-Test-Plan ergaenzt** (V2 §10).

- **L8: `_cq_tx_even is None` defensive bei reset_counter_after_measure**
  — wenn vor erstem on_cycle_start `reset_counter_after_measure` gerufen
  wird (theoretisch), darf nicht crashen. `bool(self._cq_tx_even or False)`.

---

## 1. Wurzel-Bedingung im Code (V1 unveraendert)

`core/omni_cq.py:35` `_OMNI_FLIP_AFTER_SEARCHES = 10` Konstante.
`_search_trigger_count` zaehlt **Such-Trigger vom Diversity-System**.
`on_search_trigger()` wird aus `mw_cycle.py:166` gerufen wenn
`_diversity_ctrl.tick_slot()` True returnt (alle 60s). Bei
`_search_trigger_count >= 10` → `flip_tx_parity()` + Counter-Reset.

**Schwaeche:** Coupling zu Diversity-Mess-Mechanik. Wenn Mess haengt,
kein Such-Trigger, kein Paritaets-Wechsel. Brueckhaufes Design.

## 2. Akzeptanzkriterien

A1. **Counter pro Modus:** `_OMNI_TARGETS = {"FT8": 10, "FT4": 20,
    "FT2": 40}`. In `start()` einmalig `self._cq_target =
    _OMNI_TARGETS.get(timer.mode, 10)`.

A2. **Down-Count nach TX:** Nach `encoder.transmit == True`:
    `_cq_remaining -= 1`. Wenn `_cq_remaining == 0` → `flip_tx_parity()`
    + `_cq_remaining = _cq_target` **VOR** dem Signal-Emit (KISS, nur 1
    Emit pro Slot — L2).

A3. **QSO-Reset:** `resume_after_qso()` setzt `_cq_remaining =
    _cq_target` + emit cq_count_changed.

A4. **Mess-Reset:** Neue Methode
    `reset_counter_after_measure()` aus mw_cycle bei Phase-Uebergang
    `measure → operate` gerufen. Resettet `_cq_remaining = _cq_target`
    + emit. No-op wenn nicht aktiv oder paused.

A5. **Bandwechsel/Modus-Wechsel:** OMNI **stop** — bereits implementiert
    (mw_radio.py:212 mode_change, mw_radio.py:327 band_change). KEIN
    Code-Change.

A6. **on_search_trigger entfaellt:** Methode + Feld
    `_search_trigger_count` + Konstante `_OMNI_FLIP_AFTER_SEARCHES` weg.
    Hook in `mw_cycle.py:163-166` weg.

A7. **Display-Suffix:** `qso_panel.add_tx` bekommt `omni_remaining: int |
    None = None`. Suffix `  ↻{remaining}` ans **ENDE** der Zeile (nach
    ant_label).

A8. **Diversity unangetastet:** Mess-Algorithmus + Such-Counter selbst
    + Threshold + Median + Antennen-Switch — bleiben 1:1.

A9. **Encoder-Pfad unangetastet:** `transmit(message, tx_even,
    audio_freq_hz)` bleibt.

A10. **Pause-Verhalten:** Bei `pause()` bleibt `_cq_remaining`
     unveraendert. Bei `is_paused == True` wird kein TX ausgefuehrt
     (existing on_cycle_start guard) → Counter dekrementiert nicht.

A11. **Signal-Format:** `cq_count_changed = Signal(int, bool)` bleibt
     `(remaining, tx_even)` — KEINE Aenderung (L4). UI-Code unveraendert.

A12. **Statusbar-Format:** `Ω CQ={remaining} ({parity_str})` (KISS,
     ohne `/target`).

A13. **Defensive emit-bool:** Bei `_cq_tx_even is None` wird in
     `reset_counter_after_measure` `False` als Fallback emittiert (Qt
     `Signal(bool)` darf nicht None bekommen).

## 3. Architektur

### 3a. `core/omni_cq.py`

```python
# Modulebene (statt _OMNI_FLIP_AFTER_SEARCHES):
_OMNI_TARGETS = {"FT8": 10, "FT4": 20, "FT2": 40}
_OMNI_DEFAULT_TARGET = 10  # Fallback fuer unbekannte Modi


class OmniCQ(QObject):
    cq_count_changed = Signal(int, bool)   # (remaining, current_tx_even)
    parity_flipped = Signal(bool)
    # Andere Signals unveraendert

    def __init__(self, encoder, diversity_ctrl, timer,
                 my_call: str, my_grid: str):
        ...
        self._cq_remaining = 0
        self._cq_target = _OMNI_DEFAULT_TARGET
        # WEG: self._search_trigger_count

    @property
    def cq_remaining(self) -> int:
        return self._cq_remaining

    @property
    def cq_target(self) -> int:
        return self._cq_target

    # WEG: @property cq_count

    def start(self) -> None:
        if self._active:
            return
        self._active = True
        self._paused = False
        self._cq_audio_hz = None
        self._cq_tx_even = None
        # P23: Counter aus Modus ableiten (einmalig im start)
        mode = getattr(self._timer, 'mode', 'FT8')
        self._cq_target = _OMNI_TARGETS.get(mode, _OMNI_DEFAULT_TARGET)
        self._cq_remaining = self._cq_target
        self.omni_started.emit()
        logger.info("[OMNI-CQ] Start (Modus %s, Counter %d)",
                    mode, self._cq_target)

    def stop(self, reason: str) -> None:
        if not self._active:
            return
        self._active = False
        self._paused = False
        self._cq_audio_hz = None
        self._cq_tx_even = None
        self._cq_remaining = 0
        self._cq_target = _OMNI_DEFAULT_TARGET
        self.omni_stopped.emit(reason)
        logger.info("[OMNI-CQ] Stop (%s)", reason)

    def resume_after_qso(self, last_was_even=None) -> None:
        if not self._paused:
            logger.warning("[OMNI-CQ] resume_after_qso ohne pause — ignoriert")
            return
        self._paused = False
        # P23-A3: QSO-Reset = neuer Slot startet bei TARGET
        self._cq_remaining = self._cq_target
        parity_str = "E" if self._cq_tx_even else "O"
        logger.info("[OMNI-CQ] Resume (Counter %d, Paritaet %s)",
                    self._cq_remaining, parity_str)
        self.cq_count_changed.emit(
            self._cq_remaining,
            bool(self._cq_tx_even) if self._cq_tx_even is not None else False,
        )

    def reset_counter_after_measure(self) -> None:
        """P23-A4: nach Antennen-Mess Counter zurueck auf TARGET.
        Wird aus mw_cycle bei Phase-Uebergang measure->operate gerufen.
        No-op wenn nicht aktiv oder pausiert."""
        if not self._active or self._paused:
            return
        if self._cq_remaining == self._cq_target:
            return  # nichts zu tun
        self._cq_remaining = self._cq_target
        self.cq_count_changed.emit(
            self._cq_remaining,
            bool(self._cq_tx_even) if self._cq_tx_even is not None else False,
        )
        logger.info("[OMNI-CQ] Counter reset nach Mess (auf %d)",
                    self._cq_remaining)

    @Slot(int, bool)
    def on_cycle_start(self, cycle_num, is_even):
        # bestehende Logik bis zum encoder.transmit
        if not self._active or self._paused:
            return
        if self._diversity.phase != "operate":
            return
        slot_dur = self._timer.cycle_duration
        fresh_is_even = (int(time.time() / slot_dur) % 2 == 0)
        if self._cq_tx_even is None:
            self._cq_tx_even = fresh_is_even
        if self._cq_audio_hz is None:
            self._init_audio_freq()
        if fresh_is_even != self._cq_tx_even:
            return

        cq_msg = f"CQ {self._my_call} {self._my_grid}"
        ok = self._encoder.transmit(
            cq_msg, tx_even=self._cq_tx_even,
            audio_freq_hz=self._cq_audio_hz,
        )
        if ok:
            # P23-A2: dekrementieren, ggf. Auto-Flip + Reset, EIN emit
            self._cq_remaining -= 1
            if self._cq_remaining == 0:
                self.flip_tx_parity()
                self._cq_remaining = self._cq_target
            self.cq_count_changed.emit(self._cq_remaining, self._cq_tx_even)
            label = self._slot_label(True, self._cq_tx_even)
            self.slot_action.emit(label, True, self._cq_tx_even)
        else:
            label = self._slot_label(True, self._cq_tx_even)
            logger.warning("[OMNI-CQ] encoder busy -> Slot %s uebersprungen", label)

    # WEG: def on_search_trigger(self) -> None:

    # flip_tx_parity unveraendert (bleibt public)
```

### 3b. `ui/mw_cycle.py` Hook-Umbau

**WEG (Z. 163-166 in `_refresh_diversity_freq_view`):**
```python
# inkrementieren. Bei _OMNI_FLIP_AFTER_SEARCHES (=10)
# Triggern -> flip_tx_parity (alle ~10 Min Wechsel).
if hasattr(self, '_omni_cq') and self._omni_cq:
    self._omni_cq.on_search_trigger()
```

**NEU (im Phase-Uebergang `measure → operate` in
`_handle_diversity_measure` ca. Z. 259+, **NACH** den
`commit_with_ratio`/`discard_staged`-Calls aus P22):**
```python
# P23: nach Antennen-Mess Counter im OMNI auf TARGET resetten
omni = getattr(self, '_omni_cq', None)
if omni is not None:
    omni.reset_counter_after_measure()
```

### 3c. `ui/qso_panel.py:add_tx` — Suffix

```python
def add_tx(self, message: str, ant_label: str = "",
           tx_even: bool | None = None,
           slot_start_ts: float | None = None,
           omni_remaining: int | None = None):
    """... (bestehender Doc bleibt)
    omni_remaining: P23 — wenn nicht None: Suffix `  ↻{n}` ans Ende
    der Zeile (nach ant_label) anhaengen.
    """
    if slot_start_ts is None or tx_even is None:
        now = time.time()
        slot = getattr(self, '_cycle_duration', 15.0)
        slot_start_ts = now - (now % slot)
        tx_even = int(slot_start_ts / slot) % 2 == 0
    utc = time.strftime("%H:%M:%S", time.gmtime(slot_start_ts))
    tag = "[E]" if tx_even else "[O]"
    line = f"{utc} {tag} →  Sende   {message}"
    suffix = f"  ↻{omni_remaining}" if omni_remaining is not None else ""
    if ant_label:
        # ant_label bleibt in seiner Akzentfarbe; Counter dahinter
        if suffix:
            self._append_three_color(
                line, "#FFAA00",
                f"   {ant_label}", "#888888",
                suffix, "#FFAA00",
            )
        else:
            self._append_two_color(line, "#FFAA00", f"   {ant_label}", "#888888")
    elif suffix:
        self._append_colored(line + suffix, "#FFAA00")
    else:
        self._append_colored(line, "#FFAA00")
```

(Wenn `_append_three_color` nicht existiert: einfach line + ant_label +
suffix als ein farbiger Block via `_append_colored` ausgeben — Detail
bei der Code-Phase entscheiden, abhaengig von vorhandenen Helpern.)

### 3d. `ui/mw_qso.py:_on_tx_started` — Counter holen

```python
def _on_tx_started(self, message: str, tx_even: bool, slot_start_ts: float):
    ant_label = ""  # bleibt wie heute (P15: ant_label-Logic raus)
    omni_remaining = None
    omni = getattr(self, '_omni_cq', None)
    if omni is not None and omni.is_active() and not omni.is_paused():
        omni_remaining = omni.cq_remaining
    self.qso_panel.add_tx(
        message, ant_label,
        tx_even=tx_even, slot_start_ts=slot_start_ts,
        omni_remaining=omni_remaining,
    )
```

### 3e. `ui/main_window.py` — Statusbar (klein)

`_on_omni_cq_count_changed` Signatur bleibt `(count, tx_even)` — count
heisst jetzt `remaining`, semantisch. Variable umbenennen, sonst nichts.

```python
def _on_omni_cq_count_changed(self, remaining: int, tx_even: bool):
    self._omni_cq_remaining = remaining       # umbenannt von _omni_cq_count
    self._omni_cq_tx_even = tx_even
    self._update_statusbar()
```

`_update_statusbar` Format: `Ω CQ={remaining} ({parity_str})`.

## 4. Files & Aenderungen

| Datei | Aenderung |
|---|---|
| `core/omni_cq.py` | Counter-Refactor (down + auto-flip + reset_after_measure). `_OMNI_FLIP_AFTER_SEARCHES` + `on_search_trigger` weg. `_OMNI_TARGETS` neu. |
| `ui/mw_cycle.py` | Hook-Umbau: search-trigger raus, mess-reset rein. |
| `ui/qso_panel.py` | `add_tx` Parameter `omni_remaining` + Suffix `↻N`. |
| `ui/mw_qso.py` | `_on_tx_started` liest `omni.cq_remaining`. |
| `ui/main_window.py` | `_on_omni_cq_count_changed` Variable-Rename + Statusbar-Format-Update (Helper). |
| `tests/test_omni_cq_signal.py` | Bestehende `on_search_trigger`-Tests entfernen oder als Negative-Tests umbauen. Lauscher mit 2-Arg-Lambda bleiben. |
| `tests/test_p23_omni_counter.py` | NEU: T1-T14 Counter + Display + Hook-Refactor. |
| `main.py` | APP_VERSION 0.96.6 → 0.96.7 |
| `HISTORY.md` + `HANDOFF.md` + `CLAUDE.md` + Memory | Updates. |

## 5. Tests V2

| # | Name | Was geprueft |
|---|---|---|
| T1 | `test_start_initializes_remaining_to_target_for_ft8` | start() FT8: _cq_remaining == 10 |
| T2 | `test_start_target_for_ft4` | start() FT4: _cq_remaining == 20 |
| T3 | `test_start_target_for_ft2` | start() FT2: _cq_remaining == 40 |
| T4 | `test_start_target_default_for_unknown_mode` | start() unbekannt: _cq_remaining == 10 |
| T5 | `test_tx_decrements_remaining` | nach 1 erfolgreichem TX: remaining == TARGET-1 |
| T6 | `test_tx_busy_does_not_decrement` | encoder.transmit returnt False → remaining unveraendert |
| T7 | `test_remaining_reaches_zero_triggers_flip_and_reset` | TARGET TXs: nach letztem Auto-Flip + remaining == TARGET (1 Emit, kein Zwischen-0) |
| T8 | `test_resume_after_qso_resets_remaining` | pause + resume_after_qso → remaining == TARGET + 1 emit |
| T9 | `test_reset_counter_after_measure_resets_remaining` | reset_counter_after_measure → remaining == TARGET + 1 emit |
| T10 | `test_reset_counter_after_measure_noop_when_inactive` | not active → no-op (kein emit) |
| T11 | `test_reset_counter_after_measure_noop_when_paused` | paused → no-op |
| T12 | `test_pause_does_not_reset_remaining` | pause() → remaining unveraendert |
| T13 | `test_stop_resets_remaining_to_zero_and_target_to_default` | stop() → remaining == 0, target == 10 |
| T14 | `test_on_search_trigger_method_removed` | `not hasattr(omni, 'on_search_trigger')` |
| T15 | `test_qso_panel_add_tx_with_omni_remaining_renders_suffix` | Whitebox add_tx mit omni_remaining=7 → output enthaelt `↻7` |
| T16 | `test_mw_cycle_calls_reset_counter_on_phase_operate` | mw_cycle Phase-Uebergang ruft `reset_counter_after_measure` |
| T17 | `test_mw_cycle_no_search_trigger_call_anymore` | Spy: `_omni_cq.on_search_trigger` wird in `_refresh_diversity_freq_view` NICHT aufgerufen (Lambda: `assert not hasattr(omni, 'on_search_trigger')` reicht — T14 deckt das, T17 = T14) |
| T18 | `test_cq_count_changed_signal_2args_format` | emit `(remaining: int, tx_even: bool)` — 2 Args wie heute |

T17 entfaellt → redundant zu T14. **16 Tests**.

## 6. Field-Test-Plan (V2-L7)

**F1. App-Start, OMNI in FT8:** Statusbar zeigt `Ω CQ=10 (E)` oder
`(O)`. TX-Zeile in qso_panel: `13:30:45 [E] →  Sende   CQ DA1MHH JO31  ↻10`

**F2. 5 Min beobachten (10 TXs in FT8):** Counter laeuft 10 → 9 → ... → 1.
Nach dem 10. TX: Paritaets-Wechsel automatisch (Log-Eintrag), neuer Slot
mit `Ω CQ=10` in anderer Paritaet.

**F3. Modus-Wechsel zu FT4:** OMNI **stoppt** (heutiges Verhalten),
Statusbar leer.

**F4. Modus-Wechsel zu FT4 + OMNI manuell wieder an:** Statusbar zeigt
`Ω CQ=20`. TX-Zeile zeigt `↻20`.

**F5. QSO eingehend (Antwort kommt):** OMNI pausiert, QSO laeuft. Nach
QSO: OMNI resumed, Counter zurueck auf TARGET (10/20/40), TX-Display
zeigt `↻TARGET` ab naechstem CQ.

**F6. Antennen-Mess startet:** OMNI sendet nicht waehrend Mess (existing
V2-L12 Schutz). Nach Mess (~90s): Counter zurueck auf TARGET.

**F7. Bandwechsel mid-OMNI:** OMNI auto-stop (band_change), Statusbar leer.

**F8. Counter Display visuell:** TX-Zeile am Ende `  ↻N` mit weicher
Akzentfarbe, ant_label sichtbar dazwischen wenn aktiv.

**Bestanden wenn:** F1-F5 sauber. F6 (Mess-Reset) muss in echter Mess
beobachtet werden.

## 7. Was V2 NICHT macht

- KEIN Refactor der Diversity-Mess-Mechanik.
- KEIN Refactor des Encoders.
- KEINE neue UI-Komponente (nur Suffix in TX-Zeile).
- KEIN Auto-Resume bei Bandwechsel/Modus-Wechsel.

## 8. Aufwand

V2 schaetzt: ~2-3h V3+Code+16 Tests + 30 Min Doku + Final-R1.

## 9. Atomare Commits geplant

- C1 `core/omni_cq.py` Counter-Refactor (search_trigger raus, target +
  reset + auto-flip + signal bleibt 2-arg)
- C2 `tests/test_omni_cq_signal.py` Anpassungen (search_trigger-Tests
  raus, neue counter-tests in C7)
- C3 `ui/mw_cycle.py` Hook-Umbau
- C4 `ui/qso_panel.py` add_tx Suffix
- C5 `ui/mw_qso.py` _on_tx_started Counter-Read
- C6 `ui/main_window.py` Variable-Rename + Statusbar-Format
- C7 `tests/test_p23_omni_counter.py` NEU T1-T16
- C8 `main.py` APP_VERSION + HISTORY/HANDOFF/CLAUDE/Memory
