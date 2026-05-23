# Final-R1 — DeepSeek-Review der committeten Re-Mess-Countdown-Aenderungen

## Kontext

V1→V2→R1→V3→C1-C3-Workflow fuer den Re-Mess-Countdown-Anzeige-Bug
abgeschlossen. Du bekommst die finalen Dateien.

**Ziel:** Das `dx_info`-Label „noch X Stunden bis Re-Mess" soll sich
pro Slot aktualisieren (vorher nur aktions-getriggert → stale).

**R1-Verdict (vor Code):** „1-Zeilen-Fix im Cycle-Hook ist der sauberste
Weg, keine Einwaende."

## Was committet wurde (C1-C3)

**C1** (`1e95a5d`) — `ui/mw_cycle.py:_on_cycle_finished`:
Nach `self.qso_sm.on_decoder_finished()` ergaenzt:
```python
# P83 (2026-05-23): Re-Mess-Countdown-Anzeige pro Slot refreshen,
# damit "noch X Stunden bis Re-Mess" lebendig tickt — bisher nur
# aktions-getriggert. `_update_gain_status_display` ist
# leichtgewichtig (Format-String + setText, kein I/O).
self._update_gain_status_display()
```
+ neuer Test `tests/test_remess_countdown_refresh.py` (3 Tests):
- `rx_active=True` → `_update_gain_status_display` wird aufgerufen.
- `rx_active=False` → Guard greift, kein Refresh + kein
  `qso_sm.on_decoder_finished`.
- Call-Order: `on_decoder_finished` VOR `_update_gain_status_display`.

**C2** (`6b20613`) — `TODO.md`: Eintrag „Re-Mess-Countdown-Anzeige
haengt" auf ERLEDIGT umgestellt mit HISTORY-Pointer.

**C3** (`7ed1160`) — Doku: APP_VERSION 0.97.92→0.97.93,
CLAUDE.md/HISTORY.md/HANDOFF.md.

**Tests:** 1741 → 1744 gruen (+3 neue).

## Was ich von dir will

Sanity-Check ob die committete Umsetzung sauber ist:

1. **Position des neuen Aufrufs** in `_on_cycle_finished` korrekt?
   Direkt nach `qso_sm.on_decoder_finished()` am Methoden-Ende —
   Reihenfolge OK?
2. **Tests** vollstaendig? Decken sie was sie sollen? Insbesondere
   der Call-Order-Test mit `side_effect`?
3. **Wasserdichte:** Gibt es einen subtilen Pfad, der jetzt unerwartet
   bricht oder ungewollte Konsequenzen hat (z.B. Aufruf auf
   `_update_gain_status_display` ohne `_rx_mode` gesetzt, Race mit
   Action-Triggern, Performance bei FT2 3.8s-Slots)?
4. **Kommentar** klar + nicht verwirrend?
5. **Sonstige Risiken** uebersehen?

Antworte auf Deutsch, knapp, konkret, mit Datei:Zeile. Sei kritisch —
es soll wirklich sauber sein.
