# P7.OMNI-SIMPLIFY — V3 (Compact-fest, Mike-freigabe-bereit)

**Datum:** 2026-05-10 ~11:15 UTC
**Vorgaenger:** P6.OMNI-DOUBLE-AUDIO (v0.96.3, gescheitert wegen Diversity-Block)
**Plan-Files:** `p7_omni_simplify_v1.md`, `p7_omni_simplify_v2.md`
**Status:** V3 fertig, wartet auf R1-Review + Mike-Freigabe

---

## R1-Status (10.05.2026 ~11:30 UTC)

**R1 (DeepSeek-Reasoner, in=70096 out=7730 Tokens):** „V3 freigegeben für Code".
- 0 KRITISCH
- 3 SOLLTE-FIX **bereits in V3 §4.2 + §7 eingearbeitet:**
  - SF-1: `on_search_trigger()` prüft `_paused` (Defense-in-Depth) → §4.2 Code-Snippet aktualisiert
  - SF-2: Docstring `on_cycle_start` klärt `is_even`-Parameter wird ignoriert → §4.2 Docstring aktualisiert
  - SF-3: Test `test_on_search_trigger_during_pause` ergänzt → §7.4 als T14
- R1 verifiziert: Encoder-Rückrollung kompatibel, Hook-Stelle korrekt, Out-of-Scope eingehalten, Test-Plan deckt ACs ab, Race B4 (Phase-Wechsel mid-call) durch Qt-Slot-Order ausgeschlossen.

---

## 0. Compact-Hinweis fuer fresh-Instanz

Wenn du diesen Plan **nach einem Compact** liest:

1. **Schritt 0 erneut durchfuehren** — alle file:line-Verweise in §1 mit
   `Read`/`Grep` gegen aktuellen Code verifizieren. Code kann sich geaendert
   haben (Zeilen-Verschiebung, Refactor).
2. **Memory neu laden:**
   - `project_omni_cq_spec.md` — **VERALTET**, V3 §2 ueberschreibt sie
   - `feedback_omni_separate_architecture.md` (3-Schichten-Pflicht)
   - `feedback_test_critical_path_not_mock.md` (KEIN Worker/Sleep-Mock)
   - `feedback_compact_save_cold_start_test.md` (Cold-Start-Pflicht)
   - `feedback_workflow_no_exceptions.md` (Workflow-Pflicht)
3. **R1-Output checken:** `prompts/p7_omni_simplify_r1.md` (falls schon gelaufen)
4. **App-Status:** v0.96.3 lokal commited (last commit `1ec7501`). KEIN Push
   seit v0.95.16. App muss gestoppt sein vor Code-Phase.
5. **Tests-Stand:** **1034 gruen** (verifiziert). Nach P7: **~990 gruen**
   erwartet (-40 Pattern-Tests, -8 Pending-Tests, +10 simplified Tests, netto -38).

---

## 1. Schritt 0 — Code-Verifikation (Stand 10.05.2026 ~11:00)

| File:Line | Symbol | Aktion in P7 |
|---|---|---|
| `core/encoder.py:85` | `_pending_tx`, `_pending_queued_at` (P5) | **WEG** |
| `core/encoder.py:187-247` | `transmit()` mit Pending-Branch | **rueckrollen** auf vor v0.96.2 (return False bei busy, kein Pending) |
| `core/encoder.py:249-290` | `_tx_worker` mit Pending-Loop | **rueckrollen** auf single-pass |
| `core/encoder.py:292-447` | `transmit_pair`, `_tx_pair_worker`, `_tx_pair_inner` (P6) | **WEG** |
| `core/encoder.py:449-490` | `_run_one_tx_pass`, `_compute_target_slot` (P5) | **WEG** |
| `core/omni_cq.py:60` | `_TX_PATTERN = (T,T,F,F,F)` | **WEG** |
| `core/omni_cq.py:74-79` | `_slot_index`, `_block`, counters | **vereinfacht** (siehe §4.2) |
| `core/omni_cq.py:82,101,119,245,249,257` | `_pair_in_progress` (P6) | **WEG** |
| `core/omni_cq.py:170-273` | `on_cycle_start`, `_next_slot_action`, `_do_tx_slot`, `_do_rx_slot`, `_advance_state`, `_slot_label` | **REWRITE** (single-slot mit Such-Counter) |
| `core/omni_cq.py:57` | `counter_changed = Signal(int, int)` | **AENDERN** auf `cq_count_changed = Signal(int, bool)` |
| `core/omni_cq.py:160-165` | `cq_even_count`, `cq_odd_count` Properties | **WEG**, ersetzt durch `cq_count` + `cq_tx_even` |
| `core/diversity.py:478-497` | `should_remeasure()` | **NICHT anfassen** (Mike: Diversity unantastbar) |
| `core/diversity.py:499` | `start_measure()` | **NICHT anfassen** |
| `core/diversity.py:310-316` | `tick_slot()` returnt True bei Such-Trigger | **NICHT anfassen** (P7-Hook hier dran) |
| `ui/mw_cycle.py:139-163` | `_refresh_diversity_freq_view` mit `tick_slot()` Z.160 | **HOOK NEU:** wenn `tick_slot()` True → `omni_cq.on_search_trigger()` |
| `ui/mw_cycle.py:619-620` | `should_remeasure()` + `start_measure()` | **NICHT anfassen** (existing Pfad) |
| `ui/main_window.py:264` | `omni_cq.counter_changed.connect(_on_omni_counter_changed)` | **AENDERN** auf neues Signal `cq_count_changed` |
| `ui/main_window.py:747-749` | `_on_omni_counter_changed(even, odd)` Handler | **AENDERN** auf `(count, tx_even)` |
| `ui/main_window.py:752-770` | `_on_omni_slot_action` | **VEREINFACHEN** (kein RX-Branch mehr — single-slot OMNI emit nur bei TX) |
| `ui/main_window.py:996-997` | `omni_str = "Ω Even=X Odd=Y"` | **AENDERN** auf `f"Ω CQ={cq_count} ({'E' if cq_tx_even else 'O'})"` |
| `core/omni_cq.py:133-151` | `resume_after_qso(last_was_even)` | **Signatur kompatibel halten**, last_was_even ignorieren (V2-L3) |

