# V1 — Implementierungs-Plan: QSO-Panel Slot-Tag/Zeit-Fix

## Vorlage / Input

**Diagnose abgeschlossen:**
- Symptom-Doku: `prompts/qso_panel_slot_display_v2.md`
- R1-Diagnose: `prompts/qso_panel_slot_display_r1.md` (Option A empfohlen)
- Log-Beweis: `~/.simpleft8/simpleft8.log` zeigt regelmaessig
  `Zu wenig Audio: X < 90000` → Audio-Buffer-Lag bei FlexRadio VITA-49 →
  Decoder-Output kommt im Folge-Slot, `time.time()` zur Decode-Zeit ist
  damit nicht mehr im TX-Slot der empfangenen Nachricht.

**Wichtige R1-Luecke:** R1 hatte `core/timing.py` nicht. Ich habe es
nachgelesen — `FT8Timer.is_even_cycle()` (timing.py:57-58) nutzt das
gleiche Wallclock-zur-Aufruf-Zeit-Pattern wie `qso_panel._slot_tag()`.
Wenn `_assign_slot_parity` (mw_cycle.py:135-152) damit `m._tx_even`
setzt und der Aufruf-Zeitpunkt im Folge-Slot liegt, ist auch
`m._tx_even` falsch. R1's Option A nutzt `m._tx_even` als Quelle —
**reicht nur, wenn `m._tx_even` selbst korrigiert wird.**

## Architektur-Entscheidung

**Decoder ist die einzige sichere Slot-Quelle.** Im `_process_cycle`-
Thread weiss der Decoder zur Wake-Zeit exakt zu welchem TX-Slot er
gerade arbeitet (Wake bei `slot_start + 13.5s` fuer FT8). Diese
Information faellt aktuell weg, sobald die Messages aus dem Decoder
kommen — ab da rechnet alles mit `time.time()` zur GUI-Aufruf-Zeit.

**Loesung:** Decoder setzt zwei Felder auf jede Message:
- `m._slot_start_ts: float` — UTC-Sekunden, Slot-Start des TX-Slots
- `m._tx_even: bool` — `int(slot_start_ts / cycle_duration) % 2 == 0`

Damit ist die Quelle latenz-unabhaengig. Alle Konsumenten (qso_panel,
auto_hunt, qso_state, station_stats) lesen diese Felder statt eigene
`time.time()`-basierte Berechnungen anzustellen.

## Konkrete Aenderungen

### 1. `core/decoder.py` — Slot-Quelle setzen

**Stelle:** `_process_cycle` in der Schleife wo Messages emittiert werden
(aktuell `decoder.py:237-249`).

**Aenderung:** Vor dem `cycle_decoded.emit(messages)` und vor jedem
`message_decoded.emit(msg)` werden auf jeder `msg` zwei Felder gesetzt:

```python
# Slot-Start aus Wake-Zeit ableiten:
# Wake war bei slot_start + (SLOT - WAKE_OFFSET) -> slot_start = wake - (SLOT - WAKE_OFFSET)
# Statt rueckrechnen: slot_start = floor(wake / SLOT) * SLOT
# (wake liegt sicher noch IM Slot wenn WAKE_OFFSET > 0)
slot = self._cycle_duration   # 15.0 / 7.5 / 3.8
slot_start_ts = int(wake_time / slot) * slot
tx_even = int(slot_start_ts / slot) % 2 == 0
for m in messages:
    m._slot_start_ts = slot_start_ts
    m._tx_even = tx_even
```

**Voraussetzung:** `wake_time` muss in `_process_cycle` verfuegbar sein.
Aktuell nicht vorhanden — wird vom `_tick_loop` (decoder.py:132-145)
berechnet, dann Thread gestartet ohne den Zeitpunkt durchzureichen.

**Anpassung Thread-Start (decoder.py:163-167):**
```python
threading.Thread(
    target=self._process_cycle,
    args=(chunks, wake_time),    # <-- wake_time jetzt mit
    daemon=True,
).start()
```

`wake_time = time.time()` direkt vor dem Thread-Start (= unmittelbar
nach `time.sleep(wait)`-Aufruf, bevor Audio-Chunks geholt werden) ist
zuverlaessig im Slot N (FT8: bei N*15+13.5).

