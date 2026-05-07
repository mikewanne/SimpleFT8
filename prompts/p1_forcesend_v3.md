# P1.FORCESEND V3 — Final-Plan (Compact-fest, R1-freigegeben)

**Stand:** 2026-05-06.
**Workflow:** V1 → V2 → R1 ✅ („Plan freigegeben unter Bedingungen") → **V3** → Mike-Freigabe → Code.
**R1-Empfehlung:** „Plan freigegeben unter Bedingungen 1-5."
**Davon Bedingung 1 (KP-1) als Halluzination verworfen, andere übernommen.**

---

## 1. Mike's Use-Case (NICHT verhandelbar)

Bei stuck-Gegenstation (sendet immer Report statt RR73 → wir hängen
in WAIT_RR73; oder sendet kein 73 → wir hängen in WAIT_73) manuell
RR73 oder 73 senden können statt 3-Min-Timeout abwarten.

**Lösung:** Bestehender `btn_advance` wird state-aware:
- Label dynamisch je nach State
- Enabled-Logik um WAIT_73 ergänzt
- `advance()` in qso_state.py um WAIT_73-Branch ergänzt

**Keine neuen UI-Elemente** — KISS pur.

---

## 2. R1-Befund-Auswertung

| R1-Befund | Status | V3-Behandlung |
|---|---|---|
| KP-1: qso_complete fehlt bei Force-73 | **Halluzination** | Verworfen — `qso_complete.emit` läuft bereits in TX_RR73 (Z.444), WAIT_73 = „QSO schon geloggt" laut Z.60-Kommentar |
| KP-2: Initial-Refresh harmlos | OK | Nichts zu tun |
| KP-3: Flag-Reihenfolge VOR Send | **Übernommen** | `courtesy_73_sent = True` VOR `send_message.emit` |
| Diversity-Lock-Check in `_on_state_changed` | **Übernommen** | Defense-in-Depth, mw_radio.py-Setzen redundant aber harmlos |
| Label-Stil kompakt ohne Verb | **Übernommen** | „R+Report" / „RR73" / „73" / „Weiter →" |
| Tests-Coverage 10 | **Übernommen** | KP-1-Test entfällt (Halluzination), 10 Tests |

---

## 3. Konkrete Diffs (Compact-fest)

### Diff 1 — `core/qso_state.py:640-652` `advance()` Branch erweitern

```diff
     def advance(self):
         if self.state == QSOState.WAIT_REPORT and self.qso.their_snr:
             report = f"R{self._last_snr:+03d}" if self._last_snr > -30 else "R-10"
             self.qso.our_snr = report
             msg = f"{self.qso.their_call} {self.my_call} {report}"
             self._dbg.log("TX", f"advance() R-Report: '{msg}'")
             self._set_state(QSOState.TX_REPORT)
             self.send_message.emit(msg)

         elif self.state == QSOState.WAIT_RR73:
             msg = f"{self.qso.their_call} {self.my_call} RR73"
             self._set_state(QSOState.TX_RR73)
             self.send_message.emit(msg)
+
+        elif self.state == QSOState.WAIT_73:
+            # P1.FORCESEND (v0.95.12): manuelles 73 wenn Gegenstation
+            # kein 73 schickt. WAIT_73 = "QSO schon geloggt" (qso_complete
+            # wurde in TX_RR73 emittiert), wir senden Hoeflichkeits-73.
+            # Flag VOR send (R1 KP-3, asynchron-Schutz).
+            self.qso.courtesy_73_sent = True
+            msg = f"{self.qso.their_call} {self.my_call} 73"
+            self._dbg.log("TX", f"advance() Force-73: '{msg}'")
+            self._set_state(QSOState.TX_73_COURTESY)
+            self.send_message.emit(msg)
```

### Diff 2 — `ui/control_panel.py` neue Methode `set_advance_label`

In der `ControlPanel`-Klasse (nach bestehender Methode wie `set_rx_mode`
oder in der Naehe von `update_state`):

```python
def set_advance_label(self, state) -> None:
    """P1.FORCESEND: Label dynamisch je nach QSO-State.

    Mike's Hobby-UX: Button macht klar was gesendet wird.
    KISS: kompakt ohne Verb (Button-Klick-Kontext impliziert „senden").
    """
    from core.qso_state import QSOState
    labels = {
        QSOState.WAIT_REPORT: "R+Report",
        QSOState.WAIT_RR73: "RR73",
        QSOState.WAIT_73: "73",
    }
    self.btn_advance.setText(labels.get(state, "Weiter →"))
```

**Hinweis:** `QSOState`-Import lazy in der Methode (vermeidet Zirkular-
Import wenn ControlPanel früher geladen wird als qso_state).

### Diff 3 — `ui/mw_qso.py:208-234` `_on_state_changed` erweitern

```diff
     def _on_state_changed(self, state: QSOState):
         name = state.name
         self.control_panel.update_state(name)
         # ... [bisheriger Code unverändert] ...

         in_qso = state not in (
             QSOState.IDLE, QSOState.TIMEOUT,
             QSOState.CQ_CALLING, QSOState.CQ_WAIT,
         )
+        # P1.FORCESEND: Label dynamisch + WAIT_73 in Enabled-Liste +
+        # Diversity-Lock zusätzlich prüfen (R1-Empfehlung Defense-in-Depth)
+        diversity_locked = getattr(self, "_diversity_measuring", False)
+        self.control_panel.set_advance_label(state)
         self.control_panel.btn_advance.setEnabled(
-            state in (QSOState.WAIT_REPORT, QSOState.WAIT_RR73)
+            state in (QSOState.WAIT_REPORT, QSOState.WAIT_RR73, QSOState.WAIT_73)
             and not self.qso_sm.cq_mode
+            and not diversity_locked
         )
```

### Diff 4 — `tests/test_p1_forcesend.py` (NEU, 10 Tests)

```python
"""Tests fuer P1.FORCESEND — btn_advance state-aware + WAIT_73-Branch.

Mike-Use-Case 2026-05-06: bei stuck-Gegenstation manuell RR73 oder 73
senden statt 3-Min-Timeout abwarten. Bestehender btn_advance bekommt
3 Bug-Fixes (Label dynamisch, WAIT_73 in advance(), Enabled+Lock).
"""
from __future__ import annotations

import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication

from core.qso_state import QSOState, QSOStateMachine, QSOData
from ui.control_panel import ControlPanel


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def panel(app):
    return ControlPanel(callsign="DA1MHH")


# ── advance() WAIT_73-Branch (qso_state.py) ──────────────────────────


def test_advance_wait_73_sends_73():
    """advance() in WAIT_73 → emittet '<their> <me> 73'."""
    sm = QSOStateMachine(my_call="DA1MHH", my_grid="JO31")
    sm.qso = QSOData(their_call="DK5ON", start_time=0.0)
    sm._set_state(QSOState.WAIT_73)
    received = []
    sm.send_message.connect(lambda m: received.append(m))

    sm.advance()

    assert received == ["DK5ON DA1MHH 73"]
    assert sm.state == QSOState.TX_73_COURTESY


def test_advance_wait_73_sets_courtesy_flag():
    """advance() in WAIT_73 → setzt courtesy_73_sent=True (Doppel-Send-Schutz P1.10)."""
    sm = QSOStateMachine(my_call="DA1MHH", my_grid="JO31")
    sm.qso = QSOData(their_call="DK5ON", start_time=0.0)
    sm._set_state(QSOState.WAIT_73)

    sm.advance()

    assert sm.qso.courtesy_73_sent is True


def test_advance_wait_73_flag_set_before_send():
    """R1 KP-3: Flag muss VOR send_message gesetzt werden (asynchron-Schutz)."""
    sm = QSOStateMachine(my_call="DA1MHH", my_grid="JO31")
    sm.qso = QSOData(their_call="DK5ON", start_time=0.0)
    sm._set_state(QSOState.WAIT_73)
    flag_at_emit = []
    sm.send_message.connect(lambda m: flag_at_emit.append(sm.qso.courtesy_73_sent))

    sm.advance()

    assert flag_at_emit == [True]


def test_advance_other_states_unchanged():
    """advance() in IDLE/TX_*/etc. → keine Aenderung (Default-Pfad)."""
    sm = QSOStateMachine(my_call="DA1MHH", my_grid="JO31")
    received = []
    sm.send_message.connect(lambda m: received.append(m))

    for state in [QSOState.IDLE, QSOState.TIMEOUT, QSOState.CQ_CALLING]:
        sm._set_state(state)
        sm.advance()

    assert received == []


# ── set_advance_label (control_panel.py) ─────────────────────────────


def test_advance_label_default(panel):
    """state IDLE → Default-Label 'Weiter →'."""
    panel.set_advance_label(QSOState.IDLE)
    assert panel.btn_advance.text() == "Weiter →"


def test_advance_label_wait_report(panel):
    """state WAIT_REPORT → 'R+Report'."""
    panel.set_advance_label(QSOState.WAIT_REPORT)
    assert panel.btn_advance.text() == "R+Report"


def test_advance_label_wait_rr73(panel):
    """state WAIT_RR73 → 'RR73'."""
    panel.set_advance_label(QSOState.WAIT_RR73)
    assert panel.btn_advance.text() == "RR73"


def test_advance_label_wait_73(panel):
    """state WAIT_73 → '73'."""
    panel.set_advance_label(QSOState.WAIT_73)
    assert panel.btn_advance.text() == "73"


def test_advance_label_unknown_state_default(panel):
    """state TX_RR73 (nicht in mapping) → Default 'Weiter →'."""
    panel.set_advance_label(QSOState.TX_RR73)
    assert panel.btn_advance.text() == "Weiter →"


def test_advance_label_returns_to_default(panel):
    """Nach WAIT_73 → IDLE → Label zurueck auf Default."""
    panel.set_advance_label(QSOState.WAIT_73)
    panel.set_advance_label(QSOState.IDLE)
    assert panel.btn_advance.text() == "Weiter →"
```

---

## 4. Implementations-Reihenfolge (nach Compact)

1. **Files lesen:**
   - `prompts/p1_forcesend_v3.md` (diese Datei)
   - `core/qso_state.py:640-652` (`advance()`)
   - `ui/control_panel.py:899-908` (`btn_advance`)
   - `ui/mw_qso.py:208-237` (`_on_state_changed`)

2. **Diff 1** anwenden: `qso_state.py` WAIT_73-Branch + Flag VOR Send.

3. **Diff 2** anwenden: `control_panel.py` `set_advance_label()`.

4. **Diff 3** anwenden: `mw_qso.py` Enabled-Liste + Lock-Check + Label-Call.

5. **Diff 4** anwenden: `tests/test_p1_forcesend.py` NEU.

6. **Tests laufen:** `QT_QPA_PLATFORM=offscreen ./venv/bin/python3 -m pytest tests/ -q`
   → erwartet 851 grün (841 + 10 neu).

7. **Final-R1-Codereview** (Skill Schritt 5b):
   ```bash
   echo "Reviewe P1.FORCESEND v0.95.12 — qso_state.py + control_panel.py + \
   mw_qso.py + test_p1_forcesend.py. Korrektheit, KISS, Race-Conditions?" | \
   ./venv/bin/python3 tools/deepseek_review.py core/qso_state.py \
   ui/control_panel.py ui/mw_qso.py tests/test_p1_forcesend.py
   ```

8. **APP_VERSION** in `main.py` 0.95.11 → 0.95.12.

9. **Atomare Commits:**
   - Code+Tests: `P1.FORCESEND (v0.95.12): btn_advance state-aware + WAIT_73`
   - Doku: `docs (v0.95.12): P1.FORCESEND HISTORY+TODO+HANDOFF+CLAUDE`

10. **Doku-Updates** (Pflicht):
    - `HISTORY.md` Eintrag v0.95.12
    - `HANDOFF.md` beide Pfade
    - `CLAUDE.md` Header beide Pfade + Test-Count 851
    - `TODO.md` P1.FORCESEND als ERLEDIGT
    - Memory-Lesson optional

11. **Push** (NUR nach Mike-Freigabe).

12. **Lessons-Learned** (Skill Schritt 6 final).

---

## 5. Akzeptanz-Checkliste (final)

```
- [ ] qso_state.py:advance() WAIT_73-Branch
- [ ] courtesy_73_sent = True VOR send_message (R1 KP-3)
- [ ] control_panel.py set_advance_label(state)
- [ ] mw_qso.py _on_state_changed: WAIT_73 in Enabled-Liste
- [ ] mw_qso.py _on_state_changed: diversity_locked-Check
- [ ] mw_qso.py _on_state_changed: set_advance_label-Call
- [ ] 10 Tests in test_p1_forcesend.py grün
- [ ] 851 Tests gesamt grün (841 + 10)
- [ ] Final-R1-Codereview ohne 🔴-Findings
- [ ] APP_VERSION 0.95.11 → 0.95.12
- [ ] HISTORY/TODO/HANDOFF/CLAUDE updated
- [ ] Atomare Commits erstellt
- [ ] Mike-Freigabe für Push
- [ ] Lessons-Learned beantwortet
```

---

## 6. Risiken & Notbremse

- **Race in `_on_state_changed`:** Diversity-Lock + state-aware Enabled
  jetzt an einer Stelle. mw_radio.py-Setzen redundant aber harmlos.
- **KP-1 Halluzination ignoriert:** Wenn doch ADIF-Bug auftritt
  (manueller Force-73 ohne qso_complete) — neuer Workflow. Aktuell
  Code-verifiziert: WAIT_73 = QSO schon geloggt.
- **WSJT-X-Etikette:** Force-RR73 / Force-73 ohne Empfangsbestätigung
  ist Funker-Praxis bei stuck-QSO. Mike entscheidet manuell, kein
  Auto-Force.

---

**Plan-V3 Ende. Bereit für Mike-Freigabe + Code.**
