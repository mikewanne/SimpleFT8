# Propagation-Indikatoren

## Kurz gesagt

Farbige Balken unter jedem Band-Button zeigen die aktuellen KW-Ausbreitungsbedingungen — gruen (gut), gelb (mittel), rot (schlecht) — basierend auf HamQSL-Solardaten mit Tageszeit-Korrektur fuer Mitteleuropa.

## Das Problem

- "Soll ich gerade 10m oder 40m probieren?" — die taegliche Frage jedes Funkers.
- Manuell HamQSL/DXHeat/VOACAP pruefen unterbricht den Workflow.
- Solarbedingungen aendern sich im Tagesverlauf — ein Band das mittags "gut" ist, kann nachts tot sein.
- HamQSL liefert globale Tag/Nacht-Bewertungen, aber DEINE lokale Tageszeit ist entscheidend.

## Wie es funktioniert

1. Ein Hintergrund-Thread holt alle 3 Stunden XML von `https://www.hamqsl.com/solarxml.php`.
2. Das XML enthaelt Band-Vorhersagen: good, fair oder poor fuer jedes KW-Band, getrennt nach "day" und "night".
3. SimpleFT8 wendet eine Tageszeit-Korrektur fuer Mitteleuropa an (UTC-basierte Regeln pro Band), um die richtige Bewertung auszuwaehlen und gegebenenfalls herabzustufen.
4. Ein 4 Pixel hoher Farbbalken erscheint unter jedem Band-Button.
5. Farben: gruen (#00CC00) = gut, gelb (#FFAA00) = mittel, rot (#CC0000) = schlecht, grau = keine Daten.

## Tageszeit-Korrektur (Mitteleuropa)

HamQSL liefert separate "day"- und "night"-Vorhersagen, sagt aber nicht, wann fuer deinen Standort Tag aufhoert und Nacht anfaengt. Diese Luecke schliesst die Korrektur.

Die Regeln basieren auf typischen mitteleuropaeischen Ausbreitungsfenstern. Jedes Band hat Stunden in denen es voraussichtlich nutzbar ist ("gute Stunden") und Stunden in denen die Bewertung um eine Stufe herabgesetzt wird, weil das Band zu dieser Zeit wahrscheinlich tot oder grenzwertig ist.

| Band | Gute Stunden (UTC) | Herabgestufte Stunden | Grund |
|------|--------------------|-----------------------|-------|
| 80m  | 00-07, 20-24       | 07-20 (tagsueber, -1 Stufe) | Low-Band, braucht Dunkelheit fuer Weitverkehr |
| 40m  | 00-07, 19-24       | 07-19 (tagsueber, -1 Stufe) | Aehnlich wie 80m, aber etwas breiteres Nutzfenster |
| 20m  | 09-20              | 00-09, 20-24 (nachts, -1 Stufe) | Tagesband, braucht Sonnenbeleuchtung der Ionosphaere |
| 15m  | 10-19              | 00-10, 19-24 (nachts, -1 Stufe) | Kuerzeres Tagesfenster als 20m |
| 10m  | 11-18              | 00-11, 18-24 (nachts, -1 Stufe) | Hoechstes KW-Band, braucht maximale Sonnenbeleuchtung |

"-1 Stufe" bedeutet: gut wird mittel, mittel wird schlecht, schlecht bleibt schlecht.

Das sind grobe Regeln. Echte Ausbreitung funktioniert nicht wie ein Schalter — 20m stirbt nicht genau um 20:00 UTC. Aber fuer einen schnellen visuellen Indikator reicht grob voellig aus. Die Alternative waere, die HamQSL-Rohdaten anzuzeigen: "20m: good (day), fair (night)" — ohne zu sagen, welcher Wert gerade gilt. Das ist weniger nuetzlich.

## Datenquelle

- **HamQSL.com** — kostenlos, kein API-Key, kein Login noetig.
- Basiert auf Solar Flux Index (SFI), K-Index, A-Index — diese Solarparameter bestimmen die ionosphaerischen Bedingungen.
- Daten aendern sich langsam (Solarindizes werden alle paar Stunden aktualisiert), daher reicht Abfrage alle 3 Stunden.
- Bei Netzwerkfehler: Balken werden grau und verschwinden. Kein Absturz, keine veralteten Daten angezeigt.

## Unterschied zu anderen Programmen (Ham Toolbox, VOACAP etc.)

Die meisten Tools (Ham Toolbox, DXHeat, etc.) zeigen nur **Tag/Nacht** global an — z.B. "20m tagsüber: Good, nachts: Fair". Aber was bedeutet das um 9 Uhr morgens, wenn das Band gerade erst öffnet?

**SimpleFT8 geht einen Schritt weiter:** Wir berücksichtigen die **tatsächlichen Öffnungszeiten** jedes Bandes für Mitteleuropa. Beispiele:

- **20m um 8 UTC:** Ham Toolbox zeigt "Day: Good" — aber das Band ist um 8 Uhr morgens noch nicht richtig offen. SimpleFT8 stuft auf "Fair" herab.
- **80m um 19 UTC:** Ham Toolbox zeigt "Day: Bad" — aber 80m öffnet abends bereits. SimpleFT8 nutzt den Nacht-Wert (oft "Fair" oder "Good").
- **10m um 17 UTC:** Ham Toolbox zeigt "Day: Good" — das stimmt, 10m ist nachmittags optimal. SimpleFT8 zeigt auch "Good".

**Kurz:** Andere Tools zeigen was die Sonne global macht. Wir zeigen was das Band **jetzt für dich** kann.

## Warum keine Jahreszeiten?

Kurze Antwort: Der Aufwand steht nicht im Verhältnis zum Nutzen.

Jahreszeiten-Berücksichtigung (Sommer/Winter) würde erfordern:
- Sonnenstand-Berechnung (Ephemeriden)
- Geografische Position des Nutzers
- Deutlich komplexere Modelle pro Band

Die aktuellen UTC-Stundenregeln decken bereits ~80% der Fälle ab. Die restlichen 20% sind ohnehin unvorhersagbar (Sporadic-E im Sommer, Aurora, geomagnetische Stürme). Die Propagation-Balken sind eine **schnelle Orientierung**, kein Ersatz für eigene Erfahrung.

## Was es nicht kann

- Sagt keine lokale Ausbreitung vorher. Ein gruener Balken auf 10m bedeutet: Solarbedingungen unterstuetzen 10m-Ausbreitung global — nicht dass du von JO31 aus gerade jemanden hoerst.
- Beruecksichtigt keine geomagnetischen Stuerme in Echtzeit (K-Index ist Teil der Daten, aber die Zeitkorrektur ist statisch).
- 60m fehlt, weil HamQSL es nicht abdeckt.
- Zeitkorrektur ist fest auf Mitteleuropa eingestellt. Wer in VK/ZL oder JA sitzt, hat falsche "gute Stunden". Koennte konfigurierbar gemacht werden, ist es aber noch nicht.

## Vor- und Nachteile

| Vorteil | Nachteil |
|---------|----------|
| Sofortige visuelle Bandempfehlung | Nur Mitteleuropa-Zeitkorrektur |
| Kein API-Key oder Login noetig | HamQSL-Daten koennen Stunden alt sein |
| Automatische Hintergrund-Aktualisierung | 60m nicht abgedeckt (fehlt bei HamQSL) |
| Winziger UI-Footprint (4px Balken) | Generische Vorhersage, keine lokale Ausbreitung |

## Status

UNGETESTET — Aktiv seit v0.23. Pruefe: Stimmen die Farben mit deiner Erfahrung ueberein? 80m mittags sollte rot zeigen. 20m mittags sollte gruen zeigen (bei ordentlichem SFI).
