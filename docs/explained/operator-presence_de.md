# Operator Presence Timer (Totmannschalter)

## Kurz gesagt

SimpleFT8 erzwingt eine 15-Minuten-Inaktivitaetssperre, damit immer ein lizenzierter Operator an der Station sitzt — ohne Ausnahme, ohne Konfiguration, ohne Hintertuer.

## Das Problem

FT8 laeuft weitgehend automatisch. Die Software dekodiert, waehlt die richtige Antwort und sendet — ohne dass der Operator etwas tun muss. Das ist gewollt und macht FT8 effizient. Aber es hat eine Kehrseite: Wenn du aufstehst, Kaffee holst und es vergisst, ruft deine Station froehlich weiter CQ und arbeitet Stationen ab. Ab diesem Moment betreibst du einen unbeaufsichtigten Bot — und das ist im Amateurfunk nicht erlaubt.

Das deutsche Recht ist da eindeutig: Der Operator muss jederzeit eingreifen koennen. Andere Laender haben aehnliche Regeln, und die IARU empfiehlt beaufsichtigten Betrieb fuer alle automatisierten Digimodes. SimpleFT8 nimmt das ernst. Statt sich auf die guten Vorsaetze des Operators zu verlassen, erzwingt die Software die Anwesenheit mit einem harten Timer — einem digitalen Totmannschalter.

## Wie funktioniert es?

- Ein fester **15-Minuten-Countdown** startet, sobald SimpleFT8 keine Maus- oder Tastaturaktivitaet im Anwendungsfenster erkennt.
- Ein **4 Pixel hoher Fortschrittsbalken** sitzt direkt unter dem CQ-Button als visuelle Anzeige:
  - **Gruen** — mehr als 5 Minuten uebrig. Alles in Ordnung.
  - **Gelb** — zwischen 2 und 5 Minuten uebrig. Zeit, die Maus zu bewegen oder eine Taste zu druecken.
  - **Rot** — weniger als 2 Minuten uebrig. CQ wird gleich gestoppt.
- Jede **Maus- oder Tastaturaktivitaet innerhalb des SimpleFT8-Fensters** setzt den Timer auf 15 Minuten zurueck. Aktivitaet in anderen Programmen zaehlt nicht — du musst tatsaechlich SimpleFT8 im Blick haben.
- Wenn der Timer Null erreicht:
  - **CQ-Rufe stoppen sofort.** Keine neuen CQ-Sendungen.
  - **Keine neuen TX-Sequenzen werden gestartet.** Die Station wird still.
- **Laufende QSOs werden immer geschuetzt.** Wenn du mitten in einem QSO bist (irgendwo zwischen TX_CALL und TX_RR73), wird der Austausch sauber zu Ende gefuehrt. SimpleFT8 bricht nie ein QSO mittendrin ab — das waere schlechter Betriebsstil und voellig sinnlos.
- **Nach Abschluss des QSOs** bleibt TX gesperrt, bis der Operator sich meldet (Maus oder Tastatur im SimpleFT8-Fenster).

## Rechtlicher Hintergrund

- **Deutschland, Paragraph 16 AFuV (Amateurfunkverordnung):** Der Funkamateur muss jederzeit in der Lage sein, in den Betrieb der Amateurfunkstelle einzugreifen. Unbeaufsichtigter automatischer Sendebetrieb ist fuer Standardlizenzen nicht zulaessig.
- **IARU-Empfehlung:** Automatisierte digitale Betriebsarten sollen im beaufsichtigten Modus betrieben werden. Der Operator soll die Station ueberwachen und jederzeit eingreifen koennen.
- **SimpleFT8 ist kein Bot.** Es ist ein Operator-Assistenzsystem. Es automatisiert die repetitiven Teile von FT8 (Dekodierung, Antwortauswahl, TX-Sequenzierung), setzt aber einen anwesenden Operator voraus. Der Presence Timer ist der Mechanismus, der diese Unterscheidung durchsetzt.

## Vor- und Nachteile

| Vorteil | Nachteil |
|---------|----------|
| Rechtskonform nach AFuV und internationalen Regelungen | Man muss alle 15 Minuten die Maus bewegen |
| Beweist, dass ein Mensch die Station beaufsichtigt | Kann lange unbeaufsichtigte CQ-Sessions unterbrechen (gewollt!) |
| QSO-Schutz — ein laufender Kontakt wird immer sauber beendet | — |
| Keine Konfiguration = keine Versuchung, den Wert hochzudrehen | — |

## Einstellungen

Keine. Der Timer ist fest auf 15 Minuten eingestellt. Das ist eine bewusste Designentscheidung: Waere der Wert konfigurierbar, wuerde ihn jemand auf 999 Minuten stellen und den ganzen Sinn aushebeln. 15 Minuten sind ein guter Kompromiss — lang genug, dass normaler Betrieb den Timer nicht ausloest, kurz genug, dass Weggehen die Station tatsaechlich stoppt.

## Status

Aktiv seit v0.31. Nicht optional. Kann nicht deaktiviert werden.
