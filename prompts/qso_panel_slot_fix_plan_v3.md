# V3 — Implementierungs-Plan: QSO-Panel Slot-Tag/Zeit-Fix (FINAL)

**Workflow-Trail:** V1 → V2 (Self-Review) → R1 (Validierung) → V3
- V1: `qso_panel_slot_fix_plan_v1.md`
- V2: `qso_panel_slot_fix_plan_v2.md`
- R1-Antwort: `qso_panel_slot_fix_plan_r1.md` (durchgehend positiv)

**R1-Validierung durch Claude:** Architektur, Wake-Drift und
Auto-Hunt-Analyse im Code verifiziert. `not _candidate.tx_even` an
`mw_cycle.py:512` und `mw_qso.py:87,425` existiert wirklich — R1's
Behauptung „kein Inversion-Schutz" stimmt. Eine zusaetzliche
`is_even_cycle()`-Stelle gefunden (`mw_qso.py:128`) — laeuft aber im
CQ-Start-Pfad auf User-Klick, ist NICHT latenz-betroffen, bleibt
unveraendert.

**R1-Empfehlungen aufgenommen in V3:** 2 Zusatztests, grep vor Commit 5.

---

## Architektur-Entscheidung (von R1 bestaetigt)

**Decoder ist die einzige sichere Slot-Quelle.** Im Decoder-Loop
(`core/decoder.py:132-145`) wird der Wake-Zeitpunkt gezielt gewaehlt;
dort ist die Information „zu welchem TX-Slot gehoert das Audio im
Buffer" verlustfrei verfuegbar. Der `target_slot_start` wird **vor**
`time.sleep(wait)` berechnet — driftfrei.

`target_slot_start` und das daraus abgeleitete `tx_even` wandern als
Message-Attribute (`_slot_start_ts`, `_tx_even`) bis zu allen
Konsumenten. Diese lesen die Attribute statt eigener `time.time()`-
basierter Berechnungen.

---

## Konkrete Aenderungen

### 1. `core/decoder.py` — Slot-Quelle berechnen + durchreichen

**1a. `_tick_loop` (decoder.py:132-167)** — `target_slot_start`
pre-sleep berechnen, `time.sleep(wait)`, dann `_process_cycle` mit
zusaetzlichen Args spawnen:

```python
while self._running:
    try:
        now = time.time()
        slot = {"FT8": 15.0, "FT4": 7.5, "FT2": 3.8}.get(self._mode, 15.0)
        wake_offset = {"FT8": 1.5, "FT4": 0.5, "FT2": 0.3}.get(self._mode, 1.5)
        wake_pos = slot - wake_offset            # FT8: 13.5
        cycle_pos = now % slot
        if cycle_pos < wake_pos:
            target_slot_start = now - cycle_pos          # selber Slot
        else:
            target_slot_start = now - cycle_pos + slot   # naechster Slot
        wait = target_slot_start + wake_pos - now
        time.sleep(wait)
        # ... _decode_busy-Lock ...
        # ... chunks holen ...
        threading.Thread(
            target=self._process_cycle,
            args=(chunks, target_slot_start, slot),
            daemon=True,
        ).start()
```

**1b. `_process_cycle` Signatur (decoder.py:178)**:
```python
def _process_cycle(self, chunks, target_slot_start: float, slot: float):
```

**1c. Slot-Felder auf jede Message setzen** (decoder.py:237 vor
`cycle_decoded.emit`):
```python
tx_even = int(target_slot_start / slot) % 2 == 0
for m in messages:
    m._slot_start_ts = target_slot_start
    m._tx_even = tx_even
if messages:
    self.cycle_decoded.emit(messages)
    for msg in messages:
        ...
        self.message_decoded.emit(msg)
    self.cycle_finished.emit()
else:
    self.cycle_decoded.emit([])
    self.cycle_finished.emit()
```

**1d. `[RX]`-Diagnose-Print (decoder.py:244-248)** — auch auf
`target_slot_start` umstellen statt `time.time()` (Konsistenz, klein).

### 2. `ui/mw_cycle.py` — `_assign_slot_parity` aufraeumen

```python
def _assign_slot_parity(self, messages):
    """Slot-Parity respektieren — Decoder hat sie schon gesetzt.

    Fallback nur fuer Test-Mocks ohne echten Decoder.
    """
    if not messages:
        return
    fallback_even = self.timer.is_even_cycle()
    fallback_now = ntp_time.get_time()
    slot = self.timer.cycle_duration
    fallback_slot_start = int(fallback_now / slot) * slot
    for m in messages:
        if not hasattr(m, '_tx_even'):
            m._tx_even = fallback_even
        if not hasattr(m, '_slot_start_ts'):
            m._slot_start_ts = fallback_slot_start
```

