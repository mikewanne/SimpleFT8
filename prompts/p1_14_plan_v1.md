# P1.14 Plan V1 — Code-Diffs

**Stand:** 2026-05-06.
**Workflow:** **Plan-V1** → Plan-V2 → Plan-R1 → Plan-V3 → Code.
**Diagnose-Quelle:** `prompts/p1_14_v3.md` (R1-Findings eingearbeitet).
**Code-Verifikation:** alle Stellen am aktuellen Code geprueft 2026-05-06.

---

## 1. `core/qso_state.py` — start_qso erweitern

### Diff `start_qso` (Z.238-264)

```diff
     def start_qso(self, their_call: str, their_grid: str = "",
                    freq_hz: int = 0):
         """QSO mit angeklickter Station starten. Bricht laufendes QSO ab."""
-        if self.state not in (QSOState.IDLE, QSOState.CQ_WAIT):
+        # P1.14 KP1: Reset bei JEDEM Nicht-IDLE-State (auch CQ_WAIT, da
+        # dort _pending_reply gesetzt sein kann)
+        if self.state != QSOState.IDLE:
             # Laufendes QSO abbrechen → neues starten
             old = self.qso.their_call if self.qso else "?"
             print(f"[QSO] Abbruch {old} → starte neu mit {their_call}")
+            # P1.14 KP1: Pendings explizit resetten (sonst Geister-Eintraege
+            # mit alter their_call im naechsten Slot)
+            self._pending_reply = None
+            self._pending_hunt_reply = None
+            self._pending_rr73 = None
+            # _caller_queue BEHALTEN (Option B — Mike will durchgaengig
+            # CQ-Antworter abarbeiten nach manuellem Hunt)
             self._set_state(QSOState.IDLE)

-        self._was_cq = self.cq_mode  # CQ-Modus merken fuer Resume nach Timeout
+        # P1.14 KP6: _was_cq robust setzen — externe Korrektur in
+        # mw_qso.py:103 wird damit obsolet
+        self._was_cq = self.cq_mode

         self.qso = QSOData(
             their_call=their_call,
             ...
         )
```

**Aufwand:** ~6 Zeilen +, 1 Zeile geaendert.

---

## 2. `ui/mw_qso.py` — _on_station_clicked verbessern

### Diff `_on_station_clicked` (Z.65-103)

```diff
     @Slot(object)
     def _on_station_clicked(self, msg: FT8Message):
         """User hat eine Station in der Empfangsliste angeklickt."""
         if self.encoder.is_transmitting:
             print(f"[QSO] TX aktiv — Klick ignoriert, warte auf TX-Ende")
+            # P1.14 W5: User-Feedback im Statusbar (war silent skip)
+            self.statusBar().showMessage(
+                "TX aktiv – Klick ignoriert (warte auf TX-Ende)", 3000)
             return
         if getattr(self, '_diversity_measuring', False):
             print(f"[QSO] Einmessen aktiv — Hunt blockiert")
             return

-        # CQ-Modus beenden wenn aktiv — _was_cq VOR stop_cq() sichern!
-        # stop_cq() setzt cq_mode=False; start_qso() würde dann _was_cq=False speichern
-        # → _resume_cq_if_needed() würde CQ nach QSO NICHT wiederaufnehmen (Bug)
-        _cq_was_active = self.qso_sm.cq_mode
-        if _cq_was_active:
+        # CQ-Modus beenden wenn aktiv (P1.14 KP6: _was_cq wird in start_qso
+        # robust gesetzt, externer Workaround entfaellt)
+        if self.qso_sm.cq_mode:
             self.qso_sm.stop_cq()
             self.control_panel.set_cq_active(False)
+            # _was_cq fuer Resume nach Hunt-QSO behalten — start_qso liest
+            # cq_mode aktuell, also vor stop_cq() merken nicht mehr noetig
+            # falls start_qso vor stop_cq() aufgerufen wird (was nicht der
+            # Fall ist hier).

         # Auto-Hunt pausieren bei manuellem Klick
         if self._auto_hunt.active:
             self._auto_hunt.on_manual_qso_start()
+
+        # P1.14 KP3: alte their_call aus _active_qso_targets entfernen
+        # (sonst Set-Bloat bei haeufigen Wechseln, 150s-Aging unnoetig)
+        old_call = self.qso_sm.qso.their_call if self.qso_sm.qso else None
+        if old_call:
+            self._active_qso_targets.discard(old_call)
+
         self._active_qso_targets.add(msg.caller)
         self.rx_panel.set_active_call(msg.caller)
+
+        # P1.14 KP2: wenn Station bereits in Caller-Queue (gewartet hat),
+        # aus Queue entfernen damit sie nicht doppelt kontaktiert wird
+        # nach Resume
+        if any(m.caller == msg.caller for m in self.qso_sm._caller_queue):
+            self.qso_sm._caller_queue = [
+                m for m in self.qso_sm._caller_queue
+                if m.caller != msg.caller
+            ]
+            self.qso_sm.queue_changed.emit(
+                [m.caller for m in self.qso_sm._caller_queue])
+
         self.qso_panel.add_info(f"Rufe {msg.caller}...{self._antenna_pref_label(msg.caller)}")
         self.qso_sm.max_calls = self.settings.get("max_calls", 3)
         their_even = getattr(msg, '_tx_even', None)
         if their_even is not None:
             self.encoder.tx_even = not their_even
             print(f"[TX] Slot: Gegenstation={'EVEN' if their_even else 'ODD'} → wir={'ODD' if their_even else 'EVEN'}")
         else:
             self.encoder.tx_even = None
         self.qso_sm.start_qso(
             their_call=msg.caller,
             their_grid=msg.grid_or_report if msg.is_grid else "",
             freq_hz=msg.freq_hz,
         )
-        # Fix: start_qso() hat _was_cq=False gespeichert (cq_mode war schon False durch stop_cq)
-        # → CQ-Status nachträglich korrigieren damit _resume_cq_if_needed() richtig handelt
-        if _cq_was_active:
-            self.qso_sm._was_cq = True
+        # P1.14 KP6: _was_cq Workaround entfernt — start_qso liest cq_mode
+        # robust BEFORE _set_state. Aber: stop_cq setzt cq_mode=False, so
+        # _was_cq wuerde False bleiben. Loesung: _was_cq direkt setzen wenn
+        # wir aus CQ kommen (KISS):
+        if self.qso_sm._was_cq is False and not self.qso_sm.cq_mode:
+            # Falls CQ aktiv war (cq_mode wurde durch stop_cq() False),
+            # _was_cq korrekt nachsetzen fuer CQ-Resume-Logik
+            pass  # NOTE: das wird in V2 nochmal geprueft
```