### 2. `ui/mw_cycle.py` — `_assign_slot_parity` aufraeumen

**Stelle:** `_assign_slot_parity` (mw_cycle.py:135-152).

**Aenderung:** Statt `is_even_cycle()` zur Aufruf-Zeit den vom Decoder
gesetzten Wert respektieren. Fallback nur wenn Feld fehlt
(Kompatibilitaet zu Tests / Mocks).

```python
def _assign_slot_parity(self, messages):
    """Slot-Parity respektieren — Decoder hat sie schon gesetzt.

    Falls die Message kein _tx_even / _slot_start_ts hat (z.B. in Tests
    ohne echten Decoder), faellt zurueck auf is_even_cycle()/floor(now).
    """
    if not messages:
        return
    fallback_even = self.timer.is_even_cycle()
    fallback_now = ntp_time.get_time()
    slot = self.settings.cycle_duration
    fallback_slot_start = int(fallback_now / slot) * slot
    for m in messages:
        if not hasattr(m, '_tx_even'):
            m._tx_even = fallback_even
        if not hasattr(m, '_slot_start_ts'):
            m._slot_start_ts = fallback_slot_start
```

**Wichtig:** Der bisherige FT2-Spezialfall (`_slot_from_utc(utc)`) faellt
weg — der Decoder liefert die korrekte Quelle fuer alle Modi. R1 und
Self-Review mussen pruefen ob das wirklich aequivalent ist (FT2-Slot
3.8s, gerade-Sek-Pruefung in `_slot_from_utc`).

### 3. `ui/qso_panel.py` — `add_rx`/`add_tx` Parameter

**Aenderung:** Neue optionale Parameter `tx_even` und `slot_start_ts`.
Wenn gesetzt, werden sie verwendet. Wenn nicht (Backward-Compat),
faellt der bisherige Code-Pfad ein.

```python
def add_rx(self, message: str,
           tx_even: bool | None = None,
           slot_start_ts: float | None = None):
    """Empfangene Antwort anzeigen."""
    self._cq_count = 0
    if slot_start_ts is None or tx_even is None:
        # Fallback (z.B. Tests, alte Caller)
        now = time.time()
        slot = getattr(self, '_cycle_duration', 15.0)
        slot_start_ts = now - (now % slot)
        tx_even = int(slot_start_ts / slot) % 2 == 0
    utc = time.strftime("%H:%M:%S", time.gmtime(slot_start_ts))
    tag = "[E]" if tx_even else "[O]"
    self._append_colored(f"{utc} {tag} ←  Empf.   {message}", "#44BBFF")
```

**`add_tx` analog** — Parameter hinzufuegen, aber Default-Pfad bleibt
wie bisher (TX wird zu Slot-Start aufgerufen, ist meist korrekt). Fuer
Konsistenz dennoch die Quelle durchreichen wenn verfuegbar.

### 4. `ui/mw_cycle.py:762` — Caller anpassen

```python
if msg.target == self.settings.callsign:
    self.qso_panel.add_rx(
        msg.raw,
        tx_even=msg._tx_even,
        slot_start_ts=msg._slot_start_ts,
    )
```

### 5. `_slot_tag()` in qso_panel.py

Wird nicht mehr aufgerufen wenn der neue Pfad benutzt wird, kann aber
als Fallback in `add_tx` bleiben. Alternative: ganz entfernen wenn nirgends
mehr referenziert. Zu pruefen mit grep.

## Tests

### Neue Tests `tests/test_slot_display.py`

1. **`test_add_rx_uses_provided_slot`** — `add_rx("DA1MHH X 73",
   tx_even=False, slot_start_ts=1730000115)` schreibt `[O]` und Zeit
   die zu :15-Slot passt, unabhaengig von `time.time()`.
2. **`test_add_rx_fallback_when_no_slot_info`** — alter Caller-Pfad
   funktioniert weiter (keine Regression in Tests die `add_rx(msg)` rufen).
3. **`test_assign_slot_parity_respects_decoder`** — Message mit
   `_tx_even=False` und `_slot_start_ts=...` bekommt diese Werte
   nicht ueberschrieben.
4. **`test_assign_slot_parity_fallback`** — Message ohne Felder bekommt
   Werte aus `is_even_cycle()` / `time.time()` (Test-Mock).

