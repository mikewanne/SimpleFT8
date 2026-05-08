# P1.HUNT-SNR — V3 (Compact-fest, R1-freigegeben)

**Status:** V3 (Final-Plan nach R1).
**Workflow:** V1 → V2(12 Lessons) → R1(0 KRITISCH + 1 SOLLTE + 2 KOENNTE) → **V3** → Compact → Code.
**APP_VERSION:** 0.95.20 → **0.95.21**.
**Compact-fest:** Diese Datei enthaelt das vollstaendige Code-Skelett + Tests.

---

## 1. R1-Findings adressiert

| # | Severity | R1-Finding | V3-Loesung |
|---|---|---|---|
| 1 | 🟡 SOLLTE | `advance()` nutzt `_last_snr` direkt → ueberschreibt korrekten `our_snr` bei manuellem Force-Send | **In V3 mit aufgenommen** (gleiches Pattern, gleiches Bundle). Fix: `our_snr.lstrip("R")` zuerst, fallback `_last_snr`. +2 Tests. |
| 2 | 🟢 KOENNTE | Helper `_make_report(snr)` gegen Code-Duplikation | NICHT in V3 — KISS, nur 2 Stellen. |
| 3 | 🟢 KOENNTE | AutoHuntCandidate Default `-30 → -10` direkter | NICHT in V3 — bestehende Logik korrekt (R1 selbst „intransparent aber konsistent"). |

**Die 8 Pruefauftraege wurden alle ✅ gegruen-bewertet.** Plan freigegeben.

**Tests-Soll:** 992 → **1002 erwartet (+10: 8 Hunt-SNR + 2 advance-SNR)**.

---

## 2. Vollstaendiges Code-Skelett (Compact-fest)

### 2.1 Diff `core/qso_state.py` `start_qso()` (Z.246-282)

**Signatur erweitern + snr-Logik einsetzen:**

```python
def start_qso(self, their_call: str, their_grid: str = "",
              freq_hz: int = 0, their_snr: int | None = None):
    """QSO mit angeklickter Station starten. Bricht laufendes QSO ab.

    P1.HUNT-SNR (v0.95.21): their_snr ist station-spezifischer SNR
    aus FT8Message — verhindert dass _last_snr (vom letzten Decoder-
    Iterator-Schritt im Slot) den Report dominiert. Backward-compat:
    None → fallback auf _last_snr (alte Tests).
    """
    # P1.14 KP1: Reset bei JEDEM Nicht-IDLE-State (auch CQ_WAIT, da
    # dort _pending_reply gesetzt sein kann)
    if self.state != QSOState.IDLE:
        # ... unveraendert ...
        self._set_state(QSOState.IDLE)

    self._was_cq = self.cq_mode  # CQ-Modus merken fuer Resume nach Timeout

    self.qso = QSOData(
        their_call=their_call,
        their_grid=their_grid,
        freq_hz=freq_hz,
        start_time=time.time(),
        calls_made=1,
        max_calls=self.max_calls,
    )

    self._dbg.reset(their_call)
    # P1.HUNT-SNR (v0.95.21): explizite their_snr > _last_snr-Fallback.
    # Verhindert dass im selben Slot decodierte andere Stationen
    # _last_snr ueberschreiben und falsche Reports erzeugen.
    snr = their_snr if their_snr is not None else self._last_snr
    report = f"{snr:+03d}" if snr > -30 else "-10"
    self.qso.our_snr = report
    msg = f"{their_call} {self.my_call} {report}"
    self._dbg.log("START", f"Hunt: {their_call} auf {freq_hz}Hz, max {self.max_calls} Versuche")
    self._dbg.log("TX", f"Sende: '{msg}' (SNR={snr})")
    self._set_state(QSOState.TX_CALL)
    self.send_message.emit(msg)
```

### 2.2 Diff `core/qso_state.py` `advance()` (Z.651-658)

**WAIT_REPORT-Branch: `our_snr` zuerst, fallback `_last_snr`:**

```python
def advance(self):
    if self.state == QSOState.WAIT_REPORT and self.qso.their_snr:
        # P1.HUNT-SNR (v0.95.21): qso.our_snr wurde in start_qso bereits
        # mit station-spezifischem SNR gesetzt. R-Praefix wird hier hinzu-
        # gefuegt. Fallback _last_snr nur wenn our_snr leer (Edge-Case).
        if self.qso.our_snr:
            base = self.qso.our_snr.lstrip("R")  # ist heute ohne R
            report = f"R{base}"
        else:
            report = f"R{self._last_snr:+03d}" if self._last_snr > -30 else "R-10"
        self.qso.our_snr = report
        msg = f"{self.qso.their_call} {self.my_call} {report}"
        self._dbg.log("TX", f"advance() R-Report: '{msg}'")
        self._set_state(QSOState.TX_REPORT)
        self.send_message.emit(msg)

    elif self.state == QSOState.WAIT_RR73:
        # ... unveraendert ...

    elif self.state == QSOState.WAIT_73:
        # ... unveraendert ...
```

**Hinweis:** `start_qso` setzt `our_snr` ohne R-Praefix (zb. „-18"),
`advance()` haengt R-Praefix vor. `_process_cq_reply` Z.236-242 setzt
`our_snr` MIT R-Praefix bei `is_report+nicht-r` — `lstrip("R")` ist
defensiv (mehrfaches R wird verhindert).

### 2.3 Diff `ui/mw_qso.py:138` Hunt-Klick

```python
self.qso_sm.start_qso(
    their_call=msg.caller,
    their_grid=msg.grid_or_report if msg.is_grid else "",
    freq_hz=msg.freq_hz,
    their_snr=msg.snr,  # P1.HUNT-SNR (v0.95.21)
)
```

### 2.4 Diff `ui/mw_cycle.py:562` Auto-Hunt

```python
self.qso_sm.start_qso(
    their_call=_candidate.call,
    their_grid=_candidate.grid,
    freq_hz=_candidate.freq_hz,
    their_snr=_candidate.snr,  # P1.HUNT-SNR (v0.95.21)
)
```

### 2.5 Diff `main.py` APP_VERSION

```python
APP_VERSION = "0.95.21"
```

---

## 3. Tests (NEU `tests/test_p1_hunt_snr.py` — 10 Tests)

```python
"""Tests fuer P1.HUNT-SNR (v0.95.21).

Hunt-Klick + Auto-Hunt nutzen station-spezifischen SNR aus FT8Message
statt _last_snr. Plus advance() liest qso.our_snr statt _last_snr.
Hardware-frei, Qt-offscreen via conftest.
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from core.qso_state import QSOStateMachine, QSOState  # noqa: E402


# ── start_qso(): their_snr ueberschreibt _last_snr ──────────────────


def _new_sm(my_call: str = "DA1MHH", my_grid: str = "JN58") -> QSOStateMachine:
    sm = QSOStateMachine(my_call, my_grid)
    sm._last_snr = -25  # bewusst „falscher" Wert um zu zeigen dass their_snr gewinnt
    return sm


def test_start_qso_uses_their_snr_when_provided():
    sm = _new_sm()
    sent = []
    sm.send_message.connect(lambda m: sent.append(m))
    sm.start_qso(their_call="EV81AB", their_grid="KN12", freq_hz=946,
                 their_snr=-18)
    assert sm.qso.our_snr == "-18"
    assert sent[-1] == "EV81AB DA1MHH -18"


def test_start_qso_falls_back_to_last_snr_when_none():
    sm = _new_sm()
    sm._last_snr = -12
    sent = []
    sm.send_message.connect(lambda m: sent.append(m))
    sm.start_qso(their_call="EV81AB", their_grid="KN12", freq_hz=946)
    # Backward-compat: kein their_snr → _last_snr=-12 gewinnt
    assert sm.qso.our_snr == "-12"
    assert sent[-1] == "EV81AB DA1MHH -12"


def test_start_qso_clamps_weak_snr():
    sm = _new_sm()
    sent = []
    sm.send_message.connect(lambda m: sent.append(m))
    sm.start_qso(their_call="EV81AB", their_grid="KN12", freq_hz=946,
                 their_snr=-99)
    assert sm.qso.our_snr == "-10"
    assert sent[-1] == "EV81AB DA1MHH -10"


def test_start_qso_zero_snr_not_treated_as_falsy():
    """Edge-Case: their_snr=0 muss als gueltiger Wert behandelt werden."""
    sm = _new_sm()
    sm._last_snr = -25  # falscher Wert, soll NICHT gewinnen
    sent = []
    sm.send_message.connect(lambda m: sent.append(m))
    sm.start_qso(their_call="EV81AB", their_grid="KN12", freq_hz=946,
                 their_snr=0)
    assert sm.qso.our_snr == "+00"


def test_start_qso_positive_snr():
    sm = _new_sm()
    sent = []
    sm.send_message.connect(lambda m: sent.append(m))
    sm.start_qso(their_call="EV81AB", their_grid="KN12", freq_hz=946,
                 their_snr=15)
    assert sm.qso.our_snr == "+15"


def test_multi_decode_slot_uses_clicked_station_snr():
    """Mike's Field-Test: 3 Stationen im Slot, Klick auf mittlere SNR.

    Decoder iteriert -15, -18, -23 → _last_snr=-23. Klick auf -18.
    Report MUSS -18 sein, nicht -23 (alter Bug) oder -15.
    """
    sm = _new_sm()
    # Simulate Decoder-Iterator-Update
    sm.set_last_snr(-15)
    sm.set_last_snr(-18)
    sm.set_last_snr(-23)  # zuletzt iteriert
    assert sm._last_snr == -23
    sent = []
    sm.send_message.connect(lambda m: sent.append(m))
    # Mike klickt auf mittlere Station (msg.snr=-18)
    sm.start_qso(their_call="EV81AB", their_grid="KN12", freq_hz=946,
                 their_snr=-18)
    # Report station-spezifisch, NICHT _last_snr
    assert sm.qso.our_snr == "-18"
    assert sent[-1] == "EV81AB DA1MHH -18"


def test_our_snr_persisted_in_qso_data():
    sm = _new_sm()
    sm.start_qso(their_call="EV81AB", their_grid="KN12", freq_hz=946,
                 their_snr=-18)
    # Konsumenten (Logbuch ADIF, qso_panel) lesen qso.our_snr
    assert sm.qso.our_snr == "-18"
    assert sm.qso.their_call == "EV81AB"


def test_start_qso_during_active_qso_resets_pendings():
    """Backward-compat: start_qso bei nicht-IDLE-State macht Reset."""
    sm = _new_sm()
    sm.start_qso(their_call="OLD", their_snr=-15)
    sm._pending_reply = MagicMock()
    sm._pending_hunt_reply = MagicMock()
    sm._pending_rr73 = MagicMock()
    # Neuer Hunt → Pendings resettet
    sm.start_qso(their_call="NEW", their_snr=-20)
    assert sm._pending_reply is None
    assert sm._pending_hunt_reply is None
    assert sm._pending_rr73 is None
    assert sm.qso.our_snr == "-20"
    assert sm.qso.their_call == "NEW"


# ── advance(): nutzt qso.our_snr statt _last_snr ────────────────────


def test_advance_uses_our_snr_not_last_snr():
    """P1.HUNT-SNR R1-SOLLTE: advance() darf nicht _last_snr nehmen
    wenn qso.our_snr schon korrekt gesetzt ist.

    Szenario: Hunt mit -18 gestartet, dann decodierte starke Station
    setzt _last_snr=-5. Manuelles advance() muss R-18 senden, nicht R-5.
    """
    sm = _new_sm()
    sm.start_qso(their_call="EV81AB", their_grid="KN12", freq_hz=946,
                 their_snr=-18)
    sm._set_state(QSOState.WAIT_REPORT)
    sm.qso.their_snr = "-12"  # advance-Pre-Cond: their_snr existiert
    # Andere Station wurde decodiert mit starkem Signal
    sm.set_last_snr(-5)
    sent = []
    sm.send_message.connect(lambda m: sent.append(m))
    sm.advance()
    # advance() nutzt qso.our_snr=-18 (nicht _last_snr=-5)
    assert sm.qso.our_snr == "R-18"
    assert sent[-1] == "EV81AB DA1MHH R-18"


def test_advance_falls_back_to_last_snr_when_our_snr_empty():
    """Edge-Case: our_snr leer → advance() nutzt _last_snr (Backward-compat)."""
    sm = _new_sm()
    sm.start_qso(their_call="EV81AB", their_snr=-18)
    sm._set_state(QSOState.WAIT_REPORT)
    sm.qso.their_snr = "-12"
    sm.qso.our_snr = ""  # explizit leer machen
    sm.set_last_snr(-7)
    sent = []
    sm.send_message.connect(lambda m: sent.append(m))
    sm.advance()
    # Fallback auf _last_snr=-7
    assert sm.qso.our_snr == "R-07"
    assert sent[-1] == "EV81AB DA1MHH R-07"
```

**Hinweis:** Tests laufen ohne Qt — `QSOStateMachine` ist QObject aber
`send_message`-Signal funktioniert mit normalem Python-Thread.

---

## 4. Implementations-Reihenfolge (nach Compact)

1. **Files lesen** (Verifikation):
   - `prompts/p1_hunt_snr_v3.md` (diese Datei)
   - `core/qso_state.py:246-282` (start_qso) + `:651-680` (advance)
   - `ui/mw_qso.py:75-164` (_on_station_clicked)
   - `ui/mw_cycle.py:541-566` (_run_auto_hunt)
2. **`core/qso_state.py` Diff 2.1** — `start_qso` Signatur + snr-Logik.
3. **`core/qso_state.py` Diff 2.2** — `advance()` WAIT_REPORT-Branch.
4. **`ui/mw_qso.py` Diff 2.3** — Hunt-Klick `their_snr=msg.snr`.
5. **`ui/mw_cycle.py` Diff 2.4** — Auto-Hunt `their_snr=_candidate.snr`.
6. **`main.py`** — APP_VERSION 0.95.20 → 0.95.21.
7. **NEU `tests/test_p1_hunt_snr.py`** — 10 Tests aus §3.
8. **Tests laufen:** `992 → 1002 erwartet gruen`.
9. **Bestehende Tests** muessen weiter gruen sein (Backward-compat-Beweis).
10. **Final-R1-Codereview:**
    ```bash
    echo "Reviewe P1.HUNT-SNR final-Code (v0.95.21).
    Hunt-Pfad + Auto-Hunt nutzen jetzt msg.snr/candidate.snr statt _last_snr.
    advance() WAIT_REPORT nutzt qso.our_snr (Konsistenz mit start_qso)." | \
    ./venv/bin/python3 tools/deepseek_review.py \
    core/qso_state.py ui/mw_qso.py ui/mw_cycle.py tests/test_p1_hunt_snr.py
    ```
11. **Atomare Commits — 2 Code + 1 Doku:**
    - Code-1: `P1.HUNT-SNR: start_qso their_snr-Param + advance()-Fix + 10 Tests`
    - Code-2: `P1.HUNT-SNR: mw_qso + mw_cycle Aufrufer + APP_VERSION 0.95.21`
    - Doku: `docs (P1.HUNT-SNR): HISTORY+HANDOFF+CLAUDE+TODO+Memory`
12. **Doku-Updates** (HISTORY + HANDOFF beide Pfade + CLAUDE beide
    Pfade + Memory ✅).
13. **Lessons-Learned** (Memory: `feedback_partial_fix_check_other_paths.md`
    — bei P1.X-Bug-Fixes immer pruefen ob alle Pfade der gleichen Klasse
    abgedeckt sind, nicht nur der akut beobachtete).

---

## 5. Akzeptanz-Checkliste (final)

```
- [ ] start_qso(their_snr=-18) → our_snr="-18", TX "EV81AB DA1MHH -18"
- [ ] start_qso ohne their_snr → fallback auf _last_snr (Backward-compat)
- [ ] start_qso(their_snr=0) → our_snr="+00" (None-Schutz)
- [ ] start_qso(their_snr=-99) → "-10" clamp (gleiches Verhalten wie heute)
- [ ] mw_qso _on_station_clicked: their_snr=msg.snr durchgereicht
- [ ] mw_cycle _run_auto_hunt: their_snr=_candidate.snr durchgereicht
- [ ] advance() WAIT_REPORT: nutzt qso.our_snr (R-Praefix) statt _last_snr
- [ ] advance() Backward-compat: leeres our_snr → fallback _last_snr
- [ ] APP_VERSION 0.95.21
- [ ] Tests gesamt: 992 → 1002 gruen (+10)
- [ ] Bestehende Tests bleiben gruen (Backward-compat-Beweis)
- [ ] Final-R1 ohne KP-Findings (oder kleine sofort-fixbar)
- [ ] HISTORY/HANDOFF/CLAUDE updated (beide Pfade)
- [ ] 2 Code-Commits + 1 Doku-Commit
- [ ] Memory ✅ + neue Lesson Partial-Fix-Check
```

---

## 6. Risiken & Notbremse

- **Test-Bruch bei alten Backward-compat-Tests:** kontern via Default-None.
  Verifikation: 992 bestehende Tests muessen weiter gruen sein.
- **`_process_cq_reply`-Pfad NICHT betroffen** — nutzt schon msg.snr
  seit v0.95.18. Konsistenz gegeben.
- **Logbuch ADIF `<RST_SENT>`-Konsistenz:** wird durch Fix automatisch
  korrekt (`our_snr` korrekt → ADIF korrekt).
- **Notbremse:** Falls Field-Test einen Edge-Case zeigt, kann
  `their_snr=None` weiterhin `_last_snr`-Fallback nutzen (kein Total-Bruch).

---

## 7. Field-Test-Plan

1. App starten, FT8 20m oder 40m.
2. Slot mit ≥3 Stationen verschieden SNR abwarten (typisch in Tagesstunden).
3. Klick auf Station mit MITTLEREM SNR (zB nicht die staerkste, nicht
   die schwaechste).
4. QSO-Panel pruefen: erstes TX-Frame `<call> DA1MHH <SNR>` muss den
   exakt gleichen SNR zeigen wie die `dB`-Spalte im RX-Panel fuer diese
   Station.
5. Reproduktion von Mike's 13:57-Screenshot: 3+ Stationen, Klick auf
   mittlere → Diskrepanz weg.
6. Mike's „passt" → Push freigegeben.

**Auto-Hunt-Test (sekundaer):**
- Auto-Hunt aktivieren, ein paar Zyklen laufen lassen.
- QSO-Panel zeigt Hunt-Reports → SNR-Werte muessen `_candidate.snr`
  entsprechen (nicht `_last_snr`).

---

## 8. Lessons-Learned (Memory-Vorschlaege)

1. **Bei P1.X-Bug-Fix-Patterns immer pruefen ob alle Pfade gleicher
   Klasse mit-gefixt werden:** v0.95.18 fixte `_process_cq_reply` aber
   `start_qso` blieb explizit — Mike's Field-Test 3 Wochen spaeter zeigt
   den gleichen Bug im Hunt-Pfad. Memory: `feedback_partial_fix_check_
   other_paths.md`.
2. **R1-SOLLTE-Findings nicht reflexartig in Followup-Tickets** abschieben:
   wenn der Fix im selben Commit-Bundle KISS ist (gleicher Pattern,
   gleiche Tests) → mitnehmen. Kostete hier +2 Tests, ~5 Zeilen Diff.

---

**V3-Ende. Bereit fuer Compact + Code.**
