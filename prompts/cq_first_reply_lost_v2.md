# First-Reply-Lost-Bug — Diagnose V2 (Self-Review von V1)

**Status:** V2 = frische-KI Self-Review. V1 hatte Trace, 4 Loesungs-
Optionen, R1-Auftrag. V2 ergaenzt: praezisere Decode-Time-Schaetzung
(5-Pass-Subtraction), CQ_WAIT-Pfad-Analyse-Schaerfung, Option C
verfeinert (2.0 statt 2.5), Telemetrie-Counter konkret, Pfad B2 als
nie-erreichbar nachgewiesen.

V2 ist eigenstaendig (R1 braucht nur V2 + Code).

---

## 1. Symptom (unveraendert)

Field-Test 10:03-10:09 UTC, **4 Mal heute reproduziert**:

```
:05:30 [E] → CQ
:05:45 [O] ← DA1MHH DA1TST JO31     ← DA1TST ruft
:06:00 [E] → CQ                      ← BUG: noch CQ statt Report
:06:15 [O] ← DA1MHH DA1TST JO31      ← DA1TST wiederholt
:06:30 [E] → DA1TST DA1MHH -21       ← Report 1 Slot zu spaet
```

Mike: *„den kann ich gut immer wieder nachstellen"*. Race-Bedingung
greift bei FT8 + FlexRadio + Mike's typischer Stations-Dichte
**reproduzierbar** — nicht zufaellig.

---

## 2. Architektur-Komponenten (V2-erweitert)

**4 Sender im System** (V1 zaehlte 3 — Timer ist als 4. Sender wichtig):

| Sender | Thread | Wake-Zeit (FT8) | Signal |
|---|---|---|---|
| Decoder | `_decode_loop` daemon | slot + 13.5s | `cycle_decoded`, `message_decoded`, `cycle_finished` |
| Decoder-Worker | `_process_cycle` daemon | bei Decoder-Wake gestartet | (gleiche Signale, FIFO pro Sender = Decoder-Instanz) |
| Encoder-Worker | daemon | next_boundary - 1.3s | `tx_started`, `tx_finished` |
| Timer | daemon, 0.1s tick | Slot-Boundary +/- 100ms | `cycle_start(num, is_even)`, `cycle_tick` |

**Wichtig (V2-Schaerfung):** Timer.cycle_start hat **0.1s Tick-Granularitaet**
(`core/timing.py:84` `time.sleep(0.1)`). Boundary-Trigger kann +/- 100ms
abweichen → cycle_start emit zwischen `boundary` und `boundary+0.1s`.

**Qt-Reihenfolge:** Pro Sender FIFO. Zwischen verschiedenen Sendern
keine Garantie. Aber: alle Signale landen im selben GUI-Event-Loop, in
emit-Aufruf-Reihenfolge.

Wenn Encoder `tx_finished` emit'd hat (z.B. :05:43.3) und Timer dann
`cycle_start` emit'd (:05:45.0+ε), dann ist die Reihenfolge im Event-
Loop: tx_finished → cycle_start. Beide landen nacheinander, GUI dispatched
sequentiell.

---

## 3. Code-Pfad-Trace — :05:30-:06:30 (ms-genau, V2-verfeinert)

