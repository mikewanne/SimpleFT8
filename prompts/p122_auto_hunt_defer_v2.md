Du bist Senior Python-Entwickler spezialisiert auf Amateurfunk-Software
und PySide6 (Signal statt pyqtSignal, Slot statt pyqtSlot). Das Projekt
ist ein Hobby-Funker-Tool für einen einzelnen Operator — NICHT Multi-Tenant.

Deine einzige Aufgabe: diesen Prompt kritisieren — NICHT das Problem lösen.
Strukturierte Liste: Lücken, Unklarheiten, Widersprüche, Verbesserungen.

KRITISCHE REGELN:
1. SCOPE-RESPEKT: Explizit als out-of-scope markiertes NICHT als Finding melden.
2. KISS VOR DEFENSIV: Komplexität nur wenn Wahrscheinlichkeit > 50%.
3. PROJEKT-BEZUG: Jedes Finding am konkreten Use-Case messen.
4. FORMAT: Tabelle Schwere | Finding | Datei:Zeile | Empfehlung.
   Severity: Bug (rot) / Risiko (orange) / Verbesserung (gelb) / Hinweis (grau).

Overengineering ist selbst ein Fehler den du benennen sollst.

---

# P122 V2 — Auto-Hunt-Stop bei laufendem QSO defern (3 Stop-Reasons)

## Kontext (Lesehilfe)

SimpleFT8 hat einen Auto-Hunt-Modus (`core/auto_hunt.py`), der nach
Frequency-Hopping-Logik selbstständig Stationen ruft. Drei Hard-Cap-
Stop-Reasons greifen UNGEFRAGT und brechen aktuell laufende
Stations-Rufe abrupt mitten in der QSO-Sequenz ab:

