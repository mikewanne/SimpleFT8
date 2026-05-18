# P76-A SWR-Safety-Bug — R1 Prompt (DeepSeek-V4-pro)

**Du bist DeepSeek-V4-pro im Workflow V1 → V2 → R1 → V3 → Code → Final-R1.**

Reviewe diese sicherheitskritische Bug-Diagnose + Fix-Strategie fuer SimpleFT8 (FT8/FT4/FT2 Hobby-Funker-App auf FlexRadio).

---

## Context

**Bug:** Hardware-Safety. Mike testet 17m, SWR ist 2.7 (Limit 2.5), App loggt faelschlich „TUNE OK — SWR 1.0" 3× in Folge. Band-Marker wird NICHT gesetzt → User glaubt Band ist sicher fuer 70-W-QSO → PA-Schutz oder Hardware-Schaden moeglich.

**Root Cause:**
- `ui/mw_tx.py:_tune_post_swr_check` Z.262 liest `swr_now = self.radio.last_swr` **2 Sekunden NACH `tune_off()`** (via QTimer).
- In diesen 2 s laeuft FlexRadio Meter-Loop weiter und sendet SWR-Werte ohne TX-Traeger (Mess-Artefakte <1.0).
- `radio/flexradio.py:_handle_meter` Z.1389-1392 clampt `swr<1.0 → 1.0` und ueberschreibt `_last_swr=1.0`.
- Post-Check 2 s spaeter liest 1.0 → `1.0 <= swr_limit` → false-OK.

**Mike-Fall (Phase-B-Skip):**
- `swr_after_match = 2.7` (Phase A, TX aktiv → valid)
- `2.7 > 2.5` → Phase B uebersprungen, `_tune_converged_rf = None`
- `tune_off()`
- 2 s warten → `last_swr` jetzt 1.0 (Clamp-Bug)
- `1.0 <= 2.5` → SWR-OK-Branch → false-OK + Marker NICHT gesetzt

---

## Geplanter Fix (Variante A, KISS)

**State-Var:** `_tune_last_valid_swr: float | None`

**1. `ui/main_window.py:__init__`** (1 LOC):
```python
self._tune_last_valid_swr: float | None = None
```

**2. `ui/mw_tx.py:_tune_stop`** direkt VOR `radio.tune_off()` Z.192 (3 LOC):
```python
# P76-A SAFETY: SWR einfrieren BEVOR tune_off().
# Nach tune_off() Meter-Loop ohne TX-Traeger → <1.0 → Clamp auf 1.0.
self._tune_last_valid_swr = self.radio.last_swr
```

**3. `ui/mw_tx.py:_tune_post_swr_check`** Z.262 ersetzen (5 LOC):
```python
# P76-A SAFETY: gefrorenen Wert lesen.
swr_now = self._tune_last_valid_swr
if swr_now is None or swr_now < 1.0:
    swr_now = self.radio.last_swr  # Defensive Fallback
self._tune_last_valid_swr = None  # Reset fuer naechsten TUNE
```

**Gesamt:** ~9 LOC. Sehr klein, sehr kontrolliert.

---

## Phase-Pfade (zur Verifikation)

**Pfad 1 — SWR-OK + Phase B Convergenz:**
1. Phase A: Tuner-Match (TUNE_POWER 10W)
2. `swr_after_match = radio.last_swr` (TX aktiv, valid)
3. `swr_after_match <= swr_limit` → Phase B startet
4. `_tune_converge_to_target` laeuft ~6.5 s, kontinuierliche SWR-Updates → `_last_swr` immer frisch
5. Phase B fertig, `_tune_converged_rf` gesetzt
6. **FREEZE: `_tune_last_valid_swr = radio.last_swr`** ← NEU
7. `tune_off()` → TX endet
8. 2 s warten
9. Post-Check liest gefrorenen Wert → korrekt