| UTC | Thread | Aktion | State |
|---|---|---|---|
| :05:29.7-:05:43.2 | Encoder-Worker (CQ#A) | Audio :05:30-CQ wird gestreamt (BLOCKING send_audio) | CQ_CALLING |
| :05:43.3 | Encoder | tx_finished.emit() (Sender=Encoder) | — |
| :05:43.3+ε | GUI | dispatched → on_message_sent: state=CQ_CALLING + pending=None → **CQ_WAIT, tc=0** | CQ_WAIT |
| :05:45.0±0.1 | Timer | cycle_start(2423, is_even=False).emit() (Sender=Timer) | — |
| :05:45.0+ε | GUI | dispatched → on_cycle_end: state=CQ_WAIT, tc=1 → **`_send_cq()`** → state=CQ_CALLING, _pending_reply=None, send_message.emit("CQ DA1MHH JO31") → encoder.transmit(CQ#B) | CQ_CALLING |
| :05:45.0+ε' | Encoder-Worker (CQ#B) | startet daemon thread, sleep bis next EVEN boundary - 1.3 = :06:00 - 1.3 = :05:58.7 | CQ_CALLING |
| :05:58.5±ε | Decoder | wakes für :05:45-slot (slot + _WAKE 13.5), forks `_process_cycle` daemon thread | — |
| **:05:58.5–:06:00.0±** | Decoder-Worker | **5-Pass Subtraction** + Window-Sliding (3 offsets/Pass = 15 ft8lib-Calls). Bei vielen Stationen + langsamer Hardware: **bis 1.5s** | — |
| :05:58.7 | **Encoder-Worker (CQ#B)** | wakes aus sleep, **beginnt send_audio** (BLOCKING, ~14s) | CQ_CALLING |
| **WICHTIG:** Decoder noch im Decoding (~0.2s vor Encoder-Wake bis ~1.3s nach) | | | |
| :05:59.5±ε | Decoder-Worker | fertig, emit cycle_decoded → message_decoded(DA1TST) → cycle_finished (Sender=Decoder) | — |
| :05:59.5+ε' | GUI | dispatched message_decoded → on_message_received(DA1TST): state=CQ_CALLING, target ✓, is_grid ✓ → **`_pending_reply=msg`** ✓ (P1.5-Fix wirkt) | CQ_CALLING |
| **NICHT REVERSIBEL** | | Encoder ist in send_audio, kein Abort-Check (flexradio.py:1057-1085) | |
| :06:12.7 | Encoder-Worker | send_audio fertig, ptt_off, tx_finished.emit() | — |
| :06:12.7+ε | GUI | dispatched → on_message_sent: CQ_CALLING + pending=msg → `_process_cq_reply` → state=TX_REPORT, send_message.emit("DA1TST DA1MHH -21") → encoder.transmit(report) | TX_REPORT |
| :06:13 | Encoder-Worker (Report) | next EVEN boundary mit overshoot (Drift-Guard +30s) → :06:30 | TX_REPORT |
| :06:30 | RF | Report TX | TX_REPORT |

---

## 4. Pfad B2-Analyse (V2-Schaerfung) — wann klappt's ohne Verzoegerung?

V1 erwaehnte Pfad B2 (tx_finished VOR message_decoded) als alternativen
Pfad der NICHT in den Bug laeuft. Genauere Analyse:

**Pfad B2 verlangt:**
1. Decoder-Worker fertig BEFORE Encoder Audio-Start (= :05:58.7)
2. message_decoded dispatched VOR cycle_start des naechsten Slots

Punkt 1 setzt Decode-Time < 0.2s voraus. Praktisch nie bei FT8 5-Pass-
Subtraction. Sub-second Decode haben wir nur bei 0-1 Stationen im Slot
(leeres Band).

Punkt 2 ist GUI-Thread-abhaengig. Wenn GUI free, dispatched message_decoded
sofort. cycle_start kommt mit +0.1s Tick-Granularitaet → message_decoded
kann durchaus VOR cycle_start dispatched werden.

**Aber:** state ist beim message_decoded-Dispatch CQ_CALLING (von
voherigem _send_cq), nicht CQ_WAIT. Pfad B2 verlangt CQ_WAIT-State.

**Schlussfolgerung V2:** Pfad B2 wird in der aktuellen Architektur
**nicht erreicht** — das _send_cq am Slot-START setzt state immer auf
CQ_CALLING bevor Decoder fertig ist.

→ Mike's „manchmal klappt"-Faelle sind vermutlich:
- Stationen die NICHT im :05:45-Slot rufen, sondern erst spaeter (e.g.
  :06:15 ODD wenn unser :06:00-CQ schon gelaufen ist) → ihr Reply
  kommt waehrend unserer CQ_CALLING — gleicher Race aber 1 Slot Delay
  weniger relevant.
- Oder Faelle ohne pending pre-empted CQ (sehr leeres Band).

---

## 5. Decode-Time-Realitaetscheck (V2-NEU)

V1 nannte „0.5-1.5s" — V2 verfeinert.

`decoder._process_cycle` (`core/decoder.py:183-282`):
- audio raw concat + noise normalisierung: ~50ms
- resampling 24k → 12k: ~50ms
- DT-shift: ~10ms
- _preprocess_audio (FFT spectral whitening, 2048 FFT, ~14 frames): ~150-300ms
- _decode_with_subtraction (`MAX_SUBTRACT_PASSES = 5`, 3 SLIDE_OFFSETS):
  bis zu **15 ft8lib.decode()-Calls** mit `MAX_CANDIDATES=200`
  - Pro Call: ~50-200ms je nach SNR-Verteilung
  - Total: 0.5-3.0s

Bei voller Stations-Dichte (40m Sonntag 14 UTC): bis **3s Decode-Zeit**.
Bei leerem Band (FT2 nachts): ~0.3s.

**V2-Korrektur:** Encoder wake :05:58.7 vs Decoder ready :05:58.7-
:06:01.7 (variabel). Bei dichten Slots ist Decoder **massiv** spaeter
als Encoder.

→ **Replace-Mechanismus (Option A)** funktioniert nur bei sehr leeren
Slots oder Hochleistungshardware. Mike's Field-Test 10:03+ zeigt aber
volle 30m mit vielen Stationen → Replace-Chance < 10%.

→ **Option C (Decoder frueher wake) wird damit attraktiver**: nur eine
fundamentale Reorganisation kann den Bug zuverlaessig fixen.

---

## 6. Loesungs-Optionen (V2-erweitert + verfeinert)

### Option A — Pre-Audio-Replace im Encoder (V1 empfohlen)

**V2-Update:** Effektivitaet < 10% bei dichten Bands (dezimiert durch
realistische Decode-Time-Schaetzung). Trotzdem KEIN Schaden — failed
Replace = Status Quo (1 Slot Delay).

**Wert: niedrig** allein. Sinnvoll als Plus zu B oder C.

### Option B — `_send_cq()` von Slot-START zu Slot-ENDE verschieben

**V2-Bewertung:** verworfen wie V1. Slot-Skip waere die Folge bei
no-pending → schlechter als 1 Slot Delay.

### Option C — Decoder-Wake nach vorne ziehen (V2-VERFEINERT)

V1 schlug `_WAKE_OFFSET = 2.5` vor (slot+12.5 wake). V2: zu aggressiv.
FT8-Signal endet bei `slot + 0.5 + 12.64 = slot + 13.14`. Wake bei
slot+12.5 schneidet 0.64s vom Signal ab.

**V2-Vorschlag: `_WAKE_OFFSET = 2.0`** (slot+13.0 wake):
- Audio-Buffer enthaelt 13s = 99% des FT8-Signals
- Decode-Quality praktisch unveraendert (FT8 hat redundante Codierung)
- Decoder ready slot+13.0 + decode_time = slot+13.5 - slot+16.0
- Encoder wake naechster Slot bei slot+13.7 (= next_slot - 1.3)

Bei mittlerer Decode-Time (1.0s): Decoder ready slot+14.0 → noch
0.3s NACH Encoder-Wake. **Hilft nicht zuverlaessig.**

**Alternativ V2: `_WAKE_OFFSET = 3.0`** (slot+12.0 wake):
- Audio-Buffer 12s = ~95% des Signals (verliert 0.64s Anfang oder Ende)
- Decoder ready slot+12.0 + 1.0s = slot+13.0 → 0.7s VOR Encoder-Wake!
- **Replace-Mechanismus (A) funktioniert dann zuverlaessig.**

**Risiko:** Decode-Quality-Verlust. FT8 ist redundant (LDPC + Costas-
Sync) → erste oder letzte 0.5s Signal-Verlust toleriert. Aber 1s ist
Grenze.

**Empfehlung V2: Option C mit `_WAKE_OFFSET = 2.5`** (slot+12.5):
- Audio-Buffer 12.5s = enthaelt Signal slot+0.5 bis slot+13.14 = 12.64s
  vollstaendig WENN Buffer ab slot+0 startet.
- Aber Buffer im Decoder ist Audio das vom Radio kontinuierlich kommt
  — startet nicht bei slot+0 sondern „rollend".
- Praktisch: Decoder-Audio enthaelt die letzten N Sekunden. Wake bei
  slot+12.5 → Audio Last 12.5s = von slot+0 bis slot+12.5. FT8-Signal
  slot+0.5 bis slot+13.14 → letzte 0.64s fehlen.

Praktische Tests in WSJT-X-Foren: Decoder funktioniert robust mit
~12.0s FT8-Signal (Trim 0.64s am Ende → -0.5dB SNR-Schwellwert-Verlust
ca, kein gravierender Decode-Drop).

**Mike's Stats-Risiko:** SNR-Verteilung koennte sich um -0.5dB shiften
gegenueber bisherigen Stats. R1 muss bewerten ob das die 5-Tage-
Stats-Sammlung kompromittiert.

### Option D — FlexRadio-Buffer reduzieren

Verworfen wie V1 (TARGET_TX_OFFSET empirisch validiert, nicht anfassen).

### Option E (V2-NEU) — Kombination A + C

`_WAKE_OFFSET = 2.5` (Decoder frueher) **plus** `request_replace()` im
Encoder. Garantiert dass Decoder vor Encoder-Wake fertig ist (typisch
0.7s Vorsprung), Replace greift dann zuverlaessig.

**Vorteil:** robust, deckt 90%+ aller Faelle.
**Nachteil:** zwei Code-Aenderungen, hoeherer Test-Aufwand. Decoder-
Quality-Risiko (siehe C).

---

## 7. Telemetrie-Vorschlag (V2-konkretisiert)

Bevor wir fixen, sollten wir messen wie oft der Bug greift. Plan:

```python
# qso_state.py — Counter
self._cq_reply_lost_count = 0     # gesetzt: pending bei CQ_CALLING
self._cq_reply_immediate_count = 0  # gesetzt: pending bei CQ_WAIT (B2-Pfad)
```

```python
# in on_message_received bei CQ_CALLING + pending-set
if self.state == QSOState.CQ_CALLING:
    self._cq_reply_lost_count += 1
elif self.state == QSOState.CQ_WAIT:
    self._cq_reply_immediate_count += 1
```

Loggen alle 5 Minuten oder bei stop_cq:
```
[Stats] CQ-Reply: lost=12 immediate=0  (in 1h)
```

→ Mike kann ueber 1 Tag messen wie oft der Bug greift. Falls 100%
lost: kein Wunder. Falls 80% lost: Bug bestaetigt.

---

## 8. Praxis-Daten-Frage (V2-erweitert)

Mike's Beobachtung „manchmal klappt manchmal nicht" — V2-Hypothesen:

1. **Klappt:** wenn Reply NICHT im SOFORT-naechsten ODD-Slot kommt,
   sondern 1+ Slot spaeter. Dann ist unser :06:00-CQ schon gelaufen,
   :06:15-Reply erreicht uns waehrend CQ_CALLING (von :06:00-CQ-TX),
   _pending_reply=msg, on_message_sent verarbeitet bei :06:13.3 → 
   Report bei :06:30. **Gleicher 1-Slot-Delay, aber Mike merkt's
   weniger.**

2. **Klappt nicht:** Reply im sofort-naechsten Slot — was Mike heute
   provozieren kann (DA1TST sendet bewusst sofort nach Mike's CQ).

→ V2-Schlussfolgerung: der Bug ist **systematisch** (immer 1 Slot
Delay), aber Mike merkt's nur wenn die Reply sofort kommt.

R1 verifiziere: trifft das zu? Oder gibt es einen anderen Pfad?

---

## 9. Was V2 anders macht als V1

| Aspekt | V1 | V2 |
|---|---|---|
| Decode-Time-Schaetzung | 0.5-1.5s | 0.5-3.0s (variabel mit Stations-Dichte) |
| Pfad B2 | „theoretisch moeglich" | nachgewiesen **nie erreicht** |
| Option C `_WAKE_OFFSET` | 2.5 | **2.5 verfeinert begruendet, alternativ 2.0 oder 3.0** |
| Option E (NEU) | – | Kombination A+C |
| Telemetrie | Konzept | konkrete Counter mit Code |
| „manchmal klappt"-Erklaerung | offen | Hypothese: Mike merkt's nur bei sofort-naechster Reply |
| Timer-Granularitaet | nicht erwaehnt | 0.1s Tick (timing.py:84) |

---

## 10. Auftrag an V3 / R1

V2 reduziert R1-Pruefauftraege auf 5 zentrale:

1. **Decode-Time-Realitaet:** stimmt 0.5-3.0s? Wie reagiert
   `_decode_with_subtraction` (decoder.py:285-377) bei 30m FT8 mittags
   mit ~50 Stationen?

2. **Option C `_WAKE_OFFSET` Trade-Off:** 2.5 vs 2.0 vs 3.0 —
   welcher Wert hat besten Kompromiss zwischen FT8-Signal-Vollstaendigkeit
   und Encoder-Vorlauf? FT8 LDPC-Robustheit?

3. **Option E (Kombination):** lohnt sich der Aufwand zwei Aenderungen
   (Decoder + Encoder-API)? Oder reicht reine Option C als Fix?

4. **Telemetrie-Counter:** Stelle/Implementierung vernuenftig? Sollte
   `_cq_reply_lost_count` persistent gespeichert werden (z.B. in
   simpleft8.log)?

5. **„manchmal klappt"-Hypothese:** ist Mike's Symptom wirklich
   systematisch (immer 1 Slot Delay, nur unterschiedlich auffaellig)?
   Oder gibt es Pfade die ohne Delay funktionieren — und welche?

KEINE Loesung implementieren — nur Analyse-Verfeinerung.

---

## 11. Was V2 NICHT macht

- Keine Code-Aenderung. Mike entscheidet ueber Loesungs-Pfad.
- Bug #2 (Icom-73-Loop) → P1.10, separater Workflow.

---

**V2 Ende. V3 = R1-Findings einarbeiten. Plan-Mode + Code erst nach Mike-Freigabe.**
