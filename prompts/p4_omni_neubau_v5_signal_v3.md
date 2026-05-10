# P4.OMNI-NEUBAU V5 — Signal-basierter Refactor (V3, Compact-fest)

**Datum:** 2026-05-09 spät, post-R1
**Status:** R1 (DeepSeek-Reasoner, in=37701/out=12459 Tokens):
„Spezifikation durchdacht und weitgehend widerspruchsfrei. Architektur
robust und für den Hobby-Einsatz angemessen." Alle 3 Klärungsfragen
mit Variante A (KISS) bestätigt. 10 Findings angenommen, keine
Halluzinationen.
**Verbindliche Spec:** Mike-Dialog 09.05.2026 spät +
`memory/project_omni_cq_spec.md`. Diese V3 ist die einzige Wahrheit
für Code-Phase.

---

## 0. Code-Verifikation (Schritt 0, gegen aktuellen Code geprüft)

| Verifikation | Stand | Beleg |
|---|---|---|
| `FT8Timer.cycle_start = Signal(int, bool)` | EXISTIERT | `core/timing.py:19` |
| `cycle_start.emit(cycle_count, is_even)` Emit-Stelle | EXISTIERT | `core/timing.py:87` |
| `MainWindow.timer.cycle_start.connect(self._on_cycle_start)` | EXISTIERT | `ui/main_window.py:622` |
| `mw_cycle._on_cycle_start(cycle_num: int, is_even: bool)` | EXISTIERT | `ui/mw_cycle.py:575` |
| `encoder.transmit(message, *, tx_even=None, audio_freq_hz=None) -> bool` atomare API (C3) | EXISTIERT | `core/encoder.py:189-212` |
| `Encoder._next_slot_boundary` mit absolut-UTC-Slot-Boundaries | EXISTIERT | `core/encoder.py:235-281` |
| `Encoder.set_tx_antenna("ANT1")` zentral | EXISTIERT | `core/encoder.py:363` |
| Listener-Pfad `mw_cycle.on_message_decoded` (C6) | EXISTIERT | `ui/mw_cycle.py:793-832` (mit OMNI-Listener-Block) |
| `mw_qso._pause_omni_if_active` / `_maybe_resume_omni` Helper (C6) | EXISTIERT | `ui/mw_qso.py:34-86` |
| `MainWindow._omni_cq` Init + 4 Signal-Connects (C6) | EXISTIERT | `ui/main_window.py:250-265` |
| Stop-Trigger in `mw_radio.py` (C7) | EXISTIERT | `ui/mw_radio.py:211-212, 326-327, 410-411` |
| Aktuelles `core/omni_cq.py` Worker-Thread mit Bug | 337 Zeilen | wird komplett umgebaut |

---

## 1. Ziel

`core/omni_cq.py` von Worker-Thread auf signal-getriggertes Modul
refactorn. OMNI-CQ bleibt **eigenständig** (kein `qso_state.cq_mode`-Hack),
aber die Slot-Synchronisation kommt vom existing
`FT8Timer.cycle_start`-Signal — wie Normal-CQ es seit v0.78 nutzt.

**Zentrale Methode:** `OmniCQ.on_cycle_start(cycle_num: int, is_even: bool)`
entscheidet pro Slot:
- Pos 0/1 (TX): `encoder.transmit(...)` mit korrekter Parität
- Pos 2/3/4 (RX): emit `slot_action` für „Horche..."-Anzeige
- `_slot_index` advancen, bei Rollover Block wechseln

---

## 2. Verbindliches Pattern

```
Block 1 (Even-First):
  Pos 0: TX-E
  Pos 1: TX-O
  Pos 2: RX-E (Horche)
  Pos 3: RX-O (Horche)
  Pos 4: RX-E (Horche, extra Slot für sauberen Übergang)

Block 2 (Odd-First):
  Pos 0: TX-O
  Pos 1: TX-E
  Pos 2: RX-O (Horche)
  Pos 3: RX-E (Horche)
  Pos 4: RX-O (Horche)

Wechsel: nach 5 Slots automatisch (slot_index 4 → 0).
Block 1 ↔ Block 2 permanent.
QSO-Resume: endet auf Even → Block 2, endet auf Odd → Block 1.
IMMER ab Pos 0.
```

---

## 3. Akzeptanzkriterien

