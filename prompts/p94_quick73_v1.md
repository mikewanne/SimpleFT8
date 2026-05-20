# P94 — Quick-73-Ignore für doppelte Anrufe (V1)

## Mike-Beobachtung 20.05.2026 (v0.97.65, nach P93)

Sequenz vom Screenshot 9A4AA:
- 11:13:30–11:14:30 — QSO komplett (RR73 + 73 + courtesy-73)
- 11:18:30 — 9A4AA ruft wieder mit Report
- App startet vollen Report-Austausch erneut (mw_qso.py:572-580 in
  `on_message_received`) → Pile-Up + Funkzeit-Verschwendung
- ADIF-Duplikat-Filter (`_LOG_DEDUP_WINDOW_S=300s`) greift nur am
  QSO-Ende → verhindert nur den ADIF-Eintrag, NICHT den Funkverkehr

## Mike-Spec

Wenn dieselbe Station auf demselben Band innerhalb **30 Minuten** nach
abgeschlossenem QSO erneut Report sendet:
1. **Einmal sauberes `<their_call> <my_call> 73`** senden
2. **Diesen Call für 30 Min komplett ignorieren** (auch keine weitere
   73-Antwort wenn er nochmal ruft)
3. State-Machine **NICHT** weiterschalten — bleibt IDLE/CQ_WAIT

## DeepSeek-R1-Bewertung (Brainstorm, V4-pro, 20.05.2026)

**Architektur Wahl A (Pre-Filter in `ui/mw_qso.py`)** — KISS, State-
Machine bleibt unverändert. Filter VOR `qso_sm.on_message_received`.

**Zusatz-Empfehlung R1:** Auto-Hunt-Station-Cooldown (P61, heute 5 Min)
auf 30 Min hochsetzen — gleiche Konstante wie P94. Damit pickt
Auto-Hunt diese Stationen gar nicht erst. **Auto-Hunt-Hard-Cap-Timer
(10 Min Laufzeit) BLEIBT unverändert** — Bot-Tarn-Schutz wahren.

## Mike-Klarstellungen aus Brainstorm

- 30 Min Fenster ✅ (R1 bestätigt, JTDX nutzt 10-15 Min)
- Auto-Hunt-Cooldown auf 30 Min ✅ (nicht Hard-Cap-Timer!)
- UI-Text: `9A4AA → Sende 73 (bereits gearbeitet 4 min)` ✅
- Workflow: V1 → V2 → R1 minimaler Eingriff wie P93 ✅

## Code-Skizze (R1-Empfehlung)

```python
# core/qso_state.py — NICHTS ändern
# ui/mw_qso.py — neue Konstante + Filter

_QUICK73_WINDOW_S = 1800  # 30 Min (P94)

# In QSOMixin (__init__ via getattr-Defensive):
# self._quick73_sent = set()  # Calls denen schon Quick-73 ging

@Slot(object)
def _on_decoder_message(self, msg: FT8Message):  # Aufrufstelle finden
    if self._p94_quick73_filter(msg):
        return
    self.qso_sm.on_message_received(msg)

def _p94_quick73_filter(self, msg: FT8Message) -> bool:
    """P94: Bei Anruf einer kürzlich gearbeiteten Station 1x 73 senden,
    danach für 30 Min ignorieren. State-Machine bleibt unangetastet.
    """
    if msg.target != self.settings.callsign:
        return False
    if not (msg.is_grid or msg.is_report):
        return False
    band = self.settings.band.upper()
    call = msg.caller.upper()
    now = time.time()
    last_time = self._recent_logged_calls.get((call, band), 0.0)
    if now - last_time > _QUICK73_WINDOW_S:
        # Fenster abgelaufen → normale Verarbeitung, Ignore-Set leeren
        self._quick73_sent.discard(call)
        return False
    # Im Fenster — entweder 73 senden oder komplett ignorieren
    if call in self._quick73_sent:
        # Schon Quick-73 geschickt → komplett ignorieren
        return True
    # Einmaliges Quick-73
    if self.encoder.is_transmitting:
        self.encoder.abort()
    tx_msg = f"{msg.caller} {self.settings.callsign} 73"
    self.encoder.transmit(tx_msg)
    self._quick73_sent.add(call)
    age_min = int(now - last_time) // 60
    self.qso_panel.add_info(
        f"{msg.caller} → Sende 73 (bereits gearbeitet {age_min} min)")
    return True
```

**Plus Auto-Hunt:**
```python
# core/auto_hunt.py
_RECENT_QSO_COOLDOWN_S = 1800  # alt: 300 (P61 5 Min) → 1800 (30 Min für P94-Konsistenz)
```

## Aufrufstelle finden (Code-Verifikation Schritt 0)

Im Decoder-Pfad gibt es vermutlich `mw_cycle.on_message_decoded` oder
ähnlich. Grep nach `qso_sm.on_message_received` Aufrufer — dort den
Pre-Filter einbauen.

## Tests (P94)

Neue Datei `tests/test_p94_quick73.py`:
- T1: Caller im 30-Min-Fenster + Report → Quick-73 + `_quick73_sent`
  enthält Call. State-Machine NICHT gerufen.
- T2: Caller NOCHMAL im Fenster → komplett ignoriert (kein TX, kein
  State-Wechsel). State-Machine NICHT gerufen.
- T3: Caller > 30 Min seit letztem QSO → normaler Pfad, State-Machine
  gerufen, `_quick73_sent` ohne den Call.
- T4: Anderer Caller (nicht in `_recent_logged_calls`) → normaler Pfad.
- T5: Message NICHT an my_call (`msg.target != callsign`) → Filter
  passt durch, State-Machine gerufen.
- T6: Auto-Hunt-Cooldown ist 1800s (Konstante hochgesetzt).

## APP_VERSION

0.97.65 → 0.97.66

## Workflow

V1 (diese Datei) → V2 (Self-Review) → R1 (DeepSeek) → V3 → Code +
Tests → Final-R1 → Atomare Commits → Doku-Update.
