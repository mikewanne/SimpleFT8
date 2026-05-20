# P94 — Quick-73-Ignore (V2 nach Self-Review)

Du bist Senior Python-Entwickler spezialisiert auf Amateurfunk-FT8-Software
und QSO-State-Machines. Hobby-Funker-Tool, kein Contest. WSJT-X-Konventionen
sind Referenz.

## Problem (Mike-Field-Test 20.05.2026 v0.97.65)

Gegen-Station (9A4AA) hat unser RR73/73 nicht bekommen und ruft uns 4 min
nach abgeschlossenem QSO erneut mit Report → App startet komplettes neues
QSO via `qso_sm.on_message_received` → 5 Slots Report-Austausch (statt
1 Slot 73) → ADIF-Dedup (300s) verhindert nur den Logbuch-Eintrag, NICHT
den Funkverkehr.

## Mike-Spec (verbindlich)

Wenn dieselbe Station auf demselben Band **innerhalb 30 Minuten** nach
abgeschlossenem QSO erneut Report/Grid sendet:
1. **Einmal sauberes `<their_call> <my_call> 73`** senden (höflich)
2. **Diesen Call für 30 Min komplett ignorieren** (auch keine weitere
   73-Antwort wenn er nochmal ruft) — sonst Endlos-Loop
3. State-Machine **NICHT** weiterschalten — bleibt IDLE/CQ_WAIT
4. Im Fenster mit `<their_call> <my_call> 73` oder `<their_call> <my_call> RR73`:
   ignorieren (kein Echo)

Außerdem Konsistenz: **Auto-Hunt-Station-Cooldown** (P61, heute 5 Min,
`core/auto_hunt.py:_RECENT_QSO_COOLDOWN_S`) **auf 30 Min hochsetzen**
→ Auto-Hunt picked diese Stationen nicht im selben Fenster.
**Auto-Hunt-Hard-Cap-Timer (10 Min) BLEIBT unverändert** (Bot-Tarn-Schutz).

## Code-Realität (verifiziert 20.05.2026)

**Aufrufstelle `qso_sm.on_message_received` = `ui/mw_cycle.py:803`**

```python
def on_message_decoded(self, msg: FT8Message):
    if not self.rx_panel._rx_active:
        return
    self.control_panel.update_snr(msg.snr)
    self.qso_sm.set_last_snr(msg.snr)

    # Z.765-778: add_rx (mit ant_label) — bleibt für Sichtbarkeit
    if msg.target == self.settings.callsign:
        ant_label = ...
        self.qso_panel.add_rx(msg.raw, tx_even=..., slot_start_ts=..., ant_label=ant_label)

    # Z.785-801: OMNI-Pfad — wenn OMNI aktiv → start_qso + return
    if (self._omni_cq.is_active() and not self._omni_cq.is_paused()
            and msg.target == self.settings.callsign
            and not msg.is_73 and not msg.is_rr73):
        self._pause_omni_if_active()
        their_even = getattr(msg, '_tx_even', None)
        self.encoder.tx_even = (not their_even) if their_even is not None else None
        self.qso_sm.start_qso(their_call=msg.caller, ...)
        return

    self.qso_sm.on_message_received(msg)  # ← Z.803 = der QSO-Trigger
```

**`_recent_logged_calls`** wird in `ui/main_window.py:277` initialisiert
als `dict[tuple[str, str], float]` (Key: `(call.upper(), band.upper())`, Value: ts)
und in `ui/mw_qso.py:541-555` gepflegt — wird beim QSO-Abschluss SOFORT
gefüllt (auch wenn ADIF-Duplikat-Filter greift).

**`FT8Message`-API** (`core/message.py`):
- `msg.caller`, `msg.target`, `msg.freq_hz`
- `msg.is_grid`, `msg.is_report`, `msg.is_73`, `msg.is_rr73`

**`Encoder`-API** (`core/encoder.py:206-235`):
- `encoder.transmit(message, *, tx_even=None, audio_freq_hz=None) → bool`
- `encoder.is_transmitting` (property)
- `encoder.abort()` setzt `_abort_event` + `_is_transmitting=False`
- `encoder.tx_even` Attribut (None / True / False)

## V2 — Korrekturen V1→V2

V1 hatte 12 Annahmen/Halluzinationen die V2 jetzt repariert:

