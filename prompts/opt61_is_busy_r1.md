# OPT-61 Review-Anfrage (R1) — KISS: `QSOStateMachine.is_busy`-Property

## Kontext
SimpleFT8, autonome **Optimierungs-Kampagne**. Regel: NUR Optimierung,
**keine Verhaltensänderung**, KISS/Lesbarkeit. Pro Punkt voller Workflow.
Hardware-Regel ANT1=TX ist hier **nicht** berührt (reine State-Lese-Logik).

## Befund (von mir gegen den echten Code verifiziert)
Das Audit behauptete „11× kopiertes `(IDLE,TIMEOUT,CQ_CALLING,CQ_WAIT)`-Tupel".
**Falsch** — beim Live-grep zeigt sich: es gibt **genau 7** Vorkommen dieses
EXAKTEN 4-State-Sets. Die übrigen CQ_WAIT-Treffer sind semantisch ANDERE Mengen
und werden NICHT angefasst:
- `(IDLE, CQ_WAIT)` — 2-Set (start_cq-Guard, OMNI/Auto-Hunt-Start-Guard)
- `(IDLE, CQ_WAIT, CQ_CALLING)` — 3-Set (RX-Verarbeitung, quick73-Filter)
- `(IDLE, CQ_CALLING, CQ_WAIT, TIMEOUT, WAIT_73, TX_73_COURTESY)` — 6-Set (3-Min-Timeout)
- `(CQ_CALLING, CQ_WAIT)` — 2-Set (stop_cq)

## Enum (core/qso_state.py)
```
IDLE, CQ_CALLING, CQ_WAIT,
TX_CALL, WAIT_REPORT, TX_REPORT, WAIT_RR73, TX_RR73, WAIT_73, TX_73_COURTESY,
LOGGING (legacy/ungenutzt), TIMEOUT
```
→ `not in (IDLE, TIMEOUT, CQ_CALLING, CQ_WAIT)` == State ∈ {TX_CALL, WAIT_REPORT,
TX_REPORT, WAIT_RR73, TX_RR73, WAIT_73, TX_73_COURTESY, LOGGING} == „QSO-Austausch
mit einer Gegenstation läuft gerade".

## Geplante Änderung (V3-Kandidat)
Neue Property in `QSOStateMachine` (core/qso_state.py):
```python
@property
def is_busy(self) -> bool:
    """True wenn eine QSO-Austausch-Sequenz mit einer Gegenstation laeuft.

    „Nicht busy" = IDLE / TIMEOUT / CQ_CALLING / CQ_WAIT — in diesen
    Zustaenden laeuft kein QSO, das vor Bandwechsel / Frequenzsprung /
    Stop geschuetzt werden muesste.
    """
    return self.state not in (
        QSOState.IDLE, QSOState.TIMEOUT,
        QSOState.CQ_CALLING, QSOState.CQ_WAIT,
    )
```

Dann die 7 Call-Sites ersetzen (alle in UI-Mixins, KEINE in core):
1. main_window.py:1157  `_qso_active_for_msg_defer` → `return self.qso_sm.is_busy`
2. main_window.py:1463  `_in_qso = self.qso_sm.is_busy`
3. main_window.py:1615  `if state in (CQ_CALLING,CQ_WAIT,IDLE,TIMEOUT):` → `if not self.qso_sm.is_busy:`
4. mw_cycle.py:229      `qso_busy = self.qso_sm.is_busy`
5. mw_cycle.py:673      `_in_qso = self.qso_sm.is_busy`
6. mw_qso.py:223        `elif self.qso_sm.is_busy:`
7. mw_qso.py:370        `if self.qso_sm.is_busy:`

Die ANDEREN Sets (2/3/6-State oben) bleiben unverändert.

## Meine offenen Fragen an dich (kritisch prüfen)
1. **Verhaltensneutralität**: Ist jede der 7 Ersetzungen exakt äquivalent?
   Insbesondere die `in`-Form (Punkt 3) → `not is_busy` — Reihenfolge im Tupel
   egal, Set identisch? Übersehe ich einen Fall wo `state` ein anderes Set meint?
2. **Naming**: `is_busy` vs `is_in_qso`/`is_qso_active`? „busy" könnte bei
   CQ_CALLING (sendet ja CQ) missverständlich wirken. Was ist am klarsten —
   ohne Overengineering?
3. **Inline-Tupel in der Property vs Modul-`frozenset`-Konstante**? KISS sagt
   inline (4 Elemente, 1 Stelle). Stimmst du zu, oder ist eine benannte
   Konstante hier sinnvoller?
4. **`_qso_active_for_msg_defer`** wird zum dünnen Wrapper (`return is_busy`).
   Behalten (sprechender Name, Scope-Disziplin) oder ist das tote Indirektion?
5. **Thread-Safety**: Die Property liest nur `self.state` (genau wie die
   Call-Sites vorher). Kein neuer Lock nötig — korrekt?
6. Irgendein Risiko, das ich übersehe? Sonst: GO/NO-GO.

Bitte knapp und konkret. Code ist Referenz, nicht Annahmen.