### Bestehende Tests pruefen

- `test_qso_panel_*` — falls vorhanden, Signaturen aktualisieren
- `test_decoder_*` — pruefen dass `_process_cycle` mit neuem
  `wake_time`-Argument aufgerufen werden kann
- `test_auto_hunt_*` — `m._tx_even` wird dort gelesen, sicherstellen dass
  Decoder-gesetzter Wert kompatibel mit Auto-Hunt-Erwartung ist

## Risiken

1. **Auto-Hunt-Regression:** `_tx_even` wird in `core/auto_hunt.py` und
   `mw_qso.py:85,423` benutzt. Wenn der jetzige Code mit dem
   *Folge-Slot*-Wert arbeitet (wegen Latenz) und durch Inversion
   trotzdem korrekt war, koennte der Fix Auto-Hunt brechen. Voller
   Auto-Hunt-Test-Lauf vor Commit Pflicht.

2. **FT2-Pfad:** `_slot_from_utc(utc)` faellt weg. Wenn `_utc_str`
   bisher als ground-truth fuer FT2 diente und Decoder-`wake_time`
   nicht aequivalent ist, koennte FT2 brechen. Mike funkt aber
   praktisch nur FT8 — geringes Risiko, aber verifizieren.

3. **Stats-Logging:** `core/station_stats.py` wird in `_log_stats`
   aufgerufen (`mw_cycle.py`). R1 hat das nicht analysiert — wir
   sollten pruefen ob station_stats `time.time()` zur Stunden-Datei-
   Bestimmung nutzt und dort auch `slot_start_ts` durchreichen.

4. **Backward-Compat-Tests:** Tests die `add_rx(msg)` ohne neue Parameter
   rufen, mussen weiterhin laufen (Fallback-Pfad). Default-Werte `None`
   sicherstellen.

## Akzeptanzkriterien

- AC-1: Field-Test: RX-Eintraege im QSO-Panel zeigen ODD-Tag fuer
  Nachrichten der Gegenstation, EVEN-Tag fuer eigene TX
- AC-2: RX-Zeitstempel = Slot-Start des TX-Slots der Nachricht (z.B.
  `03:38:15 [O]` statt `03:38:30 [E]`)
- AC-3: Auto-Hunt funktioniert weiter (kein Slot-Affinitaets-Bug)
- AC-4: Alle bestehenden Tests gruen (742 → noch 742 oder mehr)
- AC-5: 4 neue Tests (siehe Test-Plan oben)
- AC-6: FT4 + FT2 Smoke-Test (Slot-Anzeige korrekt mit kuerzeren
  Cycle-Durations)

## Offene Fragen an Self-Review (V2) und R1

1. Ist `wake_time = time.time()` direkt nach `time.sleep(wait)` wirklich
   immer im Slot N? Oder kann es bei System-Lag (Sleep-Drift) ueber die
   Slot-Boundary rutschen?
2. `int(wake_time / slot) * slot` — was wenn `wake_time` ein paar
   Mikrosekunden NACH der Slot-Boundary liegt (z.B. `slot * (N+1) +
   0.001`)? Dann waere `slot_start_ts = (N+1) * slot` — falscher Slot.
   Schutz mit `(int(wake_time / slot) - epsilon)`?
3. Sollte `_slot_start_ts` auch im Decoder bei `_decode_busy`-Skip oder
   `kein Audio` ausgeloest werden? (Aktuell nicht — keine messages
   emittiert in dem Pfad.)
4. Migration-Risiko `_assign_slot_parity` — bestehende FT2-Logik
   (`_slot_from_utc`) wirklich gleichwertig?
5. Sollte `station_stats.log_cycle` ebenfalls `slot_start_ts`
   reinbekommen, oder ist die Stunden-Auswertung tolerant genug
   (R1-Risikobewertung: < 0.1 % falsche Slots, kein Bias)?
6. `_slot_tag()` in qso_panel — komplett entfernen oder als Fallback
   behalten?

## Workflow-Stand

- V1: dieses Dokument
- V2: noch zu schreiben (frische KI, Self-Review)
- R1: V2 an DeepSeek-R1
- R1-Validierung: kritisch lesen, Halluzinationen filtern
- V3: finaler Plan → Mike-Freigabe → Plan-Mode → Code