### Korrigiert
1. **Datei-Pfad:** V1 sagt `ui/mw_qso.py` für den Pre-Filter — falsch.
   Die Aufrufstelle ist `ui/mw_cycle.py:803`. → P94-Filter gehört in
   `mw_cycle.py` (als Helper-Methode der QSOMixin via `self`).

2. **Methoden-Name:** V1 nennt `_on_decoder_message` — existiert nicht.
   Echte Methode: `on_message_decoded(self, msg)`.

3. **Filter-Position:** V1 unklar. Korrekt: VOR Z.785 OMNI-Block (sonst
   würde OMNI ein neues QSO via `start_qso` triggern), aber NACH `add_rx`
   (Z.773-778) — damit Mike den Anruf trotzdem im QSO-Panel sieht.

4. **State-Check fehlte:** V1-Skizze prüft NICHT `qso_sm.state`. Wenn
   State = WAIT_REPORT (Mike hat aktives QSO mit anderer Station),
   würde Quick-73 dazwischenfunken. → P94 NUR aktiv wenn State ∈
   {IDLE, CQ_WAIT, CQ_CALLING}. Sonst: Filter `return False`,
   `on_message_received` läuft normal (State-Machine kümmert sich).

5. **Encoder-Abort gefährlich:** V1-Skizze `if encoder.is_transmitting:
   encoder.abort()` würde laufende QSO-Slots abbrechen. Mit State-Check
   aus Punkt 4 ist das kein Problem mehr — IDLE/CQ_WAIT/CQ_CALLING
   senden eh nichts QSO-relevantes. Trotzdem: `is_transmitting`-Check
   wegfallen lassen, statt `encoder.transmit(...)` rufen — das returnt
   `False` wenn TX läuft (KISS, keine Race).

6. **tx_even-Parität fehlte:** V1 ruft `encoder.transmit(tx_msg)` ohne
   `tx_even` — Encoder würde in eigene `self.tx_even` fallen (möglich
   stale). OMNI-Pfad macht es richtig (`tx_even = not their_even`).
   P94 muss das gleiche tun: `tx_even = not msg._tx_even` damit Quick-73
   im richtigen Slot landet (Gegenparität zur anrufenden Station).

7. **audio_freq_hz fehlte:** V1 sagt nichts zur TX-Frequenz. Wenn wir auf
   unserer CQ-Frequenz senden, hört der Anrufer (der auf seiner Frequenz
   horcht) uns nicht. WSJT-X-Praxis: Antwort auf Frequenz des Anrufers
   (`msg.freq_hz`). → `audio_freq_hz=int(msg.freq_hz)`.

8. **`is_73` / `is_rr73` ausgeschlossen:** V1 prüft `if not (msg.is_grid
   or msg.is_report): return False` — das passt schon, weil `is_73` und
   `is_rr73` weder Grid noch Report sind. **V2-Klarstellung:** Bei
   nochmaligem 73/RR73 im Fenster: kein Echo, da Filter nicht greift
   und State IDLE/CQ_WAIT eh nicht reagiert. Verhalten ✓.

9. **Init `_quick73_sent`:** V1 sagt "in QSOMixin __init__". KISS:
   in `ui/main_window.py:__init__` analog `_recent_logged_calls`.
   `self._quick73_sent: set[str] = set()` (call-only, Band-Wechsel
   resettet implizit weil Lookup `_recent_logged_calls[(call, band)]`).

10. **Reset bei Band-Wechsel:** Wenn Mike das Band wechselt, gilt das
    30-Min-Fenster im neuen Band NICHT (anderer Key in `_recent_logged_calls`).
    `_quick73_sent` ist call-only → könnte alte Calls enthalten. KISS:
    in `discard(call)` Pfad räumen (V1 macht das schon — wenn Fenster
    abgelaufen → `discard`). Plus: Bandwechsel-Hook `_quick73_sent.clear()`?
    → KISS verzichten, da call+band-Lookup eh nichts trifft.

11. **Hardware-Sicherheit ANT1:** TX läuft Im Diversity-Modus IMMER über
    ANT1 (verriegelt in FlexRadio-Setup). Quick-73 ist ein normaler TX-
    Encoder-Aufruf — keine zusätzliche `set_tx_antenna("ANT1")` nötig
    (würde auch der OMNI-Pfad nicht machen).

