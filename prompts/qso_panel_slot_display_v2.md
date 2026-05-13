# V2 — QSO-Panel: Slot-Tag und Zeitstempel bei RX-Eintraegen falsch

## Auftrag an R1 (deepseek-reasoner)

Mike (DA1MHH) hat einen visuellen Bug im QSO-Panel beobachtet. Wir
brauchen eine **Diagnose** (nicht direkt Fix) — du sollst:
1. Pruefen ob die Root-Cause-Hypothese stimmt (Decoder-Output-Slot vs
   TX-Slot der empfangenen Nachricht).
2. Erklaeren warum die Anzeige im Symptom 1 Slot zu spaet + Tag falsch ist,
   obwohl decoder.py die Decode-Loop *vor* Slot-Ende plant.
3. Alle Stellen finden wo `time.time()` zur Slot-Berechnung am falschen
   Zeitpunkt benutzt wird (Stats-Logging, ADIF, andere UI-Pfade).
4. Loesungs-Empfehlung A/B/C bewerten oder neue Option vorschlagen.
5. Risiko: Sind Stats-Daten in `statistics/` ggf. ebenfalls falsch
   gelabelt? Wenn ja, was tun mit historischen Daten?

## Hardware-Sanity (gesicherte Annahmen)

- QSO mit DA1TST 03:37-:40 UTC ist **wirklich passiert** und korrekt
  abgeschlossen. IC-7300 (Referenzgeraet) zeigte DT 0.0-0.1s.
- DA1MHH sendet konsequent EVEN, DA1TST muss zwangslaeufig ODD gesendet
  haben — sonst waere kein QSO zustande gekommen.
- ANT1=TX (Sende-Antenne, korrekt), Modus FT8 (15s-Slots), Band 30m,
  RX-Modus Normal.
- TX/RX gleichzeitig im selben Slot ist physikalisch ausgeschlossen
  (Half-Duplex-FlexRadio). → Bug ist **rein in der Anzeige**.

## Symptom (Field-Test 2026-05-05)

```
03:36:00 [E] →  Sende   CQ DA1MHH J031
03:36:30 [E] →  Sende   CQ DA1MHH J031
03:37:00 [E] →  Sende   CQ DA1MHH J031
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
03:39:30 [E] →  Sende   CQ DA1MHH J031
03:40:30 [E] →  Sende   CQ DA1MHH J031
```

Erwartet (rechtfertigt das echte FT8-Pacing):

```
03:37:30 [E] →  Sende   CQ DA1MHH J031              ← TX :37:30 EVEN ✓
03:37:45 [O] ←  Empf.   DA1MHH DA1TST J031          ← DA1TST CQ-Reply :45 ODD
03:38:00 [E] →  Sende   CQ DA1MHH J031              ← naechste TX-Pause
       Antworte DA1TST
03:38:15 [O] ←  Empf.   DA1MHH DA1TST J031          ← DA1TST wiederholt
03:38:30 [E] →  Sende   DA1TST DA1MHH -22  (ANT1)
03:38:45 [O] ←  Empf.   DA1MHH DA1TST R+18
03:39:00 [E] →  Sende   DA1TST DA1MHH RR73 (ANT1)
03:39:15 [O] ←  Empf.   DA1MHH DA1TST 73
```

Anzeige haengt also einen **ganzen Slot** vor und vergibt dasselbe
EVEN-Tag wie unsere TX-Slots.

## Code-Pfad

### Anzeige-Code (vermuteter Bug-Ort)

`ui/qso_panel.py:147-151` — Slot-Tag aus aktueller Wallclock:
```python
def _slot_tag(self) -> str:
    now = time.time()
    slot = getattr(self, '_cycle_duration', 15.0)
    return "[E]" if int(now / slot) % 2 == 0 else "[O]"
```

`ui/qso_panel.py:153-167` — `add_tx`:
```python
def add_tx(self, message: str, ant_label: str = ""):
    now = time.time()
    slot = getattr(self, '_cycle_duration', 15.0)
    slot_start = now - (now % slot)
    utc = time.strftime("%H:%M:%S", time.gmtime(slot_start))
    tag = self._slot_tag()
    line = f"{utc} {tag} →  Sende   {message}"
    ...
```

`ui/qso_panel.py:169-177` — `add_rx`:
```python
def add_rx(self, message: str):
    self._cq_count = 0
    now = time.time()
    slot = getattr(self, '_cycle_duration', 15.0)
    slot_start = now - (now % slot)
    utc = time.strftime("%H:%M:%S", time.gmtime(slot_start))
    tag = self._slot_tag()
    self._append_colored(f"{utc} {tag} ←  Empf.   {message}", "#44BBFF")
```

### Decoder-Wake-Logik (decoder.py:132-145)

