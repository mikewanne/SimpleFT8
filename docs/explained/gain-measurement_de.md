# Gain-Messung — Automatische Preamp-Optimierung

## Kurzfassung

DX Tuning misst den optimalen Preamp-Gain fuer jede Antenne auf dem aktuellen Band. Es dauert 4,5 Minuten, laeuft im Hintergrund, und speichert die Ergebnisse als Band-Presets, die bei jedem Bandwechsel automatisch geladen werden.

## Das Problem

Jede Antenne verhalt sich auf jedem Band anders. Der Preamp-Gain, der auf 20m den besten Schwachsignal-Empfang liefert, kann auf 40m zu viel Rauschen addieren oder auf 10m den ADC uebersteuern. Die meisten Funker stellen ihren Preamp einmal ein und lassen ihn so — aber die Bedingungen aendern sich mit Wetter, Tageszeit und Jahreszeit.

Ohne Messung raetst du. Mit Messung weisst du es.

## Was DX Tuning misst

DX Tuning testet **beide Antennen** bei **drei Gain-Stufen** (0 dB, 10 dB, 20 dB) und bestimmt:

- Welche Gain-Stufe den besten Durchschnitts-SNR auf ANT1 liefert
- Welche Gain-Stufe den besten Durchschnitts-SNR auf ANT2 liefert
- Welche Antennen+Gain-Kombination insgesamt am besten ist

Das Ergebnis sagt dir: "Auf 20m ist gerade ANT2 bei 0 dB Gain der beste Empfang."

## So fuehrst du eine Messung durch

1. Klicke den **DX Tuning**-Button im Antennen-Bereich.
2. Optional vorher TUNE nutzen, um die SWR der Antennen zu pruefen.
3. Der Messdialog oeffnet sich und laeuft automatisch.
4. 4,5 Minuten warten (18 FT8-Zyklen). Du kannst den Fortschritt in Echtzeit beobachten.
5. Am Ende auf **Preset speichern** klicken, um die Ergebnisse zu sichern.

Du kannst jederzeit mit **Abbrechen** abbrechen. Das Radio kehrt zu den vorherigen Einstellungen zurueck.

## So funktioniert es intern

Die Messung laeuft in 3 Runden mit je 6 Zyklen (18 Zyklen gesamt):

```
Runde 1: ANT1@0dB → ANT2@0dB → ANT1@10dB → ANT2@10dB → ANT1@20dB → ANT2@20dB
Runde 2: ANT2@0dB → ANT1@0dB → ANT2@10dB → ANT1@10dB → ANT2@20dB → ANT1@20dB
Runde 3: ANT1@0dB → ANT2@0dB → ANT1@10dB → ANT2@10dB → ANT1@20dB → ANT2@20dB
```

Das verschraenkte Muster stellt sicher, dass ANT1 und ANT2 unter nahezu identischen Ausbreitungsbedingungen gemessen werden. Die wechselnde Runden-Reihenfolge (erst ANT1, dann ANT2 zuerst) reduziert den Zeitfehler weiter.

Fuer jede Antennen+Gain-Kombination sammelt SimpleFT8 alle dekodierten Stations-SNR-Werte und berechnet den **Top-5-Durchschnitt** — den Mittelwert der fuenf staerksten Signale. Dieser Wert bildet die reale DX-Empfangsqualitaet besser ab als die reine Stationsanzahl.

### ADC-Uebersteuerungserkennung

Wenn eine Gain-Einstellung den ADC uebersteuert (zu viele Signale ueber +20 dB oder verdaechtig niedrige SNR-Varianz), wird diese Kombination automatisch aus den Ergebnissen ausgeschlossen. Der Dialog zeigt eine Warnmarkierung fuer uebersteuerter Schritte.

## Ergebnisse und Presets

Nach der Messung siehst du eine Zusammenfassung wie:

```
ANT1:
  ANT1 Gain  0 dB:  Ø  -0,8 dB  (13 St.)
  ANT1 Gain 10 dB:  Ø  -4,6 dB  ( 8 St.)
  ANT1 Gain 20 dB:  Ø  +1,6 dB  ( 9 St.)  ←
ANT2:
  ANT2 Gain  0 dB:  Ø  +3,0 dB  (25 St.)  ←
  ANT2 Gain 10 dB:  Ø  +7,6 dB  (21 St.)
  ANT2 Gain 20 dB:  Ø  +1,2 dB  (11 St.)
```

Die Pfeile zeigen den optimalen Gain fuer jede Antenne. Beim Speichern des Presets sichert SimpleFT8 beide Werte pro Band. Der Diversity-Modus nutzt dann den richtigen Gain beim Antennen-Umschalten: den optimalen Gain von ANT1 beim Empfang auf ANT1, den von ANT2 beim Empfang auf ANT2.

Presets werden beim Bandwechsel automatisch geladen.

## Wann du neu messen solltest

| Situation | Empfehlung |
|-----------|------------|
| Taeglicher DX-Betrieb | Einmal am Anfang der Session messen |
| Nach Antennen-Aenderungen | Immer neu messen (Hardware hat sich geaendert) |
| Nach starkem Wetter | Regen, Eis oder Sturm koennen die Antennenleistung verschieben |
| Saisonale Aenderungen | Ausbreitungswege aendern sich, andere Antennen koennten besser sein |
| Empfang scheint schlechter als ueblich | Schnelle Nachmessung zur Kontrolle |

Die Messung dauert nur 4,5 Minuten und laeuft im Hintergrund — du empfaengst ganz normal weiter. Es gibt keinen Grund, nicht zu messen.

## Gain-Messung vs. Diversity

Diese beiden Funktionen arbeiten zusammen, messen aber verschiedene Dinge:

| Funktion | Was sie misst | Ergebnis |
|----------|---------------|----------|
| **Gain-Messung** | Hardware-Leistung: welcher Preamp-Wert ist am besten pro Antenne | Optimaler dB-Gain pro Antenne pro Band |
| **Diversity** | Ausbreitungs-Leistung: welche Antenne empfaengt gerade mehr Stationen | Antennen-Umschaltverhaltnis (50:50, 70:30, etc.) |

Fuehre zuerst die Gain-Messung durch, um die optimalen Hardware-Einstellungen zu finden. Dann lass Diversity diese Einstellungen nutzen, um die Antennen basierend auf der Ausbreitung umzuschalten.

## Technische Details

- TX bleibt waehrend der gesamten Messung auf ANT1 (nur die RX-Antenne wird umgeschaltet).
- Der erste Zyklus wird uebersprungen (kann ein unvollstaendiger FT8-Slot von vor der Messung sein).
- Der Gain wird ueber den FlexRadio SmartSDR API `rfgain`-Parameter gesetzt.
- Jede Kombination bekommt 3 Messzyklen verteilt ueber 3 Runden, also insgesamt 9 dekodierte Stationslisten pro Antenne.
- Ergebnisse werden in der SimpleFT8-Einstellungsdatei gespeichert und bleiben ueber Neustarts erhalten.
