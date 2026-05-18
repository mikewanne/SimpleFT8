# P76-A SWR-Safety-Bug — V1

**Status:** SAFETY 🔴
**Datum:** 18.05.2026 nach Compact
**Vorgaenger:** v0.97.48 Tests 1463

---

## Bug-Symptom (Mike-Field-Test 17m)

Mike testet auf 17m, drueckt manuell TUNE:
- **Live-SWR-Anzeige** zeigt waehrend TUNE-Phase: **2.7**
- `swr_limit` (Settings): **2.5**
- 2.7 > 2.5 → Erwartung: „TUNE fehlgeschlagen — SWR 2.7" + Band-Marker setzen (P63)
- **Tatsaechlich** im QSO-Live-Log: **„✓ TUNE OK — SWR 1.0"** (3× hintereinander)
- Band-Marker bleibt nicht gesetzt → App glaubt 17m ist sicher fuer 70-W-QSO

## Root-Cause (Code-verifiziert)

`ui/mw_tx.py:_tune_post_swr_check` Z.262:
```python
swr_now = self.radio.last_swr
```

Wird **2 Sekunden NACH `tune_off()`** gelesen (via `QTimer.singleShot(2000, _tune_post_swr_check)` in `_tune_stop` Z.208).

### Was in diesen 2 s passiert

1. `tune_off()` Z.192 → TX aus
2. `_is_transmitting = False`
3. VITA-49 Meter-Loop laeuft weiter → sendet SWR-Updates aus dem Radio
4. Ohne TX-Traeger sind die Mess-Artefakte niedrig (< 1.0)
5. In `radio/flexradio.py:_handle_meter` Z.1389-1392:
   ```python
   if swr < 1.0:
       swr = 1.0
   if 1.0 <= swr <= 50.0:
       self._last_swr = swr  # → wird auf 1.0 ueberschrieben
   ```
6. Beim Post-Check 2 s spaeter: `swr_now = 1.0`
7. `1.0 <= 2.5 (limit)` → SWR-OK-Branch → falsche „TUNE OK"-Meldung

### Mike-Fall verifiziert

- Phase A misst `swr_after_match = 2.7` (Z.178, TX noch aktiv)
- `2.7 > 2.5` → **Phase B wird uebersprungen** (Z.184)
- `_tune_converged_rf = None`
- `tune_off()` Z.192
- 2 s warten
- `radio.last_swr` ist jetzt 1.0 (durch Meter-Update-Pfad)
- Post-Check liest 1.0 → SWR-OK-Branch → False-OK → Band-Marker NICHT gesetzt

## Safety-Schaden

1. **False-OK:** User-Erwartung „Band ist okay" obwohl SWR > Limit
2. **Band-Marker (P63) NICHT gesetzt** → kein Schutz fuer nachfolgende Auto-Pfade
3. **RFPreset wird gespeichert** mit falscher SWR-Annahme (rf-Wert ist aus Phase-B-Convergenz... aber Phase B wurde uebersprungen, also `_tune_converged_rf=None` → `rf_to_save=10` hart → koennte in Z.290-293 trotzdem `rf_preset_store.save` triggern bei plausibler FWDPWR)

Worst case: User sendet 70-W-QSO → FlexRadio PA-Schutz greift (Glueck) oder Hardware-Schaden (Pech).

## Fix-Strategie

### Variante A — KISS, R1-Empfehlung erbitten

**Idee:** Letzten gueltigen SWR-Wert WAEHREND TUNE-Phase (TX aktiv) sichern. Im Post-Check diesen Wert lesen statt `radio.last_swr`.

**Implementierung:**

`ui/mw_tx.py`:

1. **Init in `__init__` oder erstem TUNE-Pfad:**
   ```python
   self._tune_last_valid_swr: float | None = None
   ```

2. **In `_tune_stop` direkt VOR `radio.tune_off()` Z.192:**
   ```python
   # P76-A: SWR einfrieren BEVOR tune_off() → TX-Off macht last_swr unbrauchbar
   if self.radio.ip:
       self._tune_last_valid_swr = self.radio.last_swr
   ```

3. **In `_tune_post_swr_check` Z.262 ersetzen:**
   ```python
   # P76-A: gefrorenen Wert lesen (waehrend TX gemessen, NICHT 2s nach tune_off)
   swr_now = self._tune_last_valid_swr
   if swr_now is None or swr_now <= 0.0:
       # Fallback nur wenn freeze nicht passiert ist (sollte nie greifen)
       swr_now = self.radio.last_swr
   ```

4. **Reset nach Post-Check** (am Ende von `_tune_post_swr_check`):
   ```python
   self._tune_last_valid_swr = None
   ```

### Variante B — verworfen