12. **UI-Anzeige:** Mike-Spec: `9A4AA → Sende 73 (bereits gearbeitet
    4 min)`. Via `self.qso_panel.add_info(...)`. Sichtbar im QSO-Panel
    wie andere Info-Zeilen.

### Bewahrt
- 30 Min Fenster ✅
- Auto-Hunt-Station-Cooldown 5→30 Min ✅
- Hard-Cap 10 Min UNCHANGED ✅
- State-Machine UNCHANGED ✅
- Pre-Filter-Architektur (Variante A aus V1-Brainstorm) ✅

## Code-Skizze V2

```python
# ui/main_window.py:__init__ — neu (1 Zeile neben _recent_logged_calls)
self._quick73_sent: set[str] = set()  # P94: Calls denen schon Quick-73 ging

# ui/mw_cycle.py — neue Konstante + Helper + Aufruf
_QUICK73_WINDOW_S = 1800  # 30 Min (P94)


def on_message_decoded(self, msg: FT8Message):
    if not self.rx_panel._rx_active:
        return
    self.control_panel.update_snr(msg.snr)
    self.qso_sm.set_last_snr(msg.snr)

    # add_rx wie bisher
    if msg.target == self.settings.callsign:
        ant_label = ""
        if hasattr(self, '_antenna_pref_label') and msg.caller:
            ant_label = self._antenna_pref_label(msg.caller).lstrip()
        self.qso_panel.add_rx(
            msg.raw, tx_even=getattr(msg, '_tx_even', None),
            slot_start_ts=getattr(msg, '_slot_start_ts', None),
            ant_label=ant_label,
        )

    # P94: Quick-73 für kürzlich gearbeitete Anrufer
    if self._p94_quick73_filter(msg):
        return

    # OMNI-Pfad (unverändert)
    if (self._omni_cq.is_active() and not self._omni_cq.is_paused()
            and msg.target == self.settings.callsign
            and not msg.is_73 and not msg.is_rr73):
        self._pause_omni_if_active()
        their_even = getattr(msg, '_tx_even', None)
        if their_even is not None:
            self.encoder.tx_even = not their_even
        else:
            self.encoder.tx_even = None
        self.qso_sm.start_qso(
            their_call=msg.caller,
            their_grid=msg.grid_or_report if msg.is_grid else "",
            freq_hz=msg.freq_hz,
            their_snr=msg.snr,
        )
        return

    self.qso_sm.on_message_received(msg)


def _p94_quick73_filter(self, msg: FT8Message) -> bool:
    """P94: Bei Anruf einer kürzlich gearbeiteten Station 1x 73 senden,
    danach für 30 Min ignorieren. State-Machine bleibt unangetastet.

    Return True → Anruf konsumiert (kein weiterer Pfad). False → normal.
    """
    # Nur auf direkten Anruf an uns mit Report/Grid reagieren
    if msg.target != self.settings.callsign:
        return False
    if not (msg.is_grid or msg.is_report):
        return False
    # Nur in IDLE/CQ_WAIT/CQ_CALLING (kein aktives QSO unterbrechen)
    if self.qso_sm.state not in (
            QSOState.IDLE, QSOState.CQ_WAIT, QSOState.CQ_CALLING):
        return False

    band = self.settings.band.upper()
    call = msg.caller.upper()
    now = time.time()
    last_time = self._recent_logged_calls.get((call, band), 0.0)
    if now - last_time > _QUICK73_WINDOW_S:
        # Fenster abgelaufen — normale Verarbeitung; Set räumen
        self._quick73_sent.discard(call)
        return False

    # Im Fenster
    if call in self._quick73_sent:
        # Schon Quick-73 geschickt → komplett ignorieren
        return True

    # Einmaliges Quick-73
    their_even = getattr(msg, '_tx_even', None)
    tx_even = (not their_even) if their_even is not None else None
    tx_msg = f"{msg.caller} {self.settings.callsign} 73"
    started = self.encoder.transmit(
        tx_msg,
        tx_even=tx_even,
        audio_freq_hz=int(msg.freq_hz) if msg.freq_hz else None,
    )
    if not started:
        # TX läuft schon → kein Quick-73 jetzt, aber Set NICHT markieren
        # → nächster Slot kann's nochmal versuchen
        return True

    self._quick73_sent.add(call)
    age_min = int((now - last_time) // 60)
    self.qso_panel.add_info(
        f"{msg.caller} → Sende 73 (bereits gearbeitet {age_min} min)")
    return True
```