**Pfad 2 — SWR-bad (Mike's Fall):**
1. Phase A: Tuner-Match
2. `swr_after_match = 2.7` (TX aktiv, valid)
3. `2.7 > 2.5` → Phase B SKIP
4. **FREEZE: `_tune_last_valid_swr = 2.7`** ← NEU (last_swr noch unverfaelscht)
5. `tune_off()` → TX endet
6. 2 s warten → `last_swr` jetzt 1.0 (Clamp)
7. Post-Check liest gefrorenen Wert 2.7 → SWR-bad-Branch → Marker gesetzt + „TUNE fehlgeschlagen — SWR 2.7"

**Pfad 3 — Cancel waehrend Phase B:**
1. Phase A OK
2. Phase B startet
3. User-Cancel → `_tune_convergence_cancelled=True`, `_tune_converge_to_target` returnt None
4. `_tune_converged_rf = None`
5. **FREEZE: `_tune_last_valid_swr = radio.last_swr`** ← NEU (Phase B hat valid Werte hinterlassen)
6. `tune_off()`
7. Post-Check liest gefrorenen Wert → korrekt

**Pfad 4 — Re-Entry-Cancel (Sub-Event-Loop):**
1. `_tune_stop(token)` laeuft, `_tune_stop_active=True`
2. Cancel-Click in Sub-Event-Loop ruft `_tune_stop(None)` erneut
3. Z.167-170: `_tune_stop_active` True → setzt `_tune_convergence_cancelled=True`, returnt OHNE `tune_off()`
4. 1. Aufruf laeuft weiter, macht Freeze + tune_off
5. ✓ Kein Doppel-Freeze, kein Konflikt

---

## V2-Findings (zur Verifikation durch dich)

- **F1** ✅ V1-Diagnose verifiziert
- **F2** ⚠️ Init in main_window.py:__init__ (Mixin-Pattern)
- **F3** ⚠️ Freeze unconditional VOR tune_off, KEIN radio.ip-Guard (radio.last_swr ist lokale Property)
- **F4** ⚠️ Variante A (Single-Snapshot) vs C (Sampling-deque) — Empfehlung A wegen KISS
- **F5** ⚠️ AC1 praeziser: Clamp-1.0-Bug darf nicht mehr als SWR-OK interpretiert werden
- **F6** ⚠️ 6 Tests + 1 Source-Level-Test geplant
- **F7** ⚠️ Phase-B-Skip-Branch (Mike's Fall) durch Variante A abgedeckt
- **F8** ⚠️ Naming `_tune_last_valid_swr` OK
- **F9** ⚠️ Auto-Tune-Pfad-Signal `auto_tune_done` wird ehrlicher
- **F10** ⚠️ `[P63] Post-TUNE`-Log zeigt jetzt korrekten Wert
- **F11** ⚠️ RFPreset-Save wird nicht mehr mit Falsch-Anker korrumpiert
- **F12** ⚠️ Keine Migration noetig

---

## Pruef-Auftrag

Bitte beantworte als Code-Reviewer mit Schwerpunkt auf:

### Architektur-Bewertung
1. **Variante A vs C:** Reicht Single-Snapshot direkt vor `tune_off()`, oder ist Sampling-deque (analog `_fwdpwr_samples`) sicherer? Begruende mit Race-Conditions, Edge-Cases, KISS-Trade-off.
2. **Init-Stelle:** Ist `main_window.py:__init__` korrekt fuer Mixin-Pattern? Oder besser via `_init_tune_state`-Helper im Mixin selbst (Lazy-Init bei erstem TUNE)?
3. **Reset-Timing:** `_tune_last_valid_swr = None` AM ENDE von `_tune_post_swr_check` — passt das mit Token-Race in Re-Entry-Szenarien?

### Sicherheits-Bewertung (Pflicht!)
4. **ANT1-Pflicht:** Aenderung beruehrt nur SWR-Read-Pfad. Bestaetigung dass kein `set_tx_antenna`-Aufruf betroffen ist und ANT1-Hardware-Pflicht aus P63/P54 unveraendert bleibt.
5. **State-Sync:** Reset auf None am Ende — gibt's Pfade wo Post-Check NICHT laeuft (z.B. Disconnect-Branch Z.254-260) und `_tune_last_valid_swr` hängen bleibt? Wenn ja: explizites Reset am Disconnect-Ausgang noetig?
6. **Fallback bei freeze=None:** Defensive `swr_now = radio.last_swr` bei None — ist das wirklich sicher? Wenn `last_swr=1.0` durch Clamp-Bug, dann faellt der Fallback in den false-OK-Branch. **Sollte stattdessen abgebrochen werden mit Default-FAIL?**

### Edge-Cases
7. **Race: tune_off() vor Freeze:** Was wenn `tune_off()` aus Exception-Pfad vor Freeze laeuft? `_tune_last_valid_swr` bleibt None, Fallback liest geclampten Wert → Bug bleibt. Geplante Reihenfolge: Freeze ZUERST, dann tune_off. Bestaetigung?
8. **Mehrfach-TUNE Race:** Wenn User schnell hintereinander TUNE drueckt, koennte alter `_tune_last_valid_swr` (von TUNE 1) gelesen werden in Post-Check von TUNE 2? Token-Guard schuetzt schon, aber explizit checken.
9. **Disconnect-Branch:** Z.254 `if not self.radio.ip:` → Signal-Emit ohne Freeze-Read. Bedeutet `_tune_last_valid_swr` haengt bei Disconnect → potentieller Stale-State fuer naechsten TUNE. **Fix: Reset im Disconnect-Branch?**

### Test-Strategie
10. Sind die 6 Unit-Tests + 1 Source-Level-Test ausreichend?
11. Brauchen wir einen End-to-End-Integration-Test (mock radio mit kompletter `_tune_stop` → 2s sleep → `_tune_post_swr_check`)?

### Push-Empfehlung
12. **Push freigegeben (V3-Phase OK)?** Oder Findings die V3 noch braucht?

---

## Antwort-Format

Pro Finding:
- **F-Nummer + Status (🔴/🟠/🟡/⚪):** Kurz-Befund
- **Begruendung:** mit Zeilen-Verweis wenn relevant
- **Empfehlung:** uebernehmen / abweichen / verwerfen
- **Aenderung am Code:** falls noetig

Am Ende: **Push-Empfehlung (PUSH FREIGEGEBEN / ueberarbeiten)**.

---

**KISS-Hinweis:** SimpleFT8 ist Hobby-Funker-Tool, kein Contest-System. Lieber 9 LOC einfach als 50 LOC „sauber abstrahiert". Variante A bevorzugt wenn safety-OK.
