# Final-Review: P167 Einschub-Reentrancy-Fix (implementiert)

Push-Freigabe ja/nein + Findings 🔴/🟠/🟡. Knapp.

## Umgesetzt (gegen deinen Plan: Option A + HALT-Race-Schutz)
`ui/mw_qso.py`:
```python
def _p158_maybe_start_inserted_call(self):
    msg = self._qso_pending_insert
    if msg is None:
        return
    self._qso_pending_insert = None
    self._p158_insertable.clear()
    # P167: NICHT synchron — Reentrancy. Defer in nächsten Event-Tick.
    self._deferred_insert_msg = msg
    QTimer.singleShot(0, self._execute_deferred_insert)

def _execute_deferred_insert(self):
    msg = self._deferred_insert_msg
    self._deferred_insert_msg = None
    if msg is None:
        return
    self._on_station_clicked(msg, hard_stop=False)
```
- `_deferred_insert_msg = None` in `main_window.__init__` (neben `_qso_pending_insert`).
- `_on_cancel` (HALT) nullt jetzt ZUSÄTZLICH `_deferred_insert_msg` (Race-Schutz).
- `QTimer` zu `from PySide6.QtCore import ...` ergänzt.

## Verifiziert
- Neue Tests `test_p167_insert_defer.py` (4): defert statt synchron, no-op ohne
  Pending, HALT verwirft deferten Einschub, Executor konsumiert msg (kein
  Doppel). 4 P158-Tests auf Defer-Verhalten angepasst (T16/T17/T19/T26).
- Volle Suite **2290 passed** (vorher 2286, +4).
- Reine GUI-Ablauf-Steuerung, **kein TX-Pfad-Eingriff, kein Hardware, ANT1/ANT2
  unberührt.**

## Bitte prüfen
1. Ist der Reentrancy-Bug damit sicher behoben (Einschub läuft erst nachdem
   `_resume_cq_if_needed` den State auf IDLE gesetzt hat → start_qso → TX_CALL
   bleibt)?
2. `QTimer.singleShot(0, ...)` im GUI-Thread: bound method auf MainWindow-Instanz
   — Lifetime ok (MainWindow lebt App-weit)? Kein dangling callback?
3. HALT-Race vollständig geschlossen (`_on_cancel` nullt `_deferred_insert_msg`)?
4. Übersehene Pfade, die `_p158_maybe_start_inserted_call` synchron erwarten?

**PUSH FREIGEBEN** oder **NICHT**?