**App-Status:** Tests **1034 gruen** (v0.96.3, last commit `1ec7501`).
KEIN Push (origin) seit v0.95.16. App muss vor Code gestoppt sein.

---

## 2. Neue Spec (Mike-Freigabe 10.05.2026 ~11:00)

### 2.1 Kernkonzept

OMNI ist ein **Single-Slot-CQ-Modus** mit **Such-Counter-getriggertem Paritaets-Wechsel**.

```
OMNI-Toggle  →  CQ alle 30s in Slot-Paritaet P (Even ODER Odd)
                P = aktuelle Slot-Paritaet beim ersten cycle_start
                
~10 Min Even (~20 CQ-Rufe in Even-Slots)
   |
   v
Such-Counter erreicht 10 (10x Such-Trigger × 60s = 10 Min)
   →  flip_tx_parity() (P toggelt zu Odd)
   |
   v
~10 Min Odd
   |
   v
... permanent alternierend
```

### 2.2 Trigger fuer Paritaets-Wechsel

**Quelle:** `core/diversity.py:tick_slot()` returnt True bei jedem **Such-Trigger** (`_search_slots_remaining` erreicht 0).

**Counter:** `core/omni_cq.py:_search_trigger_count` zaehlt jeden Such-Trigger. Bei `>= _OMNI_FLIP_AFTER_SEARCHES` → `flip_tx_parity()` + Counter-Reset.

**Default:** `_OMNI_FLIP_AFTER_SEARCHES = 10` (~10 Min Wechsel bei FT8 60s/Such).

**QSO-Pause:** existing `mw_cycle._refresh_diversity_freq_view` Z.158
`reset_search_counter()` bei QSO. → OMNI-Counter friert intern, weil
`tick_slot()` nicht mehr True returnt waehrend QSO. ✓

### 2.3 Mess-Phase-Verhalten (Mike-Klaerung)

**Re-Mess startet (Phase wechselt von "operate" zu "measure"):**
- 90s Antennen-Vergleich-Mess (existing Diversity-Logik)
- OMNI sendet **NICHT** waehrend Mess-Phase (Mike-Spec)
- Implementation: `on_cycle_start` no-op wenn `_diversity.phase != "operate"`

**Status-Dialog:** geplant fuer **P8.MESS-STATUS-DIALOG** (separater Workflow nach P7).

### 2.4 Was wegfaellt vom alten OMNI

- ❌ 5-Slot-Pattern (TX-TX-RX-RX-RX)
- ❌ Block 1 / Block 2 mit gespiegelten Paritaeten
- ❌ Auto-Block-Rollover nach 5 Slots
- ❌ Toggle-Start IMMER Block 1 (jetzt: Toggle-Start nimmt aktuellen Slot)
- ❌ counter_changed (Even+Odd separat) → 1 Counter
- ❌ Encoder-Pending-Queue (P5)
- ❌ Pair-Audio (P6)
- ❌ resume_after_qso Block-Wahl (jetzt: nur _paused=False, _cq_tx_even bleibt)

### 2.5 Was erhalten bleibt

- ✅ Frequenz-Sticky (1× gesetzt, dann fest, AUCH ueber Paritaets-Wechsel)
- ✅ Diversity-only (Mode-gekoppelt, btn_omni_cq nur in Diversity)
- ✅ Pause/Resume bei eingehender Antwort
- ✅ Stop-Bedingungen: manual_halt, band_change, mode_change, totmann_expired
- ✅ Hardware-Pflicht ANT1 (encoder.transmit setzt zentral)
- ✅ Easter-Egg-Toggle ueber Versionsnummer (UI bleibt)
- ✅ on_cycle_start-API-Signatur (`cycle_num: int, is_even: bool`)

---

## 3. Wurzel — warum P5+P6 nicht passten

**P5 (Pending-Queue):** Verfall-Schwelle `1.5 * cycle_duration = 22.5s` zu klein.
Real-Diff: 29.8s → Verfall → Pos 1 nie gesendet → Pattern halb tot.

**P6 (Pair-Audio):** 27.6s durchgehend `_is_transmitting=True`.
`mw_cycle.py:595` TX-Schutz skipped Diversity-Antennen-Switching 28s lang.
**Mike-Beobachtung:** „Diversity nur noch eine Antenne".

