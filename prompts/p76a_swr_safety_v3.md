# P76-A SWR-Safety-Bug — V3 (nach R1-V4-pro)

**Workflow-Schritt:** V1 → V2 → R1 → **V3** → Code → Final-R1
**Datum:** 18.05.2026 nach Compact
**Vorgaenger:** prompts/p76a_swr_safety_v2.md + prompts/p76a_swr_safety_r1.md

---

## R1-V4-pro-Findings & Entscheidungen

### F1-F4, F7-F8, F10-F12 — ✅ Bestaetigt, keine Aenderung

### F5 🟡 — UEBERNOMMEN (sicherheitsrelevant!)

**Problem:** V2-Plan hatte `swr_now = self.radio.last_swr` als Fallback bei `_tune_last_valid_swr is None`. Wenn Freeze fehlschlug (Exception-Pfad), faellt der Fallback **direkt in den Clamp-1.0-Bug** den wir gerade fixen wollen.

**Loesung:** Bei `None` oder `<1.0` → **FAIL** statt Fallback. Setze `swr_now = swr_limit + 1.0` damit garantiert der else-Branch (SWR-bad, Marker setzen, Hinweis) greift.

### F6 🔴 — UEBERNOMMEN (Stale-State-Bug)

**Problem:** Disconnect-Branch Z.254-260 in `_tune_post_swr_check` macht `return` ohne Reset von `_tune_last_valid_swr`. Wenn Radio nach TUNE disconnected → Wert haengt → nächster TUNE nach Re-Connect liest stale Wert von altem TUNE.

**Loesung:** Reset im Disconnect-Branch explizit setzen.

### F9 🟡 — Token-Schutz reicht, keine Aenderung

### F13 🟡 — UEBERNOMMEN (analog F5)

Bei `swr_now < 1.0` ebenfalls FAIL (physikalisch unmoeglich, deutet auf Clamp-Bug oder Mess-Artefakt).

---

## Finaler Code-Plan

### Aenderung 1: `ui/main_window.py:__init__`

Nach existierender `_tune_*`-Block:
```python
# P76-A SAFETY: SWR-Wert direkt vor tune_off() eingefroren
# (FlexRadio liefert nach tune_off() <1.0-Artefakte die auf 1.0 geclamped
# werden → false-OK ohne diesen Freeze).
self._tune_last_valid_swr: float | None = None
```

### Aenderung 2: `ui/mw_tx.py:_tune_stop` direkt VOR Z.192 `radio.tune_off()`

```python
# P76-A SAFETY: SWR einfrieren BEVOR tune_off().
# Nach tune_off() liefert FlexRadio Meter-Updates ohne TX-Traeger
# Werte <1.0 die auf 1.0 geclamped werden → false-OK-Bug bei
# Phase-B-Skip-Pfad (siehe HISTORY P76-A).
self._tune_last_valid_swr = self.radio.last_swr
```

### Aenderung 3: `ui/mw_tx.py:_tune_post_swr_check`

**3a:** Disconnect-Branch Z.254-260 ergaenzen (R1-F6):
```python
if not self.radio.ip:
    # P76-A SAFETY (R1-F6): Reset Stale-State auch im Disconnect-Pfad
    self._tune_last_valid_swr = None
    if is_auto and dlg is not None:
        print(f"[P54a] DONE FAIL reason=disconnect ...")
        dlg.auto_tune_done.emit(False, 0.0, 0.0)
    return
```

**3b:** Z.262 ersetzen (R1-F5 + F13):
```python
# P76-A SAFETY: gefrorenen Wert lesen (waehrend TX gemessen).
# R1-F5+F13: KEIN Fallback auf radio.last_swr — der koennte durch
# Clamp-Bug (1.0) faelschlich SWR-OK signalisieren. Bei None oder <1.0
# garantiert in else-Branch (SWR-bad → Marker setzen + Hinweis).
swr_frozen = self._tune_last_valid_swr
self._tune_last_valid_swr = None  # IMMER Reset (Stale-Schutz)

if swr_frozen is None or swr_frozen < 1.0:
    print(f"[P76-A] WARNUNG: Freeze ungueltig (got {swr_frozen!r}) "
          f"→ FAIL-Behandlung")
    swr_limit_for_fail = self.settings.get("swr_limit", 3.0)
    swr_now = swr_limit_for_fail + 1.0  # garantiert > limit → else-Branch
else:
    swr_now = swr_frozen
```

