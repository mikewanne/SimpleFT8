# P76-A SWR-Safety-Bug — Final-R1 Prompt

**Du bist DeepSeek-V4-pro im Workflow V1 → V2 → R1 → V3 → Code → **Final-R1**.**

Final-Push-Freigabe-Check fuer SimpleFT8 v0.97.49 P76-A SAFETY-Bug-Fix.

---

## Was wurde gemacht (kurz)

**Bug:** Mike-Field-Test 17m: SWR 2.7 (>Limit 2.5) wurde als „TUNE OK SWR 1.0" geloggt — Safety-relevant (User glaubte Band sicher fuer 70-W-QSO).

**Root:** `_tune_post_swr_check` liest `radio.last_swr` 2 s NACH `tune_off()`. FlexRadio Meter-Loop liefert ohne TX-Traeger Werte <1.0 die in `_handle_meter` auf 1.0 geclamped werden → `_last_swr` ueberschrieben → false-OK.

**Fix (Variante A, KISS):**
1. State-Var `_tune_last_valid_swr: float | None = None` in `main_window.py:__init__`
2. Freeze `_tune_last_valid_swr = radio.last_swr` direkt VOR `radio.tune_off()` in `_tune_stop`
3. Im Post-Check gefrorenen Wert lesen (kein Fallback auf `radio.last_swr`)
4. Bei `None` oder `<1.0` → FAIL (else-Branch, kein false-OK)
5. Reset auch im Disconnect-Branch (Stale-State-Schutz)

**R1-V4-pro-Findings alle uebernommen:**
- F5: kein `radio.last_swr`-Fallback
- F6: Disconnect-Reset
- F13: `<1.0` ebenfalls FAIL

**Tests:** 1463 → 1474 (+11 P76-A T1-T11). Alle grün. Plus 2 Helper-Anpassungen in `test_p54_fix.py` + `test_p54_auto_tune.py` (Mock-Setup `obj._tune_last_valid_swr = swr` analog `obj.radio.last_swr = swr`).

---

## Geaenderte Files (Diff im Anhang)

- `main.py` — APP_VERSION 0.97.48 → 0.97.49
- `ui/main_window.py` — Init-Variable + Marker-Kommentar
- `ui/mw_tx.py` — 2 Code-Bloecke (Freeze in `_tune_stop`, Read+Reset+FAIL in `_tune_post_swr_check` inkl. Disconnect-Branch-Reset)
- `tests/test_p76_swr_safety.py` — NEU 11 Tests
- `tests/test_p54_fix.py` — Helper `_make_mw_tx_for_post_check` + 1 Zeile
- `tests/test_p54_auto_tune.py` — Helper `_make_mw_tx_mock` + 1 Zeile

---

## Final-Pruef-Auftrag (kritisch!)

Bitte beantworte mit Schwerpunkt:

### 1. Code-Korrektheit
1.1 Freeze-Reihenfolge: ist `self._tune_last_valid_swr = self.radio.last_swr` GARANTIERT vor `self.radio.tune_off()`? Verifiziere im Anhang.
1.2 Post-Check-Read: liest `swr_frozen = self._tune_last_valid_swr` als ALLERERSTE Zeile nach dem Disconnect-Guard?
1.3 Reset: passiert IMMER nach Read (unabhaengig von success/fail)?
1.4 FAIL-Wert: `swr_limit + 1.0` → garantiert > `swr_limit` auch bei extremen Settings (z.B. swr_limit=5.0 → fail=6.0 > 5.0 ✓)?

### 2. ANT1-Hardware-Pflicht
2.1 Beruehrt KEIN `set_tx_antenna`-Call in den NEU eingefuegten Bloecken? (Test T9 prueft das, aber verifiziere manuell)
2.2 Geaenderter Code beeintraechtigt KEINE existierenden P63/P54 ANT1-Pfade?

### 3. Stale-State-Schutz (R1-F6)
3.1 Reset im Disconnect-Branch korrekt platziert (VOR `auto_tune_done.emit`)?
3.2 Gibt es weitere `return`-Pfade in `_tune_post_swr_check` die KEIN Reset machen?
3.3 Was passiert wenn `_tune_post_swr_check` durch Exception abbricht? → `_tune_last_valid_swr` haengt → naechster TUNE liest stale. Akzeptabel oder Reset im try/finally noetig?

### 4. Race-Conditions
4.1 Mehrfach-TUNE: Token-Guard schuetzt Post-Check, aber `_tune_last_valid_swr` ist nicht token-getrennt. Wenn TUNE-2 in `_tune_stop` Freeze ueberschreibt waehrend TUNE-1 Post-Check noch laeuft — Problem?
4.2 Re-Entry-Cancel via Sub-Event-Loop: 1. `_tune_stop` schreibt Freeze + tune_off + plant Post-Check. 2. Cancel-Click via Sub-Event-Loop ruft `_tune_stop(None)` → wegen `_tune_stop_active=True` returnt early ohne weiteren Freeze. ✓ OK?

### 5. Regression
5.1 Bestehende P54/P54-FIX-Tests laufen alle gruen (verifiziert: 1474 passed). Helper-Anpassung in 2 Files akzeptabel (1 Zeile pro File)?
5.2 Andere Code-Pfade die `radio.last_swr` lesen — sind die durch unsere Aenderung beeinflusst? (Suche bestaetigt: nur `_tune_post_swr_check` Z.262 war Bug-Stelle, sonst `swr_after_match` Z.178 in `_tune_stop` selbst (TX aktiv, valid))

