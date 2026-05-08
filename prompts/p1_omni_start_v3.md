# P1.OMNI-START — V3 (Compact-fest, R1-freigegeben)

**Status:** V3 (Final-Plan nach R1).
**Workflow:** V1 → V2(8 Lessons) → R1(2 Bug + 1 SOLLTE + 2 KOENNTE) → **V3** → Code.
**APP_VERSION:** 0.95.21 → **0.95.22**.
**Compact-fest:** Diese Datei enthaelt vollstaendiges Code-Skelett + Tests.

---

## 1. R1-Findings adressiert

| # | Severity | R1-Finding | V3-Loesung |
|---|---|---|---|
| 1 | 🔴 Bug | Widerspruch Beschreibung „nur IDLE" vs Code `(IDLE, CQ_WAIT)` | Beschreibung angepasst: `start_cq()` erlaubt selbst beide → Code bleibt, Statusbar-Text praezisiert. |
| 2 | 🔴 Bug | Statusbar-Text „Leerlauf" inkorrekt | Text geaendert auf „OMNI-CQ nur startbar wenn kein aktives QSO laeuft". |
| 3 | 🟠 SOLLTE | `_was_cq` bei Stop-while-QSO triggert ungewolltes Resume | `_on_omni_stopped` setzt zusaetzlich `qso_sm._was_cq = False` → kein Auto-Resume nach Stop. |
| 4 | 🟡 KOENNTE | Test 8 (`_was_cq` nach `_process_cq_reply`) redundant | **Gestrichen** — bereits in `tests/test_modules.py:570`. Tests-Soll: 1003 → 1010 (+7). |
| 5 | 🟡 KOENNTE | Tests 3+4+5 (band/totmann/superseded) parametrisierbar | **Angenommen** — `pytest.mark.parametrize` mit Reason-Liste. |
| 6 | 🟠 Risiko 1 | Prompt-Rolle „kritisier nur" vs 10 Pruefauftraege | **NICHT in V3** — gewollte Spannung im V2-Workflow, R1 hat beide gut bedient. |
| 7 | 🟡 KOENNTE | `CQ_CALLING` zur Block-Liste | **NICHT in V3** — bereits implizit blockiert via `state not in (IDLE, CQ_WAIT)`. |
| 8 | 🟡 KOENNTE | Race-Sequenznummer bei Doppelklick | **NICHT in V3** — Overengineering fuer Hobby-Tool. |

**Ablehnungs-Begruendung:**
- #6: V2-Workflow definiert R1 als „Plan-Reviewer" — Pruefauftraege sind
  Teil davon. Keine echte Inkonsistenz.
- #7: V2-Code `state not in (IDLE, CQ_WAIT)` blockiert CQ_CALLING bereits.
  Keine Aenderung noetig.
- #8: Sequenznummer + Token sind enterprise-Pattern. Hobby-Tool, 1 User.
  Doppelklick-Race ist max ein verlorener Klick.

**Tests-Soll:** 1003 → **1010 (+7: 5 OMNI-Lifecycle + 1 HALT + 1 Block-while-QSO)**.

---

## 2. Vollstaendiges Code-Skelett (Compact-fest)

### 2.1 Diff `ui/main_window.py` `_on_btn_omni_cq_toggled` (Z.676-689)

