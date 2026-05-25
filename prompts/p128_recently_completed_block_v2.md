# R1 — P128 Empf.-Eintrag 60s blocken nach ✓ QSO

## Was ich will

Du bist Reviewer. KEIN Code generieren. Findings nach Severity (🔴/🟠/🟡/🟢)
mit Datei:Zeile, Was, Warum, Vorschlag. KISS bewerten. Code ist Referenz.

## Kontext

**Mike-Field-Bug 25.05.2026 (Screenshot EA1FLB):** Nach „✓ QSO mit
EA1FLB komplett" (2x RR73 gesendet) sendet EA1FLB im nächsten Slot
nochmal R-23 → erscheint trotzdem als „← Empf."-Eintrag im QSO-Log.

Mike-Worte: „wir haben 2 mal 73 gesendet noch höflicher geht es
nicht, wenn er nicht kann oder will ist es ja sein problem ... wenn
beendet ist beendet".

**Mike-Spec (per AskUserQuestion):** Variante A — 60s harter Block
nach `qso_complete`. RX-Tabelle/Wasserfall unberührt.

## V1/V2-Architektur

### Init `ui/main_window.py:287`
```python
self._recently_completed_qsos: dict[str, float] = {}
```

### Konstante `ui/mw_qso.py` Modul-Top
```python
_RECENTLY_COMPLETED_BLOCK_S = 60.0
```

### Set-Pfad `ui/mw_qso.py:_on_qso_complete` Z. 538
```python
self._active_qso_targets.discard(qso_data.their_call)
# P128: Cooldown setzen
self._recently_completed_qsos[qso_data.their_call] = time.monotonic()
```

### Filter `ui/mw_cycle.py:on_message_decoded` Z. 776
```python
if msg.target == self.settings.callsign:
    # P128: 60s-Block nach ✓ QSO
    if self._p128_recently_completed_block(msg.caller):
        return  # KEIN add_rx, State-Machine läuft trotzdem
    # ... bestehender add_rx-Code
```

Helper:
```python
def _p128_recently_completed_block(self, caller: str) -> bool:
    completion_ts = self._recently_completed_qsos.get(caller)
    if completion_ts is None:
        return False
    if time.monotonic() - completion_ts < _RECENTLY_COMPLETED_BLOCK_S:
        return True
    del self._recently_completed_qsos[caller]  # Aging
    return False
```

### Reset-Pfade
- `ui/mw_radio.py:_on_band_changed` Z. 546: `_recently_completed_qsos.clear()`
- `ui/mw_radio.py:_on_mode_changed` Z. 432: analog
- `ui/mw_qso.py:_on_station_clicked` Z. 250: `pop(msg.caller, None)` (Re-Klick)

## ACs

- AC1-AC10 wie V1 (Set, Filter, RX-Tabelle unberührt, State-Machine läuft
  durch, Reset bei Band/Mode/Re-Klick, andere Stationen nicht betroffen,
  Timeout setzt KEINEN Cooldown, P100-Pfad auch).

## Was du prüfen sollst

**Frage 1 (KRITISCH — Mike-Spec offen):**
`_on_qso_timeout` (✗) — soll auch 60s blocken oder nicht? Mein
Vorschlag: NICHT — Timeout = QSO gescheitert, weitere Decodings
sind „doch noch was gehört" und potentiell wichtig für User. Mike
hat bei P128 explizit von „✓ QSO komplett" gesprochen, nicht von
Timeout.

Argumente PRO Timeout-Block:
- Symmetrie: nach Timeout will Mike auch keine Empf.-Spam-Einträge
- Einheitliches Verhalten

Argumente CONTRA:
- Timeout-Station ist potentiell „wieder ansprechbar" → User will
  vielleicht sehen
- Mike-Spec war explizit ✓
- Auto-Hunt hat schon eigenen Cooldown nach Timeout

Welche Wahl?

**Frage 2 (Quick73-Interaktion):**
P94 Quick73-Filter (mw_cycle.py:822) sendet 1x 73 wenn kürzlich
(30 Min) gearbeitete Station erneut Report/Grid sendet. Mit P128
würde Quick73 noch im 60s-Block 73 senden (Sende-Eintrag im Log),
während add_rx blockiert ist. Bedeutet: Mike sieht „→ Sende 73 ..."
aber kein „← Empf.". Verwirrend?

Vorschlag KISS: nicht ändern — P128 ist nur Display-Filter, Quick73
ist eigenständig. Wenn nervt → P129. Akzeptabel?

**Frage 3 (P124-Interaktion):**
P124 (Hash-Resolution) läuft VOR P128-Filter im on_message_decoded.
Hash-Frame wird zuerst zu echtem Call resolved, dann gegen Cooldown
geprüft. Korrekt?

**Frage 4 (Reset-Vollständigkeit):**
Reset-Pfade: Bandwechsel, Mode-Wechsel, Re-Klick. Fehlt was?
- App-Restart → Runtime-State, automatisch
- RX-Panel-Toggle (`_on_rx_panel_toggled`)? Vermutlich nicht nötig
  (P115 hat das schon als „Reset"-Pfad — sollte hier auch sein?)
- CQ-Start/Stop?
- Diversity-Toggle?

**Frage 5 (State-Machine läuft trotzdem):**
Filter macht `return` nur für add_rx-Block, aber `on_message_received`
läuft weiter. Wichtig falls die Station nochmal was Relevantes sendet
(z.B. CQ → würde aus QSO-Kontext rausfallen). Bestätigen?

**Frage 6 (Edge-Cases):**
- Was wenn QSO mit RA9LL endet, dann mit EA1FLB neu beginnt (Auto-Hunt),
  und RA9LL sendet R-23 im 60s-Fenster → wird blockiert. Aber EA1FLB-
  QSO läuft! Mike könnte denken „RA9LL ist verschwunden". Akzeptabel?
- Mit P124: was wenn aktives QSO mit EA1FLB läuft + RA9LL (60s
  blocked) sendet Hash an uns → Hash wird zu EA1FLB resolved (Bug-
  R2 aus P124), DANN P128 blockt EA1FLB-Eintrag → DOPPELT verwirrend.
  Wirklich?

**Frage 7 (KISS-Bewertung):**
60s als Konstante hardcoded vs Settings-konfigurierbar? Mike-Spec war
60s — KISS = Konstante. Aber falls Mike später anders will, müsste
er Code ändern. Settings sind 30 Sek Aufwand. Lohnt sich?

**Frage 8 (Tests-Vollständigkeit):**
12 Tests in V1-Plan. Was fehlt?
