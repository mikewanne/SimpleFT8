# P23.OMNI-COUNTER-EIGEN — V1 (initialer Entwurf)

## 1. Ziel

OMNI-CQ-Paritaets-Wechsel von **Diversity-Such-Counter-Coupling** (heute)
auf **eigenen Sende-Counter** umstellen. Counter im Display sichtbar
(`↻10` Suffix), zaehlt DOWN nach jedem TX, bei 0 wird Paritaet getoggelt
und Counter resettet.

Mike-Spec 10.05.2026:
- Counter pro Modus: **FT8=10, FT4=20, FT2=40** (alle ~5 Min Wallclock)
- QSO eingehend → Counter zurueck auf TARGET (Slot scheint gut)
- Antennen-Mess + Verstaerker-Mess → Counter zurueck auf TARGET
- Bandwechsel + Modus-Wechsel → OMNI **STOPP** (wie heute)
- Display-Format: `13:30:45 [O] →  Sende   CQ DA1MHH JO31  ↻10`

## 2. Wurzel-Bedingung im Code

Heute (v0.96.4 P7.OMNI-SIMPLIFY):
- `core/omni_cq.py:35` `_OMNI_FLIP_AFTER_SEARCHES = 10` Konstante
- `_search_trigger_count` zaehlt **Such-Trigger vom Diversity-System**
- `on_search_trigger()` (Z. 195) wird aus `mw_cycle.py:166` gerufen wenn
  `_diversity_ctrl.tick_slot()` True returnt (alle 60s)
- Bei `_search_trigger_count >= 10` → `flip_tx_parity()` + Counter-Reset

**Schwaeche:** OMNI haengt an Diversity-Mess-Mechanik. Wenn Mess haengt,
kein Such-Trigger, kein Paritaets-Wechsel. Wenn jemand am Diversity-
Such-Counter dreht, kippt OMNI aus dem Takt.

## 3. Akzeptanzkriterien

A1. **Counter pro Modus:** Konstante `_OMNI_TARGETS = {"FT8": 10, "FT4": 20,
    "FT2": 40}`. Counter wird beim Start auf `_target_for_mode(mode)` gesetzt.

A2. **Down-Count nach TX:** Nach jedem erfolgreichen `encoder.transmit`
    `_cq_remaining -= 1`. Emit `cq_count_changed(remaining, target,
    current_tx_even)`.

A3. **Auto-Flip bei 0:** Wenn `_cq_remaining == 0` nach Dekrement →
    `flip_tx_parity()` + Counter-Reset auf TARGET.