**Beide Loesungen verbiegen Encoder/Diversity um TX-TX-konsekutiv-Pattern zu retten.
Mike-Idee P7:** Pattern aendern statt Encoder/Diversity verbiegen.

---

## 4. Loesung — Code-Diff

### 4.1 `core/encoder.py` — P5+P6 zurueckrollen

#### 4.1.1 `__init__` — Pending-State weg

```python
# WEG (Z. 84-86):
# self._pending_tx: tuple[str, bool | None, int | None] | None = None
# self._pending_queued_at: float = 0.0
```

#### 4.1.2 `transmit()` — Pending-Branch weg, return False bei busy (Z. 187-247 ersetzen)

```python
def transmit(self, message: str, *,
             tx_even: bool | None = None,
             audio_freq_hz: int | None = None) -> bool:
    """FT8-Nachricht encoden und zum naechsten Zyklusbeginn senden.

    Atomare API (P4.OMNI-NEUBAU C3): tx_even und audio_freq_hz werden
    UNTER Lock gesetzt, dann startet der Worker.

    Returns True wenn Worker gestartet, False wenn TX bereits laeuft.
    """
    if (self._tx_thread is not None
            and self._tx_thread.is_alive()
            and threading.current_thread() is not self._tx_thread):
        self._tx_thread.join(timeout=0.5)
    with self._replace_lock:
        if self._is_transmitting:
            return False
        if tx_even is not None:
            self.tx_even = tx_even
        if audio_freq_hz is not None:
            self.audio_freq_hz = audio_freq_hz
    self._tx_thread = threading.Thread(
        target=self._tx_worker, args=(message,), daemon=True
    )
    self._tx_thread.start()
    return True
```

#### 4.1.3 `_tx_worker()` — Single-pass (Z. 249-290 ersetzen)

```python
def _tx_worker(self, message: str):
    """TX-Worker: Single-Pass.

    Pre-P7-Stand (vor v0.96.2): kein Pending-Loop, kein Pair.
    """
    self._is_transmitting = True
    self._abort_event.clear()
    self._audio_started = False
    with self._replace_lock:
        self._replace_message = None
    try:
        self._tx_worker_inner(message)
    finally:
        self._is_transmitting = False
        self._audio_started = False
```

#### 4.1.4 ENTFERNEN

- `transmit_pair()` (Z. 292-324) — komplett weg
- `_tx_pair_worker()` (Z. 326-336) — komplett weg
- `_tx_pair_inner()` (Z. 338-447) — komplett weg
- `_run_one_tx_pass()` (Z. 449-467) — komplett weg
- `_compute_target_slot()` (Z. 469-490) — komplett weg

`_next_slot_boundary()` (Z. 491-522) bleibt — wird von `_tx_worker_inner` weiter genutzt.

---

### 4.2 `core/omni_cq.py` — radikale Vereinfachung

**Komplett neu** (alte Datei loeschen, neue schreiben):