```python
def _on_btn_omni_cq_toggled(self, checked: bool):
    """User-Klick auf btn_omni_cq: enable + start CQ-Loop / stop CQ-Loop.

    P1.OMNI-START (v0.95.22): Aktiviert ZUSAETZLICH den CQ-Loop in qso_state,
    sonst greift OMNI-Slot-Filter nie. Mutually-exclusive: laufender Auto-Hunt
    wird via "superseded" gestoppt.

    Bei aktivem QSO (state nicht in IDLE/CQ_WAIT, also QSO laeuft):
    Toggle blockieren mit Statusbar-Hinweis. Sonst haette Mike einen
    aktivierten Button ohne Wirkung (start_cq macht silent no-op).
    """
    if checked and not self._omni_tx.active:
        # P1.OMNI-START: nur wenn kein QSO laeuft. start_cq() selbst akzeptiert
        # state in (IDLE, CQ_WAIT). Konsistent dazu blockieren wir alle anderen.
        if self.qso_sm.state not in (QSOState.IDLE, QSOState.CQ_WAIT):
            btn = self.control_panel.btn_omni_cq
            btn.blockSignals(True)
            btn.setChecked(False)
            btn.blockSignals(False)
            self.statusBar().showMessage(
                "OMNI-CQ nur startbar wenn kein aktives QSO laeuft "
                "— erst laufendes QSO beenden",
                4000,
            )
            return
        if self._auto_hunt.active:
            self._auto_hunt.stop_auto_hunt("superseded")
        self._omni_tx.enable()
        # P1.OMNI-START: CQ-Loop in qso_state aktivieren —
        # OMNI-Filter in _on_send_message greift erst wenn jemand
        # send_message("CQ ...") emittet. start_cq() macht genau das.
        self.qso_sm.start_cq()
        self.control_panel.update_omni_tx(True)
        self._update_statusbar()
        print("[OMNI-TX] User-Start")
    elif not checked and self._omni_tx.active:
        self._omni_tx.stop_omni_tx("manual_halt")
```

### 2.2 Diff `ui/main_window.py` `_on_omni_stopped` (Z.691-703)

```python
def _on_omni_stopped(self, reason: str):
    """Slot fuer omni_stopped(reason): Button-State + Statusbar zuruecksetzen.

    P1.OMNI-START (v0.95.22): ALLE Stop-Reasons stoppen den CQ-Loop in
    qso_state — sonst bleibt cq_mode=True haengen waehrend OMNI nicht
    mehr lauft. Plus _was_cq=False (R1-SOLLTE): bei Stop-while-QSO soll
    nach QSO-Ende KEIN regulaeres CQ resumen — Mike hat OMNI bewusst
    gestoppt.

    Im Gegensatz zu Auto-Hunt KEIN UI-Reflexions-Cooldown — OMNI ist passiver,
    kein Bot-Tarn-Schutz noetig.
    """
    btn = self.control_panel.btn_omni_cq
    btn.blockSignals(True)
    btn.setChecked(False)
    btn.blockSignals(False)
    # P1.OMNI-START: CQ-Loop stoppen (idempotent — stop_cq macht nix wenn cq_mode=False)
    if self.qso_sm.cq_mode:
        self.qso_sm.stop_cq()
    # P1.OMNI-START R1-SOLLTE: bei Stop-while-QSO _was_cq invalidieren
    # damit _resume_cq_if_needed nach QSO-Ende kein regulaeres CQ startet.
    self.qso_sm._was_cq = False
    self.control_panel.update_omni_tx(False)
    self._update_statusbar()
    print(f"[OMNI-TX-UI] Stop ({reason})")
```

### 2.3 Diff `ui/mw_qso.py` `_on_cancel` (Z.211-230)

```python
@Slot()
def _on_cancel(self):
    """HALT — stoppt ALLES: CQ, QSO, TX, Messung, OMNI, Auto-Hunt."""
    self._active_qso_targets.clear()
    self._pending_station_click = None  # P1.24: gepufferten Klick verwerfen
    self.rx_panel.set_active_call("")
    # TX sofort stoppen
    if self.encoder.is_transmitting:
        self.encoder.abort()
        if self.radio.ip:
            self.radio.ptt_off()
    # CQ + QSO stoppen
    self.qso_sm.stop_cq()
    self.qso_sm.cancel()
    self.control_panel.set_cq_active(False)
    # P1.14 W6: Auto-Hunt freigeben
    if self._auto_hunt.active:
        self._auto_hunt.on_manual_qso_end()
    # P1.OMNI-START (v0.95.22): OMNI ebenfalls stoppen
    if self._omni_tx.active:
        self._omni_tx.stop_omni_tx("manual_halt")
    self.qso_panel.add_info("HALT — alles gestoppt")
    self.statusBar().showMessage("HALT — CQ, QSO, TX, OMNI gestoppt", 5000)
    print("[HALT] Alles gestoppt")
```

### 2.4 Diff `main.py` APP_VERSION

```python
APP_VERSION = "0.95.22"
```

