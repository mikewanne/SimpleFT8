# R1-Review: P162 — QSO-Abschluss-Vorfahrtsregel (ersetzt 6 verstreute Pfade)

Du bist Senior-Python/PySide6-Reviewer für SimpleFT8 (FT8-Hobby-Funker-Tool,
KISS, kein Contest-Tool). Es geht um das Herzstück: die QSO-State-Machine in
`core/qso_state.py`. Prüfe meinen Plan KRITISCH auf Bugs, Race-Conditions,
Edge-Cases, Overengineering. Antworte mit nummerierten Findings (🔴 Blocker /
🟠 sollte / 🟡 nice). Am Ende: GO oder NO-GO + Empfehlung welche Variante.

## Mike-Field-Bug (Anlass)

Auto-Hunt rief EG5SUN (sehr schwache Station, wir geben −25 dB). EG5SUN schickte
SOFORT `R-12` (= R-Report = Bestätigung + Rapport), BEVOR der normale Report-
Austausch durch war ("voraus"-Timing — sie hatte uns schon vorher gehört). Log:
```
Rufe EG5SUN...
10:56:30 ← Empf. DA1MHH EG5SUN R-12   (R-Report, sie bestätigt)
10:56:45 → Gesendet EG5SUN DA1MHH -25  (FALSCH: wir wiederholen unseren Report)
10:57:00 ← Empf. DA1MHH EG5SUN R-12
10:57:15 → Gesendet EG5SUN DA1MHH -25
... 5× ... ✗ EG5SUN Timeout (QSO verloren)
```
Vergleich RC1C (Gleichtakt, lief sauber): wir senden Report → sie R-08 → wir
RR73 → sie 73 → ✓. Bei RC1C waren wir im richtigen State (WAIT_RR73), bei
EG5SUN kam ihr R-Report während wir noch in WAIT_REPORT/TX_CALL waren und es
rutschte durch.

## Mike-Diagnose (wörtlich, sehr treffend)
„Es ist KEIN Timing-Problem — wir decodieren das R-12 sauber und zeigen es an,
reagieren nur falsch. Statt zig Zustände abzufragen reicht EINE Regel: kommt vom
QSO-Partner eine Empfangs-Zeile an mich mit einem Rapport (Zahl MIT Vorzeichen
+ oder − davor — sauberer Diskriminator gegen Grid wie JN65, das nie ein
Vorzeichen hat), dann haben wir alle QSO-Daten → mit R: sofort 73; ohne R:
genau 1× eigenen R-Report nachlegen, dann 73."

## Ist-Zustand: die 6 verstreuten Abschluss-Pfade (core/qso_state.py)

Aktuelle Behandlung von empfangenem Report/R-Report ist über 6 Stellen verteilt:
1. `WAIT_REPORT` + R-Report → RR73 (Z.629, in `on_message_received`)
2. `TX_CALL`-pending (R-Report kam während WIR senden) → RR73 (Z.500, in `on_message_sent`)
3. `TX_REPORT`-pending (R-Report während WIR senden) → RR73 (Z.652)
4. `WAIT_RR73` + R-Report → advance/RR73, mit Cap MAX_RR73_RETRIES=5 (Z.677)
5. `WAIT_RR73` + Report-ohne-R → Wiederholung, Cap (Z.708)
6. `WAIT_73` + R-Report → Höflichkeits-RR73, Cap wait_73_retries<2 (Z.786)

PLUS der Bug-Verursacher: `on_decoder_finished` (Z.413-427) triggert am Slot-
ENDE einen WAIT_REPORT-Retry (`calls_made++`, sendet `their my our_snr`) wenn
`timeout_cycles==1`. Genau das lief bei EG5SUN statt der R-Report-Behandlung.

## Relevante Strukturen (verifiziert)