1. `timer_expired` — 10-Min-Hard-Cap (Bot-Tarn-Schutz, ethische
   Begrenzung — Mike's Spec, NICHT ändern)
2. `mouse_inactive_5min` — 5 Min ohne Mausbewegung (P67, zweite
   Schicht)
3. `totmann_expired` — 15-Min Operator-Presence-Watchdog

**Mike-Field-Beobachtung 25.05.2026 (Screenshot):** Während ein Ruf
`Sende RA9LL DA1MHH -17` läuft, feuert der 10-Min-Timer. `active=False`
wird sofort gesetzt, Cooldown geleert. Die noch laufenden Slot-Calls
laufen ins Leere — keine Antwort wird mehr verarbeitet, Loop endet mit
„RA9LL — Timeout". Mike-Spec: **„alles muss sauber durchlaufen, nicht
mittendrin beenden wenn autohunt oder totman läuft".**

P81 (v0.97.53) hat **die MELDUNG** über `_auto_hunt_stop_msg_pending`
deferiert — aber die AKTION läuft trotzdem sofort. P122 = AKTION
deferieren analog zur Meldung.

## Bestehende Patterns die wiederverwendet werden

- `main_window._qso_active_for_msg_defer()` (Z. 1054-1062) — liefert
  schon das exakte Defer-Kriterium: `qso_sm.state not in (IDLE,
  TIMEOUT, CQ_CALLING, CQ_WAIT)`. Aktiver Ruf-State = defer.
- `main_window._auto_hunt_stop_msg_pending` + `_flush_auto_hunt_stop_msg()`
  — P81-Pattern für deferierte Meldung. P122 baut auf das gleiche
  Flush-Muster in den 3 QSO-Ende-Pfaden:
  - `_on_qso_confirmed_visual` (✓ komplett)
  - `_on_qso_timeout` (✗ Timeout)
  - `_on_cancel` (HALT-Pfad, R1-F1 aus P81)

## 1. Ziel

`stop_auto_hunt(reason)` für die drei Defer-Reasons NICHT sofort
ausführen wenn QSO aktiv ist. Stattdessen: Pending-Reason setzen, bei
QSO-Ende echten Stop ausführen.

Die anderen 6 Reasons (`manual_halt`, `swr_block`, `band_change`,
`ft_mode_change`, `rx_mode_change`, `scoring_toggle`, `superseded`)
greifen WEITERHIN sofort — siehe Reason-Klassifizierung in §2.

## 2. Akzeptanzkriterien

### A. Reason-Klassifizierung (hartcodiert in core/auto_hunt.py)

```python
# Reasons die bei aktivem QSO bis QSO-Ende deferiert werden
_DEFER_REASONS = frozenset({
    "timer_expired",        # 10-Min-Hard-Cap
    "mouse_inactive_5min",  # 5-Min-Maus-Inaktivität
    "totmann_expired",      # 15-Min Operator-Presence
})
# Alle anderen Reasons greifen sofort (manual_halt, swr_block,
# band_change, ft_mode_change, rx_mode_change, scoring_toggle,
# superseded — Hardware-Safety oder Kontext-Wechsel).
```

### B. Defer-Logik in `core/auto_hunt.py:stop_auto_hunt()`

```python
def stop_auto_hunt(self, reason: str):
    # P122 (2026-05-25): Defer bei aktivem QSO für 3 Reasons.
    # Hardware-Safety + User-Aktion greifen weiterhin sofort.
    if reason in _DEFER_REASONS and self._is_qso_active_callback():
        if self._pending_stop_reason is None:
            self._pending_stop_reason = reason
            logger.info(f"[Auto-Hunt] Stop deferiert (reason={reason}, "
                        "QSO läuft — wird bei QSO-Ende ausgeführt)")
        else:
            # Mehrere Defer-Reasons während QSO → ERSTER gewinnt
            # (chronologisch — meist 10-Min-Cap vor Totmann)
            logger.info(f"[Auto-Hunt] Stop {reason} verworfen — "
                        f"{self._pending_stop_reason} ist schon pending")
        return  # Aktion NICHT ausführen
    # ... bisheriger Stop-Code (active=False, timer.stop, cooldown.clear,
    # emit auto_hunt_stopped)
```

### C. Callback-Injection (KISS — keine Cross-Modul-Imports)

`AutoHunt` muss erfahren wann QSO aktiv ist. Saubere Lösung:
Callback in `__init__`-Signatur:

```python
class AutoHunt(QObject):
    def __init__(self,
                 qso_sm,                     # bestehend
                 stations_provider,          # bestehend
                 ...,
                 is_qso_active_callback=None  # NEU
                 ):
        ...
        # Default-Callback wenn nicht übergeben (Tests, Legacy)
        self._is_qso_active_callback = is_qso_active_callback or (lambda: False)
        self._pending_stop_reason: Optional[str] = None
```

Aufruf in `main_window` wo `AutoHunt` instanziiert wird:

```python
self._auto_hunt = AutoHunt(
    qso_sm=self.qso_sm,
    stations_provider=...,
    ...,
    is_qso_active_callback=self._qso_active_for_msg_defer,
)
```

Damit nutzt P122 GENAU das gleiche Kriterium wie P81 — keine Drift,
keine Logik-Duplikation.

### D. Flush-Pfad in `main_window`

Bei QSO-Ende `auto_hunt.flush_pending_stop()` aufrufen — der prüft
ob Pending-Reason gesetzt ist, ruft dann `stop_auto_hunt()` mit dem
gespeicherten Reason auf (der ist dann nicht mehr in `_DEFER_REASONS`-
Pfad weil QSO inzwischen idle).

ABER: einfacher ist Defer im `auto_hunt` selbst zu lösen — `stop_auto_hunt`
mit dem Pending-Reason rekursiv aufrufen (kein Defer mehr da QSO idle):

```python
def flush_pending_stop(self):
    """Wird vom main_window bei QSO-Ende gerufen."""
    if self._pending_stop_reason is not None:
        reason = self._pending_stop_reason
        self._pending_stop_reason = None
        self.stop_auto_hunt(reason)  # Defer-Check schlägt jetzt fehl → echt stoppen
```

Aufrufer in `main_window` (3 Stellen analog P81-Pattern):
- `_on_qso_confirmed_visual`
- `_on_qso_timeout`
- `_on_cancel` (HALT-Pfad)

Plus: in `_flush_auto_hunt_stop_msg()` (P81) ANSCHLIESSEND `flush_pending_stop()`
aufrufen — saubere Reihenfolge: Stop-Aktion vor Meldung-Anzeige.

### E. Interaktion mit P81-Meldung

P81-Meldungstext sollte erst NACH `flush_pending_stop` angezeigt werden
damit die Reihenfolge im QSO-Log stimmt:

```
07:30:00 ✓ QSO mit DO1DP komplett
[Auto-Hunt-Stop intern, kein UI-Output]
⏸ Auto-Hunt gestoppt — 10 Min Hard-Cap abgelaufen.
```

Implementierung: Reihenfolge in den 3 QSO-Ende-Handlern:
1. QSO-Ende-Verarbeitung (Erfolg/Timeout/HALT)
2. `_auto_hunt.flush_pending_stop()`  ← Aktion
3. `_flush_auto_hunt_stop_msg()`     ← Meldung (P81)

### F. Edge-Case: manueller HALT während Defer-Pending

User klickt HALT während Pending-Reason gesetzt aber QSO noch läuft.
HALT ist sofortig (manual_halt nicht in DEFER_REASONS).

```python
def stop_auto_hunt(self, reason: str):
    if reason in _DEFER_REASONS and self._is_qso_active_callback():
        # Defer
        ...
        return
    # Sofortiger Stop — pending_stop_reason RESET damit kein doppelter Flush
    self._pending_stop_reason = None
    # ... rest
```

### G. Edge-Case: Defer-Pending + Band-Change

User wechselt Band während Pending-Reason gesetzt. `band_change` ist
sofortig → tritt in den Stop-Code unten ein → `_pending_stop_reason = None`
durch G-Reset. Sauber.

### H. Edge-Case: Defer-Pending + QSO-Ende + neuer Defer-Reason gleichzeitig

Unwahrscheinlich (Timer-Updates sind Slot-getaktet, QSO-Ende auch
Slot-getaktet, Race nahezu unmöglich). Falls doch: erster Pending
wird bei QSO-Ende geflusht (= echter Stop), zweiter Defer-Reason
greift dann auf bereits inaktiven `auto_hunt` → no-op.

```python
def stop_auto_hunt(self, reason: str):
    if not self.active and reason not in ("band_change", "mode_change"):
        # Auto-Hunt war schon aus — kein Stop nötig, kein Signal nochmal
        return
    ...
```

Defensive Check existiert vermutlich schon — vor V3 verifizieren.

### I. Logger-Ausgabe für Diagnostik

Pending + Flush logger.info-Einträge damit Mike + ich später
nachvollziehen können was wann passierte.

### J. Tests (~8 neu)

T1 `test_p122_defer_during_qso.py::test_timer_expired_defers_when_qso_active`
   AutoHunt mit `is_qso_active_callback=lambda: True` → `stop_auto_hunt
   ("timer_expired")` → `active=True`, `_pending_stop_reason ==
   "timer_expired"`.

T2 `test_timer_expired_immediate_when_qso_idle`
   Callback `lambda: False` → sofort gestoppt.

T3 `test_mouse_inactive_defers`
T4 `test_totmann_expired_defers`

T5 `test_manual_halt_immediate_even_with_qso_active`
   Callback `lambda: True` → `stop_auto_hunt("manual_halt")` →
   `active=False` SOFORT.

T6 `test_swr_block_immediate_even_with_qso_active`
T7 `test_band_change_immediate_even_with_qso_active`

T8 `test_flush_pending_stop_completes_deferred_stop`
   QSO aktiv → defer → QSO endet (Callback `lambda: False`) →
   `flush_pending_stop()` → echter Stop, Signal emittiert,
   `_pending_stop_reason == None`.

T9 `test_no_pending_no_flush` — `flush_pending_stop()` ohne Pending
   ist no-op.

T10 `test_first_defer_reason_wins`
    QSO aktiv → defer timer_expired → defer mouse_inactive →
    `_pending_stop_reason == "timer_expired"` (FIFO).

T11 Regression: alle 1838 bestehenden Tests bleiben grün.

## 3. Betroffene Dateien

- `core/auto_hunt.py` — `_DEFER_REASONS` Konstante, Konstruktor-Param
  `is_qso_active_callback`, Instanz-Var `_pending_stop_reason`, Defer-
  Branch in `stop_auto_hunt()`, neue Methode `flush_pending_stop()`,
  Reset-Branch im sofortigen Stop-Pfad (~30 LOC)
- `ui/main_window.py` — AutoHunt-Instanziation um Callback erweitern
  (~3 LOC), in den 3 QSO-Ende-Pfaden `_auto_hunt.flush_pending_stop()`
  vor `_flush_auto_hunt_stop_msg()` aufrufen
- `tests/test_p122_defer_during_qso.py` NEU — 10 Tests

## 4. Randbedingungen

- **CLAUDE.md Hardware-Pflicht:** keine Berührung mit TX/TUNE/PA. Pure
  State-Machine-Logik in Python.
- **Threading:** `stop_auto_hunt` läuft im GUI-Thread (Signal-Emits,
  Timer-Callbacks). Keine Lock-Sorgen.
- **Persistence:** keine. `_pending_stop_reason` ist Runtime-State.
  App-Crash bei Pending → User muss manuell stoppen, kein Persist nötig
  (Mike-Spec: Auto-Hunt-Sitzungen sind kurz, 10 Min).
- **P67 Bot-Tarn-Schutz unverändert:** 10-Min-Hard-Cap-Timer läuft
  weiter, nur die SICHTBARE Stop-Aktion wird kurz verzögert (bis QSO-
  Ende, max wenige Slots = wenige Sekunden). Mike's Tarn-Logik bleibt
  intakt.
- **P81-Meldungspfad bleibt unverändert** — P122 ergänzt nur den
  Aktions-Defer.
- **Tests-Pflicht:** `QT_QPA_PLATFORM=offscreen pytest tests/ -q` grün
  vor Commit.

## 5. Nicht im Scope

- `manual_halt`-Verhalten (User-Notbremse — sofort, by design)
- `swr_block`-Verhalten (Hardware-Safety — sofort, by design)
- Erweiterung der Defer-Liste auf `band_change` / `mode_change`
  (Hardware-Kontext-Wechsel — laufender Ruf wäre ohnehin obsolet)
- UI-Anzeige eines „Stop pending" Status während Defer (KISS —
  Mike sieht beim Flush ohnehin die deferierte Meldung)
