# P41 — audio_streaming-Flag fuer OMNI-CQ Antennen-Switch-Bug (DeepSeek-R1)

## Auftrag

V2 fuer einen TX-Pfad-Bugfix in SimpleFT8 (FT8-Hobby-Tool, FlexRadio).
Pruefe auf:
1. Threading-Sicherheit (TX-Thread, GUI-Thread, Decoder-Thread)
2. Race-Conditions zwischen Flag-Setzung und Antennen-Switch
3. Edge-Cases (abort, replace, encoding-error)
4. TX-Pfad-Risiken (CLAUDE.md: TX-Pfad-Aenderungen sind Backup-pflichtig)
5. Test-Coverage

Kurze Antwort. KP-Findings KRITISCH/SOLLTE/KOENNTE/OK.

---

## Bug live-verifiziert (Mike Field-Test 12.05.2026 morgens)

OMNI-CQ aktiv (sendet alle 30s Even-Parity), Adaptive Diversity aktiv,
Ratio 30:70 (A2 dominant). Erwartung: Antennen-Pattern wechselt
slot-fuer-slot A1:A2 = 1:2 wie in `core/diversity.py:83 _PAT_70_A2`.

**Beobachtung:** Hardware-Antenne wechselt **5 Minuten lang nicht**.
Debug-Log:
```
05:45:14 [ANT] SWITCH cmd=ANT2 OK   ← letzter Switch vor OMNI-Start
05:45:29 [ANT] SKIP — encoder.is_transmitting
05:45:44 [ANT] SKIP — encoder.is_transmitting
05:45:59 [ANT] SKIP — encoder.is_transmitting
... 20× SKIP in Folge alle 15s ...
05:50:29 [ANT] SWITCH cmd=ANT1 OK
```

Adaptive-Buffer fuellt sich einseitig (`record_slot ant=A1` 10 Mal in Folge),
Mike's Label zeigt nur "RX Ant1" obwohl Hardware noch auf ANT2 ist.

## Root-Cause-Analyse

`ui/mw_cycle.py:678-680`:
```python
if self.encoder.is_transmitting:
    _dlog("ANT", "SKIP — encoder.is_transmitting")
    return  # ← komplett raus, kein choose(), kein Switch
```

`core/encoder.py` Zeitleiste:
- Z.216 `_is_transmitting = True` (Start `_tx_worker`)
- Z.270 `audio_12k = self.encode_message(...)` (Encoding ~50ms)
- Z.282 `next_boundary = self._next_slot_boundary()`
- Z.288 `self._abort_event.wait(timeout=sleep_dur)` (Sleep ggf. mehrere Sekunden)
- Z.358 `self._radio.ptt_on()`
- Z.372 `self._radio.send_audio(audio_full, ...)` (BLOCKING ~13.5s)
- Z.376 `self._radio.ptt_off()`
- Z.378 `self.tx_finished.emit()`
- Z.226 finally `_is_transmitting = False`

`_is_transmitting` ist also True von Worker-Start bis Worker-Ende
inkl. Sleep-Phase und Encoding-Setup. Bei OMNI-CQ startet alle 30s
ein neuer TX-Worker — die Phase zwischen Worker-End (`finally`) und
naechstem Worker-Start ist offenbar so kurz (sub-second) dass jeder
`_on_cycle_start` (alle 15s) im "True"-Fenster trifft.

## V2-Fix: feinerer `_audio_streaming`-Flag

Neuer Flag der **nur True ist waehrend send_audio() blockierend Audio
streamt** (die echten 13.5s, nicht waehrend Sleep/Setup).

### Aenderungen

**`core/encoder.py`:**
```python
# __init__:
self._audio_streaming = False

# Property:
@property
def is_audio_streaming(self) -> bool:
    """True NUR waehrend send_audio() blockierend Audio rausstreamt.

    Feiner als is_transmitting (das auch waehrend Sleep/Setup True ist).
    Nutzung: Antennen-Switch in mw_cycle.py — verhindert Block durch
    den Slot-Setup-Teil des Workers, erlaubt aber Schutz waehrend
    tatsaechlich Audio fliesst.
    """
    return self._audio_streaming

# In _tx_worker_inner direkt um send_audio:
if self._radio:
    self._radio.set_tx_antenna("ANT1")
    self._radio.ptt_on()

# Slot-Quelle-Berechnung + emit tx_started ...

if self._radio:
    self._audio_streaming = True
    try:
        self._radio.send_audio(audio_full, sample_rate=SAMPLE_RATE_FT8)
    finally:
        self._audio_streaming = False

if self._radio:
    self._radio.ptt_off()

self.tx_finished.emit()

# _tx_worker finally (Safety-Net):
try:
    self._tx_worker_inner(message)
finally:
    self._is_transmitting = False
    self._audio_started = False
    self._audio_streaming = False  # Safety: bei Exception im send_audio

# abort():
def abort(self):
    self._is_transmitting = False
    self._audio_streaming = False  # NEU
    self._abort_event.set()
```

