# P1.14 Plan V3 — Final (R1-freigegeben)

**Stand:** 2026-05-06.
**Workflow:** Plan-V1 → V2 → R1 ✅ → **V3 (diese Datei)** → Code.
**R1-Empfehlung:** „Plan freigegeben" unter den unten genannten Bedingungen.
**R1-Findings:** Keine neuen Befunde — KP-A und KP-B in R1 sind nur Bestaetigungen
von Plan-V1 §2 (auto_hunt _on_cancel) und §1 (caller_queue Cleanup).

---

## 1. Code-Aenderungen (final)

### 1.1 `core/qso_state.py:start_qso` (Z.238-265)

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

         self._was_cq = self.cq_mode  # CQ-Modus merken fuer Resume nach Timeout
```

### 1.2 `ui/mw_qso.py:_on_station_clicked` (Z.65-103)

```diff
     @Slot(object)
     def _on_station_clicked(self, msg: FT8Message):
         """User hat eine Station in der Empfangsliste angeklickt."""
         if self.encoder.is_transmitting:
             print(f"[QSO] TX aktiv — Klick ignoriert, warte auf TX-Ende")
+            # P1.14 W5: User-Feedback (war silent skip — frustrierend)
+            self.statusBar().showMessage(
+                "TX aktiv – Klick ignoriert (warte auf TX-Ende)", 3000)
             return
         if getattr(self, '_diversity_measuring', False):
             print(f"[QSO] Einmessen aktiv — Hunt blockiert")
             return
         # CQ-Modus beenden wenn aktiv — _was_cq VOR stop_cq() sichern!
         # stop_cq() setzt cq_mode=False; start_qso() würde dann _was_cq=False speichern
         # → _resume_cq_if_needed() würde CQ nach QSO NICHT wiederaufnehmen (Bug)
         _cq_was_active = self.qso_sm.cq_mode
         if _cq_was_active:
             self.qso_sm.stop_cq()
             self.control_panel.set_cq_active(False)
         # Auto-Hunt pausieren bei manuellem Klick
         if self._auto_hunt.active:
             self._auto_hunt.on_manual_qso_start()
+        # P1.14 KP3: alte their_call aus _active_qso_targets entfernen
+        # (sonst Set-Bloat bei haeufigen Wechseln)
+        old_call = self.qso_sm.qso.their_call if self.qso_sm.qso else None
+        if old_call:
+            self._active_qso_targets.discard(old_call)
         self._active_qso_targets.add(msg.caller)  # 150s Aging fuer angerufene Station
         self.rx_panel.set_active_call(msg.caller)  # Zeile im RX-Panel hervorheben
+        # P1.14 KP2: wenn Station bereits in Caller-Queue gewartet hat, aus
+        # Queue entfernen damit sie nicht doppelt kontaktiert wird
+        if any(m.caller == msg.caller for m in self.qso_sm._caller_queue):
+            self.qso_sm._caller_queue = [
+                m for m in self.qso_sm._caller_queue
+                if m.caller != msg.caller
+            ]
+            self.qso_sm.queue_changed.emit(
+                [m.caller for m in self.qso_sm._caller_queue])
         self.qso_panel.add_info(f"Rufe {msg.caller}...{self._antenna_pref_label(msg.caller)}")
         ...
         # Fix: start_qso() hat _was_cq=False gespeichert (cq_mode war schon False durch stop_cq)
         # → CQ-Status nachträglich korrigieren damit _resume_cq_if_needed() richtig handelt
+        # P1.14 KP6 (Plan-V2-Entscheidung): Workaround BEHALTEN. Saubere
+        # Integration in start_qso ist nicht moeglich weil stop_cq() vor
+        # start_qso() laufen MUSS — _was_cq waere dort schon False.
         if _cq_was_active:
             self.qso_sm._was_cq = True
```

### 1.3 `ui/mw_qso.py:_on_cancel` (Z.151-166)

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
+        # P1.14 W6: Auto-Hunt freigeben (sonst dauerhaft pausiert nach HALT)
+        if self._auto_hunt.active:
+            self._auto_hunt.on_manual_qso_end()
         self.qso_panel.add_info("HALT — alles gestoppt")
```

