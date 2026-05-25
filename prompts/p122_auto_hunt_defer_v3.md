# P122 V3 — Auto-Hunt-Stop bei laufendem QSO defern (3 Stop-Reasons)

> R1-Findings (V2-Review V4-pro) eingearbeitet — alle 5 Findings valide,
> keine Halluzinationen. F1 war ein V2-Fehler von mir (`AutoHunt.__init__`
> hat keine bestehenden Params), F2 war ein Widerspruch §2.D vs §2.E,
> F3 ist Defensive-Check-Pflicht, F4+F5 trivial korrigiert.

## 1. Ziel

`stop_auto_hunt(reason)` für 3 Defer-Reasons (`timer_expired`,
`mouse_inactive_5min`, `totmann_expired`) NICHT sofort ausführen wenn
QSO aktiv ist. Stattdessen: Pending-Reason setzen, bei QSO-Ende echten
Stop ausführen. Die anderen Reasons greifen unverändert sofort.

## 2. Akzeptanzkriterien (R1-korrigiert)

### A. Reason-Klassifizierung

```python
# core/auto_hunt.py, Modul-Ebene
_DEFER_REASONS = frozenset({
    "timer_expired",        # 10-Min-Hard-Cap
    "mouse_inactive_5min",  # 5-Min-Maus-Inaktivität (P67)
    "totmann_expired",      # 15-Min Operator-Presence
})
```

### B. Konstruktor-Erweiterung (R1-F1 korrigiert — KISS, nur 1 Param)

`AutoHunt.__init__(self)` hat heute KEINE Parameter (Z. 94 verifiziert).
Wird zu:

```python
def __init__(self, is_qso_active_callback=None):
    super().__init__()
    self.active: bool = False
    # ... bisheriger Init ...
    # P122 (2026-05-25): Defer-Mechanik für Stop bei aktivem QSO.
    # Callback liefert True wenn QSO im aktiven Ruf-State ist.
    # Default-Fallback `lambda: False` = nie deferieren (Test/Legacy).
    self._is_qso_active_callback = is_qso_active_callback or (lambda: False)
    self._pending_stop_reason: Optional[str] = None
```

Default-Wert `None` → Fallback auf `lambda: False` → bisheriges
Verhalten bei Tests/Legacy-Konstruktion ohne Callback. **Backward-
compat garantiert.**

Aufruf in `main_window`:

```python
# wo AutoHunt() heute instanziiert wird, Callback ergänzen:
self._auto_hunt = AutoHunt(is_qso_active_callback=self._qso_active_for_msg_defer)
```

`_qso_active_for_msg_defer()` existiert bereits (Z. 1054-1062,
P81-Pattern) und nutzt:
```python
qso_sm.state not in (IDLE, TIMEOUT, CQ_CALLING, CQ_WAIT)
```

### C. Defer-Logik in `stop_auto_hunt()` (R1-F3 mit Defensive-Check)

```python
def stop_auto_hunt(self, reason: str):
    # P122 (2026-05-25) R1-F3: Defensive Idempotenz — wenn bereits
    # inaktiv und KEIN Pending, ist nichts zu tun.
    if not self.active and self._pending_stop_reason is None:
        return

    # P122: Defer für 3 Stop-Reasons wenn QSO aktiv.
    if reason in _DEFER_REASONS and self._is_qso_active_callback():
        if self._pending_stop_reason is None:
            self._pending_stop_reason = reason
            logger.info(f"[Auto-Hunt] Stop deferiert (reason={reason}, "
                        "QSO läuft — wird bei QSO-Ende ausgeführt)")
        else:
            # FIFO: erster Defer-Reason gewinnt
            logger.info(f"[Auto-Hunt] Stop {reason} verworfen — "
                        f"{self._pending_stop_reason} ist schon pending")
        return  # KEIN active=False, KEIN Signal-Emit

    # Sofortiger Stop (alle anderen Reasons ODER QSO idle).
    # P122: Pending-Reset bei sofortigem Stop (HALT/Band/SWR überschreibt
    # einen evtl. gesetzten Defer-Reason).
    self._pending_stop_reason = None
    self.active = False
    self._current_target = None
    self._auto_hunt_timer.stop()

    if reason != "totmann_expired":
        self._cooldown.clear()
        self._last_tx_even = None

    logger.info(f"[Auto-Hunt] Stop (reason={reason})")
    print(f"[Auto-Hunt] Gestoppt — {reason}")
    self.auto_hunt_stopped.emit(reason)
```

