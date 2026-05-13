# V2 — Implementierungs-Plan: QSO-Panel Slot-Tag/Zeit-Fix

(V1: `qso_panel_slot_fix_plan_v1.md` — V2 ist kompletter Re-Take nach
Self-Review als frische KI. 10 Findings adressiert, siehe Abschnitt
„Self-Review-Findings" am Ende.)

## Auftrag an R1

Du bekommst diesen V2-Plan mit dem Code. Bitte pruefe:
1. Architektur-Entscheidung (Decoder = Slot-Quelle) — robust und KISS,
   oder Overengineering?
2. Wake-Drift-Behandlung — ist `target_slot_start` pre-sleep berechnet
   wirklich schluessig, oder uebersehe ich einen Edge-Case?
3. Auto-Hunt-Regressions-Risiko — nutzt `_tx_even` aktuell den falschen
   Wert und kompensiert durch Inversion? Wenn ja, was passiert beim Fix?
4. Sind die 6 atomaren Commits sinnvoll geschnitten?
5. Welche Tests fehlen? Welche AC-Punkte sind nicht testbar?

## Vorlage / Input

- Diagnose: `prompts/qso_panel_slot_display_v2.md` + R1-Antwort
  `prompts/qso_panel_slot_display_r1.md` (Option A)
- Log-Beweis: `~/.simpleft8/simpleft8.log` `Zu wenig Audio: X < 90000` →
  Decoder skipt initialen Slot, decodiert im Folge-Slot → `time.time()`
  zur Decode-Zeit ist 1 Slot zu spaet
- Code-Verifikation: `core/timing.py:57-58` `is_even_cycle()` nutzt
  `int(utc_now() / cycle_duration) % 2` — gleiche Latenz-Falle wie
  `qso_panel._slot_tag()`
- `core/station_stats.py:113-117` `log_cycle` bildet die Stunde aus
  `time.strftime` zur Aufrufzeit — gleiche potentielle Falle, aber
  R1-bewertet < 0.1 % Bias und symmetrisch, **nicht Teil dieses Fixes**

## Architektur-Entscheidung

**Decoder ist die einzige sichere Slot-Quelle.** Im Decoder-Loop
(`core/decoder.py:132-145`) wird der Wake-Zeitpunkt gezielt gewaehlt;
dort ist die Information „zu welchem TX-Slot gehoert das Audio im
Buffer" verlustfrei verfuegbar.

**Loesung:** Decoder berechnet **vor** `time.sleep(wait)` einen
`target_slot_start` (UTC-Sekunden). Dieser Wert wandert ueber den
`_process_cycle`-Thread bis zu jeder dekodierten Message als Attribut
`_slot_start_ts: float` und `_tx_even: bool`. Alle Konsumenten lesen
diese Attribute statt eigener `time.time()`-basierter Berechnungen.

**Warum pre-sleep berechnen** (Self-Review-Finding 1): `wake_time =
time.time()` post-sleep liegt mit Sleep-Drift gelegentlich Mikrosekunden
hinter der Slot-Boundary. `floor(wake_time / slot) * slot` waere dann
um einen ganzen Slot daneben. Pre-sleep haben wir den intendierten
Slot exakt, ohne Drift-Risiko.

## Konkrete Aenderungen

### 1. `core/decoder.py` — Slot-Quelle berechnen + durchreichen

**1a. `_tick_loop` (decoder.py:132-167)** — `target_slot_start`
pre-sleep berechnen:

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
            args=(chunks, target_slot_start, slot),  # <-- neu
            daemon=True,
        ).start()
```

**1b. `_process_cycle` Signatur (decoder.py:178)** — Signatur erweitern:

```python
def _process_cycle(self, chunks, target_slot_start: float, slot: float):
    """Preprocessing + Decode in eigenem Thread."""
    ...
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
`target_slot_start` umstellen statt `time.time()`. Klein, aber
konsistent.

### 2. `ui/mw_cycle.py` — `_assign_slot_parity` aufraeumen

**Stelle:** `_assign_slot_parity` (mw_cycle.py:135-152).

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

