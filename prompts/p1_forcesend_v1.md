# P1.FORCESEND V1 — btn_advance dynamisch labeln + WAIT_73-Branch

**Stand:** 2026-05-06.
**Workflow:** **V1 (diese Datei)** → V2 (Self-Review) → R1 (DeepSeek) → V3 → Plan → Code.
**Mike-Anweisung:** Bei stuck-Gegenstation (sendet immer Report statt
RR73/73) manuell RR73 oder 73 senden können. Nach Code-Inspektion:
`btn_advance` macht das schon zur Hälfte, nur unbenutzt + dauerhaft
disabled.

---

## 1. Befunde aus Code-Inspektion

**Bug-Kette (3 Probleme an einem Button):**

### Bug A — `btn_advance` dauerhaft disabled

`ui/control_panel.py:908` — `setEnabled(False)` initial, danach nur in
`ui/mw_radio.py:801,1227` über `_set_diversity_locked()` enabled/disabled.
Outside Diversity-Mess-Phase wird er NIE wieder enabled. Mike kann ihn
seit App-Start praktisch nie klicken.

### Bug B — Label „Weiter →" semantisch unklar

`btn_advance` macht je nach State unterschiedliche Dinge:
- WAIT_REPORT → R-Report senden
- WAIT_RR73 → RR73 senden

Aber der Label „Weiter →" macht das nicht sichtbar. Mike hat ihn nie
genutzt → vergessenes UX-Feature.

### Bug C — WAIT_73-Branch fehlt in `advance()`

`core/qso_state.py:640-652` — `advance()` hat 2 Branches (WAIT_REPORT
+ WAIT_RR73). **Kein Branch für WAIT_73** = kein manuelles 73 senden
wenn die Gegenstation kein RR73 schickt.

---

## 2. Ziel

`btn_advance` wird zu einem **state-aware Manuell-Senden-Button** mit:
- Dynamischem Label je nach QSO-State
- State-aware Enabled-Logik (statt nur Diversity-Lock)
- Voller Coverage WAIT_REPORT / WAIT_RR73 / WAIT_73

**KISS:** Keine neuen Buttons. Bestehender btn_advance bekommt 3 Bug-Fixes.

---

## 3. Akzeptanzkriterien

1. `core/qso_state.py:advance()` bekommt 3. Branch:
   ```python
   elif self.state == QSOState.WAIT_73:
       msg = f"{self.qso.their_call} {self.my_call} 73"
       self._set_state(QSOState.TX_73_COURTESY)  # vorhandener State
       self.send_message.emit(msg)
   ```
2. `btn_advance.text` ändert sich je nach `qso_sm.state`:
   - WAIT_REPORT → `"R+Report senden"`
   - WAIT_RR73 → `"RR73 senden"`
   - WAIT_73 → `"73 senden"`
   - sonst → `"Weiter →"` (Default, button disabled)
3. `btn_advance.setEnabled` ist `True` genau dann wenn:
   - state in {WAIT_REPORT, WAIT_RR73, WAIT_73}
   - UND nicht Diversity-locked
4. State-Wechsel triggern Label + Enabled-Update.
5. Diversity-Lock überschreibt (deaktiviert) auch wenn state passend.
6. Bestehende Tests bleiben grün.
7. Neue Tests decken Label-Wechsel + WAIT_73-Branch + Enabled-Logik ab.

---

## 4. Betroffene Module

- **`core/qso_state.py:640-652`** — `advance()` 3. Branch (WAIT_73)
- **`ui/control_panel.py:899-908`** — Helper-Methode `update_advance_button(state)`
  oder `set_advance_state(state)` die Label + Enabled setzt
- **`ui/mw_qso.py`** — bei `state_changed`-Signal (oder analog) den
  Label-Update triggern. Stelle prüfen wo aktuell auf state-Wechsel
  reagiert wird.
- **`ui/mw_radio.py:801,1227`** — Diversity-Lock muss zusätzlich state
  prüfen, sonst überschreibt es den state-aware Enabled.

