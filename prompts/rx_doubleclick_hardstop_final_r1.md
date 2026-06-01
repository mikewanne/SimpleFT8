FINAL-REVIEW (R1) — P166 RX-Listen-Doppelklick = harter Auto-Hunt-Stop ist
fertig codiert, alle Tests grün (2255 passed, 0 Regression). Prüfe den
angehängten finalen Code kritisch auf Bugs/Edge-Cases/Regressionen, bevor lokal
committet wird. KISS-Hobby-Tool, EIN Operator.

================================================================================
WAS UMGESETZT WURDE
================================================================================
Ziel: Doppelklick in der RX-Liste = bewusste Übernahme → Auto-Hunt KOMPLETT
stoppen (wie HALT), CQ/QSO abbrechen, sofort die Station rufen. Der P164-Klick
im QSO-FENSTER bleibt unverändert sanft (pausieren + Auto-Resume).

1. `ui/mw_qso.py:_on_station_clicked(self, msg, hard_stop=True)` — neuer
   Parameter. Stop-Block GANZ OBEN (vor allen Vorab-Returns):
   ```python
   if hard_stop:
       if self._auto_hunt.active:
           self._auto_hunt.stop_auto_hunt("manual_halt")
       self._qso_pending_insert = None
       self._p158_insertable.clear()
   ```
   Der alte Pausieren-Aufruf weiter unten ist jetzt `if not hard_stop and
   self._auto_hunt.active: self._auto_hunt.on_manual_qso_start()`.
2. `ui/mw_cycle.py:_on_hunt_insert_clicked` IDLE-Sofort-Ruf →
   `_on_station_clicked(msg, hard_stop=False)` (P164 QSO-Fenster bleibt sanft).
3. `ui/mw_qso.py:_p158_maybe_start_inserted_call` Einschub →
   `_on_station_clicked(msg, hard_stop=False)`.
4. RX-Panel-Signal (main_window) + TX-Buffer-Resume nutzen Default → hard_stop=
   True (harter Stop).

================================================================================
ENTSCHEIDUNGEN GEGEN DEINE R1-VORRUNDE (bitte gegenprüfen)
================================================================================
A) Deine R1 (🟠 F2) empfahl ein explizites `qso_sm.cancel()` vor `start_qso()`.
   VERWORFEN nach Code-Verifikation: `core/qso_state.py:start_qso` (Z.297-330)
   bricht ein laufendes QSO BEREITS sauber ab — `if self.state != IDLE:` setzt
   `_pending_reply/_pending_hunt_reply/_pending_rr73 = None` + `_set_state(IDLE)`
   (dokumentiert P1.14 KP1), dann frisches QSOData (timeout_cycles=0). Ein
   zusätzliches cancel() wäre redundant. Ist diese Begründung korrekt, oder
   übersehe ich einen State (Timer/Encoder-Auftrag), den start_qso NICHT räumt,
   cancel() aber schon?
B) Deine R1 (🟡 F3+F4) empfahl separate stop_auto_hunt-Aufrufe im TX-Pfad UND
   in den Vorab-Return-Pfaden. Stattdessen: EIN Stop-Block GANZ OBEN deckt alle
   Pfade ab (TX-Buffer, SWR, Slot-Lock, Einmessen, Normal) — DRY, KISS. Ist das
   äquivalent/besser, oder gibt es einen Pfad der den Block-oben umgeht?

================================================================================
PRÜF-FRAGEN
================================================================================
Q1. Korrektheit Stop-Block: greift er in ALLEN hard_stop-Pfaden genau einmal?
    Doppel-Stop beim TX-Buffer-Resume (Stop oben + erneut beim gepufferten
    `_on_station_clicked(buffered)`) — durch stop_auto_hunt-Idempotenz harmlos?
Q2. P164-Regression: bleibt der QSO-Fenster-Klick (beide Pfade — IDLE-Sofort +
    Einschub-nach-QSO) wirklich sanft (Auto-Resume)? Wird `_qso_pending_insert`
    im sanften Pfad NICHT fälschlich genullt?
Q3. `_p158_insertable.clear()` im hard_stop-Block: korrekt dass ein RX-Klick
    alle vorgemerkten QSO-Fenster-Einschübe verwirft? (Operator übernimmt
    bewusst → alte Vormerkungen sind obsolet.)
Q4. Reihenfolge: Stop-Block VOR SWR/TX/Slot-Lock-Checks. Kann der frühe
    stop_auto_hunt (+ auto_hunt_stopped-Signal → UI) ein Problem machen wenn
    danach doch nicht gerufen wird (SWR-Sperre)? Inkonsistenter UI-State?
Q5. on_manual_qso_end (QSO-Ende-Handler, global) nach hartem Stop: harmlos
    (active=False → kein Resume)? Re-Resume-Gefahr?
Q6. Hardware: TX-/Antennen-Pfad (ANT1) unberührt — bestätige.

FORMAT: (1) Verdikt (PUSH FREIGEBEN / BLOCKER), (2) A/B + Q1-Q6 knapp mit
Datei:Zeile, (3) Severity-Tabelle 🔴/🟠/🟡/⚪ falls Findings.

Angehängt: ui/mw_qso.py (final). Referenz core/qso_state.py:start_qso (Z.297):
bricht laufendes QSO via Pending-Reset + _set_state(IDLE) ab (P1.14 KP1).