```python
"""OMNI-CQ — Single-Slot-CQ-Modus mit Such-Counter-Paritaets-Wechsel.

P7.OMNI-SIMPLIFY (v0.96.4, 10.05.2026 Mike-Spec):
- Sendet CQ in EINER Slot-Paritaet (Even ODER Odd)
- Paritaet wird automatisch alle ~10 Min gewechselt (Such-Counter)
- Diversity-Re-Mess pausiert OMNI (kein TX waehrend Mess-Phase)
- Sticky Audio-Frequenz ueber Paritaets-Wechsel hinweg

Eigenstaendiges Modul (KEIN qso_state.cq_mode-Hack — Memory-Pflicht
feedback_omni_separate_architecture.md).

Lifecycle:
  start()                    -> _active=True, _cq_tx_even=None
  on_cycle_start(c, is_even) -> erster Aufruf: setzt _cq_tx_even=is_even +
                                _init_audio_freq, sendet im selben Slot
                                folgende Aufrufe: nur senden wenn is_even
                                matcht
  on_search_trigger()        -> Counter ++; bei >= 10 -> flip_tx_parity()
  flip_tx_parity()           -> _cq_tx_even toggle (True↔False)
  pause() / resume_after_qso(...) -> Lifecycle (Resume nimmt last_was_even
                                     fuer API-Kompat, ignoriert Wert)
  stop(reason)               -> Reset alles
"""
from __future__ import annotations

import logging
import time
from PySide6.QtCore import QObject, Signal, Slot

logger = logging.getLogger(__name__)


# Wechsel-Schwelle: nach N Such-Triggern flip Paritaet.
# FT8: 60s/Such × 10 = 10 Min Wechsel-Intervall.
_OMNI_FLIP_AFTER_SEARCHES = 10


class OmniCQ(QObject):
    """Single-Slot-CQ mit Such-Counter-Wechsel."""

    omni_started = Signal()
    omni_stopped = Signal(str)               # reason
    slot_action = Signal(str, bool, bool)    # label, is_tx, target_even
    cq_freq_changed = Signal(int)            # audio_hz
    cq_count_changed = Signal(int, bool)     # P7: (count, current_tx_even)
    parity_flipped = Signal(bool)            # P7 NEU: new_tx_even (UI/Log)

    _FALLBACK_AUDIO_HZ = 1500

    def __init__(self, encoder, diversity_ctrl, timer,
                 my_call: str, my_grid: str):
        super().__init__()
        self._encoder = encoder
        self._diversity = diversity_ctrl
        self._timer = timer  # API-Kompat (Tests/Init)
        self._my_call = my_call
        self._my_grid = my_grid

        self._active = False
        self._paused = False
        self._cq_audio_hz: int | None = None
        self._cq_tx_even: bool | None = None  # None bis erster on_cycle_start
        self._cq_count = 0
        self._search_trigger_count = 0

    # ── Public API ────────────────────────────────────────────────────

    def start(self) -> None:
        """OMNI starten — _cq_tx_even bleibt None bis erster on_cycle_start."""
        if self._active:
            return
        self._active = True
        self._paused = False
        self._cq_audio_hz = None
        self._cq_tx_even = None
        self._cq_count = 0
        self._search_trigger_count = 0
        self.omni_started.emit()
        logger.info("[OMNI-CQ] Start")

    def stop(self, reason: str) -> None:
        if not self._active:
            return
        self._active = False
        self._paused = False
        self._cq_audio_hz = None
        self._cq_tx_even = None
        self._cq_count = 0
        self._search_trigger_count = 0
        self.omni_stopped.emit(reason)
        logger.info("[OMNI-CQ] Stop (%s)", reason)

    def pause(self) -> None:
        if not self._active or self._paused:
            return
        self._paused = True
        logger.info("[OMNI-CQ] Pause (QSO laeuft)")

    def resume_after_qso(self, last_was_even: bool | None = None) -> None:
        """API-Kompat (Pos.-Param. ignoriert in P7).

        last_was_even-Block-Wahl entfaellt — _cq_tx_even bleibt unveraendert.
        """
        if not self._paused:
            logger.warning(
                "[OMNI-CQ] resume_after_qso ohne pause — ignoriert"
            )
            return
        self._paused = False
        logger.info("[OMNI-CQ] Resume (Paritaet bleibt %s)",
                    "E" if self._cq_tx_even else "O")

    def is_active(self) -> bool:
        return self._active

    def is_paused(self) -> bool:
        return self._paused

    @property
    def cq_count(self) -> int:
        return self._cq_count

    @property
    def cq_tx_even(self) -> bool | None:
        return self._cq_tx_even

    @property
    def cq_audio_hz(self) -> int | None:
        return self._cq_audio_hz

    # ── Cycle-Hook (vom mw_cycle._on_cycle_start) ────────────────────

    @Slot(int, bool)
    def on_cycle_start(self, cycle_num: int, is_even: bool) -> None:
        """Pro Slot 1× — entscheidet ob OMNI sendet.

        V2-L9 / R1-SF-2: cycle_num UND is_even Parameter werden IGNORIERT.
        Paritaet wird FRESH aus time.time() berechnet (Robustheit gegen
        Signal-Latenz, im P6-Field-Test 14s Latenz beobachtet → falsche
        Paritaet via signal). Parameter bleiben in der Signatur fuer
        Qt-Slot-Kompat (`@Slot(int, bool)` bindet an cycle_start signal).
        """
        if not self._active or self._paused:
            return

        # V2-L12: kein Senden waehrend Diversity-Mess-Phase
        if self._diversity.phase != "operate":
            return

        # V2-L9 Fresh-Compute is_even — robust gegen Signal-Latenz
        slot_dur = self._timer.cycle_duration
        fresh_is_even = (int(time.time() / slot_dur) % 2 == 0)

        # Erster Aufruf: Paritaet aus aktuellem Slot waehlen
        if self._cq_tx_even is None:
            self._cq_tx_even = fresh_is_even

        # Frequenz initialisieren wenn noch nicht (sticky)
        if self._cq_audio_hz is None:
            self._init_audio_freq()

        # Nur senden wenn aktueller Slot die richtige Paritaet hat
        if fresh_is_even != self._cq_tx_even:
            return

        cq_msg = f"CQ {self._my_call} {self._my_grid}"
        ok = self._encoder.transmit(
            cq_msg, tx_even=self._cq_tx_even,
            audio_freq_hz=self._cq_audio_hz,
        )
        if ok:
            self._cq_count += 1
            self.cq_count_changed.emit(self._cq_count, self._cq_tx_even)
            label = self._slot_label(True, self._cq_tx_even)
            self.slot_action.emit(label, True, self._cq_tx_even)
        else:
            label = self._slot_label(True, self._cq_tx_even)
            logger.warning(
                "[OMNI-CQ] encoder busy -> Slot %s uebersprungen", label
            )

    # ── Such-Counter-Hook (vom mw_cycle._refresh_diversity_freq_view) ─

    def on_search_trigger(self) -> None:
        """Diversity Such-Trigger gefeuert — Counter ++.

        Bei _OMNI_FLIP_AFTER_SEARCHES (=10) Triggern: flip_tx_parity().

        R1-SF-1 Defense-in-Depth: prueft auch _paused (existing mw_cycle
        TX-Schutz greift bereits, aber zukuenftige Hook-Aenderungen
        sollen den Counter nicht versehentlich waehrend QSO inkrementieren).
        """
        if not self._active or self._paused:
            return
        self._search_trigger_count += 1
        if self._search_trigger_count >= _OMNI_FLIP_AFTER_SEARCHES:
            self._search_trigger_count = 0
            self.flip_tx_parity()

    def flip_tx_parity(self) -> None:
        """Paritaets-Wechsel — toggle _cq_tx_even.

        Public fuer Tests + manueller Trigger (zukuenftig UI-Button?).
        """
        if not self._active:
            return
        if self._cq_tx_even is None:
            return  # noch nicht initialisiert -> kein flip
        self._cq_tx_even = not self._cq_tx_even
        self.parity_flipped.emit(self._cq_tx_even)
        logger.info("[OMNI-CQ] Paritaets-Wechsel auf %s",
                    "Even" if self._cq_tx_even else "Odd")

    # ── Internal ──────────────────────────────────────────────────────

    def _init_audio_freq(self) -> None:
        """Sticky-Frequenz beim ersten TX setzen. Fallback _FALLBACK_AUDIO_HZ."""
        freq = self._diversity.get_free_cq_freq()
        if freq is None:
            logger.warning(
                "[OMNI-CQ] get_free_cq_freq=None -> Fallback %d Hz",
                self._FALLBACK_AUDIO_HZ,
            )
            freq = self._FALLBACK_AUDIO_HZ
        self._cq_audio_hz = int(freq)
        self.cq_freq_changed.emit(self._cq_audio_hz)
        logger.info("[OMNI-CQ] CQ-Audiofrequenz: %d Hz", self._cq_audio_hz)

    def _slot_label(self, is_tx: bool, target_even: bool) -> str:
        parity = "E" if target_even else "O"
        kind = "TX" if is_tx else "RX"
        return f"{kind}-{parity}"
```