`FT8Message` (`core/message.py`, @dataclass, field1/field2/field3):
- `caller` = field2 (Property), `target` = field1 (leer bei CQ)
- `is_report` = field3 ist Zahl −50..50 (mit optionalem R-Prefix) → das ist
  Mikes "Vorzeichen-Rapport". `is_r_report` = startswith("R") AND is_report.
- `is_grid` = 4 Zeichen Buchstabe/Buchstabe/Ziffer/Ziffer (JN65) — KEIN is_report.
- `is_rr73` (RR73/RRR), `is_73` (73) — separate Properties, KEINE Zahl.

`QSOData`: their_call, their_grid, their_snr, our_snr, my_call, calls_made,
timeout_cycles, max_timeout=12, max_calls=5, rr73_retries, wait_73_retries,
courtesy_73_sent, cq_mode.

`QSOState`: IDLE, CQ_CALLING, CQ_WAIT, TX_CALL, WAIT_REPORT, TX_REPORT,
WAIT_RR73, TX_RR73, WAIT_73, TX_73_COURTESY, TIMEOUT.

`on_message_received(msg)` Ablauf (Z.549+): RX-Log → CQ-Anrufer-Warteliste →
"jemand ruft uns" (IDLE/CQ) → Guard `if msg.target != my_call: return` (Z.599)
→ Guard `if state not in (IDLE/CQ...): if msg.caller != qso.their_call: return`
(Z.603-605) → DANN die State-Blöcke (WAIT_REPORT Z.607, TX_REPORT Z.647,
WAIT_RR73 Z.662, WAIT_73 Z.751).

Sende-Mechanik: TX-States (TX_CALL/TX_REPORT/TX_RR73/TX_73_COURTESY) = WIR senden
gerade (Halbduplex). Während wir senden, dürfen wir NICHT sofort umschalten —
eingehende Nachrichten werden als `_pending_*` gemerkt und in `on_message_sent`
(am TX-Ende) ausgewertet. WAIT-States = wir warten, können im nächsten Slot
direkt senden.

## Mein Plan (V1)

**Neue zentrale Vorfahrtsregel** `_p162_try_finish_on_report(msg) -> bool`,
aufgerufen GANZ VORNE in `on_message_received` — direkt NACH den beiden Guards
(Z.599 "an uns" + Z.603-605 "Absender=Gegenstation"), VOR allen State-Blöcken.

```python
# QSO-Abschluss-States in denen wir auf/nach Report-Austausch sind:
_P162_FINISH_STATES = {WAIT_REPORT, WAIT_RR73}   # WAIT-States: direkt senden
# TX-States werden NICHT hier behandelt — deren pending-Mechanik bleibt (s.u.)

def _p162_try_finish_on_report(self, msg) -> bool:
    if self.state not in _P162_FINISH_STATES:
        return False
    if not msg.is_report:           # Mikes Diskriminator: Zahl MIT Vorzeichen
        return False                # Grid/RR73/73 → alte Pfade
    # caller==their_call schon durch Z.603-605 garantiert
    self.qso.their_snr = msg.grid_or_report
    if msg.is_r_report:
        # mit R = Partner hat uns bestätigt → sofort RR73, QSO zu
        tx = f"{self.qso.their_call} {self.my_call} RR73"
        self._set_state(TX_RR73)
        self.send_message.emit(tx)
        return True
    # ohne R: genau 1× unseren R-Report nachlegen, dann 73
    if not self.qso.p162_relayed:           # neues Flag, default False
        self.qso.p162_relayed = True
        rpt = self.qso.our_snr or f"R{self._last_snr:+03d}"
        tx = f"{self.qso.their_call} {self.my_call} {rpt}"
        self._set_state(TX_REPORT)
        self.send_message.emit(tx)
    else:
        tx = f"{self.qso.their_call} {self.my_call} RR73"
        self._set_state(TX_RR73)
        self.send_message.emit(tx)
    return True
```
In `on_message_received` nach Z.605:
```python
if self._p162_try_finish_on_report(msg):
    return
```
Alte 6 Pfade bleiben AKTIV als Fallback (Mike-Spec: Probebetrieb, kein Risiko
für die 95%-Fälle). Neue Regel sitzt davor und fängt den Abschluss zuerst.