**Migration FT2** (Self-Review-Finding 6): Der bisherige FT2-Spezialfall
(`_slot_from_utc(utc)`) faellt weg, weil der Decoder fuer alle Modi den
`target_slot_start` setzt. R1 muss bestaetigen dass das aequivalent ist.
Argumentation: Fuer FT2 wird `slot=3.8` korrekt verwendet; Wake-Logik
funktioniert identisch.

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

**`add_tx` analog mit denselben Parametern.** Self-Review-Finding 5:
`tx_started` (encoder.py:275) wird AM TX-START gefeuert — `time.time()`
ist meistens im richtigen Slot, aber bei Encoder-Setup-Latenz koennte
es ueberlaufen. Konsistenz herstellen indem Encoder `slot_start_ts` mit
emittiert.

**`_slot_tag()` (qso_panel.py:147-151)** — als Privat-Helper bleibt er
fuer den Fallback in `add_tx`/`add_rx`. Self-Review-Finding 9: nicht
geloescht, aber nicht mehr extern referenziert.

### 4. `core/encoder.py` — `tx_started` mit Slot-Info

**Self-Review-Finding 5 (vertieft):** Damit `add_tx` einen sicheren
Slot-Wert bekommt, sollte `tx_started` zwei Werte mitliefern.

```python
# encoder.py — Signal-Definition (Zeile 42)
tx_started = Signal(str, bool, float)  # message, tx_even, slot_start_ts
```

**Aufruf** (decoder.py:275):
```python
tx_now = time.time()
slot = self._cycle_duration   # vom Encoder bekannt? Pruefen!
slot_start_ts = int(tx_now / slot) * slot
tx_even = int(slot_start_ts / slot) % 2 == 0
self.tx_started.emit(message, tx_even, slot_start_ts)
```

**Caller `mw_qso.py:59`:**
```python
self.qso_panel.add_tx(message, ant_label, tx_even=tx_even,
                      slot_start_ts=slot_start_ts)
```

→ R1 muss pruefen ob `tx_started`-Listener-Liste komplett umgestellt
wird (Backward-Compat mit Slots, die nur `(str)` erwarten).

### 5. `ui/mw_cycle.py:762` — Caller anpassen

```python
if msg.target == self.settings.callsign:
    self.qso_panel.add_rx(
        msg.raw,
        tx_even=msg._tx_even,
        slot_start_ts=msg._slot_start_ts,
    )
```

### 6. Konsumenten-Liste `_tx_even` (Self-Review-Finding 2)

Diese Stellen lesen `_tx_even`. Nach dem Fix ist `_tx_even` der **echte
TX-Slot-Wert** (nicht mehr potentiell `not actual_tx_even` wegen Latenz).

| Datei:Zeile | Was | Risiko |
|---|---|---|
| `core/auto_hunt.py:95,132,162,232` | Slot-Affinitaet | **Hoch — siehe AC-3** |
| `core/qso_state.py:100` | `tx_slot_for_partner`-Signal | Encoder Gegentakt |
| `ui/mw_qso.py:85,423` | TX-Slot-Trigger | TX-Pacing |
| `ui/rx_panel.py:412` | RX-Tabelle (Slot-Spalte?) | Visuell |
| `tests/test_modules.py:343` | Mock | Test-Setup |
| `tests/test_auto_hunt_extended.py` | Auto-Hunt-Tests | Test-Logik |

**Kritischste Frage** (R1 muss klaeren): Hat das aktuelle System mit
dem Latenz-bedingt FALSCHEN `_tx_even` gearbeitet, und wurde das durch
implizite Inversion in Auto-Hunt kompensiert? Wenn ja, wuerde der Fix
die Slot-Affinitaet umkehren und Auto-Hunt brechen.

**Vorgehen:** Vor jedem atomaren Commit der Auto-Hunt beruehrt: kompletter
`pytest tests/test_auto_hunt*` Lauf + Mike-Field-Test mit Auto-Hunt.

## Tests

### Neue Tests `tests/test_slot_display.py` (5 Stueck)