```python
# core/auto_hunt.py — Konstante hochsetzen
_RECENT_QSO_COOLDOWN_S = 1800  # P94: 5 Min → 30 Min (Konsistenz mit Quick-73)
```

## Tests (`tests/test_p94_quick73.py`)

- **T1:** Caller im 30-Min-Fenster + Report → Filter konsumiert,
  `_quick73_sent` enthält Call, `encoder.transmit` gerufen mit korrektem
  Format `<their> <us> 73`, `qso_panel.add_info` gerufen.
  State-Machine `on_message_received` NICHT gerufen.
- **T2:** Caller NOCHMAL im Fenster (bereits in `_quick73_sent`) →
  Filter konsumiert, kein TX, kein Add_info. State-Machine NICHT gerufen.
- **T3:** Caller > 30 Min seit letztem QSO → normaler Pfad
  (State-Machine GERUFEN), `_quick73_sent` ohne den Call.
- **T4:** Anderer Caller (nicht in `_recent_logged_calls`) → normaler Pfad.
- **T5:** Message NICHT an my_call (`msg.target != callsign`) → Filter
  passt durch.
- **T6:** Message ohne Report/Grid (z.B. nochmal 73 oder RR73) → Filter
  passt durch (nicht das Quick-73-Ziel).
- **T7:** State = WAIT_REPORT (aktives QSO) → Filter passt durch
  (kein Eingriff in laufendes QSO).
- **T8:** Auto-Hunt `_RECENT_QSO_COOLDOWN_S` ist 1800 (Konstanten-Test).
- **T9:** Encoder.transmit returnt False (TX läuft) → Set NICHT markiert
  (nochmal-versuch beim nächsten Slot möglich).

## DeepSeek-R1 Fragen

1. **Filter-Position:** vor OMNI-Pfad → richtig? Es gibt den Edge-Case
   dass OMNI aktiv UND die anrufende Station kürzlich gearbeitet wurde.
   Mit V2-Position: Quick-73 → OMNI bleibt aktiv (wird nicht pausiert).
   Mike-Etikette ✓ (kein neues OMNI-konsumiertes QSO mit alter Station).
   Bestätigung erwünscht.

2. **State-Check `IDLE/CQ_WAIT/CQ_CALLING`:** ausreichend? Übersehe ich
   einen State wo Quick-73 stören könnte? `WAIT_73` State (nach RR73
   gesendet, wartet auf 73)?

3. **`audio_freq_hz=int(msg.freq_hz)`:** wir antworten auf der Frequenz
   des Anrufers — könnte unsere Frequenz für die nächsten Slots
   verlassen? Encoder sticky? Oder reset nach 1 TX?

4. **`_quick73_sent` Lifecycle bei Band-Wechsel:** call-only Set wird
   nicht geleert. Wenn 9A4AA auf 20m gearbeitet, in `_quick73_sent`,
   Mike wechselt 40m, gleicher Call ruft → `_recent_logged_calls`
   greift mit anderem Band-Key nicht → Filter passt durch (State-
   Machine startet normal QSO). Problem? Oder Klarheit?

5. **Encoder-Race:** wenn `encoder.transmit` returnt `False` weil TX
   schon läuft (sehr selten in IDLE/CQ_WAIT, aber theoretisch) → wir
   markieren NICHT `_quick73_sent`. Nächster Anruf-Slot der gleichen
   Station könnte erneut versuchen — geht das in einen Tight-Loop?
   Im selben 15s-Slot kann er aber nicht — Encoder hat dann TX-Lock.
   Erst nächster Slot → kein Tight-Loop. Tradeoff OK?

6. **Tests T7 (`WAIT_REPORT`):** den State setzen wir per `qso_sm.state =
   WAIT_REPORT` — gibt's einen Helper oder geht das direkt?

7. **Final-Check:** missing edge cases? Beispiel: Diversity vs Normal-
   Mode, ANT1-Setup, Hardware-Sicherheit?

## Workflow

V2 → R1 (jetzt) → V3 → Code → Tests → Final-R1 → atomare Commits → Doku.

KISS-Prinzip: minimaler Eingriff, State-Machine unverändert, ~40 LOC neu.