**FT2-Migration:** `_slot_from_utc(utc)`-Spezialfall faellt weg —
Decoder liefert `target_slot_start` korrekt fuer alle Modi (FT2 mit
slot=3.8 nutzt dieselbe pre-sleep-Logik). Test deckt das ab (siehe
unten).

### 3. `ui/qso_panel.py` — `add_rx`/`add_tx` Parameter

```python
def add_rx(self, message: str,
           tx_even: bool | None = None,
           slot_start_ts: float | None = None):
    """Empfangene Antwort anzeigen."""
    self._cq_count = 0
    if slot_start_ts is None or tx_even is None:
        # Fallback fuer Test-Mocks und alte Caller
        now = time.time()
        slot = getattr(self, '_cycle_duration', 15.0)
        slot_start_ts = now - (now % slot)
        tx_even = int(slot_start_ts / slot) % 2 == 0
    utc = time.strftime("%H:%M:%S", time.gmtime(slot_start_ts))
    tag = "[E]" if tx_even else "[O]"
    self._append_colored(f"{utc} {tag} ←  Empf.   {message}", "#44BBFF")
```

`add_tx` analog mit denselben Parametern. `_slot_tag()` bleibt als
Privat-Helper im Fallback-Pfad.

### 4. `core/encoder.py` — `tx_started` mit Slot-Info

**Signal-Signatur erweitern (encoder.py:42):**
```python
tx_started = Signal(str, bool, float)  # message, tx_even, slot_start_ts
```

**Aufruf (encoder.py:275):**
```python
tx_now = time.time()
slot = self._cycle_duration   # vom Encoder bekannt
slot_start_ts = int(tx_now / slot) * slot
tx_even = int(slot_start_ts / slot) % 2 == 0
self.tx_started.emit(message, tx_even, slot_start_ts)
```

**⚠️ R1-Pflicht vor Commit 5: Komplette Listener-Migration.** Vor dem
Commit:
```bash
grep -rn "tx_started\.connect" --include="*.py"
grep -rn "tx_started\.emit" --include="*.py"   # Selbsttest
```
Alle gefundenen Listener mussen mit-migriert werden (neue Signatur).
R1-Empfehlung explizit aufgenommen.

**Caller `mw_qso.py:59`:**
```python
self.qso_panel.add_tx(message, ant_label, tx_even=tx_even,
                      slot_start_ts=slot_start_ts)
```

### 5. `ui/mw_cycle.py:762` — Caller `add_rx` anpassen

```python
if msg.target == self.settings.callsign:
    self.qso_panel.add_rx(
        msg.raw,
        tx_even=msg._tx_even,
        slot_start_ts=msg._slot_start_ts,
    )
```

---

## Konsumenten-Liste `_tx_even` (R1-validiert)

| Datei:Zeile | Was | Risiko nach Fix |
|---|---|---|
| `core/auto_hunt.py:232,240,249,271` | Slot-Affinitaet, `_last_tx_even` | **Korrigiert** (R1: kein Inversion-Schutz) |
| `core/qso_state.py:100` | `tx_slot_for_partner`-Signal | Encoder Gegentakt → korrekt |
| `ui/mw_cycle.py:512` | `encoder.tx_even = not _candidate.tx_even` | **Korrigiert** durch Fix |
| `ui/mw_qso.py:85,87,423,425` | TX-Slot-Trigger | **Korrigiert** durch Fix |
| `ui/mw_qso.py:128` | CQ-Start: `not is_even_cycle()` | **Unveraendert** — User-Klick-Pfad, kein Latenz-Issue |
| `ui/rx_panel.py:412` | RX-Tabelle | Pruefen (AC-7) |
| `tests/test_modules.py:343` | Mock | Test-Setup OK |
| `tests/test_auto_hunt_extended.py` | Mocks `_tx_even=True/False` | Test-Setup OK |

---

## Tests

### Neue Tests `tests/test_slot_display.py` (5 Stueck)

1. `test_add_rx_uses_provided_slot` — explizite Slot-Parameter werden
   verwendet
2. `test_add_rx_fallback_when_no_slot_info` — alter Pfad funktioniert
3. `test_add_tx_uses_provided_slot` — analog
4. `test_assign_slot_parity_respects_decoder` — Decoder-Werte werden
   nicht ueberschrieben
5. `test_assign_slot_parity_fallback` — Fallback bei fehlenden Feldern

### Neue Tests `tests/test_decoder_slot_source.py` (3 Stueck)

6. `test_target_slot_start_pre_sleep_no_drift` — Sleep-Drift kann
   `target_slot_start` nicht verfaelschen
7. `test_target_slot_start_modes` — FT8/FT4/FT2 mit verschiedenen
   `now`-Werten
8. `test_messages_get_slot_attributes` — Decoder setzt `_slot_start_ts`
   und `_tx_even` auf jede Message

### Auto-Hunt-Regressions-Test

