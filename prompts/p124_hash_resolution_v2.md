# R1 — P124 Hash-Call `<...>` kontextuell aus aktivem QSO auflösen

## Was ich will

Du bist Reviewer. KEIN Code generieren. Nur Findings nach Severity
(🔴/🟠/🟡/🟢) mit Datei:Zeile, Was, Warum, Vorschlag. Knapp & kritisch.
KISS bewerten. Bei Widerspruch: Code ist Referenz, nicht meine Behauptung.

## Kontext

**Projekt:** SimpleFT8 (FT8-App für FlexRadio, Hobby-Funker-Tool).
**Mike-Field-Bug 25.05.2026:** Bei aktivem QSO mit RA9LL sendet die
Gegenstation `DA1MHH <...> R+10` (FT8 i3-Frame mit 22-Bit-Hash unseres
Calls). Unsere State-Machine vergleicht `msg.caller == "<...>"` mit
`qso.their_call == "RA9LL"` → mismatch → return → Frame verworfen →
WAIT_REPORT bleibt → Retry-Loop bis Timeout.

**Mike's KISS-Idee (Quote 25.05.2026):**
> „ich verstehe nicht die 3 ... — das ist doch das call der anderen
> station, das haben wir doch schon gehabt als wir sie gerufen haben.
> das ist doch die antwort warum können wir die ... nicht einfach mit
> dem call ersetzen"

Im aktiven QSO ist der einzig sinnvolle Hash-Kandidat die
Gegenstation (`qso.their_call`). Heuristisch ersetzen, Display
plain, State-Machine matcht.

**Mike-Spec:** kein „RA9LL?"-Suffix, kein Farbcode, plain
„RA9LL" — User weiß im QSO-Kontext mit wem.

## V1/V2-Architektur

### Helper-Modul `core/qso_state.py` (Modul-Ende, NEU)

```python
_HASH_MARKER = "<...>"

_HASH_RESOLVE_STATES = frozenset({
    QSOState.TX_CALL,
    QSOState.WAIT_REPORT,
    QSOState.TX_REPORT,
    QSOState.WAIT_RR73,
    QSOState.TX_RR73,
    QSOState.WAIT_73,
    QSOState.TX_73_COURTESY,
})

def is_hash_marker(call: str) -> bool:
    """FT8 22-Bit-Hash-Marker im 2. Feld eines i3-Frames."""
    return call == _HASH_MARKER

def resolve_hash_in_msg(msg, expected_call: str) -> bool:
    """Wenn msg.field2 == '<...>' und expected_call != '',
    ersetze field2 + raw (in-place). Returns True wenn resolved."""
    if not is_hash_marker(msg.field2):
        return False
    if not expected_call:
        return False
    msg.field2 = expected_call
    msg.raw = msg.raw.replace(_HASH_MARKER, expected_call)
    return True
```

### Integration in `ui/mw_cycle.py:on_message_decoded` (Z. 763)

```python
def on_message_decoded(self, msg: FT8Message):
    if not self.rx_panel._rx_active:
        return
    # P124: Hash kontextuell auflösen VOR add_rx + on_message_received
    self._p124_resolve_hash_if_active_qso(msg)
    
    self.control_panel.update_snr(msg.snr)
    ...

def _p124_resolve_hash_if_active_qso(self, msg) -> bool:
    from core.qso_state import resolve_hash_in_msg, _HASH_RESOLVE_STATES
    if msg.target != self.settings.callsign:
        return False
    if self.qso_sm.state not in _HASH_RESOLVE_STATES:
        return False
    if not self.qso_sm.qso or not self.qso_sm.qso.their_call:
        return False
    return resolve_hash_in_msg(msg, self.qso_sm.qso.their_call)
```

### Aufruf-Reihenfolge (verifiziert via P82 Decoder-Signal-Reihenfolge)

```
1. _on_cycle_decoded(messages)  ← Aggregation, _assign_slot_parity,
                                   _handle_normal_mode/diversity_operate
                                   (Locator-DB, accumulate_stations →
                                    RX-Tabelle), AP-Lite, Auto-Hunt
2. PRO MSG: on_message_decoded(msg)
   ├─ P124 Resolution (NEU)
   ├─ add_rx(msg.raw)            ← Display
   └─ on_message_received(msg)   ← State-Machine
3. _on_cycle_finished() → on_decoder_finished()
```

## Akzeptanzkriterien (AC)

- **AC1-7** wie V1 dokumentiert (siehe Backlog).
- **AC8:** Display zeigt aufgelösten Call.
- **AC9:** State-Machine matcht (kein verworfener R-Report).
- **AC10:** Echte Calls (`EA1FLB DA1MHH JO31`) unverändert.

## Risiken (Stand V2)

