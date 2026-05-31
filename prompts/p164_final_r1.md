# P164 — Final-R1 (Review des FERTIGEN Codes)

Du bist Senior-Reviewer einer PySide6 FT8-App (Hobby-Tool, KISS, KEIN Contest).
Antwort DEUTSCH, knapp, kritisch. Das ist der FINALE Review vor Commit. Der Plan
wurde bereits R1-reviewt (GO). Prüfe jetzt die UMSETZUNG am echten Code:
Korrektheit, Races, Edge-Cases, Regressions, KISS. Markiere 🔴/🟠/🟡.
Verdikt am Ende: PUSH FREIGEBEN / NACHBESSERN.

## Was P164 macht (Kurzfassung)

Generalisiert die alte P158-Logik: Eine Station die UNS ruft, ist im QSO-Log
klickbar — KEIN Auto-Hunt-Zwang, KEIN "anderes aktives QSO muss laufen". Einzige
inhaltliche Bedingung: sie ruft uns + kein 73/rr73 + nicht CQ-Modus + nicht der
aktuelle QSO-Partner (Doppel-Ruf-Schutz). Klick-Wirkung state-abhängig: aktives
QSO → vormerken (A zu Ende, dann B), IDLE → sofort rufen. Merker
`_qso_pending_insert` lebt in MainWindow (vom Auto-Hunt entkoppelt). Alte
auto_hunt.set/take_pending_insert ENTFERNT. Finaler Anruf IMMER über
`_on_station_clicked` (alle Safety-Guards: SWR-Sperre, Diversity, TX-Buffer,
ANT1-Verriegelung).

R1-Findings eingebaut: F2 🔴 HALT (`_on_cancel`) nullt `_qso_pending_insert`;
F4 ACTIVE_QSO_STATES-Alias in qso_state.py.

## Tests: 2205 passed (volle Suite grün), 34 in test_p158_insert_pending_call.py.

## Prüf-Schwerpunkte (bitte gezielt)

1. **`_p158_is_insertable_caller`** (mw_cycle.py): deckt die Bedingungen Mikes
   Spec korrekt ab? `ACTIVE_QSO_STATES`-Check + `qso.their_call == msg.caller`
   nur als Doppel-Ruf-Schutz — greift er auch wenn qso=None / their_call leer
   (IDLE)? (Soll dann klickbar sein.)
2. **`_on_hunt_insert_clicked`** (mw_cycle.py): state-abhängige Verzweigung
   korrekt? IDLE→sofort (`_on_station_clicked`), aktiv→vormerken. Klick auf
   aktuellen Partner→noop. Race wenn zwischen Decode (Dict-Eintrag) und Klick der
   State wechselt?
3. **`_p158_maybe_start_inserted_call`** (mw_qso.py): vom Auto-Hunt entkoppelt,
   nullt `_qso_pending_insert` VOR `_on_station_clicked` (Reentrancy). Reihenfolge
   in `_on_qso_confirmed`/`_on_qso_timeout` OK (nach on_manual_qso_end)?
4. **HALT** (`_on_cancel`): nullt `_qso_pending_insert`. Reicht das? `cancel()`
   emittiert KEIN qso-Signal → maybe_start läuft nach HALT nicht → Pending bliebe
   sonst liegen → korrekt genullt?
5. **Cleanup-Symmetrie**: `_qso_pending_insert = None` bei Band-/Mode-/RX-Wechsel
   (mw_radio.py) + HALT + Konsum. Fehlt eine Stelle? (z.B. muss Auto-Hunt-Stop es
   NICHT nullen, weil ein manuell vorgemerktes B einen Auto-Hunt-Stop überleben
   soll — korrekt so?)
6. **Entkopplung sauber?** auto_hunt.py: set/take_pending_insert + Attribut +
   alle Clears entfernt, keine verwaisten Referenzen? (`grep` zeigt 0 außerhalb
   Tests.)
7. **Regression**: Verändert P164 das Verhalten im normalen Auto-Hunt-Einschub
   (B ruft während Auto-Hunt-QSO mit A) gegenüber P158? Soll IDENTISCH bleiben
   (A zu Ende → B → Auto-Resume), nur dass jetzt zusätzlich manuelle QSOs + IDLE
   abgedeckt sind.
8. **Safety**: TX läuft IMMER über ANT1 — bleibt durch `_on_station_clicked`
   garantiert? Kein neuer TX-Pfad?

## Code folgt (vollständige geänderte Dateien angehängt).