**Idee:** SWR-Check sofort in `_tune_stop` direkt nach `swr_after_match` lesen, ohne 2s-Timer.

**Warum verworfen:**
- 2s-Beruhigungszeit ist P63-Spec (R1-F1 in P63)
- Bricht Watchdog-Reset-Sequenz
- Hat eigene Race-Conditions

### Variante C — optional fuer R1-Empfehlung

**Idee:** Sampling-deque `_tune_swr_samples` analog `_fwdpwr_samples` waehrend `_tune_active=True` in `_on_meter_update`. Post-Check liest `max(samples)` (worst-case = sicherer Anker).

**Vorteil:** robuster gegen Single-Sample-Glueck.
**Nachteil:** mehr Code, mehr Test-Aufwand.

**Empfehlung:** Variante A reicht — Phase B ist Closed-Loop und stabilisiert SWR. Letzter Wert direkt vor `tune_off()` ist der gewollte (gleicher Wert wie waehrend Phase B-Konvergenz).

## Hardware-Pflicht (ANT1)

Aenderung beruehrt nur SWR-Read-Pfad, kein `set_tx_antenna`-Call. ANT1-Pflicht aus P63/P54 bleibt unveraendert.

## Test-Bedarf

- T1: `_tune_last_valid_swr` wird in `_tune_stop` aus `radio.last_swr` gesetzt VOR `tune_off()`
- T2: `_tune_post_swr_check` liest `_tune_last_valid_swr` wenn vorhanden, sonst Fallback
- T3: Bei SWR 2.7 waehrend TUNE → Marker wird gesetzt + „TUNE fehlgeschlagen" im QSO-Log
- T4: Bei SWR 1.5 waehrend TUNE → „TUNE OK — SWR 1.5" geloggt (nicht 1.0!)
- T5: Reset `_tune_last_valid_swr = None` nach Post-Check
- T6: Regression: bestehendes P63-SWR-OK-Verhalten unveraendert (Marker discard, Diversity-Resume)
- T7: Auto-Tune-Pfad: Signal an Dialog mit korrektem SWR-Wert (nicht 1.0)

## Akzeptanz-Kriterien

- **AC1:** Bei SWR > Limit waehrend TUNE → Post-Check liest echten Wert (z.B. 2.7) → SWR-bad-Branch → Band-Marker gesetzt
- **AC2:** Bei SWR <= Limit waehrend TUNE → Post-Check liest echten Wert (z.B. 1.5) → SWR-OK-Branch → korrekter SWR im Log
- **AC3:** Kein Fallback auf `radio.last_swr` ausser `_tune_last_valid_swr` ist None (Safety-Net)
- **AC4:** State-Var wird nach jedem TUNE auf None zurueckgesetzt
- **AC5:** Auto-Tune-Pfad sendet korrektes Signal `auto_tune_done(success, swr_real, fwdpwr)`

## Offene Fragen fuer R1

1. **Variante A vs C?** KISS-Anker reicht oder Sampling-deque sicherer?
2. **Edge-Case Disconnect waehrend TUNE:** `radio.ip` weg → wird `_tune_last_valid_swr` korrekt gesetzt? (Schutz Z.177 `if token is not None and self.radio.ip`)
3. **Test-Strategie:** Mock `_tune_last_valid_swr` ausreichend oder echter `_tune_stop`-Aufruf in Test?
4. **Migration P54-FIX-Test-File:** Brauchen die alten Tests Anpassungen? (verifizieren ob die `radio.last_swr` mocken)

## Akzeptanzkriterien-Negativtests

- **N1:** Wenn `tune_off()` exceptioniert vor Freeze → `_tune_last_valid_swr` bleibt None → Fallback greift
- **N2:** Wenn `_tune_post_swr_check` 2× hintereinander gerufen wird (Token-Race) → 2. Aufruf liest None → Fallback (gewollt, da Token-Guard greift)

## Workflow-Schritte ab hier

1. **V2** (Self-Review)
2. **R1** (DeepSeek-V4-pro): Variante A vs C + Code-Skizze
3. **V3** nach Findings
4. **Code:**
   - C1: `mw_tx.py` `_tune_last_valid_swr` Init + Set vor tune_off
   - C2: `_tune_post_swr_check` Read + Reset
   - C3: Tests NEU `test_p76_swr_safety.py` (T1-T7)
   - C4: APP_VERSION 0.97.48 → 0.97.49
   - C5: HISTORY+HANDOFF+CLAUDE+TODO Update
5. **Final-R1** Push-Freigabe-Check
6. **Field-Test** bei Mike: 17m TUNE wiederholen → muss „TUNE fehlgeschlagen — SWR 2.7" zeigen + Marker setzen
