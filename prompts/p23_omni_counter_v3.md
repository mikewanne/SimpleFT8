# P23.OMNI-COUNTER-EIGEN — V3 (Compact-fest, EINZIGE WAHRHEIT)

## Aenderungen V2 → V3 (nach R1)

R1 fand 2 KRITISCH + 3 SOLLTE — alle in V3 adressiert.

- **R1-K1 (Test-Migration unklar):** V2 sagte „Lauscher mit 2-Arg bleiben"
  ohne zu nennen welche Tests konkret kippen wuerden. V3 §5.2 listet
  jeden bestehenden Test mit Action (BLEIBT/ANPASSEN/LOESCHEN).

- **R1-K2 (`_append_three_color` existiert nicht):** V3 §3c nutzt KISS-
  Variante mit nur `_append_colored` + `_append_two_color` (kein neuer
  Helper). Counter direkt an `line` angehaengt, ant_label danach grau.

- **R1-S1 (T7 wie testen):** V3 §6 T7 explizit Spy-Pattern: Liste
  initialisieren vor Slot-Aufruf, nach Slot `len(captured) == 1`
  asserten — beweist „kein Zwischen-0-emit".

- **R1-S2 (T17 Streichung dokumentieren):** V3 §6 erwaehnt T17 explizit
  als gestrichen mit Begruendung.

- **R1-S3 (Fallback konkret):** Erledigt durch K2-Fix.

- **R1-KOENNTE:** angenommen (defensive bool-Cast bleibt + DEFAULT_TARGET
  bleibt).

---

## 1. Spec (Mike 10.05.2026)

OMNI-CQ Paritaets-Wechsel **nicht mehr** ueber Diversity-Such-Counter.
Eigener Counter im OMNI-Modul, sichtbar im TX-Display.

| Aspekt | Verhalten |
|---|---|
| Counter pro Modus | FT8=10, FT4=20, FT2=40 (alle ~5 Min Wallclock) |
| Counter-Logik | DOWN nach jedem TX. Bei 0 → flip + reset auf TARGET |
| QSO eingehend | Counter zurueck auf TARGET (positiv-Verstaerkung) |
| Antennen-Mess fertig | Counter zurueck auf TARGET |
| Bandwechsel | OMNI **stop** (heute schon, kein Aenderung) |
| Modus-Wechsel | OMNI **stop** (heute schon) |
| Display | `13:30:45 [O] → Sende CQ DA1MHH JO31  ↻10   (ANT2)` |
| Statusbar | `Ω CQ=10 (E)` (KISS, ohne /target) |

## 2. Wurzel-Bedingung im Code

`core/omni_cq.py:35` `_OMNI_FLIP_AFTER_SEARCHES = 10` Konstante +
`_search_trigger_count` zaehlt Such-Trigger vom Diversity-System.
`on_search_trigger()` wird aus `mw_cycle.py:166` gerufen wenn
`_diversity_ctrl.tick_slot()` True (alle 60s). Bei `>= 10` →
`flip_tx_parity()` + Counter-Reset.

**Schwaeche:** Coupling zu Diversity-Mess-Mechanik. Wenn Mess haengt,
kein Such-Trigger, kein Paritaets-Wechsel.

## 3. Akzeptanzkriterien

A1. **Counter pro Modus:** Modulebene `_OMNI_TARGETS = {"FT8": 10,
    "FT4": 20, "FT2": 40}`, `_OMNI_DEFAULT_TARGET = 10`. In `start()`
    einmalig `self._cq_target = _OMNI_TARGETS.get(timer.mode, 10)`.

A2. **Down-Count + Auto-Flip + 1 Emit pro Slot:** Nach
    `encoder.transmit == True`:
    ```
    self._cq_remaining -= 1
    if self._cq_remaining == 0:
        self.flip_tx_parity()
        self._cq_remaining = self._cq_target
    self.cq_count_changed.emit(self._cq_remaining, self._cq_tx_even)
    ```
    Genau 1 emit von `cq_count_changed` pro TX-Slot — kein Zwischen-0.