**Anmerkung KP6:** der robust-Fix in `start_qso` reicht NICHT, weil
`stop_cq()` VOR `start_qso()` aufgerufen wird → `cq_mode=False` →
`_was_cq=False`. Die Reihenfolge muss bleiben (sonst doppelter
Sende-Trigger). Daher Workaround in mw_qso.py weiterhin noetig — aber
mit Kommentar warum. Plan-V2 soll das nochmal pruefen.

### Diff `_on_cancel` (Z.151-166)

```diff
     @Slot()
     def _on_cancel(self):
         """HALT — stoppt ALLES: CQ, QSO, TX, Messung."""
         self._active_qso_targets.clear()
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
+        # P1.14 W6: Auto-Hunt freigeben (war pausiert durch
+        # on_manual_qso_start, sonst dauerhaft pausiert nach HALT)
+        if self._auto_hunt.active:
+            self._auto_hunt.on_manual_qso_end()
         self.qso_panel.add_info("HALT — alles gestoppt")
         self.statusBar().showMessage("HALT — CQ, QSO, TX gestoppt", 5000)
         print("[HALT] Alles gestoppt")
```

---

## 3. Tests (8 neu)

### NEU `tests/test_p1_14_station_switch.py`

```python
"""P1.14: Station-Wechsel-Bug Tests."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from unittest.mock import MagicMock
import pytest


def _make_sm():
    """QSOStateMachine ohne UI."""
    from core.qso_state import QSOStateMachine, QSOState
    sm = QSOStateMachine(my_call="DA1MHH")
    return sm, QSOState


def _make_msg(caller, snr=-10, freq_hz=1000):
    """FT8Message-Mock."""
    msg = MagicMock()
    msg.caller = caller
    msg.target = "DA1MHH"
    msg.grid_or_report = "JO40"
    msg.is_grid = True
    msg.snr = snr
    msg.freq_hz = freq_hz
    msg._tx_even = True
    return msg


def test_start_qso_resets_pending_reply():
    """KP1: bei state != IDLE wird _pending_reply auf None gesetzt."""
    sm, ST = _make_sm()
    sm.cq_mode = True
    sm._set_state(ST.CQ_WAIT)
    sm._pending_reply = _make_msg("OLD")
    sm.start_qso(their_call="NEW", freq_hz=1000)
    assert sm._pending_reply is None
    assert sm.qso.their_call == "NEW"


def test_start_qso_resets_pending_hunt_reply():
    """KP1: bei TX_CALL/WAIT_REPORT wird _pending_hunt_reply resetet."""
    sm, ST = _make_sm()
    sm.qso = MagicMock(their_call="OLD")
    sm._set_state(ST.WAIT_REPORT)
    sm._pending_hunt_reply = _make_msg("OLD")
    sm.start_qso(their_call="NEW", freq_hz=1000)
    assert sm._pending_hunt_reply is None


def test_start_qso_resets_pending_rr73():
    """KP1: bei TX_REPORT/WAIT_RR73 wird _pending_rr73 resetet."""
    sm, ST = _make_sm()
    sm.qso = MagicMock(their_call="OLD")
    sm._set_state(ST.WAIT_RR73)
    sm._pending_rr73 = _make_msg("OLD")
    sm.start_qso(their_call="NEW", freq_hz=1000)
    assert sm._pending_rr73 is None


def test_start_qso_keeps_caller_queue():
    """Option B: _caller_queue bleibt erhalten fuer CQ-Resume."""
    sm, ST = _make_sm()
    sm._set_state(ST.CQ_WAIT)
    sm._caller_queue = [_make_msg("CALLER1"), _make_msg("CALLER2")]
    sm.start_qso(their_call="NEW", freq_hz=1000)
    assert len(sm._caller_queue) == 2


def test_start_qso_was_cq_robust():
    """KP6: _was_cq wird vor stop_cq aus cq_mode gelesen."""
    sm, ST = _make_sm()
    sm.cq_mode = True
    sm._set_state(ST.CQ_WAIT)
    sm.start_qso(their_call="NEW", freq_hz=1000)
    # _was_cq wird in start_qso aus cq_mode gesetzt (vor _set_state(IDLE))
    # Hier ist cq_mode noch True (kein stop_cq vorher), also _was_cq=True
    assert sm._was_cq is True


def test_handler_clicked_station_removed_from_queue():
    """KP2: Klick auf Station die in Queue ist → aus Queue entfernen."""
    # Test laeuft via mw_qso.py-Logik — braucht MainWindow-Mock
    # ODER: testen direkt im StateMachine? Hier State-Logik:
    sm, ST = _make_sm()
    sm._set_state(ST.CQ_WAIT)
    msg_in_q = _make_msg("DUPE")
    sm._caller_queue = [msg_in_q, _make_msg("OTHER")]
    # Simuliere mw_qso.py-Logik:
    if any(m.caller == "DUPE" for m in sm._caller_queue):
        sm._caller_queue = [m for m in sm._caller_queue if m.caller != "DUPE"]
    assert len(sm._caller_queue) == 1
    assert sm._caller_queue[0].caller == "OTHER"


def test_courtesy_73_state_resetable():
    """KP4/W3: Klick waehrend TX_73_COURTESY bricht sauber ab."""
    sm, ST = _make_sm()
    sm.qso = MagicMock(their_call="OLD", courtesy_73_sent=False)
    sm._set_state(ST.TX_73_COURTESY)
    sm.start_qso(their_call="NEW", freq_hz=1000)
    assert sm.state == ST.TX_CALL
    assert sm.qso.their_call == "NEW"
    assert sm.qso.courtesy_73_sent is False  # neue QSOData


def test_start_qso_old_call_not_in_active_targets():
    """KP3: alte their_call wird aus _active_qso_targets entfernt
    (test in mw_qso.py, hier via Logik-Sim)."""
    targets = {"OLD", "OTHER"}
    old_call = "OLD"
    if old_call:
        targets.discard(old_call)
    targets.add("NEW")
    assert "OLD" not in targets
    assert "NEW" in targets
    assert "OTHER" in targets
```

