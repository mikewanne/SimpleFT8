# Frequenzdrift-Kompensation

## Kurz gesagt

Billige QRP-Transceiver (QRP Labs QCX, uBITX usw.) haben instabile Oszillatoren, die waehrend eines 15-Sekunden FT8-Slots um 0,5-5 Hz wegdriften. SimpleFT8 kompensiert diesen Drift und rettet Signale, die normale Decoder nicht mehr knacken.

## Das Problem

- FT8 nutzt 79 Symbole ueber 12,64 Sekunden, jedes auf einer exakten Frequenz.
- Der LDPC-Decoder erwartet eine stabile Frequenz — Drift verschmiert die Symbol-Energie ueber mehrere FFT-Bins.
- Bei 6,25 Hz Tonabstand bedeutet schon 1 Hz Drift einen Frequenzfehler von 16%.
- Unser FlexRadio hat einen GNSS-gestuetzten Oszillator (kein Drift), aber die *sendende* Gegenstation driftet.
- Ergebnis: Wir dekodieren Signale von billigen Radios nicht, die eigentlich ueber dem Rauschboden liegen.

## Wie Drift die Dekodierung ruiniert

Der FT8-Tonabstand betraegt 6,25 Hz. Diese Zahl bestimmt, wie viel Drift der Decoder verkraften kann, bevor es schiefgeht.

- **1 Hz Drift** ueber 12,64 Sekunden verschiebt das letzte Symbol um 1/6,25 = **16%** einer Bin-Breite. Der Decoder kommt noch klar, aber die Reserve schrumpft bereits.
- **3 Hz Drift** verschiebt um 48% — fast ein halbes Bin. Das Symbol liegt jetzt fast genau zwischen zwei FFT-Bins, und die Dekodierzuverlaessigkeit sinkt massiv.
- **5 Hz Drift** bringt es auf 80%. Das Signal sitzt fuer die letzten Symbole praktisch im falschen Bin.

Die LDPC-Fehlerkorrektur ist maechtig, aber sie ist fuer zufaelliges Rauschen ausgelegt, nicht fuer systematische Verzerrung. Drift wuerfelt nicht zufaellig Bits durcheinander — er verschiebt jedes Symbol in die gleiche Richtung, und die Fehler addieren sich. Damit kommt die LDPC nicht gut zurecht.

## So kompensiert SimpleFT8

Die Drift-Kompensation laeuft als zweite Stufe, nachdem der normale Decoder fertig ist.

1. **Normaler Decode** laeuft zuerst (Standard-Pipeline, keine Drift-Korrektur).
2. **Signal-Subtraktion** entfernt alle erfolgreich dekodierten Stationen aus dem Audio.
3. Auf dem **Rest-Audio** (alles was der normale Decoder nicht knacken konnte) wird eine lineare Drift-Korrektur bei 4 Raten angewendet: +0,5, -0,5, +1,5, -1,5 Hz/s.
4. Fuer jede korrigierte Version laeuft der komplette Decoder noch einmal.
5. Neue Dekodierungen sind Stationen, die wegen Drift verpasst wurden.

Weil die Korrektur nur auf dem Rest-Audio laeuft, beeinflusst sie normale Dekodierungen nie. Stationen mit stabilem Oszillator werden in Schritt 1 dekodiert und vor Schritt 3 bereits subtrahiert.

### Die Mathematik

Ein linearer Frequenzdrift *d* (Hz/s) erzeugt eine quadratische Phasenverschiebung im Signal:

```
phi(t) = 2*pi * (f0*t + d/2 * t^2)
```

Der erste Term ist die Traegerfrequenz. Der zweite Term ist der Drift — er waechst mit dem Quadrat der Zeit, weshalb selbst ein kleiner Drift am Ende einer 12,64-Sekunden-Sendung spuerbaren Frequenzfehler erzeugt.

Um den Drift zu entfernen, multipliziert man das Signal mit dem konjugiert-komplexen Gegenstueck der Drift-Komponente:

```
correction(t) = exp(-j*pi * d * t^2)
```

Das hebt die quadratische Phase auf und drueckt das gedriftete Signal zurueck auf eine feste Frequenz.

Da unser Audio reell ist (kein komplexes IQ-Signal), wandelt die Implementierung zunaechst per Hilbert-Transformation (FFT-basiert) in ein analytisches Signal um, wendet die Korrektur im komplexen Bereich an und nimmt dann den Realteil, um wieder reelles Audio zu erhalten. Das korrigierte Audio durchlaeuft danach die normale Decoder-Pipeline, als haette die Gegenstation nie gedriftet.

### Warum genau diese Drift-Raten?

Die vier Raten (+/-0,5 und +/-1,5 Hz/s) sind nicht willkuerlich gewaehlt:

- **+/-0,5 Hz/s** deckt 0-6 Hz Gesamtdrift ueber einen 12,64s-Slot ab. Das ist der typische Bereich fuer Quarzoszillatoren beim Aufwaermen oder bei Temperaturaenderungen — das haeufigste Szenario bei QRP-Bausaetzen.
- **+/-1,5 Hz/s** deckt 0-19 Hz Gesamtdrift ab. Das erwischt Extremfaelle: billige LC-VFOs, Bausaetze mit schlechtem Waermemanagement oder Stationen die draussen bei wechselnden Temperaturen funken.

Zusammen decken diese vier Raten geschaetzt 80-90% des realen QRP-Drifts ab. Wir muessen nicht jede moegliche Rate abdecken — LDPC verkraftet Restfehler von wenigen Prozent einer Bin-Breite, also reicht es, nah genug ranzukommen.

## Erwarteter Gewinn

- Geschaetzt **+5-10% mehr Dekodierungen** auf Baendern mit QRP-Aktivitaet (40m, 20m).
- Staerkster Effekt bei marginalen Signalen (-20 bis -24 dB SNR) von driftenden Stationen — das sind Signale, die knapp ueber der Dekodier-Schwelle liegen und durch den Drift drunter gerueckt werden.
- Kein Effekt auf Stationen mit stabilem Oszillator (die meisten kommerziellen Radios). Die werden schon im normalen Durchlauf dekodiert.
- **UNGETESTET** — das sind theoretische Schaetzungen basierend auf der Mathematik und typischen QRP-Oszillator-Spezifikationen. Feld-Validierung steht aus.

## Performance-Auswirkung

- 4 zusaetzliche Decoder-Durchlaeufe auf dem Rest-Audio (einer pro Drift-Rate).
- Jeder Durchlauf dauert ca. 100ms (C-Bibliothek, schnell).
- Zusaetzliche Gesamtzeit: ~400ms pro 15-Sekunden-Zyklus.
- Locker im Budget — die gesamte Dekodierzeit liegt typisch bei 500-1000ms, und der 15-Sekunden-Zyklus hat reichlich Luft.

## Vor- und Nachteile

| Vorteil | Nachteil |
|---------|----------|
| Rettet Signale von billigen QRP-Radios | +400ms Dekodierzeit pro Zyklus |
| Vollautomatisch, keine Konfiguration noetig | Theoretisch: seltene Fehl-Dekodierungen moeglich |
| Laeuft nur auf Rest-Audio (beeinflusst normale Dekodierungen nicht) | UNGETESTET — braucht Feld-Tests |
| Hilft dem "kleinen Mann" mit Budget-Ausruestung | Kein Effekt auf Stationen die nicht driften |

## Status

**UNGETESTET** — Implementiert in v0.30, Feld-Validierung steht aus.
Achte auf `[Drift] +N Stationen` im Log, um zu sehen ob die Drift-Kompensation zusaetzliche Dekodierungen findet.