A3. **QSO-Reset:** `resume_after_qso()` setzt `_cq_remaining =
    _cq_target` + emit cq_count_changed.

A4. **Mess-Reset:** Neue Methode `reset_counter_after_measure()` aus
    mw_cycle bei Phase-Uebergang `measure → operate` gerufen. Resettet
    + emit. **No-op wenn nicht aktiv ODER paused** (KISS — wenn paused
    war's gerade ein QSO, resume_after_qso macht Reset selbst).

A5. **Bandwechsel/Modus-Wechsel:** OMNI **stop** — bereits implementiert
    (mw_radio.py:212 mode_change, mw_radio.py:327 band_change). KEIN
    Code-Change.

A6. **on_search_trigger entfaellt:** Methode + Feld
    `_search_trigger_count` + Konstante `_OMNI_FLIP_AFTER_SEARCHES` weg.
    Hook in `mw_cycle.py:163-166` weg.

A7. **Display-Suffix:** `qso_panel.add_tx` bekommt `omni_remaining: int |
    None = None`. Wenn != None: `  ↻{remaining}` direkt an `line`
    anhaengen (in der Hauptfarbe `#FFAA00`). ant_label danach in seiner
    grauen Farbe (`#888888`) wenn vorhanden — wie heute.

A8. **Diversity unangetastet:** Mess-Algorithmus + Such-Counter selbst
    + Threshold + Median + Antennen-Switch — bleiben 1:1.

A9. **Encoder-Pfad unangetastet:** `transmit(message, tx_even,
    audio_freq_hz)` bleibt.

A10. **Pause-Verhalten:** Bei `pause()` bleibt `_cq_remaining`
     unveraendert. Bei `is_paused == True` wird kein TX ausgefuehrt
     (existing on_cycle_start guard) → Counter dekrementiert nicht.

A11. **Signal-Format unveraendert:** `cq_count_changed = Signal(int,
     bool)` bleibt `(remaining, tx_even)` — semantischer Wechsel
     (count → remaining), kein Format-Wechsel. Existing UI-Code
     unveraendert (nur Variable umbenennen).

A12. **Statusbar:** `Ω CQ={remaining} ({parity_str})`.

A13. **Defensive bool-Cast:** Bei `_cq_tx_even is None` wird in
     `reset_counter_after_measure` `False` als Fallback emittiert (Qt
     `Signal(bool)` darf nicht None bekommen).

A14. **Tests-Migration vollstaendig:** Alle bestehenden Tests in
     `tests/test_omni_cq_signal.py` die `cq_count`, `_search_trigger_count`
     oder `_OMNI_FLIP_AFTER_SEARCHES` referenzieren werden EXPLIZIT
     migriert (siehe §5.2 Tabelle).

## 4. Loesungs-Architektur

### 4a. `core/omni_cq.py` — Counter-Refactor

```python
# Modulebene (statt _OMNI_FLIP_AFTER_SEARCHES = 10):
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
        No-op wenn nicht aktiv ODER pausiert (paused-Pfad reset macht
        resume_after_qso selbst).
        """
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
            # P23-A2: dekrementieren, ggf. Auto-Flip + Reset, GENAU 1 emit
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

### 4b. `ui/mw_cycle.py` — Hook-Umbau

**WEG (im `_refresh_diversity_freq_view`, ca. Z. 163-166):**
```python
# inkrementieren. Bei _OMNI_FLIP_AFTER_SEARCHES (=10)
# Triggern -> flip_tx_parity (alle ~10 Min Wechsel).
if hasattr(self, '_omni_cq') and self._omni_cq:
    self._omni_cq.on_search_trigger()
```

**NEU (im Phase-Uebergang `measure → operate` in
`_handle_diversity_measure` ca. Z. 259+, **NACH** den
`commit_with_ratio`/`discard_staged`/`save_diversity_preset`-Calls aus
P22):**
```python
# P23: nach Antennen-Mess Counter im OMNI auf TARGET resetten
omni = getattr(self, '_omni_cq', None)
if omni is not None:
    omni.reset_counter_after_measure()
```

### 4c. `ui/qso_panel.py:add_tx` — KISS-Suffix (R1-K2-Fix)

```python
def add_tx(self, message: str, ant_label: str = "",
           tx_even: bool | None = None,
           slot_start_ts: float | None = None,
           omni_remaining: int | None = None):
    """... (bestehender Doc bleibt)
    omni_remaining: P23 — wenn nicht None: `  ↻{n}` an `line` anhaengen
    (Hauptfarbe). ant_label kommt danach in seiner grauen Farbe wie heute.
    """
    if slot_start_ts is None or tx_even is None:
        now = time.time()
        slot = getattr(self, '_cycle_duration', 15.0)
        slot_start_ts = now - (now % slot)
        tx_even = int(slot_start_ts / slot) % 2 == 0
    utc = time.strftime("%H:%M:%S", time.gmtime(slot_start_ts))
    tag = "[E]" if tx_even else "[O]"
    line = f"{utc} {tag} →  Sende   {message}"
    if omni_remaining is not None:
        line = f"{line}  ↻{omni_remaining}"
    if ant_label:
        # KISS: line (incl. evtl. Counter) in Hauptfarbe + ant_label grau
        self._append_two_color(line, "#FFAA00", f"   {ant_label}", "#888888")
    else:
        self._append_colored(line, "#FFAA00")
    # P1.16: _auto_trim_by_age laeuft via QTimer alle 30s, kein expliziter Aufruf hier
```

### 4d. `ui/mw_qso.py:_on_tx_started` — Counter holen

```python
def _on_tx_started(self, message: str, tx_even: bool, slot_start_ts: float):
    ant_label = ""  # bleibt wie heute (P15: ant_label-Logic raus aus TX)
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

### 4e. `ui/main_window.py` — Statusbar (Variable-Rename)

`_on_omni_cq_count_changed` Signatur unveraendert `(int, bool)` —
intern `count` → `remaining` umbenennen, `_omni_cq_count` Attribut
auf `_omni_cq_remaining` umbenennen, `_update_statusbar` Format
auf `Ω CQ={remaining} ({parity_str})` halten.

```python
def _on_omni_cq_count_changed(self, remaining: int, tx_even: bool):
    """P23: Statusbar zeigt Down-Counter (war: count Up-Counter)."""
    self._omni_cq_remaining = remaining
    self._omni_cq_tx_even = tx_even
    self._update_statusbar()
```

`_update_statusbar` Helper anpassen wo `_omni_cq_count` gelesen wird.

## 5. Files & Tests-Migration

### 5.1 Files

| Datei | Aenderung |
|---|---|
| `core/omni_cq.py` | Counter-Refactor (down + auto-flip + reset_after_measure). `_OMNI_FLIP_AFTER_SEARCHES` + `on_search_trigger` weg. `_OMNI_TARGETS` neu. `cq_count` Property → `cq_remaining` + `cq_target`. |
| `ui/mw_cycle.py` | Hook-Umbau: search-trigger raus, mess-reset rein. |
| `ui/qso_panel.py` | `add_tx` Parameter `omni_remaining` + Suffix-Logik. |
| `ui/mw_qso.py` | `_on_tx_started` liest `omni.cq_remaining`. |
| `ui/main_window.py` | `_on_omni_cq_count_changed` Variable-Rename + Statusbar-Helper-Update. |
| `tests/test_omni_cq_signal.py` | Migration siehe §5.2 |
| `tests/test_p23_omni_counter.py` | NEU: T1-T16 (siehe §6) |
| `main.py` | APP_VERSION 0.96.6 → 0.96.7 |
| `HISTORY.md` + `HANDOFF.md` + `CLAUDE.md` + Memory | Updates. |

### 5.2 Tests-Migration `test_omni_cq_signal.py` (R1-K1-Fix)

| Test (alt) | Action | Begruendung |
|---|---|---|
| `test_start_initializes_state` | BLEIBT | nutzt `cq_tx_even`, `cq_audio_hz` — nicht `cq_count` |
| `test_start_idempotent` | BLEIBT | testet nur start() doppelt |
| `test_first_call_uses_fresh_is_even_param` | BLEIBT | testet `cq_tx_even`-Init |
| `test_matching_cycle_calls_encoder_transmit_and_emits` (T3) | **ANPASSEN** | `cq_count == 1` → `cq_remaining == cq_target - 1`. Lambda bleibt `(c, e)`. captured_count[0] vergleichen mit `(target-1, True)` |
| `test_non_matching_cycle_skips_encoder` (T4) | **ANPASSEN** | `cq_count == 0` → `cq_remaining == cq_target` (kein TX → Counter unveraendert) |
| `test_skips_during_diversity_measure_phase` (T5) | BLEIBT | testet phase-skip, nicht Counter |
| `test_flip_tx_parity_toggles_and_emits` (T6) | BLEIBT | testet flip + parity_flipped |
| `test_flip_tx_parity_noop_when_uninitialized` (T7) | BLEIBT | testet flip-noop |
| `test_flip_tx_parity_noop_when_inactive` (T7b) | BLEIBT | testet flip-noop |
| `test_on_search_trigger_counts_and_flips_at_threshold` (T8) | **LOESCHEN** | on_search_trigger entfaellt komplett |
| `test_on_search_trigger_inactive_noop` (T8b) | **LOESCHEN** | on_search_trigger entfaellt |
| `test_pause_resume_preserves_parity` (T10) | **ANPASSEN** | `omni._cq_count = 5` → setze `_cq_remaining = 5`. assert `cq_remaining == cq_target` nach resume (Reset auf TARGET, NICHT 5 wie vorher) |
| `test_frequency_sticky_across_flip` (T11) | BLEIBT | testet _cq_audio_hz sticky |
| `test_on_search_trigger_during_pause_noop` (T14) | **LOESCHEN** | on_search_trigger entfaellt |
| Import `_OMNI_FLIP_AFTER_SEARCHES` | **ENTFERNEN** | Konstante weg |

Resultat: 3 LOESCHEN, 3 ANPASSEN, Rest BLEIBT.

## 6. Tests V3 (NEU in `tests/test_p23_omni_counter.py`)

| # | Name | Was geprueft |
|---|---|---|
| T1 | `test_start_initializes_remaining_to_target_for_ft8` | start() FT8: _cq_remaining == 10 |
| T2 | `test_start_target_for_ft4` | start() FT4: _cq_remaining == 20 |
| T3 | `test_start_target_for_ft2` | start() FT2: _cq_remaining == 40 |
| T4 | `test_start_target_default_for_unknown_mode` | start() unbekannt: _cq_remaining == 10 |
| T5 | `test_tx_decrements_remaining_by_one` | nach 1 erfolgreichem TX: remaining == TARGET-1 + GENAU 1 cq_count_changed-Emit |
| T6 | `test_tx_busy_does_not_decrement` | encoder.transmit returnt False → remaining unveraendert + KEIN Emit |
| T7 | `test_remaining_reaches_zero_triggers_flip_and_reset_with_one_emit` | TARGET TXs: nach letztem `len(captured) == TARGET` (genau 1 emit pro Slot, nicht 2 fuer den letzten). Letzter Wert == TARGET (nicht 0). parity_flipped ==1 mal. (R1-S1) |
| T8 | `test_resume_after_qso_resets_remaining` | pause + dekrementieren auf TARGET-3 + resume_after_qso → remaining == TARGET + emit |
| T9 | `test_reset_counter_after_measure_resets_remaining` | start + setze remaining=5 + reset_counter_after_measure → remaining == TARGET + emit |
| T10 | `test_reset_counter_after_measure_noop_when_inactive` | not active → no-op (kein emit) |
| T11 | `test_reset_counter_after_measure_noop_when_paused` | paused → no-op |
| T12 | `test_reset_counter_after_measure_noop_when_already_target` | remaining == target → no-op (kein emit) |
| T13 | `test_pause_does_not_reset_remaining` | start + dekrementieren + pause() → remaining unveraendert |
| T14 | `test_stop_resets_remaining_to_zero_and_target_to_default` | stop() → remaining == 0, target == 10 |
| T15 | `test_on_search_trigger_method_removed` | `not hasattr(omni, 'on_search_trigger')` (R1: T17 entfaellt — ehemals doppelter Coverage-Check) |
| T16 | `test_qso_panel_add_tx_with_omni_remaining_renders_suffix` | qso_panel.add_tx mit omni_remaining=7 → output enthaelt `↻7` |

**Zu R1-S2:** T17 (`mw_cycle ruft NICHT on_search_trigger`) wurde
gestrichen weil redundant zu T15 — wenn die Methode garnicht existiert,
kann mw_cycle sie nicht aufrufen.

## 7. Field-Test-Plan (5 Punkte)

**F1.** App-Start, OMNI in FT8. Statusbar zeigt `Ω CQ=10 (E)` oder `(O)`.
TX-Zeile in qso_panel: `13:30:45 [E] →  Sende   CQ DA1MHH JO31  ↻10`

**F2.** 5 Min beobachten (10 TXs in FT8). Counter laeuft 10 → 9 → ... → 1.
Nach dem 10. TX: Paritaets-Wechsel (Log: „Paritaets-Wechsel auf Odd")
+ Statusbar `Ω CQ=10 (O)` + naechste TX-Zeile `↻10` in anderer Paritaet.

**F3.** Modus-Wechsel zu FT4: OMNI **stoppt** (heutiges Verhalten),
Statusbar leer. OMNI manuell wieder an: Statusbar `Ω CQ=20`.

**F4.** QSO eingehend (Antwort kommt). OMNI pausiert, QSO laeuft. Nach
QSO: OMNI resumed, Counter zurueck auf TARGET, naechste TX-Zeile `↻10`.

**F5.** Antennen-Mess startet (~1h Frist abgelaufen, oder via
KALIBRIEREN-Button). OMNI sendet nicht waehrend Mess (existing
V2-L12-Schutz). Nach Mess (~90s): Counter zurueck auf TARGET, OMNI
sendet wieder.

**Bestanden wenn:** F1-F4 sauber. F5 muss in echter Mess beobachtet
werden — Mess kommt eh alle ~1h.

## 8. Atomare Commits geplant

- **C1** `core/omni_cq.py` Counter-Refactor (search_trigger raus, target +
  reset + auto-flip-mit-1-emit + signal bleibt 2-arg)
- **C2** `tests/test_omni_cq_signal.py` Migration (3 LOESCHEN, 3
  ANPASSEN, Rest BLEIBT)
- **C3** `ui/mw_cycle.py` Hook-Umbau (search-trigger raus, mess-reset rein)
- **C4** `ui/qso_panel.py` add_tx Parameter `omni_remaining` + Suffix-Logik
- **C5** `ui/mw_qso.py` `_on_tx_started` Counter-Read
- **C6** `ui/main_window.py` Variable-Rename (`_omni_cq_count` →
  `_omni_cq_remaining`) + Statusbar-Format-Update
- **C7** `tests/test_p23_omni_counter.py` NEU T1-T16
- **C8** `main.py` APP_VERSION 0.96.6 → 0.96.7 + HISTORY/HANDOFF/CLAUDE/Memory

## 9. Was V3 NICHT macht

- KEIN Refactor des Diversity-Mess-Algorithmus.
- KEIN Refactor des Encoders.
- KEINE neue UI-Komponente — nur Suffix in TX-Zeile + Statusbar-Wert.
- KEIN Auto-Resume bei Bandwechsel/Modus-Wechsel — Stop bleibt Stop.
- KEIN Refactor der bestehenden mw_cycle Phase-Uebergang-Logik (nur 1
  zusaetzliche Zeile fuer reset_counter_after_measure).

## 10. Aufwand

V3 schaetzt: ~2h Code + 30 Min Tests + 30 Min Doku + Final-R1 + Field-Test.