**Zeilen-Bilanz:** alt 305 Z. → neu ~210 Z. (-95 Z., -31%).

---

### 4.3 `ui/mw_cycle.py:160` — Such-Trigger-Hook

```python
# bestehend (Z. 155-163):
with self._diversity_lock:
    self._diversity_ctrl.sync_from_stations(self._diversity_stations)
    if qso_busy:
        self._diversity_ctrl.reset_search_counter()
    else:
        if self._diversity_ctrl.tick_slot():
            self._diversity_ctrl.update_proposed_freq(qso_active=False)
            # P7 NEU: OMNI-Counter ueber Such-Trigger inkrementieren
            if hasattr(self, '_omni_cq'):
                self._omni_cq.on_search_trigger()
self.control_panel.update_freq_histogram(
    self._diversity_ctrl.get_histogram_data())
```

**Anmerkung:** Hook NUR wenn Such-Trigger feuert (`tick_slot()` True),
NICHT bei jedem Aufruf von `_refresh_diversity_freq_view`. Damit ist der
Counter sauber pro 60s.

---

### 4.4 `ui/main_window.py` — Signal + UI

#### 4.4.1 `_on_omni_counter_changed` Signatur (Z. 264 + 747-749)

```python
# Z. 264:
self._omni_cq.cq_count_changed.connect(self._on_omni_cq_count_changed)
# (Optional: parity_flipped fuer UI-Notification)
self._omni_cq.parity_flipped.connect(self._on_omni_parity_flipped)

# Z. 747-749 ersetzen:
@Slot(int, bool)
def _on_omni_cq_count_changed(self, count: int, tx_even: bool):
    """OMNI: 1 Counter mit aktueller Paritaet."""
    # Statusbar-Update folgt automatisch durch _update_statusbar
    pass

@Slot(bool)
def _on_omni_parity_flipped(self, new_tx_even: bool):
    """OMNI: Paritaet wurde gewechselt — User-Notification."""
    parity_str = "Even" if new_tx_even else "Odd"
    print(f"[OMNI-CQ-UI] Paritaets-Wechsel auf {parity_str}")
```

#### 4.4.2 `_on_omni_slot_action` (Z. 752-770) — vereinfachen

```python
@Slot(str, bool, bool)
def _on_omni_slot_action(self, label: str, is_tx: bool, target_even: bool):
    """OMNI emittet slot_action NUR bei TX (kein RX-Branch mehr in P7).

    TX-Slot wird ueber encoder.tx_started → qso_panel.add_tx angezeigt
    (Sende-Eintrag). Hier ist nichts zu tun.
    """
    pass
```

#### 4.4.3 Statusbar-Display (Z. 996-997)

```python
# alt:
omni_str = (f"  Ω Even={self._omni_cq.cq_even_count} "
            f"Odd={self._omni_cq.cq_odd_count}")

# neu:
parity = self._omni_cq.cq_tx_even
parity_str = "E" if parity else "O" if parity is False else "?"
omni_str = f"  Ω CQ={self._omni_cq.cq_count} ({parity_str})"
```

---

## 5. Akzeptanzkriterien