### 6. Test-Coverage
6.1 11 Tests reichen (T1-T11)?
6.2 Welche Test-Luecken bleiben? (z.B. Multi-TUNE-Race in 4.1?)

### 7. KISS
7.1 9 LOC Code-Aenderung + 5 LOC FAIL-Branch + 1 LOC Disconnect-Reset = ~15 LOC. KISS gewahrt?
7.2 Alternative Sampling-deque (Variante C) waere ~50 LOC mehr — Verzicht gerechtfertigt?

### 8. Mike-Field-Test-Vorbereitung
8.1 Mike-Fall (17m SWR 2.7): wird er nach Fix korrekt als „TUNE fehlgeschlagen — SWR 2.7" geloggt + Marker setzen?
8.2 Edge-Case: was wenn SWR exakt = swr_limit (z.B. 2.5)? Z.299 `if swr_now <= swr_limit:` → SWR-OK-Branch (inklusive). ✓ Spec-konform?

---

## Antwort-Format

Pro Punkt:
- ✅ OK / 🟡 Hinweis / 🟠 Risiko / 🔴 Blocker
- Kurz-Begruendung
- Empfehlung (Push freigeben / ueberarbeiten)

**Am Ende:** `PUSH FREIGEGEBEN` oder `ueberarbeiten + welche Aenderungen`.

---

## Code-Anhang (zur Verifikation)

### main_window.py:__init__ (neue Zeile am Ende des `_tune_*`-Blocks)
```python
# P76-A SAFETY (v0.97.49): SWR-Wert direkt vor tune_off() eingefroren.
# FlexRadio liefert nach tune_off() ohne TX-Traeger Mess-Artefakte <1.0
# die in _handle_meter auf 1.0 geclamped werden → ueberschreibt
# _last_swr → Post-Check 2s spaeter liest 1.0 → false-OK-Bug.
# Freeze in _tune_stop direkt vor tune_off, Read+Reset in
# _tune_post_swr_check. Siehe HISTORY P76-A.
self._tune_last_valid_swr: float | None = None
```

### mw_tx.py:_tune_stop (Freeze-Block, eingefuegt VOR tune_off())
```python
# P76-A SAFETY (v0.97.49): SWR einfrieren BEVOR tune_off().
# Nach tune_off() liefert FlexRadio Meter-Updates ohne TX-Traeger
# Werte <1.0 die in _handle_meter auf 1.0 geclamped werden →
# ueberschreibt radio._last_swr → Post-Check 2s spaeter liest 1.0
# → false-OK-Bug (Phase-B-Skip-Pfad: echter SWR 2.7 verloren).
# Freeze unconditional (kein radio.ip-Guard — last_swr ist
# lokale Property, kein Hardware-Zugriff).
self._tune_last_valid_swr = self.radio.last_swr

# tune_off + VFO+Power zurück
self.radio.tune_off()
```

### mw_tx.py:_tune_post_swr_check (Disconnect-Branch + Read+Reset+FAIL)
```python
if not self.radio.ip:
    # P76-A SAFETY (R1-F6): Stale-State-Reset auch im Disconnect-Pfad,
    # sonst haengt gefrorener Wert von altem TUNE und naechster TUNE
    # nach Re-Connect liest stale Wert.
    self._tune_last_valid_swr = None
    if is_auto and dlg is not None:
        print(f"[P54a] DONE FAIL reason=disconnect "
              f"band={self.settings.band} mode={self.settings.mode}")
        dlg.auto_tune_done.emit(False, 0.0, 0.0)
    return

# P76-A SAFETY (v0.97.49): gefrorenen Wert lesen (waehrend TX gemessen).
# R1-F5+F13: KEIN Fallback auf radio.last_swr — der koennte durch
# Clamp-Bug (1.0) faelschlich SWR-OK signalisieren. Bei None oder <1.0
# garantiert in else-Branch (SWR-bad → Marker setzen + Hinweis).
swr_frozen = self._tune_last_valid_swr
self._tune_last_valid_swr = None  # IMMER Reset (Stale-Schutz)

if swr_frozen is None or swr_frozen < 1.0:
    print(f"[P76-A] WARNUNG: Freeze ungueltig (got {swr_frozen!r}) "
          f"→ FAIL-Behandlung (kein false-OK durch Clamp-Bug)")
    _swr_limit_fail = self.settings.get("swr_limit", 3.0)
    swr_now = _swr_limit_fail + 1.0  # garantiert > limit → else-Branch
else:
    swr_now = swr_frozen
swr_limit = self.settings.get("swr_limit", 3.0)
band = self.settings.band.upper()
```

### tests/test_p76_swr_safety.py — 11 Tests T1-T11 (Source-Level + Functional)

T1 Init, T2 Freeze in stop, T3 Reihenfolge Freeze<tune_off, T4 Read+Reset, T5 kein last_swr-Fallback, T6 FAIL-Branch bei None/<1.0, T7 Disconnect-Reset, T8 Reset-Reihenfolge, T9 kein set_tx_antenna in P76-A-Bloecken, T10 functional Mike-Fall, T11 functional None→FAIL.