### Pattern + Trigger

| AC | Kriterium |
|----|-----------|
| AC1 | Bei btn_omni_cq → `OmniCQ.start()` setzt `_active=True`, `_slot_index=0`, `_block=1`, `_paused=False`, `_cq_audio_hz=None`, Counter zurück. Statusbar „Ω Even=0 Odd=0", Button-Label „OMNI CQ (aktiv)". `start()` ist **idempotent** — Aufruf bei `_active=True` ist no-op (return). |
| AC2 | Block 1 Pattern: Pos 0 TX-E, Pos 1 TX-O, Pos 2 RX-E, Pos 3 RX-O, Pos 4 RX-E. |
| AC3 | Block 2 Pattern: Pos 0 TX-O, Pos 1 TX-E, Pos 2 RX-O, Pos 3 RX-E, Pos 4 RX-O. |
| AC4 | Block-Rollover automatisch nach 5 Slots (`slot_index 4 → 0`): Block 1 ↔ Block 2 permanent. |
| AC5 | **Toggle-Start: IMMER Block 1 (Even-First).** Wenn aktueller UTC-Slot odd ist, encoder verzögert TX-E auf nächsten passenden Slot (1 Slot = 15s FT8 / 7.5s FT4 / 3.8s FT2 Wartezeit, akzeptabel KISS). Keine Block-Wahl-Heuristik. |
| AC6 | `OmniCQ.on_cycle_start(cycle_num: int, is_even: bool)` mit `@Slot(int, bool)` deklariert. Wird aus `mw_cycle._on_cycle_start` aufgerufen (siehe §4). |
| AC7 | `on_cycle_start` startet mit Defense-in-Depth-Guard: `if not self._active or self._paused: return`. Pattern-Entscheidung basiert auf `_slot_index` (NICHT auf `is_even` aus dem Signal — `is_even` wird nur für RX-Anzeige genutzt). |
| AC8 | TX-Slot (Pos 0/1): ruft `encoder.transmit("CQ {call} {grid}", tx_even=target_even, audio_freq_hz=cq_freq)`. Encoder-Thread schedulet auf passenden UTC-Slot (analog Normal-CQ-Pfad seit v0.78). Bei Erfolg (Return True): Counter inkrementieren + `counter_changed.emit(even, odd)` + `slot_action.emit(label, is_tx=True, target_even=target_even)`. |
| AC9 | RX-Slot (Pos 2/3/4): `slot_action.emit(label, is_tx=False, target_even=is_even)` — `is_even` aus dem Signal-Parameter (echte UTC-Slot-Parität). KEIN `transmit`-Aufruf. |
| AC10 | Nach Aktion (TX oder RX, auch bei encoder-busy): `_slot_index = (_slot_index + 1) % 5`. Bei Rollover (slot_index → 0): `_block = 2 if _block==1 else 1`. |

### Encoder-Busy-Verhalten

| AC | Kriterium |
|----|-----------|
| AC11 | Wenn `encoder.transmit(...)` False returnt (TX schon laufend): KEIN counter increment, KEIN `slot_action.emit`, **nur log warning** (KISS — `qso_panel` ist NICHT in OmniCQ injectet, UI-Hinweis wäre Architektur-Bruch). `_slot_index` advanced trotzdem (Pattern bleibt synchron, AC10). |

### Frequenz

| AC | Kriterium |
|----|-----------|
| AC12 | Beim ersten TX-Slot in einem aktiven OMNI-Lauf (`_cq_audio_hz is None`): `_cq_audio_hz = diversity.get_free_cq_freq()`. Fallback 1500 Hz wenn None. Emit `cq_freq_changed(_cq_audio_hz)`. |
| AC13 | **Frequenz-Sticky V5-KISS:** 1× am Anfang setzen, dann fest bis Stop. Kein Recheck-Counter, kein Histogramm-Recheck zur Laufzeit. Mike-Original-Spec: „Bleibt fest. Kein Versatz, kein Springen." |
| AC14 | Bei `pause()` und `resume_after_qso(...)`: `_cq_audio_hz` BEHALTEN. Frequenz wechselt NUR durch `stop()` + neuer `start()`. |
| AC15 | Bei `stop(...)`: `_cq_audio_hz = None`. |

### QSO-Übergabe