- 10-Min-Hard-Cap-Toleranz vergrößern (Bot-Tarn-Schutz bleibt!)
- Persistenz des Pending-State über App-Restarts
- Reset-Pfade für `_pending_stop_reason` außerhalb stop_auto_hunt
  + flush_pending_stop (sollten nicht nötig sein, vor V3 prüfen)

## 6. Testbarkeit

- Pure-Python-Logik in `core/auto_hunt.py`, perfekt unit-testbar
- Mock-Callback `lambda: True/False` simuliert QSO-State ohne
  `QSOStateMachine`-Setup
- 11 Tests decken alle 3 Defer-Reasons + alle 4 Sofort-Reasons + die
  Edge-Cases (Flush, FIFO, no-pending) ab

## Self-Review-Hinweise (V1 → V2 Schritt 1b)

**Was ich noch nicht gut habe in V1:**

- **A1 Callback statt direkter qso_sm-Reference:** Saubere Lösung,
  aber bricht Backward-Compat wenn alte Tests `AutoHunt(qso_sm=...)`
  ohne Callback bauen. Lösung: Default-Param `is_qso_active_callback=None`
  + Fallback auf `lambda: False` (= alte Verhalten = nie deferieren).
  Damit bleiben alle bisherigen Test-Konstruktoren funktional.