1. **`test_add_rx_uses_provided_slot`** — `add_rx("DA1MHH X 73",
   tx_even=False, slot_start_ts=1730000115)` schreibt `[O]` und Zeit
   die zu :15-Slot passt, unabhaengig von `time.time()`.
2. **`test_add_rx_fallback_when_no_slot_info`** — alter Caller-Pfad
   funktioniert weiter (keine Regression).
3. **`test_add_tx_uses_provided_slot`** — analog zu `add_rx`.
4. **`test_assign_slot_parity_respects_decoder`** — Message mit
   `_tx_even=False` bekommt diese Werte nicht ueberschrieben.
5. **`test_assign_slot_parity_fallback`** — Message ohne Felder
   bekommt Werte aus Timer-Fallback.

### Neue Tests `tests/test_decoder_slot_source.py` (3 Stueck)

6. **`test_target_slot_start_pre_sleep_no_drift`** — Mock `time.time()`
   und `time.sleep`, verifiziere dass `target_slot_start` floor(now/slot)
   gleich bleibt auch wenn `wait + 0.05s` post-sleep ueber Slot-Grenze
   rutscht.
7. **`test_target_slot_start_modes`** — FT8/FT4/FT2 mit jeweils 3
   verschiedenen `now`-Werten (Slot-Anfang, Mitte, kurz vor Wake).
8. **`test_messages_get_slot_attributes`** — Decoder-Mock mit kuenstlichen
   Messages, pruefe dass `m._slot_start_ts` und `m._tx_even` gesetzt
   sind nach `_process_cycle`.

### Auto-Hunt-Regressions-Tests (Self-Review-Finding 2)

9. **`test_auto_hunt_with_corrected_tx_even`** (NEU in
   `tests/test_auto_hunt_extended.py`) — sicherstellen dass
   Slot-Affinitaet weiterhin korrekt arbeitet wenn `_tx_even` jetzt
   den ECHTEN TX-Slot widerspiegelt.

### Bestehende Tests pruefen

- `test_modules.py:343` (`self._tx_even = True`) — Mock weiter ok
- `test_decoder_*` — Signatur-Anpassungen `_process_cycle(chunks,
  target_slot_start, slot)`
- `test_patterns.py:317` `test_omni_tx_even_odd_alternation` — pruefen
  ob OMNI-TX-Logik betroffen

**Total:** 5 + 3 + 1 = **9 neue Tests**, +0 Regressions erwartet
(742 → 751).

## Risiken

1. **Auto-Hunt-Regression (R1.5):** `_tx_even` wird jetzt korrekt — wenn
   bestehender Code mit invertiertem Wert kompensierte, bricht Auto-Hunt.
   Mitigation: Auto-Hunt-Tests gruen + Field-Test mit Auto-Hunt vor
   Release.

2. **`tx_started`-Signal-Signatur-Aenderung:** Drei-Tupel statt
   ein-Tupel. Alle Slots in Code mussen mit-migriert werden. R1 muss
   alle Listener finden.

3. **FT2-Pfad:** `_slot_from_utc(utc)` faellt weg. R1 muss bestaetigen
   dass `target_slot_start` aus Wake-Logik fuer FT2 (3.8s) aequivalent
   ist. Mike funkt praktisch FT8, aber Tests muessen FT2 abdecken.

4. **station_stats Stunden-Datei:** R1-Risikobewertung < 0.1 % Bias.
   **NICHT Teil dieses Fixes** — separates TODO falls je relevant.
   Self-Review-Finding 4 dokumentiert.

5. **Backward-Compat:** Alle `add_rx`/`add_tx`-Caller mit nur
   `(message)` mussen weiterhin laufen. Default `None` + Fallback-Pfad
   sicherstellen.

6. **rx_panel `_tx_even`-Lese:** rx_panel.py:412 liest `_tx_even` —
   wenn das fuer eine Slot-Spalte oder Highlighting verwendet wird,
   sollte sich die Anzeige aendern (R1: pruefen).

## Akzeptanzkriterien