| AC | Kriterium |
|----|-----------|
| AC16 | Listener `mw_cycle.on_message_decoded` bleibt UNVERÄNDERT (C6-korrekt): wenn `_omni_cq.is_active() and not _omni_cq.is_paused() and msg.target == my_call and not msg.is_73 and not msg.is_rr73` → `_pause_omni_if_active()` + `encoder.tx_even = not msg._tx_even` + `qso_sm.start_qso(...)`. |
| AC17 | `pause()` setzt `_paused=True` (kein Thread mehr — einfacher Flag-Set). `_active` bleibt True. `on_cycle_start` während `_paused` → no-op (AC7-Guard). Idempotent — Aufruf bei `_paused=True` ist no-op. |
| AC18 | `resume_after_qso(last_was_even)` mit Pre-Check: `if not self._paused: return` (no-op + log warning falls fälschlich nach `stop` aufgerufen). Sonst: Block-Wahl — `last_was_even=True` → `_block=2`, sonst `_block=1`. `_slot_index=0`. `_paused=False`. `_cq_audio_hz` BLEIBT (AC14). |
| AC19 | Caller-Queue bleibt im `_maybe_resume_omni`-Helper in `mw_qso.py` (C6-Code unverändert). |

### Stop-Trigger

| AC | Kriterium |
|----|-----------|
| AC20 | `stop(reason)`: `_active=False`, `_paused=False`, `_slot_index=0`, `_block=1`, `_cq_audio_hz=None`, `_cq_even_count=0`, `_cq_odd_count=0`. Emittet `omni_stopped(reason)`. Idempotent (Aufruf bei `_active=False` ist no-op). |
| AC21 | Stop-Reasons (alle bleiben aus C7): `manual_halt`, `band_change`, `mode_change`, `rx_mode_change`, `totmann_expired`, `superseded`, `easter_egg_off`, `test_cleanup`. Trigger-Stellen unverändert. |

### Signals (API-Compat zu C6 main_window-Slots)

| AC | Kriterium |
|----|-----------|
| AC22 | `omni_started = Signal()` — emittet beim `start()` direkt nach State-Init, VOR erstem `cycle_start`. |
| AC23 | `omni_stopped = Signal(str)` — emittet beim `stop(reason)`. |
| AC24 | `slot_action = Signal(str, bool, bool)` — `(label, is_tx, target_even)`. Bei TX UND RX. Reihenfolge bei TX-Erfolg: `counter_changed.emit` → `slot_action.emit`. |
| AC25 | `cq_freq_changed = Signal(int)` — emittet beim ersten TX-Slot wenn Frequenz initialisiert wird (AC12). |
| AC26 | `counter_changed = Signal(int, int)` — `(cq_even, cq_odd)`. Bei TX-Erfolg (AC8). |

### Hardware

| AC | Kriterium |
|----|-----------|
| AC27 | OMNI emittet keinen TX direkt — geht über `encoder.transmit()`, der zentral `radio.set_tx_antenna("ANT1")` setzt (`core/encoder.py:363`). Kein Extra-Check nötig. |

### Tests

| AC | Kriterium |
|----|-----------|
| AC28 | `tests/test_omni_cq_signal.py` NEU (~20 Tests): rufen `on_cycle_start(cycle_num, is_even)` direkt auf, Mock-Encoder verifiziert `transmit`-Calls + kwargs. **KEIN Worker-Mock, KEIN Sleep-Mock, KEIN Boundary-Mock.** Lessons-Learned aus heute: `_block_worker_boundaries` hat den kritischen Pfad versteckt. |
| AC29 | `tests/test_omni_cq_worker.py` (37 Tests, v0.96.0 obsolet) → KOMPLETT ENTFERNEN. |
| AC30 | `tests/test_omni_cq_integration.py` (14 Tests aus C6) — `_block_worker_boundaries`-Hilfe entfernen (kein Thread mehr). API-Aufrufe bleiben gleich. |

---

## 4. Betroffene Module/Dateien

### NEU geschrieben

**`core/omni_cq.py`** — kompletter Refactor (~80-120 Zeilen statt 337).