---

## Aktualisierte Akzeptanz-Kriterien

- **AC1:** Bei echtem SWR > Limit waehrend TUNE → Post-Check liest gefrorenen Wert (z.B. 2.7) → SWR-bad-Branch → Band-Marker gesetzt
- **AC2:** Bei echtem SWR <= Limit waehrend TUNE → Post-Check liest gefrorenen Wert (z.B. 1.5) → SWR-OK-Branch → korrekter SWR im Log
- **AC3:** Wenn Freeze fehlschlug (None) ODER < 1.0 → FAIL-Behandlung (else-Branch, Marker bleibt rot, kein false-OK)
- **AC4:** Reset auf None NACH Read im Post-Check + im Disconnect-Branch
- **AC5:** Auto-Tune-Pfad sendet korrektes `auto_tune_done(success, swr_real, fwdpwr)` (kein 1.0 mehr aus Clamp-Bug)
- **AC6:** ANT1-Hardware-Pflicht aus P63/P54 unveraendert (Aenderung beruehrt nur SWR-Read-Pfad)

---

## Test-Bedarf (V3 final)

**T1** — Freeze setzt SWR korrekt vor tune_off (Source-Level + Functional)
**T2** — Post-Check liest gefrorenen Wert bei SWR-OK (1.5 statt 1.0)
**T3** — Post-Check liest gefrorenen Wert bei SWR-bad (2.7 statt 1.0) → Marker gesetzt
**T4** — Reset auf None nach Post-Check
**T5** — None-Fallback geht in FAIL (R1-F5)
**T6** — <1.0-Fallback geht in FAIL (R1-F13)
**T7** — Disconnect-Branch reset `_tune_last_valid_swr` (R1-F6)
**T8** — Stale-State nach Disconnect+ReConnect: neuer TUNE sieht None statt alten Wert
**T9** — Source-Level: `_tune_last_valid_swr = self.radio.last_swr` MUSS VOR `self.radio.tune_off()` stehen
**T10** — Source-Level: `_tune_last_valid_swr = None` im Disconnect-Branch
**T11** — ANT1-Pflicht-Schutz: kein `set_tx_antenna`-Aufruf in den 3 geaenderten Code-Bloecken (Source-Level)

---

## Atomare Commits (V3 final)

- **C1** `ui/main_window.py` Init-Variable
- **C2** `ui/mw_tx.py` Freeze in `_tune_stop`
- **C3** `ui/mw_tx.py` Read+Reset+FAIL-Path in `_tune_post_swr_check` (inkl. Disconnect-Branch)
- **C4** `tests/test_p76_swr_safety.py` NEU (T1-T11)
- **C5** APP_VERSION 0.97.48 → 0.97.49
- **C6** HISTORY.md + HANDOFF.md + CLAUDE.md + TODO.md + Memory Update

---

## Field-Test (V3 final)

- **F1** (Radio noetig): 17m TUNE mit echtem SWR ≥ 2.5 (Mike's Original-Reproduktion)
  - **Erwartung:** „⚠ Tuner konnte nicht matchen — SWR 2.7 > Limit 2.5" im Live-Log + Band-Marker setzt sich (Banner zeigt 17m rot)
- **F2** (Radio): TUNE auf Band mit niedrigem SWR (z.B. 40m)
  - **Erwartung:** „✓ TUNE OK — SWR 1.2" mit korrektem Wert, keine 1.0
- **F3** (Radio): Bandwechsel mit Auto-Tune
  - **Erwartung:** AutoTuneDialog zeigt echten SWR-Wert nach Phase B
- **F4** (Radio): TUNE → Disconnect → Re-Connect → erneut TUNE
  - **Erwartung:** Kein stale-State, sauberes neues Ergebnis
- **F5** (ohne Radio): Bestehende Tests laufen alle gruen
  - **Erwartung:** 1463 + 11 (P76) = 1474 grün

---

## Open Items vor Code

Keine offenen Punkte mehr. Alle R1-Findings adressiert.

**Naechster Schritt:** Code implementieren.
