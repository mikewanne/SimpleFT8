# V1 — QSO-Panel: Slot-Tag und Zeitstempel bei RX-Eintraegen falsch

## Symptom (Mike Field-Test 2026-05-05 03:36-03:40 UTC)

FT8 30m Normal, FlexRadio TX nach IC-7300. QSO mit DA1TST lief sauber
(IC-7300 zeigte DT 0.0-0.1s, alle Reports + RR73 + 73 ausgetauscht).
Aber das QSO-Panel-Log zeigt RX und TX im **selben** Slot mit demselben
Slot-Tag `[E]`:

```
03:37:30 [E] →  Sende   CQ DA1MHH J031
03:38:00 [E] ←  Empf.   DA1MHH DA1TST J031
03:38:00 [E] →  Sende   CQ DA1MHH J031
       Antworte DA1TST (ANT1)
03:38:30 [E] ←  Empf.   DA1MHH DA1TST J031
03:38:30 [E] →  Sende   DA1TST DA1MHH -22  (ANT1)
03:39:00 [E] ←  Empf.   DA1MHH DA1TST R+18
03:39:00 [E] →  Sende   DA1TST DA1MHH RR73 (ANT1)
03:39:30 [E] ←  Empf.   DA1MHH DA1TST 73
       ✓ QSO mit DA1TST komplett
```

DA1MHH sendet konsequent EVEN (:00, :30) — korrekt. DA1TST muss
zwangslaeufig im Gegen-Slot (ODD: :15, :45) gesendet haben, sonst waere
das QSO physikalisch nicht zustande gekommen. Das QSO IST aber zustande
gekommen → die Hardware-Pacing ist korrekt, **nur die Anzeige ist
falsch**.

## Erwartete Anzeige

```
03:37:30 [E] →  Sende   CQ DA1MHH J031
03:37:45 [O] ←  Empf.   DA1MHH DA1TST J031
03:38:00 [E] →  Sende   CQ DA1MHH J031
       Antworte DA1TST (ANT1)
03:38:15 [O] ←  Empf.   DA1MHH DA1TST J031
03:38:30 [E] →  Sende   DA1TST DA1MHH -22  (ANT1)
03:38:45 [O] ←  Empf.   DA1MHH DA1TST R+18
03:39:00 [E] →  Sende   DA1TST DA1MHH RR73 (ANT1)
03:39:15 [O] ←  Empf.   DA1MHH DA1TST 73
```

## Root-Cause-Hypothese

Datei `ui/qso_panel.py:169-177` (`add_rx`):

```python
def add_rx(self, message: str):
    self._cq_count = 0
    now = time.time()                              # ← Decoder-Output-Zeit
    slot = getattr(self, '_cycle_duration', 15.0)
    slot_start = now - (now % slot)                # ← Slot-Start zur Decode-Zeit
    utc = time.strftime("%H:%M:%S", time.gmtime(slot_start))
    tag = self._slot_tag()                         # ← Tag aus aktueller Zeit
    self._append_colored(f"{utc} {tag} ←  Empf.   {message}", "#44BBFF")
```

`_slot_tag()` (`qso_panel.py:147-151`):

```python
def _slot_tag(self) -> str:
    now = time.time()
    slot = getattr(self, '_cycle_duration', 15.0)
    return "[E]" if int(now / slot) % 2 == 0 else "[O]"
```

**Problem:** ft8lib läuft mit `DT_BUFFER_OFFSET=2.0s` — Decoder-Output kommt
~1-2 s **nach** Slot-Ende, also bereits im **Folge-Slot**. `time.time()`
zur Decode-Zeit zeigt damit den Folge-Slot, nicht den TX-Slot der
empfangenen Nachricht.

Beispiel: DA1TST sendet :15-:30 (ODD).
- Decoder feuert bei ~:31-:32.
- `time.time()` = 03:38:31, `int(:31/15) % 2 = 0` → `[E]` (falsch, sollte `[O]`).
- `slot_start = :30` → Anzeige-Zeit `03:38:30` (falsch, sollte `03:38:15`).

Das erklaert exakt das Symptom: jede RX-Zeile haengt einen Slot vor.

`add_tx` (`qso_panel.py:153-167`) hat dasselbe Konstrukt, leidet aber
nicht unter dem Effekt, weil das `tx_started`-Signal **am Slot-Anfang**
feuert — `time.time()` ist dann im richtigen Slot.

## Vorhandene Source-of-Truth im Code

In `ui/mw_cycle.py:135-152` setzt `_assign_slot_parity` auf jeder
empfangenen Message `m._tx_even`:

```python
def _assign_slot_parity(self, messages):
    msg_was_even = self.timer.is_even_cycle()
    mode = self.settings.mode
    for m in messages:
        if mode == "FT2":
            utc = getattr(m, '_utc_str', None) or getattr(m, '_utc_display', None)
            slot = _slot_from_utc(utc) if utc else None
            m._tx_even = slot if slot is not None else msg_was_even
        else:
            m._tx_even = msg_was_even
```

