# RMS Auto-Gain Control

## Kurz gesagt

Automatische Pegelregelung am Decodereingang, die eine Uebersteuerung auf vollen Baendern (40m abends) verhindert und gleichzeitig die Empfindlichkeit auf ruhigen Baendern erhaelt.

## Das Problem

- 40m um 20:00 UTC: 50+ starke Stationen, deren kombinierte Audioleistung den Decoder ueberlaeuft.
- Das Spectral Whitening des Decoders erwartet einen bestimmten Pegelbereich.
- Zu laut: Whitening kann das Spektrum nicht glaetten — starke Signale ueberdecken schwache.
- Zu leise: Dynamikbereich verschenkt, schwache Signale rutschen unter die Decoderschwelle.
- Verschiedene Baender haben voellig unterschiedliche Signalpegel (80m abends vs. 10m tagsueber).

## Wie es funktioniert

- Misst die RMS-Leistung (Root Mean Square) des 12-kHz-Audios nach dem Resampling.
- Zielwert: -12 dBFS (= 8225 in der int16-Skala, etwa 25% der Vollaussteuerung).
- Passt die Verstaerkung langsam per EMA-Glaettung an (alpha=0,02 — Aenderung ueber ~50 Zyklen, nicht pro Zyklus).
- +/-3 dB Hysterese-Totband: kleine Schwankungen loesen keine Anpassung aus.
- Verstaerkungsgrenzen: 0,1x (-20 dB) Minimum bis 4,0x (+12 dB) Maximum.
- Position in der Kette: NACH dem 24->12 kHz Resampling, VOR dem Spectral Whitening.

## Die Mathematik

RMS misst die mittlere Signalleistung, nicht die Spitzenamplitude. Das ist hier die richtige Metrik, weil FT8-Signale sich in Frequenz und Zeit ueberlagern — Spitzenwerte sagen etwas ueber die lauteste Station, aber RMS sagt etwas ueber die Gesamtenergie, die der Decoder verarbeiten muss.

```
RMS = sqrt(mean(samples^2))
```

Die AGC vergleicht den gemessenen RMS-Wert mit dem festen Zielwert und berechnet die Verstaerkung, die noetig waere um den Zielwert zu erreichen:

```
Ziel-RMS = 8225 (int16-Skala, entspricht -12 dBFS)
Gewuenschte Verstaerkung = Zielwert / gemessener_RMS
```

Diese gewuenschte Verstaerkung wird nicht direkt angewendet. Stattdessen fliesst sie in einen exponentiell gleitenden Mittelwert (EMA), der die Verstaerkungsaenderungen ueber viele Zyklen glaettet:

```
gain_neu = 0,02 * gewuenscht + 0,98 * gain_alt
```

Der EMA wirkt als Tiefpassfilter auf Verstaerkungsaenderungen. Bei alpha=0,02 betraegt die effektive Zeitkonstante etwa 1/0,02 = 50 Zyklen = 50 x 15 Sekunden = 12,5 Minuten. Die AGC braucht also rund 12 Minuten, um sich komplett an eine neue Bandsituation anzupassen.

Die Hysterese verhindert staendige kleine Korrekturen wenn das Band stabil ist:

```
Verhaeltnis = gewuenschte_Verstaerkung / EMA_Verstaerkung
Schwellwert = 10^(3/20) = 1,41 (also 3 dB)
Aktualisierung nur wenn Verhaeltnis > 1,41 oder < 1/1,41
```

Zuletzt sorgt ein Clipping-Schutz dafuer, dass kein Sample den int16-Bereich ueberschreitet:

```
Ausgabe = clip(audio * gain, -32767, 32767)
```

## Warum alpha=0,02 (so langsam)?

- FT8-Zyklus = 15 Sekunden. Die AGC darf NICHT innerhalb eines Zyklus reagieren.
- Schnelle AGC wuerde "pumpen": Verstaerkung sinkt waehrend eines starken Signals, steigt in der Luecke zwischen Signalen wieder an, sinkt wieder. Das erzeugt kuenstliche Amplitudenmodulation, die der Decoder als Rauschen sieht.
- alpha=0,02 ergibt eine effektive Zeitkonstante von ~50 Zyklen = ~12,5 Minuten.
- Passt sich an langsame Aenderungen an (Bandoeffnungen, Tag/Nacht-Wechsel), ignoriert aber einzelne Stationen die auftauchen und verschwinden.
- Kompromiss: Beim Bandwechsel braucht die AGC 2-3 Minuten zum Einschwingen. In den ersten Zyklen gilt noch die Verstaerkung vom alten Band. Die Gain-Grenzen (0,1x bis 4,0x) verhindern, dass das zur Katastrophe wird.

## Erwarteter Gewinn

- Verhindert Decoder-Saettigung auf vollen Baendern — geschaetzt +10-20% Dekodierungen auf 40m abends.
- Erhaelt die Empfindlichkeit auf ruhigen Baendern — schwaches DX geht nicht durch zu geringe Verstaerkung verloren.
- UNGETESTET — Schaetzungen basieren auf Simulation, Feld-Validierung steht aus.

## Vor- und Nachteile

| Vorteil | Nachteil |
|---------|----------|
| Automatisch, kein Benutzereingriff noetig | Sehr langsame Reaktion (~12 Min Zeitkonstante) |
| Verhindert Decoder-Uebersteuerung auf vollen Baendern | Wechselwirkung mit vorhandener Noise-Floor-Normalisierung |
| Clipping-Schutz eingebaut | Auf stillem Band: Gain steigt auf 4x Maximum (erholt sich wenn Signale kommen) |
| Bandwechsel: passt sich in 2-3 Minuten an | — |

## Status

UNGETESTET — Aktiv seit v0.27. Achte auf `[AGC] Gain=X.XXx` im Log.