```python
while self._running:
    now = time.time()
    _SLOT = {"FT8": 15.0, "FT4": 7.5, "FT2": 3.8}.get(self._mode, 15.0)
    _WAKE_OFFSETS = {"FT8": 1.5, "FT4": 0.5, "FT2": 0.3}
    _WAKE = _SLOT - _WAKE_OFFSETS.get(self._mode, 1.5)  # FT8: 13.5
    cycle_pos = now % _SLOT
    if cycle_pos < _WAKE:
        wait = _WAKE - cycle_pos
    else:
        wait = _SLOT - cycle_pos + _WAKE
    time.sleep(wait)
    ...
    threading.Thread(target=self._process_cycle, args=(chunks,)).start()
```

→ Decoder wacht 1.5 s **vor** Slot-Ende. Decode in eigenem Thread,
typische Dauer < 0.5 s laut HISTORY.md. **Theoretisch** sollte
`cycle_decoded.emit()` noch im selben Slot wie der TX-Slot der Nachricht
feuern.

### Caller-Pfad (mw_cycle.py:753-764)

```python
def on_message_decoded(self, msg: FT8Message):
    if not self.rx_panel._rx_active:
        return
    self.control_panel.update_snr(msg.snr)
    self.qso_sm.set_last_snr(msg.snr)
    if msg.target == self.settings.callsign:
        self.qso_panel.add_rx(msg.raw)        # ← hier
    self.qso_sm.on_message_received(msg)
```

`add_rx` bekommt nur `msg.raw` — keine Slot-Info, kein Timestamp.

### Existierende Slot-Source-of-Truth

`ui/mw_cycle.py:135-152` `_assign_slot_parity` setzt auf jeder Message
`m._tx_even`. Kommentar:
> "ft8lib dekodiert innerhalb des SELBEN Slots (< 0.3s) → is_even_cycle()
> zeigt noch den aktuellen Slot, KEIN not nötig. FT2: 3.75s Zyklen → Slot
> aus Nachricht-UTC berechnen (Timer-Drift zu gross)."

**Widerspruch:** Wenn das stimmt, sollte `add_rx` mit `time.time()` zum
Decode-Zeitpunkt das richtige Tag berechnen (gleicher Slot wie `_tx_even`).
Mike's Anzeige zeigt aber den FOLGE-Slot.

## Self-Review-Findings (Luecken in V1, jetzt geschlossen)

1. **Hypothese „Decoder feuert 2 s nach Slot-Ende" war falsch.** Der
   Decoder wacht *vor* Slot-Ende (decoder.py:138-139). DT_BUFFER_OFFSET=2.0
   ist nur eine DT-Korrektur in der Decode-Output-Verarbeitung, kein
   Zeitversatz beim Wake.
2. **Open question:** Warum hinkt die Anzeige trotzdem 1 Slot hinterher?
   Moegliche Ursachen die R1 pruefen soll:
   - **Qt-Signal-Queue-Lag:** `cycle_decoded` → `message_decoded` →
     `on_message_decoded` ueber `Qt.QueuedConnection`. Dispatch im
     GUI-Thread. Wenn GUI-Thread busy (z.B. RX-Panel-Update,
     Histogramm-Repaint), kann Slot-Wechsel zwischendurch passieren.
   - **Audio-Buffer-Lag:** FlexRadio VITA-49-Audio kommt vermutlich mit
     1-2 s Lag. Wenn der Audio-Buffer fuer Slot N erst bei N+1.5s gefuellt
     ist, schiebt der Decoder den Wake auf den Folge-Slot.
   - **Decode-Busy-Skip (decoder.py:148-150):** Wenn ein Decode 14+ s
     dauert (Sub-Pass 5x), wird der naechste Slot geskippt — der
     uebernaechste Decode laeuft dann auf altem Audio-Buffer und sieht eine
     verschobene Slot-Zeit.
   - **`_decode_busy`-Lock-Variable + Thread-Spawn:** decoder.py:163-167
     spawnt einen Thread. Thread-Start hat Latenz. `t_start` in
     `_process_cycle` ist die Thread-Start-Zeit, nicht die Wake-Zeit.
   - **Statusbar-/Repaint-Lag:** wenn Mike's GUI auf einem entfernten
     Display (Display 2 via Fernwartung-Setup) laeuft, koennte
     Repaint-Lag den `time.time()`-Punkt verschieben — **unwahrscheinlich,
     weil `add_rx` selbst `time.time()` zieht, nicht das Painting.**
3. **Falscher Slot-Tag fuer ALLE 5 RX-Empfaenge** im Log. Nicht
   sporadisch — systematisch. Das spricht **gegen** Qt-Signal-Lag (waere
   sporadisch) und **fuer** einen konsistenten Versatz im Decoder oder
   Audio-Buffer.
4. **Sanity-Check:** Im Log-File `~/.simpleft8/simpleft8.log` muesste der
   Decoder seine `[RX]` Zeilen schreiben (decoder.py:248):
   ```python
   _now = time.time()
   _slot = "EVEN" if int(_now / 15.0) % 2 == 0 else "ODD"
   _utc = time.strftime("%H:%M:%S", time.gmtime(_now))
   ```
   R1, falls dieses Log fuer das Field-Test-QSO vorliegt, sieht man dort
   ob der Decoder selbst schon im Folge-Slot operiert.