| AC | Kriterium | Test |
|---|---|---|
| AC1 | OMNI-Start: _active=True, _cq_tx_even=None, _cq_count=0, _search_trigger_count=0 | T1 |
| AC2 | Erster on_cycle_start setzt _cq_tx_even = fresh_is_even (aus time.time()) | T2 |
| AC3 | on_cycle_start mit matching is_even ruft encoder.transmit + _cq_count++ + cq_count_changed.emit + slot_action.emit | T3 |
| AC4 | on_cycle_start mit non-matching is_even ruft KEINEN encoder | T4 |
| AC5 | on_cycle_start no-op wenn diversity.phase != "operate" (V2-L12) | T5 |
| AC6 | flip_tx_parity() toggelt _cq_tx_even, emit parity_flipped(new_value) | T6 |
| AC7 | flip_tx_parity() bei _cq_tx_even=None → no-op | T7 |
| AC8 | on_search_trigger() inkrementiert _search_trigger_count; bei >=10 flip + Reset | T8 |
| AC9 | mw_cycle._refresh_diversity_freq_view ruft _omni_cq.on_search_trigger() bei tick_slot()==True | T9 (Integration) |
| AC10 | Pause: _cq_tx_even bleibt; resume_after_qso(*): _cq_tx_even bleibt | T10 |
| AC11 | Frequenz-Sticky: _cq_audio_hz wird 1× gesetzt, bleibt ueber flip | T11 |
| AC12 | Stop: _active=False, alles zurueckgesetzt | T12 |
| AC13 | resume_after_qso() Signatur kompatibel: ohne und mit last_was_even-Param | T13 |
| AC14 | encoder.transmit Pending-Loop ist WEG | Code-Read + test_modules.py gruen |
| AC15 | encoder.transmit_pair etc. ist WEG | Code-Read |
| AC16 | mw_cycle:595 TX-Schutz greift normal (kein 28s-Pair-Block) | Field-Test |
| AC17 | Hardware-Garantie ANT1 (encoder.transmit zentral) | Code-Read unveraendert |
| AC18 | UI Statusbar zeigt `Ω CQ=X (E/O)` | Code-Read |
| AC19 | Tests-Bilanz: 1034 → ~990 gruen (Pattern+Pending Tests weg, simplified Tests rein) | pytest |

---

## 6. Field-Test-Plan

