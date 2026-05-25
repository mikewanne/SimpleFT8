# Final-R1 — P124 Hash-Call Resolution (Committeter Code)

## Was ich will

Final-Review der **implementierten** Lösung gegen die V3-Akzeptanzkriterien.
Knapp. Severity (🔴/🟠/🟡/🟢). Datei:Zeile. PUSH FREIGEGEBEN ja/nein.

## Kontext

P124 ist Mike's Field-Bug: bei aktivem QSO mit RA9LL sendet Gegenstation
`DA1MHH <...> R+10` (ft8_lib Hash-Marker für unaufgelösten 22-Bit-Hash).
State-Machine Z. 604 `if msg.caller != self.qso.their_call: return`
verwirft den R-Report → Retry-Loop bis Timeout.

Mike's KISS-Lösung: im aktiven QSO ist einziger sinnvoller Hash-Kandidat
die Gegenstation → heuristisch ersetzen. Mike-Spec auch „plain anzeigen".

## V3 ACs (alle MÜSSEN nach Review erfüllt sein)

- AC1-7: Resolution greift nur bei msg.target==my_call + State in
  HASH_RESOLVE_STATES + qso.their_call gesetzt
- AC8: Display zeigt aufgelösten Call (msg.raw mutiert)
- AC9: State-Machine matcht (kein verworfener R-Report)
- AC10: Echte Calls unverändert
- AC11: `<RA9LL>` (Hashtable-resolved) auch erkannt
- AC12: msg.raw replace bei beiden Bracket-Formen korrekt

## R1-Findings die in V3 eingearbeitet wurden

| # | Findng | V3-Fix |
|---|---|---|
| F1 🔴 | 1-Liner reicht nicht | V1-Helper-Architektur beibehalten |
| F2 🟡 | Konstanten public | `HASH_MARKER`/`HASH_RESOLVE_STATES` ohne Underscore |
| F3 🟡 | End-to-End-Test | T12 hinzugefügt |
| F4 🟠 | `<...>` verifizieren | ft8_lib/message.c:709 verifiziert + Bracket-Pfad ergänzt |

## Implementierung

### core/qso_state.py (am Modul-Ende, NACH `cancel`-Methode)
- HASH_MARKER = "<...>"
- HASH_RESOLVE_STATES frozenset({TX_CALL, WAIT_REPORT, TX_REPORT,
  WAIT_RR73, TX_RR73, WAIT_73, TX_73_COURTESY})
- is_hash_marker(call): bracket-Test + len >= 3
- resolve_hash_in_msg(msg, expected_call): mutiert msg.field2 + msg.raw

### ui/mw_cycle.py
- on_message_decoded Z. 763 — Aufruf von _p124_resolve_hash_if_active_qso
  als allererstes nach rx_panel-Guard, VOR add_rx und on_message_received
- _p124_resolve_hash_if_active_qso (neue Mixin-Methode nach on_message_decoded):
  3 Guards (target == my_call, state in HASH_RESOLVE_STATES, qso.their_call gesetzt)
  → resolve_hash_in_msg

## Tests (16 in tests/test_p124_hash_resolution.py)

T1-T5: is_hash_marker (5 Cases inkl. Brackets-Resolved-Pfad)
T6-T9: resolve_hash_in_msg (4 Cases inkl. No-Op-Pfade)
T10-T11e: Mixin-Methode + State-Gates (6 Cases inkl. alle States in
HASH_RESOLVE_STATES)
T12: End-to-End — on_message_received in WAIT_REPORT matcht nach
Resolution → State wechselt zu TX_RR73, sendet "RA9LL DA1MHH RR73"

Tests grün: 1851 → 1867 (+16). Komplette Suite (1867) bleibt grün.

## Was du prüfen sollst

1. **Sind die Akzeptanzkriterien AC1-AC12 abgedeckt?** Welche fehlen
   oder sind unvollständig getestet?
2. **Race-Conditions?** msg-Mutation in-place — gibt es einen Pfad wo
   dasselbe msg-Objekt nach `on_message_decoded` nochmal genutzt wird
   und durch die Mutation überrascht wäre?
3. **Konsistenz `resolve_hash_in_msg`:** `msg.raw.replace(original_marker,
   expected_call)` — bei mehreren `<...>` im raw würden alle ersetzt.
   In Praxis: 1 Hash pro Frame. Reicht das?
4. **Import-Stil:** `from core.qso_state import resolve_hash_in_msg,
   HASH_RESOLVE_STATES` innerhalb der Mixin-Methode (lazy). Python-
   idiomatisch oder besser top-of-file?
5. **State-Liste vollständig?** HASH_RESOLVE_STATES schließt IDLE,
   CQ_CALLING, CQ_WAIT, TIMEOUT, LOGGING bewusst aus. Korrekt?
6. **Hardware-Sicherheit unverändert?** Kein TX-Pfad berührt — verify.
7. **Backward-Compat:** Alle bestehenden Tests (1851) bleiben grün
   (verified: 1867 total). Keine Regression?

## Verdict erwartet

PUSH FREIGEGEBEN / NACHBESSERN / BLOCK

Sei kritisch.