Code-Skelett:
```python
from PySide6.QtCore import QObject, Signal, Slot

class OmniCQ(QObject):
    omni_started = Signal()
    omni_stopped = Signal(str)
    slot_action = Signal(str, bool, bool)
    cq_freq_changed = Signal(int)
    counter_changed = Signal(int, int)

    _TX_PATTERN = (True, True, False, False, False)
    _FALLBACK_AUDIO_HZ = 1500

    def __init__(self, encoder, diversity_ctrl, timer,
                 my_call: str, my_grid: str):
        super().__init__()
        self._encoder = encoder
        self._diversity = diversity_ctrl
        self._timer = timer            # nur für is_even_cycle in Tests
        self._my_call = my_call
        self._my_grid = my_grid
        self._active = False
        self._paused = False
        self._slot_index = 0
        self._block = 1
        self._cq_audio_hz: int | None = None
        self._cq_even_count = 0
        self._cq_odd_count = 0

    def start(self) -> None:
        if self._active:
            return                      # AC1: idempotent
        self._active = True
        self._paused = False
        self._slot_index = 0
        self._block = 1                 # AC5: IMMER Block 1
        self._cq_audio_hz = None
        self._cq_even_count = 0
        self._cq_odd_count = 0
        self.omni_started.emit()        # AC22

    def stop(self, reason: str) -> None:
        if not self._active:
            return                      # AC20: idempotent
        self._active = False
        self._paused = False
        self._slot_index = 0
        self._block = 1
        self._cq_audio_hz = None
        self._cq_even_count = 0
        self._cq_odd_count = 0
        self.omni_stopped.emit(reason)

    def pause(self) -> None:
        if not self._active or self._paused:
            return                      # AC17: idempotent
        self._paused = True

    def resume_after_qso(self, last_was_even: bool) -> None:
        if not self._paused:
            return                      # AC18: Pre-Check
        self._block = 2 if last_was_even else 1
        self._slot_index = 0
        self._paused = False
        # _cq_audio_hz bleibt (AC14)

    def is_active(self) -> bool:
        return self._active

    def is_paused(self) -> bool:
        return self._paused

    @property
    def cq_even_count(self) -> int:
        return self._cq_even_count

    @property
    def cq_odd_count(self) -> int:
        return self._cq_odd_count

    @property
    def cq_audio_hz(self) -> int | None:
        return self._cq_audio_hz

    @Slot(int, bool)
    def on_cycle_start(self, cycle_num: int, is_even: bool) -> None:
        # AC7: Defense-in-Depth-Guard
        if not self._active or self._paused:
            return
        is_tx, target_even = self._next_slot_action()
        if is_tx:
            self._do_tx_slot(target_even)
        else:
            self._do_rx_slot(is_even)
        self._advance_state()           # AC10: immer advance

    def _next_slot_action(self) -> tuple[bool, bool]:
        is_tx = self._TX_PATTERN[self._slot_index]
        if not is_tx:
            return False, False
        if self._block == 1:
            target_even = (self._slot_index == 0)
        else:
            target_even = (self._slot_index == 1)
        return True, target_even

    def _do_tx_slot(self, target_even: bool) -> None:
        # AC12: Sticky-Frequenz beim ersten TX
        if self._cq_audio_hz is None:
            freq = self._diversity.get_free_cq_freq()
            if freq is None:
                freq = self._FALLBACK_AUDIO_HZ
            self._cq_audio_hz = int(freq)
            self.cq_freq_changed.emit(self._cq_audio_hz)
        cq_msg = f"CQ {self._my_call} {self._my_grid}"
        ok = self._encoder.transmit(
            cq_msg, tx_even=target_even, audio_freq_hz=self._cq_audio_hz,
        )
        label = self._slot_label(True, target_even)
        if ok:
            if target_even:
                self._cq_even_count += 1
            else:
                self._cq_odd_count += 1
            self.counter_changed.emit(self._cq_even_count, self._cq_odd_count)
            self.slot_action.emit(label, True, target_even)
        else:
            # AC11: Fail-Pfad — log + UI-Hinweis, kein counter, kein slot_action
            logger.warning("[OMNI-CQ] encoder.transmit busy → Slot %s übersprungen", label)
            # qso_panel.add_info-Aufruf ist Aufruferseite (in mw_cycle, optional)

    def _do_rx_slot(self, is_even: bool) -> None:
        label = self._slot_label(False, is_even)
        self.slot_action.emit(label, False, is_even)

    def _advance_state(self) -> None:
        self._slot_index = (self._slot_index + 1) % 5
        if self._slot_index == 0:
            self._block = 2 if self._block == 1 else 1

    def _slot_label(self, is_tx: bool, target_even: bool) -> str:
        parity = "E" if target_even else "O"
        kind = "TX" if is_tx else "RX"
        return f"B{self._block} [{self._slot_index}/4] {kind}-{parity}"
```