### D. Flush-Methode `flush_pending_stop()` (R1-F2 klargestellt)

```python
def flush_pending_stop(self):
    """Wird vom main_window bei QSO-Ende gerufen.

    Wenn Pending-Reason gesetzt ist, ECHTER Stop durchführen
    (Defer-Check schlägt jetzt fehl da QSO idle).
    """
    if self._pending_stop_reason is None:
        return
    reason = self._pending_stop_reason
    self._pending_stop_reason = None
    # Rekursiver Aufruf — Defer-Check schlägt fehl (QSO idle), echter Stop.
    self.stop_auto_hunt(reason)
```

### E. Aufrufpunkte für flush_pending_stop (R1-F2 — eindeutige Reihenfolge)

**EINZIG in den 3 QSO-Ende-Handlern**, **NICHT** in
`_flush_auto_hunt_stop_msg` (das bleibt P81-Meldungspfad, separat):

1. `_on_qso_confirmed_visual(...)` — QSO ✓ komplett
2. `_on_qso_timeout(...)` — QSO ✗ Timeout
3. `_on_cancel(...)` — HALT-Pfad (User-Notbremse beendet QSO)

Reihenfolge in jedem Handler:
1. Bestehende QSO-Ende-Verarbeitung
2. `self._auto_hunt.flush_pending_stop()`   ← AKTION (P122)
3. `self._flush_auto_hunt_stop_msg()`       ← MELDUNG (P81)

Damit: Stop-Aktion läuft VOR Meldung-Anzeige → User sieht zuerst
QSO-Ende-Eintrag, dann „Auto-Hunt gestoppt"-Hinweis. Sauber.

### F. Edge-Cases — verifiziert

- **manual_halt während Defer-Pending:** `manual_halt` NICHT in
  `_DEFER_REASONS` → sofortiger Stop-Pfad → `_pending_stop_reason = None`
  + `active = False`. Folgender `flush_pending_stop()` bei QSO-Ende ist
  no-op weil Pending bereits geleert.
- **Band-/Mode-Change während Defer-Pending:** analog, sofort-Pfad
  resetted Pending.
- **Mehrfach-Defer (Timer + Maus):** First-Wins (FIFO) — siehe C.
- **AutoHunt schon inaktiv:** Defensive Check (R1-F3) returnt sofort.
- **Defer-Pending + Crash:** `_pending_stop_reason` ist Runtime-State,
  geht verloren — kein Persist nötig (Mike-Spec: Auto-Hunt = kurze
  Sessions, 10 Min).

### G. Logger + Print-Diagnostik

`logger.info` + `print` bei jedem Defer/Flush damit Mike +
Diagnose-Logs den Pfad nachvollziehen können.

### H. Tests (R1-F5 — alle Tests müssen mit Backward-compat-Default klappen)

T1-T10 (Pure-Python in `tests/test_p122_auto_hunt_defer.py`, neu):

T1 `test_timer_expired_defers_when_qso_active`
   AutoHunt(`lambda: True`) → `stop_auto_hunt("timer_expired")` →
   `active=True`, `_pending_stop_reason == "timer_expired"`, KEIN
   Signal emittiert.

T2 `test_timer_expired_immediate_when_qso_idle`
   AutoHunt(`lambda: False`) → sofort gestoppt, Signal emittiert.

T3 `test_mouse_inactive_defers` (analog T1)
T4 `test_totmann_expired_defers` (analog T1, mit Spezial-Cleanup-Logik
   beachten: bei `totmann_expired` werden Cooldown + last_tx_even NICHT
   geleert — auch beim deferred-flushed-Stop)

T5 `test_manual_halt_immediate_even_with_qso_active`
   AutoHunt(`lambda: True`) → `stop_auto_hunt("manual_halt")` → sofort
   `active=False`.

T6 `test_swr_block_immediate_even_with_qso_active`
T7 `test_band_change_immediate_even_with_qso_active`

T8 `test_flush_pending_stop_completes_deferred_stop`
   Defer (active=True, pending=timer_expired) → Callback wechselt auf
   `lambda: False` → `flush_pending_stop()` → echter Stop + Signal.