### 1.4 `ui/mw_qso.py:_on_qso_confirmed` (Z.300-308) — Plan-V2 Erweiterung

```diff
     @Slot(object)
     def _on_qso_confirmed(self, qso_data):
         """73 empfangen — QSO wirklich komplett, ✓ anzeigen."""
         self.qso_panel.add_qso_complete(qso_data.their_call)
         self.qso_panel.logbook.refresh()
+        # P1.14 W6: Auto-Hunt nach erfolgreichem manuellem QSO freigeben
+        if self._auto_hunt.active:
+            self._auto_hunt.on_manual_qso_end()
         if self.qso_sm.cq_mode:
             self.control_panel.set_cq_active(True)
             self.qso_panel.add_info("CQ-Modus läuft weiter...")
```

### 1.5 `ui/mw_qso.py:_on_qso_timeout` (Z.402-412) — Plan-V2 Erweiterung

```diff
     @Slot(str)
     def _on_qso_timeout(self, their_call: str):
         self._active_qso_targets.discard(their_call)
         self.rx_panel.set_active_call("")
         self.qso_panel.add_timeout(their_call)
         if self._auto_hunt.active:
             self._auto_hunt.on_qso_timeout(their_call)
+            # P1.14 W6: _manual_override zuruecksetzen (sonst pausiert
+            # Auto-Hunt nach Klick → Timeout dauerhaft)
+            self._auto_hunt.on_manual_qso_end()
         if self.qso_sm.cq_mode:
             self.control_panel.set_cq_active(True)
```

---

## 2. Tests

NEU `tests/test_p1_14_station_switch.py` mit **10 Tests**:

1. `test_start_qso_resets_pending_reply` — KP1
2. `test_start_qso_resets_pending_hunt_reply` — KP1
3. `test_start_qso_resets_pending_rr73` — KP1
4. `test_start_qso_keeps_caller_queue` — Option B
5. `test_start_qso_was_cq_robust` — KP6 Regression
6. `test_handler_clicked_station_removed_from_queue` — KP2 (Logik-Sim)
7. `test_courtesy_73_state_resetable` — KP4/W3
8. `test_start_qso_old_call_not_in_active_targets` — KP3 (Logik-Sim)
9. `test_auto_hunt_resume_on_manual_qso_end` — W6 (idempotent API)
10. `test_auto_hunt_resume_after_timeout` — W6

---

## 3. Akzeptanz-Checkliste

```
- [ ] qso_state.py:start_qso resetet 3 Pendings bei state != IDLE
- [ ] qso_state.py:start_qso Reset-Set: state != IDLE (CQ_WAIT inkl.)
- [ ] mw_qso.py:_on_station_clicked Statusbar-Toast bei TX (3s)
- [ ] mw_qso.py:_on_station_clicked alte their_call discarden
- [ ] mw_qso.py:_on_station_clicked Station aus _caller_queue entfernen
- [ ] mw_qso.py:_on_station_clicked KP6-Workaround BEHALTEN + besser kommentiert
- [ ] mw_qso.py:_on_cancel auto_hunt.on_manual_qso_end()
- [ ] mw_qso.py:_on_qso_confirmed auto_hunt.on_manual_qso_end()
- [ ] mw_qso.py:_on_qso_timeout auto_hunt.on_manual_qso_end()
- [ ] 10 neue Tests gruen
- [ ] 802 bestehende Tests gruen
- [ ] APP_VERSION 0.95.7 → 0.95.8
- [ ] Smoke-Test App
- [ ] Atomare Commits: Code + Tests + Doku
```

---

## 4. Implementations-Reihenfolge

1. `core/qso_state.py:start_qso` (KP1)
2. `ui/mw_qso.py:_on_station_clicked` (KP2/KP3/W5/KP6-Kommentar)
3. `ui/mw_qso.py:_on_cancel` (W6)
4. `ui/mw_qso.py:_on_qso_confirmed` (W6)
5. `ui/mw_qso.py:_on_qso_timeout` (W6)
6. `tests/test_p1_14_station_switch.py` (10 Tests)
7. Tests laufen (~802 + 10 = 812 erwartet)
8. App-Smoke-Test
9. APP_VERSION bump
10. Atomare Commits + Doku

**Plan-V3 Ende. Weiter mit Code.**