## Gezielte Fragen

F1: **Greift die Regel den EG5SUN-Bug?** EG5SUN: State=WAIT_REPORT, msg=R-12
(is_r_report). Regel → TX_RR73, sendet RR73. Korrekt? Oder war der State zum
fraglichen Zeitpunkt TX_CALL (wir sendeten noch)? Falls TX_CALL: meine Regel
greift NICHT (nicht in _P162_FINISH_STATES) → der bestehende TX_CALL-pending-
Pfad (Z.500) müsste greifen. Hat der versagt? Brauche ich TX_CALL/TX_REPORT
AUCH in der Regel (mit pending-Mechanik), um den Bug sicher zu fangen?

F2: **on_decoder_finished-Race.** Der WAIT_REPORT-Retry (Z.413) läuft am Slot-
ENDE. Läuft `on_message_received` (und damit meine Regel) GARANTIERT vor
`on_decoder_finished` im selben Slot? Wenn nein, feuert der Retry (`-25`) BEVOR
meine Regel das R-12 sieht → Bug bleibt. Wie absichern? (Ich kläre die genaue
Reihenfolge gerade separat im Code — sag was DU aus dem Beschriebenen ableitest.)

F3: **WAIT_RR73-Doppelung.** In WAIT_RR73 behandelt schon Pfad 4/5 R-Report und
Report-ohne-R (mit Cap). Meine Regel greift dort jetzt ZUERST (gleicher State).
Kollision? Sollte ich WAIT_RR73 aus _P162_FINISH_STATES rausnehmen (nur
WAIT_REPORT neu, WAIT_RR73 bei den bewährten Pfaden lassen)? Oder ist die neue
Regel in WAIT_RR73 sauberer?

F4: **„ohne R → 1× nachlegen" Semantik.** Ist `p162_relayed`-Flag (1× R-Report
nachlegen, dann 73) protokoll-korrekt? Oder sollte „ohne R" gar nicht über diese
Regel laufen (weil der normale Erst-Report-Austausch ja genau das ist) und die
Regel NUR bei is_r_report greifen (= reiner EG5SUN-Fix, minimal-invasiv)?

F5: **Counter/Cap.** Die alten Pfade cappen gegen rr73_retries/MAX=5 +
3-Min-Gesamttimeout. Meine Regel hat keinen eigenen Cap (außer p162_relayed für
den ohne-R-Fall). Kann das endlos werden? (Der 3-Min-`on_cycle_end`-Timeout
Z.354 fängt eh alles ab — reicht das als Backstop?)

F6: **their_snr-Überschreiben.** Ich setze `qso.their_snr = msg.grid_or_report`
immer. Bei R-12 ist grid_or_report="R-12" (mit R-Prefix) — soll das R im
gespeicherten SNR bleiben oder gestrippt werden (fürs ADIF-Log)? Wie machen es
die alten Pfade?

F7: **Variante-Empfehlung.** Drei Varianten:
(a) Minimal: Regel NUR is_r_report, NUR WAIT_REPORT (reiner EG5SUN-Fix).
(b) Mein Plan: is_r_report + ohne-R-1×-nachlegen, WAIT_REPORT+WAIT_RR73.
(c) Maximal: zusätzlich TX_CALL/TX_REPORT mit pending → ersetzt wirklich alle 6.
Welche ist KISS-korrekt für ein Hobby-Tool und fängt den Bug sicher? Mike will
langfristig die 6 Pfade loswerden, aber erstmal sicher + Probebetrieb.

Sei knapp. Code ist Referenz, keine Spekulation. Wo du die Reihenfolge
on_message_received vs on_decoder_finished nicht aus dem Text ableiten kannst,
sag es explizit statt zu raten.