T9 `test_no_pending_no_flush` — Idempotent: `flush_pending_stop()` ohne
   Pending ist no-op.

T10 `test_first_defer_reason_wins`
    QSO aktiv → defer timer_expired → defer mouse_inactive →
    `_pending_stop_reason == "timer_expired"`.

T11 `test_immediate_stop_resets_pending`
    QSO aktiv → defer timer_expired → manual_halt → Pending raus,
    Folge-Flush ist no-op.

T12 `test_legacy_constructor_no_callback_never_defers`
    AutoHunt() ohne Callback → Default `lambda: False` → kein Defer
    möglich, alle 1838 alten Tests bleiben unverändert.

T13 `test_defensive_check_double_stop_idempotent`
    Schon inaktiv + kein Pending → `stop_auto_hunt("manual_halt")` ist
    no-op, kein zweites Signal.

Regression: alle 1838 bestehenden Tests bleiben grün.

## 3. Betroffene Dateien

| Datei | Δ LOC | Änderung |
|---|---|---|
| `core/auto_hunt.py` | +30/-3 | `_DEFER_REASONS`, Konstruktor +1 optionaler Param, `_pending_stop_reason`, Defer-Branch + Defensive-Check in `stop_auto_hunt`, neue Methode `flush_pending_stop()` |
| `ui/main_window.py` | +6 | AutoHunt-Instanziation um Callback erweitern; in 3 QSO-Ende-Handlern `flush_pending_stop()` vor `_flush_auto_hunt_stop_msg()` ergänzen |
| `tests/test_p122_auto_hunt_defer.py` NEU | +200 | 13 Tests |

## 4. Randbedingungen

- **Hardware-Pflicht:** keine TX/TUNE/PA-Berührung. Pure State-Machine.
- **Threading:** GUI-Thread, keine Lock-Sorgen.
- **Persistence:** keine — Pending ist Runtime-State.
- **P67 Bot-Tarn-Schutz:** 10-Min-Hard-Cap-Timer läuft weiter, nur die
  SICHTBARE Stop-Aktion wird verzögert (max ein paar Slots = 15-30s
  pro deferiertem QSO). Bot-Tarn-Charakter bleibt erhalten.
- **P81-Meldungspfad unverändert** — P122 ergänzt nur den Aktions-Defer.
- **Tests-Pflicht:** `QT_QPA_PLATFORM=offscreen pytest tests/ -q` grün.

## 5. Nicht im Scope

- `manual_halt`/`swr_block`/`band_change`/`mode_change`/`rx_mode_change`/
  `scoring_toggle`/`superseded` Defer (Hardware-Safety oder Kontext-
  Wechsel — sofort by design)
- UI-Anzeige eines „Stop pending"-Status während Defer
- 10-Min-Hard-Cap-Verlängerung
- Persistenz des Pending-State über App-Restarts

## R1-Findings-Bilanz V2-Review

| # | Severity | Status | Wie adressiert |
|---|---|---|---|
| 1 | 🟠 V2-Falschannahme über `__init__`-Params | Korrigiert | Nur 1 optionaler Param `is_qso_active_callback=None` |
| 2 | 🟠 §2.D vs §2.E widersprechen | Korrigiert | Flush nur in 3 QSO-Ende-Handlern, NICHT in `_flush_auto_hunt_stop_msg` |
| 3 | 🟠 Kein Defensive-Check in `stop_auto_hunt` | Adressiert | `if not self.active and pending is None: return` |
| 4 | 🟡 Overengineering durch erfundene Params | Korrigiert mit F1 |
| 5 | 🟠 Backward-compat-Risiko bei Konstruktor | Adressiert | Default-Param `None` + Fallback-Lambda |

**Halluzinationen:** keine. Alle 5 Findings verifizierbar per
Code-Read (`auto_hunt.py:94` def __init__(self):).

## Implementierungs-Reihenfolge

Atomarer Commit-Plan:

1. **Commit 1:** P122 Code (`core/auto_hunt.py` + `ui/main_window.py`)
2. **Commit 2:** P122 Tests
3. **Commit 3:** P122 Doku (HISTORY/HANDOFF/CLAUDE/TODO/Memory)

Push nur auf Mike-Freigabe.