---

## 5. Randbedingungen

- **State-Signal:** Existiert `qso_sm.state_changed = Signal(QSOState)`?
  Code-Verifikation pflicht (V2). Wenn nein: Hook in `_set_state`
  setzen.
- **TX_73_COURTESY:** P1.10 (v0.95.4) hat den State eingeführt für
  Hoeflichkeits-73 nach Empfang von 73. Wir verwenden den gleichen
  State auch für manuell-erzwungenes 73 — semantisch leicht anders
  (kein Hoeflichkeits-Echo, sondern manuelles Beenden), aber funktional
  identisch (sende 73, dann LOGGING). V2/R1 prüfen ob das ok ist oder
  ein neuer State `TX_73_FORCED` her muss.
- **`courtesy_73_sent`-Flag:** P1.10 setzt das Flag um max 1× pro QSO
  zu senden. Bei manuellem Force-73 sollte es auch gesetzt werden,
  damit nicht beide Pfade (manuell + auto) zusammen 2× 73 schicken.
- **3-Min-Timeout:** Wenn manuell 73 gesendet wird im WAIT_73-State,
  läuft der Timeout in `on_cycle_end` weiter. Ist der TX_73_COURTESY-
  State in der Timeout-Ausschluss-Liste (P1.10)? Verifizieren.
- **Hobby-Tool-Philosophie:** Mike soll bei stuck-QSO eingreifen können.
  Kein Auto-Force, kein Hot-Key — nur Button-Klick.

---

## 6. Nicht im Scope

- Force-Buttons im RX-Panel-Kontextmenü
- Free-Text "TNX NAME 73" (Mike: zu kompliziert, raus)
- TX1/TX2/TX3-Buttons à la WSJT-X (volle manuelle Kontrolle)
- Keyboard-Shortcuts
- TX_REPORT-Force (= Re-Send Report) — selten gebraucht, aktueller
  Branch deckt das

---

## 7. Testbarkeit

**Pflicht-Tests (qso_state.py):**

1. `test_advance_wait_73_sends_73`:
   - state = WAIT_73, advance() → send_message.emit "DK5ON DA1MHH 73"
   - state wechselt zu TX_73_COURTESY

2. `test_advance_wait_73_sets_courtesy_flag` (falls relevant):
   - Nach advance() in WAIT_73 → `qso.courtesy_73_sent == True`
   - (verhindert dass Auto-Pfad nochmal 73 schickt)

3. Bestehende `advance()`-Tests bleiben grün

**Pflicht-Tests (control_panel.py):**

4. `test_advance_label_default`:
   - state = IDLE → label "Weiter →", enabled False

5. `test_advance_label_wait_report`:
   - state = WAIT_REPORT → label "R+Report senden", enabled True

6. `test_advance_label_wait_rr73`:
   - state = WAIT_RR73 → label "RR73 senden", enabled True

7. `test_advance_label_wait_73`:
   - state = WAIT_73 → label "73 senden", enabled True

8. `test_advance_disabled_during_diversity_lock`:
   - state = WAIT_RR73 + diversity_locked → enabled False
   - Label bleibt "RR73 senden" (informativ)

---

## 8. Offene Fragen für V2/R1

1. **Update-Hook:** Wo state→Label-Update anhängen? `qso_sm`-Signal
   nutzen oder im `_on_qso_state_changed`-Handler in mw_qso.py?
2. **TX_73_COURTESY vs neuer State:** Reuse oder neuer State `TX_73_FORCED`?
3. **`courtesy_73_sent`-Flag:** Auch bei Force setzen (Doppel-Send-Schutz)?
4. **Timeout-Ausschluss-Liste:** TX_73_COURTESY drin? Wenn ja → kein Eingriff.
5. **Diversity-Lock-Override:** wer hat Vorrang — state-aware oder
   diversity-aware? Diversity gewinnt (kein TX während Mess).

---

**Workflow-Status:** V1 fertig. Weiter mit V2 (Self-Review).