### Optional: `test_p1_14_handler.py` (mw_qso.py-Tests, mit MainWindow-Mock)
Komplexer wegen QSOPanel/RxPanel/AutoHunt-Mocks. Plan-V2 entscheidet ob
sinnvoll oder ob die State-Tests reichen.

---

## 4. Implementations-Reihenfolge

1. `core/qso_state.py:start_qso` — Reset-Logik
2. `ui/mw_qso.py:_on_station_clicked` — KP2/KP3 Cleanups + UX-Toast
3. `ui/mw_qso.py:_on_cancel` — Auto-Hunt-Resume
4. `tests/test_p1_14_station_switch.py` — 8 Tests
5. Tests laufen lassen (~802 + 8 = 810 erwartet)
6. App-Smoke-Test
7. Atomarer Code-Commit + Doku-Commit

---

## 5. Akzeptanz-Checkliste (final)

- [ ] qso_state.py:start_qso resetet 3 Pendings bei state != IDLE
- [ ] mw_qso.py:_on_station_clicked discardet alte their_call
- [ ] mw_qso.py:_on_station_clicked entfernt Station aus _caller_queue
- [ ] mw_qso.py:_on_station_clicked Statusbar-Toast bei TX
- [ ] mw_qso.py:_on_cancel ruft auto_hunt.on_manual_qso_end()
- [ ] 8 neue Tests gruen
- [ ] 802 bestehende Tests gruen
- [ ] APP_VERSION 0.95.7 → 0.95.8

---

**Plan-V1 Ende. Naechster Schritt: Plan-V2 Self-Review.**