| F | Test | Erwartung |
|---|---|---|
| F1 | App start, Diversity, OMNI toggeln | OMNI-Start-Log + CQ-Audiofreq-Set + erster CQ in aktuellem Slot |
| F2 | 5-10 Min beobachten | CQ-Ruf in EINER Paritaet (z.B. nur Even-Slots :30/:00). Andere Slots leer im qso_panel. Diversity-Anzeige zeigt **beide Antennen wechselnd** (kein „nur eine"). |
| F3 | Statusbar checken | `Ω CQ=X (E)` oder `(O)` zeigt aktuellen Stand |
| F4 | 10 Min weiterlaufen lassen | Paritaets-Wechsel automatisch (Log: „Paritaets-Wechsel auf Odd"). qso_panel zeigt ab dann CQ in anderer Paritaet (z.B. nur Odd :45/:15) |
| F5 | Antwort kommt waehrend OMNI | OMNI pausiert, QSO laeuft normal mit voller Diversity. Nach QSO: OMNI resumed in alter Paritaet |
| F6 | 1h warten → Diversity Re-Mess (90s) | OMNI sendet **nicht** waehrend Mess (Log: kein TX-Eintrag in 90s). Nach Mess: OMNI sendet wieder |
| F7 | Bandwechsel mid-OMNI | OMNI auto-stop (band_change), App stabil |
| F8 | Mode-Wechsel auf Normal | OMNI auto-stop (mode_change), App stabil |

**Bestanden wenn:** F1-F4 sauber + F2 zeigt Diversity beide Antennen.

---

## 7. Test-Plan

### 7.1 Tests die WEGGEHEN

- `tests/test_encoder_pending.py` (8 Tests) — **DELETE komplett**
- `tests/test_omni_cq_signal.py` (32 Tests) — **REWRITE komplett** (alte Pattern-Tests obsolet)

### 7.2 Tests die ANGEPASST werden

- `tests/test_omni_cq_integration.py` (~14 Tests) — Pattern-spezifische Aufrufe (`_slot_index = N`) entfernen, Resume-Tests bleiben kompatibel
- `tests/test_modules.py` — Encoder-Tests koennten betroffen sein durch Rueckrollung (Z. 710/2582/2648/2690/2823 setzen `_is_transmitting=True`). Nach Rueckrollung sollten alle wieder gruen sein.

### 7.3 Tests die BLEIBEN unangetastet

- `tests/test_main_window_slot_boundary.py` (5) — allgemeine Slot-Boundary
- `tests/test_p1_9_replace.py` (5) — Encoder-Replace-Pfad (kein Pending betroffen)
- alle anderen

### 7.4 NEUE Tests fuer simplified OMNI (10 Tests, mappen zu AC1-AC13)

| ID | Name | AC |
|---|---|---|
| T1 | `test_start_initial_state` | AC1 |
| T2 | `test_first_cycle_sets_tx_even_from_fresh_time` | AC2 |
| T3 | `test_matching_cycle_calls_encoder_transmit_and_emits` | AC3 |
| T4 | `test_non_matching_cycle_skips_encoder` | AC4 |
| T5 | `test_skips_during_diversity_measure_phase` | AC5 |
| T6 | `test_flip_tx_parity_toggles_and_emits` | AC6 |
| T7 | `test_flip_tx_parity_noop_when_uninitialized` | AC7 |
| T8 | `test_on_search_trigger_counts_and_flips_at_threshold` | AC8 |
| T9 | `test_mw_cycle_calls_omni_on_search_trigger` (Integration) | AC9 |
| T10 | `test_pause_resume_preserves_parity` | AC10 |
| T11 | `test_frequency_sticky_across_flip` | AC11 |
| T12 | `test_stop_resets_all_state` | AC12 |
| T13 | `test_resume_after_qso_signature_compat` (mit/ohne Arg) | AC13 |
| T14 | `test_on_search_trigger_during_pause_noop` (R1-SF-3) | AC8/SF-1 |

### 7.5 KEIN Worker/Sleep/Boundary-Mock

(Lesson `feedback_test_critical_path_not_mock.md`) — Tests rufen
`on_cycle_start` direkt mit synthetischen Werten + Mock-Encoder.
Diversity-`phase` als Mock-Property kontrollierbar.

### 7.6 Test-Bilanz

**Vor P7:** 1034 gruen
**Aenderungen:**
- WEG: 8 (test_encoder_pending) + 32 (test_omni_cq_signal) = -40
- ANGEPASST: ~14 (test_omni_cq_integration) — Anzahl bleibt
- NEU: ~10 (simplified test_omni_cq) + Integration T9 = +11
- Netto: -40 + 11 = -29

**Nach P7:** ~1005 gruen erwartet (Toleranz ±5).

---

## 8. Atomare Commits-Plan

| # | Commit | Files | Tests-Effekt |
|---|---|---|---|
| C1 | `core/encoder.py: P5+P6 zurueckrollen (Pending+Pair weg)` | core/encoder.py | -8 (test_encoder_pending DELETE in C5) |
| C2 | `core/omni_cq.py: radikale Vereinfachung (single-slot + Such-Counter)` | core/omni_cq.py | breaks test_omni_cq_signal.py (komplett neu in C5) |
| C3 | `ui/mw_cycle.py: Such-Trigger-Hook fuer omni_cq.on_search_trigger()` | ui/mw_cycle.py | breaks integration tests bis C5 |
| C4 | `ui/main_window.py: cq_count_changed signal + parity_flipped + Statusbar-Update` | ui/main_window.py | — |
| C5 | `tests: alte OMNI/Pending-Tests entfernen, neue simplified Tests T1-T13` | tests/test_encoder_pending.py (DELETE), tests/test_omni_cq_signal.py (REWRITE), tests/test_omni_cq_integration.py (UPDATE) | netto -29 |
| C6 | `main.py: APP_VERSION 0.96.3 → 0.96.4` | main.py:16 | — |
| C7 | `Doku: HISTORY + HANDOFF + CLAUDE + TODO + Memory + Spec-Update` | HISTORY.md, HANDOFF.md, CLAUDE.md, TODO.md, memory/* | — |

**Reihenfolge:** C1 → grun-Check (mit failing test_encoder_pending) → C2 → grun-Check (mit failing test_omni_cq_signal) → C3 → C4 → C5 → grun-Check (alle gruen) → C6 → C7.

**Pre-Code-Pflicht:**
1. `git status` clean
2. Tests-Baseline: `QT_QPA_PLATFORM=offscreen ./venv/bin/python3 -m pytest tests/ -q` → 1034 erwartet
3. App gestoppt (Mike's Anweisung)

---

## 9. Out-of-Scope

- ❌ Diversity-Logik aendern (Mike: UNANTASTBAR)
- ❌ `should_remeasure`, `start_measure`, `tick_slot` Logik aendern (nur Hook hinzufuegen)
- ❌ Normal-CQ-Pfad (`qso_state.cq_mode`) anfassen
- ❌ Counter-UI radikal umbauen (nur Statusbar-Text aendern)
- ❌ P8.MESS-STATUS-DIALOG (separater Workflow)
- ❌ Re-Mess-Intervall aendern (3600s bleibt)

---

## 10. APP_VERSION-Plan

`v0.96.3 → v0.96.4` (Patch-Bump: OMNI-Refactor, Encoder-Cleanup).

---

## 11. Doku-Update Plan (C7)

### `HISTORY.md` (neuer Eintrag am Ende)

```markdown
## 2026-05-10 v0.96.4 — P7.OMNI-SIMPLIFY: Single-Slot + Such-Counter

**Auslöser:** P5 (Pending-Verfall) und P6 (Pair-Audio) lösten Pos-1-Race
nicht sauber:
- P5: Verfall-Schwelle zu klein, TX kommt zu spät, Pattern halb tot
- P6: 27.6s durchgehend `_is_transmitting=True` blockt Diversity-
  Antennen-Switching → Mike sieht „nur eine Antenne"

**Wurzel:** TX-TX-konsekutiv in 15s-Slots passt physisch nicht zu
Encoder + Diversity. Beide Workarounds verbiegen Encoder/Diversity um
das alte Pattern zu retten.

**Mike-Spec 10.05.:** Pattern aendern statt Encoder/Diversity verbiegen.
OMNI = Single-Slot-CQ in EINER Paritaet, automatischer Wechsel ueber
existierenden Such-Counter alle ~10 Min.

**Loesung:**
- `core/encoder.py`: P5+P6 komplett zurueckgerollt (transmit_pair,
  _tx_pair_*, _pending_tx, _run_one_tx_pass, _compute_target_slot weg)
- `core/omni_cq.py`: 305 Z. → 210 Z., 5-Slot-Pattern + Block-Wechsel +
  _pair_in_progress entfernt. Neu: `on_search_trigger()`, `flip_tx_parity()`
- `ui/mw_cycle.py:160`: Hook nach `tick_slot() == True` →
  `_omni_cq.on_search_trigger()`
- `ui/main_window.py`: cq_count_changed Signal-Format + Statusbar
  vereinfacht
- `_OMNI_FLIP_AFTER_SEARCHES = 10` → ~10 Min Wechsel-Intervall (FT8 60s/Such)
- Mess-Phase-Schutz: OMNI no-op wenn `diversity.phase != "operate"`
- V2-L9 Robustheit: is_even FRESH neu berechnen aus time.time() (Live-
  Test-Latenz-Schutz)

**Vorteile:**
- Diversity 100% unangetastet (Mike-Pflicht)
- Encoder schlanker als vor v0.96.2
- omni_cq.py 31% kleiner
- KEIN Race, KEIN Drift-Konflikt, KEINE Pending-Loop, KEIN Pair-Audio
- Coverage: 10 Min Even / 10 Min Odd alternierend (vorher: jeder Slot
  alternierend, aber mit Race-Bug)

**Atomare Commits:** C1-C7 (Encoder + OMNI + mw_cycle + main_window +
Tests + APP_VERSION + Doku).

**Tests:** 1034 → ~1005 gruen (-40 Pattern+Pending Tests, +11 simplified
Tests).

**APP_VERSION:** v0.96.3 → v0.96.4. Push pending bis Mike-Field-Test grün.
```

### `HANDOFF.md`

Stand-Block ersetzen mit P7-ERLEDIGT + Field-Test-Plan F1-F8.

### `CLAUDE.md` Header

Aktueller Stand v0.96.4 + Tests ~1005.

### `TODO.md`

P7-Block raus, Field-Test als TOP. P8-Block bleibt (geplant nach P7).

### `memory/project_omni_cq_spec.md`

**Komplett neu schreiben** — alte 5-Slot-Spec obsolet.

### `memory/MEMORY.md`

P7-Eintrag „✅ ERLEDIGT", P5-Eintrag auf „verworfen wegen Diversity-Block".

---

## 12. Risiko-Bewertung

| ID | Risiko | Wahrscheinlichkeit | Mitigation |
|---|---|---|---|
| R1 | Encoder-Rueckrollung bricht test_p1_9_replace.py | Niedrig (P5+P6 sind isoliert hinzugefuegt) | Vor C5 manuell durchspielen |
| R2 | Re-Mess-Hook in mw_cycle:160 greift nicht (Pfad evtl. nicht jeder Slot) | Niedrig (siehe `_refresh_diversity_freq_view` ist pro Slot) | T9 Integration-Test |
| R3 | OMNI startet vor erstem Such-Trigger → Counter bei 0 → 10 Min keine flip | Mittel (akzeptiert) | Doku, Mike erwartet das |
| R4 | Mess-Phase-Skip blockiert OMNI komplett wenn diversity stuck in measure | Niedrig (existing) | Wenn diversity bug: anderer Workflow |
| R5 | UI Statusbar `Ω CQ=X (E)` koennte verwirren wenn _cq_tx_even=None | Niedrig | Code zeigt `(?)` als Initial-Wert |
| R6 | Bestehende Aufrufer von resume_after_qso(last_was_even) brechen | Sehr niedrig (Signatur kompatibel mit Default-Param) | T13 |
| R7 | parity_flipped Signal nirgendwo connected → emit ohne Receiver | Niedrig (Qt erlaubt das) | UI connectet (C4) |
| R8 | Such-Counter zaehlt waehrend Mess-Phase weiter → flip mid-Mess | Niedrig (`tick_slot` wird in mw_cycle pro Slot gerufen unabhaengig von Phase) | Phase-Check im on_cycle_start fängt es ab — Mess-Slot sendet eh nicht |

---

## 13. Plan-Files Verzeichnis

- ✅ `prompts/p7_omni_simplify_v1.md`
- ✅ `prompts/p7_omni_simplify_v2.md` (Self-Review, 12 Lessons)
- ✅ `prompts/p7_omni_simplify_v3.md` (DIESE DATEI, Compact-fest)
- 🔜 `prompts/p7_omni_simplify_r1_prompt.md` (R1-Brief, schreibe ich als naechstes)
- 🔜 `prompts/p7_omni_simplify_r1.md` (R1-Output)
- 🔜 `prompts/p7_omni_simplify_final_r1_prompt.md` (Final-R1 nach Code)
- 🔜 `prompts/p7_omni_simplify_final_r1.md`

---

## 14. Naechste Schritte

1. **R1-Brief schreiben** (`p7_omni_simplify_r1_prompt.md`)
2. **R1-Lauf** mit DeepSeek-Reasoner
3. **V3-Final** (R1-Findings einarbeiten)
4. **Mike-Freigabe**
5. **Compact** (mit Cold-Start-Test post-Compact)
6. **Code C1-C7** atomar
7. **Final-R1** nach Code
8. **Field-Test mit Mike** (V3 §6)
9. **Push** wenn Mike OK

---

**Ende V3.**