### Verbindung (kleine Änderung)

**`ui/mw_cycle.py:575` `_on_cycle_start`** — am ENDE ergänzen (NACH `qso_sm.on_cycle_end()`):
```python
@Slot(int, bool)
def _on_cycle_start(self, cycle_num: int, is_even: bool):
    # ... bestehender Code:
    # 1. Anzeige-Reset wenn nicht TX
    # 2. Auto-TX-Level-Regelung
    # 3. qso_sm.on_cycle_end()  ← Normal-CQ Re-Trigger etc.
    # 4. OMNI-Trigger NEU am Ende:
    if hasattr(self, '_omni_cq'):
        self._omni_cq.on_cycle_start(cycle_num, is_even)
```

**Reihenfolge ist wichtig:** `qso_sm.on_cycle_end()` läuft VOR
`omni_cq.on_cycle_start()`. Damit greifen Normal-CQ-Re-Trigger und
QSO-Timeout zuerst (cq_mode=False während OMNI → no-op), erst danach
OMNI-Pattern-Advance.

`hasattr`-Guard ist defensiv (OmniCQ wird in MainWindow.__init__ vor
dem cycle_start-Connect initialisiert, existiert also immer zur
Laufzeit) — schadet aber nicht, KISS für Test-Setups die mw_cycle
isoliert testen.

### Tests

- **`tests/test_omni_cq_worker.py`** — KOMPLETT LÖSCHEN (37 Tests obsolet, Worker weg).
- **`tests/test_omni_cq_signal.py`** — NEU (siehe §6).
- **`tests/test_omni_cq_integration.py`** — `_block_worker_boundaries`-Helfer entfernen, weiter nutzen wo es um `is_active()` / `pause()` / `stop()` etc. geht.

### UNVERÄNDERT

- `core/encoder.py` (atomare API C3 ✓)
- `core/qso_state.py` (kein cq_mode-Hack ✓)
- `ui/mw_cycle.on_message_decoded` (Listener C6 ✓)
- `ui/mw_qso._pause_omni_if_active` / `_maybe_resume_omni` (Helper C6 ✓)
- `ui/main_window.py` OMNI-Init + 4 Signal-Slots (C6 ✓)
- `ui/mw_radio.py` Stop-Trigger (C7 ✓)

---

## 5. Randbedingungen

### Threading

- `cycle_start`-Signal vom FT8Timer-Thread → Qt.QueuedConnection → GUI-Thread.
- `OmniCQ.on_cycle_start` läuft im **GUI-Thread** — kein Lock nötig.
- `encoder.transmit` thread-safe (atomare API mit `_replace_lock` aus C3).
- `pause` / `resume_after_qso` / `stop` aus mw_qso/main_window/mw_radio: alle GUI-Thread.

### Decoder-Blockade-Risiko (akzeptiert KISS)

- `cycle_start`-Signal kann durch GUI-Thread-Blockade (Decoder ~0.1-1s) verzögert ankommen.
- Wenn `cycle_start` für Slot N erst bei `now = N*SLOT + cycle_pos > 0.5s` ankommt:
  - `encoder.transmit(tx_even=True)` wird gerufen, encoder berechnet `_next_slot_boundary`:
    - `cycle_pos > 0.5` → encoder nimmt **nächsten** passenden Slot.
  - Folge: 1 Pos im Pattern „skipped" auf späteren Slot, `_slot_index` advanced trotzdem.
- Bei regelmäßigen Blockaden > 0.5s pro Slot kann das OMNI-Pattern temporär inkonsistent werden — für Hobby-Use akzeptabel (Normal-CQ hat dasselbe Risiko seit v0.78).

### Encoder-Erfolg ≠ TX-Send-Erfolg (R1-Hinweis)

- `encoder.transmit(...)` returnt True wenn der Worker akzeptiert wurde, NICHT wenn der TX wirklich on-air gegangen ist (Encoding-Fehler / Radio-Fehler treten später im Worker auf).
- OMNI inkrementiert Counter trotzdem bei True-Return (KISS, Hobby-typisch selten relevant).