**`ui/mw_cycle.py:678`:**
```python
# Vorher:
if self.encoder.is_transmitting:
    return

# Nachher:
if self.encoder.is_audio_streaming:
    return
```

## Akzeptanzkriterien

- AK1: OMNI-CQ aktiv + Adaptive 30:70 → Antennen-Pattern wechselt
  slot-fuer-slot wie `_PAT_70_A2` definiert (live-pruefbar im Log)
- AK2: Adaptive-Buffer fuellt sich mit BEIDEN Antennen (`record_slot`
  zeigt sowohl A1 als auch A2)
- AK3: Mike's Label „● DYNAMISCH (live) — RX Ant1/Ant2" wechselt
  zwischen Slots
- AK4: Waehrend Audio aktiv rausgeht (send_audio blockierend) wird
  KEIN Antennen-Switch gemacht (Schutz bleibt)
- AK5: Bei `abort()` oder Exception → `is_audio_streaming=False`
- AK6: 1140 bestehende Tests bleiben gruen
- AK7: Neue Tests fuer den Flag (Init=False, beim send_audio=True,
  nach send_audio=False, abort=False)

## V2-Self-Review

1. **Threading**: `_audio_streaming` Schreiber = TX-Worker-Thread.
   Leser = GUI-Thread (mw_cycle._on_cycle_start). String/bool atomic
   in CPython (GIL). Race-Fenster zwischen `send_audio`-Return und
   `_audio_streaming=False` ist <1ms — irrelevant fuer 50ms-Antennen-Switch.
2. **Backwards-Compat**: `is_transmitting` bleibt unveraendert.
   Andere Aufrufer (z.B. `mw_qso.py` Replace-Logik) sehen weiter
   das alte Verhalten. Kein API-Bruch.
3. **Edge: Encoding-Error** (Z.275 `tx_finished.emit()` ohne Audio-Send)
   → `_audio_streaming` wurde nie auf True gesetzt → bleibt False ✓.
4. **Edge: Replace**: `request_replace` setzt `_replace_message`,
   `_abort_event.set()`. Worker wacht auf, re-encoded, loopt. Bis dann
   Audio-Send startet ist `_audio_streaming=False`. Antennen-Switch
   waehrend Replace-Wait moeglich. OK.
5. **Edge: Abort waehrend send_audio**: send_audio ist blocking. abort()
   setzt `_audio_streaming=False`. Aber send_audio blockiert weiter
   bis zur naechsten Audio-Paket-Lieferung. Antennen-Switch koennte
   dann gleich passieren waehrend Audio noch raus geht — POTENZIELLES
   PROBLEM. → Mitigation: `_audio_streaming=False` in abort() ist
   nur Defensive; faktisch wird Audio sowieso beendet vom Hardware-PTT-off.
   Akzeptabel weil abort selten + Notfall.
6. **TX-Pfad-Risiken (CLAUDE.md)**: Backup wurde angelegt
   (`Appsicherungen/2026-05-12_v0.97.6_vor_p41_omni_antenna_fix/`).

## Frage an R1

1. Stimmt mein Threading-Argument (CPython GIL, atomic bool R/W)?
2. Edge 5 (Abort waehrend send_audio): ist die Mitigation akzeptabel
   oder muss ich anders absichern (z.B. Lock)?
3. Test-Strategie: kann ich `send_audio` mocken um den Flag-Toggle
   zu verifizieren, ohne tatsaechliche Hardware?
4. Bessere Alternative die ich nicht sehe?
5. Sollte `is_audio_streaming` auch in `mw_qso.py` Replace-Logik
   genutzt werden (Replace nur erlaubt vor Audio-Send)?