9. `test_auto_hunt_with_corrected_tx_even` (in
   `tests/test_auto_hunt_extended.py`) — Slot-Affinitaet weiterhin
   korrekt

### R1-Empfehlung 1: Encoder-Signal-Migration-Test

10. `test_tx_started_emits_with_slot_info` (in
    `tests/test_encoder_slot.py` NEU) — `Encoder.tx_started`-Signal
    emittiert (str, bool, float). Listener (mocked) erhaelt alle drei
    Werte.

### R1-Empfehlung 2: FT2-Konsistenz-Test

11. `test_ft2_slot_from_decoder` (in `tests/test_decoder_slot_source.py`)
    — FT2 (slot=3.8) bekommt `_slot_start_ts`/`_tx_even` korrekt
    gesetzt, ohne `_slot_from_utc`-Fallback.

**Total:** 11 neue Tests. Erwartet: 742 → 753 gruen.

---

## Risiken (R1-validiert)

1. **Auto-Hunt-Regression** — R1 sagt: gering. Aktuell sendet Auto-Hunt
   bei skipped Slots im falschen Slot (kein Inversion-Schutz). Fix
   korrigiert das. Validierung durch Test 9 + Field-Test.

2. **`tx_started`-Signal-Signatur-Aenderung** — Drei-Tupel statt
   ein-Tupel. **Vor Commit 5: grep tx_started.connect**, alle Listener
   migrieren. R1-Empfehlung.

3. **FT2-Pfad** — `_slot_from_utc`-Fallback weg. Test 11 deckt das ab.

4. **station_stats Stunden-Datei** — < 0.1 % Bias, NICHT Teil dieses
   Fixes (separates TODO falls je relevant).

5. **Backward-Compat** — Default `None` + Fallback-Pfad sicherstellen
   (Tests 2 + 5).

6. **rx_panel `_tx_even`-Lese (AC-7)** — pruefen ob visuelle Anzeige
   sich aendert oder gleich bleibt.

---

## Akzeptanzkriterien

- **AC-1 Field-Test:** RX-Eintraege mit ODD-Tag fuer Gegenstation,
  EVEN-Tag fuer eigene TX. Mike's Sequenz von 03:38-:40 mit DA1TST
  zeigt erwartete Slot-Sequenz aus `qso_panel_slot_display_v2.md`.
- **AC-2** RX-Zeitstempel = Slot-Start des TX-Slots
  (`03:38:15 [O]` statt `03:38:30 [E]`).
- **AC-3** Auto-Hunt funktioniert weiter (Field-Test + Tests gruen).
- **AC-4** Alle bestehenden Tests gruen (742 → 753).
- **AC-5** 11 neue Tests bestehen.
- **AC-6** FT4 + FT2 Smoke-Test (Tests, da Mike FT8 funkt).
- **AC-7** `rx_panel.py:412`-Verbraucher: visuell unveraendert oder
  bewusst angepasst.

---

## Atomare Commits (7 Stueck)

1. **`feat(decoder): target_slot_start pre-sleep + Thread-Arg`**
   (decoder.py:132-167 + `_process_cycle` Signatur)
2. **`feat(decoder): _slot_start_ts/_tx_even auf Messages setzen`**
   (decoder.py:237-256)
3. **`refactor(mw_cycle): _assign_slot_parity respektiert Decoder`**
   (mw_cycle.py:135-152)
4. **`feat(qso_panel): add_rx/add_tx mit slot_start_ts/tx_even`**
   (qso_panel.py:153-177)
5. **`feat(encoder): tx_started mit slot_start_ts/tx_even`**
   ⚠️ Vor Commit: `grep -rn "tx_started\.connect" --include="*.py"`,
   alle Listener mit-migrieren
   (encoder.py:42,275 + alle Listener)
6. **`refactor(mw_cycle): Caller add_rx mit Message-Feldern`**
   (mw_cycle.py:762)
7. **`test(slot): 11 neue Tests`** (test_slot_display.py +
   test_decoder_slot_source.py + test_auto_hunt_extended.py +
   test_encoder_slot.py)

---

## Workflow-Stand

- ✅ V1: `qso_panel_slot_fix_plan_v1.md`
- ✅ V2: `qso_panel_slot_fix_plan_v2.md` (Self-Review, 10 Findings)
- ✅ R1: `qso_panel_slot_fix_plan_r1.md` (durchgehend positiv,
  2 Zusatz-Empfehlungen)
- ✅ R1-Validierung: keine Halluzinationen, eine V3-Anmerkung
  (`mw_qso.py:128` ist nicht betroffen)
- ✅ V3: dieses Dokument
- ⏳ **Mike-Freigabe** ← hier
- ⏳ Plan-Mode + 7 Commits
- ⏳ Field-Test
- ⏳ HISTORY.md/HANDOFF.md/CLAUDE.md/Memory-Update
