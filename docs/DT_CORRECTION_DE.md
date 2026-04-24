# DT-Zeitkorrektur

[Zurück zur README](../README.md) | [Diversity](DIVERSITY_DE.md) | [Frequenz-Histogramm](FREQUENCY_HISTOGRAM_DE.md)

## Was ist DT?

Jede dekodierte FT8-Nachricht enthält einen **DT-Wert** — den Zeitversatz in Sekunden zwischen dem Beginn des Sendeslots der Gegenstation und dem Empfangszeitpunkt bei dir. Im Idealfall liegt DT bei 0.0. Wenn deine Uhr oder die Audio-Pipeline deines Funkgeräts eine konstante Verzögerung einführt, werden alle empfangenen DT-Werte systematisch verschoben.

SimpleFT8 misst diese Verschiebung und kompensiert sie automatisch.

## Zweistufige Architektur

Der gesamte Timing-Fehler wird in zwei Komponenten aufgeteilt:

### Stufe 1 — Fester Hardware-Offset (hardcodiert)

Das FlexRadio SmartSDR führt eine konstante Verzögerung in der Audio-Pipeline ein. Diese ist eine bekannte, stabile Hardware-Eigenschaft, die sich zwischen Sitzungen nicht ändert. Sie wird durch einen festen Offset direkt im Decoder kompensiert (`DT_BUFFER_OFFSET`):

| Modus | DT_BUFFER_OFFSET |
|-------|-----------------|
| FT8   | 2,0 s           |
| FT4   | 1,0 s           |
| FT2   | 0,8 s           |

Diese Werte beinhalten bereits die 0,5 s WSJT-X-Protokollkonvention. Nach der Subtraktion beträgt der verbleibende DT-Fehler typischerweise nur noch ±0,3 s.

### Stufe 2 — Adaptive Korrektur (automatisch)

Nach dem Abzug des festen Offsets verbleibt ein kleiner Restfehler (~0,27 s beim FlexRadio VITA-49). Dieser wird adaptiv durch `core/ntp_time.py` korrigiert:

1. **Messphase** (2 Zyklen): DT-Werte aller dekodierten Stationen sammeln, Median berechnen
2. **Korrektur anwenden**: Interne Zeit um 70% des gemessenen Median-Fehlers anpassen
3. **Betriebsphase** (10 Zyklen): Mit der aktuellen Korrektur senden
4. **Wiederholen**: Alle ~150 s neu messen (FT8), Ergebnis auf Disk speichern

Korrekturen werden **pro Modus und Band** gespeichert: Ein Wechsel von 40m FT8 zu 20m FT8 lädt einen separaten gespeicherten Wert — jede Band-/Modus-Kombination konvergiert unabhängig und startet in der nächsten Sitzung von einem guten Ausgangswert.

## Warum fest + adaptiv?

Früher wurde der gesamte Fehler von ~0,77 s adaptiv behandelt. Das hatte zwei Nachteile:
- **Kalter Start** brauchte viele Zyklen zum Konvergieren (Korrektur startete bei 0, musste sich auf 0,77 s einpendeln)
- **Großer adaptiver Bereich** führte zu langsamer, rauschbehafteter Konvergenz

Durch Hardcodierung der stabilen FlexRadio-Konstante (~0,5 s) muss die adaptive Stufe nur noch ~0,27 s ausregeln. Konvergenz ist schneller und stabiler.

## Speicherung

Korrekturen werden in `~/.simpleft8/dt_corrections.json` gespeichert:

```json
{
  "FT8_20m": 0.24,
  "FT8_40m": 0.27,
  "FT4_20m": 0.25
}
```

Bei Band- oder Modus-Wechsel wird der gespeicherte Wert für die neue Kombination sofort geladen. Existiert kein Wert, startet die adaptive Stufe bei 0 und konvergiert innerhalb weniger Zyklen.

## Parameter

| Parameter | Wert | Bedeutung |
|-----------|------|-----------|
| Messzyklen | 2 | Zyklen pro Messfenster |
| Betriebszyklen | 10 | Zyklen zwischen Messungen |
| Dämpfung | 70% | Nur 70% des gemessenen Fehlers wird pro Schritt angewendet |
| Totband | 50 ms | Korrekturen kleiner als dieser Wert werden ignoriert |
| Max. Korrektur (FT8) | ±1,0 s | Sicherheitsgrenze |
| Max. Korrektur (FT4) | ±0,5 s | |
| Max. Korrektur (FT2) | ±0,3 s | |
| Sprungdetektion | > 1,0 s | Vollständiger Reset bei plötzlichem DT-Ausreißer |

## TX-Timing

Beim Senden puffert das FlexRadio Audio-Samples ~1,3 s vor der HF-Ausgabe. Dies wird durch `TARGET_TX_OFFSET = -0,8 s` im Encoder kompensiert:

```
TARGET_TX_OFFSET = 0,5 s (Protokoll) − 1,3 s (FlexRadio TX-Buffer) = −0,8 s
```

Dieser Wert ist FlexRadio-spezifisch. Ein anderes Funkgerät (z. B. IC-7300) benötigt einen eigens gemessenen Wert.