A4. **QSO-Reset:** `resume_after_qso()` setzt `_cq_remaining = TARGET`
    (positiv-Verstaerkung „guter Slot, weiter so").

A5. **Mess-Reset:** Wenn Phase wechselt von `measure` → `operate`
    (Antennenmess fertig), Counter resettet auf TARGET.

A6. **Bandwechsel/Modus-Wechsel:** OMNI **stop** (wie heute, kein Aenderung).

A7. **Such-Counter-Coupling weg:** `on_search_trigger()` entfaellt komplett.
    `_search_trigger_count` Feld weg. `_OMNI_FLIP_AFTER_SEARCHES` Konstante
    weg. `mw_cycle.py:166` `_omni_cq.on_search_trigger()` Hook weg.

A8. **Display-Suffix:** `qso_panel.add_tx` bekommt optional
    `omni_remaining: int | None = None`. Wenn != None: Suffix
    `  ↻{remaining}` an Zeile anhaengen (in der Akzent-Farbe).

A9. **Diversity unangetastet:** Mess-Algorithmus, Such-Counter selbst,
    Threshold, Median, Antennen-Switch — bleiben 1:1.

A10. **Encoder-Pfad unangetastet:** `transmit(message, tx_even, audio_freq_hz)`
     bleibt wie heute.

A11. **Pause-Verhalten:** Bei `pause()` bleibt `_cq_remaining` unveraendert
     (nur Resume macht Reset). Bei `is_paused == True` wird kein TX
     ausgefuehrt → Counter dekrementiert nicht.

A12. **Statusbar-Format:** Existing Statusbar-Format
     `Ω CQ={remaining} ({parity_str})` bleibt — `cq_count_changed` Signal
     liefert jetzt remaining statt count.

## 4. Loesungs-Skizze

### 4a. `core/omni_cq.py` — Counter-Logik umstellen

```python
# NEU: Konstanten
_OMNI_TARGETS = {"FT8": 10, "FT4": 20, "FT2": 40}
_OMNI_DEFAULT_TARGET = 10  # Fallback fuer unbekannte Modi

# WEG: _OMNI_FLIP_AFTER_SEARCHES = 10

class OmniCQ(QObject):
    # Signals: cq_count_changed jetzt (remaining, target, tx_even)
    cq_count_changed = Signal(int, int, bool)
    # parity_flipped (bool) bleibt

    def __init__(self, encoder, diversity_ctrl, timer,
                 my_call: str, my_grid: str):
        ...
        self._cq_remaining = 0
        self._cq_target = _OMNI_DEFAULT_TARGET
        # WEG: self._search_trigger_count

    def _get_target(self) -> int:
        """Counter-Target aus aktuellem Timer-Modus ableiten."""
        mode = getattr(self._timer, 'mode', 'FT8')
        return _OMNI_TARGETS.get(mode, _OMNI_DEFAULT_TARGET)

    def start(self):
        ...
        self._cq_target = self._get_target()
        self._cq_remaining = self._cq_target

    def stop(self, reason):
        ...
        self._cq_remaining = 0
        self._cq_target = _OMNI_DEFAULT_TARGET

    def resume_after_qso(self, last_was_even=None):
        ...
        # P23: QSO-Reset = neuer Slot startet bei TARGET
        self._cq_target = self._get_target()
        self._cq_remaining = self._cq_target
        self.cq_count_changed.emit(
            self._cq_remaining, self._cq_target, self._cq_tx_even or False
        )

    def reset_counter_after_measure(self):
        """P23-A5: nach Antennen-Mess Counter zurueck auf TARGET.
        Wird aus mw_cycle bei Phase-Uebergang measure->operate gerufen."""
        if not self._active or self._paused:
            return
        self._cq_target = self._get_target()
        self._cq_remaining = self._cq_target
        self.cq_count_changed.emit(
            self._cq_remaining, self._cq_target,
            self._cq_tx_even if self._cq_tx_even is not None else False,
        )

    @Slot(int, bool)
    def on_cycle_start(self, cycle_num, is_even):
        ...  # bestehende Logik bis zum encoder.transmit

        ok = self._encoder.transmit(...)
        if ok:
            self._cq_remaining = max(0, self._cq_remaining - 1)
            self.cq_count_changed.emit(
                self._cq_remaining, self._cq_target, self._cq_tx_even
            )
            label = self._slot_label(True, self._cq_tx_even)
            self.slot_action.emit(label, True, self._cq_tx_even)
            # P23-A3: Auto-Flip bei 0
            if self._cq_remaining == 0:
                self.flip_tx_parity()
                self._cq_target = self._get_target()
                self._cq_remaining = self._cq_target
                self.cq_count_changed.emit(
                    self._cq_remaining, self._cq_target, self._cq_tx_even
                )
        else:
            ...  # bestehende busy-Behandlung

    # WEG: def on_search_trigger(self) -> None:
```

### 4b. `ui/mw_cycle.py` — Hook-Umbau

**WEG (Z. 163-166):**
```python
# inkrementieren. Bei _OMNI_FLIP_AFTER_SEARCHES (=10)
# Triggern -> flip_tx_parity (alle ~10 Min Wechsel).
if hasattr(self, '_omni_cq') and self._omni_cq:
    self._omni_cq.on_search_trigger()
```

**NEU (im phase=operate-Uebergang in `_handle_diversity_measure`,
ca. Z. 259+):**
```python
# P23-A5: nach Antennen-Mess Counter im OMNI auf TARGET resetten
if hasattr(self, '_omni_cq') and self._omni_cq:
    self._omni_cq.reset_counter_after_measure()
```

### 4c. `ui/qso_panel.py:add_tx` — Suffix

```python
def add_tx(self, message: str, ant_label: str = "",
           tx_even: bool | None = None,
           slot_start_ts: float | None = None,
           omni_remaining: int | None = None):
    """... (bestehender Doc)
    omni_remaining: P23 — wenn nicht None: Suffix `  ↻{n}` anhaengen
    (Counter wieviele OMNI-CQs noch in dieser Paritaet)."""
    ...
    line = f"{utc} {tag} →  Sende   {message}"
    if omni_remaining is not None:
        line = f"{line}  ↻{omni_remaining}"
    if ant_label:
        self._append_two_color(line, "#FFAA00", f"   {ant_label}", "#888888")
    else:
        self._append_colored(line, "#FFAA00")
```

### 4d. `ui/mw_qso.py:_on_tx_started` — Counter holen

```python
def _on_tx_started(self, message: str, tx_even: bool, slot_start_ts: float):
    ...
    omni_remaining = None
    omni = getattr(self, '_omni_cq', None)
    if omni is not None and omni.is_active() and not omni.is_paused():
        # P23: Counter im TX-Display anzeigen wenn OMNI-CQ
        omni_remaining = omni.cq_remaining
    self.qso_panel.add_tx(
        message, ant_label,
        tx_even=tx_even, slot_start_ts=slot_start_ts,
        omni_remaining=omni_remaining,
    )
```

### 4e. `ui/main_window.py:_on_omni_cq_count_changed` — Signal-Format

```python
def _on_omni_cq_count_changed(self, remaining: int, target: int, tx_even: bool):
    """P23: Statusbar zeigt Down-Counter."""
    self._omni_cq_remaining = remaining
    self._omni_cq_target = target
    self._omni_cq_tx_even = tx_even
    self._update_statusbar()
```

`_update_statusbar` zeigt `Ω CQ={remaining}/{target} ({parity_str})` —
oder einfacher `Ω CQ={remaining} ({parity_str})` wenn target redundant
wirkt (Mike-Vorschlag: zaehlt sichtbar runter, target im Hint).

## 5. Tests

| # | Name | Was geprueft |
|---|---|---|
| T1 | `test_start_initializes_remaining_to_target_for_mode` | start() im FT8: _cq_remaining == 10 |
| T2 | `test_start_target_for_ft4` | start() im FT4: _cq_remaining == 20 |
| T3 | `test_start_target_for_ft2` | start() im FT2: _cq_remaining == 40 |
| T4 | `test_tx_decrements_remaining` | nach 1 erfolgreichem TX: remaining == TARGET-1 |
| T5 | `test_tx_busy_does_not_decrement` | encoder.transmit returnt False → remaining unveraendert |
| T6 | `test_remaining_reaches_zero_triggers_flip` | TARGET TXs: nach letztem Auto-Flip + Reset auf TARGET |
| T7 | `test_resume_after_qso_resets_remaining` | pause + resume_after_qso → remaining == TARGET |
| T8 | `test_reset_counter_after_measure_resets_remaining` | reset_counter_after_measure → remaining == TARGET |
| T9 | `test_reset_counter_after_measure_noop_when_inactive` | not active → no-op |
| T10 | `test_pause_does_not_reset_remaining` | pause() → remaining unveraendert |
| T11 | `test_stop_resets_remaining_to_zero` | stop() → remaining == 0, target == default |
| T12 | `test_on_search_trigger_method_removed` | hasattr(omni, 'on_search_trigger') == False |
| T13 | `test_cq_count_changed_signal_format_remaining_target_even` | emit (remaining, target, tx_even) — 3 Args |
| T14 | `test_qso_panel_add_tx_with_omni_remaining_suffix` | qso_panel-Whitebox: Suffix ↻N im Output |
| T15 | `test_mw_cycle_no_more_on_search_trigger_call` | mw_cycle._refresh_diversity_freq_view ruft NICHT mehr on_search_trigger |
| T16 | `test_mw_cycle_calls_reset_counter_on_phase_operate` | mw_cycle Phase-Uebergang ruft `reset_counter_after_measure` |

## 6. Files & Aenderungen

| Datei | Aenderung |
|---|---|
| `core/omni_cq.py` | `_cq_count` → `_cq_remaining`. `_search_trigger_count` weg. `_cq_target` neu. `_OMNI_TARGETS` Konstante. `_get_target` Helper. `reset_counter_after_measure` Methode. `on_search_trigger` raus. `cq_count_changed` Signal-Format `(int, int, bool)`. Auto-Flip-Logik in `on_cycle_start`. |
| `ui/mw_cycle.py` | Z. 163-166 `_omni_cq.on_search_trigger()` Hook RAUS. Z. ~259+ Phase-Uebergang `_omni_cq.reset_counter_after_measure()` NEU. |
| `ui/qso_panel.py` | `add_tx` Parameter `omni_remaining: int \| None = None` + Suffix-Logik. |
| `ui/mw_qso.py` | `_on_tx_started` liest `omni.cq_remaining` wenn aktiv + uebergibt. |
| `ui/main_window.py` | `_on_omni_cq_count_changed` Signatur `(remaining, target, tx_even)`. Statusbar-Update. |
| `tests/test_omni_cq_signal.py` | Bestehende Tests anpassen — Signal-Format-Aenderung, on_search_trigger-Tests entfernen oder umfunktionieren. |
| `tests/test_p23_omni_counter.py` | NEU: T1-T16 Counter-Logik + Display + Hook-Refactor. |
| `main.py` | APP_VERSION 0.96.6 → 0.96.7 |
| `HISTORY.md` + `HANDOFF.md` + `CLAUDE.md` + Memory | Updates. |

## 7. Was V1 NICHT macht

- KEIN Refactor des Diversity-Mess-Algorithmus.
- KEIN Refactor des Encoders.
- KEIN Aenderung am UI ausser Suffix in TX-Zeile + Statusbar-Werte.
- KEIN Auto-Resume bei Bandwechsel/Modus-Wechsel — Stop bleibt Stop.

## 8. Offene Fragen / Klaerungs-Bedarf

Q1. **Display-Suffix-Position:** Vor oder nach dem `ant_label`?
    - Variante A: `13:30:45 [O] →  Sende   CQ DA1MHH JO31  ↻10`
    - Variante B: `13:30:45 [O] →  Sende   CQ DA1MHH JO31   (ANT2)  ↻10`
    - Variante C: `13:30:45 [O] →  Sende   CQ DA1MHH JO31  ↻10   (ANT2)`
    V1-Vorschlag: **Variante C** (Counter direkt nach Message, ant_label
    hinten in seiner gewohnten Position).

Q2. **Statusbar-Format:** `Ω CQ={remaining}` (nur Restzahl) ODER
    `Ω CQ={remaining}/{target}` (Bruchanzeige)?
    V1-Vorschlag: **`Ω CQ={remaining}`** (KISS, Mike sagt nur "10 9 usw").

Q3. **Mess-Reset auch bei Adaptiv-Stop?** Mess kann via Adaptiv-Stop frueh
    enden (`_was_early_stopped == True`). Soll der Counter-Reset trotzdem
    laufen (Phase-Uebergang findet auch bei Adaptiv-Stop statt)?
    V1-Vorschlag: **Ja, immer bei measure→operate** (KISS, kein Sonderfall).

Q4. **Wenn kein gueltiger Modus im Timer (z.B. WSPR-Plug-in?):** Fallback
    auf `_OMNI_DEFAULT_TARGET = 10`. Akzeptabel?

## 9. Aufwand

V1 schaetzt: ~3h V1→V2→R1→V3+Code+16 Tests + 30 Min Doku.

## 10. Atomare Commits geplant

- C1 `core/omni_cq.py` Counter-Refactor (stage_gain-aehnlich, breaking change tests)
- C2 `tests/test_omni_cq_signal.py` Anpassungen
- C3 `ui/mw_cycle.py` Hook-Umbau (search_trigger raus, mess-reset rein)
- C4 `ui/qso_panel.py` add_tx Suffix
- C5 `ui/mw_qso.py` _on_tx_started Counter-Read
- C6 `ui/main_window.py` Signal-Format + Statusbar
- C7 `tests/test_p23_omni_counter.py` NEU T1-T16
- C8 `main.py` APP_VERSION + HISTORY/HANDOFF/CLAUDE/Memory