Der Kommentar darueber sagt:
> "ft8lib dekodiert innerhalb des SELBEN Slots (< 0.3s) → is_even_cycle()
> zeigt noch den aktuellen Slot, KEIN not nötig."

→ **R1, bitte verifiziere:** Stimmt der Kommentar mit dem tatsaechlichen
Verhalten ueberein? Bei `DT_BUFFER_OFFSET=2.0s` (FT8) startet ft8lib doch
erst 2 s nach Slot-Ende — wie kann es im selben Slot fertig sein? Oder
bezieht sich der Kommentar auf eine andere Decoder-Phase (Sub-Pass)?

## Akzeptanzkriterien

1. **AC-1 RX-Slot-Tag korrekt:** Wenn DA1TST im ODD-Slot (:15-:30) sendet,
   zeigt das QSO-Panel `[O]` — nicht `[E]`. Allgemein: Tag entspricht dem
   TX-Slot der empfangenen Nachricht, nicht der Decode-Zeit.
2. **AC-2 RX-Zeitstempel korrekt:** Anzeige zeigt Slot-START der
   empfangenen Nachricht (z.B. `03:38:15`), nicht den Folge-Slot
   (`03:38:30`).
3. **AC-3 TX-Anzeige unveraendert:** `add_tx` weiterhin korrekt
   (`03:38:00 [E] → Sende CQ ...` bleibt). Keine Regression.
4. **AC-4 Mode-Konsistenz:** Korrektur funktioniert fuer FT8 (15s),
   FT4 (7.5s) und FT2 (3.8s). FT2-Slot-Berechnung schon in
   `_assign_slot_parity` separat geloest (`_slot_from_utc`).
5. **AC-5 Tests:** Smoke-Test fuer `add_rx` mit Slot-Verschiebung —
   simulierter Decoder-Output 2s nach Slot-Ende muss als vorheriger Slot
   geloggt werden.
6. **AC-6 Statistics-Logging:** R1 prueft ob `core/station_stats.py` /
   `_log_stats` (mw_cycle.py) ebenfalls den falschen Slot verwendet — die
   Stats-Daten sind fuer Pooled-Mean kritisch und duerfen nicht falsch
   gelabelt sein.

## Loesungsskizze (offen fuer R1-Kritik)

**Option A — Caller liefert Slot-Info:**
```python
def add_rx(self, message: str, tx_even: bool | None = None,
           slot_start_ts: float | None = None):
    ...
```
Caller `mw_cycle.py:762`:
```python
self.qso_panel.add_rx(msg.raw, tx_even=msg._tx_even,
                      slot_start_ts=msg._slot_start)
```

**Voraussetzung:** Decoder oder `_on_cycle_decoded` setzt `_slot_start`
auf jeder Message (= TX-Slot-Start in Wallclock-Sekunden). Aktuell
existiert nur `_utc_display` (gesetzt in station_accumulator.py:59 mit
`time.time()` zur Decode-Zeit, nicht TX-Zeit).

**Option B — Rueckrechnung in qso_panel:**
```python
def add_rx(self, message: str):
    now = time.time()
    slot = getattr(self, '_cycle_duration', 15.0)
    # 1 Slot zurueck (Decoder feuert im Folge-Slot)
    tx_slot_start = (int(now / slot) - 1) * slot
    utc = time.strftime("%H:%M:%S", time.gmtime(tx_slot_start))
    tag = "[E]" if int(tx_slot_start / slot) % 2 == 0 else "[O]"
    self._append_colored(f"{utc} {tag} ←  Empf.   {message}", "#44BBFF")
```
Risiko: Nimmt an dass Decoder IMMER im Folge-Slot feuert. Bei sehr
schnellem Decoder oder GUI-Lag koennte das brechen.

**Option C — Caller liefert nur `tx_even`, Zeit aus mw_cycle berechnen:**
Mittelweg. mw_cycle hat `self.timer.is_even_cycle()` und kennt den Slot,
kann `slot_start` einmal zentral berechnen und weiterreichen.

R1, welche Option ist robust + minimal-invasiv? Gibt es weitere Stellen
im Code wo `time.time()` zur Slot-Berechnung am falschen Punkt benutzt
wird?

## Frage an R1

1. Stimmt die Root-Cause-Diagnose (Decoder feuert im Folge-Slot)?
2. Welche Option (A/B/C) ist sauber? Oder gibt es eine bessere?
3. Warum funktioniert `_assign_slot_parity` mit `is_even_cycle()` zur
   Decode-Zeit, wenn der Decoder erst 2 s nach Slot-Ende feuert? Ist der
   Kommentar veraltet, oder gibt es einen anderen Mechanismus?
4. Gibt es weitere `time.time()`-basierte Slot-Berechnungen (Stats,
   ADIF-Logging, ...) die denselben Bug haben?
5. Ist `add_tx` wirklich frei von dem Bug — oder kann `tx_started`-Signal
   in seltenen Faellen ueber Slot-Grenze feuern?