- **A2 First-Wins vs Last-Wins bei multiple Defers:** Mike-Spec
  unklar. „Erster gewinnt" ist KISS (FIFO). „Letzter gewinnt" wäre
  Last-Status-prioritär. → First-Wins gewählt (10-Min-Cap kommt
  typisch vor Maus-Inaktivität-Trigger, und Reason-Text der angezeigt
  wird sollte stabil bleiben).
- **A3 Flush-Reihenfolge:** Aktion VOR Meldung — sonst sieht User
  „Auto-Hunt gestoppt"-Meldung BEVOR der interne Stop läuft.
  Verifiziert in §E.
- **A4 Reset bei sofortigem Stop:** Wichtig! Wenn User HALT klickt
  während Pending → Pending muss raus damit kein doppelter Flush bei
  späterem QSO-Ende greift. In §F adressiert.
- **A5 Defer-Reason-Anzahl:** Drei Reasons (timer/mouse/totmann)
  reichen für die Spec. Alle anderen sind Kontext-Wechsel oder Safety.
- **A6 Edge-Case `not self.active`:** Wenn Defer-Reason kommt aber
  Auto-Hunt schon manuell gestoppt → würde fälschlich Pending setzen.
  Vor V3 prüfen ob `if not self.active: return` als allererste Zeile
  in `stop_auto_hunt` schon existiert (Z. 200 `self.active = False`
  — das ist das SETZEN, nicht das CHECK). Defensive Check muss vermutlich
  ergänzt werden.
- **A7 `auto_hunt_stopped`-Signal-Emission bei Defer:** NICHT
  emittieren (sonst zeigt UI „gestoppt" obwohl noch aktiv). Wird
  später beim echten Stop emittiert.
