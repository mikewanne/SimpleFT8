# Frequenz-Histogramm & CQ-Frequenzwahl

[Zurück zur README](../README.md) | [Diversity](DIVERSITY_DE.md) | [DX-Tuning](DX_TUNING_DE.md) | [DT-Korrektur](DT_CORRECTION_DE.md)

## Was du siehst

Das Histogramm im Panel oben rechts zeigt, welche Audiofrequenzen (150–2800 Hz) gerade von anderen Stationen belegt sind. Es spiegelt exakt dieselben Stationen wider, die auch im RX-Fenster sichtbar sind — nicht mehr und nicht weniger.

**Farbcodierung:**
- **Grau** — eine Station in diesem 50-Hz-Bereich
- **Orange** — zwei bis drei Stationen
- **Rot** — vier oder mehr Stationen (stark belegt)
- **Gelber Marker** — deine vorgeschlagene CQ-Frequenz (eine freie Lücke)

## Datenquelle: Echtzeit, 1:1 mit dem RX-Fenster

Das Histogramm wird nach jedem Dekodierzyklus aus dem Stationsspeicher neu aufgebaut. Der Stationsspeicher hält Stationen für:
- **75 Sekunden** — normale Stationen
- **150 Sekunden** — Stationen in deinem aktiven QSO
- **300 Sekunden** — aktive CQ-Rufer

Das Histogramm deckt damit automatisch mehrere Zyklen ab, einschließlich Even- und Odd-Slots. Wenn eine Station aus dem RX-Fenster verschwindet (Alterung), verschwindet sie auch aus dem Histogramm. Was im Histogramm steht, stimmt mit dem RX-Fenster überein.

## Wie die freie CQ-Frequenz gefunden wird

SimpleFT8 scannt den gesamten Audiobereich (150–2800 Hz) nach Lücken — Frequenzbereichen ohne aktive Stationen. Eine Lücke muss mindestens 150 Hz breit sein, um als nutzbar zu gelten.

Aus allen gefundenen Lücken wird diejenige gewählt, die **am nächsten am Median aller belegten Frequenzen** liegt. Wenn die meisten Stationen um 1200 Hz clustern, wählt der Algorithmus den nächsten freien Bereich zu diesem Schwerpunkt — nicht den nächsten Bereich zu 0 Hz oder 3000 Hz.

**Wenn keine Lücke gefunden wird** (extrem volles Band): Die aktuelle TX-Frequenz bleibt unverändert.

## Wann wird die Frequenz neu berechnet?

| Auslöser | Bedingung |
|----------|-----------|
| **Erstbenutzung** | Beim ersten CQ nach Band- oder Modus-Wechsel |
| **Kollision** | ≥ 3 Stationen erscheinen innerhalb ±50 Hz der TX-Frequenz (nach mind. 3 Zyklen Dwell-Time) |
| **Timer** | Alle 10 Zyklen (~150 s bei FT8, ~75 s bei FT4, ~38 s bei FT2) |
| **QSO-Schutz** | Keine Neuberechnung während eines aktiven QSOs |

Der Algorithmus ist bewusst konservativ: Er bleibt auf einer gewählten Frequenz, solange sie frei ist, und wechselt nur wenn nötig.

## Technische Details

| Parameter | Wert |
|-----------|------|
| Bin-Breite | 50 Hz |
| Suchbereich | 150–2800 Hz |
| Mindest-Lücke | 150 Hz (3 Bins) |
| Neuberechnungsintervall | 10 Zyklen |
| Mindest-Verweildauer | 3 Zyklen vor Kollisionsprüfung |
| QSO-Schutz | Aktiv solange QSO-Status nicht IDLE/TIMEOUT |