- **R1** 🟡: Hash-Collision (1 in 4M). Akzeptiert (Mike-Spec).
- **R2** 🟢: Parallel-Call mit echtem Call → no-op, Standard-Pfad greift.
- **R3** 🟡: msg-Mutation in-place. Konsumenten nach `on_message_decoded`: keine bekannt (msg geht durch und endet).
- **R4** 🟢: Auto-Hunt + AP-Lite (Schritt 1) sehen Original-msg. Auto-Hunt filtert nur `is_cq=True`, Hash kommt nie als CQ. AP-Lite ist beratend.
- **R5** 🟡: `_handle_normal_mode` → `accumulate_stations` (Schritt 1) sieht Original-`<...>`. Würde als RX-Tabellen-Eintrag „`<...>`" landen. KISS-Frage: stört das?
- **R6** 🟢: `qso_sm.qso` wird bei `qso_complete`/`qso_timeout` nicht null gesetzt — state-Filter `_HASH_RESOLVE_STATES` schließt TIMEOUT/IDLE aus.
- **R7** 🟢: Hardware-Sicherheit unverändert.

## Was du prüfen sollst

**Frage 1 (Architektur — wichtigste!):**
Resolution in `on_message_decoded` (V1-Plan, **KISS**, RX-Tabelle
bleibt `<...>`) ODER in `_on_cycle_decoded` VOR
`_handle_normal_mode` (sauberer, RX-Tabelle auch resolved, aber
Eingriff früher und Resolution läuft pro msg im messages-Loop)?

Mike-Spec sagt nur „plain anzeigen" — er meinte primär das QSO-Log.
RX-Tabelle hat Mike nicht erwähnt. Für KISS wäre A besser; für
Konsistenz B. Welche Wahl?

**Frage 2 (API-Sichtbarkeit):**
`_HASH_MARKER` und `_HASH_RESOLVE_STATES` sind Modul-privat
(underscore). Import in `ui/mw_cycle.py` mit Underscore möglich aber
„dirty". Alternative: public `HASH_MARKER` / `HASH_RESOLVE_STATES`
ODER als Methode `QSOStateMachine.is_active_for_hash_resolve()`.
Was ist KISS und Python-idiomatisch?

**Frage 3 (Edge-Case Validierung):**
- Was wenn `msg.raw` mehrere `<...>` enthält? (`<...> <...> JO31`)
  In Praxis bei i3-Frames: 1 Hash. Aber theoretisch?
- Was wenn FT8-Sender-Hash bekannt: `<DA1MHH> <...> R+10`. Würde
  `replace("<...>", call)` `<DA1MHH>` berühren? (Nein, weil exact
  Match.) Aber: ist das so robust?

**Frage 4 (State-Liste):**
`_HASH_RESOLVE_STATES` enthält {TX_CALL, WAIT_REPORT, TX_REPORT,
WAIT_RR73, TX_RR73, WAIT_73, TX_73_COURTESY}. Fehlt was? LOGGING ist
legacy (nicht mehr aktiv genutzt, siehe qso_state.py:101) — bewusst
ausgelassen. CQ_CALLING ist „wir senden CQ, noch kein Partner"
→ kein QSO-Kontext → bewusst ausgelassen. Korrekt?

**Frage 5 (Test-Coverage):**
V1-Plan hat 10 Tests. Was fehlt?

**Frage 6 (Hash-Frame Spezifikation):**
Ist meine Annahme korrekt dass FT8 i3-Frames `<...>` als String-
Repräsentation des 22-Bit-Hash im Decoder-Output liefern (PyFT8/
ft8_lib)? Oder gibt's andere Varianten (z.B. `<HASH>`, `<12345>`,
`<unknown>`)? Falls ja → `is_hash_marker` zu schwach.

**Frage 7 (KISS-Bewertung Gesamt):**
Ist die Lösung KISS (Mike-Wert) oder overengineered? Würde ein
einfacher 1-Zeilen-Patch in `on_message_received` Z. 604 reichen?

```python
# Z. 604 ORIGINAL: if msg.caller != self.qso.their_call: return
# P124 KISS-1-Liner:
if msg.caller != self.qso.their_call and msg.caller != "<...>": return
```

Vorteile 1-Liner:
- Minimal-invasiv
- Kein neuer Helper, keine neue Konstante
- Nur State-Machine fixed, Display zeigt aber weiter `<...>` (R-Report
  geht aber durch → kein Retry-Loop mehr)

Nachteile:
- Display zeigt `<...>` (gegen Mike-Spec „plain anzeigen")
- Keine State-Liste — greift in ALLEN states wo der Check läuft

Bewerte: KISS-1-Liner ODER V1-Helper-Architektur? Mike will plain
anzeigen → 1-Liner reicht nicht — er deckt nur die State-Machine,
nicht den Display-Pfad. Aber: vielleicht ist das genug? Bug ist primär
„Retry-Loop", Plain-Display ist Mike's Bonus-Wunsch.

## Was ich NICHT will

- Vorschläge wie „Hash-Cache aufbauen für später eintreffende Hash-
  Frames ohne aktiven QSO-Kontext" → overengineered, Mike-Spec NUR
  während aktivem QSO.
- Vorschläge wie „Hash-Database mit ft8_lib-API koppeln" → out-of-scope.
- Multi-Hash-Stationen-Disambiguation (Theorie für DXpedition) →
  Hobby-Tool, nicht relevant.

Sei kritisch. Sag wenn du was übersiehst.