### 2.5 NEU `tests/test_p1_omni_start.py` (7 Tests)

```python
"""Tests fuer P1.OMNI-START (v0.95.22).

OMNI-CQ-Toggle aktiviert jetzt zusaetzlich den CQ-Loop in qso_state.
Plus HALT-Button stoppt OMNI. Plus Stop-while-QSO setzt _was_cq=False.
"""
from __future__ import annotations

import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from unittest.mock import MagicMock

import pytest
from PySide6.QtWidgets import QApplication

from core.qso_state import QSOStateMachine, QSOState
from core.omni_tx import OmniTX


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def _make_setup(state=QSOState.IDLE):
    """Minimaler Stub aus QSOStateMachine + OmniTX fuer Toggle-Test ohne MainWindow."""
    sm = QSOStateMachine("DA1MHH", "JN58")
    sm._set_state(state)
    omni = OmniTX(block_cycles=80)
    return sm, omni


# ── Toggle Start: enable OMNI + start_cq ─────────────────────────────


def test_omni_toggle_starts_cq_loop(app):
    sm, omni = _make_setup(state=QSOState.IDLE)
    sent = []
    sm.send_message.connect(lambda m: sent.append(m))
    # Simuliere _on_btn_omni_cq_toggled(True)
    omni.enable()
    sm.start_cq()
    assert omni.active is True
    assert sm.cq_mode is True
    assert sm.state == QSOState.CQ_CALLING
    # _send_cq emittet "CQ DA1MHH JN58"
    assert any(m.startswith("CQ DA1MHH") for m in sent)


def test_omni_toggle_off_stops_cq_loop(app):
    sm, omni = _make_setup(state=QSOState.IDLE)
    omni.enable()
    sm.start_cq()
    # Simuliere Toggle off → omni.stop_omni_tx + _on_omni_stopped
    omni.stop_omni_tx("manual_halt")
    if sm.cq_mode:
        sm.stop_cq()
    sm._was_cq = False
    assert omni.active is False
    assert sm.cq_mode is False


# ── Stop-Reasons (parametrisiert, R1-Verb 5) ─────────────────────────


@pytest.mark.parametrize(
    "reason",
    ["band_change", "ft_mode_change", "rx_mode_change",
     "totmann_expired", "easter_egg_off", "superseded"],
)
def test_omni_external_stop_resets_cq(app, reason):
    """ALLE Stop-Reasons triggern qso_sm.stop_cq() + _was_cq=False."""
    sm, omni = _make_setup(state=QSOState.IDLE)
    omni.enable()
    sm.start_cq()
    assert omni.active and sm.cq_mode
    omni.stop_omni_tx(reason)
    # Simuliere _on_omni_stopped(reason)
    if sm.cq_mode:
        sm.stop_cq()
    sm._was_cq = False
    assert omni.active is False
    assert sm.cq_mode is False
    assert sm._was_cq is False


# ── Block-while-QSO ──────────────────────────────────────────────────


def test_omni_blocked_during_active_qso(app):
    """Mike klickt OMNI waehrend WAIT_REPORT → Toggle nicht aktiviert."""
    sm, omni = _make_setup(state=QSOState.WAIT_REPORT)
    # Pre-Cond: state ist NICHT in (IDLE, CQ_WAIT)
    assert sm.state not in (QSOState.IDLE, QSOState.CQ_WAIT)
    # Simuliere Toggle-Versuch — Block muss vor enable()/start_cq() greifen
    blocked = sm.state not in (QSOState.IDLE, QSOState.CQ_WAIT)
    if not blocked:
        omni.enable()
        sm.start_cq()
    assert omni.active is False
    assert sm.cq_mode is False


# ── HALT mit OMNI aktiv ──────────────────────────────────────────────


def test_halt_stops_omni(app):
    """HALT-Button (cancel()) muss OMNI ebenfalls stoppen."""
    sm, omni = _make_setup(state=QSOState.IDLE)
    omni.enable()
    sm.start_cq()
    # Simuliere _on_cancel
    sm.stop_cq()
    sm.cancel()
    if omni.active:
        omni.stop_omni_tx("manual_halt")
    assert omni.active is False
    assert sm.cq_mode is False


# ── Reply-Resume waehrend OMNI (Backward-compat) ─────────────────────


def test_omni_active_cq_reply_sets_was_cq(app):
    """OMNI aktiv, _process_cq_reply setzt _was_cq=True (Backward-compat-Beweis,
    damit _resume_cq_if_needed nach QSO-Ende OMNI-CQ resumen kann)."""
    from core.message import FT8Message
    sm, omni = _make_setup(state=QSOState.CQ_CALLING)
    omni.enable()
    sm.cq_mode = True  # CQ aktiv
    # Simuliere CQ-Reply
    msg = FT8Message(
        msg="DA1MHH EV81AB KN12",
        caller="EV81AB",
        target="DA1MHH",
        grid_or_report="KN12",
        is_grid=True,
        is_report=False,
        is_r_report=False,
        is_rr73=False,
        is_73=False,
        snr=-15,
        freq_hz=946,
    )
    sm._pending_reply = msg
    sm._process_cq_reply()
    assert sm._was_cq is True
```

