# P1.14 Plan V2 — Self-Review

**Stand:** 2026-05-06.
**Workflow:** Plan-V1 → **Plan-V2 (diese Datei)** → Plan-R1 → Plan-V3 → Code.
**Aufgabe:** Plan-V1 (`p1_14_plan_v1.md`) kritisch reviewen, Lücken füllen.

---

## L1 — KP6 _was_cq Workaround: BEHALTEN, NICHT entfernen

Plan-V1 hat selbst zugegeben unsicher zu sein („wird in V2 nochmal geprueft").
**V2-Entscheidung: Workaround behalten.** Begründung:

```
Aktuelle Reihenfolge in mw_qso.py:_on_station_clicked
  Z.77  _cq_was_active = self.qso_sm.cq_mode    # snapshot (= True)
  Z.79  self.qso_sm.stop_cq()                   # cq_mode → False
  Z.95  self.qso_sm.start_qso(...)              # _was_cq = cq_mode = False ✗
  Z.103 self.qso_sm._was_cq = True              # Workaround korrigiert
```

**Warum nicht in start_qso integrieren (R1-Vorschlag):**
`start_qso` hat keinen Zugriff auf den vorherigen `cq_mode`-Wert vor `stop_cq()`.
Optionen:
- Reihenfolge tauschen (start_qso vor stop_cq) → state ist nicht IDLE,
  stop_cq würde fragwürdig laufen
- Optionaler Parameter `was_cq_override` → API-Bloat, Overengineering
- Method-Signature ändern → Breaking Change ohne Mehrwert

**Beste Lösung:** Workaround behalten, Kommentar präzisieren als bewusste
Design-Entscheidung. KISS. Test `test_start_qso_was_cq_robust` testet das
existierende Verhalten und ist OK als Regression-Schutz.

→ **Plan-V1 KP6-Diff `pass # NOTE: das wird in V2 nochmal geprueft` STREICHEN**.
   Stattdessen Original-Workaround behalten + besserer Kommentar.

---

## L2 — W6 Auto-Hunt-Resume: Plan-V1 hat 2 Fix-Stellen ÜBERSEHEN

Plan-V1 fixt nur `_on_cancel` (HALT). Aber `_manual_override = True` wird
auch in 2 anderen Pfaden gesetzt und NIE zurückgesetzt:

### Fall A: Erfolgreiches manuelles QSO
```
mw_qso.py:_on_qso_confirmed (Z.300)
  → ruft KEIN auto_hunt.on_manual_qso_end()
  → _manual_override bleibt True
  → Auto-Hunt pausiert dauerhaft auch nach erfolgreichem QSO
```

### Fall B: Manuelles QSO mit Timeout
```
mw_qso.py:_on_qso_timeout (Z.403)
  → ruft auto_hunt.on_qso_timeout(call) [Cooldown setzen]
  → setzt aber _manual_override NICHT zurück
  → Auto-Hunt pausiert dauerhaft auch nach Timeout
```

**V2-Erweiterung Plan-V1 §2:** zusätzlich zu `_on_cancel` auch in
`_on_qso_confirmed` und `_on_qso_timeout` `on_manual_qso_end()` rufen,
aber nur wenn vorher manuelles QSO lief (`_manual_override` war gesetzt).

**Vereinfachung KISS:** `on_manual_qso_end()` ist idempotent (setzt nur
`_manual_override = False`). Plan-V2 ruft es **immer** wenn `auto_hunt.active`.
Kein State-Tracking nötig.

### Diff `_on_qso_confirmed` (Z.300-308)
```diff
     @Slot(object)
     def _on_qso_confirmed(self, qso_data):
         """73 empfangen — QSO wirklich komplett, ✓ anzeigen."""
         self.qso_panel.add_qso_complete(qso_data.their_call)
         # Logbuch aktualisieren (neues QSO wurde in ADIF geschrieben)
         self.qso_panel.logbook.refresh()
+        # P1.14 W6: Auto-Hunt nach manuellem QSO freigeben (sonst pausiert
+        # _manual_override dauerhaft nach Klick + erfolgreichem 73)
+        if self._auto_hunt.active:
+            self._auto_hunt.on_manual_qso_end()
         # CQ-Modus läuft weiter — visuell bestätigen
         if self.qso_sm.cq_mode:
             self.control_panel.set_cq_active(True)
             self.qso_panel.add_info("CQ-Modus läuft weiter...")
```

### Diff `_on_qso_timeout` (Z.402-412)
```diff
     @Slot(str)
     def _on_qso_timeout(self, their_call: str):
         self._active_qso_targets.discard(their_call)
         self.rx_panel.set_active_call("")
         self.qso_panel.add_timeout(their_call)
         # Auto-Hunt: Timeout → Cooldown setzen, naechste Station
         if self._auto_hunt.active:
             self._auto_hunt.on_qso_timeout(their_call)
+            # P1.14 W6: _manual_override zuruecksetzen, sonst pausiert
+            # Auto-Hunt nach Klick → Timeout dauerhaft
+            self._auto_hunt.on_manual_qso_end()
         # CQ-Button aktiv halten wenn CQ-Modus laeuft
         if self.qso_sm.cq_mode:
             self.control_panel.set_cq_active(True)
```

---

## L3 — Test-Suite: 2 fehlende Tests ergänzen

Plan-V1 hat 8 Tests, davon 2 mit „via Logik-Sim" (dummer State-Stub).
Akzeptabel für KP2/KP3 (pure Logik), aber W6 Auto-Hunt-Resume fehlt
komplett. Zusätzlich:

### Test 9 (NEU): Auto-Hunt-Resume nach manuellem QSO-Confirm
```python
def test_auto_hunt_resume_on_qso_confirmed():
    """W6: nach erfolgreichem manuellem QSO _manual_override = False."""
    from core.auto_hunt import AutoHunt
    hunt = AutoHunt()
    hunt.active = True
    hunt.on_manual_qso_start()
    assert hunt._manual_override is True
    hunt.on_manual_qso_end()
    assert hunt._manual_override is False
```

### Test 10 (NEU): Auto-Hunt-Resume nach Timeout
```python
def test_auto_hunt_resume_on_qso_timeout():
    """W6: nach manuellem QSO-Timeout _manual_override = False."""
    from core.auto_hunt import AutoHunt
    hunt = AutoHunt()
    hunt.active = True
    hunt.on_manual_qso_start()
    hunt.on_qso_timeout("DUMMY")
    # In mw_qso.py wird zusaetzlich on_manual_qso_end gerufen:
    hunt.on_manual_qso_end()
    assert hunt._manual_override is False
```

**Hinweis:** Diese 2 Tests testen die Auto-Hunt-API (idempotent).
Den UI-Pfad (mw_qso.py-Slot ruft beide korrekt) testet kein Test —
zu komplex ohne MainWindow-Mock. Akzeptabel, weil Logik trivial.

---

## L4 — `test_start_qso_was_cq_robust` (Plan-V1 Test 5): VEREINFACHEN

Plan-V1 testet:
```python
sm.cq_mode = True
sm._set_state(ST.CQ_WAIT)
sm.start_qso(their_call="NEW", freq_hz=1000)
assert sm._was_cq is True
```

Test passt, aber Kommentar irreführend („wird in start_qso aus cq_mode
gesetzt vor _set_state(IDLE)") — Code macht das schon JETZT (Z.247).
**V2-Korrektur:** Test als „Regression-Schutz für KP6-Workaround in mw_qso.py"
umkommentieren. Test bleibt unverändert in Logik.

---

## L5 — `test_courtesy_73_state_resetable` (Plan-V1 Test 7) — KRITISCH

Plan-V1 setzt:
```python
sm._set_state(ST.TX_73_COURTESY)
sm.start_qso(their_call="NEW", freq_hz=1000)
assert sm.qso.courtesy_73_sent is False  # neue QSOData
```

**V2-Finding:** `start_qso` weist neue `QSOData()` an `self.qso` zu (Z.249).
Default-Wert von `courtesy_73_sent` muss in QSOData False sein. Verifizieren!

```bash
grep -n "courtesy_73_sent" core/qso_state.py
```

Wenn Default = False → Test ist OK. Wenn nicht → Test schlägt fehl.

---

## L6 — Implementations-Reihenfolge ergänzen

Plan-V1 §4 hat 7 Schritte. V2 ergänzt:

8. **Smoke-Test der App** nach Tests grün — manuelles UI-Klicken auf Station
   während CQ läuft, prüfen dass:
   - alte Station aus _active_qso_targets entfernt
   - Pendings resetet
   - Statusbar-Toast bei TX-Klick erscheint
   - Auto-Hunt nach manuellem QSO + 73 wieder läuft (Field-Test, nicht Test-Suite)

---

## L7 — Akzeptanz-Checkliste finale Form

```
- [ ] qso_state.py:start_qso resetet 3 Pendings bei state != IDLE
- [ ] qso_state.py:start_qso Reset-Set: state != IDLE (CQ_WAIT inkl.)
- [ ] mw_qso.py:_on_station_clicked alte their_call discarden
- [ ] mw_qso.py:_on_station_clicked Station aus _caller_queue entfernen
- [ ] mw_qso.py:_on_station_clicked Statusbar-Toast bei TX (3s)
- [ ] mw_qso.py:_on_cancel auto_hunt.on_manual_qso_end()
- [ ] mw_qso.py:_on_qso_confirmed auto_hunt.on_manual_qso_end()  (V2 NEU)
- [ ] mw_qso.py:_on_qso_timeout auto_hunt.on_manual_qso_end()  (V2 NEU)
- [ ] KP6 _was_cq Workaround in mw_qso.py:103 BEHALTEN (V2 KORREKTUR)
- [ ] 10 neue Tests gruen (8 Plan-V1 + 2 V2: Auto-Hunt-Resume)
- [ ] 802 bestehende Tests gruen
- [ ] APP_VERSION 0.95.7 → 0.95.8
- [ ] Smoke-Test App
```

---

## L8 — Geschätzter Code-Aufwand revidiert

Plan-V1: ~6 Zeilen + in qso_state.py, ~30 Zeilen + in mw_qso.py.
**Plan-V2:** ~6 Zeilen + in qso_state.py, ~38 Zeilen + in mw_qso.py
(8 Zeilen mehr für 2 zusätzliche on_manual_qso_end-Aufrufe), 10 Tests.

---

## L9 — Risiken die Plan-V1 NICHT genannt hat

1. **`_manual_override`-API:** wird in Tests direkt gepokt (`hunt._manual_override`).
   Zugriff auf private Attribute. Akzeptabel weil Logik trivial. Kein
   Refactor zu öffentlicher API nötig (KISS).

2. **`_caller_queue`-Manipulation:** Plan-V1 ändert die Liste in mw_qso.py
   direkt (`self.qso_sm._caller_queue = [...]`). Das ist ein State-Machine-
   externer Eingriff — fragil aber konsistent mit `_was_cq`-Pattern.
   Alternative: neue State-Machine-Methode `discard_from_caller_queue(call)`.
   **V2-Entscheidung:** KISS, direkt. 1 Stelle, keine Wiederholung. Wenn
   Pattern öfter auftritt → später extrahieren.

3. **`self._active_qso_targets`-Discard:** wird in Plan-V1 nur in
   `_on_station_clicked` gemacht. Was ist mit `_on_qso_confirmed` /
   `_on_qso_timeout`? Antwort: dort wird schon disjarded
   (`_on_qso_timeout:404`). Bei `_on_qso_confirmed` ist das aktuell NICHT
   geclearedt aber das ist OK weil `_active_qso_targets` ein Set für 150s
   Aging ist (StationAccumulator) — kein Problem wenn Eintrag bleibt bis
   Aging zuschlägt.

---

## L10 — Nächste Schritte

→ Plan-R1 (DeepSeek-Reasoner mit Plan-V2 + 3 Code-Files):
   - `core/qso_state.py`
   - `ui/mw_qso.py`
   - `core/auto_hunt.py`

**Plan-V2 Ende. Weiter mit Plan-R1.**
