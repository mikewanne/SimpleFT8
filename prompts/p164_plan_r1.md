# P164 — Plan-Review (R1): P158 generalisieren auf „jede Station die uns ruft"

Du bist Senior-Reviewer einer PySide6 FT8-App (Hobby-Tool, KISS, KEIN Contest).
Antwort DEUTSCH, kritisch, knapp. Code ist Referenz. Bewerte den Plan, finde
Bugs/Races/Edge-Cases VOR der Implementierung. Markiere Findings 🔴 (Blocker) /
🟠 (sollte) / 🟡 (nice). Am Ende: GO / NO-GO.

## Ziel (Mike-Spec, verbindlich)

P158 (heute) macht eine „← Empf."-Zeile im QSO-Log NUR dann klickbar, wenn
ALLE 4 gelten: Auto-Hunt aktiv + nicht manual_override + aktives QSO mit ANDEREM
Call + kein 73/rr73. Mike will das **generalisieren**: die EINZIGE inhaltliche
Bedingung soll sein „eine Station ruft uns (msg.target==my_call) und ist damit
im QSO-Fenster sichtbar" → dann klickbar. KEIN Auto-Hunt-Zwang, KEIN „anderes
aktives QSO muss laufen".

**Mike-Einsicht (wichtig):** Der EINE Schutz der BLEIBEN muss ist:
**nicht die Station anklickbar machen, mit der wir GERADE funken** (sonst würde
der Klick = „nach dem QSO nochmal rufen" = sinnloses Doppel-QSO). Im aktiven QSO
erscheint der Partner ja auch als `← Empf.`-Zeile; genau die bleibt toter Text.

**Doktrin (Memory):** Höflichkeit > Stationszahl. Wer uns ruft, dem wollen wir
antworten können — notfalls laufendes QSO erst zu Ende, dann B einschieben.

**Mike-Auftrag:** „alte Logik durch neue ersetzen, NICHT zweiten Pfad bauen."

## Ist-Architektur (verifiziert am Code)

- `mw_cycle.on_message_decoded` (Z.832): bei `msg.target==my_call` (und nicht
  P128-Cooldown) wird die Zeile via `qso_panel.add_rx(...)` ins QSO-Log
  geschrieben. Wenn `_p158_is_insertable_caller(msg)` True → `insert_call` gesetzt
  + `_p158_insertable[caller]=msg` (Merk-Dict für späteren Start).
- `_p158_is_insertable_caller` (Z.1027): die 4 Bedingungen oben.
- Render: `qso_panel.add_rx(insert_call=...)` → `_render_entry` rx-Zweig →
  `_append_anchor_line` baut `<a href="huntinsert:CALL">`. `log_view` =
  QTextBrowser, `anchorClicked`→`_on_anchor_clicked`→`hunt_insert_clicked(call)`.
  Re-render-fest (insert_call im _entries-dict).
- Klick: `main_window:667` verbindet → `_on_hunt_insert_clicked(call)` (Z.1062):
  Guards (ah.active, aktives QSO mit anderem Call, call im Dict) →
  `auto_hunt.set_pending_insert(msg)` + Info.
- QSO-Ende: `_p158_maybe_start_inserted_call` (mw_qso.py:1032) in
  `_on_qso_confirmed` (Z.711) UND `_on_qso_timeout` (Z.1024), NACH
  `on_manual_qso_end()`. Prüft `ah.active` → `take_pending_insert()` →
  `_on_station_clicked(msg)`.
- Cleanup `_p158_insertable.clear()`: Bandwechsel (mw_radio:730), Konsum
  (mw_qso:1056), Auto-Hunt-Stop (main_window:1031).
- `auto_hunt.set_pending_insert/take_pending_insert/_insert_pending_call`
  (auto_hunt.py:551/558/138): Puffer, wird bei stop_auto_hunt geleert (Z.290).
- `_on_station_clicked` (mw_qso.py:168): EINE zentrale Start-Methode. Guards:
  SWR-Sperre (return), `encoder.is_transmitting` (buffert in
  `_pending_station_click`), Diversity-Messung (return), TX-Slot-Lock. Dann:
  OMNI-Pause, CQ-Stop (cq_was_active sichern), Auto-Hunt-Pause
  (on_manual_qso_start), aus caller_queue entfernen, `start_qso(...)`.
  → ALLE Safety-Guards (inkl. ANT1-TX-Verriegelung) hängen hier.
- `qso_state.HASH_RESOLVE_STATES` (Z.862) = {TX_CALL, WAIT_REPORT, TX_REPORT,
  WAIT_RR73, TX_RR73, WAIT_73, TX_73_COURTESY} = exakt „aktives QSO mit festem
  Partner". Wiederverwendbar als „ACTIVE_QSO_STATES".
- CQ-Modus: wer uns während CQ-QSO ruft, landet in `qso_sm._caller_queue`
  (qso_state.py:564), wird nach QSO-Ende via `_resume_cq_if_needed` (pop(0))
  automatisch abgearbeitet — eigener etablierter Mechanismus.

## V1 — Implementierungsplan

### 1. `mw_cycle._p158_is_insertable_caller` — Logik ersetzen
```python
def _p158_is_insertable_caller(self, msg):
    # P164 (generalisiert): jede Station die UNS ruft ist klickbar.
    # msg.target==my_call ist durch Aufruf-Kontext (Z.832) garantiert.
    if not msg.caller or msg.caller == self.settings.callsign:
        return False
    if msg.is_73 or msg.is_rr73:
        return False
    if self.qso_sm.cq_mode:
        return False  # CQ-Modus: caller_queue ist zuständig (kein Doppel-Pfad)
    qso = self.qso_sm.qso
    if (self.qso_sm.state in ACTIVE_QSO_STATES and qso
            and qso.their_call == msg.caller):
        return False  # Doppel-Ruf-Schutz: Station mit der wir GERADE funken
    return True
```

### 2. `mw_cycle._on_hunt_insert_clicked` — state-abhängige Wirkung
```python
def _on_hunt_insert_clicked(self, call):
    msg = self._p158_insertable.get(call)
    if msg is None:
        return
    qso = self.qso_sm.qso
    in_active = (self.qso_sm.state in ACTIVE_QSO_STATES and qso
                 and qso.their_call)
    if in_active and qso.their_call == call:
        return  # Doppel-Ruf-Schutz (Klick auf aktuellen Partner)
    if in_active:
        self._qso_pending_insert = msg
        self.qso_panel.add_info(
            f"⏳ {call} vorgemerkt — wird nach diesem QSO gerufen")
    else:
        self._p158_insertable.clear()
        self._on_station_clicked(msg)   # IDLE/kein QSO → sofort rufen
```

### 3. `mw_qso._p158_maybe_start_inserted_call` — vom Auto-Hunt entkoppeln
```python
def _p158_maybe_start_inserted_call(self):
    msg = self._qso_pending_insert
    if msg is None:
        return
    self._qso_pending_insert = None
    self._p158_insertable.clear()
    self._on_station_clicked(msg)
```
(Aufruf-Stellen unverändert: Ende von `_on_qso_confirmed` + `_on_qso_timeout`,
nach `on_manual_qso_end()`.)

### 4. `main_window.__init__` — neuer Merker
`self._qso_pending_insert = None` (neben `_p158_insertable`, Z.321).

### 5. Cleanup `_qso_pending_insert` symmetrisch zum Dict
- Bandwechsel `mw_radio:730` (+ Mode-Wechsel + RX-Toggle wo Log geleert wird):
  zusätzlich `self._qso_pending_insert = None` (Pending von Band A nicht auf
  Band B feuern).
- Auto-Hunt-Stop (main_window:1031): `_p158_insertable.clear()` bleibt;
  `_qso_pending_insert` wird hier NICHT genullt (ein während manuellem QSO
  vorgemerkter Einschub muss einen Auto-Hunt-Stop überleben).

### 6. `core/auto_hunt.py` — toten Code entfernen
`set_pending_insert`, `take_pending_insert`, `_insert_pending_call`-Attribut +
dessen Clear in `__init__`/`stop_auto_hunt` raus (nicht mehr genutzt).

### 7. `qso_state.py` — Lesbarkeit
`ACTIVE_QSO_STATES = HASH_RESOLVE_STATES` (semantischer Alias, 1 Zeile) ODER in
mw_cycle direkt `HASH_RESOLVE_STATES` importieren. (Frage an dich: Alias oder
direkt?)

### 8. Tests
- Umschreiben (altes Verhalten zementiert): test_p158_active_qso.py,
  test_p158_insert_pending.py, test_p158_workflow.py,
  test_p158_pending_insert_clear.py.
- Neu testen: klickbar im IDLE ohne Auto-Hunt; klickbar im manuellen QSO mit
  anderer Station; NICHT klickbar wenn caller==aktueller Partner; NICHT für
  73/rr73/own/cq_mode; Klick im IDLE→sofort _on_station_clicked; Klick im
  aktiven QSO→_qso_pending_insert gesetzt (nicht sofort); Klick auf aktuellen
  Partner→noop; maybe_start feuert pending nach QSO-Ende OHNE Auto-Hunt;
  maybe_start ohne pending→noop; Band-Wechsel nullt _qso_pending_insert.
- Behalten: Render-Tests (Mechanik unverändert), P144-Separation.

## V2 — Self-Review (meine eigenen Bedenken, bitte prüfen/ergänzen)

1. **CQ-Ausschluss:** Ich schließe cq_mode aus (caller_queue ist zuständig).
   Sonst Konflikt: Klick setzt _qso_pending_insert, aber am QSO-Ende läuft auch
   `_resume_cq_if_needed` (pop(0)) → mögliche Doppel-Abarbeitung/Reihenfolge-
   Race. Richtig so? Oder soll P164 auch im CQ greifen (dann wie absichern)?
2. **Re-Render-Konsistenz:** Klickbarkeit wird zur DECODE-Zeit entschieden
   (insert_call gesetzt/nicht). Der HANDLER prüft zur KLICK-Zeit erneut
   (in_active, partner-check). Eine zur QSO-A-Zeit klickbar gemachte B-Zeile,
   die man erst nach QSO-Ende (IDLE) klickt → Handler ruft sofort. OK? Eine zur
   Decode-Zeit NICHT-klickbar gemachte Zeile (war Partner) bleibt toter Text
   auch wenn später valide — akzeptiert (Zeile kommt beim nächsten Decode neu).
3. **_qso_pending_insert überlebt Auto-Hunt-Stop:** nötig, weil bei manuellem
   QSO kein Auto-Hunt läuft. Aber: Wenn während QSO-A (manuell) B vorgemerkt
   und dann HALT gedrückt wird — soll B noch gefunkt werden? HALT bricht QSO-A
   ab (cancel→qso_timeout? oder nicht?). Risiko: B feuert nach HALT obwohl User
   alles stoppen wollte. → Soll HALT `_qso_pending_insert=None` setzen? Ich
   neige zu JA (HALT = Notbremse, alles weg). Bitte bewerten.
4. **Sofort-Ruf im IDLE während TX:** _on_station_clicked buffert bei
   is_transmitting in `_pending_station_click`. Doppel-Puffer mit
   _qso_pending_insert? Im IDLE-Sofort-Pfad setzen wir _qso_pending_insert NICHT
   (wir rufen direkt _on_station_clicked) → kein Konflikt. ✓
5. **Reihenfolge am QSO-Ende:** _p158_maybe_start_inserted_call läuft NACH
   on_manual_qso_end + flush_pending_stop. Der Einschub-_on_station_clicked ruft
   on_manual_qso_start (pausiert Auto-Hunt erneut). Nach B-QSO-Ende erneut
   on_manual_qso_end → Auto-Resume. Konsistent mit P158-Verhalten. ✓
6. **Safety:** finaler Anruf IMMER über _on_station_clicked → SWR-Sperre/
   Diversity/TX-Buffer/ANT1-Verriegelung intakt. Kein neuer TX-Pfad. ✓
7. **Doppel-Klick / Last-Wins:** zweiter Klick überschreibt
   _qso_pending_insert. KISS, wie alter Einzelpuffer. ✓

## Fragen an dich (DeepSeek)
- F1: CQ-Ausschluss korrekt, oder verliert Mike damit den „im CQ ruft mich
  einer"-Fall? (caller_queue deckt das ja ab — reicht das?)
- F2: HALT soll _qso_pending_insert nullen — ja/nein?
- F3: Übersehe ich einen Race zwischen _qso_pending_insert-Konsum und
  _resume_cq_if_needed / caller_queue?
- F4: ACTIVE_QSO_STATES-Alias in qso_state.py vs direkter HASH_RESOLVE_STATES-
  Import in mw_cycle — was ist sauberer?
- F5: Weitere Edge-Cases/Blocker die ich übersehe?

Gib konkrete Findings + GO/NO-GO.