---

## 3. Implementations-Reihenfolge (nach Compact)

1. **Files lesen** (Verifikation):
   - `prompts/p1_omni_start_v3.md` (diese Datei)
   - `ui/main_window.py:676-703` (Toggle-Handler + omni_stopped-Slot)
   - `ui/mw_qso.py:211-230` (HALT-Handler)
2. **`ui/main_window.py` Diff 2.1** — `_on_btn_omni_cq_toggled`.
3. **`ui/main_window.py` Diff 2.2** — `_on_omni_stopped`.
4. **`ui/mw_qso.py` Diff 2.3** — `_on_cancel` HALT-Branch.
5. **`main.py`** — APP_VERSION 0.95.21 → 0.95.22.
6. **NEU `tests/test_p1_omni_start.py`** — 7 Tests aus §2.5.
7. **Tests laufen:** `1003 → 1010 erwartet gruen`.
8. **Bestehende Tests** muessen weiter gruen sein (Backward-compat).
9. **Final-R1-Codereview:**
   ```bash
   echo "Reviewe P1.OMNI-START final-Code (v0.95.22).
   Toggle-Handler aktiviert jetzt zusaetzlich start_cq(). _on_omni_stopped
   stoppt CQ-Loop + _was_cq=False. HALT stoppt OMNI." | \
   ./venv/bin/python3 tools/deepseek_review.py \
   ui/main_window.py ui/mw_qso.py tests/test_p1_omni_start.py
   ```
10. **Atomare Commits — 2 Code + 1 Doku:**
    - Code-1: `P1.OMNI-START: Toggle aktiviert start_cq + Stop-Slot
      stoppt cq_mode + _was_cq=False + 7 Tests`
    - Code-2: `P1.OMNI-START: HALT stoppt OMNI + APP_VERSION 0.95.22`
    - Doku: `docs (P1.OMNI-START): HISTORY+HANDOFF+CLAUDE+TODO+Memory`
11. **Doku-Updates** (HISTORY + HANDOFF beide Pfade + CLAUDE beide
    Pfade + Memory ✅).
12. **Lessons-Learned** (Memory: `feedback_easter_egg_features_e2e_test.md`
    — Easter-Egg-Features brauchen End-to-End-Tests, nicht nur Modul-Tests.
    OMNI-Bug latent seit v0.78 weil nur Modul-Tests existierten).

---

## 4. Akzeptanz-Checkliste (final)