- **AC-1 Field-Test:** RX-Eintraege im QSO-Panel zeigen ODD-Tag fuer
  Nachrichten der Gegenstation, EVEN-Tag fuer eigene TX (Mike's
  Sequenz von 03:38-:40 mit DA1TST: erwartete Slot-Sequenz aus
  `qso_panel_slot_display_v2.md`).
- **AC-2 RX-Zeitstempel** = Slot-Start des TX-Slots der Nachricht
  (`03:38:15 [O]` statt `03:38:30 [E]`).
- **AC-3 Auto-Hunt funktioniert weiter** (Field-Test + Tests gruen).
- **AC-4 Alle bestehenden Tests gruen** (742 → 751).
- **AC-5 9 neue Tests** (siehe Test-Plan).
- **AC-6 FT4 + FT2 Smoke-Test** (Tests nicht Field, da Mike FT8 funkt).
- **AC-7 rx_panel-Visualisierung** unveraendert oder bewusst geandert
  (R1-Empfehlung).

## Atomare Commits (Self-Review-Finding 9)

Plan-Mode → 6 atomare Commits:

1. **`feat(decoder): target_slot_start pre-sleep + Thread-Arg`**
   (decoder.py:132-167 + `_process_cycle` Signatur)
2. **`feat(decoder): _slot_start_ts/_tx_even auf Messages setzen`**
   (decoder.py:237-256)
3. **`refactor(mw_cycle): _assign_slot_parity respektiert Decoder`**
   (mw_cycle.py:135-152)
4. **`feat(qso_panel): add_rx/add_tx mit slot_start_ts/tx_even`**
   (qso_panel.py:153-177)
5. **`feat(encoder): tx_started mit slot_start_ts/tx_even`**
   (encoder.py:42,275 + mw_qso.py:59)
6. **`refactor(mw_cycle): Caller add_rx mit Message-Feldern`**
   (mw_cycle.py:762)
7. **`test(slot): 9 neue Tests`** (test_slot_display.py +
   test_decoder_slot_source.py + test_auto_hunt_extended.py)

→ 7 Commits (Self-Review zeigt: lieber +1 dedizierter Test-Commit).

## Workflow-Stand

- V1: `qso_panel_slot_fix_plan_v1.md`
- V2: dieses Dokument
- R1: V2 an DeepSeek-R1 schicken
- R1-Validierung: kritisch lesen, Halluzinationen filtern
- V3: finaler Plan → Mike-Freigabe → Plan-Mode → 7 Commits

## Self-Review-Findings (V1 → V2)

1. **Wake-Drift:** `wake_time = time.time()` post-sleep ist
   driftanfaellig → V2 nutzt **pre-sleep `target_slot_start`**.
2. **Konsumenten-Liste `_tx_even`:** V1 hatte unklare Liste → V2 hat
   konkrete Tabelle mit Datei:Zeile + Risikobewertung.
3. **`tx_started`-Signal:** V1 hat das uebersehen → V2 erweitert
   Signal-Signatur, dokumentiert Migrationsbedarf.
4. **station_stats:** V1 hatte unklare Stats-Frage → V2 stellt klar:
   nicht Teil dieses Fixes, separates TODO falls je relevant.
5. **`_slot_tag()`:** V1 liess offen → V2 sagt: Privat-Helper, bleibt
   fuer Fallback, kein extern-Schaden.
6. **FT2-Migration:** V1 erwaehnt nur, V2 stellt explizite Frage an R1.
7. **Test-Anzahl:** V1 hatte 4 Tests → V2 hat 9 (mit Auto-Hunt-Regression
   + Decoder-Slot-Source-Tests).
8. **Auto-Hunt-Regressions-Risiko:** V1 nur kurz erwaehnt → V2 hat
   eigenen Risikopunkt + Test + Field-Test-Pflicht.
9. **Atomare Commits:** V1 hatte keine Aufteilung → V2 hat konkrete
   7-Commit-Liste.
10. **rx_panel.py:412:** V1 uebersah dass auch RX-Tabelle `_tx_even`
    liest → V2 hat AC-7 dafuer.