### Pause während TX-Slot (R1-Hinweis)

- Wenn `pause()` während eines TX-Slots ausgelöst wird (z.B. Mike's CQ wurde gerade beantwortet aber OMNI ist mid-TX): aktueller TX läuft im Encoder-Thread weiter zu Ende. `_slot_index` friert auf aktuellem Wert ein.
- Bei `resume_after_qso(...)` wird `_slot_index=0` gesetzt — der zuvor verarbeitete TX-Slot ist „verloren" (keine Wiederholung).
- Akzeptiert KISS: typisches QSO startet aus RX-Slot heraus, nicht mid-TX.

### Hardware ANT1

- `encoder.transmit` setzt zentral `radio.set_tx_antenna("ANT1")`. Kein Extra-Check nötig.

### KISS

- Kein Frequenz-Recheck-Counter (V5: 1× am Start, fest).
- Kein 80-Cycles-Counter (Block-Rollover bei `slot_index 4 → 0`).
- Kein cycle_tick-Pretrigger / kein QTimer (obsolet).
- Kein Worker-Thread, keine Sleeps, keine Boundary-Berechnung.

---

## 6. Test-Plan

### Unit-Tests `tests/test_omni_cq_signal.py` (NEU, 20 Tests)

**Test-Helper (Vorlage für `tests/test_omni_cq_signal.py`):**
```python
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from PySide6.QtWidgets import QApplication

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from core.omni_cq import OmniCQ  # noqa: E402


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def _make_omni(*, free_cq_freq: int | None = 1500):
    """Test-Setup: OmniCQ mit Mock-Encoder/Diversity/Timer.

    Returns: (omni, encoder, diversity, timer) für Test-Asserts.
    KEIN Worker-Mock, KEIN Sleep-Mock, KEIN Boundary-Mock.
    """
    encoder = MagicMock()
    encoder.transmit = MagicMock(return_value=True)
    diversity = MagicMock()
    diversity.get_free_cq_freq = MagicMock(return_value=free_cq_freq)
    timer = MagicMock()
    timer.cycle_duration = 15.0
    timer.is_even_cycle = MagicMock(return_value=False)
    omni = OmniCQ(
        encoder=encoder,
        diversity_ctrl=diversity,
        timer=timer,
        my_call="DA1MHH",
        my_grid="JN58",
    )
    return omni, encoder, diversity, timer
```

**Test-Pattern:**
```python
def test_block1_pos0_calls_encoder_transmit_tx_even(app):
    omni, encoder, *_ = _make_omni()
    omni.start()
    omni.on_cycle_start(cycle_num=100, is_even=True)
    encoder.transmit.assert_called_once_with(
        "CQ DA1MHH JN58", tx_even=True, audio_freq_hz=1500
    )
    assert omni._slot_index == 1
```

**KEIN `_block_worker_boundaries`. KEIN Thread-Mock. Tests rufen `on_cycle_start` direkt auf.** Wenn ein Test einen Mock braucht der die Logik überschreibt die er prüfen will → Test überarbeiten (siehe Memory `feedback_test_critical_path_not_mock.md`).

| # | Test | AC |
|---|------|----|
| T1 | `test_initial_state_inactive` | AC1 |
| T2 | `test_start_initializes_block1_pos0` | AC1, AC5 |
| T3 | `test_start_idempotent_on_already_active` | AC1 |
| T4 | `test_block1_pos0_calls_encoder_transmit_tx_even` | AC2, AC8 |
| T5 | `test_block1_pos1_calls_encoder_transmit_tx_odd` | AC2, AC8 |
| T6 | `test_block1_pos_2_3_4_no_transmit_emits_horche` | AC2, AC9 |
| T7 | `test_rollover_block1_to_block2_first_tx_is_odd` (vorher T6, R1-Rename) | AC3, AC4, AC10 |
| T8 | `test_block2_pos1_tx_even` | AC3 |
| T9 | `test_block2_rollover_back_to_block1` | AC4 |
| T10 | `test_block_alternation_permanent_15_slots` | AC4 |
| T11 | `test_pause_freezes_slot_index_active_stays_true` | AC17 |
| T12 | `test_on_cycle_start_during_pause_no_op` | AC7, AC17 |
| T13 | `test_resume_after_qso_even_chooses_block2_pos0` | AC18 |
| T14 | `test_resume_after_qso_odd_chooses_block1_pos0` | AC18 |
| T15 | `test_resume_after_qso_no_op_when_not_paused` (R1-AC18-PreCheck) | AC18 |
| T16 | `test_stop_resets_full_state` (parametrize 8 reasons) | AC20, AC21 |
| T17 | `test_freq_init_from_diversity_first_tx` | AC12 |
| T18 | `test_freq_fallback_1500_when_diversity_none` | AC12 |
| T19 | `test_freq_sticky_during_omni_5_cycles` | AC13 |
| T20 | `test_freq_kept_during_pause_resume` | AC14 |
| T21 | `test_encoder_busy_no_counter_no_slot_action_but_advance` (R1-Hinweis) | AC11 |
| T22 | `test_signals_emitted_correctly` (alle 5 Signale) | AC22-26 |

(22 Tests — V3 nimmt 20+2 R1-Findings dazu).

### Integration-Tests `tests/test_omni_cq_integration.py` (existing 14, leicht migriert)

C6-Tests bleiben weitgehend, nur `_block_worker_boundaries`-Helfer wird gestrichen.
Methoden-API von OmniCQ (`start`, `stop`, `pause`, `resume_after_qso`, `is_active`,
`is_paused`) bleibt gleich. Erwartung: 14 Tests grün ohne Code-Änderung.

### Field-Test (Mike, vor Push) — V3 §6 17-Punkte-Plan F1-F17 unverändert

---

## 7. Atomare Commits (V5-Plan)

| C# | Inhalt | Files |
|---|---|---|
| **C9** | Refactor `core/omni_cq.py` Worker→Signal + alte Worker-Tests löschen + neue Signal-Tests | core/omni_cq.py, tests/test_omni_cq_worker.py (gelöscht), tests/test_omni_cq_signal.py (NEU), tests/test_omni_cq_integration.py (Boundary-Mock raus), ui/mw_cycle.py (1 Zeile Connect) |
| **C10** | Doku (HISTORY+HANDOFF+CLAUDE+Memory) | HISTORY.md, HANDOFF.md (beide), CLAUDE.md (beide), Memory-Update |

(2 atomare Commits — V5 ist 1 Modul-Refactor + Doku, kein Multi-File-Refactor wie P4.OMNI-NEUBAU C1-C8.)

**Test-Aufruf nach C9:**
```bash
cd "/Users/mikehammerer/Documents/KI N8N Projekte/FT8/SimpleFT8"
QT_QPA_PLATFORM=offscreen ./venv/bin/python3 -m pytest tests/ -q
```
Erwartung: Tests 1026 → ~1010 grün (-37 Worker + +22 Signal + 14 Integration unverändert = -1 netto).

---

## 8. Out-of-Scope

- ❌ Änderungen an `core/encoder.py` (atomare API ist fertig, C3)
- ❌ Änderungen an `core/qso_state.py` (kein `cq_mode`-Hack)
- ❌ Änderungen am Listener-Pfad in `mw_cycle.on_message_decoded` (C6)
- ❌ Änderungen am Hunt-Pfad — `qso_state.start_qso` bleibt
- ❌ Frequenz-Recheck zur Laufzeit
- ❌ 80-Cycles-Counter
- ❌ `cycle_tick`-basierter Pretrigger / QTimer
- ❌ Encoder-Queue für OMNI

---

## 9. Mike-Freigabe-Punkte

R1 hat alle 3 Klärungsfragen mit Variante A (KISS) bestätigt:
- ✅ Toggle-Start: IMMER Block 1
- ✅ Frequenz: 1× am Start, fest bis Stop
- ✅ Decoder-Blockade: kein Schutz, akzeptiert

**Letzter Mike-Sanity-Check:** Pattern korrekt? 5 Slots Block 1 + 5 Slots Block 2,
permanent alternierend, beim Toggle-Start IMMER Block 1, bei QSO-Resume
Block-Wahl nach last_was_even. Frequenz 1× setzen, fest.

---

## 10. APP_VERSION

`v0.96.0 → v0.96.1` (Patch-Bump: Bug-Fix Architektur-Refactor, kein neues Feature).

---

**Ende V3.**