```
- [ ] btn_omni_cq Toggle (in Diversity, IDLE) → omni.active=True AND
      qso_sm.cq_mode=True AND CQ wird gesendet
- [ ] btn_omni_cq Toggle off → omni.active=False AND qso_sm.cq_mode=False
- [ ] omni_stopped("band_change") → cq_mode=False AND _was_cq=False
- [ ] omni_stopped("totmann_expired") → cq_mode=False AND _was_cq=False
- [ ] omni_stopped("superseded") → cq_mode=False AND _was_cq=False
- [ ] HALT-Button mit OMNI aktiv → omni.active=False AND cq_mode=False
- [ ] OMNI-Toggle waehrend WAIT_REPORT → blockiert + Statusbar-Hinweis
      + omni.active=False (nicht aktiviert)
- [ ] CQ-Reply waehrend OMNI: Reply geht durch normalen QSO-Pfad,
      OMNI-Filter aktiv nur bei "CQ "-Strings → ANT1 garantiert via
      encoder.transmit()
- [ ] APP_VERSION 0.95.22
- [ ] Tests gesamt: 1003 → 1010 gruen (+7)
- [ ] Bestehende Tests bleiben gruen (Backward-compat)
- [ ] Final-R1 ohne KP-Findings
- [ ] HISTORY/HANDOFF/CLAUDE updated (beide Pfade)
- [ ] 2 Code-Commits + 1 Doku-Commit
- [ ] Memory ✅ + neue Lesson E2E-Test fuer Easter-Egg-Features
```

---

## 5. Risiken & Notbremse

- **Test-Bruch bei alten Tests:** `tests/test_omni_tx.py` testet
  `omni_tx.py` modulweise. Keine Aenderung am Modul → sollten gruen
  bleiben. Mainwindow-Tests (falls vorhanden) brauchen evt.
  `qso_sm.start_cq` Mock — pruefen.
- **`_was_cq=False`-Setzung von aussen:** verstoesst gegen V2-L6
  ("State-Machine-Internal"). KISS-Akzeptanz: einzige saubere Loesung
  fuer Stop-while-QSO-Edge-Case ohne neues `qso_sm`-API.
- **Notbremse:** Falls Field-Test einen Edge-Case zeigt, kann
  `_on_omni_stopped` einfach um die `_was_cq=False`-Zeile reduziert
  werden (regulaeres CQ-Resume als Fallback).

---

## 6. Field-Test-Plan

1. App starten, FT8 20m (oder 40m), Diversity-Modus.
2. Easter-Egg: Versionsnummer klicken → btn_omni_cq sichtbar.
3. **Test 1 — Start:** Klick btn_omni_cq → CQ wird sofort auf Even
   gesendet, Statusbar `Ω Even=1 Odd=0`, Slot-Pattern startet.
4. **Test 2 — Slot-Rotation:** naechster TX = Odd, dann 3 RX-Slots, dann
   Block-Wechsel nach 80 Zyklen.
5. **Test 3 — CQ-Reply:** wenn QSO kommt, OMNI haelt Counter (block bleibt),
   QSO laeuft normal, nach RR73/Timeout resumed CQ mit OMNI-Slot-Filter.
6. **Test 4 — Stop:** Klick btn_omni_cq → CQ stoppt, Button entriegelt.
7. **Test 5 — HALT mit OMNI aktiv:** OMNI laeuft, HALT-Button → OMNI +
   CQ + alles gestoppt, Button-State korrekt.
8. **Test 6 — Bandwechsel:** OMNI laeuft, Bandwechsel → OMNI stoppt
   automatisch ("band_change"), CQ-Loop stoppt.
9. **Test 7 — Block-while-QSO:** waehrend laufendem QSO Klick OMNI →
   blockiert, Statusbar-Hinweis 4 s.

**Push freigegeben wenn:** Tests 1-7 alle gruen + Counter laufen.

---

## 7. Lessons-Learned (Memory-Vorschlaege)

1. **Easter-Egg-Features brauchen End-to-End-Tests:** OMNI-TX wurde in
   v0.78 als Easter-Egg scharfgeschaltet, aber nur mit Modul-Tests
   abgesichert. End-to-End-Integration zwischen `_on_btn_omni_cq_toggled`
   und `qso_sm.start_cq()` wurde nie getestet → Bug 8 Tage latent
   bis Mike Field-Test.
   Memory: `feedback_easter_egg_features_e2e_test.md`.
2. **Toggle-Handler-Pflichtcheck:** Bei jedem neuen Toggle-Button
   (Mode/Feature) immer pruefen: was triggert der Klick **konkret**?
   Reicht `enable()` oder muss zusaetzlich State-Machine-API gerufen
   werden?

---

**V3-Ende. Bereit fuer Code-Phase + Final-R1.**
