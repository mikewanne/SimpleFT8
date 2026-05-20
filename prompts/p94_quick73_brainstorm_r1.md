Du bist Senior Python-Entwickler spezialisiert auf Amateurfunk-FT8-
Software und QSO-State-Machines. Hobby-Funker-Tool für einen Operator,
KEIN Multi-Operator, kein Contest. WSJT-X-Funkverkehrs-Konventionen
sind die Referenz.

# P94 — Etiquette-konformer Umgang mit „doppelten" Anrufen nach abgeschlossenem QSO

## Mike's Beobachtung (20.05.2026 Field-Test, v0.97.65)

Sequenz vom Screenshot:
```
11:13:30  Sende  9A4AA DA1MHH -16
11:13:45  Empf.  9A4AA  R-12
11:14:00  Sende  9A4AA RR73
11:14:15  Empf.  9A4AA  73
11:14:30  Sende  9A4AA 73          (courtesy-73, max 1x)
✓ QSO mit 9A4AA komplett

[4 Minuten Pause]

11:18:30  Sende  9A4AA DA1MHH -14   ← App hat erneut volles QSO gestartet!
11:18:45  Empf.  9A4AA  R-08
11:19:00          → Duplikat (299s) — kein ADIF-Eintrag
11:19:15  Empf.  9A4AA  RR73
11:19:30  Sende  9A4AA RR73
✓ QSO mit 9A4AA komplett   (wieder, aber nicht im ADIF)
```

9A4AA hat unser RR73 oder 73 anscheinend nicht aufgenommen und ruft
uns erneut mit Report → unsere App fährt vollen Report-Austausch
nochmal, weil `on_message_received` (core/qso_state.py:572) bei
State CQ_WAIT/IDLE und target=my_call+is_report → einen neuen QSO
über `_process_cq_reply` startet.

Bestehender Schutz: `_LOG_DEDUP_WINDOW_S=300s` in `ui/mw_qso.py:23`
verhindert nur den **ADIF-Eintrag** am QSO-Ende. Der Funkverkehr
findet trotzdem statt — Pile-Up + Funkzeit-Verschwendung + chaotisches
QSO-Panel.

## Mike's Spec für P94

> „Wenn nach abgeschlossenem QSO eine andere Station nochmal Rapport
> sendet → einmal normales 73 senden, dann für 30 Minuten ignorieren."

Begründung Mike:
- Etiquette: 73 ist die korrekte Antwort auf nochmaligen Report nach
  komplettem QSO (signalisiert „QSO ist für mich vorbei, danke").
- Funkzeit sparen: 1 Slot 73 statt 5 Slots Report-Austausch.
- QSO-Panel bleibt übersichtlich: pro Station nur 1 Block aus 5-6
  Zeilen wie heute, keine Doppel-QSOs mehr.

## Aktueller Code (Zeit-verifiziert)

**`core/qso_state.py:546-589` `on_message_received`:**
```python
# ── Jemand ruft UNS (CQ-Modus, oder im IDLE) ──
if self.state in (QSOState.IDLE, QSOState.CQ_WAIT, QSOState.CQ_CALLING) \
        and msg.target == self.my_call:
    if msg.is_grid or msg.is_report:
        self._pending_reply = msg
        if self.state in (QSOState.IDLE, QSOState.CQ_WAIT):
            self._process_cq_reply()  # ← HIER startet ein neues QSO
        elif self.state == QSOState.CQ_CALLING:
            self.try_replace_pending_tx.emit(msg)
        return
```

`_process_cq_reply()` setzt State auf TX_REPORT und sendet `their_call
my_call -XX` — startet damit den Hunt-Zyklus.

**Bestehender ADIF-Dedup-Filter (`ui/mw_qso.py:537-555`):**
```python
_LOG_DEDUP_WINDOW_S = 300  # 5 Minuten
# wenn (call, band) innerhalb 300s schon geloggt → kein ADIF-Eintrag
```

Liste der "kürzlich geloggten" Calls ist `self._recent_logged_calls`
in MainWindow — dict {(call, band): timestamp}, Session-lokal.

## P94 Lösungsskizze (zur Bewertung)

**Lösungs-Vorschlag „Quick-73-Ignore":**

1. Neue Konstante `_RECENT_QSO_QUICK73_WINDOW_S = 1800` (30 Min).
2. Im `on_message_received` Z.572-580 BEVOR `_process_cq_reply`:
   - Prüfen: `msg.caller` in `_recent_logged_calls` mit Timestamp
     innerhalb 30 Min auf demselben Band?
   - **JA:** kein neues QSO. Stattdessen:
     a) Einmal `<caller> <my_call> 73` als TX-Slot encoden.
     b) Caller-Ignore-Liste setzen (separate dict mit Timestamp).
     c) UI-Info: `9A4AA → bereits gearbeitet, sende 73`.
     d) State bleibt IDLE/CQ_WAIT.
   - **NEIN:** weiter wie heute (Report-Austausch).