5. **`add_tx`-Pfad nicht verifiziert:** `add_tx` wird via
   `tx_started`-Signal aufgerufen (`encoder.py:42, 275`). Wann genau
   feuert `tx_started`? Wenn am Anfang der TX-Phase (Slot-Start +
   protokoll-spezifischer Offset 0.5s), dann ist `time.time()` im richtigen
   Slot. Wenn aber spaeter (z.B. nach erstem Audio-Sample-Push), koennte
   auch das brechen. R1, schau dir encoder.py um Zeile 275 an.

## Akzeptanzkriterien (unveraendert von V1)

1. **AC-1 RX-Slot-Tag korrekt:** ODD wenn Gegenstation im ODD sendet.
2. **AC-2 RX-Zeitstempel = Slot-Start des empfangenen TX**, nicht Decode-Zeit.
3. **AC-3 TX-Anzeige unveraendert.**
4. **AC-4 Mode-Konsistenz** FT8/FT4/FT2.
5. **AC-5 Tests** fuer add_rx mit Slot-Verschiebung.
6. **AC-6 Stats-Daten-Integritaet:** R1 prueft ob station_stats /
   `statistics/<Modus>/<Band>/<Proto>/YYYY-MM-DD_HH.md` ebenfalls den
   falschen Slot/Stunde verwendet — und falls ja, ob das in
   Pooled-Mean-Auswertungen (40m FT8 +88%/+124%) bisher Bias erzeugt hat.

## Loesungs-Optionen (offen fuer R1)

**Option A — Caller liefert Slot-Info:**
```python
def add_rx(self, message: str, tx_even: bool, slot_start_ts: float):
    ...
```
Caller `mw_cycle.py:762`:
```python
self.qso_panel.add_rx(msg.raw, tx_even=msg._tx_even,
                      slot_start_ts=msg._slot_start_ts)
```
Voraussetzung: `_assign_slot_parity` setzt zusaetzlich
`m._slot_start_ts = self.timer.current_slot_start()` (oder aequivalent).

**Option B — Rueckrechnung in qso_panel:**
Annahme: Decoder feuert IMMER konsistent X Slots nach TX-Slot.
Wenn X=1 (Folge-Slot): `tx_slot_start = (int(now / slot) - 1) * slot`.
Wenn X=0 (selber Slot): wie aktuell.
**R1, kannst du sagen welches X tatsaechlich gilt? Bitte mit Code-Beleg.**

**Option C — Caller liefert nur `tx_even`, qso_panel rechnet Zeit
zurueck:**
Wenn `tx_even` bekannt ist, kann qso_panel pruefen ob aktuelles
`is_even_cycle` damit uebereinstimmt — wenn nicht, 1 Slot zurueck.
Robust gegen Variabilitaet (Decoder mal selber Slot, mal Folge-Slot).

## Konkrete R1-Fragen

1. **Welcher Mechanismus** verzoegert die Anzeige um 1 Slot, gegeben die
   Decoder-Wake-Logik in decoder.py:132-145?
2. **Stimmt der Kommentar** in `_assign_slot_parity` (mw_cycle.py:138-141)
   mit der Realitaet ueberein? Wenn ja, warum sehen wir den Versatz?
3. **`_tx_even` vs Anzeige:** Wenn `m._tx_even` korrekt ist (laut Code-
   Notiz in CLAUDE.md), wieso bekommt `add_rx` ueber `time.time()` einen
   anderen Slot-Tag als `m._tx_even` zur selben Zeit?
4. **Welche `time.time()`-Stellen** im Codebase verwenden die aktuelle
   Wallclock zur Slot-Bestimmung und sind potentiell von demselben Versatz
   betroffen? Liste mit Datei:Zeile.
5. **Stats-Logging-Risiko:** `core/station_stats.py` schreibt nach
   `statistics/<Modus>/<Band>/<Proto>/YYYY-MM-DD_HH.md`. Welcher
   Zeitpunkt bestimmt die Stunde? Wenn Decode-Zeit, dann liegen ggf.
   einzelne Slots am Stunden-Wechsel in der falschen Datei.
6. **Beste Loesung A/B/C** — oder gibt es eine bessere? Bitte mit
   Begruendung was am robustesten + minimal-invasiv ist.

## Begleitete Files (volle Files anhaengen)

- `ui/qso_panel.py` (Bug-Ort)
- `ui/mw_cycle.py` (Caller, _assign_slot_parity)
- `core/decoder.py` (Wake-Logik)
- `core/encoder.py` (tx_started-Signal)
- `core/station_stats.py` (Stats-Logging-Pfad)
- `core/timing.py` (Timer/is_even_cycle/current_slot_start)
- `core/station_accumulator.py` (_utc_display)
