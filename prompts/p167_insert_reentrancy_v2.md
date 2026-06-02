# Bug-Diagnose-Review: Eingeschobenes QSO (P164) hängt nach 1 Anruf

Hobby-FT8-Tool (PySide6, EIN GUI-Thread, Signale Qt.DirectConnection = synchron).
KISS. Antworte kritisch + knapp, Findings 🔴/🟠/🟡. Bestätige oder widerlege
meine Root-Cause, empfiehl die beste Fix-Variante.

## Symptom (Mike-Field, Log verifiziert)
Auto-Hunt jagte 9A60CBM. Fremde Station IN3BFW rief Mike dazwischen an
(„DA1MHH IN3BFW R-09"). Mike klickte IN3BFW im QSO-Fenster → P164-Einschub
(„vorgemerkt — wird nach diesem QSO gerufen", Merker `_qso_pending_insert`).
9A60CBM lief in TIMEOUT (5/5). Dann wurde IN3BFW **genau EINMAL** gerufen und
das Programm blieb stehen: kein Retry, Auto-Hunt nahm NICHT wieder auf. Erst
manueller Auto-Hunt-Neustart (~4 Min später) brachte es zurück.

## Log (entscheidend)
```
[06:40:12] [TIMEOUT] Max Versuche (5) erreicht
[06:40:12] [STATE] WAIT_REPORT → TIMEOUT
[Auto-Hunt] Timeout 9A60CBM — 5 Min Cooldown
[Auto-Hunt] Manuelles QSO beendet — Auto-Hunt wird fortgesetzt
[Auto-Hunt] Manueller QSO-Start — Auto-Hunt pausiert
[QSO] Abbruch 9A60CBM → starte neu mit IN3BFW
[06:40:12] [STATE] TIMEOUT → IDLE              # start_qso-Reset
[06:40:12] [START] Hunt: IN3BFW auf 43Hz, max 5 Versuche
[06:40:12] [TX]    Sende: 'IN3BFW DA1MHH -18'
[06:40:12] [STATE] IDLE → TX_CALL              # start_qso Ende
[TX] → 'IN3BFW DA1MHH -18'                      # send_message-Handler (TX-Trigger)
[06:40:12] [STATE] TX_CALL → IDLE              # <<< HIER fällt es zurück!
[TX] 06:40:13 ... sendet einmal ...
# danach: State IDLE, QSO=IN3BFW, aber nie wieder TX. Auto-Hunt pausiert (bleibt).
```
Normaler Auto-Hunt-Start (ohne Einschub) bleibt korrekt in TX_CALL.

## Root-Cause (meine Analyse, bitte prüfen)
`core/qso_state.py:on_decoder_finished` Timeout-Zweig:
```python
self._set_state(QSOState.TIMEOUT)        # Z.424
self.qso_timeout.emit(call)              # Z.425  SYNCHRON (DirectConnection)
self._resume_cq_if_needed()              # Z.426  läuft NACH dem emit
return
```
- Z.425 `qso_timeout.emit` ruft synchron `mw_qso._on_qso_timeout` →
  `_p158_maybe_start_inserted_call()` → `_on_station_clicked(IN3BFW,
  hard_stop=False)` → `start_qso(IN3BFW)` → State = **TX_CALL**, erster Anruf
  emittiert.
- Zurück in Z.426: `_resume_cq_if_needed()`. Kein CQ aktiv (`cq_mode`/`_was_cq`
  False im Auto-Hunt) → else-Zweig:
  ```python
  else:
      self._set_state(QSOState.IDLE)     # Z.474  <<< überschreibt frischen TX_CALL!
  ```
→ State zurück auf IDLE. QSO=IN3BFW existiert, aber State IDLE → kein Retry/
  WAIT_REPORT. Und weil nie ein sauberes QSO-Ende kam, blieb `_manual_override`
  (Auto-Hunt pausiert) → Auto-Hunt-Stillstand.

**Erfolgs-Pfad identisch:** `on_message_sent` TX_73_COURTESY (Z.543-545):
`qso_confirmed.emit` (→ Einschub → TX_CALL) gefolgt von `_resume_cq_if_needed()`
(→ IDLE). Also derselbe Reentrancy-Bug auch wenn der Einschub nach ERFOLG (statt
Timeout) startet.

Kern: Der P164-Einschub startet **synchron mitten im qso_state-Abschluss-
Handler** ein neues QSO; der Handler überschreibt danach den frischen TX_CALL
mit IDLE.

## Fix-Optionen
**Option A (mein Favorit) — Einschub deferren:** In
`_p158_maybe_start_inserted_call` den Klick im nächsten Event-Tick starten:
```python
msg = self._qso_pending_insert
if msg is None: return
self._qso_pending_insert = None
self._p158_insertable.clear()
QTimer.singleShot(0, lambda: self._on_station_clicked(msg, hard_stop=False))
```
→ `_resume_cq_if_needed` läuft zuerst (State sauber IDLE), DANN der Einschub
(TX_CALL bleibt). Behebt Timeout- UND Erfolgs-Pfad an EINER Stelle, ohne die
fragile qso_state-Reihenfolge anzufassen.

**Option B — Guard in `_resume_cq_if_needed`:** else-Zweig nur IDLE setzen wenn
State noch im Abschluss-State (TIMEOUT/TX_RR73/TX_73_COURTESY/WAIT_73), NICHT
wenn inzwischen TX_CALL (Einschub) gesetzt wurde. Gezielter in qso_state, aber
fragil (welche States genau?).

**Option C — Reihenfolge:** `_resume_cq_if_needed()` VOR `qso_timeout.emit`.
Riskant (ändert CQ-Resume-Semantik global, viele Aufrufer).

## Fragen
1. Ist meine Root-Cause korrekt (Reentrancy: Einschub setzt TX_CALL, danach
   `_resume_cq_if_needed` → IDLE)?
2. Welche Option ist am robustesten + KISS? Edge-Cases bei Option A
   (QTimer.singleShot(0): Auto-Hunt select_next läuft im Slot-Takt, nicht im
   Event-Tick → Einschub kommt zuerst; HALT im Mini-Fenster verwirft Merker
   nicht mehr, aber msg ist in Closure — vernachlässigbar?)?
3. Übersehe ich, dass der Einschub auch `on_manual_qso_start` (Auto-Hunt-Pause)
   ruft — bleibt der Auto-Hunt-Resume nach dem (jetzt korrekt laufenden)
   Einschub-QSO erhalten?