3. Wenn derselbe Caller innerhalb dieser 30 Min nochmal ruft (vielleicht
   hat er auch das 73 nicht bekommen):
   - In Ignore-Liste → **gar nichts senden**, einfach im RX-Panel
     anzeigen ohne State-Wechsel.
4. Cross-Module-Pfad: `_recent_logged_calls` lebt in `mw_qso.py`
   (MainWindow), nicht in `qso_state.py` (core). Heißt: P94-Logik
   muss entweder
   - **A)** in `mw_qso.py` (Pre-Filter vor `qso_sm.on_message_received`)
     ODER
   - **B)** `qso_state.py` bekommt Zugriff auf dieselbe Quelle via
     Reference/Callback.

## Bewertungs-Fragen für DeepSeek-R1

1. **Wahl A vs B (Pre-Filter in mw_qso.py vs Logik in qso_state.py):**
   wo gehört das hin? KISS-mäßig welche Schicht ist die richtige?
   - A: weniger Eingriff in State-Machine, aber `mw_qso.py` muss
     Encoder direkt rufen für das 73.
   - B: sauberer state-machine-intern, aber `qso_state.py` braucht
     Cross-Module-Zugriff auf Dedup-Liste.

2. **30 Min Fenster — sinnvoll?** Mike sagt 30 Min. WSJT-X hat keinen
   solchen Mechanismus. JTDX hat ähnliches mit ~10 Min Default.
   Sollte das Fenster konfigurierbar sein oder fest? Hobby-Kontext
   = fest 30 Min reicht?

3. **Was wenn die andere Station nach unserem 73 immer noch Report
   sendet** (also auch 73 nicht angekommen)? Vorschlag oben Punkt 3:
   gar nichts senden. Alternative: 73 nochmal? Riskiert Endlos-Loop.
   Was ist die WSJT-X-Praxis hier?

4. **State-Machine-Implikation:** Wenn wir bei CQ_WAIT einen 73-Slot
   einschieben, danach State zurück auf CQ_WAIT — Encoder.tx_even +
   Slot-Parity korrekt nach dem 73-Slot? Brauchen wir
   `try_replace_pending_tx` oder kann direkt `encoder.transmit()`
   gerufen werden?

5. **Was wenn die Station ein NEUER Anrufer ist** (nicht in
   `_recent_logged_calls`)? Standard-Verhalten unverändert (vollständiger
   Report-Austausch). Bestätige.

6. **Was wenn Mike im OMNI-CQ ist?** Dort gibt's eigenen Pfad
   (`_omni_cq.py`, `on_cycle_start`). Sollte P94-Quick-73 dort auch
   greifen oder nur in Normal-CQ + Hunt?

7. **Was wenn Auto-Hunt das Call wieder selbst pickt?** Eigentlich
   sollte Auto-Hunt schon den Recent-QSO-Cooldown haben (P61, 5 Min
   Hard-Cap). Aber 30 Min wäre passender als Default-Override. Konsistenz?

8. **UI-Anzeige:** wie sollte das im QSO-Panel aussehen?
   - Option A: `9A4AA → Sende 73 (bereits gearbeitet 4 min)`
   - Option B: dezent, nur als info-Zeile ohne Action-Eintrag
   - Option C: gar nichts anzeigen, nur ins ADIF/Stats

9. **KISS-Sicht:** ist 30 Min vs 5 Min (heute ADIF-Filter) ein
   Konflikt? Sollten die zusammengeführt werden (eine Schwelle für
   alles) oder bewusst getrennt?

10. **Risiko-Abschätzung:** Pile-Up bei großem Contest würde mit
    P94 schlechter aussehen (Station ruft uns 3x, wir senden 3x 73)?
    Oder besser (wir blocken nach 1x 73)? Im Hobby-Kontext relevant?

## Erwartete Antwort

- Tabelle Schwere | Finding | Datei:Zeile | Empfehlung
- Konkrete A-vs-B-Empfehlung mit Begründung
- 30-Min-Schwelle bewerten
- Code-Skizze für den empfohlenen Ansatz (welche Funktion ändert sich
  wie, ohne kompletten Code)
- Empfehlung Workflow: voller V1→V2→R1 oder „minimaler Eingriff" wie
  bei P93?
