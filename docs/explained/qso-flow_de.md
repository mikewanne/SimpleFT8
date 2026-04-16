# QSO-Ablauf — Wie SimpleFT8 ein QSO durchfuehrt

## Kurzfassung

SimpleFT8 uebernimmt den kompletten FT8-Nachrichtenaustausch automatisch. Du klickst eine Station an (Hunt-Modus) oder drueckst CQ (CQ-Modus), und die Zustandsmaschine kuemmert sich um Nachrichten, Timeouts, Wiederholungen und das Loggen.

## Zwei Betriebsarten

| Modus | Du machst | SimpleFT8 macht |
|-------|-----------|-----------------|
| **Hunt** | Station in der RX-Liste anklicken | Report senden, Austausch, QSO loggen |
| **CQ** | CQ-Button druecken | CQ rufen, Anrufer beantworten, Warteliste verwalten, jedes QSO loggen |

Beide Modi verwenden denselben Nachrichtenaustausch. Der Unterschied liegt nur darin, wer den Kontakt startet.

## Hunt-Modus — Schritt fuer Schritt

1. **Station anklicken** in der Empfangsliste. SimpleFT8 sendet deinen Signalreport an die Station.
2. **Auf Report warten.** Die Gegenstation sendet ihren Signalreport zurueck.
3. **R-Report senden.** SimpleFT8 bestaetigt mit R-Prefix (z.B. `R-12`).
4. **Auf RR73 warten.** Die Gegenstation bestaetigt mit RR73 oder 73.
5. **RR73 senden.** SimpleFT8 sendet RR73 und loggt das QSO in die ADIF-Datei.
6. **Auf 73 warten.** SimpleFT8 wartet bis zu 3 Zyklen auf eine 73-Bestaetigung, dann zurueck auf Leerlauf.

Wenn die Gegenstation nach 2 Zyklen nicht antwortet, wiederholt SimpleFT8 automatisch. Nach der konfigurierten Maximalzahl (Standard: 3 Versuche) wird das QSO abgebrochen.

## CQ-Modus — Schritt fuer Schritt

1. **CQ druecken.** SimpleFT8 sendet `CQ DA1MHH JO31` auf einer freien Frequenz.
2. **Station antwortet.** SimpleFT8 erkennt den Anrufer und fuehrt den QSO-Austausch automatisch durch.
3. **QSO abgeschlossen.** Der Kontakt wird geloggt, und SimpleFT8 prueft die Warteliste.
4. **Naechster Anrufer.** Wenn Stationen waehrend des QSOs gerufen haben, wird die naechste sofort beantwortet. Sonst geht CQ weiter.

### Die Warteliste

Wenn du mitten in einem QSO bist und eine andere Station dich ruft, wird sie auf die Warteliste gesetzt. Sowohl Grid- als auch Report-Antworten werden akzeptiert. Nach dem aktuellen QSO wird die naechste Station von der Warteliste sofort beantwortet, ohne nochmal CQ zu rufen. Das haelt die Effizienz bei Pile-Ups hoch.

Das QSO-Panel zeigt die Warteliste an: `Warteliste: EA3FHP, W1XY`.

## Even und Odd Slots — [E] und [O]

FT8 arbeitet in 15-Sekunden-Zeitschlitzen, abwechselnd gerade und ungerade:

| Sekunde | Slot | Wer sendet |
|---------|------|------------|
| 0-15 | Even [E] | Eine Seite des QSOs |
| 15-30 | Odd [O] | Die andere Seite |

SimpleFT8 waehlt automatisch den richtigen Slot:

- **Hunt-Modus:** Du sendest im Gegentakt zur angeklickten Station. Wenn sie im geraden Slot gesendet hat, sendest du im ungeraden.
- **CQ-Modus:** Du sendest in einem festen Slot (der Gegentakt zum aktuellen Zyklus beim Druecken von CQ).

Die Anzeige [E] oder [O] im Kontrollfeld zeigt deinen aktuellen Sendeslot.

## RR73-Hoeflichkeitswiederholung

Manchmal sendet die Gegenstation ihren R-Report weiter, weil sie unser RR73 nicht empfangen hat. SimpleFT8 reagiert automatisch:

- Nach dem Senden von RR73 geht SimpleFT8 in den WAIT_73-Zustand.
- Wenn die Gegenstation ihren R-Report wiederholt, sendet SimpleFT8 erneut RR73 (maximal 2 Mal).
- Nach 2 Hoeflichkeitswiederholungen werden weitere Nachrichten ignoriert.

Das verhindert Endlosschleifen und bleibt trotzdem hoeflich auf dem Band.

## WAIT_73 — Auf Bestaetigung warten

Nach dem Loggen eines QSOs wartet SimpleFT8 bis zu 3 Zyklen auf ein finales 73 von der Gegenstation:

- Wenn 73 empfangen wird, bekommt das QSO ein Bestaetigungszeichen in der Oberflaeche.
- Wenn kein 73 innerhalb von 3 Zyklen kommt, ist das QSO trotzdem geloggt (RR73 wurde ja gesendet), und SimpleFT8 macht mit CQ weiter oder geht in den Leerlauf.

Das QSO wird in dem Moment in die ADIF-Datei geschrieben, wenn RR73 gesendet wird. WAIT_73 steuert nur die Anzeige der Bestaetigung.

## Timeouts

| Timeout | Dauer | Was passiert |
|---------|-------|--------------|
| Einzelschritt-Retry | 2 Zyklen (~30 s) | Letzte Nachricht wird wiederholt |
| Globaler QSO-Timeout | 3 Minuten | QSO wird komplett abgebrochen |
| WAIT_73-Timeout | 3 Zyklen (~45 s) | CQ fortsetzen oder Leerlauf |
| Gesperrt-nach-QSO | 5 Minuten | Gleiche Station kann nicht erneut gearbeitet werden |

## Vorwaertsspruenge

SimpleFT8 kann mit Nachrichten umgehen, die ausserhalb der normalen Reihenfolge ankommen:

- Wenn RR73 empfangen wird, waehrend noch auf den Report gewartet wird, springt SimpleFT8 vor und sendet sofort 73.
- Wenn ein R-Report waehrend des ersten Anrufs empfangen wird, springt SimpleFT8 direkt zu RR73.

Das entspricht dem WSJT-X-Verhalten und schliesst QSOs schneller ab, wenn die Gegenstation in der Sequenz voraus ist.

## HALT-Button

HALT druecken stoppt sofort alles: CQ-Modus, laufendes QSO und TX. Das Radio geht zurueck auf reinen Empfang. Nutze das, wenn du den Betrieb sofort unterbrechen musst.

## Tipps fuer den Betrieb

- **Im Hunt-Modus** lass SimpleFT8 die Wiederholungen machen. Nochmal auf dieselbe Station zu klicken waehrend ein QSO laeuft, startet die Sequenz von vorne.
- **Im CQ-Modus** macht die Warteliste Pile-Ups effizient. Du musst Anrufer nicht manuell auswaehlen.
- **Beobachte das QSO-Panel** fuer Statusmeldungen. Es zeigt jeden Zustandswechsel, Retry und Timeout.
- **Die Stationssperre** verhindert Doppel-QSOs fuer 5 Minuten. Wenn du dieselbe Station nochmal arbeiten willst, warte bis die Sperre abgelaufen ist.
